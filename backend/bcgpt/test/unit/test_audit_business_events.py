"""Unit tests for log_business_event (P2.3)."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.models.audit_log import AuditLogForm
from bcgpt.utils import audit as audit_mod


class _FakeTable:
    def __init__(self):
        self.inserted = []

    def insert_log(self, form):
        self.inserted.append(form)


def test_log_business_event_persists(monkeypatch):
    fake = _FakeTable()
    monkeypatch.setattr("bcgpt.models.audit_log.AuditLogsTable", lambda: fake)

    audit_mod.log_business_event(
        action="file.added_to_kb",
        resource_type="knowledge",
        user=SimpleNamespace(id="u1", email="u@e"),
        resource_id="kb-1",
        details={"file_id": "f1"},
    )

    assert len(fake.inserted) == 1
    form = fake.inserted[0]
    assert isinstance(form, AuditLogForm)
    assert form.action == "file.added_to_kb"
    assert form.resource_type == "knowledge"
    assert form.user_id == "u1"
    assert form.user_email == "u@e"
    assert form.resource_id == "kb-1"
    assert form.audit_details == {"file_id": "f1"}
    assert form.category == "rag"


def test_log_business_event_defaults_optional_fields(monkeypatch):
    fake = _FakeTable()
    monkeypatch.setattr("bcgpt.models.audit_log.AuditLogsTable", lambda: fake)

    audit_mod.log_business_event(action="kb.deleted", resource_type="knowledge")

    form = fake.inserted[0]
    assert form.user_id is None
    assert form.resource_id is None
    assert form.severity == "INFO"


def test_log_business_event_swallows_errors(monkeypatch):
    # audit must never break the calling operation
    class _Boom:
        def insert_log(self, form):
            raise RuntimeError("db down")

    monkeypatch.setattr("bcgpt.models.audit_log.AuditLogsTable", lambda: _Boom())
    audit_mod.log_business_event(action="x", resource_type="y")  # must not raise
