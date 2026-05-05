from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .backtest import run_backtest
from .models import AssetProfile, ValuationInput


@dataclass(frozen=True)
class StrategyComparison:
    summary: pd.DataFrame
    equity_curve: pd.DataFrame


def compare_profiles(
    prices: pd.DataFrame,
    profiles: list[AssetProfile] | tuple[AssetProfile, ...],
    monthly_contribution: float,
    valuation: ValuationInput | None = None,
) -> StrategyComparison:
    summary_rows: list[dict[str, object]] = []
    curve_frames: list[pd.DataFrame] = []

    for profile in profiles:
        result = run_backtest(prices, profile, monthly_contribution, valuation)
        summary_rows.append(
            {
                "策略组合": profile.display_name,
                "累计投入": result.summary.total_invested,
                "期末市值": result.summary.final_value,
                "总收益率": result.summary.total_return_pct,
                "年化回报率": result.summary.annualized_return_pct,
                "组合最大回撤": result.summary.max_drawdown_pct,
            }
        )

        curve = result.monthly[["date", "value"]].copy()
        curve["策略组合"] = profile.display_name
        curve = curve.rename(columns={"date": "日期", "value": "组合市值"})
        curve_frames.append(curve)

    summary = pd.DataFrame(summary_rows)
    equity_curve = (
        pd.concat(curve_frames, ignore_index=True)
        if curve_frames
        else pd.DataFrame(columns=["日期", "组合市值", "策略组合"])
    )
    return StrategyComparison(summary=summary, equity_curve=equity_curve)
