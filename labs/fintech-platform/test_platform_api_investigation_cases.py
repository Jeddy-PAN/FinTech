from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessEvent  # noqa: E402
from compliance_investigation_cases import (  # noqa: E402
    INVESTIGATION_FALSE_POSITIVE,
    INVESTIGATION_INVESTIGATING,
    AccessAnomalyInvestigationService,
)
from platform_api_access_anomaly_report import (  # noqa: E402
    detect_platform_api_access_anomalies,
)
from platform_api_investigation_cases import (  # noqa: E402
    export_platform_api_access_investigation_report,
    open_platform_api_access_investigation_cases,
)
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore  # noqa: E402


def test_open_platform_api_access_investigation_cases_creates_cases_from_findings() -> None:
    service = AccessAnomalyInvestigationService()
    findings = _platform_api_findings()

    cases = open_platform_api_access_investigation_cases(
        findings,
        opened_by="api_compliance_lead_001",
        created_at=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
        service=service,
    )

    assert len(cases) == len(findings)
    assert cases[0].status == "open"
    assert cases[0].opened_by == "api_compliance_lead_001"
    assert cases[0].finding.actor == "api_viewer_404"
    assert cases[0].finding.events[0].target.startswith("fintech_platform_api_")
    assert [event.event_type for event in service.audit_events] == [
        "access_investigation_case.created",
    ]


def test_platform_api_access_investigation_case_can_be_started_and_marked_false_positive() -> None:
    service = AccessAnomalyInvestigationService()
    investigation_case = open_platform_api_access_investigation_cases(
        _platform_api_findings(),
        opened_by="api_compliance_lead_001",
        created_at=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
        service=service,
    )[0]

    investigating_case = service.start_investigation(
        investigation_case.case_id,
        assigned_to="api_investigator_001",
        started_at=datetime(2026, 5, 19, 13, 10, tzinfo=timezone.utc),
    )
    false_positive_case = service.mark_false_positive(
        investigating_case.case_id,
        closed_by="api_investigator_001",
        reason="Confirmed sample missing-run lookups were test traffic",
        closed_at=datetime(2026, 5, 19, 14, 0, tzinfo=timezone.utc),
    )

    assert investigating_case.status == INVESTIGATION_INVESTIGATING
    assert false_positive_case.status == INVESTIGATION_FALSE_POSITIVE
    assert false_positive_case.closed_by == "api_investigator_001"
    assert [event.event_type for event in service.audit_events][-2:] == [
        "access_investigation_case.started",
        "access_investigation_case.false_positive",
    ]


def test_platform_api_access_investigation_cases_can_be_persisted() -> None:
    database_path = _database_path()
    store = SQLiteInvestigationCaseStore(database_path)
    service = AccessAnomalyInvestigationService()
    try:
        investigation_case = open_platform_api_access_investigation_cases(
            _platform_api_findings(),
            opened_by="api_compliance_lead_001",
            created_at=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
            service=service,
        )[0]
        investigating_case = service.start_investigation(
            investigation_case.case_id,
            assigned_to="api_investigator_001",
            started_at=datetime(2026, 5, 19, 13, 10, tzinfo=timezone.utc),
        )

        store.save_case(investigating_case)

        persisted = store.get_case(investigating_case.case_id)
        assert persisted.status == INVESTIGATION_INVESTIGATING
        assert persisted.assigned_to == "api_investigator_001"
        assert persisted.finding.events[0].target.startswith("fintech_platform_api_")
        assert store.query_cases(actor="api_viewer_404") == (persisted,)
    finally:
        _close_and_remove(store)


def test_export_platform_api_access_investigation_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    service = AccessAnomalyInvestigationService()
    investigation_case = open_platform_api_access_investigation_cases(
        _platform_api_findings(),
        opened_by="api_compliance_lead_001",
        created_at=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
        service=service,
    )[0]
    investigating_case = service.start_investigation(
        investigation_case.case_id,
        assigned_to="api_investigator_001",
        started_at=datetime(2026, 5, 19, 13, 10, tzinfo=timezone.utc),
    )
    resolved_case = service.resolve(
        investigating_case.case_id,
        closed_by="api_investigator_001",
        reason="Reviewed sample platform API finding",
        closed_at=datetime(2026, 5, 19, 14, 0, tzinfo=timezone.utc),
    )

    paths = export_platform_api_access_investigation_report(
        output_directory,
        cases=(resolved_case,),
    )

    try:
        cases_csv = paths.cases_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert paths.cases_csv.name == "platform_api_access_investigation_cases.csv"
        assert paths.html_report.name == "platform_api_access_investigation_report.html"
        assert "case_id,status,finding_type,actor" in cases_csv
        assert "FinTech Platform API Access Investigation Report" in html_report
        assert "api_investigator_001" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_platform_api_access_investigation_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    service = AccessAnomalyInvestigationService()
    findings = detect_platform_api_access_anomalies(
        tuple(
            _access_event(
                actor="api_viewer_<script>",
                target=f"fintech_platform_api_payment_runs/missing_{minute}",
                occurred_at=datetime(2026, 5, 19, 12, minute, tzinfo=timezone.utc),
            )
            for minute in (0, 5, 10)
        )
    )
    investigation_case = open_platform_api_access_investigation_cases(
        findings,
        opened_by="api_lead_<script>",
        created_at=datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc),
        service=service,
    )[0]

    paths = export_platform_api_access_investigation_report(
        output_directory,
        cases=(investigation_case,),
    )

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "api_viewer_&lt;script&gt;" in html_report
        assert "api_lead_&lt;script&gt;" in html_report
        assert "api_viewer_<script>" not in html_report
        assert "api_lead_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _platform_api_findings():
    return detect_platform_api_access_anomalies(
        tuple(
            _access_event(
                actor="api_viewer_404",
                target=f"fintech_platform_api_payment_runs/missing_{minute}",
                occurred_at=datetime(2026, 5, 19, 12, minute, tzinfo=timezone.utc),
            )
            for minute in (0, 5, 10)
        )
    )


def _access_event(
    *,
    actor: str,
    target: str,
    occurred_at: datetime,
) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type="audit_access.denied",
        actor=actor,
        permission="view_platform_payment_run",
        target=target,
        outcome="denied",
        occurred_at=occurred_at,
        reason="Sample missing platform payment run lookup",
    )


def _database_path() -> Path:
    directory = _test_data_directory()
    return directory / f"platform-api-investigation-cases-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"platform-api-investigation-report-{uuid4()}"
    directory.mkdir()
    return directory


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _close_and_remove(store: SQLiteInvestigationCaseStore) -> None:
    database_path = store.database_path
    store.close()
    if database_path.exists():
        database_path.unlink()


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
