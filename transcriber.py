import time

import assemblyai as aai
import requests


def transcribe(audio_path: str, api_key: str) -> dict:
    """
    Transcribe a local audio file using AssemblyAI with speaker diarization.

    Submits the file to AssemblyAI, waits for completion (the SDK handles
    upload and polling), and returns a structured dict. Auto-detects English
    or Spanish. Produces utterance-level and word-level confidence scores,
    which the flagging layer uses to highlight uncertain zones.

    Args:
        audio_path: Path to a local mp3/wav/m4a file.
        api_key:    AssemblyAI API key. Do not pass a Bearer-prefixed value —
                    the STT API uses the raw key with no prefix.

    Returns:
        {
            "language":         str,    # "en" or "es" (ISO 639-1)
            "duration_seconds": float,  # total audio length
            "utterances": [
                {
                    "speaker":    str,   # "A", "B", "C", …
                    "start_ms":   int,   # utterance start in milliseconds
                    "end_ms":     int,   # utterance end in milliseconds
                    "text":       str,
                    "confidence": float, # 0.0 – 1.0, utterance-level
                    "words": [
                        {
                            "text":       str,
                            "start_ms":   int,
                            "end_ms":     int,
                            "confidence": float,
                        }
                    ],
                }
            ],
        }

    Raises:
        RuntimeError: if AssemblyAI returns an error status.
    """
    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(
        # speech_models is REQUIRED. Raw strings only — enum aliases do not exist.
        speech_models=["universal-3-pro", "universal-2"],
        speaker_labels=True,       # diarization: who said what
        language_detection=True,   # auto-detect English or Spanish
        punctuate=True,
        format_text=True,
    )

    transcript = aai.Transcriber(config=config).transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(
            f"AssemblyAI transcription failed: {transcript.error}"
        )

    utterances = []
    for utt in (transcript.utterances or []):
        words = [
            {
                "text":       w.text,
                "start_ms":   w.start,
                "end_ms":     w.end,
                "confidence": float(w.confidence or 0.0),
            }
            for w in (utt.words or [])
        ]
        utterances.append({
            "speaker":    utt.speaker,
            "start_ms":   utt.start,
            "end_ms":     utt.end,
            "text":       utt.text,
            "confidence": float(utt.confidence or 0.0),
            "words":      words,
        })

    return {
        "language":         getattr(transcript, "language_code", "unknown") or "unknown",
        "duration_seconds": float(transcript.audio_duration or 0.0),
        "utterances":       utterances,
    }


def transcribe_with_progress(
    audio_path: str,
    api_key: str,
    audio_duration_seconds: float,
    on_progress,
) -> dict:
    """
    Like transcribe(), but calls on_progress(fraction: float) throughout.

    Uses submit() instead of transcribe() so the main thread stays free to
    drive the progress bar. Polls the REST API every 3 s; updates the caller
    every 0.5 s using elapsed-time vs estimated-duration to scale 0.0 → 1.0.

    Estimated transcription time: ~12 % of audio duration, minimum 30 s.
    The bar slows near 1.0 if the job takes longer than the estimate — it
    will never reach 1.0 until the job actually completes.

    Args:
        audio_path:             Path to a local mp3/wav file.
        api_key:                AssemblyAI API key (no Bearer prefix).
        audio_duration_seconds: Used to estimate completion time.
        on_progress:            Callable(float) — receives values from 0.0 to 1.0.

    Raises:
        RuntimeError: if AssemblyAI returns an error status.
    """
    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"],
        speaker_labels=True,
        language_detection=True,
        punctuate=True,
        format_text=True,
    )

    # Submit without blocking — returns immediately with status "queued"
    job = aai.Transcriber(config=config).submit(audio_path)
    transcript_id = job.id

    headers = {"Authorization": api_key}
    poll_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    expected_secs = max(audio_duration_seconds * 0.12, 30)

    on_progress(0.0)
    start = time.monotonic()
    resp = {}

    while True:
        # Update bar every 0.5 s for 3 s, then hit the API once
        poll_deadline = time.monotonic() + 3.0
        while time.monotonic() < poll_deadline:
            elapsed = time.monotonic() - start
            # Asymptotic scale: approaches 1.0 but never reaches it until done
            frac = 1.0 - 1.0 / (1.0 + elapsed / expected_secs)
            on_progress(min(frac, 0.95))
            time.sleep(0.5)

        resp = requests.get(poll_url, headers=headers, timeout=10).json()
        status = resp.get("status")

        if status == "completed":
            on_progress(1.0)
            break
        if status == "error":
            raise RuntimeError(
                f"AssemblyAI transcription failed: {resp.get('error', 'unknown error')}"
            )

    return _parse_rest_response(resp)


def _parse_rest_response(resp: dict) -> dict:
    """Convert a completed AssemblyAI REST response into our standard transcript dict."""
    utterances = []
    for utt in (resp.get("utterances") or []):
        words = [
            {
                "text":       w["text"],
                "start_ms":   w["start"],
                "end_ms":     w["end"],
                "confidence": float(w.get("confidence") or 0.0),
            }
            for w in (utt.get("words") or [])
        ]
        utterances.append({
            "speaker":    utt["speaker"],
            "start_ms":   utt["start"],
            "end_ms":     utt["end"],
            "text":       utt["text"],
            "confidence": float(utt.get("confidence") or 0.0),
            "words":      words,
        })

    return {
        "language":         resp.get("language_code") or "unknown",
        "duration_seconds": float(resp.get("audio_duration") or 0.0),
        "utterances":       utterances,
    }
