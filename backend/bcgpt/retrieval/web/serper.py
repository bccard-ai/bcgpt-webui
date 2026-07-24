"""Serper.dev Google SERP API integration.

Wraps the Serper.dev API to provide fast Google search results sorted by
SERP position.

API Documentation:
    https://serper.dev
"""

import json
import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

SERPER_URL = "https://google.serper.dev/search"


def search_serper(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Serper.dev's Google SERP API.

    Args:
        api_key: A Serper.dev API key (passed as ``X-API-KEY`` header).
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects sorted by SERP position with
        *link*, *title*, and *snippet* fields. The *snippet* is sourced from
        the ``description`` field in the Serper response.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    payload = json.dumps({"q": query})
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

    response = requests.post(SERPER_URL, headers=headers, data=payload)
    response.raise_for_status()

    json_response = response.json()
    results = sorted(
        json_response.get("organic", []),
        key=lambda x: x.get("position", 0),
    )

    if filter_list:
        results = get_filtered_results(results, filter_list)

    return [
        SearchResult(
            link=result["link"],
            title=result.get("title"),
            snippet=result.get("description"),
        )
        for result in results[:count]
    ]
