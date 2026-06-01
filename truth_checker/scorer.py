def compute_speaker_scores(
    claims: list[dict],
    responses: list[dict],
    rhetoric: list[dict],
    threads: list[dict] | None = None,
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
        if claim.get("thread_id"):
            s.setdefault("_thread_ids", set()).add(claim["thread_id"])

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

        s["thread_engagement"] = None
        s["rebuttal_rate"]     = None

    # -- Thread engagement (requires threads list) ----------------------------
    n_threads = len(threads) if threads else 0
    if n_threads > 0:
        for sid, s in scores.items():
            contributed = len(s.get("_thread_ids", set()))
            s["thread_engagement"] = round(contributed / n_threads, 3)

    # -- Rebuttal rate (opponent claims responded to) -------------------------
    all_claim_ids   = {c["id"]: c.get("speaker", "") for c in claims}
    for sid, s in scores.items():
        opponent_ids = {cid for cid, spk in all_claim_ids.items() if spk != sid}
        if not opponent_ids:
            continue
        rebuttled = {
            r["responds_to_claim_id"]
            for r in responses
            if (r.get("from_speaker") == sid
                and r.get("responds_to_claim_id") in opponent_ids)
        }
        s["rebuttal_rate"] = round(len(rebuttled) / len(opponent_ids), 3)

    # -- Clean up internal tracking fields ------------------------------------
    for s in scores.values():
        s.pop("_thread_ids", None)

    return scores


def compute_debate_scores(
    claims: list[dict],
    responses: list[dict],
    stages: list[dict],
    threads: list[dict],
) -> dict:
    """Debate-level aggregate metrics derived from existing pipeline outputs."""
    if not claims:
        return {}

    n_claims    = len(claims)
    n_responses = len(responses)

    response_density = round(n_responses / n_claims, 3)

    evasion_rate: float | None = None
    if n_responses > 0:
        n_evasions   = sum(1 for r in responses if r.get("relationship") in ("evades", "ignores"))
        evasion_rate = round(n_evasions / n_responses, 3)

    dialectical_completeness = 0.0
    if stages:
        present = {s.get("dialectical_stage") for s in stages} - {None, ""}
        dialectical_completeness = round(len(present) / 4, 3)

    thread_coverage: float | None = None
    if len(threads) >= 2:
        covered = 0
        for thread in threads:
            tid      = thread.get("thread_id", "")
            speakers = {c.get("speaker") for c in claims if c.get("thread_id") == tid}
            if len(speakers) >= 2:
                covered += 1
        thread_coverage = round(covered / len(threads), 3)

    concession_count = sum(1 for r in responses if r.get("relationship") == "concedes")

    return {
        "response_density":         response_density,
        "evasion_rate":             evasion_rate,
        "dialectical_completeness": dialectical_completeness,
        "thread_coverage":          thread_coverage,
        "concession_count":         concession_count,
    }
