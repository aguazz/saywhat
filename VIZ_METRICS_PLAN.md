# Visualization & Metrics Redesign Plan

---

## 1. Current Visualizations

| View | Tab | What it shows | Key limitation |
|------|-----|---------------|----------------|
| **Thread Timeline** | Thread Timeline | Horizontal lanes per thread; claims as colored bars at their timestamp; speaker-color coded; selectbox-driven claim selection; basic text detail card below | Claim card is minimal — no type, no verdict, no stage, no connections, no rhetoric; no mini-map |
| **Argument Map** | Argument Map | pyvis interactive graph; nodes = claims (color = speaker, shape = type); edges = response relationships (color = rel type); node/edge fading when filter active | No temporal dimension; rhizomatic — hard to see narrative arc or who "won" threads |
| **Dialectical Stage Bar Chart** | Rhetorical Profile | Vertical stacked bars; count of speaker turns per stage (confrontation / opening / argumentation / concluding); speaker distinguished by CSS texture | Buried in Rhetorical Profile tab, disconnected from timeline |
| **Stage Timeline Chips** | Rhetorical Profile | `<details>/<summary>` chips per turn; stage color + claim preview + ⚠/✦ annotations | Also in Rhetorical Profile, not alongside the claims |
| **Verdict Distribution Bars** | Speaker Report | Horizontal bar chart per speaker; count of each verdict type | Not normalized; doesn't show thread-level picture |
| **Fact-Check Table** | Fact-Check | Expandable list of checkable claims with verdict, sources, feedback button | List view only; no cross-reference to timeline position |

---

## 2. Current Metrics

### Speaker-level (computed by `scorer.py`, shown in Speaker Report)

| Metric | Formula | Condition shown |
|--------|---------|-----------------|
| Reliability score | (true + partially_true) / checkable_claims | factcheck run |
| Supported claims | true + partially_true / checkable (count form) | factcheck run |
| Direct response rate | (responses − evasions) / responses | responses detected |
| Fallacy count | sum of fallacies across all turns | rhetoric run |
| Stance breakdown | pro / con / neutral claim counts | motion set |
| Survivability breakdown | grounded / contested / unattacked claim counts | responses detected |
| Dialectical stage breakdown | turn counts per stage | rhetoric / stages run |
| Restatement count | claims flagged as restatements | analysis run |

### Debate-level

**None.** No aggregate cross-speaker metrics exist. Users see two separate speaker cards but no head-to-head comparison or overall debate quality signal.

---

## 3. Problems with the Current Experience

1. **No whole-debate-at-a-glance view.** The argument map is rigorous but spatially crowded and time-blind. The thread timeline is closest, but its claim detail is bare.
2. **Thread Timeline claim card is minimal.** Selecting a claim shows speaker, timestamp, thread name, and other claims in the same thread — nothing else. No type, no verdict, no stage, no connections, no rhetoric.
3. **No mini argument map.** There is no way to zoom into one claim and see its argument neighbourhood without going to the full graph and filtering there.
4. **Metrics ignore threads.** Reliability and direct-response rate are debate-wide aggregates. A speaker who crushed one thread but ignored two others looks the same as one who engaged evenly.
5. **No debate-quality signal.** There is no single place that answers "was this a good debate?" — e.g., how much real engagement happened, how many threads got resolved, how dialectically complete the exchange was.
6. **Motion is underused.** The "Debate motion" input gates stance labels but isn't wired to any meaningful summary of whether the motion was successfully argued.
7. **Stage chart is stranded.** The dialectical stage bars live in the Rhetorical Profile tab, far from the Thread Timeline where temporal context would make them informative.

---

## 4. Proposed Visualization Improvement: Enriched Claim Card

The thread timeline already has the right structure. The improvement is purely in what happens when a claim is selected.

### Current claim card (lines 2676–2715 in app.py)

- Claim text (blockquote)
- Speaker · Timestamp · Thread
- List of other claims in the same thread

### Proposed claim card

A bordered `st.container` with up to 8 sections, each shown only when the data is available:

**Header row**
- Claim text (full, not truncated)
- Badge: claim type · checkable status

**Metadata row** (inline, muted small text)
- Speaker name · Timestamp · Thread name · Dialectical stage (if stages run)

**Verdict section** (if factcheck run and claim is checkable)
- Verdict badge + confidence %
- One-sentence AI summary (for/against the claim)
- Key source link

**Connections section** (if responses detected)
- "Responds to N claims · Challenged by M claims · Supported by K claims"
- Bullet list of directly connected claim texts (truncated)

**Rhetoric section** (if rhetoric run)
- Fallacies: names + quoted text
- Devices: names + quoted text

**Argument status** (if responses detected)
- Survivability dot + label: grounded / contested / unattacked

**Mini argument map button** (if responses detected)
- `[Show neighbourhood map]` button
- Renders an inline pyvis graph showing only: selected claim + claims it responds to + claims that respond to it
- ~300px tall, no physics controls, stable layout

**Thread context expander**
- Other claims in the same thread, in turn order (already exists, keep as-is)

### Implementation notes
- All sections behind `if data_available` guards — card degrades gracefully before each pipeline step runs.
- Stage lookup: iterate `st.session_state["stages"]` to find the turn containing this claim's `start_ms`, read its `dialectical_stage`.
- Rhetoric lookup: iterate `st.session_state["rhetoric"]` for fallacies/devices that cite this claim's text.
- Mini map: filter `claims` list to `{sel_id} ∪ connected_ids`; pass to `build_graph_html()` with `highlighted_ids=None`; render with `components.html(html, height=320)`.

---

## 5. Proposed New Metrics

### 5a. Debate-level (new — no equivalent exists)

| Metric | What it measures | Data needed |
|--------|-----------------|-------------|
| **Engagement rate** | % of each speaker's turns that directly respond to something the other said | `responses` |
| **Response density** | Average number of direct responses per claim across the whole debate | `responses`, `claims` |
| **Dialectical completeness** | How many of the 4 stages appeared (0–4) | `stages` |
| **Thread coverage** | % of threads where both speakers contributed at least one claim | `claims`, `threads` |
| **Evasion rate** | % of responses that are `evades` or `ignores` (debate-wide) | `responses` |

Display location: a new top row in the **Speaker Report** tab above the per-speaker cards, or a dedicated "Debate Summary" section.

### 5b. Thread-level (new)

| Metric | What it measures | Data needed |
|--------|-----------------|-------------|
| **Thread depth** | Total claim count in thread | `claims` |
| **Speaker balance** | % of thread claims per speaker | `claims` |
| **Survival ratio** | % of thread claims that are grounded (not contested) | `survivability`, `claims` |
| **Verdict ratio** | % of checkable thread claims with a conclusive verdict (true/false/misleading) | `verdicts`, `claims` |
| **Response density** | Response edges between claims within the same thread | `responses`, `claims` |

Display location: collapsed `st.expander` per thread in the Thread Timeline sub-tab, above or below the timeline visual. Or a "Thread Scorecard" table.

### 5c. Speaker-level additions

| Metric | What it measures | Notes |
|--------|-----------------|-------|
| **Thread engagement** | # of threads the speaker contributed to / total threads | Already computable from `claims` |
| **Argument depth** | Average length of response chains this speaker initiated | Requires traversal of response graph |
| **Pro-claim ratio** | % of own claims that are pro-motion (when motion set) | Already have stance labels |
| **Rebuttal rate** | % of opponent's claims that received a direct response from this speaker | `responses`, `claims` |

### 5d. Motion-driven metrics (when motion set)

| Metric | What it measures |
|--------|-----------------|
| **Pro coverage** | How many threads contained pro-motion arguments (from either speaker) |
| **Con coverage** | Same for con-motion arguments |
| **Concession count** | How many `concedes` response edges exist (signals real progress) |

---

## 6. Implementation Plan

### Phase 1 — Claim card enrichment (highest impact, no new pipeline)

**Files changed:** `app.py` only (section lines ~2676–2715)

1. Replace the current minimal card with the structured card described in §4.
2. Build stage lookup helper (3-line function: find turn by ms range → read stage).
3. Build rhetoric lookup helper (scan `rhetoric` session state for fallacies/devices citing this claim).
4. Build connections summary helper (scan `responses` for `from_claim_id == sel_id` and `responds_to_claim_id == sel_id`).
5. Add mini-map button + inline `build_graph_html()` call.
6. Add 8–10 bilingual LABELS entries.

Effort: medium. No backend changes.

### Phase 2 — Thread scorecards (thread-level metrics)

**Files changed:** `app.py` (Thread Timeline section)

1. Compute thread metrics from existing session state when thread section renders.
2. Add a collapsed expander per thread (or a summary table above the visualization).
3. No new LABELS needed beyond thread metric names.

Effort: small-medium. All data already in session state.

### Phase 3 — Debate-level summary metrics

**Files changed:** `app.py` (Speaker Report tab, new top section), `truth_checker/scorer.py` (new debate-level function)

1. Add `compute_debate_scores(claims, responses, stages, threads)` function in `scorer.py`.
2. Store result in `st.session_state["debate_score"]` at the Speaker Report button click.
3. Show in a 4–5 column metric row at the top of the Speaker Report tab.

Effort: medium.

### Phase 4 — Speaker-level additions + motion metrics

**Files changed:** `truth_checker/scorer.py`, `app.py` (Speaker Report rendering)

1. Add rebuttal rate and thread engagement to `compute_speaker_scores()`.
2. Add motion-driven metrics when `st.session_state["motion"]` is set.

Effort: small.

---

## 7. Decisions

**D1 — Mini-map click target: keep dropdown**
Bars stay click-free. Claim selection continues via the dropdown (`st.selectbox`). The enriched card makes the dropdown worthwhile.

**D2 — Thread scorecards: collapsed expander per thread in the Thread Timeline sub-tab**
No new tab. A `st.expander` per thread (collapsed by default) keeps everything on one screen.

**D3 — Debate-level metrics: persistent banner between buttons and sub-tabs**
A compact 4–5 metric row inserted between the run-buttons row and the analysis sub-tabs. Always visible once analysis has run; gives the "at a glance" signal before users dive into individual tabs.

**D4 — Motion surfacing: show as heading/caption**
Show the motion text as a caption at the top of the Speaker Report and Thread Timeline when set. Pro/con counts fold into the existing stance breakdown below it. No new dedicated section.

**D5 — Scope: Phase 1 first, then review**
Implement Phase 1 (enriched claim card) as a standalone deliverable. Review before starting Phases 2–4.

---

## 8. Implementation Prompts

Seven sequential prompts. Each is self-contained and paste-ready. Complete and verify one before starting the next.

Status legend: ◻ pending · ✓ done

---

### Prompt 1A — Enriched claim card (metadata + verdict + connections + rhetoric) ✓

```
In app.py, replace the minimal claim detail section in `subtab_timeline` (currently lines ~2676–2715, the block starting at `if _sel_cid:`) with a structured claim card.

The card should be a `st.container(border=True)` with the following sections, each gated on data availability:

1. **Claim text** — full text (not truncated) as a blockquote. Below it: a single metadata line with speaker name · timestamp · thread name · dialectical stage (if stages available in session state). To get the stage: iterate `st.session_state.get("stages", [])` and find the turn whose `start_ms` ≤ claim's `start_ms` and `end_ms` (or start_ms + some buffer) ≥ claim's `start_ms`, and read `dialectical_stage`. Fall back to "" if not found.

2. **Type & status badges** — one line: claim type + checkable badge (inline, small caps or colored span) + survivability dot+label (grounded/contested/unattacked) from `st.session_state.get("survivability", {})`.

3. **Verdict section** — shown only when `st.session_state.get("verdicts")` is non-empty and the claim is checkable. Show: verdict badge (same HTML badge style used elsewhere in the Claims tab) + confidence % + one-sentence summary (the `summary` field from the verdict dict, which contains the for/against summary). If `key_source` exists, show it as a small link or caption.

4. **Connections section** — shown only when `st.session_state.get("responses")` is non-empty. Compute:
   - `responds_to`: list of claims where `resp["from_claim_id"] == sel_id` (this claim responds to those)
   - `challenged_by`: list of claims where `resp["responds_to_claim_id"] == sel_id` and `resp["relationship"]` in ("refutes", "undercuts", "weakens")
   - `supported_by`: list of claims where `resp["responds_to_claim_id"] == sel_id` and `resp["relationship"]` in ("supports", "concedes")
   Show as: "Responds to N · Challenged by M · Supported by K" in a single caption line. Then for each non-empty list, a bullet showing the connected claim speaker + text[:70].

5. **Rhetoric section** — shown only when `st.session_state.get("rhetoric")` is non-empty. Scan the rhetoric list for the entry whose `speaker == sel_c["speaker"]` and whose turn overlaps the claim's timestamp. Show fallacies (if any) and rhetorical devices (if any) as small labelled bullet lists. If neither found, omit this section entirely.

6. **Thread context expander** — keep the existing "Other claims in this thread (N)" expander exactly as it is.

Add ~10 bilingual LABELS entries for the card section headings (card_stage, card_type, card_verdict_section, card_connections, card_responds_to, card_challenged_by, card_supported_by, card_rhetoric, card_fallacies, card_devices). Bilingual (English + Español). Style consistently with the existing cards in the app.

Do not change `_build_thread_timeline()` or any other function. Only change the claim-detail rendering block in `subtab_timeline`.
```

---

### Prompt 1B — Mini neighbourhood map in the Thread Timeline ✓

```
In app.py, inside the enriched claim card built in Prompt 1A, add a "Show neighbourhood map" section after the Connections section and before the Thread context expander.

The section should be a toggle button (label: L("card_show_minimap") / L("card_hide_minimap")) that sets st.session_state[f"minimap_open_{sel_id}"] to True/False. Bilingual LABELS: "card_show_minimap", "card_hide_minimap".

When the toggle is open:
1. Build a set of neighbour IDs from responses in session state: all claim IDs directly connected to `sel_id` (either as `from_claim_id` or `responds_to_claim_id`).
2. Filter `_tl_claims` to only claims in `{sel_id} | neighbour_ids`.
3. Filter `responses_ss` (from `st.session_state.get("responses", [])`) to only edges where both endpoints are in that filtered set.
4. Call `build_graph_html(filtered_claims, filtered_responses, speaker_names_an, survivability=st.session_state.get("survivability"), verdicts=st.session_state.get("verdicts"))`. Do NOT pass `highlighted_ids` — all nodes in the mini-map should appear at full opacity.
5. Render with `components.html(mini_html, height=320, scrolling=False)`.

If `responses_ss` is empty or the claim has no neighbours, show `st.caption(L("card_no_connections"))` instead of the button. Add that LABELS entry too.

No changes to `build_graph_html()` or `visualizer.py` — the existing signature already handles this.
```

---

### Prompt 2 — Thread scorecards in the Thread Timeline sub-tab ✓

```
In app.py, in the Thread Timeline sub-tab (`with subtab_timeline:`), add a collapsed per-thread scorecard section that appears above the `st.caption(L("timeline_hint"))` line.

For each thread in `_tl_threads`, compute (from existing session state — no new pipeline calls):
- `depth`: total claims in thread (count from `_tl_claims` filtered to this `thread_id`)
- `per_speaker`: dict of speaker_id → claim count within thread
- `survival_ratio`: % of thread claims whose survivability is "grounded" — only computed when `st.session_state.get("survivability")` is non-empty, else None
- `verdict_ratio`: % of checkable thread claims with a conclusive verdict (true / partially_true / false / contested / misleading) — only when `st.session_state.get("verdicts")` is non-empty, else None
- `response_count`: count of response edges where both `from_claim_id` and `responds_to_claim_id` belong to this thread — only when `st.session_state.get("responses")` is non-empty, else None

Render as a `st.expander(thread_topic, expanded=False)` for each thread, inside a `st.expander(L("thread_scorecard_heading"), expanded=False)` outer wrapper (so the whole section is a single collapsible block, not one expander per thread at top level).

Inside each thread expander:
- A row of `st.metric()` calls: Depth (always), Speaker balance (always — e.g. "Alex 60% · Sam 40%"), Survival rate (when available), Verdict rate (when available), Response edges (when available).

Add ~6 bilingual LABELS entries: thread_scorecard_heading, thread_depth, thread_balance, thread_survival, thread_verdict_rate, thread_responses.
```

---

### Prompt 3A — compute_debate_scores() in scorer.py ✓

```
In truth_checker/scorer.py, add a new top-level function:

def compute_debate_scores(
    claims: list[dict],
    responses: list[dict],
    stages: list[dict],
    threads: list[dict],
) -> dict:

It should compute and return a flat dict with these keys:

- "response_density": float — (total response edges) / (total claims). 0.0 if no claims.
- "evasion_rate": float — responses whose relationship is "evades" or "ignores" / total responses. None if no responses.
- "dialectical_completeness": float — count of distinct stages present in `stages` list / 4. 0.0 if no stages.
- "thread_coverage": float — % of threads where ≥2 distinct speakers contributed at least one claim. None if fewer than 2 threads.
- "concession_count": int — total responses whose relationship is "concedes" across the whole debate.

All values should be rounded to 3 decimal places where float. Return an empty dict if claims is empty.

No imports needed beyond what's already in scorer.py. No changes to compute_speaker_scores().
```

---

### Prompt 3B — Debate scorecard banner in app.py ✓

```
In app.py, make these two changes:

1. At the Speaker Report button click handler (where `compute_speaker_scores()` is called and the result stored in `st.session_state["speaker_report"]`), also call:
   from truth_checker.scorer import compute_debate_scores
   st.session_state["debate_score"] = compute_debate_scores(
       claims=analysis.get("claims", []),
       responses=st.session_state.get("responses", []),
       stages=st.session_state.get("stages", []),
       threads=analysis.get("threads", []),
   )

2. Between the run-buttons row (the st.columns block that contains Run Analysis, Download PDF, Download JSON) and the `st.tabs([...])` call that opens the six analysis sub-tabs, insert a debate scorecard banner:

   _ds = st.session_state.get("debate_score")
   if _ds:
       ds1, ds2, ds3, ds4, ds5 = st.columns(5)
       ds1.metric(L("ds_response_density"),    f'{_ds.get("response_density", 0):.1f}',  help=L("ds_response_density_help"))
       ds2.metric(L("ds_evasion_rate"),         f'{_ds.get("evasion_rate", 0):.0%}' if _ds.get("evasion_rate") is not None else L("metric_na"), help=L("ds_evasion_rate_help"))
       ds3.metric(L("ds_completeness"),         f'{_ds.get("dialectical_completeness", 0):.0%}', help=L("ds_completeness_help"))
       ds4.metric(L("ds_thread_coverage"),      f'{_ds.get("thread_coverage", 0):.0%}' if _ds.get("thread_coverage") is not None else L("metric_na"), help=L("ds_thread_coverage_help"))
       ds5.metric(L("ds_concessions"),          str(_ds.get("concession_count", 0)),     help=L("ds_concessions_help"))

Add 10 bilingual LABELS entries: the 5 metric names and 5 help strings explaining what each measures. Help text should follow the same plain-language style as the existing help_reliability / help_direct_resp entries.
```

---

### Prompt 4A — Speaker-level additions: rebuttal rate and thread engagement ✓

```
In truth_checker/scorer.py, add two new fields to `compute_speaker_scores()`. Both need access to the full claims list and threads list. Update the function signature to:

def compute_speaker_scores(
    claims: list[dict],
    responses: list[dict],
    rhetoric: list[dict],
    threads: list[dict] | None = None,
) -> dict:

After the existing derived-ratios block, add:

- "thread_engagement": float — count of distinct thread_ids in this speaker's claims / total thread count (from threads list). None if threads is empty or None.
- "rebuttal_rate": float — for each speaker S, count opponent claims that received at least one response whose `from_speaker == S` (i.e. the speaker directly responded to an opponent claim), divided by total opponent claims. None if there are no opponent claims. "Opponent claims" = all claims not belonging to speaker S.

Also add "thread_ids_contributed": set[str] — not shown to users, just used by the debate scorecard. Actually, skip this — the two rates are enough.

In app.py, update the `compute_speaker_scores()` call site to pass `threads=analysis.get("threads", [])`.

In the Speaker Report sub-tab rendering, add two new `st.metric()` calls for each speaker:
- `mc5.metric(L("metric_thread_engagement"), ...)` — formatted as % if not None, else L("metric_na"), with help=L("help_thread_engagement")
- `mc6.metric(L("metric_rebuttal_rate"), ...)` — same pattern

Expand the columns from `mc1, mc2, mc3, mc4 = st.columns(4)` to 6 columns. Add 4 bilingual LABELS entries: metric_thread_engagement, metric_rebuttal_rate, help_thread_engagement, help_rebuttal_rate.
```

---

### Prompt 4B — Motion surfacing in Thread Timeline and Speaker Report ✓

```
In app.py, make these two small additions:

1. In the Thread Timeline sub-tab (`with subtab_timeline:`), at the very top of the non-empty branch (just after the `if not _tl_threads: st.info(...)` block ends and the content starts), add:
   _motion_tl = st.session_state.get("motion", "").strip()
   if _motion_tl:
       st.caption(L("motion_caption").format(motion=_motion_tl))

2. In the Speaker Report sub-tab (`with subtab_report:`), at the top of the content branch (just before the `for idx, sid in sorted(speaker_report.keys()):` loop), add the same two lines with a different variable name:
   _motion_sr = st.session_state.get("motion", "").strip()
   if _motion_sr:
       st.caption(L("motion_caption").format(motion=_motion_sr))

Add one bilingual LABELS entry:
  "motion_caption": {
    "English": "Motion: *{motion}*",
    "Español": "Moción: *{motion}*"
  }

No other changes. The existing per-speaker stance breakdown (pro/con/neutral) is already gated on the motion being set — it will naturally appear below this caption for each speaker.
```
