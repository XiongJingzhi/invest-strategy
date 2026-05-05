from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf


def download_prices(ticker: str, start: date | str, end: date | str | None = None) -> pd.DataFrame:
    symbol = ticker.strip()
    if not symbol:
        raise ValueError("ticker cannot be empty")

    raw = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError(f"未能下载到 {symbol} 的行情数据")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    close_column = "Close" if "Close" in raw.columns else "Adj Close"
    if close_column not in raw.columns:
        raise ValueError("行情数据缺少收盘价列")

    frame = raw.reset_index()[["Date", close_column]].rename(
        columns={"Date": "date", close_column: "close"}
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["close"])
