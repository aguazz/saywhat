"""
Manual end-to-end test for the download → transcribe pipeline.
Run from the project root:  python test_pipeline.py
Not part of the app — delete or ignore before deploying.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from downloader import download_audio
from transcriber import transcribe

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TEST_URL = "https://www.youtube.com/watch?v=cpbtcsGE0OA"
OUTPUT_DIR = "audio_tmp"
OUTPUT_JSON = "audio_tmp/test_output.json"


def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to MM:SS string."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def main() -> None:
    # --- Load API key ---
    load_dotenv()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("ERROR: ASSEMBLYAI_API_KEY not found in .env file.")
        print("Make sure .env exists and contains: ASSEMBLYAI_API_KEY=your_key_here")
        sys.exit(1)
    print("API key loaded.\n")

    # --- Step 1: Download ---
    print(f"[1/3] Downloading audio from:\n      {TEST_URL}")
    try:
        download_result = download_audio(TEST_URL, OUTPUT_DIR)
    except (ValueError, RuntimeError) as e:
        print(f"ERROR during download: {e}")
        sys.exit(1)

    print("      Done.")
    print(f"      title:            {download_result['title']}")
    print(f"      duration_seconds: {download_result['duration_seconds']:.1f}s")
    print(f"      saved to:         {download_result['path']}\n")

    # --- Step 2: Transcribe ---
    print("[2/3] Sending audio to AssemblyAI (this may take 1–3 minutes)…")
    try:
        transcript = transcribe(download_result["path"], api_key)
    except RuntimeError as e:
        print(f"ERROR during transcription: {e}")
        sys.exit(1)

    print("      Done.\n")
    print(f"      Detected language: {transcript['language']}")
    print(f"      Duration:          {transcript['duration_seconds']:.1f}s")
    print(f"      Utterances found:  {len(transcript['utterances'])}\n")

    # --- Step 3: Print first 5 utterances ---
    print("[3/3] First 5 utterances:")
    print("-" * 60)
    for utt in transcript["utterances"][:5]:
        start = ms_to_timestamp(utt["start_ms"])
        end   = ms_to_timestamp(utt["end_ms"])
        conf  = utt["confidence"]
        print(f"  [{start}–{end}]  Speaker {utt['speaker']}  (confidence: {conf:.2f})")
        print(f"  \"{utt['text']}\"\n")
    print("-" * 60)

    # --- Save full result ---
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)
    print(f"\nFull transcript saved to: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
