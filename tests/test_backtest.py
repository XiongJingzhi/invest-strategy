import pandas as pd

from invest_strategy.backtest import run_backtest
from invest_strategy.profiles import get_default_profiles


def monthly_prices(values):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-31", periods=len(values), freq="ME"),
            "close": values,
        }
    )


def daily_prices(start, values):
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(values), freq="D"),
            "close": values,
        }
    )


def test_backtest_tracks_shares_invested_and_value():
    profile = get_default_profiles()["sp500"]
    result = run_backtest(monthly_prices([100.0, 100.0]), profile, monthly_contribution=1000)

    assert result.summary.total_invested == 2000
    assert result.summary.final_value == 2000
    assert result.monthly.iloc[-1]["shares"] == 20


def test_backtest_applies_drawdown_multiplier():
    profile = get_default_profiles()["sp500"]
    result = run_backtest(monthly_prices([100.0, 120.0, 90.0]), profile, monthly_contribution=1000)

    assert result.monthly.iloc[-1]["multiplier"] == 2.0
    assert result.monthly.iloc[-1]["contribution"] == 2000
    assert result.summary.total_invested == 4000


def test_backtest_resamples_short_daily_history_to_monthly_operations():
    profile = get_default_profiles()["sp500"]
    prices = daily_prices("2024-01-15", [100.0] * 31)

    result = run_backtest(prices, profile, monthly_contribution=1000)

    assert len(result.monthly) == 2
    assert result.monthly["date"].dt.strftime("%Y-%m").tolist() == ["2024-01", "2024-02"]
