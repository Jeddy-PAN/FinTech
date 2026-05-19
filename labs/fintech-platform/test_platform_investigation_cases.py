from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_investigation_cases import (  # noqa: E402
    INVESTIGATION_INVESTIGATING,
    INVESTIGATION_RESOLVED,
    AccessAnomalyInvestigationService,
)
from platform_access_anomaly_report import detect_platform_report_access_anomalies  # noqa: E402
from platform_investigation_cases import (  # noqa: E402
    export_platform_access_investigation_report,
    open_platform_access_investigation_cases,
)
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore  # noqa: E402
from compliance_audit import AuditAccessEvent  # noqa: E402


def test_open_platform_access_investigation_cases_creates_cases_from_findings() -> None:
    service = AccessAnomalyInvestigationService()
    findings = _platform_findings()

    cases = open_platform_access_investigation_cases(
        findings,
        opened_by="platform_compliance_lead_001",
        created_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
        service=service,
    )

    assert len(cases) == len(findings)
    assert {case.finding for case in cases} == set(findings)
    assert all(case.status == "open" for case in cases)
    assert all(case.opened_by == "platform_compliance_lead_001" for case in cases)
    assert [event.event_type for event in service.audit_events] == [
        "access_investigation_case.created",
        "access_investigation_case.created",
    ]


def test_platform_access_investigation_case_can_be_started_and_resolved() -> None:
    service = AccessAnomalyInvestigationService()
    investigation_case = open_platform_access_investigation_cases(
        _platform_findings(),
        opened_by="platform_compliance_lead_001",
        created_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
        service=service,
    )[0]

    investigating_case = service.start_investigation(
        investigation_case.case_id,
        assigned_to="platform_investigator_001",
        started_at=datetime(2026, 5, 18, 13, 10, tzinfo=timezone.utc),
    )
    resolved_case = service.resolve(
        investigating_case.case_id,
        closed_by="platform_investigator_001",
        reason="Confirmed sample platform export access issue was reviewed",
        closed_at=datetime(2026, 5, 18, 14, 0, tzinfo=timezone.utc),
    )

    assert investigating_case.status == INVESTIGATION_INVESTIGATING
    assert resolved_case.status == INVESTIGATION_RESOLVED
    assert resolved_case.closed_by == "platform_investigator_001"
    assert [event.event_type for event in service.audit_events][-2:] == [
        "access_investigation_case.started",
        "access_investigation_case.resolved",
    ]


def test_platform_access_investigation_cases_can_be_persisted() -> None:
    database_path = _database_path()
    store = SQLiteInvestigationCaseStore(database_path)
    service = AccessAnomalyInvestigationService()
    try:
        cases = open_platform_access_investigation_cases(
            _platform_findings(),
            opened_by="platform_compliance_lead_001",
            created_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
            service=service,
        )
        investigating_case = service.start_investigation(
            cases[0].case_id,
            assigned_to="platform_investigator_001",
            started_at=datetime(2026, 5, 18, 13, 10, tzinfo=timezone.utc),
        )

        store.save_case(investigating_case)
        store.save_case(cases[1])

        assert store.query_cases(assigned_to="platform_investigator_001") == (
            investigating_case,
        )
        assert len(store.open_cases) == 2
        assert store.get_case(investigating_case.case_id).finding.events[0].target.startswith(
            "fintech_platform_"
        )
    finally:
        _close_and_remove(store)


def test_export_platform_access_investigation_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    service = AccessAnomalyInvestigationService()
    investigation_case = open_platform_access_investigation_cases(
        _platform_findings(),
        opened_by="platform_compliance_lead_001",
        created_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
        service=service,
    )[0]
    investigating_case = service.start_investigation(
        investigation_case.case_id,
        assigned_to="platform_investigator_001",
        started_at=datetime(2026, 5, 18, 13, 10, tzinfo=timezone.utc),
    )
    resolved_case = service.resolve(
        investigating_case.case_id,
        closed_by="platform_investigator_001",
        reason="Reviewed sample platform finding",
        closed_at=datetime(2026, 5, 18, 14, 0, tzinfo=timezone.utc),
    )

    paths = export_platform_access_investigation_report(
        output_directory,
        cases=(resolved_case,),
    )

    try:
        cases_csv = paths.cases_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert paths.cases_csv.name == "platform_access_investigation_cases.csv"
        assert paths.html_report.name == "platform_access_investigation_report.html"
        assert "case_id,status,finding_type,actor" in cases_csv
        assert "FinTech Platform Access Investigation Report" in html_report
        assert "platform_investigator_001" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_platform_access_investigation_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    service = AccessAnomalyInvestigationService()
    findings = detect_platform_report_access_anomalies(
        (
            _access_event(
                actor="analyst_<script>",
                target="fintech_platform_payment_report",
                occurred_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            ),
        )
    )
    investigation_case = open_platform_access_investigation_cases(
        findings,
        opened_by="lead_<script>",
        created_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
        service=service,
    )[0]

    paths = export_platform_access_investigation_report(
        output_directory,
        cases=(investigation_case,),
    )

    try:
        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "analyst_&lt;script&gt;" in html_report
        assert "lead_&lt;script&gt;" in html_report
        assert "analyst_<script>" not in html_report
        assert "lead_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _platform_findings():
    return detect_platform_report_access_anomalies(
        (
            _access_event(
                actor="viewer_002",
                target="fintech_platform_history_report",
                occurred_at=datetime(2026, 5, 18, 12, 20, tzinfo=timezone.utc),
            ),
            _access_event(
                actor="viewer_002",
                target="fintech_platform_history_report",
                occurred_at=datetime(2026, 5, 18, 12, 24, tzinfo=timezone.utc),
            ),
            _access_event(
                actor="viewer_002",
                target="fintech_platform_history_report",
                occurred_at=datetime(2026, 5, 18, 12, 28, tzinfo=timezone.utc),
            ),
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
        permission="export_audit_report",
        target=target,
        outcome="denied",
        occurred_at=occurred_at,
        reason="Sample platform export attempt",
    )


def _database_path() -> Path:
    directory = _test_data_directory()
    return directory / f"platform-investigation-cases-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"platform-investigation-report-{uuid4()}"
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
