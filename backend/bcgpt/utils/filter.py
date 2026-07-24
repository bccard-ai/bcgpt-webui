"""Filter-function pipeline for request/response processing.

Handles loading, sorting, and executing filter functions (inlet, outlet,
stream) that transform chat payloads as they flow through the system.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Functions
from bcgpt.utils import load_function_module_by_id

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# Filter ordering
# ---------------------------------------------------------------------------


def get_sorted_filter_ids(model: dict) -> List[str]:
    """Return filter IDs applicable to *model*, sorted by priority.

    Global filters are merged with any model-specific ``filterIds`` listed
    in ``model["info"]["meta"]``.  Only enabled (active) filters are
    retained, and the result is sorted in ascending priority order.

    Args:
        model: Model descriptor dict whose ``info.meta.filterIds`` may
            declare additional filters.

    Returns:
        Ordered list of filter function IDs.
    """

    def get_priority(function_id: str) -> int:
        function = Functions.get_function_by_id(function_id)
        if function is not None and hasattr(function, "valves"):
            return (function.valves if function.valves else {}).get("priority", 0)
        return 0

    filter_ids = [f.id for f in Functions.get_global_filter_functions()]

    if "info" in model and "meta" in model["info"]:
        filter_ids.extend(model["info"]["meta"].get("filterIds", []))
        filter_ids = list(set(filter_ids))

    enabled_ids = {
        f.id for f in Functions.get_functions_by_type("filter", active_only=True)
    }
    filter_ids = [fid for fid in filter_ids if fid in enabled_ids]
    filter_ids.sort(key=get_priority)
    return filter_ids


# ---------------------------------------------------------------------------
# Filter execution
# ---------------------------------------------------------------------------


async def process_filter_functions(
    request: Any,
    filter_functions: List[Any],
    filter_type: str,
    form_data: Dict[str, Any],
    extra_params: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute a chain of filter functions sequentially.

    For each filter the handler matching *filter_type* (``"inlet"``,
    ``"outlet"``, or ``"stream"``) is looked up and invoked with the
    appropriate parameters.  Valve configuration and per-user valve
    overrides are applied before execution.

    When *filter_type* is ``"inlet"`` and a filter module exposes a
    ``file_handler`` attribute, file metadata is stripped from the
    payload after all filters have run.

    Args:
        request: The current FastAPI ``Request`` (used for app state).
        filter_functions: Iterable of function model objects.
        filter_type: One of ``"inlet"``, ``"outlet"``, ``"stream"``.
        form_data: The chat payload being filtered.
        extra_params: Additional keyword parameters forwarded to handlers.

    Returns:
        ``(transformed_form_data, {})`` — the second element is reserved
        for future metadata.

    Raises:
        Exception: Re-raises any error raised by a filter handler.
    """
    skip_files: Optional[bool] = None

    for function in filter_functions:
        filter_id = function.id
        if not function:
            continue

        # Load or retrieve cached module
        if filter_id in request.app.state.FUNCTIONS:
            function_module = request.app.state.FUNCTIONS[filter_id]
        else:
            function_module, _, _ = load_function_module_by_id(filter_id)
            request.app.state.FUNCTIONS[filter_id] = function_module

        handler = getattr(function_module, filter_type, None)
        if not handler:
            continue

        # Track file-handler flag for inlet filters
        if filter_type == "inlet" and hasattr(function_module, "file_handler"):
            skip_files = function_module.file_handler

        # Apply global valves
        if hasattr(function_module, "valves") and hasattr(function_module, "Valves"):
            valves = Functions.get_function_valves_by_id(filter_id)
            function_module.valves = function_module.Valves(
                **(valves if valves else {})
            )

        try:
            sig = inspect.signature(handler)

            # Build parameter dict based on handler type
            params: Dict[str, Any] = {"body": form_data}
            if filter_type == "stream":
                params = {"event": form_data}

            params = params | {
                k: v
                for k, v in {
                    **extra_params,
                    "__id__": filter_id,
                }.items()
                if k in sig.parameters
            }

            # Inject per-user valves
            if "__user__" in sig.parameters and hasattr(function_module, "UserValves"):
                try:
                    params["__user__"]["valves"] = function_module.UserValves(
                        **Functions.get_user_valves_by_id_and_user_id(
                            filter_id, params["__user__"]["id"]
                        )
                    )
                except Exception as exc:
                    log.exception("Failed to resolve user valves: %s", exc)

            # Execute synchronously or asynchronously
            if inspect.iscoroutinefunction(handler):
                form_data = await handler(**params)
            else:
                form_data = handler(**params)

        except Exception as exc:
            log.debug("Error in %s handler %s: %s", filter_type, filter_id, exc)
            raise exc

    # Strip file metadata when file_handler is active
    if skip_files and "files" in form_data.get("metadata", {}):
        del form_data["files"]
        del form_data["metadata"]["files"]

    return form_data, {}
