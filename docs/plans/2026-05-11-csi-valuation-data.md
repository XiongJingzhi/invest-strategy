# CSI Valuation Data Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make 515100 use CSI 930955 index dividend yield and PE valuation data.

**Architecture:** Add a valuation-history path in `invest_strategy.data` that maps ETF tickers to CSI index codes and normalizes AkShare valuation rows. Compute PE percentile from CSI historical rolling PE, use recent CSI valuation data for dividend yield, preserve existing ETF cash-distribution dividend logic as fallback, and propagate PE data through current advice and backtest valuation lookup.

**Tech Stack:** Python, pandas, AkShare, pytest.

---

### Task 1: Failing Data Test

**Files:**
- Modify: `tests/test_data.py`
- Modify: `src/invest_strategy/data.py`

**Steps:**
1. Add a test that monkeypatches `akshare.stock_zh_index_value_csindex` and calls `download_dividend_percentiles("515100.SS", ...)`.
2. Assert that the AkShare call uses `930955`.
3. Assert returned rows include `dividend_yield`, `dividend_percentile`, `pe`, and `pe_percentile`.
4. Run the specific test and confirm it fails because the current code does not use CSI valuation data.
5. Implement the minimal code to pass.

### Task 2: Failing Propagation Tests

**Files:**
- Modify: `tests/test_app_interaction.py`
- Modify: `tests/test_backtest.py`
- Modify: `app.py`
- Modify: `src/invest_strategy/backtest.py`

**Steps:**
1. Add tests showing `dividend_yield` and `pe_percentile` are copied into `ValuationInput` for current advice and backtests.
2. Run the specific tests and confirm they fail.
3. Update the conversion helpers to preserve `pe_percentile`.
4. Run the specific tests and then the full suite.
