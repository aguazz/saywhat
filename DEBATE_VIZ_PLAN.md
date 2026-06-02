# Ultimate Debate Visualization — Design Plan

## Design decisions (confirmed with user)

| Question | Answer |
|----------|--------|
| "Purpose" field | AI-generated role sentence (Claude Haiku, cached) **+** stance on motion |
| Layout | Color toggle above timeline · Claim card in **right 40% panel** (60/40 split) |
| Map button | Keep inline mini-map **+** add "Open in full map" button |
| Tab strategy | **Redesign** existing Thread Timeline tab (no new tab) |

---

## 1. What changes

### 1.1 Color-coding toggle

A compact button group sits immediately above the timeline lanes:

```
[ ● Speakers ]  [ ● Stage ]  [ ● Claim type ]
```

Stored in `st.session_state["tl_color_mode"]` (default: `"speaker"`).
Switching the mode re-renders the timeline with a different color scheme; no
pipeline call is needed (all data is already available).

| Mode | Colors | Legend |
|------|--------|--------|
| Speakers | Existing `_SPK_COLORS` per speaker | Colored circles + speaker names |
| Stage | confrontation=#d62728, opening=#1f77b4, argumentation=#2ca02c, concluding=#9467bd | Colored squares + stage names |
| Claim type | factual/statistical/comparative=#1f77b4, causal/predictive=#ff7f0e, definitional/interpretive=#9467bd, moral/anecdotal=#d62728 | Colored squares + type names |

The color-mode parameter is threaded into `_build_thread_timeline()` so the function can map each bar's color. Restatements keep their diagonal stripe overlay regardless of color mode.

### 1.2 60 / 40 split layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Thread Timeline  (60 %)        │  Claim Card  (40 %)           │
│                                 │                               │
│  [color toggle]                 │  [empty state hint when no    │
│  [legend]                       │   claim is selected]          │
│  ───────────────────────────    │                               │
│  [timeline lanes]               │  [card appears on click]      │
│  [thread scorecards expander]   │                               │
└─────────────────────────────────────────────────────────────────┘
```

The right panel is always rendered (60/40 via `st.columns([3, 2])`). When no
claim is selected it shows a short hint. When a claim is selected it shows
the full card. The selected claim bar in the timeline keeps the gold border
ring regardless of color mode.

### 1.3 Claim card (right panel)

Sections, each gated on data availability:

| # | Section | Data source | Notes |
|---|---------|-------------|-------|
| 1 | **Claim text** | `claim["text"]` | Full text, not truncated |
| 2 | **Speaker · Time · Thread** | claim fields | Metadata line |
| 3 | **Purpose** | `claim["stance"]` + `_get_claim_role()` | See §1.4 |
| 4 | **Type & status** | `claim_type`, `checkable`, `survivability` | Badges |
| 5 | **Fact-check** | `verdicts[id]` | Verdict badge + confidence + explanation + for/against + key source |
| 6 | **Fallacies** | `rhetoric[turn]` | Type label + quoted text + explanation |
| 7 | **Rhetorical devices** | `rhetoric[turn]` | Type label + quoted text |
| 8 | **Related claims** | `responses` | Responds to / Challenged by / Supported by with claim text |
| 9 | **Neighbourhood map** | `build_graph_html()` | Inline 250 px (narrower than full-width version) |
| 10 | **Open in full map** | session state flag | Button; see §1.5 |

*Turn-level scope note* for sections 6 and 7 (same caption added in the previous session).

### 1.4 "Purpose" field — AI role sentence + stance

**Stance** (no API call): `claim["stance"]` = `"pro"` / `"con"` / `"neutral"`.
Shown only when a motion is set. Uses existing ▲/▼ indicators.

**Role sentence** (Claude Haiku, lazy + cached):

- Called the first time a claim is selected and not yet in cache.
- Cached in `st.session_state["claim_roles"][claim_id]`.
- While loading: `st.caption("…")` spinner-style placeholder.
- Prompt (user message):

```
Claim: "{text}"
Speaker: {name}
Thread: {thread_topic}
Type: {claim_type}
Connected to {N} other claims.

Describe in one short phrase (12 words max) the argumentative role
this claim plays in the debate. Examples: "Establishes the speaker's
opening position on diet", "Directly rebuts the opponent's data claim",
"Introduces a new causal mechanism to explain the effect".
Respond in the same language as the claim.
```

- Model: `claude-haiku-4-5-20251001`, `max_tokens=60`.
- New module-level function: `_get_claim_role(claim, thread_topic, n_connections, api_key) -> str`.

### 1.5 "Open in full map" button

When clicked:
1. Sets `st.session_state["map_focus_ids"]` = `{sel_id} ∪ neighbour_ids`.
2. Triggers `st.rerun()`.

The Argument Map sub-tab checks for `map_focus_ids` on each render:
- If present, uses them as `highlighted_ids` (non-matching nodes fade).
- Shows a caption: "Showing neighbourhood of 1 claim · clear".
- A "✕ Clear focus" button removes `map_focus_ids` from session state.

This reuses the existing `highlighted_ids` mechanism in `build_graph_html()`
without changing `visualizer.py`.

---

## 2. What stays the same

- `_build_thread_timeline()` function signature extended with `color_mode` parameter but otherwise unchanged in structure.
- Thread scorecards expander (Prompt 2) stays, moves to left column.
- Restatement diagonal stripes and restatement legend.
- Click listener (`st_javascript` + versioned key) is unchanged.
- All existing LABELS.
- The claim card built in Prompts 1A/1B is **replaced** by the right-panel card (not duplicated).

---

## 3. New data required

| Field | Where it comes from | Available without new pipeline step? |
|-------|-------------------|--------------------------------------|
| `claim["stance"]` | extractor.py (already there) | ✓ yes |
| `claim["claim_type"]` | classifier.py (already there) | ✓ yes |
| `dialectical_stage` | stage_labeler.py (already there) | ✓ yes (in `stages` list) |
| Role sentence | Claude Haiku, lazy per-claim | needs new function call |

The only new API call is the role sentence, fired lazily on first click.

---

## 4. Implementation prompts

All prompts target `app.py` only unless otherwise stated. Complete each in order; each is self-contained.

---

### Prompt A — Color-coding toggle + updated timeline ✓

Update `_build_thread_timeline()` to accept a `color_mode: str = "speaker"` parameter.
Derive bar color based on mode:
- `"speaker"`: existing `spk_color` dict (unchanged)
- `"stage"`: look up `claim["dialectical_stage"]` via the `stages` session-state list; use `_STAGE_COLORS`
- `"type"`: map `claim["claim_type"]` to a color group using `_TYPE_COLOR_MAP`

Define `_TYPE_COLOR_MAP` at module level (near `_STAGE_COLORS`):
```python
_TYPE_COLOR_MAP = {
    "factual":      "#1f77b4",
    "statistical":  "#1f77b4",
    "comparative":  "#1f77b4",
    "causal":       "#ff7f0e",
    "predictive":   "#ff7f0e",
    "definitional": "#9467bd",
    "interpretive": "#9467bd",
    "moral":        "#d62728",
    "anecdotal":    "#d62728",
}
```

In the Thread Timeline sub-tab:
1. Read `_tl_color_mode = st.session_state.get("tl_color_mode", "speaker")`.
2. Add toggle buttons above the legend:
   ```python
   _cm1, _cm2, _cm3, _ = st.columns([1,1,1,5])
   if _cm1.button("● Speakers", ...): st.session_state["tl_color_mode"] = "speaker"; st.rerun()
   if _cm2.button("● Stage",    ...): st.session_state["tl_color_mode"] = "stage";   st.rerun()
   if _cm3.button("● Type",     ...): st.session_state["tl_color_mode"] = "type";    st.rerun()
   ```
3. Update the legend to match the active mode.
4. Pass `color_mode=_tl_color_mode` to `_build_thread_timeline()`.

LABELS: `tl_color_speakers`, `tl_color_stage`, `tl_color_type`, `tl_color_label` (4 entries).

---

### Prompt B — 60/40 split: timeline left, card right ✓

Wrap the entire Thread Timeline content (toggle, legend, visualization, scorecards) in a
`st.columns([3, 2])` split. Left column takes everything currently in the sub-tab. Right
column is a new `st.container(border=True)` for the claim card.

Move the existing claim card code from its current "below-timeline" position into the
right column. Add an empty-state hint in the right column when `_sel_cid` is empty:
```
Click any block in the timeline to see the full claim details here.
```

Reduce mini-map height from 320 px to 250 px (narrower column).

LABELS: `card_empty_hint` (1 entry).

---

### Prompt C — "Purpose" section: role sentence + stance ✓

Add module-level function:
```python
def _get_claim_role(claim: dict, thread_topic: str, n_connections: int, api_key: str) -> str:
```

- Calls `claude-haiku-4-5-20251001`, `max_tokens=60`.
- Returns a single sentence (12 words max) describing the claim's argumentative role.
- Cache key: `st.session_state.setdefault("claim_roles", {})[claim_id]`.

In the claim card (right panel), after the metadata line (Speaker · Time · Thread):
1. Show stance badge (▲ pro / ▼ con / neutral) if motion is set.
2. Show role sentence from cache, or call `_get_claim_role()` and cache it.
   - While loading: `st.caption(L("card_role_loading"))`.

LABELS: `card_purpose`, `card_role_loading`, `card_stance_label` (3 entries).

---

### Prompt D — "Open in full map" button ✓

In the claim card, after the inline mini-map, add:
```python
if st.button(L("card_open_in_map"), key=f"open_map_{sel_id}"):
    _nb_ids = {sel_id} | neighbour_ids   # reuse _nb_ids already computed for mini-map
    st.session_state["map_focus_ids"] = _nb_ids
    st.rerun()
```

In the Argument Map sub-tab, at the top of the content block:
1. Check `_map_focus = st.session_state.get("map_focus_ids")`.
2. If set, use `_map_focus` as `highlighted_ids` (overrides the filter-derived `_hi_ids`).
3. Show caption: "Showing neighbourhood · " + `[✕ Clear]` button that removes `map_focus_ids`.

The tab-switching is handled by the user: after clicking the button, the page reruns and
the user sees the updated map. A visible "You've been redirected from Timeline" caption
in the Argument Map tells them where to look.

LABELS: `card_open_in_map`, `map_focus_caption`, `map_focus_clear` (3 entries).

---

### Prompt E — Documentation update ◻

Update `docs/ux-recommendations.md`:
- Add "Ultimate Debate Visualization (Prompts A–D) ✓" section.

Update `README.md`:
- Update Thread Timeline bullet point to describe the color toggle + right-panel card.

---

## 5. Open questions (deferred — decide later)

- **Other metrics in the card**: No specific requests yet. Candidates: qualifier strength
  (how hedged the claim is), claim word count, how many threads the claim touches, in-degree
  and out-degree in the argument graph.
- **Keyboard navigation**: Arrow keys to move between claims in the timeline. Deferred.
- **Card export**: "Copy card as Markdown" button. Deferred.
