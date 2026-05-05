from __future__ import annotations

from collections.abc import Sequence
from datetime import date
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf


def download_prices(
    ticker: str | Sequence[str],
    start: date | str,
    end: date | str | None = None,
) -> pd.DataFrame:
    symbols = _normalize_symbols(ticker)
    if not symbols:
        raise ValueError("ticker cannot be empty")

    failures = []
    for symbol in symbols:
        if _is_plain_china_fund_code(symbol):
            try:
                return _download_china_fund_nav(symbol, start, end)
            except Exception as exc:
                failures.append(f"{symbol}（{exc}）")
                continue

        try:
            raw = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
        except Exception as exc:  # yfinance may raise on unsupported fund symbols.
            failures.append(f"{symbol}（{exc}）")
            continue

        if raw.empty:
            failures.append(symbol)
            continue

        return _normalize_price_frame(raw)

    failed_symbols = "、".join(symbols)
    detail = f"；已尝试：{failed_symbols}"
    if failures and failures != list(symbols):
        detail += f"；失败明细：{'、'.join(failures)}"
    raise ValueError(f"未能下载到行情数据{detail}")


def _normalize_symbols(ticker: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(ticker, str):
        raw_symbols = (ticker,)
    else:
        raw_symbols = tuple(ticker)
    return tuple(symbol.strip().upper() for symbol in raw_symbols if symbol and symbol.strip())


def _is_plain_china_fund_code(symbol: str) -> bool:
    return symbol.isdigit() and len(symbol) == 6


def _download_china_fund_nav(
    symbol: str,
    start: date | str,
    end: date | str | None,
) -> pd.DataFrame:
    start_date = pd.to_datetime(_format_date(start))
    all_records = []
    page_index = 1
    while True:
        payload = _fetch_china_fund_nav_page(symbol, page_index)
        data = payload.get("Data") or {}
        records = data.get("LSJZList", [])
        if not records:
            break

        all_records.extend(records)
        oldest_date = pd.to_datetime(records[-1].get("FSRQ"))
        if oldest_date < start_date:
            break

        total_count = int(payload.get("TotalCount") or 0)
        page_size = int(payload.get("PageSize") or len(records))
        if page_size <= 0 or page_index * page_size >= total_count:
            break
        page_index += 1

    if not all_records:
        raise ValueError("基金净值数据为空")

    frame = pd.DataFrame(all_records)
    if "FSRQ" not in frame.columns or "DWJZ" not in frame.columns:
        raise ValueError("基金净值数据缺少日期或单位净值")

    result = frame.rename(columns={"FSRQ": "date", "DWJZ": "close"})[["date", "close"]]
    result["date"] = pd.to_datetime(result["date"])
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.dropna(subset=["close"]).sort_values("date")
    result = result[result["date"] >= start_date]
    if end is not None:
        end_date = pd.to_datetime(_format_date(end))
        result = result[result["date"] < end_date]
    if result.empty:
        raise ValueError("基金净值数据为空")
    return result.reset_index(drop=True)


def _fetch_china_fund_nav_page(symbol: str, page_index: int) -> dict:
    query = urlencode(
        {
            "fundCode": symbol,
            "pageIndex": page_index,
            "pageSize": 20,
            "startDate": "",
            "endDate": "",
        }
    )
    request = Request(
        f"https://api.fund.eastmoney.com/f10/lsjz?{query}",
        headers={
            "Referer": "https://fundf10.eastmoney.com/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _format_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalize_price_frame(raw: pd.DataFrame) -> pd.DataFrame:
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
