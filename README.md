# 東京企業マップシステム (Tokyo Corporate Map System)

![企業情報マップ](https://img.shields.io/badge/Status-Production%20Ready-green.svg)
![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-orange.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue.svg)
![Mobile](https://img.shields.io/badge/Mobile-Responsive-purple.svg)
![Tokyo](https://img.shields.io/badge/Area-Tokyo%20Only-red.svg)

</div>

## 📋 目次

- [概要](#概要)
- [主な機能](#主な機能)
- [技術スタック](#技術スタック)
- [セットアップ](#セットアップ)
- [使用方法](#使用方法)
- [API仕様](#api仕様)
- [ディレクトリ構成](#ディレクトリ構成)

## 🎯 概要

東京企業マップシステムは、**東京都内限定**の企業情報を地図上で視覚的に表示し、検索・お気に入り登録・新規企業登録ができるWebアプリケーションです。皇居を中心とした高精度な地図表示と最寄駅情報により、東京都内の企業探索を効率化します。

### 🌟 主要な特徴

- **皇居中心の地図表示**: 東京都の中心である皇居を基点とした詳細地図
- **東京都限定**: 地図表示・企業登録を東京都内のみに制限
- **最寄駅情報**: 25の主要駅からの徒歩時間とルート表示
- **高度な検索機能**: 企業名・住所・市区町村での曖昧検索（類似度70%以上）
- **スマートレコメンデーション**: 常時3件のランダムおすすめ企業表示
- **レスポンシブデザイン**: PC・タブレット・スマートフォン完全対応
- **リアルタイム登録**: GeoCoding APIによる正確な座標取得
- **UI切り替え**: 検索バー・お気に入りサイドバーの表示/非表示

## ✨ 主な機能

###  地図機能
- **東京都境界制限**: 地図移動を東京都内に制限（maxBounds設定）
- **企業マーカー表示**: 東京都内の全企業をピンポイント表示
- **カスタムアイコン**: お気に入り企業は赤色、通常企業は青色、駅は緑色
- **ポップアップ情報**: 企業名・住所・お気に入り登録ボタン
- **ズーム・パン操作**: マウス・タッチでスムーズな地図操作

###  最寄駅・ルート機能
- **25主要駅データ**: 新宿、渋谷、池袋、東京駅など東京の主要駅を網羅
- **徒歩時間計算**: 平均歩行速度4km/hで正確な徒歩時間を算出
- **ルート表示**: 企業から最寄駅までの破線ルートを地図上に表示
- **駅情報パネル**: 左下に駅名・徒歩時間・利用路線を表示
- **ルート切り替え**: ワンクリックでルート表示/非表示

###  検索・発見機能
- **東京都限定検索**: 企業名・住所・市区町村での部分一致検索（東京都内のみ）
- **曖昧検索**: fuzzywuzzyライブラリによる柔軟な類似度マッチング（70%以上）
- **おすすめ企業**: 検索結果に関係なく常時3件のランダム企業を表示
- **セクション分け**: 「検索結果」と「おすすめ企業」を視覚的に区別
- **表示切替**: 検索バーの表示/非表示切り替えボタン

###  お気に入り機能
- **サイドバー管理**: 左側スライドパネルでお気に入り企業を一覧表示
- **ワンクリック登録**: 企業ポップアップから簡単お気に入り登録・解除
- **LocalStorage**: ブラウザ内でお気に入り情報を永続化
- **クイックアクセス**: お気に入りリストから直接地図ジャンプ

###  企業登録機能
- **フォーム入力**: 企業名・住所（東京都内のみ）・法人番号（任意）
- **GeoCoding API**: OpenStreetMap Nominatim APIで住所から座標を取得
- **東京都内制限**: 座標が東京都外の場合は登録拒否
- **フォールバック機能**: API失敗時は主要エリア座標で推定
- **即座反映**: 登録完了と同時に地図・検索結果に反映
- **重複チェック**: 同名企業の重複登録を防止

###  モバイル対応
- **レスポンシブレイアウト**: 768px/480px ブレークポイント
- **タッチ最適化**: ボタンサイズ・操作性の最適化
- **画面回転対応**: 縦向き・横向き両対応
- **フォント調整**: iOSズーム防止のための16pxフォント
- **モバイル専用UI**: 検索バー・サイドバーの最適化

## 🛠️ 技術スタック

### バックエンド
- **Python 3.9+**: メイン開発言語
- **Flask 2.0+**: 軽量Webフレームワーク
- **MySQL 8.0+**: リレーショナルデータベース
- **fuzzywuzzy**: 曖昧文字列マッチングライブラリ
- **requests**: HTTP APIクライアント（GeoCoding用）

### フロントエンド
- **HTML5/CSS3**: モダンなマークアップ・スタイリング
- **JavaScript (ES6+)**: フロントエンド機能実装
- **Leaflet.js 1.9+**: オープンソース地図ライブラリ
- **OpenStreetMap**: 地図タイルデータソース

### API統合
- **OpenStreetMap Nominatim**: 住所ジオコーディングAPI
- **駅情報API**: 東京25主要駅の座標・路線データ統合

### データベース設計
```sql
CREATE TABLE companies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    corporate_number VARCHAR(20) UNIQUE
);
```

## 🚀 セットアップ

### 必要な環境
- Python 3.9以上
- MySQL 8.0以上
- pip (Python パッケージマネージャー)

### 1. リポジトリのクローン
```bash
git clone "https://github.com/pamo0827/tokyo-corporate-map"
```

### 2. 仮想環境の作成・有効化
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows
```

### 3. 依存関係のインストール
```bash
pip install -r requirements.txt
# または個別インストール
pip install flask mysql-connector-python fuzzywuzzy python-levenshtein requests
```

### 4. 環境変数の設定
`.env`ファイルを作成し、以下を設定：
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=dbs_final
FLASK_DEBUG=True
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
SEARCH_SIMILARITY_THRESHOLD=70
```

### 5. データベースのセットアップ
```bash
# MySQLサーバーを起動
mysql -u root -p

# データベースとテーブルの作成、サンプルデータの挿入
python3 fetch_gbiz_data.py
```

### 6. アプリケーションの起動
```bash
python3 app.py
```

アプリケーションは `http://127.0.0.1:5000` でアクセス可能です。

## 📖 使用方法

### 基本操作
1. ** 企業検索**: 右上の「検索」ボタンで検索バーを表示し、企業名・住所・市区町村を入力
2. ** 地図操作**: マウスドラッグで移動、ホイールでズーム（東京都内限定）
3. ** 企業詳細**: マーカーをクリックしてポップアップ表示
4. ** お気に入り**: ポップアップのボタンでお気に入り登録・解除
5. ** 最寄駅情報**: 企業選択時に左下に駅情報パネルが表示

### 新規企業登録
1. 右上の「検索」ボタンで検索バーを表示
2. 検索バー下の「新しい企業を登録」をクリック
3. 企業名・住所（東京都内のみ）を入力（法人番号は任意）
4. 「登録」ボタンで完了（GeoCoding APIで座標自動取得）

### お気に入り管理
1. 左上の「お気に入り」ボタンでサイドバー表示
2. リスト項目をクリックで該当企業にジャンプ
3. サイドバー外クリックまたは地図クリックで閉じる

### 最寄駅・ルート機能
1. 企業マーカーをクリックして企業を選択
2. 左下の駅情報パネルで最寄駅・徒歩時間を確認
3. 「ルート表示/非表示」ボタンで駅までのルートを表示

### モバイル利用
- **👆 タッチ操作**: タップ・ピンチで地図操作
- **📱 レスポンシブUI**: 検索バー・サイドバーが画面サイズに最適化
- **🔤 フォーム入力**: 16pxフォントでズーム防止

## 🔌 API仕様

### GET /api/companies
全企業データを取得
```json
[
  {
    "id": 1,
    "name": "株式会社サンプル",
    "address": "東京都渋谷区",
    "latitude": 35.6895,
    "longitude": 139.6917
  }
]
```

### GET /search_companies?query={search_term}
企業検索（クエリが空の場合はおすすめ企業のみ）
```json
{
  "results": [
    {
      "id": 1,
      "name": "株式会社サンプル",
      "address": "東京都渋谷区",
      "latitude": 35.6895,
      "longitude": 139.6917,
      "is_random": false
    }
  ],
  "search_count": 1,
  "random_count": 3
}
```

### POST /register_company
新規企業登録（東京都内限定・GeoCoding API使用）
```json
// Request
{
  "name": "新規企業株式会社",
  "address": "東京都新宿区神南1-1-1",
  "corporate_number": "1234567890123"
}

// Response（成功時）
{
  "success": true,
  "message": "Company registered successfully",
  "company": {
    "id": 234,
    "name": "新規企業株式会社",
    "address": "東京都新宿区神南1-1-1",
    "latitude": 35.6935,
    "longitude": 139.7034,
    "station_info": {
      "station": {
        "name": "渋谷駅",
        "lat": 35.6580,
        "lng": 139.7016,
        "lines": ["JR山手線", "東急東横線"]
      },
      "distance_km": 0.8,
      "walk_time_minutes": 12
    }
  }
}

// Response（東京都外エラー時）
{
  "success": false,
  "error": "東京都内の住所のみ登録可能です"
}
```

## 📁 ディレクトリ構成

```
dbs_final/
├── README.md              # プロジェクト説明書（更新済み）
├── requirements.txt       # Python依存関係
├── app.py                 # Flaskメインアプリケーション（GeoCoding API統合）
├── config.py              # 設定ファイル
├── db_utils.py            # データベースユーティリティ
├── exceptions.py          # カスタム例外クラス
├── fetch_gbiz_data.py     # サンプルデータ作成スクリプト
├── static/
│   └── js/
│       └── main.js        # フロントエンドJavaScript（最寄駅・UI切替機能）
├── templates/
│   └── index.html         # メインHTMLテンプレート（東京都限定UI）
└── venv/                  # Python仮想環境
```
