#!/usr/bin/env python3
"""Run the macro ETF data pipeline end-to-end from one command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(cmd: list[str]) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Orchestrate ETF fetch, WEO fetch, and combined annual dataset build."
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Optional ETF start date (YYYY-MM-DD). If omitted, fetches full ETF history.",
    )
    parser.add_argument("--end-date")
    parser.add_argument(
        "--snapshot-date",
        default="2026-02-27",
        help=(
            "Snapshot end date for ETF history (YYYY-MM-DD). Default: 2026-02-27 (MSCI factsheet date). "
            "Filters ETF output to end on or before this date for consistent comparison with MSCI data. "
            "Change only when explicitly needed."
        ),
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2029)
    parser.add_argument("--etf-output", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-output", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--reer-output", default="data/outputs/bis_reer_metrics.csv")
    parser.add_argument("--fx-output", default="data/outputs/fx_prices.csv")
    parser.add_argument("--crude-impact-output", default="data/outputs/crude_oil_import_impact.csv")
    parser.add_argument(
        "--metadata-output",
        default="data/outputs/etf_ticker_metadata.csv",
    )
    parser.add_argument("--combined-output", default="data/outputs/etf_weo_combined_annual.csv")
    parser.add_argument("--dashboard-output", default="data/outputs/etf_gdp_dashboard_mvp.xlsx")
    parser.add_argument("--html-output", default="data/outputs/etf_macro_dashboard.html")
    parser.add_argument(
        "--history-charts-output",
        default="data/outputs/etf_price_history_charts.xlsx",
    )
    parser.add_argument(
        "--skip-dashboard",
        action="store_true",
        help="Skip Excel MVP dashboard generation step.",
    )
    parser.add_argument(
        "--skip-html",
        action="store_true",
        help="Skip interactive HTML dashboard generation step.",
    )
    parser.add_argument(
        "--skip-history-charts",
        action="store_true",
        help="Skip separate ETF history-charts workbook generation step.",
    )
    args = parser.parse_args()

    py = sys.executable

    etf_cmd = [
        py,
        str(script_dir / "fetch_etf_prices.py"),
        "--output",
        args.etf_output,
        "--metadata-output",
        args.metadata_output,
    ]
    if args.start_date:
        etf_cmd.extend(["--start", args.start_date])
    if args.end_date:
        etf_cmd.extend(["--end", args.end_date])
    if args.snapshot_date:
        etf_cmd.extend(["--snapshot-date", args.snapshot_date])

    weo_cmd = [
        py,
        str(script_dir / "fetch_weo_gdp.py"),
        "--start-year",
        str(args.start_year),
        "--end-year",
        str(args.end_year),
        "--output",
        args.weo_output,
    ]

    reer_cmd = [
        py,
        str(script_dir / "fetch_bis_reer.py"),
        "--output",
        args.reer_output,
    ]

    fx_cmd = [
        py,
        str(script_dir / "fetch_fx_prices.py"),
        "--metadata",
        args.metadata_output,
        "--output",
        args.fx_output,
    ]

    crude_impact_cmd = [
        py,
        str(script_dir / "build_crude_oil_import_impact_v2.py"),
        "--crude-csv",
        "data/inputs/crude oil data_WITS-By-HS6Product (1).xlsx",
        "--gas-csv",
        "data/inputs/natural gas data_WITS-By-HS6Product.xlsx",
        "--weo-csv",
        args.weo_output,
        "--output",
        args.crude_impact_output,
    ]

    combined_cmd = [
        py,
        str(script_dir / "build_combined_etf_weo.py"),
        "--etf-csv",
        args.etf_output,
        "--weo-csv",
        args.weo_output,
        "--metadata-csv",
        args.metadata_output,
        "--output",
        args.combined_output,
    ]

    run_step(etf_cmd)
    run_step(weo_cmd)
    run_step(reer_cmd)
    run_step(fx_cmd)
    run_step(crude_impact_cmd)
    run_step(combined_cmd)
    if not args.skip_dashboard:
        dashboard_cmd = [
            py,
            str(script_dir / "build_excel_dashboard_mvp.py"),
            "--etf-csv",
            args.etf_output,
            "--weo-csv",
            args.weo_output,
            "--metadata-csv",
            args.metadata_output,
            "--crude-impact-csv",
            args.crude_impact_output,
            "--output",
            args.dashboard_output,
        ]
        run_step(dashboard_cmd)
    if not args.skip_html:
        html_cmd = [
            py,
            str(script_dir / "build_html_dashboard.py"),
            "--etf-csv",
            args.etf_output,
            "--weo-csv",
            args.weo_output,
            "--metadata-csv",
            args.metadata_output,
            "--output",
            args.html_output,
        ]
        run_step(html_cmd)
    if not args.skip_history_charts:
        history_cmd = [
            py,
            str(script_dir / "build_etf_history_charts_workbook.py"),
            "--etf-csv",
            args.etf_output,
            "--output",
            args.history_charts_output,
        ]
        run_step(history_cmd)
    print("Pipeline completed.")


if __name__ == "__main__":
    main()
