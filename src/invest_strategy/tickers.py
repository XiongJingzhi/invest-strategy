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
        TickerSuggestion("DIA", "道琼斯工业 ETF", inception_date=date(1998, 1, 14)),
        TickerSuggestion("IWM", "罗素2000 ETF", inception_date=date(2000, 5, 22)),
        TickerSuggestion("VT", "全球股票 ETF", inception_date=date(2008, 6, 24)),
        TickerSuggestion("VTI", "美国全市场 ETF", inception_date=date(2001, 5, 24)),
        TickerSuggestion("510300.SS", "沪深300 ETF", inception_date=date(2012, 5, 4)),
        TickerSuggestion("510500.SS", "中证500 ETF", inception_date=date(2013, 2, 6)),
        TickerSuggestion("159915.SZ", "创业板 ETF", inception_date=date(2011, 9, 20)),
        TickerSuggestion("510880.SS", "上证红利 ETF", inception_date=date(2006, 11, 17)),
        TickerSuggestion(
            "090010",
            "中证红利基金",
            inception_date=date(2010, 2, 2),
            download_symbols=("090010", "090010.SS", "090010.SZ"),
        ),
        TickerSuggestion("501305.SS", "港股红利", inception_date=date(2017, 11, 24)),
        TickerSuggestion("515100.SS", "A股红利低波ETF", inception_date=date(2020, 5, 22)),
        TickerSuggestion("512890.SS", "红利低波 ETF", inception_date=date(2018, 12, 1)),
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
