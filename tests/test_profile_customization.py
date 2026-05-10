from invest_strategy.models import DrawdownRule, MaRule
from invest_strategy.profiles import (
    get_default_profiles,
    get_profile_strategy_rows,
    with_profile_settings,
)


def test_profile_strategy_rows_explain_drawdown_and_ma_rules():
    profiles = get_default_profiles()

    low_vol_rows = get_profile_strategy_rows(profiles["cashflow_defense"])
    sp500_rows = get_profile_strategy_rows(profiles["core_dca"])

    assert any(row["策略"] == "均线偏离" for row in low_vol_rows)
    assert any(row["策略"] == "回撤加仓" for row in sp500_rows)


def test_profile_settings_can_override_user_adjustable_rules():
    profile = get_default_profiles()["growth_aggressive"]

    customized = with_profile_settings(
        profile,
        trend_ma_days=300,
        fixed_layer_weight=0.5,
        drawdown_rules=(DrawdownRule(-25, 2.5, "用户加仓"),),
        ma_rules=(MaRule(25, 0.0, "用户止盈", allow_elastic_buy=False),),
    )

    assert customized.trend_ma_days == 300
    assert customized.fixed_layer_weight == 0.5
    assert customized.drawdown_rules[0].threshold_pct == -25
    assert customized.ma_rules[0].action == "用户止盈"
