"""
Data Subject Access Request (DSAR) processor.

Implements PIPA Art. 37-2 rights:
  - Right to data export (portability)
  - Right to erasure (right to be forgotten)
  - Right to explanation of automated decisions
  - Right to object to automated processing

Cascade delete covers ALL tables with user_id references.
Data export bundles all user data into a structured JSON.
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
import time
import zipfile
from collections import Counter
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text

from bcgpt.internal import get_db
from bcgpt.models import Chats, Files, Groups, UserMFAs

log = logging.getLogger(__name__)


# Tables to hard-delete on erasure (user-owned content)
_HARD_DELETE_TABLES = [
    ("memory", "user_id"),
    ("folder", "user_id"),
    ("feedback", "user_id"),
    ("tag", "user_id"),
    ("prompt", "user_id"),
    ("tool", "user_id"),
    ("function", "user_id"),
    ("model", "user_id"),
    ("knowledge", "user_id"),
    ("channel", "user_id"),
    ("message", "user_id"),
    ("message_reaction", "user_id"),
    ("handoff_request", "user_id"),
    ("hitl_approval_ticket", "user_id"),
    ("ai_model_inventory", "business_owner_id"),
    ("aiia_record", "assessor_id"),
    ("ai_fairness_test", "created_by"),
    ("ai_dsar_request", "user_id"),
    ("ai_rag_provenance", "user_id"),
]

# Tables to anonymize on erasure (retain for compliance/audit)
_ANONYMIZE_TABLES = [
    ("audit_log", "user_id"),
    ("security_event", "user_id"),
    ("llm_token_usage", "user_id"),
    ("ai_incident", "related_user_id"),
]

# Current model-backed tables that are erased through existing application APIs
# or final account removal steps. They are still exported with raw SQL.
_OPERATIONAL_USER_TABLES = [
    ("chat", "user_id"),
    ("file", "user_id"),
    ("group", "user_id"),
    ("user_mfa", "user_id"),
    ("auth", "id"),
    ("user", "id"),
]

# Legacy/Open WebUI-era tables may still exist in upgraded deployments.
_LEGACY_HARD_DELETE_TABLES = [
    ("chatidtag", "user_id"),
    ("document", "user_id"),
    ("modelfile", "user_id"),
]

_EXPORT_TABLES = list(
    dict.fromkeys(
        _HARD_DELETE_TABLES
        + _ANONYMIZE_TABLES
        + _OPERATIONAL_USER_TABLES
        + _LEGACY_HARD_DELETE_TABLES
    )
)

_SENSITIVE_EXPORT_FIELDS = {
    "auth": {"password"},
    "user": {"api_key"},
    "user_mfa": {"secret", "backup_codes"},
}

_REDACTED = "[REDACTED_FOR_SECURITY]"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _quote_identifier(identifier: str) -> str:
    if not identifier or "\x00" in identifier:
        raise ValueError("Invalid SQL identifier")
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {str(key): _json_safe(value) for key, value in dict(row).items()}
        for row in rows
    ]


def _redact_export_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    sensitive_fields = _SENSITIVE_EXPORT_FIELDS.get(table, set())
    if not sensitive_fields:
        return row
    return {
        key: (_REDACTED if key in sensitive_fields and value is not None else value)
        for key, value in row.items()
    }


def _coerce_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _rowcount(result: Any) -> int:
    count = getattr(result, "rowcount", 0)
    if count is None or count < 0:
        return 0
    return int(count)


def _safe_filename(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-_." else "_" for char in value)
    return safe[:64] or "user"


def _select_rows(table: str, column: str, value: str) -> list[dict[str, Any]]:
    sql = text(
        f"SELECT * FROM {_quote_identifier(table)} "
        f"WHERE {_quote_identifier(column)} = :value"
    )
    with get_db() as db:
        rows = db.execute(sql, {"value": value}).mappings().all()
        return [_redact_export_row(table, row) for row in _rows_to_dicts(rows)]


def _select_shared_chat_rows(user_id: str) -> list[dict[str, Any]]:
    chat_rows = _select_rows("chat", "user_id", user_id)
    shared_rows: list[dict[str, Any]] = []
    for row in chat_rows:
        chat_id = row.get("id")
        if not chat_id:
            continue
        shared_rows.extend(_select_rows("chat", "user_id", f"shared-{chat_id}"))
    return shared_rows


def _select_group_memberships(user_id: str) -> list[dict[str, Any]]:
    sql = text(
        f"SELECT * FROM {_quote_identifier('group')} "
        f"WHERE CAST({_quote_identifier('user_ids')} AS TEXT) LIKE :needle"
    )
    with get_db() as db:
        rows = db.execute(sql, {"needle": f"%{json.dumps(user_id)}%"}).mappings().all()
        return _rows_to_dicts(rows)


def _count_rows(table: str, column: str, value: str) -> int:
    sql = text(
        f"SELECT COUNT(*) FROM {_quote_identifier(table)} "
        f"WHERE {_quote_identifier(column)} = :value"
    )
    with get_db() as db:
        return int(db.execute(sql, {"value": value}).scalar() or 0)


def _delete_rows(table: str, column: str, value: str) -> int:
    sql = text(
        f"DELETE FROM {_quote_identifier(table)} "
        f"WHERE {_quote_identifier(column)} = :value"
    )
    with get_db() as db:
        try:
            result = db.execute(sql, {"value": value})
            db.commit()
            return _rowcount(result)
        except Exception:
            db.rollback()
            raise


def _update_rows(table: str, column: str, value: str, replacement: str) -> int:
    quoted_column = _quote_identifier(column)
    sql = text(
        f"UPDATE {_quote_identifier(table)} "
        f"SET {quoted_column} = :replacement "
        f"WHERE {quoted_column} = :value"
    )
    with get_db() as db:
        try:
            result = db.execute(sql, {"value": value, "replacement": replacement})
            db.commit()
            return _rowcount(result)
        except Exception:
            db.rollback()
            raise


def _delete_table_with_count(table: str, column: str, user_id: str) -> int:
    before = _count_rows(table, column, user_id)
    deleted = _delete_rows(table, column, user_id)
    return deleted or before


def _anonymize_table_with_count(table: str, column: str, user_id: str) -> int:
    before = _count_rows(table, column, user_id)
    updated = _update_rows(table, column, user_id, f"anonymized:{user_id}")
    return updated or before


def _safe_delete_table(table: str, column: str, user_id: str) -> int:
    try:
        deleted = _delete_table_with_count(table, column, user_id)
        log.info(
            "DSAR erase hard-deleted %d rows from %s.%s",
            deleted,
            table,
            column,
        )
        return deleted
    except Exception as exc:
        log.exception(
            "DSAR erase failed for hard-delete table %s.%s: %s",
            table,
            column,
            exc,
        )
        return 0


def _safe_delete_table_with_errors(
    table: str, column: str, user_id: str, errors: list[dict[str, str]]
) -> int:
    try:
        deleted = _delete_table_with_count(table, column, user_id)
        log.info(
            "DSAR erase hard-deleted %d rows from %s.%s",
            deleted,
            table,
            column,
        )
        return deleted
    except Exception as exc:
        errors.append({"step": f"delete:{table}.{column}", "error": str(exc)})
        log.exception(
            "DSAR erase failed for hard-delete table %s.%s: %s",
            table,
            column,
            exc,
        )
        return 0


def _safe_anonymize_table(table: str, column: str, user_id: str) -> int:
    try:
        updated = _anonymize_table_with_count(table, column, user_id)
        log.info(
            "DSAR erase anonymized %d rows in %s.%s",
            updated,
            table,
            column,
        )
        return updated
    except Exception as exc:
        log.exception(
            "DSAR erase failed for anonymize table %s.%s: %s",
            table,
            column,
            exc,
        )
        return 0


def _safe_anonymize_table_with_errors(
    table: str, column: str, user_id: str, errors: list[dict[str, str]]
) -> int:
    try:
        updated = _anonymize_table_with_count(table, column, user_id)
        log.info(
            "DSAR erase anonymized %d rows in %s.%s",
            updated,
            table,
            column,
        )
        return updated
    except Exception as exc:
        errors.append({"step": f"anonymize:{table}.{column}", "error": str(exc)})
        log.exception(
            "DSAR erase failed for anonymize table %s.%s: %s",
            table,
            column,
            exc,
        )
        return 0


def _get_user_email(user_id: str) -> Optional[str]:
    try:
        rows = _select_rows("user", "id", user_id)
        if rows:
            email = rows[0].get("email")
            return str(email) if email else None
    except Exception as exc:
        log.exception("DSAR erase failed to read user email for %s: %s", user_id, exc)
    return None


def _anonymize_audit_email(
    user_email: Optional[str], errors: list[dict[str, str]]
) -> int:
    if not user_email:
        return 0
    try:
        updated = _update_rows("audit_log", "user_email", user_email, "anonymized")
        log.info("DSAR erase anonymized %d audit_log.user_email rows", updated)
        return updated
    except Exception as exc:
        errors.append({"step": "anonymize:audit_log.user_email", "error": str(exc)})
        log.exception("DSAR erase failed anonymizing audit_log.user_email: %s", exc)
        return 0


def _write_backup_zip(user_id: str) -> str:
    archive = export_user_data(user_id)
    prefix = f"bcgpt-dsar-{_safe_filename(user_id)}-"
    with tempfile.NamedTemporaryFile(
        prefix=prefix, suffix=".zip", delete=False
    ) as backup:
        backup.write(archive)
        path = backup.name
    log.info("DSAR erase safety export for user %s written to %s", user_id, path)
    return path


def _delete_chats(user_id: str) -> dict[str, int]:
    counts = {"chat": 0, "shared_chat": 0}
    try:
        chat_rows = _select_rows("chat", "user_id", user_id)
        counts["chat"] = len(chat_rows)
        for row in chat_rows:
            chat_id = row.get("id")
            if chat_id:
                counts["shared_chat"] += _count_rows(
                    "chat", "user_id", f"shared-{chat_id}"
                )
    except Exception as exc:
        log.exception("DSAR erase failed to count chats for user %s: %s", user_id, exc)

    try:
        if Chats.delete_shared_chats_by_user_id(user_id):
            log.info(
                "DSAR erase deleted %d shared chat rows for user %s",
                counts["shared_chat"],
                user_id,
            )
        else:
            log.warning("DSAR erase shared chat delete returned False for %s", user_id)
            counts["shared_chat"] = 0
    except Exception as exc:
        log.exception(
            "DSAR erase failed deleting shared chats for %s: %s", user_id, exc
        )
        counts["shared_chat"] = 0

    try:
        if Chats.delete_chats_by_user_id(user_id):
            log.info(
                "DSAR erase deleted %d primary chat rows for user %s",
                counts["chat"],
                user_id,
            )
        else:
            log.warning("DSAR erase chat delete returned False for %s", user_id)
            counts["chat"] = 0
    except Exception as exc:
        log.exception("DSAR erase failed deleting chats for %s: %s", user_id, exc)
        counts["chat"] = 0

    return counts


def _load_storage_provider() -> Any:
    try:
        from bcgpt.storage.provider import Storage

        return Storage
    except Exception as exc:
        log.exception("DSAR erase could not load storage provider: %s", exc)
        return None


def _delete_user_files(
    user_id: str, errors: Optional[list[dict[str, str]]] = None
) -> int:
    try:
        files = Files.get_files_by_user_id(user_id)
    except Exception as exc:
        log.exception("DSAR erase failed to list files for user %s: %s", user_id, exc)
        return 0

    storage = _load_storage_provider()
    deleted = 0

    for file in files:
        file_id = getattr(file, "id", None)
        file_path = getattr(file, "path", None)
        physical_deleted = True

        if storage and file_path:
            try:
                storage.delete_file(file_path)
                log.info("DSAR erase deleted physical file %s", file_path)
            except Exception as exc:
                physical_deleted = False
                if errors is not None:
                    errors.append(
                        {"step": f"delete_file_storage:{file_id}", "error": str(exc)}
                    )
                log.exception(
                    "DSAR erase failed deleting physical file %s: %s", file_path, exc
                )

        if not physical_deleted:
            log.warning(
                "DSAR erase retained file record %s because physical deletion failed",
                file_id,
            )
            continue

        try:
            if file_id and Files.delete_file_by_id(file_id):
                deleted += 1
                log.info(
                    "DSAR erase deleted file record %s for user %s", file_id, user_id
                )
            elif file_id:
                log.warning(
                    "DSAR erase file record delete returned False for %s", file_id
                )
        except Exception as exc:
            if errors is not None:
                errors.append(
                    {"step": f"delete_file_record:{file_id}", "error": str(exc)}
                )
            log.exception("DSAR erase failed deleting file record %s: %s", file_id, exc)

    return deleted


def _disable_user_mfa(user_id: str) -> int:
    try:
        count = _count_rows("user_mfa", "user_id", user_id)
    except Exception as exc:
        log.exception("DSAR erase failed counting MFA records for %s: %s", user_id, exc)
        count = 0

    try:
        if UserMFAs.disable(user_id):
            log.info("DSAR erase disabled MFA for user %s", user_id)
            return count
        log.warning("DSAR erase MFA disable returned False for %s", user_id)
    except Exception as exc:
        log.exception("DSAR erase failed disabling MFA for %s: %s", user_id, exc)
    return 0


def _remove_group_memberships(user_id: str) -> int:
    try:
        memberships = Groups.get_groups_by_member_id(user_id)
        count = len(memberships)
    except Exception as exc:
        log.exception(
            "DSAR erase failed counting group memberships for %s: %s", user_id, exc
        )
        count = 0

    try:
        if Groups.remove_user_from_all_groups(user_id):
            log.info("DSAR erase removed user %s from %d groups", user_id, count)
            return count
        log.warning(
            "DSAR erase group membership removal returned False for %s", user_id
        )
    except Exception as exc:
        log.exception(
            "DSAR erase failed removing group memberships for %s: %s", user_id, exc
        )
    return 0


def export_user_data(user_id: str) -> bytes:
    """
    Export ALL user data as a ZIP archive containing JSON files.

    Returns ZIP file bytes suitable for StreamingResponse.
    """
    log.info("DSAR export started for user %s", user_id)
    buffer = io.BytesIO()
    row_counts: dict[str, int] = {}
    errors: dict[str, str] = {}

    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table, column in _EXPORT_TABLES:
            filename = f"{table}.json"
            try:
                rows = _select_rows(table, column, user_id)
                row_counts[table] = len(rows)
                log.info(
                    "DSAR export collected %d rows from %s.%s",
                    len(rows),
                    table,
                    column,
                )
            except Exception as exc:
                rows = []
                row_counts[table] = 0
                errors[table] = str(exc)
                log.exception(
                    "DSAR export failed for table %s.%s: %s", table, column, exc
                )

            archive.writestr(
                filename,
                json.dumps(rows, ensure_ascii=False, indent=2),
            )

        try:
            shared_chats = _select_shared_chat_rows(user_id)
            row_counts["shared_chats"] = len(shared_chats)
            log.info("DSAR export collected %d shared chat rows", len(shared_chats))
        except Exception as exc:
            shared_chats = []
            row_counts["shared_chats"] = 0
            errors["shared_chats"] = str(exc)
            log.exception("DSAR export failed for shared chats: %s", exc)

        archive.writestr(
            "shared_chats.json",
            json.dumps(shared_chats, ensure_ascii=False, indent=2),
        )

        try:
            group_memberships = _select_group_memberships(user_id)
            row_counts["group_memberships"] = len(group_memberships)
            log.info(
                "DSAR export collected %d group membership rows",
                len(group_memberships),
            )
        except Exception as exc:
            group_memberships = []
            row_counts["group_memberships"] = 0
            errors["group_memberships"] = str(exc)
            log.exception("DSAR export failed for group memberships: %s", exc)

        archive.writestr(
            "group_memberships.json",
            json.dumps(group_memberships, ensure_ascii=False, indent=2),
        )

        manifest = {
            "export_date": _utc_now(),
            "user_id": user_id,
            "table_names": list(row_counts.keys()),
            "row_counts": row_counts,
            "errors": errors,
        }
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    log.info("DSAR export completed for user %s", user_id)
    return buffer.getvalue()


def cascade_erase_user_data(user_id: str) -> dict:
    """
    Permanently delete ALL user data across every table.

    This goes far beyond the existing Users.delete_user_by_id() which only
    cascades to chats and group memberships.

    Process:
    1. Export user data first (safety backup)
    2. Hard-delete user-owned content tables
    3. Anonymize compliance/audit tables (replace user_id with "anonymized:{user_id}")
    4. Delete chat data (existing cascade)
    5. Delete file records + physical files
    6. Delete user MFA records
    7. Remove from group memberships
    8. Delete auth + user records

    Returns dict with per-table deletion counts.
    """
    log.info("DSAR cascade erasure started for user %s", user_id)
    counts: dict[str, Any] = {"_status": "completed", "_errors": []}
    errors: list[dict[str, str]] = counts["_errors"]
    user_email = _get_user_email(user_id)

    try:
        counts["_backup_path"] = _write_backup_zip(user_id)
    except Exception as exc:
        counts["_status"] = "partial_failed"
        errors.append({"step": "backup_export", "error": str(exc)})
        log.exception("DSAR erase safety export failed for user %s: %s", user_id, exc)

    for table, column in _HARD_DELETE_TABLES:
        counts[table] = _safe_delete_table_with_errors(table, column, user_id, errors)

    for table, column in _LEGACY_HARD_DELETE_TABLES:
        counts[table] = _safe_delete_table_with_errors(table, column, user_id, errors)

    for table, column in _ANONYMIZE_TABLES:
        counts[table] = _safe_anonymize_table_with_errors(
            table, column, user_id, errors
        )

    counts["audit_log_user_email"] = _anonymize_audit_email(user_email, errors)

    counts.update(_delete_chats(user_id))
    counts["file"] = _delete_user_files(user_id, errors)
    counts["user_mfa"] = _disable_user_mfa(user_id)
    counts["group_membership"] = _remove_group_memberships(user_id)
    counts["group"] = _safe_delete_table_with_errors(
        "group", "user_id", user_id, errors
    )
    counts["auth"] = _safe_delete_table_with_errors("auth", "id", user_id, errors)
    counts["user"] = _safe_delete_table_with_errors("user", "id", user_id, errors)

    if errors:
        counts["_status"] = "partial_failed"

    log.info("DSAR cascade erasure completed for user %s: %s", user_id, counts)
    return counts


def _query_ai_interaction_logs(
    user_id: str, chat_id: Optional[str], limit: int
) -> list[dict[str, Any]]:
    where = [
        f"{_quote_identifier('user_id')} = :user_id",
        f"{_quote_identifier('action')} = :action",
    ]
    params: dict[str, Any] = {"user_id": user_id, "action": "AI_INTERACTION"}
    if chat_id:
        where.append(f"{_quote_identifier('resource_id')} = :chat_id")
        params["chat_id"] = chat_id

    sql = text(
        f"SELECT * FROM {_quote_identifier('audit_log')} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {_quote_identifier('timestamp')} DESC LIMIT {limit}"
    )
    with get_db() as db:
        rows = db.execute(sql, params).mappings().all()
        return _rows_to_dicts(rows)


def _query_rag_provenance(
    user_id: str, chat_id: Optional[str], limit: int
) -> list[dict[str, Any]]:
    where = [f"{_quote_identifier('user_id')} = :user_id"]
    params: dict[str, Any] = {"user_id": user_id}
    if chat_id:
        where.append(f"{_quote_identifier('related_chat_id')} = :chat_id")
        params["chat_id"] = chat_id

    sql = text(
        f"SELECT * FROM {_quote_identifier('ai_rag_provenance')} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {_quote_identifier('timestamp')} DESC LIMIT {limit}"
    )
    with get_db() as db:
        rows = db.execute(sql, params).mappings().all()
        return _rows_to_dicts(rows)


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _quality_summary(scores: list[dict[str, float]]) -> dict[str, Any]:
    if not scores:
        return {
            "available": False,
            "averages": {},
            "samples": [],
        }

    totals: dict[str, list[float]] = {}
    for sample in scores:
        for key, value in sample.items():
            totals.setdefault(key, []).append(value)

    averages = {
        key: round(sum(values) / len(values), 4)
        for key, values in totals.items()
        if values
    }
    return {
        "available": True,
        "averages": averages,
        "samples": scores,
    }


def generate_explanation(
    user_id: str, chat_id: Optional[str] = None, limit: int = 10
) -> dict:
    """
    Generate an explanation of automated decisions for a user.

    Pulls AI interaction audit logs, RAG provenance records, and quality
    pipeline results to explain what data influenced AI responses.

    Returns a structured explanation suitable for PIPA Art. 37-2 response.
    """
    limit = max(1, min(int(limit or 10), 100))
    log.info(
        "DSAR automated-decision explanation started for user %s chat_id=%s limit=%d",
        user_id,
        chat_id,
        limit,
    )

    try:
        audit_rows = _query_ai_interaction_logs(user_id, chat_id, limit)
    except Exception as exc:
        audit_rows = []
        log.exception("DSAR explanation failed querying audit_log: %s", exc)

    try:
        provenance_rows = _query_rag_provenance(user_id, chat_id, limit)
    except Exception as exc:
        provenance_rows = []
        log.exception("DSAR explanation failed querying ai_rag_provenance: %s", exc)

    model_counts: Counter[str] = Counter()
    quality_samples: list[dict[str, float]] = []
    automated_decisions: list[dict[str, Any]] = []
    audit_rag_sources = 0
    total_tokens = 0
    tool_calls = 0

    quality_keys = (
        "quality_score",
        "overall_quality_score",
        "grounding_score",
        "doc_quality_score",
        "entailment_score",
    )

    for row in audit_rows:
        details = _coerce_json(row.get("details"), {})
        if not isinstance(details, dict):
            details = {}

        model_id = details.get("model_id") or "unknown"
        model_counts[str(model_id)] += 1
        audit_rag_sources += _int_value(details.get("rag_source_count"))
        total_tokens += _int_value(details.get("total_tokens"))
        tool_calls += _int_value(details.get("tool_call_count"))

        quality = {
            key: value
            for key in quality_keys
            if (value := _float_value(details.get(key))) is not None
        }
        if quality:
            quality_samples.append(quality)

        automated_decisions.append(
            {
                "timestamp": row.get("timestamp"),
                "chat_id": row.get("resource_id"),
                "message_id": row.get("resource_name"),
                "model_id": model_id,
                "provider": details.get("provider"),
                "prompt_tokens": details.get("prompt_tokens"),
                "completion_tokens": details.get("completion_tokens"),
                "total_tokens": details.get("total_tokens"),
                "rag_source_count": details.get("rag_source_count", 0),
                "tool_call_count": details.get("tool_call_count", 0),
                "web_search_used": bool(details.get("web_search_used")),
                "output_sanitized": bool(details.get("output_sanitized")),
                "latency_ms": details.get("latency_ms"),
                "streaming": bool(details.get("streaming")),
            }
        )

    provenance_summaries: list[dict[str, Any]] = []
    provenance_rag_sources = 0

    for row in provenance_rows:
        model_name = row.get("model_name") or "unknown"
        model_counts[str(model_name)] += 1
        chunks = _coerce_json(row.get("retrieved_chunks"), [])
        if not isinstance(chunks, list):
            chunks = []
        source_count = len(chunks)
        provenance_rag_sources += source_count
        total_tokens += _int_value(row.get("total_tokens"))

        provenance_summaries.append(
            {
                "timestamp": row.get("timestamp"),
                "chat_id": row.get("related_chat_id"),
                "model_name": model_name,
                "model_version": row.get("model_version"),
                "prompt_hash": row.get("prompt_hash"),
                "response_hash": row.get("response_hash"),
                "query_text": row.get("query_text"),
                "retrieved_source_count": source_count,
                "retrieved_chunks": chunks,
                "total_tokens": row.get("total_tokens"),
            }
        )

    summary = {
        "ai_interaction_count": len(audit_rows),
        "rag_provenance_count": len(provenance_rows),
        "models_used": dict(model_counts),
        "rag_sources_retrieved": {
            "audit_signals": audit_rag_sources,
            "provenance_records": provenance_rag_sources,
            "total_observed": audit_rag_sources + provenance_rag_sources,
        },
        "tool_call_count": tool_calls,
        "total_tokens_observed": total_tokens,
        "quality_scores": _quality_summary(quality_samples),
    }

    explanation = {
        "plain_language": (
            "BCGPT generated automated responses using the models listed in "
            "summary.models_used. When retrieval-augmented generation was used, "
            "the system retrieved the sources listed in rag_provenance and used "
            "them as context for the response. Audit rows show operational "
            "signals such as token usage, tool calls, web search usage, output "
            "sanitization, and latency."
        ),
        "data_influencing_responses": [
            "User prompts and conversation context for the selected chat scope.",
            "Retrieved knowledge/RAG chunks listed in rag_provenance.",
            "Configured model/provider behavior and available tool/web-search signals.",
            "Safety and output-filter decisions recorded in AI interaction audit details.",
        ],
        "automated_processing_objection": (
            "The user may object to automated processing or request human review; "
            "operators should use this explanation with the exported records to "
            "evaluate the request under PIPA Art. 37-2."
        ),
    }

    result = {
        "user_id": user_id,
        "chat_id": chat_id,
        "generated_at": _utc_now(),
        "scope": {"limit": limit},
        "summary": summary,
        "explanation": explanation,
        "automated_decisions": automated_decisions,
        "rag_provenance": provenance_summaries,
    }

    log.info("DSAR automated-decision explanation completed for user %s", user_id)
    return result
