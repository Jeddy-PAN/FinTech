from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_audit import AuditAccessEvent
from platform_evidence_package import (
    build_platform_evidence_package,
    export_platform_evidence_package,
)
from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_PENDING,
    OperationApprovalRecord,
)
from platform_settlement_reconciliation_report import (
    PlatformSettlementReconciliationFinding,
)


def test_build_platform_evidence_package_collects_key_evidence_sources() -> None:
    package = build_platform_evidence_package(
        case_id="case_001",
        generated_by="compliance_analyst_001",
        generated_at=_now(),
        settlement_findings=(_settlement_finding(),),
        access_findings=(_access_finding(),),
        approval_records=(_approval_record(),),
        access_events=(
            _access_event(outcome="denied"),
            _access_event(outcome="granted"),
            _provider_webhook_event(outcome="granted", reason="event_id=evt_001 duplicate=False"),
        ),
        legal_hold=True,
        retention_policy_id="platform-evidence-hold",
    )

    assert package.package_id == "evidence_package:case_001"
    assert package.legal_hold is True
    assert package.retention_policy_id == "platform-evidence-hold"
    assert package.evidence_count == 5
    assert package.high_severity_count == 3
    assert package.source_counts == (
        ("access_audit", 1),
        ("access_monitoring", 1),
        ("operation_approval", 1),
        ("payment_provider", 1),
        ("settlement_reconciliation", 1),
    )
    assert [item.severity for item in package.items][:3] == ["high", "high", "high"]
    assert {item.evidence_type for item in package.items} == {
        "access_anomaly_finding",
        "denied_access_event",
        "operation_approval_record",
        "provider_webhook_event",
        "settlement_reconciliation_finding",
    }


def test_build_platform_evidence_package_collects_provider_webhook_events() -> None:
    package = build_platform_evidence_package(
        case_id="case_001",
        generated_by="compliance_analyst_001",
        generated_at=_now(),
        access_events=(
            _provider_webhook_event(
                outcome="granted",
                reason="event_id=evt_001 duplicate=False",
            ),
            _provider_webhook_event(
                outcome="granted",
                reason="event_id=evt_001 duplicate=True",
                occurred_at=datetime(2026, 6, 12, 9, 1, tzinfo=timezone.utc),
            ),
            _provider_webhook_event(
                outcome="denied",
                reason="Provider webhook timestamp is outside the replay window",
                occurred_at=datetime(2026, 6, 12, 9, 2, tzinfo=timezone.utc),
            ),
        ),
    )

    assert package.evidence_count == 3
    assert package.source_counts == (("payment_provider", 3),)
    assert {item.evidence_type for item in package.items} == {"provider_webhook_event"}
    assert [item.severity for item in package.items] == ["high", "medium", "low"]
    assert {item.subject_id for item in package.items} == {"evt_001", "provider_webhook"}
    assert any(
        item.summary == "Provider webhook denied: Provider webhook timestamp is outside the replay window"
        for item in package.items
    )


def test_build_platform_evidence_package_ignores_passed_settlement_and_granted_access() -> None:
    package = build_platform_evidence_package(
        case_id="case_001",
        generated_by="compliance_analyst_001",
        generated_at=_now(),
        settlement_findings=(
            PlatformSettlementReconciliationFinding(
                run_id="run_001",
                settlement_id="settlement_001",
                check_id="provider_settlement_amount_matches_internal_payment",
                status="passed",
                severity="info",
                message="Provider settlement amount matches internal amount: 100.00",
            ),
        ),
        access_events=(_access_event(outcome="granted"),),
    )

    assert package.evidence_count == 0
    assert package.source_counts == ()


def test_build_platform_evidence_package_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="case_id is required"):
        build_platform_evidence_package(
            case_id=" ",
            generated_by="compliance_analyst_001",
            generated_at=_now(),
        )

    with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
        build_platform_evidence_package(
            case_id="case_001",
            generated_by="compliance_analyst_001",
            generated_at=datetime(2026, 6, 12, 9, 0),
        )


def test_export_platform_evidence_package_writes_csv_and_escaped_html() -> None:
    output_directory = _output_directory()
    package = build_platform_evidence_package(
        case_id="case_<script>",
        generated_by="compliance_<script>",
        generated_at=_now(),
        settlement_findings=(
            _settlement_finding(
                run_id="run_<script>",
                message="Provider <script> mismatch",
            ),
        ),
        approval_records=(
            _approval_record(
                approval_id="approval_<script>",
                operation_id="run_<script>",
            ),
        ),
    )

    try:
        paths = export_platform_evidence_package(output_directory, package=package)

        items_csv = paths.items_csv.read_text(encoding="utf-8")
        summary_csv = paths.summary_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert paths.items_csv.name == "platform_evidence_package_items.csv"
        assert paths.summary_csv.name == "platform_evidence_package_summary.csv"
        assert paths.html_report.name == "platform_evidence_package_report.html"
        assert "evidence_id,evidence_type,source_system" in items_csv
        assert "metric,value" in summary_csv
        assert "FinTech Platform Evidence Package" in html_report
        assert "run_&lt;script&gt;" in html_report
        assert "compliance_&lt;script&gt;" in html_report
        assert "run_<script>" not in html_report
        assert "compliance_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _settlement_finding(
    *,
    run_id: str = "run_001",
    settlement_id: str = "settlement_001",
    message: str = "Provider settlement amount 99.99 does not match internal amount 100.00",
) -> PlatformSettlementReconciliationFinding:
    return PlatformSettlementReconciliationFinding(
        run_id=run_id,
        settlement_id=settlement_id,
        check_id="provider_settlement_amount_matches_internal_payment",
        status="failed",
        severity="error",
        message=message,
    )


def _access_finding() -> AccessAnomalyFinding:
    events = (
        _access_event(outcome="denied", occurred_at=datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)),
        _access_event(outcome="denied", occurred_at=datetime(2026, 6, 12, 9, 5, tzinfo=timezone.utc)),
        _access_event(outcome="denied", occurred_at=datetime(2026, 6, 12, 9, 10, tzinfo=timezone.utc)),
    )
    return AccessAnomalyFinding(
        finding_type="repeated_denied_access",
        actor="api_viewer_404",
        severity="high",
        event_count=len(events),
        reason="Actor has 3 denied access events within 15 minutes",
        first_occurred_at=events[0].occurred_at,
        last_occurred_at=events[-1].occurred_at,
        events=events,
    )


def _approval_record(
    *,
    approval_id: str = "approval_001",
    operation_id: str = "run_001",
    status: str = OPERATION_APPROVAL_APPROVED,
) -> OperationApprovalRecord:
    return OperationApprovalRecord(
        approval_id=approval_id,
        operation_type="retry_platform_async_run",
        operation_id=operation_id,
        target=f"fintech_platform_api_async_payment_runs/{operation_id}",
        requested_by="ops_user_001",
        request_reason="Retry after settlement review",
        approved_by="ops_manager_001" if status != OPERATION_APPROVAL_PENDING else None,
        approval_reason="Approved retry after reviewing evidence"
        if status != OPERATION_APPROVAL_PENDING
        else None,
        status=status,
        decision_reason="approved" if status != OPERATION_APPROVAL_PENDING else "pending approval",
        requested_at=_now(),
        decided_at=_now() if status != OPERATION_APPROVAL_PENDING else None,
    )


def _access_event(
    *,
    outcome: str,
    occurred_at: datetime | None = None,
) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.denied" if outcome == "denied" else "audit_access.granted",
        actor="api_viewer_404",
        permission="view_platform_payment_run",
        target="fintech_platform_api_payment_runs/missing_001",
        outcome=outcome,
        occurred_at=occurred_at or _now(),
        reason="Sample missing run lookup",
    )


def _provider_webhook_event(
    *,
    outcome: str,
    reason: str,
    occurred_at: datetime | None = None,
) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.denied" if outcome == "denied" else "audit_access.granted",
        actor="provider_webhook",
        permission="process_platform_provider_webhook",
        target="fintech_platform_provider_webhooks",
        outcome=outcome,
        occurred_at=occurred_at or _now(),
        reason=reason,
    )


def _now() -> datetime:
    return datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc)


def _output_directory() -> Path:
    directory = _test_data_directory() / f"platform-evidence-package-{uuid4()}"
    directory.mkdir()
    return directory


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
