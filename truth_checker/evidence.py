import logging
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 1  # seconds per request


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------

def _wiki_base(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def _wiki_search(query: str, lang: str) -> list[str]:
    """Return a list of page titles matching the query (up to 3)."""
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
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return [item["title"] for item in r.json().get("query", {}).get("search", [])]
    except Exception as exc:
        logger.warning("Wikipedia search failed (%s, %s): %s", lang, query, exc)
        return []


def _wiki_extract(title: str, lang: str) -> dict | None:
    """Fetch the introductory extract for a Wikipedia page title."""
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
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        # Pages is keyed by page_id; negative IDs mean the page was not found
        for page_id, page in pages.items():
            if int(page_id) < 0:
                return None
            extract = (page.get("extract") or "").strip()
            if not extract:
                return None
            url = f"https://{lang}.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}"
            return {
                "title":   page["title"],
                "snippet": extract[:400],
                "url":     url,
                "source":  "wikipedia",
            }
    except Exception as exc:
        logger.warning("Wikipedia extract failed (%s, %s): %s", lang, title, exc)
    return None


def _fetch_wikipedia(query: str, language: str) -> list[dict]:
    """Query Wikipedia (primary language, then English fallback)."""
    results: list[dict] = []

    for lang in ([language, "en"] if language != "en" else ["en"]):
        titles = _wiki_search(query, lang)
        for title in titles[:1]:   # only top result gets a full extract
            item = _wiki_extract(title, lang)
            if item:
                results.append(item)
        if results:
            break   # stop at first language that returns something

    return results


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

def _fetch_semantic_scholar(query: str, max_results: int) -> list[dict]:
    """Search Semantic Scholar and return filtered paper dicts."""
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query":  query,
                "fields": "title,year,citationCount,abstract,paperId",
                "limit":  max_results + 5,   # fetch extra to survive filtering
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as exc:
        logger.warning("Semantic Scholar search failed (%s): %s", query, exc)
        return []

    results = []
    for paper in data:
        if paper.get("citationCount", 0) < 5:
            continue
        abstract = paper.get("abstract") or ""
        if not abstract:
            continue
        results.append({
            "title":          paper.get("title", ""),
            "snippet":        abstract[:400],
            "url":            f"https://semanticscholar.org/paper/{paper.get('paperId', '')}",
            "year":           paper.get("year"),
            "citation_count": paper.get("citationCount", 0),
            "source":         "semantic_scholar",
        })

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_evidence(
    suggested_query: str,
    language: str = "es",
    max_results: int = 5,
) -> list[dict]:
    """
    Retrieve external evidence for a factual claim from Wikipedia and Semantic Scholar.

    Wikipedia is queried first in the debate's language; falls back to English if
    the primary-language search returns nothing. Semantic Scholar is always queried
    in English (where coverage is highest).

    Returns up to max_results dicts, deduplicated by title (case-insensitive).
    Returns [] if both APIs fail or produce no usable results.
    """
    if not suggested_query or not suggested_query.strip():
        return []

    wiki_results = _fetch_wikipedia(suggested_query, language)
    ss_results   = _fetch_semantic_scholar(suggested_query, max_results)

    # Merge: Wikipedia first, then Semantic Scholar
    seen: set[str] = set()
    merged: list[dict] = []
    for item in wiki_results + ss_results:
        key = item["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= max_results:
            break

    return merged
