import re
import json
import logging
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_KR_PARTICLES = re.compile(r"[은는이가을를의에도에서로으로와과하다]$", re.UNICODE)


def _normalize_korean(word: str) -> str:
    return _KR_PARTICLES.sub("", word)


def _tokenize(text: str) -> list[str]:
    tokens = [_normalize_korean(t.lower()) for t in text.split()]
    return [t for t in tokens if t]


def _doc_content(doc: dict) -> str:
    return doc.get("text", doc.get("content", ""))


def compute_relevance_score(query: str, documents: list[dict]) -> float:
    if not documents:
        return 0.0

    query_terms = _tokenize(query)
    if not query_terms:
        return 0.0

    keyword_scores = []
    similarity_scores = []
    for doc in documents:
        content = _doc_content(doc).lower()
        content_tokens = _tokenize(content)

        found = sum(1 for qt in query_terms if qt in content_tokens)
        keyword_scores.append(found / len(query_terms) if query_terms else 0.0)

        sim = doc.get("score", 0.0)
        # A doc's score may be present but non-numeric (e.g. None) from some
        # retrieval paths; coerce before the scale check to avoid a TypeError
        # on ``None > 1.0`` (which would otherwise crash the whole RAG eval).
        if not isinstance(sim, (int, float)):
            sim = 0.0
        elif sim > 1.0:
            sim = sim / 100.0
        similarity_scores.append(min(sim, 1.0))

    avg_keyword = sum(keyword_scores) / len(keyword_scores)
    avg_similarity = sum(similarity_scores) / len(similarity_scores)

    return min(0.6 * avg_keyword + 0.4 * avg_similarity, 1.0)


def compute_context_precision(documents: list[dict]) -> float:
    if len(documents) <= 1:
        return 0.0

    doc_word_sets = []
    for doc in documents:
        content = _doc_content(doc).lower()
        words = set(_tokenize(content))
        doc_word_sets.append(words)

    pairwise_jaccard = []
    for i in range(len(doc_word_sets)):
        for j in range(i + 1, len(doc_word_sets)):
            a, b = doc_word_sets[i], doc_word_sets[j]
            union = a | b
            if not union:
                jaccard = 0.0
            else:
                jaccard = len(a & b) / len(union)
            pairwise_jaccard.append(jaccard)

    avg_jaccard = sum(pairwise_jaccard) / len(pairwise_jaccard)
    return 1.0 - avg_jaccard


def compute_context_recall_heuristic(query: str, documents: list[dict]) -> float:
    if not documents:
        return 0.0

    query_terms = set(_tokenize(query))
    if not query_terms:
        return 0.0

    all_content = " ".join(_doc_content(doc).lower() for doc in documents)
    all_tokens = set(_tokenize(all_content))

    covered = len(query_terms & all_tokens)
    return covered / len(query_terms)


async def compute_faithfulness(
    query: str,
    answer: str,
    documents: list[dict],
    request,
    user,
) -> float:
    if not answer or not documents:
        return 0.0

    try:
        from bcgpt.utils import generate_chat_completion
        from bcgpt.utils.task import resolve_task_model

        resolved_model_id = resolve_task_model(request, None)
        if not resolved_model_id:
            return _faithfulness_heuristic(answer, documents)

        context = "\n\n".join(
            f"[Doc {i+1}]: {_doc_content(doc)[:800]}" for i, doc in enumerate(documents)
        )

        prompt = (
            "Extract the factual claims from the answer below. "
            "For each claim, determine if it is supported by the provided context documents. "
            'Respond in JSON: {"total_claims": N, "supported_claims": M}\n\n'
            f"Context:\n{context}\n\n"
            f"Answer: {answer}\n\n"
            "JSON:"
        )

        payload = {
            "model": resolved_model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 64,
        }

        response = await generate_chat_completion(request, form_data=payload, user=user)

        response_text = ""
        if hasattr(response, "body"):
            body = json.loads(response.body)
            response_text = (
                body.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
        elif isinstance(response, dict):
            response_text = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

        json_match = re.search(r"\{[^}]+\}", response_text)
        if json_match:
            data = json.loads(json_match.group())
            total = data.get("total_claims", 0)
            supported = data.get("supported_claims", 0)
            if total > 0:
                return min(supported / total, 1.0)

        return _faithfulness_heuristic(answer, documents)

    except Exception as e:
        log.warning(f"Faithfulness LLM evaluation failed: {e}")
        return _faithfulness_heuristic(answer, documents)


def _faithfulness_heuristic(answer: str, documents: list[dict]) -> float:
    answer_terms = _tokenize(answer)
    if not answer_terms:
        return 0.0

    all_content = " ".join(_doc_content(doc).lower() for doc in documents)
    context_tokens = set(_tokenize(all_content))

    supported = sum(1 for t in answer_terms if t in context_tokens)
    return min(supported / len(answer_terms), 1.0)


async def compute_answer_relevance(
    query: str,
    answer: str,
    request,
    user,
) -> float:
    if not answer:
        return 0.0

    try:
        from bcgpt.utils import generate_chat_completion
        from bcgpt.utils.task import resolve_task_model

        resolved_model_id = resolve_task_model(request, None)
        if not resolved_model_id:
            return _answer_relevance_heuristic(query, answer)

        prompt = (
            "Rate how relevant the answer is to the given question on a scale of 0 to 10. "
            "Respond with ONLY a single integer number.\n\n"
            f"Question: {query}\n"
            f"Answer: {answer}\n\n"
            "Rating (0-10):"
        )

        payload = {
            "model": resolved_model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 10,
        }

        response = await generate_chat_completion(request, form_data=payload, user=user)

        response_text = ""
        if hasattr(response, "body"):
            body = json.loads(response.body)
            response_text = (
                body.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
        elif isinstance(response, dict):
            response_text = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

        digits = re.search(r"\b(\d{1,2})\b", response_text.strip())
        if digits:
            score = int(digits.group(1))
            return min(max(score, 0), 10) / 10.0

        return _answer_relevance_heuristic(query, answer)

    except Exception as e:
        log.warning(f"Answer relevance LLM evaluation failed: {e}")
        return _answer_relevance_heuristic(query, answer)


def _answer_relevance_heuristic(query: str, answer: str) -> float:
    query_terms = set(_tokenize(query))
    answer_terms = set(_tokenize(answer))
    if not query_terms or not answer_terms:
        return 0.0
    overlap = len(query_terms & answer_terms)
    return min(overlap / len(query_terms), 1.0)
