from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import uuid

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from invest_strategy.advice import build_advice
from invest_strategy.backtest import run_backtest
from invest_strategy.compare import compare_profiles
from invest_strategy.data import download_dividend_percentiles, download_prices
from invest_strategy.display import (
    comparison_display_frame,
    monthly_display_frame,
    target_monthly_display_frame,
)
from invest_strategy.models import AssetProfile, StrategyComponent, ValuationInput
from invest_strategy.profiles import (
    dividend_component,
    drawdown_component,
    fixed_contribution_component,
    get_default_profiles,
    get_profile_strategy_rows,
    ma_component,
    valuation_component,
    with_strategy_components,
)
from invest_strategy.strategies import evaluate_strategy
from invest_strategy.tickers import (
    CUSTOM_TICKER_LABEL,
    TickerSuggestion,
    get_suggested_tickers,
    resolve_ticker_choice,
)

_SESSION_CUSTOM = "custom_profiles"
_SESSION_LOADED = "custom_profiles_loaded"
_CUSTOM_PROFILES_FILE = Path.home() / ".invest-strategy-custom-profiles.json"

_COMPONENT_OPTIONS = {
    "固定定投": "fixed_contribution",
    "回撤加仓": "drawdown_add",
    "均线偏离": "ma_deviation",
    "股息率分位": "dividend_yield",
    "PB/PE估值辅助": "valuation_guard",
}


def main() -> None:
    st.set_page_config(page_title="投资策略回测", layout="wide")
    st.title("投资策略回测与建议")

    default_profiles = get_default_profiles()
    ticker_suggestions = get_suggested_tickers()

    _ensure_custom_loaded()
    custom_profiles: dict[str, AssetProfile] = st.session_state.get(_SESSION_CUSTOM, {})

    all_profiles = {**default_profiles, **custom_profiles}
    profile_names = {p.display_name: k for k, p in all_profiles.items()}

    with st.sidebar:
        ticker_options = [item.label for item in ticker_suggestions] + [CUSTOM_TICKER_LABEL]
        selected_ticker = st.selectbox("标的", ticker_options, index=0, label_visibility="collapsed")
        custom_ticker = ""
        if selected_ticker == CUSTOM_TICKER_LABEL:
            custom_ticker = st.text_input("自定义代码", value="SPY")
        ticker = resolve_ticker_choice(selected_ticker, custom_ticker, ticker_suggestions)

        profile_list = list(profile_names)
        selected_name = st.selectbox("策略", profile_list, index=min(1, len(profile_list) - 1))
        profile_key = profile_names[selected_name]

        col_new, col_copy, col_del = st.columns(3)
        with col_new:
            if st.button("新建", use_container_width=True):
                _enter_create_mode("blank")
        with col_copy:
            if st.button("复制", use_container_width=True):
                _enter_create_mode("copy", all_profiles[profile_key])
        with col_del:
            if profile_key in custom_profiles:
                if st.button("删除", use_container_width=True):
                    del custom_profiles[profile_key]
                    st.session_state[_SESSION_CUSTOM] = custom_profiles
                    _save_custom_profiles(custom_profiles)
                    st.rerun()

        if _is_create_mode():
            profile = _create_mode_editor(default_profiles, profile_key)
        else:
            profile = all_profiles[profile_key]

        if profile is None:
            st.info("请在上方配置策略组合。")
            return

        compare_names = st.multiselect(
            "对比",
            list(profile_names),
            default=st.session_state.get("compare_names", ["纯固定定投", "稳健定投"]),
        )
        st.session_state.compare_names = compare_names

        _prev_ticker = st.session_state.get("_prev_ticker")
        if _prev_ticker != selected_ticker:
            st.session_state._prev_ticker = selected_ticker
            min_start = _ticker_min_start(selected_ticker, ticker_suggestions)
            if min_start:
                st.session_state.backtest_start = min_start

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start = st.date_input(
                "开始",
                value=st.session_state.get("backtest_start", date(2015, 1, 1)),
            )
        with date_col2:
            end = st.date_input("结束", value=date.today())
        st.session_state.backtest_start = start
        monthly_contribution = st.number_input("月定投", min_value=100.0, value=100.0, step=100.0)

        st.subheader("策略参数")
        profile = _profile_editor(profile)

    _render_current_strategy(profile)
    source_label = "自定义" if profile_key in custom_profiles else "预设"
    st.caption(f"当前来源：{source_label} · {profile.display_name} · {profile.role}")

    if not ticker:
        st.info("请输入标的代码。")
        return

    selected_suggestion = _find_suggestion(selected_ticker, ticker_suggestions)

    try:
        price_symbols = selected_suggestion.price_symbols() if selected_suggestion else ticker
        prices = download_prices(price_symbols, start, end)
        valuation_history = download_dividend_percentiles(
            price_symbols[0] if isinstance(price_symbols, tuple) else price_symbols, start, end
        )
        current_valuation = _current_valuation_from_history(valuation_history)
        signal = evaluate_strategy(prices, profile, current_valuation)
        advice = build_advice(profile.display_name, signal, monthly_contribution)
        result = run_backtest(prices, profile, monthly_contribution, valuation_history)
        compare_profiles_selected = [all_profiles[profile_names[name]] for name in compare_names]
        if profile.display_name not in compare_names:
            compare_profiles_selected = [profile, *compare_profiles_selected]
        else:
            compare_profiles_selected = [
                profile if item.display_name == profile.display_name else item
                for item in compare_profiles_selected
            ]
        comparison = compare_profiles(
            prices,
            compare_profiles_selected,
            monthly_contribution,
            valuation_history,
        )
    except Exception as exc:  # Streamlit should show a friendly message.
        st.error(str(exc))
        return

    st.subheader("当前建议")
    st.markdown(f"### {advice.summary}")
    st.write(advice.details)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("累计投入", f"{result.summary.total_invested:,.0f}")
    col2.metric("期末市值", f"{result.summary.final_value:,.0f}")
    col3.metric("总收益率", f"{result.summary.total_return_pct:.2f}%")
    col4.metric("简单年化", f"{result.summary.annualized_return_pct:.2f}%")
    col5.metric("XIRR 年化", f"{result.summary.xirr_pct:.2f}%")
    col6.metric("组合最大回撤", f"{result.summary.max_drawdown_pct:.2f}%")

    signal_rows = {
        "操作": signal.action,
        "买入倍数": signal.multiplier,
        "标的从高点回撤": _fmt_pct(signal.drawdown_pct),
        f"MA{profile.trend_ma_days} 偏离": _fmt_pct(signal.ma_deviation_pct),
        "股息率": f"{signal.dividend_yield:.2f}%" if signal.dividend_yield is not None else "N/A",
        "股息率分位": f"{signal.dividend_percentile:.0f}%" if signal.dividend_percentile is not None else "N/A",
        "允许弹性买入": "是" if signal.allow_elastic_buy else "否",
    }
    st.dataframe(signal_rows, use_container_width=True)

    chart = px.line(result.monthly, x="date", y=["invested", "value"], title="投入本金 vs 组合市值")
    st.plotly_chart(chart, use_container_width=True)

    st.subheader("标的月度走势与回撤")
    target_col1, target_col2 = st.columns(2)
    target_price_chart = px.line(result.monthly, x="date", y="close", title="标的月度收盘价")
    target_col1.plotly_chart(target_price_chart, use_container_width=True)
    target_drawdown_chart = px.area(
        result.monthly,
        x="date",
        y="drawdown_pct",
        title="标的月度最大回撤",
    )
    target_col2.plotly_chart(target_drawdown_chart, use_container_width=True)
    st.dataframe(target_monthly_display_frame(result.monthly), use_container_width=True, hide_index=True)

    st.subheader("月度操作")
    st.dataframe(monthly_display_frame(result.monthly), use_container_width=True)

    st.subheader("策略组合对比")
    comparison_tsv = comparison.summary.to_csv(index=False, sep="\t")
    tool_col1, tool_col2, tool_col3 = st.columns([1.05, 1.05, 4])
    with tool_col1:
        st.download_button(
            "导出 CSV",
            data=comparison.summary.to_csv(index=False).encode("utf-8-sig"),
            file_name="strategy-comparison.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with tool_col2:
        _render_copy_button(comparison_tsv)
    st.dataframe(
        comparison_display_frame(comparison.summary),
        use_container_width=True,
        hide_index=True,
        height=360,
        column_config={
            "策略组合": st.column_config.TextColumn("策略组合", width="medium"),
            "投入份额": st.column_config.NumberColumn("投入份额", format="%.2f", width="small"),
            "累计投入": st.column_config.NumberColumn("累计投入", format="%.0f", width="small"),
            "期末市值": st.column_config.NumberColumn("期末市值", format="%.0f", width="small"),
            "总收益率": st.column_config.NumberColumn("总收益率", format="%.2f%%", width="small"),
            "年化回报率": st.column_config.NumberColumn("年化回报率", format="%.2f%%", width="small"),
            "XIRR年化": st.column_config.NumberColumn("XIRR年化", format="%.2f%%", width="small"),
            "组合最大回撤": st.column_config.NumberColumn("组合最大回撤", format="%.2f%%", width="small"),
        },
    )
    compare_chart = px.line(
        comparison.equity_curve,
        x="日期",
        y="组合市值",
        color="策略组合",
        title="不同策略组合市值对比",
    )
    st.plotly_chart(compare_chart, use_container_width=True)


# ---------------------------------------------------------------------------
# localStorage persistence
# ---------------------------------------------------------------------------

def _ensure_custom_loaded() -> None:
    if st.session_state.get(_SESSION_LOADED):
        return
    st.session_state[_SESSION_LOADED] = True
    saved = _load_custom_profiles()
    if saved:
        st.session_state[_SESSION_CUSTOM] = saved


def _load_custom_profiles() -> dict[str, AssetProfile]:
    if not _CUSTOM_PROFILES_FILE.exists():
        return {}
    try:
        data = json.loads(_CUSTOM_PROFILES_FILE.read_text(encoding="utf-8"))
        return {k: _profile_from_dict(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, KeyError):
        return {}


def _save_custom_profiles(profiles: dict[str, AssetProfile]) -> None:
    data = {k: _profile_to_dict(v) for k, v in profiles.items()}
    _CUSTOM_PROFILES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _profile_to_dict(p: AssetProfile) -> dict:
    return {
        "key": p.key,
        "display_name": p.display_name,
        "role": p.role,
        "base_description": p.base_description,
        "strategy_notes": p.strategy_notes,
        "fixed_layer_weight": p.fixed_layer_weight,
        "trend_ma_days": p.trend_ma_days,
        "strategy_components": [
            {
                "key": c.key,
                "display_name": c.display_name,
                "component_type": c.component_type,
                "enabled": c.enabled,
                "priority": c.priority,
                "params": c.params,
            }
            for c in p.strategy_components
        ],
    }


def _profile_from_dict(d: dict) -> AssetProfile:
    comps = tuple(
        StrategyComponent(
            key=c["key"],
            display_name=c["display_name"],
            component_type=c["component_type"],
            enabled=c.get("enabled", True),
            priority=c.get("priority", 100),
            params=c.get("params", {}),
        )
        for c in d.get("strategy_components", [])
    )
    return AssetProfile(
        key=d["key"],
        display_name=d["display_name"],
        role=d["role"],
        base_description=d["base_description"],
        strategy_notes=tuple(d.get("strategy_notes", [])),
        fixed_layer_weight=d.get("fixed_layer_weight", 1.0),
        trend_ma_days=d.get("trend_ma_days", 250),
        strategy_components=comps,
    )


# ---------------------------------------------------------------------------
# Create mode
# ---------------------------------------------------------------------------

_CREATE_MODE_KEY = "create_mode"


def _enter_create_mode(mode: str, source_profile: AssetProfile | None = None) -> None:
    st.session_state[_CREATE_MODE_KEY] = {
        "mode": mode,
        "source": _profile_to_dict(source_profile) if source_profile else None,
    }
    st.rerun()


def _exit_create_mode() -> None:
    st.session_state.pop(_CREATE_MODE_KEY, None)
    st.rerun()


def _is_create_mode() -> bool:
    return _CREATE_MODE_KEY in st.session_state


def _create_mode_editor(
    default_profiles: dict[str, AssetProfile],
    current_profile_key: str,
) -> AssetProfile | None:
    state = st.session_state[_CREATE_MODE_KEY]
    mode = state["mode"]

    st.subheader("新建策略组合" if mode == "blank" else "复制策略组合")

    if mode == "copy" and state["source"] is not None:
        source = _profile_from_dict(state["source"])
        default_name = f"{source.display_name}（副本）"
        default_role = source.role
        default_desc = source.base_description
        default_notes = source.strategy_notes
        default_comps = source.strategy_components
    else:
        default_name = ""
        default_role = "自定义策略"
        default_desc = ""
        default_notes = ("自定义策略组合。",)
        default_comps = (fixed_contribution_component(1.0),)

    display_name = st.text_input("策略名称", value=default_name, key="create-display-name")
    role = st.text_input("用途说明", value=default_role, key="create-role")

    if mode == "blank":
        selected_component_names = st.multiselect(
            "选择组件",
            list(_COMPONENT_OPTIONS),
            default=["固定定投"],
            key="create-components",
        )
        comps = tuple(
            _build_default_component(_COMPONENT_OPTIONS[name])
            for name in selected_component_names
        )
        if not comps:
            comps = (fixed_contribution_component(1.0),)
    else:
        comps = default_comps

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("保存", use_container_width=True, type="primary"):
            if not display_name.strip():
                st.error("请输入策略名称。")
                return None
            profile = AssetProfile(
                key=f"custom_{uuid.uuid4().hex[:8]}",
                display_name=display_name.strip(),
                role=role.strip() or "自定义策略",
                base_description=default_desc,
                strategy_notes=default_notes,
                fixed_layer_weight=_fixed_weight_from_raw(comps),
                trend_ma_days=_ma_days_from_raw(comps),
                strategy_components=comps,
            )
            custom_profiles: dict[str, AssetProfile] = st.session_state.get(_SESSION_CUSTOM, {})
            custom_profiles[profile.key] = profile
            st.session_state[_SESSION_CUSTOM] = custom_profiles
            _save_custom_profiles(custom_profiles)
            _exit_create_mode()
            return None
    with col_cancel:
        if st.button("取消", use_container_width=True):
            _exit_create_mode()
            return None

    if mode == "copy" and state["source"] is not None:
        source = _profile_from_dict(state["source"])
        profile = AssetProfile(
            key="preview",
            display_name=display_name or default_name,
            role=role or default_role,
            base_description=default_desc,
            strategy_notes=default_notes,
            fixed_layer_weight=_fixed_weight_from_raw(comps),
            trend_ma_days=_ma_days_from_raw(comps),
            strategy_components=comps,
        )
        st.caption("下方可预览并调整组件参数，保存后生效。")
        return profile

    return None


def _build_default_component(component_type: str) -> StrategyComponent:
    if component_type == "fixed_contribution":
        return fixed_contribution_component(1.0)
    if component_type == "drawdown_add":
        from invest_strategy.models import DrawdownRule
        return drawdown_component((
            DrawdownRule(-20, 2.0, "加倍定投"),
            DrawdownRule(-10, 1.3, "提高定投"),
        ))
    if component_type == "ma_deviation":
        from invest_strategy.models import MaRule
        return ma_component(250, (
            MaRule(20, 0.8, "停止弹性买入", allow_elastic_buy=False),
        ))
    if component_type == "dividend_yield":
        return dividend_component(0.3)
    if component_type == "valuation_guard":
        return valuation_component(0.1)
    return fixed_contribution_component(1.0)


def _fixed_weight_from_raw(comps: tuple[StrategyComponent, ...]) -> float:
    for c in comps:
        if c.component_type == "fixed_contribution" and c.enabled:
            return float(c.params.get("weight", 1.0))
    return 1.0


def _ma_days_from_raw(comps: tuple[StrategyComponent, ...]) -> int:
    for c in comps:
        if c.component_type == "ma_deviation" and c.enabled:
            return int(c.params.get("ma_days", 250))
    return 250


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _render_current_strategy(profile) -> None:
    st.subheader("当前组合策略")
    st.write(profile.base_description)

    enabled_components = [
        component.display_name for component in profile.strategy_components if component.enabled
    ]
    disabled_components = [
        component.display_name for component in profile.strategy_components if not component.enabled
    ]

    col1, col2 = st.columns(2)
    col1.markdown("**启用组件**")
    col1.write("、".join(enabled_components) if enabled_components else "无")
    col2.markdown("**停用组件**")
    col2.write("、".join(disabled_components) if disabled_components else "无")

    st.dataframe(pd.DataFrame(get_profile_strategy_rows(profile)), use_container_width=True)


def _render_copy_button(tsv_text: str) -> None:
    payload = json.dumps(tsv_text, ensure_ascii=False)
    components.html(
        f"""
        <style>
            .copy-btn {{
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: #ffffff;
                color: #111827;
                cursor: pointer;
                font: 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                padding: 8px 12px;
                width: 100%;
                box-sizing: border-box;
                display: block;
                height: 100%;
            }}
            .copy-btn:hover {{
                background: #f9fafb;
            }}
            html {{
                height: 100%;
            }}
            body {{
                margin: 0;
                height: 100%;
            }}
        </style>
        <button class="copy-btn" id="copy-comparison">复制数据</button>
        <script>
        const button = document.getElementById('copy-comparison');
        button.addEventListener('click', async () => {{
            const original = button.textContent;
            try {{
                await navigator.clipboard.writeText({payload});
                button.textContent = '已复制';
                setTimeout(() => button.textContent = original, 1500);
            }} catch (error) {{
                button.textContent = '复制失败';
                setTimeout(() => button.textContent = original, 1500);
            }}
        }});
        </script>
        """,
        height=40,
    )


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
                st.markdown("标的回撤加仓规则")
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


def _ticker_min_start(
    selected_label: str,
    suggestions: tuple[TickerSuggestion, ...],
) -> date | None:
    suggestion = _find_suggestion(selected_label, suggestions)
    if suggestion is None:
        return None
    return suggestion.min_backtest_start()


def _current_valuation_from_history(
    valuation_history: "pd.DataFrame | None",
) -> ValuationInput:
    if valuation_history is None or valuation_history.empty:
        return ValuationInput()
    last = valuation_history.iloc[-1]
    dp = float(last["dividend_percentile"]) if pd.notna(last.get("dividend_percentile")) else None
    return ValuationInput(dividend_percentile=dp)


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def _find_suggestion(
    selected_label: str,
    suggestions: tuple[TickerSuggestion, ...],
) -> TickerSuggestion | None:
    for s in suggestions:
        if s.label == selected_label:
            return s
    return None


if __name__ == "__main__":
    main()
