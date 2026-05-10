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
