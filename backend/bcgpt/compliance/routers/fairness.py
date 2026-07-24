from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.compliance.models.fairness_test import AIFairnessTestForm, AIFairnessTests
from bcgpt.utils.auth import get_admin_user

router = APIRouter()


class FairnessStatusForm(BaseModel):
    status: str


class FairnessResultsForm(BaseModel):
    results: Optional[dict[str, object]] = None
    metrics_summary: Optional[dict[str, object]] = None
    threshold_passed: Optional[bool] = None


@router.post("")
async def create_fairness_test(
    request: Request,
    form_data: AIFairnessTestForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIFairnessTests.insert(form_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create fairness test")
    return result.model_dump()


@router.get("")
async def list_fairness_tests(
    request: Request,
    user=Depends(get_admin_user),
    status: Optional[str] = None,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    tests = AIFairnessTests.get_all(status=status)
    return [test.model_dump() for test in tests] if tests else []


@router.get("/model/{model_id}/latest")
async def get_latest_fairness_test_for_model(
    model_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIFairnessTests.get_latest_by_model(model_id)
    if not result:
        raise HTTPException(status_code=404, detail="No fairness test found for model")
    return result.model_dump()


@router.get("/{test_id}")
async def get_fairness_test(
    test_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIFairnessTests.get_by_id(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Fairness test not found")
    return result.model_dump()


@router.put("/{test_id}/status")
async def update_fairness_test_status(
    test_id: str,
    request: Request,
    form_data: FairnessStatusForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIFairnessTests.update_status(test_id, form_data.status)
    if not result:
        raise HTTPException(status_code=404, detail="Fairness test not found")
    return result.model_dump()


@router.put("/{test_id}/results")
async def upload_fairness_test_results(
    test_id: str,
    request: Request,
    form_data: FairnessResultsForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIFairnessTests.update_results(
        test_id,
        results=form_data.results,
        metrics_summary=form_data.metrics_summary,
        threshold_passed=form_data.threshold_passed,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Fairness test not found")
    return result.model_dump()


@router.delete("/{test_id}")
async def delete_fairness_test(
    test_id: str,
    request: Request,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    result = AIFairnessTests.delete_by_id(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Fairness test not found")
    return {"success": True}
