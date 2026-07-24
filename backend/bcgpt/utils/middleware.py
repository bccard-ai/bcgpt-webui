"""Chat completion middleware — payload processing and response handling.

This module implements the middleware layer between the chat API endpoint and
the underlying LLM providers.  It is responsible for:

* Pre-processing user payloads (tool resolution, RAG retrieval, web search,
  security scanning, rate limiting, context compression, smart query
  enhancement).
* Post-processing streaming and non-streaming LLM responses (content
  extraction, reasoning detection, tool-call loops, background tasks such as
  title / tag generation, output security scanning, semantic caching).

Public API
----------
apply_params_to_form_data
    Map per-model parameters onto the OpenAI / Ollama request body.
chat_completion_tools_handler
    Execute synthetic tool-calling for models without native support.
chat_web_search_handler
    Run web searches and inject results as RAG files.
chat_image_generation_handler
    Generate images from user prompts and inject into the conversation.
chat_completion_files_handler
    Full RAG pipeline: query generation -> retrieval -> post-retrieval
    (HyDE, expansion, step-back, reranking, CRAG, doc grading,
    evidence reconciliation, evaluation).
process_chat_payload
    Top-level payload pre-processor (orchestrates all of the above).
process_chat_response
    Top-level response post-processor (streaming + non-streaming).
"""

from __future__ import annotations

import asyncio
import ast
import html
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
from uuid import uuid4

import orjson

from fastapi import HTTPException, Request, status
from starlette.responses import Response, StreamingResponse

from bcgpt.config import DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
from bcgpt.constants import TASKS
from bcgpt.env import (
    ENABLE_REALTIME_CHAT_SAVE,
    GLOBAL_LOG_LEVEL,
    SRC_LOG_LEVELS,
)
from bcgpt.models import ChatGenerations, Chats, Functions, Users
from bcgpt.models import UserModel
from bcgpt.models.audit_log import AuditLogForm, AuditLogs
from bcgpt.retrieval import get_sources_from_files
from bcgpt.retrieval.source_resolution import assert_files_access
from bcgpt.retrieval.advanced.reconciliation import reconcile_evidence
from bcgpt.retrieval.graph.retrieval import graph_enhanced_retrieval
from bcgpt.retrieval.quality.crag import evaluate_retrieval_quality
from bcgpt.retrieval.quality.doc_grading import grade_documents_heuristic
from bcgpt.retrieval.query.expansion import expand_queries
from bcgpt.retrieval.query.hyde import generate_hypothetical_document
from bcgpt.retrieval.query.step_back import generate_step_back_queries
from bcgpt.retrieval.reranking.cross_encoder import cross_encoder_rerank
from bcgpt.retrieval.reranking.llm_rerank import llm_rerank
from bcgpt.retrieval.reranking.rule_based import rule_based_rerank
from bcgpt.routers import image_generations
from bcgpt.routers import process_web_search, SearchForm
from bcgpt.routers.images import GenerateImageForm
from bcgpt.routers.pipelines import process_pipeline_inlet_filter
from bcgpt.routers.tasks import (
    expand_image_prompt,
    generate_chat_tags,
    generate_context_compression,
    generate_image_prompt,
    generate_queries,
    generate_smart_query,
    generate_title,
    translate_image_prompt,
)
from bcgpt.socket.main import (
    get_active_status_by_user_id,
    get_event_call,
    get_event_emitter,
)
from bcgpt.tasks import create_task
from bcgpt.utils import generate_chat_completion, get_tools, post_webhook
from bcgpt.utils.filter import get_sorted_filter_ids, process_filter_functions
from bcgpt.utils.query_entity_guard import (
    entity_appears_in_text,
    extract_query_entities,
    guard_rewrite,
)
from bcgpt.utils.security.content_isolation import (
    get_isolation_instruction,
    isolate_block,
)
from bcgpt.utils.misc import (
    add_or_update_system_message,
    convert_logit_bias_input_to_json,
    get_last_assistant_message,
    get_last_user_message,
    get_message_list,
    prepend_to_first_user_message_content,
)
from bcgpt.utils.prometheus_metrics import (
    record_cache_hit,
    record_cache_miss,
    record_retrieval_score,
    record_token_usage,
)
from bcgpt.utils.task import (
    get_task_model_id,
    rag_template,
    tools_function_calling_generation_template,
)

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# Section: Internal helpers
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> Optional[str]:
    """Return the outermost ``{...}`` substring from *text*, or ``None``."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    return text[start:end]


def _parse_task_json_response(text: str) -> dict:
    """Extract and parse the first JSON object from *text*.

    Falls back to returning a dict with the raw text under the key
    ``"queries"`` (the most common caller expectation).
    """
    json_str = _extract_json_object(text)
    if json_str is None:
        return {"queries": [text]}
    try:
        return orjson.loads(json_str)
    except Exception:
        return {"queries": [text]}


def _task_completion_content(result: dict | Response) -> str:
    """Extract the assistant message content from a task chat-completion result.

    Task helpers in ``routers/tasks.py`` return an OpenAI-shaped dict on
    success but a Starlette ``Response`` when the upstream model call fails.
    This helper normalises both cases and always returns a string.
    """
    if isinstance(result, dict):
        return result["choices"][0]["message"]["content"]

    detail = f"task model returned {type(result).__name__}"
    body = getattr(result, "body", None)
    if body is not None:
        try:
            raw = bytes(body).decode("utf-8", errors="replace")
            try:
                detail = orjson.loads(raw).get("detail", raw)
            except Exception:
                detail = raw
        except Exception:
            pass
    raise RuntimeError(detail)


def _exception_message(error: Exception) -> str:
    """Return a human-readable message from *error*."""
    if isinstance(error, HTTPException):
        detail = error.detail
        return detail if isinstance(detail, str) else str(detail)
    return str(error) or error.__class__.__name__


def _user_info_dict(user: UserModel) -> dict[str, Any]:
    """Build the standard user-info mapping passed to security scanners."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


async def _emit_status(
    emitter: Any,
    action: str,
    description: str,
    *,
    done: bool = False,
    error: bool = False,
    query: str | None = None,
    urls: list[str] | None = None,
) -> None:
    """Emit a ``status`` event through *emitter*."""
    data: dict[str, Any] = {
        "action": action,
        "description": description,
        "done": done,
    }
    if error:
        data["error"] = True
    if query is not None:
        data["query"] = query
    if urls is not None:
        data["urls"] = urls
    await emitter({"type": "status", "data": data})


def _build_tool_source(
    tool_id: str,
    function_name: str,
    tool_result: str,
    *,
    citation: bool = False,
    direct: bool = False,
) -> dict[str, Any]:
    """Construct a source dict for a tool-call result."""
    name = f"TOOL:{tool_id}/{function_name}" if tool_id else function_name
    source_name = name if (citation or direct) else {}
    return {
        "source": (
            {"name": source_name} if isinstance(source_name, str) else source_name
        ),
        "document": [tool_result],
        "metadata": [{"source": name}],
    }


def _extract_sources_from_events(events: list[dict]) -> list[dict]:
    """Collect all source dicts from a list of emitted events."""
    result: list[dict] = []
    for ev in events:
        if isinstance(ev, dict) and "sources" in ev:
            for s in ev["sources"]:
                result.append(
                    {
                        "page_content": s.get("page_content", ""),
                        "document": s.get("document", []),
                        "metadata": s.get("metadata", {}),
                        "score": s.get("score", 0),
                        "source": s.get("source", {}),
                    }
                )
    return result


def _log_ai_interaction(
    request: Request,
    user: UserModel,
    metadata: dict,
    model: dict,
    form_data: dict,
    *,
    usage: dict | None,
    rag_source_count: int,
    tool_call_count: int,
    output_sanitized: bool,
    web_search_used: bool,
    streaming: bool,
) -> None:
    """Write one structured AI-interaction audit row (EU AI Act / 한국 AI 기본법).

    Records explainability signals — model/provider, in/out tokens, guardrail
    outcome, tool/RAG/web usage, and end-to-end latency — as a single
    ``category='ai_interaction'`` audit entry. Stores NO message content, so the
    payload is PII-free by construction. Best-effort: never raises into the
    response path. Gated by ``AI_INTERACTION_AUDIT_ENABLED`` (default OFF).
    """
    try:
        if not request.app.state.config.AI_INTERACTION_AUDIT_ENABLED:
            return

        usage = usage or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        if (
            total_tokens is None
            and isinstance(prompt_tokens, int)
            and isinstance(completion_tokens, int)
        ):
            total_tokens = prompt_tokens + completion_tokens

        start_ts = metadata.get("__chat_start_ts__")
        latency_ms = None
        if isinstance(start_ts, (int, float)):
            latency_ms = max(0, int((time.time() - start_ts) * 1000))

        AuditLogs.insert_log(
            AuditLogForm(
                user_id=user.id,
                user_email=user.email,
                action="AI_INTERACTION",
                resource_type="chat",
                resource_id=metadata.get("chat_id"),
                resource_name=metadata.get("message_id"),
                severity="INFO",
                category="ai_interaction",
                session_id=metadata.get("session_id"),
                audit_details={
                    "model_id": (model or {}).get("id") or form_data.get("model"),
                    "provider": (model or {}).get("owned_by"),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "rag_source_count": rag_source_count,
                    "tool_call_count": tool_call_count,
                    "web_search_used": bool(web_search_used),
                    "output_sanitized": bool(output_sanitized),
                    "latency_ms": latency_ms,
                    # estimated_cost is populated once model_pricing exists (Phase 2.1).
                    "estimated_cost": None,
                    "streaming": bool(streaming),
                },
            )
        )
    except Exception as exc:
        log.warning("Failed to write ai_interaction audit log: %s", exc)


def _record_provenance(
    request: Request,
    user,
    metadata: dict,
    model: dict,
    form_data: dict,
    content: str,
    events: list,
    usage: dict | None,
) -> None:
    """Best-effort RAG provenance record for compliance (EU AI Act Art. 12)."""
    try:
        cfg = request.app.state.config
        if not getattr(cfg, "COMPLIANCE_PROVENANCE_ENABLED", False):
            return

        from bcgpt.compliance.models.provenance import AIRAGProvenances

        messages = form_data.get("messages") or []
        query = ""
        if messages:
            last = messages[-1]
            query = last.get("content", "") if isinstance(last, dict) else str(last)

        sources = _extract_sources_from_events(events) if events else []

        total_tokens = 0
        if usage and isinstance(usage, dict):
            total_tokens = usage.get("total_tokens", 0)

        AIRAGProvenances.record_from_chat(
            user_id=user.id,
            model_name=model.get("id", model.get("name", "unknown")),
            query=query,
            response=content or "",
            sources=sources,
            total_tokens=total_tokens,
            chat_id=metadata.get("chat_id"),
        )
    except Exception as exc:
        log.warning("Failed to write RAG provenance record: %s", exc)


def _web_search_used_in_form(form_data: dict) -> bool:
    """True if any web-search result file was attached during payload processing."""
    return any(
        isinstance(f, dict) and f.get("type") == "web_search"
        for f in (form_data.get("files") or [])
    )


async def _persist_token_usage(
    request: Request,
    user: UserModel,
    metadata: dict,
    model: dict,
    usage: dict | None,
) -> None:
    """Account for an interaction's tokens after the response completes.

    Two independently-gated effects: (2.1) persist one ``llm_token_usage`` row
    with computed cost when ``TOKEN_USAGE_PERSIST_ENABLED``; (2.2) record the
    tokens against the per-user budget windows when ``TOKEN_BUDGET_ENABLED``.
    Best-effort; never raises into the response path.
    """
    usage = usage or {}
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    if not isinstance(pt, int) and not isinstance(ct, int):
        return
    pt_i = int(pt) if isinstance(pt, int) else 0
    ct_i = int(ct) if isinstance(ct, int) else 0
    uid = (metadata or {}).get("user_id") or getattr(user, "id", None)

    # 2.1 — FinOps persistence
    try:
        if request.app.state.config.TOKEN_USAGE_PERSIST_ENABLED:
            from bcgpt.models.token_usage import TokenUsages

            await asyncio.to_thread(
                TokenUsages.insert_usage,
                uid,
                (model or {}).get("id") or "unknown",
                pt_i,
                ct_i,
                (model or {}).get("owned_by"),
                (metadata or {}).get("agent_id"),
            )
    except Exception as exc:
        log.warning("Failed to persist token usage: %s", exc)

    # 2.2 — Token budget consumption
    try:
        if request.app.state.config.TOKEN_BUDGET_ENABLED and uid and (pt_i + ct_i) > 0:
            from bcgpt.utils.per_user_rate_limit import token_budget_limiter

            token_budget_limiter.record_token_usage("user:%s" % uid, pt_i + ct_i)
    except Exception as exc:
        log.warning("Failed to record token budget: %s", exc)


def _get_rag_override(model: dict, app_config: Any) -> dict[str, Any]:
    """Resolve per-model RAG overrides, falling back to app-level config."""
    rag_settings = (model.get("info", {}).get("meta", {}).get("rag_settings")) or {}
    return {
        "k": rag_settings.get("k", app_config.TOP_K),
        "k_reranker": rag_settings.get("k_reranker", app_config.TOP_K_RERANKER),
        "r": rag_settings.get("r", app_config.RELEVANCE_THRESHOLD),
        "hybrid": rag_settings.get("hybrid", app_config.ENABLE_RAG_HYBRID_SEARCH),
        "query_rewrite": rag_settings.get(
            "query_rewrite",
            getattr(app_config, "ENABLE_RETRIEVAL_QUERY_GENERATION", True),
        ),
        "hyde": rag_settings.get("hyde", False),
        "rag_template": rag_settings.get("rag_template"),
    }


def _get_models_for_request(request: Request) -> dict:
    """Return the model dict appropriate for the current request context."""
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        return {request.state.model["id"]: request.state.model}
    return request.app.state.MODELS


def _resolve_task_model(request: Request, base_model_id: str, models: dict) -> str:
    """Determine the task model ID for the given *base_model_id*."""
    return get_task_model_id(
        base_model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )


# ---------------------------------------------------------------------------
# Section: Tool calling handler (synthetic / non-native)
# ---------------------------------------------------------------------------


async def _get_content_from_response(
    response: StreamingResponse | dict,
) -> Optional[str]:
    """Extract text content from a chat-completion response."""
    if hasattr(response, "body_iterator"):
        content: Optional[str] = None
        async for chunk in response.body_iterator:
            data = orjson.loads(chunk.decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
        if response.background is not None:
            await response.background()
        return content
    return response["choices"][0]["message"]["content"]


def _build_tools_calling_payload(
    messages: list[dict],
    task_model_id: str,
    system_content: str,
) -> dict[str, Any]:
    """Build the payload used to ask the task model which tools to invoke."""
    user_message = get_last_user_message(messages)
    history = "\n".join(
        f"{m['role'].upper()}: \"\"\"{m['content']}\"\"\"" for m in messages[::-1][:4]
    )
    return {
        "model": task_model_id,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Query: {user_message}"},
        ],
        "stream": False,
        "metadata": {"task": str(TASKS.FUNCTION_CALLING)},
    }


def _coerce_tool_param(value: Any, expected_type: str | None) -> Any:
    """Coerce *value* to the JSON schema *expected_type*, best-effort."""
    if expected_type == "string" and not isinstance(value, str):
        return str(value)
    if expected_type == "number" and not isinstance(value, (int, float)):
        return float(value)
    if expected_type == "integer" and not isinstance(value, int):
        return int(float(value))
    if expected_type == "boolean" and not isinstance(value, bool):
        return bool(value)
    if expected_type == "array" and not isinstance(value, list):
        return [value]
    return value


def _filter_and_coerce_params(raw_params: dict, spec: dict) -> dict:
    """Keep only allowed params from *spec* and coerce their types."""
    properties = spec.get("parameters", {}).get("properties", {})
    allowed = properties.keys()
    param_types = {k: v.get("type") for k, v in properties.items()}

    filtered: dict[str, Any] = {k: v for k, v in raw_params.items() if k in allowed}
    for pname in list(filtered.keys()):
        filtered[pname] = _coerce_tool_param(filtered[pname], param_types.get(pname))
        if param_types.get(pname) == "object" and not isinstance(filtered[pname], dict):
            filtered.pop(pname, None)
    return filtered


async def chat_completion_tools_handler(
    request: Request,
    body: dict,
    extra_params: dict,
    user: UserModel,
    models: dict,
    tools: dict,
) -> tuple[dict, dict]:
    """Resolve tool calls via the task model for non-native function calling.

    Returns ``(body, flags)`` where *flags* may contain ``"sources"``.
    """
    event_caller = extra_params["__event_call__"]
    metadata = extra_params["__metadata__"]

    task_model_id = _resolve_task_model(request, body["model"], models)

    skip_files = False
    sources: list[dict] = []

    specs = [tool["spec"] for tool in tools.values()]
    tools_specs = orjson.dumps(specs).decode()

    template = (
        request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
        or DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    )
    tools_prompt = tools_function_calling_generation_template(template, tools_specs)
    payload = _build_tools_calling_payload(
        body["messages"], task_model_id, tools_prompt
    )

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        content = await _get_content_from_response(response)
        log.debug("tools_handler content=%s", content)

        if not content:
            return body, {}

        try:
            json_str = _extract_json_object(content)
            if not json_str:
                raise ValueError("No JSON object found in the response")
            result = orjson.loads(json_str)

            async def _handle_tool_call(tool_call: dict) -> None:
                nonlocal skip_files
                tool_name = tool_call.get("name")
                if tool_name not in tools:
                    return

                raw_params = tool_call.get("parameters", {})
                tool = tools[tool_name]
                tool_params = _filter_and_coerce_params(
                    raw_params, tool.get("spec", {})
                )

                try:
                    if tool.get("direct", False):
                        tool_result = await event_caller(
                            {
                                "type": "execute:tool",
                                "data": {
                                    "id": str(uuid4()),
                                    "name": tool_name,
                                    "params": tool_params,
                                    "server": tool.get("server", {}),
                                    "session_id": metadata.get("session_id"),
                                },
                            }
                        )
                    else:
                        tool_result = await tool["callable"](**tool_params)
                except Exception as exc:
                    tool_result = str(exc)

                if isinstance(tool_result, (dict, list)):
                    tool_result = orjson.dumps(
                        tool_result,
                        option=orjson.OPT_INDENT_2,
                    ).decode()

                if isinstance(tool_result, str):
                    tool_id = tool.get("toolkit_id", "")
                    sources.append(
                        _build_tool_source(
                            tool_id,
                            tool_name,
                            tool_result,
                            citation=tool.get("citation", False),
                            direct=tool.get("direct", False),
                        )
                    )
                    if tool.get("file_handler", False):
                        skip_files = True

            if result.get("tool_calls"):
                for tc in result["tool_calls"]:
                    await _handle_tool_call(tc)
            else:
                await _handle_tool_call(result)

        except Exception as exc:
            log.debug("Error parsing tool call result: %s", exc)
    except Exception as exc:
        log.debug("Error in tools handler: %s", exc)

    log.debug("tool_contexts: %s", sources)

    if skip_files and "files" in body.get("metadata", {}):
        del body["metadata"]["files"]

    return body, {"sources": sources}


# ---------------------------------------------------------------------------
# Section: Web search handler
# ---------------------------------------------------------------------------


async def _security_scan_web_results(
    request: Request,
    results: dict,
    user: UserModel,
    search_query: str,
    form_data: dict,
) -> dict | None:
    """Scan web search results through the security pipeline.

    Returns ``None`` if the results were blocked.
    """
    if not (
        request.app.state.config.SECURITY_SCANNER_ENABLED
        and request.app.state.config.SECURITY_SCAN_WEB_RESULTS
    ):
        return results

    try:
        from bcgpt.utils.security import SecurityPipeline

        pipeline = SecurityPipeline(request.app.state.config)
        text_parts = [
            doc.get("content", "")
            for doc in results.get("docs", [])
            if doc.get("content")
        ]
        if not text_parts:
            return results

        search_content = "\n".join(text_parts)
        scan_result = await pipeline.scan_input(
            search_content,
            _user_info_dict(user),
            metadata={
                "source": "web_search",
                "search_query": search_query,
                "chat_id": form_data.get("chat_id"),
                "model_id": form_data.get("model", ""),
            },
        )
        if pipeline.should_block(scan_result):
            return None
    except Exception as exc:
        log.exception("Web search security scan error: %s", exc)

    return results


def _web_result_to_file(search_query: str, results: dict) -> dict | None:
    """Convert web search results into a file dict for RAG processing."""
    if results.get("collection_name"):
        return {
            "collection_name": results["collection_name"],
            "name": search_query,
            "type": "web_search",
            "urls": results["filenames"],
        }
    if results.get("docs"):
        return {
            "docs": results.get("docs", []),
            "name": search_query,
            "type": "web_search",
            "urls": results["filenames"],
        }
    return None


async def _search_single_query(
    request: Request,
    search_query: str,
    user: UserModel,
    event_emitter: Any,
    form_data: dict,
) -> tuple[str, dict | None]:
    """Execute a single web search and return (query, results_or_None)."""
    await _emit_status(
        event_emitter,
        "web_search",
        'Searching "%s"' % search_query,
        query=search_query,
    )
    try:
        results = await process_web_search(
            request, SearchForm(query=search_query), user=user
        )
        if results:
            results = await _security_scan_web_results(
                request, results, user, search_query, form_data
            )
        return search_query, results
    except Exception as exc:
        reason = _exception_message(exc)
        await _emit_status(
            event_emitter,
            "web_search",
            'Error searching "%s": %s' % (search_query, reason),
            query=search_query,
            done=True,
            error=True,
        )
        return search_query, None


async def chat_web_search_handler(
    request: Request,
    form_data: dict,
    extra_params: dict,
    user: UserModel,
) -> dict:
    """Run web search(es) and append results as RAG files.

    Supports query rewriting for better search quality and parallel
    execution when multiple queries are generated.
    """
    event_emitter = extra_params["__event_emitter__"]
    await _emit_status(event_emitter, "web_search", "Generating search query")

    messages = form_data["messages"]
    user_message = form_data.get("__enhanced_query__", get_last_user_message(messages))

    # --- Query generation ---
    queries: list[str] = [user_message]
    rewrite_enabled = request.app.state.config.RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED
    rewrite_model = request.app.state.config.RAG_WEB_SEARCH_QUERY_REWRITE_MODEL

    if rewrite_enabled:
        try:
            model = rewrite_model or form_data["model"]
            res = await generate_queries(
                request,
                {
                    "model": model,
                    "messages": messages,
                    "prompt": user_message,
                    "type": "web_search",
                },
                user,
            )
            response = _task_completion_content(res)
            parsed = _parse_task_json_response(response)
            queries = parsed.get("queries", [response])

            # Named-entity preservation: rewrites may legitimately DECOMPOSE a
            # query into sub-queries, so validate the UNION (not each query) —
            # only fall back if an explicit entity is dropped from ALL of them.
            if request.app.state.config.QUERY_REWRITE_ENTITY_GUARD_ENABLED and queries:
                _entities = extract_query_entities(user_message)
                if _entities:
                    _joined = " ".join(queries)
                    _missing = [
                        e for e in _entities if not entity_appears_in_text(e, _joined)
                    ]
                    if _missing:
                        log.warning(
                            "Web search rewrite dropped named entities %s; "
                            "falling back to the original query.",
                            _missing,
                        )
                        queries = [user_message]
        except Exception as exc:
            log.warning(
                "Web search query generation failed; "
                "using original query. Reason: %s",
                _exception_message(exc),
            )
            queries = [user_message]

    if not queries:
        await _emit_status(
            event_emitter,
            "web_search",
            "No search query generated",
            done=True,
        )
        return form_data

    # --- Execute searches ---
    all_results: list[dict] = []
    files = form_data.get("files", [])
    concurrent = request.app.state.config.RAG_WEB_SEARCH_CONCURRENT_QUERIES

    if concurrent and len(queries) > 1:
        search_results = await asyncio.gather(
            *[
                _search_single_query(request, q, user, event_emitter, form_data)
                for q in queries
            ]
        )
        for search_query, results in search_results:
            if results:
                all_results.append(results)
                file_entry = _web_result_to_file(search_query, results)
                if file_entry:
                    files.append(file_entry)
    else:
        for search_query in queries:
            sq_clean, results = await _search_single_query(
                request, search_query, user, event_emitter, form_data
            )
            if results:
                all_results.append(results)
                file_entry = _web_result_to_file(sq_clean, results)
                if file_entry:
                    files.append(file_entry)

    form_data["files"] = files

    # --- Final status ---
    if all_results:
        urls: list[str] = []
        for r in all_results:
            if "filenames" in r:
                urls.extend(r["filenames"])
        await _emit_status(
            event_emitter,
            "web_search",
            "Searched {{count}} sites",
            done=True,
            urls=urls,
        )
    else:
        await _emit_status(
            event_emitter,
            "web_search",
            "No search results found",
            done=True,
            error=True,
        )

    return form_data


# ---------------------------------------------------------------------------
# Section: Image generation handler
# ---------------------------------------------------------------------------


async def _try_prompt_stage(
    request: Request,
    form_data: dict,
    user: UserModel,
    generate_fn: Any,
    prompt_key: str,
) -> str | None:
    """Run a prompt transformation stage; return the extracted prompt."""
    try:
        res = await generate_fn(request, form_data, user)
        response = _task_completion_content(res)
        json_str = _extract_json_object(response)
        if json_str:
            parsed = orjson.loads(json_str)
            return parsed.get(prompt_key)
    except Exception as exc:
        log.warning(
            "Prompt stage %s failed: %s",
            getattr(generate_fn, "__name__", "?"),
            exc,
        )
    return None


async def chat_image_generation_handler(
    request: Request,
    form_data: dict,
    extra_params: dict,
    user: UserModel,
) -> dict:
    """Generate images from the user's prompt and emit to the client."""
    event_emitter = extra_params["__event_emitter__"]
    await _emit_status(event_emitter, "image_generation", "Generating an image")

    messages = form_data["messages"]
    user_message = get_last_user_message(messages)
    prompt = user_message

    config = request.app.state.config

    # Stage 1: Prompt generation
    if config.ENABLE_IMAGE_PROMPT_GENERATION:
        new_prompt = await _try_prompt_stage(
            request,
            {"model": form_data["model"], "messages": messages},
            user,
            generate_image_prompt,
            "prompt",
        )
        if new_prompt:
            prompt = new_prompt

    # Stage 2: Translation
    if config.ENABLE_IMAGE_PROMPT_TRANSLATION:
        translated = await _try_prompt_stage(
            request,
            {"model": form_data["model"], "prompt": prompt},
            user,
            translate_image_prompt,
            "prompt",
        )
        if translated:
            prompt = translated

    # Stage 3: Expansion
    if config.ENABLE_IMAGE_PROMPT_EXPANSION:
        expanded = await _try_prompt_stage(
            request,
            {"model": form_data["model"], "prompt": prompt},
            user,
            expand_image_prompt,
            "prompt",
        )
        if expanded:
            prompt = expanded

    # Image generation
    system_message_content = ""
    try:
        images = await image_generations(
            request=request,
            form_data=GenerateImageForm(**{"prompt": prompt}),
            user=user,
        )
        await _emit_status(
            event_emitter,
            "image_generation",
            "Generated an image",
            done=True,
        )

        for image in images:
            await event_emitter(
                {
                    "type": "message",
                    "data": {"content": ("![Generated Image](%s)\n" % image["url"])},
                }
            )
        system_message_content = (
            "<context>User is shown the generated image, "
            "tell the user that the image has been generated"
            "</context>"
        )
    except Exception as exc:
        log.exception("Image generation error: %s", exc)
        await _emit_status(
            event_emitter,
            "image_generation",
            "An error occurred while generating an image",
            done=True,
        )
        system_message_content = (
            "<context>Unable to generate an image, "
            "tell the user that an error occurred</context>"
        )

    if system_message_content:
        form_data["messages"] = add_or_update_system_message(
            system_message_content, form_data["messages"]
        )

    return form_data


# ---------------------------------------------------------------------------
# Section: RAG / file handler
# ---------------------------------------------------------------------------


async def _semantic_cache_lookup(
    request: Request,
    query: str,
    user: UserModel,
) -> dict | None:
    """Check the semantic cache for *query*.  Returns cached data or None."""
    config = request.app.state.config
    if not getattr(config, "RAG_SEMANTIC_CACHE_ENABLED", False):
        return None

    from bcgpt.retrieval.vector.connector import VECTOR_DB_CLIENT
    from bcgpt.utils.semantic_cache import SemanticCache

    embedding_fn = request.app.state.EMBEDDING_FUNCTION
    if not embedding_fn or not VECTOR_DB_CLIENT or not VECTOR_DB_CLIENT.client:
        return None

    cache = SemanticCache(
        qdrant_client=VECTOR_DB_CLIENT,
        embedding_fn=lambda q: embedding_fn(q, user=user),
        threshold=getattr(config, "RAG_SEMANTIC_CACHE_THRESHOLD", 0.95),
        ttl=getattr(config, "RAG_SEMANTIC_CACHE_TTL", 3600),
    )
    return cache.lookup(query, user_id=str(user.id))


async def _semantic_cache_store(
    request: Request,
    query: str,
    response: str,
    sources: list[dict],
    user: UserModel,
) -> None:
    """Store a response in the semantic cache (best-effort)."""
    try:
        config = request.app.state.config
        from bcgpt.retrieval.vector.connector import VECTOR_DB_CLIENT
        from bcgpt.utils.semantic_cache import SemanticCache

        embedding_fn = request.app.state.EMBEDDING_FUNCTION
        if not embedding_fn or not VECTOR_DB_CLIENT or not VECTOR_DB_CLIENT.client:
            return

        cache = SemanticCache(
            qdrant_client=VECTOR_DB_CLIENT,
            embedding_fn=lambda q: embedding_fn(q, user=user),
            threshold=getattr(config, "RAG_SEMANTIC_CACHE_THRESHOLD", 0.95),
            ttl=getattr(config, "RAG_SEMANTIC_CACHE_TTL", 3600),
        )
        cache.store(
            query=query,
            response=response,
            sources=sources,
            user_id=str(user.id),
        )
    except Exception:
        pass


async def _run_pre_retrieval(
    config: Any,
    queries: list[str],
    original_query: str,
    request: Request,
    user: UserModel,
) -> list[str]:
    """Run pre-retrieval stages (HyDE, query expansion, step-back).

    Returns the augmented list of queries.
    """
    augmented = list(queries)

    # HyDE
    if getattr(config, "RAG_HYDE_ENABLED", False) and augmented:
        hyde_doc = await generate_hypothetical_document(
            query=augmented[0],
            request=request,
            user=user,
            model_id=getattr(config, "RAG_HYDE_MODEL", "") or None,
        )
        if hyde_doc:
            augmented.append(hyde_doc)

    # Query expansion
    if getattr(config, "RAG_QUERY_EXPANSION_ENABLED", False) and augmented:
        expanded: list[str] = []
        for q in augmented[:2]:
            expanded.extend(
                await expand_queries(
                    query=q,
                    request=request,
                    user=user,
                    max_expansions=getattr(config, "RAG_QUERY_EXPANSION_MAX", 3),
                )
            )
        augmented.extend(expanded)

    # Step-back prompting
    if getattr(config, "RAG_STEP_BACK_ENABLED", False) and augmented:
        step_back = await generate_step_back_queries(
            query=original_query, request=request, user=user
        )
        if step_back:
            augmented.extend(step_back)

    return augmented


async def _run_post_retrieval(
    config: Any,
    source_docs: list[dict],
    original_query: str,
    request: Request,
    user: UserModel,
) -> list[dict]:
    """Run post-retrieval processing pipeline.

    Returns the filtered / reranked documents.
    """
    docs = list(source_docs)

    # Rule-based reranking
    if getattr(config, "RAG_RULE_BASED_RERANKING_ENABLED", False) and docs:
        docs = rule_based_rerank(query=original_query, documents=docs)

    # LLM reranking
    if getattr(config, "RAG_LLM_RERANKING_ENABLED", False) and docs:
        docs = await llm_rerank(
            query=original_query,
            documents=docs,
            request=request,
            user=user,
            model_id=(getattr(config, "RAG_LLM_RERANKING_MODEL", "") or None),
        )

    # Cross-encoder reranking
    if getattr(config, "RAG_CROSS_ENCODER_RERANKING_ENABLED", False) and docs:
        docs = cross_encoder_rerank(
            query=original_query,
            documents=docs,
            model_name=getattr(
                config,
                "RAG_CROSS_ENCODER_MODEL",
                "BAAI/bge-reranker-v2-m3",
            ),
            max_length=getattr(config, "RAG_CROSS_ENCODER_MAX_LENGTH", 512),
            top_k=getattr(config, "RAG_CROSS_ENCODER_TOP_K", 10),
        )

    # GraphRAG enhancement
    if getattr(config, "RAG_GRAPH_ENABLED", False) and docs:
        try:
            docs = await graph_enhanced_retrieval(
                query=original_query,
                documents=docs,
                request=request,
                user=user,
                config={
                    "max_hops": getattr(config, "RAG_GRAPH_MAX_HOPS", 2),
                    "ppr_enabled": getattr(config, "RAG_GRAPH_PPR_ENABLED", True),
                },
            )
        except Exception as exc:
            log.warning("GraphRAG enhancement failed, skipping: %s", exc)

    # CRAG quality evaluation
    if getattr(config, "RAG_CRAG_ENABLED", False) and docs:
        crag_result = evaluate_retrieval_quality(query=original_query, documents=docs)
        crag_verdict = crag_result.get("verdict")
        log.debug(
            "CRAG verdict: %s, score: %s",
            crag_verdict,
            crag_result.get("score"),
        )
        if crag_verdict == "insufficient":
            log.info(
                "CRAG: retrieval quality insufficient, "
                "source quality may be degraded"
            )

    # Document grading
    if getattr(config, "RAG_DOC_GRADING_ENABLED", False) and docs:
        docs = grade_documents_heuristic(query=original_query, documents=docs)
        docs = [d for d in docs if d.get("grade") != "incorrect"]

    # Evidence reconciliation (logging only)
    if getattr(config, "RAG_EVIDENCE_RECONCILIATION_ENABLED", False) and len(docs) >= 2:
        reconciliation = reconcile_evidence(query=original_query, documents=docs)
        if reconciliation.get("conflicts"):
            log.warning(
                "RAG evidence conflicts detected: %d conflicts",
                len(reconciliation["conflicts"]),
            )
        if reconciliation.get("redundant_pairs"):
            log.debug(
                "RAG redundancy detected: %d pairs",
                len(reconciliation["redundant_pairs"]),
            )

    # RAG evaluation
    if getattr(config, "RAG_EVALUATION_ENABLED", False) and docs:
        try:
            from bcgpt.retrieval.evaluation.evaluator import (
                evaluate_rag,
            )

            eval_result = await evaluate_rag(
                query=original_query,
                documents=docs,
                include_llm_metrics=False,
                metrics=getattr(
                    config,
                    "RAG_EVALUATION_METRICS",
                    "faithfulness,relevance,context_precision",
                ),
            )
            if getattr(config, "RAG_EVALUATION_LOG_RESULTS", True):
                log.info(
                    "RAG evaluation: overall=%.2f, "
                    "relevance=%.2f, precision=%.2f, "
                    "recall=%.2f, metrics=%s",
                    eval_result.overall_score,
                    eval_result.relevance,
                    eval_result.context_precision,
                    eval_result.context_recall,
                    eval_result.metrics_used,
                )
        except Exception as exc:
            log.warning("RAG evaluation failed, skipping: %s", exc)

    return docs


def _source_docs_to_sources(source_docs: list[dict]) -> list[dict]:
    """Convert internal source-doc format to the external source format."""
    return [
        {
            "page_content": doc["content"],
            "document": [doc["content"]] if doc["content"] else [],
            "metadata": doc.get("metadata", {}),
            "score": doc.get("score", 0),
        }
        for doc in source_docs
    ]


def _sources_to_source_docs(sources: list[dict]) -> list[dict]:
    """Convert external source format to internal source-doc format."""
    docs: list[dict] = []
    for source in sources:
        content = source.get(
            "page_content",
            source.get(
                "content",
                (
                    "\n".join(source.get("document", []))
                    if source.get("document")
                    else ""
                ),
            ),
        )
        score = source.get("score", source.get("distance", 0))
        docs.append(
            {
                "content": content,
                "metadata": source.get("metadata", {}),
                "score": score,
            }
        )
        if isinstance(score, (int, float)):
            record_retrieval_score(float(score))
    return docs


async def chat_completion_files_handler(
    request: Request,
    body: dict,
    user: UserModel,
    model: dict | None = None,
) -> tuple[dict, dict[str, list]]:
    """Full RAG pipeline: query generation -> retrieval -> post-processing.

    Returns ``(body, flags)`` where *flags* may contain ``"sources"``.
    """
    sources: list[dict] = []

    files = body.get("metadata", {}).get("files")
    if not files:
        return body, {"sources": sources}

    # Enforce server-side ACL on CLIENT-supplied collection references. Model
    # knowledge refs are tagged __model_knowledge__ and skipped by the helper,
    # so an admin-curated agent KB remains usable while a client cannot inject
    # another user's KB / user-memory collection into the retrieval.
    await assert_files_access(files, user)

    # --- Query generation ---
    queries: list[str] = []
    try:
        res = await generate_queries(
            request,
            {
                "model": body["model"],
                "messages": body["messages"],
                "type": "retrieval",
            },
            user,
        )
        response = _task_completion_content(res)
        parsed = _parse_task_json_response(response)
        queries = parsed.get("queries", [])
    except Exception as exc:
        log.warning("Query generation failed: %s", exc)

    if not queries:
        queries = [get_last_user_message(body["messages"])]

    try:
        overrides = _get_rag_override(model or {}, request.app.state.config)
        config = request.app.state.config

        # --- Semantic cache ---
        cache_hit = await _semantic_cache_lookup(request, queries[0], user)
        if cache_hit:
            sources = cache_hit["sources"]
            body["__semantic_cache_miss__"] = False
            body["__semantic_cache_query__"] = queries[0]
            record_cache_hit()
        else:
            body["__semantic_cache_miss__"] = True
            body["__semantic_cache_query__"] = queries[0]
            record_cache_miss()

        if not cache_hit:
            original_query = get_last_user_message(body["messages"])

            # Pre-retrieval
            augmented_queries = await _run_pre_retrieval(
                config, queries, original_query, request, user
            )

            # Retrieval
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as executor:
                embedding_fn = request.app.state.EMBEDDING_FUNCTION
                raw_sources = await loop.run_in_executor(
                    executor,
                    lambda: get_sources_from_files(
                        request=request,
                        files=files,
                        queries=augmented_queries,
                        embedding_function=(
                            lambda query, prefix: (
                                embedding_fn(
                                    query,
                                    prefix=prefix,
                                    user=user,
                                )
                                if embedding_fn
                                else None
                            )
                        ),
                        k=overrides["k"],
                        reranking_function=request.app.state.rf,
                        k_reranker=overrides["k_reranker"],
                        r=overrides["r"],
                        hybrid_search=overrides["hybrid"],
                        full_context=config.RAG_FULL_CONTEXT,
                        rrf_k=getattr(config, "RAG_RRF_K", 60),
                        vector_weight=getattr(config, "RAG_RRF_VECTOR_WEIGHT", 0.7),
                        keyword_weight=getattr(config, "RAG_RRF_KEYWORD_WEIGHT", 0.3),
                    ),
                )

            # Post-retrieval
            source_docs = _sources_to_source_docs(raw_sources)
            source_docs = await _run_post_retrieval(
                config, source_docs, original_query, request, user
            )
            sources = _source_docs_to_sources(source_docs)

    except Exception as exc:
        log.exception("RAG pipeline error: %s", exc)

    log.debug("rag_contexts:sources: %s", sources)
    return body, {"sources": sources}


# ---------------------------------------------------------------------------
# Section: Parameter mapping
# ---------------------------------------------------------------------------

_OPENAI_PARAM_KEYS = (
    "seed",
    "stop",
    "temperature",
    "max_tokens",
    "top_p",
    "frequency_penalty",
    "reasoning_effort",
)


def apply_params_to_form_data(form_data: dict, model: dict) -> dict:
    """Apply per-model parameters to the request body.

    Ollama models receive ``options`` and ``format`` / ``keep_alive``
    keys, while OpenAI-compatible models receive individual parameter
    keys.
    """
    params = form_data.pop("params", {})
    if not params:
        return form_data

    if model.get("ollama"):
        form_data["options"] = params
        for key in ("format", "keep_alive"):
            if key in params:
                form_data[key] = params[key]
    else:
        for key in _OPENAI_PARAM_KEYS:
            if key in params:
                form_data[key] = params[key]

        if "logit_bias" in params:
            try:
                form_data["logit_bias"] = orjson.loads(
                    convert_logit_bias_input_to_json(params["logit_bias"])
                )
            except Exception as exc:
                log.warning("Error parsing logit_bias: %s", exc)

    return form_data


# ---------------------------------------------------------------------------
# Section: Context compression & smart query handlers
# ---------------------------------------------------------------------------


async def chat_context_compression_handler(
    request: Request,
    form_data: dict,
    extra_params: dict,
    user: UserModel,
) -> tuple[dict, dict]:
    """Compress older messages into a summary to reduce context length.

    Keeps the most recent messages intact and replaces older ones with
    an LLM-generated summary.
    """
    messages = form_data.get("messages", [])
    min_messages = 6
    if len(messages) < min_messages:
        log.debug(
            "Skipping context compression: %d messages (need %d)",
            len(messages),
            min_messages,
        )
        return form_data, {}

    keep_recent = 4
    messages_to_compress = messages[:-keep_recent]
    event_emitter = extra_params.get("__event_emitter__")

    if event_emitter:
        await _emit_status(
            event_emitter,
            "context_compression",
            "Compressing conversation history...",
        )

    try:
        models = _get_models_for_request(request)
        task_model_id = _resolve_task_model(request, form_data["model"], models)

        compression_model = request.app.state.config.CONTEXT_COMPRESSION_MODEL
        if compression_model:
            task_model_id = compression_model

        res = await generate_context_compression(
            request,
            {
                "model": task_model_id,
                "messages": messages_to_compress,
                "chat_id": form_data.get("chat_id"),
            },
            user,
        )

        summary: str | None = None
        if isinstance(res, Response):
            try:
                body = orjson.loads(res.body)
                if "detail" in body:
                    log.debug(
                        "Context compression skipped: %s",
                        body["detail"],
                    )
                    return form_data, {}
            except Exception:
                pass
        else:
            summary = _task_completion_content(res)

        if summary:
            summary_message = {
                "role": "system",
                "content": ("[Previous Conversation Summary]\n" "%s" % summary.strip()),
            }
            form_data["messages"] = [summary_message] + messages[-keep_recent:]
            log.debug(
                "Context compression complete: %d messages "
                "compressed to summary + %d recent",
                len(messages),
                keep_recent,
            )

        if event_emitter:
            await _emit_status(
                event_emitter,
                "context_compression",
                "Conversation history compressed",
                done=True,
            )

        return form_data, {}

    except Exception as exc:
        log.exception("Context compression error: %s", exc)
        if event_emitter:
            await _emit_status(
                event_emitter,
                "context_compression",
                "Context compression failed, using full history",
                done=True,
            )
        return form_data, {}


async def chat_smart_query_handler(
    request: Request,
    form_data: dict,
    extra_params: dict,
    user: UserModel,
) -> tuple[dict, dict]:
    """Enhance the user's query with conversation context using an LLM.

    Returns ``(form_data, flags)`` where *flags* contains
    ``"enhanced_query"``.
    """
    messages = form_data.get("messages", [])
    user_message = get_last_user_message(messages)

    if len(messages) < 3:
        log.debug("Skipping smart query: only %d messages", len(messages))
        return form_data, {"enhanced_query": user_message}

    event_emitter = extra_params.get("__event_emitter__")
    if event_emitter:
        await _emit_status(
            event_emitter,
            "smart_query",
            "Enhancing query with conversation context...",
        )

    try:
        models = _get_models_for_request(request)
        task_model_id = _resolve_task_model(request, form_data["model"], models)

        smart_model = request.app.state.config.SMART_QUERY_MODEL
        if smart_model:
            task_model_id = smart_model

        res = await generate_smart_query(
            request,
            {
                "model": task_model_id,
                "messages": messages,
                "prompt": user_message,
                "chat_id": form_data.get("chat_id"),
            },
            user,
        )

        enhanced_query: str | None = None
        if isinstance(res, Response):
            try:
                body = orjson.loads(res.body)
                if "detail" in body:
                    log.debug("Smart query skipped: %s", body["detail"])
                    return form_data, {"enhanced_query": user_message}
            except Exception:
                pass
        else:
            response_text = _task_completion_content(res)
            if response_text:
                json_str = _extract_json_object(response_text)
                if json_str:
                    try:
                        parsed = orjson.loads(json_str)
                        enhanced_query = parsed.get("query", user_message)
                    except Exception:
                        enhanced_query = response_text
                else:
                    enhanced_query = response_text

        if not enhanced_query:
            enhanced_query = user_message

        # Named-entity preservation: a single rewritten query must keep every
        # explicit entity from the original; otherwise fall back to the original.
        if request.app.state.config.QUERY_REWRITE_ENTITY_GUARD_ENABLED:
            enhanced_query, _eq_ok = guard_rewrite(user_message, enhanced_query)
            if not _eq_ok:
                log.warning(
                    "Smart query rewrite dropped named entities; "
                    "using the original user message."
                )

        log.debug(
            "Smart query: enhanced from %d chars to %d chars",
            len(user_message),
            len(enhanced_query),
        )

        if event_emitter:
            await _emit_status(
                event_emitter,
                "smart_query",
                "Query enhanced with conversation context",
                done=True,
            )

        return form_data, {"enhanced_query": enhanced_query}

    except Exception as exc:
        log.exception("Smart query error: %s", exc)
        if event_emitter:
            await _emit_status(
                event_emitter,
                "smart_query",
                "Smart query failed, using original query",
                done=True,
            )
        return form_data, {"enhanced_query": user_message}


# ---------------------------------------------------------------------------
# Section: Security scanning helpers
# ---------------------------------------------------------------------------


# Tracks fire-and-forget advisory security scans so the event loop keeps a
# strong reference until they finish (otherwise they can be garbage-collected
# mid-flight). Used in shadow mode, where scans only log and never block — so
# they must not sit on the request critical path and inflate TTFT.
_BACKGROUND_SCAN_TASKS: set = set()


def _run_scan_in_background(coro, label: str) -> None:
    """Schedule an advisory scan coroutine without awaiting it."""
    try:
        task = asyncio.ensure_future(coro)
    except RuntimeError:
        # No running loop (not expected on the request path) — don't leak the coro.
        coro.close()
        return

    _BACKGROUND_SCAN_TASKS.add(task)

    def _on_done(finished):
        _BACKGROUND_SCAN_TASKS.discard(finished)
        if not finished.cancelled() and finished.exception() is not None:
            log.warning("Background %s failed: %s", label, finished.exception())

    task.add_done_callback(_on_done)


async def _scan_input_security(
    request: Request,
    form_data: dict,
    user: UserModel,
    metadata: dict,
) -> None:
    """Scan the user's input message for security threats.

    Raises ``SecurityException`` or ``PIIBlockException`` when threats
    are detected that warrant blocking.

    In shadow mode the scan can never block (``should_block`` is always
    ``False``), so only the fast regex scanners — which still drive PII
    masking/blocking — run on the critical path; the slow LLM scanners run in
    the background purely for detection logging and don't gate TTFT.
    """
    config = request.app.state.config
    if not config.SECURITY_SCANNER_ENABLED:
        return

    from bcgpt.utils.security import (
        BLOCKED_MESSAGE_KO,
        PII_BLOCKED_MESSAGE_KO,
        PIIBlockException,
        SecurityException,
        SecurityPipeline,
    )

    pipeline = SecurityPipeline(config)
    user_message = get_last_user_message(form_data.get("messages", []))
    if not user_message:
        return

    user_info = _user_info_dict(user)
    scan_metadata = {
        "chat_id": (metadata.get("chat_id") if metadata else None),
        "message_id": (metadata.get("message_id") if metadata else None),
        "session_id": form_data.get("session_id"),
        "model_id": form_data.get("model", ""),
    }

    shadow = bool(getattr(config, "SECURITY_SHADOW_MODE", False))
    llm_active = bool(getattr(config, "SECURITY_LLM_SCANNER_ENABLED", False)) or bool(
        getattr(config, "SECURITY_GUARDRAIL_ENABLED", False)
    )

    if shadow and llm_active:
        # Critical path: regex-only (fast). PII mask/block still enforced.
        security_result = await pipeline.scan_input(
            user_message,
            user_info,
            metadata=scan_metadata,
            request=request,
            skip_llm=True,
        )
        # Advisory: full LLM scan off the critical path (logs detections itself).
        _run_scan_in_background(
            pipeline.scan_input(
                user_message,
                user_info,
                metadata=scan_metadata,
                request=request,
                skip_llm=False,
            ),
            "input security scan",
        )
    else:
        security_result = await pipeline.scan_input(
            user_message,
            user_info,
            metadata=scan_metadata,
            request=request,
        )

    if pipeline.should_block(security_result):
        raise SecurityException(BLOCKED_MESSAGE_KO, security_result.threats)
    if pipeline.should_block_pii(security_result):
        raise PIIBlockException(PII_BLOCKED_MESSAGE_KO, security_result.threats)

    # PII masking
    if security_result.masked_text is not None and metadata:
        await _apply_pii_masking(
            request,
            form_data,
            metadata,
            user,
            security_result,
        )


async def _apply_pii_masking(
    request: Request,
    form_data: dict,
    metadata: dict,
    user: UserModel,
    security_result: Any,
) -> None:
    """Replace PII in stored messages with masked text (best-effort)."""
    try:
        masked_content = security_result.masked_text
        messages = form_data.get("messages", [])

        # Mask in the in-flight messages
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                messages[i]["content"] = masked_content
                break

        # Mask in the persisted chat messages
        if metadata.get("chat_id") and metadata.get("message_id"):
            chat_messages = Chats.get_messages_by_chat_id(metadata["chat_id"])
            if chat_messages:
                response_msg = chat_messages.get(metadata["message_id"], {})
                user_msg_id = response_msg.get("parentId")
                if user_msg_id:
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        user_msg_id,
                        {"content": masked_content},
                    )
                    log.info(
                        "PII masked in chat %s, user message %s",
                        metadata["chat_id"],
                        user_msg_id,
                    )

                    event_emitter = get_event_emitter(metadata)
                    await event_emitter(
                        {
                            "type": "pii_masked",
                            "data": {
                                "user_message_id": user_msg_id,
                                "masked_content": masked_content,
                            },
                        }
                    )

                    # Audit log
                    try:
                        pii_types = list(
                            {t.pattern_name for t in security_result.threats}
                        )
                        AuditLogs.insert_log(
                            AuditLogForm(
                                user_id=user.id,
                                user_email=user.email,
                                action="PII_MASKED",
                                resource_type="message",
                                resource_id=user_msg_id,
                                severity="WARNING",
                                category="security",
                                audit_details={
                                    "chat_id": metadata.get("chat_id"),
                                    "threat_types": pii_types,
                                    "threat_count": len(security_result.threats),
                                },
                            )
                        )
                    except Exception as audit_err:
                        log.warning(
                            "Failed to create PII audit log: %s",
                            audit_err,
                        )
    except Exception as exc:
        log.warning(
            "Failed to apply PII masking to stored message: %s",
            exc,
        )


async def _scan_conversation_security(
    request: Request,
    form_data: dict,
    user: UserModel,
    metadata: dict,
) -> None:
    """Scan the full conversation for security threats."""
    if not (
        request.app.state.config.SECURITY_SCANNER_ENABLED
        and request.app.state.config.SECURITY_CONVERSATION_SCANNING_ENABLED
    ):
        return

    from bcgpt.utils.security import (
        BLOCKED_MESSAGE_KO,
        SecurityException,
        SecurityPipeline,
    )

    pipeline = SecurityPipeline(request.app.state.config)
    scan_metadata = {
        "chat_id": (metadata.get("chat_id") if metadata else None),
        "session_id": form_data.get("session_id"),
        "model_id": form_data.get("model", ""),
    }

    # Shadow mode can never block, so the multi-turn scan is purely advisory —
    # run it in the background instead of gating the response on it.
    if bool(getattr(request.app.state.config, "SECURITY_SHADOW_MODE", False)):
        _run_scan_in_background(
            pipeline.scan_conversation(
                form_data.get("messages", []),
                _user_info_dict(user),
                metadata=scan_metadata,
                request=request,
            ),
            "conversation security scan",
        )
        return

    try:
        result = await pipeline.scan_conversation(
            form_data.get("messages", []),
            _user_info_dict(user),
            metadata=scan_metadata,
            request=request,
        )
        if pipeline.should_block(result):
            raise SecurityException(BLOCKED_MESSAGE_KO, result.threats)
    except SecurityException:
        raise
    except Exception as exc:
        log.exception("Conversation security scan error: %s", exc)


async def _scan_file_uploads(
    request: Request,
    sources: list[dict],
    user: UserModel,
    metadata: dict,
    form_data: dict,
) -> None:
    """Scan uploaded file content for security threats."""
    if not (
        request.app.state.config.SECURITY_SCANNER_ENABLED
        and request.app.state.config.SECURITY_SCAN_FILE_UPLOADS
        and sources
    ):
        return

    from bcgpt.utils.security import (
        BLOCKED_MESSAGE_KO,
        SecurityException,
        SecurityPipeline,
    )

    try:
        pipeline = SecurityPipeline(request.app.state.config)
        file_content_parts = [
            doc for source in sources for doc in source.get("document", []) if doc
        ]
        if not file_content_parts:
            return

        file_content = "\n".join(file_content_parts)
        file_names = [
            s.get("source", {}).get("name", "unknown")
            for s in sources
            if s.get("source", {}).get("name")
        ]

        scan_result = await pipeline.scan_input(
            file_content,
            _user_info_dict(user),
            metadata={
                "source": "file_upload",
                "file_names": file_names,
                "chat_id": (metadata.get("chat_id") if metadata else None),
                "message_id": (metadata.get("message_id") if metadata else None),
                "model_id": form_data.get("model", ""),
            },
        )
        if pipeline.should_block(scan_result):
            raise SecurityException(BLOCKED_MESSAGE_KO, scan_result.threats)
    except SecurityException:
        raise
    except Exception as exc:
        log.exception("File upload security scan error: %s", exc)


async def _scan_output(
    request: Request,
    content: str,
    metadata: dict,
    form_data: dict,
    user: UserModel,
) -> tuple[str, bool]:
    """Scan model output for security issues.

    Returns ``(content, was_sanitized)``.
    """
    if not (
        request.app.state.config.SECURITY_SCANNER_ENABLED
        and request.app.state.config.SECURITY_OUTPUT_FILTER_ENABLED
    ):
        return content, False

    try:
        from bcgpt.utils.security import SecurityPipeline

        pipeline = SecurityPipeline(request.app.state.config)
        result = await pipeline.scan_output(
            content,
            metadata={
                "chat_id": metadata["chat_id"],
                "message_id": metadata["message_id"],
                "model_id": form_data.get("model", ""),
                "session_id": metadata.get("session_id"),
            },
            request=request,
            user=user,
        )
        if result.masked_text and not request.app.state.config.SECURITY_SHADOW_MODE:
            return result.masked_text, True
    except Exception as exc:
        log.exception("Output security scan error: %s", exc)

    return content, False


# ---------------------------------------------------------------------------
# Section: Top-level payload processing
# ---------------------------------------------------------------------------


async def process_chat_payload(
    request: Request,
    form_data: dict,
    user: UserModel,
    metadata: dict,
    model: dict,
) -> tuple[dict, dict, list[dict]]:
    """Pre-process a chat completion request before forwarding to the LLM.

    Orchestrates parameter mapping, pipeline inlet filters, security
    scanning, rate limiting, tool resolution, web search, RAG retrieval,
    context compression, and smart query enhancement.

    Returns ``(form_data, metadata, events)``.
    """
    form_data = apply_params_to_form_data(form_data, model)
    log.debug(
        "process_chat_payload: model=%s, messages=%d",
        form_data.get("model", "?"),
        len(form_data.get("messages", [])),
    )

    event_emitter = get_event_emitter(metadata)
    event_call = get_event_call(metadata)

    extra_params: dict[str, Any] = {
        "__event_emitter__": event_emitter,
        "__event_call__": event_call,
        "__user__": _user_info_dict(user),
        "__metadata__": metadata,
        "__request__": request,
        "__model__": model,
    }

    models = _get_models_for_request(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    events: list[dict] = []
    sources: list[dict] = []

    user_message = get_last_user_message(form_data["messages"])
    model_knowledge = model.get("info", {}).get("meta", {}).get("knowledge", False)

    # --- Skills: Layer-1 catalog (always-on name+description in system prompt) ---
    try:
        from bcgpt.utils.extensions import resolve_effective_skills
        from bcgpt.utils.skill_runtime import build_skill_catalog

        _active_skills = resolve_effective_skills(user, metadata.get("skill_ids"))
        _catalog_text = build_skill_catalog(_active_skills)
        if _catalog_text:
            form_data["messages"] = add_or_update_system_message(
                _catalog_text, form_data["messages"]
            )
    except Exception as _exc:
        log.debug("Skill catalog injection skipped: %s", _exc)

    # --- Model knowledge ---
    if model_knowledge:
        await _emit_status(
            event_emitter,
            "knowledge_search",
            "Searching knowledge base",
            query=user_message,
        )
        knowledge_files: list[dict] = []
        for item in model_knowledge:
            if item.get("collection_name"):
                knowledge_files.append(
                    {
                        "id": item.get("collection_name"),
                        "name": item.get("name"),
                        "legacy": True,
                        "__model_knowledge__": True,
                    }
                )
            elif item.get("collection_names"):
                knowledge_files.append(
                    {
                        "name": item.get("name"),
                        "type": "collection",
                        "collection_names": item.get("collection_names"),
                        "legacy": True,
                        "__model_knowledge__": True,
                    }
                )
            else:
                knowledge_files.append({**item, "__model_knowledge__": True})

        files = form_data.get("files", [])
        files.extend(knowledge_files)
        form_data["files"] = files

    form_data.pop("variables", None)

    # --- Pipeline inlet filter ---
    try:
        form_data = await process_pipeline_inlet_filter(
            request, form_data, user, models
        )
    except Exception:
        raise

    # --- Rate limiting ---
    if request.app.state.config.RATE_LIMIT_CHAT_ENABLED:
        from bcgpt.utils.per_user_rate_limit import rate_limiter

        client_id = (
            "user:%s" % user.id
            if user
            else "ip:%s" % (request.client.host if request.client else "unknown")
        )
        if user.role != "admin":
            allowed, error_msg = rate_limiter.check_rate_limit(
                client_id,
                max_per_minute=(request.app.state.config.RATE_LIMIT_CHAT_PER_MINUTE),
                max_per_hour=(request.app.state.config.RATE_LIMIT_CHAT_PER_HOUR),
                max_per_day=(request.app.state.config.RATE_LIMIT_CHAT_PER_DAY),
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail={"message": error_msg},
                )

    # --- Token budget (OWASP LLM10 denial-of-wallet) pre-flight ---
    if request.app.state.config.TOKEN_BUDGET_ENABLED and user and user.role != "admin":
        from bcgpt.utils.per_user_rate_limit import token_budget_limiter

        budget_client_id = "user:%s" % user.id
        daily_cap = int(request.app.state.config.TOKEN_BUDGET_DAILY or 0)
        per_min_cap = int(request.app.state.config.TOKEN_BUDGET_PER_MIN or 0)
        # Per-group overrides (most-permissive) via groups.permissions.token_budget.
        try:
            from bcgpt.utils.access_control import get_permissions

            tb = (get_permissions(user.id, {}) or {}).get("token_budget") or {}
            if tb.get("daily_tokens"):
                daily_cap = int(tb["daily_tokens"])
            if tb.get("per_minute_tokens"):
                per_min_cap = int(tb["per_minute_tokens"])
        except Exception:
            pass
        allowed, error_msg = token_budget_limiter.check_token_budget(
            budget_client_id, daily_cap=daily_cap, per_min_cap=per_min_cap
        )
        if not allowed:
            raise HTTPException(status_code=429, detail={"message": error_msg})

    # --- Emergency stop ---
    if request.app.state.config.SECURITY_EMERGENCY_STOP:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": (
                    "AI service has been temporarily suspended by "
                    "the administrator. Please try again later."
                ),
                "message_en": (
                    "AI service has been temporarily suspended by "
                    "the administrator. Please try again later."
                ),
            },
        )

    # --- Input security scanning ---
    await _scan_input_security(request, form_data, user, metadata)
    await _scan_conversation_security(request, form_data, user, metadata)

    # --- Filter functions ---
    try:
        filter_functions = [
            Functions.get_function_by_id(fid) for fid in get_sorted_filter_ids(model)
        ]
        form_data, _ = await process_filter_functions(
            request=request,
            filter_functions=filter_functions,
            filter_type="inlet",
            form_data=form_data,
            extra_params=extra_params,
        )
    except Exception as exc:
        raise Exception("Error: %s" % exc) from exc

    # --- Feature extraction ---
    features = form_data.pop("features", None)
    tool_ids = form_data.pop("tool_ids", None)
    files = form_data.pop("files", None)

    # Deduplicate files
    if files:
        files = list(
            {orjson.dumps(f, option=orjson.OPT_SORT_KEYS): f for f in files}.values()
        )

    metadata = {**metadata, "tool_ids": tool_ids, "files": files}
    form_data["metadata"] = metadata

    # --- Image generation ---
    if features and features.get("image_generation"):
        form_data = await chat_image_generation_handler(
            request, form_data, extra_params, user
        )

    # --- Context compression & smart query (parallel) ---
    compression_enabled = features and features.get("context_compression", False)
    smart_query_enabled = features and features.get("smart_query", False)

    if compression_enabled or smart_query_enabled:
        try:
            if compression_enabled and smart_query_enabled:
                comp_result, sq_result = await asyncio.gather(
                    chat_context_compression_handler(
                        request, form_data, extra_params, user
                    ),
                    chat_smart_query_handler(request, form_data, extra_params, user),
                    return_exceptions=True,
                )
                if not isinstance(comp_result, Exception):
                    form_data, _ = comp_result
                else:
                    log.error("Context compression error: %s", comp_result)

                if not isinstance(sq_result, Exception):
                    _, sq_flags = sq_result
                    if sq_flags.get("enhanced_query"):
                        form_data["__enhanced_query__"] = sq_flags["enhanced_query"]
                else:
                    log.error("Smart query error: %s", sq_result)
            elif compression_enabled:
                form_data, _ = await chat_context_compression_handler(
                    request, form_data, extra_params, user
                )
            elif smart_query_enabled:
                _, sq_flags = await chat_smart_query_handler(
                    request, form_data, extra_params, user
                )
                if sq_flags.get("enhanced_query"):
                    form_data["__enhanced_query__"] = sq_flags["enhanced_query"]
        except Exception as exc:
            log.exception("Context compression/smart query error: %s", exc)

    # --- Tool resolution ---
    tool_ids = metadata.get("tool_ids")
    tool_servers = metadata.get("tool_servers")
    log.debug("tool_ids=%s", tool_ids)
    log.debug("tool_servers=%s", tool_servers)

    tools_dict: dict[str, Any] = {}

    if tool_ids:
        tools_dict = get_tools(
            request,
            tool_ids,
            user,
            {
                **extra_params,
                "__model__": models[task_model_id],
                "__messages__": form_data["messages"],
                "__files__": metadata.get("files", []),
            },
        )

    # --- Skills: Layer-2 read_skill tool (registered when any skill is active) ---
    try:
        from bcgpt.utils.extensions import resolve_effective_skills
        from bcgpt.utils.skill_runtime import make_read_skill_descriptor

        if resolve_effective_skills(user, metadata.get("skill_ids")):
            if not tools_dict:
                tools_dict = {}
            tools_dict.setdefault("read_skill", make_read_skill_descriptor(user))
    except Exception as _exc:
        log.debug("read_skill registration skipped: %s", _exc)

    # --- MCP: register server-side-executed MCP tools into tools_dict ---
    try:
        from bcgpt.mcpbridge.client import McpClient
        from bcgpt.mcpbridge.registry import make_mcp_tool_descriptor
        from bcgpt.utils.extensions import resolve_effective_mcp_servers

        for srv in resolve_effective_mcp_servers(user, metadata.get("mcp_server_ids")):
            try:
                _mcp_client = McpClient(srv)
                await _mcp_client.connect()
                _mcp_tools = await _mcp_client.list_tools()
                await _mcp_client.close()
            except Exception as _e:
                log.debug("MCP server %s discovery failed: %s", srv.get("id"), _e)
                continue
            if not tools_dict:
                tools_dict = {}
            for _t in _mcp_tools:
                _desc = make_mcp_tool_descriptor(srv, _t)
                tools_dict.setdefault(_desc["spec"]["name"], _desc)
    except Exception as _exc:
        log.debug("MCP tool registration skipped: %s", _exc)

    if tool_servers:
        for tool_server in tool_servers:
            tool_specs = tool_server.pop("specs", [])
            for tool in tool_specs:
                tools_dict[tool["name"]] = {
                    "spec": tool,
                    "direct": True,
                    "server": tool_server,
                }

    if tools_dict:
        if metadata.get("function_calling") == "native":
            metadata["tools"] = tools_dict
            form_data["tools"] = [
                {
                    "type": "function",
                    "function": t.get("spec", {}),
                }
                for t in tools_dict.values()
            ]
        else:
            try:
                form_data, flags = await chat_completion_tools_handler(
                    request,
                    form_data,
                    extra_params,
                    user,
                    models,
                    tools_dict,
                )
                sources.extend(flags.get("sources", []))
            except Exception as exc:
                log.exception("Tool calling error: %s", exc)

    # --- Web search + RAG (parallel when web search enabled) ---
    web_search_enabled = features and features.get("web_search", False)

    try:
        if web_search_enabled:
            web_form_data = {
                k: v
                for k, v in form_data.items()
                if k in ("messages", "model", "chat_id")
            }
            web_form_data["files"] = []

            web_result, rag_result = await asyncio.gather(
                chat_web_search_handler(request, web_form_data, extra_params, user),
                chat_completion_files_handler(request, form_data, user, model),
                return_exceptions=True,
            )

            if not isinstance(rag_result, Exception):
                form_data, flags = rag_result
                sources.extend(flags.get("sources", []))
            else:
                log.error(
                    "RAG search error in parallel execution: %s",
                    rag_result,
                )

            if not isinstance(web_result, Exception):
                web_files = web_result.get("files", [])
                if web_files:
                    current_files = form_data.get("metadata", {}).get("files", [])
                    current_files.extend(web_files)
                    form_data["metadata"] = {
                        **form_data.get("metadata", {}),
                        "files": current_files,
                    }

                    # Phase 2: RAG for web search results
                    try:
                        web_rag_body = {**form_data}
                        web_rag_body["metadata"] = {
                            **form_data.get("metadata", {}),
                            "files": web_files,
                        }
                        _, web_flags = await chat_completion_files_handler(
                            request,
                            web_rag_body,
                            user,
                            model,
                        )
                        sources.extend(web_flags.get("sources", []))
                    except Exception as exc:
                        log.exception(
                            "Web search RAG processing error: %s",
                            exc,
                        )
            else:
                log.error(
                    "Web search error in parallel execution: %s",
                    web_result,
                )
        else:
            form_data, flags = await chat_completion_files_handler(
                request, form_data, user, model
            )
            sources.extend(flags.get("sources", []))

        # --- File upload security scan ---
        await _scan_file_uploads(request, sources, user, metadata, form_data)

    except Exception as exc:
        from bcgpt.utils.security import (
            SecurityException as _SE,
        )

        if isinstance(exc, _SE):
            raise
        log.exception("Payload processing error: %s", exc)

    # --- Inject RAG context into messages ---
    if sources:
        # Content isolation / spotlighting: defensively wrap untrusted external
        # content (RAG/web/tool results) so the model treats it as DATA only.
        _ci_enabled = bool(request.app.state.config.CONTENT_ISOLATION_ENABLED)
        _ci_method = request.app.state.config.CONTENT_ISOLATION_METHOD or "datamarking"
        context_string = ""
        for source_idx, source in enumerate(sources):
            for doc_context in source.get("document", []):
                if _ci_enabled:
                    doc_context = isolate_block(doc_context, _ci_method)
                context_string += (
                    "<source>"
                    "<source_id>%d</source_id>"
                    "<source_context>%s</source_context>"
                    "</source>\n" % (source_idx + 1, doc_context)
                )
        context_string = context_string.strip()
        prompt = get_last_user_message(form_data["messages"])

        if prompt is None:
            raise Exception("No user message found")

        if (
            request.app.state.config.RELEVANCE_THRESHOLD == 0
            and not context_string.strip()
        ):
            log.debug(
                "With a 0 relevancy threshold for RAG, " "the context cannot be empty"
            )

        rag_tpl = (
            _get_rag_override(model, request.app.state.config).get("rag_template")
            or request.app.state.config.RAG_TEMPLATE
        )
        rag_content = rag_template(rag_tpl, context_string, prompt)

        if _ci_enabled:
            # Prepend the data-only directive so the wrapping has an instruction.
            rag_content = get_isolation_instruction(_ci_method) + "\n\n" + rag_content

        if model.get("owned_by") == "ollama":
            form_data["messages"] = prepend_to_first_user_message_content(
                rag_content, form_data["messages"]
            )
        else:
            form_data["messages"] = add_or_update_system_message(
                rag_content, form_data["messages"]
            )

    # --- Citations ---
    sources = [s for s in sources if s.get("source", {}).get("name", "")]
    if sources:
        events.append({"sources": sources})

    if model_knowledge:
        await _emit_status(
            event_emitter,
            "knowledge_search",
            "Knowledge search complete",
            query=user_message,
            done=True,
        )
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "knowledge_search",
                    "query": user_message,
                    "done": True,
                    "hidden": True,
                },
            }
        )

    return form_data, metadata, events


# ---------------------------------------------------------------------------
# Section: Streaming content helpers
# ---------------------------------------------------------------------------

_REASONING_TAGS = [
    ("think", "/think"),
    ("thinking", "/thinking"),
    ("reason", "/reason"),
    ("reasoning", "/reasoning"),
    ("thought", "/thought"),
    ("Thought", "/Thought"),
    ("|begin_of_thought|", "|end_of_thought|"),
]

_SOLUTION_TAGS = [
    ("|begin_of_solution|", "|end_of_solution|"),
]


def _serialize_content_blocks(content_blocks: list[dict], *, raw: bool = False) -> str:
    """Render content blocks into a display string."""
    parts: list[str] = []

    for block in content_blocks:
        if block["type"] == "text":
            parts.append(block["content"].strip())

        elif block["type"] == "tool_calls":
            tool_calls = block.get("content", [])
            results = block.get("results", [])

            if results and not raw:
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    tc_name = tc.get("function", {}).get("name", "")
                    tc_args = tc.get("function", {}).get("arguments", "")
                    tc_result = None
                    for r in results:
                        if tc_id == r.get("tool_call_id", ""):
                            tc_result = r.get("content")
                            break

                    if tc_result is not None:
                        parts.append(
                            '\n<details type="tool_calls" '
                            'done="true" id="%s" '
                            'name="%s" '
                            'arguments="%s" '
                            'result="%s">\n'
                            "<summary>Tool Executed</summary>\n"
                            "</details>"
                            % (
                                tc_id,
                                tc_name,
                                html.escape(orjson.dumps(tc_args).decode()),
                                html.escape(orjson.dumps(tc_result).decode()),
                            )
                        )
                    else:
                        parts.append(
                            '\n<details type="tool_calls" '
                            'done="false" id="%s" '
                            'name="%s" '
                            'arguments="%s">\n'
                            "<summary>Executing...</summary>\n"
                            "</details>"
                            % (
                                tc_id,
                                tc_name,
                                html.escape(orjson.dumps(tc_args).decode()),
                            )
                        )
            elif not raw:
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    tc_name = tc.get("function", {}).get("name", "")
                    tc_args = tc.get("function", {}).get("arguments", "")
                    parts.append(
                        '\n<details type="tool_calls" '
                        'done="false" id="%s" '
                        'name="%s" '
                        'arguments="%s">\n'
                        "<summary>Executing...</summary>\n"
                        "</details>"
                        % (
                            tc_id,
                            tc_name,
                            html.escape(orjson.dumps(tc_args).decode()),
                        )
                    )

        elif block["type"] == "reasoning":
            display = "\n".join(
                ("> %s" % line if not line.startswith(">") else line)
                for line in block["content"].splitlines()
            )
            duration = block.get("duration")

            if raw:
                parts.append(
                    "\n<%s>%s<%s>\n"
                    % (block["start_tag"], block["content"], block["end_tag"])
                )
            elif duration is not None:
                parts.append(
                    '\n<details type="reasoning" done="true" '
                    'duration="%s">\n'
                    "<summary>Thought for %s seconds</summary>\n"
                    "%s\n</details>\n" % (duration, duration, display)
                )
            else:
                parts.append(
                    '\n<details type="reasoning" done="false">\n'
                    "<summary>Thinking...</summary>\n"
                    "%s\n</details>\n" % display
                )
        else:
            block_content = str(block["content"]).strip()
            parts.append("%s: %s" % (block["type"], block_content))

    return "\n".join(parts).strip()


def _convert_blocks_to_messages(
    content_blocks: list[dict],
) -> list[dict]:
    """Convert content blocks into OpenAI-style messages."""
    messages: list[dict] = []
    temp: list[dict] = []

    for block in content_blocks:
        if block["type"] == "tool_calls":
            messages.append(
                {
                    "role": "assistant",
                    "content": _serialize_content_blocks(temp),
                    "tool_calls": block.get("content"),
                }
            )
            for r in block.get("results", []):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": r["tool_call_id"],
                        "content": r["content"],
                    }
                )
            temp = []
        else:
            temp.append(block)

    if temp:
        content = _serialize_content_blocks(temp)
        if content:
            messages.append({"role": "assistant", "content": content})

    return messages


def _tag_content_handler(
    content_type: str,
    tags: list[tuple[str, str]],
    content: str,
    content_blocks: list[dict],
) -> tuple[str, list[dict], bool]:
    """Detect and extract tagged content (reasoning, solution blocks).

    Returns ``(content, content_blocks, end_flag)``.
    """
    end_flag = False

    def _extract_attrs(tag_content: str) -> dict[str, str]:
        if not tag_content:
            return {}
        return dict(re.findall(r'(\w+)\s*=\s*"([^"]+)"', tag_content))

    if not content_blocks:
        return content, content_blocks, end_flag

    last = content_blocks[-1]

    if last["type"] == "text":
        for start_tag, end_tag in tags:
            pattern = r"<%s(\s.*?)?>" % re.escape(start_tag)
            match = re.search(pattern, content)
            if not match:
                continue

            attr_content = match.group(1) or ""
            attributes = _extract_attrs(attr_content)
            before_tag = content[: match.start()]
            after_tag = content[match.end() :]

            content_blocks[-1]["content"] = content_blocks[-1]["content"].replace(
                match.group(0) + after_tag, ""
            )
            if before_tag:
                content_blocks[-1]["content"] = before_tag
            if not content_blocks[-1]["content"]:
                content_blocks.pop()

            content_blocks.append(
                {
                    "type": content_type,
                    "start_tag": start_tag,
                    "end_tag": end_tag,
                    "attributes": attributes,
                    "content": "",
                    "started_at": time.time(),
                }
            )
            if after_tag:
                content_blocks[-1]["content"] = after_tag
            break

    elif last["type"] == content_type:
        start_tag = last["start_tag"]
        end_tag = last["end_tag"]
        end_pattern = r"</%s>" % re.escape(end_tag)

        if re.search(end_pattern, content):
            end_flag = True
            block_content = last["content"]
            block_content = re.sub(
                r"<%s(.*?)>" % re.escape(start_tag),
                "",
                block_content,
            ).strip()

            split = re.compile(end_pattern, re.DOTALL).split(block_content, maxsplit=1)
            inner = split[0].strip() if split else ""
            leftover = split[1].strip() if len(split) > 1 else ""

            if inner:
                last["content"] = inner
                last["ended_at"] = time.time()
                last["duration"] = int(last["ended_at"] - last["started_at"])
                content_blocks.append({"type": "text", "content": leftover})
            else:
                content_blocks.pop()
                content_blocks.append({"type": "text", "content": leftover})

            content = re.sub(
                r"<%s(.*?)>(.|\n)*?</%s>" % (re.escape(start_tag), re.escape(end_tag)),
                "",
                content,
                flags=re.DOTALL,
            )

    return content, content_blocks, end_flag


# ---------------------------------------------------------------------------
# Section: Top-level response processing
# ---------------------------------------------------------------------------


async def _send_webhook(
    request: Request,
    user: UserModel,
    title: str,
    content: str,
    chat_id: str,
) -> None:
    """Send a webhook notification if the user is not active."""
    if get_active_status_by_user_id(user.id) is not None:
        return
    webhook_url = Users.get_user_webhook_url_by_id(user.id)
    if not webhook_url:
        return

    chat_url = "%s/c/%s" % (
        request.app.state.config.BCGPT_URL,
        chat_id,
    )
    post_webhook(
        request.app.state.BCGPT_APP_NAME,
        webhook_url,
        "%s - %s\n\n%s" % (title, chat_url, content),
        {
            "action": "chat",
            "message": content,
            "title": title,
            "url": chat_url,
        },
    )


def _extract_title_from_response(res: dict, fallback: str) -> str:
    """Extract a chat title from a title-generation response."""
    if not res or not isinstance(res, dict):
        return fallback
    choices = res.get("choices", [])
    if len(choices) != 1:
        return fallback

    title_string = choices[0].get("message", {}).get("content", fallback)
    json_str = _extract_json_object(title_string)
    if json_str:
        try:
            title = orjson.loads(json_str).get("title", "")
            if title:
                return title
        except Exception:
            pass
    return fallback


def _strip_emojis(text: str) -> str:
    """Remove emoji characters from *text*."""
    return re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        r"\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        r"\u2702-\u27B0\u24C2-\U0001F251"
        r"\U0001f926-\U0001f937\U00010000-\U0010ffff"
        r"\u2600-\u26FF\u2700-\u27BF]",
        "",
        text,
    ).strip()


async def _generate_and_save_title(
    request: Request,
    message: dict,
    messages: list[dict],
    metadata: dict,
    user: UserModel,
    event_emitter: Any,
) -> None:
    """Generate, clean, and persist a chat title."""
    chat_id = metadata["chat_id"]
    res = await generate_title(
        request,
        {
            "model": message["model"],
            "messages": messages,
            "chat_id": chat_id,
        },
        user,
    )

    title = ""
    for attempt in range(3):
        current_res = (
            res
            if attempt == 0
            else await generate_title(
                request,
                {
                    "model": message["model"],
                    "messages": messages,
                    "chat_id": chat_id,
                },
                user,
            )
        )

        if current_res and isinstance(current_res, dict):
            title = _extract_title_from_response(
                current_res,
                messages[0].get("content", "New Chat"),
            )
            title = _strip_emojis(title)

        if title:
            break

    if not title:
        title = messages[0].get("content", "New Chat")

    Chats.update_chat_title_by_id(chat_id, title)
    await event_emitter({"type": "chat:title", "data": title})


async def _generate_and_save_tags(
    request: Request,
    message: dict,
    messages: list[dict],
    metadata: dict,
    user: UserModel,
    event_emitter: Any,
) -> None:
    """Generate and persist chat tags."""
    res = await generate_chat_tags(
        request,
        {
            "model": message["model"],
            "messages": messages,
            "chat_id": metadata["chat_id"],
        },
        user,
    )

    if not res or not isinstance(res, dict):
        return

    choices = res.get("choices", [])
    if len(choices) != 1:
        return

    tags_string = choices[0].get("message", {}).get("content", "")
    json_str = _extract_json_object(tags_string)
    if not json_str:
        return

    try:
        tags = orjson.loads(json_str).get("tags", [])
        Chats.update_chat_tags_by_id(metadata["chat_id"], tags, user)
        await event_emitter({"type": "chat:tags", "data": tags})
    except Exception:
        pass


async def process_chat_response(
    request: Request,
    response: dict | StreamingResponse,
    form_data: dict,
    user: UserModel,
    metadata: dict,
    model: dict,
    events: list[dict],
    tasks: set | dict,
) -> dict | StreamingResponse:
    """Post-process an LLM response (streaming or non-streaming).

    Handles content extraction, background tasks, output security
    scanning, semantic cache storage, and webhook notifications.
    """
    has_full_session = (
        metadata.get("session_id")
        and metadata.get("chat_id")
        and metadata.get("message_id")
    )

    event_emitter = get_event_emitter(metadata) if has_full_session else None
    event_caller = get_event_call(metadata) if has_full_session else None
    generation_id = metadata.get("generation_id")
    generation_user_id = str(metadata.get("user_id"))

    async def _terminalize_generation(status: str, reason: str) -> None:
        if not generation_id:
            return
        generation = await asyncio.to_thread(
            ChatGenerations.terminalize,
            generation_id,
            generation_user_id,
            status,
            reason,
        )
        if generation is None:
            log.error("Generation terminal authority missing: %s", generation_id)
            return
        await asyncio.to_thread(
            Chats.upsert_message_to_chat_by_id_and_message_id,
            generation.chat_id,
            generation.assistant_message_id,
            {
                "done": True,
                "generationId": generation.generation_id,
                "generationStatus": generation.status,
                "terminalReason": generation.terminal_reason,
            },
        )

    async def _background_tasks_handler() -> None:
        message_map = Chats.get_messages_by_chat_id(metadata["chat_id"])
        message = message_map.get(metadata["message_id"]) if message_map else None
        if not message or not tasks:
            return

        msgs = get_message_list(message_map, message.get("id"))

        if TASKS.TITLE_GENERATION in tasks and tasks[TASKS.TITLE_GENERATION]:
            await _generate_and_save_title(
                request,
                message,
                msgs,
                metadata,
                user,
                event_emitter,
            )
        elif len(msgs) == 2:
            title = msgs[0].get("content", "New Chat")
            Chats.update_chat_title_by_id(metadata["chat_id"], title)
            if event_emitter:
                await event_emitter(
                    {
                        "type": "chat:title",
                        "data": message.get("content", "New Chat"),
                    }
                )

        if TASKS.TAGS_GENERATION in tasks and tasks[TASKS.TAGS_GENERATION]:
            await _generate_and_save_tags(
                request,
                message,
                msgs,
                metadata,
                user,
                event_emitter,
            )

    # --- Non-streaming response ---
    if not isinstance(response, StreamingResponse):
        if not event_emitter:
            await _terminalize_generation("completed", "passthrough_response")
            return response

        response_has_error = "error" in response
        if "error" in response:
            error = response["error"].get("detail", response["error"])
            Chats.upsert_message_to_chat_by_id_and_message_id(
                metadata["chat_id"],
                metadata["message_id"],
                {"error": {"content": error}},
            )

        if "selected_model_id" in response:
            Chats.upsert_message_to_chat_by_id_and_message_id(
                metadata["chat_id"],
                metadata["message_id"],
                {"selectedModelId": response["selected_model_id"]},
            )

        choices = response.get("choices", [])
        content = ""
        if choices and choices[0].get("message", {}).get("content"):
            content = choices[0]["message"]["content"]

        if not content:
            await _terminalize_generation(
                "error" if response_has_error else "completed",
                "provider_error" if response_has_error else "empty_response",
            )
            return response

        content, output_sanitized = await _scan_output(
            request, content, metadata, form_data, user
        )

        await event_emitter({"type": "chat:completion", "data": response})

        # Deliver the completed response before any optional LLM work such as
        # title/tag generation. Those tasks can take several seconds and must
        # not leave the chat UI in its generating state after the provider has
        # already finished.
        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {"content": content},
        )
        title = Chats.get_chat_title_by_id(metadata["chat_id"])

        done_data: dict[str, Any] = {
            "done": True,
            "content": content,
            "title": title,
        }
        if output_sanitized:
            done_data["sanitized"] = True

        await event_emitter({"type": "chat:completion", "data": done_data})
        await _terminalize_generation("completed", "provider_completed")

        try:
            await _background_tasks_handler()
            title = Chats.get_chat_title_by_id(metadata["chat_id"])

            # Semantic cache store
            if form_data.get("__semantic_cache_miss__") and not output_sanitized:
                await _semantic_cache_store(
                    request,
                    form_data.get("__semantic_cache_query__", ""),
                    content,
                    _extract_sources_from_events(events),
                    user,
                )

            await _send_webhook(request, user, title, content, metadata["chat_id"])

            _log_ai_interaction(
                request,
                user,
                metadata,
                model,
                form_data,
                usage=response.get("usage") if isinstance(response, dict) else None,
                rag_source_count=len(_extract_sources_from_events(events)),
                tool_call_count=len(
                    ((response.get("choices") or [{}])[0].get("message") or {}).get(
                        "tool_calls"
                    )
                    or []
                ),
                output_sanitized=output_sanitized,
                web_search_used=_web_search_used_in_form(form_data),
                streaming=False,
            )
            _record_provenance(
                request,
                user,
                metadata,
                model,
                form_data,
                content,
                events,
                response.get("usage") if isinstance(response, dict) else None,
            )
            await _persist_token_usage(
                request,
                user,
                metadata,
                model,
                response.get("usage") if isinstance(response, dict) else None,
            )
        except Exception as exc:
            log.exception("Post-completion work failed: %s", exc)

        return response

    # --- Non-standard streaming ---
    if not any(
        ct in response.headers["Content-Type"]
        for ct in ["text/event-stream", "application/x-ndjson"]
    ):
        await _terminalize_generation("error", "untracked_stream_content_type")
        return response

    # --- Streaming response ---
    extra_params: dict[str, Any] = {
        "__event_emitter__": event_emitter,
        "__event_call__": event_caller,
        "__user__": _user_info_dict(user),
        "__metadata__": metadata,
        "__request__": request,
        "__model__": model,
    }
    filter_functions = [
        Functions.get_function_by_id(fid) for fid in get_sorted_filter_ids(model)
    ]

    if event_emitter and event_caller:
        return await _handle_streaming_response(
            request,
            response,
            form_data,
            user,
            metadata,
            model,
            events,
            tasks,
            event_emitter,
            event_caller,
            extra_params,
            filter_functions,
            _background_tasks_handler,
            _terminalize_generation,
        )
    else:
        return _handle_passthrough_streaming(
            response,
            events,
            request,
            extra_params,
            filter_functions,
        )


# ---------------------------------------------------------------------------
# Section: Streaming response handler
# ---------------------------------------------------------------------------


async def _handle_streaming_response(
    request: Request,
    response: StreamingResponse,
    form_data: dict,
    user: UserModel,
    metadata: dict,
    model: dict,
    events: list[dict],
    tasks: set | dict,
    event_emitter: Any,
    event_caller: Any,
    extra_params: dict,
    filter_functions: list,
    background_tasks_handler: Any,
    terminalize_generation: Any,
) -> dict:
    """Process a streaming chat completion response."""
    model_id = form_data.get("model", "")
    generation_id = metadata.get("generation_id")
    generation_user_id = str(metadata.get("user_id"))
    replay_last_write = 0.0
    generation_delivery_complete = False

    async def _emit_completion(
        data: dict, *, replay_content: str | None = None, force_replay: bool = False
    ) -> None:
        """Emit live data and periodically checkpoint its visible content."""

        nonlocal replay_last_write
        emitted_data = data
        now = time.monotonic()
        if (
            generation_id
            and replay_content is not None
            and (force_replay or now - replay_last_write >= 0.25)
        ):
            replay = await asyncio.to_thread(
                ChatGenerations.append_replay_snapshot,
                generation_id,
                str(metadata["user_id"]),
                replay_content,
            )
            replay_last_write = now
            if replay is not None and not replay.degraded:
                emitted_data = {**data, "generation_cursor": replay.last_sequence}
        await event_emitter({"type": "chat:completion", "data": emitted_data})

    Chats.upsert_message_to_chat_by_id_and_message_id(
        metadata["chat_id"],
        metadata["message_id"],
        {"model": model_id},
    )

    async def _post_response_handler(resp: StreamingResponse, evts: list[dict]) -> None:
        nonlocal generation_delivery_complete

        content = ""
        content_blocks: list[dict] = [{"type": "text", "content": ""}]
        tool_calls: list[list[dict]] = []
        # Accumulates the final usage block for the ai_interaction audit (1.5).
        usage_holder: dict = {}

        # Initialise from existing message
        message = Chats.get_message_by_id_and_message_id(
            metadata["chat_id"], metadata["message_id"]
        )
        last_assistant = None
        try:
            if form_data["messages"][-1]["role"] == "assistant":
                last_assistant = get_last_assistant_message(form_data["messages"])
        except Exception:
            pass

        existing_content = (
            message.get("content", "") if message else last_assistant or ""
        )
        content_blocks[0]["content"] = existing_content

        # Emit pre-stream events
        for event in evts:
            await event_emitter({"type": "chat:completion", "data": event})
            Chats.upsert_message_to_chat_by_id_and_message_id(
                metadata["chat_id"],
                metadata["message_id"],
                {**event},
            )

        async def _stream_body_handler(
            stream_resp: StreamingResponse,
        ) -> None:
            nonlocal content, content_blocks, model_id
            response_tool_calls: list[dict] = []

            async for line in stream_resp.body_iterator:
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if not line.strip() or not line.startswith("data:"):
                    continue

                data_str = line[len("data:") :].strip()
                try:
                    data = orjson.loads(data_str)
                    data, _ = await process_filter_functions(
                        request=request,
                        filter_functions=filter_functions,
                        filter_type="stream",
                        form_data=data,
                        extra_params=extra_params,
                    )

                    if not data:
                        continue

                    if "selected_model_id" in data:
                        model_id = data["selected_model_id"]
                        Chats.upsert_message_to_chat_by_id_and_message_id(
                            metadata["chat_id"],
                            metadata["message_id"],
                            {"selectedModelId": model_id},
                        )
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        error = data.get("error", {})
                        if error:
                            await event_emitter(
                                {
                                    "type": "chat:completion",
                                    "data": {"error": error},
                                }
                            )
                        usage = data.get("usage", {})
                        if usage:
                            usage_holder.update(usage)
                            await event_emitter(
                                {
                                    "type": "chat:completion",
                                    "data": {"usage": usage},
                                }
                            )
                            _pt = usage.get("prompt_tokens")
                            if isinstance(_pt, int):
                                record_token_usage("input", _pt, model_id)
                            _ct = usage.get("completion_tokens")
                            if isinstance(_ct, int):
                                record_token_usage("output", _ct, model_id)
                        continue

                    delta = choices[0].get("delta", {})

                    # Tool calls (delta)
                    delta_tool_calls = delta.get("tool_calls")
                    if delta_tool_calls:
                        for dtc in delta_tool_calls:
                            idx = dtc.get("index")
                            if idx is not None:
                                if len(response_tool_calls) <= idx:
                                    response_tool_calls.append(dtc)
                                else:
                                    d_name = dtc.get("function", {}).get("name")
                                    d_args = dtc.get("function", {}).get("arguments")
                                    if d_name:
                                        response_tool_calls[idx]["function"][
                                            "name"
                                        ] += d_name
                                    if d_args:
                                        response_tool_calls[idx]["function"][
                                            "arguments"
                                        ] += d_args

                    # Reasoning content
                    reasoning_content = delta.get("reasoning_content") or delta.get(
                        "reasoning"
                    )
                    if reasoning_content:
                        if (
                            not content_blocks
                            or content_blocks[-1]["type"] != "reasoning"
                        ):
                            content_blocks.append(
                                {
                                    "type": "reasoning",
                                    "start_tag": "think",
                                    "end_tag": "/think",
                                    "attributes": {"type": "reasoning_content"},
                                    "content": "",
                                    "started_at": time.time(),
                                }
                            )
                        content_blocks[-1]["content"] += reasoning_content
                        data = {"content": _serialize_content_blocks(content_blocks)}

                    # Main content
                    value = delta.get("content")
                    if value:
                        # Close open reasoning block
                        if (
                            content_blocks
                            and content_blocks[-1]["type"] == "reasoning"
                            and content_blocks[-1].get("attributes", {}).get("type")
                            == "reasoning_content"
                        ):
                            rb = content_blocks[-1]
                            rb["ended_at"] = time.time()
                            rb["duration"] = int(rb["ended_at"] - rb["started_at"])
                            content_blocks.append({"type": "text", "content": ""})

                        content = "%s%s" % (content, value)
                        if not content_blocks:
                            content_blocks.append({"type": "text", "content": ""})
                        content_blocks[-1]["content"] = (
                            content_blocks[-1]["content"] + value
                        )

                        content, content_blocks, _ = _tag_content_handler(
                            "reasoning",
                            _REASONING_TAGS,
                            content,
                            content_blocks,
                        )
                        content, content_blocks, _ = _tag_content_handler(
                            "solution",
                            _SOLUTION_TAGS,
                            content,
                            content_blocks,
                        )

                        if ENABLE_REALTIME_CHAT_SAVE:
                            Chats.upsert_message_to_chat_by_id_and_message_id(
                                metadata["chat_id"],
                                metadata["message_id"],
                                {
                                    "content": (
                                        _serialize_content_blocks(content_blocks)
                                    ),
                                },
                            )
                        else:
                            data = {
                                "content": (_serialize_content_blocks(content_blocks)),
                            }

                    await _emit_completion(
                        data,
                        replay_content=_serialize_content_blocks(content_blocks),
                    )
                except Exception:
                    if "data: [DONE]" in line:
                        pass
                    else:
                        log.debug("Stream parse error", exc_info=True)
                    continue

            # Clean up trailing empty text block
            if content_blocks and content_blocks[-1]["type"] == "text":
                content_blocks[-1]["content"] = content_blocks[-1]["content"].strip()
                if not content_blocks[-1]["content"]:
                    content_blocks.pop()
                    if not content_blocks:
                        content_blocks.append({"type": "text", "content": ""})

            if response_tool_calls:
                tool_calls.append(response_tool_calls)

            if stream_resp.background:
                await stream_resp.background()

        await _stream_body_handler(response)

        # --- Tool-call loop ---
        max_retries = 5
        retries = 0
        while tool_calls and retries < max_retries:
            retries += 1
            response_tool_calls = tool_calls.pop(0)

            content_blocks.append(
                {
                    "type": "tool_calls",
                    "content": response_tool_calls,
                }
            )
            await _emit_completion(
                {"content": _serialize_content_blocks(content_blocks)},
                replay_content=_serialize_content_blocks(content_blocks),
                force_replay=True,
            )

            tools = metadata.get("tools", {})
            results: list[dict] = []

            for tc in response_tool_calls:
                tc_id = tc.get("id", "")
                tc_name = tc.get("function", {}).get("name", "")
                tc_params: dict = {}
                try:
                    # ast.literal_eval is the safe alternative to eval
                    tc_params = ast.literal_eval(
                        tc.get("function", {}).get("arguments", "{}")
                    )
                except Exception:
                    try:
                        tc_params = orjson.loads(
                            tc.get("function", {}).get("arguments", "{}")
                        )
                    except Exception:
                        log.debug(
                            "Error parsing tool call args: %s",
                            tc.get("function", {}).get("arguments"),
                        )

                tool_result = None
                if tc_name in tools:
                    tool = tools[tc_name]
                    spec = tool.get("spec", {})
                    try:
                        allowed = (
                            spec.get("parameters", {}).get("properties", {}).keys()
                        )
                        tc_params = {k: v for k, v in tc_params.items() if k in allowed}

                        if tool.get("direct", False):
                            tool_result = await event_caller(
                                {
                                    "type": "execute:tool",
                                    "data": {
                                        "id": str(uuid4()),
                                        "name": tc_name,
                                        "params": tc_params,
                                        "server": tool.get("server", {}),
                                        "session_id": metadata.get("session_id"),
                                    },
                                }
                            )
                        else:
                            tool_result = await tool["callable"](**tc_params)
                    except Exception as exc:
                        tool_result = str(exc)

                if isinstance(tool_result, (dict, list)):
                    tool_result = orjson.dumps(
                        tool_result,
                        option=orjson.OPT_INDENT_2,
                    ).decode()

                results.append({"tool_call_id": tc_id, "content": tool_result})

            content_blocks[-1]["results"] = results
            content_blocks.append({"type": "text", "content": ""})
            await _emit_completion(
                {"content": _serialize_content_blocks(content_blocks)},
                replay_content=_serialize_content_blocks(content_blocks),
                force_replay=True,
            )

            # Follow-up completion
            try:
                res = await generate_chat_completion(
                    request,
                    {
                        "model": model_id,
                        "stream": True,
                        "tools": form_data["tools"],
                        "messages": [
                            *form_data["messages"],
                            *_convert_blocks_to_messages(content_blocks),
                        ],
                    },
                    user,
                )
                if isinstance(res, StreamingResponse):
                    await _stream_body_handler(res)
                else:
                    break
            except Exception:
                break

        # --- Finalise ---
        final_content = _serialize_content_blocks(content_blocks)

        # Output security scan
        final_content, output_sanitized = await _scan_output(
            request, final_content, metadata, form_data, user
        )
        title = Chats.get_chat_title_by_id(metadata["chat_id"])

        done_data: dict[str, Any] = {
            "done": True,
            "content": final_content,
            "title": title,
        }
        if output_sanitized:
            done_data["sanitized"] = True

        if not ENABLE_REALTIME_CHAT_SAVE or output_sanitized:
            Chats.upsert_message_to_chat_by_id_and_message_id(
                metadata["chat_id"],
                metadata["message_id"],
                {"content": final_content},
            )

        # Completion must reach the client before optional title/tag generation.
        # The latter may issue additional LLM calls and previously made the UI
        # appear to keep thinking after the answer's final token arrived.
        await _emit_completion(
            done_data,
            replay_content=final_content,
            force_replay=True,
        )
        await terminalize_generation("completed", "provider_completed")
        generation_delivery_complete = True

        try:
            await background_tasks_handler()
            title = Chats.get_chat_title_by_id(metadata["chat_id"])
            await _send_webhook(
                request, user, title, final_content, metadata["chat_id"]
            )

            _log_ai_interaction(
                request,
                user,
                metadata,
                model,
                form_data,
                usage=usage_holder,
                rag_source_count=len(_extract_sources_from_events(evts)),
                tool_call_count=sum(
                    len(b.get("content") or [])
                    for b in content_blocks
                    if isinstance(b, dict) and b.get("type") == "tool_calls"
                ),
                output_sanitized=output_sanitized,
                web_search_used=_web_search_used_in_form(form_data),
                streaming=True,
            )
            _record_provenance(
                request,
                user,
                metadata,
                model,
                form_data,
                final_content,
                evts,
                usage_holder,
            )
            await _persist_token_usage(request, user, metadata, model, usage_holder)
        except Exception as exc:
            log.exception("Post-completion work failed: %s", exc)

    async def _wait_for_durable_stop() -> None:
        """Poll the durable fence so a different replica can stop this worker."""

        while True:
            await asyncio.sleep(0.75)
            try:
                stop_requested = await asyncio.to_thread(
                    ChatGenerations.is_stop_requested,
                    generation_id,
                    generation_user_id,
                )
            except Exception as exc:
                log.warning(
                    "Could not poll generation stop authority %s: %s",
                    generation_id,
                    exc,
                )
                continue
            if stop_requested:
                return

    async def _post_response_with_stop_watch(
        resp: StreamingResponse, evts: list[dict]
    ) -> None:
        if not generation_id:
            await _post_response_handler(resp, evts)
            return

        handler_task = asyncio.create_task(_post_response_handler(resp, evts))
        stop_watch_task = asyncio.create_task(_wait_for_durable_stop())
        try:
            done, _ = await asyncio.wait(
                {handler_task, stop_watch_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_watch_task in done:
                handler_task.cancel()
                await asyncio.gather(handler_task, return_exceptions=True)
                raise asyncio.CancelledError
            await handler_task
        finally:
            for child in (handler_task, stop_watch_task):
                if not child.done():
                    child.cancel()
            await asyncio.gather(handler_task, stop_watch_task, return_exceptions=True)

    # --- Safe wrapper with error handling ---
    async def _safe_handler(resp: StreamingResponse, evts: list[dict]) -> None:
        try:
            await _post_response_with_stop_watch(resp, evts)
            if not generation_delivery_complete:
                await terminalize_generation("completed", "provider_completed")
        except asyncio.CancelledError:
            log.warning("Task was cancelled!")
            await terminalize_generation("stopped", "user_requested")
            await event_emitter({"type": "task-cancelled"})
            if not ENABLE_REALTIME_CHAT_SAVE:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {"content": ""},
                )
        except (asyncio.TimeoutError, TimeoutError):
            log.warning("Stream timed out before completion!")
            await terminalize_generation("timed_out", "provider_timeout")
            await event_emitter(
                {
                    "type": "chat:completion",
                    "data": {
                        "error": {
                            "content": (
                                "Response stream timed out " "before completion."
                            ),
                        },
                    },
                }
            )
            if not ENABLE_REALTIME_CHAT_SAVE:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {"content": ""},
                )
        except Exception as exc:
            log.exception("Error in post_response_handler: %s", exc)
            await terminalize_generation("error", "stream_error")
            await event_emitter(
                {
                    "type": "chat:completion",
                    "data": {"error": {"content": str(exc)}},
                }
            )
            if not ENABLE_REALTIME_CHAT_SAVE:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {"content": ""},
                )
        finally:
            if response.background is not None:
                await response.background()

    task_id, execution_task = create_task(
        _safe_handler(response, events),
        owner_id=metadata["user_id"],
        chat_id=metadata["chat_id"],
        message_id=metadata["message_id"],
        generation_id=generation_id,
    )
    if generation_id:
        try:
            bound_generation = ChatGenerations.bind_task(
                generation_id, generation_user_id, task_id
            )
        except Exception:
            execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)
            await terminalize_generation("error", "task_binding_error")
            if response.background is not None:
                await response.background()
            raise

        if bound_generation is None:
            execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)
            if response.background is not None:
                await response.background()
            raise RuntimeError("Generation task authority disappeared during binding")
        if bound_generation.status != "running" or bound_generation.task_id != task_id:
            execution_task.cancel()
            await asyncio.gather(execution_task, return_exceptions=True)
            await terminalize_generation("stopped", "stopped_before_task_binding")
            if response.background is not None:
                await response.background()
            return {
                "status": False,
                "task_id": None,
                "generation_id": generation_id,
                "chat_id": metadata["chat_id"],
                "message_id": metadata["message_id"],
                "admission": {
                    "status": "stopped",
                    "accepted": False,
                    "terminal": True,
                    "stopped": True,
                    "durable": True,
                },
            }

    return {
        "status": True,
        "task_id": task_id,
        "generation_id": generation_id or task_id,
        "chat_id": metadata["chat_id"],
        "message_id": metadata["message_id"],
        **(
            {
                "admission": {
                    "status": "accepted",
                    "accepted": True,
                    "terminal": False,
                    "stopped": False,
                    "durable": True,
                }
            }
            if generation_id
            else {}
        ),
    }


# ---------------------------------------------------------------------------
# Section: Passthrough streaming (no event emitter/caller)
# ---------------------------------------------------------------------------


def _handle_passthrough_streaming(
    response: StreamingResponse,
    events: list[dict],
    request: Request,
    extra_params: dict,
    filter_functions: list,
) -> StreamingResponse:
    """Handle streaming when no full session is available."""

    async def _stream_wrapper(original_generator: Any, evts: list[dict]) -> Any:
        def _wrap(item: Any) -> str:
            return "data: %s\n\n" % item

        for event in evts:
            event, _ = await process_filter_functions(
                request=request,
                filter_functions=filter_functions,
                filter_type="stream",
                form_data=event,
                extra_params=extra_params,
            )
            if event:
                yield _wrap(orjson.dumps(event).decode())

        last_yield = time.monotonic()
        heartbeat_interval = 15

        async for data in original_generator:
            data, _ = await process_filter_functions(
                request=request,
                filter_functions=filter_functions,
                filter_type="stream",
                form_data=data,
                extra_params=extra_params,
            )
            if data:
                yield data
                last_yield = time.monotonic()
            else:
                now = time.monotonic()
                if now - last_yield >= heartbeat_interval:
                    yield ": heartbeat\n\n"
                    last_yield = now

    return StreamingResponse(
        _stream_wrapper(response.body_iterator, events),
        headers=dict(response.headers),
        background=response.background,
    )
