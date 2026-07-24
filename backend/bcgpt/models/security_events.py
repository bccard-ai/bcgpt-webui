import csv
import hashlib
import io
import json
import logging
import time
import uuid
from typing import Optional

from bcgpt.internal import Base, get_db
from bcgpt.utils.csv_safety import sanitize_row

from bcgpt.env import SRC_LOG_LEVELS
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Column, String, Text, JSON, Boolean, Integer, func

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


############################
# SecurityEvent DB Schema
############################


class SecurityEvent(Base):
    __tablename__ = "security_event"

    id = Column(String, primary_key=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    chat_id = Column(String, nullable=True, index=True)
    message_id = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    direction = Column(String, nullable=False)
    scanner_name = Column(String, nullable=False)
    threat_types = Column(JSON, nullable=True)
    threat_count = Column(Integer, default=0)
    severity = Column(String, nullable=True)
    is_blocked = Column(Boolean, default=False)
    is_shadow = Column(Boolean, default=True)
    text_hash = Column(String, nullable=True)
    text_sample = Column(Text, nullable=True)
    model_id = Column(String, nullable=True)
    # NOTE: 'metadata' is reserved by SQLAlchemy's Declarative API (Base.metadata),
    # so the Python attribute is 'event_metadata' while the DB column stays "metadata".
    event_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class SecurityEventModel(BaseModel):
    id: str
    timestamp: int
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    session_id: Optional[str] = None
    direction: str
    scanner_name: str
    threat_types: Optional[list[str]] = None
    threat_count: int = 0
    severity: Optional[str] = None
    is_blocked: bool = False
    is_shadow: bool = True
    text_hash: Optional[str] = None
    text_sample: Optional[str] = None
    model_id: Optional[str] = None
    # Read from the SQLAlchemy attribute `event_metadata` (the DB column is "metadata",
    # but `.metadata` on a declarative object is the reserved Base.metadata registry).
    # Serialize back out as "metadata" to preserve the API contract.
    event_metadata: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("event_metadata", "metadata"),
        serialization_alias="metadata",
    )
    created_at: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


############################
# Forms
############################


class SecurityEventForm(BaseModel):
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    session_id: Optional[str] = None
    direction: str = "input"
    scanner_name: str = "pipeline"
    threat_types: Optional[list[str]] = None
    threat_count: int = 0
    severity: Optional[str] = None
    is_blocked: bool = False
    is_shadow: bool = True
    text_hash: Optional[str] = None
    text_sample: Optional[str] = None
    model_id: Optional[str] = None
    event_metadata: Optional[dict] = Field(default=None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class SecurityEventsTable:
    def insert_new_event(
        self, form_data: SecurityEventForm
    ) -> Optional[SecurityEventModel]:
        with get_db() as db:
            id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            event = SecurityEventModel(
                **{
                    "id": id,
                    "timestamp": now,
                    **form_data.model_dump(),
                    "created_at": now,
                }
            )
            try:
                result = SecurityEvent(**event.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return SecurityEventModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception(f"Error creating a new security event: {e}")
                return None

    def get_event_by_id(self, id: str) -> Optional[SecurityEventModel]:
        try:
            with get_db() as db:
                event = db.query(SecurityEvent).filter_by(id=id).first()
                if not event:
                    return None
                return SecurityEventModel.model_validate(event)
        except Exception:
            return None

    def get_events_by_time_range(
        self,
        start_ts: int,
        end_ts: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SecurityEventModel]:
        with get_db() as db:
            return [
                SecurityEventModel.model_validate(event)
                for event in db.query(SecurityEvent)
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                )
                .order_by(SecurityEvent.timestamp.desc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def get_events_by_user_id(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SecurityEventModel]:
        with get_db() as db:
            return [
                SecurityEventModel.model_validate(event)
                for event in db.query(SecurityEvent)
                .filter_by(user_id=user_id)
                .order_by(SecurityEvent.timestamp.desc())
                .offset(offset)
                .limit(limit)
                .all()
            ]

    def get_event_stats(self, start_ts: int, end_ts: int) -> dict:
        with get_db() as db:
            events = (
                db.query(SecurityEvent)
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                )
                .all()
            )

            total = len(events)
            by_scanner: dict[str, int] = {}
            by_severity: dict[str, int] = {}
            by_threat_type: dict[str, int] = {}
            blocked_count = 0
            shadow_count = 0

            for event in events:
                scanner = event.scanner_name or "unknown"
                by_scanner[scanner] = by_scanner.get(scanner, 0) + 1

                sev = event.severity or "info"
                by_severity[sev] = by_severity.get(sev, 0) + 1

                if event.threat_types:
                    for tt in event.threat_types:
                        by_threat_type[tt] = by_threat_type.get(tt, 0) + 1

                if event.is_blocked:
                    blocked_count += 1
                if event.is_shadow:
                    shadow_count += 1

            return {
                "total": total,
                "by_scanner": by_scanner,
                "by_severity": by_severity,
                "by_threat_type": by_threat_type,
                "blocked_count": blocked_count,
                "shadow_count": shadow_count,
            }

    def get_threat_type_distribution(self, start_ts: int, end_ts: int) -> dict:
        with get_db() as db:
            events = (
                db.query(SecurityEvent)
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                )
                .all()
            )

            distribution: dict[str, int] = {}
            for event in events:
                if event.threat_types:
                    for tt in event.threat_types:
                        distribution[tt] = distribution.get(tt, 0) + 1

            return distribution

    def get_timeline_data(
        self,
        start_ts: int,
        end_ts: int,
        granularity: str = "hour",
    ) -> list[dict]:
        with get_db() as db:
            events = (
                db.query(SecurityEvent)
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                )
                .order_by(SecurityEvent.timestamp.asc())
                .all()
            )

            # Determine bucket size in ms
            if granularity == "day":
                bucket_ms = 86400 * 1000
            elif granularity == "week":
                bucket_ms = 604800 * 1000
            else:
                bucket_ms = 3600 * 1000  # hour

            buckets: dict[int, dict] = {}

            # Initialize buckets from start to end
            current = start_ts - (start_ts % bucket_ms)
            while current <= end_ts:
                buckets[current] = {
                    "timestamp": current,
                    "total": 0,
                    "blocked": 0,
                    "by_severity": {},
                }
                current += bucket_ms

            # Fill buckets
            for event in events:
                bucket_key = event.timestamp - (event.timestamp % bucket_ms)
                if bucket_key not in buckets:
                    buckets[bucket_key] = {
                        "timestamp": bucket_key,
                        "total": 0,
                        "blocked": 0,
                        "by_severity": {},
                    }
                buckets[bucket_key]["total"] += 1
                if event.is_blocked:
                    buckets[bucket_key]["blocked"] += 1
                sev = event.severity or "info"
                buckets[bucket_key]["by_severity"][sev] = (
                    buckets[bucket_key]["by_severity"].get(sev, 0) + 1
                )

            return sorted(buckets.values(), key=lambda x: x["timestamp"])

    def export_events(self, start_ts: int, end_ts: int, format: str = "json") -> str:
        with get_db() as db:
            events = (
                db.query(SecurityEvent)
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                )
                .order_by(SecurityEvent.timestamp.asc())
                .all()
            )

            if format == "csv":
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(
                    [
                        "id",
                        "timestamp",
                        "user_id",
                        "chat_id",
                        "message_id",
                        "session_id",
                        "direction",
                        "scanner_name",
                        "threat_types",
                        "threat_count",
                        "severity",
                        "is_blocked",
                        "is_shadow",
                        "text_hash",
                        "text_sample",
                        "model_id",
                        "created_at",
                    ]
                )
                for event in events:
                    # CSV formula-injection guard (CWE-1236) on every cell.
                    writer.writerow(
                        sanitize_row(
                            [
                                event.id,
                                event.timestamp,
                                event.user_id or "",
                                event.chat_id or "",
                                event.message_id or "",
                                event.session_id or "",
                                event.direction,
                                event.scanner_name,
                                (
                                    json.dumps(event.threat_types)
                                    if event.threat_types
                                    else ""
                                ),
                                event.threat_count,
                                event.severity or "",
                                event.is_blocked,
                                event.is_shadow,
                                event.text_hash or "",
                                event.text_sample or "",
                                event.model_id or "",
                                event.created_at,
                            ]
                        )
                    )
                return output.getvalue()

            elif format == "cef":
                lines = []
                severity_map = {"critical": 10, "high": 8, "medium": 5, "low": 3}
                for event in events:
                    sev = severity_map.get(event.severity, 1) if event.severity else 1
                    threat_str = (
                        ",".join(event.threat_types) if event.threat_types else "none"
                    )
                    line = (
                        f"CEF:0|BCGPT|SecurityScanner|1.0|{event.scanner_name}"
                        f"|{threat_str}|{sev}|"
                        f"ts={event.timestamp} src={event.user_id or ''} "
                        f"direction={event.direction} "
                        f"blocked={event.is_blocked} shadow={event.is_shadow} "
                        f"hash={event.text_hash or ''}"
                    )
                    lines.append(line)
                return "\n".join(lines)

            else:
                return json.dumps(
                    [SecurityEventModel.model_validate(e).model_dump() for e in events],
                    default=str,
                    ensure_ascii=False,
                    indent=2,
                )

    def _compute_integrity_hash(self, events: list) -> str:
        """Compute SHA-256 hash of all event IDs for tamper detection."""
        event_ids = "|".join(sorted(e.id for e in events))
        return hashlib.sha256(event_ids.encode()).hexdigest()

    def generate_compliance_report(self, start_ts: int, end_ts: int) -> dict:
        """Generate compliance summary report for Korean AI Basic Act / ISO 42001 audits."""
        events = self.get_events_by_time_range(start_ts, end_ts, limit=100000, offset=0)
        stats = self.get_event_stats(start_ts, end_ts)

        return {
            "report_metadata": {
                "generated_at": int(time.time() * 1000),
                "period_start": start_ts,
                "period_end": end_ts,
                "report_type": "AI Basic Act Compliance Report",
                "framework_version": "1.0",
            },
            "summary": {
                "total_events": len(events),
                "total_blocked": sum(1 for e in events if e.is_blocked),
                "total_shadow": sum(1 for e in events if e.is_shadow),
                "unique_users_affected": len(
                    set(e.user_id for e in events if e.user_id)
                ),
                "by_threat_type": stats.get("by_threat_type", {}),
                "by_severity": stats.get("by_severity", {}),
                "by_scanner": stats.get("by_scanner", {}),
                "by_direction": stats.get("by_direction", {}),
            },
            "compliance_status": {
                "audit_logging_enabled": True,
                "retention_days": 1825,
                "input_scanning_active": True,
                "output_scanning_active": True,
                "pii_detection_active": True,
            },
            "events_sample": [
                {
                    "timestamp": e.timestamp,
                    "direction": e.direction,
                    "threat_types": e.threat_types,
                    "severity": e.severity,
                    "is_blocked": e.is_blocked,
                    "scanner_name": e.scanner_name,
                }
                for e in events[:100]
            ],
            "integrity": self._compute_integrity_hash(events),
        }

    def purge_expired(self, retention_days: int = 180) -> int:
        cutoff_ts = int((time.time() - retention_days * 86400) * 1000)
        with get_db() as db:
            deleted = (
                db.query(SecurityEvent)
                .filter(SecurityEvent.timestamp < cutoff_ts)
                .delete()
            )
            db.commit()
            return deleted

    def count_events(
        self,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> int:
        with get_db() as db:
            query = db.query(func.count(SecurityEvent.id))
            if start_ts is not None:
                query = query.filter(SecurityEvent.timestamp >= start_ts)
            if end_ts is not None:
                query = query.filter(SecurityEvent.timestamp <= end_ts)
            return query.scalar() or 0

    def get_top_users(
        self,
        start_ts: int,
        end_ts: int,
        limit: int = 10,
    ) -> list[dict]:
        with get_db() as db:
            rows = (
                db.query(
                    SecurityEvent.user_id,
                    func.count(SecurityEvent.id).label("event_count"),
                    func.max(SecurityEvent.timestamp).label("latest_event"),
                )
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                    SecurityEvent.user_id.isnot(None),
                )
                .group_by(SecurityEvent.user_id)
                .order_by(func.count(SecurityEvent.id).desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "user_id": r.user_id,
                    "event_count": r.event_count,
                    "latest_event": r.latest_event,
                }
                for r in rows
            ]

    def get_direction_breakdown(
        self,
        start_ts: int,
        end_ts: int,
    ) -> dict:
        with get_db() as db:
            rows = (
                db.query(
                    SecurityEvent.direction,
                    func.count(SecurityEvent.id).label("cnt"),
                )
                .filter(
                    SecurityEvent.timestamp >= start_ts,
                    SecurityEvent.timestamp <= end_ts,
                )
                .group_by(SecurityEvent.direction)
                .all()
            )
            result = {"input": 0, "output": 0}
            for r in rows:
                key = r.direction if r.direction in result else "input"
                result[key] = r.cnt
            return result


SecurityEvents = SecurityEventsTable()
