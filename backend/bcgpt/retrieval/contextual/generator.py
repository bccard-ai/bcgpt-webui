import logging
import re
import time

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_HANGUL_RE = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]")


def _contains_korean(text: str) -> bool:
    return bool(_HANGUL_RE.search(text))


_CONTEXTUAL_SYSTEM = (
    "Please give a short succinct context to situate this chunk within the overall "
    "document for the purposes of improving search retrieval of the chunk. "
    "Answer only with the short succinct context to situate the chunk."
)

_CONTEXTUAL_SYSTEM_KR = (
    "전체 문서 내에서 이 청크의 위치를 파악할 수 있는 짧고 간결한 문맥을 제공해 주세요. "
    "검색 시 이 청크의 검색 정확도를 높이기 위한 목적입니다. "
    "오직 그 짧고 간결한 문맥만으로 답변하세요."
)

_MAX_CONTEXT_LEN = 300


def _sanitize_context(text: str) -> str:
    text = text.strip()
    if len(text) > _MAX_CONTEXT_LEN:
        text = text[:_MAX_CONTEXT_LEN].strip()
    return text


async def generate_chunk_context(
    chunk_content: str,
    full_document: str,
    request,
    user,
    model_id: str | None = None,
) -> str:
    try:
        from bcgpt.utils.task import resolve_task_model

        contextual_model = getattr(
            request.app.state.config, "RAG_CONTEXTUAL_RETRIEVAL_MODEL", ""
        )
        resolved_model_id = resolve_task_model(
            request,
            model_id,
            specific_model=contextual_model,
        )
        if not resolved_model_id:
            log.warning("Contextual retrieval: no available model")
            return ""

        from bcgpt.utils import generate_chat_completion

        is_korean = _contains_korean(full_document) or _contains_korean(chunk_content)
        system_prompt = _CONTEXTUAL_SYSTEM_KR if is_korean else _CONTEXTUAL_SYSTEM

        max_tokens = getattr(
            request.app.state.config,
            "RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS",
            200,
        )

        user_prompt = f"<document>\n{full_document}\n</document>\n\n<chunk>\n{chunk_content}\n</chunk>"

        result = await generate_chat_completion(
            request,
            form_data={
                "model": resolved_model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
                "max_tokens": max_tokens,
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
            return ""

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return ""

        return _sanitize_context(content)

    except Exception as e:
        log.warning(f"Contextual retrieval: chunk context generation failed: {e}")
        return ""


async def enrich_chunks_with_context(
    chunks: list[str],
    full_document: str,
    request,
    user,
) -> list[str]:
    if not chunks:
        return chunks

    batch_size = getattr(
        request.app.state.config,
        "RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE",
        10,
    )

    enriched: list[str] = []
    total_tokens = 0
    start = time.time()

    for i, chunk in enumerate(chunks):
        try:
            context = await generate_chunk_context(
                chunk_content=chunk,
                full_document=full_document,
                request=request,
                user=user,
            )
            if context:
                enriched.append(f"{context}\n{chunk}")
                total_tokens += len(context.split())
            else:
                enriched.append(chunk)
        except Exception as e:
            log.warning(
                f"Contextual retrieval: enriching chunk {i}/{len(chunks)} failed: {e}"
            )
            enriched.append(chunk)

        if (i + 1) % batch_size == 0:
            log.debug(
                f"Contextual retrieval: processed {i + 1}/{len(chunks)} chunks "
                f"({time.time() - start:.1f}s)"
            )

    elapsed = time.time() - start
    log.info(
        f"Contextual retrieval: enriched {len(enriched)} chunks "
        f"in {elapsed:.1f}s, ~{total_tokens} context tokens"
    )

    return enriched
