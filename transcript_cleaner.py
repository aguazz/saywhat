import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are reviewing a debate transcript to identify non-debate segments that should "
    "be excluded from argument analysis. Non-debate content includes:\n"
    "- Host or presenter intro/outro monologues not addressed to the other debater\n"
    "- Sponsor reads, advertising, or product promotions\n"
    "- Calls to action ('subscribe', 'follow me at', 'check the link')\n"
    "- Repeated teaser clips (content that appears word-for-word elsewhere in the transcript)\n"
    "- Mid-roll ad breaks\n"
    "Debate content includes: any exchange between debaters, moderator questions to debaters, "
    "and any substantive claims about the debate topic, even if made during an intro.\n\n"
    "Return a JSON object:\n"
    "{ 'out_of_scope': [list of integer indices] }\n\n"
    "Be conservative: when in doubt, keep the utterance (do not mark it out-of-scope). "
    "If nothing should be excluded, return { 'out_of_scope': [] }. "
    "Return only valid JSON. No markdown fences."
)


def detect_out_of_scope_utterances(
    utterances: list[dict],
    motion: str = "",
    api_key: str = "",
) -> list[int]:
    transcript_text = "\n".join(
        f"[{i}] {u['speaker']}: {u.get('text', '').strip()}"
        for i, u in enumerate(utterances)
    )
    motion_line = f"Debate topic: {motion}\n" if motion.strip() else ""
    user_msg = f"{motion_line}Transcript (index: speaker: text):\n{transcript_text}"

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error detecting out-of-scope utterances: %s", exc)
        return []

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        indices = data.get("out_of_scope", [])
        if not isinstance(indices, list):
            raise ValueError("out_of_scope must be a list")
        return [int(i) for i in indices if isinstance(i, (int, float))]
    except Exception as exc:
        logger.warning("JSON parse error detecting out-of-scope utterances: %s — raw: %.120s", exc, raw)
        return []
