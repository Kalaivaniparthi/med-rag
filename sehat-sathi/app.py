"""Sehat Sathi - landing page + multilingual voice chat over your documents."""
import hashlib
import time
from datetime import datetime

import streamlit as st

from core import db, rag, voice
from core.anim import render_retrieval_animation as render

db.page_setup("Chat", "🩺")
speak_on = db.get_setting("voice", "0") == "1"

db.hero("Namaste 🙏 How can I help today?",
        "Ask about your medical documents in your own language - type or use your voice. "
        "Every answer shows exactly where it came from.")

# ---- at-a-glance stats ----
sched = db.today_schedule()
taken = sum(1 for s in sched if s["status"] == "taken")
nxt = next((a for a in sorted(db.q("SELECT * FROM appointments"), key=lambda a: a["datetime"])
            if a["datetime"] >= datetime.now().isoformat(timespec="minutes")), None)
db.stats([("Documents", len(db.q("SELECT id FROM documents")), "indexed and searchable"),
          ("Doses today", f"{taken}/{len(sched)}", "taken so far"),
          ("Next visit", datetime.fromisoformat(nxt["datetime"]).strftime("%d %b") if nxt else "-", nxt["title"] if nxt else "none scheduled")])

if not db.cfg("GROQ_API_KEY"):
    st.info("👉 Add your free Groq key in **⚙️ Settings** to start asking questions.")

msgs = st.session_state.setdefault("messages", [])
question = None

# ---- voice input (open while the chat is empty) ----
with st.expander("🎤 Ask by voice", expanded=not msgs):
    audio = st.audio_input("Tap the mic, speak, then tap stop", label_visibility="collapsed")
    if audio:
        data = audio.getvalue()
        digest = hashlib.md5(data).hexdigest()
        if digest != st.session_state.get("last_audio"):  # audio_input keeps its value across reruns
            st.session_state.last_audio = digest
            with st.spinner("Listening..."):
                text, err = voice.transcribe(data, db.LANGS.get(db.get_setting("language", db.AUTO)))
            if err:
                st.error(err)
            else:
                question = text

# ---- suggestions ----
if not msgs:
    st.markdown("**Try asking**")
    ideas = ["What is my LDL cholesterol?", "Which medicines was I prescribed?",
             "When is my follow-up visit?", "मेरा कोलेस्ट्रॉल कितना है?"]
    for col, idea in zip(st.columns(len(ideas)), ideas):
        if col.button(idea, width="stretch"):
            question = idea

for m in msgs:
    with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "🩺"):
        if m["role"] == "user":
            st.write(m["content"])
        else:
            st.markdown(render(m["q"], m["chunks"], m["content"]), unsafe_allow_html=True)

question = st.chat_input("Ask about your documents...") or question
if question:
    msgs.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑"):
        st.write(question)
    with st.chat_message("assistant", avatar="🩺"):
        try:
            with st.spinner("Searching your documents..."):
                res = rag.ask(question)
        except Exception as e:
            st.error(str(e))
            st.stop()
        box = st.empty()
        for stage, pause in ((0, 0.3), (1, 0.8), (2, 0.4), (3, 0)):  # cards fade in, curves, lift, answer
            box.markdown(render(question, res["chunks"], res["answer"], stage), unsafe_allow_html=True)
            time.sleep(pause)
        if speak_on:
            voice.play(res["answer"], res["lang"])
    msgs.append({"role": "assistant", "content": res["answer"], "q": question, "chunks": res["chunks"]})

if msgs:
    with st.sidebar:
        if st.button("🗑️ Clear chat", width="stretch"):
            st.session_state.messages = []
            st.rerun()
