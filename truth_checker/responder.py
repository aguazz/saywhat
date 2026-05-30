import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an argument analyst. Determine whether the current claim is a direct "
    "response to any of the listed prior claims.\n"
    "Relationship types: refutes (presents counter-evidence or reasoning), "
    "supports (agrees or extends), weakens (qualifies or reduces strength), "
    "reframes (accepts fact, changes interpretation), concedes (acknowledges "
    "the other is at least partly right), evades (changes subject), ignores (no link).\n"
    "Return a JSON object:\n"
    '{"is_response": bool, "responds_to_claim_id": str|null, '
    '"relationship": str|null, "explanation": str}'
)

_VALID_RELATIONSHIPS = {
    "refutes", "supports", "weakens", "reframes", "concedes", "evades", "ignores",
}

_MAX_PRIOR = 8


def detect_responses(
    claims: list[dict],
    api_key: str,
    on_progress=None,
) -> list[dict]:
    """
    Detect cross-speaker response relationships between claims.

    Processes claims in chronological order. For each claim, looks at the last
    _MAX_PRIOR prior claims from different speakers and asks Claude whether the
    current claim is a direct response to any of them.

    on_progress: optional callable(i: int, total: int) called after every claim,
    even skipped ones, so a progress bar stays accurate.

    Returns a list of response edge dicts (not the claims themselves).
    """
    if len(claims) < 2:
        return []

    # Ensure chronological order
    ordered  = sorted(claims, key=lambda c: c.get("start_ms", 0))
    client   = anthropic.Anthropic(api_key=api_key)
    claim_ids = {c["id"] for c in ordered}
    total    = len(ordered) - 1
    edges: list[dict] = []

    for idx, claim in enumerate(ordered[1:], start=1):
        try:
            # Collect last _MAX_PRIOR prior claims from different speakers
            prior_other = [
                c for c in ordered[:idx]
                if c["speaker"] != claim["speaker"]
            ][-_MAX_PRIOR:]

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
                    model="claude-sonnet-4-6",
                    max_tokens=256,
                    system=_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                )
                raw = response.content[0].text.strip()
            except Exception as exc:
                logger.warning("Claude API error on claim %s: %s", claim["id"], exc)
                continue
            finally:
                time.sleep(0.5)

            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("expected a JSON object")
            except Exception as exc:
                logger.warning("JSON parse error on claim %s: %s — raw: %.120s", claim["id"], exc, raw)
                continue

            if not data.get("is_response"):
                continue

            responds_to  = data.get("responds_to_claim_id")
            relationship = data.get("relationship")

            if responds_to not in claim_ids:
                logger.warning(
                    "Claim %s: responds_to_claim_id %r not in known claims — skipping edge.",
                    claim["id"], responds_to,
                )
                continue

            if relationship not in _VALID_RELATIONSHIPS:
                relationship = "ignores"

            edges.append({
                "id":                   f"resp_{claim['id']}",
                "from_claim_id":        claim["id"],
                "responds_to_claim_id": responds_to,
                "from_speaker":         claim["speaker"],
                "relationship":         relationship,
                "explanation":          str(data.get("explanation", "")),
                "start_ms":             claim.get("start_ms", 0),
            })

        finally:
            if on_progress:
                on_progress(idx, total)

    return edges
