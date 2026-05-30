import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an argument analyst reviewing a debate transcript. "
    "Group the following claims into argument threads. A thread is a set of claims that "
    "share the same topic or sub-topic, regardless of which speaker made them. "
    "Aim for 3–8 threads. Assign every claim to exactly one thread. "
    "If a claim fits no other thread, assign it to a thread with topic 'miscellaneous'. "
    "Return a JSON array of thread objects:\n"
    '[{"thread_id": str, "topic": str, "claim_ids": [str]}]\n'
    "thread_id is a short slug (e.g. 'real_wages_2024'). "
    "topic is a plain-language label of 5-8 words. "
    "claim_ids lists the IDs belonging to that thread in chronological order."
)

_FALLBACK_THREAD_ID    = "main"
_FALLBACK_THREAD_TOPIC = "General debate"


def group_into_threads(claims: list[dict], api_key: str) -> list[dict]:
    """
    Group a list of classified claim dicts into argument threads using Claude Sonnet.

    Mutates each claim dict in-place, adding 'thread_id' and 'thread_topic'.
    Returns the list of thread dicts (each with thread_id, topic, claim_ids).
    On any failure, all claims are assigned to a single fallback thread.
    """
    if not claims:
        return []

    compact = [{"id": c["id"], "speaker": c["speaker"], "text": c["text"]} for c in claims]

    client = anthropic.Anthropic(api_key=api_key)

    threads: list[dict] = []
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(compact, ensure_ascii=False)}],
        )
        raw = response.content[0].text.strip()

        # Strip optional markdown code fence
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("expected a JSON array")
        threads = parsed

    except Exception as exc:
        logger.warning("Thread grouping failed (%s) — falling back to single thread.", exc)

    # Build lookup: claim_id → (thread_id, thread_topic)
    claim_map: dict[str, tuple[str, str]] = {}
    valid_threads: list[dict] = []

    for thread in threads:
        tid   = str(thread.get("thread_id", "")).strip() or _FALLBACK_THREAD_ID
        topic = str(thread.get("topic", "")).strip()     or _FALLBACK_THREAD_TOPIC
        ids   = thread.get("claim_ids", [])
        if not isinstance(ids, list):
            continue
        valid_threads.append({"thread_id": tid, "topic": topic, "claim_ids": ids})
        for cid in ids:
            claim_map[str(cid)] = (tid, topic)

    # Any claim not assigned by the model goes to fallback
    unassigned = [c for c in claims if c["id"] not in claim_map]
    if unassigned:
        fallback_ids = [c["id"] for c in unassigned]
        # Merge into existing fallback thread if present, else create one
        existing = next((t for t in valid_threads if t["thread_id"] == _FALLBACK_THREAD_ID), None)
        if existing:
            existing["claim_ids"].extend(fallback_ids)
        else:
            valid_threads.append({
                "thread_id": _FALLBACK_THREAD_ID,
                "topic":     _FALLBACK_THREAD_TOPIC,
                "claim_ids": fallback_ids,
            })
        for c in unassigned:
            claim_map[c["id"]] = (_FALLBACK_THREAD_ID, _FALLBACK_THREAD_TOPIC)

    # Mutate claim dicts in-place
    for claim in claims:
        tid, topic = claim_map.get(claim["id"], (_FALLBACK_THREAD_ID, _FALLBACK_THREAD_TOPIC))
        claim["thread_id"]    = tid
        claim["thread_topic"] = topic

    return valid_threads
