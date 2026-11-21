"""Experimental five-year PE anchor; never a complete DCF or a historical data feed."""

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FairPEModel:
    growth: float = 0.10
    dividend: float = 0.005
    required_return: float = 0.10
    terminal_pe: float = 22

    def fair_pe(self) -> float:
        values = (self.growth, self.dividend, self.required_return, self.terminal_pe)
        if (
            not all(math.isfinite(v) for v in values)
            or min(values[:3]) <= -1
            or self.terminal_pe <= 0
        ):
            raise ValueError("Invalid valuation assumptions")
        return (
            self.terminal_pe
            * ((1 + self.growth) * (1 + self.dividend) / (1 + self.required_return))
            ** 5
        )


def multiplier(q: float) -> float:
    if not math.isfinite(q) or q <= 0:
        raise ValueError("Q must be positive and finite")
    return 1.25 if q <= 0.85 else 1.0 if q <= 1.15 else 0.75 if q <= 1.35 else 0.5


def historical_q(
    history: pd.DataFrame | None, when: pd.Timestamp, max_age_days=100
) -> float:
    """Rows must carry actual publication time, observation time, provenance and assumptions.

    Parameters are row-wise vintage assumptions, not today's model retrofitted to history.
    A caller is responsible for licensing, vintage authenticity and pre-registration.
    """
    required = {
        "observed_at",
        "available_at",
        "source",
        "forward_pe",
        "growth",
        "dividend",
        "required_return",
        "terminal_pe",
        "parameters_fixed_at",
    }
    if history is None or not required.issubset(history.columns):
        raise ValueError("Historical point-in-time valuation unavailable")
    h = history.copy()
    for col in ("observed_at", "available_at", "parameters_fixed_at"):
        h[col] = pd.to_datetime(h[col], utc=True)
    ts = pd.Timestamp(when)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    h = h[
        (h.available_at <= ts)
        & (h.observed_at <= h.available_at)
        & (h.parameters_fixed_at <= h.observed_at)
    ].sort_values("available_at")
    if h.empty:
        raise ValueError("Historical point-in-time valuation unavailable")
    row = h.iloc[-1]
    if (
        (ts - row.observed_at).days > max_age_days
        or not str(row.source).strip()
        or pd.isna(row.source)
    ):
        raise ValueError("Historical valuation stale or missing provenance")
    fair = FairPEModel(
        float(row.growth),
        float(row.dividend),
        float(row.required_return),
        float(row.terminal_pe),
    ).fair_pe()
    q = float(row.forward_pe) / fair
    multiplier(q)
    return q


def sensitivity(growths, returns, dividend=0.005, terminal_pe=22):
    return pd.DataFrame(
        [
            {
                "growth": g,
                "required_return": r,
                "fair_pe": FairPEModel(g, dividend, r, terminal_pe).fair_pe(),
            }
            for g in growths
            for r in returns
        ]
    )


def run_frozen_holdout(market, start, end, frozen_at, valuations, config, policy=None):
    """Explicit out-of-sample experiment with pre-registered constant model assumptions.

    Deliberately strict: changing assumptions requires a new experiment, not tuning the
    holdout. Forward PE observations may evolve with their actual publication vintages.
    """
    from .account import run_account
    from .models import ExecutionPolicy

    frozen = pd.Timestamp(frozen_at)
    if pd.Timestamp(start) <= frozen:
        raise ValueError("Holdout must start after parameter freeze")
    h = valuations.copy()
    fixed = pd.to_datetime(h["parameters_fixed_at"], utc=True)
    frozen_utc = (
        frozen.tz_localize("UTC") if frozen.tzinfo is None else frozen.tz_convert("UTC")
    )
    if (fixed > frozen_utc).any() or h[
        ["growth", "dividend", "required_return", "terminal_pe"]
    ].drop_duplicates().shape[0] != 1:
        raise ValueError("Holdout parameters were not frozen before observation")
    return run_account(market, start, end, config, "F", policy or ExecutionPolicy(), h)
