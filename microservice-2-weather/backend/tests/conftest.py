import os
import tempfile

os.environ['ENVIRONMENT'] = 'development'
os.environ['LOCAL_DEV_AUTH_ENABLED'] = 'true'
os.environ['SECRET_KEY'] = 'test-secret-key-that-is-long-enough-for-tests-2026'
os.environ['TESTING'] = 'true'
os.environ['WEATHER_PROVIDER_TIMEOUT_SECONDS'] = '0.5'

_test_db_path = os.path.join(tempfile.gettempdir(), 'test_weather_service.db').replace('\\', '/')
os.environ['DATABASE_URL'] = f'sqlite:///{_test_db_path}'

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def token(client):
    return client.post('/api/dev/token', json={'role': 'admin', 'subject': 'test-admin', 'field_ids': ['field-demo']}).json()['access_token']
