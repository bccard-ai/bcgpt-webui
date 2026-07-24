"""Tavily Search API integration.

Wraps the Tavily AI research search API to provide structured search
results optimized for AI and RAG workloads.

API Documentation:
    https://docs.tavily.com
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def search_tavily(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Tavily's AI-optimized search API.

    Args:
        api_key: A Tavily API key.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Unused placeholder for API consistency. Tavily
            does not support domain filtering natively.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields. The *snippet* is populated with the ``content``
        field from the Tavily response.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    payload = {"query": query, "api_key": api_key}

    response = requests.post(TAVILY_SEARCH_URL, json=payload)
    response.raise_for_status()

    raw_results = response.json().get("results", [])

    return [
        SearchResult(
            link=result["url"],
            title=result.get("title", ""),
            snippet=result.get("content"),
        )
        for result in raw_results[:count]
    ]
