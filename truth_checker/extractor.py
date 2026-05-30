import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an argument analyst. Extract discrete substantive claims from the speaker turn below. "
    "A claim is a statement about the world presented as true that can be agreed or disagreed with. "
    "Do NOT extract:\n"
    "- Questions directed at other speakers\n"
    "- Greetings, thank-yous, filler phrases, or transition sentences\n"
    "- Descriptions of what other speakers believe or have said (e.g. 'Juan Ramón says that…')\n"
    "- Moderator-style introductions or context-setting sentences about the debate itself\n"
    "- Expressions of preference ('I think we should…') without a factual assertion\n"
    "- Clear jokes, hyperbole, or rhetorical questions\n"
    "Focus on factual, causal, statistical, interpretive, or evaluative claims about the debate topic. "
    "Be conservative: extract the 3–6 most substantive claims per turn, not every possible statement. "
    "The turn may be in Spanish or English — preserve the original language in your output. "
    'Return a JSON array. Each item: {"text": str, "start_hint": str}. '
    '"text" is the exact or lightly cleaned claim. '
    '"start_hint" is the first 5 words of the sentence. '
    "If there are no substantive claims, return []."
)

_MIN_TURN_WORDS = 20   # skip turns shorter than this — usually greetings or brief remarks


def extract_claims_from_turn(turn: dict, api_key: str) -> list[dict]:
    """
    Extract discrete substantive claims from a single speaker turn using Claude Haiku.

    Skips very short turns (likely greetings/acknowledgements) that would not
    contain meaningful claims.  Returns [] if the API call fails or no claims
    are found.
    """
    # Skip turns that are too short to contain a real claim
    word_count = len(turn["text"].split())
    if word_count < _MIN_TURN_WORDS:
        return []

    client = anthropic.Anthropic(api_key=api_key)
    user_msg = f"Speaker: {turn['speaker']}\nText:\n{turn['text']}"

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error on turn %s: %s", turn["turn_index"], exc)
        return []
    finally:
        time.sleep(0.3)

    # Strip optional markdown code fence
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("expected a JSON array")
    except Exception as exc:
        logger.warning("JSON parse error on turn %s: %s — raw: %.120s", turn["turn_index"], exc, raw)
        return []

    claims = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("text", "").strip():
            continue
        claims.append(
            {
                "id":          f"claim_{turn['turn_index']}_{i}",
                "speaker":     turn["speaker"],
                "turn_index":  turn["turn_index"],
                "start_ms":    turn["start_ms"],
                "end_ms":      turn["end_ms"],
                "text":        item["text"].strip(),
                "start_hint":  item.get("start_hint", "").strip(),
            }
        )

    return claims
