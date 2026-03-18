# AGENTS.md

Project-Level Agent Configuration

---

## 0. Inheritance

This project follows the principles defined in:

`~/ai-config/BASE_AGENTS.md`

This file defines only project-specific context, constraints, and overrides.

If a rule here conflicts with the base file, this file takes precedence for this project only.

---

## 1. Project Overview

### Purpose

This project is intended to automate retrieval of ETF pricing data for selected country-focused tickers from Yahoo Finance and combine it with country-level macroeconomic indicators (for example GDP).  
The target output is a CSV or Excel workbook for internal use at a wealth management firm, with data tables and an interactive Excel KPI dashboard (second sheet when using Excel) that supports slicers/filters and linked visuals.  
The stakeholder uses this output to compare ETF performance versus underlying country performance and identify potential market mispricing for further investigation and investment decision support.  
The solution must remain extensible so additional dashboard variables can be added later based on stakeholder requirements.

### Scope

- In scope:
  - Automated ETF data retrieval from `yfinance` for selected tickers
  - Integration of country-level macro data from IMF World Economic Outlook (October 2025 edition)
  - Output generation as CSV and/or Excel (including an interactive KPI dashboard sheet for Excel outputs)
  - Python environment managed with `uv` and `pyproject.toml`
- Out of scope (current state):
  - Production API/service layer
  - Fully productionized scheduled orchestration
  - Database persistence layer
  - External client-facing productization (internal decision-support tool only)

### Success Criteria

- Pipeline runs end-to-end in the project environment and refreshes ETF + macro datasets without manual data edits.
- IMF macro inputs are sourced from World Economic Outlook October 2025 data, including 2025 and 2026 GDP projections where available.
- Output is generated in at least one supported format (`.csv` or `.xlsx`), and Excel mode contains:
  - one sheet with tabular data
  - one sheet with interactive KPI dashboard views/metrics (filters/slicers and linked visuals)
- Dataset includes consistent date alignment and country/ticker mappings needed for ETF-vs-macro comparison.
- Dashboard design supports adding new stakeholder-requested variables without rewriting the full pipeline.
- Changes do not silently alter ticker universe, macro series definitions, or output schema without explicit documentation.

---

## 2. Current State Assessment

This section describes current reality as of March 6, 2026 (updated after Session 4 refinements).

- Existing architecture:
  - Script-first workflow with directory separation (`src/`, `data/outputs/`, `notebooks/`, `docs/`).
  - Core pipeline scripts live under `src/`: `fetch_etf_prices.py`, `fetch_weo_gdp.py`, `build_combined_etf_weo.py`, `build_excel_dashboard_mvp.py`, `main.py`.
  - `src/main.py` orchestrates end-to-end refresh (ETF -> WEO -> combined annual output).
  - Core artifacts: `etf_prices.csv`, `etf_ticker_metadata.csv`, `weo_gdp.csv`, `etf_weo_combined_annual.csv`, and `etf_gdp_dashboard_mvp.xlsx`.
- Recent hardening and refinements (v0.8):
  - **Strict Ticker Selection (Hard Gates):** Inception date must be <= 2016-01-01 and must be **Accumulating** (proxy checked via 3yr dividend history/yield).
  - **Dashboard Layout Alignment:** Flipped GDP/ETF columns in focus tables to match Screener (GDP first). Added vertical alignment gaps across all tables.
  - **Robustness:** Hardened Macro Disconnect formulas to handle non-existent ETF history (return 0% -> NA).
  - **Default Selection Priority:** Transitioned to Currency (USD pref) -> Fund Size (AUM) -> Alphabetical.
- Known inconsistencies/technical debt:
  - Upstream Yahoo history can include unexplained level breaks for some tickers; return calculations require defensive checks.
  - Currency hedged status is currently determined via name-matching heuristics; remain cautious of "unknown" flags.
  - Excel dashboard chart rendering for negative annual/CAGR values remains unreliable in some environments.
- Areas that must remain stable:
  - `src/etf_mapping.py` as the source of truth for country-to-ticker maps.
  - CSV outputs remain consumable by downstream analysis workflows.
  - Python 3.12+ compatibility and current dependency manager (`uv`).
- Areas intentionally marked for future refactor:
  - Formalization of output schema and validation checks into a dedicated module.
  - Extraction of shared return-validation logic from notebook into reusable Python modules.
- Constraints imposed by legacy decisions:
  - Generated CSVs reflect the current pipeline version and should be treated as derived artifacts.
- Undocumented conventions currently in use:
  - Quality gates: 252 rows min, 45 days staleness max, **2016-01-01** min start.

---

## 3. Technical Context

### Stack

- Language: Python (3.12+)
- Framework: Script-based CLI workflow with optional Jupyter notebook for validation
- Runtime: Local Python virtual environment (`.venv`) and `uv` project tooling
- Database: None
- Infrastructure: Local filesystem artifacts only

---

## 4. Architectural Rules (Project-Specific)

- Treat `.py` scripts as the canonical pipeline implementation.
- `src/etf_mapping.py` is the source of truth for country-to-ticker mappings.
- Treat `etf_return_validation.ipynb` as a validation/debug surface.
- Keep data acquisition logic and ticker definitions deterministic within a run.
- Do not introduce new folder/module structures proactively.
- Preserve output file naming/location conventions.
- Pin macro baseline to IMF World Economic Outlook October 2025.

---

## 5. Code Conventions (Local Overrides Only)

- Use clear dataset column naming; include source ticker or metric family.
- Prefer explicit date fields (`Date`, `Year`, `Month`) for exported tabular outputs.
- In notebook code, keep one logical operation block per cell.

---

## 6. Safety & Boundaries

- Ask for approval before structural refactors.
- Treat data artifacts as generated; regenerate intentionally.
- Keep session work notes under `docs/worklog/`.
- Validate IMF WEO units/frequency before merge.
- Do not silently switch IMF WEO edition/version.

---

## 7. Dependency Policy

- External dependencies are allowed when justified by data acquisition or analysis.
- Prefer minimizing dependency count.
- Add dependencies only if they reduce complexity or improve reproducibility.

---

## 8. Performance Profile

- Priorities: Determinism, reproducibility, and simplicity.
- Non-priorities: Low-latency execution, micro-optimization.

---

## 9. Testing Expectations

- Unit tests required: No (not currently enforced)
- Manual validation:
  - Run pipeline end-to-end (`uv run python src/main.py`).
  - Confirm `data/outputs/etf_prices.csv`, `data/outputs/etf_ticker_metadata.csv`, `data/outputs/weo_gdp.csv`, `data/outputs/etf_weo_combined_annual.csv`, and `data/outputs/etf_gdp_dashboard_mvp.xlsx` are produced and readable.
  - Use `notebooks/etf_return_validation.ipynb` for deep checks.

---

## 10. Change Discipline (Local)

- Default to minimal, targeted edits.
- Any structural refactor requires explicit user approval.
- **ALWAYS verify output before committing:**
  - After making changes, run the code and print the output
  - Show the user the output (tables, structures, values) for verification
  - Wait for explicit user approval ("ok", "proceed", "commit") before committing
  - This applies to ALL changes: code, documentation, data files, dashboards

---

## 11. Open Questions / Design Tensions

- Script-first workflow vs full modular package structure.
- Source of truth for schema validation.
- Policy for versioning large data artifacts in git.

---

## 12. Evolution Log (Optional but Recommended)

- v0.1 - Initial repository created.
- v0.2 - Data workflow implemented in notebook.
- v0.3 - CSV artifacts committed.
- v0.4 - Pipeline migrated to script-first flow.
- v0.5 - Added validation notebook.
- v0.6 - Added metadata enrichment and quality gates.
- v0.7 - Reformatted dashboard layout and unified USD-based returns.
- v0.8 - Hardened selection (2016 start, Accumulating only) and aligned dashboard focus tables.
- **v0.9 (2026-03-16) - FX Jan 1st CAGR Fix:**
  - Fixed `FX Jan 1st CAGR %` to use Country LCU vs USD (was incorrectly using ETF quote currency).
  - Added `COUNTRY_TO_LCU` mapping to `src/etf_mapping.py`.
  - Added `country_lcu_vs_usd_jan1_pct` column to combined output CSV.
  - Fixed syntax error in `src/build_combined_etf_weo.py`.
- **v0.10 (2026-03-16) - Distributing ETF Support for Top 60 Economies:**
  - Added 10 missing top 60 economies (Austria, Belgium, Bulgaria, Greece, Hong Kong, Italy, Kuwait, Netherlands, Singapore, Sweden).
  - Added `ALLOW_DIST_COUNTRIES` set to allow Distributing ETFs for specific countries.
  - Distributing ETFs use Adjusted Close price for comparability with Accumulating ETFs.
  - Dashboard marks distributing tickers with asterisk (*) and includes definition.
- **v0.11 (2026-03-18) - Dashboard Restructure to Match Reference Format:**
  - Split single `Country_CAGR_Summary` sheet into two dedicated sheets:
    - `Comparing Countries`: Country screener with reference-format column order and grouping
    - `Country Focus`: Interactive single-country detail panel with three sections (ETF returns, annual decomposition, CAGR comparison)
  - Added `get_spot_fx_rates()` function to fetch latest FX spot rates from yfinance
  - Added `write_comparing_countries_sheet()` and `write_country_focus_sheet()` functions
  - Aligned column names and order with reference dashboard format
  - Added placeholder columns for MSCI Index Returns and FX Futures rates (hidden)
  - Populated nGDP (USD) 2025 levels from WEO data
  - Populated USD/LCU spot rates from yfinance
  - Maintains 6 underlying data sheets: Crude_Oil_Impact, ETF_Timeframes, Annual, CAGR, REER_Data, Lists
