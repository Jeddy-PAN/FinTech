from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from risk_reporting import RiskRuleVersionComparisonReport, RiskSummaryReport


@dataclass(frozen=True)
class RiskReportExportPaths:
    summary_csv: Path
    comparison_csv: Path | None
    html_report: Path


def export_risk_reports(
    output_directory: str | Path,
    *,
    summary_report: RiskSummaryReport,
    comparison_report: RiskRuleVersionComparisonReport | None = None,
) -> RiskReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_csv = output_path / "risk_summary_report.csv"
    comparison_csv = (
        output_path / "rule_version_comparison_report.csv"
        if comparison_report is not None
        else None
    )
    html_report = output_path / "risk_report.html"

    _write_summary_csv(summary_csv, summary_report)
    if comparison_report is not None and comparison_csv is not None:
        _write_comparison_csv(comparison_csv, comparison_report)
    html_report.write_text(
        _render_html_report(
            summary_report=summary_report,
            comparison_report=comparison_report,
        ),
        encoding="utf-8",
    )

    return RiskReportExportPaths(
        summary_csv=summary_csv,
        comparison_csv=comparison_csv,
        html_report=html_report,
    )


def _write_summary_csv(path: Path, report: RiskSummaryReport) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["section", "metric", "value"])
        writer.writerows(_summary_rows(report))


def _write_comparison_csv(
    path: Path,
    report: RiskRuleVersionComparisonReport,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["section", "metric", "baseline_value", "comparison_value", "delta"]
        )
        writer.writerows(_comparison_rows(report))


def _summary_rows(report: RiskSummaryReport) -> list[list[object]]:
    rows: list[list[object]] = [
        ["metadata", "rule_version_id", report.rule_version_id or "all"],
        ["metadata", "decided_from", _datetime_or_all(report.decided_from)],
        ["metadata", "decided_to", _datetime_or_all(report.decided_to)],
        ["summary", "total_decisions", report.total_decisions],
        ["summary", "average_risk_score", f"{report.average_risk_score:.2f}"],
        ["summary", "max_risk_score", report.max_risk_score],
        ["summary", "pending_review_count", report.pending_review_count],
    ]
    rows.extend(
        ["decision_status", item.status, item.count]
        for item in report.decision_status_counts
    )
    rows.extend(["rule_hit", item.rule_id, item.count] for item in report.rule_hit_counts)
    rows.extend(
        ["review_status", item.status, item.count]
        for item in report.review_status_counts
    )
    return rows


def _comparison_rows(report: RiskRuleVersionComparisonReport) -> list[list[object]]:
    rows: list[list[object]] = [
        [
            "metadata",
            "rule_version_id",
            report.baseline_rule_version_id,
            report.comparison_rule_version_id,
            "",
        ],
        [
            "metadata",
            "decided_from",
            _datetime_or_all(report.decided_from),
            _datetime_or_all(report.decided_from),
            "",
        ],
        [
            "metadata",
            "decided_to",
            _datetime_or_all(report.decided_to),
            _datetime_or_all(report.decided_to),
            "",
        ],
        [
            "summary",
            "total_decisions",
            report.baseline_summary.total_decisions,
            report.comparison_summary.total_decisions,
            report.total_decisions_delta,
        ],
        [
            "summary",
            "average_risk_score",
            f"{report.baseline_summary.average_risk_score:.2f}",
            f"{report.comparison_summary.average_risk_score:.2f}",
            f"{report.average_risk_score_delta:.2f}",
        ],
        [
            "summary",
            "max_risk_score",
            report.baseline_summary.max_risk_score,
            report.comparison_summary.max_risk_score,
            report.max_risk_score_delta,
        ],
        [
            "summary",
            "pending_review_count",
            report.baseline_summary.pending_review_count,
            report.comparison_summary.pending_review_count,
            report.pending_review_delta,
        ],
    ]
    rows.extend(
        [
            "decision_status",
            item.status,
            item.baseline_count,
            item.comparison_count,
            item.delta,
        ]
        for item in report.decision_status_comparisons
    )
    rows.extend(
        [
            "rule_hit",
            item.rule_id,
            item.baseline_count,
            item.comparison_count,
            item.delta,
        ]
        for item in report.rule_hit_comparisons
    )
    rows.extend(
        [
            "review_status",
            item.status,
            item.baseline_count,
            item.comparison_count,
            item.delta,
        ]
        for item in report.review_status_comparisons
    )
    return rows


def _render_html_report(
    *,
    summary_report: RiskSummaryReport,
    comparison_report: RiskRuleVersionComparisonReport | None,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    comparison_section = (
        _comparison_report_to_html(comparison_report)
        if comparison_report is not None
        else "<p>No rule version comparison report was provided.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Risk Rule Report</title>
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
      text-align: right;
    }}
    th:first-child, td:first-child {{
      text-align: left;
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
  <h1>Risk Rule Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Risk Summary</h2>
  {_summary_report_to_html(summary_report)}

  <h2>Rule Version Comparison</h2>
  {comparison_section}
</body>
</html>
"""


def _summary_report_to_html(report: RiskSummaryReport) -> str:
    rows = [
        ("rule_version_id", report.rule_version_id or "all"),
        ("decided_from", _datetime_or_all(report.decided_from)),
        ("decided_to", _datetime_or_all(report.decided_to)),
        ("total_decisions", report.total_decisions),
        ("average_risk_score", f"{report.average_risk_score:.2f}"),
        ("max_risk_score", report.max_risk_score),
        ("pending_review_count", report.pending_review_count),
    ]
    return _table(["metric", "value"], rows)


def _comparison_report_to_html(report: RiskRuleVersionComparisonReport) -> str:
    rows = [
        ("baseline_rule_version_id", report.baseline_rule_version_id),
        ("comparison_rule_version_id", report.comparison_rule_version_id),
        ("decided_from", _datetime_or_all(report.decided_from)),
        ("decided_to", _datetime_or_all(report.decided_to)),
        ("total_decisions_delta", report.total_decisions_delta),
        ("average_risk_score_delta", f"{report.average_risk_score_delta:.2f}"),
        ("max_risk_score_delta", report.max_risk_score_delta),
        ("pending_review_delta", report.pending_review_delta),
    ]
    status_rows = [
        (
            item.status,
            item.baseline_count,
            item.comparison_count,
            _signed_int(item.delta),
        )
        for item in report.decision_status_comparisons
    ]
    return (
        _table(["metric", "value"], rows)
        + "<h2>Decision Status Comparison</h2>"
        + _table(["status", "baseline", "comparison", "delta"], status_rows)
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


def _datetime_or_all(value: datetime | None) -> str:
    if value is None:
        return "all"
    return value.isoformat()


def _signed_int(value: int) -> str:
    return f"{value:+d}"
