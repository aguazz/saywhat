import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a rigorous fact-checker writing for a general audience. "
    "Your job is to assess the factual accuracy of a claim using all available means.\n\n"

    "You have two sources of knowledge:\n"
    "1. Retrieved external evidence (Wikipedia, DuckDuckGo, Semantic Scholar) — shown below.\n"
    "2. Your training knowledge — the scientific consensus, established facts, and "
    "well-documented findings up to your knowledge cutoff.\n\n"

    "Priority rules:\n"
    "• If retrieved evidence directly addresses the claim, use it as your primary basis "
    "and cite specific sources in your explanation.\n"
    "• If retrieved evidence is thin, absent, or only tangentially related, draw on your "
    "training knowledge — but you MUST set 'knowledge_based' to true and clearly state in "
    "your explanation that your assessment is based on scientific consensus or established "
    "knowledge, not a retrieved source.\n"
    "• Return 'unverifiable' ONLY when the claim concerns events after your knowledge cutoff, "
    "or when it is genuinely impossible to assess even with training knowledge.\n"
    "• Return 'subjective' for normative, moral, or value judgments with no factual core.\n"
    "• Never fabricate URLs, statistics, or source titles.\n\n"

    "Return a JSON object with these fields:\n"
    "- verdict: one of [true, partially_true, contested, misleading, false, unverifiable, subjective]\n"
    "- confidence: float 0.0–1.0 (how strongly the evidence supports the verdict)\n"
    "- explanation: 2–3 plain-language sentences explaining the verdict; "
    "cite specific evidence when available, or state 'established scientific consensus' when knowledge-based\n"
    "- for_the_claim: if verdict=contested, one sentence on what supports it; else ''\n"
    "- against_the_claim: if verdict=contested, one sentence against it; else ''\n"
    "- key_source: title and URL of the most relevant retrieved source, "
    "or 'Scientific consensus / training knowledge' if knowledge-based\n"
    "- all_sources: list of {title, url} for every retrieved source used; "
    "empty list if knowledge-based only\n"
    "- knowledge_based: true if this verdict is primarily based on training knowledge "
    "rather than the retrieved evidence; false if retrieved evidence was the main basis\n"
)

_VALID_VERDICTS = {
    "true", "partially_true", "contested", "misleading",
    "false", "unverifiable", "subjective",
}

_PARSE_FAILURE = {
    "verdict":          "unverifiable",
    "confidence":       0.0,
    "knowledge_based":  False,
    "explanation":      "The fact-check could not be completed due to a parsing error.",
    "for_the_claim":    "",
    "against_the_claim": "",
    "key_source":       "",
    "all_sources":      [],
}


def _format_evidence(evidence: list[dict]) -> str:
    lines = []
    for i, item in enumerate(evidence, 1):
        source_tag = f" [{item.get('source', '')}]" if item.get("source") else ""
        lines.append(
            f"{i}. {item.get('title', '')}{source_tag}\n"
            f"   {item.get('snippet', '')}"
        )
    return "\n\n".join(lines)


def verify_claim(claim: dict, evidence: list[dict], api_key: str) -> dict:
    """
    Assess a claim using retrieved evidence + Claude's training knowledge (Option C hybrid).

    Claude always runs — even with empty evidence — and decides for itself whether to
    return "unverifiable". The knowledge_based field in the result indicates whether the
    verdict was grounded in retrieved sources or training knowledge.
    """
    _warrant = claim.get("warrant_hint")
    _warrant_line = f"Stated inference: {_warrant}\n" if _warrant else ""

    if evidence:
        evidence_section = f"Retrieved evidence:\n{_format_evidence(evidence)}"
    else:
        evidence_section = (
            "No external sources were retrieved for this query. "
            "Assess the claim using your training knowledge. "
            "Set knowledge_based to true."
        )

    user_msg = (
        f"Claim: {claim['text']}\n"
        f"Speaker: {claim.get('speaker', '')}\n"
        f"{_warrant_line}"
        f"\n{evidence_section}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error verifying claim %s: %s", claim.get("id"), exc)
        return {**_PARSE_FAILURE, "claim_id": claim["id"]}

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

    verdict = data.get("verdict", "unverifiable")
    if verdict not in _VALID_VERDICTS:
        verdict = "unverifiable"

    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    is_contested = verdict == "contested"

    return {
        "claim_id":          claim["id"],
        "verdict":           verdict,
        "confidence":        confidence,
        "knowledge_based":   bool(data.get("knowledge_based", False)),
        "explanation":       str(data.get("explanation", "")),
        "for_the_claim":     str(data.get("for_the_claim", ""))     if is_contested else "",
        "against_the_claim": str(data.get("against_the_claim", "")) if is_contested else "",
        "key_source":        data.get("key_source", ""),
        "all_sources":       data.get("all_sources", []) if isinstance(data.get("all_sources"), list) else [],
    }
