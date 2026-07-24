"""Qdrant vector database adapter.

Wraps the ``qdrant_client`` library to provide collection management,
vector similarity search, metadata filtering, and point-level CRUD.
All collection names are automatically prefixed with ``bcgpt_``.
"""

from __future__ import annotations

import logging
from typing import Optional

from qdrant_client import QdrantClient as Qclient
from qdrant_client.http.models import PointStruct
from qdrant_client.models import models

from bcgpt.config import QDRANT_API_KEY, QDRANT_URL
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.vector import VectorItem, SearchResult, GetResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

#: Sentinel value used when no explicit limit is provided — Qdrant defaults to 10 otherwise.
NO_LIMIT = 999999999


class QdrantClient:
    """Qdrant-backed vector store with the standard BCGPT adapter interface."""

    COLLECTION_PREFIX = "bcgpt"

    def __init__(self) -> None:
        self.collection_prefix: str = self.COLLECTION_PREFIX
        self._url = str(QDRANT_URL) if QDRANT_URL else None
        self._api_key = str(QDRANT_API_KEY) if QDRANT_API_KEY else None
        self.client: Optional[Qclient] = self._build_client()

    def _build_client(self) -> Optional[Qclient]:
        """Construct a ``QdrantClient`` from the stored URL and API key."""
        if self._url and self._api_key:
            return Qclient(url=self._url, api_key=self._api_key)
        if self._url:
            return Qclient(url=self._url)
        return None

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def reinitialize(self) -> None:
        """Re-create the Qdrant client (useful after config changes)."""
        self._url = str(QDRANT_URL) if QDRANT_URL else None
        self._api_key = str(QDRANT_API_KEY) if QDRANT_API_KEY else None
        self.client = self._build_client()
        log.info(
            "Qdrant client reinitialized: url=%s, api_key=%s",
            self._url,
            "***" if self._api_key else None,
        )

    def close(self) -> None:
        """Close the underlying Qdrant client connection."""
        if self.client is not None:
            self.client.close()
            log.info("Qdrant client closed.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prefixed(self, collection_name: str) -> str:
        """Return the full Qdrant collection name with prefix."""
        return f"{self.collection_prefix}_{collection_name}"

    @staticmethod
    def _result_to_get_result(points) -> GetResult:
        """Convert Qdrant point results into a ``GetResult``."""
        ids, documents, metadatas = [], [], []
        for point in points:
            payload = point.payload
            ids.append(point.id)
            documents.append(payload["text"])
            metadatas.append(payload["metadata"])
        return GetResult(ids=[ids], documents=[documents], metadatas=[metadatas])

    @staticmethod
    def _create_points(items: list[VectorItem]) -> list[PointStruct]:
        """Build Qdrant ``PointStruct`` objects from ``VectorItem`` dicts."""
        return [
            PointStruct(
                id=item["id"],
                vector=item["vector"],
                payload={"text": item["text"], "metadata": item["metadata"]},
            )
            for item in items
        ]

    def _create_collection(self, collection_name: str, dimension: int) -> None:
        """Create a new Qdrant collection with cosine distance."""
        full_name = self._prefixed(collection_name)
        self.client.create_collection(
            collection_name=full_name,
            vectors_config=models.VectorParams(
                size=dimension, distance=models.Distance.COSINE
            ),
        )
        log.info("Collection %s created.", full_name)

    def _ensure_collection(self, collection_name: str, dimension: int) -> None:
        """Create the collection if it does not already exist."""
        if not self.has_collection(collection_name):
            self._create_collection(collection_name, dimension)

    def ensure_corpus_collection(self, collection_name: str, dimension: int) -> None:
        """Ensure a corpus collection exists and carries the payload indexes.

        Corpus collections (one per embedding-model config — see
        ``retrieval.vector.corpus``) hold many files/KBs and are queried with
        metadata filters, so they need keyword payload indexes on the standard
        filter fields. Index creation is idempotent: 'already exists' / schema
        errors are swallowed at debug level. Only call this for corpus
        collections; per-file and KB collections do not need the indexes.
        """
        self._ensure_collection(collection_name, dimension)
        full = self._prefixed(collection_name)
        from bcgpt.retrieval.vector.corpus import PAYLOAD_INDEX_FIELDS

        for field in PAYLOAD_INDEX_FIELDS:
            try:
                self.client.create_payload_index(
                    collection_name=full,
                    field_name=f"metadata.{field}",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                log.info("Payload index created on %s.metadata.%s", full, field)
            except Exception as exc:
                # already exists, or field not present yet — non-fatal
                log.debug("Payload index %s.metadata.%s skipped: %s", full, field, exc)

    # ------------------------------------------------------------------
    # Collection operations
    # ------------------------------------------------------------------

    def has_collection(self, collection_name: str) -> bool:
        """Check whether *collection_name* exists."""
        return self.client.collection_exists(self._prefixed(collection_name))

    def delete_collection(self, collection_name: str):
        """Delete the Qdrant collection for *collection_name*."""
        return self.client.delete_collection(
            collection_name=self._prefixed(collection_name)
        )

    def list_collections(self) -> list:
        """Return all BCGPT-managed collections with counts."""
        from bcgpt.retrieval.vector.main import CollectionInfo

        result: list = []
        try:
            for c in self.client.get_collections().collections:
                if not c.name.startswith(f"{self.collection_prefix}_"):
                    continue
                display_name = c.name[len(self.collection_prefix) + 1 :]
                try:
                    info = self.client.get_collection(c.name)
                    result.append(
                        CollectionInfo(
                            name=display_name,
                            document_count=info.points_count,
                            vector_count=info.vectors_count or 0,
                        )
                    )
                except Exception:
                    result.append(
                        CollectionInfo(
                            name=display_name, document_count=0, vector_count=0
                        )
                    )
        except Exception:
            pass
        return result

    # ------------------------------------------------------------------
    # Search / query
    # ------------------------------------------------------------------

    def search(
        self, collection_name: str, vectors: list[list[float | int]], limit: int
    ) -> Optional[SearchResult]:
        """Perform approximate nearest-neighbour search."""
        if limit is None:
            limit = NO_LIMIT

        response = self.client.query_points(
            collection_name=self._prefixed(collection_name),
            query=vectors[0],
            limit=limit,
        )
        get_result = self._result_to_get_result(response.points)
        # Qdrant distance is [-1, 1], normalize to [0, 1].
        return SearchResult(
            ids=get_result.ids,
            documents=get_result.documents,
            metadatas=get_result.metadatas,
            distances=[[(point.score + 1.0) / 2.0 for point in response.points]],
        )

    def search_filtered(
        self,
        collection_name: str,
        vectors: list[list[float | int]],
        conditions: list[tuple[str, object]],
        limit: int,
    ) -> Optional[SearchResult]:
        """Filtered approximate-nearest-neighbour search.

        Like :meth:`search` but constrained by metadata *conditions* — a list of
        ``(key, value)`` pairs. A scalar value becomes ``MatchValue`` (equality);
        a list/tuple/set becomes ``MatchAny`` (IN-semantics), which is how the
        corpus path scopes by an allowed-set of ``knowledge_id`` / ``file_id``.
        Keys are metadata field names without the ``metadata.`` prefix (added
        here). Empty IN-lists are skipped (Qdrant rejects an empty ``any``).

        Returns a scored :class:`SearchResult` (distances normalised to
        ``[0, 1]``), or ``None`` if the collection does not exist.
        """
        if not self.has_collection(collection_name):
            return None
        must: list[models.FieldCondition] = []
        for key, value in conditions or []:
            full_key = key if key.startswith("metadata.") else f"metadata.{key}"
            if isinstance(value, (list, tuple, set)):
                values = list(value)
                if not values:
                    continue
                must.append(
                    models.FieldCondition(
                        key=full_key, match=models.MatchAny(any=values)
                    )
                )
            else:
                must.append(
                    models.FieldCondition(
                        key=full_key, match=models.MatchValue(value=value)
                    )
                )
        response = self.client.query_points(
            collection_name=self._prefixed(collection_name),
            query=vectors[0],
            query_filter=models.Filter(must=must) if must else None,
            limit=limit if limit is not None else NO_LIMIT,
        )
        get_result = self._result_to_get_result(response.points)
        return SearchResult(
            ids=get_result.ids,
            documents=get_result.documents,
            metadatas=get_result.metadatas,
            distances=[[(point.score + 1.0) / 2.0 for point in response.points]],
        )

    def query(self, collection_name: str, filter: dict, limit: Optional[int] = None):
        """Retrieve points matching metadata *filter*."""
        if not self.has_collection(collection_name):
            return None
        try:
            if limit is None:
                limit = NO_LIMIT

            conditions = [
                models.FieldCondition(
                    key=f"metadata.{key}", match=models.MatchValue(value=value)
                )
                for key, value in filter.items()
            ]
            points = self.client.query_points(
                collection_name=self._prefixed(collection_name),
                query_filter=models.Filter(should=conditions),
                limit=limit,
            )
            return self._result_to_get_result(points.points)
        except Exception:
            log.exception("Error querying collection '%s'", collection_name)
            return None

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Return all points in *collection_name*."""
        points = self.client.query_points(
            collection_name=self._prefixed(collection_name),
            limit=NO_LIMIT,
        )
        return self._result_to_get_result(points.points)

    def get_collection_info(self, collection_name: str) -> Optional[dict]:
        """Return collection-level stats (point count, dimension, distance, status)."""
        full_name = self._prefixed(collection_name)
        if not self.client.collection_exists(full_name):
            return None
        info = self.client.get_collection(full_name)

        dimension, distance = None, None
        try:
            vectors = info.config.params.vectors
            if hasattr(vectors, "size"):
                dimension = vectors.size
                distance = getattr(vectors.distance, "name", str(vectors.distance))
            elif isinstance(vectors, dict) and vectors:
                first = next(iter(vectors.values()))
                dimension = getattr(first, "size", None)
                dist = getattr(first, "distance", None)
                distance = (
                    getattr(dist, "name", str(dist)) if dist is not None else None
                )
        except Exception:
            pass

        status = getattr(info.status, "value", None) or str(info.status)
        return {
            "points_count": info.points_count or 0,
            "dimension": dimension,
            "distance": distance,
            "status": status,
        }

    def list_points(
        self,
        collection_name: str,
        limit: int = 50,
        offset: Optional[str] = None,
    ) -> Optional[dict]:
        """Page through points using Qdrant's scroll cursor (vectors excluded)."""
        full_name = self._prefixed(collection_name)
        if not self.client.collection_exists(full_name):
            return None

        records, next_offset = self.client.scroll(
            collection_name=full_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points = [
            {
                "id": str(r.id),
                "text": (r.payload or {}).get("text", ""),
                "metadata": (r.payload or {}).get("metadata", {}),
            }
            for r in records
        ]
        return {
            "points": points,
            "next_offset": str(next_offset) if next_offset is not None else None,
        }

    def list_points_with_vectors(
        self,
        collection_name: str,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Optional[dict]:
        """Page through points INCLUDING vectors (admin corpus consolidation).

        Unlike :meth:`list_points` (which omits vectors), this returns each
        point's vector so the consolidation migration can copy points into the
        shared corpus without re-embedding. Larger payloads — admin use only.
        """
        full_name = self._prefixed(collection_name)
        if not self.client.collection_exists(full_name):
            return None
        records, next_offset = self.client.scroll(
            collection_name=full_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        points = [
            {
                "id": str(r.id),
                "text": (r.payload or {}).get("text", ""),
                "metadata": (r.payload or {}).get("metadata", {}) or {},
                "vector": list(r.vector) if r.vector is not None else None,
            }
            for r in records
        ]
        return {
            "points": points,
            "next_offset": str(next_offset) if next_offset is not None else None,
        }

    def delete_points(self, collection_name: str, point_ids: list[str]):
        """Delete points by their Qdrant point IDs."""
        return self.client.delete(
            collection_name=self._prefixed(collection_name),
            points_selector=models.PointIdsList(points=point_ids),
        )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert(self, collection_name: str, items: list[VectorItem]) -> None:
        """Insert points, creating the collection if necessary."""
        self._ensure_collection(collection_name, len(items[0]["vector"]))
        self.client.upload_points(
            self._prefixed(collection_name), self._create_points(items)
        )

    def upsert(self, collection_name: str, items: list[VectorItem]):
        """Upsert points, creating the collection if necessary."""
        self._ensure_collection(collection_name, len(items[0]["vector"]))
        return self.client.upsert(
            self._prefixed(collection_name), self._create_points(items)
        )

    def delete(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        filter: Optional[dict] = None,
    ):
        """Delete points by *ids* or metadata *filter*."""
        conditions: list = []
        if ids:
            conditions = [
                models.FieldCondition(
                    key="metadata.id", match=models.MatchValue(value=id_value)
                )
                for id_value in ids
            ]
        elif filter:
            conditions = [
                models.FieldCondition(
                    key=f"metadata.{key}", match=models.MatchValue(value=value)
                )
                for key, value in filter.items()
            ]
        return self.client.delete(
            collection_name=self._prefixed(collection_name),
            points_selector=models.FilterSelector(
                filter=models.Filter(must=conditions)
            ),
        )

    # ------------------------------------------------------------------
    # Stats / reset
    # ------------------------------------------------------------------

    def get_db_stats(self) -> dict:
        """Aggregate total vector count and cluster status."""
        total_vectors = 0
        cluster_status = None
        try:
            for c in self.client.get_collections().collections:
                if c.name.startswith(f"{self.collection_prefix}_"):
                    try:
                        info = self.client.get_collection(c.name)
                        total_vectors += info.vectors_count or 0
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            cluster = self.client.get_cluster_status()
            cluster_status = getattr(cluster, "status", None)
            if cluster_status:
                cluster_status = str(cluster_status)
        except Exception:
            pass
        return {"total_vectors": total_vectors, "cluster_status": cluster_status}

    def reset(self) -> None:
        """Drop all BCGPT-managed collections."""
        for collection in self.client.get_collections().collections:
            if collection.name.startswith(self.collection_prefix):
                self.client.delete_collection(collection_name=collection.name)
