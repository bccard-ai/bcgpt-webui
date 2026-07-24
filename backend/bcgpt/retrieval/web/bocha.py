"""Bocha AI Web Search API integration.

Wraps the Bocha (BochaAI) web search endpoint to provide structured search
results with AI-generated summaries. Bocha is optimized for the Chinese market
and supports fresh result retrieval.

API Documentation:
    https://bochaai.com
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

BOCHA_SEARCH_URL = "https://api.bochaai.com/v1/web-search?utm_source=ollama"


def _parse_response(response: dict) -> dict:
    """Extract web page results from the Bocha API response.

    Args:
        response: Raw JSON response from the Bocha API.

    Returns:
        A dict with a ``"webpage"`` key containing a list of result dicts.
        Each dict has keys: ``id``, ``name``, ``url``, ``snippet``,
        ``summary``, ``siteName``, ``siteIcon``, ``datePublished``.
    """
    result: dict = {}
    if "data" not in response:
        return result

    data = response["data"]
    if "webPages" not in data:
        return result

    web_pages = data["webPages"]
    if "value" not in web_pages:
        return result

    result["webpage"] = [
        {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", ""),
            "summary": item.get("summary", ""),
            "siteName": item.get("siteName", ""),
            "siteIcon": item.get("siteIcon", ""),
            "datePublished": item.get("datePublished", "")
            or item.get("dateLastCrawled", ""),
        }
        for item in web_pages["value"]
    ]
    return result


def search_bocha(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Bocha's AI-powered search API.

    Args:
        api_key: A Bocha Search API key.
        query: The search query string.
        count: Maximum number of results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects. The *snippet* field is
        populated with the AI-generated summary when available.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "summary": True,
        "freshness": "noLimit",
        "count": count,
    }

    response = requests.post(
        BOCHA_SEARCH_URL, headers=headers, json=payload, timeout=5
    )
    response.raise_for_status()

    parsed = _parse_response(response.json())
    log.debug("Bocha search results: %s", parsed)

    results = parsed.get("webpage", [])
    if filter_list:
        results = get_filtered_results(results, filter_list)

    return [
        SearchResult(
            link=result["url"],
            title=result.get("name"),
            snippet=result.get("summary"),
        )
        for result in results[:count]
    ]
