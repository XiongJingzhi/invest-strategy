# Invest Strategy

本项目是一个本地 Streamlit 应用，用于股票、ETF 和指数类资产的投资策略回测与操作建议。

首版内置三类资产模板：

- 红利现金流防守：股息率、PE、MA120/MA250。
- 全球核心定投：固定定投、回撤加仓、估值辅助。
- 科技成长进攻：小额定投、深度回撤加仓、MA250 趋势风控。

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
streamlit run app.py
```

## Test

```bash
pytest -v
```

## V2.1 确定性账户

在同一个 `streamlit run app.py` 中，侧栏切换到 **V2.1 确定性账户**。
原模板保留用于探索，不应将其不同投入金额的结果用于策略优劣结论。

- `account.py`：日频状态机、独立事件ID、待执行额度、资金子账与成交。
- `models.py`：显式初始现金、债券、持仓单位和核对总资产；权重只用于风险资金。
- `compare.py`：同本金、同外部现金流的A–F对照；历史估值不足时F不可用。
- `market.py`：原始行情快照、来源、下载时间、币种、缺失值与SHA256。
- `performance.py`：家庭及风险账户TWR/XIRR、回撤、波动、执行效率。
- `research.py`：逐月起点1/3/5/10年滚动与重叠回撤事件分布。
- `decision.py`：使用真实余额及用户导入成交记录给出确定性买入额度。
- `valuation.py`：独立合理PE、敏感性、时点估值校验及冻结参数样本外接口。

已归档真实数据和可复核结果见 [回测报告](reports/V2.1-real-history.md)，
架构审查及执行边界见 [实施说明](docs/V2.1-audit.md)。

```bash
# 从归档数据重现完整报告，运行时间取决于滚动样本数量
python scripts/v21_report.py --rolling
# 仅生成指定历史窗口和事件研究
python scripts/v21_report.py
```

下载新快照（网络可用时；`end` 不包含该日）：

```python
from invest_strategy.market import download_snapshot, extend_fx_from_fred
path = "reports/data/single"
download_snapshot(path, start="1985-01-01")
extend_fx_from_fred(path)  # 补充2001年前FRED历史汇率
```

默认9个月转仓不保留永久战术现金。战术池是存量现金的子预算；
首次触发锁定档位金额，所有周期的授权额度合计不超过10万元，
转仓期后只有市场信号记录，不产生新授权。未成交额度单独保留。
基础转仓按累计计划减已支出存量本金补足，提前投入不会重复支出。
外部月供从计划开始后的下一个日历月首次观测日到账，各组完全相同。

当前决策需提供计划起点、当前现金/债券、未支出存量预算、拟执行日期及
实际战术成交CSV（`event_id,date,debit`，金额为含费用的现金支出）。
事件清单可从页面下载；同一事件可以分批成交。没有导入成交记录即表示
**用户声明该计划尚无战术成交**，不是系统已经核对过券商账户。
余额和CSV由用户负责核对，工具不连接券商，也不发送订单。

真实QDII实验应使用真实产品的人民币复权净值/可成交价格列 `equity`、
独立的 `ndx` 列及实际可执行日期。基金成立前及关闭申购日不应提供可成交值。
`ExecutionPolicy` 可设置每产品成立日、日限购、申购费及滑点；
`equity_premium` 等列为相对资产净值的额外执行溢价假设（不要对已含溢价的交易价格再加一次）。
已归档QQQ/GLD并不是嘉实、银华或境内QDII的实际业绩。
中国产品与美国市场的开放日、申购截止和净值确认时差需由产品数据适配时
提供符合时序的可执行日期；本版日频引擎不自动推断这些日期。

历史估值CSV必须包含 `observed_at,available_at,source,forward_pe,growth,dividend,
required_return,terminal_pe,parameters_fixed_at`。日期带时区，参数为小数。
只使用已公布且观察时点前冻结的参数，默认超过100日的观测视为失效。
当前假设面板不会变成历史估值输入。严格冻结的样本外实验使用
`run_frozen_holdout`；未获得合规时点历史，本仓库不宣称F存在优势。

可选逐日列 `equity_cap` / `equity_fee`（其他资产同样使用列名前缀）可以
编码历史限购变化及费率；0限额表示暂停申购，缺失限额不生成成交。
所有买入共享同一资产当天限额，不会让定投和战术订单分别重复使用限额。
