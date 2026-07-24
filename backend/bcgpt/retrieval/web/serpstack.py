"""Serpstack Google SERP API integration.

Wraps the Serpstack API to provide Google search results sorted by
position. Supports optional HTTPS toggle for free-tier compatibility.

API Documentation:
    https://serpstack.com/documentation
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def search_serpstack(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
    https_enabled: bool = True,
) -> list[SearchResult]:
    """Search using Serpstack's Google SERP API.

    Args:
        api_key: A Serpstack API key (passed as ``access_key`` parameter).
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.
        https_enabled: Whether to use HTTPS for the API request. Set to
            ``False`` when using the free tier which only supports HTTP.
            Defaults to ``True``.

    Returns:
        A list of :class:`SearchResult` objects sorted by position with
        *link*, *title*, and *snippet* fields.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    scheme = "https" if https_enabled else "http"
    url = f"{scheme}://api.serpstack.com/search"

    headers = {"Content-Type": "application/json"}
    params = {"access_key": api_key, "query": query}

    response = requests.post(url, headers=headers, params=params)
    response.raise_for_status()

    json_response = response.json()
    results = sorted(
        json_response.get("organic_results", []),
        key=lambda x: x.get("position", 0),
    )

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
