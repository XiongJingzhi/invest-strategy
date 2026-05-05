from __future__ import annotations

import pandas as pd

from .models import AssetProfile, StrategySignal, ValuationInput


def evaluate_strategy(
    prices: pd.DataFrame,
    profile: AssetProfile,
    valuation: ValuationInput | None = None,
) -> StrategySignal:
    if prices.empty:
        raise ValueError("prices cannot be empty")

    valuation = valuation or ValuationInput()
    frame = _normalized_prices(prices)
    current_price = float(frame["close"].iloc[-1])
    peak_price = float(frame["close"].max())
    drawdown_pct = round((current_price / peak_price - 1) * 100, 2) if peak_price else 0.0
    ma_deviation_pct = _ma_deviation(frame, profile.trend_ma_days)
    signal = StrategySignal(drawdown_pct=drawdown_pct, ma_deviation_pct=ma_deviation_pct)

    _apply_drawdown_rules(signal, profile)
    _apply_ma_rules(signal, profile)
    _apply_valuation_hint(signal, profile, valuation)

    if not signal.reasons:
        signal.reasons.append("价格处于常规区间")

    return signal


def _normalized_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if "close" not in prices.columns:
        raise ValueError("prices must include a close column")
    frame = prices.copy()
    frame = frame.sort_values("date") if "date" in frame.columns else frame
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["close"])
    if frame.empty:
        raise ValueError("prices contains no valid close values")
    return frame


def _ma_deviation(frame: pd.DataFrame, days: int) -> float | None:
    if len(frame) < 2:
        return None
    window = min(days, len(frame))
    moving_average = float(frame["close"].tail(window).mean())
    if moving_average == 0:
        return None
    current_price = float(frame["close"].iloc[-1])
    return round((current_price / moving_average - 1) * 100, 2)


def _apply_drawdown_rules(signal: StrategySignal, profile: AssetProfile) -> None:
    if signal.drawdown_pct is None:
        return
    for rule in sorted(profile.drawdown_rules, key=lambda item: item.threshold_pct):
        if signal.drawdown_pct <= rule.threshold_pct:
            signal.multiplier = max(signal.multiplier, rule.multiplier)
            signal.action = rule.action
            signal.reasons.append(f"从高点回撤 {abs(signal.drawdown_pct):.1f}%")
            return


def _apply_ma_rules(signal: StrategySignal, profile: AssetProfile) -> None:
    if signal.ma_deviation_pct is None:
        return

    lower_rules = sorted(
        [rule for rule in profile.ma_rules if rule.threshold_pct < 0],
        key=lambda item: item.threshold_pct,
    )
    for rule in lower_rules:
        if signal.ma_deviation_pct <= rule.threshold_pct:
            signal.multiplier = max(signal.multiplier, rule.multiplier)
            signal.action = rule.action
            signal.allow_elastic_buy = rule.allow_elastic_buy
            signal.reasons.append(
                f"低于 MA{profile.trend_ma_days} {abs(signal.ma_deviation_pct):.1f}%"
            )
            return

    upper_rules = sorted(
        [rule for rule in profile.ma_rules if rule.threshold_pct > 0],
        key=lambda item: item.threshold_pct,
        reverse=True,
    )
    for rule in upper_rules:
        if signal.ma_deviation_pct >= rule.threshold_pct:
            signal.multiplier = rule.multiplier
            signal.action = rule.action
            signal.allow_elastic_buy = rule.allow_elastic_buy
            signal.reasons.append(
                f"高于 MA{profile.trend_ma_days} {signal.ma_deviation_pct:.1f}%"
            )
            return


def _apply_valuation_hint(
    signal: StrategySignal,
    profile: AssetProfile,
    valuation: ValuationInput,
) -> None:
    values = [
        value
        for value in (
            valuation.dividend_percentile,
            valuation.pb_percentile,
            valuation.pe_percentile,
        )
        if value is not None
    ]
    if not values:
        return

    score = round(sum(values) / len(values), 2)
    signal.valuation_score = score
    if profile.key == "low_vol_dividend":
        if valuation.dividend_percentile is not None and valuation.dividend_percentile >= 70:
            signal.multiplier = max(signal.multiplier, 1.5)
            signal.action = "股息率高位加仓"
            signal.reasons.append(f"股息率分位 {valuation.dividend_percentile:.0f}%")
        elif score <= 25:
            signal.allow_elastic_buy = False
            signal.reasons.append(f"估值分位偏低吸引力不足 {score:.0f}%")
    elif score >= 90:
        signal.allow_elastic_buy = False
        signal.reasons.append(f"估值分位偏高 {score:.0f}%，只控制弹性层")
