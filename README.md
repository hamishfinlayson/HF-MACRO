# HF Macro

Hamish Finlayson's macro terminal: a terminal-style dashboard for UK and US macro data, global markets, currencies, IMF world forecasts and economic news. Inspired by the Bloomberg Terminal. Built in Python with Streamlit.

## What's in it
| Code | Page | What's there |
|---|---|---|
| `HOME` | Home | US recession probability, risk-on/risk-off meter, calendar, headlines, watchlist, US/UK/EA scorecard |
| `US` | US | Jobs, claims, inflation, GDP, production, retail, sentiment, housing, trade, M2, credit spreads, rates |
| `UK` | UK | GDP, production, inflation, labour market, pay, retail, trade, Bank Rate, real rate, gilts |
| `EA` | Euro area | HICP and core inflation, unemployment, ECB rate, real rate, Euro Stoxx 50 |
| `MKT` | Markets | Key indices, VIX, oil, gas, gold, copper, copper/gold ratio |
| `WEI` | World equities | 23 global indices: 1D / 1W / 1M / YTD / 1Y with trend lines and a YTD ranking |
| `CMDTY` | Commodities | Energy, metals and agriculture futures performance |
| `FX` | FX | GBP snapshot, currency strength heatmap, 20 currency pairs |
| `GLOB` | Global | IMF world map, major economies, central bank rates board (BIS) |
| `CTRY` | Country | One-page profile for 20 economies: IMF data and forecasts, policy rate, currency, stock index, news |
| `NEWS` | News | FX snapshot, world growth, news search, live feeds by topic |
| `CRV` | Curves | US and UK yield curves, yield-curve recession signal |
| `CAL` | Calendar | Upcoming US releases, UK/Europe calendar links |
| `LAB` | Lab | Correlation and lead/lag explorer, Taylor rule, risk appetite breakdown |
| `PMI` | PMI | PMI headline figures (kept on your PC) |
| `HELP` | Help | Every code and ticker, data status, shading options |

## Getting around
- **Command line** at the top: type a ticker (`UKCPI`, `GBPUSD`, `BRENT`), a page code (`WEI`, `CTRY`), or any word (*inflation*, *gilt*, *yen*).
- **Click any card**, ticker-tape item or scorecard row to open it full screen.
- **Full-screen view**: period buttons, a date slider that refits the axis, chart type, views (change, y/y, averages), up to 3 overlays, rebase to 100, log scale, 11 shading options (recessions, Fed/BoE hiking and cutting cycles, curve inversions, bear markets, VIX stress, high inflation), target and custom level lines, event markers, news markers, biggest moves with matching headlines, forecast with confidence meter, stats, CSV download, pin to Home.
- **Drawing**: pick Line, Draw, Box or Circle under *Mouse*, then drag on the chart. Eraser and camera icons are top right of the chart.
- The address bar changes as you move, so you can bookmark any view.

---

## First-time setup on Windows

### 1. Put the folder somewhere sensible
Unzip into Documents, so you have `Documents\macro-monitor`.

### 2. Add your FRED key
Open `.streamlit\secrets.toml` in Notepad, replace `paste-your-key-here` with your key (keep the quote marks), save.

### 3. Install the libraries
In the `macro-monitor` folder, click the address bar, type `cmd`, press Enter, then run:
```
py -m pip install -r requirements.txt
```
**Run this again whenever `requirements.txt` changes** (it only installs what's new).

### 4. Open the dashboard
Double-click **`Open HF Macro.bat`**, or run `py -m streamlit run app.py`. Keep the black window open while you use it.

---

## Adding a new indicator
Open `indicators.py`. Each indicator is one `dict(...)` entry with a `ticker` you can search for. Copy one, change the details, save, and refresh the browser. Instructions are at the top of the file.

## How the analytics work
- **Forecasts**: an autoregressive model learns how each indicator usually moves on from its last two readings (last 25 years, pandemic months excluded), then runs 2,000 simulated futures. Dotted line = middle; band = 80% of outcomes. 12 months ahead (4 quarters for GDP).
- **Confidence (0-5 blocks)**: five related indicators (see `SIGNALS` in `indicators.py`) are checked over the last 6 months. Filled blocks = how many point the same way as the forecast.
- **Recession probability**: the New York Fed's published yield-curve model, P = N(-0.5333 - 0.6330 x (10y minus 3m spread)), giving the chance of a US recession 12 months ahead.
- **Scorecard percentile**: where today's reading sits in the last 20 years (0 = lowest, 100 = highest).
- **Lead/lag**: correlation between two indicators when one is shifted by up to 12 months.
- **Taylor rule**: rate = neutral real rate + inflation + w1 x (inflation - target) + w2 x (natural unemployment - unemployment).
- **Recessions**: US = official NBER dates. UK = 2+ quarters of falling GDP.
- **Risk appetite (0-100)**: VIX, high-yield spreads, copper/gold ratio, dollar index and the S&P 500's gap to its 200-day average, each compared with its last 3 years and averaged.
- **Currency strength**: % change in each currency's value against USD, GBP or EUR over 1D to 1Y.

Forecasts and models are for education only and are not financial advice.

## Files
| File | What it does |
|---|---|
| `app.py` | Navigation, command bar and every page |
| `ui.py` | The look: terminal styling, cards, ticker tape, charts, tables, status bar |
| `indicators.py` | Settings: indicators, tickers, signals, events, news feeds, IMF and calendar lists |
| `sources.py` | Downloads and tidies data (FRED, ONS, BoE, ECB, BIS, IMF, Yahoo, RSS and Google News, FX) |
| `forecast.py` | Forecasts, confidence ratings, shading rules, recession model, risk meter, lead/lag, Taylor rule |
| `data/pmi.csv` | PMI figures, added monthly (not uploaded to GitHub) |
| `data/watchlist.json` | Your pinned indicators (created automatically) |
| `.streamlit/config.toml` | Theme |
| `.streamlit/secrets.toml` | Your FRED key (private, never uploaded) |

## If something doesn't load
Every card, chart and page handles its own errors, so one broken source won't stop the rest.
- **"Add your FRED API key"**: step 2.
- **"Couldn't reach the data source"**: the site may be down; try again later.
- **"Data problem"**: a series code may have changed; check it on the source website.
- **News feeds unavailable**: listed under the headlines; the rest still show.

## Data sources and credits
FRED, Federal Reserve Bank of St. Louis (this product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis; some series are owned by third parties such as S&P and ICE) · Office for National Statistics, Open Government Licence v3.0 · Bank of England · European Central Bank · Bank for International Settlements · IMF DataMapper / World Economic Outlook · ECB reference rates via Frankfurter · Yahoo Finance via `yfinance` (unofficial) · headlines and links from public RSS feeds (BBC, Guardian, CNBC, Federal Reserve, Bank of England, ECB, IMF, WTO) and Google News search (personal, non-commercial use) · PMI: S&P Global and ISM headline releases, kept local.

Personal educational project. Not investment advice. Not affiliated with Bloomberg L.P.
