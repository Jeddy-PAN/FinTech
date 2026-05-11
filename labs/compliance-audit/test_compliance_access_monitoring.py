from __future__ import annotations

from datetime import datetime, timezone

import pytest

from compliance_access_monitoring import (
    FINDING_REPEATED_DENIED_ACCESS,
    FINDING_REPEATED_PAYLOAD_VIEW,
    FINDING_UNAUTHORIZED_EXPORT_ATTEMPT,
    SEVERITY_HIGH,
    AccessMonitoringRule,
    detect_access_anomalies,
)
from compliance_audit import AuditAccessEvent, ComplianceAuditError


def test_detects_repeated_denied_access_within_window() -> None:
    findings = detect_access_anomalies(
        (
            _event("viewer_001", "view_audit_payload", "denied", 0),
            _event("viewer_001", "export_audit_report", "denied", 5),
            _event("viewer_001", "view_audit_payload", "denied", 10),
        )
    )

    assert len(findings) == 2
    denied_finding = _finding(findings, FINDING_REPEATED_DENIED_ACCESS)
    assert denied_finding.actor == "viewer_001"
    assert denied_finding.severity == SEVERITY_HIGH
    assert denied_finding.event_count == 3
    assert "denied access" in denied_finding.reason


def test_does_not_detect_repeated_denied_access_outside_window() -> None:
    findings = detect_access_anomalies(
        (
            _event("viewer_001", "view_audit_payload", "denied", 0),
            _event("viewer_001", "view_audit_payload", "denied", 20),
            _event("viewer_001", "view_audit_payload", "denied", 40),
        )
    )

    assert FINDING_REPEATED_DENIED_ACCESS not in [
        finding.finding_type for finding in findings
    ]


def test_detects_non_manager_export_attempt() -> None:
    findings = detect_access_anomalies(
        (
            _event("analyst_001", "export_audit_report", "denied", 0),
            _event("manager_001", "export_audit_report", "granted", 1),
        )
    )

    assert [finding.finding_type for finding in findings] == [
        FINDING_UNAUTHORIZED_EXPORT_ATTEMPT
    ]
    assert findings[0].actor == "analyst_001"
    assert findings[0].event_count == 1


def test_detects_repeated_payload_views() -> None:
    events = tuple(
        _event("analyst_001", "view_audit_payload", "granted", minute)
        for minute in (0, 2, 4, 6, 8)
    )

    findings = detect_access_anomalies(events)

    assert [finding.finding_type for finding in findings] == [
        FINDING_REPEATED_PAYLOAD_VIEW
    ]
    assert findings[0].actor == "analyst_001"
    assert findings[0].event_count == 5
    assert findings[0].events[0].occurred_at == datetime(
        2026, 5, 8, 11, 0, tzinfo=timezone.utc
    )


def test_custom_manager_actor_prefix_can_prevent_export_false_positive() -> None:
    findings = detect_access_anomalies(
        (_event("lead_001", "export_audit_report", "granted", 0),),
        manager_actor_prefixes=("lead_",),
    )

    assert findings == ()


def test_rejects_invalid_monitoring_rule() -> None:
    with pytest.raises(ComplianceAuditError, match="threshold"):
        detect_access_anomalies(
            (),
            rules=(
                AccessMonitoringRule(
                    rule_id="invalid",
                    finding_type=FINDING_REPEATED_DENIED_ACCESS,
                    threshold=0,
                    window_minutes=15,
                    severity=SEVERITY_HIGH,
                ),
            ),
        )


def _finding(findings, finding_type):
    for finding in findings:
        if finding.finding_type == finding_type:
            return finding
    raise AssertionError(f"Missing finding: {finding_type}")


def _event(
    actor: str,
    permission: str,
    outcome: str,
    minute: int,
) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.granted" if outcome == "granted" else "audit_access.denied",
        actor=actor,
        permission=permission,
        target="audit_events",
        outcome=outcome,
        occurred_at=datetime(2026, 5, 8, 11, minute, tzinfo=timezone.utc),
        reason=None,
    )
