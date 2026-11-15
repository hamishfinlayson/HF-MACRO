"""
news.py - finds out WHAT CAUSED our biggest misses, using credible sources only (PC version only).

Order of trust:
  1. Primary sources: official company filings (SEC EDGAR 8-K reports for US companies: the company's own
     legal announcement of results, deals, management changes, accounting problems...), our earnings
     calendar, and official event dates (Fed decisions, US inflation data).
  2. Trusted newsrooms: Reuters, Bloomberg, FT, WSJ, AP, CNBC, MarketWatch, Barron's, BBC, The Economist
     (via Finnhub's company news, free plan: roughly the last year). Re-written copies of the same
     story are removed.
  3. Anything else is shown as "other source" and never used to decide the cause on its own.

Each big miss is then labelled SCHEDULED (we could have known the date: earnings, shareholder votes,
Fed/CPI weeks) or UNSCHEDULED (deals, lawsuits, profit warnings, shocks). Scheduled misses are the
avoidable ones: the risk layer's "Event next week" check skips them.

Just for fun and learning. Not financial advice.
"""

import json
import re
import time as _time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import signals

CACHE = Path(__file__).parent / "data" / "cache" / "news"
TRUSTED = ["reuters", "bloomberg", "financial times", "ft.com", "wall street journal", "wsj", "associated press",
           "ap news", "cnbc", "marketwatch", "barron", "bbc", "economist", "dow jones"]
ITEMS_8K = {  # SEC 8-K item: (cause, scheduled?)
    "1.01": ("Major agreement signed", False), "1.02": ("Major agreement ended", False),
    "1.03": ("Bankruptcy", False), "1.05": ("Cybersecurity incident", False),
    "2.01": ("Acquisition or sale completed", False), "2.02": ("Results (earnings)", True),
    "2.03": ("New debt", False), "2.04": ("Debt problem", False), "2.05": ("Restructuring / job cuts", False),
    "2.06": ("Write-down", False), "3.01": ("Delisting warning", False), "3.02": ("New shares sold", False),
    "4.01": ("Auditor changed", False), "4.02": ("Accounts can't be relied on", False),
    "5.02": ("Management change", False), "5.07": ("Shareholder vote", True), "7.01": ("Company announcement", False),
    "8.01": ("Company announcement", False),
}
KEYWORDS = [  # headline words -> cause, scheduled?
    (r"\b(results|earnings|quarter|q[1-4]|eps|revenue|profit)\b", "Results (earnings)", True),
    (r"\b(guidance|outlook|forecast|warns?|warning|cuts? (its )?(forecast|outlook))\b", "Guidance / profit warning", False),
    (r"\b(acquir\w*|merger|takeover|buyout|bid|deal to buy|to buy)\b", "Takeover / deal", False),
    (r"\b(upgrade\w*|downgrade\w*|price target|rating)\b", "Analyst upgrade/downgrade", False),
    (r"\b(lawsuit|sued|probe|investigation|antitrust|regulator\w*|fine[ds]?|recall)\b", "Legal / regulatory", False),
    (r"\b(ceo|cfo|chief executive|resign\w*|steps down|appoint\w*)\b", "Management change", False),
    (r"\b(dividend|buyback|share repurchase)\b", "Dividend / buyback", True),
    (r"\b(fed|interest rates?|inflation|tariff\w*|recession)\b", "Macro news", False),
]


def _ua():
    contact = signals.get_key("SEC_CONTACT_EMAIL")
    # The SEC asks automated tools to say who they are; add SEC_CONTACT_EMAIL to secrets.toml if it refuses.
    return {"User-Agent": f"HF-Macro personal research {contact or '(https://hf-macro.streamlit.app)'}",
            "Accept-Encoding": "gzip, deflate"}


def _cached_json(name, url, params=None, max_age_days=7, headers=None, pause=0.0):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', name)}.json"
    if p.exists() and _time.time() - p.stat().st_mtime < max_age_days * 86400:
        return json.loads(p.read_text())
    if pause:
        _time.sleep(pause)
    r = requests.get(url, params=params, headers=headers or signals.UA, timeout=20)
    r.raise_for_status()
    data = r.json()
    p.write_text(json.dumps(data))
    return data


def sec_ciks():
    data = _cached_json("sec_tickers", "https://www.sec.gov/files/company_tickers.json", max_age_days=30, headers=_ua())
    return {str(v["ticker"]).upper().replace(".", "-"): int(v["cik_str"]) for v in data.values()}


def sec_8k(cik):
    """Every recent 8-K (official company announcement): date, cause, scheduled?, link."""
    data = _cached_json(f"sec_{cik}", f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=_ua(),
                        max_age_days=3, pause=0.15)
    rec = data.get("filings", {}).get("recent", {})
    rows = []
    for i, form in enumerate(rec.get("form", [])):
        if form not in ("8-K", "8-K/A"):
            continue
        items = [x.strip() for x in str(rec.get("items", [""] * (i + 1))[i]).split(",") if x.strip()]
        acc = str(rec["accessionNumber"][i]).replace("-", "")
        doc = rec.get("primaryDocument", [""] * (i + 1))[i]
        link = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
        main = [x for x in items if x in ITEMS_8K and x not in ("9.01",)]
        for it in main or ["8.01"]:
            cause, sched = ITEMS_8K.get(it, ("Company announcement", False))
            rows.append(dict(date=pd.Timestamp(rec["filingDate"][i]), cause=cause, scheduled=sched,
                             source="SEC filing (official)", headline=f"8-K item {it}: {cause}", link=link, tier=1))
    return pd.DataFrame(rows)


def finnhub_news(ticker, start, end):
    key = signals.get_key("FINNHUB_API_KEY")
    if not key:
        return pd.DataFrame()
    data = _cached_json(f"fhnews_{ticker}_{start:%Y%m%d}", "https://finnhub.io/api/v1/company-news",
                        params={"symbol": ticker.replace("-", "."), "from": f"{start:%Y-%m-%d}", "to": f"{end:%Y-%m-%d}",
                                "token": key}, max_age_days=30, pause=1.1)
    rows, seen = [], set()
    for n in data or []:
        head = str(n.get("headline", "")).strip()
        norm = re.sub(r"[^a-z ]", "", head.lower())[:60]
        if not head or norm in seen:
            continue                                   # the same story re-written by another site
        seen.add(norm)
        src = str(n.get("source", ""))
        tier = 2 if any(t in src.lower() for t in TRUSTED) else 3
        cause, sched = classify(head + " " + str(n.get("summary", ""))[:200])
        rows.append(dict(date=pd.Timestamp(int(n.get("datetime", 0)), unit="s"), cause=cause, scheduled=sched,
                         source=src or "unknown", headline=head, link=n.get("url", ""), tier=tier))
    return pd.DataFrame(rows)


def classify(text):
    t = text.lower()
    for pat, cause, sched in KEYWORDS:
        if re.search(pat, t):
            return cause, sched
    return "Other news", False


def _macro_cause(cls, date, ctx):
    """For FX, commodities, indices and crypto: official event dates and market-wide shocks."""
    a, b = date + pd.Timedelta(days=1), date + pd.Timedelta(days=7)
    hits = []
    if ((signals.FOMC >= a) & (signals.FOMC <= b)).any():
        hits.append(("Fed decision", True))
    cpi = (ctx or {}).get("cpi")
    if cpi is not None and len(cpi) and ((cpi >= a) & (cpi <= b)).any():
        hits.append(("US inflation data", True))
    fac = (ctx or {}).get("factors")
    if fac is not None and "vix" in getattr(fac, "columns", []):
        v = fac["vix"].dropna()
        w = v[(v.index > date) & (v.index <= b)]
        before = v[v.index <= date]
        if len(w) and len(before) and w.max() > before.iloc[-1] * 1.25:
            hits.append(("Market-wide fear spike (VIX up 25%+)", False))
    return hits


def tag_misses(worst, ctx=None, earnings=None, max_items=25, progress=None):
    """
    worst: DataFrame with date, ticker, cls, miss (biggest misses). Returns one row per miss with the most
    credible cause found, whether it was scheduled, the source and a link.
    """
    rows, ciks, errors = [], None, []
    for i, (_, r) in enumerate(worst.head(max_items).iterrows()):
        if progress:
            progress(i / max(1, min(len(worst), max_items)), f"Checking {r['ticker']} in the week of {r['date']:%d %b %Y}...")
        date, t, cls = pd.Timestamp(r["date"]), r["ticker"], r["cls"]
        a, b = date + pd.Timedelta(days=1), date + pd.Timedelta(days=7)
        found = []
        if cls in ("US stocks", "UK stocks"):
            ev = (earnings or {}).get(t)
            if ev is not None and len(ev) and ((ev >= a) & (ev <= b)).any():
                found.append(dict(cause="Results (earnings)", scheduled=True, source="Earnings calendar",
                                  headline="Earnings were reported this week", link="", tier=1))
            if cls == "US stocks":
                try:
                    ciks = ciks if ciks is not None else sec_ciks()
                    cik = ciks.get(t.upper())
                    if cik:
                        f = sec_8k(cik)
                        if not f.empty:
                            found += f[(f["date"] >= a) & (f["date"] <= b + pd.Timedelta(days=1))].to_dict("records")
                except Exception as exc:
                    errors.append(f"SEC: {type(exc).__name__}: {exc}"[:160])
                try:
                    nws = finnhub_news(t, a, b)
                    if not nws.empty:
                        found += nws[(nws["date"] >= a) & (nws["date"] <= b + pd.Timedelta(days=1))].to_dict("records")
                except Exception as exc:
                    errors.append(f"Finnhub news: {type(exc).__name__}: {exc}"[:160])
        else:
            for cause, sched in _macro_cause(cls, date, ctx):
                found.append(dict(cause=cause, scheduled=sched, source="Official calendar / market data",
                                  headline=cause, link="", tier=1))
        best = sorted(found, key=lambda x: (x["tier"], 0 if x["cause"] not in ("Other news", "Company announcement") else 1))
        top = best[0] if best else None
        if top is None or top["tier"] >= 3:
            label = "❔ Unexplained (no credible source found)"
        elif top["scheduled"]:
            label = "📅 Scheduled (avoidable)"
        else:
            label = "⚡ Unscheduled (bad luck)"
        rows.append(dict(date=date, ticker=t, cls=cls, miss=r.get("miss"), type=label,
                         cause=top["cause"] if top else "", source=top["source"] if top else "",
                         headline=top["headline"] if top else "", link=top["link"] if top else "",
                         other_sources=len(found) - 1 if found else 0))
    if progress:
        progress(1.0, "Done")
    return pd.DataFrame(rows), sorted(set(errors))
