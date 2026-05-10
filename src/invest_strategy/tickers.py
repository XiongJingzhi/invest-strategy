from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta


CUSTOM_TICKER_LABEL = "自定义"


@dataclass(frozen=True)
class TickerSuggestion:
    symbol: str
    name: str
    inception_date: date | None = None
    download_symbols: tuple[str, ...] | None = None

    @property
    def label(self) -> str:
        return f"{self.symbol} - {self.name}"

    def min_backtest_start(self) -> date | None:
        if self.inception_date is None:
            return None
        inception_month = self.inception_date.replace(day=1)
        return inception_month + relativedelta(months=2)

    def price_symbols(self) -> tuple[str, ...]:
        return self.download_symbols or (self.symbol,)


def get_suggested_tickers() -> tuple[TickerSuggestion, ...]:
    return (
        TickerSuggestion("SPY", "标普500 ETF", inception_date=date(1993, 1, 22)),
        TickerSuggestion("QQQ", "纳指100 ETF", inception_date=date(1999, 3, 10)),
        TickerSuggestion("515100.SS", "红利低波100ETF", inception_date=date(2020, 5, 22)),
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
