from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kyc_replay import KycReplayReport
from kyc_reporting import KycSummaryReport, KycVersionComparisonReport


@dataclass(frozen=True)
class KycReportExportPaths:
    summary_csv: Path
    comparison_csv: Path | None
    replay_csv: Path | None
    html_report: Path


def export_kyc_reports(
    output_directory: str | Path,
    *,
    summary_report: KycSummaryReport,
    comparison_report: KycVersionComparisonReport | None = None,
    replay_report: KycReplayReport | None = None,
) -> KycReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_csv = output_path / "kyc_summary_report.csv"
    comparison_csv = (
        output_path / "kyc_version_comparison_report.csv"
        if comparison_report is not None
        else None
    )
    replay_csv = (
        output_path / "kyc_replay_report.csv" if replay_report is not None else None
    )
    html_report = output_path / "kyc_report.html"

    _write_summary_csv(summary_csv, summary_report)
    if comparison_report is not None and comparison_csv is not None:
        _write_comparison_csv(comparison_csv, comparison_report)
    if replay_report is not None and replay_csv is not None:
        _write_replay_csv(replay_csv, replay_report)
    html_report.write_text(
        _render_html_report(
            summary_report=summary_report,
            comparison_report=comparison_report,
            replay_report=replay_report,
        ),
        encoding="utf-8",
    )

    return KycReportExportPaths(
        summary_csv=summary_csv,
        comparison_csv=comparison_csv,
        replay_csv=replay_csv,
        html_report=html_report,
    )


def _write_summary_csv(path: Path, report: KycSummaryReport) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["section", "metric", "value"])
        writer.writerows(_summary_rows(report))


def _write_comparison_csv(
    path: Path,
    report: KycVersionComparisonReport,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["section", "metric", "baseline_value", "comparison_value", "delta"]
        )
        writer.writerows(_comparison_rows(report))


def _write_replay_csv(path: Path, report: KycReplayReport) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["section", "metric", "value"])
        writer.writerows(_replay_rows(report))


def _summary_rows(report: KycSummaryReport) -> list[list[object]]:
    rows: list[list[object]] = [
        ["metadata", "customer_type", report.customer_type or "all"],
        ["metadata", "decision_status", report.decision_status or "all"],
        ["metadata", "watchlist_version_id", report.watchlist_version_id or "all"],
        ["metadata", "policy_version_id", report.policy_version_id or "all"],
        ["metadata", "submitted_from", _datetime_or_all(report.submitted_from)],
        ["metadata", "submitted_to", _datetime_or_all(report.submitted_to)],
        ["metadata", "decided_from", _datetime_or_all(report.decided_from)],
        ["metadata", "decided_to", _datetime_or_all(report.decided_to)],
        ["summary", "total_applications", report.total_applications],
        ["summary", "average_risk_score", f"{report.average_risk_score:.2f}"],
        ["summary", "max_risk_score", report.max_risk_score],
        ["summary", "pending_review_count", report.pending_review_count],
    ]
    rows.extend(
        ["customer_type", item.customer_type, item.count]
        for item in report.customer_type_counts
    )
    rows.extend(
        ["decision_status", item.status, item.count]
        for item in report.decision_status_counts
    )
    rows.extend(["check_hit", item.check_id, item.count] for item in report.check_hit_counts)
    rows.extend(
        ["review_status", item.status, item.count]
        for item in report.review_status_counts
    )
    return rows


def _comparison_rows(report: KycVersionComparisonReport) -> list[list[object]]:
    rows: list[list[object]] = [
        [
            "metadata",
            "version_type",
            report.version_type,
            report.version_type,
            "",
        ],
        [
            "metadata",
            "version_id",
            report.baseline_version_id,
            report.comparison_version_id,
            "",
        ],
        [
            "metadata",
            "submitted_from",
            _datetime_or_all(report.submitted_from),
            _datetime_or_all(report.submitted_from),
            "",
        ],
        [
            "metadata",
            "submitted_to",
            _datetime_or_all(report.submitted_to),
            _datetime_or_all(report.submitted_to),
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
            "total_applications",
            report.baseline_summary.total_applications,
            report.comparison_summary.total_applications,
            report.total_applications_delta,
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
            "customer_type",
            item.customer_type,
            item.baseline_count,
            item.comparison_count,
            item.delta,
        ]
        for item in report.customer_type_comparisons
    )
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
            "check_hit",
            item.check_id,
            item.baseline_count,
            item.comparison_count,
            item.delta,
        ]
        for item in report.check_hit_comparisons
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


def _replay_rows(report: KycReplayReport) -> list[list[object]]:
    rows: list[list[object]] = [
        [
            "metadata",
            "replay_policy_version_id",
            report.replay_policy_version_id or "unversioned",
        ],
        [
            "metadata",
            "replay_watchlist_version_id",
            report.replay_watchlist_version_id or "unversioned",
        ],
        ["summary", "total_applications", report.total_applications],
        ["summary", "status_changed_count", report.status_changed_count],
        ["summary", "increased_risk_count", report.increased_risk_count],
        ["summary", "decreased_risk_count", report.decreased_risk_count],
        ["summary", "unchanged_risk_count", report.unchanged_risk_count],
    ]
    for item in report.items:
        rows.extend(
            [
                ["item", f"{item.customer_id}.original_status", item.original_status],
                ["item", f"{item.customer_id}.replay_status", item.replay_status],
                ["item", f"{item.customer_id}.status_changed", item.status_changed],
                [
                    "item",
                    f"{item.customer_id}.original_risk_score",
                    item.original_risk_score,
                ],
                [
                    "item",
                    f"{item.customer_id}.replay_risk_score",
                    item.replay_risk_score,
                ],
                ["item", f"{item.customer_id}.risk_score_delta", item.risk_score_delta],
                [
                    "item",
                    f"{item.customer_id}.new_check_ids",
                    "|".join(item.new_check_ids),
                ],
                [
                    "item",
                    f"{item.customer_id}.resolved_check_ids",
                    "|".join(item.resolved_check_ids),
                ],
            ]
        )
    return rows


def _render_html_report(
    *,
    summary_report: KycSummaryReport,
    comparison_report: KycVersionComparisonReport | None,
    replay_report: KycReplayReport | None,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    comparison_section = (
        _comparison_report_to_html(comparison_report)
        if comparison_report is not None
        else "<p>No KYC version comparison report was provided.</p>"
    )
    replay_section = (
        _replay_report_to_html(replay_report)
        if replay_report is not None
        else "<p>No KYC replay report was provided.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KYC Summary Report</title>
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
  <h1>KYC Summary Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Filters</h2>
  {_filters_to_html(summary_report)}

  <h2>Summary</h2>
  {_summary_to_html(summary_report)}

  <h2>Customer Types</h2>
  {_table(["customer_type", "count"], ((item.customer_type, item.count) for item in summary_report.customer_type_counts))}

  <h2>Decision Status</h2>
  {_table(["status", "count"], ((item.status, item.count) for item in summary_report.decision_status_counts))}

  <h2>Check Hits</h2>
  {_table(["check_id", "count"], ((item.check_id, item.count) for item in summary_report.check_hit_counts))}

  <h2>Review Status</h2>
  {_table(["status", "count"], ((item.status, item.count) for item in summary_report.review_status_counts))}

  <h2>KYC Version Comparison</h2>
  {comparison_section}

  <h2>KYC Replay</h2>
  {replay_section}
</body>
</html>
"""


def _filters_to_html(report: KycSummaryReport) -> str:
    rows = [
        ("customer_type", report.customer_type or "all"),
        ("decision_status", report.decision_status or "all"),
        ("watchlist_version_id", report.watchlist_version_id or "all"),
        ("policy_version_id", report.policy_version_id or "all"),
        ("submitted_from", _datetime_or_all(report.submitted_from)),
        ("submitted_to", _datetime_or_all(report.submitted_to)),
        ("decided_from", _datetime_or_all(report.decided_from)),
        ("decided_to", _datetime_or_all(report.decided_to)),
    ]
    return _table(["filter", "value"], rows)


def _summary_to_html(report: KycSummaryReport) -> str:
    rows = [
        ("total_applications", report.total_applications),
        ("average_risk_score", f"{report.average_risk_score:.2f}"),
        ("max_risk_score", report.max_risk_score),
        ("pending_review_count", report.pending_review_count),
    ]
    return _table(["metric", "value"], rows)


def _comparison_report_to_html(report: KycVersionComparisonReport) -> str:
    rows = [
        ("version_type", report.version_type),
        ("baseline_version_id", report.baseline_version_id),
        ("comparison_version_id", report.comparison_version_id),
        ("submitted_from", _datetime_or_all(report.submitted_from)),
        ("submitted_to", _datetime_or_all(report.submitted_to)),
        ("decided_from", _datetime_or_all(report.decided_from)),
        ("decided_to", _datetime_or_all(report.decided_to)),
        ("total_applications_delta", _signed_int(report.total_applications_delta)),
        ("average_risk_score_delta", f"{report.average_risk_score_delta:+.2f}"),
        ("max_risk_score_delta", _signed_int(report.max_risk_score_delta)),
        ("pending_review_delta", _signed_int(report.pending_review_delta)),
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
    check_rows = [
        (
            item.check_id,
            item.baseline_count,
            item.comparison_count,
            _signed_int(item.delta),
        )
        for item in report.check_hit_comparisons
    ]
    return (
        _table(["metric", "value"], rows)
        + "<h2>Decision Status Comparison</h2>"
        + _table(["status", "baseline", "comparison", "delta"], status_rows)
        + "<h2>Check Hit Comparison</h2>"
        + _table(["check_id", "baseline", "comparison", "delta"], check_rows)
    )


def _replay_report_to_html(report: KycReplayReport) -> str:
    rows = [
        ("replay_policy_version_id", report.replay_policy_version_id or "unversioned"),
        (
            "replay_watchlist_version_id",
            report.replay_watchlist_version_id or "unversioned",
        ),
        ("total_applications", report.total_applications),
        ("status_changed_count", report.status_changed_count),
        ("increased_risk_count", report.increased_risk_count),
        ("decreased_risk_count", report.decreased_risk_count),
        ("unchanged_risk_count", report.unchanged_risk_count),
    ]
    item_rows = [
        (
            item.customer_id,
            item.original_status,
            item.replay_status,
            _signed_bool(item.status_changed),
            item.original_risk_score,
            item.replay_risk_score,
            _signed_int(item.risk_score_delta),
            "|".join(item.new_check_ids),
            "|".join(item.resolved_check_ids),
        )
        for item in report.items
    ]
    return (
        _table(["metric", "value"], rows)
        + "<h2>Replay Items</h2>"
        + _table(
            [
                "customer_id",
                "original_status",
                "replay_status",
                "status_changed",
                "original_risk_score",
                "replay_risk_score",
                "risk_score_delta",
                "new_check_ids",
                "resolved_check_ids",
            ],
            item_rows,
        )
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


def _signed_bool(value: bool) -> str:
    return "yes" if value else "no"
