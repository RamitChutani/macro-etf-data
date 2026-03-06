#!/usr/bin/env python3
"""Fetch daily ETF prices using refined close-only notebook logic."""

from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd
import yfinance as yf

from etf_mapping import build_label_to_ticker_map


ETF_LABEL_TO_TICKER = build_label_to_ticker_map()


DISALLOWED_EXCHANGES: set[str] = {
    # Add any specific exchanges to exclude here in the future
}
REQUIRED_QUOTE_TYPE = "ETF"
ALLOWED_CURRENCIES = {"GBP", "GBp", "USD", "EUR"}
DEFAULT_MIN_HISTORY_ROWS = 252
DEFAULT_MAX_STALE_DAYS = 45
DEFAULT_MIN_HISTORY_START = "2020-01-01"


def detect_currency_hedged(text: str) -> tuple[str, str]:
    t = (text or "").lower()
    if not t:
        return "unknown", "no_name_text"
    hedged_markers = [
        "currency hedged",
        "fx hedged",
        "hedged",
        "usd hedged",
        "eur hedged",
        "gbp hedged",
    ]
    unhedged_markers = [
        "unhedged",
        "not hedged",
    ]
    for marker in unhedged_markers:
        if marker in t:
            return "no", f"name_marker:{marker}"
    for marker in hedged_markers:
        if marker in t:
            return "yes", f"name_marker:{marker}"
    return "unknown", "no_name_marker"


def build_pretty_col(label: str, ticker: str) -> str:
    return f"{label} - {ticker} - Close"


def fetch_ticker_history_close(
    label: str,
    ticker: str,
    start: str | None,
    end: str,
    min_history_rows: int = DEFAULT_MIN_HISTORY_ROWS,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
    min_history_start: str | None = DEFAULT_MIN_HISTORY_START,
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
        "long_name": None,
        "short_name": None,
        "currency_hedged": None,
        "currency_hedged_basis": None,
        "history_start_date": None,
        "history_end_date": None,
        "history_rows": None,
        "history_stale_days": None,
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
        long_name = str(info.get("longName") or "")
        short_name = str(info.get("shortName") or "")
        hedged_flag, hedged_basis = detect_currency_hedged(f"{long_name} {short_name}")
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
        info_row["long_name"] = long_name
        info_row["short_name"] = short_name
        info_row["currency_hedged"] = hedged_flag
        info_row["currency_hedged_basis"] = hedged_basis

        if exchange in DISALLOWED_EXCHANGES:
            info_row["reason"] = f"disallowed exchange {exchange}"
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

        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)

        history_start_date = close.index.min().strftime("%Y-%m-%d")
        history_end_date = close.index.max().strftime("%Y-%m-%d")
        history_rows = int(close.shape[0])
        today = pd.to_datetime(end).normalize()
        history_end_ts = pd.to_datetime(history_end_date).normalize()
        history_stale_days = int((today - history_end_ts).days)

        info_row["history_start_date"] = history_start_date
        info_row["history_end_date"] = history_end_date
        info_row["history_rows"] = history_rows
        info_row["history_stale_days"] = history_stale_days

        if history_rows < int(min_history_rows):
            info_row["reason"] = f"insufficient history rows ({history_rows} < {int(min_history_rows)})"
            return None, info_row
        if history_stale_days > int(max_stale_days):
            info_row["reason"] = f"history is stale ({history_stale_days}d > {int(max_stale_days)}d)"
            return None, info_row
        if min_history_start:
            min_start_ts = pd.to_datetime(min_history_start)
            actual_start_ts = pd.to_datetime(history_start_date)
            if actual_start_ts > min_start_ts:
                info_row["reason"] = (
                    f"history starts too late ({history_start_date} > {min_history_start})"
                )
                return None, info_row

        # Normalize GBp (pence) to GBP (pounds) to align comparisons.
        if currency == "GBp":
            close = close * 0.01

        close.name = build_pretty_col(label, ticker)

        info_row["included"] = "yes"
        info_row["reason"] = ""
        return close, info_row
    except Exception as exc:
        info_row["reason"] = str(exc)
        return None, info_row


def fetch_daily_prices(
    start: str | None,
    end: str,
    min_history_rows: int = DEFAULT_MIN_HISTORY_ROWS,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
    min_history_start: str | None = DEFAULT_MIN_HISTORY_START,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_series: list[pd.Series] = []
    metadata_rows: list[dict[str, object | None]] = []

    for label, ticker in ETF_LABEL_TO_TICKER.items():
        series, meta = fetch_ticker_history_close(
            label,
            ticker,
            start,
            end,
            min_history_rows=min_history_rows,
            max_stale_days=max_stale_days,
            min_history_start=min_history_start,
        )
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


def inspect_tickers(
    candidate_tickers: list[str] | None = None,
    min_history_start: str | None = None,
    min_history_rows: int | None = None,
    max_stale_days: int | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object | None]] = []
    ticker_pairs: list[tuple[str, str]]
    if candidate_tickers:
        ticker_pairs = [(ticker, ticker) for ticker in candidate_tickers]
    else:
        ticker_pairs = list(ETF_LABEL_TO_TICKER.items())

    min_history_start_ts = pd.to_datetime(min_history_start) if min_history_start else None
    today_ts = pd.Timestamp.today().normalize()

    for label, ticker in ticker_pairs:
        try:
            tk = yf.Ticker(ticker)
            info = tk.info
            first_trade = info.get("firstTradeDateEpochUtc")
            exchange = info.get("exchange")
            currency = info.get("currency")
            quote_type = info.get("quoteType")
            long_name = str(info.get("longName") or "")
            short_name = str(info.get("shortName") or "")
            hedged_flag, hedged_basis = detect_currency_hedged(f"{long_name} {short_name}")
            row: dict[str, object | None] = {
                "label": label,
                "ticker": ticker,
                "exchange": exchange,
                "currency": currency,
                "quote_type": quote_type,
                "long_name": long_name,
                "short_name": short_name,
                "currency_hedged": hedged_flag,
                "currency_hedged_basis": hedged_basis,
                "start_date": (
                    datetime.utcfromtimestamp(first_trade).strftime("%Y-%m-%d")
                    if first_trade
                    else None
                ),
            }

            reasons: list[str] = []
            if exchange in DISALLOWED_EXCHANGES:
                reasons.append(f"disallowed exchange {exchange}")
            if quote_type != REQUIRED_QUOTE_TYPE:
                reasons.append(f"unsupported quoteType {quote_type}")
            if not currency:
                reasons.append("missing currency")
            elif currency not in ALLOWED_CURRENCIES:
                reasons.append(f"unsupported currency {currency}")

            hist = tk.history(period="max", interval="1d", auto_adjust=False, actions=False)
            if hist.empty or "Close" not in hist.columns:
                row["history_start_date"] = None
                row["history_end_date"] = None
                row["history_rows"] = 0
                reasons.append("no close history returned")
            else:
                close = hist["Close"].dropna()
                if close.empty:
                    row["history_start_date"] = None
                    row["history_end_date"] = None
                    row["history_rows"] = 0
                    reasons.append("close series is empty after dropna")
                else:
                    if getattr(close.index, "tz", None) is not None:
                        close.index = close.index.tz_localize(None)
                    row["history_start_date"] = close.index.min().strftime("%Y-%m-%d")
                    row["history_end_date"] = close.index.max().strftime("%Y-%m-%d")
                    row["history_rows"] = int(close.shape[0])
                    if min_history_rows is not None and int(close.shape[0]) < int(min_history_rows):
                        reasons.append(
                            f"insufficient history rows ({int(close.shape[0])} < {int(min_history_rows)})"
                        )
                    if min_history_start_ts is not None:
                        actual_start = pd.to_datetime(row["history_start_date"])
                        if actual_start > min_history_start_ts:
                            reasons.append(
                                "history starts too late "
                                f"({row['history_start_date']} > {min_history_start})"
                            )
                    if max_stale_days is not None:
                        actual_end = pd.to_datetime(row["history_end_date"]).normalize()
                        stale_days = int((today_ts - actual_end).days)
                        row["history_stale_days"] = stale_days
                        if stale_days > int(max_stale_days):
                            reasons.append(
                                f"history is stale ({stale_days}d > {int(max_stale_days)}d)"
                            )

            row["eligible"] = "yes" if not reasons else "no"
            row["reason"] = "; ".join(reasons)
            rows.append(row)
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
        "--min-history-start",
        default=DEFAULT_MIN_HISTORY_START,
        help=(
            "Minimum acceptable first close date for inclusion (YYYY-MM-DD). "
            "Use empty string to disable."
        ),
    )
    parser.add_argument(
        "--min-history-rows",
        type=int,
        default=DEFAULT_MIN_HISTORY_ROWS,
        help="Minimum non-null close rows required for inclusion.",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=DEFAULT_MAX_STALE_DAYS,
        help="Maximum days since latest close required for inclusion.",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Only print ticker metadata checks; do not fetch price history.",
    )
    parser.add_argument(
        "--candidate-tickers",
        default="",
        help=(
            "Optional comma-separated candidate symbols to inspect instead of the current mapping, "
            "e.g. 'CMIB.L,EWJ,EWU'."
        ),
    )
    parser.add_argument(
        "--inspect-output",
        default="",
        help="Optional CSV output path for inspect results.",
    )
    args = parser.parse_args()

    if args.inspect_only:
        candidate_tickers = [
            ticker.strip() for ticker in args.candidate_tickers.split(",") if ticker.strip()
        ]
        details = inspect_tickers(
            candidate_tickers=candidate_tickers or None,
            min_history_start=args.min_history_start or None,
            min_history_rows=args.min_history_rows,
            max_stale_days=args.max_stale_days,
        )
        print(details.to_string(index=False))
        if args.inspect_output:
            details.to_csv(args.inspect_output, index=False)
            print(f"Wrote inspect report to {args.inspect_output}")
        return

    prices, metadata = fetch_daily_prices(
        args.start,
        args.end,
        min_history_rows=args.min_history_rows,
        max_stale_days=args.max_stale_days,
        min_history_start=args.min_history_start or None,
    )
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
