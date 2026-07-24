"""Bing Web Search API integration.

Wraps the Microsoft Bing Web Search API v7 to provide structured search results.
Each result contains a link, title, and snippet extracted from the API response.

API Documentation:
    https://docs.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def search_bing(
    subscription_key: str,
    endpoint: str,
    locale: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search Bing Web Search API and return structured results.

    Args:
        subscription_key: Azure Bing Search API subscription key
            (Ocp-Apim-Subscription-Key header value).
        endpoint: Bing Search API endpoint URL
            (e.g. ``https://api.bing.microsoft.com/v7.0/search``).
        locale: Market / locale code for result localization
            (e.g. ``"en-US"``, ``"ko-KR"``).
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields populated from the Bing ``webPages`` response.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    params = {"q": query, "mkt": locale, "count": count}
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        json_response = response.json()
        results = json_response.get("webPages", {}).get("value", [])

        if filter_list:
            results = get_filtered_results(results, filter_list)

        return [
            SearchResult(
                link=result["url"],
                title=result.get("name"),
                snippet=result.get("snippet"),
            )
            for result in results
        ]
    except Exception as ex:
        log.error("Bing search failed: %s", ex)
        raise
