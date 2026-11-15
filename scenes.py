"""
scenes.py - the v42 page animations: world trading day (World equities), currency gravity (FX), the yield curve
through time (Curves), deal radar (Takeovers), the strategy graveyard (Event Lab), the country globe (Country),
release countdown (Calendar) and the economy heartbeat (US / UK / Euro area pages).

Each builder takes data the app has already loaded and returns a self-contained HTML page for st.components.
Decoration only: if anything is missing the app simply skips the animation.
"""

import json
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import scenes_assets as A

FONTS_URL = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@125,800"
             "&family=JetBrains+Mono:wght@300;400;500;600&family=Inter:wght@300;400;500;600&display=swap")

# where each market / country sits on the world clock and the globe (latitude, longitude)
MARKET_PLACES = {"^GSPC": (40.7, -74), "^DJI": (41.6, -72), "^IXIC": (39.6, -76), "^RUT": (38.4, -78), "^GSPTSE": (43.7, -79.4),
                 "^BVSP": (-23.5, -46.6), "^MXX": (19.4, -99.1), "^FTSE": (51.5, -.1), "^FTMC": (53, -2), "^GDAXI": (50.1, 8.7),
                 "^FCHI": (48.9, 2.35), "^STOXX50E": (52.4, 4.9), "FTSEMIB.MI": (45.5, 9.2), "^IBEX": (40.4, -3.7), "^AEX": (52.4, 4.9),
                 "^SSMI": (47.4, 8.5), "^N225": (35.7, 139.7), "^HSI": (22.3, 114.2), "000001.SS": (31.2, 121.5), "^KS11": (37.6, 127),
                 "^TWII": (25, 121.6), "^BSESN": (19.1, 72.9), "^AXJO": (-33.9, 151.2)}
COUNTRY_PLACES = {"USA": (38, -97), "CHN": (35, 104), "DEU": (51, 10), "JPN": (36, 138), "IND": (21, 78), "GBR": (54, -2), "FRA": (46, 2),
                  "ITA": (42.8, 12.5), "CAN": (56, -106), "BRA": (-10, -52), "RUS": (60, 90), "KOR": (36.5, 128), "AUS": (-25, 134),
                  "MEX": (23, -102), "ESP": (40, -4), "IDN": (-2, 118), "NLD": (52.2, 5.3), "SAU": (24, 45), "TUR": (39, 35), "CHE": (46.8, 8.2)}


def _clean(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else round(o, 4)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return _clean(float(o))
    return o


def html(scene, data, load_fonts=False, owner="", min_ms=0, force=False):
    d = dict(_clean(data), scene=scene, owner=owner, min=min_ms, force=force)
    doc = (A.SCENES_HTML.replace("__FONTS__", f'<link href="{FONTS_URL}" rel="stylesheet">' if load_fonts else "")
           .replace("const D = __D__;", "const D = " + json.dumps(d, separators=(",", ":")).replace("</", "<\\/") + ";"))
    return doc


# ---------------------------------------------------------------- data builders (all from data the app already has)
def markets_data(perf):
    """perf: the World equities performance table (columns Ticker/Name/1D %)."""
    rows = []
    for _, r in perf.iterrows():
        t = r.get("Ticker")
        v = r.get("1D %")
        if t in MARKET_PLACES and v == v and v is not None:
            la, lo = MARKET_PLACES[t]
            rows.append({"n": str(r.get("Name", t)).split(" (")[0], "lat": la, "lon": lo, "d": float(v)})
    return {"mkts": rows[:18]} if len(rows) >= 4 else None


def fx_data(strength):
    """strength: currency_strength() table (index = currency, columns 1D/1W/1M/1Y), measured against USD."""
    out = []
    for c, r in strength.iterrows():
        vals = {k: r.get(col) for k, col in (("d1", "1D"), ("w1", "1W"), ("m1", "1M"), ("y1", "1Y"))}
        if all(v is None or v != v for v in vals.values()):
            continue
        out.append({"c": str(c), **{k: (0.0 if v is None or v != v else float(v)) for k, v in vals.items()}})
    if "USD" not in [o["c"] for o in out]:
        out.append({"c": "USD", "d1": 0.0, "w1": 0.0, "m1": 0.0, "y1": 0.0})
    return {"fx": out[:20]} if len(out) >= 5 else None


def curves_data(tenors, recessions, start=2006):
    """tenors: {"3M": series, ..., "30Y": series} of daily yields; recessions: [(start, end)] US recession periods."""
    names = ["3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]
    if any(n not in tenors or tenors[n] is None or tenors[n].dropna().empty for n in names):
        return None
    df = pd.DataFrame({n: tenors[n] for n in names}).dropna()
    df = df[df.index >= pd.Timestamp(f"{start}-01-01")]
    if len(df) < 200:
        return None
    snaps = df.groupby(df.index.year).tail(1)
    if snaps.index[-1] != df.index[-1]:
        snaps = pd.concat([snaps, df.iloc[[-1]]])
    rec = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in recessions or []]
    frames = []
    for d, row in snaps.iterrows():
        in_rec = any(a - pd.Timedelta(days=200) <= d <= b + pd.Timedelta(days=200) for a, b in rec)
        frames.append({"d": f"{d:%b %Y}", "y": [float(row[n]) for n in names], "rec": int(in_rec)})
    return {"curves": frames}


def deals_data(deals):
    """deals: the Takeovers filings table (company, sponsor, form)."""
    if deals is None or deals.empty:
        return None
    rows = [{"t": str(r["company"])[:26], "b": str(r["sponsor"]), "f": str(r.get("form", ""))} for _, r in deals.head(12).iterrows()]
    return {"deals": rows}


def eventlab_data(published):
    return {"pub": published}


def countries_data(imf_tables, names, year):
    """imf_tables: {"NGDP_RPCH": table, "PCPIPCH": table, "LUR": table} (index = country code, columns = years)."""
    out = []
    for iso, (la, lo) in COUNTRY_PLACES.items():
        k = []
        for code, label in (("NGDP_RPCH", "GDP growth"), ("PCPIPCH", "Inflation"), ("LUR", "Unemployment")):
            t = imf_tables.get(code)
            try:
                v = float(t.loc[iso, year])
            except Exception:
                v = float("nan")
            if v == v:
                k.append([f"{label} {year}", round(v, 1), "%"])
        if k and iso in names:
            out.append({"code": iso, "name": names[iso], "lat": la, "lon": lo, "k": k})
    return {"countries": out} if len(out) >= 3 else None



def calendar_data(cal, now=None):
    """cal: the FRED release calendar (release_name, date). Most US releases come out at 8:30am New York time
    (13:30 UK), so that's the time used for the countdown."""
    if cal is None or cal.empty:
        return None
    now = now or datetime.now()
    rows = []
    for _, r in cal.sort_values("date").iterrows():
        when = pd.Timestamp(r["date"]).to_pydatetime().replace(hour=13, minute=30)
        h = (when - now).total_seconds() / 3600
        if 0 < h < 14 * 24:
            rows.append({"n": str(r["release_name"])[:28], "h": round(h, 3), "prev": "", "c": f"{when:%a %d %b} · 13:30 UK (8:30am New York)"})
    past = cal[pd.to_datetime(cal["date"]) < pd.Timestamp(now).normalize()].sort_values("date")
    last = str(past["release_name"].iloc[-1]).upper()[:28] if len(past) else "THE LATEST RELEASE"
    return {"cal": rows[:9], "last": last} if rows else None


def heartbeat_data(items, region, months=10):
    """items: [(indicator, series)] for one economy. Each month: every growth/jobs indicator's 3-month change, compared
    with its own history, pointed so that 'better' is positive, then averaged. Fast, tall beats = improving fast."""
    zs = []
    for ind, s in items:
        gw = ind.get("good_when")
        if s is None or gw not in ("up", "down") or len(s) < 60:
            continue
        m = s.resample("ME").last().dropna()
        ch = m.diff(3).dropna()
        if len(ch) < 36:
            continue
        z = (ch - ch.rolling(240, min_periods=36).mean()) / ch.rolling(240, min_periods=36).std()
        zs.append(z * (1 if gw == "up" else -1))
    if len(zs) < 3:
        return None
    df = pd.concat(zs, axis=1)
    df = df[df.index >= df.index.max() - pd.DateOffset(months=months + 1)]
    score = df.mean(axis=1, skipna=True).dropna().tail(months)
    if score.empty:
        return None
    # the body scan: one 'organ' per indicator group, glowing by its latest reading
    slots = [(-26, -115), (26, -78), (0, 12), (-28, 92), (28, 98)]
    by_group = {}
    for (ind, _), z in zip([it for it in items if it[0].get("good_when") in ("up", "down") and it[1] is not None and len(it[1]) >= 60], zs):
        last = z.dropna()
        if len(last):
            by_group.setdefault(ind.get("group", "Other"), []).append(float(last.iloc[-1]))
    groups = sorted(by_group.items(), key=lambda kv: -len(kv[1]))[:5]
    organs = [{"n": g, "x": slots[i][0], "y": slots[i][1], "z": float(np.tanh(np.mean(v) / 1.2))} for i, (g, v) in enumerate(groups)]
    return {"beat": [{"d": f"{d:%b %Y}".upper(), "r": region, "z": float(np.tanh(v / 1.2))} for d, v in score.items()], "organs": organs}
