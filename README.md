# macro-etf-data

Python pipeline to fetch daily ETF prices from Yahoo Finance, fetch IMF WEO GDP data (Oct 2025 baseline), and build a merged annual ETF-vs-macro dataset.

## Repository Layout

- `src/`: pipeline scripts
- `data/outputs/`: generated CSV outputs
- `notebooks/`: interactive validation notebooks
- `docs/`: references and worklogs

## Current Capabilities

- Fetch ETF daily price data for configured country-focused tickers.
- Fetch IMF WEO indicators `NGDPD` and `NGDP_RPCH` for mapped countries.
- Build annual ETF return output merged with GDP metrics.
- Run full pipeline from one command via `main.py`.
- Build an interactive Excel KPI dashboard (MVP) for stakeholder review with:
  - ETF-only timeframe returns (YTD, 1M, 3M, 6M, 1Y, 3Y, 5Y, 10Y, MAX)
  - annual ETF vs GDP comparison (last 10 years)
  - GDP same-year comparison
  - CAGR comparison (3Y, 5Y, 10Y) for ETF vs GDP
- Build a separate Excel workbook with one full-history ETF chart sheet per ticker.
- Validate a single ticker interactively in notebook:
  - manual ticker selection (project ticker or custom Yahoo symbol)
  - GBP/GBp checks
  - close-price diagnostics charts
  - return windows: YTD, 1M, 3M, 6M, 1Y, 3Y, 5Y, 10Y, MAX, 2025, 2024, 2023, 2022

## Run Pipeline

1. Full pipeline (recommended):

```bash
uv run python src/main.py
```

This also produces `data/outputs/etf_gdp_dashboard_mvp.xlsx` unless `--skip-dashboard` is provided.
It also produces `data/outputs/etf_price_history_charts.xlsx` unless `--skip-history-charts` is provided.
By default, ETF fetch now uses full Yahoo history (`period=max`) unless `--start-date` is explicitly set.

2. Step-by-step (equivalent):

```bash
uv run python src/fetch_etf_prices.py --output data/outputs/etf_prices.csv
uv run python src/fetch_weo_gdp.py --start-year 2015 --end-year 2026 --output data/outputs/weo_gdp.csv
uv run python src/build_combined_etf_weo.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_weo_combined_annual.csv
uv run python src/build_excel_dashboard_mvp.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_gdp_dashboard_mvp.xlsx
uv run python src/build_etf_history_charts_workbook.py --etf-csv data/outputs/etf_prices.csv --output data/outputs/etf_price_history_charts.xlsx
```

WEO output now includes:
- `NGDPD` (GDP current USD level)
- `NGDP_RPCH` (real GDP growth %)
- `NGDPD_PCH` (nominal GDP growth %, derived from `NGDPD`)

## Validation Notebook

Run Jupyter and open `notebooks/etf_return_validation.ipynb`:

```bash
uv run jupyter notebook
```

## Outputs

- `data/outputs/etf_prices.csv`
- `data/outputs/weo_gdp.csv`
- `data/outputs/etf_weo_combined_annual.csv`
- `data/outputs/etf_gdp_dashboard_mvp.xlsx`
- `data/outputs/etf_price_history_charts.xlsx`
