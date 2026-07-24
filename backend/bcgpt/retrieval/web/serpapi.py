"""SerpApi integration.

Wraps the SerpApi (serpapi.com) structured Google SERP API to provide
search results sorted by position. Supports multiple search engines
through SerpApi's engine parameter.

API Documentation:
    https://serpapi.com/search-api
"""

import logging
from typing import Optional
from urllib.parse import urlencode

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

SERPAPI_URL = "https://serpapi.com/search"


def search_serpapi(
    api_key: str,
    engine: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using SerpApi's structured SERP API.

    Args:
        api_key: A SerpApi API key.
        engine: The search engine to query (e.g. ``"google"``, ``"bing"``).
            Defaults to ``"google"`` when empty.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects sorted by SERP position with
        *link*, *title*, and *snippet* fields.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    engine = engine or "google"
    payload = {"engine": engine, "q": query, "api_key": api_key}

    url = f"{SERPAPI_URL}?{urlencode(payload)}"
    response = requests.get(url)
    response.raise_for_status()

    json_response = response.json()
    log.info("SerpApi response: %s", json_response)

    results = sorted(
        json_response.get("organic_results", []),
        key=lambda x: x.get("position", 0),
    )

    if filter_list:
        results = get_filtered_results(results, filter_list)

    return [
        SearchResult(
            link=result["link"],
            title=result["title"],
            snippet=result["snippet"],
        )
        for result in results[:count]
    ]
