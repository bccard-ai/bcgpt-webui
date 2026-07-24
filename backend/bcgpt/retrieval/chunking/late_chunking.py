"""Late Chunking — embed full document then apply chunk boundaries via mean pooling.

Based on: "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models"
(Günther et al., 2024, arXiv:2409.04701)

Traditional: chunk → embed each chunk separately (loses cross-chunk context)
Late Chunking: embed full doc → mean pool token embeddings per chunk boundary (preserves context)
"""

import bisect
import logging

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


class LateChunker:
    """Late Chunking with BAAI/bge-m3 (8192 max tokens, 1024-dim)."""

    def __init__(self, sentence_transformer_model, max_tokens: int = 8192):
        self.model = sentence_transformer_model
        self.max_tokens = max_tokens

    def embed_with_spans(
        self,
        text: str,
        char_spans: list[tuple[int, int]],
    ) -> list[list[float]]:
        """Embed full text, then mean-pool token embeddings per chunk span.

        Args:
            text: Full document text
            char_spans: List of (start_char, end_char) for each chunk

        Returns:
            List of embedding vectors (one per chunk)
        """
        if not char_spans:
            return []

        tokenizer = self.model.tokenizer

        # Tokenize full document with offset mapping
        encoded = tokenizer(
            text,
            return_tensors="pt",
            return_offsets_mapping=True,
            truncation=True,
            max_length=self.max_tokens,
        )
        offsets = encoded.pop("offset_mapping").squeeze(0).tolist()

        # Move to same device as model
        device = next(self.model.parameters()).device
        encoded = {k: v.to(device) for k, v in encoded.items()}

        # Forward pass — get per-token embeddings
        output = self.model[0].auto_model(**encoded)
        token_embeddings = output.last_hidden_state.squeeze(0).cpu()

        # Map char spans to token spans
        token_spans = self._char_to_token_spans(char_spans, offsets)

        # Mean pool per span
        chunk_vectors = []
        for start_tok, end_tok in token_spans:
            if end_tok <= start_tok:
                end_tok = min(start_tok + 1, token_embeddings.shape[0])
            span_vecs = token_embeddings[start_tok:end_tok]
            chunk_vec = span_vecs.mean(dim=0).tolist()
            chunk_vectors.append(chunk_vec)

        return chunk_vectors

    def _char_to_token_spans(
        self,
        char_spans: list[tuple[int, int]],
        token_offsets: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Map (char_start, char_end) to (token_start_idx, token_end_idx)."""
        token_starts = [s for s, _ in token_offsets]

        result = []
        for cs, ce in char_spans:
            start = bisect.bisect_right(token_starts, cs)
            if start > 0 and token_starts[start - 1] <= cs:
                start -= 1

            end = start
            while end < len(token_offsets) and token_offsets[end][1] <= ce:
                end += 1

            result.append((start, max(end, start + 1)))
        return result
