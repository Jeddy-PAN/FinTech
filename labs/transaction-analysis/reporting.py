from __future__ import annotations

import html
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

from transaction_analysis import BudgetVariance, TransactionRepository


class ReportGenerationError(ValueError):
    """Base error for invalid report generation operations."""


def generate_analysis_report(
    repository: TransactionRepository,
    output_directory: str | Path,
    *,
    budget_month: str,
    budget_by_category: dict[str, str | int | Decimal],
) -> Path:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    monthly_cashflow = repository.pandas_monthly_cashflow()
    expense_matrix = repository.category_monthly_expense_matrix()
    budget_variance = repository.compare_monthly_budget(
        budget_month,
        budget_by_category,
    )

    monthly_cashflow_path = output_path / "monthly_cashflow.csv"
    expense_matrix_path = output_path / "monthly_expense_matrix.csv"
    report_path = output_path / "transaction_analysis_report.html"

    monthly_cashflow.to_csv(monthly_cashflow_path, index=False)
    expense_matrix.to_csv(expense_matrix_path, index=False)
    report_path.write_text(
        _render_html_report(
            monthly_cashflow,
            expense_matrix,
            budget_variance,
            budget_month=budget_month,
        ),
        encoding="utf-8",
    )

    return report_path


def _render_html_report(
    monthly_cashflow: pd.DataFrame,
    expense_matrix: pd.DataFrame,
    budget_variance: tuple[BudgetVariance, ...],
    *,
    budget_month: str,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Transaction Analysis Report</title>
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
    .over-budget {{
      color: #b91c1c;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <h1>Transaction Analysis Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Monthly Cashflow</h2>
  {_dataframe_to_html_table(monthly_cashflow)}

  <h2>Monthly Expense Matrix</h2>
  {_dataframe_to_html_table(expense_matrix)}

  <h2>Budget Variance: {html.escape(budget_month)}</h2>
  {_budget_variance_to_html_table(budget_variance)}
</body>
</html>
"""


def _dataframe_to_html_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>No data.</p>"

    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in frame.columns)
    rows = []
    for record in frame.to_dict("records"):
        cells = "".join(
            f"<td>{html.escape(_format_cell(record[column]))}</td>"
            for column in frame.columns
        )
        rows.append(f"<tr>{cells}</tr>")

    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _budget_variance_to_html_table(items: tuple[BudgetVariance, ...]) -> str:
    if not items:
        return "<p>No data.</p>"

    headers = (
        "<th>category</th>"
        "<th>budget</th>"
        "<th>actual</th>"
        "<th>remaining</th>"
        "<th>over_budget</th>"
    )
    rows = []
    for item in items:
        record = asdict(item)
        class_name = ' class="over-budget"' if item.is_over_budget else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(record['category'])}</td>"
            f"<td>{item.budget}</td>"
            f"<td>{item.actual}</td>"
            f"<td{class_name}>{item.remaining}</td>"
            f"<td>{str(item.is_over_budget)}</td>"
            "</tr>"
        )

    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _format_cell(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)

