"""Admin-managed maintenance accounts. Passwords are salted scrypt hashes."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from . import auth, db

router = APIRouter(prefix='/api/staff')

def init():
    with db.connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS staff_accounts(
          id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
          role TEXT NOT NULL,team TEXT,password_hash TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,must_change INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS staff_audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
        ''')

def hash_password(password):
    salt=secrets.token_bytes(16)
    key=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return salt.hex()+':'+key.hex()

def check_password(password,stored):
    try:
        salt,key=stored.split(':')
        candidate=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32)
        return hmac.compare_digest(candidate.hex(),key)
    except (ValueError,TypeError):return False

DUMMY_HASH=hash_password('not-a-real-account')

def principal(request,roles=None,allow_change=False):
    user=auth.identity(request)
    if not user:raise HTTPException(401,'Sign in to continue.')
    if user.get('must_change') and not allow_change:raise HTTPException(403,'Change your temporary password first.')
    if roles and user.get('role') not in roles:raise HTTPException(403,'This action is not available to your account.')
    return user

def authorize_ticket(request,ticket):
    user=principal(request,('admin','team'))
    if user['role']=='team' and ticket['team']!=user['team']:
        raise HTTPException(403,'This report belongs to another maintenance team.')
    return user

def audit(c,user,action,detail):
    c.execute('INSERT INTO staff_audit(actor,action,detail,created_at) VALUES(?,?,?,?)',
        (user['user_id'],action,detail,db.now()))

class Login(BaseModel):
    username:str=Field(min_length=1,max_length=64)
    password:str=Field(min_length=1,max_length=200)

@router.post('/login')
def login(body:Login,request:Request,response:Response):
    username=body.username.strip().lower()
    auth.limit('staff-login:'+auth.digest(username),10,600)
    auth.limit('staff-ip:'+auth.digest(request.client.host if request.client else 'unknown'),50,600)
    with db.connect() as c:
        row=c.execute('SELECT * FROM staff_accounts WHERE username=?',(username,)).fetchone()
    valid=check_password(body.password,row['password_hash'] if row else DUMMY_HASH)
    if not row or not valid or not row['active']:
        raise HTTPException(401,'The user ID or password is incorrect.')
    auth.create_session(request,response,'staff:'+row['id'],'')
    return {'ok':True}

class Password(BaseModel):
    current_password:str=Field(min_length=1,max_length=200)
    new_password:str=Field(min_length=12,max_length=200)

@router.post('/password')
def change_password(body:Password,request:Request,response:Response):
    user=principal(request,('admin','team'),allow_change=True)
    if not user['user_id'].startswith('staff:'):raise HTTPException(400,'This account uses email sign-in.')
    auth.limit('password:'+user['user_id'],10,600)
    with db.connect() as c:
        row=c.execute('SELECT * FROM staff_accounts WHERE id=?',(user['user_id'][6:],)).fetchone()
        if not check_password(body.current_password,row['password_hash']):raise HTTPException(400,'Current password is incorrect.')
        if body.new_password==body.current_password:raise HTTPException(422,'Choose a different password.')
        c.execute('UPDATE staff_accounts SET password_hash=?,must_change=0 WHERE id=?',(hash_password(body.new_password),row['id']))
        c.execute('DELETE FROM auth_sessions WHERE user_id=?',(user['user_id'],))
        audit(c,user,'Password changed',row['username'])
    auth.create_session(request,response,user['user_id'],'')
    return {'ok':True}

class Account(BaseModel):
    username:str=Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._-]{2,39}$')
    name:str=Field(min_length=2,max_length=80)
    team:str

@router.get('/accounts')
def accounts(request:Request):
    principal(request,('admin',))
    with db.connect() as c:
        return [dict(r) for r in c.execute('SELECT id,username,name,role,team,active,must_change,created_at FROM staff_accounts ORDER BY created_at DESC')]

@router.post('/accounts')
def create_account(body:Account,request:Request):
    user=principal(request,('admin',))
    if body.team not in db.TEAMS.values():raise HTTPException(422,'Choose a maintenance team.')
    password=secrets.token_urlsafe(18)
    uid=secrets.token_hex(16)
    try:
        with db.connect() as c:
            c.execute('INSERT INTO staff_accounts(id,username,name,role,team,password_hash,created_at) VALUES(?,?,?,?,?,?,?)',
                (uid,body.username.lower(),body.name.strip(),'team',body.team,hash_password(password),db.now()))
            audit(c,user,'Team account created',body.username.lower()+' / '+body.team)
    except sqlite3.IntegrityError:raise HTTPException(409,'That user ID already exists.')
    return {'username':body.username.lower(),'temporary_password':password,'team':body.team}

class AccountAction(BaseModel):
    action:str=Field(pattern=r'^(reset|disable|enable)$')

@router.post('/accounts/{account_id}')
def manage_account(account_id:str,body:AccountAction,request:Request):
    user=principal(request,('admin',))
    with db.connect() as c:
        row=c.execute("SELECT * FROM staff_accounts WHERE id=? AND role='team'",(account_id,)).fetchone()
        if not row:raise HTTPException(404,'Team account not found.')
        password=None
        if body.action=='reset':
            password=secrets.token_urlsafe(18)
            c.execute('UPDATE staff_accounts SET password_hash=?,must_change=1 WHERE id=?',(hash_password(password),account_id))
        else:c.execute('UPDATE staff_accounts SET active=? WHERE id=?',(int(body.action=='enable'),account_id))
        c.execute('DELETE FROM auth_sessions WHERE user_id=?',('staff:'+account_id,))
        audit(c,user,'Account '+body.action,row['username'])
    return {'username':row['username'],'temporary_password':password,'team':row['team']}

@router.get('/summary')
def summary(request:Request):
    principal(request,('admin',))
    with db.connect() as c:
        counts=[dict(r) for r in c.execute('SELECT team,status,COUNT(*) AS count FROM tickets GROUP BY team,status')]
        audit_rows=[dict(r) for r in c.execute('SELECT * FROM staff_audit ORDER BY id DESC LIMIT 30')]
    return {'teams':list(db.TEAMS.values()),'counts':counts,'audit':audit_rows}
