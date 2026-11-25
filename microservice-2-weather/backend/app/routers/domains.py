import hashlib, json, secrets, re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from app.auth import Principal, get_current_principal
from app.database import get_db
from app.models import DomainRegistration, AuditLog
router = APIRouter(prefix='/api/domains', tags=['External domain registration'])
ALLOWED = {'environment:read','weather:read','sensor:read','forecast:read','assessment:read','growth:read'}
class RegistrationIn(BaseModel):
    service_name: str = Field(min_length=2,max_length=160)
    domain_url: HttpUrl
    contact_email: str = Field(min_length=5,max_length=254)
    description: str = Field(default='',max_length=1000)
    organization_type: str = Field(default='Other',max_length=100)
    purpose: str = Field(min_length=10,max_length=2000)
    requested_scopes: list[str] = Field(min_length=1)
@router.post('/register')
def register(body: RegistrationIn, db: Session=Depends(get_db)):
    scopes=set(body.requested_scopes)
    if not scopes or not scopes.issubset(ALLOWED): raise HTTPException(422, 'Unsupported requested scope.')
    row=DomainRegistration(service_name=body.service_name.strip(),domain_url=str(body.domain_url),contact_email=body.contact_email,description=body.description,organization_type=body.organization_type,purpose=body.purpose,requested_scopes=json.dumps(sorted(scopes)),status='PENDING')
    db.add(row); db.commit(); db.refresh(row)
    return {'registration_id':row.id,'status':row.status,'message':'Request submitted. Admin approval is required before API access.'}
@router.get('/status/{registration_id}')
def status(registration_id:int, db:Session=Depends(get_db)):
    row=db.query(DomainRegistration).filter_by(id=registration_id).first()
    if not row: raise HTTPException(404,'Registration not found.')
    return {'registration_id':row.id,'service_name':row.service_name,'status':row.status,'created_at':row.created_at}
@router.get('/pending')
def pending(p:Principal=Depends(get_current_principal),db:Session=Depends(get_db)):
    if p.role!='admin': raise HTTPException(403,'Admin role required.')
    rows=db.query(DomainRegistration).order_by(DomainRegistration.created_at.desc()).all()
    return [{'id':x.id,'service_name':x.service_name,'domain_url':x.domain_url,'contact_email':x.contact_email,'description':x.description,'organization_type':x.organization_type,'purpose':x.purpose,'requested_scopes':json.loads(x.requested_scopes),'approved_scopes':json.loads(x.approved_scopes) if x.approved_scopes else [],'status':x.status,'created_at':x.created_at} for x in rows]
class ReviewIn(BaseModel):
    approved_scopes: list[str] = Field(default_factory=list)
@router.post('/{registration_id}/approve')
def approve(registration_id:int,body:ReviewIn,p:Principal=Depends(get_current_principal),db:Session=Depends(get_db)):
    if p.role!='admin': raise HTTPException(403,'Admin role required.')
    row=db.query(DomainRegistration).filter_by(id=registration_id).first()
    if not row: raise HTTPException(404,'Registration not found.')
    requested=set(json.loads(row.requested_scopes)); approved=set(body.approved_scopes)
    if not approved or not approved.issubset(requested): raise HTTPException(422,'Approved scopes must be a non-empty subset of requested scopes.')
    secret=secrets.token_urlsafe(40); client_id='ll_'+secrets.token_urlsafe(18)
    row.client_id=client_id; row.client_secret_hash=hashlib.sha256(secret.encode()).hexdigest(); row.approved_scopes=json.dumps(sorted(approved)); row.status='APPROVED'; row.reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(AuditLog(actor_id=p.subject,actor_role=p.role,action='DOMAIN_APPROVED',resource=f'domain:{row.id}',detail=json.dumps(sorted(approved))))
    db.commit()
    return {'registration_id':row.id,'status':'APPROVED','client_id':client_id,'client_secret':secret,'warning':'Copy this secret now. It cannot be retrieved again.'}
@router.post('/{registration_id}/reject')
def reject(registration_id:int,p:Principal=Depends(get_current_principal),db:Session=Depends(get_db)):
    if p.role!='admin': raise HTTPException(403,'Admin role required.')
    row=db.query(DomainRegistration).filter_by(id=registration_id).first()
    if not row: raise HTTPException(404,'Registration not found.')
    row.status='REJECTED'; row.reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None); db.commit()
    return {'registration_id':row.id,'status':row.status}


class ClientTokenIn(BaseModel):
    grant_type: str = "client_credentials"
    client_id: str
    client_secret: str

@router.post('/token')
def client_token(body: ClientTokenIn, db: Session=Depends(get_db)):
    from datetime import timedelta
    from app.config import SECRET_KEY, JWT_ALGORITHM
    import jwt
    if body.grant_type != "client_credentials":
        raise HTTPException(400,"Only client_credentials is supported.")
    row=db.query(DomainRegistration).filter_by(client_id=body.client_id,status="APPROVED").first()
    supplied=hashlib.sha256(body.client_secret.encode()).hexdigest()
    if not row or not row.client_secret_hash or not secrets.compare_digest(row.client_secret_hash,supplied):
        raise HTTPException(401,"Invalid client credentials.")
    scopes=json.loads(row.approved_scopes or "[]")
    now=datetime.now(timezone.utc)
    token=jwt.encode({"sub":row.client_id,"role":"service","service_name":row.service_name,"scopes":scopes,"iat":now,"exp":now+timedelta(hours=1)},SECRET_KEY,algorithm=JWT_ALGORITHM)
    return {"access_token":token,"token_type":"bearer","expires_in":3600,"scope":" ".join(scopes)}

