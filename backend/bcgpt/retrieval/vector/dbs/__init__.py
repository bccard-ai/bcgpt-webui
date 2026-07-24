def __getattr__(name):
    _mapping = {
        "Base": ".pgvector",
        "DocumentChunk": ".pgvector",
        "ElasticsearchClient": ".elasticsearch",
        "MilvusClient": ".milvus",
        "NO_LIMIT": ".qdrant",
        "OpenSearchClient": ".opensearch",
        "PgvectorClient": ".pgvector",
        "QdrantClient": ".qdrant",
        "VECTOR_LENGTH": ".pgvector",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
