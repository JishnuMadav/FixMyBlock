import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .geo import LANDMARKS

LOCATIONS = ["Hostel 1", "Hostel 2", "Hostel 3", "Central mess", "Library", "Main gate", "Sports ground", "Academic block", "Health centre", "Bus stop"]
LOCATIONS += [l['name'] for l in LANDMARKS if l['name'] not in LOCATIONS]
TEAMS = {"Lighting": "Electrical team", "Waste": "Sanitation team", "Roads": "Grounds team", "Drainage": "Plumbing team"}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    path = Path(os.getenv("DATABASE_PATH", "data/fixmyblock.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def event(db, ticket_id, action, detail, actor="Assistant"):
    db.execute("INSERT INTO events(ticket_id,action,detail,actor,created_at) VALUES(?,?,?,?,?)", (ticket_id, action, detail, actor, now()))


def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS tickets (
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL,
          category TEXT NOT NULL, location TEXT NOT NULL, team TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Assigned', created_at TEXT NOT NULL, due_at TEXT NOT NULL,
          sample INTEGER NOT NULL DEFAULT 0, followup TEXT, proposal TEXT
        );
        CREATE TABLE IF NOT EXISTS reports (
          id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id),
          owner TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(ticket_id,owner)
        );
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id),
          action TEXT NOT NULL, detail TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY,owner TEXT NOT NULL,state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY,owner TEXT NOT NULL,response TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT OR IGNORE INTO settings VALUES('hours','0');
        ''')
        if db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]:
            return
        seeds = [
            ("Streetlight out at the rear gate", "The streetlight at the rear gate of Hostel 3 is not working.", "Lighting", "Hostel 3", "In progress", -26),
            ("Overflowing bins near the dining entrance", "Two bins at the Central mess entrance need collection.", "Waste", "Central mess", "Assigned", -5),
            ("Pothole along the library approach", "A pothole on the approach road outside the Library.", "Roads", "Library", "Awaiting verification", -10),
            ("Blocked drain beside the bus shelter", "Water is collecting in the drain by the Bus stop.", "Drainage", "Bus stop", "Assigned", -3),
            ("Walkway light restored", "The light beside the Academic block entrance was repaired.", "Lighting", "Academic block", "Resolved", -48),
            ("Litter cleared from the field entrance", "Rubbish at the Sports ground entrance was collected.", "Waste", "Sports ground", "Resolved", -36),
        ]
        for title, desc, cat, loc, status, hours in seeds:
            created = datetime.now(timezone.utc) + timedelta(hours=hours)
            cur = db.execute("INSERT INTO tickets(title,description,category,location,team,status,created_at,due_at,sample) VALUES(?,?,?,?,?,?,?,?,1)", (title,desc,cat,loc,TEAMS[cat],status,created.isoformat(),(created+timedelta(hours=24)).isoformat()))
            event(db, cur.lastrowid, "Sample report created", desc, "Demo data")
            event(db, cur.lastrowid, "Assigned to " + TEAMS[cat], "Routed using the campus team directory.")
            if status != "Assigned":
                event(db, cur.lastrowid, status, "Illustrative maintenance update.", TEAMS[cat])


def ticket(db, ticket_id, owner=""):
    row = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["reference"] = f"FMB-{1000+data['id']}"
    data["reports"] = db.execute("SELECT COUNT(*) FROM reports WHERE ticket_id=?", (ticket_id,)).fetchone()[0] + (1 if data["sample"] else 0)
    data["mine"] = bool(db.execute("SELECT 1 FROM reports WHERE ticket_id=? AND owner=?", (ticket_id,owner)).fetchone())
    offset = int(db.execute("SELECT value FROM settings WHERE key='hours'").fetchone()[0])
    data["overdue"] = data["status"] in ("Assigned", "In progress") and datetime.fromisoformat(data["due_at"]) < datetime.now(timezone.utc)+timedelta(hours=offset)
    data["events"] = [dict(e) for e in db.execute("SELECT * FROM events WHERE ticket_id=? ORDER BY id", (ticket_id,))]
    data['photos']=[]
    if owner and db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='photos'").fetchone():
        for p in db.execute('SELECT id,analysis FROM photos WHERE ticket_id=? AND (owner=? OR ?)',(ticket_id,owner,int(owner.startswith('staff:')))):
            data['photos'].append({'id':p['id'],'url':'/api/photos/'+p['id'],'analysis':json.loads(p['analysis'])})
    return data


def init_campus():
    """Additive migration: preserve all existing reports and their history."""
    with connect() as conn:
        columns={r['name'] for r in conn.execute('PRAGMA table_info(tickets)')}
        for name,kind in [('latitude','REAL'),('longitude','REAL'),('location_detail','TEXT')]:
            if name not in columns:
                conn.execute(f'ALTER TABLE tickets ADD COLUMN {name} {kind}')
        if conn.execute("SELECT 1 FROM settings WHERE key='nitk_demo_v1'").fetchone():
            return
        samples=[
            ('Main Gate','Lighting','Streetlight needs attention near Main Gate'),
            ('Mega Mess (Chaitanya)','Waste','Bin collection needed near Mega Mess'),
            ('NITK Central Library','Roads','Uneven path near the Central Library'),
            ('Student Activity Center','Drainage','Drain inspection near the Activity Center'),
        ]
        for name,category,title in samples:
            l=next(l for l in LANDMARKS if l['name']==name)
            created=datetime.now(timezone.utc)
            desc='Fictional demo incident near this mapped landmark. No real fault is asserted.'
            cur=conn.execute('INSERT INTO tickets(title,description,category,location,team,status,created_at,due_at,sample,latitude,longitude,location_detail) VALUES(?,?,?,?,?,?,?,?,1,?,?,?)',
                (title,desc,category,name,TEAMS[category],'Assigned',created.isoformat(),(created+timedelta(hours=24)).isoformat(),l['lat'],l['lng'],'Approximate landmark position — sample incident'))
            event(conn,cur.lastrowid,'NITK demo incident',desc,'Demo data')
        conn.execute("INSERT INTO settings VALUES('nitk_demo_v1','1')")
