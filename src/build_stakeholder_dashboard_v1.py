#!/usr/bin/env python3
"""Build stakeholder dashboard v1.0 with MSCI index data.

This script creates a single-sheet Excel dashboard with 60 countries
(excluding aggregate indices ACWI, WORLD, EM) using the exact schema
from the stakeholder reference file.

Data sources:
- MSCI factsheet: Returns, Market Cap, P/E, factsheet links
- WEO (IMF API): nGDP CAGR, projections, nGDP 2025 levels
- BIS: REER Index
- Manual (from reference Excel): FX forwards, spot rates
- Manual (WITS/UN): Oil impact data

Output: data/outputs/stakeholder_dashboard_v1.xlsx
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def load_msci_data(input_path: Path) -> pd.DataFrame:
    """Load MSCI factsheet data and filter to country-level only."""
    df = pd.read_excel(input_path)
    
    # Exclude aggregate indices (ACWI, WORLD, EM)
    aggregates = {"ACWI", "WORLD", "EM"}
    df = df[~df["country"].isin(aggregates)].copy()
    
    # Remove duplicates (keep first occurrence)
    df = df.drop_duplicates(subset=["country"], keep="first")
    
    # Rename columns for clarity
    df = df.rename(columns={
        "country": "country_name",
        "10 yr": "msci_10y_return",
        "Index Market Cap ($ billion)": "index_market_cap_billion",
        "Top 10 Float Adj Mkt Cap ($ billion)": "top_10_market_cap_billion",
        "P/E": "pe_ratio",
        "link": "factsheet_link"
    })
    
    return df


def load_weo_data(weo_path: Path) -> pd.DataFrame:
    """Load WEO GDP data and calculate required metrics."""
    df = pd.read_csv(weo_path)
    
    # Filter to NGDP (nominal GDP in USD) indicator
    # NGDPD = GDP, current prices (US dollars)
    ngdp_usd = df[df["indicator"] == "NGDPD"].copy()
    
    # Pivot to get years as columns
    pivot = ngdp_usd.pivot_table(
        index=["country_name", "country_code"],
        columns="year",
        values="value",
        aggfunc="first"
    ).reset_index()
    
    # Calculate nGDP (USD) CAGR for 10Y (2015-2025)
    # CAGR = (End/Start)^(1/n) - 1
    if 2015 in pivot.columns and 2025 in pivot.columns:
        pivot["ngdp_usd_cagr_10y"] = (
            (pivot[2025] / pivot[2015]) ** (1/10) - 1
        )
    
    # Get 2025 nGDP levels (in billions)
    if 2025 in pivot.columns:
        pivot["ngdp_2025_billion"] = pivot[2025] / 1e9
    
    # Calculate projected growth 2026-28 CAGR
    if 2026 in pivot.columns and 2028 in pivot.columns:
        pivot["proj_growth_26_28_cagr"] = (
            (pivot[2028] / pivot[2026]) ** (1/2) - 1
        )
    
    # Select relevant columns
    result = pivot[[
        "country_name", "country_code",
        "ngdp_usd_cagr_10y", "ngdp_2025_billion", "proj_growth_26_28_cagr"
    ]].copy()
    
    return result


def load_bis_reer(bis_path: Path) -> pd.DataFrame:
    """Load BIS REER data."""
    df = pd.read_csv(bis_path)
    
    # Select relevant columns
    result = df[[
        "country_name", "bis_code", "current_reer"
    ]].copy()
    
    # Calculate implied currency effect from REER
    # REER > 100 means overvalued, < 100 means undervalued
    result["reer_implied_fx_effect"] = (result["current_reer"] - 100) / 100
    
    return result


def load_fx_manual(fx_path: Path) -> pd.DataFrame:
    """Load manual FX forwards and spot rates."""
    df = pd.read_csv(fx_path)
    
    # Rename for consistency
    df = df.rename(columns={
        "country": "country_name",
        "forward_rate_1y": "forward_rate_1y",
        "spot_rate": "spot_rate"
    })
    
    return df


def load_oil_impact(oil_path: Path) -> pd.DataFrame:
    """Load oil import impact data."""
    df = pd.read_csv(oil_path)
    
    # Select relevant columns
    result = df[[
        "country_name", "impact_percent_gdp"
    ]].copy()
    
    # Classify oil sensitivity
    def classify_sensitivity(impact):
        if pd.isna(impact):
            return np.nan
        if impact < 0.2:
            return "low"
        elif impact < 0.5:
            return "medium"
        else:
            return "high"
    
    result["oil_sensitivity"] = result["impact_percent_gdp"].apply(classify_sensitivity)
    
    return result


def calculate_macro_gap(row: pd.Series) -> float:
    """Calculate Macro Gap (MSCI return - nGDP CAGR)."""
    if pd.isna(row.get("msci_10y_return")) or pd.isna(row.get("ngdp_usd_cagr_10y")):
        return np.nan
    return row["msci_10y_return"] - row["ngdp_usd_cagr_10y"]


def calculate_avg_currency_signals(row: pd.Series) -> float:
    """Calculate average currency signals from forwards and REER."""
    signals = []
    
    if pd.notna(row.get("forward_rate_1y")):
        signals.append(row["forward_rate_1y"])
    
    if pd.notna(row.get("reer_implied_fx_effect")):
        signals.append(row["reer_implied_fx_effect"])
    
    if len(signals) == 0:
        return np.nan
    
    return sum(signals) / len(signals)


def calculate_currency_forecast(row: pd.Series) -> str:
    """Generate currency forecast based on signals."""
    avg_signal = row.get("avg_currency_signals")
    
    if pd.isna(avg_signal):
        return ""
    
    # Simple classification based on average signal
    if avg_signal > 0.02:
        return "Appreciating"
    elif avg_signal < -0.02:
        return "Depreciating"
    else:
        return "Neutral"


def build_dashboard(
    msci_path: Path,
    weo_path: Path,
    bis_path: Path,
    fx_path: Path,
    oil_path: Path,
    output_path: Path
):
    """Build the complete stakeholder dashboard."""
    
    print("Loading data sources...")
    
    # Load all data
    msci = load_msci_data(msci_path)
    print(f"  MSCI: {len(msci)} countries")
    
    weo = load_weo_data(weo_path)
    print(f"  WEO: {len(weo)} countries")
    
    bis = load_bis_reer(bis_path)
    print(f"  BIS REER: {len(bis)} countries")
    
    fx = load_fx_manual(fx_path)
    print(f"  FX Manual: {len(fx)} countries")
    
    oil = load_oil_impact(oil_path)
    print(f"  Oil Impact: {len(oil)} countries")
    
    # Merge all datasets
    print("\nMerging datasets...")
    
    # Start with MSCI as base (60 countries)
    df = msci.copy()
    
    # Merge WEO
    df = df.merge(weo, on="country_name", how="left")
    
    # Merge BIS
    df = df.merge(bis, on="country_name", how="left")
    
    # Merge FX
    df = df.merge(fx, on="country_name", how="left")
    
    # Merge Oil
    df = df.merge(oil, on="country_name", how="left")
    
    print(f"  Merged: {len(df)} countries")
    
    # Calculate derived columns
    print("\nCalculating derived columns...")
    
    df["macro_gap"] = df.apply(calculate_macro_gap, axis=1)
    df["avg_currency_signals"] = df.apply(calculate_avg_currency_signals, axis=1)
    df["currency_forecast"] = df.apply(calculate_currency_forecast, axis=1)
    
    # Build final output dataframe with exact column order
    print("\nBuilding final output...")
    
    # Define column names
    columns = [
        "Country", "nGDP (USD) CAGR (%)", "MSCI Index Return (USD) CAGR (%)",
        "Undervalued Country (Macro Gap)", "Projected Growth (2026-28) CAGR",
        "REER Index", "Implied currency effect from REER",
        "Forward rate for USD/LCU 1 year out (% change)",
        "Avg Currency signals", "Currency Forecast",
        "Impact of $10 Oil Price rise relative to GDP (%)", "Oil Sensitivity",
        "", "  ",  # Spacer columns
        "nGDP 2025 ($ billion)", "USD/LCU spot rate as of Mar 19, 2026",
        "Futures rate for USD/LCU (1 years out from Mar 19, 2026)",
        "Index Market Cap ($ billion)", "Top 10 Float Adj Mkt Cap ($ billion)",
        "P/E", "MSCI Factsheet Link"
    ]
    
    output = pd.DataFrame(columns=columns)
    output["Country"] = df["country_name"]
    output["nGDP (USD) CAGR (%)"] = df["ngdp_usd_cagr_10y"]
    output["MSCI Index Return (USD) CAGR (%)"] = df["msci_10y_return"]
    output["Undervalued Country (Macro Gap)"] = df["macro_gap"]
    output["Projected Growth (2026-28) CAGR"] = df["proj_growth_26_28_cagr"]
    output["REER Index"] = df["current_reer"]
    output["Implied currency effect from REER"] = df["reer_implied_fx_effect"]
    output["Forward rate for USD/LCU 1 year out (% change)"] = df["forward_rate_1y"]
    output["Avg Currency signals"] = df["avg_currency_signals"]
    output["Currency Forecast"] = df["currency_forecast"]
    output["Impact of $10 Oil Price rise relative to GDP (%)"] = df["impact_percent_gdp"]
    output["Oil Sensitivity"] = df["oil_sensitivity"]
    output[""] = np.nan  # Spacer column 1
    output["  "] = np.nan  # Spacer column 2
    output["nGDP 2025 ($ billion)"] = df["ngdp_2025_billion"]
    output["USD/LCU spot rate as of Mar 19, 2026"] = df["spot_rate"]
    output["Futures rate for USD/LCU (1 years out from Mar 19, 2026)"] = df["forward_rate_1y"]  # Same as forward rate
    output["Index Market Cap ($ billion)"] = df["index_market_cap_billion"]
    output["Top 10 Float Adj Mkt Cap ($ billion)"] = df["top_10_market_cap_billion"]
    output["P/E"] = df["pe_ratio"]
    output["MSCI Factsheet Link"] = df["factsheet_link"]
    
    # Write to Excel
    print(f"\nWriting to {output_path}...")
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Write data with headers starting at row 2
        output.to_excel(
            writer,
            sheet_name="Dashboard",
            index=False,
            startrow=1  # Start at row 2 (row 1 reserved for title)
        )
        
        # Apply basic formatting
        workbook = writer.book
        worksheet = writer.sheets["Dashboard"]
        
        # Add header row with date in row 1
        header_date = datetime.now().strftime("%b %d, %Y")
        worksheet.cell(row=1, column=1, value=f"Country Disconnect Dashboard (As of {header_date})")
        
        # Set column widths
        column_widths = [
            18,  # Country
            12,  # nGDP CAGR
            14,  # MSCI Return
            12,  # Macro Gap
            14,  # Projected Growth
            12,  # REER Index
            14,  # REER implied
            14,  # Forward rate
            14,  # Avg signals
            14,  # Currency forecast
            14,  # Oil impact
            12,  # Oil sensitivity
            2,   # Spacer 1
            2,   # Spacer 2
            14,  # nGDP 2025
            14,  # Spot rate
            14,  # Futures rate
            14,  # Market Cap
            18,  # Top 10 Cap
            10,  # P/E
            40,  # Factsheet link
        ]
        
        for i, width in enumerate(column_widths):
            col_letter = chr(65 + i)  # A, B, C, ...
            worksheet.column_dimensions[col_letter].width = width
    
    print(f"\nDashboard created successfully with {len(output)} countries!")
    print(f"Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Build stakeholder dashboard v1.0 with MSCI index data"
    )
    parser.add_argument(
        "--msci",
        type=Path,
        default=Path("data/inputs/factsheet data manual_feb 27 2026.xlsx"),
        help="Path to MSCI factsheet Excel file"
    )
    parser.add_argument(
        "--weo",
        type=Path,
        default=Path("data/outputs/weo_gdp.csv"),
        help="Path to WEO GDP CSV file"
    )
    parser.add_argument(
        "--bis",
        type=Path,
        default=Path("data/outputs/bis_reer_metrics.csv"),
        help="Path to BIS REER CSV file"
    )
    parser.add_argument(
        "--fx",
        type=Path,
        default=Path("data/inputs/fx_forwards_manual.csv"),
        help="Path to manual FX forwards CSV file"
    )
    parser.add_argument(
        "--oil",
        type=Path,
        default=Path("data/outputs/crude_oil_import_impact.csv"),
        help="Path to oil import impact CSV file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/outputs/stakeholder_dashboard_v1.xlsx"),
        help="Output Excel file path"
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    msci_path = project_root / args.msci
    weo_path = project_root / args.weo
    bis_path = project_root / args.bis
    fx_path = project_root / args.fx
    oil_path = project_root / args.oil
    output_path = project_root / args.output
    
    build_dashboard(
        msci_path=msci_path,
        weo_path=weo_path,
        bis_path=bis_path,
        fx_path=fx_path,
        oil_path=oil_path,
        output_path=output_path
    )


if __name__ == "__main__":
    main()
