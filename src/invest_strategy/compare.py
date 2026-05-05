from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .backtest import run_backtest
from .models import AssetProfile, ValuationInput
from .profiles import get_profile_strategy_rows


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
                "组合规则": _profile_rules_text(profile),
                "策略参数": _profile_params_text(profile),
                "投入份额": round(float(result.monthly.iloc[-1]["shares"]), 4),
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


def _profile_rules_text(profile: AssetProfile) -> str:
    rules = []
    for row in get_profile_strategy_rows(profile):
        if row.get("状态") == "停用":
            continue
        strategy = row.get("策略", "")
        condition = row.get("触发条件", "")
        action = row.get("动作", "")
        multiplier = row.get("买入倍数", "")
        rules.append(f"{strategy}: {condition} -> {action} / {multiplier}")
    return "；".join(rules)


def _profile_params_text(profile: AssetProfile) -> str:
    parts = []
    for component in sorted(profile.strategy_components, key=lambda item: item.priority):
        if not component.enabled:
            continue
        params = component.params
        if component.component_type == "fixed_contribution":
            parts.append(f"{component.display_name}: 固定层权重={params.get('weight', 0)}")
        elif component.component_type == "drawdown_add":
            rules = [
                f"{rule.get('threshold_pct')}%->{rule.get('multiplier')}x/{rule.get('action')}"
                for rule in params.get("rules", [])
            ]
            parts.append(f"{component.display_name}: " + ", ".join(rules))
        elif component.component_type == "ma_deviation":
            rules = [
                f"{rule.get('threshold_pct')}%->{rule.get('multiplier')}x/{rule.get('action')}"
                for rule in params.get("rules", [])
            ]
            parts.append(
                f"{component.display_name}: MA={params.get('ma_days', profile.trend_ma_days)}, "
                + ", ".join(rules)
            )
        elif component.component_type == "dividend_yield":
            parts.append(
                f"{component.display_name}: 分位>={params.get('high_percentile', 70)}%, "
                f"倍数={params.get('multiplier', 1.5)}"
            )
        elif component.component_type == "valuation_guard":
            parts.append(
                f"{component.display_name}: 高估分位>={params.get('high_percentile', 90)}%"
            )
    return "；".join(parts)
