from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import ComplianceAuditEvent
from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_ledger_reconciliation_report import (
    evaluate_platform_ledger_reconciliation,
    export_platform_ledger_reconciliation_report,
)
from sqlite_platform_store import PlatformRunSnapshot, SQLitePlatformStore


def test_ledger_reconciliation_passes_completed_platform_run() -> None:
    findings = evaluate_platform_ledger_reconciliation((_completed_snapshot(),))

    assert {finding.status for finding in findings} == {"passed"}
    assert {
        finding.check_id
        for finding in findings
    } == {
        "completed_ledger_amount_matches_payment_order",
        "completed_balances_match_ledger_amount",
    }


def test_ledger_reconciliation_detects_ledger_amount_mismatch() -> None:
    snapshot = _completed_snapshot()
    broken = PlatformRunSnapshot(
        record=snapshot.record,
        audit_events=tuple(
            _ledger_event_with_amount(event, "99.99")
            if event.event_type == "ledger_transaction.posted"
            else event
            for event in snapshot.audit_events
        ),
    )

    findings = evaluate_platform_ledger_reconciliation((broken,))

    assert any(
        finding.check_id == "completed_ledger_amount_matches_payment_order"
        and finding.status == "failed"
        and "payment amount 100.00 but ledger amount 99.99" in finding.message
        for finding in findings
    )


def test_ledger_reconciliation_detects_balance_mismatch() -> None:
    snapshot = _completed_snapshot()
    broken = PlatformRunSnapshot(
        record=replace(
            snapshot.record,
            platform_bank_balance=Decimal("100.00"),
            user_wallet_balance=Decimal("90.00"),
        ),
        audit_events=snapshot.audit_events,
    )

    findings = evaluate_platform_ledger_reconciliation((broken,))

    assert any(
        finding.check_id == "completed_balances_match_ledger_amount"
        and finding.status == "failed"
        and "platform_bank_balance=100.00 user_wallet_balance=90.00 ledger_amount=100.00"
        in finding.message
        for finding in findings
    )


def test_ledger_reconciliation_detects_non_posting_state_with_ledger_artifacts() -> None:
    snapshot = _review_rejected_snapshot()
    broken = PlatformRunSnapshot(
        record=replace(
            snapshot.record,
            platform_bank_balance=Decimal("10.00"),
            user_wallet_balance=Decimal("10.00"),
        ),
        audit_events=(
            *snapshot.audit_events,
            _ledger_event(
                ledger_transaction_id="unexpected_ledger_txn",
                payment_order_id=snapshot.record.payment_order_id or "order_rejected",
                amount="10.00",
            ),
        ),
    )

    findings = evaluate_platform_ledger_reconciliation((broken,))

    assert any(
        finding.check_id == "non_posting_run_has_no_ledger_artifacts"
        and finding.status == "failed"
        and "must not have ledger events or non-zero balances" in finding.message
        for finding in findings
    )


def test_export_platform_ledger_reconciliation_report_writes_csv_and_escaped_html() -> None:
    output_directory = _output_directory()
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)

    try:
        store.save_result(
            _completed_result(order_id="order_<script>"),
            run_id="run_<script>",
            created_at=_requested_at(),
        )
        paths = export_platform_ledger_reconciliation_report(
            output_directory,
            snapshots=(store.get_run("run_<script>"),),
        )

        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert paths.findings_csv.exists()
        assert paths.html_report.exists()
        assert "run_id,check_id,status,severity,message" in findings_csv
        assert "completed_balances_match_ledger_amount,passed" in findings_csv
        assert "FinTech Platform Ledger Reconciliation Report" in html_report
        assert "run_&lt;script&gt;" in html_report
        assert "run_<script>" not in html_report
    finally:
        store.close()
        _remove_directory(output_directory)


def _completed_snapshot() -> PlatformRunSnapshot:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            _completed_result(order_id="order_completed"),
            run_id="run_completed",
            created_at=_requested_at(),
        )
        return store.get_run("run_completed")
    finally:
        store.close()


def _review_rejected_snapshot() -> PlatformRunSnapshot:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            _review_rejected_result(),
            run_id="run_review_rejected",
            created_at=_requested_at(),
        )
        return store.get_run("run_review_rejected")
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


def _review_rejected_result():
    platform = FinTechPlatform()
    review_result = platform.process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_review_rejected",
            requested_at=_requested_at(),
        )
    )
    return platform.reject_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Could not verify customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )


def _ledger_event_with_amount(
    event: ComplianceAuditEvent,
    amount: str,
) -> ComplianceAuditEvent:
    payload = json.loads(event.payload)
    payload["amount"] = amount
    return ComplianceAuditEvent(
        source_system=event.source_system,
        event_id=event.event_id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        actor=event.actor,
        reason=event.reason,
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        occurred_at=event.occurred_at,
    )


def _ledger_event(
    *,
    ledger_transaction_id: str,
    payment_order_id: str,
    amount: str,
) -> ComplianceAuditEvent:
    return ComplianceAuditEvent(
        source_system="ledger",
        event_id=f"ledger_transaction.posted:{ledger_transaction_id}",
        event_type="ledger_transaction.posted",
        aggregate_type="ledger_transaction",
        aggregate_id=ledger_transaction_id,
        actor="payment_service",
        reason="Unexpected ledger transaction posted",
        payload=json.dumps(
            {
                "ledger_transaction_id": ledger_transaction_id,
                "payment_order_id": payment_order_id,
                "amount": amount,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        occurred_at=_requested_at(),
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
    return _test_data_directory() / f"ledger-reconciliation-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"ledger-reconciliation-report-{uuid4()}"
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
