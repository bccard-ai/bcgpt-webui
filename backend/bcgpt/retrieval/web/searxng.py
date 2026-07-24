"""SearXNG meta-search engine integration.

Wraps a self-hosted SearXNG instance to aggregate results from multiple
search engines. Results are sorted by SearXNG relevance score in
descending order.

Project:
    https://github.com/searxng/searxng
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def search_searxng(
    query_url: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
    **kwargs,
) -> list[SearchResult]:
    """Search a SearXNG instance and return results sorted by relevance.

    Args:
        query_url: The base URL of the SearXNG server
            (e.g. ``"http://localhost:8080/search"``).
            Legacy ``<query>`` placeholders in the URL are stripped
            automatically.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Keyword Args:
        language: Language filter (e.g. ``"en-US"``). Defaults to ``"en-US"``.
        safesearch: Safe-search level (0=off, 1=moderate, 2=strict).
            Defaults to ``1``.
        time_range: Date filter (e.g. ``"2023-04-05..today"``). Defaults to
            empty string.
        categories: Category filter as a list of strings
            (e.g. ``["general", "news"]``). Defaults to empty.

    Returns:
        A list of :class:`SearchResult` objects sorted by SearXNG relevance
        score in descending order.

    Raises:
        requests.HTTPError: If the request to the SearXNG instance fails.
    """
    language = kwargs.get("language", "en-US")
    safesearch = kwargs.get("safesearch", "1")
    time_range = kwargs.get("time_range", "")
    categories = "".join(kwargs.get("categories", []))

    params = {
        "q": query,
        "format": "json",
        "pageno": 1,
        "safesearch": safesearch,
        "language": language,
        "time_range": time_range,
        "categories": categories,
        "theme": "simple",
        "image_proxy": 0,
    }

    # Strip legacy <query> placeholder and query parameters from URL
    if "<query>" in query_url:
        query_url = query_url.split("?")[0]

    log.debug("Searching SearXNG at %s", query_url)

    response = requests.get(
        query_url,
        headers={
            "User-Agent": (
                "BCGPT (https://github.com/bccard-ai/bcgpt-webui) RAG Bot"
            ),
            "Accept": "text/html",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        },
        params=params,
    )
    response.raise_for_status()

    json_response = response.json()
    results = json_response.get("results", [])
    sorted_results = sorted(
        results, key=lambda x: x.get("score", 0), reverse=True
    )

    if filter_list:
        sorted_results = get_filtered_results(sorted_results, filter_list)

    return [
        SearchResult(
            link=result["url"],
            title=result.get("title"),
            snippet=result.get("content"),
        )
        for result in sorted_results[:count]
    ]
