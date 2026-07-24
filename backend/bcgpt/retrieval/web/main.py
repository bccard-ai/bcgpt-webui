"""Web search result types and domain filtering utilities.

This module defines the shared :class:`SearchResult` data model used by all
search provider modules and the :func:`get_filtered_results` helper that
restricts results to a whitelist of domain suffixes.
"""

from typing import Optional
from urllib.parse import urlparse

import validators
from pydantic import BaseModel


def get_filtered_results(
    results: list[dict],
    filter_list: list[str],
) -> list[dict]:
    """Filter search results to only include matching domains.

    Each result dict is expected to have either a ``"url"`` or ``"link"``
    key containing the result URL. Results whose URL's registered domain
    ends with one of the entries in *filter_list* are kept.

    Args:
        results: Raw result dicts from a search provider response.
        filter_list: Domain suffixes to allow (e.g. ``["example.com"]``).

    Returns:
        The subset of *results* whose domain matches at least one entry
        in *filter_list*.
    """
    if not filter_list:
        return results

    filtered: list[dict] = []
    for result in results:
        url = result.get("url") or result.get("link", "")
        if not validators.url(url):
            continue
        domain = urlparse(url).netloc
        if any(domain.endswith(allowed) for allowed in filter_list):
            filtered.append(result)
    return filtered


class SearchResult(BaseModel):
    """A single web search result returned by any search provider.

    Attributes:
        link: The URL of the search result.
        title: The title of the result page (may be ``None``).
        snippet: A short text excerpt from the result page (may be ``None``).
    """

    link: str
    title: Optional[str] = None
    snippet: Optional[str] = None
