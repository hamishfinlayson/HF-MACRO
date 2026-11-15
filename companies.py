"""
companies.py - COMPANY DATA ingredients for stocks (PC version only, needs your free API keys).

Sources (all free plans, personal use):
  Finnhub   - earnings dates and surprises, analyst recommendations, directors buying/selling
  FMP       - company accounts (income statement and balance sheet) for value and quality
  Tiingo    - a second source of stock prices, to cross-check Yahoo Finance

Free plans have limits (Finnhub ~60 requests a minute, FMP 250 a day, Tiingo ~50 an hour), so the
data is downloaded once per company, saved on disk, and topped up a bit each time you press
"Download company data". Ingredients use whatever has been downloaded so far (coverage is shown).

Every ingredient only uses information published BEFORE each Friday (filing / announcement dates).
Just for fun and learning. Not financial advice.
"""

import json
import time as _time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import signals

CACHE = Path(__file__).parent / "data" / "cache" / "company"
UA = signals.UA
DATASETS = {   # name: (source, refresh after N days, what it is)
    "fh_earnings": ("finnhub", 7, "earnings dates and surprises"),
    "fh_recs": ("finnhub", 14, "analyst recommendations"),
    "fh_insider": ("finnhub", 7, "director buying and selling"),
    "fmp_income": ("fmp", 45, "income statements"),
    "fmp_balance": ("fmp", 45, "balance sheets"),
}
LIMITS = {"finnhub": 1.1, "fmp": 0.3, "tiingo": 1.0}     # seconds between requests
FMP_DAILY = 240                                          # stay just under the free plan's 250 a day

INGREDIENTS = {
    "earn_drift": ("Earnings surprise drift", "Company data", "How much the last quarterly earnings beat or missed "
                   "analysts' forecast, for 60 days after the announcement.",
                   "Post-earnings drift: prices keep moving in the surprise direction for weeks because investors under-react."),
    "earn_next": ("Earnings next week", "Company data", "1 if the company reports earnings next week.",
                  "The 'earnings announcement premium': stocks tend to rise into results as investors pay for the risk."),
    "analyst_rev": ("Analyst upgrades", "Company data", "Change over 3 months in the share of analysts saying buy.",
                    "Analysts move slowly and in herds; upgrades often keep coming and pull the price along."),
    "insider_buy": ("Directors buying", "Company data", "Directors buying their own company's shares in the last 3 months "
                    "(minus a little for selling).",
                    "Directors know their company best. They sell for many reasons, but they only buy for one."),
    "value_ey": ("Value (earnings yield)", "Company data", "Latest annual earnings per share divided by today's price.",
                 "Cheap companies have beaten expensive ones over the long run (the value effect), with long dry spells."),
    "quality_roe": ("Quality (return on equity)", "Company data", "Profit divided by shareholders' money.",
                    "Profitable, well-run companies tend to be under-priced: investors overpay for exciting stories instead."),
    "profitability": ("Gross profitability", "Company data", "Gross profit divided by total assets.",
                      "One of the strongest quality signals in research (Novy-Marx)."),
    "low_leverage": ("Low debt", "Company data", "Minus debt as a share of total assets.",
                     "Heavily indebted companies get hit hardest when things go wrong."),
    "sector_mom": ("Sector momentum", "Company data", "The company's sector's average 3-month return.",
                   "Whole industries trend as money rotates between them (no key needed)."),
}
signals.INGREDIENTS.update(INGREDIENTS)
signals.FLAG_KEYS.update({"earn_next"})
signals.XS_KEYS.update({"earn_drift", "analyst_rev", "insider_buy", "value_ey", "quality_roe", "profitability",
                        "low_leverage", "sector_mom"})


def _symbol(ticker, source):
    """Yahoo ticker -> the provider's spelling."""
    if source == "finnhub":
        return ticker.replace("-", ".")
    return ticker


def _path(name, ticker):
    return CACHE / f"{name}_{ticker.replace('/', '_')}.json"


def _load(name, ticker):
    p = _path(name, ticker)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _fresh(name, ticker):
    p = _path(name, ticker)
    return p.exists() and _time.time() - p.stat().st_mtime < DATASETS[name][1] * 86400


def _fmp_budget():
    """How many FMP requests are left today (counted on disk)."""
    p = CACHE / "_fmp_count.json"
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    try:
        d = json.loads(p.read_text())
    except Exception:
        d = {}
    return d, p, today, FMP_DAILY - d.get(today, 0)


def _fmp_spend(n=1):
    d, p, today, _ = _fmp_budget()
    d = {today: d.get(today, 0) + n}
    p.write_text(json.dumps(d))


def fetch_dataset(name, ticker):
    """One request for one company. Returns parsed JSON (raises on failure)."""
    src = DATASETS[name][0]
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    if src == "finnhub":
        key = signals.get_key("FINNHUB_API_KEY")
        sym = _symbol(ticker, "finnhub")
        url, params = {
            "fh_earnings": ("https://finnhub.io/api/v1/calendar/earnings",
                            {"symbol": sym, "from": "2015-01-01",
                             "to": (pd.Timestamp.now() + pd.Timedelta(days=45)).strftime("%Y-%m-%d")}),
            "fh_recs": ("https://finnhub.io/api/v1/stock/recommendation", {"symbol": sym}),
            "fh_insider": ("https://finnhub.io/api/v1/stock/insider-transactions", {"symbol": sym, "from": "2015-01-01"}),
        }[name]
        params["token"] = key
    else:
        key = signals.get_key("FMP_API_KEY")
        url = {"fmp_income": "https://financialmodelingprep.com/stable/income-statement",
               "fmp_balance": "https://financialmodelingprep.com/stable/balance-sheet-statement"}[name]
        params = {"symbol": _symbol(ticker, "fmp"), "period": "annual", "limit": 10, "apikey": key}
    r = requests.get(url, params=params, headers=UA, timeout=20)
    if src == "fmp":
        _fmp_spend()
    if r.status_code == 429:
        raise RuntimeError("rate limit")
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and ("error" in data or "Error Message" in data):
        raise RuntimeError(str(data)[:200])
    return data


def download(tickers, max_minutes=8, progress=None, stop_after_errors=25):
    """
    Tops up the company data cache. Stops when everything is fresh, the time limit is reached, or the
    FMP daily allowance is used. Returns a summary dict.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    have = {s: bool(signals.get_key(k)) for s, k in (("finnhub", "FINNHUB_API_KEY"), ("fmp", "FMP_API_KEY"))}
    todo = [(n, t) for t in tickers for n, (src, _, _) in DATASETS.items() if have[src] and not _fresh(n, t)]
    t0, done, errors, last_call = _time.time(), 0, {}, {}
    blocked = set()
    for i, (name, t) in enumerate(todo):
        src = DATASETS[name][0]
        if _time.time() - t0 > max_minutes * 60:
            break
        if src in blocked:
            continue
        if src == "fmp" and _fmp_budget()[3] <= 0:
            blocked.add("fmp")
            errors.setdefault("fmp", []).append("daily free allowance used: more tomorrow")
            continue
        wait = LIMITS[src] - (_time.time() - last_call.get(src, 0))
        if wait > 0:
            _time.sleep(wait)
        last_call[src] = _time.time()
        try:
            data = fetch_dataset(name, t)
            _path(name, t).write_text(json.dumps(data))
            done += 1
        except Exception as exc:
            msg = f"{t} {name}: {type(exc).__name__}: {exc}"[:200]
            errors.setdefault(src, []).append(msg)
            if "rate limit" in str(exc):
                _time.sleep(30)
            # premium-only symbols (e.g. UK stocks on free plans) come back as 403: save an empty result
            if src == "finnhub" and ("403" in str(exc) or "401" in str(exc)):
                _path(name, t).write_text("[]")
            if len(errors[src]) >= stop_after_errors and done == 0:
                blocked.add(src)
        if progress and i % 5 == 0:
            progress(min(1.0, (i + 1) / max(1, len(todo))), f"{t}: {DATASETS[name][2]} ({i + 1} of {len(todo)})")
    return dict(done=done, remaining=max(0, len(todo) - done), errors=errors, coverage=coverage(tickers))


def coverage(tickers):
    out = {}
    for n in DATASETS:
        out[n] = sum(1 for t in tickers if _path(n, t).exists() and _path(n, t).stat().st_size > 5)
    return out


# ================================================================= parsers (point-in-time)

def _num(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _first(d, *names):
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return None


def parse_earnings(data):
    """-> DataFrame [date (usable from), surprise %] from Finnhub calendar or FMP earnings."""
    rows = data.get("earningsCalendar", data) if isinstance(data, dict) else data
    out = []
    for r in rows or []:
        d = _first(r, "date")
        act, est = _num(_first(r, "epsActual", "actual")), _num(_first(r, "epsEstimate", "epsEstimated", "estimate"))
        if not d:
            continue
        day = pd.Timestamp(d)
        hour = str(r.get("hour", "")).lower()
        usable = day + pd.Timedelta(days=1 if hour != "bmo" else 0)
        sur = (act - est) / max(abs(est), 0.05) * 100 if np.isfinite(act) and np.isfinite(est) else np.nan
        out.append((day, usable, float(np.clip(sur, -100, 100)) if np.isfinite(sur) else np.nan))
    return pd.DataFrame(out, columns=["date", "usable", "surprise"]).sort_values("date") if out else pd.DataFrame(
        columns=["date", "usable", "surprise"])


def parse_recs(data):
    out = []
    for r in data or []:
        if not isinstance(r, dict) or "period" not in r:
            continue
        sb, b, h, s, ss = (_num(r.get(k, 0)) or 0 for k in ("strongBuy", "buy", "hold", "sell", "strongSell"))
        tot = sb + b + h + s + ss
        if tot > 0:
            out.append((pd.Timestamp(r["period"]) + pd.Timedelta(days=7), (sb + b - s - ss) / tot * 100))
    return pd.Series(dict(out)).sort_index() if out else pd.Series(dtype=float)


def parse_insider(data):
    rows = data.get("data", []) if isinstance(data, dict) else data or []
    out = []
    for r in rows:
        code = str(r.get("transactionCode", "")).upper()
        f = r.get("filingDate") or r.get("transactionDate")
        if code in ("P", "S") and f:
            out.append((pd.Timestamp(f) + pd.Timedelta(days=1), str(r.get("name", "")), 1 if code == "P" else -1))
    return pd.DataFrame(out, columns=["usable", "name", "side"])


def parse_statements(data):
    """FMP annual statements -> DataFrame indexed by the date they became public."""
    out = []
    for r in data or []:
        if not isinstance(r, dict) or "date" not in r:
            continue
        f = _first(r, "filingDate", "fillingDate", "acceptedDate")
        usable = pd.Timestamp(str(f)[:10]) + pd.Timedelta(days=1) if f else pd.Timestamp(r["date"]) + pd.Timedelta(days=90)
        out.append(dict(usable=usable, **{k: _num(v) for k, v in r.items() if isinstance(v, (int, float))}))
    return pd.DataFrame(out).sort_values("usable").set_index("usable") if out else pd.DataFrame()


# ================================================================= building the ingredients

def _asof(events, fridays):
    """Value of a dated series as known on each Friday."""
    if events is None or len(events) == 0:
        return pd.Series(np.nan, index=fridays)
    s = events[~events.index.duplicated(keep="last")].sort_index()
    return s.reindex(s.index.union(fridays)).ffill().reindex(fridays)


def company_ingredients(cls, W, sectors=None):
    """All company-data ingredients for one stock class, from the disk cache (no downloading here)."""
    fridays, cols = W.index, W.columns
    out = {k: {} for k in INGREDIENTS}
    for t in cols:
        e = _load("fh_earnings", t)
        if e:
            ev = parse_earnings(e)
            if not ev.empty:
                known = ev.dropna(subset=["surprise"])
                s = _asof(known.set_index("usable")["surprise"], fridays)
                last_day = _asof(pd.Series(known["usable"].values, index=known["usable"].values), fridays)
                age = (fridays.to_series() - pd.to_datetime(last_day)).dt.days
                out["earn_drift"][t] = s.where(age <= 60)
                nxt = [float(((ev["date"] > d) & (ev["date"] <= d + pd.Timedelta(days=7))).any()) for d in fridays]
                out["earn_next"][t] = pd.Series(nxt, index=fridays)
        r = _load("fh_recs", t)
        if r:
            s = _asof(parse_recs(r), fridays)
            out["analyst_rev"][t] = s - s.shift(13)
        ins = _load("fh_insider", t)
        if ins:
            df = parse_insider(ins)
            if not df.empty:
                vals = []
                for d in fridays:
                    w = df[(df["usable"] <= d) & (df["usable"] > d - pd.Timedelta(days=90))]
                    buyers = w[w["side"] > 0]["name"].nunique()
                    sellers = w[w["side"] < 0]["name"].nunique()
                    vals.append(buyers - 0.25 * sellers)
                out["insider_buy"][t] = pd.Series(vals, index=fridays)
        inc, bal = parse_statements(_load("fmp_income", t)), parse_statements(_load("fmp_balance", t))
        if not inc.empty:
            if "eps" in inc or "epsDiluted" in inc or "epsdiluted" in inc:
                eps = inc["eps"] if "eps" in inc else inc.get("epsDiluted", inc.get("epsdiluted"))
                out["value_ey"][t] = _asof(eps, fridays) / W[t] * 100
            if not bal.empty and "netIncome" in inc and "totalStockholdersEquity" in bal:
                ni = _asof(inc["netIncome"], fridays)
                eq = _asof(bal["totalStockholdersEquity"], fridays)
                out["quality_roe"][t] = (ni / eq.where(eq > 0) * 100).clip(-100, 200)
            if not bal.empty and "grossProfit" in inc and "totalAssets" in bal:
                out["profitability"][t] = _asof(inc["grossProfit"], fridays) / _asof(bal["totalAssets"], fridays) * 100
        if not bal.empty and {"totalDebt", "totalAssets"} <= set(bal.columns):
            out["low_leverage"][t] = -_asof(bal["totalDebt"], fridays) / _asof(bal["totalAssets"], fridays) * 100
    frames = {k: pd.DataFrame(v).reindex(index=fridays, columns=cols) for k, v in out.items() if v}
    if sectors:
        mom = (W / W.shift(13) - 1) * 100
        sec = pd.Series({t: sectors.get(t, "Other") for t in cols})
        if sec.nunique() > 1:
            sm = pd.DataFrame(index=fridays, columns=cols, dtype=float)
            for s_name, members in sec.groupby(sec).groups.items():
                sm[list(members)] = np.repeat(mom[list(members)].mean(axis=1).values[:, None], len(members), axis=1)
            frames["sector_mom"] = sm
    return {k: v for k, v in frames.items() if v.notna().any().any()}


# ================================================================= Tiingo price cross-check

def tiingo_check(tickers, prices, max_n=30):
    """Compares Yahoo's weekly returns with Tiingo's for a few stocks. Flags big disagreements."""
    key = signals.get_key("TIINGO_API_KEY")
    if not key:
        return pd.DataFrame(), "no TIINGO_API_KEY in secrets.toml"
    CACHE.mkdir(parents=True, exist_ok=True)
    rows, msg = [], ""
    start = (pd.Timestamp.now() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    for t in list(tickers)[:max_n]:
        if t not in prices or t.endswith(".L"):
            continue
        p = CACHE / f"tiingo_{t}.json"
        try:
            if p.exists() and _time.time() - p.stat().st_mtime < 7 * 86400:
                data = json.loads(p.read_text())
            else:
                _time.sleep(LIMITS["tiingo"])
                r = requests.get(f"https://api.tiingo.com/tiingo/daily/{t.replace('.', '-')}/prices",
                                 params={"startDate": start, "token": key}, headers=UA, timeout=20)
                r.raise_for_status()
                data = r.json()
                p.write_text(json.dumps(data))
            ti = pd.Series({pd.Timestamp(str(d["date"])[:10]): _num(d.get("adjClose")) for d in data}).dropna()
            ya = prices[t].dropna()
            both = pd.concat([ya.resample("W-FRI").last(), ti.resample("W-FRI").last()], axis=1, keys=["y", "t"]).dropna()
            if len(both) < 20:
                continue
            ry, rt = both["y"].pct_change() * 100, both["t"].pct_change() * 100
            diff = (ry - rt).abs()
            rows.append(dict(ticker=t, weeks=len(both), typical_gap=diff.median(), worst_gap=diff.max(),
                             worst_week=diff.idxmax(), ok="✅ agree" if diff.max() < 2 else "⚠️ check this one"))
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"[:200]
    return pd.DataFrame(rows), msg
