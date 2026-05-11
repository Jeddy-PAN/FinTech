from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from compliance_access_monitoring import AccessAnomalyFinding
from compliance_audit import AuditAccessEvent
from compliance_investigation_cases import AccessAnomalyInvestigationService
from compliance_investigation_report_export import export_investigation_case_report


def test_export_investigation_case_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    investigation_case = _resolved_case()

    paths = export_investigation_case_report(
        output_directory,
        cases=(investigation_case,),
    )

    try:
        assert paths.cases_csv.exists()
        assert paths.html_report.exists()

        cases_csv = paths.cases_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "case_id,status,finding_type,actor" in cases_csv
        assert "resolved,repeated_denied_access,viewer_001,high,3" in cases_csv
        assert "investigator_001" in cases_csv
        assert "Access Investigation Case Report" in html_report
        assert "Status Summary" in html_report
        assert "viewer_001" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_investigation_case_report_handles_empty_cases() -> None:
    output_directory = _output_directory()

    paths = export_investigation_case_report(output_directory, cases=())

    try:
        cases_csv = paths.cases_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert cases_csv.startswith("case_id,status,finding_type,actor")
        assert "No investigation cases were included in this report." in html_report
        assert "No access anomaly investigation cases were found." in html_report
    finally:
        _remove_directory(output_directory)


def test_export_investigation_case_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    service = AccessAnomalyInvestigationService()
    investigation_case = service.create_case(
        _finding(actor="viewer_<script>", reason="<b>unsafe</b>"),
        opened_by="lead_<script>",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )

    paths = export_investigation_case_report(
        output_directory,
        cases=(investigation_case,),
    )

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "viewer_&lt;script&gt;" in html_report
        assert "lead_&lt;script&gt;" in html_report
        assert "&lt;b&gt;unsafe&lt;/b&gt;" in html_report
        assert "viewer_<script>" not in html_report
        assert "<b>unsafe</b>" not in html_report
    finally:
        _remove_directory(output_directory)


def _resolved_case():
    service = AccessAnomalyInvestigationService()
    investigation_case = service.create_case(
        _finding(actor="viewer_001"),
        opened_by="compliance_lead_001",
        created_at=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
    )
    investigating_case = service.start_investigation(
        investigation_case.case_id,
        assigned_to="investigator_001",
        started_at=datetime(2026, 5, 8, 12, 10, tzinfo=timezone.utc),
    )
    return service.resolve(
        investigating_case.case_id,
        closed_by="investigator_001",
        reason="Confirmed access pattern was reviewed",
        closed_at=datetime(2026, 5, 8, 13, 0, tzinfo=timezone.utc),
    )


def _finding(
    *,
    actor: str,
    reason: str = "Actor has 3 denied access events within 15 minutes",
) -> AccessAnomalyFinding:
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
        reason=reason,
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


def _output_directory() -> Path:
    directory = _test_data_directory() / f"investigation-case-report-{uuid4()}"
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
