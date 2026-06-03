"""
Attribution resolver — synthesize asserting claims from affirmed challenges.

When Speaker A voices a claim with posture "challenging", "attributing", or
"questioning", and Speaker B responds with an "affirms" edge, B has adopted that
proposition as their own assertion.  This module creates a synthesized asserting
claim for B so that:

  - The claim is correctly attributed to B for scoring and display.
  - A's original claim keeps its posture and gains an "affirmed_by" back-reference.
  - The synthesized claim carries an "affirmed_from" forward-reference to A's claim.

Synthesized claims inherit all classifier fields from A's original claim but carry
B's turn identity (speaker, turn_index, start_ms, end_ms).  Fields that can only
be populated by the extractor from the actual speech (start_hint, premises,
warrant_hint, rebuttal_cond) are left null/empty.
"""

import logging

logger = logging.getLogger(__name__)

_NON_ASSERTING = {"challenging", "attributing", "questioning"}


def resolve_attributions(
    claims: list[dict],
    responses: list[dict],
) -> list[dict]:
    """
    For every non-asserting claim that has an "affirms" response edge from a
    different speaker, synthesize a new asserting claim for the affirming speaker.

    Parameters
    ----------
    claims    : Full list of claim dicts (with posture field populated).
    responses : Response-edge dicts produced by detect_responses().

    Returns
    -------
    Augmented claims list: originals first, synthesized claims appended.
    Original non-asserting claims that were affirmed gain an "affirmed_by" field.
    """
    # Index claims by id for O(1) look-up
    by_id: dict[str, dict] = {c["id"]: c for c in claims}

    new_claims: list[dict] = []

    for edge in responses:
        if edge.get("relationship") != "affirms":
            continue

        # B's claim (the one doing the affirming)
        affirming_claim = by_id.get(edge.get("from_claim_id"))
        # A's claim (the one being affirmed — must be non-asserting)
        target_claim = by_id.get(edge.get("responds_to_claim_id"))

        if not affirming_claim or not target_claim:
            continue
        if target_claim.get("posture", "asserting") not in _NON_ASSERTING:
            continue
        if affirming_claim.get("speaker") == target_claim.get("speaker"):
            continue  # same speaker — nothing to re-attribute

        synth_id = f"{affirming_claim['id']}_synth_{target_claim['id']}"
        if synth_id in by_id:
            continue  # already synthesized (idempotent)

        synth: dict = {
            # ── Identity (B's turn) ───────────────────────────────────────
            "id":          synth_id,
            "speaker":     affirming_claim["speaker"],
            "turn_index":  affirming_claim.get("turn_index"),
            "start_ms":    affirming_claim.get("start_ms"),
            "end_ms":      affirming_claim.get("end_ms"),
            # ── Content (inherited from A's original claim) ───────────────
            "text":        target_claim["text"],
            "posture":     "asserting",
            "attributed_to": None,
            # ── Classifier fields (inherited) ─────────────────────────────
            "claim_type":          target_claim.get("claim_type", "factual"),
            "checkable":           target_claim.get("checkable", False),
            "check_as_attributed": False,
            "evidence_quality":    target_claim.get("evidence_quality", "none"),
            "suggested_query":     target_claim.get("suggested_query"),
            "thread_id":           target_claim.get("thread_id"),
            "stance":              target_claim.get("stance", "neutral"),
            "qualifier":           target_claim.get("qualifier", "probable"),
            "satirical":           False,
            "restatement_of":      None,
            # ── Fields not extractable from B's affirming turn ────────────
            "start_hint":    None,
            "premises":      [],
            "warrant_hint":  None,
            "rebuttal_cond": None,
            # ── Cross-reference ───────────────────────────────────────────
            "affirmed_from": target_claim["id"],
        }

        # Mark the original so the UI can link back
        target_claim["affirmed_by"] = synth_id

        new_claims.append(synth)
        by_id[synth_id] = synth

        logger.debug(
            "Synthesized asserting claim %s for speaker %s (affirmed from %s)",
            synth_id,
            affirming_claim["speaker"],
            target_claim["id"],
        )

    if new_claims:
        logger.info(
            "resolve_attributions: synthesized %d asserting claim(s) from affirmed challenges.",
            len(new_claims),
        )

    return claims + new_claims
