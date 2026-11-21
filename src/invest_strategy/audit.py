"""Independent ledger reconciliation, usable on synthetic and real account runs."""

import numpy as np
import pandas as pd


def audit_account(result, market, tolerance=0.01):
    daily, trades, config = result.daily, result.trades, result.config
    dates = daily.index
    cash_expected = (
        config.cash
        + daily.external.cumsum()
        - trades.groupby("date").debit.sum().reindex(dates, fill_value=0).cumsum()
    )
    errors = {"cash": float((daily.cash - cash_expected).abs().max())}
    marks = market.loc[: dates[-1], list(config.weights)].ffill().reindex(dates)
    invested_value = pd.Series(0.0, index=dates)
    for asset in config.weights:
        purchases = (
            trades[trades.asset == asset]
            .groupby("date")
            .units.sum()
            .reindex(dates, fill_value=0)
            .cumsum()
        )
        expected = config.holdings.get(asset, 0) + purchases
        errors["units_" + asset] = float(
            (daily["units_" + asset] - expected).abs().max()
        )
        invested_value += expected * marks[asset]
    errors["market_value"] = float(
        (daily.total - (cash_expected + config.bonds + invested_value)).abs().max()
    )
    stock = (
        trades[trades.kind != "new"]
        .groupby("date")
        .debit.sum()
        .reindex(dates, fill_value=0)
        .cumsum()
    )
    errors["stock_spent"] = float((daily.stock_spent - stock).abs().max())
    errors["summary_final"] = abs(result.metrics["final_total"] - daily.total.iloc[-1])
    errors["summary_profit"] = abs(
        result.metrics["net_profit"]
        - (daily.total.iloc[-1] - config.initial_total - daily.external.sum())
    )
    safe = (
        daily.reserve_balance
        >= min(config.cash + config.bonds, config.reserve) - tolerance
    )
    checks = {k: bool(np.isfinite(v) and v <= tolerance) for k, v in errors.items()}
    checks["nonnegative_cash"] = bool((daily.cash >= -tolerance).all())
    checks["reserve"] = bool(safe.all())
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "maximum_absolute_errors": errors,
    }
