from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from compliance_audit import (
    AuditAccessRecorder,
    AuditExportApproval,
    AuditUser,
    ComplianceAuditError,
    ComplianceAuditEvent,
    build_audit_timeline,
    summarize_audit_events,
)
from compliance_audit_export import export_compliance_audit_report


def test_export_compliance_audit_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    events = _events()
    summary = summarize_audit_events(events)
    timeline = build_audit_timeline(
        events,
        subject_type="customer",
        subject_id="cust_001",
        aggregate_links=(
            ("kyc_application", "cust_001"),
            ("risk_decision", "txn_001"),
        ),
    )

    paths = export_compliance_audit_report(
        output_directory,
        events=events,
        summary=summary,
        timeline=timeline,
    )

    try:
        assert paths.events_csv.exists()
        assert paths.summary_csv.exists()
        assert paths.timeline_csv is not None
        assert paths.timeline_csv.exists()
        assert paths.html_report.exists()

        events_csv = paths.events_csv.read_text(encoding="utf-8")
        summary_csv = paths.summary_csv.read_text(encoding="utf-8")
        timeline_csv = paths.timeline_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert (
            "occurred_at,source_system,event_type,aggregate_type,aggregate_id"
            in events_csv
        )
        assert "kyc,kyc_application.saved,kyc_application,cust_001" in events_csv
        assert "summary,total_events,2" in summary_csv
        assert "source_system,kyc,1" in summary_csv
        assert "subject_type,subject_id,occurred_at" in timeline_csv
        assert "customer,cust_001,2026-05-08T09:00:00+00:00" in timeline_csv
        assert "Compliance Audit Report" in html_report
        assert "cust_001" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_can_skip_timeline_csv() -> None:
    output_directory = _output_directory()

    paths = export_compliance_audit_report(
        output_directory,
        events=_events(),
    )

    try:
        assert paths.timeline_csv is None
        assert paths.events_csv.exists()
        assert paths.summary_csv.exists()
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "No audit timeline was provided." in html_report
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    events = (
        ComplianceAuditEvent(
            source_system="kyc",
            event_id="event_unsafe",
            event_type="kyc_decision.saved",
            aggregate_type="kyc_decision",
            aggregate_id="cust_<script>",
            actor="analyst_001",
            reason="<b>unsafe</b>",
            payload='{"note":"<script>alert(1)</script>"}',
            occurred_at=datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc),
        ),
    )

    paths = export_compliance_audit_report(output_directory, events=events)

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "cust_&lt;script&gt;" in html_report
        assert "&lt;b&gt;unsafe&lt;/b&gt;" in html_report
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_report
        assert "<script>alert(1)</script>" not in html_report
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_requires_export_permission() -> None:
    output_directory = _output_directory()

    try:
        try:
            export_compliance_audit_report(
                output_directory,
                events=_events(),
                requested_by=AuditUser("viewer_001", ("audit_viewer",)),
            )
        except ComplianceAuditError as error:
            assert "export_audit_report" in str(error)
        else:
            raise AssertionError("Expected ComplianceAuditError")

        paths = export_compliance_audit_report(
            output_directory,
            events=_events(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
        )
        assert paths.html_report.exists()
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_records_export_access() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()

    try:
        paths = export_compliance_audit_report(
            output_directory,
            events=_events(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
        )

        assert paths.html_report.exists()
        assert len(recorder.events) == 1
        assert recorder.events[0].event_type == "audit_access.granted"
        assert recorder.events[0].permission == "export_audit_report"
        assert recorder.events[0].target == "compliance_audit_report"
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_can_require_separate_approval() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()

    try:
        paths = export_compliance_audit_report(
            output_directory,
            events=_events(),
            requested_by=AuditUser("manager_001", ("audit_manager",)),
            access_recorder=recorder,
            accessed_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
            require_approval=True,
            approval=AuditExportApproval(
                approved_by=AuditUser("manager_002", ("audit_manager",)),
                approved_at=datetime(2026, 5, 8, 12, 5, tzinfo=timezone.utc),
                reason="Approved sample export",
            ),
        )

        assert paths.html_report.exists()
        assert [event.event_type for event in recorder.events] == [
            "audit_access.granted",
            "audit_access.granted",
            "audit_export_approval.granted",
        ]
        assert recorder.events[-1].actor == "manager_002"
        assert recorder.events[-1].permission == "approve_audit_export"
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_rejects_missing_required_approval() -> None:
    output_directory = _output_directory()

    try:
        try:
            export_compliance_audit_report(
                output_directory,
                events=_events(),
                requested_by=AuditUser("manager_001", ("audit_manager",)),
                require_approval=True,
            )
        except ComplianceAuditError as error:
            assert "approval is required" in str(error)
        else:
            raise AssertionError("Expected ComplianceAuditError")
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_rejects_self_approval() -> None:
    output_directory = _output_directory()
    recorder = AuditAccessRecorder.create()

    try:
        try:
            export_compliance_audit_report(
                output_directory,
                events=_events(),
                requested_by=AuditUser("manager_001", ("audit_manager",)),
                access_recorder=recorder,
                accessed_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
                require_approval=True,
                approval=AuditExportApproval(
                    approved_by=AuditUser("manager_001", ("audit_manager",)),
                    approved_at=datetime(2026, 5, 8, 12, 5, tzinfo=timezone.utc),
                    reason="Self approval should fail",
                ),
            )
        except ComplianceAuditError as error:
            assert "approver must differ" in str(error)
        else:
            raise AssertionError("Expected ComplianceAuditError")

        assert recorder.events[-1].event_type == "audit_export_approval.denied"
        assert recorder.events[-1].outcome == "denied"
    finally:
        _remove_directory(output_directory)


def test_export_compliance_audit_report_rejects_approval_without_permission() -> None:
    output_directory = _output_directory()

    try:
        try:
            export_compliance_audit_report(
                output_directory,
                events=_events(),
                requested_by=AuditUser("manager_001", ("audit_manager",)),
                require_approval=True,
                approval=AuditExportApproval(
                    approved_by=AuditUser("analyst_001", ("audit_analyst",)),
                    approved_at=datetime(2026, 5, 8, 12, 5, tzinfo=timezone.utc),
                    reason="Analyst approval should fail",
                ),
            )
        except ComplianceAuditError as error:
            assert "approve_audit_export" in str(error)
        else:
            raise AssertionError("Expected ComplianceAuditError")
    finally:
        _remove_directory(output_directory)


def _events() -> tuple[ComplianceAuditEvent, ...]:
    return (
        ComplianceAuditEvent(
            source_system="kyc",
            event_id="kyc_001",
            event_type="kyc_application.saved",
            aggregate_type="kyc_application",
            aggregate_id="cust_001",
            actor="system",
            reason=None,
            payload='{"customer_id":"cust_001"}',
            occurred_at=datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc),
        ),
        ComplianceAuditEvent(
            source_system="risk",
            event_id="risk_001",
            event_type="risk_decision.saved",
            aggregate_type="risk_decision",
            aggregate_id="txn_001",
            actor="system",
            reason=None,
            payload='{"request_id":"txn_001"}',
            occurred_at=datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        ),
    )


def _output_directory() -> Path:
    directory = _test_data_directory() / f"report-{uuid4()}"
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
