"""Perplexity AI Search API integration.

Wraps the Perplexity ``sonar`` model chat completions endpoint to provide
AI-powered search results with citation URLs.

API Documentation:
    https://docs.perplexity.ai
"""

import logging
from typing import Optional

import requests

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval import SearchResult, get_filtered_results

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def search_perplexity(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Perplexity's AI-powered search API.

    Uses the ``sonar`` model to generate factual answers with citations.
    Citation URLs are returned as search results, with the AI-generated
    content attached as the snippet for the first citation.

    Args:
        api_key: A Perplexity API key.
        query: The search query string.
        count: Maximum number of citation results to return.
        filter_list: Optional list of domain suffixes to restrict results to.

    Returns:
        A list of :class:`SearchResult` objects where *link* is a citation
        URL and *snippet* contains the AI-generated answer content for the
        first result. Returns an empty list on error.
    """
    # Handle PersistentConfig objects that may wrap the API key
    if hasattr(api_key, "__str__"):
        api_key = str(api_key)

    try:
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a search assistant. "
                        "Provide factual information with citations."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers)
        json_response = response.json()

        citations = json_response.get("citations", [])
        content = ""
        choices = json_response.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        results = [
            {
                "link": citation,
                "title": f"Source {i + 1}",
                "snippet": content if i == 0 else "",
            }
            for i, citation in enumerate(citations[:count])
        ]

        if filter_list:
            results = get_filtered_results(results, filter_list)

        return [
            SearchResult(
                link=result["link"],
                title=result["title"],
                snippet=result["snippet"],
            )
            for result in results[:count]
        ]

    except Exception as exc:
        log.error("Perplexity search failed: %s", exc)
        return []
