#!/usr/bin/env python3
"""Build an Excel MVP dashboard for ETF vs GDP growth comparison."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

import pandas as pd
from openpyxl.utils import get_column_letter


@dataclass
class PricePoint:
    date: pd.Timestamp
    value: float


def pct_return(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


def cagr_from_total_return(total_ret_pct: float, years: float) -> float:
    if total_ret_pct <= -100.0 or years <= 0:
        return 0.0
    decimal_ret = total_ret_pct / 100.0
    return ((1.0 + decimal_ret) ** (1.0 / years) - 1.0) * 100.0


def last_on_or_before(series: pd.Series, target: pd.Timestamp) -> PricePoint | None:
    available = series.index[series.index <= target]
    if available.empty:
        return None
    dt = available[-1]
    return PricePoint(dt, float(series.loc[dt]))


def max_start_point(series: pd.Series) -> PricePoint | None:
    """Find the earliest valid price point, skipping bad launch prints (zeros/nans)."""
    valid = series[series > 0].dropna()
    if valid.empty:
        return None
    dt = valid.index[0]
    return PricePoint(dt, float(valid.iloc[0]))


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

TIMEFRAME_ORDER = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y", "MAX"]


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
    
    # Fallback for simpler names if regex fails
    if not selected:
        for col in columns:
            parts = col.split(" - ")
            if len(parts) >= 3:
                selected[parts[1]] = col
                
    return selected


def load_gdp_growth_maps(
    weo_csv: str,
) -> tuple[
    dict[tuple[str, int], float],
    dict[tuple[str, int], float],
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
    
    real_map = {(str(r.country_code), int(r.year)): float(r.value) for r in weo[weo["indicator"] == "NGDP_RPCH"].itertuples(index=False)}
    nominal_usd_map = {(str(r.country_code), int(r.year)): float(r.value) for r in weo[weo["indicator"] == "NGDPD_PCH"].itertuples(index=False)}
    nominal_lcu_map = {(str(r.country_code), int(r.year)): float(r.value) for r in weo[weo["indicator"] == "NGDP_PCH"].itertuples(index=False)}
    current_usd_map = {(str(r.country_code), int(r.year)): float(r.value) for r in weo[weo["indicator"] == "NGDPD"].itertuples(index=False)}
    pppex_map = {(str(r.country_code), int(r.year)): float(r.value) for r in weo[weo["indicator"] == "PPPEX"].itertuples(index=False)}

    country_fx_map: dict[tuple[str, int], float] = {}
    ngdp = weo[weo["indicator"] == "NGDP"][["country_code", "year", "value"]].rename(columns={"value": "ngdp_lcu"})
    ngdpd = weo[weo["indicator"] == "NGDPD"][["country_code", "year", "value"]].rename(columns={"value": "ngdp_usd"})
    fx_levels = ngdp.merge(ngdpd, on=["country_code", "year"], how="inner")
    if not fx_levels.empty:
        fx_levels["lcu_per_usd"] = fx_levels["ngdp_lcu"] / fx_levels["ngdp_usd"]
        fx_levels = fx_levels.sort_values(["country_code", "year"]).copy()
        fx_levels["country_lcu_vs_usd_weo_pct"] = (
            fx_levels.groupby("country_code")["lcu_per_usd"].shift(1) 
            / fx_levels["lcu_per_usd"] - 1.0
        ) * 100.0
        country_fx_map = {
            (str(r.country_code), int(r.year)): float(r.country_lcu_vs_usd_weo_pct)
            for r in fx_levels.itertuples(index=False)
            if pd.notna(r.country_lcu_vs_usd_weo_pct)
        }

    return real_map, nominal_lcu_map, nominal_usd_map, country_fx_map, current_usd_map, pppex_map


def load_currency_valuation_map(weo_csv: str) -> dict[str, tuple[float, str]]:
    df = pd.read_csv(weo_csv)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["country_code", "year"])
    pivot = df.pivot_table(index=["country_code", "year"], columns="indicator", values="value").reset_index()
    if not all(c in pivot.columns for c in ["PPPEX", "NGDP", "NGDPD"]): return {}
    pivot["price_level_ratio"] = (pivot["NGDP"] / pivot["NGDPD"]) / pivot["PPPEX"]
    val_map = {}
    for cc in pivot["country_code"].unique():
        c_data = pivot[pivot["country_code"] == cc].sort_values("year")
        try:
            v25 = c_data[c_data["year"] == 2025]["price_level_ratio"].iloc[0]
            avg = c_data[(c_data["year"] >= 2020) & (c_data["year"] <= 2024)]["price_level_ratio"].mean()
            if pd.notna(v25) and pd.notna(avg) and avg > 0:
                dev = (v25 / avg - 1.0) * 100.0
                label = "Undervalued" if dev < -5.0 else "Overvalued" if dev > 5.0 else "Fair Value"
                val_map[str(cc)] = (float(dev), label)
        except: continue
    return val_map


def gdp_cagr(gdp_growth_map, country_code, end_year, years) -> float | None:
    values = []
    for y in range(end_year - years + 1, end_year + 1):
        v = gdp_growth_map.get((country_code, y))
        if v is None: return None
        values.append(v)
    comp = 1.0
    for v in values: comp *= 1.0 + (v / 100.0)
    return ((comp ** (1.0 / years)) - 1.0) * 100.0


def write_dashboard_xlsx(
    timeframe_df: pd.DataFrame,
    annual_df: pd.DataFrame,
    cagr_df: pd.DataFrame,
    output_xlsx: str,
    metadata_csv: str | None = "data/outputs/etf_ticker_metadata.csv",
) -> None:
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.worksheet.datavalidation import DataValidation

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        meta_df = pd.read_csv(metadata_csv) if metadata_csv else pd.DataFrame()
        ticker_fund_size_map = meta_df.set_index("ticker")["fund_size"].dropna().to_dict() if not meta_df.empty else {}
        ticker_exch_map = meta_df.set_index("ticker")["exchange"].fillna("").to_dict() if not meta_df.empty else {}
        ticker_cur_map = meta_df.set_index("ticker")["currency"].fillna("").to_dict() if not meta_df.empty else {}
        
        # Currency Valuation Context
        weo_path = "data/outputs/weo_gdp.csv" # Hardcoded path for lookup
        val_map = load_currency_valuation_map(weo_path)

        # 1. POPULATE DATA SHEETS
        timeframe_df.to_excel(writer, sheet_name="ETF_Timeframes", index=False)
        annual_df.to_excel(writer, sheet_name="Annual", index=False)
        cagr_df.to_excel(writer, sheet_name="CAGR", index=False)
        
        countries = sorted(timeframe_df["country_name"].unique().tolist())
        ticker_map = timeframe_df[["country_name", "ticker"]].drop_duplicates().sort_values(["country_name", "ticker"])
        lists_df = pd.DataFrame({
            "country_name": pd.Series(countries),
            "ticker": pd.Series(sorted(timeframe_df["ticker"].unique().tolist())),
            "val_dev": pd.Series([val_map.get(row.country_code, (None,None))[0] for row in annual_df.drop_duplicates("country_code").itertuples()]),
            "val_label": pd.Series([val_map.get(row.country_code, (None,None))[1] for row in annual_df.drop_duplicates("country_code").itertuples()]),
        })
        lists_df.to_excel(writer, sheet_name="Lists", index=False)
        ticker_map.to_excel(writer, sheet_name="Lists", index=False, startcol=5)

        # 2. BUILD SUMMARY SHEET
        ws_country = writer.book.create_sheet("Country_CAGR_Summary", 0)
        ws_country["A1"] = "Country Macro Disconnect Screener"; ws_country["A1"].font = Font(bold=True, size=14)
        ws_country["A2"] = "Horizon"; ws_country["B2"] = "5Y"
        horizon_dv = DataValidation(type="list", formula1='"1Y,3Y,5Y,10Y"', allow_blank=False)
        ws_country.add_data_validation(horizon_dv); horizon_dv.add("B2")

        # Table 1 Headers
        ws_country.merge_cells("F4:I4"); ws_country["F4"] = "Projected Nominal GDP Growth (USD) %"
        ws_country["F4"].font = Font(bold=True); ws_country["F4"].alignment = Alignment(horizontal="center")
        
        h1 = ["country_name", "ticker_used", "GDP Nominal CAGR % (USD)", "ETF CAGR % (USD)", "Macro Disconnect %", "2026", "2027", "2028", "2029", "Currency Val vs 5Y Avg (%)", "Valuation", "", "region", "GDP Real CAGR %"]
        for i, h in enumerate(h1):
            cell = ws_country.cell(row=5, column=i+1, value=h); cell.font = Font(bold=True)

        screener_countries = annual_df.dropna(subset=["gdp_current_usd"]).sort_values("gdp_current_usd", ascending=False)["country_name"].unique().tolist()
        for r_idx, country in enumerate(screener_countries):
            r = r_idx + 6
            ws_country[f"A{r}"] = country
            # Set default ticker
            def_t = ticker_map[ticker_map["country_name"] == country]["ticker"].iloc[0]
            ws_country[f"B{r}"] = def_t
            ws_country[f"C{r}"] = f'=IFERROR(1*INDEX(CAGR!$I:$I, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            ws_country[f"D{r}"] = f'=IFERROR(1*INDEX(CAGR!$F:$F, MATCH($A{r}&"|"&$B{r}&"|"&$B$2, CAGR!$K:$K, 0)), NA())'
            ws_country[f"E{r}"] = f"=IF(AND(ISNUMBER(C{r}),ISNUMBER(D{r})),C{r}-D{r},NA())"
            for i, year in enumerate(["2026", "2027", "2028", "2029"]):
                col = get_column_letter(6 + i)
                ws_country[f"{col}{r}"] = f'=IFERROR(IF(INDEX(Annual!$H:$H, MATCH($A{r}&"|{year}", Annual!$K:$K, 0))=0, NA(), INDEX(Annual!$H:$H, MATCH($A{r}&"|{year}", Annual!$K:$K, 0))), NA())'
            
            # Currency Valuation Lookups
            cc = annual_df[annual_df["country_name"] == country]["country_code"].iloc[0]
            val_info = val_map.get(cc, (None, "N/A"))
            ws_country[f"J{r}"] = val_info[0]
            ws_country[f"K{r}"] = val_info[1]
            ws_country[f"M{r}"] = COUNTRY_TO_REGION.get(country, "Other")
            ws_country[f"N{r}"] = f'=IFERROR(1*INDEX(CAGR!$G:$G, MATCH($A{r}&"|"&$B$2, CAGR!$L:$L, 0)), NA())'
            for col in ["C","D","E","F","G","H","I","J","N"]: ws_country[f"{col}{r}"].number_format = "0.00"

        # Widths to Headers (using Row 5)
        for col in ws_country.columns:
            header = col[4].value
            if header: ws_country.column_dimensions[get_column_letter(col[0].column)].width = len(str(header)) + 4

        writer.book["ETF_Timeframes"].sheet_state = "hidden"
        writer.book["Annual"].sheet_state = "hidden"
        writer.book["CAGR"].sheet_state = "hidden"
        writer.book["Lists"].sheet_state = "hidden"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etf-csv", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--metadata-csv", default="data/outputs/etf_ticker_metadata.csv")
    parser.add_argument("--output", default="data/outputs/etf_gdp_dashboard_mvp.xlsx")
    args = parser.parse_args()

    from build_combined_etf_weo import build_combined_dataset
    annual_df = build_combined_dataset(args.etf_csv, args.weo_csv, args.metadata_csv)
    annual_df["country_year_key"] = annual_df["country_name"] + "|" + annual_df["year"].astype(str)
    annual_df["country_ticker_year_key"] = annual_df["country_name"] + "|" + annual_df["ticker"] + "|" + annual_df["year"].astype(str)
    cols = annual_df.columns.tolist()
    for k in ["country_ticker_year_key", "country_year_key"]: cols.remove(k)
    annual_df = annual_df[cols[:9] + ["country_ticker_year_key", "country_year_key"] + cols[9:]]

    prices_raw = pd.read_csv(args.etf_csv); prices_raw["Date"] = pd.to_datetime(prices_raw["Date"], errors="coerce")
    prices_raw = prices_raw.dropna(subset=["Date"]).sort_values("Date")
    price_cols = choose_price_columns(prices_raw.columns.tolist())
    meta_df = pd.read_csv(args.metadata_csv); ticker_inc = meta_df.set_index("ticker")["included"].to_dict()
    gdp_real_map, _, _, _, cur_usd_map, _ = load_gdp_growth_maps(args.weo_csv)
    
    cagr_rows, timeframe_rows = [], []
    for ticker, col_name in price_cols.items():
        if ticker_inc.get(ticker) != "yes": continue
        match_row = annual_df[annual_df["ticker"] == ticker].iloc[0]
        country, cc = match_row["country_name"], match_row["country_code"]
        series = prices_raw.set_index("Date")[col_name].dropna()
        if series.empty: continue
        s_max = max_start_point(series); e_pt = PricePoint(series.index[-1], float(series.iloc[-1]))
        
        for hz in ["1Y", "3Y", "5Y", "10Y"]:
            years = int(hz[:-1])
            s_pt = last_on_or_before(series, e_pt.date - pd.DateOffset(years=years))
            etf_c = cagr_from_total_return(pct_return(s_pt.value, e_pt.value), years) if s_pt and s_pt.date >= s_max.date else None
            gdp_u = None
            try:
                v_s, v_e = cur_usd_map.get((cc, 2025-years)), cur_usd_map.get((cc, 2025))
                if v_s and v_e: gdp_u = cagr_from_total_return(((v_e/v_s)-1)*100, years)
            except: pass
            cagr_rows.append({"country_name": country, "ticker": ticker, "horizon": hz, "etf_return_usd_pct": etf_c, "gdp_real_cagr": gdp_real_map.get((cc, 2025)), "gdp_usd_cagr": gdp_u, "lookup_key": f"{country}|{ticker}|{hz}", "country_horizon_key": f"{country}|{hz}"})
        
        for tf in TIMEFRAME_ORDER:
            # Simplified timeframe rows for sheet population
            timeframe_rows.append({"country_name": country, "ticker": ticker, "timeframe": tf, "start_date": None, "etf_return_usd_pct": 0.0, "lookup_key": f"{country}|{ticker}|{tf}"})

    cagr_df = pd.DataFrame(cagr_rows)
    cols = cagr_df.columns.tolist()
    for k in ["lookup_key", "country_horizon_key"]: cols.remove(k)
    cagr_df = cagr_df[cols[:10] + ["lookup_key", "country_horizon_key"] + cols[10:]]
    
    write_dashboard_xlsx(pd.DataFrame(timeframe_rows), annual_df, cagr_df, args.output, args.metadata_csv)
    print(f"Success: Dashboard written to {args.output}")

if __name__ == "__main__": main()
