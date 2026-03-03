#!/usr/bin/env python3
"""Build an Excel MVP dashboard for ETF vs GDP growth comparison."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

import pandas as pd

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
) -> tuple[dict[tuple[str, int], float], dict[tuple[str, int], float]]:
    weo = pd.read_csv(weo_csv)
    weo["year"] = pd.to_numeric(weo["year"], errors="coerce").astype("Int64")
    weo["value"] = pd.to_numeric(weo["value"], errors="coerce")
    weo = weo.dropna(subset=["country_code", "year"])
    weo["year"] = weo["year"].astype(int)
    real_weo = weo[(weo["indicator"] == "NGDP_RPCH") & (weo["value"].notna())].copy()
    nominal_weo = weo[(weo["indicator"] == "NGDPD_PCH") & (weo["value"].notna())].copy()

    real_map = {
        (str(r.country_code), int(r.year)): float(r.value)
        for r in real_weo.itertuples(index=False)
    }
    nominal_map = {
        (str(r.country_code), int(r.year)): float(r.value)
        for r in nominal_weo.itertuples(index=False)
    }

    # Backward-compatible fallback if NGDPD_PCH not present in weo_csv.
    if not nominal_map:
        gdp_levels = weo[(weo["indicator"] == "NGDPD") & (weo["value"].notna())].copy()
        gdp_levels = gdp_levels.sort_values(["country_code", "year"])
        gdp_levels["nominal_growth"] = (
            gdp_levels.groupby("country_code")["value"].pct_change() * 100.0
        )
        nominal_map = {
            (str(r.country_code), int(r.year)): float(r.nominal_growth)
            for r in gdp_levels.itertuples(index=False)
            if pd.notna(r.nominal_growth)
        }

    return real_map, nominal_map


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
    gdp_real_growth_map, gdp_nominal_growth_map = load_gdp_growth_maps(weo_csv)

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

        # Annual ETF vs GDP table for last 10 completed years (GDP-driven window).
        gdp_years = [y for y in gdp_years if y <= completed_year]
        if gdp_years:
            last_10_years = gdp_years[-ANNUAL_WINDOW_YEARS:]
            for y in last_10_years:
                start_pt = first_in_year(series, y)
                end_year_pt = last_in_year(series, y)
                etf_return = None
                if start_pt is not None and end_year_pt is not None:
                    etf_return = pct_return(start_pt.value, end_year_pt.value)
                gdp_real_same = gdp_real_growth_map.get((country_code, y))
                gdp_nominal_same = gdp_nominal_growth_map.get((country_code, y))
                annual_rows.append(
                    {
                        "country_name": country_name,
                        "country_code": country_code,
                        "ticker": ticker,
                        "year": y,
                        "etf_return_pct": etf_return,
                        "gdp_real_growth_pct": gdp_real_same,
                        "gdp_nominal_growth_pct": gdp_nominal_same,
                        "gdp_real_minus_etf_growth_pct": (
                            gdp_real_same - etf_return
                            if (etf_return is not None and gdp_real_same is not None)
                            else None
                        ),
                        "gdp_nominal_minus_etf_growth_pct": (
                            gdp_nominal_same - etf_return
                            if (etf_return is not None and gdp_nominal_same is not None)
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
            gdp_nominal_cagr = gdp_cagr(
                gdp_nominal_growth_map, country_code, cagr_end_year, years
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
                    "gdp_nominal_cagr_pct": gdp_nominal_cagr,
                    "gdp_real_minus_etf_cagr_pct": (
                        gdp_real_cagr - etf_cagr if gdp_real_cagr is not None else None
                    ),
                    "gdp_nominal_minus_etf_cagr_pct": (
                        gdp_nominal_cagr - etf_cagr
                        if gdp_nominal_cagr is not None
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
                "gdp_nominal_growth_pct",
                "gdp_real_minus_etf_growth_pct",
                "gdp_nominal_minus_etf_growth_pct",
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
            gdp_nominal_cagr = gdp_cagr(
                gdp_nominal_growth_map, country_code, cagr_end_year, years
            )
            if gdp_real_cagr is None and gdp_nominal_cagr is None:
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
                    "gdp_nominal_cagr_pct": gdp_nominal_cagr,
                    "gdp_real_minus_etf_cagr_pct": None,
                    "gdp_nominal_minus_etf_cagr_pct": None,
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
                "gdp_nominal_cagr_pct",
                "gdp_real_minus_etf_cagr_pct",
                "gdp_nominal_minus_etf_cagr_pct",
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
) -> None:
    from openpyxl.styles import Font
    from openpyxl.styles import PatternFill
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.worksheet.datavalidation import DataValidation

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        default_map = (
            timeframe_df[["country_name", "ticker"]]
            .drop_duplicates()
            .sort_values(["country_name", "ticker"])
            .groupby("country_name", as_index=False)
            .first()
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
        ws_dash = wb.create_sheet("Dashboard")

        # Source-sheet usability
        ws_tf.auto_filter.ref = ws_tf.dimensions
        ws_tf.freeze_panes = "A2"
        ws_annual.auto_filter.ref = ws_annual.dimensions
        ws_annual.freeze_panes = "A2"
        ws_cagr.auto_filter.ref = ws_cagr.dimensions
        ws_cagr.freeze_panes = "A2"
        ws_country.auto_filter.ref = ws_country.dimensions
        ws_country.freeze_panes = "A6"

        ws_country["A1"] = "Country CAGR Disconnect Screener"
        ws_country["A1"].font = Font(bold=True, size=14)
        ws_country["A2"] = "Horizon"
        ws_country["B2"] = "5Y"
        ws_country["D2"] = "Start here: choose horizon, then sort by GDP - ETF CAGR."
        ws_country["A3"] = "Metrics are CAGR (annualized), not cumulative return."
        ws_country["A5"] = "country_name"
        ws_country["B5"] = "region"
        ws_country["C5"] = "ticker_used"
        ws_country["D5"] = "ticker_currency"
        ws_country["E5"] = "ETF CAGR %"
        ws_country["F5"] = "GDP Real CAGR %"
        ws_country["G5"] = "GDP - ETF CAGR %"
        for c in ["A2", "A5", "B5", "C5", "D5", "E5", "F5", "G5"]:
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
            ws_country[f"G{r}"] = f"=IF(AND(ISNUMBER(E{r}),ISNUMBER(F{r})),F{r}-E{r},NA())"
            for col in ["E", "F", "G"]:
                ws_country[f"{col}{r}"].number_format = "0.00"

        ws_country.auto_filter.ref = f"A5:G{country_end_row}"

        # Dashboard header and controls
        ws_dash["A1"] = "Interactive Excel KPI Dashboard"
        ws_dash["A1"].font = Font(bold=True, size=14)
        ws_dash["A2"] = "Country"
        ws_dash["A3"] = "Ticker (auto)"
        ws_dash["A4"] = "As-of Date"
        ws_dash["A5"] = "Ticker Currency"
        ws_dash["D2"] = "Choose country from dropdown; ticker auto-selects first mapped ETF."
        ws_dash["D3"] = "ETF timeframe panel is ETF-only; GDP comparison is annual (last 10 years)."
        ws_dash["D4"] = "Review Country_CAGR_Summary first to identify top disconnects."

        country_count = ws_lists.max_row - 1
        country_dv = DataValidation(
            type="list",
            formula1=f"=Lists!$A$2:$A${country_count + 1}",
            allow_blank=False,
        )
        ws_dash.add_data_validation(country_dv)
        country_dv.add("B2")
        ws_dash["B2"] = timeframe_df["country_name"].iloc[0]
        ws_dash["B3"] = '=IFERROR(INDEX(Lists!$D:$D, MATCH($B$2, Lists!$C:$C, 0)),"")'
        ws_dash["B4"] = '=IFERROR(INDEX(ETF_Timeframes!$F:$F, MATCH($B$2&"|"&$B$3&"|MAX", ETF_Timeframes!$H:$H, 0)),"")'
        ws_dash["B5"] = '=IFERROR(INDEX(ETF_Timeframes!$I:$I, MATCH($B$2&"|"&$B$3&"|MAX", ETF_Timeframes!$H:$H, 0)),"")'
        ws_dash["B4"].number_format = "yyyy-mm-dd"

        # ETF-only timeframe KPI table
        ws_dash["A6"] = "ETF Timeframe Returns (%)"
        ws_dash["A6"].font = Font(bold=True)
        ws_dash["A7"] = "Timeframe"
        ws_dash["B7"] = "ETF Return %"
        ws_dash["C7"] = "Start Date"
        for c in ["A7", "B7", "C7"]:
            ws_dash[c].font = Font(bold=True)

        start_row = 8
        for i, tf in enumerate(TIMEFRAME_ORDER):
            r = start_row + i
            ws_dash[f"A{r}"] = tf
            ws_dash[f"B{r}"] = (
                f'=IFERROR(INDEX(ETF_Timeframes!$G:$G, MATCH($B$2&"|"&$B$3&"|"&$A{r}, ETF_Timeframes!$H:$H, 0)), "")'
            )
            ws_dash[f"C{r}"] = (
                f'=IFERROR(INDEX(ETF_Timeframes!$E:$E, MATCH($B$2&"|"&$B$3&"|"&$A{r}, ETF_Timeframes!$H:$H, 0)),"")'
            )

        # Annual ETF vs GDP comparison table (last 10 years)
        ws_dash["A21"] = "Annual ETF vs GDP (Last 10 Years, %)"
        ws_dash["A21"].font = Font(bold=True)
        ws_dash["A22"] = "Year"
        ws_dash["B22"] = "ETF Return %"
        ws_dash["C22"] = "Real GDP Growth %"
        ws_dash["D22"] = "Nominal GDP Growth %"
        ws_dash["E22"] = "Real GDP - ETF %"
        ws_dash["F22"] = "Nominal GDP - ETF %"
        for c in ["A22", "B22", "C22", "D22", "E22", "F22"]:
            ws_dash[c].font = Font(bold=True)

        annual_years = sorted(annual_df["year"].dropna().unique().tolist())[-ANNUAL_WINDOW_YEARS:]
        for i, year in enumerate(annual_years):
            r = 23 + i
            ws_dash[f"A{r}"] = int(year)
            ws_dash[f"B{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$E:$E, MATCH($B$2&"|"&$B$3&"|"&$A{r}, Annual!$J:$J, 0)), NA())'
            )
            ws_dash[f"C{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$F:$F, MATCH($B$2&"|"&$A{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_dash[f"D{r}"] = (
                f'=IFERROR(1*INDEX(Annual!$G:$G, MATCH($B$2&"|"&$A{r}, Annual!$K:$K, 0)), NA())'
            )
            ws_dash[f"E{r}"] = f"=IF(AND(ISNUMBER(B{r}),ISNUMBER(C{r})),C{r}-B{r},NA())"
            ws_dash[f"F{r}"] = f"=IF(AND(ISNUMBER(B{r}),ISNUMBER(D{r})),D{r}-B{r},NA())"

        # CAGR KPI table
        cagr_title_row = 35
        cagr_header_row = 36
        cagr_start_row = 37
        ws_dash[f"A{cagr_title_row}"] = "CAGR Comparison (%)"
        ws_dash[f"A{cagr_title_row}"].font = Font(bold=True)
        ws_dash[f"A{cagr_header_row}"] = "Horizon"
        ws_dash[f"B{cagr_header_row}"] = "ETF CAGR %"
        ws_dash[f"C{cagr_header_row}"] = "Real GDP CAGR %"
        ws_dash[f"D{cagr_header_row}"] = "Nominal GDP CAGR %"
        ws_dash[f"E{cagr_header_row}"] = "Real GDP - ETF CAGR %"
        ws_dash[f"F{cagr_header_row}"] = "Nominal GDP - ETF CAGR %"
        for c in [
            f"A{cagr_header_row}",
            f"B{cagr_header_row}",
            f"C{cagr_header_row}",
            f"D{cagr_header_row}",
            f"E{cagr_header_row}",
            f"F{cagr_header_row}",
        ]:
            ws_dash[c].font = Font(bold=True)

        for i, hz in enumerate(["3Y", "5Y", "10Y"]):
            r = cagr_start_row + i
            ws_dash[f"A{r}"] = hz
            ws_dash[f"B{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$F:$F, MATCH($B$2&"|"&$B$3&"|"&$A{r}, CAGR!$K:$K, 0)), NA())'
            )
            ws_dash[f"C{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$G:$G, MATCH($B$2&"|"&$A{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_dash[f"D{r}"] = (
                f'=IFERROR(1*INDEX(CAGR!$H:$H, MATCH($B$2&"|"&$A{r}, CAGR!$L:$L, 0)), NA())'
            )
            ws_dash[f"E{r}"] = f"=IF(AND(ISNUMBER(B{r}),ISNUMBER(C{r})),C{r}-B{r},NA())"
            ws_dash[f"F{r}"] = f"=IF(AND(ISNUMBER(B{r}),ISNUMBER(D{r})),D{r}-B{r},NA())"

        # Number format
        for row in range(8, 8 + len(TIMEFRAME_ORDER)):
            for col in ["B"]:
                ws_dash[f"{col}{row}"].number_format = "0.00"
            ws_dash[f"C{row}"].number_format = "yyyy-mm-dd"
        for row in range(23, 23 + len(annual_years)):
            for col in ["B", "C", "D", "E", "F"]:
                ws_dash[f"{col}{row}"].number_format = "0.00"
        for row in range(cagr_start_row, cagr_start_row + 3):
            for col in ["B", "C", "D", "E", "F"]:
                ws_dash[f"{col}{row}"].number_format = "0.00"

        # Conditional formatting for KPI numeric cells.
        pos_fill = PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid")
        neg_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        for rng in ["B8:B16", "B23:F32", "B37:F39"]:
            ws_dash.conditional_formatting.add(
                rng, CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=pos_fill)
            )
            ws_dash.conditional_formatting.add(
                rng, CellIsRule(operator="lessThan", formula=["0"], fill=neg_fill)
            )
        ws_country.conditional_formatting.add(
            f"E{country_start_row}:G{country_end_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=pos_fill),
        )
        ws_country.conditional_formatting.add(
            f"E{country_start_row}:G{country_end_row}",
            CellIsRule(operator="lessThan", formula=["0"], fill=neg_fill),
        )

        # Layout polish
        ws_dash.column_dimensions["A"].width = 14
        ws_dash.column_dimensions["B"].width = 14
        ws_dash.column_dimensions["C"].width = 18
        ws_dash.column_dimensions["D"].width = 18
        ws_dash.column_dimensions["E"].width = 20
        ws_dash.column_dimensions["F"].width = 22
        ws_dash.freeze_panes = None
        ws_country.column_dimensions["A"].width = 20
        ws_country.column_dimensions["B"].width = 16
        ws_country.column_dimensions["C"].width = 14
        ws_country.column_dimensions["D"].width = 14
        ws_country.column_dimensions["E"].width = 14
        ws_country.column_dimensions["F"].width = 16
        ws_country.column_dimensions["G"].width = 18

        # Keep helper lists out of the way.
        ws_lists.sheet_state = "hidden"
        wb.active = wb.sheetnames.index("Country_CAGR_Summary")

        # Force Excel to recalculate formulas/charts on open.
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
    write_dashboard_xlsx(timeframe_df, annual_df, cagr_df, args.output)
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
