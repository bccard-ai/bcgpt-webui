"""Corpus-collection naming and metadata fields for consolidated RAG (P1).

Target architecture (option B): instead of one Qdrant collection per file
(``file-{id}``) and per KB (``{knowledge.id}``), all vectors live in a small
number of **corpus** collections — one per embedding-model configuration — and
retrieval scopes by payload filter (``metadata.knowledge_id`` etc.).

A Qdrant collection holds a single vector dimension, so the corpus is sharded
by embedding config. The collection name is derived from a stable SHA-1 of
``(engine, model, prefix)``; the adapter prepends its ``bcgpt_`` prefix, so the
final name in Qdrant is ``bcgpt_corpus_<sha1>``. Same config ⇒ same name ⇒ same
collection ⇒ same dimension, so no dimension probing is required to name it.

KBs become logical groupings: every chunk carries ``metadata.knowledge_id``
(the KB uuid, or None for a standalone upload), ``metadata.workspace_id``
(forward-compat partition key, ``"default"`` for now), plus the existing
``file_id`` and ``embedding_config``. These four fields carry payload indexes
(see ``PAYLOAD_INDEX_FIELDS``) so filtered ANN is fast.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Metadata fields that should carry a Qdrant payload index on corpus collections
#: so filtered ANN (by knowledge_id / file_id / workspace_id / embedding_config)
#: stays fast as the corpus grows. Field names are unprefixed; the adapter adds
#: the ``metadata.`` namespace when creating the index.
PAYLOAD_INDEX_FIELDS: tuple[str, ...] = (
    "knowledge_id",
    "file_id",
    "workspace_id",
    "embedding_config",
)

#: Value stamped on every chunk for the forward-compatible workspace partition
#: key. No-op today (single-org); becomes the partition filter if real
#: multi-tenancy is introduced later (roadmap P3).
DEFAULT_WORKSPACE_ID = "default"


def _norm(value: Any) -> Any:
    """Reduce a PersistentConfig to its underlying value; pass through otherwise."""
    return getattr(value, "value", value)


def corpus_collection_name(
    embedding_config: dict | None = None,
    *,
    engine: Any = None,
    model: Any = None,
    prefix: Any = None,
) -> str:
    """Return the deterministic corpus collection name for an embedding config.

    Args:
        embedding_config: optional dict (e.g. ``{"engine", "model"}`` as stamped
            on chunk metadata). When provided its keys seed the hash.
        engine/model/prefix: explicit overrides (PersistentConfig values are
            normalised via ``.value``).

    Returns:
        Unprefixed name like ``corpus_<sha1[:16]>``. The Qdrant adapter prepends
        ``bcgpt_``, yielding ``bcgpt_corpus_<sha1[:16]>``.
    """
    if embedding_config:
        engine = embedding_config.get("engine", engine)
        model = embedding_config.get("model", model)
        prefix = embedding_config.get("prefix", prefix)
    raw = json.dumps(
        {"engine": _norm(engine), "model": _norm(model), "prefix": _norm(prefix)},
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"corpus_{digest}"
