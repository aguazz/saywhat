# In-App UX Recommendations

Concrete guidance for making SayWhat's debate-analysis system understandable to first-time users. Each item specifies location, the confusion it resolves, and what was done (or should be done).

For the conceptual background behind each recommendation, see [how-it-works.md](how-it-works.md).

---

## Implemented

### Help Tour (Prompts A–D) ✓

Six interactive `st.dialog` modals explaining the analysis system, accessible from two surfaces:

- **Inline `→` links** in the analysis tab empty state (all 6), below the claims table filters (`→ what are claims?` · `→ what are threads?`), beside the Detect Responses button, in the Argument Map legend area, in the Rhetorical Profile tab, and above each speaker's metrics in the Speaker Report.
- **Sidebar Help panel** — a permanent `📖 Help` expander in the sidebar listing all 6 topics, reachable from anywhere in the app.

All dialogs live in `truth_checker/help_dialogs.py`. Each is bilingual, short, and contains a compact table plus one concrete example. The analysis tab empty state was refactored from `st.info(markdown_string)` to a `st.container(border=True)` layout with per-row `→` buttons.

---

### Original 8 essential items

All eight items below are live in `app.py` (and `truth_checker/visualizer.py` for item 5).

---

### 1. Verdict badge color legend ✓

**Location:** Claims tab, above the claims table. Also in the Fact-Check tab, below the summary metrics.

**Confusion solved:** Users see colored verdict badges but have no way to know what the colors mean without clicking through every badge.

**What was done:** A single-line HTML color swatch legend is rendered whenever verdicts are present. Uses the same badge colors and bilingual label strings as the badges themselves (`verdict_legend_label` LABELS key). Appears in both the Claims sub-tab (inside `if verdicts:`, before the table) and the Fact-Check sub-tab (after the four summary metrics, before the disclaimer).

---

### 2. Column header tooltips on the claims table ✓

**Location:** Claims table column headers — "Type", "Checkable", "Verdict".

**Confusion solved:** These column names mean specific things in this system. Without tooltips, users guess.

**What was done:** In the HTML table path (active when verdicts are present), the three ambiguous headers are wrapped in `<abbr title="..." style="cursor:help;text-decoration:underline dotted #888">` elements, giving browser-native hover tooltips. Tooltip text is bilingual via LABELS (`col_type_help`, `col_checkable_help`, `col_verdict_help`). In the plain `st.dataframe` path (before fact-check runs), a `st.caption(L("col_headers_note"))` line below the table provides a plain-text column key.

---

### 3. Argument Map "How to read this" overlay ✓

**Location:** Argument Map sub-tab, as the first element inside the `else:` block (shown whenever responses have been detected).

**Confusion solved:** A graph of colored nodes and labeled arrows is opaque to first-time users. Many don't know what a node or arrow represents.

**What was done:** A `st.expander(L("map_how_to_expander"), expanded=True)` block is inserted before the graph layer-toggle checkboxes. It contains four bilingual markdown sections explaining: what nodes are, what arrows are and which direction they point, what each arrow label means (with definitions for all 6 relationship types), and what patterns to look for (contested vs. unchallenged claims). Users can collapse it. It always defaults to open.

---

### 4. Argument Map relationship legend — with meanings ✓

**Location:** Argument Map sub-tab, below the graph (the existing legend block).

**Confusion solved:** The original legend showed which color corresponds to which relationship type but gave no indication of what each relationship *means*. Users saw "━ directly contradicts" but not what that signifies.

**What was done:** The `edge_legend` variable was refactored from hardcoded English strings to full f-string f-literals using `L()` throughout (fixing a pre-existing bilingual inconsistency). Each relationship now renders as: colored bar + **bold name** + `— plain-English meaning` in muted small text. Seven new LABELS entries added (`legend_refutes`, `legend_supports`, `legend_weakens`, `legend_concedes`, `legend_reframes`, `legend_evades`, `legend_ignores`). The existing `legend_undercuts` entry was already bilingual and is reused.

---

### 5. Node and edge hover tooltips in the graph ✓

**Location:** Argument Map — each node and each edge in the pyvis graph.

**Confusion solved:** Hovering over a node previously showed only `"Speaker A · [claim text]"`. Hovering over an edge showed only `"refutes: [one sentence]"`. Neither included claim type, checkable status, verdict, or a plain-English definition of the relationship type.

**What was done:** `truth_checker/visualizer.py` was updated:
- `build_graph_html()` now accepts `verdicts: dict | None = None` as a new optional parameter, consistent with the existing `survivability` parameter.
- Node `title=` now shows: speaker name, full claim text, type + checkable status, argument survivability status (when available), and fact-check verdict with confidence (when available).
- A `_REL_DESCRIPTIONS` dict was added with plain-English definitions for all 8 relationship types.
- Edge `title=` now appends `\n\n(description)` after the existing `rel: explanation` text for the standard case. The undercut-via-proxy edge also uses the description.
- `app.py` updated to pass `verdicts=st.session_state.get("verdicts")` at the `build_graph_html()` call site.

---

### 6. Rhetorical Profile tab intro blurb ✓

**Location:** Rhetorical Profile sub-tab, as the first element in the content section (before stage timeline and per-speaker expanders).

**Confusion solved:** "Rhetorical Profile" is not self-explanatory. Many users don't know what a logical fallacy is, what rhetorical devices are, or that the two are different.

**What was done:** `st.info(L("rhetoric_intro"))` inserted as the first statement in the `else:` block (i.e., whenever rhetoric data is present). The `rhetoric_intro` LABELS entry contains three paragraphs in both English and Español: defining fallacies with examples, defining rhetorical devices as legitimate techniques, and explaining that the app only flags fallacies when a specific quote is available.

---

### 7. Speaker Report score explanations ✓

**Location:** Speaker Report sub-tab, as tooltips on the four metric labels (Reliability, Supported claims, Direct response rate, Logical fallacies).

**Confusion solved:** A reliability score of 0.64 is meaningless without knowing what it measures, what counts as "good," or what it explicitly does *not* measure.

**What was done:** The four `st.metric()` calls now pass `help=L("...")` parameters. Streamlit renders these as a ℹ icon next to each metric label; clicking reveals the tooltip text. Four new bilingual LABELS entries added (`help_reliability`, `help_factchecked`, `help_direct_resp`, `help_fallacies`). Each tooltip explains what the score measures and — critically — what it does not measure.

---

### 8. Claims tab empty state ✓

**Location:** Analysis tab, above the Run Analysis button, shown only when no analysis has been run yet.

**Confusion solved:** With only a button and a cost note visible, users don't know what the analysis will produce or whether it's worth running.

**What was done:** `st.info(...)` block inserted after the `if not anthropic_key:` warning and before the Run Analysis button columns, gated on `if not analysis:` so it disappears once analysis has run. Two new bilingual LABELS entries added (`analysis_empty_heading`, `analysis_empty_body`). The body lists six bullet points explaining what the analysis does: classifies claims, groups them into threads, maps responses, fact-checks, detects rhetoric, and scores speakers.

---

## Pending: Nice to Have

These improve the experience but are not blocking for launch.

---

### 9. "What is a claim?" inline explainer

**Location:** Claims tab, just above the claims table (collapsed `st.expander`).

**Confusion solved:** "Claim" is a technical term here. Users may wonder what qualifies — does a question count? Does an opinion count?

**Proposed copy (inside a collapsed expander titled "What counts as a claim?"):**

> A **claim** is a statement about the world that can be agreed or disagreed with. It could be a fact, a statistic, a prediction, a comparison, or a value judgment.
>
> The app skips questions, jokes, filler words, pleasantries, and statements that don't assert anything. It keeps the substantive assertions — the things one speaker is actually putting forward as true.
>
> Not every claim can be fact-checked. Moral claims ("we *should* do X") and pure opinions aren't verifiable against evidence — they're value judgments. The app labels these *subjective* and doesn't count them for or against the speaker's reliability score.

**Implementation:** `st.expander("What counts as a claim?", expanded=False)` with static markdown. No logic required.

---

### 10. Grounded/Contested/Unattacked status explanation

**Location:** Claims table — tooltip on the survivability dot (●/○) in the Claim column, or as part of the claim detail expander.

**Confusion solved:** The colored dot already appears in the claims table (green ● = grounded, orange ● = contested, grey ○ = unattacked) but the `title=` HTML tooltip text is already populated via `_SURV_ICON`. A dedicated explanation of what these statuses mean is not surfaced anywhere prominent.

**Proposed addition:** An `st.expander("What do the coloured dots mean?", expanded=False)` near the top of the Claims sub-tab, or a short note in `st.caption()` below the table, pointing to the three statuses and linking to `docs/how-it-works.md`.

---

### 11. Example debate loader

**Location:** Analysis tab empty state (when transcript is loaded but analysis hasn't run).

**Confusion solved:** First-time users may not have a debate ready. An example lets them explore the full output immediately with no friction.

**Proposed implementation:** A `[Try an example debate]` button in the empty state block. Loads a pre-stored transcript and pre-computed analysis (no API calls). The analysis JSON can be shipped with the app and loaded via the existing `load_analysis_json` path.

**What the example should be:** A 5–8 minute excerpt of a public debate on a low-controversy topic. The Alex/Sam car-ban debate from `docs/how-it-works.md` is a natural candidate.

**Priority for public launch:** High. A working example is the single most effective first-impression improvement.

---

### 12. Thread filter on the claims table

**Location:** Claims table — additional filter dropdown alongside the existing Speaker and Type filters.

**Confusion solved:** When there are 60+ claims, it's hard to follow any single topic. Users want to zoom into "the economic debate" or "the air quality debate" without scrolling.

**Proposed interaction:** Dropdown: `Show thread: [All] | [Thread 1: air quality effects] | [Thread 2: economic impact] | ...`

Thread names come from `threader.py` (already in `analysis["threads"]`). Filtering is one line: `[c for c in filtered if c.get("thread_id") == selected_tid]`.

---

### 13. First-run walkthrough

**Location:** Phase 2 tab — shown only on first visit (tracked via `st.session_state`).

**Confusion solved:** A new user has no mental model of the four analysis tabs or the workflow order.

**Proposed flow (3 steps, dismissable):**

1. *"This is the Claims tab. After running analysis, it shows every claim in the debate with a type and fact-check verdict."*
2. *"The Argument Map shows how claims connect — who responded to whom, and how."*
3. *"The Speaker Report scores each speaker on accuracy and engagement."*

With a *Skip* button and a *Don't show again* checkbox (store in `st.session_state`).

---

## Progressive Disclosure Note

Several features involve concepts that are genuinely non-trivial (argument survivability, the refutes/undercuts distinction, the fallacy vs. device distinction). The implemented items follow a **progressive disclosure** pattern:

- Show the label first.
- Make the explanation available on hover, in a collapsible panel, or as a tooltip.
- Never force the explanation on users who already understand.

The pending items (9–13) deepen the explanation for users who want more context, or reduce friction for users encountering the app for the first time.
