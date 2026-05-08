from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from compliance_audit import AuditAccessEvent, AuditAccessRecorder, ComplianceAuditError
from sqlite_access_audit_store import SQLiteAccessAuditStore


def test_store_can_save_and_load_access_event() -> None:
    store = SQLiteAccessAuditStore(_database_path())
    try:
        event = _access_event(
            actor="viewer_001",
            permission="view_audit_events",
            outcome="granted",
            occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
        )

        store.save_event(event)

        assert store.access_events == (event,)
    finally:
        _close_and_remove(store)


def test_store_can_save_events_from_recorder() -> None:
    store = SQLiteAccessAuditStore(_database_path())
    recorder = AuditAccessRecorder.create()
    recorder.record(
        event_type="audit_access.granted",
        actor="viewer_001",
        permission="view_audit_events",
        target="audit_events",
        outcome="granted",
        occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
    )
    recorder.record(
        event_type="audit_payload.hidden",
        actor="viewer_001",
        permission="view_audit_payload",
        target="audit_events.payload",
        outcome="denied",
        occurred_at=datetime(2026, 5, 8, 11, 1, tzinfo=timezone.utc),
        reason="User viewer_001 is missing permission: view_audit_payload",
    )

    try:
        store.save_events(recorder.events)

        assert [event.event_type for event in store.access_events] == [
            "audit_access.granted",
            "audit_payload.hidden",
        ]
        assert store.access_events[1].reason is not None
    finally:
        _close_and_remove(store)


def test_store_queries_by_actor_permission_outcome_and_time_window() -> None:
    store = SQLiteAccessAuditStore(_database_path())
    try:
        store.save_events(
            (
                _access_event(
                    actor="viewer_001",
                    permission="view_audit_events",
                    outcome="granted",
                    occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
                ),
                _access_event(
                    actor="viewer_001",
                    permission="view_audit_payload",
                    outcome="denied",
                    occurred_at=datetime(2026, 5, 8, 11, 1, tzinfo=timezone.utc),
                ),
                _access_event(
                    actor="analyst_001",
                    permission="view_audit_payload",
                    outcome="granted",
                    occurred_at=datetime(2026, 5, 8, 11, 5, tzinfo=timezone.utc),
                ),
            )
        )

        denied_payload_events = store.query_access_events(
            actor="viewer_001",
            permission="view_audit_payload",
            outcome="denied",
            occurred_from=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
            occurred_to=datetime(2026, 5, 8, 11, 2, tzinfo=timezone.utc),
        )

        assert len(denied_payload_events) == 1
        assert denied_payload_events[0].actor == "viewer_001"
        assert denied_payload_events[0].permission == "view_audit_payload"
        assert denied_payload_events[0].outcome == "denied"
    finally:
        _close_and_remove(store)


def test_store_can_reopen_database_and_read_access_events() -> None:
    database_path = _database_path()
    store = SQLiteAccessAuditStore(database_path)
    try:
        store.save_event(
            _access_event(
                actor="manager_001",
                permission="export_audit_report",
                outcome="granted",
                occurred_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
            )
        )
    finally:
        store.close()

    reopened = SQLiteAccessAuditStore(database_path)
    try:
        assert [event.permission for event in reopened.access_events] == [
            "export_audit_report"
        ]
        assert reopened.access_events[0].actor == "manager_001"
    finally:
        _close_and_remove(reopened)


def test_store_rejects_naive_access_event_timestamp() -> None:
    store = SQLiteAccessAuditStore(_database_path())
    try:
        with pytest.raises(ComplianceAuditError, match="timezone-aware"):
            store.save_event(
                _access_event(
                    actor="viewer_001",
                    permission="view_audit_events",
                    outcome="granted",
                    occurred_at=datetime(2026, 5, 8, 11, 0),
                )
            )
    finally:
        _close_and_remove(store)


def _access_event(
    *,
    actor: str,
    permission: str,
    outcome: str,
    occurred_at: datetime,
) -> AuditAccessEvent:
    event_type = (
        "audit_access.granted" if outcome == "granted" else "audit_access.denied"
    )
    return AuditAccessEvent(
        event_type=event_type,
        actor=actor,
        permission=permission,
        target="audit_events",
        outcome=outcome,
        occurred_at=occurred_at,
        reason=None,
    )


def _database_path() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory / f"access-audit-{uuid4()}.db"


def _close_and_remove(store: SQLiteAccessAuditStore) -> None:
    database_path = store.database_path
    store.close()
    if str(database_path) != ":memory:" and database_path.exists():
        database_path.unlink()
