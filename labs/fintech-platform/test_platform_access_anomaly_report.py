from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessEvent
from platform_access_anomaly_report import (
    detect_platform_report_access_anomalies,
    export_platform_access_anomaly_report,
)


def test_detect_platform_report_access_anomalies_filters_to_platform_targets() -> None:
    findings = detect_platform_report_access_anomalies(
        (
            _access_event(
                actor="analyst_001",
                permission="export_audit_report",
                target="fintech_platform_payment_report",
                outcome="denied",
                occurred_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            ),
            _access_event(
                actor="analyst_002",
                permission="export_audit_report",
                target="compliance_audit_report",
                outcome="denied",
                occurred_at=datetime(2026, 5, 18, 12, 1, tzinfo=timezone.utc),
            ),
        )
    )

    assert len(findings) == 1
    assert findings[0].finding_type == "unauthorized_export_attempt"
    assert findings[0].actor == "analyst_001"
    assert findings[0].events[0].target == "fintech_platform_payment_report"


def test_detect_platform_report_access_anomalies_finds_repeated_denied_access() -> None:
    findings = detect_platform_report_access_anomalies(
        tuple(
            _access_event(
                actor="viewer_001",
                permission="export_audit_report",
                target="fintech_platform_history_report",
                outcome="denied",
                occurred_at=datetime(2026, 5, 18, 12, minute, tzinfo=timezone.utc),
            )
            for minute in (0, 5, 10)
        )
    )

    finding_types = {finding.finding_type for finding in findings}
    assert "repeated_denied_access" in finding_types
    assert "unauthorized_export_attempt" in finding_types


def test_export_platform_access_anomaly_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    findings = detect_platform_report_access_anomalies(
        (
            _access_event(
                actor="analyst_001",
                permission="export_audit_report",
                target="fintech_platform_consistency_report",
                outcome="denied",
                occurred_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            ),
        )
    )

    paths = export_platform_access_anomaly_report(
        output_directory,
        findings=findings,
    )

    try:
        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "finding_type,actor,severity,event_count" in findings_csv
        assert "unauthorized_export_attempt,analyst_001,high,1" in findings_csv
        assert "fintech_platform_consistency_report" in findings_csv
        assert "FinTech Platform Access Anomaly Report" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_platform_access_anomaly_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    findings = detect_platform_report_access_anomalies(
        (
            _access_event(
                actor="analyst_<script>",
                permission="export_audit_report",
                target="fintech_platform_payment_report",
                outcome="denied",
                occurred_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            ),
        )
    )

    paths = export_platform_access_anomaly_report(
        output_directory,
        findings=findings,
    )

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "analyst_&lt;script&gt;" in html_report
        assert "analyst_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _access_event(
    *,
    actor: str,
    permission: str,
    target: str,
    outcome: str,
    occurred_at: datetime,
) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type=(
            "audit_access.granted" if outcome == "granted" else "audit_access.denied"
        ),
        actor=actor,
        permission=permission,
        target=target,
        outcome=outcome,
        occurred_at=occurred_at,
        reason=None,
    )


def _output_directory() -> Path:
    directory = _test_data_directory() / f"platform-access-anomaly-{uuid4()}"
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
