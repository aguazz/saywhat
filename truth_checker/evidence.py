import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

_WIKI_TIMEOUT = 8
_DDG_TIMEOUT  = 6
_SS_TIMEOUT   = 12


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------

def _wiki_base(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def _wiki_search(query: str, lang: str) -> list[str]:
    """Return up to 3 page titles matching the query."""
    try:
        r = requests.get(
            _wiki_base(lang),
            params={
                "action":   "query",
                "list":     "search",
                "srsearch": query,
                "srlimit":  3,
                "format":   "json",
            },
            timeout=_WIKI_TIMEOUT,
        )
        r.raise_for_status()
        return [item["title"] for item in r.json().get("query", {}).get("search", [])]
    except Exception as exc:
        logger.warning("Wikipedia search failed (%s, %s): %s", lang, query, exc)
        return []


def _wiki_extract(title: str, lang: str) -> dict | None:
    """Fetch the introductory extract for a Wikipedia page (up to 600 chars)."""
    try:
        r = requests.get(
            _wiki_base(lang),
            params={
                "action":      "query",
                "prop":        "extracts",
                "exintro":     True,
                "explaintext": True,
                "titles":      title,
                "format":      "json",
            },
            timeout=_WIKI_TIMEOUT,
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if int(page_id) < 0:
                return None
            extract = (page.get("extract") or "").strip()
            if not extract:
                return None
            url = f"https://{lang}.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}"
            return {
                "title":   page["title"],
                "snippet": extract[:600],
                "url":     url,
                "source":  "wikipedia",
            }
    except Exception as exc:
        logger.warning("Wikipedia extract failed (%s, %s): %s", lang, title, exc)
    return None


def _fetch_wikipedia(query: str, language: str) -> list[dict]:
    """Query Wikipedia in the debate language, then English fallback. Returns up to 2 pages."""
    results: list[dict] = []
    for lang in ([language, "en"] if language != "en" else ["en"]):
        titles = _wiki_search(query, lang)
        for title in titles[:2]:        # top 2 results (was 1)
            item = _wiki_extract(title, lang)
            if item:
                results.append(item)
        if results:
            break
    return results


# ---------------------------------------------------------------------------
# DuckDuckGo Instant Answer  (free, no API key)
# ---------------------------------------------------------------------------

def _fetch_duckduckgo(query: str) -> list[dict]:
    """
    Query the DuckDuckGo Zero-Click / Instant Answer API.

    Returns curated topic summaries (often Wikipedia-backed but formatted
    differently, and catches answers the Wikipedia search misses).
    Free — no API key required.
    """
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q":           query,
                "format":      "json",
                "no_redirect": 1,
                "no_html":     1,
                "skip_disambig": 1,
            },
            timeout=_DDG_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.warning("DuckDuckGo search failed (%s): %s", query, exc)
        return []

    results = []
    # Main abstract — most useful result
    if data.get("AbstractText") and data.get("AbstractURL"):
        results.append({
            "title":   data.get("Heading") or query,
            "snippet": data["AbstractText"][:600],
            "url":     data["AbstractURL"],
            "source":  "duckduckgo",
        })
    # Direct computed answer (e.g. unit conversions, simple facts)
    if data.get("Answer"):
        answer_text = str(data["Answer"])
        if len(answer_text) > 20:   # skip trivially short answers
            results.append({
                "title":   f"Quick answer: {query[:60]}",
                "snippet": answer_text[:400],
                "url":     data.get("AnswerURL") or "",
                "source":  "duckduckgo",
            })
    return results[:2]


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

def _fetch_semantic_scholar(query: str, max_results: int) -> list[dict]:
    """Search Semantic Scholar for peer-reviewed papers."""
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query":  query,
                "fields": "title,year,citationCount,abstract,paperId",
                "limit":  max_results + 5,
            },
            timeout=_SS_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as exc:
        logger.warning("Semantic Scholar search failed (%s): %s", query, exc)
        return []

    results = []
    for paper in data:
        if paper.get("citationCount", 0) < 2:   # lowered from 5 — catches newer/niche work
            continue
        abstract = paper.get("abstract") or ""
        if not abstract:
            continue
        results.append({
            "title":          paper.get("title", ""),
            "snippet":        abstract[:600],    # was 400
            "url":            f"https://semanticscholar.org/paper/{paper.get('paperId', '')}",
            "year":           paper.get("year"),
            "citation_count": paper.get("citationCount", 0),
            "source":         "semantic_scholar",
        })

    return results[:max_results]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_evidence(
    suggested_query: str,
    language: str = "es",
    max_results: int = 8,
) -> list[dict]:
    """
    Retrieve external evidence for a factual claim from three free sources:
      - Wikipedia (up to 2 pages in the debate language, then English)
      - DuckDuckGo Instant Answer (curated topic summaries, no key needed)
      - Semantic Scholar (peer-reviewed paper abstracts)

    All three are fetched in parallel to minimise latency.
    Returns up to max_results dicts, deduplicated by title (case-insensitive).
    Returns [] only if all three sources fail or return nothing.
    """
    if not suggested_query or not suggested_query.strip():
        return []

    fetchers = {
        "wiki": lambda: _fetch_wikipedia(suggested_query, language),
        "ddg":  lambda: _fetch_duckduckgo(suggested_query),
        "ss":   lambda: _fetch_semantic_scholar(suggested_query, max_results),
    }

    all_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn): name for name, fn in fetchers.items()}
        for future in as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception as exc:
                logger.warning("Evidence fetcher %s raised: %s", futures[future], exc)

    # Deduplicate by title and cap at max_results
    seen: set[str] = set()
    merged: list[dict] = []
    # Prioritise Wikipedia and DDG (encyclopedic) over academic papers
    source_order = {"wikipedia": 0, "duckduckgo": 1, "semantic_scholar": 2}
    all_results.sort(key=lambda x: source_order.get(x.get("source", ""), 3))

    for item in all_results:
        key = item["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= max_results:
            break

    return merged
