import json
import logging
import re

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_HANGUL_RE = re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]+")

_STOCK_CODE_RE = re.compile(r"^\d{6}$")
_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


def _is_korean(text: str) -> bool:
    return bool(_HANGUL_RE.search(text))


def _guess_entity_type(name: str) -> str:
    """Lightweight type label for a co-occurrence entity name."""
    if _STOCK_CODE_RE.match(name):
        return "STOCK_CODE"
    if _TICKER_RE.match(name):
        return "TICKER"
    return "ENTITY"


def extract_cooccurrence_entities(
    text: str, max_entities: int | None = None
) -> list[dict]:
    """Deterministic (no-LLM) named-entity extraction for the co-occurrence graph.

    Reuses the regex financial-entity extractor from query hardening (3.1) so the
    ingest-side and query-side node names align. Returns
    ``[{"entity", "type", "description"}, ...]``. Empty on no entities.
    """
    if not text:
        return []
    try:
        from bcgpt.utils.query_entity_guard import extract_query_entities

        names = extract_query_entities(text)
    except Exception:
        names = []
    if max_entities and max_entities > 0:
        names = names[:max_entities]
    return [
        {"entity": n, "type": _guess_entity_type(n), "description": ""} for n in names
    ]


async def extract_entities(
    text: str,
    request,
    user,
    model_id: str | None = None,
) -> list[dict]:
    try:
        from bcgpt.utils.task import resolve_task_model

        graph_model = getattr(
            request.app.state.config, "RAG_GRAPH_ENTITY_EXTRACTION_MODEL", ""
        )
        resolved_model_id = resolve_task_model(
            request, model_id, specific_model=graph_model
        )
        if not resolved_model_id:
            log.warning("GraphRAG entity extraction: no available model")
            return []

        from bcgpt.utils import generate_chat_completion

        lang_hint = "Korean" if _is_korean(text) else "English"

        system_prompt = (
            f"You are a precise named-entity extractor. Given a {lang_hint} text, "
            f"extract all named entities as a JSON array. Each element must be an object "
            f'with keys "entity" (the entity name), "type" (e.g. PERSON, ORGANIZATION, '
            f'LOCATION, TECHNOLOGY, CONCEPT, EVENT, PRODUCT, DATE), and "description" '
            f"(a brief 5-15 word description of the entity in context). "
            f"Respond with ONLY the JSON array, no markdown fences."
        )
        user_prompt = f"Text:\n{text}"

        result = await generate_chat_completion(
            request,
            form_data={
                "model": resolved_model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1024,
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

        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())

        entities = json.loads(content)
        if not isinstance(entities, list):
            return []

        valid = []
        for e in entities:
            if isinstance(e, dict) and "entity" in e and "type" in e:
                valid.append(
                    {
                        "entity": str(e["entity"]),
                        "type": str(e["type"]),
                        "description": str(e.get("description", "")),
                    }
                )
        return valid

    except Exception as e:
        log.warning(f"GraphRAG entity extraction failed: {e}")
        return []


async def extract_relations(
    text: str,
    entities: list[dict],
    request,
    user,
    model_id: str | None = None,
) -> list[dict]:
    if len(entities) < 2:
        return []

    try:
        from bcgpt.utils.task import resolve_task_model

        graph_model = getattr(
            request.app.state.config, "RAG_GRAPH_ENTITY_EXTRACTION_MODEL", ""
        )
        resolved_model_id = resolve_task_model(
            request, model_id, specific_model=graph_model
        )
        if not resolved_model_id:
            log.warning("GraphRAG relation extraction: no available model")
            return []

        from bcgpt.utils import generate_chat_completion

        entity_names = [e["entity"] for e in entities]

        system_prompt = (
            "You are a precise relation extractor. Given a text and a list of entities, "
            "identify relationships between pairs of entities mentioned in the text. "
            'Return a JSON array where each element has "source" (entity name), '
            '"target" (entity name), "relation" (short relation label), and '
            '"weight" (float 0.0-1.0 indicating strength). '
            "Respond with ONLY the JSON array, no markdown fences."
        )
        user_prompt = (
            f"Text:\n{text}\n\nEntities: {json.dumps(entity_names, ensure_ascii=False)}"
        )

        result = await generate_chat_completion(
            request,
            form_data={
                "model": resolved_model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 512,
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

        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())

        relations = json.loads(content)
        if not isinstance(relations, list):
            return []

        entity_set = set(entity_names)
        valid = []
        for r in relations:
            if (
                isinstance(r, dict)
                and "source" in r
                and "target" in r
                and r["source"] in entity_set
                and r["target"] in entity_set
            ):
                weight = float(r.get("weight", 0.5))
                weight = max(0.0, min(1.0, weight))
                valid.append(
                    {
                        "source": str(r["source"]),
                        "target": str(r["target"]),
                        "relation": str(r.get("relation", "related_to")),
                        "weight": weight,
                    }
                )
        return valid

    except Exception as e:
        log.warning(f"GraphRAG relation extraction failed: {e}")
        return []
