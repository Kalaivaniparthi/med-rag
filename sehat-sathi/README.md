# Sehat Sathi (Health Companion)

A multilingual voice health companion that runs locally with free services only. Upload medical documents, then ask about them by typing or speaking, in your own language. Answers come only from your documents, with citations. Medications, appointments, lab trends, diet and reminders are extracted or tracked in a local SQLite database.

> Not a doctor. It helps you understand your documents. It never gives medical advice, diagnosis or treatment.

**Stack:** Streamlit, Groq (`llama-3.1-8b-instant`), ChromaDB (ONNX embeddings, no torch), SQLite, SpeechRecognition (Google Web Speech), pyttsx3 / gTTS, ntfy.sh, Plotly, APScheduler, pdfplumber / pypdf, icalendar, fpdf2.

## Run

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...        # or paste it on the Settings page
streamlit run app.py
```

First launch indexes `docs/` and downloads the small ONNX embedding model (about 80 MB, one time).

## Get a Groq key (free)
1. Sign in at https://console.groq.com and open **API Keys**.
2. Create a key and set it as `GROQ_API_KEY`, or paste it on the **⚙️ Settings** page. `st.secrets` also works.

## Phone reminders with ntfy.sh (no account)
1. Install the **ntfy** app (Android/iOS) or open https://ntfy.sh in a browser.
2. Subscribe to the random topic shown on the Settings page (change it with `NTFY_TOPIC`).
3. Press **Send test notification**. Medication reminders fire at each dose time while the app is running.

## Notes
- The mic button uses the browser microphone (`st.audio_input`) and sends the recording to Google Web Speech through SpeechRecognition. Recognition needs internet. This avoids PyAudio, which is not in the allowed requirements.
- Speech output is played in the browser. English uses offline pyttsx3 when available. Other languages use gTTS, which needs internet.
- Retrieval uses English embeddings, so non-English questions are translated to English for the search step only. The answer is written in your language.
- PDF export of non-Latin scripts (Hindi, Tamil, Telugu) needs a Unicode font on the machine (Nirmala on Windows, Noto or DejaVu on Linux). Conjunct shaping is basic.
- The 6,000 tokens-per-minute free Groq limit applies. Very long documents are truncated for extraction.

## Demo script (5 minutes)
Set **Language = Hindi** on the Settings page first and turn voice on.

| Scene | Time | What to do |
|---|---|---|
| 1 | 0:00 | **📄 Documents**: upload `lab_report.pdf` and `discharge_summary.pdf`, or use the pre-loaded `docs/*.txt` samples. They appear on the timeline with dates. |
| 2 | 0:30 | On **Chat**, click the mic and ask in Hindi: "मेरा कोलेस्ट्रॉल कितना है?" Watch the retrieval animation. The answer appears and is spoken in Hindi, with citation cards. |
| 3 | 1:15 | On **Documents → Point and ask**, press 🔍 on the paragraph about the appendectomy (the sample discharge summary is an appendectomy case). The assistant explains it in plain Hindi, out loud. |
| 4 | 2:00 | On **💊 Medications**, show the auto-extracted list (amoxicillin, paracetamol, omeprazole), press **Taken** on one, and show the adherence bar. |
| 5 | 2:30 | On **📅 Appointments**, press **Prepare for my next visit**. Five questions appear in Hindi. Download the PDF. |
| 6 | 3:00 | On **📊 Trends**, show the LDL line across the 3 visits with the reference band. |

Close: "Runs locally. Free. Private. In your language."

## Files
`app.py` (chat), `pages/` (documents, medications, appointments, diet, trends, settings), `core/` (rag, voice, db, extract, notify, anim), `docs/` (fictional samples).
