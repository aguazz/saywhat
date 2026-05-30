import json

from pyvis.network import Network


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

_SPEAKER_COLORS = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

_SHAPE_MAP = {
    "factual":      "dot",
    "statistical":  "dot",
    "comparative":  "dot",
    "causal":       "diamond",
    "predictive":   "diamond",
    "definitional": "square",
    "interpretive": "square",
    "moral":        "triangle",
    "anecdotal":    "triangle",
}

_EDGE_COLORS = {
    "refutes":   "#d62728",  # red   — directly contradicts the conclusion
    "undercuts": "#e377c2",  # pink  — challenges the reasoning behind the conclusion
    "supports":  "#2ca02c",
    "weakens":   "#ff7f0e",
    "concedes":  "#ff7f0e",
    "reframes":  "#9467bd",
    "evades":    "#aaaaaa",
    "ignores":   "#aaaaaa",
}


_SURV_BORDER = {
    "grounded":   ("#2ca02c", 3),  # green, thick — survived all attacks
    "contested":  ("#ff7f0e", 2),  # orange, medium — has undefeated attackers
    "unattacked": (None,      1),  # default — no attacks received
}


def build_graph_html(
    claims: list[dict],
    responses: list[dict],
    speaker_names: dict,
    survivability: dict[str, str] | None = None,
    show_premises: bool = True,
    show_reasoning_targets: bool = False,
) -> str:
    """
    Build an interactive pyvis argument graph and return it as an HTML string.

    Nodes represent claims (colored by speaker, shaped by claim type).
    Edges represent response relationships (colored by relationship type).

    show_premises: when True, premise sub-nodes and their dashed support edges are
      rendered. When False, only claim nodes and response edges are shown.
    show_reasoning_targets: when True, "undercuts" edges are rendered via a small
      proxy diamond node placed on the attacked inference rather than pointing directly
      at the target claim node.
    survivability: optional dict[claim_id → "grounded"|"contested"|"unattacked"]
      from compute_grounded_extension(). Encodes survival status as node border.
    Returns an empty string if claims is empty.
    """
    if not claims:
        return ""

    net = Network(height="600px", width="100%", directed=True, bgcolor="#ffffff")

    # Assign a stable color to each unique speaker (sorted for determinism)
    speakers = sorted({c["speaker"] for c in claims})
    speaker_color = {
        spk: _SPEAKER_COLORS[i % len(_SPEAKER_COLORS)]
        for i, spk in enumerate(speakers)
    }

    known_ids: set[str] = set()

    for claim in claims:
        cid   = claim["id"]
        text  = claim.get("text", "")
        label = text[:40] + ("…" if len(text) > 40 else "")
        spk   = claim.get("speaker", "")
        name  = speaker_names.get(spk, f"Speaker {spk}")
        bg    = speaker_color.get(spk, _SPEAKER_COLORS[0])
        shape = _SHAPE_MAP.get(claim.get("claim_type", ""), "dot")
        size  = 20 if claim.get("checkable") else 14
        title = f"{name} · {text}"

        # Encode survivability as border width + color when available
        surv_status = (survivability or {}).get(cid, "unattacked")
        border_color, border_width = _SURV_BORDER.get(surv_status, (None, 1))
        node_color = (
            {"background": bg, "border": border_color} if border_color else bg
        )

        net.add_node(
            cid, label=label, title=title,
            color=node_color, shape=shape, size=size,
            borderWidth=border_width,
        )
        known_ids.add(cid)

        # Premise sub-nodes — only when the layer is enabled
        if show_premises:
            claim_short = text[:60] + ("…" if len(text) > 60 else "")
            for pi, prem_text in enumerate(claim.get("premises", [])):
                if not isinstance(prem_text, str) or not prem_text.strip():
                    continue
                prem_id    = f"prem_{cid}_{pi}"
                prem_label = prem_text[:35] + ("…" if len(prem_text) > 35 else "")
                net.add_node(
                    prem_id,
                    label=prem_label,
                    title=prem_text,
                    color="#cccccc",
                    shape="box",
                    size=10,
                    borderWidth=1,
                )
                prem_edge_color = _hex_to_rgba(bg, 0.6)
                net.add_edge(
                    prem_id,
                    cid,
                    color={"color": prem_edge_color, "highlight": prem_edge_color},
                    title=f"supports: {claim_short}",
                    arrows="to",
                    dashes=True,
                )

    for resp in responses:
        # from_id = the claim that was responded to (target T)
        # to_id   = the claim doing the responding (responder U)
        from_id = resp.get("responds_to_claim_id")
        to_id   = resp.get("from_claim_id")

        if from_id not in known_ids or to_id not in known_ids:
            continue

        rel         = resp.get("relationship", "ignores")
        explanation = resp.get("explanation", "")
        for sid, sname in speaker_names.items():
            explanation = explanation.replace(f"Speaker {sid}", sname)

        if rel == "undercuts" and show_reasoning_targets:
            # Place a small proxy diamond on the attacked inference.
            # T → proxy (invisible anchor) ; U → proxy (visible undercut arrow)
            proxy_id = f"proxy_{from_id}_{to_id}"
            net.add_node(
                proxy_id,
                label="",
                title="Inference point (reasoning challenged here)",
                color="#e377c2",
                shape="diamond",
                size=6,
                borderWidth=1,
            )
            # Invisible anchor edge from T to proxy — pulls proxy close to T
            _ghost = _hex_to_rgba("#e377c2", 0.12)
            net.add_edge(
                from_id,
                proxy_id,
                color={"color": _ghost, "highlight": _ghost},
                title="",
                arrows="",
            )
            # Visible undercut arrow from U to proxy
            _pink = "#e377c2"
            net.add_edge(
                to_id,
                proxy_id,
                color={"color": _pink, "highlight": _pink},
                title=f"challenges reasoning: {explanation}",
                arrows="to",
            )
        else:
            color = _EDGE_COLORS.get(rel, "#aaaaaa")
            net.add_edge(
                from_id,
                to_id,
                color={"color": color, "highlight": color},
                title=f"{rel}: {explanation}",
                arrows="to",
            )

    net.set_options(json.dumps({
        "physics": {
            "solver": "forceAtlas2Based",
        }
    }))

    return net.generate_html()
