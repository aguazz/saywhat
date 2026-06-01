# SayWhat — Help Tour Plan

Interactive in-app help: six `st.dialog` modals explaining the analysis system,
accessible via inline `→` links and a permanent sidebar Help panel.

---

## Status

| # | Prompt | Files | Status |
|---|--------|-------|--------|
| A | Create `truth_checker/help_dialogs.py` — all 6 dialog functions | new file | ✓ Done |
| B | LABELS + empty state restructure | `app.py` | ✓ Done |
| C | Sidebar Help panel | `app.py` | ✓ Done |
| D | Contextual `→` buttons at 5 locations | `app.py` | ✓ Done |

---

## Prompt A — Create `truth_checker/help_dialogs.py`

Create a new file at `truth_checker/help_dialogs.py` with the full content below.
Do not modify any other file in this prompt.

```python
import streamlit as st


# ── Dialog 1: Claims ──────────────────────────────────────────────────────────

@st.dialog("What is a claim?")
def claims_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Una **afirmación** es una declaración sobre el mundo con la que se puede estar de acuerdo o en desacuerdo. "
            "No todas las frases son afirmaciones: las preguntas, los saludos y los chistes se descartan. "
            "Solo se conservan las aseveraciones sustantivas."
        )
        st.markdown("**Tipos de afirmación**")
        st.markdown(
            "| Tipo | Qué asevera | Ejemplo |\n"
            "|------|-------------|--------|\n"
            "| Factual | Algo que ocurrió o existe | *«Oslo prohibió los coches en 2019»* |\n"
            "| Estadística | Un número o cantidad | *«Los negocios cayeron un 15 % el primer año»* |\n"
            "| Causal | Una cosa causó otra | *«Más tráfico peatonal impulsó los ingresos»* |\n"
            "| Predictiva | Lo que ocurrirá | *«Houston se paralizaría sin coches»* |\n"
            "| Comparativa | Una comparación | *«El transporte de Oslo es mejor que el de Houston»* |\n"
            "| Interpretativa | El significado de algo | *«Una caída de un año no es un problema real»* |\n"
            "| Moral | Lo que debería hacerse | *«Las ciudades deberían prohibir los coches»* |\n"
            "| Definitoria | El significado de un término | *«Una zona peatonal no es una ciudad sin coches»* |\n"
            "| Anecdótica | Un caso personal aislado | *«La tienda de mi primo duplicó sus ventas»* |"
        )
        st.caption("La herramienta extrae 3-6 afirmaciones por turno de hablante, no cada frase.")
    else:
        st.markdown(
            "A **claim** is a statement about the world that can be agreed or disagreed with. "
            "Not every sentence is a claim: questions, greetings, and jokes are filtered out. "
            "Only substantive assertions are kept."
        )
        st.markdown("**Claim types**")
        st.markdown(
            "| Type | What it asserts | Example |\n"
            "|------|----------------|--------|\n"
            "| Factual | Something that happened or exists | *'Oslo tried a car ban in 2019'* |\n"
            "| Statistical | A number or quantity | *'Businesses dropped 15% in year one'* |\n"
            "| Causal | One thing caused another | *'Higher foot traffic drove revenue up'* |\n"
            "| Predictive | What will happen | *'Houston would be paralyzed without cars'* |\n"
            "| Comparative | A comparison | *'Oslo's transit is better than Houston's'* |\n"
            "| Interpretive | What something means | *'A one-year dip isn't a real problem'* |\n"
            "| Moral | What should be done | *'Cities should ban cars downtown'* |\n"
            "| Definitional | What a term means | *'A pedestrian zone isn't a car-free city'* |\n"
            "| Anecdotal | A single personal case | *'My cousin's shop doubled its sales'* |"
        )
        st.caption("The app extracts 3–6 claims per speaker turn, not every sentence.")


# ── Dialog 2: Threads ─────────────────────────────────────────────────────────

@st.dialog("What are threads?")
def threads_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Un **hilo** es un grupo de afirmaciones que tratan el mismo subtema, "
            "independientemente de quién las hizo."
        )
        st.markdown(
            "Los hilos permiten ver qué temas generaron más intercambio "
            "y cuáles quedaron sin resolver."
        )
        st.markdown("**Ejemplo** — debate Alex / Sam sobre los coches en el centro:")
        st.markdown(
            "| Hilo | Afirmaciones |\n"
            "|------|-------------|\n"
            "| Efectos en la calidad del aire | C1 (Alex), C2 (Sam) |\n"
            "| Impacto económico en los negocios | C3 (Sam), C4 (Alex), C5 (Alex) |\n"
            "| Generalización a otras ciudades | C6 (Sam), C7 (Sam) |"
        )
        st.caption("Un debate típico genera entre 3 y 8 hilos.")
    else:
        st.markdown(
            "A **thread** is a group of claims that address the same sub-topic, "
            "regardless of who made them."
        )
        st.markdown(
            "Threads let you see which subjects generated the most back-and-forth "
            "and which were left unresolved."
        )
        st.markdown("**Example** — Alex / Sam debate on cars in city centres:")
        st.markdown(
            "| Thread | Claims |\n"
            "|--------|--------|\n"
            "| Air quality effects | C1 (Alex), C2 (Sam) |\n"
            "| Economic impact on businesses | C3 (Sam), C4 (Alex), C5 (Alex) |\n"
            "| Generalizability to other cities | C6 (Sam), C7 (Sam) |"
        )
        st.caption("A typical debate produces 3–8 threads.")


# ── Dialog 3: Responses ───────────────────────────────────────────────────────

@st.dialog("How claims respond to each other")
def responses_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Cada vez que un hablante aborda una afirmación anterior, esa conexión es una **respuesta**. "
            "Las respuestas son las flechas del mapa de argumentos."
        )
        st.markdown("**Tipos de respuesta**")
        st.markdown(
            "| Tipo | Qué hace |\n"
            "|------|----------|\n"
            "| **refutes** | Niega directamente la conclusión |\n"
            "| **undercuts** | Cuestiona la evidencia, no la conclusión |\n"
            "| **supports** | Añade evidencia a favor |\n"
            "| **weakens** | Acepta pero reduce el alcance |\n"
            "| **reframes** | Acepta los hechos, cambia su significado |\n"
            "| **concedes** | Reconoce que el otro lado tiene razón |\n"
            "| **evades** | Cambia de tema |\n"
            "| **ignores** | Introduce un punto no relacionado |"
        )
        st.info(
            "**refutes** = «estás equivocado.»  \n"
            "**undercuts** = «tu evidencia no lo demuestra — aunque puede que tengas razón.»  \n\n"
            "Ejemplo: Sam dice que la cifra del 40 % de NO₂ proviene de «una sola calle en Madrid». "
            "Eso es un **undercut**: Sam no niega que la calidad del aire mejore, "
            "solo que este dato no lo prueba."
        )
    else:
        st.markdown(
            "Every time a speaker addresses a prior claim, that connection is a **response**. "
            "Responses are the arrows in the argument map."
        )
        st.markdown("**Response types**")
        st.markdown(
            "| Type | What it does |\n"
            "|------|--------------|\n"
            "| **refutes** | Directly denies the conclusion |\n"
            "| **undercuts** | Challenges the evidence, not the conclusion |\n"
            "| **supports** | Adds evidence in favour |\n"
            "| **weakens** | Accepts but limits scope |\n"
            "| **reframes** | Accepts facts, changes their meaning |\n"
            "| **concedes** | Acknowledges the other side has a point |\n"
            "| **evades** | Changes the subject |\n"
            "| **ignores** | Makes an unrelated new point |"
        )
        st.info(
            "**refutes** = 'you're wrong.'  \n"
            "**undercuts** = 'your evidence doesn't prove it — though you might still be right.'  \n\n"
            "Example: Sam says the 40% NO₂ figure comes from 'just one street in Madrid.' "
            "That's an **undercut** — Sam isn't saying air quality doesn't improve, "
            "just that this data point doesn't prove it does everywhere."
        )


# ── Dialog 4: Fact-checking ───────────────────────────────────────────────────

@st.dialog("How fact-checking works")
def factcheck_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Solo se verifican las afirmaciones **comprobables** — aquellas que pueden contrastarse "
            "con evidencia externa. Las afirmaciones morales, las opiniones puras y las predicciones se omiten."
        )
        st.markdown("**Tres pasos**")
        st.markdown(
            "1. **Recuperar evidencia** — busca en Wikipedia y Semantic Scholar fuentes relevantes  \n"
            "2. **Valorar** — un modelo de IA lee la afirmación y la evidencia y las sopesa  \n"
            "3. **Veredicto** — una de siete etiquetas"
        )
        st.markdown("**Veredictos**")
        st.markdown(
            "| Veredicto | Significado |\n"
            "|-----------|-------------|\n"
            "| Respaldado | La evidencia apoya la afirmación |\n"
            "| Parcialmente respaldado | Verdadero pero incompleto o sin contexto |\n"
            "| Disputado | La evidencia apunta en ambas direcciones |\n"
            "| Engañoso | Técnicamente correcto pero desorientador |\n"
            "| No respaldado | La evidencia contradice la afirmación |\n"
            "| Fuera de alcance | No verificable (moral, subjetivo) |\n"
            "| No verificable | Evidencia insuficiente encontrada |"
        )
        st.caption(
            "«Respaldado» significa que la evidencia disponible apoya la afirmación — "
            "no que esté probada de forma definitiva."
        )
    else:
        st.markdown(
            "Only **checkable** claims are fact-checked — those that can be tested against external evidence. "
            "Moral claims, pure opinions, and predictions are skipped."
        )
        st.markdown("**Three steps**")
        st.markdown(
            "1. **Retrieve evidence** — searches Wikipedia and Semantic Scholar for relevant sources  \n"
            "2. **Assess** — an AI model reads the claim and the evidence and weighs them  \n"
            "3. **Verdict** — one of seven labels"
        )
        st.markdown("**Verdicts**")
        st.markdown(
            "| Verdict | Meaning |\n"
            "|---------|--------|\n"
            "| Supported | Evidence backs the claim |\n"
            "| Partially supported | True but incomplete or missing context |\n"
            "| Contested | Evidence cuts both ways |\n"
            "| Misleading | Technically accurate but likely to mislead |\n"
            "| Unsupported | Evidence contradicts the claim |\n"
            "| Beyond scope | Not verifiable against evidence (moral, subjective) |\n"
            "| Unverifiable | Insufficient evidence found |"
        )
        st.caption(
            "'Supported' means the available evidence backs the claim — "
            "not that it has been definitively proven."
        )


# ── Dialog 5: Rhetoric ────────────────────────────────────────────────────────

@st.dialog("Fallacies and rhetorical devices")
def rhetoric_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "**Las falacias** son errores de razonamiento. Solo se marcan cuando hay una cita concreta que señalar.  \n"
            "**Los recursos retóricos** son técnicas de persuasión. No son errores — pueden ser completamente legítimos."
        )
        st.markdown("**Falacias principales**")
        st.markdown(
            "| Falacia | Qué hace |\n"
            "|---------|----------|\n"
            "| Hombre de paja | Ataca una versión distorsionada del argumento |\n"
            "| Ad hominem | Ataca a la persona, no al argumento |\n"
            "| Selección de evidencia | Usa solo los datos favorables |\n"
            "| Falsa disyuntiva | Presenta solo dos opciones cuando hay más |\n"
            "| Pendiente resbaladiza | Un paso lleva inevitablemente al extremo |\n"
            "| Generalización apresurada | Conclusión amplia a partir de muy pocos casos |\n"
            "| Whataboutism | Desvía señalando los fallos del otro |"
        )
        st.markdown("**Recursos retóricos**")
        st.markdown(
            "| Recurso | Qué hace |\n"
            "|---------|----------|\n"
            "| Apelación a la autoridad | Cita a un experto o institución legítima |\n"
            "| Ejemplo vívido | Hace concreta una idea abstracta |\n"
            "| Prueba social | Apela al consenso amplio |\n"
            "| Lenguaje cargado | Palabras con carga emocional |"
        )
        st.caption(
            "La misma técnica (p. ej., citar autoridad) puede ser un recurso legítimo o una falacia "
            "según el contexto. La herramienta intenta distinguirlos."
        )
    else:
        st.markdown(
            "**Fallacies** are reasoning errors. They're only flagged when a specific quote can be cited.  \n"
            "**Rhetorical devices** are persuasion techniques. They're not errors — they can be entirely legitimate."
        )
        st.markdown("**Key fallacies**")
        st.markdown(
            "| Fallacy | What it does |\n"
            "|---------|-------------|\n"
            "| Straw man | Attacks a distorted version of the argument |\n"
            "| Ad hominem | Attacks the person, not the argument |\n"
            "| Cherry-picking | Uses only the supporting evidence |\n"
            "| False dichotomy | Presents only two options when more exist |\n"
            "| Slippery slope | Claims one step inevitably leads to the extreme |\n"
            "| Hasty generalisation | Broad conclusion from too few cases |\n"
            "| Whataboutism | Deflects by pointing to the other side's faults |"
        )
        st.markdown("**Rhetorical devices**")
        st.markdown(
            "| Device | What it does |\n"
            "|--------|-------------|\n"
            "| Appeal to authority | Cites a relevant expert or institution |\n"
            "| Vivid example | Makes an abstract point concrete |\n"
            "| Social proof | Appeals to wide consensus |\n"
            "| Loaded language | Emotionally charged word choice |"
        )
        st.caption(
            "The same technique (e.g., citing authority) can be a legitimate device or a fallacy "
            "depending on context. The app tries to distinguish them."
        )


# ── Dialog 6: Scoring ─────────────────────────────────────────────────────────

@st.dialog("How speakers are scored")
def scoring_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown("Dos puntuaciones independientes, que miden cosas distintas.")
        st.markdown(
            "**Fiabilidad**  \n"
            "De todas las afirmaciones comprobables del hablante, ¿qué fracción resultó "
            "respaldada o parcialmente respaldada?  \n"
            "→ Mide la precisión factual. *No* mide si el argumento fue persuasivo o lógicamente sólido."
        )
        st.markdown(
            "**Tasa de respuesta directa**  \n"
            "De todas las veces que el hablante pudo responder a una afirmación concreta del otro lado, "
            "¿con qué frecuencia respondió de verdad (refutó, apoyó, reencuadró…) en lugar de evadir?  \n"
            "→ Mide el compromiso argumentativo. Una tasa alta = debatiente implicado. Baja = evita el tema."
        )
        st.markdown("**Cómo leer las dos juntas**")
        st.markdown(
            "| Fiabilidad | Tasa de respuesta | Perfil |\n"
            "|------------|-------------------|--------|\n"
            "| Alta | Alta | Más sólido: preciso y comprometido |\n"
            "| Alta | Baja | Preciso pero evasivo |\n"
            "| Baja | Alta | Comprometido pero a menudo incorrecto |\n"
            "| Baja | Baja | Evasivo e impreciso |"
        )
        st.caption(
            "Un hablante que hace solo afirmaciones morales o subjetivas mostrará N/D en fiabilidad — "
            "no una puntuación baja. Esas afirmaciones están fuera del alcance de la verificación."
        )
    else:
        st.markdown("Two independent scores, measuring different things.")
        st.markdown(
            "**Reliability**  \n"
            "Of all this speaker's checkable claims, what fraction were rated Supported or "
            "Partially Supported?  \n"
            "→ Measures factual accuracy. Does *not* measure whether the argument was persuasive or logically sound."
        )
        st.markdown(
            "**Direct response rate**  \n"
            "Of all the times this speaker could have responded to a specific claim from the other side, "
            "how often did they genuinely engage (refute, support, reframe…) rather than evade or ignore?  \n"
            "→ Measures argumentative engagement. High rate = engaged debater. Low rate = deflects."
        )
        st.markdown("**Reading both scores together**")
        st.markdown(
            "| Reliability | Response rate | Profile |\n"
            "|-------------|---------------|---------|\n"
            "| High | High | Strongest: accurate and engaged |\n"
            "| High | Low | Accurate but evasive |\n"
            "| Low | High | Engaged but often wrong |\n"
            "| Low | Low | Evasive and inaccurate |"
        )
        st.caption(
            "A speaker who makes only moral or subjective claims will show N/A for reliability — "
            "not a low score. Those claims are outside the scope of fact-checking."
        )
```

---

## Prompt B — LABELS + empty state restructure in app.py

### Step 1 — Add LABELS entries

In app.py, add the following entries in the **"── Analysis tab ──"** section (around line 103),
after the existing `analysis_empty_heading` and `analysis_empty_body` entries.
Keep `analysis_empty_heading` as-is; `analysis_empty_body` is no longer used
but leave it in place (it does no harm).

```python
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
```

### Step 2 — Add the import

At the top of app.py, after the existing truth_checker imports, add:

```python
from truth_checker import help_dialogs
```

### Step 3 — Replace the empty state block

Find the existing block (around line 1249):

```python
            if not st.session_state.get("analysis"):
                st.info(
                    f"**{L('analysis_empty_heading')}**\n\n{L('analysis_empty_body')}"
                )
```

Replace it with:

```python
            if not st.session_state.get("analysis"):
                with st.container(border=True):
                    st.markdown(f"**{L('analysis_empty_heading')}**")
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
                            st.markdown(f"— {L(_bkey)}")
                        with _col_btn:
                            if st.button(
                                f"→ {L(_lkey)}",
                                key=f"help_{_lkey}_empty",
                                use_container_width=True,
                            ):
                                _dlg(lang)
```

---

## Prompt C — Sidebar Help panel in app.py

Find the existing sidebar block (around lines 690–696):

```python
    with st.sidebar:
        st.session_state["lang"] = st.selectbox(
            "Language / Idioma",
            ["English", "Español"],
            index=["English", "Español"].index(st.session_state["lang"]),
        )
```

Replace it with:

```python
    with st.sidebar:
        st.session_state["lang"] = st.selectbox(
            "Language / Idioma",
            ["English", "Español"],
            index=["English", "Español"].index(st.session_state["lang"]),
        )
        st.divider()
        with st.expander(f"📖 {L('help_sidebar_heading')}", expanded=False):
            _SIDEBAR_HELP = [
                ("help_link_claims",    help_dialogs.claims_dialog),
                ("help_link_threads",   help_dialogs.threads_dialog),
                ("help_link_responses", help_dialogs.responses_dialog),
                ("help_link_factcheck", help_dialogs.factcheck_dialog),
                ("help_link_rhetoric",  help_dialogs.rhetoric_dialog),
                ("help_link_scoring",   help_dialogs.scoring_dialog),
            ]
            for _lkey, _dlg in _SIDEBAR_HELP:
                if st.button(f"→ {L(_lkey)}", key=f"help_{_lkey}_sidebar", use_container_width=True):
                    _dlg(lang)
```

Note: `L("help_sidebar_heading")` and `L("help_link_*")` are added in Prompt B Step 1.
The `lang` variable is available at this point in `main()` because the selectbox
has just set `st.session_state["lang"]` and `lang = st.session_state["lang"]` follows.

---

## Prompt D — Contextual `→` buttons at 5 locations in app.py

### D1 — Claims tab: below the filter selectors

Find the two filter columns (around the `col_f1, col_f2 = st.columns(2)` line
and the `sel_spk` / `sel_type` selectors inside them). Add the following two lines
immediately after the closing `with col_f2:` block ends and before `filtered = claims`:

```python
                        _hc1, _hc2, _ = st.columns([2, 2, 6])
                        with _hc1:
                            if st.button(f"→ {L('help_link_claims')}", key="help_claims_table"):
                                help_dialogs.claims_dialog(lang)
                        with _hc2:
                            if st.button(f"→ {L('help_link_threads')}", key="help_threads_table"):
                                help_dialogs.threads_dialog(lang)
```

### D2 — Detect Responses button: add link beside it

Find the Detect Responses button row (the `col_dr, col_dr_note, col_dr_dl = st.columns([1, 2, 2])`
block). After that entire block ends and before the `if dr_clicked and anthropic_key:` block,
insert:

```python
                _dr_help_col, _ = st.columns([3, 7])
                with _dr_help_col:
                    if st.button(f"→ {L('help_link_responses')}", key="help_responses_dr"):
                        help_dialogs.responses_dialog(lang)
```

### D3 — Argument Map: near the legend heading

Find `st.markdown(f"#### {L('legend_heading')}")` in the Argument Map sub-tab
(after the graph HTML component). Insert immediately before it:

```python
                        _map_help_col, _ = st.columns([3, 7])
                        with _map_help_col:
                            if st.button(f"→ {L('help_link_responses')}", key="help_responses_map"):
                                help_dialogs.responses_dialog(lang)
```

### D4 — Rhetorical Profile: near the intro blurb

Find `st.info(L("rhetoric_intro"))` in the Rhetorical Profile sub-tab.
Insert immediately after it:

```python
                        _rh_help_col, _ = st.columns([3, 7])
                        with _rh_help_col:
                            if st.button(f"→ {L('help_link_rhetoric')}", key="help_rhetoric_tab"):
                                help_dialogs.rhetoric_dialog(lang)
```

### D5 — Speaker Report: near the metric grid

Find `mc1, mc2, mc3, mc4 = st.columns(4)` in the Speaker Report sub-tab.
Insert immediately before it:

```python
                            _sr_help_col, _ = st.columns([3, 7])
                            with _sr_help_col:
                                if st.button(
                                    f"→ {L('help_link_scoring')}",
                                    key=f"help_scoring_{sid}",
                                ):
                                    help_dialogs.scoring_dialog(lang)
```

Note: this is inside the `for idx, sid in enumerate(sorted(speaker_report.keys())):` loop,
so the key uses `sid` to ensure uniqueness per speaker.

---

## Notes

**`lang` availability:** All dialog call sites are inside `main()` where `lang` is already defined.

**Key uniqueness:** Every `st.button` uses a distinct `key=` argument. Buttons in loops
include the loop variable in the key.

**Dialog titles are English-only** — hardcoded in the `@st.dialog` decorator at function
definition time. Content inside each dialog is fully bilingual via the `lang` parameter.

**`analysis_empty_body` LABELS entry** from UX_IMPROVEMENTS_PLAN Prompt 3 is now superseded
by the per-bullet entries. It is left in LABELS but no longer referenced.
