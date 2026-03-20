#!/usr/bin/env python3
"""Extract FX forward rates and spot rates from stakeholder reference dashboard.

This is a one-time extraction script to populate fx_forwards_manual.csv
with the 33 countries that have forward rate data. The remaining 30
countries will have blank values for manual filling.

Input: docs/reference/stakeholder final dash columns.xlsx
Output: data/inputs/fx_forwards_manual.csv
"""

import pandas as pd
from pathlib import Path


def main():
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    input_file = project_root / "docs" / "reference" / "stakeholder final dash columns.xlsx"
    output_file = project_root / "data" / "inputs" / "fx_forwards_manual.csv"

    # Read reference dashboard
    df = pd.read_excel(input_file, sheet_name="Sheet2")

    # Header row is at index 2
    header_row = df.iloc[2].tolist()

    # Extract data rows (index 3 to 35 = 33 countries with data)
    # Skip aggregate indices (ACWI, WORLD, EM) and metadata rows
    data_df = df.iloc[3:36].copy()
    data_df.columns = header_row

    # Extract country, forward rate, and spot rate columns
    fx_data = data_df[[
        "Country",
        "Forward rate for USD/LCU 1 year out (% change)",
        "USD/LCU spot rate as of Mar 19, 2026"
    ]].copy()
    fx_data.columns = ["country", "forward_rate_1y", "spot_rate"]

    # Filter out any rows without country names
    fx_data = fx_data[fx_data["country"].notna() & (fx_data["country"] != "")]

    # Save to CSV
    fx_data.to_csv(output_file, index=False)

    print(f"Extracted {len(fx_data)} countries with FX data")
    print(f"Output saved to: {output_file}")
    print("\nPreview:")
    print(fx_data.to_string())


if __name__ == "__main__":
    main()
