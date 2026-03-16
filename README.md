# macro-etf-data

Python pipeline to fetch daily ETF prices from Yahoo Finance, fetch IMF WEO GDP data (Oct 2025 baseline), and build a merged annual ETF-vs-macro dataset.

## Repository Layout

- `src/`: pipeline scripts
  - `src/etf_mapping.py`: canonical country/ticker + ISO3 mappings (single source of truth)
  - `COUNTRY_TO_LCU`: country name to local currency unit (LCU) mapping for FX calculations
- `data/outputs/`: generated CSV outputs
- `notebooks/`: interactive validation notebooks
- `docs/`: references and worklogs

## Current Capabilities

- Fetch ETF daily price data for configured country-focused tickers.
- Include valid ETFs across LSE + NYSE/Nasdaq Yahoo exchange codes, with currencies `GBP`/`GBp`/`USD`/`EUR`.
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
- Fetch IMF WEO indicators `NGDPD`, `NGDP`, `NGDP_RPCH`, `PCPIPCH` (CPI inflation), and `NGDP_D` (GDP Deflator) for mapped countries.
- **Calculate Crude Oil Import Impact:**
  - Compute the economic sensitivity to oil price changes (Value of a $10/barrel price change in crude oil imports as % of nominal GDP).
  - Uses UN Energy Statistics (Metric tons, thousand) and WEO GDP (USD).
  - Includes full conversion steps: Metric Tons -> Barrels -> USD Value -> % GDP.
- **Fetch BIS REER (Real Effective Exchange Rate) monthly series and compute current deviation vs 10Y rolling average.**
- Build annual ETF return output merged with GDP metrics.
  - combined annual output now includes `etf_currency`
  - combined annual output now includes FX decomposition fields:
    - `etf_return_quote_pct`
    - `quote_ccy_vs_usd_pct`
    - `etf_return_usd_pct`
    - `country_lcu_vs_usd_weo_pct`
    - `country_lcu_vs_usd_10y_cagr`
    - `etf_usd_minus_country_fx_pct`
  - combined annual output includes `currency_hedged` (name-based detection from Yahoo ETF names; `yes` / `no` / `unknown`)
  - **combined annual output includes `country_lcu_vs_usd_jan1_pct` (Jan 1 point-to-point FX return for country LCU vs USD)**
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
  - **REER valuation metrics (Over/Under % vs 10Y average and Interpretation) integrated into the screener for valuation context.**
  - **Redundant currency columns (FX Decomposition) now automatically blank out if the ticker is already denominated in USD**
  - **Column headers are dynamic and show the specific quote currency (e.g., "ETF Return (GBP) %")**
  - final-sheet delta columns compute directly from in-row values (`Nominal USD GDP - ETF`) to avoid lookup mismatch
  - **New screener columns for valuation context (Main Area):**
    - `FX CAGR %`: Annualized currency movement against USD over selected horizon.
    - `Inf. Diff CAGR %`: Annualized difference between local and USA inflation CAGRs.
    - `Currency Gap %`: Sum of FX and Inflation CAGRs (Real currency valuation indicator).
    - `Oil Impact %`: Value of a $10/barrel price change in crude oil imports as % of nominal GDP.
  - **New Crude_Oil_Impact sheet:**
    - Detailed calculation steps for all countries (Metric Tons, Barrels, USD Value, GDP).
  - **New stakeholder documentation section:** 10 gap rows added between tables with detailed metric definitions.
  - table widths auto-fit to table ranges (explainer cells do not drive column widths)
- **FX Jan 1st CAGR Fix (v0.9):**
  - `FX Jan 1st CAGR %` now correctly uses **Country LCU vs USD** (not ETF quote currency).
  - Both `FX CAGR %` and `FX Jan 1st CAGR %` now measure the same underlying metric (country currency vs USD).
  - Values differ due to methodology: FX CAGR uses IMF WEO GDP levels (year-end), FX Jan 1st CAGR uses Yahoo FX (Jan 1 point-to-point).
- **Distributing ETF Support for Top 60 Economies (v0.10):**
  - Added 10 missing top 60 economies: Austria, Belgium, Bulgaria, Greece, Hong Kong, Italy, Kuwait, Netherlands, Singapore, Sweden.
  - These countries use **Distributing ETFs** with **Adjusted Close** prices for comparability with Accumulating ETFs.
  - Distributing tickers are marked with asterisk (*) in dashboard column B.
  - Ticker selection for multi-ticker countries uses largest AUM as decider.
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
uv run python src/fetch_bis_reer.py --output data/outputs/bis_reer_metrics.csv
uv run python src/build_crude_oil_import_impact.py --weo-csv data/outputs/weo_gdp.csv --output data/outputs/crude_oil_import_impact.csv
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
  --min-history-start 2016-01-01 \
  --min-history-rows 252 \
  --max-stale-days 45
```

WEO output now includes:
- `NGDPD` (GDP current USD level)
- `NGDP` (GDP current domestic-currency level)
- `NGDP_RPCH` (real GDP growth %)
- `PCPIPCH` (CPI inflation %)
- `NGDP_D` (GDP Deflator index)
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
- `data/outputs/bis_reer_metrics.csv`
- `data/outputs/crude_oil_import_impact.csv`
- `data/outputs/etf_weo_combined_annual.csv`
- `data/outputs/etf_gdp_dashboard_mvp.xlsx`
- `data/outputs/etf_price_history_charts.xlsx`

## Dashboard Conditional Formatting

The Excel dashboard (`etf_gdp_dashboard_mvp.xlsx`) uses color-coded conditional formatting:

**Main Metrics** (GDP CAGR, ETF CAGR, Macro Gap, Proj. 3Y, REER vs 10Y, GDP Real/LCU CAGR):
- 0% to 5%: Light green
- 5% to 10%: Dark green
- 10%+: Darker green
- Negative values: Red (same scale)

**BOE Price Impact (% of GDP)**:
Economic sensitivity to oil price changes, calculated using Barrels of Oil Equivalent (BOE):
- **Primary data source**: WITS 2024 crude oil + natural gas import data (individual countries only)
- **Fallback data source**: UN Energy Statistics (crude oil only, latest available year)
- **Data source selection rules**:
  1. Use WITS when BOTH crude oil AND natural gas data exist
  2. Use WITS when ONLY crude oil exists (no natural gas)
  3. Use UN fallback when ONLY natural gas exists (no crude oil)
  4. Use UN fallback when NEITHER exists
- **Yellow highlighting**: Indicates UN fallback data (not WITS)
- Crude oil: Kg → MT (÷1000) → bbl (×7.33 for WITS, ×7.53 for UN) → Mbbl (÷1,000,000)
- Natural gas: Kg → MT (÷1000) → bbl BOE (×8.4) → Mbbl BOE (÷1,000,000)
- Total BOE = Crude Oil + Natural Gas (in Mbbl/year)
- Impact % = (Total BOE × $10 / GDP_USD) × 100
- Lower values indicate less sensitivity to oil prices (closer to 0 is better)
- N/A for countries without any import data

**REER Index**:
- 100: No color (neutral, at 10-year average)
- 100-110: Light green (slightly above average)
- 110+: Dark green (significantly above average)
- 90-100: Light red (slightly below average)
- <90: Dark red (significantly below average)

## Dashboard Column Definitions

**Main Table (Columns A-I):**
- **Country**: Country name
- **Ticker**: ETF ticker (asterisk * indicates Distributing ETF using Adjusted Close)
- **GDP CAGR (USD)**: Annualized growth of the country's economy in USD terms
- **ETF CAGR (USD)**: Annualized ETF price return in USD terms (includes currency effects)
- **Macro Gap %**: GDP CAGR minus ETF CAGR. Positive = economy grew faster than market
- **BOE Price Impact (% of GDP)**: Economic sensitivity to $10/barrel oil price change using BOE methodology. Combines crude oil + natural gas imports (WITS 2024 data, UN fallback for some countries). Yellow highlight = UN fallback data. Lower = less sensitivity. N/A if no data.
- **Proj. 3Y (26-28)**: IMF forecast for nominal USD GDP growth (2026-2028)
- **REER vs 10Y**: REER deviation from 10-year mean. Positive = currency stronger than average
- **REER Index**: Current REER level. 100 = at 10-year average

**Reference Section (Columns M-V):**
- **Valuation**: Interpretation (near neutral / mild / meaningful over/undervaluation)
- **FX CAGR %**: Annualized currency movement vs USD
- **FX Jan 1st CAGR %**: Currency movement using Jan 1 point-to-point rates
- **Inf. Diff CAGR %**: Country inflation CAGR minus USA inflation CAGR
- **Currency Gap %**: FX CAGR + Inflation Differential (PPP alignment indicator)
- **Region, Exchange, Currency**: Ticker metadata
- **GDP Real CAGR, GDP LCU CAGR**: Additional GDP growth metrics

## Current Eligibility Policy

When screening candidate ETFs for inclusion in mapping updates, current hard checks are:
- `exchange` in `{LSE, PCX, NYQ, ASE, NMS, NGM, NCM, NAS}` (Yahoo exchange codes for LSE + NYSE/Nasdaq families)
- `quoteType == ETF`
- earliest available Yahoo history date `<= 2016-01-01` (default, configurable)
- history has at least `252` non-null close rows (default, configurable)
- latest close is no more than `45` days stale (default, configurable)
- **Primary standard is Accumulating (Acc) policy only** (verified against factsheets or 3yr dividend history).

Currency-hedged metadata:
- metadata file includes `currency_hedged` and `currency_hedged_basis`
- current detection is name-marker based (for example contains `hedged` / `currency hedged`)
- this is heuristic and should be treated as advisory unless manually validated

Preference (not exclusion):
- prefer `USD` where multiple eligible tickers exist for a country
- prefer LSE-listed UCITS (Ireland-domiciled) for tax efficiency and accumulation policy
