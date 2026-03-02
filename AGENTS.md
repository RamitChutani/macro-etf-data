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
The target output is a CSV or Excel workbook for internal use at a wealth management firm, with data tables and a dashboard view (second sheet when using Excel).  
The stakeholder uses this output to compare ETF performance versus underlying country performance and identify potential market mispricing for further investigation and investment decision support.  
The solution must remain extensible so additional dashboard variables can be added later based on stakeholder requirements.

### Scope

- In scope:
  - Automated ETF data retrieval from `yfinance` for selected tickers
  - Integration of country-level macro data from an approved source (source currently undecided)
  - Output generation as CSV and/or Excel (including a dashboard sheet for Excel outputs)
  - Python environment managed with `uv` and `pyproject.toml`
- Out of scope (current state):
  - Production API/service layer
  - Fully productionized scheduled orchestration
  - Database persistence layer
  - External client-facing productization (internal decision-support tool only)

### Success Criteria

- Pipeline runs end-to-end in the project environment and refreshes ETF + macro datasets without manual data edits.
- Output is generated in at least one supported format (`.csv` or `.xlsx`), and Excel mode contains:
  - one sheet with tabular data
  - one sheet with dashboard-ready views/metrics
- Dataset includes consistent date alignment and country/ticker mappings needed for ETF-vs-macro comparison.
- Dashboard design supports adding new stakeholder-requested variables without rewriting the full pipeline.
- Changes do not silently alter ticker universe, macro series definitions, or output schema without explicit documentation.

---

## 2. Current State Assessment

This section describes current reality as of March 2, 2026.

- Existing architecture:
  - Flat repository with notebook-first workflow.
  - `yf_data.ipynb` contains the effective business logic (ticker list, ETF download, frame shaping, CSV export).
  - `main.py` exists but only prints a hello-world message and is not part of the data pipeline.
  - `etf_prices.csv` is a large checked-in artifact used as current output.
- Known inconsistencies/technical debt:
  - Macro data retrieval is not implemented yet; only ETF price extraction exists.
  - Data source for macro series is still undecided, so ingestion contracts are not defined.
  - Notebook comments indicate a simplified adjusted-close-only schema, but current CSV includes a much wider schema with multiple field/index variants (including volume-derived columns), indicating artifact/code drift across runs.
  - No formal module boundaries; logic, experimentation, and output generation are mixed in notebook cells.
  - README is minimal and does not document run instructions, data contract, or update policy.
  - No automated test suite currently present.
- Areas that must remain stable:
  - Existing ticker dictionary semantics (country-to-ticker mapping) unless explicitly changed.
  - CSV output remains consumable by downstream analysis workflows.
  - Python 3.12+ compatibility and current dependency manager (`uv`).
- Areas intentionally marked for future refactor:
  - Possible extraction of notebook logic into importable Python modules/scripts.
  - Formalization of macro-data ingestion once source/provider is selected.
  - Formalization of output schema, dashboard metric definitions, and validation checks.
- Constraints imposed by legacy decisions:
  - Current behavior and data lineage are tied to notebook execution order/state.
  - Generated CSV may reflect prior logic versions and should be treated as derived, not source-of-truth logic.
- Undocumented conventions currently in use:
  - Date window defaults to `start = "2015-01-01"` and dynamic end date (`today`) in notebook.
  - Output file path defaults to repository root (`etf_prices.csv`).
  - Country-ticker mapping currently lives inline in notebook code.

---

## 3. Technical Context

### Stack

- Language: Python (3.12+)
- Framework: Jupyter Notebook workflow (no web framework)
- Runtime: Local Python virtual environment (`.venv`) and `uv` project tooling
- Database: None
- Infrastructure: Local filesystem artifacts only

### Environment

- Development setup assumptions:
  - `uv` is available for dependency/environment management.
  - Notebook is run from repository root so relative export path is stable.
- OS assumptions:
  - No strict OS lock-in, but current workflow is validated on Linux-like shell environments.
- Deployment target:
  - Local development and local artifact generation.
- Tooling:
  - Package/dependency management: `uv`, `pyproject.toml`, `uv.lock`
  - Analysis/data tooling: `jupyter`, `pandas`, `yfinance`, `matplotlib`
  - No enforced linter/formatter/test runner configured yet

---

## 4. Architectural Rules (Project-Specific)

- Treat `yf_data.ipynb` as the current canonical pipeline implementation unless the user explicitly approves migration to scripts/modules.
- Keep data acquisition logic and ticker definitions deterministic within a run; avoid hidden randomness or non-repeatable sampling.
- Do not introduce new folder/module structures proactively; architecture is evolving and requires explicit user sign-off before structural changes.
- Preserve output file naming/location conventions unless change is explicitly requested.
- Keep external data fetch boundaries explicit (`yfinance` only unless approved otherwise).
- Keep dashboard variables and derived metrics explicitly defined and traceable to source columns/series.

---

## 5. Code Conventions (Local Overrides Only)

- Use clear dataset column naming when adding new derived fields; include source ticker or metric family in the column name.
- Prefer explicit date fields (`Date`, `Year`, `Month`) for exported tabular outputs.
- In notebook code, keep one logical operation block per cell (ingest, transform, export) to reduce execution-order ambiguity.

---

## 6. Safety & Boundaries

- Ask for approval before structural refactors (file/folder reorganization, notebook-to-package conversion, major pipeline rewrites).
- Treat `etf_prices.csv` as a generated artifact; regenerate intentionally and avoid accidental churn.
- Treat external API responses from `yfinance` as untrusted and potentially incomplete; handle missing fields defensively.
- Treat macroeconomic source data as untrusted and version-sensitive; validate units/frequency before merge.
- Do not add auto-download side effects to `main.py` or import-time code without explicit request.

---

## 7. Dependency Policy

Clarify project bias:

- External dependencies are allowed when directly justified by data acquisition or analysis needs.
- Prefer minimizing dependency count because current project is small and notebook-centric.
- Current phase is exploratory/stability-balanced: fast iteration is acceptable, but avoid unnecessary framework/tooling sprawl.
- Long-term maintainability matters; add dependencies only if they reduce complexity or improve reproducibility.

---

## 8. Performance Profile

Performance is secondary at current project stage.

- Priorities:
  - Determinism and reproducibility of dataset shape
  - Simplicity over micro-optimization
- Non-priorities (for now):
  - Low-latency execution
  - Benchmark-driven optimization

---

## 9. Testing Expectations

- Unit tests required: No (not currently enforced)
- Integration tests required: No (not currently enforced)
- Edge case expectations:
  - Validate handling of missing/empty ticker data from upstream API.
  - Validate output includes expected date columns and non-empty row count.
- Mocking allowed: Yes, if tests are introduced.
- Deterministic test requirement: Yes for any future automated tests.
- Manual validation (current enforcement):
  - Run notebook end-to-end.
  - Confirm `etf_prices.csv` is produced and readable.
  - Spot-check sample columns and date range for plausibility.

---

## 10. Change Discipline (Local)

Conservative.

- Default to minimal, targeted edits.
- Refactors within a touched cell/file are acceptable only when required to complete the requested task safely.
- Any structural refactor requires explicit user approval before implementation.

---

## 11. Open Questions / Design Tensions

- Notebook-first workflow vs modular Python package pipeline.
- Which macro data source to use (for example FRED, World Bank, IMF, OECD) and what licensing/access constraints apply.
- Source of truth for schema: notebook comments/current logic vs existing checked-in CSV shape.
- Should ticker universe live in code, config file, or external data source.
- Policy for regenerating and versioning large data artifacts in git.
- How dashboard metrics should be prioritized for lead-generation vs portfolio decision support.
- Whether to add automated validation/tests before further feature growth.

---

## 12. Evolution Log (Optional but Recommended)

- v0.1 - Initial repository created with Python project scaffolding and placeholder `main.py`.
- v0.2 - Data workflow implemented in `yf_data.ipynb` using `yfinance` and `pandas`.
- v0.3 - CSV artifact (`etf_prices.csv`) committed as generated output; schema drift now exists between notebook intent comments and current artifact shape.
