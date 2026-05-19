from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from compliance_audit import ComplianceAuditEvent
from fintech_platform import PlatformPaymentResult, PlatformPaymentStatus


class SQLitePlatformStoreError(ValueError):
    """Base error for invalid platform persistence operations."""


@dataclass(frozen=True)
class PlatformRunRecord:
    run_id: str
    customer_id: str
    status: str
    kyc_status: str
    payment_order_id: str | None
    payment_order_status: str | None
    risk_status: str | None
    risk_review_case_id: str | None
    ledger_transaction_id: str | None
    platform_bank_balance: Decimal
    user_wallet_balance: Decimal
    audit_event_count: int
    created_at: datetime


@dataclass(frozen=True)
class PlatformRunSnapshot:
    record: PlatformRunRecord
    audit_events: tuple[ComplianceAuditEvent, ...]


class SQLitePlatformStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._connection = sqlite3.connect(str(database_path))
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def runs(self) -> tuple[PlatformRunRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM platform_runs
            ORDER BY created_at, run_id
            """
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def save_result(
        self,
        result: PlatformPaymentResult,
        *,
        run_id: str,
        created_at: datetime,
    ) -> PlatformRunRecord:
        normalized_run_id = _require_text(run_id, "run_id")
        created_at_text = _timestamp_to_storage(created_at, "created_at")
        record = _record_from_result(
            result,
            run_id=normalized_run_id,
            created_at=datetime.fromisoformat(created_at_text),
        )
        event_rows = [
            _event_to_row(normalized_run_id, sequence, event)
            for sequence, event in enumerate(result.customer_timeline.events, start=1)
        ]

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO platform_runs (
                    run_id,
                    customer_id,
                    status,
                    kyc_status,
                    payment_order_id,
                    payment_order_status,
                    risk_status,
                    risk_review_case_id,
                    ledger_transaction_id,
                    platform_bank_balance,
                    user_wallet_balance,
                    audit_event_count,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    customer_id = excluded.customer_id,
                    status = excluded.status,
                    kyc_status = excluded.kyc_status,
                    payment_order_id = excluded.payment_order_id,
                    payment_order_status = excluded.payment_order_status,
                    risk_status = excluded.risk_status,
                    risk_review_case_id = excluded.risk_review_case_id,
                    ledger_transaction_id = excluded.ledger_transaction_id,
                    platform_bank_balance = excluded.platform_bank_balance,
                    user_wallet_balance = excluded.user_wallet_balance,
                    audit_event_count = excluded.audit_event_count,
                    created_at = excluded.created_at
                """,
                _record_to_row(record),
            )
            self._connection.execute(
                "DELETE FROM platform_run_audit_events WHERE run_id = ?",
                (normalized_run_id,),
            )
            self._connection.executemany(
                """
                INSERT INTO platform_run_audit_events (
                    run_id,
                    sequence,
                    source_system,
                    event_id,
                    event_type,
                    aggregate_type,
                    aggregate_id,
                    actor,
                    reason,
                    payload,
                    occurred_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                event_rows,
            )
        return record

    def get_run(self, run_id: str) -> PlatformRunSnapshot:
        normalized_run_id = _require_text(run_id, "run_id")
        row = self._connection.execute(
            """
            SELECT *
            FROM platform_runs
            WHERE run_id = ?
            """,
            (normalized_run_id,),
        ).fetchone()
        if row is None:
            raise SQLitePlatformStoreError(f"Unknown platform run: {normalized_run_id}")
        return PlatformRunSnapshot(
            record=_record_from_row(row),
            audit_events=self._events_for_run(normalized_run_id),
        )

    def query_runs(
        self,
        *,
        status: PlatformPaymentStatus | str | None = None,
        customer_id: str | None = None,
    ) -> tuple[PlatformRunRecord, ...]:
        conditions: list[str] = []
        parameters: list[str] = []
        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value if isinstance(status, PlatformPaymentStatus) else status)
        if customer_id is not None:
            conditions.append("customer_id = ?")
            parameters.append(_require_text(customer_id, "customer_id"))

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._connection.execute(
            f"""
            SELECT *
            FROM platform_runs
            {where_sql}
            ORDER BY created_at, run_id
            """,
            tuple(parameters),
        ).fetchall()
        return tuple(_record_from_row(row) for row in rows)

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_runs (
                    run_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    kyc_status TEXT NOT NULL,
                    payment_order_id TEXT,
                    payment_order_status TEXT,
                    risk_status TEXT,
                    risk_review_case_id TEXT,
                    ledger_transaction_id TEXT,
                    platform_bank_balance TEXT NOT NULL,
                    user_wallet_balance TEXT NOT NULL,
                    audit_event_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS platform_run_audit_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    source_system TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT,
                    payload TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES platform_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_platform_runs_status
                ON platform_runs (status, created_at);

                CREATE INDEX IF NOT EXISTS idx_platform_runs_customer
                ON platform_runs (customer_id, created_at);
                """
            )

    def _events_for_run(self, run_id: str) -> tuple[ComplianceAuditEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                source_system,
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                actor,
                reason,
                payload,
                occurred_at
            FROM platform_run_audit_events
            WHERE run_id = ?
            ORDER BY sequence
            """,
            (run_id,),
        ).fetchall()
        return tuple(
            ComplianceAuditEvent(
                source_system=row["source_system"],
                event_id=row["event_id"],
                event_type=row["event_type"],
                aggregate_type=row["aggregate_type"],
                aggregate_id=row["aggregate_id"],
                actor=row["actor"],
                reason=row["reason"],
                payload=row["payload"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
            )
            for row in rows
        )


def _record_from_result(
    result: PlatformPaymentResult,
    *,
    run_id: str,
    created_at: datetime,
) -> PlatformRunRecord:
    payment_order = result.payment_order
    risk_decision = result.risk_decision
    risk_review_case = result.risk_review_case
    return PlatformRunRecord(
        run_id=run_id,
        customer_id=result.kyc_decision.customer_id,
        status=result.status.value,
        kyc_status=result.kyc_decision.status.value,
        payment_order_id=payment_order.id if payment_order is not None else None,
        payment_order_status=(
            payment_order.status.value if payment_order is not None else None
        ),
        risk_status=risk_decision.status.value if risk_decision is not None else None,
        risk_review_case_id=(
            risk_review_case.case_id if risk_review_case is not None else None
        ),
        ledger_transaction_id=result.ledger_transaction_id,
        platform_bank_balance=result.platform_bank_balance,
        user_wallet_balance=result.user_wallet_balance,
        audit_event_count=result.audit_summary.total_events,
        created_at=created_at,
    )


def _record_to_row(record: PlatformRunRecord) -> tuple:
    return (
        record.run_id,
        record.customer_id,
        record.status,
        record.kyc_status,
        record.payment_order_id,
        record.payment_order_status,
        record.risk_status,
        record.risk_review_case_id,
        record.ledger_transaction_id,
        str(record.platform_bank_balance),
        str(record.user_wallet_balance),
        record.audit_event_count,
        _timestamp_to_storage(record.created_at, "created_at"),
    )


def _record_from_row(row: sqlite3.Row) -> PlatformRunRecord:
    return PlatformRunRecord(
        run_id=row["run_id"],
        customer_id=row["customer_id"],
        status=row["status"],
        kyc_status=row["kyc_status"],
        payment_order_id=row["payment_order_id"],
        payment_order_status=row["payment_order_status"],
        risk_status=row["risk_status"],
        risk_review_case_id=row["risk_review_case_id"],
        ledger_transaction_id=row["ledger_transaction_id"],
        platform_bank_balance=Decimal(row["platform_bank_balance"]),
        user_wallet_balance=Decimal(row["user_wallet_balance"]),
        audit_event_count=row["audit_event_count"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _event_to_row(
    run_id: str,
    sequence: int,
    event: ComplianceAuditEvent,
) -> tuple:
    return (
        run_id,
        sequence,
        _require_text(event.source_system, "source_system"),
        _require_text(event.event_id, "event_id"),
        _require_text(event.event_type, "event_type"),
        _require_text(event.aggregate_type, "aggregate_type"),
        _require_text(event.aggregate_id, "aggregate_id"),
        _require_text(event.actor, "actor"),
        event.reason,
        event.payload,
        _timestamp_to_storage(event.occurred_at, "occurred_at"),
    )


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise SQLitePlatformStoreError(f"{field_name} is required")
    return normalized


def _timestamp_to_storage(value: datetime, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SQLitePlatformStoreError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()
