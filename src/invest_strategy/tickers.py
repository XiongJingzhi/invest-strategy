from __future__ import annotations

from dataclasses import dataclass


CUSTOM_TICKER_LABEL = "自定义"


@dataclass(frozen=True)
class TickerSuggestion:
    symbol: str
    name: str

    @property
    def label(self) -> str:
        return f"{self.symbol} - {self.name}"


def get_suggested_tickers() -> tuple[TickerSuggestion, ...]:
    return (
        TickerSuggestion("SPY", "标普500 ETF"),
        TickerSuggestion("VOO", "标普500 ETF"),
        TickerSuggestion("IVV", "标普500 ETF"),
        TickerSuggestion("QQQ", "纳指100 ETF"),
        TickerSuggestion("QQQM", "纳指100 ETF"),
        TickerSuggestion("DIA", "道琼斯工业 ETF"),
        TickerSuggestion("IWM", "罗素2000 ETF"),
        TickerSuggestion("VT", "全球股票 ETF"),
        TickerSuggestion("VTI", "美国全市场 ETF"),
        TickerSuggestion("510300.SS", "沪深300 ETF"),
        TickerSuggestion("510500.SS", "中证500 ETF"),
        TickerSuggestion("159915.SZ", "创业板 ETF"),
        TickerSuggestion("515100.SS", "A股红利低波ETF"),
        TickerSuggestion("512890.SS", "红利低波 ETF"),
    )


def resolve_ticker_choice(
    selected_label: str,
    custom_ticker: str,
    suggestions: tuple[TickerSuggestion, ...],
) -> str:
    if selected_label == CUSTOM_TICKER_LABEL:
        return custom_ticker.strip().upper()

    for suggestion in suggestions:
        if suggestion.label == selected_label:
            return suggestion.symbol
    return custom_ticker.strip().upper()
