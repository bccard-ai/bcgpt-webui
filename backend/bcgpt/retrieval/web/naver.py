import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
from bcgpt.retrieval import SearchResult, get_filtered_results
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def _clean_naver_text(text: str) -> str:
    """Remove <b> tags Naver wraps around matching keywords."""
    return re.sub(r"</?b>", "", text)


def _search_single_endpoint(
    client_id, client_secret, endpoint, query, display, sort="sim"
):
    """Search a single Naver API endpoint."""
    url = f"https://openapi.naver.com/v1/search/{endpoint}.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query, "display": min(display, 100), "sort": sort}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("items", [])


def _summarize_errors(errors: list[tuple[str, Exception]]) -> str:
    error_messages = [str(error) or error.__class__.__name__ for _, error in errors]
    error_counts = Counter(error_messages)
    return error_counts.most_common(1)[0][0]


def search_naver(
    client_id: str,
    client_secret: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
    endpoints: Optional[str] = "webkr",
) -> list[SearchResult]:
    """Search using Naver's Search API and return the results as a list of SearchResult objects.

    Args:
        client_id (str): A Naver API client ID
        client_secret (str): A Naver API client secret
        query (str): The query to search for
        count (int): Number of results to return
        filter_list (Optional[list[str]]): Domain filter list
        endpoints (Optional[str]): Comma-separated endpoints to search (e.g. "webkr,news,blog")
    """
    endpoint_list = [e.strip() for e in (endpoints or "webkr").split(",") if e.strip()]
    if not endpoint_list:
        endpoint_list = ["webkr"]

    per_endpoint_count = max(1, count // len(endpoint_list))

    all_items = []
    errors: list[tuple[str, Exception]] = []
    with ThreadPoolExecutor(max_workers=len(endpoint_list)) as executor:
        futures = {
            executor.submit(
                _search_single_endpoint,
                client_id,
                client_secret,
                endpoint,
                query,
                per_endpoint_count,
            ): endpoint
            for endpoint in endpoint_list
        }
        for future in as_completed(futures):
            endpoint = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as e:
                errors.append((endpoint, e))

    if errors:
        failed_endpoints = ", ".join(endpoint for endpoint, _ in errors)
        summary = _summarize_errors(errors)

        if len(errors) == len(endpoint_list):
            raise RuntimeError(
                "Naver search failed for all endpoints "
                f"({failed_endpoints}): {summary}"
            )

        if not all_items:
            raise RuntimeError(
                "Naver search returned no results after endpoint failures "
                f"({failed_endpoints}): {summary}"
            )

        log.warning(
            "Naver search failed on %s/%s endpoints (%s); continuing with %s raw results. Reason: %s",
            len(errors),
            len(endpoint_list),
            failed_endpoints,
            len(all_items),
            summary,
        )

    seen_links = set()
    unique_items = []
    for item in all_items:
        link = item.get("link", "")
        if link and link not in seen_links:
            seen_links.add(link)
            unique_items.append(item)

    if filter_list:
        unique_items = get_filtered_results(unique_items, filter_list)

    return [
        SearchResult(
            link=item["link"],
            title=_clean_naver_text(item.get("title", "")),
            snippet=_clean_naver_text(item.get("description", "")),
        )
        for item in unique_items[:count]
    ]
