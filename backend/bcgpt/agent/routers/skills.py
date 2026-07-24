"""Skill management endpoints (CRUD + YAML/JSON import/export + flags).

Skills are persisted in the ``skill`` table (see bcgpt.models.skills). Admins
curate the global catalog; users register their own (per-user rows). The CRUD
surface is contract-stable.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.agent.definitions import (
    SkillDefinition,
    export_skill,
    import_skill,
)
from bcgpt.models import SkillForm, SkillMeta, Skills
from bcgpt.utils.auth import get_admin_user, get_verified_user

router = APIRouter()


class SkillFlags(BaseModel):
    is_active: bool | None = None
    is_global: bool | None = None


def _form_from_skill_def(skill: SkillDefinition, skill_id: str) -> SkillForm:
    return SkillForm(
        id=skill_id,
        name=skill.name,
        description=skill.description,
        content=skill.prompt_template,
        meta=SkillMeta(
            description=skill.description,
            resources=skill.resources,
            tools=skill.tools,
            required_capabilities=skill.required_capabilities,
        ),
    )


def _model_to_record(m) -> dict:
    return m.model_dump()


@router.get("/")
async def list_skills(request: Request, user=Depends(get_verified_user)):
    # Catalog = all global skills + this user's own; non-admins see global only.
    if user.role == "admin":
        rows = Skills.get_skills()
    else:
        rows = [s for s in Skills.get_skills() if s.is_global or s.user_id == user.id]
    return {"skills": [_model_to_record(s) for s in rows]}


@router.post("/")
async def create_skill(form: SkillForm, request: Request, user=Depends(get_admin_user)):
    created = Skills.insert_new_skill(user_id=user.id, form_data=form)
    if created is None:
        raise HTTPException(status_code=400, detail="Skill create failed")
    return _model_to_record(created)


@router.get("/{skill_id}")
async def get_skill(skill_id: str, request: Request, user=Depends(get_verified_user)):
    skill = Skills.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _model_to_record(skill)


@router.put("/{skill_id}")
async def update_skill(
    skill_id: str, form: SkillForm, request: Request, user=Depends(get_admin_user)
):
    if Skills.get_skill_by_id(skill_id) is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    updated = Skills.update_skill_by_id(
        skill_id,
        {
            "name": form.name,
            "description": form.description,
            "content": form.content,
            "meta": form.meta.model_dump(),
        },
    )
    if updated is None:
        raise HTTPException(status_code=400, detail="Skill update failed")
    return _model_to_record(updated)


@router.patch("/{skill_id}/flags")
async def set_skill_flags(
    skill_id: str,
    flags: SkillFlags,
    request: Request,
    user=Depends(get_admin_user),
):
    if Skills.get_skill_by_id(skill_id) is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    patch = {k: v for k, v in flags.model_dump().items() if v is not None}
    updated = Skills.update_skill_by_id(skill_id, patch)
    if updated is None:
        raise HTTPException(status_code=400, detail="Skill flag update failed")
    return _model_to_record(updated)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, request: Request, user=Depends(get_admin_user)):
    skill = Skills.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.is_builtin:
        # Builtins are disabled, never deleted.
        Skills.update_skill_by_id(skill_id, {"is_active": False, "is_global": False})
        raise HTTPException(
            status_code=403, detail="Built-in skill disabled, not deleted"
        )
    Skills.delete_skill_by_id(skill_id)
    return {"deleted": skill_id}


class ImportForm(BaseModel):
    content: str
    format: str = "md"  # "md" | "json"


@router.post("/import")
async def import_skill_endpoint(
    form: ImportForm, request: Request, user=Depends(get_admin_user)
):
    from bcgpt.utils.gh_import import validate_skill_content

    try:
        skill_def, _meta = validate_skill_content(form.content, fmt=form.format)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Import failed: {e}")
    skill_def.id = str(uuid.uuid4())
    created = Skills.insert_new_skill(
        user_id=user.id, form_data=_form_from_skill_def(skill_def, skill_def.id)
    )
    if created is None:
        raise HTTPException(status_code=400, detail="Skill create failed")
    return _model_to_record(created)


@router.post("/import-url")
async def import_skill_from_url(
    request: Request, url: str, user=Depends(get_admin_user)
):
    from bcgpt.utils.gh_import import fetch_skill_from_url, validate_skill_content

    try:
        content, source_url = fetch_skill_from_url(url)
        skill_def, _meta = validate_skill_content(content, fmt="md")
    except ValueError as e:  # host / size / format policy errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Import failed: {e}")
    skill_def.id = str(uuid.uuid4())
    form = _form_from_skill_def(skill_def, skill_def.id)
    form.meta.source_url = source_url
    created = Skills.insert_new_skill(user_id=user.id, form_data=form)
    if created is None:
        raise HTTPException(status_code=400, detail="Skill create failed")
    return _model_to_record(created)


@router.get("/{skill_id}/export")
async def export_skill_endpoint(
    skill_id: str,
    request: Request,
    format: str = "md",
    user=Depends(get_verified_user),
):
    record = Skills.get_skill_by_id(skill_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill = SkillDefinition(
        name=record.name,
        description=record.description,
        id=record.id,
        prompt_template=record.content,
        tools=list(record.meta.tools) if record.meta else [],
        required_capabilities=(
            list(record.meta.required_capabilities) if record.meta else []
        ),
        resources=dict(record.meta.resources) if record.meta else {},
    )
    return {"format": format, "content": export_skill(skill, fmt=format)}
