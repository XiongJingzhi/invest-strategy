from __future__ import annotations

from collections.abc import Sequence
from datetime import date
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf


_CHINA_FUND_INDEX_VALUATION_CODES = {
    "515100": "930955",
}


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


def _is_china_exchange_symbol(symbol: str) -> bool:
    return symbol.endswith(".SS") or symbol.endswith(".SZ") or symbol.endswith(".BJ")


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


def download_dividend_percentiles(
    ticker: str,
    start: date | str,
    end: date | str | None = None,
) -> pd.DataFrame:
    symbol = ticker.strip().upper()
    fund_code = symbol.replace(".SS", "").replace(".SZ", "").replace(".BJ", "")
    index_code = _china_index_valuation_code(symbol)
    if index_code:
        index_valuation = _china_index_valuation_percentiles(index_code, fund_code, start, end)
        if not index_valuation.empty:
            return index_valuation

    if _is_plain_china_fund_code(symbol) or _is_china_exchange_symbol(symbol):
        return _china_fund_dividend_percentiles(fund_code, start, end)

    try:
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        dividends = t.dividends
        if dividends.empty:
            return pd.DataFrame(columns=["date", "dividend_yield", "dividend_percentile"])

        dividends = dividends.reset_index()
        dividends.columns = ["date", "dividend"]
        dividends["date"] = (
            pd.to_datetime(dividends["date"])
            .dt.tz_localize(None)
            .dt.normalize()
        )

        prices = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
        if isinstance(prices.columns, pd.MultiIndex):
            prices.columns = prices.columns.get_level_values(0)
        prices = prices.reset_index()
        prices["date"] = pd.to_datetime(prices["Date"]).dt.tz_localize(None).dt.normalize()
        prices = prices[["date", "Close"]].rename(columns={"Close": "close"})
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["close"]).sort_values("date")

        if prices.empty:
            return pd.DataFrame(columns=["date", "dividend_yield", "dividend_percentile"])

        merged = prices.merge(dividends, on="date", how="left")
        merged["dividend"] = merged["dividend"].fillna(0)

        monthly = merged.set_index("date").resample("ME").agg(
            close=("close", "last"),
            dividend=("dividend", "sum"),
        ).reset_index()

        result = _compute_percentile_from_monthly(monthly)
        return result  # Current trailing PE is not historical point-in-time information.
    except Exception:
        return pd.DataFrame(columns=["date", "dividend_yield", "dividend_percentile"])


def _compute_percentile_from_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    monthly["rolling_dividends"] = monthly["dividend"].rolling(window=12, min_periods=1).sum()
    monthly["dividend_yield"] = (monthly["rolling_dividends"] / monthly["close"] * 100).round(4)
    monthly["dividend_percentile"] = (
        monthly["dividend_yield"]
        .rolling(window=60, min_periods=12)
        .apply(lambda x: _percentile_rank(x.iloc[-1], x), raw=False)
        .round(1)
    )

    result = monthly[["date", "dividend_yield", "dividend_percentile"]].copy()
    return result.dropna(subset=["dividend_percentile"]).reset_index(drop=True)


def _add_current_pe_valuation(valuation: pd.DataFrame, ticker: object) -> pd.DataFrame:
    if valuation.empty:
        return valuation

    # Retained for API compatibility. A current quote must never populate history.
    return valuation.copy()


def _current_trailing_pe(ticker: object) -> float | None:
    try:
        info = getattr(ticker, "info", {}) or {}
        pe = info.get("trailingPE")
    except Exception:
        return None

    if pe is None or pd.isna(pe):
        return None
    return round(float(pe), 4)


def _china_index_valuation_code(symbol: str) -> str | None:
    fund_code = symbol.replace(".SS", "").replace(".SZ", "").replace(".BJ", "")
    return _CHINA_FUND_INDEX_VALUATION_CODES.get(fund_code)


def _china_index_valuation_percentiles(
    index_code: str,
    fund_code: str,
    start: date | str,
    end: date | str | None,
) -> pd.DataFrame:
    columns = ["date", "dividend_yield", "dividend_percentile", "pe", "pe_percentile"]
    try:
        import akshare as ak

        start_dt = pd.to_datetime(_format_date(start))
        end_dt = pd.to_datetime(_format_date(end)) if end else None
        history = (getattr(ak, "stock_zh_index_hist_csindex", None) or ak.index_hist_csindex)(
            symbol=index_code,
            start_date=start_dt.strftime("%Y%m%d"),
            end_date=(
                end_dt.strftime("%Y%m%d")
                if end_dt is not None
                else date.today().strftime("%Y%m%d")
            ),
        )
        if history.empty or not {"日期", "滚动市盈率"}.issubset(history.columns):
            return pd.DataFrame(columns=columns)

        pe_history = history.rename(columns={"日期": "date", "滚动市盈率": "pe"})[
            ["date", "pe"]
        ]
        pe_history["date"] = pd.to_datetime(pe_history["date"])
        pe_history["pe"] = pd.to_numeric(pe_history["pe"], errors="coerce")
        pe_history = pe_history.dropna(subset=["pe"]).sort_values("date")

        monthly = pe_history.set_index("date").resample("ME").agg(
            pe=("pe", "last"),
        ).reset_index()
        monthly = monthly.dropna(subset=["pe"])
        if len(monthly) < 12:
            return pd.DataFrame(columns=columns)

        monthly["pe_percentile"] = (
            monthly["pe"]
            .rolling(window=60, min_periods=1)
            .apply(lambda x: _percentile_rank(x.iloc[-1], x), raw=False)
            .round(1)
        )
        monthly["pe"] = monthly["pe"].round(4)

        fallback_dividend = _china_fund_dividend_percentiles(fund_code, start, end)
        if fallback_dividend.empty:
            result = monthly.copy()
            result["dividend_yield"] = pd.NA
            result["dividend_percentile"] = pd.NA
        else:
            result = monthly.merge(fallback_dividend, on="date", how="left")

        recent_dividend = _china_index_recent_dividend_yield(ak, index_code, start_dt, end_dt)
        if not recent_dividend.empty:
            # Recent CSI dividend yield is a display override. Keep dividend_percentile
            # from fallback_dividend so filled display values never enter percentile ranks.
            result = result.merge(
                recent_dividend,
                on="date",
                how="left",
                suffixes=("", "_recent"),
            )
            result["dividend_yield"] = result["dividend_yield_recent"].combine_first(
                result["dividend_yield"]
            )
            result = result.drop(columns=["dividend_yield_recent"])

        result["dividend_yield"] = result["dividend_yield"].fillna(0.0)
        result["dividend_percentile"] = result["dividend_percentile"].fillna(0.0)
        result = result[columns].copy()
        return result.dropna(subset=["pe_percentile"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=columns)


def _china_index_recent_dividend_yield(
    ak: object,
    index_code: str,
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp | None,
) -> pd.DataFrame:
    raw = (getattr(ak, "stock_zh_index_value_csindex", None) or ak.index_value_csindex)(symbol=index_code)
    if raw.empty or not {"日期", "股息率1"}.issubset(raw.columns):
        return pd.DataFrame(columns=["date", "dividend_yield"])

    dividend = raw.rename(columns={"日期": "date", "股息率1": "dividend_yield"})[
        ["date", "dividend_yield"]
    ]
    dividend["date"] = pd.to_datetime(dividend["date"])
    dividend["dividend_yield"] = pd.to_numeric(dividend["dividend_yield"], errors="coerce")
    dividend = dividend.dropna(subset=["dividend_yield"]).sort_values("date")
    dividend = dividend[dividend["date"] >= start_dt]
    if end_dt is not None:
        dividend = dividend[dividend["date"] <= end_dt]
    if dividend.empty:
        return pd.DataFrame(columns=["date", "dividend_yield"])

    monthly = dividend.set_index("date").resample("ME").agg(
        dividend_yield=("dividend_yield", "last")
    ).reset_index()
    monthly["dividend_yield"] = monthly["dividend_yield"].round(4)
    return monthly.dropna(subset=["dividend_yield"])


def _china_fund_dividend_percentiles(
    fund_code: str,
    start: date | str,
    end: date | str | None,
) -> pd.DataFrame:
    try:
        import akshare as ak

        nav = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        cum = ak.fund_open_fund_info_em(symbol=fund_code, indicator="累计净值走势")

        nav["date"] = pd.to_datetime(nav["净值日期"])
        cum["date"] = pd.to_datetime(cum["净值日期"])

        merged = nav[["date", "单位净值"]].merge(cum[["date", "累计净值"]], on="date")
        merged = merged.sort_values("date").reset_index(drop=True)

        start_dt = pd.to_datetime(_format_date(start))
        end_dt = pd.to_datetime(_format_date(end)) if end else None
        merged = merged[merged["date"] >= start_dt]
        if end_dt:
            merged = merged[merged["date"] <= end_dt]

        if len(merged) < 12:
            return pd.DataFrame(columns=["date", "dividend_yield", "dividend_percentile"])

        merged["diff"] = merged["累计净值"] - merged["单位净值"]
        merged["dividend"] = merged["diff"].diff()
        merged.loc[merged["dividend"] < 0, "dividend"] = 0
        merged["close"] = merged["单位净值"]

        weekly = merged.set_index("date").resample("W").agg(
            close=("close", "last"),
            dividend=("dividend", "sum"),
        ).reset_index()
        weekly = weekly.dropna(subset=["close"])

        monthly = weekly.set_index("date").resample("ME").agg(
            close=("close", "last"),
            dividend=("dividend", "sum"),
        ).reset_index()
        monthly = monthly.dropna(subset=["close"])

        if len(monthly) < 12:
            return pd.DataFrame(columns=["date", "dividend_yield", "dividend_percentile"])

        return _compute_percentile_from_monthly(monthly)
    except Exception:
        return pd.DataFrame(columns=["date", "dividend_yield", "dividend_percentile"])


def _percentile_rank(current: float, series: pd.Series) -> float:
    if len(series) < 2:
        return 50.0
    return float((series < current).sum() / (len(series) - 1) * 100)
