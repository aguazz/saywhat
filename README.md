# SayWhat

A web app that takes a debate video (YouTube URL or uploaded file) and produces a
speaker-attributed transcript with low-confidence zones highlighted, then
fact-checks each speaker's claims against peer-reviewed scientific literature.

**Status:** Phase 1 in progress — transcription pipeline.

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

**Phase 2 — Fact-Checking (planned)**
- Extracts factual claims from each speaker's turns
- Searches Semantic Scholar, PubMed, and CrossRef for supporting or contradicting evidence
- Scores each source by study type, recency, citation count, and conflict of interest
- Returns a verdict per claim: Supported / Contradicted / Contested / Insufficient evidence

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
├── storage.py          SQLite storage (transcripts.db). save_transcript(), load_transcript(),
│                       list_recent(). Each transcript gets a UUID for shareable links.
├── exporters.py        Builds PDF (fpdf2) and prepares JSON exports. substitute_names()
│                       replaces speaker IDs with user-given names before export.
│
├── test_pipeline.py    Manual end-to-end test: downloads a YouTube clip, transcribes it,
│                       and saves the result to audio_tmp/test_output.json. Not part of the app.
│
├── audio_tmp/          Temporary audio files (downloaded + processed). Not committed to git.
│
├── requirements.txt    Python dependencies
├── .env.template       Template for environment variables — copy to .env and fill in keys
├── .env                Your real API keys — never committed to git
├── CLAUDE.md           Instructions for Claude when editing this project
└── PLAN.md             Full build plan with architecture decisions and prompt sequence
```

> `fact_checker/` (extractor, searcher, scorer) will be added in Phase 2.

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
- [ ] P12–P15 — Phase 2: fact-checking pipeline

---

## Cost Reference

| Item | Cost |
|------|------|
| Transcription | ~$0.65 / hour of audio (AssemblyAI) |
| Hosting | $0 (Streamlit Community Cloud free tier) |
| Fact-checking LLM | ~$0.002 / debate (Claude Haiku) — Phase 2 |
| Evidence APIs | Free (Semantic Scholar, PubMed, CrossRef) |

A typical 1.5-hour debate costs roughly **$1.00** to transcribe.
