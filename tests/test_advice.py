from invest_strategy.advice import build_advice
from invest_strategy.models import StrategySignal


def test_advice_for_buy_signal_mentions_multiplier():
    signal = StrategySignal(action="加倍定投", multiplier=2.0, reasons=["从高点回撤 25.0%"])

    advice = build_advice("标普500", signal, 1000)

    assert "建议投入 2000" in advice.summary
    assert "加倍定投" in advice.summary


def test_advice_for_partial_sell_signal_does_not_show_buy_amount():
    signal = StrategySignal(
        action="减部分弹性仓",
        multiplier=0.0,
        allow_elastic_buy=False,
        reasons=["高于 MA250 32.0%"],
    )

    advice = build_advice("纳指100", signal, 1000)

    assert "减部分弹性仓" in advice.summary
    assert "停止弹性买入" in advice.details
