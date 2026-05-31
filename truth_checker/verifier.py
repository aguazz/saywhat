import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a rigorous fact-checker writing for a general audience. "
    "Your job is to assess a claim, provide a reasoned verdict, and cite your sources clearly.\n\n"

    "You have two inputs:\n"
    "A. Retrieved external evidence (shown below) — Wikipedia articles, DuckDuckGo summaries, "
    "and peer-reviewed paper abstracts gathered specifically for this claim.\n"
    "B. Your training knowledge — scientific consensus, established data, and well-documented "
    "research up to your knowledge cutoff.\n\n"

    "HOW TO USE THEM:\n"
    "• Always read the retrieved evidence first. Even if it gives only background context "
    "(e.g. a Wikipedia article about the general topic), include every retrieved source in "
    "all_sources — they represent real research done on behalf of the user.\n"
    "• Use retrieved evidence as your primary factual basis wherever it is relevant, even "
    "partially. Cite it in your explanation by name.\n"
    "• Supplement with training knowledge when retrieved evidence does not fully answer the "
    "claim — for example to add specific numbers, name a study, or complete the picture. "
    "Clearly distinguish which part comes from training knowledge vs. retrieved sources.\n"
    "• Set knowledge_based=false whenever at least one retrieved source was relevant enough "
    "to include in all_sources (even as background context).\n"
    "• Set knowledge_based=true ONLY when the retrieved evidence list was completely empty "
    "or every source was entirely off-topic for the claim. In that case, name the specific "
    "authoritative institution, report, or study your verdict draws on in key_source "
    "(e.g. 'FAO World Livestock 2021', 'IPCC AR6 Land Chapter', 'Poore & Nemecek 2018 – Science', "
    "'WHO Nutrition Guidelines'). Never write 'scientific consensus' without naming the source.\n\n"

    "VERDICT RULES:\n"
    "• true / partially_true / contested / misleading / false — use these for factual claims "
    "you can assess. Include specific figures, dates, or study names in the explanation.\n"
    "• unverifiable — ONLY for claims about events after your knowledge cutoff, or claims "
    "with no factual content that could possibly be checked.\n"
    "• subjective — for normative, moral, or value judgments with no verifiable factual core.\n"
    "• Never fabricate URLs or invent statistics.\n\n"

    "Return a JSON object with these exact fields:\n"
    "- verdict: one of [true, partially_true, contested, misleading, false, unverifiable, subjective]\n"
    "- confidence: float 0.0–1.0\n"
    "- explanation: 3–5 sentences. Name specific sources, figures, or studies. "
    "Distinguish retrieved evidence from training knowledge explicitly.\n"
    "- for_the_claim: if verdict=contested, one sentence supporting it; else ''\n"
    "- against_the_claim: if verdict=contested, one sentence against it; else ''\n"
    "- key_source: the single most authoritative source. If retrieved: title and URL. "
    "If training-knowledge-only: name the specific institution or study (no URL needed, "
    "but be specific — e.g. 'Poore & Nemecek 2018, Science' not 'scientific consensus').\n"
    "- all_sources: list of {title, url} for EVERY retrieved source from the evidence list "
    "that was even tangentially relevant. Include them even if you primarily used training "
    "knowledge. Use url='' if no URL is available. Empty list [] ONLY if the evidence list "
    "was completely empty.\n"
    "- knowledge_based: false if any retrieved source appears in all_sources; "
    "true only if all_sources is empty []\n"
)

_VALID_VERDICTS = {
    "true", "partially_true", "contested", "misleading",
    "false", "unverifiable", "subjective",
}

_PARSE_FAILURE = {
    "verdict":          "unverifiable",
    "confidence":       0.0,
    "knowledge_based":  True,
    "explanation":      "The fact-check could not be completed due to a parsing error.",
    "for_the_claim":    "",
    "against_the_claim": "",
    "key_source":       "",
    "all_sources":      [],
}


def _format_evidence(evidence: list[dict]) -> str:
    lines = []
    for i, item in enumerate(evidence, 1):
        source_tag = f" [{item.get('source', '').upper()}]" if item.get("source") else ""
        url_line = f"\n   URL: {item['url']}" if item.get("url") else ""
        lines.append(
            f"{i}. {item.get('title', '')}{source_tag}{url_line}\n"
            f"   {item.get('snippet', '')}"
        )
    return "\n\n".join(lines)


def verify_claim(claim: dict, evidence: list[dict], api_key: str) -> dict:
    """
    Assess a claim using retrieved evidence + Claude's training knowledge (Option C hybrid).

    Claude always runs. The knowledge_based field signals whether any retrieved source
    contributed to the assessment. All retrieved sources are always listed in all_sources
    so users can see what research was done, regardless of which knowledge source dominated.
    """
    _warrant = claim.get("warrant_hint")
    _warrant_line = f"Stated inference: {_warrant}\n" if _warrant else ""

    if evidence:
        n = len(evidence)
        evidence_section = (
            f"Retrieved evidence ({n} source{'s' if n != 1 else ''} found):\n"
            f"{_format_evidence(evidence)}"
        )
        logger.info("verify_claim %s: %d evidence items retrieved", claim.get("id"), n)
    else:
        evidence_section = (
            "Retrieved evidence: none (all external searches returned empty results).\n"
            "Assess using your training knowledge. Set knowledge_based=true and "
            "name the specific authoritative source in key_source."
        )
        logger.info("verify_claim %s: no evidence retrieved", claim.get("id"))

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
            max_tokens=800,
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
        logger.warning("JSON parse error for claim %s: %s — raw: %.120s",
                       claim.get("id"), exc, raw)
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

    raw_sources = data.get("all_sources", [])
    all_sources = raw_sources if isinstance(raw_sources, list) else []

    # Canonical rule: knowledge_based iff no retrieved sources were listed.
    # Overrides the model's self-report to keep the flag consistent with all_sources.
    knowledge_based = len(all_sources) == 0

    return {
        "claim_id":          claim["id"],
        "verdict":           verdict,
        "confidence":        confidence,
        "knowledge_based":   knowledge_based,
        "explanation":       str(data.get("explanation", "")),
        "for_the_claim":     str(data.get("for_the_claim", ""))     if is_contested else "",
        "against_the_claim": str(data.get("against_the_claim", "")) if is_contested else "",
        "key_source":        str(data.get("key_source", "")),
        "all_sources":       all_sources,
    }
