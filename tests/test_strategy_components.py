import pandas as pd

from invest_strategy.models import StrategyComponent
from invest_strategy.profiles import get_default_profiles, get_profile_strategy_rows, with_strategy_components
from invest_strategy.strategies import evaluate_strategy


def price_frame(values):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(values), freq="D"),
            "close": values,
        }
    )


def test_presets_are_built_from_selectable_components():
    profiles = get_default_profiles()

    sp500_components = {component.key for component in profiles["sp500"].strategy_components}
    nasdaq_components = {component.key for component in profiles["nasdaq100"].strategy_components}
    steady_components = {component.key for component in profiles["steady_dca"].strategy_components}
    aggressive_components = {
        component.key for component in profiles["aggressive_drawdown"].strategy_components
    }
    trend_components = {component.key for component in profiles["trend_guard"].strategy_components}

    assert sp500_components == {"fixed_contribution", "drawdown_add", "valuation_guard"}
    assert nasdaq_components == {"fixed_contribution", "drawdown_add", "ma_deviation"}
    assert steady_components == {"fixed_contribution", "drawdown_add"}
    assert aggressive_components == {"fixed_contribution", "drawdown_add", "ma_deviation"}
    assert trend_components == {"fixed_contribution", "ma_deviation", "valuation_guard"}


def test_disabling_drawdown_component_removes_drawdown_add_on():
    profile = get_default_profiles()["sp500"]
    components = tuple(
        component if component.key != "drawdown_add" else component.disabled()
        for component in profile.strategy_components
    )
    profile = with_strategy_components(profile, components)

    signal = evaluate_strategy(price_frame([100.0, 120.0, 90.0]), profile)

    assert signal.drawdown_pct == -25.0
    assert signal.multiplier == 1.0
    assert signal.action == "正常定投"
    assert not any(row["策略"] == "回撤加仓" and row["状态"] == "启用" for row in get_profile_strategy_rows(profile))


def test_component_parameters_can_be_edited():
    profile = get_default_profiles()["nasdaq100"]
    custom_ma = StrategyComponent(
        key="ma_deviation",
        display_name="均线偏离",
        component_type="ma_deviation",
        params={
            "ma_days": 300,
            "rules": [
                {
                    "threshold_pct": 25,
                    "multiplier": 0.0,
                    "action": "用户止买",
                    "allow_elastic_buy": False,
                }
            ],
        },
    )
    profile = with_strategy_components(profile, (custom_ma,))

    signal = evaluate_strategy(price_frame([100.0] * 310 + [130.0]), profile)

    assert signal.ma_deviation_pct >= 25
    assert signal.action == "用户止买"
    assert signal.allow_elastic_buy is False
