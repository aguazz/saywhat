def compute_speaker_scores(
    claims: list[dict],
    responses: list[dict],
    rhetoric: list[dict],
) -> dict:
    """
    Aggregate per-speaker metrics from claims (with optional `verdict` field merged in),
    response edges, and rhetoric analysis results.
    Claims are expected to have a `verdict` key if fact-checking was run.
    """
    _VERDICT_KEYS = [
        "true", "partially_true", "contested",
        "misleading", "false", "unverifiable", "subjective",
    ]
    _EVIDENCE_KEYS = ["strong", "moderate", "weak", "none"]
    _EVASION_RELS  = {"evades", "ignores"}

    scores: dict = {}

    # -- Pass 1: claims --------------------------------------------------------
    for claim in claims:
        sid = claim.get("speaker", "")
        if sid not in scores:
            scores[sid] = {
                "total_claims":          0,
                "checkable_claims":      0,
                "verdicts":              {k: 0 for k in _VERDICT_KEYS},
                "evidence_quality":      {k: 0 for k in _EVIDENCE_KEYS},
                "reliability_score":     None,
                "total_responses_made":  0,
                "evasions":              0,
                "direct_response_rate":  None,
                "fallacy_count":         0,
                "fallacy_types":         [],
            }

        s = scores[sid]
        s["total_claims"] += 1

        verdict = claim.get("verdict", "")
        if verdict in s["verdicts"]:
            s["verdicts"][verdict] += 1

        if claim.get("checkable"):
            s["checkable_claims"] += 1

        eq = claim.get("evidence_quality", "none") or "none"
        if eq not in _EVIDENCE_KEYS:
            eq = "none"
        s["evidence_quality"][eq] += 1

    # -- Pass 2: responses -----------------------------------------------------
    for resp in responses:
        sid = resp.get("from_speaker", "")
        if sid not in scores:
            continue
        s = scores[sid]
        s["total_responses_made"] += 1
        if resp.get("relationship") in _EVASION_RELS:
            s["evasions"] += 1

    # -- Pass 3: rhetoric ------------------------------------------------------
    for rh in rhetoric:
        sid = rh.get("speaker", "")
        if sid not in scores:
            continue
        s = scores[sid]
        fallacies = rh.get("fallacies", [])
        s["fallacy_count"] += len(fallacies)
        for f in fallacies:
            ftype = f.get("type", "")
            if ftype and ftype not in s["fallacy_types"]:
                s["fallacy_types"].append(ftype)

    # -- Derived ratios --------------------------------------------------------
    for s in scores.values():
        checkable = s["checkable_claims"]
        if checkable > 0:
            accurate = s["verdicts"]["true"] + s["verdicts"]["partially_true"]
            s["reliability_score"] = round(accurate / checkable, 3)

        total_resp = s["total_responses_made"]
        if total_resp > 0:
            direct = total_resp - s["evasions"]
            s["direct_response_rate"] = round(direct / total_resp, 3)

    return scores
