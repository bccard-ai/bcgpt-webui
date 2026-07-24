"""Brave Search API integration.

Wraps the Brave Web Search API to provide privacy-focused search results.

API Documentation:
    https://api.search.brave.com/app/documentation
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def search_brave(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Brave's privacy-focused search API.

    Args:
        api_key: A Brave Search API subscription token.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields populated from the Brave ``web.results`` response.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": count}

    response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params)
    response.raise_for_status()

    json_response = response.json()
    results = json_response.get("web", {}).get("results", [])

    if filter_list:
        results = get_filtered_results(results, filter_list)

    return [
        SearchResult(
            link=result["url"],
            title=result.get("title"),
            snippet=result.get("snippet"),
        )
        for result in results[:count]
    ]
