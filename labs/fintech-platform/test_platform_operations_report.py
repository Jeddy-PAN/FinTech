from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4

LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessEvent, ComplianceAuditEvent
from platform_async_service import PlatformAsyncRun
from platform_operations_report import (
    build_platform_operations_report,
    export_platform_operations_report,
)
from sqlite_platform_store import PlatformRunRecord, PlatformRunSnapshot


def test_operations_report_detects_completed_async_run_without_platform_result() -> None:
    report = build_platform_operations_report(
        async_runs=(_async_run("run_missing_platform", status="completed"),),
        snapshots=(),
        access_events=(),
    )

    assert report.summary.async_run_count == 1
    assert report.summary.failed_finding_count == 1
    assert report.run_rows[0].run_id == "run_missing_platform"
    assert report.run_rows[0].reconciliation_status == "failed"
    assert any(
        finding.run_id == "run_missing_platform"
        and finding.check_id == "completed_async_has_platform_result"
        and finding.status == "failed"
        and finding.severity == "error"
        for finding in report.findings
    )


def test_operations_report_includes_failed_async_run_as_warning() -> None:
    report = build_platform_operations_report(
        async_runs=(
            _async_run(
                "run_failed_async",
                status="failed",
                attempt_count=3,
                last_error="different request fingerprint",
            ),
        ),
        snapshots=(),
        access_events=(),
    )

    assert report.summary.failed_async_run_count == 1
    assert report.summary.warning_finding_count == 1
    assert report.run_rows[0].run_id == "run_failed_async"
    assert report.run_rows[0].async_status == "failed"
    assert report.run_rows[0].last_error == "different request fingerprint"
    assert report.run_rows[0].reconciliation_status == "warning"
    assert any(
        finding.check_id == "failed_async_run_requires_review"
        and finding.status == "warning"
        and finding.severity == "warning"
        for finding in report.findings
    )


def test_operations_report_counts_retry_access_audit_by_run_id() -> None:
    report = build_platform_operations_report(
        async_runs=(_async_run("run_retry_audit", status="failed"),),
        snapshots=(),
        access_events=(
            _access_event("run_retry_audit", "granted"),
            _access_event("run_retry_audit", "denied"),
            _access_event("run_other", "granted"),
        ),
    )

    row = report.run_rows[0]
    assert row.run_id == "run_retry_audit"
    assert row.retry_granted_count == 1
    assert row.retry_denied_count == 1
    assert report.summary.retry_granted_count == 2
    assert report.summary.retry_denied_count == 1


def test_operations_report_detects_completed_platform_ledger_issues() -> None:
    snapshot = _completed_snapshot("run_ledger_missing_event")
    no_ledger_id_snapshot = PlatformRunSnapshot(
        record=replace(
            snapshot.record,
            run_id="run_missing_ledger_id",
            ledger_transaction_id=None,
        ),
        audit_events=(),
    )
    no_matching_event_snapshot = PlatformRunSnapshot(
        record=replace(
            snapshot.record,
            run_id="run_ledger_missing_event",
            ledger_transaction_id="ledger_txn_missing",
        ),
        audit_events=(),
    )

    report = build_platform_operations_report(
        async_runs=(),
        snapshots=(no_ledger_id_snapshot, no_matching_event_snapshot),
        access_events=(),
    )

    assert {
        (finding.run_id, finding.check_id, finding.status)
        for finding in report.findings
    } == {
        ("run_missing_ledger_id", "completed_platform_has_ledger_transaction", "failed"),
        ("run_ledger_missing_event", "ledger_transaction_has_posted_event", "failed"),
    }
    assert {row.reconciliation_status for row in report.run_rows} == {"failed"}


def test_export_platform_operations_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    snapshot = _completed_snapshot("run_export_<script>")

    try:
        paths = export_platform_operations_report(
            output_directory,
            async_runs=(
                _async_run(
                    "run_export_<script>",
                    status="completed",
                    attempt_count=1,
                ),
            ),
            snapshots=(snapshot,),
            access_events=(_access_event("run_export_<script>", "granted"),),
        )

        assert paths.run_rows_csv.exists()
        assert paths.findings_csv.exists()
        assert paths.html_report.exists()

        rows_csv = paths.run_rows_csv.read_text(encoding="utf-8")
        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "run_id,async_status,platform_status,payment_order_status" in rows_csv
        assert "run_export_<script>,completed,completed,succeeded" in rows_csv
        assert "run_id,check_id,status,severity,message" in findings_csv
        assert "FinTech Platform Operations Report" in html_report
        assert "Run Rows" in html_report
        assert "Reconciliation Findings" in html_report
        assert "run_export_&lt;script&gt;" in html_report
        assert "run_export_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _async_run(
    run_id: str,
    *,
    status: str,
    attempt_count: int = 0,
    max_attempts: int = 3,
    last_error: str | None = None,
) -> PlatformAsyncRun:
    now = _now()
    return PlatformAsyncRun(
        run_id=run_id,
        status=status,
        request_payload={"run_id": run_id},
        request_fingerprint=f"fingerprint:{run_id}",
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        last_error=last_error,
        created_at=now,
        updated_at=now,
        started_at=now if status in {"processing", "completed", "failed"} else None,
        completed_at=now if status in {"completed", "failed"} else None,
    )


def _completed_snapshot(run_id: str) -> PlatformRunSnapshot:
    ledger_transaction_id = f"ledger_{run_id}"
    return PlatformRunSnapshot(
        record=PlatformRunRecord(
            run_id=run_id,
            customer_id="cust_001",
            status="completed",
            kyc_status="approved",
            payment_order_id=f"order_{run_id}",
            payment_order_status="succeeded",
            risk_status="approved",
            risk_review_case_id=None,
            ledger_transaction_id=ledger_transaction_id,
            platform_bank_balance=Decimal("100.00"),
            user_wallet_balance=Decimal("100.00"),
            audit_event_count=1,
            created_at=_now(),
        ),
        audit_events=(
            ComplianceAuditEvent(
                source_system="ledger",
                event_id=f"event_{run_id}",
                event_type="ledger_transaction.posted",
                aggregate_type="ledger_transaction",
                aggregate_id=ledger_transaction_id,
                actor="system",
                reason=None,
                payload="{}",
                occurred_at=_now(),
            ),
        ),
    )


def _access_event(run_id: str, outcome: str) -> AuditAccessEvent:
    return AuditAccessEvent(
        event_type=f"audit_access.{outcome}",
        actor="ops_user_001",
        permission="retry_platform_async_run",
        target=f"fintech_platform_api_async_payment_runs/{run_id}",
        outcome=outcome,
        occurred_at=_now(),
        reason="sample retry audit",
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)


def _output_directory() -> Path:
    directory = Path(__file__).with_name(".test-data") / f"operations-report-{uuid4()}"
    directory.mkdir(parents=True)
    return directory


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
