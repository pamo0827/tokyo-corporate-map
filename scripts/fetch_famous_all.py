"""gBizINFO から全業種の有名・大規模企業を活動数(number_of_activity)上位で追加する。

- 業種を問わない幅広いキーワードで収集し、活動数で上位 TARGET 件を採用。
- 既存と重複(法人番号)はスキップ。
- 社名が既存の上場企業行（edinetdb由来・住所/法人番号なし）と一致する場合は、
  その行に法人番号・住所・座標を補完（enrich）。
- それ以外は新規追加。住所は geolonia で全国対応のジオコーディング（失敗時 座標NULL）。
"""

import os
import re
import sys
import time
import random
import requests

# リポジトリ直下のモジュール(config/db_utils/exceptions)を import するため
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import api_config
from db_utils import get_db_connection
from exceptions import logger

GBIZ_URL = "https://info.gbiz.go.jp/hojin/v1/hojin"
GBIZ_HEADERS = {"X-hojinInfo-api-token": api_config.gbiz_token, "Accept": "application/json"}
GEO_URL = "https://geolonia.github.io/japanese-addresses/api/ja/{}/{}.json"

TARGET = 5000
PAGE_LIMIT = 5000

# 全業種の大企業を拾う幅広いキーワード（社名に含まれる語）
KEYWORDS = [
    "工業", "製作所", "商事", "産業", "製造", "建設", "製薬", "薬品", "食品",
    "銀行", "電機", "電気", "自動車", "化学", "重工", "海運", "不動産", "物産",
    "倉庫", "ホールディングス", "製鉄", "鉄鋼", "硝子", "セメント", "製紙",
    "印刷", "運輸", "保険", "証券", "電力", "ガス", "繊維", "機械", "金属",
    "精機", "飲料", "商会", "興業", "製鋼", "鉄道", "百貨店", "石油",
]

PREF_RE = re.compile(r"^(.+?[都道府県])")
KANJI_NUM = {"〇":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")
_geo_cache = {}


def norm_name(name):
    s = name or ""
    s = re.sub(r"(株式会社|有限会社|合同会社|（株）|\(株\)|㈱)", "", s)
    s = re.sub(r"[\s・,，.。\-－―ー]", "", s)
    return s.translate(ZEN2HAN).lower()


def kanji_to_int(s):
    if not s: return None
    if s.isdigit(): return int(s)
    total = cur = 0
    for ch in s:
        v = KANJI_NUM.get(ch)
        if v is None: return None
        if v == 10: cur = (cur or 1) * 10; total += cur; cur = 0
        else: cur = v
    return total + cur


def geo_index(pref, city):
    key = (pref, city)
    if key in _geo_cache:
        return _geo_cache[key]
    precise, town_pts = {}, {}
    try:
        r = requests.get(GEO_URL.format(pref, city), timeout=25)
        if r.status_code == 200:
            for t in r.json():
                town = t.get("town", "")
                m = re.search(r"([一二三四五六七八九十]+)丁目$", town)
                base = town[:m.start()] if m else town
                ch = kanji_to_int(m.group(1)) if m else None
                lat, lng = t.get("lat"), t.get("lng")
                if lat is None: continue
                if ch is not None: precise[(base, ch)] = (lat, lng)
                town_pts.setdefault(base, []).append((lat, lng))
    except Exception:  # noqa: BLE001
        pass
    town_avg = {b: (sum(p[0] for p in v)/len(v), sum(p[1] for p in v)/len(v)) for b, v in town_pts.items()}
    _geo_cache[key] = (precise, town_avg)
    return _geo_cache[key]


def geocode(address):
    if not address: return None
    pm = PREF_RE.match(address)
    if not pm: return None
    pref = pm.group(1); rest = address[len(pref):]
    cm = re.match(r"(.+?[市区町村])", rest)
    if not cm: return None
    city = cm.group(1); town_part = rest[len(city):].translate(ZEN2HAN)
    precise, town_avg = geo_index(pref, city)
    m = re.search(r"(\d+)\s*丁目", town_part)
    if m:
        base = town_part[:m.start()].strip(); ch = int(m.group(1))
        if (base, ch) in precise: return _jit(precise[(base, ch)])
        if base in town_avg: return _jit(town_avg[base])
    m2 = re.search(r"\d", town_part)
    base = (town_part[:m2.start()] if m2 else town_part).strip()
    if base in town_avg: return _jit(town_avg[base])
    if town_avg: return _jit(next(iter(town_avg.values())))
    return None


def _jit(c):
    return (round(c[0] + random.uniform(-0.0008, 0.0008), 6),
            round(c[1] + random.uniform(-0.0008, 0.0008), 6))


def call_api(params, tries=6):
    last = None
    for i in range(tries):
        try:
            r = requests.get(GBIZ_URL, headers=GBIZ_HEADERS, params=params, timeout=25)
            if r.status_code == 200: return r.json()
            if r.status_code == 404: return {"hojin-infos": []}
            last = r.status_code
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"gBiz API failed: {last}")


def run():
    conn = get_db_connection()
    if not conn:
        logger.error("DB接続失敗"); return
    try:
        # 1) プール収集（全国・全業種キーワード）
        pool = {}
        for kw in KEYWORDS:
            data = call_api({"name": kw, "limit": str(PAGE_LIMIT), "page": "1"})
            for info in data.get("hojin-infos") or []:
                cn = info.get("corporate_number")
                name = info.get("name")
                addr = info.get("location")
                if not cn or not name or info.get("status") == "閉鎖":
                    continue
                act = int(info.get("number_of_activity") or 0)
                cur = pool.get(cn)
                if cur is None or act > cur["activity"]:
                    pool[cn] = {"cn": cn, "name": name, "address": addr or "", "activity": act}
            logger.info(f"kw='{kw}' 収集 (pool={len(pool)})")
            time.sleep(0.5)

        ranked = sorted(pool.values(), key=lambda x: x["activity"], reverse=True)[:TARGET]
        logger.info(f"プール {len(pool)} → 採用 {len(ranked)} 件")

        # 2) 既存情報
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, corporate_number FROM companies")
        existing_cn = set()
        enrichable = {}   # 法人番号なし行（上場edinet由来）を社名で補完できるように
        for row in cur.fetchall():
            if row["corporate_number"]:
                existing_cn.add(row["corporate_number"])
            else:
                enrichable.setdefault(norm_name(row["name"]), row["id"])

        ins_sql = ("INSERT INTO companies (name, address, latitude, longitude, "
                   "corporate_number, activity, listed) VALUES (%s,%s,%s,%s,%s,%s,0)")
        added = enriched = skipped = 0
        for r in ranked:
            if r["cn"] in existing_cn:
                skipped += 1
                continue
            coord = geocode(r["address"])
            lat = coord[0] if coord else None
            lng = coord[1] if coord else None
            hit = enrichable.get(norm_name(r["name"]))
            if hit:
                with conn.cursor() as c2:
                    c2.execute("UPDATE companies SET corporate_number=%s, address=%s, "
                               "latitude=%s, longitude=%s, activity=%s WHERE id=%s",
                               (r["cn"], r["address"][:255], lat, lng, r["activity"], hit))
                del enrichable[norm_name(r["name"])]
                enriched += 1
            else:
                with conn.cursor() as c2:
                    c2.execute(ins_sql, (r["name"][:255], r["address"][:255], lat, lng,
                                         r["cn"], r["activity"]))
                added += 1
            existing_cn.add(r["cn"])
            if (added + enriched) % 300 == 0:
                conn.commit()
        conn.commit()

        with conn.cursor() as c3:
            c3.execute("SELECT COUNT(*) FROM companies")
            total = c3.fetchone()[0]
        logger.info(f"完了: 新規 {added} / 上場補完 {enriched} / 重複skip {skipped} / DB総数 {total}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
