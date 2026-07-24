import re
import json
import logging

from bcgpt.utils import generate_chat_completion, get_task_model_id
from bcgpt.utils.task import _first_non_arena_model

log = logging.getLogger(__name__)

_MULTI_HOP_PATTERN = re.compile(
    r"(compare|versus|vs\.?|difference between|relationship between|"
    r"history of|evolution of|impact of.*on|how.*affect|"
    r"비교|차이|관계|영향|역사|변화)",
    re.IGNORECASE,
)


def should_multi_hop(query: str) -> bool:
    return bool(_MULTI_HOP_PATTERN.search(query))


async def decompose_query(
    query: str,
    request,
    user,
    model_id: str | None = None,
) -> list[dict]:
    if not should_multi_hop(query):
        return []

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

        prompt = (
            "Break down this complex query into 2-4 sub-queries that need to be answered separately.\n\n"
            f'Query: "{query}"\n\n'
            "Return ONLY a JSON array of objects:\n"
            "[\n"
            '  {"query": "first sub-query", "depends_on": []},\n'
            '  {"query": "second sub-query", "depends_on": [0]}\n'
            "]\n\n"
            "Rules:\n"
            "- Start with foundational queries (no dependencies)\n"
            "- Later queries can build on earlier ones\n"
            "- Keep each sub-query focused and answerable"
        )

        payload = {
            "model": task_model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 500,
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
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(response_text.strip())

        if not isinstance(parsed, list):
            return []

        sub_queries = []
        for item in parsed[:4]:
            if isinstance(item, dict) and "query" in item:
                depends = item.get("depends_on")
                if depends is not None and not isinstance(depends, list):
                    depends = None
                sub_queries.append(
                    {
                        "query": str(item["query"]),
                        "depends_on": depends,
                    }
                )

        return sub_queries

    except Exception as e:
        log.error(f"Query decomposition failed: {e}")
        return []
