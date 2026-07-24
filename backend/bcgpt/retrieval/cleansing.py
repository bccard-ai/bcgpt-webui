"""LLM-based text cleansing for document ingestion.

Primarily used for Korean-language documents that need normalization
before embedding.
"""

from __future__ import annotations

import logging

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

FILE_CLEANSE_PROMPT = """당신은 문서 텍스트 정제 전문가입니다. 아래 텍스트를 읽고 다음 작업을 수행하세요:

1. 불필요한 공백, 특수문자, 반복 문자 제거
2. 문단 구조 정리 (논리적 흐름 유지)
3. 핵심 내용은 모두 보존 (요약하지 않음)
4. 표 형태의 데이터는 마크다운 테이블로 정리
5. 출력은 정제된 텍스트만 (설명 없이)

원본 텍스트:
---
{text}
---

정제된 텍스트:"""


async def cleanse_text_with_llm(
    request,
    text: str,
    user,
) -> str:
    """Use an LLM to cleanse / normalise *text* (typically Korean documents).

    Falls back to returning the original text on any failure.
    """
    if not text or not text.strip():
        return text

    from bcgpt.utils.task import resolve_task_model

    task_model_id = resolve_task_model(request)
    if not task_model_id:
        log.warning("No model available for text cleansing, skipping")
        return text

    max_chars = 50000
    truncated = text[:max_chars]
    if len(text) > max_chars:
        log.warning(
            "Text truncated from %d to %d chars for cleansing", len(text), max_chars
        )
        log.warning(
            "Text truncated from %d to %d chars for cleansing", len(text), max_chars
        )

    prompt = FILE_CLEANSE_PROMPT.format(text=truncated)

    try:
        from bcgpt.utils import generate_chat_completion

        result = await generate_chat_completion(
            request,
            form_data={
                "model": task_model_id,
                "messages": [{"role": "user", "content": prompt}],
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
            return text

        cleansed = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        return cleansed.strip() if cleansed else text

    except Exception as exc:
        log.warning("LLM text cleansing failed, using raw text: %s", exc)
        return text
