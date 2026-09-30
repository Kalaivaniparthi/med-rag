import json
from datetime import date

import streamlit as st

from core import db, notify

db.page_setup("Medications", "💊")
db.hero("💊 Medications", f"{date.today():%A, %d %B} - tap a button when you take a dose. "
        "Reminders are sent to your phone through ntfy.")

sched, all_meds = db.today_schedule(), db.meds()
taken = sum(1 for s in sched if s["status"] == "taken")
scores = [a for a in (db.adherence(m) for m in all_meds) if a is not None]
db.stats([("Today", f"{taken}/{len(sched)}", "doses taken"),
          ("7-day adherence", f"{round(sum(scores) / len(scores))}%" if scores else "-", "across scheduled medicines"),
          ("Medicines", len(all_meds), "on your list")])
tab_today, tab_adh, tab_manage = st.tabs(["🗓️ Today", "📈 Adherence", "✏️ Manage"])

# ---- today ----
STATUS = {"taken": ("Taken", "ok"), "skipped": ("Skipped", "idle"), "snoozed": ("Snoozed", "warn"), None: ("Pending", "brand")}
with tab_today:
    if not sched:
        st.info("Nothing scheduled today. Medicines found in your uploaded documents appear here automatically.")
    for s in sched:
        m, t = s["med"], s["time"]
        label, kind = STATUS[s["status"]]
        with st.container(border=True):
            c = st.columns([1, 4, 1.4, 1.2, 1.2, 1.2], vertical_alignment="center")
            c[0].markdown(f"### ⏰ {t}")
            c[1].markdown(f"**{m['name']}**  \n{m['dose']} {('· ' + m['notes']) if m['notes'] else ''}")
            c[2].markdown(db.pill(label, kind), unsafe_allow_html=True)
            if c[3].button("✅ Taken", key=f"t{m['id']}{t}", type="primary" if s["status"] != "taken" else "secondary"):
                db.log_dose(m["id"], t, "taken")
                st.rerun()
            if c[4].button("⏭️ Skip", key=f"s{m['id']}{t}"):
                db.log_dose(m["id"], t, "skipped")
                st.rerun()
            if c[5].button("⏰ Later", key=f"z{m['id']}{t}", help="Remind me again in 10 minutes"):
                notify.snooze(m["id"], t)
                st.rerun()
    as_needed = [m for m in all_meds if not m["times"]]
    if as_needed:
        st.markdown("**Take only when needed**")
        for m in as_needed:
            st.markdown(f'<div class="ss-card">💊 <b>{m["name"]}</b> {m["dose"]} &nbsp; {m["notes"] or ""}</div>',
                        unsafe_allow_html=True)

# ---- adherence ----
with tab_adh:
    st.caption("Share of scheduled doses marked as taken over the last 7 days.")
    for m in all_meds:
        a = db.adherence(m)
        body = "as needed - no scheduled doses" if a is None else f"<b>{a}%</b>" + db.bar(a)
        st.markdown(f'<div class="ss-card"><b>{m["name"]}</b> {m["dose"]}<br>{body}</div>', unsafe_allow_html=True)
    if not all_meds:
        st.info("No medicines yet.")


# ---- manage ----
def med_form(key, m=None):
    m = m or {"name": "", "dose": "", "times": [], "start_date": "", "end_date": "", "notes": ""}
    with st.form(key):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", m["name"])
        dose = c2.text_input("Dose", m["dose"])
        times = st.text_input("Times (HH:MM, comma separated - leave empty if only when needed)", ", ".join(m["times"]))
        c1, c2 = st.columns(2)
        start = c1.text_input("Start date (YYYY-MM-DD)", m["start_date"])
        end = c2.text_input("End date (YYYY-MM-DD)", m["end_date"])
        notes = st.text_input("Notes", m["notes"])
        return (st.form_submit_button("💾 Save", type="primary"), name, dose,
                [x.strip() for x in times.split(",") if x.strip()], start, end, notes)


with tab_manage:
    with st.expander("➕ Add a medicine", expanded=not all_meds):
        ok, name, dose, times, start, end, notes = med_form("add")
        if ok and name:
            db.add_med(name, dose, times, start, end, notes)
            notify.schedule_medication_reminders(db.meds())
            st.rerun()
    for m in all_meds:
        with st.expander(f"✏️ {m['name']} {m['dose']}"):
            ok, name, dose, times, start, end, notes = med_form(f"e{m['id']}", m)
            if ok:
                db.run("UPDATE medications SET name=?,dose=?,times_json=?,start_date=?,end_date=?,notes=? WHERE id=?",
                       (name, dose, json.dumps(times), start, end, notes, m["id"]))
                notify.schedule_medication_reminders(db.meds())
                st.rerun()
            if st.button("🗑️ Delete this medicine", key=f"d{m['id']}"):
                db.run("DELETE FROM medications WHERE id=?", (m["id"],))
                db.run("DELETE FROM med_log WHERE med_id=?", (m["id"],))
                notify.schedule_medication_reminders(db.meds())
                st.rerun()
