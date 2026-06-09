from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from platform_operation_approval import (
    OPERATION_APPROVAL_APPROVED,
    OPERATION_APPROVAL_CANCELLED,
    OPERATION_APPROVAL_EXPIRED,
    OPERATION_APPROVAL_PENDING,
    OPERATION_APPROVAL_REJECTED,
    RETRY_PLATFORM_ASYNC_RUN_OPERATION,
    OperationApprovalRecord,
)


@dataclass(frozen=True)
class OperationApprovalReportSummary:
    total_record_count: int
    pending_count: int
    approved_count: int
    rejected_count: int
    cancelled_count: int
    expired_count: int
    retry_operation_count: int
    self_approval_rejected_count: int


@dataclass(frozen=True)
class OperationApprovalReport:
    summary: OperationApprovalReportSummary
    records: tuple[OperationApprovalRecord, ...]


@dataclass(frozen=True)
class OperationApprovalReportExportPaths:
    records_csv: Path
    summary_csv: Path
    html_report: Path


def build_operation_approval_report(
    *,
    records: tuple[OperationApprovalRecord, ...],
) -> OperationApprovalReport:
    ordered_records = tuple(
        sorted(records, key=lambda record: (record.requested_at, record.approval_id))
    )
    return OperationApprovalReport(
        summary=OperationApprovalReportSummary(
            total_record_count=len(ordered_records),
            pending_count=sum(
                1 for record in ordered_records if record.status == OPERATION_APPROVAL_PENDING
            ),
            approved_count=sum(
                1 for record in ordered_records if record.status == OPERATION_APPROVAL_APPROVED
            ),
            rejected_count=sum(
                1 for record in ordered_records if record.status == OPERATION_APPROVAL_REJECTED
            ),
            cancelled_count=sum(
                1
                for record in ordered_records
                if record.status == OPERATION_APPROVAL_CANCELLED
            ),
            expired_count=sum(
                1 for record in ordered_records if record.status == OPERATION_APPROVAL_EXPIRED
            ),
            retry_operation_count=sum(
                1
                for record in ordered_records
                if record.operation_type == RETRY_PLATFORM_ASYNC_RUN_OPERATION
            ),
            self_approval_rejected_count=sum(
                1
                for record in ordered_records
                if record.status == OPERATION_APPROVAL_REJECTED
                and record.requested_by == record.approved_by
            ),
        ),
        records=ordered_records,
    )


def export_operation_approval_report(
    output_directory: str | Path,
    *,
    records: tuple[OperationApprovalRecord, ...],
) -> OperationApprovalReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    report = build_operation_approval_report(records=records)
    records_csv = output_path / "platform_operation_approval_records.csv"
    summary_csv = output_path / "platform_operation_approval_summary.csv"
    html_report = output_path / "platform_operation_approval_report.html"

    _write_records_csv(records_csv, report.records)
    _write_summary_csv(summary_csv, report.summary)
    html_report.write_text(_render_html_report(report), encoding="utf-8")

    return OperationApprovalReportExportPaths(
        records_csv=records_csv,
        summary_csv=summary_csv,
        html_report=html_report,
    )


def _write_records_csv(
    path: Path,
    records: tuple[OperationApprovalRecord, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_record_headers())
        for record in records:
            writer.writerow(_record_values(record))


def _write_summary_csv(path: Path, summary: OperationApprovalReportSummary) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        for row in _summary_values(summary):
            writer.writerow(row)


def _render_html_report(report: OperationApprovalReport) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Operation Approval Report</title>
  <style>
    body {{
      color: #1f2937;
      font-family: Arial, sans-serif;
      line-height: 1.5;
      margin: 32px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    h2 {{
      margin-top: 28px;
    }}
    table {{
      border-collapse: collapse;
      margin-top: 8px;
      width: 100%;
    }}
    th, td {{
      border: 1px solid #d1d5db;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f3f4f6;
    }}
    .meta {{
      color: #6b7280;
      font-size: 14px;
      margin-bottom: 24px;
    }}
  </style>
</head>
<body>
  <h1>FinTech Platform Operation Approval Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Summary</h2>
  {_summary_to_html(report.summary)}

  <h2>Approval Records</h2>
  {_table(_record_headers(), (_record_values(record) for record in report.records))}
</body>
</html>
"""


def _summary_to_html(summary: OperationApprovalReportSummary) -> str:
    return _table(["metric", "value"], _summary_values(summary))


def _summary_values(summary: OperationApprovalReportSummary) -> tuple[tuple[str, int], ...]:
    return (
        ("total_record_count", summary.total_record_count),
        ("pending_count", summary.pending_count),
        ("approved_count", summary.approved_count),
        ("rejected_count", summary.rejected_count),
        ("cancelled_count", summary.cancelled_count),
        ("expired_count", summary.expired_count),
        ("retry_operation_count", summary.retry_operation_count),
        ("self_approval_rejected_count", summary.self_approval_rejected_count),
    )


def _table(headers: list[str], rows) -> str:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(_csv_value(value)))}</td>" for value in row)
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _record_headers() -> list[str]:
    return [
        "approval_id",
        "operation_type",
        "operation_id",
        "target",
        "requested_by",
        "request_reason",
        "approved_by",
        "approval_reason",
        "status",
        "decision_reason",
        "requested_at",
        "decided_at",
    ]


def _record_values(record: OperationApprovalRecord) -> list[object]:
    return [
        record.approval_id,
        record.operation_type,
        record.operation_id,
        record.target,
        record.requested_by,
        record.request_reason,
        record.approved_by,
        record.approval_reason,
        record.status,
        record.decision_reason,
        record.requested_at.isoformat(),
        None if record.decided_at is None else record.decided_at.isoformat(),
    ]


def _csv_value(value: object) -> object:
    return "" if value is None else value
