#!/usr/bin/env python3
"""Build a normalized annual ETF+WEO dataset for dashboard use."""

from __future__ import annotations

import argparse
import re

import pandas as pd

from etf_mapping import COUNTRY_TO_ISO3, build_ticker_country_map


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

def load_ticker_currency_map(metadata_csv: str | None) -> dict[str, str]:
    if not metadata_csv:
        return {}
    try:
        meta = pd.read_csv(metadata_csv)
    except FileNotFoundError:
        return {}
    required = {"ticker", "currency"}
    if not required.issubset(set(meta.columns)):
        return {}
    meta = meta.copy()
    meta["ticker"] = meta["ticker"].astype(str)
    meta["currency"] = meta["currency"].fillna("").astype(str)
    out = (
        meta[["ticker", "currency"]]
        .drop_duplicates(subset=["ticker"], keep="first")
        .set_index("ticker")["currency"]
        .to_dict()
    )
    return out


def compute_annual_etf_returns(etf_csv: str, metadata_csv: str | None = None) -> pd.DataFrame:
    raw = pd.read_csv(etf_csv)
    selected = choose_etf_price_columns(raw.columns.tolist())
    ticker_country = build_ticker_country_map()
    ticker_currency = load_ticker_currency_map(metadata_csv)

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
        annual["etf_currency"] = ticker_currency.get(ticker, "")
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
    pivot = pivot.rename(
        columns={
            "NGDPD": "gdp_current_usd",
            "NGDP_RPCH": "gdp_real_growth_pct",
            "NGDPD_PCH": "gdp_nominal_growth_pct",
        }
    )
    # Backward-compatible fallback if nominal growth rows are missing.
    if "gdp_nominal_growth_pct" not in pivot.columns and "gdp_current_usd" in pivot.columns:
        pivot = pivot.sort_values(["country_code", "year"]).copy()
        pivot["gdp_nominal_growth_pct"] = (
            pivot.groupby("country_code")["gdp_current_usd"].pct_change() * 100.0
        )
    return pivot


def build_combined_dataset(
    etf_csv: str, weo_csv: str, metadata_csv: str | None = None
) -> pd.DataFrame:
    etf_annual = compute_annual_etf_returns(etf_csv, metadata_csv)
    gdp = load_weo_gdp(weo_csv)

    merged = etf_annual.merge(gdp, on=["country_code", "year"], how="left")
    merged["gdp_real_minus_etf_growth_pct"] = (
        merged["gdp_real_growth_pct"] - merged["etf_return_pct"]
    )
    merged["gdp_nominal_minus_etf_growth_pct"] = (
        merged["gdp_nominal_growth_pct"] - merged["etf_return_pct"]
    )
    # Keep existing column name for compatibility; this now explicitly tracks real GDP minus ETF.
    merged["gdp_minus_etf_growth_pct"] = (
        merged["gdp_real_growth_pct"] - merged["etf_return_pct"]
    )
    return merged[
        [
            "country_name",
            "country_code",
            "ticker",
            "etf_currency",
            "etf_price_field",
            "year",
            "etf_price_start",
            "etf_price_end",
            "etf_return_pct",
            "gdp_current_usd",
            "gdp_real_growth_pct",
            "gdp_nominal_growth_pct",
            "gdp_real_minus_etf_growth_pct",
            "gdp_nominal_minus_etf_growth_pct",
            "gdp_minus_etf_growth_pct",
        ]
    ].sort_values(["country_name", "ticker", "year"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build normalized annual ETF returns merged with IMF WEO GDP metrics."
    )
    parser.add_argument("--etf-csv", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument(
        "--metadata-csv",
        default="data/outputs/etf_ticker_metadata.csv",
        help="Optional ticker metadata CSV containing currency by ticker.",
    )
    parser.add_argument("--output", default="data/outputs/etf_weo_combined_annual.csv")
    args = parser.parse_args()

    combined = build_combined_dataset(args.etf_csv, args.weo_csv, args.metadata_csv)
    combined.to_csv(args.output, index=False)
    print(f"Wrote {len(combined)} rows to {args.output}")
    print(
        f"Tickers: {combined['ticker'].nunique()}, "
        f"Countries: {combined['country_code'].nunique()}, "
        f"Years: {combined['year'].min()}-{combined['year'].max()}"
    )


if __name__ == "__main__":
    main()
