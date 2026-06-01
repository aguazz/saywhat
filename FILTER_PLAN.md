# Find / Filter Claims — Implementation Plan

---

## Status

| # | Prompt | Files | Status |
|---|--------|-------|--------|
| A | LABELS + `apply_filters()` helper + derived attribute maps | `app.py` | ✓ Done |
| B | Replace 2-filter block with full filter panel + chips | `app.py` | ✓ Done |
| C | Argument Map: fade non-matching nodes/edges | `app.py`, `truth_checker/visualizer.py` | ✓ Done |
| D | Thread Timeline: dim non-matching claim blocks | `app.py` | ☐ Pending |

---

## Resolved Decisions

| Question | Answer |
|----------|--------|
| Graph: hide vs fade | **Fade** — non-matching nodes grey out; full graph structure stays visible |
| Connection count filter | **v1** — included alongside the other enrichment filters |

---

## Current State

The Claims sub-tab has exactly two filters: speaker (dropdown) and claim type (dropdown). They
produce `filtered` → `sorted_claims` feeding the table, CSV export, and verdict expanders.
They do not affect the Argument Map or Thread Timeline.

All claim attributes are in `analysis["claims"]`. Enrichment data (verdicts, survivability,
rhetoric, responses) lives in separate session state keys, joined by claim ID or `start_ms`.

---

## Assumptions

1. **AND logic** — all active filters must match simultaneously.
2. **Filter state** stored in `st.session_state["claim_filter"]` (dict), persists across sub-tab
   switches.
3. **Graph behavior** — non-matching nodes turn `#e0e0e0` (light grey), small size; matching
   nodes keep full speaker color. Non-matching edges also turn grey. Preserves argument
   structure as context while highlighting filtered claims.
4. **Timeline behavior** — non-matching claim blocks dim to `opacity: 0.12`. Entire thread rows
   with no matching claims also dim.
5. **Enrichment filters** (verdict, survivability, fallacy, device, connections, stance) rendered
   only when their source data exists in session state.
6. **Connection count** derived at render time from the `responses` list.
7. **No saved presets** in v1.
8. **Language** — all new UI strings go in LABELS (bilingual).

---

## Filter definitions

### v1 — included

| Filter | Control | Source | Condition |
|--------|---------|--------|-----------|
| Speaker | Dropdown | `claim["speaker"]` | Always |
| Claim type | Dropdown | `claim["claim_type"]` | Always |
| Thread | Dropdown | `claim["thread_id"]` | Always |
| Text search | Text input | `claim["text"]` | Always |
| Verdict | Multi-select | `verdicts[id]["verdict"]` | `verdicts` populated |
| Argument status | Dropdown | `survivability[id]` | `survivability` populated |
| Has fallacy | Dropdown | derived from `rhetoric` | `rhetoric` populated |
| Has device | Dropdown | derived from `rhetoric` | `rhetoric` populated |
| Connections | Dropdown | derived from `responses` | `responses` populated |
| Checkable | Dropdown | `claim["checkable"]` | Always |
| Certainty | Dropdown | `claim["qualifier"]` | Always |
| Stance | Dropdown | `claim["stance"]` | `motion` non-empty |

### v2 — deferred

Specific fallacy type · specific device type · time range slider ·
"claims that attack claim X" · save/load filter presets.

---

## Graph and Timeline Behaviour

### Argument Map — Fade

`build_graph_html()` gains `highlighted_ids: set[str] | None = None`.
When set and a claim is **not** in `highlighted_ids`:
- Node color → `#e0e0e0`, size → 10.
- Every edge touching that node → color `#e0e0e0`, width 1.

Matching claims keep full speaker color and normal size.
A caption above the graph reads `"Showing N of M claims · filter active"`.

### Thread Timeline — Dim

`_build_thread_timeline()` gains `highlighted_ids: set[str] | None = None`.
When set, claim blocks not in `highlighted_ids` render at `opacity: 0.12`.
Thread rows where **no** claim matches also render at `opacity: 0.12`.

---

## New LABELS entries

```python
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
```

---

## Prompt A — LABELS + `apply_filters()` + derived attribute maps

### Step 1 — Add LABELS entries

Add the entries from the table above into the LABELS dict in `app.py`, after the existing
`"filter_all"` entry (around line 196).

### Step 2 — Add `apply_filters()` before `main()`

Insert this module-level pure function immediately before `def main() -> None:` in `app.py`:

```python
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
```

### Step 3 — Add derived attribute computation in the Claims sub-tab

Inside `with subtab_claims:`, find the line `claims   = analysis.get("claims", [])`.
Just after the line `verdicts = st.session_state.get("verdicts", {})`, insert:

```python
                    # ── Derived filter attributes ──────────────────────────────
                    _rhet_ss_f  = st.session_state.get("rhetoric") or []
                    _resp_ss_f  = st.session_state.get("responses") or []
                    _surv_ss_f  = st.session_state.get("survivability", {})

                    # Map turn start_ms → rhetoric data
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

                    # Initialise filter state
                    if "claim_filter" not in st.session_state:
                        st.session_state["claim_filter"] = {}
```

Do not change any other code in this step. The derived maps are computed but not yet
used by the filter widgets (that happens in Prompt B).

---

## Prompt B — Replace 2-filter block with full filter panel

**Find** the existing block in the Claims sub-tab that starts with:

```python
                        # Filters
                        all_lbl   = L("filter_all")
                        spk_opts  = [all_lbl] + [
```

and ends with:

```python
                        sorted_claims = sorted(
                            filtered,
                            key=lambda c: (c.get("thread_id", ""), c.get("start_ms", 0)),
                        )
```

**Replace the entire block** with:

```python
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
                            _thr_ids   = [None] + [t["thread_id"] for t in threads]
                            _thr_disp  = {None: L("filter_all")} | {
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

                        # Row 2: more filters expander
                        with st.expander(L("filter_more"), expanded=False):
                            _mf_widgets: list = []  # (label_key, widget_value, cf_key, default)
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
                                    None: L("filter_any"),
                                    True: L("filter_yes"),
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
                                    None: L("filter_any"),
                                    True: L("filter_yes"),
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
                                _cn_opts  = [None, 1, 3, 0]
                                _cn_disp  = {
                                    None: L("filter_conn_any"),
                                    1:    L("filter_conn_1"),
                                    3:    L("filter_conn_3"),
                                    0:    L("filter_conn_0"),
                                }
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
                                None: L("filter_any"),
                                True: L("filter_yes"),
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
                            _ql_vals   = sorted({
                                c.get("qualifier", "") for c in claims
                                if c.get("qualifier")
                            })
                            if _ql_vals:
                                _ql_opts  = [None] + _ql_vals
                                _ql_disp  = LABELS["qualifier_labels"][lang]
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
                                    "pro": L("stance_pro"),
                                    "con": L("stance_con"),
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
```

---

## Prompt C — Argument Map: fade non-matching nodes/edges

### Step 1 — `truth_checker/visualizer.py`: add `highlighted_ids` parameter

**Change 1:** Update the function signature (after `verdicts`):

```python
def build_graph_html(
    claims: list[dict],
    responses: list[dict],
    speaker_names: dict,
    survivability: dict[str, str] | None = None,
    show_premises: bool = True,
    show_reasoning_targets: bool = False,
    verdicts: dict | None = None,
    highlighted_ids: set | None = None,
) -> str:
```

**Change 2:** In the node-building loop, replace:

```python
        node_color = (
            {"background": bg, "border": border_color} if border_color else bg
        )
```

with:

```python
        if highlighted_ids is not None and cid not in highlighted_ids:
            # Fade non-matching nodes to grey
            node_color = {"background": "#e0e0e0", "border": "#cccccc"}
            size       = 10
            border_width = 1
        else:
            node_color = (
                {"background": bg, "border": border_color} if border_color else bg
            )
```

**Change 3:** In the edge-building loop, for the standard (non-undercut) `net.add_edge` call,
replace:

```python
            color = _EDGE_COLORS.get(rel, "#aaaaaa")
            desc  = _REL_DESCRIPTIONS.get(rel, "")
            title = f"{rel}: {explanation}" + (f"\n\n({desc})" if desc else "")
            net.add_edge(
                from_id,
                to_id,
                color={"color": color, "highlight": color},
                title=title,
                arrows="to",
            )
```

with:

```python
            if (highlighted_ids is not None
                    and (from_id not in highlighted_ids
                         or to_id not in highlighted_ids)):
                color = "#e0e0e0"
            else:
                color = _EDGE_COLORS.get(rel, "#aaaaaa")
            desc  = _REL_DESCRIPTIONS.get(rel, "")
            title = f"{rel}: {explanation}" + (f"\n\n({desc})" if desc else "")
            net.add_edge(
                from_id,
                to_id,
                color={"color": color, "highlight": color},
                title=title,
                arrows="to",
            )
```

Apply the same fade logic to the undercut-via-proxy visible edge (the `net.add_edge` with
`title=f"undercuts: {explanation}..."`): check if both `to_id` and `from_id` are in
`highlighted_ids`, else use `"#e0e0e0"`.

### Step 2 — `app.py` Argument Map sub-tab

Find the `build_graph_html(...)` call and update it:

```python
                        _fc_all   = analysis.get("claims", [])
                        _fc_filt  = st.session_state.get("filtered_claims")
                        _fc_use   = _fc_filt if _fc_filt is not None else _fc_all
                        _hi_ids   = (
                            {c["id"] for c in _fc_use}
                            if _fc_filt is not None and len(_fc_filt) < len(_fc_all)
                            else None
                        )

                        graph_html = build_graph_html(
                            _fc_all,           # always pass ALL claims (faded, not hidden)
                            responses,
                            speaker_names_an,
                            survivability=st.session_state.get("survivability"),
                            show_premises=show_premises_cb,
                            show_reasoning_targets=show_rt_cb,
                            verdicts=st.session_state.get("verdicts"),
                            highlighted_ids=_hi_ids,
                        )
```

Also add a caption after `if graph_html:` to show the filter state:

```python
                        if _hi_ids is not None:
                            st.caption(
                                LABELS["graph_filter_caption"][lang].format(
                                    n=len(_fc_use), m=len(_fc_all)
                                )
                            )
```

---

## Prompt D — Thread Timeline: dim non-matching claim blocks

### Step 1 — `_build_thread_timeline()` function

Add `highlighted_ids: set | None = None` as the last parameter:

```python
def _build_thread_timeline(
    claims: list[dict],
    threads: list[dict],
    speaker_names: dict,
    selected_claim_id: str | None = None,
    highlighted_ids: set | None = None,
) -> str:
```

Inside the per-claim block rendering (the `for c in t_claims:` loop), update the
`row_opacity` logic. Currently `row_opacity` is set per thread row based on `focus_tid`.
After the existing opacity calculation, compute a per-claim opacity:

```python
            for c in t_claims:
                # ...existing position/color/styling variables...

                # Highlight: if highlighted_ids active and claim not in it → very faint
                if highlighted_ids is not None and c["id"] not in highlighted_ids:
                    bar_opacity = "0.12"
                # (the existing is_restat and is_sel logic already sets bar_opacity;
                #  the highlighted_ids check should OVERRIDE it when the claim doesn't match)
```

Also update the thread-row opacity to account for whether any claim in the row matches:

```python
        # Dim row if no claims match the highlight set
        if highlighted_ids is not None:
            _row_has_match = any(
                c["id"] in highlighted_ids for c in t_claims
            )
            row_opacity = "1" if _row_has_match else "0.12"
        else:
            row_opacity = "1" if (focus_tid is None or focus_tid == tid) else "0.25"
```

### Step 2 — Thread Timeline sub-tab call

Find `_tl_html = _build_thread_timeline(...)` and update:

```python
                        _tl_fc    = st.session_state.get("filtered_claims")
                        _tl_fc_all = analysis.get("claims", [])
                        _tl_hi    = (
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
```
