import re
import json
import logging

from bcgpt.utils import generate_chat_completion, get_task_model_id
from bcgpt.utils.task import _first_non_arena_model

log = logging.getLogger(__name__)

_KR_PARTICLES = re.compile(r"[은는이가을를의에도에서로으로와과하다]$", re.UNICODE)


def _normalize_korean(word: str) -> str:
    return _KR_PARTICLES.sub("", word)


def _keyword_overlap(query: str, content: str) -> float:
    query_terms = [_normalize_korean(t.lower()) for t in query.split()]
    query_terms = [t for t in query_terms if t]
    if not query_terms:
        return 0.0
    content_lower = content.lower()
    found = sum(1 for term in query_terms if term in content_lower)
    return found / len(query_terms)


def grade_documents_heuristic(
    query: str,
    documents: list[dict],
) -> list[dict]:
    results = []
    for doc in documents:
        doc_copy = dict(doc)
        score = doc.get("score", 0.0)
        content = doc.get("text", doc.get("content", ""))
        overlap = _keyword_overlap(query, content)

        if score >= 0.7 and overlap >= 0.3:
            doc_copy["grade"] = "correct"
        elif score >= 0.4 or overlap >= 0.2:
            doc_copy["grade"] = "ambiguous"
        else:
            doc_copy["grade"] = "incorrect"

        results.append(doc_copy)
    return results


async def grade_documents_llm(
    query: str,
    documents: list[dict],
    request,
    user,
    model_id: str | None = None,
) -> list[dict]:
    results = []
    heuristic_results = grade_documents_heuristic(query, documents)

    try:
        if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
            models = {request.state.model["id"]: request.state.model}
        else:
            models = request.app.state.MODELS

        resolved_model_id = model_id
        if resolved_model_id is None:
            resolved_model_id = _first_non_arena_model(models) or next(iter(models))

        task_model_id = get_task_model_id(
            resolved_model_id,
            request.app.state.config.TASK_MODEL,
            request.app.state.config.TASK_MODEL_EXTERNAL,
            models,
        )
    except Exception:
        return heuristic_results

    for i, doc in enumerate(documents):
        doc_copy = dict(doc)

        if i >= 5:
            doc_copy["grade"] = heuristic_results[i]["grade"]
            results.append(doc_copy)
            continue

        content = doc.get("text", doc.get("content", ""))

        try:
            prompt = (
                "Grade whether the following document is relevant to the query. "
                "Respond with ONLY one word: 'correct', 'ambiguous', or 'incorrect'.\n\n"
                f"Query: {query}\n"
                f"Document: {content[:500]}\n\n"
                "Grade:"
            )

            payload = {
                "model": task_model_id,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.1,
                "max_tokens": 10,
            }

            response = await generate_chat_completion(
                request, form_data=payload, user=user
            )

            response_text = ""
            if hasattr(response, "body"):
                body = json.loads(response.body)
                response_text = (
                    body.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
            elif isinstance(response, dict):
                response_text = (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

            grade = response_text.strip().lower()
            if grade in ("correct", "ambiguous", "incorrect"):
                doc_copy["grade"] = grade
            else:
                doc_copy["grade"] = heuristic_results[i]["grade"]

        except Exception:
            doc_copy["grade"] = heuristic_results[i]["grade"]

        results.append(doc_copy)

    return results
