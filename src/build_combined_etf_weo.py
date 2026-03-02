#!/usr/bin/env python3
"""Build a normalized annual ETF+WEO dataset for dashboard use."""

from __future__ import annotations

import argparse
import re

import pandas as pd


ETF_COUNTRY_TO_TICKERS = {
    "Australia": ["SAUS.L"],
    "Austria": ["XB4A.L"],
    "Belgium": ["BEL.L"],
    "Brazil": ["XMBR.L"],
    "Bulgaria": ["BGX.L"],
    "Canada": ["CSCA.L"],
    "China": ["IASH.L", "FRCH.L"],
    "France": ["ISFR.L", "CACC.L"],
    "Germany": ["XDAX.L"],
    "Greece": ["GRE.L"],
    "Hong Kong": ["HKDU.L"],
    "India": ["IIND.L", "FRIN.L"],
    "Indonesia": ["INDO.L"],
    "Italy": ["CMIB.L"],
    "Japan": ["LCJP.L", "IJPN.L"],
    "Kuwait": ["MKUW.L"],
    "Malaysia": ["XCX3.L"],
    "Mexico": ["XMEX.L"],
    "Netherlands": ["IAEA.L"],
    "Pakistan": ["XBAK.L"],
    "Philippines": ["XPHG.L"],
    "Poland": ["SPOL.L"],
    "Saudi Arabia": ["IKSA.L"],
    "Singapore": ["XBAS.L"],
    "South Africa": ["SRSA.L"],
    "South Korea": ["CSKR.L", "FLRK.L"],
    "Spain": ["CS1.L", "XESP.L"],
    "Sweden": ["OMXS.L"],
    "Switzerland": ["CHUSD.L"],
    "Taiwan": ["XMTW.L", "FRXT.L"],
    "Thailand": ["XCX4.L"],
    "Turkey": ["TURL.L"],
    "United Kingdom": ["CUKX.L", "CSUK.L"],
    "United States": ["SPXL.L"],
    "Vietnam": ["XFVT.L"],
}

COUNTRY_TO_ISO3 = {
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Brazil": "BRA",
    "Bulgaria": "BGR",
    "Canada": "CAN",
    "China": "CHN",
    "France": "FRA",
    "Germany": "DEU",
    "Greece": "GRC",
    "Hong Kong": "HKG",
    "India": "IND",
    "Indonesia": "IDN",
    "Italy": "ITA",
    "Japan": "JPN",
    "Kuwait": "KWT",
    "Malaysia": "MYS",
    "Mexico": "MEX",
    "Netherlands": "NLD",
    "Pakistan": "PAK",
    "Philippines": "PHL",
    "Poland": "POL",
    "Saudi Arabia": "SAU",
    "Singapore": "SGP",
    "South Africa": "ZAF",
    "South Korea": "KOR",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "Taiwan": "TWN",
    "Thailand": "THA",
    "Turkey": "TUR",
    "United Kingdom": "GBR",
    "United States": "USA",
    "Vietnam": "VNM",
}


def choose_etf_price_columns(columns: list[str]) -> dict[str, tuple[str, str]]:
    """Return ticker -> (price_column_name, source_field) with Adj Close fallback."""
    legacy_pattern = re.compile(r"\('([^']+)', '([^']+)'\)_price")
    ticker_fields: dict[str, dict[str, str]] = {}
    for col in columns:
        legacy_match = legacy_pattern.match(col)
        if legacy_match:
            field, ticker = legacy_match.groups()
            ticker_fields.setdefault(ticker, {})[field] = col
            continue

        # New format from fetch_etf_prices.py: "<Label> - <TICKER> - Adj Close"
        parts = col.rsplit(" - ", 2)
        if len(parts) == 3:
            _, ticker, field = parts
            if field in {"Adj Close", "Close"}:
                ticker_fields.setdefault(ticker, {})[field] = col

    selected: dict[str, tuple[str, str]] = {}
    for ticker, fields in ticker_fields.items():
        if "Adj Close" in fields:
            selected[ticker] = (fields["Adj Close"], "Adj Close")
        elif "Close" in fields:
            selected[ticker] = (fields["Close"], "Close")
    return selected


def build_ticker_country_map() -> dict[str, str]:
    ticker_to_country: dict[str, str] = {}
    for country_name, tickers in ETF_COUNTRY_TO_TICKERS.items():
        for ticker in tickers:
            ticker_to_country[ticker] = country_name
    return ticker_to_country


def compute_annual_etf_returns(etf_csv: str) -> pd.DataFrame:
    raw = pd.read_csv(etf_csv)
    selected = choose_etf_price_columns(raw.columns.tolist())
    ticker_country = build_ticker_country_map()

    keep_cols = ["Date"] + [col for col, _ in selected.values()]
    frame = raw[keep_cols].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"])
    frame["year"] = frame["Date"].dt.year.astype(int)

    chunks: list[pd.DataFrame] = []
    for ticker, (price_col, field_used) in selected.items():
        if ticker not in ticker_country:
            continue
        series = frame[["year", price_col]].rename(columns={price_col: "price"}).dropna()
        if series.empty:
            continue
        annual = (
            series.groupby("year", as_index=False)["price"]
            .agg(etf_price_start="first", etf_price_end="last")
            .sort_values("year")
        )
        annual["etf_return_pct"] = (
            (annual["etf_price_end"] / annual["etf_price_start"]) - 1.0
        ) * 100.0
        annual["ticker"] = ticker
        annual["etf_price_field"] = field_used
        annual["country_name"] = ticker_country[ticker]
        annual["country_code"] = annual["country_name"].map(COUNTRY_TO_ISO3)
        chunks.append(annual)

    if not chunks:
        raise RuntimeError("No ETF annual return rows were produced from etf_prices.csv")
    return pd.concat(chunks, ignore_index=True)


def load_weo_gdp(weo_csv: str) -> pd.DataFrame:
    weo = pd.read_csv(weo_csv)
    weo = weo.copy()
    weo["year"] = pd.to_numeric(weo["year"], errors="coerce").astype("Int64")
    weo["value"] = pd.to_numeric(weo["value"], errors="coerce")
    weo = weo.dropna(subset=["year", "country_code", "indicator"])
    weo["year"] = weo["year"].astype(int)

    pivot = (
        weo.pivot_table(
            index=["country_code", "year"],
            columns="indicator",
            values="value",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    return pivot.rename(
        columns={
            "NGDPD": "gdp_current_usd",
            "NGDP_RPCH": "gdp_real_growth_pct",
        }
    )


def build_combined_dataset(etf_csv: str, weo_csv: str) -> pd.DataFrame:
    etf_annual = compute_annual_etf_returns(etf_csv)
    gdp = load_weo_gdp(weo_csv)

    merged = etf_annual.merge(gdp, on=["country_code", "year"], how="left")
    merged["etf_minus_gdp_growth_pct"] = (
        merged["etf_return_pct"] - merged["gdp_real_growth_pct"]
    )
    return merged[
        [
            "country_name",
            "country_code",
            "ticker",
            "etf_price_field",
            "year",
            "etf_price_start",
            "etf_price_end",
            "etf_return_pct",
            "gdp_current_usd",
            "gdp_real_growth_pct",
            "etf_minus_gdp_growth_pct",
        ]
    ].sort_values(["country_name", "ticker", "year"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build normalized annual ETF returns merged with IMF WEO GDP metrics."
    )
    parser.add_argument("--etf-csv", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--output", default="data/outputs/etf_weo_combined_annual.csv")
    args = parser.parse_args()

    combined = build_combined_dataset(args.etf_csv, args.weo_csv)
    combined.to_csv(args.output, index=False)
    print(f"Wrote {len(combined)} rows to {args.output}")
    print(
        f"Tickers: {combined['ticker'].nunique()}, "
        f"Countries: {combined['country_code'].nunique()}, "
        f"Years: {combined['year'].min()}-{combined['year'].max()}"
    )


if __name__ == "__main__":
    main()
