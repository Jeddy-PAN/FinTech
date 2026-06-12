from __future__ import annotations

import csv
import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlite_platform_store import PlatformRunSnapshot


PROVIDER_SETTLEMENT_SETTLED = "settled"
PROVIDER_SETTLEMENT_FAILED = "failed"
PROVIDER_SETTLEMENT_REVERSED = "reversed"
PROVIDER_SETTLEMENT_STATUSES = {
    PROVIDER_SETTLEMENT_SETTLED,
    PROVIDER_SETTLEMENT_FAILED,
    PROVIDER_SETTLEMENT_REVERSED,
}


@dataclass(frozen=True)
class ProviderSettlementRow:
    provider: str
    settlement_id: str
    provider_payment_id: str
    platform_run_id: str
    payment_order_id: str
    amount: Decimal
    currency: str
    status: str
    settled_at: datetime


@dataclass(frozen=True)
class PlatformSettlementReconciliationFinding:
    run_id: str
    settlement_id: str | None
    check_id: str
    status: str
    severity: str
    message: str


@dataclass(frozen=True)
class PlatformSettlementReconciliationReportExportPaths:
    findings_csv: Path
    html_report: Path


def evaluate_platform_settlement_reconciliation(
    snapshots: tuple[PlatformRunSnapshot, ...],
    *,
    provider_rows: tuple[ProviderSettlementRow, ...],
) -> tuple[PlatformSettlementReconciliationFinding, ...]:
    snapshots_by_run_id = {snapshot.record.run_id: snapshot for snapshot in snapshots}
    rows_by_run_id: dict[str, list[ProviderSettlementRow]] = {}
    findings: list[PlatformSettlementReconciliationFinding] = []

    for row in provider_rows:
        _validate_provider_row(row)
        rows_by_run_id.setdefault(row.platform_run_id, []).append(row)

    for snapshot in snapshots:
        rows = tuple(rows_by_run_id.get(snapshot.record.run_id, ()))
        if snapshot.record.status == "completed":
            findings.extend(_evaluate_completed_snapshot(snapshot, rows))
        else:
            findings.append(_check_non_completed_snapshot(snapshot, rows))

    for row in provider_rows:
        if row.platform_run_id not in snapshots_by_run_id:
            findings.append(
                _fail(
                    run_id=row.platform_run_id,
                    settlement_id=row.settlement_id,
                    check_id="provider_settlement_has_internal_run",
                    message=(
                        "Provider settlement row has no matching internal platform run: "
                        f"provider={row.provider} provider_payment_id={row.provider_payment_id}"
                    ),
                )
            )

    return tuple(findings)


def export_platform_settlement_reconciliation_report(
    output_directory: str | Path,
    *,
    snapshots: tuple[PlatformRunSnapshot, ...],
    provider_rows: tuple[ProviderSettlementRow, ...],
) -> PlatformSettlementReconciliationReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    findings = evaluate_platform_settlement_reconciliation(
        snapshots,
        provider_rows=provider_rows,
    )
    findings_csv = output_path / "platform_settlement_reconciliation_findings.csv"
    html_report = output_path / "platform_settlement_reconciliation_report.html"

    _write_findings_csv(findings_csv, findings)
    html_report.write_text(_render_html_report(findings), encoding="utf-8")

    return PlatformSettlementReconciliationReportExportPaths(
        findings_csv=findings_csv,
        html_report=html_report,
    )


def _evaluate_completed_snapshot(
    snapshot: PlatformRunSnapshot,
    rows: tuple[ProviderSettlementRow, ...],
) -> tuple[PlatformSettlementReconciliationFinding, ...]:
    settled_rows = tuple(
        row for row in rows if row.status == PROVIDER_SETTLEMENT_SETTLED
    )
    if not rows:
        return (
            _fail(
                run_id=snapshot.record.run_id,
                settlement_id=None,
                check_id="completed_internal_run_has_provider_settlement",
                message="Completed internal run has no provider settlement row",
            ),
        )
    if not settled_rows:
        statuses = ", ".join(row.status for row in rows)
        return (
            _fail(
                run_id=snapshot.record.run_id,
                settlement_id=rows[0].settlement_id,
                check_id="completed_internal_run_has_settled_provider_row",
                message=(
                    "Completed internal run has provider rows but none are settled: "
                    f"statuses={statuses}"
                ),
            ),
        )

    settled_row = settled_rows[0]
    return (
        _pass(
            run_id=snapshot.record.run_id,
            settlement_id=settled_row.settlement_id,
            check_id="completed_internal_run_has_provider_settlement",
            message="Completed internal run has a settled provider row",
        ),
        _check_completed_amount(snapshot, settled_row),
        _check_completed_currency(snapshot, settled_row),
    )


def _check_completed_amount(
    snapshot: PlatformRunSnapshot,
    row: ProviderSettlementRow,
) -> PlatformSettlementReconciliationFinding:
    internal_amount = _payment_order_amount(snapshot)
    if internal_amount is None:
        return _fail(
            run_id=snapshot.record.run_id,
            settlement_id=row.settlement_id,
            check_id="provider_settlement_amount_matches_internal_payment",
            message="Completed internal run has no payment amount in audit events",
        )
    if internal_amount == row.amount:
        return _pass(
            run_id=snapshot.record.run_id,
            settlement_id=row.settlement_id,
            check_id="provider_settlement_amount_matches_internal_payment",
            message=f"Provider settlement amount matches internal amount: {row.amount}",
        )
    return _fail(
        run_id=snapshot.record.run_id,
        settlement_id=row.settlement_id,
        check_id="provider_settlement_amount_matches_internal_payment",
        message=(
            f"Provider settlement amount {row.amount} does not match "
            f"internal amount {internal_amount}"
        ),
    )


def _check_completed_currency(
    snapshot: PlatformRunSnapshot,
    row: ProviderSettlementRow,
) -> PlatformSettlementReconciliationFinding:
    internal_currency = _payment_order_currency(snapshot)
    if internal_currency is None:
        return _fail(
            run_id=snapshot.record.run_id,
            settlement_id=row.settlement_id,
            check_id="provider_settlement_currency_matches_internal_payment",
            message="Completed internal run has no payment currency in audit events",
        )
    if internal_currency == row.currency:
        return _pass(
            run_id=snapshot.record.run_id,
            settlement_id=row.settlement_id,
            check_id="provider_settlement_currency_matches_internal_payment",
            message=f"Provider settlement currency matches internal currency: {row.currency}",
        )
    return _fail(
        run_id=snapshot.record.run_id,
        settlement_id=row.settlement_id,
        check_id="provider_settlement_currency_matches_internal_payment",
        message=(
            f"Provider settlement currency {row.currency} does not match "
            f"internal currency {internal_currency}"
        ),
    )


def _check_non_completed_snapshot(
    snapshot: PlatformRunSnapshot,
    rows: tuple[ProviderSettlementRow, ...],
) -> PlatformSettlementReconciliationFinding:
    settled_rows = tuple(
        row for row in rows if row.status == PROVIDER_SETTLEMENT_SETTLED
    )
    if not settled_rows:
        return _pass(
            run_id=snapshot.record.run_id,
            settlement_id=rows[0].settlement_id if rows else None,
            check_id="non_completed_internal_run_has_no_provider_settlement",
            message="Non-completed internal run has no settled provider row",
        )
    return _fail(
        run_id=snapshot.record.run_id,
        settlement_id=settled_rows[0].settlement_id,
        check_id="non_completed_internal_run_has_no_provider_settlement",
        message=(
            "Non-completed internal run must not have a settled provider row: "
            f"internal_status={snapshot.record.status}"
        ),
    )


def _payment_order_amount(snapshot: PlatformRunSnapshot) -> Decimal | None:
    payload = _payment_order_success_payload(snapshot)
    if payload is None:
        return None
    try:
        return Decimal(str(payload["amount"])).quantize(Decimal("0.01"))
    except (KeyError, InvalidOperation, ValueError):
        return None


def _payment_order_currency(snapshot: PlatformRunSnapshot) -> str | None:
    payload = _payment_order_success_payload(snapshot)
    if payload is None:
        return None
    currency = payload.get("currency", "USD")
    if currency is None:
        return None
    normalized = str(currency).strip().upper()
    return normalized or None


def _payment_order_success_payload(snapshot: PlatformRunSnapshot) -> dict | None:
    payment_order_id = snapshot.record.payment_order_id
    if payment_order_id is None:
        return None
    for event in snapshot.audit_events:
        if event.event_type != "payment_order.succeeded":
            continue
        if event.aggregate_id != payment_order_id:
            continue
        try:
            return json.loads(event.payload)
        except json.JSONDecodeError:
            return None
    return None


def _validate_provider_row(row: ProviderSettlementRow) -> None:
    _require_text(row.provider, "provider")
    _require_text(row.settlement_id, "settlement_id")
    _require_text(row.provider_payment_id, "provider_payment_id")
    _require_text(row.platform_run_id, "platform_run_id")
    _require_text(row.payment_order_id, "payment_order_id")
    if row.amount < Decimal("0.00"):
        raise ValueError("amount must be greater than or equal to 0")
    _require_text(row.currency, "currency")
    if row.status not in PROVIDER_SETTLEMENT_STATUSES:
        raise ValueError(f"Unknown provider settlement status: {row.status}")
    if row.settled_at.tzinfo is None or row.settled_at.utcoffset() is None:
        raise ValueError("settled_at must be timezone-aware")


def _require_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _write_findings_csv(
    path: Path,
    findings: tuple[PlatformSettlementReconciliationFinding, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(_finding_headers())
        for finding in findings:
            writer.writerow(_finding_values(finding))


def _render_html_report(
    findings: tuple[PlatformSettlementReconciliationFinding, ...],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    failed_count = sum(1 for finding in findings if finding.status == "failed")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Settlement Reconciliation Report</title>
  <style>
    body {{
      color: #1f2937;
      font-family: Arial, sans-serif;
      line-height: 1.5;
      margin: 32px;
    }}
    table {{
      border-collapse: collapse;
      margin-top: 12px;
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
  <h1>FinTech Platform Settlement Reconciliation Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>
  <p>Total findings: {len(findings)}; failed findings: {failed_count}</p>
  {_table(_finding_headers(), (_finding_values(finding) for finding in findings))}
</body>
</html>
"""


def _table(headers: list[str], rows) -> str:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(_csv_value(value)))}</td>" for value in row
        )
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _finding_headers() -> list[str]:
    return ["run_id", "settlement_id", "check_id", "status", "severity", "message"]


def _finding_values(finding: PlatformSettlementReconciliationFinding) -> list[object]:
    return [
        finding.run_id,
        finding.settlement_id,
        finding.check_id,
        finding.status,
        finding.severity,
        finding.message,
    ]


def _pass(
    *,
    run_id: str,
    settlement_id: str | None,
    check_id: str,
    message: str,
) -> PlatformSettlementReconciliationFinding:
    return PlatformSettlementReconciliationFinding(
        run_id=run_id,
        settlement_id=settlement_id,
        check_id=check_id,
        status="passed",
        severity="info",
        message=message,
    )


def _fail(
    *,
    run_id: str,
    settlement_id: str | None,
    check_id: str,
    message: str,
) -> PlatformSettlementReconciliationFinding:
    return PlatformSettlementReconciliationFinding(
        run_id=run_id,
        settlement_id=settlement_id,
        check_id=check_id,
        status="failed",
        severity="error",
        message=message,
    )


def _csv_value(value: object) -> object:
    return "" if value is None else value
