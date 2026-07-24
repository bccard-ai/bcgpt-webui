from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger as log
from pydantic import BaseModel

from bcgpt.models.audit_log import AuditLogs, AuditLogModel
from bcgpt.utils import get_admin_user
from bcgpt.utils.audit import AuditLevel

router = APIRouter()


def _get_config_value(val):
    from bcgpt.config import PersistentConfig

    if isinstance(val, PersistentConfig):
        return val.value
    return val


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogModel]
    total: int


class AuditStatsResponse(BaseModel):
    total_logs: int
    logs_today: int
    by_severity: dict[str, int]
    by_action: dict[str, int]
    by_resource_type: dict[str, int]
    recent_critical_count: int
    active_users_today: int


class TimelineBucket(BaseModel):
    timestamp: int
    count: int


class TimelineResponse(BaseModel):
    data: list[TimelineBucket]


class AnomalyResponse(BaseModel):
    type: str
    severity: str
    details: dict
    detected_at: int


class AnomaliesResponse(BaseModel):
    anomalies: list[AnomalyResponse]


class ComplianceSummaryResponse(BaseModel):
    period_days: int
    period_start: int
    period_end: int
    total_events: int
    personal_data_access_count: int
    pii_masked_count: int
    data_exports: int
    security_events: int
    failed_auth_attempts: int
    generated_at: int


class PurgeResponse(BaseModel):
    deleted: int


class AuditConfigResponse(BaseModel):
    audit_log_level: str
    audit_excluded_paths: str
    max_body_log_size: int
    audit_log_file_rotation_size: str
    audit_retention_days: int


class AuditConfigForm(BaseModel):
    audit_log_level: Optional[str] = None
    audit_excluded_paths: Optional[str] = None
    max_body_log_size: Optional[int] = None
    audit_log_file_rotation_size: Optional[str] = None
    audit_retention_days: Optional[int] = None


@router.get("/config", response_model=AuditConfigResponse)
async def get_audit_config(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    return AuditConfigResponse(
        audit_log_level=_get_config_value(config.AUDIT_LOG_LEVEL),
        audit_excluded_paths=_get_config_value(config.AUDIT_EXCLUDED_PATHS),
        max_body_log_size=_get_config_value(config.MAX_BODY_LOG_SIZE),
        audit_log_file_rotation_size=_get_config_value(
            config.AUDIT_LOG_FILE_ROTATION_SIZE
        ),
        audit_retention_days=_get_config_value(config.AUDIT_RETENTION_DAYS),
    )


@router.post("/config/update", response_model=AuditConfigResponse)
async def update_audit_config(
    request: Request, form_data: AuditConfigForm, user=Depends(get_admin_user)
):
    config = request.app.state.config

    if form_data.audit_log_level is not None:
        try:
            AuditLevel(form_data.audit_log_level)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid audit_log_level: {form_data.audit_log_level}. "
                f"Valid values: {[e.value for e in AuditLevel]}",
            )
        config.AUDIT_LOG_LEVEL = form_data.audit_log_level

    if form_data.audit_excluded_paths is not None:
        config.AUDIT_EXCLUDED_PATHS = form_data.audit_excluded_paths
    if form_data.max_body_log_size is not None:
        config.MAX_BODY_LOG_SIZE = form_data.max_body_log_size
    if form_data.audit_log_file_rotation_size is not None:
        config.AUDIT_LOG_FILE_ROTATION_SIZE = form_data.audit_log_file_rotation_size
    if form_data.audit_retention_days is not None:
        config.AUDIT_RETENTION_DAYS = form_data.audit_retention_days

    try:
        from bcgpt.models.audit_log import AuditLogs, AuditLogForm

        AuditLogs.insert_log(
            AuditLogForm(
                user_id=user.id,
                user_email=user.email,
                action="UPDATE",
                resource_type="config",
                request_method="POST",
                request_path="/api/v1/audit/config/update",
                response_status=200,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                # `audit_details` is a JSON/dict column — pass a dict, not a
                # string, or Pydantic rejects the row and the log is dropped.
                audit_details={"changes": form_data.model_dump(exclude_none=True)},
                severity="INFO",
                category="configuration",
            )
        )
    except Exception as e:
        log.warning(f"Failed to record audit config change: {e}")

    return AuditConfigResponse(
        audit_log_level=_get_config_value(config.AUDIT_LOG_LEVEL),
        audit_excluded_paths=_get_config_value(config.AUDIT_EXCLUDED_PATHS),
        max_body_log_size=_get_config_value(config.MAX_BODY_LOG_SIZE),
        audit_log_file_rotation_size=_get_config_value(
            config.AUDIT_LOG_FILE_ROTATION_SIZE
        ),
        audit_retention_days=_get_config_value(config.AUDIT_RETENTION_DAYS),
    )


@router.get("/logs", response_model=AuditLogListResponse)
async def list_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    start_time: Optional[int] = Query(None, description="Start timestamp (unix ms)"),
    end_time: Optional[int] = Query(None, description="End timestamp (unix ms)"),
    search: Optional[str] = Query(None),
    user=Depends(get_admin_user),
):
    logs = AuditLogs.get_logs(
        skip=skip,
        limit=limit,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        search=search,
    )
    total = AuditLogs.count_logs(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        search=search,
    )
    return AuditLogListResponse(logs=logs, total=total)


@router.get("/stats", response_model=AuditStatsResponse)
async def get_stats(user=Depends(get_admin_user)):
    stats = AuditLogs.get_stats()
    return AuditStatsResponse(**stats)


@router.get("/personal-data-access", response_model=AuditLogListResponse)
async def get_personal_data_access(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user_id: Optional[str] = Query(None),
    start_time: Optional[int] = Query(None),
    end_time: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    logs = AuditLogs.get_personal_data_access(
        skip=skip,
        limit=limit,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
    )
    total = AuditLogs.count_personal_data_access(
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
    )
    return AuditLogListResponse(logs=logs, total=total)


@router.get("/anomalies", response_model=AnomaliesResponse)
async def get_anomalies(
    hours: int = Query(24, ge=1, le=720, description="Look back period in hours"),
    user=Depends(get_admin_user),
):
    anomalies = AuditLogs.get_anomalies(hours=hours)
    return AnomaliesResponse(anomalies=[AnomalyResponse(**a) for a in anomalies])


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    hours: int = Query(24, ge=1, le=720),
    interval: str = Query("hour", description="hour or day"),
    user=Depends(get_admin_user),
):
    data = AuditLogs.get_timeline_data(hours=hours, interval=interval)
    return TimelineResponse(data=[TimelineBucket(**d) for d in data])


@router.get("/export")
async def export_logs(
    format: str = Query("json", description="json or csv"),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    start_time: Optional[int] = Query(None),
    end_time: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    data = AuditLogs.export_logs(
        format=format,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
    )

    if format == "csv":
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
        )

    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
    )


@router.get("/compliance-summary", response_model=ComplianceSummaryResponse)
async def get_compliance_summary(user=Depends(get_admin_user)):
    summary = AuditLogs.get_compliance_summary()
    return ComplianceSummaryResponse(**summary)


@router.delete("/purge", response_model=PurgeResponse)
async def purge_logs(
    days: int = Query(90, ge=1, description="Delete logs older than N days"),
    user=Depends(get_admin_user),
):
    deleted = AuditLogs.purge_expired(days=days)
    return PurgeResponse(deleted=deleted)
