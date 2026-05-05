import pandas as pd

from invest_strategy.display import monthly_display_frame, target_monthly_display_frame


def test_monthly_display_frame_uses_chinese_columns():
    monthly = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31"]),
            "close": [100.0],
            "multiplier": [1.5],
            "contribution": [1500.0],
            "bought_shares": [15.0],
            "shares": [15.0],
            "invested": [1500.0],
            "value": [1500.0],
            "drawdown_pct": [-10.0],
            "action": ["提高定投"],
        }
    )

    display = monthly_display_frame(monthly)

    assert list(display.columns) == [
        "日期",
        "收盘价",
        "买入倍数",
        "投入金额",
        "买入份额",
        "累计份额",
        "累计投入",
        "组合市值",
        "标的回撤",
        "操作",
    ]
    assert display.iloc[0]["日期"] == "2024-01"


def test_target_monthly_display_frame_contains_target_and_investment_data():
    monthly = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31"]),
            "close": [100.0],
            "multiplier": [1.5],
            "contribution": [1500.0],
            "bought_shares": [15.0],
            "shares": [15.0],
            "invested": [1500.0],
            "value": [1500.0],
            "drawdown_pct": [-10.0],
            "action": ["提高定投"],
        }
    )

    display = target_monthly_display_frame(monthly)

    assert list(display.columns) == [
        "日期",
        "标的收盘价",
        "标的最大回撤",
        "操作",
        "买入倍数",
        "投入金额",
        "买入份额",
        "累计份额",
        "累计投入",
        "组合市值",
    ]
