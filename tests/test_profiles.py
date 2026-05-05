from invest_strategy.profiles import get_default_profiles


def test_default_profiles_cover_three_asset_roles():
    profiles = get_default_profiles()

    assert {
        "low_vol_dividend",
        "sp500",
        "nasdaq100",
        "steady_dca",
        "aggressive_drawdown",
        "trend_guard",
        "pure_dca",
        "crisis_cash_bucket",
        "dividend_value_plus",
        "ma_rebalance",
        "low_vol_dividend_small_drawdown",
    }.issubset(profiles)
    assert profiles["low_vol_dividend"].display_name == "红利现金流防守"
    assert profiles["sp500"].display_name == "全球核心定投"
    assert profiles["nasdaq100"].display_name == "科技成长进攻"
    assert profiles["steady_dca"].display_name == "稳健定投"
    assert profiles["aggressive_drawdown"].display_name == "进攻回撤"
    assert profiles["trend_guard"].display_name == "趋势风控"
    assert profiles["pure_dca"].display_name == "纯固定定投"
    assert profiles["crisis_cash_bucket"].display_name == "现金桶危机加仓"
    assert profiles["dividend_value_plus"].display_name == "红利估值增强"
    assert profiles["ma_rebalance"].display_name == "均线再平衡"
    assert profiles["low_vol_dividend_small_drawdown"].display_name == "低波红利小回撤增强"


def test_growth_and_core_profiles_do_not_use_ma120_sell_rule():
    profiles = get_default_profiles()

    assert profiles["sp500"].trend_ma_days == 250
    assert profiles["nasdaq100"].trend_ma_days == 250
    assert profiles["sp500"].partial_sell_above_ma_pct is None
    assert profiles["nasdaq100"].partial_sell_above_ma_pct == 30
