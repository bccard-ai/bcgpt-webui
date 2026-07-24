"""Semantic Cache — stores LLM responses keyed by query embedding similarity.

Uses a dedicated Qdrant collection to cache query->response pairs.
When a new query is semantically similar (>threshold), returns cached response.
"""

import json
import logging
import time
import uuid
from typing import Optional

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

CACHE_COLLECTION = "semantic_cache"
DEFAULT_TTL = 3600  # 1 hour default TTL


class SemanticCache:
    """Qdrant-backed semantic cache for LLM responses.

    Stores query embedding -> response text + sources mapping.
    Cosine similarity threshold controls cache hit/miss.
    TTL support expires stale entries on lookup.
    """

    def __init__(
        self,
        qdrant_client,
        embedding_fn,
        threshold: float = 0.95,
        ttl: int = DEFAULT_TTL,
    ):
        self.client = qdrant_client
        self.embedding_fn = embedding_fn
        self.threshold = threshold
        self.ttl = ttl
        self._initialized = False

    def _ensure_collection(self, dim: int):
        """Create the cache collection if it doesn't exist."""
        if self._initialized:
            return
        try:
            prefixed = f"{self.client.collection_prefix}_{CACHE_COLLECTION}"
            if not self.client.has_collection(CACHE_COLLECTION):
                from qdrant_client.models import Distance, VectorParams

                self.client.client.create_collection(
                    collection_name=prefixed,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
                log.info(f"Created semantic cache collection '{prefixed}' (dim={dim})")
            self._initialized = True
        except Exception as e:
            log.warning(f"Failed to initialize semantic cache: {e}")

    def _collection_name(self) -> str:
        return f"{self.client.collection_prefix}_{CACHE_COLLECTION}"

    def lookup(self, query: str, user_id: str = "") -> Optional[dict]:
        """Check if a semantically similar query exists in cache.

        Returns cached response dict or None if no match.
        """
        try:
            query_vec = self.embedding_fn(query)
            if not query_vec:
                return None

            dim = len(query_vec)
            self._ensure_collection(dim)

            results = self.client.client.query_points(
                collection_name=self._collection_name(),
                query=query_vec,
                limit=1,
                score_threshold=self.threshold,
            )

            if results.points:
                point = results.points[0]
                payload = point.payload or {}

                # Check TTL
                cached_at = payload.get("metadata", {}).get("cached_at", 0)
                if time.time() - cached_at > self.ttl:
                    log.debug(
                        f"Semantic cache entry expired (age={time.time() - cached_at:.0f}s)"
                    )
                    return None

                log.info(
                    f"Semantic cache HIT (score={point.score:.4f}, "
                    f"age={time.time() - cached_at:.0f}s)"
                )
                return {
                    "response": payload.get("text", ""),
                    "sources": json.loads(
                        payload.get("metadata", {}).get("sources", "[]")
                    ),
                    "score": point.score,
                }

            return None
        except Exception as e:
            log.debug(f"Semantic cache lookup failed: {e}")
            return None

    def store(
        self,
        query: str,
        response: str,
        sources: list[dict] = None,
        user_id: str = "",
    ):
        """Store a query->response pair in the semantic cache."""
        try:
            query_vec = self.embedding_fn(query)
            if not query_vec:
                return

            dim = len(query_vec)
            self._ensure_collection(dim)

            point_id = str(uuid.uuid4())
            payload = {
                "text": response,
                "metadata": {
                    "query": query[:200],
                    "sources": json.dumps(sources or [], ensure_ascii=False),
                    "cached_at": time.time(),
                    "user_id": user_id,
                },
            }

            from qdrant_client.models import PointStruct

            point = PointStruct(id=point_id, vector=query_vec, payload=payload)
            self.client.client.upsert(
                collection_name=self._collection_name(), points=[point]
            )

            log.debug(f"Semantic cache STORE (query='{query[:50]}...')")
        except Exception as e:
            log.debug(f"Semantic cache store failed: {e}")
