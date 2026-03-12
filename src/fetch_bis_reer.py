#!/usr/bin/env python3
"""Fetch REER data from BIS and calculate over/undervaluation metric."""

from __future__ import annotations

import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path

# Mapping of Project Country Names to BIS REF_AREA (ISO2)
COUNTRY_TO_BIS_ISO2 = {
    "Australia": "AU",
    "Austria": "AT",
    "Belgium": "BE",
    "Brazil": "BR",
    "Bulgaria": "BG",
    "Canada": "CA",
    "China": "CN",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Hong Kong": "HK",
    "India": "IN",
    "Indonesia": "ID",
    "Italy": "IT",
    "Japan": "JP",
    "Kuwait": "KW",
    "Malaysia": "MY",
    "Mexico": "MX",
    "Netherlands": "NL",
    "Pakistan": "PK",
    "Philippines": "PH",
    "Poland": "PL",
    "Saudi Arabia": "SA",
    "Singapore": "SG",
    "South Africa": "ZA",
    "South Korea": "KR",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Taiwan": "TW",
    "Thailand": "TH",
    "Turkey": "TR",
    "United Kingdom": "GB",
    "United States": "US",
    "Vietnam": "VN",
}

def fetch_and_process_reer(output_path: str):
    # Use a 10-year window ending today
    end_date = datetime.now().strftime("%Y-%m-%d")
    # To get a 10-year average ending in 2026, we need data back to 2016.
    start_date = "2016-01-01"
    
    url = f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_EER/1.0/M.R.B?startPeriod={start_date}&endPeriod={end_date}&format=csv"
    
    print(f"Fetching BIS REER data from: {url}")
    df = pd.read_csv(url)
    
    # Filter for countries in our scope
    bis_codes = set(COUNTRY_TO_BIS_ISO2.values())
    df = df[df["REF_AREA"].isin(bis_codes)].copy()
    
    # Convert TIME_PERIOD to datetime for sorting
    df["date"] = pd.to_datetime(df["TIME_PERIOD"])
    df = df.sort_values(["REF_AREA", "date"])
    
    results = []
    
    # Invert mapping for lookup
    iso2_to_country = {v: k for k, v in COUNTRY_TO_BIS_ISO2.items()}
    
    for code, group in df.groupby("REF_AREA"):
        if group.empty:
            continue
            
        current_reer = group.iloc[-1]["OBS_VALUE"]
        avg_10y_reer = group["OBS_VALUE"].mean()
        
        # Metric: ((current REER - 10 year average REER)/(10 year average REER)) * 100
        reer_pct_diff = ((current_reer - avg_10y_reer) / avg_10y_reer) * 100
        
        results.append({
            "country_name": iso2_to_country.get(code, code),
            "bis_code": code,
            "current_reer": current_reer,
            "avg_10y_reer": avg_10y_reer,
            "reer_pct_diff": reer_pct_diff
        })
        
    res_df = pd.DataFrame(results)
    res_df.to_csv(output_path, index=False)
    print(f"Wrote REER metrics to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch BIS REER data.")
    parser.add_argument("--output", default="data/outputs/bis_reer_metrics.csv")
    args = parser.parse_args()
    
    fetch_and_process_reer(args.output)
