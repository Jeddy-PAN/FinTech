from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

LAB_DIR = Path(__file__).resolve().parent
KYC_LAB_DIR = LAB_DIR.parent / "kyc-aml-onboarding"
if str(KYC_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(KYC_LAB_DIR))

from fintech_platform import FinTechPlatform, PlatformPaymentRequest
from kyc_aml import build_individual_application
from platform_settlement_reconciliation_report import (
    PROVIDER_SETTLEMENT_SETTLED,
    ProviderSettlementRow,
    evaluate_platform_settlement_reconciliation,
    export_platform_settlement_reconciliation_report,
)
from sqlite_platform_store import PlatformRunSnapshot, SQLitePlatformStore


def test_settlement_reconciliation_passes_completed_run_with_matching_provider_row() -> None:
    snapshot = _completed_snapshot()

    findings = evaluate_platform_settlement_reconciliation(
        (snapshot,),
        provider_rows=(_provider_row(platform_run_id="run_completed"),),
    )

    assert {finding.status for finding in findings} == {"passed"}
    assert {
        finding.check_id
        for finding in findings
    } == {
        "completed_internal_run_has_provider_settlement",
        "provider_settlement_amount_matches_internal_payment",
        "provider_settlement_currency_matches_internal_payment",
    }


def test_settlement_reconciliation_detects_missing_provider_settlement() -> None:
    snapshot = _completed_snapshot()

    findings = evaluate_platform_settlement_reconciliation(
        (snapshot,),
        provider_rows=(),
    )

    assert len(findings) == 1
    assert findings[0].check_id == "completed_internal_run_has_provider_settlement"
    assert findings[0].status == "failed"
    assert "no provider settlement row" in findings[0].message


def test_settlement_reconciliation_detects_amount_mismatch() -> None:
    snapshot = _completed_snapshot()

    findings = evaluate_platform_settlement_reconciliation(
        (snapshot,),
        provider_rows=(
            _provider_row(
                platform_run_id="run_completed",
                amount=Decimal("99.99"),
            ),
        ),
    )

    assert any(
        finding.check_id == "provider_settlement_amount_matches_internal_payment"
        and finding.status == "failed"
        and "Provider settlement amount 99.99 does not match internal amount 100.00"
        in finding.message
        for finding in findings
    )


def test_settlement_reconciliation_detects_external_row_without_internal_run() -> None:
    snapshot = _completed_snapshot()

    findings = evaluate_platform_settlement_reconciliation(
        (snapshot,),
        provider_rows=(
            _provider_row(platform_run_id="run_completed"),
            _provider_row(
                settlement_id="settlement_orphan",
                platform_run_id="run_orphan",
                payment_order_id="order_orphan",
            ),
        ),
    )

    assert any(
        finding.check_id == "provider_settlement_has_internal_run"
        and finding.run_id == "run_orphan"
        and finding.status == "failed"
        for finding in findings
    )


def test_settlement_reconciliation_detects_settled_provider_row_for_non_completed_run() -> None:
    snapshot = _review_rejected_snapshot()

    findings = evaluate_platform_settlement_reconciliation(
        (snapshot,),
        provider_rows=(
            _provider_row(
                platform_run_id="run_review_rejected",
                payment_order_id="order_review_rejected",
                amount=Decimal("1500.00"),
            ),
        ),
    )

    assert len(findings) == 1
    assert findings[0].check_id == "non_completed_internal_run_has_no_provider_settlement"
    assert findings[0].status == "failed"
    assert "internal_status=risk_review_rejected" in findings[0].message


def test_settlement_reconciliation_rejects_invalid_provider_rows() -> None:
    snapshot = _completed_snapshot()

    with pytest.raises(ValueError, match="Unknown provider settlement status"):
        evaluate_platform_settlement_reconciliation(
            (snapshot,),
            provider_rows=(
                _provider_row(
                    platform_run_id="run_completed",
                    status="unknown",
                ),
            ),
        )

    with pytest.raises(ValueError, match="settled_at must be timezone-aware"):
        evaluate_platform_settlement_reconciliation(
            (snapshot,),
            provider_rows=(
                _provider_row(
                    platform_run_id="run_completed",
                    settled_at=datetime(2026, 5, 19, 9, 0),
                ),
            ),
        )


def test_export_settlement_reconciliation_report_writes_csv_and_escaped_html() -> None:
    output_directory = _output_directory()
    snapshot = _completed_snapshot(run_id="run_<script>", order_id="order_<script>")

    try:
        paths = export_platform_settlement_reconciliation_report(
            output_directory,
            snapshots=(snapshot,),
            provider_rows=(
                _provider_row(
                    platform_run_id="run_<script>",
                    payment_order_id="order_<script>",
                ),
            ),
        )

        findings_csv = paths.findings_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert paths.findings_csv.exists()
        assert paths.html_report.exists()
        assert "run_id,settlement_id,check_id,status,severity,message" in findings_csv
        assert "provider_settlement_amount_matches_internal_payment,passed" in findings_csv
        assert "FinTech Platform Settlement Reconciliation Report" in html_report
        assert "run_&lt;script&gt;" in html_report
        assert "run_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _completed_snapshot(
    *,
    run_id: str = "run_completed",
    order_id: str = "order_completed",
) -> PlatformRunSnapshot:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    try:
        store.save_result(
            FinTechPlatform().process_payment(
                PlatformPaymentRequest(
                    application=_approved_application(),
                    amount="100.00",
                    currency="USD",
                    order_id=order_id,
                    requested_at=_requested_at(),
                )
            ),
            run_id=run_id,
            created_at=_requested_at(),
        )
        return store.get_run(run_id)
    finally:
        store.close()


def _review_rejected_snapshot() -> PlatformRunSnapshot:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    platform = FinTechPlatform()
    try:
        review_result = platform.process_payment(
            PlatformPaymentRequest(
                application=_approved_application(),
                amount="1500.00",
                currency="USD",
                order_id="order_review_rejected",
                requested_at=_requested_at(),
            )
        )
        rejected = platform.reject_risk_review(
            review_result,
            reviewed_by="risk_manager_001",
            reason="Could not verify customer activity",
            reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        )
        store.save_result(
            rejected,
            run_id="run_review_rejected",
            created_at=_requested_at(),
        )
        return store.get_run("run_review_rejected")
    finally:
        store.close()


def _provider_row(
    *,
    settlement_id: str = "settlement_001",
    platform_run_id: str,
    payment_order_id: str = "order_completed",
    amount: Decimal = Decimal("100.00"),
    currency: str = "USD",
    status: str = PROVIDER_SETTLEMENT_SETTLED,
    settled_at: datetime = datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc),
) -> ProviderSettlementRow:
    return ProviderSettlementRow(
        provider="sample_provider",
        settlement_id=settlement_id,
        provider_payment_id=f"provider_payment_{payment_order_id}",
        platform_run_id=platform_run_id,
        payment_order_id=payment_order_id,
        amount=amount,
        currency=currency,
        status=status,
        settled_at=settled_at,
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
    return _test_data_directory() / f"settlement-reconciliation-{uuid4()}.db"


def _output_directory() -> Path:
    directory = _test_data_directory() / f"settlement-reconciliation-report-{uuid4()}"
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
