from datetime import date

import pandas as pd
import pytest

from invest_strategy.data import download_dividend_percentiles, download_prices


def test_download_prices_tries_candidate_symbols(monkeypatch):
    calls = []

    def fake_download(symbol, start, end, auto_adjust, progress):
        calls.append(symbol)
        if symbol == "090010.SS":
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
                "Close": [1.0, 1.1],
            }
        ).set_index("Date")

    monkeypatch.setattr("invest_strategy.data.yf.download", fake_download)

    prices = download_prices(("090010.SS", "090010.SZ", "090010"), date(2020, 1, 1))

    assert calls == ["090010.SS", "090010.SZ"]
    assert prices["close"].tolist() == [1.0, 1.1]


def test_download_prices_reports_all_failed_candidates(monkeypatch):
    def fake_download(symbol, start, end, auto_adjust, progress):
        return pd.DataFrame()

    monkeypatch.setattr("invest_strategy.data.yf.download", fake_download)

    with pytest.raises(ValueError, match="090010.SS、090010.SZ"):
        download_prices(("090010.SS", "090010.SZ"), date(2020, 1, 1))


def test_download_prices_supports_plain_china_fund_code(monkeypatch):
    calls = []

    def fake_fund_nav(symbol, start, end):
        calls.append((symbol, start, end))
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
                "close": [1.2, 1.3],
            }
        )

    monkeypatch.setattr("invest_strategy.data._download_china_fund_nav", fake_fund_nav)

    prices = download_prices("090010", date(2020, 1, 1), date(2020, 2, 1))

    assert calls == [("090010", date(2020, 1, 1), date(2020, 2, 1))]
    assert prices["close"].tolist() == [1.2, 1.3]


def test_download_dividend_percentiles_uses_csi_index_valuation_for_515100(monkeypatch):
    value_calls = []
    hist_calls = []

    def fake_index_value(symbol):
        value_calls.append(symbol)
        return pd.DataFrame(
            {
                "日期": pd.to_datetime(["2024-12-30", "2024-12-31"]),
                "市盈率1": [9.2, 9.4],
                "股息率1": [5.8, 5.9],
            }
        )

    def fake_index_history(symbol, start_date, end_date):
        hist_calls.append((symbol, start_date, end_date))
        return pd.DataFrame(
            {
                "日期": pd.date_range("2024-01-31", periods=12, freq="ME"),
                "滚动市盈率": [8.0, 8.2, 8.1, 8.3, 8.4, 8.5, 8.7, 8.9, 9.0, 9.1, 9.2, 9.4],
            }
        )

    def fake_fund_dividends(fund_code, start, end):
        return pd.DataFrame(
            {
                "date": pd.date_range("2024-01-31", periods=12, freq="ME"),
                "dividend_yield": [4.0] * 12,
                "dividend_percentile": [50.0] * 12,
            }
        )

    monkeypatch.setattr("akshare.stock_zh_index_value_csindex", fake_index_value, raising=False)
    monkeypatch.setattr("akshare.stock_zh_index_hist_csindex", fake_index_history, raising=False)
    monkeypatch.setattr("invest_strategy.data._china_fund_dividend_percentiles", fake_fund_dividends)

    valuation = download_dividend_percentiles("515100.SS", date(2024, 1, 1), date(2025, 1, 1))

    assert value_calls == ["930955"]
    assert hist_calls == [("930955", "20240101", "20250101")]
    assert valuation.columns.tolist() == [
        "date",
        "dividend_yield",
        "dividend_percentile",
        "pe",
        "pe_percentile",
    ]
    assert valuation.iloc[-1]["dividend_yield"] == 5.9
    assert valuation.iloc[0]["dividend_yield"] == 4.0
    assert valuation.iloc[0]["dividend_percentile"] == 50.0
    assert valuation.iloc[0]["pe_percentile"] == 50.0
    assert valuation.iloc[-1]["pe"] == 9.4
    assert valuation.iloc[-1]["pe_percentile"] == 100.0


def test_index_dividend_fallback_does_not_recompute_percentile(monkeypatch):
    def fake_index_value(symbol):
        return pd.DataFrame(
            {
                "日期": pd.to_datetime(["2024-12-31"]),
                "市盈率1": [9.4],
                "股息率1": [9.9],
            }
        )

    def fake_index_history(symbol, start_date, end_date):
        return pd.DataFrame(
            {
                "日期": pd.date_range("2024-01-31", periods=12, freq="ME"),
                "滚动市盈率": [8.0, 8.2, 8.1, 8.3, 8.4, 8.5, 8.7, 8.9, 9.0, 9.1, 9.2, 9.4],
            }
        )

    def fake_fund_dividends(fund_code, start, end):
        return pd.DataFrame(
            {
                "date": pd.date_range("2024-01-31", periods=12, freq="ME"),
                "dividend_yield": [4.0] * 12,
                "dividend_percentile": [25.0] * 12,
            }
        )

    monkeypatch.setattr("akshare.stock_zh_index_value_csindex", fake_index_value, raising=False)
    monkeypatch.setattr("akshare.stock_zh_index_hist_csindex", fake_index_history, raising=False)
    monkeypatch.setattr("invest_strategy.data._china_fund_dividend_percentiles", fake_fund_dividends)

    valuation = download_dividend_percentiles("515100.SS", date(2024, 1, 1), date(2025, 1, 1))

    assert valuation.iloc[-1]["dividend_yield"] == 9.9
    assert valuation.iloc[-1]["dividend_percentile"] == 25.0


def test_download_dividend_percentiles_normalizes_yfinance_dividend_dates(monkeypatch):
    class FakeTicker:
        info = {"trailingPE": 27.7}

        @property
        def dividends(self):
            return pd.Series(
                [1.0],
                index=pd.DatetimeIndex(["2024-01-15 09:30:00"], name="Date"),
                name="Dividends",
            )

    def fake_download(symbol, start, end, auto_adjust, progress):
        return pd.DataFrame(
            {
                "Date": pd.date_range("2024-01-01", periods=370, freq="D"),
                "Close": [100.0] * 370,
            }
        ).set_index("Date")

    monkeypatch.setattr("invest_strategy.data.yf.Ticker", lambda symbol: FakeTicker())
    monkeypatch.setattr("invest_strategy.data.yf.download", fake_download)

    valuation = download_dividend_percentiles("SPY", date(2024, 1, 1), date(2025, 1, 31))

    assert valuation["dividend_yield"].max() == 1.0
    assert "pe" not in valuation.columns  # Never retrofill today's PE into history.
    assert "pe_percentile" not in valuation.columns
