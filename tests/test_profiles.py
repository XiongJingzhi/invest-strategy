from invest_strategy.profiles import get_default_profiles


def test_default_profiles_cover_three_asset_roles():
    profiles = get_default_profiles()

    assert set(profiles) == {"low_vol_dividend", "sp500", "nasdaq100"}
    assert profiles["low_vol_dividend"].display_name == "低波红利"
    assert profiles["sp500"].display_name == "标普500"
    assert profiles["nasdaq100"].display_name == "纳指100"


def test_growth_and_core_profiles_do_not_use_ma120_sell_rule():
    profiles = get_default_profiles()

    assert profiles["sp500"].trend_ma_days == 250
    assert profiles["nasdaq100"].trend_ma_days == 250
    assert profiles["sp500"].partial_sell_above_ma_pct is None
    assert profiles["nasdaq100"].partial_sell_above_ma_pct == 30
