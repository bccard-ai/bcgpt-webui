from fastapi import APIRouter, Depends, HTTPException, Request

from bcgpt.compliance.models.ai_inventory import AIModelInventories
from bcgpt.compliance.models.aiia import AIIARecords
from bcgpt.compliance.models.dsar import AIDSARRequests
from bcgpt.compliance.models.fairness_test import AIFairnessTests
from bcgpt.compliance.models.incident import AIIncidents
from bcgpt.models.audit_log import AuditLogs
from bcgpt.utils.auth import get_admin_user

router = APIRouter()


@router.get("/overview")
async def get_compliance_overview(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    inventory_items = []
    try:
        inventory_items = AIModelInventories.get_all()
    except Exception:
        inventory_items = []

    risk_tier_counts: dict[str, int] = {}
    for item in inventory_items or []:
        risk_tier = item.risk_tier or "unknown"
        risk_tier_counts[risk_tier] = risk_tier_counts.get(risk_tier, 0) + 1

    pending_aiias = []
    try:
        pending_aiias = AIIARecords.get_all(status="in_review")
    except Exception:
        pending_aiias = []

    overdue_aiias = []
    try:
        overdue_aiias = AIIARecords.get_expired()
    except Exception:
        overdue_aiias = []

    incident_stats: dict[str, object] = {
        "total": 0,
        "by_status": {},
        "by_severity": {},
        "overdue": 0,
    }
    try:
        incident_stats = AIIncidents.get_stats()
    except Exception:
        incident_stats = {"total": 0, "by_status": {}, "by_severity": {}, "overdue": 0}

    overdue_incidents = []
    try:
        overdue_incidents = AIIncidents.get_overdue()
    except Exception:
        overdue_incidents = []

    fairness_tests = []
    try:
        fairness_tests = AIFairnessTests.get_all()
    except Exception:
        fairness_tests = []

    fairness_pass_rate = 0.0
    if fairness_tests:
        passed_tests = sum(
            1 for test in fairness_tests if test.threshold_passed is True
        )
        fairness_pass_rate = round(passed_tests / len(fairness_tests), 4)

    dsar_pending = []
    try:
        dsar_pending = AIDSARRequests.get_all(status="pending")
    except Exception:
        dsar_pending = []

    incident_status_counts = incident_stats.get("by_status")
    open_incidents = (
        incident_status_counts.get("open", 0)
        if isinstance(incident_status_counts, dict)
        else 0
    )

    return {
        "inventory_items_by_risk_tier": risk_tier_counts,
        "pending_aiias": len(pending_aiias or []),
        "overdue_aiias": len(overdue_aiias or []),
        "open_incidents": open_incidents,
        "overdue_incidents": len(overdue_incidents or []),
        "fairness_test_pass_rate": fairness_pass_rate,
        "dsar_pending_count": len(dsar_pending or []),
    }


@router.get("/regulatory-mapping")
async def get_regulatory_mapping(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    return {
        "Korean AI Basic Act": {
            "Article 31 - AI transparency": {
                "status": "partial",
                "evidence": ["AI transparency settings", "dashboard.overview"],
            },
            "Articles 33-35 - High-impact AI safety and reliability": {
                "status": "implemented",
                "evidence": ["inventory", "aiia", "incidents", "fairness"],
            },
            "Article 37-2 - Data subject rights": {
                "status": "implemented",
                "evidence": [
                    "dsar.export",
                    "dsar.erase",
                    "dsar.explain",
                    "dsar.object",
                ],
            },
        },
        "EU AI Act": {
            "Risk management and model inventory": {
                "status": "implemented",
                "evidence": ["inventory", "aiia"],
            },
            "Post-market monitoring and incident reporting": {
                "status": "implemented",
                "evidence": ["incidents", "dashboard.timeline"],
            },
            "Bias monitoring and technical documentation": {
                "status": "partial",
                "evidence": ["fairness", "vendor"],
            },
        },
        "FSC Guidelines": {
            "Governance and accountability": {
                "status": "implemented",
                "evidence": ["inventory", "aiia", "dashboard.regulatory_mapping"],
            },
            "Consumer rights and automated decision explanation": {
                "status": "implemented",
                "evidence": ["dsar.explain", "dsar.object"],
            },
            "Third-party and AIBOM management": {
                "status": "implemented",
                "evidence": ["vendor"],
            },
        },
    }


@router.get("/timeline")
async def get_compliance_timeline(
    request: Request,
    user=Depends(get_admin_user),
    limit: int = 50,
):
    config = request.app.state.config
    if not getattr(config, "COMPLIANCE_ENABLED", False):
        raise HTTPException(status_code=403, detail="Compliance module is disabled")

    events = []

    audit_logs = []
    try:
        audit_logs = AuditLogs.get_logs(limit=limit)
    except Exception:
        audit_logs = []

    for log in audit_logs or []:
        timestamp = getattr(log, "timestamp", 0) or 0
        events.append(
            {
                "source": "audit_log",
                "action": "audit_event",
                "timestamp": timestamp,
                "record": log.model_dump() if hasattr(log, "model_dump") else log,
            }
        )

    incidents = []
    try:
        incidents = AIIncidents.get_all()
    except Exception:
        incidents = []

    for incident in (incidents or [])[:limit]:
        timestamp = (
            incident.updated_at
            or incident.created_at
            or incident.detected_at
            or incident.reported_at
            or 0
        )
        events.append(
            {
                "source": "incident",
                "action": "incident_update",
                "timestamp": timestamp,
                "record": incident.model_dump(),
            }
        )

    aiias = []
    try:
        aiias = AIIARecords.get_all()
    except Exception:
        aiias = []

    for aiia in (aiias or [])[:limit]:
        timestamp = aiia.updated_at or aiia.created_at or aiia.approved_at or 0
        events.append(
            {
                "source": "aiia",
                "action": "aiia_update",
                "timestamp": timestamp,
                "record": aiia.model_dump(),
            }
        )

    fairness_tests = []
    try:
        fairness_tests = AIFairnessTests.get_all()
    except Exception:
        fairness_tests = []

    for test in (fairness_tests or [])[:limit]:
        timestamp = (
            test.updated_at
            or test.created_at
            or test.completed_at
            or test.started_at
            or 0
        )
        events.append(
            {
                "source": "fairness_test",
                "action": "fairness_test_update",
                "timestamp": timestamp,
                "record": test.model_dump(),
            }
        )

    events.sort(key=lambda event: event.get("timestamp") or 0, reverse=True)
    return {"events": events[:limit]}
