"""LangChain-compatible reranking components.

Provides:
* ``RerankCompressor`` – LangChain ``BaseDocumentCompressor`` that scores and
  filters documents using either a reranking model or cosine-similarity fallback.
* ``ExternalReranker`` – Drop-in replacement for
  ``sentence_transformers.CrossEncoder`` that delegates to a vLLM ``/v1/score``
  endpoint.
"""

from __future__ import annotations

import logging
import operator
from typing import Any, Optional, Sequence

import numpy as np
import requests
from pydantic import ConfigDict
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document

from bcgpt.config import RAG_EMBEDDING_QUERY_PREFIX, RAG_EMBEDDING_CONTENT_PREFIX
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class RerankCompressor(BaseDocumentCompressor):
    """Score and filter documents via a reranker or cosine-similarity fallback.

    When *reranking_function* is provided (e.g. a ``CrossEncoder`` or
    ``ExternalReranker``), ``predict(pairs)`` is called directly.  Otherwise
    embeddings + cosine similarity are used as a fallback.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    embedding_function: Any
    top_n: int
    reranking_function: Any
    r_score: float

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        reranking = self.reranking_function is not None

        if reranking:
            scores = self.reranking_function.predict(
                [(query, doc.page_content) for doc in documents]
            )
        else:
            from sentence_transformers import util

            query_embedding = self.embedding_function(query, RAG_EMBEDDING_QUERY_PREFIX)
            document_embedding = self.embedding_function(
                [doc.page_content for doc in documents], RAG_EMBEDDING_CONTENT_PREFIX
            )
            scores = util.cos_sim(query_embedding, document_embedding)[0]

        docs_with_scores = list(zip(documents, scores.tolist()))

        if self.r_score:
            docs_with_scores = [
                (d, s) for d, s in docs_with_scores if s >= self.r_score
            ]
            docs_with_scores = [
                (d, s) for d, s in docs_with_scores if s >= self.r_score
            ]

        result = sorted(docs_with_scores, key=operator.itemgetter(1), reverse=True)
        final: list[Document] = []
        for doc, doc_score in result[: self.top_n]:
            metadata = {**doc.metadata, "score": doc_score}
            final.append(Document(page_content=doc.page_content, metadata=metadata))
        return final


class ExternalReranker:
    """Reranker that calls a vLLM ``/v1/score`` endpoint.

    Drop-in replacement for ``sentence_transformers.CrossEncoder`` — exposes
    the same ``predict(pairs)`` interface expected by ``RerankCompressor``.
    """

    def __init__(self, uri: str, api_key: str, model: str):
        self.uri = uri.rstrip("/")
        self.api_key = api_key
        self.model = model

    def predict(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        """Score ``(query, document)`` pairs via the external API.

        Returns a numpy array of scores matching the
        ``CrossEncoder.predict`` return shape.
        """
        if not pairs:
            return np.array([], dtype=float)

        query = pairs[0][0]
        documents = [p[1] for p in pairs]

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.post(
                f"{self.uri}/v1/score",
                headers=headers,
                json={
                    "model": self.model,
                    "text_1": query,
                    "text_2": documents,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            scores = [0.0] * len(documents)
            for item in data.get("data", []):
                idx = item.get("index", 0)
                if idx < len(scores):
                    scores[idx] = item.get("score", 0.0)

            return np.array(scores)

        except Exception as exc:
            log.exception("ExternalReranker error: %s", exc)
            return np.zeros(len(documents))
