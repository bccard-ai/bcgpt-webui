"""Template and model-resolution utilities for background LLM tasks.

This module provides:
  - Model resolution helpers (``get_task_model_id``, ``resolve_task_model``)
  - Prompt variable interpolation (``replace_prompt_variable``, ``replace_messages_variable``)
  - RAG context template assembly with injection protection
  - Generation-template factories for titles, tags, queries, emojis, autocomplete, MoA, etc.

All template functions are pure (no I/O) and safe to call from async contexts.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from datetime import datetime
from typing import Optional

from bcgpt.config import DEFAULT_RAG_TEMPLATE
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.utils import get_last_user_message, get_messages_content

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

_RE_PROMPT_VARS: re.Pattern[str] = re.compile(
    r"(?i){{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}"
)
_RE_MESSAGES_VARS: re.Pattern[str] = re.compile(
    r"{{MESSAGES}}|{{MESSAGES:START:(\d+)}}|{{MESSAGES:END:(\d+)}}|{{MESSAGES:MIDDLETRUNCATE:(\d+)}}"
)
_RE_RAG_INJECTION: list[re.Pattern[str]] = [
    re.compile(r"</?context>", re.IGNORECASE),
    re.compile(r"</?(?:query|question)>", re.IGNORECASE),
    re.compile(r"</?system>", re.IGNORECASE),
    re.compile(r"</?instructions>", re.IGNORECASE),
    re.compile(r"</?source_id>", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMBEDDING_KEYWORDS: frozenset[str] = frozenset({"embedding", "embed"})

_PROMPT_TEMPLATE_VARS: frozenset[str] = frozenset({
    "{{CURRENT_DATE}}",
    "{{CURRENT_TIME}}",
    "{{CURRENT_DATETIME}}",
    "{{CURRENT_WEEKDAY}}",
    "{{USER_NAME}}",
    "{{USER_LOCATION}}",
})


# ---------------------------------------------------------------------------
# Model resolution helpers
# ---------------------------------------------------------------------------


def _is_embedding_model(model_id: str) -> bool:
    """Return ``True`` if *model_id* looks like an embedding-only model."""
    return any(kw in model_id.lower() for kw in _EMBEDDING_KEYWORDS)


def _first_non_arena_model(models: dict) -> str | None:
    """Return the ID of the first non-arena, non-embedding model, or ``None``."""
    for mid, model in models.items():
        if model.get("owned_by") != "arena" and not _is_embedding_model(mid):
            return mid
    return None


def get_task_model_id(
    default_model_id: str,
    task_model: str,
    task_model_external: str,
    models: dict,
) -> str:
    """Select the best task-specific model ID.

    For Ollama-owned default models, prefer *task_model*; otherwise prefer
    *task_model_external*. Falls back to *default_model_id* when neither is
    available.

    Args:
        default_model_id: Base model to fall back to.
        task_model: Preferred local/Ollama task model name.
        task_model_external: Preferred external task model name.
        models: Current model registry (``{id: model_dict}``).

    Returns:
        A validated model ID present in *models*.
    """
    task_model_id = default_model_id
    if models[task_model_id].get("owned_by") == "ollama":
        if task_model and task_model in models:
            task_model_id = task_model
    else:
        if task_model_external and task_model_external in models:
            task_model_id = task_model_external
    return task_model_id


def resolve_task_model(
    request,
    model_id: str | None = None,
    *,
    specific_model: str = "",
) -> str | None:
    """Resolve a model ID suitable for background / task LLM calls.

    Resolution order:
      1. Explicit *model_id* parameter
      2. *specific_model* config value (e.g. ``RAG_HYDE_MODEL``)
      3. ``TASK_MODEL`` / ``TASK_MODEL_EXTERNAL`` via :func:`get_task_model_id`
      4. First non-arena model with a routable provider

    Returns ``None`` when no suitable model is found.
    """
    from bcgpt.providers import get_provider as _get_provider

    config = request.app.state.config
    models = request.app.state.MODELS

    # --- 1. Explicit model_id ---------------------------------------------------
    if model_id:
        if model_id in models:
            if _is_embedding_model(model_id):
                log.warning("resolve_task_model: '%s' is embedding-only, skipping", model_id)
            else:
                return model_id
        else:
            log.warning("resolve_task_model: '%s' not in model registry", model_id)
        return None

    # --- 2. specific_model config -----------------------------------------------
    if specific_model:
        if specific_model in models:
            if _is_embedding_model(specific_model):
                log.warning("resolve_task_model: specific_model '%s' is embedding-only, skipping", specific_model)
            else:
                return specific_model
        else:
            log.warning("resolve_task_model: specific_model '%s' not in model registry", specific_model)

    # --- 3. TASK_MODEL / TASK_MODEL_EXTERNAL ------------------------------------
    default_model_id = _first_non_arena_model(models)
    if not default_model_id:
        log.warning("resolve_task_model: no non-arena models available")
        return None

    task_model = getattr(config, "TASK_MODEL", "")
    task_model_external = getattr(config, "TASK_MODEL_EXTERNAL", "")
    # Handle Pydantic FieldInfo values
    if hasattr(task_model, "value"):
        task_model = task_model.value
    if hasattr(task_model_external, "value"):
        task_model_external = task_model_external.value

    resolved_id = get_task_model_id(default_model_id, task_model, task_model_external, models)

    # --- 4. Validate provider routability ---------------------------------------
    resolved_model = models.get(resolved_id, {})
    if _is_embedding_model(resolved_id):
        log.warning("resolve_task_model: resolved '%s' is embedding-only, scanning for chat model", resolved_id)
    elif _get_provider(resolved_model) is not None:
        return resolved_id

    # Scan for any model with a routable provider
    for mid, m in models.items():
        if m.get("owned_by") == "arena" or _is_embedding_model(mid):
            continue
        if _get_provider(m) is not None:
            log.info("resolve_task_model: '%s' has no provider, using '%s' instead", resolved_id, mid)
            return mid

    log.warning("resolve_task_model: no model with a routable provider found")
    return None


# ---------------------------------------------------------------------------
# Prompt variable interpolation
# ---------------------------------------------------------------------------


def prompt_variables_template(template: str, variables: dict[str, str]) -> str:
    """Replace ``{{KEY}}`` placeholders in *template* with *variables* values."""
    for variable, value in variables.items():
        template = template.replace(variable, value)
    return template


def prompt_template(
    template: str,
    user_name: Optional[str] = None,
    user_location: Optional[str] = None,
) -> str:
    """Expand date/time and user placeholders in *template*.

    Supported placeholders:
      ``{{CURRENT_DATE}}``, ``{{CURRENT_TIME}}``, ``{{CURRENT_DATETIME}}``,
      ``{{CURRENT_WEEKDAY}}``, ``{{USER_NAME}}``, ``{{USER_LOCATION}}``

    Returns *template* unchanged when no placeholders are present.
    """
    if not any(v in template for v in _PROMPT_TEMPLATE_VARS):
        return template

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M:%S %p")
    weekday_str = now.strftime("%A")

    for placeholder, value in {
        "{{CURRENT_DATE}}": date_str,
        "{{CURRENT_TIME}}": time_str,
        "{{CURRENT_DATETIME}}": f"{date_str} {time_str}",
        "{{CURRENT_WEEKDAY}}": weekday_str,
        "{{USER_NAME}}": user_name or "Unknown",
        "{{USER_LOCATION}}": user_location or "Unknown",
    }.items():
        if placeholder in template:
            template = template.replace(placeholder, value)

    return template


def replace_prompt_variable(template: str, prompt: str) -> str:
    """Replace ``{{prompt}}`` (and slice variants) in *template* with *prompt*.

    Slice variants:
      - ``{{prompt:start:N}}`` – first N characters
      - ``{{prompt:end:N}}`` – last N characters
      - ``{{prompt:middletruncate:N}}`` – middle-truncate to N characters
    """

    def _replace(match: re.Match[str]) -> str:
        full = match.group(0).lower()
        start_n = match.group(1)
        end_n = match.group(2)
        mid_n = match.group(3)

        if full == "{{prompt}}":
            return prompt
        if start_n is not None:
            return prompt[: int(start_n)]
        if end_n is not None:
            return prompt[-int(end_n) :]
        if mid_n is not None:
            n = int(mid_n)
            if len(prompt) <= n:
                return prompt
            half_up = math.ceil(n / 2)
            half_down = math.floor(n / 2)
            return f"{prompt[:half_up]}...{prompt[-half_down:]}"
        return ""

    return _RE_PROMPT_VARS.sub(_replace, template)


def replace_messages_variable(
    template: str,
    messages: Optional[list[dict]] = None,
) -> str:
    """Replace ``{{MESSAGES}}`` (and slice variants) in *template*.

    Slice variants work the same as :func:`replace_prompt_variable` but operate
    on the message list. Content is extracted via :func:`get_messages_content`.
    """

    def _replace(match: re.Match[str]) -> str:
        full = match.group(0)
        start_n = match.group(1)
        end_n = match.group(2)
        mid_n = match.group(3)

        if messages is None:
            return ""

        if full == "{{MESSAGES}}":
            return get_messages_content(messages)
        if start_n is not None:
            return get_messages_content(messages[: int(start_n)])
        if end_n is not None:
            return get_messages_content(messages[-int(end_n) :])
        if mid_n is not None:
            n = int(mid_n)
            if len(messages) <= n:
                return get_messages_content(messages)
            half = n // 2
            start_msgs = messages[:half]
            end_msgs = messages[-(half + (n % 2)) :]
            return f"{get_messages_content(start_msgs)}\n{get_messages_content(end_msgs)}"
        return ""

    return _RE_MESSAGES_VARS.sub(_replace, template)


# ---------------------------------------------------------------------------
# RAG template
# ---------------------------------------------------------------------------


def _strip_rag_injection_tags(text: str) -> str:
    """Remove XML-style tags from RAG context that could hijack the prompt.

    Strips ``<context>``, ``<query>``, ``<system>``, ``<instructions>``, and
    ``<source_id>`` tags (both opening and closing) to neutralise injection
    attempts embedded in retrieved documents.
    """
    for pattern in _RE_RAG_INJECTION:
        text = pattern.sub("", text)
    return text


def rag_template(template: str, context: str, query: str) -> str:
    """Assemble a RAG prompt by injecting *context* and *query* into *template*.

    Falls back to :data:`DEFAULT_RAG_TEMPLATE` when *template* is empty.
    Handles ``[context]``, ``{{CONTEXT}}``, ``[query]``, and ``{{QUERY}}``
    placeholders. Strips injection tags from *context* before interpolation.

    Args:
        template: RAG prompt template with ``[context]`` / ``{{CONTEXT}}`` placeholders.
        context: Retrieved document context (already formatted).
        query: The user query string.

    Returns:
        Fully assembled prompt string.
    """
    if not template.strip():
        template = DEFAULT_RAG_TEMPLATE

    if "[context]" not in template and "{{CONTEXT}}" not in template:
        log.debug("RAG template missing '[context]' or '{{CONTEXT}}' placeholder")

    # Security: strip injection tags before interpolation
    context = _strip_rag_injection_tags(context)

    # Handle query placeholders that might already exist in context
    query_placeholders: list[str] = []
    for marker in ("[query]", "{{QUERY}}"):
        if marker in context:
            placeholder = f"{{{{QUERY{uuid.uuid4()}}}}}"
            template = template.replace(marker, placeholder)
            query_placeholders.append(placeholder)

    # Interpolate context
    template = template.replace("[context]", context)
    template = template.replace("{{CONTEXT}}", context)

    # Interpolate query
    template = template.replace("[query]", query)
    template = template.replace("{{QUERY}}", query)
    for ph in query_placeholders:
        template = template.replace(ph, query)

    return template


# ---------------------------------------------------------------------------
# Template application helpers
# ---------------------------------------------------------------------------


def _apply_user_template_vars(
    template: str,
    user: Optional[dict] = None,
) -> str:
    """Apply ``prompt_template`` with user name/location if available."""
    return prompt_template(
        template,
        **({"user_name": user.get("name"), "user_location": user.get("location")} if user else {}),
    )


def _apply_prompt_and_messages(
    template: str,
    messages: list[dict],
) -> str:
    """Replace ``{{prompt}}`` and ``{{MESSAGES}}`` from the last user message."""
    prompt = get_last_user_message(messages)
    template = replace_prompt_variable(template, prompt)
    return replace_messages_variable(template, messages)


# ---------------------------------------------------------------------------
# Generation template functions
# ---------------------------------------------------------------------------


def title_generation_template(
    template: str,
    messages: list[dict],
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for chat-title generation."""
    return _apply_user_template_vars(
        _apply_prompt_and_messages(template, messages),
        user,
    )


def tags_generation_template(
    template: str,
    messages: list[dict],
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for chat-tag generation."""
    return _apply_user_template_vars(
        _apply_prompt_and_messages(template, messages),
        user,
    )


def image_prompt_generation_template(
    template: str,
    messages: list[dict],
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for image-generation from chat messages."""
    return _apply_user_template_vars(
        _apply_prompt_and_messages(template, messages),
        user,
    )


def image_prompt_translation_template(template: str, prompt: str) -> str:
    """Build the prompt for translating an image prompt."""
    return replace_prompt_variable(template, prompt)


def image_prompt_expansion_template(template: str, prompt: str) -> str:
    """Build the prompt for expanding an image prompt with detail."""
    return replace_prompt_variable(template, prompt)


def emoji_generation_template(
    template: str,
    prompt: str,
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for emoji suggestion."""
    return _apply_user_template_vars(
        replace_prompt_variable(template, prompt),
        user,
    )


def autocomplete_generation_template(
    template: str,
    prompt: str,
    messages: Optional[list[dict]] = None,
    type: Optional[str] = None,
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for autocomplete suggestions.

    Supports an additional ``{{TYPE}}`` placeholder for the suggestion type.
    """
    template = template.replace("{{TYPE}}", type or "")
    template = replace_prompt_variable(template, prompt)
    template = replace_messages_variable(template, messages)
    return _apply_user_template_vars(template, user)


def query_generation_template(
    template: str,
    messages: list[dict],
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for search-query generation from chat messages."""
    return _apply_user_template_vars(
        _apply_prompt_and_messages(template, messages),
        user,
    )


def moa_response_generation_template(
    template: str,
    prompt: str,
    responses: list[str],
) -> str:
    """Build the prompt for Mixture-of-Agents response aggregation.

    Replaces ``{{prompt}}`` (with slice variants) and ``{{responses}}``
    (joined triple-quoted blocks).
    """
    template = replace_prompt_variable(template, prompt)
    joined = "\n\n".join(f'"""{r}"""' for r in responses)
    return template.replace("{{responses}}", joined)


def tools_function_calling_generation_template(
    template: str,
    tools_specs: str,
) -> str:
    """Build the prompt for tool/function-calling generation."""
    return template.replace("{{TOOLS}}", tools_specs)


def context_compression_template(
    template: str,
    messages: list[dict],
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for context/window compression."""
    template = replace_messages_variable(template, messages)
    return _apply_user_template_vars(template, user)


def smart_query_template(
    template: str,
    messages: list[dict],
    user: Optional[dict] = None,
) -> str:
    """Build the prompt for smart-query refinement."""
    return _apply_user_template_vars(
        _apply_prompt_and_messages(template, messages),
        user,
    )
