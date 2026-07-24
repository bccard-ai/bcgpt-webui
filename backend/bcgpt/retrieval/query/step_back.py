import logging
import re

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_RE_KOREAN_PARTICLES = re.compile(r"(얼마|몇|무슨|무엇|어디|언제|누구|어떻게|왜|어떤)")
_RE_ENGLISH_STARTERS = re.compile(
    r"\b(what|when|where|why|who|how|which|how\s+much|how\s+many|how\s+old)\b",
    re.IGNORECASE,
)
_RE_SPECIFIC_NUMBERS = re.compile(
    r"\b20\d{2}\b|\b\d+[\.,]?\d*\s*(원|달러|달|만|억|천|백|십|km|m|개|명|건)\b"
)
_RE_HANGUL = re.compile(r"[가-힣]")
_RE_DOT_NUM = re.compile(r"^\d+\.\s*")


def should_step_back(query: str) -> bool:
    words = query.split()
    if len(words) <= 2:
        return False
    if _RE_KOREAN_PARTICLES.search(query):
        return True
    if _RE_ENGLISH_STARTERS.search(query):
        return True
    if _RE_SPECIFIC_NUMBERS.search(query):
        return True
    return False


def _is_korean(text: str) -> bool:
    hangul_count = len(_RE_HANGUL.findall(text))
    return hangul_count > len(text.replace(" ", "")) * 0.25


async def generate_step_back_queries(
    query: str,
    request,
    user,
    model_id: str | None = None,
) -> list[str]:
    try:
        if not should_step_back(query):
            return []

        from bcgpt.utils.task import resolve_task_model

        resolved_model_id = resolve_task_model(request, model_id)
        if not resolved_model_id:
            log.warning("Step-back: no available model")
            return []

        models = request.app.state.MODELS

        from bcgpt.utils import generate_chat_completion

        if _is_korean(query):
            user_prompt = (
                "질문 분석 전문가입니다. 구체적인 질문을 더 넓은 배경 지식을 검색할 수 있는 "
                "추상적인 질문으로 변환하세요.\n\n"
                f"원본 질문: {query}\n\n"
                "2개의 후퇴 질문을 생성하세요 (한 줄에 하나, 번호 없이):"
            )
        else:
            user_prompt = (
                "You are an expert at query analysis. Your role is to transform specific "
                "questions into broader, more abstract versions that would help retrieve "
                "wider background context.\n\n"
                f"Original question: {query}\n\n"
                "Generate 2 step-back questions (one per line, no numbering):"
            )

        result = await generate_chat_completion(
            request,
            form_data={
                "model": resolved_model_id,
                "messages": [{"role": "user", "content": user_prompt}],
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

        queries: list[str] = []
        query_lower = query.lower()
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            line = _RE_DOT_NUM.sub("", line)
            line = line.strip()
            if not line or line.lower() == query_lower:
                continue
            if line not in queries:
                queries.append(line)

        return queries[:2]

    except Exception as e:
        log.warning(f"Step-back generation failed: {e}")
        return []
