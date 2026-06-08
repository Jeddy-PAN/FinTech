from __future__ import annotations

import csv
import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from compliance_audit import ComplianceAuditEvent
from sqlite_platform_store import PlatformRunSnapshot


@dataclass(frozen=True)
class PlatformLedgerReconciliationFinding:
    run_id: str
    check_id: str
    status: str
    severity: str
    message: str


@dataclass(frozen=True)
class PlatformLedgerReconciliationReportExportPaths:
    findings_csv: Path
    html_report: Path


def evaluate_platform_ledger_reconciliation(
    snapshots: tuple[PlatformRunSnapshot, ...],
) -> tuple[PlatformLedgerReconciliationFinding, ...]:
    findings: list[PlatformLedgerReconciliationFinding] = []
    for snapshot in snapshots:
        if snapshot.record.status == "completed":
            findings.extend(_evaluate_completed_snapshot(snapshot))
        else:
            findings.append(_check_non_posting_run(snapshot))
    return tuple(findings)


def export_platform_ledger_reconciliation_report(
    output_directory: str | Path,
    *,
    snapshots: tuple[PlatformRunSnapshot, ...],
) -> PlatformLedgerReconciliationReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    findings = evaluate_platform_ledger_reconciliation(snapshots)
    findings_csv = output_path / "platform_ledger_reconciliation_findings.csv"
    html_report = output_path / "platform_ledger_reconciliation_report.html"

    _write_findings_csv(findings_csv, findings)
    html_report.write_text(_render_html_report(findings), encoding="utf-8")

    return PlatformLedgerReconciliationReportExportPaths(
        findings_csv=findings_csv,
        html_report=html_report,
    )


def _evaluate_completed_snapshot(
    snapshot: PlatformRunSnapshot,
) -> tuple[PlatformLedgerReconciliationFinding, ...]:
    return (
        _check_completed_amounts(snapshot),
        _check_completed_balances(snapshot),
    )


def _check_completed_amounts(
    snapshot: PlatformRunSnapshot,
) -> PlatformLedgerReconciliationFinding:
    payment_amount = _payment_order_amount(snapshot)
    ledger_amount = _ledger_amount(snapshot)
    if payment_amount is None:
        return _fail(
            snapshot,
            "completed_ledger_amount_matches_payment_order",
            "Completed run has no payment order amount in audit events",
        )
    if ledger_amount is None:
        return _fail(
            snapshot,
            "completed_ledger_amount_matches_payment_order",
            "Completed run has no ledger amount in audit events",
        )
    if payment_amount == ledger_amount:
        return _pass(
            snapshot,
            "completed_ledger_amount_matches_payment_order",
            f"Payment amount matches ledger amount: {ledger_amount}",
        )
    return _fail(
        snapshot,
        "completed_ledger_amount_matches_payment_order",
        f"Completed run has payment amount {payment_amount} but ledger amount {ledger_amount}",
    )


def _check_completed_balances(
    snapshot: PlatformRunSnapshot,
) -> PlatformLedgerReconciliationFinding:
    ledger_amount = _ledger_amount(snapshot)
    if ledger_amount is None:
        return _fail(
            snapshot,
            "completed_balances_match_ledger_amount",
            "Completed run has no ledger amount to compare with balances",
        )
    record = snapshot.record
    if (
        record.platform_bank_balance == ledger_amount
        and record.user_wallet_balance == ledger_amount
    ):
        return _pass(
            snapshot,
            "completed_balances_match_ledger_amount",
            f"Platform bank and user wallet balances match ledger amount: {ledger_amount}",
        )
    return _fail(
        snapshot,
        "completed_balances_match_ledger_amount",
        (
            f"Completed run balance mismatch: "
            f"platform_bank_balance={record.platform_bank_balance} "
            f"user_wallet_balance={record.user_wallet_balance} "
            f"ledger_amount={ledger_amount}"
        ),
    )


def _check_non_posting_run(
    snapshot: PlatformRunSnapshot,
) -> PlatformLedgerReconciliationFinding:
    ledger_events = _ledger_events(snapshot)
    record = snapshot.record
    if (
        not ledger_events
        and record.ledger_transaction_id is None
        and record.platform_bank_balance == Decimal("0.00")
        and record.user_wallet_balance == Decimal("0.00")
    ):
        return _pass(
            snapshot,
            "non_posting_run_has_no_ledger_artifacts",
            "Non-posting run has no ledger events, ledger id, or balances",
        )
    return _fail(
        snapshot,
        "non_posting_run_has_no_ledger_artifacts",
        (
            f"Non-posting run must not have ledger events or non-zero balances: "
            f"ledger_events={len(ledger_events)} "
            f"ledger_transaction_id={record.ledger_transaction_id or ''} "
            f"platform_bank_balance={record.platform_bank_balance} "
            f"user_wallet_balance={record.user_wallet_balance}"
        ),
    )


def _payment_order_amount(snapshot: PlatformRunSnapshot) -> Decimal | None:
    payment_order_id = snapshot.record.payment_order_id
    if payment_order_id is None:
        return None
    for event in snapshot.audit_events:
        if event.event_type != "payment_order.succeeded":
            continue
        if event.aggregate_id != payment_order_id:
            continue
        return _payload_amount(event)
    return None


def _ledger_amount(snapshot: PlatformRunSnapshot) -> Decimal | None:
    ledger_transaction_id = snapshot.record.ledger_transaction_id
    if ledger_transaction_id is None:
        return None
    for event in _ledger_events(snapshot):
        if event.aggregate_id == ledger_transaction_id:
            return _payload_amount(event)
    return None


def _ledger_events(snapshot: PlatformRunSnapshot) -> tuple[ComplianceAuditEvent, ...]:
    return tuple(
        event
        for event in snapshot.audit_events
        if event.event_type == "ledger_transaction.posted"
    )


def _payload_amount(event: ComplianceAuditEvent) -> Decimal | None:
    try:
        payload = json.loads(event.payload)
    except json.JSONDecodeError:
        return None
    amount = payload.get("amount")
    if amount is None:
        return None
    try:
        return Decimal(str(amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _write_findings_csv(
    path: Path,
    findings: tuple[PlatformLedgerReconciliationFinding, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["run_id", "check_id", "status", "severity", "message"])
        for finding in findings:
            writer.writerow(_finding_values(finding))


def _render_html_report(
    findings: tuple[PlatformLedgerReconciliationFinding, ...],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    failed_count = sum(1 for finding in findings if finding.status == "failed")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Ledger Reconciliation Report</title>
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
  <h1>FinTech Platform Ledger Reconciliation Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>
  <p>Total findings: {len(findings)}; failed findings: {failed_count}</p>
  {_findings_to_html(findings)}
</body>
</html>
"""


def _findings_to_html(
    findings: tuple[PlatformLedgerReconciliationFinding, ...],
) -> str:
    headers = ["run_id", "check_id", "status", "severity", "message"]
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for finding in findings:
        cells = "".join(
            f"<td>{html.escape(str(value))}</td>"
            for value in _finding_values(finding)
        )
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _finding_values(finding: PlatformLedgerReconciliationFinding) -> list[object]:
    return [
        finding.run_id,
        finding.check_id,
        finding.status,
        finding.severity,
        finding.message,
    ]


def _pass(
    snapshot: PlatformRunSnapshot,
    check_id: str,
    message: str,
) -> PlatformLedgerReconciliationFinding:
    return PlatformLedgerReconciliationFinding(
        run_id=snapshot.record.run_id,
        check_id=check_id,
        status="passed",
        severity="info",
        message=message,
    )


def _fail(
    snapshot: PlatformRunSnapshot,
    check_id: str,
    message: str,
) -> PlatformLedgerReconciliationFinding:
    return PlatformLedgerReconciliationFinding(
        run_id=snapshot.record.run_id,
        check_id=check_id,
        status="failed",
        severity="error",
        message=message,
    )
