#!/usr/bin/env python3
"""Build crude oil import impact metrics using WITS data and BOE methodology.

This script calculates the economic sensitivity to oil price changes using:
1. Crude oil imports from WITS (kg/yr)
2. Natural gas imports from WITS (kg/yr)
3. Conversion to Barrels of Oil Equivalent (BOE)
4. Impact as % of nominal GDP (USD)

Methodology:
- Crude oil: kg → MT (÷1000) → bbl (×7.33) → Mbbl (÷1,000,000)
- Natural gas: kg → MT (÷1000) → bbl BOE (×8.4) → Mbbl BOE (÷1,000,000)
- Total BOE = Crude Oil Mbbl + Natural Gas Mbbl BOE
- Impact % = (Total BOE × $10 / GDP_USD) × 100
"""

from __future__ import annotations

import argparse
import pandas as pd
from etf_mapping import COUNTRY_TO_ISO3


# Mapping from WITS country names to our canonical names
WITS_TO_CANONICAL: dict[str, str] = {
    "Korea, Rep.": "South Korea",
    "Türkiye": "Turkey",
    "Viet Nam": "Vietnam",
    "China": "China",
    "United States": "United States",
    "India": "India",
    "Japan": "Japan",
    "Netherlands": "Netherlands",
    "Germany": "Germany",
    "Spain": "Spain",
    "Thailand": "Thailand",
    "Italy": "Italy",
    "United Kingdom": "United Kingdom",
    "France": "France",
    "Singapore": "Singapore",
    "Belgium": "Belgium",
    "Poland": "Poland",
    "Greece": "Greece",
    "Canada": "Canada",
    "Malaysia": "Malaysia",
    "Sweden": "Sweden",
    "Indonesia": "Indonesia",
    "Brazil": "Brazil",
    "Israel": "Israel",
    "Portugal": "Portugal",
    "Pakistan": "Pakistan",
    "Lithuania": "Lithuania",
    "Australia": "Australia",
    "Finland": "Finland",
    "South Africa": "South Africa",
    "Egypt, Arab Rep.": "Egypt",
    "Croatia": "Croatia",
    "Colombia": "Colombia",
    "Dominican Republic": "Dominican Republic",
    "Philippines": "Philippines",
    "Chile": "Chile",
    "Argentina": "Argentina",
}

# Countries to exclude (aggregates, regions, etc.)
EXCLUDE_PATTERNS = [
    "world",
    "european union",
    "other asia",
    "nes",
    "not specified",
]


def is_excluded_country(name: str) -> bool:
    """Check if country name matches exclusion patterns."""
    if pd.isna(name) or str(name).strip() == "":
        return True
    name_lower = str(name).lower()
    for pattern in EXCLUDE_PATTERNS:
        if pattern in name_lower:
            return True
    return False


def parse_quantity(value) -> float | None:
    """Parse quantity value, handling scientific notation as text."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        # Handle scientific notation as string (e.g., "5.53232e+011")
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def load_wits_crude_oil(csv_path: str) -> pd.DataFrame:
    """Load WITS crude oil import data for 2024."""
    df = pd.read_excel(csv_path, sheet_name="By-HS6Product")
    
    # Filter for 2024
    df = df[df["Year"] == 2024].copy()
    
    # Filter for individual countries only
    df = df[~df["Reporter"].apply(is_excluded_country)].copy()
    
    # Map to canonical names
    df["country_name"] = df["Reporter"].map(
        lambda x: WITS_TO_CANONICAL.get(x, x)
    )
    
    # Map to ISO3
    df["country_code"] = df["country_name"].map(COUNTRY_TO_ISO3)
    
    # Parse quantity (Kg)
    df["quantity_kg"] = df["Quantity"].apply(parse_quantity)
    
    # Keep only rows with valid quantity and country code
    df = df.dropna(subset=["quantity_kg", "country_code"])
    
    # Aggregate by country (in case multiple entries per country)
    result = df.groupby("country_code").agg(
        country_name=("country_name", "first"),
        crude_oil_kg=("quantity_kg", "sum"),
    ).reset_index()
    
    return result


def load_wits_natural_gas(csv_path: str) -> pd.DataFrame:
    """Load WITS natural gas import data for 2024."""
    df = pd.read_excel(csv_path, sheet_name="By-HS6Product")
    
    # Filter for 2024
    df = df[df["Year"] == 2024].copy()
    
    # Filter for individual countries only
    df = df[~df["Reporter"].apply(is_excluded_country)].copy()
    
    # Map to canonical names
    df["country_name"] = df["Reporter"].map(
        lambda x: WITS_TO_CANONICAL.get(x, x)
    )
    
    # Map to ISO3
    df["country_code"] = df["country_name"].map(COUNTRY_TO_ISO3)
    
    # Parse quantity (Kg)
    df["quantity_kg"] = df["Quantity"].apply(parse_quantity)
    
    # Keep only rows with valid quantity and country code
    df = df.dropna(subset=["quantity_kg", "country_code"])
    
    # Aggregate by country
    result = df.groupby("country_code").agg(
        country_name=("country_name", "first"),
        natural_gas_kg=("quantity_kg", "sum"),
    ).reset_index()
    
    return result


def load_weo_gdp(csv_path: str) -> pd.DataFrame:
    """Load WEO nominal GDP data in USD for 2024."""
    df = pd.read_csv(csv_path)

    # Filter for NGDPD (GDP current USD) and 2024
    df = df[(df["indicator"] == "NGDPD") & (df["year"] == 2024)].copy()

    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    return df[["country_code", "value"]].rename(columns={"value": "gdp_usd_2024"})


def load_un_crude_fallback(csv_path: str) -> pd.DataFrame:
    """Load UN crude oil import data as fallback for countries without WITS data."""
    df = pd.read_csv(csv_path)
    
    # Filter for crude oil imports
    df = df[df["Commodity - Transaction"] == "Conventional crude oil - imports"].copy()
    
    # Map country names
    UN_COUNTRY_MAPPING = {
        "Korea, Republic of": "South Korea",
        "Türkiye": "Turkey",
        "Viet Nam": "Vietnam",
    }
    df["country_name"] = df["Country or Area"].map(lambda x: UN_COUNTRY_MAPPING.get(x, x))
    
    # Map to ISO3
    df["country_code"] = df["country_name"].map(COUNTRY_TO_ISO3)
    
    # Filter out rows without country code
    df = df.dropna(subset=["country_code"])
    
    # Get latest year (2024 preferred, otherwise latest available)
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    
    # Get latest year for each country
    latest = df.sort_values("Year").groupby("country_code").last().reset_index()
    
    # Calculate: thousand metric tons → metric tons → barrels → Mbbl
    # UN data is already in thousand metric tons
    latest["crude_oil_mbbl"] = (
        latest["Quantity"] * 1000 * 7.53 / 1_000_000
    )
    
    result = latest[["country_code", "country_name", "Year", "crude_oil_mbbl"]].rename(
        columns={"Year": "year", "crude_oil_mbbl": "crude_oil_mbbl_un"}
    )
    
    return result


def calculate_boe_impact(
    crude_df: pd.DataFrame,
    gas_df: pd.DataFrame,
    gdp_df: pd.DataFrame,
    un_fallback_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate BOE-based oil import impact metrics with UN fallback.
    
    Fallback logic:
    - Use WITS when BOTH crude oil AND natural gas data exist
    - Use UN fallback when neither exists OR only natural gas exists (no crude)
    - Use WITS when only crude oil exists (no natural gas)
    - For countries with NO WITS data at all, use UN fallback if available
    """
    # Get all countries from GDP (our universe of countries)
    all_countries = set(gdp_df["country_code"].unique())
    
    # Merge crude and gas data
    merged = crude_df.merge(
        gas_df,
        on="country_code",
        how="outer",
        suffixes=("_crude", "_gas"),
    )

    # Fill missing country names
    merged["country_name"] = merged["country_name_crude"].combine_first(
        merged["country_name_gas"]
    )

    # Calculate BOE components for WITS data
    # Crude oil: kg → MT (÷1000) → bbl (×7.33) → Mbbl (÷1,000,000)
    merged["crude_oil_mbbl"] = (
        merged["crude_oil_kg"].fillna(0) / 1000 * 7.33 / 1_000_000
    )

    # Natural gas: kg → MT (÷1000) → bbl BOE (×8.4) → Mbbl BOE (÷1,000,000)
    merged["natural_gas_mbbl_boe"] = (
        merged["natural_gas_kg"].fillna(0) / 1000 * 8.4 / 1_000_000
    )

    # Total BOE
    merged["total_boe_mbbl"] = (
        merged["crude_oil_mbbl"] + merged["natural_gas_mbbl_boe"]
    )

    # Determine data source based on availability rules
    has_crude = merged["crude_oil_kg"].notna()
    has_gas = merged["natural_gas_kg"].notna()
    
    # Use UN fallback when: neither exists OR only gas exists (no crude)
    use_un_fallback = (~has_crude & ~has_gas) | (~has_crude & has_gas)
    
    merged["data_source"] = "WITS"
    merged.loc[use_un_fallback, "data_source"] = "UN_PENDING"  # Mark for potential UN fallback

    # Select WITS columns
    wits_result = merged[[
        "country_name",
        "country_code",
        "crude_oil_mbbl",
        "natural_gas_mbbl_boe",
        "total_boe_mbbl",
        "data_source",
    ]].copy()

    # Identify countries without any WITS data
    wits_countries = set(wits_result["country_code"].unique())
    missing_countries = all_countries - wits_countries
    
    # Process UN fallback for:
    # 1. Countries marked as UN_PENDING (gas-only or no WITS data)
    # 2. Countries with NO WITS data at all
    if un_fallback_df is not None and not un_fallback_df.empty:
        # Get all countries needing UN fallback
        pending_countries = set(wits_result[wits_result["data_source"] == "UN_PENDING"]["country_code"].unique())
        all_un_needed = pending_countries | missing_countries
        
        # Filter UN data for these countries
        un_for_fallback = un_fallback_df[un_fallback_df["country_code"].isin(all_un_needed)].copy()
        
        if not un_for_fallback.empty:
            # UN fallback: use crude_oil_mbbl_un directly (already calculated)
            un_for_fallback["natural_gas_mbbl_boe"] = 0.0  # No gas data in UN fallback
            un_for_fallback["total_boe_mbbl"] = un_for_fallback["crude_oil_mbbl_un"]
            un_for_fallback["data_source"] = "UN"
            
            un_result = un_for_fallback[[
                "country_name",
                "country_code",
                "crude_oil_mbbl_un",
                "natural_gas_mbbl_boe",
                "total_boe_mbbl",
                "data_source",
            ]].rename(columns={"crude_oil_mbbl_un": "crude_oil_mbbl"})
            
            # Remove UN_PENDING rows and combine with UN data
            wits_result = wits_result[wits_result["data_source"] != "UN_PENDING"]
            combined = pd.concat([wits_result, un_result], ignore_index=True)
        else:
            # No UN data available, keep WITS (even if incomplete)
            wits_result.loc[wits_result["data_source"] == "UN_PENDING", "data_source"] = "WITS"
            combined = wits_result
    else:
        # No UN fallback available
        wits_result.loc[wits_result["data_source"] == "UN_PENDING", "data_source"] = "WITS"
        combined = wits_result

    # Valuation at $10/barrel
    combined["valuation_at_10_usd"] = combined["total_boe_mbbl"] * 10 * 1_000_000

    # Merge with GDP
    combined = combined.merge(gdp_df, on="country_code", how="left")

    # Calculate impact as % of GDP
    combined["impact_percent_gdp"] = (
        combined["valuation_at_10_usd"] / combined["gdp_usd_2024"] * 100
    )

    # Select and format output columns
    result = combined[[
        "country_name",
        "country_code",
        "crude_oil_mbbl",
        "natural_gas_mbbl_boe",
        "total_boe_mbbl",
        "valuation_at_10_usd",
        "gdp_usd_2024",
        "impact_percent_gdp",
        "data_source",
    ]].copy()

    # Round for readability
    for col in ["crude_oil_mbbl", "natural_gas_mbbl_boe", "total_boe_mbbl"]:
        result[col] = result[col].round(4)
    result["valuation_at_10_usd"] = result["valuation_at_10_usd"].round(0)
    result["gdp_usd_2024"] = result["gdp_usd_2024"].round(0)
    result["impact_percent_gdp"] = result["impact_percent_gdp"].round(6)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build BOE-based crude oil import impact metrics using WITS data with UN fallback."
    )
    parser.add_argument(
        "--crude-csv",
        default="data/inputs/crude oil data_WITS-By-HS6Product (1).xlsx",
        help="Path to WITS crude oil import data",
    )
    parser.add_argument(
        "--gas-csv",
        default="data/inputs/natural gas data_WITS-By-HS6Product.xlsx",
        help="Path to WITS natural gas import data",
    )
    parser.add_argument(
        "--un-csv",
        default="data/inputs/UNdata_Export_20260313_085844383.csv",
        help="Path to UN crude oil import data (fallback)",
    )
    parser.add_argument(
        "--weo-csv",
        default="data/outputs/weo_gdp.csv",
        help="Path to WEO GDP data",
    )
    parser.add_argument(
        "--output",
        default="data/outputs/crude_oil_import_impact.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    print(f"Loading WITS crude oil data from {args.crude_csv}...")
    crude_df = load_wits_crude_oil(args.crude_csv)
    print(f"  Loaded {len(crude_df)} countries with crude oil data")

    print(f"Loading WITS natural gas data from {args.gas_csv}...")
    gas_df = load_wits_natural_gas(args.gas_csv)
    print(f"  Loaded {len(gas_df)} countries with natural gas data")

    print(f"Loading WEO GDP data from {args.weo_csv}...")
    gdp_df = load_weo_gdp(args.weo_csv)
    print(f"  Loaded {len(gdp_df)} countries with GDP data")

    print("Loading UN fallback data...")
    un_fallback_df = load_un_crude_fallback(args.un_csv)
    print(f"  Loaded {len(un_fallback_df)} countries with UN data")

    print("Calculating BOE impact metrics...")
    result_df = calculate_boe_impact(crude_df, gas_df, gdp_df, un_fallback_df)
    print(f"  Calculated impact for {len(result_df)} countries")

    print(f"Saving results to {args.output}...")
    result_df.to_csv(args.output, index=False)
    print("Done.")

    # Summary
    print("\n=== Summary ===")
    wits_both = len(result_df[(result_df["data_source"] == "WITS")])
    un_fallback = len(result_df[result_df["data_source"] == "UN"])
    print(f"Countries with WITS data (both oil+gas or oil-only): {wits_both}")
    print(f"Countries with UN fallback data: {un_fallback}")
    
    # Show which countries use UN fallback
    if un_fallback > 0:
        un_countries = result_df[result_df["data_source"] == "UN"]["country_name"].tolist()
        print(f"  UN fallback countries: {un_countries}")


if __name__ == "__main__":
    main()
