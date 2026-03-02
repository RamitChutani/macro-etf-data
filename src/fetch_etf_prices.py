#!/usr/bin/env python3
"""Fetch daily ETF prices using refined close-only notebook logic."""

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


ALLOWED_CURRENCIES = {"GBP", "GBp"}


def build_pretty_col(label: str, ticker: str) -> str:
    return f"{label} - {ticker} - Close"


def fetch_ticker_history_close(
    label: str,
    ticker: str,
    start: str | None,
    end: str,
) -> tuple[pd.Series | None, dict[str, str | None]]:
    info_row: dict[str, str | None] = {
        "label": label,
        "ticker": ticker,
        "exchange": None,
        "currency": None,
        "quote_type": None,
        "included": "no",
        "reason": None,
    }
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        currency = info.get("currency")
        info_row["exchange"] = info.get("exchange")
        info_row["currency"] = currency
        info_row["quote_type"] = info.get("quoteType")

        if currency not in ALLOWED_CURRENCIES:
            info_row["reason"] = f"unsupported currency {currency}"
            return None, info_row

        history_kwargs: dict[str, object] = {
            "end": end,
            "interval": "1d",
            "auto_adjust": False,
            "actions": True,
        }
        if start:
            history_kwargs["start"] = start
        else:
            history_kwargs["period"] = "max"

        hist = tk.history(**history_kwargs)
        if hist.empty or "Close" not in hist.columns:
            info_row["reason"] = "no close history returned"
            return None, info_row

        close = hist["Close"].copy().dropna()
        if close.empty:
            info_row["reason"] = "close series is empty after dropna"
            return None, info_row

        # Normalize GBp (pence) to GBP (pounds) to align comparisons.
        if currency == "GBp":
            close = close * 0.01

        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        close.name = build_pretty_col(label, ticker)

        info_row["included"] = "yes"
        info_row["reason"] = ""
        return close, info_row
    except Exception as exc:
        info_row["reason"] = str(exc)
        return None, info_row


def fetch_daily_prices(start: str | None, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_series: list[pd.Series] = []
    metadata_rows: list[dict[str, str | None]] = []

    for label, ticker in ETF_LABEL_TO_TICKER.items():
        series, meta = fetch_ticker_history_close(label, ticker, start, end)
        metadata_rows.append(meta)
        if series is not None:
            all_series.append(series)

    if not all_series:
        raise RuntimeError("No ETF close series were produced from configured tickers.")

    prices = pd.concat(all_series, axis=1, sort=True)
    desired_order = [build_pretty_col(label, ticker) for label, ticker in ETF_LABEL_TO_TICKER.items()]
    prices = prices.reindex(columns=[c for c in desired_order if c in prices.columns])
    prices = prices.sort_index().dropna(how="all")

    metadata = pd.DataFrame(metadata_rows)
    return prices, metadata


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
    parser.add_argument(
        "--start",
        default=None,
        help="Optional start date (YYYY-MM-DD). If omitted, fetches full Yahoo history.",
    )
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--output", default="data/outputs/etf_prices.csv")
    parser.add_argument(
        "--metadata-output",
        default="data/outputs/etf_ticker_metadata.csv",
        help="Per-ticker fetch/currency metadata output CSV.",
    )
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

    prices, metadata = fetch_daily_prices(args.start, args.end)
    df = to_export_frame(prices)
    df.to_csv(args.output, index=False)
    metadata.to_csv(args.metadata_output, index=False)
    included = int((metadata["included"] == "yes").sum())
    print(
        f"Wrote {len(df)} rows and {len(df.columns)} columns to {args.output} "
        f"for {args.start or 'MAX'} to {args.end}"
    )
    print(
        f"Wrote ticker metadata to {args.metadata_output}. "
        f"Included tickers: {included}/{len(metadata)}"
    )


if __name__ == "__main__":
    main()
