def __getattr__(name):
    _mapping = {
        # utils
        "RerankCompressor": ".utils",
        "VectorSearchRetriever": ".utils",
        "generate_embeddings": ".utils",
        "generate_ollama_batch_embeddings": ".utils",
        "generate_openai_batch_embeddings": ".utils",
        "get_all_items_from_collections": ".utils",
        "get_doc": ".utils",
        "get_embedding_function": ".utils",
        "get_model_path": ".utils",
        "get_sources_from_files": ".utils",
        "GetResult": ".vector",
        "log": ".utils",
        "merge_and_sort_query_results": ".utils",
        "merge_get_results": ".utils",
        "query_collection": ".utils",
        "query_collection_with_hybrid_search": ".utils",
        "query_doc": ".utils",
        "query_doc_with_hybrid_search": ".utils",
        # vector.connector
        "VECTOR_DB_CLIENT": ".vector.connector",
        # vector.main (re-exported from vector subpackage)
        "SearchResult": ".web",
        "VectorItem": ".vector",
        # vector.dbs (re-exported for connector.py)
        "ElasticsearchClient": ".vector.dbs",
        "MilvusClient": ".vector.dbs",
        "OpenSearchClient": ".vector.dbs",
        "PgvectorClient": ".vector.dbs",
        "QdrantClient": ".vector.dbs",
        # web (re-exported from web subpackage)
        "get_filtered_results": ".web",
        "get_web_loader": ".web",
        "search_bing": ".web",
        "search_bocha": ".web",
        "search_brave": ".web",
        "search_duckduckgo": ".web",
        "search_exa": ".web",
        "search_google_pse": ".web",
        "search_jina": ".web",
        "search_kagi": ".web",
        "search_mojeek": ".web",
        "search_naver": ".web",
        "search_perplexity": ".web",
        "search_searchapi": ".web",
        "search_searxng": ".web",
        "search_serpapi": ".web",
        "search_serper": ".web",
        "search_serply": ".web",
        "search_serpstack": ".web",
        "search_tavily": ".web",
        # loaders (re-exported from loaders subpackage)
        "Loader": ".loaders",
        "TavilyLoader": ".loaders",
        "YoutubeLoader": ".loaders",
        # models (re-exported from models subpackage)
        "ColBERT": ".models",
    }
    if name in _mapping:
        import importlib

        module = importlib.import_module(_mapping[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
