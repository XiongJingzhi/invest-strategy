from __future__ import annotations

import math

import pandas as pd

from .models import AssetProfile, BacktestResult, BacktestSummary, ValuationInput
from .strategies import evaluate_strategy


def run_backtest(
    prices: pd.DataFrame,
    profile: AssetProfile,
    monthly_contribution: float,
    valuation_history: pd.DataFrame | None = None,
) -> BacktestResult:
    if monthly_contribution <= 0:
        raise ValueError("monthly_contribution must be positive")
    if prices.empty:
        raise ValueError("prices cannot be empty")

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    monthly = _monthly_prices(frame)

    valuation_lookup = _build_valuation_lookup(valuation_history)

    rows: list[dict[str, float | str | pd.Timestamp]] = []
    shares = 0.0
    total_invested = 0.0
    peak_value = 0.0
    max_drawdown_pct = 0.0

    for _, row in monthly.iterrows():
        history = frame[frame["date"] <= row["date"]]
        month_date = row["date"]
        valuation = _lookup_valuation(valuation_lookup, month_date)
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
                "dividend_yield": signal.dividend_yield,
                "dividend_percentile": signal.dividend_percentile,
                "pe": valuation.pe if valuation else None,
                "pe_percentile": valuation.pe_percentile if valuation else None,
            }
        )

    output = pd.DataFrame(rows)
    final_value = float(output.iloc[-1]["value"])
    total_return_pct = (final_value / total_invested - 1) * 100 if total_invested else 0.0
    annualized_return_pct = _annualized_return_pct(output, final_value, total_invested)
    xirr_pct = _compute_xirr(output, final_value)
    summary = BacktestSummary(
        total_invested=round(total_invested, 2),
        final_value=round(final_value, 2),
        total_return_pct=round(total_return_pct, 2),
        annualized_return_pct=round(annualized_return_pct, 2),
        xirr_pct=round(xirr_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
    )
    return BacktestResult(monthly=output, summary=summary)


def _build_valuation_lookup(
    valuation_history: pd.DataFrame | None,
) -> dict[pd.Timestamp, ValuationInput]:
    if valuation_history is None or valuation_history.empty:
        return {}
    lookup: dict[pd.Timestamp, ValuationInput] = {}
    for _, row in valuation_history.iterrows():
        dt = pd.Timestamp(row["date"])
        dy = float(row["dividend_yield"]) if pd.notna(row.get("dividend_yield")) else None
        dp = float(row["dividend_percentile"]) if pd.notna(row.get("dividend_percentile")) else None
        pe = float(row["pe"]) if pd.notna(row.get("pe")) else None
        pe_percentile = (
            float(row["pe_percentile"]) if pd.notna(row.get("pe_percentile")) else None
        )
        lookup[dt] = ValuationInput(
            dividend_yield=dy,
            dividend_percentile=dp,
            pe=pe,
            pe_percentile=pe_percentile,
        )
    return lookup


def _lookup_valuation(
    lookup: dict[pd.Timestamp, ValuationInput],
    month_date: pd.Timestamp,
) -> ValuationInput | None:
    if not lookup:
        return None
    if month_date in lookup:
        return lookup[month_date]
    best_key = None
    for key in lookup:
        if key <= month_date and (best_key is None or key > best_key):
            best_key = key
    return lookup.get(best_key)


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


def _compute_xirr(output: pd.DataFrame, final_value: float) -> float:
    if len(output) < 2 or final_value <= 0:
        return 0.0

    dates: list[pd.Timestamp] = []
    amounts: list[float] = []

    for _, row in output.iterrows():
        dates.append(pd.Timestamp(row["date"]))
        amounts.append(-float(row["contribution"]))

    dates.append(dates[-1])
    amounts.append(final_value)

    if not amounts or all(a == 0 for a in amounts):
        return 0.0

    rate = _xirrNewton(dates, amounts)
    return (rate - 1) * 100 if rate and math.isfinite(rate) else 0.0


def _xirrNewton(
    dates: list[pd.Timestamp],
    amounts: list[float],
    guess: float = 1.1,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> float | None:
    d0 = dates[0].to_pydatetime()
    year_days = 365.25

    rate = guess
    for _ in range(max_iter):
        npv = 0.0
        d_npv = 0.0
        for dt, amt in zip(dates, amounts):
            year_frac = (dt.to_pydatetime() - d0).days / year_days
            try:
                factor = rate ** year_frac
                npv += amt / factor
                if year_frac != 0:
                    d_npv -= amt * year_frac / (rate ** (year_frac + 1))
            except (OverflowError, ZeroDivisionError):
                return rate
        if d_npv == 0:
            break
        new_rate = rate - npv / d_npv
        if not math.isfinite(new_rate) or new_rate <= 0:
            break
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate
    return rate if rate > 0 else None
