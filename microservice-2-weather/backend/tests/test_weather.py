import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
from datetime import date
import pytest
from fastapi.testclient import TestClient

# Ensure app is discoverable
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Set test environment
os.environ["TESTING"] = "true"
os.environ["LOCAL_DEV_AUTH_ENABLED"] = "true"

def test_weather_health_endpoints(client):
    """Verify both /health and /api/health return 200 online status."""
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert res1.json()["status"] == "online"
    assert "Weather Service" in res1.json()["service"]

    res2 = client.get("/api/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "online"

def test_dev_token_issuance(client):
    """Verify local development JWT token creation."""
    payload = {
        "subject": "agronomist@leafline.local",
        "role": "agronomist",
        "field_ids": ["field-demo-1", "field-demo-2"]
    }
    res = client.post("/api/dev/token", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "agronomist"

def test_growth_stages_endpoint(client, token):
    """Verify growth stage list is populated."""
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/disease-forecast/growth-stages", headers=headers)
    assert res.status_code == 200
    stages = res.json()
    assert isinstance(stages, list)

def test_disease_forecast_calculate(client, token):
    """Verify Alternaria epidemiological risk engine (EDPS calculation)."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "field_id": "field-test-01",
        "latitude": 15.4589,
        "longitude": 75.0078,
        "growth_stage": "flowering",
        "pdi": 18.5,
        "days": 1
    }
    mock_weather_days = [{
        "forecast_date": date.today(),
        "temperature_max_c": 31.0,
        "temperature_min_c": 21.5,
        "humidity_mean_pct": 65.0,
        "rainfall_sum_mm": 2.0
    }]
    with patch("app.routers.disease_forecast.fetch_forecast", new=AsyncMock(return_value=mock_weather_days)):
        res = client.post("/api/disease-forecast/calculate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "field_id" in data
    assert "results" in data
    assert len(data["results"]) == 1

def test_sensor_registration_and_reading(client, token):
    """Verify sensor device registration and reading ingestion."""
    headers = {"Authorization": f"Bearer {token}"}
    dev_id = f"test-sensor-{os.urandom(3).hex()}"
    reg_payload = {
        "deviceId": dev_id,
        "name": "Sunflower Canopy Temp/RH Probe",
        "fieldId": "field-test-01",
        "sensorType": "DHT22",
        "measurementType": "Temperature & Humidity",
        "measurementUnit": "°C / %",
        "farmLocation": "Sector 4"
    }
    res_reg = client.post("/api/sensors/register", json=reg_payload, headers=headers)
    assert res_reg.status_code in [200, 201]
    sensor_key = res_reg.json()["sensorKey"]

    # Ingest a sensor reading using X-Sensor-Key
    read_payload = {
        "deviceId": dev_id,
        "fieldId": "field-test-01",
        "temperatureC": 28.5,
        "humidityPct": 74.0,
        "rainfallMm": 0.0,
        "windSpeedKmh": 10.5
    }
    read_headers = {"X-Sensor-Key": sensor_key}
    res_read = client.post("/api/sensor-data", json=read_payload, headers=read_headers)
    assert res_read.status_code in [200, 201]
