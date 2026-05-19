from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from fintech_platform import (
    FinTechPlatform,
    PlatformPaymentRequest,
    PlatformPaymentStatus,
)
from kyc_aml import build_individual_application
from sqlite_platform_store import SQLitePlatformStore, SQLitePlatformStoreError


def test_sqlite_platform_store_saves_and_loads_run_snapshot() -> None:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    result = _approved_result()

    try:
        record = store.save_result(
            result,
            run_id="run_001",
            created_at=_requested_at(),
        )
        snapshot = store.get_run("run_001")

        assert record.run_id == "run_001"
        assert snapshot.record.status == PlatformPaymentStatus.COMPLETED.value
        assert snapshot.record.customer_id == "cust_001"
        assert snapshot.record.payment_order_id == "order_001"
        assert snapshot.record.payment_order_status == "succeeded"
        assert snapshot.record.risk_status == "approved"
        assert snapshot.record.ledger_transaction_id == result.ledger_transaction_id
        assert snapshot.record.audit_event_count == 5
        assert [event.event_type for event in snapshot.audit_events] == [
            "kyc_decision.saved",
            "payment_order.created",
            "risk_decision.saved",
            "payment_order.succeeded",
            "ledger_transaction.posted",
        ]
    finally:
        store.close()


def test_sqlite_platform_store_lists_and_queries_runs() -> None:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)

    try:
        store.save_result(
            _approved_result(order_id="order_001"),
            run_id="run_completed",
            created_at=_requested_at(),
        )
        store.save_result(
            _risk_review_result(),
            run_id="run_review",
            created_at=datetime(2026, 5, 18, 9, 5, tzinfo=timezone.utc),
        )

        assert [record.run_id for record in store.runs] == [
            "run_completed",
            "run_review",
        ]
        assert [record.run_id for record in store.query_runs(status="completed")] == [
            "run_completed",
        ]
        assert [
            record.run_id
            for record in store.query_runs(
                status=PlatformPaymentStatus.RISK_REVIEW_REQUIRED
            )
        ] == ["run_review"]
        assert [record.run_id for record in store.query_runs(customer_id="cust_001")] == [
            "run_completed",
            "run_review",
        ]
    finally:
        store.close()


def test_sqlite_platform_store_updates_existing_run() -> None:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)

    try:
        store.save_result(
            _risk_review_result(),
            run_id="run_001",
            created_at=_requested_at(),
        )
        store.save_result(
            _approved_result(order_id="order_updated"),
            run_id="run_001",
            created_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        )

        snapshot = store.get_run("run_001")
        assert snapshot.record.status == "completed"
        assert snapshot.record.payment_order_id == "order_updated"
        assert snapshot.record.audit_event_count == 5
        assert len(snapshot.audit_events) == 5
        assert len(store.runs) == 1
    finally:
        store.close()


def test_sqlite_platform_store_saves_completed_review_result() -> None:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)
    platform = FinTechPlatform()
    review_result = platform.process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_review_approved",
            requested_at=_requested_at(),
        )
    )
    completed = platform.approve_risk_review(
        review_result,
        reviewed_by="risk_manager_001",
        reason="Verified customer activity",
        reviewed_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )

    try:
        store.save_result(
            completed,
            run_id="run_review_approved",
            created_at=datetime(2026, 5, 18, 10, 5, tzinfo=timezone.utc),
        )
        snapshot = store.get_run("run_review_approved")

        assert snapshot.record.status == "completed"
        assert snapshot.record.risk_review_case_id == "review:order_review_approved"
        assert snapshot.record.payment_order_status == "succeeded"
        assert snapshot.record.audit_event_count == 7
        assert [event.event_type for event in snapshot.audit_events][-3:] == [
            "review_case.approved",
            "payment_order.succeeded",
            "ledger_transaction.posted",
        ]
    finally:
        store.close()


def test_sqlite_platform_store_rejects_unknown_run() -> None:
    database_path = _database_path()
    store = SQLitePlatformStore(database_path)

    try:
        with pytest.raises(SQLitePlatformStoreError, match="Unknown platform run"):
            store.get_run("missing_run")
    finally:
        store.close()


def _approved_result(order_id: str = "order_001"):
    return FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="100.00",
            currency="USD",
            order_id=order_id,
            requested_at=_requested_at(),
        )
    )


def _risk_review_result():
    return FinTechPlatform().process_payment(
        PlatformPaymentRequest(
            application=_approved_application(),
            amount="1500.00",
            currency="USD",
            order_id="order_review",
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


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory
