import os
from dataclasses import dataclass

# APIキー等の秘匿情報は secrets_local.py（gitignore対象）または環境変数から読む。
# リポジトリには実キーを含めない。
try:
    from secrets_local import GBIZ_API_TOKEN as _GBIZ, EDINET_API_KEY as _EDINET
except Exception:
    _GBIZ = _EDINET = ''

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
class APIConfig:
    gbiz_token: str = os.getenv('GBIZ_API_TOKEN', _GBIZ)
    edinet_api_key: str = os.getenv('EDINET_API_KEY', _EDINET)
    timeout: int = int(os.getenv('API_TIMEOUT', '10'))

db_config = DatabaseConfig()
app_config = AppConfig()
api_config = APIConfig()