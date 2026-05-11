from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_access_report_export import export_access_anomaly_report
from compliance_audit import AuditAccessEvent


def test_export_access_anomaly_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    findings = (_finding(),)

    paths = export_access_anomaly_report(output_directory, findings=findings)

    try:
        assert paths.findings_csv.exists()
        assert paths.html_report.exists()

        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "finding_type,actor,severity,event_count" in findings_csv
        assert "repeated_denied_access,viewer_001,high,3" in findings_csv
        assert "view_audit_payload" in findings_csv
        assert "Access Anomaly Report" in html_report
        assert "repeated_denied_access" in html_report
        assert "viewer_001" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_access_anomaly_report_handles_empty_findings() -> None:
    output_directory = _output_directory()

    paths = export_access_anomaly_report(output_directory, findings=())

    try:
        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert findings_csv.startswith("finding_type,actor,severity,event_count")
        assert "No access anomaly findings were detected." in html_report
    finally:
        _remove_directory(output_directory)


def test_export_access_anomaly_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    unsafe_finding = AccessAnomalyFinding(
        finding_type="repeated_denied_access",
        actor="viewer_<script>",
        severity="high",
        event_count=1,
        reason="<b>unsafe</b>",
        first_occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
        last_occurred_at=datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc),
        events=(
            _access_event(
                actor="viewer_<script>",
                permission="view_audit_payload",
                target="audit_events.<payload>",
            ),
        ),
    )

    paths = export_access_anomaly_report(
        output_directory,
        findings=(unsafe_finding,),
    )

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "viewer_&lt;script&gt;" in html_report
        assert "&lt;b&gt;unsafe&lt;/b&gt;" in html_report
        assert "audit_events.&lt;payload&gt;" not in html_report
        assert "<b>unsafe</b>" not in html_report
    finally:
        _remove_directory(output_directory)


def _finding() -> AccessAnomalyFinding:
    events = tuple(
        _access_event(
            actor="viewer_001",
            permission="view_audit_payload",
            target="audit_events.payload",
            minute=minute,
        )
        for minute in (0, 5, 10)
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


def _access_event(
    *,
    actor: str,
    permission: str,
    target: str,
    minute: int = 0,
) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.denied",
        actor=actor,
        permission=permission,
        target=target,
        outcome="denied",
        occurred_at=datetime(2026, 5, 8, 11, minute, tzinfo=timezone.utc),
        reason=None,
    )


def _output_directory() -> Path:
    directory = _test_data_directory() / f"access-anomaly-report-{uuid4()}"
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
