from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path

import pandas as pd


TRADING_DAYS_PER_YEAR = 252
WEIGHT_TOLERANCE = 0.000001


class PortfolioAnalysisError(ValueError):
    """Base error for invalid portfolio analysis operations."""


@dataclass(frozen=True)
class PortfolioMetrics:
    cumulative_return: float
    annualized_volatility: float
    max_drawdown: float


@dataclass(frozen=True)
class RebalanceTrade:
    asset: str
    price: float
    current_quantity: float
    current_value: float
    current_weight: float
    target_weight: float
    target_value: float
    trade_value: float
    trade_quantity: float


def load_price_history(csv_path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, parse_dates=["date"])
    required_columns = {"date", "asset", "close"}
    missing_columns = required_columns - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise PortfolioAnalysisError(f"Price CSV missing required columns: {missing}")

    if frame.empty:
        raise PortfolioAnalysisError("Price CSV must contain at least one row")

    if (frame["close"] <= 0).any():
        raise PortfolioAnalysisError("Close prices must be positive")

    prices = (
        frame.pivot(index="date", columns="asset", values="close")
        .sort_index()
        .astype(float)
    )
    if prices.isna().any().any():
        raise PortfolioAnalysisError("Price history has missing asset/date values")

    return prices


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    if len(prices.index) < 2:
        raise PortfolioAnalysisError("At least two price rows are required")

    return prices.pct_change(fill_method=None).dropna()


def calculate_portfolio_returns(
    asset_returns: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    normalized_weights = _validate_weights(asset_returns.columns, weights)
    weight_series = pd.Series(normalized_weights)
    return asset_returns.mul(weight_series, axis=1).sum(axis=1).rename("portfolio_return")


def calculate_portfolio_metrics(portfolio_returns: pd.Series) -> PortfolioMetrics:
    if portfolio_returns.empty:
        raise PortfolioAnalysisError("Portfolio returns are required")

    growth = (1.0 + portfolio_returns).cumprod()
    running_peak = growth.cummax()
    drawdowns = growth / running_peak - 1.0

    return PortfolioMetrics(
        cumulative_return=float(growth.iloc[-1] - 1.0),
        annualized_volatility=float(portfolio_returns.std(ddof=1) * sqrt(TRADING_DAYS_PER_YEAR)),
        max_drawdown=float(drawdowns.min()),
    )


def calculate_correlation_matrix(asset_returns: pd.DataFrame) -> pd.DataFrame:
    if asset_returns.empty:
        raise PortfolioAnalysisError("Asset returns are required")
    return asset_returns.corr()


def calculate_covariance_matrix(
    asset_returns: pd.DataFrame,
    *,
    annualize: bool = False,
) -> pd.DataFrame:
    if asset_returns.empty:
        raise PortfolioAnalysisError("Asset returns are required")

    covariance = asset_returns.cov()
    if annualize:
        return covariance * TRADING_DAYS_PER_YEAR
    return covariance


def calculate_portfolio_volatility_from_covariance(
    covariance_matrix: pd.DataFrame,
    weights: dict[str, float],
) -> float:
    if covariance_matrix.empty:
        raise PortfolioAnalysisError("Covariance matrix is required")

    normalized_weights = _validate_weights(covariance_matrix.columns, weights)
    weight_series = pd.Series(normalized_weights)
    ordered_covariance = covariance_matrix.loc[weight_series.index, weight_series.index]
    variance = float(weight_series.T @ ordered_covariance @ weight_series)
    return sqrt(variance)


def calculate_rebalance_trades(
    latest_prices: pd.Series,
    current_quantities: dict[str, float],
    target_weights: dict[str, float],
) -> tuple[RebalanceTrade, ...]:
    normalized_weights = _validate_weights(latest_prices.index, target_weights)
    price_assets = set(latest_prices.index)
    quantity_assets = set(current_quantities)
    missing_quantities = price_assets - quantity_assets
    extra_quantities = quantity_assets - price_assets

    if missing_quantities:
        missing = ", ".join(sorted(missing_quantities))
        raise PortfolioAnalysisError(f"Missing current quantities: {missing}")

    if extra_quantities:
        extra = ", ".join(sorted(extra_quantities))
        raise PortfolioAnalysisError(f"Unknown quantity assets: {extra}")

    for asset, quantity in current_quantities.items():
        if quantity < 0:
            raise PortfolioAnalysisError(f"Current quantity cannot be negative: {asset}")

    if (latest_prices <= 0).any():
        raise PortfolioAnalysisError("Latest prices must be positive")

    current_values = pd.Series(
        {
            asset: float(latest_prices[asset]) * current_quantities[asset]
            for asset in latest_prices.index
        }
    )
    total_value = float(current_values.sum())
    if total_value <= 0:
        raise PortfolioAnalysisError("Current portfolio value must be positive")

    trades = []
    for asset in sorted(latest_prices.index):
        price = float(latest_prices[asset])
        current_value = float(current_values[asset])
        target_weight = normalized_weights[asset]
        target_value = total_value * target_weight
        trade_value = target_value - current_value
        trades.append(
            RebalanceTrade(
                asset=asset,
                price=price,
                current_quantity=current_quantities[asset],
                current_value=current_value,
                current_weight=current_value / total_value,
                target_weight=target_weight,
                target_value=target_value,
                trade_value=trade_value,
                trade_quantity=trade_value / price,
            )
        )

    return tuple(trades)


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _validate_weights(
    asset_names,
    weights: dict[str, float],
) -> dict[str, float]:
    assets = set(asset_names)
    weight_assets = set(weights)
    missing_assets = assets - weight_assets
    extra_assets = weight_assets - assets

    if missing_assets:
        missing = ", ".join(sorted(missing_assets))
        raise PortfolioAnalysisError(f"Missing portfolio weights: {missing}")

    if extra_assets:
        extra = ", ".join(sorted(extra_assets))
        raise PortfolioAnalysisError(f"Unknown portfolio weight assets: {extra}")

    for asset, weight in weights.items():
        if weight < 0:
            raise PortfolioAnalysisError(f"Portfolio weight cannot be negative: {asset}")

    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > WEIGHT_TOLERANCE:
        raise PortfolioAnalysisError("Portfolio weights must sum to 1.0")

    return dict(weights)
