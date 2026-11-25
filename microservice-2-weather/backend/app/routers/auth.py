import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth import Principal, get_current_principal, hash_password, verify_password, create_access_token
from app.config import ADMIN_ACCESS_KEY
from app.database import get_db
from app.models import User, Organization, AuditLog, utc_now
from app.schemas import AdminKeyLogin, UserRegisterIn, UserLoginIn, OrgRegisterIn, OrgLoginIn

router = APIRouter(prefix='/api/auth', tags=['Authentication & Registration'])

@router.post('/admin-login')
def admin_login(body: AdminKeyLogin, db: Session = Depends(get_db)):
    # Accept configured key or standard local dev keys
    valid_keys = {ADMIN_ACCESS_KEY, 'Leafline@123', 'admin123', 'Leafline-Admin-Local-Only-Change-Me'}
    valid_keys = {k for k in valid_keys if k}

    matched = any(secrets.compare_digest(body.admin_key, k) for k in valid_keys)
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid administrator key.'
        )

    token = create_access_token({
        'sub': 'admin',
        'role': 'admin',
        'name': 'System Administrator',
        'email': 'admin@leafline.ag',
        'field_ids': ['*'],
        'scopes': ['*']
    })

    db.add(AuditLog(
        actor_id='admin',
        actor_role='admin',
        action='admin.login',
        resource='auth',
        detail='Administrator session started'
    ))
    db.commit()

    return {
        'access_token': token,
        'token_type': 'bearer',
        'role': 'admin',
        'name': 'System Administrator',
        'expires_in': 43200
    }

@router.post('/user/register', status_code=201)
def user_register(body: UserRegisterIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='A user with this email address is already registered.'
        )

    # Generate next User ID: USR1, USR2, USR3...
    total_users = db.query(User).count()
    user_id = f"USR{total_users + 1}"
    while db.query(User).filter_by(user_id=user_id).first():
        total_users += 1
        user_id = f"USR{total_users + 1}"

    user = User(
        user_id=user_id,
        full_name=body.fullName.strip(),
        email=body.email.strip().lower(),
        mobile=body.mobile.strip(),
        password_hash=hash_password(body.password),
        farm_name=body.farmName.strip() if body.farmName else None,
        farm_location=body.farmLocation.strip() if body.farmLocation else None,
        state=body.state.strip() if body.state else None,
        district=body.district.strip() if body.district else None,
        latitude=body.latitude or 12.9716,
        longitude=body.longitude or 77.5946,
        organization_id=body.organizationId.strip() if body.organizationId else None,
        created_at=utc_now()
    )
    db.add(user)
    db.add(AuditLog(
        actor_id=user_id,
        actor_role='user',
        action='user.register',
        resource=f'user:{user_id}',
        detail=f'Registered individual user {user.full_name}'
    ))
    db.commit()
    db.refresh(user)

    return {
        'userId': user.user_id,
        'fullName': user.full_name,
        'email': user.email,
        'farmName': user.farm_name,
        'message': f'User registered successfully with User ID: {user.user_id}'
    }

@router.post('/user/login')
def user_login(body: UserLoginIn, db: Session = Depends(get_db)):
    ident = body.email.strip().lower()
    user = db.query(User).filter(
        (User.email == ident) | (User.user_id == ident.upper())
    ).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid user email or password.'
        )

    token = create_access_token({
        'sub': user.user_id,
        'user_id': user.user_id,
        'role': 'user',
        'name': user.full_name,
        'email': user.email,
        'org_id': user.organization_id,
        'field_ids': [user.farm_location or 'field-demo']
    })

    return {
        'access_token': token,
        'token_type': 'bearer',
        'role': 'user',
        'userId': user.user_id,
        'name': user.full_name,
        'email': user.email,
        'farmName': user.farm_name,
        'farmLocation': user.farm_location,
        'latitude': user.latitude,
        'longitude': user.longitude,
        'organizationId': user.organization_id,
        'expires_in': 43200
    }

@router.post('/org/register', status_code=201)
def org_register(body: OrgRegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    existing = db.query(Organization).filter_by(email=email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='An organization with this official email is already registered.'
        )

    # Generate Request ID: RQ1, RQ2, RQ3...
    total_reqs = db.query(Organization).count()
    request_id = f"RQ{total_reqs + 1}"
    while db.query(Organization).filter_by(request_id=request_id).first():
        total_reqs += 1
        request_id = f"RQ{total_reqs + 1}"

    org = Organization(
        request_id=request_id,
        organization_id=None,
        name=body.organizationName.strip(),
        organization_type=body.organizationType.strip(),
        email=email,
        contact_number=body.contactNumber.strip(),
        contact_person=body.contactPerson.strip(),
        address=body.address.strip() if body.address else None,
        state=body.state.strip() if body.state else None,
        district=body.district.strip() if body.district else None,
        description=body.description.strip() if body.description else None,
        password_hash=hash_password(body.password),
        status='Pending',
        created_at=utc_now()
    )
    db.add(org)
    db.add(AuditLog(
        actor_id=request_id,
        actor_role='organization',
        action='org.request_submitted',
        resource=f'org_request:{request_id}',
        detail=f'Registration submitted for {org.name}'
    ))
    db.commit()
    db.refresh(org)

    return {
        'requestId': org.request_id,
        'organizationName': org.name,
        'status': org.status,
        'message': f'Registration submitted. Please save your Request ID: {org.request_id}. Administrator approval is required before login.'
    }

@router.get('/org/status/{request_id}')
def org_status(request_id: str, db: Session = Depends(get_db)):
    req_clean = request_id.strip().upper()
    org = db.query(Organization).filter(
        (Organization.request_id == req_clean) | (Organization.organization_id == req_clean)
    ).first()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No registration request found for ID: {request_id}'
        )

    return {
        'requestId': org.request_id,
        'organizationId': org.organization_id,
        'organizationName': org.name,
        'organizationType': org.organization_type,
        'email': org.email,
        'status': org.status,
        'createdAt': org.created_at,
        'reviewedAt': org.reviewed_at
    }

@router.post('/org/login')
def org_login(body: OrgLoginIn, db: Session = Depends(get_db)):
    ident = body.identifier.strip()
    ident_lower = ident.lower()
    ident_upper = ident.upper()

    org = db.query(Organization).filter(
        (Organization.email == ident_lower) |
        (Organization.request_id == ident_upper) |
        (Organization.organization_id == ident_upper)
    ).first()

    if not org or not verify_password(body.password, org.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid organization credentials.'
        )

    # Check status strictly on backend
    if org.status == 'Pending':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f'Registration request ({org.request_id}) is currently PENDING administrator review. Login is disabled until approved.'
        )
    elif org.status == 'Rejected':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f'Registration request ({org.request_id}) was REJECTED by the administrator. Access denied.'
        )
    elif org.status != 'Accepted':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f'Organization status is {org.status}. Login not permitted.'
        )

    token = create_access_token({
        'sub': org.organization_id or org.request_id,
        'org_id': org.organization_id,
        'role': 'organization',
        'name': org.name,
        'email': org.email,
        'field_ids': ['*'],
        'scopes': ['weather:read', 'sensor:read', 'forecast:read', 'report:export']
    })

    return {
        'access_token': token,
        'token_type': 'bearer',
        'role': 'organization',
        'organizationId': org.organization_id,
        'requestId': org.request_id,
        'name': org.name,
        'email': org.email,
        'organizationType': org.organization_type,
        'expires_in': 43200
    }

@router.get('/me')
def get_me(p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    res = {
        'subject': p.subject,
        'role': p.role,
        'name': p.name,
        'email': p.email,
        'userId': p.user_id,
        'organizationId': p.org_id
    }
    if p.role == 'user' and p.user_id:
        u = db.query(User).filter_by(user_id=p.user_id).first()
        if u:
            res.update({
                'farmName': u.farm_name,
                'farmLocation': u.farm_location,
                'state': u.state,
                'district': u.district,
                'latitude': u.latitude,
                'longitude': u.longitude,
                'createdAt': u.created_at
            })
    elif p.role == 'organization' and p.org_id:
        o = db.query(Organization).filter_by(organization_id=p.org_id).first()
        if o:
            res.update({
                'organizationType': o.organization_type,
                'contactPerson': o.contact_person,
                'contactNumber': o.contact_number,
                'state': o.state,
                'district': o.district,
                'address': o.address,
                'createdAt': o.created_at
            })
    return res
