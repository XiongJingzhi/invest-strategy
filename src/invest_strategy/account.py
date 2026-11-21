"""V2.1 daily account engine. Pure deterministic accounting, no network or UI."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from .models import AccountConfig, AccountResult, ExecutionPolicy
from .performance import account_metrics
from .valuation import historical_q, multiplier


@dataclass
class DrawdownState:
    high: float
    cycle: int = 0
    fired: set[float] = field(default_factory=set)

    def observe(self, close: float, date, thresholds, amounts, factor=1.0):
        if not math.isfinite(close) or close <= 0:
            raise ValueError("NDX close must be positive")
        if close > self.high:
            self.high, self.cycle, self.fired = close, self.cycle + 1, set()
        drawdown = 1 - close / self.high
        events = []
        for threshold, amount in zip(thresholds, amounts):
            if drawdown + 1e-12 >= threshold and threshold not in self.fired:
                self.fired.add(threshold)
                events.append(
                    dict(
                        event_id=f"{self.cycle}:{pd.Timestamp(date).isoformat()}:{threshold:.8f}",
                        cycle=self.cycle,
                        signal_date=pd.Timestamp(date),
                        threshold=threshold,
                        base_amount=amount,
                        multiplier=factor,
                        target=amount * factor,
                        executed=0.0,
                    )
                )
        return events


def validate_market(market, assets):
    frame = market.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
        raise ValueError("Market index must contain timezone-naive session dates")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Market dates must be unique and increasing")
    if not {"ndx", *assets}.issubset(frame.columns):
        raise ValueError("Missing NDX or CNY adjusted asset prices")
    for col in ["ndx", *assets]:
        values = frame[col].dropna().astype(float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(f"Invalid prices: {col}")
    return frame


def run_account(
    market: pd.DataFrame,
    start,
    end,
    config=None,
    strategy="C",
    policy=None,
    valuations=None,
) -> AccountResult:
    config = config if config is not None else AccountConfig()
    policy = policy if policy is not None else ExecutionPolicy()
    if strategy not in "ABCDEF" or len(strategy) != 1:
        raise ValueError("Unknown strategy")
    assets = list(config.weights)
    if (
        "equity" not in assets
        or any(w < 0 for w in config.weights.values())
        or not math.isclose(sum(config.weights.values()), 1)
    ):
        raise ValueError("Weights must sum to one and include equity")
    values = [
        config.initial_total,
        config.cash,
        config.bonds,
        config.reserve,
        config.monthly,
        config.tactical_budget,
        config.monthly_tactical_cap,
        *config.holdings.values(),
        *config.weights.values(),
    ]
    if any(not math.isfinite(v) or v < 0 for v in values) or config.months < 1:
        raise ValueError("Invalid account balances or horizon")
    if not set(config.holdings).issubset(assets):
        raise ValueError("Initial holdings must be included in configured assets")
    if len(config.thresholds) != len(config.amounts) or sorted(
        set(config.thresholds)
    ) != list(config.thresholds):
        raise ValueError("Thresholds must be distinct, increasing and match amounts")
    if any(not 0 < t < 1 for t in config.thresholds) or any(
        not math.isfinite(a) or a < 0 for a in config.amounts
    ):
        raise ValueError("Invalid drawdown ladder")
    if (
        not 0 <= policy.slippage < 1
        or any(not 0 <= f < 1 for f in policy.fees.values())
        or any(not math.isfinite(c) or c < 0 for c in policy.daily_caps.values())
    ):
        raise ValueError("Invalid execution policy")
    frame = validate_market(market, assets)
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    warmup = frame.loc[frame.index < start, "ndx"].dropna()
    if len(warmup) < 252:
        raise ValueError("At least 252 valid pre-start NDX closes required")
    period = frame.loc[start:end]
    if period.empty:
        raise ValueError("No backtest sessions")
    marks = frame.loc[frame.index < period.index[0], assets].ffill().iloc[-1]
    if pd.isna(pd.Series(marks)).any():
        raise ValueError("No initial asset marks; cannot backfill before inception")
    marks = marks.to_dict()
    units = {a: float(config.holdings.get(a, 0)) for a in assets}
    if not math.isclose(
        config.cash + config.bonds + sum(units[a] * marks[a] for a in assets),
        config.initial_total,
        abs_tol=0.01,
    ):
        raise ValueError(
            "Initial total does not reconcile with cash, bonds and holdings"
        )
    cash = config.cash
    # Bonds are reserves, not implicitly liquidated. B is an initial cash sub-ledger.
    budget = min(cash, max(0.0, cash + config.bonds - config.reserve))
    remaining, new_cash, tactical_spent, stock_spent = budget, 0.0, 0.0, 0.0
    state = DrawdownState(float(warmup.max()))
    thresholds, amounts = config.thresholds, config.amounts
    if strategy == "D":
        thresholds, amounts = (0.15, 0.25, 0.35), (config.tactical_budget / 3,) * 3
    events, trades, rows = [], [], []
    seen_months, month_tactical = set(), {}
    pending_regular = {a: {"stock": 0.0, "new": 0.0} for a in assets}
    first_month = period.index[0].to_period("M")
    transfer_end = (first_month + config.months - 1).end_time.normalize()
    calendar = xcals.get_calendar(
        "XNYS",
        start=period.index[0] - pd.Timedelta(days=10),
        end=transfer_end + pd.Timedelta(days=10),
    )
    transfer_dates = calendar.sessions_in_range(
        period.index[0], transfer_end
    ).tz_localize(None)
    daily_amount = budget / len(transfer_dates) if len(transfer_dates) else budget
    previous_total = config.initial_total
    previous_risk = config.initial_total - config.reserve
    nav, risk_nav = 1.0, 1.0
    for record in period.itertuples(name=None):
        date = record[0]
        bar = dict(zip(period.columns, record[1:]))
        month = date.to_period("M")
        mi = month.ordinal - first_month.ordinal
        external = 0.0
        first_of_month = month not in seen_months
        if first_of_month:
            seen_months.add(month)
            # Monthly deposits start in the next calendar month; initial account is explicit.
            if month != first_month:
                external = config.monthly
                cash += external
                new_cash += external
        month_tactical.setdefault(month, 0.0)
        allocation_values = {a: units[a] * marks[a] for a in assets}
        for a in assets:
            if pd.notna(bar[a]):
                marks[a] = float(bar[a])
        used = {a: 0.0 for a in assets}

        def buy(asset, requested, kind, event=None):
            nonlocal cash, remaining, new_cash, stock_spent, tactical_spent
            price = bar[asset]
            if pd.isna(price) or date < pd.Timestamp(
                policy.inception.get(asset, "1900-01-01")
            ):
                return 0.0
            day_cap = bar.get(
                f"{asset}_cap", policy.daily_caps.get(asset, float("inf"))
            )
            fee_rate = bar.get(f"{asset}_fee", policy.fees.get(asset, 0.0))
            if (
                pd.isna(day_cap)
                or day_cap < 0
                or not math.isfinite(fee_rate)
                or not 0 <= fee_rate < 1
            ):
                return 0.0  # Unknown/invalid dated execution terms cannot grant a fill.
            day_cap = min(day_cap, policy.daily_caps.get(asset, float("inf")))
            source = new_cash if kind == "new" else remaining
            available = min(cash, max(0.0, cash + config.bonds - config.reserve))
            debit = max(
                0.0,
                min(
                    requested,
                    source,
                    available,
                    day_cap - used[asset],
                ),
            )
            if debit < 1e-8:
                return 0.0
            premium = bar.get(f"{asset}_premium", 0.0)
            if pd.isna(premium) or premium <= -1:
                return 0.0
            fee = debit * fee_rate
            execution_price = float(price) * (1 + policy.slippage) * (1 + premium)
            qty = (debit - fee) / execution_price
            units[asset] += qty
            # Planned allocation uses prior-close values plus known cash debits, not today's final price.
            allocation_values[asset] += debit - fee
            cash -= debit
            used[asset] += debit
            if kind == "new":
                new_cash -= debit
            else:
                remaining -= debit
                stock_spent += debit
            if kind == "tactical":
                tactical_spent += debit
                month_tactical[month] += debit
                event["executed"] += debit
            trades.append(
                dict(
                    date=date,
                    asset=asset,
                    kind=kind,
                    debit=debit,
                    units=qty,
                    mark=float(price),
                    execution_price=execution_price,
                    fee=fee,
                    friction=debit - qty * float(price),
                    event_id=event["event_id"] if event else None,
                    signal_date=event["signal_date"] if event else pd.NaT,
                )
            )
            return debit

        # Existing close-confirmed signals execute before ordinary scheduled purchases.
        for event in events:
            if date > event["signal_date"] and mi < config.months:
                buy(
                    "equity",
                    min(
                        event["target"] - event["executed"],
                        config.tactical_budget - tactical_spent,
                        config.monthly_tactical_cap - month_tactical[month],
                    ),
                    "tactical",
                    event,
                )
        # Cancel and recompute ordinary queue from cumulative B spending: no double budget.
        for a in assets:
            pending_regular[a]["stock"] = 0.0
        if strategy == "A":
            stock_due = remaining
        elif strategy == "E":
            elapsed = int((transfer_dates <= date).sum())
            stock_due = max(0.0, min(budget, elapsed * daily_amount) - stock_spent)
            if date > transfer_end:
                stock_due = remaining
        else:
            stock_due = max(
                0.0, budget * min(mi + 1, config.months) / config.months - stock_spent
            )

        # Allocate fresh due amounts by target deficits, accounting for existing holdings.
        def allocate(amount, source):
            current = allocation_values.copy()
            total = sum(current.values()) + amount
            deficits = {
                a: max(0.0, total * config.weights[a] - current[a]) for a in assets
            }
            denominator = sum(deficits.values())
            for a in assets:
                pending_regular[a][source] = (
                    amount * deficits[a] / denominator
                    if denominator
                    else amount * config.weights[a]
                )

        allocate(min(stock_due, remaining), "stock")
        allocate(new_cash, "new")
        for a in assets:
            for source in ("stock", "new"):
                pending_regular[a][source] -= buy(a, pending_regular[a][source], source)
        # Observe today's NDX only AFTER execution. F requires valid vintage data on every signal session.
        q = None
        if strategy == "F" and pd.notna(bar["ndx"]):
            signal_time = date.tz_localize("America/New_York") + pd.Timedelta(hours=16)
            q = historical_q(valuations, signal_time)
        if pd.notna(bar["ndx"]):
            fresh = state.observe(
                float(bar["ndx"]),
                date,
                thresholds,
                amounts,
                multiplier(q) if q else 1.0,
            )
            if strategy in "CDF":
                for event in fresh:
                    event["raw_target"] = event["target"]
                    authorized = (
                        max(
                            0.0,
                            config.tactical_budget - sum(e["target"] for e in events),
                        )
                        if mi < config.months
                        else 0.0
                    )
                    event["target"] = min(event["target"], authorized)
                    event["constraint"] = (
                        "TRANSFER_CLOSED"
                        if mi >= config.months
                        else "TACTICAL_POOL"
                        if event["target"] < event["raw_target"]
                        else ""
                    )
                    events.append(event)
        total = cash + config.bonds + sum(units[a] * marks[a] for a in assets)
        risk = total - config.reserve
        daily_return = (
            total / (previous_total + external) - 1
            if previous_total + external > 0
            else 0.0
        )
        risk_return = (
            risk / (previous_risk + external) - 1
            if previous_risk + external > 0
            else 0.0
        )
        nav *= 1 + daily_return
        risk_nav *= 1 + risk_return
        pending = sum(max(0.0, e["target"] - e["executed"]) for e in events)
        rows.append(
            dict(
                date=date,
                total=total,
                risk_value=risk,
                cash=cash,
                bonds=config.bonds,
                reserve_balance=cash + config.bonds,
                external=external,
                stock_remaining=remaining,
                stock_spent=stock_spent,
                new_remaining=new_cash,
                tactical_spent=tactical_spent,
                pending_tactical=pending,
                pending_regular=sum(sum(v.values()) for v in pending_regular.values()),
                tactical_executable=min(
                    pending,
                    remaining,
                    max(0.0, cash + config.bonds - config.reserve),
                    max(0.0, config.tactical_budget - tactical_spent),
                    max(0.0, config.monthly_tactical_cap - month_tactical[month]),
                )
                if mi < config.months
                else 0.0,
                ndx=bar["ndx"],
                high=state.high,
                drawdown=1 - float(bar["ndx"]) / state.high
                if pd.notna(bar["ndx"])
                else np.nan,
                nav=nav,
                risk_nav=risk_nav,
                daily_return=daily_return,
                risk_return=risk_return,
                q=q,
                **{f"units_{a}": units[a] for a in assets},
            )
        )
        if cash < -1e-6 or remaining < -1e-6 or new_cash < -1e-6:
            raise AssertionError("Negative account budget")
        previous_total, previous_risk = total, risk
    daily = pd.DataFrame(rows).set_index("date")
    trade_frame = pd.DataFrame(
        trades,
        columns=[
            "date",
            "asset",
            "kind",
            "debit",
            "units",
            "mark",
            "execution_price",
            "fee",
            "friction",
            "event_id",
            "signal_date",
        ],
    )
    event_frame = pd.DataFrame(
        events,
        columns=[
            "event_id",
            "cycle",
            "signal_date",
            "threshold",
            "base_amount",
            "multiplier",
            "target",
            "executed",
            "raw_target",
            "constraint",
        ],
    )
    return AccountResult(
        daily,
        trade_frame,
        event_frame,
        account_metrics(daily, trade_frame, event_frame, config),
        config,
        strategy,
    )
