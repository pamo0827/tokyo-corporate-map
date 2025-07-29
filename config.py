import os
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str = os.getenv('DB_HOST', 'localhost')
    user: str = os.getenv('DB_USER', 'root')
    password: str = os.getenv('DB_PASSWORD', '')
    database: str = os.getenv('DB_NAME', 'dbs_final')

@dataclass
class AppConfig:
    debug: bool = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    host: str = os.getenv('FLASK_HOST', '127.0.0.1')
    port: int = int(os.getenv('FLASK_PORT', '5000'))

@dataclass
class SearchConfig:
    similarity_threshold: int = int(os.getenv('SEARCH_SIMILARITY_THRESHOLD', '70'))

@dataclass
class APIConfig:
    gbiz_token: str = os.getenv('GBIZ_API_TOKEN', '7zNLwssU7OUnhFvcEBVEjPeg2Ih9DOzx')
    corporate_number_api_id: str = os.getenv('CORPORATE_NUMBER_API_ID', '')
    timeout: int = int(os.getenv('API_TIMEOUT', '10'))

db_config = DatabaseConfig()
app_config = AppConfig()
search_config = SearchConfig()
api_config = APIConfig()