"""STT (Google Web Speech, free) + TTS (pyttsx3 offline for English, gTTS otherwise)."""
import io
import os
import re
import tempfile

import speech_recognition as sr
import streamlit as st

STT_LOCALES = {"en": "en-IN", "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "es": "es-ES",
               "fr": "fr-FR", "de": "de-DE", "ar": "ar-SA", "zh-CN": "zh-CN"}
AUTO_CANDIDATES = ["en-IN", "hi-IN", "ta-IN", "te-IN"]


def transcribe(wav_bytes, code=None):
    """WAV bytes -> (text, error). code=None tries several locales and keeps the most confident."""
    rec = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(wav_bytes)) as src:
            audio = rec.record(src)
    except Exception as e:
        return "", f"Could not read audio: {e}"
    best, best_conf, err = "", -1.0, "Could not understand the audio."
    for loc in ([STT_LOCALES[code]] if code in STT_LOCALES else AUTO_CANDIDATES):
        try:
            res = rec.recognize_google(audio, language=loc, show_all=True)
        except sr.RequestError as e:
            return "", f"Speech service unreachable: {e}"
        except sr.UnknownValueError:
            continue
        alts = res.get("alternative", []) if isinstance(res, dict) else []
        if alts and alts[0].get("confidence", 0.5) > best_conf:
            best, best_conf = alts[0]["transcript"], alts[0].get("confidence", 0.5)
    return (best, "") if best else ("", err)


def speak(text, code="en"):
    """Text -> (audio_bytes, mime) or None. pyttsx3 for English, gTTS for everything else/fallback."""
    text = re.sub(r"[*#_`]", "", text)
    if code == "en":
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            import pyttsx3
            eng = pyttsx3.init()
            eng.save_to_file(text, path)
            eng.runAndWait()
            if os.path.getsize(path) > 1000:
                with open(path, "rb") as f:
                    return f.read(), "audio/wav"
        except Exception:
            pass
        finally:
            os.path.exists(path) and os.remove(path)
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text, lang=code).write_to_fp(buf)
        return buf.getvalue(), "audio/mpeg"
    except Exception:
        return None


def play(text, code="en"):
    """Speak in the browser (works wherever the server runs, even headless/WSL)."""
    out = speak(text, code)
    if out:
        st.audio(out[0], format=out[1], autoplay=True)
    else:
        st.caption("🔇 Could not generate speech (offline?).")
