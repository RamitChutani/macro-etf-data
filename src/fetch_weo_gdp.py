#!/usr/bin/env python3
"""Fetch IMF WEO GDP data for ETF countries and export normalized CSV."""

from __future__ import annotations

import argparse
import csv
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from etf_mapping import COUNTRY_TO_ISO3 as ETF_COUNTRY_TO_ISO3

INDICATOR_LABELS = {
    "NGDPD": "GDP, current prices (U.S. dollars)",
    "NGDP": "GDP, current prices (domestic currency)",
    "NGDP_RPCH": "Real GDP growth (percent change)",
    "NGDPD_PCH": "Nominal GDP growth (percent change, derived from NGDPD)",
    "NGDP_PCH": "Nominal GDP growth (percent change, derived from NGDP)",
    "PPPEX": "Implied PPP conversion rate",
}


def build_weo_url(
    countries: list[str],
    indicators: list[str],
    start_year: int,
    end_year: int,
    base_url: str,
) -> str:
    key = f"{'+'.join(countries)}.{'+'.join(indicators)}.A"
    encoded_key = urllib.parse.quote(key, safe="+.")
    params = urllib.parse.urlencode(
        {"startPeriod": str(start_year), "endPeriod": str(end_year)}
    )
    return f"{base_url.rstrip('/')}/data/WEO/{encoded_key}?{params}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sdmx_generic_xml(xml_payload: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_payload)
    rows: list[dict[str, str]] = []

    for series in root.iter():
        if _local_name(series.tag) != "Series":
            continue

        series_key: dict[str, str] = {}
        # SDMX-ML generic format: <Series><SeriesKey><Value id=... value=.../></SeriesKey>...
        for child in series:
            if _local_name(child.tag) == "SeriesKey":
                for item in child:
                    if _local_name(item.tag) == "Value":
                        k = item.attrib.get("id")
                        v = item.attrib.get("value")
                        if k and v:
                            series_key[k] = v
        # SDMX-ML compact format: <Series COUNTRY="..." INDICATOR="..." FREQUENCY="...">
        # Use direct series attributes when present.
        for k, v in series.attrib.items():
            if k in {"COUNTRY", "INDICATOR", "FREQUENCY"} and v:
                series_key[k] = v

        country_code = series_key.get("COUNTRY", "")
        indicator = series_key.get("INDICATOR", "")
        frequency = series_key.get("FREQUENCY", "")

        for obs in series:
            if _local_name(obs.tag) != "Obs":
                continue
            year = ""
            value = ""
            # SDMX-ML compact format often stores values as Obs attributes.
            if "TIME_PERIOD" in obs.attrib:
                year = obs.attrib.get("TIME_PERIOD", "")
            if "OBS_VALUE" in obs.attrib:
                value = obs.attrib.get("OBS_VALUE", "")
            for item in obs:
                ln = _local_name(item.tag)
                if ln == "ObsDimension":
                    year = item.attrib.get("value", "")
                elif ln == "ObsValue":
                    value = item.attrib.get("value", "")

            if not year:
                continue

            rows.append(
                {
                    "country_code": country_code,
                    "indicator": indicator,
                    "indicator_label": INDICATOR_LABELS.get(indicator, indicator),
                    "frequency": frequency,
                    "year": year,
                    "value": value,
                }
            )

    return rows


def write_csv(rows: list[dict[str, str]], output_path: str) -> None:
    fieldnames = [
        "country_name",
        "country_code",
        "indicator",
        "indicator_label",
        "frequency",
        "year",
        "value",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_derived_growth_rows(
    rows: list[dict[str, str]],
    *,
    level_indicator: str,
    growth_indicator: str,
) -> list[dict[str, str]]:
    """YoY growth from level indicator."""
    out = list(rows)
    existing = {
        (r.get("country_code", ""), r.get("year", ""))
        for r in rows
        if r.get("indicator") == growth_indicator
    }
    by_country: dict[str, dict[int, float]] = {}
    for row in rows:
        if row.get("indicator") != level_indicator:
            continue
        country = row.get("country_code", "")
        year_str = row.get("year", "")
        value_str = row.get("value", "")
        try:
            year = int(year_str)
            value = float(value_str)
        except (TypeError, ValueError):
            continue
        by_country.setdefault(country, {})[year] = value

    for country_code, levels in by_country.items():
        years = sorted(levels)
        for y in years:
            if (country_code, str(y)) in existing:
                continue
            prev = levels.get(y - 1)
            cur = levels.get(y)
            if prev in (None, 0) or cur is None:
                continue
            growth_pct = ((cur / prev) - 1.0) * 100.0
            out.append(
                {
                    "country_name": next(
                        (
                            r.get("country_name", country_code)
                            for r in rows
                            if r.get("country_code") == country_code
                        ),
                        country_code,
                    ),
                    "country_code": country_code,
                    "indicator": growth_indicator,
                    "indicator_label": INDICATOR_LABELS[growth_indicator],
                    "frequency": "A",
                    "year": str(y),
                    "value": f"{growth_pct:.6f}",
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch IMF WEO GDP data (NGDPD, NGDP, NGDP_RPCH, PPPEX) for ETF countries."
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2029)
    parser.add_argument(
        "--base-url",
        default="https://api.imf.org/external/sdmx/2.1",
        help="IMF SDMX base URL.",
    )
    parser.add_argument(
        "--countries",
        default=",".join(ETF_COUNTRY_TO_ISO3.values()),
        help="Comma-separated ISO3 country codes.",
    )
    parser.add_argument(
        "--indicators",
        default="NGDPD,NGDP,NGDP_RPCH,PPPEX",
        help="Comma-separated WEO indicator codes.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip fetch, only run derived logic on existing file.",
    )
    parser.add_argument("--output", default="data/outputs/weo_gdp.csv")
    args = parser.parse_args()

    iso_to_name = {v: k for k, v in ETF_COUNTRY_TO_ISO3.items()}

    if not args.no_fetch:
        countries = args.countries.split(",")
        indicators = args.indicators.split(",")
        url = build_weo_url(
            countries, indicators, args.start_year, args.end_year, args.base_url
        )
        print(f"Request URL:\n{url}\n")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            payload = response.read()
            rows = parse_sdmx_generic_xml(payload)
            for r in rows:
                r["country_name"] = iso_to_name.get(r["country_code"], r["country_code"])
    else:
        with open(args.output, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    rows = append_derived_growth_rows(
        rows, level_indicator="NGDPD", growth_indicator="NGDPD_PCH"
    )
    rows = append_derived_growth_rows(
        rows, level_indicator="NGDP", growth_indicator="NGDP_PCH"
    )
    rows.sort(key=lambda r: (r["country_name"], r["indicator"], r["year"]))
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
