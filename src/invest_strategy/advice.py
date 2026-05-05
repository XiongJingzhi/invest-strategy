from __future__ import annotations

from .models import Advice, StrategySignal


def build_advice(asset_name: str, signal: StrategySignal, monthly_contribution: float) -> Advice:
    amount = round(monthly_contribution * signal.multiplier, 2)
    reasons = "；".join(signal.reasons) if signal.reasons else "当前没有显著极端信号"

    if signal.multiplier <= 0:
        summary = f"{asset_name}：{signal.action}。"
    else:
        summary = f"{asset_name}：{signal.action}，建议投入 {amount:g}。"

    elastic = "弹性层可继续买入" if signal.allow_elastic_buy else "停止弹性买入"
    details = f"{elastic}。依据：{reasons}。"
    return Advice(summary=summary, details=details)
