"""WorkOS Magic Auth with opaque, revocable local application sessions."""
import hashlib
import os
import re
import secrets
import time
import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from . import db

router = APIRouter(prefix='/api/auth')
COOKIE = 'fmb_auth'

def required():
    return os.getenv('AUTH_REQUIRED', 'true').lower() == 'true'

def configured():
    return bool(os.getenv('WORKOS_API_KEY') and os.getenv('WORKOS_CLIENT_ID'))

def init():
    with db.connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS auth_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,email TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS auth_limits(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL,expires REAL NOT NULL);
        ''')

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def email_address(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@nitk\.edu\.in', value) or len(value)>254:
        raise HTTPException(422, 'Use your @nitk.edu.in email address.')
    return value

def identity(request):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token)>100:
        return None
    with db.connect() as c:
        row = c.execute('SELECT user_id,email FROM auth_sessions WHERE token_hash=? AND expires>?',(digest(token),time.time())).fetchone()
    return dict(row) if row else None

def is_operator(user):
    allowed = {x.strip().lower() for x in os.getenv('WORKOS_OPERATOR_EMAILS','').split(',') if x.strip()}
    return bool(user and user['email'] in allowed)

def limit(bucket, maximum, seconds):
    now = time.time()
    blocked = False
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM auth_limits WHERE expires<=?',(now,))
        c.execute('INSERT OR IGNORE INTO auth_limits VALUES(?,0,?)',(bucket,now+seconds))
        row = c.execute('SELECT count FROM auth_limits WHERE bucket=?',(bucket,)).fetchone()
        blocked = row['count'] >= maximum
        if not blocked:
            c.execute('UPDATE auth_limits SET count=count+1 WHERE bucket=?',(bucket,))
    if blocked:
        raise HTTPException(429,'Too many attempts. Please wait before trying again.')

def workos(path, payload):
    if not configured():
        raise HTTPException(503,'Student sign-in is being set up. Add the WorkOS API key and Client ID on the server.')
    try:
        with httpx.Client(timeout=20) as client:
            r = client.post('https://api.workos.com/user_management/'+path,
                headers={'Authorization':'Bearer '+os.environ['WORKOS_API_KEY']},json=payload)
        if r.status_code == 429:
            raise HTTPException(429,'Please wait before requesting or entering another code.')
        if r.status_code >= 400:
            if path == 'authenticate' and r.status_code in (400,401,403):
                raise HTTPException(401,'That code could not be verified. Check it or request a new code.')
            raise HTTPException(503,'Email sign-in is unavailable. Check the WorkOS configuration or try again later.')
        return r.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503,'Could not reach the sign-in service. Please try again.')

class Email(BaseModel):
    email: str = Field(max_length=254)

class Code(Email):
    code: str = Field(pattern=r'^\d{6}$')

@router.post('/send')
def send(body: Email, request: Request):
    email = email_address(body.email)
    ip = request.client.host if request.client else 'unknown'
    limit('send-ip:'+digest(ip),20,600)
    limit('send-email:'+digest(email),1,60)
    workos('magic_auth',{'email':email})
    # Never return, persist, or log the provider's code.
    return {'ok':True,'email':email,'expires_in':600,'resend_after':60}

@router.post('/verify')
def verify(body: Code, request: Request, response: Response):
    email = email_address(body.email)
    ip = request.client.host if request.client else 'unknown'
    limit('verify-ip:'+digest(ip),50,600)
    limit('verify-email:'+digest(email),10,600)
    result = workos('authenticate',{'client_id':os.getenv('WORKOS_CLIENT_ID'),
        'client_secret':os.getenv('WORKOS_API_KEY'),'grant_type':'urn:workos:oauth:grant-type:magic-auth:code',
        'email':email,'code':body.code})
    user = result.get('user',{})
    if not user.get('id') or user.get('email','').lower()!=email or user.get('email_verified') is not True:
        raise HTTPException(403,'A verified NITK email address is required.')
    token = secrets.token_urlsafe(32)
    with db.connect() as c:
        c.execute('DELETE FROM auth_sessions WHERE expires<=? OR token_hash=?',(time.time(),digest(request.cookies.get(COOKIE,''))))
        c.execute('INSERT INTO auth_sessions VALUES(?,?,?,?)',(digest(token),user['id'],email,time.time()+8*3600))
    response.set_cookie(COOKIE,token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false').lower()=='true',max_age=8*3600)
    response.delete_cookie('fmb_operator')
    return {'ok':True}

@router.post('/logout')
def logout(request: Request,response: Response):
    with db.connect() as c:
        c.execute('DELETE FROM auth_sessions WHERE token_hash=?',(digest(request.cookies.get(COOKIE,'')),))
    response.delete_cookie(COOKIE)
    response.delete_cookie('fmb_operator')
    return {'ok':True}
