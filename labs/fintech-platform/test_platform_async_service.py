from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from platform_api_service import PlatformApiPaymentRequest
from platform_async_service import (
    ASYNC_RUN_ACCEPTED,
    ASYNC_RUN_COMPLETED,
    ASYNC_RUN_FAILED,
    ASYNC_RUN_PROCESSING,
    PlatformAsyncRunStoreError,
    PlatformAsyncWorker,
    SQLitePlatformAsyncRunStore,
    rebuild_api_request,
)
from sqlite_platform_store import SQLitePlatformStore


def test_async_run_store_creates_accepted_run() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        result = store.create_run(
            _api_request(),
            created_at=_created_at(),
        )

        assert result.idempotent_replay is False
        assert result.run.run_id == "run_async_001"
        assert result.run.status == ASYNC_RUN_ACCEPTED
        assert result.run.attempt_count == 0
        assert result.run.max_attempts == 3
        assert result.run.last_error is None
        assert result.run.created_at == _created_at()
        assert result.run.updated_at == _created_at()
        assert result.run.request_payload["customer_id"] == "cust_001"
        assert result.run.request_payload["amount"] == "100.00"
        assert len(result.run.request_fingerprint) == 64

        stored = store.get_run("run_async_001")
        assert stored == result.run
    finally:
        _close_and_remove(store)


def test_async_run_store_replays_same_run_id_with_same_fingerprint() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        first = store.create_run(_api_request(), created_at=_created_at())
        replay = store.create_run(
            _api_request(),
            created_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
        )

        assert first.idempotent_replay is False
        assert replay.idempotent_replay is True
        assert replay.run.run_id == "run_async_001"
        assert replay.run.created_at == _created_at()
        assert len(store.runs) == 1
    finally:
        _close_and_remove(store)


def test_async_run_store_rejects_same_run_id_with_different_fingerprint() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        store.create_run(_api_request(), created_at=_created_at())

        with pytest.raises(PlatformAsyncRunStoreError, match="different request fingerprint"):
            store.create_run(
                _api_request(amount="250.00", order_id="order_changed"),
                created_at=_created_at(),
            )
    finally:
        _close_and_remove(store)


def test_async_run_store_queries_runs_by_status() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        store.create_run(
            _api_request(run_id="run_async_001", order_id="order_001"),
            created_at=_created_at(),
        )
        store.create_run(
            _api_request(run_id="run_async_002", order_id="order_002"),
            created_at=datetime(2026, 5, 20, 9, 5, tzinfo=timezone.utc),
        )

        assert [run.run_id for run in store.runs] == [
            "run_async_001",
            "run_async_002",
        ]
        assert [run.run_id for run in store.query_runs(status=ASYNC_RUN_ACCEPTED)] == [
            "run_async_001",
            "run_async_002",
        ]
        assert store.query_runs(status="completed") == ()
    finally:
        _close_and_remove(store)


def test_async_run_store_claims_next_accepted_run_once_across_connections() -> None:
    database_path = _database_path()
    first_store = SQLitePlatformAsyncRunStore(database_path)
    second_store = SQLitePlatformAsyncRunStore(database_path)
    try:
        first_store.create_run(_api_request(), created_at=_created_at())

        claimed = first_store.claim_next_accepted(started_at=_processed_at())
        duplicate_claim = second_store.claim_next_accepted(started_at=_processed_at())

        assert claimed is not None
        assert claimed.run_id == "run_async_001"
        assert claimed.status == ASYNC_RUN_PROCESSING
        assert claimed.attempt_count == 1
        assert duplicate_claim is None
        assert second_store.get_run("run_async_001").status == ASYNC_RUN_PROCESSING

        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot process processing"):
            second_store.mark_processing("run_async_001", started_at=_processed_at())
    finally:
        first_store.close()
        second_store.close()
        if database_path.exists():
            database_path.unlink()


def test_async_run_store_survives_reopen_and_can_rebuild_request() -> None:
    database_path = _database_path()
    store = SQLitePlatformAsyncRunStore(database_path)
    try:
        store.create_run(_api_request(), created_at=_created_at())
    finally:
        store.close()

    reopened = SQLitePlatformAsyncRunStore(database_path)
    try:
        run = reopened.get_run("run_async_001")
        rebuilt = rebuild_api_request(run.request_payload)

        assert run.status == ASYNC_RUN_ACCEPTED
        assert rebuilt.run_id == "run_async_001"
        assert rebuilt.date_of_birth == date(1992, 5, 20)
        assert rebuilt.requested_at == _requested_at()
    finally:
        _close_and_remove(reopened)


def test_async_worker_processes_next_accepted_run_to_completed() -> None:
    async_store = SQLitePlatformAsyncRunStore(_database_path())
    platform_store = SQLitePlatformStore(_database_path())
    try:
        async_store.create_run(_api_request(), created_at=_created_at())
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
        )

        result = worker.process_next(processed_at=_processed_at())

        assert result.processed is True
        assert result.run_id == "run_async_001"
        assert result.async_status == ASYNC_RUN_COMPLETED
        assert result.platform_status == "completed"

        async_run = async_store.get_run("run_async_001")
        assert async_run.status == ASYNC_RUN_COMPLETED
        assert async_run.attempt_count == 1
        assert async_run.started_at == _processed_at()
        assert async_run.completed_at == _processed_at()
        assert async_run.last_error is None

        platform_snapshot = platform_store.get_run("run_async_001")
        assert platform_snapshot.record.status == "completed"
        assert platform_snapshot.record.payment_order_id == "order_async_001"
    finally:
        _close_and_remove(async_store)
        _close_and_remove_platform_store(platform_store)


def test_async_worker_returns_not_processed_when_no_accepted_run() -> None:
    async_store = SQLitePlatformAsyncRunStore(_database_path())
    platform_store = SQLitePlatformStore(_database_path())
    try:
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
        )

        result = worker.process_next(processed_at=_processed_at())

        assert result.processed is False
        assert result.run_id is None
        assert result.async_status is None
    finally:
        _close_and_remove(async_store)
        _close_and_remove_platform_store(platform_store)


def test_async_worker_retries_failure_until_max_attempts() -> None:
    async_store = SQLitePlatformAsyncRunStore(_database_path())
    platform_store = SQLitePlatformStore(_database_path())
    try:
        async_store.create_run(
            _api_request(run_id="run_failing"),
            created_at=_created_at(),
            max_attempts=2,
        )
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
            service_factory=lambda: _FailingService(),
        )

        first = worker.process_next(processed_at=_processed_at())
        first_run = async_store.get_run("run_failing")
        second = worker.process_next(
            processed_at=datetime(2026, 5, 20, 9, 6, tzinfo=timezone.utc)
        )
        second_run = async_store.get_run("run_failing")

        assert first.processed is True
        assert first.async_status == ASYNC_RUN_ACCEPTED
        assert "temporary failure" in first.error
        assert first_run.status == ASYNC_RUN_ACCEPTED
        assert first_run.attempt_count == 1
        assert first_run.last_error == "temporary failure"

        assert second.processed is True
        assert second.async_status == ASYNC_RUN_FAILED
        assert "temporary failure" in second.error
        assert second_run.status == ASYNC_RUN_FAILED
        assert second_run.attempt_count == 2
        assert second_run.completed_at == datetime(
            2026, 5, 20, 9, 6, tzinfo=timezone.utc
        )
    finally:
        _close_and_remove(async_store)
        _close_and_remove_platform_store(platform_store)


def test_async_run_store_retries_failed_run_to_accepted() -> None:
    async_store = SQLitePlatformAsyncRunStore(_database_path())
    platform_store = SQLitePlatformStore(_database_path())
    try:
        async_store.create_run(
            _api_request(run_id="run_retry"),
            created_at=_created_at(),
            max_attempts=1,
        )
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
            service_factory=lambda: _FailingService(),
        )
        failed = worker.process_next(processed_at=_processed_at())

        retried_at = datetime(2026, 5, 20, 9, 10, tzinfo=timezone.utc)
        retried = async_store.retry_failed("run_retry", retried_at=retried_at)

        assert failed.async_status == ASYNC_RUN_FAILED
        assert retried.run_id == "run_retry"
        assert retried.status == ASYNC_RUN_ACCEPTED
        assert retried.attempt_count == 1
        assert retried.max_attempts == 1
        assert retried.last_error is None
        assert retried.completed_at is None
        assert retried.updated_at == retried_at
        assert retried.request_payload["amount"] == "100.00"
        assert retried.request_fingerprint == async_store.get_run(
            "run_retry"
        ).request_fingerprint
    finally:
        _close_and_remove(async_store)
        _close_and_remove_platform_store(platform_store)


def test_async_run_store_rejects_retry_for_non_failed_runs() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        store.create_run(
            _api_request(run_id="run_accepted", order_id="order_accepted"),
            created_at=_created_at(),
        )
        store.create_run(
            _api_request(run_id="run_processing", order_id="order_processing"),
            created_at=datetime(2026, 5, 20, 9, 2, tzinfo=timezone.utc),
        )
        store.create_run(
            _api_request(run_id="run_completed", order_id="order_completed"),
            created_at=datetime(2026, 5, 20, 9, 3, tzinfo=timezone.utc),
        )

        store.mark_processing("run_processing", started_at=_processed_at())
        store.mark_processing("run_completed", started_at=_processed_at())
        store.mark_completed("run_completed", completed_at=_processed_at())

        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot retry accepted"):
            store.retry_failed("run_accepted", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot retry processing"):
            store.retry_failed("run_processing", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot retry completed"):
            store.retry_failed("run_completed", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="Unknown platform async run"):
            store.retry_failed("missing_run", retried_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="timezone-aware"):
            store.retry_failed(
                "run_accepted",
                retried_at=datetime(2026, 5, 20, 9, 10),
            )
    finally:
        _close_and_remove(store)


def test_async_worker_processes_pending_runs_up_to_limit() -> None:
    async_store = SQLitePlatformAsyncRunStore(_database_path())
    platform_store = SQLitePlatformStore(_database_path())
    try:
        async_store.create_run(
            _api_request(run_id="run_async_001", order_id="order_001"),
            created_at=_created_at(),
        )
        async_store.create_run(
            _api_request(run_id="run_async_002", order_id="order_002"),
            created_at=datetime(2026, 5, 20, 9, 2, tzinfo=timezone.utc),
        )
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
        )

        results = worker.process_pending(limit=1, processed_at=_processed_at())

        assert [result.run_id for result in results] == ["run_async_001"]
        assert async_store.get_run("run_async_001").status == ASYNC_RUN_COMPLETED
        assert async_store.get_run("run_async_002").status == ASYNC_RUN_ACCEPTED
        assert [record.run_id for record in platform_store.runs] == ["run_async_001"]

        with pytest.raises(PlatformAsyncRunStoreError, match="limit must be positive"):
            worker.process_pending(limit=0)
    finally:
        _close_and_remove(async_store)
        _close_and_remove_platform_store(platform_store)


def test_async_run_store_rejects_invalid_status_transitions() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        store.create_run(_api_request(), created_at=_created_at())

        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot complete accepted"):
            store.mark_completed("run_async_001", completed_at=_processed_at())

        processing = store.mark_processing("run_async_001", started_at=_processed_at())
        assert processing.status == ASYNC_RUN_PROCESSING

        with pytest.raises(PlatformAsyncRunStoreError, match="Cannot process processing"):
            store.mark_processing("run_async_001", started_at=_processed_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="error_message is required"):
            store.mark_failed("run_async_001", error_message=" ", failed_at=_processed_at())
    finally:
        _close_and_remove(store)


def test_async_run_store_rejects_invalid_inputs() -> None:
    store = SQLitePlatformAsyncRunStore(_database_path())
    try:
        with pytest.raises(PlatformAsyncRunStoreError, match="run_id is required"):
            store.create_run(_api_request(run_id=" "), created_at=_created_at())
        with pytest.raises(PlatformAsyncRunStoreError, match="timezone-aware"):
            store.create_run(
                _api_request(
                    run_id="run_naive",
                    requested_at=datetime(2026, 5, 20, 9, 0),
                ),
                created_at=_created_at(),
            )
        with pytest.raises(PlatformAsyncRunStoreError, match="timezone-aware"):
            store.create_run(
                _api_request(run_id="run_bad_created_at"),
                created_at=datetime(2026, 5, 20, 9, 0),
            )
        with pytest.raises(PlatformAsyncRunStoreError, match="max_attempts"):
            store.create_run(
                _api_request(run_id="run_bad_attempts"),
                created_at=_created_at(),
                max_attempts=0,
            )
        with pytest.raises(PlatformAsyncRunStoreError, match="Unknown platform async run"):
            store.get_run("missing_run")
        with pytest.raises(PlatformAsyncRunStoreError, match="Unknown platform async run status"):
            store.query_runs(status="unknown")
    finally:
        _close_and_remove(store)


def _api_request(
    *,
    run_id: str = "run_async_001",
    amount: str = "100.00",
    order_id: str = "order_async_001",
    requested_at: datetime = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
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


def _requested_at() -> datetime:
    return datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)


def _created_at() -> datetime:
    return datetime(2026, 5, 20, 9, 1, tzinfo=timezone.utc)


def _processed_at() -> datetime:
    return datetime(2026, 5, 20, 9, 5, tzinfo=timezone.utc)


def _database_path() -> Path:
    return _test_data_directory() / f"platform-async-{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _close_and_remove(store: SQLitePlatformAsyncRunStore) -> None:
    database_path = store.database_path
    store.close()
    if database_path.exists():
        database_path.unlink()


def _close_and_remove_platform_store(store: SQLitePlatformStore) -> None:
    database_path = store.database_path
    store.close()
    if database_path.exists():
        database_path.unlink()


class _FailingService:
    def create_payment_run(self, request):  # noqa: ARG002
        raise RuntimeError("temporary failure")
