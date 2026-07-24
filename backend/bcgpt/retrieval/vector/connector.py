"""Vector DB connector — selects and instantiates the configured backend.

The ``VECTOR_DB`` environment variable determines which adapter is
loaded.  Supported values are ``milvus``, ``qdrant``, ``opensearch``,
``pgvector``, and ``elasticsearch``.  An unrecognised value (or an
empty value) falls back to Qdrant.
"""

from __future__ import annotations

from bcgpt.config import VECTOR_DB

if VECTOR_DB == "milvus":
    from bcgpt.retrieval import MilvusClient

    VECTOR_DB_CLIENT = MilvusClient()
elif VECTOR_DB == "qdrant":
    from bcgpt.retrieval import QdrantClient

    VECTOR_DB_CLIENT = QdrantClient()
elif VECTOR_DB == "opensearch":
    from bcgpt.retrieval import OpenSearchClient

    VECTOR_DB_CLIENT = OpenSearchClient()
elif VECTOR_DB == "pgvector":
    from bcgpt.retrieval import PgvectorClient

    VECTOR_DB_CLIENT = PgvectorClient()
elif VECTOR_DB == "elasticsearch":
    from bcgpt.retrieval import ElasticsearchClient

    VECTOR_DB_CLIENT = ElasticsearchClient()
else:
    from bcgpt.retrieval import QdrantClient

    VECTOR_DB_CLIENT = QdrantClient()
