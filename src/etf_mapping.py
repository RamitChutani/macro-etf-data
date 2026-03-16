"""Canonical ETF country/ticker mappings shared across pipeline scripts."""

from __future__ import annotations


ETF_COUNTRY_TO_TICKERS: dict[str, list[str]] = {
    "Australia": ["SAUS.L", "EWA"],
    "Austria": ["EWO"],
    "Belgium": ["EWK"],
    "Brazil": ["XMBR.L", "EWZ"],
    "Bulgaria": ["BGX.L"],
    "Canada": ["CSCA.L", "EWC"],
    "China": ["IASH.L", "FRCH.L", "MCHI"],
    "France": ["ISFR.L", "EWQ"],
    "Germany": ["XDAX.L", "EWG", "EXS1.DE"],
    "Greece": ["0IWZ.L", "GREK"],
    "Hong Kong": ["EWH"],
    "India": ["IIND.L", "FRIN.L", "NDIA.L", "INDA", "LYINR.SW"],
    "Indonesia": ["INDO.L", "EIDO", "INDO.PA"],
    "Italy": ["CMIB.L", "EWI"],
    "Japan": ["LCJP.L", "CJPU.L", "EWJ"],
    "Kuwait": ["MKUW.L", "KWT"],
    "Malaysia": ["XCX3.L", "EWM"],
    "Mexico": ["XMEX.L", "EWW"],
    "Netherlands": ["EWN"],
    "Pakistan": ["XBAK.L"],
    "Philippines": ["XPHG.L", "EPHE"],
    "Poland": ["SPOL.L", "IPOL.L", "EPOL"],
    "Saudi Arabia": ["IKSA.L", "KSA"],
    "Singapore": ["0JLR.L", "EWS"],
    "South Africa": ["SRSA.L", "IRSA.L", "EZA"],
    "South Korea": ["CSKR.L", "FLRK.L", "EWY"],
    "Spain": ["XESP.DE", "EWP"],
    "Sweden": ["OMXS.L", "EWD"],
    "Switzerland": ["CSWG.L", "EWL", "CSW.PA"],
    "Taiwan": ["XMTW.L", "EWT"],
    "Thailand": ["XCX4.L", "THD"],
    "Turkey": ["TURL.L", "TUR"],
    "United Kingdom": ["CUKX.L", "CSUK.L", "EWU"],
    "United States": ["CSPX.L", "VUAA.L", "VUSA.L", "CSUS.L"],
    "Vietnam": ["XFVT.L", "VNAM"],
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


# Local Currency Unit (LCU) for each country - used for FX calculations vs USD
COUNTRY_TO_LCU: dict[str, str] = {
    "Australia": "AUD",
    "Austria": "EUR",
    "Belgium": "EUR",
    "Brazil": "BRL",
    "Bulgaria": "BGN",
    "Canada": "CAD",
    "China": "CNY",
    "France": "EUR",
    "Germany": "EUR",
    "Greece": "EUR",
    "Hong Kong": "HKD",
    "India": "INR",
    "Indonesia": "IDR",
    "Italy": "EUR",
    "Japan": "JPY",
    "Kuwait": "KWD",
    "Malaysia": "MYR",
    "Mexico": "MXN",
    "Netherlands": "EUR",
    "Pakistan": "PKR",
    "Philippines": "PHP",
    "Poland": "PLN",
    "Saudi Arabia": "SAR",
    "Singapore": "SGD",
    "South Africa": "ZAR",
    "South Korea": "KRW",
    "Spain": "EUR",
    "Sweden": "SEK",
    "Switzerland": "CHF",
    "Taiwan": "TWD",
    "Thailand": "THB",
    "Turkey": "TRY",
    "United Kingdom": "GBP",
    "United States": "USD",
    "Vietnam": "VND",
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
    "United States",
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
