import sys
from pathlib import Path

from portfolio_analysis import (
    calculate_correlation_matrix,
    calculate_covariance_matrix,
    calculate_portfolio_metrics,
    calculate_portfolio_returns,
    calculate_portfolio_volatility_from_covariance,
    calculate_rebalance_trades,
    calculate_returns,
    format_percent,
    load_price_history,
)
from portfolio_reporting import generate_portfolio_report


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    lab_dir = Path(__file__).resolve().parent
    price_path = lab_dir / "sample_prices.csv"
    weights = {
        "STOCK_A": 0.60,
        "BOND_B": 0.40,
    }
    current_quantities = {
        "STOCK_A": 8.0,
        "BOND_B": 12.0,
    }

    prices = load_price_history(price_path)
    asset_returns = calculate_returns(prices)
    portfolio_returns = calculate_portfolio_returns(asset_returns, weights)
    metrics = calculate_portfolio_metrics(portfolio_returns)
    correlation_matrix = calculate_correlation_matrix(asset_returns)
    annualized_covariance = calculate_covariance_matrix(asset_returns, annualize=True)
    covariance_volatility = calculate_portfolio_volatility_from_covariance(
        annualized_covariance,
        weights,
    )
    rebalance_trades = calculate_rebalance_trades(
        prices.iloc[-1],
        current_quantities,
        weights,
    )

    print("Price History")
    print(prices.to_string())

    print("\nAsset Returns")
    print(asset_returns.to_string())

    print("\nPortfolio Returns")
    print(portfolio_returns.to_string())

    print("\nCorrelation Matrix")
    print(correlation_matrix.to_string())

    print("\nAnnualized Covariance Matrix")
    print(annualized_covariance.to_string())

    print("\nPortfolio Metrics")
    print(f"- Cumulative return: {format_percent(metrics.cumulative_return)}")
    print(f"- Annualized volatility: {format_percent(metrics.annualized_volatility)}")
    print(f"- Covariance volatility: {format_percent(covariance_volatility)}")
    print(f"- Max drawdown: {format_percent(metrics.max_drawdown)}")

    print("\nRebalance Trades")
    for trade in rebalance_trades:
        print(
            f"- {trade.asset}: "
            f"current_weight={format_percent(trade.current_weight)}, "
            f"target_weight={format_percent(trade.target_weight)}, "
            f"trade_value={trade.trade_value:.2f}, "
            f"trade_quantity={trade.trade_quantity:.4f}"
        )

    report_path = generate_portfolio_report(
        lab_dir / "reports",
        asset_returns=asset_returns,
        portfolio_returns=portfolio_returns,
        metrics=metrics,
        correlation_matrix=correlation_matrix,
        annualized_covariance=annualized_covariance,
        rebalance_trades=rebalance_trades,
    )
    print(f"\nHTML report: {report_path}")
    print(f"CSV exports: {report_path.parent}")


if __name__ == "__main__":
    main()
