import re
import json

import requests
import mysql.connector
from flask import Flask, render_template, jsonify, request

from db_utils import get_db_cursor
from exceptions import DatabaseError, ValidationError, NotFoundError
from config import app_config, api_config

app = Flask(__name__)

GBIZ_DETAIL_URL = "https://info.gbiz.go.jp/hojin/v1/hojin/{}"
EDINET_BASE = "https://edinetdb.jp/v1"


# ===== ページ =====
@app.route('/')
def index():
    return render_template('index.html')


# ===== 企業一覧（DB全件）=====
@app.route('/api/companies')
def get_companies():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM companies")
            companies = cursor.fetchall()
        return jsonify(companies)
    except mysql.connector.Error as err:
        raise DatabaseError("Failed to retrieve companies", err)


# ===== gBizINFO 法人詳細プロキシ（トークン秘匿）=====
@app.route('/api/company_detail')
def company_detail():
    corporate_number = request.args.get('corporate_number', '').strip()
    if not corporate_number.isdigit():
        raise ValidationError("Invalid corporate_number")

    headers = {'X-hojinInfo-api-token': api_config.gbiz_token, 'Accept': 'application/json'}
    try:
        resp = requests.get(GBIZ_DETAIL_URL.format(corporate_number),
                            headers=headers, timeout=api_config.timeout)
        if resp.status_code != 200:
            return jsonify({'error': f'gBizINFO returned {resp.status_code}'}), 502
        infos = (resp.json() or {}).get('hojin-infos') or []
        if not infos:
            raise NotFoundError("Company not found in gBizINFO")
        return jsonify(infos[0])
    except requests.RequestException as err:
        return jsonify({'error': f'Failed to reach gBizINFO: {err}'}), 502


# ===== edinetdb.jp 企業詳細プロキシ（クォータ節約のためDBキャッシュ）=====
def _edinet_cache_get(code):
    with get_db_cursor() as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS edinet_cache "
            "(code VARCHAR(20) PRIMARY KEY, payload LONGTEXT, "
            "fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("SELECT payload FROM edinet_cache WHERE code=%s", (code,))
        row = cursor.fetchone()
    return json.loads(row['payload']) if row else None


def _edinet_cache_put(code, data):
    with get_db_cursor() as cursor:
        cursor.execute("REPLACE INTO edinet_cache (code, payload) VALUES (%s, %s)",
                       (code, json.dumps(data, ensure_ascii=False)))


@app.route('/api/edinet_detail')
def edinet_detail():
    code = request.args.get('code', '').strip()
    if not code:
        raise ValidationError("code is required")

    if request.args.get('refresh') != '1':
        cached = _edinet_cache_get(code)
        if cached is not None:
            return jsonify({'cached': True, 'data': cached})

    headers = {'X-API-Key': api_config.edinet_api_key}
    try:
        resp = requests.get(f"{EDINET_BASE}/companies/{code}",
                            headers=headers, timeout=api_config.timeout)
    except requests.RequestException as err:
        return jsonify({'error': f'edinetdb detail failed: {err}'}), 502

    if resp.status_code != 200:
        return jsonify({'error': f'edinetdb returned {resp.status_code}',
                        'remaining': resp.headers.get('X-Ratelimit-Remaining')}), resp.status_code

    data = resp.json().get('data', resp.json())
    _edinet_cache_put(code, data)
    return jsonify({'cached': False,
                    'remaining': resp.headers.get('X-Ratelimit-Remaining'),
                    'data': data})


# ===== ジオコーディング（geolonia 町丁目・全国対応）=====
_GEO_TOWN_URL = "https://geolonia.github.io/japanese-addresses/api/ja/{}/{}.json"
_GEO_PREF_RE = re.compile(r"^(.+?[都道府県])")
_GEO_KANJI = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_GEO_Z2H = str.maketrans("０１２３４５６７８９", "0123456789")
_geo_cache = {}


def _geo_kanji_to_int(s):
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total = cur = 0
    for ch in s:
        v = _GEO_KANJI.get(ch)
        if v is None:
            return None
        if v == 10:
            cur = (cur or 1) * 10
            total += cur
            cur = 0
        else:
            cur = v
    return total + cur


def _geo_index(pref, city):
    key = (pref, city)
    if key in _geo_cache:
        return _geo_cache[key]
    precise, town_pts = {}, {}
    try:
        r = requests.get(_GEO_TOWN_URL.format(pref, city), timeout=api_config.timeout)
        if r.status_code == 200:
            for t in r.json():
                town = t.get("town", "")
                m = re.search(r"([一二三四五六七八九十]+)丁目$", town)
                base = town[:m.start()] if m else town
                ch = _geo_kanji_to_int(m.group(1)) if m else None
                lat, lng = t.get("lat"), t.get("lng")
                if lat is None:
                    continue
                if ch is not None:
                    precise[(base, ch)] = (lat, lng)
                town_pts.setdefault(base, []).append((lat, lng))
    except requests.RequestException:
        pass
    town_avg = {b: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v))
                for b, v in town_pts.items()}
    _geo_cache[key] = (precise, town_avg)
    return _geo_cache[key]


def _geocode(address):
    if not address:
        return None
    pm = _GEO_PREF_RE.match(address)
    if not pm:
        return None
    pref = pm.group(1)
    rest = address[len(pref):]
    cm = re.match(r"(.+?[市区町村])", rest)
    if not cm:
        return None
    city = cm.group(1)
    town_part = rest[len(city):].translate(_GEO_Z2H)
    precise, town_avg = _geo_index(pref, city)
    m = re.search(r"(\d+)\s*丁目", town_part)
    if m:
        base = town_part[:m.start()].strip()
        ch = int(m.group(1))
        if (base, ch) in precise:
            return precise[(base, ch)]
        if base in town_avg:
            return town_avg[base]
    m2 = re.search(r"\d", town_part)
    base = (town_part[:m2.start()] if m2 else town_part).strip()
    if base in town_avg:
        return town_avg[base]
    if town_avg:
        return next(iter(town_avg.values()))
    return None


@app.route('/api/geocode')
def api_geocode():
    """住所→緯度経度。idを渡すと座標(と空の住所)をDBへ保存する。"""
    address = request.args.get('address', '').strip()
    cid = request.args.get('id', '')
    if not address:
        return jsonify({'lat': None, 'lng': None})
    coord = _geocode(address)
    if coord and cid.isdigit():
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "UPDATE companies SET latitude=%s, longitude=%s, "
                    "address=IF(address IS NULL OR address='', %s, address) "
                    "WHERE id=%s AND latitude IS NULL",
                    (coord[0], coord[1], address, int(cid)))
        except mysql.connector.Error:
            pass
    return jsonify({'lat': coord[0] if coord else None,
                    'lng': coord[1] if coord else None})


# ===== エラーハンドラ =====
@app.errorhandler(DatabaseError)
def handle_database_error(_error):
    return jsonify({"error": "Database error occurred"}), 500


@app.errorhandler(ValidationError)
def handle_validation_error(e):
    return jsonify({"error": str(e)}), 400


@app.errorhandler(NotFoundError)
def handle_not_found_error(e):
    return jsonify({"error": str(e)}), 404


if __name__ == '__main__':
    app.run(debug=app_config.debug, host=app_config.host, port=app_config.port)
