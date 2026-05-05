from invest_strategy.tickers import get_suggested_tickers, resolve_ticker_choice


def test_suggested_tickers_include_core_assets():
    suggestions = get_suggested_tickers()
    labels = [item.label for item in suggestions]

    assert "SPY - 标普500 ETF" in labels
    assert "QQQ - 纳指100 ETF" in labels
    assert "515100.SS - A股红利低波ETF" in labels


def test_resolve_ticker_choice_supports_custom_input():
    suggestions = get_suggested_tickers()

    assert resolve_ticker_choice("自定义", "VOO", suggestions) == "VOO"
    assert resolve_ticker_choice("SPY - 标普500 ETF", "", suggestions) == "SPY"
