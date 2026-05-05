from datetime import date

import pandas as pd
import pytest

from invest_strategy.data import download_prices


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
