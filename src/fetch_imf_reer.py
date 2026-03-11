#!/usr/bin/env python3
"""Fetch Real Effective Exchange Rate (REER) data from IMF EER dataflow."""

from __future__ import annotations

import argparse
import csv
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from etf_mapping import COUNTRY_TO_ISO3

def build_eer_url(countries: list[str], start_year: int, end_year: int) -> str:
    # EER Key: [COUNTRY].EREER_IX.A
    # We join countries with +
    key = f"{'+'.join(countries)}.EREER_IX.A"
    encoded_key = urllib.parse.quote(key, safe="+.")
    params = urllib.parse.urlencode({
        "startPeriod": str(start_year),
        "endPeriod": str(end_year)
    })
    return f"https://api.imf.org/external/sdmx/2.1/data/EER/{encoded_key}?{params}"

def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

def parse_eer_xml(xml_payload: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_payload)
    rows: list[dict[str, str]] = []

    for series in root.iter():
        if _local_name(series.tag) != "Series":
            continue

        # Extract country code from attributes or SeriesKey
        country_code = series.attrib.get("UNIT_AREA") or series.attrib.get("COUNTRY")
        if not country_code:
            for child in series:
                if _local_name(child.tag) == "SeriesKey":
                    for item in child:
                        if _local_name(item.tag) == "Value" and item.attrib.get("id") in ["UNIT_AREA", "COUNTRY"]:
                            country_code = item.attrib.get("value")
        
        if not country_code: continue

        for obs in series:
            if _local_name(obs.tag) != "Obs":
                continue
            
            year = obs.attrib.get("TIME_PERIOD")
            value = obs.attrib.get("OBS_VALUE")
            
            if not year or not value:
                for item in obs:
                    ln = _local_name(item.tag)
                    if ln == "ObsDimension": year = item.attrib.get("value")
                    elif ln == "ObsValue": value = item.attrib.get("value")

            if year and value:
                rows.append({
                    "country_code": country_code,
                    "year": year,
                    "reer_index": value
                })
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--output", default="data/outputs/imf_reer.csv")
    args = parser.parse_args()

    iso3_codes = list(COUNTRY_TO_ISO3.values())
    # Note: Some datasets use ISO2, but EER documentation suggests Area/Country codes. 
    # We will try with ISO3 first.
    
    url = build_eer_url(iso3_codes, args.start_year, args.end_year)
    print(f"Fetching REER from: {url}")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            payload = response.read()
            rows = parse_eer_xml(payload)
            
            if not rows:
                print("Warning: No data returned from IMF EER API.")
            
            # Map back to country names for convenience
            iso_to_name = {v: k for k, v in COUNTRY_TO_ISO3.items()}
            for r in rows:
                r["country_name"] = iso_to_name.get(r["country_code"], "Unknown")
            
            with open(args.output, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["country_name", "country_code", "year", "reer_index"])
                writer.writeheader()
                writer.writerows(rows)
            print(f"Wrote {len(rows)} REER rows to {args.output}")
            
    except Exception as e:
        print(f"Error fetching REER data: {e}")

if __name__ == "__main__":
    main()
