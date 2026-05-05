from __future__ import annotations

from dataclasses import replace

from .models import AssetProfile, DrawdownRule, MaRule, StrategyComponent


def get_default_profiles() -> dict[str, AssetProfile]:
    return {
        "low_vol_dividend": AssetProfile(
            key="low_vol_dividend",
            display_name="红利现金流防守",
            role="红利 + 价值 + 防守",
            base_description="适合红利低波类标的的组合：股息率/PB/PE 优先，MA120/MA250 辅助判断。",
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
            display_name="全球核心定投",
            role="核心 + 宽基 + 长期",
            base_description="适合全球核心宽基的组合：固定层持续定投，回撤加仓，估值只控制弹性层。",
            strategy_notes=(
                "固定层长期不断投，不因短期估值或均线信号轻易中断。",
                "标的价格从历史高点回撤 10% 后逐级提高投入，30% 后动用现金桶。",
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
            display_name="科技成长进攻",
            role="成长 + 高波动 + 进攻",
            base_description="适合科技成长类高波动标的的组合：小额定投，深度回撤加仓，MA250 控制弹性仓。",
            strategy_notes=(
                "固定层小额持续，仓位不应超过全球核心宽基仓。",
                "标的价格回撤 20% 后开始加大买入，30%-40% 是重点加仓区。",
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
        "steady_dca": AssetProfile(
            key="steady_dca",
            display_name="稳健定投",
            role="稳健 + 低干预",
            base_description="固定层为主，轻度标的回撤加仓，适合不想频繁调仓的长期定投。",
            strategy_notes=(
                "固定层保持 1 倍定投，不轻易中断。",
                "标的回撤 10% 后小幅提高投入，20% 后再提高一档。",
                "不设置卖出规则，避免过度择时。",
            ),
            fixed_layer_weight=1.0,
            trend_ma_days=250,
            drawdown_rules=(
                DrawdownRule(-20, 1.8, "稳健加仓"),
                DrawdownRule(-10, 1.3, "小幅加仓"),
            ),
            strategy_components=(
                fixed_contribution_component(1.0),
                drawdown_component(
                    (
                        DrawdownRule(-20, 1.8, "稳健加仓"),
                        DrawdownRule(-10, 1.3, "小幅加仓"),
                    )
                ),
            ),
        ),
        "aggressive_drawdown": AssetProfile(
            key="aggressive_drawdown",
            display_name="进攻回撤",
            role="进攻 + 深跌加仓",
            base_description="固定层较低，主要等待标的深度回撤时提高买入倍数，并用长期均线禁止高位追涨。",
            strategy_notes=(
                "平时低速定投，保留现金弹性。",
                "标的回撤 20% 后开始明显加仓，40% 后大额分批。",
                "高于长期均线 25% 后停止弹性买入。",
            ),
            fixed_layer_weight=0.5,
            trend_ma_days=250,
            drawdown_rules=(
                DrawdownRule(-40, 4.0, "大额分批加仓"),
                DrawdownRule(-30, 3.0, "重点加仓"),
                DrawdownRule(-20, 2.0, "明显加仓"),
            ),
            ma_rules=(
                MaRule(25, 0.5, "停止弹性买入", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(0.5),
                drawdown_component(
                    (
                        DrawdownRule(-40, 4.0, "大额分批加仓"),
                        DrawdownRule(-30, 3.0, "重点加仓"),
                        DrawdownRule(-20, 2.0, "明显加仓"),
                    )
                ),
                ma_component(
                    ma_days=250,
                    rules=(MaRule(25, 0.5, "停止弹性买入", allow_elastic_buy=False),),
                ),
            ),
        ),
        "trend_guard": AssetProfile(
            key="trend_guard",
            display_name="趋势风控",
            role="趋势 + 风控",
            base_description="固定定投叠加长期均线风控，适合高波动资产或用户想控制高位弹性买入的场景。",
            strategy_notes=(
                "固定层保持在场。",
                "低于长期均线 15% 时提高买入。",
                "高于长期均线 20% 后停止弹性买入，30% 后可减部分弹性仓。",
            ),
            fixed_layer_weight=0.8,
            trend_ma_days=250,
            valuation_weight=0.1,
            ma_rules=(
                MaRule(-15, 1.5, "趋势低位加仓"),
                MaRule(20, 0.8, "停止弹性买入", allow_elastic_buy=False),
                MaRule(30, 0.0, "减部分弹性仓", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(0.8),
                ma_component(
                    ma_days=250,
                    rules=(
                        MaRule(-15, 1.5, "趋势低位加仓"),
                        MaRule(20, 0.8, "停止弹性买入", allow_elastic_buy=False),
                        MaRule(30, 0.0, "减部分弹性仓", allow_elastic_buy=False),
                    ),
                ),
                valuation_component(weight=0.1),
            ),
        ),
        "pure_dca": AssetProfile(
            key="pure_dca",
            display_name="纯固定定投",
            role="极简 + 长期在场",
            base_description="只执行固定定投，不做回撤加仓、不做均线止买，作为所有复杂策略的基准线。",
            strategy_notes=(
                "每月按固定金额投入。",
                "不根据标的回撤、均线、估值改变买入金额。",
                "适合作为对照组，观察复杂策略是否真的创造增益。",
            ),
            fixed_layer_weight=1.0,
            trend_ma_days=250,
            strategy_components=(fixed_contribution_component(1.0),),
        ),
        "crisis_cash_bucket": AssetProfile(
            key="crisis_cash_bucket",
            display_name="现金桶危机加仓",
            role="现金桶 + 极端机会",
            base_description="平时低速定投，只有标的出现较大回撤时才显著动用现金桶。",
            strategy_notes=(
                "固定层保持低权重，避免正常行情消耗过多现金。",
                "标的回撤 25% 后开始明显加仓，45% 后进入危机加仓。",
                "适合现金储备充足、想等待大跌机会的用户。",
            ),
            fixed_layer_weight=0.4,
            trend_ma_days=250,
            drawdown_rules=(
                DrawdownRule(-45, 5.0, "危机大额加仓"),
                DrawdownRule(-35, 3.5, "现金桶重点加仓"),
                DrawdownRule(-25, 2.0, "开始动用现金桶"),
            ),
            strategy_components=(
                fixed_contribution_component(0.4),
                drawdown_component(
                    (
                        DrawdownRule(-45, 5.0, "危机大额加仓"),
                        DrawdownRule(-35, 3.5, "现金桶重点加仓"),
                        DrawdownRule(-25, 2.0, "开始动用现金桶"),
                    )
                ),
            ),
        ),
        "dividend_value_plus": AssetProfile(
            key="dividend_value_plus",
            display_name="红利估值增强",
            role="红利 + 估值 + 趋势",
            base_description="更偏红利/价值资产：股息率和估值优先，均线只做辅助加减速。",
            strategy_notes=(
                "股息率分位较高时提高买入倍数。",
                "估值偏高时停止弹性买入。",
                "低于 MA120 时加仓，高于 MA120 较多时停止弹性层。",
            ),
            fixed_layer_weight=0.8,
            trend_ma_days=120,
            dividend_weight=0.5,
            valuation_weight=0.3,
            ma_rules=(
                MaRule(-15, 2.0, "价值低位加仓"),
                MaRule(-5, 1.3, "温和加仓"),
                MaRule(15, 0.0, "停止弹性买入", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(0.8),
                dividend_component(weight=0.5),
                valuation_component(weight=0.3),
                ma_component(
                    ma_days=120,
                    rules=(
                        MaRule(-15, 2.0, "价值低位加仓"),
                        MaRule(-5, 1.3, "温和加仓"),
                        MaRule(15, 0.0, "停止弹性买入", allow_elastic_buy=False),
                    ),
                ),
            ),
        ),
        "ma_rebalance": AssetProfile(
            key="ma_rebalance",
            display_name="均线再平衡",
            role="均线 + 再平衡",
            base_description="用长期均线偏离控制买入节奏，适合希望少看估值、更多依赖价格趋势的用户。",
            strategy_notes=(
                "低于 MA200 时提高定投。",
                "高于 MA200 15% 时降低弹性买入。",
                "高于 MA200 25% 时停止弹性买入或减部分弹性仓。",
            ),
            fixed_layer_weight=0.9,
            trend_ma_days=200,
            ma_rules=(
                MaRule(-20, 2.0, "均线低位加仓"),
                MaRule(-10, 1.5, "提高定投"),
                MaRule(15, 0.5, "降低弹性买入", allow_elastic_buy=False),
                MaRule(25, 0.0, "减部分弹性仓", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(0.9),
                ma_component(
                    ma_days=200,
                    rules=(
                        MaRule(-20, 2.0, "均线低位加仓"),
                        MaRule(-10, 1.5, "提高定投"),
                        MaRule(15, 0.5, "降低弹性买入", allow_elastic_buy=False),
                        MaRule(25, 0.0, "减部分弹性仓", allow_elastic_buy=False),
                    ),
                ),
            ),
        ),
        "dividend_low_vol_drawdown_ma": AssetProfile(
            key="dividend_low_vol_drawdown_ma",
            display_name="红利低波回撤均线",
            role="红利低波 + 回撤 + MA250",
            base_description="适合红利低波类标的：平时正常定投，按标的回撤阶梯加仓，高于 MA250 后降低或停止弹性买入。",
            strategy_notes=(
                "正常状态保持 1.0 倍定投。",
                "标的回撤 -5%、-10%、-15%、-20% 时逐级提高到 1.2、1.5、2.0、2.5 倍。",
                "高于 MA250 20% 降到 0.7 倍，30% 停止弹性买入，35% 只考虑卖弹性仓。",
            ),
            fixed_layer_weight=1.0,
            trend_ma_days=250,
            drawdown_rules=(
                DrawdownRule(-20, 2.5, "回撤 -20% 加仓"),
                DrawdownRule(-15, 2.0, "回撤 -15% 加仓"),
                DrawdownRule(-10, 1.5, "回撤 -10% 加仓"),
                DrawdownRule(-5, 1.2, "回撤 -5% 加仓"),
            ),
            ma_rules=(
                MaRule(20, 0.7, "高于 MA250 20% 降低定投"),
                MaRule(30, 0.0, "停止弹性买入", allow_elastic_buy=False),
                MaRule(35, 0.0, "只考虑卖弹性仓", allow_elastic_buy=False),
            ),
            strategy_components=(
                fixed_contribution_component(1.0),
                drawdown_component(
                    (
                        DrawdownRule(-20, 2.5, "回撤 -20% 加仓"),
                        DrawdownRule(-15, 2.0, "回撤 -15% 加仓"),
                        DrawdownRule(-10, 1.5, "回撤 -10% 加仓"),
                        DrawdownRule(-5, 1.2, "回撤 -5% 加仓"),
                    )
                ),
                ma_component(
                    ma_days=250,
                    rules=(
                        MaRule(20, 0.7, "高于 MA250 20% 降低定投"),
                        MaRule(30, 0.0, "停止弹性买入", allow_elastic_buy=False),
                        MaRule(35, 0.0, "只考虑卖弹性仓", allow_elastic_buy=False),
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
                "触发条件": f"标的从历史高点回撤 <= {rule.threshold_pct:g}%",
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
                        "触发条件": f"标的从历史高点回撤 <= {rule['threshold_pct']:g}%",
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
