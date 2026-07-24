import csv
import io
import json
import logging
import time
import uuid
from typing import Optional

from bcgpt.internal import Base, get_db
from bcgpt.utils.csv_safety import sanitize_row

from bcgpt.env import SRC_LOG_LEVELS
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Column, String, Integer, JSON, func, or_

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


############################
# AuditLog DB Schema
############################


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    user_email = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False, index=True)
    resource_id = Column(String, nullable=True)
    resource_name = Column(String, nullable=True)
    # NOTE: 'details' is aliased to avoid potential reserved word conflicts
    audit_details = Column("details", JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    request_method = Column(String, nullable=True)
    request_path = Column(String, nullable=True)
    response_status = Column(Integer, nullable=True)
    severity = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class AuditLogModel(BaseModel):
    id: str
    timestamp: int
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    audit_details: Optional[dict] = Field(default=None, alias="details")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    response_status: Optional[int] = None
    severity: Optional[str] = "INFO"
    category: Optional[str] = None
    session_id: Optional[str] = None
    created_at: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


############################
# Forms
############################


class AuditLogForm(BaseModel):
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str = "ACCESS"
    resource_type: str = "system"
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    audit_details: Optional[dict] = Field(default=None, alias="details")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    response_status: Optional[int] = None
    severity: Optional[str] = "INFO"
    category: Optional[str] = None
    session_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class AuditLogsTable:
    def insert_log(self, form_data: AuditLogForm) -> Optional[AuditLogModel]:
        with get_db() as db:
            id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            entry = AuditLogModel(
                **{
                    "id": id,
                    "timestamp": now,
                    **form_data.model_dump(),
                    "created_at": now,
                }
            )
            try:
                result = AuditLog(**entry.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return AuditLogModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception(f"Error creating audit log entry: {e}")
                return None

    def get_log_by_id(self, id: str) -> Optional[AuditLogModel]:
        try:
            with get_db() as db:
                entry = db.query(AuditLog).filter_by(id=id).first()
                if not entry:
                    return None
                return AuditLogModel.model_validate(entry)
        except Exception:
            return None

    def get_logs(
        self,
        skip: int = 0,
        limit: int = 50,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        search: Optional[str] = None,
    ) -> list[AuditLogModel]:
        with get_db() as db:
            query = db.query(AuditLog)

            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            if severity:
                query = query.filter(AuditLog.severity == severity)
            if start_time is not None:
                query = query.filter(AuditLog.timestamp >= start_time)
            if end_time is not None:
                query = query.filter(AuditLog.timestamp <= end_time)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (AuditLog.user_email.ilike(search_pattern))
                    | (AuditLog.resource_name.ilike(search_pattern))
                    | (AuditLog.request_path.ilike(search_pattern))
                    | (AuditLog.ip_address.ilike(search_pattern))
                )

            return [
                AuditLogModel.model_validate(entry)
                for entry in query.order_by(AuditLog.timestamp.desc())
                .offset(skip)
                .limit(limit)
                .all()
            ]

    def count_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        search: Optional[str] = None,
    ) -> int:
        with get_db() as db:
            query = db.query(func.count(AuditLog.id))

            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            if severity:
                query = query.filter(AuditLog.severity == severity)
            if start_time is not None:
                query = query.filter(AuditLog.timestamp >= start_time)
            if end_time is not None:
                query = query.filter(AuditLog.timestamp <= end_time)
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (AuditLog.user_email.ilike(search_pattern))
                    | (AuditLog.resource_name.ilike(search_pattern))
                    | (AuditLog.request_path.ilike(search_pattern))
                    | (AuditLog.ip_address.ilike(search_pattern))
                )

            return query.scalar() or 0

    def get_stats(self) -> dict:
        with get_db() as db:
            now = int(time.time() * 1000)
            today_start = now - (now % 86400000)  # midnight today in epoch ms

            # Adjust for timezone: treat today_start as local midnight
            total_logs = db.query(func.count(AuditLog.id)).scalar() or 0
            logs_today = (
                db.query(func.count(AuditLog.id))
                .filter(AuditLog.timestamp >= today_start)
                .scalar()
                or 0
            )

            # Severity distribution
            severity_rows = (
                db.query(AuditLog.severity, func.count(AuditLog.id).label("cnt"))
                .group_by(AuditLog.severity)
                .all()
            )
            by_severity = {r.severity or "INFO": r.cnt for r in severity_rows}

            # Action distribution
            action_rows = (
                db.query(AuditLog.action, func.count(AuditLog.id).label("cnt"))
                .group_by(AuditLog.action)
                .all()
            )
            by_action = {r.action or "UNKNOWN": r.cnt for r in action_rows}

            # Resource type distribution
            resource_rows = (
                db.query(AuditLog.resource_type, func.count(AuditLog.id).label("cnt"))
                .group_by(AuditLog.resource_type)
                .all()
            )
            by_resource_type = {
                r.resource_type or "unknown": r.cnt for r in resource_rows
            }

            # Recent critical count (last 24h)
            yesterday = now - (24 * 3600 * 1000)
            recent_critical_count = (
                db.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.timestamp >= yesterday,
                    AuditLog.severity == "CRITICAL",
                )
                .scalar()
                or 0
            )

            # Unique active users today
            active_users_today = (
                db.query(func.count(func.distinct(AuditLog.user_id)))
                .filter(
                    AuditLog.timestamp >= today_start,
                    AuditLog.user_id.isnot(None),
                )
                .scalar()
                or 0
            )

            return {
                "total_logs": total_logs,
                "logs_today": logs_today,
                "by_severity": by_severity,
                "by_action": by_action,
                "by_resource_type": by_resource_type,
                "recent_critical_count": recent_critical_count,
                "active_users_today": active_users_today,
            }

    def get_personal_data_access(
        self,
        skip: int = 0,
        limit: int = 50,
        user_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[AuditLogModel]:
        with get_db() as db:
            query = db.query(AuditLog).filter(
                or_(
                    AuditLog.category == "data_access",
                    AuditLog.action == "PII_MASKED",
                ),
                AuditLog.resource_type.in_(["user", "chat", "message", "file"]),
            )
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if start_time is not None:
                query = query.filter(AuditLog.timestamp >= start_time)
            if end_time is not None:
                query = query.filter(AuditLog.timestamp <= end_time)

            return [
                AuditLogModel.model_validate(entry)
                for entry in query.order_by(AuditLog.timestamp.desc())
                .offset(skip)
                .limit(limit)
                .all()
            ]

    def count_personal_data_access(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> int:
        with get_db() as db:
            query = db.query(func.count(AuditLog.id)).filter(
                or_(
                    AuditLog.category == "data_access",
                    AuditLog.action == "PII_MASKED",
                ),
                AuditLog.resource_type.in_(["user", "chat", "message", "file"]),
            )
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if start_time is not None:
                query = query.filter(AuditLog.timestamp >= start_time)
            if end_time is not None:
                query = query.filter(AuditLog.timestamp <= end_time)
            return query.scalar()

    def get_anomalies(self, hours: int = 24) -> list[dict]:
        now = int(time.time() * 1000)
        period_start = now - (hours * 3600 * 1000)
        anomalies: list[dict] = []

        with get_db() as db:
            # 1. Multiple failed logins from same IP (>5 in period)
            failed_login_rows = (
                db.query(
                    AuditLog.ip_address,
                    func.count(AuditLog.id).label("cnt"),
                )
                .filter(
                    AuditLog.timestamp >= period_start,
                    AuditLog.action == "LOGIN",
                    AuditLog.response_status >= 400,
                    AuditLog.ip_address.isnot(None),
                )
                .group_by(AuditLog.ip_address)
                .having(func.count(AuditLog.id) > 5)
                .all()
            )
            for r in failed_login_rows:
                anomalies.append(
                    {
                        "type": "multiple_failed_logins",
                        "severity": "WARNING",
                        "details": {
                            "ip_address": r.ip_address,
                            "failed_attempts": r.cnt,
                            "period_hours": hours,
                        },
                        "detected_at": now,
                    }
                )

            # 2. Unusual data export volume (>10 exports by one user)
            export_rows = (
                db.query(
                    AuditLog.user_id,
                    func.count(AuditLog.id).label("cnt"),
                )
                .filter(
                    AuditLog.timestamp >= period_start,
                    AuditLog.action == "EXPORT",
                    AuditLog.user_id.isnot(None),
                )
                .group_by(AuditLog.user_id)
                .having(func.count(AuditLog.id) > 10)
                .all()
            )
            for r in export_rows:
                anomalies.append(
                    {
                        "type": "excessive_exports",
                        "severity": "WARNING",
                        "details": {
                            "user_id": r.user_id,
                            "export_count": r.cnt,
                            "period_hours": hours,
                        },
                        "detected_at": now,
                    }
                )

            # 3. Off-hours admin access (10pm-6am, simplified via timestamp hour)
            off_hours_logs = (
                db.query(AuditLog)
                .filter(
                    AuditLog.timestamp >= period_start,
                    AuditLog.category == "authentication",
                    AuditLog.action == "LOGIN",
                )
                .all()
            )
            for entry in off_hours_logs:
                # Convert epoch ms to hour (approximate, UTC-based)
                hour_utc = (entry.timestamp // 3600000) % 24
                if hour_utc >= 22 or hour_utc < 6:
                    anomalies.append(
                        {
                            "type": "off_hours_admin_access",
                            "severity": "INFO",
                            "details": {
                                "user_id": entry.user_id,
                                "user_email": entry.user_email,
                                "ip_address": entry.ip_address,
                                "hour_utc": hour_utc,
                            },
                            "detected_at": entry.timestamp,
                        }
                    )

            # 4. Bulk data access (>50 reads in 1 hour by one user)
            one_hour_ago = now - (3600 * 1000)
            bulk_read_rows = (
                db.query(
                    AuditLog.user_id,
                    func.count(AuditLog.id).label("cnt"),
                )
                .filter(
                    AuditLog.timestamp >= one_hour_ago,
                    AuditLog.action == "READ",
                    AuditLog.user_id.isnot(None),
                )
                .group_by(AuditLog.user_id)
                .having(func.count(AuditLog.id) > 50)
                .all()
            )
            for r in bulk_read_rows:
                anomalies.append(
                    {
                        "type": "bulk_data_access",
                        "severity": "WARNING",
                        "details": {
                            "user_id": r.user_id,
                            "read_count": r.cnt,
                            "period_hours": 1,
                        },
                        "detected_at": now,
                    }
                )

        return anomalies

    def get_timeline_data(
        self,
        hours: int = 24,
        interval: str = "hour",
    ) -> list[dict]:
        now = int(time.time() * 1000)
        start_ts = now - (hours * 3600 * 1000)

        with get_db() as db:
            events = (
                db.query(AuditLog)
                .filter(AuditLog.timestamp >= start_ts, AuditLog.timestamp <= now)
                .order_by(AuditLog.timestamp.asc())
                .all()
            )

            if interval == "day":
                bucket_ms = 86400 * 1000
            else:
                bucket_ms = 3600 * 1000  # hour

            buckets: dict[int, dict] = {}

            current = start_ts - (start_ts % bucket_ms)
            while current <= now:
                buckets[current] = {"timestamp": current, "count": 0}
                current += bucket_ms

            for event in events:
                bucket_key = event.timestamp - (event.timestamp % bucket_ms)
                if bucket_key not in buckets:
                    buckets[bucket_key] = {"timestamp": bucket_key, "count": 0}
                buckets[bucket_key]["count"] += 1

            return sorted(buckets.values(), key=lambda x: x["timestamp"])

    def export_logs(
        self,
        format: str = "json",
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> str:
        logs = self.get_logs(
            skip=0,
            limit=100000,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
        )

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "timestamp",
                    "user_id",
                    "user_email",
                    "action",
                    "resource_type",
                    "resource_id",
                    "resource_name",
                    "details",
                    "ip_address",
                    "user_agent",
                    "request_method",
                    "request_path",
                    "response_status",
                    "severity",
                    "category",
                    "session_id",
                    "created_at",
                ]
            )
            for entry in logs:
                # CSV formula-injection guard (CWE-1236) on every cell.
                writer.writerow(
                    sanitize_row(
                        [
                            entry.id,
                            entry.timestamp,
                            entry.user_id or "",
                            entry.user_email or "",
                            entry.action,
                            entry.resource_type,
                            entry.resource_id or "",
                            entry.resource_name or "",
                            (
                                json.dumps(entry.audit_details)
                                if entry.audit_details
                                else ""
                            ),
                            entry.ip_address or "",
                            entry.user_agent or "",
                            entry.request_method or "",
                            entry.request_path or "",
                            entry.response_status or "",
                            entry.severity or "",
                            entry.category or "",
                            entry.session_id or "",
                            entry.created_at,
                        ]
                    )
                )
            return output.getvalue()

        return json.dumps(
            [entry.model_dump() for entry in logs],
            default=str,
            ensure_ascii=False,
            indent=2,
        )

    def get_compliance_summary(self) -> dict:
        now = int(time.time() * 1000)
        thirty_days_ago = now - (30 * 86400 * 1000)

        with get_db() as db:
            total_events = (
                db.query(func.count(AuditLog.id))
                .filter(AuditLog.timestamp >= thirty_days_ago)
                .scalar()
                or 0
            )

            personal_data_access_count = (
                db.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.timestamp >= thirty_days_ago,
                    or_(
                        AuditLog.category == "data_access",
                        AuditLog.action == "PII_MASKED",
                    ),
                    AuditLog.resource_type.in_(["user", "chat", "message", "file"]),
                )
                .scalar()
                or 0
            )

            pii_masked_count = (
                db.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.timestamp >= thirty_days_ago,
                    AuditLog.action == "PII_MASKED",
                )
                .scalar()
                or 0
            )

            data_exports = (
                db.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.timestamp >= thirty_days_ago,
                    AuditLog.action == "EXPORT",
                )
                .scalar()
                or 0
            )

            failed_auth_attempts = (
                db.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.timestamp >= thirty_days_ago,
                    AuditLog.action == "LOGIN",
                    AuditLog.response_status >= 400,
                )
                .scalar()
                or 0
            )

            security_events = (
                db.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.timestamp >= thirty_days_ago,
                    AuditLog.severity.in_(["CRITICAL", "WARNING"]),
                )
                .scalar()
                or 0
            )

        return {
            "period_days": 30,
            "period_start": thirty_days_ago,
            "period_end": now,
            "total_events": total_events,
            "personal_data_access_count": personal_data_access_count,
            "pii_masked_count": pii_masked_count,
            "data_exports": data_exports,
            "security_events": security_events,
            "failed_auth_attempts": failed_auth_attempts,
            "generated_at": now,
        }

    def purge_expired(self, days: int = 90) -> int:
        cutoff_ts = int((time.time() - days * 86400) * 1000)
        with get_db() as db:
            deleted = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_ts).delete()
            db.commit()
            return deleted


AuditLogs = AuditLogsTable()
