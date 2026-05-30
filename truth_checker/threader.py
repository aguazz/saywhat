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
    "thread_id is a short English slug (e.g. 'real_wages_2024'). "
    "topic is a plain-language label of 5-8 words. "
    "claim_ids lists the IDs belonging to that thread in chronological order."
)

_FALLBACK_THREAD_ID    = "main"
_FALLBACK_THREAD_TOPIC = "General debate"
_MAX_PER_BATCH         = 60   # max claims sent in one API call


def _call_api(compact: list[dict], client, existing_thread_ids: list[str] | None = None) -> list[dict]:
    """Single Claude call to group a list of compact claim dicts into threads."""
    hint = ""
    if existing_thread_ids:
        hint = (
            "\nFor consistency with previous batches, reuse these thread IDs where "
            f"the topic matches: {', '.join(existing_thread_ids)}. "
            "You may create new IDs only for topics not covered."
        )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM + hint,
        messages=[{"role": "user", "content": json.dumps(compact, ensure_ascii=False)}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("expected a JSON array")
    return parsed


def group_into_threads(claims: list[dict], api_key: str) -> list[dict]:
    """
    Group classified claim dicts into argument threads using Claude Sonnet.

    For large claim sets (>MAX_PER_BATCH) the work is split into batches and
    thread IDs are shared across batches so related claims land in the same thread.

    Mutates each claim dict in-place, adding 'thread_id' and 'thread_topic'.
    Returns the deduplicated list of thread dicts.
    On any failure the affected claims fall back to a single fallback thread.
    """
    if not claims:
        return []

    compact = [{"id": c["id"], "speaker": c["speaker"], "text": c["text"]} for c in claims]
    client  = anthropic.Anthropic(api_key=api_key)

    raw_threads: list[dict] = []

    if len(compact) <= _MAX_PER_BATCH:
        # Small enough for a single call
        try:
            raw_threads = _call_api(compact, client)
        except Exception as exc:
            logger.warning("Thread grouping failed (%s) — using fallback.", exc)
    else:
        # Batch: split into chunks, reuse thread IDs across batches so the
        # model can put same-topic claims from different chunks in the same thread.
        existing_ids: list[str] = []
        for start in range(0, len(compact), _MAX_PER_BATCH):
            batch = compact[start : start + _MAX_PER_BATCH]
            try:
                batch_threads = _call_api(batch, client, existing_ids if existing_ids else None)
                raw_threads.extend(batch_threads)
                # Update the vocabulary of known thread IDs for the next batch
                existing_ids = list({t.get("thread_id", "") for t in raw_threads if t.get("thread_id")})
            except Exception as exc:
                logger.warning("Thread grouping failed on batch starting at %d (%s).", start, exc)

    # ── Deduplicate: merge threads that share the same thread_id ──────────────
    merged: dict[str, dict] = {}
    for t in raw_threads:
        tid   = str(t.get("thread_id", "")).strip() or _FALLBACK_THREAD_ID
        topic = str(t.get("topic",     "")).strip() or _FALLBACK_THREAD_TOPIC
        ids   = t.get("claim_ids", [])
        if not isinstance(ids, list):
            continue
        if tid in merged:
            merged[tid]["claim_ids"].extend(ids)
        else:
            merged[tid] = {"thread_id": tid, "topic": topic, "claim_ids": list(ids)}

    valid_threads = list(merged.values())

    # ── Build claim_id → (thread_id, topic) lookup ───────────────────────────
    claim_map: dict[str, tuple[str, str]] = {}
    for t in valid_threads:
        tid, topic = t["thread_id"], t["topic"]
        for cid in t["claim_ids"]:
            claim_map[str(cid)] = (tid, topic)

    # ── Unassigned claims → fallback thread ───────────────────────────────────
    unassigned = [c for c in claims if c["id"] not in claim_map]
    if unassigned:
        fallback_ids = [c["id"] for c in unassigned]
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

    # ── Mutate claim dicts in-place ───────────────────────────────────────────
    for claim in claims:
        tid, topic = claim_map.get(claim["id"], (_FALLBACK_THREAD_ID, _FALLBACK_THREAD_TOPIC))
        claim["thread_id"]    = tid
        claim["thread_topic"] = topic

    return valid_threads
