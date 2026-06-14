"""edinetdb.jp から全業種の上場企業を取り込む（ITに限定しない）。

- 一覧 /v1/companies?per_page=5000 を使い、全上場企業（約4,400社）を
  数リクエストで取得（1リクエスト=1クォータ）。
- 一覧には住所・法人番号・売上が含まれないため、追加分は
  address='' / 座標NULL（地図ピンなし）で登録し、
  name・edinet_code・industry・credit_score を持たせる。
  詳細はクリック時に /api/edinet_detail（キャッシュ付き）で全情報取得。
- 既存DBに名前一致する社は listed/edinet_code/credit_score/industry をタグ付け。
"""

import os
import re
import sys
import requests

# リポジトリ直下のモジュール(config/db_utils/exceptions)を import するため
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import api_config
from db_utils import get_db_connection
from exceptions import logger

BASE = "https://edinetdb.jp/v1"
HEADERS = {"X-API-Key": api_config.edinet_api_key}
PER_PAGE = 5000

ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")


def norm_name(name):
    s = name or ""
    s = re.sub(r"(株式会社|有限会社|合同会社|（株）|\(株\)|㈱)", "", s)
    s = re.sub(r"[\s・,，.。\-－―ー]", "", s)
    return s.translate(ZEN2HAN).lower()


def ensure_columns(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=DATABASE() AND table_name='companies'")
        have = {r[0] for r in cur.fetchall()}
        for col, ddl in [
            ("listed", "ADD COLUMN listed TINYINT DEFAULT 0"),
            ("edinet_code", "ADD COLUMN edinet_code VARCHAR(12) DEFAULT NULL"),
            ("credit_score", "ADD COLUMN credit_score INT DEFAULT NULL"),
            ("industry", "ADD COLUMN industry VARCHAR(60) DEFAULT NULL"),
        ]:
            if col not in have:
                cur.execute(f"ALTER TABLE companies {ddl}")
    conn.commit()


def fetch_all_listed():
    items = []
    page = 1
    while True:
        r = requests.get(f"{BASE}/companies",
                         params={"per_page": PER_PAGE, "page": page}, headers=HEADERS, timeout=40)
        r.raise_for_status()
        body = r.json()
        batch = body.get("data") or []
        items.extend(batch)
        pg = (body.get("meta") or {}).get("pagination") or {}
        total_pages = pg.get("total_pages", 1)
        logger.info(f"page {page}/{total_pages}: {len(batch)} 社（累計 {len(items)}）"
                    f" 残{r.headers.get('X-Ratelimit-Remaining')}")
        if page >= total_pages or not batch:
            break
        page += 1
    return items


def run():
    conn = get_db_connection()
    if not conn:
        logger.error("DB接続失敗"); return
    try:
        ensure_columns(conn)
        items = fetch_all_listed()
        logger.info(f"上場企業 合計: {len(items)} 社")

        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, edinet_code FROM companies")
        by_norm, have_edinet = {}, set()
        for row in cur.fetchall():
            by_norm.setdefault(norm_name(row["name"]), row["id"])
            if row["edinet_code"]:
                have_edinet.add(row["edinet_code"])

        insert_sql = (
            "INSERT INTO companies "
            "(name, address, latitude, longitude, activity, listed, edinet_code, credit_score, industry) "
            "VALUES (%s, '', NULL, NULL, 0, 1, %s, %s, %s)"
        )
        tagged = added = 0
        for it in items:
            name = it.get("name_ja") or it.get("name")
            edinet = it.get("edinet_code")
            score = it.get("credit_score")
            industry = it.get("industry")
            if not name:
                continue
            if edinet and edinet in have_edinet:
                continue  # 既に取り込み済み
            cid = by_norm.get(norm_name(name))
            if cid:
                with conn.cursor() as c2:
                    c2.execute("UPDATE companies SET listed=1, edinet_code=%s, credit_score=%s, industry=%s WHERE id=%s",
                               (edinet, score, industry, cid))
                tagged += 1
            else:
                with conn.cursor() as c2:
                    c2.execute(insert_sql, (name[:255], edinet, score, industry))
                added += 1
            if edinet:
                have_edinet.add(edinet)
            if (tagged + added) % 500 == 0:
                conn.commit()
        conn.commit()

        with conn.cursor() as cur2:
            cur2.execute("SELECT COUNT(*) FROM companies")
            total = cur2.fetchone()[0]
            cur2.execute("SELECT COUNT(*) FROM companies WHERE listed=1")
            listed = cur2.fetchone()[0]
        logger.info(f"完了: 既存タグ付け {tagged} / 新規追加 {added} / DB総数 {total} / 上場 {listed}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
