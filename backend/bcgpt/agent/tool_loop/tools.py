"""Tool definitions, built-in tools, and the tool registry.

A :class:`ToolDefinition` pairs an OpenAI-style JSON-schema function spec with an
async ``executor(args, ctx)`` that performs the work. Built-in tools wrap the
same retrieval/web subsystems the workflow nodes use.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Runtime context handed to tool executors."""

    request: Any = None
    user: Any = None
    node_config: dict = field(default_factory=dict)
    # Sources surfaced by tools accumulate here for citation.
    sources: list = field(default_factory=list)


ToolExecutor = Callable[[dict, ToolContext], Awaitable[str]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema
    executor: ToolExecutor

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# --- built-in tool executors ------------------------------------------------


async def _rag_search_executor(args: dict, ctx: ToolContext) -> str:
    query = (args or {}).get("query", "")
    collection_ids = (args or {}).get("collection_ids") or ctx.node_config.get(
        "collection_ids", []
    )
    if not query or not collection_ids or ctx.request is None:
        return "No knowledge collections available or empty query."

    try:
        from bcgpt.agent.workflow.nodes.rag_search import _to_sources
        from bcgpt.retrieval import query_collection

        embedding_function = getattr(ctx.request.app.state, "EMBEDDING_FUNCTION", None)
        if embedding_function is None:
            return "Knowledge search is not configured."
        result = query_collection(
            collection_names=list(collection_ids),
            queries=[query],
            embedding_function=embedding_function,
            k=int(ctx.node_config.get("top_k", 5)),
        )
        sources = _to_sources(result)
        ctx.sources.extend(sources)
        if not sources:
            return "No relevant documents found."
        return "\n\n".join(
            f"[{i+1}] {s.get('document','')[:500]}" for i, s in enumerate(sources)
        )
    except Exception as e:  # noqa: BLE001
        log.warning("rag_search tool failed: %s", e)
        return f"Knowledge search error: {e}"


async def _web_search_executor(args: dict, ctx: ToolContext) -> str:
    query = (args or {}).get("query", "")
    if not query or ctx.request is None:
        return "Empty query."
    try:
        from bcgpt.agent.workflow.nodes.web_search import _resolve_engine
        from bcgpt.routers.retrieval import search_web

        class _N:  # minimal shim so _resolve_engine can read node config
            config = ctx.node_config

        engine = _resolve_engine(_N(), ctx)  # type: ignore[arg-type]
        if not engine:
            return "Web search is not configured."
        results = await asyncio.to_thread(search_web, ctx.request, engine, query)
        top_k = int(ctx.node_config.get("web_top_k", 5))
        chosen = (results or [])[:top_k]
        for r in chosen:
            ctx.sources.append(
                {
                    "document": getattr(r, "snippet", "") or "",
                    "metadata": {
                        "title": getattr(r, "title", None),
                        "link": getattr(r, "link", None),
                    },
                    "source_type": "web",
                }
            )
        if not chosen:
            return "No web results found."
        return "\n\n".join(
            f"[{i+1}] {getattr(r,'title','') or ''}: {getattr(r,'snippet','') or ''} "
            f"({getattr(r,'link','') or ''})"
            for i, r in enumerate(chosen)
        )
    except Exception as e:  # noqa: BLE001
        log.warning("web_search tool failed: %s", e)
        return f"Web search error: {e}"


BUILTIN_TOOLS: dict[str, ToolDefinition] = {
    "rag_search": ToolDefinition(
        name="rag_search",
        description="Search the knowledge base for documents relevant to a query.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
                "collection_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional collection ids to search.",
                },
            },
            "required": ["query"],
        },
        executor=_rag_search_executor,
    ),
    "web_search": ToolDefinition(
        name="web_search",
        description="Search the public web for up-to-date information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
        executor=_web_search_executor,
    ),
}


def resolve_tools(names: list[str]) -> list[ToolDefinition]:
    """Map tool names to definitions, ignoring unknown names (logged)."""
    tools: list[ToolDefinition] = []
    for name in names or []:
        tool = BUILTIN_TOOLS.get(name)
        if tool is None:
            log.warning("Unknown tool requested: %s", name)
            continue
        tools.append(tool)
    return tools
