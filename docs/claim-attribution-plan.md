# Claim Attribution & Posture — Analysis and Solution Plan

> Status: planning  
> Triggered by: claim "La dieta que seguían los reyes era la ideal" attributed to Gonzalo at 00:00, when Gonzalo was actually challenging a third-party Instagram post.

---

## 1. The Problem in Two Parts

### Part A — Single-turn attribution errors

The extractor processes one speaker turn in isolation and returns extracted claims, each attributed to the speaker of that turn. But a speaker can voice a proposition in at least four distinct ways:

| Posture | Description | Example |
|---|---|---|
| **asserting** | Speaker states this as their own position | *"Los estudios de Keys han sido replicados"* |
| **challenging** | Speaker voices a claim in order to challenge/refute it | *"¿Eso significa que la dieta de los reyes era la ideal?"* |
| **attributing** | Speaker reports a claim made by someone else | *"Tu post decía que los reyes comían carne"* |
| **questioning** | Speaker asks whether something is true without committing | *"¿No es un poco contradictorio que...?"* |

Currently the app only models one posture — **asserting** — and treats every extracted claim as an assertion by the turn's speaker.

**Concrete failures found in the Debate Alimentario cleaned analysis:**

| Claim ID | Text | Speaker | start_hint | Actual posture |
|---|---|---|---|---|
| claim_0_1 | La dieta que seguían los reyes era la ideal | A (Gonzalo) | ¿Eso significa que | challenging — quoting Azarian's Instagram post |
| claim_6_1 | Los resultados de Kiss se han replicado tan contundentemente | A | ¿Cómo puede ser | questioning — asking how this is possible |
| claim_20_4 | La recomendación de cereales integrales es contradictoria | A | ¿no es un poco | questioning — rhetorical challenge |
| claim_83_1 | Un ser humano puede ser controlado bajo 4 premisas | B | ¿Cómo nos puede, cómo | attributing — describing "the Matrix" framework |
| claim_94_3 | Existe el peligro de meter todo en el mismo saco | A | ¿No crees que hay | questioning — asking B to reflect |
| claim_105_2 | Los que tienen más pasta pueden financiar los estudios | B | ¿Quién puede financiar eso? | questioning |

**Downstream damage:** The scorer currently counts ALL `checkable` claims toward the speaker's reliability score. When a speaker challenges a false claim and the fact-checker correctly marks it false, **the challenger's reliability score drops** for a claim they were actively disproving. This is the most serious consequence.

---

### Part B — Cross-turn attribution: the affirmation problem

The attribution of a claim can change depending on what the next speaker says. Consider:

**Case 1 — Challenge only (B does not respond directly)**
```
A: ¿Eso significa que la dieta de los reyes era la ideal?
B: [continues with a different point]
```
→ The claim should not be attributed to anyone as an assertion.

**Case 2 — Challenge affirmed**
```
A: ¿Eso significa que la dieta de los reyes era la ideal?
B: Sí, exactamente, eso es lo que creo.
```
→ B is now the asserter. The claim should be attributed to B and count against B's reliability score.

**Case 3 — Challenge denied**
```
A: ¿Eso significa que la dieta de los reyes era la ideal?
B: No, no quiero decir eso exactamente.
```
→ Neither speaker asserts it. A's challenge is vindicated. The claim should not appear in either speaker's reliability score.

**Case 4 — Implicit affirmation (B argues as if the claim is true)**
```
A: ¿Eso significa que la dieta de los reyes era la ideal?
B: Sí, por eso yo quiero comer como un rey...
```
→ B accepts the premise and builds on it. B is the asserter.

**Case 5 — Third-party attribution with cross-turn adoption**
```
A: Tu post de Instagram decía que los reyes comían mejor.
B: Sí, eso es lo que defiendo.
```
→ B adopts the attributed claim and becomes the asserter.

This creates a **cross-turn attribution problem**: the extractor processes one turn at a time, but the "owner" of a claim can only be determined by looking at the adjacent response. The claim's posture is not fully knowable from the turn it was voiced in.

---

## 2. Current Architecture and Where It Breaks

```
utterances
    → segment_turns()
    → extract_claims_from_turn()   ← posture lost here
    → classify_claim()             ← no posture awareness
    → group_into_threads()
    → detect_responses()           ← cross-turn, but relationships only
    → compute_speaker_scores()     ← counts all checkable claims equally
```

### The extractor

Processes one turn at a time. Has rules against extracting attributed/rhetorical speech:
- *"Questions directed at other speakers"*
- *"Clear jokes, hyperbole, or rhetorical questions"*
- *"Embedded quotation of the opponent's view"*

But these rules fail because:
1. **"Opponent's view" is too narrow** — covers only the other debater's direct in-debate statements, not third-party sources (Instagram posts, studies, other people)
2. **Question-to-assertion transformation** — the model silently converts "¿Does X mean Y?" into "Y" as an assertion by the questioner
3. **No schema slot for posture** — even when the model gets it right, there is nowhere to record it

### The responder

Already does cross-turn analysis and identifies `supports`, `refutes`, `undercuts`, etc. relationships between claims. This is the **right module to also detect affirmations** (B's `supports` response to A's `questioning` claim implies B is asserting the claim). However, the current relationship types do not include "affirms" and no downstream logic uses responses to re-attribute claims.

### The scorer

```python
if claim.get("checkable"):
    s["checkable_claims"] += 1
```

No posture filter. Every checkable claim counts regardless of whether the speaker was asserting, challenging, or merely attributing.

---

## 3. Solution Plan

### Phase 1 — `posture` and `attributed_to` fields in the extractor *(addresses Part A)*

Add two new fields to the extracted claim JSON schema:

```json
{
  "posture": "asserting | challenging | attributing | questioning",
  "attributed_to": "string | null"
}
```

**`posture` definitions for the extraction prompt:**
- `"asserting"` — speaker states this as their own belief or factual position
- `"challenging"` — speaker voices this claim in order to question or refute it; often introduced with ¿...? or "¿No es X?"
- `"attributing"` — speaker explicitly reports this as someone else's claim ("B dijo que...", "el post decía que...", "según X...")
- `"questioning"` — speaker genuinely asks whether the claim is true without committing to it

**`attributed_to`** (non-null when posture ≠ "asserting"):
- Name of the other speaker, institution, or source being quoted/challenged
- E.g. `"Azarian's Instagram post"`, `"Kiss"`, `"la industria azucarera"`

**Key prompt strengthening needed:**
- Extend "Do NOT transform questions into assertions" — when the sentence is interrogative, either skip it or mark posture as "questioning"
- Extend attribution to cover third-party sources, not just the debating opponent
- Add Spanish-specific challenge patterns: "¿Eso significa que...?", "¿No te parece...?", "¿Cómo puede ser que...?"

**Impact on classifier:**
- The classifier should still mark non-asserting claims as `checkable` if the underlying content is factually verifiable
- Add a new field `check_as_attributed` (bool) — when True, fact-checking the claim yields a verdict about the *attributed source*, not the speaker

**Impact on scorer:**
```python
# Only asserting claims count toward reliability
if claim.get("checkable") and claim.get("posture", "asserting") == "asserting":
    s["checkable_claims"] += 1
```

### Phase 2 — Cross-turn affirmation resolution in the responder *(addresses Part B)*

After `detect_responses()` builds response edges, add an **attribution resolver** pass that:

1. Finds all claims with `posture ∈ {"challenging", "questioning"}` that have a response edge of type `"supports"` from another speaker's claim
2. When found: creates a **synthesized asserting claim** attributed to the affirming speaker (B), with:
   - Same `text` as the original questioned claim
   - `posture: "asserting"`
   - `speaker: B`
   - `affirmed_from: original_claim_id` (link back to A's questioning claim)
3. The original (A's questioning claim) keeps its posture but gains an `affirmed_by: new_claim_id` field

This preserves both the structure ("A challenged X, B affirmed X") and the correct attribution ("X is B's assertion").

**Affirmation detection rules:**
- Explicit: B's turn contains "sí", "exactamente", "eso es lo que defiendo", "por eso creo que..."
- Implicit: B's claim `supports` A's questioning claim AND B is a different speaker than A
- **Not an affirmation:** B's claim `refutes` or `undercuts` A's questioning claim (Case 3 above)

**New relationship type**: Consider adding `"affirms"` to the responder's vocabulary alongside `refutes`, `supports`, etc. — specifically for the case where one speaker adopts/accepts a proposition voiced by another.

### Phase 3 — Downstream updates

**Scorer:**
- Phase 1 already handles the primary fix (exclude non-asserting from reliability score)
- With Phase 2: synthesized affirming claims from B count toward B's score correctly

**Fact-checker:**
- Non-asserting claims can still be fact-checked (the content is still checkable)
- The verdict display changes: "Gonzalo's position: ..." vs "Gonzalo challenges [Azarian's claim]: ..."
- Synthesized affirming claims (from Phase 2) are fact-checked and attributed to B

**Argument map:**
- `challenging` claims appear as attack edges toward the source (`attributed_to`)
- `attributing` claims appear as "reports" edges
- `affirmed_from` links connect B's synthesized assertion back to A's challenge

**Claim card display:**
- `asserting` → current display
- `challenging` → "↩ Gonzalo challenges [Azarian's Instagram post]: ..."
- `attributing` → "Gonzalo reports [source]: ..."
- `questioning` → "Gonzalo questions: ..."
- Synthesized affirming claim → "Azarian (affirmed from Gonzalo's challenge): ..."

---

## 4. Implementation Roadmap

| Phase | Scope | API calls | Risk |
|---|---|---|---|
| **1a** | Add `posture` + `attributed_to` to extractor schema | Haiku, same count | Low — additive schema change |
| **1b** | Update scorer to filter by posture | None | Low |
| **1c** | Update classifier to set `check_as_attributed` | Haiku, same count | Low |
| **1d** | Update claim card display to show posture | None | Low |
| **2a** | Add `affirms` relationship type to responder | Haiku, slight increase | Medium |
| **2b** | Attribution resolver pass (synthesize affirming claims) | None (logic only) | Medium — new claim creation |
| **2c** | Update argument map edges for posture | None | Medium |
| **3** | Update fact-checker display + verdict attribution | None | Low |

Phases 1a–1d can be implemented independently. Phase 2 depends on Phase 1.

---

## 5. Open Questions

The following questions need answers before implementation begins.

### Questions from Part A (single-turn)

**Q1 — Scope of attribution sources:**  
Should `attributed_to` cover (a) only the other debater, (b) third-party sources (social media posts, studies, institutions), or (c) all sources? The Gonzalo/Instagram case is type (b).

**Q2 — Fact-checking non-asserting claims:**  
Should the fact-checker still verify `challenging` and `attributing` claims? Arguments for: the content is factually checkable and showing "this claim Gonzalo challenges is indeed false" is useful. Arguments against: it complicates the display.

**Q3 — Display preference for non-asserting claims:**  
Should non-asserting claims:
- (a) Be hidden from the main claim list, shown only in the argument map  
- (b) Appear inline with a visual posture indicator (e.g. "↩ challenges")  
- (c) Appear in a separate "Challenges & Attributions" section

**Q4 — Scoring of challenged-but-correct challenges:**  
If Gonzalo challenges a claim that turns out to be false, should he get a "correct challenge" credit in the score? This would require a new sub-score: "accuracy of challenges made".

### Questions from Part B (cross-turn)

**Q5 — Scope of cross-turn resolution for v1:**  
Is Phase 2 (synthesizing affirming claims) needed for v1, or is Phase 1 (correct posture + score filtering) sufficient for now?

**Q6 — What counts as an affirmation?**  
Only explicit verbal affirmations ("Sí, exactamente") or also implicit ones where B argues as if the questioned claim is true?

**Q7 — Fate of A's questioning claim after B affirms:**  
When B affirms A's questioned claim:
- Does A's original claim disappear from A's claim list?  
- Or does it remain as a "challenge" with a link to B's assertion?  
- Is A credited for correctly identifying something B believes?

**Q8 — Synthesized claims and the pipeline:**  
When the attribution resolver creates a new claim (B's synthesized assertion), should it go through the classifier/threader again, or inherit the attributes from A's original claim?

**Q9 — The "steelman" edge case:**  
Sometimes Speaker A presents the strongest version of B's position before refuting it ("One could argue that X — but this is wrong because Y"). Should X be extracted with posture `"challenging"` and attributed to B, even though B never said X explicitly?

---

## 6. Related Files

| File | Relevance |
|---|---|
| `truth_checker/extractor.py` | Phase 1 — add posture schema |
| `truth_checker/classifier.py` | Phase 1 — add `check_as_attributed` field |
| `truth_checker/responder.py` | Phase 2 — add `affirms` relationship + resolver |
| `truth_checker/scorer.py` | Phase 1 — filter by posture |
| `app.py` | Phase 1/2 — invoke resolver, pass posture downstream |
| `docs/how-it-works.md` | Phase 3 — update pipeline description |
| `docs/claim-types-reference.md` | Phase 3 — add posture definitions |
