"""Canonical ETF country/ticker mappings shared across pipeline scripts."""

from __future__ import annotations


ETF_COUNTRY_TO_TICKERS: dict[str, list[str]] = {
    "Australia": ["SAUS.L"],
    "Brazil": ["XMBR.L"],
    "Bulgaria": ["BGX.L"],
    "Canada": ["CSCA.L"],
    "China": ["IASH.L", "FRCH.L"],
    "France": ["ISFR.L"],
    "Germany": ["XDAX.L"],
    "Greece": ["0IWZ.L"],
    "India": ["IIND.L", "FRIN.L", "NDIA.L"],
    "Indonesia": ["INDO.L"],
    "Italy": ["CMIB.L"],
    "Japan": ["LCJP.L", "CJPU.L"],
    "Kuwait": ["MKUW.L"],
    "Malaysia": ["XCX3.L"],
    "Mexico": ["XMEX.L"],
    "Pakistan": ["XBAK.L"],
    "Philippines": ["XPHG.L"],
    "Poland": ["SPOL.L", "IPOL.L"],
    "Saudi Arabia": ["IKSA.L"],
    "Singapore": ["0JLR.L"],
    "South Africa": ["SRSA.L", "IRSA.L"],
    "South Korea": ["CSKR.L", "FLRK.L"],
    "Sweden": ["OMXS.L"],
    "Switzerland": ["CSWG.L"],
    "Taiwan": ["XMTW.L"],
    "Thailand": ["XCX4.L"],
    "Turkey": ["TURL.L"],
    "United Kingdom": ["CUKX.L", "CSUK.L"],
    "United States": ["CSPX.L", "VUAA.L", "VUSA.L"],
    "Vietnam": ["XFVT.L"],
}


COUNTRY_TO_ISO3: dict[str, str] = {
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Brazil": "BRA",
    "Bulgaria": "BGR",
    "Canada": "CAN",
    "China": "CHN",
    "France": "FRA",
    "Germany": "DEU",
    "Greece": "GRC",
    "Hong Kong": "HKG",
    "India": "IND",
    "Indonesia": "IDN",
    "Italy": "ITA",
    "Japan": "JPN",
    "Kuwait": "KWT",
    "Malaysia": "MYS",
    "Mexico": "MEX",
    "Netherlands": "NLD",
    "Pakistan": "PAK",
    "Philippines": "PHL",
    "Poland": "POL",
    "Saudi Arabia": "SAU",
    "Singapore": "SGP",
    "South Africa": "ZAF",
    "South Korea": "KOR",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "Taiwan": "TWN",
    "Thailand": "THA",
    "Turkey": "TUR",
    "United Kingdom": "GBR",
    "United States": "USA",
    "Vietnam": "VNM",
}


COUNTRIES_WITH_SUFFIXED_PRIMARY = {
    "China",
    "France",
    "India",
    "Japan",
    "South Korea",
    "Spain",
    "Taiwan",
    "United Kingdom",
}


def build_ticker_country_map() -> dict[str, str]:
    ticker_to_country: dict[str, str] = {}
    for country_name, tickers in ETF_COUNTRY_TO_TICKERS.items():
        for ticker in tickers:
            ticker_to_country[ticker] = country_name
    return ticker_to_country


def build_label_to_ticker_map() -> dict[str, str]:
    """Build the existing fetch label format (e.g., China_1, China_2)."""
    out: dict[str, str] = {}
    for country_name, tickers in ETF_COUNTRY_TO_TICKERS.items():
        if len(tickers) == 1:
            out[country_name] = tickers[0]
            continue
        if country_name in COUNTRIES_WITH_SUFFIXED_PRIMARY:
            for i, ticker in enumerate(tickers, start=1):
                out[f"{country_name}_{i}"] = ticker
            continue
        out[country_name] = tickers[0]
        for i, ticker in enumerate(tickers[1:], start=2):
            out[f"{country_name}_{i}"] = ticker
    return out
