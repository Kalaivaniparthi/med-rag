"""SQLite schema + helpers + config lookup."""
import json
import os
import secrets
import sqlite3
import string
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data.db"
DISCLAIMER = ("This assistant helps you understand your documents. It is not a doctor. "
              "For medical advice, contact your healthcare provider.")
LANGS = {"English": "en", "Hindi": "hi", "Tamil": "ta", "Telugu": "te", "Spanish": "es",
         "French": "fr", "German": "de", "Arabic": "ar", "Chinese": "zh-CN"}
AUTO = "Auto-detect"

SCHEMA = """
CREATE TABLE IF NOT EXISTS medications(id INTEGER PRIMARY KEY, name TEXT, dose TEXT,
  times_json TEXT, start_date TEXT, end_date TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS med_log(id INTEGER PRIMARY KEY, med_id INTEGER, day TEXT,
  time TEXT, status TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, title TEXT, doctor TEXT,
  datetime TEXT, location TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS diet(id INTEGER PRIMARY KEY, timestamp TEXT, meal_type TEXT,
  description TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS lab_values(id INTEGER PRIMARY KEY, test TEXT, value REAL,
  unit TEXT, date TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, name TEXT UNIQUE, doc_date TEXT,
  kind TEXT, added TEXT, extracted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def q(sql, args=()):
    """Run a SELECT, return list of dicts."""
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def run(sql, args=()):
    """Run a write, return lastrowid."""
    c = _conn()
    try:
        with c:
            return c.execute(sql, args).lastrowid
    finally:
        c.close()


with _conn() as _c:
    _c.executescript(SCHEMA)


# ---------- settings / config ----------
def get_setting(key, default=None):
    r = q("SELECT value FROM settings WHERE key=?", (key,))
    return r[0]["value"] if r else default


def set_setting(key, value):
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))


def cfg(name):
    """GROQ_API_KEY / NTFY_TOPIC: env -> st.secrets -> Settings page (SQLite)."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    v = get_setting(name)
    if not v and name == "NTFY_TOPIC":
        v = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        set_setting(name, v)
    return v


# ---------- medications ----------
def add_med(name, dose="", times=None, start="", end="", notes=""):
    if q("SELECT id FROM medications WHERE lower(name)=lower(?)", (name,)):
        return None
    return run("INSERT INTO medications(name,dose,times_json,start_date,end_date,notes) VALUES(?,?,?,?,?,?)",
               (name, dose, json.dumps(times or []), start, end, notes))


def meds():
    rows = q("SELECT * FROM medications ORDER BY name")
    for r in rows:
        r["times"] = json.loads(r["times_json"] or "[]")
    return rows


def _active(m, day):
    return (not m["start_date"] or m["start_date"] <= day) and (not m["end_date"] or day <= m["end_date"])


def log_dose(med_id, time, status, day=None):
    day = day or date.today().isoformat()
    run("DELETE FROM med_log WHERE med_id=? AND day=? AND time=? AND status!='snoozed'", (med_id, day, time))
    run("INSERT INTO med_log(med_id,day,time,status,ts) VALUES(?,?,?,?,?)",
        (med_id, day, time, status, datetime.now().isoformat(timespec="seconds")))


def dose_status(med_id, time, day=None):
    day = day or date.today().isoformat()
    r = q("SELECT status FROM med_log WHERE med_id=? AND day=? AND time=? ORDER BY id DESC LIMIT 1",
          (med_id, day, time))
    return r[0]["status"] if r else None


def today_schedule():
    today = date.today().isoformat()
    out = [{"med": m, "time": t, "status": dose_status(m["id"], t)}
           for m in meds() if _active(m, today) for t in m["times"]]
    return sorted(out, key=lambda x: x["time"])


def adherence(med):
    """% of scheduled doses taken over the last 7 days (None for as-needed meds)."""
    expected = taken = 0
    for i in range(7):
        day = (date.today() - timedelta(days=i)).isoformat()
        if _active(med, day):
            expected += len(med["times"])
            taken += q("SELECT COUNT(DISTINCT time) n FROM med_log WHERE med_id=? AND day=? AND status='taken'",
                       (med["id"], day))[0]["n"]
    return round(100 * taken / expected) if expected else None


# ---------- appointments / labs ----------
def add_appt(title, doctor="", dt="", location="", notes=""):
    if q("SELECT id FROM appointments WHERE lower(title)=lower(?) AND datetime=?", (title, dt)):
        return None
    return run("INSERT INTO appointments(title,doctor,datetime,location,notes) VALUES(?,?,?,?,?)",
               (title, doctor, dt, location, notes))


def add_lab(test, value, unit, day, source):
    if q("SELECT id FROM lab_values WHERE test=? AND date=? AND source=?", (test, day, source)):
        return None
    return run("INSERT INTO lab_values(test,value,unit,date,source) VALUES(?,?,?,?,?)",
               (test, value, unit, day, source))


# ---------- shared page chrome ----------
CSS = """<style>
:root{--brand:#0d9488;--brand2:#0ea5e9;--ok:#16a34a;--warn:#d97706;--bad:#dc2626;
--card:rgba(127,127,127,.08);--line:rgba(127,127,127,.25)}
.block-container{padding-top:1rem;max-width:1100px}
#MainMenu,footer{visibility:hidden}
header[data-testid=stHeader]{background:transparent}
.ss-hero{background:linear-gradient(120deg,#0d9488,#0ea5e9);color:#fff;border-radius:20px;padding:22px 26px;margin:6px 0 14px;
box-shadow:0 8px 24px rgba(13,148,136,.25)}
.ss-hero .t{font-size:1.7rem;font-weight:800;line-height:1.2}.ss-hero .s{opacity:.92;margin-top:4px;font-size:1rem}
.ss-disc{font-size:.78rem;border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:10px;padding:6px 12px;
margin-bottom:6px;background:var(--card)}
.ss-card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin:8px 0}
.ss-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:6px 0 14px}
.ss-stat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 16px}
.ss-stat .l{font-size:.78rem;opacity:.7;text-transform:uppercase;letter-spacing:.04em}
.ss-stat .v{font-size:1.5rem;font-weight:800}.ss-stat .d{font-size:.8rem;opacity:.75}
.ss-pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:700;color:#fff}
.ss-pill.ok{background:var(--ok)}.ss-pill.warn{background:var(--warn)}.ss-pill.bad{background:var(--bad)}
.ss-pill.idle{background:#64748b}.ss-pill.brand{background:var(--brand)}
.ss-bar{height:10px;border-radius:999px;background:var(--line);overflow:hidden;margin:4px 0 10px}
.ss-bar>i{display:block;height:100%;border-radius:999px}
.ss-date{display:inline-block;text-align:center;min-width:54px;border-radius:12px;padding:6px 8px;color:#fff;
background:linear-gradient(160deg,#0d9488,#0ea5e9);margin-right:12px;vertical-align:middle;line-height:1.1}
.ss-date b{font-size:1.4rem;display:block}.ss-date span{font-size:.7rem;letter-spacing:.08em}
.ss-brand{font-size:1.15rem;font-weight:800;padding:4px 0 10px}.ss-brand span{font-weight:400;font-size:.8rem;opacity:.7}
.clickable{padding:8px 10px;border-radius:8px;margin:2px 0;transition:.2s}
.clickable:hover{background:rgba(13,148,136,.14);box-shadow:0 0 14px rgba(13,148,136,.55)}
div.stButton>button,div.stDownloadButton>button,div[data-testid=stFormSubmitButton]>button{border-radius:12px;font-weight:600}
div.stButton>button:hover{border-color:var(--brand);color:var(--brand)}
.stTabs [data-baseweb=tab]{font-weight:600;padding:8px 14px}
div[data-testid=stVerticalBlockBorderWrapper]{border-radius:16px}
</style>"""


def hero(title, subtitle=""):
    st.markdown(f'<div class="ss-hero"><div class="t">{title}</div><div class="s">{subtitle}</div></div>',
                unsafe_allow_html=True)


def stats(items):
    """items: [(label, value, detail)] -> responsive stat cards."""
    st.markdown('<div class="ss-stats">' + "".join(
        f'<div class="ss-stat"><div class="l">{l}</div><div class="v">{v}</div><div class="d">{d}</div></div>'
        for l, v, d in items) + "</div>", unsafe_allow_html=True)


def pill(text, kind="idle"):
    return f'<span class="ss-pill {kind}">{text}</span>'


def bar(pct, color=None):
    color = color or ("var(--ok)" if pct >= 80 else "var(--warn)" if pct >= 50 else "var(--bad)")
    return f'<div class="ss-bar"><i style="width:{max(0, min(pct, 100))}%;background:{color}"></i></div>'


def _sidebar():
    with st.sidebar:
        st.markdown('<div class="ss-brand">🩺 Sehat Sathi<br><span>Your health companion</span></div>', unsafe_allow_html=True)
        opts, cur = [AUTO] + list(LANGS), get_setting("language", AUTO)
        st.selectbox("🌐 Language", opts, index=opts.index(cur) if cur in opts else 0, key="sb_lang",
                     on_change=lambda: set_setting("language", st.session_state.sb_lang))
        st.toggle("🔊 Speak answers aloud", value=get_setting("voice", "0") == "1", key="sb_voice",
                  on_change=lambda: set_setting("voice", "1" if st.session_state.sb_voice else "0"))


def page_setup(title, icon):
    """Call first on every page: config, styling, sidebar, disclaimer banner, one-time bootstrap."""
    st.set_page_config(page_title=f"Sehat Sathi - {title}", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    if title != "Settings":  # Settings has its own language/voice controls
        _sidebar()
    st.markdown(f'<div class="ss-disc">⚕️ {DISCLAIMER}</div>', unsafe_allow_html=True)
    if not st.session_state.get("booted"):
        from core import extract, notify
        with st.spinner("Getting your documents ready (the first run downloads a small model)..."):
            try:
                extract.bootstrap()
            except Exception as e:
                st.error(f"Setup problem: {e}")
        notify.start()
        st.session_state.booted = True
