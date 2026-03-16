#!/usr/bin/env python3
"""Fetch daily FX history from Yahoo Finance for all project currencies."""

from __future__ import annotations

import argparse
import pandas as pd
import yfinance as yf
from pathlib import Path


def normalize_currency_code(currency: str) -> str:
    c = str(currency or "").strip()
    if c == "GBp":
        return "GBP"
    return c


def fetch_fx_prices(currencies: set[str], output_csv: str) -> None:
    dfs = []
    for currency in sorted(currencies):
        ccy = normalize_currency_code(currency)
        if not ccy or ccy == "USD":
            continue
        
        print(f"Fetching FX for {ccy}...")
        series: pd.Series | None = None
        # Try both directions
        for pair, invert in ((f"{ccy}USD=X", False), (f"USD{ccy}=X", True)):
            ticker = yf.Ticker(pair)
            hist = ticker.history(period="max", interval="1d", auto_adjust=True, actions=False)
            if hist.empty or "Close" not in hist.columns:
                continue
            
            s = hist["Close"].dropna()
            if s.empty:
                continue
            
            if invert:
                s = 1.0 / s
            
            df = s.to_frame(name="price_usd")
            df["currency"] = ccy
            dfs.append(df)
            series = s
            break
        
        if series is None:
            print(f"Warning: Could not fetch FX data for {ccy}")

    if dfs:
        final_df = pd.concat(dfs).reset_index()
        # Remove timezone if exists for CSV compatibility
        if pd.api.types.is_datetime64tz_dtype(final_df["Date"]):
            final_df["Date"] = final_df["Date"].dt.tz_localize(None)
        
        final_df.to_csv(output_csv, index=False)
        print(f"Wrote {len(final_df)} FX price rows to {output_csv}")
    else:
        print("No FX data fetched.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily FX prices for all project currencies.")
    parser.add_argument("--metadata", default="data/outputs/etf_ticker_metadata.csv")
    parser.add_argument("--output", default="data/outputs/fx_prices.csv")
    args = parser.parse_args()

    if not Path(args.metadata).exists():
        print(f"Metadata file {args.metadata} not found. Run fetch_etf_prices.py first.")
        return

    meta = pd.read_csv(args.metadata)
    if "currency" not in meta.columns:
        print("No currency column in metadata.")
        return
    
    currencies = set(meta["currency"].dropna().unique())
    # Also add LCU currencies from etf_mapping if possible, 
    # but metadata covers what ETFs actually use.
    
    fetch_fx_prices(currencies, args.output)


if __name__ == "__main__":
    main()
