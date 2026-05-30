import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_RULE_NAMES = {
    1: "Freedom",
    2: "Burden of proof",
    3: "Standpoint",
    4: "Relevance",
    7: "Argument scheme",
    10: "Usage",
}

_SYSTEM = (
    "You are a logician and rhetoric expert writing for a general (non-expert) audience. "
    "Analyze the speaker turn below using the pragma-dialectical theory of argumentation "
    "(van Eemeren & Grootendorst 2004). Only flag clear, unambiguous examples — do not invent violations.\n\n"

    "FALLACIES — violations of rules of critical discussion:\n"
    "Rule 1 (Freedom) — prevents the other party from advancing a standpoint:\n"
    "  ad_hominem, silencing_the_opponent\n"
    "Rule 2 (Burden of proof) — evades the obligation to defend a standpoint:\n"
    "  shifting_burden, appeal_to_unfalsifiability\n"
    "Rule 3 (Standpoint) — attacks a position the opponent did not actually hold:\n"
    "  straw_man, attacking_a_different_position\n"
    "Rule 4 (Relevance) — defends with arguments irrelevant to the standpoint:\n"
    "  red_herring, whataboutism, tu_quoque\n"
    "Rule 7 (Argument scheme) — uses a logically invalid argument pattern:\n"
    "  false_dichotomy, slippery_slope, hasty_generalization, false_analogy, "
    "appeal_to_authority_illegitimate, cherry_picking, correlation_as_causation\n"
    "Rule 10 (Usage) — exploits ambiguity or vagueness to evade challenge:\n"
    "  loaded_language, equivocation, vague_terms_to_evade\n\n"

    "NEUTRAL RHETORICAL DEVICES — techniques that are not rule violations:\n"
    "  appeal_to_authority_legitimate, vivid_example, social_proof, "
    "personal_testimony, framing_effect\n\n"

    "For each item found return a JSON object:\n"
    '{"type": str, "violated_rule": int|null, "label": str, "quote": str, '
    '"is_fallacy": bool, "explanation": str}\n'
    "  type: the snake_case identifier from the lists above\n"
    "  violated_rule: the rule number (1, 2, 3, 4, 7, or 10) for fallacies; "
    "null for neutral devices\n"
    "  label: short plain-language name (e.g. 'False choice', 'Straw man')\n"
    "  quote: exact phrase from the text (keep it short)\n"
    "  is_fallacy: true for rule violations, false for neutral devices\n"
    "  explanation: 2-3 plain sentences — what happened, why it matters or does not, "
    "and for fallacies what a stronger version of the argument would look like\n\n"
    'Return JSON: {"fallacies": [...], "rhetorical_devices": [...]}. '
    "Empty lists if none found."
)


def analyze_turn_rhetoric(turn: dict, api_key: str, model: str = "claude-sonnet-4-6") -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    user_msg = f"Speaker: {turn['speaker']}\nText:\n{turn['text']}"

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("rhetorician: JSON parse failed for turn %s", turn.get("turn_index"))
        result = {"fallacies": [], "rhetorical_devices": []}
    except Exception as exc:
        logger.warning("rhetorician: API error for turn %s: %s", turn.get("turn_index"), exc)
        result = {"fallacies": [], "rhetorical_devices": []}
    finally:
        time.sleep(0.3)

    result["turn_index"] = turn["turn_index"]
    result["speaker"] = turn["speaker"]
    result["start_ms"] = turn["start_ms"]
    return result
