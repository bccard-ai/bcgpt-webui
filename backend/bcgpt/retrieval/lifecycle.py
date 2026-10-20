"""Vector-DB lifecycle helpers shared across routers.

These were previously private to ``routers/knowledge.py`` (``_delete_file_vectors``,
``_cleanup_orphan_file_collection``). They are needed from ``routers/files.py`` and
the chat retrieval path too, so they live here in a neutral module to avoid
router-to-router import cycles.

Under the per-file collection model (pre-consolidation), each file may have:
  * a standalone ``file-{id}`` collection (created on upload), and/or
  * vectors inside a Knowledge Base collection named ``{knowledge.id}`` whose
    name is recorded on ``File.meta['collection_name']``.

``purge_file_vectors`` removes every vector-db trace of a file in O(1) by reading
``File.meta['collection_name']`` — no full KB scan required.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException, status

from bcgpt.constants import ERROR_MESSAGES
from bcgpt.models.knowledge import Knowledges
from bcgpt.retrieval import VECTOR_DB_CLIENT
from bcgpt.utils import has_access

log = logging.getLogger(__name__)


async def delete_file_vectors(collection_name: str, file_id: str) -> None:
    """Remove all vectors tagged with *file_id* from *collection_name*."""
    try:
        await asyncio.to_thread(
            VECTOR_DB_CLIENT.delete,
            collection_name=collection_name,
            filter={"file_id": file_id},
        )
    except Exception as exc:
        log.debug(
            "Vector delete failed (collection=%s, file=%s): %s",
            collection_name,
            file_id,
            exc,
        )


async def cleanup_orphan_file_collection(file_id: str) -> None:
    """Drop a leftover standalone ``file-{id}`` collection if it exists."""
    try:
        col = f"file-{file_id}"
        if await asyncio.to_thread(
            VECTOR_DB_CLIENT.has_collection, collection_name=col
        ):
            await asyncio.to_thread(
                VECTOR_DB_CLIENT.delete_collection, collection_name=col
            )
    except Exception as exc:
        log.debug("Orphan collection cleanup failed for file %s: %s", file_id, exc)


def check_collection_access(collection_name: str, user) -> None:
    """Raise 403 if *user* cannot access the given vector collection.

    Access model:
      * ``user-{id}`` collections are private — only the owner (or an admin) may read.
      * A collection name matching a Knowledge Base row requires ownership, admin,
        or read access via the KB's ``access_control``.
      * Anything else (e.g. a standalone ``file-{id}`` collection, or a bare
        collection with no KB row) is allowed — file-level access is enforced at
        upload/manage time, and bare collections are admin-gated at registration.

    This is the canonical server-side collection-access check, shared by the
    ``/api/v1/retrieval/query`` endpoints, the live chat retrieval path and the
    agent RAG nodes/tools.
    """
    _check_access(collection_name, user, "read")


def check_collection_write_access(collection_name: str, user) -> None:
    """Raise 403 if *user* may not create, overwrite or add to the collection.

    Stricter than :func:`check_collection_access`: Knowledge Base collections
    need ``write`` access, ``file-{id}`` collections need file ownership, and
    the shared ``corpus_*`` collections are only written by the server itself
    (callers that route to the corpus pick the name; users may not).
    """
    if user.role == "admin":
        return
    if collection_name.startswith("corpus_"):
        _forbid()
    if collection_name.startswith("file-"):
        from bcgpt.models.files import Files

        file = Files.get_file_by_id(collection_name[len("file-") :])
        if file is not None and file.user_id != user.id:
            _forbid()
        return
    _check_access(collection_name, user, "write")


def filter_readable_collections(collection_names, user) -> list[str]:
    """Return the subset of *collection_names* that *user* may read.

    For callers that take collection ids from model or LLM input (agent
    workflow nodes, tool loop) and must drop -- not error on -- ids the
    invoking user cannot read. No user means no access.
    """
    if user is None:
        return []
    allowed: list[str] = []
    for name in collection_names or []:
        try:
            check_collection_access(str(name), user)
        except HTTPException:
            log.warning("Dropped unreadable collection %r for user %s", name, user.id)
            continue
        allowed.append(str(name))
    return allowed


def _forbid() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
    )


def _check_access(collection_name: str, user, permission: str) -> None:
    if collection_name.startswith("user-"):
        own = (f"user-{user.id}", f"user-memory-{user.id}")
        if collection_name not in own and user.role != "admin":
            _forbid()
        return
    kb = Knowledges.get_knowledge_by_id(collection_name)
    if kb is not None and not (
        kb.user_id == user.id
        or user.role == "admin"
        or has_access(user.id, permission, kb.access_control)
    ):
        _forbid()


async def purge_file_vectors(file) -> None:
    """Remove all vector-db traces of *file* (a FileModel-like object).

    If the file currently lives in a Knowledge Base collection
    (``file.meta['collection_name']`` set to a KB id), only its own vectors are
    deleted from that collection, preserving the other files in the KB. Any
    standalone ``file-{id}`` collection is then dropped as well. O(1): uses the
    recorded collection name, no KB scan.
    """
    file_id = file.id
    collection_name = None
    try:
        meta = file.meta or {}
        if isinstance(meta, dict):
            collection_name = meta.get("collection_name")
    except Exception:
        collection_name = None

    standalone = f"file-{file_id}"
    if collection_name and collection_name != standalone:
        await delete_file_vectors(collection_name, file_id)
    await cleanup_orphan_file_collection(file_id)


async def delete_knowledge_vectors(knowledge_id: str) -> None:
    """Remove all corpus vectors tagged with *knowledge_id* (P1.6).

    Under ``RAG_USE_CORPUS`` a KB's vectors live in the shared corpus collection
    (keyed by ``metadata.knowledge_id``), so KB delete/reset must filter-delete
    by ``knowledge_id`` rather than only dropping a legacy ``{knowledge_id}``
    collection. No-op when the flag is off — the caller still drops the legacy
    collection. Idempotent and best-effort (errors logged at debug).
    """
    from bcgpt import config as _cfg

    if not bool(getattr(_cfg.RAG_USE_CORPUS, "value", _cfg.RAG_USE_CORPUS)):
        return
    from bcgpt.retrieval.vector.corpus import corpus_collection_name

    corpus_name = corpus_collection_name(
        engine=_cfg.RAG_EMBEDDING_ENGINE, model=_cfg.RAG_EMBEDDING_MODEL
    )
    try:
        await asyncio.to_thread(
            VECTOR_DB_CLIENT.delete,
            collection_name=corpus_name,
            filter={"knowledge_id": knowledge_id},
        )
    except Exception as exc:
        log.debug("Corpus knowledge delete failed (kb=%s): %s", knowledge_id, exc)
