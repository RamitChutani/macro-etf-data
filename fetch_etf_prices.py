#!/usr/bin/env python3
"""Fetch daily ETF prices from Yahoo Finance and export a normalized CSV."""

from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd
import yfinance as yf


# Keep label -> ticker semantics aligned with prior notebook output.
ETF_LABEL_TO_TICKER = {
    "Australia": "SAUS.L",
    "Austria": "XB4A.L",
    "Belgium": "BEL.L",
    "Brazil": "XMBR.L",
    "Bulgaria": "BGX.L",
    "Canada": "CSCA.L",
    "China_1": "IASH.L",
    "China_2": "FRCH.L",
    "France_1": "ISFR.L",
    "France_2": "CACC.L",
    "Germany": "XDAX.L",
    "Greece": "GRE.L",
    "Hong Kong": "HKDU.L",
    "India_1": "IIND.L",
    "India_2": "FRIN.L",
    "Indonesia": "INDO.L",
    "Italy": "CMIB.L",
    "Japan_1": "LCJP.L",
    "Japan_2": "IJPN.L",
    "Kuwait": "MKUW.L",
    "Malaysia": "XCX3.L",
    "Mexico": "XMEX.L",
    "Netherlands": "IAEA.L",
    "Pakistan": "XBAK.L",
    "Philippines": "XPHG.L",
    "Poland": "SPOL.L",
    "Saudi Arabia": "IKSA.L",
    "Singapore": "XBAS.L",
    "South Africa": "SRSA.L",
    "South Korea_1": "CSKR.L",
    "South Korea_2": "FLRK.L",
    "Spain_1": "CS1.L",
    "Spain_2": "XESP.L",
    "Sweden": "OMXS.L",
    "Switzerland": "CHUSD.L",
    "Taiwan_1": "XMTW.L",
    "Taiwan_2": "FRXT.L",
    "Thailand": "XCX4.L",
    "Turkey": "TURL.L",
    "United Kingdom_1": "CUKX.L",
    "United Kingdom_2": "CSUK.L",
    "United States": "SPXL.L",
    "Vietnam": "XFVT.L",
}


def build_pretty_col(label: str, ticker: str) -> str:
    return f"{label} - {ticker} - Adj Close"


def fetch_daily_prices(start: str, end: str) -> pd.DataFrame:
    raw = yf.download(
        tickers=list(ETF_LABEL_TO_TICKER.values()),
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        actions=True,
        group_by="column",
        progress=False,
        threads=True,
    )
    if raw.empty:
        raise RuntimeError("No ETF rows returned by yfinance download.")

    if "Adj Close" in raw.columns.get_level_values(0):
        prices = raw["Adj Close"].copy()
    elif "Close" in raw.columns.get_level_values(0):
        prices = raw["Close"].copy()
    else:
        raise RuntimeError("No Adj Close or Close series found in yfinance output.")

    prices.columns = [
        build_pretty_col(label, ticker)
        for label, ticker in ETF_LABEL_TO_TICKER.items()
        if ticker in prices.columns
    ]
    desired_order = [build_pretty_col(label, ticker) for label, ticker in ETF_LABEL_TO_TICKER.items()]
    prices = prices.reindex(columns=desired_order)
    prices = prices.dropna(how="all")
    return prices


def to_export_frame(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.reset_index()
    if "Date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Date"})
    date_series = pd.to_datetime(df["Date"], errors="coerce")
    df.insert(1, "Year", date_series.dt.year)
    df.insert(2, "Month", date_series.dt.month)
    return df


def inspect_tickers() -> pd.DataFrame:
    rows: list[dict[str, str | None]] = []
    for label, ticker in ETF_LABEL_TO_TICKER.items():
        try:
            info = yf.Ticker(ticker).info
            first_trade = info.get("firstTradeDateEpochUtc")
            rows.append(
                {
                    "label": label,
                    "ticker": ticker,
                    "exchange": info.get("exchange"),
                    "currency": info.get("currency"),
                    "quote_type": info.get("quoteType"),
                    "start_date": (
                        datetime.utcfromtimestamp(first_trade).strftime("%Y-%m-%d")
                        if first_trade
                        else None
                    ),
                }
            )
        except Exception as exc:
            rows.append({"label": label, "ticker": ticker, "error": str(exc)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch daily ETF prices and export etf_prices.csv-style output."
    )
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--output", default="etf_prices.csv")
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Only print ticker metadata checks; do not fetch price history.",
    )
    args = parser.parse_args()

    if args.inspect_only:
        details = inspect_tickers()
        print(details.to_string(index=False))
        return

    prices = fetch_daily_prices(args.start, args.end)
    df = to_export_frame(prices)
    df.to_csv(args.output, index=False)
    print(
        f"Wrote {len(df)} rows and {len(df.columns)} columns to {args.output} "
        f"for {args.start} to {args.end}"
    )


if __name__ == "__main__":
    main()
