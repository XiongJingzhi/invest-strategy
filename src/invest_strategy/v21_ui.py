"""Thin V2.1 pages inside the existing Streamlit entry point."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from .compare import compare_accounts
from .decision import current_decision
from .market import download_snapshot, load_snapshot
from .models import AccountConfig, ExecutionPolicy
from .research import event_study, rolling_accounts
from .valuation import FairPEModel, sensitivity


def render_v21():
    st.header("V2.1 固定规则投资决策")
    st.caption(
        "人民币账户；NDX价格指数触发，复权可交易代理计算收益。估值模型为实验近似。"
    )
    directory = st.sidebar.text_input("可复核快照目录", "reports/data/single")
    mode = st.sidebar.selectbox("回测资产范围", ["纯纳指代理", "70/15/15组合"])
    if st.sidebar.button("下载真实行情快照"):
        try:
            symbols = (
                {"equity": "QQQ"}
                if mode == "纯纳指代理"
                else {"equity": "QQQ", "gold": "GLD", "dividend": "515100.SS"}
            )
            with st.spinner("下载与记录来源、时间及哈希…"):
                download_snapshot(directory, symbols=symbols)
        except Exception as exc:
            st.error(str(exc))
    if not (Path(directory) / "manifest.json").exists():
        st.info(
            "请下载快照，或选择已有含 market.csv 和 manifest.json 的目录。没有数据时不生成历史收益。"
        )
        return
    try:
        market, manifest = load_snapshot(directory)
        weights = (
            {"equity": 1.0}
            if mode == "纯纳指代理"
            else {"equity": 0.7, "gold": 0.15, "dividend": 0.15}
        )
        if not set(weights).issubset(market.columns):
            st.error("该快照不含三资产数据，请改用 reports/data/portfolio 或重新下载。")
            return
        st.caption(
            f"数据类型：{manifest['kind']}；最新有效NDX日期：{market.ndx.last_valid_index().date()}。不是盘中报价。"
        )
        with st.expander("来源与缺失值审计"):
            st.json(manifest)
        valid = market[list(weights)].dropna()
        default_start = max(pd.Timestamp("2022-01-03"), valid.index[0])
        start = st.sidebar.date_input("回测/计划起点", default_start.date())
        end = st.sidebar.date_input("回测截止", valid.index[-1].date())
        cash = st.sidebar.number_input(
            "期初现金", min_value=0.0, value=650000.0, step=10000.0
        )
        bonds = st.sidebar.number_input(
            "期初债券（固定储备市值）", min_value=0.0, value=0.0, step=10000.0
        )
        holdings = json.loads(st.sidebar.text_input("已有持仓单位 JSON", "{}"))
        total = st.sidebar.number_input(
            "核对期初总资产", min_value=0.0, value=650000.0, step=10000.0
        )
        reserve = st.sidebar.number_input(
            "安全底线", min_value=0.0, value=150000.0, step=10000.0
        )
        monthly = st.sidebar.number_input(
            "每月外部到账（首月不重复到账）", min_value=0.0, value=20000.0, step=1000.0
        )
        months = st.sidebar.number_input("转仓月数", min_value=1, value=9, step=1)
        ladder = st.sidebar.text_input("回撤比例 JSON", "[0.10,0.15,0.20,0.30]")
        amounts = st.sidebar.text_input(
            "各档新增金额 JSON", "[10000,20000,30000,40000]"
        )
        config = AccountConfig(
            initial_total=total,
            cash=cash,
            bonds=bonds,
            holdings=holdings,
            reserve=reserve,
            monthly=monthly,
            months=months,
            weights=weights,
            thresholds=tuple(json.loads(ladder)),
            amounts=tuple(json.loads(amounts)),
        )
        with st.sidebar.expander("产品执行实验"):
            st.caption("真实QDII须提供实际产品历史。QQQ结果不代表嘉实或银华主动基金。")
            cap = st.number_input(
                "权益日限购（0代表暂停申购）", min_value=0.0, value=1000000000.0
            )
            fee = st.number_input(
                "权益申购费率", min_value=0.0, max_value=0.99, value=0.0, step=0.001
            )
            slip = st.number_input(
                "滑点", min_value=0.0, max_value=0.99, value=0.0, step=0.001
            )
        policy = ExecutionPolicy(
            daily_caps={"equity": cap}, fees={"equity": fee}, slippage=slip
        )
        valuation_file = st.sidebar.file_uploader("历史时点估值CSV（可选）", type="csv")
        valuations = pd.read_csv(valuation_file) if valuation_file else None
        page = st.radio(
            "功能",
            ["当前投资决策", "历史回测", "估值分析", "滚动回测"],
            horizontal=True,
        )
        if page == "当前投资决策":
            st.info(
                "以下使用您填写的当前真实余额和成交CSV；不会将模拟成交当成真实已执行买入。请保存下载的事件ID，后续成交按ID登记。"
            )
            c1, c2, c3 = st.columns(3)
            current_cash = c1.number_input("当前现金", min_value=0.0, value=cash)
            current_bonds = c2.number_input("当前债券市值", min_value=0.0, value=bonds)
            remaining = c3.number_input(
                "尚未支出存量本金",
                min_value=0.0,
                value=max(0.0, cash + bonds - reserve),
            )
            execution_date = st.date_input(
                "拟执行交易日期（需自行核对产品开放日）", date.today()
            )
            ledger_file = st.file_uploader(
                "实际战术成交CSV：event_id,date,debit", type="csv"
            )
            ledger = pd.read_csv(ledger_file) if ledger_file else None
            d = current_decision(
                market.ndx.loc[: str(end)],
                start,
                execution_date,
                current_cash,
                current_bonds,
                remaining,
                ledger,
                config,
                valuations,
                cap,
            )
            for cols, items in [
                (
                    st.columns(3),
                    [
                        ("NDX正式收盘", d["close"]),
                        ("本轮历史高点", d["high"]),
                        ("当前回撤", f"{d['drawdown']:.2%}"),
                    ],
                ),
                (
                    st.columns(3),
                    [
                        ("应买入金额", d["should_buy"]),
                        ("真实累计战术买入", d["executed"]),
                        ("剩余待买", d["pending"]),
                    ],
                ),
                (
                    st.columns(3),
                    [
                        ("可动用资金", d["available"]),
                        ("现金+债券安全余额", d["reserve_balance"]),
                        ("下一触发价格", d["next_trigger_price"]),
                    ],
                ),
            ]:
                for col, (label, value) in zip(cols, items):
                    col.metric(label, "N/A" if value is None else value)
            st.write(
                "数据截至",
                d["as_of"],
                "已触发档位",
                d["triggered"],
                "理论累计目标",
                d["cumulative_target"],
            )
            st.write("执行约束 / 暂不买入原因：", d["reasons"])
            st.dataframe(d["events"])
            st.download_button(
                "下载事件清单", d["events"].to_csv(index=False), "events.csv"
            )
            return
        if page == "估值分析":
            st.warning(
                "下列是用户假设，不是可回填历史的基本面数据，也不是完整DCF。历史策略F需逐时点来源与公布时间。"
            )
            pe = st.number_input("用户输入当前远期PE", min_value=0.01, value=30.0)
            source = st.text_input("PE来源及公布日期", "未提供：此数值仅为演示假设")
            g = st.slider("五年EPS年增长假设", -0.3, 0.5, 0.1, 0.01)
            y = st.slider("股息率假设", 0.0, 0.1, 0.005, 0.001)
            r = st.slider(
                "要求收益率假设（可设为当时美债+风险溢价）", 0.01, 0.3, 0.1, 0.01
            )
            terminal = st.number_input("第五年合理PE假设", min_value=1.0, value=22.0)
            fair = FairPEModel(g, y, r, terminal).fair_pe()
            from .valuation import multiplier

            q = pe / fair
            st.write(
                {"来源": source, "模型合理PE": fair, "Q": q, "战术系数": multiplier(q)}
            )
            table = sensitivity(
                [g - 0.04, g - 0.02, g, g + 0.02, g + 0.04],
                [r - 0.02, r, r + 0.02],
                y,
                terminal,
            )
            st.dataframe(
                table.pivot(index="growth", columns="required_return", values="fair_pe")
            )
            return
        if page == "滚动回测":
            horizons = st.multiselect(
                "完整观察年限", [1, 3, 5, 10], default=[1, 3, 5, 10]
            )
            st.caption(
                "逐月第一个观测日建立新账户；只纳入完整区间。现金相同，已有持仓按起点重估。该运算可能较慢。"
            )
            if st.button("运行所有月度起点"):
                with st.spinner("计算滚动样本…"):
                    rolling = rolling_accounts(
                        market, start, end, config, tuple(horizons), policy, valuations
                    )
                st.dataframe(rolling)
                if not rolling.empty:
                    ok = rolling[rolling.status == "OK"]
                    st.plotly_chart(px.box(ok, x="strategy", y="twr", color="years"))
                    st.dataframe(
                        ok.groupby(["years", "strategy"])[
                            ["twr", "max_drawdown", "profit_vs_A", "profit_vs_B"]
                        ].agg(["median", "min", "max"])
                    )
                    st.download_button(
                        "下载全部起点结果", rolling.to_csv(index=False), "rolling.csv"
                    )
            return
        if st.button("运行同本金策略对比"):
            summary, results = compare_accounts(
                market, start, end, config, policy, valuations
            )
            st.dataframe(summary)
            st.caption(
                "金额以元计；收益与风险指标使用小数。家庭总资产与扣除固定安全底线的风险账户分别计算。Sharpe/Sortino以0为参考利率。"
            )
            selected = results["C"]
            curves = pd.concat({k: v.daily.nav for k, v in results.items()}, axis=1)
            st.plotly_chart(px.line(curves, labels={"value": "现金流调整净值"}))
            st.plotly_chart(
                px.line(
                    pd.concat({k: v.daily.total for k, v in results.items()}, axis=1),
                    labels={"value": "家庭总资产 CNY"},
                )
            )
            st.plotly_chart(
                px.line(
                    pd.concat(
                        {
                            k: v.daily.nav / v.daily.nav.cummax().clip(lower=1) - 1
                            for k, v in results.items()
                        },
                        axis=1,
                    )
                )
            )
            st.plotly_chart(
                px.line(
                    pd.concat(
                        {k: v.daily.risk_nav for k, v in results.items()}, axis=1
                    ),
                    labels={"value": "风险账户现金流调整净值"},
                )
            )
            trigger_chart = px.line(
                selected.daily, y="drawdown", labels={"drawdown": "NDX回撤"}
            )
            if not selected.events.empty:
                trigger_dates = selected.events.signal_date.drop_duplicates()
                trigger_chart.add_scatter(
                    x=trigger_dates,
                    y=selected.daily.loc[trigger_dates, "drawdown"],
                    mode="markers",
                    name="收盘触发",
                )
            st.plotly_chart(trigger_chart)
            st.subheader("策略C触发事件与流水")
            st.dataframe(selected.events)
            st.dataframe(selected.trades)
            st.download_button(
                "下载策略C账户日账", selected.daily.to_csv(), "account-C.csv"
            )
            st.download_button(
                "下载策略C成交", selected.trades.to_csv(index=False), "trades-C.csv"
            )
            detail, stats = event_study(market, start, str(end))
            st.subheader("历史回撤事件研究")
            st.caption(
                "事件重叠且相关；基准为同观察窗口所有可入场日期的无条件均值。未满观察期剔除。"
            )
            st.dataframe(stats)
            st.download_button(
                "下载事件明细", detail.to_csv(index=False), "event-study.csv"
            )
    except (ValueError, KeyError, TypeError) as exc:
        st.error(str(exc))
