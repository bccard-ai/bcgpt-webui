"""Backward-compatible facade for ``bcgpt.retrieval`` utilities.

All public symbols are re-exported from their new homes so that existing
imports such as ``from bcgpt.retrieval.utils import query_doc`` continue
to work without changes.

Module layout:

* ``embedding.py``           – embedding generation & model path resolution
* ``search.py``              – vector / hybrid search & result merging
* ``reranking/compressor.py`` – LangChain reranking components
* ``cleansing.py``           – LLM-based text cleansing
* ``source_resolution.py``   – file-to-context resolution
"""

# -- Embedding -----------------------------------------------------------------
from bcgpt.retrieval.embedding import (
    generate_openai_batch_embeddings,
    generate_ollama_batch_embeddings,
    generate_embeddings,
    get_embedding_function,
    get_model_path,
)

# -- Search --------------------------------------------------------------------
from bcgpt.retrieval.search import (
    VectorSearchRetriever,
    query_doc,
    get_doc,
    query_doc_with_hybrid_search,
    query_collection,
    query_collection_with_hybrid_search,
    merge_get_results,
    merge_and_sort_query_results,
    get_all_items_from_collections,
)

# -- Reranking -----------------------------------------------------------------
from bcgpt.retrieval.reranking.compressor import (
    RerankCompressor,
    ExternalReranker,
)

# -- Cleansing -----------------------------------------------------------------
from bcgpt.retrieval.cleansing import (
    FILE_CLEANSE_PROMPT,
    cleanse_text_with_llm,
)

# -- Source resolution ----------------------------------------------------------
from bcgpt.retrieval.source_resolution import (
    get_sources_from_files,
)

__all__ = [
    # Embedding
    "generate_openai_batch_embeddings",
    "generate_ollama_batch_embeddings",
    "generate_embeddings",
    "get_embedding_function",
    "get_model_path",
    # Search
    "VectorSearchRetriever",
    "query_doc",
    "get_doc",
    "query_doc_with_hybrid_search",
    "query_collection",
    "query_collection_with_hybrid_search",
    "merge_get_results",
    "merge_and_sort_query_results",
    "get_all_items_from_collections",
    # Reranking
    "RerankCompressor",
    "ExternalReranker",
    # Cleansing
    "FILE_CLEANSE_PROMPT",
    "cleanse_text_with_llm",
    # Source resolution
    "get_sources_from_files",
]
