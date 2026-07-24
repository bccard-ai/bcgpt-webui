"""File-to-context resolution for RAG retrieval.

Translates a list of file references (uploaded files, collections,
web-search results, etc.) into structured source dictionaries ready
for the RAG pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Files

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def get_sources_from_files(
    request,
    files: list[dict],
    queries: list[str],
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
    hybrid_search: bool,
    full_context: bool = False,
    rrf_k: int = 60,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict[str, Any]]:
    """Resolve *files* into a list of ``{"source", "document", "metadata", …}`` dicts.

    This is the central dispatch function called by the RAG pipeline to turn
    user-specified file / collection references into searchable contexts.
    """
    from bcgpt.retrieval.search import (
        get_all_items_from_collections,
        query_collection,
        query_collection_with_hybrid_search,
    )

    log.debug(
        "files: %s queries=%s embedding_function=%s reranking_function=%s full_context=%s",
        files,
        queries,
        embedding_function,
        reranking_function,
        full_context,
    )

    extracted_collections: list[str] = []
    relevant_contexts: list[dict] = []

    for file in files:
        context = _resolve_file_context(
            request=request,
            file=file,
            queries=queries,
            embedding_function=embedding_function,
            k=k,
            reranking_function=reranking_function,
            k_reranker=k_reranker,
            r=r,
            hybrid_search=hybrid_search,
            full_context=full_context,
            rrf_k=rrf_k,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            extracted_collections=extracted_collections,
        )

        if context:
            if "data" in file:
                del file["data"]
            # Strip the server-side trust marker so it does not leak into the
            # sources/citations payload. (Set on model.meta.knowledge refs.)
            file.pop("__model_knowledge__", None)
            relevant_contexts.append({**context, "file": file})

    return _build_sources(relevant_contexts)


async def assert_files_access(files: list[dict], user) -> None:
    """Server-side ACL check on the collection references carried in *files*.

    Applies to **client-supplied** file references only. Entries tagged
    ``__model_knowledge__`` were injected from the persisted
    ``model.info.meta.knowledge`` by the model's owner and are trusted — they are
    skipped here so an admin-curated agent KB stays available to users of the
    agent (access to those KBs is governed by the model's own ``access_control``,
    which already gated the user's ability to use the model at all).

    For every remaining file, each collection name it resolves to (via
    ``_resolve_collection_names``) is checked with the canonical
    ``check_collection_access``. Raises ``HTTPException(403)`` on the first
    reference the user cannot read.
    """
    from bcgpt.retrieval.lifecycle import check_collection_access

    for file in files:
        if file.get("__model_knowledge__"):
            continue
        for name in _resolve_collection_names(file):
            await asyncio.to_thread(check_collection_access, name, user)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_file_context(
    *,
    request,
    file: dict,
    queries: list[str],
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
    hybrid_search: bool,
    full_context: bool,
    rrf_k: int,
    vector_weight: float,
    keyword_weight: float,
    extracted_collections: list[str],
) -> dict | None:
    """Determine the search context for a single *file* entry."""

    # --- Pre-supplied docs (web-search bypass) ---
    if file.get("docs"):
        return {
            "documents": [[doc.get("content") for doc in file["docs"]]],
            "metadatas": [[doc.get("metadata") for doc in file["docs"]]],
        }

    # --- Manual full-context toggle ---
    if file.get("context") == "full":
        return {
            "documents": [[file.get("file", {}).get("data", {}).get("content")]],
            "metadatas": [[{"file_id": file.get("id"), "name": file.get("name")}]],
        }

    # --- Bypass embedding & retrieval ---
    if (
        file.get("type") != "web_search"
        and request.app.state.config.BYPASS_EMBEDDING_AND_RETRIEVAL
    ):
        return _bypass_context(file)

    # --- Normal retrieval path ---
    return _retrieval_context(
        file=file,
        queries=queries,
        embedding_function=embedding_function,
        k=k,
        reranking_function=reranking_function,
        k_reranker=k_reranker,
        r=r,
        hybrid_search=hybrid_search,
        full_context=full_context,
        rrf_k=rrf_k,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
        extracted_collections=extracted_collections,
    )


def _bypass_context(file: dict) -> dict | None:
    """Build context when embedding/retrieval is bypassed."""
    if file.get("type") == "collection":
        file_ids = file.get("data", {}).get("file_ids", [])
        documents, metadatas = [], []
        for fid in file_ids:
            obj = Files.get_file_by_id(fid)
            if obj:
                documents.append(obj.data.get("content", ""))
                metadatas.append(
                    {"file_id": fid, "name": obj.filename, "source": obj.filename}
                )
        return {"documents": [documents], "metadatas": [metadatas]}

    if file.get("id"):
        obj = Files.get_file_by_id(file["id"])
        if obj:
            return {
                "documents": [[obj.data.get("content", "")]],
                "metadatas": [
                    [
                        {
                            "file_id": file["id"],
                            "name": obj.filename,
                            "source": obj.filename,
                        }
                    ]
                ],
            }

    if file.get("file", {}).get("data"):
        return {
            "documents": [[file["file"]["data"].get("content")]],
            "metadatas": [[file["file"]["data"].get("metadata", {})]],
        }

    return None


def _retrieval_context(
    *,
    file: dict,
    queries: list[str],
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
    hybrid_search: bool,
    full_context: bool,
    rrf_k: int,
    vector_weight: float,
    keyword_weight: float,
    extracted_collections: list[str],
) -> dict | None:
    """Resolve context via vector search or full-context fetch."""
    from bcgpt.retrieval.search import (
        get_all_items_from_collections,
        query_collection,
        query_collection_with_hybrid_search,
    )

    # No embedding function → fall back to raw file content
    if embedding_function is None:
        obj = Files.get_file_by_id(file.get("id")) if file.get("id") else None
        if obj:
            return {
                "documents": [[obj.data.get("content", "")]],
                "metadatas": [
                    [
                        {
                            "file_id": file["id"],
                            "name": obj.filename,
                            "source": obj.filename,
                        }
                    ]
                ],
            }
        return None

    # Determine collection names
    collection_names = _resolve_collection_names(file)

    # Deduplicate against already-extracted collections
    collection_names = list(set(collection_names).difference(extracted_collections))
    if not collection_names:
        log.debug("Skipping file %s — collection already extracted", file.get("id"))
        return None

    if full_context:
        try:
            return get_all_items_from_collections(collection_names)
        except Exception as exc:
            log.exception(exc)
            return None

    # Normal search path
    try:
        if file.get("type") == "text":
            return file.get("content")

        # P1.3: corpus path — filtered single-collection ANN. Dormant unless
        # RAG_USE_CORPUS is on. KB-id and standalone-file refs are eligible;
        # legacy bare-collection refs fall through to the per-collection path.
        # If the corpus yields nothing (KB not yet migrated / empty), fall back
        # to the legacy path so retrieval degrades gracefully mid-migration.
        from bcgpt import config as _cfg

        if bool(getattr(_cfg.RAG_USE_CORPUS, "value", _cfg.RAG_USE_CORPUS)):
            corpus_filter = _resolve_corpus_filter(file)
            if corpus_filter is not None:
                knowledge_ids, file_ids = corpus_filter
                from bcgpt.retrieval.search import query_corpus
                from bcgpt.retrieval.vector.corpus import (
                    DEFAULT_WORKSPACE_ID,
                    corpus_collection_name,
                )

                corpus_name = corpus_collection_name(
                    engine=_cfg.RAG_EMBEDDING_ENGINE, model=_cfg.RAG_EMBEDDING_MODEL
                )
                corpus_context = query_corpus(
                    corpus_name=corpus_name,
                    queries=queries,
                    embedding_function=embedding_function,
                    k=k,
                    knowledge_ids=knowledge_ids,
                    file_ids=file_ids,
                    workspace_id=DEFAULT_WORKSPACE_ID,
                )
                if _context_has_documents(corpus_context):
                    extracted_collections.extend(collection_names)
                    return corpus_context
                # else: corpus empty — fall through to legacy per-collection query

        context = None
        if hybrid_search:
            try:
                context = query_collection_with_hybrid_search(
                    collection_names=collection_names,
                    queries=queries,
                    embedding_function=embedding_function,
                    k=k,
                    reranking_function=reranking_function,
                    k_reranker=k_reranker,
                    r=r,
                    rrf_k=rrf_k,
                    vector_weight=vector_weight,
                    keyword_weight=keyword_weight,
                )
            except Exception:
                log.debug("Hybrid search failed, falling back to vector search")

        if not hybrid_search or context is None:
            context = query_collection(
                collection_names=collection_names,
                queries=queries,
                embedding_function=embedding_function,
                k=k,
            )

        extracted_collections.extend(collection_names)
        return context
    except Exception as exc:
        log.exception(exc)
        return None


def _resolve_collection_names(file: dict) -> list[str]:
    """Extract collection names from a file reference."""
    names: list[str] = []

    if file.get("type") == "collection":
        if file.get("legacy"):
            names = file.get("collection_names", [])
        else:
            names.append(file["id"])
    elif file.get("collection_name"):
        names.append(file["collection_name"])
    elif file.get("id"):
        prefix = f"{file['id']}" if file.get("legacy") else f"file-{file['id']}"
        names.append(prefix)

    return names


def _resolve_corpus_filter(
    file: dict,
) -> tuple[list[str] | None, list[str] | None] | None:
    """Extract (knowledge_ids, file_ids) for corpus filtering from a file ref.

    Returns None when the ref is not corpus-eligible (legacy bare
    ``collection_names``, web_search, text, etc.) so the caller falls back to
    the per-collection path. For a KB-id collection ref the KB id becomes a
    ``knowledge_id`` filter; for a standalone uploaded-file ref the file id
    becomes a ``file_id`` filter.
    """
    if file.get("type") == "collection":
        if file.get("legacy"):
            return None
        kid = file.get("id")
        return ([kid], None) if kid else (None, None)
    if file.get("collection_name"):
        # explicit collection_name (not the corpus model) — leave to legacy path
        return None
    if file.get("id"):
        return (None, [file["id"]])
    return None


def _context_has_documents(context) -> bool:
    """Return True if a merged query result carries at least one document."""
    if not isinstance(context, dict):
        return False
    docs = context.get("documents")
    if not docs:
        return False
    return any(len(row) > 0 for row in docs)


def _build_sources(relevant_contexts: list[dict]) -> list[dict[str, Any]]:
    """Convert raw contexts into source dicts for the RAG pipeline."""
    sources: list[dict[str, Any]] = []
    for ctx in relevant_contexts:
        try:
            if "documents" not in ctx:
                continue
            if "metadatas" not in ctx:
                continue

            source: dict[str, Any] = {
                "source": ctx["file"],
                "document": ctx["documents"][0],
                "metadata": ctx["metadatas"][0],
            }
            if "distances" in ctx and ctx["distances"]:
                source["distances"] = ctx["distances"][0]

            sources.append(source)
        except Exception as exc:
            log.exception(exc)

    return sources
