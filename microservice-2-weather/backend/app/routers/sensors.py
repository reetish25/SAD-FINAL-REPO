import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.auth import Principal, get_current_principal, require_roles, field_access
from app.database import get_db
from app.models import SensorDevice, SensorReading, User, AuditLog, utc_now
from app.schemas import SensorReadingIn, OperatorReadingIn, SensorRegisterIn, ReadingSubmissionIn

router = APIRouter(prefix='/api', tags=['Sensor Data & Management'])

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def _record(payload: SensorReadingIn, db: Session, device=None, transport='http', actor=None):
    at = payload.recordedAt or utc_now()
    if at.tzinfo:
        at = at.astimezone(timezone.utc).replace(tzinfo=None)
    if at > utc_now().replace(tzinfo=None):
        raise HTTPException(422, 'recordedAt cannot be in the future.')

    # Derive sensor metadata if device exists
    user_id = getattr(device, 'user_id', None) if device else None
    sensor_name = getattr(device, 'name', None) if device else None
    sensor_model = getattr(device, 'model', None) if device else None
    meas_type = getattr(device, 'measurement_type', None) if device else None
    meas_unit = getattr(device, 'measurement_unit', None) if device else None

    # Derive primary reading value
    val = payload.temperatureC
    if val is None:
        val = payload.humidityPct
    if val is None:
        val = payload.rainfallMm
    if val is None:
        val = payload.windSpeedKmh
    if val is None:
        val = payload.soilSurfaceWetnessPct

    row = SensorReading(
        device_id=device.device_id if device else payload.deviceId,
        field_id=payload.fieldId,
        latitude=payload.latitude,
        longitude=payload.longitude,
        temperature_c=payload.temperatureC,
        humidity_pct=payload.humidityPct,
        rainfall_mm=payload.rainfallMm,
        wind_speed_kmh=payload.windSpeedKmh,
        soil_surface_wetness_pct=payload.soilSurfaceWetnessPct,
        recorded_at=at,
        received_at=utc_now(),
        transport=transport,
        source_actor=actor,
        user_id=user_id,
        sensor_name=sensor_name,
        sensor_model=sensor_model,
        measurement_type=meas_type or 'Weather & Environment',
        reading_value=val,
        measurement_unit=meas_unit or '°C / %'
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Duplicate sensor reading for this device and recordedAt.')
    db.refresh(row)
    return row

@router.post('/sensor-data', status_code=201)
def sensor_ingest(
    payload: SensorReadingIn,
    x_sensor_key: str | None = Header(default=None, alias='X-Sensor-Key'),
    db: Session = Depends(get_db)
):
    if not x_sensor_key:
        raise HTTPException(401, 'X-Sensor-Key required.')
    device = db.query(SensorDevice).filter_by(device_id=payload.deviceId).first()
    if not device or not device.is_active or not secrets.compare_digest(device.api_key_hash, _hash(x_sensor_key)):
        raise HTTPException(401, 'Unknown, inactive or invalid sensor credential.')
    if device.field_id != payload.fieldId:
        raise HTTPException(403, 'Sensor is not registered for this field.')
    try:
        row = _record(payload, db, device=device, actor=device.device_id)
    except Exception:
        db.rollback()
        raise
    return {
        'readingId': row.id,
        'acceptedAt': row.received_at,
        'status': 'accepted',
        'fieldId': row.field_id,
        'userId': row.user_id
    }

@router.post('/sensor-data/operator', status_code=201)
def operator_ingest(
    payload: OperatorReadingIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    if p.role not in {'field_operator', 'agronomist', 'admin', 'user'}:
        raise HTTPException(403, 'Role cannot submit field readings.')
    field_access(payload.fieldId, p)
    device = db.query(SensorDevice).filter_by(device_id=payload.deviceId).first() if payload.deviceId else None
    row = _record(payload, db, device=device, actor=p.subject)
    if p.role == 'user' and p.user_id:
        row.user_id = p.user_id
        db.commit()
    return {
        'readingId': row.id,
        'acceptedAt': row.received_at,
        'status': 'accepted',
        'fieldId': row.field_id,
        'userId': row.user_id
    }

@router.post('/sensor-data/submit', status_code=201)
def submit_dashboard_reading(
    payload: ReadingSubmissionIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """
    Authenticated manual reading submission for an individual user's dashboard.
    Administrators have read-only access to the sensor registry and telemetry views.
    """
    if p.role != 'user':
        raise HTTPException(403, 'Only individual users can submit manual dashboard readings.')

    device = db.query(SensorDevice).filter_by(device_id=payload.deviceId).first()
    if not device:
        raise HTTPException(404, f'Sensor with ID {payload.deviceId} is not registered.')

    # User isolation: users can only submit readings for their own sensors
    if p.role == 'user' and device.user_id and device.user_id != p.user_id:
        raise HTTPException(403, 'You can only submit readings for your own registered sensors.')

    target_user_id = device.user_id or (p.user_id if p.role == 'user' else payload.userId)

    at = payload.recordedAt or utc_now()
    if at.tzinfo:
        at = at.astimezone(timezone.utc).replace(tzinfo=None)
    if at > utc_now().replace(tzinfo=None):
        raise HTTPException(422, 'recordedAt cannot be in the future.')

    # Determine reading value
    val = payload.readingValue
    if val is None:
        if payload.temperatureC is not None:
            val = payload.temperatureC
        elif payload.humidityPct is not None:
            val = payload.humidityPct
        elif payload.soilMoisturePct is not None:
            val = payload.soilMoisturePct
        elif payload.soilPh is not None:
            val = payload.soilPh
        elif payload.rainfallMm is not None:
            val = payload.rainfallMm
        elif payload.windSpeedKmh is not None:
            val = payload.windSpeedKmh

    row = SensorReading(
        device_id=device.device_id,
        field_id=payload.fieldId or device.field_id,
        temperature_c=payload.temperatureC,
        humidity_pct=payload.humidityPct,
        rainfall_mm=payload.rainfallMm,
        wind_speed_kmh=payload.windSpeedKmh,
        soil_surface_wetness_pct=payload.soilMoisturePct,
        soil_moisture_pct=payload.soilMoisturePct,
        soil_ph=payload.soilPh,
        reading_value=val,
        measurement_type=payload.measurementType or device.measurement_type,
        measurement_unit=payload.measurementUnit or device.measurement_unit,
        sensor_name=device.name,
        sensor_model=device.model,
        user_id=target_user_id,
        recorded_at=at,
        received_at=utc_now(),
        transport='dashboard',
        source_actor=p.subject
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A reading for this sensor at this exact timestamp already exists.')
    db.refresh(row)

    return {
        'readingId': row.id,
        'deviceId': row.device_id,
        'userId': row.user_id,
        'value': row.reading_value,
        'unit': row.measurement_unit,
        'recordedAt': row.recorded_at,
        'status': 'accepted'
    }

@router.post('/sensors/register', status_code=201)
@router.post('/admin/sensors', status_code=201)
def register_sensor(
    payload: SensorRegisterIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """
    Registers a sensor with complete metadata.
    Individual users can register sensors for their own account. Administrators have read-only access.
    """
    if p.role not in ('user', 'admin'):
        raise HTTPException(403, 'Only users and administrators can register sensors.')

    # User isolation: Users are automatically bound to their own user_id
    assigned_user = p.user_id or 'USR1'

    if db.query(SensorDevice).filter_by(device_id=payload.deviceId).first():
        raise HTTPException(409, f'Device ID {payload.deviceId} is already registered.')

    secret = secrets.token_urlsafe(32)
    device = SensorDevice(
        device_id=payload.deviceId.strip(),
        name=payload.name.strip(),
        field_id=payload.fieldId.strip(),
        api_key_hash=_hash(secret),
        is_active=True,
        sensor_type=payload.sensorType or 'DHT22',
        manufacturer=payload.manufacturer or 'Generic',
        model=payload.model or 'DHT22',
        measurement_type=payload.measurementType or 'Temperature and Humidity',
        measurement_unit=payload.measurementUnit or '°C / %',
        user_id=assigned_user,
        farm_location=payload.farmLocation,
        serial_number=payload.serialNumber,
        created_at=utc_now()
    )
    db.add(device)
    db.add(AuditLog(
        actor_id=p.subject,
        actor_role=p.role,
        action='sensor.register',
        resource=device.device_id,
        detail=f'Registered sensor {device.name} ({device.sensor_type}) for user {assigned_user}'
    ))
    db.commit()
    db.refresh(device)

    return {
        'deviceId': device.device_id,
        'name': device.name,
        'sensorType': device.sensor_type,
        'manufacturer': device.manufacturer,
        'model': device.model,
        'measurementType': device.measurement_type,
        'measurementUnit': device.measurement_unit,
        'userId': device.user_id,
        'farmLocation': device.farm_location,
        'fieldId': device.field_id,
        'active': device.is_active,
        'sensorKey': secret,
        'warning': 'Copy this key now. It is shown only once.'
    }

@router.get('/sensors')
@router.get('/admin/sensors')
def list_sensors(
    userId: str | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """
    List sensors scoped by caller's role:
    - Admin: all sensors, or filter by userId
    - User: only their own sensors (strict data isolation)
    - Organization: sensors belonging to users in their organization
    """
    query = db.query(SensorDevice)

    if p.role == 'user':
        # Strict user-level data isolation
        query = query.filter_by(user_id=p.user_id)
    elif p.role == 'organization':
        # Find all users belonging to this organization
        org_users = [u.user_id for u in db.query(User).filter_by(organization_id=p.org_id).all()]
        if userId and userId in org_users:
            query = query.filter_by(user_id=userId)
        else:
            query = query.filter(SensorDevice.user_id.in_(org_users))
    elif p.role == 'admin':
        if userId:
            query = query.filter_by(user_id=userId)

    rows = query.order_by(SensorDevice.created_at.desc()).all()
    return [
        {
            'deviceId': x.device_id,
            'name': x.name,
            'sensorType': x.sensor_type,
            'manufacturer': x.manufacturer,
            'model': x.model,
            'measurementType': x.measurement_type,
            'measurementUnit': x.measurement_unit,
            'userId': x.user_id,
            'farmLocation': x.farm_location,
            'fieldId': x.field_id,
            'active': x.is_active,
            'createdAt': x.created_at
        }
        for x in rows
    ]

@router.get('/sensor-data/readings')
def list_readings(
    deviceId: str | None = None,
    userId: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """
    Retrieves sensor readings strictly isolated by role:
    - User: only their own readings
    - Org: only readings for their affiliated users
    - Admin: all readings
    """
    q = db.query(SensorReading)

    if p.role == 'user':
        q = q.filter_by(user_id=p.user_id)
    elif p.role == 'organization':
        org_users = [u.user_id for u in db.query(User).filter_by(organization_id=p.org_id).all()]
        if userId and userId in org_users:
            q = q.filter_by(user_id=userId)
        else:
            q = q.filter(SensorReading.user_id.in_(org_users))
    elif p.role == 'admin':
        if userId:
            q = q.filter_by(user_id=userId)

    if deviceId:
        q = q.filter_by(device_id=deviceId)

    rows = q.order_by(SensorReading.recorded_at.desc()).limit(limit).all()
    return [
        {
            'id': r.id,
            'deviceId': r.device_id,
            'sensorName': r.sensor_name,
            'sensorModel': r.sensor_model,
            'sensorType': (db.query(SensorDevice).filter_by(device_id=r.device_id).first().sensor_type if r.device_id and db.query(SensorDevice).filter_by(device_id=r.device_id).first() else None),
            'manufacturer': (db.query(SensorDevice).filter_by(device_id=r.device_id).first().manufacturer if r.device_id and db.query(SensorDevice).filter_by(device_id=r.device_id).first() else None),
            'userName': (db.query(User).filter_by(user_id=r.user_id).first().full_name if r.user_id and db.query(User).filter_by(user_id=r.user_id).first() else None),
            'userId': r.user_id,
            'fieldId': r.field_id,
            'measurementType': r.measurement_type,
            'readingValue': r.reading_value,
            'measurementUnit': r.measurement_unit,
            'temperatureC': r.temperature_c,
            'humidityPct': r.humidity_pct,
            'rainfallMm': r.rainfall_mm,
            'windSpeedKmh': r.wind_speed_kmh,
            'soilMoisturePct': r.soil_moisture_pct,
            'soilPh': r.soil_ph,
            'recordedAt': r.recorded_at,
            'receivedAt': r.received_at,
            'transport': r.transport
        }
        for r in rows
    ]

@router.patch('/admin/sensors/{device_id}/deactivate')
def deactivate(
    device_id: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    d = db.query(SensorDevice).filter_by(device_id=device_id).first()
    if not d:
        raise HTTPException(404, 'Sensor not found.')

    if p.role == 'user' and d.user_id != p.user_id:
        raise HTTPException(403, 'You can only deactivate your own sensors.')

    d.is_active = False
    db.add(AuditLog(
        actor_id=p.subject,
        actor_role=p.role,
        action='sensor.deactivate',
        resource=device_id,
        detail=f'Deactivated sensor {device_id}'
    ))
    db.commit()
    return {'deviceId': device_id, 'active': False}
