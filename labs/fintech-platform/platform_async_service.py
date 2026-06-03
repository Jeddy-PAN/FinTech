from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from platform_api_service import (
    PlatformApiPaymentRequest,
    PlatformApiService,
    PlatformApiServiceError,
    _request_fingerprint,
)
from sqlite_platform_store import SQLitePlatformStore


ASYNC_RUN_ACCEPTED = "accepted"
ASYNC_RUN_PROCESSING = "processing"
ASYNC_RUN_COMPLETED = "completed"
ASYNC_RUN_FAILED = "failed"
ASYNC_RUN_STATUSES = {
    ASYNC_RUN_ACCEPTED,
    ASYNC_RUN_PROCESSING,
    ASYNC_RUN_COMPLETED,
    ASYNC_RUN_FAILED,
}


class PlatformAsyncRunStoreError(ValueError):
    """Base error for invalid async run persistence operations."""


@dataclass(frozen=True)
class PlatformAsyncRun:
    run_id: str
    status: str
    request_payload: dict[str, Any]
    request_fingerprint: str
    attempt_count: int
    max_attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class PlatformAsyncRunCreateResult:
    run: PlatformAsyncRun
    idempotent_replay: bool


@dataclass(frozen=True)
class PlatformAsyncWorkerResult:
    processed: bool
    run_id: str | None
    async_status: str | None
    platform_status: str | None = None
    error: str | None = None


class SQLitePlatformAsyncRunStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.database_path))
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    @property
    def runs(self) -> tuple[PlatformAsyncRun, ...]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM platform_async_runs
            ORDER BY created_at, run_id
            """
        ).fetchall()
        return tuple(_run_from_row(row) for row in rows)

    def create_run(
        self,
        request: PlatformApiPaymentRequest,
        *,
        created_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> PlatformAsyncRunCreateResult:
        normalized_run_id = _require_text(request.run_id, "run_id")
        _validate_timestamp(request.requested_at, "requested_at")
        if max_attempts <= 0:
            raise PlatformAsyncRunStoreError("max_attempts must be positive")
        created_at_value = created_at or datetime.now(timezone.utc)
        created_at_text = _timestamp_to_storage(created_at_value, "created_at")
        try:
            request_fingerprint = _request_fingerprint(request)
        except PlatformApiServiceError as exc:
            raise PlatformAsyncRunStoreError(str(exc)) from exc

        existing = self._get_run_or_none(normalized_run_id)
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise PlatformAsyncRunStoreError(
                    "run_id was already used with a different request fingerprint"
                )
            return PlatformAsyncRunCreateResult(
                run=existing,
                idempotent_replay=True,
            )

        run = PlatformAsyncRun(
            run_id=normalized_run_id,
            status=ASYNC_RUN_ACCEPTED,
            request_payload=_request_payload(request),
            request_fingerprint=request_fingerprint,
            attempt_count=0,
            max_attempts=max_attempts,
            last_error=None,
            created_at=datetime.fromisoformat(created_at_text),
            updated_at=datetime.fromisoformat(created_at_text),
            started_at=None,
            completed_at=None,
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO platform_async_runs (
                    run_id,
                    status,
                    request_payload,
                    request_fingerprint,
                    attempt_count,
                    max_attempts,
                    last_error,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _run_to_row(run),
            )
        return PlatformAsyncRunCreateResult(run=run, idempotent_replay=False)

    def get_run(self, run_id: str) -> PlatformAsyncRun:
        normalized_run_id = _require_text(run_id, "run_id")
        run = self._get_run_or_none(normalized_run_id)
        if run is None:
            raise PlatformAsyncRunStoreError(
                f"Unknown platform async run: {normalized_run_id}"
            )
        return run

    def query_runs(
        self,
        *,
        status: str | None = None,
    ) -> tuple[PlatformAsyncRun, ...]:
        if status is None:
            return self.runs
        normalized_status = _normalize_status(status)
        rows = self._connection.execute(
            """
            SELECT *
            FROM platform_async_runs
            WHERE status = ?
            ORDER BY created_at, run_id
            """,
            (normalized_status,),
        ).fetchall()
        return tuple(_run_from_row(row) for row in rows)

    def next_accepted_run(self) -> PlatformAsyncRun | None:
        row = self._connection.execute(
            """
            SELECT *
            FROM platform_async_runs
            WHERE status = ?
            ORDER BY created_at, run_id
            LIMIT 1
            """,
            (ASYNC_RUN_ACCEPTED,),
        ).fetchone()
        return _run_from_row(row) if row is not None else None

    def mark_processing(
        self,
        run_id: str,
        *,
        started_at: datetime,
    ) -> PlatformAsyncRun:
        run = self.get_run(run_id)
        if run.status != ASYNC_RUN_ACCEPTED:
            raise PlatformAsyncRunStoreError(
                f"Cannot process {run.status} async run: {run.run_id}"
            )
        started_at_text = _timestamp_to_storage(started_at, "started_at")
        with self._connection:
            self._connection.execute(
                """
                UPDATE platform_async_runs
                SET
                    status = ?,
                    attempt_count = attempt_count + 1,
                    updated_at = ?,
                    started_at = ?,
                    last_error = NULL
                WHERE run_id = ?
                """,
                (
                    ASYNC_RUN_PROCESSING,
                    started_at_text,
                    started_at_text,
                    run.run_id,
                ),
            )
        return self.get_run(run.run_id)

    def mark_completed(
        self,
        run_id: str,
        *,
        completed_at: datetime,
    ) -> PlatformAsyncRun:
        run = self.get_run(run_id)
        if run.status != ASYNC_RUN_PROCESSING:
            raise PlatformAsyncRunStoreError(
                f"Cannot complete {run.status} async run: {run.run_id}"
            )
        completed_at_text = _timestamp_to_storage(completed_at, "completed_at")
        with self._connection:
            self._connection.execute(
                """
                UPDATE platform_async_runs
                SET
                    status = ?,
                    updated_at = ?,
                    completed_at = ?,
                    last_error = NULL
                WHERE run_id = ?
                """,
                (
                    ASYNC_RUN_COMPLETED,
                    completed_at_text,
                    completed_at_text,
                    run.run_id,
                ),
            )
        return self.get_run(run.run_id)

    def mark_failed(
        self,
        run_id: str,
        *,
        error_message: str,
        failed_at: datetime,
    ) -> PlatformAsyncRun:
        run = self.get_run(run_id)
        if run.status != ASYNC_RUN_PROCESSING:
            raise PlatformAsyncRunStoreError(
                f"Cannot fail {run.status} async run: {run.run_id}"
            )
        failed_at_text = _timestamp_to_storage(failed_at, "failed_at")
        normalized_error = _require_text(error_message, "error_message")
        if run.attempt_count < run.max_attempts:
            next_status = ASYNC_RUN_ACCEPTED
            completed_at = None
        else:
            next_status = ASYNC_RUN_FAILED
            completed_at = failed_at_text
        with self._connection:
            self._connection.execute(
                """
                UPDATE platform_async_runs
                SET
                    status = ?,
                    updated_at = ?,
                    completed_at = ?,
                    last_error = ?
                WHERE run_id = ?
                """,
                (
                    next_status,
                    failed_at_text,
                    completed_at,
                    normalized_error,
                    run.run_id,
                ),
            )
        return self.get_run(run.run_id)

    def _get_run_or_none(self, run_id: str) -> PlatformAsyncRun | None:
        row = self._connection.execute(
            """
            SELECT *
            FROM platform_async_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return _run_from_row(row) if row is not None else None

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_async_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (
                        status IN ('accepted', 'processing', 'completed', 'failed')
                    ),
                    request_payload TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_platform_async_runs_status
                ON platform_async_runs (status, created_at);
                """
            )


class PlatformAsyncWorker:
    def __init__(
        self,
        *,
        async_store: SQLitePlatformAsyncRunStore,
        platform_store: SQLitePlatformStore,
        service_factory=None,
    ) -> None:
        self.async_store = async_store
        self.platform_store = platform_store
        self.service_factory = service_factory

    def process_next(
        self,
        *,
        processed_at: datetime | None = None,
    ) -> PlatformAsyncWorkerResult:
        run = self.async_store.next_accepted_run()
        if run is None:
            return PlatformAsyncWorkerResult(
                processed=False,
                run_id=None,
                async_status=None,
            )
        now = processed_at or datetime.now(timezone.utc)
        processing_run = self.async_store.mark_processing(
            run.run_id,
            started_at=now,
        )
        try:
            service = self._service()
            response = service.create_payment_run(
                rebuild_api_request(processing_run.request_payload)
            )
        except Exception as exc:  # noqa: BLE001 - worker must persist any processing error.
            failed_run = self.async_store.mark_failed(
                processing_run.run_id,
                error_message=str(exc) or type(exc).__name__,
                failed_at=now,
            )
            return PlatformAsyncWorkerResult(
                processed=True,
                run_id=failed_run.run_id,
                async_status=failed_run.status,
                error=failed_run.last_error,
            )

        completed_run = self.async_store.mark_completed(
            processing_run.run_id,
            completed_at=now,
        )
        return PlatformAsyncWorkerResult(
            processed=True,
            run_id=completed_run.run_id,
            async_status=completed_run.status,
            platform_status=response["status"],
        )

    def process_pending(
        self,
        *,
        limit: int = 10,
        processed_at: datetime | None = None,
    ) -> tuple[PlatformAsyncWorkerResult, ...]:
        if limit <= 0:
            raise PlatformAsyncRunStoreError("limit must be positive")
        results: list[PlatformAsyncWorkerResult] = []
        for _ in range(limit):
            result = self.process_next(processed_at=processed_at)
            if not result.processed:
                break
            results.append(result)
        return tuple(results)

    def _service(self):
        if self.service_factory is not None:
            return self.service_factory()
        return PlatformApiService(store=self.platform_store)


def _request_payload(request: PlatformApiPaymentRequest) -> dict[str, Any]:
    return {
        "run_id": request.run_id.strip(),
        "customer_id": request.customer_id.strip(),
        "full_name": request.full_name.strip(),
        "date_of_birth": request.date_of_birth.isoformat(),
        "country": request.country.strip(),
        "address": request.address.strip(),
        "identification_number": request.identification_number.strip(),
        "expected_monthly_volume_cents": request.expected_monthly_volume_cents,
        "amount": request.amount.strip(),
        "currency": request.currency.strip(),
        "order_id": request.order_id.strip(),
        "requested_at": request.requested_at.isoformat(),
        "device_id": request.device_id.strip(),
        "ip_country": request.ip_country.strip(),
        "beneficiary_id": request.beneficiary_id.strip(),
        "actor": request.actor.strip(),
    }


def _run_to_row(run: PlatformAsyncRun) -> tuple:
    return (
        run.run_id,
        _normalize_status(run.status),
        json.dumps(run.request_payload, sort_keys=True, separators=(",", ":")),
        run.request_fingerprint,
        run.attempt_count,
        run.max_attempts,
        run.last_error,
        _timestamp_to_storage(run.created_at, "created_at"),
        _timestamp_to_storage(run.updated_at, "updated_at"),
        _optional_timestamp_to_storage(run.started_at, "started_at"),
        _optional_timestamp_to_storage(run.completed_at, "completed_at"),
    )


def _run_from_row(row: sqlite3.Row) -> PlatformAsyncRun:
    return PlatformAsyncRun(
        run_id=row["run_id"],
        status=row["status"],
        request_payload=json.loads(row["request_payload"]),
        request_fingerprint=row["request_fingerprint"],
        attempt_count=row["attempt_count"],
        max_attempts=row["max_attempts"],
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        started_at=(
            datetime.fromisoformat(row["started_at"])
            if row["started_at"] is not None
            else None
        ),
        completed_at=(
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
    )


def _normalize_status(status: str) -> str:
    normalized = _require_text(status, "status")
    if normalized not in ASYNC_RUN_STATUSES:
        raise PlatformAsyncRunStoreError(f"Unknown platform async run status: {status}")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PlatformAsyncRunStoreError(f"{field_name} is required")
    return normalized


def _timestamp_to_storage(value: datetime, field_name: str) -> str:
    _validate_timestamp(value, field_name)
    return value.astimezone(timezone.utc).isoformat()


def _optional_timestamp_to_storage(value: datetime | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _timestamp_to_storage(value, field_name)


def _validate_timestamp(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PlatformAsyncRunStoreError(f"{field_name} must be timezone-aware")


def rebuild_api_request(payload: dict[str, Any]) -> PlatformApiPaymentRequest:
    return PlatformApiPaymentRequest(
        run_id=str(payload["run_id"]),
        customer_id=str(payload["customer_id"]),
        full_name=str(payload["full_name"]),
        date_of_birth=date.fromisoformat(str(payload["date_of_birth"])),
        country=str(payload["country"]),
        address=str(payload["address"]),
        identification_number=str(payload["identification_number"]),
        expected_monthly_volume_cents=int(payload["expected_monthly_volume_cents"]),
        amount=str(payload["amount"]),
        currency=str(payload["currency"]),
        order_id=str(payload["order_id"]),
        requested_at=datetime.fromisoformat(str(payload["requested_at"])),
        device_id=str(payload["device_id"]),
        ip_country=str(payload["ip_country"]),
        beneficiary_id=str(payload["beneficiary_id"]),
        actor=str(payload["actor"]),
    )
