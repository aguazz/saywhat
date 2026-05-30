"""
CLI test for Phase 2a: segment → extract → classify → thread.
Run from the project root:  python -m truth_checker.test_phase2a
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root (one level above this file) so imports work regardless
# of where the script is invoked from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

import storage
from truth_checker.segmenter  import segment_turns
from truth_checker.extractor  import extract_claims_from_turn
from truth_checker.classifier import classify_claim
from truth_checker.threader   import group_into_threads


def ms_to_ts(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def print_table(claims: list[dict]) -> None:
    col_widths = {"thread": 20, "speaker": 8, "time": 6, "type": 13, "check": 9, "claim": 80}
    header = (
        f"{'Thread':<{col_widths['thread']}} "
        f"{'Speaker':<{col_widths['speaker']}} "
        f"{'Time':<{col_widths['time']}} "
        f"{'Type':<{col_widths['type']}} "
        f"{'Checkable':<{col_widths['check']}} "
        f"Claim"
    )
    sep = "-" * (sum(col_widths.values()) + len(col_widths) - 1)
    print(header)
    print(sep)

    sorted_claims = sorted(claims, key=lambda c: (c.get("thread_id", ""), c.get("start_ms", 0)))
    for c in sorted_claims:
        thread  = c.get("thread_id", "")[:col_widths["thread"]]
        speaker = c.get("speaker", "")[:col_widths["speaker"]]
        time    = ms_to_ts(c.get("start_ms", 0))
        ctype   = c.get("claim_type", "")[:col_widths["type"]]
        check   = "yes" if c.get("checkable") else "no"
        claim   = c.get("text", "")
        if len(claim) > col_widths["claim"]:
            claim = claim[: col_widths["claim"] - 1] + "…"
        print(
            f"{thread:<{col_widths['thread']}} "
            f"{speaker:<{col_widths['speaker']}} "
            f"{time:<{col_widths['time']}} "
            f"{ctype:<{col_widths['type']}} "
            f"{check:<{col_widths['check']}} "
            f"{claim}"
        )


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env")
        sys.exit(1)

    # ── 1. Find most recent transcript ─────────────────────────────────────
    print("\n[1/4] Loading most recent transcript from database…")
    try:
        recent = storage.list_recent(limit=1)
    except Exception as exc:
        print(f"ERROR reading database: {exc}")
        sys.exit(1)

    if not recent:
        print("ERROR: No transcripts found in the database. Run the app to create one first.")
        sys.exit(1)

    meta = recent[0]
    print(f"      Found: '{meta['title']}' ({meta['id'][:8]}…) — {meta['language'].upper()}, "
          f"{int(meta['duration_seconds'] // 60)}m {int(meta['duration_seconds'] % 60)}s")

    try:
        record = storage.load_transcript(meta["id"])
    except Exception as exc:
        print(f"ERROR loading transcript: {exc}")
        sys.exit(1)

    utterances = record["transcript"].get("utterances", [])
    print(f"      {len(utterances)} utterances loaded.")

    # ── 2. Segment ─────────────────────────────────────────────────────────
    print("\n[2/4] Segmenting utterances into speaker turns…")
    try:
        turns = segment_turns(utterances)
    except Exception as exc:
        print(f"ERROR during segmentation: {exc}")
        sys.exit(1)
    print(f"      {len(turns)} turns produced.")

    # ── 3. Extract claims ──────────────────────────────────────────────────
    print(f"\n[3/4] Extracting claims from {len(turns)} turns (Claude Haiku)…")
    all_claims: list[dict] = []
    for i, turn in enumerate(turns, 1):
        print(f"      Turn {i}/{len(turns)} — Speaker {turn['speaker']} "
              f"[{ms_to_ts(turn['start_ms'])}]", end="", flush=True)
        try:
            claims = extract_claims_from_turn(turn, api_key)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue
        all_claims.extend(claims)
        print(f"  → {len(claims)} claim(s)")

    print(f"      Total claims extracted: {len(all_claims)}")

    # ── 4. Classify claims ─────────────────────────────────────────────────
    print(f"\n[4/4a] Classifying {len(all_claims)} claims (Claude Haiku)…")
    classified: list[dict] = []
    for i, claim in enumerate(all_claims, 1):
        print(f"      Claim {i}/{len(all_claims)}", end="", flush=True)
        try:
            result = classify_claim(claim, api_key)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            result = claim
        classified.append(result)
        print(f"  [{result.get('claim_type', '?')}] {'yes' if result.get('checkable') else 'no'}")

    # ── 5. Group into threads ──────────────────────────────────────────────
    print(f"\n[4/4b] Grouping {len(classified)} claims into argument threads (Claude Sonnet)…")
    try:
        threads = group_into_threads(classified, api_key)
    except Exception as exc:
        print(f"ERROR during threading: {exc}")
        threads = []

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"  Turns:   {len(turns)}")
    print(f"  Claims:  {len(classified)}")
    print(f"  Threads: {len(threads)}")
    for t in threads:
        n = len(t.get("claim_ids", []))
        print(f"    • [{t['thread_id']}] {t['topic']} ({n} claim{'s' if n != 1 else ''})")
    print()

    print_table(classified)

    # ── Save output ────────────────────────────────────────────────────────
    out_path = ROOT / "audio_tmp" / "phase2a_test_output.json"
    out_path.parent.mkdir(exist_ok=True)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"claims": classified, "threads": threads}, f, ensure_ascii=False, indent=2)
        print(f"\nOutput saved to {out_path}")
    except Exception as exc:
        print(f"\nERROR saving output: {exc}")


if __name__ == "__main__":
    main()
