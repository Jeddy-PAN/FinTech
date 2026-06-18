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
from compliance_audit import AuditAccessEvent  # noqa: E402
from platform_operation_approval import OperationApprovalRecord  # noqa: E402
from platform_settlement_reconciliation_report import (  # noqa: E402
    PlatformSettlementReconciliationFinding,
)


PROCESS_PLATFORM_PROVIDER_WEBHOOK = "process_platform_provider_webhook"
PLATFORM_PROVIDER_WEBHOOKS_TARGET = "fintech_platform_provider_webhooks"


@dataclass(frozen=True)
class PlatformEvidenceItem:
    evidence_id: str
    evidence_type: str
    source_system: str
    subject_id: str
    severity: str
    summary: str
    recorded_at: datetime
    reference: str


@dataclass(frozen=True)
class PlatformEvidencePackage:
    package_id: str
    case_id: str
    generated_by: str
    generated_at: datetime
    legal_hold: bool
    retention_policy_id: str
    items: tuple[PlatformEvidenceItem, ...]

    @property
    def evidence_count(self) -> int:
        return len(self.items)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for item in self.items if item.severity == "high")

    @property
    def source_counts(self) -> tuple[tuple[str, int], ...]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.source_system] = counts.get(item.source_system, 0) + 1
        return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


@dataclass(frozen=True)
class PlatformEvidencePackageExportPaths:
    items_csv: Path
    summary_csv: Path
    html_report: Path


def build_platform_evidence_package(
    *,
    case_id: str,
    generated_by: str,
    generated_at: datetime,
    settlement_findings: tuple[PlatformSettlementReconciliationFinding, ...] = (),
    access_findings: tuple[AccessAnomalyFinding, ...] = (),
    approval_records: tuple[OperationApprovalRecord, ...] = (),
    access_events: tuple[AuditAccessEvent, ...] = (),
    legal_hold: bool = False,
    retention_policy_id: str = "platform-evidence-educational",
) -> PlatformEvidencePackage:
    normalized_case_id = _require_text(case_id, "case_id")
    normalized_generated_by = _require_text(generated_by, "generated_by")
    timestamp = _validate_timestamp(generated_at, "generated_at")
    normalized_retention_policy_id = _require_text(
        retention_policy_id,
        "retention_policy_id",
    )

    items = [
        *_settlement_evidence_items(settlement_findings),
        *_provider_webhook_evidence_items(access_events),
        *_access_finding_evidence_items(access_findings),
        *_approval_evidence_items(approval_records),
        *_access_event_evidence_items(access_events),
    ]
    sorted_items = tuple(sorted(items, key=_evidence_sort_key))
    return PlatformEvidencePackage(
        package_id=f"evidence_package:{normalized_case_id}",
        case_id=normalized_case_id,
        generated_by=normalized_generated_by,
        generated_at=timestamp,
        legal_hold=legal_hold,
        retention_policy_id=normalized_retention_policy_id,
        items=sorted_items,
    )


def export_platform_evidence_package(
    output_directory: str | Path,
    *,
    package: PlatformEvidencePackage,
) -> PlatformEvidencePackageExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    items_csv = output_path / "platform_evidence_package_items.csv"
    summary_csv = output_path / "platform_evidence_package_summary.csv"
    html_report = output_path / "platform_evidence_package_report.html"

    _write_items_csv(items_csv, package.items)
    _write_summary_csv(summary_csv, package)
    html_report.write_text(_render_html_report(package), encoding="utf-8")
    return PlatformEvidencePackageExportPaths(
        items_csv=items_csv,
        summary_csv=summary_csv,
        html_report=html_report,
    )


def _settlement_evidence_items(
    findings: tuple[PlatformSettlementReconciliationFinding, ...],
) -> tuple[PlatformEvidenceItem, ...]:
    items: list[PlatformEvidenceItem] = []
    for finding in findings:
        if finding.status != "failed":
            continue
        items.append(
            PlatformEvidenceItem(
                evidence_id=(
                    f"settlement:{finding.run_id}:"
                    f"{finding.settlement_id or 'missing'}:{finding.check_id}"
                ),
                evidence_type="settlement_reconciliation_finding",
                source_system="settlement_reconciliation",
                subject_id=finding.run_id,
                severity=_normalize_severity(finding.severity),
                summary=finding.message,
                recorded_at=datetime.now(timezone.utc),
                reference=finding.check_id,
            )
        )
    return tuple(items)


def _provider_webhook_evidence_items(
    events: tuple[AuditAccessEvent, ...],
) -> tuple[PlatformEvidenceItem, ...]:
    items: list[PlatformEvidenceItem] = []
    provider_events = tuple(event for event in events if _is_provider_webhook_event(event))
    for index, event in enumerate(provider_events, start=1):
        items.append(
            PlatformEvidenceItem(
                evidence_id=(
                    f"provider_webhook:{index}:{event.outcome}:"
                    f"{_provider_webhook_subject_id(event)}"
                ),
                evidence_type="provider_webhook_event",
                source_system="payment_provider",
                subject_id=_provider_webhook_subject_id(event),
                severity=_provider_webhook_severity(event),
                summary=_provider_webhook_summary(event),
                recorded_at=_validate_timestamp(event.occurred_at, "occurred_at"),
                reference=f"{event.permission}:{event.target}",
            )
        )
    return tuple(items)


def _access_finding_evidence_items(
    findings: tuple[AccessAnomalyFinding, ...],
) -> tuple[PlatformEvidenceItem, ...]:
    return tuple(
        PlatformEvidenceItem(
            evidence_id=f"access_finding:{finding.finding_type}:{finding.actor}",
            evidence_type="access_anomaly_finding",
            source_system="access_monitoring",
            subject_id=finding.actor,
            severity=_normalize_severity(finding.severity),
            summary=finding.reason,
            recorded_at=_validate_timestamp(
                finding.first_occurred_at,
                "first_occurred_at",
            ),
            reference=finding.finding_type,
        )
        for finding in findings
    )


def _approval_evidence_items(
    records: tuple[OperationApprovalRecord, ...],
) -> tuple[PlatformEvidenceItem, ...]:
    return tuple(
        PlatformEvidenceItem(
            evidence_id=f"approval:{record.approval_id}",
            evidence_type="operation_approval_record",
            source_system="operation_approval",
            subject_id=record.operation_id,
            severity=_approval_severity(record),
            summary=(
                f"{record.operation_type} status={record.status} "
                f"requested_by={record.requested_by} "
                f"approved_by={record.approved_by or ''}"
            ),
            recorded_at=record.decided_at or record.requested_at,
            reference=record.approval_id,
        )
        for record in records
    )


def _access_event_evidence_items(
    events: tuple[AuditAccessEvent, ...],
) -> tuple[PlatformEvidenceItem, ...]:
    items: list[PlatformEvidenceItem] = []
    for index, event in enumerate(events, start=1):
        if event.outcome != "denied":
            continue
        if _is_provider_webhook_event(event):
            continue
        items.append(
            PlatformEvidenceItem(
                evidence_id=f"access_event:{index}:{event.actor}:{event.permission}",
                evidence_type="denied_access_event",
                source_system="access_audit",
                subject_id=event.actor,
                severity="medium",
                summary=event.reason or f"Denied {event.permission} on {event.target}",
                recorded_at=_validate_timestamp(event.occurred_at, "occurred_at"),
                reference=f"{event.permission}:{event.target}",
            )
        )
    return tuple(items)


def _is_provider_webhook_event(event: AuditAccessEvent) -> bool:
    return (
        event.permission == PROCESS_PLATFORM_PROVIDER_WEBHOOK
        and event.target == PLATFORM_PROVIDER_WEBHOOKS_TARGET
    )


def _provider_webhook_subject_id(event: AuditAccessEvent) -> str:
    reason = event.reason or ""
    for part in reason.split():
        if part.startswith("event_id="):
            event_id = part.removeprefix("event_id=").strip()
            if event_id:
                return event_id
    return event.actor


def _provider_webhook_severity(event: AuditAccessEvent) -> str:
    if event.outcome == "denied":
        return "high"
    if "duplicate=True" in (event.reason or ""):
        return "medium"
    return "low"


def _provider_webhook_summary(event: AuditAccessEvent) -> str:
    reason = event.reason or "provider webhook processed"
    return f"Provider webhook {event.outcome}: {reason}"


def _approval_severity(record: OperationApprovalRecord) -> str:
    if record.status == "approved":
        return "high"
    if record.status in {"rejected", "cancelled", "expired"}:
        return "medium"
    return "low"


def _normalize_severity(severity: str) -> str:
    normalized = severity.strip().lower()
    if normalized == "error":
        return "high"
    if normalized == "warning":
        return "medium"
    if normalized in {"high", "medium", "low", "info"}:
        return "low" if normalized == "info" else normalized
    return "medium"


def _write_items_csv(path: Path, items: tuple[PlatformEvidenceItem, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_item_headers())
        for item in items:
            writer.writerow(_item_row(item))


def _write_summary_csv(path: Path, package: PlatformEvidencePackage) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        for row in _summary_rows(package):
            writer.writerow(row)


def _render_html_report(package: PlatformEvidencePackage) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Evidence Package</title>
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
  <h1>FinTech Platform Evidence Package</h1>
  <div class="meta">Generated at {html.escape(package.generated_at.isoformat())}</div>
  <h2>Summary</h2>
  {_table(["metric", "value"], _summary_rows(package))}
  <h2>Source Counts</h2>
  {_table(["source_system", "count"], package.source_counts)}
  <h2>Evidence Items</h2>
  {_table(_item_headers(), (_item_row(item) for item in package.items))}
</body>
</html>
"""


def _summary_rows(package: PlatformEvidencePackage) -> list[tuple[str, object]]:
    return [
        ("package_id", package.package_id),
        ("case_id", package.case_id),
        ("generated_by", package.generated_by),
        ("generated_at", package.generated_at.isoformat()),
        ("legal_hold", str(package.legal_hold).lower()),
        ("retention_policy_id", package.retention_policy_id),
        ("evidence_count", package.evidence_count),
        ("high_severity_count", package.high_severity_count),
    ]


def _item_headers() -> list[str]:
    return [
        "evidence_id",
        "evidence_type",
        "source_system",
        "subject_id",
        "severity",
        "summary",
        "recorded_at",
        "reference",
    ]


def _item_row(item: PlatformEvidenceItem) -> list[object]:
    return [
        item.evidence_id,
        item.evidence_type,
        item.source_system,
        item.subject_id,
        item.severity,
        item.summary,
        item.recorded_at.isoformat(),
        item.reference,
    ]


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


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _validate_timestamp(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _evidence_sort_key(item: PlatformEvidenceItem):
    severity_order = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }
    return (
        severity_order.get(item.severity, 3),
        item.recorded_at,
        item.source_system,
        item.evidence_id,
    )
