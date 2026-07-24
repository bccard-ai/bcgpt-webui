import json
import re
import logging

from bcgpt.utils import generate_chat_completion, get_task_model_id
from bcgpt.utils.task import _first_non_arena_model

log = logging.getLogger(__name__)


async def llm_rerank(
    query: str,
    documents: list[dict],
    request,
    user,
    model_id: str | None = None,
    top_n: int = 10,
) -> list[dict]:
    if not documents:
        return documents

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

        numbered_docs = ""
        for i, doc in enumerate(documents):
            content = doc.get("text", doc.get("content", ""))
            numbered_docs += f"[{i}] {content[:500]}\n\n"

        prompt = (
            "Rank the following documents by relevance to the query. "
            "Return ONLY a JSON array of indices (0-based) in order of relevance, most relevant first.\n\n"
            f"Query: {query}\n\n"
            f"Documents:\n{numbered_docs}"
            "Ranked indices (JSON array):"
        )

        payload = {
            "model": task_model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 200,
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

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            indices = json.loads(json_match.group(1))
        else:
            indices = json.loads(response_text.strip())

        if not isinstance(indices, list):
            raise ValueError("Response is not a list")

        total = len(documents)
        reordered = []
        used = set()
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < total and idx not in used:
                doc_copy = dict(documents[idx])
                doc_copy["score"] = 1.0 - (len(reordered) / total)
                reordered.append(doc_copy)
                used.add(idx)

        for i, doc in enumerate(documents):
            if i not in used:
                doc_copy = dict(doc)
                doc_copy["score"] = 1.0 - (len(reordered) / total)
                reordered.append(doc_copy)
                used.add(i)

        return reordered[:top_n]

    except Exception as e:
        log.error(f"LLM rerank failed: {e}")
        return [dict(doc) for doc in documents]
