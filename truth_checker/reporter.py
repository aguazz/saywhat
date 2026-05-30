import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a balanced debate analyst writing for a curious general reader. "
    "Given a speaker's statistical profile from a debate, write a 2-paragraph summary "
    "(200 words maximum total). "
    "First paragraph: factual accuracy and evidence quality — what proportion of their "
    "checkable claims held up, and how well-evidenced were their arguments. "
    "Second paragraph: how well they engaged with the other speaker's arguments — "
    "their response rate, evasion patterns, and any recurring logical fallacies. "
    "Be fair and balanced. Do not editorialize beyond what the data shows. "
    "If a metric is null (no data), acknowledge the gap rather than inventing an assessment."
)


def generate_speaker_summary(
    speaker_id: str,
    speaker_name: str,
    score: dict,
    api_key: str,
) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    user_msg = (
        f"Speaker: {speaker_name} (ID: {speaker_id})\n\n"
        f"Stats:\n{json.dumps(score, indent=2, ensure_ascii=False)}"
    )
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.warning("reporter: API error for %s: %s", speaker_id, exc)
        v = score.get("verdicts", {})
        rs = score.get("reliability_score")
        dr = score.get("direct_response_rate")
        rs_str = f"{rs:.0%}" if rs is not None else "n/a"
        dr_str = f"{dr:.0%}" if dr is not None else "n/a"
        return (
            f"{speaker_name} made {score.get('total_claims', 0)} claims "
            f"({score.get('checkable_claims', 0)} checkable). "
            f"Accuracy rate: {rs_str}. "
            f"Verdicts — true: {v.get('true', 0)}, partly true: {v.get('partially_true', 0)}, "
            f"false: {v.get('false', 0)}, contested: {v.get('contested', 0)}.\n\n"
            f"Made {score.get('total_responses_made', 0)} responses "
            f"({score.get('evasions', 0)} evasions). "
            f"Direct response rate: {dr_str}. "
            f"Fallacies detected: {score.get('fallacy_count', 0)} "
            f"({', '.join(score.get('fallacy_types', [])) or 'none'})."
        )
