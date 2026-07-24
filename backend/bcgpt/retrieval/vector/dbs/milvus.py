"""Milvus vector database adapter.

Provides a uniform interface over Milvus for collection management,
vector search, metadata filtering, and document CRUD.  Collection names
are prefixed with ``bcgpt_`` and hyphens are automatically replaced
with underscores to satisfy Milvus naming constraints.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from pymilvus import DataType, FieldSchema, MilvusClient as Client

from bcgpt.config import MILVUS_DB, MILVUS_TOKEN, MILVUS_URI
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.vector import VectorItem, SearchResult, GetResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

_SAFE_FILTER_KEY = re.compile(r"^[A-Za-z0-9_]+$")


def _safe_filter_items(filter: dict):
    """Yield ``(key, value)`` pairs after validating each metadata key.

    Keys are interpolated raw into Milvus boolean expressions, so a key
    containing quotes or operators could inject arbitrary filter logic.
    Only strict identifiers are accepted.
    """
    for key, value in filter.items():
        if not isinstance(key, str) or not _SAFE_FILTER_KEY.match(key):
            raise ValueError(f"Invalid metadata filter key: {key!r}")
        yield key, value


class MilvusClient:
    """Milvus-backed vector store with the standard BCGPT adapter interface."""

    COLLECTION_PREFIX = "bcgpt"

    def __init__(self) -> None:
        if MILVUS_TOKEN is None:
            self.client = Client(uri=MILVUS_URI, db_name=MILVUS_DB)
        else:
            self.client = Client(uri=MILVUS_URI, db_name=MILVUS_DB, token=MILVUS_TOKEN)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prefixed(self, collection_name: str) -> str:
        """Return the full Milvus collection name with prefix."""
        return f"{self.COLLECTION_PREFIX}_{collection_name.replace('-', '_')}"

    @staticmethod
    def _sanitize(collection_name: str) -> str:
        """Replace hyphens with underscores for Milvus compatibility."""
        return collection_name.replace("-", "_")

    @staticmethod
    def _result_to_get_result(result) -> GetResult:
        """Convert raw Milvus query results into a ``GetResult``."""
        ids, documents, metadatas = [], [], []
        for match in result:
            _ids, _docs, _metas = [], [], []
            for item in match:
                _ids.append(item.get("id"))
                _docs.append(item.get("data", {}).get("text"))
                _metas.append(item.get("metadata"))
            ids.append(_ids)
            documents.append(_docs)
            metadatas.append(_metas)
        return GetResult(ids=ids, documents=documents, metadatas=metadatas)

    @staticmethod
    def _result_to_search_result(result) -> SearchResult:
        """Convert raw Milvus search results into a ``SearchResult``."""
        ids, distances, documents, metadatas = [], [], [], []
        for match in result:
            _ids, _dists, _docs, _metas = [], [], [], []
            for item in match:
                _ids.append(item.get("id"))
                # Normalize Milvus score from [-1, 1] to [0, 1] range.
                # See: https://milvus.io/docs/de/metric.md
                _dists.append((item.get("distance") + 1.0) / 2.0)
                _docs.append(item.get("entity", {}).get("data", {}).get("text"))
                _metas.append(item.get("entity", {}).get("metadata"))
            ids.append(_ids)
            distances.append(_dists)
            documents.append(_docs)
            metadatas.append(_metas)
        return SearchResult(ids=ids, distances=distances, documents=documents, metadatas=metadatas)

    def _create_collection(self, collection_name: str, dimension: int) -> None:
        """Create a new Milvus collection with HNSW index."""
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=65535)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension, description="vector")
        schema.add_field(field_name="data", datatype=DataType.JSON, description="data")
        schema.add_field(field_name="metadata", datatype=DataType.JSON, description="metadata")

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 100},
        )

        self.client.create_collection(
            collection_name=self._prefixed(collection_name),
            schema=schema,
            index_params=index_params,
        )

    def _ensure_collection(self, collection_name: str, dimension: int) -> None:
        """Create the collection if it does not already exist."""
        if not self.client.has_collection(collection_name=self._prefixed(collection_name)):
            self._create_collection(collection_name, dimension)

    # ------------------------------------------------------------------
    # Collection operations
    # ------------------------------------------------------------------

    def has_collection(self, collection_name: str) -> bool:
        """Check whether *collection_name* exists."""
        return self.client.has_collection(collection_name=self._prefixed(collection_name))

    def delete_collection(self, collection_name: str):
        """Drop the Milvus collection for *collection_name*."""
        return self.client.drop_collection(collection_name=self._prefixed(collection_name))

    def list_collections(self) -> list:
        """Return all BCGPT-managed collections with document counts."""
        from bcgpt.retrieval.vector.main import CollectionInfo

        result: list = []
        try:
            for name in self.client.list_collections():
                if not name.startswith(f"{self.COLLECTION_PREFIX}_"):
                    continue
                display_name = name[len(self.COLLECTION_PREFIX) + 1 :]
                try:
                    from pymilvus import Collection

                    col = Collection(name)
                    col.load()
                    count = col.num_entities
                    result.append(CollectionInfo(name=display_name, document_count=count))
                except Exception:
                    result.append(CollectionInfo(name=display_name, document_count=0))
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
        result = self.client.search(
            collection_name=self._prefixed(collection_name),
            data=vectors,
            limit=limit,
            output_fields=["data", "metadata"],
        )
        return self._result_to_search_result(result)

    def query(
        self, collection_name: str, filter: dict, limit: Optional[int] = None
    ):
        """Retrieve documents matching metadata *filter* with pagination."""
        if not self.has_collection(collection_name):
            return None

        filter_string = " && ".join(
            f'metadata["{key}"] == {json.dumps(value)}'
            for key, value in _safe_filter_items(filter)
        )

        max_limit = 16383
        all_results: list = []
        remaining = limit if limit is not None else float("inf")
        offset = 0

        try:
            while remaining > 0:
                current_fetch = min(max_limit, remaining)
                results = self.client.query(
                    collection_name=self._prefixed(collection_name),
                    filter=filter_string,
                    output_fields=["*"],
                    limit=current_fetch,
                    offset=offset,
                )
                if not results:
                    break
                all_results.extend(results)
                count = len(results)
                remaining -= count
                offset += count
                if count < current_fetch:
                    break
            return self._result_to_get_result([all_results])
        except Exception:
            log.exception("Error querying collection %s", collection_name)
            return None

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Return all documents in *collection_name*."""
        result = self.client.query(
            collection_name=self._prefixed(collection_name),
            filter='id != ""',
        )
        return self._result_to_get_result([result])

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert(self, collection_name: str, items: list[VectorItem]):
        """Insert documents, creating the collection if necessary."""
        self._ensure_collection(collection_name, len(items[0]["vector"]))
        return self.client.insert(
            collection_name=self._prefixed(collection_name),
            data=[
                {"id": item["id"], "vector": item["vector"], "data": {"text": item["text"]}, "metadata": item["metadata"]}
                for item in items
            ],
        )

    def upsert(self, collection_name: str, items: list[VectorItem]):
        """Upsert documents, creating the collection if necessary."""
        self._ensure_collection(collection_name, len(items[0]["vector"]))
        return self.client.upsert(
            collection_name=self._prefixed(collection_name),
            data=[
                {"id": item["id"], "vector": item["vector"], "data": {"text": item["text"]}, "metadata": item["metadata"]}
                for item in items
            ],
        )

    def delete(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        filter: Optional[dict] = None,
    ):
        """Delete documents by *ids* or metadata *filter*."""
        if ids:
            return self.client.delete(collection_name=self._prefixed(collection_name), ids=ids)
        if filter:
            filter_string = " && ".join(
                f'metadata["{key}"] == {json.dumps(value)}'
                for key, value in _safe_filter_items(filter)
            )
            return self.client.delete(collection_name=self._prefixed(collection_name), filter=filter_string)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Drop all BCGPT-managed collections."""
        for name in self.client.list_collections():
            if name.startswith(self.COLLECTION_PREFIX):
                self.client.drop_collection(collection_name=name)
