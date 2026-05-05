from __future__ import annotations

from dataclasses import replace

from .models import AssetProfile, DrawdownRule, MaRule, StrategyComponent


def get_default_profiles() -> dict[str, AssetProfile]:
    return {
        "low_vol_dividend": AssetProfile(
            key="low_vol_dividend",
            display_name="低波红利",
            role="防守 + 现金流",
            base_description="股息率/PB/PE 优先，MA120/MA250 辅助判断。",
            strategy_notes=(
                "正常情况下保持每月定投，低估时提高弹性买入。",
                "股息率处于历史高位时优先加仓，PB/PE 作为辅助确认。",
                "高于 MA120 10% 停止弹性买入，高于 20% 可减部分仓位。",
            ),
            fixed_layer_weight=1.0,
            trend_ma_days=120,
            dividend_weight=0.4,
            valuation_weight=0.3,
            partial_sell_above_ma_pct=20,
            ma_rules=(
                MaRule(-20, 3.0, "大额加仓"),
                MaRule(-10, 2.0, "明显加仓"),
                MaRule(-5, 1.5, "加倍定投"),
                MaRule(10, 0.0, "停止弹性买入", allow_elastic_buy=False),
                MaRule(20, 0.0, "明显减仓", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(1.0),
                dividend_component(weight=0.4),
                valuation_component(weight=0.3),
                ma_component(
                    ma_days=120,
                    rules=(
                        MaRule(-20, 3.0, "大额加仓"),
                        MaRule(-10, 2.0, "明显加仓"),
                        MaRule(-5, 1.5, "加倍定投"),
                        MaRule(10, 0.0, "停止弹性买入", allow_elastic_buy=False),
                        MaRule(20, 0.0, "明显减仓", allow_elastic_buy=False),
                    ),
                ),
            ),
        ),
        "sp500": AssetProfile(
            key="sp500",
            display_name="标普500",
            role="核心 + 全球权益底仓",
            base_description="固定层持续定投，回撤加仓，估值只控制弹性层。",
            strategy_notes=(
                "固定层长期不断投，不因短期估值或均线信号轻易中断。",
                "从历史高点回撤 10% 后逐级提高投入，30% 后动用现金桶。",
                "估值极高时停止弹性买入，但不轻易卖出固定仓。",
            ),
            fixed_layer_weight=1.0,
            trend_ma_days=250,
            partial_sell_above_ma_pct=None,
            valuation_weight=0.1,
            drawdown_rules=(
                DrawdownRule(-40, 4.0, "现金桶大额加仓"),
                DrawdownRule(-30, 3.0, "动用现金桶"),
                DrawdownRule(-20, 2.0, "加倍定投"),
                DrawdownRule(-10, 1.5, "提高定投"),
            ),
            strategy_components=(
                fixed_contribution_component(1.0),
                drawdown_component(
                    (
                        DrawdownRule(-40, 4.0, "现金桶大额加仓"),
                        DrawdownRule(-30, 3.0, "动用现金桶"),
                        DrawdownRule(-20, 2.0, "加倍定投"),
                        DrawdownRule(-10, 1.5, "提高定投"),
                    )
                ),
                valuation_component(weight=0.1),
            ),
        ),
        "nasdaq100": AssetProfile(
            key="nasdaq100",
            display_name="纳指100",
            role="进攻 + 科技增强",
            base_description="小额定投，深度回撤加仓，MA250 控制弹性仓。",
            strategy_notes=(
                "固定层小额持续，仓位不应超过标普500核心仓。",
                "回撤 20% 后开始加大买入，30%-40% 是重点加仓区。",
                "高于 MA250 20% 停止弹性买入，30% 以上可减部分弹性仓。",
            ),
            fixed_layer_weight=0.6,
            trend_ma_days=250,
            partial_sell_above_ma_pct=30,
            drawdown_rules=(
                DrawdownRule(-50, 4.0, "极端机会分批"),
                DrawdownRule(-40, 3.5, "大额加仓"),
                DrawdownRule(-30, 3.0, "重点加仓"),
                DrawdownRule(-20, 2.0, "加大买入"),
                DrawdownRule(-10, 1.5, "提高定投"),
            ),
            ma_rules=(
                MaRule(-20, 2.0, "好机会分批加仓"),
                MaRule(20, 1.0, "停止弹性买入", allow_elastic_buy=False),
                MaRule(30, 0.0, "减部分弹性仓", allow_elastic_buy=False),
                MaRule(40, 0.0, "严禁追涨", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(0.6),
                drawdown_component(
                    (
                        DrawdownRule(-50, 4.0, "极端机会分批"),
                        DrawdownRule(-40, 3.5, "大额加仓"),
                        DrawdownRule(-30, 3.0, "重点加仓"),
                        DrawdownRule(-20, 2.0, "加大买入"),
                        DrawdownRule(-10, 1.5, "提高定投"),
                    )
                ),
                ma_component(
                    ma_days=250,
                    rules=(
                        MaRule(-20, 2.0, "好机会分批加仓"),
                        MaRule(20, 1.0, "停止弹性买入", allow_elastic_buy=False),
                        MaRule(30, 0.0, "减部分弹性仓", allow_elastic_buy=False),
                        MaRule(40, 0.0, "严禁追涨", allow_elastic_buy=False),
                    ),
                ),
            ),
        ),
    }


def fixed_contribution_component(weight: float) -> StrategyComponent:
    return StrategyComponent(
        key="fixed_contribution",
        display_name="固定定投",
        component_type="fixed_contribution",
        priority=10,
        params={"weight": weight},
    )


def drawdown_component(rules: tuple[DrawdownRule, ...]) -> StrategyComponent:
    return StrategyComponent(
        key="drawdown_add",
        display_name="回撤加仓",
        component_type="drawdown_add",
        priority=30,
        params={"rules": [_drawdown_rule_to_dict(rule) for rule in rules]},
    )


def ma_component(ma_days: int, rules: tuple[MaRule, ...]) -> StrategyComponent:
    return StrategyComponent(
        key="ma_deviation",
        display_name="均线偏离",
        component_type="ma_deviation",
        priority=40,
        params={"ma_days": ma_days, "rules": [_ma_rule_to_dict(rule) for rule in rules]},
    )


def dividend_component(weight: float) -> StrategyComponent:
    return StrategyComponent(
        key="dividend_yield",
        display_name="股息率分位",
        component_type="dividend_yield",
        priority=20,
        params={"weight": weight, "high_percentile": 70, "multiplier": 1.5},
    )


def valuation_component(weight: float) -> StrategyComponent:
    return StrategyComponent(
        key="valuation_guard",
        display_name="PB/PE估值辅助",
        component_type="valuation_guard",
        priority=80,
        params={"weight": weight, "high_percentile": 90},
    )


def _drawdown_rule_to_dict(rule: DrawdownRule) -> dict[str, object]:
    return {
        "threshold_pct": rule.threshold_pct,
        "multiplier": rule.multiplier,
        "action": rule.action,
    }


def _ma_rule_to_dict(rule: MaRule) -> dict[str, object]:
    return {
        "threshold_pct": rule.threshold_pct,
        "multiplier": rule.multiplier,
        "action": rule.action,
        "allow_elastic_buy": rule.allow_elastic_buy,
    }


def get_profile_strategy_rows(profile: AssetProfile) -> list[dict[str, object]]:
    if profile.strategy_components:
        return get_component_strategy_rows(profile)

    rows: list[dict[str, object]] = []
    rows.append(
        {
            "策略": "固定层",
            "触发条件": "每月执行",
            "动作": f"基础定投权重 {profile.fixed_layer_weight:g}",
            "买入倍数": profile.fixed_layer_weight,
            "是否允许弹性买入": "是",
        }
    )

    for rule in sorted(profile.drawdown_rules, key=lambda item: item.threshold_pct, reverse=True):
        rows.append(
            {
                "策略": "回撤加仓",
                "触发条件": f"从历史高点回撤 <= {rule.threshold_pct:g}%",
                "动作": rule.action,
                "买入倍数": rule.multiplier,
                "是否允许弹性买入": "是",
            }
        )

    for rule in sorted(profile.ma_rules, key=lambda item: item.threshold_pct):
        direction = "低于" if rule.threshold_pct < 0 else "高于"
        rows.append(
            {
                "策略": "均线偏离",
                "触发条件": f"{direction} MA{profile.trend_ma_days} {abs(rule.threshold_pct):g}%",
                "动作": rule.action,
                "买入倍数": rule.multiplier,
                "是否允许弹性买入": "是" if rule.allow_elastic_buy else "否",
            }
        )

    if profile.dividend_weight:
        rows.append(
            {
                "策略": "股息率",
                "触发条件": f"权重 {profile.dividend_weight:.0%}，分位越高越有吸引力",
                "动作": "高股息分位加仓",
                "买入倍数": "按输入分位辅助调整",
                "是否允许弹性买入": "是",
            }
        )

    if profile.valuation_weight:
        rows.append(
            {
                "策略": "估值辅助",
                "触发条件": f"权重 {profile.valuation_weight:.0%}，PB/PE 分位辅助判断",
                "动作": "高估时控制弹性层",
                "买入倍数": "辅助信号",
                "是否允许弹性买入": "视估值而定",
            }
        )

    return rows


def get_component_strategy_rows(profile: AssetProfile) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for component in sorted(profile.strategy_components, key=lambda item: item.priority):
        status = "启用" if component.enabled else "停用"
        if component.component_type == "fixed_contribution":
            rows.append(
                {
                    "策略": component.display_name,
                    "状态": status,
                    "触发条件": "每月执行",
                    "动作": f"基础定投权重 {float(component.params.get('weight', 0)):g}",
                    "买入倍数": component.params.get("weight", 0),
                    "是否允许弹性买入": "是",
                }
            )
        elif component.component_type == "drawdown_add":
            for rule in component.params.get("rules", []):
                rows.append(
                    {
                        "策略": component.display_name,
                        "状态": status,
                        "触发条件": f"从历史高点回撤 <= {rule['threshold_pct']:g}%",
                        "动作": rule["action"],
                        "买入倍数": rule["multiplier"],
                        "是否允许弹性买入": "是",
                    }
                )
        elif component.component_type == "ma_deviation":
            ma_days = int(component.params.get("ma_days", profile.trend_ma_days))
            for rule in component.params.get("rules", []):
                threshold = float(rule["threshold_pct"])
                direction = "低于" if threshold < 0 else "高于"
                rows.append(
                    {
                        "策略": component.display_name,
                        "状态": status,
                        "触发条件": f"{direction} MA{ma_days} {abs(threshold):g}%",
                        "动作": rule["action"],
                        "买入倍数": rule["multiplier"],
                        "是否允许弹性买入": "是" if rule.get("allow_elastic_buy", True) else "否",
                    }
                )
        elif component.component_type == "dividend_yield":
            rows.append(
                {
                    "策略": component.display_name,
                    "状态": status,
                    "触发条件": f"股息率分位 >= {component.params.get('high_percentile', 70):g}%",
                    "动作": "提高买入倍数",
                    "买入倍数": component.params.get("multiplier", 1.5),
                    "是否允许弹性买入": "是",
                }
            )
        elif component.component_type == "valuation_guard":
            rows.append(
                {
                    "策略": component.display_name,
                    "状态": status,
                    "触发条件": f"估值分位 >= {component.params.get('high_percentile', 90):g}%",
                    "动作": "停止弹性买入",
                    "买入倍数": "不影响固定层",
                    "是否允许弹性买入": "否",
                }
            )
    return rows


def with_profile_settings(
    profile: AssetProfile,
    *,
    trend_ma_days: int | None = None,
    fixed_layer_weight: float | None = None,
    drawdown_rules: tuple[DrawdownRule, ...] | None = None,
    ma_rules: tuple[MaRule, ...] | None = None,
) -> AssetProfile:
    return replace(
        profile,
        trend_ma_days=trend_ma_days if trend_ma_days is not None else profile.trend_ma_days,
        fixed_layer_weight=(
            fixed_layer_weight if fixed_layer_weight is not None else profile.fixed_layer_weight
        ),
        drawdown_rules=drawdown_rules if drawdown_rules is not None else profile.drawdown_rules,
        ma_rules=ma_rules if ma_rules is not None else profile.ma_rules,
    )


def with_strategy_components(
    profile: AssetProfile,
    components: tuple[StrategyComponent, ...],
) -> AssetProfile:
    return replace(
        profile,
        strategy_components=components,
        fixed_layer_weight=_fixed_weight_from_components(components, profile.fixed_layer_weight),
        trend_ma_days=_ma_days_from_components(components, profile.trend_ma_days),
        drawdown_rules=_drawdown_rules_from_components(components, profile.drawdown_rules),
        ma_rules=_ma_rules_from_components(components, profile.ma_rules),
    )


def _fixed_weight_from_components(
    components: tuple[StrategyComponent, ...],
    fallback: float,
) -> float:
    component = next((item for item in components if item.key == "fixed_contribution"), None)
    if component is None or not component.enabled:
        return 0.0 if component is not None else fallback
    return float(component.params.get("weight", fallback))


def _ma_days_from_components(components: tuple[StrategyComponent, ...], fallback: int) -> int:
    component = next((item for item in components if item.key == "ma_deviation"), None)
    if component is None:
        return fallback
    return int(component.params.get("ma_days", fallback))


def _drawdown_rules_from_components(
    components: tuple[StrategyComponent, ...],
    fallback: tuple[DrawdownRule, ...],
) -> tuple[DrawdownRule, ...]:
    component = next((item for item in components if item.key == "drawdown_add"), None)
    if component is None:
        return fallback
    if not component.enabled:
        return ()
    return tuple(
        DrawdownRule(
            threshold_pct=float(rule["threshold_pct"]),
            multiplier=float(rule["multiplier"]),
            action=str(rule["action"]),
        )
        for rule in component.params.get("rules", [])
    )


def _ma_rules_from_components(
    components: tuple[StrategyComponent, ...],
    fallback: tuple[MaRule, ...],
) -> tuple[MaRule, ...]:
    component = next((item for item in components if item.key == "ma_deviation"), None)
    if component is None:
        return fallback
    if not component.enabled:
        return ()
    return tuple(
        MaRule(
            threshold_pct=float(rule["threshold_pct"]),
            multiplier=float(rule["multiplier"]),
            action=str(rule["action"]),
            allow_elastic_buy=bool(rule.get("allow_elastic_buy", True)),
        )
        for rule in component.params.get("rules", [])
    )
