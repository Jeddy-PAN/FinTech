from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_REJECTED,
    RETRY_PLATFORM_ASYNC_RUN_OPERATION,
    OperationApprovalRecord,
)
from platform_operation_approval_report import (
    build_operation_approval_report,
    export_operation_approval_report,
)


def test_operation_approval_report_summarizes_approval_records() -> None:
    report = build_operation_approval_report(
        records=(
            _approval_record("approval_approved_001", status=OPERATION_APPROVAL_APPROVED),
            _approval_record("approval_approved_002", status=OPERATION_APPROVAL_APPROVED),
            _approval_record(
                "approval_rejected_001",
                status=OPERATION_APPROVAL_REJECTED,
                requested_by="ops_user_001",
                approved_by="ops_user_001",
            ),
        )
    )

    assert report.summary.total_record_count == 3
    assert report.summary.approved_count == 2
    assert report.summary.rejected_count == 1
    assert report.summary.retry_operation_count == 3
    assert report.summary.self_approval_rejected_count == 1


def test_operation_approval_report_orders_records_by_requested_at_and_id() -> None:
    later = _approval_record(
        "approval_002",
        requested_at=datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc),
    )
    earlier = _approval_record(
        "approval_001",
        requested_at=datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc),
    )

    report = build_operation_approval_report(records=(later, earlier))

    assert [record.approval_id for record in report.records] == [
        "approval_001",
        "approval_002",
    ]


def test_export_operation_approval_report_writes_csv_and_escaped_html() -> None:
    output_directory = _output_directory()
    record = _approval_record(
        "approval_<script>",
        operation_id="run_<script>",
        requested_by="ops_<script>",
        request_reason="Retry <failed> run",
        approved_by="manager_<script>",
        approval_reason="Approved <retry>",
        decision_reason="retry accepted <ok>",
    )

    try:
        paths = export_operation_approval_report(
            output_directory,
            records=(record,),
        )

        assert paths.records_csv.exists()
        assert paths.summary_csv.exists()
        assert paths.html_report.exists()

        records_csv = paths.records_csv.read_text(encoding="utf-8")
        summary_csv = paths.summary_csv.read_text(encoding="utf-8")
        html_report = paths.html_report.read_text(encoding="utf-8")

        assert (
            "approval_id,operation_type,operation_id,target,requested_by,"
            "request_reason,approved_by,approval_reason,status,decision_reason,"
            "requested_at,decided_at"
        ) in records_csv
        assert "approval_<script>,retry_platform_async_run,run_<script>" in records_csv
        assert "metric,value" in summary_csv
        assert "approved_count,1" in summary_csv
        assert "FinTech Platform Operation Approval Report" in html_report
        assert "Approval Records" in html_report
        assert "approval_&lt;script&gt;" in html_report
        assert "run_&lt;script&gt;" in html_report
        assert "approval_<script>" not in html_report
        assert "run_<script>" not in html_report
    finally:
        _remove_directory(output_directory)


def _approval_record(
    approval_id: str,
    *,
    operation_type: str = RETRY_PLATFORM_ASYNC_RUN_OPERATION,
    operation_id: str = "run_retry_001",
    target: str | None = None,
    requested_by: str = "ops_user_001",
    request_reason: str = "Retry after review",
    approved_by: str = "ops_manager_001",
    approval_reason: str = "Approved retry after review",
    status: str = OPERATION_APPROVAL_APPROVED,
    decision_reason: str = "retry accepted",
    requested_at: datetime | None = None,
    decided_at: datetime | None = None,
) -> OperationApprovalRecord:
    requested = requested_at or datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    decided = decided_at or datetime(2026, 6, 8, 9, 5, tzinfo=timezone.utc)
    return OperationApprovalRecord(
        approval_id=approval_id,
        operation_type=operation_type,
        operation_id=operation_id,
        target=target or f"fintech_platform_api_async_payment_runs/{operation_id}",
        requested_by=requested_by,
        request_reason=request_reason,
        approved_by=approved_by,
        approval_reason=approval_reason,
        status=status,
        decision_reason=decision_reason,
        requested_at=requested,
        decided_at=decided,
    )


def _output_directory() -> Path:
    directory = Path(__file__).with_name(".test-data") / f"approval-report-{uuid4()}"
    directory.mkdir(parents=True)
    return directory


def _remove_directory(directory: Path) -> None:
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
