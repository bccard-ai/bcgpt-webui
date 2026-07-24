"""API_CALL node: call an external HTTP API and capture its response.

Config::

    {
      "url": "https://...",
      "method": "GET" | "POST" | ...,
      "headers": {...},
      "params": {...},            # query string
      "json": {...},              # request body (JSON)
      "timeout": 30,
      "result_path": "data.items" # optional dot-path to extract from JSON
    }

Best-effort and bounded by timeout; failures surface as the node error so the
node's ``error_strategy`` decides what happens next.
"""

from __future__ import annotations

import logging
from typing import Any

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.retrieval.web.utils import validate_url
from bcgpt.utils.webhook import _is_webhook_url_safe
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

log = logging.getLogger(__name__)


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


class APICallHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        url = node.config.get("url")
        if not url:
            raise ValueError("API_CALL requires a 'url'")

        method = (node.config.get("method") or "GET").upper()
        headers = node.config.get("headers") or {}
        query = node.config.get("params") or {}
        body = node.config.get("json")
        timeout = float(node.config.get("timeout", 30))

        import aiohttp

        validate_url(url)

        if not _is_webhook_url_safe(url):
            raise ValueError(
                f"SSRF blocked: URL targets internal/private network: {url}"
            )

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            # SSRF: don't follow redirects — validate_url/_is_webhook_url_safe
            # above only checked the initial host, a 3xx could pivot internally.
            async with session.request(
                method,
                url,
                headers=headers,
                params=query,
                json=body,
                allow_redirects=False,
            ) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    payload: Any = await resp.json()
                else:
                    payload = await resp.text()

        result_path = node.config.get("result_path")
        extracted = _dig(payload, result_path) if result_path else payload
        return NodeResult(
            output=extracted,
            metadata={"status": status, "url": url, "method": method},
        )
