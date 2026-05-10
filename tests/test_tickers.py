from datetime import date

from invest_strategy.tickers import TickerSuggestion, get_suggested_tickers, resolve_ticker_choice


def test_suggested_tickers_include_core_assets():
    suggestions = get_suggested_tickers()
    labels = [item.label for item in suggestions]
    symbols = [item.symbol for item in suggestions]

    assert "SPY - 标普500 ETF" in labels
    assert "QQQ - 纳指100 ETF" in labels
    assert "515100.SS - 红利低波100ETF" in labels
    assert len(suggestions) == 3


def test_suggested_tickers_include_dividend_fund():
    suggestions = get_suggested_tickers()
    symbols = [item.symbol for item in suggestions]
    assert "515100.SS" in symbols


def test_min_backtest_start_skips_first_month():
    ticker = TickerSuggestion("515100.SS", "红利低波100ETF", inception_date=date(2020, 5, 22))
    assert ticker.min_backtest_start() == date(2020, 7, 1)


def test_min_backtest_start_returns_none_without_inception():
    ticker = TickerSuggestion("SPY", "标普500 ETF")
    assert ticker.min_backtest_start() is None


def test_resolve_ticker_choice_supports_custom_input():
    suggestions = get_suggested_tickers()

    assert resolve_ticker_choice("自定义", "VOO", suggestions) == "VOO"
    assert resolve_ticker_choice("SPY - 标普500 ETF", "", suggestions) == "SPY"
