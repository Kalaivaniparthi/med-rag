from datetime import date, datetime, timedelta

import plotly.express as px
import streamlit as st

from core import db, rag

db.page_setup("Diet", "🍎")
db.hero("🍎 Food & water", "Log what you eat and drink in a few taps. You'll get neutral observations - never advice.")
today = date.today().isoformat()
ICON = {"breakfast": "🍳", "lunch": "🍛", "dinner": "🍽️", "snack": "🍎"}


def add(kind, desc, notes=""):
    db.run("INSERT INTO diet(timestamp,meal_type,description,notes) VALUES(?,?,?,?)",
           (datetime.now().isoformat(timespec="seconds"), kind, desc, notes))


water_today = sum(int(r["description"]) for r in db.q(
    "SELECT description FROM diet WHERE meal_type='water' AND timestamp LIKE ?", (today + "%",)))
meals = db.q("SELECT * FROM diet WHERE meal_type!='water' AND timestamp LIKE ? ORDER BY timestamp", (today + "%",))
since = (date.today() - timedelta(days=6)).isoformat()
week = db.q("SELECT * FROM diet WHERE timestamp>=? ORDER BY timestamp", (since,))
db.stats([("Water today", f"{water_today} ml", "logged"), ("Meals today", len(meals), "logged"),
          ("This week", sum(1 for w in week if w["meal_type"] != "water"), "meals logged")])
tab_log, tab_week = st.tabs(["➕ Log & today", "📅 This week"])

with tab_log:
    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.form("meal", clear_on_submit=True):
            st.markdown("**Add a meal**")
            kind = st.segmented_control("Meal", list(ICON), default="breakfast", format_func=lambda k: f"{ICON[k]} {k.title()}",
                                        label_visibility="collapsed") or "snack"
            desc = st.text_input("What did you eat?", placeholder="e.g. 2 idli with sambar")
            notes = st.text_input("Notes (optional)")
            if st.form_submit_button("Add meal", type="primary") and desc:
                add(kind, desc, notes)
                st.rerun()
    with right:
        with st.container(border=True):
            st.markdown("**💧 Water**")
            st.markdown(f"### {water_today} ml")
            c = st.columns(3)
            for col, ml in zip(c, (150, 250, 500)):
                if col.button(f"+{ml}", key=f"w{ml}", width="stretch"):
                    add("water", str(ml))
                    st.rerun()
    st.markdown("#### Today")
    if not meals:
        st.caption("Nothing logged yet today.")
    for m in meals:
        with st.container(border=True):
            c1, c2 = st.columns([10, 1], vertical_alignment="center")
            c1.markdown(f"{ICON.get(m['meal_type'], '🍽️')} **{m['meal_type'].title()}** "
                        f"<span style='opacity:.6'>{m['timestamp'][11:16]}</span><br>{m['description']}"
                        f"{(' · _' + m['notes'] + '_') if m['notes'] else ''}", unsafe_allow_html=True)
            if c2.button("🗑️", key=f"del{m['id']}", help="Remove"):
                db.run("DELETE FROM diet WHERE id=?", (m["id"],))
                st.rerun()

with tab_week:
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    rows = [{"Day": d[5:], "Meals": sum(1 for w in week if w["timestamp"][:10] == d and w["meal_type"] != "water"),
             "Water (ml)": sum(int(w["description"]) for w in week if w["timestamp"][:10] == d and w["meal_type"] == "water")}
            for d in days]
    g1, g2 = st.columns(2)
    g1.plotly_chart(px.bar(rows, x="Day", y="Meals", title="Meals logged", color_discrete_sequence=["#0d9488"]), width="stretch")
    g2.plotly_chart(px.bar(rows, x="Day", y="Water (ml)", title="Water", color_discrete_sequence=["#0ea5e9"]), width="stretch")
    if st.button("✨ Observation summary", type="primary"):
        log = "\n".join(f"{w['timestamp'][:10]} {w['meal_type']}: {w['description']}" for w in week if w["meal_type"] != "water")
        if not log:
            st.info("Log some meals first.")
        else:
            with st.spinner("Summarizing..."):
                try:
                    st.session_state.diet_obs = rag.llm(
                        "You summarize a food diary with neutral factual observations only (counts, patterns, "
                        "what was logged). NEVER give advice, recommendations, or 'should' statements. "
                        "Example good: 'You logged 5 high-sodium meals this week.' "
                        f"Example forbidden: 'You should reduce sodium.' Reply in {rag.lang_name(rag.lang_code(''))}.",
                        f"Water total this week: {sum(r['Water (ml)'] for r in rows)} ml\nMeals:\n{log}", 0.2)
                except Exception as e:
                    st.error(str(e))
    if st.session_state.get("diet_obs"):
        with st.container(border=True):
            st.markdown("**👀 Observations**")
            st.markdown(st.session_state.diet_obs)
