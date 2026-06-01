# SayWhat

A web app that takes a debate video (YouTube URL or uploaded file) and produces a
speaker-attributed transcript with low-confidence zones highlighted, then
fact-checks each speaker's claims against peer-reviewed scientific literature.

**Status:** Phase 1 and Phase 2 complete.

---

## What It Does

**Phase 1 — Transcription (current)**
- Paste a YouTube URL or upload a video file (mp4, mp3, wav, m4a)
- Automatically detects English or Spanish
- Bilingual interface: English / Español toggle in the sidebar
- Real-time progress bar with step labels (download → transcribe → analyze)
- Produces a timestamped transcript with each speaker color-coded (Speaker A, Speaker B…)
- Rename any speaker inline — the transcript updates live as you type
- Uncertain words highlighted in yellow, unreliable utterances in red (based on AssemblyAI confidence scores)
- Download transcript as JSON or PDF
- Every transcript gets a shareable link (UUID in URL, stored in SQLite)

**Phase 2 — Debate Analysis (complete)**
- Extracts and classifies every speaker's claims (factual, statistical, causal, moral, and more)
- Detects how claims respond to each other: refutes, undercuts, reframes, supports, evades, and more
- Builds an interactive argument map: claims as nodes, responses as directed edges
- Retrieves evidence from Wikipedia and Semantic Scholar; returns a verdict per checkable claim
- Detects logical fallacies and rhetorical devices per speaker turn
- Scores each speaker: factual reliability and direct-response engagement rate
- Generates a plain-language narrative summary of each speaker's debate performance
- **Find / Filter Claims**: 12-dimension filter panel (speaker, type, thread, text search, verdict, argument status, fallacies, rhetorical devices, connections, checkable, certainty, stance) with live cross-surface sync to the Argument Map and Thread Timeline

See [docs/how-it-works.md](docs/how-it-works.md) for a full explanation of how the analysis works.

---

## Project Structure

```
debate-fact-checker/
│
├── app.py              Main Streamlit web app — UI, routing, session state
├── downloader.py       Downloads audio from YouTube URLs or prepares local files
│                       using yt-dlp + ffmpeg. Enforces 1.5-hour limit.
├── transcriber.py      Sends audio to AssemblyAI, returns structured transcript
│                       with speaker labels, timestamps, and confidence scores.
├── flagging.py         Classifies each utterance and word as ok / uncertain / unreliable
│                       based on AssemblyAI confidence scores.
├── storage.py          SQLite storage (transcripts.db). Handles transcripts, analyses,
│                       claims, and verdict feedback. Each record gets a UUID.
├── exporters.py        Builds PDF (fpdf2) and JSON exports for both phases.
│
├── truth_checker/      Phase 2 — debate analysis pipeline
│   ├── segmenter.py    Groups utterances into speaker turns
│   ├── extractor.py    Extracts claims from each turn (Claude Haiku)
│   ├── classifier.py   Classifies claim type, checkability, evidence quality
│   ├── threader.py     Groups claims by topic into argument threads
│   ├── responder.py    Detects cross-speaker responses and relationship types
│   ├── dung.py         Computes grounded extension (argument acceptability)
│   ├── evidence.py     Retrieves Wikipedia + Semantic Scholar sources
│   ├── verifier.py     Generates fact-check verdicts (Claude Sonnet)
│   ├── rhetorician.py  Detects fallacies and rhetorical devices
│   ├── scorer.py       Computes per-speaker reliability and engagement scores
│   ├── reporter.py     Generates plain-language speaker narrative summaries
│   ├── visualizer.py   Builds pyvis/networkx argument graph
│   ├── translator.py   Translates claims EN ↔ ES on demand
│   └── deduplicator.py Removes near-duplicate claims
│
├── docs/               User-facing documentation
│   ├── how-it-works.md Full explanation of the debate-analysis system with examples
│   ├── claim-types-reference.md  Quick-reference tables for all labels and types
│   ├── limitations.md  What the system cannot do
│   └── ux-recommendations.md  In-app UX improvements (developer-facing)
│
├── papers/             Academic papers underlying the analysis system
├── test_pipeline.py    End-to-end Phase 1 test (not part of the app)
├── requirements.txt    Python dependencies
├── .env.template       Template for environment variables
└── PLAN.md             Full build plan with architecture decisions
```

---

## Prerequisites

Install these before running the app:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.13 | [python.org](https://www.python.org/downloads/) |
| ffmpeg + ffprobe | any recent | [ffmpeg.org](https://ffmpeg.org/download.html) — must be on `PATH` |
| AssemblyAI account | — | [assemblyai.com/dashboard/api-keys](https://www.assemblyai.com/dashboard/api-keys) |

Verify ffmpeg is on your PATH:
```bash
ffmpeg -version
ffprobe -version
```

---

## Setup

**1. Clone or open the project folder in Positron.**

**2. Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**3. Create your `.env` file:**
```bash
# Copy the template
cp .env.template .env
```
Then open `.env` and fill in your API key:
```
ASSEMBLYAI_API_KEY=your_real_key_here
STREAMLIT_APP_URL=http://localhost:8501
```

---

## Running Locally

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ASSEMBLYAI_API_KEY` | Yes | Your AssemblyAI API key from the dashboard |
| `STREAMLIT_APP_URL` | Yes (for sharing) | Base URL of the deployed app, used to build shareable links. Use `http://localhost:8501` for local dev. |

When deploying to Streamlit Community Cloud, these are added under **Settings → Secrets**
in the Streamlit dashboard (not in a `.env` file).

---

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Transcription API | AssemblyAI | Built-in speaker diarization + word-level confidence scores via a simple Python SDK |
| Speech model | `universal-3-pro` (fallback: `universal-2`) | Best accuracy for conversational/debate audio |
| Language | Auto-detect English + Spanish | `language_detection=True` in AssemblyAI config |
| Audio format sent to API | 16 kHz mono mp3 | Optimal for speech-to-text; ffmpeg handles conversion |
| Max debate length | 1.5 hours | Cost and UX control; enforced in `downloader.py` |
| App name | SayWhat | Short, memorable, bilingual-friendly; alludes to "Say what?!" reaction when someone says something questionable |
| UI framework | Streamlit | Python-native, no JavaScript needed, fast to iterate |
| Storage | SQLite | Zero-config, sufficient for MVP; shareable links via UUID |
| Transcript access | Shareable link (no login) | Simpler to build; can add user accounts later without rewriting storage |
| UI language | Bilingual (English + Spanish) | Matches the supported transcription languages |
| Transcription progress | `submit()` + manual REST polling every 3 s | SDK's `transcribe()` is blocking — polling lets the main thread update the bar every 0.5 s using elapsed-time/expected-time scaling |
| Export | JSON + PDF (Helvetica core font, Latin-1 safe) | Two side-by-side download buttons; speaker names substituted before export; filenames include datetime slug |
| Shareable links | UUID in URL (`?id=`), stored in SQLite | No login needed; `st.query_params` loads transcript on first render; URL bar updated silently after save |

---

## Build Progress

- [x] P1 — Project scaffold
- [x] P2 — YouTube downloader (`downloader.py`)
- [x] P3 — AssemblyAI transcriber (`transcriber.py`)
- [x] P4 — CLI test script (`test_pipeline.py`)
- [x] P5 — Confidence flagging (`flagging.py`)
- [x] P6 — Basic Streamlit UI (`app.py`)
- [x] P7 — Speaker renaming + highlights
- [x] P8 — File upload support (500 MB guard, file size display)
- [x] P9 — PDF + JSON export (`exporters.py`)
- [x] P10 — SQLite storage + shareable links (`storage.py`)
- [ ] P11 — Deploy to Streamlit Community Cloud
- [x] P16–P35 — Phase 2: debate analysis pipeline (all complete)

---

## Cost Reference

| Item | Cost |
|------|------|
| Transcription | ~$0.65 / hour of audio (AssemblyAI) |
| Hosting | $0 (Streamlit Community Cloud free tier) |
| Fact-checking LLM | ~$0.002 / debate (Claude Haiku) — Phase 2 |
| Evidence APIs | Free (Semantic Scholar, PubMed, CrossRef) |

A typical 1.5-hour debate costs roughly **$1.00** to transcribe.
