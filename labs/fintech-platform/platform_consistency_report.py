from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlite_platform_store import PlatformRunSnapshot


@dataclass(frozen=True)
class PlatformConsistencyFinding:
    run_id: str
    check_id: str
    status: str
    severity: str
    message: str


@dataclass(frozen=True)
class PlatformConsistencyReportExportPaths:
    findings_csv: Path
    html_report: Path


def evaluate_platform_run_consistency(
    snapshots: tuple[PlatformRunSnapshot, ...],
) -> tuple[PlatformConsistencyFinding, ...]:
    findings: list[PlatformConsistencyFinding] = []
    for snapshot in snapshots:
        findings.extend(_evaluate_snapshot(snapshot))
    return tuple(findings)


def export_platform_consistency_report(
    output_directory: str | Path,
    *,
    snapshots: tuple[PlatformRunSnapshot, ...],
) -> PlatformConsistencyReportExportPaths:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    findings = evaluate_platform_run_consistency(snapshots)
    findings_csv = output_path / "platform_consistency_findings.csv"
    html_report = output_path / "platform_consistency_report.html"

    _write_findings_csv(findings_csv, findings)
    html_report.write_text(_render_html_report(findings), encoding="utf-8")

    return PlatformConsistencyReportExportPaths(
        findings_csv=findings_csv,
        html_report=html_report,
    )


def _evaluate_snapshot(
    snapshot: PlatformRunSnapshot,
) -> tuple[PlatformConsistencyFinding, ...]:
    findings = [
        _check_audit_event_count(snapshot),
        _check_event_time_order(snapshot),
        _check_ledger_event_matches_record(snapshot),
    ]
    findings.extend(_check_status_contract(snapshot))
    return tuple(findings)


def _check_audit_event_count(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    expected = snapshot.record.audit_event_count
    actual = len(snapshot.audit_events)
    if expected == actual:
        return _pass(
            snapshot,
            "audit_event_count_matches",
            f"Audit event count matches: {actual}",
        )
    return _fail(
        snapshot,
        "audit_event_count_matches",
        f"Expected {expected} audit events but found {actual}",
    )


def _check_event_time_order(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    previous = None
    for event in snapshot.audit_events:
        if previous is not None and event.occurred_at < previous:
            return _fail(
                snapshot,
                "audit_event_time_order",
                "Audit events are not ordered by occurred_at",
            )
        previous = event.occurred_at
    return _pass(
        snapshot,
        "audit_event_time_order",
        "Audit events are ordered by occurred_at",
    )


def _check_ledger_event_matches_record(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    ledger_events = [
        event
        for event in snapshot.audit_events
        if event.event_type == "ledger_transaction.posted"
    ]
    ledger_transaction_id = snapshot.record.ledger_transaction_id
    if ledger_transaction_id is None:
        if ledger_events:
            return _fail(
                snapshot,
                "ledger_event_matches_record",
                "Ledger event exists but run record has no ledger transaction id",
            )
        return _pass(
            snapshot,
            "ledger_event_matches_record",
            "No ledger transaction is recorded or posted",
        )
    if any(event.aggregate_id == ledger_transaction_id for event in ledger_events):
        return _pass(
            snapshot,
            "ledger_event_matches_record",
            "Ledger posted event matches the run record",
        )
    return _fail(
        snapshot,
        "ledger_event_matches_record",
        "Run record has a ledger transaction id but no matching ledger posted event",
    )


def _check_status_contract(
    snapshot: PlatformRunSnapshot,
) -> tuple[PlatformConsistencyFinding, ...]:
    status = snapshot.record.status
    if status == "completed":
        return (_check_completed_contract(snapshot),)
    if status == "risk_review_rejected":
        return (_check_risk_review_rejected_contract(snapshot),)
    if status == "risk_review_required":
        return (_check_risk_review_required_contract(snapshot),)
    if status == "risk_blocked":
        return (_check_risk_blocked_contract(snapshot),)
    if status == "kyc_blocked":
        return (_check_kyc_blocked_contract(snapshot),)
    if status == "kyc_review_required":
        return (_check_kyc_review_required_contract(snapshot),)
    return (
        _fail(
            snapshot,
            "platform_status_contract",
            f"Unknown platform status: {status}",
        ),
    )


def _check_completed_contract(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    event_types = _event_types(snapshot)
    if snapshot.record.payment_order_status != "succeeded":
        return _fail(snapshot, "platform_status_contract", "Completed run must have a succeeded payment order")
    if snapshot.record.ledger_transaction_id is None:
        return _fail(snapshot, "platform_status_contract", "Completed run must have a ledger transaction id")
    if "payment_order.succeeded" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Completed run must include payment_order.succeeded")
    if "ledger_transaction.posted" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Completed run must include ledger_transaction.posted")
    if snapshot.record.risk_review_case_id and "review_case.approved" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Completed reviewed run must include review_case.approved")
    return _pass(snapshot, "platform_status_contract", "Completed run has succeeded order and ledger posting")


def _check_risk_review_rejected_contract(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    event_types = _event_types(snapshot)
    if snapshot.record.payment_order_status != "failed":
        return _fail(snapshot, "platform_status_contract", "Rejected risk review must have a failed payment order")
    if snapshot.record.ledger_transaction_id is not None:
        return _fail(snapshot, "platform_status_contract", "Rejected risk review must not have a ledger transaction id")
    if "review_case.rejected" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Rejected risk review must include review_case.rejected")
    if "payment_order.failed" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Rejected risk review must include payment_order.failed")
    if "ledger_transaction.posted" in event_types:
        return _fail(snapshot, "platform_status_contract", "Rejected risk review must not include ledger_transaction.posted")
    return _pass(snapshot, "platform_status_contract", "Rejected risk review has failed order and no ledger posting")


def _check_risk_review_required_contract(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    event_types = _event_types(snapshot)
    if snapshot.record.payment_order_status != "pending":
        return _fail(snapshot, "platform_status_contract", "Pending risk review must keep payment order pending")
    if not snapshot.record.risk_review_case_id:
        return _fail(snapshot, "platform_status_contract", "Pending risk review must have a review case id")
    if snapshot.record.ledger_transaction_id is not None:
        return _fail(snapshot, "platform_status_contract", "Pending risk review must not have a ledger transaction id")
    if "review_case.created" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Pending risk review must include review_case.created")
    if "payment_order.succeeded" in event_types or "payment_order.failed" in event_types:
        return _fail(snapshot, "platform_status_contract", "Pending risk review must not include final payment status events")
    return _pass(snapshot, "platform_status_contract", "Pending risk review has review case and no final posting")


def _check_risk_blocked_contract(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    event_types = _event_types(snapshot)
    if snapshot.record.payment_order_status != "failed":
        return _fail(snapshot, "platform_status_contract", "Risk blocked run must have a failed payment order")
    if snapshot.record.ledger_transaction_id is not None:
        return _fail(snapshot, "platform_status_contract", "Risk blocked run must not have a ledger transaction id")
    if "payment_order.failed" not in event_types:
        return _fail(snapshot, "platform_status_contract", "Risk blocked run must include payment_order.failed")
    return _pass(snapshot, "platform_status_contract", "Risk blocked run has failed order and no ledger posting")


def _check_kyc_blocked_contract(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    if snapshot.record.payment_order_id is not None:
        return _fail(snapshot, "platform_status_contract", "KYC blocked run must not create a payment order")
    if snapshot.record.ledger_transaction_id is not None:
        return _fail(snapshot, "platform_status_contract", "KYC blocked run must not have a ledger transaction id")
    return _pass(snapshot, "platform_status_contract", "KYC blocked run stops before payment order")


def _check_kyc_review_required_contract(
    snapshot: PlatformRunSnapshot,
) -> PlatformConsistencyFinding:
    if snapshot.record.payment_order_id is not None:
        return _fail(snapshot, "platform_status_contract", "KYC review run must not create a payment order")
    if snapshot.record.ledger_transaction_id is not None:
        return _fail(snapshot, "platform_status_contract", "KYC review run must not have a ledger transaction id")
    return _pass(snapshot, "platform_status_contract", "KYC review run stops before payment order")


def _write_findings_csv(
    path: Path,
    findings: tuple[PlatformConsistencyFinding, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["run_id", "check_id", "status", "severity", "message"])
        for finding in findings:
            writer.writerow(
                [
                    finding.run_id,
                    finding.check_id,
                    finding.status,
                    finding.severity,
                    finding.message,
                ]
            )


def _render_html_report(
    findings: tuple[PlatformConsistencyFinding, ...],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    failed_count = sum(1 for finding in findings if finding.status == "failed")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinTech Platform Consistency Report</title>
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
  <h1>FinTech Platform Consistency Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>
  <p>Total findings: {len(findings)}; failed findings: {failed_count}</p>
  {_findings_to_html(findings)}
</body>
</html>
"""


def _findings_to_html(
    findings: tuple[PlatformConsistencyFinding, ...],
) -> str:
    headers = ["run_id", "check_id", "status", "severity", "message"]
    rows = (
        (
            finding.run_id,
            finding.check_id,
            finding.status,
            finding.severity,
            finding.message,
        )
        for finding in findings
    )
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        row_html.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )


def _event_types(snapshot: PlatformRunSnapshot) -> set[str]:
    return {event.event_type for event in snapshot.audit_events}


def _pass(
    snapshot: PlatformRunSnapshot,
    check_id: str,
    message: str,
) -> PlatformConsistencyFinding:
    return PlatformConsistencyFinding(
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
) -> PlatformConsistencyFinding:
    return PlatformConsistencyFinding(
        run_id=snapshot.record.run_id,
        check_id=check_id,
        status="failed",
        severity="error",
        message=message,
    )
