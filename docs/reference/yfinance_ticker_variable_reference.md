# yfinance Ticker Variable Reference

Last updated: 2026-03-05  
Project environment: `yfinance==1.2.0`

## Purpose

This document defines what can be pulled from a `yfinance.Ticker` object, what each field means, and how to read it with examples.

Notes:
- `fast_info` is a compact quote snapshot with relatively stable keys.
- `info` is a large Yahoo metadata dictionary; keys can differ by ticker and can be missing.
- Many items below are accessor methods that return tables, dictionaries, or series rather than scalar values.

## Quick Usage

```python
import yfinance as yf

t = yf.Ticker("SPXL.L")

fi = t.fast_info
meta = t.info
hist = t.history(period="1y", interval="1d")
```

## `fast_info` Variables (stable key set in this environment)

Each item below is typically read as `t.fast_info["<key>"]` or `t.fast_info.<property>`.

- `currency`: Trading currency for quote values. Example: `"GBp"` or `"USD"`.
- `day_high`: Highest trade/quote level in current session. Example: `103.25`.
- `day_low`: Lowest trade/quote level in current session. Example: `100.80`.
- `exchange`: Exchange code for listing venue. Example: `"LSE"`.
- `fifty_day_average`: Rolling 50-trading-day average price. Example: `97.41`.
- `last_price`: Latest known market price. Example: `101.55`.
- `last_volume`: Latest session volume. Example: `128734`.
- `market_cap`: Estimated market capitalization. Example: `2750000000`.
- `open`: Session open price. Example: `101.10`.
- `previous_close`: Prior session close. Example: `100.95`.
- `quote_type`: Instrument type. Example: `"ETF"` or `"EQUITY"`.
- `regular_market_previous_close`: Previous close in regular market context. Example: `100.95`.
- `shares`: Estimated shares outstanding from Yahoo fast path. Example: `24500000`.
- `ten_day_average_volume`: 10-session average volume. Example: `96500`.
- `three_month_average_volume`: 3-month average volume. Example: `105240`.
- `timezone`: Exchange timezone identifier. Example: `"Europe/London"`.
- `two_hundred_day_average`: Rolling 200-trading-day average price. Example: `92.18`.
- `year_change`: 1-year fractional change (not percent). Example: `0.118` means `11.8%`.
- `year_high`: 52-week high. Example: `106.72`.
- `year_low`: 52-week low. Example: `84.33`.

## Common `info` Variables Used in ETF Workflows

Read with `t.info.get("<key>")`.

- `longName`: Human-readable security name. Example: `"Direxion Daily S&P 500 Bull 3X Shares"`.
- `shortName`: Abbreviated security name. Example: `"Direxion S&P 500 Bull 3X"`.
- `symbol`: Ticker symbol. Example: `"SPXL.L"`.
- `quoteType`: Security class label. Example: `"ETF"`.
- `exchange`: Listing exchange code. Example: `"LSE"`.
- `currency`: Quote currency. Example: `"GBP"` or `"GBp"`.
- `country`: Issuer or listing country metadata. Example: `"United States"`.
- `sector`: Sector classification (mainly equities). Example: `"Financial Services"`.
- `industry`: Industry classification (mainly equities). Example: `"Asset Management"`.
- `website`: Issuer/fund website URL. Example: `"https://www.direxion.com"`.
- `marketCap`: Market capitalization. Example: `2750000000`.
- `enterpriseValue`: Enterprise value (mostly company equities). Example: `4200000000`.
- `sharesOutstanding`: Shares currently outstanding. Example: `24500000`.
- `floatShares`: Shares estimated as free float. Example: `23000000`.
- `averageVolume`: Typical trading volume. Example: `104300`.
- `averageVolume10days`: 10-day average volume. Example: `97500`.
- `fiftyTwoWeekHigh`: 52-week high. Example: `106.72`.
- `fiftyTwoWeekLow`: 52-week low. Example: `84.33`.
- `fiftyDayAverage`: 50-day moving average. Example: `97.41`.
- `twoHundredDayAverage`: 200-day moving average. Example: `92.18`.
- `beta`: Sensitivity to market benchmark (mostly equities). Example: `1.15`.
- `dividendYield`: Dividend yield as fraction. Example: `0.013` means `1.3%`.
- `trailingPE`: Trailing price/earnings ratio. Example: `21.8`.
- `forwardPE`: Forward price/earnings ratio estimate. Example: `19.4`.
- `bookValue`: Book value per share. Example: `12.75`.
- `priceToBook`: Price/book ratio. Example: `3.2`.
- `totalAssets`: ETF fund size/AUM-style field when available. Example: `1692662016`.
- `netAssets`: Alternative ETF asset-size field when `totalAssets` is missing. Example: `175565600`.
- `yield`: Fund/security yield (fraction). Example: `0.021` means `2.1%`.
- `fundFamily`: Fund sponsor family. Example: `"iShares"`.
- `category`: Fund category/classification. Example: `"Leveraged Equity"`.
- `navPrice`: Net asset value per share if provided. Example: `43.27`.
- `regularMarketPrice`: Current/last market price if provided. Example: `44.10`.
- `firstTradeDateEpochUtc`: First trade timestamp (epoch seconds). Example: `1133827200`.

## Ticker Accessors and Methods

These are public members available on `yfinance.Ticker` in this environment.

### Market History and Corporate Actions

- `history(...)`: OHLCV time series for a date range/period. Example: `t.history(period="5y", interval="1d")`.
- `get_history_metadata(...)`: Metadata about available history intervals/ranges. Example: `t.get_history_metadata()`.
- `history_metadata`: Property form of history metadata. Example: `t.history_metadata`.
- `actions`: Combined dividends/splits actions table. Example: `t.actions.tail()`.
- `get_actions(...)`: Method form of actions retrieval. Example: `t.get_actions()`.
- `dividends`: Dividend cash series. Example: `t.dividends.tail()`.
- `get_dividends(...)`: Method form of dividends retrieval. Example: `t.get_dividends()`.
- `splits`: Stock split ratio series. Example: `t.splits.tail()`.
- `get_splits(...)`: Method form of splits retrieval. Example: `t.get_splits()`.
- `capital_gains`: Capital gains distribution series (funds where available). Example: `t.capital_gains`.
- `get_capital_gains(...)`: Method form of capital gains retrieval. Example: `t.get_capital_gains()`.

### Quote and Metadata

- `info`: Large Yahoo metadata dictionary. Example: `t.info.get("quoteType")`.
- `get_info(...)`: Method form for info retrieval. Example: `t.get_info()`.
- `fast_info`: Lightweight quote snapshot. Example: `t.fast_info["last_price"]`.
- `get_fast_info(...)`: Method form for fast info retrieval. Example: `t.get_fast_info()`.
- `isin`: International Security Identification Number when available. Example: `t.isin`.
- `get_isin(...)`: Method form of ISIN retrieval. Example: `t.get_isin()`.
- `news`: Recent news item list. Example: `t.news[:3]`.
- `get_news(...)`: Method form of news retrieval. Example: `t.get_news()`.
- `live`: Streaming-style quote helper object in this version. Example: `t.live`.

### Options

- `options`: Available options expiration dates. Example: `t.options`.
- `option_chain(...)`: Option chains for a selected expiry. Example: `t.option_chain(t.options[0])`.

### Holders and Ownership

- `major_holders`: Major holder summary table. Example: `t.major_holders`.
- `get_major_holders(...)`: Method form of major holders retrieval. Example: `t.get_major_holders()`.
- `institutional_holders`: Institutional holder table. Example: `t.institutional_holders`.
- `get_institutional_holders(...)`: Method form of institutional holders retrieval. Example: `t.get_institutional_holders()`.
- `mutualfund_holders`: Mutual fund holder table. Example: `t.mutualfund_holders`.
- `get_mutualfund_holders(...)`: Method form of mutual fund holder retrieval. Example: `t.get_mutualfund_holders()`.
- `insider_transactions`: Insider transaction history. Example: `t.insider_transactions`.
- `get_insider_transactions(...)`: Method form of insider transactions retrieval. Example: `t.get_insider_transactions()`.
- `insider_purchases`: Insider purchase summary. Example: `t.insider_purchases`.
- `get_insider_purchases(...)`: Method form of insider purchases retrieval. Example: `t.get_insider_purchases()`.
- `insider_roster_holders`: Insider roster table. Example: `t.insider_roster_holders`.
- `get_insider_roster_holders(...)`: Method form of insider roster retrieval. Example: `t.get_insider_roster_holders()`.

### Financial Statements (Annual)

- `financials`: Annual income statement-style table (legacy alias behavior). Example: `t.financials`.
- `get_financials(...)`: Method form of `financials`. Example: `t.get_financials()`.
- `income_stmt`: Annual income statement table. Example: `t.income_stmt`.
- `get_income_stmt(...)`: Method form of income statement retrieval. Example: `t.get_income_stmt()`.
- `incomestmt`: Alias of `income_stmt`. Example: `t.incomestmt`.
- `get_incomestmt(...)`: Alias method for income statement retrieval. Example: `t.get_incomestmt()`.
- `balance_sheet`: Annual balance sheet table. Example: `t.balance_sheet`.
- `get_balance_sheet(...)`: Method form of balance sheet retrieval. Example: `t.get_balance_sheet()`.
- `balancesheet`: Alias of `balance_sheet`. Example: `t.balancesheet`.
- `get_balancesheet(...)`: Alias method for balance sheet retrieval. Example: `t.get_balancesheet()`.
- `cash_flow`: Annual cash flow table. Example: `t.cash_flow`.
- `get_cash_flow(...)`: Method form of cash flow retrieval. Example: `t.get_cash_flow()`.
- `cashflow`: Alias of `cash_flow`. Example: `t.cashflow`.
- `get_cashflow(...)`: Alias method for cash flow retrieval. Example: `t.get_cashflow()`.

### Financial Statements (Quarterly and TTM)

- `quarterly_financials`: Quarterly income statement-style table. Example: `t.quarterly_financials`.
- `quarterly_income_stmt`: Quarterly income statement table. Example: `t.quarterly_income_stmt`.
- `quarterly_incomestmt`: Alias of quarterly income statement. Example: `t.quarterly_incomestmt`.
- `quarterly_balance_sheet`: Quarterly balance sheet table. Example: `t.quarterly_balance_sheet`.
- `quarterly_balancesheet`: Alias of quarterly balance sheet. Example: `t.quarterly_balancesheet`.
- `quarterly_cash_flow`: Quarterly cash flow table. Example: `t.quarterly_cash_flow`.
- `quarterly_cashflow`: Alias of quarterly cash flow. Example: `t.quarterly_cashflow`.
- `ttm_financials`: Trailing-twelve-month financials table. Example: `t.ttm_financials`.
- `ttm_income_stmt`: TTM income statement table. Example: `t.ttm_income_stmt`.
- `ttm_incomestmt`: Alias of TTM income statement. Example: `t.ttm_incomestmt`.
- `ttm_cash_flow`: TTM cash flow table. Example: `t.ttm_cash_flow`.
- `ttm_cashflow`: Alias of TTM cash flow. Example: `t.ttm_cashflow`.
- `quarterly_earnings`: Quarterly earnings table. Example: `t.quarterly_earnings`.

### Earnings, Estimates, and Analyst Data

- `earnings`: Earnings table (annual/summary form depending on ticker). Example: `t.earnings`.
- `get_earnings(...)`: Method form of earnings retrieval. Example: `t.get_earnings()`.
- `earnings_history`: Historical earnings surprises table. Example: `t.earnings_history`.
- `get_earnings_history(...)`: Method form of earnings history retrieval. Example: `t.get_earnings_history()`.
- `earnings_dates`: Upcoming/recent earnings dates. Example: `t.earnings_dates`.
- `get_earnings_dates(...)`: Method form of earnings dates retrieval. Example: `t.get_earnings_dates()`.
- `earnings_estimate`: Analyst earnings estimate table. Example: `t.earnings_estimate`.
- `get_earnings_estimate(...)`: Method form of earnings estimate retrieval. Example: `t.get_earnings_estimate()`.
- `revenue_estimate`: Analyst revenue estimate table. Example: `t.revenue_estimate`.
- `get_revenue_estimate(...)`: Method form of revenue estimate retrieval. Example: `t.get_revenue_estimate()`.
- `eps_trend`: EPS trend table. Example: `t.eps_trend`.
- `get_eps_trend(...)`: Method form of EPS trend retrieval. Example: `t.get_eps_trend()`.
- `eps_revisions`: EPS revisions table. Example: `t.eps_revisions`.
- `get_eps_revisions(...)`: Method form of EPS revisions retrieval. Example: `t.get_eps_revisions()`.
- `growth_estimates`: Growth estimate table. Example: `t.growth_estimates`.
- `get_growth_estimates(...)`: Method form of growth estimate retrieval. Example: `t.get_growth_estimates()`.
- `recommendations`: Analyst recommendation history table. Example: `t.recommendations`.
- `get_recommendations(...)`: Method form of recommendations retrieval. Example: `t.get_recommendations()`.
- `recommendations_summary`: Aggregated recommendation counts. Example: `t.recommendations_summary`.
- `get_recommendations_summary(...)`: Method form of recommendations summary retrieval. Example: `t.get_recommendations_summary()`.
- `analyst_price_targets`: Analyst target price summary. Example: `t.analyst_price_targets`.
- `get_analyst_price_targets(...)`: Method form of analyst target retrieval. Example: `t.get_analyst_price_targets()`.
- `upgrades_downgrades`: Broker rating change history. Example: `t.upgrades_downgrades`.
- `get_upgrades_downgrades(...)`: Method form of upgrades/downgrades retrieval. Example: `t.get_upgrades_downgrades()`.

### Shares, Filings, Funds, and Sustainability

- `shares`: Share-count history/snapshot table. Example: `t.shares`.
- `get_shares(...)`: Method form of shares retrieval. Example: `t.get_shares()`.
- `get_shares_full(...)`: Extended shares history retrieval. Example: `t.get_shares_full(start="2018-01-01")`.
- `sec_filings`: SEC filings table/list where available. Example: `t.sec_filings`.
- `get_sec_filings(...)`: Method form of SEC filings retrieval. Example: `t.get_sec_filings()`.
- `funds_data`: Fund-oriented data block for ETF/mutual fund tickers. Example: `t.funds_data`.
- `get_funds_data(...)`: Method form of funds data retrieval. Example: `t.get_funds_data()`.
- `sustainability`: ESG/sustainability metrics table where available. Example: `t.sustainability`.
- `get_sustainability(...)`: Method form of sustainability retrieval. Example: `t.get_sustainability()`.
- `calendar`: Calendar events (earnings/dividend dates depending on ticker). Example: `t.calendar`.
- `get_calendar(...)`: Method form of calendar retrieval. Example: `t.get_calendar()`.

## Reliability Guidance

- Treat all Yahoo responses as untrusted and incomplete.
- Missing keys in `info` are normal; always access via `.get(...)`.
- Data definitions differ by instrument type (`ETF`, `EQUITY`, `INDEX`, etc.).
- Field semantics can drift over time with Yahoo upstream changes.

