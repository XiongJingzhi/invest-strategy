"""All market fixtures in this file are SYNTHETIC; no historical performance claims."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from invest_strategy.account import DrawdownState, run_account
from invest_strategy.compare import compare_accounts
from invest_strategy.models import AccountConfig, ExecutionPolicy
from invest_strategy.research import event_study
from invest_strategy.valuation import FairPEModel, historical_q, multiplier


def market(values=None, periods=500):
    dates = pd.bdate_range("2023-01-02", periods=periods)
    values = values or [100.0] * periods
    return pd.DataFrame({"ndx": values, "equity": np.full(periods, 100.0)}, index=dates)


@pytest.mark.parametrize(
    "threshold,close", [(0.1, 90), (0.15, 85), (0.2, 80), (0.3, 70)]
)
def test_exact_threshold(threshold, close):
    state = DrawdownState(100)
    assert len(state.observe(close, "2024-01-01", (threshold,), (100,))) == 1
    assert not state.observe(close + 0.01, "2024-01-02", (threshold,), (100,))


def test_no_threshold_and_gap_rebound_reset():
    state = DrawdownState(100)
    ladder, amounts = (0.1, 0.15, 0.2, 0.3), (1, 2, 3, 4)
    assert not state.observe(90.001, "2024-01-01", ladder, amounts)
    events = state.observe(70, "2024-01-02", ladder, amounts)
    assert len(events) == 4 and len({e["event_id"] for e in events}) == 4
    assert not state.observe(95, "2024-01-03", ladder, amounts)
    assert not state.observe(70, "2024-01-04", ladder, amounts)
    assert not state.observe(100, "2024-01-05", ladder, amounts)
    state.observe(101, "2024-01-06", ladder, amounts)
    assert len(state.observe(70, "2024-01-07", ladder, amounts)) == 4


def test_account_caps_cash_flows_and_reconciliation():
    m = market(periods=650)
    m.loc[m.index[260] :, "ndx"] = 60.0
    m.loc[m.index[300], "ndx"] = 101.0
    cfg = AccountConfig()
    r = run_account(m, m.index[252], m.index[-1], cfg)
    t = r.trades[r.trades.kind == "tactical"]
    assert (t.date > t.signal_date).all()
    assert t.debit.sum() <= 100000 + 1e-6
    assert t.groupby(t.date.dt.to_period("M")).debit.sum().max() <= 50000 + 1e-6
    assert r.daily.reserve_balance.min() >= cfg.reserve - 1e-6
    assert r.daily.cash.min() >= -1e-6
    assert r.trades[r.trades.kind != "new"].debit.sum() == pytest.approx(500000)
    assert r.daily.iloc[-1].stock_remaining == pytest.approx(0)
    deposits = r.daily[r.daily.external > 0]
    assert deposits.index.to_period("M").is_unique
    assert (deposits.external == 20000).all()
    last = r.daily.iloc[-1]
    assert last.total == pytest.approx(cfg.initial_total + r.daily.external.sum())
    assert last.cash == pytest.approx(
        cfg.cash + r.daily.external.sum() - r.trades.debit.sum()
    )
    assert last.units_equity == pytest.approx(r.trades.units.sum())
    assert r.metrics["net_profit"] == pytest.approx(0, abs=1e-6)
    assert r.metrics["twr"] == pytest.approx(0)
    assert r.metrics["cagr"] is None


def test_no_signal_close_execution_and_pending_queue():
    m = market()
    m.loc[m.index[252] :, "ndx"] = 60
    cfg = replace(AccountConfig(), monthly_tactical_cap=5000)
    r = run_account(m, m.index[252], m.index[265], cfg)
    assert r.trades[r.trades.kind == "tactical"].date.min() > m.index[252]
    assert r.daily.iloc[-1].pending_tactical > 0
    assert r.metrics["unfilled_orders"] > 0


def test_existing_holdings_and_bonds_no_invented_capital():
    m = market()
    cfg = replace(AccountConfig(), cash=200000, bonds=150000, holdings={"equity": 3000})
    r = run_account(m, m.index[252], m.index[-1], cfg, "A")
    assert r.daily.iloc[0].total == 650000
    assert r.daily.iloc[0].cash == 0
    assert r.daily.iloc[0].bonds == 150000
    with pytest.raises(ValueError, match="reconcile"):
        run_account(m, m.index[252], m.index[-1], replace(cfg, initial_total=999999))


@pytest.mark.parametrize("strategy", list("ABCDE"))
def test_future_data_cannot_change_prefix(strategy):
    m = market(periods=600)
    start, cutoff = m.index[252], m.index[320]
    # E must use pre-known exchange calendar, not the future number of dataset bars.
    full = run_account(m, start, m.index[-1], strategy=strategy)
    m.loc[m.index > cutoff, "ndx"] = 100000
    m.loc[m.index > cutoff, "equity"] = 500
    altered = run_account(m, start, cutoff, strategy=strategy)
    pd.testing.assert_frame_equal(
        full.daily.loc[:cutoff], altered.daily, check_dtype=False
    )


def test_same_capital_and_flows_all_comparison_arms():
    m = market()
    summary, results = compare_accounts(m, m.index[252], m.index[-1], AccountConfig())
    assert summary.loc["F", "status"].startswith("UNAVAILABLE")
    assert len(results) == 5
    assert len({r.metrics["external_total"] for r in results.values()}) == 1
    assert len({round(r.metrics["final_total"], 2) for r in results.values()}) == 1


def test_valuation_missing_and_future_vintage_rejected():
    m = market()
    with pytest.raises(ValueError, match="valuation"):
        run_account(m, m.index[252], m.index[260], strategy="F")
    history = pd.DataFrame(
        [
            dict(
                observed_at="2026-01-01",
                available_at="2026-01-02",
                source="test",
                forward_pe=30,
                growth=0.1,
                dividend=0.005,
                required_return=0.1,
                terminal_pe=22,
                parameters_fixed_at="2025-01-01",
            )
        ]
    )
    with pytest.raises(ValueError):
        historical_q(history, pd.Timestamp("2024-01-01"))
    assert FairPEModel().fair_pe() > 0
    assert [multiplier(q) for q in (0.85, 1.15, 1.35, 1.36)] == [1.25, 1, 0.75, 0.5]


def test_warmup_is_not_rolling_high():
    m = market()
    m.iloc[0, m.columns.get_loc("ndx")] = 200
    r = run_account(m, m.index[300], m.index[310])
    assert (r.daily.high == 200).all()
    with pytest.raises(ValueError, match="252"):
        run_account(m, m.index[100], m.index[200])


def test_fees_and_daily_limits_and_inception():
    m = market()
    policy = ExecutionPolicy(
        daily_caps={"equity": 1000},
        fees={"equity": 0.01},
        slippage=0.01,
        inception={"equity": str(m.index[255].date())},
    )
    r = run_account(m, m.index[252], m.index[270], policy=policy, strategy="A")
    assert r.trades.date.min() == m.index[255]
    assert r.trades.groupby("date").debit.sum().max() <= 1000
    assert r.metrics["fees"] > 0 and r.metrics["friction"] > r.metrics["fees"]
    assert r.daily.iloc[-1].total == pytest.approx(
        650000 + r.daily.external.sum() - r.metrics["friction"]
    )


def test_valuation_coefficient_locked():
    m = market()
    start = m.index[252]
    m.loc[start:, "ndx"] = 80
    hist = pd.DataFrame(
        [
            dict(
                observed_at=start - pd.Timedelta(days=1),
                available_at=start - pd.Timedelta(days=1),
                source="SYNTHETIC",
                forward_pe=15,
                growth=0.1,
                dividend=0,
                required_return=0.1,
                terminal_pe=20,
                parameters_fixed_at=start - pd.Timedelta(days=10),
            )
        ]
    )
    r = run_account(m, start, m.index[270], strategy="F", valuations=hist)
    assert r.events.multiplier.tolist() == [1.25] * 3
    assert r.events.target.sum() == 75000


def test_events_next_session_and_right_censoring():
    m = market(periods=800)
    m.loc[m.index[252] :, "ndx"] = 70
    detail, summary = event_study(m, m.index[252])
    assert (detail.entry > detail.signal_date).all()
    assert (detail.months <= 12).all()
    assert summary.overlapping_correlated_samples.all()
    assert len(detail[detail.months == 1]) == 5  # 10/15/20/25/30 each once


def test_actual_decision_uses_supplied_fills_not_simulated_buys():
    from invest_strategy.decision import current_decision

    m = market()
    start = m.index[252]
    m.loc[start:, "ndx"] = 80
    signal_date = m.index[260]
    price = m.ndx.loc[:signal_date]
    d = current_decision(
        price, start, signal_date + pd.Timedelta(days=1), 200000, 0, 500000
    )
    assert d["cumulative_target"] == 60000
    assert d["executed"] == 0
    assert d["should_buy"] == 50000  # cash reserve and monthly limit
    event = d["events"].iloc[0]
    ledger = pd.DataFrame(
        [dict(event_id=event.event_id, date=m.index[253], debit=10000)]
    )
    d = current_decision(
        price, start, signal_date + pd.Timedelta(days=1), 190000, 0, 490000, ledger
    )
    assert d["executed"] == 10000 and d["should_buy"] == 40000
    d = current_decision(price, start, signal_date, 150000, 0, 490000, ledger)
    assert d["should_buy"] == 0
    assert any("安全资金底线" in reason for reason in d["reasons"])


def test_multiaset_reconciles_fees_and_existing_holdings():
    m = market()
    m["gold"] = 200.0
    m["dividend"] = 50.0
    cfg = replace(
        AccountConfig(),
        cash=500000,
        bonds=50000,
        holdings={"gold": 500},
        weights={"equity": 0.7, "gold": 0.15, "dividend": 0.15},
    )
    r = run_account(
        m, m.index[252], m.index[-1], cfg, policy=ExecutionPolicy(fees={"equity": 0.01})
    )
    last = r.daily.iloc[-1]
    value = sum(last["units_" + a] * m.iloc[-1][a] for a in cfg.weights)
    assert last.total == pytest.approx(last.cash + last.bonds + value)
    assert last.total == pytest.approx(
        cfg.initial_total + r.daily.external.sum() - r.trades.friction.sum()
    )
    assert (r.daily.reserve_balance >= cfg.reserve - 1e-6).all()


def test_valuation_future_updates_leave_prefix_unchanged():
    m = market()
    start = m.index[252]
    m.loc[start:, "ndx"] = 80
    row = dict(
        observed_at=start - pd.Timedelta(days=1),
        available_at=start - pd.Timedelta(days=1),
        source="SYNTHETIC",
        forward_pe=15,
        growth=0.1,
        dividend=0,
        required_return=0.1,
        terminal_pe=20,
        parameters_fixed_at=start - pd.Timedelta(days=10),
    )
    hist = pd.DataFrame([row])
    r = run_account(m, start, m.index[270], strategy="F", valuations=hist)
    future = {
        **row,
        "observed_at": "2026-01-01",
        "available_at": "2026-01-02",
        "forward_pe": 1000,
    }
    altered = run_account(
        m, start, m.index[270], strategy="F", valuations=pd.DataFrame([row, future])
    )
    pd.testing.assert_frame_equal(r.daily, altered.daily)


def test_streamlit_v21_pages_load_without_network():
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path("app.py").resolve()), default_timeout=15)
    app.session_state["workflow"] = "V2.1 确定性账户"
    app.run()
    assert not app.exception
    app.radio[0].set_value("历史回测").run()
    assert not app.exception
    app.radio[0].set_value("估值分析").run()
    assert not app.exception
    app.radio[0].set_value("滚动回测").run()
    assert not app.exception


def test_tactical_authorized_queue_cannot_refill_after_new_high_or_deadline():
    m = market(periods=650)
    start = m.index[252]
    m.loc[start:, "ndx"] = 60
    m.loc[m.index[280], "ndx"] = 101
    m.loc[m.index[450], "ndx"] = 102
    r = run_account(m, start, m.index[-1])
    assert r.events.target.sum() <= 100000
    assert r.events[r.events.constraint == "TRANSFER_CLOSED"].target.sum() == 0
    assert r.events[r.events.cycle > 0].target.sum() == 0
    assert r.daily.iloc[-1].pending_tactical <= 100000


def test_missing_asset_session_cannot_execute_and_premium_debits_cash():
    m = market()
    start = m.index[252]
    m.loc[start:, "ndx"] = 80
    m.loc[m.index[253], "equity"] = np.nan
    m["equity_premium"] = 0.1
    r = run_account(m, start, m.index[270])
    assert not (r.trades.date == m.index[253]).any()
    assert np.allclose(r.trades.execution_price, 110.0)
    assert r.metrics["friction"] > 0


def test_frozen_holdout_refuses_retuned_parameters():
    from invest_strategy.valuation import run_frozen_holdout

    m = market()
    start = m.index[252]
    row = dict(
        observed_at=start - pd.Timedelta(days=1),
        available_at=start - pd.Timedelta(days=1),
        source="SYNTHETIC",
        forward_pe=15,
        growth=0.1,
        dividend=0,
        required_return=0.1,
        terminal_pe=20,
        parameters_fixed_at=start - pd.Timedelta(days=10),
    )
    r = run_frozen_holdout(
        m,
        start,
        m.index[260],
        start - pd.Timedelta(days=5),
        pd.DataFrame([row]),
        AccountConfig(),
    )
    assert r.strategy == "F"
    with pytest.raises(ValueError, match="frozen"):
        run_frozen_holdout(
            m,
            start,
            m.index[260],
            start - pd.Timedelta(days=5),
            pd.DataFrame([row, {**row, "growth": 0.2}]),
            AccountConfig(),
        )


def test_rolling_prefix_optimization_matches_independent_accounts():
    from invest_strategy.research import rolling_accounts

    m = market(periods=850)
    m["equity"] = 100 * np.exp(np.linspace(0, 0.3, len(m)))
    start = m.index[252]
    # Only one monthly cohort, but supply long observation history.
    r = rolling_accounts(m, start, m.index[-1], AccountConfig(), horizons=(1, 2))
    first = r[(pd.to_datetime(r.start) == start) & (r.years == 1)].set_index("strategy")
    summary, _ = compare_accounts(
        m, start, start + pd.DateOffset(years=1), AccountConfig()
    )
    for strategy in "ABCDE":
        for metric in [
            "final_total",
            "twr",
            "xirr",
            "net_profit",
            "max_drawdown",
            "triggers",
            "pending_tactical",
            "unfilled_orders",
        ]:
            assert first.loc[strategy, metric] == pytest.approx(
                summary.loc[strategy, metric]
            )


def test_portfolio_order_sizing_cannot_see_execution_close():
    m = market()
    m["gold"] = 100.0
    m["dividend"] = 100.0
    cfg = replace(
        AccountConfig(),
        cash=450000,
        holdings={"gold": 1000, "equity": 1000},
        weights={"equity": 0.7, "gold": 0.15, "dividend": 0.15},
    )
    start = m.index[252]
    execution = (
        m.loc[start:].groupby(m.loc[start:].index.to_period("M")).head(1).index[1]
    )
    a = run_account(m, start, execution, cfg, "B")
    m.loc[execution, "equity"] = 10000.0
    b = run_account(m, start, execution, cfg, "B")
    aa = a.trades[a.trades.date == execution].set_index(["asset", "kind"]).debit
    bb = b.trades[b.trades.date == execution].set_index(["asset", "kind"]).debit
    pd.testing.assert_series_equal(aa, bb)


def test_independent_ledger_audit_detects_tampered_cash():
    from invest_strategy.audit import audit_account

    m = market()
    r = run_account(m, m.index[252], m.index[-1])
    assert audit_account(r, m)["passed"]
    tampered = r.daily.copy()
    tampered.iloc[-1, tampered.columns.get_loc("cash")] += 100
    assert not audit_account(replace(r, daily=tampered), m)["passed"]


def test_dated_subscription_caps_pause_and_resume_queue():
    m = market()
    start = m.index[252]
    m["equity_cap"] = 0.0
    m.loc[m.index[255] :, "equity_cap"] = 2000.0
    m["equity_fee"] = 0.02
    r = run_account(m, start, m.index[260], strategy="A")
    assert r.trades.date.min() == m.index[255]
    assert r.trades.groupby("date").debit.sum().max() <= 2000
    assert np.allclose(r.trades.fee, r.trades.debit * 0.02)
    assert r.daily.iloc[-1].pending_regular > 0
