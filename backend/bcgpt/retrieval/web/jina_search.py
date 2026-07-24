"""Jina Search API integration.

Wraps the Jina AI search endpoint (``s.jina.ai``) to provide neural
search results with AI-generated content summaries.

API Documentation:
    https://jina.ai/search/
"""

import logging

import requests
from yarl import URL

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

JINA_SEARCH_URL = "https://s.jina.ai/"
JINA_MAX_COUNT = 10


def search_jina(api_key: str, query: str, count: int) -> list[SearchResult]:
    """Search using Jina's neural search API.

    Args:
        api_key: A Jina API key (passed as the ``Authorization`` header).
        query: The search query string.
        count: Maximum number of results to return. Capped at 10.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields. The *snippet* is populated with the full content
        returned by Jina.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": api_key,
        "X-Retain-Images": "none",
    }
    payload = {"q": query, "count": min(count, JINA_MAX_COUNT)}

    url = str(URL(JINA_SEARCH_URL))
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    data = response.json()
    results = [
        SearchResult(
            link=item["url"],
            title=item.get("title"),
            snippet=item.get("content"),
        )
        for item in data.get("data", [])
    ]

    return results
