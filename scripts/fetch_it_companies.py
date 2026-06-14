"""gBizINFO API から東京都内の実在IT企業を収集してDBへ投入するスクリプト。

- 情報源: gBizINFO（経済産業省の法人情報API / 正規）
- 規模/知名度: 各法人の number_of_activity（政府調達・補助金・表彰などの
        活動件数）を「知名度・規模の代理指標」として採用。広く集めた
        プールをこの値で降順に並べ、上位 TARGET 件を採用する。
        （ソフトバンク/NTTデータ/NECソリューションイノベータ等が上位に来る）
- 座標: gBizINFOは緯度経度を返さないため、住所中の区・市から
        その中心座標＋微小なランダムずらしを付与する。
"""

import os
import sys
import time
import random
import requests

# リポジトリ直下のモジュール(config/db_utils/exceptions)を import するため
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import api_config
from db_utils import get_db_connection, create_database_and_tables
from exceptions import logger

API_URL = "https://info.gbiz.go.jp/hojin/v1/hojin"
HEADERS = {"X-hojinInfo-api-token": api_config.gbiz_token, "Accept": "application/json"}

TARGET = 5000
PAGE_LIMIT = 5000

# IT関連企業を拾うための検索キーワード（社名に含まれる語）
IT_KEYWORDS = [
    "システム", "ソフト", "テクノロジー", "ソリューション", "データ",
    "デジタル", "ネット", "テック", "コンピュータ", "インフォメーション",
    "情報", "通信", "サイバー", "クラウド", "アプリ",
]

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
    "八王子市": (35.6664, 139.3160), "立川市": (35.7138, 139.4079),
    "武蔵野市": (35.7178, 139.5662), "三鷹市": (35.6835, 139.5596),
    "府中市": (35.6689, 139.4777), "調布市": (35.6516, 139.5410),
    "町田市": (35.5460, 139.4386), "小金井市": (35.6994, 139.5031),
    "日野市": (35.6712, 139.3949), "西東京市": (35.7256, 139.5386),
    "多摩市": (35.6369, 139.4463), "稲城市": (35.6378, 139.5046),
    "国分寺市": (35.7100, 139.4623), "国立市": (35.6838, 139.4413),
    "小平市": (35.7284, 139.4774), "東村山市": (35.7547, 139.4686),
    "狛江市": (35.6347, 139.5786), "東久留米市": (35.7581, 139.5294),
    "清瀬市": (35.7857, 139.5263), "あきる野市": (35.7287, 139.2940),
    "青梅市": (35.7880, 139.2756), "武蔵村山市": (35.7549, 139.3874),
    "昭島市": (35.7058, 139.3539), "福生市": (35.7387, 139.3266),
    "羽村市": (35.7672, 139.3110),
}
DEFAULT_CENTROID = (35.6812, 139.7671)  # 東京駅


def extract_area(address):
    if not address:
        return None
    body = address.replace("東京都", "")
    for sep in ("区", "市", "町", "村"):
        idx = body.find(sep)
        if idx != -1:
            return body[: idx + 1]
    return None


def coords_for(address):
    base = WARD_CENTROIDS.get(extract_area(address), DEFAULT_CENTROID)
    lat = base[0] + random.uniform(-0.012, 0.012)
    lng = base[1] + random.uniform(-0.015, 0.015)
    return round(lat, 6), round(lng, 6)


def call_api(params, tries=6):
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(API_URL, headers=HEADERS, params=params, timeout=25)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:  # ヒット0件
                return {"hojin-infos": []}
            last_err = f"status {r.status_code}: {r.text[:200]}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"API call failed after {tries} tries: {last_err}")


def ensure_activity_column(conn):
    """companies テーブルに activity 列が無ければ追加する。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name='companies' "
            "AND column_name='activity'"
        )
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE companies ADD COLUMN activity INT DEFAULT 0")
    conn.commit()


def fetch_and_store():
    create_database_and_tables()
    conn = get_db_connection()
    if not conn:
        logger.error("DB接続に失敗しました")
        return

    try:
        ensure_activity_column(conn)

        # 1) IT企業プールを収集（社名キーワード × 東京都）
        pool = {}  # corporate_number -> dict
        for kw in IT_KEYWORDS:
            logger.info(f"keyword='{kw}' 収集中... (pool={len(pool)})")
            data = call_api({"name": kw, "prefecture": "13", "limit": str(PAGE_LIMIT), "page": "1"})
            for info in data.get("hojin-infos") or []:
                cn = info.get("corporate_number")
                name = info.get("name")
                address = info.get("location")
                if not cn or not name or not address:
                    continue
                if info.get("status") == "閉鎖":
                    continue
                act = int(info.get("number_of_activity") or 0)
                cur = pool.get(cn)
                if cur is None or act > cur["activity"]:
                    pool[cn] = {"name": name, "address": address, "activity": act, "cn": cn}
            time.sleep(0.6)

        logger.info(f"プール件数: {len(pool)}")

        # 2) 知名度（activity）で降順 → 上位 TARGET 件を採用
        ranked = sorted(pool.values(), key=lambda x: x["activity"], reverse=True)[:TARGET]
        logger.info(f"採用 {len(ranked)} 件 (activity>0 は {sum(1 for r in ranked if r['activity']>0)} 件)")

        # 3) 投入
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE companies")
        conn.commit()

        insert_sql = (
            "INSERT IGNORE INTO companies "
            "(name, address, latitude, longitude, corporate_number, activity) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        rows = []
        for r in ranked:
            lat, lng = coords_for(r["address"])
            rows.append((r["name"][:255], r["address"][:255], lat, lng, r["cn"], r["activity"]))

        with conn.cursor() as cur:
            cur.executemany(insert_sql, rows)
        conn.commit()
        logger.info(f"完了: {len(rows)} 件を投入しました")
    finally:
        conn.close()


if __name__ == "__main__":
    fetch_and_store()
