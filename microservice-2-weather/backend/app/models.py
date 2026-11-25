from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class WeatherObservation(Base):
    __tablename__ = 'weather_observations'
    __table_args__ = (Index('ix_weather_location_observed', 'latitude', 'longitude', 'observed_at'),)
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temperature_c = Column(Float)
    humidity_pct = Column(Float)
    rainfall_mm = Column(Float)
    wind_speed_kmh = Column(Float)
    observed_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, nullable=False, default=utc_now)
    source = Column(String(120), nullable=False)
    location_name = Column(String(255))

class ForecastSnapshot(Base):
    __tablename__ = 'forecast_snapshots'
    __table_args__ = (Index('ix_forecast_location_date', 'latitude', 'longitude', 'forecast_date'),)
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    forecast_date = Column(Date, nullable=False)
    temperature_max_c = Column(Float)
    temperature_min_c = Column(Float)
    humidity_mean_pct = Column(Float)
    rainfall_sum_mm = Column(Float)
    wind_speed_max_kmh = Column(Float)
    rain_probability_max_pct = Column(Float)
    fetched_at = Column(DateTime, nullable=False, default=utc_now)
    source = Column(String(120), nullable=False)
    location_name = Column(String(255))
    user_id = Column(String(50), nullable=True, index=True)
    organization_id = Column(String(50), nullable=True, index=True)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(30), unique=True, nullable=False, index=True)
    full_name = Column(String(160), nullable=False)
    email = Column(String(254), unique=True, nullable=False, index=True)
    mobile = Column(String(30))
    password_hash = Column(String(128), nullable=False)
    farm_name = Column(String(160))
    farm_location = Column(String(255))
    state = Column(String(100))
    district = Column(String(100))
    latitude = Column(Float, default=12.9716)
    longitude = Column(Float, default=77.5946)
    organization_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    request_id = Column(String(20), unique=True, nullable=False, index=True)
    organization_id = Column(String(30), unique=True, nullable=True, index=True)
    name = Column(String(200), nullable=False)
    organization_type = Column(String(100))
    email = Column(String(254), unique=True, nullable=False, index=True)
    contact_number = Column(String(50))
    contact_person = Column(String(160))
    address = Column(Text)
    state = Column(String(100))
    district = Column(String(100))
    description = Column(Text)
    password_hash = Column(String(128), nullable=False)
    status = Column(String(20), default='Pending', nullable=False, index=True)  # Pending, Accepted, Rejected
    created_at = Column(DateTime, default=utc_now, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

class SensorDevice(Base):
    __tablename__ = 'sensor_devices'
    id = Column(Integer, primary_key=True)
    device_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(160), nullable=False)
    field_id = Column(String(100), nullable=False, index=True)
    api_key_hash = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    # Extended sensor registration metadata
    sensor_type = Column(String(100), default='DHT22')
    manufacturer = Column(String(160), default='Generic')
    model = Column(String(160), default='DHT22')
    measurement_type = Column(String(160), default='Temperature and Humidity')
    measurement_unit = Column(String(50), default='°C / %')
    user_id = Column(String(50), nullable=True, index=True)
    farm_location = Column(String(255))
    serial_number = Column(String(100))

class SensorReading(Base):
    __tablename__ = 'sensor_readings'
    __table_args__ = (
        Index('ix_sensor_field_recorded', 'field_id', 'recorded_at'),
        Index('ix_sensor_device_recorded', 'device_id', 'recorded_at'),
        Index('ix_sensor_user_recorded', 'user_id', 'recorded_at'),
        UniqueConstraint('device_id', 'recorded_at', name='uq_sensor_device_recorded')
    )
    id = Column(Integer, primary_key=True)
    device_id = Column(String(100), ForeignKey('sensor_devices.device_id'), nullable=True)
    field_id = Column(String(100), nullable=False, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    temperature_c = Column(Float)
    humidity_pct = Column(Float)
    rainfall_mm = Column(Float)
    wind_speed_kmh = Column(Float)
    soil_surface_wetness_pct = Column(Float)
    recorded_at = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, default=utc_now, nullable=False)
    transport = Column(String(20), nullable=False)
    source_actor = Column(String(120))
    # Extended reading metadata
    user_id = Column(String(50), nullable=True, index=True)
    sensor_name = Column(String(160))
    sensor_model = Column(String(160))
    measurement_type = Column(String(160))
    reading_value = Column(Float)
    measurement_unit = Column(String(50))
    soil_moisture_pct = Column(Float)
    soil_ph = Column(Float)

class EnvironmentalAssessment(Base):
    __tablename__ = 'environmental_assessments'
    id = Column(Integer, primary_key=True)
    field_id = Column(String(100), index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    input_values_json = Column(Text, nullable=False)
    condition_label = Column(String(80), nullable=False)
    observations_json = Column(Text, nullable=False)
    assessed_at = Column(DateTime, default=utc_now, nullable=False)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    actor_id = Column(String(120))
    actor_role = Column(String(60), nullable=False)
    action = Column(String(120), nullable=False)
    resource = Column(String(160), nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)

# Alternaria disease-risk forecasting extension
class DiseaseObservation(Base):
    __tablename__ = 'disease_observations'
    id = Column(Integer, primary_key=True)
    field_id = Column(String(100), nullable=False, index=True)
    pdi = Column(Float, nullable=False)
    leaves_observed = Column(Integer)
    rating_sum = Column(Float)
    maximum_disease_grade = Column(Integer)
    observation_date = Column(DateTime, nullable=False, default=utc_now)
    source = Column(String(80), nullable=False, default='field_observation')
    created_at = Column(DateTime, nullable=False, default=utc_now)

class CropGrowthStage(Base):
    __tablename__ = 'crop_growth_stages'
    id = Column(Integer, primary_key=True)
    stage_name = Column(String(80), nullable=False, unique=True)
    score = Column(Float, nullable=False)

class ScoringRule(Base):
    __tablename__ = 'scoring_rules'
    id = Column(Integer, primary_key=True)
    parameter = Column(String(50), nullable=False, index=True)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    lower_inclusive = Column(Boolean, nullable=False, default=True)
    upper_inclusive = Column(Boolean, nullable=False, default=False)
    score = Column(Float, nullable=False)
    description = Column(String(200))

class ParameterWeight(Base):
    __tablename__ = 'parameter_weights'
    id = Column(Integer, primary_key=True)
    parameter = Column(String(50), nullable=False, unique=True)
    weight = Column(Float, nullable=False)

class DiseaseForecast(Base):
    __tablename__ = 'disease_forecasts'
    id = Column(Integer, primary_key=True)
    field_id = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    pdi_used = Column(Float, nullable=False)
    growth_stage = Column(String(80), nullable=False)
    forecast_days = Column(Integer, nullable=False, default=7)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    algorithm_version = Column(String(30), nullable=False, default='1.0')

class ForecastDailyResult(Base):
    __tablename__ = 'forecast_daily_results'
    id = Column(Integer, primary_key=True)
    forecast_id = Column(Integer, ForeignKey('disease_forecasts.id', ondelete='CASCADE'), nullable=False, index=True)
    day_number = Column(Integer, nullable=False)
    forecast_date = Column(Date, nullable=False)
    temperature_max_c = Column(Float, nullable=False)
    temperature_min_c = Column(Float, nullable=False)
    temperature_mean_c = Column(Float, nullable=False)
    humidity_mean_pct = Column(Float, nullable=False)
    rainfall_mm = Column(Float, nullable=False)
    rainy_day_score = Column(Float, nullable=False)
    temperature_score = Column(Float, nullable=False)
    humidity_score = Column(Float, nullable=False)
    rainfall_score = Column(Float, nullable=False)
    disease_pressure_score = Column(Float, nullable=False)
    growth_stage_score = Column(Float, nullable=False)
    edps = Column(Float, nullable=False)
    risk_category = Column(String(30), nullable=False)
    advisory = Column(Text, nullable=False)

class DomainRegistration(Base):
    __tablename__ = 'domain_registrations'
    id = Column(Integer, primary_key=True)
    service_name = Column(String(160), nullable=False)
    domain_url = Column(String(500), nullable=False)
    contact_email = Column(String(254), nullable=False)
    description = Column(Text)
    organization_type = Column(String(100))
    purpose = Column(Text)
    requested_scopes = Column(Text, nullable=False)
    approved_scopes = Column(Text)
    status = Column(String(20), nullable=False, default='PENDING', index=True)
    client_id = Column(String(80), unique=True, index=True)
    client_secret_hash = Column(String(64))
    created_at = Column(DateTime, nullable=False, default=utc_now)
    reviewed_at = Column(DateTime)

class SensorDiseaseAssessment(Base):
    __tablename__ = 'sensor_disease_assessments'
    id = Column(Integer, primary_key=True)
    field_id = Column(String(100), nullable=False, index=True)
    mode = Column(String(30), nullable=False)
    reading_count = Column(Integer, nullable=False)
    reading_ids_json = Column(Text, nullable=False)
    temperature_mean_c = Column(Float)
    humidity_mean_pct = Column(Float)
    rainfall_mm = Column(Float)
    pdi_used = Column(Float)
    growth_stage = Column(String(80))
    edps = Column(Float)
    risk_category = Column(String(30))
    advisory = Column(Text)
    status = Column(String(30), nullable=False)
    assessed_at = Column(DateTime, nullable=False, default=utc_now, index=True)

class SensorDiseaseSchedule(Base):
    __tablename__ = 'sensor_disease_schedules'
    id = Column(Integer, primary_key=True)
    field_id = Column(String(100), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    interval_hours = Column(Integer, nullable=False, default=15)
    growth_stage = Column(String(80))
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    updated_at = Column(DateTime, nullable=False, default=utc_now)
