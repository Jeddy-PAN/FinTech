from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


OPERATION_APPROVAL_APPROVED = "approved"
OPERATION_APPROVAL_CANCELLED = "cancelled"
OPERATION_APPROVAL_EXPIRED = "expired"
OPERATION_APPROVAL_PENDING = "pending"
OPERATION_APPROVAL_REJECTED = "rejected"
OPERATION_APPROVAL_STATUSES = {
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_REJECTED,
}
RETRY_PLATFORM_ASYNC_RUN_OPERATION = "retry_platform_async_run"
OPERATION_APPROVAL_SORT_FIELDS = {
    "approval_id",
    "operation_type",
    "operation_id",
    "requested_by",
    "status",
    "requested_at",
    "decided_at",
}
OPERATION_APPROVAL_SORT_ORDERS = {"asc", "desc"}


class OperationApprovalError(ValueError):
    """Base error for invalid operation approval records."""


@dataclass(frozen=True)
class OperationApprovalRecord:
    approval_id: str
    operation_type: str
    operation_id: str
    target: str
    requested_by: str
    request_reason: str
    approved_by: str | None
    approval_reason: str | None
    status: str
    decision_reason: str
    requested_at: datetime
    decided_at: datetime | None


class SQLiteOperationApprovalStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.database_path))
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def records(self) -> tuple[OperationApprovalRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM operation_approvals
            ORDER BY requested_at, approval_id
            """
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def save_record(self, record: OperationApprovalRecord) -> None:
        _validate_record(record)
        with self._connection:
            self._connection.execute(
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
                ON CONFLICT(approval_id) DO UPDATE SET
                    operation_type = excluded.operation_type,
                    operation_id = excluded.operation_id,
                    target = excluded.target,
                    requested_by = excluded.requested_by,
                    request_reason = excluded.request_reason,
                    approved_by = excluded.approved_by,
                    approval_reason = excluded.approval_reason,
                    status = excluded.status,
                    decision_reason = excluded.decision_reason,
                    requested_at = excluded.requested_at,
                    decided_at = excluded.decided_at
                """,
                _record_to_row(record),
            )

    def approve_pending(
        self,
        approval_id: str,
        *,
        approved_by: str,
        approval_reason: str,
        decided_at: datetime,
    ) -> OperationApprovalRecord:
        existing = self.get_record(approval_id)
        approved = OperationApprovalRecord(
            approval_id=existing.approval_id,
            operation_type=existing.operation_type,
            operation_id=existing.operation_id,
            target=existing.target,
            requested_by=existing.requested_by,
            request_reason=existing.request_reason,
            approved_by=approved_by,
            approval_reason=approval_reason,
            status=OPERATION_APPROVAL_APPROVED,
            decision_reason="approved",
            requested_at=existing.requested_at,
            decided_at=decided_at,
        )
        return self._transition_pending(
            existing,
            approved,
            action_name="approve",
        )

    def reject_pending(
        self,
        approval_id: str,
        *,
        rejected_by: str,
        rejection_reason: str,
        decided_at: datetime,
    ) -> OperationApprovalRecord:
        existing = self.get_record(approval_id)
        rejected = OperationApprovalRecord(
            approval_id=existing.approval_id,
            operation_type=existing.operation_type,
            operation_id=existing.operation_id,
            target=existing.target,
            requested_by=existing.requested_by,
            request_reason=existing.request_reason,
            approved_by=rejected_by,
            approval_reason=rejection_reason,
            status=OPERATION_APPROVAL_REJECTED,
            decision_reason="rejected",
            requested_at=existing.requested_at,
            decided_at=decided_at,
        )
        return self._transition_pending(
            existing,
            rejected,
            action_name="reject",
        )

    def cancel_pending(
        self,
        approval_id: str,
        *,
        cancelled_by: str,
        cancellation_reason: str,
        decided_at: datetime,
    ) -> OperationApprovalRecord:
        existing = self.get_record(approval_id)
        cancelled = OperationApprovalRecord(
            approval_id=existing.approval_id,
            operation_type=existing.operation_type,
            operation_id=existing.operation_id,
            target=existing.target,
            requested_by=existing.requested_by,
            request_reason=existing.request_reason,
            approved_by=cancelled_by,
            approval_reason=cancellation_reason,
            status=OPERATION_APPROVAL_CANCELLED,
            decision_reason="cancelled",
            requested_at=existing.requested_at,
            decided_at=decided_at,
        )
        return self._transition_pending(
            existing,
            cancelled,
            action_name="cancel",
        )

    def expire_pending(
        self,
        approval_id: str,
        *,
        expired_by: str,
        expiration_reason: str,
        decided_at: datetime,
    ) -> OperationApprovalRecord:
        existing = self.get_record(approval_id)
        expired = OperationApprovalRecord(
            approval_id=existing.approval_id,
            operation_type=existing.operation_type,
            operation_id=existing.operation_id,
            target=existing.target,
            requested_by=existing.requested_by,
            request_reason=existing.request_reason,
            approved_by=expired_by,
            approval_reason=expiration_reason,
            status=OPERATION_APPROVAL_EXPIRED,
            decision_reason="expired",
            requested_at=existing.requested_at,
            decided_at=decided_at,
        )
        return self._transition_pending(
            existing,
            expired,
            action_name="expire",
        )

    def get_record(self, approval_id: str) -> OperationApprovalRecord:
        normalized_approval_id = _require_text(approval_id, "approval_id")
        row = self._connection.execute(
            """
            SELECT *
            FROM operation_approvals
            WHERE approval_id = ?
            """,
            (normalized_approval_id,),
        ).fetchone()
        if row is None:
            raise OperationApprovalError(
                f"Unknown operation approval record: {normalized_approval_id}"
            )
        return _record_from_row(row)

    def query_records(
        self,
        *,
        status: str | None = None,
        operation_type: str | None = None,
        operation_id: str | None = None,
        sort_by: str = "requested_at",
        sort_order: str = "asc",
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[OperationApprovalRecord, ...]:
        where_sql, parameters = _query_filter_sql(
            status=status,
            operation_type=operation_type,
            operation_id=operation_id,
        )
        order_by_sql = _order_by_sql(sort_by=sort_by, sort_order=sort_order)
        pagination_sql = _pagination_sql(limit=limit, offset=offset)
        if limit is not None:
            parameters.append(limit)
        if offset:
            parameters.append(offset)
        rows = self._connection.execute(
            f"""
            SELECT *
            FROM operation_approvals
            {where_sql}
            {order_by_sql}
            {pagination_sql}
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def count_records(
        self,
        *,
        status: str | None = None,
        operation_type: str | None = None,
        operation_id: str | None = None,
    ) -> int:
        where_sql, parameters = _query_filter_sql(
            status=status,
            operation_type=operation_type,
            operation_id=operation_id,
        )
        row = self._connection.execute(
            f"""
            SELECT COUNT(*) AS record_count
            FROM operation_approvals
            {where_sql}
            """,
            tuple(parameters),
        ).fetchone()
        return int(row["record_count"])

    def _transition_pending(
        self,
        existing: OperationApprovalRecord,
        next_record: OperationApprovalRecord,
        *,
        action_name: str,
    ) -> OperationApprovalRecord:
        if existing.status != OPERATION_APPROVAL_PENDING:
            raise OperationApprovalError(
                f"Cannot {action_name} {existing.status} operation approval record"
            )
        _validate_record(next_record)
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE operation_approvals
                SET
                    operation_type = ?,
                    operation_id = ?,
                    target = ?,
                    requested_by = ?,
                    request_reason = ?,
                    approved_by = ?,
                    approval_reason = ?,
                    status = ?,
                    decision_reason = ?,
                    requested_at = ?,
                    decided_at = ?
                WHERE approval_id = ? AND status = ?
                """,
                (
                    next_record.operation_type,
                    next_record.operation_id,
                    next_record.target,
                    next_record.requested_by,
                    next_record.request_reason,
                    next_record.approved_by,
                    next_record.approval_reason,
                    next_record.status,
                    next_record.decision_reason,
                    _timestamp_to_storage(next_record.requested_at, "requested_at"),
                    _optional_timestamp_to_storage(next_record.decided_at, "decided_at"),
                    next_record.approval_id,
                    OPERATION_APPROVAL_PENDING,
                ),
            )
            if cursor.rowcount != 1:
                current = self.get_record(next_record.approval_id)
                raise OperationApprovalError(
                    f"Cannot {action_name} {current.status} operation approval record"
                )
        return self.get_record(next_record.approval_id)

    def _create_schema(self) -> None:
        self._migrate_schema_if_needed()
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operation_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    request_reason TEXT NOT NULL,
                    approved_by TEXT,
                    approval_reason TEXT,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired')),
                    decision_reason TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_operation_approvals_operation
                ON operation_approvals (operation_type, operation_id, requested_at);

                CREATE INDEX IF NOT EXISTS idx_operation_approvals_status
                ON operation_approvals (status, requested_at);
                """
            )

    def _migrate_schema_if_needed(self) -> None:
        row = self._connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'operation_approvals'
            """
        ).fetchone()
        if row is None:
            return
        schema_sql = row["sql"] or ""
        if (
            "'pending'" in schema_sql
            and "'cancelled'" in schema_sql
            and "'expired'" in schema_sql
            and "approved_by TEXT NOT NULL" not in schema_sql
            and "approval_reason TEXT NOT NULL" not in schema_sql
            and "decided_at TEXT NOT NULL" not in schema_sql
        ):
            return
        with self._connection:
            self._connection.executescript(
                """
                ALTER TABLE operation_approvals RENAME TO operation_approvals_legacy;

                CREATE TABLE operation_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    request_reason TEXT NOT NULL,
                    approved_by TEXT,
                    approval_reason TEXT,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired')),
                    decision_reason TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT
                );

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
                SELECT
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
                FROM operation_approvals_legacy;

                DROP TABLE operation_approvals_legacy;
                """
            )


def _validate_record(record: OperationApprovalRecord) -> None:
    _require_text(record.approval_id, "approval_id")
    _require_text(record.operation_type, "operation_type")
    _require_text(record.operation_id, "operation_id")
    _require_text(record.target, "target")
    requested_by = _require_text(record.requested_by, "requested_by")
    _require_text(record.request_reason, "request_reason")
    _validate_status(record.status)
    _require_text(record.decision_reason, "decision_reason")
    _timestamp_to_storage(record.requested_at, "requested_at")

    if record.status == OPERATION_APPROVAL_PENDING:
        if record.approved_by is not None:
            _require_text(record.approved_by, "approved_by")
        if record.approval_reason is not None:
            _require_text(record.approval_reason, "approval_reason")
        if record.decided_at is not None:
            raise OperationApprovalError("pending approval must not have decided_at")
        return

    approved_by = _require_optional_text(record.approved_by, "approved_by")
    _require_optional_text(record.approval_reason, "approval_reason")
    _timestamp_to_storage(record.decided_at, "decided_at")
    if record.status == OPERATION_APPROVAL_APPROVED and requested_by == approved_by:
        raise OperationApprovalError("approved_by must differ from requested_by")


def _validate_status(status: str) -> None:
    if status not in OPERATION_APPROVAL_STATUSES:
        raise OperationApprovalError(f"Unknown approval status: {status}")


def _order_by_sql(*, sort_by: str, sort_order: str) -> str:
    normalized_sort_by = _require_text(sort_by, "sort_by")
    normalized_sort_order = _require_text(sort_order, "sort_order").lower()
    if normalized_sort_by not in OPERATION_APPROVAL_SORT_FIELDS:
        raise OperationApprovalError(f"Unknown approval sort field: {sort_by}")
    if normalized_sort_order not in OPERATION_APPROVAL_SORT_ORDERS:
        raise OperationApprovalError(f"Unknown approval sort order: {sort_order}")
    direction = "DESC" if normalized_sort_order == "desc" else "ASC"
    if normalized_sort_by == "approval_id":
        return f"ORDER BY approval_id {direction}"
    return f"ORDER BY {normalized_sort_by} {direction}, approval_id {direction}"


def _query_filter_sql(
    *,
    status: str | None,
    operation_type: str | None,
    operation_id: str | None,
) -> tuple[str, list[object]]:
    conditions: list[str] = []
    parameters: list[object] = []
    if status is not None:
        _validate_status(status)
        conditions.append("status = ?")
        parameters.append(status)
    if operation_type is not None:
        conditions.append("operation_type = ?")
        parameters.append(_require_text(operation_type, "operation_type"))
    if operation_id is not None:
        conditions.append("operation_id = ?")
        parameters.append(_require_text(operation_id, "operation_id"))
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_sql, parameters


def _pagination_sql(*, limit: int | None, offset: int) -> str:
    if offset < 0:
        raise OperationApprovalError("offset must be greater than or equal to 0")
    if limit is None:
        if offset:
            raise OperationApprovalError("limit is required when offset is provided")
        return ""
    if limit <= 0:
        raise OperationApprovalError("limit must be greater than 0")
    if offset:
        return "LIMIT ? OFFSET ?"
    return "LIMIT ?"


def _record_to_row(record: OperationApprovalRecord) -> tuple:
    return (
        _require_text(record.approval_id, "approval_id"),
        _require_text(record.operation_type, "operation_type"),
        _require_text(record.operation_id, "operation_id"),
        _require_text(record.target, "target"),
        _require_text(record.requested_by, "requested_by"),
        _require_text(record.request_reason, "request_reason"),
        _optional_text_to_storage(record.approved_by, "approved_by"),
        _optional_text_to_storage(record.approval_reason, "approval_reason"),
        record.status,
        _require_text(record.decision_reason, "decision_reason"),
        _timestamp_to_storage(record.requested_at, "requested_at"),
        _optional_timestamp_to_storage(record.decided_at, "decided_at"),
    )


def _record_from_row(row: sqlite3.Row) -> OperationApprovalRecord:
    return OperationApprovalRecord(
        approval_id=row["approval_id"],
        operation_type=row["operation_type"],
        operation_id=row["operation_id"],
        target=row["target"],
        requested_by=row["requested_by"],
        request_reason=row["request_reason"],
        approved_by=row["approved_by"],
        approval_reason=row["approval_reason"],
        status=row["status"],
        decision_reason=row["decision_reason"],
        requested_at=datetime.fromisoformat(row["requested_at"]),
        decided_at=(
            None if row["decided_at"] is None else datetime.fromisoformat(row["decided_at"])
        ),
    )


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise OperationApprovalError(f"{field_name} is required")
    return normalized


def _require_optional_text(value: str | None, field_name: str) -> str:
    if value is None:
        raise OperationApprovalError(f"{field_name} is required")
    return _require_text(value, field_name)


def _optional_text_to_storage(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _timestamp_to_storage(value: datetime, field_name: str) -> str:
    if value is None:
        raise OperationApprovalError(f"{field_name} is required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise OperationApprovalError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _optional_timestamp_to_storage(
    value: datetime | None,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _timestamp_to_storage(value, field_name)
