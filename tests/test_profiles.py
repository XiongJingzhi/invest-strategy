from invest_strategy.profiles import get_default_profiles


def test_default_profiles_cover_three_asset_roles():
    profiles = get_default_profiles()

    expected_keys = {
        "pure_dca",
        "steady_dca",
        "core_dca",
        "growth_aggressive",
        "drawdown_strike",
        "crisis_bucket",
        "cashflow_defense",
        "valuation_plus",
        "trend_guard",
        "ma_rebalance",
        "low_vol_small_dd",
        "desensitized",
        "simple_practical",
        "deep_value",
        "conservative_balance",
        "ladder_dd",
        "ultra_aggressive",
    }
    assert expected_keys.issubset(profiles)

    assert profiles["pure_dca"].display_name == "纯固定定投"
    assert profiles["steady_dca"].display_name == "稳健定投"
    assert profiles["core_dca"].display_name == "全球核心定投"
    assert profiles["growth_aggressive"].display_name == "成长进攻"
    assert profiles["drawdown_strike"].display_name == "进攻回撤"
    assert profiles["crisis_bucket"].display_name == "现金桶危机加仓"
    assert profiles["cashflow_defense"].display_name == "现金流防守"
    assert profiles["valuation_plus"].display_name == "估值增强"
    assert profiles["trend_guard"].display_name == "趋势风控"
    assert profiles["ma_rebalance"].display_name == "均线再平衡"
    assert profiles["low_vol_small_dd"].display_name == "低波小回撤增强"
    assert profiles["desensitized"].display_name == "降低敏感度版"
    assert profiles["simple_practical"].display_name == "简单实盘版"
    assert profiles["deep_value"].display_name == "深度价值版"
    assert profiles["conservative_balance"].display_name == "保守平衡版"
    assert profiles["ladder_dd"].display_name == "阶梯加仓版"
    assert profiles["ultra_aggressive"].display_name == "极致进攻版"


def test_growth_and_core_profiles_do_not_use_ma120_sell_rule():
    profiles = get_default_profiles()

    assert profiles["core_dca"].trend_ma_days == 250
    assert profiles["growth_aggressive"].trend_ma_days == 250
    assert profiles["core_dca"].partial_sell_above_ma_pct is None
    assert profiles["growth_aggressive"].partial_sell_above_ma_pct == 30
