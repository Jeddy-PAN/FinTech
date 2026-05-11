from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from compliance_audit import ComplianceAuditEvent
from compliance_retention import AuditRetentionPolicy, build_retention_report
from compliance_retention_export import export_audit_retention_report


def test_export_audit_retention_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    report = build_retention_report(
        (
            _event(
                event_id="evt_001",
                event_type="kyc_decision.saved",
                occurred_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
        ),
        policies=(
            AuditRetentionPolicy(
                policy_id="kyc-standard",
                event_type_prefix="kyc_",
                retention_days=90,
                archive_after_days=30,
            ),
        ),
        generated_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    paths = export_audit_retention_report(output_directory, report=report)

    try:
        assert paths.decisions_csv.exists()
        assert paths.html_report.exists()

        decisions_csv = paths.decisions_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "event_id,event_type,source_system,aggregate_type" in decisions_csv
        assert "evt_001,kyc_decision.saved,kyc,customer,cust_001" in decisions_csv
        assert "kyc-standard,active,7" in decisions_csv
        assert "Audit Retention Report" in html_report
        assert "Status Summary" in html_report
        assert "kyc_decision.saved" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_audit_retention_report_handles_empty_decisions() -> None:
    output_directory = _output_directory()
    report = build_retention_report(
        (),
        policies=(
            AuditRetentionPolicy(
                policy_id="kyc-standard",
                event_type_prefix="kyc_",
                retention_days=90,
            ),
        ),
        generated_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    paths = export_audit_retention_report(output_directory, report=report)

    try:
        decisions_csv = paths.decisions_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert decisions_csv.startswith("event_id,event_type,source_system")
        assert "No retention decisions were generated." in html_report
        assert "No audit events were included in this retention report." in html_report
    finally:
        _remove_directory(output_directory)


def test_export_audit_retention_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    unsafe_event = _event(
        event_id="evt_<script>",
        event_type="kyc_decision.<saved>",
        occurred_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        aggregate_id="cust_<001>",
    )
    report = build_retention_report(
        (unsafe_event,),
        policies=(
            AuditRetentionPolicy(
                policy_id="kyc-<standard>",
                event_type_prefix="kyc_",
                retention_days=90,
            ),
        ),
        generated_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    paths = export_audit_retention_report(output_directory, report=report)

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "evt_&lt;script&gt;" in html_report
        assert "kyc_decision.&lt;saved&gt;" in html_report
        assert "cust_&lt;001&gt;" in html_report
        assert "kyc-&lt;standard&gt;" in html_report
        assert "evt_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _event(
    *,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    aggregate_id: str = "cust_001",
) -> ComplianceAuditEvent:
    return ComplianceAuditEvent(
        source_system="kyc",
        event_id=event_id,
        event_type=event_type,
        aggregate_type="customer",
        aggregate_id=aggregate_id,
        actor="system",
        reason="<b>sample</b>",
        payload="{}",
        occurred_at=occurred_at,
    )


def _output_directory() -> Path:
    directory = _test_data_directory() / f"audit-retention-report-{uuid4()}"
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
