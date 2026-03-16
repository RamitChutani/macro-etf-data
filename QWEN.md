# QWEN.md - Project Context for AI Assistant

## Project Overview

**macro-etf-data** is a Python pipeline that automates retrieval of ETF pricing data from Yahoo Finance and combines it with country-level macroeconomic indicators (IMF WEO GDP data, BIS REER, crude oil import data). The target output is CSV files and an interactive Excel KPI dashboard for internal use at a wealth management firm.

**Purpose:** Enable stakeholders to compare ETF performance versus underlying country economic performance and identify potential market mispricing for investment decision support.

**Current Version:** v0.8 (as of March 2026)

## Repository Structure

```
macro-etf-data/
├── src/                          # Core pipeline scripts
│   ├── main.py                   # Main orchestrator (run from here)
│   ├── etf_mapping.py            # Source of truth: country/ticker mappings
│   ├── fetch_etf_prices.py       # ETF price data from Yahoo Finance
│   ├── fetch_weo_gdp.py          # IMF WEO GDP data fetcher
│   ├── fetch_bis_reer.py         # BIS REER (Real Effective Exchange Rate) fetcher
│   ├── fetch_fx_prices.py        # FX rates fetcher
│   ├── build_crude_oil_import_impact.py  # Oil sensitivity calculations
│   ├── build_combined_etf_weo.py # Merges ETF + macro datasets
│   ├── build_excel_dashboard_mvp.py      # Excel KPI dashboard generator
│   ├── build_html_dashboard.py   # HTML dashboard generator
│   └── build_etf_history_charts_workbook.py  # Per-ticker chart workbook
├── data/
│   ├── inputs/                   # External data (e.g., UN crude oil imports)
│   └── outputs/                  # Generated artifacts (CSV, XLSX)
├── notebooks/
│   └── etf_return_validation.ipynb  # Interactive validation notebook
├── docs/
│   ├── reference/                # Reference documentation
│   └── worklog/                  # Session notes (dated)
├── pyproject.toml                # Project dependencies (uv-managed)
├── uv.lock                       # Locked dependency versions
└── .python-version               # Python version (3.12)
```

## Building and Running

### Environment Setup

```bash
# Python 3.12+ required (managed by uv)
uv sync  # Install dependencies from pyproject.toml
```

### Run Full Pipeline (Recommended)

```bash
uv run python src/main.py
```

This orchestrates all steps and produces:
- `data/outputs/etf_prices.csv`
- `data/outputs/etf_ticker_metadata.csv`
- `data/outputs/weo_gdp.csv`
- `data/outputs/bis_reer_metrics.csv`
- `data/outputs/fx_prices.csv`
- `data/outputs/crude_oil_import_impact.csv`
- `data/outputs/etf_weo_combined_annual.csv`
- `data/outputs/etf_gdp_dashboard_mvp.xlsx`
- `data/outputs/etf_macro_dashboard.html`
- `data/outputs/etf_price_history_charts.xlsx`

### Run Individual Steps

```bash
# ETF prices
uv run python src/fetch_etf_prices.py --output data/outputs/etf_prices.csv

# WEO GDP data
uv run python src/fetch_weo_gdp.py --start-year 2015 --end-year 2026 --output data/outputs/weo_gdp.csv

# BIS REER data
uv run python src/fetch_bis_reer.py --output data/outputs/bis_reer_metrics.csv

# Crude oil import impact
uv run python src/build_crude_oil_import_impact.py --weo-csv data/outputs/weo_gdp.csv --output data/outputs/crude_oil_import_impact.csv

# Combined annual dataset
uv run python src/build_combined_etf_weo.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_weo_combined_annual.csv

# Excel dashboard
uv run python src/build_excel_dashboard_mvp.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_gdp_dashboard_mvp.xlsx

# HTML dashboard
uv run python src/build_html_dashboard.py --etf-csv data/outputs/etf_prices.csv --weo-csv data/outputs/weo_gdp.csv --output data/outputs/etf_macro_dashboard.html

# History charts workbook
uv run python src/build_etf_history_charts_workbook.py --etf-csv data/outputs/etf_prices.csv --output data/outputs/etf_price_history_charts.xlsx
```

### Validation Notebook

```bash
uv run jupyter notebook
# Open: notebooks/etf_return_validation.ipynb
```

### Common CLI Options

```bash
# ETF fetch with custom date range
uv run python src/fetch_etf_prices.py --start 2020-01-01 --end 2025-12-31

# Skip dashboard generation
uv run python src/main.py --skip-dashboard

# Skip HTML dashboard
uv run python src/main.py --skip-html

# Skip history charts
uv run python src/main.py --skip-history-charts

# Inspect tickers without full fetch
uv run python src/fetch_etf_prices.py --inspect-only
```

## Key Technologies

| Category | Technology |
|----------|------------|
| Language | Python 3.12+ |
| Package Manager | uv |
| Data Processing | pandas |
| Data Sources | yfinance, IMF WEO API, BIS, UN Statistics |
| Output Formats | CSV, Excel (openpyxl), HTML |
| Validation | Jupyter notebooks |

## ETF Eligibility Criteria (Hard Gates)

Tickers must pass ALL checks to be included:

1. **Exchange:** LSE, PCX, NYQ, ASE, NMS, NGM, NCM, NAS (Yahoo codes)
2. **Quote Type:** Must be `ETF`
3. **History Start:** Earliest close date <= 2016-01-01
4. **History Length:** Minimum 252 non-null close rows
5. **Data Freshness:** Latest close within 45 days
6. **Distribution Policy:** Must be **Accumulating** (checked via 3yr dividend history / yield)

**Default Selection Priority** (for multi-ticker countries):
1. Currency: USD preferred
2. Fund Size: Largest AUM
3. Alphabetical

## Data Sources

| Source | Data Type | Baseline |
|--------|-----------|----------|
| Yahoo Finance | ETF daily prices, metadata | Real-time |
| IMF WEO | GDP (NGDPD, NGDP), Real GDP growth (NGDP_RPCH), CPI inflation (PCPIPCH), GDP Deflator (NGDP_D) | October 2025 |
| BIS | REER monthly series | Current |
| UN Statistics | Crude oil imports (metric tons) | Latest available |

## Output Schema Highlights

### etf_prices.csv
- Columns: `Date`, plus per-ticker price columns (`<Label> - <TICKER> - Close/Adj Close`)

### etf_ticker_metadata.csv
- Columns: `ticker`, `exchange`, `currency`, `total_assets`, `net_assets`, `fund_size`, `history_start_date`, `history_end_date`, `history_rows`, `history_stale_days`, `included`, `reason`, `currency_hedged`

### weo_gdp.csv
- Columns: `country_code`, `country_name`, `indicator`, `year`, `value`

### etf_weo_combined_annual.csv
- Merged annual ETF returns with GDP metrics
- Includes FX decomposition columns for non-USD tickers
- Includes `currency_hedged` flag

## Excel Dashboard Features

### Sheet 1: Country CAGR Summary (Screener)
- Selectable horizon (1Y/3Y/5Y/10Y, default 5Y)
- Per-country ticker dropdowns
- CAGR columns: Real GDP, Nominal GDP (LCU/USD), ETF Return, Disconnect
- Valuation context: REER Over/Under %, FX CAGR %, Inflation Diff CAGR %, Currency Gap %, Oil Impact %

### Sheet 2: Country Focus Panel
- Country/ticker/date selectors
- Linked ETF/GDP tables
- Annual panel (last 10 years + projection)
- FX decomposition (for non-USD tickers)

## Development Conventions

### Code Style
- Clear dataset column naming with source ticker/metric family
- Explicit date fields (`Date`, `Year`, `Month`) in outputs
- Notebook code: one logical operation block per cell

### Architectural Rules
- `src/etf_mapping.py` is the **source of truth** for country/ticker mappings
- Treat `.py` scripts as canonical pipeline implementation
- Treat `etf_return_validation.ipynb` as validation/debug surface
- Keep data acquisition logic deterministic within a run
- Preserve output file naming/location conventions
- Pin macro baseline to IMF WEO October 2025

### Change Discipline
- Default to minimal, targeted edits
- **Ask for approval before structural refactors**
- Treat data artifacts as generated; regenerate intentionally
- Do not silently alter ticker universe, macro series, or output schema without documentation

### Session Notes
- Keep work notes under `docs/worklog/` with format `session-YYYY-MM-DD.md`

## Known Issues / Technical Debt

1. **Yahoo History Level Breaks:** Some tickers show unexplained level breaks; return calculations need defensive checks
2. **Currency Hedged Detection:** Currently name-matching heuristics; treat "unknown" flags cautiously
3. **Excel Chart Rendering:** Negative annual/CAGR chart rendering unreliable in some environments
4. **Schema Validation:** No formal validation module yet (future refactor candidate)

## Testing / Validation

No formal unit tests. Validate via:

1. **End-to-end run:** `uv run python src/main.py`
2. **Verify outputs:** Check all CSV/XLSX files are readable
3. **Notebook validation:** Run `notebooks/etf_return_validation.ipynb` for deep checks
4. **Manual inspection:** Review dashboard Excel for correct formulas and formatting

## Country Coverage (38 countries)

Australia, Austria, Belgium, Brazil, Bulgaria, Canada, China, France, Germany, Greece, Hong Kong, India, Indonesia, Italy, Japan, Kuwait, Malaysia, Mexico, Netherlands, Pakistan, Philippines, Poland, Saudi Arabia, Singapore, South Africa, South Korea, Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, United Kingdom, United States, Vietnam

## Quick Reference

```bash
# Full pipeline with all outputs
uv run python src/main.py

# Pipeline without optional outputs (faster)
uv run python src/main.py --skip-dashboard --skip-html --skip-history-charts

# Validate a specific ticker interactively
uv run jupyter notebook  # Open etf_return_validation.ipynb

# Check available tickers
uv run python src/fetch_etf_prices.py --inspect-only
```
