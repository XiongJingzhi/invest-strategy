"""Actual-account recommendation from dated official-close inputs and supplied fill ledger."""

import math

import pandas as pd

from .account import DrawdownState
from .models import AccountConfig
from .valuation import historical_q, multiplier


def current_decision(
    ndx,
    plan_start,
    execution_date,
    cash,
    bonds,
    stock_remaining,
    ledger=None,
    config=None,
    valuations=None,
    product_cap=float("inf"),
):
    config = config if config is not None else AccountConfig()
    if (
        len(config.thresholds) != len(config.amounts)
        or sorted(set(config.thresholds)) != list(config.thresholds)
        or any(not 0 < t < 1 for t in config.thresholds)
        or any(not math.isfinite(a) or a < 0 for a in config.amounts)
    ):
        raise ValueError("Invalid drawdown ladder")
    ndx = ndx.dropna().sort_index()
    plan_start, execution_date = pd.Timestamp(plan_start), pd.Timestamp(execution_date)
    if ndx.index.has_duplicates or any(not math.isfinite(v) or v <= 0 for v in ndx):
        raise ValueError("Invalid official NDX history")
    if (
        any(not math.isfinite(v) or v < 0 for v in (cash, bonds, stock_remaining))
        or product_cap < 0
    ):
        raise ValueError("Invalid actual balances")
    warm = ndx.loc[ndx.index < plan_start]
    if len(warm) < 252:
        raise ValueError("252 pre-start NDX closes required")
    state = DrawdownState(float(warm.max()))
    events = []
    end = (plan_start.to_period("M") + config.months - 1).end_time.normalize()
    for date, price in ndx.loc[plan_start:].items():
        q = (
            historical_q(
                valuations,
                date.tz_localize("America/New_York") + pd.Timedelta(hours=16),
            )
            if valuations is not None
            else None
        )
        for event in state.observe(
            float(price),
            date,
            config.thresholds,
            config.amounts,
            multiplier(q) if q else 1.0,
        ):
            event["raw_target"] = event["target"]
            event["target"] = (
                min(
                    event["target"],
                    max(0.0, config.tactical_budget - sum(e["target"] for e in events)),
                )
                if date <= end
                else 0.0
            )
            events.append(event)
    lookup = {e["event_id"]: e for e in events}
    ledger = (
        pd.DataFrame(columns=["event_id", "date", "debit"])
        if ledger is None
        else ledger.copy()
    )
    if not {"event_id", "date", "debit"}.issubset(ledger.columns):
        raise ValueError("Fill ledger requires event_id,date,debit")
    ledger["date"] = pd.to_datetime(ledger.date)
    for _, fill in ledger.iterrows():
        if (
            fill.event_id not in lookup
            or fill.date <= lookup[fill.event_id]["signal_date"]
            or fill.date > execution_date
        ):
            raise ValueError("Unknown event or invalid actual fill date")
        if not math.isfinite(fill.debit) or fill.debit <= 0:
            raise ValueError("Invalid fill debit")
        lookup[fill.event_id]["executed"] += fill.debit
    if any(e["executed"] > e["target"] + 0.01 for e in events):
        raise ValueError("Actual fills exceed event targets")
    spent = float(ledger.debit.sum())
    monthly = ledger.groupby(ledger.date.dt.to_period("M")).debit.sum()
    if (
        spent > config.tactical_budget + 0.01
        or (monthly > config.monthly_tactical_cap + 0.01).any()
    ):
        raise ValueError("Actual ledger violates tactical limits")
    month_spent = float(monthly.get(execution_date.to_period("M"), 0))
    due = sum(
        e["target"] - e["executed"] for e in events if e["signal_date"] < execution_date
    )
    available = min(cash, max(0.0, cash + bonds - config.reserve))
    limits = {
        "待买额度": due,
        "存量转仓预算": stock_remaining,
        "安全资金底线": available,
        "整个转仓期战术上限": max(0.0, config.tactical_budget - spent),
        "单月战术上限": max(0.0, config.monthly_tactical_cap - month_spent),
        "产品当日限购": product_cap,
    }
    reasons = []
    end = (plan_start.to_period("M") + config.months - 1).end_time.normalize()
    if execution_date > end:
        limits["转仓期限结束，须明确重新划拨战术资金"] = 0.0
    if execution_date <= ndx.index[-1]:
        limits["正式收盘信号必须在后续交易日执行"] = 0.0
    if spent >= config.tactical_budget - 0.01:
        reasons.append("战术资金池已经用完；创新高不会补充预算")
    if execution_date > end:
        reasons.append("九个月转仓已结束；新周期须明确重新划拨战术资金")
    amount = max(0.0, min(limits.values()))
    for name, limit in limits.items():
        if limit < due - 0.01 or (due <= 0.01 and name == "待买额度"):
            reasons.append(f"{name}: {limit:,.2f}元")
    untriggered = [t for t in config.thresholds if t not in state.fired]
    return dict(
        as_of=ndx.index[-1],
        close=float(ndx.iloc[-1]),
        high=state.high,
        drawdown=1 - float(ndx.iloc[-1]) / state.high,
        cycle=state.cycle,
        triggered=sorted(state.fired),
        cumulative_target=sum(
            e["raw_target"] for e in events if e["cycle"] == state.cycle
        ),
        executed=spent,
        pending=sum(e["target"] - e["executed"] for e in events),
        should_buy=amount,
        available=available,
        reserve_balance=cash + bonds,
        next_trigger_price=state.high * (1 - min(untriggered)) if untriggered else None,
        reasons=reasons or ["全部明确资金约束允许执行；成交仍须遵守所选产品交易时点"],
        events=pd.DataFrame(events),
    )
