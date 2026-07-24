import logging
import re

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_RE_BRACKET_NUM = re.compile(r"^\[\d+\]\s*")
_RE_DOT_NUM = re.compile(r"^\d+\.\s*")


async def expand_queries(
    query: str,
    request,
    user,
    max_expansions: int = 3,
    model_id: str | None = None,
) -> list[str]:
    try:
        from bcgpt.utils.task import resolve_task_model

        resolved_model_id = resolve_task_model(request, model_id)
        if not resolved_model_id:
            log.warning("Query expansion: no available model")
            return []

        models = request.app.state.MODELS

        from bcgpt.utils import generate_chat_completion

        user_prompt = (
            f"You are a search query expansion assistant. Generate {max_expansions} "
            f"alternative search queries that capture the same intent but use different "
            f"words, phrases, or perspectives.\n\n"
            f'Original query: "{query}"\n\n'
            f"Generate {max_expansions} alternative queries that:\n"
            f"1. Use synonyms or related terms\n"
            f"2. Rephrase the question in different ways\n"
            f"3. Include related concepts or broader/narrower terms\n"
            f"4. Keep the same search intent and language\n"
            f"5. Avoid introducing topics not present in the original query\n\n"
            f"Return ONLY the alternative queries, one per line, without numbering or explanation."
        )

        result = await generate_chat_completion(
            request,
            form_data={
                "model": resolved_model_id,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": 0.7,
                "max_tokens": 500,
                "stream": False,
            },
            user=user,
            bypass_filter=True,
        )

        if hasattr(result, "body"):
            import orjson

            body = orjson.loads(result.body)
        elif isinstance(result, dict):
            body = result
        else:
            return []

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return []

        expanded: list[str] = []
        query_lower = query.lower()
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            line = _RE_BRACKET_NUM.sub("", line)
            line = _RE_DOT_NUM.sub("", line)
            line = line.strip()
            if not line or line.lower() == query_lower:
                continue
            if line not in expanded:
                expanded.append(line)

        return expanded[:max_expansions]

    except Exception as e:
        log.warning(f"Query expansion failed: {e}")
        return []
