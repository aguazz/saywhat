# SayWhat — UX Improvements Plan

> **Reading guide:** skim the status table first, then jump to the prompt for the change you want
> to implement. Each prompt is self-contained — paste it directly into Claude Code.

---

## Current Status

| # | Change | File(s) | Status |
|---|--------|---------|--------|
| 1 | Speaker Report — metric help tooltips | `app.py` | ✓ Done |
| 2 | Verdict badge color legend | `app.py` | ✓ Done |
| 3 | Claims tab empty state | `app.py` | ✓ Done |
| 4 | Rhetorical Profile intro blurb | `app.py` | ✓ Done |
| 5 | Argument Map "How to read this" overlay | `app.py` | ✓ Done |
| 6 | Claims table column header tooltips | `app.py` | ✓ Done |
| 7 | Argument Map relationship legend — add meanings | `app.py` | ✓ Done |
| 8 | Graph node and edge hover tooltips | `app.py`, `truth_checker/visualizer.py` | ✓ Done |

**Recommended implementation order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (roughly easiest first,
most complex last). Each prompt is independent — order is not a hard requirement.

---

## Change 1 — Speaker Report: metric help tooltips

**Problem solved:** The four metrics on the Speaker Report tab (`Reliability`, `Supported claims`,
`Direct response rate`, `Logical fallacies`) are numbers with no frame of reference. Users don't
know what they measure, what a good score looks like, or what the score does *not* measure.

**How it works:** Streamlit `st.metric()` accepts a `help=` parameter that renders an ℹ tooltip
icon next to the metric label. No layout changes needed.

**Files changed:** `app.py` only — two places: new LABELS entries (in the LABELS dict near the
top) and updated `st.metric()` calls (around lines 2448–2452).

---

**Prompt 1:**

```
In app.py, add help tooltip text to the four st.metric() calls in the Speaker Report sub-tab.

Step 1 — Add these four new entries to the LABELS dict (insert them in the
"── Speaker Report sub-tab ──" section, after the existing "chart_verdicts" entry, around line 334):

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

Step 2 — Update the four st.metric() calls around lines 2448–2452 to use the help= parameter:

    mc1.metric(L("metric_reliability"), rs_str,                            help=L("help_reliability"))
    mc2.metric(L("metric_factchecked"), sup_str,                           help=L("help_factchecked"))
    mc3.metric(L("metric_direct_resp"), dr_str,                            help=L("help_direct_resp"))
    mc4.metric(L("metric_fallacies"),   str(score.get("fallacy_count", 0)), help=L("help_fallacies"))

Do not change any other code. Make sure the LABELS entries use proper Python string formatting
(no trailing commas inside the string, proper quote escaping).
```

---

## Change 2 — Verdict badge color legend

**Problem solved:** Users see colored verdict badges in the Claims tab and Fact-Check tab but
have no way to know what the colors mean without clicking through every badge.

**How it works:** A single-line HTML legend is inserted just above the claims table (inside the
`else:` branch of `if not claims:`, before the `<details open>` collapsible section at line 1586).
The same legend is inserted in the Fact-Check tab, just after the four summary metrics
(before `st.divider()` at line 2061). Both reuse the existing `_VSTYLE` / `_FC_VSTYLE` colors
and the existing L("verdict_*") label strings — no new colors to define.

**Files changed:** `app.py` only.

---

**Prompt 2:**

```
In app.py, add a verdict color legend in two places.

Step 1 — Add one new LABELS entry in the "── Verdict labels ──" section (around line 140),
after the existing "verdict_none" entry:

    "verdict_legend_label": {
        "English": "Verdicts:",
        "Español": "Veredictos:",
    },

Step 2 — In the Claims sub-tab, insert the legend BEFORE the `st.markdown(...)` call that
opens the `<details open>` collapsible table at line 1586. The legend should only appear
when verdicts are present, so place it just inside the `if verdicts:` block (around line 1593),
as the first thing inside that block, before the `th = ...` line:

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
    st.markdown(
        f'<div style="margin-bottom:8px"><small><strong>{L("verdict_legend_label")}</strong> '
        f'{_legend_html}</small></div>',
        unsafe_allow_html=True,
    )

Step 3 — In the Fact-Check sub-tab, insert the same legend AFTER the four summary metrics
(after the `_mc4.metric(...)` line around line 2011) and BEFORE the `st.caption(L("fc_disclaimer"))`
line. Reuse the same _legend_html construction but use `_FC_VSTYLE` colors instead:

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

Do not change any other code.
```

---

## Change 3 — Claims tab empty state

**Problem solved:** When a transcript is loaded but analysis has not yet been run, the Claims
tab shows only a "Run Analysis" button with a cost note. Users have no idea what they're about
to trigger or what the result will look like.

**How it works:** Add a short `st.info()` block that appears only when `analysis` is None,
inserted just before the `Run Analysis` button section (before `col_btn, col_note = st.columns(...)`)
at line 1076. When analysis has run, this block is not shown.

**Files changed:** `app.py` only.

---

**Prompt 3:**

```
In app.py, add an empty-state explanation above the Run Analysis button.

Step 1 — Add these two new LABELS entries in the "── Analysis tab ──" section (around line 103),
after the existing "analysis_cost" entry:

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

Step 2 — In the Analysis tab body, find the block that starts with `if not anthropic_key:` and
ends just before `col_btn, col_note = st.columns([1, 3])` (around lines 1073–1076).
Insert the following AFTER the `if not anthropic_key:` block but BEFORE `col_btn, col_note`:

    if not analysis:
        st.info(
            f"**{L('analysis_empty_heading')}**\n\n{L('analysis_empty_body')}"
        )

Do not change any other code.
```

---

## Change 4 — Rhetorical Profile intro blurb

**Problem solved:** The Rhetorical Profile tab shows speaker-by-speaker breakdowns of fallacies
and rhetorical devices, but never explains what those terms mean. Many users don't know what a
logical fallacy is, don't know the difference between a fallacy and a rhetorical device, or
assume that any flagged item is evidence of bad behavior.

**How it works:** A single `st.info()` block is added at the top of the rhetoric content section
(inside the `else:` branch at line 2212, before the stage timeline block).

**Files changed:** `app.py` only.

---

**Prompt 4:**

```
In app.py, add an intro blurb to the Rhetorical Profile sub-tab.

Step 1 — Add this new LABELS entry in the "── Rhetorical Profile sub-tab ──" section
(around line 287), after the existing "rhetoric_footer" entry:

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

Step 2 — In the Rhetorical Profile sub-tab, find the `else:` branch that starts at line ~2212
(after `if not rhetoric and not _stages:`). Inside the `else:` block, as the very first
statement — before the `if _stages:` check — insert:

    st.info(L("rhetoric_intro"))

Do not change any other code.
```

---

## Change 5 — Argument Map "How to read this" overlay

**Problem solved:** The argument graph (pyvis interactive network) is opaque to first-time users.
They see colored nodes and labeled arrows but don't know: what a node represents, what an arrow
means, which direction to follow arrows, or what to look for.

**How it works:** A collapsible `st.expander()` is added at the top of the Argument Map
sub-tab content section (after the graph is confirmed to exist, above the graph HTML component).
It defaults to `expanded=True` so first-time users see it immediately; they can collapse it.

**Files changed:** `app.py` only.

---

**Prompt 5:**

```
In app.py, add a "How to read this map" collapsible explainer to the Argument Map sub-tab.

Step 1 — Add these new LABELS entries in the "── Argument Map ──" section (around line 244),
after the existing "legend_undercuts" entry:

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

Step 2 — In the Argument Map sub-tab (`with subtab_map:`), find the `else:` block after
`if not responses:` (around line 2112). The `else:` block currently starts with the two
`st.checkbox` calls for graph layer toggles (lines 2114–2118). Insert the following as the
VERY FIRST thing inside the `else:` block, before the checkboxes:

    with st.expander(L("map_how_to_expander"), expanded=True):
        st.markdown(L("map_how_to_nodes"))
        st.markdown(L("map_how_to_arrows"))
        st.markdown(L("map_how_to_labels"))
        st.markdown(L("map_how_to_patterns"))

Do not change any other code. The expander always defaults to expanded=True;
users can collapse it themselves.
```

---

## Change 6 — Claims table column header tooltips

**Problem solved:** The claims table has columns named "Type", "Checkable", and "Verdict" — all
of which mean specific things in this system that are not obvious from the label alone. Users
have to guess what they mean or read the docs.

**How it works:** The HTML table path (which renders when verdicts are present, around line 1594)
builds column headers as a list of strings. Wrapping the ambiguous headers in
`<abbr title="...">` gives browser-native hover tooltips with a dotted-underline hint.
This approach requires no JavaScript.

The plain `st.dataframe` path (rendered when no verdicts yet, around line 1680) cannot use
`<abbr>` directly, so a brief `st.caption()` with a summary of the column meanings is added
below the dataframe instead.

**Files changed:** `app.py` only.

---

**Prompt 6:**

```
In app.py, add hover tooltips to the ambiguous column headers in the claims table.

Step 1 — Add these new LABELS entries in the "── Analysis tab ──" section
(around line 103, near the existing col_* entries):

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

Step 2 — In the HTML table path (inside `if verdicts:` around line 1593), find the `hdrs` list
(around line 1596–1599):

    hdrs = [
        L("col_thread"), L("col_speaker"), L("col_time"),
        L("col_type"), L("col_checkable"), L("col_verdict"), L("col_claim"),
    ]

Replace it with:

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

Note: define `_abbr` as a local function inside the `if verdicts:` block, not at module level.

Step 3 — In the plain `st.dataframe` path (inside the `else:` branch after the `if verdicts:`
block, ending around line 1683), add a caption below the `st.dataframe(...)` call:

    st.caption(L("col_headers_note"))

Do not change any other code.
```

---

## Change 7 — Argument Map relationship legend: add meanings

**Problem solved:** The existing Argument Map legend (around lines 2139–2204) shows what color
each relationship type is, but doesn't explain what each relationship type *means*. Users see
"━ directly contradicts" but don't know that *refutes* denies the conclusion while *undercuts*
challenges the evidence behind it — a distinction that matters for reading the map.

**Decision: Option A — full refactor** (confirmed). All edge label strings are moved into
LABELS entries and meaning descriptions are added as part of the same pass. This fixes the
existing inconsistency where `L("legend_undercuts")` used the bilingual system while every
other edge label was hardcoded English.

---

**Prompt 7:**

```
In app.py, refactor the Argument Map edge legend to use bilingual LABELS entries,
and extend it to include a one-line meaning for each relationship type.

Step 1 — Add these new LABELS entries in the "── Argument Map ──" section
(around line 244, after the existing legend_* entries):

    "legend_refutes":  {"English": "directly denies the conclusion",        "Español": "niega directamente la conclusión"},
    "legend_supports": {"English": "agrees with or extends the claim",      "Español": "apoya o amplía la afirmación"},
    "legend_weakens":  {"English": "accepts but reduces scope",             "Español": "acepta pero reduce el alcance"},
    "legend_concedes": {"English": "acknowledges the other side has a point","Español": "reconoce que el otro lado tiene razón"},
    "legend_reframes": {"English": "same facts, different meaning",         "Español": "mismos hechos, distinto significado"},
    "legend_evades":   {"English": "changes subject without responding",    "Español": "cambia de tema sin responder"},
    "legend_ignores":  {"English": "makes an unrelated new point",          "Español": "introduce un punto no relacionado"},

Step 2 — In the Argument Map sub-tab, find the `edge_legend` variable construction
(currently around lines 2157–2164). Replace the entire `edge_legend = (...)` assignment with:

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

Do not change the survivability legend, shape legend, or node-color legend.
Do not change any other code.
```

---

## Change 8 — Graph node and edge hover tooltips

**Problem solved:** When a user hovers over a node in the argument graph, they currently see
`"Speaker A · [claim text]"` — just the speaker name and raw text. When they hover over an edge,
they see `"refutes: [one-sentence explanation]"`. Neither tooltip includes the claim type,
whether the claim is checkable, the fact-check verdict (if available), or a plain-English
description of what the relationship type means.

**How it works:** `truth_checker/visualizer.py` is modified to (a) accept an optional `verdicts`
parameter and (b) build richer `title=` strings for nodes and edges.
`app.py` is updated to pass `verdicts` when calling `build_graph_html()`.

**Decision: Option A — new parameter** (confirmed). `verdicts: dict | None = None` is added
to `build_graph_html()`'s signature, consistent with how `survivability` was already added as
a separate optional dict parameter. Keeps the call site explicit about what data the graph uses.

---

**Prompt 8:**

```
Implement richer hover tooltips for nodes and edges in the argument graph.

This change touches two files: truth_checker/visualizer.py and app.py.

─── Changes to truth_checker/visualizer.py ───────────────────────────────────────

Step 1 — Add a relationship description dict near the top of the file,
after the existing _SURV_BORDER dict (after line 41):

    _REL_DESCRIPTIONS = {
        "refutes":   "directly denies the conclusion",
        "undercuts": "challenges the evidence/reasoning (not the conclusion itself)",
        "supports":  "agrees with or adds evidence for the claim",
        "weakens":   "accepts but reduces the scope of the claim",
        "concedes":  "acknowledges the other speaker has a point",
        "reframes":  "accepts the facts but changes their interpretation",
        "evades":    "changes subject without addressing the claim",
        "ignores":   "makes an unrelated new point",
    }

Step 2 — Change the signature of build_graph_html() (line 44) to accept an optional verdicts
parameter:

    def build_graph_html(
        claims: list[dict],
        responses: list[dict],
        speaker_names: dict,
        survivability: dict[str, str] | None = None,
        show_premises: bool = True,
        show_reasoning_targets: bool = False,
        verdicts: dict | None = None,
    ) -> str:

Step 3 — Replace the node title construction (line 90) with a richer version that includes
claim type, checkable status, survivability status, and verdict (when available).
Find `title = f"{name} · {text}"` and replace it with:

    claim_type   = claim.get("claim_type", "")
    checkable    = "checkable" if claim.get("checkable") else "not checkable"
    surv_status  = (survivability or {}).get(cid, "")
    surv_labels  = {
        "grounded":   "survived all counterarguments",
        "contested":  "challenged",
        "unattacked": "unchallenged",
    }
    surv_note    = surv_labels.get(surv_status, "")
    vdict        = (verdicts or {}).get(cid, {})
    verdict_str  = vdict.get("verdict", "")
    verdict_conf = int(vdict.get("confidence", 0) * 100)
    verdict_note = f"{verdict_str} ({verdict_conf}% confidence)" if verdict_str else ""

    title_parts = [f"{name}", f"{text}", f"Type: {claim_type} · {checkable}"]
    if surv_note:
        title_parts.append(f"Status: {surv_note}")
    if verdict_note:
        title_parts.append(f"Verdict: {verdict_note}")
    title = "\n".join(title_parts)

Step 4 — Improve the edge title for the non-undercut case.
Find the line `title=f"{rel}: {explanation}"` (around line 184) and replace it with:

    desc  = _REL_DESCRIPTIONS.get(rel, "")
    title = f"{rel}: {explanation}" + (f"\n\n({desc})" if desc else "")

Also update the undercut-via-proxy edge title (around line 175,
`title=f"challenges reasoning: {explanation}"`) to:

    title = f"undercuts: {explanation}\n\n({_REL_DESCRIPTIONS['undercuts']})"

─── Changes to app.py ────────────────────────────────────────────────────────────

Step 5 — In the Argument Map sub-tab in app.py, find the build_graph_html() call
(around lines 2120–2127) and add the verdicts keyword argument:

    graph_html = build_graph_html(
        analysis.get("claims", []),
        responses,
        speaker_names_an,
        survivability=st.session_state.get("survivability"),
        show_premises=show_premises_cb,
        show_reasoning_targets=show_rt_cb,
        verdicts=st.session_state.get("verdicts"),
    )

Do not change anything else in either file.
```

---

## Notes for all prompts

**Bilingual requirement:** Every prompt that adds user-visible text adds matching entries to the
`LABELS` dict with both `"English"` and `"Español"` values. All new text in `app.py` uses
`L("key")` — never hardcoded English strings for user-visible content.

**No layout changes:** All changes are additive. No existing UI elements are moved or removed.

**Test after each change:** Run `streamlit run app.py` and confirm the change renders correctly
in both English and Español before marking it complete in the status table above.
