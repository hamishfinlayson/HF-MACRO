"""
stats.py - STATS CHECK for every HF Macro model (PC version).

Plain tools from a Data Analysis course, used to tell a real edge from luck:
  * paired t-test      : model vs the S&P 500 over the SAME rounds (4-week blocks), with a 95% confidence interval
  * confidence intervals: for any average (t-interval) and any win rate (Wilson interval for a proportion)
  * correlation        : does a signal line up with the returns that FOLLOW it? (r, strength, p-value)
  * two-group t-test   : average returns when a signal is ON vs OFF (Welch's independent-samples t-test)
  * power              : the smallest edge the data could reliably spot (so a 'no' isn't over-read: Type II error)
  * idea counter       : how many ideas have been tested, so a pass at 5% can be weighed against luck (Type I error)
No scipy needed: the t-distribution is worked out here with the standard incomplete-beta formula.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ALPHA = 0.05
MIN_N = 30                       # fewer than this and a number gets a 'small sample' flag
MATTERS_PCT_YEAR = 2.0           # an edge smaller than this (% a year) is too small to matter after costs and tax
ROUNDS_PER_YEAR = 13             # 4-week rounds in a year

# ---------------------------------------------------------------- the t-distribution (no scipy)


def _betacf(a, b, x):
    m_max, eps, fpmin = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > fpmin else fpmin)
    h = d
    for m in range(1, m_max + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > fpmin else fpmin)
        c = 1 + aa / c
        c = c if abs(c) > fpmin else fpmin
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > fpmin else fpmin)
        c = 1 + aa / c
        c = c if abs(c) > fpmin else fpmin
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1 - math.exp(lbeta) * _betacf(b, a, 1 - x) / b


def t_p(t, df):
    """Two-sided p-value for a t statistic with df degrees of freedom."""
    if not np.isfinite(t) or df <= 0:
        return float("nan")
    return _betai(df / 2, 0.5, df / (df + t * t))


def t_crit(df, alpha=ALPHA):
    """The t value that leaves alpha/2 in each tail (e.g. ~1.96 for big samples, 2.04 for 30)."""
    if df <= 0:
        return float("nan")
    lo, hi = 0.0, 50.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if t_p(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- building blocks


def mean_ci(x, alpha=ALPHA):
    """Average with its 95% confidence interval (t-interval)."""
    x = pd.Series(x).dropna().astype(float)
    n = len(x)
    if n < 2:
        return dict(n=n, mean=float(x.mean()) if n else np.nan, lo=np.nan, hi=np.nan, se=np.nan, small=True)
    m, se = float(x.mean()), float(x.std(ddof=1) / math.sqrt(n))
    tc = t_crit(n - 1, alpha)
    return dict(n=n, mean=m, lo=m - tc * se, hi=m + tc * se, se=se, small=n < MIN_N)


def proportion_ci(wins, n, alpha=ALPHA):
    """Win rate with its 95% Wilson confidence interval (the interval for a proportion)."""
    if n == 0:
        return dict(n=0, p=np.nan, lo=np.nan, hi=np.nan, small=True)
    z = 1.959963984540054 if alpha == 0.05 else -_norm_ppf(alpha / 2)
    p = wins / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return dict(n=n, p=p * 100, lo=(centre - half) * 100, hi=(centre + half) * 100, small=n < MIN_N)


def _norm_ppf(q):
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def paired_test(a, b, alpha=ALPHA):
    """Paired t-test: is the average of (a - b) different from 0? a and b are measured over the SAME rounds."""
    d = (pd.Series(a) - pd.Series(b)).dropna().astype(float)
    n = len(d)
    ci = mean_ci(d, alpha)
    if n < 2 or ci["se"] == 0:
        return dict(**ci, t=np.nan, p=np.nan, sd=np.nan)
    t = ci["mean"] / ci["se"]
    return dict(**ci, t=t, p=t_p(t, n - 1), sd=float(d.std(ddof=1)))


def welch_test(on, off, alpha=ALPHA):
    """Independent-samples (Welch) t-test: are average returns different when a signal is ON vs OFF?"""
    x, y = pd.Series(on).dropna().astype(float), pd.Series(off).dropna().astype(float)
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return dict(n_on=nx, n_off=ny, mean_on=x.mean() if nx else np.nan, mean_off=y.mean() if ny else np.nan,
                    diff=np.nan, lo=np.nan, hi=np.nan, p=np.nan, small=True)
    vx, vy = x.var(ddof=1) / nx, y.var(ddof=1) / ny
    se = math.sqrt(vx + vy)
    diff = float(x.mean() - y.mean())
    df = (vx + vy) ** 2 / (vx * vx / (nx - 1) + vy * vy / (ny - 1)) if (vx + vy) > 0 else 1
    t = diff / se if se > 0 else np.nan
    tc = t_crit(df, alpha)
    return dict(n_on=nx, n_off=ny, mean_on=float(x.mean()), mean_off=float(y.mean()), diff=diff,
                lo=diff - tc * se, hi=diff + tc * se, t=t, p=t_p(t, df), small=min(nx, ny) < MIN_N)


def corr_test(x, y):
    """Pearson correlation r, its p-value (is r different from 0?) and a plain-English strength."""
    d = pd.DataFrame({"x": x, "y": y}).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(d)
    if n < 4 or d.x.std() == 0 or d.y.std() == 0:
        return dict(n=n, r=np.nan, p=np.nan, strength="not enough data", direction="", small=True)
    r = float(np.corrcoef(d.x, d.y)[0, 1])
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    a = abs(r)
    strength = "very weak" if a < 0.1 else "weak" if a < 0.3 else "moderate" if a < 0.5 else "strong"
    return dict(n=n, r=r, p=t_p(t, n - 2), strength=strength, direction="positive" if r > 0 else "negative",
                small=n < MIN_N)


def min_detectable(sd, n, alpha=ALPHA, power=0.8):
    """Smallest true average difference the test would spot 80% of the time (guards against Type II errors)."""
    if not (n and n > 2 and sd == sd):
        return np.nan
    return (t_crit(n - 1, alpha) + 0.8416212335729143) * sd / math.sqrt(n)


# ---------------------------------------------------------------- rounds and verdicts


def rounds(weekly, weeks=4):
    """Non-overlapping 4-week blocks (the model's holding period), compounded, in %. Index = end of each block."""
    w = pd.Series(weekly).dropna()
    if w.empty:
        return w
    g = np.arange(len(w)) // weeks
    out = (1 + w / 100).groupby(g).prod() - 1
    sizes = pd.Series(1, index=w.index).groupby(g).sum()
    ends = pd.Series(w.index).groupby(g).last()
    out = (out * 100)[sizes == weeks]
    out.index = pd.DatetimeIndex(ends[sizes == weeks].values)
    return out


def edge_vs_benchmark(model_weekly, bench_weekly, weeks=4, label_bench="the S&P 500"):
    """The headline test: paired t-test of the model vs the benchmark over the same 4-week rounds."""
    both = pd.concat([pd.Series(model_weekly, name="m"), pd.Series(bench_weekly, name="b")], axis=1).dropna()
    rm, rb = rounds(both["m"], weeks), rounds(both["b"], weeks)
    t = paired_test(rm, rb)
    per_year = ROUNDS_PER_YEAR * 4 / weeks
    t.update(year=t["mean"] * per_year, year_lo=t["lo"] * per_year, year_hi=t["hi"] * per_year,
             mde_year=min_detectable(t.get("sd", np.nan), t["n"]) * per_year,
             model=mean_ci(rm), bench=mean_ci(rb), win=proportion_ci(int((rm > 0).sum()), len(rm)),
             beat=proportion_ci(int((rm > rb).sum()), len(rm)), bench_label=label_bench, rounds_m=rm, rounds_b=rb)
    t["light"], t["verdict"] = verdict(t, label_bench)
    return t


def verdict(t, what="the S&P 500"):
    """Traffic light + one plain-English line."""
    n, p = t.get("n", 0), t.get("p", np.nan)
    if not n or n < 2 or p != p:
        return "🟠", "Not enough data to test yet."
    lo, hi, yr = t.get("year_lo", t["lo"]), t.get("year_hi", t["hi"]), t.get("year", t["mean"])
    unit = "% a year" if "year" in t else "% a round"
    half = (hi - lo) / 2
    if lo > 0:
        small = yr < MATTERS_PCT_YEAR if "year" in t else False
        line = f"Evidence this beats {what} by about {yr:.1f}{unit}, give or take {half:.1f}."
        if small:
            line += " Real, but probably too small to matter after costs and tax."
        return ("🟠" if small else "🟢"), line
    if hi < 0:
        return "🔴", f"Evidence this does WORSE than {what}, by about {abs(yr):.1f}{unit} (give or take {half:.1f})."
    if n < MIN_N:
        return "🟠", f"Not enough rounds yet ({n}) to tell. The 95% range runs from {lo:+.1f} to {hi:+.1f}{unit}."
    return "🔴", (f"No evidence this beats {what}. The 95% range for the difference ({lo:+.1f} to {hi:+.1f}{unit}) "
                 "includes 0, so a good run could be luck.")


def fmt_ci(d, unit="%", digits=2):
    if d is None or d.get("n", 0) == 0 or d.get("lo") != d.get("lo"):
        return "–"
    m = d.get("mean", d.get("p"))
    flag = " ⚠ under 30" if d.get("small") else ""
    return f"{m:+.{digits}f}{unit} (95%: {d['lo']:+.{digits}f} to {d['hi']:+.{digits}f}) · n={d['n']}{flag}"


def fmt_rate(d):
    if d is None or d.get("n", 0) == 0:
        return "–"
    flag = " ⚠ under 30" if d.get("small") else ""
    return f"{d['p']:.0f}% (95%: {d['lo']:.0f}–{d['hi']:.0f}%) · n={d['n']}{flag}"


def fmt_p(p):
    if p != p:
        return "–"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def light_p(p, effect_ok=True, n=99):
    if p != p or n < MIN_N:
        return "🟠"
    return "🟢" if (p < ALPHA and effect_ok) else "🔴"


# ---------------------------------------------------------------- the idea log (for the Type I error count)

SEED_IDEAS = [
    # (date, area, idea, result, why/lesson)
    ("2026-10", "Commodities", "Momentum 12-1", "kept", "Best on its own in all three tests; the classic setting beat 3/6/9-month versions."),
    ("2026-10", "Commodities", "Trust-weighted momentum", "kept", "Near-twin of momentum; dropping it hurt every test."),
    ("2026-10", "Commodities", "52-week high", "kept", "Earns its place; 2-year high promising but not proven."),
    ("2026-10", "Commodities", "Averages agree + momentum", "kept", "Strong on build years, fine on fresh."),
    ("2026-10", "Commodities", "Monte Carlo: trend continues", "parked", "Dragged the model down; more sims and a 4-week horizon didn't fix it."),
    ("2026-10", "Commodities", "Quiet climbers", "parked", "+2.7%/yr alone on the build years; model better without it in all 3 tests."),
    ("2026-10", "Commodities", "Hold losers 1 more week (reassess)", "kept", "Helped in all 3 tests."),
    ("2026-10", "Commodities", "Pause after 3 losing weeks", "kept", "Mixed but smaller drops; kept by choice."),
    ("2026-10", "Commodities", "6-month switch to the S&P", "kept", "Unseen tests roughly level with the S&P; smoother."),
    ("2026-10", "Commodities", "Personality filter per commodity", "kept", "Small help; kept with an off switch."),
    ("2026-10", "Commodities", "Trailing stops", "cut", "Cut the big winners that pay for the losers."),
    ("2026-10", "Commodities", "-2% / -3% / -5% stops", "cut", "Commodities wobble 2% a day; stops hit by noise, average trade fell."),
    ("2026-10", "Commodities", "Sell on Thursday instead of Friday", "cut", "Tie on build years, worse on both fresh tests."),
    ("2026-10", "Commodities", "Profit lock (sell when up 0.6-2% in a week)", "cut", "Cut the big weeks; turned 2001-16 negative."),
    ("2026-10", "Commodities", "Only trade the top 1-2 most confident picks", "cut", "No better return, much bigger drops."),
    ("2026-10", "Commodities", "1-5 star confidence ratings", "cut", "5-star trades no better than 1-star; no ladder in any test."),
    ("2026-10", "Commodities", "Fast trends", "cut", "Worse."),
    ("2026-10", "Commodities", "FX version of the model", "cut", "The profit was all USD/TRY; fake edge."),
    ("2026-10", "Commodities", "Week-2/3 check-ins", "cut", "A tie; not worth the extra trades."),
    ("2026-10", "Commodities", "Slump filter", "cut", "Mixed."),
    ("2026-10", "Commodities", "Company shares + SEC accounts as a 5th strategy", "cut", "Accounts lag prices by months; shares just echo momentum."),
    ("2026-10", "Commodities", "Pick top 10/15/25/33% instead of 20%", "cut", "20% best."),
    ("2026-10", "Commodities", "Hold 2/3/6/8 weeks instead of 4", "cut", "4 weeks clearly best."),
    ("2026-10", "Commodities", "Momentum 3/6/9-month or blended", "cut", "Worse, some badly."),
    ("2026-10", "Commodities", "Averages agree with 4-week Monte Carlo", "cut", "Worse on build years (only better on fresh = cheating to pick)."),
    ("2026-10", "Macro stars", "Trade 5-star dashboard signals (all assets)", "cut", "43% winners, lost money over the last year; 18-year profit was one lucky year."),
    ("2026-10", "Macro stars", "Trade 5-star signals on commodities", "cut", "Coin-flip win rate; 8 of 10 trading years lost."),
    ("2026-10", "Macro stars", "5-star commodities with a 2% stop", "cut", "Less bad, still loses without 2021."),
    ("2026-10", "Bubble", "Bubble Watch checklist (66 signs)", "kept", "Score separated big-fall years on build AND unseen years (AUC 0.80 / 0.78)."),
    ("2026-11", "Pairs", "Rival-stock pairs (short the leader, buy the laggard)", "cut", "Real raw edge, shrinking; CFD fees on both legs turn it negative."),
    ("2026-11", "Pairs", "Commodity pairs", "cut", "Commodities trend, they don't snap back."),
    ("2026-11", "Pairs", "Pairs only when VIX 30+", "cut", "Positive on unseen years but negative on build years."),
    ("2026-11", "Pairs", "Rival sympathy bounce", "cut", "Hedged ~0 after costs; unhedged is just buying the dip, beaten by the S&P."),
    ("2026-11", "Smart money", "CFTC: follow the hedge funds", "cut", "Worked 2001-12, failed on held-out years: their buying is already priced in."),
    ("2026-11", "Smart money", "CFTC: fade the crowd", "cut", "No edge; crowded trades stay crowded."),
    ("2026-11", "Smart money", "CFTC: follow the producers", "cut", "No edge; producers hedge for business reasons."),
    ("2026-11", "Smart money", "CFTC filters on the commodities model", "cut", "None helped; 'only when funds add' made it worse (p = 0.03)."),
    ("2026-11", "Smart money", "13F: copy each fund's top 3", "cut", "Slightly ahead of the S&P, well within luck (p 0.29 / 0.46)."),
    ("2026-11", "Smart money", "13F: copy new buys of 2%+", "cut", "Behind the S&P on held-out years; the 45-day delay hurts."),
    ("2026-11", "Smart money", "13F: consensus top-10 of 3+ funds", "parked", "Beat the S&P (p 0.053) but level with the Nasdaq 100: it's a big-tech bet."),
    ("2026-11", "Smart money", "Insider cluster buys", "cut", "Early edge vanished: -1.2%/month vs S&P since 2018 (p < 0.001)."),
    ("2026-11", "Smart money", "Strong insider clusters only", "cut", "No edge."),
    ("2026-11", "Big-fund strategies", "Trend following across all markets (AQR/Man AHL style)", "cut",
     "Raw edge ~+5%/yr and gains in 2008/2020/2022, but CFD financing on both sides wipes it out (held-out -1.2%/yr)."),
    ("2026-11", "Big-fund strategies", "Trend following, long only", "cut", "+1.6%/yr held-out vs S&P +12.9%."),
    ("2026-11", "Big-fund strategies", "Bond carry (long 7-10y when the curve is steep)", "cut", "Same as just holding 7-10y bonds (p 0.82)."),
    ("2026-11", "Big-fund strategies", "FX carry", "parked", "Not tested: FRED dropped the interest-rate series; T212 swap markups likely kill it anyway."),
    ("2026-11", "Big-fund strategies", "Value / momentum / quality / low-vol factors (US, 1963-2026)", "cut",
     "Strong 1963-99, faded after 2000 (all 4: +1.6%/yr, p 0.06); the UK factor ETFs lagged MSCI World since 2014."),
    ("2026-11", "Big-fund strategies", "Risk parity / All Weather (with and without borrowing)", "cut",
     "Smaller drops (-20%) but +7%/yr vs S&P +12.9% on held-out years."),
    ("2026-11", "Big-fund strategies", "Adding trend or risk parity to 50/50 model + S&P", "cut",
     "Smaller drops (-20 to -22% vs -24%) but lower returns; the current 50/50 stays best."),
    ("2026-11", "Takeovers", "Merger arbitrage (buy announced deals)", "cut", "Funds made +2-5%/yr, well behind the S&P; like a savings account."),
    ("2026-11", "Takeovers", "PE target spotter from company accounts", "cut", "Held-out AUC 0.51: no better than a coin flip."),
    ("2026-11", "Takeovers", "Activist 13D 'sale' filings predict takeovers", "kept",
     "5-7x more likely to be taken private within 2 years (12% vs 1.7%), held-out tested - shown as a watch list."),
    ("2026-11", "Takeovers", "Buy every activist 13D target", "cut", "Survivors lagged the S&P (-7.4% over 6 months, p 0.001)."),
    ("2026-11", "Takeovers", "The opposite: short activist targets, buy the S&P", "cut",
     "Lost in 2005-15 at every holding period; 2016-24 gain was just small companies lagging big ones (gone vs a small-company index)."),
    ("2026-11", "Copied models", "Dual Momentum (Antonacci), as published", "cut", "Beat the S&P until 2014 (when published), -5.9%/yr since (p 0.01)."),
    ("2026-11", "Copied models", "Faber 10-month rule, as published", "cut", "Tiny crashes (-8%) but -8.4%/yr vs the S&P since 2015."),
    ("2026-11", "Copied models", "AQR trend, ISA version (long or cash)", "cut", "-10%/yr vs the S&P since 2015; CFD version already failed on costs."),
    ("2026-11", "Copied models", "Dual Momentum with faster signals", "cut", "-5.4%/yr vs the S&P since 2015."),
    ("2026-11", "Copied models", "S&P with crash switch (both signals)", "cut",
     "Best on 2003-14 (+3%/yr, -18% worst drop vs -53%) but -4%/yr since 2015 - insurance, not a strategy."),
    ("2026-11", "Copied models", "S&P with crash switch (either signal)", "cut", "-5.9%/yr vs the S&P since 2015."),
    ("2026-11", "Copied models", "50 model / 50 Dual Momentum", "cut", "Behind the current 50/50 model + S&P since 2015."),
    ("2026-11", "Copied models", "50 model / 50 S&P-with-crash-switch", "cut", "Behind the current 50/50 model + S&P since 2015."),
    ("2026-11", "Copied models", "1/3 model, 1/3 S&P, 1/3 Dual Momentum", "cut", "Behind the current 50/50 model + S&P since 2015."),
    ("2026-11", "Carry", "Commodity carry: long backwardated, short contango (AQR 'Carry')", "cut",
     "+3.6%/yr in 2010-17 (p 0.21), -3.4%/yr in 2018-26; the signal faded to zero after 2017. Adding it cut the 50/50 mix's return."),
    ("2026-11", "Carry", "Commodity carry, long-only top third", "cut", "+3.4%/yr then +7.8%/yr - no better than holding all commodities (+7.7%) since 2018."),
    ("2026-11", "Carry", "FX carry (central-bank rates)", "cut", "+1.0%/yr 2001-14, +4.1%/yr since (p 0.14), crashes of -13% in a month."),
]


def idea_log_path(base):
    return Path(base) / "idea_log.json"


def load_ideas(base):
    p = idea_log_path(base)
    try:
        return json.loads(p.read_text())
    except Exception:
        return [dict(date=d, area=a, idea=i, result=r, why=w, p=None) for d, a, i, r, w in SEED_IDEAS]


def save_ideas(base, ideas):
    p = idea_log_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ideas, indent=1))


def luck_line(n_ideas, alpha=ALPHA):
    exp = n_ideas * alpha
    return (f"{n_ideas} ideas tested so far. At a 5% significance level, about {exp:.0f} of them would 'pass' by luck "
            f"alone, so one pass on its own isn't proof. A stricter bar that allows for all {n_ideas} tests "
            f"(Bonferroni) is p below {alpha / max(n_ideas, 1):.4f}.")
