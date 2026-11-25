from datetime import datetime, date
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any

class DevTokenRequest(BaseModel):
    role: str = 'admin'
    subject: str = 'local-developer'
    field_ids: list[str] = Field(default_factory=lambda: ['field-demo'])

class AdminKeyLogin(BaseModel):
    admin_key: str = Field(min_length=6, max_length=256)
    subject: str = 'environment-service-admin'

class UserRegisterIn(BaseModel):
    fullName: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254)
    mobile: str = Field(default='', max_length=30)
    password: str = Field(min_length=6, max_length=128)
    farmName: Optional[str] = Field(default=None, max_length=160)
    farmLocation: Optional[str] = Field(default=None, max_length=255)
    state: Optional[str] = Field(default=None, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    latitude: Optional[float] = Field(default=12.9716, ge=-90, le=90)
    longitude: Optional[float] = Field(default=77.5946, ge=-180, le=180)
    organizationId: Optional[str] = Field(default=None, max_length=50)

class UserLoginIn(BaseModel):
    email: str
    password: str

class OrgRegisterIn(BaseModel):
    organizationName: str = Field(min_length=2, max_length=200)
    organizationType: str = Field(default='Research institution', max_length=100)
    email: str = Field(min_length=5, max_length=254)
    contactNumber: str = Field(min_length=5, max_length=50)
    contactPerson: str = Field(min_length=2, max_length=160)
    address: Optional[str] = Field(default=None, max_length=500)
    state: Optional[str] = Field(default=None, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default='', max_length=1000)
    password: str = Field(min_length=6, max_length=128)

class OrgLoginIn(BaseModel):
    identifier: str  # email, request_id, or organization_id
    password: str

class CurrentWeather(BaseModel):
    latitude: float
    longitude: float
    temperatureC: float | None
    humidityPct: float | None
    rainfallMm: float | None
    windSpeedKmh: float | None
    observedAt: datetime
    fetchedAt: datetime
    source: str
    stale: bool

class DailyForecast(BaseModel):
    date: date
    temperatureMaxC: float | None
    temperatureMinC: float | None
    humidityMeanPct: float | None = None
    rainfallSumMm: float | None
    rainfallProbabilityPct: float | None = None
    windSpeedMaxKmh: float | None

class ForecastResponse(BaseModel):
    latitude: float
    longitude: float
    days: list[DailyForecast]
    source: str
    fetchedAt: datetime
    stale: bool

class SensorReadingIn(BaseModel):
    deviceId: str | None = None
    fieldId: str = Field(min_length=1, max_length=100)
    recordedAt: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    temperatureC: float | None = None
    humidityPct: float | None = Field(default=None, ge=0, le=100)
    rainfallMm: float | None = Field(default=None, ge=0)
    windSpeedKmh: float | None = Field(default=None, ge=0)
    soilSurfaceWetnessPct: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode='after')
    def measurement_required(self):
        keys = ['temperatureC', 'humidityPct', 'rainfallMm', 'windSpeedKmh', 'soilSurfaceWetnessPct']
        if all(getattr(self, key) is None for key in keys):
            raise ValueError('At least one measurement is required')
        return self

class OperatorReadingIn(SensorReadingIn):
    deviceId: str | None = None

class SensorRegisterIn(BaseModel):
    deviceId: str = Field(min_length=1, max_length=100)
    name: str
    fieldId: str = "field-demo"
    sensorType: Optional[str] = "DHT22"
    manufacturer: Optional[str] = "Generic"
    model: Optional[str] = "DHT22"
    measurementType: Optional[str] = "Temperature and Humidity"
    measurementUnit: Optional[str] = "°C / %"
    userId: Optional[str] = None
    farmLocation: Optional[str] = None
    serialNumber: Optional[str] = None

class ReadingSubmissionIn(BaseModel):
    deviceId: str = Field(min_length=1, max_length=100)
    userId: Optional[str] = None
    fieldId: str = Field(default="field-demo", max_length=100)
    sensorName: Optional[str] = None
    sensorModel: Optional[str] = None
    measurementType: Optional[str] = "Temperature and Humidity"
    readingValue: Optional[float] = None
    measurementUnit: Optional[str] = "°C"
    farmLocation: Optional[str] = None
    temperatureC: Optional[float] = None
    humidityPct: Optional[float] = None
    rainfallMm: Optional[float] = None
    windSpeedKmh: Optional[float] = None
    soilMoisturePct: Optional[float] = None
    soilPh: Optional[float] = None
    recordedAt: Optional[datetime] = None

class AssessmentResponse(BaseModel):
    id: int
    fieldId: str | None
    conditionLabel: str
    observations: list[str]
    inputs: dict
    assessedAt: datetime
    dataFreshness: str
    disclaimer: str
