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
- Include valid ETFs across LSE + NYSE/Nasdaq Yahoo exchange codes, with currencies `GBP`/`GBp`/`USD`/`EUR`.
- Apply automatic inclusion filters before downstream outputs:
  - minimum non-null close rows (default `252`)
  - maximum staleness in days from latest close (default `45`)
  - minimum acceptable first close date (default `2020-01-01`)
  - only `included=yes` tickers flow into combined outputs and dashboard sheets
- ETF metadata export includes `total_assets`, `net_assets`, and selected `fund_size`.
  - metadata also records `history_start_date`, `history_end_date`, `history_rows`, `history_stale_days`, `included`, `reason`
- Dashboard default ticker selection for multi-ticker countries:
  - prefer `USD` ticker first
  - if no USD ticker exists, choose largest `fund_size`
- Fetch IMF WEO indicators `NGDPD`, `NGDP`, and `NGDP_RPCH` for mapped countries.
- Build annual ETF return output merged with GDP metrics.
  - combined annual output now includes `etf_currency`
  - combined annual output now includes FX decomposition fields:
    - `etf_return_quote_pct`
    - `quote_ccy_vs_usd_pct`
    - `etf_return_usd_pct`
    - `country_lcu_vs_usd_weo_pct`
    - `etf_usd_minus_country_fx_pct`
  - combined annual output includes `currency_hedged` (name-based detection from Yahoo ETF names; `yes` / `no` / `unknown`)
- Run full pipeline from one command via `main.py`.
- Build an interactive Excel KPI dashboard (MVP) for stakeholder review with:
  - country-level CAGR disconnect screener sheet with selectable horizon (1Y/3Y/5Y/10Y, default 5Y)
  - per-country ticker dropdowns in screener rows (`ticker_used`) so ticker choice is user-controlled
  - screener `ticker_currency` and `ticker_exchange` update from selected ticker dropdown
  - country focus panel ticker dropdown depends on selected country and cascades to linked ETF/GDP tables
  - country focus controls include country, ticker, as-of date, ticker currency, and ticker exchange
  - screener `ticker_exchange` values are human-readable (for example `NYSE Arca`, `London Stock Exchange`)
  - country focus panel is on the same sheet (`Country_CAGR_Summary`) below the screener (with row gap separation)
  - annual panel FX decomposition columns (`Quote CCY vs USD %`, `ETF Return % (USD)`, `Country LCU vs USD % (WEO)`, `ETF USD - Country FX %`) render only for non-USD ticker selections
  - annual panel shows real GDP, nominal GDP (LCU), nominal GDP (USD), and `Nominal USD GDP - ETF`
  - annual panel keeps last 10 completed years and adds one projection/YTD row (for 2026 while in 2026)
  - CAGR panel shows real GDP, nominal GDP (LCU), nominal GDP (USD), and `Nominal USD GDP - ETF`
  - ETF-only cumulative returns (YTD, 1M, 3M, 6M, 1Y, 3Y, 5Y, 10Y, MAX)
  - final-sheet delta columns compute directly from in-row values (`Nominal USD GDP - ETF`) to avoid lookup mismatch
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

Optional preflight for mapped or candidate tickers:

```bash
uv run python src/fetch_etf_prices.py --inspect-only
uv run python src/fetch_etf_prices.py --inspect-only --candidate-tickers CMIB.L,EWJ,EWU --inspect-output data/outputs/ticker_candidate_preflight.csv
```

Optional filter overrides:

```bash
uv run python src/fetch_etf_prices.py \
  --min-history-start 2020-01-01 \
  --min-history-rows 252 \
  --max-stale-days 45
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
- `exchange` in `{LSE, PCX, NYQ, ASE, NMS, NGM, NCM, NAS}` (Yahoo exchange codes for LSE + NYSE/Nasdaq families)
- `quoteType == ETF`
- earliest available Yahoo history date `<= 2020-01-01` (default, configurable)
- history has at least `252` non-null close rows (default, configurable)
- latest close is no more than `45` days stale (default, configurable)
- exclude only explicit distributing classes (`Dist` / `Distributing` in ETF name)

Currency-hedged metadata:
- metadata file includes `currency_hedged` and `currency_hedged_basis`
- current detection is name-marker based (for example contains `hedged` / `currency hedged`)
- this is heuristic and should be treated as advisory unless manually validated

Preference (not exclusion):
- prefer `USD` where multiple eligible tickers exist for a country
