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


@dataclass(frozen=True)
class AccountConfig:
    """CNY balances; existing holdings are units valued at the last pre-start observed marks."""
    initial_total: float = 650_000
    cash: float = 650_000
    bonds: float = 0
    holdings: dict[str, float] = field(default_factory=dict)
    reserve: float = 150_000
    monthly: float = 20_000
    months: int = 9
    tactical_budget: float = 100_000
    monthly_tactical_cap: float = 50_000
    weights: dict[str, float] = field(default_factory=lambda: {"equity": 1.0})
    thresholds: tuple[float, ...] = (.10, .15, .20, .30)
    amounts: tuple[float, ...] = (10_000, 20_000, 30_000, 40_000)


@dataclass(frozen=True)
class ExecutionPolicy:
    """Limits apply to total cash debit per asset/session, including costs."""
    daily_caps: dict[str, float] = field(default_factory=dict)
    fees: dict[str, float] = field(default_factory=dict)
    slippage: float = 0
    inception: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AccountResult:
    daily: object
    trades: object
    events: object
    metrics: dict[str, float | None]
    config: AccountConfig
    strategy: str
