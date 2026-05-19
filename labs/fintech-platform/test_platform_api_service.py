from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from platform_api_service import (
    PlatformApiPaymentRequest,
    PlatformApiService,
    PlatformApiServiceError,
    service_error_response,
)
from sqlite_platform_store import SQLitePlatformStore, SQLitePlatformStoreError


def test_platform_api_service_creates_and_persists_payment_run() -> None:
    store = SQLitePlatformStore(_database_path())
    service = PlatformApiService(store=store)
    try:
        response = service.create_payment_run(_api_request())

        assert response["run_id"] == "run_api_001"
        assert response["status"] == "completed"
        assert response["kyc_status"] == "approved"
        assert response["payment_order_status"] == "succeeded"
        assert response["risk_status"] == "approved"
        assert response["platform_bank_balance"] == "100.00"
        assert response["user_wallet_balance"] == "100.00"
        assert response["audit_event_count"] == 5
        assert response["idempotent_replay"] is False
        assert [event["event_type"] for event in response["audit_events"]] == [
            "kyc_decision.saved",
            "payment_order.created",
            "risk_decision.saved",
            "payment_order.succeeded",
            "ledger_transaction.posted",
        ]

        stored = store.get_run("run_api_001")
        assert stored.record.status == "completed"
        assert stored.record.payment_order_id == "order_api_001"
    finally:
        _close_and_remove(store)


def test_platform_api_service_replays_existing_run_for_same_run_id() -> None:
    store = SQLitePlatformStore(_database_path())
    service = PlatformApiService(store=store)
    try:
        first_response = service.create_payment_run(_api_request())
        replay_response = service.create_payment_run(_api_request())

        assert first_response["idempotent_replay"] is False
        assert replay_response["idempotent_replay"] is True
        assert replay_response["run_id"] == "run_api_001"
        assert replay_response["payment_order_id"] == "order_api_001"
        assert replay_response["platform_bank_balance"] == "100.00"
        assert len(store.runs) == 1
    finally:
        _close_and_remove(store)


def test_platform_api_service_rejects_same_run_id_with_different_fingerprint() -> None:
    store = SQLitePlatformStore(_database_path())
    service = PlatformApiService(store=store)
    try:
        service.create_payment_run(_api_request())

        with pytest.raises(PlatformApiServiceError, match="different request fingerprint"):
            service.create_payment_run(
                _api_request(amount="999.00", order_id="order_changed")
            )
    finally:
        _close_and_remove(store)


def test_platform_api_service_gets_payment_run() -> None:
    store = SQLitePlatformStore(_database_path())
    service = PlatformApiService(store=store)
    try:
        service.create_payment_run(_api_request())

        response = service.get_payment_run("run_api_001")

        assert response["run_id"] == "run_api_001"
        assert response["status"] == "completed"
        assert response["idempotent_replay"] is False
        assert len(response["audit_events"]) == 5
    finally:
        _close_and_remove(store)


def test_platform_api_service_lists_payment_runs_with_filters() -> None:
    store = SQLitePlatformStore(_database_path())
    service = PlatformApiService(store=store)
    try:
        service.create_payment_run(_api_request(run_id="run_completed", order_id="order_001"))
        service.create_payment_run(
            _api_request(
                run_id="run_review",
                order_id="order_review",
                amount="1500.00",
            )
        )

        all_runs = service.list_payment_runs()
        review_runs = service.list_payment_runs(status="risk_review_required")
        customer_runs = service.list_payment_runs(customer_id="cust_001")

        assert [run["run_id"] for run in all_runs] == [
            "run_completed",
            "run_review",
        ]
        assert [run["run_id"] for run in review_runs] == ["run_review"]
        assert [run["run_id"] for run in customer_runs] == [
            "run_completed",
            "run_review",
        ]
    finally:
        _close_and_remove(store)


def test_platform_api_service_rejects_invalid_request_values() -> None:
    store = SQLitePlatformStore(_database_path())
    service = PlatformApiService(store=store)
    try:
        with pytest.raises(PlatformApiServiceError, match="run_id is required"):
            service.create_payment_run(_api_request(run_id=" "))
        with pytest.raises(PlatformApiServiceError, match="amount must be positive"):
            service.create_payment_run(_api_request(run_id="run_invalid", amount="0"))
        with pytest.raises(PlatformApiServiceError, match="timezone-aware"):
            service.create_payment_run(
                _api_request(
                    run_id="run_naive",
                    requested_at=datetime(2026, 5, 19, 9, 0),
                )
            )
    finally:
        _close_and_remove(store)


def test_platform_api_service_error_response_maps_expected_errors() -> None:
    response = service_error_response(SQLitePlatformStoreError("Unknown platform run"))

    assert response == {
        "error": "SQLitePlatformStoreError",
        "message": "Unknown platform run",
    }


def _api_request(
    *,
    run_id: str = "run_api_001",
    amount: str = "100.00",
    order_id: str = "order_api_001",
    requested_at: datetime = datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc),
) -> PlatformApiPaymentRequest:
    return PlatformApiPaymentRequest(
        run_id=run_id,
        customer_id="cust_001",
        full_name="Jordan Smith",
        date_of_birth=date(1992, 5, 20),
        country="US",
        address="100 Market Street",
        identification_number="ID-1001",
        expected_monthly_volume_cents=250_000,
        amount=amount,
        currency="USD",
        order_id=order_id,
        requested_at=requested_at,
        device_id="device_known",
        ip_country="US",
        beneficiary_id="beneficiary_001",
        actor="api_client_001",
    )


def _database_path() -> Path:
    return _test_data_directory() / f"platform-api-{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _close_and_remove(store: SQLitePlatformStore) -> None:
    database_path = store.database_path
    store.close()
    if database_path.exists():
        database_path.unlink()
