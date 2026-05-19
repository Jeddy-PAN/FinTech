from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_consistency_report import (
    evaluate_platform_run_consistency,
    export_platform_consistency_report,
)
from sqlite_platform_store import PlatformRunSnapshot, SQLitePlatformStore


def test_platform_consistency_report_passes_expected_platform_states() -> None:
    snapshots = _snapshots()

    findings = evaluate_platform_run_consistency(snapshots)

    assert len(findings) == 12
    assert {finding.status for finding in findings} == {"passed"}
    assert {
        (finding.run_id, finding.check_id)
        for finding in findings
        if finding.check_id == "platform_status_contract"
    } == {
        ("run_completed", "platform_status_contract"),
        ("run_review_approved", "platform_status_contract"),
        ("run_review_rejected", "platform_status_contract"),
    }


def test_platform_consistency_report_detects_ledger_mismatch() -> None:
    snapshot = _snapshots()[0]
    broken_snapshot = PlatformRunSnapshot(
        record=replace(snapshot.record, ledger_transaction_id="missing_ledger_txn"),
        audit_events=snapshot.audit_events,
    )

    findings = evaluate_platform_run_consistency((broken_snapshot,))

    assert any(
        finding.check_id == "ledger_event_matches_record"
        and finding.status == "failed"
        and "no matching ledger posted event" in finding.message
        for finding in findings
    )


def test_export_platform_consistency_report_writes_csv_and_html() -> None:
    output_directory = _output_directory()
    snapshots = _snapshots()

    paths = export_platform_consistency_report(
        output_directory,
        snapshots=snapshots,
    )

    try:
        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert "run_id,check_id,status,severity,message" in findings_csv
        assert "run_review_rejected,platform_status_contract,passed" in findings_csv
        assert "FinTech Platform Consistency Report" in html_report
        assert "failed findings: 0" in html_report
    finally:
        _remove_directory(output_directory)


def test_export_platform_consistency_report_escapes_html_values() -> None:
    output_directory = _output_directory()
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)

    try:
        store.save_result(
            _completed_result(order_id="order_<script>"),
            run_id="run_<script>",
            created_at=_requested_at(),
        )
        paths = export_platform_consistency_report(
            output_directory,
            snapshots=(store.get_run("run_<script>"),),
        )

        html_report = paths.html_report.read_text(encoding="utf-8")
        assert "run_&lt;script&gt;" in html_report
        assert "run_<script>" not in html_report
    finally:
        store.close()
        _remove_directory(output_directory)


def _snapshots() -> tuple[PlatformRunSnapshot, ...]:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            _completed_result(order_id="order_completed"),
            run_id="run_completed",
            created_at=_requested_at(),
        )
        store.save_result(
            _review_approved_result(),
            run_id="run_review_approved",
            created_at=datetime(2026, 5, 18, 10, 5, tzinfo=timezone.utc),
        )
        store.save_result(
            _review_rejected_result(),
            run_id="run_review_rejected",
            created_at=datetime(2026, 5, 18, 10, 10, tzinfo=timezone.utc),
        )
        return (
            store.get_run("run_completed"),
            store.get_run("run_review_approved"),
            store.get_run("run_review_rejected"),
        )
    finally:
        store.close()


def _completed_result(order_id: str):
    return FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id=order_id,
            requested_at=_requested_at(),
        )
    )


def _review_approved_result():
    platform = FinTechPlatform()
    review_result = _risk_review_result(platform, "order_review_approved")
    return platform.approve_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Verified customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )


def _review_rejected_result():
    platform = FinTechPlatform()
    review_result = _risk_review_result(platform, "order_review_rejected")
    return platform.reject_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Could not verify customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )


def _risk_review_result(platform: FinTechPlatform, order_id: str):
    return platform.process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id=order_id,
            requested_at=_requested_at(),
        )
    )


def _approved_application():
    return build_individual_application(
        "cust_001",
        "Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
    )


def _requested_at() -> datetime:
    return datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)


def _database_path() -> Path:
    return _test_data_directory() / f"platform-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"consistency-report-{uuid4()}"
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
