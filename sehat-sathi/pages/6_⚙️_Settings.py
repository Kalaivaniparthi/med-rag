import os

import streamlit as st

from core import db, extract, notify

db.page_setup("Settings", "⚙️")
db.hero("⚙️ Settings", "Language, voice, phone reminders and your Groq key.")
tab_lang, tab_ntfy, tab_key, tab_safe = st.tabs(["🌐 Language & voice", "🔔 Reminders", "🔑 Groq key", "🛡️ Safety"])

with tab_lang:
    options, cur = [db.AUTO] + list(db.LANGS), db.get_setting("language", db.AUTO)
    lang = st.selectbox("Language for answers, explanations and speech", options,
                        index=options.index(cur) if cur in options else 0,
                        help="Auto-detect answers in the language you ask in.")
    voice_on = st.toggle("🔊 Speak answers aloud", value=db.get_setting("voice", "0") == "1")
    if st.button("💾 Save", type="primary", key="save_lang"):
        db.set_setting("language", lang)
        db.set_setting("voice", "1" if voice_on else "0")
        st.success("Saved.")

with tab_ntfy:
    st.markdown("**1.** Install the free **ntfy** app on your phone  \n"
                "**2.** Subscribe to the topic below  \n**3.** Press *Send test notification*")
    topic = st.text_input("Your ntfy topic", db.cfg("NTFY_TOPIC"),
                          help="Anyone who knows this topic can post to it, so keep it random.")
    st.code(f"https://ntfy.sh/{topic}", language=None)
    c1, c2 = st.columns(2)
    if c1.button("💾 Save topic", type="primary"):
        db.set_setting("NTFY_TOPIC", topic.strip())
        st.success("Saved.")
    if c2.button("🔔 Send test notification"):
        if notify.send_ntfy("Sehat Sathi", "Test notification - reminders are working!"):
            st.success("Sent - check your phone.")
        else:
            st.error("Could not reach ntfy.sh.")

with tab_key:
    if os.environ.get("GROQ_API_KEY"):
        st.success("Using GROQ_API_KEY from the environment.")
    else:
        st.markdown("Get a free key at **console.groq.com → API Keys**.")
        if db.get_setting("GROQ_API_KEY"):
            st.success("A key is saved.")
        key = st.text_input("GROQ_API_KEY", type="password", placeholder="gsk_...")
        if st.button("💾 Save key", type="primary") and key:
            db.set_setting("GROQ_API_KEY", key.strip())
            with st.spinner("Reading your documents for medicines, appointments and lab values..."):
                st.write(extract.extract_pending())
            st.success("Saved.")

with tab_safe:
    st.markdown("- Answers come **only from your uploaded documents**, with citations.\n"
                "- The assistant **never gives medical advice, diagnosis or treatment**.\n"
                "- Everything is stored on this computer (`data.db`, `chroma_db/`). Only short text snippets are sent to Groq.\n"
                "- For medical advice, contact your healthcare provider.")
