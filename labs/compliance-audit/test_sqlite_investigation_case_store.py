from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_audit import AuditAccessEvent, ComplianceAuditError
from compliance_investigation_cases import (
    INVESTIGATION_INVESTIGATING,
    INVESTIGATION_OPEN,
    INVESTIGATION_RESOLVED,
    AccessAnomalyInvestigationService,
)
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore


def test_store_can_save_and_load_investigation_case() -> None:
    store = SQLiteInvestigationCaseStore(_database_path())
    try:
        investigation_case = _open_case()

        store.save_case(investigation_case)

        loaded = store.get_case(investigation_case.case_id)
        assert loaded == investigation_case
        assert store.cases == (investigation_case,)
        assert store.open_cases == (investigation_case,)
    finally:
        _close_and_remove(store)


def test_store_can_update_case_status_to_resolved() -> None:
    store = SQLiteInvestigationCaseStore(_database_path())
    service = AccessAnomalyInvestigationService()
    try:
        open_case = service.create_case(
            _finding(actor="viewer_001"),
            opened_by="compliance_lead_001",
            created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
        )
        store.save_case(open_case)
        investigating_case = service.start_investigation(
            open_case.case_id,
            assigned_to="investigator_001",
            started_at=datetime(2026, 5, 8, 12, 10, tzinfo=timezone.utc),
        )
        store.save_case(investigating_case)
        resolved_case = service.resolve(
            investigating_case.case_id,
            closed_by="investigator_001",
            reason="Reviewed sample access anomaly",
            closed_at=datetime(2026, 5, 8, 13, 0, tzinfo=timezone.utc),
        )
        store.save_case(resolved_case)

        loaded = store.get_case(open_case.case_id)
        assert loaded.status == INVESTIGATION_RESOLVED
        assert loaded.closed_by == "investigator_001"
        assert loaded.resolution_reason == "Reviewed sample access anomaly"
        assert store.open_cases == ()
    finally:
        _close_and_remove(store)


def test_store_can_query_cases_by_status_assignee_and_actor() -> None:
    store = SQLiteInvestigationCaseStore(_database_path())
    service = AccessAnomalyInvestigationService()
    try:
        first_case = service.create_case(
            _finding(actor="viewer_001"),
            opened_by="compliance_lead_001",
            created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
        )
        second_case = service.create_case(
            _finding(actor="analyst_001"),
            opened_by="compliance_lead_001",
            created_at=datetime(2026, 5, 8, 12, 5, tzinfo=timezone.utc),
        )
        investigating_case = service.start_investigation(
            first_case.case_id,
            assigned_to="investigator_001",
            started_at=datetime(2026, 5, 8, 12, 10, tzinfo=timezone.utc),
        )
        store.save_case(investigating_case)
        store.save_case(second_case)

        assert store.query_cases(status=INVESTIGATION_INVESTIGATING) == (
            investigating_case,
        )
        assert store.query_cases(assigned_to="investigator_001") == (
            investigating_case,
        )
        assert store.query_cases(actor="analyst_001") == (second_case,)
        assert store.query_cases(statuses=(INVESTIGATION_OPEN,)) == (second_case,)
    finally:
        _close_and_remove(store)


def test_store_can_reopen_database_and_read_case_with_events() -> None:
    database_path = _database_path()
    store = SQLiteInvestigationCaseStore(database_path)
    investigation_case = _open_case()
    try:
        store.save_case(investigation_case)
    finally:
        store.close()

    reopened = SQLiteInvestigationCaseStore(database_path)
    try:
        loaded = reopened.get_case(investigation_case.case_id)
        assert loaded.case_id == investigation_case.case_id
        assert loaded.finding.events == investigation_case.finding.events
        assert loaded.finding.event_count == 3
    finally:
        _close_and_remove(reopened)


def test_store_rejects_naive_case_timestamp() -> None:
    store = SQLiteInvestigationCaseStore(_database_path())
    try:
        investigation_case = replace(
            _open_case(),
            created_at=datetime(2026, 5, 8, 12, 0),
        )
        with pytest.raises(ComplianceAuditError, match="timezone-aware"):
            store.save_case(investigation_case)
    finally:
        _close_and_remove(store)


def _open_case(
    *,
    created_at: datetime = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
):
    service = AccessAnomalyInvestigationService()
    return service.create_case(
        _finding(actor="viewer_001"),
        opened_by="compliance_lead_001",
        created_at=created_at,
    )


def _finding(*, actor: str) -> AccessAnomalyFinding:
    events = (
        _access_event(actor=actor, minute=0),
        _access_event(actor=actor, minute=5),
        _access_event(actor=actor, minute=10),
    )
    return AccessAnomalyFinding(
        finding_type="repeated_denied_access",
        actor=actor,
        severity="high",
        event_count=3,
        reason="Actor has 3 denied access events within 15 minutes",
        first_occurred_at=events[0].occurred_at,
        last_occurred_at=events[-1].occurred_at,
        events=events,
    )


def _access_event(*, actor: str, minute: int) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.denied",
        actor=actor,
        permission="view_audit_payload",
        target="audit_events.payload",
        outcome="denied",
        occurred_at=datetime(2026, 5, 8, 11, minute, tzinfo=timezone.utc),
        reason=None,
    )


def _database_path() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory / f"investigation-cases-{uuid4()}.db"


def _close_and_remove(store: SQLiteInvestigationCaseStore) -> None:
    database_path = store.database_path
    store.close()
    if str(database_path) != ":memory:" and database_path.exists():
        database_path.unlink()
