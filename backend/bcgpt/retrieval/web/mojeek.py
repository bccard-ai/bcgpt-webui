"""Mojeek Search API integration.

Wraps the Mojeek independent search engine API. Mojeek maintains its own
web index and does not rely on third-party search results.

API Documentation:
    https://www.mojeek.com/support/api/search/
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

MOJEEK_SEARCH_URL = "https://api.mojeek.com/search"


def search_mojeek(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Mojeek's independent search index.

    Args:
        api_key: A Mojeek Search API key.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields. The *snippet* is sourced from the ``desc`` field
        in the Mojeek response.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    headers = {"Accept": "application/json"}
    params = {"q": query, "api_key": api_key, "fmt": "json", "t": count}

    response = requests.get(MOJEEK_SEARCH_URL, headers=headers, params=params)
    response.raise_for_status()

    json_response = response.json()
    results = json_response.get("response", {}).get("results", [])
    log.debug("Mojeek search results: %s", results)

    if filter_list:
        results = get_filtered_results(results, filter_list)

    return [
        SearchResult(
            link=result["url"],
            title=result.get("title"),
            snippet=result.get("desc"),
        )
        for result in results
    ]
