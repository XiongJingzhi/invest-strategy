# CSI Valuation Data Design

## Goal

Use index-level valuation data for the dividend low-volatility ETF preset, so 515100 uses CSI 930955 dividend yield and PE data instead of treating ETF cash distributions as the main valuation signal.

## Design

- Keep ETF price downloads unchanged.
- Add a valuation-history downloader that maps `515100.SS` and `515100` to underlying index `930955`.
- Fetch CSI valuation data with AkShare `stock_zh_index_value_csindex("930955")`.
- Normalize it into monthly rows with `dividend_yield`, `dividend_percentile`, `pe`, and `pe_percentile`.
- Compute PE percentile from CSI historical rolling PE. Use CSI recent valuation data for the actual dividend yield; leave dividend percentile empty when the public CSI file does not provide enough history.
- Keep the existing ETF-distribution calculation as the fallback for symbols without an index valuation mapping.
- Propagate `pe_percentile` into `ValuationInput` for current advice and backtests.

## Error Handling

If CSI valuation data is unavailable or malformed, return an empty valuation frame and fall back to the existing no-valuation behavior rather than blocking price downloads.

## Testing

Add focused unit tests that monkeypatch AkShare and verify:

- `515100.SS` uses CSI 930955 valuation rows.
- Current valuation includes CSI dividend yield and PE percentile.
- Backtest valuation lookup preserves CSI dividend yield and PE percentile.
