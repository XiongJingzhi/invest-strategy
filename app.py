from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from invest_strategy.advice import build_advice
from invest_strategy.backtest import run_backtest
from invest_strategy.data import download_prices
from invest_strategy.display import monthly_display_frame
from invest_strategy.models import DrawdownRule, MaRule, ValuationInput
from invest_strategy.profiles import (
    get_default_profiles,
    get_profile_strategy_rows,
    with_profile_settings,
)
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

        st.subheader("策略参数")
        profile = _profile_editor(profile)

        st.subheader("可选估值输入")
        dividend_percentile = _optional_percent("股息率分位")
        pb_percentile = _optional_percent("PB 分位")
        pe_percentile = _optional_percent("PE 分位")

    display_profiles = {**profiles, profile.key: profile}
    _render_strategy_library(display_profiles, profile.key)
    st.divider()
    st.caption(f"当前执行模板：{profile.role} · {profile.base_description}")

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

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("累计投入", f"{result.summary.total_invested:,.0f}")
    col2.metric("期末市值", f"{result.summary.final_value:,.0f}")
    col3.metric("总收益率", f"{result.summary.total_return_pct:.2f}%")
    col4.metric("年化回报率", f"{result.summary.annualized_return_pct:.2f}%")
    col5.metric("组合最大回撤", f"{result.summary.max_drawdown_pct:.2f}%")

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

    st.subheader("月度操作")
    st.dataframe(monthly_display_frame(result.monthly), use_container_width=True)


def _render_strategy_library(profiles: dict[str, object], selected_key: str) -> None:
    st.subheader("资产策略库")
    tabs = st.tabs([profile.display_name for profile in profiles.values()])
    for tab, profile in zip(tabs, profiles.values(), strict=True):
        with tab:
            marker = "当前选择" if profile.key == selected_key else profile.role
            st.markdown(f"**{marker}**")
            st.write(profile.base_description)
            for note in profile.strategy_notes:
                st.markdown(f"- {note}")
            st.dataframe(pd.DataFrame(get_profile_strategy_rows(profile)), use_container_width=True)


def _profile_editor(profile):
    trend_ma_days = st.number_input(
        "趋势均线天数",
        min_value=20,
        max_value=500,
        value=int(profile.trend_ma_days),
        step=10,
    )
    fixed_layer_weight = st.slider(
        "固定层权重",
        min_value=0.0,
        max_value=2.0,
        value=float(profile.fixed_layer_weight),
        step=0.1,
    )

    drawdown_rules = profile.drawdown_rules
    if profile.drawdown_rules:
        st.markdown("回撤加仓规则")
        drawdown_frame = pd.DataFrame(
            [
                {
                    "回撤阈值%": rule.threshold_pct,
                    "买入倍数": rule.multiplier,
                    "动作": rule.action,
                }
                for rule in profile.drawdown_rules
            ]
        )
        edited_drawdown = st.data_editor(
            drawdown_frame,
            hide_index=True,
            num_rows="dynamic",
            key=f"{profile.key}-drawdown-rules",
        )
        drawdown_rules = _drawdown_rules_from_frame(edited_drawdown)

    ma_rules = profile.ma_rules
    if profile.ma_rules:
        st.markdown("均线偏离规则")
        ma_frame = pd.DataFrame(
            [
                {
                    "偏离阈值%": rule.threshold_pct,
                    "买入倍数": rule.multiplier,
                    "动作": rule.action,
                    "允许弹性买入": rule.allow_elastic_buy,
                }
                for rule in profile.ma_rules
            ]
        )
        edited_ma = st.data_editor(
            ma_frame,
            hide_index=True,
            num_rows="dynamic",
            key=f"{profile.key}-ma-rules",
        )
        ma_rules = _ma_rules_from_frame(edited_ma)

    return with_profile_settings(
        profile,
        trend_ma_days=int(trend_ma_days),
        fixed_layer_weight=float(fixed_layer_weight),
        drawdown_rules=drawdown_rules,
        ma_rules=ma_rules,
    )


def _drawdown_rules_from_frame(frame: pd.DataFrame) -> tuple[DrawdownRule, ...]:
    rules: list[DrawdownRule] = []
    for _, row in frame.dropna(subset=["回撤阈值%", "买入倍数", "动作"]).iterrows():
        rules.append(
            DrawdownRule(
                threshold_pct=float(row["回撤阈值%"]),
                multiplier=float(row["买入倍数"]),
                action=str(row["动作"]),
            )
        )
    return tuple(rules)


def _ma_rules_from_frame(frame: pd.DataFrame) -> tuple[MaRule, ...]:
    rules: list[MaRule] = []
    for _, row in frame.dropna(subset=["偏离阈值%", "买入倍数", "动作"]).iterrows():
        rules.append(
            MaRule(
                threshold_pct=float(row["偏离阈值%"]),
                multiplier=float(row["买入倍数"]),
                action=str(row["动作"]),
                allow_elastic_buy=bool(row.get("允许弹性买入", True)),
            )
        )
    return tuple(rules)


def _optional_percent(label: str) -> float | None:
    enabled = st.checkbox(f"填写 {label}", value=False)
    if not enabled:
        return None
    return st.slider(label, min_value=0.0, max_value=100.0, value=50.0, step=1.0)


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


if __name__ == "__main__":
    main()
