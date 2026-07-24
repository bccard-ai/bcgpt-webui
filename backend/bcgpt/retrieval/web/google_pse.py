"""Google Programmable Search Engine (PSE) API integration.

Wraps the Google Custom Search JSON API to provide structured web search
results. Handles pagination automatically when the requested result count
exceeds 10 (the per-page maximum).

API Documentation:
    https://developers.google.com/custom-search/v1/overview
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

GOOGLE_PSE_URL = "https://www.googleapis.com/customsearch/v1"
GOOGLE_PSE_MAX_PER_PAGE = 10


def search_google_pse(
    api_key: str,
    search_engine_id: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Google's Programmable Search Engine API.

    Automatically paginates when *count* exceeds 10 (the PSE per-page
    maximum). Up to 100 results can be retrieved (10 pages × 10 results).

    Args:
        api_key: A Google Programmable Search Engine API key.
        search_engine_id: The Programmable Search Engine ID (``cx`` parameter).
        query: The search query string.
        count: Total number of results to return. Values above 10 trigger
            automatic pagination.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    headers = {"Content-Type": "application/json"}
    all_results: list[dict] = []
    start_index = 1  # Google PSE ``start`` is 1-based
    remaining = count

    while remaining > 0:
        page_size = min(remaining, GOOGLE_PSE_MAX_PER_PAGE)
        params = {
            "cx": search_engine_id,
            "q": query,
            "key": api_key,
            "num": page_size,
            "start": start_index,
        }

        response = requests.get(GOOGLE_PSE_URL, headers=headers, params=params)
        response.raise_for_status()

        page_results = response.json().get("items", [])
        if not page_results:
            break

        all_results.extend(page_results)
        remaining -= len(page_results)
        start_index += GOOGLE_PSE_MAX_PER_PAGE

    if filter_list:
        all_results = get_filtered_results(all_results, filter_list)

    return [
        SearchResult(
            link=result["link"],
            title=result.get("title"),
            snippet=result.get("snippet"),
        )
        for result in all_results
    ]
