#!/usr/bin/env python3
"""Fetch daily ETF prices using refined close-only notebook logic."""

from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd
import yfinance as yf

from etf_mapping import build_label_to_ticker_map


ETF_LABEL_TO_TICKER = build_label_to_ticker_map()


REQUIRED_EXCHANGE = "LSE"
REQUIRED_QUOTE_TYPE = "ETF"
ALLOWED_CURRENCIES = {"GBP", "GBp", "USD", "EUR"}


def build_pretty_col(label: str, ticker: str) -> str:
    return f"{label} - {ticker} - Close"


def fetch_ticker_history_close(
    label: str,
    ticker: str,
    start: str | None,
    end: str,
) -> tuple[pd.Series | None, dict[str, object | None]]:
    info_row: dict[str, object | None] = {
        "label": label,
        "ticker": ticker,
        "exchange": None,
        "currency": None,
        "quote_type": None,
        "total_assets": None,
        "net_assets": None,
        "fund_size": None,
        "fund_size_currency": None,
        "fund_size_field": None,
        "included": "no",
        "reason": None,
    }
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        currency = info.get("currency")
        exchange = info.get("exchange")
        quote_type = info.get("quoteType")
        total_assets = info.get("totalAssets")
        net_assets = info.get("netAssets")
        fund_size = total_assets
        if fund_size is None:
            fund_size = net_assets
            if fund_size is not None:
                info_row["fund_size_field"] = "netAssets"
        else:
            info_row["fund_size_field"] = "totalAssets"

        info_row["exchange"] = exchange
        info_row["currency"] = currency
        info_row["quote_type"] = quote_type
        info_row["total_assets"] = total_assets
        info_row["net_assets"] = net_assets
        info_row["fund_size"] = fund_size
        info_row["fund_size_currency"] = currency

        if exchange != REQUIRED_EXCHANGE:
            info_row["reason"] = f"unsupported exchange {exchange}"
            return None, info_row
        if quote_type != REQUIRED_QUOTE_TYPE:
            info_row["reason"] = f"unsupported quoteType {quote_type}"
            return None, info_row
        if not currency:
            info_row["reason"] = "missing currency"
            return None, info_row
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
    metadata_rows: list[dict[str, object | None]] = []

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
