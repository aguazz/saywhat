"""
Dialectical stage labeling for speaker turns.

Van Eemeren & Grootendorst (2004) describe four stages of a critical discussion:
  confrontation  — the disagreement is made explicit
  opening        — shared starting points / procedures are established
  argumentation  — arguments for / against standpoints are exchanged
  concluding     — the outcome of the discussion is determined

Reference: van Eemeren, F. H., & Grootendorst, R. (2004). A systematic theory of
argumentation: The pragma-dialectical approach. Cambridge University Press.
"""

import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_VALID_STAGES = {"confrontation", "opening", "argumentation", "concluding"}
_DEFAULT_STAGE = "argumentation"
_BATCH_SIZE = 10

_SYSTEM = (
    "You are an expert in argumentation theory. "
    "Label each numbered speaker turn below with its dialectical stage.\n\n"

    "The four stages of a critical discussion (van Eemeren & Grootendorst 2004):\n"
    "  confrontation — the disagreement is expressed or made explicit; "
    "speakers assert opposing positions or challenge each other's standpoints "
    "(e.g. 'I disagree — X is wrong because…', 'That claim is false').\n"
    "  opening — shared premises, procedures, or definitions are established; "
    "speakers clarify what the debate is about or agree how to proceed "
    "(e.g. 'Let us agree that the question is whether…', "
    "'By X I mean…', 'The burden of proof here lies with…').\n"
    "  argumentation — arguments and counter-arguments for the respective standpoints "
    "are advanced and challenged; this is the substantive exchange "
    "(e.g. citing data, giving reasons, rebutting evidence, drawing inferences).\n"
    "  concluding — the result of the discussion is established; a speaker concedes, "
    "maintains their position after challenge, or declares the standpoint resolved "
    "(e.g. 'Given all this, I maintain…', 'I accept your point on X', "
    "'This debate shows that…').\n\n"

    "Return a JSON array with EXACTLY one stage label per turn, in the same order, "
    "using only these four values: "
    '"confrontation", "opening", "argumentation", "concluding".\n'
    "Example for 3 turns: [\"argumentation\", \"confrontation\", \"argumentation\"]"
)


def _label_batch(batch: list[dict], client) -> list[str]:
    sections = []
    for i, turn in enumerate(batch):
        preview = turn["text"][:200] + ("…" if len(turn["text"]) > 200 else "")
        sections.append(f"Turn {i + 1} (Speaker {turn['speaker']}):\n{preview}")
    user_msg = "\n\n".join(sections)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    finally:
        time.sleep(0.3)

    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    result = json.loads(raw)
    if not isinstance(result, list) or len(result) != len(batch):
        raise ValueError(f"expected {len(batch)} labels, got {result!r}")
    return [str(s) for s in result]


def label_dialectical_stages(turns: list[dict], api_key: str) -> list[dict]:
    """
    Labels each turn with its dialectical stage. Mutates turns in place, adding
    "dialectical_stage": one of "confrontation", "opening", "argumentation", "concluding".
    Returns the same list.
    """
    if not turns:
        return turns

    client = anthropic.Anthropic(api_key=api_key)

    for batch_start in range(0, len(turns), _BATCH_SIZE):
        batch = turns[batch_start: batch_start + _BATCH_SIZE]
        try:
            labels = _label_batch(batch, client)
            for turn, label in zip(batch, labels):
                stage = label if label in _VALID_STAGES else _DEFAULT_STAGE
                turn["dialectical_stage"] = stage
        except Exception as exc:
            logger.warning(
                "stage_labeler: batch at %d failed (%s) — defaulting to '%s'.",
                batch_start, exc, _DEFAULT_STAGE,
            )
            for turn in batch:
                turn.setdefault("dialectical_stage", _DEFAULT_STAGE)

    return turns
