# Scientific Improvement Plan — SayWhat Debate Fact-Checker

*Based on a deep reading of the 8 papers in `papers/` against the current pipeline.*
*Date: 2026-05-30*

---

## 1. Current Pipeline (Baseline)

```
Audio
  └─→ AssemblyAI transcription → speaker turns
        └─→ extractor.py        → claims (3–6 per turn, Claude Haiku)
              ├─→ threader.py   → topic threads (Claude Sonnet)
              ├─→ fact_checker  → verdicts (factual/statistical/comparative only)
              ├─→ responder.py  → cross-speaker response edges
              │                   (refutes/supports/weakens/reframes/concedes/evades/ignores)
              └─→ rhetorician.py → fallacies & rhetorical devices per turn

visualizer.py: pyvis graph — nodes = claims, edges = response relationships
```

**What the current architecture captures well:**
- Claims as discrete extractable units from speaker turns
- Cross-speaker argumentative relationships (the response graph)
- Rhetorical quality of individual turns
- Thematic grouping of claims
- Basic fact-checking of verifiable claims

**What it misses:** see Section 3.

---

## 2. Paper-by-Paper Findings

### 2.1 Dung (1995) — Abstract Argumentation Framework

**Core concept.** An argumentation framework is a pair ⟨AR, attacks⟩. Dung defines
three semantics for determining which arguments are collectively acceptable:

- **Preferred extension**: a maximal admissible set — the largest set of arguments that can defend itself
- **Stable extension**: a conflict-free set that attacks every argument not in it
- **Grounded extension** (skeptical): the *least* fixpoint of the characteristic function F_AF — what a cautious, skeptical reasoner would accept as undefeated

The key theorem: every argumentation framework has at least one preferred extension, and the
grounded extension is always defined (even if empty). An argument is in the grounded extension
only if all its attackers are themselves attacked by grounded arguments.

**What this means for the app.** `responder.py` already builds the AR set (claims) and the attacks
relation (edges). The visualizer renders it. But we never *evaluate* the graph — we never compute
which claims survive. Dung gives us the algorithm for free.

**Gap.** We build the AAF and stop. The user sees a graph of claims attacking claims and must
mentally reason about who "wins." Dung's grounded extension computes this formally.

**Limitation.** Dung's AAF treats arguments as atomic — no internal structure. It answers
"does claim A defeat claim B?" but not "does A defeat B because A attacks B's premise or B's
conclusion?" The internal-structure question requires Toulmin (§2.2) and Peldszus & Stede (§2.6).

---

### 2.2 Toulmin (1958) — The Uses of Argument

**Core concept.** Every argument has six functional components:

```
Data (D) ──────────────────────────────────────→ Claim (C)
            [since Warrant (W)]
            [because Backing (B)]
            [Qualifier (Q): presumably/certainly/possibly...]
            [unless Rebuttal (R) condition]
```

Toulmin's central insight: *warrants are what debates are really about.* Both sides often
agree on the data. Both sides often accept the logical form. The real fight is over the
inference rule — the warrant — that connects data to conclusion.

**What the app does.** `extractor.py` extracts only **C** — the conclusions. The data cited
by the speaker (D), the causal/inferential logic used (W), the modal certainty (Q), and
pre-empted objections (R) are all discarded.

**Gap.** Given a claim "real wages fell because of labor market deregulation," we extract
"real wages fell" and discard "because of labor market deregulation" — which is the
most contestable part of the argument and the one most worth fact-checking.

**Limitation.** Toulmin was designed for monological argumentation (a single speaker
building a case). In live debate, the dialogical dimension complicates warrant identification.
Peldszus & Stede (§2.6) provide a better scheme for dialectical texts.

---

### 2.3 Rittel & Webber (1973) — Wicked Problems

**Core concept.** Policy and planning problems are "wicked": they have no definitive
formulation, no stopping rule, and solutions that are good-or-bad rather than true-or-false.
Ten distinguishing properties are identified. Property 3 is most critical: *"solutions to
wicked problems are not true-or-false, but good-or-bad."*

**What the app does.** The fact-checker assigns verdicts ("True / False / Misleading /
Unverifiable") using language that implies objective correctness. The argument map suggests
there are "winning" arguments. The Speaker Report implies a scoreable debate.

**Gap.** Real political and economic debates — wages, trade, taxation, inequality —
are almost always debates about wicked problems. A claim like "labor market flexibility
reduces wages" is not verifiable the way "the Earth orbits the Sun" is. It depends on
model assumptions, time frames, counterfactuals, and value weightings. Treating it like
a factual claim with a correct answer misleads the user.

**Implication.** The app must communicate clearly where it can add value (verifiable
sub-claims) and where it cannot (interpretive/normative claims about wicked problems).
This is not just academic scruple — it is a core design constraint.

---

### 2.4 van Eemeren & Grootendorst (2004) — Pragma-Dialectics

**Core concept.** Argumentation is a *critical discussion* aimed at resolving a difference of
opinion by testing the acceptability of standpoints. Ten rules of rational critical discussion:

1. **Freedom rule**: neither party may prevent the other from advancing a standpoint
2. **Burden of proof rule**: a standpoint must be defended if challenged
3. **Standpoint rule**: attacks must address the actual standpoint advanced
4. **Relevance rule**: only relevant arguments may be used
5. **Unexpressed premise rule**: implicit premises must be acknowledged
6. **Starting point rule**: no false appeals to shared starting points
7. **Argument scheme rule**: the argument scheme used must be valid
8. **Validity rule**: reasoning must be logically valid
9. **Closure rule**: a failed defense means the standpoint must be retracted
10. **Usage rule**: no ambiguous or equivocal use of language

Violations of these rules constitute *fallacies* — not classical logical fallacies, but
procedural violations that prevent the discussion from resolving the difference rationally.

A critical discussion proceeds through four **dialectical stages**: (1) confrontation, where
the difference of opinion emerges; (2) opening, where procedures and shared premises are
established; (3) argumentation, the exchange proper; (4) concluding, where the result is determined.

**What the app does.** `rhetorician.py` detects an ad-hoc list of fallacies. This covers
many of the right targets but lacks principled grounding and misses the stage structure.

**Gaps.**
- Fallacy detection is not mapped to violated discussion rules, making explanations ad-hoc
- No tracking of dialectical stage per turn
- No detection of "relevance violations" (Rule 4) where a speaker appears to respond but
  actually attacks a different standpoint from the one advanced

---

### 2.5 Stab & Gurevych (2014) — Argument Mining in Persuasive Essays

**Core concept.** An argument consists of a **major claim** (thesis), **claims** (controversial
statements), and **premises** (reasons for claims). Corpus distribution: 4.8% major claims,
22.8% claims, **55% premises**, 17.4% non-argumentative. Identifying premises is essential —
a claim cannot be properly evaluated without knowing what supports it.

**What the app does.** `extractor.py` extracts only claims. The ~55% of argumentative content
that consists of premises is currently invisible to the entire pipeline.

**Gap.** This is the most consequential structural gap. When a speaker says:

> "Real wages have fallen [CLAIM] as shown by INE data from 2008–2018 [DATUM/PREMISE],
>  because labor market flexibility reforms reduced workers' bargaining power [CAUSAL PREMISE]."

We extract "Real wages have fallen" and discard the two premises — the evidence cited and
the causal mechanism — which are what the debate is actually about.

**Consequence for the argument map.** The current map shows claim-to-claim attacks, but
the actual argumentative structure is argument-to-argument (a claim plus its premises is
an argument). A speaker who attacks only the conclusion node may be missing the more
vulnerable premise. The map cannot show this because premises don't exist in the data model.

---

### 2.6 Peldszus & Stede (2013) — Argumentation Mining: A Survey

**Core concept.** Proposes a unified annotation scheme distinguishing:

**Support structures:**
- Basic argument: single premise → conclusion
- Linked support: premises that only work together
- Multiple support: independent arguments for the same conclusion
- Serial support: chained arguments (premise → intermediate → conclusion)
- Example support (dashed): inductive examples

**Attack structures:**
- **Rebuttal**: attacks the conclusion ("your claim is false")
- **Undercutter**: attacks the inference ("your premises don't support your conclusion")
- Counter-attacks on attacks (rebut a rebuttal, undercut an undercutter)

The **rebuttal vs. undercutter distinction** is the single most important theoretical insight
from this paper for the app.

**What the app does.** `responder.py` uses `refutes` and `weakens` for all attacks. Both map
to claim-to-claim edges in the visualizer.

**Gap.** The distinction between rebuttal and undercutting is lost:

- **Rebuttal**: "Real wages did NOT fall — the INE data shows a 2% increase" (attacks C)
- **Undercutter**: "Labor market deregulation doesn't necessarily reduce wages — Germany
  deregulated and wages rose" (attacks the warrant W linking the premise to C)

These require fundamentally different responses from the original speaker. Collapsing both
into `refutes` loses information the user needs to understand the debate.

**Also noted:** the "restatement" operation — when a speaker repeats the same claim verbatim
or paraphrastically. Currently treated as two separate claims, inflating claim counts and
causing duplicate fact-check calls.

---

### 2.7 Lippi & Torroni (2016) — Argumentation Mining: State of the Art

**Core concept.** Survey of the full AM pipeline. Key findings:
- Every existing system is genre-specific; there is no genre-agnostic AM system
- Budzynska et al. (2014) show "AM from dialogue cannot be satisfactorily addressed using
  dialogue-agnostic models" — spoken debate has its own pragmatics
- Structure prediction (our responder) has F1 ≈ 0.5 in the literature — this is the
  hardest step in the pipeline
- Abstract argumentation (Dung) vs. structured argumentation (Toulmin) is the key
  architectural choice

**What the app does.** The extractor uses a general-purpose LLM prompt not calibrated
for spoken debate dialogue specifically.

**Gaps.**
- The extractor prompt does not account for spoken-debate-specific phenomena: oral discourse
  markers, backchannels, embedded quotation of the opponent, metalinguistic commentary
- The responder's performance (~F1 0.5 in comparable systems) means the argument map
  contains a substantial proportion of spurious or missed edges — this should be
  communicated to the user
- The app conflates abstract-level (Dung) and structured-level (Toulmin) representations
  within a single graph, which is theoretically inconsistent

---

### 2.8 Slonim et al. (2021) — IBM Project Debater

**Core concept.** Four-module autonomous debate system: (1) Argument Mining (claim + evidence
+ stance detection from 400M articles), (2) Argument Knowledge Base (principled arguments by
topic class), (3) Rebuttal module (match opponent claims → response selection), (4) Debate
Construction (cluster + select + generate speech). Debates human experts live.

**Most relevant architectural insight.** Project Debater defines:
- **Claim**: "a concise statement with a clear stance towards the motion"
- **Evidence**: "a single sentence that clearly supports or contests the motion, yet is not
  merely a belief or a claim"

This claim/evidence split maps exactly to Stab & Gurevych's claim/premise split and Toulmin's C/D split.
Project Debater tracks **stance** (pro/con toward the debate motion) for every claim.

**Gaps in our app relative to Project Debater.**
- No stance tracking (pro/con/neutral relative to the debate's central question)
- No redundancy removal across claims within the same thread
- No background knowledge base — all knowledge comes from Claude's parametric memory

**Key observation from their evaluation section.** Slonim acknowledges there is no agreed
metric for debate "winner" — the problem is inherently subjective. This directly corroborates
Rittel & Webber: our app must not claim to score or rank debaters.

---

## 3. Consolidated Gap Matrix

| # | Gap | Relevant Papers | Current State | Missing |
|---|-----|-----------------|--------------|---------|
| G1 | Premise/datum extraction | Stab, Toulmin, Peldszus | Claims only | Premises that support each claim |
| G2 | Qualifier/certainty tracking | Toulmin | None | Modal strength of each claim |
| G3 | Stance detection (pro/con motion) | Slonim | None | Which side of the debate each claim supports |
| G4 | Claim survivability (Dung extensions) | Dung | None | Which claims survive all attacks (grounded extension) |
| G5 | Rebuttal vs. undercutter distinction | Peldszus & Stede | `refutes` conflates both | `undercuts` relationship type for inference attacks |
| G6 | Systematic fallacy taxonomy | van Eemeren | Ad-hoc list | Fallacies mapped to violated discussion rules |
| G7 | Epistemic humility framing | Rittel & Webber | "True/False" verdicts | "Supported/Contested" language; wicked-problem disclaimer |
| G8 | Restatement/deduplication | Peldszus & Stede, Slonim | None | Detect near-duplicate claims within threads |
| G9 | Dialectical stage labeling | van Eemeren | None | Stage per turn (confrontation/opening/argumentation/concluding) |
| G10 | Spoken-debate prompt calibration | Lippi & Torroni | General LLM prompts | Genre-specific exclusions for spoken dialogue |

---

## 4. Implementation Plan

Improvements are organized into three tiers by effort and impact.

---

### Tier 1 — High Impact, Low Effort (do first)

These require minimal code changes and no architectural rework. Each can be
implemented independently as a small PR.

---

#### I-1: Rename verdict labels (G7)
**File:** `app.py` (LABELS dict and verdict display logic)
**Change:** Replace "True / False / Misleading / Unverifiable" with
"Supported / Contested / Unsupported / Beyond scope"
**Rationale (Rittel & Webber):** "True" implies objective correctness for claims
that are about contested interpretations of evidence. The new labels communicate
epistemic qualification without abandoning usefulness.
**Effort:** 1 hour — string search-and-replace in LABELS dict + any verdict
storage format update.

---

#### I-2: Add `qualifier` field to extractor (G2)
**File:** `truth_checker/extractor.py`

**Change:** Extend the JSON schema returned by the extractor to include a
`qualifier` field capturing the modal certainty of each claim.

```python
# Updated _SYSTEM prompt addition:
'Each item: {"text": str, "start_hint": str, "qualifier": str}. '
'"qualifier" is one of: "definite" (stated as certain fact), '
'"probable" (likely/generally true), "possible" (may be true, hedged), '
'"speculative" (uncertain/hypothetical). '
'Infer from modal language: "certainly"→definite, "probably/tends to"→probable, '
'"perhaps/may/could"→possible, "might/unclear"→speculative.'
```

**Downstream impact:**
- Fact-checker can filter: only fact-check `definite` and `probable` claims
- Visualizer: node size or opacity can encode qualifier
- Speaker Report: show claim certainty distribution per speaker
**Effort:** 2 hours — prompt update + schema update + display in UI.

---

#### I-3: Add `stance` field to extractor (G3)
**File:** `truth_checker/extractor.py`, `app.py`

**Change:** Add a `"stance"` field per claim and require the debate motion/question
to be passed as a parameter to the extraction call.

```python
def extract_claims_from_turn(turn: dict, api_key: str, motion: str = "") -> list[dict]:
    ...
    # Motion added to system prompt if provided:
    motion_line = f'\nDebate motion: "{motion}"' if motion else ""
    # JSON schema extended:
    '{"text": str, "start_hint": str, "qualifier": str, "stance": str}. '
    '"stance" is "pro" (supports the motion), "con" (opposes it), or "neutral".'
```

**Downstream impact:**
- Speaker Report: show pro/con claim counts per speaker — who is making the
  offensive vs. defensive argument
- Argument map: node border color can encode stance (e.g. green rim = pro, red rim = con)
- Combined with Dung survivability (I-5): "Speaker A made 14 pro-motion claims,
  9 of which were in the grounded extension"
**Effort:** 3 hours — extractor update + motion input widget in app.py + display.

---

#### I-4: Systematic fallacy taxonomy in rhetorician (G6)
**File:** `truth_checker/rhetorician.py`

**Change:** Replace the ad-hoc fallacy list with van Eemeren's pragma-dialectical
taxonomy, mapping each fallacy to the discussion rule it violates.

```python
_SYSTEM = (
    "You are a logician and rhetoric expert. Analyze the speaker turn for violations "
    "of the rules of critical discussion (van Eemeren & Grootendorst 2004).\n"
    "Rule violations to detect:\n"
    "- Rule 1 (Freedom): ad_hominem, veiled_threat, silencing_the_opponent\n"
    "- Rule 2 (Burden of proof): shifting_burden, appeal_to_unfalsifiability\n"
    "- Rule 3 (Standpoint): straw_man, attacking_a_different_position\n"
    "- Rule 4 (Relevance): red_herring, whataboutism, tu_quoque\n"
    "- Rule 7 (Argument scheme): false_dichotomy, slippery_slope, "
    "hasty_generalization, false_analogy, appeal_to_authority (illegitimate), "
    "cherry_picking, correlation_as_causation\n"
    "- Rule 10 (Usage): loaded_language, equivocation, vague_terms_to_evade\n"
    "Neutral rhetorical devices (not violations): vivid_example, social_proof, "
    "personal_testimony, framing_effect, appeal_to_authority (legitimate).\n"
    "For each item found, return:\n"
    '{"type": str, "violated_rule": int|null, "label": str, "quote": str, '
    '"is_fallacy": bool, "explanation": str}.\n'
    "explanation: 2-3 sentences — what happened, why it matters, and for fallacies "
    "what a compliant version would look like.\n"
    'Return JSON: {"fallacies": [...], "rhetorical_devices": [...]}'
)
```

**Downstream impact:**
- Each fallacy now comes with a `violated_rule` integer linking it to the
  pragma-dialectical framework — richer, principled explanations
- Speaker Report can aggregate: "Speaker A violated Rule 7 (argument scheme) 4 times"
**Effort:** 2 hours — prompt rewrite + update `violated_rule` field in UI display.

---

#### I-5: Add `undercuts` response type (G5)
**Files:** `truth_checker/responder.py`, `truth_checker/visualizer.py`

**Change:** Add `undercuts` as a valid relationship type, distinct from `refutes`.

```python
# In responder.py:
_VALID_RELATIONSHIPS = {
    "refutes",    # attacks the CONCLUSION (the claim itself is false)
    "undercuts",  # attacks the INFERENCE (the premises don't support the claim)
    "supports", "weakens", "reframes", "concedes", "evades", "ignores",
}

# Updated prompt addition to _SINGLE_SYSTEM and _BATCH_SYSTEM:
"Distinguish: 'refutes' = the conclusion is false; 'undercuts' = the reasoning "
"from premises to conclusion is flawed even if premises are true."
```

```python
# In visualizer.py:
_EDGE_COLORS = {
    "refutes":   "#d62728",   # red — attacks conclusion
    "undercuts": "#e377c2",   # pink/purple — attacks inference
    "supports":  "#2ca02c",
    "weakens":   "#ff7f0e",
    "concedes":  "#ff7f0e",
    "reframes":  "#9467bd",
    "evades":    "#aaaaaa",
    "ignores":   "#aaaaaa",
}
```

**Effort:** 3 hours — prompt update + new edge color + legend update in UI.

---

#### I-6: Add wicked-problem disclaimer to UI (G7)
**File:** `app.py`

**Change:** In the fact-check tab, add an informational box that appears above
verdicts, contextualizing what the fact-checker can and cannot do.

```python
st.info(
    "**What this fact-check covers and what it does not.** "
    "This tool verifies factual sub-claims: statistics, historical events, "
    "cited studies, and comparable empirical assertions. It does NOT evaluate "
    "normative claims ('we should do X'), value judgments, or contested "
    "interpretations of economic/social data — these are matters of ongoing "
    "scholarly and political debate that have no single correct answer. "
    "Claims of those types are labeled 'Beyond scope'."
)
```

**Also:** Add `normative` to the claim type taxonomy in the extractor and exclude
it from fact-checking (alongside the existing `_VERIFIABLE_TYPES` filter).

**Effort:** 1 hour — UI text + one additional excluded type.

---

### Tier 2 — High Impact, Medium Effort

These require more substantial changes but no architectural rewrite.

---

#### I-7: Premise extraction (G1) ← most impactful single improvement
**File:** `truth_checker/extractor.py`, `truth_checker/visualizer.py`, `app.py`

**Change:** Extend the extractor JSON schema to include premises supporting each claim.

```python
# Updated _SYSTEM prompt:
'Each item: {"text": str, "start_hint": str, "qualifier": str, "stance": str, '
'"premises": [str]}. '
'"premises" is a list (possibly empty) of supporting reasons/data the speaker '
'cited for this claim in the same turn. Copy phrases verbatim or lightly clean. '
'"premises" are sub-claims that support "text" — not restatements of it. '
'Limit to the 1–3 most explicit supporting statements.'
```

**Downstream changes:**
- `visualizer.py`: render premise sub-nodes as smaller squares connected to their
  parent claim node with a dashed support arrow (distinct from solid cross-speaker edges)
- `app.py`: expand claim cards in the Claims tab to show premises
- Fact-checker: offer option to fact-check premises independently
- `threader.py`: include premise text when computing topic groups (richer signal)

**Schema migration:** claims stored in analyses will need a migration path.
New field `"premises": []` defaults to empty list for backward compatibility.

**Effort:** 1–2 days — extractor prompt + schema + visualizer + UI card display.

---

#### I-8: Compute Dung grounded extension (G4)
**File:** new `truth_checker/dung.py`, called from `app.py` after `detect_responses()`

**Change:** Pure Python postprocessor — no API calls. Implement the characteristic
function fixpoint algorithm on the response graph.

```python
# truth_checker/dung.py

def compute_grounded_extension(
    claims: list[dict],
    responses: list[dict],
) -> dict[str, str]:
    """
    Compute Dung's grounded extension over the claim/response graph.

    Returns a dict mapping claim_id → status:
      "grounded"   — in the grounded extension (skeptically accepted)
      "contested"  — attacked by at least one undefeated attacker
      "unattacked" — no attacks received
    """
    attack_types = {"refutes", "undercuts", "weakens"}
    claim_ids = {c["id"] for c in claims}

    # Build attack graph: attacked_id → set of attacking ids
    attackers: dict[str, set[str]] = {cid: set() for cid in claim_ids}
    for r in responses:
        if r.get("relationship") in attack_types:
            target = r.get("responds_to_claim_id")
            source = r.get("from_claim_id")
            if target in claim_ids and source in claim_ids:
                attackers[target].add(source)

    # Iterative fixpoint: grounded extension = least fixpoint of F_AF
    # F_AF(S) = { A | every attacker of A is attacked by S }
    grounded: set[str] = set()
    changed = True
    while changed:
        changed = False
        for cid in claim_ids:
            if cid in grounded:
                continue
            # A is acceptable w.r.t. grounded if every attacker of A is attacked by grounded
            if all(
                any(r.get("responds_to_claim_id") == atk and
                    r.get("relationship") in attack_types and
                    r.get("from_claim_id") in grounded
                    for r in responses)
                for atk in attackers[cid]
            ):
                grounded.add(cid)
                changed = True

    # Label each claim
    status = {}
    for cid in claim_ids:
        if cid in grounded:
            status[cid] = "grounded"
        elif attackers[cid]:
            status[cid] = "contested"
        else:
            status[cid] = "unattacked"
    return status
```

**Downstream:**
- `visualizer.py`: encode survivability as node border thickness
  (thick border = grounded, normal = unattacked, dashed = contested)
- `app.py` Speaker Report: "N claims were grounded (survived all attacks),
  M claims remained contested"
- Fact-check tab: sort/filter claims by survivability status

**Effort:** 4–6 hours — algorithm + integration + visualizer update + UI labels.

---

#### I-9: Restatement detection and deduplication (G8)
**File:** new `truth_checker/deduplicator.py`, called after extraction, before threading

**Change:** After all claims are extracted, run a semantic similarity pass within
each thread (or across all claims if threading is not yet done) to detect near-duplicates.

**Algorithm:**
1. For each pair of claims by the same speaker within 5 turns of each other,
   ask Claude Haiku (batch): "Are these two statements making the same assertion?
   Answer yes/no with one sentence of justification."
2. If yes: mark the later one as `"restatement_of": earlier_id`. Do not submit
   restatements to the fact-checker. Merge in the visualizer (or show as a single
   node with a restatement count badge).

**Cost:** Small — only same-speaker, close-proximity pairs need checking. For a
45-min debate with ~80 claims, this is at most 50–60 pairs, costing ~$0.005 with Haiku.

**Effort:** 1 day — deduplicator module + integration + UI display.

---

#### I-10: Spoken-debate prompt calibration (G10)
**File:** `truth_checker/extractor.py`

**Change:** Add dialogue-specific exclusion patterns to the extractor's system prompt,
calibrated for the specific characteristics of spoken political/economic debate.

```python
# Additional exclusion rules to add to _SYSTEM:
"- Oral discourse markers that are not part of the claim itself: "
  "'well', 'look', 'you see', 'I mean', 'right', 'obviously'\n"
"- Metalinguistic commentary: 'as I was saying', 'let me return to', "
  "'to summarize my position'\n"
"- Embedded quotation of the opponent's view presented for rebuttal: "
  "'you claim that X' or 'your argument is that X' — extract only "
  "the speaker's own assertions\n"
"- Rhetorical questions even when they have an implied answer: "
  "'and what has that achieved?'\n"
"- Performative acts: 'I agree', 'I disagree', 'I concede' — these are "
  "moves, not claims\n"
```

**Effort:** 1 hour — prompt update, test on known transcripts.

---

### Tier 3 — Medium Impact, Higher Effort (future work)

These are theoretically valuable but require substantial design and implementation work.

---

#### I-11: Dialectical stage labeling per turn (G9)
**File:** `truth_checker/rhetorician.py` or new `truth_checker/stage_labeler.py`

**Change:** Add a step that labels each speaker turn with its dialectical stage
following van Eemeren's four-stage model:

- **Confrontation**: speaker is establishing or sharpening a difference of opinion
- **Opening**: speaker is establishing shared starting points, definitions, or procedures
- **Argumentation**: speaker is advancing or defending arguments for/against a standpoint
- **Concluding**: speaker is drawing together results or claiming the standpoint is upheld

This runs as an additional pass over the transcript (one call per turn or batch),
consuming the rhetorician's budget.

**Value:** A timeline chart in the Speaker Report showing the stage sequence of each
speaker's turns — "Speaker A spent 70% of the debate in argumentation, Speaker B
spent 45% in confrontation (establishing disagreement) rather than arguing substantively."
This is a meaningful measure of argumentation quality.

**Effort:** 1–2 days — new module + timeline visualization component.

---

#### I-12: Full Toulmin decomposition (G1 extended)
**Supersedes I-7 if fully implemented.**

**Change:** Extend the extractor to produce full Toulmin-structured arguments:

```python
{
  "text": "Real wages have fallen",           # Claim (C)
  "datum": "INE data shows 12% drop 2008-18", # Data (D)
  "warrant": "nominal minus inflation = real", # Warrant (W) — implicit inference rule
  "qualifier": "probable",                     # Qualifier (Q)
  "rebuttal_cond": "unless productivity rose", # Rebuttal condition (R)
  "premises": ["INE data shows...", "deregulation reduced bargaining power"]
}
```

**Challenge:** The warrant (W) is often implicit — speakers do not state the inference
rule they are using. Extracting it reliably requires pragmatic inference that even Claude
Sonnet performs inconsistently on. Recommend leaving W for manual annotation or
presenting it as "inferred warrant — may be incorrect."

**Value:** The visualizer could expand any node to show its Toulmin structure.
The fact-checker could verify D independently from C. The responder could identify
which component an attack targets.

**Effort:** 2–3 days — extractor + visualizer expansion + schema migration.

---

#### I-13: Argument-level graph (architectural shift)
**This is the direction the literature collectively points toward.**

The papers suggest moving from the current *claim-level* model:
```
Nodes = bare claims
Edges = claim → claim (refutes/supports/...)
```

To an *argument-level* model:
```
Nodes = structured arguments (claim + premises)
Premise sub-nodes → claim node: dashed support arrows (intra-argument)
Claim node → claim node: solid attack arrows (cross-argument rebuttal)
Inference node → inference arrow: dotted undercut (undercutting)
```

This requires:
1. Premises extracted (I-7 complete)
2. `undercuts` relationship type (I-5 complete)
3. Visualizer redesigned with two visual layers (intra-argument support, inter-argument attack)
4. Dung's semantics evaluated at the argument level, not the claim level (I-8 extended)

**This is not a single PR but a version-level milestone.** It would be the single most
significant theoretical upgrade to the app, producing a visualization that is grounded
end-to-end in Toulmin (structure), Dung (semantics), Stab & Gurevych (mining methodology),
and Peldszus & Stede (annotation scheme).

**Effort:** 3–5 days of focused work once I-5, I-7, I-8 are complete.

---

## 5. Implementation Roadmap

```
Phase A — Labeling & Framing                              ✅ COMPLETE
  I-1  Rename verdict labels                              ✅ done (P1)
  I-6  Wicked-problem disclaimer in UI                   ✅ done (P1)
  I-4  Pragma-dialectical fallacy taxonomy in rhetorician ⚠ partial (P2) — see §10

Phase B — Richer Claim Schema                             ✅ COMPLETE
  I-2  Add qualifier field to extractor                  ✅ done (P3)
  I-3  Add stance field + motion input                   ✅ done (P4)
  I-10 Spoken-debate prompt calibration                  ✅ done (P3)

Phase C — Graph Enrichment                                ✅ COMPLETE
  I-5  Add undercuts relationship type                   ✅ done (P5)
  I-8  Compute Dung grounded extension                   ✅ done (P6)
  I-9  Restatement deduplication                         ✅ done (P7)

Phase D — Premise Layer                                   ✅ COMPLETE
  I-7  Premise extraction (extractor + claim card UI)     ✅ done (P8)
  I-7  Premises in argument map (visualizer)              ✅ done (P9, extended P12)

Phase E — Full Argument-Level Architecture                ✅ COMPLETE
  I-11 Dialectical stage labeling                         ✅ done (P10)
  I-12 Full Toulmin decomposition                         ✅ done (P11)
  I-13 Argument-level graph (architectural shift)         ✅ done (P12)
```

All phases are now complete. The full pipeline from claim extraction through
argument-level graph with Dung semantics, Toulmin structure, and dialectical
stage analysis is implemented. Remaining work consists of UI polish items
listed in Section 10 open issues.

---

## 6. What the Papers Say About the App's Limits

Beyond improvements, the papers collectively establish firm *epistemic limits* on what
any automated debate analysis system can achieve. These should be documented in the
app's about section and communicated to users.

**From Rittel & Webber (1973):** Real debates concern wicked problems. There are no
correct verdicts, no objective winners, no definitive argument maps. Any automated
analysis is at best a useful approximation that surfaces structure — it does not resolve
the underlying dispute.

**From Lippi & Torroni (2016):** Structure prediction (the argument map) has F1 ≈ 0.5
in the best published systems. Approximately half of the edges in the argument map will
be incorrect (either spurious or missing). The map is suggestive, not authoritative.

**From Slonim et al. (2021):** Even IBM Project Debater — a decade-long, multi-million
dollar project — cannot be evaluated by any agreed metric. The audience vote used in
their evaluation is itself imperfect. Declaring a debate "won" by either speaker is
outside the scope of what any automated system can legitimately claim.

**From van Eemeren & Grootendorst (2004):** What the pragma-dialectical model evaluates
is procedural rationality — whether the rules of critical discussion were followed — not
whether any standpoint is objectively correct. Our rhetorician operates at this level.
It can identify when an argument scheme was fallacious, not when a position is true.

These limits are not failures of the app. They are features of the domain. A fact-checker
that honestly represents its uncertainty is more valuable than one that confidently
overstates its conclusions.

---

## 7. Reference Table: Paper → App Component

| Paper | Theory | Primarily affects |
|-------|---------|-----------------|
| Dung (1995) | Grounded/preferred extensions, attack semantics | `responder.py` (graph), new `dung.py`, `visualizer.py` |
| Toulmin (1958) | Claim/data/warrant/qualifier/rebuttal structure | `extractor.py`, `visualizer.py` |
| Rittel & Webber (1973) | Wicked problems, no true-or-false solutions | `app.py` (UI framing, verdict labels) |
| van Eemeren & Grootendorst (2004) | Critical discussion rules, fallacy taxonomy, dialectical stages | `rhetorician.py`, new stage labeler |
| Stab & Gurevych (2014) | Claims vs. premises, argument component classification | `extractor.py`, `visualizer.py` |
| Peldszus & Stede (2013) | Rebuttal vs. undercutter, annotation scheme, restatements | `responder.py`, `deduplicator.py` |
| Lippi & Torroni (2016) | AM pipeline architecture, genre-specificity, performance limits | `extractor.py` (prompt), UI (confidence messaging) |
| Slonim et al. (2021) | Claim/evidence split, stance detection, evaluation limits | `extractor.py` (stance), `app.py` (UI) |

---

## 8. UI Design Principles

The scientific improvements in this plan add meaningful analytical depth, but depth
must never become an obstacle for regular users. The app serves two audiences at once:
a casual listener who wants to know "did he make that up?" and a more curious reader
who wants to understand how the argument actually worked. Both must feel at home.

The rule that governs every implementation prompt below is:

> **All academic machinery lives in the backend. The UI speaks plain language by
> default. Expert detail is available behind a toggle or collapsed expander — never
> forced on the user.**

### 8.1 Concrete principles

**Plain language always, jargon never in the UI.**
Every academic concept has a plain-language translation that must be used in all
user-facing text. Code variables, documentation, and this plan may use the academic
terms. The app may not.

| Academic term | Plain-language UI label |
|---|---|
| Grounded extension | "Survived all counterarguments" |
| Contested (Dung) | "Challenged — no clear winner" |
| Undercuts | "Challenges the reasoning" |
| Refutes | "Directly contradicts" |
| Qualifier: definite | "Stated as fact" |
| Qualifier: probable | "Presented as likely" |
| Qualifier: possible | "Presented as possible" |
| Qualifier: speculative | "Uncertain / hypothetical" |
| Dialectical stage: confrontation | "Establishing disagreement" |
| Dialectical stage: opening | "Setting the terms" |
| Dialectical stage: argumentation | "Making the argument" |
| Dialectical stage: concluding | "Drawing conclusions" |
| Premise | "Evidence cited" |
| Warrant hint | "Reasoning used" |
| Rebuttal condition | "Acknowledged exception" |
| Stance: pro | "Supports the motion" |
| Stance: con | "Opposes the motion" |

**Simple view by default.**
The default state of every tab and section must be readable without any prior knowledge
of argumentation theory. Features that add complexity are opt-in.

- The argument map has two layer toggles. **"Show supporting evidence"** defaults
  **on** (revised in P12 — premises are now the default view; the claim-only graph
  is opt-out). **"Show reasoning targets"** defaults **off** (proxy diamond nodes
  for undercutter attacks are a power feature that clutters the default map).
- Toulmin fields (reasoning used, acknowledged exception) are in a **collapsed
  expander** inside each claim card. The card is readable without opening it.
- The Rhetoric tab shows the dialectical stage timeline directly (not behind a
  toggle) because it is high-level and non-cluttering. The per-speaker fallacy
  detail is inside collapsed expanders, expanded only when fallacies exist.
- The Dung survivability badge is a small coloured icon next to each claim, not a
  prominent feature — visible but unobtrusive.

**One number, one sentence, one insight.**
Every new analytical result should surface as a single sentence the user can act on
or share, before exposing any detail. Examples:
- "9 of 14 claims by Speaker A survived all counterarguments."
- "Speaker B challenged the reasoning behind 4 claims rather than their conclusions."
- "Speaker A spent most of the debate making arguments; Speaker B spent most
  establishing disagreement."

**Complexity scales with curiosity.**
A user who clicks nothing should see: claim verdicts, a readable argument map, a
speaker summary. A user who expands sections should additionally see: evidence cited,
survivability breakdown, fallacy explanations, stage analysis. A user who downloads
JSON gets everything. Three layers, none of them required.

### 8.2 Prompts most affected by this principle

Three prompts in Phase D–E push visible complexity and must be implemented with
special care:

**P9 (premise sub-nodes in graph):** The graph must remain readable with premises
hidden. The "Show supporting evidence" toggle must default to **off**. When on,
limit to showing premises only for claims the user hovers over, or only for claims
in the currently selected thread — not all premises for all claims simultaneously.

**P11 (Toulmin full decomposition):** The claim card default view shows only the
claim text, verdict, and qualifier badge. Warrant and rebuttal condition appear in
a collapsed expander labelled "Reasoning details" — never visible by default.
Do not use the words "warrant" or "rebuttal condition" in the UI; use "Reasoning used"
and "Acknowledged exception."

**P12 (argument-level graph):** The proxy diamond node approach for undercutters is
visually complex. Implement it behind an additional toggle: "Show reasoning targets"
(default off). The default map shows solid and dashed edges without proxy nodes.
The legend must be written in plain language; no academic terminology.

---

## 9. Implementation Prompts

The prompts below are designed to be executed sequentially, one per session. Each prompt
is self-contained enough to implement on its own but builds on the outputs of previous ones.
They follow the Phase A → E roadmap in Section 5.

Files referenced throughout:
- `truth_checker/extractor.py` — claim extraction from speaker turns
- `truth_checker/responder.py` — cross-speaker response edge detection
- `truth_checker/rhetorician.py` — fallacy and rhetorical device detection
- `truth_checker/threader.py` — topic thread grouping
- `truth_checker/visualizer.py` — pyvis argument graph builder
- `app.py` — Streamlit UI (all tabs, settings, LABELS dict)

---

### Prompt 1 — Epistemic framing: verdict labels and wicked-problem disclaimer
*(implements I-1 and I-6 from Phase A)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

The app currently labels fact-check verdicts as "True", "False", "Misleading", and
"Unverifiable". Academic literature on wicked problems (Rittel & Webber 1973) shows
that real political and economic debates concern claims that are inherently contested —
they do not have objectively correct answers in the way scientific facts do. Presenting
verdicts as "True/False" overstates the app's epistemic authority.

Make two changes to `app.py`:

1. VERDICT LABEL RENAME: Find every place in the LABELS dict and the verdict display
   logic where "True", "False", "Misleading", "Unverifiable" appear as verdict strings
   (not in code logic — only in user-facing display text). Replace them with:
   - "True"          → "Supported"
   - "False"         → "Unsupported"
   - "Misleading"    → "Contested"
   - "Unverifiable"  → "Beyond scope"
   Do not change any conditional logic that compares against these strings — only the
   display labels. If verdicts are stored as one of those strings in session state, add
   a display-time mapping dict rather than changing the stored values.

2. WICKED-PROBLEM DISCLAIMER: In the fact-check tab, directly above the verdict list,
   add an `st.info()` box with this text (or its translation if the UI is in Spanish):
   "This fact-check covers verifiable sub-claims: statistics, historical events, and
   cited empirical data. It does not evaluate normative claims, value judgments, or
   contested interpretations of social and economic data — these involve ongoing scholarly
   debate and have no single correct answer. Claims of those types are labeled
   'Beyond scope'."

Read `app.py` carefully before editing to understand the current verdict display flow
and LABELS structure. Do not change any other logic.
```

---

### Prompt 2 — Pragma-dialectical fallacy taxonomy in the rhetorician
*(implements I-4 from Phase A)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

`truth_checker/rhetorician.py` currently detects fallacies using an ad-hoc list.
We want to ground it in van Eemeren & Grootendorst's pragma-dialectical theory (2004),
which classifies fallacies as violations of specific rules of critical discussion.
This makes explanations more principled and adds a `violated_rule` field that can be
displayed in the UI.

Rewrite the `_SYSTEM` prompt constant in `truth_checker/rhetorician.py` to:

1. Instruct the model to detect violations of these numbered discussion rules:
   - Rule 1 (Freedom): ad_hominem, silencing_the_opponent
   - Rule 2 (Burden of proof): shifting_burden, appeal_to_unfalsifiability  
   - Rule 3 (Standpoint): straw_man, attacking_a_different_position
   - Rule 4 (Relevance): red_herring, whataboutism, tu_quoque
   - Rule 7 (Argument scheme): false_dichotomy, slippery_slope, hasty_generalization,
     false_analogy, appeal_to_authority_illegitimate, cherry_picking,
     correlation_as_causation
   - Rule 10 (Usage): loaded_language, equivocation, vague_terms_to_evade

2. Keep the neutral rhetorical devices list (appeal_to_authority_legitimate,
   vivid_example, social_proof, personal_testimony, framing_effect) unchanged.

3. Change the JSON output schema for each fallacy to add a `violated_rule` field:
   `{"type": str, "violated_rule": int|null, "label": str, "quote": str,
    "is_fallacy": bool, "explanation": str}`
   `violated_rule` is the rule number (1, 2, 3, 4, 7, or 10) for fallacies, null for
   neutral rhetorical devices.

4. In `app.py`, find where rhetoric results are displayed (the Rhetoric tab or speaker
   report section). Add a small text label next to each fallacy showing which rule was
   violated, e.g. "(Rule 7 — Argument scheme)". Use the LABELS dict for any new strings.

Read both files before editing. Do not change `analyze_turn_rhetoric()`'s signature or
the retry/sleep/error-handling logic — only the prompt and the downstream display.
```

---

### Prompt 3 — Add `qualifier` field and spoken-debate calibration to extractor
*(implements I-2 and I-10 from Phase B)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

`truth_checker/extractor.py` extracts claims from speaker turns but does not capture
the modal certainty with which each claim is asserted. Toulmin (1958) calls this the
"qualifier" — the difference between "wages certainly fell" and "wages may have fallen."
We also want to improve the extractor's exclusion list for spoken debate dialogue, which
has specific phenomena not present in written text.

Make two changes to `truth_checker/extractor.py`:

1. ADD QUALIFIER FIELD: Extend the JSON schema the model returns to include a
   `"qualifier"` field per claim. Update the `_SYSTEM` prompt to define it as:
   - "definite"    — stated as an established fact, no hedging
   - "probable"    — likely true, language like "tends to", "generally", "in most cases"
   - "possible"    — hedged, language like "may", "could", "perhaps", "seems"
   - "speculative" — uncertain or hypothetical, language like "might", "I suspect"
   Add the field to the dict assembled in `extract_claims_from_turn()`. Default to
   "probable" if the model omits it.

2. SPOKEN-DEBATE CALIBRATION: Add these items to the "Do NOT extract" list in _SYSTEM:
   - Oral discourse markers that precede but are not part of the claim: "well", "look",
     "you see", "I mean", "obviously", "clearly" used as filler
   - Metalinguistic commentary: "as I was saying", "let me return to my point",
     "to summarize", "what I mean is"
   - Embedded quotation of the opponent's view set up for rebuttal: "you argue that X"
     or "your position is that X" — extract only the speaker's own assertions
   - Performative speech acts that are moves, not claims: "I agree", "I disagree",
     "I concede that", "I accept your point"

Read `extractor.py` fully before editing. Do not change the function signature or the
word-count guard. Verify the updated JSON is parsed correctly in `extract_claims_from_turn`.
```

---

### Prompt 4 — Stance detection and debate motion input
*(implements I-3 from Phase B)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

IBM's Project Debater (Slonim et al. 2021) tracks whether each claim is "pro" or "con"
relative to the debate motion. This enables a scoreboard view: how many claims per
speaker support vs. oppose the central question, and which ones survived all attacks.

Add stance detection to the pipeline:

1. EXTRACTOR — `truth_checker/extractor.py`:
   - Add a `"stance"` field to the JSON schema: "pro" (supports the motion/thesis),
     "con" (opposes it), or "neutral" (procedural or orthogonal claim).
   - Add a `motion: str = ""` parameter to `extract_claims_from_turn()`. When non-empty,
     include it in the user message: `f"Debate motion: {motion}\n"` before the speaker turn.
   - The _SYSTEM prompt should instruct the model to classify stance relative to that motion.
     If no motion is provided, always return "neutral".
   - Default the field to "neutral" if the model omits it.

2. APP — `app.py`:
   - In the transcription/setup section (before Run Analysis), add a text input:
     `motion = st.text_input("Debate motion or central question (optional)", ...)`
     Store in `st.session_state`. Pass it to `extract_claims_from_turn()` calls.
   - In the Speaker Report tab, add a simple breakdown per speaker:
     "Pro-motion claims: N | Con-motion claims: M | Neutral: K"
     Use the `stance` field already stored on each claim dict.
   - Add any new display strings to the LABELS dict.

Read both files before editing. The motion is optional — the app must work identically
when it is left blank. Do not break existing JSON import/export compatibility; the
`stance` field should default gracefully when absent from loaded files.
```

---

### Prompt 5 — Add `undercuts` as a response relationship type
*(implements I-5 from Phase C)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

Peldszus & Stede (2013) distinguish two fundamentally different types of attack:
- Rebuttal: "your conclusion is false" — attacks the claim directly
- Undercutter: "your premises don't support your conclusion" — attacks the inference

Currently `truth_checker/responder.py` collapses both into `refutes`. This loses
information the user needs to understand the debate, and matters for the Dung
grounded-extension computation we will add later.

Make these changes:

1. `truth_checker/responder.py`:
   - Add "undercuts" to `_VALID_RELATIONSHIPS`.
   - In both `_SINGLE_SYSTEM` and `_BATCH_SYSTEM`, add a line explaining the distinction:
     'Use "refutes" when the response denies the conclusion itself. Use "undercuts" when
     the response argues that the cited evidence or reasoning does not support the
     conclusion, even if the conclusion might still be true.'
   - No other logic changes needed — the existing `_build_edge` and parsing code will
     handle the new value automatically.

2. `truth_checker/visualizer.py`:
   - Add "undercuts" to `_EDGE_COLORS` with a visually distinct color from "refutes"
     (e.g. a muted magenta/pink: "#e377c2").
   - Update the pyvis legend (if one exists in `build_graph_html`) to include the new
     edge type with a plain-language label: "undercuts (attacks the reasoning)".

3. `app.py`:
   - If there is a legend or colour key for edge types in the argument map section,
     add "undercuts" there. Add any new strings to the LABELS dict.

Read all three files before editing. Do not change the relationship type of existing
stored analyses — the new type will only appear in newly run analyses.
```

---

### Prompt 6 — Dung grounded extension: claim survivability computation
*(implements I-8 from Phase C)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

Dung (1995) proves that any argumentation framework ⟨AR, attacks⟩ has a grounded
extension — the set of arguments that survive all attacks under skeptical semantics.
We already build this framework (claims = AR, response edges = attacks). We now want to
compute which claims are in the grounded extension and surface this in the UI.

1. Create `truth_checker/dung.py` with a single public function:

   def compute_grounded_extension(
       claims: list[dict],
       responses: list[dict],
   ) -> dict[str, str]:
       """
       Returns claim_id → status:
         "grounded"   — in the grounded extension (survives all attacks)
         "contested"  — attacked by at least one claim not in the grounded extension
         "unattacked" — no attacks received
       """

   Attack relationships are: "refutes", "undercuts", "weakens".
   Implementation: iterative fixpoint of Dung's characteristic function F_AF.
   Start with grounded = set of claims with no attackers. Then iteratively add claims
   whose every attacker is itself attacked by a claim already in grounded. Repeat until
   no new claims are added.

2. `truth_checker/visualizer.py`:
   - Add an optional `survivability: dict[str, str] = None` parameter to
     `build_graph_html()`.
   - When provided, encode survivability in node border width:
     - "grounded"   → borderWidth=3, border color "#2ca02c" (green)
     - "unattacked" → borderWidth=1 (default, no change)
     - "contested"  → borderWidth=2, border color dashed or "#ff7f0e" (orange)
     Use pyvis node options to set these properties.

3. `app.py`:
   - After `detect_responses()` returns and responses are stored in session state,
     call `compute_grounded_extension(claims, responses)` and store the result.
   - Pass it to `build_graph_html()`.
   - In the Claims tab and Speaker Report, show each claim's survivability status
     with a small badge or icon next to the claim text. Add strings to LABELS.

Read all files before editing. The computation must handle empty claims/responses
gracefully. Import `compute_grounded_extension` only where needed.
```

---

### Prompt 7 — Restatement detection and claim deduplication
*(implements I-9 from Phase C)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

When a speaker restates the same claim multiple times across different turns, we
currently treat each occurrence as a separate claim, inflating claim counts and
wasting fact-check API calls on the same assertion. Peldszus & Stede (2013) call
this the "restatement" phenomenon and provide a principled way to handle it.

Create `truth_checker/deduplicator.py` with one public function:

  def mark_restatements(
      claims: list[dict],
      api_key: str,
  ) -> list[dict]:
      """
      For each pair of claims by the same speaker where both share the same thread_id
      and the later claim occurs within 8 turns of the earlier one, ask Claude Haiku
      whether they assert the same proposition.

      Marks the later claim with "restatement_of": earlier_claim_id.
      Returns the same list, mutated in place.
      """

Rules:
- Only compare claims by the same speaker (same "speaker" field).
- Only compare within the same thread_id (requires threading to have run first;
  if thread_id is absent, skip deduplication).
- Only compare claims within 8 turns of each other (use "turn_index" field).
- Batch pairs: send up to 10 pairs in one Claude Haiku call using a structured prompt
  that returns a JSON array of booleans.
- A claim marked as a restatement should NOT be submitted to the fact-checker.
  It should still appear in the Claims tab but with a "(restatement)" label.

Wire it into `app.py`:
- Call `mark_restatements(claims, api_key)` after threading and before fact-checking.
- In the Claims tab, show restated claims with a muted style and a note
  "Restatement of: [original claim text truncated to 60 chars]".
- Add a counter in the Speaker Report: "X restatements detected (not fact-checked)".
- Add new strings to LABELS.

Read `app.py`, `extractor.py`, and `threader.py` for the claim dict structure before
writing the new module.
```

---

### Prompt 8 — Premise extraction in the extractor
*(first half of I-7 from Phase D)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

The most consequential structural gap in the current pipeline is that we extract only
claims (conclusions) but not the premises (supporting reasons and evidence) the speaker
cites for them. Stab & Gurevych (2014) show ~55% of argumentative text is premises.
Without them, the argument map is incomplete and the fact-checker checks only claims,
not the evidence cited for them.

Extend `truth_checker/extractor.py` to also extract premises:

1. Update the `_SYSTEM` prompt to change the JSON schema to:
   '{"text": str, "start_hint": str, "qualifier": str, "stance": str, "premises": [str]}'
   Define "premises" as: the 1–3 most explicit supporting reasons, data points, or
   evidence the speaker cited for this claim *in the same turn*. Extract verbatim or
   lightly cleaned phrases. If no supporting premise is stated, return [].
   Distinguish premises from the claim itself — a premise supports the claim, it is not
   a restatement of it.

2. In `extract_claims_from_turn()`, add "premises" to the assembled claim dict:
   `"premises": item.get("premises", [])` — default to empty list if absent.

3. In `app.py`, update the Claims tab to display premises under each claim:
   - If a claim has premises, show them in a collapsed `st.expander("Evidence cited")`
     below the claim text.
   - List each premise as a bullet point.
   - The fact-check result and other fields are unchanged.

4. Update the JSON download format for claims (the "fact_check" download) to include
   the premises array, so saved analyses preserve this information.

Read `extractor.py` and `app.py` carefully before editing. The change must be backward-
compatible: claims loaded from old JSON files without a "premises" field must default to [].
Do not yet change visualizer.py — the visual rendering of premises is a separate prompt.
```

---

### Prompt 9 — Render premises in the argument map
*(second half of I-7 from Phase D; requires Prompt 8 to be complete)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

Prompt 8 added premise extraction to the extractor. Claims now have a "premises" list.
We now want the argument map (built by `truth_checker/visualizer.py`) to show premises
as sub-nodes connected to their parent claim, visually distinguished from cross-speaker
attack/support edges.

Update `truth_checker/visualizer.py` — specifically `build_graph_html()`:

1. For each claim that has a non-empty "premises" list, add a premise sub-node for
   each premise string:
   - Node ID: f"prem_{claim_id}_{i}"
   - Shape: "box" (rectangular, distinct from claim circles/dots)
   - Size: 10 (smaller than claim nodes)
   - Color: a light grey (#cccccc) or pale version of the speaker's color
   - Label: first 35 chars of the premise text + "…" if longer
   - Title (tooltip): full premise text

2. Add a directed edge from each premise sub-node to its parent claim node:
   - Edge style: dashed (use pyvis `dashes: True` in edge options)
   - Color: same as the speaker's color but at 60% opacity
   - No arrowhead on the premise side; arrowhead pointing to the claim (arrow "to")
   - No label on the edge itself
   - Title (tooltip): "supports: [claim text truncated to 60 chars]"

3. Ensure existing cross-speaker edges (from `responses`) remain solid and unchanged.
   Premise edges are purely intra-speaker, intra-argument structure.

4. Update the graph legend (if present) to include: "□ Premise (supports parent claim)".

**UI simplicity constraint (see Section 8):** The "Show supporting evidence" checkbox
must default to **off**. When on, consider showing premise sub-nodes only for the
claim the user is hovering over, or only for claims in the selected thread — not all
premises for all claims at once. The graph must remain readable with premises hidden.

*Note (revised in P12):* The toggle was later changed to default **on**. The premise
layer proved to be informative without cluttering the graph, and the function signature
was extended in P12 (`show_premises: bool = True`) making the per-call control cleaner.

Read `visualizer.py` fully. Also read the pyvis Network documentation patterns in the
existing code. Test that the graph still renders when claims have no premises (empty list).
Do not change the function signature.
```

---

### Prompt 10 — Dialectical stage labeling per speaker turn
*(implements I-11 from Phase E)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

Van Eemeren & Grootendorst (2004) describe four stages of a critical discussion:
1. Confrontation — the difference of opinion is established
2. Opening — shared starting points and procedures are agreed
3. Argumentation — arguments for/against standpoints are exchanged
4. Concluding — the result of the discussion is determined

Labeling each speaker turn with its dialectical stage lets us analyze how debaters
structure their participation: are they spending time arguing substantively, or mostly
establishing and re-establishing disagreement?

Create `truth_checker/stage_labeler.py` with one public function:

  def label_dialectical_stages(
      turns: list[dict],
      api_key: str,
  ) -> list[dict]:
      """
      Labels each turn with its dialectical stage. Mutates turns in place, adding
      "dialectical_stage": one of "confrontation", "opening", "argumentation", "concluding".
      Returns the same list.
      """

Process in batches of 10 turns per API call (Claude Haiku). Each batch call receives
the turns as a numbered list and returns a JSON array of stage labels in the same order.
The system prompt should explain the four stages with brief examples. Default to
"argumentation" if a label is missing or invalid.

Wire into `app.py`:
- Add a "Run Stage Analysis" button in the Rhetoric tab (or run it alongside rhetoric
  analysis if rhetoric is already running).
- Display a timeline visualization using `st.bar_chart` or a simple colored sequence
  of labeled boxes showing the stage of each turn in order.
- In the Speaker Report, add a breakdown per speaker:
  "Confrontation: N turns | Opening: M | Argumentation: K | Concluding: J"
- Add all new strings to the LABELS dict.

The stage labels should be stored in session state and included in the rhetoric JSON
download. Read `rhetorician.py` and `app.py` for patterns to follow.
```

---

### Prompt 11 — Full Toulmin decomposition of extracted claims
*(implements I-12 from Phase E; requires Prompt 8 to be complete)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

Prompt 8 added premises to the claim schema. The full Toulmin model additionally
includes a Qualifier (Q) — already added in Prompt 3 — and a Rebuttal condition (R):
the exception under which the claim would not hold. The warrant (W) — the implicit
inference rule — is also part of Toulmin's model but is often not stated explicitly;
extract it only when the speaker has made it explicit.

Extend `truth_checker/extractor.py` to complete the Toulmin schema:

1. Add two new fields to the JSON schema:
   - "rebuttal_cond": str | null — a condition the speaker acknowledges would defeat
     the claim (often introduced by "unless", "except if", "provided that", "as long as").
     Extract verbatim. Return null if none stated.
   - "warrant_hint": str | null — the explicit inference rule the speaker stated to
     connect premises to conclusion (often introduced by "because", "which means that",
     "this shows that", "the logic is"). Return null if purely implicit — do NOT invent
     a warrant that was not stated.

2. Add both fields to the claim dict assembled in `extract_claims_from_turn()`,
   defaulting to null when absent from the model response.

3. In `app.py`, update the claim card display in the Claims tab:
   - Show "Rebuttal condition" inline below premises if non-null, with a label like
     "⚠ Unless: [rebuttal_cond]"
   - Show "Warrant" if non-null with a label like "∴ Because: [warrant_hint]"
   - Both should appear in collapsed expanders to avoid cluttering the default view.

4. Update the fact-check tab: when a claim has an explicit `warrant_hint`, add it to
   the context sent to the fact-checker so it can assess whether the inference is valid,
   not just whether the conclusion is true.

**UI simplicity constraint (see Section 8):** Do not use the words "warrant" or
"rebuttal condition" anywhere in the UI. Use "Reasoning used" and "Acknowledged
exception" instead. Both fields must appear inside a collapsed expander labelled
"Reasoning details" — the claim card must be fully readable without opening it.

Read `extractor.py` and `app.py` before editing. All new fields must default gracefully
for claims loaded from older JSON files that lack them.
```

---

### Prompt 12 — Argument-level graph: unifying premises, attacks, and Dung semantics
*(implements I-13 from Phase E; requires Prompts 5, 6, 8, and 9 to be complete)*

```
We are working on SayWhat, a Streamlit debate fact-checker app.

This prompt completes the full argument-level architecture described in the
SCIENTIFIC_IMPROVEMENT_PLAN.md. Previous prompts added:
- Premises as sub-nodes in the graph (Prompt 9)
- "undercuts" as a relationship type (Prompt 5)
- Dung survivability labels on nodes (Prompt 6)

The remaining gap: undercutters should visually target the inference (the edge they
attack), not the claim node. Pyvis does not natively support edge-to-edge connections,
so we use a proxy: for each "undercuts" response, insert a small invisible intermediate
node on the attacked edge and point the undercutter arrow at it.

Update `truth_checker/visualizer.py` — specifically `build_graph_html()`:

1. For each edge in `responses` with relationship "undercuts":
   a. Identify the edge from `from_claim_id` to `responds_to_claim_id` (the attacked edge).
   b. Create a small proxy node: ID = f"proxy_{resp['id']}", shape = "diamond",
      size = 6, color = "#e377c2" (undercutter pink), label = "", hidden = False,
      title = "Inference point (undercut here)".
   c. Add an invisible edge from `from_claim_id` to the proxy node (same color as the
      original attacked edge, opacity low, no arrow).
   d. Add the visible undercutter edge from the undercutter claim to the proxy node,
      styled as the undercutter edge color with arrow "to".
   This creates the visual effect of an arrow targeting the middle of another edge.

2. Add a toggle in `app.py` in the argument map section:
   "Show premises in graph" (checkbox, default on).
   When unchecked, suppress all premise sub-nodes and their support edges from the
   graph — showing only the claim-level graph with attack/support/undercut edges.
   Pass this flag into `build_graph_html()` as `show_premises: bool = True`.

3. Update the graph legend to clearly explain all three visual layers:
   - Circles: claims (colored by speaker)
   - Squares: premises (lighter, smaller)
   - Diamonds: inference points (where undercutters attack)
   - Solid arrows: attacks (refutes / undercuts / weakens)
   - Dashed arrows: intra-argument support (premise → claim)

4. In `app.py`, below the argument map, add a summary sentence drawn from the Dung
   survivability data: "After all attacks, N claims remain grounded (skeptically
   accepted), M are contested, and K are unattacked."

Read `visualizer.py` and `app.py` fully before editing. Test with empty responses,
with only support edges, and with a mix of all relationship types.
```

---

## 10. Implementation Progress

*Last updated: 2026-05-30. Records what was actually built vs. what was planned,
deviations, and known issues to fix before the next prompt.*

---

### P1 — Verdict labels + wicked-problem disclaimer
**Status:** ✅ Complete
**Files changed:** `app.py`

**What was done:**
- Renamed 4 verdict display labels: True→Supported, False→Unsupported,
  Misleading→Contested, Unverifiable→Beyond scope. Also renamed
  Subjective→Beyond scope (same treatment — not in the original plan but
  logically consistent). Partly True→Partially supported.
- Stored verdict strings (e.g. `"true"`, `"false"`) are untouched; only display
  labels changed. A single `_VSTYLE` dict drives all rendering so no logic duplication.
- Added `factcheck_disclaimer` LABELS key (bilingual) and `st.info()` injection
  above verdict expanders, rendered only when verdicts exist.

**Deviations from plan:** `verdict_subjective` was also renamed to "Beyond scope"
(not listed in P1's renames but correct given its meaning). `verdict_contested`
(the stored key for the genuinely contested verdict) was already "Contested" and
left as-is; `verdict_misleading` now also maps to "Contested" — two stored keys,
one display label, same orange colour.

---

### P2 — Pragma-dialectical fallacy taxonomy
**Status:** ⚠ Partially complete
**Files changed:** `truth_checker/rhetorician.py`, `app.py` (LABELS only)

**What was done:**
- Rewrote `_SYSTEM` in `rhetorician.py` around van Eemeren's 10 rules (Rules 1, 2,
  3, 4, 7, 10). Added `violated_rule: int|null` to the JSON schema returned by the
  model. Added `_RULE_NAMES` module-level dict (documentation reference).
- Added `rhetoric_rule_label` and `rhetoric_rule_names` to LABELS in `app.py`.

**Known gap — display not wired up:** The Rhetoric tab in `app.py` still renders
fallacies using only `label` and `quote`. The `violated_rule` field is now present
in the data but is never displayed. The edit to the fallacy rendering loop was
started but the session ended before it was applied.

**Fix needed before P10:** In the Rhetoric tab, for each fallacy with
`violated_rule` set, append `"(Rule N — Name)"` after the fallacy label using
`LABELS["rhetoric_rule_names"][lang].get(f.get("violated_rule"))`.

Also: `_RULE_NAMES` in `rhetorician.py` is currently unused code — it can either
be removed or used to replace the hardcoded rule-name strings inside `_SYSTEM`.

---

### P3 — Qualifier field + spoken-debate calibration
**Status:** ✅ Complete
**Files changed:** `truth_checker/extractor.py`

**What was done:**
- Extended `_SYSTEM` prompt with 4 new "Do NOT extract" bullet points for
  spoken-debate-specific phenomena: oral filler markers, metalinguistic commentary,
  embedded opponent quotation, and performative speech acts.
- Added `"qualifier"` to the JSON schema with four levels (`definite` / `probable` /
  `possible` / `speculative`) and linguistic examples for each.
- Added `_qualifier` extraction in `extract_claims_from_turn()` with whitelist
  validation (invalid values fall back to `"probable"`).
- `"qualifier"` added to every claim dict. Defaults gracefully when absent from
  loaded JSON files via `.get("qualifier", "probable")`.

**Deviations from plan:** None. The qualifier is stored in the claim but not yet
surfaced in the UI (no badge or filter in the Claims tab). That display work was
left for a future pass — it is a small addition to the claims table.

---

### P4 — Stance detection + debate motion input
**Status:** ✅ Complete
**Files changed:** `truth_checker/extractor.py`, `app.py`

**What was done:**
- Added `motion: str = ""` parameter to `extract_claims_from_turn()`. When non-empty,
  prepended as `"Debate motion: {motion}\n"` to the user message.
- Extended `_SYSTEM` with `"stance"` field definition (pro/con/neutral). Model
  returns "neutral" for all claims when no motion is provided.
- Added `_stance` extraction with whitelist validation (defaults to `"neutral"`).
- In `app.py`: `st.text_input` for the motion stored in `st.session_state["motion"]`,
  placed inside the Analysis tab before the Run Analysis button.
- Motion passed to all `extract_claims_from_turn()` calls via `_motion`.
- Stance breakdown (3 metrics: For / Against / Neutral) in the Speaker Report,
  rendered only when a motion was set.

**Deviations from plan:** Stance is stored in the claim dict and shown in the Speaker
Report, but not yet shown in the Claims tab table or as a badge on individual claims.
A future pass could add a stance colour indicator to the claim table rows.

---

### P5 — `undercuts` relationship type
**Status:** ✅ Complete
**Files changed:** `truth_checker/responder.py`, `truth_checker/visualizer.py`,
`app.py`

**What was done:**
- Added `"undercuts"` to `_VALID_RELATIONSHIPS` in `responder.py`.
- Added disambiguation sentence to both `_SINGLE_SYSTEM` and `_BATCH_SYSTEM`:
  "use `refutes` when the response denies the conclusion itself; use `undercuts`
  when the response argues that the reasoning does not support the conclusion."
- Added `"undercuts": "#e377c2"` (muted pink) to `_EDGE_COLORS` in `visualizer.py`
  with inline comments distinguishing it from `"refutes"` (red).
- Added `"legend_undercuts"` LABELS key ("challenges the reasoning" / "cuestiona el
  razonamiento") in `app.py`. Updated the inline `edge_legend` string to include the
  pink swatch. Also renamed `refutes` display to "directly contradicts" for plain language.

**Deviations from plan:** The plan mentioned updating a legend inside `build_graph_html`
— there is no internal legend; the legend lives in `app.py`. Handled there instead.

---

### P6 — Dung grounded extension
**Status:** ✅ Complete
**Files changed:** `truth_checker/dung.py` (new), `truth_checker/visualizer.py`,
`app.py`

**What was done:**
- Created `truth_checker/dung.py` with `compute_grounded_extension()` implementing
  the iterative fixpoint of F_AF from the empty set. Attack relationships: `refutes`,
  `undercuts`, `weakens`. Returns `claim_id → "grounded"|"contested"|"unattacked"`.
  Handles empty inputs gracefully.
- Updated `build_graph_html()` in `visualizer.py` to accept optional
  `survivability: dict[str, str] | None`. Added `_SURV_BORDER` dict mapping status
  to `(border_color, border_width)`. When provided, nodes get a coloured border
  (green/thick = grounded, orange/medium = contested, default = unattacked).
- In `app.py`: import added; `compute_grounded_extension()` called immediately after
  `detect_responses()` succeeds, stored in `st.session_state["survivability"]`.
- Survivability passed to `build_graph_html()`.
- Argument map legend extended with a border-colour key row.
- Summary caption added below the map: "N survived · M challenged · K unchallenged."
- `surv_icon()` helper prepends a coloured dot (●/○) to each claim in the HTML table.
- Verdict expanders: survivability label appended inline after the verdict badge.
- Speaker Report: 3-column metric block per speaker (grounded/contested/unattacked),
  shown only when detect_responses has run.

**Known gap:** When responses are *loaded from a saved JSON file* (rather than run
fresh), `survivability` is not recomputed. The argument map will render without
border colours and the survivability metrics will be absent. Fix: call
`compute_grounded_extension()` when responses are loaded from a file, in the same
block that sets `st.session_state["responses"]`.

---

### P7 — Restatement detection and deduplication
**Status:** ✅ Complete
**Files changed:** `truth_checker/deduplicator.py` (new), `app.py`

**What was done:**
- Created `truth_checker/deduplicator.py` with `mark_restatements()`. Groups eligible
  claims by `(speaker, thread_id)`, sorts by `turn_index`, generates same-speaker /
  same-thread pairs within `_MAX_TURN_GAP=8` turns. Skips claims already marked as
  restatements as the "earlier" anchor. Batches up to 10 pairs per Claude Haiku call
  (returns JSON boolean array). Marks `later["restatement_of"] = earlier["id"]` on
  matches. Batch failures are logged and skipped silently.
- In `app.py`: import added; `mark_restatements()` called after threading (progress
  bar 93%), before storing analysis in session state — so the `restatement_of` field
  is persisted in the analysis JSON and preserved through save/load cycles.
- Fact-check filter: added `and not c.get("restatement_of")` to exclude restatements.
- Claims tab (HTML path): restatement rows shown italic+grey with "repeated" badge
  and a note "Repeated claim — same as: [60-char preview]".
- Claims tab (dataframe path): `_claim_cell_plain()` appends `[repeated: ...]` suffix.
- Speaker Report: "N repeated claim(s) detected and skipped in fact-check" caption
  per speaker, shown only when `_n_restat > 0`.

**Known gap:** The deduplicator adds API calls to the Run Analysis step, adding a
small but non-zero cost (~$0.005 for a 45-min debate with Haiku). The progress bar
jumps from 85% (threading) to 93% (deduplicating) to 100%. If deduplication is slow
(many candidate pairs), the 93% step may stall visually. A future pass could add
a per-batch progress callback.

---

### P8 — Premise extraction
**Status:** ✅ Complete
**Files changed:** `truth_checker/extractor.py`, `app.py`

**What was done:**
- Extended `_SYSTEM` in `extractor.py` to include `"premises": [str]` in the JSON
  schema. Added description: 1–3 most explicit supporting reasons/data the speaker
  cited in the same turn; distinguishes premises from restatements; returns `[]` if
  none stated.
- Added `"premises"` to the claim dict in `extract_claims_from_turn()`. Validated as
  a list; non-string entries filtered out; defaults to `[]` for backward compatibility.
- Added `"evidence_cited"` LABELS key (English/Spanish).
- In `app.py` verdict expanders: `st.expander(L("evidence_cited"))` appears after
  the bold claim text if `c.get("premises", [])` is non-empty. Each premise shown
  as a bullet point. Collapsed by default.
- Analysis JSON download automatically includes premises (they live on the claim dict).
  The `dl_verdicts` download exports only verdicts, which is correct — premises are
  part of the analysis, not the fact-check result set.

**Deviations from plan:** None material. The plan mentioned "Update the JSON download
format for claims (the 'fact_check' download)" but on inspection, the fact-check
download only holds verdict dicts, not claim dicts. Premises are correctly preserved
in the analysis download. No separate migration needed.

---

### P9 — Premises in the argument map
**Status:** ✅ Complete (later extended in P12)
**Files changed:** `truth_checker/visualizer.py`, `app.py`

**What was done:**
- Added `_hex_to_rgba()` helper to `visualizer.py` (converts hex color to rgba with
  alpha) for tinted premise edge colors.
- Inside the claim loop in `build_graph_html()`: for each non-empty, non-whitespace
  premise in `claim.get("premises", [])`, adds a `"box"` sub-node (grey `#cccccc`,
  size 10) and a dashed directed edge from sub-node to parent claim. Edge color uses
  the speaker's color at 60% opacity. Tooltip: `"supports: <claim[:60]>"`.
- In `app.py`: added `"show_premises"`, `"legend_premise"` LABELS. Added
  `show_premises_cb = st.checkbox(..., value=False)` in the Argument Map subtab.
  When unchecked, claims were passed with `"premises": []` stripped in-place — a
  workaround to avoid changing the function signature per the P9 constraint.

**Deviations from plan:** The prompt said "Do not change the function signature."
The in-app stripping workaround was the compliance mechanism. This was superseded in
P12 which added `show_premises: bool = True` as a proper parameter and changed the
default to ON. The stripping workaround no longer exists.

**Legend:** Conditional `□` box + dashed-arrow entry added to the map legend, shown
only when the premises toggle is on.

---

### P10 — Dialectical stage labeling
**Status:** ✅ Complete
**Files changed:** `truth_checker/stage_labeler.py` (new), `app.py`

**What was done:**
- Created `truth_checker/stage_labeler.py` with `label_dialectical_stages(turns, api_key)`.
  Batches 10 turns per Claude Haiku call. System prompt explains all four stages
  (confrontation / opening / argumentation / concluding) with signal phrases and
  examples. Mutates turns in place with `"dialectical_stage"` key. On batch failure,
  defaults silently to `"argumentation"`. Returns the same list.
- In `app.py`: import added. 7 new LABELS (`stage_labeling`, `stage_timeline`,
  `stage_confrontation`, `stage_opening`, `stage_argumentation`, `stage_concluding`,
  `stage_heading_report`).
- **Rhetoric button handler**: stage labeling runs immediately after rhetoric
  completes, on the same `turns_rh`. Progress bar updated to "Detecting dialectical
  stages…" during this step. Result stored as `st.session_state["stages"]` — a list
  of `{turn_index, speaker, start_ms, dialectical_stage}` dicts.
- **Rhetoric download button**: moved to 3-column layout; now exports
  `{"rhetoric": [...], "stages": [...]}` together. Load handler also restores
  `stages` from the file when present.
- **Rhetoric subtab**: when `stages` exist, shows `st.subheader(L("stage_timeline"))`
  followed by a distribution bar chart (turns per stage) and a compact horizontal
  sequence of colored turn boxes (confrontation=red, opening=blue,
  argumentation=green, concluding=purple). A divider separates the timeline from
  per-speaker rhetoric expanders. Timeline shows even without rhetoric (e.g. if
  rhetoric was cleared from session).
- **Speaker Report**: 4-metric stage breakdown per speaker (one metric per stage),
  shown only when `st.session_state["stages"]` is non-empty.

**Deviations from plan:** The plan described a dedicated "Run Stage Analysis" button
or a combined run with rhetoric. Chosen approach: stage labeling runs automatically as
a post-step of the rhetoric button (one click does both). This is simpler UX and costs
< $0.01 extra per typical debate with Haiku.

---

### P11 — Full Toulmin decomposition
**Status:** ✅ Complete
**Files changed:** `truth_checker/extractor.py`, `truth_checker/verifier.py`, `app.py`

**What was done:**
- Extended extractor `_SYSTEM` JSON schema to include `"rebuttal_cond": str|null` and
  `"warrant_hint": str|null`. Added field descriptions:
  - `rebuttal_cond`: condition signalled by "unless / except if / provided that /
    as long as". Return null if none stated.
  - `warrant_hint`: explicit inference rule signalled by "because / which means that /
    this shows that". Return null if purely implicit — do NOT invent.
- Both fields added to claim dict: validated as non-empty strings or stored as `None`.
  Old JSON files without these keys default to `None` via `.get()`.
- **verifier.py**: `verify_claim()` now prepends `"Stated inference: {warrant_hint}\n"`
  to the user message when `warrant_hint` is present. This tells the fact-checker to
  assess whether the stated reasoning is valid, not just the conclusion.
- **app.py**: 3 new LABELS (`reasoning_details`, `reasoning_used` with ∴ prefix,
  `acknowledged_exception` with ⚠ prefix). In verdict expanders: a collapsed
  `st.expander(L("reasoning_details"))` appears after the premises expander when at
  least one of `warrant_hint` / `rebuttal_cond` is non-null. Shows `∴ Reasoning used`
  and `⚠ Acknowledged exception` lines inside. No academic terminology in the UI.

**Deviations from plan:** Plan step 3 said "Show in collapsed expanders to avoid
cluttering the default view." Implemented as a single combined "Reasoning details"
expander containing both fields rather than two separate expanders — cleaner than
two collapsed expanders side by side.

---

### P12 — Argument-level graph: proxy diamonds, parameter cleanup, legend, summary
**Status:** ✅ Complete
**Files changed:** `truth_checker/visualizer.py`, `app.py`

**What was done:**
- **Function signature extended**: `build_graph_html()` now accepts
  `show_premises: bool = True` and `show_reasoning_targets: bool = False`. All
  existing callers are backward-compatible (both have defaults).
- **Premise gate**: moved inside `if show_premises:` in the function, replacing the
  P9 workaround of stripping premises in app.py before the call.
- **Proxy diamond nodes for undercuts** (when `show_reasoning_targets=True`):
  - For each `"undercuts"` response, creates proxy node ID `f"proxy_{from_id}_{to_id}"`
    (shape=diamond, size=6, color=#e377c2, label="").
  - Ghost edge from target claim to proxy (rgba #e377c2 at 12% opacity, no arrowhead)
    pulls the proxy toward the target claim in the physics simulation.
  - Visible undercut edge from undercutter to proxy (pink, `arrows="to"`, tooltip
    "challenges reasoning: …"). Original target→undercutter edge is NOT added when
    in proxy mode.
  - With `show_reasoning_targets=False` (default): undercut edges render as the
    existing solid pink arrows — no visual change.
- **app.py toggles**: two columns, `show_premises` defaults True, `show_reasoning_targets`
  defaults False. Passes both to `build_graph_html()`. Old stripping workaround removed.
- **Legend update**: conditional sections added. When premises on: grey □ box + dashed
  arrow entry. When reasoning targets on: pink ◆ inference point entry.
- **Survivability summary**: `surv_map_summary` label updated to a full sentence with
  bold counts ("After all counterarguments: **N** claims survived all attacks, **M**
  are challenged, and **K** had none."). Display changed from `st.caption` to
  `st.markdown` so bold rendering applies.
- New LABELS: `show_reasoning_targets`, `legend_inference_pt`, `legend_dashed`.

**Deviations from plan:**
- The prompt described proxy ID as `f"proxy_{resp['id']}"`. Since response dicts have
  no `id` field, used `f"proxy_{from_id}_{to_id}"` (target + undercutter claim IDs),
  which is unique per (T, U) pair.
- The "invisible edge from `from_claim_id` to proxy" was interpreted as a ghost anchor
  edge from the *target* claim to the proxy, not from the undercutter. This produces
  the correct visual: the proxy hovers near the target's inference point.
- The `surv_map_summary` was already present as `st.caption` from P6. This prompt
  upgraded it to a richer `st.markdown` sentence and updated the label text.

---

### Summary: claim dict schema after P1–P12

Every claim dict now carries these fields after a full Run Analysis:

```python
{
    "id":             "claim_5_0",
    "speaker":        "A",
    "turn_index":     5,
    "start_ms":       120000,
    "end_ms":         125000,
    "text":           "Real wages have fallen…",
    "start_hint":     "Real wages have",
    "qualifier":      "definite",                     # P3
    "stance":         "con",                          # P4
    "premises":       ["INE data shows 12% drop…"],   # P8
    "rebuttal_cond":  "unless productivity also rose", # P11 (str or None)
    "warrant_hint":   "because real = nominal − CPI", # P11 (str or None)
    "thread_id":      "wages_2024",                   # threader
    "thread_topic":   "Real wages",                   # threader
    "claim_type":     "statistical",                  # classifier
    "checkable":      True,                           # classifier
    "restatement_of": None,                           # P7 (str or None)
}
```

Session-state-only data (not on the claim dict):
- `st.session_state["survivability"]`: `dict[claim_id → "grounded"|"contested"|"unattacked"]`
  derived from `compute_grounded_extension()`. Recomputed whenever responses change.
- `st.session_state["stages"]`: `list[{turn_index, speaker, start_ms, dialectical_stage}]`
  produced by `label_dialectical_stages()`. Stored alongside rhetoric results.

---

### Open issues after P1–P12

The following are known gaps that have NOT been addressed by any prompt. They are all
UI-only additions; the underlying data is already collected.

1. **P2 display gap** (open since P2): `violated_rule` is populated in rhetoric data
   but the Rhetoric tab still shows only `label` and `quote` for each fallacy. Fix:
   append `"(Rule N — Name)"` after the fallacy label using
   `LABELS["rhetoric_rule_names"][lang].get(f.get("violated_rule"))`.

2. **Survivability on JSON load** (open since P6): when responses are loaded from a
   saved file, `compute_grounded_extension()` is not called, so survivability borders
   and metrics are absent. Fix: call it in the responses-load block alongside
   `st.session_state["responses"] = _d["responses"]`.

3. **Qualifier not displayed per claim** (open since P3): `qualifier` is stored on
   every claim but never shown in the Claims tab or verdict expanders. A small badge
   ("stated as fact" / "probably" / etc.) next to the claim text would complete the
   Toulmin qualifier work.

4. **Stance not shown per claim** (open since P4): stance is aggregated in the Speaker
   Report but not indicated on individual claim rows. A pro/con/neutral colour dot or
   tag on each row would complete this.

These four items are self-contained UI additions that can be addressed in a single
cleanup session without touching the backend pipeline.
