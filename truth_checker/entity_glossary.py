import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an entity normalizer for debate transcripts. Your task is to identify all "
    "named entities (people, studies, institutions, concepts, products) that appear under "
    "multiple surface forms in the transcript — including mispronunciations, nicknames, "
    "phonetic variants, abbreviations, and partial references.\n\n"
    "Return a JSON object. Each key is the canonical name. Each value is an object with:\n"
    "- description: one sentence identifying who or what this entity is.\n"
    "- variants: list of all surface forms used for this entity in the transcript, "
    "including the canonical name itself.\n\n"
    "Only include entities that genuinely appear under MORE THAN ONE surface form. "
    "Do not include entities that are referred to consistently by a single name. "
    "If no such entities exist, return {}.\n\n"
    "Return only valid JSON. No markdown fences."
)


def format_glossary_for_prompt(glossary: dict) -> str:
    if not glossary:
        return ""
    lines = []
    for name, entry in glossary.items():
        desc = entry.get("description", "")
        variants = entry.get("variants", [])
        line = f"- {name}: {desc}."
        if variants:
            line += f" Also referred to as: {', '.join(variants)}."
        lines.append(line)
    return "\n".join(lines)


def build_entity_glossary(
    transcript_text: str,
    motion: str = "",
    api_key: str = "",
) -> dict:
    motion_line = f"Debate topic: {motion}\n" if motion.strip() else ""
    user_msg = f"{motion_line}Transcript:\n{transcript_text}"

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error building entity glossary: %s", exc)
        return {}

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data
    except Exception as exc:
        logger.warning("JSON parse error building entity glossary: %s — raw: %.120s", exc, raw)
        return {}
