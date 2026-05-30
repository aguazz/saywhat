import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from downloader import download_audio
from exporters import build_pdf, substitute_names
from flagging import flag_transcript
from identifier import suggest_speaker_names
from storage import (complete_analysis, fail_analysis, load_transcript,
                     save_analysis, save_feedback, save_transcript)
from transcriber import transcribe_with_progress
from truth_checker.classifier import classify_claim
from truth_checker.evidence   import retrieve_evidence
from truth_checker.extractor  import extract_claims_from_turn
from truth_checker.segmenter  import segment_turns
from truth_checker.threader   import group_into_threads
from truth_checker.translator import translate_claim
from truth_checker.verifier   import verify_claim

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
    "prog_done":    {"English": "Done!",                           "Español": "Listo!"},
    "btn_dl_json":  {"English": "⬇  Download JSON",               "Español": "⬇  Descargar JSON"},
    "btn_dl_pdf":   {"English": "⬇  Download PDF",                "Español": "⬇  Descargar PDF"},
    "file_info":    {"English": "Selected: **{name}** ({size})",  "Español": "Seleccionado: **{name}** ({size})"},
    "err_too_large":{"English": "File is too large ({size}). Maximum allowed is 500 MB.",
                     "Español": "El archivo es demasiado grande ({size}). El máximo permitido es 500 MB."},
    "saved_link":   {"English": "Transcript saved. Share this link:",
                     "Español": "Transcripción guardada. Comparte este enlace:"},
    "err_not_found":{"English": "Transcript not found. The link may be invalid or the record was deleted.",
                     "Español": "Transcripción no encontrada. El enlace puede ser inválido o el registro fue eliminado."},
    "merge_lbl":    {"English": "Merge {sid} into…",    "Español": "Fusionar {sid} con…"},
    "merge_keep":   {"English": "Keep separate",          "Español": "Mantener separado"},
    "btn_suggest":  {"English": "✨  Suggest speaker names",
                     "Español": "✨  Sugerir nombres de hablantes"},
    "suggesting":   {"English": "Asking Claude to identify speakers…",
                     "Español": "Consultando a Claude para identificar hablantes…"},
    "suggest_ok":   {"English": "Names suggested — review and edit if needed.",
                     "Español": "Nombres sugeridos — revisa y edita si es necesario."},
    "suggest_low":  {"English": "⚠ Speaker {sid}: low confidence — please verify this name.",
                     "Español": "⚠ Hablante {sid}: baja confianza — por favor verifica este nombre."},
    "suggest_err":  {"English": "Could not suggest names: {err}",
                     "Español": "No se pudieron sugerir nombres: {err}"},
    # ── Analysis tab ────────────────────────────────────────────────────────
    "tab_transcript":    {"English": "Transcript",               "Español": "Transcripción"},
    "tab_analysis":      {"English": "Analysis",                 "Español": "Análisis"},
    "load_first":        {"English": "Load a transcript first — paste a URL or upload a file above.",
                          "Español": "Primero carga una transcripción — pega una URL o sube un archivo arriba."},
    "run_analysis":      {"English": "Run Analysis",             "Español": "Ejecutar análisis"},
    "analysis_cost":     {"English": "Estimated cost: ~$0.05–$0.15 (Claude Haiku + Sonnet)",
                          "Español": "Coste estimado: ~$0.05–$0.15 (Claude Haiku + Sonnet)"},
    "no_anthropic_an":   {"English": "Add ANTHROPIC_API_KEY to your .env to enable analysis.",
                          "Español": "Añade ANTHROPIC_API_KEY a tu .env para habilitar el análisis."},
    "prog_seg":          {"English": "Segmenting turns…",        "Español": "Segmentando turnos…"},
    "prog_extract":      {"English": "Extracting claims… ({i}/{n})",
                          "Español": "Extrayendo afirmaciones… ({i}/{n})"},
    "prog_classify":     {"English": "Classifying claims… ({i}/{n})",
                          "Español": "Clasificando afirmaciones… ({i}/{n})"},
    "prog_thread":       {"English": "Grouping into threads…",   "Español": "Agrupando en hilos…"},
    "analysis_summary":  {"English": "**{n}** claims across **{t}** threads from **{s}** speakers",
                          "Español": "**{n}** afirmaciones en **{t}** hilos de **{s}** hablantes"},
    "filter_speaker":    {"English": "Filter by speaker",        "Español": "Filtrar por hablante"},
    "filter_type":       {"English": "Filter by type",           "Español": "Filtrar por tipo"},
    "filter_all":        {"English": "All",                      "Español": "Todos"},
    "col_thread":        {"English": "Thread",                   "Español": "Hilo"},
    "col_speaker":       {"English": "Speaker",                  "Español": "Hablante"},
    "col_time":          {"English": "Time",                     "Español": "Tiempo"},
    "col_type":          {"English": "Type",                     "Español": "Tipo"},
    "col_checkable":     {"English": "Checkable",                "Español": "Verificable"},
    "col_claim":         {"English": "Claim",                    "Español": "Afirmación"},
    "btn_dl_csv":        {"English": "⬇  Download CSV",          "Español": "⬇  Descargar CSV"},
    "analysis_no_claims":{"English": "No claims were extracted. Try running the analysis again.",
                          "Español": "No se extrajeron afirmaciones. Intenta ejecutar el análisis de nuevo."},
    # ── Fact-check button + progress ────────────────────────────────────────
    "run_factcheck":     {"English": "Run Fact-Check",
                          "Español": "Ejecutar verificación"},
    "factcheck_cost":    {"English": "Estimated cost: ~$0.01–$0.05 per claim (Claude Sonnet + free APIs)",
                          "Español": "Coste estimado: ~$0.01–$0.05 por afirmación (Claude Sonnet + APIs gratuitas)"},
    "prog_factcheck":    {"English": "Fact-checking claim {i} of {n}…",
                          "Español": "Verificando afirmación {i} de {n}…"},
    # ── Verdict labels ───────────────────────────────────────────────────────
    "col_verdict":       {"English": "Verdict",          "Español": "Veredicto"},
    "verdict_true":      {"English": "True",             "Español": "Verdadero"},
    "verdict_partly_true":{"English": "Partly True",    "Español": "Parcialmente verdadero"},
    "verdict_contested": {"English": "Contested",        "Español": "Disputado"},
    "verdict_misleading":{"English": "Misleading",       "Español": "Engañoso"},
    "verdict_false":     {"English": "False",            "Español": "Falso"},
    "verdict_unverifiable":{"English": "Unverifiable",  "Español": "No verificable"},
    "verdict_subjective":{"English": "Subjective",      "Español": "Subjetivo"},
    "verdict_none":      {"English": "—",               "Español": "—"},
    # ── Expander detail ──────────────────────────────────────────────────────
    "in_favour":         {"English": "In favour:",      "Español": "A favor:"},
    "against":           {"English": "Against:",        "Español": "En contra:"},
    "sources":           {"English": "Sources",         "Español": "Fuentes"},
    # ── Feedback form ────────────────────────────────────────────────────────
    "report_error":      {"English": "Report an error",
                          "Español": "Reportar un error"},
    "feedback_question": {"English": "What is wrong with this verdict?",
                          "Español": "¿Qué está mal con este veredicto?"},
    "fb_incorrect":      {"English": "Incorrect",       "Español": "Incorrecto"},
    "fb_misleading":     {"English": "Misleading",      "Español": "Engañoso"},
    "fb_incomplete":     {"English": "Incomplete",      "Español": "Incompleto"},
    "feedback_note":     {"English": "Add a note (optional)",
                          "Español": "Añadir nota (opcional)"},
    "feedback_submit":   {"English": "Submit",          "Español": "Enviar"},
    "feedback_thanks":   {"English": "Thank you for your feedback.",
                          "Español": "Gracias por tu comentario."},
    # ── Translation toggle ───────────────────────────────────────────────────
    "translate_btn":     {"English": "🌐 Show in English",
                          "Español": "🌐 Mostrar en español"},
    "translation_label": {"English": "Translation (machine)",
                          "Español": "Traducción (automática)"},
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

    # API keys
    api_key       = os.environ.get("ASSEMBLYAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.warning(
            "⚠ **ASSEMBLYAI_API_KEY not found.** "
            "Add it to your `.env` file and restart the app."
        )

    # Input section
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
            def on_dl(frac: float) -> None:
                prog.progress(int(frac * 30), text=L("prog_dl"))

            dl = download_audio(source, "audio_tmp", on_progress=on_dl)
            prog.progress(35, text=L("prog_tx"))

            def on_tx(frac: float) -> None:
                prog.progress(35 + int(frac * 55), text=L("prog_tx"))

            raw = transcribe_with_progress(
                dl["path"], api_key, dl["duration_seconds"], on_tx
            )
            prog.progress(92, text=L("prog_flag"))

            flagged = flag_transcript(raw)
            flagged["_title"] = dl["title"]
            st.session_state["transcript"] = flagged
            # Clear any previous analysis when a new transcript is loaded
            st.session_state.pop("analysis", None)
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

    # ── Tabs (shown once a transcript is available) ──────────────────────────
    t = st.session_state.get("transcript")

    if t:
        st.divider()
        if "_saved_link" in st.session_state:
            st.info(f"{L('saved_link')}\n\n`{st.session_state['_saved_link']}`")

    tab_tx, tab_an = st.tabs([L("tab_transcript"), L("tab_analysis")])

    # ── Transcript tab ───────────────────────────────────────────────────────
    with tab_tx:
        if not t:
            st.info(L("load_first"))
        else:
            utterances = t.get("utterances", [])
            speakers   = sorted({u["speaker"] for u in utterances})
            dur        = t.get("duration_seconds", 0)
            dur_str    = f"{int(dur // 60)}m {int(dur % 60)}s"

            low_conf_note = []
            if "_name_suggestions" in st.session_state:
                for sid, info in st.session_state.pop("_name_suggestions").items():
                    name = info.get("name", "")
                    if name and name != "Unknown":
                        st.session_state[f"speaker_name_{sid}"] = name
                    if info.get("confidence") == "low":
                        low_conf_note.append(sid)

            speaker_names = {
                sid: st.session_state.get(f"speaker_name_{sid}", "")
                for sid in speakers
            }
            merge_map = {
                sid: st.session_state.get(f"speaker_merge_{sid}", sid)
                for sid in speakers
            }

            effective_speakers = len({merge_map.get(sid, sid) for sid in speakers})
            st.markdown(
                LABELS["summary"][lang].format(
                    lang  = t.get("language", "?").upper(),
                    dur   = dur_str,
                    spk   = effective_speakers,
                    flags = t.get("low_confidence_count", 0),
                )
            )

            st.subheader(L("name_speakers"))

            if anthropic_key:
                if st.button(L("btn_suggest")):
                    try:
                        with st.spinner(L("suggesting")):
                            suggestions = suggest_speaker_names(t, anthropic_key)
                        st.session_state["_name_suggestions"] = suggestions
                        st.rerun()
                    except Exception as e:
                        st.error(LABELS["suggest_err"][lang].format(err=str(e)[:200]))
            else:
                st.caption("Add ANTHROPIC_API_KEY to Streamlit Secrets to enable name suggestions.")

            for sid in speakers:
                effective  = merge_map.get(sid, sid)
                is_merged  = effective != sid
                col_name, col_merge = st.columns([3, 2])
                with col_name:
                    st.text_input(
                        LABELS["spk_name_lbl"][lang].format(sid=sid),
                        placeholder=L("spk_name_ph"),
                        key=f"speaker_name_{sid}",
                        disabled=is_merged,
                    )
                    if is_merged:
                        target_name = speaker_names.get(effective) or f"{LABELS['speaker'][lang]} {effective}"
                        st.caption(f"→ {target_name}")
                with col_merge:
                    other = [s for s in speakers if s != sid]
                    if other:
                        st.selectbox(
                            LABELS["merge_lbl"][lang].format(sid=sid),
                            options=[sid] + other,
                            format_func=lambda s, _sid=sid: (
                                L("merge_keep") if s == _sid
                                else (speaker_names.get(s) or f"{LABELS['speaker'][lang]} {s}")
                            ),
                            key=f"speaker_merge_{sid}",
                        )

            for sid in low_conf_note:
                st.caption(LABELS["suggest_low"][lang].format(sid=sid))

            # Re-read after widgets so merged_utterances uses current values
            speaker_names = {
                sid: st.session_state.get(f"speaker_name_{sid}", "")
                for sid in speakers
            }
            merge_map = {
                sid: st.session_state.get(f"speaker_merge_{sid}", sid)
                for sid in speakers
            }

            merged_utterances = [
                {**u, "speaker": merge_map.get(u["speaker"], u["speaker"])}
                for u in utterances
            ]

            with st.expander(L("transcript"), expanded=True):
                st.markdown(
                    "".join(render_utterance(u, lang, speaker_names) for u in merged_utterances),
                    unsafe_allow_html=True,
                )
                if t.get("has_low_confidence_zones"):
                    st.caption(L("legend"))

            st.divider()
            export_t = substitute_names({**t, "utterances": merged_utterances}, speaker_names)
            slug     = "".join(c if c.isalnum() or c in "-_" else "_"
                               for c in t.get("_title", "transcript")).strip()[:50]
            dt_str   = datetime.now().strftime("%Y%m%d_%H%M%S")

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
                    data      = build_pdf(export_t),
                    file_name = f"transcript_{slug}_{dt_str}.pdf",
                    mime      = "application/pdf",
                )

    # ── Analysis tab ─────────────────────────────────────────────────────────
    with tab_an:
        if not t:
            st.info(L("load_first"))
        else:
            utterances_an   = t.get("utterances", [])
            speakers_an     = sorted({u["speaker"] for u in utterances_an})
            transcript_lang = t.get("language", "en")
            speaker_names_an = {
                sid: st.session_state.get(f"speaker_name_{sid}", "") or f"{L('speaker')} {sid}"
                for sid in speakers_an
            }

            # ── Run Analysis button ────────────────────────────────────────────
            if not anthropic_key:
                st.warning(L("no_anthropic_an"))

            col_btn, col_note = st.columns([1, 3])
            with col_btn:
                run_clicked = st.button(
                    L("run_analysis"), type="primary", disabled=not anthropic_key,
                )
            with col_note:
                st.caption(L("analysis_cost"))

            if run_clicked and anthropic_key:
                transcript_id = st.session_state.get("_current_id", "unknown")
                aid = save_analysis(transcript_id, "claude-haiku-4-5-20251001 + claude-sonnet-4-6")
                st.session_state["_analysis_id"] = aid
                prog = st.progress(0, text=L("prog_seg"))
                try:
                    turns = segment_turns(utterances_an)
                    prog.progress(5, text=L("prog_seg"))

                    all_claims: list[dict] = []
                    for i, turn in enumerate(turns):
                        claims = extract_claims_from_turn(turn, anthropic_key)
                        all_claims.extend(claims)
                        pct = 5 + int((i + 1) / max(len(turns), 1) * 50)
                        prog.progress(pct, text=LABELS["prog_extract"][lang].format(i=i + 1, n=len(turns)))

                    classified: list[dict] = []
                    for i, claim in enumerate(all_claims):
                        result = classify_claim(claim, anthropic_key)
                        classified.append(result)
                        pct = 55 + int((i + 1) / max(len(all_claims), 1) * 30)
                        prog.progress(pct, text=LABELS["prog_classify"][lang].format(i=i + 1, n=len(all_claims)))

                    prog.progress(85, text=L("prog_thread"))
                    threads = group_into_threads(classified, anthropic_key)
                    prog.progress(100, text=L("prog_done"))

                    st.session_state["analysis"] = {"claims": classified, "threads": threads}
                    st.session_state.pop("verdicts", None)
                    complete_analysis(aid, {"claims": classified, "threads": threads})

                except Exception as e:
                    fail_analysis(aid, str(e))
                    prog.empty()
                    st.error(str(e))
                    st.stop()

            # ── Run Fact-Check button ──────────────────────────────────────────
            analysis = st.session_state.get("analysis")
            if analysis:
                col_fc, col_fc_note = st.columns([1, 3])
                with col_fc:
                    fc_clicked = st.button(L("run_factcheck"), disabled=not anthropic_key)
                with col_fc_note:
                    st.caption(L("factcheck_cost"))

                if fc_clicked and anthropic_key:
                    checkable = [
                        c for c in analysis.get("claims", [])
                        if c.get("checkable") and not c.get("satirical")
                    ]
                    verdicts: dict = {}
                    prog_fc = st.progress(
                        0,
                        text=LABELS["prog_factcheck"][lang].format(i=0, n=len(checkable)),
                    )
                    for i, claim in enumerate(checkable):
                        try:
                            evidence = retrieve_evidence(
                                claim.get("suggested_query") or claim["text"],
                                language=transcript_lang,
                            )
                            vdict = verify_claim(claim, evidence, anthropic_key)
                        except Exception as exc:
                            vdict = {
                                "claim_id": claim["id"], "verdict": "unverifiable",
                                "confidence": 0.0,
                                "explanation": f"Error during fact-check: {exc}",
                                "for_the_claim": "", "against_the_claim": "",
                                "key_source": "", "all_sources": [],
                            }
                        verdicts[claim["id"]] = vdict
                        pct = int((i + 1) / max(len(checkable), 1) * 100)
                        prog_fc.progress(
                            pct,
                            text=LABELS["prog_factcheck"][lang].format(i=i + 1, n=len(checkable)),
                        )
                    st.session_state["verdicts"] = verdicts

            # ── Display results ────────────────────────────────────────────────
            if analysis:
                claims   = analysis.get("claims", [])
                threads  = analysis.get("threads", [])
                verdicts = st.session_state.get("verdicts", {})

                if not claims:
                    st.info(L("analysis_no_claims"))
                else:
                    n_spk = len({c["speaker"] for c in claims})
                    st.markdown(LABELS["analysis_summary"][lang].format(
                        n=len(claims), t=len(threads), s=n_spk,
                    ))

                    # Filters
                    all_lbl   = L("filter_all")
                    spk_opts  = [all_lbl] + [
                        speaker_names_an.get(s, s)
                        for s in sorted({c["speaker"] for c in claims})
                    ]
                    type_opts = [all_lbl] + sorted({c.get("claim_type", "") for c in claims})

                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        sel_spk  = st.selectbox(L("filter_speaker"), spk_opts)
                    with col_f2:
                        sel_type = st.selectbox(L("filter_type"), type_opts)

                    filtered = claims
                    if sel_spk != all_lbl:
                        sid_lookup = {v: k for k, v in speaker_names_an.items()}
                        target_sid = sid_lookup.get(sel_spk, sel_spk)
                        filtered   = [c for c in filtered if c["speaker"] == target_sid]
                    if sel_type != all_lbl:
                        filtered = [c for c in filtered if c.get("claim_type") == sel_type]

                    sorted_claims = sorted(
                        filtered,
                        key=lambda c: (c.get("thread_id", ""), c.get("start_ms", 0)),
                    )

                    # Verdict badge helper
                    _VSTYLE = {
                        "true":           ("#d4edda", L("verdict_true")),
                        "partially_true": ("#fff3cd", L("verdict_partly_true")),
                        "contested":      ("#fde8c8", L("verdict_contested")),
                        "misleading":     ("#fde8c8", L("verdict_misleading")),
                        "false":          ("#f8d7da", L("verdict_false")),
                        "unverifiable":   ("#e2e3e5", L("verdict_unverifiable")),
                        "subjective":     ("#e2e3e5", L("verdict_subjective")),
                    }

                    def badge(v: str) -> str:
                        bg, lbl = _VSTYLE.get(v, ("#e2e3e5", L("verdict_none")))
                        return (
                            f'<span style="background:{bg};border-radius:4px;'
                            f'padding:2px 7px;font-size:0.82em;white-space:nowrap">{lbl}</span>'
                        )

                    # Table — HTML with badge column when verdicts present, plain dataframe otherwise
                    if verdicts:
                        th = "padding:6px 8px;text-align:left;border-bottom:2px solid #dee2e6;font-size:0.88em"
                        td = "padding:5px 8px;border-bottom:1px solid #f0f0f0;font-size:0.85em;vertical-align:top"
                        hdrs = [
                            L("col_thread"), L("col_speaker"), L("col_time"),
                            L("col_type"), L("col_checkable"), L("col_verdict"), L("col_claim"),
                        ]
                        hdr_html = "".join(f"<th style='{th}'>{h}</th>" for h in hdrs)
                        rows_html = ""
                        for c in sorted_claims:
                            v_key  = verdicts.get(c["id"], {}).get("verdict", "")
                            short  = (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"]
                            rows_html += (
                                f"<tr>"
                                f"<td style='{td}'>{c.get('thread_id','')}</td>"
                                f"<td style='{td}'>{speaker_names_an.get(c['speaker'], c['speaker'])}</td>"
                                f"<td style='{td}'>{ms_to_ts(c.get('start_ms', 0))}</td>"
                                f"<td style='{td}'>{c.get('claim_type','')}</td>"
                                f"<td style='{td}'>{'yes' if c.get('checkable') else 'no'}</td>"
                                f"<td style='{td}'>{badge(v_key)}</td>"
                                f"<td style='{td}'>{short}</td>"
                                f"</tr>"
                            )
                        st.markdown(
                            f"<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse'>"
                            f"<thead><tr>{hdr_html}</tr></thead><tbody>{rows_html}</tbody></table></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        rows = [
                            {
                                L("col_thread"):   c.get("thread_id", ""),
                                L("col_speaker"):  speaker_names_an.get(c["speaker"], c["speaker"]),
                                L("col_time"):     ms_to_ts(c.get("start_ms", 0)),
                                L("col_type"):     c.get("claim_type", ""),
                                L("col_checkable"): "yes" if c.get("checkable") else "no",
                                L("col_claim"):    (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"],
                            }
                            for c in sorted_claims
                        ]
                        st.dataframe(rows, use_container_width=True)

                    # CSV export (always includes Verdict column)
                    if sorted_claims:
                        csv_rows = [
                            {
                                L("col_thread"):   c.get("thread_id", ""),
                                L("col_speaker"):  speaker_names_an.get(c["speaker"], c["speaker"]),
                                L("col_time"):     ms_to_ts(c.get("start_ms", 0)),
                                L("col_type"):     c.get("claim_type", ""),
                                L("col_checkable"): "yes" if c.get("checkable") else "no",
                                L("col_verdict"):  verdicts.get(c["id"], {}).get("verdict", ""),
                                L("col_claim"):    c["text"],
                            }
                            for c in sorted_claims
                        ]
                        buf = io.StringIO()
                        writer = csv.DictWriter(buf, fieldnames=list(csv_rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(csv_rows)
                        st.download_button(
                            label     = L("btn_dl_csv"),
                            data      = buf.getvalue().encode("utf-8"),
                            file_name = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime      = "text/csv",
                        )

                    # ── Verdict expanders ──────────────────────────────────────
                    if verdicts:
                        st.divider()
                        aid_fb = st.session_state.get("_analysis_id", "")
                        for c in sorted_claims:
                            vdict = verdicts.get(c["id"])
                            if not vdict:
                                continue
                            spk_lbl    = speaker_names_an.get(c["speaker"], c["speaker"])
                            short_text = (c["text"][:40] + "…") if len(c["text"]) > 40 else c["text"]
                            with st.expander(f"[{ms_to_ts(c.get('start_ms', 0))}] {spk_lbl} — {short_text}"):
                                st.markdown(f"**{c['text']}**")

                                # Translation toggle — only when transcript language ≠ UI language
                                ui_lang_code = "en" if lang == "English" else "es"
                                if transcript_lang != ui_lang_code:
                                    t_cache_key = f"translation_{cid}_{ui_lang_code}"
                                    if t_cache_key not in st.session_state:
                                        if st.button(L("translate_btn"), key=f"tr_btn_{cid}"):
                                            translation = translate_claim(
                                                c["text"], transcript_lang, ui_lang_code, anthropic_key,
                                            )
                                            st.session_state[t_cache_key] = translation
                                            st.rerun()
                                    if t_cache_key in st.session_state:
                                        st.info(
                                            f"**{L('translation_label')}:** "
                                            f"{st.session_state[t_cache_key]}"
                                        )

                                st.markdown("---")

                                v_key = vdict.get("verdict", "")
                                st.markdown(badge(v_key), unsafe_allow_html=True)
                                conf_pct = int(vdict.get("confidence", 0.0) * 100)
                                st.progress(conf_pct, text=f"{L('col_verdict')}: {conf_pct}%")

                                st.markdown(vdict.get("explanation", ""))

                                if v_key == "contested":
                                    if vdict.get("for_the_claim"):
                                        st.markdown(f"**{L('in_favour')}** {vdict['for_the_claim']}")
                                    if vdict.get("against_the_claim"):
                                        st.markdown(f"**{L('against')}** {vdict['against_the_claim']}")

                                sources = vdict.get("all_sources") or []
                                if sources:
                                    st.markdown(f"**{L('sources')}**")
                                    for src in sources:
                                        title_s = src.get("title", "Source") if isinstance(src, dict) else str(src)
                                        url_s   = src.get("url", "")        if isinstance(src, dict) else ""
                                        st.markdown(f"- [{title_s}]({url_s})" if url_s else f"- {title_s}")

                                # Feedback
                                cid    = c["id"]
                                fb_key = f"feedback_open_{cid}"
                                if not st.session_state.get(fb_key):
                                    if st.button(f"👎 {L('report_error')}", key=f"fb_btn_{cid}"):
                                        st.session_state[fb_key] = True
                                        st.rerun()
                                else:
                                    with st.form(key=f"fb_form_{cid}"):
                                        rating = st.radio(
                                            L("feedback_question"),
                                            [L("fb_incorrect"), L("fb_misleading"), L("fb_incomplete")],
                                            horizontal=True,
                                        )
                                        note      = st.text_input(L("feedback_note"), max_chars=300)
                                        submitted = st.form_submit_button(L("feedback_submit"))
                                    if submitted:
                                        try:
                                            save_feedback(cid, aid_fb, rating, note)
                                        except Exception:
                                            pass
                                        st.session_state[fb_key] = False
                                        st.success(L("feedback_thanks"))


if __name__ == "__main__":
    main()
