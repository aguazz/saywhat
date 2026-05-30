import json

from pyvis.network import Network

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
    "refutes":  "#d62728",
    "supports": "#2ca02c",
    "weakens":  "#ff7f0e",
    "concedes": "#ff7f0e",
    "reframes": "#9467bd",
    "evades":   "#aaaaaa",
    "ignores":  "#aaaaaa",
}


def build_graph_html(
    claims: list[dict],
    responses: list[dict],
    speaker_names: dict,
) -> str:
    """
    Build an interactive pyvis argument graph and return it as an HTML string.

    Nodes represent claims (colored by speaker, shaped by claim type).
    Edges represent response relationships (colored by relationship type).
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
        color = speaker_color.get(spk, _SPEAKER_COLORS[0])
        shape = _SHAPE_MAP.get(claim.get("claim_type", ""), "dot")
        size  = 20 if claim.get("checkable") else 14
        title = f"<b>{name}</b><br>{text}"

        net.add_node(cid, label=label, title=title, color=color, shape=shape, size=size)
        known_ids.add(cid)

    for resp in responses:
        from_id = resp.get("responds_to_claim_id")
        to_id   = resp.get("from_claim_id")

        if from_id not in known_ids or to_id not in known_ids:
            continue

        rel   = resp.get("relationship", "ignores")
        color = _EDGE_COLORS.get(rel, "#aaaaaa")
        title = f"{rel}: {resp.get('explanation', '')}"

        net.add_edge(
            from_id,
            to_id,
            color={"color": color, "highlight": color},
            title=title,
            arrows="to",
        )

    net.set_options(json.dumps({
        "physics": {
            "solver": "forceAtlas2Based",
        }
    }))

    return net.generate_html()
