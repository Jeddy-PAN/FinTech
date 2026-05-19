from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlite_platform_store import PlatformRunSnapshot


@dataclass(frozen=True)
class PlatformHistoryReportExportPaths:
    runs_csv: Path
    audit_events_csv: Path
    html_report: Path


def export_platform_history_report(
    output_directory: str | Path,
    *,
    snapshots: tuple[PlatformRunSnapshot, ...],
) -> PlatformHistoryReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    runs_csv = output_path / "platform_run_history.csv"
    audit_events_csv = output_path / "platform_run_audit_events.csv"
    html_report = output_path / "platform_run_history.html"

    _write_runs_csv(runs_csv, snapshots)
    _write_audit_events_csv(audit_events_csv, snapshots)
    html_report.write_text(_render_html_report(snapshots), encoding="utf-8")

    return PlatformHistoryReportExportPaths(
        runs_csv=runs_csv,
        audit_events_csv=audit_events_csv,
        html_report=html_report,
    )


def _write_runs_csv(path: Path, snapshots: tuple[PlatformRunSnapshot, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_run_headers())
        for snapshot in snapshots:
            writer.writerow(_run_row(snapshot))


def _write_audit_events_csv(
    path: Path,
    snapshots: tuple[PlatformRunSnapshot, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "run_id",
                "sequence",
                "occurred_at",
                "source_system",
                "event_type",
                "aggregate_type",
                "aggregate_id",
                "actor",
                "reason",
                "event_id",
            ]
        )
        for snapshot in snapshots:
            for sequence, event in enumerate(snapshot.audit_events, start=1):
                writer.writerow(
                    [
                        snapshot.record.run_id,
                        sequence,
                        event.occurred_at.isoformat(),
                        event.source_system,
                        event.event_type,
                        event.aggregate_type,
                        event.aggregate_id,
                        event.actor,
                        event.reason or "",
                        event.event_id,
                    ]
                )


def _run_headers() -> list[str]:
    return [
        "run_id",
        "customer_id",
        "status",
        "kyc_status",
        "payment_order_id",
        "payment_order_status",
        "risk_status",
        "risk_review_case_id",
        "ledger_transaction_id",
        "platform_bank_balance",
        "user_wallet_balance",
        "audit_event_count",
        "created_at",
    ]


def _run_row(snapshot: PlatformRunSnapshot) -> list[object]:
    record = snapshot.record
    return [
        record.run_id,
        record.customer_id,
        record.status,
        record.kyc_status,
        record.payment_order_id or "",
        record.payment_order_status or "",
        record.risk_status or "",
        record.risk_review_case_id or "",
        record.ledger_transaction_id or "",
        record.platform_bank_balance,
        record.user_wallet_balance,
        record.audit_event_count,
        record.created_at.isoformat(),
    ]


def _render_html_report(snapshots: tuple[PlatformRunSnapshot, ...]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Run History</title>
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
  <h1>FinTech Platform Run History</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Run Summary</h2>
  {_runs_to_html(snapshots)}

  <h2>Audit Events</h2>
  {_audit_events_to_html(snapshots)}
</body>
</html>
"""


def _runs_to_html(snapshots: tuple[PlatformRunSnapshot, ...]) -> str:
    return _table(_run_headers(), (_run_row(snapshot) for snapshot in snapshots))


def _audit_events_to_html(snapshots: tuple[PlatformRunSnapshot, ...]) -> str:
    rows = []
    for snapshot in snapshots:
        for sequence, event in enumerate(snapshot.audit_events, start=1):
            rows.append(
                (
                    snapshot.record.run_id,
                    sequence,
                    event.occurred_at.isoformat(),
                    event.source_system,
                    event.event_type,
                    f"{event.aggregate_type}:{event.aggregate_id}",
                    event.actor,
                    event.reason or "",
                )
            )
    return _table(
        [
            "run_id",
            "sequence",
            "occurred_at",
            "source_system",
            "event_type",
            "aggregate",
            "actor",
            "reason",
        ],
        rows,
    )


def _table(headers: list[str], rows) -> str:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )
