import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a logician and rhetoric expert writing for a general (non-expert) audience. "
    "Analyze the speaker turn below for logical fallacies and rhetorical devices. "
    "Only flag clear, unambiguous examples — do not invent fallacies. "
    "Fallacies to check: straw_man, ad_hominem, false_dichotomy, appeal_to_authority "
    "(illegitimate), slippery_slope, cherry_picking, appeal_to_emotion (manipulative), "
    "anecdote_over_data, whataboutism, hasty_generalization, correlation_as_causation. "
    "Neutral devices to note: appeal_to_authority (legitimate), vivid_example, social_proof, "
    "personal_testimony, framing_effect, loaded_language. "
    "For each item found, return: "
    "{type: str, label: str (plain-language name, e.g. 'False choice'), "
    "quote: str (exact phrase from text), is_fallacy: bool, "
    "explanation: str (2-3 plain sentences: what happened, why it matters or does not, "
    "and for fallacies — what a stronger version would look like)}. "
    "Return JSON: {fallacies: [...], rhetorical_devices: [...]}. Empty lists if none found."
)


def analyze_turn_rhetoric(turn: dict, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    user_msg = f"Speaker: {turn['speaker']}\nText:\n{turn['text']}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
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
