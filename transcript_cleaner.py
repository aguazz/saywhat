import json
import logging

import anthropic

logger = logging.getLogger(__name__)

# ── Tuning knobs ─────────────────────────────────────────────────────────────

# Number of utterances sent per chunk in the local scan (Phase 1).
# Smaller = sharper attention but more API calls. 20 is a good balance.
_CHUNK_SIZE = 20

# Characters kept from each end of a long utterance in the global scan (Phase 2).
# Only used for the global/teaser pass where we need the whole transcript visible.
_HEAD_CHARS = 400
_TAIL_CHARS = 250

# ── Shared system prompt ──────────────────────────────────────────────────────

_SYSTEM = (
    "You are reviewing a debate transcript to identify utterances that contain "
    "non-debate content and should be excluded from argument analysis.\n\n"

    "CRITICAL: A single utterance can contain BOTH legitimate debate content AND "
    "non-debate content. This happens when a host finishes a debate point and then "
    "pivots to a podcast intro, a sponsor read, or an outro — all within the same "
    "turn. You MUST flag such utterances even when they also contain debate content. "
    "Read the COMPLETE text of each utterance carefully, including the middle.\n\n"

    "FLAG utterances that contain ANY of the following non-debate elements:\n\n"

    "1. PODCAST / SHOW INTRODUCTIONS\n"
    "   Signals: host greeting the audience and introducing the show by name; "
    "host identifying themselves ('yo soy [name]', 'I'm your host'); "
    "host describing the episode format or how the guest was invited; "
    "host welcoming the guest with a structured monologue.\n"
    "   Spanish markers: 'Muy buenas y bienvenidos', 'bienvenidos a un nuevo episodio', "
    "'yo soy Gonzalo', 'episodio especial', 'desde [show name] intentamos'.\n"
    "   English markers: 'welcome to the podcast', 'I'm your host', 'today's episode'.\n\n"

    "2. SPONSOR READS / PRODUCT PROMOTIONS\n"
    "   Signals: host advertising a product, course, service, or external link; "
    "calls to enrol, buy, sign up, or visit a URL; "
    "phrases like 'antes de continuar', 'before we continue', 'our sponsor today'.\n"
    "   Spanish markers: 'antes de continuar con el podcast', 'ya tenéis disponible', "
    "'sin nota de corte', 'te dejo la información en', 'descripción del vídeo'.\n\n"

    "3. OUTRO / SIGN-OFF MONOLOGUES\n"
    "   Signals: host thanking the guest and the audience at the end of the recording; "
    "farewell phrases directed at the audience (not at the other debater); "
    "reminders to follow on social media or check show notes.\n"
    "   Spanish markers: 'nos despedimos', 'hasta el siguiente episodio', "
    "'recordad que tenéis las redes sociales', 'adiós'.\n\n"

    "4. CALLS TO ACTION directed at the audience\n"
    "   ('suscríbete', 'síguenos', 'check the link in bio', 'follow me at').\n\n"

    "5. REPEATED TEASER CLIPS\n"
    "   Utterances whose text appears almost word-for-word in another part of the "
    "transcript (episode teasers played at the top of the recording).\n\n"

    "DO NOT FLAG:\n"
    "- Substantive debate exchanges between the speakers.\n"
    "- Moderator or host questions directed at the guest about the debate topic.\n"
    "- Brief mutual greetings between speakers that are part of the natural "
    "conversation flow (not a structured audience-facing monologue).\n\n"

    "Return a JSON object with this exact structure:\n"
    "{\n"
    "  \"out_of_scope\": [\n"
    "    {\"index\": <integer>, \"reason\": \"<one concise sentence explaining why>\", "
    "\"confidence\": \"high\" | \"medium\" | \"low\"},\n"
    "    ...\n"
    "  ]\n"
    "}\n\n"
    "The reason must name the specific category (e.g. 'Podcast intro', 'Sponsor read', "
    "'Outro sign-off', 'Teaser clip') and quote a short phrase from the utterance that "
    "triggered the detection.\n"
    "confidence levels:\n"
    "  \"high\"   — the utterance is entirely or almost entirely non-debate content; "
    "safe to exclude with no loss of analysis material.\n"
    "  \"medium\" — the utterance contains BOTH non-debate content AND substantial debate "
    "content; removing it would also discard legitimate claims or arguments. Flag it so "
    "the user can review carefully.\n"
    "  \"low\"    — the utterance has only minor non-debate elements embedded in otherwise "
    "legitimate debate content; the non-debate portion is brief relative to the whole.\n"
    "If nothing should be excluded, return { \"out_of_scope\": [] }. "
    "Return only valid JSON. No markdown fences."
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _render_full(i: int, u: dict) -> str:
    """Render utterance with FULL text — used in the chunked local scan."""
    return f"[{i}] {u.get('speaker', '?')}: {u.get('text', '').strip()}"


def _render_truncated(i: int, u: dict) -> str:
    """
    Render utterance with head+tail truncation — used in the global scan
    so the full transcript fits in one prompt for cross-utterance comparison.
    """
    text = u.get("text", "").strip()
    speaker = u.get("speaker", "?")
    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return f"[{i}] {speaker}: {text}"
    return f"[{i}] {speaker}: {text[:_HEAD_CHARS]} […] {text[-_TAIL_CHARS:]}"


_VALID_CONFIDENCE = {"high", "medium", "low"}


def _parse_response(raw: str) -> list[dict]:
    """Parse a model JSON response into a list of {index, reason, confidence} dicts."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    items = data.get("out_of_scope", [])
    if not isinstance(items, list):
        raise ValueError("out_of_scope must be a list")
    result = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("index"), (int, float)):
            confidence = item.get("confidence", "high")
            if confidence not in _VALID_CONFIDENCE:
                confidence = "high"
            result.append({
                "index":      int(item["index"]),
                "reason":     str(item.get("reason", "Non-debate segment")),
                "confidence": confidence,
            })
        elif isinstance(item, (int, float)):
            result.append({
                "index":      int(item),
                "reason":     "Non-debate segment",
                "confidence": "high",
            })
    return result


def _call_model(user_msg: str, client: anthropic.Anthropic) -> list[dict]:
    """Make one detection call and return parsed results (empty list on failure)."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        return _parse_response(raw)
    except json.JSONDecodeError as exc:
        logger.warning("OOS JSON parse error: %s", exc)
    except Exception as exc:
        logger.warning("OOS model call failed: %s", exc)
    return []

# ── Sub-utterance patch system prompt ────────────────────────────────────────

_PATCH_SYSTEM = (
    "You are cleaning a debate transcript. The utterance you receive contains both "
    "debate content and a non-debate segment that has already been identified. "
    "Your task: remove only the non-debate sentences, preserving every debate "
    "sentence exactly as-is — do not paraphrase, summarise, reorder, or add text. "
    "Return only the cleaned utterance text. "
    "No commentary, no ellipsis markers where content was removed, no formatting. "
    "If the entire utterance is non-debate, return an empty string."
)

# ── Public API ────────────────────────────────────────────────────────────────

def propose_utterance_patch(
    utterance_text: str,
    reason: str,
    motion: str = "",
    api_key: str = "",
) -> str | None:
    """
    Given an utterance that contains mixed debate and non-debate content,
    return a cleaned version with only the non-debate sentences removed.

    Uses Claude Sonnet (same tier as the detection scan) so the model has
    sufficient context to make sentence-level decisions reliably.

    Returns the cleaned text string, or None on any failure.
    The caller should show the result as a proposal and let the user
    accept or discard it — never apply silently.
    """
    motion_line = f"Debate topic: {motion}\n" if motion.strip() else ""
    user_msg = (
        f"{motion_line}"
        f"Utterance to clean:\n{utterance_text}\n\n"
        f"Detected non-debate content: {reason}\n\n"
        f"Return the utterance with the non-debate sentences removed. "
        f"Keep all debate content verbatim."
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_PATCH_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        cleaned = response.content[0].text.strip()
        return cleaned if cleaned else None
    except Exception as exc:
        logger.warning("propose_utterance_patch failed: %s", exc)
        return None


def detect_out_of_scope_utterances(
    utterances: list[dict],
    motion: str = "",
    api_key: str = "",
) -> list[dict]:
    """
    Three-phase robust detection of non-debate utterances.

    Phase 1 — Chunked local scan (full text, no truncation):
        Processes _CHUNK_SIZE utterances at a time with complete text.
        Tight context window = sharp model attention = catches embedded
        intros/sponsors that fall in the middle of long utterances.
        Makes ceil(N / _CHUNK_SIZE) API calls.

    Phase 2 — Global scan (head+tail truncation):
        Sends the entire transcript in one call to catch repeated teaser
        clips and patterns that require cross-utterance comparison.
        Makes 1 API call.

    Phase 3 — Structural teaser propagation (zero API calls):
        Finds the earliest utterance flagged as a podcast intro by
        Phases 1–2. Every utterance before it is structurally a teaser
        clip (podcast highlight preview placed before the show starts)
        and is flagged automatically. Existing reasons are not overwritten
        so users see accurate labels for items already caught above.

    Results from all phases are merged (Phase 1 reasons take priority).
    Returns a list of {"index": int, "reason": str} dicts, sorted by index.
    """
    client = anthropic.Anthropic(api_key=api_key)
    motion_line = f"Debate topic: {motion}\n" if motion.strip() else ""
    found: dict[int, dict] = {}  # index → {index, reason}

    # ── Phase 1: chunked local scan (full text) ───────────────────────────
    for chunk_start in range(0, len(utterances), _CHUNK_SIZE):
        chunk = utterances[chunk_start: chunk_start + _CHUNK_SIZE]
        lines = "\n".join(
            _render_full(chunk_start + j, u) for j, u in enumerate(chunk)
        )
        user_msg = (
            f"{motion_line}"
            f"Transcript chunk — indices {chunk_start} to "
            f"{chunk_start + len(chunk) - 1} (full text, no truncation):\n"
            f"{lines}"
        )
        for r in _call_model(user_msg, client):
            found[r["index"]] = r  # Phase 1 results take priority

    # ── Phase 2: global scan (truncated) for teaser/cross-utterance patterns
    global_lines = "\n".join(
        _render_truncated(i, u) for i, u in enumerate(utterances)
    )
    user_msg_global = (
        f"{motion_line}"
        f"Full transcript (long utterances truncated — focus on teaser clips "
        f"and cross-utterance patterns):\n"
        f"{global_lines}"
    )
    for r in _call_model(user_msg_global, client):
        if r["index"] not in found:  # don't overwrite Phase 1 reasons
            found[r["index"]] = r

    # ── Phase 3: structural teaser propagation ────────────────────────────
    # Podcast teasers always appear BEFORE the intro segment. Once we know
    # which utterance is the intro, everything before it is a teaser by
    # definition — no model call needed.
    intro_indices = [
        r["index"] for r in found.values()
        if "intro" in r["reason"].lower()
    ]
    if intro_indices:
        intro_idx = min(intro_indices)
        for i in range(intro_idx):
            if i not in found:
                found[i] = {
                    "index":  i,
                    "reason": (
                        f"Teaser clip: appears before the detected intro "
                        f"segment (utterance {intro_idx})"
                    ),
                }
            # If already flagged for another reason, keep that reason.

    return sorted(found.values(), key=lambda x: x["index"])
