from __future__ import annotations

import csv
import html
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
COMPLIANCE_LAB_DIR = LAB_DIR.parent / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_audit import AuditAccessEvent  # noqa: E402
from platform_async_service import PlatformAsyncRun  # noqa: E402
from sqlite_platform_store import PlatformRunSnapshot  # noqa: E402


RETRY_PLATFORM_ASYNC_RUN = "retry_platform_async_run"
RETRY_TARGET_PREFIX = "fintech_platform_api_async_payment_runs/"


@dataclass(frozen=True)
class PlatformOperationsSummary:
    async_run_count: int
    platform_run_count: int
    completed_async_run_count: int
    failed_async_run_count: int
    retry_granted_count: int
    retry_denied_count: int
    failed_finding_count: int
    warning_finding_count: int


@dataclass(frozen=True)
class PlatformOperationsRunRow:
    run_id: str
    async_status: str | None
    platform_status: str | None
    payment_order_status: str | None
    ledger_transaction_id: str | None
    attempt_count: int | None
    max_attempts: int | None
    last_error: str | None
    retry_granted_count: int
    retry_denied_count: int
    reconciliation_status: str


@dataclass(frozen=True)
class PlatformOperationsFinding:
    run_id: str
    check_id: str
    status: str
    severity: str
    message: str


@dataclass(frozen=True)
class PlatformOperationsReport:
    summary: PlatformOperationsSummary
    run_rows: tuple[PlatformOperationsRunRow, ...]
    findings: tuple[PlatformOperationsFinding, ...]


@dataclass(frozen=True)
class PlatformOperationsReportExportPaths:
    run_rows_csv: Path
    findings_csv: Path
    html_report: Path


def build_platform_operations_report(
    *,
    async_runs: tuple[PlatformAsyncRun, ...],
    snapshots: tuple[PlatformRunSnapshot, ...],
    access_events: tuple[AuditAccessEvent, ...],
) -> PlatformOperationsReport:
    async_by_run_id = {run.run_id: run for run in async_runs}
    snapshots_by_run_id = {snapshot.record.run_id: snapshot for snapshot in snapshots}
    retry_counts = _retry_counts_by_run_id(access_events)

    findings = _evaluate_reconciliation(
        async_runs=async_runs,
        snapshots=snapshots,
        snapshots_by_run_id=snapshots_by_run_id,
    )
    run_rows = tuple(
        _run_row(
            run_id,
            async_run=async_by_run_id.get(run_id),
            snapshot=snapshots_by_run_id.get(run_id),
            retry_count=retry_counts.get(run_id, _RetryCount()),
            findings=findings,
        )
        for run_id in sorted(set(async_by_run_id) | set(snapshots_by_run_id))
    )

    return PlatformOperationsReport(
        summary=PlatformOperationsSummary(
            async_run_count=len(async_runs),
            platform_run_count=len(snapshots),
            completed_async_run_count=sum(1 for run in async_runs if run.status == "completed"),
            failed_async_run_count=sum(1 for run in async_runs if run.status == "failed"),
            retry_granted_count=sum(
                1
                for event in access_events
                if event.permission == RETRY_PLATFORM_ASYNC_RUN
                and event.outcome == "granted"
            ),
            retry_denied_count=sum(
                1
                for event in access_events
                if event.permission == RETRY_PLATFORM_ASYNC_RUN
                and event.outcome == "denied"
            ),
            failed_finding_count=sum(1 for finding in findings if finding.status == "failed"),
            warning_finding_count=sum(1 for finding in findings if finding.status == "warning"),
        ),
        run_rows=run_rows,
        findings=findings,
    )


def export_platform_operations_report(
    output_directory: str | Path,
    *,
    async_runs: tuple[PlatformAsyncRun, ...],
    snapshots: tuple[PlatformRunSnapshot, ...],
    access_events: tuple[AuditAccessEvent, ...],
) -> PlatformOperationsReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    report = build_platform_operations_report(
        async_runs=async_runs,
        snapshots=snapshots,
        access_events=access_events,
    )
    run_rows_csv = output_path / "platform_operations_run_report.csv"
    findings_csv = output_path / "platform_operations_reconciliation_findings.csv"
    html_report = output_path / "platform_operations_report.html"

    _write_run_rows_csv(run_rows_csv, report.run_rows)
    _write_findings_csv(findings_csv, report.findings)
    html_report.write_text(_render_html_report(report), encoding="utf-8")

    return PlatformOperationsReportExportPaths(
        run_rows_csv=run_rows_csv,
        findings_csv=findings_csv,
        html_report=html_report,
    )


@dataclass(frozen=True)
class _RetryCount:
    granted: int = 0
    denied: int = 0


def _evaluate_reconciliation(
    *,
    async_runs: tuple[PlatformAsyncRun, ...],
    snapshots: tuple[PlatformRunSnapshot, ...],
    snapshots_by_run_id: dict[str, PlatformRunSnapshot],
) -> tuple[PlatformOperationsFinding, ...]:
    findings: list[PlatformOperationsFinding] = []
    for run in async_runs:
        if run.status == "completed" and run.run_id not in snapshots_by_run_id:
            findings.append(
                _fail(
                    run.run_id,
                    "completed_async_has_platform_result",
                    "Completed async run has no matching platform result",
                )
            )
        if run.status == "failed":
            findings.append(
                PlatformOperationsFinding(
                    run_id=run.run_id,
                    check_id="failed_async_run_requires_review",
                    status="warning",
                    severity="warning",
                    message="Failed async run remains for operations review",
                )
            )

    for snapshot in snapshots:
        record = snapshot.record
        if record.status == "completed" and record.ledger_transaction_id is None:
            findings.append(
                _fail(
                    record.run_id,
                    "completed_platform_has_ledger_transaction",
                    "Completed platform run has no ledger transaction id",
                )
            )
        if record.ledger_transaction_id is not None and not _has_matching_ledger_event(snapshot):
            findings.append(
                _fail(
                    record.run_id,
                    "ledger_transaction_has_posted_event",
                    "Platform run has a ledger transaction id but no matching ledger posted event",
                )
            )
    return tuple(findings)


def _run_row(
    run_id: str,
    *,
    async_run: PlatformAsyncRun | None,
    snapshot: PlatformRunSnapshot | None,
    retry_count: _RetryCount,
    findings: tuple[PlatformOperationsFinding, ...],
) -> PlatformOperationsRunRow:
    run_findings = [finding for finding in findings if finding.run_id == run_id]
    if any(finding.severity == "error" for finding in run_findings):
        reconciliation_status = "failed"
    elif any(finding.severity == "warning" for finding in run_findings):
        reconciliation_status = "warning"
    else:
        reconciliation_status = "passed"

    record = snapshot.record if snapshot is not None else None
    return PlatformOperationsRunRow(
        run_id=run_id,
        async_status=async_run.status if async_run is not None else None,
        platform_status=record.status if record is not None else None,
        payment_order_status=record.payment_order_status if record is not None else None,
        ledger_transaction_id=record.ledger_transaction_id if record is not None else None,
        attempt_count=async_run.attempt_count if async_run is not None else None,
        max_attempts=async_run.max_attempts if async_run is not None else None,
        last_error=async_run.last_error if async_run is not None else None,
        retry_granted_count=retry_count.granted,
        retry_denied_count=retry_count.denied,
        reconciliation_status=reconciliation_status,
    )


def _retry_counts_by_run_id(
    access_events: tuple[AuditAccessEvent, ...],
) -> dict[str, _RetryCount]:
    counts: dict[str, _RetryCount] = {}
    for event in access_events:
        if event.permission != RETRY_PLATFORM_ASYNC_RUN:
            continue
        run_id = _retry_target_run_id(event.target)
        if run_id is None:
            continue
        current = counts.get(run_id, _RetryCount())
        if event.outcome == "granted":
            counts[run_id] = _RetryCount(
                granted=current.granted + 1,
                denied=current.denied,
            )
        elif event.outcome == "denied":
            counts[run_id] = _RetryCount(
                granted=current.granted,
                denied=current.denied + 1,
            )
    return counts


def _retry_target_run_id(target: str) -> str | None:
    if not target.startswith(RETRY_TARGET_PREFIX):
        return None
    run_id = target.removeprefix(RETRY_TARGET_PREFIX).strip()
    return run_id or None


def _has_matching_ledger_event(snapshot: PlatformRunSnapshot) -> bool:
    ledger_transaction_id = snapshot.record.ledger_transaction_id
    return any(
        event.event_type == "ledger_transaction.posted"
        and event.aggregate_id == ledger_transaction_id
        for event in snapshot.audit_events
    )


def _fail(
    run_id: str,
    check_id: str,
    message: str,
) -> PlatformOperationsFinding:
    return PlatformOperationsFinding(
        run_id=run_id,
        check_id=check_id,
        status="failed",
        severity="error",
        message=message,
    )


def _write_run_rows_csv(
    path: Path,
    run_rows: tuple[PlatformOperationsRunRow, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_run_row_headers())
        for row in run_rows:
            writer.writerow(_run_row_values(row))


def _write_findings_csv(
    path: Path,
    findings: tuple[PlatformOperationsFinding, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_finding_headers())
        for finding in findings:
            writer.writerow(_finding_values(finding))


def _render_html_report(report: PlatformOperationsReport) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Operations Report</title>
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
  <h1>FinTech Platform Operations Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Summary</h2>
  {_summary_to_html(report.summary)}

  <h2>Run Rows</h2>
  {_table(_run_row_headers(), (_run_row_values(row) for row in report.run_rows))}

  <h2>Reconciliation Findings</h2>
  {_table(_finding_headers(), (_finding_values(finding) for finding in report.findings))}
</body>
</html>
"""


def _summary_to_html(summary: PlatformOperationsSummary) -> str:
    return _table(
        ["metric", "value"],
        (
            ("async_run_count", summary.async_run_count),
            ("platform_run_count", summary.platform_run_count),
            ("completed_async_run_count", summary.completed_async_run_count),
            ("failed_async_run_count", summary.failed_async_run_count),
            ("retry_granted_count", summary.retry_granted_count),
            ("retry_denied_count", summary.retry_denied_count),
            ("failed_finding_count", summary.failed_finding_count),
            ("warning_finding_count", summary.warning_finding_count),
        ),
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


def _run_row_headers() -> list[str]:
    return [
        "run_id",
        "async_status",
        "platform_status",
        "payment_order_status",
        "ledger_transaction_id",
        "attempt_count",
        "max_attempts",
        "last_error",
        "retry_granted_count",
        "retry_denied_count",
        "reconciliation_status",
    ]


def _run_row_values(row: PlatformOperationsRunRow) -> list[object]:
    return [
        row.run_id,
        row.async_status,
        row.platform_status,
        row.payment_order_status,
        row.ledger_transaction_id,
        row.attempt_count,
        row.max_attempts,
        row.last_error,
        row.retry_granted_count,
        row.retry_denied_count,
        row.reconciliation_status,
    ]


def _finding_headers() -> list[str]:
    return ["run_id", "check_id", "status", "severity", "message"]


def _finding_values(finding: PlatformOperationsFinding) -> list[object]:
    return [
        finding.run_id,
        finding.check_id,
        finding.status,
        finding.severity,
        finding.message,
    ]


def _csv_value(value: object) -> object:
    return "" if value is None else value
