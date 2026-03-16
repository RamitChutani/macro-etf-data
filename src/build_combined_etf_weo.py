#!/usr/bin/env python3
"""Build a normalized annual ETF+WEO dataset for dashboard use."""

from __future__ import annotations

import argparse
import re

import pandas as pd
import yfinance as yf

from etf_mapping import COUNTRY_TO_ISO3, COUNTRY_TO_LCU, build_ticker_country_map


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


def load_ticker_hedged_map(metadata_csv: str | None) -> dict[str, str]:
    if not metadata_csv:
        return {}
    try:
        meta = pd.read_csv(metadata_csv)
    except FileNotFoundError:
        return {}
    required = {"ticker", "currency_hedged"}
    if not required.issubset(set(meta.columns)):
        return {}
    meta = meta.copy()
    meta["ticker"] = meta["ticker"].astype(str)
    meta["currency_hedged"] = meta["currency_hedged"].fillna("unknown").astype(str)
    return (
        meta[["ticker", "currency_hedged"]]
        .drop_duplicates(subset=["ticker"], keep="first")
        .set_index("ticker")["currency_hedged"]
        .to_dict()
    )


def normalize_currency_code(currency: str) -> str:
    c = str(currency or "").strip()
    if c == "GBp":
        return "GBP"
    return c


def compute_annual_fx_quote_to_usd_returns(
    currencies: set[str],
    min_year: int,
    max_year: int,
) -> dict[tuple[str, int], float]:
    """Calculate annual FX return within each year (First vs Last trade day)."""
    out: dict[tuple[str, int], float] = {}
    for currency in sorted(currencies):
        ccy = normalize_currency_code(currency)
        if not ccy:
            continue
        if ccy == "USD":
            for year in range(min_year, max_year + 1):
                out[(ccy, year)] = 0.0
            continue

        series: pd.Series | None = None
        for pair, invert in ((f"{ccy}USD=X", False), (f"USD{ccy}=X", True)):
            hist = yf.Ticker(pair).history(
                period="max",
                interval="1d",
                auto_adjust=True,
                actions=False,
            )
            if hist.empty or "Close" not in hist.columns:
                continue
            s = hist["Close"].dropna()
            if s.empty:
                continue
            if getattr(s.index, "tz", None) is not None:
                s.index = s.index.tz_localize(None)
            if invert:
                s = 1.0 / s
            series = s
            break

        if series is None or series.empty:
            continue

        frame = pd.DataFrame({"Date": series.index, "fx": series.values})
        frame["year"] = frame["Date"].dt.year.astype(int)
        annual = (
            frame.groupby("year", as_index=False)["fx"]
            .agg(fx_start="first", fx_end="last")
            .sort_values("year")
        )
        annual["fx_quote_vs_usd_pct"] = ((annual["fx_end"] / annual["fx_start"]) - 1.0) * 100.0
        for row in annual.itertuples(index=False):
            year = int(row.year)
            if min_year <= year <= max_year:
                out[(ccy, year)] = float(row.fx_quote_vs_usd_pct)
    return out


def compute_annual_jan1_fx_returns(
    currencies: set[str],
    min_year: int,
    max_year: int,
) -> dict[tuple[str, int], float]:
    """Calculate point-to-point FX returns (Jan 1st of year t to Jan 1st of year t+1)."""
    out: dict[tuple[str, int], float] = {}
    for currency in sorted(currencies):
        ccy = normalize_currency_code(currency)
        if not ccy or ccy == "USD":
            for year in range(min_year, max_year + 1):
                out[(ccy, year)] = 0.0
            continue

        series: pd.Series | None = None
        for pair, invert in ((f"{ccy}USD=X", False), (f"USD{ccy}=X", True)):
            hist = yf.Ticker(pair).history(period="max", interval="1d", auto_adjust=True, actions=False)
            if hist.empty or "Close" not in hist.columns:
                continue
            s = hist["Close"].dropna()
            if s.empty:
                continue
            if getattr(s.index, "tz", None) is not None:
                s.index = s.index.tz_localize(None)
            if invert:
                s = 1.0 / s
            series = s
            break

        if series is None or series.empty:
            continue

        # Get first trading day for each year
        first_days = series.to_frame(name="fx").assign(year=series.index.year).groupby("year").head(1)
        
        # Shift back to get previous Jan 1st for calculating current year return
        first_days["prev_jan1_fx"] = first_days["fx"].shift(1)
        first_days["jan1_fx_pct"] = ((first_days["fx"] / first_days["prev_jan1_fx"]) - 1.0) * 100.0
        
        # IMPORTANT: jan1_fx_pct at year T represents return over the period Jan 1 T-1 to Jan 1 T.
        # However, for annual data comparison (e.g. GDP for year T), 
        # the user usually wants the return OVER the course of year T (Jan 1 T to Jan 1 T+1).
        first_days["fx_over_year_pct"] = first_days["jan1_fx_pct"].shift(-1)

        for row in first_days.itertuples():
            year_val = int(row.Index.year)
            pct = row.fx_over_year_pct
            if min_year <= year_val <= max_year:
                out[(ccy, year_val)] = float(pct)
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
        
        # Identify the first year with a non-zero price
        valid_series = series[series["price"] > 0]
        if valid_series.empty:
            continue
        inception_year = int(valid_series["year"].min())

        annual = (
            series.groupby("year", as_index=False)["price"]
            .agg(etf_price_start="first", etf_price_end="last")
            .sort_values("year")
        )
        # Calculate return only if year >= inception and start price > 0
        annual["etf_return_pct"] = annual.apply(
            lambda r: (
                ((r["etf_price_end"] / r["etf_price_start"]) - 1.0) * 100.0
                if (int(r["year"]) >= inception_year and r["etf_price_start"] > 0)
                else None
            ),
            axis=1
        )
        annual["ticker"] = ticker
        annual["etf_price_field"] = field_used
        annual["country_name"] = ticker_country[ticker]
        annual["country_code"] = annual["country_name"].map(COUNTRY_TO_ISO3)
        annual["etf_currency"] = ticker_currency.get(ticker, "")
        annual["etf_currency_normalized"] = annual["etf_currency"].map(normalize_currency_code)
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
            "NGDP": "gdp_current_lcu",
            "NGDP_RPCH": "gdp_real_growth_pct",
            "NGDPD_PCH": "gdp_nominal_growth_pct",
            "PCPIPCH": "inflation_cpi_pct",
            "NGDP_D": "gdp_deflator_index",
        }
    )
    
    # Calculate GDP Deflator percent change
    pivot = pivot.sort_values(["country_code", "year"])
    if "gdp_deflator_index" in pivot.columns:
        pivot["inflation_deflator_pct"] = (
            pivot.groupby("country_code")["gdp_deflator_index"].pct_change() * 100.0
        )

    # Backward-compatible fallback if nominal growth rows are missing.
    if "gdp_nominal_growth_pct" not in pivot.columns and "gdp_current_usd" in pivot.columns:
        pivot["gdp_nominal_growth_pct"] = (
            pivot.groupby("country_code")["gdp_current_usd"].pct_change() * 100.0
        )
    
    if "gdp_current_lcu" in pivot.columns and "gdp_current_usd" in pivot.columns:
        # Implied exchange rate (LCU per USD)
        pivot["country_lcu_per_usd_weo"] = (
            pivot["gdp_current_lcu"] / pivot["gdp_current_usd"]
        )
        
        # Calculate Local Currency return vs USD (Inverted: USD per LCU)
        # return = (prev_rate / current_rate) - 1
        pivot["country_lcu_vs_usd_weo_pct"] = (
            pivot.groupby("country_code")["country_lcu_per_usd_weo"].shift(1) 
            / pivot["country_lcu_per_usd_weo"] - 1.0
        ) * 100.0
        
        # 10Y CAGR of LCU vs USD (USD per LCU terms)
        # CAGR = ( (1/XR_t) / (1/XR_t-10) )^(1/10) - 1 = (XR_t-10 / XR_t)^(1/10) - 1
        pivot["country_lcu_vs_usd_10y_cagr"] = (
            (pivot.groupby("country_code")["country_lcu_per_usd_weo"].shift(10) 
             / pivot["country_lcu_per_usd_weo"])**(1/10) - 1.0
        ) * 100.0

    # Inflation Differentials vs USA
    usa_data = pivot[pivot["country_code"] == "USA"][["year", "inflation_cpi_pct", "inflation_deflator_pct"]].copy()
    usa_data = usa_data.rename(columns={
        "inflation_cpi_pct": "usa_inflation_cpi_pct",
        "inflation_deflator_pct": "usa_inflation_deflator_pct"
    })
    
    pivot = pivot.merge(usa_data, on="year", how="left")
    
    # Calculate geometric 10Y CAGR of the differentials
    # CAGR = [ Product(1 + diff_i/100) ]^(1/10) - 1
    if "inflation_cpi_pct" in pivot.columns:
        pivot["inflation_cpi_diff"] = pivot["inflation_cpi_pct"] - pivot["usa_inflation_cpi_pct"]
        # Convert to multiplier: (1 + diff/100)
        pivot["_cpi_diff_mult"] = 1.0 + (pivot["inflation_cpi_diff"] / 100.0)
        pivot["inflation_cpi_diff_10y_avg"] = (
            pivot.groupby("country_code")["_cpi_diff_mult"].transform(
                lambda x: (x.rolling(10).apply(lambda window: window.prod(), raw=True))**(1/10) - 1.0
            )
        ) * 100.0
        
    if "inflation_deflator_pct" in pivot.columns:
        pivot["inflation_deflator_diff"] = pivot["inflation_deflator_pct"] - pivot["usa_inflation_deflator_pct"]
        # Convert to multiplier: (1 + diff/100)
        pivot["_defl_diff_mult"] = 1.0 + (pivot["inflation_deflator_diff"] / 100.0)
        pivot["inflation_deflator_diff_10y_avg"] = (
            pivot.groupby("country_code")["_defl_diff_mult"].transform(
                lambda x: (x.rolling(10).apply(lambda window: window.prod(), raw=True))**(1/10) - 1.0
            )
        ) * 100.0

    # Cleanup temporary multiplier columns
    cols_to_drop = [c for c in ["_cpi_diff_mult", "_defl_diff_mult"] if c in pivot.columns]
    if cols_to_drop:
        pivot = pivot.drop(columns=cols_to_drop)

    return pivot


def build_combined_dataset(
    etf_csv: str, weo_csv: str, metadata_csv: str | None = None
) -> pd.DataFrame:
    etf_annual = compute_annual_etf_returns(etf_csv, metadata_csv)
    ticker_hedged = load_ticker_hedged_map(metadata_csv)
    gdp = load_weo_gdp(weo_csv)

    min_year = int(etf_annual["year"].min())
    max_year = int(etf_annual["year"].max())
    currencies = set(etf_annual["etf_currency_normalized"].dropna().astype(str).tolist())
    fx_map = compute_annual_fx_quote_to_usd_returns(currencies, min_year, max_year)
    fx_jan1_map = compute_annual_jan1_fx_returns(currencies, min_year, max_year)
    
    # Compute Jan 1 FX returns for country LCUs (for dashboard FX Jan 1 CAGR column)
    country_lcu_currencies = set(COUNTRY_TO_LCU.values())
    country_lcu_fx_jan1_map = compute_annual_jan1_fx_returns(country_lcu_currencies, min_year, max_year)
    
    etf_annual["quote_ccy_vs_usd_pct"] = etf_annual.apply(
        lambda r: fx_map.get((str(r.etf_currency_normalized), int(r.year))),
        axis=1,
    )
    etf_annual["quote_ccy_vs_usd_jan1_pct"] = etf_annual.apply(
        lambda r: fx_jan1_map.get((str(r.etf_currency_normalized), int(r.year))),
        axis=1,
    )
    # Country LCU vs USD Jan 1 return (for dashboard consistency with FX CAGR)
    etf_annual["country_lcu_vs_usd_jan1_pct"] = etf_annual.apply(
        lambda r: country_lcu_fx_jan1_map.get((COUNTRY_TO_LCU.get(r.country_name), int(r.year))),
        axis=1,
    )
    etf_annual["etf_return_quote_pct"] = etf_annual["etf_return_pct"]
    
    # Calculate USD return
    etf_annual["etf_return_usd_pct"] = etf_annual.apply(
        lambda r: (
            ((1.0 + (r["etf_return_quote_pct"] / 100.0))
             * (1.0 + (r["quote_ccy_vs_usd_pct"] / 100.0)))
            - 1.0
        ) * 100.0 if (pd.notna(r["etf_return_quote_pct"]) and pd.notna(r["quote_ccy_vs_usd_pct"]))
        else None,
        axis=1
    )
    # Special case: If ticker currency is USD, return is already USD
    usd_mask = etf_annual["etf_currency_normalized"] == "USD"
    etf_annual.loc[usd_mask, "etf_return_usd_pct"] = etf_annual.loc[usd_mask, "etf_return_quote_pct"]

    etf_annual["etf_return_usd_pct"] = etf_annual["etf_return_usd_pct"].replace(
        [float("inf"), float("-inf")], None
    )

    merged = etf_annual.merge(gdp, on=["country_code", "year"], how="left")
    merged["currency_hedged"] = merged["ticker"].map(ticker_hedged).fillna("unknown")

    merged["etf_usd_minus_country_fx_pct"] = merged.apply(
        lambda r: (
            ((1.0 + (r["etf_return_usd_pct"] / 100.0))
             / (1.0 + (r["country_lcu_vs_usd_weo_pct"] / 100.0)))
            - 1.0
        ) * 100.0 if (pd.notna(r["etf_return_usd_pct"]) and pd.notna(r["country_lcu_vs_usd_weo_pct"]) and (1.0 + (r["country_lcu_vs_usd_weo_pct"] / 100.0)) != 0)
        else None,
        axis=1
    )

    # Real GDP Disconnect
    merged["gdp_real_minus_etf_growth_pct"] = merged.apply(
        lambda r: r["gdp_real_growth_pct"] - r["etf_return_usd_pct"]
        if (pd.notna(r["gdp_real_growth_pct"]) and pd.notna(r["etf_return_usd_pct"]))
        else None,
        axis=1
    )
    # Nominal USD GDP Disconnect
    merged["gdp_nominal_minus_etf_growth_pct"] = merged.apply(
        lambda r: r["gdp_nominal_growth_pct"] - r["etf_return_usd_pct"]
        if (pd.notna(r["gdp_nominal_growth_pct"]) and pd.notna(r["etf_return_usd_pct"]))
        else None,
        axis=1
    )
    # Backward-compatible column
    merged["gdp_minus_etf_growth_pct"] = merged["gdp_real_minus_etf_growth_pct"]
    return merged[
        [
            "country_name",
            "country_code",
            "ticker",
            "etf_currency",
            "currency_hedged",
            "etf_price_field",
            "year",
            "etf_price_start",
            "etf_price_end",
            "etf_return_pct",
            "etf_return_quote_pct",
            "quote_ccy_vs_usd_pct",
            "etf_return_usd_pct",
            "country_lcu_vs_usd_weo_pct",
            "country_lcu_vs_usd_10y_cagr",
            "inflation_cpi_diff_10y_avg",
            "inflation_deflator_diff_10y_avg",
            "etf_usd_minus_country_fx_pct",
            "gdp_current_usd",
            "gdp_current_lcu",
            "gdp_real_growth_pct",
            "gdp_nominal_growth_pct",
            "gdp_real_minus_etf_growth_pct",
            "gdp_nominal_minus_etf_growth_pct",
            "gdp_minus_etf_growth_pct",
            "quote_ccy_vs_usd_jan1_pct",
            "country_lcu_vs_usd_jan1_pct",
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
