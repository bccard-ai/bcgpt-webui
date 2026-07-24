"""Allow-listed GitHub/raw import + SKILL.md validation for skills.

Security policy:
- Only fetch from ALLOWED_HOSTS (github.com / raw.githubusercontent.com / huggingface.co).
- Enforce MAX_BYTES on the response (Content-Length or bytes read).
- Validate frontmatter (name + description required).
- Reject any bundled resource whose path is under ``scripts/`` (no executable scripts).
"""

from __future__ import annotations

import re
import urllib.request
from typing import Tuple

from bcgpt.agent.definitions import SkillDefinition, import_skill
from bcgpt.agent.definitions.importer import parse_frontmatter

ALLOWED_HOSTS = (
    "https://github.com/",
    "https://raw.githubusercontent.com/",
    "https://huggingface.co/",
)
MAX_BYTES = 2_000_000
_TIMEOUT_SECONDS = 15

_SCRIPTS_PATH = re.compile(r"(^|/)scripts/+", re.IGNORECASE)


def fetch_skill_from_url(url: str) -> Tuple[str, str]:
    """Fetch raw text from an allow-listed URL. Raises ValueError on policy violation."""
    if not isinstance(url, str) or not url.startswith(ALLOWED_HOSTS):
        raise ValueError(
            "URL host not allowed. Permitted hosts: " + ", ".join(ALLOWED_HOSTS)
        )
    req = urllib.request.Request(url, headers={"User-Agent": "bcgpt-skill-import"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
        length = resp.headers.get("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise ValueError(f"Payload too large ({length} > {MAX_BYTES} bytes)")
        data = resp.read()
    if len(data) > MAX_BYTES:
        raise ValueError(f"Payload too large ({len(data)} > {MAX_BYTES} bytes)")
    return data.decode("utf-8", errors="replace"), url


def validate_skill_content(
    content: str, fmt: str = "md"
) -> Tuple[SkillDefinition, dict]:
    """Validate and parse SKILL.md content. Raises ValueError on policy violation."""
    import json

    # Inspect the RAW frontmatter/data first — SkillDefinition.from_dict silently
    # defaults a missing name to "skill", so we cannot detect absence from the
    # parsed dataclass fields.
    if fmt == "json" or isinstance(content, dict):
        data = content if isinstance(content, dict) else json.loads(content)
    else:
        data, _body = parse_frontmatter(content)

    if not (isinstance(data, dict) and data.get("name") and str(data["name"]).strip()):
        raise ValueError("Skill frontmatter must include a non-empty 'name'")
    if not (
        isinstance(data, dict)
        and data.get("description")
        and str(data["description"]).strip()
    ):
        raise ValueError("Skill frontmatter must include a non-empty 'description'")

    skill = import_skill(content, fmt=fmt)

    resources = data.get("resources") if isinstance(data, dict) else None
    if isinstance(resources, dict):
        for path in resources.keys():
            if _SCRIPTS_PATH.search(str(path)):
                raise ValueError(
                    "Executable scripts are not permitted in skills (rejected path: "
                    f"{path})"
                )
        skill.resources = {str(k): str(v) for k, v in resources.items()}
    # Reject any literal reference to a scripts/ path in the body.
    if _SCRIPTS_PATH.search(skill.prompt_template or ""):
        raise ValueError("Skill body references a forbidden 'scripts/' path")

    return skill, {"resources": skill.resources}
