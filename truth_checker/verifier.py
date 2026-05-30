import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a fact-checker writing for a general audience. "
    "Assess the claim below using only the provided evidence. "
    "Do not use outside knowledge. Write in plain language. "
    "Return a JSON object:\n"
    "- verdict: one of [true, partially_true, contested, misleading, false, unverifiable, subjective]\n"
    "- confidence: float 0.0-1.0 reflecting how strongly the evidence supports the verdict\n"
    "- explanation: 2-3 plain-language sentences explaining the verdict, citing specific evidence\n"
    "- for_the_claim: (only if verdict=contested) one sentence on what supports it, else ''\n"
    "- against_the_claim: (only if verdict=contested) one sentence on what contradicts it, else ''\n"
    "- key_source: title and URL of the most relevant source\n"
    "- all_sources: list of {title, url} for every source you used\n"
    "Do not fabricate sources. If evidence is insufficient return verdict=unverifiable."
)

_VALID_VERDICTS = {
    "true", "partially_true", "contested", "misleading",
    "false", "unverifiable", "subjective",
}

_NO_EVIDENCE = {
    "verdict":          "unverifiable",
    "confidence":       0.0,
    "explanation":      "No external evidence was found for this claim.",
    "for_the_claim":    "",
    "against_the_claim": "",
    "key_source":       "",
    "all_sources":      [],
}

_PARSE_FAILURE = {
    "verdict":          "unverifiable",
    "confidence":       0.0,
    "explanation":      "The fact-check could not be completed due to a parsing error.",
    "for_the_claim":    "",
    "against_the_claim": "",
    "key_source":       "",
    "all_sources":      [],
}


def _format_evidence(evidence: list[dict]) -> str:
    lines = []
    for i, item in enumerate(evidence, 1):
        lines.append(f"{i}. Title: {item.get('title', '')}\n   Excerpt: {item.get('snippet', '')}")
    return "\n\n".join(lines)


def verify_claim(claim: dict, evidence: list[dict], api_key: str) -> dict:
    """
    Assess a claim against retrieved evidence using Claude Sonnet.

    Returns a verdict dict with keys: verdict, confidence, explanation,
    for_the_claim, against_the_claim, key_source, all_sources, claim_id.
    Falls back to 'unverifiable' on any error or missing evidence.
    """
    if not evidence:
        return {**_NO_EVIDENCE, "claim_id": claim["id"]}

    formatted = _format_evidence(evidence)
    _warrant = claim.get("warrant_hint")
    _warrant_line = f"Stated inference: {_warrant}\n" if _warrant else ""
    user_msg  = (
        f"Claim: {claim['text']}\n"
        f"Speaker: {claim['speaker']}\n"
        f"{_warrant_line}"
        f"\nEvidence:\n{formatted}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error verifying claim %s: %s", claim.get("id"), exc)
        return {**_PARSE_FAILURE, "claim_id": claim["id"]}

    # Strip optional markdown code fence
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
        logger.warning("JSON parse error for claim %s: %s — raw: %.120s", claim.get("id"), exc, raw)
        return {**_PARSE_FAILURE, "claim_id": claim["id"]}

    # Coerce and validate fields
    verdict = data.get("verdict", "unverifiable")
    if verdict not in _VALID_VERDICTS:
        verdict = "unverifiable"

    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    # for_the_claim / against_the_claim only relevant for "contested"
    is_contested = verdict == "contested"

    return {
        "claim_id":         claim["id"],
        "verdict":          verdict,
        "confidence":       confidence,
        "explanation":      str(data.get("explanation", "")),
        "for_the_claim":    str(data.get("for_the_claim", ""))    if is_contested else "",
        "against_the_claim": str(data.get("against_the_claim", "")) if is_contested else "",
        "key_source":       data.get("key_source", ""),
        "all_sources":      data.get("all_sources", []) if isinstance(data.get("all_sources"), list) else [],
    }
