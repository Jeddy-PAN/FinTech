from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


LABS_DIR = Path(__file__).resolve().parents[1]
COMPLIANCE_LAB_DIR = LABS_DIR / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_investigation_cases import (  # noqa: E402
    INVESTIGATION_INVESTIGATING,
    INVESTIGATION_OPEN,
)
from platform_async_service import SQLitePlatformAsyncRunStore  # noqa: E402
from platform_operation_approval import (  # noqa: E402
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_REJECTED,
    SQLiteOperationApprovalStore,
)
from sqlite_access_audit_store import SQLiteAccessAuditStore  # noqa: E402
from sqlite_investigation_case_store import SQLiteInvestigationCaseStore  # noqa: E402
from sqlite_platform_store import SQLitePlatformStore  # noqa: E402


@dataclass(frozen=True)
class PlatformReadinessCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PlatformReadinessReport:
    status: str
    generated_at: datetime
    checks: tuple[PlatformReadinessCheck, ...]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class PlatformMetric:
    name: str
    value: int
    unit: str
    description: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass(frozen=True)
class PlatformMetricsSnapshot:
    generated_at: datetime
    metrics: tuple[PlatformMetric, ...]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "metrics": [metric.to_dict() for metric in self.metrics],
        }


@dataclass(frozen=True)
class PlatformTestMatrixRow:
    area: str
    command: str
    scope: str
    expected_result: str

    def to_dict(self) -> dict:
        return {
            "area": self.area,
            "command": self.command,
            "scope": self.scope,
            "expected_result": self.expected_result,
        }


def build_platform_readiness_report(
    *,
    database_path: str | Path,
    access_audit_database_path: str | Path,
    async_database_path: str | Path,
    investigation_database_path: str | Path,
    operation_approval_database_path: str | Path,
    generated_at: datetime | None = None,
) -> PlatformReadinessReport:
    checks = (
        _platform_store_check(Path(database_path)),
        _access_audit_store_check(Path(access_audit_database_path)),
        _async_run_store_check(Path(async_database_path)),
        _investigation_store_check(Path(investigation_database_path)),
        _operation_approval_store_check(Path(operation_approval_database_path)),
    )
    status = "ready" if all(check.status == "passed" for check in checks) else "degraded"
    return PlatformReadinessReport(
        status=status,
        generated_at=_timestamp(generated_at),
        checks=checks,
    )


def build_platform_metrics_snapshot(
    *,
    database_path: str | Path,
    access_audit_database_path: str | Path,
    async_database_path: str | Path,
    investigation_database_path: str | Path,
    operation_approval_database_path: str | Path,
    generated_at: datetime | None = None,
) -> PlatformMetricsSnapshot:
    runs = _with_store(Path(database_path), SQLitePlatformStore, lambda store: store.runs)
    async_runs = _with_store(
        Path(async_database_path),
        SQLitePlatformAsyncRunStore,
        lambda store: store.runs,
    )
    access_events = _with_store(
        Path(access_audit_database_path),
        SQLiteAccessAuditStore,
        lambda store: store.access_events,
    )
    investigation_cases = _with_store(
        Path(investigation_database_path),
        SQLiteInvestigationCaseStore,
        lambda store: store.cases,
    )
    approval_records = _with_store(
        Path(operation_approval_database_path),
        SQLiteOperationApprovalStore,
        lambda store: store.records,
    )

    metrics = (
        _metric("platform.payment_runs.total", len(runs), "Persisted platform runs"),
        _metric(
            "platform.payment_runs.completed",
            sum(1 for run in runs if run.status == "completed"),
            "Completed platform runs",
        ),
        _metric(
            "platform.payment_runs.review_required",
            sum(1 for run in runs if run.status == "risk_review_required"),
            "Platform runs waiting for risk review",
        ),
        _metric("platform.async_runs.total", len(async_runs), "Persisted async runs"),
        *_status_metrics("platform.async_runs", (run.status for run in async_runs)),
        _metric(
            "platform.operation_approvals.total",
            len(approval_records),
            "Persisted operation approvals",
        ),
        *_status_metrics(
            "platform.operation_approvals",
            (record.status for record in approval_records),
            statuses=(
                OPERATION_APPROVAL_PENDING,
                OPERATION_APPROVAL_APPROVED,
                OPERATION_APPROVAL_REJECTED,
                OPERATION_APPROVAL_CANCELLED,
                OPERATION_APPROVAL_EXPIRED,
            ),
        ),
        _metric(
            "platform.access_events.total",
            len(access_events),
            "Persisted API and report access events",
        ),
        _metric(
            "platform.access_events.denied",
            sum(1 for event in access_events if event.outcome == "denied"),
            "Denied access events",
        ),
        _metric(
            "platform.investigation_cases.total",
            len(investigation_cases),
            "Persisted investigation cases",
        ),
        _metric(
            "platform.investigation_cases.open",
            sum(
                1
                for investigation_case in investigation_cases
                if investigation_case.status
                in {INVESTIGATION_OPEN, INVESTIGATION_INVESTIGATING}
            ),
            "Open or investigating cases",
        ),
    )
    return PlatformMetricsSnapshot(
        generated_at=_timestamp(generated_at),
        metrics=metrics,
    )


def build_platform_test_matrix() -> tuple[PlatformTestMatrixRow, ...]:
    python = "& 'C:\\App\\Anaconda\\python.exe'"
    return (
        PlatformTestMatrixRow(
            area="syntax",
            command=(
                f"{python} -m py_compile "
                ".\\labs\\fintech-platform\\platform_api_app.py "
                ".\\labs\\fintech-platform\\platform_operability.py "
                ".\\labs\\fintech-platform\\demo.py"
            ),
            scope="FastAPI app, operability helpers, demo entrypoint",
            expected_result="No syntax or import errors",
        ),
        PlatformTestMatrixRow(
            area="platform tests",
            command=f"{python} -m pytest -p no:cacheprovider .\\labs\\fintech-platform -q",
            scope="End-to-end platform modules, API routes, reports and stores",
            expected_result="All fintech-platform tests pass",
        ),
        PlatformTestMatrixRow(
            area="demo",
            command=f"{python} .\\labs\\fintech-platform\\demo.py",
            scope="Local runnable scenario and report generation",
            expected_result="Demo completes and writes reports under labs/fintech-platform/reports",
        ),
        PlatformTestMatrixRow(
            area="full labs",
            command=f"{python} -m pytest -p no:cacheprovider .\\labs -q",
            scope="All learning labs",
            expected_result="All labs tests pass",
        ),
    )


def _platform_store_check(path: Path) -> PlatformReadinessCheck:
    return _store_check("platform_store", path, SQLitePlatformStore, lambda store: len(store.runs))


def _access_audit_store_check(path: Path) -> PlatformReadinessCheck:
    return _store_check(
        "access_audit_store",
        path,
        SQLiteAccessAuditStore,
        lambda store: len(store.access_events),
    )


def _async_run_store_check(path: Path) -> PlatformReadinessCheck:
    return _store_check(
        "async_run_store",
        path,
        SQLitePlatformAsyncRunStore,
        lambda store: len(store.runs),
    )


def _investigation_store_check(path: Path) -> PlatformReadinessCheck:
    return _store_check(
        "investigation_case_store",
        path,
        SQLiteInvestigationCaseStore,
        lambda store: len(store.cases),
    )


def _operation_approval_store_check(path: Path) -> PlatformReadinessCheck:
    return _store_check(
        "operation_approval_store",
        path,
        SQLiteOperationApprovalStore,
        lambda store: len(store.records),
    )


def _store_check(
    name: str,
    path: Path,
    store_type,
    count_records: Callable[[object], int],
) -> PlatformReadinessCheck:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record_count = _with_store(path, store_type, count_records)
    except Exception as error:  # pragma: no cover - defensive readiness detail
        return PlatformReadinessCheck(
            name=name,
            status="failed",
            detail=f"{type(error).__name__}: {error}",
        )
    return PlatformReadinessCheck(
        name=name,
        status="passed",
        detail=f"openable; records={record_count}",
    )


def _with_store(path: Path, store_type, read):
    path.parent.mkdir(parents=True, exist_ok=True)
    store = store_type(path)
    try:
        return read(store)
    finally:
        store.close()


def _metric(name: str, value: int, description: str) -> PlatformMetric:
    return PlatformMetric(
        name=name,
        value=value,
        unit="count",
        description=description,
    )


def _status_metrics(
    prefix: str,
    observed_statuses,
    *,
    statuses: tuple[str, ...] = ("accepted", "processing", "completed", "failed"),
) -> tuple[PlatformMetric, ...]:
    counts = {status: 0 for status in statuses}
    for status in observed_statuses:
        if status in counts:
            counts[status] += 1
    return tuple(
        _metric(f"{prefix}.{status}", count, f"{prefix} with status={status}")
        for status, count in counts.items()
    )


def _timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value
