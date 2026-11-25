import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import SECRET_KEY, JWT_ALGORITHM, JWT_ISSUER, JWT_AUDIENCE

bearer_scheme = HTTPBearer(auto_error=False, description='Paste a Leafline JWT bearer token.')

@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    field_ids: tuple[str, ...] = ()
    service_name: Optional[str] = None
    scopes: tuple[str, ...] = ()

SALT = b"leafline_weather_service_salt_2026"

def hash_password(password: str) -> str:
    if not password:
        return ""
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SALT, 100000)
    return dk.hex()

def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    target = hash_password(password)
    return hmac.compare_digest(target, hashed)

def create_access_token(data: dict, expires_hours: int = 12) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        'iss': JWT_ISSUER or 'leafline-weather-service',
        'iat': now,
        'exp': now + timedelta(hours=expires_hours)
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)

def _decode(token: str) -> Principal:
    kwargs = {'algorithms': [JWT_ALGORITHM], 'options': {'verify_aud': bool(JWT_AUDIENCE)}}
    if JWT_ISSUER:
        kwargs['issuer'] = JWT_ISSUER
    if JWT_AUDIENCE:
        kwargs['audience'] = JWT_AUDIENCE
    try:
        p = jwt.decode(token, SECRET_KEY, **kwargs)
        sub = p.get('sub')
        role = p.get('role')
        if not sub or not role:
            raise ValueError('Required claims missing')
        fields = p.get('field_ids') or []
        if not isinstance(fields, list):
            fields = []
        return Principal(
            subject=str(sub),
            role=str(role).lower(),
            user_id=p.get('user_id'),
            org_id=p.get('org_id'),
            email=p.get('email'),
            name=p.get('name'),
            field_ids=tuple(map(str, fields)),
            service_name=p.get('service_name'),
            scopes=tuple(p.get('scopes') or [])
        )
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired bearer token.',
            headers={'WWW-Authenticate': 'Bearer'}
        )

def get_current_principal(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Principal:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Bearer token required.',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    return _decode(credentials.credentials)

def get_optional_principal(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Optional[Principal]:
    if not credentials or credentials.scheme.lower() != 'bearer':
        return None
    try:
        return _decode(credentials.credentials)
    except HTTPException:
        return None

def require_roles(*roles):
    allowed = {r.lower() for r in roles}
    def check(p: Principal = Depends(get_current_principal)):
        if p.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Your role ({p.role}) is not permitted to perform this action. Required: {", ".join(sorted(allowed))}'
            )
        return p
    return check

def field_access(field_id: str, p: Principal):
    if p.role == 'field_operator' and field_id not in p.field_ids:
        raise HTTPException(status_code=403, detail='You are not authorised for this field.')
