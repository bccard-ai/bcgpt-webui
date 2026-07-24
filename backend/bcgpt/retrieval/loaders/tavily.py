"""Tavily Extract API document loader.

A LangChain-compatible loader that retrieves web page content via
Tavily's Extract API and yields ``Document`` objects.  Supports
batch extraction of up to 20 URLs per API call.
"""

from __future__ import annotations

import logging
from typing import Iterator, List, Literal, Union

import requests
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

#: Maximum URLs per Tavily Extract API call.
_BATCH_SIZE = 20


class TavilyLoader(BaseLoader):
    """Extract web page content from URLs using the Tavily Extract API.

    Args:
        urls: One or more URLs to extract content from.
        api_key: Tavily API key.
        extract_depth: ``"basic"`` or ``"advanced"`` extraction depth.
            Advanced mode retrieves more data (tables, embedded content)
            at higher latency and cost.
        continue_on_failure: If ``True``, extraction errors are logged
            rather than raised.
    """

    def __init__(
        self,
        urls: Union[str, List[str]],
        api_key: str,
        extract_depth: Literal["basic", "advanced"] = "basic",
        continue_on_failure: bool = True,
    ) -> None:
        if not urls:
            raise ValueError("At least one URL must be provided.")

        self.api_key: str = api_key
        self.urls: List[str] = urls if isinstance(urls, list) else [urls]
        self.extract_depth: str = extract_depth
        self.continue_on_failure: bool = continue_on_failure
        self.api_url: str = "https://api.tavily.com/extract"

    def lazy_load(self) -> Iterator[Document]:
        """Extract and yield ``Document`` objects from each URL batch."""
        for i in range(0, len(self.urls), _BATCH_SIZE):
            batch = self.urls[i : i + _BATCH_SIZE]
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                }
                # Tavily accepts a single string for one URL or a list for many.
                urls_param = batch[0] if len(batch) == 1 else batch
                payload = {"urls": urls_param, "extract_depth": self.extract_depth}

                response = requests.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                for result in data.get("results", []):
                    url = result.get("url", "")
                    content = result.get("raw_content", "")
                    if not content:
                        log.warning("No content extracted from %s", url)
                        continue
                    yield Document(page_content=content, metadata={"source": url})

                for failed in data.get("failed_results", []):
                    url = failed.get("url", "")
                    error = failed.get("error", "Unknown error")
                    log.error("Failed to extract content from %s: %s", url, error)

            except Exception as exc:
                if self.continue_on_failure:
                    log.error("Error extracting content from batch %s: %s", batch, exc)
                else:
                    raise
