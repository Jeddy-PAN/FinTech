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

from compliance_access_monitoring import AccessAnomalyFinding  # noqa: E402
from compliance_investigation_cases import (  # noqa: E402
    AccessAnomalyInvestigationCase,
    AccessAnomalyInvestigationService,
)


@dataclass(frozen=True)
class PlatformApiInvestigationCaseExportPaths:
    cases_csv: Path
    html_report: Path


def open_platform_api_access_investigation_cases(
    findings: tuple[AccessAnomalyFinding, ...],
    *,
    opened_by: str,
    created_at: datetime,
    service: AccessAnomalyInvestigationService | None = None,
) -> tuple[AccessAnomalyInvestigationCase, ...]:
    investigation_service = service or AccessAnomalyInvestigationService()
    return tuple(
        investigation_service.create_case(
            finding,
            opened_by=opened_by,
            created_at=created_at,
        )
        for finding in sorted(findings, key=_finding_sort_key)
    )


def export_platform_api_access_investigation_report(
    output_directory: str | Path,
    *,
    cases: tuple[AccessAnomalyInvestigationCase, ...],
) -> PlatformApiInvestigationCaseExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    cases_csv = output_path / "platform_api_access_investigation_cases.csv"
    html_report = output_path / "platform_api_access_investigation_report.html"
    sorted_cases = tuple(sorted(cases, key=_case_sort_key))

    _write_cases_csv(cases_csv, sorted_cases)
    html_report.write_text(
        _render_html_report(cases=sorted_cases),
        encoding="utf-8",
    )

    return PlatformApiInvestigationCaseExportPaths(
        cases_csv=cases_csv,
        html_report=html_report,
    )


def _write_cases_csv(
    path: Path,
    cases: tuple[AccessAnomalyInvestigationCase, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_case_headers())
        for investigation_case in cases:
            writer.writerow(_case_row(investigation_case))


def _case_headers() -> list[str]:
    return [
        "case_id",
        "status",
        "finding_type",
        "actor",
        "severity",
        "event_count",
        "created_at",
        "opened_by",
        "assigned_to",
        "investigation_started_at",
        "closed_by",
        "closed_at",
        "resolution_reason",
        "finding_reason",
        "first_occurred_at",
        "last_occurred_at",
        "permissions",
        "targets",
    ]


def _case_row(investigation_case: AccessAnomalyInvestigationCase) -> list[str | int]:
    finding = investigation_case.finding
    return [
        investigation_case.case_id,
        investigation_case.status,
        finding.finding_type,
        finding.actor,
        finding.severity,
        finding.event_count,
        investigation_case.created_at.isoformat(),
        investigation_case.opened_by,
        investigation_case.assigned_to or "",
        _optional_datetime(investigation_case.investigation_started_at),
        investigation_case.closed_by or "",
        _optional_datetime(investigation_case.closed_at),
        investigation_case.resolution_reason or "",
        finding.reason,
        finding.first_occurred_at.isoformat(),
        finding.last_occurred_at.isoformat(),
        _join_unique(event.permission for event in finding.events),
        _join_unique(event.target for event in finding.events),
    ]


def _render_html_report(*, cases: tuple[AccessAnomalyInvestigationCase, ...]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    summary_section = (
        _summary_to_html(_status_counts(cases))
        if cases
        else "<p>No platform API access investigation cases were included in this report.</p>"
    )
    cases_section = (
        _cases_to_html(cases)
        if cases
        else "<p>No platform API access investigation cases were found.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform API Access Investigation Report</title>
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
  <h1>FinTech Platform API Access Investigation Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>
  <h2>Status Summary</h2>
  {summary_section}
  <h2>Cases</h2>
  {cases_section}
</body>
</html>
"""


def _summary_to_html(status_counts: tuple[tuple[str, int], ...]) -> str:
    return _table(["status", "count"], status_counts)


def _cases_to_html(cases: tuple[AccessAnomalyInvestigationCase, ...]) -> str:
    return _table(
        _case_headers(),
        [_case_row(investigation_case) for investigation_case in cases],
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


def _status_counts(
    cases: tuple[AccessAnomalyInvestigationCase, ...],
) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for investigation_case in cases:
        counts[investigation_case.status] = counts.get(investigation_case.status, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _optional_datetime(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _join_unique(values) -> str:
    return "|".join(dict.fromkeys(values))


def _finding_sort_key(finding: AccessAnomalyFinding):
    return (
        finding.first_occurred_at,
        finding.severity,
        finding.actor,
        finding.finding_type,
    )


def _case_sort_key(investigation_case: AccessAnomalyInvestigationCase):
    return (
        investigation_case.created_at,
        investigation_case.status,
        investigation_case.case_id,
    )
