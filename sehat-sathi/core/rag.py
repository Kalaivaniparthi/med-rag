"""ChromaDB ingest + retrieve + Groq calls (plus small shared helpers: PDF export, paragraphs)."""
import re
from pathlib import Path

import chromadb
from langchain_groq import ChatGroq
from langdetect import DetectorFactory, detect
from pypdf import PdfReader

from core import db

DetectorFactory.seed = 0
MODEL = "llama-3.1-8b-instant"
DOCS = db.ROOT / "docs"
SYSTEM_PROMPT = (
    "You are a patient health assistant. Answer ONLY using the provided context. "
    "If the answer is not in the context, say in the user's language: "
    "'I could not find that in your documents.' Never give medical advice, diagnosis, or treatment. "
    "Always cite the source file and page. Respond in the SAME LANGUAGE as the user's question.")
_col = None


def collection():
    global _col
    if _col is None:  # default embedding function = ONNX MiniLM, no torch
        _col = chromadb.PersistentClient(path=str(db.ROOT / "chroma_db")).get_or_create_collection("docs")
    return _col


def llm(system, user, temperature=0.0):
    key = db.cfg("GROQ_API_KEY")
    if not key:
        raise RuntimeError("No Groq key: set GROQ_API_KEY in the environment or on the Settings page.")
    return ChatGroq(model=MODEL, api_key=key, temperature=temperature).invoke(
        [("system", system), ("human", user)]).content


# ---------- language ----------
def lang_code(text):
    """Answer language: Settings choice, or auto-detected from the text."""
    chosen = db.get_setting("language", db.AUTO)
    if chosen in db.LANGS:
        return db.LANGS[chosen]
    try:
        c = detect(text)
    except Exception:
        return "en"
    return "zh-CN" if c.startswith("zh") else c


def lang_name(code):
    return next((n for n, c in db.LANGS.items() if c == code), "the same language as the question")


# ---------- ingest ----------
def read_pages(path):
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return [(i + 1, pg.extract_text() or "") for i, pg in enumerate(PdfReader(str(p)).pages)]
    return [(1, p.read_text(encoding="utf-8", errors="ignore"))]


def chunk_text(text, size=500, overlap=50):
    text = re.sub(r"[ \t]+", " ", text).strip()
    return [text[i:i + size] for i in range(0, max(len(text), 1), size - overlap) if text[i:i + size].strip()]


def ingest_file(path):
    """(Re)index one .txt/.pdf. Returns (n_chunks, full_text)."""
    name, pages = Path(path).name, read_pages(path)
    col = collection()
    col.delete(where={"source_file": name})
    ids, docs, metas = [], [], []
    for page, text in pages:
        for i, ch in enumerate(chunk_text(text)):
            ids.append(f"{name}:{page}:{i}")
            docs.append(ch)
            metas.append({"source_file": name, "page_number": page, "chunk_index": i})
    if ids:
        col.add(ids=ids, documents=docs, metadatas=metas)
    return len(ids), "\n".join(t for _, t in pages)


def retrieve(query, k=3):
    col = collection()
    if col.count() == 0:
        return []
    r = col.query(query_texts=[query], n_results=min(k, col.count()))
    return [{"source_file": m["source_file"], "page": m["page_number"], "raw_chunk": d,
             "score": round(max(0.0, 1 - dist / 2), 3)}  # squared-L2 on unit vectors -> cosine
            for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])]


# ---------- ask ----------
def ask(question):
    code = lang_code(question)
    search = question
    if code != "en":  # embeddings are English-centric: retrieve with an English rendering of the query
        try:
            search = llm("Translate to English. Output only the translation.", question)
        except Exception:
            pass
    chunks = retrieve(search)
    if not chunks:
        return {"answer": llm(SYSTEM_PROMPT, f"Context: (none)\n\nQuestion: {question}\nRespond in {lang_name(code)}."),
                "chunks": [], "lang": code}
    ctx = "\n\n".join(f"[Source: {c['source_file']}, page {c['page']}]\n{c['raw_chunk']}" for c in chunks)
    answer = llm(SYSTEM_PROMPT, f"Context:\n{ctx}\n\nQuestion: {question}\nRespond in {lang_name(code)}.")
    return {"answer": answer, "chunks": chunks, "lang": code}


def explain(paragraph, context, code):
    return llm(f"You are a patient health assistant. Explain the highlighted passage from the user's medical "
               f"document in plain, simple {lang_name(code)}. Use only the passage and its context. "
               f"Never give medical advice, diagnosis, or treatment.",
               f"Context:\n{context}\n\nHighlighted passage:\n{paragraph}", 0.2)


def doc_texts():
    got = collection().get()
    docs = {}
    for d, m in sorted(zip(got["documents"], got["metadatas"]),
                       key=lambda x: (x[1]["source_file"], x[1]["page_number"], x[1]["chunk_index"])):
        docs.setdefault(m["source_file"], []).append(d)
    return docs


def summarize_all(code):
    """One bullet per document; long docs are summarised in batches then merged."""
    sysm = ("Summarize these medical documents in plain language, in the user's language, with a bullet "
            "per document. No medical advice.")
    bullets = []
    for name, parts in doc_texts().items():
        text = "\n".join(parts)
        batches = [text[i:i + 7000] for i in range(0, len(text), 7000)]
        partial = [llm(sysm, f"Language: {lang_name(code)}\nDocument: {name}\n\n{b}") for b in batches]
        bullets.append(partial[0] if len(partial) == 1 else llm(
            sysm, f"Language: {lang_name(code)}\nMerge into one bullet for {name}:\n" + "\n".join(partial)))
    return "\n\n".join(bullets)


# ---------- shared helpers ----------
def paragraphs(path):
    """[(page, text)] paragraphs for point-and-ask. Uses pdfplumber for PDFs."""
    p, out = Path(path), []
    if p.suffix.lower() == ".pdf":
        import pdfplumber
        with pdfplumber.open(str(p)) as pdf:
            pages = [(i + 1, pg.extract_text() or "") for i, pg in enumerate(pdf.pages)]
    else:
        pages = read_pages(p)
    for page, text in pages:
        for para in re.split(r"\n\s*\n", text):
            if para.strip():
                out.append((page, para.strip()))
    return out


def to_pdf(title, text):
    """Text -> PDF bytes (fpdf2). Needs a system Unicode font for Hindi/Tamil/etc."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    font = next((f for f in ["C:/Windows/Fonts/Nirmala.ttf", "/mnt/c/Windows/Fonts/Nirmala.ttf",
                             "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"] if Path(f).exists()), None)
    if font:
        pdf.add_font("U", "", font)
        pdf.set_font("U", size=12)
    else:
        pdf.set_font("Helvetica", size=12)
        title, text = (s.encode("latin-1", "replace").decode("latin-1") for s in (title, text))
    for chunk in (title, "", text.replace("**", "")):
        pdf.multi_cell(0, 7, chunk, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
