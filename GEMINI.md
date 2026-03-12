# GEMINI.md

## Project Overview
**macro-etf-data** is a Python-based data pipeline designed for a wealth management firm to compare ETF performance against country-level macroeconomic indicators (IMF WEO GDP). It automates data retrieval, merges datasets, and generates interactive dashboards (Excel/HTML) to identify market mispricing.

- **Primary Stack:** Python 3.12, `uv` for dependency management.
- **Data Sources:** Yahoo Finance (`yfinance`), IMF WEO (October 2025 baseline).
- **Architecture:** Script-first workflow (`src/`) with local artifact outputs (`data/outputs/`).

---

## Building and Running

### Setup
Ensure `uv` is installed, then run any command via `uv run` to handle the virtual environment automatically.

### Full Pipeline
To refresh the entire dataset and regenerate all dashboards:
```bash
uv run python src/main.py
```

### Individual Steps
- **Fetch ETF Prices:** `uv run python src/fetch_etf_prices.py`
- **Fetch IMF Macro:** `uv run python src/fetch_weo_gdp.py`
- **Build Combined Data:** `uv run python src/build_combined_etf_weo.py`
- **Build Excel Dashboard:** `uv run python src/build_excel_dashboard_mvp.py`
- **Build Chart Workbook:** `uv run python src/build_etf_history_charts_workbook.py`

### Interactive Validation
Use the Jupyter notebook for deep-dive checks and return validation:
```bash
uv run jupyter notebook notebooks/etf_return_validation.ipynb
```

---

## Development Conventions

### 1. Canonical Sources
- **Mappings:** `src/etf_mapping.py` is the single source of truth for country-to-ticker and ISO3 mappings.
- **Macro Baseline:** IMF World Economic Outlook October 2025 (do not switch without explicit instruction).

### 2. Ticker Selection Policy (Hard Gates)
ETFs must meet these criteria for inclusion in combined outputs:
- **Accumulating (Acc) Only:** Verified via yield/dividend history and name markers.
- **History Start:** Earliest close must be `<= 2016-01-01`.
- **History Volume:** Minimum `252` non-null close rows.
- **Staleness:** Latest close must be `< 45` days old.
- **Preferred Currency:** USD tickers are preferred over other currencies.

### 3. Output Standards
- **Formats:** Maintain CSV compatibility for downstream analysis and XLSX for stakeholder review.
- **Excel Dashboard:** Sheet 2 (`Country_CAGR_Summary`) contains the interactive screener and focus panels.
- **Structure:** Preserve the `data/outputs/` and `src/` directory separation.

---

## Agent Guidance (Project-Specific)
- **Inheritance:** Follow `BASE_AGENTS.md` and `AGENTS.md` for all behavioral and architectural rules.
- **Change Discipline:** Prioritize minimal, targeted edits. Propose structural refactors before execution.
- **Logging:** Maintain worklogs in `docs/worklog/` for every session.
- **Testing:** Validate changes by running the full pipeline and checking the integrity of generated artifacts in `data/outputs/`.
