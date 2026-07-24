"""Tool function loading and introspection utilities for BCGPT WebUI.

Provides helpers for loading user-defined tool modules, inspecting
their callable signatures, converting them to Pydantic models and
OpenAI function specs, and injecting runtime parameters (user context,
valves, etc.) into tool callables.

Public exports (re-exported via ``bcgpt.utils.__init__``):
    apply_extra_params_to_tool_function,
    get_tools, parse_description, parse_docstring,
    function_to_pydantic_model,
    get_callable_attributes, get_tools_specs
"""

from __future__ import annotations

import inspect
import logging
import re
from functools import partial, update_wrapper
from typing import Any, Awaitable, Callable, get_type_hints

from fastapi import Request
from langchain_core.utils.function_calling import convert_to_openai_function
from pydantic import BaseModel, Field, create_model

from bcgpt.models import Tools, UserModel
from bcgpt.utils import load_tools_module_by_id

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callable parameter injection
# ---------------------------------------------------------------------------


def apply_extra_params_to_tool_function(
    function: Callable, extra_params: dict
) -> Callable[..., Awaitable]:
    """Inject extra runtime parameters into a tool function.

    Only parameters that the function actually declares are injected.
    Sync functions are wrapped into async coroutines so that the caller
    can always ``await`` the result.

    Args:
        function: The original tool function (sync or async).
        extra_params: Keyword arguments to inject.

    Returns:
        An async callable with the extra parameters pre-bound.
    """
    sig = inspect.signature(function)
    filtered = {k: v for k, v in extra_params.items() if k in sig.parameters}
    bound = partial(function, **filtered)

    if inspect.iscoroutinefunction(function):
        update_wrapper(bound, function)
        return bound

    async def async_wrapper(*args, **kwargs):
        return bound(*args, **kwargs)

    update_wrapper(async_wrapper, function)
    return async_wrapper


# ---------------------------------------------------------------------------
# Tool collection
# ---------------------------------------------------------------------------


def get_tools(
    request: Request,
    tool_ids: list[str],
    user: UserModel,
    extra_params: dict,
) -> dict[str, dict]:
    """Load and prepare tool functions for the given *tool_ids*.

    For each tool the function:

    1. Loads the tool module (cached in ``app.state.TOOLS``).
    2. Injects user valves and global valves.
    3. Normalises the tool's OpenAI function specs.
    4. Binds extra parameters (user context, ``__id__``) to callables.
    5. Generates a Pydantic model for parameter validation.

    .. note::
        *extra_params* is **mutated** in-place (``__id__`` and
        ``__user__.valves`` keys are added).

    Args:
        request: The incoming FastAPI request.
        tool_ids: List of tool database IDs to load.
        user: The current user model.
        extra_params: Mutable dict of runtime parameters to inject.

    Returns:
        A dict mapping function names to tool descriptor dicts with keys
        ``spec``, ``callable``, ``toolkit_id``, ``pydantic_model``,
        ``file_handler``, and ``citation``.
    """
    tools_dict: dict[str, dict] = {}

    for tool_id in tool_ids:
        tool_record = Tools.get_tool_by_id(tool_id)
        if tool_record is None:
            continue

        # Load module (from cache or disk)
        module = request.app.state.TOOLS.get(tool_id)
        if module is None:
            module, _ = load_tools_module_by_id(tool_id)
            request.app.state.TOOLS[tool_id] = module

        # Inject valves
        extra_params["__id__"] = tool_id
        if hasattr(module, "valves") and hasattr(module, "Valves"):
            valves = Tools.get_tool_valves_by_id(tool_id) or {}
            module.valves = module.Valves(**valves)

        if hasattr(module, "UserValves"):
            extra_params["__user__"]["valves"] = module.UserValves(  # type: ignore[assignment]
                **Tools.get_user_valves_by_id_and_user_id(tool_id, user.id)
            )

        tools_dict = _process_tool_specs(
            tool_record, module, tool_id, extra_params, tools_dict
        )

    return tools_dict


def _process_tool_specs(
    tool_record, module, tool_id: str, extra_params: dict, tools_dict: dict
) -> dict[str, dict]:
    """Process all function specs from a single tool record."""
    for spec in tool_record.specs:
        _normalise_spec_types(spec)
        _strip_internal_params(spec)

        function_name = spec["name"]
        original_func = getattr(module, function_name)
        callable_fn = apply_extra_params_to_tool_function(
            original_func, extra_params
        )

        spec["description"] = _extract_callable_description(
            callable_fn, function_name
        )

        # Detect name collisions
        if function_name in tools_dict:
            log.warning(
                "Tool %s already exists — collision between %s and %s, discarding %s.%s",
                function_name,
                tools_dict[function_name].get("toolkit_id"),
                tool_id,
                tool_id,
                function_name,
            )
            continue

        tools_dict[function_name] = {
            "spec": spec,
            "callable": callable_fn,
            "toolkit_id": tool_id,
            "pydantic_model": function_to_pydantic_model(callable_fn),
            "file_handler": hasattr(module, "file_handler") and module.file_handler,
            "citation": hasattr(module, "citation") and module.citation,
        }

    return tools_dict


# ---------------------------------------------------------------------------
# Spec normalisation helpers
# ---------------------------------------------------------------------------


def _normalise_spec_types(spec: dict) -> None:
    """Fix type shorthand in OpenAI function parameter specs."""
    for prop in spec.get("parameters", {}).get("properties", {}).values():
        if prop.get("type") == "str":
            prop["type"] = "string"


def _strip_internal_params(spec: dict) -> None:
    """Remove dunder-prefixed parameters from a function spec."""
    props = spec.get("parameters", {}).get("properties", {})
    spec["parameters"]["properties"] = {
        k: v for k, v in props.items() if not k.startswith("__")
    }


def _extract_callable_description(callable_fn: Callable, fallback: str) -> str:
    """Extract the description portion of a callable's docstring."""
    doc = callable_fn.__doc__
    if doc and doc.strip():
        parts = re.split(r":(param|return)", doc, 1)
        return parts[0]
    return fallback


# ---------------------------------------------------------------------------
# Docstring parsing
# ---------------------------------------------------------------------------


def parse_description(docstring: str | None) -> str:
    """Extract the free-text description from a docstring.

    Everything before the first ``:param`` or ``:return`` directive is
    returned as the description.

    Args:
        docstring: The raw docstring (may be ``None``).

    Returns:
        The description text, or an empty string.
    """
    if not docstring:
        return ""

    lines = [line.strip() for line in docstring.strip().split("\n")]
    description_lines: list[str] = []

    for line in lines:
        if re.match(r":param", line) or re.match(r":return", line):
            break
        description_lines.append(line)

    return "\n".join(description_lines)


def parse_docstring(docstring: str | None) -> dict[str, str]:
    """Parse reST-style ``:param name: description`` entries from a docstring.

    Internal parameters (prefixed with ``__``) are excluded.

    Args:
        docstring: The raw docstring (may be ``None``).

    Returns:
        A dict mapping parameter names to their descriptions.
    """
    if not docstring:
        return {}

    pattern = re.compile(r":param (\w+):\s*(.+)")
    descriptions: dict[str, str] = {}

    for line in docstring.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        name, desc = match.groups()
        if name.startswith("__"):
            continue
        descriptions[name] = desc

    return descriptions


# ---------------------------------------------------------------------------
# Pydantic model generation
# ---------------------------------------------------------------------------


def function_to_pydantic_model(func: Callable) -> type[BaseModel]:
    """Convert a function's type hints and docstring into a Pydantic model.

    Parameter descriptions are extracted from reST-style ``:param``
    directives in the docstring and attached as :class:`~pydantic.Field`
    metadata.

    Args:
        func: The function to introspect.

    Returns:
        A dynamically-created Pydantic model class.
    """
    type_hints = get_type_hints(func)
    signature = inspect.signature(func)
    parameters = signature.parameters

    docstring = func.__doc__
    descriptions = parse_docstring(docstring)
    tool_description = parse_description(docstring)

    field_defs: dict = {}
    for name, param in parameters.items():
        type_hint = type_hints.get(name, Any)
        default = param.default if param.default is not param.empty else ...
        description = descriptions.get(name)
        if description:
            field_defs[name] = (type_hint, Field(default, description=description))
        else:
            field_defs[name] = (type_hint, default)

    model = create_model(func.__name__, **field_defs)
    model.__doc__ = tool_description
    return model


# ---------------------------------------------------------------------------
# Tool class introspection
# ---------------------------------------------------------------------------


def get_callable_attributes(tool: object) -> list[Callable]:
    """Return all public, non-class callable attributes of *tool*.

    Dunder methods and classes are excluded.

    Args:
        tool: An object (typically a tool module or class instance).

    Returns:
        A list of callable objects.
    """
    return [
        getattr(tool, name)
        for name in dir(tool)
        if callable(getattr(tool, name))
        and not name.startswith("__")
        and not inspect.isclass(getattr(tool, name))
    ]


def get_tools_specs(tool_class: object) -> list[dict]:
    """Generate OpenAI function specs for every callable in *tool_class*.

    Args:
        tool_class: An object whose public callables will be converted.

    Returns:
        A list of OpenAI function spec dictionaries.
    """
    callables = get_callable_attributes(tool_class)
    models = map(function_to_pydantic_model, callables)
    return [convert_to_openai_function(m) for m in models]
