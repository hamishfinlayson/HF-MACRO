"""
takeovers.py - TAKEOVERS (PC version only).

Private-equity takeovers and the legal ways to spot them early, from free official sources:
  1. Deal tracker  : the newest SEC filings (merger votes, going-private statements, tender offers) that name one of
                     ~50 big PE firms. These arrive AFTER a deal is announced.
  2. Activist watch: SEC 13D filings (a fund buying 5%+ of a company) that talk about 'strategic alternatives' or a
                     'sale of the company'. These come BEFORE many deals.
  3. Rumour scanner: takeover headlines from news wires (Finnhub's merger news) using words like 'explores sale' or
                     'takeover approach'. Public rumours are legal to trade on; tips from insiders are not (UK law).
All ideas were tested before the page was built (TESTS below). Not financial advice.
"""

import re
import time

import pandas as pd
import requests

SPONSORS = ["Blackstone", "KKR", "Apollo", "Carlyle", "Thoma Bravo", "Silver Lake", "Vista Equity", "TPG", "Bain Capital",
            "Advent International", "EQT", "CVC", "Hellman & Friedman", "Permira", "Warburg Pincus", "Brookfield",
            "Clearlake", "Francisco Partners", "Platinum Equity", "Sycamore Partners", "Searchlight", "Stone Point",
            "Veritas Capital", "Apax", "Cinven", "BC Partners", "Leonard Green", "Golden Gate Capital", "Insight Partners",
            "Siris Capital", "Clayton, Dubilier", "Genstar", "Madison Dearborn", "Onex", "GTCR", "Ares Management",
            "American Securities", "Cerberus", "Sun Capital", "Thomas H. Lee", "Providence Equity", "Roark Capital",
            "New Mountain Capital", "Stonepeak", "Elliott Investment"]
DEAL_FORMS = "DEFM14A,PREM14A,SC 13E3,SC TO-T,SC 14D9"
FORM_WORDS = {"PREM14A": "Draft merger vote papers", "DEFM14A": "Final merger vote papers", "SC 13E3": "Going-private statement",
              "SC TO-T": "Tender offer (buyer bids for the shares)", "SC 14D9": "Company's reply to a tender offer"}
ACTIVIST_PHRASES = ['"strategic alternatives"', '"sale of the company"', '"sale of the Issuer"', '"explore a sale"']
RUMOUR = re.compile(r"\b(explor\w* (a )?sale|weigh\w* (a )?sale|consider\w* (a )?sale|takeover (approach|interest|bid)|"
                    r"strategic (review|alternatives)|take[- ]private|buyout|in talks to (buy|acquire)|nears? (a )?deal|"
                    r"people familiar|approach(ed)? (about|for) (a )?(deal|takeover)|bid for)\b", re.I)
TRUSTED = ["reuters", "bloomberg", "financial times", "wsj", "wall street journal", "cnbc", "marketwatch", "barron", "dow jones", "ap"]

TESTS = [
    dict(light="🔴", idea="Merger arbitrage: buy every announced deal and earn the gap to the offer",
         result="Real funds: Merger Fund +4.9%/yr since 1989, MNA +2.7% since 2009, MRGR +2.2%, ARB +4.2% (S&P +9.6% to +17%). "
                "All significantly behind the S&P (p 0.03 to <0.001), but tiny drops (-2% in 2008 vs S&P -37%).",
         why="The +30% jump happens at the announcement; what's left is a 2-5% gap, and a failed deal wipes out several wins. "
             "Behaves like a savings account."),
    dict(light="🔴", idea="Target spotter: score companies on what PE firms look for (cash profits, debt, size, growth...)",
         result="Held-out 2016-24 AUC 0.51 (0.5 = coin flip). Top 10% of scores were bought LESS often (15.9% vs 20.8%).",
         why="Accounts-only scores can't separate targets; price (how cheap a company is) matters most and Yahoo deletes "
             "bought-out companies, so it couldn't be included honestly."),
    dict(light="🟢", idea="Activist watch: a fund buys 5%+ and pushes for a 'sale' or 'strategic alternatives' (SEC 13D)",
         result="Taken private by PE within 2 years: 8.1% (2005-15) and 12.2% (2016-24, 95%: 10.1-14.5%) vs 1.7% for a "
                "random listed company: about 5-7x more likely, on both build and held-out years.",
         why="Activists push boards to sell, and PE firms watch the same filings."),
    dict(light="🔴", idea="...but buying every activist target",
         result="Survivors lagged the S&P: -7.4% over 6 months (p 0.001) and -7.8% over 12 months (p 0.05) on held-out years. "
                "The bought-out winners are missing from Yahoo, so the real result is better than this, but a rough "
                "estimate (12% bought at ~+30%, the rest lagging) is still about -3% a year vs the S&P.",
         why="The share price jumps on the 13D filing day itself, before you can buy, and most targets never get sold."),
    dict(light="⚪", idea="Rumour scanner (news headlines)",
         result="Not tested: there's no free history of takeover headlines.", why="Shown for information only."),
]
HEADLINE = ("Activist stakes really do flag likely takeovers (5-7x more likely, held-out tested), but buying them all "
            "still lagged the S&P, and merger arbitrage and the target spotter didn't beat it either. Use this page to watch, "
            "not as a buy list.")


def _get(url, ua, params=None):
    for k in range(4):
        try:
            r = requests.get(url, headers=ua, params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(4 * (k + 1))
                continue
            r.raise_for_status()
            time.sleep(0.13)
            return r.json()
        except Exception:
            if k == 3:
                raise
            time.sleep(2)


def _ua(contact):
    return {"User-Agent": f"HF Macro personal research {contact}", "Accept-Encoding": "gzip, deflate"}


def _hits(js):
    for h in (js or {}).get("hits", {}).get("hits", []):
        s = h.get("_source", {})
        _id = h.get("_id", "")
        adsh, fname = (_id.split(":", 1) + [""])[:2]
        ciks = s.get("ciks", [])
        cik = str(int(ciks[0])) if ciks else ""
        link = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fname}" if cik and adsh else ""
        names = [re.sub(r"\s*\(CIK.*?\)", "", n).strip() for n in s.get("display_names", [])]
        yield dict(form=s.get("form", ""), filed=s.get("file_date", ""), names=names, link=link, adsh=adsh)


def recent_deals(contact, days=60, progress=None):
    ua = _ua(contact)
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days)
    rows, seen = [], set()
    for i, sp in enumerate(SPONSORS):
        if progress:
            progress((i + 1) / len(SPONSORS), sp)
        try:
            js = _get("https://efts.sec.gov/LATEST/search-index", ua, params={
                "q": f'"{sp}" "merger"', "forms": DEAL_FORMS, "dateRange": "custom",
                "startdt": f"{start:%Y-%m-%d}", "enddt": f"{end:%Y-%m-%d}"})
        except Exception:
            continue
        for h in _hits(js):
            key = (h["adsh"], h["form"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(dict(company=h["names"][0] if h["names"] else "?", sponsor=sp, form=h["form"],
                             what=FORM_WORDS.get(h["form"].split("/")[0], h["form"]), filed=h["filed"], link=h["link"]))
    d = pd.DataFrame(rows)
    if d.empty:
        return d
    d = d.groupby(["company", "form", "filed", "link", "what"], as_index=False)["sponsor"].agg(lambda x: ", ".join(sorted(set(x))))
    return d.sort_values("filed", ascending=False)


def recent_activists(contact, days=90):
    ua = _ua(contact)
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days)
    rows, seen = [], set()
    for ph in ACTIVIST_PHRASES:
        try:
            js = _get("https://efts.sec.gov/LATEST/search-index", ua, params={
                "q": ph, "forms": "SC 13D", "dateRange": "custom", "startdt": f"{start:%Y-%m-%d}", "enddt": f"{end:%Y-%m-%d}"})
        except Exception:
            continue
        for h in _hits(js):
            if h["adsh"] in seen:
                continue
            seen.add(h["adsh"])
            n = h["names"]
            rows.append(dict(company=n[0] if n else "?", fund=", ".join(n[1:3]) if len(n) > 1 else "", phrase=ph.strip('"'),
                             filed=h["filed"], link=h["link"]))
    d = pd.DataFrame(rows)
    return d.sort_values("filed", ascending=False) if not d.empty else d


def rumours(finnhub_key, max_items=40):
    if not finnhub_key:
        return pd.DataFrame()
    r = requests.get("https://finnhub.io/api/v1/news", params={"category": "merger", "token": finnhub_key}, timeout=30)
    r.raise_for_status()
    rows, seen = [], set()
    for n in r.json() or []:
        head = str(n.get("headline", "")).strip()
        text = head + " " + str(n.get("summary", ""))[:300]
        norm = re.sub(r"[^a-z ]", "", head.lower())[:60]
        if not head or norm in seen or not RUMOUR.search(text):
            continue
        seen.add(norm)
        src = str(n.get("source", ""))
        rows.append(dict(date=pd.Timestamp(int(n.get("datetime", 0)), unit="s"), headline=head, source=src,
                         trusted=any(t in src.lower() for t in TRUSTED), link=n.get("url", ""),
                         tickers=str(n.get("related", ""))))
    d = pd.DataFrame(rows)
    return d.sort_values("date", ascending=False).head(max_items) if not d.empty else d
