# Claim Attribution & Posture — Analysis and Solution Plan

> Status: ready for implementation  
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

**Case 6 — Partial affirmation / weakening**
```
A: ¿Eso significa que la dieta de los reyes era la ideal?
B: No exactamente, pero sí creo que había sabiduría en la dieta real...
```
→ B qualifies/weakens — this is NOT an affirmation. Captured by the responder as `weakens` or `reframes`, not `affirms`.

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

Already does cross-turn analysis and identifies `supports`, `refutes`, `undercuts`, etc. relationships between claims. This is the **right module to also detect affirmations**. A new `"affirms"` relationship type will be added specifically for when one speaker adopts a proposition voiced by another. This is distinct from `"supports"` (which means adding evidence to a claim) — `"affirms"` means "I accept this proposition as my own."

### The scorer

```python
if claim.get("checkable"):
    s["checkable_claims"] += 1
```

No posture filter. Every checkable claim counts regardless of whether the speaker was asserting, challenging, or merely attributing.

---

## 3. All Decisions

| # | Question | Decision |
|---|---|---|
| Q1 | Scope of `attributed_to` | All sources: other debater, third parties, institutions, social media posts |
| Q2 | Fact-check non-asserting claims? | Yes — content is still factually verifiable |
| Q2a | Display of fact-checked challenges | (ii) Verdict shown on claim card; posture badge provides the attribution context |
| Q3 | Display of non-asserting claims | (b) Inline with posture badge |
| Q4a | Scoring of challenged claims | Exclude all non-asserting claims from reliability score for v1; no challenge credit, no penalty |
| Q5 | Phase 2 scope | Phase 2 (cross-turn resolver) is in scope for v1 |
| Q6 | What counts as affirmation | Both explicit ("Sí, exactamente") and implicit (B builds on the premise as true) |
| Q6a | Affirmation detection mechanism | Add dedicated `"affirms"` relationship type to the responder vocabulary |
| Q6b | Partial affirmation | Not an affirmation — captured by `weakens` or `reframes` |
| Q7 | Fate of A's questioning claim after affirmation | Remains as `challenging` with `affirmed_by` link to B's synthesized assertion; A gets no credit |
| Q8 | Synthesized claims and the pipeline | Inherit all classifier fields from A's original; override `speaker`, `posture`, `start_ms`, `affirmed_from` only; no re-classification |
| Q8a | Premises/warrant on synthesized claim | `start_hint`, `premises`, `warrant_hint` are null/empty on the synthesized claim |
| Q9 | Steelman edge case | Yes — A steelmanning B's position: extract with `posture: "challenging"`, `attributed_to: "B (steelmanned position)"` |
| Q9a | Steelman true claim → B credit? | No — stays as A's characterization only; B only gets credit for claims B explicitly adopted |

---

## 4. Solution Plan

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
- `"challenging"` — speaker voices this claim in order to question or refute it (includes steelmanning: A presents B's strongest position before refuting it); often introduced with ¿...? patterns or "One could argue that..."
- `"attributing"` — speaker explicitly reports this as someone else's claim ("B dijo que...", "el post decía que...", "según X..."); any source counts (other debater, third parties, studies, social media)
- `"questioning"` — speaker genuinely asks whether the claim is true without committing to it

**`attributed_to`** (non-null when posture ≠ "asserting"):
- Name of the other speaker, institution, or source being quoted/challenged
- E.g. `"Azarian's Instagram post"`, `"Kiss"`, `"la industria azucarera"`, `"B (steelmanned position)"`

**Key prompt changes needed:**
- Do NOT transform questions into assertions — when the sentence is interrogative, mark posture as "questioning" or "challenging"
- Extend attribution to cover all sources, not just the debating opponent
- Spanish-specific challenge patterns: "¿Eso significa que...?", "¿No te parece...?", "¿Cómo puede ser que...?", "¿No es un poco contradictorio que...?"
- Steelman pattern: "podría decirse que", "si siguiésemos esa lógica", "one could argue that"

**Impact on classifier:**
- Add `check_as_attributed` (bool): True when posture ≠ "asserting". Signals to the fact-checker that the verdict should be displayed as applying to the attributed source, not the speaker.

**Impact on scorer:**
```python
# Only asserting claims count toward reliability
if claim.get("checkable") and claim.get("posture", "asserting") == "asserting":
    s["checkable_claims"] += 1
```

### Phase 2 — Cross-turn affirmation resolution *(addresses Part B)*

**Step 2a — Add `"affirms"` to the responder**

Add `"affirms"` as a dedicated relationship type in the responder. Definition: "B adopts/accepts the proposition that A voiced (regardless of whether A voiced it as a challenge, attribution, or question)."  
Distinct from `"supports"` (which means adding evidence or reasoning to an existing claim).

**Step 2b — Attribution resolver pass**

After `detect_responses()` builds edges, a new `resolve_attributions()` pass:

1. Finds all claims with `posture ∈ {"challenging", "questioning", "attributing"}` that have a response edge of type `"affirms"` from another speaker (B)
2. Creates a **synthesized asserting claim** for B:
   - `text`, `claim_type`, `checkable`, `evidence_quality`, `suggested_query`, `thread_id` — inherited from A's original claim
   - `speaker` = B
   - `posture` = `"asserting"`
   - `start_ms`, `end_ms`, `turn_index` = B's affirming turn values
   - `start_hint`, `premises`, `warrant_hint` = null/empty
   - `affirmed_from` = A's original claim ID
   - New `id` = `"claim_{B_turn_index}_synth_{A_claim_id}"`
3. A's original claim gains `affirmed_by` = synthesized claim ID

**Affirmation signal for the responder prompt:**
- Explicit: "sí", "exactamente", "eso es lo que defiendo", "correcto", "yes"
- Implicit: B's turn treats the questioned proposition as a given premise and builds on it
- **NOT affirmation:** B qualifies, weakens, or partially denies → use `weakens` or `reframes`

### Phase 3 — Downstream updates

**Scorer:**
Phase 1 handles this (filter by posture). Synthesized asserting claims from Phase 2 count toward B's score correctly since their posture is "asserting".

**Fact-checker display:**
- Non-asserting claims: verdict block reads *"This claim, attributed to [source], is [verdict]"* rather than *"[Speaker]'s claim is [verdict]"*
- The posture badge on the claim card (Phase 1d) provides the context — no separate treatment needed (Q2a = option ii)

**Argument map:**
- `challenging` claims: attack edge toward `attributed_to`
- `attributing` claims: "reports" edge
- `affirmed_from` links: dotted edge connecting synthesized claim back to original challenge

---

## 5. Implementation Roadmap

| Step | Scope | Files | Dependency |
|---|---|---|---|
| **1a** | Add `posture` + `attributed_to` to extractor schema and prompt | `extractor.py` | — |
| **1b** | Update scorer to filter by posture | `scorer.py` | 1a |
| **1c** | Add `check_as_attributed` to classifier | `classifier.py` | 1a |
| **1d** | Claim card display: posture badge + verdict attribution text | `app.py` | 1a, 1c |
| **2a** | Add `affirms` relationship type to responder | `responder.py` | 1a |
| **2b** | `resolve_attributions()` pass: synthesize affirming claims | new function, `app.py` pipeline | 2a |
| **2c** | Argument map: posture-aware edges | `visualizer.py`, `app.py` | 2b |

Steps 1a–1d are independent of Phase 2. Step 2b depends on 2a. Step 2c depends on 2b.

---

## 6. Implementation Prompts

Use these prompts sequentially. Each is self-contained. Read the referenced files before making changes.

---

### Prompt 1 — Add `posture` and `attributed_to` to the extractor

```
Read truth_checker/extractor.py in full.

Make the following changes:

1. Add two new fields to the JSON schema returned by extract_claims_from_turn():

   "posture": one of ["asserting", "challenging", "attributing", "questioning"]
   "attributed_to": string | null  (non-null when posture ≠ "asserting")

2. Update the system prompt (_SYSTEM) with these additions:

   a. In the "Do NOT extract" list, replace:
      "- Embedded quotation of the opponent's view introduced for rebuttal: 'you argue that X',
       'your position is that X', 'you claim that X' — extract only the speaker's own assertions,
       not their description of what the other side believes"
      
      With:
      "- Do NOT transform questions into assertions. If a sentence is interrogative (starts with
       ¿ or ends with ?), do not extract its content as an asserting claim. Mark it as
       'questioning' or 'challenging' instead.
      - Claims the speaker voices to challenge or refute: these include rhetorical questions like
       '¿Eso significa que X?', '¿No es contradictorio que X?', '¿Cómo puede ser que X?', and
       also steelmanning patterns like 'podría decirse que X', 'siguiendo esa lógica X sería verdad'.
       Extract these with posture='challenging', attributed_to=<source or 'opponent's implied position'>.
      - Claims attributed to any third party: the other debater, social media posts, studies,
       institutions, unnamed sources ('la industria', 'la ciencia dice que'). Extract these with
       posture='attributing', attributed_to=<name of source>.
      - These DO still get extracted — they are valuable content — but must carry the correct posture."

   b. Add posture and attributed_to to the JSON schema description:
      '"posture": one of ["asserting", "challenging", "attributing", "questioning"]. Use
       "asserting" when the speaker states this as their own belief. Use "challenging" when
       voicing a claim to refute it or interrogate it. Use "attributing" when explicitly
       reporting someone else's claim. Use "questioning" when genuinely asking without committing.\n'
      '"attributed_to": null if posture is "asserting". Otherwise the name of the source,
       speaker, institution, or description (e.g. "Azarian\'s Instagram post", "Kiss",
       "B (steelmanned position)").\n'

3. In the parsing code in extract_claims_from_turn(), extract the new fields:
   - _posture = item.get("posture", "asserting")
   - if _posture not in {"asserting", "challenging", "attributing", "questioning"}:
       _posture = "asserting"
   - _attributed_to = item.get("attributed_to") or None
   - Add both to the returned claim dict

4. Default behaviour: if posture is missing (backward compat), default to "asserting".

Do not change any other part of the extractor logic, turn segmentation, or field structure.
```

---

### Prompt 2 — Update scorer and classifier for posture awareness

```
Read truth_checker/scorer.py and truth_checker/classifier.py in full.

── Part A: scorer.py ──

In compute_speaker_scores(), in the Pass 1 (claims) loop, change the checkable
counting logic from:

    if claim.get("checkable"):
        s["checkable_claims"] += 1

To:

    if claim.get("checkable") and claim.get("posture", "asserting") == "asserting":
        s["checkable_claims"] += 1

Also update the verdicts counting to only count asserting claims:

    verdict = claim.get("verdict", "")
    if verdict in s["verdicts"] and claim.get("posture", "asserting") == "asserting":
        s["verdicts"][verdict] += 1

Do not change any other scoring logic, response counting, or rhetoric counting.

── Part B: classifier.py ──

1. Add "check_as_attributed" to the classifier output schema. This is a bool that is
   True when the claim's posture is not "asserting" — it signals to the fact-checker
   that the verdict should be displayed as applying to the attributed source, not the speaker.

2. In classify_claim(), after building the result dict, add:
   posture = claim.get("posture", "asserting")
   result["check_as_attributed"] = posture != "asserting"

3. Add "check_as_attributed": False to the _DEFAULTS dict.

4. Do not ask the LLM to determine check_as_attributed — derive it from the existing
   posture field. Do not change the LLM prompt or any other classifier logic.
```

---

### Prompt 3 — Add `affirms` relationship type to the responder

```
Read truth_checker/responder.py in full.

Make the following changes:

1. Add "affirms" to _VALID_RELATIONSHIPS:
   _VALID_RELATIONSHIPS = {
       "refutes", "undercuts", "supports", "weakens", "reframes",
       "concedes", "evades", "ignores", "affirms",
   }

2. In _SINGLE_SYSTEM and _BATCH_SYSTEM, add "affirms" to the relationship types list
   with this definition:
   "affirms (B adopts as their own assertion a proposition that A voiced as a challenge,
   attribution, or question — B treats the proposition as true and commits to it; this
   is stronger than 'supports' which merely adds evidence to an existing claim)"

3. Add a clarification note to both prompts:
   "Use 'affirms' ONLY when the responding speaker explicitly or implicitly accepts the
   proposition as their own. Partial agreement, qualification, or building on a related
   point does NOT count as 'affirms' — use 'weakens', 'reframes', or 'supports' instead.
   'Affirms' is appropriate for responses like 'Sí, exactamente', 'Eso es lo que creo',
   or when B continues the debate treating A's questioned premise as a settled fact."

4. Do not change the edge detection logic, batching, or any other responder behaviour.
   The new relationship type flows through the existing infrastructure automatically.
```

---

### Prompt 4 — Attribution resolver: synthesize affirming claims

```
Read truth_checker/responder.py (for response edge structure) and app.py
(lines around detect_responses and mark_restatements calls, find exact positions).

── Part A: Create resolve_attributions() ──

Create a new function resolve_attributions(claims, responses) in a new file
truth_checker/attribution_resolver.py:

def resolve_attributions(claims: list[dict], responses: list[dict]) -> list[dict]:
    """
    For every non-asserting claim (posture ∈ challenging/attributing/questioning)
    that has an 'affirms' response edge from a different speaker, synthesize a new
    asserting claim attributed to the affirming speaker.

    The original claim gains 'affirmed_by': new_claim_id.
    The synthesized claim has 'affirmed_from': original_claim_id.

    Synthesized claims inherit all classifier fields from the original.
    They do NOT inherit start_hint, premises, or warrant_hint (set to null/[]).

    Returns the augmented claims list (original + synthesized claims appended).
    """
    NON_ASSERTING = {"challenging", "attributing", "questioning"}
    
    # Index claims by id
    by_id = {c["id"]: c for c in claims}
    
    # Find affirms edges
    new_claims = []
    for edge in responses:
        if edge.get("relationship") != "affirms":
            continue
        
        affirming_claim = by_id.get(edge.get("claim_id"))       # B's claim
        target_claim    = by_id.get(edge.get("responds_to_claim_id"))  # A's claim
        
        if not affirming_claim or not target_claim:
            continue
        if target_claim.get("posture", "asserting") not in NON_ASSERTING:
            continue
        if affirming_claim.get("speaker") == target_claim.get("speaker"):
            continue  # same speaker, skip
        
        # Build synthesized claim id
        synth_id = f"{affirming_claim['id']}_synth_{target_claim['id']}"
        if synth_id in by_id:
            continue  # already synthesized
        
        synth = {
            # Identity
            "id":              synth_id,
            "speaker":         affirming_claim["speaker"],
            "turn_index":      affirming_claim.get("turn_index"),
            "start_ms":        affirming_claim.get("start_ms"),
            "end_ms":          affirming_claim.get("end_ms"),
            # Content — inherited from original
            "text":            target_claim["text"],
            "posture":         "asserting",
            "attributed_to":   None,
            # Inherited classifier fields
            "claim_type":      target_claim.get("claim_type", "factual"),
            "checkable":       target_claim.get("checkable", False),
            "check_as_attributed": False,
            "evidence_quality": target_claim.get("evidence_quality", "none"),
            "suggested_query": target_claim.get("suggested_query"),
            "thread_id":       target_claim.get("thread_id"),
            "stance":          target_claim.get("stance", "neutral"),
            "qualifier":       target_claim.get("qualifier", "probable"),
            "satirical":       False,
            "restatement_of":  None,
            # Null fields (not extractable from B's affirming turn)
            "start_hint":      None,
            "premises":        [],
            "warrant_hint":    None,
            "rebuttal_cond":   None,
            # Cross-reference
            "affirmed_from":   target_claim["id"],
        }
        
        # Mark the original
        target_claim["affirmed_by"] = synth_id
        
        new_claims.append(synth)
        by_id[synth_id] = synth
    
    return claims + new_claims

── Part B: Wire into app.py ──

1. Import resolve_attributions at the top of app.py:
   from truth_checker.attribution_resolver import resolve_attributions

2. In the analysis pipeline, after detect_responses() and before mark_restatements():
   classified = resolve_attributions(classified, responses)

The synthesized claims will then pass through mark_restatements() and the scorer
as normal asserting claims attributed to the correct speaker.
```

---

### Prompt 5 — Claim card display: posture badges and verdict attribution

```
Read app.py. Find the section that renders individual claim cards — search for
where claim["text"] is displayed along with speaker, verdict, and other metadata.
Also find where fact-check verdicts are rendered on claim cards.

Make the following changes:

1. Add a posture badge helper function near the top of the UI section:

   def _posture_badge(claim: dict, speaker_names: dict) -> str:
       posture = claim.get("posture", "asserting")
       source  = claim.get("attributed_to") or ""
       if posture == "asserting":
           return ""
       labels = {
           "challenging":  "↩ challenges",
           "attributing":  "📎 reports",
           "questioning":  "? questions",
       }
       badge = labels.get(posture, posture)
       if source:
           return f'<span style="font-size:0.78em;color:#888;font-style:italic">{badge}: {source}</span>'
       return f'<span style="font-size:0.78em;color:#888;font-style:italic">{badge}</span>'

   For synthesized claims (affirmed_from is not None), show:
   '⬆ affirmed by [speaker_name]' pointing back to the original challenge.

2. In the claim card rendering, below the speaker/time line and above the claim text,
   insert the posture badge (using st.markdown with unsafe_allow_html=True).

3. When a fact-check verdict is shown on a claim card and check_as_attributed is True,
   change the verdict header from:
     "[Speaker]'s claim — verdict: [VERDICT]"
   to:
     "Claim attributed to [attributed_to] — verdict: [VERDICT]"
   
   If attributed_to is None but check_as_attributed is True, use:
     "Attributed claim — verdict: [VERDICT]"

4. For synthesized claims (affirmed_from is set), show a small link/reference below
   the badge: "Synthesized from [original_claim_id] — affirmed in this turn."

Do not change claim card layout, thread display, or any other UI element.
```

---

### Prompt 6 — Argument map: posture-aware edges

```
Read truth_checker/visualizer.py in full.
Read app.py to find where build_graph_html is called and how edges/nodes are passed.

Make the following changes to visualizer.py:

1. Node styling by posture:
   - "asserting" (or missing) → current node style (no change)
   - "challenging"            → dashed border or lighter node color
   - "attributing"            → dotted border
   - "questioning"            → same as challenging
   - synthesized (affirmed_from set) → slightly different fill to indicate it's synthesized

2. Edge types for posture-related connections:
   - When a claim has posture="challenging" and attributed_to is set, add a directed
     edge from the claim node to a SOURCE NODE representing the attributed_to string.
     Style: red dashed arrow, label "challenges".
   - When a claim has affirmed_from set, add a directed edge from the synthesized claim
     node to the original claim node.
     Style: green dotted arrow, label "affirmed from".
   - When a claim has affirmed_by set, add a directed edge from the original claim node
     to the synthesized claim node.
     Style: green dotted arrow, label "affirmed by".

3. Source nodes (for attributed_to targets):
   Add lightweight "source" nodes (different shape, e.g. box vs circle) for
   attributed_to values that don't correspond to any speaker in the debate.
   Use the attributed_to string as the node label.
   Only create one source node per unique attributed_to value (dedup).

Do not change the existing response-edge rendering or any layout logic.
```

---

## 7. Related Files

| File | Relevance |
|---|---|
| `truth_checker/extractor.py` | Prompt 1 — add posture schema |
| `truth_checker/scorer.py` | Prompt 2A — filter by posture |
| `truth_checker/classifier.py` | Prompt 2B — add `check_as_attributed` |
| `truth_checker/responder.py` | Prompt 3 — add `affirms` relationship |
| `truth_checker/attribution_resolver.py` | Prompt 4 — new file |
| `app.py` | Prompts 4, 5 — wire resolver, display changes |
| `truth_checker/visualizer.py` | Prompt 6 — argument map edges |
| `docs/how-it-works.md` | Post-implementation — update pipeline description |
| `docs/claim-types-reference.md` | Post-implementation — add posture definitions |
