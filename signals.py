"""
signals.py - SIGNAL LAB (PC version only).

Every idea for predicting next week's direction is an "ingredient": a number for each asset each
Friday, where a higher number means "more likely to go up". Each ingredient only uses information
that was really available on that Friday.

The Signal Lab tests every ingredient the same way:
  1. Direction: when it says up, does the price go up more often than a coin toss (50%)?
  2. Edge: if you bet in its direction each week (bigger bets when it is more confident), what do you make?
  3. Discovery vs unseen: the test period is split. The first part (discovery) is where we are allowed
     to look; the last part (unseen) is only for confirming. An idea only counts if it works in both.
  4. Adds to model: does the combined model do better with it than without it? (see model.py)
Failures get a plain-English "why it failed" note, so we learn from them.

Just for fun and learning. Not financial advice.
"""

import io
import os
import time as _time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent / "data" / "cache"
UA = {"User-Agent": "HF-Macro/1.2 (personal educational dashboard) python-requests"}
STATUS = {}            # data source -> (ok?, message)


def _status(name, ok, msg):
    STATUS[name] = (bool(ok), str(msg)[:300])


def get_key(name):
    """Reads an API key from .streamlit/secrets.toml (or an environment variable)."""
    try:
        import streamlit as st
        key = st.secrets[name]
    except Exception:
        key = os.environ.get(name, "")
    key = str(key or "").strip()
    return key if key and "paste" not in key else None


def _disk_cache(name, max_age_hours, fn):
    """Runs fn() at most every max_age_hours and keeps the result on disk (old copy used if the download fails)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.pkl"
    old = None
    if path.exists():
        try:
            old = pd.read_pickle(path)
            if _time.time() - path.stat().st_mtime < max_age_hours * 3600:
                return old
        except Exception:
            old = None
    try:
        value = fn()
        pd.to_pickle(value, path)
        return value
    except Exception:
        if old is not None:
            return old
        raise


# ================================================================= calendar

# FOMC (US Federal Reserve) rate decision days: the last day of each scheduled meeting, plus the 2020 emergency cuts.
# Source: federalreserve.gov meeting calendars and press releases.
FOMC = pd.to_datetime([
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-03-03", "2020-03-15", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05",
    "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
])


def cpi_dates():
    """US CPI release days from FRED (release 10). Falls back to 'around the 10th-15th of each month'."""
    key = get_key("FRED_API_KEY")

    def fetch():
        r = requests.get("https://api.stlouisfed.org/fred/release/dates",
                         params={"release_id": 10, "api_key": key, "file_type": "json", "limit": 1000,
                                 "include_release_dates_with_no_data": "true", "sort_order": "asc"},
                         headers=UA, timeout=20)
        r.raise_for_status()
        d = pd.to_datetime([x["date"] for x in r.json().get("release_dates", [])])
        if len(d) < 50:
            raise ValueError("too few CPI dates")
        return pd.DatetimeIndex(d)

    try:
        if not key:
            raise ValueError("no FRED key")
        d = _disk_cache("cpi_dates", 24 * 7, fetch)
        _status("CPI release dates (FRED)", True, f"{len(d)} release days")
        return d
    except Exception as exc:
        _status("CPI release dates (FRED)", False, f"using approximate dates ({exc})")
        months = pd.date_range("2014-01-01", "2028-01-01", freq="MS")
        return pd.DatetimeIndex(months + pd.Timedelta(days=11))


def calendar_flags(fridays, cpi):
    """0/1 flags for the week AFTER each Friday (the week being predicted). Dates are known in advance."""
    out = {}
    nxt = [(t + pd.Timedelta(days=1), t + pd.Timedelta(days=7)) for t in fridays]
    def has(days):
        days = pd.DatetimeIndex(days).sort_values()
        return pd.Series([float(((days >= a) & (days <= b)).any()) for a, b in nxt], index=fridays)
    out["fomc_next"] = has(FOMC)
    out["cpi_next"] = has(cpi)
    month_ends = pd.date_range(fridays.min() - pd.Timedelta(days=40), fridays.max() + pd.Timedelta(days=40), freq="BME")
    firsts = pd.date_range(fridays.min() - pd.Timedelta(days=40), fridays.max() + pd.Timedelta(days=40), freq="BMS")
    out["month_end_next"] = has(month_ends)
    out["turn_of_month"] = has(list(month_ends) + list(firsts) + list(firsts + pd.offsets.BDay(1)))
    third_fri = pd.date_range(fridays.min() - pd.Timedelta(days=40), fridays.max() + pd.Timedelta(days=40), freq="WOM-3FRI")
    out["opex_next"] = has(third_fri)
    return out


# ================================================================= cross-asset factors

FACTOR_TICKERS = {"vix": "^VIX", "copper": "HG=F", "gold": "GC=F", "oil": "CL=F", "dollar": "DX-Y.NYB", "spx": "^GSPC"}
FRED_FACTORS = {"us2y": "DGS2", "credit": "BAMLH0A0HYM2"}


def load_factors():
    """Daily VIX, copper, gold, oil, dollar index, S&P 500 (Yahoo) and US 2-year yield, junk-bond spread (FRED)."""
    import assetlab
    frames = {}
    try:
        px = _disk_cache("factors_yahoo", 12, lambda: assetlab.download_prices(tuple(FACTOR_TICKERS.values())))
        for k, t in FACTOR_TICKERS.items():
            if t in px.columns:
                frames[k] = px[t]
        _status("Cross-asset prices (Yahoo)", True, f"{len(frames)} of {len(FACTOR_TICKERS)} series")
    except Exception as exc:
        _status("Cross-asset prices (Yahoo)", False, exc)
    key = get_key("FRED_API_KEY")
    for k, code in FRED_FACTORS.items():
        try:
            def fetch(code=code):
                r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                                 params={"series_id": code, "api_key": key, "file_type": "json",
                                         "observation_start": "2012-01-01"}, headers=UA, timeout=20)
                r.raise_for_status()
                obs = r.json()["observations"]
                s = pd.Series({pd.Timestamp(o["date"]): pd.to_numeric(o["value"], errors="coerce") for o in obs})
                return s.dropna()
            if not key:
                raise ValueError("no FRED key")
            s = _disk_cache(f"fred_{code}", 12, fetch)
            s.index = s.index + pd.Timedelta(days=1)            # a day's value is published the next day
            frames[k] = s
            _status(f"FRED {code}", True, f"{len(s)} days")
        except Exception as exc:
            _status(f"FRED {code}", False, exc)
    if not frames:
        return pd.DataFrame()
    return pd.DataFrame(frames).sort_index()


# ================================================================= CFTC Commitments of Traders (hedge fund positioning)

# CFTC market code and name words for each currency / asset (futures). Speculators = "non-commercial" traders.
COT_MARKETS = {
    "GBP": ("096742", ["BRITISH POUND"]), "EUR": ("099741", ["EURO FX"]), "JPY": ("097741", ["JAPANESE YEN"]),
    "CHF": ("092741", ["SWISS FRANC"]), "AUD": ("232741", ["AUSTRALIAN DOLLAR"]),
    "CAD": ("090741", ["CANADIAN DOLLAR"]), "NZD": ("112741", ["NZ DOLLAR", "NEW ZEALAND"]),
    "MXN": ("095741", ["MEXICAN PESO"]), "ZAR": ("122741", ["SO AFRICAN RAND", "SOUTH AFRICAN RAND"]),
    "USD": ("098662", ["U.S. DOLLAR INDEX", "USD INDEX"]),
    "BTC": ("133741", ["BITCOIN - CHICAGO"]), "ETH": ("146021", ["ETHER CASH SETTLED", "ETHER -"]),
    "GC=F": ("088691", ["GOLD - COMMODITY"]), "SI=F": ("084691", ["SILVER - COMMODITY"]),
    "HG=F": ("085692", ["COPPER"]), "PL=F": ("076651", ["PLATINUM"]),
    "CL=F": ("067651", ["CRUDE OIL, LIGHT SWEET", "WTI-PHYSICAL", "WTI FINANCIAL"]),
    "NG=F": ("023651", ["NATURAL GAS (NYME", "NAT GAS NYME", "HENRY HUB - NEW YORK MERC"]),
    "RB=F": ("111659", ["GASOLINE BLENDSTOCK", "GASOLINE RBOB", "RBOB"]),
    "HO=F": ("022651", ["NY HARBOR ULSD", "#2 HEATING OIL"]),
    "ZW=F": ("001602", ["WHEAT-SRW", "WHEAT - CHICAGO"]), "ZC=F": ("002602", ["CORN - CHICAGO"]),
    "ZS=F": ("005602", ["SOYBEANS - CHICAGO"]), "KC=F": ("083731", ["COFFEE C"]),
    "SB=F": ("080732", ["SUGAR NO. 11"]), "CC=F": ("073732", ["COCOA - ICE"]),
    "CT=F": ("033661", ["COTTON NO. 2"]), "LE=F": ("057642", ["LIVE CATTLE"]),
    "^GSPC": ("13874A", ["E-MINI S&P 500 -", "E-MINI S&P 500 STOCK"]), "^IXIC": ("209742", ["NASDAQ MINI", "NASDAQ-100 STOCK INDEX (MINI)"]),
    "^DJI": ("124603", ["DJIA x $5", "DOW JONES INDUSTRIAL AVG- x $5"]), "^RUT": ("239742", ["RUSSELL E-MINI", "E-MINI RUSSELL 2000"]),
    "^N225": ("240741", ["NIKKEI STOCK AVERAGE YEN"]),
}
COT_ALIAS = {"BZ=F": "CL=F", "BTC-USD": "BTC", "ETH-USD": "ETH"}


def _norm(c):
    return "".join(ch for ch in str(c).lower() if ch.isalnum())


def parse_cot(df):
    """Any CFTC legacy table (API or yearly file) -> date, code, name, speculators' net position as % of open interest."""
    cols = {c: _norm(c) for c in df.columns}
    bad = ("old", "other", "pct", "change", "spread", "trader", "conc", "chg")
    def find(*must, avoid=bad):
        for c, n in cols.items():
            if all(m in n for m in must) and not any(a in n for a in avoid):
                return c
        return None
    date = find("yyyy", avoid=("old", "other")) or find("date", avoid=("old", "other", "yymmdd"))
    code = find("contract", "code") or find("marketcode")
    name = find("market", "name") or find("exchange", "name")
    long_ = find("noncomm", "long", "all")
    short = find("noncomm", "short", "all")
    oi = find("openinterest", "all")
    if not all([date, code, long_, short, oi]):
        raise ValueError(f"COT columns not recognised: {list(df.columns)[:12]}")
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date].astype(str).str[:10], errors="coerce"),
        "code": df[code].astype(str).str.strip().str.upper(),
        "name": df[name].astype(str).str.upper() if name else "",
        "long": pd.to_numeric(df[long_], errors="coerce"), "short": pd.to_numeric(df[short], errors="coerce"),
        "oi": pd.to_numeric(df[oi], errors="coerce")}).dropna(subset=["date", "long", "short", "oi"])
    out = out[out["oi"] > 0]
    out["net_pct"] = (out["long"] - out["short"]) / out["oi"] * 100
    return out


def _cot_download():
    codes = sorted({v[0] for v in COT_MARKETS.values()})
    try:
        where = "cftc_contract_market_code in(" + ",".join(f"'{c}'" for c in codes) + ") AND report_date_as_yyyy_mm_dd >= '2014-01-01'"
        r = requests.get("https://publicreporting.cftc.gov/resource/6dca-aqww.json",
                         params={"$where": where, "$limit": 200000}, headers=UA, timeout=60)
        r.raise_for_status()
        data = parse_cot(pd.DataFrame(r.json()))
        if len(data) > 500:
            return data, "CFTC public reporting API"
    except Exception as exc:
        first_error = exc
    else:
        first_error = "too few rows"
    parts = []
    for year in range(2014, pd.Timestamp.now().year + 1):
        try:
            r = requests.get(f"https://www.cftc.gov/files/dea/history/deacot{year}.zip", headers=UA, timeout=60)
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
            with z.open(z.namelist()[0]) as f:
                parts.append(parse_cot(pd.read_csv(f, low_memory=False)))
        except Exception:
            continue
    if not parts:
        raise ValueError(f"CFTC download failed ({first_error})")
    return pd.concat(parts, ignore_index=True), "CFTC yearly files"


def load_cot():
    """Weekly speculator positioning (% of open interest), one column per currency/asset, dated when it was PUBLISHED."""
    try:
        raw, src = _disk_cache("cot", 24 * 3, _cot_download)
    except Exception as exc:
        _status("CFTC positioning", False, exc)
        return pd.DataFrame()
    out = {}
    for key, (code, names) in COT_MARKETS.items():
        rows = raw[raw["code"] == code]
        if rows.empty:
            for n in names:
                cand = raw[raw["name"].str.contains(n, regex=False, na=False)]
                if not cand.empty:
                    best = cand["code"].value_counts().index[0]
                    rows = cand[cand["code"] == best]
                    break
        if rows.empty:
            continue
        s = rows.groupby("date")["net_pct"].mean().sort_index()
        # Positions are as of Tuesday and published Friday afternoon (US time). To be safe we treat each
        # report as usable only from the FOLLOWING Friday.
        s.index = s.index + pd.Timedelta(days=4)
        out[key] = s
    _status("CFTC positioning", bool(out), f"{len(out)} of {len(COT_MARKETS)} markets from {src}")
    return pd.DataFrame(out).sort_index()


# ================================================================= EIA weekly inventories

EIA_SERIES = {  # name: (API route, series id, assets it affects)
    "crude": ("petroleum/stoc/wstk", "WCESTUS1", ["CL=F", "BZ=F"]),
    "gasoline": ("petroleum/stoc/wstk", "WGTSTUS1", ["RB=F"]),
    "distillate": ("petroleum/stoc/wstk", "WDISTUS1", ["HO=F"]),
    "natgas": ("natural-gas/stor/wkly", "NW2_EPG0_SWO_R48_BCF", ["NG=F"]),
}


def parse_eia(payload):
    rows = payload.get("response", {}).get("data", [])
    s = pd.Series({pd.Timestamp(r["period"]): pd.to_numeric(r.get("value"), errors="coerce") for r in rows})
    return s.dropna().sort_index()


def load_eia():
    """Weekly US oil product and gas inventories. Each week's figure is released the following Wednesday."""
    key = get_key("EIA_API_KEY")
    if not key:
        _status("EIA inventories", False, "no EIA_API_KEY in secrets.toml")
        return {}
    out, errors = {}, []
    for name, (route, sid, _) in EIA_SERIES.items():
        def fetch(route=route, sid=sid):
            r = requests.get(f"https://api.eia.gov/v2/{route}/data/",
                             params={"api_key": key, "frequency": "weekly", "data[0]": "value",
                                     "facets[series][]": sid, "start": "2010-01-01",
                                     "sort[0][column]": "period", "sort[0][direction]": "asc", "length": 5000},
                             headers=UA, timeout=30)
            r.raise_for_status()
            s = parse_eia(r.json())
            if len(s) < 100:
                raise ValueError(f"{sid}: only {len(s)} weeks")
            return s
        try:
            s = _disk_cache(f"eia_{sid}", 24, fetch)
            s.index = s.index + pd.Timedelta(days=7)        # usable from the Friday after release
            out[name] = s
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    _status("EIA inventories", bool(out), f"{len(out)} of {len(EIA_SERIES)} series" + (f" ({'; '.join(errors)})" if errors else ""))
    return out


def inventory_surprise(s):
    """This week's change minus the usual change for this time of year (average of the previous 5 years)."""
    chg = s.diff()
    woy = chg.index.isocalendar().week.values
    out = pd.Series(np.nan, index=chg.index)
    for i, (d, v) in enumerate(chg.items()):
        past = chg[(chg.index < d - pd.Timedelta(days=300)) & (chg.index >= d - pd.Timedelta(days=5 * 366))]
        same = past[np.abs(past.index.isocalendar().week.values.astype(int) - int(woy[i])) <= 1]
        if len(same) >= 4:
            out[d] = v - same.mean()
    return out


# ================================================================= the ingredients

FAMILIES = {
    "Price patterns": "Patterns in the asset's own price and volume.",
    "Cross-asset": "Moves in other markets that might lead this one (each asset learns its own link from the past).",
    "Interest rates": "Currencies and the interest rates behind them.",
    "Positioning": "What hedge funds and other speculators are already betting on (CFTC weekly report).",
    "Inventories": "How full US oil and gas storage is compared with normal (EIA weekly report).",
    "Calendar": "Known events in the week ahead.",
    "Company data": "Earnings, analysts, directors and company accounts (needs your API keys).",
    "Chart patterns": "Shapes in the price chart: seasons, trend quality, streaks, and whether this asset trends or snaps back.",
    "Context": "Market conditions the machine-learning model can combine with other ingredients (not tested alone).",
}

# key: (name, family, what it measures, why it might work)
INGREDIENTS = {
    "mom_1m": ("1-month momentum", "Price patterns", "% change over the last month.",
               "Short-term trends can carry on as news is slowly priced in."),
    "mom_3m": ("3-month momentum", "Price patterns", "% change over the last 3 months.",
               "Trends over a few months are one of the most studied effects in finance."),
    "mom_6m": ("6-month momentum", "Price patterns", "% change over the last 6 months.", "As above, longer trend."),
    "mom_12_1": ("12-1 momentum", "Price patterns", "% change from 12 months ago to 1 month ago (skips the last month).",
                 "The classic academic momentum signal; skipping the last month avoids short-term reversals."),
    "ma_cross": ("Moving-average gap", "Price patterns", "How far the 50-day average is above the 200-day average.",
                 "The 'golden cross' that trend followers watch; when lots of people use it, it can move prices."),
    "high52": ("Near 52-week high", "Price patterns", "How close the price is to its 52-week high (0 = at the high).",
               "Investors hesitate to buy at highs ('anchoring'), so good news is priced in slowly near them."),
    "rsi_rev": ("RSI overstretch (reversal)", "Price patterns", "Minus the 14-day RSI gap from 50: positive when oversold.",
                "Prices that rose or fell too fast often snap back a little."),
    "rev_1w": ("Last week reversal", "Price patterns", "Minus last week's return.",
               "Over-reaction: last week's big movers often give some of it back."),
    "squeeze": ("Volatility squeeze", "Price patterns", "How calm the last month was vs the last year, times the trend direction.",
                "Calm spells often end in a big move, usually in the direction of the trend."),
    "volume": ("Volume confirmation", "Price patterns", "Last week's trading volume vs normal, times the direction of last week's move.",
               "A move on heavy volume is 'real' and may continue; on light volume it may fade."),
    "gap_fill": ("Gap fill", "Price patterns", "Minus the overnight jumps over the last week.",
                 "Prices that jump at the open often drift back to fill the gap."),
    "breakout": ("20-day breakout", "Price patterns", "Where the price sits in its 20-day range (+1 = at the top, -1 = at the bottom).",
                 "Breakouts from a range are the classic 'turtle trader' rule."),
    "x_vix": ("VIX link", "Cross-asset", "4-week change in the VIX (fear index), times this asset's past reaction to it.",
              "Fear spikes hit risky assets and help safe havens, sometimes with a delay."),
    "x_copper_gold": ("Copper/gold ratio link", "Cross-asset", "4-week change in copper vs gold, times this asset's past reaction.",
                      "Copper rises with growth, gold with fear: the ratio is a growth gauge."),
    "x_oil": ("Oil link", "Cross-asset", "4-week change in oil, times this asset's past reaction.",
              "Oil feeds into oil currencies (NOK, CAD), oil companies and inflation."),
    "x_dollar": ("Dollar link", "Cross-asset", "4-week change in the dollar index, times this asset's past reaction.",
                 "A strong dollar squeezes commodities and emerging markets."),
    "x_us2y": ("US 2-year yield link", "Cross-asset", "4-week change in the US 2-year yield, times this asset's past reaction.",
               "The 2-year yield tracks expected Fed rates, which move currencies and growth stocks."),
    "x_credit": ("Credit spread link", "Cross-asset", "4-week change in the junk-bond spread, times this asset's past reaction.",
                 "Bond investors often spot trouble before stock investors."),
    "x_spx": ("S&P 500 link", "Cross-asset", "4-week change in the S&P 500, times this asset's past reaction.",
              "Some markets follow the US with a delay."),
    "carry": ("FX carry", "Interest rates", "Interest rate of the first currency minus the second (central bank rates).",
              "You earn the interest gap by holding the higher-rate currency; it has paid over decades (with crashes)."),
    "rate_change": ("Rate gap change", "Interest rates", "Change in the interest rate gap over the last 3 months.",
                    "Currencies follow where rates are heading, not just where they are."),
    "cot_crowd": ("Positioning extreme (contrarian)", "Positioning", "Minus how extreme speculators' net position is vs the last 3 years.",
                  "When everyone is already in a trade there's nobody left to buy, so extremes tend to reverse."),
    "cot_flow": ("Positioning flow", "Positioning", "Change in speculators' net position over the last 4 weeks.",
                 "Big funds build positions over weeks, which can keep pushing the price."),
    "eia_surprise": ("Inventory surprise", "Inventories", "Minus the latest weekly inventory change vs normal for the time of year.",
                     "Stocks falling faster than normal means tight supply, which pushes prices up."),
    "fomc_next": ("Fed decision next week", "Calendar", "1 if the Fed announces rates next week.",
                  "Studies found stocks drift up before Fed decisions; volatility changes around them."),
    "cpi_next": ("US inflation data next week", "Calendar", "1 if US CPI is released next week.",
                 "Big data releases change risk appetite and the dollar."),
    "turn_of_month": ("Turn of the month", "Calendar", "1 if next week includes the last or first trading days of a month.",
                      "Salaries and pension money arriving at month end push stocks up around the turn of the month."),
    "opex_next": ("Options expiry week", "Calendar", "1 if next Friday is the monthly options expiry (third Friday).",
                  "Dealers hedging options can pin or push prices in expiry week."),
    "rebalance": ("Month-end rebalancing", "Calendar", "If next week is month end: minus this month's move so far.",
                  "Big funds sell what went up and buy what went down at month end to rebalance."),
    "seasonal": ("Seasonal pattern", "Chart patterns", "How this asset did in the same calendar month in previous years.",
                 "Harvests, heating season, driving season and year-end flows repeat every year, especially in commodities."),
    "trend_quality": ("Trend quality", "Chart patterns", "12-week move divided by all the up-and-down wiggles along the way "
                      "(+1 = a perfectly smooth rise, -1 = a smooth fall).",
                      "Smooth trends tend to carry on; choppy ones don't."),
    "regime_follow": ("Trend-or-snap-back regime", "Chart patterns", "If this asset's weekly moves have tended to continue "
                      "lately, follow last week's move; if they've tended to reverse, bet against it.",
                      "Some markets trend and some snap back, and it changes over time: this follows whichever is working."),
    "streak": ("Up/down streak", "Chart patterns", "How many weeks in a row it has risen (+) or fallen (-), up to 6.",
               "Long streaks show strong one-way pressure, but can also mean it's overstretched: the test tells us which."),
    "off_low": ("Distance from 52-week low", "Chart patterns", "How far above its lowest price of the last year (in %).",
                "Assets that have bounced well off their lows have buyers stepping in."),
    "ctx_vix": ("Market fear level (VIX)", "Context", "How high the VIX is vs the last 2 years (machine-learning model only).",
                "Lets the model learn rules like 'momentum works when markets are calm'."),
    "ctx_vol": ("Asset's own volatility", "Context", "How wild this asset is right now vs its last 2 years (machine-learning model only).",
                "Lets the model learn that some ingredients only work in calm or wild spells."),
}
CALENDAR_KEYS = ["fomc_next", "cpi_next", "turn_of_month", "opex_next"]       # 0/1 flags (not z-scored)
FLAG_KEYS = set(CALENDAR_KEYS)          # 0/1 flags: centred, not z-scored
XS_KEYS = set()                         # compared ACROSS companies each week (e.g. cheap vs expensive), not over time


def zscore_xs(df):
    """Each week, rank the assets against each other and turn the rank into a score from about -1.7 to +1.7."""
    r = df.rank(axis=1, pct=True)
    n = df.notna().sum(axis=1)
    out = (r - 0.5) * np.sqrt(12)
    out.loc[n < 5] = np.nan
    return out


def zscore_ts(df, window=104, min_periods=26):
    """How unusual each value is vs that asset's own past 2 years (only past data). Clipped at +-3."""
    m = df.rolling(window, min_periods=min_periods).mean()
    s = df.rolling(window, min_periods=min_periods).std()
    return ((df - m) / s.where(s > 0)).clip(-3, 3)


def _rsi(daily, n=14):
    d = daily.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def lead_lag(R, factor_weekly, window=104, min_periods=52):
    """
    For each asset: how its weekly return reacted to the factor's 4-week change the week BEFORE
    (a rolling regression on the past 2 years), times the factor's latest 4-week change.
    """
    f4 = factor_weekly.reindex(R.index).ffill(limit=2)
    f4 = f4 - f4.shift(4)
    x = f4.shift(1)
    mx = x.rolling(window, min_periods=min_periods).mean()
    vx = x.rolling(window, min_periods=min_periods).var()
    mr = R.rolling(window, min_periods=min_periods).mean()
    mrx = R.mul(x, axis=0).rolling(window, min_periods=min_periods).mean()
    beta = (mrx - mr.mul(mx, axis=0)).div(vx.where(vx > 0), axis=0)
    return beta.mul(f4, axis=0)


def _pair_ccy(ticker):
    t = ticker.replace("=X", "")
    return (t[:3], t[3:6]) if len(t) >= 6 else (None, None)


def build_ingredients(cls, prices, ohlc, ctx):
    """
    All ingredients for one asset class. Returns (raw scores, z-scores, W, R, F, weekly volatility),
    every table indexed by Friday with one column per asset. Positive = expect up.
    """
    prices = prices.dropna(axis=1, how="all")
    daily = prices.ffill(limit=5)
    W = prices.resample("W-FRI").last()
    W = W[W.index <= prices.index.max()]          # drop an unfinished week (e.g. when run on a Monday)
    R = W.pct_change(fill_method=None) * 100
    F = R.shift(-1)
    at = lambda df: df.resample("W-FRI").last().reindex(W.index)
    lr = np.log(daily).diff()
    vol_w = at(lr.rolling(60, min_periods=40).std() * np.sqrt(5) * 100)       # typical weekly move, %
    raw = {}
    raw["mom_1m"] = at(daily / daily.shift(21) - 1) * 100
    raw["mom_3m"] = at(daily / daily.shift(63) - 1) * 100
    raw["mom_6m"] = at(daily / daily.shift(126) - 1) * 100
    raw["mom_12_1"] = at(daily.shift(21) / daily.shift(252) - 1) * 100
    raw["ma_cross"] = at(daily.rolling(50, min_periods=40).mean() / daily.rolling(200, min_periods=150).mean() - 1) * 100
    raw["high52"] = at(daily / daily.rolling(252, min_periods=200).max() - 1) * 100
    raw["rsi_rev"] = -(at(_rsi(daily)) - 50)
    raw["rev_1w"] = -R
    bw = lr.rolling(20, min_periods=15).std()
    bw_z = (bw - bw.rolling(252, min_periods=150).mean()) / bw.rolling(252, min_periods=150).std()
    raw["squeeze"] = at(-bw_z * np.sign(daily / daily.shift(21) - 1))
    hi20, lo20 = daily.rolling(20, min_periods=15).max(), daily.rolling(20, min_periods=15).min()
    raw["breakout"] = at((daily - (hi20 + lo20) / 2) / ((hi20 - lo20) / 2).replace(0, np.nan))
    if ohlc:
        vol = ohlc.get("volume")
        if vol is not None:
            vol = vol.reindex(index=daily.index, columns=daily.columns)
            vol = vol.where(vol > 0)
            if vol.notna().sum().sum() > 0.2 * daily.notna().sum().sum():
                spike = np.log(vol.rolling(5, min_periods=3).mean() / vol.rolling(50, min_periods=30).mean())
                raw["volume"] = at(spike * np.sign(daily / daily.shift(5) - 1))
        op = ohlc.get("open")
        if op is not None:
            op = op.reindex(index=daily.index, columns=daily.columns)
            gaps = (op / daily.shift(1) - 1) * 100
            raw["gap_fill"] = at(-gaps.rolling(5, min_periods=3).sum())
    # chart patterns
    month_ret = daily.resample("ME").last().pct_change(fill_method=None) * 100
    seas = pd.DataFrame(np.nan, index=W.index, columns=W.columns)
    target_month = (W.index + pd.Timedelta(days=7)).month
    for m in range(1, 13):
        hist = month_ret[month_ret.index.month == m]
        # average of that calendar month in PREVIOUS years only (needs at least 3 years)
        past = hist.expanding(min_periods=3).mean()       # at last year's month-end: includes last year, not this
        rows = W.index[target_month == m]
        if len(rows) and not past.empty:
            seas.loc[rows] = past.reindex(rows, method="ffill").values
    raw["seasonal"] = seas
    move12 = W / W.shift(12) - 1
    wiggle = R.abs().rolling(12, min_periods=10).sum() / 100
    raw["trend_quality"] = (move12 / wiggle.replace(0, np.nan)).clip(-1, 1)
    ac = R.rolling(52, min_periods=26).corr(R.shift(1))
    raw["regime_follow"] = ac * R
    streak = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for c in R.columns:
        s_ = np.sign(R[c].fillna(0)).values
        out_, cur = np.zeros(len(s_)), 0.0
        for i, v in enumerate(s_):
            cur = (cur + v if np.sign(cur) == v else v) if v != 0 else 0.0
            out_[i] = max(-6, min(6, cur))
        streak[c] = out_
    raw["streak"] = streak.where(R.notna())
    raw["off_low"] = at(daily / daily.rolling(252, min_periods=200).min() - 1) * 100
    # cross-asset links
    fac = ctx.get("factors")
    if fac is not None and not fac.empty:
        fw = fac.resample("W-FRI").last()
        series = {}
        if "vix" in fw: series["x_vix"] = fw["vix"]
        if {"copper", "gold"} <= set(fw.columns): series["x_copper_gold"] = np.log(fw["copper"] / fw["gold"]) * 100
        if "oil" in fw: series["x_oil"] = np.log(fw["oil"]) * 100
        if "dollar" in fw: series["x_dollar"] = np.log(fw["dollar"]) * 100
        if "us2y" in fw: series["x_us2y"] = fw["us2y"] * 100
        if "credit" in fw: series["x_credit"] = fw["credit"] * 100
        if "spx" in fw: series["x_spx"] = np.log(fw["spx"]) * 100
        for k, s in series.items():
            raw[k] = lead_lag(R, s)
    # interest rates (FX only)
    rates = ctx.get("rates")
    if cls == "FX" and rates is not None and not rates.empty:
        from reference import CURRENCIES
        r = rates.copy()
        r.index = pd.DatetimeIndex(r.index) + pd.offsets.MonthEnd(1) + pd.Timedelta(days=7)   # known after the month ends
        rw = r.resample("W-FRI").last().ffill().reindex(W.index, method="ffill")
        carry, chg = {}, {}
        for pair in W.columns:
            b, q = _pair_ccy(pair)
            bc, qc = CURRENCIES.get(b, {}).get("bis"), CURRENCIES.get(q, {}).get("bis")
            if bc in rw.columns and qc in rw.columns:
                gap = rw[bc] - rw[qc]
                carry[pair], chg[pair] = gap, gap - gap.shift(13)
        if carry:
            raw["carry"] = pd.DataFrame(carry).reindex(columns=W.columns)
            raw["rate_change"] = pd.DataFrame(chg).reindex(columns=W.columns)
    # positioning
    cot = ctx.get("cot")
    if cot is not None and not cot.empty:
        cw = cot.resample("W-FRI").last().reindex(W.index, method="ffill", limit=2)
        crowd_z = (cw - cw.rolling(156, min_periods=52).mean()) / cw.rolling(156, min_periods=52).std()
        flow = cw - cw.shift(4)
        crowd, flw = {}, {}
        for t in W.columns:
            if cls == "FX":
                b, q = _pair_ccy(t)
                parts = [(b, 1), (q, -1)]
            else:
                parts = [(COT_ALIAS.get(t, t), 1)]
            cz = [crowd_z[k] * s for k, s in parts if k in crowd_z]
            fz = [flow[k] * s for k, s in parts if k in flow]
            if cz:
                crowd[t] = -sum(cz)
                flw[t] = sum(fz)
        if crowd:
            raw["cot_crowd"] = pd.DataFrame(crowd).reindex(columns=W.columns)
            raw["cot_flow"] = pd.DataFrame(flw).reindex(columns=W.columns)
    # inventories
    eia = ctx.get("eia") or {}
    inv = {}
    for name, (_, _, assets) in EIA_SERIES.items():
        if name in eia:
            surprise = -inventory_surprise(eia[name])
            sw = surprise.resample("W-FRI").last().reindex(W.index, method="ffill", limit=1)
            for a in assets:
                if a in W.columns:
                    inv[a] = sw
    if inv:
        raw["eia_surprise"] = pd.DataFrame(inv).reindex(columns=W.columns)
    # calendar (the same for every asset in the class)
    cal = ctx.get("calendar")
    if cal is None:
        cal = calendar_flags(W.index, ctx.get("cpi", pd.DatetimeIndex([])))
    for k in CALENDAR_KEYS:
        if k in cal:
            raw[k] = pd.DataFrame(np.repeat(cal[k].reindex(W.index).values[:, None], W.shape[1], axis=1),
                                  index=W.index, columns=W.columns)
    if "month_end_next" in cal:
        month_start = daily.groupby(daily.index.to_period("M")).transform("first")
        mtd = at(daily / month_start - 1) * 100
        raw["rebalance"] = -mtd.mul(cal["month_end_next"].reindex(W.index), axis=0)
    # context (machine-learning model only): conditions that may change how other ingredients work
    if fac is not None and not fac.empty and "vix" in fac:
        vix_w = fac["vix"].resample("W-FRI").last().reindex(W.index, method="ffill")
        raw["ctx_vix"] = pd.DataFrame(np.repeat(vix_w.values[:, None], W.shape[1], axis=1), index=W.index, columns=W.columns)
    raw["ctx_vol"] = vol_w.copy()
    # company data (v19) plugs in here
    for k, df in (ctx.get("company", {}).get(cls) or {}).items():
        raw[k] = df.reindex(index=W.index, columns=W.columns)
    raw = {k: v.replace([np.inf, -np.inf], np.nan) for k, v in raw.items() if v is not None and v.notna().any().any()}
    # calendar flags are centred (event weeks positive, normal weeks slightly negative), so the test compares
    # event weeks with normal weeks instead of only counting the few event weeks
    z = {}
    for k, v in raw.items():
        if k in FLAG_KEYS:
            z[k] = v.clip(0, 1) - v.clip(0, 1).stack().mean()
        elif k in XS_KEYS:
            z[k] = zscore_xs(v)
        else:
            z[k] = zscore_ts(v)
    return raw, z, W, R, F, vol_w


def build_context(classes):
    """Downloads everything the ingredients need once (cached on disk)."""
    ctx = {"factors": load_factors(), "cot": load_cot(), "eia": load_eia(), "cpi": cpi_dates()}
    try:
        from reference import CURRENCIES
        from sources import fetch_policy_rates
        ctx["rates"] = fetch_policy_rates(tuple(sorted({c["bis"] for c in CURRENCIES.values()})))
        _status("Central bank rates (BIS)", True, f"{ctx['rates'].shape[1]} countries")
    except Exception as exc:
        ctx["rates"] = None
        _status("Central bank rates (BIS)", False, exc)
    return ctx


# ================================================================= testing one ingredient

def normal_p(t):
    from math import erf, sqrt
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def signal_returns(score, F):
    """Weekly % return from betting in the ingredient's direction, bigger bets when it is more extreme."""
    s = score.where(F.notna())
    w = s.div(s.abs().sum(axis=1).replace(0, np.nan), axis=0)
    ret = (w * F).sum(axis=1, min_count=1)
    return ret.where(w.abs().sum(axis=1) > 0)


def _part_stats(score, F, idx):
    s, f = score.reindex(idx), F.reindex(idx)
    ok = s.notna() & f.notna() & (s != 0) & (f != 0)
    if ok.sum().sum() < 20:
        return None
    hits = (np.sign(s) == np.sign(f)).where(ok)
    weekly_hit = hits.mean(axis=1).dropna()
    ret = signal_returns(s.where(ok), f).dropna()
    if len(ret) < 8:
        return None
    t = ret.mean() / ret.std() * np.sqrt(len(ret)) if ret.std() > 0 else 0.0
    ht = (weekly_hit.mean() - 0.5) / weekly_hit.std() * np.sqrt(len(weekly_hit)) if weekly_hit.std() > 0 else 0.0
    ics = []
    if s.shape[1] >= 5:
        for d in s.index:
            a, b = s.loc[d], f.loc[d]
            m = a.notna() & b.notna()
            if m.sum() >= 5 and a[m].nunique() > 1:
                ics.append(a[m].rank().corr(b[m].rank()))
    return dict(weeks=len(ret), calls=int(ok.sum().sum()), hit=float(hits.stack().mean() * 100),
                hit_p=normal_p(ht), edge=float(ret.mean()), t=float(t), p=normal_p(t),
                ic=float(np.nanmean(ics)) if ics else np.nan)


def judge(disc, unseen):
    """
    Verdict plus a plain-English 'why it failed' note. t-stats measure how sure we can be it isn't luck
    (about 2 = convincing, below 1 = indistinguishable from noise).
    """
    if not disc or not unseen:
        return "Not enough data", ("Too few weeks with this ingredient available in one of the two periods "
                                   "(its data may not reach back far enough, it's a rare event, or it didn't load).")
    a, b = disc["t"], unseen["t"]
    if a >= 1.5 and b >= 1:
        return "✅ Confirmed", "Worked in discovery and again on the unseen period."
    if a <= -1.5 and b <= -1:
        return "🔄 Confirmed in reverse", ("It works backwards: the opposite of what it says happened in both periods. "
                                          "The model can use it with a minus sign.")
    if a >= 1 and b >= 0.5:
        return "🟡 Promising", f"Positive in both periods but not strong enough to rule out luck (t = {a:.1f} then {b:.1f}; about 2 is convincing)."
    if a <= -1 and b <= -0.5:
        return "🟡 Promising (reverse)", f"Backwards in both periods but not convincingly (t = {a:.1f} then {b:.1f})."
    if abs(a) >= 1.5:
        return "❌ Failed to confirm", ("Looked good in discovery but didn't hold on the unseen period: "
                                       "classic luck, or an effect that faded once people knew about it.")
    if abs(b) >= 1.5:
        return "⚠️ Only worked recently", ("Nothing in discovery but strong on the unseen period. Could be a new effect, "
                                          "or a lucky streak: it needs to keep working in the prediction log.")
    return "❌ No effect", "Indistinguishable from noise in both periods."


def test_ingredient(z, F, start, end, unseen_frac=0.3):
    idx = F.index[(F.index >= start) & (F.index <= end) & F.notna().any(axis=1)]
    if len(idx) < 12:
        return None
    cut = idx[int(len(idx) * (1 - unseen_frac))]
    disc, uns = _part_stats(z, F, idx[idx < cut]), _part_stats(z, F, idx[idx >= cut])
    allp = _part_stats(z, F, idx)
    v, why = judge(disc, uns)
    if allp and abs(allp["hit"] - 50) < 1 and v.startswith("❌"):
        why += f" Its direction calls were right {allp['hit']:.1f}% of the time: a coin toss."
    return dict(disc=disc, unseen=uns, all=allp, verdict=v, why=why, cut=cut,
                curve=signal_returns(z.reindex(idx), F.reindex(idx)))


def run_lab(prices_by_class, ohlc_by_class, ctx, start, end, unseen_frac=0.3, progress=None):
    """Tests every ingredient on every asset class. Returns (league table, details, built data)."""
    rows, details, built = [], {}, {}
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    for ci, (cls, prices) in enumerate(prices_by_class.items()):
        if progress:
            progress(ci / max(1, len(prices_by_class)), f"Building ingredients for {cls}...")
        raw, z, W, R, F, vol_w = build_ingredients(cls, prices, (ohlc_by_class or {}).get(cls), ctx)
        built[cls] = dict(raw=raw, z=z, W=W, R=R, F=F, vol_w=vol_w)
        for k in z:
            if k.startswith("ctx_"):
                continue
            res = test_ingredient(z[k], F, start, end, unseen_frac)
            if res is None:
                continue
            details[(k, cls)] = res
            name, fam = INGREDIENTS.get(k, (k, "Other", "", ""))[:2]
            d, u, a = res["disc"] or {}, res["unseen"] or {}, res["all"] or {}
            rows.append(dict(key=k, ingredient=name, family=fam, cls=cls, verdict=res["verdict"],
                             disc_edge=d.get("edge"), disc_t=d.get("t"), unseen_edge=u.get("edge"), unseen_t=u.get("t"),
                             hit=a.get("hit"), ic=a.get("ic"), weeks=a.get("weeks"), why=res["why"]))
    if progress:
        progress(1.0, "Done")
    league = pd.DataFrame(rows)
    if not league.empty:
        rank = {"✅": 0, "🔄": 1, "🟡": 2, "⚠": 3, "❌": 5, "N": 6}
        league["_r"] = league["verdict"].map(lambda v: rank.get(v[:1], 6))
        league = league.sort_values(["_r", "unseen_t"], ascending=[True, False]).drop(columns="_r")
    return league, details, built


# ================================================================= API key check

KEY_TESTS = {
    "FRED_API_KEY": ("FRED (US economic data)", "https://api.stlouisfed.org/fred/series/observations",
                     lambda k: {"series_id": "DGS2", "api_key": k, "file_type": "json", "limit": 1}),
    "EIA_API_KEY": ("EIA (oil and gas inventories)", "https://api.eia.gov/v2/petroleum/stoc/wstk/data/",
                    lambda k: {"api_key": k, "frequency": "weekly", "data[0]": "value", "length": 1}),
    "FINNHUB_API_KEY": ("Finnhub (earnings, analysts, directors)", "https://finnhub.io/api/v1/quote",
                        lambda k: {"symbol": "AAPL", "token": k}),
    "FMP_API_KEY": ("Financial Modeling Prep (company accounts)", "https://financialmodelingprep.com/stable/profile",
                    lambda k: {"symbol": "AAPL", "apikey": k}),
    "TIINGO_API_KEY": ("Tiingo (price cross-check)", "https://api.tiingo.com/tiingo/daily/AAPL",
                       lambda k: {"token": k}),
}


def check_keys():
    """Tries one tiny request with each key. Returns [(source, status, detail)]."""
    rows = []
    for name, (label, url, params) in KEY_TESTS.items():
        key = get_key(name)
        if not key:
            rows.append((label, "➖ no key", f"add {name} to .streamlit/secrets.toml"))
            continue
        try:
            r = requests.get(url, params=params(key), headers=UA, timeout=15)
            if r.status_code in (401, 403):
                rows.append((label, "❌ key refused", f"HTTP {r.status_code}: {r.text[:120]}"))
            elif r.status_code == 429:
                rows.append((label, "🟡 connected, rate-limited", "too many requests just now; try again in a minute"))
            elif r.ok:
                body = r.text[:200].lower()
                if "error" in body and ("invalid" in body or "limit" in body):
                    rows.append((label, "❌ error", r.text[:160]))
                else:
                    rows.append((label, "✅ connected", "test request worked"))
            else:
                rows.append((label, "❌ error", f"HTTP {r.status_code}: {r.text[:120]}"))
        except Exception as exc:
            rows.append((label, "❌ couldn't connect", f"{type(exc).__name__}: {exc}"[:160]))
    return rows
