"""
Claim deduplication for debate analysis.

Two functions:

  remove_teaser_duplicates()
      Pre-classification pass. Removes claims produced from podcast teaser
      clips (the same exchange played at the top of an episode before the
      intro). Identifies pairs of claims from the same speaker whose texts
      are nearly identical but far apart in time, and drops the earlier one.
      Zero API calls.

  mark_restatements()
      Post-threading pass. Detects same-speaker, same-thread restatements
      and marks the later occurrence so the rest of the pipeline can skip
      it. Makes batched calls to Claude Haiku.

Reference: Peldszus & Stede (2013) — "restatement" annotation operation.
"""

import json
import logging
import re
import time
from collections import defaultdict

import anthropic

logger = logging.getLogger(__name__)

# ── Teaser duplicate removal ──────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _word_set(text: str) -> frozenset:
    """Lowercase, strip punctuation, return a frozenset of words."""
    return frozenset(_PUNCT_RE.sub("", text.lower()).split())


def _containment(a: frozenset, b: frozenset) -> float:
    """
    Fraction of the *shorter* set's words that appear in the other set.
    More lenient than Jaccard: the real-debate instance often has a bit
    more context than the compressed teaser version.
    """
    if not a or not b:
        return 0.0
    shorter = a if len(a) <= len(b) else b
    return len(a & b) / len(shorter)


def remove_teaser_duplicates(
    claims: list[dict],
    threshold: float = 0.75,
    min_gap_ms: int = 120_000,
    min_words: int = 5,
) -> tuple[list[dict], int]:
    """
    Remove claims that are near-duplicates of later claims from the same
    speaker — a signature of podcast teaser clips played at the start of
    an episode before the actual debate begins.

    Algorithm (no API calls):
    - For each same-speaker pair (earlier, later) where the time gap is
      at least min_gap_ms, compute the containment ratio of their texts.
    - If containment >= threshold the earlier claim is a teaser copy:
      drop it and keep the later (canonical) instance.
    - Claims with fewer than min_words words are skipped to avoid false
      positives on very short phrases.

    Returns (deduplicated_claims, n_removed).
    """
    if len(claims) <= 1:
        return claims, 0

    by_time = sorted(claims, key=lambda c: c.get("start_ms", 0))
    word_sets = [_word_set(c.get("text", "")) for c in by_time]
    to_remove: set[int] = set()
    n = len(by_time)

    for i in range(n):
        if i in to_remove:
            continue
        ws_i = word_sets[i]
        if len(ws_i) < min_words:
            continue
        t_i = by_time[i].get("start_ms", 0)
        spk_i = by_time[i].get("speaker")

        for j in range(i + 1, n):
            if j in to_remove:
                continue
            if by_time[j].get("speaker") != spk_i:
                continue
            t_j = by_time[j].get("start_ms", 0)
            if t_j - t_i < min_gap_ms:
                continue
            ws_j = word_sets[j]
            if len(ws_j) < min_words:
                continue
            if _containment(ws_i, ws_j) >= threshold:
                to_remove.add(i)
                logger.debug(
                    "Teaser dedup: dropped '%s' (%.0f ms) — duplicate of "
                    "'%s' (%.0f ms)",
                    by_time[i].get("text", "")[:60], t_i,
                    by_time[j].get("text", "")[:60], t_j,
                )
                break  # i is already gone; no need to check further j's

    kept = [c for k, c in enumerate(by_time) if k not in to_remove]
    # Restore extraction order
    kept.sort(key=lambda c: (c.get("turn_index", 0), c.get("id", "")))
    return kept, len(to_remove)


# ── Restatement detection ─────────────────────────────────────────────────────

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
