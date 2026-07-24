"""Agent autonomy, workflow management, tools, and quality endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt import config
from bcgpt.agent.capabilities import model_capability_enabled
from bcgpt.agent.config import resolve_autonomy_level
from bcgpt.agent.types import AgentAutonomyLevel
from bcgpt.agent.tool_loop.tools import BUILTIN_TOOLS
from bcgpt.agent.workflow import (
    DynamicWorkflowGenerator,
    ExecutionContext,
    WorkflowEngine,
    WorkflowState,
    WorkflowValidationError,
    deserialize_workflow,
    serialize_workflow,
    validate_workflow,
)
from bcgpt.agent.workflow.nodes import create_default_registry
from bcgpt.compliance.hitl import ApprovalGates
from bcgpt.models.models import ModelForm, Models
from bcgpt.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)
router = APIRouter()

# One shared, stateless registry for all workflow executions.
_REGISTRY = create_default_registry()
_GENERATOR = DynamicWorkflowGenerator()


# --- helpers ----------------------------------------------------------------


def _model_meta(model) -> dict:
    meta = getattr(model, "meta", None)
    if meta is None:
        return {}
    return meta.model_dump() if hasattr(meta, "model_dump") else dict(meta)


def build_agent_config(model) -> dict:
    """Derive a workflow generator config from a persisted model."""
    meta = _model_meta(model)
    knowledge = meta.get("knowledge") or []
    collection_ids = [k.get("id") if isinstance(k, dict) else k for k in knowledge if k]
    return {
        "model_id": getattr(model, "id", None),
        "rag_enabled": bool(collection_ids),
        "collection_ids": collection_ids,
        "web_search_enabled": model_capability_enabled(model, "web_search"),
        "hybrid_search": model_capability_enabled(model, "hybrid_search"),
    }


def _load_workflow_nodes(model):
    """Custom workflow from meta if present & valid, else generated default."""
    meta = _model_meta(model)
    custom = meta.get("workflow")
    if custom:
        nodes = deserialize_workflow(custom)
        validate_workflow(nodes)
        return nodes, "custom"
    level = resolve_autonomy_level(model)
    nodes = _GENERATOR.generate(level, build_agent_config(model))
    return nodes, "generated"


# --- autonomy ---------------------------------------------------------------


@router.get("/autonomy-levels")
async def get_autonomy_levels(user=Depends(get_verified_user)):
    descriptions = {
        "suggest": "Fast suggestion — no tools, no pre-search.",
        "assistant": "Default — pre-search (RAG + Web) → merge → LLM → response.",
        "operator": "Autonomous ReAct tool loop (explicit opt-in).",
    }
    return {
        "levels": [
            {"value": lvl.value, "description": descriptions[lvl.value]}
            for lvl in AgentAutonomyLevel
        ]
    }


@router.get("/tools")
async def list_tools(user=Depends(get_verified_user)):
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in BUILTIN_TOOLS.values()
        ]
    }


# --- workflow management ----------------------------------------------------


class WorkflowForm(BaseModel):
    workflow: list


class WorkflowTestForm(BaseModel):
    input: str
    workflow: Optional[list] = None  # optional override to test before saving


def _get_model_or_404(model_id: str):
    model = Models.get_model_by_id(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


def _require_owner_or_admin(model, user):
    if user.role != "admin" and getattr(model, "user_id", None) != user.id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this agent")


@router.get("/{model_id}/workflow")
async def get_agent_workflow(model_id: str, user=Depends(get_verified_user)):
    model = _get_model_or_404(model_id)
    try:
        nodes, source = _load_workflow_nodes(model)
    except WorkflowValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "model_id": model_id,
        "autonomy_level": resolve_autonomy_level(model).value,
        "source": source,
        "workflow": serialize_workflow(nodes),
    }


@router.put("/{model_id}/workflow")
async def update_agent_workflow(
    model_id: str, form: WorkflowForm, user=Depends(get_verified_user)
):
    model = _get_model_or_404(model_id)
    _require_owner_or_admin(model, user)

    try:
        nodes = deserialize_workflow(form.workflow)
        validate_workflow(nodes)
    except WorkflowValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    meta = _model_meta(model)
    meta["workflow"] = serialize_workflow(nodes)
    update = ModelForm(
        id=model.id,
        base_model_id=model.base_model_id,
        name=model.name,
        meta=meta,
        params=(
            model.params.model_dump()
            if hasattr(model.params, "model_dump")
            else model.params
        ),
        access_control=model.access_control,
        is_active=model.is_active,
    )
    saved = Models.update_model_by_id(model_id, update)
    if saved is None:
        raise HTTPException(status_code=500, detail="Failed to save workflow")
    return {"model_id": model_id, "workflow": meta["workflow"]}


@router.post("/{model_id}/workflow/test")
async def test_agent_workflow(
    model_id: str,
    form: WorkflowTestForm,
    request: Request,
    user=Depends(get_verified_user),
):
    model = _get_model_or_404(model_id)

    try:
        if form.workflow:
            nodes = deserialize_workflow(form.workflow)
            validate_workflow(nodes)
        else:
            nodes, _ = _load_workflow_nodes(model)
    except WorkflowValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    engine = WorkflowEngine(_REGISTRY)
    state = WorkflowState(
        user_input=form.input,
        messages=[{"role": "user", "content": form.input}],
    )
    approval_gate = (
        ApprovalGates if bool(config.COMPLIANCE_HITL_ENABLED.value) else None
    )
    context = ExecutionContext(
        request=request,
        user=user,
        model=model,
        model_id=model_id,
        approval_gate=approval_gate,
    )
    try:
        state = await engine.execute(nodes, state, context)
    except Exception as e:  # noqa: BLE001
        log.exception("workflow test failed")
        raise HTTPException(status_code=500, detail=f"Workflow error: {e}")

    return {
        "model_id": model_id,
        "final_response": state.final_response,
        "status": state.status,
        "state": state.to_dict(),
    }


# --- quality ----------------------------------------------------------------


class QualityForm(BaseModel):
    response: str
    query: str = ""
    sources: list = []
    model_id: Optional[str] = None


@router.post("/quality/evaluate")
async def evaluate_quality(
    form: QualityForm, request: Request, user=Depends(get_verified_user)
):
    from bcgpt.agent.config import (
        QUALITY_CLAIM_DECOMPOSITION_ENABLED,
        QUALITY_CITATION_AUDIT_ENABLED,
        QUALITY_DOC_STRUCTURE_SCORE_ENABLED,
        QUALITY_DOC_GRADING_ENABLED,
        QUALITY_GROUNDING_ENABLED,
        QUALITY_DEFAULT_MODEL,
        QUALITY_CLAIM_MODEL,
        QUALITY_GROUNDING_MODEL,
        QUALITY_DOC_GRADING_MODEL,
        QUALITY_ENTAILMENT_MODEL,
        LETTUCE_DETECT_ENABLED,
        LETTUCE_DETECT_THRESHOLD,
    )
    from bcgpt.agent.quality import QualityPipeline

    model_id = form.model_id
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    default_model = (
        str(QUALITY_DEFAULT_MODEL.value) if QUALITY_DEFAULT_MODEL.value else model_id
    )

    pipeline = QualityPipeline(
        request,
        user,
        model_id,
        default_model=default_model,
        claim_decomposition=bool(QUALITY_CLAIM_DECOMPOSITION_ENABLED.value),
        grounding=bool(QUALITY_GROUNDING_ENABLED.value),
        doc_grading=bool(QUALITY_DOC_GRADING_ENABLED.value),
        citation_audit=bool(QUALITY_CITATION_AUDIT_ENABLED.value),
        doc_structure_score=bool(QUALITY_DOC_STRUCTURE_SCORE_ENABLED.value),
        lettuce_detect=bool(LETTUCE_DETECT_ENABLED.value),
        lettuce_detect_threshold=float(LETTUCE_DETECT_THRESHOLD.value),
        claim_model=str(QUALITY_CLAIM_MODEL.value) if QUALITY_CLAIM_MODEL.value else "",
        grounding_model=(
            str(QUALITY_GROUNDING_MODEL.value) if QUALITY_GROUNDING_MODEL.value else ""
        ),
        doc_grading_model=(
            str(QUALITY_DOC_GRADING_MODEL.value)
            if QUALITY_DOC_GRADING_MODEL.value
            else ""
        ),
        entailment_model=(
            str(QUALITY_ENTAILMENT_MODEL.value)
            if QUALITY_ENTAILMENT_MODEL.value
            else ""
        ),
    )
    report = await pipeline.evaluate(form.response, form.sources, form.query)
    return report.to_dict()


# --- agent configuration ----------------------------------------------------


class AgentConfigUpdateForm(BaseModel):
    default_autonomy_level: Optional[str] = None
    operator_max_tool_iterations: Optional[int] = None
    quality_pipeline_enabled: Optional[bool] = None
    quality_sampling_rate: Optional[float] = None
    workflow_engine_enabled: Optional[bool] = None
    workflow_default_timeout: Optional[int] = None
    workflow_node_timeout: Optional[int] = None
    multi_agent_enabled: Optional[bool] = None
    multi_agent_max_parallel: Optional[int] = None
    multi_agent_debate_rounds: Optional[int] = None
    multi_agent_consensus_threshold: Optional[float] = None
    quality_claim_decomposition_enabled: Optional[bool] = None
    quality_grounding_enabled: Optional[bool] = None
    quality_doc_grading_enabled: Optional[bool] = None
    quality_default_model: Optional[str] = None
    quality_claim_model: Optional[str] = None
    quality_grounding_model: Optional[str] = None
    quality_doc_grading_model: Optional[str] = None
    quality_entailment_model: Optional[str] = None
    lettuce_detect_enabled: Optional[bool] = None
    lettuce_detect_threshold: Optional[float] = None


@router.get("/config")
async def get_agent_config(request: Request, user=Depends(get_admin_user)):
    return {
        "status": True,
        "agent_system": {
            "default_autonomy_level": request.app.state.config.AGENT_DEFAULT_AUTONOMY_LEVEL,
            "operator_max_tool_iterations": request.app.state.config.AGENT_OPERATOR_MAX_TOOL_ITERATIONS,
            "quality_pipeline_enabled": request.app.state.config.AGENT_QUALITY_PIPELINE_ENABLED,
            "quality_sampling_rate": request.app.state.config.AGENT_QUALITY_SAMPLING_RATE,
        },
        "workflow_engine": {
            "enabled": request.app.state.config.WORKFLOW_ENGINE_ENABLED,
            "default_timeout": request.app.state.config.WORKFLOW_DEFAULT_TIMEOUT,
            "node_timeout": request.app.state.config.WORKFLOW_NODE_TIMEOUT,
        },
        "multi_agent": {
            "enabled": request.app.state.config.MULTI_AGENT_ENABLED,
            "max_parallel": request.app.state.config.MULTI_AGENT_MAX_PARALLEL,
            "debate_rounds": request.app.state.config.MULTI_AGENT_DEBATE_ROUNDS,
            "consensus_threshold": request.app.state.config.MULTI_AGENT_CONSENSUS_THRESHOLD,
        },
        "quality": {
            "default_model": request.app.state.config.QUALITY_DEFAULT_MODEL,
            "claim_decomposition_enabled": request.app.state.config.QUALITY_CLAIM_DECOMPOSITION_ENABLED,
            "grounding_enabled": request.app.state.config.QUALITY_GROUNDING_ENABLED,
            "doc_grading_enabled": request.app.state.config.QUALITY_DOC_GRADING_ENABLED,
            "claim_model": request.app.state.config.QUALITY_CLAIM_MODEL,
            "grounding_model": request.app.state.config.QUALITY_GROUNDING_MODEL,
            "doc_grading_model": request.app.state.config.QUALITY_DOC_GRADING_MODEL,
            "entailment_model": request.app.state.config.QUALITY_ENTAILMENT_MODEL,
            "lettuce_detect_enabled": request.app.state.config.LETTUCE_DETECT_ENABLED,
            "lettuce_detect_threshold": request.app.state.config.LETTUCE_DETECT_THRESHOLD,
        },
    }


@router.post("/config/update")
async def update_agent_config(
    request: Request, form_data: AgentConfigUpdateForm, user=Depends(get_admin_user)
):
    cfg = request.app.state.config

    if form_data.default_autonomy_level is not None:
        cfg.AGENT_DEFAULT_AUTONOMY_LEVEL = form_data.default_autonomy_level
    if form_data.operator_max_tool_iterations is not None:
        cfg.AGENT_OPERATOR_MAX_TOOL_ITERATIONS = form_data.operator_max_tool_iterations
    if form_data.quality_pipeline_enabled is not None:
        cfg.AGENT_QUALITY_PIPELINE_ENABLED = form_data.quality_pipeline_enabled
    if form_data.quality_sampling_rate is not None:
        cfg.AGENT_QUALITY_SAMPLING_RATE = form_data.quality_sampling_rate

    if form_data.workflow_engine_enabled is not None:
        cfg.WORKFLOW_ENGINE_ENABLED = form_data.workflow_engine_enabled
    if form_data.workflow_default_timeout is not None:
        cfg.WORKFLOW_DEFAULT_TIMEOUT = form_data.workflow_default_timeout
    if form_data.workflow_node_timeout is not None:
        cfg.WORKFLOW_NODE_TIMEOUT = form_data.workflow_node_timeout

    if form_data.multi_agent_enabled is not None:
        cfg.MULTI_AGENT_ENABLED = form_data.multi_agent_enabled
    if form_data.multi_agent_max_parallel is not None:
        cfg.MULTI_AGENT_MAX_PARALLEL = form_data.multi_agent_max_parallel
    if form_data.multi_agent_debate_rounds is not None:
        cfg.MULTI_AGENT_DEBATE_ROUNDS = form_data.multi_agent_debate_rounds
    if form_data.multi_agent_consensus_threshold is not None:
        cfg.MULTI_AGENT_CONSENSUS_THRESHOLD = form_data.multi_agent_consensus_threshold

    if form_data.quality_claim_decomposition_enabled is not None:
        cfg.QUALITY_CLAIM_DECOMPOSITION_ENABLED = (
            form_data.quality_claim_decomposition_enabled
        )
    if form_data.quality_grounding_enabled is not None:
        cfg.QUALITY_GROUNDING_ENABLED = form_data.quality_grounding_enabled
    if form_data.quality_doc_grading_enabled is not None:
        cfg.QUALITY_DOC_GRADING_ENABLED = form_data.quality_doc_grading_enabled
    if form_data.quality_default_model is not None:
        cfg.QUALITY_DEFAULT_MODEL = form_data.quality_default_model
    if form_data.quality_claim_model is not None:
        cfg.QUALITY_CLAIM_MODEL = form_data.quality_claim_model
    if form_data.quality_grounding_model is not None:
        cfg.QUALITY_GROUNDING_MODEL = form_data.quality_grounding_model
    if form_data.quality_doc_grading_model is not None:
        cfg.QUALITY_DOC_GRADING_MODEL = form_data.quality_doc_grading_model
    if form_data.quality_entailment_model is not None:
        cfg.QUALITY_ENTAILMENT_MODEL = form_data.quality_entailment_model

    if form_data.lettuce_detect_enabled is not None:
        cfg.LETTUCE_DETECT_ENABLED = form_data.lettuce_detect_enabled
    if form_data.lettuce_detect_threshold is not None:
        cfg.LETTUCE_DETECT_THRESHOLD = form_data.lettuce_detect_threshold

    return {"status": True}
