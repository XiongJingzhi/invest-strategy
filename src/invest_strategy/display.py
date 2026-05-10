from __future__ import annotations

import pandas as pd


MONTHLY_COLUMN_NAMES = {
    "date": "日期",
    "close": "收盘价",
    "multiplier": "买入倍数",
    "contribution": "投入金额",
    "invested": "累计投入",
    "drawdown_pct": "标的回撤",
    "dividend_yield": "股息率%",
    "dividend_percentile": "股息率分位",
    "pe": "PE",
    "pe_percentile": "PE分位",
    "action": "操作",
}


def monthly_display_frame(monthly: pd.DataFrame) -> pd.DataFrame:
    display = monthly.copy()
    display["date"] = pd.to_datetime(display["date"]).dt.strftime("%Y-%m")
    for column in ("contribution", "invested"):
        if column in display.columns:
            values = pd.to_numeric(display[column], errors="coerce")
            display[column] = values.map(
                lambda value: pd.NA if pd.isna(value) else int(value + 0.5)
            ).astype("Int64")
    display = _drop_empty_optional_columns(display, ("pe", "pe_percentile"))
    display = display.rename(columns=MONTHLY_COLUMN_NAMES)
    available = [col for col in MONTHLY_COLUMN_NAMES.values() if col in display.columns]
    return display[available]


def _drop_empty_optional_columns(display: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    for column in columns:
        if column in display.columns and display[column].isna().all():
            display = display.drop(columns=column)
    return display


def target_monthly_display_frame(monthly: pd.DataFrame) -> pd.DataFrame:
    display = monthly.copy()
    display["date"] = pd.to_datetime(display["date"]).dt.strftime("%Y-%m")
    display = display.rename(
        columns={
            "date": "日期",
            "close": "标的收盘价",
            "drawdown_pct": "标的最大回撤",
            "action": "操作",
            "multiplier": "买入倍数",
            "contribution": "投入金额",
            "bought_shares": "买入份额",
            "shares": "累计份额",
            "invested": "累计投入",
            "value": "组合市值",
        }
    )
    return display[
        [
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
    ]


def comparison_display_frame(summary: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "策略组合",
        "投入份额",
        "累计投入",
        "期末市值",
        "总收益率",
        "年化回报率",
        "XIRR年化",
        "组合最大回撤",
    ]
    return summary[[column for column in columns if column in summary.columns]].copy()
