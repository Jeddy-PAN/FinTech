from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from pathlib import Path

from compliance_retention import AuditRetentionDecision, AuditRetentionReport


@dataclass(frozen=True)
class AuditRetentionExportPaths:
    decisions_csv: Path
    html_report: Path


def export_audit_retention_report(
    output_directory: str | Path,
    *,
    report: AuditRetentionReport,
) -> AuditRetentionExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    decisions_csv = output_path / "audit_retention_decisions.csv"
    html_report = output_path / "audit_retention_report.html"

    _write_decisions_csv(decisions_csv, report.decisions)
    html_report.write_text(
        _render_html_report(report=report),
        encoding="utf-8",
    )

    return AuditRetentionExportPaths(
        decisions_csv=decisions_csv,
        html_report=html_report,
    )


def _write_decisions_csv(
    path: Path,
    decisions: tuple[AuditRetentionDecision, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_decision_headers())
        for decision in decisions:
            writer.writerow(_decision_row(decision))


def _decision_headers() -> list[str]:
    return [
        "event_id",
        "event_type",
        "source_system",
        "aggregate_type",
        "aggregate_id",
        "policy_id",
        "status",
        "age_days",
        "archive_due_at",
        "delete_due_at",
        "reason",
    ]


def _decision_row(decision: AuditRetentionDecision) -> list[str | int]:
    event = decision.event
    return [
        event.event_id,
        event.event_type,
        event.source_system,
        event.aggregate_type,
        event.aggregate_id,
        decision.policy.policy_id,
        decision.status,
        decision.age_days,
        _optional_datetime(decision.archive_due_at),
        decision.delete_due_at.isoformat(),
        decision.reason,
    ]


def _render_html_report(*, report: AuditRetentionReport) -> str:
    summary_section = (
        _summary_to_html(report.status_counts)
        if report.status_counts
        else "<p>No retention decisions were generated.</p>"
    )
    decisions_section = (
        _decisions_to_html(report.decisions)
        if report.decisions
        else "<p>No audit events were included in this retention report.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Audit Retention Report</title>
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
  <h1>Audit Retention Report</h1>
  <div class="meta">Generated at {html.escape(report.generated_at.isoformat())}</div>
  <h2>Status Summary</h2>
  {summary_section}
  <h2>Decisions</h2>
  {decisions_section}
</body>
</html>
"""


def _summary_to_html(status_counts: tuple[tuple[str, int], ...]) -> str:
    return _table(
        ["status", "count"],
        status_counts,
    )


def _decisions_to_html(decisions: tuple[AuditRetentionDecision, ...]) -> str:
    rows = [_decision_row(decision) for decision in decisions]
    return _table(_decision_headers(), rows)


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


def _optional_datetime(value) -> str:
    return value.isoformat() if value is not None else ""
