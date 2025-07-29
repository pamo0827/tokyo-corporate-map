from flask import Flask, render_template, jsonify, request
import mysql.connector
from fuzzywuzzy import fuzz
from db_utils import get_db_cursor
from exceptions import DatabaseError, ValidationError, NotFoundError
from config import app_config, search_config
import requests
import json
import random

app = Flask(__name__)

# 東京都の境界定義
TOKYO_BOUNDS = {
    'north': 35.9,
    'south': 35.5,  
    'east': 139.9,
    'west': 139.4
}

def is_within_tokyo(lat, lng):
    """指定された座標が東京都内かどうかチェック"""
    return (TOKYO_BOUNDS['south'] <= lat <= TOKYO_BOUNDS['north'] and 
            TOKYO_BOUNDS['west'] <= lng <= TOKYO_BOUNDS['east'])

def geocode_address(address):
    """住所から緯度経度を取得（OpenStreetMap Nominatim API使用）"""
    try:
        # より具体的な検索のため「東京」を付加
        search_address = f"{address}, 東京, 日本"
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': search_address,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1,
            'countrycodes': 'JP'  # 日本に限定
        }
        headers = {
            'User-Agent': 'CorporateMapSystem/1.0'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data and len(data) > 0:
            result = data[0]
            lat = float(result['lat'])
            lng = float(result['lon'])
            
            # 結果が東京都内か確認
            if is_within_tokyo(lat, lng):
                return (lat, lng)
        
        return None
    except Exception as e:
        print(f"Geocoding error: {e}")
        # フォールバック: 住所に基づく簡易的な座標推定
        return fallback_geocode(address)

def fallback_geocode(address):
    """住所文字列から東京都内の推定座標を返す（フォールバック機能）"""
    
    # 東京都内の主要エリアの座標データ
    tokyo_areas = {
        '渋谷': (35.6580, 139.7016),
        '新宿': (35.6895, 139.6917),
        '池袋': (35.7295, 139.7109),
        '東京': (35.6812, 139.7671),
        '品川': (35.6284, 139.7387),
        '上野': (35.7133, 139.7775),
        '銀座': (35.6762, 139.7653),
        '六本木': (35.6627, 139.7314),
        '恵比寿': (35.6465, 139.7100),
        '秋葉原': (35.6984, 139.7731),
        '浅草': (35.7148, 139.7967),
        '丸の内': (35.6814, 139.7649),
        '有楽町': (35.6751, 139.7640),
        '赤坂': (35.6745, 139.7377),
        '青山': (35.6698, 139.7206)
    }
    
    # 住所に含まれるエリア名をチェック
    for area_name, (lat, lng) in tokyo_areas.items():
        if area_name in address:
            # 少しランダムオフセットを加える
            lat_offset = random.uniform(-0.005, 0.005)
            lng_offset = random.uniform(-0.005, 0.005)
            return (lat + lat_offset, lng + lng_offset)
    
    # エリアが見つからない場合は東京駅周辺をデフォルトとする
    lat = 35.6812 + random.uniform(-0.05, 0.05)
    lng = 139.7671 + random.uniform(-0.05, 0.05)
    
    # 東京都内の範囲内に収める
    lat = max(TOKYO_BOUNDS['south'], min(TOKYO_BOUNDS['north'], lat))
    lng = max(TOKYO_BOUNDS['west'], min(TOKYO_BOUNDS['east'], lng))
    
    return (lat, lng)

def get_station_info(lat, lng):
    """指定座標周辺の駅情報を取得（駅情報API統合）"""
    try:
        # 既存の東京駅データから最寄駅を検索
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lon1, lat1, lon2, lat2):
            # 2点間の距離をハバーサイン公式で計算
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # 地球の半径 (km)
            return c * r
        
        # 東京主要駅データ
        tokyo_stations = [
            {"name": "新宿駅", "lat": 35.6896, "lng": 139.7006, "lines": ["JR山手線", "JR中央線", "小田急線", "京王線"]},
            {"name": "渋谷駅", "lat": 35.6580, "lng": 139.7016, "lines": ["JR山手線", "東急東横線", "地下鉄半蔵門線"]},
            {"name": "池袋駅", "lat": 35.7295, "lng": 139.7109, "lines": ["JR山手線", "東武東上線", "西武池袋線"]},
            {"name": "東京駅", "lat": 35.6812, "lng": 139.7671, "lines": ["JR東海道線", "JR中央線", "地下鉄丸ノ内線"]},
            {"name": "品川駅", "lat": 35.6284, "lng": 139.7387, "lines": ["JR東海道線", "JR山手線", "京急本線"]},
            {"name": "上野駅", "lat": 35.7133, "lng": 139.7775, "lines": ["JR山手線", "JR東北線", "地下鉄銀座線"]},
            {"name": "秋葉原駅", "lat": 35.6984, "lng": 139.7731, "lines": ["JR山手線", "地下鉄日比谷線"]},
            {"name": "新橋駅", "lat": 35.6658, "lng": 139.7587, "lines": ["JR東海道線", "JR山手線", "地下鉄銀座線"]},
            {"name": "六本木駅", "lat": 35.6627, "lng": 139.7314, "lines": ["地下鉄日比谷線", "地下鉄大江戸線"]},
            {"name": "恵比寿駅", "lat": 35.6465, "lng": 139.7100, "lines": ["JR山手線", "地下鉄日比谷線"]}
        ]
        
        # 最寄駅を検索
        nearest_station = None
        min_distance = float('inf')
        
        for station in tokyo_stations:
            distance = haversine(lng, lat, station['lng'], station['lat'])
            if distance < min_distance:
                min_distance = distance
                nearest_station = station
                
        if nearest_station:
            # 徒歩時間計算（平均歩行速度4km/h）
            walk_time = int((min_distance / 4) * 60)
            return {
                'station': nearest_station,
                'distance_km': round(min_distance, 2),
                'walk_time_minutes': walk_time
            }
        
        return None
    except Exception as e:
        print(f"Station info error: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/companies')
def get_companies():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM companies")
            companies = cursor.fetchall()
        return jsonify(companies)
    except mysql.connector.Error as err:
        raise DatabaseError("Failed to retrieve companies", err)
    except Exception as err:
        raise DatabaseError("Unexpected error occurred", err)

@app.route('/search_companies')
def search_companies():
    query = request.args.get('query', '').strip()

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, name, address, latitude, longitude FROM companies")
            all_companies = cursor.fetchall()

        results = []
        
        # クエリが空でない場合のみ検索処理を実行
        if query:
            for company in all_companies:
                name_similarity = fuzz.partial_ratio(query.lower(), company['name'].lower())
                address_similarity = fuzz.partial_ratio(query.lower(), company['address'].lower())
                max_similarity = max(name_similarity, address_similarity)
                
                if max_similarity > search_config.similarity_threshold:
                    results.append({
                        'id': company['id'],
                        'name': company['name'],
                        'address': company['address'],
                        'latitude': company['latitude'],
                        'longitude': company['longitude']
                    })
            
            # Sort by similarity score (higher first)
            results.sort(key=lambda x: max(
                fuzz.partial_ratio(query.lower(), x['name'].lower()),
                fuzz.partial_ratio(query.lower(), x['address'].lower())
            ), reverse=True)
        
        # ランダムな企業を最大5件取得（重複除外のため多めに取得）
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, name, address, latitude, longitude FROM companies ORDER BY RAND() LIMIT 5")
            random_companies = cursor.fetchall()
        
        # ランダム企業をフラグ付きで追加（重複を除外して3件まで）
        existing_ids = {company['id'] for company in results}
        random_results = []
        for company in random_companies:
            if company['id'] not in existing_ids and len(random_results) < 3:
                random_results.append({
                    'id': company['id'],
                    'name': company['name'],
                    'address': company['address'],
                    'latitude': company['latitude'],
                    'longitude': company['longitude'],
                    'is_random': True  # ランダム企業のフラグ
                })
        
        # 重複除外後に3件に満たない場合は追加取得
        if len(random_results) < 3:
            excluded_ids = existing_ids | {company['id'] for company in random_results}
            with get_db_cursor() as cursor:
                placeholders = ','.join(['%s'] * len(excluded_ids))
                cursor.execute(f"SELECT id, name, address, latitude, longitude FROM companies WHERE id NOT IN ({placeholders}) ORDER BY RAND() LIMIT %s", 
                             list(excluded_ids) + [3 - len(random_results)])
                additional_companies = cursor.fetchall()
                
                for company in additional_companies:
                    random_results.append({
                        'id': company['id'],
                        'name': company['name'],
                        'address': company['address'],
                        'latitude': company['latitude'],
                        'longitude': company['longitude'],
                        'is_random': True
                    })
        
        # 検索結果の後にランダム企業を追加
        all_results = results + random_results
        
        return jsonify({
            'results': all_results,
            'search_count': len(results),
            'random_count': len(random_results)
        })
    except mysql.connector.Error as err:
        raise DatabaseError("Failed to search companies", err)
    except Exception as err:
        raise DatabaseError("Unexpected error occurred during search", err)

@app.route('/register_company', methods=['POST'])
def register_company():
    data = request.get_json()
    
    if not data:
        raise ValidationError("No data provided")
    
    name = data.get('name', '').strip()
    address = data.get('address', '').strip()
    corporate_number = data.get('corporate_number', '').strip()
    
    if not name:
        raise ValidationError("Company name is required")
    if not address:
        raise ValidationError("Company address is required")
    
    try:
        # GeoCoding APIを使用して住所から座標を取得
        geocoded_coords = geocode_address(address)
        if not geocoded_coords:
            raise ValidationError("住所から座標を取得できませんでした")
        
        latitude, longitude = geocoded_coords
        
        # 東京都内かチェック
        if not is_within_tokyo(latitude, longitude):
            raise ValidationError("東京都内の住所のみ登録可能です")
        
        with get_db_cursor() as cursor:
            # 同じ企業名が既に存在するかチェック
            cursor.execute("SELECT id FROM companies WHERE name = %s", (name,))
            existing = cursor.fetchone()
            
            if existing:
                raise ValidationError("Company with this name already exists")
            
            # 新しい企業を登録
            add_company = (
                "INSERT INTO companies "
                "(name, address, latitude, longitude, corporate_number) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            company_data = (name, address, latitude, longitude, corporate_number if corporate_number else None)
            cursor.execute(add_company, company_data)
            
            # 登録された企業の情報を取得
            cursor.execute(
                "SELECT id, name, address, latitude, longitude FROM companies WHERE name = %s AND address = %s",
                (name, address)
            )
            new_company = cursor.fetchone()
            
            # 駅情報を取得して追加
            station_info = get_station_info(latitude, longitude)
            if station_info:
                new_company['station_info'] = station_info
        
        return jsonify({
            'success': True,
            'message': 'Company registered successfully',
            'company': new_company
        }), 201
        
    except ValidationError:
        raise
    except mysql.connector.Error as err:
        raise DatabaseError("Failed to register company", err)
    except Exception as err:
        raise DatabaseError("Unexpected error occurred during registration", err)


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