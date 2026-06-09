from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
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


def test_operation_approval_store_saves_and_queries_pending_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)

        saved = store.get_record("approval_pending")
        assert saved == pending
        assert store.query_records(status=OPERATION_APPROVAL_PENDING) == (pending,)
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_sorts_and_paginates_records() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    oldest = _approval_record(
        approval_id="approval_oldest",
        operation_id="run_oldest",
        status=OPERATION_APPROVAL_APPROVED,
        requested_at=_timestamp("2026-06-08T09:00:00+00:00"),
    )
    newest = _approval_record(
        approval_id="approval_newest",
        operation_id="run_newest",
        status=OPERATION_APPROVAL_APPROVED,
        requested_at=_timestamp("2026-06-08T11:00:00+00:00"),
    )
    middle = _approval_record(
        approval_id="approval_middle",
        operation_id="run_middle",
        status=OPERATION_APPROVAL_APPROVED,
        requested_at=_timestamp("2026-06-08T10:00:00+00:00"),
    )

    try:
        store.save_record(oldest)
        store.save_record(newest)
        store.save_record(middle)

        page = store.query_records(
            sort_by="requested_at",
            sort_order="desc",
            limit=2,
            offset=1,
        )

        assert [record.approval_id for record in page] == [
            "approval_middle",
            "approval_oldest",
        ]
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_rejects_unknown_sort_field() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)

    try:
        with pytest.raises(OperationApprovalError, match="Unknown approval sort field"):
            store.query_records(sort_by="created_at")
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_approves_pending_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)

        approved = store.approve_pending(
            "approval_pending",
            approved_by="ops_manager_001",
            approval_reason="Approved after reviewing retry request",
            decided_at=_now(),
        )

        assert approved.status == OPERATION_APPROVAL_APPROVED
        assert approved.approved_by == "ops_manager_001"
        assert approved.approval_reason == "Approved after reviewing retry request"
        assert approved.decision_reason == "approved"
        assert approved.decided_at == _now()
        assert store.get_record("approval_pending") == approved
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_rejects_pending_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)

        rejected = store.reject_pending(
            "approval_pending",
            rejected_by="ops_manager_001",
            rejection_reason="Retry evidence is incomplete",
            decided_at=_now(),
        )

        assert rejected.status == OPERATION_APPROVAL_REJECTED
        assert rejected.approved_by == "ops_manager_001"
        assert rejected.approval_reason == "Retry evidence is incomplete"
        assert rejected.decision_reason == "rejected"
        assert rejected.decided_at == _now()
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_cancels_pending_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)

        cancelled = store.cancel_pending(
            "approval_pending",
            cancelled_by="ops_user_001",
            cancellation_reason="Requester withdrew retry request",
            decided_at=_now(),
        )

        assert cancelled.status == OPERATION_APPROVAL_CANCELLED
        assert cancelled.approved_by == "ops_user_001"
        assert cancelled.approval_reason == "Requester withdrew retry request"
        assert cancelled.decision_reason == "cancelled"
        assert cancelled.decided_at == _now()
        assert store.query_records(status=OPERATION_APPROVAL_CANCELLED) == (cancelled,)
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_expires_pending_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)

        expired = store.expire_pending(
            "approval_pending",
            expired_by="system_scheduler",
            expiration_reason="Approval request exceeded review window",
            decided_at=_now(),
        )

        assert expired.status == OPERATION_APPROVAL_EXPIRED
        assert expired.approved_by == "system_scheduler"
        assert expired.approval_reason == "Approval request exceeded review window"
        assert expired.decision_reason == "expired"
        assert expired.decided_at == _now()
        assert store.query_records(status=OPERATION_APPROVAL_EXPIRED) == (expired,)
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
            store.save_record(_approval_record(status="waiting"))
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_rejects_approving_non_pending_record() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)

    try:
        store.save_record(
            _approval_record(
                approval_id="approval_approved",
                status=OPERATION_APPROVAL_APPROVED,
            )
        )

        with pytest.raises(OperationApprovalError, match="Cannot approve approved"):
            store.approve_pending(
                "approval_approved",
                approved_by="ops_manager_001",
                approval_reason="Duplicate approval",
                decided_at=_now(),
            )
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_rejects_terminal_lifecycle_transitions() -> None:
    database_path = _database_path()
    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)
        store.cancel_pending(
            "approval_pending",
            cancelled_by="ops_user_001",
            cancellation_reason="Requester withdrew retry request",
            decided_at=_now(),
        )

        with pytest.raises(OperationApprovalError, match="Cannot approve cancelled"):
            store.approve_pending(
                "approval_pending",
                approved_by="ops_manager_001",
                approval_reason="Late approval",
                decided_at=_now(),
            )
        with pytest.raises(OperationApprovalError, match="Cannot expire cancelled"):
            store.expire_pending(
                "approval_pending",
                expired_by="system_scheduler",
                expiration_reason="Late expiry",
                decided_at=_now(),
            )
    finally:
        store.close()
        _remove_database(database_path)


def test_operation_approval_store_migrates_legacy_terminal_status_schema() -> None:
    database_path = _database_path()
    _create_legacy_terminal_status_record(database_path)

    store = SQLiteOperationApprovalStore(database_path)
    pending = _approval_record(
        approval_id="approval_pending",
        status=OPERATION_APPROVAL_PENDING,
        approved_by=None,
        approval_reason=None,
        decision_reason="pending approval",
        decided_at=None,
    )

    try:
        store.save_record(pending)

        legacy = store.get_record("approval_legacy")
        assert legacy.status == OPERATION_APPROVAL_APPROVED
        assert legacy.approved_by == "ops_manager_legacy"
        assert store.get_record("approval_pending") == pending
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
    approved_by: str | None = "ops_manager_001",
    approval_reason: str | None = "Approved retry after reviewing worker failure",
    status: str,
    decision_reason: str = "approved",
    requested_at: datetime | None = None,
    decided_at: datetime | None = None,
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
        requested_at=_now() if requested_at is None else requested_at,
        decided_at=(
            _now()
            if decided_at is None and status != OPERATION_APPROVAL_PENDING
            else decided_at
        ),
    )


def _now() -> datetime:
    return datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _database_path() -> Path:
    return _test_data_directory() / f"operation-approval-{uuid4()}.db"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory


def _remove_database(database_path: Path) -> None:
    if database_path.exists():
        database_path.unlink()


def _create_legacy_terminal_status_record(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path))
    try:
        with connection:
            connection.executescript(
                """
                CREATE TABLE operation_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    request_reason TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approval_reason TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'rejected')),
                    decision_reason TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT INTO operation_approvals (
                    approval_id,
                    operation_type,
                    operation_id,
                    target,
                    requested_by,
                    request_reason,
                    approved_by,
                    approval_reason,
                    status,
                    decision_reason,
                    requested_at,
                    decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "approval_legacy",
                    "retry_platform_async_run",
                    "run_legacy",
                    "fintech_platform_api_async_payment_runs/run_legacy",
                    "ops_user_legacy",
                    "Retry legacy run",
                    "ops_manager_legacy",
                    "Approved legacy retry",
                    OPERATION_APPROVAL_APPROVED,
                    "approved",
                    _now().isoformat(),
                    _now().isoformat(),
                ),
            )
    finally:
        connection.close()
