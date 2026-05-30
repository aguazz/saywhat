# SayWhat — Truth Checker Phase (Phase 2)

> **Reading guide:** Start with §1 (what we are building), then §3 (data model), then §4
> (pipeline), then §8 (MVP proposal). The research sections (§6, §7) and the risks (§12) are
> reference material — come back to them as needed.

---

## Current Implementation Status (2026-05-30)

### ✓ All P16–P35 complete — Phase 2 build sprint finished

| Prompt | File | Status |
|--------|------|--------|
| P16 | `storage.py` — `analyses`, `claims`, `verdict_feedback` tables + 5 new functions | ✓ Done |
| P17 | `truth_checker/__init__.py`, `truth_checker/segmenter.py` | ✓ Done |
| P18 | `truth_checker/extractor.py` | ✓ Done |
| P19 | `truth_checker/classifier.py` | ✓ Done |
| P20 | `truth_checker/threader.py` | ✓ Done |
| P21 | `truth_checker/test_phase2a.py` (CLI test script) | ✓ Done |
| P22 | `app.py` — Analysis tab, claim table, CSV export | ✓ Done |
| P23 | `truth_checker/evidence.py` (Wikipedia + Semantic Scholar) | ✓ Done |
| P24 | `truth_checker/verifier.py` | ✓ Done |
| P25 | `app.py` — Run Fact-Check button, verdict badges, expanders, feedback form | ✓ Done |
| P26 | `truth_checker/translator.py`, `app.py` — EN↔ES claim toggle | ✓ Done |
| P27 | `truth_checker/responder.py` | ✓ Done |
| P28 | `truth_checker/visualizer.py`, `requirements.txt` (pyvis + networkx) | ✓ Done |
| P29 | `app.py` — Claims/Argument Map sub-tabs, Detect Responses button, graph + legend | ✓ Done |
| P30 | `truth_checker/rhetorician.py` — fallacy + device detection (Claude Sonnet) | ✓ Done |
| P31 | `app.py` — Rhetorical Profile sub-tab with per-speaker expanders | ✓ Done |
| P32 | `truth_checker/scorer.py` + `truth_checker/reporter.py` | ✓ Done |
| P33 | `app.py` — Speaker Report sub-tab (metrics, chart, narrative) | ✓ Done |
| P34 | `exporters.py` — `build_analysis_pdf()`, `app.py` — PDF + JSON download buttons | ✓ Done |
| P35 | `storage.py` — `load_analysis_for_transcript()`, `app.py` — analysis shareable link | ✓ Done |

### Deviations from original plan

- **`feedback.py` not created as a separate module.** Feedback storage is handled directly by `storage.save_feedback()` (added in P16) and the feedback form is inline in `app.py`. No functional loss.
- **PubMed not implemented in `evidence.py`.** Only Wikipedia and Semantic Scholar are queried. PubMed can be added later for biomedical claims.
- **`claims` SQLite table created but not populated per-claim.** Claims are stored as part of the `analysis_json` blob in the `analyses` table. The `claims` table exists for future query use. The `verdict_feedback` table is in active use.
- **`test_phase2a.py` placed inside `truth_checker/`** rather than a top-level `tests/` directory. This keeps it alongside the modules it tests and avoids import path issues.
- **`threads` SQLite table not created.** Threads are stored inside the `analysis_json` blob in the `analyses` table. The separate `threads` table from the original plan was not implemented; the blob approach is sufficient for current use.
- **`build_analysis_pdf` renders verdicts and speaker_report only if data is available.** The shareable link currently restores claims + threads from the stored blob; verdicts and speaker_report are not yet persisted back to the blob after fact-check or speaker report runs (future improvement: call `complete_analysis` again with enriched data after each step).
- **Analysis PDF download triggers on every Streamlit render** (no caching). Acceptable for current debate lengths; if needed, cache result in `session_state`.

---

## 0  Decisions Made

| Question | Decision |
|----------|----------|
| UI language | Bilingual EN/ES. Claims are extracted and displayed in their original debate language (Spanish or English). A "Show in English / Mostrar en inglés" toggle translates individual claims on demand via Claude. |
| Target reader | Casual debate viewer (non-expert). Language should be plain and jargon-free. Outputs should be self-explanatory without knowing argumentation theory. |
| Contested claims | Display verdict as **Contested** with a 1–2 sentence explanation of why credible sources disagree, plus links to both sides. Do not suppress the verdict — be transparent about the disagreement. |
| Reasoning transparency | **Justification and evidence are mandatory, not optional.** Every verdict shows the reasoning. Every fallacy shows the quote and why it is a fallacy. Every response classification explains the logic. No bare labels. |
| User feedback loop | Add a thumbs-down button per claim verdict. Store flags in SQLite. Used to identify systematic errors and improve prompts over time. |

---

## 1  What Phase 2 Is Trying to Achieve

Phase 1 gives you a clean speaker-attributed transcript with confidence flagging. That is useful
but stops before the hard question: **who is actually right?**

Phase 2 is a **structural debate analyzer**. Given a transcript, it produces a structured map of
the argument exchange: what each speaker claimed, what type of claim it was, what evidence they
offered, how the other speaker responded, and whether each checkable claim is factually supported.

The goal is to help a user understand the debate at the level of **claims, logic, and evidence**
rather than through the lens of charisma, confidence, or prior beliefs.

### What the system does NOT try to do

- Declare one speaker the "winner" — debates are not scored that way.
- Produce verdicts on value or moral claims (e.g. "capitalism is good/bad") — those are
  inherently subjective.
- Replace human judgment — it surfaces evidence and structure, not final answers.
- Fact-check every sentence — only checkable factual claims get verdicts.

---

## 2  Core Concepts and Vocabulary

| Term | Definition |
|------|-----------|
| **Speaker turn** | A block of consecutive utterances from the same speaker. One speaker may take many turns. |
| **Claim** | A statement the speaker presents as true. May be factual, causal, moral, etc. |
| **Claim type** | See the taxonomy below. Determines whether the claim is checkable. |
| **Checkable claim** | A claim specific enough to be verified against external evidence. |
| **Assertion** | A claim offered without supporting evidence or reasoning. |
| **Evidence** | Data, statistics, citations, examples, or reasoning offered to support a claim. |
| **Argument thread** | A sequence of claims and responses on the same topic/subtopic. |
| **Response** | A speaker's direct reaction to a specific claim made by another speaker. |
| **Refutation** | A response that presents evidence or reasoning against the original claim. |
| **Rebuttal** | A response that argues the original claim is wrong, possibly without new evidence. |
| **Evasion** | A response that changes the subject or ignores the original claim entirely. |
| **Concession** | Acknowledgment that the other speaker's claim is at least partly correct. |
| **Reframing** | Accepting the fact but changing its interpretation or context. |
| **Topic shift** | Introduction of a new argument thread, abandoning the current one. |
| **Factual verdict** | One of: True, Partially True, Contested, Misleading, False, Unverifiable, Subjective. |
| **Evidence quality** | How well the in-speech evidence supports the claim: Strong / Moderate / Weak / None. |
| **Reliability score** | Per-speaker aggregate: fraction of checkable claims that are true or partially true. |
| **Confidence** | How confident the system is in its own verdict (0.0–1.0). |
| **Logical fallacy** | A flaw in reasoning that makes an argument invalid regardless of its premises. |
| **Rhetorical device** | A technique that increases persuasive force without increasing logical strength. |

### Claim type taxonomy

| Type | Example | Checkable? |
|------|---------|-----------|
| **Factual** | "Unemployment was 4.2% in 2024." | Yes |
| **Causal** | "Tax cuts cause growth." | Partially (evidence exists but causation is contested) |
| **Statistical** | "Wages fell 12% in real terms since 2010." | Yes |
| **Predictive** | "This policy will increase inflation." | No (future) — but track record checkable |
| **Definitional** | "That is not capitalism — it is cronyism." | Contested (semantic) |
| **Moral/normative** | "The government has a duty to provide housing." | No |
| **Interpretive** | "This data shows the policy failed." | Partially |
| **Comparative** | "Spain's growth was faster than Germany's." | Yes |
| **Anecdotal** | "I know a business owner who said…" | Partially |

---

## 3  Data Model

All analysis results are stored alongside the existing `transcripts.db` SQLite database.
New tables extend the schema without touching the existing `transcripts` table.

### 3.1  Conceptual graph structure

```
Transcript
└── Turns  (grouped from utterances)
    └── Claims  ← NODES in the argument graph
            │
            ├── has_type, is_checkable, in_thread
            ├── contains  → Evidence (in-speech)
            ├── verdict   → FactualVerdict
            └── responses → Response ← EDGES in the argument graph
                                └── from_claim, to_claim, relationship
Threads ← CLUSTERS of claims
```

### 3.2  JSON schema — single-claim object

```json
{
  "id": "claim_003",
  "transcript_id": "uuid",
  "speaker": "A",
  "turn_index": 2,
  "start_ms": 124000,
  "end_ms": 138000,
  "text": "exact quote from transcript",
  "claim_type": "statistical",
  "checkable": true,
  "evidence_in_speech": "according to the INE data from 2023",
  "evidence_quality": "weak",
  "thread_id": "thread_002",
  "thread_position": 1,
  "fact_check": {
    "verdict": "partially_true",
    "confidence": 0.72,
    "explanation": "The figure is accurate but refers to nominal wages, not real wages.",
    "sources": [
      {
        "title": "INE Labour Cost Survey 2023",
        "url": "https://...",
        "source_type": "government_data",
        "relevance": 0.88
      }
    ]
  },
  "fallacies": [],
  "rhetorical_devices": ["appeal_to_authority"]
}
```

### 3.3  JSON schema — response (edge)

```json
{
  "id": "response_007",
  "from_speaker": "B",
  "from_claim_id": "claim_008",
  "to_claim_id": "claim_003",
  "relationship": "reframes",
  "explanation": "Speaker B accepts the wage figure but argues it was caused by the pandemic, not the policy.",
  "start_ms": 155000
}
```

### 3.4  JSON schema — argument thread

```json
{
  "id": "thread_002",
  "topic": "real wages under the current government",
  "claim_ids": ["claim_003", "claim_008", "claim_012"],
  "first_claim_ms": 124000,
  "last_claim_ms": 201000,
  "resolution": "contested",
  "resolution_note": "Both speakers cite different data sources; neither concedes."
}
```

### 3.5  JSON schema — per-speaker summary

```json
{
  "speaker": "A",
  "name": "Juan Ramón Rallo",
  "total_claims": 24,
  "checkable_claims": 14,
  "verdicts": {
    "true": 6,
    "partially_true": 3,
    "misleading": 2,
    "false": 1,
    "unverifiable": 2
  },
  "evidence_quality_distribution": {"strong": 2, "moderate": 4, "weak": 5, "none": 3},
  "direct_response_rate": 0.68,
  "evasion_count": 4,
  "fallacies_detected": ["straw_man", "false_dichotomy"],
  "reliability_score": 0.64
}
```

### 3.6  New SQLite tables

```sql
CREATE TABLE IF NOT EXISTS analyses (
    id                  TEXT PRIMARY KEY,   -- UUID
    transcript_id       TEXT NOT NULL,
    created_at          TEXT,
    model_used          TEXT,
    analysis_json       TEXT,               -- full JSON blob (claims, threads, responses, summary)
    status              TEXT,               -- "pending" | "complete" | "error"
    error_msg           TEXT
);

CREATE TABLE IF NOT EXISTS claims (
    id              TEXT PRIMARY KEY,
    analysis_id     TEXT NOT NULL,
    transcript_id   TEXT NOT NULL,
    speaker         TEXT,
    start_ms        INT,
    claim_type      TEXT,
    checkable       INT,                    -- 0 or 1
    verdict         TEXT,
    confidence      REAL,
    claim_json      TEXT                    -- full claim object
);

CREATE TABLE IF NOT EXISTS threads (
    id              TEXT PRIMARY KEY,
    analysis_id     TEXT NOT NULL,
    topic           TEXT,
    resolution      TEXT,
    thread_json     TEXT
);
```

---

## 4  Processing Pipeline

```
Transcript (from storage.py / session state)
    │
    ▼
[Step 1] Turn Segmentation
    Group consecutive utterances by the same speaker.
    Output: list of Turn objects with speaker, start_ms, end_ms, full text.
    │
    ▼
[Step 2] Claim Extraction  ← Claude Sonnet
    For each turn, extract discrete claims.
    Output: raw claim list (text, speaker, start_ms, end_ms).
    │
    ▼
[Step 3] Claim Classification  ← Claude Sonnet
    For each claim: assign type, checkable flag, in-speech evidence, evidence quality.
    Filter out non-claims (questions, filler, emotional statements).
    │
    ▼
[Step 4] Thread Detection  ← Claude Sonnet
    Group all claims from all speakers into argument threads by topic.
    Each thread gets a label and a list of claim IDs in chronological order.
    │
    ▼
[Step 5] Response Detection  ← Claude Sonnet
    For each claim, determine if any subsequent claim from a different speaker
    is a direct response to it. Build the response edges.
    Classify the relationship: supports / refutes / weakens / reframes /
    concedes / evades / ignores / redirects.
    │
    ▼
[Step 6] Evidence Retrieval  ← Free APIs (parallel)
    For each checkable claim:
    - Semantic Scholar (papers, citations)
    - Wikipedia API (factual background)
    - PubMed (for biomedical claims)
    - (optional) Tavily Search API (web)
    │
    ▼
[Step 7] Factual Verdict  ← Claude Sonnet + retrieved evidence
    For each checkable claim, give Claude the claim + the top 3 evidence snippets.
    Ask for: verdict, confidence, one-sentence explanation, source links.
    │
    ▼
[Step 8] Rhetorical Analysis  ← Claude Sonnet  [Phase 2c+]
    Scan each turn for logical fallacies and rhetorical devices.
    Taxonomy: straw man, ad hominem, appeal to authority, false dichotomy,
    slippery slope, cherry-picking, appeal to emotion, anecdote over data.
    │
    ▼
[Step 9] Speaker Scoring
    Aggregate verdicts, evidence quality, evasion count, fallacy count
    into a per-speaker reliability profile.
    │
    ▼
[Step 10] Report Generation
    Produce the structured analysis JSON.
    Save to SQLite analyses table.
    │
    ▼
[Step 11] UI Rendering
    Display in the new "Analysis" tab in app.py.
    Optionally render an interactive argument graph.
```

### Design principles for the pipeline

- **Each step is independently callable and testable.** Steps 1–3 can run without Steps 4–11.
- **Steps run in order** — each step consumes the output of the previous one.
- **Expensive steps (6, 7, 8) are gated** — only run on checkable claims, with rate limiting.
- **Results are cached** — once an analysis is saved, it is not recomputed on page reload.
- **Chunking** — long debates may exceed context windows. Claims are processed in batches of
  ~20, with thread and response detection running across the full claim list.

---

## 5  Evaluation Dimensions

The system distinguishes six orthogonal dimensions. They can all be low or high independently.

| Dimension | What it measures | Example — high | Example — low |
|-----------|-----------------|---------------|--------------|
| **Factual accuracy** | Are the stated facts true? | Cites correct unemployment figure | Claims a statistic that is 30% off |
| **Logical validity** | Does the reasoning hold even if premises are true? | Coherent deductive argument | Commits a false dichotomy |
| **Evidence quality** | How strong is the supporting evidence cited? | Points to an RCT with 50k participants | "Everyone knows that…" |
| **Response relevance** | Does the response actually address the prior claim? | Directly refutes the stated number | Changes subject entirely |
| **Rhetorical effectiveness** | How persuasive is the argument to a lay listener? | Vivid example, confident delivery | Dry, jargon-heavy, hesitant |
| **Overall confidence** | System confidence in its own analysis | High evidence, unambiguous claim | Vague claim, no retrievable evidence |

A speaker can be **rhetorically effective but factually weak** (persuasive but wrong), or
**factually accurate but logically confused** (cites real data in a bad argument), or
**logically valid but insufficiently supported** (valid reasoning from unproven premises).
The system tracks all six rather than collapsing them into one score.

---

## 6  Connected Academic and Technical Fields

Understanding these fields will help you evaluate libraries and interpret the system's outputs.
You do not need to read all of these — they are pointers for when you want to go deeper.

### Argumentation Theory
- **Toulmin model** (1958): a claim is supported by data and a warrant, with qualifiers and
  rebuttals. This maps directly onto our claim → evidence → verdict structure.
- **Walton's argumentation schemes**: ~60 argument patterns (argument from authority, from
  analogy, from example, etc.), each with a set of critical questions to test it.
- **Abstract Argumentation (Dung, 1995)**: claims as nodes, attacks as edges — the mathematical
  framework behind argument graphs and argument maps.

### Informal Logic and Rhetoric
- **Informal fallacy taxonomies** (e.g. Aristotle's Sophistical Refutations, Hamblin, Tindale):
  the reference list for classifying rhetorical failures.
- **Classical rhetoric**: ethos (credibility), logos (logic), pathos (emotion). All three appear
  in debate performance.

### Discourse Analysis
- **Coherence and cohesion**: how topics hang together across a conversation.
- **Topic continuity**: techniques for detecting when a conversation shifts subject.

### Computational Argument Mining
The field that automates argumentation theory with NLP. Key tasks:
1. **Claim detection** — is this sentence a claim?
2. **Premise detection** — is this evidence for a claim?
3. **Argument structure prediction** — which claims attack/support which?
4. **Stance detection** — does speaker B agree or disagree with speaker A?
Key researchers: Stab & Gurevych (2014), Mochales-Palau, Moens, IBM Debater project.

### Natural Language Inference (NLI)
Given a premise and a hypothesis, classify the relationship as:
**entailment** (premise proves hypothesis), **contradiction**, or **neutral**.
NLI is the foundation for claim-evidence matching and response classification.

### Fact-Checking
The field closest to what Phase 2 does. Two broad approaches:
1. **Knowledge-based**: look up the claim in a structured knowledge base (Wikidata, DBpedia).
2. **Evidence-based**: retrieve relevant documents and reason over them.
Datasets: FEVER, MultiFC, ClaimBuster, LIAR, PolitiFact archives.

### Retrieval-Augmented Generation (RAG)
The technique of retrieving relevant documents and giving them to the LLM as context before
generating an answer. Step 6 (evidence retrieval) + Step 7 (verdict) is a RAG pattern.

### Knowledge Graphs
Structured representations of facts as triples: (subject, relation, object).
Wikidata has 1.7 billion statements that can be queried for many factual claims.

### Epistemology
The branch of philosophy concerned with knowledge, justification, and certainty. Relevant for
defining what counts as "verified" and how to handle contested evidence.

---

## 7  Existing Tools, Libraries, and Datasets

### Claim Detection and Argument Mining

| Name | Type | Notes |
|------|------|-------|
| [ClaimBuster](https://idir.uta.edu/claimbuster/) | Tool + API | Free API for detecting check-worthy factual claims. University of Texas. |
| [IBM Debater APIs](https://early-access-program.debater.res.ibm.com/) | API | Claim detection, evidence search, key points. Research access required. |
| [ArgMining shared tasks](https://argmining-org.github.io/) | Dataset + benchmark | Annual ACL shared task datasets for argument mining. |
| [Stab & Gurevych (2014)](https://aclanthology.org/D14-1006/) | Paper + dataset | Student essay corpus with claim/premise annotations. |
| [DebateSum](https://github.com/Hellisotherpeople/DebateSum) | Dataset | 187,000+ debate arguments with summaries and citations. |
| [UKP Sentential Argument Mining Corpus](https://github.com/UKPLab/acl2018-ArgMining-LongDocuments) | Dataset | 25k sentences annotated for claim/non-claim. |

### Fact-Checking

| Name | Type | Notes |
|------|------|-------|
| [FEVER dataset](https://fever.ai/) | Benchmark | 185k claims labelled SUPPORTS / REFUTES / NOT ENOUGH INFO against Wikipedia. |
| [FactCC](https://github.com/salesforce/factCC) | Library | Factual consistency scoring for generated text. |
| [ClaimBuster API](https://idir.uta.edu/claimbuster/api/) | Free API | Rates sentences by "check-worthiness". |
| [Full Fact Automated Fact-Checking](https://fullfact.org/automated/) | Tool | Open source NLP tools from UK fact-checkers. |
| [LIAR dataset](https://www.cs.ucsb.edu/~william/data/liar_dataset.zip) | Benchmark | 12.8k political statements from PolitiFact with verdicts. |
| [MultiFC](https://competitions.codalab.org/competitions/21163) | Benchmark | 36k claims from 26 fact-checking sites. |

### Evidence Retrieval APIs (free tiers)

| Name | Type | Coverage |
|------|------|---------|
| [Semantic Scholar](https://api.semanticscholar.org/graph/v1/) | API | 200M+ papers, no key needed for low volumes |
| [PubMed E-utilities](https://eutils.ncbi.nlm.nih.gov/entrez/eutils/) | API | All biomedical literature, free |
| [Wikipedia API](https://en.wikipedia.org/w/api.php) | API | Broad factual coverage, free, fast |
| [Wikidata SPARQL](https://query.wikidata.org/) | API | Structured knowledge base, 1.7B facts, free |
| [CrossRef](https://api.crossref.org/) | API | DOI metadata, journal impact, free |
| [CORE](https://core.ac.uk/services/api) | API | Open-access full text, free |
| [OpenAlex](https://api.openalex.org/) | API | 250M+ works, successor to MAG, no key needed |
| [Tavily Search](https://tavily.com/) | API | Web search optimized for RAG, generous free tier |

### NLI and Stance Detection

| Name | Type | Notes |
|------|------|-------|
| [AllenNLP](https://github.com/allenai/allennlp) | Library | NLI, SRL, coreference. Python. |
| [HuggingFace NLI models](https://huggingface.co/models?pipeline_tag=text-classification&sort=downloads&search=nli) | Models | Many pretrained cross-encoder NLI models. |
| [nli-deberta-v3-small](https://huggingface.co/cross-encoder/nli-deberta-v3-small) | Model | Fast and accurate NLI. Can run locally. |

### Argument Visualization

| Name | Type | Notes |
|------|------|-------|
| [Kialo](https://www.kialo.com/) | App | Pro tool for argument maps. Not open source but shows the UX target. |
| [Argdown](https://argdown.org/) | Tool | Markdown-like syntax for argument reconstruction. Has JS renderer. |
| [pyvis](https://pyvis.readthedocs.io/en/latest/) | Python library | Interactive network graphs, outputs HTML. Works in Streamlit via `components.v1.html`. |
| [streamlit-agraph](https://github.com/ChrisDelClea/streamlit-agraph) | Streamlit component | Graph visualization directly in Streamlit. |
| [networkx](https://networkx.org/) | Python library | Graph data structures. For building the argument graph before rendering. |
| [Plotly](https://plotly.com/python/network-graphs/) | Python library | Network graphs with hover tooltips. |

### RAG Frameworks (optional)

| Name | Type | Notes |
|------|------|-------|
| [LangChain](https://www.langchain.com/) | Framework | Retrieval + LLM chains. Heavy but powerful. |
| [LlamaIndex](https://www.llamaindex.ai/) | Framework | Easier RAG for structured data. |
| Neither | — | For this project, a direct requests → Claude call is simpler and sufficient. |

**Recommendation:** Do not add LangChain or LlamaIndex. The pipeline is simple enough that
calling APIs directly and passing retrieved text to Claude is cleaner and cheaper.

---

## 8  MVP Proposal

The MVP does one thing well: **produce a claim table** from an existing transcript.

### What the MVP delivers

1. Load any transcript from storage (by ID or from session state).
2. Extract discrete claims from each speaker turn using Claude.
3. Classify each claim: type + checkable flag.
4. Group claims by topic into 3–6 argument threads.
5. Display a sortable/filterable table showing:

| Speaker | Time | Claim | Type | Checkable | Suggested fact-check query |
|---------|------|-------|------|-----------|---------------------------|
| A | 02:04 | "Unemployment fell to 4.2% in 2024" | Statistical | ✓ | "Spain unemployment rate 2024 official" |
| B | 03:11 | "That figure ignores discouraged workers" | Interpretive | Partial | "Spain discouraged workers ILO definition 2024" |

6. No external API calls yet — just Claude for extraction and classification.
7. Export the table as CSV.

### What the MVP does NOT include

- External evidence retrieval (that is Phase 2b)
- Factual verdicts (Phase 2b)
- Response relationship detection (Phase 2b)
- Visualization (Phase 2c)
- Rhetorical analysis (Phase 2c)

### MVP cost estimate

- Each debate (~60 minutes): ~40–60 speaker turns → ~40–60 Claude API calls (small)
- Using `claude-haiku-4-5-20251001`: ~$0.01–$0.05 per debate analyzed
- Using `claude-sonnet-4-6` (better quality): ~$0.10–$0.30 per debate analyzed

**Recommendation:** Use Haiku for claim extraction (high volume, structured output) and
Sonnet for thread grouping and response detection (requires more reasoning).

---

## 9  Phased Implementation Roadmap

Each milestone is independently testable. Build and test each before moving to the next.

---

### Phase 2a — Claim Table (MVP) ✓ COMPLETE (P16–P22)

**Goal:** Extract and classify claims into a table. No external evidence.

**Files to add:**
```
truth_checker/
├── __init__.py
├── segmenter.py     — group utterances into turns
├── extractor.py     — extract claims from a turn (Claude Haiku)
├── classifier.py    — classify each claim (Claude Haiku)
└── threader.py      — group claims into threads (Claude Sonnet)
```

**App changes:**
- Add "Analysis" tab to `app.py` (alongside "Transcript").
- Show a "Run Analysis" button when a transcript is loaded.
- Display the claim table. Allow filtering by speaker and claim type.
- Add CSV export.

**Storage changes:**
- Add the `analyses`, `claims`, and `threads` tables to `storage.py`.
- Save and load analysis results.

**Definition of done:**
- Given the existing Rallo–Garzón transcript, produces a table of ~30–50 claims with types
  and checkability flags. A human review agrees with ≥80% of the classifications.

---

### Phase 2b — Factual Verification ✓ COMPLETE (P23–P26)

**Goal:** For checkable claims, retrieve evidence and generate verdicts.

**Files to add:**
```
truth_checker/
├── evidence.py      — evidence retrieval (Semantic Scholar, Wikipedia, PubMed)
└── verifier.py      — factual verdict per claim (Claude Sonnet + evidence)
```

**App changes:**
- Show verdict badges in the claim table (green/red/orange/grey).
- Show confidence bars.
- Expandable "Sources" section per claim.

**Definition of done:**
- For 10 manually chosen checkable claims from the Rallo–Garzón debate, compare the system
  verdict against a human fact-check. Target: 7/10 verdicts match human judgment.

---

### Phase 2c — Response Mapping and Argument Graph ✓ COMPLETE (P27–P29)

**Goal:** Detect cross-speaker responses and visualize the argument structure.

**Files to add:**
```
truth_checker/
├── responder.py     — detect and classify cross-speaker responses (Claude Sonnet)
└── visualizer.py    — render argument graph (pyvis + streamlit HTML component)
```

**App changes:**
- Add an "Argument Map" sub-tab inside "Analysis".
- Interactive graph: nodes = claims, edges = responses, colors = speakers.
- Click a node to see the claim text and verdict.

**Definition of done:**
- Given the Rallo–Garzón debate, the graph correctly identifies ≥5 direct response chains
  (claim → direct rebuttal → counter-rebuttal) as verified by listening to those exchanges.

---

### Phase 2d — Rhetorical and Logical Analysis ✓ COMPLETE (P30–P31)

**Goal:** Detect logical fallacies and rhetorical devices per speaker turn.

**Files to add:**
```
truth_checker/
└── rhetorician.py   — fallacy and device detection (Claude Sonnet)
```

**App changes:**
- Add a "Rhetorical Profile" section per speaker.
- List detected fallacies with the relevant quote and explanation.

**Fallacies to detect (Phase 2d scope):**
- Straw man
- Ad hominem
- False dichotomy
- Appeal to authority (legitimate vs. illegitimate)
- Slippery slope
- Cherry-picking / selective evidence
- Appeal to emotion
- Anecdote over population data
- Whataboutism

**Definition of done:**
- For 5 known fallacies in the Rallo–Garzón debate (identified by human review), the system
  detects ≥4 and correctly labels them.

---

### Phase 2e — Per-Speaker Reliability Report ✓ COMPLETE (P32–P33)

**Goal:** Generate an aggregate per-speaker reliability profile.

**Files to add:**
```
truth_checker/
└── scorer.py        — aggregate reliability scores
└── reporter.py      — narrative report generation (Claude Sonnet)
```

**App changes:**
- Add a "Speaker Report" section showing:
  - Reliability score (fraction of checkable claims that are true/partially true)
  - Direct response rate (fraction of the time they address the prior claim rather than evading)
  - Fallacy count and types
  - Evidence quality distribution
  - A one-paragraph narrative summary per speaker.

**Definition of done:**
- Two human evaluators read the per-speaker report and agree it is fair, accurate, and does
  not misrepresent the speakers' positions.

---

### Phase 2f — Export, Sharing, and Feedback Loop ✓ COMPLETE (P34–P35)

**Goal:** Make the analysis output shareable and downloadable. Add a user feedback mechanism.

**Files to add / modify:**
- Extend `exporters.py` with `build_analysis_pdf()` and `build_analysis_json()`.
- Extend shareable link system in `storage.py` to include analysis ID.
- Add `truth_checker/feedback.py` — stores thumbs-down flags and optional user comments.

**New SQLite table:**
```sql
CREATE TABLE IF NOT EXISTS verdict_feedback (
    id              TEXT PRIMARY KEY,
    claim_id        TEXT NOT NULL,
    analysis_id     TEXT NOT NULL,
    transcript_id   TEXT NOT NULL,
    rating          TEXT,          -- "incorrect" | "misleading" | "incomplete"
    user_note       TEXT,
    created_at      TEXT
);
```

**App changes:**
- "Download Analysis" button: PDF report + JSON export.
- Shareable link that loads both the transcript and its analysis.
- Thumbs-down button (👎) next to each claim verdict. Clicking opens a small form:
  - "What is wrong with this verdict?" → radio: Incorrect / Misleading / Incomplete
  - Optional free-text note
  - On submit, saves to `verdict_feedback` table.
- Note: feedback data is local only. No external reporting in MVP.

---

## 10  LLM Prompts for Each Step

These are reference prompts. Use them as starting points for the implementation prompts
in each phase. They use structured JSON output to make parsing reliable.

---

### Step 2 — Claim Extraction (per speaker turn)

The claim is extracted and stored in the **original debate language** (Spanish or English).
Translation is a separate on-demand step, not done here.

```
You are an argument analyst. Read the following speaker turn from a debate transcript.
Extract every discrete claim the speaker makes.

A claim is a statement the speaker presents as true. Do not extract:
- Questions
- Expressions of opinion phrased as preferences ("I think we should...")
- Greetings, filler, or transition phrases
- Clear jokes, sarcasm, or hyperbole

For each claim, return:
- "claim": the exact or slightly cleaned quote from the text, in the original language
- "start_hint": the first few words of the sentence containing the claim

Return a JSON array. If there are no claims, return [].

Speaker: {speaker_name}
Turn text:
"""
{turn_text}
"""
```

### Step 2b — On-Demand Translation (optional, per claim)

Called only when the user clicks "Show in English" / "Mostrar en inglés" for a specific claim.
Costs one Haiku call per claim translated.

```
Translate the following claim from {source_language} to {target_language}.
Preserve the original meaning exactly. Do not add interpretation or commentary.
Return only the translated text, nothing else.

Claim: "{claim_text}"
```

---

### Step 3 — Claim Classification

```
You are an argument analyst. Classify the following claim.

Claim: "{claim_text}"
Speaker: {speaker_name}

Return a JSON object with:
- "claim_type": one of ["factual", "statistical", "causal", "predictive", "comparative",
  "definitional", "interpretive", "moral", "anecdotal"]
- "checkable": true if this claim can be verified against external data or evidence, false otherwise
- "evidence_in_speech": quote any evidence or data the speaker cited in support (or "" if none)
- "evidence_quality": one of ["strong", "moderate", "weak", "none"]
  - strong: specific statistics, named studies, official sources
  - moderate: general references to research or trends without citation
  - weak: anecdote, vague reference, personal experience
  - none: bare assertion
- "suggested_query": if checkable, a 5–10 word search query suitable for Semantic Scholar or Google
```

---

### Step 4 — Thread Detection (full claim list at once)

```
You are an argument analyst. Below is a list of claims extracted from a debate transcript,
in chronological order, from multiple speakers.

Group these claims into argument threads. An argument thread is a set of claims and responses
that share the same topic or sub-topic.

For each thread:
- "thread_id": short slug, e.g. "wages_2024"
- "topic": a short descriptive label (5–8 words)
- "claim_ids": list of claim IDs that belong to this thread, in chronological order

Aim for 3–8 threads. Assign every claim to exactly one thread.
If a claim does not fit any thread, assign it to a thread called "miscellaneous".

Return a JSON array of thread objects.

Claims:
{json_list_of_claims}
```

---

### Step 5 — Response Detection (one claim at a time)

```
You are an argument analyst. A debate has produced the following sequence of claims
from multiple speakers. For each claim after the first, determine whether it is a
direct response to any earlier claim.

Definitions:
- "refutes": presents evidence or reasoning against the prior claim
- "supports": agrees with or extends the prior claim
- "weakens": accepts the claim but reduces its strength (qualifies, adds context)
- "reframes": accepts the fact but reinterprets its meaning
- "concedes": acknowledges the prior claim is (partly) correct
- "evades": changes subject without addressing the prior claim
- "ignores": makes a new point with no connection to prior claims

For the claim below, return a JSON object with:
- "is_response": true or false
- "responds_to_claim_id": ID of the claim being responded to (or null)
- "relationship": one of the types above (or null if not a response)
- "explanation": one sentence explaining the classification

Current claim:
{claim_json}

Previous claims (in order):
{previous_claims_json}
```

---

### Step 7 — Factual Verdict

Justification and evidence are shown to the user, not just the verdict label.
For "contested" verdicts, both sides of the disagreement are shown.
Language: explanation is written in plain language for a general audience.

```
You are a fact-checker. Assess the following claim using the evidence provided.
Write for a general audience — avoid academic or legal jargon.

Claim: "{claim_text}"
Speaker: "{speaker_name}"

Evidence (retrieved from external sources):
{evidence_snippets}

Return a JSON object with:
- "verdict": one of ["true", "partially_true", "contested", "misleading", "false",
  "unverifiable", "subjective"]
  - true: evidence clearly supports the claim
  - partially_true: claim is directionally right but overstated, understated, or missing context
  - contested: credible, independent sources reach opposite conclusions
  - misleading: technically accurate but creates a false impression
  - false: evidence clearly contradicts the claim
  - unverifiable: no reliable evidence found; do not guess
  - subjective: the claim is a value judgment, not a factual question
- "confidence": 0.0 to 1.0 (your confidence in this verdict, based on evidence quality)
- "explanation": 2–3 sentences in plain language explaining the verdict, referencing specific
  evidence. For "contested" verdicts, explain what each side of the disagreement claims.
- "for_the_claim": (only for "contested") one sentence summarising the strongest evidence
  that supports the claim
- "against_the_claim": (only for "contested") one sentence summarising the strongest evidence
  that contradicts the claim
- "key_source": the most relevant source title and URL
- "all_sources": list of all source titles and URLs used

Do not fabricate sources or statistics. If evidence is insufficient, return "unverifiable".
```

---

### Step 8 — Rhetorical Analysis (per speaker turn)

Explanations are written for a general audience — no assumed knowledge of logic or rhetoric.
Each finding includes the quote AND a plain-language explanation of what it means and why
it matters (or why it does not weaken the argument, in the case of neutral devices).

```
You are a logician and rhetoric expert. Analyze the following speaker turn for logical
fallacies and rhetorical devices. Write for a general, non-expert audience.

Logical fallacies to check for:
straw_man, ad_hominem, false_dichotomy, appeal_to_authority (illegitimate),
slippery_slope, cherry_picking, appeal_to_emotion, anecdote_over_data,
whataboutism, hasty_generalization, correlation_as_causation

Rhetorical devices to note (these are not necessarily negative):
appeal_to_authority (legitimate), appeal_to_emotion (fair), vivid_example,
social_proof, personal_testimony, framing_effect, loaded_language

For each fallacy or device found, return:
- "type": the fallacy or device name (in English, regardless of debate language)
- "label": a short plain-language name, e.g. "False choice" for false_dichotomy
- "quote": the exact phrase from the text that contains it
- "explanation": 2–3 sentences in plain language explaining:
    1. What the speaker did
    2. Why this is (or is not) a problem for their argument
    3. What a stronger version of the argument would look like (for fallacies)
- "is_fallacy": true if it weakens the argument logically, false if neutral or positive

Return a JSON object with "fallacies" (list) and "rhetorical_devices" (list).
If none found, return empty lists. Do not invent fallacies — only flag clear examples.

Turn text:
"""
{turn_text}
"""
```

---

## 11  Proposed File and Module Structure

```
debate-fact-checker/
├── app.py                         ✓ Full analysis UI: Claims/Map/Rhetoric/Speaker Report (P22–P35)
├── storage.py                     ✓ analyses/claims/verdict_feedback tables + 6 functions (P16, P35)
├── exporters.py                   ✓ build_analysis_pdf() + build_analysis_json() (P34)
├── requirements.txt               ✓ pyvis + networkx added (P28)
│
├── truth_checker/
│   ├── __init__.py                ✓ (P17)
│   ├── segmenter.py               ✓ segment_turns() (P17)
│   ├── extractor.py               ✓ extract_claims_from_turn() (P18)
│   ├── classifier.py              ✓ classify_claim() (P19)
│   ├── translator.py              ✓ translate_claim() EN↔ES (P26)
│   ├── threader.py                ✓ group_into_threads() (P20)
│   ├── responder.py               ✓ detect_responses() (P27)
│   ├── evidence.py                ✓ retrieve_evidence() Wikipedia + Semantic Scholar (P23)
│   ├── verifier.py                ✓ verify_claim() with full reasoning (P24)
│   ├── visualizer.py              ✓ build_graph_html() pyvis (P28)
│   ├── rhetorician.py             ✓ analyze_turn_rhetoric() fallacy + device detection (P30)
│   ├── scorer.py                  ✓ compute_speaker_scores() (P32)
│   ├── reporter.py                ✓ generate_speaker_summary() (P32)
│   └── test_phase2a.py            ✓ CLI pipeline test (P21)
│
└── tests/                         ○ not yet created (golden transcript + unit tests)

✓ = built   ○ = planned, not yet implemented
```

**Note:** `feedback.py` was merged into `storage.py` (`save_feedback` function) — no separate module needed.
**Note:** `threads` SQLite table from the original plan not created — threads stored in `analysis_json` blob.

### Key design decisions

- **No new UI framework.** The "Analysis" tab sits inside the existing Streamlit `app.py`
  using `st.tabs()`.
- **No LangChain.** Each step makes direct API calls. Simpler to debug.
- **Claude model choice:**
  - Haiku for high-volume structured extraction (Steps 2, 3).
  - Sonnet for reasoning-heavy steps (Steps 4, 5, 7, 8).
- **Rate limiting:** A 0.5s sleep between Claude calls per claim; batching where possible.
- **Cost guard:** Before running, show the user an estimated cost and ask to confirm.
- **Progressive disclosure:** Analysis runs step by step with a progress bar. Intermediate
  results appear as each step completes.

---

## 12  Risks and Limitations

### Hallucinated fact-checks
**Risk:** Claude may invent plausible-sounding sources or fabricate statistics.
**Mitigation:**
- The Step 7 prompt explicitly says "do not fabricate sources".
- All verdicts are displayed with the source title and URL so users can click to verify.
- Add a prominent disclaimer: "This tool does not replace manual fact-checking."
- Never report a verdict without at least one retrieved external source snippet.

### Biased verdicts
**Risk:** Claude's training data has political and cultural biases that may skew verdicts
on contested economic, political, or social claims.
**Mitigation:**
- Use `verdict: contested` liberally for claims where credible sources disagree.
- Display confidence scores prominently so low-confidence verdicts are visually muted.
- Allow users to report incorrect verdicts (Phase 2f feature).
- In the prompt, explicitly instruct Claude not to favor one political position.

### Unreliable sources
**Risk:** Semantic Scholar and Wikipedia can return low-quality or outdated content.
**Mitigation:**
- Score sources by recency, citation count, and domain type.
- Prefer .gov, .edu, peer-reviewed sources over opinion sites.
- Display the source so the user can judge its quality.

### Difficulty distinguishing rhetoric from truth
**Risk:** A speaker may be rhetorically weak but factually correct, or vice versa. Users may
conflate the rhetorical score with the factual score.
**Mitigation:**
- Show factual accuracy and rhetorical quality as separate, clearly labeled dimensions.
- Include an explanation of what each score means in the UI.

### Subjective and value claims
**Risk:** Moral or normative claims ("the government should...") may be incorrectly classified
as checkable factual claims and given spurious verdicts.
**Mitigation:**
- The classifier explicitly tags moral and definitional claims as not checkable.
- The verifier returns `verdict: subjective` for any claim that reaches it without a
  checkable tag — belt and suspenders.

### Satire, jokes, and rhetorical questions
**Risk:** A speaker may say something hyperbolic or ironic, and the system may extract it as
a genuine claim.
**Mitigation:**
- The extraction prompt instructs Claude to skip rhetorical questions and clear hyperbole.
- Add a `satirical: true` flag to the claim schema — the classifier can set this.
- Claims flagged as satirical are shown in the table but not fact-checked.

### Overconfidence
**Risk:** The system may report high confidence on claims where the evidence is thin.
**Mitigation:**
- Confidence calibration: require at least 2 independent sources to reach confidence > 0.8.
- Default to confidence 0.5 for claims with only 1 weak source.

### Long debates exceeding context windows
**Risk:** A 90-minute debate may have 200+ claims. Sending all of them to Claude for thread
grouping will overflow the context.
**Mitigation:**
- Steps 2 and 3 process one turn at a time — no context limit issue.
- Step 4 (thread grouping) operates on the claim list (short strings), not the transcript.
  200 claims × ~20 words = ~4,000 tokens — well within limits.
- Steps 5 and 7 process one claim at a time — no issue.
- Step 8 processes one turn at a time — no issue.

### On-demand translation introducing errors
**Risk:** Translating a claim from Spanish to English (or vice versa) may subtly change
its meaning, especially for domain-specific terms (economic or legal vocabulary).
**Mitigation:**
- Translation is always shown alongside the original, not replacing it.
- A note in the UI clarifies: "This is a machine translation. The original text is always
  used for fact-checking."
- Fact-checking and verdict generation always use the original-language claim, never
  a translated version.

### Cost overruns
**Risk:** Running full analysis on every transcript view could get expensive.
**Mitigation:**
- Analysis is opt-in (user clicks "Run Analysis").
- Show cost estimate before running (count turns × cost per call).
- Cache results in SQLite — never re-analyze the same transcript.
- Add a per-transcript cost field to the analyses table for transparency.

---

## 13  Testing and Evaluation Strategy

### Unit tests (per module)

| Module | Test approach |
|--------|--------------|
| `segmenter.py` | Pure Python — test against synthetic utterance lists. No API needed. |
| `extractor.py` | Snapshot test: run against a 5-turn excerpt, save JSON output, assert structure valid. |
| `classifier.py` | Golden dataset: 20 manually labeled claims → measure accuracy. |
| `verifier.py` | Use FEVER dev set (English subset): compare verdicts against SUPPORTS/REFUTES labels. |
| `responder.py` | Manually annotate 10 response chains → measure precision/recall. |

### Golden transcript

Use the existing Rallo–Garzón MP3 (already in the repo) to produce a reference transcript
and manually label:
- 30 claims (with type, checkability, expected verdict)
- 10 response relationships (claim pairs with expected relationship type)
- 5 argument threads

Store in `tests/golden_transcript.json`. Run evaluation script `tests/eval_pipeline.py`
that compares pipeline output against the golden labels and reports accuracy.

### Benchmark datasets

| Dataset | Use |
|---------|-----|
| FEVER (dev set) | Evaluate factual verdict accuracy for English claims. 2,384 labeled examples. |
| LIAR (test set) | Evaluate on political statements closer to debate language. 1,267 examples. |
| ArgMining 2021 | Evaluate claim vs. non-claim classification. |

### Human review protocol

Before any public release:
1. Run the pipeline on 3 different debates (different speakers, topics, languages).
2. Have 2 human reviewers independently assess 20 random claims per debate.
3. Compute inter-rater agreement (Cohen's kappa) between reviewers.
4. Compute system vs. human agreement for each step.
5. Document known failure modes.

### Regression test after each phase

After each phase, run the golden transcript through the updated pipeline and compare with the
previous run. Any regression in accuracy (>5% drop) blocks the phase from merging.

---

## 14  Assumptions Made

The following are assumptions made in writing this plan. Flag any that are incorrect.

1. **The primary debate language is Spanish.** Claims are extracted and stored in Spanish
   (the original language). Prompts are in English; Claude processes Spanish input correctly.
   Translation to English is on-demand, never automatic.
   **Decision confirmed: claims stay in original language; EN↔ES toggle per claim.**

2. **No speaker diarization post-processing is needed.** The transcript already has accurate
   speaker labels from Phase 1. If speaker labels are noisy (e.g. "Speaker A" contains
   multiple people), the analysis quality degrades. **Assumption: Phase 1 speaker labels
   are good enough.**

3. **The user will run analysis on demand, not automatically.** There is no background job or
   webhook. Analysis is triggered by a button click. **Assumption confirmed from PLAN.md.**

4. **Budget stays within $20–50/month.** At Sonnet pricing (~$3/$15 per M tokens), a
   60-minute debate produces ~2,000 tokens of claims text. Running Steps 2–8 on 50 claims
   costs roughly $0.15–$0.50 per debate. This is well within budget.
   **Assumption: fewer than 100 debates analyzed per month.**

5. **No real-time analysis.** Analysis takes 1–3 minutes. A progress bar is shown. This is
   acceptable for the target use case. **Assumption: user tolerates a 2-minute wait.**

6. **Wikipedia and Semantic Scholar are sufficient for most claims.** Political and economic
   claims in Spanish debates often cite EU statistics, INE (Spain), or well-known economists.
   These are indexable via Wikipedia and Semantic Scholar. **Assumption: no specialized
   Spanish-language databases are needed for the MVP.**

---

## 15  Open Questions

All five initial open questions are now answered. Decisions are recorded in §0.

**Remaining open question (pre-Phase 2b):**

- **Evidence language:** When querying Semantic Scholar or Wikipedia for a Spanish-language
  claim, should the search query be sent in Spanish or translated to English first?
  English queries return more results, but may miss Spain-specific sources (INE, BOE, etc.).
  **Tentative approach:** try Spanish query first; if fewer than 3 results, retry in English.

---

## 16  What to Build First

**Start with Phase 2a milestone 1: the claim extractor.**

The single most valuable thing Phase 2 can deliver is a list of explicit claims extracted
from the transcript, classified by type and checkability. Everything else (evidence,
verdicts, graphs) is built on top of this foundation.

A claim table already gives users something useful: they can see at a glance what each
speaker claimed, whether it sounds checkable, and what search query they should type to
verify it themselves — even before any automated fact-checking is added.

**Concrete first step:**

1. Create `truth_checker/segmenter.py` — pure Python, 30 lines.
2. Create `truth_checker/extractor.py` — Claude Haiku call, structured JSON output.
3. Test on the existing Rallo–Garzón transcript by running it from the command line.
4. Once the output looks good to a human reader, add the "Analysis" tab to `app.py`.

This is the lowest-risk, highest-value starting point. It does not require any external
APIs (no Semantic Scholar, no Wikipedia), costs under $0.05 to run on a full debate, and
delivers immediately readable output.

---

## Appendix A — Claim type examples from a Spanish economics debate

| Claim | Type | Checkable |
|-------|------|-----------|
| "El paro bajó al 11,6% en el tercer trimestre de 2025." | Statistical | ✓ |
| "Las bajadas de impuestos generan más recaudación a largo plazo." | Causal | Partial |
| "Eso no es capitalismo, es mercantilismo de Estado." | Definitional | No |
| "Si seguimos así, la deuda superará el 140% del PIB en 2030." | Predictive | No (future) |
| "España creció más rápido que la media europea en 2024." | Comparative | ✓ |
| "El gasto social es un derecho, no un privilegio." | Moral | No |
| "Ese estudio que citas tiene conflictos de interés con el sector financiero." | Interpretive | Partial |
| "Yo conozco empresarios que no pueden contratar por los costes laborales." | Anecdotal | Partial |

---

## Appendix B — Relationship type decision tree

```
Did Speaker B's turn come after Speaker A's claim?
└── Yes → Did Speaker B acknowledge Speaker A's specific claim?
           ├── No  → "ignores" or "redirects" (new topic)
           └── Yes → Did Speaker B agree with the claim?
                      ├── Yes, fully → "supports"
                      ├── Yes, partially → "concedes" or "weakens"
                      └── No → Did Speaker B present counter-evidence or reasoning?
                                 ├── Yes → "refutes"
                                 ├── No, but reinterpreted it → "reframes"
                                 └── No, just expressed disagreement → "rebuts" (without evidence)
```

---

*Last updated: 2026-05-30*
*Phase 1 completion: P1–P10 done, P11 (deploy) pending.*
*Phase 2 completion: P16–P35 all done. Full Truth Checker build sprint complete.*
*Remaining work: P11 (deploy to Streamlit Community Cloud), `tests/` directory (golden transcript + unit tests).*
*This document covers Phase 2 (P16–P35).*

---

## 17  Implementation Prompt Sequence (Phase 2)

> Each prompt below is self-contained. Paste the full block into a new Claude Code session.
> You do not need prior context — all necessary detail is in the prompt.
> Complete one prompt and verify its output before moving to the next.
> Prompts build on each other: later prompts reference functions created by earlier ones.

**Progress: P16–P35 all done ✓ — Phase 2 complete**

| Prompt | Status | What it builds |
|--------|--------|----------------|
| P16 | ✓ | Storage schema: `analyses`, `claims`, `verdict_feedback` tables |
| P17 | ✓ | `truth_checker/` package + `segmenter.py` |
| P18 | ✓ | `extractor.py` — claim extraction (Claude Haiku) |
| P19 | ✓ | `classifier.py` — claim type + checkability (Claude Haiku) |
| P20 | ✓ | `threader.py` — thread grouping (Claude Sonnet) |
| P21 | ✓ | `test_phase2a.py` — CLI pipeline test |
| P22 | ✓ | `app.py` — Analysis tab, claim table, CSV export |
| P23 | ✓ | `evidence.py` — Wikipedia + Semantic Scholar retrieval |
| P24 | ✓ | `verifier.py` — factual verdict with reasoning (Claude Sonnet) |
| P25 | ✓ | `app.py` — Run Fact-Check, verdict badges, expanders, feedback form |
| P26 | ✓ | `translator.py` + `app.py` — EN↔ES claim translation toggle |
| P27 | ✓ | `responder.py` — cross-speaker response detection (Claude Sonnet) |
| P28 | ✓ | `visualizer.py` — pyvis argument graph + `requirements.txt` update |
| P29 | ✓ | `app.py` — Claims/Argument Map sub-tabs, Detect Responses, legend |
| P30 | ✓ | `rhetorician.py` — fallacy + device detection (Claude Sonnet) |
| P31 | ✓ | `app.py` — Rhetorical Profile sub-tab |
| P32 | ✓ | `scorer.py` + `reporter.py` — per-speaker scores + narrative |
| P33 | ✓ | `app.py` — Speaker Report sub-tab |
| P34 | ✓ | `exporters.py` — `build_analysis_pdf()` + `app.py` download buttons |
| P35 | ✓ | `storage.py` — `load_analysis_for_transcript()` + `app.py` shareable link |

---

### Prompt 16 — Extend Storage for Analysis Results

```
I am building a debate fact-checker web app in Python.
The file `storage.py` already has a SQLite database (`transcripts.db`) with a `transcripts`
table and these functions: _connect(), _init(), save_transcript(), load_transcript(), list_recent().

Edit `storage.py` to add support for storing analysis results.

Add three new tables inside _init() using CREATE TABLE IF NOT EXISTS:

  analyses (
    id               TEXT PRIMARY KEY,   -- UUID4
    transcript_id    TEXT NOT NULL,
    created_at       TEXT,               -- ISO 8601 UTC
    model_used       TEXT,
    status           TEXT,               -- "pending" | "complete" | "error"
    error_msg        TEXT,
    analysis_json    TEXT                -- full JSON blob (claims, threads, responses, summary)
  )

  claims (
    id               TEXT PRIMARY KEY,
    analysis_id      TEXT NOT NULL,
    transcript_id    TEXT NOT NULL,
    speaker          TEXT,
    start_ms         INTEGER,
    claim_type       TEXT,
    checkable        INTEGER,            -- 0 or 1
    verdict          TEXT,
    confidence       REAL,
    claim_json       TEXT                -- full claim object as JSON
  )

  verdict_feedback (
    id               TEXT PRIMARY KEY,
    claim_id         TEXT NOT NULL,
    analysis_id      TEXT NOT NULL,
    rating           TEXT,              -- "incorrect" | "misleading" | "incomplete"
    user_note        TEXT,
    created_at       TEXT
  )

Add these five functions:

  save_analysis(transcript_id: str, model_used: str) -> str
    Creates a new row in analyses with status="pending". Returns the UUID.

  complete_analysis(analysis_id: str, analysis_json: dict) -> None
    Updates status="complete" and writes analysis_json as JSON string.

  fail_analysis(analysis_id: str, error_msg: str) -> None
    Updates status="error" and writes error_msg.

  load_analysis(analysis_id: str) -> dict | None
    Returns the full analyses row as a dict, with analysis_json parsed back to dict.
    Returns None if not found.

  save_feedback(claim_id: str, analysis_id: str, rating: str, user_note: str) -> None
    Inserts a row into verdict_feedback.

Do not change any existing functions or tables.
```

---

### Prompt 17 — Turn Segmenter

```
I am building a debate fact-checker web app in Python.
A transcript is a dict with key "utterances": a list of dicts, each with:
  {"speaker": str, "start_ms": int, "end_ms": int, "text": str, "confidence": float, ...}

Speakers are labeled "A", "B", "C", etc. Multiple consecutive utterances from the same
speaker form one "turn".

Create the file `truth_checker/__init__.py` (empty).

Create the file `truth_checker/segmenter.py`. Write one function:

  segment_turns(utterances: list[dict]) -> list[dict]

Rules:
- Consecutive utterances with the same speaker are merged into one turn.
- Each turn dict has:
    {
      "turn_index": int,       -- 0-based, sequential across all speakers
      "speaker": str,
      "start_ms": int,         -- start_ms of the first utterance in the turn
      "end_ms": int,           -- end_ms of the last utterance in the turn
      "text": str,             -- utterance texts joined with a single space
      "utterance_count": int
    }
- Empty utterances (text is blank or whitespace only) are skipped.
- If utterances is empty, return [].

No external libraries or API calls. Pure Python only.
Add a short docstring to the function.
```

---

### Prompt 18 — Claim Extractor

```
I am building a debate fact-checker web app in Python.
I have `truth_checker/segmenter.py` with segment_turns() which returns a list of turn dicts:
  {"turn_index": int, "speaker": str, "start_ms": int, "end_ms": int, "text": str}

Create `truth_checker/extractor.py`. Write one function:

  extract_claims_from_turn(turn: dict, api_key: str) -> list[dict]

The function must:
1. Call the Claude API (model: claude-haiku-4-5-20251001) with this system prompt:
   "You are an argument analyst. Extract every discrete claim from the speaker turn below.
    A claim is a statement presented as true. Do not extract questions, expressions of
    preference ('I think we should...'), greetings, filler, or clear jokes and hyperbole.
    The turn may be in Spanish or English — preserve the original language in your output.
    Return a JSON array. Each item: {\"text\": str, \"start_hint\": str}.
    \"text\" is the exact or lightly cleaned claim. \"start_hint\" is the first 5 words of
    the sentence. If there are no claims, return []."
   User message: "Speaker: {turn['speaker']}\nText:\n{turn['text']}"
2. Parse the JSON array from the response. If parsing fails, log a warning and return [].
3. Assign each claim a unique ID: f"claim_{turn['turn_index']}_{i}" where i is 0-based index.
4. Return a list of dicts:
   {
     "id": str,
     "speaker": str,        -- from turn["speaker"]
     "turn_index": int,     -- from turn["turn_index"]
     "start_ms": int,       -- from turn["start_ms"] (best approximation available)
     "end_ms": int,         -- from turn["end_ms"]
     "text": str,
     "start_hint": str
   }

Use the anthropic Python SDK. Pass api_key as anthropic.Anthropic(api_key=api_key).
Do not hardcode the key. Add a 0.3 second sleep after each API call to avoid rate limits.
```

---

### Prompt 19 — Claim Classifier

```
I am building a debate fact-checker web app in Python.
I have claim dicts from truth_checker/extractor.py with keys:
  {id, speaker, turn_index, start_ms, end_ms, text, start_hint}

Create `truth_checker/classifier.py`. Write one function:

  classify_claim(claim: dict, api_key: str) -> dict

The function must:
1. Call the Claude API (model: claude-haiku-4-5-20251001) with this system prompt:
   "You are an argument analyst. Classify the claim below. The claim may be in Spanish
    or English — your labels must be in English regardless.
    Return a JSON object with these exact keys:
    - claim_type: one of [factual, statistical, causal, predictive, comparative,
      definitional, interpretive, moral, anecdotal]
    - checkable: true if verifiable against external data, false otherwise
    - evidence_in_speech: any data, statistic, or citation the speaker mentioned
      in support (empty string if none)
    - evidence_quality: one of [strong, moderate, weak, none]
      strong=specific named source or statistic, moderate=general reference to research,
      weak=anecdote or vague reference, none=bare assertion
    - suggested_query: if checkable=true, a 6-10 word search query for fact-checking
      (write the query in English even if the claim is in Spanish); else empty string
    - satirical: true only if the claim is clearly a joke or hyperbole, else false"
   User message: "Claim: {claim['text']}\nSpeaker: {claim['speaker']}"
2. Parse the JSON. On failure, log a warning and return the claim dict unchanged plus
   default values: claim_type="factual", checkable=False, evidence_in_speech="",
   evidence_quality="none", suggested_query="", satirical=False.
3. Return the original claim dict merged with the classification fields.

Use the anthropic Python SDK. Add a 0.3 second sleep after each call.
```

---

### Prompt 20 — Thread Grouper

```
I am building a debate fact-checker web app in Python.
I have a list of classified claim dicts from truth_checker/classifier.py.
Each claim has: {id, speaker, turn_index, start_ms, end_ms, text, claim_type, checkable, ...}

Create `truth_checker/threader.py`. Write one function:

  group_into_threads(claims: list[dict], api_key: str) -> list[dict]

The function must:
1. Build a compact claim list for the prompt — only: id, speaker, text (no other fields).
2. Call the Claude API (model: claude-sonnet-4-6) once with this system prompt:
   "You are an argument analyst reviewing a debate transcript.
    Group the following claims into argument threads. A thread is a set of claims that
    share the same topic or sub-topic, regardless of which speaker made them.
    Aim for 3–8 threads. Assign every claim to exactly one thread.
    If a claim fits no other thread, assign it to a thread with topic 'miscellaneous'.
    Return a JSON array of thread objects:
    [{
      'thread_id': str,       -- short slug, e.g. 'real_wages_2024'
      'topic': str,           -- plain-language label, 5-8 words
      'claim_ids': [str]      -- claim IDs in chronological order
    }]"
   User message: the compact claim list as a JSON string.
3. Parse the JSON array. On failure, assign all claims to one thread with id='main' and
   topic='General debate'.
4. Add "thread_id" and "thread_topic" fields to each claim dict in-place, keyed by claim id.
5. Return the threads list (not the claims — the caller can read thread_id from each claim).

Use the anthropic Python SDK. Max tokens: 2048. No sleep needed (only one call).
```

---

### Prompt 21 — Phase 2a CLI Test

```
I am building a debate fact-checker web app in Python.
I have these modules ready:
- storage.py         → load_transcript(transcript_id: str) -> dict | None
- truth_checker/segmenter.py  → segment_turns(utterances) -> list[dict]
- truth_checker/extractor.py  → extract_claims_from_turn(turn, api_key) -> list[dict]
- truth_checker/classifier.py → classify_claim(claim, api_key) -> dict
- truth_checker/threader.py   → group_into_threads(claims, api_key) -> list[dict]

Create `truth_checker/test_phase2a.py`. This is a CLI test script (not part of the app).

The script must:
1. Load ANTHROPIC_API_KEY from .env using python-dotenv.
2. Load the most recent transcript from the database using storage.list_recent(limit=1).
   If the database is empty, print an error and exit.
3. Load the full transcript with load_transcript(id).
4. Run the four steps: segment_turns → extract (all turns) → classify (all claims) →
   group_into_threads.
5. Print a progress message before each step.
6. After step 4, print:
   - Total turns, total claims extracted, number of threads
   - A table with columns: Thread | Speaker | Time | Type | Checkable | Claim (truncated to 80 chars)
     sorted by thread_id then start_ms
7. Save the full claim list and thread list as JSON to `audio_tmp/phase2a_test_output.json`.

Print clear step-by-step progress. Catch and print any exceptions without crashing the script.
```

---

### Prompt 22 — Analysis Tab UI (Phase 2a)

```
I am building a debate fact-checker web app in Streamlit.
The app already has a transcript display in app.py.
I have these new modules:
- truth_checker/segmenter.py  → segment_turns(utterances) -> list[dict]
- truth_checker/extractor.py  → extract_claims_from_turn(turn, api_key) -> list[dict]
- truth_checker/classifier.py → classify_claim(claim, api_key) -> dict
- truth_checker/threader.py   → group_into_threads(claims, api_key) -> list[dict]
- storage.py                  → save_analysis(), complete_analysis(), fail_analysis()

Edit `app.py`:

1. Wrap the existing transcript display in a tab called "Transcript" using st.tabs().
   Add a second tab "Analysis / Análisis".

2. In the Analysis tab:
   a. If no transcript is loaded in session state, show "Load a transcript first."
   b. Show a "Run Analysis" button with an estimated cost note:
      "Estimated cost: ~$0.05–$0.15 (Claude Haiku + Sonnet)"
   c. When clicked:
      - Show a progress bar (4 steps: segmenting, extracting, classifying, grouping).
      - Run the four pipeline steps. Store results in st.session_state["analysis"].
      - Save to storage (save_analysis → complete_analysis or fail_analysis on error).
      - On error, show st.error and stop.
   d. If st.session_state["analysis"] exists, show:
      - Summary: "{N} claims across {T} threads from {S} speakers"
      - A filter row: selectbox for speaker (All + each speaker name) and
        selectbox for claim type (All + each type).
      - A table rendered with st.dataframe() showing filtered claims:
        columns: Thread | Speaker | Time (MM:SS) | Type | Checkable | Claim text
        "Claim text" is truncated to 120 characters.
      - A st.download_button to export the filtered table as CSV.

3. Add bilingual labels for all new UI strings to the LABELS dict at the top of app.py.

Read ANTHROPIC_API_KEY from os.environ. If missing, show a warning and disable the button.
Do not change anything in the Transcript tab.
```

---

### Prompt 23 — Evidence Retrieval

```
I am building a debate fact-checker web app in Python.
I need to retrieve external evidence for checkable factual claims.

Create `truth_checker/evidence.py`. Write one function:

  retrieve_evidence(suggested_query: str, language: str = "es",
                    max_results: int = 5) -> list[dict]

The function must query two free APIs in this order:

API 1 — Wikipedia (always queried first):
  URL: https://en.wikipedia.org/w/api.php (English) or https://es.wikipedia.org/w/api.php (Spanish)
  Use 'action=query&list=search&srsearch={query}&srlimit=3&format=json'
  Then fetch the extract for the top result:
  'action=query&prop=extracts&exintro=true&explaintext=true&titles={title}&format=json'
  Each result dict: {"title": str, "snippet": str (first 400 chars of extract),
                     "url": str, "source": "wikipedia"}

API 2 — Semantic Scholar:
  URL: https://api.semanticscholar.org/graph/v1/paper/search
  Params: query={suggested_query in English}, fields=title,year,citationCount,abstract, limit=5
  Filter: only papers with citationCount >= 5 and abstract not None.
  Each result dict: {"title": str, "snippet": str (first 400 chars of abstract),
                     "url": f"https://semanticscholar.org/paper/{paperId}",
                     "year": int, "citation_count": int, "source": "semantic_scholar"}

Language fallback: if language == "es" and Wikipedia Spanish returns 0 results,
retry with the English Wikipedia.

Merge results, deduplicate by title (case-insensitive), return up to max_results.
If both APIs fail or return nothing, return [].

Use only the requests library. Add a 1 second timeout to each request.
Handle all network errors gracefully — log a warning, do not raise.
No API keys required for either endpoint.
```

---

### Prompt 24 — Factual Verifier

```
I am building a debate fact-checker web app in Python.
I have evidence dicts from truth_checker/evidence.py:
  {"title": str, "snippet": str, "url": str, "source": str, ...}

Create `truth_checker/verifier.py`. Write one function:

  verify_claim(claim: dict, evidence: list[dict], api_key: str) -> dict

Where claim has at minimum: {id, text, speaker, claim_type, checkable}.

The function must:
1. If evidence is empty, return immediately with:
   {"verdict": "unverifiable", "confidence": 0.0,
    "explanation": "No external evidence was found for this claim.",
    "for_the_claim": "", "against_the_claim": "", "key_source": "", "all_sources": []}
2. Format the evidence as a numbered list of "Title: ...\nExcerpt: ..." strings.
3. Call the Claude API (model: claude-sonnet-4-6) with this system prompt:
   "You are a fact-checker writing for a general audience. Assess the claim below using
    only the provided evidence. Do not use outside knowledge. Write in plain language.
    Return a JSON object:
    - verdict: one of [true, partially_true, contested, misleading, false, unverifiable, subjective]
    - confidence: float 0.0-1.0 reflecting how strongly the evidence supports the verdict
    - explanation: 2-3 plain-language sentences explaining the verdict, citing specific evidence
    - for_the_claim: (only if verdict=contested) one sentence on what supports it, else ''
    - against_the_claim: (only if verdict=contested) one sentence on what contradicts it, else ''
    - key_source: title and URL of the most relevant source
    - all_sources: list of {title, url} for every source you used
    Do not fabricate sources. If evidence is insufficient return verdict=unverifiable."
   User message: "Claim: {claim['text']}\nSpeaker: {claim['speaker']}\n\nEvidence:\n{formatted}"
4. Parse the JSON. On failure, log a warning and return verdict="unverifiable", confidence=0.0.
5. Return the parsed dict merged with {"claim_id": claim["id"]}.

Use the anthropic Python SDK. Max tokens: 512.
```

---

### Prompt 25 — Phase 2b UI Update (Verdicts)

```
I am building a debate fact-checker web app in Streamlit.
The Analysis tab in app.py already shows a claim table (from Phase 2a).
I now have:
- truth_checker/evidence.py  → retrieve_evidence(suggested_query, language) -> list[dict]
- truth_checker/verifier.py  → verify_claim(claim, evidence, api_key) -> dict

Edit `app.py` — Analysis tab only. Do not touch the Transcript tab.

Changes:
1. Add a second button "Run Fact-Check" that appears after "Run Analysis" has completed
   and st.session_state["analysis"] exists. It is disabled if no ANTHROPIC_API_KEY is set.

2. When "Run Fact-Check" is clicked:
   - Filter to only checkable claims (checkable=True, satirical=False).
   - For each checkable claim, call retrieve_evidence then verify_claim.
   - Show a progress bar: "Fact-checking claim N of M…"
   - Store the dict of {claim_id: verdict_dict} in st.session_state["verdicts"].

3. In the claim table, when verdicts exist, add a "Verdict" column before "Claim text".
   Render verdicts as colored badges using st.markdown with unsafe_allow_html=True:
   - true         → green background  #d4edda  label "True"
   - partially_true → yellow #fff3cd  label "Partly True"
   - contested    → orange #fde8c8    label "Contested"
   - misleading   → orange #fde8c8    label "Misleading"
   - false        → red    #f8d7da    label "False"
   - unverifiable → grey   #e2e3e5    label "Unverifiable"
   - subjective   → grey   #e2e3e5    label "Subjective"
   - (no verdict yet) → grey #e2e3e5  label "—"

4. Below the table, for each claim that has a verdict (in thread order), show an expander:
   Title: "[Time] Speaker — truncated claim text (40 chars)"
   Inside the expander:
   - Full claim text
   - Verdict badge + confidence bar (st.progress)
   - Explanation paragraph
   - If contested: "In favour:" / "Against:" sub-sections
   - "Sources" sub-section: each source as a markdown link [title](url)
   - 👎 button labeled "Report an error". When clicked, show a small form:
     radio: Incorrect / Misleading / Incomplete + optional text input.
     On submit, call storage.save_feedback(claim_id, analysis_id, rating, note).

Add all new UI strings to the LABELS dict (bilingual EN/ES).
```

---

### Prompt 26 — On-Demand Translator

```
I am building a debate fact-checker web app in Python.
Claim texts are stored in the debate's original language (Spanish or English).
Users may want to read claims in the other language via a toggle button.

Create `truth_checker/translator.py`. Write one function:

  translate_claim(text: str, source_lang: str, target_lang: str,
                  api_key: str) -> str

Where source_lang and target_lang are "es" or "en".

The function must:
1. If source_lang == target_lang, return text unchanged.
2. Call the Claude API (model: claude-haiku-4-5-20251001) with:
   System: "You are a translator. Translate the text below from {source_lang} to
            {target_lang}. Preserve the original meaning exactly. Do not add commentary.
            Return only the translated text, nothing else."
   User: text
3. Return the response content string stripped of leading/trailing whitespace.
4. On any API error, log a warning and return the original text unchanged.

Use the anthropic Python SDK. Max tokens: 256.

Then edit `app.py` — in the claim expander section (added in Prompt 25):
- Add a small toggle button "🌐 Show in English" / "🌐 Mostrar en español" below the full
  claim text. It should only appear when the transcript language differs from the UI language.
- On click, call translate_claim and display the translation in a grey info box.
- Cache translations in st.session_state keyed by (claim_id, target_lang) so the API is
  not called again on re-render.
```

---

### Prompt 27 — Response Detector

```
I am building a debate fact-checker web app in Python.
I have a list of classified claim dicts (sorted by start_ms ascending), each with:
  {id, speaker, turn_index, start_ms, text, thread_id, claim_type, checkable}

Create `truth_checker/responder.py`. Write one function:

  detect_responses(claims: list[dict], api_key: str) -> list[dict]

The function must process claims in chronological order. For each claim after the first:
1. Collect the last 8 prior claims from DIFFERENT speakers as context.
2. Call the Claude API (model: claude-sonnet-4-6):
   System: "You are an argument analyst. Determine whether the current claim is a direct
            response to any of the listed prior claims.
            Relationship types: refutes (presents counter-evidence or reasoning),
            supports (agrees or extends), weakens (qualifies or reduces strength),
            reframes (accepts fact, changes interpretation), concedes (acknowledges
            the other is at least partly right), evades (changes subject), ignores (no link).
            Return a JSON object:
            {is_response: bool, responds_to_claim_id: str|null,
             relationship: str|null, explanation: str}"
   User: "Current claim (Speaker {speaker}): {text}\n\nPrior claims:\n{numbered list}"
3. Parse the JSON. On failure, return is_response=false.
4. If is_response=true, build a response edge dict:
   {id: f"resp_{claim['id']}", from_claim_id: claim['id'],
    responds_to_claim_id: ..., from_speaker: claim['speaker'],
    relationship: ..., explanation: ..., start_ms: claim['start_ms']}
   Append it to the results list.

Return the list of response edge dicts (not the claims themselves).
Add a 0.5 second sleep between API calls. Log warnings on parse failures.
```

---

### Prompt 28 — Argument Graph Visualizer

```
I am building a debate fact-checker web app in Python.
I have lists of claim dicts and response edge dicts from truth_checker/responder.py.
I want to render an interactive argument graph in Streamlit.

First, add pyvis and networkx to requirements.txt.

Create `truth_checker/visualizer.py`. Write one function:

  build_graph_html(claims: list[dict], responses: list[dict],
                   speaker_names: dict) -> str

Where speaker_names maps speaker ID to display name: {"A": "Rallo", "B": "Garzón"}.

The function must:
1. Create a pyvis Network (height="600px", width="100%", directed=True, bgcolor="#ffffff").
2. Add one node per claim:
   - id: claim["id"]
   - label: first 40 chars of claim["text"] + "…"
   - title: full claim text (shown on hover)
   - color: one per speaker (cycle through ["#1f77b4","#2ca02c","#d62728","#9467bd","#8c564b"])
   - shape: based on claim_type:
       factual/statistical/comparative → "dot"
       causal/predictive → "diamond"
       definitional/interpretive → "square"
       moral/anecdotal → "triangle"
   - size: 20 if checkable else 14
3. Add one edge per response:
   - from: responds_to_claim_id, to: from_claim_id
   - color based on relationship:
       refutes → "#d62728" (red), supports → "#2ca02c" (green),
       weakens/concedes → "#ff7f0e" (orange), reframes → "#9467bd" (purple),
       evades/ignores → "#aaaaaa" (grey)
   - title: relationship + ": " + explanation (shown on hover)
   - arrows: "to"
4. Set physics options: {"solver": "forceAtlas2Based"}.
5. Return the HTML string using network.generate_html().

Return empty string if claims list is empty.
```

---

### Prompt 29 — Phase 2c UI (Argument Map)

```
I am building a debate fact-checker web app in Streamlit.
The Analysis tab in app.py has a claim table and verdict expanders.
I now have truth_checker/visualizer.py → build_graph_html(claims, responses, speaker_names) -> str.
I also have truth_checker/responder.py → detect_responses(claims, api_key) -> list[dict].

Edit `app.py` — Analysis tab only.

Changes:
1. Inside the Analysis tab, add st.tabs(["Claims", "Argument Map"]) to create two sub-tabs.
   Move the existing claim table and verdict expanders into the "Claims" sub-tab.

2. Add a "Detect Responses" button in the Claims sub-tab (shown after Run Fact-Check, or
   after Run Analysis if fact-check has not been run). When clicked:
   - Call detect_responses(claims, api_key) with a progress spinner.
   - Store results in st.session_state["responses"].

3. In the "Argument Map" sub-tab:
   - If no analysis exists: show "Run Analysis first."
   - If analysis exists but no responses: show a note "Run Detect Responses to enable the map."
   - If responses exist: call build_graph_html and render with st.components.v1.html(html, height=620).
   - Below the graph, show a legend using st.markdown:
     Node color = speaker. Node shape = claim type. Edge color = response relationship.
     List each color/shape and its meaning in a compact grid.

4. Add all new UI strings to the LABELS dict (bilingual EN/ES).
```

---

### Prompt 30 — Rhetorical Analyzer

```
I am building a debate fact-checker web app in Python.
Speaker turns are dicts: {turn_index, speaker, start_ms, end_ms, text, utterance_count}.

Create `truth_checker/rhetorician.py`. Write one function:

  analyze_turn_rhetoric(turn: dict, api_key: str) -> dict

The function must:
1. Call the Claude API (model: claude-sonnet-4-6) with this system prompt:
   "You are a logician and rhetoric expert writing for a general (non-expert) audience.
    Analyze the speaker turn below for logical fallacies and rhetorical devices.
    Only flag clear, unambiguous examples — do not invent fallacies.
    Fallacies to check: straw_man, ad_hominem, false_dichotomy, appeal_to_authority
    (illegitimate), slippery_slope, cherry_picking, appeal_to_emotion (manipulative),
    anecdote_over_data, whataboutism, hasty_generalization, correlation_as_causation.
    Neutral devices to note: appeal_to_authority (legitimate), vivid_example, social_proof,
    personal_testimony, framing_effect, loaded_language.
    For each item found, return:
    {type: str, label: str (plain-language name, e.g. 'False choice'),
     quote: str (exact phrase from text), is_fallacy: bool,
     explanation: str (2-3 plain sentences: what happened, why it matters or does not,
     and for fallacies — what a stronger version would look like)}.
    Return JSON: {fallacies: [...], rhetorical_devices: [...]}. Empty lists if none found."
   User: "Speaker: {turn['speaker']}\nText:\n{turn['text']}"
2. Parse JSON. On failure, log warning and return {"fallacies": [], "rhetorical_devices": []}.
3. Add {"turn_index": turn["turn_index"], "speaker": turn["speaker"], "start_ms": turn["start_ms"]}.
4. Return the dict.

Use the anthropic Python SDK. Max tokens: 1024. Add 0.3 second sleep after the call.
```

---

### Prompt 31 — Phase 2d UI (Rhetorical Profile)

```
I am building a debate fact-checker web app in Streamlit.
The Analysis tab has Claims and Argument Map sub-tabs.
I now have truth_checker/rhetorician.py → analyze_turn_rhetoric(turn, api_key) -> dict.

Edit `app.py` — Analysis tab only.

Changes:
1. Add a third sub-tab "Rhetorical Profile / Perfil retórico" to the existing sub-tabs.

2. Add a "Analyze Rhetoric" button in the Claims sub-tab. When clicked:
   - Run analyze_turn_rhetoric on each turn (from the segmented turns list).
   - Show a progress bar: "Analyzing turn N of M…"
   - Store results as a list in st.session_state["rhetoric"].

3. In the "Rhetorical Profile" sub-tab:
   - If no rhetoric data: show "Run Rhetoric Analysis first."
   - Group findings by speaker. For each speaker, show a collapsible st.expander:
     Title: "{speaker name} — {N} fallacies · {M} rhetorical devices"
     Inside:
     - Section "Logical fallacies" (only if any):
       For each fallacy across all of that speaker's turns:
         [MM:SS] **{label}** — "{quote}"
         > {explanation}
     - Section "Rhetorical devices" (only if any is_fallacy=False):
       Same format, but without the negative framing.
   - Show a small note at the bottom: "Rhetorical devices are not always flaws. Labels show
     technique, not quality."

4. Add all new UI strings to the LABELS dict (bilingual EN/ES).
```

---

### Prompt 32 — Scorer and Reporter

```
I am building a debate fact-checker web app in Python.
I have:
- Claim dicts with optional verdict field (from st.session_state["verdicts"])
- Response edge dicts (from st.session_state["responses"])
- Rhetoric dicts (from st.session_state["rhetoric"])

Create `truth_checker/scorer.py`. Write one function:

  compute_speaker_scores(claims: list[dict], responses: list[dict],
                         rhetoric: list[dict]) -> dict

Returns a dict keyed by speaker ID:
  {
    "total_claims": int,
    "checkable_claims": int,
    "verdicts": {true: int, partially_true: int, contested: int,
                 misleading: int, false: int, unverifiable: int, subjective: int},
    "evidence_quality": {strong: int, moderate: int, weak: int, none: int},
    "reliability_score": float,   -- (true + partially_true) / checkable_claims; null if 0 checkable
    "total_responses_made": int,  -- responses where from_speaker == this speaker
    "evasions": int,              -- responses with relationship in [evades, ignores]
    "direct_response_rate": float, -- (total_responses_made - evasions) / total_responses_made; null if 0
    "fallacy_count": int,
    "fallacy_types": [str]        -- unique fallacy type names
  }

Create `truth_checker/reporter.py`. Write one function:

  generate_speaker_summary(speaker_id: str, speaker_name: str,
                           score: dict, api_key: str) -> str

Calls Claude (model: claude-sonnet-4-6) with the score dict and returns a 2-paragraph
plain-language narrative summary. First paragraph: factual accuracy and evidence quality.
Second paragraph: how well they engaged with the other speaker's arguments.
Instruction in the prompt: write for a curious general reader; be fair and balanced;
do not editorialize beyond what the data shows. Max 200 words total.
Return the summary string. On API error return a fallback string with the raw numbers.
```

---

### Prompt 33 — Phase 2e UI (Speaker Report)

```
I am building a debate fact-checker web app in Streamlit.
The Analysis tab has Claims, Argument Map, and Rhetorical Profile sub-tabs.
I now have:
- truth_checker/scorer.py  → compute_speaker_scores(claims, responses, rhetoric) -> dict
- truth_checker/reporter.py → generate_speaker_summary(speaker_id, name, score, api_key) -> str

Edit `app.py` — Analysis tab only.

Changes:
1. Add a fourth sub-tab "Speaker Report / Informe de hablantes".

2. Add a "Generate Speaker Report" button in the Claims sub-tab. It requires that at least
   one of verdicts, responses, or rhetoric is present in session state (show a note if none).
   When clicked:
   - Call compute_speaker_scores with whatever data is available (pass empty lists for missing).
   - Call generate_speaker_summary for each speaker.
   - Store as st.session_state["speaker_report"] = {speaker_id: {score, summary}}.

3. In the "Speaker Report" sub-tab:
   - For each speaker, show their display name as a heading.
   - Show a metric grid (st.columns) with 4 cells:
       Reliability: "{reliability_score:.0%}" (or "N/A")
       Fact-checked claims: "{true+partially_true} of {checkable_claims} supported"
       Direct response rate: "{direct_response_rate:.0%}" (or "N/A")
       Logical fallacies: "{fallacy_count}"
   - Show a horizontal bar chart of verdict distribution using st.bar_chart on a small
     DataFrame (verdict types as index, count as value).
   - Show the narrative summary paragraph in a grey info box (st.info).
   - Add a divider between speakers.

4. Add all new UI strings to the LABELS dict (bilingual EN/ES).
```

---

### Prompt 34 — Analysis Export

```
I am building a debate fact-checker web app in Python.
The file exporters.py already has build_pdf(transcript, speaker_names) -> bytes.
After running the Truth Checker pipeline, st.session_state["analysis"] contains claims
and threads, and st.session_state["speaker_report"] contains scores and summaries.

Edit `exporters.py`. Add one new function:

  build_analysis_pdf(claims: list[dict], threads: list[dict],
                     speaker_names: dict, speaker_report: dict,
                     verdicts: dict, title: str) -> bytes

Uses reportlab (already in requirements.txt). Format:
- Page 1 header: "SayWhat — Debate Analysis Report" + title + date
- Section 1 "Speaker Summary": for each speaker, show the score grid and the summary
  paragraph. Use a table layout.
- Section 2 "Claims by Thread": for each thread, a heading with the thread topic, then
  a table with columns: Time | Speaker | Type | Claim (wrapped) | Verdict
  Verdict cell is plain text: True / Partly True / Contested / etc.
  Non-checkable claims: blank verdict cell.
- Section 3 "Fact-Check Details": for each claim with a verdict, the claim text + the
  full explanation paragraph + key source URL.
- Use reportlab Paragraph, Table, TableStyle, and SimpleDocTemplate.
- Font: Helvetica. Body size 9pt. Headings 12pt bold. Margins: 20mm all sides.

Then edit `app.py` — Analysis tab, Claims sub-tab:
- Add a "Download Analysis PDF" button below the claim table when analysis exists.
  Call build_analysis_pdf with current session state and use st.download_button.
- Add a "Download Analysis JSON" button that exports st.session_state["analysis"] +
  verdicts + speaker_report as a single JSON file.
```

---

### Prompt 35 — Analysis Shareable Link

```
I am building a debate fact-checker web app in Streamlit.
The app already stores transcripts with a UUID and loads them via ?id= query params.
storage.py has: save_analysis(transcript_id, model_used) -> str (returns analysis UUID)
and complete_analysis(analysis_id, analysis_json) -> None.

Edit `storage.py`:
Add one function:
  load_analysis_for_transcript(transcript_id: str) -> dict | None
  Fetches the most recent complete analysis for a given transcript_id.
  Returns the row with analysis_json parsed, or None.

Edit `app.py`:
1. After a successful "Run Analysis", call complete_analysis with the full analysis data
   (claims, threads, responses if available). Store the analysis_id in
   st.session_state["analysis_id"].

2. Update the shareable link display to include the analysis ID:
   If both transcript_id and analysis_id are known, the link is:
   {base_url}?id={transcript_id}&analysis={analysis_id}

3. On app startup, after reading ?id=, also read ?analysis= from st.query_params.
   If present, call load_analysis(analysis_id) and restore:
   - st.session_state["analysis"] from analysis_json["claims"] and analysis_json["threads"]
   - st.session_state["verdicts"] from analysis_json.get("verdicts", {})
   - st.session_state["speaker_report"] from analysis_json.get("speaker_report", {})
   Show an info banner: "Analysis loaded from saved link."

4. Update the LABELS dict with bilingual strings for the new banner and updated link text.
```
