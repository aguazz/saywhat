import json
import re

import anthropic


def suggest_speaker_names(transcript: dict, api_key: str) -> dict:
    """
    Ask Claude Haiku to identify debate speakers from transcript content.

    Sends the first few utterances per speaker plus any utterances that
    mention proper names, then asks Claude to return a JSON mapping.

    Returns:
        {
            "A": {"name": "Juan Ramón Rallo", "confidence": "high"},
            "B": {"name": "Eduardo Garzón",   "confidence": "high"},
            "C": {"name": "Moderator",         "confidence": "low"},
        }
    """
    utterances = transcript.get("utterances", [])
    if not utterances:
        return {}

    speakers = sorted({u["speaker"] for u in utterances})
    excerpt  = _build_excerpt(utterances, speakers)

    prompt = (
        "You are analyzing a debate transcript to identify who each speaker is.\n\n"
        "Transcript excerpt (speakers labeled A, B, C…):\n\n"
        f"{excerpt}\n\n"
        "Identify each speaker by name. Look for:\n"
        "- Self-introductions ('I am…', 'My name is…')\n"
        "- How other speakers address them ('Thank you, [name]', '[name] argued…')\n"
        "- Their stated positions, affiliations, or areas of expertise\n"
        "- Any other contextual clues\n\n"
        f"Speakers to identify: {', '.join(speakers)}\n\n"
        "Return ONLY a valid JSON object — no markdown, no explanation:\n"
        "{\n"
        '  "<id>": {"name": "<Full Name or role>", "confidence": "high" or "low"}\n'
        "}\n\n"
        'Use "high" when clearly identified, "low" when uncertain or inferred. '
        'Use "Unknown" as the name only when there are truly no identifying clues.'
    )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()

    # Extract the JSON object even if Claude wrapped it in markdown or prose
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Claude did not return valid JSON. Response: {raw[:300]}")
    parsed = json.loads(match.group(0))

    # Ensure every speaker has an entry
    for sid in speakers:
        if sid not in parsed:
            parsed[sid] = {"name": "Unknown", "confidence": "low"}

    return parsed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_excerpt(utterances: list, speakers: list, per_speaker: int = 5) -> str:
    """
    First N utterances per speaker (introductions happen early) plus
    later utterances that appear to mention a person's name.
    """
    counts  = {sid: 0 for sid in speakers}
    primary = []
    hints   = []

    for utt in utterances:
        sid  = utt["speaker"]
        text = utt["text"]

        if counts[sid] < per_speaker:
            primary.append(f"Speaker {sid}: {text}")
            counts[sid] += 1
        elif len(hints) < 10:
            # Capture utterances containing what looks like a proper name
            if re.search(
                r"\b[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+ [A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+", text
            ):
                hints.append(f"Speaker {sid}: {text}")

    if hints:
        return (
            "\n".join(primary)
            + "\n\n[Additional name references found later in the transcript:]\n"
            + "\n".join(hints)
        )
    return "\n".join(primary)
