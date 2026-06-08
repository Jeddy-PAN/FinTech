from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_REJECTED,
    OperationApprovalError,
    OperationApprovalRecord,
    SQLiteOperationApprovalStore,
)


def test_operation_approval_store_saves_and_reads_approved_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    record = _approval_record(
        approval_id="approval_001",
        status=OPERATION_APPROVAL_APPROVED,
    )

    try:
        store.save_record(record)

        saved = store.get_record("approval_001")
        assert saved == record
        assert store.records == (record,)
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_queries_rejected_records() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    approved = _approval_record(
        approval_id="approval_approved",
        operation_id="run_approved",
        status=OPERATION_APPROVAL_APPROVED,
    )
    rejected = _approval_record(
        approval_id="approval_rejected",
        operation_id="run_rejected",
        status=OPERATION_APPROVAL_REJECTED,
        requested_by="ops_user_001",
        approved_by="ops_user_001",
        decision_reason="retry approver must differ from actor",
    )

    try:
        store.save_record(approved)
        store.save_record(rejected)

        assert store.query_records(status=OPERATION_APPROVAL_REJECTED) == (rejected,)
        assert store.query_records(operation_id="run_approved") == (approved,)
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_rejects_approved_self_approval() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)

    try:
        with pytest.raises(OperationApprovalError, match="approved_by must differ"):
            store.save_record(
                _approval_record(
                    requested_by="ops_user_001",
                    approved_by="ops_user_001",
                    status=OPERATION_APPROVAL_APPROVED,
                )
            )
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_rejects_unknown_status() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)

    try:
        with pytest.raises(OperationApprovalError, match="Unknown approval status"):
            store.save_record(_approval_record(status="pending"))
    finally:
        store.close()
        _remove_database(database_path)


def _approval_record(
    *,
    approval_id: str = "approval_001",
    operation_type: str = "retry_platform_async_run",
    operation_id: str = "run_retry_http",
    target: str = "fintech_platform_api_async_payment_runs/run_retry_http",
    requested_by: str = "ops_user_001",
    request_reason: str = "Retry after transient worker failure",
    approved_by: str = "ops_manager_001",
    approval_reason: str = "Approved retry after reviewing worker failure",
    status: str,
    decision_reason: str = "approved",
) -> OperationApprovalRecord:
    return OperationApprovalRecord(
        approval_id=approval_id,
        operation_type=operation_type,
        operation_id=operation_id,
        target=target,
        requested_by=requested_by,
        request_reason=request_reason,
        approved_by=approved_by,
        approval_reason=approval_reason,
        status=status,
        decision_reason=decision_reason,
        requested_at=_now(),
        decided_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)


def _database_path() -> Path:
    return _test_data_directory() / f"operation-approval-{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()
