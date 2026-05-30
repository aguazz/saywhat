import logging

import anthropic

logger = logging.getLogger(__name__)


def translate_claim(text: str, source_lang: str, target_lang: str, api_key: str) -> str:
    """
    Translate claim text between 'en' and 'es' using Claude Haiku.

    Returns the original text unchanged if source_lang == target_lang
    or if the API call fails.
    """
    if source_lang == target_lang:
        return text

    client = anthropic.Anthropic(api_key=api_key)
    system = (
        f"You are a translator. Translate the text below from {source_lang} to "
        f"{target_lang}. Preserve the original meaning exactly. Do not add commentary. "
        "Return only the translated text, nothing else."
    )
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Translation failed (%s→%s): %s", source_lang, target_lang, exc)
        return text
