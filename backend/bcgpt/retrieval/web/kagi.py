"""Kagi Search API integration.

Wraps the Kagi premium search API. Results inherit the personalization and
snippet-length settings configured in the user's Kagi account.

API Documentation:
    https://help.kagi.com/kagi/api/search.html
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

KAGI_SEARCH_URL = "https://kagi.com/api/v0/search"


def search_kagi(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Kagi's premium search API.

    Only results of type ``t == 0`` (standard web results) are returned;
    other result types (news, videos, etc.) are filtered out.

    Args:
        api_key: A Kagi Search API key (passed as ``Bot <key>``).
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    headers = {"Authorization": f"Bot {api_key}"}
    params = {"q": query, "limit": count}

    response = requests.get(KAGI_SEARCH_URL, headers=headers, params=params)
    response.raise_for_status()

    json_response = response.json()
    search_data = json_response.get("data", [])

    results = [
        SearchResult(
            link=item["url"],
            title=item["title"],
            snippet=item.get("snippet"),
        )
        for item in search_data
        if item.get("t") == 0
    ]

    log.debug("Kagi search results: %s", results)

    if filter_list:
        results = get_filtered_results(results, filter_list)

    return results
