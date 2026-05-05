from __future__ import annotations

import html
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from portfolio_analysis import PortfolioMetrics, RebalanceTrade, format_percent


def generate_portfolio_report(
    output_directory: str | Path,
    *,
    asset_returns: pd.DataFrame,
    portfolio_returns: pd.Series,
    metrics: PortfolioMetrics,
    correlation_matrix: pd.DataFrame,
    annualized_covariance: pd.DataFrame,
    rebalance_trades: tuple[RebalanceTrade, ...],
) -> Path:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    report_path = output_path / "portfolio_analysis_report.html"
    asset_returns_path = output_path / "asset_returns.csv"
    portfolio_returns_path = output_path / "portfolio_returns.csv"
    correlation_path = output_path / "correlation_matrix.csv"
    covariance_path = output_path / "annualized_covariance_matrix.csv"
    rebalance_path = output_path / "rebalance_trades.csv"

    asset_returns.to_csv(asset_returns_path)
    portfolio_returns.to_frame().to_csv(portfolio_returns_path)
    correlation_matrix.to_csv(correlation_path)
    annualized_covariance.to_csv(covariance_path)
    _rebalance_trades_to_frame(rebalance_trades).to_csv(rebalance_path, index=False)

    report_path.write_text(
        _render_html_report(
            metrics=metrics,
            correlation_matrix=correlation_matrix,
            annualized_covariance=annualized_covariance,
            rebalance_trades=rebalance_trades,
        ),
        encoding="utf-8",
    )

    return report_path


def _render_html_report(
    *,
    metrics: PortfolioMetrics,
    correlation_matrix: pd.DataFrame,
    annualized_covariance: pd.DataFrame,
    rebalance_trades: tuple[RebalanceTrade, ...],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    metrics_frame = pd.DataFrame(
        [
            {"metric": "cumulative_return", "value": format_percent(metrics.cumulative_return)},
            {
                "metric": "annualized_volatility",
                "value": format_percent(metrics.annualized_volatility),
            },
            {"metric": "max_drawdown", "value": format_percent(metrics.max_drawdown)},
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portfolio Analysis Report</title>
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
  <h1>Portfolio Analysis Report</h1>
  <div class="meta">Generated at {html.escape(generated_at)}</div>

  <h2>Portfolio Metrics</h2>
  {_dataframe_to_html_table(metrics_frame)}

  <h2>Correlation Matrix</h2>
  {_dataframe_to_html_table(correlation_matrix.reset_index())}

  <h2>Annualized Covariance Matrix</h2>
  {_dataframe_to_html_table(annualized_covariance.reset_index())}

  <h2>Rebalance Trades</h2>
  {_dataframe_to_html_table(_rebalance_trades_to_frame(rebalance_trades))}
</body>
</html>
"""


def _rebalance_trades_to_frame(trades: tuple[RebalanceTrade, ...]) -> pd.DataFrame:
    return pd.DataFrame([asdict(trade) for trade in trades])


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


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)

