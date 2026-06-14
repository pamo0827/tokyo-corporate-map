# 企業情報マップ (Corporate Map)

全国の企業を一覧・検索・地図表示し、各社の詳細情報（EDINET / gBizINFO）を閲覧できる Web アプリケーションです。約13,000社（gBizINFO の活動実績上位企業＋全業種の上場・著名企業）を収録しています。

## 目次

- [概要](#概要)
- [主な機能](#主な機能)
- [技術スタック](#技術スタック)
- [データソース](#データソース)
- [セットアップ](#セットアップ)
- [起動方法](#起動方法)
- [データ生成スクリプト](#データ生成スクリプト)
- [API仕様](#api仕様)
- [ディレクトリ構成](#ディレクトリ構成)
- [デプロイについて](#デプロイについて)
- [補足・制約](#補足制約)

## 概要

左ペインに企業一覧（社名の五十音「あかさたな」で折りたたみ分類）、右ペインに地図または詳細を表示する2ペイン構成です。企業を選ぶと、その地点に地図ピンを立て、右ペインの詳細タブで EDINET と gBizINFO の取得可能な全項目を日本語ラベルで表示します。

## 主な機能

- 企業一覧: 社名の五十音で分類した折りたたみ表示。初期は全セクション閉じた状態。
- 検索: 左上の検索バーで企業名・住所を即時絞り込み。
- 地図: 初期はピンなし。企業を選択したときだけ、その企業のピンを表示。
  - 座標を持たない企業は、選択時に住所（または EDINET の本社所在地）から町丁目レベルでジオコーディングしてピンを付与し、結果を DB に保存（次回以降は即表示）。
- 詳細パネル: 地図／詳細をタブで切替（初期は詳細）。EDINET と gBizINFO の全フィールドを日本語項目名で表示。
- 分割比率: 一覧と地図の境界をドラッグして自由にリサイズ（初期は一覧4：地図6）。
- レスポンシブ: スマートフォンでは上下分割。

## 技術スタック

- バックエンド: Python / Flask
- データベース: MySQL
- フロントエンド: 素の HTML / CSS / JavaScript、地図は Leaflet（OpenStreetMap タイル）
- 外部API: gBizINFO（経済産業省）/ edinetdb.jp（EDINET 由来の上場企業財務）/ geolonia japanese-addresses（住所→緯度経度）

## データソース

- gBizINFO: 法人名・所在地・代表者・従業員数・事業概要・活動実績など。
- edinetdb.jp: 上場企業の財務（売上高・各利益・BS/PL/CF）、信用スコア、配当、従業員指標など。無料プランは 100リクエスト/日。
- geolonia/japanese-addresses: 町丁目レベルの緯度経度（無料・全国）。

## セットアップ

前提: Python 3.9+ / MySQL 8.0+

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 秘匿情報の設定

API キーはリポジトリに含めていません。`secrets_local.py`（`.gitignore` 済み）を作成するか、環境変数で設定します。

`secrets_local.py` の例:

```python
GBIZ_API_TOKEN = "your_gbiz_token"
EDINET_API_KEY = "your_edinetdb_key"
```

環境変数の例:

```bash
export GBIZ_API_TOKEN=your_gbiz_token
export EDINET_API_KEY=your_edinetdb_key
```

### データベース

`config.py` の `DatabaseConfig`（環境変数 `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`）で接続先を設定します。テーブルは `db_utils.create_database_and_tables()` および各データ生成スクリプトが自動作成します。

## 起動方法

```bash
# 例: ポート5001で起動（macOSの5000はAirPlayが使用するため）
FLASK_PORT=5001 venv/bin/python app.py
```

ブラウザで `http://127.0.0.1:5001` を開きます。

設定可能な環境変数: `FLASK_HOST` / `FLASK_PORT` / `FLASK_DEBUG` / `API_TIMEOUT`。

## データ生成スクリプト

データ投入・更新は `scripts/` 配下のスクリプトで行います（アプリ本体からは使用しません）。リポジトリ直下から実行します。

```bash
venv/bin/python scripts/fetch_it_companies.py   # gBizINFOの活動実績上位でIT企業を投入
venv/bin/python scripts/fetch_listed_all.py     # 全業種の上場企業を追加
venv/bin/python scripts/fetch_famous_all.py     # 全業種の著名・大規模企業を追加
venv/bin/python scripts/fetch_edinet.py         # EDINETの売上・信用スコアを取得（日次上限内・再実行で続き）
venv/bin/python scripts/geocode_refine.py       # 住所を町丁目レベルでジオコーディング
```

`fetch_edinet.py` は 100リクエスト/日の上限内で知名度順に少しずつ取得し、結果をキャッシュします。日をまたいで再実行すると続きから取得します。

## API仕様

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/` | アプリ画面 |
| GET | `/api/companies` | DB の全企業を返す |
| GET | `/api/company_detail?corporate_number=` | gBizINFO の法人詳細（サーバー経由でトークン秘匿） |
| GET | `/api/edinet_detail?code=` | edinetdb.jp の企業詳細（全フィールド、DBキャッシュ付き）。`refresh=1` で再取得 |
| GET | `/api/geocode?address=&id=` | 住所→緯度経度。`id` を渡すと座標を DB に保存 |

## ディレクトリ構成

```
.
├── app.py              Flask アプリ本体
├── config.py           設定（DB・API・アプリ）
├── db_utils.py         DB接続・テーブル作成
├── exceptions.py       例外とロガー
├── requirements.txt
├── secrets_local.py    APIキー（gitignore・各自作成）
├── templates/
│   └── index.html      画面（HTML/CSS）
├── static/js/
│   └── main.js         フロントエンドロジック
└── scripts/            データ生成・更新スクリプト
    ├── fetch_it_companies.py
    ├── fetch_listed_all.py
    ├── fetch_famous_all.py
    ├── fetch_edinet.py
    └── geocode_refine.py
```

## デプロイについて

本アプリは静的ページ（GitHub Pages 等）としてはそのままデプロイできません。理由:

- MySQL からデータを返す API が必要。
- gBizINFO / EDINET / ジオコーディングへのアクセスは、APIキーを秘匿するためサーバー側でプロキシしている。
- ブラウザから外部APIを直接叩くと、キー露出と CORS の問題が発生する。

デプロイする場合は、Flask が動くサーバー（Render / Railway / Fly.io / VPS など）と MySQL を用意してください。どうしても静的化する場合は、企業一覧を静的 JSON に書き出し、詳細・ジオコーディングなどサーバー依存機能を外す（または別途 API を用意する）必要があります。

## 補足・制約

- edinetdb.jp は 100リクエスト/日。詳細はキャッシュされ、同じ企業の再表示はリクエストを消費しません。検索系はキー不要のため消費しません。
- 座標は町丁目レベルの近似（番地までは特定しません）。
- 読み仮名データを持たないため、五十音分類は社名先頭が漢字の場合「漢字・その他」にまとめます（カタカナ・ひらがな始まりは正しく分類）。
- APIキーはコミットしないでください（`secrets_local.py` は `.gitignore` 済み）。
