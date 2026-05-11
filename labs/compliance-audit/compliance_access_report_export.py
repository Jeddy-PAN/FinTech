from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from compliance_access_monitoring import AccessAnomalyFinding


@dataclass(frozen=True)
class AccessAnomalyExportPaths:
    findings_csv: Path
    html_report: Path


def export_access_anomaly_report(
    output_directory: str | Path,
    *,
    findings: tuple[AccessAnomalyFinding, ...],
) -> AccessAnomalyExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    findings_csv = output_path / "access_anomaly_findings.csv"
    html_report = output_path / "access_anomaly_report.html"

    _write_findings_csv(findings_csv, findings)
    html_report.write_text(
        _render_html_report(findings=tuple(sorted(findings, key=_finding_sort_key))),
        encoding="utf-8",
    )

    return AccessAnomalyExportPaths(
        findings_csv=findings_csv,
        html_report=html_report,
    )


def _write_findings_csv(
    path: Path,
    findings: tuple[AccessAnomalyFinding, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_finding_headers())
        for finding in sorted(findings, key=_finding_sort_key):
            writer.writerow(_finding_row(finding))


def _finding_headers() -> list[str]:
    return [
        "finding_type",
        "actor",
        "severity",
        "event_count",
        "first_occurred_at",
        "last_occurred_at",
        "reason",
        "event_types",
        "permissions",
        "targets",
    ]


def _finding_row(finding: AccessAnomalyFinding) -> list[str | int]:
    return [
        finding.finding_type,
        finding.actor,
        finding.severity,
        finding.event_count,
        finding.first_occurred_at.isoformat(),
        finding.last_occurred_at.isoformat(),
        finding.reason,
        _join_unique(event.event_type for event in finding.events),
        _join_unique(event.permission for event in finding.events),
        _join_unique(event.target for event in finding.events),
    ]


def _render_html_report(*, findings: tuple[AccessAnomalyFinding, ...]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    findings_section = (
        _findings_to_html(findings)
        if findings
        else "<p>No access anomaly findings were detected.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Access Anomaly Report</title>
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
  <h1>Access Anomaly Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>
  <h2>Findings</h2>
  {findings_section}
</body>
</html>
"""


def _findings_to_html(findings: tuple[AccessAnomalyFinding, ...]) -> str:
    rows = [
        (
            finding.finding_type,
            finding.actor,
            finding.severity,
            finding.event_count,
            finding.first_occurred_at.isoformat(),
            finding.last_occurred_at.isoformat(),
            finding.reason,
            _join_unique(event.permission for event in finding.events),
        )
        for finding in findings
    ]
    return _table(
        [
            "finding_type",
            "actor",
            "severity",
            "event_count",
            "first_occurred_at",
            "last_occurred_at",
            "reason",
            "permissions",
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


def _join_unique(values) -> str:
    return "|".join(dict.fromkeys(values))


def _finding_sort_key(finding: AccessAnomalyFinding):
    return (
        finding.first_occurred_at,
        finding.severity,
        finding.actor,
        finding.finding_type,
    )
