from __future__ import annotations

from datetime import date

import plotly.express as px
import streamlit as st

from invest_strategy.advice import build_advice
from invest_strategy.backtest import run_backtest
from invest_strategy.data import download_prices
from invest_strategy.models import ValuationInput
from invest_strategy.profiles import get_default_profiles
from invest_strategy.strategies import evaluate_strategy


def main() -> None:
    st.set_page_config(page_title="投资策略回测", layout="wide")
    st.title("投资策略回测与建议")

    profiles = get_default_profiles()
    profile_names = {profile.display_name: key for key, profile in profiles.items()}

    with st.sidebar:
        st.header("参数")
        ticker = st.text_input("股票/ETF 代码", value="SPY")
        selected_name = st.selectbox("资产类型", list(profile_names), index=1)
        profile = profiles[profile_names[selected_name]]
        start = st.date_input("开始日期", value=date(2015, 1, 1))
        end = st.date_input("结束日期", value=date.today())
        monthly_contribution = st.number_input("每月基础定投金额", min_value=100.0, value=3000.0, step=100.0)

        st.subheader("可选估值输入")
        dividend_percentile = _optional_percent("股息率分位")
        pb_percentile = _optional_percent("PB 分位")
        pe_percentile = _optional_percent("PE 分位")

    st.caption(f"{profile.role} · {profile.base_description}")

    if not ticker:
        st.info("请输入标的代码。")
        return

    try:
        prices = download_prices(ticker, start, end)
        valuation = ValuationInput(dividend_percentile, pb_percentile, pe_percentile)
        signal = evaluate_strategy(prices, profile, valuation)
        advice = build_advice(profile.display_name, signal, monthly_contribution)
        result = run_backtest(prices, profile, monthly_contribution, valuation)
    except Exception as exc:  # Streamlit should show a friendly message.
        st.error(str(exc))
        return

    st.subheader("当前建议")
    st.markdown(f"### {advice.summary}")
    st.write(advice.details)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("累计投入", f"{result.summary.total_invested:,.0f}")
    col2.metric("期末市值", f"{result.summary.final_value:,.0f}")
    col3.metric("总收益率", f"{result.summary.total_return_pct:.2f}%")
    col4.metric("组合最大回撤", f"{result.summary.max_drawdown_pct:.2f}%")

    signal_rows = {
        "操作": signal.action,
        "买入倍数": signal.multiplier,
        "从高点回撤": _fmt_pct(signal.drawdown_pct),
        f"MA{profile.trend_ma_days} 偏离": _fmt_pct(signal.ma_deviation_pct),
        "允许弹性买入": "是" if signal.allow_elastic_buy else "否",
    }
    st.dataframe(signal_rows, use_container_width=True)

    chart = px.line(result.monthly, x="date", y=["invested", "value"], title="投入本金 vs 组合市值")
    st.plotly_chart(chart, use_container_width=True)

    display = result.monthly.copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    st.subheader("月度操作")
    st.dataframe(display.tail(36), use_container_width=True)


def _optional_percent(label: str) -> float | None:
    enabled = st.checkbox(f"填写 {label}", value=False)
    if not enabled:
        return None
    return st.slider(label, min_value=0.0, max_value=100.0, value=50.0, step=1.0)


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


if __name__ == "__main__":
    main()
