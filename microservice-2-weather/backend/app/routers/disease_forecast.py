from datetime import datetime, timezone, timedelta
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.auth import Principal, get_current_principal, field_access
from app.database import get_db
from app.models import DiseaseObservation, DiseaseForecast, ForecastDailyResult, CropGrowthStage, ScoringRule, ParameterWeight, SensorReading, SensorDiseaseAssessment, SensorDiseaseSchedule
from app.services.open_meteo import fetch_forecast, WeatherProviderError
from app.services.alternaria_engine import GROWTH_STAGES, WEIGHTS, calculate_day

router = APIRouter(prefix='/api/disease-forecast', tags=['Alternaria Disease-Risk Forecasting'])

class ObservationIn(BaseModel):
    field_id: str = Field(min_length=1, max_length=100)
    pdi: float = Field(ge=0, le=100)
    observation_date: datetime | None = None
    source: str = 'field_observation'

class ForecastIn(BaseModel):
    field_id: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    growth_stage: str
    pdi: float | None = Field(default=None, ge=0, le=100)
    days: int = Field(default=7, ge=1, le=7)

@router.post('/observations')
def save_observation(body: ObservationIn, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    if p.role == 'field_operator': field_access(body.field_id, p)
    row = DiseaseObservation(field_id=body.field_id, pdi=body.pdi, observation_date=body.observation_date or datetime.now(timezone.utc).replace(tzinfo=None), source=body.source)
    db.add(row); db.commit(); db.refresh(row)
    return {'id': row.id, 'field_id': row.field_id, 'pdi': row.pdi, 'observation_date': row.observation_date, 'source': row.source}

@router.get('/growth-stages')
def growth_stages(p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    rows = db.query(CropGrowthStage).order_by(CropGrowthStage.id).all()
    return [{'stage_name': x.stage_name, 'score': x.score} for x in rows] or [{'stage_name': k, 'score': v} for k, v in GROWTH_STAGES.items()]

@router.post('/calculate')
async def calculate_forecast(body: ForecastIn, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    if p.role == 'field_operator': field_access(body.field_id, p)
    stage = body.growth_stage.strip().lower()
    if stage not in GROWTH_STAGES: raise HTTPException(422, f'Invalid growth_stage. Choose: {", ".join(GROWTH_STAGES)}')
    pdi = body.pdi
    if pdi is None:
        obs = db.query(DiseaseObservation).filter_by(field_id=body.field_id).order_by(DiseaseObservation.observation_date.desc(), DiseaseObservation.id.desc()).first()
        if obs is None: raise HTTPException(422, 'No PDI observation exists for this field. Submit PDI using POST /api/disease-forecast/observations or provide pdi.')
        pdi = obs.pdi
    try:
        weather_days = await fetch_forecast(body.latitude, body.longitude, body.days)
    except WeatherProviderError as exc:
        raise HTTPException(503, f'Weather forecast unavailable: {exc}')
    forecast = DiseaseForecast(field_id=body.field_id, latitude=body.latitude, longitude=body.longitude, pdi_used=pdi, growth_stage=stage, forecast_days=len(weather_days))
    db.add(forecast); db.flush()
    results = []
    for index, day in enumerate(weather_days, start=1):
        calculated = calculate_day(tmax=day.get('temperature_max_c'), tmin=day.get('temperature_min_c'), humidity=day.get('humidity_mean_pct'), rainfall=day.get('rainfall_sum_mm'), pdi=pdi, growth_stage=stage)
        if calculated['status'] != 'COMPLETE':
            db.rollback(); raise HTTPException(422, f'Weather inputs are incomplete for {day.get("forecast_date")}; no partial forecast was saved.')
        row = ForecastDailyResult(forecast_id=forecast.id, day_number=index, forecast_date=day['forecast_date'], temperature_max_c=day['temperature_max_c'], temperature_min_c=day['temperature_min_c'], temperature_mean_c=calculated['temperature_mean_c'], humidity_mean_pct=day['humidity_mean_pct'], rainfall_mm=day['rainfall_sum_mm'], rainy_day_score=calculated['rainy_day_score'], temperature_score=calculated['temperature_score'], humidity_score=calculated['humidity_score'], rainfall_score=calculated['rainfall_score'], disease_pressure_score=calculated['disease_pressure_score'], growth_stage_score=calculated['growth_stage_score'], edps=calculated['edps'], risk_category=calculated['risk_category'], advisory=calculated['advisory'])
        db.add(row)
        results.append({'day_number': index, 'date': day['forecast_date'], **calculated, 'temperature_max_c': day['temperature_max_c'], 'temperature_min_c': day['temperature_min_c'], 'humidity_mean_pct': day['humidity_mean_pct'], 'rainfall_mm': day['rainfall_sum_mm']})
    db.commit()
    return {'forecast_id': forecast.id, 'field_id': body.field_id, 'pdi_used': pdi, 'growth_stage': stage, 'algorithm_version': '1.0', 'results': results, 'scientific_note': 'Proposed operational scoring rules; not validated disease-incidence probabilities. Field validation is required. Do not prescribe fungicide solely from EDPS.'}

@router.get('/history/{forecast_id}')
def forecast_history(forecast_id: int, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    forecast = db.query(DiseaseForecast).filter_by(id=forecast_id).first()
    if not forecast: raise HTTPException(404, 'Forecast not found.')
    if p.role == 'field_operator': field_access(forecast.field_id, p)
    rows = db.query(ForecastDailyResult).filter_by(forecast_id=forecast_id).order_by(ForecastDailyResult.day_number).all()
    return {'forecast_id': forecast.id, 'field_id': forecast.field_id, 'pdi_used': forecast.pdi_used, 'growth_stage': forecast.growth_stage, 'created_at': forecast.created_at, 'results': [{'day_number': x.day_number, 'date': x.forecast_date, 'edps': x.edps, 'risk_category': x.risk_category, 'advisory': x.advisory, 'temperature_max_c': x.temperature_max_c, 'temperature_min_c': x.temperature_min_c, 'humidity_mean_pct': x.humidity_mean_pct, 'rainfall_mm': x.rainfall_mm} for x in rows]}

@router.get('/configuration')
def configuration(p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    # Expose the implemented version-1.0 configuration for transparency.
    return {'growth_stages': [{'stage_name': k, 'score': v} for k, v in GROWTH_STAGES.items()], 'weights': WEIGHTS, 'risk_bands': [{'minimum': 0, 'maximum': 25, 'category': 'LOW'}, {'minimum': 25, 'maximum': 50, 'category': 'MODERATE'}, {'minimum': 50, 'maximum': 75, 'category': 'HIGH'}, {'minimum': 75, 'maximum': 100, 'category': 'VERY HIGH'}], 'note': 'Thresholds and weights are proposed initial values requiring field validation.'}


class SensorCalculationIn(BaseModel):
    field_id: str = Field(min_length=1, max_length=100)
    growth_stage: str | None = None
    pdi: float | None = Field(default=None, ge=0, le=100)
    mode: str = Field(default="latest", pattern="^(latest|last_15_hours)$")

def _sensor_assessment(db: Session, field_id: str, mode: str, growth_stage: str | None, pdi: float | None):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = db.query(SensorReading).filter(SensorReading.field_id == field_id)
    if mode == "last_15_hours":
        query = query.filter(SensorReading.recorded_at >= now - timedelta(hours=15), SensorReading.recorded_at <= now)
    rows = query.order_by(SensorReading.recorded_at.desc()).all()
    if not rows:
        raise HTTPException(422, "No sensor readings are available for the selected calculation window.")
    # latest refresh uses one reading; scheduled window averages T/RH and sums recorded rainfall.
    selected = rows[:1] if mode == "latest" else rows
    temps = [r.temperature_c for r in selected if r.temperature_c is not None]
    rhs = [r.humidity_pct for r in selected if r.humidity_pct is not None]
    rains = [r.rainfall_mm for r in selected if r.rainfall_mm is not None]
    stage = (growth_stage or "").strip().lower()
    if not stage:
        raise HTTPException(422, "Select the current crop growth stage; no tracking record is available for this field.")
    if stage not in GROWTH_STAGES:
        raise HTTPException(422, f"Unsupported growth stage. Choose: {', '.join(GROWTH_STAGES)}")
    if pdi is None:
        obs = db.query(DiseaseObservation).filter_by(field_id=field_id).order_by(DiseaseObservation.observation_date.desc(), DiseaseObservation.id.desc()).first()
        pdi = obs.pdi if obs else None
    missing = []
    if not temps: missing.append("temperature")
    if not rhs: missing.append("humidity")
    if not rains: missing.append("rainfall")
    if pdi is None: missing.append("observed PDI")
    if missing:
        result = {"status":"INCOMPLETE_DATA","message":"Missing required inputs: " + ", ".join(missing)}
    else:
        # Sensor mode has a point temperature, so use it as both bounds (no forecast data is mixed in).
        t = sum(temps)/len(temps); rh = sum(rhs)/len(rhs); rain = sum(rains)
        result = calculate_day(tmax=t, tmin=t, humidity=rh, rainfall=rain, pdi=pdi, growth_stage=stage)
    record = SensorDiseaseAssessment(field_id=field_id, mode=mode, reading_count=len(selected),
        reading_ids_json=json.dumps([r.id for r in selected]), temperature_mean_c=(sum(temps)/len(temps) if temps else None),
        humidity_mean_pct=(sum(rhs)/len(rhs) if rhs else None), rainfall_mm=(sum(rains) if rains else None),
        pdi_used=pdi, growth_stage=stage, edps=result.get("edps"), risk_category=result.get("risk_category"),
        advisory=result.get("advisory"), status=result["status"], assessed_at=now)
    db.add(record); db.commit(); db.refresh(record)
    return {"assessment_id":record.id,"field_id":field_id,"source":"FIELD_SENSORS","mode":mode,
        "reading_count":record.reading_count,"reading_ids":json.loads(record.reading_ids_json),
        "temperature_mean_c":record.temperature_mean_c,"humidity_mean_pct":record.humidity_mean_pct,
        "rainfall_mm":record.rainfall_mm,"pdi_used":record.pdi_used,"growth_stage":record.growth_stage,
        "assessed_at":record.assessed_at,**result,
        "note":"Sensor-only current field assessment; it is not a seven-day forecast. A single sensor temperature is used as the point estimate for both temperature bounds."}

@router.post('/calculate-sensor')
def calculate_sensor(body: SensorCalculationIn, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    if p.role == 'field_operator': field_access(body.field_id, p)
    return _sensor_assessment(db, body.field_id, body.mode, body.growth_stage, body.pdi)

@router.get('/sensor-history/{field_id}')
def sensor_history(field_id: str, limit: int = 30, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    if p.role == 'field_operator': field_access(field_id, p)
    rows = db.query(SensorDiseaseAssessment).filter_by(field_id=field_id).order_by(SensorDiseaseAssessment.assessed_at.desc()).limit(min(limit,100)).all()
    return [{"assessment_id":r.id,"mode":r.mode,"reading_count":r.reading_count,"temperature_mean_c":r.temperature_mean_c,
        "humidity_mean_pct":r.humidity_mean_pct,"rainfall_mm":r.rainfall_mm,"pdi_used":r.pdi_used,"growth_stage":r.growth_stage,
        "edps":r.edps,"risk_category":r.risk_category,"status":r.status,"assessed_at":r.assessed_at} for r in rows]

@router.post('/sensor-schedule')
def set_sensor_schedule(body: dict, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    if p.role != 'admin': raise HTTPException(403,'Admin role required.')
    field_id = str(body.get('field_id','')).strip()
    enabled = body.get('enabled')
    growth_stage = str(body.get('growth_stage','')).strip().lower()
    if not field_id or not isinstance(enabled,bool) or growth_stage not in GROWTH_STAGES: raise HTTPException(422,'field_id, enabled and a valid growth_stage are required.')
    row = db.query(SensorDiseaseSchedule).filter_by(field_id=field_id).first()
    if not row:
        row=SensorDiseaseSchedule(field_id=field_id, enabled=enabled, interval_hours=15, growth_stage=growth_stage)
        db.add(row)
    row.enabled=enabled; row.interval_hours=15; row.growth_stage=growth_stage; row.updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    row.next_run_at=(row.last_run_at or row.updated_at)+timedelta(hours=15) if enabled else None
    db.commit()
    return {"field_id":field_id,"enabled":row.enabled,"interval_hours":15,"next_run_at":row.next_run_at}

@router.get('/sensor-schedule/{field_id}')
def get_sensor_schedule(field_id: str, p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    row=db.query(SensorDiseaseSchedule).filter_by(field_id=field_id).first()
    return {"field_id":field_id,"enabled":bool(row and row.enabled),"interval_hours":15,"last_run_at":row.last_run_at if row else None,"next_run_at":row.next_run_at if row else None}
