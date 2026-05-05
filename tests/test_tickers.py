from datetime import date

from invest_strategy.tickers import TickerSuggestion, get_suggested_tickers, resolve_ticker_choice


def test_suggested_tickers_include_core_assets():
    suggestions = get_suggested_tickers()
    labels = [item.label for item in suggestions]
    symbols = [item.symbol for item in suggestions]

    assert "SPY - 标普500 ETF" in labels
    assert "QQQ - 纳指100 ETF" in labels
    assert "515100.SS - A股红利低波ETF" in labels
    assert "VOO" not in symbols
    assert "IVV" not in symbols
    assert "QQQM" not in symbols


def test_suggested_tickers_include_dividend_funds():
    suggestions = get_suggested_tickers()
    symbols = [item.symbol for item in suggestions]
    assert "510880.SS" in symbols
    assert "090010" in symbols
    assert "501305.SS" in symbols


def test_fund_ticker_can_define_download_fallbacks():
    suggestions = get_suggested_tickers()
    fund = next(item for item in suggestions if item.symbol == "090010")

    assert fund.download_symbols == ("090010", "090010.SS", "090010.SZ")


def test_min_backtest_start_skips_first_month():
    ticker = TickerSuggestion("512890.SS", "红利低波 ETF", inception_date=date(2018, 12, 1))
    assert ticker.min_backtest_start() == date(2019, 2, 1)


def test_min_backtest_start_returns_none_without_inception():
    ticker = TickerSuggestion("SPY", "标普500 ETF")
    assert ticker.min_backtest_start() is None


def test_resolve_ticker_choice_supports_custom_input():
    suggestions = get_suggested_tickers()

    assert resolve_ticker_choice("自定义", "VOO", suggestions) == "VOO"
    assert resolve_ticker_choice("SPY - 标普500 ETF", "", suggestions) == "SPY"
