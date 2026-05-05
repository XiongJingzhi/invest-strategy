# Streamlit Invest Strategy Design

## Goal

Build a local Python app for stock and index investing workflows: fetch price history, run monthly contribution backtests, combine asset-specific strategy rules, and show a clear Streamlit UI with current investment advice.

## Product Shape

The first version is a local Streamlit app. It does not include user accounts, broker integration, database persistence, or paid valuation feeds. Price data comes from `yfinance`; valuation and dividend inputs can be entered manually when unavailable.

The app is designed around three asset profiles:

- Low-volatility dividend assets: dividend yield, PB/PE valuation, and MA120/MA250 deviation.
- S&P 500 style broad assets: fixed contribution, drawdown add-ons, and valuation as an auxiliary signal.
- Nasdaq 100 style growth assets: smaller fixed contribution, deep drawdown add-ons, and MA250 trend risk control.

## Architecture

The app uses a small package under `src/invest_strategy` plus a Streamlit entrypoint at `app.py`.

- `data.py` fetches and normalizes daily price history.
- `models.py` defines shared dataclasses and enums.
- `profiles.py` provides asset templates and default strategy parameters.
- `strategies.py` evaluates strategy signals and recommended contribution multipliers.
- `backtest.py` simulates monthly investing, holdings, portfolio value, and drawdowns.
- `advice.py` creates a human-readable recommendation from latest strategy signals.
- `app.py` wires the package into Streamlit controls, charts, and metrics.

## Data Flow

1. The user enters a ticker, selects an asset profile, and sets a monthly contribution.
2. The app downloads adjusted close prices for the selected period.
3. The strategy engine computes moving averages, high-watermark drawdown, and optional valuation/dividend scores.
4. The backtest engine invests monthly according to the profile's multiplier rules.
5. The UI displays the equity curve, monthly actions, latest signal table, and an action summary.

## Strategy Rules

Low-volatility dividend assets prioritize dividend and valuation inputs when available. MA120 deviation is used as a practical fallback and as a secondary timing signal.

S&P 500 style assets always keep the fixed layer running. Drawdown increases contribution size; valuation only slows or stops elastic buying, not the base contribution.

Nasdaq 100 style assets keep a smaller base contribution. Drawdown creates the main buying opportunities, while MA250 deviation controls elastic buying and partial profit-taking warnings.

## Error Handling

The data layer validates required columns and reports empty downloads clearly. Strategy calculations tolerate missing valuation fields by marking those signals as unavailable instead of failing. The UI shows user-facing errors for ticker or network failures.

## Testing

Unit tests cover signal thresholds, profile defaults, advice generation, and deterministic backtest math using synthetic price data. The Streamlit UI is kept thin so most behavior is testable without launching the UI.

