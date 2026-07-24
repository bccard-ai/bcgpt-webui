"""Function (plugin) CRUD router with module loading and valve management.

Provides endpoints for creating, reading, updating, and deleting user-defined
Python function plugins, along with valve (configuration) management for both
admin-level and per-user settings.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from bcgpt.config import CACHE_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models.functions import (
    FunctionForm,
    FunctionModel,
    FunctionResponse,
    Functions,
)
from bcgpt.utils import get_admin_user, get_verified_user, has_access
from bcgpt.utils import load_function_module_by_id, replace_imports

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_function_or_404(function_id: str) -> FunctionModel:
    """Retrieve a function by id, raising 401 if not found.

    The 401 status code is preserved for backward compatibility with the
    original API contract.
    """
    function = Functions.get_function_by_id(function_id)
    if not function:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return function


def _resolve_function_module(request: Request, function_id: str) -> Any:
    """Return the loaded module for *function_id*, caching it if necessary.

    Checks the in-memory FUNCTIONS registry first.  If not present, loads the
    module from the stored source code, caches it, and returns it.
    """
    functions_registry: dict = request.app.state.FUNCTIONS
    if function_id in functions_registry:
        return functions_registry[function_id]

    module, _ftype, _frontmatter = load_function_module_by_id(function_id)
    functions_registry[function_id] = module
    return module


def _require_user_read_access(function: FunctionModel, user: Any) -> None:
    """Raise 403 if *user* is not authorized to read *function*'s user valves.

    Access is granted when the user is an admin, is the function owner, or has
    explicit read access via access_control.
    """
    if (
        user.role == "admin"
        or function.user_id == user.id
        or has_access(user.id, "read", function.access_control)
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
    )


def _strip_none_values(data: dict) -> dict:
    """Return a copy of *data* with all ``None`` values removed."""
    return {k: v for k, v in data.items() if v is not None}


def _build_update_payload(form_data: FunctionForm, function_type: str) -> dict:
    """Build the update dictionary from form data and detected function type."""
    return {**form_data.model_dump(exclude={"id"}), "type": function_type}


# ---------------------------------------------------------------------------
# List / Export endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[FunctionResponse])
async def get_functions(user=Depends(get_verified_user)):
    """Return all functions visible to the current verified user."""
    return Functions.get_functions()


@router.get("/export", response_model=list[FunctionModel])
async def export_functions(user=Depends(get_admin_user)):
    """Export full function definitions including source code (admin only)."""
    return Functions.get_functions()


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/create", response_model=Optional[FunctionResponse])
async def create_new_function(
    request: Request,
    form_data: FunctionForm,
    user=Depends(get_admin_user),
):
    """Create a new function plugin.

    Validates that the id is a valid Python identifier, processes the source
    code (replacing imports), loads the module, and persists the record.
    """
    if not form_data.id.isidentifier():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only alphanumeric characters and underscores are allowed in the id",
        )

    form_data.id = form_data.id.lower()

    if Functions.get_function_by_id(form_data.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ID_TAKEN,
        )

    try:
        form_data.content = replace_imports(form_data.content)
        module, function_type, frontmatter = load_function_module_by_id(
            form_data.id,
            content=form_data.content,
        )
        form_data.meta.manifest = frontmatter

        request.app.state.FUNCTIONS[form_data.id] = module

        function = Functions.insert_new_function(user.id, function_type, form_data)
        if not function:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error creating function"),
            )

        # Ensure the cache directory exists for this function
        cache_dir = CACHE_DIR / "functions" / form_data.id
        cache_dir.mkdir(parents=True, exist_ok=True)

        return function
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to create a new function: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.get("/id/{id}", response_model=Optional[FunctionModel])
async def get_function_by_id(id: str, user=Depends(get_admin_user)):
    """Return the full definition of a single function by id (admin only)."""
    return _load_function_or_404(id)


@router.post("/id/{id}/toggle", response_model=Optional[FunctionModel])
async def toggle_function_by_id(id: str, user=Depends(get_admin_user)):
    """Toggle the ``is_active`` flag on a function."""
    function = _load_function_or_404(id)
    updated = Functions.update_function_by_id(
        id, {"is_active": not function.is_active}
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
        )
    return updated


@router.post("/id/{id}/toggle/global", response_model=Optional[FunctionModel])
async def toggle_global_by_id(id: str, user=Depends(get_admin_user)):
    """Toggle the ``is_global`` flag on a function."""
    function = _load_function_or_404(id)
    updated = Functions.update_function_by_id(
        id, {"is_global": not function.is_global}
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
        )
    return updated


@router.post("/id/{id}/update", response_model=Optional[FunctionModel])
async def update_function_by_id(
    request: Request,
    id: str,
    form_data: FunctionForm,
    user=Depends(get_admin_user),
):
    """Update a function's source code and metadata.

    Re-processes the source (import replacement, module loading) and persists
    the updated record.
    """
    try:
        form_data.content = replace_imports(form_data.content)
        module, function_type, frontmatter = load_function_module_by_id(
            id, content=form_data.content
        )
        form_data.meta.manifest = frontmatter

        request.app.state.FUNCTIONS[id] = module

        payload = _build_update_payload(form_data, function_type)
        log.debug("Updating function %s with payload: %s", id, payload)

        function = Functions.update_function_by_id(id, payload)
        if not function:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
            )
        return function
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.delete("/id/{id}/delete", response_model=bool)
async def delete_function_by_id(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
):
    """Delete a function and remove it from the in-memory module registry."""
    result = Functions.delete_function_by_id(id)

    if result:
        functions_registry: dict = request.app.state.FUNCTIONS
        functions_registry.pop(id, None)

    return result


# ---------------------------------------------------------------------------
# Admin valve endpoints
# ---------------------------------------------------------------------------


@router.get("/id/{id}/valves", response_model=Optional[dict])
async def get_function_valves_by_id(id: str, user=Depends(get_admin_user)):
    """Return the current valve configuration for a function (admin level)."""
    _load_function_or_404(id)
    try:
        return Functions.get_function_valves_by_id(id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.get("/id/{id}/valves/spec", response_model=Optional[dict])
async def get_function_valves_spec_by_id(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
):
    """Return the JSON schema of a function's ``Valves`` class.

    Loads the function module if necessary and returns ``Valves.schema()``
    when the class is defined, or ``None`` otherwise.
    """
    _load_function_or_404(id)
    module = _resolve_function_module(request, id)

    if hasattr(module, "Valves"):
        return module.Valves.schema()
    return None


@router.post("/id/{id}/valves/update", response_model=Optional[dict])
async def update_function_valves_by_id(
    request: Request,
    id: str,
    form_data: dict,
    user=Depends(get_admin_user),
):
    """Update the admin-level valve configuration for a function.

    Instantiates the module's ``Valves`` class with the submitted data,
    persists the result, and returns the validated values.
    """
    _load_function_or_404(id)
    module = _resolve_function_module(request, id)

    if not hasattr(module, "Valves"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    try:
        valves = module.Valves(**_strip_none_values(form_data))
        Functions.update_function_valves_by_id(id, valves.model_dump())
        return valves.model_dump()
    except Exception as exc:
        log.exception("Error updating function valves for %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


# ---------------------------------------------------------------------------
# User valve endpoints
# ---------------------------------------------------------------------------


@router.get("/id/{id}/valves/user", response_model=Optional[dict])
async def get_function_user_valves_by_id(
    id: str,
    user=Depends(get_verified_user),
):
    """Return the per-user valve values for a function."""
    function = _load_function_or_404(id)
    _require_user_read_access(function, user)

    try:
        return Functions.get_user_valves_by_id_and_user_id(id, user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


@router.get("/id/{id}/valves/user/spec", response_model=Optional[dict])
async def get_function_user_valves_spec_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
):
    """Return the JSON schema of a function's ``UserValves`` class."""
    function = _load_function_or_404(id)
    _require_user_read_access(function, user)

    module = _resolve_function_module(request, id)

    if hasattr(module, "UserValves"):
        return module.UserValves.schema()
    return None


@router.post("/id/{id}/valves/user/update", response_model=Optional[dict])
async def update_function_user_valves_by_id(
    request: Request,
    id: str,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Update the per-user valve configuration for a function.

    Instantiates the module's ``UserValves`` class with the submitted data,
    persists the result, and returns the validated values.
    """
    function = _load_function_or_404(id)
    _require_user_read_access(function, user)

    module = _resolve_function_module(request, id)

    if not hasattr(module, "UserValves"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    try:
        user_valves = module.UserValves(**_strip_none_values(form_data))
        Functions.update_user_valves_by_id_and_user_id(
            id, user.id, user_valves.model_dump()
        )
        return user_valves.model_dump()
    except Exception as exc:
        log.exception("Error updating user valves for function %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )
