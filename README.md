# macro-etf-data

Python pipeline to fetch daily ETF prices from Yahoo Finance, fetch IMF WEO GDP data (Oct 2025 baseline), and build a merged annual ETF-vs-macro dataset.

## Current Capabilities

- Fetch ETF daily price data for configured country-focused tickers.
- Fetch IMF WEO indicators `NGDPD` and `NGDP_RPCH` for mapped countries.
- Build annual ETF return output merged with GDP metrics.
- Run full pipeline from one command via `main.py`.
- Validate a single ticker interactively in notebook:
  - manual ticker selection (project ticker or custom Yahoo symbol)
  - GBP/GBp checks
  - close-price diagnostics charts
  - return windows: YTD, 1M, 3M, 6M, 1Y, 3Y, 5Y, 10Y, MAX, 2025, 2024, 2023, 2022

## Run Pipeline

1. Full pipeline (recommended):

```bash
uv run python main.py
```

2. Step-by-step (equivalent):

```bash
uv run python fetch_etf_prices.py --start 2015-01-01 --output etf_prices.csv
uv run python fetch_weo_gdp.py --start-year 2015 --end-year 2026 --output weo_gdp.csv
uv run python build_combined_etf_weo.py --etf-csv etf_prices.csv --weo-csv weo_gdp.csv --output etf_weo_combined_annual.csv
```

## Validation Notebook

Run Jupyter and open `etf_return_validation.ipynb`:

```bash
uv run jupyter notebook
```

## Outputs

- `etf_prices.csv`
- `weo_gdp.csv`
- `etf_weo_combined_annual.csv`
