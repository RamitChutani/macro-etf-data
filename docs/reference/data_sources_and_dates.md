# Data Sources and Reference Dates

**Last Updated:** March 18, 2026  
**Dashboard Version:** v0.11

This document tracks the source, reference date, and update frequency for all data used in the macro-etf-data dashboard.

---

## Quick Reference Table

| Data Type | As Of / Reference Period | Source | Update Frequency |
|-----------|-------------------------|--------|-----------------|
| ETF Prices | **Feb 27, 2026** (fixed snapshot) | Yahoo Finance | Daily (filtered to snapshot) |
| MSCI Returns | Feb 27, 2026 | MSCI Factsheet | Monthly |
| GDP (WEO) | Oct 2025 baseline | IMF WEO API | Semi-annual (Apr/Oct) |
| REER | **Feb 2026** | BIS API | Monthly (~6-8 week lag) |
| Oil Impact | 2024 | WITS / UN | Annual |
| FX Rates | Latest day | Yahoo Finance | Daily |
| Dashboard Date | Generation date | System date | Per run |

---

## Dashboard Filters

### Horizon Filter (Cell B2)
- **Options:** 1Y, 3Y, 5Y, 10Y
- **Default:** 10Y
- **Usage:** Select horizon from dropdown; all CAGR metrics update automatically

### Region Reference (Column Z)
- **Purpose:** Reference information showing which region each country belongs to
- **Regions:** Africa, Asia, Europe, Latin America, Middle East, North America, Oceania
- **Note:** This is reference data only, not a filter

---

## Detailed Data Sources

### 1. ETF Ticker Data

| Property | Value |
|----------|-------|
| **As of Date** | **February 27, 2026** (fixed snapshot date) |
| **Date Range** | Varies by ticker; minimum 252 trading days, earliest start 2016-01-01 |
| **Source** | Yahoo Finance (yfinance library) |
| **Update Frequency** | Daily (market days), filtered to snapshot date |
| **Price Type** | Close price for Accumulating ETFs; Adjusted Close for Distributing ETFs |
| **Currency** | ETF quote currency (USD, GBP, EUR, GBp) |
| **Script** | `src/fetch_etf_prices.py` (with `--snapshot-date 2026-02-27`) |
| **Output** | `data/outputs/etf_prices.csv`, `data/outputs/etf_ticker_metadata.csv` |

**Note:** The ETF data is filtered to end on February 27, 2026 (or the closest trading day on or before that date) to align with the MSCI factsheet date. This enables direct comparison between ETF returns and MSCI index returns.

**CAGR Methodology:**
- ETF CAGR is calculated using the exact snapshot date (Feb 27, 2026)
- For example, 5Y ETF CAGR uses Feb 27, 2021 → Feb 27, 2026
- This matches MSCI methodology for consistent comparison
- GDP CAGR uses calendar years (GDP is annual data): 2020 → 2025 for 5Y

**To change the snapshot date:** Modify the `--snapshot-date` default in `src/fetch_etf_prices.py` and `src/main.py`.

**Eligibility Criteria:**
- Exchange: LSE, PCX, NYQ, ASE, NMS, NGM, NCM, NAS (Yahoo codes)
- Quote Type: ETF
- History Start: <= 2016-01-01
- History Length: >= 252 non-null close rows
- Data Freshness: Latest close within 45 days
- Distribution Policy: Accumulating preferred (Distributing allowed for specific countries)

---

### 2. MSCI Index Returns

| Property | Value |
|----------|-------|
| **As of Date** | February 27, 2026 (file date) |
| **Return Periods** | 1-year, 3-year, 5-year, 10-year CAGR |
| **Source** | MSCI Factsheet data manual (provided file) |
| **Data Type** | Gross returns in USD (net returns used as fallback for Belgium, Greece) |
| **Coverage** | 55 countries (33 mapped to dashboard countries) |
| **Missing** | Bulgaria, Kuwait (no MSCI coverage) |
| **File** | `data/inputs/MSCI factsheet data manual_feb 27 2026.xlsx` |
| **Script** | `src/build_excel_dashboard_mvp.py` (load_msci_returns function) |

**Country Mapping:**
- 33 of 35 dashboard countries have MSCI data
- Bulgaria, Kuwait show NA() (no MSCI coverage)

---

### 3. GDP Data (IMF WEO)

| Property | Value |
|----------|-------|
| **Baseline** | IMF World Economic Outlook (WEO) **October 2025** edition |
| **Year Range** | 2015–2029 (historical + projections) |
| **Source** | IMF SDMX API |
| **Update Frequency** | Semi-annual (April and October) |
| **Script** | `src/fetch_weo_gdp.py` |
| **Output** | `data/outputs/weo_gdp.csv` |

**Indicators:**
| Code | Label | Description |
|------|-------|-------------|
| NGDPD | GDP, current prices (U.S. dollars) | Nominal GDP in USD |
| NGDP | GDP, current prices (domestic currency) | Nominal GDP in LCU |
| NGDP_RPCH | Real GDP growth (percent change) | Inflation-adjusted GDP growth |
| PCPIPCH | Inflation, average consumer prices (percent change) | CPI inflation rate |
| NGDP_D | Gross domestic product, deflator (index) | GDP deflator index |

**Projections:**
- 2025–2029 are IMF forecasts
- Updated semi-annually (April and October WEO releases)
- Next update: April 2026

---

### 4. BIS REER (Real Effective Exchange Rate)

| Property | Value |
|----------|-------|
| **As of Date** | **February 2026** (latest available; ~1-2 month publication lag) |
| **Data Range** | 2016-01-01 to current |
| **Source** | BIS Statistics API |
| **Metric** | REER index level (base year 2020=100) + project's custom 10-year average deviation |
| **Derived** | REER % difference vs 10-year average (custom valuation metric) |
| **Frequency** | Monthly |
| **Publication Lag** | ~6-8 weeks (BIS releases mid-month for prior month) |
| **Script** | `src/fetch_bis_reer.py` |
| **Output** | `data/outputs/bis_reer_metrics.csv` |

**Important:** The BIS REER uses **base year 2020=100**, not a rolling 10-year average. An index level of 120 means 20% appreciation since 2020. BIS explicitly states that REER levels "do not provide information concerning over- or undervaluation."

**Project's Custom Metric (REER vs 10Y):**
- The project calculates a custom deviation metric: `((current REER − 10yr average REER) / 10yr average REER) × 100`
- This shows how far the current REER deviates from its 10-year historical average
- Positive % = Currency stronger than its 10Y average
- Negative % = Currency weaker than its 10Y average
- This is a **heuristic overlay** for valuation context, not official BIS methodology

---

### 5. Crude Oil Import Impact

| Property | Value |
|----------|-------|
| **Data Year** | 2024 (latest available) |
| **Source** | **Primary:** WITS (World Integrated Trade Solution) 2024<br>**Fallback:** UN Energy Statistics (latest available) |
| **Metric** | Value of $10/barrel oil price change as % of GDP |
| **Methodology** | Barrels of Oil Equivalent (BOE): crude oil + natural gas converted to BOE |
| **Yellow Highlight** | Indicates UN fallback data (not WITS) |
| **Script** | `src/build_crude_oil_import_impact_v2.py` |
| **Output** | `data/outputs/crude_oil_import_impact.csv` |

**Data Source Selection Rules:**
1. Use WITS when BOTH crude oil AND natural gas data exist
2. Use WITS when ONLY crude oil exists (no natural gas)
3. Use UN fallback when ONLY natural gas exists (no crude oil)
4. Use UN fallback when NEITHER exists

**UN Fallback Countries:** Brazil, Spain, United Kingdom, Indonesia, Mexico, Philippines, Turkey, Vietnam

---

### 6. FX Rates

| Property | Value |
|----------|-------|
| **Spot Rates** | Latest available (today/yesterday) |
| **Historical** | Daily data from Yahoo Finance |
| **Source** | yfinance (CCYUSD=X or USDCCY=X pairs) |
| **Usage** | • ETF currency conversion to USD<br>• FX CAGR calculations<br>• Jan 1st point-to-point FX returns |
| **Script** | `src/fetch_fx_prices.py` |
| **Output** | `data/outputs/fx_prices.csv` |

---

### 7. Dashboard "As Of" Date

| Property | Value |
|----------|-------|
| **Display Date** | Current date (date when dashboard was generated) |
| **Location** | Cell A1 of Comparing Countries sheet |
| **Format** | "Country Disconnect Dashboard (As of Mar 18, 2026)" |
| **Script** | `src/build_excel_dashboard_mvp.py` |

---

## Update Schedule

| Data Source | Next Expected Update | Notes |
|-------------|---------------------|-------|
| ETF Prices | Daily (market days) | Automatic via yfinance |
| MSCI Returns | Monthly (factsheet release) | Manual file update required |
| GDP (WEO) | April 2026 | IMF WEO Spring Meetings |
| REER (BIS) | **Mid-April 2026** (for March 2026 data) | Monthly, ~6-8 week publication lag |
| Oil Impact | Annual (Q2) | WITS/UN data lag ~1 year |
| FX Rates | Daily | Automatic via yfinance |

---

## Version History

| Date | Change |
|------|--------|
| 2026-03-18 | Initial documentation created |
| 2026-03-18 | MSCI data added (Feb 27, 2026 factsheet) |

---

## Notes

- **ETF prices** reflect the most recent trading day when the pipeline was run
- **MSCI data** is from a static factsheet file; update by replacing the input file
- **GDP projections** (2025-2029) are IMF forecasts, not actual data
- **REER data** has a ~6-8 week publication lag from BIS (e.g., February 2026 data available in late March 2026)
- **Oil import data** has approximately 1-year lag (2024 data available in 2025-2026)
