import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.auth import Principal, get_current_principal, field_access
from app.database import get_db
from app.models import WeatherObservation, ForecastSnapshot, SensorDevice, SensorReading, EnvironmentalAssessment, User, utc_now

router = APIRouter(prefix='/api/environmental-data', tags=['Environmental Analysis & Historical Data'])

def _fresh(ts):
    return 'CURRENT' if ts and (utc_now() - ts).total_seconds() <= 6 * 3600 else 'STALE'

@router.get('')
def assess(
    fieldId: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    if p.role == 'field_operator':
        if not fieldId:
            raise HTTPException(403, 'Field Operators must specify an assigned fieldId.')
        field_access(fieldId, p)

    if not fieldId and (latitude is None or longitude is None):
        raise HTTPException(400, 'Provide fieldId or latitude and longitude.')

    reading_q = db.query(SensorReading)
    weather_q = db.query(WeatherObservation)

    if fieldId:
        reading_q = reading_q.filter_by(field_id=fieldId)
        weather = None
    else:
        reading_q = reading_q.filter(
            SensorReading.latitude.between(latitude - 0.01, latitude + 0.01),
            SensorReading.longitude.between(longitude - 0.01, longitude + 0.01)
        )
        weather_q = weather_q.filter(
            WeatherObservation.latitude.between(latitude - 0.01, latitude + 0.01),
            WeatherObservation.longitude.between(longitude - 0.01, longitude + 0.01)
        )
        weather = weather_q.order_by(WeatherObservation.observed_at.desc()).first()

    sensor = reading_q.order_by(SensorReading.recorded_at.desc()).first()
    vals = {}
    for key in ['temperature_c', 'humidity_pct', 'rainfall_mm', 'wind_speed_kmh', 'soil_surface_wetness_pct']:
        v = getattr(sensor, key, None) if sensor else None
        if v is None and weather:
            v = getattr(weather, key, None)
        vals[key] = v

    available = [v for v in vals.values() if v is not None]
    if not available:
        raise HTTPException(503, 'No weather or sensor observations are available for this field/location yet.')

    label = 'DATA_AVAILABLE'
    observations = [
        'Measurements retrieved successfully from Weather Service sensors and stations.',
        'Environmental baseline parameters loaded.'
    ]
    newest = max([x for x in [sensor.recorded_at if sensor else None, weather.observed_at if weather else None] if x], default=None)

    a = EnvironmentalAssessment(
        field_id=fieldId,
        latitude=latitude,
        longitude=longitude,
        input_values_json=json.dumps(vals),
        condition_label=label,
        observations_json=json.dumps(observations),
        assessed_at=utc_now()
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    return {
        'id': a.id,
        'fieldId': fieldId,
        'conditionLabel': label,
        'observations': observations,
        'inputs': vals,
        'assessedAt': a.assessed_at,
        'dataFreshness': _fresh(newest),
        'disclaimer': 'Informational data summary only; not a diagnosis or agronomic advice.'
    }

@router.get('/assessments')
def assessments(
    fieldId: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    q = db.query(EnvironmentalAssessment)
    if p.role == 'field_operator':
        if not fieldId:
            raise HTTPException(403, 'Field Operators must specify an assigned fieldId.')
        field_access(fieldId, p)
    if fieldId:
        q = q.filter_by(field_id=fieldId)
    rows = q.order_by(EnvironmentalAssessment.assessed_at.desc(), EnvironmentalAssessment.id.desc()).limit(limit).all()
    return {
        'items': [
            {
                'id': x.id,
                'fieldId': x.field_id,
                'conditionLabel': x.condition_label,
                'inputs': json.loads(x.input_values_json),
                'observations': json.loads(x.observations_json),
                'assessedAt': x.assessed_at
            }
            for x in rows
        ],
        'count': len(rows)
    }

@router.get('/history')
def history(
    fieldId: str | None = None,
    userId: str | None = None,
    deviceId: str | None = None,
    measurementType: str | None = None,
    from_: datetime | None = Query(default=None, alias='from'),
    to: datetime | None = None,
    recordType: str = 'all',
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """
    Historical sensor and weather records with strict role isolation:
    - User: strictly limited to records where user_id == p.user_id
    - Organization: strictly limited to records for users in p.org_id
    - Admin: can query any user or all users
    """
    if from_ and to and from_ > to:
        raise HTTPException(400, 'from must be earlier than to.')

    items = []

    # 1. Query Sensor Readings
    if recordType in {'all', 'sensor'}:
        q = db.query(SensorReading)

        # Enforce Role-Based Data Isolation
        if p.role == 'user':
            q = q.filter_by(user_id=p.user_id)
        elif p.role == 'organization':
            org_users = [u.user_id for u in db.query(User).filter_by(organization_id=p.org_id).all()]
            if userId:
                if userId not in org_users:
                    raise HTTPException(403, f'User {userId} does not belong to your organization.')
                q = q.filter_by(user_id=userId)
            else:
                q = q.filter(SensorReading.user_id.in_(org_users))
        elif p.role == 'admin':
            if userId:
                q = q.filter_by(user_id=userId)

        if deviceId:
            q = q.filter_by(device_id=deviceId)
        if fieldId:
            q = q.filter_by(field_id=fieldId)
        if from_:
            q = q.filter(SensorReading.recorded_at >= from_)
        if to:
            q = q.filter(SensorReading.recorded_at <= to)
        if measurementType and measurementType != 'all':
            q = q.filter(SensorReading.measurement_type.ilike(f"%{measurementType}%"))

        for x in q.all():
            val = x.reading_value
            unit = x.measurement_unit or ''
            if val is None:
                if x.temperature_c is not None:
                    val = x.temperature_c
                    unit = '°C'
                elif x.humidity_pct is not None:
                    val = x.humidity_pct
                    unit = '%'
                elif x.rainfall_mm is not None:
                    val = x.rainfall_mm
                    unit = 'mm'

            items.append({
                'type': 'sensor',
                'id': x.id,
                'userId': x.user_id or 'USR1',
                'deviceId': x.device_id,
                'sensorType': (db.query(SensorDevice).filter_by(device_id=x.device_id).first().sensor_type if x.device_id and db.query(SensorDevice).filter_by(device_id=x.device_id).first() else None),
                'manufacturer': (db.query(SensorDevice).filter_by(device_id=x.device_id).first().manufacturer if x.device_id and db.query(SensorDevice).filter_by(device_id=x.device_id).first() else None),
                'sensorName': x.sensor_name or x.device_id or 'Field Sensor',
                'sensorModel': x.sensor_model or 'DHT22',
                'measurementType': x.measurement_type or 'Weather & Environment',
                'readingValue': val,
                'measurementUnit': unit,
                'fieldId': x.field_id,
                'recordedAt': x.recorded_at,
                'receivedAt': x.received_at,
                'source': x.transport,
                'temperatureC': x.temperature_c,
                'humidityPct': x.humidity_pct,
                'rainfallMm': x.rainfall_mm,
                'windSpeedKmh': x.wind_speed_kmh,
                'soilMoisturePct': x.soil_moisture_pct,
                'soilPh': x.soil_ph
            })

    # 2. Actual observed weather records, scoped by role/location.
    if recordType in {'all', 'weather'}:
        wq = db.query(WeatherObservation)
        if p.role == 'user':
            if userId and userId != p.user_id: raise HTTPException(403, 'You can only view your own historical weather.')
            u = db.query(User).filter_by(user_id=p.user_id).first()
            if u and u.latitude is not None and u.longitude is not None:
                wq = wq.filter(WeatherObservation.latitude.between(u.latitude-.05, u.latitude+.05), WeatherObservation.longitude.between(u.longitude-.05, u.longitude+.05))
            else: wq = wq.filter(False)
        elif p.role == 'organization':
            org_users_rows = db.query(User).filter_by(organization_id=p.org_id).all()
            if userId:
                org_users_rows = [u for u in org_users_rows if u.user_id == userId]
                if not org_users_rows: raise HTTPException(403, f'User {userId} does not belong to your organization.')
            coord_filters = []
            from sqlalchemy import or_, and_
            for u in org_users_rows:
                if u.latitude is not None and u.longitude is not None:
                    coord_filters.append(and_(WeatherObservation.latitude.between(u.latitude-.05,u.latitude+.05), WeatherObservation.longitude.between(u.longitude-.05,u.longitude+.05)))
            wq = wq.filter(or_(*coord_filters)) if coord_filters else wq.filter(False)
        if from_:
            wq = wq.filter(WeatherObservation.observed_at >= from_)
        if to:
            wq = wq.filter(WeatherObservation.observed_at <= to)
        for x in wq.all():
            items.append({
                'type': 'weather',
                'id': x.id,
                'userId': 'SYSTEM',
                'deviceId': 'Open-Meteo',
                'sensorName': 'Weather Station',
                'sensorModel': 'Open-Meteo API',
                'measurementType': 'Weather Observation',
                'readingValue': x.temperature_c,
                'measurementUnit': '°C',
                'fieldId': 'Regional',
                'recordedAt': x.observed_at,
                'receivedAt': x.fetched_at,
                'source': x.source,
                'temperatureC': x.temperature_c,
                'humidityPct': x.humidity_pct,
                'rainfallMm': x.rainfall_mm,
                'windSpeedKmh': x.wind_speed_kmh,
                'latitude': x.latitude,
                'longitude': x.longitude
            })

    # 3. Historical forecast snapshots are projections captured at fetchedAt,
    # not observed weather. Scope them by the caller's farm coordinates / org users.
    if recordType in {'all', 'forecast', 'weather'}:
        fq = db.query(ForecastSnapshot)
        from sqlalchemy import or_, and_
        if p.role == 'user':
            if userId and userId != p.user_id: raise HTTPException(403, 'You can only view your own forecast history.')
            u = db.query(User).filter_by(user_id=p.user_id).first()
            owner_filters = [ForecastSnapshot.user_id == p.user_id]
            if u and u.latitude is not None and u.longitude is not None:
                owner_filters.append(and_(
                    ForecastSnapshot.user_id.is_(None),
                    ForecastSnapshot.organization_id.is_(None),
                    ForecastSnapshot.latitude.between(u.latitude-.05,u.latitude+.05),
                    ForecastSnapshot.longitude.between(u.longitude-.05,u.longitude+.05)
                ))
            fq = fq.filter(or_(*owner_filters))
        elif p.role == 'organization':
            org_users_rows = db.query(User).filter_by(organization_id=p.org_id).all()
            if userId:
                org_users_rows = [u for u in org_users_rows if u.user_id == userId]
                if not org_users_rows: raise HTTPException(403, f'User {userId} does not belong to your organization.')
            owner_filters = [ForecastSnapshot.organization_id == p.org_id]
            for u in org_users_rows:
                if u.latitude is not None and u.longitude is not None:
                    owner_filters.append(and_(
                        ForecastSnapshot.organization_id.is_(None),
                        ForecastSnapshot.user_id.is_(None),
                        ForecastSnapshot.latitude.between(u.latitude-.05,u.latitude+.05),
                        ForecastSnapshot.longitude.between(u.longitude-.05,u.longitude+.05)
                    ))
            fq = fq.filter(or_(*owner_filters))
        if from_:
            fq = fq.filter(ForecastSnapshot.forecast_date >= from_.date())
        if to:
            fq = fq.filter(ForecastSnapshot.forecast_date <= to.date())
        if fieldId and p.role == 'admin':
            pass
        for x in fq.order_by(ForecastSnapshot.fetched_at.desc(), ForecastSnapshot.forecast_date.asc()).all():
            items.append({
                'type': 'forecast', 'id': x.id,
                'userId': x.user_id or x.organization_id or 'SYSTEM',
                'organizationId': x.organization_id,
                'locationName': getattr(x, 'location_name', None),
                'latitude': x.latitude, 'longitude': x.longitude,
                'forecastDate': x.forecast_date, 'fetchedAt': x.fetched_at,
                'temperatureMaxC': x.temperature_max_c, 'temperatureMinC': x.temperature_min_c,
                'humidityMeanPct': x.humidity_mean_pct, 'rainfallMm': x.rainfall_sum_mm,
                'rainfallProbabilityPct': getattr(x, 'rain_probability_max_pct', None),
                'windSpeedMaxKmh': x.wind_speed_max_kmh, 'source': x.source
            })

    # Sort descending by recordedAt
    items.sort(key=lambda x: (x.get('recordedAt') or x.get('fetchedAt') or x.get('observedAt'), x['type'], x['id']), reverse=True)
    return {
        'items': items[offset:offset + limit],
        'offset': offset,
        'limit': limit,
        'total': len(items)
    }
