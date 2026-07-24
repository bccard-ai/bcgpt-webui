"""Serply.io SERP proxy API integration.

Wraps the Serply.io API to provide Google search results via a SERP proxy.
Supports localization, device type simulation, and proxy location settings.

API Documentation:
    https://serply.io
"""

import logging
from typing import Optional
from urllib.parse import urlencode

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

SERPLY_URL = "https://api.serply.io/v1/search/"


def search_serply(
    api_key: str,
    query: str,
    count: int,
    hl: str = "us",
    limit: int = 10,
    device_type: str = "desktop",
    proxy_location: str = "US",
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Serply.io's SERP proxy API.

    Args:
        api_key: A Serply.io API key (passed as ``X-API-KEY`` header).
        query: The search query string.
        count: Maximum number of results to return after filtering.
        hl: Host language code for result localization
            (see Google language codes). Defaults to ``"us"``.
        limit: Number of results to request from the API (10–100).
            Defaults to 10.
        device_type: Device type to simulate (``"desktop"`` or ``"mobile"``).
            Defaults to ``"desktop"``.
        proxy_location: Geographic proxy location (e.g. ``"US"``, ``"KR"``).
            Defaults to ``"US"``.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects sorted by ``realPosition``
        with *link*, *title*, and *snippet* fields. The *snippet* is sourced
        from the ``description`` field in the Serply response.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    query_params = {
        "q": query,
        "language": "en",
        "num": limit,
        "gl": proxy_location.upper(),
        "hl": hl.lower(),
    }

    url = f"{SERPLY_URL}{urlencode(query_params)}"
    headers = {
        "X-API-KEY": api_key,
        "X-User-Agent": device_type,
        "User-Agent": "bcgpt",
        "X-Proxy-Location": proxy_location,
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    json_response = response.json()
    log.info("Serply response: %s", json_response)

    results = sorted(
        json_response.get("results", []),
        key=lambda x: x.get("realPosition", 0),
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
