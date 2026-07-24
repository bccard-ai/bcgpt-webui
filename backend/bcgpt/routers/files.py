"""File management router — upload, download, CRUD, and content access.

Provides endpoints for file lifecycle management including upload with validation,
content retrieval with proper MIME handling, and access control through knowledge
base membership checks.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models.files import FileForm, FileModel, FileModelResponse, Files
from bcgpt.models import Knowledges
from bcgpt.models.knowledge_file import KnowledgeFiles
from bcgpt.retrieval.lifecycle import purge_file_vectors
from bcgpt.routers import (
    ProcessFileForm,
    get_knowledge,
    get_knowledge_list,
    process_file,
    transcribe,
)
from bcgpt.storage import Storage
from bcgpt.utils import get_admin_user, get_verified_user
from bcgpt.utils.audit import log_business_event
from bcgpt.utils.security.file_signature import validate_file_signature

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DANGEROUS_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".html",
        ".htm",
        ".xhtml",
        ".shtml",
        ".svg",
        ".xml",
        ".xsl",
        ".xslt",
        ".js",
        ".mjs",
        ".vbs",
        ".hta",
    }
)

AUDIO_CONTENT_TYPES: frozenset[str] = frozenset(
    {"audio/mpeg", "audio/wav", "audio/ogg", "audio/x-m4a"}
)

IMAGE_CONTENT_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/gif"}
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ContentForm(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# File validation helpers
# ---------------------------------------------------------------------------


def validate_file_extension(filename: str) -> str:
    """Return sanitised basename; raise on dangerous extension."""
    basename = Path(filename).name  # equivalent to os.path.basename
    ext = Path(basename).suffix.lower()
    if ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{ext}' is not allowed for security reasons.",
        )
    return basename


def validate_file_size(contents: bytes, max_size_mb: int | None) -> None:
    """Raise HTTP 413 when the payload exceeds *max_size_mb* (None = unlimited)."""
    if max_size_mb is None:
        return
    max_bytes = int(max_size_mb) * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size ({len(contents)} bytes) exceeds the maximum "
                f"allowed size ({max_size_mb} MB)."
            ),
        )


# ---------------------------------------------------------------------------
# Access-control helpers
# ---------------------------------------------------------------------------


async def _fetch_file(file_id: str) -> FileModel:
    """Return the file model or raise 404."""
    file = await asyncio.to_thread(Files.get_file_by_id, file_id)
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return file


def _can_access(file: FileModel, user, *, require_write: bool = False) -> bool:
    """Quick ownership / admin check (synchronous)."""
    if file.user_id == user.id:
        return True
    if user.role == "admin":
        return True
    return False  # knowledge-base check is async, handled separately


async def _can_access_via_knowledge(file: FileModel, user, access_type: str) -> bool:
    """Check whether *user* can access *file* through a shared knowledge base.

    P2.2: a file may belong to several KBs (now tracked in the ``knowledge_file``
    junction); access is granted if the user can access ANY of them — so file
    access effectively inherits the union of its KBs' ACLs. Falls back to the
    legacy single ``meta.collection_name`` pointer when the junction has no rows
    for the file (transition / pre-backfill). ``File.access_control`` remains
    vestigial — KB membership is the access surface.
    """
    kb_ids = await asyncio.to_thread(KnowledgeFiles.knowledges_for_file, file.id)
    if not kb_ids:
        collection_name = file.meta.get("collection_name") if file.meta else None
        kb_ids = [collection_name] if collection_name else []
    if not kb_ids:
        return False
    knowledge_bases = await asyncio.to_thread(
        Knowledges.get_knowledge_bases_by_user_id, user.id, access_type
    )
    accessible_ids = {kb.id for kb in knowledge_bases}
    return any(kb_id in accessible_ids for kb_id in kb_ids)


async def _authorize_read(file_id: str, user) -> FileModel:
    """Fetch file and verify read access; raise 404 on failure."""
    file = await _fetch_file(file_id)
    if (
        file.user_id == user.id
        or user.role == "admin"
        or await _can_access_via_knowledge(file, user, "read")
    ):
        return file
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


async def _authorize_write(file_id: str, user) -> FileModel:
    """Fetch file and verify write access; raise 404 on failure."""
    file = await _fetch_file(file_id)
    if (
        file.user_id == user.id
        or user.role == "admin"
        or await _can_access_via_knowledge(file, user, "write")
    ):
        return file
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ERROR_MESSAGES.NOT_FOUND,
    )


# ---------------------------------------------------------------------------
# Public dependency — kept for backward compat with other routers that import
# has_access_to_file from this module.
# ---------------------------------------------------------------------------


async def has_access_to_file(
    file_id: Optional[str],
    access_type: str,
    user=Depends(get_verified_user),
) -> bool:
    """Return True when *user* has *access_type* permission on *file_id*."""
    file = await _fetch_file(file_id)
    return await _can_access_via_knowledge(file, user, access_type)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("/", response_model=FileModelResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
    file_metadata: dict = {},
    process: bool = Query(True),
):
    log.info(f"file.content_type: {file.content_type}")

    # --- read payload & validate -------------------------------------------
    contents = file.file.read()
    file.file.seek(0)

    max_size = request.app.state.config.FILE_MAX_SIZE
    validate_file_size(contents, max_size)

    filename = validate_file_extension(file.filename)

    # Magic-byte signature validation: block extension/MIME spoofing (fail-secure).
    if request.app.state.config.FILE_MAGIC_VALIDATION_ENABLED:
        ok, reason = validate_file_signature(contents, filename, file.content_type)
        if not ok:
            log.warning(
                "Rejected upload %r: file signature validation failed (%s)",
                file.filename,
                reason,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content does not match its extension ({reason}).",
            )

    # --- persist to storage ------------------------------------------------
    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}_{filename}"
    contents, file_path = await asyncio.to_thread(
        Storage.upload_file, file.file, stored_name
    )

    file_item = await asyncio.to_thread(
        Files.insert_new_file,
        user.id,
        FileForm(
            id=file_id,
            filename=filename,
            path=file_path,
            meta={
                "name": filename,
                "content_type": file.content_type,
                "size": len(contents),
                "data": file_metadata,
            },
        ),
    )

    # --- optional post-processing ------------------------------------------
    if process:
        file_item = await _process_uploaded_file(
            request, file_item, file_id, file.content_type, user
        )

    if file_item is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error uploading file"),
        )

    return file_item


async def _process_uploaded_file(
    request: Request,
    file_item,
    file_id: str,
    content_type: str | None,
    user,
):
    """Run transcription / text-extraction / LLM cleansing on a fresh upload."""
    try:
        if content_type in AUDIO_CONTENT_TYPES:
            await _process_audio(request, file_item, file_id, user)
        elif content_type not in IMAGE_CONTENT_TYPES:
            await _process_document(request, file_item, file_id, user)
    except Exception as exc:
        log.exception(exc)
        log.error(f"Error processing file: {file_item.id}")
        file_item = FileModelResponse(
            **{
                **file_item.model_dump(),
                "error": str(exc.detail) if hasattr(exc, "detail") else str(exc),
            }
        )
    return file_item


async def _process_audio(request, file_item, file_id, user):
    local_path = await asyncio.to_thread(Storage.get_file, file_item.path)
    result = await asyncio.to_thread(transcribe, request, local_path)
    await asyncio.to_thread(
        process_file,
        request,
        ProcessFileForm(file_id=file_id, content=result.get("text", "")),
        user=user,
    )


async def _process_document(request, file_item, file_id, user):
    await asyncio.to_thread(
        process_file, request, ProcessFileForm(file_id=file_id), user=user
    )
    refreshed = await asyncio.to_thread(Files.get_file_by_id, id=file_id)
    if refreshed is None:
        return

    text = (refreshed.data or {}).get("content")
    if not text:
        return

    from bcgpt.retrieval.utils import cleanse_text_with_llm

    cleansed = await cleanse_text_with_llm(request, text, user)
    if cleansed != text:
        await asyncio.to_thread(
            Files.update_file_data_by_id, refreshed.id, {"content": cleansed}
        )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[FileModelResponse])
async def list_files(user=Depends(get_verified_user)):
    if user.role == "admin":
        return Files.get_files()
    return Files.get_files_by_user_id(user.id)


# ---------------------------------------------------------------------------
# Delete all
# ---------------------------------------------------------------------------


@router.delete("/all")
async def delete_all_files(user=Depends(get_admin_user)):
    result = Files.delete_all_files()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
        )
    try:
        Storage.delete_all_files()
    except Exception as exc:
        log.exception(exc)
        log.error("Error deleting files")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
        )
    return {"message": "All files deleted successfully"}


# ---------------------------------------------------------------------------
# Get by id
# ---------------------------------------------------------------------------


@router.get("/{id}", response_model=Optional[FileModel])
async def get_file_by_id(id: str, user=Depends(get_verified_user)):
    return await _authorize_read(id, user)


# ---------------------------------------------------------------------------
# Data content
# ---------------------------------------------------------------------------


@router.get("/{id}/data/content")
async def get_file_data_content_by_id(id: str, user=Depends(get_verified_user)):
    file = await _authorize_read(id, user)
    return {"content": (file.data or {}).get("content", "")}


@router.post("/{id}/data/content/update")
async def update_file_data_content_by_id(
    request: Request,
    id: str,
    form_data: ContentForm,
    user=Depends(get_verified_user),
):
    file = await _authorize_write(id, user)
    try:
        process_file(
            request,
            ProcessFileForm(file_id=id, content=form_data.content),
            user=user,
        )
        file = Files.get_file_by_id(id=id)
    except Exception as exc:
        log.exception(exc)
        log.error(f"Error processing file: {file.id}")

    return {"content": (file.data or {}).get("content", "")}


# ---------------------------------------------------------------------------
# File content download
# ---------------------------------------------------------------------------


def _build_content_disposition(
    filename: str, *, attachment: bool = False, content_type: str | None = None
) -> dict[str, str]:
    """Return a headers dict with the appropriate Content-Disposition value."""
    encoded = quote(filename)
    if attachment:
        return {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}

    # PDF files served inline
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        return {"Content-Disposition": f"inline; filename*=UTF-8''{encoded}"}

    # Non-plain-text served as attachment
    if content_type != "text/plain":
        return {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}

    return {}


@router.get("/{id}/content")
async def get_file_content_by_id(
    id: str,
    user=Depends(get_verified_user),
    attachment: bool = Query(False),
):
    file = await _authorize_read(id, user)

    try:
        file_path = Path(Storage.get_file(file.path))
    except Exception as exc:
        log.exception(exc)
        log.error("Error getting file content")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    filename = (file.meta or {}).get("name", file.filename)
    content_type = (file.meta or {}).get("content_type")
    headers = _build_content_disposition(
        filename, attachment=attachment, content_type=content_type
    )
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        content_type = "application/pdf"

    return FileResponse(file_path, headers=headers, media_type=content_type)


@router.get("/{id}/content/html")
async def get_html_file_content_by_id(id: str, user=Depends(get_verified_user)):
    file = await _authorize_read(id, user)

    try:
        file_path = Path(Storage.get_file(file.path))
    except Exception as exc:
        log.exception(exc)
        log.error("Error getting file content")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    headers = {
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(file_path, headers=headers)


@router.get("/{id}/content/{file_name}")
async def get_file_content_by_name(
    id: str,
    file_name: str,
    user=Depends(get_verified_user),
):
    file = await _authorize_read(id, user)

    filename = (file.meta or {}).get("name", file.filename)
    encoded = quote(filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}

    if file.path:
        try:
            file_path = Path(Storage.get_file(file.path))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

        if file_path.is_file():
            return FileResponse(file_path, headers=headers)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    # No storage path — fall back to inline text content
    text_content = (file.content or {}).get("content", "")

    def _stream():
        yield text_content.encode("utf-8")

    return StreamingResponse(
        _stream(),
        media_type="text/plain",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Delete single
# ---------------------------------------------------------------------------


@router.delete("/{id}")
async def delete_file_by_id(id: str, user=Depends(get_verified_user)):
    file = await _authorize_write(id, user)

    result = Files.delete_file_by_id(id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting file"),
        )

    # Remove vector-db traces: vectors from any KB collection the file lives in,
    # plus the standalone `file-{id}` collection (previously leaked here).
    await purge_file_vectors(file)

    try:
        Storage.delete_file(file.path)
    except Exception as exc:
        log.exception(exc)
        log.error("Error deleting files")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
        )

    log_business_event(
        action="file.deleted",
        resource_type="file",
        user=user,
        resource_id=id,
        resource_name=file.filename,
    )

    return {"message": "File deleted successfully"}
