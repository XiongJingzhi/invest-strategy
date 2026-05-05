from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from invest_strategy.advice import build_advice
from invest_strategy.backtest import run_backtest
from invest_strategy.data import download_prices
from invest_strategy.display import monthly_display_frame
from invest_strategy.models import StrategyComponent, ValuationInput
from invest_strategy.profiles import (
    get_default_profiles,
    get_profile_strategy_rows,
    with_strategy_components,
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
    components = []
    for component in sorted(profile.strategy_components, key=lambda item: item.priority):
        with st.expander(component.display_name, expanded=component.enabled):
            enabled = st.checkbox(
                "启用",
                value=component.enabled,
                key=f"{profile.key}-{component.key}-enabled",
            )
            params = dict(component.params)

            if component.component_type == "fixed_contribution":
                params["weight"] = st.slider(
                    "固定层权重",
                    min_value=0.0,
                    max_value=2.0,
                    value=float(params.get("weight", 1.0)),
                    step=0.1,
                    key=f"{profile.key}-{component.key}-weight",
                )
            elif component.component_type == "drawdown_add":
                st.markdown("回撤加仓规则")
                params["rules"] = _rules_from_editor(
                    params.get("rules", []),
                    key=f"{profile.key}-{component.key}-rules",
                    include_elastic=False,
                )
            elif component.component_type == "ma_deviation":
                params["ma_days"] = st.number_input(
                    "趋势均线天数",
                    min_value=20,
                    max_value=500,
                    value=int(params.get("ma_days", profile.trend_ma_days)),
                    step=10,
                    key=f"{profile.key}-{component.key}-ma-days",
                )
                st.markdown("均线偏离规则")
                params["rules"] = _rules_from_editor(
                    params.get("rules", []),
                    key=f"{profile.key}-{component.key}-rules",
                    include_elastic=True,
                )
            elif component.component_type == "dividend_yield":
                params["high_percentile"] = st.slider(
                    "加仓股息率分位",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(params.get("high_percentile", 70)),
                    step=1.0,
                    key=f"{profile.key}-{component.key}-high",
                )
                params["multiplier"] = st.slider(
                    "加仓买入倍数",
                    min_value=0.0,
                    max_value=5.0,
                    value=float(params.get("multiplier", 1.5)),
                    step=0.1,
                    key=f"{profile.key}-{component.key}-multiplier",
                )
            elif component.component_type == "valuation_guard":
                params["high_percentile"] = st.slider(
                    "高估停止弹性买入分位",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(params.get("high_percentile", 90)),
                    step=1.0,
                    key=f"{profile.key}-{component.key}-high",
                )

            components.append(
                StrategyComponent(
                    key=component.key,
                    display_name=component.display_name,
                    component_type=component.component_type,
                    enabled=enabled,
                    priority=component.priority,
                    params=params,
                )
            )

    return with_strategy_components(profile, tuple(components))


def _rules_from_editor(
    rules: object,
    *,
    key: str,
    include_elastic: bool,
) -> list[dict[str, object]]:
    rows = []
    for rule in rules if isinstance(rules, list) else []:
        row = {
            "阈值%": rule.get("threshold_pct", 0),
            "买入倍数": rule.get("multiplier", 1),
            "动作": rule.get("action", "正常定投"),
        }
        if include_elastic:
            row["允许弹性买入"] = rule.get("allow_elastic_buy", True)
        rows.append(row)

    edited = st.data_editor(pd.DataFrame(rows), hide_index=True, num_rows="dynamic", key=key)
    normalized = []
    required = ["阈值%", "买入倍数", "动作"]
    for _, row in edited.dropna(subset=required).iterrows():
        item = {
            "threshold_pct": float(row["阈值%"]),
            "multiplier": float(row["买入倍数"]),
            "action": str(row["动作"]),
        }
        if include_elastic:
            item["allow_elastic_buy"] = bool(row.get("允许弹性买入", True))
        normalized.append(item)
    return normalized


def _optional_percent(label: str) -> float | None:
    enabled = st.checkbox(f"填写 {label}", value=False)
    if not enabled:
        return None
    return st.slider(label, min_value=0.0, max_value=100.0, value=50.0, step=1.0)


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


if __name__ == "__main__":
    main()
