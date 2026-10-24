import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import db


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'test.db'))
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.setenv('AUTH_REQUIRED','false')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with TestClient(app) as c:
        c.get('/api/bootstrap')
        yield c


def talk(c,conversation,message='',action=None,request_id=None):
    return c.post('/api/chat',json={'conversation_id':conversation,'message':message,'action':action,'request_id':request_id or str(uuid.uuid4())})


def create(c,message='There is garbage outside Hostel 1'):
    conversation=str(uuid.uuid4())
    r=talk(c,conversation,message)
    assert r.status_code==200,r.text
    assert r.json()['phase']=='review'
    r=talk(c,conversation,action='submit')
    assert r.status_code==200,r.text
    return r.json()['ticket']


def test_clarification_persistence_and_idempotency(client):
    conversation=str(uuid.uuid4())
    r=talk(client,conversation,'There is garbage piling up')
    assert r.json()['phase']=='clarify'
    assert 'Where' in r.json()['message']
    r=talk(client,conversation,'Hostel 1')
    assert r.json()['phase']=='review'
    key=str(uuid.uuid4())
    first=talk(client,conversation,action='submit',request_id=key)
    retry=talk(client,conversation,action='submit',request_id=key)
    assert first.json()==retry.json()
    assert first.json()['ticket']['mine']
    assert len(client.get('/api/tickets').json())==11
    assert talk(client,conversation,action='submit').status_code==409


def test_duplicate_requires_confirmation(client):
    conversation=str(uuid.uuid4())
    r=talk(client,conversation,'The streetlight at Hostel 3 rear gate is broken')
    assert r.json()['phase']=='duplicate'
    assert len(client.get('/api/tickets').json())==10
    r=talk(client,conversation,action='link')
    assert r.json()['ticket']['id']==1
    assert r.json()['ticket']['reports']==2
    assert len(client.get('/api/tickets').json())==10


def test_separate_issue_does_not_merge(client):
    conversation=str(uuid.uuid4())
    assert talk(client,conversation,'Streetlight out at Hostel 3 front entrance').json()['phase']=='duplicate'
    assert talk(client,conversation,action='separate').json()['phase']=='review'
    r=talk(client,conversation,action='submit')
    assert r.json()['ticket']['id']!=1


def test_cannot_bypass_confirmation(client):
    assert talk(client,str(uuid.uuid4()),action='submit').status_code==409
    assert talk(client,str(uuid.uuid4()),'   ').status_code==422


def test_operator_gate_and_repair_verification(client):
    t=create(client)
    path=f"/api/tickets/{t['id']}"
    assert client.patch(path,json={'status':'In progress','note':'Team dispatched'}).status_code==403
    client.post('/api/demo/operator')
    assert client.patch(path,json={'status':'Awaiting verification','note':'Already done'}).status_code==409
    assert client.patch(path,json={'status':'In progress','note':'Team dispatched'}).status_code==200
    assert client.patch(path,json={'status':'Awaiting verification','note':'Bins have been cleared'}).status_code==200
    r=client.post(path+'/verify',json={'fixed':False})
    assert r.json()['status']=='In progress'
    client.patch(path,json={'status':'Awaiting verification','note':'Second inspection completed'})
    assert client.post(path+'/verify',json={'fixed':True}).json()['status']=='Resolved'


def test_another_resident_cannot_verify_or_resume(client):
    conversation=str(uuid.uuid4())
    talk(client,conversation,'Rubbish at Hostel 1')
    with TestClient(app) as other:
        other.get('/api/bootstrap')
        assert talk(other,conversation,action='submit').status_code==403
        assert other.post('/api/tickets/3/verify',json={'fixed':True}).status_code==403


def test_followup_approval_and_clock(client):
    client.post('/api/demo/operator')
    result=client.post('/api/demo/advance').json()
    assert result['flagged']>0
    r=client.post('/api/tickets/1/followup',json={'note':'The crew could not find the location.'})
    assert 'Request location details' in r.json()['proposal']
    approved=client.post('/api/tickets/1/approve').json()
    assert approved['proposal'] is None
    assert 'Request location details' in approved['followup']
    assert client.post('/api/tickets/1/approve').status_code==409


def test_model_failure_rolls_back(client,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    def fail(*a,**kw):raise RuntimeError('unavailable')
    monkeypatch.setattr('backend.agent.model_json',fail)
    assert talk(client,str(uuid.uuid4()),'Garbage at Hostel 1').status_code==503
    assert len(client.get('/api/tickets').json())==10


def test_foreign_origin_rejected(client):
    assert client.post('/api/demo/operator',headers={'origin':'https://other.example'}).status_code==403


def test_unknown_location_not_invented(client):
    r=talk(client,str(uuid.uuid4()),'Garbage outside an unknown building')
    assert r.json()['phase']=='clarify'
    assert r.json()['draft']['location'] is None


def test_new_ticket_after_time_advance_is_not_immediately_overdue(client):
    client.post('/api/demo/operator')
    client.post('/api/demo/advance')
    client.post('/api/demo/advance')
    t=create(client)
    assert not t['overdue']


def test_gemini_adapter_uses_validated_output(client,monkeypatch):
    from backend.agent import Interpretation, Match
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    def fake_model(prompt,schema):
        if schema is Interpretation:
            return Interpretation(intent='complaint',category='Lighting',location='Hostel 3',title='Light near rear gate is out')
        return Match(ticket_id=99999,explanation='Invalid candidate must not be accepted')
    monkeypatch.setattr('backend.agent.model_json',fake_model)
    conversation=str(uuid.uuid4())
    r=talk(client,conversation,'The rear entrance is dark')
    assert r.json()['mode']=='gemini'
    assert r.json()['phase']=='review'
    assert talk(client,conversation,action='submit').json()['ticket']['category']=='Lighting'
