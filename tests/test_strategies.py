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
    profile = get_default_profiles()["cashflow_defense"]
    prices = price_frame([100.0] * 130 + [78.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.ma_deviation_pct <= -20
    assert signal.multiplier == 3.0
    assert signal.action == "大额加仓"


def test_sp500_drawdown_controls_multiplier_without_sell_signal():
    profile = get_default_profiles()["core_dca"]
    prices = price_frame([100.0, 120.0, 90.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.drawdown_pct == -25.0
    assert signal.multiplier == 2.0
    assert signal.action == "加倍定投"


def test_nasdaq_ma250_above_30_percent_suggests_partial_elastic_sell():
    profile = get_default_profiles()["growth_aggressive"]
    prices = price_frame([100.0] * 260 + [132.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.ma_deviation_pct >= 30
    assert signal.action == "减部分弹性仓"
    assert signal.allow_elastic_buy is False


def test_nasdaq_ma250_above_20_percent_stops_elastic_buying_at_fixed_layer():
    profile = get_default_profiles()["growth_aggressive"]
    prices = price_frame([100.0] * 260 + [124.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.ma_deviation_pct >= 20
    assert signal.action == "停止弹性买入"
    assert signal.allow_elastic_buy is False
    assert signal.multiplier == 0.6


def test_nasdaq_normal_state_uses_smaller_fixed_layer_weight():
    profile = get_default_profiles()["growth_aggressive"]
    prices = price_frame([100.0, 101.0, 102.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.action == "正常定投"
    assert signal.multiplier == 0.6


def test_fixed_never_stop_small_drawdown_strategy_uses_fine_grained_drawdown_rules():
    profile = get_default_profiles()["fixed_never_stop_small_dd"]
    prices = price_frame([100.0, 92.5])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.drawdown_pct == -7.5
    assert signal.action == "回撤 -7.5% 加仓"
    assert signal.multiplier == 1.5


def test_fixed_never_stop_small_drawdown_strategy_keeps_fixed_layer_above_ma250():
    profile = get_default_profiles()["fixed_never_stop_small_dd"]
    prices = price_frame([100.0] * 260 + [132.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.ma_deviation_pct >= 30
    assert signal.action == "暂停弹性层，固定层继续"
    assert signal.allow_elastic_buy is False
    assert signal.multiplier == 1.0


def test_steady_dca_uses_valuation_when_provided():
    profile = get_default_profiles()["steady_dca"]
    prices = price_frame([100.0, 101.0, 102.0])
    valuation = ValuationInput(pb_percentile=95.0, pe_percentile=92.0)

    signal = evaluate_strategy(prices, profile, valuation)

    assert signal.valuation_score is not None
    assert signal.valuation_score >= 90
    assert signal.allow_elastic_buy is False
    assert any("估值分位偏高" in r for r in signal.reasons)


def test_steady_dca_ignores_empty_valuation():
    profile = get_default_profiles()["steady_dca"]
    prices = price_frame([100.0, 101.0, 102.0])

    signal = evaluate_strategy(prices, profile, ValuationInput())

    assert signal.valuation_score is None
    assert signal.allow_elastic_buy is True


def test_core_dca_valuation_component_not_duplicated():
    profile = get_default_profiles()["core_dca"]
    prices = price_frame([100.0, 101.0, 102.0])
    valuation = ValuationInput(pb_percentile=95.0)

    signal = evaluate_strategy(prices, profile, valuation)

    assert signal.valuation_score is not None
    valuation_reasons = [r for r in signal.reasons if "估值" in r]
    assert len(valuation_reasons) == 1


def test_pure_dca_uses_valuation_when_provided():
    profile = get_default_profiles()["pure_dca"]
    prices = price_frame([100.0, 101.0, 102.0])
    valuation = ValuationInput(pe_percentile=95.0)

    signal = evaluate_strategy(prices, profile, valuation)

    assert signal.valuation_score is not None
    assert signal.allow_elastic_buy is False
