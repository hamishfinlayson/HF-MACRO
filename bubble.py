"""
bubble.py - BUBBLE WATCH (PC version only).

A checklist of warning signs that came before past stock-market bubbles burst: the Nasdaq in 1987, 2000,
2008, 2018, 2020, 2022 and 2025, Japan 1989, China 2007 and 2015, Hong Kong 2007 and 2021, and Bitcoin.

Every sign gets a light each week:
  🔴 RED   = no sign of it yet
  🟠 AMBER = some sign of it
  🟢 GREEN = it has happened / is happening now
(These colours were chosen by Hamish: green means "this warning is showing", not "good".)

Score = greens + half the ambers, out of the signs that have data. The KEY (what a score means, how often a
big fall followed and how long it took) is worked out from history: built on 1985-2010, checked on 2011-2026.

The signs are grouped like a fuse burning down, because bubbles burst in stages:
  1 BUILD-UP  -> prices going up too fast (the bubble shape)
  2 PRICEY    -> too expensive and too crowded
  3 FUEL      -> borrowed money pouring in
  4 TRIGGER   -> something that usually pops bubbles (rate rises, curve, dollar, oil...)
  5 CRACKS    -> stress showing underneath (credit, fear, defensives, leaders slipping, jobs)
  6 BREAK     -> the fall has started
Only the public data sources HF Macro already uses (Yahoo Finance and FRED).
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- what to download
YAHOO = ["^IXIC", "^GSPC", "^NDX", "^DJI", "^SOX", "^RUT", "^VIX", "^VIX3M", "^TNX", "^IRX",
         "RSP", "SPY", "QQQ", "IWM", "XLU", "XLK", "XLP", "SMH", "ARKK", "HYG", "LQD", "TLT", "GLD",
         "GC=F", "HG=F", "CL=F", "DX-Y.NYB", "^N225", "000001.SS", "000300.SS", "^HSI", "^KS11", "^TWII",
         "^STOXX50E", "^FTSE", "^GDAXI", "BTC-USD", "ETH-USD",
         "NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AVGO", "TSLA", "ORCL", "AMD", "TSM", "PLTR", "SMCI",
         "CSCO", "INTC", "QCOM", "MU", "ASML", "CRWV", "ARM", "NOW", "CRM", "ADBE", "IBM", "SNOW", "COIN"]
FRED = ["BAA10Y", "BAMLH0A0HYM2", "T10Y3M", "DFF", "DGS10", "DFII10", "ICSA", "SAHMREALTIME", "NFCI",
        "STLFSI4", "M2SL", "WALCL", "INDPRO", "UMCSENT", "CPIAUCSL", "GDP", "NCBEILQ027S", "CP", "DTWEXBGS",
        "BUSLOANS", "DRTSCILM", "TOTALSL", "BOGZ1FL663067003Q", "BOGZ1FL153064486Q"]

# Days after the end of the period before FRED figures are actually published (so tests can't peek)
LAG_DAYS = {"ICSA": 6, "NFCI": 5, "STLFSI4": 6, "WALCL": 2, "M2SL": 28, "INDPRO": 17, "UMCSENT": 0,
            "CPIAUCSL": 14, "SAHMREALTIME": 8, "BUSLOANS": 10, "TOTALSL": 40, "GDP": 60, "CP": 90,
            "NCBEILQ027S": 75, "BOGZ1FL663067003Q": 75, "BOGZ1FL153064486Q": 75, "DRTSCILM": 35}
MONTHLY_END = {"M2SL", "INDPRO", "UMCSENT", "CPIAUCSL", "SAHMREALTIME", "TOTALSL", "BUSLOANS"}  # dated at month start
QUARTERLY = {"GDP", "CP", "NCBEILQ027S", "BOGZ1FL663067003Q", "BOGZ1FL153064486Q", "DRTSCILM"}

TECH = ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AVGO", "TSLA", "ORCL", "AMD", "TSM", "PLTR", "SMCI",
        "CSCO", "INTC", "QCOM", "MU", "ASML", "ARM", "NOW", "CRM", "ADBE", "IBM", "SNOW", "CRWV"]
AI_GIANTS = ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AVGO", "TSLA"]   # the "Magnificent 7" + Broadcom
SPEC = ["ARKK", "COIN", "PLTR", "SMCI", "CRWV", "BTC-USD", "ETH-USD"]
WORLD = ["^GSPC", "^N225", "^HSI", "^STOXX50E", "^FTSE", "^GDAXI", "^KS11", "^TWII", "000001.SS"]
N_LEADERS = 6

STAGES = {
    1: ("BUILD-UP", "Prices going up too fast: the shape every bubble has"),
    2: ("PRICEY", "Too expensive and too crowded"),
    3: ("FUEL", "Borrowed and easy money pouring in"),
    4: ("TRIGGER", "The things that usually pop bubbles"),
    5: ("CRACKS", "Stress showing underneath while the headline index still looks fine"),
    6: ("BREAK", "The fall has started"),
}
LIGHT = {0: "🔴", 1: "🟠", 2: "🟢"}
LIGHT_WORD = {0: "No sign yet", 1: "Some sign", 2: "Happening"}

# Past bubbles the "looks like" matcher compares today with (name, Yahoo code, the top)
ANALOGS = [
    ("Nasdaq dot-com 2000", "^IXIC", "2000-03-10"),
    ("Japan Nikkei 1989", "^N225", "1989-12-29"),
    ("China Shanghai 2007", "000001.SS", "2007-10-16"),
    ("China Shanghai 2015", "000001.SS", "2015-06-12"),
    ("Hong Kong 2007", "^HSI", "2007-10-30"),
    ("Nasdaq 2007 (before 2008)", "^IXIC", "2007-10-31"),
    ("Nasdaq tech 2021", "^IXIC", "2021-11-19"),
    ("Hong Kong 2021", "^HSI", "2021-02-17"),
    ("Bitcoin 2017", "BTC-USD", "2017-12-16"),
    ("Bitcoin 2021", "BTC-USD", "2021-11-08"),
    ("Nasdaq 1987", "^IXIC", "1987-08-26"),
    ("Semiconductors 2000", "^SOX", "2000-03-10"),
]


# ---------------------------------------------------------------- data
def from_rows(df):
    """df with columns name, date, value  ->  {name: daily Series}"""
    out = {}
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for n, g in df.groupby("name"):
        s = pd.Series(g["value"].values.astype(float), index=pd.DatetimeIndex(g["date"].values)).sort_index()
        out[n] = s[~s.index.duplicated(keep="last")]
    return out


def download(fetch_yahoo_close, fetch_fred, fred_key, progress=None):
    """Downloads everything. fetch_yahoo_close(code) -> (close Series, volume Series or None)."""
    rows = []
    jobs = [("Y", c) for c in YAHOO] + [("F", c) for c in FRED]
    for i, (kind, c) in enumerate(jobs):
        if progress:
            progress((i + 1) / len(jobs), c)
        try:
            if kind == "Y":
                close, vol = fetch_yahoo_close(c)
                rows.append(pd.DataFrame({"name": c, "date": close.index, "value": close.values}))
                if vol is not None and len(vol):
                    rows.append(pd.DataFrame({"name": c + "|vol", "date": vol.index, "value": vol.values}))
            elif fred_key:
                s = fetch_fred(c, fred_key)
                rows.append(pd.DataFrame({"name": "FRED:" + c, "date": s.index, "value": s.values}))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=["name", "date", "value"])
    df = pd.concat(rows, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize() if hasattr(
        pd.to_datetime(df["date"]).dt, "tz") and pd.to_datetime(df["date"]).dt.tz is not None else pd.to_datetime(df["date"]).dt.normalize()
    return df


class Data:
    def __init__(self, S, end=None):
        self.S = S
        last = max((s.index.max() for k, s in S.items() if not k.startswith("FRED:") and len(s)), default=None)
        end = pd.Timestamp(end) if end is not None else last
        self.W = pd.date_range("1985-01-04", end, freq="W-FRI")

    def has(self, name):
        return name in self.S and len(self.S[name].dropna()) > 0

    def daily(self, name):
        return self.S[name].dropna() if self.has(name) else None

    def wk(self, name, limit=6):
        """Weekly value, as known on each Friday (FRED figures moved to their publication date)."""
        if not self.has(name):
            return pd.Series(np.nan, index=self.W)
        s = self.S[name].dropna()
        code = name.replace("FRED:", "")
        if name.startswith("FRED:"):
            shift = pd.Timedelta(days=LAG_DAYS.get(code, 1))
            if code in MONTHLY_END:
                shift += pd.Timedelta(days=31)
            if code in QUARTERLY:
                shift += pd.Timedelta(days=91)
                limit = 30
            elif code in MONTHLY_END:
                limit = 10
            s = s.copy()
            s.index = s.index + shift
        w = s.resample("W-FRI").last()
        return w.reindex(self.W).ffill(limit=limit)


def basket(D, names, min_n=3):
    """Equal-weight index of whichever names have prices (needs at least min_n)."""
    px = pd.DataFrame({n: D.daily(n) for n in names if D.has(n)})
    if px.empty:
        return None
    r = px.pct_change(fill_method=None)
    r = r.where(r.abs() < 0.6)
    n = r.notna().sum(axis=1)
    m = r.mean(axis=1).where(n >= min_n)
    m = m.dropna()
    return (1 + m).cumprod() * 100 if len(m) else None


def leaders(D):
    """THE LEADERS: the 6 big tech stocks that went up most over the last 2 years, re-picked each month.
    In 1999 that picks Cisco, Qualcomm, Oracle...; today it picks the AI winners. No hindsight."""
    px = pd.DataFrame({n: D.daily(n) for n in TECH if D.has(n)})
    if px.empty:
        return None, {}
    px = px[px.index >= "1990-01-01"].ffill(limit=5)
    r = px.pct_change(fill_method=None).where(lambda x: x.abs() < 0.6)
    month_ends = px.resample("ME").last().index
    two_y = px / px.shift(504) - 1
    picks, out, cur = {}, [], []
    idx = px.index
    me_set = set(px.groupby(px.index.to_period("M")).apply(lambda g: g.index[-1]))
    for d in idx:
        if out:
            day = r.loc[d, cur].mean() if cur else np.nan
            out.append(day if day == day else 0.0)
        else:
            out.append(0.0)
        if d in me_set:
            row = two_y.loc[d].dropna()
            if len(row) >= N_LEADERS:
                cur = list(row.sort_values(ascending=False).index[:N_LEADERS])
                picks[d] = cur
    s = pd.Series(out, index=idx)
    first = min(picks) if picks else None
    if first is None:
        return None, {}
    s = s[s.index > first]
    return (1 + s).cumprod() * 100, picks


# ---------------------------------------------------------------- small helpers (all weekly)
def wk_of(D, s, limit=6):
    if s is None:
        return pd.Series(np.nan, index=D.W)
    return s.resample("W-FRI").last().reindex(D.W).ffill(limit=limit)


def chg(w, weeks):
    return (w / w.shift(weeks) - 1) * 100


def diff(w, weeks):
    return w - w.shift(weeks)


def above_ma(daily, days=200):
    if daily is None:
        return None
    return (daily / daily.rolling(days, min_periods=int(days * 0.8)).mean() - 1) * 100


def drawdown(daily, days=252):
    if daily is None:
        return None
    return (daily / daily.rolling(days, min_periods=20).max() - 1) * 100


def expanding_pct(w, min_obs=104):
    """Where each value sits in its own history up to then (0-100). No peeking at the future."""
    v = w.dropna()
    out = pd.Series(np.nan, index=w.index)
    if len(v) < min_obs:
        return out
    arr = v.values
    res = [np.nan] * len(arr)
    for i in range(min_obs, len(arr)):
        res[i] = (arr[:i + 1] < arr[i]).mean() * 100
    out.loc[v.index] = res
    return out.ffill(limit=30)


def lights(value, amber, green, higher=True, when=None):
    """0 red / 1 amber / 2 green; NaN where there's no data. `when` = extra condition that must be true."""
    v = value
    if higher:
        st = np.where(v >= green, 2, np.where(v >= amber, 1, 0))
    else:
        st = np.where(v <= green, 2, np.where(v <= amber, 1, 0))
    st = pd.Series(st, index=v.index, dtype=float).where(v.notna())
    if when is not None:
        st = st.where(when.fillna(False) | st.isna(), 0.0)
    return st


# ---------------------------------------------------------------- the signs
def build(D):
    """Returns (list of signs, extras). Each sign: id, stage, name, what, lesson, rule, unit, value, status."""
    W = D.W
    ix = D.daily("^IXIC")
    ixw = wk_of(D, ix)
    near_high = wk_of(D, drawdown(ix)) > -5 if ix is not None else pd.Series(False, index=W)
    near_high10 = wk_of(D, drawdown(ix)) > -10 if ix is not None else pd.Series(False, index=W)
    lead, picks = leaders(D)
    leadw = wk_of(D, lead)
    spec = basket(D, SPEC, min_n=2)
    specw = wk_of(D, spec)
    signs = []

    def add(stage, sid, name, value, status, what, lesson, rule, unit="%"):
        signs.append(dict(id=sid, stage=stage, name=name, value=value.reindex(W), status=status.reindex(W),
                          what=what, lesson=lesson, rule=rule, unit=unit))

    # ======================= 1 BUILD-UP
    v = chg(leadw, 104)
    add(1, "lead2y", "The leaders up 100% in 2 years", v, lights(v, 60, 100),
        "The 6 best big tech stocks (re-picked monthly, today the AI winners) have doubled in 2 years.",
        "Harvard 'Bubbles for Fama': after a 100% 2-year run, about half crash 40%+ within 2 years; after 150%, 80% do.",
        "🟠 up 60%+ · 🟢 up 100%+")
    v = chg(ixw, 104)
    add(1, "ndq2y", "Nasdaq up fast over 2 years", v, lights(v, 40, 70),
        "The whole Nasdaq, not just the leaders, has run up hard.", "Nasdaq was up 150%+ in 2 years by March 2000.",
        "🟠 up 40%+ · 🟢 up 70%+")
    v = chg(wk_of(D, D.daily("^SOX")), 104)
    add(1, "sox2y", "Chip stocks up fast over 2 years", v, lights(v, 70, 120),
        "Semiconductors are the picks and shovels of this boom (and were in 2000).",
        "Chip stocks rose ~400% in 1998-2000 then fell 80%+.", "🟠 up 70%+ · 🟢 up 120%+")
    a1, a0 = chg(leadw, 52), chg(leadw, 52).shift(52)
    v = a1 - a0
    add(1, "accel", "Speeding up (acceleration)", v, lights(v, 0, 25, when=a1 > 30),
        "This year's gain is bigger than last year's: the rise is speeding up, not slowing.",
        "The strongest single crash warning in the Harvard bubble study.",
        "only counts if the leaders are up 30%+ this year · 🟠 faster than last year · 🟢 25+ points faster")
    v = wk_of(D, above_ma(ix))
    add(1, "stretch", "Nasdaq stretched far above its 200-day average", v, lights(v, 12, 20),
        "How far the price is above its long-run average. Rubber bands snap back.",
        "Nasdaq was 50%+ above its 200-day in early 2000.", "🟠 12%+ above · 🟢 20%+ above")
    vol = lambda d: (np.log(d).diff().rolling(63, min_periods=40).std() * np.sqrt(252) * 100) if d is not None else None
    lv = wk_of(D, vol(lead))
    v = lv - lv.shift(52)
    add(1, "volup", "Shakier while still rising", v, lights(v, 5, 12, when=a1 > 30),
        "The leaders are swinging more wildly than a year ago even though they're still going up.",
        "Harvard study: rising volatility in a boom is one of the best crash warnings (and a rule that sold on it beat holding).",
        "only counts if the leaders are up 30%+ · 🟠 5+ points more volatile · 🟢 12+ points")
    v = chg(ixw, 26)
    add(1, "parab", "Going vertical (6-month surge)", v, lights(v, 20, 30),
        "A huge gain in just 6 months: the 'blow-off' part of a bubble.",
        "Nasdaq +80% in the 6 months before March 2000; Shanghai +100% in 6 months before June 2015.",
        "🟠 up 20%+ in 6 months · 🟢 up 30%+")
    if ix is not None:
        lg = np.log(ixw)
        trend = lg.rolling(520, min_periods=260).apply(lambda y: np.polyval(np.polyfit(np.arange(len(y)), y, 1), len(y) - 1), raw=True)
        v = (np.exp(lg - trend) - 1) * 100
    else:
        v = pd.Series(np.nan, index=W)
    add(1, "trend", "Way above its 10-year trend line", v, lights(v, 25, 45),
        "Draw a straight line through 10 years of the Nasdaq: how far above it are we?",
        "In 2000 the Nasdaq was ~150% above its trend; in 2021 ~45%.", "🟠 25%+ above · 🟢 45%+ above")
    v = chg(specw, 52)
    add(1, "spec", "Speculative stuff flying", v, lights(v, 80, 150),
        "Bitcoin, Ether, ARK Innovation, Coinbase, Palantir, Super Micro and CoreWeave: the riskiest stocks and coins.",
        "Meme stocks, ARKK and crypto all went parabolic in 2020-21 before the 2022 crash.", "🟠 up 80%+ in a year · 🟢 up 150%+")
    v = chg(wk_of(D, D.daily("BTC-USD")), 52)
    add(1, "btc", "Bitcoin boom", v, lights(v, 100, 200),
        "Crypto is the purest gauge of 'free money' speculation.", "Bitcoin +1,300% in 2017, +500% into 2021: both ended in 75%+ crashes.",
        "🟠 up 100%+ in a year · 🟢 up 200%+")
    vd = D.daily("^IXIC|vol")
    v = wk_of(D, vd.rolling(63, min_periods=40).mean() / vd.rolling(504, min_periods=250).mean()) if vd is not None else pd.Series(np.nan, index=W)
    add(1, "volume", "Trading frenzy (volume surge)", v, lights(v, 1.25, 1.5),
        "Shares are changing hands much faster than normal: new money and day traders piling in.",
        "China 2015: 40 million new trading accounts in a year and record turnover.", "🟠 25%+ busier than normal · 🟢 50%+ busier", unit="x")
    if ix is not None:
        up = (ix.pct_change() > 0.02).astype(float).rolling(63).sum()
        v = wk_of(D, up)
    else:
        v = pd.Series(np.nan, index=W)
    add(1, "updays", "Lots of huge up days near the highs", v, lights(v, 6, 10, when=near_high),
        "Calm markets rise slowly. Bubbles have lots of +2% days.", "1999-2000 and 2020-21 both had clusters of huge up days at the top.",
        "only counts within 5% of the high · 🟠 6+ days of +2% in 3 months · 🟢 10+", unit="days")
    world = pd.DataFrame({n: chg(wk_of(D, D.daily(n)), 52) for n in WORLD if D.has(n)})
    v = (world > 20).sum(axis=1) / world.notna().sum(axis=1) * 100 if not world.empty else pd.Series(np.nan, index=W)
    v = v.where(world.notna().sum(axis=1) >= 4) if not world.empty else v
    add(1, "world", "Everything everywhere going up", v, lights(v, 50, 75),
        "Share of the world's big stock markets up 20%+ in a year. When everyone is euphoric, there's no one left to buy.",
        "1999, 2007 and 2021: almost every market was up big at the same time.", "🟠 half up 20%+ · 🟢 three-quarters")
    asia = pd.concat([chg(wk_of(D, D.daily(n)), 52) for n in ("^TWII", "^KS11") if D.has(n)], axis=1)
    v = asia.mean(axis=1) if not asia.empty else pd.Series(np.nan, index=W)
    add(1, "asia", "Taiwan & Korea chip markets surging", v, lights(v, 30, 50),
        "Taiwan (TSMC) and Korea (Samsung, SK Hynix) are where AI chips are made.", "Both surged ~70% into 2000 and 2021.",
        "🟠 up 30%+ in a year · 🟢 up 50%+")

    # ======================= 2 PRICEY
    if D.has("FRED:NCBEILQ027S") and D.has("FRED:GDP"):
        v = D.wk("FRED:NCBEILQ027S") / D.wk("FRED:GDP")
        p = expanding_pct(v)
    else:
        v = p = pd.Series(np.nan, index=W)
    add(2, "buffett", "Buffett indicator (stocks vs the economy)", p, lights(p, 90, 97),
        "Value of all US company shares divided by GDP. Warren Buffett calls it 'the best single measure'. Shown as where it sits in its own history (100 = highest ever).",
        "Hit records in 2000 and 2021, both before big falls.", "🟠 top 10% of history · 🟢 top 3%", unit="pct")
    v = D.wk("FRED:BOGZ1FL153064486Q")
    p = expanding_pct(v)
    add(2, "hholds", "Households all-in on shares", p, lights(p, 90, 97),
        "How much of American families' money is in shares. When everyone is already in, who's left to buy?",
        "Peaked in early 2000 and late 2021; one of the best long-term return predictors.", "🟠 top 10% of history · 🟢 top 3%", unit="pct")
    sp, cpi = wk_of(D, D.daily("^GSPC")), D.wk("FRED:CPIAUCSL")
    real = sp / cpi
    v = real / real.rolling(520, min_periods=400).mean()
    p = expanding_pct(v)
    add(2, "cape", "Price vs 10-year average (CAPE-style)", p, lights(p, 90, 97),
        "Inflation-adjusted S&P 500 vs its own 10-year average, like Shiller's CAPE without earnings.",
        "At records in 1929, 2000 and 2021.", "🟠 top 10% of history · 🟢 top 3%", unit="pct")
    v = chg(wk_of(D, D.daily("^NDX")), 156) - chg(ixw, 156)
    add(2, "conc", "A few giants carrying the market", v, lights(v, 10, 20),
        "The biggest 100 Nasdaq stocks beating the whole Nasdaq (3,000+ stocks) over 3 years: the market rests on fewer shoulders.",
        "Concentration hit records in 2000 and again with today's 'Magnificent 7'.", "🟠 giants 10+ points ahead · 🟢 20+ points ahead", unit="pts")
    tech = pd.DataFrame({n: wk_of(D, above_ma(D.daily(n))) for n in TECH if D.has(n)})
    breadth = (tech > 0).sum(axis=1) / tech.notna().sum(axis=1) * 100
    breadth = breadth.where(tech.notna().sum(axis=1) >= 8)
    add(2, "narrow", "New highs with fewer stocks joining in", breadth, lights(breadth, 70, 50, higher=False, when=near_high),
        "Nasdaq near its high, but fewer of the big tech names are above their 200-day average.",
        "Before 2000 and 2021 fewer and fewer stocks made new highs: the generals led, the soldiers stopped following.",
        "only counts within 5% of the high · 🟠 fewer than 70% above · 🟢 fewer than 50%", unit="%")
    rut = D.daily("^RUT")
    v = chg(wk_of(D, rut), 52) - chg(sp, 52)
    add(2, "small", "Small companies left behind", v, lights(v, -8, -15, higher=False),
        "Russell 2000 small caps lagging the S&P 500: the boom is only in the big names.", "1998-99 and 2021.",
        "🟠 8+ points behind · 🟢 15+ points behind", unit="pts")
    v = wk_of(D, D.daily("^NDX")) / sp
    p = expanding_pct(v / v.rolling(260, min_periods=200).mean())
    add(2, "techshare", "Tech pulling far ahead of the rest", p, lights(p, 90, 97),
        "Nasdaq 100 vs the S&P 500 compared with its 5-year normal.", "Record in 2000.", "🟠 top 10% of history · 🟢 top 3%", unit="pct")
    v = D.wk("FRED:DFII10")
    add(2, "realrate", "Shares ignoring high real interest rates", v, lights(v, 1.5, 2.0, when=near_high),
        "Bonds now pay well above inflation, yet shares are at their highs: shares are priced as if money is still free.",
        "Real rates were ~4% in 2000 while tech traded at 100x earnings.", "only counts within 5% of the high · 🟠 real 10-year yield 1.5%+ · 🟢 2%+", unit="%")
    vix = wk_of(D, D.daily("^VIX"))
    v = vix.rolling(13, min_periods=8).mean()
    add(2, "calm", "Too calm (low fear gauge)", v, lights(v, 14, 12, higher=False),
        "VIX averaging very low: nobody is paying for protection.", "VIX sat near 10 before Feb 2018's 'Volmageddon' and in 2007.",
        "🟠 3-month average under 14 · 🟢 under 12", unit="")
    b = D.wk("FRED:BAA10Y")
    p = expanding_pct(b)
    add(2, "cheapcredit", "Lending too cheap (tight credit spreads)", p, lights(p, 10, 5, higher=False),
        "The extra interest risky companies pay is near record lows: lenders aren't worried about anything.",
        "Spreads were at lows in 2007 and 2021.", "🟠 bottom 10% of history · 🟢 bottom 5%", unit="pct")

    # ======================= 3 FUEL
    m = D.wk("FRED:BOGZ1FL663067003Q")
    v = chg(m, 52)
    add(3, "margin", "Borrowing to buy shares surging", v, lights(v, 20, 35),
        "Money lent to investors by brokers (margin debt), growth over a year.",
        "China 2015: margin lending went from 400bn to 2.2tn yuan in a year. US margin debt also peaked in 2000, 2007 and 2021.",
        "🟠 up 20%+ in a year · 🟢 up 35%+")
    q = chg(m, 13)
    surge = v.rolling(52, min_periods=1).max() > 20
    add(3, "marginroll", "Borrowing rolling over after a surge", q, lights(q, 0, -5, higher=False, when=surge),
        "After a margin surge, borrowing starts falling: forced selling begins.",
        "China June 2015: the regulator capped margin lending and the market fell 30% in a month.",
        "only counts after a 20%+ surge · 🟠 stopped growing · 🟢 down 5%+ in a quarter")
    v = chg(D.wk("FRED:BUSLOANS"), 52)
    add(3, "loans", "Bank loans to business booming", v, lights(v, 10, 15),
        "Fast credit growth funds the boom (today: AI data centres borrowing heavily).", "Loan growth peaked in 2000 and 2007.",
        "🟠 up 10%+ in a year · 🟢 up 15%+")
    v = chg(D.wk("FRED:TOTALSL"), 52)
    add(3, "consumer", "Consumer borrowing booming", v, lights(v, 8, 10),
        "Households borrowing fast to spend.", "High in 2000 and 2022.", "🟠 up 8%+ · 🟢 up 10%+")
    v = chg(D.wk("FRED:M2SL"), 52)
    add(3, "money", "Flood of money (M2 growth)", v, lights(v, 9, 14),
        "Money supply growing fast: cash looking for a home.", "M2 +25% in 2021 fuelled meme stocks and crypto.",
        "🟠 up 9%+ in a year · 🟢 up 14%+")

    # ======================= 4 TRIGGER
    ff = D.wk("FRED:DFF")
    v = diff(ff, 52)
    add(4, "hikes", "Central bank raising rates", v, lights(v, 0.75, 1.5),
        "The Fed has raised rates over the last year.", "Japan 1989, Nasdaq 2000, China 2007, tech 2022: all popped by rate rises.",
        "🟠 up 0.75+ points in a year · 🟢 up 1.5+", unit="pts")
    peak = ff.rolling(78, min_periods=20).max()
    rose = (peak - ff.rolling(156, min_periods=20).min()) >= 1.0
    cut = peak - ff
    first_cut = (cut >= 0.4) & (cut.shift(1) < 0.4)
    weeks_since = pd.Series(np.nan, index=W)
    last = None
    for i, d in enumerate(W):
        if first_cut.iloc[i] and rose.iloc[i]:
            last = i
        if last is not None:
            weeks_since.iloc[i] = i - last
    v = weeks_since
    st = pd.Series(np.where(v <= 26, 2, np.where(v <= 52, 1, 0)), index=W, dtype=float).where(ff.notna())
    add(4, "firstcut", "The Fed's first cut after hiking (the trap)", v, st,
        "Sounds bullish, but the first rate cut after a hiking cycle usually means the Fed has seen trouble coming.",
        "First cuts came in Jan 2001, Sep 2007, Jul 2019 and Sep 2024: big falls followed within months each time.",
        "🟠 6-12 months since the first cut · 🟢 within 6 months", unit="wks")
    v = diff(D.wk("FRED:DGS10"), 52)
    add(4, "yields", "Bond yields jumping", v, lights(v, 0.75, 1.25),
        "The 10-year Treasury yield has risen fast: future profits are worth less today.", "1987 crash, 1994, 2018 and 2022.",
        "🟠 up 0.75+ points in a year · 🟢 up 1.25+", unit="pts")
    v = diff(D.wk("FRED:DFII10"), 26)
    add(4, "realjump", "Real interest rates jumping", v, lights(v, 0.5, 0.9),
        "Inflation-adjusted yields rising fast. Long-dated growth stocks (AI) are the most sensitive.", "2022: real yields +2.5 points, Nasdaq -35%.",
        "🟠 up 0.5+ points in 6 months · 🟢 up 0.9+", unit="pts")
    c = D.wk("FRED:T10Y3M")
    add(4, "invert", "Yield curve upside down", c, lights(c, 0, -0.75, higher=False),
        "Short-term rates above long-term ones. Has come before every US recession since 1970.", "Inverted 2000, 2006-07, 2019, 2022-24.",
        "🟠 inverted · 🟢 deeply inverted (-0.75 or lower)", unit="pts")
    was_inv = c.rolling(78, min_periods=10).min() < -0.25
    v = c - c.rolling(78, min_periods=10).min()
    add(4, "uninvert", "Yield curve un-inverting (the real timer)", v, lights(v, 0.5, 0.75, when=was_inv & (c > -0.25)),
        "The curve flips back to normal after being upside down. Historically, crashes and recessions start here, not at the inversion.",
        "Un-inverted in early 2001, mid-2007 and 2019, each just before stocks fell hard.",
        "only counts after an inversion · 🟠 rebounding 0.5+ points · 🟢 0.75+ and back near normal", unit="pts")
    dx = D.wk("FRED:DTWEXBGS")
    dxf = wk_of(D, D.daily("DX-Y.NYB"))
    v = chg(dx, 52).combine_first(chg(dxf, 52))
    add(4, "dollar", "Dollar surging", v, lights(v, 6, 10),
        "A fast-rising dollar drains money from the world and squeezes borrowers.", "1997-98, 2000, 2008 and 2022.",
        "🟠 up 6%+ in a year · 🟢 up 10%+")
    v = chg(wk_of(D, D.daily("CL=F")), 52)
    add(4, "oil", "Oil price shock", v, lights(v, 40, 70),
        "A big oil spike acts like a tax on everyone.", "Oil doubled before the 1990, 2000 and 2008 crashes.", "🟠 up 40%+ in a year · 🟢 up 70%+")
    infl = chg(D.wk("FRED:CPIAUCSL"), 52)
    v = infl - infl.shift(26)
    add(4, "inflation", "Inflation speeding back up", v, lights(v, 0.75, 1.5),
        "Rising inflation forces central banks to tighten.", "2021-22 and 1987.", "🟠 up 0.75+ points in 6 months · 🟢 up 1.5+", unit="pts")
    v = chg(D.wk("FRED:WALCL"), 52)
    add(4, "qt", "Fed draining money (QT)", v, lights(v, -3, -8, higher=False),
        "The Fed's balance sheet shrinking: it's pulling cash out of the system.", "2018 and 2022 sell-offs both came with QT.",
        "🟠 down 3%+ in a year · 🟢 down 8%+")
    v = chg(D.wk("FRED:M2SL"), 52)
    add(4, "m2shrink", "Money supply shrinking", v, lights(v, 2, 0, higher=False),
        "Money supply growing slowly or shrinking: the punch bowl is being taken away.", "M2 shrank in 2022-23 for the first time since the 1930s.",
        "🟠 growing under 2% · 🟢 shrinking")
    v = D.wk("FRED:DRTSCILM")
    add(4, "banks", "Banks tightening lending", v, lights(v, 10, 25),
        "Fed survey: share of banks making it harder to borrow.", "Spiked in 2000, 2007-08 and 2022-23.",
        "🟠 10%+ of banks tightening · 🟢 25%+", unit="%")

    # ======================= 5 CRACKS
    v = b - b.rolling(26, min_periods=8).min()
    add(5, "spreads", "Credit spreads widening", v, lights(v, 0.3, 0.6),
        "Risky companies suddenly paying more to borrow. Bond markets usually smell trouble before stocks.",
        "Spreads widened from mid-2007, months before stocks topped.", "🟠 up 0.3+ points from the low · 🟢 up 0.6+", unit="pts")
    h = D.wk("FRED:BAMLH0A0HYM2")
    v = h - h.rolling(26, min_periods=8).min()
    add(5, "junk", "Junk bond spreads jumping", v, lights(v, 0.75, 1.5),
        "Same idea for the riskiest companies (data only from the last few years).", "2007, 2015, 2018, 2020, 2022.",
        "🟠 up 0.75+ points · 🟢 up 1.5+", unit="pts")
    n = D.wk("FRED:NFCI")
    v = n - n.rolling(26, min_periods=8).min()
    add(5, "conds", "Financial conditions tightening", v, lights(v, 0.15, 0.35),
        "Chicago Fed index of how easy it is to get money (credit, shares, banks, borrowing).", "2000, 2007, 2018, 2022.",
        "🟠 tighter by 0.15+ · 🟢 by 0.35+", unit="")
    v = D.wk("FRED:STLFSI4")
    add(5, "stress", "Financial stress index above normal", v, lights(v, 0, 1),
        "St. Louis Fed stress index (0 = normal).", "2008, 2020, 2022.", "🟠 above 0 · 🟢 above 1", unit="")
    v = vix.rolling(4, min_periods=2).mean() / vix.rolling(26, min_periods=10).min()
    add(5, "fear", "Fear waking up from calm", v, lights(v, 1.5, 2.0),
        "VIX jumping well above its recent low.", "Feb 2018, Feb 2020, Aug 2024.", "🟠 50% above its low · 🟢 double", unit="x")
    v3 = wk_of(D, D.daily("^VIX3M"))
    v = (vix / v3).rolling(2, min_periods=1).mean()
    add(5, "vixcurve", "Short-term fear above long-term fear", v, lights(v, 0.95, 1.05),
        "When near-term protection costs more than 3-month protection, traders want cover NOW.", "Flipped in 2008, 2018, 2020, 2022.",
        "🟠 ratio above 0.95 · 🟢 above 1.05", unit="x")
    dfn = (wk_of(D, D.daily("XLU")) / wk_of(D, D.daily("XLU")).shift(13) + wk_of(D, D.daily("XLP")) / wk_of(D, D.daily("XLP")).shift(13)) / 2
    v = (dfn - wk_of(D, D.daily("XLK")) / wk_of(D, D.daily("XLK")).shift(13)) * 100
    add(5, "defens", "Safe stocks beating tech", v, lights(v, 5, 10),
        "Utilities and supermarkets beating tech over 3 months: big money quietly hiding.", "Late 2000, 2007, 2022.",
        "🟠 5+ points ahead · 🟢 10+ points ahead", unit="pts")
    gold = wk_of(D, D.daily("GC=F"))
    v = chg(gold, 26) - chg(sp, 26)
    add(5, "gold", "Gold beating shares", v, lights(v, 10, 20),
        "Gold doing much better than the S&P 500 over 6 months.", "2000-01, 2007-08, 2022.", "🟠 10+ points ahead · 🟢 20+", unit="pts")
    cu = wk_of(D, D.daily("HG=F"))
    v = chg(cu / gold, 26)
    add(5, "copper", "Copper falling vs gold (growth scare)", v, lights(v, -10, -20, higher=False),
        "Copper (used by industry) falling against gold (a safe haven): the economy is slowing.", "2008, 2015, 2018, 2022.",
        "🟠 down 10%+ in 6 months · 🟢 down 20%+")
    v = wk_of(D, drawdown(spec))
    add(5, "specbreak", "Speculative stuff cracking first", v, lights(v, -30, -45, higher=False, when=near_high10),
        "The riskiest assets are already falling while the Nasdaq still looks fine. The froth always goes first.",
        "ARKK peaked Feb 2021 and Bitcoin Nov 2021, before the Nasdaq. In 2000 the dot-com small caps cracked first.",
        "only counts with Nasdaq within 10% of high · 🟠 down 30%+ from the high · 🟢 down 45%+")
    if lead is not None and picks:
        pk = pd.Series(picks)
        dates = pk.index
        aboves = {n: above_ma(D.daily(n)) for n in TECH if D.has(n)}
        vals = []
        for d in W:
            j = dates.searchsorted(d, side="right") - 1
            if j < 0:
                vals.append(np.nan)
                continue
            names = pk.iloc[j]
            xs = [aboves[n].asof(d) for n in names if n in aboves]
            xs = [x for x in xs if x == x]
            vals.append(np.mean([x < 0 for x in xs]) * 100 if len(xs) >= 4 else np.nan)
        v = pd.Series(vals, index=W)
    else:
        v = pd.Series(np.nan, index=W)
    add(5, "leadbreak", "The leaders slipping below their 200-day", v, lights(v, 50, 80),
        "Share of the 6 leaders now below their 200-day average.", "Cisco, Oracle and Qualcomm broke down in 2000; NVDA and META in 2022.",
        "🟠 half of them · 🟢 most of them (5+)")
    v = chg(wk_of(D, D.daily("^SOX")), 13)
    add(5, "chips", "Chip stocks falling first", v, lights(v, -10, -20, higher=False),
        "Semiconductors dropping over 3 months. Chips usually lead tech down.", "2000, 2018, 2022.", "🟠 down 10%+ · 🟢 down 20%+")
    v = wk_of(D, above_ma(rut))
    add(5, "smallbreak", "Small caps breaking down", v, lights(v, -3, -8, higher=False),
        "Russell 2000 below its 200-day average.", "Usually breaks before the big indices.", "🟠 3%+ below · 🟢 8%+ below")
    wb = pd.DataFrame({n2: wk_of(D, above_ma(D.daily(n2))) for n2 in WORLD if D.has(n2)})
    v = (wb < 0).sum(axis=1) / wb.notna().sum(axis=1) * 100
    v = v.where(wb.notna().sum(axis=1) >= 4)
    add(5, "worldbreak", "World markets turning down", v, lights(v, 40, 60),
        "Share of the world's big markets below their 200-day average. Contagion spreads.",
        "China 2015 and 2007 dragged on everyone; Japan 1990 led Asia down.", "🟠 40%+ of markets · 🟢 60%+")
    v = D.wk("FRED:SAHMREALTIME")
    add(5, "sahm", "Unemployment starting to rise (Sahm rule)", v, lights(v, 0.3, 0.5),
        "Unemployment up from its low. At 0.5 it has always meant recession.", "Triggered 2001, 2008, 2020 (and touched in 2024).",
        "🟠 0.3+ · 🟢 0.5+ (recession signal)", unit="pts")
    cl = D.wk("FRED:ICSA").rolling(4, min_periods=2).mean()
    v = cl / cl.rolling(52, min_periods=20).min()
    add(5, "claims", "Jobless claims climbing", v, lights(v, 1.15, 1.3),
        "New unemployment claims up from their low.", "Rose from early 2000 and early 2007.", "🟠 15%+ above the low · 🟢 30%+", unit="x")
    v = chg(D.wk("FRED:INDPRO"), 52)
    add(5, "industry", "Factories slowing", v, lights(v, 0, -2, higher=False),
        "Industrial production compared with a year ago.", "Fell into 2001, 2008, 2015-16, 2019-20.", "🟠 below a year ago · 🟢 down 2%+")
    v = diff(D.wk("FRED:UMCSENT"), 52)
    add(5, "confidence", "Shoppers losing confidence", v, lights(v, -10, -20, higher=False),
        "University of Michigan consumer sentiment vs a year ago.", "2000-01, 2007-08, 2022.", "🟠 down 10+ points · 🟢 down 20+", unit="pts")
    v = chg(D.wk("FRED:CP"), 52)
    add(5, "profits", "Company profits falling", v, lights(v, 0, -10, higher=False),
        "US corporate profits after tax vs a year ago (the economy-wide version).", "Fell in 2000, 2007 and 2015.",
        "🟠 below a year ago · 🟢 down 10%+")

    # ======================= 6 BREAK
    v = wk_of(D, above_ma(ix))
    add(6, "below200", "Nasdaq below its 200-day average", v, lights(v, 3, 0, higher=False),
        "The classic line between a bull and bear market.", "Broke in Oct 2000, Dec 2007, Jan 2022 and Mar 2025.",
        "🟠 within 3% above it · 🟢 below it")
    ma = ix.rolling(200, min_periods=160).mean() if ix is not None else None
    v = chg(wk_of(D, ma), 4) if ma is not None else pd.Series(np.nan, index=W)
    add(6, "maslope", "200-day average turning down", v, lights(v, 0, -1, higher=False),
        "The long-run trend itself has started falling.", "Turned down in late 2000, early 2008, 2022.",
        "🟠 flat or falling · 🟢 down 1%+ in a month")
    dd = wk_of(D, drawdown(ix))
    add(6, "dd", "Nasdaq falling from its high", dd, lights(dd, -8, -15, higher=False),
        "How far the Nasdaq is below its high of the past year.", "-10% = correction, -20% = bear market.",
        "🟠 down 8%+ · 🟢 down 15%+")
    if ix is not None:
        m50 = ix.rolling(50, min_periods=40).mean()
        dc = wk_of(D, (m50 < ma).astype(float).where(ma.notna()))
        below50 = wk_of(D, (ix < m50).astype(float).where(m50.notna()))
        v = dc + below50
    else:
        v = pd.Series(np.nan, index=W)
    add(6, "cross", "Death cross (50-day below 200-day)", v, lights(v, 1, 2),
        "Short-term average below the long-term one AND price below the short-term average.", "Late 2000, early 2008, early 2022.",
        "🟠 one of the two · 🟢 both", unit="")
    v = wk_of(D, drawdown(lead))
    add(6, "leaddd", "The leaders in a bear market", v, lights(v, -15, -30, higher=False),
        "The 6 leaders down from their high.", "Dot-com leaders fell 80%+; 2022 leaders 50%+.", "🟠 down 15%+ · 🟢 down 30%+")
    if ix is not None:
        dn = (ix.pct_change() < -0.03).astype(float).rolling(40).sum()
        v = wk_of(D, dn)
    else:
        v = pd.Series(np.nan, index=W)
    add(6, "crashdays", "Big down days (-3% or worse)", v, lights(v, 2, 4),
        "Number of -3% Nasdaq days in the last 2 months.", "Clusters in 2000, 2008, 2020, 2022, Apr 2025.",
        "🟠 2+ · 🟢 4+", unit="days")

    # Hamish's rule: green = "it has happened or is happening". The build-up signs (stages 1-3) stay lit for a year
    # after they fire, because the froth that came before a bust is still in the system. (Tested: this version holds
    # up better on the unseen 2011-2026 years.) Stages 4-6 only count what's happening now.
    for s in signs:
        s["status_now"] = s["status"]
        if s["stage"] <= 3:
            s["status"] = s["status"].rolling(52, min_periods=1).max().where(s["status"].notna())
    extras = dict(leaders=lead, picks=picks, nasdaq=ix, giants=basket(D, AI_GIANTS, min_n=6))
    return signs, extras


# ---------------------------------------------------------------- scoring
def score_table(signs):
    st = pd.DataFrame({s["id"]: s["status"] for s in signs})
    pts = (st == 2).sum(axis=1) + 0.5 * (st == 1).sum(axis=1)
    avail = st.notna().sum(axis=1)
    out = pd.DataFrame({"greens": (st == 2).sum(axis=1), "ambers": (st == 1).sum(axis=1), "points": pts,
                        "available": avail, "pct": pts / avail.replace(0, np.nan) * 100})
    for k in STAGES:
        ids = [s["id"] for s in signs if s["stage"] == k]
        sub = st[ids]
        out[f"stage{k}"] = ((sub == 2).sum(axis=1) + 0.5 * (sub == 1).sum(axis=1)) / sub.notna().sum(axis=1).replace(0, np.nan) * 100
    return out, st


def tops(daily, fall=20):
    """Tops that were followed by a fall of `fall`%+ from the high of the past year (found with hindsight,
    only used for testing). A new top can only start once the old fall is over (a fresh 52-week high)."""
    if daily is None:
        return []
    w = daily.resample("W-FRI").last().dropna()
    vals, idx = w.values, w.index
    out, i = [], 52
    while i < len(vals):
        lo = max(0, i - 52)
        hi_j = lo + int(np.argmax(vals[lo:i + 1]))
        if vals[i] <= vals[hi_j] * (1 - fall / 100):
            j, tr = i, i
            while j < len(vals) and vals[j] < vals[max(0, j - 52):j + 1].max() * 1.0 - 1e-9 or (j == i):
                if vals[j] < vals[tr]:
                    tr = j
                j += 1
                if j < len(vals) and vals[j] >= vals[max(0, j - 52):j].max():
                    break
            out.append(dict(peak=idx[hi_j], level=vals[hi_j], trough=idx[tr], fall=(vals[tr] / vals[hi_j] - 1) * 100))
            i = j + 1
            continue
        i += 1
    return out


def bear_ahead(daily, W, weeks=52, fall=20):
    """For each week: is the Nasdaq at some point in the next `weeks` at least `fall`% below its high
    (falls already under way count). Uses hindsight, only for testing."""
    v = daily.resample("W-FRI").last().reindex(W).ffill().values
    out = np.full(len(v), np.nan)
    for i in range(len(v) - weeks):
        if v[i] != v[i]:
            continue
        past = v[max(0, i - 52):i + 1]
        seg = v[i + 1:i + weeks + 1]
        hi = np.maximum.accumulate(np.concatenate([[np.nanmax(past)], seg]))[1:]
        out[i] = float((seg <= hi * (1 - fall / 100)).any())
    return pd.Series(out, index=W)


def weeks_to_top(daily, W, weeks=104, fall=20):
    """For each week: how many weeks until the top that came before the next 20%+ fall (0 = already past the top)."""
    v = daily.resample("W-FRI").last().reindex(W).ffill().values
    out = np.full(len(v), np.nan)
    for i in range(len(v) - weeks):
        if v[i] != v[i]:
            continue
        past = v[max(0, i - 52):i + 1]
        seg = v[i + 1:i + weeks + 1]
        hi = np.maximum.accumulate(np.concatenate([[np.nanmax(past)], seg]))[1:]
        hit = np.where(seg <= hi * (1 - fall / 100))[0]
        if len(hit):
            j = hit[0]
            top_j = int(np.argmax(seg[:j + 1])) if seg[:j + 1].max() > np.nanmax(past) else -1
            out[i] = top_j + 1 if top_j >= 0 else 0
    return pd.Series(out, index=W)


BANDS = [(0, 15, "Calm", "Nothing building. Big falls here came from out-of-the-blue shocks only."),
         (15, 25, "Warming up", "A few signs. Normal for a healthy bull market."),
         (25, 30, "Frothy", "The build-up is clear, but bubbles usually keep running for a while from here."),
         (30, 40, "Danger zone", "Froth plus triggers or early cracks. Most past tops came in or just before this band."),
         (40, 101, "High alert", "Froth, triggers and cracks together: a big fall usually followed or was already under way.")]


def band_of(pct):
    for lo, hi, name, text in BANDS:
        if lo <= pct < hi:
            return name, text
    return BANDS[-1][2], BANDS[-1][3]


def key_table(score, fwd, wk_to_top, mask=None):
    """For each band: how often a 20%+ fall followed within a year, and how long until the top."""
    rows = []
    for lo, hi, name, text in BANDS:
        m = (score["pct"] >= lo) & (score["pct"] < hi)
        if mask is not None:
            m &= mask
        f = fwd[m].dropna()
        t = wk_to_top[m & (wk_to_top <= 104)].dropna()
        rows.append(dict(band=name, lo=lo, hi=min(hi, 100), weeks=int(m.sum()), chance=f.mean() * 100 if len(f) else np.nan,
                         t_med=t.median() if len(t) >= 3 else np.nan, t_lo=t.quantile(0.25) if len(t) >= 3 else np.nan,
                         t_hi=t.quantile(0.75) if len(t) >= 3 else np.nan, text=text))
    return pd.DataFrame(rows)


def sign_test(signs, st, fwd, mask=None):
    """How good is each sign: chance of a 20%+ fall within a year when it's green vs normal."""
    base = fwd[mask].dropna().mean() if mask is not None else fwd.dropna().mean()
    rows = []
    for s in signs:
        x = st[s["id"]]
        m = (x == 2)
        if mask is not None:
            m &= mask
        f = fwd[m].dropna()
        rows.append(dict(id=s["id"], green_weeks=int(m.sum()), chance=f.mean() * 100 if len(f) >= 8 else np.nan,
                         lift=(f.mean() / base) if len(f) >= 8 and base > 0 else np.nan))
    return pd.DataFrame(rows).set_index("id"), base * 100


# ---------------------------------------------------------------- "today looks most like..."
def analog_match(S_daily, today_daily, years=3, search_weeks=104):
    """Slides today's last 3 years of prices along each past bubble and finds where it fits best."""
    if today_daily is None:
        return []
    L = years * 52
    now = np.log(today_daily.resample("W-FRI").last().dropna().iloc[-L:])
    if len(now) < L:
        return []
    z = (now - now.mean()) / now.std()
    out = []
    for name, code, top in ANALOGS:
        d = S_daily.get(code)
        if d is None:
            continue
        w = np.log(d.dropna().resample("W-FRI").last().dropna())
        top = pd.Timestamp(top)
        best = None
        for k in range(-search_weeks, 9):
            end = top + pd.Timedelta(weeks=k)
            seg = w[w.index <= end].iloc[-L:]
            if len(seg) < L or seg.index[-1] < end - pd.Timedelta(days=10):
                continue
            zs = (seg - seg.mean()) / seg.std()
            r = float(np.corrcoef(z.values, zs.values)[0, 1])
            gain_now = float(now.iloc[-1] - now.iloc[0])
            gain_then = float(seg.iloc[-1] - seg.iloc[0])
            size = min(gain_now, gain_then) / max(gain_now, gain_then) if gain_now > 0 and gain_then > 0 else 0
            fit = r * (0.7 + 0.3 * size)
            if best is None or fit > best["fit"]:
                after = d[(d.index > end)]
                pk = d[(d.index >= end - pd.Timedelta(days=60))]
                peak_val = d[(d.index >= min(end, top)) & (d.index <= top + pd.Timedelta(days=30))].max()
                trough = d[(d.index >= top) & (d.index <= top + pd.Timedelta(days=3 * 365))].min()
                out_end = d.asof(end)
                best = dict(name=name, fit=fit, corr=r, at=seg.index[-1], weeks_to_top=max(0, (top - end).days / 7),
                            gain_to_top=(peak_val / out_end - 1) * 100 if peak_val == peak_val else np.nan,
                            fall_after=(trough / peak_val - 1) * 100 if peak_val == peak_val else np.nan,
                            path_then=np.exp(seg.values - seg.values[0]) * 100,
                            path_after=(after.resample("W-FRI").last().dropna().iloc[:104] / out_end * 100).values)
        if best:
            out.append(best)
    out.sort(key=lambda x: -x["fit"])
    return out


def time_estimate(key_row, matches):
    """Combines the history key with the best 3 look-alikes into one time range (weeks)."""
    xs = []
    if key_row is not None and key_row.get("t_med") == key_row.get("t_med"):
        xs += [key_row["t_lo"], key_row["t_med"], key_row["t_hi"]]
    good = [m for m in matches[:3] if m["fit"] > 0.7]
    xs += [m["weeks_to_top"] for m in good]
    xs = [x for x in xs if x == x]
    if not xs:
        return None
    return dict(lo=float(np.percentile(xs, 25)), mid=float(np.median(xs)), hi=float(np.percentile(xs, 75)), n=len(xs))
