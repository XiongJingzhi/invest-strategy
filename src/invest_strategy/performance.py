"""Cash-flow adjusted performance. Undefined measures return None, never invented zeros."""

import numpy as np
import pandas as pd


def xirr(dates, flows):
    years = np.array(
        [(pd.Timestamp(d) - pd.Timestamp(dates[0])).days / 365.25 for d in dates]
    )
    amounts = np.asarray(flows, dtype=float)
    if not (np.any(amounts > 0) and np.any(amounts < 0)) or years.max() <= 0:
        return None

    def value(log_rate):
        return float(np.sum(amounts * np.exp(np.clip(-log_rate * years, -700, 700))))

    lo, hi = -20.0, 20.0
    if value(lo) * value(hi) > 0:
        return None
    for _ in range(100):
        if hi - lo < 1e-12:
            break
        mid = (lo + hi) / 2
        if value(lo) * value(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return float(np.expm1((lo + hi) / 2))


def risk_metrics(nav, returns):
    # Include the initial NAV=1, so an immediate fee/loss is a drawdown.
    high = nav.cummax().clip(lower=1.0)
    dd = nav / high - 1
    underwater = dd < -1e-10
    durations, begin = [], None
    last_peak = nav.index[0]
    for date, down in underwater.items():
        if down and begin is None:
            begin = last_peak
        if not down and begin is not None:
            durations.append((date - begin).days)
            begin = None
        if not down:
            last_peak = date
    if begin is not None:
        durations.append((nav.index[-1] - begin).days)
    std = returns.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(returns, 0) ** 2))
    rolling = nav.pct_change(252).dropna()
    return dict(
        max_drawdown=float(dd.min()),
        max_drawdown_duration_days=max(durations, default=0),
        recovery_time_days=max(durations, default=0),
        recovery_censored=bool(underwater.iloc[-1]),
        annual_volatility=float(std * np.sqrt(252)) if len(returns) > 1 else None,
        sharpe=float(returns.mean() / std * np.sqrt(252)) if std > 0 else None,
        sortino=float(returns.mean() / downside * np.sqrt(252))
        if downside > 0
        else None,
        worst_rolling_1y=float(rolling.min()) if len(rolling) else None,
    )


def account_metrics(daily, trades, events, config):
    final = daily.iloc[-1]
    dates = [daily.index[0], *daily.index, daily.index[-1]]
    flows = [-config.initial_total, *(-daily.external).tolist(), final.total]
    risk_initial = config.initial_total - config.reserve
    risk_flows = [-risk_initial, *(-daily.external).tolist(), final.risk_value]
    tactical = trades[trades.kind == "tactical"]
    funded_events = events[events.target > 0]
    days = (daily.index[-1] - daily.index[0]).days
    # Actual asset CAGR is undefined for a contributed account; annualized TWR is separate.
    result = dict(
        final_total=float(final.total),
        final_risk_value=float(final.risk_value),
        net_profit=float(final.total - config.initial_total - daily.external.sum()),
        twr=float(final.nav - 1),
        risk_twr=float(final.risk_nav - 1),
        xirr=xirr(dates, flows),
        risk_xirr=xirr(dates, risk_flows) if risk_initial > 0 else None,
        cagr=float((final.total / config.initial_total) ** (365.25 / days) - 1)
        if days > 0 and daily.external.sum() == 0 and config.initial_total > 0
        else None,
        annualized_twr=float(final.nav ** (365.25 / days) - 1) if days > 0 else None,
        invested=float(trades.debit.sum()),
        external_total=float(daily.external.sum()),
        average_cash_ratio=float((daily.cash / daily.total).mean()),
        utilization=float(
            trades.debit.sum()
            / (
                max(0.0, config.cash + config.bonds - config.reserve)
                + daily.external.sum()
            )
        )
        if config.cash + config.bonds - config.reserve + daily.external.sum() > 0
        else None,
        triggers=len(events),
        execution_success=float(
            (funded_events.executed >= funded_events.target - 1e-6).mean()
        )
        if len(funded_events)
        else None,
        tactical_average_cost=float(tactical.debit.sum() / tactical.units.sum())
        if tactical.units.sum() > 0
        else None,
        fees=float(trades.fee.sum()),
        friction=float(trades.friction.sum()),
        unfilled_orders=int((events.executed < events.target - 1e-6).sum()),
        pending_tactical=float(final.pending_tactical),
    )
    result.update(risk_metrics(daily.nav, daily.daily_return))
    result.update(
        {
            "risk_" + k: v
            for k, v in risk_metrics(daily.risk_nav, daily.risk_return).items()
        }
    )
    return result
