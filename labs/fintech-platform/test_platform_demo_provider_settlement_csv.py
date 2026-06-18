from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from demo import _write_provider_settlement_csv
from platform_payment_provider import parse_provider_settlement_csv
from platform_settlement_reconciliation_report import PROVIDER_SETTLEMENT_SETTLED
from sqlite_platform_store import PlatformRunRecord, PlatformRunSnapshot


def test_demo_provider_settlement_csv_is_parsed_into_provider_rows() -> None:
    output_directory = _output_directory()
    try:
        csv_path = _write_provider_settlement_csv(
            output_directory,
            (
                _snapshot(
                    run_id="run_completed",
                    status="completed",
                    payment_order_id="order_completed",
                    user_wallet_balance=Decimal("100.00"),
                ),
                _snapshot(
                    run_id="run_rejected",
                    status="risk_review_rejected",
                    payment_order_id="order_rejected",
                    user_wallet_balance=Decimal("0.00"),
                ),
            ),
        )

        rows = parse_provider_settlement_csv(csv_path.read_text(encoding="utf-8"))

        assert csv_path.name == "provider_settlement_sample.csv"
        assert len(rows) == 1
        row = rows[0]
        assert row.provider == "sample_provider"
        assert row.settlement_id == "settlement_run_completed"
        assert row.provider_payment_id == "sample_provider_intent_run_completed"
        assert row.platform_run_id == "run_completed"
        assert row.payment_order_id == "order_completed"
        assert row.amount == Decimal("100.00")
        assert row.currency == "USD"
        assert row.status == PROVIDER_SETTLEMENT_SETTLED
    finally:
        _remove_directory(output_directory)


def _snapshot(
    *,
    run_id: str,
    status: str,
    payment_order_id: str | None,
    user_wallet_balance: Decimal,
) -> PlatformRunSnapshot:
    return PlatformRunSnapshot(
        record=PlatformRunRecord(
            run_id=run_id,
            customer_id="cust_001",
            status=status,
            kyc_status="approved",
            payment_order_id=payment_order_id,
            payment_order_status="succeeded" if payment_order_id else None,
            risk_status="approved",
            risk_review_case_id=None,
            ledger_transaction_id="ledger_txn_001",
            platform_bank_balance=user_wallet_balance,
            user_wallet_balance=user_wallet_balance,
            audit_event_count=0,
            created_at=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
        ),
        audit_events=(),
    )


def _output_directory() -> Path:
    directory = Path(__file__).with_name(".test-data") / f"demo-provider-{uuid4()}"
    directory.mkdir(parents=True)
    return directory


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
