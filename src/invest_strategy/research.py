"""Overlapping historical events and monthly-start cohorts; no inference of independence."""

from dataclasses import replace

import pandas as pd

from .account import DrawdownState
from .compare import compare_accounts


def event_study(
    market, start, end=None, thresholds=(0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5)
):
    """Return in CNY adjusted equity proxy from NEXT observed session close.

    Baseline: unconditional entries on all eligible sessions, same calendar horizon.
    Missing end horizons are right-censored and excluded, never shortened.
    """
    frame = market.loc[:end].copy() if end else market.copy()
    warm = frame.loc[frame.index < pd.Timestamp(start), "ndx"].dropna()
    if len(warm) < 252:
        raise ValueError("252 pre-start NDX observations required")
    state = DrawdownState(float(warm.max()))
    prices = frame.equity.dropna()
    rows = []
    for date, bar in frame.loc[start:].iterrows():
        if pd.isna(bar.ndx):
            continue
        for event in state.observe(
            float(bar.ndx), date, thresholds, (0,) * len(thresholds)
        ):
            entries = prices.loc[prices.index > date]
            if entries.empty:
                continue
            entry = entries.index[0]
            for months in (1, 3, 6, 12, 36, 60):
                exits = prices.loc[prices.index >= entry + pd.DateOffset(months=months)]
                if exits.empty:
                    continue
                exit_date = exits.index[0]
                ret = float(exits.iloc[0] / prices.loc[entry] - 1)
                rows.append(
                    {
                        **event,
                        "entry": entry,
                        "exit": exit_date,
                        "months": months,
                        "return": ret,
                    }
                )
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame()
    baseline = {}
    for months in detail.months.unique():
        vals = []
        for entry, price in prices.loc[start:].items():
            idx = prices.index.searchsorted(entry + pd.DateOffset(months=int(months)))
            if idx < len(prices):
                vals.append(prices.iloc[idx] / price - 1)
        baseline[months] = float(pd.Series(vals).mean())
    summary = (
        detail.groupby(["threshold", "months"])
        .agg(
            samples=("return", "size"),
            mean=("return", "mean"),
            median=("return", "median"),
            positive_probability=("return", lambda x: (x > 0).mean()),
            maximum_loss=("return", "min"),
            worst_5pct=("return", lambda x: x.quantile(0.05)),
        )
        .reset_index()
    )
    summary["unconditional_mean"] = summary.months.map(baseline)
    summary["excess_vs_unconditional"] = summary["mean"] - summary.unconditional_mean
    summary["overlapping_correlated_samples"] = True
    return detail, summary


def rolling_accounts(
    market,
    start,
    end,
    config,
    horizons=(1, 3, 5, 10),
    policy=None,
    valuations=None,
    progress=None,
    resume=None,
):
    """Prefixes of one longest run are exact cohorts (engine has prefix-invariance tests)."""
    from .performance import account_metrics

    frame = market.loc[start:end]
    starts = frame.groupby(frame.index.to_period("M")).head(1).index
    if resume is not None:
        resume = resume.copy()
        for column in ("start", "end"):
            resume[column] = pd.to_datetime(resume[column], format="mixed")
    rows = [] if resume is None else resume.to_dict("records")
    completed = set() if resume is None else set(resume.start)
    for begin in starts:
        if begin in completed:
            continue
        valid = [
            years
            for years in horizons
            if begin + pd.DateOffset(years=years) <= frame.index[-1]
        ]
        if not valid:
            continue
        marks = market.loc[market.index < begin, list(config.weights)].ffill().iloc[-1]
        total = (
            config.cash
            + config.bonds
            + sum(config.holdings.get(a, 0) * marks[a] for a in config.weights)
        )
        cohort = replace(config, initial_total=total)
        longest = begin + pd.DateOffset(years=max(valid))
        unavailable, full = compare_accounts(
            market, begin, longest, cohort, policy, valuations
        )
        for years in valid:
            finish = begin + pd.DateOffset(years=years)
            metrics = {}
            for strategy in "ABCDEF":
                if strategy not in full:
                    if strategy == "F" and valuations is not None:
                        short_summary, short = compare_accounts(
                            market, begin, finish, cohort, policy, valuations
                        )
                        if strategy in short:
                            metrics[strategy] = {
                                "status": "OK",
                                **short[strategy].metrics,
                            }
                            continue
                    metrics[strategy] = {"status": unavailable.loc[strategy, "status"]}
                    continue
                result = full[strategy]
                daily = result.daily.loc[:finish]
                trades = result.trades[result.trades.date <= finish]
                events = result.events[result.events.signal_date <= finish].copy()
                executed = (
                    trades[trades.kind == "tactical"].groupby("event_id").debit.sum()
                )
                events["executed"] = events.event_id.map(executed).fillna(0.0)
                metrics[strategy] = {
                    "status": "OK",
                    **account_metrics(daily, trades, events, cohort),
                }
            for strategy, row in metrics.items():
                if row["status"] == "OK":
                    row["profit_vs_A"] = (
                        row["final_total"] - metrics["A"]["final_total"]
                    )
                    row["profit_vs_B"] = (
                        row["final_total"] - metrics["B"]["final_total"]
                    )
                    row["cash_drag_vs_A"] = -row["profit_vs_A"]
                rows.append(
                    {
                        "start": begin,
                        "end": finish,
                        "years": years,
                        "strategy": strategy,
                        **row,
                    }
                )
        if progress is not None:
            progress(begin, rows)
    return pd.DataFrame(rows)
