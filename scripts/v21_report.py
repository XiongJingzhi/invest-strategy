"""Reproduce reports exclusively from hash-checked archived real snapshots.

Run: python scripts/v21_report.py [--rolling]
No historical valuation feed is supplied: F must remain unavailable.
"""

import argparse
from pathlib import Path
from dataclasses import asdict
import json
from invest_strategy.audit import audit_account

import pandas as pd

from invest_strategy.compare import compare_accounts
from invest_strategy.market import load_snapshot
from invest_strategy.models import AccountConfig
from invest_strategy.research import event_study, rolling_accounts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rolling", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed rolling checkpoints for this exact snapshot/config",
    )
    args = parser.parse_args()
    root = Path("reports")
    audits = {}
    run_config = {}
    lines = [
        "# V2.1 真实历史回测报告",
        "",
        "本报告仅使用随仓库保存、SHA256校验的数据快照。不是市场预测或保证收益。",
        "金额均为人民币。初始65万元现金，其中15万元安全底线；无已有持仓；每月2万元从第二个日历月首次观测日到账。",
        "存量50万元，9个月转仓，10万元战术池属于50万元的一部分。战术单月上限5万元。",
        "价格：NDX未复权正式收盘字段触发，QQQ/GLD/515100复权价格用于收益；USD资产用同日FRED汇率（缺失时Yahoo同日）换算。",
        "成交采用信号后可交易日复权收盘代理，零费用、零滑点、无限申购；因此是第一层基准实验，不能解释为真实QDII业绩。",
        "债券与现金收益设为0，安全底线为名义15万元。风险账户=家庭账户减固定15万元，不含安全资金市场波动。",
        "A一次性，B按月9期，C回撤10/15/20/30%，D旧梯度15/25/35%，E按预先已知XNYS交易日等额排期，F需时点估值。",
        "历史F不可用：未获得可验证、有许可及公布时间的远期盈利一致预期与估值参数。不会将当前假设填入过去。",
        "",
    ]
    for name, weights, starts in [
        (
            "single",
            {"equity": 1.0},
            ["2000-01-03", "2008-01-02", "2020-01-02", "2022-01-03"],
        ),
        (
            "portfolio",
            {"equity": 0.7, "gold": 0.15, "dividend": 0.15},
            ["2020-06-01", "2022-01-03"],
        ),
    ]:
        market, manifest = load_snapshot(root / "data" / name)
        end = market[list(weights)].dropna().index[-1]
        config = AccountConfig(weights=weights)
        run_config[name] = {
            "account": asdict(config),
            "starts": starts,
            "end": str(end),
            "market_sha256": manifest["market_sha256"],
        }
        lines += [
            f"## {name}：截至{end.date()}",
            f"快照哈希 `{manifest['market_sha256']}`。有效三资产历史不足2000/2008/2020年初，不做基金成立前拼接。"
            if name == "portfolio"
            else f"快照哈希 `{manifest['market_sha256']}`。NDX包含1985年以来预热；QQQ从1999年成立后开始。",
            "",
        ]
        for start in starts:
            summary, results = compare_accounts(market, start, end, config)
            prefix = root / f"{name}-{start}"
            summary.to_csv(str(prefix) + "-summary.csv")
            for strategy, result in results.items():
                audit = audit_account(result, market)
                audits[f"{name}-{start}-{strategy}"] = audit
                if not audit["passed"]:
                    raise AssertionError(
                        f"Ledger audit failed: {name} {start} {strategy}: {audit}"
                    )
                result.daily.to_csv(str(prefix) + f"-{strategy}-daily.csv")
                result.trades.to_csv(
                    str(prefix) + f"-{strategy}-trades.csv", index=False
                )
                result.events.to_csv(
                    str(prefix) + f"-{strategy}-events.csv", index=False
                )
            lines += [
                f"### 起点 {start}",
                "|策略|期末家庭总资产|净收益|TWR|XIRR|最大回撤|相对A金额|相对B金额|",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
            for strategy, row in summary.iterrows():
                if row.status != "OK":
                    lines += [f"|{strategy}|不可用|||||||"]
                else:
                    lines += [
                        f"|{strategy}|{row.final_total:,.2f}|{row.net_profit:,.2f}|{row.twr:.2%}|{row.xirr:.2%}|{row.max_drawdown:.2%}|{row.profit_vs_A:,.2f}|{row.profit_vs_B:,.2f}|"
                    ]
            lines += [
                "",
                "完整指标、每日台账、事件与成交见同前缀CSV；持续入金账户CAGR留空，年化TWR单独报告。",
                "",
            ]
            print(name, start, "done", flush=True)
        event_start = starts[0]
        detail, stats = event_study(market, event_start, str(end))
        detail.to_csv(root / f"{name}-event-detail.csv", index=False)
        stats.to_csv(root / f"{name}-event-summary.csv", index=False)
        lines += [
            f"事件研究见 `{name}-event-summary.csv` 与明细。下一可执行交易日入场，按日历月寻找期满后首个观测收盘。",
            "未满观察期右删失；样本重叠、相关，不报告独立样本显著性。相对基准是整个窗口同期限所有可入场日期的无条件均值差，不是因果优势。",
            "",
        ]
        if args.rolling:
            count = [0]

            def progress(begin, rows):
                count[0] += 1
                if count[0] % 12 == 0:
                    print(name, "rolling", begin.date(), len(rows), "rows", flush=True)
                    pd.DataFrame(rows).to_csv(root / f"{name}-rolling.csv", index=False)

            checkpoint = root / f"{name}-rolling.csv"
            resume = (
                pd.read_csv(checkpoint) if args.resume and checkpoint.exists() else None
            )
            rolling = rolling_accounts(
                market, starts[0], end, config, progress=progress, resume=resume
            )
            rolling.to_csv(root / f"{name}-rolling.csv", index=False)
            ok = rolling[rolling.status == "OK"]
            agg = ok.groupby(["years", "strategy"]).agg(
                cohorts=("twr", "size"),
                median_twr=("twr", "median"),
                worst_twr=("twr", "min"),
                best_twr=("twr", "max"),
                win_A=("profit_vs_A", lambda x: (x > 0).mean()),
                win_B=("profit_vs_B", lambda x: (x > 0).mean()),
                median_delta_A=("profit_vs_A", "median"),
                worst_delta_A=("profit_vs_A", "min"),
                worst_drawdown=("max_drawdown", "min"),
            )
            agg.to_csv(root / f"{name}-rolling-summary.csv")
            lines += [
                "### 每月起点滚动结果",
                "完整样本与汇总见滚动CSV；仅完整1/3/5/10年区间纳入。",
                "",
            ]
            c = agg.xs("C", level="strategy")
            for years, row in c.iterrows():
                lines += [
                    f"- {years}年：{int(row.cohorts)}个起点；C胜A {row.win_A:.1%}，胜B {row.win_B:.1%}；相对A金额中位数{row.median_delta_A:,.0f}元，最差{row.worst_delta_A:,.0f}元；C最差账户回撤{row.worst_drawdown:.1%}。"
                ]
            if 10 not in c.index:
                lines += ["10年观察期不可用：该组合真实产品历史不足10年。", ""]
            # Record C regimes including paired drawdown risk, not only best starts.
            paired = ok.pivot(
                index=["start", "years"], columns="strategy", values="max_drawdown"
            )
            paired["C_minus_A"] = paired.C - paired.A
            paired["C_minus_B"] = paired.C - paired.B
            paired.to_csv(root / f"{name}-rolling-extra-risk.csv")
            lines += [
                f"C相比A最大额外回撤为{-paired.C_minus_A.min() * 100:.2f}个百分点；相比B为{-paired.C_minus_B.min() * 100:.2f}个百分点（同起点、同观察期配对）。",
                "",
            ]
            regimes = ok[ok.strategy == "C"].sort_values("profit_vs_A")
            regimes.groupby("years").head(3).to_csv(
                root / f"{name}-C-worst-starts.csv", index=False
            )
            regimes.groupby("years").tail(3).to_csv(
                root / f"{name}-C-best-starts.csv", index=False
            )
    lines += [
        "",
        "## 可证伪范围与局限",
        "- 回撤提前买入只是同一存量本金的投入时机变化，不创造资金。长期收益差主要来自最初9个月，随后规则趋同。",
        "- 不同起点和事件有重叠；排名会受牛熊路径、初始持仓、汇率、费用和产品限购影响。不能仅凭崩盘前起点断言C优于A/B。",
        "- 数据为当前下载的供应商历史版本（不是逐日原始存档），复权可能被修订；manifest保存来源、下载时间、币种、缺失值和哈希。",
        "- F未运行，因此不能宣称基本面估值改善回测。合法时点数据接入后，须事先冻结参数及样本内/样本外日期再研究。",
        "- 实际QDII产品历时净值、成立日期、限购、申购费、场内溢价、汇率及可成交时间须独立输入；未获得两只主动替代基金的完整产品执行历史。",
        "- 执行日期为日频保守后续收盘代理；不提供经纪商下单、自动产品日历或净值确认对账。",
        "- Sharpe/Sortino以0参考利率，波动率按252日年化；回本时间含未回本的右删失标记。现金拖累定义为相对A期末资产差，包含投入时机效应。",
    ]
    (root / "ledger-audit.json").write_text(json.dumps(audits, indent=2))
    (root / "run-config.json").write_text(json.dumps(run_config, indent=2))
    (root / "V2.1-real-history.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
