# How SayWhat Analyzes a Debate

SayWhat takes a debate — any recorded conversation where people argue about something — and breaks it into its building blocks.

Those building blocks are **claims**.

From claims, the app builds a map showing how speakers attack, support, evade, and challenge each other. It checks whether the facts hold up. It spots rhetorical tricks. And it scores each speaker on how well they actually engaged with the argument they were supposed to be having.

This guide explains the whole system in plain English. No background in logic or computer science required.

---

## The Running Example

Throughout this guide, we'll use a short imaginary debate between **Alex** and **Sam**, arguing about whether cities should ban cars from their downtown areas.

> **Alex:** "Cities should ban cars from downtown. Studies show that pedestrian zones reduce NO₂ — a major air pollutant — by up to 40%."
>
> **Sam:** "You're cherry-picking. That figure comes from a single street in Madrid, not from city-wide data. And when Oslo tried a broader ban, local businesses reported a 15% drop in revenue in year one."
>
> **Alex:** "The Oslo revenue dip was temporary. Shops were up 10% within two years, thanks to higher foot traffic. And Madrid wasn't an isolated case — Brussels and Ghent showed similar results."
>
> **Sam:** "Oslo and Brussels both have excellent public transit as an alternative. You can't generalize from those cities to somewhere like Houston, which would be paralyzed without cars."

Four short turns. Plenty to work with.

---

## What Is a Claim?

A **claim** is a statement about the world that can be agreed or disagreed with.

Not everything a speaker says is a claim. Questions aren't claims. Greetings aren't claims. "I just feel like..." without any factual content isn't a claim. But when a speaker asserts something they expect to be accepted as true — that's a claim.

From Alex and Sam's debate, here are the claims SayWhat would extract:

| # | Speaker | Claim |
|---|---------|-------|
| C1 | Alex | "Pedestrian zones reduce NO₂ by up to 40%." |
| C2 | Sam | "That figure comes from a single street in Madrid, not city-wide data." |
| C3 | Sam | "Oslo businesses reported a 15% drop in revenue in year one." |
| C4 | Alex | "Oslo shops were up 10% within two years." |
| C5 | Alex | "Brussels and Ghent showed similar results to Madrid." |
| C6 | Sam | "Oslo and Brussels have excellent public transit alternatives." |
| C7 | Sam | "Houston would be paralyzed without cars." |

Notice that not all claims are equally verifiable. C1 is the kind of thing you could look up. C7 is a prediction — harder to check, but still a claim about the world. The app handles both, but treats them differently.

---

## What Information Does a Claim Contain?

Every claim the app extracts carries a set of attributes. Here's what each one means.

### Claim type

What kind of statement is this?

| Type | Plain English | Example from the debate |
|------|--------------|-------------------------|
| **Factual** | A verifiable statement about what is or was true | "Oslo tried a car ban." |
| **Statistical** | Involves a number, percentage, or quantity | "Businesses saw a 15% revenue drop." |
| **Causal** | Claims one thing causes another | "Higher foot traffic caused revenue growth." |
| **Predictive** | Claims what will happen | "Houston would be paralyzed without cars." |
| **Comparative** | Compares two or more things | "Oslo's transit is better than Houston's." |
| **Definitional** | Argues about the meaning of a concept | "A pedestrian zone isn't the same as a car-free city." |
| **Interpretive** | A judgment about the significance of facts | "A one-year dip isn't a real problem." |
| **Moral** | A claim about what ought to be done | "Cities should ban cars from downtown." |
| **Anecdotal** | Based on a single case without broader data | "My cousin's shop in Madrid doubled its sales." |

Knowing the type matters because different claim types warrant different responses. A statistical claim should be answered with better statistics. A moral claim can't really be "fact-checked" — it's a value judgment.

### Checkable

Can this claim be verified against external evidence? A statistical claim about Oslo's revenue is checkable. A moral claim about what cities "should" do is not. The app only runs fact-checking on checkable claims — holding a value judgment to an evidence standard would be a category error, and it would be unfair to penalize a speaker for having opinions.

### Evidence cited in speech

Did the speaker themselves provide evidence for the claim? "Studies show a 40% reduction" cites a source (vaguely, but it does). "It's obvious" doesn't. The app notes how strong or weak the cited evidence is:

- **Strong** — Named study, institution, or official data source
- **Moderate** — General reference to research or expert consensus
- **Weak** — A single example, a vague claim of expertise
- **None** — Bare assertion with no supporting reasoning

### Suggested search query

When the app checks a claim against evidence, it generates a short search query optimized for academic databases. For C3 ("Oslo businesses dropped 15%"), the suggested query might be: *Oslo pedestrian zone business revenue impact 2019*.

### Satirical

Was the statement clearly a joke or hyperbole? Satirical claims are skipped in fact-checking.

---

## How Claims Connect: Relationships

Here's where it gets interesting.

In any real debate, claims don't stand alone. Speakers react to each other. They attack, agree, dodge, and reframe. SayWhat tracks these reactions as **relationships between claims**.

| Relationship | What it means |
|---|---|
| **Refutes** | Directly denies the conclusion. "You said X; I'm saying X is wrong." |
| **Undercuts** | Challenges the *evidence or reasoning*, not the conclusion itself. "That evidence doesn't actually prove X." |
| **Supports** | Agrees with or extends the prior claim. "X is true, and here's more evidence." |
| **Weakens** | Accepts the claim but reduces its strength or scope. "X may be true for Europe, but not everywhere." |
| **Reframes** | Accepts the facts but changes their interpretation. "Yes, X happened, but it means something different." |
| **Concedes** | Acknowledges the other speaker is at least partly right. "Fair point." |
| **Evades** | Changes the subject without engaging with the prior claim. |
| **Ignores** | Makes a new, unrelated claim — no connection to what was just said. |

> **Refutes vs. Undercuts — what's the difference?**
>
> These look similar but aren't.
>
> *Refutes* = "Your conclusion is wrong."
>
> *Undercuts* = "Your evidence doesn't support your conclusion — though the conclusion might still be true."
>
> In the example, when Sam says the 40% figure comes from "just one street in Madrid," that's an *undercut* — Sam isn't saying air quality doesn't improve, just that this particular data point doesn't prove it does everywhere. It's a subtler and often more effective move than outright denial.

From Alex and Sam's debate, SayWhat would map these relationships:

| From | To | Relationship | Why |
|---|---|---|---|
| C2 (Sam) | C1 (Alex) | **Undercuts** | Challenges the evidence behind the claim, not the claim itself |
| C3 (Sam) | C1 (Alex) | **Refutes** | Presents counter-evidence that the conclusion is wrong |
| C4 (Alex) | C3 (Sam) | **Reframes** | Accepts the Oslo data but argues it means something different |
| C5 (Alex) | C2 (Sam) | **Refutes** | Argues the evidence wasn't as narrow as Sam claimed |
| C6 (Sam) | C5 (Alex) | **Undercuts** | Argues Brussels/Ghent don't generalize to other cities |

---

## The Ten-Step Pipeline

SayWhat processes a debate in ten steps:

1. **Split into turns.** Group the transcript by speaker, creating a sequence of turns.

2. **Extract claims.** Read each turn and pull out the substantive statements (3–6 per turn). Questions, jokes, filler, and pure rhetorical questions are filtered out.

3. **Classify each claim.** Assign a claim type, checkable flag, evidence-quality rating, and a suggested search query.

4. **Group into threads.** Cluster all claims — across all speakers — by topic. A thread is a set of claims that share a subject. In our example, there would be a thread about *air quality effects* and a thread about *economic impact on businesses*.

5. **Map responses.** For each claim, determine whether any later claim from a different speaker is a direct response, and what kind of response it is.

6. **Compute argument status.** Apply a mathematical rule borrowed from formal argumentation theory: a claim is "defended" if all the claims that attack it are themselves successfully attacked. Defended claims are labeled **Grounded**. Claims under attack that aren't defended are **Contested**. Unchallenged claims are **Unattacked**. (More on this below.)

7. **Retrieve evidence.** Search Wikipedia and academic databases for information relevant to each checkable claim.

8. **Verify claims.** Pass each checkable claim and its evidence to an AI model, which returns a verdict and explanation.

9. **Detect rhetoric.** Analyze each speaker turn for logical fallacies (straw man, cherry-picking, ad hominem, etc.) and legitimate rhetorical devices (appeals to authority, vivid examples, etc.).

10. **Score speakers.** Calculate per-speaker reliability (how many claims held up to fact-checking) and engagement rate (how often they actually addressed what the other speaker said).

---

## How a Debate Becomes a Graph

After step 5, the app has a network: **nodes** (claims) connected by **edges** (responses).

- Each **node** is a claim. Its color shows the speaker who made it.
- Each **edge** is a directed arrow showing a response. Its label shows the relationship type.
- The arrow points *from* the responding claim *to* the claim being responded to.

Here's a rough sketch of what the Alex/Sam graph looks like:

```
[Alex C1: 40% NO₂ reduction]
        ↑ undercuts ── [Sam C2: just one Madrid street]
        ↑ refutes ─── [Sam C3: Oslo -15% revenue year one]
                              ↑ reframes ── [Alex C4: Oslo +10% in year two]
                                                    ↑ undercuts ── [Sam C6: good transit ≠ universal]

[Alex C5: Brussels and Ghent too]
        ↑ undercuts ── [Sam C6: Oslo/Brussels ≠ Houston]

[Sam C7: Houston paralyzed] — no responses
```

**How to read the graph:**

- **Follow arrows from responder to target.** An arrow from Sam C2 to Alex C1 means Sam C2 is responding to Alex C1.
- **Clusters of incoming arrows** on one node mean that claim attracted a lot of attention. It's probably a central point of contention.
- **Nodes with no incoming arrows** are uncontested — nobody challenged them. Uncontested is not the same as proven true; it might just mean the other speaker didn't get to it.
- **Long chains** (A responds to B, B responds to C, C responds to D) show sustained back-and-forth on one topic.
- **Dead ends** — a claim made that gets no response from the other speaker — are worth noticing. They could represent evasion, or just a debate that moved on.

---

## What "Grounded," "Contested," and "Unattacked" Mean

These three statuses come from a mathematical model of argumentation (see [the theoretical note](#theoretical-foundations) at the end). In plain English:

**Grounded:** This claim survived all the attacks against it. Every claim that attacked it was itself successfully attacked. Under a strict rational reading, this claim is *accepted*.

**Contested:** This claim is under attack and not fully defended. The debate left it in genuine dispute.

**Unattacked:** Nothing in the debate challenged this claim. It stands unopposed — which is not the same as being proven true. It might be undisputed because everyone agreed, or simply because the other speaker never addressed it.

In our example:
- **C6 (Sam: "Oslo and Brussels have excellent public transit")** — Grounded. Alex never challenged it.
- **C1 (Alex: "Pedestrian zones reduce NO₂ by 40%")** — Contested. Attacked by C2 and C3; defended somewhat by C4 and C5, but not decisively.
- **C7 (Sam: "Houston would be paralyzed")** — Unattacked. Alex never addressed this claim.

---

## How to Interpret the Analysis

### What the graph helps you notice

- **Hotspots:** Which claims attracted the most responses? These are the real battlegrounds of the debate — the questions where both sides invested effort.
- **Evasions:** Did one speaker consistently leave certain claims unanswered? A pattern of `evades` or `ignores` responses from one speaker is visible in the graph.
- **Thread structure:** The natural clustering of claims reveals how the debate was actually organized, which may differ from the stated topic.
- **Engagement asymmetry:** One speaker may engage deeply while the other deflects. The direct response rate score captures this.

### What to be careful about

**The analysis is a simplification.** A long, nuanced speech turn is reduced to a few claims. Important caveats and qualifications can get lost in extraction.

**Relationships are AI-classified.** The app uses a language model to decide whether a claim "refutes" or "reframes" another. It gets it right most of the time, but it will occasionally misclassify. If a relationship label seems off, trust your reading.

**Verdicts are based on available evidence, not ground truth.** "True" means the available evidence supports the claim. For many topics — especially recent events, regional statistics, or contested science — the evidence base is incomplete. "Unverifiable" often means "we couldn't find good sources," not "this is unknowable."

**Confidence scores are approximate.** When the app says it is "75% confident" in a verdict, that reflects the AI model's internal assessment — not a statistically calibrated probability. High confidence means the evidence was clear; low confidence means it was murky.

**Some claims resist fact-checking by design.** Moral claims, pure opinions, predictions, and interpretive judgments are labeled `subjective` or `unverifiable` and are not counted for or against the speaker's reliability score.

### Speaker scores — what they mean and don't mean

| Score | What it measures | What it does not measure |
|-------|-----------------|--------------------------|
| **Reliability score** | % of checkable claims that were True or Partially True | Whether the overall argument was good or persuasive |
| **Direct response rate** | % of responses that genuinely engaged (vs. evaded or ignored) | Whether the engagement was correct or effective |

A speaker can score well on reliability (accurate facts) while making a bad argument. A speaker can engage deeply (high response rate) while being consistently wrong. The scores measure specific dimensions — they don't add up to a single verdict.

---

## The Running Example, Fully Analyzed

**Claims table:**

| # | Speaker | Claim text | Type | Checkable | Verdict |
|---|---------|-----------|------|-----------|---------|
| C1 | Alex | "Pedestrian zones reduce NO₂ by up to 40%." | Statistical | Yes | Partially True |
| C2 | Sam | "That figure comes from a single street in Madrid." | Factual | Yes | Contested |
| C3 | Sam | "Oslo businesses saw a 15% revenue drop in year one." | Statistical | Yes | Partially True |
| C4 | Alex | "Oslo shops were up 10% within two years." | Statistical | Yes | Partially True |
| C5 | Alex | "Brussels and Ghent showed similar results." | Factual | Yes | Partially True |
| C6 | Sam | "Oslo and Brussels have excellent public transit alternatives." | Factual | Yes | True |
| C7 | Sam | "Houston would be paralyzed without cars." | Predictive | No | — (not checked) |

**Argument statuses:**
- C6 → **Grounded** (unattacked, accepted)
- C7 → **Unattacked** (not addressed by Alex)
- C1 → **Contested** (attacked by C2 and C3, not fully defended)
- C3 → **Contested** (attacked by C4 and C5)

**Rhetorical profile:**
- Sam: **cherry-picking** flagged on C2 — Sam accuses Alex of cherry-picking, but the prompt is also valid as a legitimate methodological objection. The app distinguishes the two.
- Alex: **hasty generalization** flagged on C5 — inferring from three European cities to a general claim about car bans.
- Alex: **appeal to authority** (legitimate) — "studies show" is a real rhetorical move and can be fair or unfair depending on whether the studies are identified.

**Speaker scores:**
- **Alex** — Reliability: 3/4 checkable claims Partially True = 75%. Direct response rate: Alex responded to all of Sam's major claims = 100%.
- **Sam** — Reliability: 2/3 checkable claims True or Partially True = 67%. Direct response rate: Sam left C4 and C5 unanswered = 33%.

**What a user would take away:**
- The NO₂ claim (C1) is the most contested node — it drew two attacks and was only partially defended.
- Sam's transit claim (C6) is the strongest accepted fact in the exchange. Neither speaker disputed it.
- The economic debate was not resolved: both sides cited real data about Oslo, but they measured different things (year one vs. year two). Both claims are "Partially True" — they're not contradictory, just measuring different timeframes.
- Alex engaged with every one of Sam's claims. Sam did not engage with Alex's Brussels/Ghent evidence (C5) or the Oslo recovery data (C4).
- Houston (C7) was raised as a rebuttal but never addressed. It stands as an uncontested challenge to the generalizability of Alex's argument.

---

## Theoretical Foundations

SayWhat's analysis is grounded in real academic research on argumentation. You don't need to know any of this to use the app — but it's worth knowing the system was built on genuine scholarly foundations.

- **Toulmin (1958)** — The claim–evidence–warrant structure of each claim mirrors the Toulmin model, the most widely used framework for representing argument components. When the app records what evidence a speaker cited and how strong it was, it's applying Toulmin.

- **Dung (1995)** — The "Grounded / Contested / Unattacked" status labels implement Dung's abstract argumentation frameworks — a mathematical theory of how arguments defeat each other and which ones remain rationally acceptable. The algorithm that computes these labels is built directly into the app.

- **van Eemeren & Grootendorst (2004)** — The fallacy taxonomy treats fallacies as violations of the rules of fair discussion, following the pragma-dialectics framework. A straw man is a fallacy not because it's illogical in the abstract, but because it breaks the rule that you must address your opponent's *actual* argument.

- **Slonim et al. (2021)** — The overall pipeline — extract → classify → thread → respond → verify — mirrors the architecture of IBM Project Debater, the most advanced autonomous debate system built to date.

The app doesn't make you read these papers. But they're in the `papers/` folder if you're curious.
