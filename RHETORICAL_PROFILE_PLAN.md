# Rhetorical Profile Redesign Plan

---

## Status

| # | Prompt | Files | Status |
|---|--------|-------|--------|
| A | Replace overview chart with grouped vertical bars | `app.py` | ✓ Done |
| B | Add type-breakdown expander (horizontal stacked by type) | `app.py` | ☐ Pending |
| C | Enrich stage timeline chips with rhetoric data | `app.py` | ☐ Pending |

---

## Resolved Decisions

| Question | Answer |
|----------|--------|
| "Other" grouping | Types appearing exactly once (count = 1) are grouped into an "Other" bucket |
| Chip rhetoric detail | `⚠ FallacyLabel — "short quote…"` and `✦ DeviceLabel — "short quote…"` |
| Type breakdown visibility | Collapsed `st.expander` — always accessible, not overwhelming |
| Bilingual type labels | English only for now |
| Per-speaker expanders | Kept as-is — remain the detailed reference layer |

---

## Current State (for reference)

The `_rh_chart_html` block (lines ~2787–2831 in `app.py`) builds one horizontal-bar section
per speaker with two bars (total fallacies | total devices). Type detail is buried in a small
text label listing the top-3 fallacy names. The per-speaker `st.expander` sections below
provide full quotes and explanations.

---

## Prompt A — Replace overview chart with grouped vertical bars

**What it does:**  
Replaces the existing `_rh_chart_html` horizontal block with a vertical grouped bar chart.
Two bars per speaker (Fallacies | Devices), side by side, in red and blue. Count label above
each bar. Speaker name below each group. Legend below the chart.

**File:** `app.py`

**Find and replace:** the entire block from  
`# ── Rhetorical profile overview chart ──────────────`  
through `st.divider()` (the divider immediately after `st.markdown(_rh_chart_html, ...)`)

**New code:**

```python
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
                                    f'<div title="{_spkn}: {_fv} {L(\"rhetoric_fallacies\").lower()}" '
                                    f'style="flex:1;height:{_fh}px;background:#d62728;'
                                    f'border-radius:4px 4px 0 0"></div>'
                                    f'<div title="{_spkn}: {_dv} {L(\"rhetoric_devices\").lower()}" '
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
```

---

## Prompt B — Add type-breakdown expander

**What it does:**  
Immediately after the `st.divider()` added by Prompt A (and before the `for sid in sorted(spk_rhetoric.keys()):` per-speaker expanders loop), insert a collapsed `st.expander` containing:
- **Fallacy types chart**: one horizontal bar per fallacy type, stacked by speaker (speaker colors). Types appearing exactly once are grouped into "Other".
- **Device types chart**: same structure for rhetorical device types.

**File:** `app.py`

**New LABELS entries** — add in the `"── Rhetorical Profile sub-tab ──"` section of LABELS, after `"rhetoric_footer"`:

```python
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
```

**New code (insert after `st.divider()` from Prompt A, before the per-speaker loop):**

```python
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
```

---

## Prompt C — Enrich stage timeline chips with rhetoric data

**What it does:**  
Before the chip-building loop in the Dialectical Stage Timeline, build a lookup from
`start_ms` to the rhetoric turn data. In each chip's expanded `<div>`, after the turn
text, show any fallacies and devices detected in that turn: `⚠ Label — "short quote"` /
`✦ Label — "short quote"`.

**File:** `app.py`

**Find:** the comment `# Build turn-text lookup: turn start_ms → full turn text` at the
start of the chip-building section.

**Insert before that comment:**

```python
                            # Build rhetoric lookup: turn start_ms → rhetoric data
                            _rhetoric_by_ms: dict[int, dict] = {}
                            _rhet_ss = st.session_state.get("rhetoric")
                            if _rhet_ss:
                                for _ritem in _rhet_ss:
                                    _rhetoric_by_ms[_ritem.get("start_ms", -1)] = _ritem
```

**Find the chip's expanded `<div>` string** (the `f'<div style="background:{_color}...'` block
inside `_boxes.append(...)`). Replace only the content of that div:

**Old:**
```python
                                    f'<div style="background:{_color};color:#fff;'
                                    f'border-radius:0 0 4px 4px;padding:6px 9px;'
                                    f'font-size:0.8em;line-height:1.45;max-width:300px;'
                                    f'white-space:normal;'
                                    f'box-shadow:0 3px 10px rgba(0,0,0,0.25)">'
                                    f'{_excerpt}</div>'
```

**New:**
```python
                                    # Build rhetoric annotation for this turn
                                    _rhet_item = _rhetoric_by_ms.get(_si.get("start_ms", 0), {})
                                    _rhet_lines = ""
                                    for _rf2 in _rhet_item.get("fallacies", []):
                                        _rl = _rf2.get("label") or _rf2.get("type", "")
                                        _rq = _rf2.get("quote", "")
                                        _rq_short = (_rq[:60] + "…") if len(_rq) > 60 else _rq
                                        if _rl:
                                            _rhet_lines += (
                                                f'<div style="margin-top:3px;opacity:0.92">'
                                                f'⚠ <strong>{_rl}</strong>'
                                                + (f' — <em>"{_rq_short}"</em>' if _rq_short else "")
                                                + f'</div>'
                                            )
                                    for _rd2 in _rhet_item.get("rhetorical_devices", []):
                                        if _rd2.get("is_fallacy", False):
                                            continue
                                        _rl = _rd2.get("label") or _rd2.get("type", "")
                                        _rq = _rd2.get("quote", "")
                                        _rq_short = (_rq[:60] + "…") if len(_rq) > 60 else _rq
                                        if _rl:
                                            _rhet_lines += (
                                                f'<div style="margin-top:3px;opacity:0.85">'
                                                f'✦ <strong>{_rl}</strong>'
                                                + (f' — <em>"{_rq_short}"</em>' if _rq_short else "")
                                                + f'</div>'
                                            )
                                    _sep = (
                                        '<hr style="border:none;border-top:1px solid '
                                        'rgba(255,255,255,0.3);margin:5px 0">'
                                        if _rhet_lines else ""
                                    )
                                    f'<div style="background:{_color};color:#fff;'
                                    f'border-radius:0 0 4px 4px;padding:6px 9px;'
                                    f'font-size:0.8em;line-height:1.45;max-width:300px;'
                                    f'white-space:normal;'
                                    f'box-shadow:0 3px 10px rgba(0,0,0,0.25)">'
                                    f'{_excerpt}{_sep}{_rhet_lines}</div>'
```

**Note:** `_rhet_ss` is read from session state inside the `if _stages:` block where `rhetoric`
may or may not be set. The lookup gracefully returns `{}` if rhetoric hasn't been run or if a
turn has no rhetoric data.

---

## Files Affected

| File | Change |
|------|--------|
| `app.py` LABELS | Add `rh_breakdown_expander`, `rh_fallacy_types_heading`, `rh_device_types_heading`, `rh_other` |
| `app.py` Rhetoric tab | Prompt A: replace overview chart · Prompt B: insert type breakdown expander |
| `app.py` Stage timeline | Prompt C: rhetoric lookup + chip enrichment |
| `docs/ux-recommendations.md` | Update once all prompts are implemented |
