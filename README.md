# macro-etf-data

Python pipeline to fetch daily ETF prices from Yahoo Finance, fetch IMF WEO GDP data (Oct 2025 baseline), and build a merged annual ETF-vs-macro dataset.

## Repository Layout

- `src/`: pipeline scripts
  - `src/etf_mapping.py`: canonical country/ticker + ISO3 mappings (single source of truth)
- `data/outputs/`: generated CSV outputs
- `notebooks/`: interactive validation notebooks
- `docs/`: references and worklogs

## Current Capabilities

- Fetch ETF daily price data for configured country-focused tickers.
- Include valid LSE ETFs across `GBP`/`GBp`/`USD`/`EUR` (no GBP-only exclusion).
- ETF metadata export includes `total_assets`, `net_assets`, and selected `fund_size`.
- Dashboard default ticker selection for multi-ticker countries:
  - prefer `USD` ticker first
  - if no USD ticker exists, choose largest `fund_size`
- Fetch IMF WEO indicators `NGDPD`, `NGDP`, and `NGDP_RPCH` for mapped countries.
- Build annual ETF return output merged with GDP metrics.
  - combined annual output now includes `etf_currency`
- Run full pipeline from one command via `main.py`.
- Build an interactive Excel KPI dashboard (MVP) for stakeholder review with:
  - country-level CAGR disconnect screener sheet with selectable horizon (1Y/3Y/5Y/10Y, default 5Y)
  - country focus panel is on the same sheet (`Country_CAGR_Summary`) to the right of the screener
  - screener includes ticker currency column and country focus controls (country, auto ticker, as-of date, ticker currency)
  - annual panel shows real GDP, nominal GDP (LCU), nominal GDP (USD), and `Nominal USD GDP - ETF`
  - annual panel keeps last 10 completed years and adds one projection/YTD row (for 2026 while in 2026)
  - CAGR panel shows real GDP, nominal GDP (LCU), nominal GDP (USD), and `Nominal USD GDP - ETF`
  - ETF-only cumulative returns (YTD, 1M, 3M, 6M, 1Y, 3Y, 5Y, 10Y, MAX)
  - final-sheet delta columns compute directly from in-row values (`Nominal USD GDP - ETF = O - L`) to avoid lookup mismatch
  - table widths auto-fit to table ranges (explainer cells do not drive column widths)
- Build a separate Excel workbook with one full-history ETF chart sheet per ticker.
  - chart workbook sheet columns are auto-fit
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
- `NGDP` (GDP current domestic-currency level)
- `NGDP_RPCH` (real GDP growth %)
- `NGDP_PCH` (nominal GDP growth in domestic currency %, derived from `NGDP`)
- `NGDPD_PCH` (nominal GDP growth %, derived from `NGDPD`)

## Validation Notebook

Run Jupyter and open `notebooks/etf_return_validation.ipynb`:

```bash
uv run jupyter notebook
```

## Outputs

- `data/outputs/etf_prices.csv`
- `data/outputs/etf_ticker_metadata.csv`
- `data/outputs/weo_gdp.csv`
- `data/outputs/etf_weo_combined_annual.csv`
- `data/outputs/etf_gdp_dashboard_mvp.xlsx`
- `data/outputs/etf_price_history_charts.xlsx`

## Current Eligibility Policy

When screening candidate ETFs for inclusion in mapping updates, current hard checks are:
- `exchange == LSE`
- `quoteType == ETF`
- earliest available Yahoo history date `<= 2020-01-01`
- exclude only explicit distributing classes (`Dist` / `Distributing` in ETF name)

Preference (not exclusion):
- prefer `USD` where multiple eligible tickers exist for a country
