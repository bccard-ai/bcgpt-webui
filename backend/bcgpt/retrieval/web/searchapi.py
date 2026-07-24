"""SearchApi.io integration.

Wraps the SearchApi multi-engine API to provide structured search results
sorted by position. Supports Google, Bing, and other search backends.

API Documentation:
    https://www.searchapi.io/docs
"""

import logging
from typing import Optional
from urllib.parse import urlencode

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"


def search_searchapi(
    api_key: str,
    engine: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using searchapi.io's multi-engine API.

    Args:
        api_key: A searchapi.io API key.
        engine: The search engine to use (e.g. ``"google"``, ``"bing"``).
            Defaults to ``"google"`` when empty.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects sorted by position with
        *link*, *title*, and *snippet* fields.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    engine = engine or "google"
    payload = {"engine": engine, "q": query, "api_key": api_key}

    url = f"{SEARCHAPI_URL}?{urlencode(payload)}"
    response = requests.get(url)
    response.raise_for_status()

    json_response = response.json()
    log.info("SearchApi response: %s", json_response)

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
