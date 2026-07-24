from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from bcgpt.models.security_events import SecurityEvents, SecurityEventModel
from bcgpt.utils import get_admin_user

router = APIRouter()


class EventListResponse(BaseModel):
    events: list[SecurityEventModel]
    total: int


class StatsResponse(BaseModel):
    total: int
    by_scanner: dict[str, int]
    by_severity: dict[str, int]
    by_threat_type: dict[str, int]
    by_direction: dict[str, int]
    blocked_count: int
    shadow_count: int


class TimelineBucket(BaseModel):
    timestamp: int
    total: int
    blocked: int
    by_severity: dict[str, int]


class TimelineResponse(BaseModel):
    data: list[TimelineBucket]


class CountResponse(BaseModel):
    count: int


class PurgeResponse(BaseModel):
    deleted: int


class TopUserResponse(BaseModel):
    user_id: str
    event_count: int
    latest_event: int


class TopUsersResponse(BaseModel):
    users: list[TopUserResponse]


class ExportResponse(BaseModel):
    data: str
    format: str


@router.get("/events", response_model=EventListResponse)
async def list_events(
    start_ts: int = Query(..., description="Start timestamp (unix ms)"),
    end_ts: int = Query(..., description="End timestamp (unix ms)"),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(get_admin_user),
):
    if user_id:
        all_events = SecurityEvents.get_events_by_user_id(
            user_id, limit=limit + offset, offset=0
        )
        all_events = [e for e in all_events if start_ts <= e.timestamp <= end_ts]
        events = all_events[offset : offset + limit]
    else:
        events = SecurityEvents.get_events_by_time_range(
            start_ts, end_ts, limit=limit, offset=offset
        )
    total = SecurityEvents.count_events(start_ts=start_ts, end_ts=end_ts)
    return EventListResponse(events=events, total=total)


@router.get("/events/stats", response_model=StatsResponse)
async def get_event_stats(
    start_ts: int = Query(..., description="Start timestamp (unix ms)"),
    end_ts: int = Query(..., description="End timestamp (unix ms)"),
    user=Depends(get_admin_user),
):
    stats = SecurityEvents.get_event_stats(start_ts, end_ts)
    direction = SecurityEvents.get_direction_breakdown(start_ts, end_ts)
    stats["by_direction"] = direction
    return StatsResponse(**stats)


@router.get("/events/timeline", response_model=TimelineResponse)
async def get_timeline(
    start_ts: int = Query(..., description="Start timestamp (unix ms)"),
    end_ts: int = Query(..., description="End timestamp (unix ms)"),
    granularity: str = Query("hour", description="hour, day, or week"),
    user=Depends(get_admin_user),
):
    data = SecurityEvents.get_timeline_data(start_ts, end_ts, granularity=granularity)
    return TimelineResponse(data=[TimelineBucket(**d) for d in data])


@router.get("/events/top-users", response_model=TopUsersResponse)
async def get_top_users(
    start_ts: int = Query(..., description="Start timestamp (unix ms)"),
    end_ts: int = Query(..., description="End timestamp (unix ms)"),
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_admin_user),
):
    users = SecurityEvents.get_top_users(start_ts, end_ts, limit=limit)
    return TopUsersResponse(users=[TopUserResponse(**u) for u in users])


@router.get("/events/export", response_model=ExportResponse)
async def export_events(
    start_ts: int = Query(..., description="Start timestamp (unix ms)"),
    end_ts: int = Query(..., description="End timestamp (unix ms)"),
    format: str = Query("json", description="json, csv, or cef"),
    user=Depends(get_admin_user),
):
    data = SecurityEvents.export_events(start_ts, end_ts, format=format)
    return ExportResponse(data=data, format=format)


@router.get("/compliance-report")
async def get_compliance_report(
    start_ts: int = Query(..., description="Start timestamp (unix ms)"),
    end_ts: int = Query(..., description="End timestamp (unix ms)"),
    user=Depends(get_admin_user),
):
    report = SecurityEvents.generate_compliance_report(start_ts, end_ts)
    return report


@router.delete("/events/purge", response_model=PurgeResponse)
async def purge_events(
    retention_days: int = Query(
        180, ge=1, description="Delete events older than N days"
    ),
    user=Depends(get_admin_user),
):
    deleted = SecurityEvents.purge_expired(retention_days=retention_days)
    return PurgeResponse(deleted=deleted)


@router.get("/events/count", response_model=CountResponse)
async def count_events(
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    user=Depends(get_admin_user),
):
    count = SecurityEvents.count_events(start_ts=start_ts, end_ts=end_ts)
    return CountResponse(count=count)
