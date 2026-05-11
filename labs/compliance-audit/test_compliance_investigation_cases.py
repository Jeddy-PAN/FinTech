from __future__ import annotations

from datetime import datetime, timezone

import pytest

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_audit import AuditAccessEvent, ComplianceAuditError
from compliance_investigation_cases import (
    INVESTIGATION_FALSE_POSITIVE,
    INVESTIGATION_INVESTIGATING,
    INVESTIGATION_OPEN,
    INVESTIGATION_RESOLVED,
    AccessAnomalyInvestigationService,
    investigation_case_id,
)


def test_investigation_service_creates_case_from_finding() -> None:
    finding = _finding()
    service = AccessAnomalyInvestigationService()

    investigation_case = service.create_case(
        finding,
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    assert investigation_case.case_id == investigation_case_id(finding)
    assert investigation_case.status == INVESTIGATION_OPEN
    assert investigation_case.opened_by == "compliance_lead_001"
    assert investigation_case.finding == finding
    assert service.open_cases == (investigation_case,)
    assert [event.event_type for event in service.audit_events] == [
        "access_investigation_case.created"
    ]
    assert service.audit_events[0].actor == "compliance_lead_001"
    assert service.audit_events[0].aggregate_id == investigation_case.case_id
    assert '"status":"open"' in service.audit_events[0].payload


def test_investigation_service_reuses_existing_case_for_same_finding() -> None:
    finding = _finding()
    service = AccessAnomalyInvestigationService()

    first_case = service.create_case(
        finding,
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )
    second_case = service.create_case(
        finding,
        opened_by="compliance_lead_002",
        created_at=datetime(2026, 5, 8, 12, 5, tzinfo=timezone.utc),
    )

    assert second_case == first_case
    assert service.cases == (first_case,)


def test_investigation_service_can_start_and_resolve_case() -> None:
    service = AccessAnomalyInvestigationService()
    investigation_case = service.create_case(
        _finding(),
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    investigating_case = service.start_investigation(
        investigation_case.case_id,
        assigned_to="investigator_001",
        started_at=datetime(2026, 5, 8, 12, 10, tzinfo=timezone.utc),
    )
    resolved_case = service.resolve(
        investigating_case.case_id,
        closed_by="investigator_001",
        reason="Confirmed access pattern was reviewed and contained",
        closed_at=datetime(2026, 5, 8, 13, 0, tzinfo=timezone.utc),
    )

    assert investigating_case.status == INVESTIGATION_INVESTIGATING
    assert investigating_case.assigned_to == "investigator_001"
    assert resolved_case.status == INVESTIGATION_RESOLVED
    assert resolved_case.closed_by == "investigator_001"
    assert resolved_case.resolution_reason == "Confirmed access pattern was reviewed and contained"
    assert service.open_cases == ()
    assert [event.event_type for event in service.audit_events] == [
        "access_investigation_case.created",
        "access_investigation_case.started",
        "access_investigation_case.resolved",
    ]
    assert service.audit_events[-1].actor == "investigator_001"
    assert service.audit_events[-1].reason == "Confirmed access pattern was reviewed and contained"


def test_investigation_service_can_mark_case_false_positive() -> None:
    service = AccessAnomalyInvestigationService()
    investigation_case = service.create_case(
        _finding(),
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )
    service.start_investigation(
        investigation_case.case_id,
        assigned_to="investigator_001",
        started_at=datetime(2026, 5, 8, 12, 10, tzinfo=timezone.utc),
    )

    closed_case = service.mark_false_positive(
        investigation_case.case_id,
        closed_by="investigator_001",
        reason="Known test account used in sample audit review",
        closed_at=datetime(2026, 5, 8, 12, 30, tzinfo=timezone.utc),
    )

    assert closed_case.status == INVESTIGATION_FALSE_POSITIVE
    assert closed_case.resolution_reason == "Known test account used in sample audit review"
    assert service.audit_events[-1].event_type == (
        "access_investigation_case.false_positive"
    )
    assert '"status":"false_positive"' in service.audit_events[-1].payload


def test_investigation_service_rejects_closing_open_case() -> None:
    service = AccessAnomalyInvestigationService()
    investigation_case = service.create_case(
        _finding(),
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ComplianceAuditError, match="must be investigating"):
        service.resolve(
            investigation_case.case_id,
            closed_by="investigator_001",
            reason="Cannot close before investigation starts",
            closed_at=datetime(2026, 5, 8, 12, 30, tzinfo=timezone.utc),
        )


def test_investigation_service_requires_timezone_aware_timestamps() -> None:
    service = AccessAnomalyInvestigationService()

    with pytest.raises(ComplianceAuditError, match="timezone-aware"):
        service.create_case(
            _finding(),
            opened_by="compliance_lead_001",
            created_at=datetime(2026, 5, 8, 12, 0),
        )


def test_investigation_service_requires_reason_when_closing() -> None:
    service = AccessAnomalyInvestigationService()
    investigation_case = service.create_case(
        _finding(),
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )
    service.start_investigation(
        investigation_case.case_id,
        assigned_to="investigator_001",
        started_at=datetime(2026, 5, 8, 12, 10, tzinfo=timezone.utc),
    )

    with pytest.raises(ComplianceAuditError, match="reason is required"):
        service.resolve(
            investigation_case.case_id,
            closed_by="investigator_001",
            reason=" ",
            closed_at=datetime(2026, 5, 8, 12, 30, tzinfo=timezone.utc),
        )


def _finding() -> AccessAnomalyFinding:
    events = (
        _access_event(minute=0),
        _access_event(minute=5),
        _access_event(minute=10),
    )
    return AccessAnomalyFinding(
        finding_type="repeated_denied_access",
        actor="viewer_001",
        severity="high",
        event_count=3,
        reason="Actor has 3 denied access events within 15 minutes",
        first_occurred_at=events[0].occurred_at,
        last_occurred_at=events[-1].occurred_at,
        events=events,
    )


def _access_event(*, minute: int) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.denied",
        actor="viewer_001",
        permission="view_audit_payload",
        target="audit_events.payload",
        outcome="denied",
        occurred_at=datetime(2026, 5, 8, 11, minute, tzinfo=timezone.utc),
        reason=None,
    )
