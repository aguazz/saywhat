# SayWhat — Build & Deploy Plan

## What We Are Building

A web app where a user pastes a YouTube URL (or uploads a video file) and gets back:

1. **Phase 1 (now):** A clean, speaker-attributed transcript with timestamps and visual markers for low-confidence zones (overlapping speech, noise, crosstalk).
2. **Phase 2 (later):** Automated fact-checking of each speaker's claims, ranked by source credibility (peer-reviewed journals, study quality, conflict-of-interest flags).

---

## Who This Is For (Context)

- Builder: R user, limited full-stack experience, using **Positron + Claude**.
- Budget: **$20–50/month** all-in.
- Timeline: Iterative — Phase 1 MVP first, Phase 2 layered on top.

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Language scope | English + Spanish (auto-detected) |
| Max debate length | **1.5 hours** — videos longer than this are rejected with a clear error |
| Domain name | Use free `.streamlit.app` URL for MVP |
| Transcript storage | **Stored** — transcripts are saved and accessible via a shareable link |
| Transcript access model | **Shareable link** (no user login for now; architecture allows adding accounts later without rewriting storage) |
| App interface language | **Bilingual** — all UI labels, buttons, and messages in both English and Spanish |
| Monetization | **None for now** — launch fully free, add Stripe later if needed |

---

## Architecture Overview

```
User (browser)
    │
    ▼
Streamlit Web UI          ← Python, hosted free on Streamlit Community Cloud
    │
    ├─ YouTube URL  →  yt-dlp  →  audio file (mp3)   [max 1.5 h enforced]
    ├─ File upload  →  audio file (mp3)               [max 1.5 h enforced]
    │
    ▼
ffmpeg pre-processing
    • Normalize volume
    • Trim silence at start/end
    • Enforce 1.5 h cap
    │
    ▼
AssemblyAI Transcription API
    • Language: English or Spanish (auto-detect)
    • Speaker diarization (who said what)
    • Word-level confidence scores
    • Utterance-level timestamps
    │
    ▼
Confidence Flagging Layer (local Python)
    • confidence < 0.60 → yellow (uncertain word)
    • confidence < 0.40 → red (unreliable zone / likely overlap)
    │
    ▼
Structured Transcript JSON
    │
    ├─ SQLite DB  ←  stored with unique ID for shareable link
    │
    ▼
Transcript Viewer (Streamlit)
    • Color-coded by speaker (renamed inline by user)
    • Word-level highlights: yellow (uncertain) / red (unreliable)
    • Utterance-level badges: ⚠ uncertain · 🔴 unreliable
    • Download as JSON  [built]
    • Export as PDF     [P9 — not yet built]
```

---

## Compute Decision — Why AssemblyAI for Phase 1

| Option | Setup Difficulty | Quality | Cost / 1.5 h debate | Overlap Detection |
|--------|-----------------|---------|---------------------|-------------------|
| **AssemblyAI API** | Easy (REST API) | Very good | ~$0.55–$0.98 | Yes — word confidence + diarization |
| WhisperX on Modal.com | Medium | Best | ~$0.15–$0.45 (GPU) | Yes — word timestamps + pyannote |
| Groq Whisper API | Easiest | Good | Free tier | No diarization |

**Recommendation: Start with AssemblyAI.** Once you have paying users, the backend can be swapped to WhisperX on Modal (~3× cheaper) without changing a single line of the UI.

---

## Tech Stack

| Layer | Tool | Why | Cost |
|-------|------|-----|------|
| UI framework | [Streamlit](https://streamlit.io) | Python-native, like R Shiny. No HTML/JS needed. | Free |
| Video download | [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloads from YouTube + 1000 other sites | Free |
| Audio processing | [ffmpeg](https://ffmpeg.org) | Converts video → audio, enforces length cap, normalizes | Free |
| Transcription | [AssemblyAI](https://www.assemblyai.com) | Speaker diarization + confidence scores via simple API | ~$0.65/hr |
| Storage | SQLite (local file) | Zero-config database, sufficient for MVP | Free |
| Hosting | [Streamlit Community Cloud](https://streamlit.io/cloud) | Free public hosting from GitHub | Free |
| Code | Python 3.13 | Close to R, massive ecosystem (you already have 3.13 installed — works perfectly) | Free |
| IDE | Positron | Already using it | Free |
| Version control | GitHub (private repo) | Required by Streamlit Community Cloud | Free |

---

## Quality & Reliability Strategy

| Problem | Solution |
|---------|----------|
| Two speakers talking simultaneously | AssemblyAI diarization + confidence < 0.5 → yellow warning |
| Speaker interrupts mid-word | Word-level timestamps expose the cut; flagged in UI |
| Poor audio (crowd noise, mic feedback) | ffmpeg pre-processing: normalize volume |
| Non-English speech | AssemblyAI auto-detects English vs Spanish |
| Debate > 1.5 hours | Rejected at download step with friendly error message |
| Video has no speech (music intro) | AssemblyAI skips silence automatically |

---

## Phase 2 — Fact-Checking (Design Sketch)

> Not building yet — but structure of Phase 1 code is designed to plug Phase 2 in cleanly.

```
Transcript (speaker-attributed claims)
    │
    ▼
Claim Extraction  (Claude Haiku API  ~$0.002 per debate)
    • "Extract factual claims from this text as a JSON list"
    │
    ▼
Evidence Search  (all free APIs)
    • Semantic Scholar  — 200M+ papers
    • PubMed/NCBI       — biomedical
    • CrossRef          — DOI lookup + journal metadata
    • CORE              — open access full text
    │
    ▼
Source Quality Scoring
    • Study type: RCT > meta-analysis > observational > opinion
    • Journal impact factor (via CrossRef)
    • Conflict of interest (funding / author affiliations)
    • Recency
    │
    ▼
Verdict per Claim
    Supported | Contradicted | Contested | Insufficient evidence
    + confidence score + top 3 sources with links
```

---

## Monetization Path

| Tier | Price | Limit | Notes |
|------|-------|-------|-------|
| Free | $0 | 2 transcriptions/month | Acquire users |
| Basic | $5/month | 20 transcriptions | Covers costs |
| Pro | $15/month | Unlimited + fact-checking | Main revenue tier |
| API | $0.10/transcription | Pay per use | For media orgs |

---

## Full Cost Breakdown at Scale

| Users/month | Debates processed | AssemblyAI cost | Hosting | Total |
|-------------|------------------|----------------|---------|-------|
| 10 (MVP) | ~20 | ~$13 | $0 | ~$13 |
| 50 | ~100 | ~$65 | $7 (Render) | ~$72 |
| 200+ | Switch to WhisperX on Modal | ~$20–30 | $7 | ~$30 |

---

## Build Order

- [x] **P1** — Project scaffold (folders, requirements.txt, .gitignore, .env template)
- [x] **P2** — YouTube downloader (yt-dlp + ffmpeg + 1.5 h cap)
- [x] **P3** — AssemblyAI transcriber (English + Spanish, speaker diarization)
- [x] **P4** — CLI test script (proves pipeline works before building UI)
- [x] **P5** — Confidence flagging (yellow/red zones)
- [x] **P6** — Basic Streamlit UI (URL input → transcript display)
- [x] **P6a** — Real-time progress bar (yt-dlp hooks for download; submit/poll REST loop for transcription)
- [x] **P6b** — JSON download button added to transcript section
- [x] **P7** — Speaker renaming + word-level low-confidence highlights in UI
- [x] **P8** — File upload support
- [x] **P9** — Export (PDF + JSON download buttons)
- [x] **P10** — SQLite storage + shareable links
- [ ] **P11** — Deploy to Streamlit Community Cloud
- [~] **P12** — ~~Phase 2: Claim extraction~~ → superseded by TRUTH_CHECKER_PLAN.md P18–P20
- [~] **P13** — ~~Phase 2: Evidence search~~ → superseded by TRUTH_CHECKER_PLAN.md P23
- [~] **P14** — ~~Phase 2: Source quality scoring~~ → superseded by TRUTH_CHECKER_PLAN.md P24
- [~] **P15** — ~~Phase 2: Fact-check tab in UI~~ → superseded by TRUTH_CHECKER_PLAN.md P22, P25, P29, P31, P33
- [x] **P16** — Storage schema: `analyses`, `claims`, `verdict_feedback` tables
- [x] **P17** — `truth_checker/` package + `segmenter.py`
- [x] **P18** — `extractor.py` — claim extraction per turn (Claude Haiku)
- [x] **P19** — `classifier.py` — claim type + checkability (Claude Haiku)
- [x] **P20** — `threader.py` — thread grouping (Claude Sonnet)
- [x] **P21** — `test_phase2a.py` — CLI pipeline test
- [x] **P22** — `app.py` — Analysis tab, claim table, CSV export
- [x] **P23** — `evidence.py` — Wikipedia + Semantic Scholar retrieval
- [x] **P24** — `verifier.py` — factual verdict with reasoning (Claude Sonnet)
- [x] **P25** — `app.py` — Run Fact-Check, verdict badges, expanders, 👎 feedback
- [x] **P26** — `translator.py` + EN↔ES claim toggle in `app.py`
- [x] **P27** — `responder.py` — cross-speaker response detection (Claude Sonnet)
- [x] **P28** — `visualizer.py` — pyvis argument graph; pyvis + networkx in requirements
- [x] **P29** — `app.py` — Claims/Argument Map sub-tabs, Detect Responses, graph legend
- [x] **P30** — `rhetorician.py` — fallacy + device detection (Claude Sonnet)
- [x] **P31** — `app.py` — Rhetorical Profile sub-tab
- [x] **P32** — `scorer.py` + `reporter.py` — per-speaker scores and narrative
- [x] **P33** — `app.py` — Speaker Report sub-tab
- [x] **P34** — `exporters.py` — analysis PDF/JSON export + `app.py` download buttons
- [x] **P35** — `storage.py` + `app.py` — analysis shareable link

---

## Prompt Sequence

> Each prompt below is a self-contained briefing to paste into Claude (in Positron).
> You do not need prior context in the chat — copy the whole block each time.
> Complete one prompt fully before moving to the next.

---

### Prompt 1 — Project Scaffold

```
I am building a debate fact-checker web app in Python.
Stack: Streamlit (UI), AssemblyAI (transcription), yt-dlp + ffmpeg (video/audio), SQLite (storage).
Hosting: Streamlit Community Cloud (free tier).

Create the following project structure in the current directory:

debate-fact-checker/
├── app.py                  ← empty for now, just: import streamlit as st
├── transcriber.py          ← empty for now
├── downloader.py           ← empty for now
├── flagging.py             ← empty for now
├── storage.py              ← empty for now
├── requirements.txt        ← with these packages: streamlit, assemblyai, yt-dlp, python-dotenv, fpdf2
├── .env.template           ← template showing which keys are needed, no actual values
├── .gitignore              ← must exclude .env, __pycache__, *.pyc, audio_tmp/, *.db
├── CLAUDE.md               ← one rule: always fetch https://www.assemblyai.com/docs/llms.txt before writing AssemblyAI code
└── audio_tmp/              ← empty folder with a .gitkeep file inside

Do not write any logic yet — just the scaffold.
After creating the files, show me the final folder structure.
```

---

### Prompt 2 — YouTube Downloader

```
I am building a debate fact-checker web app.
Stack: Python, yt-dlp, ffmpeg.

Edit the file `downloader.py`. Write a single function:

    download_audio(source: str, output_dir: str) -> dict

Where `source` is either a YouTube URL or a local file path (mp4/mp3/wav).
The function must:
1. If source is a URL: use yt-dlp to download the best audio stream. Save as mp3 to output_dir.
2. If source is a local file: copy it to output_dir as-is (no re-encoding needed).
3. After obtaining the file, use ffmpeg to:
   a. Check the duration. If it exceeds 5400 seconds (1.5 hours), raise a ValueError with a clear message.
   b. Normalize audio volume (ffmpeg loudnorm filter).
   c. Output a clean mono mp3 at 16kHz (ideal for speech transcription APIs).
4. Return a dict: {"path": str, "duration_seconds": float, "title": str}
   - title: video title from yt-dlp metadata, or filename if local file.

Use subprocess to call ffmpeg. Do not import ffmpeg-python.
Handle errors gracefully: if yt-dlp fails (private video, geo-block, etc.), raise ValueError with a user-friendly message.
Add a short docstring to the function explaining what it does and what errors it raises.
```

---

### Prompt 3 — AssemblyAI Transcriber

```
I am building a debate fact-checker web app.
Stack: Python 3.13, AssemblyAI SDK (pip package: assemblyai).

Before writing any code, fetch https://www.assemblyai.com/docs/llms.txt to verify
current parameter names and SDK patterns.

Edit the file `transcriber.py`. Write a single function:

    transcribe(audio_path: str, api_key: str) -> dict

The function must:
1. Set aai.settings.api_key = api_key.
2. Create a TranscriptionConfig with:
   - speech_models=["universal-3-pro", "universal-2"]   ← REQUIRED, ordered fallback list
   - speaker_labels=True                                  ← speaker diarization
   - language_detection=True                              ← auto-detect English or Spanish
   - punctuate=True
   - format_text=True
3. Call aai.Transcriber(config=config).transcribe(audio_path).
   The SDK handles upload and polling automatically — do NOT write a manual polling loop.
4. If transcript.status == aai.TranscriptStatus.error, raise RuntimeError(transcript.error).
5. Return a dict with this structure:
   {
     "language": str,             # "en" or "es"
     "duration_seconds": float,
     "utterances": [
       {
         "speaker": str,          # "A", "B", "C", etc.
         "start_ms": int,
         "end_ms": int,
         "text": str,
         "confidence": float,     # 0.0 to 1.0, utterance-level average
         "words": [
           {"text": str, "start_ms": int, "end_ms": int, "confidence": float}
         ]
       }
     ]
   }

Important:
- speech_models values are raw strings — do NOT use enum aliases like aai.SpeechModel.universal_3_pro
  (those do not exist and will fail at runtime).
- The API key is passed as a parameter — do not read from the environment inside this function.
- The Authorization header used by the SDK does NOT use a "Bearer" prefix (this is correct for STT).
```

---

### Prompt 4 — CLI Test Script

```
I am building a debate fact-checker web app.
I have two files already written:
- downloader.py  with function  download_audio(source, output_dir) -> dict
- transcriber.py with function  transcribe(audio_path, api_key) -> dict

Write a file called `test_pipeline.py` that:
1. Reads ASSEMBLYAI_API_KEY from a .env file using python-dotenv.
2. Defines TEST_URL = "https://www.youtube.com/watch?v=cpbtcsGE0OA"  (a short public debate clip — replace if needed)
3. Calls download_audio(TEST_URL, "audio_tmp/") and prints the returned dict.
4. Calls transcribe(result["path"], api_key) and prints:
   - The detected language
   - Total duration
   - First 5 utterances with speaker label, timestamp, text, and confidence score
5. Saves the full result dict to a file called audio_tmp/test_output.json.

This script is for manual testing only — not part of the app.
Print clear progress messages so I can see what step is running.
```

---

### Prompt 5 — Confidence Flagging

```
I am building a debate fact-checker web app.
Transcripts come from AssemblyAI as a dict of utterances, each with a "confidence" score (0.0–1.0)
and a "words" list where each word also has its own "confidence" score.

Edit the file `flagging.py`. Write a single function:

    flag_transcript(transcript: dict) -> dict

It takes the transcript dict from transcriber.py and returns the same dict, but with two fields added
to each utterance:
- "flag": one of "ok", "uncertain", "unreliable"
  - "ok"         if utterance confidence >= 0.60
  - "uncertain"  if utterance confidence is 0.40–0.59
  - "unreliable" if utterance confidence < 0.40
- "flagged_words": list of word dicts (from the words list) where word confidence < 0.60

Also add a top-level field to the returned dict:
- "has_low_confidence_zones": bool  (True if any utterance is not "ok")
- "low_confidence_count": int        (number of utterances flagged as uncertain or unreliable)

Do not modify the original dict — return a new one (use copy.deepcopy).
```

---

### Prompt 6 — Basic Streamlit UI

```
I am building a debate fact-checker web app.
Stack: Streamlit (Python). I have these modules ready:
- downloader.py  →  download_audio(source, output_dir) -> dict
- transcriber.py →  transcribe(audio_path, api_key) -> dict
- flagging.py    →  flag_transcript(transcript) -> dict

Edit `app.py` to build a bilingual Streamlit web app (English + Spanish).

LANGUAGE TOGGLE:
At the top of the sidebar, add a selectbox: Language / Idioma → ["English", "Español"].
Store the choice in st.session_state["lang"]. Default: "English".
Define a dict LABELS at the top of the file with every user-visible string in both languages, e.g.:
  LABELS = {
    "title":    {"English": "Debate Fact-Checker", "Español": "Verificador de Debates"},
    "subtitle": {"English": "Paste a YouTube URL...", "Español": "Pega una URL de YouTube..."},
    ...  (add all labels used in the UI)
  }
Use LABELS[key][lang] everywhere instead of hardcoded strings.

PAGE TITLE: LABELS["title"][lang]
SUBTITLE: LABELS["subtitle"][lang]

INPUT SECTION:
- A text input for YouTube URL
- The word "or" / "o" centered between them
- A file uploader accepting mp4, mp3, wav, m4a files
- A "Transcribe" / "Transcribir" button
- When clicked:
  1. Validate: exactly one input must be provided. Show st.error if invalid.
  2. Show st.spinner with bilingual text.
  3. Call download_audio, then transcribe, then flag_transcript.
  4. Store the flagged transcript in st.session_state["transcript"].
  5. If any error is raised, show it with st.error and stop.

TRANSCRIPT SECTION (only shown if st.session_state["transcript"] exists):
- Show a summary line: detected language, duration, number of speakers, number of flagged zones.
- For each utterance, render one row:
  [MM:SS]  Speaker X  "utterance text"
  - If flag == "uncertain": show a yellow ⚠ icon after the text
  - If flag == "unreliable": show a red 🔴 icon and italicize the text
- Use st.markdown with unsafe_allow_html=True for the colored rendering.

Read ASSEMBLYAI_API_KEY from environment (use os.environ.get).
Keep app.py under 180 lines — import helper logic from the other modules.
```

---

### Prompt 7 — Speaker Renaming + Highlighted Words

```
I am building a debate fact-checker web app in Streamlit.
The app already shows a transcript (stored in st.session_state["transcript"]).
Speakers are labeled "A", "B", "C", etc.

Make two improvements to `app.py`:

IMPROVEMENT 1 — Speaker renaming:
After the transcript appears, show a bilingual section heading ("Name the Speakers" / "Nombrar a los hablantes").
For each unique speaker in the transcript (A, B, C...), show a text_input:
  "Speaker A's name:" (empty default, placeholder e.g. "e.g. Joe Biden")
When the user fills in names, replace "Speaker A" with the given name throughout
the rendered transcript. Store the name mapping in st.session_state["speaker_names"].
The replacement must be live (no extra button needed — Streamlit re-renders on input change).

IMPROVEMENT 2 — Highlighted uncertain words:
For each utterance flagged as "uncertain" or "unreliable", in the rendered text,
wrap each word that appears in "flagged_words" in an HTML <mark> span:
- uncertain word: background-color #fff3cd (yellow)
- unreliable utterance: background-color #f8d7da (red-ish)
Use unsafe_allow_html=True.

Do not change anything else in the file.
```

---

### Prompt 8 — File Upload Support

```
I am building a debate fact-checker web app in Streamlit.
The downloader.py already handles both URLs and local file paths.
However, Streamlit file uploads return an in-memory UploadedFile object, not a path.

Edit `app.py` to handle file uploads correctly:
1. When the user uploads a file via st.file_uploader, save it to audio_tmp/ with its original filename.
2. Pass the saved file path to download_audio() as the source argument.
3. After transcription is complete, delete the temporary file from audio_tmp/.

Also add a check: if the uploaded file is larger than 500 MB, show st.error and stop before saving.
Display the file size in the UI next to the uploader ("Max 500 MB, max 1.5 hours").
```

---

### Prompt 9 — Export Buttons

```
I am building a debate fact-checker web app in Streamlit.
After transcription, st.session_state["transcript"] contains the flagged transcript dict,
and st.session_state["speaker_names"] contains the name mapping (e.g. {"A": "Biden", "B": "Trump"}).

Edit `app.py` to add two download buttons below the transcript:

BUTTON 1 — Download JSON:
Export the full transcript dict (with speaker names substituted) as a JSON file.
Filename: "transcript_{title}_{datetime}.json" (title from transcript metadata, slugified).

BUTTON 2 — Download PDF:
Generate a clean PDF using the fpdf2 library.
Format:
  - Title at top: "Debate Transcript — {title}"
  - Subtitle: "Generated by Debate Fact-Checker · {date}"
  - For each utterance, one paragraph: "[MM:SS] SpeakerName: text"
  - Flagged utterances get a note: "(⚠ low confidence)" appended.
  - Font: Arial, size 11. Page margins 20mm.

Use st.download_button for both.
Write a helper function build_pdf(transcript, speaker_names) -> bytes in a new file called exporters.py.
Import and call it from app.py.
```

---

### Prompt 10 — SQLite Storage + Shareable Links

> **Before running this prompt, answer the Open Questions at the top of this plan.**
> The prompt below assumes Option A (shareable link, no user login).
> If you choose Option B (user accounts), ask Claude to rewrite this prompt for you first.

```
I am building a debate fact-checker web app in Streamlit.
I want to store transcripts in SQLite so they can be accessed later via a unique shareable URL.
No user accounts — each transcript gets a UUID that becomes its URL parameter.

Edit `storage.py`:
1. On import, create (if not exists) a SQLite database file called transcripts.db with one table:
   CREATE TABLE IF NOT EXISTS transcripts (
     id TEXT PRIMARY KEY,       -- UUID4
     title TEXT,
     created_at TEXT,           -- ISO 8601
     language TEXT,
     duration_seconds REAL,
     transcript_json TEXT,      -- full JSON blob
     speaker_names_json TEXT    -- JSON mapping e.g. {"A": "Biden"}
   )

2. Write these functions:
   - save_transcript(transcript: dict, speaker_names: dict, title: str) -> str
     Saves and returns the UUID.
   - load_transcript(transcript_id: str) -> dict | None
     Returns the full record or None if not found.
   - list_recent(limit: int = 20) -> list[dict]
     Returns the most recent N transcripts (id, title, created_at, language, duration_seconds).

Edit `app.py`:
3. After a successful transcription, call save_transcript and display:
   "Transcript saved. Shareable link: [copy this URL]"
   Construct the URL as: {base_url}?id={uuid}
   where base_url is read from an env var STREAMLIT_APP_URL (fallback: "http://localhost:8501").
4. On app load, read the query param ?id= from st.query_params.
   If present, load the transcript from storage and populate st.session_state["transcript"]
   and st.session_state["speaker_names"] automatically.
```

---

### Prompt 11 — Deploy to Streamlit Community Cloud

> This is a checklist, not a code prompt. Follow these steps manually.

```
Deployment steps for Streamlit Community Cloud:

1. Make sure these files are committed to your GitHub repo:
   - app.py, transcriber.py, downloader.py, flagging.py, storage.py, exporters.py
   - requirements.txt
   - audio_tmp/.gitkeep
   - .gitignore  (confirm .env and *.db are excluded)
   DO NOT commit: .env, transcripts.db, audio_tmp/*.mp3

2. Go to https://share.streamlit.io → "New app"
   - Repo: your GitHub repo
   - Branch: main
   - Main file: app.py

3. In "Advanced settings → Secrets", add:
   ASSEMBLYAI_API_KEY = "your_key_here"
   STREAMLIT_APP_URL = "https://your-app-name.streamlit.app"

4. Click Deploy. Wait ~2 minutes.

5. Test with a short YouTube URL (< 5 minutes) to verify the live deployment works.

KNOWN LIMITATION: Streamlit Community Cloud has a 1 GB memory limit and does not persist files
between restarts. The SQLite database (transcripts.db) will be wiped on each restart.
This is acceptable for MVP. For persistence, migrate to Render ($7/month) + a persistent disk,
or use a free PostgreSQL tier on Supabase.
```

---

### Prompt 12 — Phase 2: Claim Extraction

```
I am building a debate fact-checker web app.
Phase 1 (transcription) is complete. Now I am adding fact-checking.

Create a new file `fact_checker/extractor.py`.

Write a function:
    extract_claims(utterances: list[dict], api_key: str) -> list[dict]

Where utterances is a list from the transcript (each has "speaker", "text", "start_ms").
The function must:
1. Group consecutive utterances by the same speaker into "speaking turns".
2. For each turn, call the Claude API (model: claude-haiku-4-5-20251001) with a prompt:
   "You are a fact-checking assistant. Extract every specific factual claim from the following
    text. A factual claim is a statement that can be verified as true or false using evidence.
    Return a JSON array where each item has: claim (string), speaker (string), start_ms (int).
    Text: {text}"
3. Parse the JSON response. If parsing fails, log a warning and return an empty list for that turn.
4. Return a flat list of all claims across all turns.

Use the anthropic Python SDK. Read the API key from the parameter — do not hardcode it.
Add a __init__.py to the fact_checker/ folder.
```

---

### Prompt 13 — Phase 2: Evidence Search

```
I am building a debate fact-checker web app.
I have a list of factual claims (each a dict with "claim", "speaker", "start_ms").
I need to search for scientific evidence for each claim.

Create `fact_checker/searcher.py`.

Write a function:
    search_evidence(claim: str, max_results: int = 5) -> list[dict]

The function must query two free APIs in parallel (use concurrent.futures.ThreadPoolExecutor):

API 1 — Semantic Scholar (https://api.semanticscholar.org/graph/v1/paper/search):
  - Query: the claim text
  - Fields: title, authors, year, citationCount, externalIds, abstract
  - Filter: only papers with citationCount > 10

API 2 — PubMed E-utilities (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/):
  - Use esearch then efetch to get titles + abstracts
  - Only if Semantic Scholar returns < 3 results

Merge results, deduplicate by DOI, return up to max_results.
Each result dict: {"title", "authors", "year", "citation_count", "doi", "abstract", "source"}
where source is "semantic_scholar" or "pubmed".

Use only the requests library (no API keys needed for these endpoints — they are free).
Add a 1-second delay between PubMed requests to comply with their rate limit.
```

---

### Prompt 14 — Phase 2: Source Quality Scoring

```
I am building a debate fact-checker web app.
I have a list of evidence papers from search_evidence(), each with title, authors, year,
citation_count, doi, abstract, source.

Create `fact_checker/scorer.py`.

Write a function:
    score_evidence(claim: str, papers: list[dict], api_key: str) -> dict

The function must:
1. For each paper, compute a quality score (0–100) based on:
   - citation_count: log scale, max 30 points
   - recency: papers from last 5 years get 20 pts, 5–10 years 10 pts, older 0 pts
   - abstract relevance to claim: call Claude Haiku with a short prompt to rate 0–50
     ("Rate how relevant this abstract is to the following claim on a scale 0-50. 
      Claim: {claim}. Abstract: {abstract}. Reply with only a number.")
2. Sort papers by score descending.
3. Generate a verdict using Claude Haiku:
   Prompt: "Given the following claim and the top evidence papers, return a JSON with:
   verdict (one of: Supported, Contradicted, Contested, Insufficient_evidence),
   confidence (0.0-1.0), summary (1 sentence explaining why).
   Claim: {claim}
   Evidence: {top 3 paper titles and abstracts}"
4. Return:
   {
     "verdict": str,
     "confidence": float,
     "summary": str,
     "top_papers": list[dict]  (top 3, with score field added)
   }
```

---

### Prompt 15 — Phase 2: Fact-Check UI Tab

```
I am building a debate fact-checker web app in Streamlit.
I have these Phase 2 modules ready:
- fact_checker/extractor.py  →  extract_claims(utterances, api_key) -> list[dict]
- fact_checker/searcher.py   →  search_evidence(claim, max_results) -> list[dict]
- fact_checker/scorer.py     →  score_evidence(claim, papers, api_key) -> dict

Edit `app.py` to add a second tab "Fact-Check" alongside the existing "Transcript" tab.
Use st.tabs(["Transcript", "Fact-Check"]).

In the Fact-Check tab:
1. Show a button "Run Fact-Check" (only if a transcript is loaded in session state).
2. When clicked, run the full pipeline for each utterance (with a progress bar).
   Store results in st.session_state["fact_check_results"].
3. Display results grouped by speaker:
   For each claim:
   - The claim text (quoted)
   - Verdict badge: green = Supported, red = Contradicted, orange = Contested, grey = Insufficient
   - Confidence score as a progress bar
   - One-sentence summary
   - Expander "View sources" showing the top 3 papers with title, year, citation count, and a link
     (construct as https://doi.org/{doi} if DOI is available).

Read ANTHROPIC_API_KEY from environment (same pattern as ASSEMBLYAI_API_KEY).
Add ANTHROPIC_API_KEY to .env.template and to the Streamlit secrets instructions in Prompt 11.
```

---

---

*Last updated: 2026-05-28*
