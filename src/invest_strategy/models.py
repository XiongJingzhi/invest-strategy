from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class DrawdownRule:
    threshold_pct: float
    multiplier: float
    action: str


@dataclass(frozen=True)
class MaRule:
    threshold_pct: float
    multiplier: float
    action: str
    allow_elastic_buy: bool = True


@dataclass(frozen=True)
class StrategyComponent:
    key: str
    display_name: str
    component_type: str
    enabled: bool = True
    priority: int = 100
    params: dict[str, object] = field(default_factory=dict)

    def disabled(self) -> "StrategyComponent":
        return replace(self, enabled=False)


@dataclass(frozen=True)
class AssetProfile:
    key: str
    display_name: str
    role: str
    base_description: str
    strategy_notes: tuple[str, ...]
    fixed_layer_weight: float
    drawdown_rules: tuple[DrawdownRule, ...] = ()
    ma_rules: tuple[MaRule, ...] = ()
    trend_ma_days: int = 250
    valuation_weight: float = 0.0
    dividend_weight: float = 0.0
    partial_sell_above_ma_pct: float | None = None
    strategy_components: tuple[StrategyComponent, ...] = ()


@dataclass(frozen=True)
class ValuationInput:
    dividend_percentile: float | None = None
    pb_percentile: float | None = None
    pe_percentile: float | None = None
    dividend_yield: float | None = None
    pe: float | None = None


@dataclass
class StrategySignal:
    action: str = "正常定投"
    multiplier: float = 1.0
    allow_elastic_buy: bool = True
    drawdown_pct: float | None = None
    ma_deviation_pct: float | None = None
    valuation_score: float | None = None
    dividend_percentile: float | None = None
    dividend_yield: float | None = None
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Advice:
    summary: str
    details: str


@dataclass(frozen=True)
class BacktestSummary:
    total_invested: float
    final_value: float
    total_return_pct: float
    annualized_return_pct: float
    xirr_pct: float
    max_drawdown_pct: float


@dataclass(frozen=True)
class BacktestResult:
    monthly: object
    summary: BacktestSummary
