import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import agent,db

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'evaluation.db'))
    monkeypatch.setenv('AUTH_REQUIRED','false')
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with TestClient(app) as c:
        c.get('/api/bootstrap')
        yield c

def talk(c,text='',cid='test',action=None):
    return c.post('/api/chat',json={'conversation_id':cid,'request_id':str(uuid.uuid4()),'message':text,'action':action})

def test_ambiguous_surface_never_guesses_category(client,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:pytest.fail('Ambiguous wet surface must be clarified before calling Gemini'))
    r=talk(client,'It is wet near the stairs again.').json()
    assert r['phase']=='clarify' and r['draft']['category'] is None
    assert 'leaking' in r['message']
    assert talk(client,action='submit').status_code==409

@pytest.mark.parametrize('text',['cancel that','Never mind, cancel that. The cleaners have already removed it.','please cancel my report'])
def test_cancel_clears_draft_even_without_model(client,monkeypatch,text):
    assert talk(client,'Garbage outside Hostel 1').json()['phase']=='review'
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:pytest.fail('Cancellation should not need model availability'))
    r=talk(client,text).json()
    assert r['phase']=='blocked' and r['draft']['category'] is None
    assert talk(client,action='submit').status_code==409
    monkeypatch.delenv('GEMINI_API_KEY')
    # No old location may bleed into the next report.
    r=talk(client,'There is a blocked drain').json()
    assert r['phase']=='clarify' and r['draft']['location'] is None

@pytest.mark.parametrize('intent',['resolved','cancel','unsupported','unrelated'])
def test_model_rejection_clears_previous_review(client,monkeypatch,intent):
    talk(client,'Garbage outside Hostel 1')
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent=intent,category='Waste',location='Hostel 1'))
    r=talk(client,'New information').json()
    assert r['phase']=='blocked' and r['draft']['category'] is None
    assert talk(client,action='submit').status_code==409

@pytest.mark.parametrize('code,status',[(429,429),(500,503)])
def test_provider_failure_invalidates_old_draft_and_retries(client,monkeypatch,code,status):
    talk(client,'Garbage outside Hostel 1')
    class ProviderError(Exception):pass
    e=ProviderError('secret provider payload');e.code=code
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    def fail(*a,**kw):raise e
    monkeypatch.setattr(agent,'model_json',fail)
    r=talk(client,'Actually the problem is at Hostel 2')
    assert r.status_code==status and 'secret' not in r.text
    if code==429:assert r.headers['retry-after']=='60' and 'usage limit' in r.text
    assert talk(client,action='submit').status_code==409
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='clarification',category='Waste',location='Hostel 2',title='Overflowing bins'))
    assert talk(client,'Actually the problem is at Hostel 2').json()['phase']=='review'
    with db.connect() as c:assert c.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]==10

def test_issue_question_is_not_overwritten_with_location_question(client,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='complaint',category='Drainage',question='Is there a leak or a spill?',needs_details=True))
    r=talk(client,'Water everywhere').json()
    assert r['message']=='Is there a leak or a spill?' and r['draft']['category'] is None
    assert talk(client,action='submit').status_code==409

def test_location_correction_replaces_old_draft(client,monkeypatch):
    talk(client,'Garbage outside Hostel 1')
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='clarification',category='Waste',location='Hostel 2',title='Overflowing bins at Hostel 2'))
    r=talk(client,'Sorry, Hostel 2, not Hostel 1.').json()
    assert r['draft']['location']=='Hostel 2'
    assert talk(client,action='submit').json()['ticket']['location']=='Hostel 2'

def test_hazard_does_not_claim_emergency_dispatch(client):
    r=talk(client,'Sparks and smoke from a broken streetlight at Hostel 1').json()
    assert 'Keep away' in r['message'] and 'does not dispatch' in r['message']
    assert r['ticket'] is None


def test_location_question_keeps_known_category_for_followup(client,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    replies=iter([
        agent.Interpretation(intent='complaint',category='Drainage',question='Where is the overflowing drain?',needs_details=True),
        agent.Interpretation(intent='clarification',category='Drainage',location='Hostel 1',title='Overflowing drain')])
    monkeypatch.setattr(agent,'model_json',lambda *a:next(replies))
    assert talk(client,'The drain is overflowing').json()['draft']['category']=='Drainage'
    assert talk(client,'Hostel 1').json()['phase']=='review'


def test_unrelated_model_question_does_not_create_a_draft(client,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='unclear',question='How can I help you?'))
    assert talk(client,'If something breaks next month?').json()['phase']=='blocked'
    assert talk(client,action='submit').status_code==409


@pytest.mark.parametrize('code,status',[(429,429),(500,503)])
def test_photo_provider_error_is_safe_and_saves_no_photo(client,monkeypatch,code,status):
    import io
    from PIL import Image
    from backend import photos
    raw=io.BytesIO();Image.new('RGB',(20,20),'white').save(raw,format='JPEG')
    class ProviderError(Exception):pass
    e=ProviderError('private provider diagnostic');e.code=code
    def fail(*a,**kw):raise e
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(photos,'model_json',fail)
    r=client.post('/api/photos',content=raw.getvalue(),headers={'content-type':'image/jpeg'})
    assert r.status_code==status and 'private provider' not in r.text
    with db.connect() as c:assert c.execute('SELECT COUNT(*) FROM photos').fetchone()[0]==0


def test_canonical_description_replaces_superseded_facts(client,monkeypatch):
    talk(client,'Garbage outside Hostel 1')
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    summary='Overflowing bin outside Hostel 2, beside the entrance.'
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='clarification',category='Waste',location='Hostel 2',title='Overflowing bin',description=summary))
    r=talk(client,'Actually Hostel 2, beside the entrance.').json()
    assert r['draft']['description']==summary
    t=talk(client,action='submit').json()['ticket']
    assert t['description']==summary and 'Hostel 1' not in t['description']


@pytest.mark.parametrize('message',['Cancel the garbage one, report the broken light instead.','Never mind, report the broken light instead.'])
def test_partial_cancellation_is_interpreted_not_discarded(client,monkeypatch,message):
    talk(client,'Garbage outside Hostel 1')
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='complaint',category='Lighting',location='Hostel 1',title='Broken lamp',description='Broken lamp outside Hostel 1'))
    r=talk(client,message).json()
    assert r['phase']=='review' and r['draft']['category']=='Lighting'


def test_pin_conflict_blocks_submission_until_pin_rechecked(client,monkeypatch):
    from backend.geo import LANDMARKS
    pin={k:LANDMARKS[0][k] for k in ('lat','lng')};pin['detail']=''
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='complaint',category='Waste',location='Hostel 2',pin_conflict=True))
    r=client.post('/api/chat',json={'conversation_id':'test','request_id':str(uuid.uuid4()),'message':'Garbage at another location','pin':pin})
    assert r.json()['phase']=='clarify' and r.json()['draft']['location'] is None
    assert talk(client,action='submit').status_code==409


def test_removing_pin_during_submit_requires_review(client):
    from backend.geo import LANDMARKS
    l=next(l for l in LANDMARKS if l['name']=='E-Library');pin={'lat':l['lat'],'lng':l['lng'],'detail':''}
    r=client.post('/api/chat',json={'conversation_id':'test','request_id':str(uuid.uuid4()),'message':'A broken streetlight','pin':pin})
    assert r.json()['phase']=='review'
    r=client.post('/api/chat',json={'conversation_id':'test','request_id':str(uuid.uuid4()),'action':'submit','pin':None})
    assert r.status_code==409


def test_removing_photo_during_submit_requires_review(client):
    import io
    from PIL import Image
    raw=io.BytesIO();Image.new('RGB',(20,20),'white').save(raw,format='JPEG')
    photo=client.post('/api/photos',content=raw.getvalue(),headers={'content-type':'image/jpeg'}).json()
    r=client.post('/api/chat',json={'conversation_id':'test','request_id':str(uuid.uuid4()),'message':'Garbage outside Hostel 1','photo_id':photo['id']})
    assert r.json()['phase']=='review'
    r=client.post('/api/chat',json={'conversation_id':'test','request_id':str(uuid.uuid4()),'action':'submit','photo_id':None})
    assert r.status_code==409


def test_geographic_conflict_is_caught_even_when_model_misses_it(client,monkeypatch):
    from backend.geo import LANDMARKS
    gate=next(l for l in LANDMARKS if l['name']=='Main Gate')
    library=next(l for l in LANDMARKS if l['name']=='E-Library')
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setattr(agent,'model_json',lambda *a:agent.Interpretation(intent='complaint',category='Waste',location='E-Library',description='Garbage outside E-Library',pin_conflict=False))
    def send(pin):
        return client.post('/api/chat',json={'conversation_id':'test','request_id':str(uuid.uuid4()),'message':'Garbage outside E-Library','pin':{'lat':pin['lat'],'lng':pin['lng'],'detail':''}})
    assert send(gate).json()['phase']=='clarify'
    assert talk(client,action='submit').status_code==409
    assert send(library).json()['phase']=='review'
