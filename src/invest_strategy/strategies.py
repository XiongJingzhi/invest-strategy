from __future__ import annotations

import pandas as pd

from .models import AssetProfile, DrawdownRule, MaRule, StrategyComponent, StrategySignal, ValuationInput


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
    ma_days = _ma_days(profile)
    ma_deviation_pct = _ma_deviation(frame, ma_days)
    fixed_layer_weight = _fixed_layer_weight(profile)
    signal = StrategySignal(
        multiplier=fixed_layer_weight,
        drawdown_pct=drawdown_pct,
        ma_deviation_pct=ma_deviation_pct,
    )

    if profile.strategy_components:
        _apply_components(signal, profile, valuation, ma_days, fixed_layer_weight)
    else:
        _apply_drawdown_rules(signal, profile.drawdown_rules)
        _apply_ma_rules(signal, profile.ma_rules, ma_days, fixed_layer_weight)
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


def _fixed_layer_weight(profile: AssetProfile) -> float:
    component = _component(profile, "fixed_contribution")
    if component is None:
        return profile.fixed_layer_weight
    if not component.enabled:
        return 0.0
    return float(component.params.get("weight", profile.fixed_layer_weight))


def _ma_days(profile: AssetProfile) -> int:
    component = _component(profile, "ma_deviation")
    if component is None:
        return profile.trend_ma_days
    return int(component.params.get("ma_days", profile.trend_ma_days))


def _component(profile: AssetProfile, key: str) -> StrategyComponent | None:
    return next((item for item in profile.strategy_components if item.key == key), None)


def _apply_components(
    signal: StrategySignal,
    profile: AssetProfile,
    valuation: ValuationInput,
    ma_days: int,
    fixed_layer_weight: float,
) -> None:
    has_valuation_component = False
    for component in sorted(profile.strategy_components, key=lambda item: item.priority):
        if not component.enabled:
            continue
        if component.component_type == "drawdown_add":
            _apply_drawdown_rules(signal, _drawdown_rules(component))
        elif component.component_type == "ma_deviation":
            _apply_ma_rules(signal, _ma_rules(component), ma_days, fixed_layer_weight)
        elif component.component_type == "dividend_yield":
            has_valuation_component = True
            _apply_dividend_component(signal, component, valuation)
        elif component.component_type == "valuation_guard":
            has_valuation_component = True
            _apply_valuation_component(signal, component, valuation)

    if not has_valuation_component:
        _apply_valuation_hint(signal, profile, valuation)


def _drawdown_rules(component: StrategyComponent) -> tuple[DrawdownRule, ...]:
    return tuple(
        DrawdownRule(
            threshold_pct=float(rule["threshold_pct"]),
            multiplier=float(rule["multiplier"]),
            action=str(rule["action"]),
        )
        for rule in component.params.get("rules", [])
    )


def _ma_rules(component: StrategyComponent) -> tuple[MaRule, ...]:
    return tuple(
        MaRule(
            threshold_pct=float(rule["threshold_pct"]),
            multiplier=float(rule["multiplier"]),
            action=str(rule["action"]),
            allow_elastic_buy=bool(rule.get("allow_elastic_buy", True)),
        )
        for rule in component.params.get("rules", [])
    )


def _apply_drawdown_rules(signal: StrategySignal, rules: tuple[DrawdownRule, ...]) -> None:
    if signal.drawdown_pct is None:
        return
    for rule in sorted(rules, key=lambda item: item.threshold_pct):
        if signal.drawdown_pct <= rule.threshold_pct:
            signal.multiplier = max(signal.multiplier, rule.multiplier)
            signal.action = rule.action
            signal.reasons.append(f"标的从高点回撤 {abs(signal.drawdown_pct):.1f}%")
            return


def _apply_ma_rules(
    signal: StrategySignal,
    rules: tuple[MaRule, ...],
    ma_days: int,
    fixed_layer_weight: float,
) -> None:
    if signal.ma_deviation_pct is None:
        return

    lower_rules = sorted(
        [rule for rule in rules if rule.threshold_pct < 0],
        key=lambda item: item.threshold_pct,
    )
    for rule in lower_rules:
        if signal.ma_deviation_pct <= rule.threshold_pct:
            signal.multiplier = max(signal.multiplier, rule.multiplier)
            signal.action = rule.action
            signal.allow_elastic_buy = rule.allow_elastic_buy
            signal.reasons.append(
                f"低于 MA{ma_days} {abs(signal.ma_deviation_pct):.1f}%"
            )
            return

    upper_rules = sorted(
        [rule for rule in rules if rule.threshold_pct > 0],
        key=lambda item: item.threshold_pct,
        reverse=True,
    )
    for rule in upper_rules:
        if signal.ma_deviation_pct >= rule.threshold_pct:
            signal.multiplier = _ma_rule_multiplier(rule, fixed_layer_weight)
            signal.action = rule.action
            signal.allow_elastic_buy = rule.allow_elastic_buy
            signal.reasons.append(
                f"高于 MA{ma_days} {signal.ma_deviation_pct:.1f}%"
            )
            return


def _ma_rule_multiplier(rule: MaRule, fixed_layer_weight: float) -> float:
    if rule.allow_elastic_buy:
        return rule.multiplier
    return min(rule.multiplier, fixed_layer_weight)


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
    signal.dividend_yield = valuation.dividend_yield
    signal.dividend_percentile = valuation.dividend_percentile
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


def _apply_dividend_component(
    signal: StrategySignal,
    component: StrategyComponent,
    valuation: ValuationInput,
) -> None:
    if valuation.dividend_percentile is None:
        return
    signal.dividend_yield = valuation.dividend_yield
    high_percentile = float(component.params.get("high_percentile", 70))
    if valuation.dividend_percentile >= high_percentile:
        multiplier = float(component.params.get("multiplier", 1.5))
        signal.multiplier = max(signal.multiplier, multiplier)
        signal.action = "股息率高位加仓"
        signal.reasons.append(f"股息率分位 {valuation.dividend_percentile:.0f}%")


def _apply_valuation_component(
    signal: StrategySignal,
    component: StrategyComponent,
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
    signal.dividend_yield = valuation.dividend_yield
    signal.dividend_percentile = valuation.dividend_percentile
    high_percentile = float(component.params.get("high_percentile", 90))
    if score >= high_percentile:
        signal.allow_elastic_buy = False
        signal.reasons.append(f"估值分位偏高 {score:.0f}%，只控制弹性层")
