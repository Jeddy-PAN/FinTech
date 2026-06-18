from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path

from core_banking_audit import CoreBankingAuditRecorder, audit_payload
from core_banking import AccountPosting, MonthlyStatement, PostingDirection


@dataclass(frozen=True)
class StatementExportResult:
    summary_csv_path: Path
    postings_csv_path: Path


@dataclass(frozen=True)
class StatementHtmlExportResult:
    html_path: Path


def export_monthly_statement_csv(
    statement: MonthlyStatement,
    output_directory: str | Path,
    *,
    file_prefix: str | None = None,
    audit_recorder: CoreBankingAuditRecorder | None = None,
) -> StatementExportResult:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    prefix = _safe_file_prefix(file_prefix or _default_file_prefix(statement))
    summary_csv_path = output_path / f"{prefix}_summary.csv"
    postings_csv_path = output_path / f"{prefix}_postings.csv"

    _write_summary_csv(statement, summary_csv_path)
    _write_postings_csv(statement.postings, postings_csv_path)

    if audit_recorder is not None:
        audit_recorder.record_audit_event(
            "statement.exported",
            account_id=statement.account_id,
            payload=audit_payload(
                period_start=statement.period_start,
                period_end=statement.period_end,
                opening_balance=statement.opening_balance,
                closing_balance=statement.closing_balance,
                posting_count=len(statement.postings),
                summary_csv_path=summary_csv_path,
                postings_csv_path=postings_csv_path,
            ),
            source="core_banking_statement_export",
        )

    return StatementExportResult(
        summary_csv_path=summary_csv_path,
        postings_csv_path=postings_csv_path,
    )


def export_monthly_statement_html(
    statement: MonthlyStatement,
    output_directory: str | Path,
    *,
    file_prefix: str | None = None,
    audit_recorder: CoreBankingAuditRecorder | None = None,
) -> StatementHtmlExportResult:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    prefix = _safe_file_prefix(file_prefix or _default_file_prefix(statement))
    html_path = output_path / f"{prefix}.html"

    html_path.write_text(_render_statement_html(statement), encoding="utf-8")

    if audit_recorder is not None:
        audit_recorder.record_audit_event(
            "statement.html_exported",
            account_id=statement.account_id,
            payload=audit_payload(
                period_start=statement.period_start,
                period_end=statement.period_end,
                opening_balance=statement.opening_balance,
                closing_balance=statement.closing_balance,
                posting_count=len(statement.postings),
                html_path=html_path,
            ),
            source="core_banking_statement_export",
        )

    return StatementHtmlExportResult(html_path=html_path)


def _write_summary_csv(statement: MonthlyStatement, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "account_id",
                "period_start",
                "period_end",
                "opening_balance",
                "closing_balance",
                "total_credits",
                "total_debits",
                "interest_credited",
                "posting_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "account_id": statement.account_id,
                "period_start": statement.period_start.isoformat(),
                "period_end": statement.period_end.isoformat(),
                "opening_balance": str(statement.opening_balance),
                "closing_balance": str(statement.closing_balance),
                "total_credits": str(statement.total_credits),
                "total_debits": str(statement.total_debits),
                "interest_credited": str(statement.interest_credited),
                "posting_count": str(len(statement.postings)),
            }
        )


def _write_postings_csv(postings: tuple[AccountPosting, ...], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "posting_id",
                "account_id",
                "posted_at",
                "direction",
                "posting_type",
                "amount",
                "signed_amount",
                "currency",
                "description",
                "idempotency_key",
                "request_fingerprint",
            ],
        )
        writer.writeheader()
        for posting in postings:
            writer.writerow(
                {
                    "posting_id": posting.posting_id,
                    "account_id": posting.account_id,
                    "posted_at": posting.posted_at.isoformat(),
                    "direction": posting.direction.value,
                    "posting_type": posting.posting_type.value,
                    "amount": str(posting.amount),
                    "signed_amount": str(_signed_amount(posting)),
                    "currency": posting.currency,
                    "description": posting.description,
                    "idempotency_key": posting.idempotency_key or "",
                    "request_fingerprint": posting.request_fingerprint or "",
                }
            )


def _signed_amount(posting: AccountPosting) -> Decimal:
    if posting.direction == PostingDirection.CREDIT:
        return posting.amount
    return -posting.amount


def _render_statement_html(statement: MonthlyStatement) -> str:
    rows = "\n".join(_render_posting_row(posting) for posting in statement.postings)
    if not rows:
        rows = (
            "<tr>"
            '<td colspan="6" class="empty">No postings in this statement period.</td>'
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Account Statement - {escape(statement.account_id)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: #d8dee8;
      --panel: #f7f9fc;
      --credit: #116b45;
      --debit: #9f2d2d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.45;
    }}
    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 28px auto 48px;
    }}
    header {{
      border-bottom: 2px solid var(--ink);
      padding-bottom: 16px;
      margin-bottom: 20px;
    }}
    h1 {{
      font-size: 28px;
      margin: 0 0 6px;
      letter-spacing: 0;
    }}
    h2 {{
      font-size: 18px;
      margin: 24px 0 12px;
      letter-spacing: 0;
    }}
    .meta, .note {{
      color: var(--muted);
      font-size: 14px;
      margin: 0;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
      margin: 18px 0 22px;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      padding: 12px;
      min-height: 72px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .metric strong {{
      display: block;
      font-size: 20px;
      overflow-wrap: anywhere;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #eef2f7;
      color: #273444;
      font-size: 12px;
      text-transform: uppercase;
    }}
    td.amount, th.amount {{
      text-align: right;
      white-space: nowrap;
    }}
    .credit {{ color: var(--credit); font-weight: 700; }}
    .debit {{ color: var(--debit); font-weight: 700; }}
    .empty {{
      color: var(--muted);
      text-align: center;
      padding: 18px;
    }}
    .footnote {{
      border-top: 1px solid var(--line);
      margin-top: 24px;
      padding-top: 12px;
    }}
    @media (max-width: 720px) {{
      main {{ width: min(100% - 20px, 1080px); margin-top: 18px; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
      h1 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Account Statement</h1>
      <p class="meta">Account {escape(statement.account_id)} · {statement.period_start.isoformat()} to {statement.period_end.isoformat()}</p>
    </header>

    <section aria-label="Statement summary">
      <div class="summary">
        {_metric("Opening Balance", statement.opening_balance)}
        {_metric("Closing Balance", statement.closing_balance)}
        {_metric("Total Credits", statement.total_credits)}
        {_metric("Total Debits", statement.total_debits)}
        {_metric("Interest Credited", statement.interest_credited)}
        {_metric("Posting Count", len(statement.postings))}
      </div>
    </section>

    <section aria-label="Posting details">
      <h2>Posting Details</h2>
      <table>
        <thead>
          <tr>
            <th>Posted At</th>
            <th>Type</th>
            <th>Direction</th>
            <th class="amount">Signed Amount</th>
            <th>Description</th>
            <th>Idempotency Key</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </section>

    <p class="note footnote">Teaching report only. This is not a formal bank statement, disclosure, customer notice, legal record, or regulatory report.</p>
  </main>
</body>
</html>
"""


def _render_posting_row(posting: AccountPosting) -> str:
    signed_amount = _signed_amount(posting)
    amount_class = "credit" if posting.direction == PostingDirection.CREDIT else "debit"
    return (
        "<tr>"
        f"<td>{escape(posting.posted_at.isoformat())}</td>"
        f"<td>{escape(posting.posting_type.value)}</td>"
        f"<td>{escape(posting.direction.value)}</td>"
        f'<td class="amount {amount_class}">{escape(str(signed_amount))}</td>'
        f"<td>{escape(posting.description)}</td>"
        f"<td>{escape(posting.idempotency_key or '')}</td>"
        "</tr>"
    )


def _metric(label: str, value: object) -> str:
    return (
        '<div class="metric">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</div>"
    )


def _default_file_prefix(statement: MonthlyStatement) -> str:
    return (
        f"statement_{statement.account_id}_"
        f"{statement.period_start.isoformat()}_{statement.period_end.isoformat()}"
    )


def _safe_file_prefix(value: str) -> str:
    allowed = []
    for character in value.strip():
        if character.isalnum() or character in {"-", "_"}:
            allowed.append(character)
        else:
            allowed.append("_")
    prefix = "".join(allowed).strip("_")
    if not prefix:
        raise ValueError("file_prefix cannot be blank")
    return prefix
