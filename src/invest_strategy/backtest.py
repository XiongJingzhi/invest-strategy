from __future__ import annotations

import pandas as pd

from .models import AssetProfile, BacktestResult, BacktestSummary, ValuationInput
from .strategies import evaluate_strategy


def run_backtest(
    prices: pd.DataFrame,
    profile: AssetProfile,
    monthly_contribution: float,
    valuation: ValuationInput | None = None,
) -> BacktestResult:
    if monthly_contribution <= 0:
        raise ValueError("monthly_contribution must be positive")
    if prices.empty:
        raise ValueError("prices cannot be empty")

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    monthly = _monthly_prices(frame)

    rows: list[dict[str, float | str | pd.Timestamp]] = []
    shares = 0.0
    total_invested = 0.0
    peak_value = 0.0
    max_drawdown_pct = 0.0

    for _, row in monthly.iterrows():
        history = frame[frame["date"] <= row["date"]]
        signal = evaluate_strategy(history, profile, valuation)
        contribution = monthly_contribution * signal.multiplier
        price = float(row["close"])
        bought_shares = contribution / price if price else 0.0
        shares += bought_shares
        total_invested += contribution
        value = shares * price
        peak_value = max(peak_value, value)
        portfolio_drawdown = (value / peak_value - 1) * 100 if peak_value else 0.0
        max_drawdown_pct = min(max_drawdown_pct, portfolio_drawdown)

        rows.append(
            {
                "date": row["date"],
                "close": price,
                "multiplier": signal.multiplier,
                "contribution": contribution,
                "bought_shares": bought_shares,
                "shares": shares,
                "invested": total_invested,
                "value": value,
                "drawdown_pct": signal.drawdown_pct,
                "action": signal.action,
            }
        )

    output = pd.DataFrame(rows)
    final_value = float(output.iloc[-1]["value"])
    total_return_pct = (final_value / total_invested - 1) * 100 if total_invested else 0.0
    annualized_return_pct = _annualized_return_pct(output, final_value, total_invested)
    summary = BacktestSummary(
        total_invested=round(total_invested, 2),
        final_value=round(final_value, 2),
        total_return_pct=round(total_return_pct, 2),
        annualized_return_pct=round(annualized_return_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
    )
    return BacktestResult(monthly=output, summary=summary)


def _monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.set_index("date")
    return frame.resample("ME").last().dropna(subset=["close"]).reset_index()


def _annualized_return_pct(output: pd.DataFrame, final_value: float, total_invested: float) -> float:
    if total_invested <= 0 or len(output) < 2:
        return 0.0

    start = pd.Timestamp(output.iloc[0]["date"])
    end = pd.Timestamp(output.iloc[-1]["date"])
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if months <= 0:
        return 0.0

    years = months / 12
    total_return = final_value / total_invested
    return (total_return ** (1 / years) - 1) * 100
