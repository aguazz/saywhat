import csv
import io
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

import streamlit as st
from dotenv import load_dotenv

from downloader import download_audio
from exporters import build_analysis_pdf, build_pdf, substitute_names
from flagging import flag_transcript
from identifier import suggest_speaker_names
from storage import (complete_analysis, fail_analysis, load_analysis,
                     load_transcript, save_analysis, save_feedback, save_transcript)
from transcriber import transcribe_with_progress
import streamlit.components.v1 as components

from truth_checker.classifier import classify_claim
from truth_checker.evidence   import retrieve_evidence
from truth_checker.extractor  import extract_claims_from_turn
from truth_checker.responder  import detect_responses
from truth_checker.segmenter  import segment_turns
from truth_checker.threader   import group_into_threads
from truth_checker.translator import translate_claim
from truth_checker.verifier   import verify_claim
from truth_checker.rhetorician import analyze_turn_rhetoric
from truth_checker.reporter    import generate_speaker_summary
from truth_checker.scorer      import compute_speaker_scores
from truth_checker.visualizer  import build_graph_html

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
    "factcheck_cost":    {"English": "Estimated cost: ~$0.01–$0.05 per checkable claim (Claude Sonnet + free APIs)",
                          "Español": "Coste estimado: ~$0.01–$0.05 por afirmación verificable (Claude Sonnet + APIs gratuitas)"},
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
    "translate_btn":     {"English": "🌐 Show in English",
                          "Español": "🌐 Mostrar en español"},
    "translation_label": {"English": "Translation (machine)",
                          "Español": "Traducción (automática)"},
    # ── Sub-tabs ─────────────────────────────────────────────────────────────
    "subtab_claims":     {"English": "Claims",               "Español": "Afirmaciones"},
    "subtab_map":        {"English": "Argument Map",         "Español": "Mapa de argumentos"},
    # ── Detect Responses ─────────────────────────────────────────────────────
    "detect_responses":  {"English": "Detect Responses",
                          "Español": "Detectar respuestas"},
    "detect_responses_note": {
        "English": "Estimated cost: ~$0.002–$0.03 per claim depending on model and batch size",
        "Español": "Coste estimado: ~$0.002–$0.03 por afirmación según modelo y tamaño de lote",
    },
    "detecting_responses": {
        "English": "Detecting response relationships between speakers…",
        "Español": "Detectando relaciones de respuesta entre hablantes…",
    },
    # ── Argument Map ─────────────────────────────────────────────────────────
    "run_analysis_first": {
        "English": "Run Analysis first to see the argument map.",
        "Español": "Ejecuta el análisis primero para ver el mapa de argumentos.",
    },
    "run_detect_first": {
        "English": "Run Detect Responses (in the Claims tab) to enable the argument map.",
        "Español": "Ejecuta Detectar respuestas (en la pestaña Afirmaciones) para habilitar el mapa.",
    },
    "legend_heading":      {"English": "Legend",                    "Español": "Leyenda"},
    "legend_node_color":   {"English": "Node color = speaker",      "Español": "Color del nodo = hablante"},
    "legend_node_shape":   {"English": "Node shape = claim type",   "Español": "Forma del nodo = tipo de afirmación"},
    "legend_edge_color":   {"English": "Edge color = relationship",  "Español": "Color del arco = relación"},
    # ── Rhetorical Profile sub-tab ───────────────────────────────────────────
    "subtab_rhetoric":    {"English": "Rhetorical Profile",          "Español": "Perfil retórico"},
    "run_rhetoric":       {"English": "Analyze Rhetoric",            "Español": "Analizar retórica"},
    "rhetoric_cost":      {"English": "Estimated cost: ~$0.01–$0.03 per turn (Claude Sonnet)",
                           "Español": "Coste estimado: ~$0.01–$0.03 por turno (Claude Sonnet)"},
    "rhetoric_progress":  {"English": "Analyzing turn {i} of {n}…", "Español": "Analizando turno {i} de {n}…"},
    "rhetoric_run_first": {"English": "Run Rhetoric Analysis first.",
                           "Español": "Ejecuta primero el análisis retórico."},
    "rhetoric_fallacies": {"English": "Logical fallacies",           "Español": "Falacias lógicas"},
    "rhetoric_devices":   {"English": "Rhetorical devices",          "Español": "Recursos retóricos"},
    "rhetoric_footer":    {
        "English": "Rhetorical devices are not always flaws. Labels show technique, not quality.",
        "Español": "Los recursos retóricos no son siempre defectos. Las etiquetas indican técnica, no calidad.",
    },
    # ── Speaker Report sub-tab ───────────────────────────────────────────────
    "subtab_report":      {"English": "Speaker Report",             "Español": "Informe de hablantes"},
    "run_report":         {"English": "Generate Speaker Report",    "Español": "Generar informe de hablantes"},
    "report_cost":        {"English": "Estimated cost: ~$0.01–$0.02 per speaker (Claude Sonnet)",
                           "Español": "Coste estimado: ~$0.01–$0.02 por hablante (Claude Sonnet)"},
    "report_need_data":   {
        "English": "Run at least one of: Fact-Check, Detect Responses, or Analyze Rhetoric first.",
        "Español": "Ejecuta al menos uno de: Verificación, Detectar respuestas o Analizar retórica primero.",
    },
    "report_generating":  {"English": "Generating report for {name}…",
                           "Español": "Generando informe para {name}…"},
    "report_run_first":   {
        "English": "Generate a Speaker Report (button in the Claims tab) to see this section.",
        "Español": "Genera un informe de hablantes (botón en la pestaña Afirmaciones) para ver esta sección.",
    },
    "metric_reliability":  {"English": "Reliability",               "Español": "Fiabilidad"},
    "metric_factchecked":  {"English": "Supported claims",          "Español": "Afirmaciones respaldadas"},
    "metric_direct_resp":  {"English": "Direct response rate",      "Español": "Tasa de respuesta directa"},
    "metric_fallacies":    {"English": "Logical fallacies",         "Español": "Falacias lógicas"},
    "metric_supported":    {"English": "{n} of {total}",            "Español": "{n} de {total}"},
    "metric_na":           {"English": "N/A",                       "Español": "N/D"},
    "chart_verdicts":      {"English": "Verdict distribution",      "Español": "Distribución de veredictos"},
    "btn_dl_analysis_pdf": {"English": "⬇  Download Analysis PDF",  "Español": "⬇  Descargar PDF de análisis"},
    "btn_dl_analysis_json":{"English": "⬇  Download Analysis JSON", "Español": "⬇  Descargar JSON de análisis"},
    # ── JSON import ──────────────────────────────────────────────────────────
    "upload_json_label":   {"English": "Upload saved transcript JSON",
                            "Español": "Subir JSON de transcripción guardado"},
    "upload_json_help":    {"English": "Exported from Transcript tab → ⬇ Download JSON",
                            "Español": "Exportado desde Transcripción → ⬇ Descargar JSON"},
    "load_json_btn":       {"English": "Load transcript from JSON",  "Español": "Cargar transcripción desde JSON"},
    "json_loaded":         {"English": "Transcript loaded from JSON file.",
                            "Español": "Transcripción cargada desde archivo JSON."},
    "upload_analysis_expander": {"English": "Load saved analysis JSON",
                                 "Español": "Cargar JSON de análisis guardado"},
    "upload_analysis_label":{"English": "Upload analysis JSON",      "Español": "Subir JSON de análisis"},
    "upload_analysis_help": {"English": "Exported from Analysis tab → ⬇ Download Analysis JSON",
                             "Español": "Exportado desde Análisis → ⬇ Descargar JSON de análisis"},
    "load_analysis_json_btn":{"English": "Load analysis",            "Español": "Cargar análisis"},
    "analysis_json_loaded":{"English": "Analysis loaded from JSON file.",
                            "Español": "Análisis cargado desde archivo JSON."},
    "err_invalid_json":    {"English": "Could not read the JSON file — check it is valid.",
                            "Español": "No se pudo leer el archivo JSON — comprueba que es válido."},
    "err_not_transcript_json": {"English": "This file does not contain transcript data (no 'utterances' key).",
                                "Español": "Este archivo no contiene datos de transcripción (falta clave 'utterances')."},
    "err_not_analysis_json":   {"English": "This file does not contain analysis data (no 'analysis.claims' key).",
                                "Español": "Este archivo no contiene datos de análisis (falta 'analysis.claims')."},
    # ── Detect Responses progress ────────────────────────────────────────────
    "prog_detect":         {"English": "Detecting response {i} of {n}…",
                            "Español": "Detectando respuesta {i} de {n}…"},
    # ── Pipeline settings ────────────────────────────────────────────────────
    "settings_expander":   {"English": "⚙️ Cost / quality settings",
                            "Español": "⚙️ Ajustes de coste / calidad"},
    "resp_model_label":    {"English": "Response detection model",
                            "Español": "Modelo — detección de respuestas"},
    "rhet_model_label":    {"English": "Rhetoric analysis model",
                            "Español": "Modelo — análisis retórico"},
    "resp_batch_label":    {"English": "Claims per API call (batching)",
                            "Español": "Afirmaciones por llamada (lotes)"},
    "model_haiku":         {"English": "Haiku · faster, ~12× cheaper",
                            "Español": "Haiku · más rápido, ~12× más barato"},
    "model_sonnet":        {"English": "Sonnet · best quality",
                            "Español": "Sonnet · mayor calidad"},
    "settings_tip":        {
        "English": (
            "**Haiku** is recommended for both steps unless you need maximum precision. "
            "**Batch size 5** gives ~5× fewer API calls with minimal quality loss. "
            "Fact-checking runs only on factual / statistical / comparative claims."
        ),
        "Español": (
            "**Haiku** es recomendable en ambos pasos salvo que necesites máxima precisión. "
            "**Lote 5** reduce ~5× las llamadas con pérdida mínima de calidad. "
            "La verificación solo se ejecuta en afirmaciones factuales / estadísticas / comparativas."
        ),
    },
    "saved_link_full":     {
        "English": "Transcript & analysis saved. Share this link:",
        "Español": "Transcripción y análisis guardados. Comparte este enlace:",
    },
    "analysis_loaded":     {
        "English": "Analysis loaded from saved link.",
        "Español": "Análisis cargado desde enlace guardado.",
    },
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
    # Single-char IDs from AssemblyAI ("A","B"…) use the original formula.
    # Multi-char IDs (from re-imported substituted JSONs or custom names) use a
    # deterministic sum of char codes so the colour is stable across reruns.
    if len(sid) == 1:
        color = SPEAKER_COLORS[min(ord(sid) - ord("A"), len(SPEAKER_COLORS) - 1)]
    else:
        color = SPEAKER_COLORS[sum(ord(c) for c in sid) % len(SPEAKER_COLORS)]
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

    _qaid = st.query_params.get("analysis")
    if _qaid and _qaid != st.session_state.get("_current_analysis_id"):
        _arecord = load_analysis(_qaid)
        if _arecord and _arecord.get("status") == "complete":
            _ajson = _arecord.get("analysis_json") or {}
            st.session_state["analysis"] = {
                "claims":  _ajson.get("claims", []),
                "threads": _ajson.get("threads", []),
            }
            st.session_state["verdicts"]       = _ajson.get("verdicts", {})
            st.session_state["speaker_report"] = _ajson.get("speaker_report", {})
            st.session_state["analysis_id"]    = _qaid
            st.session_state["_current_analysis_id"]      = _qaid
            st.session_state["_analysis_loaded_from_link"] = True

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

    # ── Transcript JSON import ───────────────────────────────────────────────
    st.markdown(
        f'<p style="text-align:center;color:#888;margin:4px 0">{L("or")}</p>',
        unsafe_allow_html=True,
    )
    json_tx_file = st.file_uploader(
        L("upload_json_label"), type=["json"],
        help=L("upload_json_help"), key="json_transcript_upload",
    )
    if json_tx_file is not None:
        if st.button(L("load_json_btn")):
            try:
                data = json.loads(json_tx_file.read())
                if "utterances" not in data:
                    st.error(L("err_not_transcript_json"))
                else:
                    # Normalise speaker IDs: if utterances use multi-char IDs
                    # (e.g. "Speaker A" from a substituted export), remap them
                    # back to single uppercase letters so the rest of the app works.
                    raw_speakers = sorted({u["speaker"] for u in data["utterances"]})
                    if any(len(s) > 1 for s in raw_speakers):
                        sid_map = {s: chr(ord("A") + i) for i, s in enumerate(raw_speakers)}
                        for u in data["utterances"]:
                            u["speaker"] = sid_map[u["speaker"]]
                    st.session_state["transcript"] = data
                    for key in ("analysis", "verdicts", "responses", "rhetoric",
                                "speaker_report", "_saved_link", "_has_analysis_link",
                                "_current_id", "analysis_id"):
                        st.session_state.pop(key, None)
                    st.success(L("json_loaded"))
                    st.rerun()
            except Exception:
                st.error(L("err_invalid_json"))

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
            _link_lbl = L("saved_link_full") if st.session_state.get("_has_analysis_link") else L("saved_link")
            st.info(f"{_link_lbl}\n\n`{st.session_state['_saved_link']}`")
        if st.session_state.get("_analysis_loaded_from_link"):
            st.success(L("analysis_loaded"))

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

            # ── Analysis JSON import ───────────────────────────────────────────
            with st.expander(L("upload_analysis_expander")):
                json_an_file = st.file_uploader(
                    L("upload_analysis_label"), type=["json"],
                    help=L("upload_analysis_help"), key="json_analysis_upload",
                )
                if json_an_file is not None:
                    if st.button(L("load_analysis_json_btn")):
                        try:
                            data = json.loads(json_an_file.read())
                            an = data.get("analysis", {})
                            if not isinstance(an.get("claims"), list):
                                st.error(L("err_not_analysis_json"))
                            else:
                                st.session_state["analysis"]       = an
                                st.session_state["verdicts"]       = data.get("verdicts", {})
                                st.session_state["speaker_report"] = data.get("speaker_report", {})
                                st.session_state.pop("responses", None)
                                st.session_state.pop("rhetoric", None)
                                st.success(L("analysis_json_loaded"))
                                st.rerun()
                        except Exception:
                            st.error(L("err_invalid_json"))

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
                    st.session_state.pop("responses", None)
                    st.session_state.pop("rhetoric", None)
                    st.session_state.pop("speaker_report", None)
                    complete_analysis(aid, {"claims": classified, "threads": threads})

                    # Update shareable link to include analysis ID
                    st.session_state["analysis_id"] = aid
                    st.session_state["_current_analysis_id"] = aid
                    _base_an = os.environ.get("STREAMLIT_APP_URL", "http://localhost:8501")
                    _tid_an  = st.session_state.get("_current_id", "")
                    if _tid_an:
                        st.session_state["_saved_link"]      = f"{_base_an}?id={_tid_an}&analysis={aid}"
                        st.session_state["_has_analysis_link"] = True

                    # Force a clean re-render so the results appear immediately.
                    # (Setting st.query_params mid-run can interrupt rendering in
                    # some Streamlit versions; st.rerun() is the safe alternative.)
                    st.rerun()

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

                # Claim types that can actually be verified against external evidence.
                # Causal, interpretive, moral, and anecdotal claims almost always
                # return "unverifiable" and waste API calls.
                _VERIFIABLE_TYPES = {"factual", "statistical", "comparative"}

                if fc_clicked and anthropic_key:
                    checkable = [
                        c for c in analysis.get("claims", [])
                        if c.get("checkable")
                        and not c.get("satirical")
                        and c.get("claim_type") in _VERIFIABLE_TYPES
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

            # ── Sub-tabs ───────────────────────────────────────────────────────
            if analysis:
                subtab_claims, subtab_map, subtab_rhetoric, subtab_report = st.tabs(
                    [L("subtab_claims"), L("subtab_map"), L("subtab_rhetoric"), L("subtab_report")]
                )

                # ── Claims sub-tab ─────────────────────────────────────────────
                with subtab_claims:
                    # ── Pipeline settings ──────────────────────────────────────
                    with st.expander(L("settings_expander")):
                        _s1, _s2, _s3 = st.columns([2, 2, 1])
                        with _s1:
                            _resp_model_choice = st.radio(
                                L("resp_model_label"),
                                [L("model_haiku"), L("model_sonnet")],
                                index=0,
                                key="resp_model_radio",
                            )
                        with _s2:
                            _rhet_model_choice = st.radio(
                                L("rhet_model_label"),
                                [L("model_haiku"), L("model_sonnet")],
                                index=0,
                                key="rhet_model_radio",
                            )
                        with _s3:
                            _resp_batch = st.select_slider(
                                L("resp_batch_label"),
                                options=[1, 3, 5, 10],
                                value=1,
                                key="resp_batch_slider",
                            )
                        st.caption(L("settings_tip"))

                    # Resolve model IDs from widget return values
                    _resp_model      = "claude-haiku-4-5-20251001" if _resp_model_choice == L("model_haiku") else "claude-sonnet-4-6"
                    _rhet_model      = "claude-haiku-4-5-20251001" if _rhet_model_choice == L("model_haiku") else "claude-sonnet-4-6"
                    _resp_batch_size = _resp_batch

                    # ── Dynamic cost estimates ─────────────────────────────────
                    # Rough per-API-call cost ranges (USD) for each model.
                    # Detect Responses: ~400 tokens in + ~150 out per call.
                    # Rhetoric: ~800 tokens in + ~300 out per call (longer turns).
                    _RESP_CALL_COST = {
                        "claude-haiku-4-5-20251001": (0.0008, 0.002),
                        "claude-sonnet-4-6":         (0.006,  0.018),
                    }
                    _RHET_CALL_COST = {
                        "claude-haiku-4-5-20251001": (0.001,  0.004),
                        "claude-sonnet-4-6":         (0.010,  0.035),
                    }

                    _n_claims  = len(analysis.get("claims", []))
                    _n_turns   = len({c.get("turn_index") for c in analysis.get("claims", [])})

                    # Number of API calls = ceiling(_n_claims / batch_size)
                    _n_dr_calls = max(1, (_n_claims + _resp_batch_size - 1) // _resp_batch_size)
                    _dr_lo, _dr_hi = _RESP_CALL_COST[_resp_model]
                    _dr_lo_tot, _dr_hi_tot = _dr_lo * _n_dr_calls, _dr_hi * _n_dr_calls

                    _rh_lo, _rh_hi = _RHET_CALL_COST[_rhet_model]
                    _rh_lo_tot, _rh_hi_tot = _rh_lo * _n_turns, _rh_hi * _n_turns

                    def _fmt(lo: float, hi: float) -> str:
                        if hi < 0.01:
                            return f"~${lo:.3f}–${hi:.3f}"
                        return f"~${lo:.2f}–${hi:.2f}"

                    _dr_note = (
                        f"{_fmt(_dr_lo_tot, _dr_hi_tot)} "
                        f"({_n_claims} claims · {_n_dr_calls} API call{'s' if _n_dr_calls != 1 else ''} · "
                        f"{'Haiku' if 'haiku' in _resp_model else 'Sonnet'}, batch {_resp_batch_size})"
                    )
                    _rh_note = (
                        f"{_fmt(_rh_lo_tot, _rh_hi_tot)} "
                        f"({_n_turns} turns · "
                        f"{'Haiku' if 'haiku' in _rhet_model else 'Sonnet'})"
                    )

                    # ── Detect Responses button
                    col_dr, col_dr_note = st.columns([1, 3])
                    with col_dr:
                        dr_clicked = st.button(L("detect_responses"), disabled=not anthropic_key)
                    with col_dr_note:
                        st.caption(_dr_note)

                    if dr_clicked and anthropic_key:
                        _dr_claims = sorted(
                            analysis.get("claims", []),
                            key=lambda c: c.get("start_ms", 0),
                        )
                        _dr_total = max(len(_dr_claims) - 1, 1)
                        _prog_dr  = st.progress(
                            0,
                            text=LABELS["prog_detect"][lang].format(i=0, n=_dr_total),
                        )
                        def _dr_progress(i: int, n: int) -> None:
                            _prog_dr.progress(
                                int(i / max(n, 1) * 100),
                                text=LABELS["prog_detect"][lang].format(i=i, n=n),
                            )
                        try:
                            st.session_state["responses"] = detect_responses(
                                _dr_claims, anthropic_key,
                                on_progress=_dr_progress,
                                model=_resp_model,
                                batch_size=_resp_batch_size,
                            )
                        except Exception as exc:
                            _prog_dr.empty()
                            st.error(str(exc))

                    # Analyze Rhetoric button
                    col_rh, col_rh_note = st.columns([1, 3])
                    with col_rh:
                        rh_clicked = st.button(L("run_rhetoric"), disabled=not anthropic_key)
                    with col_rh_note:
                        st.caption(_rh_note)

                    if rh_clicked and anthropic_key:
                        turns_rh = segment_turns(utterances_an)
                        rh_results: list[dict] = []
                        prog_rh = st.progress(
                            0,
                            text=LABELS["rhetoric_progress"][lang].format(i=0, n=len(turns_rh)),
                        )
                        for i, turn in enumerate(turns_rh):
                            try:
                                rh_results.append(analyze_turn_rhetoric(turn, anthropic_key, model=_rhet_model))
                            except Exception as exc:
                                rh_results.append({
                                    "fallacies": [], "rhetorical_devices": [],
                                    "turn_index": turn["turn_index"],
                                    "speaker": turn["speaker"],
                                    "start_ms": turn["start_ms"],
                                })
                            pct = int((i + 1) / max(len(turns_rh), 1) * 100)
                            prog_rh.progress(
                                pct,
                                text=LABELS["rhetoric_progress"][lang].format(i=i + 1, n=len(turns_rh)),
                            )
                        st.session_state["rhetoric"] = rh_results

                    # Generate Speaker Report button
                    has_any_data = any([
                        st.session_state.get("verdicts"),
                        st.session_state.get("responses"),
                        st.session_state.get("rhetoric"),
                    ])
                    col_sr, col_sr_note = st.columns([1, 3])
                    with col_sr:
                        sr_clicked = st.button(L("run_report"), disabled=not (anthropic_key and has_any_data))
                    with col_sr_note:
                        if not has_any_data:
                            st.caption(L("report_need_data"))
                        else:
                            st.caption(L("report_cost"))

                    if sr_clicked and anthropic_key and has_any_data:
                        verdicts_ss  = st.session_state.get("verdicts", {})
                        responses_ss = st.session_state.get("responses") or []
                        rhetoric_ss  = st.session_state.get("rhetoric") or []
                        claims_mv    = [
                            {**c, "verdict": verdicts_ss.get(c["id"], {}).get("verdict", "")}
                            for c in analysis.get("claims", [])
                        ]
                        scores = compute_speaker_scores(claims_mv, responses_ss, rhetoric_ss)
                        report: dict = {}
                        sr_prog = st.progress(0)
                        spk_ids = sorted(scores.keys())
                        for i, sid in enumerate(spk_ids):
                            name = speaker_names_an.get(sid, sid)
                            sr_prog.progress(
                                int(i / max(len(spk_ids), 1) * 100),
                                text=LABELS["report_generating"][lang].format(name=name),
                            )
                            summary = generate_speaker_summary(sid, name, scores[sid], anthropic_key)
                            report[sid] = {"score": scores[sid], "summary": summary}
                        sr_prog.progress(100, text=L("prog_done"))
                        st.session_state["speaker_report"] = report

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

                        # Table — HTML with badge column when verdicts present
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
                                v_key = verdicts.get(c["id"], {}).get("verdict", "")
                                short = (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"]
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
                                    L("col_thread"):    c.get("thread_id", ""),
                                    L("col_speaker"):   speaker_names_an.get(c["speaker"], c["speaker"]),
                                    L("col_time"):      ms_to_ts(c.get("start_ms", 0)),
                                    L("col_type"):      c.get("claim_type", ""),
                                    L("col_checkable"): "yes" if c.get("checkable") else "no",
                                    L("col_claim"):     (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"],
                                }
                                for c in sorted_claims
                            ]
                            st.dataframe(rows, use_container_width=True)

                        # CSV export
                        if sorted_claims:
                            csv_rows = [
                                {
                                    L("col_thread"):    c.get("thread_id", ""),
                                    L("col_speaker"):   speaker_names_an.get(c["speaker"], c["speaker"]),
                                    L("col_time"):      ms_to_ts(c.get("start_ms", 0)),
                                    L("col_type"):      c.get("claim_type", ""),
                                    L("col_checkable"): "yes" if c.get("checkable") else "no",
                                    L("col_verdict"):   verdicts.get(c["id"], {}).get("verdict", ""),
                                    L("col_claim"):     c["text"],
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

                        # ── Analysis export buttons ────────────────────────────
                        dl_col1, dl_col2 = st.columns(2)
                        with dl_col1:
                            _an_title = t.get("_title", "Debate") if t else "Debate"
                            try:
                                _pdf_bytes = build_analysis_pdf(
                                    claims        = analysis.get("claims", []),
                                    threads       = analysis.get("threads", []),
                                    speaker_names = speaker_names_an,
                                    speaker_report= st.session_state.get("speaker_report", {}),
                                    verdicts      = st.session_state.get("verdicts", {}),
                                    title         = _an_title,
                                )
                            except Exception as _pdf_err:
                                _pdf_bytes = b""
                                st.caption(f"PDF unavailable: {_pdf_err}")
                            st.download_button(
                                label     = L("btn_dl_analysis_pdf"),
                                data      = _pdf_bytes,
                                file_name = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                mime      = "application/pdf",
                                disabled  = not _pdf_bytes,
                            )
                        with dl_col2:
                            _export_json = json.dumps(
                                {
                                    "analysis":       analysis,
                                    "verdicts":       st.session_state.get("verdicts", {}),
                                    "speaker_report": st.session_state.get("speaker_report", {}),
                                },
                                indent=2,
                                ensure_ascii=False,
                            )
                            st.download_button(
                                label     = L("btn_dl_analysis_json"),
                                data      = _export_json.encode("utf-8"),
                                file_name = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime      = "application/json",
                            )

                        # ── Verdict expanders ──────────────────────────────────
                        if verdicts:
                            st.divider()
                            aid_fb = st.session_state.get("_analysis_id", "")
                            for c in sorted_claims:
                                vdict = verdicts.get(c["id"])
                                if not vdict:
                                    continue
                                cid        = c["id"]
                                spk_lbl    = speaker_names_an.get(c["speaker"], c["speaker"])
                                short_text = (c["text"][:40] + "…") if len(c["text"]) > 40 else c["text"]
                                with st.expander(f"[{ms_to_ts(c.get('start_ms', 0))}] {spk_lbl} — {short_text}"):
                                    st.markdown(f"**{c['text']}**")

                                    # Translation toggle
                                    ui_lang_code = "en" if lang == "English" else "es"
                                    if transcript_lang != ui_lang_code:
                                        t_cache_key = f"translation_{cid}_{ui_lang_code}"
                                        if t_cache_key not in st.session_state:
                                            if st.button(L("translate_btn"), key=f"tr_btn_{cid}"):
                                                st.session_state[t_cache_key] = translate_claim(
                                                    c["text"], transcript_lang, ui_lang_code, anthropic_key,
                                                )
                                                st.rerun()
                                        if t_cache_key in st.session_state:
                                            st.info(f"**{L('translation_label')}:** {st.session_state[t_cache_key]}")

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

                # ── Argument Map sub-tab ───────────────────────────────────────
                with subtab_map:
                    responses = st.session_state.get("responses")
                    if not responses:
                        st.info(L("run_detect_first"))
                    else:
                        graph_html = build_graph_html(
                            analysis.get("claims", []),
                            responses,
                            speaker_names_an,
                        )
                        if graph_html:
                            components.html(graph_html, height=620, scrolling=False)
                        else:
                            st.info(L("analysis_no_claims"))

                        # Legend
                        st.markdown(f"#### {L('legend_heading')}")
                        _SPEAKER_COLORS_VIS = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
                        spk_sorted = sorted({c["speaker"] for c in analysis.get("claims", [])})
                        spk_legend = " &nbsp; ".join(
                            f'<span style="background:{_SPEAKER_COLORS_VIS[i % 5]};'
                            f'border-radius:50%;display:inline-block;width:12px;height:12px"></span> '
                            f'{speaker_names_an.get(s, s)}'
                            for i, s in enumerate(spk_sorted)
                        )
                        shape_legend = (
                            "⬤ factual / statistical / comparative &nbsp;&nbsp;"
                            "◆ causal / predictive &nbsp;&nbsp;"
                            "■ definitional / interpretive &nbsp;&nbsp;"
                            "▲ moral / anecdotal"
                        )
                        edge_legend = (
                            '<span style="color:#d62728">━</span> refutes &nbsp;&nbsp;'
                            '<span style="color:#2ca02c">━</span> supports &nbsp;&nbsp;'
                            '<span style="color:#ff7f0e">━</span> weakens / concedes &nbsp;&nbsp;'
                            '<span style="color:#9467bd">━</span> reframes &nbsp;&nbsp;'
                            '<span style="color:#aaaaaa">━</span> evades / ignores'
                        )
                        st.markdown(
                            f"**{L('legend_node_color')}:** {spk_legend}<br>"
                            f"**{L('legend_node_shape')}:** {shape_legend}<br>"
                            f"**{L('legend_edge_color')}:** {edge_legend}",
                            unsafe_allow_html=True,
                        )

                # ── Rhetorical Profile sub-tab ─────────────────────────────────
                with subtab_rhetoric:
                    rhetoric = st.session_state.get("rhetoric")
                    if not rhetoric:
                        st.info(L("rhetoric_run_first"))
                    else:
                        # Group findings by speaker
                        spk_rhetoric: dict[str, list[dict]] = defaultdict(list)
                        for item in rhetoric:
                            spk_rhetoric[item["speaker"]].append(item)

                        for sid in sorted(spk_rhetoric.keys()):
                            turns_for_spk = spk_rhetoric[sid]
                            all_fallacies = [
                                {**f, "start_ms": t["start_ms"]}
                                for t in turns_for_spk
                                for f in t.get("fallacies", [])
                            ]
                            all_devices = [
                                {**d, "start_ms": t["start_ms"]}
                                for t in turns_for_spk
                                for d in t.get("rhetorical_devices", [])
                                if not d.get("is_fallacy", False)
                            ]
                            spk_name = speaker_names_an.get(sid, sid)
                            title = (
                                f"{spk_name} — "
                                f"{len(all_fallacies)} {L('rhetoric_fallacies').lower()} · "
                                f"{len(all_devices)} {L('rhetoric_devices').lower()}"
                            )
                            with st.expander(title, expanded=len(all_fallacies) > 0):
                                if all_fallacies:
                                    st.markdown(f"**{L('rhetoric_fallacies')}**")
                                    for f in all_fallacies:
                                        ts = ms_to_ts(f["start_ms"])
                                        st.markdown(
                                            f"[{ts}] **{f.get('label', f.get('type', ''))}**"
                                            f" — \"{f.get('quote', '')}\""
                                        )
                                        st.markdown(f"> {f.get('explanation', '')}")
                                if all_devices:
                                    if all_fallacies:
                                        st.markdown("---")
                                    st.markdown(f"**{L('rhetoric_devices')}**")
                                    for d in all_devices:
                                        ts = ms_to_ts(d["start_ms"])
                                        st.markdown(
                                            f"[{ts}] **{d.get('label', d.get('type', ''))}**"
                                            f" — \"{d.get('quote', '')}\""
                                        )
                                        st.markdown(f"> {d.get('explanation', '')}")
                                if not all_fallacies and not all_devices:
                                    st.caption("—")

                        st.caption(L("rhetoric_footer"))

                # ── Speaker Report sub-tab ─────────────────────────────────────
                with subtab_report:
                    speaker_report = st.session_state.get("speaker_report")
                    if not speaker_report:
                        st.info(L("report_run_first"))
                    else:
                        _VERDICT_LABEL_MAP = {
                            "true":           L("verdict_true"),
                            "partially_true": L("verdict_partly_true"),
                            "contested":      L("verdict_contested"),
                            "misleading":     L("verdict_misleading"),
                            "false":          L("verdict_false"),
                            "unverifiable":   L("verdict_unverifiable"),
                            "subjective":     L("verdict_subjective"),
                        }
                        for idx, sid in enumerate(sorted(speaker_report.keys())):
                            entry  = speaker_report[sid]
                            score  = entry["score"]
                            summary = entry["summary"]
                            name   = speaker_names_an.get(sid, sid)

                            st.subheader(name)

                            # Metric grid
                            rs = score.get("reliability_score")
                            dr = score.get("direct_response_rate")
                            checkable = score.get("checkable_claims", 0)
                            v = score.get("verdicts", {})
                            supported = v.get("true", 0) + v.get("partially_true", 0)

                            rs_str = f"{rs:.0%}" if rs is not None else L("metric_na")
                            dr_str = f"{dr:.0%}" if dr is not None else L("metric_na")
                            sup_str = LABELS["metric_supported"][lang].format(
                                n=supported, total=checkable
                            )

                            mc1, mc2, mc3, mc4 = st.columns(4)
                            mc1.metric(L("metric_reliability"),  rs_str)
                            mc2.metric(L("metric_factchecked"),  sup_str)
                            mc3.metric(L("metric_direct_resp"),  dr_str)
                            mc4.metric(L("metric_fallacies"),    str(score.get("fallacy_count", 0)))

                            # Verdict bar chart (only non-zero verdicts)
                            verdict_counts = {
                                _VERDICT_LABEL_MAP[k]: cnt
                                for k, cnt in v.items()
                                if cnt > 0
                            }
                            if verdict_counts:
                                st.caption(L("chart_verdicts"))
                                chart_df = pd.DataFrame.from_dict(
                                    verdict_counts, orient="index", columns=["count"]
                                )
                                st.bar_chart(chart_df, use_container_width=True)

                            # Narrative summary
                            st.info(summary)

                            if idx < len(speaker_report) - 1:
                                st.divider()


if __name__ == "__main__":
    main()
