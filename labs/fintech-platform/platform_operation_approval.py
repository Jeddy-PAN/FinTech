from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


OPERATION_APPROVAL_APPROVED = "approved"
OPERATION_APPROVAL_REJECTED = "rejected"
OPERATION_APPROVAL_STATUSES = {
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_REJECTED,
}
RETRY_PLATFORM_ASYNC_RUN_OPERATION = "retry_platform_async_run"


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
    approved_by: str
    approval_reason: str
    status: str
    decision_reason: str
    requested_at: datetime
    decided_at: datetime


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
    ) -> tuple[OperationApprovalRecord, ...]:
        conditions: list[str] = []
        parameters: list[str] = []
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
        rows = self._connection.execute(
            f"""
            SELECT *
            FROM operation_approvals
            {where_sql}
            ORDER BY requested_at, approval_id
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def _create_schema(self) -> None:
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
                    approved_by TEXT NOT NULL,
                    approval_reason TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('approved', 'rejected')),
                    decision_reason TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_operation_approvals_operation
                ON operation_approvals (operation_type, operation_id, requested_at);

                CREATE INDEX IF NOT EXISTS idx_operation_approvals_status
                ON operation_approvals (status, requested_at);
                """
            )


def _validate_record(record: OperationApprovalRecord) -> None:
    _require_text(record.approval_id, "approval_id")
    _require_text(record.operation_type, "operation_type")
    _require_text(record.operation_id, "operation_id")
    _require_text(record.target, "target")
    requested_by = _require_text(record.requested_by, "requested_by")
    approved_by = _require_text(record.approved_by, "approved_by")
    _require_text(record.request_reason, "request_reason")
    _require_text(record.approval_reason, "approval_reason")
    _validate_status(record.status)
    _require_text(record.decision_reason, "decision_reason")
    _timestamp_to_storage(record.requested_at, "requested_at")
    _timestamp_to_storage(record.decided_at, "decided_at")
    if record.status == OPERATION_APPROVAL_APPROVED and requested_by == approved_by:
        raise OperationApprovalError("approved_by must differ from requested_by")


def _validate_status(status: str) -> None:
    if status not in OPERATION_APPROVAL_STATUSES:
        raise OperationApprovalError(f"Unknown approval status: {status}")


def _record_to_row(record: OperationApprovalRecord) -> tuple:
    return (
        _require_text(record.approval_id, "approval_id"),
        _require_text(record.operation_type, "operation_type"),
        _require_text(record.operation_id, "operation_id"),
        _require_text(record.target, "target"),
        _require_text(record.requested_by, "requested_by"),
        _require_text(record.request_reason, "request_reason"),
        _require_text(record.approved_by, "approved_by"),
        _require_text(record.approval_reason, "approval_reason"),
        record.status,
        _require_text(record.decision_reason, "decision_reason"),
        _timestamp_to_storage(record.requested_at, "requested_at"),
        _timestamp_to_storage(record.decided_at, "decided_at"),
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
        decided_at=datetime.fromisoformat(row["decided_at"]),
    )


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise OperationApprovalError(f"{field_name} is required")
    return normalized


def _timestamp_to_storage(value: datetime, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OperationApprovalError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()
