from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, date

def auth(t):
    return {'Authorization': f'Bearer {t}'}

def test_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'online'
    assert r.json()['service'] == 'Leafline Weather Service'

def test_local_dev_token(client):
    r = client.post('/api/dev/token', json={'role': 'admin'})
    assert r.status_code == 200
    assert r.json()['token_type'] == 'bearer'

def test_weather_current_persists(client, token):
    payload = {
        'latitude': 12.9716,
        'longitude': 77.5946,
        'temperature_c': 28.1,
        'humidity_pct': 60,
        'rainfall_mm': 0,
        'wind_speed_kmh': 5,
        'observed_at': datetime.now(timezone.utc).replace(tzinfo=None),
        'source': 'open-meteo'
    }
    with patch('app.routers.weather.fetch_current', new=AsyncMock(return_value=payload)):
        r = client.get('/api/weather/current?latitude=12.9716&longitude=77.5946', headers=auth(token))
    assert r.status_code == 200
    assert r.json()['temperatureC'] == 28.1
    assert r.json()['stale'] is False

def test_forecast(client, token):
    payload = [{
        'forecast_date': date.today(),
        'temperature_max_c': 31,
        'temperature_min_c': 22,
        'humidity_mean_pct': 55,
        'rainfall_sum_mm': 0,
        'wind_speed_max_kmh': 12
    }]
    with patch('app.routers.weather.fetch_forecast', new=AsyncMock(return_value=payload)):
        r = client.get('/api/weather/forecast?latitude=12.97&longitude=77.59&days=1', headers=auth(token))
    assert r.status_code == 200
    assert len(r.json()['days']) == 1

def test_sensor_registration_and_ingestion(client, token):
    h = auth(token)
    reg = client.post('/api/admin/sensors', headers=h, json={
        'deviceId': 'sensor-01',
        'name': 'Field sensor',
        'fieldId': 'field-demo',
        'sensorType': 'DHT22',
        'manufacturer': 'Adafruit',
        'model': 'DHT22',
        'measurementType': 'Temperature & Humidity',
        'measurementUnit': '°C / %'
    })
    assert reg.status_code == 201
    key = reg.json()['sensorKey']

    reading = client.post('/api/sensor-data', headers={'X-Sensor-Key': key}, json={
        'deviceId': 'sensor-01',
        'fieldId': 'field-demo',
        'temperatureC': 29,
        'humidityPct': 65
    })
    assert reading.status_code == 201

    history = client.get('/api/environmental-data/history?fieldId=field-demo', headers=h)
    assert history.status_code == 200
    assert history.json()['total'] == 1

def test_operator_scope(client):
    tok = client.post('/api/dev/token', json={'role': 'field_operator', 'field_ids': ['field-A']}).json()['access_token']
    r = client.post('/api/sensor-data/operator', headers=auth(tok), json={'fieldId': 'field-B', 'temperatureC': 28})
    assert r.status_code == 403

def test_missing_weather_token(client):
    r = client.get('/api/weather/current?latitude=12&longitude=77')
    assert r.status_code == 401

def test_user_registration_and_login(client):
    reg = client.post('/api/auth/user/register', json={
        'fullName': 'Mahesh Hegde',
        'email': 'mahesh@sunflower.org',
        'mobile': '+91 99887 76655',
        'password': 'password123',
        'farmName': 'Hegde Fields',
        'farmLocation': 'Hubli Plot 1',
        'state': 'Karnataka',
        'district': 'Dharwad'
    })
    assert reg.status_code == 201
    user_id = reg.json()['userId']
    assert user_id.startswith('USR')

    login = client.post('/api/auth/user/login', json={
        'email': 'mahesh@sunflower.org',
        'password': 'password123'
    })
    assert login.status_code == 200
    assert login.json()['role'] == 'user'
    assert login.json()['userId'] == user_id

def test_organization_approval_workflow(client, token):
    # 1. Organization submits registration request
    reg = client.post('/api/auth/org/register', json={
        'organizationName': 'Southern AgTech Labs',
        'organizationType': 'Research institution',
        'email': 'contact@southernag.org',
        'contactNumber': '+91 80 1234 5678',
        'contactPerson': 'Dr. K. S. Rao',
        'password': 'password123'
    })
    assert reg.status_code == 201
    req_id = reg.json()['requestId']
    assert req_id.startswith('RQ')
    assert reg.json()['status'] == 'Pending'

    # 2. Check public status endpoint
    st = client.get(f'/api/auth/org/status/{req_id}')
    assert st.status_code == 200
    assert st.json()['status'] == 'Pending'

    # 3. Attempt login while Pending -> Must be blocked with 403
    blocked_login = client.post('/api/auth/org/login', json={
        'identifier': req_id,
        'password': 'password123'
    })
    assert blocked_login.status_code == 403

    # 4. Administrator approves the organization
    approval = client.post(f'/api/admin/organizations/{req_id}/accept', headers=auth(token))
    assert approval.status_code == 200
    assert approval.json()['status'] == 'Accepted'
    org_id = approval.json()['organizationId']
    assert org_id.startswith('ORG')

    # 5. Organization logs in successfully
    approved_login = client.post('/api/auth/org/login', json={
        'identifier': req_id,
        'password': 'password123'
    })
    assert approved_login.status_code == 200
    assert approved_login.json()['role'] == 'organization'
    assert approved_login.json()['organizationId'] == org_id

def test_organization_rejected_workflow(client, token):
    reg = client.post('/api/auth/org/register', json={
        'organizationName': 'Disallowed Traders',
        'organizationType': 'Other',
        'email': 'traders@unknown.net',
        'contactNumber': '+91 99999 00000',
        'contactPerson': 'A. Trader',
        'password': 'password123'
    })
    req_id = reg.json()['requestId']

    # Reject
    rej = client.post(f'/api/admin/organizations/{req_id}/reject', headers=auth(token))
    assert rej.status_code == 200
    assert rej.json()['status'] == 'Rejected'

    # Login blocked
    r = client.post('/api/auth/org/login', json={'identifier': req_id, 'password': 'password123'})
    assert r.status_code == 403

def test_pdf_report_generation(client, token):
    # Register org & approve
    reg = client.post('/api/auth/org/register', json={
        'organizationName': 'PDF Test Org',
        'email': 'pdf@test.org',
        'contactNumber': '123456',
        'contactPerson': 'Tester',
        'password': 'password123'
    })
    req_id = reg.json()['requestId']
    client.post(f'/api/admin/organizations/{req_id}/accept', headers=auth(token))
    login = client.post('/api/auth/org/login', json={'identifier': req_id, 'password': 'password123'})
    org_token = login.json()['access_token']

    # Generate PDF
    pdf_res = client.get('/api/reports/pdf', headers=auth(org_token))
    assert pdf_res.status_code == 200
    assert pdf_res.headers['content-type'] == 'application/pdf'
    assert pdf_res.content.startswith(b'%PDF-1.4')
    assert b'%%EOF' in pdf_res.content
