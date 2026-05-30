def segment_turns(utterances: list[dict]) -> list[dict]:
    """
    Group consecutive utterances from the same speaker into turns.

    Empty utterances (blank or whitespace-only text) are skipped before grouping.
    Returns a list of turn dicts ordered chronologically, with 0-based turn_index.
    """
    turns = []
    current: dict | None = None

    for utt in utterances:
        if not utt.get("text", "").strip():
            continue

        if current is None or utt["speaker"] != current["speaker"]:
            if current is not None:
                turns.append(current)
            current = {
                "turn_index":      len(turns),
                "speaker":         utt["speaker"],
                "start_ms":        utt["start_ms"],
                "end_ms":          utt["end_ms"],
                "text":            utt["text"].strip(),
                "utterance_count": 1,
            }
        else:
            current["end_ms"] = utt["end_ms"]
            current["text"] += " " + utt["text"].strip()
            current["utterance_count"] += 1

    if current is not None:
        turns.append(current)

    return turns
