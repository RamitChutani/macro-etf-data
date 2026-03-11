# macro-etf-data

Python pipeline to fetch daily ETF prices from Yahoo Finance, fetch IMF WEO GDP data (Oct 2025 baseline), and build a merged annual ETF-vs-macro dataset.

## Repository Layout

- `src/`: pipeline scripts
  - `src/etf_mapping.py`: canonical country/ticker + ISO3 mappings (single source of truth)
- `data/outputs/`: generated CSV and Excel outputs
- `notebooks/`: interactive validation notebooks
- `docs/`: references and worklogs

## Current Capabilities

- Fetch ETF daily price data for configured country-focused tickers using **automatic split adjustment**.
- Include valid ETFs across LSE + NYSE/Nasdaq/Euronext Yahoo exchange codes, with currencies `GBP`/`GBp`/`USD`/`EUR`.
- Apply automatic inclusion filters before downstream outputs:
  - minimum non-null close rows (default `252`)
  - maximum staleness in days from latest close (default `45`)
  - **minimum acceptable first close date (default `2016-01-01`)**
  - only `included=yes` tickers flow into combined outputs and dashboard sheets
- ETF metadata export includes `total_assets`, `net_assets`, and selected `fund_size`.
  - metadata also records `history_start_date`, `history_end_date`, `history_rows`, `history_stale_days`, `included`, `reason`
- Dashboard default ticker selection for multi-ticker countries:
  - prefer `USD` ticker first
  - if no USD ticker exists, choose largest `fund_size`
- Fetch IMF WEO indicators `NGDPD`, `NGDP`, `NGDP_RPCH`, and **`PPPEX`** (PPP conversion rate) for mapped countries through **2029**.
- **Fetch IMF EER dataflow for Real Effective Exchange Rate (REER) indices** for trend validation.
- Build annual ETF return output merged with GDP metrics.
  - combined annual output now includes `etf_currency`
  - combined annual output now includes FX decomposition fields:
    - `etf_return_quote_pct`
    - `quote_ccy_vs_usd_pct`
    - `etf_return_usd_pct`
    - **`country_lcu_vs_usd_weo_pct` (Aligned: Positive = LCU strengthened)**
- Run full pipeline from one command via `main.py`.
- Build an interactive Excel KPI dashboard (MVP) for stakeholder review with:
  - **Country-level CAGR disconnect screener** with selectable horizon (1Y/3Y/5Y/10Y).
  - **2026-2029 Nominal GDP USD Forecasts** displayed in the screener table.
  - **Currency Valuation metrics** based on PPP Price Level Ratio deviations from 5-year averages.
  - Interactive highlights for toggle cells (Horizon and Country selector).
  - Professional styling with table borders and header-aligned column widths.
  - Annual panel shows real GDP, nominal GDP (LCU), nominal GDP (USD), and `Nominal USD GDP - ETF`.
  - CAGR panel shows real GDP, nominal GDP (LCU), nominal GDP (USD), and `Nominal USD GDP - ETF`.
- **Interactive HTML Dashboard (Prototype):**
  - Modern, dark-themed dashboard at `data/outputs/etf_macro_dashboard.html`.
  - Drill-down navigation: Click any country to see detailed short-term returns and annual macro decomposition.
  - Region-based filtering and Annual/CAGR horizon toggles.
- Build a separate Excel workbook with one full-history ETF chart sheet per ticker.
- Validate a single ticker interactively in notebook.

## Run Pipeline

1. Full pipeline (recommended):

```bash
uv run python src/main.py
```

This produces:
- `data/outputs/etf_gdp_dashboard_mvp.xlsx` (Excel Dashboard)
- `data/outputs/etf_macro_dashboard.html` (Interactive HTML Dashboard)
- `data/outputs/etf_price_history_charts.xlsx` (Chart Workbook)

2. Step-by-step (equivalent):

```bash
uv run python src/fetch_etf_prices.py --output data/outputs/etf_prices.csv
uv run python src/fetch_weo_gdp.py --start-year 2015 --end-year 2029 --output data/outputs/weo_gdp.csv
uv run python src/fetch_imf_reer.py # Optional: REER fetcher
uv run python src/build_combined_etf_weo.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_weo_combined_annual.csv
uv run python src/build_excel_dashboard_mvp.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_gdp_dashboard_mvp.xlsx
uv run python src/build_html_dashboard.py --output data/outputs/etf_macro_dashboard.html
```

## Outputs

- `data/outputs/etf_prices.csv`
- `data/outputs/etf_ticker_metadata.csv`
- `data/outputs/weo_gdp.csv` (Extended through 2029)
- `data/outputs/etf_weo_combined_annual.csv`
- `data/outputs/etf_gdp_dashboard_mvp.xlsx`
- `data/outputs/etf_macro_dashboard.html`
- `data/outputs/etf_price_history_charts.xlsx`

## Current Eligibility Policy

When screening candidate ETFs for inclusion in mapping updates, current hard checks are:
- `exchange` in `{LSE, PCX, NYQ, ASE, NMS, NGM, NCM, NAS, PAR, GER, EBS}`.
- `quoteType == ETF`.
- earliest available Yahoo history date `<= 2016-01-01` (Exception: `IKSA.L` allowed for 5Y depth).
- history has at least `252` non-null close rows.
- latest close is no more than `45` days stale.
- **Primary standard is Accumulating (Acc) policy only** (verified via dividend history proxy and name-marker detection).
- **History is fetched with `auto_adjust=True`** to ensure returns are not distorted by stock splits.
