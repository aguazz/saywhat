import json
import logging
import time

import anthropic

from truth_checker.entity_glossary import format_glossary_for_prompt

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an argument analyst. Extract discrete substantive claims from the speaker turn below. "
    "A claim is a statement about the world presented as true that can be agreed or disagreed with. "

    "Do NOT extract:\n"
    "- Questions directed at other speakers\n"
    "- Greetings, thank-yous, filler phrases, or transition sentences\n"
    "- Descriptions of what other speakers believe or have said (e.g. 'Juan Ramón says that…')\n"
    "- Moderator-style introductions or context-setting sentences about the debate itself\n"
    "- Expressions of preference ('I think we should…') without a factual assertion\n"
    "- Clear jokes, hyperbole, or rhetorical questions\n"
    "- Oral discourse markers that precede but are not part of a claim: 'well', 'look', "
    "'you see', 'I mean', 'obviously', 'clearly' used as filler — strip these, do not "
    "extract them as claims on their own\n"
    "- Metalinguistic commentary about the speaker's own discourse: 'as I was saying', "
    "'let me return to my point', 'to summarize', 'what I mean is'\n"
    "- Do NOT transform questions into assertions. If a sentence is interrogative (starts with "
    "¿ or ends with ?), do not extract its content as an asserting claim. Mark it as "
    "'questioning' or 'challenging' with the appropriate posture field instead.\n"
    "- Claims the speaker voices to challenge or refute — these DO get extracted, but with "
    "posture='challenging'. Includes: rhetorical questions like '¿Eso significa que X?', "
    "'¿No es contradictorio que X?', '¿Cómo puede ser que X?'; and steelmanning patterns "
    "like 'podría decirse que X', 'siguiendo esa lógica X sería verdad', 'one could argue X'. "
    "Set attributed_to to the source or 'opponent's implied position'.\n"
    "- Claims attributed to any third party — these DO get extracted, but with "
    "posture='attributing'. Covers: the other debater, social media posts, studies, "
    "institutions, unnamed sources ('la industria dice que', 'la ciencia dice que', "
    "'según X'). Set attributed_to to the name of the source.\n"
    "- Performative speech acts that are argumentative moves, not claims: 'I agree', "
    "'I disagree', 'I concede that', 'I accept your point'\n"

    "Focus on factual, causal, statistical, interpretive, or evaluative claims about the debate topic. "
    "Be conservative: extract the 3–6 most substantive claims per turn, not every possible statement. "
    "The turn may be in Spanish or English — preserve the original language in your output. "

    'Return a JSON array. Each item: {"text": str, "start_hint": str, "qualifier": str, "stance": str, "premises": [str], "rebuttal_cond": str|null, "warrant_hint": str|null, "posture": str, "attributed_to": str|null}. '
    '"text" is the exact or lightly cleaned claim. '
    '"start_hint" is the first 5 words of the sentence containing the claim. '
    '"posture" is one of ["asserting", "challenging", "attributing", "questioning"]. '
    'Use "asserting" when the speaker states this as their own belief or factual position. '
    'Use "challenging" when voicing a claim in order to refute or interrogate it (rhetorical '
    'questions, steelmanning). Use "attributing" when explicitly reporting someone else\'s claim '
    '("B dijo que...", "el post decía que...", "según X..."). Use "questioning" when genuinely '
    'asking whether the claim is true without committing to it. Default to "asserting".\n'
    '"attributed_to": null if posture is "asserting". Otherwise the name of the source, '
    'speaker, institution, or short description (e.g. "Azarian\'s Instagram post", "Kiss", '
    '"B (steelmanned position)", "la industria azucarera").\n'
    '"qualifier" captures the modal certainty with which the speaker asserted the claim:\n'
    '  "definite"    — stated as an established fact, no hedging '
    '(e.g. "wages fell", "the data shows", "it is a fact that")\n'
    '  "probable"    — likely true but not absolute '
    '(e.g. "tends to", "generally", "in most cases", "the evidence suggests")\n'
    '  "possible"    — explicitly hedged '
    '(e.g. "may", "could", "perhaps", "it seems", "one might argue")\n'
    '  "speculative" — uncertain or hypothetical '
    '(e.g. "might", "I suspect", "it is possible that", "if this continues")\n'
    '"stance" is the claim\'s position relative to the debate motion (if one is provided '
    'in the message): "pro" (supports or argues in favour of the motion), "con" (opposes '
    'or argues against it), or "neutral" (procedural, definitional, or orthogonal to the '
    'motion). If no debate motion is provided, always return "neutral".\n'
    '"premises" is a list of the 1–3 most explicit supporting reasons, data points, or '
    'pieces of evidence the speaker cited for this claim *in the same turn*. '
    'Extract verbatim or lightly cleaned phrases. '
    'A premise supports the claim — it is not a restatement of it. '
    'If no supporting premise is stated in the turn, return [].\n'
    '"rebuttal_cond": a condition the speaker explicitly acknowledged would defeat the claim '
    '(often signalled by "unless", "except if", "provided that", "as long as"). '
    'Extract verbatim or lightly cleaned. Return null if none is stated.\n'
    '"warrant_hint": the explicit inference rule the speaker stated to connect premises to '
    'the conclusion (often signalled by "because", "which means that", "this shows that", '
    '"the logic is"). Return null if the warrant is purely implicit — do NOT invent one '
    'that the speaker did not state.\n'
    "If there are no substantive claims, return []."
)

_MIN_TURN_WORDS = 20   # skip turns shorter than this — usually greetings or brief remarks


def extract_claims_from_turn(turn: dict, api_key: str, motion: str = "", glossary: dict = {}) -> list[dict]:
    """
    Extract discrete substantive claims from a single speaker turn using Claude Haiku.

    Skips very short turns (likely greetings/acknowledgements) that would not
    contain meaningful claims.  Returns [] if the API call fails or no claims
    are found.

    motion: optional debate motion or central question. When provided, the model
    classifies each claim's stance as "pro", "con", or "neutral" relative to it.
    """
    # Skip turns that are too short to contain a real claim
    word_count = len(turn["text"].split())
    if word_count < _MIN_TURN_WORDS:
        return []

    client = anthropic.Anthropic(api_key=api_key)
    motion_line = f"Debate motion: {motion}\n" if motion.strip() else ""
    glossary_block = (
        f"Entity glossary (when a claim uses a variant name, rewrite it as the canonical "
        f"name followed by the variant in parentheses, e.g. 'Ancel Keys (referido como «Kiss»)'):\n"
        f"{format_glossary_for_prompt(glossary)}\n\n"
        if glossary else ""
    )
    user_msg = f"{motion_line}{glossary_block}Speaker: {turn['speaker']}\nText:\n{turn['text']}"

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error on turn %s: %s", turn["turn_index"], exc)
        return []
    finally:
        time.sleep(0.3)

    # Strip optional markdown code fence
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("expected a JSON array")
    except Exception as exc:
        logger.warning("JSON parse error on turn %s: %s — raw: %.120s", turn["turn_index"], exc, raw)
        return []

    claims = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("text", "").strip():
            continue
        _qualifier = item.get("qualifier", "probable")
        if _qualifier not in {"definite", "probable", "possible", "speculative"}:
            _qualifier = "probable"
        _stance = item.get("stance", "neutral")
        if _stance not in {"pro", "con", "neutral"}:
            _stance = "neutral"
        _premises = item.get("premises", [])
        if not isinstance(_premises, list):
            _premises = []
        _rb = item.get("rebuttal_cond")
        _wh = item.get("warrant_hint")
        _posture = item.get("posture", "asserting")
        if _posture not in {"asserting", "challenging", "attributing", "questioning"}:
            _posture = "asserting"
        _attributed_to = item.get("attributed_to") or None
        claims.append(
            {
                "id":             f"claim_{turn['turn_index']}_{i}",
                "speaker":        turn["speaker"],
                "turn_index":     turn["turn_index"],
                "start_ms":       turn["start_ms"],
                "end_ms":         turn["end_ms"],
                "text":           item["text"].strip(),
                "start_hint":     item.get("start_hint", "").strip(),
                "qualifier":      _qualifier,
                "stance":         _stance,
                "premises":       [p for p in _premises if isinstance(p, str) and p.strip()],
                "rebuttal_cond":  _rb.strip() if isinstance(_rb, str) and _rb.strip() else None,
                "warrant_hint":   _wh.strip() if isinstance(_wh, str) and _wh.strip() else None,
                "posture":        _posture,
                "attributed_to":  _attributed_to,
            }
        )

    return claims
