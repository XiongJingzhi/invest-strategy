from __future__ import annotations

from .models import AssetProfile, DrawdownRule, MaRule


def get_default_profiles() -> dict[str, AssetProfile]:
    return {
        "low_vol_dividend": AssetProfile(
            key="low_vol_dividend",
            display_name="低波红利",
            role="防守 + 现金流",
            base_description="股息率/PB/PE 优先，MA120/MA250 辅助判断。",
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
        ),
        "sp500": AssetProfile(
            key="sp500",
            display_name="标普500",
            role="核心 + 全球权益底仓",
            base_description="固定层持续定投，回撤加仓，估值只控制弹性层。",
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
        ),
        "nasdaq100": AssetProfile(
            key="nasdaq100",
            display_name="纳指100",
            role="进攻 + 科技增强",
            base_description="小额定投，深度回撤加仓，MA250 控制弹性仓。",
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
        ),
    }
