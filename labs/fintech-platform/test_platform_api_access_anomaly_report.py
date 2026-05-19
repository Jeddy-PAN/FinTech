from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessEvent  # noqa: E402
from platform_api_access_anomaly_report import (  # noqa: E402
    detect_platform_api_access_anomalies,
    export_platform_api_access_anomaly_report,
)
from platform_api_app import create_app  # noqa: E402
from sqlite_access_audit_store import SQLiteAccessAuditStore  # noqa: E402


def test_detect_platform_api_access_anomalies_filters_to_api_targets() -> None:
    findings = detect_platform_api_access_anomalies(
        (
            _access_event(
                actor="api_viewer_001",
                permission="view_platform_payment_run",
                target="fintech_platform_api_payment_runs/missing_run",
                outcome="denied",
                occurred_at=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
            ),
            _access_event(
                actor="report_viewer_001",
                permission="export_audit_report",
                target="fintech_platform_history_report",
                outcome="denied",
                occurred_at=datetime(2026, 5, 19, 12, 1, tzinfo=timezone.utc),
            ),
        )
    )

    assert findings == ()


def test_detect_platform_api_access_anomalies_finds_repeated_denied_api_access() -> None:
    findings = detect_platform_api_access_anomalies(
        tuple(
            _access_event(
                actor="api_viewer_001",
                permission="view_platform_payment_run",
                target=f"fintech_platform_api_payment_runs/missing_run_{minute}",
                outcome="denied",
                occurred_at=datetime(2026, 5, 19, 12, minute, tzinfo=timezone.utc),
            )
            for minute in (0, 5, 10)
        )
    )

    assert len(findings) == 1
    assert findings[0].finding_type == "repeated_denied_access"
    assert findings[0].actor == "api_viewer_001"
    assert findings[0].event_count == 3


def test_detect_platform_api_access_anomalies_uses_fastapi_access_audit_events() -> None:
    client, database_path, access_audit_database_path = _client()
    try:
        for run_id in ("missing_001", "missing_002", "missing_003"):
            response = client.get(
                f"/platform/payment-runs/{run_id}",
                headers={"x-actor-id": "api_viewer_404"},
            )
            assert response.status_code == 404

        access_store = SQLiteAccessAuditStore(access_audit_database_path)
        try:
            findings = detect_platform_api_access_anomalies(access_store.access_events)
        finally:
            access_store.close()

        assert len(findings) == 1
        assert findings[0].finding_type == "repeated_denied_access"
        assert findings[0].actor == "api_viewer_404"
        assert {
            event.target for event in findings[0].events
        } == {
            "fintech_platform_api_payment_runs/missing_001",
            "fintech_platform_api_payment_runs/missing_002",
            "fintech_platform_api_payment_runs/missing_003",
        }
    finally:
        client.close()
        _remove_database(database_path)
        _remove_database(access_audit_database_path)


def test_export_platform_api_access_anomaly_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    findings = detect_platform_api_access_anomalies(
        tuple(
            _access_event(
                actor="api_viewer_<script>",
                permission="view_platform_payment_run",
                target=f"fintech_platform_api_payment_runs/missing_run_{minute}",
                outcome="denied",
                occurred_at=datetime(2026, 5, 19, 12, minute, tzinfo=timezone.utc),
            )
            for minute in (0, 5, 10)
        )
    )

    paths = export_platform_api_access_anomaly_report(
        output_directory,
        findings=findings,
    )

    try:
        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "finding_type,actor,severity,event_count" in findings_csv
        assert "repeated_denied_access" in findings_csv
        assert "FinTech Platform API Access Anomaly Report" in html_report
        assert "api_viewer_&lt;script&gt;" in html_report
        assert "api_viewer_<script>" not in html_report
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


def _client():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
    )


def _database_path() -> Path:
    return _test_data_directory() / f"platform-api-anomaly-{uuid4()}.db"


def _access_audit_database_path() -> Path:
    return _test_data_directory() / f"platform-api-anomaly-access-audit-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"platform-api-access-anomaly-{uuid4()}"
    directory.mkdir()
    return directory


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
