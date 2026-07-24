"""Elasticsearch vector database adapter.

Stores document embeddings in dimension-based indices.  Collections are
logical namespaces distinguished by a ``collection`` keyword field rather
than separate physical indices.  This keeps the index count low since the
embedding vector length is fixed for a given model.

Authentication is resolved in order: API key → basic auth (username +
password).  SSL certificate verification and fingerprint matching are
configurable via environment variables.
"""

from __future__ import annotations

import logging
from typing import Optional

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan

from bcgpt.config import (
    ELASTICSEARCH_API_KEY,
    ELASTICSEARCH_CA_CERTS,
    ELASTICSEARCH_CLOUD_ID,
    ELASTICSEARCH_INDEX_PREFIX,
    ELASTICSEARCH_PASSWORD,
    ELASTICSEARCH_URL,
    ELASTICSEARCH_USERNAME,
    SSL_ASSERT_FINGERPRINT,
)
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.vector import VectorItem, SearchResult, GetResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BATCH_SIZE = 100


def _lazy_import_collection_info():  # noqa: ANN202 – simple deferred import
    """Avoid circular import at module level."""
    from bcgpt.retrieval.vector.main import CollectionInfo

    return CollectionInfo


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ElasticsearchClient:
    """Elasticsearch-backed vector store.

    Each embedding dimension gets its own index named
    ``{prefix}_d{dimension}``.  Documents within the same index are
    partitioned by a ``collection`` keyword so that logical collections
    can share the physical index.
    """

    def __init__(self) -> None:
        self.index_prefix: str = ELASTICSEARCH_INDEX_PREFIX

        basic_auth: tuple[str, str] | None = None
        if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
            basic_auth = (ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)

        self.client = Elasticsearch(
            hosts=[ELASTICSEARCH_URL],
            ca_certs=ELASTICSEARCH_CA_CERTS,
            api_key=ELASTICSEARCH_API_KEY,
            cloud_id=ELASTICSEARCH_CLOUD_ID,
            basic_auth=basic_auth,
            ssl_assert_fingerprint=SSL_ASSERT_FINGERPRINT,
        )

    # ------------------------------------------------------------------
    # Index management helpers
    # ------------------------------------------------------------------

    def _get_index_name(self, dimension: int) -> str:
        """Return the physical index name for *dimension*."""
        return f"{self.index_prefix}_d{dimension}"

    def _has_index(self, dimension: int) -> bool:
        """Check whether the index for *dimension* already exists."""
        return bool(
            self.client.indices.exists(index=self._get_index_name(dimension))
        )

    def _create_index(self, dimension: int) -> None:
        """Create a new index with cosine-similarity dense_vector mapping."""
        body = {
            "mappings": {
                "dynamic_templates": [
                    {"strings": {"match_mapping_type": "string", "mapping": {"type": "keyword"}}}
                ],
                "properties": {
                    "collection": {"type": "keyword"},
                    "id": {"type": "keyword"},
                    "vector": {
                        "type": "dense_vector",
                        "dims": dimension,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "text": {"type": "text"},
                    "metadata": {"type": "object"},
                },
            }
        }
        self.client.indices.create(index=self._get_index_name(dimension), body=body)

    def get_or_create_index(self, dimension: int) -> None:
        """Ensure the index for *dimension* exists, creating it if needed."""
        if not self._has_index(dimension):
            self._create_index(dimension)

    # ------------------------------------------------------------------
    # Result conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_result_to_get_result(result: list) -> Optional[GetResult]:
        """Convert a ``scan`` iterator into a ``GetResult``."""
        if not result:
            return None
        ids, documents, metadatas = [], [], []
        for hit in result:
            ids.append(hit["_id"])
            documents.append(hit["_source"].get("text"))
            metadatas.append(hit["_source"].get("metadata"))
        return GetResult(ids=[ids], documents=[documents], metadatas=[metadatas])

    @staticmethod
    def _result_to_get_result(result: dict) -> Optional[GetResult]:
        """Convert a standard search response into a ``GetResult``."""
        hits = result.get("hits", {}).get("hits", [])
        if not hits:
            return None
        ids, documents, metadatas = [], [], []
        for hit in hits:
            ids.append(hit["_id"])
            documents.append(hit["_source"].get("text"))
            metadatas.append(hit["_source"].get("metadata"))
        return GetResult(ids=[ids], documents=[documents], metadatas=[metadatas])

    @staticmethod
    def _result_to_search_result(result: dict) -> SearchResult:
        """Convert a standard search response into a ``SearchResult``."""
        ids, distances, documents, metadatas = [], [], [], []
        for hit in result.get("hits", {}).get("hits", []):
            ids.append(hit["_id"])
            distances.append(hit["_score"])
            documents.append(hit["_source"].get("text"))
            metadatas.append(hit["_source"].get("metadata"))
        return SearchResult(
            ids=[ids], distances=[distances], documents=[documents], metadatas=[metadatas]
        )

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    @staticmethod
    def _create_batches(items: list[VectorItem], batch_size: int = _BATCH_SIZE):
        """Yield successive batches of *items*."""
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    # ------------------------------------------------------------------
    # Public API – collection operations
    # ------------------------------------------------------------------

    def has_collection(self, collection_name: str) -> Optional[bool]:
        """Return ``True`` if *collection_name* contains at least one document."""
        query_body: dict = {
            "query": {"bool": {"filter": [{"term": {"collection": collection_name}}]}}
        }
        try:
            result = self.client.count(index=f"{self.index_prefix}*", body=query_body)
            return result.body["count"] > 0
        except Exception:
            return None

    def delete_collection(self, collection_name: str) -> None:
        """Remove all documents belonging to *collection_name*."""
        query: dict = {"query": {"term": {"collection": collection_name}}}
        self.client.delete_by_query(index=f"{self.index_prefix}*", body=query)

    def list_collections(self) -> list:
        """Aggregate collection names and document counts across all indices."""
        CollectionInfo = _lazy_import_collection_info()
        result: list = []
        try:
            resp = self.client.search(
                index=f"{self.index_prefix}*",
                body={
                    "size": 0,
                    "aggs": {"collections": {"terms": {"field": "collection", "size": 10000}}},
                },
            )
            for bucket in resp["aggregations"]["collections"]["buckets"]:
                result.append(CollectionInfo(name=bucket["key"], document_count=bucket["doc_count"]))
        except Exception:
            pass
        return result

    # ------------------------------------------------------------------
    # Public API – search / query
    # ------------------------------------------------------------------

    def search(
        self, collection_name: str, vectors: list[list[float]], limit: int
    ) -> Optional[SearchResult]:
        """Perform cosine similarity search for the first query vector."""
        query: dict = {
            "size": limit,
            "_source": ["text", "metadata"],
            "query": {
                "script_score": {
                    "query": {"bool": {"filter": [{"term": {"collection": collection_name}}]}},
                    "script": {
                        "source": "cosineSimilarity(params.vector, 'vector') + 1.0",
                        "params": {"vector": vectors[0]},
                    },
                }
            },
        }
        result = self.client.search(index=self._get_index_name(len(vectors[0])), body=query)
        return self._result_to_search_result(result)

    def query(
        self, collection_name: str, filter: dict, limit: Optional[int] = None
    ) -> Optional[GetResult]:
        """Retrieve documents matching metadata *filter* values."""
        if not self.has_collection(collection_name):
            return None

        query_body: dict = {
            "query": {"bool": {"filter": []}},
            "_source": ["text", "metadata"],
        }
        for field, value in filter.items():
            query_body["query"]["bool"]["filter"].append({"term": {field: value}})
        query_body["query"]["bool"]["filter"].append({"term": {"collection": collection_name}})

        size = limit if limit else 10
        try:
            result = self.client.search(index=f"{self.index_prefix}*", body=query_body, size=size)
            return self._result_to_get_result(result)
        except Exception:
            return None

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Return all documents in *collection_name*."""
        query: dict = {
            "query": {"bool": {"filter": [{"term": {"collection": collection_name}}]}},
            "_source": ["text", "metadata"],
        }
        results = list(scan(self.client, index=f"{self.index_prefix}*", query=query))
        return self._scan_result_to_get_result(results)

    # ------------------------------------------------------------------
    # Public API – mutations
    # ------------------------------------------------------------------

    def insert(self, collection_name: str, items: list[VectorItem]) -> None:
        """Insert new documents into *collection_name* in batches."""
        dimension = len(items[0]["vector"])
        if not self._has_index(dimension):
            self._create_index(dimension)

        index_name = self._get_index_name(dimension)
        for batch in self._create_batches(items):
            actions = [
                {
                    "_index": index_name,
                    "_id": item["id"],
                    "_source": {
                        "collection": collection_name,
                        "vector": item["vector"],
                        "text": item["text"],
                        "metadata": item["metadata"],
                    },
                }
                for item in batch
            ]
            bulk(self.client, actions)

    def upsert(self, collection_name: str, items: list[VectorItem]) -> None:
        """Insert or update documents using Elasticsearch's update API."""
        dimension = len(items[0]["vector"])
        if not self._has_index(dimension):
            self._create_index(dimension)

        for batch in self._create_batches(items):
            actions = [
                {
                    "_op_type": "update",
                    "_index": self._get_index_name(dimension=len(item["vector"])),
                    "_id": item["id"],
                    "doc": {
                        "collection": collection_name,
                        "vector": item["vector"],
                        "text": item["text"],
                        "metadata": item["metadata"],
                    },
                    "doc_as_upsert": True,
                }
                for item in batch
            ]
            bulk(self.client, actions)

    def delete(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        filter: Optional[dict] = None,
    ) -> None:
        """Remove documents by *ids* or metadata *filter*."""
        query: dict = {
            "query": {"bool": {"filter": [{"term": {"collection": collection_name}}]}}
        }
        if ids:
            query["query"]["bool"]["filter"].append({"terms": {"_id": ids}})
        elif filter:
            for field, value in filter.items():
                query["query"]["bool"]["filter"].append({"term": {f"metadata.{field}": value}})
        self.client.delete_by_query(index=f"{self.index_prefix}*", body=query)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Delete all BCGPT-managed indices."""
        indices = self.client.indices.get(index=f"{self.index_prefix}*")
        for index in indices:
            self.client.indices.delete(index=index)
