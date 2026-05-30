import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

# ── System prompts ────────────────────────────────────────────────────────────

_SINGLE_SYSTEM = (
    "You are an argument analyst. Determine whether the current claim is a direct "
    "response to any of the listed prior claims.\n"
    "Relationship types: refutes (presents counter-evidence or reasoning), "
    "undercuts (argues that the evidence or reasoning does not support the conclusion, "
    "even if the conclusion might still be true), "
    "supports (agrees or extends), weakens (qualifies or reduces strength), "
    "reframes (accepts fact, changes interpretation), concedes (acknowledges "
    "the other is at least partly right), evades (changes subject), ignores (no link).\n"
    "Distinguish carefully: use \"refutes\" when the response denies the conclusion itself. "
    "Use \"undercuts\" when the response argues that the cited evidence or reasoning does "
    "not support the conclusion, even if the conclusion might still be true.\n"
    "Return a JSON object:\n"
    '{"is_response": bool, "responds_to_claim_id": str|null, '
    '"relationship": str|null, "explanation": str}'
)

_BATCH_SYSTEM = (
    "You are an argument analyst. For each numbered Current Claim below, determine "
    "whether it is a direct response to any of its listed Prior Claims.\n"
    "Relationship types: refutes / undercuts / supports / weakens / reframes / concedes / evades / ignores.\n"
    "Distinguish carefully: use \"refutes\" when the response denies the conclusion itself. "
    "Use \"undercuts\" when the response argues that the cited evidence or reasoning does "
    "not support the conclusion, even if the conclusion might still be true.\n"
    "Return a JSON array with EXACTLY one object per Current Claim, in the same order:\n"
    '[{"is_response": bool, "responds_to_claim_id": str|null, '
    '"relationship": str|null, "explanation": str}, ...]'
)

_VALID_RELATIONSHIPS = {
    "refutes", "undercuts", "supports", "weakens", "reframes", "concedes", "evades", "ignores",
}

_MAX_PRIOR = 8


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_single(raw: str) -> dict:
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _parse_batch(raw: str, expected: int) -> list[dict]:
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    items = json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("expected a JSON array")
    if len(items) != expected:
        raise ValueError(f"expected {expected} items, got {len(items)}")
    return items


def _build_edge(claim: dict, data: dict, claim_ids: set) -> dict | None:
    if not data.get("is_response"):
        return None
    responds_to = data.get("responds_to_claim_id")
    relationship = data.get("relationship") or "ignores"
    if responds_to not in claim_ids:
        logger.warning("Claim %s: responds_to_claim_id %r not in known claims.", claim["id"], responds_to)
        return None
    if relationship not in _VALID_RELATIONSHIPS:
        relationship = "ignores"
    return {
        "id":                   f"resp_{claim['id']}",
        "from_claim_id":        claim["id"],
        "responds_to_claim_id": responds_to,
        "from_speaker":         claim["speaker"],
        "relationship":         relationship,
        "explanation":          str(data.get("explanation", "")),
        "start_ms":             claim.get("start_ms", 0),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def detect_responses(
    claims: list[dict],
    api_key: str,
    on_progress=None,
    model: str = "claude-sonnet-4-6",
    batch_size: int = 1,
) -> list[dict]:
    """
    Detect cross-speaker response relationships between claims.

    Parameters
    ----------
    model       : Claude model ID — Haiku is ~12× cheaper, Sonnet is higher quality.
    batch_size  : How many claims to evaluate in a single API call.
                  1 = original behaviour (one call per claim).
                  3–10 = batched mode (fewer calls, lower cost, slight quality trade-off).
    on_progress : optional callable(i: int, total: int) — fires after every claim.
    """
    if len(claims) < 2:
        return []

    ordered   = sorted(claims, key=lambda c: c.get("start_ms", 0))
    client    = anthropic.Anthropic(api_key=api_key)
    claim_ids = {c["id"] for c in ordered}
    total     = len(ordered) - 1
    edges: list[dict] = []

    # Pre-compute (claim, prior_other) pairs — skip claims with no cross-speaker prior
    pairs: list[tuple[dict, list[dict]]] = []
    for idx in range(1, len(ordered)):
        claim = ordered[idx]
        prior_other = [c for c in ordered[:idx] if c["speaker"] != claim["speaker"]][-_MAX_PRIOR:]
        pairs.append((claim, prior_other))   # keep even if empty — counted for progress

    if batch_size <= 1:
        _run_single(pairs, client, model, claim_ids, edges, on_progress, total)
    else:
        _run_batched(pairs, client, model, claim_ids, edges, on_progress, total, batch_size)

    return edges


# ── Single-claim mode (original behaviour) ────────────────────────────────────

def _run_single(pairs, client, model, claim_ids, edges, on_progress, total):
    for idx, (claim, prior_other) in enumerate(pairs, start=1):
        try:
            if not prior_other:
                continue

            prior_lines = "\n".join(
                f"{i + 1}. [ID: {c['id']}] Speaker {c['speaker']}: {c['text']}"
                for i, c in enumerate(prior_other)
            )
            user_msg = (
                f"Current claim (Speaker {claim['speaker']}): {claim['text']}\n\n"
                f"Prior claims:\n{prior_lines}"
            )

            raw = ""
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=256,
                    system=_SINGLE_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                )
                raw = response.content[0].text.strip()
            except Exception as exc:
                logger.warning("API error on claim %s: %s", claim["id"], exc)
                continue
            finally:
                time.sleep(0.5)

            try:
                data = _parse_single(raw)
            except Exception as exc:
                logger.warning("Parse error on claim %s: %s — raw: %.120s", claim["id"], exc, raw)
                continue

            edge = _build_edge(claim, data, claim_ids)
            if edge:
                edges.append(edge)

        finally:
            if on_progress:
                on_progress(idx, total)


# ── Batched mode ──────────────────────────────────────────────────────────────

def _run_batched(pairs, client, model, claim_ids, edges, on_progress, total, batch_size):
    for batch_start in range(0, len(pairs), batch_size):
        batch = pairs[batch_start : batch_start + batch_size]

        # Only send claims that actually have prior other-speaker claims
        active = [(claim, prior) for claim, prior in batch if prior]

        if active:
            sections = []
            for i, (claim, prior) in enumerate(active):
                prior_lines = "\n".join(
                    f"  {j + 1}. [ID: {c['id']}] Speaker {c['speaker']}: {c['text']}"
                    for j, c in enumerate(prior)
                )
                sections.append(
                    f"Current Claim [{i + 1}]\n"
                    f"ID: {claim['id']} | Speaker {claim['speaker']}: {claim['text']}\n"
                    f"Prior claims to consider:\n{prior_lines}"
                )
            user_msg = "\n\n---\n\n".join(sections)

            raw = ""
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=max(256, 300 * len(active)),
                    system=_BATCH_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                )
                raw = response.content[0].text.strip()
                items = _parse_batch(raw, len(active))
                for (claim, _), data in zip(active, items):
                    edge = _build_edge(claim, data, claim_ids)
                    if edge:
                        edges.append(edge)
            except Exception as exc:
                logger.warning(
                    "Batch API/parse error (claims %d–%d): %s — falling back to skip.",
                    batch_start, batch_start + len(batch) - 1, exc,
                )
            finally:
                time.sleep(0.5)

        # Fire progress for every claim in the batch (including skipped ones)
        if on_progress:
            for k in range(len(batch)):
                on_progress(batch_start + k + 1, total)
