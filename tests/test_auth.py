import time
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.main import app
from backend import auth, db

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'auth.db'))
    monkeypatch.setenv('AUTH_REQUIRED','true')
    monkeypatch.setenv('WORKOS_API_KEY','test-secret')
    monkeypatch.setenv('WORKOS_CLIENT_ID','test-client')
    monkeypatch.setenv('WORKOS_OPERATOR_EMAILS','')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    def provider(path,payload):
        if path=='magic_auth':return {'code':'123456','email':payload['email']}
        if payload['code']!='123456':raise HTTPException(401,'Invalid code')
        return {'user':{'id':'user_'+payload['email'].split('@')[0],'email':payload['email'],'email_verified':True}}
    monkeypatch.setattr(auth,'workos',provider)
    with TestClient(app) as c:yield c

def login(c,email='student@nitk.edu.in'):
    return c.post('/api/auth/verify',json={'email':email,'code':'123456'})

def test_anonymous_and_forged_cookie_blocked(client):
    assert client.get('/api/bootstrap').json()['user'] is None
    client.cookies.set('fmb_session','workos:user_student')
    client.cookies.set('fmb_auth','invented')
    assert client.get('/api/tickets').status_code==401
    assert client.post('/api/demo/operator').status_code==401

@pytest.mark.parametrize('email',['a@gmail.com','a@nitk.edu.in.evil.com','a@evilnitk.edu.in','a@sub.nitk.edu.in','a@@nitk.edu.in'])
def test_other_domains_rejected(client,email):
    assert client.post('/api/auth/send',json={'email':email}).status_code==422
    assert login(client,email).status_code==422

def test_send_never_returns_code_and_throttles(client):
    r=client.post('/api/auth/send',json={'email':'Student@nitk.edu.in'})
    assert r.status_code==200
    assert 'code' not in r.json() and '123456' not in r.text
    assert r.json()['email']=='student@nitk.edu.in'
    assert client.post('/api/auth/send',json={'email':'student@nitk.edu.in'}).status_code==429

def test_bad_code_and_unverified_provider_user(client,monkeypatch):
    assert client.post('/api/auth/verify',json={'email':'student@nitk.edu.in','code':'999999'}).status_code==401
    assert client.post('/api/auth/verify',json={'email':'student@nitk.edu.in','code':'123'}).status_code==422
    monkeypatch.setattr(auth,'workos',lambda *a:{'user':{'id':'x','email':'student@nitk.edu.in','email_verified':False}})
    assert login(client).status_code==403

def test_session_rotation_logout_and_student_role(client):
    r=login(client)
    assert r.status_code==200
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    old=client.cookies.get('fmb_auth')
    assert client.get('/api/bootstrap').json()['user']['email']=='student@nitk.edu.in'
    assert client.get('/api/tickets').status_code==200
    client.cookies.set('fmb_operator','demo')
    assert client.post('/api/demo/operator').status_code==403
    login(client)
    with db.connect() as c:assert not c.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?',(auth.digest(old),)).fetchone()
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/tickets').status_code==401

def test_ownership_survives_login_and_isolates_accounts(client):
    login(client)
    payload={'conversation_id':'owned','request_id':'draft','message':'garbage at Hostel 1'}
    assert client.post('/api/chat',json=payload).status_code==200
    r=client.post('/api/chat',json={**payload,'request_id':'submit','action':'submit'})
    assert r.status_code==200
    ticket=r.json()['ticket']['id']
    client.post('/api/auth/logout')
    login(client,'other@nitk.edu.in')
    assert not next(t for t in client.get('/api/tickets').json() if t['id']==ticket)['mine']
    assert client.post('/api/chat',json={**payload,'request_id':'different'}).status_code==403
    client.post('/api/auth/logout');login(client)
    assert next(t for t in client.get('/api/tickets').json() if t['id']==ticket)['mine']

def test_expired_session_and_operator_allowlist(client,monkeypatch):
    login(client)
    monkeypatch.setenv('WORKOS_OPERATOR_EMAILS','student@nitk.edu.in')
    assert client.post('/api/demo/operator').status_code==200
    with db.connect() as c:c.execute('UPDATE auth_sessions SET expires=?',(time.time()-1,))
    assert client.get('/api/tickets').status_code==401

def test_foreign_origin_rejected(client):
    assert client.post('/api/auth/send',json={'email':'student@nitk.edu.in'},headers={'origin':'https://evil.example'}).status_code==403
