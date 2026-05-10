import pandas as pd

from invest_strategy.display import (
    comparison_display_frame,
    monthly_display_frame,
    target_monthly_display_frame,
)


def test_monthly_display_frame_uses_chinese_columns():
    monthly = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31"]),
            "close": [100.0],
            "multiplier": [1.5],
            "contribution": [1500.49],
            "bought_shares": [15.0],
            "shares": [15.0],
            "invested": [1500.5],
            "value": [1500.0],
            "drawdown_pct": [-10.0],
            "pe": [8.86],
            "pe_percentile": [78.6],
            "action": ["提高定投"],
        }
    )

    display = monthly_display_frame(monthly)

    assert list(display.columns) == [
        "日期",
        "收盘价",
        "买入倍数",
        "投入金额",
        "累计投入",
        "标的回撤",
        "PE",
        "PE分位",
        "操作",
    ]
    assert display.iloc[0]["日期"] == "2024-01"
    assert display.iloc[0]["投入金额"] == 1500
    assert display.iloc[0]["累计投入"] == 1501
    assert "买入份额" not in display.columns
    assert "累计份额" not in display.columns
    assert "组合市值" not in display.columns


def test_monthly_display_frame_hides_empty_pe_columns():
    monthly = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-31"]),
            "close": [100.0],
            "contribution": [100.0],
            "invested": [100.0],
            "pe": [None],
            "pe_percentile": [None],
            "action": ["正常定投"],
        }
    )

    display = monthly_display_frame(monthly)

    assert "PE" not in display.columns
    assert "PE分位" not in display.columns


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


def test_comparison_display_frame_hides_export_only_columns_and_orders_metrics():
    summary = pd.DataFrame(
        {
            "策略组合": ["纯固定定投"],
            "组合规则": ["full rule text"],
            "策略参数": ["full params"],
            "投入份额": [333601.8323],
            "累计投入": [267000.0],
            "期末市值": [396318.96],
            "总收益率": [48.43],
            "年化回报率": [5.53],
            "组合最大回撤": [-6.71],
        }
    )

    display = comparison_display_frame(summary)

    assert list(display.columns) == [
        "策略组合",
        "投入份额",
        "累计投入",
        "期末市值",
        "总收益率",
        "年化回报率",
        "组合最大回撤",
    ]
    assert "组合规则" not in display.columns
    assert "策略参数" not in display.columns
