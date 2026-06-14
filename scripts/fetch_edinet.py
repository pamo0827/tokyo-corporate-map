"""edinetdb.jp API で上場IT企業の情報と売上高を取り込む。

制約: 無料プランは 100リクエスト/日。そのため
  1) 一覧取得は industry=information-communication を per_page=5000 で「1リクエスト」だけ。
     -> 全上場IT企業（約616社）の name/sec_code/edinet_code/credit_score を取得。
        既存DBに名前一致した社へ listed/edinet_code/credit_score をタグ付け。
  2) 売上は 1社=1リクエスト なので、知名度(activity)の高い順に、
     当日の残回数の範囲で少しずつ取得して sales 列にキャッシュ（再実行で続きから）。

売上フィールド: GET /v1/companies/{edinet_code} -> latest_financials.revenue（円）
"""

import os
import re
import sys
import time
import requests

# リポジトリ直下のモジュール(config/db_utils/exceptions)を import するため
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import api_config
from db_utils import get_db_connection
from exceptions import logger

BASE = "https://edinetdb.jp/v1"
HEADERS = {"X-API-Key": api_config.edinet_api_key}

DAILY_SALES_BUDGET = 90     # 当日に売上取得する最大社数（100/日の上限内で余裕を持たせる）
STOP_WHEN_REMAINING = 5     # 残回数がこれ未満になったら停止

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
            ("sales", "ADD COLUMN sales BIGINT DEFAULT NULL"),
            ("sales_fy", "ADD COLUMN sales_fy INT DEFAULT NULL"),
        ]:
            if col not in have:
                cur.execute(f"ALTER TABLE companies {ddl}")
    conn.commit()


def tag_listed(conn):
    """上場IT企業一覧を1リクエストで取得し、既存DBへタグ付け。"""
    r = requests.get(f"{BASE}/companies",
                     params={"industry": "information-communication", "per_page": 5000},
                     headers=HEADERS, timeout=40)
    r.raise_for_status()
    items = r.json().get("data") or []
    logger.info(f"上場IT企業 一覧: {len(items)} 社 取得（残 {r.headers.get('X-Ratelimit-Remaining')}）")

    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name FROM companies")
    db_by_norm = {}
    for row in cur.fetchall():
        db_by_norm.setdefault(norm_name(row["name"]), row["id"])

    tagged = 0
    for it in items:
        edinet = it.get("edinet_code")
        score = it.get("credit_score")
        cid = db_by_norm.get(norm_name(it.get("name_ja") or it.get("name")))
        if cid:
            with conn.cursor() as c2:
                c2.execute("UPDATE companies SET listed=1, edinet_code=%s, credit_score=%s WHERE id=%s",
                           (edinet, score, cid))
            tagged += 1
    conn.commit()
    logger.info(f"既存DBにタグ付け: {tagged} 社（listed/edinet_code/credit_score）")


def fetch_sales(conn):
    """edinet_codeを持ち売上未取得の社を、知名度順に当日上限まで取得。"""
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name, edinet_code FROM companies "
                "WHERE edinet_code IS NOT NULL AND sales IS NULL "
                "ORDER BY activity DESC, credit_score DESC LIMIT %s", (DAILY_SALES_BUDGET,))
    targets = cur.fetchall()
    logger.info(f"売上取得対象: {len(targets)} 社")

    done = 0
    for t in targets:
        try:
            r = requests.get(f"{BASE}/companies/{t['edinet_code']}",
                             params={"fields": "latest_financials"}, headers=HEADERS, timeout=30)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"取得失敗 {t['name']}: {e}")
            continue
        remaining = r.headers.get("X-Ratelimit-Remaining")
        if r.status_code != 200:
            logger.warning(f"{t['name']} -> status {r.status_code}（残 {remaining}）")
            if r.status_code == 429:
                break
            continue
        data = r.json().get("data", {})
        fin = (data or {}).get("latest_financials") or {}
        rev = fin.get("revenue")
        fy = fin.get("fiscal_year")
        if rev is not None:
            with conn.cursor() as c2:
                c2.execute("UPDATE companies SET sales=%s, sales_fy=%s WHERE id=%s",
                           (int(rev), fy, t["id"]))
            done += 1
        if done % 20 == 0:
            conn.commit()
        if remaining is not None and remaining.isdigit() and int(remaining) < STOP_WHEN_REMAINING:
            logger.info(f"残回数 {remaining} のため停止")
            break
    conn.commit()
    logger.info(f"売上取得 完了: {done} 社更新")


def run():
    conn = get_db_connection()
    if not conn:
        logger.error("DB接続失敗"); return
    try:
        ensure_columns(conn)
        tag_listed(conn)
        fetch_sales(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM companies WHERE listed=1")
            listed = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM companies WHERE sales IS NOT NULL")
            withsales = cur.fetchone()[0]
        logger.info(f"現状: 上場タグ {listed} 社 / 売上あり {withsales} 社")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
