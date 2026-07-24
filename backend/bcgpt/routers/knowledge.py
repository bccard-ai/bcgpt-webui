"""Knowledge base CRUD router with vector DB integration.

Provides endpoints for creating, reading, updating, and deleting knowledge bases,
along with file management (add/remove/reprocess) that coordinates with the
vector database for embedding operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import FileModel, Files
from bcgpt.models import Models, ModelForm
from bcgpt.models.knowledge import (
    KnowledgeForm,
    KnowledgeResponse,
    KnowledgeUserResponse,
    Knowledges,
)
from bcgpt.models.knowledge_file import KnowledgeFiles
from bcgpt.retrieval import VECTOR_DB_CLIENT
from bcgpt.retrieval.lifecycle import (
    cleanup_orphan_file_collection,
    delete_file_vectors,
    delete_knowledge_vectors,
)
from bcgpt.routers.retrieval import (
    BatchProcessFilesForm,
    ProcessFileForm,
    process_file,
    process_files_batch,
)
from bcgpt.utils import get_verified_user, has_access, has_permission
from bcgpt.utils.audit import log_business_event

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class KnowledgeFileIdForm(BaseModel):
    """Payload for single-file add/remove operations."""

    file_id: str


class KnowledgeFilesResponse(KnowledgeResponse):
    """Knowledge response enriched with full file objects."""

    files: list[FileModel]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_write_access(knowledge, user) -> None:
    """Raise 403 if *user* lacks write access to *knowledge*.

    Access is granted when the user is the owner, has explicit write access
    via access_control, or is an admin.
    """
    if (
        knowledge.user_id == user.id
        or has_access(user.id, "write", knowledge.access_control)
        or user.role == "admin"
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
    )


def _require_read_access(knowledge, user) -> None:
    """Raise 401 if *user* lacks read access to *knowledge*."""
    if (
        user.role == "admin"
        or knowledge.user_id == user.id
        or has_access(user.id, "read", knowledge.access_control)
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


def _enrich_with_files(knowledge_base) -> KnowledgeUserResponse:
    """Attach resolved file metadata to a knowledge base, pruning missing files.

    Membership is sourced from the ``knowledge_file`` junction (P2.1) and falls
    back to the legacy ``data['file_ids']`` JSON cache if the junction has no
    rows for this KB (defence for any row that skipped backfill).
    """
    file_ids: list[str] = KnowledgeFiles.file_ids_for_knowledge(knowledge_base.id)
    if not file_ids:
        file_ids = (
            knowledge_base.data.get("file_ids", []) if knowledge_base.data else []
        )

    files = Files.get_file_metadatas_by_ids(file_ids)

    # Prune file_ids that no longer exist in storage
    if len(files) != len(file_ids):
        found_ids = {f.id for f in files}
        missing_ids = [fid for fid in file_ids if fid not in found_ids]
        if missing_ids:
            surviving = [fid for fid in file_ids if fid in found_ids]
            data = {**(knowledge_base.data or {}), "file_ids": surviving}
            Knowledges.update_knowledge_data_by_id(id=knowledge_base.id, data=data)
            files = Files.get_file_metadatas_by_ids(surviving)

    return KnowledgeUserResponse(
        **knowledge_base.model_dump(),
        files=files,
    )


async def _get_file_or_404(file_id: str, user) -> FileModel:
    """Fetch a file and verify the user owns it (or is admin)."""
    file = await asyncio.to_thread(Files.get_file_by_id, file_id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    if file.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return file


async def _load_knowledge_or_404(id: str):
    """Retrieve knowledge by id, raising 400 if not found."""
    knowledge = await asyncio.to_thread(Knowledges.get_knowledge_by_id, id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return knowledge


def _build_files_response(knowledge, file_ids: list[str]) -> KnowledgeFilesResponse:
    """Construct a KnowledgeFilesResponse with resolved file objects."""
    files = Files.get_files_by_ids(file_ids)
    return KnowledgeFilesResponse(**knowledge.model_dump(), files=files)


async def _build_files_response_async(
    knowledge, file_ids: list[str]
) -> KnowledgeFilesResponse:
    """Async variant of `_build_files_response`."""
    files = await asyncio.to_thread(Files.get_files_by_ids, file_ids)
    return KnowledgeFilesResponse(**knowledge.model_dump(), files=files)


# ---------------------------------------------------------------------------
# List endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[KnowledgeUserResponse])
async def get_knowledge(user=Depends(get_verified_user)):
    """Return all knowledge bases readable by the current user.

    Admins see everything; other users see only knowledge bases they have
    read access to (via ownership or access_control groups).
    """
    if user.role == "admin":
        bases = Knowledges.get_knowledge_bases()
    else:
        bases = Knowledges.get_knowledge_bases_by_user_id(user.id, "read")

    return [_enrich_with_files(kb) for kb in bases]


@router.get("/list", response_model=list[KnowledgeUserResponse])
async def get_knowledge_list(user=Depends(get_verified_user)):
    """Return knowledge bases the user can *write* to.

    Used by UI components that need to present a selection of knowledge bases
    the user is allowed to modify.
    """
    if user.role == "admin":
        bases = Knowledges.get_knowledge_bases()
    else:
        bases = Knowledges.get_knowledge_bases_by_user_id(user.id, "write")

    return [_enrich_with_files(kb) for kb in bases]


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/create", response_model=Optional[KnowledgeResponse])
async def create_new_knowledge(
    request: Request,
    form_data: KnowledgeForm,
    user=Depends(get_verified_user),
):
    """Create a new knowledge base.

    Non-admin users must have the ``workspace.knowledge`` permission.
    """
    if user.role != "admin" and not has_permission(
        user.id, "workspace.knowledge", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    knowledge = Knowledges.insert_new_knowledge(user.id, form_data)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_EXISTS,
        )
    return knowledge


@router.get("/{id}", response_model=Optional[KnowledgeFilesResponse])
async def get_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    """Retrieve a single knowledge base with its full file objects."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    _require_read_access(knowledge, user)

    file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
    files = Files.get_files_by_ids(file_ids)
    return KnowledgeFilesResponse(**knowledge.model_dump(), files=files)


@router.post("/{id}/update", response_model=Optional[KnowledgeFilesResponse])
async def update_knowledge_by_id(
    id: str,
    form_data: KnowledgeForm,
    user=Depends(get_verified_user),
):
    """Update metadata (name, description, access_control) of a knowledge base."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    _require_write_access(knowledge, user)

    knowledge = Knowledges.update_knowledge_by_id(id=id, form_data=form_data)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ID_TAKEN,
        )

    file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
    return _build_files_response(knowledge, file_ids)


@router.delete("/{id}/delete", response_model=bool)
async def delete_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    """Delete a knowledge base, its vector collection, and model references."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    _require_write_access(knowledge, user)

    log.info("Deleting knowledge base: %s (name: %s)", id, knowledge.name)

    # Remove references from models that point to this knowledge base
    _cleanup_model_references(id)

    # Drop the vector collection
    try:
        VECTOR_DB_CLIENT.delete_collection(collection_name=id)
    except Exception as exc:
        log.debug("Vector collection deletion failed: %s", exc)

    # P1.6: when RAG_USE_CORPUS is on the KB's vectors live in the shared corpus
    # keyed by knowledge_id — drop them with a filter-delete (no-op when off).
    await delete_knowledge_vectors(id)

    # Detach member File rows from the now-deleted KB so they don't carry a
    # dangling collection_name. The rows and storage blobs are preserved.
    file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
    for fid in file_ids:
        try:
            await asyncio.to_thread(
                Files.update_file_metadata_by_id, fid, {"collection_name": None}
            )
        except Exception as exc:
            log.debug("Failed to clear collection_name on file %s: %s", fid, exc)

    # P2.1: clear junction membership (also handled by FK CASCADE, but explicit
    # so it works even where the cascade is not enforced).
    await asyncio.to_thread(KnowledgeFiles.remove_knowledge, id)

    log_business_event(
        action="kb.deleted",
        resource_type="knowledge",
        user=user,
        resource_id=id,
        resource_name=knowledge.name,
    )

    return Knowledges.delete_knowledge_by_id(id=id)


@router.post("/{id}/reset", response_model=Optional[KnowledgeResponse])
async def reset_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    """Reset a knowledge base: drop its vector collection and clear file list."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    _require_write_access(knowledge, user)

    try:
        VECTOR_DB_CLIENT.delete_collection(collection_name=id)
    except Exception as exc:
        log.debug("Collection deletion during reset: %s", exc)

    # P1.6: filter-delete the KB's vectors from the corpus under RAG_USE_CORPUS.
    await delete_knowledge_vectors(id)

    return Knowledges.update_knowledge_data_by_id(id=id, data={"file_ids": []})


# ---------------------------------------------------------------------------
# File add/remove endpoints
# ---------------------------------------------------------------------------


@router.post("/{id}/file/add", response_model=Optional[KnowledgeFilesResponse])
async def add_file_to_knowledge_by_id(
    request: Request,
    id: str,
    form_data: KnowledgeFileIdForm,
    user=Depends(get_verified_user),
):
    """Embed a single file into the knowledge base's vector collection."""
    knowledge = await _load_knowledge_or_404(id)
    _require_write_access(knowledge, user)
    await _get_file_or_404(form_data.file_id, user)

    # Remove any prior embedding for this file in the knowledge collection
    if await asyncio.to_thread(
        VECTOR_DB_CLIENT.has_collection, collection_name=knowledge.id
    ):
        await delete_file_vectors(knowledge.id, form_data.file_id)

    # Embed the file into the knowledge collection
    try:
        await asyncio.to_thread(
            process_file,
            request,
            ProcessFileForm(file_id=form_data.file_id, collection_name=id),
            user=user,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Clean up any orphaned per-file collection
    await cleanup_orphan_file_collection(form_data.file_id)

    # Persist the file_id in the knowledge base data
    data = knowledge.data or {}
    file_ids: list[str] = data.get("file_ids", [])

    if form_data.file_id not in file_ids:
        file_ids.append(form_data.file_id)
        data["file_ids"] = file_ids
        knowledge = await asyncio.to_thread(
            Knowledges.update_knowledge_data_by_id, id=id, data=data
        )
        # P2.1 dual-write: also record membership in the junction table.
        await asyncio.to_thread(KnowledgeFiles.add, id, form_data.file_id, user.id)
        if not knowledge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("knowledge"),
            )

    log_business_event(
        action="file.added_to_kb",
        resource_type="knowledge",
        user=user,
        resource_id=id,
        details={"file_id": form_data.file_id},
    )

    return await _build_files_response_async(knowledge, file_ids)


@router.post("/{id}/file/remove", response_model=Optional[KnowledgeFilesResponse])
async def remove_file_from_knowledge_by_id(
    id: str,
    form_data: KnowledgeFileIdForm,
    user=Depends(get_verified_user),
):
    """Remove a file from a knowledge base and delete its vectors."""
    knowledge = await _load_knowledge_or_404(id)
    _require_write_access(knowledge, user)

    file = await asyncio.to_thread(Files.get_file_by_id, form_data.file_id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    # Remove vectors from the knowledge collection
    await delete_file_vectors(knowledge.id, form_data.file_id)

    # Also remove the file's standalone collection
    await cleanup_orphan_file_collection(form_data.file_id)

    # Delete the file record if the user owns it or is admin
    if file.user_id == user.id or user.role == "admin":
        await asyncio.to_thread(Files.delete_file_by_id, form_data.file_id)

    # Remove file_id from the knowledge base data
    data = knowledge.data or {}
    file_ids: list[str] = data.get("file_ids", [])

    if form_data.file_id not in file_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("file_id"),
        )

    file_ids.remove(form_data.file_id)
    data["file_ids"] = file_ids
    knowledge = await asyncio.to_thread(
        Knowledges.update_knowledge_data_by_id, id=id, data=data
    )
    # P2.1 dual-write: remove the membership row from the junction table.
    await asyncio.to_thread(KnowledgeFiles.remove, id, form_data.file_id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("knowledge"),
        )

    return await _build_files_response_async(knowledge, file_ids)


# ---------------------------------------------------------------------------
# Batch & reprocess endpoints
# ---------------------------------------------------------------------------


@router.post("/{id}/files/batch/add", response_model=Optional[KnowledgeFilesResponse])
async def add_files_to_knowledge_batch(
    request: Request,
    id: str,
    form_data: list[KnowledgeFileIdForm],
    user=Depends(get_verified_user),
):
    """Add multiple files to a knowledge base in one request.

    Successfully processed files are persisted; per-file errors are returned
    as warnings in the response.
    """
    knowledge = await _load_knowledge_or_404(id)
    _require_write_access(knowledge, user)

    # Validate all files upfront
    files: List[FileModel] = []
    for form in form_data:
        await _get_file_or_404(form.file_id, user)
        file = await asyncio.to_thread(Files.get_file_by_id, form.file_id)
        files.append(file)

    log.info("files/batch/add - %d files", len(files))

    # Batch embed
    try:
        result = await asyncio.to_thread(
            process_files_batch,
            request=request,
            form_data=BatchProcessFilesForm(files=files, collection_name=id),
            user=user,
        )
    except Exception as exc:
        log.error("add_files_to_knowledge_batch failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Persist successful file ids
    data = knowledge.data or {}
    existing_ids: list[str] = data.get("file_ids", [])

    for r in result.results:
        if r.status == "completed" and r.file_id not in existing_ids:
            existing_ids.append(r.file_id)

    data["file_ids"] = existing_ids
    knowledge = await asyncio.to_thread(
        Knowledges.update_knowledge_data_by_id, id=id, data=data
    )

    response = await _build_files_response_async(knowledge, existing_ids)

    if result.errors:
        error_details = [f"{err.file_id}: {err.error}" for err in result.errors]
        response.warnings = {
            "message": "Some files failed to process",
            "errors": error_details,
        }

    return response


@router.post("/{id}/reprocess", response_model=Optional[KnowledgeFilesResponse])
async def reprocess_knowledge_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
):
    """Re-embed all files using the current embedding model and chunking config.

    Drops the entire vector collection first, then re-chunks and re-embeds
    every tracked file. Files that no longer exist in storage are pruned.
    """
    knowledge = await _load_knowledge_or_404(id)
    _require_write_access(knowledge, user)

    data = knowledge.data or {}
    file_ids: list[str] = data.get("file_ids", [])

    # Nothing to reprocess
    if not file_ids:
        return KnowledgeFilesResponse(**knowledge.model_dump(), files=[])

    # Resolve file objects, dropping missing ones
    files: List[FileModel] = []
    resolved_ids: list[str] = []
    unresolved_ids: list[str] = []

    for fid in file_ids:
        file = await asyncio.to_thread(Files.get_file_by_id, fid)
        if file:
            files.append(file)
            resolved_ids.append(fid)
        else:
            unresolved_ids.append(fid)

    # Drop the entire collection to clear stale vectors
    try:
        await asyncio.to_thread(VECTOR_DB_CLIENT.delete_collection, collection_name=id)
    except Exception as exc:
        log.debug("Reprocess collection delete: %s", exc)

    # Re-embed resolved files
    errors = []
    if files:
        try:
            result = await asyncio.to_thread(
                process_files_batch,
                request=request,
                form_data=BatchProcessFilesForm(files=files, collection_name=id),
                user=user,
            )
            errors = result.errors
        except Exception as exc:
            log.error("reprocess_knowledge_by_id failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    # Update data if any file_ids were pruned
    if unresolved_ids:
        data["file_ids"] = resolved_ids
        knowledge = await asyncio.to_thread(
            Knowledges.update_knowledge_data_by_id, id=id, data=data
        )

    # Build warnings
    warning_errors: list[str] = []
    warning_errors.extend(f"{err.file_id}: {err.error}" for err in errors)
    warning_errors.extend(
        f"{fid}: file not found, removed from knowledge base" for fid in unresolved_ids
    )

    response = KnowledgeFilesResponse(**knowledge.model_dump(), files=files)
    if warning_errors:
        response.warnings = {
            "message": "Some files failed to reprocess",
            "errors": warning_errors,
        }

    return response


# ---------------------------------------------------------------------------
# Model reference cleanup (sync helper)
# ---------------------------------------------------------------------------


def _cleanup_model_references(knowledge_id: str) -> None:
    """Remove references to *knowledge_id* from all models that reference it."""
    models = Models.get_all_models()
    log.info(
        "Checking %d models for references to knowledge base %s",
        len(models),
        knowledge_id,
    )

    for model in models:
        if not model.meta or not hasattr(model.meta, "knowledge"):
            continue
        knowledge_list = model.meta.knowledge or []
        updated = [k for k in knowledge_list if k.get("id") != knowledge_id]

        if len(updated) != len(knowledge_list):
            log.info(
                "Updating model %s to remove knowledge base %s", model.id, knowledge_id
            )
            model.meta.knowledge = updated
            Models.update_model_by_id(
                model.id,
                ModelForm(
                    id=model.id,
                    name=model.name,
                    base_model_id=model.base_model_id,
                    meta=model.meta,
                    params=model.params,
                    access_control=model.access_control,
                    is_active=model.is_active,
                ),
            )
