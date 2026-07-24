"""Corpus consolidation migration (P1.5).

Copies vectors from legacy per-file (``file-{id}``) and per-KB
(``{knowledge.id}``) collections into the shared corpus collection (one per
embedding-model config) so retrieval can use a single filtered-ANN query.

Vector-preserving: scrolls each source collection WITH vectors and upserts into
the corpus (point ids are preserved, so re-runs are idempotent). Re-embedding
never happens — collections whose vector dimension does not match the active
embedding-model shard are LEFT IN PLACE and become dual-read targets (the
``file-{id}``/KB-id retrieval path keeps working for them).

Admin-invoked (see ``POST /api/v1/retrieval/db/consolidate``); safe to re-run.
Does NOT delete source collections — drop empty legacy collections separately
after verifying retrieval parity (top-k Jaccard ≥ 0.9 vs pre-migration).
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _is_legacy_corpus_candidate(name: str) -> bool:
    """True for per-file / per-KB collections; false for corpus/user/web/etc."""
    if name.startswith("corpus_"):
        return False
    if name.startswith("user-"):
        return False
    if name.startswith("web-search-"):
        return False
    if name.endswith("__docstore"):  # parent-child docstore companion
        return False
    return True


def consolidate_corpus(request, *, dry_run: bool = False, page_size: int = 200) -> dict:
    """Migrate legacy collections into the shared corpus by vector copy.

    Returns a summary dict: ``{corpus, dim, migrated, seen,
    skipped_dim_mismatch, dry_run}``. Idempotent — point ids are preserved on
    upsert.

    Raises RuntimeError if the backend lacks ``list_points_with_vectors`` (the
    Qdrant adapter implements it) or the embedding function is unavailable.
    """
    from bcgpt import config as cfg
    from bcgpt.retrieval import VECTOR_DB_CLIENT
    from bcgpt.retrieval.vector.corpus import (
        DEFAULT_WORKSPACE_ID,
        corpus_collection_name,
    )

    corpus_name = corpus_collection_name(
        engine=cfg.RAG_EMBEDDING_ENGINE, model=cfg.RAG_EMBEDDING_MODEL
    )

    # Probe the active embedding dimension (the corpus shard's vector size).
    embedding_fn = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    if embedding_fn is None:
        raise RuntimeError("EMBEDDING_FUNCTION is not initialised on app.state")
    try:
        dim = len(embedding_fn("dimension_probe"))
    except Exception as exc:
        raise RuntimeError(f"Could not probe embedding dimension: {exc}") from exc

    summary: dict = {
        "corpus": corpus_name,
        "dim": dim,
        "migrated": 0,
        "seen": [],
        "skipped_dim_mismatch": [],
        "dry_run": dry_run,
    }

    lister = getattr(VECTOR_DB_CLIENT, "list_points_with_vectors", None)
    if lister is None:
        raise RuntimeError(
            "backend has no list_points_with_vectors; corpus consolidation "
            "requires the Qdrant adapter"
        )

    for c in VECTOR_DB_CLIENT.list_collections():
        name = getattr(c, "name", c)
        if not _is_legacy_corpus_candidate(name):
            continue
        info = VECTOR_DB_CLIENT.get_collection_info(collection_name=name)
        if not info:
            continue
        cdim = info.get("dimension")
        if cdim != dim:
            summary["skipped_dim_mismatch"].append({"collection": name, "dim": cdim})
            continue
        summary["seen"].append(name)
        if dry_run:
            continue

        # knowledge_id: a KB-id collection's points belong to that KB; a
        # file-{id} collection's points are standalone (knowledge_id=None,
        # scoped by their existing file_id metadata).
        knowledge_id = None if name.startswith("file-") else name

        offset = None
        while True:
            page = lister(collection_name=name, limit=page_size, offset=offset)
            if not page or not page.get("points"):
                break
            items = []
            for p in page["points"]:
                vec = p.get("vector")
                if vec is None:
                    continue
                md = dict(p.get("metadata") or {})
                md["knowledge_id"] = knowledge_id
                md["workspace_id"] = DEFAULT_WORKSPACE_ID
                items.append(
                    {
                        "id": p["id"],
                        "vector": vec,
                        "text": p.get("text", ""),
                        "metadata": md,
                    }
                )
            if items:
                VECTOR_DB_CLIENT.upsert(collection_name=corpus_name, items=items)
                summary["migrated"] += len(items)
                log.info(
                    "consolidate_corpus: %s → %s (%d points)",
                    name,
                    corpus_name,
                    len(items),
                )
            offset = page.get("next_offset")
            if not offset:
                break

    log.info(
        "consolidate_corpus done: migrated=%d seen=%d skipped=%d (dry_run=%s)",
        summary["migrated"],
        len(summary["seen"]),
        len(summary["skipped_dim_mismatch"]),
        dry_run,
    )
    return summary
