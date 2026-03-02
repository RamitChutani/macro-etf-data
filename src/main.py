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
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--etf-output", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-output", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--combined-output", default="data/outputs/etf_weo_combined_annual.csv")
    args = parser.parse_args()

    py = sys.executable

    etf_cmd = [
        py,
        str(script_dir / "fetch_etf_prices.py"),
        "--start",
        args.start_date,
        "--output",
        args.etf_output,
    ]
    if args.end_date:
        etf_cmd.extend(["--end", args.end_date])

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

    combined_cmd = [
        py,
        str(script_dir / "build_combined_etf_weo.py"),
        "--etf-csv",
        args.etf_output,
        "--weo-csv",
        args.weo_output,
        "--output",
        args.combined_output,
    ]

    run_step(etf_cmd)
    run_step(weo_cmd)
    run_step(combined_cmd)
    print("Pipeline completed.")


if __name__ == "__main__":
    main()
