import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import db
from backend.geo import LANDMARKS,distance_m

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'geo.db'))
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.setenv('AUTH_REQUIRED','false')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with TestClient(app) as c:
        c.get('/api/bootstrap')
        yield c

def chat(c,cid,message='',action=None,pin=None):
    return c.post('/api/chat',json={'conversation_id':cid,'request_id':str(uuid.uuid4()),'message':message,'action':action,'pin':pin})

def landmark(name):
    l=next(l for l in LANDMARKS if l['name']==name)
    return {'lat':l['lat'],'lng':l['lng'],'detail':'Beside the entrance'}

def test_pinned_report_persists_and_skips_location_question(client):
    p=landmark('E-Library');cid=str(uuid.uuid4())
    r=chat(client,cid,'A broken streetlight',pin=p)
    assert r.status_code==200,r.text
    assert r.json()['phase']=='review'
    assert r.json()['draft']['pin']==p
    t=chat(client,cid,action='submit',pin=p).json()['ticket']
    assert t['latitude']==p['lat'] and t['longitude']==p['lng']
    assert t['location_detail']==p['detail']

def test_nearby_duplicate_uses_distance_not_name(client):
    p=landmark('Main Gate');p['lat']+=0.0002;cid=str(uuid.uuid4())
    r=chat(client,cid,'A broken streetlight',pin=p)
    assert r.json()['phase']=='duplicate'
    assert any('120 m' in e['detail'] for e in r.json()['trace'])
    assert chat(client,cid,action='link',pin=p).json()['ticket']['location']=='Main Gate'

def test_far_report_is_not_a_candidate(client):
    cid=str(uuid.uuid4());p=landmark('Mega Mess (Chaitanya)')
    assert chat(client,cid,'Streetlight is out',pin=p).json()['phase']=='review'

def test_outside_area_rejected(client):
    r=chat(client,str(uuid.uuid4()),'A pothole',pin={'lat':12.9,'lng':74.8,'detail':''})
    assert r.status_code==422

def test_changed_pin_requires_new_review(client):
    cid=str(uuid.uuid4());p=landmark('E-Library')
    assert chat(client,cid,'A broken streetlight',pin=p).json()['phase']=='review'
    assert chat(client,cid,action='submit',pin=landmark('Main Gate')).status_code==409
    assert chat(client,cid,'Use this new pin',pin=landmark('Main Gate')).json()['phase']=='duplicate'

def test_migration_is_idempotent_and_preserves_old_records(client):
    before=client.get('/api/tickets').json()
    db.init_campus();db.init_campus()
    after=client.get('/api/tickets').json()
    assert len(before)==len(after)==10
    assert next(t for t in after if t['id']==1)['latitude'] is None
    assert len([t for t in after if t['latitude'] is not None])==4

def test_distance():
    assert distance_m(13,74,13,74)==0
    assert 110<distance_m(13,74,13.001,74)<112
