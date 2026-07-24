import logging
import re

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_RE_CODE_FENCE = re.compile(r"^```[\s\S]*?```\s*", re.DOTALL)
_RE_ANSWER_PREFIX = re.compile(r"^Answer\s+passage:\s*", re.IGNORECASE)
_RE_SENTENCE_BOUNDARY = re.compile(r"[.!?]")


def _sanitize_hyde(text: str) -> str | None:
    text = text.strip()
    text = _RE_CODE_FENCE.sub("", text).strip()
    text = _RE_ANSWER_PREFIX.sub("", text).strip()
    if len(text) < 20:
        return None
    if len(text) > 600:
        matches = list(_RE_SENTENCE_BOUNDARY.finditer(text[:600]))
        if matches:
            text = text[: matches[-1].end()].strip()
        else:
            text = text[:600].strip()
    if len(text) < 20:
        return None
    return text


async def generate_hypothetical_document(
    query: str,
    request,
    user,
    model_id: str | None = None,
) -> str | None:
    try:
        from bcgpt.utils.task import resolve_task_model

        hyde_model = getattr(request.app.state.config, "RAG_HYDE_MODEL", "")
        resolved_model_id = resolve_task_model(
            request,
            model_id,
            specific_model=hyde_model,
        )
        if not resolved_model_id:
            log.warning("HyDE: no available model")
            return None

        models = request.app.state.MODELS

        from bcgpt.utils import generate_chat_completion

        system_prompt = (
            "You write a short, factual passage that would directly answer the user query, "
            "as if excerpted from an authoritative document. Write 2-4 sentences in the same "
            "language as the query. State concrete facts and likely terminology. Do NOT add "
            "caveats, do NOT say you are unsure, do NOT mention that this is hypothetical."
        )
        user_prompt = f"Query: {query}\nAnswer passage:"

        result = await generate_chat_completion(
            request,
            form_data={
                "model": resolved_model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 256,
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
            return None

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None

        return _sanitize_hyde(content)

    except Exception as e:
        log.warning(f"HyDE generation failed: {e}")
        return None
