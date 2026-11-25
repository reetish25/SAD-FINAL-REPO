from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.auth import Principal, get_current_principal
from app.database import get_db
from app.models import WeatherObservation, ForecastSnapshot, SensorReading, SensorDevice, User, utc_now
from app.schemas import CurrentWeather, ForecastResponse, DailyForecast
from app.services.open_meteo import fetch_current, fetch_forecast, WeatherProviderError
import httpx

router = APIRouter(prefix='/api/weather', tags=['Weather Data & Analysis'])

def _dt(v):
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)



def _forecast_scope_query(query, principal: Principal, db: Session):
    """Scope snapshots by owner; legacy unowned rows are only visible at affiliated farm coordinates."""
    from sqlalchemy import and_, or_
    if principal.role == 'user':
        user = db.query(User).filter_by(user_id=principal.user_id).first()
        clauses = [ForecastSnapshot.user_id == principal.user_id]
        if user and user.latitude is not None and user.longitude is not None:
            clauses.append(and_(
                ForecastSnapshot.user_id.is_(None),
                ForecastSnapshot.organization_id.is_(None),
                ForecastSnapshot.latitude.between(user.latitude - .05, user.latitude + .05),
                ForecastSnapshot.longitude.between(user.longitude - .05, user.longitude + .05)
            ))
        return query.filter(or_(*clauses))
    if principal.role == 'organization':
        users = db.query(User).filter_by(organization_id=principal.org_id).all()
        clauses = [ForecastSnapshot.organization_id == principal.org_id]
        for user in users:
            if user.latitude is not None and user.longitude is not None:
                clauses.append(and_(
                    ForecastSnapshot.organization_id.is_(None),
                    ForecastSnapshot.user_id.is_(None),
                    ForecastSnapshot.latitude.between(user.latitude - .05, user.latitude + .05),
                    ForecastSnapshot.longitude.between(user.longitude - .05, user.longitude + .05)
                ))
        return query.filter(or_(*clauses))
    return query


@router.get('/current', response_model=CurrentWeather)
async def current(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    locationName: str | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    now = utc_now()
    try:
        d = await fetch_current(latitude, longitude)
        row = WeatherObservation(
            latitude=d['latitude'],
            longitude=d['longitude'],
            temperature_c=d['temperature_c'],
            humidity_pct=d['humidity_pct'],
            rainfall_mm=d['rainfall_mm'],
            wind_speed_kmh=d['wind_speed_kmh'],
            observed_at=d['observed_at'],
            fetched_at=now,
            source=d['source'],
            location_name=locationName
        )
        recent = db.query(WeatherObservation).filter(
            WeatherObservation.latitude.between(latitude - 0.0001, latitude + 0.0001),
            WeatherObservation.longitude.between(longitude - 0.0001, longitude + 0.0001),
            WeatherObservation.observed_at == d['observed_at']
        ).first()
        if recent:
            row = recent
        else:
            db.add(row)
            db.commit()
        db.refresh(row)
        stale = False
    except WeatherProviderError:
        db.rollback()
        row = db.query(WeatherObservation).filter(
            WeatherObservation.latitude.between(latitude - 0.01, latitude + 0.01),
            WeatherObservation.longitude.between(longitude - 0.01, longitude + 0.01)
        ).order_by(WeatherObservation.fetched_at.desc()).first()
        if row is None:
            raise HTTPException(503, 'Weather provider unavailable and no stored observation exists.')
        stale = True

    return CurrentWeather(
        latitude=row.latitude,
        longitude=row.longitude,
        temperatureC=row.temperature_c,
        humidityPct=row.humidity_pct,
        rainfallMm=row.rainfall_mm,
        windSpeedKmh=row.wind_speed_kmh,
        observedAt=_dt(row.observed_at),
        fetchedAt=_dt(row.fetched_at),
        source=row.source,
        stale=stale
    )

@router.get('/forecast', response_model=ForecastResponse)
async def forecast(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    days: int = Query(7, ge=1, le=16),
    locationName: str | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    now = utc_now()
    if not locationName and p.role == 'user' and p.user_id:
        _u = db.query(User).filter_by(user_id=p.user_id).first()
        if _u:
            locationName = ', '.join(x for x in [_u.farm_location, _u.district, _u.state] if x)
    elif not locationName and p.role == 'organization':
        _org_users = db.query(User).filter_by(organization_id=p.org_id).all()
        _u = next((u for u in _org_users if u.latitude is not None and u.longitude is not None
                   and abs(u.latitude - latitude) <= .05 and abs(u.longitude - longitude) <= .05), None)
        if _u:
            locationName = ', '.join(x for x in [_u.farm_location, _u.district, _u.state] if x)
    try:
        data = await fetch_forecast(latitude, longitude, days)
        recent_query = db.query(ForecastSnapshot.fetched_at).filter(
            ForecastSnapshot.latitude.between(latitude - 0.0001, latitude + 0.0001),
            ForecastSnapshot.longitude.between(longitude - 0.0001, longitude + 0.0001)
        )
        recent_time = _forecast_scope_query(recent_query, p, db).order_by(ForecastSnapshot.fetched_at.desc()).first()
        if recent_time and (now - recent_time[0]).total_seconds() < 300:
            rows_query = db.query(ForecastSnapshot).filter(
                ForecastSnapshot.latitude.between(latitude - 0.0001, latitude + 0.0001),
                ForecastSnapshot.longitude.between(longitude - 0.0001, longitude + 0.0001),
                ForecastSnapshot.fetched_at == recent_time[0]
            )
            rows = _forecast_scope_query(rows_query, p, db).order_by(ForecastSnapshot.forecast_date).limit(days).all()
            fetched = recent_time[0]
        else:
            rows = [
                ForecastSnapshot(
                latitude=latitude,
                longitude=longitude,
                forecast_date=x['forecast_date'],
                temperature_max_c=x['temperature_max_c'],
                temperature_min_c=x['temperature_min_c'],
                humidity_mean_pct=x['humidity_mean_pct'],
                rainfall_sum_mm=x['rainfall_sum_mm'],
                wind_speed_max_kmh=x['wind_speed_max_kmh'],
                rain_probability_max_pct=x.get('rain_probability_max_pct'),
                fetched_at=now,
                source='open-meteo',
                location_name=locationName or None,
                user_id=p.user_id if p.role == 'user' else None,
                organization_id=p.org_id if p.role == 'organization' else None
                )
                for x in data
            ]
            db.add_all(rows)
            db.commit()
            fetched = now
        stale = False
    except WeatherProviderError:
        db.rollback()
        latest_query = db.query(ForecastSnapshot.fetched_at).filter(
            ForecastSnapshot.latitude.between(latitude - 0.01, latitude + 0.01),
            ForecastSnapshot.longitude.between(longitude - 0.01, longitude + 0.01)
        )
        latest = _forecast_scope_query(latest_query, p, db).order_by(ForecastSnapshot.fetched_at.desc()).first()
        if not latest:
            raise HTTPException(503, 'Forecast provider unavailable and no stored forecast exists.')
        fetched = latest[0]
        fallback_query = db.query(ForecastSnapshot).filter(
            ForecastSnapshot.latitude.between(latitude - 0.01, latitude + 0.01),
            ForecastSnapshot.longitude.between(longitude - 0.01, longitude + 0.01),
            ForecastSnapshot.fetched_at == fetched
        )
        rows = _forecast_scope_query(fallback_query, p, db).order_by(ForecastSnapshot.forecast_date).limit(days).all()
        stale = True

    return ForecastResponse(
        latitude=latitude,
        longitude=longitude,
        days=[
            DailyForecast(
                date=x.forecast_date,
                temperatureMaxC=x.temperature_max_c,
                temperatureMinC=x.temperature_min_c,
                humidityMeanPct=x.humidity_mean_pct,
                rainfallSumMm=x.rainfall_sum_mm,
                windSpeedMaxKmh=x.wind_speed_max_kmh,
                rainfallProbabilityPct=x.rain_probability_max_pct
            )
            for x in rows
        ],
        source='open-meteo',
        fetchedAt=_dt(fetched),
        stale=stale
    )

@router.get('/analysis')
async def weather_analysis(
    latitude: float = Query(12.9716, ge=-90, le=90),
    longitude: float = Query(77.5946, ge=-180, le=180),
    days: int = Query(7, ge=1, le=16),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """
    Combines Open-Meteo forecast cards (source A) and registered sensor readings (source B).
    Strictly isolated based on caller role:
    - Admin: sees all sensor data
    - User: sees only their own sensor readings
    - Organization: sees sensor readings for users in their organization
    """
    # 1. Fetch Forecast Data (source: open-meteo)
    forecast_items = []
    try:
        raw_forecast = await fetch_forecast(latitude, longitude, days)
        recent_query = db.query(ForecastSnapshot.fetched_at).filter(
            ForecastSnapshot.latitude.between(latitude - 0.0001, latitude + 0.0001),
            ForecastSnapshot.longitude.between(longitude - 0.0001, longitude + 0.0001)
        )
        recent_snapshot = _forecast_scope_query(recent_query, p, db).order_by(ForecastSnapshot.fetched_at.desc()).first()
        if not recent_snapshot or (utc_now() - recent_snapshot[0]).total_seconds() >= 300:
            _location_name = None
            if p.role == 'user' and p.user_id:
                _u = db.query(User).filter_by(user_id=p.user_id).first()
                if _u: _location_name = ', '.join(x for x in [_u.farm_location, _u.district, _u.state] if x)
            elif p.role == 'organization':
                _org_users = db.query(User).filter_by(organization_id=p.org_id).all()
                _u = next((u for u in _org_users if u.latitude is not None and u.longitude is not None
                           and abs(u.latitude - latitude) <= .05 and abs(u.longitude - longitude) <= .05), None)
                if _u: _location_name = ', '.join(x for x in [_u.farm_location, _u.district, _u.state] if x)
            _fetched = utc_now()
            db.add_all([ForecastSnapshot(
                latitude=latitude, longitude=longitude, forecast_date=d['forecast_date'],
                temperature_max_c=d['temperature_max_c'], temperature_min_c=d['temperature_min_c'],
                humidity_mean_pct=d['humidity_mean_pct'], rainfall_sum_mm=d['rainfall_sum_mm'],
                wind_speed_max_kmh=d['wind_speed_max_kmh'],
                rain_probability_max_pct=d.get('rain_probability_max_pct'),
                fetched_at=_fetched, source='open-meteo', location_name=_location_name,
                user_id=p.user_id if p.role == 'user' else None,
                organization_id=p.org_id if p.role == 'organization' else None
            ) for d in raw_forecast])
            db.commit()
        for d in raw_forecast:
            forecast_items.append({
                'sourceType': 'FORECAST',
                'date': str(d['forecast_date']),
                'tempMaxC': d['temperature_max_c'],
                'tempMinC': d['temperature_min_c'],
                'humidityMeanPct': d['humidity_mean_pct'],
                'rainfallMm': d['rainfall_sum_mm'],
                'rainfallProbabilityPct': d.get('rain_probability_max_pct'),
                'windSpeedMaxKmh': d['wind_speed_max_kmh'],
                'provider': 'Open-Meteo'
            })
    except Exception:
        # Fallback to local snapshot
        latest_query = db.query(ForecastSnapshot.fetched_at)
        latest = _forecast_scope_query(latest_query, p, db).order_by(ForecastSnapshot.fetched_at.desc()).first()
        if latest:
            snaps_query = db.query(ForecastSnapshot).filter_by(fetched_at=latest[0])
            snaps = _forecast_scope_query(snaps_query, p, db).order_by(ForecastSnapshot.forecast_date).limit(days).all()
            for s in snaps:
                forecast_items.append({
                    'sourceType': 'FORECAST',
                    'date': str(s.forecast_date),
                    'tempMaxC': s.temperature_max_c,
                    'tempMinC': s.temperature_min_c,
                    'humidityMeanPct': s.humidity_mean_pct,
                    'rainfallMm': s.rainfall_sum_mm,
                    'windSpeedMaxKmh': s.wind_speed_max_kmh,
                    'provider': 'Open-Meteo (Cached Snapshot)'
                })

    # 2. Fetch Sensor Data (source: registered sensors)
    sensor_q = db.query(SensorReading)
    if p.role == 'user':
        sensor_q = sensor_q.filter_by(user_id=p.user_id)
    elif p.role == 'organization':
        org_users = [u.user_id for u in db.query(User).filter_by(organization_id=p.org_id).all()]
        sensor_q = sensor_q.filter(SensorReading.user_id.in_(org_users))

    readings = sensor_q.order_by(SensorReading.recorded_at.desc()).limit(20).all()
    sensor_items = []
    for r in readings:
        val = r.reading_value
        unit = r.measurement_unit or ''
        if val is None:
            if r.temperature_c is not None:
                val = r.temperature_c
                unit = '°C'
            elif r.humidity_pct is not None:
                val = r.humidity_pct
                unit = '%'

        sensor_items.append({
            'sourceType': 'SENSOR DATA',
            'id': r.id,
            'deviceId': r.device_id,
            'sensorName': r.sensor_name or r.device_id or 'Field Sensor',
            'sensorModel': r.sensor_model or 'DHT22',
            'sensorType': (db.query(SensorDevice).filter_by(device_id=r.device_id).first().sensor_type if r.device_id and db.query(SensorDevice).filter_by(device_id=r.device_id).first() else None),
            'manufacturer': (db.query(SensorDevice).filter_by(device_id=r.device_id).first().manufacturer if r.device_id and db.query(SensorDevice).filter_by(device_id=r.device_id).first() else None),
            'userName': (db.query(User).filter_by(user_id=r.user_id).first().full_name if r.user_id and db.query(User).filter_by(user_id=r.user_id).first() else None),
            'measurementType': r.measurement_type or 'Weather & Environment',
            'readingValue': val,
            'measurementUnit': unit,
            'userId': r.user_id or 'USR1',
            'fieldId': r.field_id,
            'temperatureC': r.temperature_c,
            'humidityPct': r.humidity_pct,
            'rainfallMm': r.rainfall_mm,
            'windSpeedKmh': r.wind_speed_kmh,
            'recordedAt': r.recorded_at,
            'receivedAt': r.received_at
        })

    return {
        'forecast': forecast_items,
        'sensors': sensor_items,
        'userRole': p.role,
        'userId': p.user_id,
        'organizationId': p.org_id
    }


@router.get('/reverse-geocode')
async def reverse_geocode(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    p: Principal = Depends(get_current_principal)
):
    """Resolve coordinates to a human-readable place name using OpenStreetMap Nominatim."""
    try:
        async with httpx.AsyncClient(timeout=8.0, headers={'User-Agent': 'Leafline-Weather-Service/2.1'}) as client:
            response = await client.get('https://nominatim.openstreetmap.org/reverse', params={
                'format': 'jsonv2', 'lat': latitude, 'lon': longitude, 'zoom': 14, 'addressdetails': 1
            })
            response.raise_for_status()
            data = response.json()
        address = data.get('address') or {}
        locality = address.get('suburb') or address.get('neighbourhood') or address.get('village') or address.get('town') or address.get('city') or address.get('county')
        city = address.get('city') or address.get('town') or address.get('municipality') or address.get('county')
        state = address.get('state')
        parts = []
        for part in (locality, city, state):
            if part and part not in parts:
                parts.append(part)
        name = ', '.join(parts) or data.get('display_name')
        if not name:
            raise ValueError('No location name returned')
        return {'locationName': name, 'displayName': data.get('display_name'), 'latitude': latitude, 'longitude': longitude}
    except Exception:
        raise HTTPException(502, 'Reverse geocoding failed. You can continue using your registered farm location.')
