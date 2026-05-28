import copy


def flag_transcript(transcript: dict) -> dict:
    """
    Classify each utterance and word by transcription confidence.

    Adds two fields to every utterance:
        flag          "ok" | "uncertain" | "unreliable"
        flagged_words list of word dicts whose confidence < 0.60

    Adds two top-level fields to the transcript:
        has_low_confidence_zones  bool
        low_confidence_count      int

    The original dict is never modified — a deep copy is returned.
    """
    result = copy.deepcopy(transcript)

    low_confidence_count = 0

    for utt in result.get("utterances", []):
        conf = utt.get("confidence", 0.0)

        if conf >= 0.60:
            utt["flag"] = "ok"
        elif conf >= 0.40:
            utt["flag"] = "uncertain"
            low_confidence_count += 1
        else:
            utt["flag"] = "unreliable"
            low_confidence_count += 1

        utt["flagged_words"] = [
            w for w in utt.get("words", [])
            if w.get("confidence", 0.0) < 0.60
        ]

    result["has_low_confidence_zones"] = low_confidence_count > 0
    result["low_confidence_count"] = low_confidence_count

    return result
