#!/usr/bin/env python3
"""Build an Excel MVP dashboard for ETF vs GDP growth comparison."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

import pandas as pd
from openpyxl.utils import get_column_letter

from build_combined_etf_weo import (
    COUNTRY_TO_ISO3,
    build_ticker_country_map,
    compute_annual_fx_quote_to_usd_returns,
    normalize_currency_code,
)


TIMEFRAME_ORDER = [
    "YTD",
    "1 Month",
    "3 Months",
    "6 Months",
    "1 Year",
    "3 Years",
    "5 Years",
    "10 Years",
    "MAX",
]

TIMEFRAME_SPECS: list[tuple[str, object]] = [
    ("YTD", "ytd"),
    ("1 Month", pd.DateOffset(months=1)),
    ("3 Months", pd.DateOffset(months=3)),
    ("6 Months", pd.DateOffset(months=6)),
    ("1 Year", pd.DateOffset(years=1)),
    ("3 Years", pd.DateOffset(years=3)),
    ("5 Years", pd.DateOffset(years=5)),
    ("10 Years", pd.DateOffset(years=10)),
    ("MAX", "max"),
]

ANNUAL_WINDOW_YEARS = 10
CAGR_HORIZONS = [1, 3, 5, 10]
COUNTRY_TO_REGION = {
    "Australia": "Oceania",
    "Austria": "Europe",
    "Belgium": "Europe",
    "Brazil": "Latin America",
    "Bulgaria": "Europe",
    "Canada": "North America",
    "China": "Asia",
    "France": "Europe",
    "Germany": "Europe",
    "Greece": "Europe",
    "Hong Kong": "Asia",
    "India": "Asia",
    "Indonesia": "Asia",
    "Italy": "Europe",
    "Japan": "Asia",
    "Kuwait": "Middle East",
    "Malaysia": "Asia",
    "Mexico": "Latin America",
    "Netherlands": "Europe",
    "Pakistan": "Asia",
    "Philippines": "Asia",
    "Poland": "Europe",
    "Saudi Arabia": "Middle East",
    "Singapore": "Asia",
    "South Africa": "Africa",
    "South Korea": "Asia",
    "Spain": "Europe",
    "Sweden": "Europe",
    "Switzerland": "Europe",
    "Taiwan": "Asia",
    "Thailand": "Asia",
    "Turkey": "Europe",
    "United Kingdom": "Europe",
    "United States": "North America",
    "Vietnam": "Asia",
}


@dataclass
class PricePoint:
    date: pd.Timestamp
    value: float


def last_on_or_before(series: pd.Series, target: pd.Timestamp) -> PricePoint | None:
    s = series.dropna()
    s = s[s.index <= target]
    if s.empty:
        return None
    idx = s.index[-1]
    return PricePoint(date=idx, value=float(s.loc[idx]))


def first_in_year(series: pd.Series, year: int) -> PricePoint | None:
    s = series.dropna()
    s = s[s.index.year == year]
    if s.empty:
        return None
    idx = s.index[0]
    return PricePoint(date=idx, value=float(s.iloc[0]))


def last_in_year(series: pd.Series, year: int) -> PricePoint | None:
    s = series.dropna()
    s = s[s.index.year == year]
    if s.empty:
        return None
    idx = s.index[-1]
    return PricePoint(date=idx, value=float(s.iloc[-1]))


def pct_return(start_value: float, end_value: float) -> float:
    return ((end_value / start_value) - 1.0) * 100.0


def cagr_from_total_return(total_return_pct: float, years: int) -> float:
    return (((1.0 + (total_return_pct / 100.0)) ** (1.0 / years)) - 1.0) * 100.0


def max_start_point(series: pd.Series) -> PricePoint | None:
    s = series.dropna()
    if s.empty:
        return None

    # Guard against bad launch prints / scale breaks near series start.
    ratio = (s / s.shift(1)).dropna()
    suspicious = ratio[(ratio < 0.2) | (ratio > 5.0)]
    if not suspicious.empty:
        window_end = s.index.min() + pd.DateOffset(days=120)
        early_breaks = suspicious[suspicious.index <= window_end]
        if not early_breaks.empty:
            s = s[s.index >= early_breaks.index.min()]
            if s.empty:
                return None

    idx = s.index[1] if len(s) > 1 else s.index[0]
    return PricePoint(date=idx, value=float(s.loc[idx]))


def choose_price_columns(columns: list[str]) -> dict[str, str]:
    """
    Return ticker -> price column.
    Prefers Adj Close if available, otherwise Close.
    """
    pattern = re.compile(r"^(.+?) - ([^- ]+) - (Adj Close|Close)$")
    ticker_fields: dict[str, dict[str, str]] = {}
    for col in columns:
        match = pattern.match(col)
        if not match:
            continue
        _, ticker, field = match.groups()
        ticker_fields.setdefault(ticker, {})[field] = col

    selected: dict[str, str] = {}
    for ticker, fields in ticker_fields.items():
        if "Adj Close" in fields:
            selected[ticker] = fields["Adj Close"]
        elif "Close" in fields:
            selected[ticker] = fields["Close"]
    return selected


def load_gdp_growth_maps(
    weo_csv: str,
) -> tuple[
    dict[tuple[str, int], float],
    dict[tuple[str, int], float],
    dict[tuple[str, int], float],
    dict[tuple[str, int], float],
]:
    weo = pd.read_csv(weo_csv)
    weo["year"] = pd.to_numeric(weo["year"], errors="coerce").astype("Int64")
    weo["value"] = pd.to_numeric(weo["value"], errors="coerce")
    weo = weo.dropna(subset=["country_code", "year"])
    weo["year"] = weo["year"].astype(int)
    real_weo = weo[(weo["indicator"] == "NGDP_RPCH") & (weo["value"].notna())].copy()
    nominal_usd_weo = weo[(weo["indicator"] == "NGDPD_PCH") & (weo["value"].notna())].copy()
    nominal_lcu_weo = weo[(weo["indicator"] == "NGDP_PCH") & (weo["value"].notna())].copy()

    real_map = {
        (str(r.country_code), int(r.year)): float(r.value)
        for r in real_weo.itertuples(index=False)
    }
    nominal_usd_map = {
        (str(r.country_code), int(r.year)): float(r.value)
        for r in nominal_usd_weo.itertuples(index=False)
    }
    nominal_lcu_map = {
        (str(r.country_code), int(r.year)): float(r.value)
        for r in nominal_lcu_weo.itertuples(index=False)
    }

    # Backward-compatible fallback if NGDPD_PCH not present in weo_csv.
    if not nominal_usd_map:
        gdp_levels = weo[(weo["indicator"] == "NGDPD") & (weo["value"].notna())].copy()
        gdp_levels = gdp_levels.sort_values(["country_code", "year"])
        gdp_levels["nominal_growth"] = (
            gdp_levels.groupby("country_code")["value"].pct_change() * 100.0
        )
        nominal_usd_map = {
            (str(r.country_code), int(r.year)): float(r.nominal_growth)
            for r in gdp_levels.itertuples(index=False)
            if pd.notna(r.nominal_growth)
        }

    # Backward-compatible fallback if NGDP_PCH not present in weo_csv.
    if not nominal_lcu_map:
        gdp_levels_lcu = weo[(weo["indicator"] == "NGDP") & (weo["value"].notna())].copy()
        gdp_levels_lcu = gdp_levels_lcu.sort_values(["country_code", "year"])
        gdp_levels_lcu["nominal_growth"] = (
            gdp_levels_lcu.groupby("country_code")["value"].pct_change() * 100.0
        )
        nominal_lcu_map = {
            (str(r.country_code), int(r.year)): float(r.nominal_growth)
            for r in gdp_levels_lcu.itertuples(index=False)
            if pd.notna(r.nominal_growth)
        }

    country_fx_map: dict[tuple[str, int], float] = {}
    ngdp = weo[(weo["indicator"] == "NGDP") & (weo["value"].notna())][
        ["country_code", "year", "value"]
    ].rename(columns={"value": "ngdp_lcu"})
    ngdpd = weo[(weo["indicator"] == "NGDPD") & (weo["value"].notna())][
        ["country_code", "year", "value"]
    ].rename(columns={"value": "ngdp_usd"})
    fx_levels = ngdp.merge(ngdpd, on=["country_code", "year"], how="inner")
    if not fx_levels.empty:
        fx_levels["lcu_per_usd"] = fx_levels["ngdp_lcu"] / fx_levels["ngdp_usd"]
        fx_levels = fx_levels.sort_values(["country_code", "year"]).copy()
        fx_levels["country_lcu_vs_usd_weo_pct"] = (
            fx_levels.groupby("country_code")["lcu_per_usd"].pct_change() * 100.0
        )
        country_fx_map = {
            (str(r.country_code), int(r.year)): float(r.country_lcu_vs_usd_weo_pct)
            for r in fx_levels.itertuples(index=False)
            if pd.notna(r.country_lcu_vs_usd_weo_pct)
        }

    return real_map, nominal_lcu_map, nominal_usd_map, country_fx_map


def gdp_cagr(
    gdp_growth_map: dict[tuple[str, int], float],
    country_code: str,
    end_year: int,
    years: int,
) -> float | None:
    start_year = end_year - years + 1
    finish_year = end_year
    values: list[float] = []
    for y in range(start_year, finish_year + 1):
        v = gdp_growth_map.get((country_code, y))
        if v is None:
            return None
        values.append(v)
    compounded = 1.0
    for v in values:
        compounded *= 1.0 + (v / 100.0)
    return ((compounded ** (1.0 / years)) - 1.0) * 100.0


def load_history_wide(etf_csv: str) -> pd.DataFrame:
    raw = pd.read_csv(etf_csv)
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw.dropna(subset=["Date"]).sort_values("Date")
    cols = ["Date"] + [c for c in raw.columns if c.endswith(" - Close")]
    return raw[cols].copy()


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
    return (
        meta[["ticker", "currency"]]
        .drop_duplicates(subset=["ticker"], keep="first")
        .set_index("ticker")["currency"]
        .to_dict()
    )


def load_ticker_exchange_map(metadata_csv: str | None) -> dict[str, str]:
    if not metadata_csv:
        return {}
    try:
        meta = pd.read_csv(metadata_csv)
    except FileNotFoundError:
        return {}
    required = {"ticker", "exchange"}
    if not required.issubset(set(meta.columns)):
        return {}
    exchange_labels = {
        "LSE": "London Stock Exchange",
        "PCX": "NYSE Arca",
        "NYQ": "NYSE",
        "ASE": "NYSE American",
        "NMS": "Nasdaq Global Select",
        "NGM": "Nasdaq Global Market",
        "NCM": "Nasdaq Capital Market",
        "NAS": "Nasdaq",
    }

    meta = meta.copy()
    meta["ticker"] = meta["ticker"].astype(str)
    meta["exchange"] = meta["exchange"].fillna("").astype(str)
    meta["exchange"] = meta["exchange"].map(lambda x: exchange_labels.get(x, x))
    return (
        meta[["ticker", "exchange"]]
        .drop_duplicates(subset=["ticker"], keep="first")
        .set_index("ticker")["exchange"]
        .to_dict()
    )


def load_ticker_fund_size_map(metadata_csv: str | None) -> dict[str, float]:
    if not metadata_csv:
        return {}
    try:
        meta = pd.read_csv(metadata_csv)
    except FileNotFoundError:
        return {}
    required = {"ticker", "fund_size"}
    if not required.issubset(set(meta.columns)):
        return {}
    meta = meta.copy()
    meta["ticker"] = meta["ticker"].astype(str)
    meta["fund_size"] = pd.to_numeric(meta["fund_size"], errors="coerce")
    out = (
        meta[["ticker", "fund_size"]]
        .drop_duplicates(subset=["ticker"], keep="first")
        .dropna(subset=["fund_size"])
        .set_index("ticker")["fund_size"]
        .to_dict()
    )
    return {k: float(v) for k, v in out.items()}


def fit_columns_from_ranges(
    ws,
    ranges: list[tuple[int, int, int, int]],
    *,
    min_width: float = 10.0,
    max_width: float = 80.0,
    padding: float = 2.0,
) -> None:
    """Auto-size column widths from specific table ranges only."""
    widths: dict[int, int] = {}
    for min_col, max_col, min_row, max_row in ranges:
        for col_idx in range(min_col, max_col + 1):
            max_len = widths.get(col_idx, 0)
            for row_idx in range(min_row, max_row + 1):
                value = ws.cell(row=row_idx, column=col_idx).value
                if value is None:
                    continue
                if isinstance(value, str) and value.startswith("="):
                    continue
                max_len = max(max_len, len(str(value)))
            widths[col_idx] = max_len

    for col_idx, max_len in widths.items():
        width = max(min_width, min(max_width, max_len + padding))
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def build_timeframe_rows(
    etf_csv: str,
    weo_csv: str,
    metadata_csv: str | None = "data/outputs/etf_ticker_metadata.csv",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(etf_csv)
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw.dropna(subset=["Date"]).sort_values("Date")

    ticker_to_country = build_ticker_country_map()
    ticker_to_currency = load_ticker_currency_map(metadata_csv)
    price_columns = choose_price_columns(raw.columns.tolist())
    (
        gdp_real_growth_map,
        gdp_nominal_lcu_growth_map,
        gdp_nominal_usd_growth_map,
        country_lcu_vs_usd_weo_map,
    ) = load_gdp_growth_maps(weo_csv)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    min_year = int(raw["Date"].dt.year.min())
    max_year = int(raw["Date"].dt.year.max())
    currencies = {
        normalize_currency_code(ticker_to_currency.get(ticker, ""))
        for ticker in price_columns
        if ticker_to_currency.get(ticker, "")
    }
    quote_fx_map = compute_annual_fx_quote_to_usd_returns(currencies, min_year, max_year)

    timeframe_rows: list[dict[str, object]] = []
    annual_rows: list[dict[str, object]] = []
    cagr_rows: list[dict[str, object]] = []

    for ticker, price_col in price_columns.items():
        country_name = ticker_to_country.get(ticker)
        if not country_name:
            continue
        country_code = COUNTRY_TO_ISO3.get(country_name)
        if not country_code:
            continue

        series = raw.set_index("Date")[price_col].dropna()
        if series.empty:
            continue
        
        # Identify the first date with a non-zero price (inception)
        valid_series = series[series > 0]
        if valid_series.empty:
            continue
        inception_date = valid_series.index.min()
        inception_year = int(inception_date.year)

        end_pt = PricePoint(series.index[-1], float(series.iloc[-1]))
        end_date = end_pt.date
        completed_year = pd.Timestamp.today().year - 1
        etf_year_max = int(series.index.year.max())
        gdp_years = sorted(
            {
                year
                for (cc, year), _ in gdp_real_growth_map.items()
                if cc == country_code
            }
        )
        gdp_year_max = max(gdp_years) if gdp_years else completed_year
        cagr_end_year = min(completed_year, etf_year_max, gdp_year_max)

        # Relative + MAX windows
        for label, spec in TIMEFRAME_SPECS:
            if spec == "max":
                start_pt = max_start_point(series)
            elif spec == "ytd":
                jan1 = pd.Timestamp(year=end_date.year, month=1, day=1)
                start_pt = last_on_or_before(series, jan1)
            else:
                target = end_date - spec
                start_pt = last_on_or_before(series, target)

            if start_pt is None:
                continue

            etf_return = pct_return(start_pt.value, end_pt.value)
            timeframe_rows.append(
                {
                    "country_name": country_name,
                    "country_code": country_code,
                    "ticker": ticker,
                    "timeframe": label,
                    "start_date": start_pt.date.date(),
                    "end_date": end_pt.date.date(),
                    "etf_return_pct": etf_return,
                    "etf_currency": ticker_to_currency.get(ticker, ""),
                }
            )

        # Annual source rows include all available GDP years; dashboard view filters
        # to last completed years and can append a separate projection/YTD row.
        if gdp_years:
            for y in gdp_years:
                start_pt = None
                end_year_pt = None
                etf_return = None
                etf_return_usd = None
                
                if y >= inception_year:
                    start_pt = first_in_year(series, y)
                    end_year_pt = last_in_year(series, y)
                    if start_pt is not None and end_year_pt is not None and start_pt.value > 0:
                        etf_return = pct_return(start_pt.value, end_year_pt.value)
                
                gdp_real_same = gdp_real_growth_map.get((country_code, y))
                gdp_nominal_lcu_same = gdp_nominal_lcu_growth_map.get((country_code, y))
                gdp_nominal_usd_same = gdp_nominal_usd_growth_map.get((country_code, y))
                quote_ccy_vs_usd = quote_fx_map.get(
                    (normalize_currency_code(ticker_to_currency.get(ticker, "")), y)
                )
                etf_return_usd = None
                if etf_return is not None:
                    ccy_norm = normalize_currency_code(ticker_to_currency.get(ticker, ""))
                    if ccy_norm == "USD":
                        etf_return_usd = etf_return
                    elif quote_ccy_vs_usd is not None:
                        etf_return_usd = (
                            ((1.0 + (etf_return / 100.0)) * (1.0 + (quote_ccy_vs_usd / 100.0)))
                            - 1.0
                        ) * 100.0

                country_lcu_vs_usd_weo = country_lcu_vs_usd_weo_map.get((country_code, y))
                etf_usd_minus_country_fx = None
                if (
                    etf_return_usd is not None
                    and country_lcu_vs_usd_weo is not None
                    and (1.0 + (country_lcu_vs_usd_weo / 100.0)) != 0.0
                ):
                    etf_usd_minus_country_fx = (
                        ((1.0 + (etf_return_usd / 100.0))
                         / (1.0 + (country_lcu_vs_usd_weo / 100.0)))
                        - 1.0
                    ) * 100.0
                annual_rows.append(
                    {
                        "country_name": country_name,
                        "country_code": country_code,
                        "ticker": ticker,
                        "year": y,
                        "etf_return_pct": etf_return,
                        "etf_return_quote_pct": etf_return,
                        "quote_ccy_vs_usd_pct": quote_ccy_vs_usd,
                        "etf_return_usd_pct": etf_return_usd,
                        "country_lcu_vs_usd_weo_pct": country_lcu_vs_usd_weo,
                        "etf_usd_minus_country_fx_pct": etf_usd_minus_country_fx,
                        "gdp_real_growth_pct": gdp_real_same,
                        "gdp_nominal_lcu_growth_pct": gdp_nominal_lcu_same,
                        "gdp_nominal_usd_growth_pct": gdp_nominal_usd_same,
                        "gdp_nominal_usd_minus_etf_growth_pct": (
                            gdp_nominal_usd_same - etf_return_usd
                            if (etf_return_usd is not None and gdp_nominal_usd_same is not None)
                            else None
                        ),
                        "etf_currency": ticker_to_currency.get(ticker, ""),
                    }
                )

        # CAGR rows (1Y, 3Y, 5Y, 10Y)
        for years in CAGR_HORIZONS:
            start_year = cagr_end_year - years + 1
            if start_year < inception_year:
                continue
            
            start_pt = first_in_year(series, start_year)
            end_year_pt = last_in_year(series, cagr_end_year)
            if start_pt is None or end_year_pt is None or start_pt.value <= 0:
                continue
            
            total_ret_local = pct_return(start_pt.value, end_year_pt.value)
            
            # Calculate total return in USD for CAGR
            ccy_norm = normalize_currency_code(ticker_to_currency.get(ticker, ""))
            if ccy_norm == "USD":
                total_ret_usd = total_ret_local
            else:
                # We need the FX change over the exact same period.
                # Since we have annual FX returns, we can compound them, but it's more accurate to fetch the actual price.
                # However, for simplicity and consistency with the annual table, 
                # we'll use the cumulative FX return from the quote_fx_map years.
                fx_compounded = 1.0
                valid_fx = True
                for y in range(start_year, cagr_end_year + 1):
                    ann_fx = quote_fx_map.get((ccy_norm, y))
                    if ann_fx is None:
                        valid_fx = False
                        break
                    fx_compounded *= (1.0 + (ann_fx / 100.0))
                
                if valid_fx:
                    total_ret_usd = ((1.0 + (total_ret_local / 100.0)) * fx_compounded - 1.0) * 100.0
                else:
                    total_ret_usd = None
            
            if total_ret_usd is not None:
                etf_cagr = cagr_from_total_return(total_ret_usd, years)
            else:
                etf_cagr = None

            gdp_real_cagr = gdp_cagr(
                gdp_real_growth_map, country_code, cagr_end_year, years
            )
            gdp_nominal_lcu_cagr = gdp_cagr(
                gdp_nominal_lcu_growth_map, country_code, cagr_end_year, years
            )
            gdp_nominal_usd_cagr = gdp_cagr(
                gdp_nominal_usd_growth_map, country_code, cagr_end_year, years
            )
            cagr_rows.append(
                {
                    "country_name": country_name,
                    "country_code": country_code,
                    "ticker": ticker,
                    "as_of_date": end_year_pt.date.date(),
                    "horizon": f"{years}Y",
                    "etf_cagr_pct": etf_cagr,
                    "gdp_real_cagr_pct": gdp_real_cagr,
                    "gdp_nominal_lcu_cagr_pct": gdp_nominal_lcu_cagr,
                    "gdp_nominal_usd_cagr_pct": gdp_nominal_usd_cagr,
                    "gdp_nominal_usd_minus_etf_cagr_pct": (
                        gdp_nominal_usd_cagr - etf_cagr
                        if (gdp_nominal_usd_cagr is not None and etf_cagr is not None)
                        else None
                    ),
                    "etf_currency": ticker_to_currency.get(ticker, ""),
                }
            )

    timeframe_df = pd.DataFrame(timeframe_rows)
    if not timeframe_df.empty:
        timeframe_df["timeframe"] = pd.Categorical(
            timeframe_df["timeframe"], categories=TIMEFRAME_ORDER, ordered=True
        )
        timeframe_df = timeframe_df.sort_values(
            ["country_name", "ticker", "timeframe"]
        ).reset_index(drop=True)
        timeframe_df["timeframe"] = timeframe_df["timeframe"].astype(str)
        timeframe_df["lookup_key"] = (
            timeframe_df["country_name"] + "|" + timeframe_df["ticker"] + "|" + timeframe_df["timeframe"]
        )
        timeframe_df = timeframe_df[
            [
                "country_name",
                "country_code",
                "ticker",
                "timeframe",
                "start_date",
                "end_date",
                "etf_return_pct",
                "lookup_key",
                "etf_currency",
            ]
        ]

    annual_df = pd.DataFrame(annual_rows)
    if not annual_df.empty:
        annual_df = annual_df.sort_values(
            ["country_name", "ticker", "year"]
        ).reset_index(drop=True)
        annual_df["lookup_key"] = (
            annual_df["country_name"] + "|" + annual_df["ticker"] + "|" + annual_df["year"].astype(str)
        )
        annual_df["country_year_key"] = (
            annual_df["country_name"] + "|" + annual_df["year"].astype(str)
        )
        annual_df = annual_df[
            [
                "country_name",
                "country_code",
                "ticker",
                "year",
                "etf_return_pct",
                "gdp_real_growth_pct",
                "gdp_nominal_lcu_growth_pct",
                "gdp_nominal_usd_growth_pct",
                "gdp_nominal_usd_minus_etf_growth_pct",
                "lookup_key",
                "country_year_key",
                "etf_currency",
                "etf_return_quote_pct",
                "quote_ccy_vs_usd_pct",
                "etf_return_usd_pct",
                "country_lcu_vs_usd_weo_pct",
                "etf_usd_minus_country_fx_pct",
            ]
        ]

    cagr_df = pd.DataFrame(cagr_rows)
    # Ensure GDP CAGR exists per country+horizon even when ETF CAGR is unavailable.
    gdp_only_rows: list[dict[str, object]] = []
    completed_year = pd.Timestamp.today().year - 1
    countries_in_scope = sorted(timeframe_df["country_name"].dropna().unique().tolist()) if not timeframe_df.empty else []
    for country_name in countries_in_scope:
        country_code = COUNTRY_TO_ISO3.get(country_name)
        if not country_code:
            continue
        gdp_years = sorted(
            {
                year
                for (cc, year), _ in gdp_real_growth_map.items()
                if cc == country_code
            }
        )
        if not gdp_years:
            continue
        cagr_end_year = min(completed_year, max(gdp_years))
        for years in CAGR_HORIZONS:
            gdp_real_cagr = gdp_cagr(
                gdp_real_growth_map, country_code, cagr_end_year, years
            )
            gdp_nominal_lcu_cagr = gdp_cagr(
                gdp_nominal_lcu_growth_map, country_code, cagr_end_year, years
            )
            gdp_nominal_usd_cagr = gdp_cagr(
                gdp_nominal_usd_growth_map, country_code, cagr_end_year, years
            )
            if (
                gdp_real_cagr is None
                and gdp_nominal_lcu_cagr is None
                and gdp_nominal_usd_cagr is None
            ):
                continue
            gdp_only_rows.append(
                {
                    "country_name": country_name,
                    "country_code": country_code,
                    "ticker": "",
                    "as_of_date": pd.Timestamp(year=cagr_end_year, month=12, day=31).date(),
                    "horizon": f"{years}Y",
                    "etf_cagr_pct": None,
                    "gdp_real_cagr_pct": gdp_real_cagr,
                    "gdp_nominal_lcu_cagr_pct": gdp_nominal_lcu_cagr,
                    "gdp_nominal_usd_cagr_pct": gdp_nominal_usd_cagr,
                    "gdp_nominal_usd_minus_etf_cagr_pct": None,
                    "etf_currency": "",
                }
            )
    if gdp_only_rows:
        cagr_df = pd.concat([cagr_df, pd.DataFrame(gdp_only_rows)], ignore_index=True)

    if not cagr_df.empty:
        horizon_order = pd.Categorical(
            cagr_df["horizon"],
            categories=[f"{y}Y" for y in CAGR_HORIZONS],
            ordered=True,
        )
        cagr_df = (
            cagr_df.assign(_h=horizon_order)
            .sort_values(["country_name", "ticker", "_h"])
            .drop(columns=["_h"])
            .reset_index(drop=True)
        )
        cagr_df["lookup_key"] = (
            cagr_df["country_name"] + "|" + cagr_df["ticker"] + "|" + cagr_df["horizon"]
        )
        cagr_df["country_horizon_key"] = (
            cagr_df["country_name"] + "|" + cagr_df["horizon"]
        )
        cagr_df = cagr_df[
            [
                "country_name",
                "country_code",
                "ticker",
                "as_of_date",
                "horizon",
                "etf_cagr_pct",
                "gdp_real_cagr_pct",
                "gdp_nominal_lcu_cagr_pct",
                "gdp_nominal_usd_cagr_pct",
                "gdp_nominal_usd_minus_etf_cagr_pct",
                "lookup_key",
                "country_horizon_key",
                "etf_currency",
            ]
        ]

    return timeframe_df, annual_df, cagr_df


def write_dashboard_xlsx(
    timeframe_df: pd.DataFrame,
    annual_df: pd.DataFrame,
    cagr_df: pd.DataFrame,
    output_xlsx: str,
    metadata_csv: str | None = "data/outputs/etf_ticker_metadata.csv",
) -> None:
    from openpyxl.styles import Font
    from openpyxl.styles import PatternFill
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.worksheet.datavalidation import DataValidation

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        ticker_fund_size_map = load_ticker_fund_size_map(metadata_csv)
        ticker_exchange_map = load_ticker_exchange_map(metadata_csv)
        default_map = (
            timeframe_df[["country_name", "ticker", "etf_currency"]]
            .drop_duplicates(subset=["country_name", "ticker"], keep="first")
            .assign(
                usd_rank=lambda d: (d["etf_currency"] == "USD").astype(int),
                fund_size_rank=lambda d: d["ticker"].map(ticker_fund_size_map).fillna(-1.0),
            )
            .sort_values(
                ["country_name", "usd_rank", "fund_size_rank", "ticker"],
                ascending=[True, False, False, True],
            )
            .groupby("country_name", as_index=False)
            .first()[["country_name", "ticker"]]
        )
        ticker_currency_map = (
            timeframe_df[["ticker", "etf_currency"]]
            .drop_duplicates(subset=["ticker"], keep="first")
            .set_index("ticker")["etf_currency"]
            .to_dict()
        )
        country_summary_df = default_map.rename(columns={"ticker": "ticker_used"}).copy()
        country_summary_df["ticker_exchange"] = country_summary_df["ticker_used"].map(
            ticker_exchange_map
        ).fillna("")
        country_summary_df["ticker_currency"] = country_summary_df["ticker_used"].map(
            ticker_currency_map
        ).fillna("")
        country_summary_df["region"] = country_summary_df["country_name"].map(
            COUNTRY_TO_REGION
        ).fillna("Other")
        country_summary_df = country_summary_df[
            ["country_name", "region", "ticker_used", "ticker_exchange", "ticker_currency"]
        ].sort_values(["region", "country_name"], ascending=[True, True]).reset_index(drop=True)
        country_ticker_options_df = (
            timeframe_df[["country_name", "ticker"]]
            .drop_duplicates(subset=["country_name", "ticker"], keep="first")
            .sort_values(["country_name", "ticker"], ascending=[True, True])
            .reset_index(drop=True)
        )
        ticker_attrs_df = (
            timeframe_df[["ticker"]]
            .drop_duplicates(subset=["ticker"], keep="first")
            .assign(
                ticker_exchange=lambda d: d["ticker"].map(ticker_exchange_map).fillna(""),
                ticker_currency=lambda d: d["ticker"].map(ticker_currency_map).fillna(""),
            )
            .sort_values(["ticker"], ascending=[True])
            .reset_index(drop=True)
        )

        timeframe_df.to_excel(writer, sheet_name="ETF_Timeframes", index=False)
        annual_df.to_excel(writer, sheet_name="Annual", index=False)
        cagr_df.to_excel(writer, sheet_name="CAGR", index=False)
        lists_df = pd.DataFrame(
            {
                "country_name": pd.Series(
                    sorted(timeframe_df["country_name"].dropna().unique().tolist())
                ),
                "ticker": pd.Series(
                    sorted(timeframe_df["ticker"].dropna().unique().tolist())
                ),
                "country_for_default": pd.Series(default_map["country_name"].tolist()),
                "default_ticker": pd.Series(default_map["ticker"].tolist()),
            }
        )
        lists_df.to_excel(writer, sheet_name="Lists", index=False)
        country_ticker_options_df.to_excel(
            writer,
            sheet_name="Lists",
            index=False,
            startcol=5,
        )
        ticker_attrs_df.to_excel(
            writer,
            sheet_name="Lists",
            index=False,
            startcol=8,
        )
        country_summary_df.to_excel(writer, sheet_name="Country_CAGR_Summary", index=False, startrow=4)

        wb = writer.book
        ws_tf = wb["ETF_Timeframes"]
        ws_annual = wb["Annual"]
        ws_cagr = wb["CAGR"]
        ws_lists = wb["Lists"]
        ws_country = wb["Country_CAGR_Summary"]

        ws_tf.auto_filter.ref = ws_tf.dimensions
        ws_tf.freeze_panes = "A2"
        ws_annual.auto_filter.ref = ws_annual.dimensions
        ws_annual.freeze_panes = "A2"
        ws_cagr.auto_filter.ref = ws_cagr.dimensions
        ws_cagr.freeze_panes = "A2"
        ws_country.freeze_panes = "A6"

        ws_country["A1"] = "Country CAGR Disconnect Screener"
        ws_country["A1"].font = Font(bold=True, size=14)
        ws_country["A2"] = "Horizon"
        ws_country["B2"] = "5Y"
        ws_country["D2"] = "Choose horizon, then sort by Nominal USD GDP - ETF CAGR."
        ws_country["A3"] = "Metrics are CAGR (annualized), not cumulative return."
        ws_country["A5"] = "country_name"
        ws_country["B5"] = "region"
        ws_country["C5"] = "ticker_used"
        ws_country["D5"] = "ticker_exchange"
        ws_country["E5"] = "ticker_currency"
        ws_country["F5"] = "ETF CAGR %"
        ws_country["G5"] = "GDP Real CAGR %"
        ws_country["H5"] = "GDP Nominal CAGR % (LCU)"
        ws_country["I5"] = "GDP Nominal CAGR % (USD)"
        ws_country["J5"] = "GDP Nominal USD - ETF CAGR %"
        for c in ["A2", "A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5", "I5", "J5"]:
            ws_country[c].font = Font(bold=True)

        horizon_dv = DataValidation(type="list", formula1='"1Y,3Y,5Y,10Y"', allow_blank=False)
        ws_country.add_data_validation(horizon_dv)
        horizon_dv.add("B2")

        country_start_row = 6
        country_end_row = 5 + len(country_summary_df)
        country_ticker_end_row = 1 + len(country_ticker_options_df)
        ticker_attrs_end_row = 1 + len(ticker_attrs_df)
        for r in range(country_start_row, country_end_row + 1):
            ticker_formula_row = (
                '=OFFSET(Lists!$G$2,'
                f'IFERROR(MATCH($A{r},Lists!$F$2:$F${country_ticker_end_row},0)-1,0),'
                "0,"
                f'COUNTIF(Lists!$F$2:$F${country_ticker_end_row},$A{r}),'
                "1)"
            )
            ticker_dv_row = DataValidation(type="list", formula1=ticker_formula_row, allow_blank=False)
            ws_country.add_data_validation(ticker_dv_row)
            ticker_dv_row.add(f"C{r}")
            ws_country[f"D{r}"] = (
                f'=IFERROR(INDEX(Lists!$J$2:$J${ticker_attrs_end_row}, MATCH($C{r}, Lists!$I$2:$I${ticker_attrs_end_row}, 0)),"")'
            )
            ws_country[f"E{r}"] = (
                f'=IFERROR(INDEX(Lists!$K$2:$K${ticker_attrs_end_row}, MATCH($C{r}, Lists!$I$2:$I${ticker_attrs_end_row}, 0)),"")'
            )
            ws_country[f"F{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$F:$F, MATCH($A{r}&"|"&$C{r}&"|"&$B$2, CAGR!$K:$K, 0)), NA())'
            )
            ws_country[f"G{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$G:$G, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"H{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$H:$H, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"I{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$I:$I, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"J{r}"] = f"=IF(AND(ISNUMBER(F{r}),ISNUMBER(I{r})),I{r}-F{r},NA())"
            for col in ["F", "G", "H", "I", "J"]:
                ws_country[f"{col}{r}"].number_format = "0.00"
        ws_country.auto_filter.ref = f"A5:J{country_end_row}"

        # Country focus dashboard below screener.
        focus_top_row = country_end_row + 3
        ws_country[f"A{focus_top_row}"] = "Country Focus Dashboard"
        ws_country[f"A{focus_top_row}"].font = Font(bold=True, size=14)
        ws_country[f"A{focus_top_row + 1}"] = "Country"
        ws_country[f"A{focus_top_row + 2}"] = "Ticker"
        ws_country[f"A{focus_top_row + 3}"] = "As-of Date"
        ws_country[f"A{focus_top_row + 4}"] = "Ticker Currency"
        ws_country[f"A{focus_top_row + 5}"] = "Ticker Exchange"
        ws_country[f"E{focus_top_row + 1}"] = (
            "Same-year GDP comparison: last 10 completed years + one projection/YTD row."
        )

        country_count = ws_lists.max_row - 1
        country_dv_focus = DataValidation(
            type="list",
            formula1=f"=Lists!$A$2:$A${country_count + 1}",
            allow_blank=False,
        )
        ws_country.add_data_validation(country_dv_focus)
        country_dv_focus.add(f"B{focus_top_row + 1}")
        ws_country[f"B{focus_top_row + 1}"] = timeframe_df["country_name"].iloc[0]
        ticker_formula_focus = (
            '=OFFSET(Lists!$G$2,'
            f'IFERROR(MATCH($B${focus_top_row + 1},Lists!$F$2:$F${country_ticker_end_row},0)-1,0),'
            "0,"
            f'COUNTIF(Lists!$F$2:$F${country_ticker_end_row},$B${focus_top_row + 1}),'
            "1)"
        )
        ticker_dv_focus = DataValidation(type="list", formula1=ticker_formula_focus, allow_blank=False)
        ws_country.add_data_validation(ticker_dv_focus)
        ticker_dv_focus.add(f"B{focus_top_row + 2}")
        ws_country[f"B{focus_top_row + 2}"] = (
            f'=IFERROR(INDEX(Lists!$D:$D, MATCH($B${focus_top_row + 1}, Lists!$C:$C, 0)),"")'
        )
        ws_country[f"B{focus_top_row + 3}"] = (
            f'=IFERROR(INDEX(ETF_Timeframes!$F:$F, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|MAX", ETF_Timeframes!$H:$H, 0)),"")'
        )
        ws_country[f"B{focus_top_row + 4}"] = (
            f'=IFERROR(INDEX(Lists!$K$2:$K${ticker_attrs_end_row}, MATCH($B${focus_top_row + 2}, Lists!$I$2:$I${ticker_attrs_end_row}, 0)),"")'
        )
        ws_country[f"B{focus_top_row + 5}"] = (
            f'=IFERROR(INDEX(Lists!$J$2:$J${ticker_attrs_end_row}, MATCH($B${focus_top_row + 2}, Lists!$I$2:$I${ticker_attrs_end_row}, 0)),"")'
        )
        ws_country[f"B{focus_top_row + 3}"].number_format = "yyyy-mm-dd"
        focus_currency_ref = f"$B${focus_top_row + 4}"

        timeframe_title_row = focus_top_row + 7
        timeframe_header_row = focus_top_row + 8
        timeframe_start_row = focus_top_row + 9
        ws_country[f"A{timeframe_title_row}"] = "ETF Cumulative returns"
        ws_country[f"A{timeframe_title_row}"].font = Font(bold=True)
        ws_country[f"A{timeframe_header_row}"] = "Timeframe"
        ws_country[f"B{timeframe_header_row}"] = "ETF Return %"
        ws_country[f"C{timeframe_header_row}"] = "Start Date"
        for c in [f"A{timeframe_header_row}", f"B{timeframe_header_row}", f"C{timeframe_header_row}"]:
            ws_country[c].font = Font(bold=True)

        for i, tf in enumerate(TIMEFRAME_ORDER):
            r = timeframe_start_row + i
            ws_country[f"A{r}"] = tf
            ws_country[f"B{r}"] = (
                f'=IFERROR(INDEX(ETF_Timeframes!$G:$G, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, ETF_Timeframes!$H:$H, 0)), "")'
            )
            ws_country[f"C{r}"] = (
                f'=IFERROR(INDEX(ETF_Timeframes!$E:$E, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, ETF_Timeframes!$H:$H, 0)),"")'
            )

        annual_title_row = timeframe_start_row + len(TIMEFRAME_ORDER) + 3
        annual_header_row = annual_title_row + 1
        annual_start_row = annual_header_row + 1
        ws_country[f"A{annual_title_row}"] = "Annual ETF vs GDP + FX Decomposition (Last 10 Years, %)"
        ws_country[f"A{annual_title_row}"].font = Font(bold=True)
        ws_country[f"A{annual_header_row}"] = "Year"
        ws_country[f"B{annual_header_row}"] = "ETF Return (Local) %"
        ws_country[f"C{annual_header_row}"] = "Real GDP Growth %"
        ws_country[f"D{annual_header_row}"] = "Nominal GDP Growth % (LCU)"
        ws_country[f"E{annual_header_row}"] = "Nominal GDP Growth % (USD)"
        ws_country[f"F{annual_header_row}"] = "Disconnect (Real GDP) %"
        ws_country[f"G{annual_header_row}"] = "Disconnect (Nom USD GDP) %"
        ws_country[f"H{annual_header_row}"] = f'=IF({focus_currency_ref}<>"USD","FX Change (vs USD) %","")'
        ws_country[f"I{annual_header_row}"] = f'=IF({focus_currency_ref}<>"USD","ETF Return (USD) %","")'
        ws_country[f"J{annual_header_row}"] = f'=IF({focus_currency_ref}<>"USD","Country LCU vs USD % (WEO)","")'
        ws_country[f"K{annual_header_row}"] = f'=IF({focus_currency_ref}<>"USD","ETF USD - Country FX %","")'
        for c in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]:
            ws_country[f"{c}{annual_header_row}"].font = Font(bold=True)

        completed_year = pd.Timestamp.today().year - 1
        annual_years = sorted(
            [y for y in annual_df["year"].dropna().unique().tolist() if int(y) <= completed_year]
        )[-ANNUAL_WINDOW_YEARS:]
        for i, year in enumerate(annual_years):
            r = annual_start_row + i
            ws_country[f"A{r}"] = int(year)
            ws_country[f"B{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$E:$E, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, Annual!$J:$J, 0)), NA())'
            )
            ws_country[f"C{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$F:$F, MATCH($B${focus_top_row + 1}&"|"&$A{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"D{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$G:$G, MATCH($B${focus_top_row + 1}&"|"&$A{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"E{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$H:$H, MATCH($B${focus_top_row + 1}&"|"&$A{r}, Annual!$K:$K, 0)), NA())'
            )
            
            # Fetch USD Return from Annual!$O (Column O = 15th column) for disconnect calc
            usd_ret_idx = f'INDEX(Annual!$O:$O, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, Annual!$J:$J, 0))'
            # Check if index returned a non-empty cell. ISNUMBER(1*...) works but 1*empty is 0. 
            # We use IF(AND(ISNUMBER(C{r}), ISNUMBER({usd_ret_idx}), {usd_ret_idx}<>""), ...)
            ws_country[f"F{r}"] = f"=IF(AND(ISNUMBER(C{r}),ISNUMBER({usd_ret_idx}),{usd_ret_idx}<>\"\"),C{r}-{usd_ret_idx},NA())"
            ws_country[f"G{r}"] = f"=IF(AND(ISNUMBER(E{r}),ISNUMBER({usd_ret_idx}),{usd_ret_idx}<>\"\"),E{r}-{usd_ret_idx},NA())"
            
            ws_country[f"H{r}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$N:$N, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, Annual!$J:$J, 0)), NA()),"")'
            )
            ws_country[f"I{r}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$O:$O, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, Annual!$J:$J, 0)), NA()),"")'
            )
            ws_country[f"J{r}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$P:$P, MATCH($B${focus_top_row + 1}&"|"&$A{r}, Annual!$K:$K, 0)), NA()),"")'
            )
            ws_country[f"K{r}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$Q:$Q, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, Annual!$J:$J, 0)), NA()),"")'
            )

        projection_years = sorted(
            [y for y in annual_df["year"].dropna().unique().tolist() if int(y) > completed_year]
        )
        annual_last_row = annual_header_row + len(annual_years)
        if projection_years:
            projection_year = int(projection_years[0])
            projection_row = annual_start_row + len(annual_years)
            ws_country[f"A{projection_row}"] = f"{projection_year} (Proj GDP / ETF YTD)"
            ws_country[f"B{projection_row}"] = (
                f'=IFERROR(1*INDEX(ETF_Timeframes!$G:$G, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|YTD", ETF_Timeframes!$H:$H, 0)), NA())'
            )
            ws_country[f"C{projection_row}"] = (
                f'=IFERROR(1*INDEX(Annual!$F:$F, MATCH($B${focus_top_row + 1}&"|"&{projection_year}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"D{projection_row}"] = (
                f'=IFERROR(1*INDEX(Annual!$G:$G, MATCH($B${focus_top_row + 1}&"|"&{projection_year}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"E{projection_row}"] = (
                f'=IFERROR(1*INDEX(Annual!$H:$H, MATCH($B${focus_top_row + 1}&"|"&{projection_year}, Annual!$K:$K, 0)), NA())'
            )
            # ETF_Timeframes!$G is USD return (or local if USD)
            proj_usd_ret_idx = f'INDEX(ETF_Timeframes!$G:$G, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|YTD", ETF_Timeframes!$H:$H, 0))'
            ws_country[f"F{projection_row}"] = (
                f"=IF(AND(ISNUMBER(C{projection_row}),ISNUMBER({proj_usd_ret_idx}),{proj_usd_ret_idx}<>\"\"),C{projection_row}-{proj_usd_ret_idx},NA())"
            )
            ws_country[f"G{projection_row}"] = (
                f"=IF(AND(ISNUMBER(E{projection_row}),ISNUMBER({proj_usd_ret_idx}),{proj_usd_ret_idx}<>\"\"),E{projection_row}-{proj_usd_ret_idx},NA())"
            )
            ws_country[f"H{projection_row}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$N:$N, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&{projection_year}, Annual!$J:$J, 0)), NA()),"")'
            )
            ws_country[f"I{projection_row}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$O:$O, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&{projection_year}, Annual!$J:$J, 0)), NA()),"")'
            )
            ws_country[f"J{projection_row}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$P:$P, MATCH($B${focus_top_row + 1}&"|"&{projection_year}, Annual!$K:$K, 0)), NA()),"")'
            )
            ws_country[f"K{projection_row}"] = (
                f'=IF({focus_currency_ref}<>"USD",IFERROR(1*INDEX(Annual!$Q:$Q, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&{projection_year}, Annual!$J:$J, 0)), NA()),"")'
            )
            annual_last_row = projection_row
            ws_country[f"A{annual_last_row + 1}"] = (
                f"* {projection_year} row: GDP is IMF projection; ETF is YTD return (USD)."
            )

        cagr_title_row = annual_last_row + 3
        cagr_header_row = cagr_title_row + 1
        cagr_start_row = cagr_header_row + 1
        cagr_end_row = cagr_start_row + 2
        ws_country[f"A{cagr_title_row}"] = "CAGR Comparison (%)"
        ws_country[f"A{cagr_title_row}"].font = Font(bold=True)
        ws_country[f"A{cagr_header_row}"] = "Horizon"
        ws_country[f"B{cagr_header_row}"] = "ETF CAGR %"
        ws_country[f"C{cagr_header_row}"] = "Real GDP CAGR %"
        ws_country[f"D{cagr_header_row}"] = "Nominal GDP CAGR % (LCU)"
        ws_country[f"E{cagr_header_row}"] = "Nominal GDP CAGR % (USD)"
        ws_country[f"F{cagr_header_row}"] = "Real GDP - ETF CAGR %"
        ws_country[f"G{cagr_header_row}"] = "Nom USD GDP - ETF CAGR %"
        for c in [f"A{cagr_header_row}", f"B{cagr_header_row}", f"C{cagr_header_row}", f"D{cagr_header_row}", f"E{cagr_header_row}", f"F{cagr_header_row}", f"G{cagr_header_row}"]:
            ws_country[c].font = Font(bold=True)

        for i, hz in enumerate(["3Y", "5Y", "10Y"]):
            r = cagr_start_row + i
            ws_country[f"A{r}"] = hz
            ws_country[f"B{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$F:$F, MATCH($B${focus_top_row + 1}&"|"&$B${focus_top_row + 2}&"|"&$A{r}, CAGR!$K:$K, 0)), NA())'
            )
            ws_country[f"C{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$G:$G, MATCH($B${focus_top_row + 1}&"|"&$A{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"D{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$H:$H, MATCH($B${focus_top_row + 1}&"|"&$A{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"E{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$I:$I, MATCH($B${focus_top_row + 1}&"|"&$A{r}, CAGR!$L:$L, 0)), NA())'
            )
            # CAGR Real Disconnect
            ws_country[f"F{r}"] = f"=IF(AND(ISNUMBER(C{r}),ISNUMBER(B{r})),C{r}-B{r},NA())"
            # CAGR Nom USD Disconnect
            ws_country[f"G{r}"] = f"=IF(AND(ISNUMBER(E{r}),ISNUMBER(B{r})),E{r}-B{r},NA())"

        for row in range(timeframe_start_row, timeframe_start_row + len(TIMEFRAME_ORDER)):
            ws_country[f"B{row}"].number_format = "0.00"
            ws_country[f"C{row}"].number_format = "yyyy-mm-dd"
        for row in range(annual_start_row, annual_last_row + 1):
            for col in ["B", "C", "D", "E", "F", "G", "H", "I", "J"]:
                ws_country[f"{col}{row}"].number_format = "0.00"
        for row in range(cagr_start_row, cagr_end_row + 1):
            for col in ["B", "C", "D", "E", "F"]:
                ws_country[f"{col}{row}"].number_format = "0.00"

        pos_fill = PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid")
        neg_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        for rng in [
            f"B{timeframe_start_row}:B{timeframe_start_row + len(TIMEFRAME_ORDER) - 1}",
            f"B{annual_start_row}:K{annual_last_row}",
            f"B{cagr_start_row}:G{cagr_end_row}",
        ]:
            ws_country.conditional_formatting.add(
                rng, CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=pos_fill)
            )
            ws_country.conditional_formatting.add(
                rng, CellIsRule(operator="lessThan", formula=["0"], fill=neg_fill)
            )
        ws_country.conditional_formatting.add(
            f"F{country_start_row}:J{country_end_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=pos_fill),
        )
        ws_country.conditional_formatting.add(
            f"F{country_start_row}:J{country_end_row}",
            CellIsRule(operator="lessThan", formula=["0"], fill=neg_fill),
        )

        fit_columns_from_ranges(ws_tf, [(1, ws_tf.max_column, 1, ws_tf.max_row)])
        fit_columns_from_ranges(ws_annual, [(1, ws_annual.max_column, 1, ws_annual.max_row)])
        fit_columns_from_ranges(ws_cagr, [(1, ws_cagr.max_column, 1, ws_cagr.max_row)])
        fit_columns_from_ranges(ws_lists, [(1, ws_lists.max_column, 1, ws_lists.max_row)])
        fit_columns_from_ranges(
            ws_country,
            [
                (1, 10, 5, country_end_row),
                (1, 2, focus_top_row + 1, focus_top_row + 5),
                (1, 3, timeframe_header_row, timeframe_start_row + len(TIMEFRAME_ORDER) - 1),
                (1, 11, annual_header_row, annual_last_row),
                (1, 7, cagr_header_row, cagr_end_row),
            ],
        )

        ws_lists.sheet_state = "hidden"
        wb.active = wb.sheetnames.index("Country_CAGR_Summary")
        wb.calculation.calcMode = "auto"
        wb.calculation.fullCalcOnLoad = True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Excel MVP dashboard for country-level ETF returns vs GDP growth "
            "(same-year comparisons)."
        )
    )
    parser.add_argument("--etf-csv", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument(
        "--metadata-csv",
        default="data/outputs/etf_ticker_metadata.csv",
        help="Optional ticker metadata CSV containing currency by ticker.",
    )
    parser.add_argument("--output", default="data/outputs/etf_gdp_dashboard_mvp.xlsx")
    args = parser.parse_args()

    timeframe_df, annual_df, cagr_df = build_timeframe_rows(
        args.etf_csv, args.weo_csv, args.metadata_csv
    )
    if timeframe_df.empty:
        raise RuntimeError("No timeframe rows produced. Check ETF and WEO input data.")
    if annual_df.empty:
        raise RuntimeError("No annual rows produced. Check ETF and WEO input data.")
    if cagr_df.empty:
        raise RuntimeError("No CAGR rows produced. Check ETF and WEO input data.")
    write_dashboard_xlsx(
        timeframe_df, annual_df, cagr_df, args.output, metadata_csv=args.metadata_csv
    )
    print(f"Wrote dashboard MVP to {args.output}")
    print(
        f"Timeframe rows: {len(timeframe_df)}, "
        f"Annual rows: {len(annual_df)}, "
        f"CAGR rows: {len(cagr_df)}, "
        f"Countries: {annual_df['country_code'].nunique()}, "
        f"Tickers: {annual_df['ticker'].nunique()}"
    )


if __name__ == "__main__":
    main()
