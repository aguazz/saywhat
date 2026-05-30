"""
Restatement detection for debate claims.

When a speaker makes the same assertion multiple times across different turns,
those repetitions waste fact-check API calls and inflate claim counts. This
module detects same-speaker, same-thread restatements and marks the later
occurrence so the rest of the pipeline can skip it.

Reference: Peldszus & Stede (2013) — "restatement" annotation operation.
"""

import json
import logging
import time
from collections import defaultdict

import anthropic

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10
_MAX_TURN_GAP = 8   # only compare claims within this many turns of each other

_SYSTEM = (
    "For each numbered pair of statements below, decide whether Claim A and "
    "Claim B assert the same proposition — that is, whether they make the same "
    "core factual assertion, even if worded differently or with added context. "
    "Return YES only when the central claim is identical, not merely related. "
    "Ignore differences in phrasing, emphasis, examples, or minor elaborations "
    "if the underlying assertion is the same. "
    "Return a JSON array of booleans with EXACTLY one entry per pair, in order: "
    "[true, false, ...]"
)


def _check_pairs_batch(pairs: list[tuple[dict, dict]], client) -> list[bool]:
    sections = []
    for i, (earlier, later) in enumerate(pairs):
        sections.append(
            f"Pair {i + 1}:\n"
            f"  Claim A: {earlier['text']}\n"
            f"  Claim B: {later['text']}"
        )
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
    if not isinstance(result, list) or len(result) != len(pairs):
        raise ValueError(f"expected {len(pairs)} booleans, got {result!r}")
    return [bool(x) for x in result]


def mark_restatements(claims: list[dict], api_key: str) -> list[dict]:
    """
    Detect restatements and mark the later claim with "restatement_of": earlier_id.

    Rules:
    - Only compares claims by the same speaker within the same thread_id.
    - Only compares claims within _MAX_TURN_GAP turns of each other.
    - Skips claims that are already marked as restatements (avoids using a
      restatement as the canonical "earlier" claim in further comparisons).
    - Claims without a thread_id are skipped (threading must run first).
    - Mutates the claim dicts in place; returns the same list.
    - On any API failure, that batch is skipped silently.
    """
    # Only work on claims that have been assigned a thread
    eligible = [c for c in claims if c.get("thread_id")]
    if not eligible:
        return claims

    # Group by (speaker, thread_id), sort each group by turn_index
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in eligible:
        groups[(c["speaker"], c["thread_id"])].append(c)

    for group in groups.values():
        group.sort(key=lambda c: c.get("turn_index", 0))

    # Generate candidate pairs: (earlier, later) within the turn gap limit
    all_pairs: list[tuple[dict, dict]] = []
    for group in groups.values():
        for i in range(len(group)):
            earlier = group[i]
            if earlier.get("restatement_of"):
                # Don't use a restatement as the canonical earlier claim
                continue
            for j in range(i + 1, len(group)):
                later = group[j]
                gap = later.get("turn_index", 0) - earlier.get("turn_index", 0)
                if gap > _MAX_TURN_GAP:
                    break  # group is sorted, further j's will only increase the gap
                if later.get("restatement_of"):
                    continue  # already marked, no need to re-evaluate
                all_pairs.append((earlier, later))

    if not all_pairs:
        return claims

    client = anthropic.Anthropic(api_key=api_key)

    for batch_start in range(0, len(all_pairs), _BATCH_SIZE):
        batch = all_pairs[batch_start: batch_start + _BATCH_SIZE]
        try:
            results = _check_pairs_batch(batch, client)
            for (earlier, later), is_restatement in zip(batch, results):
                if is_restatement and not later.get("restatement_of"):
                    later["restatement_of"] = earlier["id"]
                    logger.debug(
                        "Marked claim %s as restatement of %s", later["id"], earlier["id"]
                    )
        except Exception as exc:
            logger.warning(
                "deduplicator: batch starting at %d failed (%s) — skipping.",
                batch_start, exc,
            )

    return claims
