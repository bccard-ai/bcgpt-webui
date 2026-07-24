"""Resolution helpers for the extensions layer — skills now, MCP later.

``resolve_effective_skills`` merges the admin global catalog with per-user
enabled skills to produce the active set for a single chat. Honors an optional
per-chat ``skill_ids`` selection (Task 9) that restricts the result to the
intersection.
"""

from __future__ import annotations

from typing import Any, Optional

from bcgpt.models import SkillModel, Skills


def _user_settings_dict(user: Any) -> dict:
    settings = getattr(user, "settings", None)
    if settings is None:
        return {}
    if hasattr(settings, "model_dump"):
        return settings.model_dump()
    if isinstance(settings, dict):
        return settings
    return {}


def resolve_effective_skills(
    user: Any, skill_ids: Optional[list[str]] = None
) -> list[SkillModel]:
    """Return the active skill set for a chat: admin-global ∪ user-enabled.

    If ``skill_ids`` is provided, restricts the result to those ids (per-chat
    selection) — still only ids that are otherwise effective for the user.
    """
    merged: dict[str, SkillModel] = {}

    for s in Skills.get_active_global_skills():
        merged[s.id] = s

    ui = _user_settings_dict(user).get("ui", {}) or {}
    for sid in (ui.get("skills") or {}).get("enabled") or []:
        s = Skills.get_skill_by_id(sid)
        if (
            s is not None
            and s.is_active
            and (s.is_global or s.user_id == getattr(user, "id", None))
        ):
            merged.setdefault(s.id, s)

    for s in Skills.get_skills_for_user(getattr(user, "id", "")):
        if s.is_active:
            merged.setdefault(s.id, s)

    if skill_ids is not None:
        wanted = set(skill_ids)
        return [s for s in merged.values() if s.id in wanted]
    return list(merged.values())


def resolve_effective_mcp_servers(
    user: Any, server_ids: Optional[list[str]] = None
) -> list[dict]:
    """Effective MCP servers: admin-catalog (enabled, allow-host pass)
    ∪ user-registered (allow-host pass). Empty when the feature flag is off.

    Server URLs are NEVER trusted from client form_data — only admin
    PersistentConfig + per-user settings, both gated by MCP_ALLOWED_HOSTS.
    """
    from bcgpt import config as cfg
    from bcgpt.mcpbridge.allowlist import is_host_allowed

    if not getattr(cfg.ENABLE_MCP_SERVERS, "value", False):
        return []
    allowed_hosts = list(getattr(cfg.MCP_ALLOWED_HOSTS, "value", []) or [])
    merged: dict[str, dict] = {}
    for s in getattr(cfg.MCP_SERVERS, "value", []) or []:
        if s.get("enabled") and is_host_allowed(s.get("url", ""), allowed_hosts):
            merged[s["id"]] = s
    ui = _user_settings_dict(user).get("ui", {}) or {}
    for s in ui.get("mcpServers") or []:
        if s.get("enabled") and is_host_allowed(s.get("url", ""), allowed_hosts):
            merged.setdefault(s["id"], s)
    rows = list(merged.values())
    if server_ids is not None:
        wanted = set(server_ids)
        rows = [r for r in rows if r.get("id") in wanted]
    return rows
