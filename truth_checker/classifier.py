import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an argument analyst. Classify the claim below. "
    "The claim may be in Spanish or English — your labels must be in English regardless. "
    "Return a JSON object with these exact keys:\n"
    "- claim_type: one of [factual, statistical, causal, predictive, comparative, "
    "definitional, interpretive, moral, anecdotal]\n"
    "- checkable: true if verifiable against external data, false otherwise\n"
    "- evidence_in_speech: any data, statistic, or citation the speaker mentioned "
    "in support (empty string if none)\n"
    "- evidence_quality: one of [strong, moderate, weak, none] — "
    "strong=specific named source or statistic, moderate=general reference to research, "
    "weak=anecdote or vague reference, none=bare assertion\n"
    "- suggested_query: if checkable=true, a 6-10 word search query for fact-checking "
    "(write the query in English even if the claim is in Spanish); else empty string\n"
    "- satirical: true only if the claim is clearly a joke or hyperbole, else false"
)

_DEFAULTS = {
    "claim_type":        "factual",
    "checkable":         False,
    "evidence_in_speech": "",
    "evidence_quality":  "none",
    "suggested_query":   "",
    "satirical":         False,
}

_VALID_TYPES = {
    "factual", "statistical", "causal", "predictive", "comparative",
    "definitional", "interpretive", "moral", "anecdotal",
}
_VALID_QUALITY = {"strong", "moderate", "weak", "none"}


def classify_claim(claim: dict, api_key: str) -> dict:
    """
    Classify a claim dict using Claude Haiku.

    Adds claim_type, checkable, evidence_in_speech, evidence_quality,
    suggested_query, and satirical to the original claim dict and returns it.
    On any failure the original dict is returned with safe default values.
    """
    client = anthropic.Anthropic(api_key=api_key)

    user_msg = f"Claim: {claim['text']}\nSpeaker: {claim['speaker']}"

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error on claim %s: %s", claim.get("id"), exc)
        return {**claim, **_DEFAULTS}
    finally:
        time.sleep(0.3)

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
        logger.warning("JSON parse error on claim %s: %s — raw: %.120s", claim.get("id"), exc, raw)
        return {**claim, **_DEFAULTS}

    # Coerce and validate each field against allowed values
    claim_type = data.get("claim_type", "factual")
    if claim_type not in _VALID_TYPES:
        claim_type = "factual"

    evidence_quality = data.get("evidence_quality", "none")
    if evidence_quality not in _VALID_QUALITY:
        evidence_quality = "none"

    classification = {
        "claim_type":         claim_type,
        "checkable":          bool(data.get("checkable", False)),
        "evidence_in_speech": str(data.get("evidence_in_speech", "")),
        "evidence_quality":   evidence_quality,
        "suggested_query":    str(data.get("suggested_query", "")),
        "satirical":          bool(data.get("satirical", False)),
    }

    return {**claim, **classification}
