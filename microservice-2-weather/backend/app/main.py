from datetime import datetime, timedelta, timezone
import jwt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import (
    CORS_ORIGINS, LOCAL_DEV_AUTH_ENABLED, ENVIRONMENT,
    SECRET_KEY, JWT_ALGORITHM, ADMIN_ACCESS_KEY
)
from app.database import Base, engine
from app import models
from app.auth import hash_password
from app.schemas import DevTokenRequest
from app.routers.auth import router as auth_router
from app.routers.weather import router as weather_router
from app.routers.sensors import router as sensor_router
from app.routers.environment import router as environment_router
from app.routers.reports import router as reports_router
from app.routers.admin import router as admin_router
from app.routers.disease_forecast import router as disease_forecast_router
from app.routers.domains import router as domains_router

# Create any newly defined tables
Base.metadata.create_all(bind=engine)

# Safe SQLite additive migrations for columns added to existing tables
_inspector = inspect(engine)

# 1. Migrate domain_registrations
if 'domain_registrations' in _inspector.get_table_names():
    _domain_cols = {c['name'] for c in _inspector.get_columns('domain_registrations')}
    with engine.begin() as _conn:
        if 'organization_type' not in _domain_cols:
            _conn.execute(text("ALTER TABLE domain_registrations ADD COLUMN organization_type VARCHAR(100)"))
        if 'purpose' not in _domain_cols:
            _conn.execute(text("ALTER TABLE domain_registrations ADD COLUMN purpose TEXT"))

# 2. Migrate sensor_devices
if 'sensor_devices' in _inspector.get_table_names():
    _sensor_cols = {c['name'] for c in _inspector.get_columns('sensor_devices')}
    with engine.begin() as _conn:
        if 'sensor_type' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN sensor_type VARCHAR(100) DEFAULT 'DHT22'"))
        if 'manufacturer' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN manufacturer VARCHAR(160) DEFAULT 'Generic'"))
        if 'model' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN model VARCHAR(160) DEFAULT 'DHT22'"))
        if 'measurement_type' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN measurement_type VARCHAR(160) DEFAULT 'Temperature and Humidity'"))
        if 'measurement_unit' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN measurement_unit VARCHAR(50) DEFAULT '°C / %'"))
        if 'user_id' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN user_id VARCHAR(50) DEFAULT 'USR1'"))
        if 'farm_location' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN farm_location VARCHAR(255) DEFAULT 'Field A'"))
        if 'serial_number' not in _sensor_cols:
            _conn.execute(text("ALTER TABLE sensor_devices ADD COLUMN serial_number VARCHAR(100)"))

# 2b. Additive weather history metadata migration
if 'weather_observations' in _inspector.get_table_names():
    _weather_cols = {c['name'] for c in _inspector.get_columns('weather_observations')}
    with engine.begin() as _conn:
        if 'location_name' not in _weather_cols:
            _conn.execute(text("ALTER TABLE weather_observations ADD COLUMN location_name VARCHAR(255)"))
if 'forecast_snapshots' in _inspector.get_table_names():
    _forecast_cols = {c['name'] for c in _inspector.get_columns('forecast_snapshots')}
    with engine.begin() as _conn:
        if 'rain_probability_max_pct' not in _forecast_cols:
            _conn.execute(text("ALTER TABLE forecast_snapshots ADD COLUMN rain_probability_max_pct FLOAT"))
        if 'location_name' not in _forecast_cols:
            _conn.execute(text("ALTER TABLE forecast_snapshots ADD COLUMN location_name VARCHAR(255)"))
        if 'user_id' not in _forecast_cols:
            _conn.execute(text("ALTER TABLE forecast_snapshots ADD COLUMN user_id VARCHAR(50)"))
        if 'organization_id' not in _forecast_cols:
            _conn.execute(text("ALTER TABLE forecast_snapshots ADD COLUMN organization_id VARCHAR(50)"))

# 3. Migrate sensor_readings
if 'sensor_readings' in _inspector.get_table_names():
    _reading_cols = {c['name'] for c in _inspector.get_columns('sensor_readings')}
    with engine.begin() as _conn:
        if 'user_id' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN user_id VARCHAR(50) DEFAULT 'USR1'"))
        if 'sensor_name' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN sensor_name VARCHAR(160)"))
        if 'sensor_model' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN sensor_model VARCHAR(160)"))
        if 'measurement_type' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN measurement_type VARCHAR(160)"))
        if 'reading_value' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN reading_value FLOAT"))
        if 'measurement_unit' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN measurement_unit VARCHAR(50)"))
        if 'soil_moisture_pct' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN soil_moisture_pct FLOAT"))
        if 'soil_ph' not in _reading_cols:
            _conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN soil_ph FLOAT"))

# Idempotently seed Users, Organizations, and Alternaria config
from app.models import CropGrowthStage, ParameterWeight, User, Organization, SensorDevice, SensorReading
from app.services.alternaria_engine import GROWTH_STAGES, WEIGHTS

with Session(engine) as _seed_db:
    # Seed Alternaria configuration
    for _name, _score in GROWTH_STAGES.items():
        if not _seed_db.query(CropGrowthStage).filter_by(stage_name=_name).first():
            _seed_db.add(CropGrowthStage(stage_name=_name, score=_score))
    for _name, _weight in WEIGHTS.items():
        if not _seed_db.query(ParameterWeight).filter_by(parameter=_name).first():
            _seed_db.add(ParameterWeight(parameter=_name, weight=_weight))

    # Seed Initial Demo Users
    if not _seed_db.query(User).filter_by(user_id='USR1').first():
        _seed_db.add(User(
            user_id='USR1',
            full_name='Ramesh Kumar',
            email='ramesh.kumar@leafline.ag',
            mobile='+91 98765 43210',
            password_hash=hash_password('password123'),
            farm_name='Surya Sunflower Farm',
            farm_location='Dharwad Field A',
            state='Karnataka',
            district='Dharwad',
            latitude=15.4589,
            longitude=75.0078,
            organization_id='ORG1'
        ))
    if not _seed_db.query(User).filter_by(user_id='USR2').first():
        _seed_db.add(User(
            user_id='USR2',
            full_name='Priya Sharma',
            email='priya.sharma@leafline.ag',
            mobile='+91 98450 12345',
            password_hash=hash_password('password123'),
            farm_name='Golden Bloom Fields',
            farm_location='Chitradurga East',
            state='Karnataka',
            district='Chitradurga',
            latitude=14.2251,
            longitude=76.3980,
            organization_id='ORG1'
        ))

    # Seed Organizations
    if not _seed_db.query(Organization).filter_by(request_id='RQ1').first():
        _seed_db.add(Organization(
            request_id='RQ1',
            organization_id='ORG1',
            name='Karnataka AgriTech Research Institute',
            organization_type='Research institution',
            email='agritech@karnataka.gov.in',
            contact_number='+91 80 2345 6789',
            contact_person='Dr. Anand Rao',
            address='Agri Science Park, Hebbal',
            state='Karnataka',
            district='Bengaluru Urban',
            description='State research institute for sunflower disease monitoring and weather intelligence.',
            password_hash=hash_password('password123'),
            status='Accepted',
            reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        ))
    if not _seed_db.query(Organization).filter_by(request_id='RQ2').first():
        _seed_db.add(Organization(
            request_id='RQ2',
            organization_id=None,
            name='Apex BioLabs & Agronomy',
            organization_type='Private company',
            email='contact@apexbio.org',
            contact_number='+91 99887 76655',
            contact_person='Sunil Verma',
            address='Tech Zone 4, Whitefield',
            state='Karnataka',
            district='Bengaluru Rural',
            description='Agronomy consultancy evaluating regional weather impact.',
            password_hash=hash_password('password123'),
            status='Pending'
        ))
    if not _seed_db.query(Organization).filter_by(request_id='RQ3').first():
        _seed_db.add(Organization(
            request_id='RQ3',
            organization_id=None,
            name='Global Trade Exporters',
            organization_type='Other',
            email='info@globaltrade.net',
            contact_number='+91 91234 56789',
            contact_person='Mark Davis',
            address='12 Harbor View Road',
            state='Maharashtra',
            district='Mumbai',
            description='Commercial export logistics monitoring.',
            password_hash=hash_password('password123'),
            status='Rejected',
            reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        ))

    # Configure metadata on existing sensor devices
    device_configs = {
        'sensor-demo-01': {
            'name': 'DHT22 Weather Sensor',
            'sensor_type': 'DHT22',
            'manufacturer': 'Adafruit',
            'model': 'DHT22 / AM2302',
            'measurement_type': 'Temperature & Humidity',
            'measurement_unit': '°C / %',
            'user_id': 'USR1',
            'farm_location': 'Dharwad Field A'
        },
        'sensor-demo-02': {
            'name': 'Capacitive Soil Moisture Sensor',
            'sensor_type': 'Soil Moisture Sensor',
            'manufacturer': 'DFRobot',
            'model': 'Capacitive v1.2',
            'measurement_type': 'Soil Moisture',
            'measurement_unit': '%',
            'user_id': 'USR1',
            'farm_location': 'Dharwad Field A'
        },
        'sensor-demo-03': {
            'name': 'Precision Soil pH Sensor',
            'sensor_type': 'Soil pH Sensor',
            'manufacturer': 'Sensorex',
            'model': 'pH-4502C',
            'measurement_type': 'Soil pH',
            'measurement_unit': 'pH',
            'user_id': 'USR1',
            'farm_location': 'Dharwad Field A'
        },
        'sensor-demo-06': {
            'name': 'Optical Rain Gauge',
            'sensor_type': 'Rain Gauge',
            'manufacturer': 'Hydreon',
            'model': 'RG-11',
            'measurement_type': 'Rainfall',
            'measurement_unit': 'mm',
            'user_id': 'USR2',
            'farm_location': 'Chitradurga East'
        },
        'sensor-demo-07': {
            'name': 'Field Anemometer',
            'sensor_type': 'Anemometer',
            'manufacturer': 'Davis Instruments',
            'model': 'Vantage Pro 6410',
            'measurement_type': 'Wind Speed',
            'measurement_unit': 'km/h',
            'user_id': 'USR2',
            'farm_location': 'Chitradurga East'
        }
    }

    for dev_id, conf in device_configs.items():
        dev = _seed_db.query(SensorDevice).filter_by(device_id=dev_id).first()
        if dev:
            for k, v in conf.items():
                setattr(dev, k, v)

    # Backfill missing metadata in sensor_readings
    readings = _seed_db.query(SensorReading).all()
    for r in readings:
        if not r.user_id:
            r.user_id = 'USR1'
        dev = _seed_db.query(SensorDevice).filter_by(device_id=r.device_id).first() if r.device_id else None
        if dev:
            r.sensor_name = dev.name
            r.sensor_model = dev.model
            r.measurement_type = dev.measurement_type
            r.measurement_unit = dev.measurement_unit
            r.user_id = dev.user_id
        else:
            if not r.sensor_name:
                r.sensor_name = 'Field Weather Sensor'
            if not r.sensor_model:
                r.sensor_model = 'DHT22'
            if not r.measurement_type:
                r.measurement_type = 'Temperature & Humidity'
            if not r.measurement_unit:
                r.measurement_unit = '°C / %'

        if r.reading_value is None:
            r.reading_value = r.temperature_c if r.temperature_c is not None else (r.humidity_pct if r.humidity_pct is not None else 26.5)

    _seed_db.commit()

app = FastAPI(
    title='Leafline Weather Service',
    version='2.0.0',
    description='Leafline Weather Service microservice for weather observations, forecasts, sensor data, and environmental analysis.'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

# Include all microservice routers
app.include_router(auth_router)
app.include_router(weather_router)
app.include_router(sensor_router)
app.include_router(environment_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(disease_forecast_router)
app.include_router(domains_router)

@app.get('/health', tags=['Health'])
@app.get('/api/health', tags=['Health'])
def health():
    return {
        'status': 'online',
        'service': 'Leafline Weather Service',
        'version': '2.0.0'
    }

@app.post('/api/dev/token', tags=['Local Development'], include_in_schema=True)
def dev_token(body: DevTokenRequest):
    if ENVIRONMENT != 'development' or not LOCAL_DEV_AUTH_ENABLED:
        raise HTTPException(404, 'Local development token endpoint is disabled.')
    allowed = {'admin', 'user', 'organization', 'field_operator', 'agronomist', 'researcher', 'ai_analytics'}
    role = body.role.lower()
    if role not in allowed:
        raise HTTPException(422, f'role must be one of: {", ".join(sorted(allowed))}')
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            'sub': body.subject,
            'role': role,
            'user_id': 'USR1' if role == 'user' else None,
            'org_id': 'ORG1' if role == 'organization' else None,
            'field_ids': body.field_ids,
            'iss': 'leafline-weather-service',
            'iat': now,
            'exp': now + timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )
    return {
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': 28800,
        'role': role,
        'warning': 'LOCAL DEVELOPMENT ONLY. Never use this token issuer in production.'
    }

# 15-hour sensor-only assessment scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from app.models import SensorDiseaseSchedule
from app.routers.disease_forecast import _sensor_assessment

_scheduler = BackgroundScheduler(timezone="UTC")

def _run_due_sensor_assessments():
    with Session(engine) as _db:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        due = _db.query(SensorDiseaseSchedule).filter(SensorDiseaseSchedule.enabled == True).all()
        for _item in due:
            due_at = _item.next_run_at or (_item.updated_at + timedelta(hours=15))
            if due_at <= now:
                try:
                    _sensor_assessment(_db, _item.field_id, "last_15_hours", _item.growth_stage, None)
                    _item.last_run_at = now
                    _item.next_run_at = now + timedelta(hours=15)
                    _db.commit()
                except Exception:
                    _db.rollback()

_scheduler.add_job(_run_due_sensor_assessments, "interval", minutes=1, id="sensor-disease-15h", replace_existing=True)

@app.on_event("startup")
def _start_sensor_scheduler():
    import os
    if os.getenv("TESTING") == "true":
        return
    if not _scheduler.running:
        _scheduler.start()

@app.on_event("shutdown")
def _stop_sensor_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
