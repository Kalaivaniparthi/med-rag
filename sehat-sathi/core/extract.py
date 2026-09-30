"""LLM-based extraction of medications, appointments and lab values; document bootstrap."""
import json
import re
from datetime import date, datetime
from pathlib import Path

from core import db, rag

PROMPT = """Extract structured data from this medical document. Reply with ONLY a JSON object:
{{"medications":[{{"name":"","dose":"","times":["HH:MM"],"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","notes":""}}],
"appointments":[{{"title":"","doctor":"","datetime":"YYYY-MM-DDTHH:MM","location":"","notes":""}}],
"lab_values":[{{"test":"","value":0,"unit":"","date":"YYYY-MM-DD"}}]}}
Rules: only include what is explicitly written; use [] when absent; numeric lab values only; use the report date
for each lab value. Medication times: OD=["08:00"], BD=["08:00","20:00"], TID=["08:00","14:00","20:00"],
QID=["08:00","12:00","16:00","20:00"]; as-needed/PRN=[]. Compute end_date from start and duration when given.
Document ({name}):
{text}"""


def _json(reply):
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def extract_all(name, text):
    """One Groq call -> dict with medications / appointments / lab_values lists."""
    data = _json(rag.llm("You extract data as strict JSON. No prose.", PROMPT.format(name=name, text=text[:9000])))
    return {k: data.get(k) or [] for k in ("medications", "appointments", "lab_values")}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def save_extracted(name, data):
    """Insert extracted rows (deduplicated). Returns counts."""
    n = {"medications": 0, "appointments": 0, "lab_values": 0}
    for m in data["medications"]:
        if m.get("name") and db.add_med(m["name"], m.get("dose", ""), m.get("times") or [],
                                        m.get("start_date") or "", m.get("end_date") or "", m.get("notes") or ""):
            n["medications"] += 1
    for a in data["appointments"]:
        if a.get("title") and db.add_appt(a["title"], a.get("doctor") or "", a.get("datetime") or "",
                                          a.get("location") or "", a.get("notes") or ""):
            n["appointments"] += 1
    for lv in data["lab_values"]:
        v = _num(lv.get("value"))
        if lv.get("test") and v is not None and lv.get("date") and db.add_lab(
                lv["test"], v, lv.get("unit") or "", lv["date"], name):
            n["lab_values"] += 1
    return n


def _guess_date(text):
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return m.group(0) if m else date.today().isoformat()


def _kind(name, text):
    t = (name + text[:400]).lower()
    return "Discharge summary" if "discharge" in t else "Lab report" if "lab" in t or "hba1c" in t else "Document"


def register(path):
    """Index a file and put it on the document timeline."""
    path = Path(path)
    _, text = rag.ingest_file(path)
    db.run("INSERT OR IGNORE INTO documents(name,doc_date,kind,added) VALUES(?,?,?,?)",
           (path.name, _guess_date(text), _kind(path.name, text), datetime.now().isoformat(timespec="seconds")))


def process_document(path):
    """Register a file, then extract structured data (needs the Groq key; retried later if it fails)."""
    register(path)
    return extract_pending()


def extract_pending():
    """Run extraction for every document not yet extracted. Returns {file: counts or error}."""
    out = {}
    for d in db.q("SELECT name FROM documents WHERE extracted=0"):
        try:
            text = "\n".join(t for _, t in rag.read_pages(rag.DOCS / d["name"]))
            out[d["name"]] = save_extracted(d["name"], extract_all(d["name"], text))
            db.run("UPDATE documents SET extracted=1 WHERE name=?", (d["name"],))
        except Exception as e:
            out[d["name"]] = f"extraction skipped: {e}"
    return out


def bootstrap():
    """First run: index every .txt/.pdf in ./docs that isn't on the timeline yet."""
    known = {d["name"] for d in db.q("SELECT name FROM documents")}
    for f in sorted(rag.DOCS.glob("*")):
        if f.suffix.lower() in (".txt", ".pdf") and f.name not in known:
            register(f)
    if db.cfg("GROQ_API_KEY"):
        extract_pending()
