"""既存companiesの座標を、住所の町丁目レベルで正確に付け直すスクリプト。

座標ソース: geolonia/japanese-addresses（町丁目ごとの緯度経度・無料）
  GET https://geolonia.github.io/japanese-addresses/api/ja/東京都/{市区町村}.json
  -> [{"town":"赤坂一丁目","lat":..,"lng":..}, ...]

gBizINFOの住所（例「東京都港区東新橋２丁目９番１号」）から市区町村＋町名＋丁目を
取り出し、町丁目→（無ければ町名平均→区中心）の順で座標を引く。
"""

import os
import re
import sys
import time
import random
import requests

# リポジトリ直下のモジュール(db_utils/exceptions)を import するため
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_utils import get_db_connection
from exceptions import logger

GEO_URL = "https://geolonia.github.io/japanese-addresses/api/ja/東京都/{}.json"

# 区中心（町名が引けなかった時のフォールバック）
WARD_CENTROIDS = {
    "千代田区": (35.6940, 139.7536), "中央区": (35.6707, 139.7720),
    "港区": (35.6581, 139.7516), "新宿区": (35.6938, 139.7036),
    "文京区": (35.7080, 139.7522), "台東区": (35.7126, 139.7800),
    "墨田区": (35.7107, 139.8015), "江東区": (35.6730, 139.8170),
    "品川区": (35.6092, 139.7302), "目黒区": (35.6415, 139.6982),
    "大田区": (35.5614, 139.7161), "世田谷区": (35.6464, 139.6531),
    "渋谷区": (35.6618, 139.7041), "中野区": (35.7074, 139.6638),
    "杉並区": (35.6995, 139.6365), "豊島区": (35.7289, 139.7100),
    "北区": (35.7528, 139.7336), "荒川区": (35.7361, 139.7833),
    "板橋区": (35.7512, 139.7090), "練馬区": (35.7357, 139.6517),
    "足立区": (35.7750, 139.8044), "葛飾区": (35.7434, 139.8472),
    "江戸川区": (35.7066, 139.8682),
}
DEFAULT_CENTROID = (35.6812, 139.7671)

KANJI_NUM = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")


def kanji_to_int(s):
    """『十』『二十一』程度までの簡易変換。"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        v = KANJI_NUM.get(ch)
        if v is None:
            return None
        if v == 10:
            cur = (cur or 1) * 10
            total += cur
            cur = 0
        else:
            cur = v
    return total + cur


def parse_city(address):
    m = re.search(r"(?:東京都)?(.+?[区市町村])", address)
    return m.group(1) if m else None


def parse_town(address, city):
    """市区町村より後ろから (町名base, 丁目番号 or None) を取り出す。"""
    rest = address.split(city, 1)[1] if city in address else address
    rest = rest.translate(ZEN2HAN)
    m = re.search(r"(\d+)\s*丁目", rest)
    if m:
        base = rest[: m.start()].strip()
        return base, int(m.group(1))
    # 丁目が無い場合は最初の数字より前を町名とみなす
    m2 = re.search(r"\d", rest)
    base = (rest[: m2.start()] if m2 else rest).strip()
    return base, None


def geolonia_town(town):
    """geoloniaの town（例『赤坂一丁目』）-> (base, 丁目番号 or None)。"""
    m = re.search(r"([一二三四五六七八九十]+)丁目$", town)
    if m:
        return town[: m.start()], kanji_to_int(m.group(1))
    return town, None


def build_index(city, cache):
    """市区町村の町丁目インデックスを取得（precise, town_avg）。"""
    if city in cache:
        return cache[city]
    precise, town_pts = {}, {}
    try:
        r = requests.get(GEO_URL.format(city), timeout=25)
        if r.status_code == 200:
            for t in r.json():
                base, ch = geolonia_town(t.get("town", ""))
                lat, lng = t.get("lat"), t.get("lng")
                if lat is None or lng is None:
                    continue
                if ch is not None:
                    precise[(base, ch)] = (lat, lng)
                town_pts.setdefault(base, []).append((lat, lng))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"geolonia取得失敗 {city}: {e}")
    town_avg = {b: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
                for b, pts in town_pts.items()}
    cache[city] = (precise, town_avg)
    return cache[city]


def jitter(lat, lng, amt=0.0006):
    return round(lat + random.uniform(-amt, amt), 6), round(lng + random.uniform(-amt, amt), 6)


def refine():
    conn = get_db_connection()
    if not conn:
        logger.error("DB接続失敗")
        return
    cache = {}
    stats = {"precise": 0, "town": 0, "ward": 0, "default": 0}
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, address FROM companies")
        rows = cur.fetchall()
        logger.info(f"対象 {len(rows)} 件を再ジオコーディング")

        updates = []
        for row in rows:
            addr = row["address"] or ""
            city = parse_city(addr)
            coord = None
            if city:
                precise, town_avg = build_index(city, cache)
                base, ch = parse_town(addr, city)
                if ch is not None and (base, ch) in precise:
                    coord = jitter(*precise[(base, ch)]); stats["precise"] += 1
                elif base in town_avg:
                    coord = jitter(*town_avg[base]); stats["town"] += 1
                elif city in WARD_CENTROIDS:
                    coord = jitter(*WARD_CENTROIDS[city], amt=0.006); stats["ward"] += 1
            if coord is None:
                coord = jitter(*DEFAULT_CENTROID, amt=0.006); stats["default"] += 1
            updates.append((coord[0], coord[1], row["id"]))

        with conn.cursor() as c2:
            c2.executemany("UPDATE companies SET latitude=%s, longitude=%s WHERE id=%s", updates)
        conn.commit()
        logger.info(f"完了: {len(updates)} 件更新 / 内訳={stats}")
    finally:
        conn.close()


if __name__ == "__main__":
    refine()
