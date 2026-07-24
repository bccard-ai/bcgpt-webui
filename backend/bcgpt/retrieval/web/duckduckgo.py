"""DuckDuckGo Search integration.

Wraps the ``ddgs`` library to provide privacy-focused web search results
without requiring an API key.

Library:
    ddgs (DuckDuckGo Search)
"""

import logging
from typing import Optional

from ddgs import DDGS

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def search_duckduckgo(
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using DuckDuckGo (no API key required).

    Args:
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields. The *link* is sourced from ``href``, the *snippet*
        from ``body`` in the DuckDuckGo response.
    """
    search_results: list[dict] = []
    with DDGS() as ddgs:
        ddgs_gen = ddgs.text(
            query, safesearch="moderate", max_results=count, backend="api"
        )
        if ddgs_gen:
            search_results = list(ddgs_gen)

    if filter_list:
        search_results = get_filtered_results(search_results, filter_list)

    return [
        SearchResult(
            link=result["href"],
            title=result.get("title"),
            snippet=result.get("body"),
        )
        for result in search_results
    ]
