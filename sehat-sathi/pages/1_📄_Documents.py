import html

import streamlit as st

from core import db, extract, rag, voice

db.page_setup("Documents", "📄")
db.hero("📄 Your documents", "Upload reports, see them on a timeline, get a plain-language summary, "
        "or point at any paragraph to have it explained.")
code = rag.lang_code("")  # Settings language ("en" when auto-detect)
docs = db.q("SELECT * FROM documents ORDER BY doc_date")
tab_up, tab_ask, tab_sum = st.tabs(["📤 Upload & timeline", "🔍 Point & ask", "📝 Summary"])

# ---- upload + timeline ----
with tab_up:
    seen = st.session_state.setdefault("uploaded", set())
    for f in st.file_uploader("Drop PDF or TXT files here", type=["pdf", "txt"], accept_multiple_files=True) or []:
        if f.name not in seen:
            (rag.DOCS / f.name).write_bytes(f.getvalue())
            with st.spinner(f"Reading {f.name} and finding medicines, appointments and lab values..."):
                res = extract.process_document(rag.DOCS / f.name)
            seen.add(f.name)
            st.success(f"✅ {f.name} added. {res.get(f.name, '')}")
            st.rerun()
    st.markdown("#### Timeline")
    if not docs:
        st.info("No documents yet - upload one above.")
    for d in docs:
        icon = {"Lab report": "🧪", "Discharge summary": "🏥"}.get(d["kind"], "📄")
        status = db.pill("Ready", "ok") if d["extracted"] else db.pill("Extraction pending", "warn")
        st.markdown(f'<div class="ss-card"><span class="ss-date"><b>{d["doc_date"][8:10]}</b>'
                    f'<span>{d["doc_date"][:7]}</span></span>{icon} <b>{d["kind"]}</b> &nbsp;·&nbsp; '
                    f'<code>{html.escape(d["name"])}</code> &nbsp; {status}</div>', unsafe_allow_html=True)
    if any(not d["extracted"] for d in docs) and st.button("🔄 Retry extraction (needs Groq key)"):
        st.write(extract.extract_pending())
        st.rerun()

# ---- point and ask ----
with tab_ask:
    if not docs:
        st.info("Upload a document first.")
    else:
        name = st.selectbox("Choose a document", [d["name"] for d in docs])
        st.caption("Press 🔍 next to any paragraph and it will be explained in plain language" +
                   (" and read aloud." if db.get_setting("voice", "0") == "1" else "."))
        paras = rag.paragraphs(rag.DOCS / name)
        left, right = st.columns([3, 2], gap="large")
        with left:
            for i, (page, text) in enumerate(paras):
                c1, c2 = st.columns([9, 1])
                c1.markdown(f'<div id="para-{i}" class="clickable">{html.escape(text).replace(chr(10), "<br>")}</div>',
                            unsafe_allow_html=True)
                if c2.button("🔍", key=f"p{i}", help="Explain this paragraph"):
                    st.session_state.pending_click = i
        with right:
            i = st.session_state.pop("pending_click", None)
            if i is not None and i < len(paras):
                ctx = "\n\n".join(p[1] for p in paras[max(0, i - 1):i + 2])
                with st.spinner("Explaining in simple words..."):
                    try:
                        st.session_state.explanation = (paras[i][1], rag.explain(paras[i][1], ctx, code))
                        st.session_state.speak_now = True
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("explanation"):
                para, exp = st.session_state.explanation
                with st.container(border=True):
                    st.markdown("**💬 In simple words**")
                    st.caption(f"About: “{para[:160]}{'...' if len(para) > 160 else ''}”")
                    st.markdown(exp)
                if st.session_state.pop("speak_now", False) and db.get_setting("voice", "0") == "1":
                    voice.play(exp, code)
            else:
                st.info("👈 Your explanation will appear here.")

# ---- summary ----
with tab_sum:
    st.write("Get a short, plain-language summary of everything you've uploaded.")
    if st.button("✨ Summarize all documents", type="primary"):
        with st.spinner("Summarizing..."):
            try:
                st.session_state.summary = rag.summarize_all(code)
            except Exception as e:
                st.error(str(e))
    if st.session_state.get("summary"):
        with st.container(border=True):
            st.markdown(st.session_state.summary)
        st.download_button("⬇️ Download as PDF", rag.to_pdf("Document summary", st.session_state.summary),
                           "summary.pdf", "application/pdf")
