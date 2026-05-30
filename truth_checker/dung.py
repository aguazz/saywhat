"""
Dung (1995) grounded extension computation.

Given a set of claims (arguments) and response edges (attacks), computes
which claims survive all attacks under skeptical (grounded) semantics.

Reference: Dung, P.M. (1995). On the acceptability of arguments and its
fundamental role in nonmonotonic reasoning, logic programming and n-person
games. Artificial Intelligence, 77(2), 321-357.
"""

_ATTACK_RELATIONSHIPS = {"refutes", "undercuts", "weakens"}


def compute_grounded_extension(
    claims: list[dict],
    responses: list[dict],
) -> dict[str, str]:
    """
    Compute Dung's grounded extension over the claim/response graph.

    Returns a dict mapping claim_id → status:
      "grounded"   — in the grounded extension: every attacker is itself
                     defeated by a grounded argument (skeptically accepted)
      "contested"  — receives at least one attack not neutralised by a
                     grounded argument (outcome undecided)
      "unattacked" — receives no attacks at all

    The grounded extension is computed as the least fixpoint of Dung's
    characteristic function F_AF, starting from the empty set:

      F_AF(S) = { A | ∀ B ∈ attackers(A) : ∃ G ∈ S such that G attacks B }

    Iteration:
      S_0 = ∅
      S_{n+1} = F_AF(S_n)
      Stop when S_n = S_{n+1}

    Handles empty claims or responses gracefully (returns all "unattacked").
    """
    if not claims:
        return {}

    claim_ids = {c["id"] for c in claims}

    # attackers[B] = set of claim IDs that attack B
    attackers: dict[str, set[str]] = {cid: set() for cid in claim_ids}

    for r in responses:
        if r.get("relationship") not in _ATTACK_RELATIONSHIPS:
            continue
        source = r.get("from_claim_id")       # A attacks B
        target = r.get("responds_to_claim_id")  # B is attacked
        if source in claim_ids and target in claim_ids:
            attackers[target].add(source)

    # Iterative fixpoint: build grounded extension from the empty set.
    # A claim is added when every one of its attackers is itself attacked
    # by some claim already in the grounded set.
    grounded: set[str] = set()
    changed = True
    while changed:
        changed = False
        for cid in claim_ids:
            if cid in grounded:
                continue
            # Acceptable w.r.t. grounded iff every attacker of cid is
            # attacked by at least one member of grounded.
            # (When attackers[cid] is empty, all() is vacuously True.)
            if all(attackers[atk] & grounded for atk in attackers[cid]):
                grounded.add(cid)
                changed = True

    # Label each claim
    status: dict[str, str] = {}
    for cid in claim_ids:
        if cid in grounded:
            status[cid] = "grounded"
        elif attackers[cid]:
            status[cid] = "contested"
        else:
            status[cid] = "unattacked"

    return status
