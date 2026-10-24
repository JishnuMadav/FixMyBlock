import io
import json
import uuid
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend import auth, db, staff, photos, agent
from backend.main import app

PASSWORD='Test-password-long-enough'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'features.db'))
    monkeypatch.setenv('AUTH_REQUIRED','true')
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.setenv('WORKOS_OPERATOR_EMAILS','')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setattr(auth,'workos',lambda path,payload:{'user':{'id':payload['email'],'email':payload['email'],'email_verified':True}})
    with TestClient(app) as c:
        with db.connect() as conn:
            for uid,role,team in [('admin','admin',None),('electrical','team','Electrical team'),('plumbing','team','Plumbing team')]:
                conn.execute('INSERT INTO staff_accounts(id,username,name,role,team,password_hash,must_change,created_at) VALUES(?,?,?,?,?,?,0,?)',(uid,uid,uid,role,team,staff.hash_password(PASSWORD),db.now()))
        yield c

def login(c,user='admin',password=PASSWORD):
    return c.post('/api/staff/login',json={'username':user,'password':password})

def student(c,name='student'):
    assert c.post('/api/auth/verify',json={'email':name+'@nitk.edu.in','code':'123456'}).status_code==200

def talk(c,text='',cid='conversation',action=None,photo_id=None):
    return c.post('/api/chat',json={'conversation_id':cid,'request_id':str(uuid.uuid4()),'message':text,'action':action,'photo_id':photo_id})

def image_bytes():
    out=io.BytesIO();im=Image.new('RGB',(60,40),'green');exif=Image.Exif();exif[270]='private metadata';im.save(out,'JPEG',exif=exif)
    return out.getvalue()

def upload(c):return c.post('/api/photos',content=image_bytes(),headers={'content-type':'image/jpeg'})

def test_team_scope_all_mutations_and_admin_access(client):
    assert login(client,'electrical').status_code==200
    data=client.get('/api/tickets').json()
    assert data and all(t['team']=='Electrical team' for t in data)
    with db.connect() as c:other=c.execute("SELECT id FROM tickets WHERE team='Plumbing team' LIMIT 1").fetchone()[0]
    assert client.patch(f'/api/tickets/{other}',json={'status':'In progress','note':'Inspecting now'}).status_code==403
    assert client.post(f'/api/tickets/{other}/followup',json={'note':'Need more location details'}).status_code==403
    assert client.post(f'/api/tickets/{other}/approve').status_code==403
    assert client.post('/api/demo/advance').status_code==403
    assert client.get('/api/staff/accounts').status_code==403
    assert talk(client,'garbage at Hostel 1').status_code==403
    assert client.patch(f"/api/tickets/{data[0]['id']}",json={'status':'In progress','note':'Inspecting now'}).status_code==200
    assert login(client).status_code==200
    assert len(client.get('/api/tickets').json())==10
    assert client.get('/api/staff/summary').status_code==200

def test_create_password_change_reset_disable(client):
    login(client)
    body={'username':'new.desk','name':'Electrical desk','team':'Electrical team'}
    created=client.post('/api/staff/accounts',json=body)
    assert created.status_code==200
    temporary=created.json()['temporary_password']
    assert len(temporary)>=20
    accounts=client.get('/api/staff/accounts').json();row=next(a for a in accounts if a['username']=='new.desk')
    assert 'password_hash' not in row and temporary not in json.dumps(accounts)
    assert client.post('/api/staff/accounts',json=body).status_code==409
    assert login(client,'new.desk',temporary).status_code==200
    assert client.get('/api/bootstrap').json()['user']['must_change']==1
    assert client.get('/api/tickets').status_code==403
    assert client.post('/api/staff/password',json={'current_password':'wrong','new_password':PASSWORD}).status_code==400
    assert client.post('/api/staff/password',json={'current_password':temporary,'new_password':PASSWORD}).status_code==200
    assert client.get('/api/tickets').status_code==200
    token=client.cookies.get('fmb_auth')
    login(client)
    reset=client.post('/api/staff/accounts/'+row['id'],json={'action':'reset'})
    assert reset.status_code==200 and reset.json()['temporary_password']!=temporary
    with db.connect() as c:assert not c.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?',(auth.digest(token),)).fetchone()
    assert client.post('/api/staff/accounts/'+row['id'],json={'action':'disable'}).status_code==200
    assert login(client,'new.desk',reset.json()['temporary_password']).status_code==401

def test_student_cannot_create_or_manage_staff(client):
    student(client)
    assert client.get('/api/staff/accounts').status_code==403
    assert client.post('/api/staff/accounts',json={'username':'intruder','name':'Bad account','team':'Electrical team'}).status_code==403
    assert client.post('/api/staff/accounts/electrical',json={'action':'reset'}).status_code==403
    assert client.get('/api/staff/summary').status_code==403

@pytest.mark.parametrize('text',['hello','asdfgh qwerty','build me a website','write a poem about garbage','What is the capital of India?','Main Gate'])
def test_unrelated_text_cannot_submit(client,text):
    student(client)
    r=talk(client,text)
    assert r.json()['phase']=='blocked'
    assert not r.json()['choices']
    assert talk(client,action='submit').status_code==409
    assert len(client.get('/api/tickets').json())==10

def test_offtopic_invalidates_previous_review_and_recovers(client):
    student(client)
    assert talk(client,'garbage outside Hostel 1').json()['phase']=='review'
    assert talk(client,'build a website').json()['phase']=='blocked'
    assert talk(client,action='submit').status_code==409
    assert talk(client,'garbage outside Hostel 1').json()['phase']=='review'
    assert talk(client,action='submit').status_code==200

def test_model_intent_cannot_be_overridden_by_category_or_pin(client,monkeypatch):
    student(client)
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='unrelated',category='Waste',location='Hostel 1',title='Invented'))
    assert talk(client,'tell me something').json()['phase']=='blocked'
    assert talk(client,action='submit').status_code==409

def test_photo_validation_privacy_and_metadata(client):
    assert upload(client).status_code==401
    student(client)
    assert client.post('/api/photos',content=b'fake',headers={'content-type':'image/jpeg'}).status_code==422
    assert client.post('/api/photos',content=b'<svg/>',headers={'content-type':'image/svg+xml'}).status_code==415
    assert client.post('/api/photos',content=b'x'*(photos.MAX_BYTES+1),headers={'content-type':'image/jpeg'}).status_code==413
    r=upload(client);assert r.status_code==200
    photo=r.json();assert photo['analysis']['mode']=='demo'
    raw=client.get(photo['url']);assert raw.status_code==200
    with Image.open(io.BytesIO(raw.content)) as im:assert not im.getexif()
    student(client,'other')
    assert client.get(photo['url']).status_code==403
    assert talk(client,'garbage outside Hostel 1',photo_id=photo['id']).status_code==403

def test_photo_attachment_and_assigned_team_access(client,monkeypatch):
    student(client)
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    def observation(prompt,schema,image=None):
        assert image and image.startswith(b'\xff\xd8')
        return photos.Observation(is_issue=True,category='Waste',summary='A pile of rubbish is visible.',uncertainty='Location is not visible.')
    monkeypatch.setattr(photos,'model_json',observation)
    p=upload(client).json()
    assert p['analysis']['mode']=='gemini'
    monkeypatch.delenv('GEMINI_API_KEY')
    assert talk(client,'garbage outside Hostel 1',photo_id=p['id']).json()['phase']=='review'
    ticket=talk(client,action='submit',photo_id=p['id']).json()['ticket']
    assert ticket['photos'][0]['id']==p['id']
    assert client.delete(p['url']).status_code==409
    login(client,'electrical')
    assert client.get(p['url']).status_code==403
    login(client)
    assert client.get(p['url']).status_code==200

def test_new_photo_requires_review(client):
    student(client)
    assert talk(client,'garbage outside Hostel 1').json()['phase']=='review'
    p=upload(client).json()
    assert talk(client,action='submit',photo_id=p['id']).status_code==409
    assert talk(client,'garbage outside Hostel 1',photo_id=p['id']).json()['phase']=='review'
    assert talk(client,action='submit',photo_id=p['id']).status_code==200
