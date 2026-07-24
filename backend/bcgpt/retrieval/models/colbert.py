"""ColBERT late-interaction reranking model.

Wraps the ``colbert`` library to provide similarity scoring between
query and document token-level embeddings using the MaxSim operator.
"""

from __future__ import annotations

import logging
import os

import numpy as np
import torch
from colbert.infra import ColBERTConfig
from colbert.modeling.checkpoint import Checkpoint

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class ColBERT:
    """ColBERT model for late-interaction relevance scoring.

    Args:
        name: Model checkpoint name or path.
        env: Set to ``"docker"`` to work around torch extension caching
            issues inside containers.
    """

    def __init__(self, name: str, **kwargs) -> None:
        log.info("ColBERT: loading model %s", name)
        self.device: str = "cuda" if torch.cuda.is_available() else "cpu"

        if kwargs.get("env") == "docker":
            # Docker containers sometimes leave stale lock files that prevent
            # the segmented_maxsim_cpp extension from loading.
            lock_file = "/root/.cache/torch_extensions/py311_cpu/segmented_maxsim_cpp/lock"
            if os.path.exists(lock_file):
                os.remove(lock_file)

        self.ckpt = Checkpoint(name, colbert_config=ColBERTConfig(model_name=name)).to(self.device)

    def calculate_similarity_scores(
        self,
        query_embeddings: torch.Tensor,
        document_embeddings: torch.Tensor,
    ) -> np.ndarray:
        """Compute ColBERT MaxSim scores between queries and documents.

        Args:
            query_embeddings: Shape ``(num_queries, seq_len_q, dim)``.
            document_embeddings: Shape ``(num_docs, seq_len_d, dim)``.

        Returns:
            Softmax-normalised relevance scores as a float32 NumPy array
            of shape ``(num_docs,)``.
        """
        query_embeddings = query_embeddings.to(self.device)
        document_embeddings = document_embeddings.to(self.device)

        if query_embeddings.dim() != 3:
            raise ValueError(f"Expected 3-D query embeddings, got {query_embeddings.dim()}.")
        if document_embeddings.dim() != 3:
            raise ValueError(f"Expected 3-D document embeddings, got {document_embeddings.dim()}.")
        if query_embeddings.size(0) not in (1, document_embeddings.size(0)):
            raise ValueError("There should be either one query or queries equal to the number of documents.")

        # MaxSim: for each document token, find the max similarity with any
        # query token, then sum across document tokens.
        transposed = query_embeddings.permute(0, 2, 1)
        scores = torch.matmul(document_embeddings, transposed)
        max_scores = torch.max(scores, dim=1).values
        final_scores = max_scores.sum(dim=1)

        normalised = torch.softmax(final_scores, dim=0)
        return normalised.detach().cpu().numpy().astype(np.float32)

    def predict(self, sentences: list[tuple[str, str]]) -> np.ndarray:
        """Score query-document pairs using the ColBERT checkpoint.

        Args:
            sentences: List of ``(query, document)`` tuples.  The query
                is taken from ``sentences[0][0]`` and compared against
                every document in the list.

        Returns:
            Normalised relevance scores as a float32 NumPy array.
        """
        query = sentences[0][0]
        docs = [pair[1] for pair in sentences]

        embedded_docs = self.ckpt.docFromText(docs, bsize=32)[0]
        embedded_query = self.ckpt.queryFromText([query], bsize=32)[0]

        scores = self.calculate_similarity_scores(
            embedded_query.unsqueeze(0),
            embedded_docs,
        )
        return scores
