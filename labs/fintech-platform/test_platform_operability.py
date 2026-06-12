from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from platform_operability import (
    build_platform_metrics_snapshot,
    build_platform_readiness_report,
    build_platform_test_matrix,
)


def test_build_platform_readiness_report_checks_all_local_stores() -> None:
    with TemporaryDirectory() as temp_dir:
        paths = _paths(Path(temp_dir))
        report = build_platform_readiness_report(
            **paths,
            generated_at=datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc),
        )

        assert report.status == "ready"
        assert report.generated_at.isoformat() == "2026-06-12T12:00:00+00:00"
        assert {check.name for check in report.checks} == {
            "platform_store",
            "access_audit_store",
            "async_run_store",
            "investigation_case_store",
            "operation_approval_store",
        }
        assert {check.status for check in report.checks} == {"passed"}
        assert all("openable; records=0" == check.detail for check in report.checks)


def test_build_platform_metrics_snapshot_and_test_matrix_are_stable() -> None:
    with TemporaryDirectory() as temp_dir:
        snapshot = build_platform_metrics_snapshot(**_paths(Path(temp_dir)))
        metric_values = {
            metric.name: metric.value
            for metric in snapshot.metrics
        }
        matrix = build_platform_test_matrix()

        assert metric_values["platform.payment_runs.total"] == 0
        assert metric_values["platform.async_runs.failed"] == 0
        assert metric_values["platform.operation_approvals.pending"] == 0
        assert metric_values["platform.access_events.denied"] == 0
        assert [row.area for row in matrix] == [
            "syntax",
            "platform tests",
            "demo",
            "full labs",
        ]
        assert "demo.py" in matrix[2].command


def _paths(directory: Path) -> dict:
    return {
        "database_path": directory / "platform.db",
        "access_audit_database_path": directory / "access.db",
        "async_database_path": directory / "async.db",
        "investigation_database_path": directory / "investigation.db",
        "operation_approval_database_path": directory / "approval.db",
    }
