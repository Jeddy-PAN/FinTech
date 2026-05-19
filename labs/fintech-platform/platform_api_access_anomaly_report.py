from __future__ import annotations

import csv
import html
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


LABS_DIR = Path(__file__).resolve().parents[1]
COMPLIANCE_LAB_DIR = LABS_DIR / "compliance-audit"
if str(COMPLIANCE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(COMPLIANCE_LAB_DIR))

from compliance_access_monitoring import (  # noqa: E402
    AccessAnomalyFinding,
    AccessMonitoringRule,
    detect_access_anomalies,
)
from compliance_audit import AuditAccessEvent  # noqa: E402


PLATFORM_API_ACCESS_TARGET_PREFIX = "fintech_platform_api_"


@dataclass(frozen=True)
class PlatformApiAccessAnomalyExportPaths:
    findings_csv: Path
    html_report: Path


def detect_platform_api_access_anomalies(
    events: tuple[AuditAccessEvent, ...],
    *,
    rules: tuple[AccessMonitoringRule, ...] | None = None,
    manager_actor_prefixes: tuple[str, ...] = ("manager_",),
) -> tuple[AccessAnomalyFinding, ...]:
    api_events = tuple(
        event
        for event in events
        if event.target.startswith(PLATFORM_API_ACCESS_TARGET_PREFIX)
    )
    return detect_access_anomalies(
        api_events,
        rules=rules,
        manager_actor_prefixes=manager_actor_prefixes,
    )


def export_platform_api_access_anomaly_report(
    output_directory: str | Path,
    *,
    findings: tuple[AccessAnomalyFinding, ...],
) -> PlatformApiAccessAnomalyExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    findings_csv = output_path / "platform_api_access_anomaly_findings.csv"
    html_report = output_path / "platform_api_access_anomaly_report.html"

    sorted_findings = tuple(sorted(findings, key=_finding_sort_key))
    _write_findings_csv(findings_csv, sorted_findings)
    html_report.write_text(_render_html_report(sorted_findings), encoding="utf-8")

    return PlatformApiAccessAnomalyExportPaths(
        findings_csv=findings_csv,
        html_report=html_report,
    )


def _write_findings_csv(
    path: Path,
    findings: tuple[AccessAnomalyFinding, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
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
        )
        for finding in findings:
            writer.writerow(
                [
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
            )


def _render_html_report(findings: tuple[AccessAnomalyFinding, ...]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    findings_section = (
        _findings_to_html(findings)
        if findings
        else "<p>No platform API access anomaly findings were detected.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform API Access Anomaly Report</title>
  <style>
    body {{
      color: #1f2937;
      font-family: Arial, sans-serif;
      line-height: 1.5;
      margin: 32px;
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
  <h1>FinTech Platform API Access Anomaly Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>
  <h2>Findings</h2>
  {findings_section}
</body>
</html>
"""


def _findings_to_html(findings: tuple[AccessAnomalyFinding, ...]) -> str:
    headers = [
        "finding_type",
        "actor",
        "severity",
        "event_count",
        "first_occurred_at",
        "last_occurred_at",
        "reason",
        "permissions",
        "targets",
    ]
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
            _join_unique(event.target for event in finding.events),
        )
        for finding in findings
    ]
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
