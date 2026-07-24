"""Data models for the vector retrieval subsystem.

Defines the core types exchanged between vector DB adapters and the
rest of the application: items to store, search results, collection
metadata, and database status.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class VectorItem(BaseModel):
    """A single document with its embedding vector and metadata."""

    id: str
    text: str
    vector: List[float | int]
    metadata: Any


class GetResult(BaseModel):
    """Batched result from a retrieval or query operation.

    Each inner list corresponds to one query (or one collection scan),
    containing the IDs, texts, and metadata of matched documents.
    """

    ids: Optional[List[List[str]]]
    documents: Optional[List[List[str]]]
    metadatas: Optional[List[List[Any]]]


class SearchResult(GetResult):
    """Extended ``GetResult`` that also carries per-document similarity scores."""

    distances: Optional[List[List[float | int]]]


class CollectionInfo(BaseModel):
    """Summary metadata for a single vector DB collection."""

    name: str
    document_count: int
    vector_count: int = 0


class VectorDBStatus(BaseModel):
    """Aggregate status of the active vector DB backend."""

    backend: str
    connected: bool
    collections: list[CollectionInfo] = []
    embedding_engine: str = ""
    embedding_model: str = ""
    total_vectors: int = 0
    cluster_status: str | None = None
    embedding_loaded: bool = True
