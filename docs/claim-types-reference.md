# Claim Types and Terms Reference

Quick-reference tables for every label, type, and score the app uses. For the full explanation with examples, see [how-it-works.md](how-it-works.md).

---

## Claim Types

| Type | What it is | Example |
|------|-----------|---------|
| **Factual** | A verifiable statement about what is or was true | "Oslo implemented a car ban in 2019." |
| **Statistical** | Involves a number, percentage, rate, or quantity | "Businesses saw a 15% drop in revenue." |
| **Causal** | Claims one thing causes or caused another | "Higher foot traffic caused revenue growth." |
| **Predictive** | Claims what will happen | "Houston would grind to a halt without cars." |
| **Comparative** | Compares two or more things | "Oslo's transit is far better than Houston's." |
| **Definitional** | Argues about the meaning of a concept | "A pedestrian zone is not the same as a car-free city." |
| **Interpretive** | A judgment about the significance of facts | "A one-year revenue dip isn't a serious problem." |
| **Moral** | A claim about what ought to be done or valued | "Cities should ban cars from downtown." |
| **Anecdotal** | Based on a single personal case, without broader data | "My cousin's shop in Madrid doubled its sales after the ban." |

---

## Evidence Quality (cited by the speaker in their speech)

| Rating | What it means |
|--------|--------------|
| **Strong** | Named study, official institution, or specific data source |
| **Moderate** | General reference to research or expert consensus |
| **Weak** | A single example, a vague claim of expertise, or hearsay |
| **None** | Bare assertion with no supporting reasoning at all |

---

## Fact-Check Verdicts

| Verdict | What it means |
|---------|--------------|
| **True** | Available evidence supports the claim. |
| **Partially True** | The claim has a factual basis but is incomplete, oversimplified, or missing important context. |
| **Contested** | Evidence both supports and contradicts the claim, or expert sources genuinely disagree. |
| **Misleading** | Technically accurate but framed in a way likely to create a false impression. |
| **False** | Available evidence contradicts the claim. |
| **Unverifiable** | Not enough evidence exists to evaluate this claim — not the same as "false." |
| **Subjective** | A matter of values, interpretation, or opinion. Evidence cannot resolve it. |

---

## Argument Status (after grounded extension computation)

| Status | What it means |
|--------|--------------|
| **Grounded** | Defended: all claims that attack this one are themselves attacked. Under a strict rational reading, this claim is accepted. |
| **Contested** | Under attack and not fully defended. The debate left it in genuine dispute. |
| **Unattacked** | Nothing in the debate challenged this claim. Stands unopposed — not the same as proven true. |

---

## Claim Relationship Types

| Relationship | What it means |
|---|---|
| **Refutes** | Directly denies the conclusion. "You said X; I'm saying X is wrong." |
| **Undercuts** | Challenges the evidence or reasoning, not the conclusion itself. "That evidence doesn't prove X — though X might still be true." |
| **Supports** | Agrees with or adds evidence for the prior claim. |
| **Weakens** | Accepts the claim but reduces its strength or scope. "X may be true here, but not everywhere." |
| **Reframes** | Accepts the facts but changes what they mean. "Yes, X happened, but it shows something different." |
| **Concedes** | Acknowledges the other speaker is at least partly right. |
| **Evades** | Shifts to a different topic without addressing the prior claim. |
| **Ignores** | Makes an unrelated new claim with no connection to what was just said. |

---

## Logical Fallacies

These are rhetorical moves the app flags as violations of fair argument.

| Fallacy | What it is | Quick example |
|---------|-----------|---------------|
| **Straw Man** | Misrepresents the opponent's argument, then attacks the misrepresentation | "So you want to ban all vehicles everywhere forever?" |
| **Ad Hominem** | Attacks the person, not the argument | "You'd say that — you've never even owned a car." |
| **False Dichotomy** | Presents only two options when more exist | "Either we ban cars or we accept chronic pollution." |
| **Appeal to Authority** (illegitimate) | Invokes an authority who lacks relevant expertise, or in a misleading way | "A famous influencer said it, so it must be true." |
| **Slippery Slope** | Claims one action leads inevitably to extreme consequences without justification | "Ban cars, and next they'll ban bikes, then walking." |
| **Cherry-Picking** | Selects only the evidence that supports one side | Citing only year-one revenue data while ignoring year-two recovery |
| **Appeal to Emotion** | Uses emotional manipulation instead of evidence | "Think of the children who can't breathe!" |
| **Anecdote Over Data** | Uses one personal story to override statistical evidence | "My uncle's shop did great — therefore businesses aren't affected." |
| **Whataboutism** | Deflects critique by pointing to something else | "What about factory emissions — why are you only targeting cars?" |
| **Hasty Generalization** | Draws a broad conclusion from too few examples | "It worked in Oslo, so it'll work everywhere." |
| **Correlation as Causation** | Treats simultaneous events as cause-and-effect | "Revenue went up after the ban, so the ban caused it." |

---

## Rhetorical Devices

These are persuasion techniques that are not fallacies — they can be fair, effective, and legitimate.

| Device | What it is |
|--------|-----------|
| **Appeal to Authority** (legitimate) | Cites a relevant expert, institution, or official data source |
| **Appeal to Emotion** (fair) | Uses emotional resonance honestly to make an abstract point concrete |
| **Vivid Example** | A concrete story or scenario that makes a general claim tangible |
| **Social Proof** | Argues from wide consensus or broad popular adoption |
| **Personal Testimony** | Uses first-hand experience as supporting evidence |
| **Framing Effect** | Chooses specific words or metaphors to present facts in a favorable light |
| **Loaded Language** | Uses emotionally charged words to prime the listener toward a conclusion |

---

## Speaker Score Definitions

| Score | Formula | What high means | What it doesn't mean |
|-------|---------|----------------|----------------------|
| **Reliability score** | (True + Partially True claims) ÷ checkable claims | Speaker's checkable facts held up | That their argument was valid or persuasive |
| **Direct response rate** | Refutes + Undercuts + Supports + Weakens + Reframes + Concedes) ÷ all responses | Speaker genuinely engaged with the other side | That their engagement was correct or effective |
