"""
assetlab.py - ASSET LAB (PC version only): Monte Carlo simulations for stocks, indices,
commodities, FX and crypto, an "attention" score from news and Wikipedia, and a full
plain-English data analysis of every simulation.

HOW THE SIMULATION WORKS (filtered historical simulation)
1. Take each asset's daily returns over the last 2 years.
2. Measure how volatile it is right now (an EWMA: recent days count more), and divide each
   past return by the volatility at the time. That gives "standardised shocks".
3. For each of 10,000 simulated futures, pick past shocks at random, scale them by today's
   volatility, and let volatility keep updating as the path moves. That keeps two real-world
   features normal bell curves miss: crashes (fat tails) and calm/wild spells (clustering).
4. Optional drift (the "view"): trend continues, no view, or bounce back.

Just for fun and learning. Not financial advice.
"""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import numpy as np
import pandas as pd
import requests
import streamlit as st

from indicators import COMMODITY_MONITOR, EQUITY_MONITOR

# Wikimedia asks every tool to identify itself with a way to reach the owner (a URL), or it may refuse.
UA = {"User-Agent": "HF-Macro/1.1 (https://hf-macro.streamlit.app; personal educational dashboard) python-requests"}
WIKI_STATUS = {"ok": 0, "failed": 0, "last_error": ""}

# ---------------------------------------------------------------- the universe

FALLBACK_UK = [("AZN.L", "AstraZeneca", "AstraZeneca"), ("SHEL.L", "Shell", "Shell_plc"),
               ("HSBA.L", "HSBC", "HSBC"), ("ULVR.L", "Unilever", "Unilever"), ("BP.L", "BP", "BP"),
               ("GSK.L", "GSK", "GSK_plc"), ("RIO.L", "Rio Tinto", "Rio_Tinto"), ("REL.L", "RELX", "RELX"),
               ("DGE.L", "Diageo", "Diageo"), ("BATS.L", "British American Tobacco", "British_American_Tobacco"),
               ("LSEG.L", "London Stock Exchange Group", "London_Stock_Exchange_Group"),
               ("BARC.L", "Barclays", "Barclays"), ("LLOY.L", "Lloyds Banking Group", "Lloyds_Banking_Group"),
               ("NWG.L", "NatWest Group", "NatWest_Group"), ("RR.L", "Rolls-Royce Holdings", "Rolls-Royce_Holdings"),
               ("BA.L", "BAE Systems", "BAE_Systems"), ("TSCO.L", "Tesco", "Tesco"),
               ("VOD.L", "Vodafone", "Vodafone"), ("JD.L", "JD Sports", "JD_Sports"),
               ("NG.L", "National Grid", "National_Grid_plc"), ("AAL.L", "Anglo American", "Anglo_American_plc"),
               ("GLEN.L", "Glencore", "Glencore"), ("PRU.L", "Prudential", "Prudential_plc"),
               ("IAG.L", "International Airlines Group", "International_Airlines_Group"),
               ("MKS.L", "Marks & Spencer", "Marks_%26_Spencer")]
FALLBACK_US = [("AAPL", "Apple", "Apple_Inc."), ("MSFT", "Microsoft", "Microsoft"), ("NVDA", "Nvidia", "Nvidia"),
               ("AMZN", "Amazon", "Amazon_(company)"), ("GOOGL", "Alphabet", "Alphabet_Inc."),
               ("META", "Meta Platforms", "Meta_Platforms"), ("TSLA", "Tesla", "Tesla,_Inc."),
               ("BRK-B", "Berkshire Hathaway", "Berkshire_Hathaway"), ("JPM", "JPMorgan Chase", "JPMorgan_Chase"),
               ("V", "Visa", "Visa_Inc."), ("UNH", "UnitedHealth", "UnitedHealth_Group"),
               ("XOM", "ExxonMobil", "ExxonMobil"), ("JNJ", "Johnson & Johnson", "Johnson_%26_Johnson"),
               ("WMT", "Walmart", "Walmart"), ("PG", "Procter & Gamble", "Procter_%26_Gamble"),
               ("MA", "Mastercard", "Mastercard"), ("HD", "Home Depot", "The_Home_Depot"),
               ("COST", "Costco", "Costco"), ("NFLX", "Netflix", "Netflix"), ("AMD", "AMD", "AMD"),
               ("NKE", "Nike", "Nike,_Inc."), ("KO", "Coca-Cola", "The_Coca-Cola_Company"),
               ("DIS", "Disney", "The_Walt_Disney_Company"), ("BA", "Boeing", "Boeing"),
               ("GS", "Goldman Sachs", "Goldman_Sachs")]
FX = [("GBPUSD=X", "GBP/USD", "Pound_sterling"), ("EURUSD=X", "EUR/USD", "Euro"),
      ("USDJPY=X", "USD/JPY", "Japanese_yen"), ("GBPEUR=X", "GBP/EUR", "Pound_sterling"),
      ("USDCHF=X", "USD/CHF", "Swiss_franc"), ("AUDUSD=X", "AUD/USD", "Australian_dollar"),
      ("USDCAD=X", "USD/CAD", "Canadian_dollar"), ("NZDUSD=X", "NZD/USD", "New_Zealand_dollar"),
      ("GBPJPY=X", "GBP/JPY", "Japanese_yen"), ("USDCNY=X", "USD/CNY", "Renminbi"),
      ("USDINR=X", "USD/INR", "Indian_rupee"), ("USDMXN=X", "USD/MXN", "Mexican_peso"),
      ("USDZAR=X", "USD/ZAR", "South_African_rand"), ("USDTRY=X", "USD/TRY", "Turkish_lira"),
      ("USDNOK=X", "USD/NOK", "Norwegian_krone")]
CRYPTO = [("BTC-USD", "Bitcoin", "Bitcoin"), ("ETH-USD", "Ethereum", "Ethereum"),
          ("SOL-USD", "Solana", "Solana_(blockchain_platform)"), ("XRP-USD", "XRP", "Ripple_Labs"),
          ("BNB-USD", "BNB", "Binance"), ("DOGE-USD", "Dogecoin", "Dogecoin"), ("ADA-USD", "Cardano", "Cardano_(blockchain_platform)"),
          ("AVAX-USD", "Avalanche", "Avalanche_(blockchain_platform)"), ("LINK-USD", "Chainlink", "Chainlink_(blockchain)"),
          ("DOT-USD", "Polkadot", "Polkadot_(blockchain_platform)"), ("LTC-USD", "Litecoin", "Litecoin"),
          ("TRX-USD", "TRON", "Tron_(cryptocurrency)"), ("XLM-USD", "Stellar", "Stellar_(payment_network)")]
WIKI_INDEX = {"^GSPC": "S%26P_500", "^DJI": "Dow_Jones_Industrial_Average", "^IXIC": "Nasdaq_Composite",
              "^RUT": "Russell_2000_Index", "^GSPTSE": "S%26P/TSX_Composite_Index", "^BVSP": "Ibovespa",
              "^MXX": "S%26P/BMV_IPC", "^FTSE": "FTSE_100_Index", "^FTMC": "FTSE_250_Index", "^GDAXI": "DAX",
              "^FCHI": "CAC_40", "^STOXX50E": "Euro_Stoxx_50", "FTSEMIB.MI": "FTSE_MIB", "^IBEX": "IBEX_35",
              "^AEX": "AEX_index", "^SSMI": "Swiss_Market_Index", "^N225": "Nikkei_225", "^HSI": "Hang_Seng_Index",
              "000001.SS": "SSE_Composite_Index", "^KS11": "KOSPI", "^TWII": "Taiwan_Capitalization_Weighted_Stock_Index",
              "^BSESN": "BSE_SENSEX", "^AXJO": "S%26P/ASX_200"}
WIKI_COMMODITY = {"BZ=F": "Brent_Crude", "CL=F": "West_Texas_Intermediate", "NG=F": "Natural_gas",
                  "RB=F": "Gasoline", "HO=F": "Heating_oil", "GC=F": "Gold", "SI=F": "Silver", "PL=F": "Platinum",
                  "HG=F": "Copper", "ZW=F": "Wheat", "ZC=F": "Maize", "ZS=F": "Soybean", "KC=F": "Coffee",
                  "SB=F": "Sugar", "CC=F": "Cocoa_bean", "CT=F": "Cotton", "LE=F": "Cattle"}
CLASSES = ["UK stocks", "US stocks", "World indices", "Commodities", "FX", "Crypto"]
CLASS_COLOURS = {"UK stocks": "#3FB6FF", "US stocks": "#C792EA", "World indices": "#5EE6C9",
                 "Commodities": "#E8A33D", "FX": "#FFD166", "Crypto": "#FF7AB6"}


def _wiki_title(href):
    if isinstance(href, str) and href.startswith("/wiki/"):
        return href[len("/wiki/"):]
    return None


def _cell(v):
    return v if isinstance(v, tuple) else (v, None)


@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def fetch_index_members(which):
    """FTSE 100 or S&P 500 members from Wikipedia: [(yahoo ticker, name, wikipedia title, sector)]."""
    url = {"UK": "https://en.wikipedia.org/wiki/FTSE_100_Index",
           "US": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"}[which]
    html = requests.get(url, headers=UA, timeout=20).text
    tables = pd.read_html(StringIO(html), extract_links="body")
    for t in tables:
        cols = [str(c[0] if isinstance(c, tuple) else c) for c in t.columns]
        t.columns = cols
        tick_col = "Ticker" if "Ticker" in cols else "Symbol" if "Symbol" in cols else None
        name_col = "Company" if "Company" in cols else "Security" if "Security" in cols else None
        sector_col = next((c for c in cols if "sector" in c.lower()), None)
        if not tick_col or not name_col or len(t) < 50:
            continue
        out = []
        for _, row in t.iterrows():
            tick, _ = _cell(row[tick_col])
            name, href = _cell(row[name_col])
            tick = str(tick).strip()
            if not tick or tick == "nan":
                continue
            if which == "UK":
                yahoo = tick.replace(".", "-").rstrip("-") + ".L"
            else:
                yahoo = tick.replace(".", "-")
            sector = str(_cell(row[sector_col])[0]).strip() if sector_col else ""
            out.append((yahoo, str(name).strip(), _wiki_title(href), sector.title() if sector != "nan" else ""))
        if out:
            return out
    raise ValueError("member table not found")


def universe(classes):
    """{class: [(ticker, name, wikipedia title)]}"""
    out = {}
    for c in classes:
        if c == "UK stocks":
            try:
                out[c] = [m[:3] for m in fetch_index_members("UK")]
            except Exception:
                out[c] = FALLBACK_UK
        elif c == "US stocks":
            try:
                out[c] = [m[:3] for m in fetch_index_members("US")]
            except Exception:
                out[c] = FALLBACK_US
        elif c == "World indices":
            out[c] = [(t, n, WIKI_INDEX.get(t)) for items in EQUITY_MONITOR.values() for t, n in items]
        elif c == "Commodities":
            out[c] = [(t, n, WIKI_COMMODITY.get(t)) for items in COMMODITY_MONITOR.values() for t, n in items]
        elif c == "FX":
            out[c] = FX
        elif c == "Crypto":
            out[c] = CRYPTO
    return out


def sector_map(classes):
    """ticker -> sector (stocks, from the Wikipedia tables). Other asset classes use the class name."""
    out = {}
    for c, which in (("UK stocks", "UK"), ("US stocks", "US")):
        if c in classes:
            try:
                out.update({m[0]: (m[3] or "Other") for m in fetch_index_members(which)})
            except Exception:
                pass
    return out


# ---------------------------------------------------------------- prices: 10 years, cleaned, cached on disk

import os
import time as _time
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "data" / "cache"


def download_prices(tickers, period="10y"):
    """Daily closing prices, ADJUSTED for dividends and splits (so payouts don't look like losses)."""
    import yfinance as yf
    frame = yf.download(list(tickers), period=period, interval="1d", auto_adjust=True,
                        progress=False, threads=True)
    from sources import parse_yahoo_batch
    return parse_yahoo_batch(frame, list(tickers))


def download_ohlc(tickers, period="10y"):
    """Daily open, high, low and close (all adjusted), so trades can be checked day by day."""
    import yfinance as yf
    frame = yf.download(list(tickers), period=period, interval="1d", auto_adjust=True,
                        progress=False, threads=True)
    if frame is None or frame.empty:
        raise ValueError("Yahoo Finance returned no prices")
    out = {}
    for field in ("Open", "High", "Low", "Close", "Volume"):
        if isinstance(frame.columns, pd.MultiIndex):
            if field not in frame.columns.get_level_values(0) and field not in frame.columns.get_level_values(1):
                continue
            level = 0 if field in frame.columns.get_level_values(0) else 1
            f = frame.xs(field, axis=1, level=level)
        else:
            if field not in frame.columns:
                continue
            f = frame[[field]].rename(columns={field: list(tickers)[0]})
        idx = pd.DatetimeIndex(f.index)
        f.index = idx.tz_localize(None) if idx.tz is not None else idx
        out[field.lower()] = f.sort_index()
    return out


def clean_ohlc(raw, clean_close):
    """Applies the same glitch fixes to open/high/low that were applied to the close."""
    out = {"close": clean_close}
    if "volume" in raw:
        out["volume"] = raw["volume"].reindex(index=clean_close.index, columns=clean_close.columns)
    raw_close = raw["close"].reindex(index=clean_close.index, columns=clean_close.columns)
    factor = (clean_close / raw_close).where(clean_close.notna())
    for f in ("open", "high", "low"):
        out[f] = (raw[f].reindex(index=clean_close.index, columns=clean_close.columns) * factor)
    return out


def clean_prices(prices, asset_class):
    """
    Fixes data glitches before anything uses the prices:
    1. UK prices that flip between pence and pounds (a fake x100 or /100 jump) are rescaled.
    2. Any other impossible one-day move (over 40% in a day, crypto excepted) is treated as a bad tick
       and replaced with the previous day's price.
    Returns (clean prices, list of fixes made).
    """
    fixes = []
    out = prices.copy()
    for col in out.columns:
        s = out[col].dropna()
        s = s[s > 0]
        if len(s) < 30:
            continue
        ref = s.rolling(21, center=True, min_periods=5).median()
        ratio = s / ref
        big, small = ratio > 30, ratio < 1 / 30
        if big.any() or small.any():
            s = s.where(~big, s / 100).where(~small, s * 100)
            fixes.append((col, int(big.sum() + small.sum()), "pence/pounds switch"))
        if asset_class != "Crypto":
            r = s.pct_change()
            spike = (r.abs() > 0.4) & (r.shift(-1).abs() > 0.25)          # jumps and immediately reverses
            if spike.any():
                s = s.mask(spike).ffill()
                fixes.append((col, int(spike.sum()), "one-day spike"))
        out[col] = s.reindex(out.index)
    return out, fixes


def load_class_prices(asset_class, tickers, max_age_hours=12):
    """10 years of cleaned daily prices for one asset class, saved on disk so restarts are quick."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"prices_{asset_class.replace(' ', '_').lower()}.pkl"
    cached = _read_cache(path, tickers, max_age_hours)
    if cached is not None:
        return cached["prices"], cached["fixes"]
    ohlc = None
    try:
        raw_ohlc = download_ohlc(tuple(tickers))
        raw = raw_ohlc["close"]
    except Exception:
        raw_ohlc, raw = None, download_prices(tuple(tickers))
    clean, fixes = clean_prices(raw, asset_class)
    if raw_ohlc is not None:
        try:
            ohlc = clean_ohlc(raw_ohlc, clean)
        except Exception:
            ohlc = None
    try:
        pd.to_pickle({"prices": clean, "fixes": fixes, "ohlc": ohlc}, path)
    except Exception:
        pass
    return clean, fixes


def _read_cache(path, tickers, max_age_hours):
    if path.exists() and _time.time() - path.stat().st_mtime < max_age_hours * 3600:
        try:
            cached = pd.read_pickle(path)
            if set(tickers) <= set(cached["prices"].columns) or len(cached["prices"].columns) >= 0.9 * len(tickers):
                return cached
        except Exception:
            return None
    return None


def load_class_ohlc(asset_class, tickers, max_age_hours=12):
    """Daily open/high/low/close for one asset class (None if only closing prices are available)."""
    path = CACHE_DIR / f"prices_{asset_class.replace(' ', '_').lower()}.pkl"
    cached = _read_cache(path, tickers, max_age_hours)
    if cached is None or "ohlc" not in cached or (cached["ohlc"] and "volume" not in cached["ohlc"]):  # old cache format
        load_class_prices(asset_class, tickers, max_age_hours=0)
        cached = _read_cache(path, tickers, max_age_hours)
    return cached.get("ohlc") if cached else None


# ---------------------------------------------------------------- Monte Carlo

DRIFTS = {
    "Trend continues": "Half of the average daily move over the last 3 months carries on (momentum).",
    "No view": "No drift: every simulated future starts from a coin toss, only volatility matters.",
    "Bounce back": "Half of last week's move reverses (mean reversion).",
}


def horizon_days(asset_class, horizon):
    if asset_class == "Crypto":
        return 7 if horizon == "Next week" else 30
    return 5 if horizon == "Next week" else 21


HALF_LIFE_DAYS = 504          # a day two years ago counts half as much as yesterday when replaying shocks


def recency_weights(n, half_life=HALF_LIFE_DAYS):
    w = 0.5 ** (np.arange(n)[::-1] / half_life)
    return w / w.sum()


def simulate(prices, days, n_sims=10000, drift="Trend continues", lam=0.94, seed=1):
    """
    % change after `days` trading days for each of n_sims simulated futures.
    Replays up to 10 years of past shocks (so real crashes are included), with recent years
    counting more (half-life two years).
    """
    p = prices.dropna()
    p = p[p > 0]
    r = np.log(p).diff().dropna().values[-2520:]
    if len(r) < 120:
        raise ValueError("not enough price history")
    var = np.empty(len(r))
    var[0] = r[:20].var() or r.var()
    for t in range(1, len(r)):
        var[t] = lam * var[t - 1] + (1 - lam) * r[t - 1] ** 2
    var = np.maximum(var, 1e-12)
    z = r / np.sqrt(var)
    z = (z - z.mean()) / z.std()
    now_var = lam * var[-1] + (1 - lam) * r[-1] ** 2
    if drift == "Trend continues":
        mu = 0.5 * r[-63:].mean()
    elif drift == "Bounce back":
        mu = -0.5 * r[-5:].sum() / days
    else:
        mu = 0.0
    rng = np.random.default_rng(seed)
    w = recency_weights(len(z))
    v = np.full(n_sims, now_var)
    total = np.zeros(n_sims)
    for _ in range(days):
        ret = mu + np.sqrt(v) * rng.choice(z, size=n_sims, p=w)
        total += ret
        v = lam * v + (1 - lam) * ret ** 2
    return (np.exp(total) - 1) * 100


def kde_mode(x):
    """The most likely value: the peak of a smoothed histogram (kernel density estimate)."""
    x = np.asarray(x)
    sd = x.std()
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    sample = x if len(x) <= 1500 else np.random.default_rng(0).choice(x, 1500, replace=False)
    h = 0.9 * min(sd, iqr / 1.34 if iqr > 0 else sd) * len(sample) ** -0.2   # smoothing width for the sample used
    if h <= 0:
        return float(np.median(x))
    lo, hi = np.percentile(x, [1, 99])
    grid = np.linspace(lo, hi, 400)
    dens = np.exp(-0.5 * ((grid[:, None] - sample[None, :]) / h) ** 2).sum(axis=1)
    return float(grid[int(np.argmax(dens))])


def count_peaks(x):
    """How many clear peaks the smoothed histogram has (1 = one cluster, 2+ = separate clusters)."""
    x = np.asarray(x)
    sd = x.std()
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    sample = x if len(x) <= 1500 else np.random.default_rng(0).choice(x, 1500, replace=False)
    h = 0.9 * min(sd, iqr / 1.34 if iqr > 0 else sd) * len(sample) ** -0.2   # smoothing width for the sample used
    if h <= 0:
        return 1
    lo, hi = np.percentile(x, [1, 99])
    grid = np.linspace(lo, hi, 300)
    d = np.exp(-0.5 * ((grid[:, None] - sample[None, :]) / h) ** 2).sum(axis=1)
    peaks = [i for i in range(1, len(d) - 1) if d[i] > d[i - 1] and d[i] >= d[i + 1] and d[i] > 0.6 * d.max()]
    # only count a peak as separate if there is a real dip (valley at least 15% lower) between it and the last one
    kept = []
    for i in peaks:
        if kept and d[kept[-1]:i + 1].min() > 0.85 * min(d[kept[-1]], d[i]):
            if d[i] > d[kept[-1]]:
                kept[-1] = i
            continue
        kept.append(i)
    return max(1, len(kept))


def choose_average(x):
    """
    Works out which average best describes the simulated outcomes, the way you would in a
    data analysis exam:
      - MEAN when the data is roughly symmetrical with few outliers (it uses every value).
      - MEDIAN when the data is skewed or has outliers, because extreme values pull the mean
        (and stretch the range) but barely move the median.
      - MODE when the data has two or more separate clusters, so the mean and median land in
        a gap between them where few outcomes actually happen.
    Returns (name, value, reason, checks).
    """
    x = np.asarray(x)
    mean, med, mode = float(x.mean()), float(np.median(x)), kde_mode(x)
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    sd = x.std()
    skew = float(((x - mean) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    lo_f, hi_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr                 # Tukey's outlier fences
    outliers = float(((x < lo_f) | (x > hi_f)).mean() * 100)
    gap = abs(mean - med) / iqr * 100 if iqr > 0 else 0.0      # mean-median gap as % of the IQR
    rng = float(x.max() - x.min())
    peaks = count_peaks(x)
    checks = dict(skew=skew, outliers=outliers, gap=gap, peaks=peaks, range=rng, iqr=float(iqr),
                  range_to_iqr=rng / iqr if iqr > 0 else None, mean=mean, median=med, mode=mode)
    if peaks >= 2:
        return "Mode", mode, (f"The outcomes form {peaks} separate clusters, so the mean and median fall in a gap "
                              "between them. The mode (the biggest cluster) is the most realistic single answer."), checks
    if abs(skew) >= 0.5 or outliers > 5 or gap > 10:
        why = []
        if abs(skew) >= 0.5:
            why.append(f"the data is {'positively' if skew > 0 else 'negatively'} skewed ({skew:+.2f})")
        if outliers > 5:
            why.append(f"{outliers:.1f}% of outcomes are outliers (beyond 1.5 × IQR from the quartiles)")
        if gap > 10:
            why.append(f"the mean is pulled {gap:.0f}% of an IQR away from the median")
        return "Median", med, ("Median, because " + " and ".join(why) + ". Extreme values drag the mean and stretch "
                               "the range, but hardly move the median."), checks
    return "Mean", mean, (f"The data is close to symmetrical (skew {skew:+.2f}) with few outliers ({outliers:.1f}%), "
                          "so the mean is reliable and uses every outcome."), checks


def summary(sims):
    q1, med, q3 = np.percentile(sims, [25, 50, 75])
    best_name, best, reason, _ = choose_average(sims)
    return dict(mode=kde_mode(sims), median=float(med), mean=float(sims.mean()), sd=float(sims.std(ddof=1)),
                best=best, best_type=best_name, best_reason=reason,
                p_up=float((sims > 0).mean() * 100), p5=float(np.percentile(sims, 5)),
                p95=float(np.percentile(sims, 95)), q1=float(q1), q3=float(q3))


def scan(prices_by_class, uni, horizon, drift, n_sims=4000):
    """Runs the simulation for every asset. Returns one row per asset."""
    rows = []
    for c, members in uni.items():
        prices = prices_by_class.get(c)
        if prices is None:
            continue
        for ticker, name, wiki in members:
            if ticker not in prices.columns:
                continue
            s = prices[ticker].dropna()
            if len(s) < 130:
                continue
            try:
                sims = simulate(s, horizon_days(c, horizon), n_sims=n_sims, drift=drift)
            except Exception:
                continue
            week = s.asof(s.index[-1] - pd.Timedelta(days=7))
            summ = summary(sims)
            rows.append(dict(ticker=ticker, name=name, wiki=wiki, cls=c, last=float(s.iloc[-1]),
                             last_week=(float(s.iloc[-1]) / float(week) - 1) * 100 if week and not pd.isna(week) else None,
                             # signal per unit of risk: the median move divided by the spread of outcomes
                             score=summ["median"] / summ["sd"] if summ["sd"] > 0 else 0.0,
                             **summ))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- attention: news + Wikipedia

# These run in parallel threads, so they use a simple in-memory cache rather than Streamlit's.
_TTL_CACHE = {}


def _cached(key, hours, fn):
    import time
    hit = _TTL_CACHE.get(key)
    if hit and time.time() - hit[0] < hours * 3600:
        return hit[1]
    value = fn()
    _TTL_CACHE[key] = (time.time(), value)
    return value


def news_count(query):
    """Number of Google News headlines in the last 7 days (Google returns up to 100)."""
    def go():
        from sources import fetch_news_search
        raw = getattr(fetch_news_search, "__wrapped__", fetch_news_search)
        try:
            return int(len(raw(query, days=7)))
        except Exception:
            return None
    return _cached(("news", query), 3, go)


def wiki_views(title):
    """Wikipedia page views in the last 7 days (None if the asset has no Wikipedia page)."""
    if not isinstance(title, str) or not title.strip():
        return None
    try:
        return _cached(("wiki", title), 6, lambda: _wiki_views(title))
    except Exception:
        return None


def wiki_views_baseline(title):
    """(views in the last 7 days, typical 7-day views over the 12 weeks before that)."""
    if not isinstance(title, str) or not title.strip():
        return None, None
    try:
        return _cached(("wiki90", title), 6, lambda: _wiki_views_90(title))
    except Exception:
        return None, None


def _wiki_views_90(title):
    from urllib.parse import quote, unquote
    t = quote(unquote(title), safe="")
    end = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=90)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
           f"{t}/daily/{start:%Y%m%d}00/{end:%Y%m%d}00")
    r = requests.get(url, headers=UA, timeout=15)
    if r.status_code != 200:
        WIKI_STATUS["failed"] += 1
        WIKI_STATUS["last_error"] = f"HTTP {r.status_code}"
        return None, None
    WIKI_STATUS["ok"] += 1
    views = [i.get("views", 0) for i in r.json().get("items", [])]
    if len(views) < 14:
        return (sum(views[-7:]) if views else None), None
    last7 = sum(views[-7:])
    before = views[:-7]
    return last7, sum(before) / len(before) * 7


def news_count_30(query):
    def go():
        from sources import fetch_news_search
        raw = getattr(fetch_news_search, "__wrapped__", fetch_news_search)
        try:
            return int(len(raw(query, days=30)))
        except Exception:
            return None
    return _cached(("news30", query), 3, go)


def _wiki_views(title):
    from urllib.parse import quote, unquote
    title = quote(unquote(title), safe="")
    end = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=6)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
           f"{title}/daily/{start:%Y%m%d}00/{end:%Y%m%d}00")
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.status_code == 200:
            WIKI_STATUS["ok"] += 1
            return int(sum(i.get("views", 0) for i in r.json().get("items", [])))
        WIKI_STATUS["failed"] += 1
        WIKI_STATUS["last_error"] = f"HTTP {r.status_code}"
        return None
    except Exception as exc:
        WIKI_STATUS["failed"] += 1
        WIKI_STATUS["last_error"] = type(exc).__name__
        return None


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _safe_news(row):
    try:
        return news_count(news_query(row))
    except Exception:
        return None


def news_query(row):
    if row["cls"] in ("UK stocks", "US stocks"):
        return f'"{row["name"]}" shares'
    if row["cls"] == "FX":
        return row["name"]
    return f'"{row["name"]}"'


def attention(df, top_per_class=15):
    """Looks up news headlines (7 days) and Wikipedia views (7 days) for the biggest movers."""
    df = df.copy()
    df["abs_best"] = df["best"].abs()
    # candidates: the biggest expected moves PER UNIT OF RISK (so it isn't just the most volatile assets)
    df["abs_score"] = df["score"].abs() if "score" in df else df["abs_best"]
    pick = df.sort_values("abs_score", ascending=False).groupby("cls").head(top_per_class).copy()
    rows = [r for _, r in pick.iterrows()]
    with ThreadPoolExecutor(max_workers=8) as pool:
        news = list(pool.map(_safe_news, rows))
        news30 = list(pool.map(lambda r: _safe(lambda: news_count_30(news_query(r))), rows))
        wv = list(pool.map(wiki_views_baseline, pick["wiki"].tolist()))
    pick["news"] = news
    pick["views"] = [v[0] for v in wv]
    # attention vs this asset's own normal: 1.0 = usual, 2.0 = twice as much attention as usual
    news_norm = [(n / (m / 30 * 7)) if (n is not None and m) else None for n, m in zip(news, news30)]
    wiki_norm = [(v[0] / v[1]) if (v[0] is not None and v[1]) else None for v in wv]
    pick["attn_vs_normal"] = [np.nanmean([x for x in (a, b) if x is not None]) if (a is not None or b is not None) else None
                              for a, b in zip(news_norm, wiki_norm)]
    ranks = []
    for col in ("news", "views"):
        vals = pd.to_numeric(pick[col], errors="coerce")
        ranks.append(np.log1p(vals).rank(pct=True) * 100)
    pick["attention"] = pd.concat(ranks, axis=1).mean(axis=1, skipna=True)
    pick["attention"] = pick["attention"].fillna(pick["attention"].median() if pick["attention"].notna().any() else 50)
    # "under the radar": big expected move, little attention
    pick["radar"] = pick["abs_score"].rank(pct=True) * 100 - pick["attention"]
    return pick


# ---------------------------------------------------------------- contrarian test

def weekly_extremes(prices, members):
    """Last week's top winner and loser in an asset class."""
    rows = []
    for ticker, name, _ in members:
        if ticker not in prices.columns:
            continue
        s = prices[ticker].dropna()
        if len(s) < 130:
            continue
        past = s.asof(s.index[-1] - pd.Timedelta(days=7))
        if pd.isna(past) or not past:
            continue
        rows.append((ticker, name, (float(s.iloc[-1]) / float(past) - 1) * 100))
    if not rows:
        return None, None
    rows.sort(key=lambda r: r[2])
    return rows[-1], rows[0]


def contrarian_history(prices, members, weeks=104):
    """
    Each Friday over the last ~2 years: find the class's top winner and loser of that week,
    then see what they did the following week.
    """
    tickers = [t for t, _, _ in members if t in prices.columns]
    if len(tickers) < 3:
        return None
    w = prices[tickers].resample("W-FRI").last().dropna(how="all")
    ret = w.pct_change(fill_method=None) * 100
    ret = ret.iloc[-weeks - 1:]
    win_next, lose_next = [], []
    for i in range(len(ret) - 1):
        row, nxt = ret.iloc[i].dropna(), ret.iloc[i + 1]
        if len(row) < 3:
            continue
        top, bottom = row.idxmax(), row.idxmin()
        if not pd.isna(nxt.get(top)):
            win_next.append(nxt[top])
        if not pd.isna(nxt.get(bottom)):
            lose_next.append(nxt[bottom])
    if len(win_next) < 10:
        return None
    win_next, lose_next = np.array(win_next), np.array(lose_next)
    return dict(n=len(win_next), winner_fell=float((win_next < 0).mean() * 100),
                winner_avg_next=float(win_next.mean()), loser_rose=float((lose_next > 0).mean() * 100),
                loser_avg_next=float(lose_next.mean()))


# ---------------------------------------------------------------- data analysis, explained

def describe(sims, name, horizon_label="next week", short=False):
    """
    Every descriptive statistic of the simulated outcomes, with what it means in general
    and what it means here. Returns a list of (statistic, value, what it is, what it tells us).
    `short=True` describes the outcome of SHORTING (profit when the price falls).
    """
    x = -sims if short else sims
    word = "your short's return" if short else "the price change"
    n = len(x)
    mean, med = float(x.mean()), float(np.median(x))
    mode = kde_mode(x)
    lo, hi = float(x.min()), float(x.max())
    q1, q3 = np.percentile(x, [25, 75])
    var = float(x.var(ddof=1))
    sd = float(np.sqrt(var))
    skew = float(((x - mean) ** 3).mean() / x.std() ** 3)
    kurt = float(((x - mean) ** 4).mean() / x.std() ** 4 - 3)
    p5, p95 = np.percentile(x, [5, 95])
    p_pos = float((x > 0).mean() * 100)
    se = sd / np.sqrt(n)
    ci = (mean - 1.96 * se, mean + 1.96 * se)
    f = lambda v: f"{v:+.2f}%"
    rows = [
        ("Mean (average)", f(mean),
         "Add up every outcome and divide by how many there are.",
         f"On average across all {n:,} simulations, {word} {horizon_label} is {f(mean)}."),
        ("Median", f(med),
         "The middle value when every outcome is lined up from lowest to highest. Half are above, half below.",
         f"Half of the simulations end above {f(med)} and half below. "
         + ("It's below the mean, so a few big gains are pulling the average up." if med < mean - 0.05 else
            "It's above the mean, so a few big losses are dragging the average down." if med > mean + 0.05 else
            "It's close to the mean, so the outcomes are fairly balanced.")),
        ("Mode (most likely)", f(mode),
         "The single most common outcome: the peak of the histogram. For continuous data it's estimated by "
         "smoothing the histogram (a kernel density estimate).",
         f"If you had to bet on one number, {f(mode)} is where outcomes cluster most."),
        ("Minimum / maximum", f"{f(lo)} / {f(hi)}",
         "The single worst and best outcomes in the simulation.",
         f"The most extreme simulated futures ranged from {f(lo)} to {f(hi)}. These are rare tail events."),
        ("Range", f"{hi - lo:.2f}pp",
         "Maximum minus minimum: the full spread of outcomes. Easy to read but sensitive to one extreme value.",
         f"There are {hi - lo:.1f} percentage points between the best and worst outcomes."),
        ("Quartiles (Q1 / Q3)", f"{f(q1)} / {f(q3)}",
         "Q1 is the value 25% of outcomes fall below; Q3 is the value 75% fall below.",
         f"A quarter of simulations do worse than {f(q1)}, and a quarter do better than {f(q3)}."),
        ("Interquartile range (IQR)", f"{q3 - q1:.2f}pp",
         "Q3 minus Q1: the spread of the middle 50% of outcomes. Unlike the range, it ignores the extremes.",
         f"The typical (middle half of) outcomes span {q3 - q1:.1f} percentage points."),
        ("Variance", f"{var:.2f}",
         "The average squared distance from the mean. It measures spread, but in squared units, so it's "
         "hard to read directly. Its square root is the standard deviation.",
         "Higher variance means more uncertainty. Compare it between assets rather than reading it alone."),
        ("Standard deviation", f"{sd:.2f}pp",
         "The typical distance of an outcome from the mean, in the same units as the data. Roughly two-thirds "
         "of outcomes fall within one standard deviation of the mean if the data is bell-shaped.",
         f"A typical outcome is about {sd:.1f} percentage points away from the average. That's the "
         f"asset's {'very high' if sd > 8 else 'high' if sd > 4 else 'moderate' if sd > 2 else 'low'} risk "
         f"over this period."),
        ("Skewness", f"{skew:+.2f}",
         "Whether the distribution leans one way. 0 = symmetrical. Positive = a long tail of big gains. "
         "Negative = a long tail of big losses.",
         ("Close to symmetrical: big ups and big downs are about as likely as each other." if abs(skew) < 0.2 else
          f"{'Positive' if skew > 0 else 'Negative'} skew: the rare extreme outcomes are more likely to be "
          f"{'big gains' if skew > 0 else 'big losses'}.")),
        ("Kurtosis (excess)", f"{kurt:+.2f}",
         "How heavy the tails are compared with a normal (bell-curve) distribution, which has excess kurtosis "
         "of 0. Higher = more extreme outcomes than a bell curve predicts.",
         ("Tails are close to a normal distribution." if kurt < 0.5 else
          "Fat tails: extreme moves happen more often than a bell curve would suggest, so plan for surprises.")),
        ("5th / 95th percentile", f"{f(p5)} / {f(p95)}",
         "5% of outcomes are below the 5th percentile and 5% are above the 95th. Together they give a 90% range.",
         f"In 90% of simulations, {word} lands between {f(p5)} and {f(p95)}. "
         f"The 5th percentile ({f(p5)}) is the 'Value at Risk': a bad week that happens about 1 time in 20."),
        ("Probability of a gain", f"{p_pos:.0f}%",
         "The share of simulations that end above zero.",
         f"{p_pos:.0f}% of simulated futures make money{' on the short' if short else ''}. "
         + ("That's barely better than a coin toss." if 45 <= p_pos <= 55 else
            "That's a meaningful tilt." if p_pos > 55 else "The odds are against it.")),
        ("95% confidence interval for the mean", f"{f(ci[0])} to {f(ci[1])}",
         "A range we're 95% confident contains the true average of the model, given how many simulations "
         "were run: mean ± 1.96 × (standard deviation ÷ √n).",
         "It's narrow because 10,000 simulations is a lot. The uncertainty here is in the market, not the "
         "maths. It doesn't mean the real-world outcome is that predictable."),
    ]
    best_name, best, reason, checks = choose_average(x)
    return rows, dict(mean=mean, median=med, mode=mode, p_pos=p_pos, p5=float(p5), p95=float(p95), sd=sd,
                      best=best, best_type=best_name, best_reason=reason, checks=checks)
