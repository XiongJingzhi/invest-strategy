import pandas as pd

from invest_strategy.compare import compare_profiles
from invest_strategy.profiles import get_default_profiles


def test_compare_profiles_returns_summary_and_equity_curve():
    prices = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-31", periods=3, freq="ME"),
            "close": [100.0, 120.0, 90.0],
        }
    )
    profiles = get_default_profiles()

    comparison = compare_profiles(
        prices,
        [profiles["sp500"], profiles["steady_dca"]],
        monthly_contribution=1000,
    )

    assert comparison.summary["策略组合"].tolist() == ["全球核心定投", "稳健定投"]
    assert "组合说明" not in comparison.summary.columns
    assert "组合规则" in comparison.summary.columns
    assert "投入份额" in comparison.summary.columns
    assert "固定定投" in comparison.summary.loc[0, "组合规则"]
    assert "回撤加仓" in comparison.summary.loc[0, "组合规则"]
    assert comparison.summary.loc[0, "投入份额"] > 0
    assert {"日期", "策略组合", "组合市值"}.issubset(comparison.equity_curve.columns)
    assert len(comparison.equity_curve["策略组合"].unique()) == 2
