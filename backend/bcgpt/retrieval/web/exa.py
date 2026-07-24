"""Exa (formerly Metaphor) Search API integration.

Wraps the Exa semantic search API which supports both keyword and neural
search modes. Exa returns full text content and highlights for each result.

API Documentation:
    https://docs.exa.ai
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

EXA_API_BASE = "https://api.exa.ai"


@dataclass
class ExaResult:
    """Intermediate container for a single Exa search result."""

    url: str
    title: str
    text: str


def search_exa(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Exa's semantic search API (auto keyword/neural mode).

    Args:
        api_key: An Exa API key.
        query: The search query string.
        count: Maximum number of results to return. Defaults to 5 when zero.
        filter_list: Optional list of domains passed as ``includeDomains``
            to restrict results.

    Returns:
        A list of :class:`SearchResult` objects with *link*, *title*, and
        *snippet* fields. The *snippet* is populated with the full text
        content returned by Exa. Returns an empty list on error.
    """
    log.info("Searching with Exa for query: %s", query)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "numResults": count or 5,
        "includeDomains": filter_list,
        "contents": {"text": True, "highlights": True},
        "type": "auto",
    }

    try:
        response = requests.post(
            f"{EXA_API_BASE}/search", headers=headers, json=payload
        )
        response.raise_for_status()
        data = response.json()

        exa_results = [
            ExaResult(
                url=item["url"],
                title=item["title"],
                text=item["text"],
            )
            for item in data["results"]
        ]

        log.info("Found %d Exa results", len(exa_results))
        return [
            SearchResult(
                link=result.url,
                title=result.title,
                snippet=result.text,
            )
            for result in exa_results
        ]
    except Exception as exc:
        log.error("Exa search failed: %s", exc)
        return []
