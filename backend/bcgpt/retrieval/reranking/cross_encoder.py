import logging
import os
import threading

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_model_cache: dict[str, object] = {}
_cache_lock = threading.Lock()


def _get_cross_encoder(model_name: str):
    if model_name in _model_cache:
        return _model_cache[model_name]

    from sentence_transformers import CrossEncoder

    with _cache_lock:
        if model_name in _model_cache:
            return _model_cache[model_name]

        from bcgpt.retrieval.utils import get_model_path

        model_path = get_model_path(model_name)
        log.info(f"Loading CrossEncoder model from {model_path}")

        model = CrossEncoder(model_path)
        _model_cache[model_name] = model
        return model


def cross_encoder_rerank(
    query: str,
    documents: list[dict],
    model_name: str = "BAAI/bge-reranker-v2-m3",
    max_length: int = 512,
    top_k: int = 10,
) -> list[dict]:
    if not documents:
        return []

    if len(documents) == 1:
        doc_copy = dict(documents[0])
        doc_copy["cross_encoder_score"] = 1.0
        doc_copy["score"] = doc_copy.get("score", 0.0)
        return [doc_copy]

    try:
        model = _get_cross_encoder(model_name)

        pairs = [[query, doc.get("text", doc.get("content", ""))] for doc in documents]
        scores = model.predict(pairs, max_length=max_length)

        results = []
        for i, doc in enumerate(documents):
            doc_copy = dict(doc)
            ce_score = float(scores[i])
            doc_copy["cross_encoder_score"] = ce_score
            doc_copy["score"] = ce_score
            results.append(doc_copy)

        results.sort(key=lambda d: d["score"], reverse=True)
        return results[:top_k]

    except Exception as e:
        log.error(f"Cross-encoder rerank failed: {e}")
        return [dict(doc) for doc in documents]
