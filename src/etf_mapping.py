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
    "Switzerland": ["EWL", "CSWG.L", "CSW.PA"],
    "Taiwan": ["XMTW.L", "EWT"],
    "Thailand": ["XCX4.L", "THD"],
    "Turkey": ["TUR", "TURL.L"],
    "United Kingdom": ["CUKX.L", "CSUK.L", "EWU"],
    "United States": ["CSPX.L", "VUAA.L", "VUSA.L", "CSUS.L"],
    "Vietnam": ["XFVT.L", "VNAM"],
}


COUNTRY_TO_ISO3: dict[str, str] = {
    "Algeria": "DZA",
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Bangladesh": "BGD",
    "Belgium": "BEL",
    "Brazil": "BRA",
    "Bulgaria": "BGR",
    "Canada": "CAN",
    "Chile": "CHL",
    "China": "CHN",
    "Colombia": "COL",
    "Czech Republic": "CZE",
    "Denmark": "DNK",
    "Egypt": "EGY",
    "Finland": "FIN",
    "France": "FRA",
    "Germany": "DEU",
    "Greece": "GRC",
    "Hong Kong": "HKG",
    "Hungary": "HUN",
    "India": "IND",
    "Indonesia": "IDN",
    "Iran": "IRN",
    "Iraq": "IRQ",
    "Ireland": "IRL",
    "Israel": "ISR",
    "Italy": "ITA",
    "Japan": "JPN",
    "Kazakhstan": "KAZ",
    "Kuwait": "KWT",
    "Malaysia": "MYS",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NLD",
    "New Zealand": "NZL",
    "Nigeria": "NGA",
    "Norway": "NOR",
    "Pakistan": "PAK",
    "Peru": "PER",
    "Philippines": "PHL",
    "Poland": "POL",
    "Portugal": "PRT",
    "Qatar": "QAT",
    "Romania": "ROU",
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
    "Ukraine": "UKR",
    "United Arab Emirates": "ARE",
    "United Kingdom": "GBR",
    "United States": "USA",
    "Vietnam": "VNM",
}


# Local Currency Unit (LCU) for each country - used for FX calculations vs USD
COUNTRY_TO_LCU: dict[str, str] = {
    "Algeria": "DZD",
    "Argentina": "ARS",
    "Australia": "AUD",
    "Austria": "EUR",
    "Bangladesh": "BDT",
    "Belgium": "EUR",
    "Brazil": "BRL",
    "Bulgaria": "BGN",
    "Canada": "CAD",
    "Chile": "CLP",
    "China": "CNY",
    "Colombia": "COP",
    "Czech Republic": "CZK",
    "Denmark": "DKK",
    "Egypt": "EGP",
    "Finland": "EUR",
    "France": "EUR",
    "Germany": "EUR",
    "Greece": "EUR",
    "Hong Kong": "HKD",
    "Hungary": "HUF",
    "India": "INR",
    "Indonesia": "IDR",
    "Iran": "IRR",
    "Iraq": "IQD",
    "Ireland": "EUR",
    "Israel": "ILS",
    "Italy": "EUR",
    "Japan": "JPY",
    "Kazakhstan": "KZT",
    "Kuwait": "KWD",
    "Malaysia": "MYR",
    "Mexico": "MXN",
    "Morocco": "MAD",
    "Netherlands": "EUR",
    "New Zealand": "NZD",
    "Nigeria": "NGN",
    "Norway": "NOK",
    "Pakistan": "PKR",
    "Peru": "PEN",
    "Philippines": "PHP",
    "Poland": "PLN",
    "Portugal": "EUR",
    "Qatar": "QAR",
    "Romania": "RON",
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
    "Ukraine": "UAH",
    "United Arab Emirates": "AED",
    "United Kingdom": "GBP",
    "United States": "USD",
    "Vietnam": "VND",
}


# Countries allowed to use Distributing ETFs (for top 60 economies not passing Accumulating filter)
# These countries will use Adjusted Close price for comparability with Accumulating ETFs
ALLOW_DIST_COUNTRIES: set[str] = {
    "Austria",
    "Belgium",
    "Bulgaria",
    "Greece",
    "Hong Kong",
    "Italy",
    "Kuwait",
    "Netherlands",
    "Singapore",
    "Sweden",
    "Switzerland",  # EWL (USD) preferred over Accumulating alternatives
    "Turkey",       # TUR (USD) preferred over Accumulating alternatives
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
