from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from compliance_audit import (
    AuditSummary,
    AuditTimeline,
    AuditAccessRecorder,
    AuditExportApproval,
    AuditUser,
    ComplianceAuditEvent,
    EXPORT_AUDIT_REPORT,
    authorize_user,
    authorize_user_with_audit,
    summarize_audit_events,
    validate_export_approval,
)


@dataclass(frozen=True)
class ComplianceAuditExportPaths:
    events_csv: Path
    summary_csv: Path
    timeline_csv: Path | None
    html_report: Path


def export_compliance_audit_report(
    output_directory: str | Path,
    *,
    events: tuple[ComplianceAuditEvent, ...],
    summary: AuditSummary | None = None,
    timeline: AuditTimeline | None = None,
    requested_by: AuditUser | None = None,
    access_recorder: AuditAccessRecorder | None = None,
    accessed_at: datetime | None = None,
    require_approval: bool = False,
    approval: AuditExportApproval | None = None,
) -> ComplianceAuditExportPaths:
    if requested_by is not None:
        if access_recorder is not None:
            if accessed_at is None:
                raise ValueError("accessed_at is required when recording export access")
            authorize_user_with_audit(
                requested_by,
                EXPORT_AUDIT_REPORT,
                recorder=access_recorder,
                target="compliance_audit_report",
                occurred_at=accessed_at,
            )
        else:
            authorize_user(requested_by, EXPORT_AUDIT_REPORT)
        if require_approval:
            validate_export_approval(
                requested_by=requested_by,
                approval=approval,
                recorder=access_recorder,
            )
    elif require_approval:
        raise ValueError("requested_by is required when approval is required")

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    resolved_summary = summary or summarize_audit_events(events)
    events_csv = output_path / "compliance_audit_events.csv"
    summary_csv = output_path / "compliance_audit_summary.csv"
    timeline_csv = (
        output_path / "compliance_audit_timeline.csv" if timeline is not None else None
    )
    html_report = output_path / "compliance_audit_report.html"

    _write_events_csv(events_csv, events)
    _write_summary_csv(summary_csv, resolved_summary)
    if timeline is not None and timeline_csv is not None:
        _write_timeline_csv(timeline_csv, timeline)
    html_report.write_text(
        _render_html_report(
            events=events,
            summary=resolved_summary,
            timeline=timeline,
        ),
        encoding="utf-8",
    )

    return ComplianceAuditExportPaths(
        events_csv=events_csv,
        summary_csv=summary_csv,
        timeline_csv=timeline_csv,
        html_report=html_report,
    )


def _write_events_csv(path: Path, events: tuple[ComplianceAuditEvent, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_event_headers())
        for event in events:
            writer.writerow(_event_row(event))


def _write_timeline_csv(path: Path, timeline: AuditTimeline) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["subject_type", "subject_id", *_event_headers()])
        for event in timeline.events:
            writer.writerow([timeline.subject_type, timeline.subject_id, *_event_row(event)])


def _write_summary_csv(path: Path, summary: AuditSummary) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["section", "metric", "value"])
        writer.writerows(_summary_rows(summary))


def _event_headers() -> list[str]:
    return [
        "occurred_at",
        "source_system",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "actor",
        "reason",
        "payload",
        "event_id",
    ]


def _event_row(event: ComplianceAuditEvent) -> list[str]:
    return [
        event.occurred_at.isoformat(),
        event.source_system,
        event.event_type,
        event.aggregate_type,
        event.aggregate_id,
        event.actor,
        event.reason or "",
        event.payload,
        event.event_id,
    ]


def _summary_rows(summary: AuditSummary) -> list[list[object]]:
    rows: list[list[object]] = [["summary", "total_events", summary.total_events]]
    rows.extend(
        ["source_system", source_system, count]
        for source_system, count in summary.source_system_counts
    )
    rows.extend(
        ["event_type", event_type, count]
        for event_type, count in summary.event_type_counts
    )
    rows.extend(["actor", actor, count] for actor, count in summary.actor_counts)
    return rows


def _render_html_report(
    *,
    events: tuple[ComplianceAuditEvent, ...],
    summary: AuditSummary,
    timeline: AuditTimeline | None,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    timeline_section = (
        _timeline_to_html(timeline)
        if timeline is not None
        else "<p>No audit timeline was provided.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Compliance Audit Report</title>
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
    .payload {{
      font-family: Consolas, monospace;
      max-width: 520px;
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
  <h1>Compliance Audit Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Summary</h2>
  {_summary_to_html(summary)}

  <h2>Audit Timeline</h2>
  {timeline_section}

  <h2>Audit Events</h2>
  {_events_to_html(events)}
</body>
</html>
"""


def _summary_to_html(summary: AuditSummary) -> str:
    rows: list[tuple[object, object, object]] = [
        ("summary", "total_events", summary.total_events)
    ]
    rows.extend(
        ("source_system", source_system, count)
        for source_system, count in summary.source_system_counts
    )
    rows.extend(
        ("event_type", event_type, count)
        for event_type, count in summary.event_type_counts
    )
    rows.extend(("actor", actor, count) for actor, count in summary.actor_counts)
    return _table(["section", "metric", "value"], rows)


def _timeline_to_html(timeline: AuditTimeline) -> str:
    rows = [
        (
            timeline.subject_type,
            timeline.subject_id,
            event.occurred_at.isoformat(),
            event.source_system,
            event.event_type,
            f"{event.aggregate_type}:{event.aggregate_id}",
            event.actor,
            event.reason or "",
        )
        for event in timeline.events
    ]
    return _table(
        [
            "subject_type",
            "subject_id",
            "occurred_at",
            "source_system",
            "event_type",
            "aggregate",
            "actor",
            "reason",
        ],
        rows,
    )


def _events_to_html(events: tuple[ComplianceAuditEvent, ...]) -> str:
    rows = [
        (
            event.occurred_at.isoformat(),
            event.source_system,
            event.event_type,
            f"{event.aggregate_type}:{event.aggregate_id}",
            event.actor,
            event.reason or "",
            _Payload(event.payload),
        )
        for event in events
    ]
    return _table(
        [
            "occurred_at",
            "source_system",
            "event_type",
            "aggregate",
            "actor",
            "reason",
            "payload",
        ],
        rows,
    )


@dataclass(frozen=True)
class _Payload:
    value: str


def _table(headers: list[str], rows) -> str:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(_cell(value) for value in row)
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _cell(value) -> str:
    if isinstance(value, _Payload):
        return f'<td class="payload">{html.escape(value.value)}</td>'
    return f"<td>{html.escape(str(value))}</td>"
