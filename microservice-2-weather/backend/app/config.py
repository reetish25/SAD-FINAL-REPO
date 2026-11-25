import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
_default_db = (BASE_DIR / 'environment_weather.db').as_posix()
DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{_default_db}")
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development').lower()
LOCAL_DEV_AUTH_ENABLED = os.getenv('LOCAL_DEV_AUTH_ENABLED', 'true').lower() == 'true'
ADMIN_ACCESS_KEY = os.getenv('ADMIN_ACCESS_KEY', 'Leafline-Admin-Local-Only-Change-Me')
SECRET_KEY = os.getenv('SECRET_KEY', 'LOCAL-ONLY-CHANGE-ME-32-CHARACTERS-MINIMUM')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ISSUER = os.getenv('JWT_ISSUER') or None
JWT_AUDIENCE = os.getenv('JWT_AUDIENCE') or None
WEATHER_PROVIDER_TIMEOUT_SECONDS = float(os.getenv('WEATHER_PROVIDER_TIMEOUT_SECONDS', '10'))
CORS_ORIGINS = [x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]

if ENVIRONMENT == 'production' and (LOCAL_DEV_AUTH_ENABLED or SECRET_KEY.startswith('LOCAL-ONLY') or ADMIN_ACCESS_KEY == 'Leafline-Admin-Local-Only-Change-Me'):
    raise RuntimeError('Production requires LOCAL_DEV_AUTH_ENABLED=false and a strong SECRET_KEY.')
