"""Memory injection and extraction for the chat pipeline.

* ``build_memory_context`` fetches a user's top memories and formats them
  into an XML block suitable for injection into the system prompt.
* ``extract_and_store_memories`` asks a task model to pull durable facts
  from a completed conversation turn and persists them.
"""

import json
import loguru as log

from bcgpt.models.memories import Memories
from bcgpt.models.users import Users  # noqa: F401 (chained import side-effects)


async def build_memory_context(user, limit: int = 20) -> str:
    """Return an ``<user-memories>`` XML block or an empty string."""
    try:
        user_id = user.id if hasattr(user, "id") else str(user)
        memories = Memories.get_memories_by_user_id(user_id, limit=limit)
        if not memories:
            return ""
        lines = [f"- {m.content}" for m in memories if m.content]
        if not lines:
            return ""
        return (
            "<user-memories>\n"
            "The following are things you previously learned about this user. "
            "Use them to personalise your response but do not mention the list.\n"
            + "\n".join(lines)
            + "\n</user-memories>"
        )
    except Exception as exc:
        log.debug("Memory context build skipped: %s", exc)
        return ""


_EXTRACTION_PROMPT = """### Task:
Extract durable, reusable facts about the user from the conversation below.
Focus on preferences, instructions, identity details, and stable knowledge.
Ignore ephemeral questions, task-specific context, and one-off requests.

### Rules:
- Output a JSON array of objects with keys: content, category, importance.
- content: concise statement (max 200 chars).
- category: one of preference|fact|instruction.
- importance: float 0.0–1.0 (0.1 trivial, 0.5 moderate, 0.9 critical).
- If nothing worth remembering, output an empty array [].

### Conversation:
{conversation}

### Output (JSON array only):"""


async def extract_and_store_memories(
    request, user, messages: list[dict], *, model_id: str | None = None
) -> int:
    """Extract memories from a conversation and persist them. Returns count."""
    try:
        conversation_parts = []
        for msg in messages[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict)
                )
            if content:
                conversation_parts.append(f"{role}: {content}")

        if not conversation_parts:
            return 0

        from bcgpt.utils.chat import generate_chat_completion
        from bcgpt.utils.payload import convert_payload_openai_to_openai

        prompt = _EXTRACTION_PROMPT.format(
            conversation="\n".join(conversation_parts)
        )

        payload = {
            "model": model_id or request.app.state.config.TITLE_GENERATION_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "metadata": {"task": "memory_extraction"},
        }

        response = await generate_chat_completion(
            request, payload, user=user, bypass_filter=True
        )

        choices = response.get("choices", [])
        if not choices:
            return 0
        text = choices[0].get("message", {}).get("content", "").strip()
        if not text:
            return 0

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        extracted = json.loads(text)
        if not isinstance(extracted, list):
            return 0

        user_id = user.id if hasattr(user, "id") else str(user)
        count = 0
        for item in extracted[:5]:
            if not isinstance(item, dict) or not item.get("content"):
                continue
            Memories.insert_new_memory(
                user_id=user_id,
                content=item["content"],
                tier="long_term",
                importance=float(item.get("importance", 0.5)),
                category=item.get("category", "general"),
            )
            count += 1
        return count
    except Exception as exc:
        log.debug("Memory extraction skipped: %s", exc)
        return 0
