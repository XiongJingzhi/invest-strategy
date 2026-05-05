# Streamlit Invest Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Streamlit Python MVP for asset-specific investment backtesting and advice.

**Architecture:** Use a small typed Python package for strategy, data, backtesting, and advice, with `app.py` as a thin Streamlit shell. Keep strategy rules data-driven through asset profiles so low-volatility dividend, S&P 500, and Nasdaq 100 assets do not share one MA120 sell rule.

**Tech Stack:** Python 3.11+, pandas, numpy, yfinance, streamlit, plotly, pytest.

---

### Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`
- Create: `src/invest_strategy/__init__.py`

**Steps:**

1. Create packaging metadata with dependencies for Streamlit, pandas, numpy, yfinance, plotly, and pytest.
2. Add a README with setup and run commands.
3. Add a Python-focused `.gitignore`.
4. Run `python -m compileall src`.

### Task 2: Domain Models and Profiles

**Files:**
- Create: `src/invest_strategy/models.py`
- Create: `src/invest_strategy/profiles.py`
- Test: `tests/test_profiles.py`

**Steps:**

1. Write tests that assert default profiles exist for low-volatility dividend, S&P 500, and Nasdaq 100.
2. Verify S&P 500 and Nasdaq profiles never use MA120 as their selling rule.
3. Implement dataclasses for profile settings, signal outputs, valuation inputs, and advice actions.
4. Implement default profile factory functions.
5. Run `pytest tests/test_profiles.py -v`.

### Task 3: Strategy Engine

**Files:**
- Create: `src/invest_strategy/strategies.py`
- Test: `tests/test_strategies.py`

**Steps:**

1. Write failing tests for low-volatility MA120 thresholds, S&P 500 drawdown multipliers, and Nasdaq MA250 risk control.
2. Implement moving average deviation, drawdown calculation, multiplier rules, and action labels.
3. Add missing-data behavior for dividend, PB, and PE valuation inputs.
4. Run `pytest tests/test_strategies.py -v`.

### Task 4: Backtest Engine

**Files:**
- Create: `src/invest_strategy/backtest.py`
- Test: `tests/test_backtest.py`

**Steps:**

1. Write tests with synthetic monthly prices to verify shares, invested capital, and portfolio value.
2. Write tests that a drawdown rule increases contribution multiplier at the expected month.
3. Implement monthly simulation using the strategy engine.
4. Run `pytest tests/test_backtest.py -v`.

### Task 5: Data and Advice

**Files:**
- Create: `src/invest_strategy/data.py`
- Create: `src/invest_strategy/advice.py`
- Test: `tests/test_advice.py`

**Steps:**

1. Write tests for advice text generated from buy, hold, stop-elastic-buy, and partial-sell signals.
2. Implement `download_prices` with normalized `date` and `close` columns.
3. Implement advice generation with concise Chinese recommendations.
4. Run `pytest tests/test_advice.py -v`.

### Task 6: Streamlit UI

**Files:**
- Create: `app.py`

**Steps:**

1. Build sidebar controls for ticker, asset profile, date range, monthly contribution, and optional valuation inputs.
2. Render strategy summary, latest recommendation, metrics, equity curve, and monthly action table.
3. Add clear error handling for empty or failed downloads.
4. Run `streamlit run app.py --server.headless true --server.port 8501`.

### Task 7: Full Verification

**Files:**
- All project files.

**Steps:**

1. Run `pytest -v`.
2. Run `python -m compileall src app.py`.
3. Smoke-test Streamlit import with `python -c "import app"`.
4. Commit the final implementation.

