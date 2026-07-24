"""OpenSearch vector database adapter.

Uses OpenSearch's ``knn_vector`` field type with FAISS HNSW for
approximate nearest-neighbour search.  Each logical collection maps
to a separate OpenSearch index named ``{prefix}_{collection}``.
"""

from __future__ import annotations

import logging
from typing import Optional

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from bcgpt.config import (
    OPENSEARCH_CERT_VERIFY,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_SSL,
    OPENSEARCH_URI,
    OPENSEARCH_USERNAME,
)
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.vector import VectorItem, SearchResult, GetResult

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

_BATCH_SIZE = 100


def _lazy_import_collection_info():  # noqa: ANN202
    from bcgpt.retrieval.vector.main import CollectionInfo

    return CollectionInfo


class OpenSearchClient:
    """OpenSearch-backed vector store using k-NN for similarity search."""

    INDEX_PREFIX = "bcgpt"

    def __init__(self) -> None:
        self.index_prefix: str = self.INDEX_PREFIX
        self.client = OpenSearch(
            hosts=[OPENSEARCH_URI],
            use_ssl=OPENSEARCH_SSL,
            verify_certs=OPENSEARCH_CERT_VERIFY,
            http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_index_name(self, collection_name: str) -> str:
        """Return the physical index name for *collection_name*."""
        return f"{self.index_prefix}_{collection_name}"

    @staticmethod
    def _result_to_get_result(result: dict) -> Optional[GetResult]:
        """Convert a search response into a ``GetResult``."""
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
    def _result_to_search_result(result: dict) -> Optional[SearchResult]:
        """Convert a search response into a ``SearchResult``."""
        hits = result.get("hits", {}).get("hits", [])
        if not hits:
            return None
        ids, distances, documents, metadatas = [], [], [], []
        for hit in hits:
            ids.append(hit["_id"])
            distances.append(hit["_score"])
            documents.append(hit["_source"].get("text"))
            metadatas.append(hit["_source"].get("metadata"))
        return SearchResult(ids=[ids], distances=[distances], documents=[documents], metadatas=[metadatas])

    def _create_index(self, collection_name: str, dimension: int) -> None:
        """Create an OpenSearch index with k-NN vector mapping."""
        body = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "vector": {
                        "type": "knn_vector",
                        "dimension": dimension,
                        "index": True,
                        "similarity": "faiss",
                        "method": {
                            "name": "hnsw",
                            "space_type": "innerproduct",
                            "engine": "faiss",
                            "parameters": {"ef_construction": 128, "m": 16},
                        },
                    },
                    "text": {"type": "text"},
                    "metadata": {"type": "object"},
                }
            },
        }
        self.client.indices.create(index=self._get_index_name(collection_name), body=body)

    def _create_index_if_not_exists(self, collection_name: str, dimension: int) -> None:
        """Create the index for *collection_name* only if it does not exist."""
        if not self.has_collection(collection_name):
            self._create_index(collection_name, dimension)

    @staticmethod
    def _create_batches(items: list[VectorItem], batch_size: int = _BATCH_SIZE):
        """Yield successive batches of *items*."""
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    # ------------------------------------------------------------------
    # Collection operations
    # ------------------------------------------------------------------

    def has_collection(self, collection_name: str) -> bool:
        """Check whether the index for *collection_name* exists."""
        return bool(self.client.indices.exists(index=self._get_index_name(collection_name)))

    def delete_collection(self, collection_name: str) -> None:
        """Delete the index for *collection_name*."""
        self.client.indices.delete(index=self._get_index_name(collection_name))

    def list_collections(self) -> list:
        """Return all BCGPT-managed collections with document counts."""
        CollectionInfo = _lazy_import_collection_info()
        result: list = []
        try:
            indices = self.client.indices.get(index=f"{self.index_prefix}_*")
            for index_name in indices:
                display_name = index_name[len(self.index_prefix) + 1 :]
                try:
                    stats = self.client.indices.stats(index=index_name)
                    doc_count = stats["_all"]["primaries"]["docs"]["count"]
                    result.append(CollectionInfo(name=display_name, document_count=doc_count))
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
        """Perform cosine similarity search via script_score query."""
        try:
            if not self.has_collection(collection_name):
                return None

            query: dict = {
                "size": limit,
                "_source": ["text", "metadata"],
                "query": {
                    "script_score": {
                        "query": {"match_all": {}},
                        "script": {
                            "source": "(cosineSimilarity(params.query_value, doc[params.field]) + 1.0) / 2.0",
                            "params": {"field": "vector", "query_value": vectors[0]},
                        },
                    }
                },
            }
            result = self.client.search(index=self._get_index_name(collection_name), body=query)
            return self._result_to_search_result(result)
        except Exception:
            return None

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
            query_body["query"]["bool"]["filter"].append({"match": {"metadata." + str(field): value}})

        size = limit if limit else 10
        try:
            result = self.client.search(index=self._get_index_name(collection_name), body=query_body, size=size)
            return self._result_to_get_result(result)
        except Exception:
            return None

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Return all documents in *collection_name*."""
        query: dict = {"query": {"match_all": {}}, "_source": ["text", "metadata"]}
        result = self.client.search(index=self._get_index_name(collection_name), body=query)
        return self._result_to_get_result(result)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert(self, collection_name: str, items: list[VectorItem]) -> None:
        """Insert documents, creating the index if necessary."""
        self._create_index_if_not_exists(collection_name, len(items[0]["vector"]))
        index_name = self._get_index_name(collection_name)
        for batch in self._create_batches(items):
            actions = [
                {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": item["id"],
                    "_source": {"vector": item["vector"], "text": item["text"], "metadata": item["metadata"]},
                }
                for item in batch
            ]
            bulk(self.client, actions)

    def upsert(self, collection_name: str, items: list[VectorItem]) -> None:
        """Upsert documents, creating the index if necessary."""
        self._create_index_if_not_exists(collection_name, len(items[0]["vector"]))
        index_name = self._get_index_name(collection_name)
        for batch in self._create_batches(items):
            actions = [
                {
                    "_op_type": "update",
                    "_index": index_name,
                    "_id": item["id"],
                    "doc": {"vector": item["vector"], "text": item["text"], "metadata": item["metadata"]},
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
        index_name = self._get_index_name(collection_name)
        if ids:
            actions = [{"_op_type": "delete", "_index": index_name, "_id": doc_id} for doc_id in ids]
            bulk(self.client, actions)
        elif filter:
            query_body: dict = {"query": {"bool": {"filter": []}}}
            for field, value in filter.items():
                query_body["query"]["bool"]["filter"].append({"match": {"metadata." + str(field): value}})
            self.client.delete_by_query(index=index_name, body=query_body)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Delete all BCGPT-managed indices."""
        indices = self.client.indices.get(index=f"{self.index_prefix}_*")
        for index in indices:
            self.client.indices.delete(index=index)
