from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api_app import RETRY_PLATFORM_ASYNC_PAYMENT_RUN, create_app
from platform_async_service import PlatformAsyncWorker, SQLitePlatformAsyncRunStore
from platform_operation_approval import (
    OPERATION_APPROVAL_PENDING,
    OperationApprovalRecord,
    SQLiteOperationApprovalStore,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore
from sqlite_platform_store import SQLitePlatformStore


def create_failed_async_run_sample(client: TestClient, **kwargs):
    spec = importlib.util.spec_from_file_location(
        "fintech_platform_demo",
        Path(__file__).with_name("demo.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load fintech platform demo module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_failed_async_run_sample(client, **kwargs)


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


def _client_with_investigation():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    investigation_database_path = _investigation_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                investigation_database_path=investigation_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        investigation_database_path,
    )


def _client_with_async():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
    )


def _client_with_async_and_operation_approval():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    operation_approval_database_path = _operation_approval_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
                operation_approval_database_path=operation_approval_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
        operation_approval_database_path,
    )


def _client_with_operability():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    investigation_database_path = _investigation_database_path()
    operation_approval_database_path = _operation_approval_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
                investigation_database_path=investigation_database_path,
                operation_approval_database_path=operation_approval_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
        investigation_database_path,
        operation_approval_database_path,
    )


def _client_with_async_and_investigation():
    database_path = _database_path()
    access_audit_database_path = _access_audit_database_path()
    async_database_path = _async_database_path()
    investigation_database_path = _investigation_database_path()
    return (
        TestClient(
            create_app(
                database_path=database_path,
                access_audit_database_path=access_audit_database_path,
                async_database_path=async_database_path,
                investigation_database_path=investigation_database_path,
            )
        ),
        database_path,
        access_audit_database_path,
        async_database_path,
        investigation_database_path,
    )


def _payload(
    *,
    run_id: str = "run_http_001",
    order_id: str = "order_http_001",
    amount: str = "100.00",
    actor: str = "api_client_001",
) -> dict:
    return {
        "run_id": run_id,
        "customer_id": "cust_001",
        "full_name": "Jordan Smith",
        "date_of_birth": "1992-05-20",
        "country": "US",
        "address": "100 Market Street",
        "identification_number": "ID-1001",
        "expected_monthly_volume_cents": 250000,
        "amount": amount,
        "currency": "USD",
        "order_id": order_id,
        "requested_at": "2026-05-19T09:00:00Z",
        "device_id": "device_known",
        "ip_country": "US",
        "beneficiary_id": "beneficiary_001",
        "actor": actor,
    }


def _retry_payload() -> dict:
    return {
        "actor": "ops_user_001",
        "reason": "Retry after transient worker failure",
        "confirmation": "retry_failed_async_run",
    }


def _pending_approval_payload() -> dict:
    return {
        "approval_id": "approval_pending_001",
        "operation_type": RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
        "operation_id": "run_retry_http",
        "target": "fintech_platform_api_async_payment_runs/run_retry_http",
        "requested_by": "ops_user_001",
        "request_reason": "Request retry approval",
        "requested_at": "2026-06-08T09:00:00Z",
    }


def _fail_async_run(
    *,
    database_path: Path,
    async_database_path: Path,
    run_id: str = "run_retry_http",
) -> None:
    async_store = SQLitePlatformAsyncRunStore(async_database_path)
    platform_store = SQLitePlatformStore(database_path)
    try:
        worker = PlatformAsyncWorker(
            async_store=async_store,
            platform_store=platform_store,
            service_factory=lambda: _FailingService(),
        )
        for _ in range(3):
            worker.process_next()
        assert async_store.get_run(run_id).status == "failed"
    finally:
        async_store.close()
        platform_store.close()


class _FailingService:
    def create_payment_run(self, request):  # noqa: ARG002
        raise RuntimeError("temporary failure")


def _database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-{uuid4()}.db"


def _access_audit_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-access-audit-{uuid4()}.db"


def _async_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-async-{uuid4()}.db"


def _operation_approval_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-operation-approval-{uuid4()}.db"


def _investigation_database_path() -> Path:
    return _test_data_directory() / f"platform-api-app-investigation-{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _access_events(database_path: Path):
    store = SQLiteAccessAuditStore(database_path)
    try:
        return store.access_events
    finally:
        store.close()


def _approval_records(database_path: Path):
    store = SQLiteOperationApprovalStore(database_path)
    try:
        return store.records
    finally:
        store.close()


def _save_pending_approval(
    database_path: Path,
    *,
    approval_id: str = "approval_pending_001",
    operation_id: str = "run_retry_http",
    requested_by: str = "ops_user_001",
    requested_at: datetime | None = None,
) -> None:
    store = SQLiteOperationApprovalStore(database_path)
    try:
        store.save_record(
            OperationApprovalRecord(
                approval_id=approval_id,
                operation_type=RETRY_PLATFORM_ASYNC_PAYMENT_RUN,
                operation_id=operation_id,
                target=f"fintech_platform_api_async_payment_runs/{operation_id}",
                requested_by=requested_by,
                request_reason="Request retry approval",
                approved_by=None,
                approval_reason=None,
                status=OPERATION_APPROVAL_PENDING,
                decision_reason="pending approval",
                requested_at=_now() if requested_at is None else requested_at,
                decided_at=None,
            )
        )
    finally:
        store.close()


def _now():
    return datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()
