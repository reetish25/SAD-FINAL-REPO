from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.auth import Principal, get_current_principal, require_roles
from app.database import get_db
from app.models import SensorReading, User, Organization, ForecastSnapshot, utc_now
from app.services.pdf_generator import generate_weather_service_report

router = APIRouter(prefix='/api/reports', tags=['Data Export & Reports'])

def _get_scoped_records(
    db: Session,
    p: Principal,
    userId: str | None = None,
    deviceId: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    measurement_type: str | None = None
):
    q = db.query(SensorReading)

    # Enforce role isolation
    if p.role == 'organization':
        org_users = [u.user_id for u in db.query(User).filter_by(organization_id=p.org_id).all()]
        if userId:
            if userId not in org_users:
                raise HTTPException(403, f'User {userId} is not affiliated with your organization.')
            q = q.filter_by(user_id=userId)
        else:
            q = q.filter(SensorReading.user_id.in_(org_users))
    elif p.role == 'user':
        q = q.filter_by(user_id=p.user_id)
    elif p.role == 'admin':
        if userId:
            q = q.filter_by(user_id=userId)

    if deviceId:
        q = q.filter_by(device_id=deviceId)
    if from_date:
        q = q.filter(SensorReading.recorded_at >= from_date)
    if to_date:
        q = q.filter(SensorReading.recorded_at <= to_date)
    if measurement_type and measurement_type != 'all':
        q = q.filter(SensorReading.measurement_type.ilike(f"%{measurement_type}%"))

    return q.order_by(SensorReading.recorded_at.desc()).all()


def _compute_stats(records):
    temps = [r.reading_value or r.temperature_c for r in records if (r.reading_value or r.temperature_c) is not None and ('temp' in (r.measurement_type or '').lower() or r.temperature_c is not None)]
    temps = [t for t in temps if t is not None]
    humids = [r.humidity_pct for r in records if r.humidity_pct is not None]
    rains = [r.rainfall_mm for r in records if r.rainfall_mm is not None]
    moists = [r.soil_moisture_pct for r in records if r.soil_moisture_pct is not None]
    phs = [r.soil_ph for r in records if r.soil_ph is not None]
    users = len({r.user_id for r in records if r.user_id})
    sensors = len({r.device_id for r in records if r.device_id})

    return {
        'total_readings': len(records),
        'temp_avg': f"{sum(temps)/len(temps):.1f}°C" if temps else "N/A",
        'temp_min_max': f"{min(temps):.1f} - {max(temps):.1f}°C" if temps else "N/A",
        'humidity_avg': f"{sum(humids)/len(humids):.1f}%" if humids else "N/A",
        'rainfall_sum': f"{sum(rains):.1f} mm" if rains else "0.0 mm",
        'soil_moisture_avg': f"{sum(moists)/len(moists):.1f}%" if moists else "N/A",
        'soil_ph_avg': f"{sum(phs)/len(phs):.2f}" if phs else "N/A",
        'unique_users': users,
        'unique_sensors': sensors
    }




def _get_scoped_forecast_records(
    db: Session,
    p: Principal,
    userId: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    location: str | None = None
):
    """Return only forecast snapshots within the authenticated principal's permitted locations."""
    fq = db.query(ForecastSnapshot)
    from sqlalchemy import and_, or_
    if p.role == 'user':
        if userId and userId != p.user_id:
            raise HTTPException(403, 'You can only access your own forecast records.')
        user = db.query(User).filter_by(user_id=p.user_id).first()
        clauses = [ForecastSnapshot.user_id == p.user_id]
        if user and user.latitude is not None and user.longitude is not None:
            clauses.append(and_(
                ForecastSnapshot.user_id.is_(None),
                ForecastSnapshot.organization_id.is_(None),
                ForecastSnapshot.latitude.between(user.latitude - .05, user.latitude + .05),
                ForecastSnapshot.longitude.between(user.longitude - .05, user.longitude + .05)
            ))
        fq = fq.filter(or_(*clauses))
    elif p.role == 'organization':
        org_users = db.query(User).filter_by(organization_id=p.org_id).all()
        if userId:
            org_users = [u for u in org_users if u.user_id == userId]
            if not org_users:
                raise HTTPException(403, f'User {userId} is not affiliated with your organization.')
        clauses = [ForecastSnapshot.organization_id == p.org_id]
        for user in org_users:
            if user.latitude is not None and user.longitude is not None:
                clauses.append(and_(
                    ForecastSnapshot.organization_id.is_(None),
                    ForecastSnapshot.user_id.is_(None),
                    ForecastSnapshot.latitude.between(user.latitude - .05, user.latitude + .05),
                    ForecastSnapshot.longitude.between(user.longitude - .05, user.longitude + .05)
                ))
        fq = fq.filter(or_(*clauses))
    elif p.role == 'admin' and userId:
        user = db.query(User).filter_by(user_id=userId).first()
        if not user or user.latitude is None or user.longitude is None:
            return []
        fq = fq.filter(
            ForecastSnapshot.latitude.between(user.latitude - .05, user.latitude + .05),
            ForecastSnapshot.longitude.between(user.longitude - .05, user.longitude + .05)
        )

    if from_date:
        fq = fq.filter(ForecastSnapshot.forecast_date >= from_date.date())
    if to_date:
        fq = fq.filter(ForecastSnapshot.forecast_date <= to_date.date())
    if location:
        fq = fq.filter(ForecastSnapshot.location_name.ilike(f'%{location}%'))
    return fq.order_by(ForecastSnapshot.fetched_at.desc(), ForecastSnapshot.forecast_date.asc()).all()


def _forecast_preview_item(x):
    return {
        'type': 'forecast',
        'id': x.id,
        'recordType': 'FORECAST SNAPSHOT',
        'userId': 'FORECAST',
        'sensorName': 'Open-Meteo Forecast',
        'sensorModel': 'Forecast snapshot',
        'measurementType': 'Forecast',
        'readingValue': x.temperature_max_c,
        'measurementUnit': '°C',
        'recordedAt': x.fetched_at,
        'fetchedAt': x.fetched_at,
        'forecastDate': x.forecast_date,
        'locationName': getattr(x, 'location_name', None),
        'latitude': x.latitude,
        'longitude': x.longitude,
        'temperatureMaxC': x.temperature_max_c,
        'temperatureMinC': x.temperature_min_c,
        'humidityMeanPct': x.humidity_mean_pct,
        'rainfallMm': x.rainfall_sum_mm,
        'rainfallProbabilityPct': getattr(x, 'rain_probability_max_pct', None),
        'windSpeedMaxKmh': x.wind_speed_max_kmh,
        'farmLocation': getattr(x, 'location_name', None) or f'{x.latitude}, {x.longitude}',
        'source': x.source
    }


@router.get('/preview')
def preview_report_data(
    userId: str | None = None,
    deviceId: str | None = None,
    from_: datetime | None = Query(default=None, alias='from'),
    to: datetime | None = None,
    measurementType: str | None = None,
    dataScope: str = Query('both', pattern='^(forecast|sensor|both)$'),
    location: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """Return preview rows for the selected scope, using only role-authorized database records."""
    sensor_records = []
    forecast_records = []
    if dataScope in {'sensor', 'both'}:
        sensor_records = _get_scoped_records(db, p, userId, deviceId, from_, to, measurementType)
    if dataScope in {'forecast', 'both'}:
        forecast_records = _get_scoped_forecast_records(db, p, userId, from_, to, location)

    preview_items = []
    for x in sensor_records:
        val = x.reading_value
        unit = x.measurement_unit or ''
        if val is None:
            if x.temperature_c is not None:
                val, unit = x.temperature_c, '°C'
            elif x.humidity_pct is not None:
                val, unit = x.humidity_pct, '%'
        preview_items.append({
            'type': 'sensor', 'id': x.id, 'recordType': 'SENSOR DATA',
            'userId': x.user_id or '', 'deviceId': x.device_id,
            'sensorName': x.sensor_name or x.device_id or 'Field Sensor',
            'sensorModel': x.sensor_model or '—',
            'measurementType': x.measurement_type or 'Weather & Environment',
            'readingValue': val, 'measurementUnit': unit,
            'temperatureC': x.temperature_c, 'humidityPct': x.humidity_pct,
            'rainfallMm': x.rainfall_mm, 'windSpeedKmh': x.wind_speed_kmh,
            'farmLocation': x.field_id or '—', 'recordedAt': x.recorded_at,
            'source': x.transport
        })
    preview_items.extend(_forecast_preview_item(x) for x in forecast_records)
    preview_items.sort(key=lambda item: str(item.get('recordedAt') or ''), reverse=True)

    stats = _compute_stats(sensor_records)
    stats['total_readings'] = len(preview_items)
    org_name = p.name or 'Leafline Organization'
    org_id = p.org_id or 'ORG-MAIN'
    if p.role == 'organization' and p.org_id:
        org = db.query(Organization).filter_by(organization_id=p.org_id).first()
        if org:
            org_name, org_id = org.name, org.organization_id

    return {
        'organizationName': org_name,
        'organizationId': org_id,
        'dataScope': dataScope,
        'statistics': stats,
        'totalCount': len(preview_items),
        'sensorCount': len(sensor_records),
        'forecastCount': len(forecast_records),
        'previewCount': min(len(preview_items), limit),
        'items': preview_items[:limit]
    }


@router.get('/pdf')
def export_pdf_report(
    dataScope: str = Query('both', pattern='^(forecast|sensor|both)$'),
    userId: str | None = None,
    deviceId: str | None = None,
    from_: datetime | None = Query(default=None, alias='from'),
    to: datetime | None = None,
    measurementType: str | None = None,
    location: str | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """Backward-compatible PDF endpoint; delegates to the scope-aware export pipeline."""
    return export_scoped_report(
        format='pdf', dataScope=dataScope, userId=userId, deviceId=deviceId,
        from_=from_, to=to, measurementType=measurementType, location=location,
        p=p, db=db
    )


@router.get('/export')
def export_scoped_report(
    format: str = Query('pdf', pattern='^(pdf|csv|xlsx)$'),
    dataScope: str = Query('both', pattern='^(forecast|sensor|both)$'),
    userId: str | None = None,
    deviceId: str | None = None,
    from_: datetime | None = Query(default=None, alias='from'),
    to: datetime | None = None,
    measurementType: str | None = None,
    location: str | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db)
):
    """Role-scoped export. Scope selection controls which database tables are exported."""
    import csv, io
    from fastapi.responses import StreamingResponse
    sensor_rows = []
    forecast_rows = []
    if dataScope in {'sensor', 'both'}:
        sensor_rows = _get_scoped_records(db, p, userId, deviceId, from_, to, measurementType)
    if dataScope in {'forecast', 'both'}:
        forecast_rows = _get_scoped_forecast_records(db, p, userId, from_, to, location)


    org_name = p.name or 'Leafline System'
    org_id = p.org_id or 'SYSTEM'
    if p.role == 'organization' and p.org_id:
        org = db.query(Organization).filter_by(organization_id=p.org_id).first()
        if org: org_name, org_id = org.name, org.organization_id

    sensor_data = [{
        'record_type':'SENSOR DATA','timestamp':x.recorded_at,'user_id':x.user_id,
        'sensor_id':x.device_id,'sensor_name':x.sensor_name,'sensor_model':x.sensor_model,
        'measurement':x.measurement_type,'value':x.reading_value,'unit':x.measurement_unit,
        'location':x.field_id,'temperature_c':x.temperature_c,'humidity_pct':x.humidity_pct,
        'rainfall_mm':x.rainfall_mm,'wind_speed_kmh':x.wind_speed_kmh
    } for x in sensor_rows]
    forecast_data = [{
        'record_type':'FORECAST SNAPSHOT','retrieved_at':x.fetched_at,'forecast_date':x.forecast_date,
        'location':getattr(x,'location_name',None) or f'{x.latitude},{x.longitude}',
        'latitude':x.latitude,'longitude':x.longitude,'temperature_max_c':x.temperature_max_c,
        'temperature_min_c':x.temperature_min_c,'humidity_pct':x.humidity_mean_pct,
        'rainfall_mm':x.rainfall_sum_mm,'rain_probability_pct':getattr(x,'rain_probability_max_pct',None),
        'wind_speed_kmh':x.wind_speed_max_kmh,'source':x.source
    } for x in forecast_rows]

    filename = f"Leafline_Weather_{dataScope}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if format == 'csv':
        out = io.StringIO()
        if dataScope == 'forecast':
            rows = forecast_data
        elif dataScope == 'sensor':
            rows = sensor_data
        else:
            # A unified CSV with explicit record_type; union of all columns.
            rows = sensor_data + forecast_data
        cols = sorted({k for row in rows for k in row}) if rows else ['record_type']
        writer = csv.DictWriter(out, fieldnames=cols)
        writer.writeheader(); writer.writerows(rows)
        return StreamingResponse(iter([out.getvalue()]), media_type='text/csv',
            headers={'Content-Disposition':f'attachment; filename="{filename}.csv"'})
    if format == 'xlsx':
        try:
            from openpyxl import Workbook
        except ImportError:
            raise HTTPException(501, 'Excel export requires openpyxl. Install it with: python -m pip install openpyxl')
        wb=Workbook(); ws=wb.active; ws.title='Forecast Data' if dataScope=='forecast' else 'Sensor Data'
        def sheet_write(sheet, rows):
            cols=sorted({k for row in rows for k in row}) if rows else ['No records']
            sheet.append(cols)
            for row in rows: sheet.append([str(row.get(c) if row.get(c) is not None else '') for c in cols])
            sheet.freeze_panes='A2'; sheet.auto_filter.ref=sheet.dimensions
        if dataScope in {'forecast','both'}: sheet_write(ws,forecast_data)
        if dataScope=='both':
            ws2=wb.create_sheet('Sensor Data'); sheet_write(ws2,sensor_data)
        elif dataScope=='sensor': sheet_write(ws,sensor_data)
        buf=io.BytesIO(); wb.save(buf); buf.seek(0)
        return StreamingResponse(buf,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition':f'attachment; filename="{filename}.xlsx"'})
    # PDF: preserve the existing branded report generator and label forecast rows distinctly.
    pdf_records = [{
        'record_type':'SENSOR DATA','recorded_at':x['timestamp'],'user_id':x['user_id'] or '',
        'device_id':x['sensor_id'],'sensor_name':x['sensor_name'] or '',
        'sensor_model':x['sensor_model'] or '', 'measurement_type':x['measurement'] or '',
        'reading_value':x['value'],'measurement_unit':x['unit'] or '',
        'temperature_c':x['temperature_c'],'humidity_pct':x['humidity_pct'],
        'rainfall_mm':x['rainfall_mm'],'farm_location':x['location'] or ''
    } for x in sensor_data]
    for x in forecast_data:
        pdf_records.append({'record_type':'FORECAST DATA','recorded_at':x['retrieved_at'],'user_id':'—',
            'device_id':'Open-Meteo','sensor_name':'Open-Meteo Forecast',
            'sensor_model':f"Valid {x['forecast_date']}",'measurement_type':(
                f"Tmax {x['temperature_max_c']}C; RH {x['humidity_pct']}%; "
                f"Rain {x['rainfall_mm']}mm; Wind {x['wind_speed_kmh']}km/h"
            ),
            'reading_value':x['temperature_max_c'],'measurement_unit':'°C',
            'temperature_c':x['temperature_max_c'],'humidity_pct':x['humidity_pct'],
            'rainfall_mm':x['rainfall_mm'],'farm_location':f"{x['location']} / {x['forecast_date']}"})
    stats=_compute_stats(sensor_rows)
    pdf=generate_weather_service_report(organization_name=org_name,organization_id=org_id,
        date_from=from_.strftime('%Y-%m-%d') if from_ else None,
        date_to=to.strftime('%Y-%m-%d') if to else None,user_filter=userId,
        sensor_filter=deviceId,records=pdf_records,stats=stats,
        data_scope={'forecast':'Forecast Data Only','sensor':'Sensor Data Only','both':'Both Forecast and Sensor Data'}[dataScope],
        measurement_filter=measurementType)
    return Response(content=pdf,media_type='application/pdf',
        headers={'Content-Disposition':f'attachment; filename="{filename}.pdf"'})
