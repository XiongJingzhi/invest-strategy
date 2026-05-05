import pandas as pd

from invest_strategy.models import ValuationInput
from invest_strategy.profiles import get_default_profiles
from invest_strategy.strategies import evaluate_strategy


def price_frame(values):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(values), freq="D"),
            "close": values,
        }
    )


def test_low_vol_dividend_uses_ma120_deviation_for_buy_multiplier():
    profile = get_default_profiles()["low_vol_dividend"]
    prices = price_frame([100.0] * 130 + [78.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.ma_deviation_pct <= -20
    assert signal.multiplier == 3.0
    assert signal.action == "大额加仓"


def test_sp500_drawdown_controls_multiplier_without_sell_signal():
    profile = get_default_profiles()["sp500"]
    prices = price_frame([100.0, 120.0, 90.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.drawdown_pct == -25.0
    assert signal.multiplier == 2.0
    assert signal.action == "加倍定投"


def test_nasdaq_ma250_above_30_percent_suggests_partial_elastic_sell():
    profile = get_default_profiles()["nasdaq100"]
    prices = price_frame([100.0] * 260 + [132.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.ma_deviation_pct >= 30
    assert signal.action == "减部分弹性仓"
    assert signal.allow_elastic_buy is False


def test_nasdaq_normal_state_uses_smaller_fixed_layer_weight():
    profile = get_default_profiles()["nasdaq100"]
    prices = price_frame([100.0, 101.0, 102.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.action == "正常定投"
    assert signal.multiplier == 0.6
