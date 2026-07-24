"""CONTEXT_MERGE node: fuse RAG + web results into one ranked context.

Uses Reciprocal Rank Fusion (RRF): each result list contributes
``1 / (rrf_k + rank)`` to a document's score, so documents ranked highly across
multiple sources rise to the top. Produces a single context string (with
inline source markers) for the LLM node, plus a ``source_mapping`` for citation.
"""

from __future__ import annotations

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

RRF_K = 60  # standard RRF constant


def _doc_key(source: dict) -> str:
    doc = source.get("document") or ""
    meta = source.get("metadata") or {}
    link = meta.get("link")
    return link or doc.strip()[:200]


class ContextMergeHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        rrf_k = int(node.config.get("rrf_k", RRF_K))
        max_items = int(node.config.get("max_items", 10))

        result_lists: list[list[dict]] = []
        if state.rag_results:
            result_lists.append(state.rag_results)
        if state.web_results:
            result_lists.append(state.web_results)
        # Also fold in any sources accumulated directly on state (e.g. injected).
        if not result_lists and state.sources:
            result_lists.append(state.sources)

        scores: dict[str, float] = {}
        chosen: dict[str, dict] = {}
        for results in result_lists:
            for rank, src in enumerate(results or []):
                key = _doc_key(src)
                if not key:
                    continue
                scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
                chosen.setdefault(key, src)

        ranked_keys = sorted(scores, key=lambda k: scores[k], reverse=True)[:max_items]
        ranked_sources = [chosen[k] for k in ranked_keys]

        # Build the context string with [n] markers + a source map for citation.
        lines: list[str] = []
        source_mapping: dict[str, dict] = {}
        for i, src in enumerate(ranked_sources, start=1):
            meta = src.get("metadata") or {}
            title = meta.get("title")
            doc = (src.get("document") or "").strip()
            header = f"[{i}]" + (f" {title}" if title else "")
            lines.append(f"{header}\n{doc}".strip())
            source_mapping[str(i)] = {
                "title": title,
                "link": meta.get("link"),
                "source_type": src.get("source_type"),
                "score": scores[ranked_keys[i - 1]],
            }

        merged_context = "\n\n".join(lines)
        return NodeResult(
            output=merged_context,
            metadata={
                "count": len(ranked_sources),
                "state_updates": {
                    "source_mapping": source_mapping,
                    "sources": ranked_sources,
                },
            },
        )
