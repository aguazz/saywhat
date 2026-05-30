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
from truth_checker.dung        import compute_grounded_extension
from truth_checker.deduplicator import mark_restatements
from truth_checker.stage_labeler import label_dialectical_stages

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
    "legend_undercuts":    {"English": "challenges the reasoning",   "Español": "cuestiona el razonamiento"},
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
    "rhetoric_footer":    {
        "English": "Rhetorical devices are not always flaws. Labels show technique, not quality.",
        "Español": "Los recursos retóricos no son siempre defectos. Las etiquetas indican técnica, no calidad.",
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
    # ── Per-step download / import ──────────────────────────────────────────
    "dl_verdicts":         {"English": "⬇ Fact-check results (.json)",
                            "Español": "⬇ Resultados de verificación (.json)"},
    "dl_responses":        {"English": "⬇ Response map (.json)",
                            "Español": "⬇ Mapa de respuestas (.json)"},
    "dl_rhetoric":         {"English": "⬇ Rhetoric analysis (.json)",
                            "Español": "⬇ Análisis retórico (.json)"},
    "load_results_expander": {"English": "⬆ Load saved results (fact-check / responses / rhetoric)",
                              "Español": "⬆ Cargar resultados guardados (verificación / respuestas / retórica)"},
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

                    # ── Load saved results (verdicts / responses / rhetoric) ───
                    with st.expander(L("load_results_expander")):
                        _lv_col, _lr_col, _lrh_col = st.columns(3)

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
                                            analysis.get("claims", []),
                                            _d["responses"],
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
                                        st.success(L("rhetoric_loaded"))
                                        st.rerun()
                                except Exception:
                                    st.error(L("err_invalid_json"))

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
                            st.session_state["survivability"] = compute_grounded_extension(
                                analysis.get("claims", []),
                                st.session_state["responses"],
                            )
                        except Exception as exc:
                            _prog_dr.empty()
                            st.error(str(exc))

                    # Analyze Rhetoric button
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
                        # Stage labeling runs on the same turns (batched, Haiku)
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
                                f"<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse'>"
                                f"<thead><tr>{hdr_html}</tr></thead><tbody>{rows_html}</tbody></table></div>",
                                unsafe_allow_html=True,
                            )
                        else:
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
                        # Graph layer toggles (two columns — premises on by default)
                        _tgl1, _tgl2 = st.columns(2)
                        with _tgl1:
                            show_premises_cb = st.checkbox(L("show_premises"), value=True)
                        with _tgl2:
                            show_rt_cb = st.checkbox(L("show_reasoning_targets"), value=False)

                        graph_html = build_graph_html(
                            analysis.get("claims", []),
                            responses,
                            speaker_names_an,
                            survivability=st.session_state.get("survivability"),
                            show_premises=show_premises_cb,
                            show_reasoning_targets=show_rt_cb,
                        )
                        if graph_html:
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
                            '<span style="color:#d62728">━</span> directly contradicts &nbsp;&nbsp;'
                            '<span style="color:#e377c2">━</span> ' + L("legend_undercuts") + ' &nbsp;&nbsp;'
                            '<span style="color:#2ca02c">━</span> supports &nbsp;&nbsp;'
                            '<span style="color:#ff7f0e">━</span> weakens / concedes &nbsp;&nbsp;'
                            '<span style="color:#9467bd">━</span> reframes &nbsp;&nbsp;'
                            '<span style="color:#aaaaaa">━</span> evades / ignores'
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
                            # Distribution bar chart — turns per stage
                            _stage_counts: dict[str, int] = {}
                            for _si in _stages:
                                _stg = _si.get("dialectical_stage", "argumentation")
                                _lbl = L(_STAGE_LABEL_KEY.get(_stg, "stage_argumentation"))
                                _stage_counts[_lbl] = _stage_counts.get(_lbl, 0) + 1
                            _stage_df = pd.DataFrame.from_dict(
                                _stage_counts, orient="index", columns=["turns"]
                            )
                            st.bar_chart(_stage_df, use_container_width=True)
                            # Compact colored turn-by-turn sequence
                            _boxes = []
                            for _si in sorted(_stages, key=lambda x: x.get("turn_index", 0)):
                                _stg    = _si.get("dialectical_stage", "argumentation")
                                _color  = _STAGE_COLORS.get(_stg, "#cccccc")
                                _ts     = ms_to_ts(_si.get("start_ms", 0))
                                _spknm  = speaker_names_an.get(_si["speaker"], _si["speaker"])
                                _stglbl = L(_STAGE_LABEL_KEY.get(_stg, "stage_argumentation"))
                                _boxes.append(
                                    f'<span style="background:{_color};color:#fff;border-radius:3px;'
                                    f'padding:2px 7px;font-size:0.75em;white-space:nowrap">'
                                    f'[{_ts}] {_spknm} · {_stglbl}</span>'
                                )
                            st.markdown(
                                '<div style="display:flex;flex-wrap:wrap;gap:4px;margin:8px 0">'
                                + " ".join(_boxes) + "</div>",
                                unsafe_allow_html=True,
                            )
                            st.divider()

                        # ── Per-speaker rhetoric ───────────────────────────────
                        if rhetoric:
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
