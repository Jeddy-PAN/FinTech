from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from portfolio_analysis import (
    PortfolioAnalysisError,
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


@pytest.fixture
def price_csv_path() -> Path:
    path = _test_data_directory() / f"{uuid4()}.csv"
    path.write_text(
        "\n".join(
            [
                "date,asset,close",
                "2026-01-02,STOCK_A,100.00",
                "2026-01-02,BOND_B,100.00",
                "2026-01-05,STOCK_A,102.00",
                "2026-01-05,BOND_B,100.50",
                "2026-01-06,STOCK_A,101.00",
                "2026-01-06,BOND_B,100.80",
                "2026-01-07,STOCK_A,104.00",
                "2026-01-07,BOND_B,101.00",
            ]
        ),
        encoding="utf-8",
    )
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


def test_load_price_history_pivots_prices(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)

    assert list(prices.columns) == ["BOND_B", "STOCK_A"]
    assert list(prices.index.strftime("%Y-%m-%d")) == [
        "2026-01-02",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
    ]
    assert prices.loc[pd.Timestamp("2026-01-05"), "STOCK_A"] == 102.00


def test_calculate_returns_uses_fractional_price_change(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)

    returns = calculate_returns(prices)

    assert returns.loc[pd.Timestamp("2026-01-05"), "STOCK_A"] == pytest.approx(0.02)
    assert returns.loc[pd.Timestamp("2026-01-05"), "BOND_B"] == pytest.approx(0.005)
    assert returns.loc[pd.Timestamp("2026-01-06"), "STOCK_A"] == pytest.approx(
        -0.009803921568627416
    )


def test_calculate_portfolio_returns_uses_weights(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)

    portfolio_returns = calculate_portfolio_returns(
        returns,
        {
            "STOCK_A": 0.60,
            "BOND_B": 0.40,
        },
    )

    assert portfolio_returns.loc[pd.Timestamp("2026-01-05")] == pytest.approx(0.014)
    assert portfolio_returns.name == "portfolio_return"


def test_calculate_portfolio_metrics(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)
    portfolio_returns = calculate_portfolio_returns(
        returns,
        {
            "STOCK_A": 0.60,
            "BOND_B": 0.40,
        },
    )

    metrics = calculate_portfolio_metrics(portfolio_returns)

    assert metrics.cumulative_return == pytest.approx(0.028033592403238883)
    assert metrics.annualized_volatility == pytest.approx(0.19588789880585383)
    assert metrics.max_drawdown == pytest.approx(-0.004688323090430213)


def test_calculate_correlation_matrix(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)

    correlation = calculate_correlation_matrix(returns)

    assert list(correlation.columns) == ["BOND_B", "STOCK_A"]
    assert correlation.loc["BOND_B", "BOND_B"] == pytest.approx(1.0)
    assert correlation.loc["STOCK_A", "STOCK_A"] == pytest.approx(1.0)
    assert correlation.loc["BOND_B", "STOCK_A"] == pytest.approx(-0.046137415629889975)
    assert correlation.loc["STOCK_A", "BOND_B"] == pytest.approx(-0.046137415629889975)


def test_calculate_covariance_matrix_can_be_annualized(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)

    daily_covariance = calculate_covariance_matrix(returns)
    annualized_covariance = calculate_covariance_matrix(returns, annualize=True)

    assert daily_covariance.loc["BOND_B", "BOND_B"] == pytest.approx(
        0.000002359551748445799
    )
    assert annualized_covariance.loc["BOND_B", "BOND_B"] == pytest.approx(
        daily_covariance.loc["BOND_B", "BOND_B"] * 252
    )


def test_portfolio_volatility_from_covariance_matches_return_series_volatility(
    price_csv_path,
) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)
    weights = {
        "STOCK_A": 0.60,
        "BOND_B": 0.40,
    }
    portfolio_returns = calculate_portfolio_returns(returns, weights)
    metrics = calculate_portfolio_metrics(portfolio_returns)
    annualized_covariance = calculate_covariance_matrix(returns, annualize=True)

    volatility = calculate_portfolio_volatility_from_covariance(
        annualized_covariance,
        weights,
    )

    assert volatility == pytest.approx(metrics.annualized_volatility)


def test_calculate_rebalance_trades(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    latest_prices = prices.iloc[-1]

    trades = calculate_rebalance_trades(
        latest_prices,
        {
            "STOCK_A": 8.0,
            "BOND_B": 12.0,
        },
        {
            "STOCK_A": 0.60,
            "BOND_B": 0.40,
        },
    )

    assert trades[0].asset == "BOND_B"
    assert trades[0].current_value == pytest.approx(1212.0)
    assert trades[0].current_weight == pytest.approx(0.5929549902152642)
    assert trades[0].target_value == pytest.approx(817.6)
    assert trades[0].trade_value == pytest.approx(-394.4)
    assert trades[0].trade_quantity == pytest.approx(-3.904950495049505)
    assert trades[1].asset == "STOCK_A"
    assert trades[1].trade_value == pytest.approx(394.4)
    assert trades[1].trade_quantity == pytest.approx(3.792307692307692)


def test_rebalance_rejects_missing_quantity(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)

    with pytest.raises(PortfolioAnalysisError, match="Missing current quantities"):
        calculate_rebalance_trades(
            prices.iloc[-1],
            {"STOCK_A": 8.0},
            {
                "STOCK_A": 0.60,
                "BOND_B": 0.40,
            },
        )


def test_generate_portfolio_report_writes_html_and_csv_exports(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    asset_returns = calculate_returns(prices)
    weights = {
        "STOCK_A": 0.60,
        "BOND_B": 0.40,
    }
    portfolio_returns = calculate_portfolio_returns(asset_returns, weights)
    metrics = calculate_portfolio_metrics(portfolio_returns)
    correlation_matrix = calculate_correlation_matrix(asset_returns)
    annualized_covariance = calculate_covariance_matrix(asset_returns, annualize=True)
    rebalance_trades = calculate_rebalance_trades(
        prices.iloc[-1],
        {
            "STOCK_A": 8.0,
            "BOND_B": 12.0,
        },
        weights,
    )
    output_directory = _test_data_directory() / f"report-{uuid4()}"

    report_path = generate_portfolio_report(
        output_directory,
        asset_returns=asset_returns,
        portfolio_returns=portfolio_returns,
        metrics=metrics,
        correlation_matrix=correlation_matrix,
        annualized_covariance=annualized_covariance,
        rebalance_trades=rebalance_trades,
    )

    try:
        assert report_path.exists()
        assert (output_directory / "asset_returns.csv").exists()
        assert (output_directory / "portfolio_returns.csv").exists()
        assert (output_directory / "correlation_matrix.csv").exists()
        assert (output_directory / "annualized_covariance_matrix.csv").exists()
        assert (output_directory / "rebalance_trades.csv").exists()

        report_html = report_path.read_text(encoding="utf-8")
        assert "Portfolio Analysis Report" in report_html
        assert "Portfolio Metrics" in report_html
        assert "Correlation Matrix" in report_html
        assert "Rebalance Trades" in report_html

        rebalance_header = (output_directory / "rebalance_trades.csv").read_text(
            encoding="utf-8"
        ).splitlines()[0]
        assert rebalance_header == (
            "asset,price,current_quantity,current_value,current_weight,"
            "target_weight,target_value,trade_value,trade_quantity"
        )
    finally:
        for path in output_directory.glob("*"):
            path.unlink()
        output_directory.rmdir()


def test_weights_must_sum_to_one(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)

    with pytest.raises(PortfolioAnalysisError, match="Portfolio weights must sum to 1.0"):
        calculate_portfolio_returns(
            returns,
            {
                "STOCK_A": 0.50,
                "BOND_B": 0.40,
            },
        )


def test_missing_weight_is_rejected(price_csv_path) -> None:
    prices = load_price_history(price_csv_path)
    returns = calculate_returns(prices)

    with pytest.raises(PortfolioAnalysisError, match="Missing portfolio weights"):
        calculate_portfolio_returns(returns, {"STOCK_A": 1.00})


def test_negative_price_is_rejected() -> None:
    path = _test_data_directory() / f"{uuid4()}.csv"
    path.write_text(
        "\n".join(
            [
                "date,asset,close",
                "2026-01-02,STOCK_A,-100.00",
            ]
        ),
        encoding="utf-8",
    )

    try:
        with pytest.raises(PortfolioAnalysisError, match="Close prices must be positive"):
            load_price_history(path)
    finally:
        if path.exists():
            path.unlink()


def test_format_percent() -> None:
    assert format_percent(0.12345) == "12.35%"
    assert format_percent(-0.052) == "-5.20%"


def _test_data_directory() -> Path:
    directory = Path(__file__).with_name(".test-data")
    directory.mkdir(exist_ok=True)
    return directory
