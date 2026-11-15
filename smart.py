"""
smart.py - SMART MONEY (PC version only).

What the big players are doing, from free official sources:
  1. CFTC Commitments of Traders (weekly): how hedge funds ('managed money') and producers/merchants are positioned
     in every commodity HF Macro trades. Positions are as of Tuesday, published Friday; we treat them as known
     from the following Friday.
  2. SEC 13F filings (quarterly, up to 45 days late): what 16 concentrated stock-pickers own, bought and sold.
  3. SEC Form 4 insider data sets (quarterly bulk files): companies where several directors/officers bought their
     own shares with their own money in the same month.

All three were TESTED before this page was built (rules fixed in advance, built on early years, checked on later
years, costs included). The results are in TESTS below and on the page. None of them is used to change trades.
The SEC asks every user to give a contact email with each request: the page asks for it once and keeps it in your
own settings file on this PC.
"""

import csv
import html
import io
import re
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CFTC_CODES = {
    "067651": ("CL=F", "WTI crude oil"), "06765T": ("BZ=F", "Brent crude"), "022651": ("HO=F", "Heating oil"),
    "111659": ("RB=F", "Petrol (RBOB)"), "023651": ("NG=F", "Natural gas"), "088691": ("GC=F", "Gold"),
    "084691": ("SI=F", "Silver"), "085692": ("HG=F", "Copper"), "076651": ("PL=F", "Platinum"),
    "075651": ("PA=F", "Palladium"), "002602": ("ZC=F", "Corn"), "001602": ("ZW=F", "Wheat"),
    "001612": ("KE=F", "KC wheat"), "005602": ("ZS=F", "Soybeans"), "007601": ("ZL=F", "Soybean oil"),
    "026603": ("ZM=F", "Soybean meal"), "004603": ("ZO=F", "Oats"), "039601": ("ZR=F", "Rough rice"),
    "057642": ("LE=F", "Live cattle"), "061641": ("GF=F", "Feeder cattle"), "054642": ("HE=F", "Lean hogs"),
    "073732": ("CC=F", "Cocoa"), "083731": ("KC=F", "Coffee"), "080732": ("SB=F", "Sugar"),
    "033661": ("CT=F", "Cotton"), "040701": ("OJ=F", "Orange juice"),
}
FUNDS = {"Berkshire Hathaway": "0001067983", "Pershing Square": "0001336528", "Appaloosa": "0001656456",
         "Baupost": "0001061768", "Greenlight Capital": "0001079114", "Third Point": "0001040273",
         "Lone Pine": "0001061165", "Viking Global": "0001103804", "Duquesne Family Office": "0001536411",
         "Scion Asset Management": "0001649339", "Akre Capital": "0001112520", "Fundsmith": "0001569205",
         "Himalaya Capital": "0001709323", "Coatue": "0001135730", "Tiger Global": "0001167483",
         "Gotham Asset Management": "0001510387"}
FUND_PEOPLE = {"Berkshire Hathaway": "Warren Buffett", "Pershing Square": "Bill Ackman", "Appaloosa": "David Tepper",
               "Baupost": "Seth Klarman", "Greenlight Capital": "David Einhorn", "Third Point": "Dan Loeb",
               "Lone Pine": "Stephen Mandel's firm", "Viking Global": "Andreas Halvorsen", "Duquesne Family Office":
               "Stanley Druckenmiller", "Scion Asset Management": "Michael Burry", "Akre Capital": "Chuck Akre's firm",
               "Fundsmith": "Terry Smith", "Himalaya Capital": "Li Lu", "Coatue": "Philippe Laffont",
               "Tiger Global": "Chase Coleman", "Gotham Asset Management": "Joel Greenblatt"}

# ---------------------------------------------------------------- what the tests found (30 Oct - 14 Nov 2026)
# Each idea: rules fixed before testing; build years first, then held-out years; costs included.
TESTS = [
    dict(area="CFTC", idea="Follow the hedge funds (buy what they've added to most in 4 weeks)", light="🔴",
         build="+5.5%/yr (level with buying everything)", held="2013-16: +6.1% · 2017-26: -0.8% · new commodities: -4.3%",
         verdict="Worked early, failed on the held-out years.", why="Hedge-fund buying is already in the price by the time it's published."),
    dict(area="CFTC", idea="Fade the crowd (buy what hedge funds are least long, vs 3 years)", light="🔴",
         build="+1.7%/yr (worse than buying everything)", held="2013-16: -10.5% · 2017-26: +3.0% · new: -0.8%",
         verdict="No edge.", why="Crowded trades can stay crowded for months."),
    dict(area="CFTC", idea="Follow the producers/hedgers (least short vs 3 years)", light="🔴",
         build="+2.2%/yr", held="2013-16: -19.0% · 2017-26: +3.2% · new: -4.5%",
         verdict="No edge.", why="Producers hedge for business reasons, not to predict prices."),
    dict(area="CFTC", idea="Filters on the commodities model (skip crowded picks, or only when funds are adding)", light="🔴",
         build="none helped", held="'Only when funds are adding': -14%/yr vs the model (p = 0.03)",
         verdict="None improved the model; one made it clearly worse.", why="The model already follows the trend the funds follow."),
]
TESTS_PENDING = [
    dict(area="13F", idea="Copy each fund's top 3 holdings (from the day each filing is public)", light="🔴",
         build="2013-19: +15.3%/yr vs S&P +12.9% (p = 0.29)", held="2020-26: +16.6%/yr vs S&P +14.8% (+2.5, range -4.2 to +9.1, p = 0.46)",
         verdict="A little ahead of the S&P both times, but well within luck.", why="By the time it's filed the stocks are already big, well-known winners."),
    dict(area="13F", idea="Copy each fund's new buys of 2%+", light="🔴",
         build="+13.0%/yr vs +12.9% (p = 0.84)", held="+9.5%/yr vs +14.8% (p = 0.63)",
         verdict="No edge; behind the S&P on held-out years.", why="New positions are often small first steps or hedges; the 45-day delay hurts most here."),
    dict(area="13F", idea="Consensus: stocks in the top 10 of 3+ funds", light="🟠",
         build="+17.6%/yr vs S&P +12.9% (p = 0.28)", held="+24.0%/yr vs S&P +14.8% (+8.4, range -0.1 to +16.9, p = 0.053)",
         verdict="Beat the S&P, but it's really a big-tech bet: vs the Nasdaq 100 it was level (p = 1.0 build, 0.21 held-out). 2022: -36%.",
         why="Star growth funds all own the same mega-cap tech; copying them = owning the Nasdaq 100 with extra swings."),
    dict(area="Insiders", idea="Buy when 2+ insiders (incl. a director/officer) buy $100k+ within 30 days, hold 1 or 3 months", light="🔴",
         build="2010-17: +0.5% per month vs S&P (p = 0.03)", held="2018-26: -1.2% per month vs S&P (p < 0.001); 3-month -1.5%",
         verdict="Worked early, clearly WORSE than the S&P since 2018.", why="Widely tracked now; mostly small companies with big spreads. Missing bust companies make the real result worse still."),
    dict(area="Insiders", idea="Only strong clusters (3+ insiders, $500k+)", light="🔴",
         build="+0.3% per 3 months (p = 0.84)", held="-0.9% per 3 months (p = 0.44)", verdict="No edge.", why="Bigger buys didn't help."),
]
HEADLINE = ("🔴 none of the 9 ideas beat the market on the held-out years after costs. The closest, copying stocks that 3+ star "
            "funds hold, beat the S&P but only because it's a big-tech bet: it did no better than just buying the Nasdaq 100. "
            "So this page is for information: see who's positioned where, but don't trade off it.")


# ---------------------------------------------------------------- downloads


def _get(url, ua, js=True, params=None, timeout=60):
    for k in range(4):
        try:
            r = requests.get(url, headers=ua, params=params, timeout=timeout)
            if r.status_code == 429:
                time.sleep(4 * (k + 1))
                continue
            r.raise_for_status()
            time.sleep(0.15)
            return r.json() if js else r
        except Exception:
            if k == 3:
                raise
            time.sleep(2)


def sec_headers(contact):
    return {"User-Agent": f"HF Macro personal research {contact}", "Accept-Encoding": "gzip, deflate"}


def cftc_download(since="2018-01-01"):
    """Both CFTC reports for the commodities HF Macro trades, from the CFTC's public API."""
    where = ("cftc_contract_market_code in(" + ",".join(f"'{c}'" for c in CFTC_CODES) +
             f") AND report_date_as_yyyy_mm_dd >= '{since}'")
    out = {}
    for name, ds in (("disagg", "72hh-3qpy"), ("legacy", "6dca-aqww")):
        rows, off = [], 0
        while True:
            part = _get(f"https://publicreporting.cftc.gov/resource/{ds}.json", {"User-Agent": "HF Macro"},
                        params={"$where": where, "$limit": 50000, "$offset": off, "$order": "report_date_as_yyyy_mm_dd"},
                        timeout=120)
            rows += part
            off += 50000
            if len(part) < 50000:
                break
        out[name] = pd.DataFrame(rows)
    return out


def _net(df, long_col, short_col):
    d = df.copy()
    d["date"] = pd.to_datetime(d["report_date_as_yyyy_mm_dd"].astype(str).str[:10], errors="coerce")
    d["code"] = d["cftc_contract_market_code"].astype(str).str.strip().str.upper()
    oi = pd.to_numeric(d["open_interest_all"], errors="coerce")
    d["net"] = (pd.to_numeric(d[long_col], errors="coerce") - pd.to_numeric(d[short_col], errors="coerce")) / oi * 100
    return d.dropna(subset=["date", "net"]).groupby(["date", "code"])["net"].mean().unstack().sort_index()


def cftc_table(raw):
    """One row per commodity: where hedge funds and producers stand now, vs the last 3 years."""
    mm = _net(raw["disagg"], "m_money_positions_long_all", "m_money_positions_short_all")
    pr = _net(raw["disagg"], "prod_merc_positions_long", "prod_merc_positions_short")
    rows = []
    for code, (tk, nm) in CFTC_CODES.items():
        if code not in mm.columns:
            continue
        s, p = mm[code].dropna(), pr[code].dropna() if code in pr.columns else pd.Series(dtype=float)
        if len(s) < 60:
            continue
        last3 = s.iloc[-156:]
        pct = (last3 < s.iloc[-1]).mean() * 100
        z = (s.iloc[-1] - last3.mean()) / last3.std() if last3.std() > 0 else np.nan
        chg = s.iloc[-1] - s.iloc[-5] if len(s) > 5 else np.nan
        pp = (p.iloc[-156:] < p.iloc[-1]).mean() * 100 if len(p) > 60 else np.nan
        flag = "🔥 Crowded long" if z >= 2 else "🧊 Crowded short" if z <= -2 else ("Heavy long" if z >= 1 else "Heavy short" if z <= -1 else "Normal")
        rows.append(dict(ticker=tk, name=nm, hf_net=s.iloc[-1], hf_pct=pct, hf_z=z, hf_chg4=chg, prod_net=p.iloc[-1] if len(p) else np.nan,
                         prod_pct=pp, flag=flag, asof=s.index[-1]))
    return pd.DataFrame(rows)


def latest_13f(contact, n_filings=2, progress=None):
    """The last n 13F filings of each fund: issuer, CUSIP, value, weight."""
    ua = sec_headers(contact)
    out = []
    for i, (fund, cik) in enumerate(FUNDS.items()):
        if progress:
            progress((i + 1) / len(FUNDS), fund)
        try:
            sub = _get(f"https://data.sec.gov/submissions/CIK{cik}.json", ua)
            rec = sub["filings"]["recent"]
            fl = [(rec["accessionNumber"][k], rec["filingDate"][k], rec["reportDate"][k])
                  for k, f in enumerate(rec["form"]) if f == "13F-HR"][:n_filings]
            for acc, filed, period in fl:
                base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
                idx = _get(base + "/index.json", ua)
                names = [it["name"] for it in idx["directory"]["item"] if it["name"].lower().endswith(".xml")]
                names = [x for x in names if "primary_doc" not in x.lower()] or names
                for nm in names:
                    rows = parse_infotable(_get(base + "/" + nm, ua, js=False).text)
                    if rows:
                        for r in rows:
                            out.append(dict(fund=fund, filed=filed, period=period, **r))
                        break
        except Exception:
            continue
    df = pd.DataFrame(out)
    if df.empty:
        return df
    df = df[(df["putcall"] == "") & (df["share_type"].str.upper() == "SH")].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.groupby(["fund", "filed", "period", "cusip", "issuer"], as_index=False)["value"].sum()
    df["weight"] = df["value"] / df.groupby(["fund", "period"])["value"].transform("sum") * 100
    return df


def parse_infotable(xml):
    xml = re.sub(r"<(/?)[A-Za-z0-9_]+:", r"<\1", xml)
    rows = []
    for blk in re.findall(r"<infoTable>(.*?)</infoTable>", xml, re.S | re.I):
        g = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", blk, re.S | re.I) or [None, ""])[1].strip()
        rows.append(dict(issuer=g("nameOfIssuer").title(), cusip=g("cusip").upper(), value=g("value"),
                         share_type=g("sshPrnamtType"), putcall=g("putCall")))
    return rows


def fund_moves(h):
    """Per fund: latest top holdings, new buys, sells; plus stocks bought by several funds."""
    funds = {}
    h = h.copy()
    h["issuer"] = h["issuer"].astype(str).map(html.unescape).str.title()
    h = h.groupby(["fund", "filed", "period", "issuer"], as_index=False)[["value", "weight"]].sum()   # share classes merged
    h["cusip"] = h["issuer"]
    newest = pd.to_datetime(h["period"]).max()
    for fund, g in h.groupby("fund"):
        if pd.to_datetime(g["period"]).max() < newest - pd.Timedelta(days=200):
            continue                      # stopped filing (e.g. Scion closed its 13F in 2025)
        periods = sorted(g["period"].unique())
        cur = g[g["period"] == periods[-1]].sort_values("weight", ascending=False)
        prev = g[g["period"] == periods[-2]] if len(periods) > 1 else cur.iloc[0:0]
        pw = prev.set_index("cusip")["weight"]
        cur = cur.assign(prev_w=cur["cusip"].map(pw).fillna(0.0))
        new = cur[(cur["prev_w"] == 0) & (cur["weight"] >= 0.1)]
        added = cur[(cur["prev_w"] > 0) & (cur["weight"] > cur["prev_w"] + 1)]
        sold = prev[~prev["cusip"].isin(cur["cusip"]) & (prev["weight"] >= 0.1)].sort_values("weight", ascending=False)
        funds[fund] = dict(period=periods[-1], filed=cur["filed"].iloc[0] if len(cur) else "", top=cur.head(5),
                           new=new.head(5), added=added.head(5), sold=sold.head(5), n=len(cur))
    buys = pd.concat([f["new"].assign(fund=k) for k, f in funds.items()] + [f["added"].assign(fund=k) for k, f in funds.items()])
    crowd = (buys.groupby("issuer")["fund"].agg(lambda x: sorted(set(x))).reset_index()      # share classes merged
             if not buys.empty else pd.DataFrame(columns=["issuer", "fund"]))
    crowd["n"] = crowd["fund"].apply(len)
    return funds, crowd[crowd["n"] >= 2].sort_values("n", ascending=False)


def recent_insider_clusters(contact, quarters=2):
    """Cluster buys (2+ insiders incl. a director/officer, $100k+, within 30 days) in the latest SEC data sets."""
    ua = sec_headers(contact)
    now = pd.Timestamp.now()
    cands = []
    for back in range(0, 6):
        q = (now - pd.DateOffset(months=3 * back))
        cands.append((q.year, (q.month - 1) // 3 + 1))
    rows, got = [], 0
    for y, q in cands:
        if got >= quarters:
            break
        url = f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"
        try:
            r = requests.get(url, headers=ua, timeout=300)
            if r.status_code != 200:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            def tsv(name):
                nm = [x for x in z.namelist() if x.upper().endswith(name)][0]
                return pd.read_csv(z.open(nm), sep="\t", dtype=str, on_bad_lines="skip")
            sub, own, tr = tsv("SUBMISSION.TSV"), tsv("REPORTINGOWNER.TSV"), tsv("NONDERIV_TRANS.TSV")
            tr = tr[tr["TRANS_CODE"] == "P"].merge(sub, on="ACCESSION_NUMBER", how="left").merge(
                own.drop_duplicates("ACCESSION_NUMBER"), on="ACCESSION_NUMBER", how="left")
            rows.append(tr)
            got += 1
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(), None
    d = pd.concat(rows, ignore_index=True)
    d["filed"] = pd.to_datetime(d["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
    d["v"] = pd.to_numeric(d["TRANS_SHARES"], errors="coerce") * pd.to_numeric(d["TRANS_PRICEPERSHARE"], errors="coerce")
    d["boss"] = d["RPTOWNER_RELATIONSHIP"].fillna("").str.contains("Director|Officer", case=False)
    d = d.dropna(subset=["filed"])
    asof = d["filed"].max()
    recent = d[d["filed"] >= asof - pd.Timedelta(days=45)]
    g = recent.groupby(["ISSUERTRADINGSYMBOL", "ISSUERNAME"]).agg(
        insiders=("RPTOWNERNAME", "nunique"), value=("v", "sum"), boss=("boss", "any"), last=("filed", "max"),
        price=("TRANS_PRICEPERSHARE", lambda x: pd.to_numeric(x, errors="coerce").mean())).reset_index()
    g = g[(g["insiders"] >= 2) & (g["value"] >= 100000) & g["boss"]]
    return g.sort_values(["insiders", "value"], ascending=False), asof
