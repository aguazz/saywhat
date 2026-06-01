import csv
import io
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

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
from truth_checker.scorer      import compute_speaker_scores, compute_debate_scores
from truth_checker.visualizer  import build_graph_html
from truth_checker.dung        import compute_grounded_extension
from truth_checker.deduplicator import mark_restatements
from truth_checker              import help_dialogs
from streamlit_javascript import st_javascript
from truth_checker.stage_labeler import label_dialectical_stages

load_dotenv()  # loads .env for local dev; no-op on Streamlit Community Cloud

st.set_page_config(
    page_title="SayWhat",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
    "analysis_empty_heading": {
        "English": "What Analysis does",
        "Español": "Qué hace el análisis",
    },
    "analysis_empty_body": {
        "English": (
            "Analysis reads the transcript and extracts each speaker's claims. It then:\n\n"
            "- Classifies each claim by type (factual, statistical, causal, moral…)\n"
            "- Groups claims into topic threads\n"
            "- Maps how speakers respond to each other's claims (who challenges what)\n"
            "- Fact-checks verifiable claims against external sources\n"
            "- Detects logical fallacies and rhetorical devices per speaker\n"
            "- Scores each speaker on factual accuracy and engagement"
        ),
        "Español": (
            "El análisis lee la transcripción y extrae las afirmaciones de cada hablante. Luego:\n\n"
            "- Clasifica cada afirmación por tipo (factual, estadística, causal, moral…)\n"
            "- Agrupa las afirmaciones en hilos temáticos\n"
            "- Traza cómo responden los hablantes a las afirmaciones de los demás\n"
            "- Verifica las afirmaciones comprobables contra fuentes externas\n"
            "- Detecta falacias lógicas y recursos retóricos por hablante\n"
            "- Puntúa a cada hablante en precisión factual y nivel de participación"
        ),
    },
    "analysis_empty_intro": {
        "English": "Analysis reads the transcript and extracts each speaker's claims. It then:",
        "Español": "El análisis lee la transcripción y extrae las afirmaciones de cada hablante. Luego:",
    },
    "analysis_bullet_claims": {
        "English": "Classifies each claim by type (factual, statistical, causal, moral…)",
        "Español": "Clasifica cada afirmación por tipo (factual, estadística, causal, moral…)",
    },
    "analysis_bullet_threads": {
        "English": "Groups claims into topic threads",
        "Español": "Agrupa las afirmaciones en hilos temáticos",
    },
    "analysis_bullet_responses": {
        "English": "Maps how speakers respond to each other's claims (who challenges what)",
        "Español": "Traza cómo responden los hablantes a las afirmaciones de los demás",
    },
    "analysis_bullet_factcheck": {
        "English": "Fact-checks verifiable claims against external sources",
        "Español": "Verifica las afirmaciones comprobables contra fuentes externas",
    },
    "analysis_bullet_rhetoric": {
        "English": "Detects logical fallacies and rhetorical devices per speaker",
        "Español": "Detecta falacias lógicas y recursos retóricos por hablante",
    },
    "analysis_bullet_scoring": {
        "English": "Scores each speaker on factual accuracy and engagement",
        "Español": "Puntúa a cada hablante en precisión factual y nivel de participación",
    },
    "help_link_claims": {
        "English": "what are claims?",
        "Español": "¿qué son las afirmaciones?",
    },
    "help_link_threads": {
        "English": "what are threads?",
        "Español": "¿qué son los hilos?",
    },
    "help_link_responses": {
        "English": "how claims respond to each other",
        "Español": "cómo responden las afirmaciones entre sí",
    },
    "help_link_factcheck": {
        "English": "how fact-checking works",
        "Español": "cómo funciona la verificación",
    },
    "help_link_rhetoric": {
        "English": "fallacies and rhetorical devices",
        "Español": "falacias y recursos retóricos",
    },
    "help_link_scoring": {
        "English": "how speakers are scored",
        "Español": "cómo se puntúa a los hablantes",
    },
    "help_sidebar_heading": {
        "English": "Help",
        "Español": "Ayuda",
    },
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
    "filter_thread":        {"English": "Filter by thread",          "Español": "Filtrar por hilo"},
    "filter_text":          {"English": "Search claims…",             "Español": "Buscar afirmaciones…"},
    "filter_more":          {"English": "More filters",               "Español": "Más filtros"},
    "filter_verdict":       {"English": "Verdict",                    "Español": "Veredicto"},
    "filter_survivability": {"English": "Argument status",            "Español": "Estado del argumento"},
    "filter_has_fallacy":   {"English": "Has fallacy",                "Español": "Contiene falacia"},
    "filter_has_device":    {"English": "Has rhetorical device",      "Español": "Contiene recurso retórico"},
    "filter_connections":   {"English": "Connections",                "Español": "Conexiones"},
    "filter_conn_any":      {"English": "Any",                        "Español": "Cualquiera"},
    "filter_conn_1":        {"English": "Has at least 1",             "Español": "Al menos 1"},
    "filter_conn_3":        {"English": "Highly connected (≥ 3)",     "Español": "Muy conectada (≥ 3)"},
    "filter_conn_0":        {"English": "Isolated (0 connections)",   "Español": "Aislada (0 conexiones)"},
    "filter_checkable":     {"English": "Checkable",                  "Español": "Verificable"},
    "filter_qualifier":     {"English": "Certainty",                  "Español": "Certeza"},
    "filter_stance":        {"English": "Stance on motion",           "Español": "Posición respecto a la moción"},
    "filter_clear_all":     {"English": "Clear all",                  "Español": "Borrar todo"},
    "filter_count":         {"English": "{n} of {m} claims",          "Español": "{n} de {m} afirmaciones"},
    "filter_any":           {"English": "Any",                        "Español": "Cualquiera"},
    "filter_yes":           {"English": "Yes",                        "Español": "Sí"},
    "filter_no":            {"English": "No",                         "Español": "No"},
    "graph_filter_caption": {
        "English": "Showing {n} of {m} claims · filter active",
        "Español": "Mostrando {n} de {m} afirmaciones · filtro activo",
    },
    "col_thread":        {"English": "Thread",                   "Español": "Hilo"},
    "col_speaker":       {"English": "Speaker",                  "Español": "Hablante"},
    "col_time":          {"English": "Time",                     "Español": "Tiempo"},
    "col_type":          {"English": "Type",                     "Español": "Tipo"},
    "col_checkable":     {"English": "Checkable",                "Español": "Verificable"},
    "col_claim":         {"English": "Claim",                    "Español": "Afirmación"},
    "col_type_help": {
        "English": "What kind of claim: factual, statistical, causal, predictive, comparative, definitional, interpretive, moral, or anecdotal.",
        "Español": "Tipo de afirmación: factual, estadística, causal, predictiva, comparativa, definitoria, interpretativa, moral o anecdótica.",
    },
    "col_checkable_help": {
        "English": "Can this claim be verified against external evidence? Moral claims, pure opinions, and predictions are not checkable.",
        "Español": "¿Se puede verificar esta afirmación con evidencia externa? Las afirmaciones morales, las opiniones puras y las predicciones no son verificables.",
    },
    "col_verdict_help": {
        "English": "What the available evidence says about this claim. Only shown for checkable claims after running Fact-Check.",
        "Español": "Lo que la evidencia disponible dice sobre esta afirmación. Solo se muestra para afirmaciones verificables tras ejecutar la verificación.",
    },
    "col_headers_note": {
        "English": "Columns: Thread = topic group · Type = kind of claim · Checkable = verifiable against evidence",
        "Español": "Columnas: Hilo = grupo temático · Tipo = clase de afirmación · Verificable = comprobable con evidencia",
    },
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
    # Labels use epistemic-humility language (Rittel & Webber 1973):
    # stored verdict keys are unchanged; only the display strings are renamed.
    "col_verdict":       {"English": "Verdict",          "Español": "Veredicto"},
    "verdict_true":      {"English": "Supported",        "Español": "Respaldado"},
    "verdict_partly_true":{"English": "Partially supported", "Español": "Parcialmente respaldado"},
    "verdict_contested": {"English": "Contested",        "Español": "Disputado"},
    "verdict_misleading":{"English": "Contested",        "Español": "Disputado"},
    "verdict_false":     {"English": "Unsupported",      "Español": "No respaldado"},
    "verdict_unverifiable":{"English": "Beyond scope",  "Español": "Fuera de alcance"},
    "verdict_subjective":{"English": "Beyond scope",    "Español": "Fuera de alcance"},
    "verdict_none":      {"English": "—",               "Español": "—"},
    "verdict_legend_label": {
        "English": "Verdicts:",
        "Español": "Veredictos:",
    },
    # ── Fact-check disclaimer ────────────────────────────────────────────────
    "factcheck_disclaimer": {
        "English": (
            "**What this fact-check covers — and what it does not.** "
            "This tool verifies factual sub-claims: statistics, historical events, and "
            "cited empirical data. It does not evaluate normative claims, value judgments, "
            "or contested interpretations of social and economic data — these involve ongoing "
            "scholarly debate and have no single correct answer. "
            "Claims of those types are labeled **Beyond scope**."
        ),
        "Español": (
            "**Qué cubre esta verificación — y qué no.** "
            "Esta herramienta verifica afirmaciones factuales: estadísticas, hechos históricos "
            "y datos empíricos citados. No evalúa afirmaciones normativas, juicios de valor ni "
            "interpretaciones disputadas de datos sociales y económicos — estos implican un debate "
            "académico continuo y no tienen una única respuesta correcta. "
            "Las afirmaciones de ese tipo se etiquetan como **Fuera de alcance**."
        ),
    },
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
    "subtab_timeline":   {"English": "Thread Timeline",      "Español": "Línea de tiempo"},
    "subtab_factcheck":  {"English": "Fact-Check",           "Español": "Verificación"},
    # ── Thread Timeline tab ──────────────────────────────────────────────────
    "timeline_no_analysis": {
        "English": "Run Analysis first to see the thread timeline.",
        "Español": "Ejecuta el análisis primero para ver la línea de tiempo.",
    },
    "timeline_select":   {"English": "Highlight a claim",    "Español": "Resaltar una afirmación"},
    "timeline_all":      {"English": "— show all threads —", "Español": "— mostrar todos los hilos —"},
    "timeline_selected": {"English": "Selected claim",        "Español": "Afirmación seleccionada"},
    "timeline_thread":   {"English": "Thread",                "Español": "Hilo"},
    "timeline_legend":   {"English": "Speaker colours:",      "Español": "Colores por hablante:"},
    "timeline_hint": {
        "English": "Hover over any block to preview the claim. Click any block to open its full details below.",
        "Español": "Pasa el cursor sobre un bloque para previsualizar la afirmación. Haz clic para ver todos sus detalles abajo.",
    },
    "timeline_restat_legend": {
        "English": "⟋ diagonal stripes = claim repeated from an earlier turn",
        "Español": "⟋ rayas diagonales = afirmación repetida de un turno anterior",
    },
    "timeline_clear_sel": {"English": "✕ Clear selection", "Español": "✕ Quitar selección"},
    # ── Thread scorecards ───────────────────────────────────────────────────
    "thread_scorecard_heading": {"English": "Thread Scorecards",  "Español": "Resumen por hilos"},
    "thread_depth":      {"English": "Claims",          "Español": "Afirmaciones"},
    "thread_speakers":   {"English": "Speakers",        "Español": "Hablantes"},
    "thread_balance":    {"English": "Speaker balance", "Español": "Balance de hablantes"},
    "thread_survival":   {"English": "Survival rate",  "Español": "Tasa de supervivencia"},
    "thread_verdict_rate":{"English": "Verdict rate",  "Español": "Tasa de veredictos"},
    "thread_responses":  {"English": "Response edges",  "Español": "Conexiones de respuesta"},
    # ── Claim card (timeline detail panel) ──────────────────────────────────
    "card_stage":        {"English": "Stage",          "Español": "Etapa"},
    "card_connections":  {"English": "Connections",    "Español": "Conexiones"},
    "card_responds_to":  {"English": "Responds to",    "Español": "Responde a"},
    "card_challenged_by":{"English": "Challenged by",  "Español": "Cuestionado por"},
    "card_supported_by": {"English": "Supported by",   "Español": "Apoyado por"},
    "card_rhetoric":      {"English": "Rhetoric",             "Español": "Retórica"},
    "card_show_minimap":  {"English": "Show neighbourhood map", "Español": "Ver mapa de vecindad"},
    "card_hide_minimap":  {"English": "Hide neighbourhood map", "Español": "Ocultar mapa de vecindad"},
    "card_no_connections":{"English": "This claim has no direct argument connections.",
                           "Español": "Esta afirmación no tiene conexiones de argumento directas."},
    "subtab_map":        {"English": "Argument Map",         "Español": "Mapa de argumentos"},
    # ── Fact-Check tab ───────────────────────────────────────────────────────
    "fc_run_first": {
        "English": "Run Fact-Check (button in the Claims tab) to see results here.",
        "Español": "Ejecuta la verificación (botón en Afirmaciones) para ver los resultados aquí.",
    },
    "fc_checked":     {"English": "Claims checked",       "Español": "Afirmaciones verificadas"},
    "fc_supported":   {"English": "Supported",            "Español": "Respaldadas"},
    "fc_challenged":  {"English": "Challenged / False",   "Español": "Cuestionadas / Falsas"},
    "fc_beyond":      {"English": "Beyond scope",         "Español": "Fuera de alcance"},
    "fc_kb_col":      {"English": "Basis",                "Español": "Base"},
    "fc_sources_col": {"English": "Sources",              "Español": "Fuentes"},
    "fc_thread_col":  {"English": "Topic",                "Español": "Tema"},
    "fc_conf_help": {
        "English": (
            "How clearly the available evidence supported the verdict. "
            "An AI-estimated signal: high = clear evidence, low = ambiguous or limited sources. "
            "Not a statistically calibrated probability."
        ),
        "Español": (
            "Con qué claridad la evidencia disponible respaldó el veredicto. "
            "Una señal estimada por IA: alta = evidencia clara, baja = evidencia ambigua o limitada. "
            "No es una probabilidad estadísticamente calibrada."
        ),
    },
    "fc_disclaimer":  {
        "English": (
            "🧠 = verdict based on Claude's training knowledge  ·  "
            "📚 = verdict grounded in retrieved sources (Wikipedia / DuckDuckGo / Semantic Scholar)"
        ),
        "Español": (
            "🧠 = veredicto basado en el conocimiento de Claude  ·  "
            "📚 = veredicto basado en fuentes recuperadas (Wikipedia / DuckDuckGo / Semantic Scholar)"
        ),
    },
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
    "legend_undercuts":    {"English": "challenges the reasoning",   "Español": "cuestiona el razonamiento"},
    "legend_refutes":  {"English": "directly denies the conclusion",         "Español": "niega directamente la conclusión"},
    "legend_supports": {"English": "agrees with or extends the claim",       "Español": "apoya o amplía la afirmación"},
    "legend_weakens":  {"English": "accepts but reduces scope",              "Español": "acepta pero reduce el alcance"},
    "legend_concedes": {"English": "acknowledges the other side has a point", "Español": "reconoce que el otro lado tiene razón"},
    "legend_reframes": {"English": "same facts, different meaning",          "Español": "mismos hechos, distinto significado"},
    "legend_evades":   {"English": "changes subject without responding",     "Español": "cambia de tema sin responder"},
    "legend_ignores":  {"English": "makes an unrelated new point",           "Español": "introduce un punto no relacionado"},
    "map_how_to_expander": {
        "English": "How to read this map",
        "Español": "Cómo leer este mapa",
    },
    "map_how_to_nodes": {
        "English": "**Each dot is a claim.** Colors show who said it — same colors as in the transcript.",
        "Español": "**Cada punto es una afirmación.** Los colores muestran quién la dijo — los mismos colores que en la transcripción.",
    },
    "map_how_to_arrows": {
        "English": (
            "**Each arrow is a response.** "
            "It points *from* the responding claim *to* the claim being responded to."
        ),
        "Español": (
            "**Cada flecha es una respuesta.** "
            "Apunta *desde* la afirmación que responde *hacia* la afirmación a la que se responde."
        ),
    },
    "map_how_to_labels": {
        "English": (
            "**The label on each arrow** tells you the type of response:\n\n"
            "- *refutes* — directly denies the conclusion\n"
            "- *undercuts* — challenges the evidence or reasoning, not the conclusion itself\n"
            "- *reframes* — accepts the facts but changes their interpretation\n"
            "- *weakens* — accepts the claim but limits its scope\n"
            "- *supports* — agrees with or adds evidence for the claim\n"
            "- *evades / ignores* — changes subject or makes an unrelated point"
        ),
        "Español": (
            "**La etiqueta en cada flecha** indica el tipo de respuesta:\n\n"
            "- *refutes* — niega directamente la conclusión\n"
            "- *undercuts* — cuestiona la evidencia o el razonamiento, no la conclusión en sí\n"
            "- *reframes* — acepta los hechos pero cambia su interpretación\n"
            "- *weakens* — acepta la afirmación pero limita su alcance\n"
            "- *supports* — apoya o añade evidencia a favor\n"
            "- *evades / ignores* — cambia de tema o introduce un punto no relacionado"
        ),
    },
    "map_how_to_patterns": {
        "English": (
            "**A claim with many incoming arrows** is a contested point — both sides invested effort there. "
            "**A claim with no incoming arrows** went unchallenged in this debate."
        ),
        "Español": (
            "**Una afirmación con muchas flechas entrantes** es un punto disputado — ambos lados pusieron esfuerzo ahí. "
            "**Una afirmación sin flechas entrantes** no fue cuestionada en este debate."
        ),
    },
    # ── Argument survivability (Dung grounded extension) ────────────────────
    "surv_grounded":   {"English": "Survived all counterarguments", "Español": "Resistió todos los contraargumentos"},
    "surv_contested":  {"English": "Challenged",                    "Español": "Cuestionado"},
    "surv_unattacked": {"English": "Unchallenged",                  "Español": "Sin oposición"},
    "surv_heading":    {"English": "Argument survivability",        "Español": "Resistencia argumentativa"},
    "surv_map_summary":{
        "English": "After all counterarguments: **{g}** claims survived all attacks, **{c}** are challenged, and **{u}** had none.",
        "Español": "Tras los contraargumentos: **{g}** afirmaciones resistieron todos los ataques, **{c}** están cuestionadas y **{u}** no recibieron ninguno.",
    },
    # ── Restatement deduplication ────────────────────────────────────────────
    "deduplicating":      {"English": "Detecting repeated claims…",
                           "Español": "Detectando afirmaciones repetidas…"},
    "restatement_label":  {"English": "Repeated claim — same as:",
                           "Español": "Afirmación repetida — igual que:"},
    "restatement_badge":  {"English": "repeated",
                           "Español": "repetida"},
    "restatement_report": {"English": "{n} repeated claim(s) detected and skipped in fact-check",
                           "Español": "{n} afirmación(es) repetida(s) detectada(s) y omitida(s) en la verificación"},
    # ── Dialectical stage labeling (van Eemeren & Grootendorst 2004) ────────
    "stage_labeling":       {"English": "Detecting dialectical stages…",
                             "Español": "Detectando etapas dialécticas…"},
    "stage_timeline":       {"English": "Dialectical Stage Timeline",
                             "Español": "Línea de tiempo dialéctica"},
    "stage_confrontation":  {"English": "Confrontation",  "Español": "Confrontación"},
    "stage_opening":        {"English": "Opening",         "Español": "Apertura"},
    "stage_argumentation":  {"English": "Argumentation",  "Español": "Argumentación"},
    "stage_concluding":     {"English": "Concluding",      "Español": "Conclusión"},
    "stage_heading_report": {"English": "Dialectical stage participation",
                             "Español": "Participación por etapa dialéctica"},
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
    "rhetoric_profile_chart": {"English": "Rhetorical profile by speaker", "Español": "Perfil retórico por hablante"},
    "rhetoric_footer":    {
        "English": "Rhetorical devices are not always flaws. Labels show technique, not quality.",
        "Español": "Los recursos retóricos no son siempre defectos. Las etiquetas indican técnica, no calidad.",
    },
    "rh_breakdown_expander": {
        "English": "Breakdown by type",
        "Español": "Desglose por tipo",
    },
    "rh_fallacy_types_heading": {
        "English": "Fallacy types",
        "Español": "Tipos de falacias",
    },
    "rh_device_types_heading": {
        "English": "Rhetorical device types",
        "Español": "Tipos de recursos retóricos",
    },
    "rh_other": {
        "English": "Other",
        "Español": "Otros",
    },
    "rhetoric_intro": {
        "English": (
            "**Fallacies** are reasoning errors — arguments that look persuasive but "
            "don't hold up logically. Examples: cherry-picking evidence, attacking the "
            "person instead of their argument, or presenting a false either/or choice.\n\n"
            "**Rhetorical devices** are persuasion techniques. They're not errors — "
            "they're part of how people communicate effectively. An appeal to a legitimate "
            "authority, a vivid example, or a well-chosen word can all be fair and effective.\n\n"
            "The app only flags a fallacy when there is a specific quote to point to. "
            "It won't flag one based on vague impressions."
        ),
        "Español": (
            "**Las falacias** son errores de razonamiento — argumentos que parecen persuasivos "
            "pero no se sostienen lógicamente. Ejemplos: seleccionar solo la evidencia "
            "conveniente, atacar a la persona en lugar de su argumento, "
            "o plantear una falsa disyuntiva.\n\n"
            "**Los recursos retóricos** son técnicas de persuasión. No son errores — "
            "forman parte de cómo comunicamos con eficacia. Apelar a una autoridad legítima, "
            "usar un ejemplo vívido o elegir bien las palabras puede ser completamente justo "
            "y eficaz.\n\n"
            "La herramienta solo marca una falacia cuando hay una cita específica que la "
            "respalde. No las detecta por impresiones vagas."
        ),
    },
    "rhetoric_rule_label": {
        "English": "Rule {n} — {name}",
        "Español": "Regla {n} — {name}",
    },
    "rhetoric_rule_names": {
        "English": {1: "Freedom", 2: "Burden of proof", 3: "Standpoint",
                    4: "Relevance", 7: "Argument scheme", 10: "Usage"},
        "Español": {1: "Libertad", 2: "Carga de la prueba", 3: "Posición",
                    4: "Relevancia", 7: "Esquema argumentativo", 10: "Uso del lenguaje"},
    },
    # ── Speaker Report sub-tab ───────────────────────────────────────────────
    "subtab_report":      {"English": "Speaker Report",             "Español": "Informe de hablantes"},
    "run_report":         {"English": "Speaker Report",             "Español": "Informe de hablantes"},
    "dl_speaker_report":  {"English": "⬇ Speaker report (.json)",  "Español": "⬇ Informe de hablantes (.json)"},
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
    "metric_reliability":      {"English": "Reliability",               "Español": "Fiabilidad"},
    "metric_factchecked":      {"English": "Supported claims",          "Español": "Afirmaciones respaldadas"},
    "metric_direct_resp":      {"English": "Direct response rate",      "Español": "Tasa de respuesta directa"},
    "metric_fallacies":        {"English": "Logical fallacies",         "Español": "Falacias lógicas"},
    "metric_thread_engagement":{"English": "Thread engagement",         "Español": "Participación en hilos"},
    "metric_rebuttal_rate":    {"English": "Rebuttal rate",             "Español": "Tasa de refutación"},
    "help_thread_engagement": {
        "English": (
            "How many of the debate's argument threads this speaker contributed to, "
            "as a percentage of all threads. "
            "100% = engaged on every topic. Low % = focused on only a few threads."
        ),
        "Español": (
            "En cuántos hilos de argumento del debate participó este hablante, "
            "como porcentaje del total de hilos. "
            "100% = participó en todos los temas. % bajo = se centró en pocos hilos."
        ),
    },
    "help_rebuttal_rate": {
        "English": (
            "Percentage of the opponent's claims that this speaker directly responded to at least once. "
            "High rate = actively engaged with what the other side said. "
            "Low rate = largely ignored the opponent's arguments."
        ),
        "Español": (
            "Porcentaje de las afirmaciones del oponente a las que este hablante respondió directamente al menos una vez. "
            "Tasa alta = respondió activamente a lo que dijo el otro lado. "
            "Tasa baja = ignoró en gran medida los argumentos del oponente."
        ),
    },
    "metric_supported":    {"English": "{n} of {total}",            "Español": "{n} de {total}"},
    "metric_na":           {"English": "N/A",                       "Español": "N/D"},
    "chart_verdicts":      {"English": "Verdict distribution",      "Español": "Distribución de veredictos"},
    "help_reliability": {
        "English": (
            "Of all checkable factual claims this speaker made, "
            "what fraction were rated Supported or Partially Supported. "
            "Measures factual accuracy — not whether the overall argument was sound."
        ),
        "Español": (
            "De todas las afirmaciones verificables que hizo este hablante, "
            "qué fracción fue calificada como respaldada o parcialmente respaldada. "
            "Mide la precisión factual, no si el argumento general fue sólido."
        ),
    },
    "help_factchecked": {
        "English": (
            "Number of checkable claims rated Supported or Partially Supported "
            "out of all checkable claims made by this speaker."
        ),
        "Español": (
            "Número de afirmaciones verificables calificadas como respaldadas o "
            "parcialmente respaldadas sobre el total de afirmaciones verificables."
        ),
    },
    "help_direct_resp": {
        "English": (
            "Of all the times this speaker could have responded to a specific claim "
            "from the other side, how often did they genuinely engage "
            "(refute, support, reframe, weaken, concede) "
            "rather than evade or ignore it. "
            "High rate = engaged debater. Low rate = deflects."
        ),
        "Español": (
            "De todas las veces que este hablante pudo responder a una afirmación "
            "concreta del otro lado, con qué frecuencia respondió de verdad "
            "(refutó, apoyó, reencuadró, debilitó, concedió) "
            "en lugar de evadir o ignorar. "
            "Tasa alta = debatiente comprometido. Tasa baja = evita el tema."
        ),
    },
    "help_fallacies": {
        "English": (
            "Number of logical fallacies detected in this speaker's turns. "
            "A fallacy is only flagged when a specific quote and explanation are available. "
            "The app won't flag one based on vague impressions."
        ),
        "Español": (
            "Número de falacias lógicas detectadas en los turnos de este hablante. "
            "Solo se marca una falacia cuando hay una cita y una explicación concretas. "
            "La herramienta no las detecta por impresiones vagas."
        ),
    },
    "btn_dl_analysis_pdf": {"English": "⬇  Download Analysis PDF",  "Español": "⬇  Descargar PDF de análisis"},
    "btn_dl_analysis_json":{"English": "⬇  Download Analysis JSON", "Español": "⬇  Descargar JSON de análisis"},
    # ── Debate scorecard banner ──────────────────────────────────────────────
    "ds_response_density": {"English": "Responses / claim",       "Español": "Respuestas / afirmación"},
    "ds_evasion_rate":     {"English": "Evasion rate",             "Español": "Tasa de evasión"},
    "ds_completeness":     {"English": "Dialectical completeness", "Español": "Completitud dialéctica"},
    "ds_thread_coverage":  {"English": "Thread coverage",          "Español": "Cobertura de hilos"},
    "ds_concessions":      {"English": "Concessions",              "Español": "Concesiones"},
    "ds_response_density_help": {
        "English": (
            "Average number of direct responses per claim. "
            "Higher means the debate was more argumentatively dense — speakers engaged with each other's claims rather than talking past each other."
        ),
        "Español": (
            "Número medio de respuestas directas por afirmación. "
            "Un valor más alto indica que el debate fue más denso argumentalmente: los hablantes respondieron a las afirmaciones del otro en lugar de hablar en paralelo."
        ),
    },
    "ds_evasion_rate_help": {
        "English": (
            "Proportion of responses that were evasions — changing the subject or ignoring the claim rather than engaging with it. "
            "Low rate = substantive debate. High rate = a lot of deflection."
        ),
        "Español": (
            "Proporción de respuestas que fueron evasiones: cambiar de tema o ignorar la afirmación en lugar de responder. "
            "Tasa baja = debate sustancial. Tasa alta = mucha evasión."
        ),
    },
    "ds_completeness_help": {
        "English": (
            "How many of the four debate stages (confrontation, opening, argumentation, concluding) appeared at least once. "
            "100% means the debate followed a complete critical-discussion arc."
        ),
        "Español": (
            "Cuántas de las cuatro etapas del debate (confrontación, apertura, argumentación, conclusión) aparecieron al menos una vez. "
            "100% significa que el debate siguió un arco completo de discusión crítica."
        ),
    },
    "ds_thread_coverage_help": {
        "English": (
            "Percentage of argument threads where both speakers contributed at least one claim. "
            "Low coverage means one speaker dominated the agenda; high coverage means a genuinely two-sided exchange."
        ),
        "Español": (
            "Porcentaje de hilos de argumento en los que ambos hablantes contribuyeron al menos una afirmación. "
            "Una cobertura baja indica que un hablante dominó la agenda; una cobertura alta indica un intercambio genuinamente bilateral."
        ),
    },
    "ds_concessions_help": {
        "English": (
            "Total number of responses labelled 'concedes' — one speaker acknowledging the other has a valid point. "
            "Concessions signal intellectual honesty and genuine engagement."
        ),
        "Español": (
            "Número total de respuestas etiquetadas como 'concede': un hablante reconoce que el otro tiene razón en algo. "
            "Las concesiones son señal de honestidad intelectual y compromiso genuino."
        ),
    },
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
    # ── Per-step download / import ──────────────────────────────────────────
    "dl_verdicts":         {"English": "⬇ Fact-check results (.json)",
                            "Español": "⬇ Resultados de verificación (.json)"},
    "dl_responses":        {"English": "⬇ Response map (.json)",
                            "Español": "⬇ Mapa de respuestas (.json)"},
    "dl_rhetoric":         {"English": "⬇ Rhetoric analysis (.json)",
                            "Español": "⬇ Análisis retórico (.json)"},
    "load_results_expander": {
        "English": "⬆ Load saved results (fact-check / responses / rhetoric / speaker report)",
        "Español": "⬆ Cargar resultados guardados (verificación / respuestas / retórica / informe)",
    },
    "upload_speaker_report_label": {"English": "Speaker report JSON",
                                    "Español": "JSON de informe de hablantes"},
    "load_speaker_report_btn":     {"English": "Load",    "Español": "Cargar"},
    "speaker_report_loaded":       {"English": "Speaker report loaded.",
                                    "Español": "Informe de hablantes cargado."},
    "err_not_speaker_report_json": {"English": "File doesn't contain speaker report data.",
                                    "Español": "El archivo no contiene datos del informe de hablantes."},
    "claims_table_expander":       {"English": "Claims table", "Español": "Tabla de afirmaciones"},
    "upload_verdicts_label":  {"English": "Fact-check results JSON",
                               "Español": "JSON de resultados de verificación"},
    "upload_responses_label": {"English": "Response map JSON",
                               "Español": "JSON del mapa de respuestas"},
    "upload_rhetoric_label":  {"English": "Rhetoric analysis JSON",
                               "Español": "JSON del análisis retórico"},
    "load_verdicts_btn":   {"English": "Load",   "Español": "Cargar"},
    "load_responses_btn":  {"English": "Load",   "Español": "Cargar"},
    "load_rhetoric_btn":   {"English": "Load",   "Español": "Cargar"},
    "verdicts_loaded":     {"English": "Fact-check results loaded.",
                            "Español": "Resultados de verificación cargados."},
    "responses_loaded":    {"English": "Response map loaded.",
                            "Español": "Mapa de respuestas cargado."},
    "rhetoric_loaded":     {"English": "Rhetoric analysis loaded.",
                            "Español": "Análisis retórico cargado."},
    "err_not_verdicts_json":  {"English": "File doesn't contain fact-check results.",
                               "Español": "El archivo no contiene resultados de verificación."},
    "err_not_responses_json": {"English": "File doesn't contain response-map data.",
                               "Español": "El archivo no contiene datos del mapa de respuestas."},
    "err_not_rhetoric_json":  {"English": "File doesn't contain rhetoric analysis data.",
                               "Español": "El archivo no contiene datos de análisis retórico."},
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
    # ── Debate motion ────────────────────────────────────────────────────────
    "motion_label":  {
        "English": "Debate motion or central question (optional)",
        "Español": "Moción del debate o pregunta central (opcional)",
    },
    "motion_ph":     {
        "English": "e.g. Free trade improves workers' wages",
        "Español": "p.ej. El libre comercio mejora los salarios de los trabajadores",
    },
    "motion_help":   {
        "English": "When provided, each claim is tagged as supporting (pro) or opposing (con) this motion.",
        "Español": "Si se indica, cada afirmación se etiqueta como a favor o en contra de esta moción.",
    },
    # ── Qualifier plain-language display labels (per Section 8.1) ───────────
    "qualifier_labels": {
        "English": {
            "definite":    "stated as fact",
            "probable":    "probably",
            "possible":    "possibly",
            "speculative": "uncertain",
        },
        "Español": {
            "definite":    "afirmado como hecho",
            "probable":    "probablemente",
            "possible":    "posiblemente",
            "speculative": "incierto",
        },
    },
    # ── Premises and Toulmin reasoning fields ───────────────────────────────
    "evidence_cited":         {"English": "Evidence cited",            "Español": "Evidencia citada"},
    "reasoning_details":      {"English": "Reasoning details",         "Español": "Detalles del razonamiento"},
    "reasoning_used":         {"English": "∴ Reasoning used",          "Español": "∴ Razonamiento empleado"},
    "acknowledged_exception": {"English": "⚠ Acknowledged exception",  "Español": "⚠ Excepción reconocida"},
    "show_premises":          {"English": "Show supporting evidence", "Español": "Mostrar evidencia de apoyo"},
    "show_reasoning_targets": {"English": "Show reasoning targets",   "Español": "Mostrar objetivos de inferencia"},
    "legend_premise":         {"English": "Premise — supports parent claim", "Español": "Premisa — apoya la afirmación"},
    "legend_inference_pt":    {"English": "Reasoning target — where an argument challenges the logic",
                               "Español": "Objetivo de inferencia — donde un argumento cuestiona la lógica"},
    "legend_dashed":          {"English": "Dashed arrow: evidence supports claim",
                               "Español": "Flecha discontinua: evidencia apoya la afirmación"},
    # ── Stance breakdown in Speaker Report ──────────────────────────────────
    "motion_caption":  {"English": "Motion: *{motion}*",   "Español": "Moción: *{motion}*"},
    "stance_heading":  {"English": "Stance on motion",     "Español": "Posición sobre la moción"},
    "stance_pro":      {"English": "For the motion",       "Español": "A favor"},
    "stance_con":      {"English": "Against the motion",   "Español": "En contra"},
    "stance_neutral":  {"English": "Neutral / off-topic",  "Español": "Neutral / fuera de tema"},
    "stance_no_motion":{"English": "No motion was set — stance tracking is disabled.",
                        "Español": "No se ha indicado ninguna moción — el seguimiento de posición está desactivado."},
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

def _build_thread_timeline(
    claims: list[dict],
    threads: list[dict],
    speaker_names: dict,
    selected_claim_id: str | None = None,
    highlighted_ids: set | None = None,
) -> str:
    """
    Build an HTML thread-timeline showing all threads as parallel horizontal lanes.

    Each lane spans the full debate duration on the x-axis. Claims are coloured
    rectangles positioned by their start_ms. The selected claim's lane is shown at
    full opacity; all other lanes are dimmed to 25%. The selected claim itself gets
    a gold highlight ring.

    Returns an HTML string ready for st.markdown(..., unsafe_allow_html=True).
    """
    _SPK_COLORS = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]
    LANE_H  = 28    # px height of each thread lane
    GAP     = 5     # px vertical gap between lanes
    LABEL_W = 175   # px width of the left label column
    AXIS_H  = 22    # px for the time axis at the bottom
    MIN_W   = 0.8   # minimum claim bar width in %

    threaded = [c for c in claims if c.get("thread_id")]
    if not threaded or not threads:
        return ""

    max_ms = max(c.get("end_ms", c.get("start_ms", 0) + 1000) for c in threaded)
    if max_ms == 0:
        return ""

    speakers  = sorted({c["speaker"] for c in threaded})
    spk_color = {spk: _SPK_COLORS[i % len(_SPK_COLORS)] for i, spk in enumerate(speakers)}

    # Which thread does the selected claim live in?
    focus_tid: str | None = None
    if selected_claim_id:
        for c in threaded:
            if c["id"] == selected_claim_id:
                focus_tid = c.get("thread_id")
                break

    by_thread: dict[str, list] = {}
    for c in threaded:
        by_thread.setdefault(c["thread_id"], []).append(c)

    # Time-axis tick spacing
    if max_ms > 1_800_000:
        tick_ms = 120_000
    elif max_ms > 600_000:
        tick_ms = 60_000
    elif max_ms > 180_000:
        tick_ms = 30_000
    else:
        tick_ms = 10_000

    html = '<div style="width:100%;overflow-x:auto;font-family:sans-serif;font-size:0.8em;padding:4px 0">'

    for thread in threads:
        tid     = thread["thread_id"]
        topic   = thread.get("topic", tid)
        label   = (topic[:26] + "…") if len(topic) > 26 else topic
        t_claims = by_thread.get(tid, [])

        # Dim row if no claims match the highlight set, or if not the focus thread
        if highlighted_ids is not None:
            _row_has_match = any(c["id"] in highlighted_ids for c in t_claims)
            row_opacity = "1" if _row_has_match else "0.12"
        else:
            row_opacity = "1" if (focus_tid is None or focus_tid == tid) else "0.25"

        html += (
            f'<div style="display:flex;align-items:center;margin-bottom:{GAP}px;'
            f'opacity:{row_opacity}">'
        )

        # Label
        html += (
            f'<div title="{topic}" style="min-width:{LABEL_W}px;max-width:{LABEL_W}px;'
            f'padding-right:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
            f'color:#888;font-size:0.76em;line-height:{LANE_H}px">{label}</div>'
        )

        # Lane background
        html += (
            f'<div style="flex:1;position:relative;height:{LANE_H}px;'
            f'background:rgba(128,128,128,0.1);border-radius:4px;overflow:visible">'
        )

        for c in t_claims:
            start_pct = c.get("start_ms", 0) / max_ms * 100
            raw_w     = (c.get("end_ms", 0) - c.get("start_ms", 0)) / max_ms * 100
            width_pct = max(raw_w, MIN_W)
            color     = spk_color.get(c["speaker"], "#aaaaaa")
            is_sel    = c["id"] == selected_claim_id
            is_restat = bool(c.get("restatement_of"))

            spk_name = speaker_names.get(c["speaker"], c["speaker"])
            ts       = f"{int(c.get('start_ms',0)//60000):02d}:{int((c.get('start_ms',0)%60000)//1000):02d}"
            preview  = c["text"][:100] + ("…" if len(c["text"]) > 100 else "")
            tooltip  = f"[{ts}] {spk_name}: {preview}"

            border     = "3px solid #FFD700" if is_sel else "1px solid rgba(255,255,255,0.2)"
            shadow     = ";box-shadow:0 0 0 2px #FFD700,0 0 10px rgba(255,215,0,0.6)" if is_sel else ""
            z_idx      = "20" if is_sel else "1"
            if highlighted_ids is not None and c["id"] not in highlighted_ids:
                bar_opacity = "0.12"
            else:
                bar_opacity = "1" if is_sel else ("0.45" if is_restat else "0.85")
            # Diagonal stripe pattern for restatements
            bg_extra   = (
                "background-image:repeating-linear-gradient("
                "45deg,transparent,transparent 3px,"
                "rgba(0,0,0,0.18) 3px,rgba(0,0,0,0.18) 6px);"
            ) if is_restat else ""

            _tt_safe = tooltip.replace('"', '&quot;').replace("'", "&#39;")
            html += (
                f'<div title="{_tt_safe}" onclick="selectClaim(\'{c["id"]}\')" '
                f'style="position:absolute;cursor:pointer;'
                f'left:{start_pct:.3f}%;width:{width_pct:.3f}%;'
                f'top:2px;height:{LANE_H-4}px;'
                f'background:{color};{bg_extra}'
                f'border-radius:3px;border:{border};z-index:{z_idx};'
                f'opacity:{bar_opacity};box-sizing:border-box{shadow}"></div>'
            )

        html += '</div></div>'  # close lane + row

    # Time axis
    html += f'<div style="display:flex;margin-top:2px">'
    html += f'<div style="min-width:{LABEL_W}px"></div>'
    html += f'<div style="flex:1;position:relative;height:{AXIS_H}px">'

    t = 0
    while t <= max_ms:
        pct = t / max_ms * 100
        ts  = f"{int(t//60000):02d}:{int((t%60000)//1000):02d}"
        html += (
            f'<span style="position:absolute;left:{pct:.2f}%;transform:translateX(-50%);'
            f'font-size:0.7em;color:#888;white-space:nowrap">{ts}</span>'
        )
        t += tick_ms

    html += '</div></div>'  # close axis row
    html += '</div>'        # close outer
    html += (
        '<script>'
        'function selectClaim(id){'
        'window.parent.postMessage({type:"tl_claim_select",claim_id:id},"*");}'
        '</script>'
    )

    return html


def apply_filters(
    claims: list[dict],
    cf: dict,
    verdicts: dict,
    survivability: dict,
    has_fallacy_map: dict,
    has_device_map: dict,
    conn_count_map: dict,
) -> list[dict]:
    """Return the subset of claims matching all active filters (AND logic)."""
    result = claims

    if cf.get("speaker"):
        result = [c for c in result if c.get("speaker") == cf["speaker"]]
    if cf.get("claim_type"):
        result = [c for c in result if c.get("claim_type") == cf["claim_type"]]
    if cf.get("thread_id"):
        result = [c for c in result if c.get("thread_id") == cf["thread_id"]]
    if cf.get("text_query", "").strip():
        _q = cf["text_query"].strip().lower()
        result = [c for c in result if _q in c.get("text", "").lower()]
    if cf.get("verdicts"):
        result = [c for c in result
                  if verdicts.get(c["id"], {}).get("verdict") in cf["verdicts"]]
    if cf.get("survivability"):
        result = [c for c in result
                  if survivability.get(c["id"]) == cf["survivability"]]
    if cf.get("has_fallacy") is not None:
        result = [c for c in result
                  if has_fallacy_map.get(c["id"], False) == cf["has_fallacy"]]
    if cf.get("has_device") is not None:
        result = [c for c in result
                  if has_device_map.get(c["id"], False) == cf["has_device"]]
    if cf.get("connections") is not None:
        _th = cf["connections"]
        if _th == 0:
            result = [c for c in result if conn_count_map.get(c["id"], 0) == 0]
        else:
            result = [c for c in result if conn_count_map.get(c["id"], 0) >= _th]
    if cf.get("checkable") is not None:
        result = [c for c in result if bool(c.get("checkable")) == cf["checkable"]]
    if cf.get("qualifier"):
        result = [c for c in result if c.get("qualifier") == cf["qualifier"]]
    if cf.get("stance"):
        result = [c for c in result if c.get("stance") == cf["stance"]]

    return result


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
        st.divider()
        _slang = st.session_state["lang"]
        with st.expander(
            f"📖 {LABELS['help_sidebar_heading'][_slang]}", expanded=False
        ):
            _SIDEBAR_HELP = [
                ("help_link_claims",    help_dialogs.claims_dialog),
                ("help_link_threads",   help_dialogs.threads_dialog),
                ("help_link_responses", help_dialogs.responses_dialog),
                ("help_link_factcheck", help_dialogs.factcheck_dialog),
                ("help_link_rhetoric",  help_dialogs.rhetoric_dialog),
                ("help_link_scoring",   help_dialogs.scoring_dialog),
            ]
            for _lkey, _dlg in _SIDEBAR_HELP:
                if st.button(
                    f"→ {LABELS[_lkey][_slang]}",
                    key=f"help_{_lkey}_sidebar",
                    use_container_width=True,
                ):
                    _dlg(_slang)

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
                    _spk_names_meta  = data.get("_speaker_names",  {})
                    _spk_merges_meta = data.get("_speaker_merges", {})

                    if _spk_names_meta:
                        # New format: utterances already have single-char IDs;
                        # restore speaker names and merge mappings to session state.
                        for _sid, _name in _spk_names_meta.items():
                            if _name:
                                st.session_state[f"speaker_name_{_sid}"] = _name
                        # _speaker_merges is informational (merge already baked in),
                        # but restore it so the merge UI reflects the original setup
                        # if the merged-away speaker still appears in utterances.
                        for _sid, _tgt in _spk_merges_meta.items():
                            st.session_state[f"speaker_merge_{_sid}"] = _tgt
                    else:
                        # Old / third-party format: utterances may use full names
                        # instead of single-char IDs — remap back to letters.
                        raw_speakers = sorted({u["speaker"] for u in data["utterances"]})
                        if any(len(s) > 1 for s in raw_speakers):
                            sid_map = {s: chr(ord("A") + i)
                                       for i, s in enumerate(raw_speakers)}
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
            slug   = "".join(c if c.isalnum() or c in "-_" else "_"
                             for c in t.get("_title", "transcript")).strip()[:50]
            dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Active speakers after merging (merged-away IDs are gone from utterances)
            _active_spks = {u["speaker"] for u in merged_utterances}

            # JSON export: keep original single-char IDs; embed names + merges as
            # metadata so re-importing restores the speaker setup automatically.
            json_export = {
                **t,
                "utterances":       merged_utterances,
                "_speaker_names":   {
                    sid: name
                    for sid, name in speaker_names.items()
                    if sid in _active_spks and name
                },
                "_speaker_merges":  {
                    sid: tgt
                    for sid, tgt in merge_map.items()
                    if tgt != sid
                },
            }
            # PDF export: substitute names so the document is human-readable
            export_t = substitute_names(
                {**t, "utterances": merged_utterances}, speaker_names
            )

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label     = L("btn_dl_json"),
                    data      = json.dumps(json_export, indent=2, ensure_ascii=False),
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

            # ── Debate motion input ────────────────────────────────────────────
            st.session_state["motion"] = st.text_input(
                L("motion_label"),
                value=st.session_state.get("motion", ""),
                placeholder=L("motion_ph"),
                help=L("motion_help"),
            )

            # ── Run Analysis button ────────────────────────────────────────────
            if not anthropic_key:
                st.warning(L("no_anthropic_an"))

            _has_analysis = bool(st.session_state.get("analysis"))
            with st.expander(L("analysis_empty_heading"), expanded=not _has_analysis):
                st.caption(L("analysis_empty_intro"))
                _HELP_ROWS = [
                    ("analysis_bullet_claims",    "help_link_claims",    help_dialogs.claims_dialog),
                    ("analysis_bullet_threads",   "help_link_threads",   help_dialogs.threads_dialog),
                    ("analysis_bullet_responses", "help_link_responses", help_dialogs.responses_dialog),
                    ("analysis_bullet_factcheck", "help_link_factcheck", help_dialogs.factcheck_dialog),
                    ("analysis_bullet_rhetoric",  "help_link_rhetoric",  help_dialogs.rhetoric_dialog),
                    ("analysis_bullet_scoring",   "help_link_scoring",   help_dialogs.scoring_dialog),
                ]
                for _bkey, _lkey, _dlg in _HELP_ROWS:
                    _col_txt, _col_btn = st.columns([7, 3])
                    with _col_txt:
                        st.markdown(f"- {L(_bkey)}")
                    with _col_btn:
                        if st.button(
                            f"→ {L(_lkey)}",
                            key=f"help_{_lkey}_empty",
                            use_container_width=True,
                        ):
                            _dlg(lang)

            col_btn, col_note, col_dl_pdf, col_dl_json = st.columns([1, 2, 1, 1])
            with col_btn:
                run_clicked = st.button(
                    L("run_analysis"), type="primary", disabled=not anthropic_key,
                )
            with col_note:
                st.caption(L("analysis_cost"))
            _an_ss = st.session_state.get("analysis")
            if _an_ss:
                _an_title_dl = t.get("_title", "Debate") if t else "Debate"
                _verdicts_dl = st.session_state.get("verdicts", {})
                _sr_dl       = st.session_state.get("speaker_report", {})
                with col_dl_pdf:
                    try:
                        _pdf_dl = build_analysis_pdf(
                            claims        = _an_ss.get("claims", []),
                            threads       = _an_ss.get("threads", []),
                            speaker_names = speaker_names_an,
                            speaker_report= _sr_dl,
                            verdicts      = _verdicts_dl,
                            title         = _an_title_dl,
                        )
                    except Exception:
                        _pdf_dl = b""
                    st.download_button(
                        label     = L("btn_dl_analysis_pdf"),
                        data      = _pdf_dl,
                        file_name = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime      = "application/pdf",
                        disabled  = not _pdf_dl,
                        use_container_width=True,
                    )
                with col_dl_json:
                    _json_dl = json.dumps(
                        {
                            "analysis":       _an_ss,
                            "verdicts":       _verdicts_dl,
                            "speaker_report": _sr_dl,
                        },
                        indent=2, ensure_ascii=False,
                    )
                    st.download_button(
                        label     = L("btn_dl_analysis_json"),
                        data      = _json_dl.encode("utf-8"),
                        file_name = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime      = "application/json",
                        use_container_width=True,
                    )

            if run_clicked and anthropic_key:
                transcript_id = st.session_state.get("_current_id", "unknown")
                aid = save_analysis(transcript_id, "claude-haiku-4-5-20251001 + claude-sonnet-4-6")
                st.session_state["_analysis_id"] = aid
                prog = st.progress(0, text=L("prog_seg"))
                try:
                    turns = segment_turns(utterances_an)
                    prog.progress(5, text=L("prog_seg"))

                    _motion = st.session_state.get("motion", "")
                    all_claims: list[dict] = []
                    for i, turn in enumerate(turns):
                        claims = extract_claims_from_turn(turn, anthropic_key, motion=_motion)
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
                    prog.progress(93, text=L("deduplicating"))
                    mark_restatements(classified, anthropic_key)
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
                # ── Load saved results ────────────────────────────────────────
                with st.expander(L("load_results_expander")):
                    _lv_col, _lr_col, _lrh_col, _lsr_col = st.columns(4)
                    with _lv_col:
                        _vf = st.file_uploader(L("upload_verdicts_label"), type=["json"], key="ul_verdicts")
                        if _vf and st.button(L("load_verdicts_btn"), key="btn_ul_verdicts"):
                            try:
                                _d = json.loads(_vf.read())
                                if not isinstance(_d.get("verdicts"), dict):
                                    st.error(L("err_not_verdicts_json"))
                                else:
                                    st.session_state["verdicts"] = _d["verdicts"]
                                    st.success(L("verdicts_loaded"))
                                    st.rerun()
                            except Exception:
                                st.error(L("err_invalid_json"))
                    with _lr_col:
                        _rf = st.file_uploader(L("upload_responses_label"), type=["json"], key="ul_responses")
                        if _rf and st.button(L("load_responses_btn"), key="btn_ul_responses"):
                            try:
                                _d = json.loads(_rf.read())
                                if not isinstance(_d.get("responses"), list):
                                    st.error(L("err_not_responses_json"))
                                else:
                                    st.session_state["responses"] = _d["responses"]
                                    st.session_state["survivability"] = compute_grounded_extension(
                                        analysis.get("claims", []), _d["responses"],
                                    )
                                    st.success(L("responses_loaded"))
                                    st.rerun()
                            except Exception:
                                st.error(L("err_invalid_json"))
                    with _lrh_col:
                        _rhf = st.file_uploader(L("upload_rhetoric_label"), type=["json"], key="ul_rhetoric")
                        if _rhf and st.button(L("load_rhetoric_btn"), key="btn_ul_rhetoric"):
                            try:
                                _d = json.loads(_rhf.read())
                                if not isinstance(_d.get("rhetoric"), list):
                                    st.error(L("err_not_rhetoric_json"))
                                else:
                                    st.session_state["rhetoric"] = _d["rhetoric"]
                                    if isinstance(_d.get("stages"), list):
                                        st.session_state["stages"] = _d["stages"]
                                    st.success(L("rhetoric_loaded"))
                                    st.rerun()
                            except Exception:
                                st.error(L("err_invalid_json"))
                    with _lsr_col:
                        _srf = st.file_uploader(L("upload_speaker_report_label"), type=["json"], key="ul_speaker_report")
                        if _srf and st.button(L("load_speaker_report_btn"), key="btn_ul_speaker_report"):
                            try:
                                _d = json.loads(_srf.read())
                                if not isinstance(_d.get("speaker_report"), dict):
                                    st.error(L("err_not_speaker_report_json"))
                                else:
                                    st.session_state["speaker_report"] = _d["speaker_report"]
                                    st.success(L("speaker_report_loaded"))
                                    st.rerun()
                            except Exception:
                                st.error(L("err_invalid_json"))

                col_fc, col_fc_note, col_fc_dl = st.columns([2, 3, 2])
                with col_fc:
                    fc_clicked = st.button(L("run_factcheck"), disabled=not anthropic_key)
                with col_fc_note:
                    st.caption(L("factcheck_cost"))
                with col_fc_dl:
                    if st.session_state.get("verdicts"):
                        st.download_button(
                            label     = L("dl_verdicts"),
                            data      = json.dumps(
                                {"type": "fact_check",
                                 "verdicts": st.session_state["verdicts"]},
                                indent=2, ensure_ascii=False,
                            ).encode(),
                            file_name = f"fact_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime      = "application/json",
                            key       = "dl_verdicts_btn",
                        )

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
                        and not c.get("restatement_of")
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
                    st.rerun()

            # ── Sub-tabs ───────────────────────────────────────────────────────
            if analysis:
                # ── Pipeline settings (model / batch selection) ────────────────
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

                # ── Dynamic cost estimates ─────────────────────────────────────
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

                # ── Detect Responses button ────────────────────────────────────
                col_dr, col_dr_note, col_dr_dl = st.columns([1, 2, 2])
                with col_dr:
                    dr_clicked = st.button(L("detect_responses"), disabled=not anthropic_key)
                with col_dr_note:
                    st.caption(_dr_note)
                with col_dr_dl:
                    if st.session_state.get("responses"):
                        st.download_button(
                            label     = L("dl_responses"),
                            data      = json.dumps(
                                {"responses": st.session_state["responses"]},
                                indent=2, ensure_ascii=False,
                            ).encode(),
                            file_name = f"responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime      = "application/json",
                            key       = "dl_responses_btn",
                        )

                _dr_help_col, _ = st.columns([3, 7])
                with _dr_help_col:
                    if st.button(f"→ {L('help_link_responses')}", key="help_responses_dr"):
                        help_dialogs.responses_dialog(lang)

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
                        st.session_state["survivability"] = compute_grounded_extension(
                            analysis.get("claims", []),
                            st.session_state["responses"],
                        )
                        st.rerun()
                    except Exception as exc:
                        _prog_dr.empty()
                        st.error(str(exc))

                # ── Analyze Rhetoric button ────────────────────────────────────
                col_rh, col_rh_note, col_rh_dl = st.columns([1, 2, 2])
                with col_rh:
                    rh_clicked = st.button(L("run_rhetoric"), disabled=not anthropic_key)
                with col_rh_note:
                    st.caption(_rh_note)
                with col_rh_dl:
                    if st.session_state.get("rhetoric"):
                        st.download_button(
                            label     = L("dl_rhetoric"),
                            data      = json.dumps(
                                {
                                    "rhetoric": st.session_state["rhetoric"],
                                    "stages":   st.session_state.get("stages", []),
                                },
                                indent=2, ensure_ascii=False,
                            ).encode(),
                            file_name = f"rhetoric_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime      = "application/json",
                            key       = "dl_rhetoric_btn",
                        )

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
                    prog_rh.progress(100, text=L("stage_labeling"))
                    label_dialectical_stages(turns_rh, anthropic_key)
                    st.session_state["stages"] = [
                        {
                            "turn_index":        t["turn_index"],
                            "speaker":           t["speaker"],
                            "start_ms":          t["start_ms"],
                            "dialectical_stage": t.get("dialectical_stage", "argumentation"),
                        }
                        for t in turns_rh
                    ]
                    st.rerun()

                # ── Speaker Report button ──────────────────────────────────────
                has_any_data = any([
                    st.session_state.get("verdicts"),
                    st.session_state.get("responses"),
                    st.session_state.get("rhetoric"),
                ])
                col_sr, col_sr_note, col_sr_dl = st.columns([1, 2, 2])
                with col_sr:
                    sr_clicked = st.button(L("run_report"), disabled=not (anthropic_key and has_any_data))
                with col_sr_note:
                    if not has_any_data:
                        st.caption(L("report_need_data"))
                    else:
                        st.caption(L("report_cost"))
                with col_sr_dl:
                    if st.session_state.get("speaker_report"):
                        st.download_button(
                            label     = L("dl_speaker_report"),
                            data      = json.dumps(
                                {"speaker_report": st.session_state["speaker_report"]},
                                indent=2, ensure_ascii=False,
                            ).encode(),
                            file_name = f"speaker_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime      = "application/json",
                            key       = "dl_speaker_report_btn",
                        )

                if sr_clicked and anthropic_key and has_any_data:
                    verdicts_ss  = st.session_state.get("verdicts", {})
                    responses_ss = st.session_state.get("responses") or []
                    rhetoric_ss  = st.session_state.get("rhetoric") or []
                    claims_mv    = [
                        {**c, "verdict": verdicts_ss.get(c["id"], {}).get("verdict", "")}
                        for c in analysis.get("claims", [])
                    ]
                    scores = compute_speaker_scores(
                        claims_mv, responses_ss, rhetoric_ss,
                        threads=analysis.get("threads", []),
                    )
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
                    st.session_state["debate_score"] = compute_debate_scores(
                        claims=analysis.get("claims", []),
                        responses=st.session_state.get("responses", []),
                        stages=st.session_state.get("stages", []),
                        threads=analysis.get("threads", []),
                    )
                    st.rerun()

                st.divider()

                # ── Debate scorecard banner ────────────────────────────────────
                _ds = st.session_state.get("debate_score")
                if _ds:
                    ds1, ds2, ds3, ds4, ds5 = st.columns(5)
                    ds1.metric(
                        L("ds_response_density"),
                        f'{_ds.get("response_density", 0):.1f}',
                        help=L("ds_response_density_help"),
                    )
                    ds2.metric(
                        L("ds_evasion_rate"),
                        (f'{_ds["evasion_rate"]:.0%}'
                         if _ds.get("evasion_rate") is not None
                         else L("metric_na")),
                        help=L("ds_evasion_rate_help"),
                    )
                    ds3.metric(
                        L("ds_completeness"),
                        f'{_ds.get("dialectical_completeness", 0):.0%}',
                        help=L("ds_completeness_help"),
                    )
                    ds4.metric(
                        L("ds_thread_coverage"),
                        (f'{_ds["thread_coverage"]:.0%}'
                         if _ds.get("thread_coverage") is not None
                         else L("metric_na")),
                        help=L("ds_thread_coverage_help"),
                    )
                    ds5.metric(
                        L("ds_concessions"),
                        str(_ds.get("concession_count", 0)),
                        help=L("ds_concessions_help"),
                    )
                    st.divider()

                subtab_claims, subtab_timeline, subtab_fc, subtab_map, subtab_rhetoric, subtab_report = st.tabs(
                    [L("subtab_claims"), L("subtab_timeline"), L("subtab_factcheck"),
                     L("subtab_map"), L("subtab_rhetoric"), L("subtab_report")]
                )

                # ── Claims sub-tab ─────────────────────────────────────────────
                with subtab_claims:
                    claims   = analysis.get("claims", [])
                    threads  = analysis.get("threads", [])
                    verdicts = st.session_state.get("verdicts", {})

                    # ── Derived filter attributes ──────────────────────────────
                    _rhet_ss_f  = st.session_state.get("rhetoric") or []
                    _resp_ss_f  = st.session_state.get("responses") or []
                    _surv_ss_f  = st.session_state.get("survivability", {})

                    _rh_by_ms_f = {item["start_ms"]: item for item in _rhet_ss_f}

                    _claim_has_fallacy: dict[str, bool] = {
                        c["id"]: bool(
                            _rh_by_ms_f.get(c.get("start_ms", -1), {}).get("fallacies")
                        )
                        for c in claims
                    }
                    _claim_has_device: dict[str, bool] = {
                        c["id"]: any(
                            not d.get("is_fallacy", False)
                            for d in _rh_by_ms_f.get(
                                c.get("start_ms", -1), {}
                            ).get("rhetorical_devices", [])
                        )
                        for c in claims
                    }
                    _conn_counter: dict[str, int] = {}
                    for _resp_f in _resp_ss_f:
                        for _ck in ("from_claim_id", "responds_to_claim_id"):
                            _cid_f = _resp_f.get(_ck, "")
                            if _cid_f:
                                _conn_counter[_cid_f] = _conn_counter.get(_cid_f, 0) + 1
                    _claim_conn_count: dict[str, int] = {
                        c["id"]: _conn_counter.get(c["id"], 0) for c in claims
                    }

                    if "claim_filter" not in st.session_state:
                        st.session_state["claim_filter"] = {}

                    if not claims:
                        st.info(L("analysis_no_claims"))
                    else:
                        n_spk = len({c["speaker"] for c in claims})
                        _sum_col, _hc1, _hc2 = st.columns([6, 2, 2])
                        with _sum_col:
                            st.markdown(LABELS["analysis_summary"][lang].format(
                                n=len(claims), t=len(threads), s=n_spk,
                            ))
                        with _hc1:
                            if st.button(f"→ {L('help_link_claims')}", key="help_claims_table"):
                                help_dialogs.claims_dialog(lang)
                        with _hc2:
                            if st.button(f"→ {L('help_link_threads')}", key="help_threads_table"):
                                help_dialogs.threads_dialog(lang)

                        # ── Filter panel ──────────────────────────────────────
                        _cf = st.session_state["claim_filter"]

                        # Row 1: always-visible filters
                        _fr1, _fr2, _fr3, _fr4 = st.columns([2, 2, 2, 3])
                        with _fr1:
                            _spk_id_list = [None] + sorted({c["speaker"] for c in claims})
                            _spk_disp    = {None: L("filter_all")} | {
                                s: speaker_names_an.get(s, s) for s in _spk_id_list[1:]
                            }
                            _sel_spk = st.selectbox(
                                L("filter_speaker"),
                                options=_spk_id_list,
                                format_func=lambda k: _spk_disp[k],
                                index=_spk_id_list.index(_cf.get("speaker"))
                                if _cf.get("speaker") in _spk_id_list else 0,
                            )
                            _cf["speaker"] = _sel_spk

                        with _fr2:
                            _type_list = [None] + sorted(
                                {c.get("claim_type", "") for c in claims
                                 if c.get("claim_type")}
                            )
                            _sel_type = st.selectbox(
                                L("filter_type"),
                                options=_type_list,
                                format_func=lambda k: L("filter_all") if k is None else k,
                                index=_type_list.index(_cf.get("claim_type"))
                                if _cf.get("claim_type") in _type_list else 0,
                            )
                            _cf["claim_type"] = _sel_type

                        with _fr3:
                            _thr_ids  = [None] + [t["thread_id"] for t in threads]
                            _thr_disp = {None: L("filter_all")} | {
                                t["thread_id"]: (t.get("topic", t["thread_id"]))[:35]
                                for t in threads
                            }
                            _sel_thread = st.selectbox(
                                L("filter_thread"),
                                options=_thr_ids,
                                format_func=lambda k: _thr_disp.get(k, k),
                                index=_thr_ids.index(_cf.get("thread_id"))
                                if _cf.get("thread_id") in _thr_ids else 0,
                            )
                            _cf["thread_id"] = _sel_thread

                        with _fr4:
                            _sel_text = st.text_input(
                                L("filter_text"),
                                value=_cf.get("text_query", ""),
                            )
                            _cf["text_query"] = _sel_text

                        # Default for _cn_disp (used in chip display even when no responses)
                        _cn_disp = {
                            None: L("filter_conn_any"),
                            1:    L("filter_conn_1"),
                            3:    L("filter_conn_3"),
                            0:    L("filter_conn_0"),
                        }

                        # Row 2: more filters expander
                        with st.expander(L("filter_more"), expanded=False):
                            _mf_col_idx = 0
                            _mf_cols    = st.columns(4)

                            # Verdict
                            if verdicts:
                                _v_opts = sorted({
                                    v.get("verdict") for v in verdicts.values()
                                    if v.get("verdict")
                                })
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_v = st.multiselect(
                                        L("filter_verdict"),
                                        options=_v_opts,
                                        default=[
                                            x for x in _cf.get("verdicts", [])
                                            if x in _v_opts
                                        ],
                                        format_func=lambda k: L(f"verdict_{k}")
                                        if f"verdict_{k}" in LABELS else k,
                                    )
                                    _cf["verdicts"] = _sel_v
                                _mf_col_idx += 1

                            # Argument status
                            if _surv_ss_f:
                                _sa_opts = [None, "grounded", "contested", "unattacked"]
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_sa = st.selectbox(
                                        L("filter_survivability"),
                                        options=_sa_opts,
                                        format_func=lambda k: L("filter_any")
                                        if k is None else L(f"surv_{k}"),
                                        index=_sa_opts.index(_cf.get("survivability"))
                                        if _cf.get("survivability") in _sa_opts else 0,
                                    )
                                    _cf["survivability"] = _sel_sa
                                _mf_col_idx += 1

                            # Has fallacy
                            if _rhet_ss_f:
                                _hf_opts = [None, True, False]
                                _hf_disp = {
                                    None:  L("filter_any"),
                                    True:  L("filter_yes"),
                                    False: L("filter_no"),
                                }
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_hf = st.selectbox(
                                        L("filter_has_fallacy"),
                                        options=_hf_opts,
                                        format_func=lambda k: _hf_disp[k],
                                        index=_hf_opts.index(_cf.get("has_fallacy"))
                                        if _cf.get("has_fallacy") in _hf_opts else 0,
                                    )
                                    _cf["has_fallacy"] = _sel_hf
                                _mf_col_idx += 1

                            # Has device
                            if _rhet_ss_f:
                                _hd_opts = [None, True, False]
                                _hd_disp = {
                                    None:  L("filter_any"),
                                    True:  L("filter_yes"),
                                    False: L("filter_no"),
                                }
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_hd = st.selectbox(
                                        L("filter_has_device"),
                                        options=_hd_opts,
                                        format_func=lambda k: _hd_disp[k],
                                        index=_hd_opts.index(_cf.get("has_device"))
                                        if _cf.get("has_device") in _hd_opts else 0,
                                    )
                                    _cf["has_device"] = _sel_hd
                                _mf_col_idx += 1

                            # Connections
                            if _resp_ss_f:
                                _cn_opts = [None, 1, 3, 0]
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_cn = st.selectbox(
                                        L("filter_connections"),
                                        options=_cn_opts,
                                        format_func=lambda k: _cn_disp[k],
                                        index=_cn_opts.index(_cf.get("connections"))
                                        if _cf.get("connections") in _cn_opts else 0,
                                    )
                                    _cf["connections"] = _sel_cn
                                _mf_col_idx += 1

                            # Checkable
                            _ck_opts = [None, True, False]
                            _ck_disp = {
                                None:  L("filter_any"),
                                True:  L("filter_yes"),
                                False: L("filter_no"),
                            }
                            with _mf_cols[_mf_col_idx % 4]:
                                _sel_ck = st.selectbox(
                                    L("filter_checkable"),
                                    options=_ck_opts,
                                    format_func=lambda k: _ck_disp[k],
                                    index=_ck_opts.index(_cf.get("checkable"))
                                    if _cf.get("checkable") in _ck_opts else 0,
                                )
                                _cf["checkable"] = _sel_ck
                            _mf_col_idx += 1

                            # Qualifier
                            _ql_vals = sorted({
                                c.get("qualifier", "") for c in claims
                                if c.get("qualifier")
                            })
                            if _ql_vals:
                                _ql_opts = [None] + _ql_vals
                                _ql_disp = LABELS["qualifier_labels"][lang]
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_ql = st.selectbox(
                                        L("filter_qualifier"),
                                        options=_ql_opts,
                                        format_func=lambda k: L("filter_any")
                                        if k is None else _ql_disp.get(k, k),
                                        index=_ql_opts.index(_cf.get("qualifier"))
                                        if _cf.get("qualifier") in _ql_opts else 0,
                                    )
                                    _cf["qualifier"] = _sel_ql
                                _mf_col_idx += 1

                            # Stance (only if motion set)
                            if st.session_state.get("motion", "").strip():
                                _st_opts = [None, "pro", "con", "neutral"]
                                _st_disp = {
                                    None:      L("filter_any"),
                                    "pro":     L("stance_pro"),
                                    "con":     L("stance_con"),
                                    "neutral": L("stance_neutral"),
                                }
                                with _mf_cols[_mf_col_idx % 4]:
                                    _sel_st = st.selectbox(
                                        L("filter_stance"),
                                        options=_st_opts,
                                        format_func=lambda k: _st_disp[k],
                                        index=_st_opts.index(_cf.get("stance"))
                                        if _cf.get("stance") in _st_opts else 0,
                                    )
                                    _cf["stance"] = _sel_st

                        # Row 3: active filter chips + clear
                        _CHIP_LABELS: dict[str, tuple] = {}
                        if _cf.get("speaker"):
                            _CHIP_LABELS["speaker"] = (
                                L("filter_speaker"),
                                speaker_names_an.get(_cf["speaker"], _cf["speaker"]),
                            )
                        if _cf.get("claim_type"):
                            _CHIP_LABELS["claim_type"] = (L("filter_type"), _cf["claim_type"])
                        if _cf.get("thread_id"):
                            _tn = _thr_disp.get(_cf["thread_id"], _cf["thread_id"])
                            _CHIP_LABELS["thread_id"] = (L("filter_thread"), _tn[:20])
                        if _cf.get("text_query", "").strip():
                            _CHIP_LABELS["text_query"] = (
                                "🔍", f'"{_cf["text_query"][:18]}"'
                            )
                        if _cf.get("verdicts"):
                            _CHIP_LABELS["verdicts"] = (
                                L("filter_verdict"), ", ".join(_cf["verdicts"])
                            )
                        if _cf.get("survivability"):
                            _CHIP_LABELS["survivability"] = (
                                L("filter_survivability"),
                                L(f'surv_{_cf["survivability"]}'),
                            )
                        if _cf.get("has_fallacy") is not None:
                            _CHIP_LABELS["has_fallacy"] = (
                                L("filter_has_fallacy"),
                                L("filter_yes") if _cf["has_fallacy"] else L("filter_no"),
                            )
                        if _cf.get("has_device") is not None:
                            _CHIP_LABELS["has_device"] = (
                                L("filter_has_device"),
                                L("filter_yes") if _cf["has_device"] else L("filter_no"),
                            )
                        if _cf.get("connections") is not None:
                            _CHIP_LABELS["connections"] = (
                                L("filter_connections"),
                                _cn_disp.get(_cf["connections"], str(_cf["connections"])),
                            )
                        if _cf.get("checkable") is not None:
                            _CHIP_LABELS["checkable"] = (
                                L("filter_checkable"),
                                L("filter_yes") if _cf["checkable"] else L("filter_no"),
                            )
                        if _cf.get("qualifier"):
                            _ql_disp2 = LABELS["qualifier_labels"][lang]
                            _CHIP_LABELS["qualifier"] = (
                                L("filter_qualifier"),
                                _ql_disp2.get(_cf["qualifier"], _cf["qualifier"]),
                            )
                        if _cf.get("stance"):
                            _CHIP_LABELS["stance"] = (
                                L("filter_stance"),
                                {
                                    "pro":     L("stance_pro"),
                                    "con":     L("stance_con"),
                                    "neutral": L("stance_neutral"),
                                }.get(_cf["stance"], _cf["stance"]),
                            )

                        if _CHIP_LABELS:
                            _chip_cols = st.columns(len(_CHIP_LABELS) + 1)
                            _DEFAULTS  = {
                                "speaker": None, "claim_type": None, "thread_id": None,
                                "text_query": "", "verdicts": [], "survivability": None,
                                "has_fallacy": None, "has_device": None,
                                "connections": None, "checkable": None,
                                "qualifier": None, "stance": None,
                            }
                            for _ci, (_ck, (_cl, _cv)) in enumerate(_CHIP_LABELS.items()):
                                with _chip_cols[_ci]:
                                    if st.button(
                                        f"✕ {_cl}: {_cv}",
                                        key=f"chip_clear_{_ck}",
                                        use_container_width=True,
                                    ):
                                        _cf[_ck] = _DEFAULTS.get(_ck)
                                        st.rerun()
                            with _chip_cols[-1]:
                                if st.button(
                                    L("filter_clear_all"),
                                    key="chip_clear_all",
                                    use_container_width=True,
                                ):
                                    st.session_state["claim_filter"] = {}
                                    st.rerun()

                        # Apply filters → sorted_claims
                        _filtered_claims = apply_filters(
                            claims, _cf, verdicts, _surv_ss_f,
                            _claim_has_fallacy, _claim_has_device, _claim_conn_count,
                        )
                        st.session_state["filtered_claims"] = _filtered_claims

                        sorted_claims = sorted(
                            _filtered_claims,
                            key=lambda c: (c.get("thread_id", ""), c.get("start_ms", 0)),
                        )
                        if len(sorted_claims) < len(claims):
                            st.caption(
                                LABELS["filter_count"][lang].format(
                                    n=len(sorted_claims), m=len(claims)
                                )
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

                        # Lookup helpers used in both table paths
                        _claim_by_id = {c["id"]: c for c in claims}

                        # Survivability icon helper (used in both table paths)
                        _surv_ss = st.session_state.get("survivability", {})
                        _SURV_ICON = {
                            "grounded":   f'<span style="color:#2ca02c;font-weight:bold" title="{L("surv_grounded")}">●</span> ',
                            "contested":  f'<span style="color:#ff7f0e;font-weight:bold" title="{L("surv_contested")}">●</span> ',
                            "unattacked": f'<span style="color:#aaaaaa" title="{L("surv_unattacked")}">○</span> ',
                        }

                        def surv_icon(cid: str) -> str:
                            return _SURV_ICON.get(_surv_ss.get(cid, ""), "")

                        # Qualifier and stance helpers (used in both table paths)
                        _QUAL_LABELS     = LABELS["qualifier_labels"][lang]
                        _motion_for_tags = st.session_state.get("motion", "").strip()
                        _STANCE_TAG = {
                            "pro": (
                                f'<span style="color:#2ca02c;font-size:0.78em;font-weight:bold"'
                                f' title="{L("stance_pro")}">▲</span> '
                            ),
                            "con": (
                                f'<span style="color:#d62728;font-size:0.78em;font-weight:bold"'
                                f' title="{L("stance_con")}">▼</span> '
                            ),
                        }

                        # ── Collapsible, scrollable table ─────────────────────
                        # Table — HTML with badge column when verdicts present
                        if verdicts:
                            _legend_html = " &nbsp;|&nbsp; ".join(
                                f'<span style="background:{bg};border-radius:4px;padding:1px 7px;font-size:0.82em">{lbl}</span>'
                                for bg, lbl in [
                                    ("#d4edda", L("verdict_true")),
                                    ("#fff3cd", L("verdict_partly_true")),
                                    ("#fde8c8", L("verdict_contested")),
                                    ("#f8d7da", L("verdict_false")),
                                    ("#e2e3e5", L("verdict_unverifiable")),
                                ]
                            )
                            _legend_div = (
                                f'<div style="margin-bottom:8px"><small><strong>{L("verdict_legend_label")}</strong> '
                                f'{_legend_html}</small></div>'
                            )
                            th = "padding:6px 8px;text-align:left;border-bottom:2px solid #dee2e6;font-size:0.88em"
                            td = "padding:5px 8px;border-bottom:1px solid #f0f0f0;font-size:0.85em;vertical-align:top"

                            def _abbr(text: str, tip: str) -> str:
                                return (
                                    f'<abbr title="{tip}" style="cursor:help;text-decoration:underline dotted #888">'
                                    f'{text}</abbr>'
                                )

                            hdrs = [
                                L("col_thread"),
                                L("col_speaker"),
                                L("col_time"),
                                _abbr(L("col_type"),      L("col_type_help")),
                                _abbr(L("col_checkable"), L("col_checkable_help")),
                                _abbr(L("col_verdict"),   L("col_verdict_help")),
                                L("col_claim"),
                            ]
                            hdr_html = "".join(f"<th style='{th}'>{h}</th>" for h in hdrs)
                            rows_html = ""
                            for c in sorted_claims:
                                v_key = verdicts.get(c["id"], {}).get("verdict", "")
                                short = (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"]
                                restat_id = c.get("restatement_of")
                                if restat_id:
                                    orig_text = _claim_by_id.get(restat_id, {}).get("text", "")
                                    orig_preview = (orig_text[:60] + "…") if len(orig_text) > 60 else orig_text
                                    restat_badge = (
                                        f'<span style="background:#f0f0f0;border-radius:4px;'
                                        f'padding:1px 5px;font-size:0.78em;color:#888">'
                                        f'{L("restatement_badge")}</span>'
                                    )
                                    claim_cell = (
                                        f'<span style="color:#aaaaaa;font-style:italic">'
                                        f'{short}</span> {restat_badge}'
                                        + (f'<br><small style="color:#aaaaaa">'
                                           f'{L("restatement_label")} {orig_preview}</small>'
                                           if orig_preview else "")
                                    )
                                else:
                                    _qual_lbl   = _QUAL_LABELS.get(c.get("qualifier", ""), "")
                                    _qual_html  = (
                                        f'<br><small style="color:#888;font-style:italic">'
                                        f'{_qual_lbl}</small>'
                                        if _qual_lbl else ""
                                    )
                                    _stance_html = (
                                        _STANCE_TAG.get(c.get("stance", ""), "")
                                        if _motion_for_tags else ""
                                    )
                                    claim_cell = f"{surv_icon(c['id'])}{_stance_html}{short}{_qual_html}"
                                rows_html += (
                                    f"<tr>"
                                    f"<td style='{td}'>{c.get('thread_id','')}</td>"
                                    f"<td style='{td}'>{speaker_names_an.get(c['speaker'], c['speaker'])}</td>"
                                    f"<td style='{td}'>{ms_to_ts(c.get('start_ms', 0))}</td>"
                                    f"<td style='{td}'>{c.get('claim_type','')}</td>"
                                    f"<td style='{td}'>{'yes' if c.get('checkable') else 'no'}</td>"
                                    f"<td style='{td}'>{badge(v_key)}</td>"
                                    f"<td style='{td}'>{claim_cell}</td>"
                                    f"</tr>"
                                )
                            st.markdown(
                                f'<details open>'
                                f'<summary style="cursor:pointer;font-weight:600;padding:4px 0;user-select:none">'
                                f'{L("claims_table_expander")} ({len(sorted_claims)})</summary>'
                                f'{_legend_div}'
                                f"<div style='max-height:420px;overflow-y:auto;overflow-x:auto'>"
                                f"<table style='width:100%;border-collapse:collapse'>"
                                f"<thead><tr>{hdr_html}</tr></thead><tbody>{rows_html}</tbody></table></div>"
                                f'</details>',
                                unsafe_allow_html=True,
                            )
                        else:
                            with st.expander(f"{L('claims_table_expander')} ({len(sorted_claims)})", expanded=True):
                                def _claim_cell_plain(c: dict) -> str:
                                    short = (c["text"][:120] + "…") if len(c["text"]) > 120 else c["text"]
                                    restat_id = c.get("restatement_of")
                                    if restat_id:
                                        orig_text = _claim_by_id.get(restat_id, {}).get("text", "")
                                        orig_preview = (orig_text[:60] + "…") if len(orig_text) > 60 else orig_text
                                        note = f" [{L('restatement_badge')}: {orig_preview}]" if orig_preview else f" [{L('restatement_badge')}]"
                                        return short + note
                                    suffixes = []
                                    _ql = _QUAL_LABELS.get(c.get("qualifier", ""), "")
                                    if _ql:
                                        suffixes.append(f"({_ql})")
                                    if _motion_for_tags and c.get("stance") in ("pro", "con"):
                                        suffixes.append(
                                            f"[{L('stance_pro') if c['stance'] == 'pro' else L('stance_con')}]"
                                        )
                                    return short + (" " + " ".join(suffixes) if suffixes else "")

                                rows = [
                                    {
                                        L("col_thread"):    c.get("thread_id", ""),
                                        L("col_speaker"):   speaker_names_an.get(c["speaker"], c["speaker"]),
                                        L("col_time"):      ms_to_ts(c.get("start_ms", 0)),
                                        L("col_type"):      c.get("claim_type", ""),
                                        L("col_checkable"): "yes" if c.get("checkable") else "no",
                                        L("col_claim"):     _claim_cell_plain(c),
                                    }
                                    for c in sorted_claims
                                ]
                                st.dataframe(rows, use_container_width=True, height=420)
                                st.caption(L("col_headers_note"))

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

                        # ── Verdict expanders ──────────────────────────────────
                        if verdicts:
                            st.divider()
                            st.info(L("factcheck_disclaimer"))
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

                                    # Qualifier + stance meta-line (small, muted)
                                    _ql = LABELS["qualifier_labels"][lang].get(c.get("qualifier", ""), "")
                                    _exp_parts = []
                                    if _ql:
                                        _exp_parts.append(f"<em>{_ql}</em>")
                                    if st.session_state.get("motion", "").strip() and c.get("stance") in ("pro", "con"):
                                        _sc = "#2ca02c" if c["stance"] == "pro" else "#d62728"
                                        _sl = L("stance_pro") if c["stance"] == "pro" else L("stance_con")
                                        _exp_parts.append(f'<span style="color:{_sc};font-size:0.85em">{_sl}</span>')
                                    if _exp_parts:
                                        st.markdown(
                                            '<span style="color:#888;font-size:0.85em">'
                                            + " &nbsp;·&nbsp; ".join(_exp_parts)
                                            + "</span>",
                                            unsafe_allow_html=True,
                                        )

                                    # Premises (evidence cited by the speaker for this claim)
                                    _premises = c.get("premises", [])
                                    if _premises:
                                        with st.expander(L("evidence_cited")):
                                            for _p in _premises:
                                                st.markdown(f"- {_p}")

                                    # Reasoning details — collapsed by default (Section 8 UI rule)
                                    _warrant  = c.get("warrant_hint")
                                    _rebuttal = c.get("rebuttal_cond")
                                    if _warrant or _rebuttal:
                                        with st.expander(L("reasoning_details")):
                                            if _warrant:
                                                st.markdown(
                                                    f"**{L('reasoning_used')}:** {_warrant}"
                                                )
                                            if _rebuttal:
                                                st.markdown(
                                                    f"**{L('acknowledged_exception')}:** {_rebuttal}"
                                                )

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
                                    _surv_status = _surv_ss.get(cid, "")
                                    _surv_lbl = {
                                        "grounded":   L("surv_grounded"),
                                        "contested":  L("surv_contested"),
                                        "unattacked": L("surv_unattacked"),
                                    }.get(_surv_status, "")
                                    _badge_row = badge(v_key)
                                    if _surv_lbl:
                                        _badge_row += f" &nbsp; {surv_icon(cid)}<small>{_surv_lbl}</small>"
                                    st.markdown(_badge_row, unsafe_allow_html=True)
                                    conf_pct = int(vdict.get("confidence", 0.0) * 100)
                                    st.progress(conf_pct, text=f"{L('col_verdict')}: {conf_pct}%")
                                    st.markdown(vdict.get("explanation", ""))

                                    if v_key == "contested":
                                        if vdict.get("for_the_claim"):
                                            st.markdown(f"**{L('in_favour')}** {vdict['for_the_claim']}")
                                        if vdict.get("against_the_claim"):
                                            st.markdown(f"**{L('against')}** {vdict['against_the_claim']}")

                                    ks = vdict.get("key_source", "")
                                    if ks:
                                        st.caption(f"**Key source:** {ks}")
                                    sources = vdict.get("all_sources") or []
                                    if sources:
                                        st.markdown(f"**{L('sources')}**")
                                        for src in sources:
                                            title_s = src.get("title", "Source") if isinstance(src, dict) else str(src)
                                            url_s   = (src.get("url", "") or "") if isinstance(src, dict) else ""
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

                # ── Thread Timeline sub-tab ───────────────────────────────────
                with subtab_timeline:
                    _tl_claims  = analysis.get("claims", [])
                    _tl_threads = analysis.get("threads", [])

                    if not _tl_threads:
                        st.info(L("timeline_no_analysis"))
                    else:
                        _motion_tl = st.session_state.get("motion", "").strip()
                        if _motion_tl:
                            st.caption(L("motion_caption").format(motion=_motion_tl))

                        # ── Click listener (st_javascript → session_state) ─────
                        _js_click = st_javascript(
                            """new Promise(resolve => {
                                function handler(e) {
                                    if (e.data && e.data.type === 'tl_claim_select') {
                                        window.parent.removeEventListener('message', handler);
                                        resolve(e.data.claim_id);
                                    }
                                }
                                window.parent.addEventListener('message', handler);
                            })""",
                            key="tl_click_listener",
                        )
                        if _js_click and isinstance(_js_click, str) and _js_click.strip():
                            st.session_state["tl_selected_claim"] = _js_click.strip()

                        _sel_cid = st.session_state.get("tl_selected_claim", "")
                        # Clear stale selection if claim no longer exists
                        if _sel_cid and not any(c["id"] == _sel_cid for c in _tl_claims):
                            st.session_state.pop("tl_selected_claim", None)
                            _sel_cid = ""

                        # ── Thread scorecards ──────────────────────────────────
                        _sc_surv_ss = st.session_state.get("survivability", {})
                        _sc_verd_ss = st.session_state.get("verdicts", {})
                        _sc_resp_ss = st.session_state.get("responses", [])
                        _CONC_VERD  = {"true", "partially_true", "false", "contested", "misleading"}

                        with st.expander(L("thread_scorecard_heading"), expanded=False):
                            for _tsc in _tl_threads:
                                _tsc_tid    = _tsc["thread_id"]
                                _tsc_topic  = _tsc.get("topic", _tsc_tid)
                                _tsc_claims = [
                                    c for c in _tl_claims if c.get("thread_id") == _tsc_tid
                                ]
                                _tsc_depth  = len(_tsc_claims)
                                if _tsc_depth == 0:
                                    continue

                                # Speaker breakdown
                                _tsc_per_spk = {}
                                for _c in _tsc_claims:
                                    _tsc_per_spk[_c["speaker"]] = (
                                        _tsc_per_spk.get(_c["speaker"], 0) + 1
                                    )
                                _tsc_balance = " · ".join(
                                    f"{speaker_names_an.get(s, s)} {cnt / _tsc_depth:.0%}"
                                    for s, cnt in sorted(_tsc_per_spk.items())
                                )
                                # Time range for intro line
                                _tsc_t0 = min((c.get("start_ms", 0) for c in _tsc_claims), default=0)
                                _tsc_t1 = max((c.get("end_ms", c.get("start_ms", 0)) for c in _tsc_claims), default=0)

                                # Survival ratio (grounded / total)
                                _tsc_surv = None
                                if _sc_surv_ss:
                                    _tsc_grnd = sum(
                                        1 for c in _tsc_claims
                                        if _sc_surv_ss.get(c["id"]) == "grounded"
                                    )
                                    _tsc_surv = _tsc_grnd / _tsc_depth

                                # Verdict ratio (conclusive verdicts / checkable)
                                _tsc_vrate = None
                                if _sc_verd_ss:
                                    _tsc_ck = [c for c in _tsc_claims if c.get("checkable")]
                                    if _tsc_ck:
                                        _tsc_conc = sum(
                                            1 for c in _tsc_ck
                                            if _sc_verd_ss.get(c["id"], {}).get("verdict")
                                            in _CONC_VERD
                                        )
                                        _tsc_vrate = _tsc_conc / len(_tsc_ck)

                                # Response edges within this thread
                                _tsc_rcount = None
                                if _sc_resp_ss:
                                    _tsc_cids = {c["id"] for c in _tsc_claims}
                                    _tsc_rcount = sum(
                                        1 for r in _sc_resp_ss
                                        if (r.get("from_claim_id") in _tsc_cids
                                            and r.get("responds_to_claim_id") in _tsc_cids)
                                    )

                                with st.expander(_tsc_topic, expanded=False):
                                    # Intro line: full topic + speakers + time range
                                    _tsc_spk_names = ", ".join(
                                        speaker_names_an.get(s, s)
                                        for s in sorted(_tsc_per_spk.keys())
                                    )
                                    st.caption(
                                        f"{_tsc_spk_names} · "
                                        f"{ms_to_ts(_tsc_t0)} – {ms_to_ts(_tsc_t1)}"
                                    )
                                    # Metrics row
                                    _tsc_n_cols = 2 + sum([
                                        _tsc_surv   is not None,
                                        _tsc_vrate  is not None,
                                        _tsc_rcount is not None,
                                    ])
                                    _tsc_cols = st.columns(_tsc_n_cols)
                                    _tsc_cols[0].metric(L("thread_depth"),    _tsc_depth)
                                    _tsc_cols[1].metric(L("thread_speakers"), len(_tsc_per_spk))
                                    _tsc_ci = 2
                                    if _tsc_surv is not None:
                                        _tsc_cols[_tsc_ci].metric(
                                            L("thread_survival"), f"{_tsc_surv:.0%}"
                                        )
                                        _tsc_ci += 1
                                    if _tsc_vrate is not None:
                                        _tsc_cols[_tsc_ci].metric(
                                            L("thread_verdict_rate"), f"{_tsc_vrate:.0%}"
                                        )
                                        _tsc_ci += 1
                                    if _tsc_rcount is not None:
                                        _tsc_cols[_tsc_ci].metric(
                                            L("thread_responses"), _tsc_rcount
                                        )
                                    # Full speaker breakdown below metrics
                                    st.markdown(
                                        f"<small style='color:#888'>{L('thread_balance')}: "
                                        f"{_tsc_balance}</small>",
                                        unsafe_allow_html=True,
                                    )

                        # ── Speaker legend + hint ──────────────────────────────
                        _tl_speakers = sorted({c["speaker"] for c in _tl_claims if c.get("thread_id")})
                        _tl_spk_colors = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]
                        _tl_legend = " &nbsp; ".join(
                            f'<span style="background:{_tl_spk_colors[i % len(_tl_spk_colors)]};'
                            f'border-radius:50%;display:inline-block;width:11px;height:11px"></span> '
                            f'{speaker_names_an.get(s, s)}'
                            for i, s in enumerate(_tl_speakers)
                        )
                        _tl_leg_col, _tl_clear_col = st.columns([4, 1])
                        with _tl_leg_col:
                            st.markdown(
                                f"<small>{L('timeline_legend')} {_tl_legend}"
                                f"<br>{L('timeline_hint')}"
                                f"<br><span style='color:#aaa'>{L('timeline_restat_legend')}</span></small>",
                                unsafe_allow_html=True,
                            )
                        with _tl_clear_col:
                            if _sel_cid and st.button(L("timeline_clear_sel"), key="tl_clear"):
                                st.session_state.pop("tl_selected_claim", None)
                                st.rerun()

                        # ── Timeline visualization ─────────────────────────────
                        _tl_fc     = st.session_state.get("filtered_claims")
                        _tl_fc_all = analysis.get("claims", [])
                        _tl_hi     = (
                            {c["id"] for c in _tl_fc}
                            if _tl_fc is not None and len(_tl_fc) < len(_tl_fc_all)
                            else None
                        )
                        _tl_html = _build_thread_timeline(
                            _tl_claims,
                            _tl_threads,
                            speaker_names_an,
                            selected_claim_id=_sel_cid or None,
                            highlighted_ids=_tl_hi,
                        )
                        if _tl_html:
                            _tl_h = len(_tl_threads) * 33 + 82
                            components.html(_tl_html, height=_tl_h, scrolling=False)

                        # ── Selected claim detail ──────────────────────────────
                        if _sel_cid:
                            _sel_c = next(
                                (c for c in _tl_claims if c["id"] == _sel_cid), None
                            )
                            if _sel_c:
                                _sel_id    = _sel_c["id"]
                                _sel_spk   = speaker_names_an.get(_sel_c["speaker"], _sel_c["speaker"])
                                _sel_tid   = _sel_c.get("thread_id", "")
                                _sel_topic = next(
                                    (t.get("topic", _sel_tid) for t in _tl_threads
                                     if t["thread_id"] == _sel_tid), _sel_tid
                                )
                                _sel_ms    = _sel_c.get("start_ms", 0)

                                # Stage lookup — find the turn that contains this claim
                                _sel_stage = ""
                                _STAGE_KEY_MAP = {
                                    "confrontation": "stage_confrontation",
                                    "opening":       "stage_opening",
                                    "argumentation": "stage_argumentation",
                                    "concluding":    "stage_concluding",
                                }
                                for _st_turn in st.session_state.get("stages", []):
                                    if (_st_turn.get("speaker") == _sel_c["speaker"]
                                            and _st_turn.get("start_ms", 0) <= _sel_ms
                                            and _st_turn.get("end_ms", _sel_ms + 1) >= _sel_ms):
                                        _sel_stage = _st_turn.get("dialectical_stage", "")
                                        break
                                _sel_stage_lbl = (
                                    L(_STAGE_KEY_MAP[_sel_stage])
                                    if _sel_stage in _STAGE_KEY_MAP else ""
                                )

                                st.divider()
                                st.markdown(f"**{L('timeline_selected')}**")

                                with st.container(border=True):

                                    # 1. Full claim text + metadata line
                                    st.markdown(f"> {_sel_c['text']}")
                                    _meta_parts = [
                                        f"**{L('col_speaker')}:** {_sel_spk}",
                                        f"**{L('col_time')}:** {ms_to_ts(_sel_ms)}",
                                        f"**{L('timeline_thread')}:** {_sel_topic}",
                                    ]
                                    if _sel_stage_lbl:
                                        _meta_parts.append(f"**{L('card_stage')}:** {_sel_stage_lbl}")
                                    st.markdown(
                                        " &nbsp;·&nbsp; ".join(_meta_parts),
                                        unsafe_allow_html=True,
                                    )

                                    st.markdown("---")

                                    # 2. Type & status badges
                                    _sel_type      = _sel_c.get("claim_type", "")
                                    _sel_checkable = _sel_c.get("checkable", False)
                                    _sel_surv_ss   = st.session_state.get("survivability", {})
                                    _sel_surv_st   = _sel_surv_ss.get(_sel_id, "")
                                    _SURV_DOT = {
                                        "grounded":   '<span style="color:#2ca02c;font-weight:bold">●</span>',
                                        "contested":  '<span style="color:#ff7f0e;font-weight:bold">●</span>',
                                        "unattacked": '<span style="color:#aaaaaa">○</span>',
                                    }
                                    _SURV_LBL = {
                                        "grounded":   L("surv_grounded"),
                                        "contested":  L("surv_contested"),
                                        "unattacked": L("surv_unattacked"),
                                    }
                                    _type_badge  = (
                                        f'<span style="background:#f0f0f0;border-radius:4px;'
                                        f'padding:1px 8px;font-size:0.82em">{_sel_type}</span>'
                                    ) if _sel_type else ""
                                    _check_badge = (
                                        f'<span style="background:#e8f5e9;border-radius:4px;'
                                        f'padding:1px 8px;font-size:0.82em">{L("col_checkable")}</span>'
                                        if _sel_checkable else
                                        f'<span style="background:#f5f5f5;border-radius:4px;'
                                        f'padding:1px 8px;font-size:0.82em;color:#aaa">'
                                        f'not checkable</span>'
                                    )
                                    _surv_part = ""
                                    if _sel_surv_st:
                                        _surv_part = (
                                            f" &nbsp; {_SURV_DOT.get(_sel_surv_st, '')} "
                                            f"<small>{_SURV_LBL.get(_sel_surv_st, '')}</small>"
                                        )
                                    st.markdown(
                                        " &nbsp; ".join(b for b in [_type_badge, _check_badge] if b)
                                        + _surv_part,
                                        unsafe_allow_html=True,
                                    )

                                    # 3. Verdict section
                                    _verdicts_ss = st.session_state.get("verdicts", {})
                                    if _verdicts_ss and _sel_checkable:
                                        _vdict = _verdicts_ss.get(_sel_id)
                                        if _vdict:
                                            st.markdown("---")
                                            st.markdown(f"**{L('col_verdict')}**")
                                            _v_key = _vdict.get("verdict", "")
                                            _VSTYLE_CARD = {
                                                "true":           ("#d4edda", L("verdict_true")),
                                                "partially_true": ("#fff3cd", L("verdict_partly_true")),
                                                "contested":      ("#fde8c8", L("verdict_contested")),
                                                "misleading":     ("#fde8c8", L("verdict_misleading")),
                                                "false":          ("#f8d7da", L("verdict_false")),
                                                "unverifiable":   ("#e2e3e5", L("verdict_unverifiable")),
                                                "subjective":     ("#e2e3e5", L("verdict_subjective")),
                                            }
                                            _v_bg, _v_lbl = _VSTYLE_CARD.get(_v_key, ("#e2e3e5", _v_key))
                                            _v_conf = int(_vdict.get("confidence", 0.0) * 100)
                                            st.markdown(
                                                f'<span style="background:{_v_bg};border-radius:4px;'
                                                f'padding:2px 10px;font-size:0.88em">{_v_lbl}</span>'
                                                f' <small style="color:#888">{_v_conf}%</small>',
                                                unsafe_allow_html=True,
                                            )
                                            _v_expl = _vdict.get("explanation", "")
                                            if _v_expl:
                                                st.caption(_v_expl)
                                            if _v_key == "contested":
                                                if _vdict.get("for_the_claim"):
                                                    st.markdown(f"**{L('in_favour')}** {_vdict['for_the_claim']}")
                                                if _vdict.get("against_the_claim"):
                                                    st.markdown(f"**{L('against')}** {_vdict['against_the_claim']}")
                                            _ks = _vdict.get("key_source", "")
                                            if _ks:
                                                st.caption(f"**{L('sources')}:** {_ks}")

                                    # 4. Connections section
                                    _responses_ss = st.session_state.get("responses", [])
                                    if _responses_ss:
                                        st.markdown("---")
                                        _claim_lookup = {c["id"]: c for c in _tl_claims}
                                        _responds_to_ids = [
                                            r["responds_to_claim_id"] for r in _responses_ss
                                            if r.get("from_claim_id") == _sel_id
                                        ]
                                        _challenged_by_ids = [
                                            r["from_claim_id"] for r in _responses_ss
                                            if (r.get("responds_to_claim_id") == _sel_id
                                                and r.get("relationship") in
                                                ("refutes", "undercuts", "weakens"))
                                        ]
                                        _supported_by_ids = [
                                            r["from_claim_id"] for r in _responses_ss
                                            if (r.get("responds_to_claim_id") == _sel_id
                                                and r.get("relationship") in
                                                ("supports", "concedes"))
                                        ]
                                        st.markdown(
                                            f"**{L('card_connections')}** — "
                                            f"{L('card_responds_to')} **{len(_responds_to_ids)}** · "
                                            f"{L('card_challenged_by')} **{len(_challenged_by_ids)}** · "
                                            f"{L('card_supported_by')} **{len(_supported_by_ids)}**",
                                            unsafe_allow_html=True,
                                        )
                                        for _c_label, _c_ids in [
                                            (L("card_responds_to"),   _responds_to_ids),
                                            (L("card_challenged_by"), _challenged_by_ids),
                                            (L("card_supported_by"),  _supported_by_ids),
                                        ]:
                                            if _c_ids:
                                                _c_items = []
                                                for _cid2 in _c_ids:
                                                    _cc = _claim_lookup.get(_cid2)
                                                    if _cc:
                                                        _cc_spk = speaker_names_an.get(
                                                            _cc["speaker"], _cc["speaker"]
                                                        )
                                                        _cc_txt = (_cc["text"][:70]
                                                                   + ("…" if len(_cc["text"]) > 70 else ""))
                                                        _c_items.append(f"**{_cc_spk}:** {_cc_txt}")
                                                if _c_items:
                                                    st.markdown(
                                                        f"<small><em>{_c_label}:</em></small>",
                                                        unsafe_allow_html=True,
                                                    )
                                                    for _ci in _c_items:
                                                        st.markdown(f"- {_ci}")

                                    # 5. Rhetoric section
                                    _rhetoric_ss = st.session_state.get("rhetoric", [])
                                    if _rhetoric_ss:
                                        _rh_entry = next(
                                            (r for r in _rhetoric_ss
                                             if (r.get("speaker") == _sel_c["speaker"]
                                                 and r.get("start_ms", 0) <= _sel_ms
                                                 and r.get("end_ms", _sel_ms + 1) >= _sel_ms)),
                                            None,
                                        )
                                        if _rh_entry:
                                            _rh_falls   = _rh_entry.get("fallacies", [])
                                            _rh_devices = _rh_entry.get("rhetorical_devices", [])
                                            if _rh_falls or _rh_devices:
                                                st.markdown("---")
                                                st.markdown(f"**{L('card_rhetoric')}**")
                                                if _rh_falls:
                                                    st.markdown(f"*{L('rhetoric_fallacies')}*")
                                                    for _f in _rh_falls:
                                                        _f_lbl   = _f.get("label", _f.get("type", ""))
                                                        _f_quote = _f.get("quote", "")
                                                        _f_expl  = _f.get("explanation", "")
                                                        _f_line  = f"- **{_f_lbl}**"
                                                        if _f_quote:
                                                            _f_line += f' — "{_f_quote}"'
                                                        if _f_expl:
                                                            _f_line += f": {_f_expl}"
                                                        st.markdown(_f_line)
                                                if _rh_devices:
                                                    st.markdown(f"*{L('rhetoric_devices')}*")
                                                    for _d in _rh_devices:
                                                        _d_lbl   = _d.get("label", _d.get("type", ""))
                                                        _d_quote = _d.get("quote", "")
                                                        _d_line  = f"- **{_d_lbl}**"
                                                        if _d_quote:
                                                            _d_line += f' — "{_d_quote}"'
                                                        st.markdown(_d_line)

                                    # 5.5 Mini neighbourhood map
                                    if _responses_ss:
                                        st.markdown("---")
                                        _mm_key  = f"minimap_open_{_sel_id}"
                                        _mm_open = st.session_state.get(_mm_key, False)

                                        # Collect all claim IDs directly connected to sel_id
                                        _nb_ids: set[str] = set()
                                        for _r in _responses_ss:
                                            if _r.get("from_claim_id") == _sel_id:
                                                _nb_ids.add(_r["responds_to_claim_id"])
                                            if _r.get("responds_to_claim_id") == _sel_id:
                                                _nb_ids.add(_r["from_claim_id"])

                                        if not _nb_ids:
                                            st.caption(L("card_no_connections"))
                                        else:
                                            _mm_btn_lbl = (
                                                L("card_hide_minimap")
                                                if _mm_open else
                                                L("card_show_minimap")
                                            )
                                            if st.button(_mm_btn_lbl, key=f"mm_btn_{_sel_id}"):
                                                st.session_state[_mm_key] = not _mm_open
                                                st.rerun()
                                            if _mm_open:
                                                _mm_ids    = {_sel_id} | _nb_ids
                                                _mm_claims = [
                                                    c for c in _tl_claims
                                                    if c["id"] in _mm_ids
                                                ]
                                                _mm_resp   = [
                                                    r for r in _responses_ss
                                                    if (r.get("from_claim_id") in _mm_ids
                                                        and r.get("responds_to_claim_id") in _mm_ids)
                                                ]
                                                _mm_html = build_graph_html(
                                                    _mm_claims,
                                                    _mm_resp,
                                                    speaker_names_an,
                                                    survivability=st.session_state.get("survivability"),
                                                    verdicts=st.session_state.get("verdicts"),
                                                )
                                                if _mm_html:
                                                    components.html(
                                                        _mm_html, height=320, scrolling=False
                                                    )

                                    # 6. Thread context expander
                                    _co_claims = [
                                        c for c in _tl_claims
                                        if c.get("thread_id") == _sel_tid and c["id"] != _sel_cid
                                    ]
                                    if _co_claims:
                                        _co_sorted = sorted(
                                            _co_claims, key=lambda c: c.get("start_ms", 0)
                                        )
                                        _rows = []
                                        for _co in _co_sorted:
                                            _co_spk = speaker_names_an.get(
                                                _co["speaker"], _co["speaker"]
                                            )
                                            _co_ts = ms_to_ts(_co.get("start_ms", 0))
                                            _rows.append(
                                                f"[{_co_ts}] **{_co_spk}** — {_co['text'][:90]}"
                                                + ("…" if len(_co["text"]) > 90 else "")
                                            )
                                        with st.expander(
                                            f"Other claims in this thread ({len(_co_claims)})"
                                        ):
                                            for _row in _rows:
                                                st.markdown(f"- {_row}")

                # ── Fact-Check sub-tab ────────────────────────────────────────
                with subtab_fc:
                    _fc_verdicts = st.session_state.get("verdicts", {})
                    if not _fc_verdicts:
                        st.info(L("fc_run_first"))
                    else:
                        _fc_all_claims = analysis.get("claims", [])
                        # Claims that have a verdict
                        _fc_checked = [c for c in _fc_all_claims if c["id"] in _fc_verdicts]

                        _FC_VSTYLE = {
                            "true":           ("#d4edda", L("verdict_true")),
                            "partially_true": ("#fff3cd", L("verdict_partly_true")),
                            "contested":      ("#fde8c8", L("verdict_contested")),
                            "misleading":     ("#fde8c8", L("verdict_misleading")),
                            "false":          ("#f8d7da", L("verdict_false")),
                            "unverifiable":   ("#e2e3e5", L("verdict_unverifiable")),
                            "subjective":     ("#e2e3e5", L("verdict_subjective")),
                        }
                        _VERDICT_SEV = {
                            "false": 0, "misleading": 1, "contested": 2,
                            "partially_true": 3, "true": 4,
                            "unverifiable": 5, "subjective": 5,
                        }
                        _fc_checked_sorted = sorted(
                            _fc_checked,
                            key=lambda c: _VERDICT_SEV.get(
                                _fc_verdicts[c["id"]].get("verdict", ""), 5
                            ),
                        )

                        # ── Summary metrics ─────────────────────────────────────
                        _vc: dict[str, int] = {}
                        for _c in _fc_checked:
                            _v = _fc_verdicts[_c["id"]].get("verdict", "")
                            _vc[_v] = _vc.get(_v, 0) + 1

                        _n_supported = _vc.get("true", 0) + _vc.get("partially_true", 0)
                        _n_challenged = (_vc.get("false", 0) + _vc.get("misleading", 0)
                                         + _vc.get("contested", 0))
                        _n_beyond = _vc.get("unverifiable", 0) + _vc.get("subjective", 0)

                        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                        _mc1.metric(L("fc_checked"),   len(_fc_checked))
                        _mc2.metric(L("fc_supported"),  _n_supported)
                        _mc3.metric(L("fc_challenged"), _n_challenged)
                        _mc4.metric(L("fc_beyond"),     _n_beyond)

                        _fc_legend_html = " &nbsp;|&nbsp; ".join(
                            f'<span style="background:{bg};border-radius:4px;padding:1px 7px;font-size:0.82em">{lbl}</span>'
                            for bg, lbl in [
                                ("#d4edda", L("verdict_true")),
                                ("#fff3cd", L("verdict_partly_true")),
                                ("#fde8c8", L("verdict_contested")),
                                ("#f8d7da", L("verdict_false")),
                                ("#e2e3e5", L("verdict_unverifiable")),
                            ]
                        )
                        st.markdown(
                            f'<div style="margin-bottom:4px"><small><strong>{L("verdict_legend_label")}</strong> '
                            f'{_fc_legend_html}</small></div>',
                            unsafe_allow_html=True,
                        )
                        st.caption(L("fc_disclaimer"))
                        st.divider()

                        # ── Overview table ──────────────────────────────────────
                        _th = "padding:6px 8px;text-align:left;border-bottom:2px solid #dee2e6;font-size:0.85em"
                        _td = "padding:5px 8px;border-bottom:1px solid #f0f0f0;font-size:0.82em;vertical-align:top"
                        _conf_hdr = (
                            f'<abbr title="{L("fc_conf_help")}" '
                            f'style="cursor:help;text-decoration:underline dotted #888">Conf.</abbr>'
                        )
                        _fc_hdrs = [
                            L("col_speaker"), L("fc_thread_col"), L("col_claim"),
                            L("col_verdict"), _conf_hdr, L("fc_kb_col"), L("fc_sources_col"),
                        ]
                        _fc_hdr_html = "".join(f"<th style='{_th}'>{h}</th>" for h in _fc_hdrs)
                        _fc_rows = ""
                        for _c in _fc_checked_sorted:
                            _vd      = _fc_verdicts[_c["id"]]
                            _vkey    = _vd.get("verdict", "")
                            _bg, _lbl = _FC_VSTYLE.get(_vkey, ("#e2e3e5", "—"))
                            _conf    = int(_vd.get("confidence", 0) * 100)
                            _kb      = _vd.get("knowledge_based", False)
                            _n_src   = len(_vd.get("all_sources") or [])
                            _spknm   = speaker_names_an.get(_c["speaker"], _c["speaker"])
                            _thread  = _c.get("thread_topic", _c.get("thread_id", "—"))
                            _thread_s = (_thread[:35] + "…") if len(_thread) > 35 else _thread
                            _short   = (_c["text"][:90] + "…") if len(_c["text"]) > 90 else _c["text"]
                            _vbadge  = (
                                f'<span style="background:{_bg};border-radius:4px;'
                                f'padding:2px 6px;font-size:0.8em;white-space:nowrap">{_lbl}</span>'
                            )
                            _kb_cell = "🧠" if _kb else ("📚" if _n_src > 0 else "—")
                            _src_cell = str(_n_src) if _n_src > 0 else "—"
                            _fc_rows += (
                                f"<tr>"
                                f"<td style='{_td}'>{_spknm}</td>"
                                f"<td style='{_td};color:#888'>{_thread_s}</td>"
                                f"<td style='{_td}'>{_short}</td>"
                                f"<td style='{_td}'>{_vbadge}</td>"
                                f"<td style='{_td}'>{_conf}%</td>"
                                f"<td style='{_td};text-align:center'>{_kb_cell}</td>"
                                f"<td style='{_td};text-align:center'>{_src_cell}</td>"
                                f"</tr>"
                            )
                        st.markdown(
                            f"<div style='overflow-x:auto'>"
                            f"<table style='width:100%;border-collapse:collapse'>"
                            f"<thead><tr>{_fc_hdr_html}</tr></thead>"
                            f"<tbody>{_fc_rows}</tbody></table></div>",
                            unsafe_allow_html=True,
                        )

                        st.divider()

                        # ── Per-claim detail expanders ──────────────────────────
                        for _c in _fc_checked_sorted:
                            _vd     = _fc_verdicts[_c["id"]]
                            _vkey   = _vd.get("verdict", "")
                            _bg, _lbl = _FC_VSTYLE.get(_vkey, ("#e2e3e5", "—"))
                            _conf   = int(_vd.get("confidence", 0) * 100)
                            _kb     = _vd.get("knowledge_based", False)
                            _spknm  = speaker_names_an.get(_c["speaker"], _c["speaker"])
                            _short  = (_c["text"][:55] + "…") if len(_c["text"]) > 55 else _c["text"]
                            with st.expander(f"[{ms_to_ts(_c.get('start_ms', 0))}] {_spknm} — {_short}"):
                                st.markdown(f"**{_c['text']}**")
                                # Knowledge-basis indicator
                                if _kb:
                                    st.caption("🧠 Assessed using Claude's training knowledge — no retrieved source")
                                else:
                                    st.caption("📚 Assessed using retrieved external sources")
                                st.markdown("---")
                                # Verdict badge + confidence
                                st.markdown(
                                    f'<span style="background:{_bg};border-radius:4px;'
                                    f'padding:3px 10px;font-size:0.88em">{_lbl}</span>',
                                    unsafe_allow_html=True,
                                )
                                st.progress(_conf, text=f"Confidence: {_conf}%")
                                st.markdown(_vd.get("explanation", ""))
                                # For / against (contested)
                                if _vkey == "contested":
                                    if _vd.get("for_the_claim"):
                                        st.markdown(f"**{L('in_favour')}** {_vd['for_the_claim']}")
                                    if _vd.get("against_the_claim"):
                                        st.markdown(f"**{L('against')}** {_vd['against_the_claim']}")
                                # Key source — always shown when present
                                _ks = _vd.get("key_source", "")
                                if _ks:
                                    st.caption(f"**Key source:** {_ks}")
                                # Retrieved sources
                                _srcs = _vd.get("all_sources") or []
                                if _srcs:
                                    st.markdown(f"**{L('sources')}**")
                                    for _s in _srcs:
                                        _st = _s.get("title", "Source") if isinstance(_s, dict) else str(_s)
                                        _su = (_s.get("url", "") or "") if isinstance(_s, dict) else ""
                                        st.markdown(f"- [{_st}]({_su})" if _su else f"- {_st}")

                # ── Argument Map sub-tab ───────────────────────────────────────
                with subtab_map:
                    responses = st.session_state.get("responses")
                    if not responses:
                        st.info(L("run_detect_first"))
                    else:
                        with st.expander(L("map_how_to_expander"), expanded=True):
                            st.markdown(L("map_how_to_nodes"))
                            st.markdown(L("map_how_to_arrows"))
                            st.markdown(L("map_how_to_labels"))
                            st.markdown(L("map_how_to_patterns"))
                        # Graph layer toggles (two columns — premises on by default)
                        _tgl1, _tgl2 = st.columns(2)
                        with _tgl1:
                            show_premises_cb = st.checkbox(L("show_premises"), value=True)
                        with _tgl2:
                            show_rt_cb = st.checkbox(L("show_reasoning_targets"), value=False)

                        _fc_all  = analysis.get("claims", [])
                        _fc_filt = st.session_state.get("filtered_claims")
                        _fc_use  = _fc_filt if _fc_filt is not None else _fc_all
                        _hi_ids  = (
                            {c["id"] for c in _fc_use}
                            if _fc_filt is not None and len(_fc_filt) < len(_fc_all)
                            else None
                        )

                        graph_html = build_graph_html(
                            _fc_all,
                            responses,
                            speaker_names_an,
                            survivability=st.session_state.get("survivability"),
                            show_premises=show_premises_cb,
                            show_reasoning_targets=show_rt_cb,
                            verdicts=st.session_state.get("verdicts"),
                            highlighted_ids=_hi_ids,
                        )
                        if graph_html:
                            if _hi_ids is not None:
                                st.caption(
                                    LABELS["graph_filter_caption"][lang].format(
                                        n=len(_fc_use), m=len(_fc_all)
                                    )
                                )
                            components.html(graph_html, height=620, scrolling=False)
                            st.download_button(
                                label     = "⬇  Download argument map (.html)",
                                data      = graph_html.encode("utf-8"),
                                file_name = f"argument_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                                mime      = "text/html",
                            )
                        else:
                            st.info(L("analysis_no_claims"))

                        # ── Legend ─────────────────────────────────────────────
                        _map_help_col, _ = st.columns([3, 7])
                        with _map_help_col:
                            if st.button(f"→ {L('help_link_responses')}", key="help_responses_map"):
                                help_dialogs.responses_dialog(lang)
                        st.markdown(f"#### {L('legend_heading')}")
                        _SPEAKER_COLORS_VIS = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
                        spk_sorted = sorted({c["speaker"] for c in analysis.get("claims", [])})
                        spk_legend = " &nbsp; ".join(
                            f'<span style="background:{_SPEAKER_COLORS_VIS[i % 5]};'
                            f'border-radius:50%;display:inline-block;width:12px;height:12px"></span> '
                            f'{speaker_names_an.get(s, s)}'
                            for i, s in enumerate(spk_sorted)
                        )
                        # Claim shapes: circles for factual, diamonds for causal, etc.
                        shape_legend = (
                            "⬤ factual / statistical / comparative &nbsp;&nbsp;"
                            "◆ causal / predictive &nbsp;&nbsp;"
                            "■ definitional / interpretive &nbsp;&nbsp;"
                            "▲ moral / anecdotal"
                        )
                        # Solid-line response edges
                        edge_legend = (
                            f'<span style="color:#d62728">━</span> <strong>refutes</strong>'
                            f' <small style="color:#888">— {L("legend_refutes")}</small> &nbsp;&nbsp;'
                            f'<span style="color:#e377c2">━</span> <strong>undercuts</strong>'
                            f' <small style="color:#888">— {L("legend_undercuts")}</small> &nbsp;&nbsp;'
                            f'<span style="color:#2ca02c">━</span> <strong>supports</strong>'
                            f' <small style="color:#888">— {L("legend_supports")}</small> &nbsp;&nbsp;'
                            f'<span style="color:#ff7f0e">━</span> <strong>weakens / concedes</strong>'
                            f' <small style="color:#888">— {L("legend_weakens")}</small> &nbsp;&nbsp;'
                            f'<span style="color:#9467bd">━</span> <strong>reframes</strong>'
                            f' <small style="color:#888">— {L("legend_reframes")}</small> &nbsp;&nbsp;'
                            f'<span style="color:#aaaaaa">━</span> <strong>evades / ignores</strong>'
                            f' <small style="color:#888">— {L("legend_evades")}</small>'
                        )
                        surv_ss = st.session_state.get("survivability", {})
                        surv_legend = (
                            '<span style="color:#2ca02c;font-weight:bold">━━</span> '
                            + L("surv_grounded") + ' &nbsp;&nbsp;'
                            '<span style="color:#ff7f0e;font-weight:bold">━━</span> '
                            + L("surv_contested") + ' &nbsp;&nbsp;'
                            '<span style="color:#aaaaaa">━━</span> '
                            + L("surv_unattacked")
                        )
                        # Conditional: premise layer
                        _prem_legend = (
                            f"<br>**{L('show_premises')}:** "
                            f'<span style="background:#cccccc;border-radius:2px;'
                            f'padding:1px 6px;font-size:0.85em">□</span> '
                            f"{L('legend_premise')} &nbsp; "
                            f'<span style="color:#aaaaaa;font-size:0.9em">- - ▶</span> '
                            f"{L('legend_dashed')}"
                            if show_premises_cb else ""
                        )
                        # Conditional: reasoning-target layer
                        _rt_legend = (
                            f"<br>**{L('show_reasoning_targets')}:** "
                            f'<span style="color:#e377c2">◆</span> '
                            f"{L('legend_inference_pt')}"
                            if show_rt_cb else ""
                        )
                        st.markdown(
                            f"**{L('legend_node_color')}:** {spk_legend}<br>"
                            f"**{L('legend_node_shape')} (claims):** {shape_legend}<br>"
                            f"**{L('legend_edge_color')}:** {edge_legend}<br>"
                            f"**{L('surv_heading')} (border):** {surv_legend}"
                            + _prem_legend + _rt_legend,
                            unsafe_allow_html=True,
                        )
                        # ── Survivability summary sentence ──────────────────────
                        if surv_ss:
                            _sg = sum(1 for s in surv_ss.values() if s == "grounded")
                            _sc = sum(1 for s in surv_ss.values() if s == "contested")
                            _su = sum(1 for s in surv_ss.values() if s == "unattacked")
                            st.markdown(LABELS["surv_map_summary"][lang].format(g=_sg, c=_sc, u=_su))

                # ── Rhetorical Profile sub-tab ─────────────────────────────────
                with subtab_rhetoric:
                    _stages  = st.session_state.get("stages")
                    rhetoric = st.session_state.get("rhetoric")
                    if not rhetoric and not _stages:
                        st.info(L("rhetoric_run_first"))
                    else:
                        st.info(L("rhetoric_intro"))
                        _rh_help_col, _ = st.columns([3, 7])
                        with _rh_help_col:
                            if st.button(f"→ {L('help_link_rhetoric')}", key="help_rhetoric_tab"):
                                help_dialogs.rhetoric_dialog(lang)
                        # ── Stage timeline ─────────────────────────────────────
                        if _stages:
                            st.subheader(L("stage_timeline"))
                            _STAGE_COLORS = {
                                "confrontation": "#d62728",
                                "opening":       "#1f77b4",
                                "argumentation": "#2ca02c",
                                "concluding":    "#9467bd",
                            }
                            _STAGE_LABEL_KEY = {
                                "confrontation": "stage_confrontation",
                                "opening":       "stage_opening",
                                "argumentation": "stage_argumentation",
                                "concluding":    "stage_concluding",
                            }
                            # Vertical stacked bar chart — stage color, speaker texture
                            _stage_counts: dict[str, int] = {}
                            _stage_color_map: dict[str, str] = {}
                            _stage_spk_counts: dict[str, dict[str, int]] = {}
                            for _si in _stages:
                                _stg = _si.get("dialectical_stage", "argumentation")
                                _lbl = L(_STAGE_LABEL_KEY.get(_stg, "stage_argumentation"))
                                _spk = _si.get("speaker", "")
                                _stage_counts[_lbl] = _stage_counts.get(_lbl, 0) + 1
                                _stage_color_map[_lbl] = _STAGE_COLORS.get(_stg, "#cccccc")
                                _stage_spk_counts.setdefault(_lbl, {})
                                _stage_spk_counts[_lbl][_spk] = (
                                    _stage_spk_counts[_lbl].get(_spk, 0) + 1
                                )
                            if _stage_counts:
                                _sc_speakers = sorted(speaker_names_an.keys())
                                # CSS texture overlays: same stage color, pattern varies by speaker
                                _SPK_TEXTURES = [
                                    "",  # solid
                                    "background-image:repeating-linear-gradient("
                                    "45deg,rgba(255,255,255,0.45) 0,rgba(255,255,255,0.45) 3px,"
                                    "transparent 3px,transparent 9px);",
                                    "background-image:repeating-linear-gradient("
                                    "0deg,rgba(255,255,255,0.45) 0,rgba(255,255,255,0.45) 3px,"
                                    "transparent 3px,transparent 9px);",
                                    "background-image:radial-gradient("
                                    "circle,rgba(255,255,255,0.6) 2px,transparent 2px);"
                                    "background-size:9px 9px;",
                                    "background-image:repeating-linear-gradient("
                                    "-45deg,rgba(255,255,255,0.45) 0,rgba(255,255,255,0.45) 3px,"
                                    "transparent 3px,transparent 9px);",
                                    "background-image:repeating-linear-gradient("
                                    "90deg,rgba(255,255,255,0.45) 0,rgba(255,255,255,0.45) 3px,"
                                    "transparent 3px,transparent 9px);",
                                ]
                                _spk_tex = {
                                    _s: _SPK_TEXTURES[i % len(_SPK_TEXTURES)]
                                    for i, _s in enumerate(_sc_speakers)
                                }
                                _MAX_BAR_H = 160
                                _max_sc = max(_stage_counts.values()) or 1
                                _sorted_stages = sorted(
                                    _stage_counts.items(), key=lambda x: -x[1]
                                )
                                # Row 1: count labels above bars
                                _r1 = '<div style="display:flex;gap:12px;margin:12px 0 2px 0">'
                                for _lbl, _tot in _sorted_stages:
                                    _r1 += (
                                        f'<div style="flex:1;text-align:center;'
                                        f'font-size:0.8em;color:#888">{_tot}</div>'
                                    )
                                _r1 += '</div>'
                                # Row 2: the bars
                                _r2 = (
                                    '<div style="display:flex;align-items:flex-end;gap:12px;'
                                    f'height:{_MAX_BAR_H}px;'
                                    'border-bottom:1px solid rgba(128,128,128,0.2)">'
                                )
                                for _lbl, _tot in _sorted_stages:
                                    _col = _stage_color_map.get(_lbl, "#cccccc")
                                    _bh  = max(4, int(_tot / _max_sc * _MAX_BAR_H))
                                    _spk_data = _stage_spk_counts.get(_lbl, {})
                                    _segs = ""
                                    for _s in _sc_speakers:
                                        _sc_cnt = _spk_data.get(_s, 0)
                                        if _sc_cnt > 0:
                                            _tex = _spk_tex.get(_s, "")
                                            _sn  = speaker_names_an.get(_s, _s)
                                            _segs += (
                                                f'<div title="{_sn}: {_sc_cnt}" '
                                                f'style="flex:{_sc_cnt};background-color:{_col};'
                                                f'{_tex}"></div>'
                                            )
                                    _r2 += (
                                        f'<div style="flex:1;height:{_bh}px;display:flex;'
                                        f'flex-direction:column;border-radius:4px 4px 0 0;'
                                        f'overflow:hidden">{_segs}</div>'
                                    )
                                _r2 += '</div>'
                                # Row 3: stage labels below bars
                                _r3 = '<div style="display:flex;gap:12px;margin:5px 0 10px 0">'
                                for _lbl, _tot in _sorted_stages:
                                    _col = _stage_color_map.get(_lbl, "#cccccc")
                                    _r3 += (
                                        f'<div style="flex:1;text-align:center;'
                                        f'font-size:0.8em;color:#555">'
                                        f'<span style="display:inline-block;width:9px;height:9px;'
                                        f'border-radius:2px;background:{_col};margin-right:4px;'
                                        f'vertical-align:middle"></span>{_lbl}</div>'
                                    )
                                _r3 += '</div>'
                                # Row 4: speaker texture legend
                                _r4 = (
                                    '<div style="display:flex;gap:16px;flex-wrap:wrap;'
                                    'font-size:0.82em;color:#555;margin-bottom:12px">'
                                )
                                for _s in _sc_speakers:
                                    _tex = _spk_tex.get(_s, "")
                                    _sn  = speaker_names_an.get(_s, _s)
                                    _r4 += (
                                        f'<div style="display:flex;align-items:center;gap:6px">'
                                        f'<div style="width:24px;height:14px;background-color:#666;'
                                        f'{_tex};border-radius:2px"></div>'
                                        f'<span>{_sn}</span></div>'
                                    )
                                _r4 += '</div>'
                                st.markdown(
                                    _r1 + _r2 + _r3 + _r4, unsafe_allow_html=True
                                )
                            # Build rhetoric lookup: turn start_ms → rhetoric data
                            _rhetoric_by_ms: dict[int, dict] = {}
                            _rhet_ss = st.session_state.get("rhetoric")
                            if _rhet_ss:
                                for _ritem in _rhet_ss:
                                    _rhetoric_by_ms[_ritem.get("start_ms", -1)] = _ritem

                            # Build turn-text lookup: turn start_ms → full turn text
                            _turn_text_map: dict[int, str] = {}
                            _prev_u_spk: str | None = None
                            _cur_turn_ms = 0
                            _cur_turn_txts: list[str] = []
                            for _u in utterances_an:
                                _u_spk = _u.get("speaker", "")
                                _u_ms  = _u.get("start_ms", 0)
                                _u_txt = _u.get("text", "")
                                if _u_spk != _prev_u_spk:
                                    if _prev_u_spk is not None:
                                        _turn_text_map[_cur_turn_ms] = " ".join(_cur_turn_txts)
                                    _prev_u_spk  = _u_spk
                                    _cur_turn_ms = _u_ms
                                    _cur_turn_txts = [_u_txt]
                                else:
                                    _cur_turn_txts.append(_u_txt)
                            if _prev_u_spk is not None:
                                _turn_text_map[_cur_turn_ms] = " ".join(_cur_turn_txts)

                            # Clickable chips — stage color, speaker label, turn text on expand
                            _boxes = []
                            for _si in sorted(_stages, key=lambda x: x.get("turn_index", 0)):
                                _stg   = _si.get("dialectical_stage", "argumentation")
                                _color = _STAGE_COLORS.get(_stg, "#cccccc")
                                _ts    = ms_to_ts(_si.get("start_ms", 0))
                                _spknm = speaker_names_an.get(_si["speaker"], _si["speaker"])
                                _raw   = _turn_text_map.get(_si.get("start_ms", 0), "")
                                _excerpt = (_raw[:220] + "…") if len(_raw) > 220 else _raw
                                # Rhetoric annotation for this turn
                                _rhet_item = _rhetoric_by_ms.get(_si.get("start_ms", 0), {})
                                _rhet_lines = ""
                                for _rf2 in _rhet_item.get("fallacies", []):
                                    _rl = _rf2.get("label") or _rf2.get("type", "")
                                    _rq = _rf2.get("quote", "")
                                    _rq_s = (_rq[:60] + "…") if len(_rq) > 60 else _rq
                                    if _rl:
                                        _rhet_lines += (
                                            f'<div style="margin-top:3px;opacity:0.92">'
                                            f'⚠ <strong>{_rl}</strong>'
                                            + (f' — <em>"{_rq_s}"</em>' if _rq_s else "")
                                            + '</div>'
                                        )
                                for _rd2 in _rhet_item.get("rhetorical_devices", []):
                                    if _rd2.get("is_fallacy", False):
                                        continue
                                    _rl = _rd2.get("label") or _rd2.get("type", "")
                                    _rq = _rd2.get("quote", "")
                                    _rq_s = (_rq[:60] + "…") if len(_rq) > 60 else _rq
                                    if _rl:
                                        _rhet_lines += (
                                            f'<div style="margin-top:3px;opacity:0.85">'
                                            f'✦ <strong>{_rl}</strong>'
                                            + (f' — <em>"{_rq_s}"</em>' if _rq_s else "")
                                            + '</div>'
                                        )
                                _sep = (
                                    '<hr style="border:none;border-top:1px solid '
                                    'rgba(255,255,255,0.3);margin:5px 0">'
                                    '<div style="font-size:0.72em;opacity:0.65;margin-bottom:3px">'
                                    '⚠ fallacy &nbsp;·&nbsp; ✦ rhetorical device'
                                    '</div>'
                                    if _rhet_lines else ""
                                )
                                _boxes.append(
                                    f'<details style="display:inline-block;'
                                    f'vertical-align:top;margin:2px">'
                                    f'<summary style="background:{_color};color:#fff;'
                                    f'border-radius:3px;padding:2px 7px;font-size:0.75em;'
                                    f'white-space:nowrap;cursor:pointer;list-style:none;'
                                    f'display:inline-block">[{_ts}] {_spknm}</summary>'
                                    f'<div style="background:{_color};color:#fff;'
                                    f'border-radius:0 0 4px 4px;padding:6px 9px;'
                                    f'font-size:0.8em;line-height:1.45;max-width:300px;'
                                    f'white-space:normal;'
                                    f'box-shadow:0 3px 10px rgba(0,0,0,0.25)">'
                                    f'{_excerpt}{_sep}{_rhet_lines}</div>'
                                    f'</details>'
                                )
                            st.markdown(
                                '<div style="display:flex;flex-wrap:wrap;gap:2px;margin:8px 0">'
                                + "".join(_boxes) + "</div>",
                                unsafe_allow_html=True,
                            )
                            st.divider()

                        # ── Per-speaker rhetoric ───────────────────────────────
                        if rhetoric:
                            # Group findings by speaker
                            spk_rhetoric: dict[str, list[dict]] = defaultdict(list)
                            for item in rhetoric:
                                spk_rhetoric[item["speaker"]].append(item)

                            # ── Rhetorical profile overview chart ──────────────
                            st.subheader(L("rhetoric_profile_chart"))
                            _rh_spk_ids = sorted(spk_rhetoric.keys())
                            _rh_totals = {}
                            for _rsid in _rh_spk_ids:
                                _rturns = spk_rhetoric[_rsid]
                                _rh_totals[_rsid] = {
                                    "f": sum(len(t.get("fallacies", [])) for t in _rturns),
                                    "d": sum(
                                        len([d for d in t.get("rhetorical_devices", [])
                                             if not d.get("is_fallacy", False)])
                                        for t in _rturns
                                    ),
                                }
                            _rh_max = max(
                                max(v["f"], v["d"]) for v in _rh_totals.values()
                            ) if _rh_totals else 1
                            _RH_MAX_H = 140  # px

                            # Count labels above bars
                            _rh_r1 = '<div style="display:flex;gap:20px;margin:12px 0 2px 0">'
                            for _rsid in _rh_spk_ids:
                                _fv = _rh_totals[_rsid]["f"]
                                _dv = _rh_totals[_rsid]["d"]
                                _rh_r1 += (
                                    f'<div style="flex:1;display:flex;gap:4px">'
                                    f'<div style="flex:1;text-align:center;font-size:0.8em;color:#888">'
                                    f'{_fv}</div>'
                                    f'<div style="flex:1;text-align:center;font-size:0.8em;color:#888">'
                                    f'{_dv}</div>'
                                    f'</div>'
                                )
                            _rh_r1 += '</div>'

                            # Bars
                            _rh_r2 = (
                                '<div style="display:flex;gap:20px;align-items:flex-end;'
                                f'height:{_RH_MAX_H}px;'
                                'border-bottom:1px solid rgba(128,128,128,0.2)">'
                            )
                            for _rsid in _rh_spk_ids:
                                _fv = _rh_totals[_rsid]["f"]
                                _dv = _rh_totals[_rsid]["d"]
                                _fh = max(4, int(_fv / _rh_max * _RH_MAX_H)) if _fv else 0
                                _dh = max(4, int(_dv / _rh_max * _RH_MAX_H)) if _dv else 0
                                _spkn = speaker_names_an.get(_rsid, _rsid)
                                _rh_r2 += (
                                    f'<div style="flex:1;display:flex;gap:4px;align-items:flex-end">'
                                    f'<div title="{_spkn}: {_fv} {L("rhetoric_fallacies").lower()}" '
                                    f'style="flex:1;height:{_fh}px;background:#d62728;'
                                    f'border-radius:4px 4px 0 0"></div>'
                                    f'<div title="{_spkn}: {_dv} {L("rhetoric_devices").lower()}" '
                                    f'style="flex:1;height:{_dh}px;background:#1f77b4;'
                                    f'border-radius:4px 4px 0 0"></div>'
                                    f'</div>'
                                )
                            _rh_r2 += '</div>'

                            # Speaker labels
                            _rh_r3 = '<div style="display:flex;gap:20px;margin:4px 0 2px 0">'
                            for _rsid in _rh_spk_ids:
                                _spkn = speaker_names_an.get(_rsid, _rsid)
                                _rh_r3 += (
                                    f'<div style="flex:1;text-align:center;font-size:0.85em;'
                                    f'font-weight:600;color:#555">{_spkn}</div>'
                                )
                            _rh_r3 += '</div>'

                            # Legend
                            _rh_r4 = (
                                '<div style="display:flex;gap:16px;font-size:0.8em;'
                                'color:#555;margin:6px 0 14px 0">'
                                f'<span><span style="display:inline-block;width:12px;height:12px;'
                                f'background:#d62728;border-radius:2px;vertical-align:middle;'
                                f'margin-right:5px"></span>{L("rhetoric_fallacies")}</span>'
                                f'<span><span style="display:inline-block;width:12px;height:12px;'
                                f'background:#1f77b4;border-radius:2px;vertical-align:middle;'
                                f'margin-right:5px"></span>{L("rhetoric_devices")}</span>'
                                '</div>'
                            )

                            st.markdown(
                                _rh_r1 + _rh_r2 + _rh_r3 + _rh_r4,
                                unsafe_allow_html=True,
                            )
                            st.divider()

                            # ── Type breakdown expander ────────────────────────
                            with st.expander(L("rh_breakdown_expander"), expanded=False):
                                # Build type × speaker count tables
                                _rh_f_types: dict[str, dict[str, int]] = {}
                                _rh_d_types: dict[str, dict[str, int]] = {}
                                for _rsid, _rturns in spk_rhetoric.items():
                                    for _rt in _rturns:
                                        for _rf in _rt.get("fallacies", []):
                                            _rlbl = _rf.get("label") or _rf.get("type", "")
                                            if _rlbl:
                                                _rh_f_types.setdefault(_rlbl, {})
                                                _rh_f_types[_rlbl][_rsid] = (
                                                    _rh_f_types[_rlbl].get(_rsid, 0) + 1
                                                )
                                        for _rd in _rt.get("rhetorical_devices", []):
                                            if _rd.get("is_fallacy", False):
                                                continue
                                            _rlbl = _rd.get("label") or _rd.get("type", "")
                                            if _rlbl:
                                                _rh_d_types.setdefault(_rlbl, {})
                                                _rh_d_types[_rlbl][_rsid] = (
                                                    _rh_d_types[_rlbl].get(_rsid, 0) + 1
                                                )

                                def _rh_type_chart(
                                    type_counts: dict[str, dict[str, int]],
                                    spk_ids: list[str],
                                    heading: str,
                                ) -> None:
                                    if not type_counts:
                                        return
                                    # Group singletons into "Other"
                                    _other: dict[str, int] = {}
                                    _keep: dict[str, dict[str, int]] = {}
                                    for _tl, _sc in type_counts.items():
                                        if sum(_sc.values()) <= 1:
                                            for _sid2, _cnt2 in _sc.items():
                                                _other[_sid2] = _other.get(_sid2, 0) + _cnt2
                                        else:
                                            _keep[_tl] = _sc
                                    if _other:
                                        _keep[L("rh_other")] = _other
                                    # Sort by total count desc
                                    _sorted_types = sorted(
                                        _keep.items(),
                                        key=lambda x: -sum(x[1].values()),
                                    )
                                    _max_type = max(
                                        sum(sc.values()) for _, sc in _sorted_types
                                    ) or 1
                                    _spk_cols = [SPEAKER_COLORS[i % len(SPEAKER_COLORS)]
                                                 for i, _ in enumerate(spk_ids)]
                                    st.markdown(f"**{heading}**")
                                    _th_html = (
                                        '<div style="display:flex;flex-direction:column;'
                                        'gap:6px;margin:6px 0 14px 0">'
                                    )
                                    for _tl, _sc in _sorted_types:
                                        _total = sum(_sc.values())
                                        _segs = ""
                                        for _i2, _sid2 in enumerate(spk_ids):
                                            _cnt2 = _sc.get(_sid2, 0)
                                            if _cnt2 > 0:
                                                _sw = _cnt2 / _max_type * 100
                                                _sc2 = _spk_cols[_i2]
                                                _sn2 = speaker_names_an.get(_sid2, _sid2)
                                                _segs += (
                                                    f'<div title="{_sn2}: {_cnt2}" '
                                                    f'style="width:{_sw:.1f}%;background:{_sc2};'
                                                    f'height:100%"></div>'
                                                )
                                        _th_html += (
                                            f'<div style="display:flex;align-items:center;'
                                            f'gap:8px;font-size:0.82em">'
                                            f'<div style="min-width:160px;text-align:right;'
                                            f'color:#555;font-size:0.9em">{_tl}</div>'
                                            f'<div style="flex:1;background:rgba(128,128,128,0.1);'
                                            f'border-radius:3px;height:18px;display:flex;'
                                            f'overflow:hidden">{_segs}</div>'
                                            f'<div style="min-width:24px;color:#aaa;'
                                            f'font-size:0.85em">{_total}</div>'
                                            f'</div>'
                                        )
                                    _th_html += '</div>'
                                    # Speaker legend
                                    _leg = " &nbsp;&nbsp; ".join(
                                        f'<span style="background:{_spk_cols[_i2]};'
                                        f'border-radius:50%;display:inline-block;width:9px;'
                                        f'height:9px;vertical-align:middle"></span> '
                                        f'{speaker_names_an.get(_sid2, _sid2)}'
                                        for _i2, _sid2 in enumerate(spk_ids)
                                    )
                                    _th_html += (
                                        f'<div style="font-size:0.78em;color:#888;'
                                        f'margin-bottom:4px">{_leg}</div>'
                                    )
                                    st.markdown(_th_html, unsafe_allow_html=True)

                                _rh_type_chart(
                                    _rh_f_types, _rh_spk_ids,
                                    L("rh_fallacy_types_heading"),
                                )
                                _rh_type_chart(
                                    _rh_d_types, _rh_spk_ids,
                                    L("rh_device_types_heading"),
                                )

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
                                        _rule_names = LABELS["rhetoric_rule_names"][lang]
                                        for f in all_fallacies:
                                            ts = ms_to_ts(f["start_ms"])
                                            _rule_n = f.get("violated_rule")
                                            _rule_tag = ""
                                            if _rule_n and _rule_n in _rule_names:
                                                _rule_tag = (
                                                    ' <small style="color:#888;font-weight:normal">('
                                                    + LABELS["rhetoric_rule_label"][lang].format(
                                                        n=_rule_n, name=_rule_names[_rule_n]
                                                    )
                                                    + ")</small>"
                                                )
                                            st.markdown(
                                                f"[{ts}] **{f.get('label', f.get('type', ''))}**"
                                                f" — \"{f.get('quote', '')}\"{_rule_tag}",
                                                unsafe_allow_html=True,
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
                        _motion_sr = st.session_state.get("motion", "").strip()
                        if _motion_sr:
                            st.caption(L("motion_caption").format(motion=_motion_sr))

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

                            # Reliability is only meaningful when there are conclusive verdicts.
                            # If everything the fact-checker touched came back "beyond scope",
                            # 0% is technically correct but communicates the wrong thing.
                            _conclusive = sum(
                                v.get(k, 0)
                                for k in ("true", "partially_true", "false", "contested", "misleading")
                            )
                            rs_str = (
                                f"{rs:.0%}"
                                if rs is not None and _conclusive > 0
                                else L("metric_na")
                            )
                            dr_str = f"{dr:.0%}" if dr is not None else L("metric_na")
                            sup_str = LABELS["metric_supported"][lang].format(
                                n=supported, total=checkable
                            )

                            _sr_help_col, _ = st.columns([3, 7])
                            with _sr_help_col:
                                if st.button(
                                    f"→ {L('help_link_scoring')}",
                                    key=f"help_scoring_{sid}",
                                ):
                                    help_dialogs.scoring_dialog(lang)

                            mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
                            mc1.metric(L("metric_reliability"),  rs_str,                             help=L("help_reliability"))
                            mc2.metric(L("metric_factchecked"),  sup_str,                            help=L("help_factchecked"))
                            mc3.metric(L("metric_direct_resp"),  dr_str,                             help=L("help_direct_resp"))
                            mc4.metric(L("metric_fallacies"),    str(score.get("fallacy_count", 0)), help=L("help_fallacies"))
                            _te = score.get("thread_engagement")
                            mc5.metric(
                                L("metric_thread_engagement"),
                                f"{_te:.0%}" if _te is not None else L("metric_na"),
                                help=L("help_thread_engagement"),
                            )
                            _rb = score.get("rebuttal_rate")
                            mc6.metric(
                                L("metric_rebuttal_rate"),
                                f"{_rb:.0%}" if _rb is not None else L("metric_na"),
                                help=L("help_rebuttal_rate"),
                            )

                            # Stance breakdown (only shown when a motion was set)
                            _motion_set = st.session_state.get("motion", "").strip()
                            _spk_claims = [
                                c for c in analysis.get("claims", [])
                                if c["speaker"] == sid
                            ]
                            if _motion_set and _spk_claims:
                                st.caption(L("stance_heading"))
                                _n_pro     = sum(1 for c in _spk_claims if c.get("stance") == "pro")
                                _n_con     = sum(1 for c in _spk_claims if c.get("stance") == "con")
                                _n_neutral = sum(1 for c in _spk_claims if c.get("stance", "neutral") == "neutral")
                                sc1, sc2, sc3 = st.columns(3)
                                sc1.metric(L("stance_pro"),     _n_pro)
                                sc2.metric(L("stance_con"),     _n_con)
                                sc3.metric(L("stance_neutral"), _n_neutral)

                            # Survivability breakdown (only when detect_responses has run)
                            _surv_report = st.session_state.get("survivability", {})
                            if _surv_report and _spk_claims:
                                st.caption(L("surv_heading"))
                                _sg = sum(1 for c in _spk_claims if _surv_report.get(c["id"]) == "grounded")
                                _sc = sum(1 for c in _spk_claims if _surv_report.get(c["id"]) == "contested")
                                _su = sum(1 for c in _spk_claims if _surv_report.get(c["id"]) == "unattacked")
                                sv1, sv2, sv3 = st.columns(3)
                                sv1.metric(L("surv_grounded"),   _sg)
                                sv2.metric(L("surv_contested"),  _sc)
                                sv3.metric(L("surv_unattacked"), _su)

                            # Restatement count
                            _n_restat = sum(1 for c in _spk_claims if c.get("restatement_of"))
                            if _n_restat:
                                st.caption(
                                    LABELS["restatement_report"][lang].format(n=_n_restat)
                                )

                            # Dialectical stage breakdown (only when stage analysis has run)
                            _stages_report = st.session_state.get("stages", [])
                            _spk_stages = [s for s in _stages_report if s["speaker"] == sid]
                            if _spk_stages:
                                st.caption(L("stage_heading_report"))
                                _n_conf = sum(1 for s in _spk_stages if s.get("dialectical_stage") == "confrontation")
                                _n_open = sum(1 for s in _spk_stages if s.get("dialectical_stage") == "opening")
                                _n_arg  = sum(1 for s in _spk_stages if s.get("dialectical_stage") == "argumentation")
                                _n_conc = sum(1 for s in _spk_stages if s.get("dialectical_stage") == "concluding")
                                sg1, sg2, sg3, sg4 = st.columns(4)
                                sg1.metric(L("stage_confrontation"), _n_conf)
                                sg2.metric(L("stage_opening"),       _n_open)
                                sg3.metric(L("stage_argumentation"), _n_arg)
                                sg4.metric(L("stage_concluding"),    _n_conc)

                            # Verdict breakdown — colored horizontal bars, ordered by outcome
                            _VB_ORDER  = ["true", "partially_true", "contested",
                                          "misleading", "false", "unverifiable", "subjective"]
                            _VB_COLORS = {
                                "true":           "#2ca02c",
                                "partially_true": "#8bc34a",
                                "contested":      "#ff7f0e",
                                "misleading":     "#ff7f0e",
                                "false":          "#d62728",
                                "unverifiable":   "#9e9e9e",
                                "subjective":     "#9e9e9e",
                            }
                            _beyond_total = v.get("unverifiable", 0) + v.get("subjective", 0)
                            _total_v = sum(v.get(k, 0) for k in _VB_ORDER)
                            if _conclusive > 0 and _total_v > 0:
                                st.caption(L("chart_verdicts"))
                                _bars = ""
                                for _vk in _VB_ORDER:
                                    _cnt = v.get(_vk, 0)
                                    if _cnt == 0:
                                        continue
                                    _lbl   = _VERDICT_LABEL_MAP.get(_vk, _vk)
                                    _col   = _VB_COLORS.get(_vk, "#9e9e9e")
                                    _pct   = _cnt / _total_v * 100
                                    _bars += (
                                        f'<div style="display:flex;align-items:center;'
                                        f'margin:4px 0;gap:8px;font-size:0.83em">'
                                        f'<div style="min-width:130px;text-align:right;'
                                        f'color:#888">{_lbl}</div>'
                                        f'<div style="flex:1;background:rgba(128,128,128,0.15);'
                                        f'border-radius:3px;height:18px">'
                                        f'<div style="width:{_pct:.1f}%;background:{_col};'
                                        f'border-radius:3px;height:100%;min-width:4px"></div></div>'
                                        f'<div style="min-width:28px;color:#aaa">{_cnt}</div>'
                                        f'</div>'
                                    )
                                st.markdown(_bars, unsafe_allow_html=True)
                            elif _beyond_total > 0:
                                # All checked claims were outside verifiable scope — no chart needed
                                _beyond_note = (
                                    f"{_beyond_total} claim(s) checked — all fell outside "
                                    "what can be objectively verified (see fact-check disclaimer)."
                                    if lang == "English" else
                                    f"{_beyond_total} afirmación/es verificada/s — todas quedan "
                                    "fuera del alcance verificable (ver aviso de verificación)."
                                )
                                st.caption(_beyond_note)

                            # Narrative summary
                            st.info(summary)

                            if idx < len(speaker_report) - 1:
                                st.divider()


if __name__ == "__main__":
    main()
