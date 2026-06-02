import json
import logging

import anthropic

logger = logging.getLogger(__name__)

# Characters shown from the start and end of each long utterance.
# Showing both ends lets the model see embedded intros/sponsors that begin
# after a speaker finishes a debate point mid-utterance.
_HEAD_CHARS = 300
_TAIL_CHARS = 200

_SYSTEM = (
    "You are reviewing a debate transcript to identify utterances that contain "
    "non-debate content and should be excluded from argument analysis.\n\n"

    "CRITICAL: A single utterance can contain BOTH legitimate debate content AND "
    "non-debate content. This happens when a host finishes a debate point and then "
    "pivots to a podcast intro, a sponsor read, or an outro — all within the same "
    "turn. You MUST flag such utterances even when they also contain debate content. "
    "Look at the FULL text of each utterance, not just its opening words.\n\n"

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
    "    {\"index\": <integer>, \"reason\": \"<one concise sentence explaining why>\"},\n"
    "    ...\n"
    "  ]\n"
    "}\n\n"
    "The reason must name the specific category (e.g. 'Podcast intro', 'Sponsor read', "
    "'Outro sign-off', 'Teaser clip') and quote a short phrase from the utterance that "
    "triggered the detection.\n"
    "If nothing should be excluded, return { \"out_of_scope\": [] }. "
    "Return only valid JSON. No markdown fences."
)


def _render_utterance(i: int, u: dict) -> str:
    """
    Render one utterance for the detection prompt.

    For long utterances we show the head and the tail so the model can see
    content that is embedded mid-turn (e.g. a sponsor read that starts after
    a debate point within the same utterance).
    """
    text = u.get("text", "").strip()
    speaker = u.get("speaker", "?")

    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return f"[{i}] {speaker}: {text}"

    head = text[:_HEAD_CHARS]
    tail = text[-_TAIL_CHARS:]
    return f"[{i}] {speaker}: {head} […] {tail}"


def detect_out_of_scope_utterances(
    utterances: list[dict],
    motion: str = "",
    api_key: str = "",
) -> list[dict]:
    """
    Returns a list of dicts: [{"index": int, "reason": str}, …]
    for every utterance that should be excluded from analysis.
    """
    transcript_text = "\n".join(
        _render_utterance(i, u) for i, u in enumerate(utterances)
    )
    motion_line = f"Debate topic: {motion}\n" if motion.strip() else ""
    user_msg = f"{motion_line}Transcript (index: speaker: text):\n{transcript_text}"

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        logger.warning("Claude API error detecting out-of-scope utterances: %s", exc)
        return []

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        items = data.get("out_of_scope", [])
        if not isinstance(items, list):
            raise ValueError("out_of_scope must be a list")
        result = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("index"), (int, float)):
                result.append({
                    "index":  int(item["index"]),
                    "reason": str(item.get("reason", "Non-debate segment")),
                })
            elif isinstance(item, (int, float)):
                # backward-compat: plain integer with no reason
                result.append({"index": int(item), "reason": "Non-debate segment"})
        return result
    except Exception as exc:
        logger.warning(
            "JSON parse error detecting out-of-scope utterances: %s — raw: %.120s",
            exc, raw,
        )
        return []
