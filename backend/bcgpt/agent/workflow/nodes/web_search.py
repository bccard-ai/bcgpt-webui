"""WEB_SEARCH node: search the web for the user's query.

Wraps the synchronous ``search_web(request, engine, query)`` dispatcher in a
thread so it doesn't block the event loop. Best-effort: missing/invalid engine
config yields an empty result set instead of raising.
"""

from __future__ import annotations

import asyncio
import logging

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

log = logging.getLogger(__name__)


def _resolve_engine(node: WorkflowNode, context: ExecutionContext) -> str | None:
    engine = node.config.get("engine")
    if engine:
        return engine
    cfg = getattr(getattr(context.request, "app", None), "state", None)
    cfg = getattr(cfg, "config", None)
    for attr in ("RAG_WEB_SEARCH_ENGINE", "WEB_SEARCH_ENGINE"):
        val = getattr(cfg, attr, None)
        value = getattr(val, "value", val)
        if value:
            return value
    return None


class WebSearchHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        query = state.user_input
        top_k = int(node.config.get("top_k", 5))

        if not query or context.request is None:
            return NodeResult(output=[], metadata={"count": 0, "skipped": True})

        engine = _resolve_engine(node, context)
        if not engine:
            log.info("WEB_SEARCH: no engine configured; skipping")
            return NodeResult(output=[], metadata={"count": 0, "skipped": True})

        await context.emit(
            {"type": "status", "data": {"action": "web_search", "query": query}}
        )

        try:
            from bcgpt.routers.retrieval import search_web

            results = await asyncio.to_thread(
                search_web, context.request, engine, query
            )
            sources = [
                {
                    "document": (getattr(r, "snippet", None) or ""),
                    "metadata": {
                        "title": getattr(r, "title", None),
                        "link": getattr(r, "link", None),
                    },
                    "source_type": "web",
                }
                for r in (results or [])[:top_k]
            ]
            return NodeResult(
                output=sources, metadata={"count": len(sources), "sources": sources}
            )
        except Exception as e:  # noqa: BLE001 - best-effort web search
            log.warning("WEB_SEARCH failed: %s", e)
            return NodeResult(output=[], metadata={"count": 0, "error": str(e)})
