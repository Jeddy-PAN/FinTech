from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fintech_platform import PlatformPaymentResult


@dataclass(frozen=True)
class PlatformReportExportPaths:
    result_csv: Path
    timeline_csv: Path
    html_report: Path


def export_platform_report(
    output_directory: str | Path,
    *,
    result: PlatformPaymentResult,
) -> PlatformReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    result_csv = output_path / "platform_payment_result.csv"
    timeline_csv = output_path / "platform_audit_timeline.csv"
    html_report = output_path / "platform_report.html"

    _write_result_csv(result_csv, result)
    _write_timeline_csv(timeline_csv, result)
    html_report.write_text(_render_html_report(result), encoding="utf-8")

    return PlatformReportExportPaths(
        result_csv=result_csv,
        timeline_csv=timeline_csv,
        html_report=html_report,
    )


def _write_result_csv(path: Path, result: PlatformPaymentResult) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["section", "metric", "value"])
        writer.writerows(_result_rows(result))


def _write_timeline_csv(path: Path, result: PlatformPaymentResult) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "subject_type",
                "subject_id",
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
        for event in result.customer_timeline.events:
            writer.writerow(
                [
                    result.customer_timeline.subject_type,
                    result.customer_timeline.subject_id,
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


def _result_rows(result: PlatformPaymentResult) -> list[list[object]]:
    payment_order = result.payment_order
    risk_decision = result.risk_decision
    risk_review_case = result.risk_review_case
    rows: list[list[object]] = [
        ["platform", "status", result.status.value],
        ["kyc", "decision_status", result.kyc_decision.status.value],
        ["kyc", "risk_score", result.kyc_decision.risk_score],
        [
            "payment",
            "order_id",
            payment_order.id if payment_order is not None else "",
        ],
        [
            "payment",
            "order_status",
            payment_order.status.value if payment_order is not None else "",
        ],
        [
            "risk",
            "decision_status",
            risk_decision.status.value if risk_decision is not None else "",
        ],
        [
            "risk",
            "risk_score",
            risk_decision.risk_score if risk_decision is not None else "",
        ],
        [
            "risk",
            "review_case_id",
            risk_review_case.case_id if risk_review_case is not None else "",
        ],
        ["ledger", "transaction_id", result.ledger_transaction_id or ""],
        ["ledger", "platform_bank_balance", result.platform_bank_balance],
        ["ledger", "user_wallet_balance", result.user_wallet_balance],
        ["audit", "event_count", result.audit_summary.total_events],
    ]
    rows.extend(
        ["audit_source", source_system, count]
        for source_system, count in result.audit_summary.source_system_counts
    )
    return rows


def _render_html_report(result: PlatformPaymentResult) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Report</title>
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
  <h1>FinTech Platform Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Payment Result</h2>
  {_result_to_html(result)}

  <h2>Customer Audit Timeline</h2>
  {_timeline_to_html(result)}
</body>
</html>
"""


def _result_to_html(result: PlatformPaymentResult) -> str:
    return _table(["section", "metric", "value"], _result_rows(result))


def _timeline_to_html(result: PlatformPaymentResult) -> str:
    rows = [
        (
            event.occurred_at.isoformat(),
            event.source_system,
            event.event_type,
            f"{event.aggregate_type}:{event.aggregate_id}",
            event.actor,
            event.reason or "",
        )
        for event in result.customer_timeline.events
    ]
    return _table(
        [
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
