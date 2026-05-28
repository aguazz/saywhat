import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from downloader import download_audio
from exporters import build_pdf, substitute_names
from flagging import flag_transcript
from storage import load_transcript, save_transcript
from transcriber import transcribe_with_progress

load_dotenv()  # loads .env for local dev; no-op on Streamlit Community Cloud

# ---------------------------------------------------------------------------
# Bilingual labels
# ---------------------------------------------------------------------------

LABELS = {
    "title":        {"English": "SayWhat",                       "Español": "SayWhat"},
    "subtitle":     {"English": "Paste a YouTube URL or upload a video to get a speaker-attributed transcript.",
                     "Español": "Pega una URL de YouTube o sube un video para obtener una transcripción por hablante."},
    "url_label":    {"English": "YouTube URL",                  "Español": "URL de YouTube"},
    "url_ph":       {"English": "https://www.youtube.com/watch?v=...",
                     "Español": "https://www.youtube.com/watch?v=..."},
    "or":           {"English": "or",                           "Español": "o"},
    "upload_label": {"English": "Upload a video or audio file", "Español": "Sube un archivo de video o audio"},
    "upload_help":  {"English": "Max 500 MB · Max 1.5 hours",   "Español": "Máx. 500 MB · Máx. 1.5 horas"},
    "btn":          {"English": "Transcribe",                   "Español": "Transcribir"},
    "spinner":      {"English": "Downloading and transcribing… this may take a few minutes.",
                     "Español": "Descargando y transcribiendo… esto puede tardar unos minutos."},
    "err_no_input": {"English": "Please provide a YouTube URL or upload a file.",
                     "Español": "Por favor, proporciona una URL de YouTube o sube un archivo."},
    "err_both":     {"English": "Please provide either a URL or a file — not both.",
                     "Español": "Proporciona solo una URL o solo un archivo, no ambos."},
    "transcript":   {"English": "Transcript",                   "Español": "Transcripción"},
    "summary":      {"English": "Language: **{lang}** · Duration: **{dur}** · Speakers: **{spk}** · Flagged zones: **{flags}**",
                     "Español": "Idioma: **{lang}** · Duración: **{dur}** · Hablantes: **{spk}** · Zonas marcadas: **{flags}**"},
    "legend":       {"English": "⚠ uncertain transcription · 🔴 unreliable (likely overlap or noise)",
                     "Español": "⚠ transcripción incierta · 🔴 poco fiable (posible superposición o ruido)"},
    "speaker":      {"English": "Speaker",                      "Español": "Hablante"},
    "name_speakers":{"English": "Name the Speakers",            "Español": "Nombrar a los hablantes"},
    "spk_name_lbl": {"English": "Speaker {sid}'s name",         "Español": "Nombre del Hablante {sid}"},
    "spk_name_ph":  {"English": "e.g. Joe Biden",               "Español": "p.ej. José Biden"},
    "prog_dl":      {"English": "⬇  Downloading audio…",           "Español": "⬇  Descargando audio…"},
    "prog_tx":      {"English": "🎙  Transcribing… (usually 1 min per 10 min of audio)",
                     "Español": "🎙  Transcribiendo… (aprox. 1 min por cada 10 min de audio)"},
    "prog_flag":    {"English": "🔍  Analyzing confidence zones…",  "Español": "🔍  Analizando zonas de confianza…"},
    "prog_done":    {"English": "✅  Done!",                        "Español": "✅  ¡Listo!"},
    "btn_dl_json":  {"English": "⬇  Download JSON",                 "Español": "⬇  Descargar JSON"},
    "btn_dl_pdf":   {"English": "⬇  Download PDF",                  "Español": "⬇  Descargar PDF"},
    "file_info":    {"English": "Selected: **{name}** ({size})",   "Español": "Seleccionado: **{name}** ({size})"},
    "err_too_large":{"English": "File is too large ({size}). Maximum allowed is 500 MB.",
                     "Español": "El archivo es demasiado grande ({size}). El máximo permitido es 500 MB."},
    "saved_link":   {"English": "Transcript saved. Share this link:",
                     "Español": "Transcripción guardada. Comparte este enlace:"},
    "err_not_found":{"English": "Transcript not found. The link may be invalid or the record was deleted.",
                     "Español": "Transcripción no encontrada. El enlace puede ser inválido o el registro fue eliminado."},
}

SPEAKER_COLORS = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ms_to_ts(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def render_utterance(utt: dict, lang: str, speaker_names: dict) -> str:
    sid   = utt["speaker"]
    color = SPEAKER_COLORS[min(ord(sid) - ord("A"), len(SPEAKER_COLORS) - 1)]
    name  = speaker_names.get(sid) or f"{LABELS['speaker'][lang]} {sid}"
    start = ms_to_ts(utt["start_ms"])
    flag  = utt.get("flag", "ok")

    # Build body — highlight flagged words when present
    words      = utt.get("words", [])
    flagged_ms = {w["start_ms"] for w in utt.get("flagged_words", [])}
    word_bg    = "#f8d7da" if flag == "unreliable" else "#fff3cd"

    if words and flagged_ms:
        parts = []
        for w in words:
            t = w["text"]
            if w["start_ms"] in flagged_ms:
                parts.append(
                    f'<mark style="background:{word_bg};border-radius:2px;padding:0 2px">{t}</mark>'
                )
            else:
                parts.append(t)
        body = " ".join(parts)
    else:
        body = utt["text"]

    # Utterance-level badge
    if flag == "unreliable":
        body = f"<em>{body}</em> 🔴"
    elif flag == "uncertain":
        body = f"{body} ⚠"

    return (
        f'<div style="margin-bottom:10px;line-height:1.5">'
        f'<span style="color:#888;font-size:0.82em;font-family:monospace">[{start}]</span>&nbsp;'
        f'<span style="color:{color};font-weight:700">{name}</span>&nbsp;&nbsp;'
        f'{body}'
        f'</div>'
    )

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def main() -> None:
    # Language toggle
    if "lang" not in st.session_state:
        st.session_state["lang"] = "English"

    with st.sidebar:
        st.session_state["lang"] = st.selectbox(
            "Language / Idioma",
            ["English", "Español"],
            index=["English", "Español"].index(st.session_state["lang"]),
        )

    lang = st.session_state["lang"]
    L = lambda key: LABELS[key][lang]  # noqa: E731

    # Shareable-link loading — runs before anything renders
    _qid = st.query_params.get("id")
    if _qid and _qid != st.session_state.get("_current_id"):
        _record = load_transcript(_qid)
        if _record:
            st.session_state["transcript"] = _record["transcript"]
            for _sid, _name in _record["speaker_names"].items():
                st.session_state[f"speaker_name_{_sid}"] = _name
            st.session_state["_current_id"] = _qid
        else:
            st.error(L("err_not_found"))

    # Header
    st.title(L("title"))
    st.caption(L("subtitle"))

    # Input
    api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if not api_key:
        st.warning(
            "⚠ **ASSEMBLYAI_API_KEY not found.** "
            "Add it to your `.env` file and restart the app."
        )

    url = st.text_input(L("url_label"), placeholder=L("url_ph"))
    st.markdown(
        f'<p style="text-align:center;color:#888;margin:4px 0">{L("or")}</p>',
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        L("upload_label"), type=["mp4", "mp3", "wav", "m4a"], help=L("upload_help")
    )
    if uploaded is not None:
        size_mb = uploaded.size / (1024 * 1024)
        st.caption(
            LABELS["file_info"][lang].format(name=uploaded.name, size=f"{size_mb:.1f} MB")
        )

    if st.button(L("btn"), type="primary"):
        has_url  = bool(url.strip())
        has_file = uploaded is not None

        if not has_url and not has_file:
            st.error(L("err_no_input"))
            st.stop()
        if has_url and has_file:
            st.error(L("err_both"))
            st.stop()

        # Save uploaded file to disk so download_audio can read it
        tmp_path = None
        if has_file:
            size_mb = uploaded.size / (1024 * 1024)
            if uploaded.size > 500 * 1024 * 1024:
                st.error(LABELS["err_too_large"][lang].format(size=f"{size_mb:.1f} MB"))
                st.stop()
            tmp_path = Path("audio_tmp") / uploaded.name
            tmp_path.parent.mkdir(exist_ok=True)
            tmp_path.write_bytes(uploaded.read())

        source = url.strip() if has_url else str(tmp_path)

        prog = st.progress(0, text=L("prog_dl"))
        try:
            # Download: real progress from yt-dlp (0 % → 30 %)
            def on_dl(frac: float) -> None:
                prog.progress(int(frac * 30), text=L("prog_dl"))

            dl = download_audio(source, "audio_tmp", on_progress=on_dl)
            prog.progress(35, text=L("prog_tx"))

            # Transcription: time-based progress (35 % → 90 %)
            def on_tx(frac: float) -> None:
                prog.progress(35 + int(frac * 55), text=L("prog_tx"))

            raw = transcribe_with_progress(
                dl["path"], api_key, dl["duration_seconds"], on_tx
            )
            prog.progress(92, text=L("prog_flag"))

            flagged = flag_transcript(raw)
            flagged["_title"] = dl["title"]
            st.session_state["transcript"] = flagged
            prog.progress(100, text=L("prog_done"))

            _tid  = save_transcript(flagged, {}, dl["title"])
            _base = os.environ.get("STREAMLIT_APP_URL", "http://localhost:8501")
            st.session_state["_saved_link"] = f"{_base}?id={_tid}"
            st.session_state["_current_id"] = _tid
            st.query_params["id"] = _tid
        except (ValueError, RuntimeError) as e:
            prog.empty()
            st.error(str(e))
            st.stop()
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

    # Transcript display
    t = st.session_state.get("transcript")
    if not t:
        return

    st.divider()
    st.subheader(L("transcript"))

    utterances = t.get("utterances", [])
    speakers   = sorted({u["speaker"] for u in utterances})
    dur        = t.get("duration_seconds", 0)
    dur_str    = f"{int(dur // 60)}m {int(dur % 60)}s"

    st.markdown(
        LABELS["summary"][lang].format(
            lang  = t.get("language", "?").upper(),
            dur   = dur_str,
            spk   = len(speakers),
            flags = t.get("low_confidence_count", 0),
        )
    )

    # Read speaker names set by the inputs below (empty on first render)
    speaker_names = {
        sid: st.session_state.get(f"speaker_name_{sid}", "")
        for sid in speakers
    }

    st.markdown(
        "".join(render_utterance(u, lang, speaker_names) for u in utterances),
        unsafe_allow_html=True,
    )

    if t.get("has_low_confidence_zones"):
        st.caption(L("legend"))

    # Shareable link (shown after every transcription and when loaded via URL)
    if "_saved_link" in st.session_state:
        st.info(f"{L('saved_link')}\n\n`{st.session_state['_saved_link']}`")

    # Speaker renaming
    st.divider()
    st.subheader(L("name_speakers"))
    for sid in speakers:
        st.text_input(
            LABELS["spk_name_lbl"][lang].format(sid=sid),
            placeholder=L("spk_name_ph"),
            key=f"speaker_name_{sid}",
        )

    st.divider()
    export_t  = substitute_names(t, speaker_names)
    slug      = "".join(c if c.isalnum() or c in "-_" else "_"
                        for c in t.get("_title", "transcript")).strip()[:50]
    dt_str    = datetime.now().strftime("%Y%m%d_%H%M%S")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label     = L("btn_dl_json"),
            data      = json.dumps(export_t, indent=2, ensure_ascii=False),
            file_name = f"transcript_{slug}_{dt_str}.json",
            mime      = "application/json",
        )
    with col2:
        st.download_button(
            label     = L("btn_dl_pdf"),
            data      = build_pdf(export_t, speaker_names),
            file_name = f"transcript_{slug}_{dt_str}.pdf",
            mime      = "application/pdf",
        )


if __name__ == "__main__":
    main()
