#!/usr/bin/env python3
"""Build crude oil import impact metrics using UN data and WEO GDP."""

from __future__ import annotations

import argparse
import pandas as pd
from etf_mapping import COUNTRY_TO_ISO3

# Manual mapping for UN country names to our canonical names/ISO3
UN_COUNTRY_MAPPING = {
    "Korea, Republic of": "South Korea",
    "Türkiye": "Turkey",
    "Viet Nam": "Vietnam",
}

def load_un_crude_imports(csv_path: str) -> pd.DataFrame:
    """Load and clean UN crude oil import data."""
    df = pd.read_csv(csv_path)
    
    # Filter for crude oil imports
    df = df[df["Commodity - Transaction"] == "Conventional crude oil - imports"].copy()
    
    # Clean up country names
    df["country_name"] = df["Country or Area"].map(lambda x: UN_COUNTRY_MAPPING.get(x, x))
    
    # Map to ISO3
    df["country_code"] = df["country_name"].map(COUNTRY_TO_ISO3)
    
    # Filter out rows without a country code (garbage rows from UN export footer)
    df = df.dropna(subset=["country_code"])
    
    # Convert types
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    
    return df

def load_weo_gdp(csv_path: str) -> pd.DataFrame:
    """Load WEO nominal GDP data in USD."""
    df = pd.read_csv(csv_path)
    df = df[df["indicator"] == "NGDPD"].copy() # GDP, current prices (U.S. dollars)
    
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    
    return df[["country_code", "year", "value"]].rename(columns={"value": "gdp_usd"})

def calculate_impact_metrics(un_df: pd.DataFrame, gdp_df: pd.DataFrame) -> pd.DataFrame:
    """Perform conversion calculations and join with GDP."""
    # Get latest year for each country in UN data
    latest_un = un_df.sort_values("Year").groupby("country_code").last().reset_index()
    
    # Join with GDP for the same year
    merged = latest_un.merge(
        gdp_df, 
        left_on=["country_code", "Year"], 
        right_on=["country_code", "year"], 
        how="left"
    )
    
    # Calculations
    # 1. quantity_metric_tons = quantity_thousand_metric_tons * 1000
    merged["quantity_metric_tons"] = merged["Quantity"] * 1000
    
    # 2. quantity_barrels = quantity_metric_tons * 7.53
    merged["quantity_barrels"] = merged["quantity_metric_tons"] * 7.53
    
    # 3. value_at_10_usd_change = quantity_barrels * 10
    merged["value_at_10_usd_change"] = merged["quantity_barrels"] * 10
    
    # 4. impact_as_percent_gdp = value_at_10_usd_change / nominal_gdp_usd * 100
    merged["impact_as_percent_gdp"] = (merged["value_at_10_usd_change"] / merged["gdp_usd"]) * 100
    
    # Select and rename columns for final output
    result = merged[[
        "country_name",
        "country_code",
        "Year",
        "Quantity",
        "quantity_metric_tons",
        "quantity_barrels",
        "value_at_10_usd_change",
        "gdp_usd",
        "impact_as_percent_gdp"
    ]].rename(columns={
        "Year": "year",
        "Quantity": "qty_thousand_metric_tons",
        "Quantity": "qty_thousand_metric_tons", # redundant but safe
    })
    
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Build crude oil import impact metrics.")
    parser.add_argument("--un-csv", default="data/inputs/UNdata_Export_20260313_085844383.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--output", default="data/outputs/crude_oil_import_impact.csv")
    args = parser.parse_args()

    print(f"Loading UN data from {args.un_csv}...")
    un_df = load_un_crude_imports(args.un_csv)
    
    print(f"Loading WEO GDP data from {args.weo_csv}...")
    gdp_df = load_weo_gdp(args.weo_csv)
    
    print("Calculating impact metrics...")
    result_df = calculate_impact_metrics(un_df, gdp_df)
    
    print(f"Saving results to {args.output}...")
    result_df.to_csv(args.output, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
