# -*- coding: utf-8 -*-
import os
import sqlite3
import time
import secrets
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, jsonify, render_template_string, abort

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "debug_arena.db")
SECRET_KEY = os.environ.get("DEBUG_ARENA_SECRET", "change-this-secret-before-event")
ADMIN_PASSWORD = os.environ.get("DEBUG_ARENA_PASSWORD", "ChangeMe123!")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            college TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 120,
            max_points INTEGER NOT NULL DEFAULT 10,
            sort_order INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
            challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
            points INTEGER NOT NULL DEFAULT 0,
            result TEXT NOT NULL DEFAULT 'Correct',
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(participant_id, challenge_id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS timer_state (
            id INTEGER PRIMARY KEY CHECK(id=1),
            challenge_id INTEGER,
            running INTEGER NOT NULL DEFAULT 0,
            ends_at REAL,
            remaining REAL NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO timer_state(id, running, remaining) VALUES(1,0,0);
        INSERT OR IGNORE INTO settings(key,value) VALUES('event_name','DEBUG ARENA');
        """)
        count = c.execute("SELECT COUNT(*) n FROM challenges").fetchone()["n"]
        if count == 0:
            c.executemany(
                "INSERT INTO challenges(code,title,duration_seconds,max_points,sort_order) VALUES(?,?,?,?,?)",
                [
                    ("BUG-01","Bug #01",120,10,1),
                    ("BUG-02","Bug #02",240,20,2),
                    ("BUG-03","Bug #03",120,10,3),
                ],
            )

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def leaderboard_rows():
    with db() as c:
        return c.execute("""
            SELECT p.id,p.participant_code,p.name,p.college,
                   COALESCE(SUM(s.points),0) total_points,
                   COUNT(CASE WHEN s.result='Correct' AND s.points>0 THEN 1 END) solved,
                   COUNT(s.id) rounds_scored,
                   MIN(s.created_at) first_score
            FROM participants p LEFT JOIN scores s ON p.id=s.participant_id
            GROUP BY p.id
            ORDER BY total_points DESC, solved DESC, first_score ASC, p.name COLLATE NOCASE ASC
        """).fetchall()

def timer_payload():
    with db() as c:
        t = c.execute("""SELECT ts.*, ch.code, ch.title, ch.duration_seconds
                         FROM timer_state ts LEFT JOIN challenges ch ON ch.id=ts.challenge_id
                         WHERE ts.id=1""").fetchone()
    remaining = max(0, (t["ends_at"] - time.time()) if t["running"] and t["ends_at"] else t["remaining"])
    if t["running"] and remaining <= 0:
        with db() as c:
            c.execute("UPDATE timer_state SET running=0, remaining=0, ends_at=NULL WHERE id=1")
        return {"running": False, "remaining": 0, "challenge": t["title"] or "No challenge"}
    return {"running": bool(t["running"]), "remaining": int(remaining + 0.999),
            "challenge": t["title"] or "No challenge", "code": t["code"] or ""}

BASE = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | DEBUG ARENA</title>
<style>
:root{--bg:#090d18;--panel:#111a2b;--panel2:#172238;--line:#263653;--text:#eef4ff;--muted:#9aabc5;--cyan:#54d6ff;--purple:#9b8cff;--green:#4ade80;--red:#fb7185;--gold:#fbbf24}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#182344 0,#090d18 45%);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--cyan);text-decoration:none}button,.btn{border:0;border-radius:10px;padding:10px 14px;background:linear-gradient(120deg,#5267ed,#8b5cf6);color:white;font-weight:700;cursor:pointer;display:inline-block}
button.secondary,.btn.secondary{background:#24334e}button.danger{background:#9f2945}button.green{background:#13784a}
input,select,textarea{width:100%;background:#0c1424;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:10px;margin:4px 0 12px}
label{display:block;color:var(--muted);font-size:13px}.wrap{max-width:1180px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.brand{font-weight:900;letter-spacing:2px;font-size:20px}.brand span{color:var(--cyan)}nav{display:flex;gap:8px;flex-wrap:wrap}.nav a{padding:8px 11px;border:1px solid var(--line);border-radius:9px;color:var(--text);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.cols{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}
.card{background:linear-gradient(145deg,#131e32,#0e1728);border:1px solid var(--line);border-radius:16px;padding:17px;box-shadow:0 10px 35px #0003}
.stat{font-size:28px;font-weight:850}.muted{color:var(--muted)}.small{font-size:12px;color:var(--muted)}
h1{font-size:27px;margin:4px 0 15px}h2{font-size:18px;margin:0 0 13px}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.between{justify-content:space-between}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:11px 9px;border-bottom:1px solid #263653}th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.7px}
.pill{display:inline-block;padding:4px 9px;border-radius:99px;background:#163a36;color:var(--green);font-size:12px;font-weight:700}.pill.red{background:#421d2a;color:#ff9aac}
.flash{padding:11px 14px;background:#193a3c;border:1px solid #2b7775;border-radius:10px;margin-bottom:12px}.actions{display:flex;gap:7px;flex-wrap:wrap}
.timer{font-size:54px;font-weight:900;letter-spacing:2px;text-align:center;color:var(--cyan);font-variant-numeric:tabular-nums}
.rank{font-size:20px;font-weight:900;color:var(--gold)}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
footer{padding:30px 0;text-align:center;color:var(--muted);font-size:12px}
@media(max-width:800px){.grid{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}.wrap{padding:14px}.timer{font-size:42px}}
@media(max-width:480px){.formgrid{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}}
</style></head><body><div class="wrap">
<header class="top"><div class="brand">⚡ DEBUG <span>ARENA</span></div>
{% if session.get('admin') %}<nav class="nav"><a href="{{ url_for('dashboard') }}">Dashboard</a><a href="{{ url_for('participants') }}">Participants</a><a href="{{ url_for('challenges') }}">Challenges</a><a href="{{ url_for('scores') }}">Score Entry</a><a href="{{ url_for('leaderboard') }}">Leaderboard</a><a href="{{ url_for('projector') }}">Projector</a><a href="{{ url_for('logout') }}">Logout</a></nav>{% endif %}</header>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
{{ body|safe }}<footer>DEBUG ARENA · Admin-controlled debugging competition manager</footer></div></body></html>
"""

def page(title, body, **ctx):
    return render_template_string(BASE, title=title, body=render_template_string(body, **ctx), **ctx)

@app.route("/")
def home():
    return redirect(url_for("dashboard") if session.get("admin") else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password",""), ADMIN_PASSWORD):
            session.clear()
            session["admin"] = True
            return redirect(url_for("dashboard"))
        flash("Incorrect admin password.")
    body = """<div style="max-width:420px;margin:9vh auto" class="card"><h1>Admin Login</h1><p class="muted">Only authorized event coordinators can access DEBUG ARENA.</p><form method="post"><label>Admin password</label><input type="password" name="password" required autofocus><button style="width:100%">Secure Login</button></form><p class="small">Change the default password before the event. Do not share admin access.</p></div>"""
    return page("Login", body)

@app.route("/logout")
@admin_required
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@admin_required
def dashboard():
    with db() as c:
        students=c.execute("SELECT COUNT(*) n FROM participants").fetchone()["n"]
        challenges_count=c.execute("SELECT COUNT(*) n FROM challenges WHERE active=1").fetchone()["n"]
        total=c.execute("SELECT COALESCE(SUM(points),0) n FROM scores").fetchone()["n"]
        scores_count=c.execute("SELECT COUNT(*) n FROM scores").fetchone()["n"]
        recent=c.execute("""SELECT p.name,p.participant_code,ch.code,s.points,s.created_at
          FROM scores s JOIN participants p ON p.id=s.participant_id JOIN challenges ch ON ch.id=s.challenge_id
          ORDER BY s.id DESC LIMIT 8""").fetchall()
    t=timer_payload()
    body="""<h1>Competition Control Center</h1><div class="grid">
    <div class="card"><div class="muted">Participants</div><div class="stat">{{students}}</div></div>
    <div class="card"><div class="muted">Active challenges</div><div class="stat">{{challenges_count}}</div></div>
    <div class="card"><div class="muted">Points awarded</div><div class="stat">{{total}}</div></div>
    <div class="card"><div class="muted">Score records</div><div class="stat">{{scores_count}}</div></div></div>
    <div class="cols" style="margin-top:14px"><section class="card"><div class="row between"><h2>Challenge timer</h2><span class="pill" id="timer-status">Ready</span></div>
    <div class="muted" id="timer-challenge">{{t.challenge}}</div><div class="timer" id="timer-value">--:--</div>
    <div class="actions"><form method="post" action="{{url_for('timer_action')}}"><input type="hidden" name="action" value="pause"><button class="secondary">Pause</button></form>
    <form method="post" action="{{url_for('timer_action')}}"><input type="hidden" name="action" value="resume"><button class="secondary">Resume</button></form>
    <form method="post" action="{{url_for('timer_action')}}"><input type="hidden" name="action" value="reset"><button class="danger">Reset</button></form></div>
    <p class="small">Choose and start a challenge from the Challenges page. Timer is shared across the admin dashboard.</p></section>
    <section class="card"><h2>Quick actions</h2><div class="actions"><a class="btn" href="{{url_for('participants')}}">+ Add participant</a><a class="btn" href="{{url_for('scores')}}">+ Enter score</a><a class="btn secondary" href="{{url_for('challenges')}}">Manage challenges</a><a class="btn secondary" href="{{url_for('projector')}}">Open projector</a></div><hr style="border-color:#263653;margin:18px 0"><h2>Competition rules</h2><p class="muted">All participants receive the same challenge in each round. Admin records points individually. Highest cumulative score wins.</p></section></div>
    <section class="card" style="margin-top:14px"><h2>Recent score entries</h2>{% if recent %}<table><tr><th>Participant</th><th>Challenge</th><th>Points</th><th>Time</th></tr>{% for r in recent %}<tr><td>{{r.name}} <span class="small">({{r.participant_code}})</span></td><td>{{r.code}}</td><td><b>{{r.points}}</b></td><td>{{r.created_at}}</td></tr>{% endfor %}</table>{% else %}<p class="muted">No scores recorded yet.</p>{% endif %}</section>
    <script>
    async function refreshTimer(){let r=await fetch('{{url_for("timer_api")}}');let t=await r.json();let s=t.remaining;document.getElementById('timer-value').textContent=String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');document.getElementById('timer-status').textContent=t.running?'RUNNING':'PAUSED / READY';document.getElementById('timer-challenge').textContent=t.challenge;}
    refreshTimer();setInterval(refreshTimer,500);
    </script>"""
    return page("Dashboard",body,students=students,challenges_count=challenges_count,total=total,scores_count=scores_count,recent=recent,t=t)

@app.route("/participants", methods=["GET","POST"])
@admin_required
def participants():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        college=request.form.get("college","").strip()
        code=request.form.get("code","").strip().upper()
        if not name or not college:
            flash("Student name and college are required.")
        else:
            with db() as c:
                if not code:
                    last=c.execute("SELECT COALESCE(MAX(id),0)+1 n FROM participants").fetchone()["n"]
                    code=f"DBG{last:03d}"
                try:
                    c.execute("INSERT INTO participants(participant_code,name,college) VALUES(?,?,?)",(code,name,college))
                    flash(f"Participant {code} added.")
                except sqlite3.IntegrityError:
                    flash("Participant ID already exists. Use a unique ID.")
        return redirect(url_for("participants"))
    with db() as c: rows=c.execute("SELECT p.*,COALESCE(SUM(s.points),0) points FROM participants p LEFT JOIN scores s ON p.id=s.participant_id GROUP BY p.id ORDER BY p.id DESC").fetchall()
    body="""<h1>Participant Registration</h1><div class="cols"><section class="card"><h2>Add participant</h2><form method="post"><label>Student name *</label><input name="name" required><label>College name *</label><input name="college" required><label>Participant ID (leave blank for automatic ID)</label><input name="code" placeholder="e.g. DBG001"><button>Add participant</button></form></section>
    <section class="card"><h2>Registration summary</h2><div class="stat">{{rows|length}}</div><p class="muted">Registered participants</p><p class="small">Tip: use the same participant ID on score sheets and during result entry.</p></section></div>
    <section class="card" style="margin-top:14px"><h2>Registered participants</h2><input id="filter" placeholder="Search by student, college or ID" oninput="filterRows()"><table id="people"><tr><th>ID</th><th>Student</th><th>College</th><th>Points</th><th>Action</th></tr>{% for p in rows %}<tr><td>{{p.participant_code}}</td><td>{{p.name}}</td><td>{{p.college}}</td><td>{{p.points}}</td><td><form method="post" action="{{url_for('delete_participant',pid=p.id)}}" onsubmit="return confirm('Delete participant and all their scores?')"><button class="danger">Delete</button></form></td></tr>{% endfor %}</table></section>
    <script>function filterRows(){let q=document.getElementById('filter').value.toLowerCase();document.querySelectorAll('#people tr:not(:first-child)').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none')}</script>"""
    return page("Participants",body,rows=rows)

@app.route("/participants/<int:pid>/delete",methods=["POST"])
@admin_required
def delete_participant(pid):
    with db() as c:c.execute("DELETE FROM participants WHERE id=?",(pid,))
    flash("Participant and associated score records deleted.")
    return redirect(url_for("participants"))

@app.route("/challenges",methods=["GET","POST"])
@admin_required
def challenges():
    if request.method=="POST":
        code=request.form.get("code","").strip().upper()
        title=request.form.get("title","").strip()
        try:
            duration=int(request.form.get("duration","120"))
            points=int(request.form.get("points","10"))
            if not code or not title or duration<1 or points<0: raise ValueError()
            with db() as c:
                order=c.execute("SELECT COALESCE(MAX(sort_order),0)+1 n FROM challenges").fetchone()["n"]
                c.execute("INSERT INTO challenges(code,title,duration_seconds,max_points,sort_order) VALUES(?,?,?,?,?)",(code,title,duration,points,order))
            flash("Challenge added.")
        except (ValueError,sqlite3.IntegrityError):
            flash("Please enter valid details. Challenge code must be unique.")
        return redirect(url_for("challenges"))
    with db() as c: rows=c.execute("SELECT * FROM challenges ORDER BY sort_order,id").fetchall()
    body="""<h1>Challenge & Round Management</h1><div class="cols"><section class="card"><h2>Add challenge</h2><form method="post"><label>Challenge code *</label><input name="code" placeholder="BUG-04" required><label>Challenge title *</label><input name="title" placeholder="Bug #04" required><div class="formgrid"><div><label>Timer (seconds)</label><input type="number" name="duration" value="120" min="1" required></div><div><label>Maximum points (reference)</label><input type="number" name="points" value="10" min="0" required></div></div><button>Add challenge</button></form></section>
    <section class="card"><h2>Round instructions</h2><p class="muted">All students receive the same bug code in a round. Start its timer here. When time ends, move to the next challenge.</p><p class="small">Points are entered manually on the Score Entry page. The maximum points field is a reference; manual scoring remains in your control.</p></section></div>
    <section class="card" style="margin-top:14px"><h2>Challenges</h2><table><tr><th>Code</th><th>Title</th><th>Duration</th><th>Max points</th><th>Timer</th><th>Delete</th></tr>{% for ch in rows %}<tr><td>{{ch.code}}</td><td>{{ch.title}}</td><td>{{ch.duration_seconds//60}}m {{ch.duration_seconds%60}}s</td><td>{{ch.max_points}}</td><td><form method="post" action="{{url_for('timer_action')}}"><input type="hidden" name="action" value="start"><input type="hidden" name="challenge_id" value="{{ch.id}}"><button class="green">Start round</button></form></td><td><form method="post" action="{{url_for('delete_challenge',cid=ch.id)}}" onsubmit="return confirm('Delete challenge and all associated scores?')"><button class="danger">Delete</button></form></td></tr>{% endfor %}</table></section>"""
    return page("Challenges",body,rows=rows)

@app.route("/challenges/<int:cid>/delete",methods=["POST"])
@admin_required
def delete_challenge(cid):
    with db() as c:c.execute("DELETE FROM challenges WHERE id=?",(cid,))
    flash("Challenge and associated scores deleted.")
    return redirect(url_for("challenges"))

@app.route("/timer/action",methods=["POST"])
@admin_required
def timer_action():
    action=request.form.get("action")
    with db() as c:
        t=c.execute("SELECT * FROM timer_state WHERE id=1").fetchone()
        if action=="start":
            cid=request.form.get("challenge_id",type=int)
            ch=c.execute("SELECT * FROM challenges WHERE id=?",(cid,)).fetchone()
            if ch:
                c.execute("UPDATE timer_state SET challenge_id=?,running=1,ends_at=?,remaining=? WHERE id=1",(cid,time.time()+ch["duration_seconds"],ch["duration_seconds"]))
                flash(f"{ch['title']} timer started.")
        elif action=="pause" and t["running"]:
            rem=max(0,t["ends_at"]-time.time())
            c.execute("UPDATE timer_state SET running=0,remaining=?,ends_at=NULL WHERE id=1",(rem,))
            flash("Timer paused.")
        elif action=="resume" and not t["running"] and t["challenge_id"] and t["remaining"]>0:
            c.execute("UPDATE timer_state SET running=1,ends_at=? WHERE id=1",(time.time()+t["remaining"],))
            flash("Timer resumed.")
        elif action=="reset":
            c.execute("UPDATE timer_state SET running=0,remaining=0,ends_at=NULL WHERE id=1")
            flash("Timer reset.")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/api/timer")
@admin_required
def timer_api():
    return jsonify(timer_payload())

@app.route("/scores",methods=["GET","POST"])
@admin_required
def scores():
    if request.method=="POST":
        pid=request.form.get("participant_id",type=int)
        cid=request.form.get("challenge_id",type=int)
        points=request.form.get("points",type=int)
        result=request.form.get("result","Correct")
        note=request.form.get("note","").strip()
        if points is None or points<0 or result not in ("Correct","Incorrect","Not attempted"):
            flash("Enter a valid non-negative point value and result.")
        else:
            with db() as c:
                try:
                    c.execute("INSERT INTO scores(participant_id,challenge_id,points,result,note) VALUES(?,?,?,?,?)",(pid,cid,points,result,note))
                    flash("Score saved and leaderboard updated.")
                except sqlite3.IntegrityError:
                    flash("A score already exists for this participant and challenge. Use Edit to correct it.")
        return redirect(url_for("scores"))
    with db() as c:
        people=c.execute("SELECT * FROM participants ORDER BY name COLLATE NOCASE").fetchall()
        challenges=c.execute("SELECT * FROM challenges ORDER BY sort_order,id").fetchall()
        records=c.execute("""SELECT s.*,p.name,p.participant_code,ch.code FROM scores s JOIN participants p ON p.id=s.participant_id JOIN challenges ch ON ch.id=s.challenge_id ORDER BY s.id DESC LIMIT 30""").fetchall()
    body="""<h1>Manual Score Entry</h1><div class="cols"><section class="card"><h2>Record participant result</h2>{% if people and challenges %}<form method="post"><label>Select participant *</label><select name="participant_id" required>{% for p in people %}<option value="{{p.id}}">{{p.participant_code}} — {{p.name}} ({{p.college}})</option>{% endfor %}</select><label>Select challenge *</label><select name="challenge_id" required>{% for ch in challenges %}<option value="{{ch.id}}">{{ch.code}} — {{ch.title}}</option>{% endfor %}</select><div class="formgrid"><div><label>Points earned *</label><input type="number" name="points" min="0" value="10" required></div><div><label>Result</label><select name="result"><option>Correct</option><option>Incorrect</option><option>Not attempted</option></select></div></div><label>Admin note (optional)</label><input name="note" placeholder="e.g. verified by judge"><button>Save score</button></form>{% else %}<p class="muted">Add at least one participant and one challenge first.</p>{% endif %}</section>
    <section class="card"><h2>Scoring rules</h2><p class="muted">Points are manually assigned by the admin. The app adds each new challenge score to the participant's cumulative total.</p><ul class="muted"><li>One score per participant per challenge.</li><li>Duplicate entries are blocked.</li><li>Corrections can be made from the score history.</li><li>Leaderboard updates immediately after saving.</li></ul></section></div>
    <section class="card" style="margin-top:14px"><h2>Recent score records</h2><table><tr><th>Participant</th><th>Challenge</th><th>Result</th><th>Points</th><th>Note</th><th>Action</th></tr>{% for s in records %}<tr><td>{{s.participant_code}} · {{s.name}}</td><td>{{s.code}}</td><td>{{s.result}}</td><td><b>{{s.points}}</b></td><td>{{s.note}}</td><td><a href="{{url_for('edit_score',sid=s.id)}}">Edit</a> · <form style="display:inline" method="post" action="{{url_for('delete_score',sid=s.id)}}" onsubmit="return confirm('Delete this score?')"><button class="danger">Delete</button></form></td></tr>{% endfor %}</table></section>"""
    return page("Score Entry",body,people=people,challenges=challenges,records=records)

@app.route("/scores/<int:sid>/edit",methods=["GET","POST"])
@admin_required
def edit_score(sid):
    with db() as c:
        s=c.execute("SELECT * FROM scores WHERE id=?",(sid,)).fetchone()
        if not s: abort(404)
        if request.method=="POST":
            points=request.form.get("points",type=int)
            result=request.form.get("result","Correct")
            note=request.form.get("note","").strip()
            if points is None or points<0 or result not in ("Correct","Incorrect","Not attempted"):
                flash("Invalid score.")
            else:
                c.execute("UPDATE scores SET points=?,result=?,note=? WHERE id=?",(points,result,note,sid))
                flash("Score corrected.")
            return redirect(url_for("scores"))
    body="""<div class="card" style="max-width:520px"><h1>Edit score</h1><form method="post"><label>Points</label><input type="number" name="points" min="0" value="{{s.points}}" required><label>Result</label><select name="result"><option {% if s.result=='Correct' %}selected{% endif %}>Correct</option><option {% if s.result=='Incorrect' %}selected{% endif %}>Incorrect</option><option {% if s.result=='Not attempted' %}selected{% endif %}>Not attempted</option></select><label>Note</label><input name="note" value="{{s.note}}"><button>Save correction</button> <a class="btn secondary" href="{{url_for('scores')}}">Cancel</a></form></div>"""
    return page("Edit Score",body,s=s)

@app.route("/scores/<int:sid>/delete",methods=["POST"])
@admin_required
def delete_score(sid):
    with db() as c:c.execute("DELETE FROM scores WHERE id=?",(sid,))
    flash("Score deleted and leaderboard recalculated.")
    return redirect(url_for("scores"))

@app.route("/leaderboard")
@admin_required
def leaderboard():
    rows=leaderboard_rows()
    body="""<div class="row between"><h1>Live Leaderboard</h1><a class="btn secondary" href="{{url_for('projector')}}">Projector mode</a></div><section class="card"><table id="board"><tr><th>Rank</th><th>Participant</th><th>College</th><th>Challenges scored</th><th>Correct</th><th>Total points</th></tr>{% for p in rows %}<tr><td class="rank">{% if loop.index==1 %}🥇{% elif loop.index==2 %}🥈{% elif loop.index==3 %}🥉{% else %}{{loop.index}}{% endif %}</td><td><b>{{p.name}}</b><div class="small">{{p.participant_code}}</div></td><td>{{p.college}}</td><td>{{p.rounds_scored}}</td><td>{{p.solved}}</td><td><b>{{p.total_points}}</b></td></tr>{% endfor %}</table>{% if not rows %}<p class="muted">Register participants to populate the leaderboard.</p>{% endif %}</section>
    <script>setInterval(()=>location.reload(),10000)</script>"""
    return page("Leaderboard",body,rows=rows)

@app.route("/projector")
@admin_required
def projector():
    body="""<style>.wrap{max-width:1500px}.projector h1{font-size:42px;text-align:center}.projector .timer{font-size:68px}.projector td,.projector th{font-size:20px;padding:16px}</style><div class="projector"><h1>🏆 DEBUG ARENA LEADERBOARD</h1><div class="card" style="max-width:500px;margin:0 auto 20px;text-align:center"><div id="pc" class="muted">Current challenge</div><div class="timer" id="pt">--:--</div></div><section class="card"><table id="pb"><tr><th>Rank</th><th>Participant</th><th>College</th><th>Points</th></tr></table></section><p class="small" style="text-align:center">Live rankings · Highest cumulative score wins</p></div>
    <script>
    async function update(){let [b,t]=await Promise.all([fetch('{{url_for("leaderboard_api")}}').then(r=>r.json()),fetch('{{url_for("timer_api")}}').then(r=>r.json())]);document.getElementById('pb').innerHTML='<tr><th>Rank</th><th>Participant</th><th>College</th><th>Points</th></tr>'+b.map((p,i)=>'<tr><td>'+(i<3?['🥇','🥈','🥉'][i]:i+1)+'</td><td><b>'+esc(p.name)+'</b><div class="small">'+esc(p.participant_code)+'</div></td><td>'+esc(p.college)+'</td><td><b>'+p.total_points+'</b></td></tr>').join('');let s=t.remaining;document.getElementById('pt').textContent=String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');document.getElementById('pc').textContent=t.challenge+(t.running?' · LIVE':' · PAUSED / READY')}
    function esc(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}update();setInterval(update,2000)
    </script>"""
    return page("Projector",body)

@app.route("/api/leaderboard")
@admin_required
def leaderboard_api():
    return jsonify([dict(r) for r in leaderboard_rows()])

@app.route("/backup")
@admin_required
def backup():
    return abort(404)

if __name__ == "__main__":
    init_db()
    print("\\nDEBUG ARENA starting at http://127.0.0.1:5000")
    print("Default admin password: ChangeMe123!")
    print("Change DEBUG_ARENA_PASSWORD and DEBUG_ARENA_SECRET before the event.\\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
