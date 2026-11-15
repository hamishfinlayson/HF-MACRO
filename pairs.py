"""
pairs.py - PAIRS TRADING (PC version only).

Rivals like Coke and Pepsi usually move together. Sometimes one runs ahead of the other for no lasting reason.
The pairs trade: SHORT the one that ran ahead, BUY the one that fell behind (same £ in each), and close both when the
gap closes. If the whole market crashes, one leg loses and the other gains, so the trade only cares about the GAP.

How the gap is measured (no peeking at the future, everything uses the past year only):
  hedge   = how much B moves when A moves (from the last year of prices)
  spread  = log(A) - hedge x log(B)
  z-score = how unusual today's spread is: (spread - its 1-year average) / its 1-year normal wobble
            z = +2 means A is unusually far ahead of B (2 'normal wobbles').
Which pairs are allowed (re-checked every month, from the past year only):
  - same industry, daily moves strongly linked (correlation)
  - the gap has a habit of closing: it snaps back with a half-life of a few weeks (not months)
  - the gap passes a simple 'does it keep coming back' test (Engle-Granger style)
Trade rules (the defaults are what tested best on the build years; see the PAIRS page for the tests):
  open  when |z| >= ENTRY  (short the one ahead, buy the one behind)
  close when the gap is back near normal (|z| <= EXIT)
  stop  when the gap keeps widening (|z| >= STOP_Z) or the trade has run MAX_WEEKS
"""

import numpy as np
import pandas as pd

GROUPS = {
    "Drinks": "KO PEP KDP MNST", "Discount shops": "WMT TGT COST DG DLTR BJ", "Home improvement": "HD LOW",
    "Payments": "V MA AXP PYPL COF", "Fast food": "MCD YUM QSR CMG WEN DPZ", "Oil majors": "XOM CVX COP BP SHEL TTE",
    "Big banks": "JPM BAC C WFC USB PNC TFC", "Investment banks": "GS MS SCHW", "Railways": "UNP CSX NSC CP CNI",
    "Telecoms": "T VZ TMUS", "Parcels": "UPS FDX", "Airlines": "DAL UAL AAL LUV ALK", "Defence": "LMT RTX NOC GD BA",
    "Chips": "NVDA AMD INTC QCOM AVGO TXN MU ADI", "Software": "MSFT ORCL CRM ADBE SAP IBM", "Internet": "GOOGL META AMZN",
    "Pharma": "PFE MRK JNJ ABBV LLY BMY AZN NVS GSK", "Health insurers": "UNH ELV CI HUM CVS",
    "Household goods": "PG CL KMB CHD CLX UL", "Food makers": "GIS K KHC CPB MDLZ HSY CAG SJM", "Tobacco": "MO PM BTI",
    "Sportswear": "NKE ADDYY UAA LULU SKX DECK VFC", "Car makers": "GM F TM HMC STLA", "Hotels": "MAR HLT H",
    "Cruises": "CCL RCL NCLH", "Utilities": "DUK SO NEE D AEP XEL ED", "Insurers": "TRV ALL PGR CB",
    "Media": "DIS CMCSA WBD PARA NFLX", "Asset managers": "BLK TROW BEN IVZ", "Ratings agencies": "SPGI MCO",
    "Machinery": "CAT DE CMI", "Chemicals": "DOW LYB DD EMN", "Steel": "NUE STLD CLF", "Gold miners": "NEM GOLD AEM KGC",
    "Toys": "HAS MAT", "Department stores": "M KSS JWN DDS", "Pharmacies": "WBA CVS", "Home builders": "DHI LEN PHM TOL",
    "Trucks & logistics": "JBHT ODFL KNX", "Waste": "WM RSG", "Elevators & HVAC": "CARR TT LII",
}
FUND_PAIRS = [("SPY", "QQQ"), ("SPY", "IWM"), ("SPY", "DIA"), ("EWU", "EWG"), ("GLD", "SLV"), ("USO", "BNO"),
              ("XLE", "XOP"), ("GLD", "GDX"), ("XLF", "KBE"), ("XLU", "XLP")]
NAMES = {"KO": "Coca-Cola", "PEP": "PepsiCo", "WMT": "Walmart", "TGT": "Target", "HD": "Home Depot", "LOW": "Lowe's",
         "V": "Visa", "MA": "Mastercard", "XOM": "Exxon", "CVX": "Chevron", "MCD": "McDonald's", "UPS": "UPS",
         "FDX": "FedEx", "COST": "Costco", "DG": "Dollar General", "DLTR": "Dollar Tree", "JPM": "JPMorgan",
         "BAC": "Bank of America", "WFC": "Wells Fargo", "GS": "Goldman Sachs", "MS": "Morgan Stanley",
         "UNP": "Union Pacific", "CSX": "CSX", "NSC": "Norfolk Southern", "T": "AT&T", "VZ": "Verizon",
         "DAL": "Delta", "UAL": "United Airlines", "LUV": "Southwest", "PG": "Procter & Gamble", "CL": "Colgate",
         "KMB": "Kimberly-Clark", "MO": "Altria", "PM": "Philip Morris", "NKE": "Nike", "GM": "General Motors",
         "F": "Ford", "MAR": "Marriott", "HLT": "Hilton", "CCL": "Carnival", "RCL": "Royal Caribbean",
         "DUK": "Duke Energy", "SO": "Southern Co", "SPGI": "S&P Global", "MCO": "Moody's", "CAT": "Caterpillar",
         "DE": "Deere", "WM": "Waste Management", "RSG": "Republic Services", "LMT": "Lockheed Martin",
         "NOC": "Northrop Grumman", "GD": "General Dynamics", "RTX": "RTX", "HSY": "Hershey", "GIS": "General Mills",
         "PFE": "Pfizer", "MRK": "Merck", "JNJ": "Johnson & Johnson", "UNH": "UnitedHealth", "ELV": "Elevance",
         "DHI": "D.R. Horton", "LEN": "Lennar", "PHM": "PulteGroup", "TOL": "Toll Brothers", "NUE": "Nucor",
         "STLD": "Steel Dynamics", "BLK": "BlackRock", "TROW": "T. Rowe Price", "AXP": "American Express",
         "CB": "Chubb", "TRV": "Travelers", "ALL": "Allstate", "PGR": "Progressive", "ED": "Con Edison",
         "AEP": "American Electric Power", "XEL": "Xcel", "D": "Dominion", "NEE": "NextEra", "GLD": "Gold fund",
         "SLV": "Silver fund", "SPY": "S&P 500 fund", "QQQ": "Nasdaq 100 fund", "IWM": "Small caps fund",
         "DIA": "Dow fund", "USO": "WTI oil fund", "BNO": "Brent oil fund", "GDX": "Gold miners fund"}

# Defaults (set from the build-years tests; see the PAIRS page)
LOOKBACK = 252          # days of history used for hedge, average and wobble
ENTRY, EXIT, STOP_Z = 2.0, 0.5, 4.0
MAX_WEEKS = 8
MIN_CORR = 0.6
HALF_LIFE = (3, 40)     # days: the gap must snap back within this
EG_T = -2.9             # 'keeps coming back' test (more negative = stronger)
SLOTS = 10              # most pairs open at once, money split equally
COST_RT = 0.004         # round trip: 0.1% each leg each way (buy + short, open + close)
FIN_DAY = 0.0003        # overnight fees on both CFD legs, per day held (~7.5% a year)


def name(t):
    return NAMES.get(t, t)


def candidate_pairs(available):
    out = []
    for g, ts in GROUPS.items():
        xs = [t for t in ts.split() if t in available]
        for i in range(len(xs)):
            for j in range(i + 1, len(xs)):
                out.append((xs[i], xs[j], g))
    for a, b in FUND_PAIRS:
        if a in available and b in available:
            out.append((a, b, "Funds"))
    return out


def pair_stats(la, lb, lookback=LOOKBACK):
    """Re-fitted at the start of every month from the PAST year only, then held fixed for that month:
    hedge (beta), the spread's normal level and wobble, daily-move correlation, how fast the gap closes
    (half-life, days) and a 'does the gap keep coming back' t-stat. Daily z-score uses those fixed numbers."""
    idx = la.index
    A, B = la.values, lb.values
    ra, rb = np.diff(A, prepend=np.nan), np.diff(B, prepend=np.nan)
    months = pd.Series(np.arange(len(idx)), index=idx).groupby(idx.to_period("M")).first().values
    out = np.full((len(idx), 5), np.nan)
    for mi, start in enumerate(months):
        if start < lookback:
            continue
        stop = months[mi + 1] if mi + 1 < len(months) else len(idx)
        wa, wb = A[start - lookback:start], B[start - lookback:start]
        vb = wb.var()
        if vb <= 0:
            continue
        beta = np.cov(wa, wb, bias=True)[0, 1] / vb
        if not (0.2 <= beta <= 5):
            continue
        sp = wa - beta * wb
        mu, sd = sp.mean(), sp.std()
        if sd <= 0:
            continue
        x, y = sp[:-1] - sp[:-1].mean(), np.diff(sp)
        bb = (x * (y - y.mean())).sum() / (x * x).sum()
        res = (y - y.mean()) - bb * x
        se = np.sqrt((res * res).sum() / (len(y) - 2) / (x * x).sum())
        t = bb / se
        hl = -np.log(2) / np.log1p(bb) if -1 < bb < 0 else np.nan
        c = np.corrcoef(ra[start - lookback + 1:start], rb[start - lookback + 1:start])[0, 1]
        z = (A[start:stop] - beta * B[start:stop] - mu) / sd
        out[start:stop, 0], out[start:stop, 1], out[start:stop, 2] = beta, z, c
        out[start:stop, 3], out[start:stop, 4] = hl, t
    return pd.DataFrame(out, index=idx, columns=["beta", "z", "corr", "hl", "t"])


def build_stats(px, pairs, lookback=LOOKBACK):
    lp = np.log(px)
    S = {}
    for a, b, g in pairs:
        d = pd.concat([lp[a], lp[b]], axis=1).dropna()
        if len(d) < lookback + 60:
            continue
        S[(a, b, g)] = pair_stats(d.iloc[:, 0], d.iloc[:, 1], lookback)
    return S


def eligible(st, min_corr=MIN_CORR, hl=HALF_LIFE, eg_t=EG_T):
    return (st["corr"] >= min_corr) & (st["hl"] >= hl[0]) & (st["hl"] <= hl[1]) & (st["t"] <= eg_t)


def backtest(px, S, entry=ENTRY, exit_=EXIT, stop_z=STOP_Z, max_weeks=MAX_WEEKS, slots=SLOTS, weekly=True,
             min_corr=MIN_CORR, hl=HALF_LIFE, eg_t=EG_T, stop_pct=None, cost_rt=COST_RT, fin_day=FIN_DAY,
             start=None, end=None, allowed_groups=None, buy_only=False):
    """Day-by-day simulation. Each open pair gets 1/slots of the money: £x long the laggard, £x short the leader.
    Signals are checked on Fridays (weekly=True) or every day. Returns (daily returns, list of trades)."""
    days = px.index
    if start is not None:
        days = days[days >= pd.Timestamp(start)]
    if end is not None:
        days = days[days <= pd.Timestamp(end)]
    rets = px.pct_change(fill_method=None)
    elig = {}
    Z = {}
    for k, st in S.items():
        if allowed_groups is not None and k[2] not in allowed_groups:
            continue
        e = eligible(st, min_corr, hl, eg_t)          # already fixed for each month, from the past year only
        elig[k] = e.reindex(days).fillna(False).values
        Z[k] = st["z"].reindex(days).values
    keys = list(Z)
    zarr = np.array([Z[k] for k in keys]).T if keys else np.zeros((len(days), 0))
    earr = np.array([elig[k] for k in keys]).T if keys else np.zeros((len(days), 0), bool)
    ra = {t: rets[t].reindex(days).fillna(0).values for t in px.columns}
    is_check = np.array([d.weekday() == 4 for d in days]) if weekly else np.ones(len(days), bool)
    open_ = {}               # key index -> dict(side, start, pnl)
    out = np.zeros(len(days))
    trades = []
    for i, d in enumerate(days):
        # 1) today's P&L on open trades (signals are acted on at the close, so new trades earn from tomorrow)
        day_pnl = 0.0
        for ki, tr in list(open_.items()):
            a, b, g = keys[ki]
            if tr["side"] == 1:          # A behind: buy A, short B
                r = ra[a][i] - (0 if buy_only else ra[b][i])
            else:                        # A ahead: short A, buy B
                r = ra[b][i] - (0 if buy_only else ra[a][i])
            r -= fin_day * (0.5 if buy_only else 1)
            tr["pnl"] = (1 + tr["pnl"]) * (1 + r) - 1
            tr["days"] += 1
            day_pnl += r / slots
        out[i] = day_pnl
        if not is_check[i]:
            continue
        # 2) exits
        for ki, tr in list(open_.items()):
            z = zarr[i, ki]
            why = None
            if z == z:
                zs = z * (1 if tr["side"] == -1 else -1)       # >0 means the gap is still the way we bet against
                if zs <= exit_:
                    why = "gap closed"
                elif zs >= stop_z:
                    why = "gap kept widening (stop)"
            if why is None and stop_pct is not None and tr["pnl"] * 100 <= stop_pct:
                why = f"lost {stop_pct}% (stop)"
            if why is None and tr["days"] >= max_weeks * 5:
                why = "time limit"
            if why is None and z != z:
                why = "no data"
            if why:
                out[i] -= cost_rt / 2 / slots * (0.5 if buy_only else 1)
                tr["pnl"] -= cost_rt / 2
                a, b, g = keys[ki]
                trades.append(dict(a=a, b=b, group=g, side=tr["side"], opened=tr["start"], closed=d, pnl=tr["pnl"] * 100,
                                   why=why, days=tr["days"], z_in=tr["z_in"]))
                del open_[ki]
        # 3) entries (strongest signal first), only on eligible pairs, one trade per stock at a time
        free = slots - len(open_)
        if free <= 0:
            continue
        busy = {t for ki in open_ for t in keys[ki][:2]}
        zi = zarr[i]
        cand = [(abs(zi[k]), k) for k in range(len(keys))
                if earr[i, k] and k not in open_ and zi[k] == zi[k] and entry <= abs(zi[k]) < stop_z]
        cand.sort(reverse=True)
        for _, k in cand:
            if free <= 0:
                break
            a, b, g = keys[k]
            if a in busy or b in busy:
                continue
            side = -1 if zi[k] > 0 else 1
            open_[k] = dict(side=side, start=d, pnl=-cost_rt / 2, days=0, z_in=zi[k])
            out[i] -= cost_rt / 2 / slots * (0.5 if buy_only else 1)
            busy |= {a, b}
            free -= 1
    return pd.Series(out, index=days), pd.DataFrame(trades)


def yearly(daily):
    return daily.groupby(daily.index.year).apply(lambda s: ((1 + s).prod() - 1) * 100)


def summary(daily):
    if len(daily) < 50:
        return dict(year=np.nan, dd=np.nan, losing="-", vol=np.nan)
    eq = (1 + daily).cumprod()
    yrs = len(daily) / 252
    ann = (eq.iloc[-1] ** (1 / yrs) - 1) * 100
    dd = ((eq / eq.cummax()) - 1).min() * 100
    y = yearly(daily)
    return dict(year=ann, dd=dd, losing=f"{(y < 0).sum()}/{len(y)}", vol=daily.std() * np.sqrt(252) * 100)


def current_signals(px, S, entry=ENTRY, stop_z=STOP_Z, min_corr=MIN_CORR, hl=HALF_LIFE, eg_t=EG_T):
    """Today's list: eligible pairs and how stretched each gap is (for the trades page)."""
    rows = []
    for (a, b, g), st in S.items():
        last = st.dropna()
        if last.empty or last.index[-1] < px.index[-1] - pd.Timedelta(days=7):
            continue
        r = last.iloc[-1]
        ok = bool(eligible(st, min_corr, hl, eg_t).iloc[-1])
        rows.append(dict(a=a, b=b, group=g, z=r["z"], corr=r["corr"], hl=r["hl"], t=r["t"], beta=r["beta"], eligible=ok,
                         signal=ok and entry <= abs(r["z"]) < stop_z))
    return pd.DataFrame(rows)
