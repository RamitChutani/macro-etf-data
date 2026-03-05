#!/usr/bin/env python3
"""Build an Excel MVP dashboard for ETF vs GDP growth comparison."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

import pandas as pd
from openpyxl.utils import get_column_letter

from build_combined_etf_weo import COUNTRY_TO_ISO3, build_ticker_country_map


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

    return real_map, nominal_lcu_map, nominal_usd_map


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
    ) = load_gdp_growth_maps(weo_csv)

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
                start_pt = first_in_year(series, y)
                end_year_pt = last_in_year(series, y)
                etf_return = None
                if start_pt is not None and end_year_pt is not None:
                    etf_return = pct_return(start_pt.value, end_year_pt.value)
                gdp_real_same = gdp_real_growth_map.get((country_code, y))
                gdp_nominal_lcu_same = gdp_nominal_lcu_growth_map.get((country_code, y))
                gdp_nominal_usd_same = gdp_nominal_usd_growth_map.get((country_code, y))
                annual_rows.append(
                    {
                        "country_name": country_name,
                        "country_code": country_code,
                        "ticker": ticker,
                        "year": y,
                        "etf_return_pct": etf_return,
                        "gdp_real_growth_pct": gdp_real_same,
                        "gdp_nominal_lcu_growth_pct": gdp_nominal_lcu_same,
                        "gdp_nominal_usd_growth_pct": gdp_nominal_usd_same,
                        "gdp_nominal_usd_minus_etf_growth_pct": (
                            gdp_nominal_usd_same - etf_return
                            if (etf_return is not None and gdp_nominal_usd_same is not None)
                            else None
                        ),
                        "etf_currency": ticker_to_currency.get(ticker, ""),
                    }
                )

        # CAGR rows (1Y, 3Y, 5Y, 10Y)
        for years in CAGR_HORIZONS:
            start_year = cagr_end_year - years + 1
            start_pt = first_in_year(series, start_year)
            end_year_pt = last_in_year(series, cagr_end_year)
            if start_pt is None or end_year_pt is None:
                continue
            total_ret = pct_return(start_pt.value, end_year_pt.value)
            etf_cagr = cagr_from_total_return(total_ret, years)
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
                        if gdp_nominal_usd_cagr is not None
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
        country_summary_df["ticker_currency"] = country_summary_df["ticker_used"].map(
            ticker_currency_map
        ).fillna("")
        country_summary_df["region"] = country_summary_df["country_name"].map(
            COUNTRY_TO_REGION
        ).fillna("Other")
        country_summary_df = country_summary_df[
            ["country_name", "region", "ticker_used", "ticker_currency"]
        ].sort_values(["region", "country_name"], ascending=[True, True]).reset_index(drop=True)

        timeframe_df.to_excel(writer, sheet_name="ETF_Timeframes", index=False)
        annual_df.to_excel(writer, sheet_name="Annual", index=False)
        cagr_df.to_excel(writer, sheet_name="CAGR", index=False)
        pd.DataFrame(
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
        ).to_excel(writer, sheet_name="Lists", index=False)
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
        ws_country["D5"] = "ticker_currency"
        ws_country["E5"] = "ETF CAGR %"
        ws_country["F5"] = "GDP Real CAGR %"
        ws_country["G5"] = "GDP Nominal CAGR % (LCU)"
        ws_country["H5"] = "GDP Nominal CAGR % (USD)"
        ws_country["I5"] = "GDP Nominal USD - ETF CAGR %"
        for c in ["A2", "A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5", "I5"]:
            ws_country[c].font = Font(bold=True)

        horizon_dv = DataValidation(type="list", formula1='"1Y,3Y,5Y,10Y"', allow_blank=False)
        ws_country.add_data_validation(horizon_dv)
        horizon_dv.add("B2")

        country_start_row = 6
        country_end_row = 5 + len(country_summary_df)
        for r in range(country_start_row, country_end_row + 1):
            ws_country[f"E{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$F:$F, MATCH($A{r}&"|"&$C{r}&"|"&$B$2, CAGR!$K:$K, 0)), NA())'
            )
            ws_country[f"F{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$G:$G, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"G{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$H:$H, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"H{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$I:$I, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"I{r}"] = f"=IF(AND(ISNUMBER(E{r}),ISNUMBER(H{r})),H{r}-E{r},NA())"
            for col in ["E", "F", "G", "H", "I"]:
                ws_country[f"{col}{r}"].number_format = "0.00"
        ws_country.auto_filter.ref = f"A5:I{country_end_row}"

        # Right-side country focus panel
        ws_country["K1"] = "Country Focus Dashboard"
        ws_country["K1"].font = Font(bold=True, size=14)
        ws_country["K2"] = "Country"
        ws_country["K3"] = "Ticker (auto)"
        ws_country["K4"] = "As-of Date"
        ws_country["K5"] = "Ticker Currency"
        ws_country["N2"] = "Same-year GDP comparison: last 10 completed years + one projection/YTD row."

        country_count = ws_lists.max_row - 1
        country_dv_focus = DataValidation(
            type="list",
            formula1=f"=Lists!$A$2:$A${country_count + 1}",
            allow_blank=False,
        )
        ws_country.add_data_validation(country_dv_focus)
        country_dv_focus.add("L2")
        ws_country["L2"] = timeframe_df["country_name"].iloc[0]
        ws_country["L3"] = '=IFERROR(INDEX(Lists!$D:$D, MATCH($L$2, Lists!$C:$C, 0)),"")'
        ws_country["L4"] = '=IFERROR(INDEX(ETF_Timeframes!$F:$F, MATCH($L$2&"|"&$L$3&"|MAX", ETF_Timeframes!$H:$H, 0)),"")'
        ws_country["L5"] = '=IFERROR(INDEX(ETF_Timeframes!$I:$I, MATCH($L$2&"|"&$L$3&"|MAX", ETF_Timeframes!$H:$H, 0)),"")'
        ws_country["L4"].number_format = "yyyy-mm-dd"

        ws_country["K7"] = "ETF Cumulative returns"
        ws_country["K7"].font = Font(bold=True)
        ws_country["K8"] = "Timeframe"
        ws_country["L8"] = "ETF Return %"
        ws_country["M8"] = "Start Date"
        for c in ["K8", "L8", "M8"]:
            ws_country[c].font = Font(bold=True)

        timeframe_start_row = 9
        for i, tf in enumerate(TIMEFRAME_ORDER):
            r = timeframe_start_row + i
            ws_country[f"K{r}"] = tf
            ws_country[f"L{r}"] = (
                f'=IFERROR(INDEX(ETF_Timeframes!$G:$G, MATCH($L$2&"|"&$L$3&"|"&$K{r}, ETF_Timeframes!$H:$H, 0)), "")'
            )
            ws_country[f"M{r}"] = (
                f'=IFERROR(INDEX(ETF_Timeframes!$E:$E, MATCH($L$2&"|"&$L$3&"|"&$K{r}, ETF_Timeframes!$H:$H, 0)),"")'
            )

        ws_country["K20"] = "Annual ETF vs GDP (Last 10 Years, %)"
        ws_country["K20"].font = Font(bold=True)
        ws_country["K21"] = "Year"
        ws_country["L21"] = "ETF Return %"
        ws_country["M21"] = "Real GDP Growth %"
        ws_country["N21"] = "Nominal GDP Growth % (LCU)"
        ws_country["O21"] = "Nominal GDP Growth % (USD)"
        ws_country["P21"] = "Nominal GDP USD - ETF %"
        for c in ["K21", "L21", "M21", "N21", "O21", "P21"]:
            ws_country[c].font = Font(bold=True)

        completed_year = pd.Timestamp.today().year - 1
        annual_years = sorted(
            [y for y in annual_df["year"].dropna().unique().tolist() if int(y) <= completed_year]
        )[-ANNUAL_WINDOW_YEARS:]
        for i, year in enumerate(annual_years):
            r = 22 + i
            ws_country[f"K{r}"] = int(year)
            ws_country[f"L{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$E:$E, MATCH($L$2&"|"&$L$3&"|"&$K{r}, Annual!$J:$J, 0)), NA())'
            )
            ws_country[f"M{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$F:$F, MATCH($L$2&"|"&$K{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"N{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$G:$G, MATCH($L$2&"|"&$K{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"O{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$H:$H, MATCH($L$2&"|"&$K{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"P{r}"] = (
                f"=IF(AND(ISNUMBER(O{r}),ISNUMBER(L{r})),O{r}-L{r},NA())"
            )

        projection_years = sorted(
            [y for y in annual_df["year"].dropna().unique().tolist() if int(y) > completed_year]
        )
        annual_last_row = 21 + len(annual_years)
        if projection_years:
            projection_year = int(projection_years[0])
            projection_row = 22 + len(annual_years)
            ws_country[f"K{projection_row}"] = f"{projection_year} (Proj GDP / ETF YTD)"
            ws_country[f"L{projection_row}"] = (
                f'=IFERROR(1*INDEX(ETF_Timeframes!$G:$G, MATCH($L$2&"|"&$L$3&"|YTD", ETF_Timeframes!$H:$H, 0)), NA())'
            )
            ws_country[f"M{projection_row}"] = (
                f'=IFERROR(1*INDEX(Annual!$F:$F, MATCH($L$2&"|"&{projection_year}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"N{projection_row}"] = (
                f'=IFERROR(1*INDEX(Annual!$G:$G, MATCH($L$2&"|"&{projection_year}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"O{projection_row}"] = (
                f'=IFERROR(1*INDEX(Annual!$H:$H, MATCH($L$2&"|"&{projection_year}, Annual!$K:$K, 0)), NA())'
            )
            ws_country[f"P{projection_row}"] = (
                f"=IF(AND(ISNUMBER(O{projection_row}),ISNUMBER(L{projection_row})),O{projection_row}-L{projection_row},NA())"
            )
            annual_last_row = projection_row
            ws_country[f"K{annual_last_row + 1}"] = (
                f"* {projection_year} row: GDP is IMF projection; ETF is YTD return."
            )

        cagr_title_row = max(35, annual_last_row + 3)
        cagr_header_row = cagr_title_row + 1
        cagr_start_row = cagr_header_row + 1
        cagr_end_row = cagr_start_row + 2
        ws_country[f"K{cagr_title_row}"] = "CAGR Comparison (%)"
        ws_country[f"K{cagr_title_row}"].font = Font(bold=True)
        ws_country[f"K{cagr_header_row}"] = "Horizon"
        ws_country[f"L{cagr_header_row}"] = "ETF CAGR %"
        ws_country[f"M{cagr_header_row}"] = "Real GDP CAGR %"
        ws_country[f"N{cagr_header_row}"] = "Nominal GDP CAGR % (LCU)"
        ws_country[f"O{cagr_header_row}"] = "Nominal GDP CAGR % (USD)"
        ws_country[f"P{cagr_header_row}"] = "Nominal GDP USD - ETF CAGR %"
        for c in [
            f"K{cagr_header_row}",
            f"L{cagr_header_row}",
            f"M{cagr_header_row}",
            f"N{cagr_header_row}",
            f"O{cagr_header_row}",
            f"P{cagr_header_row}",
        ]:
            ws_country[c].font = Font(bold=True)

        for i, hz in enumerate(["3Y", "5Y", "10Y"]):
            r = cagr_start_row + i
            ws_country[f"K{r}"] = hz
            ws_country[f"L{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$F:$F, MATCH($L$2&"|"&$L$3&"|"&$K{r}, CAGR!$K:$K, 0)), NA())'
            )
            ws_country[f"M{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$G:$G, MATCH($L$2&"|"&$K{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"N{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$H:$H, MATCH($L$2&"|"&$K{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"O{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$I:$I, MATCH($L$2&"|"&$K{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_country[f"P{r}"] = (
                f"=IF(AND(ISNUMBER(O{r}),ISNUMBER(L{r})),O{r}-L{r},NA())"
            )

        for row in range(timeframe_start_row, timeframe_start_row + len(TIMEFRAME_ORDER)):
            ws_country[f"L{row}"].number_format = "0.00"
            ws_country[f"M{row}"].number_format = "yyyy-mm-dd"
        for row in range(22, annual_last_row + 1):
            for col in ["L", "M", "N", "O", "P"]:
                ws_country[f"{col}{row}"].number_format = "0.00"
        for row in range(cagr_start_row, cagr_end_row + 1):
            for col in ["L", "M", "N", "O", "P"]:
                ws_country[f"{col}{row}"].number_format = "0.00"

        pos_fill = PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid")
        neg_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        for rng in [
            f"L{timeframe_start_row}:L{timeframe_start_row + len(TIMEFRAME_ORDER) - 1}",
            f"L22:P{annual_last_row}",
            f"L{cagr_start_row}:P{cagr_end_row}",
        ]:
            ws_country.conditional_formatting.add(
                rng, CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=pos_fill)
            )
            ws_country.conditional_formatting.add(
                rng, CellIsRule(operator="lessThan", formula=["0"], fill=neg_fill)
            )
        ws_country.conditional_formatting.add(
            f"E{country_start_row}:I{country_end_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=pos_fill),
        )
        ws_country.conditional_formatting.add(
            f"E{country_start_row}:I{country_end_row}",
            CellIsRule(operator="lessThan", formula=["0"], fill=neg_fill),
        )

        fit_columns_from_ranges(ws_tf, [(1, ws_tf.max_column, 1, ws_tf.max_row)])
        fit_columns_from_ranges(ws_annual, [(1, ws_annual.max_column, 1, ws_annual.max_row)])
        fit_columns_from_ranges(ws_cagr, [(1, ws_cagr.max_column, 1, ws_cagr.max_row)])
        fit_columns_from_ranges(ws_lists, [(1, ws_lists.max_column, 1, ws_lists.max_row)])
        fit_columns_from_ranges(
            ws_country,
            [
                (1, 9, 5, country_end_row),
                (11, 12, 2, 5),
                (11, 13, 8, timeframe_start_row + len(TIMEFRAME_ORDER) - 1),
                (11, 16, 21, annual_last_row),
                (11, 16, cagr_header_row, cagr_end_row),
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
