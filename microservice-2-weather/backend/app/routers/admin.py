from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.auth import Principal, require_roles
from app.database import get_db
from app.models import (
    User, Organization, SensorDevice, SensorReading,
    WeatherObservation, AuditLog, utc_now
)

router = APIRouter(prefix='/api/admin', tags=['Administration'])

@router.get('/stats')
def admin_stats(
    p: Principal = Depends(require_roles('admin')),
    db: Session = Depends(get_db)
):
    total_users = db.query(User).count()
    total_orgs = db.query(Organization).count()
    pending_orgs = db.query(Organization).filter_by(status='Pending').count()
    accepted_orgs = db.query(Organization).filter_by(status='Accepted').count()
    total_sensors = db.query(SensorDevice).count()
    active_sensors = db.query(SensorDevice).filter_by(is_active=True).count()
    total_readings = db.query(SensorReading).count()
    total_weather_obs = db.query(WeatherObservation).count()

    return {
        'totalUsers': total_users,
        'totalOrganizations': total_orgs,
        'pendingOrganizations': pending_orgs,
        'acceptedOrganizations': accepted_orgs,
        'totalSensors': total_sensors,
        'activeSensors': active_sensors,
        'totalReadings': total_readings,
        'totalWeatherObservations': total_weather_obs
    }

@router.get('/users')
def list_users(
    p: Principal = Depends(require_roles('admin')),
    db: Session = Depends(get_db)
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            'id': u.id,
            'userId': u.user_id,
            'fullName': u.full_name,
            'email': u.email,
            'mobile': u.mobile,
            'farmName': u.farm_name,
            'farmLocation': u.farm_location,
            'state': u.state,
            'district': u.district,
            'organizationId': u.organization_id,
            'createdAt': u.created_at
        }
        for u in users
    ]

@router.get('/organizations')
def list_organizations(
    p: Principal = Depends(require_roles('admin')),
    db: Session = Depends(get_db)
):
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
    return [
        {
            'id': o.id,
            'requestId': o.request_id,
            'organizationId': o.organization_id,
            'name': o.name,
            'organizationType': o.organization_type,
            'email': o.email,
            'contactNumber': o.contact_number,
            'contactPerson': o.contact_person,
            'address': o.address,
            'state': o.state,
            'district': o.district,
            'description': o.description,
            'status': o.status,
            'createdAt': o.created_at,
            'reviewedAt': o.reviewed_at
        }
        for o in orgs
    ]

@router.post('/organizations/{request_id}/accept')
def accept_organization(
    request_id: str,
    p: Principal = Depends(require_roles('admin')),
    db: Session = Depends(get_db)
):
    req_clean = request_id.strip().upper()
    org = db.query(Organization).filter_by(request_id=req_clean).first()
    if not org:
        raise HTTPException(status_code=404, detail=f'Organization request {request_id} not found.')

    if not org.organization_id:
        # Generate next Organization ID: ORG1, ORG2...
        accepted_count = db.query(Organization).filter(Organization.organization_id != None).count()
        org_id = f"ORG{accepted_count + 1}"
        while db.query(Organization).filter_by(organization_id=org_id).first():
            accepted_count += 1
            org_id = f"ORG{accepted_count + 1}"
        org.organization_id = org_id

    org.status = 'Accepted'
    org.reviewed_at = utc_now()

    db.add(AuditLog(
        actor_id=p.subject,
        actor_role=p.role,
        action='org.accepted',
        resource=f'org:{org.organization_id}',
        detail=f'Approved organization {org.name} (Request ID: {org.request_id}, Org ID: {org.organization_id})'
    ))
    db.commit()
    db.refresh(org)

    return {
        'requestId': org.request_id,
        'organizationId': org.organization_id,
        'status': org.status,
        'organizationName': org.name,
        'message': f'Organization {org.name} approved with Organization ID: {org.organization_id}'
    }

@router.post('/organizations/{request_id}/reject')
def reject_organization(
    request_id: str,
    p: Principal = Depends(require_roles('admin')),
    db: Session = Depends(get_db)
):
    req_clean = request_id.strip().upper()
    org = db.query(Organization).filter_by(request_id=req_clean).first()
    if not org:
        raise HTTPException(status_code=404, detail=f'Organization request {request_id} not found.')

    org.status = 'Rejected'
    org.reviewed_at = utc_now()

    db.add(AuditLog(
        actor_id=p.subject,
        actor_role=p.role,
        action='org.rejected',
        resource=f'org_request:{org.request_id}',
        detail=f'Rejected organization request for {org.name}'
    ))
    db.commit()
    db.refresh(org)

    return {
        'requestId': org.request_id,
        'status': org.status,
        'organizationName': org.name,
        'message': f'Organization request {org.request_id} rejected.'
    }

@router.get('/audit-logs')
def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    p: Principal = Depends(require_roles('admin')),
    db: Session = Depends(get_db)
):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {
        'items': [
            {
                'id': x.id,
                'actorId': x.actor_id,
                'actorRole': x.actor_role,
                'action': x.action,
                'resource': x.resource,
                'detail': x.detail,
                'createdAt': x.created_at
            }
            for x in rows
        ],
        'count': len(rows)
    }
