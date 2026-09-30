from datetime import datetime, timedelta

import plotly.express as px
import streamlit as st
from icalendar import Calendar, Event

from core import db, rag

db.page_setup("Appointments", "📅")
db.hero("📅 Appointments", "Keep your visits in one place, add them to your phone calendar, "
        "and walk in prepared.")


def parse(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


appts = sorted(db.q("SELECT * FROM appointments"), key=lambda a: a["datetime"] or "")
now = datetime.now()
upcoming = [a for a in appts if (parse(a["datetime"]) or now) >= now]
tab_up, tab_prep, tab_manage = st.tabs(["📌 Upcoming", "📝 Prepare for my visit", "✏️ Add & edit"])

# ---- upcoming ----
with tab_up:
    if not upcoming:
        st.info("No upcoming appointments.")
    for a in upcoming:
        when = parse(a["datetime"])
        if not when:
            st.markdown(f'<div class="ss-card"><b>{a["title"]}</b> · {a["doctor"]}</div>', unsafe_allow_html=True)
            continue
        days = (when.date() - now.date()).days
        chip = db.pill("today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days",
                       "warn" if days <= 2 else "brand")
        st.markdown(f'<div class="ss-card"><span class="ss-date"><b>{when:%d}</b><span>{when:%b}</span></span>'
                    f'<b>{a["title"]}</b> &nbsp;{chip}<br><span style="opacity:.75">{when:%I:%M %p} · '
                    f'{a["doctor"]} · {a["location"]}</span></div>', unsafe_allow_html=True)
    dated = [{"When": parse(a["datetime"]), "Title": a["title"], "Doctor": a["doctor"]} for a in appts if parse(a["datetime"])]
    if dated:
        fig = px.scatter(dated, x="When", y=[1] * len(dated), text="Title", hover_data=["Doctor"],
                         color_discrete_sequence=["#0d9488"])
        fig.update_traces(textposition="top center", marker_size=14)
        fig.update_yaxes(visible=False, range=[0, 2])
        fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    cal = Calendar()
    cal.add("prodid", "-//Sehat Sathi//EN")
    cal.add("version", "2.0")
    for a in appts:
        if parse(a["datetime"]):
            ev = Event()
            ev.add("summary", a["title"])
            ev.add("dtstart", parse(a["datetime"]))
            ev.add("dtend", parse(a["datetime"]) + timedelta(hours=1))
            ev.add("location", a["location"] or "")
            ev.add("description", f"Doctor: {a['doctor']}. {a['notes'] or ''}")
            cal.add_component(ev)
    st.download_button("📆 Add to Google / Apple Calendar (.ics)", cal.to_ical(), "appointments.ics", "text/calendar")

# ---- prepare ----
with tab_prep:
    st.write("Get 5 questions you might want to ask your doctor, based on your documents and lab trends.")
    if st.button("✨ Prepare for my next visit", type="primary"):
        code = rag.lang_code("")
        docs = "\n\n".join(f"[{n}]\n" + "\n".join(p)[:3000] for n, p in rag.doc_texts().items())
        labs = db.q("SELECT test, unit, GROUP_CONCAT(date || ': ' || value, '; ') v FROM "
                    "(SELECT * FROM lab_values ORDER BY date) GROUP BY test, unit")
        trends = "\n".join(f"{r['test']} ({r['unit']}): {r['v']}" for r in labs)
        with st.spinner("Preparing your questions..."):
            try:
                st.session_state.prep = rag.llm(
                    "You help a patient prepare for a doctor visit. Using only the documents and lab trends given, "
                    "write exactly 5 short questions the patient could ask the doctor. Questions only - no advice, "
                    f"diagnosis or treatment. Write them in {rag.lang_name(code)}.",
                    f"Documents:\n{docs}\n\nLab trends:\n{trends}", 0.3)
            except Exception as e:
                st.error(str(e))
    if st.session_state.get("prep"):
        with st.container(border=True):
            st.markdown("**Questions for your doctor**")
            st.markdown(st.session_state.prep)
        st.download_button("⬇️ Download as PDF", rag.to_pdf("Questions for my next visit", st.session_state.prep),
                           "visit_questions.pdf", "application/pdf")


# ---- add / edit / delete ----
def appt_form(key, a=None):
    a = a or {"title": "", "doctor": "", "datetime": "", "location": "", "notes": ""}
    when = parse(a["datetime"]) or now + timedelta(days=7)
    with st.form(key):
        c1, c2 = st.columns(2)
        title = c1.text_input("Title", a["title"])
        doctor = c2.text_input("Doctor", a["doctor"])
        c1, c2 = st.columns(2)
        d = c1.date_input("Date", when.date())
        t = c2.time_input("Time", when.time().replace(second=0, microsecond=0))
        loc = st.text_input("Location", a["location"])
        notes = st.text_input("Notes", a["notes"])
        return (st.form_submit_button("💾 Save", type="primary"), title, doctor,
                datetime.combine(d, t).isoformat(timespec="minutes"), loc, notes)


with tab_manage:
    with st.expander("➕ Add an appointment", expanded=not appts):
        ok, *vals = appt_form("add")
        if ok and vals[0]:
            db.add_appt(*vals)
            st.rerun()
    for a in appts:
        with st.expander(f"✏️ {(a['datetime'] or '').replace('T', ' ')} - {a['title']}"):
            ok, *vals = appt_form(f"e{a['id']}", a)
            if ok:
                db.run("UPDATE appointments SET title=?,doctor=?,datetime=?,location=?,notes=? WHERE id=?", (*vals, a["id"]))
                st.rerun()
            if st.button("🗑️ Delete", key=f"d{a['id']}"):
                db.run("DELETE FROM appointments WHERE id=?", (a["id"],))
                st.rerun()
