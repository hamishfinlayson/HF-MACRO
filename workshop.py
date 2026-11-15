"""
workshop.py - the COMMODITIES WORKSHOP (PC version only).

Takes every strategy that can trade commodities and tries to find its best HONEST version:

  1. Clean the data: Yahoo's commodity prices jump when one futures contract expires and the next starts
     (a "roll"). Those jumps aren't real gains or losses, but they can fool reversal strategies. Each
     commodity is checked against an ETF that tracks it; days where the future jumps but the ETF doesn't
     are replaced with the ETF's move. Commodities without an ETF use a gap test.
  2. Real costs: Trading 212 commodity CFDs charge overnight fees on buys as well as shorts.
  3. Try every combination of: exit rule (hold, or take-profit/stop-loss levels), holding period
     (1, 2 or 4 weeks), minimum expected move, and an "only trade it while it's working" switch.
  4. Choose each strategy's best settings on the DISCOVERY years only, then report how those exact settings
     did on the UNSEEN years. That's the honest number.
  5. Check it year by year, by group (energy, metals, farming), how long it can lose for, and combine the
     best versions into one portfolio.

Just for fun and learning. Not financial advice.
"""

import numpy as np
import pandas as pd

import backtest

ETF_PROXY = {"CL=F": "USO", "BZ=F": "BNO", "NG=F": "UNG", "RB=F": "UGA", "GC=F": "GLD", "SI=F": "SLV",
             "PL=F": "PPLT", "HG=F": "CPER", "ZW=F": "WEAT", "ZC=F": "CORN", "ZS=F": "SOYB", "SB=F": "CANE"}
GROUPS = {"Energy": ["BZ=F", "CL=F", "NG=F", "RB=F", "HO=F"], "Metals": ["GC=F", "SI=F", "PL=F", "HG=F"],
          "Farming": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "SB=F", "CC=F", "CT=F", "LE=F"]}
EXITS = {  # name: (rule, take-profit mode, stop-loss mode, fixed tp, fixed sl)
    "Hold to Friday": ("Hold to Friday", None, None, 0, 0),
    "TP good week / SL bad week": ("Take-profit + stop-loss", backtest.TP_MODES[0], backtest.SL_MODES[0], 0, 0),
    "TP median / SL bad week": ("Take-profit + stop-loss", backtest.TP_MODES[1], backtest.SL_MODES[0], 0, 0),
    "TP good week / SL weak week": ("Take-profit + stop-loss", backtest.TP_MODES[0], backtest.SL_MODES[1], 0, 0),
    "TP 3% / SL 2%": ("Take-profit + stop-loss", "Fixed %", "Fixed %", 3.0, 2.0),
}
HOLDS = [1, 2, 4]
MIN_MOVES = [0.0, 0.3, 0.6]
LONG_FINANCING_WEEK = 0.10       # % a week for holding a commodity CFD long (about 5% a year)


# ================================================================= 1. cleaning roll jumps

def clean_rolls(prices, ohlc=None, proxies=None):
    """Returns (clean prices, clean ohlc, list of (ticker, date, raw move %, replaced with %, method))."""
    prices = prices.sort_index()
    r = prices.pct_change(fill_method=None)
    fixes = []
    r_clean = r.copy()
    for col in prices.columns:
        s = r[col]
        px = None
        if proxies is not None and ETF_PROXY.get(col) in getattr(proxies, "columns", []):
            px = proxies[ETF_PROXY[col]].reindex(prices.index).ffill(limit=3).pct_change(fill_method=None)
        if px is not None and px.notna().sum() > 250:
            diff = (s - px)
            typical = diff.abs().rolling(60, min_periods=20).median().shift(1)
            bad = (diff.abs() > 0.03) & (diff.abs() > 6 * typical) & (s.abs() > 0.025) & px.notna()
            for d in s.index[bad.fillna(False)]:
                fixes.append((col, d, s[d] * 100, px[d] * 100, f"vs {ETF_PROXY[col]} ETF"))
                r_clean.at[d, col] = px[d]
        elif ohlc is not None and "open" in ohlc:
            o = ohlc["open"][col].reindex(prices.index) if col in ohlc["open"] else None
            h = ohlc["high"][col].reindex(prices.index) if col in ohlc["high"] else None
            lo = ohlc["low"][col].reindex(prices.index) if col in ohlc["low"] else None
            if o is None:
                continue
            prev = prices[col].shift(1)
            gap = o / prev - 1
            day_range = (h - lo) / o
            mad = s.abs().rolling(60, min_periods=20).median().shift(1)
            # a roll looks like: a big overnight gap that explains the whole move, with a normal-sized day after it
            bad = (s.abs() > 6 * mad) & (gap.abs() > 0.9 * s.abs()) & (day_range < 0.3 * gap.abs()) & (s.abs() > 0.03)
            for d in s.index[bad.fillna(False)]:
                new = (prices[col][d] / o[d] - 1)
                fixes.append((col, d, s[d] * 100, new * 100, "gap test"))
                r_clean.at[d, col] = new
    clean = prices.copy()
    for col in prices.columns:
        if not any(f[0] == col for f in fixes):
            continue
        rc = r_clean[col]
        first = prices[col].first_valid_index()
        growth = (1 + rc.fillna(0)).cumprod()
        last = prices[col].last_valid_index()
        rebuilt = growth / growth[last] * prices[col][last]
        clean[col] = rebuilt.where(prices[col].notna() & (prices.index >= first))
    clean_ohlc = None
    if ohlc:
        factor = (clean / prices).where(prices.notna())
        clean_ohlc = {k: (v.reindex(index=prices.index, columns=prices.columns) * factor if k in ("open", "high", "low")
                          else v) for k, v in ohlc.items()}
        clean_ohlc["close"] = clean
    return clean, clean_ohlc, fixes


# ================================================================= 2-4. the grid

def _hold(pos, idx, h):
    if h == 1:
        return pos
    p = pos.copy()
    keep = np.zeros(len(idx), bool)
    keep[::h] = True
    p.loc[~keep] = np.nan
    return p.ffill().fillna(0)


def _stats(r):
    r = r.dropna()
    a = r[r != 0]
    if len(a) < 4:
        return None
    sd = a.std()
    curve = (1 + r / 100).cumprod()
    return dict(avg_week=a.mean(), weeks=len(a), win=(a > 0).mean() * 100,
                sharpe=a.mean() / sd * np.sqrt(52) if sd > 0 else 0.0, total=(curve.iloc[-1] - 1) * 100,
                max_dd=((curve / curve.cummax()) - 1).min() * 100)


def trust(r):
    """How long can it lose for? % of 1/3/6/12-month spells that made money, and the longest time below a past high."""
    r = r.fillna(0)
    out = {}
    for name, n in (("1 month", 4), ("3 months", 13), ("6 months", 26), ("12 months", 52)):
        roll = ((1 + r / 100).rolling(n).apply(np.prod, raw=True) - 1).dropna()
        out[name] = float((roll > 0).mean() * 100) if len(roll) else np.nan
    curve = (1 + r / 100).cumprod()
    under = curve < curve.cummax()
    longest, cur = 0, 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    out["longest_underwater_weeks"] = longest
    out["max_dd"] = float(((curve / curve.cummax()) - 1).min() * 100)
    return out


def _block_stop(pos, Fi, h, lim):
    """Sell a holding for the rest of its h-week hold once it's down more than |lim|% (checked at weekly closes)."""
    p = pos.copy()
    blk = np.arange(len(p)) // h
    vals, fv = p.to_numpy(dtype=float, copy=True), Fi.reindex(index=p.index, columns=p.columns).to_numpy(dtype=float)
    for j in range(p.shape[1]):
        cum, b0, dead = 0.0, -1, False
        for i in range(len(p)):
            if blk[i] != b0:
                b0, cum, dead = blk[i], 0.0, False
            if vals[i, j] != 0:
                if dead:
                    vals[i, j] = 0.0
                else:
                    x = fv[i, j]
                    x = 0.0 if np.isnan(x) else x * np.sign(vals[i, j])
                    cum = ((1 + cum / 100) * (1 + x / 100) - 1) * 100
                    if cum < lim:
                        dead = True
    return pd.DataFrame(vals, index=p.index, columns=p.columns)


def check_dates(start, unseen_from, end):
    """Returns a plain-English problem with the dates, or None."""
    start, unseen_from, end = pd.Timestamp(start), pd.Timestamp(unseen_from), pd.Timestamp(end)
    if not start < unseen_from < end:
        return ("The dates are in the wrong order. They must go From → Unseen from → To, e.g. From 2017, "
                "Unseen from 2023, To today. Otherwise there are no unseen weeks to test on.")
    if (end - unseen_from).days < 365:
        return "The unseen part is under a year long: move 'Unseen from' earlier or 'To' later."
    if (unseen_from - start).days < 2 * 365:
        return "The discovery part is under two years: move 'From' earlier."
    return None


def run(prices, ohlc, start, end, unseen_from, proxies=None, recession=None, entry="Monday open",
        fin_long=LONG_FINANCING_WEEK, n_sims=500, progress=None, cls="Commodities", skip=()):
    start, end, unseen_from = pd.Timestamp(start), pd.Timestamp(end), pd.Timestamp(unseen_from)
    prices = prices.dropna(axis=1, how="all")
    if cls == "Commodities":
        clean, cohlc, fixes = clean_rolls(prices, ohlc, proxies)
    else:
        clean, cohlc, fixes = prices, ohlc, []
    groups = GROUPS if cls == "Commodities" else {cls: list(prices.columns)}
    W, R, F = backtest.weekly_frames(clean)
    fridays = W.index[(W.index >= start) & (W.index <= end)]
    f = backtest.features(clean, W)
    mc_parts = {}
    for i, col in enumerate(clean.columns):
        if progress:
            progress(0.4 * i / len(clean.columns), f"Monte Carlo through history: {col}")
        m = backtest.mc_at_dates(clean[col], fridays, 5, n_sims=n_sims, seed=i)
        if not m.empty:
            mc_parts[col] = m
    if not mc_parts:
        return None
    mc = {k: pd.DataFrame({c: m[k] for c, m in mc_parts.items() if k in m}).reindex(index=W.index, columns=W.columns)
          for k in next(iter(mc_parts.values())).columns}
    mc_rows = {(c, d): m.loc[d].to_dict() for c, m in mc_parts.items() for d in m.index}
    sim = backtest.TradeSim(cohlc, clean)
    Fi, vol = F.loc[fridays], f["vol60"].loc[fridays]
    bench = Fi.mean(axis=1)
    med = mc["median_trend"].loc[fridays]
    fr_list = list(fridays) + [fridays[-1] + pd.Timedelta(days=7)]
    sides = [n for n, (_, _, ap) in backtest.SIDES.items() if ap != "cross" and (ap is None or cls in ap) and n not in skip]
    volz = (f["vol60"] / f["vol60"].rolling(104, min_periods=26).median()).loc[fridays]
    calm = ~(volz > 1.5)
    series, rows = {}, []
    for si, side in enumerate(sides):
        if progress:
            progress(0.4 + 0.55 * si / len(sides), f"Trying every setting for: {side}")
        pos0 = backtest.side_positions(side, cls, f, R, mc, {"recession": recession}).reindex(
            index=W.index, columns=W.columns).fillna(0).loc[fridays]
        if (pos0 != 0).sum().sum() < 10:
            continue
        for wild, mm in [(wd, m_) for wd in (False, True) for m_ in MIN_MOVES]:
            pos_mm = backtest.min_move_filter(pos0.where(calm, 0.0) if wild else pos0, med, mm)
            for h in HOLDS:
                pos_h = _hold(pos_mm, fridays, h)
                exits = EXITS if h == 1 else {"Hold to Friday": EXITS["Hold to Friday"],
                                              "Hold + stop at -8% (weekly close)": EXITS["Hold to Friday"]}
                for ex, (rule, tpm, slm, tpf, slf) in exits.items():
                    pos = _block_stop(pos_h, Fi, h, -8) if "stop at -8%" in ex else pos_h
                    ret, w = backtest.side_returns(pos, Fi, cls, vol, True, True)
                    if rule != "Hold to Friday" or (entry == "Monday open" and h == 1):
                        r2, _, _ = backtest.rule_side_returns(w, fr_list, sim, cls, mc_rows, entry if h == 1 else "Friday close",
                                                              rule, tpm or backtest.TP_MODES[0], slm or backtest.SL_MODES[0],
                                                              tpf, slf, True)
                        ret = r2.reindex(fridays).fillna(0)
                    ret = ret - (w.clip(lower=0).sum(axis=1) * fin_long).where(ret != 0, 0.0)
                    for filt in (False, True):
                        r = ret
                        if filt:
                            working = ret.shift(1).rolling(13, min_periods=8).sum() > 0
                            r = ret.where(working, 0.0)
                        key = (side, mm, h, ex, filt, wild)
                        series[key] = r
                        d, u = _stats(r[r.index < unseen_from]), _stats(r[r.index >= unseen_from])
                        rows.append(dict(side=side, min_move=mm, hold_weeks=h, exit=ex, only_while_working=filt,
                                         skip_wild=wild,
                                         disc_avg=(d or {}).get("avg_week"), disc_sharpe=(d or {}).get("sharpe"),
                                         disc_weeks=(d or {}).get("weeks", 0), unseen_avg=(u or {}).get("avg_week"),
                                         unseen_sharpe=(u or {}).get("sharpe"), unseen_weeks=(u or {}).get("weeks", 0),
                                         unseen_total=(u or {}).get("total"), unseen_dd=(u or {}).get("max_dd"),
                                         unseen_win=(u or {}).get("win")))
    grid = pd.DataFrame(rows)
    if grid.empty:
        return None
    best_rows, default_key = [], (None, 0.0, 1, "Hold to Friday", False)
    for side, g in grid.groupby("side"):
        ok = g[g["disc_weeks"] >= 20].dropna(subset=["disc_sharpe"])
        if ok.empty:
            continue
        b = ok.sort_values("disc_sharpe", ascending=False).iloc[0]          # chosen on DISCOVERY only
        dflt = g[(g["min_move"] == 0) & (g["hold_weeks"] == 1) & (g["exit"] == "Hold to Friday") & ~g["only_while_working"]
                 & ~g["skip_wild"]]
        key = (side, b["min_move"], b["hold_weeks"], b["exit"], b["only_while_working"], b["skip_wild"])
        r = series[key]
        years = r.groupby(r.index.year).apply(lambda x: ((1 + x / 100).prod() - 1) * 100)
        tr = trust(r)
        grp = {}
        pos0 = backtest.side_positions(side, cls, f, R, mc, {"recession": recession}).reindex(
            index=W.index, columns=W.columns).fillna(0).loc[fridays]
        for gname, members in groups.items():
            cols = [c for c in members if c in pos0.columns]
            if not cols:
                continue
            p0 = pos0[cols].where(calm[cols], 0.0) if b["skip_wild"] else pos0[cols]
            p = _hold(backtest.min_move_filter(p0, med[cols], b["min_move"]), fridays, int(b["hold_weeks"]))
            rg, _ = backtest.side_returns(p, Fi[cols], cls, vol[cols], True, True)
            st = _stats(rg)
            grp[gname] = st["avg_week"] if st else np.nan
        best_rows.append(dict(
            side=side, settings=_describe(b), min_move=b["min_move"], hold_weeks=int(b["hold_weeks"]), exit=b["exit"],
            only_while_working=bool(b["only_while_working"]), skip_wild=bool(b["skip_wild"]),
            disc_avg=b["disc_avg"], disc_sharpe=b["disc_sharpe"], unseen_avg=b["unseen_avg"],
            unseen_sharpe=b["unseen_sharpe"], unseen_total=b["unseen_total"], unseen_dd=b["unseen_dd"],
            unseen_weeks=b["unseen_weeks"], default_unseen_avg=dflt["unseen_avg"].iloc[0] if len(dflt) else np.nan,
            years_up=int((years > 0).sum()), years=int(len(years)),
            verdict=_verdict(b), **{f"group_{k}": v for k, v in grp.items()},
            **{f"trust_{k}": v for k, v in tr.items()}))
        series[("BEST", side)] = r
        series[("YEARS", side)] = years
    best = pd.DataFrame(best_rows)
    effects = option_effects(grid)
    port = portfolio(best, series, unseen_from) if not best.empty else None
    if progress:
        progress(1.0, "Done")
    return dict(grid=grid, best=best, series=series, fixes=fixes, portfolio=port, fridays=fridays, unseen_from=unseen_from,
                effects=effects,
                bench=bench, clean=clean, raw=prices)


def _describe(b):
    parts = [b["exit"], f"hold {int(b['hold_weeks'])} week" + ("s" if b["hold_weeks"] > 1 else "")]
    if b["min_move"]:
        parts.append(f"min move {b['min_move']}%")
    if b.get("skip_wild"):
        parts.append("skip wild commodities")
    if b["only_while_working"]:
        parts.append("only while working")
    return " · ".join(parts)


def _verdict(b):
    d, u = b["disc_avg"], b["unseen_avg"]
    if pd.isna(u) or b["unseen_weeks"] < 10:
        return "Not enough unseen weeks"
    if d > 0 and u > 0:
        return "✅ Profitable in discovery AND unseen" + (" (strong)" if (b["unseen_sharpe"] or 0) > 0.8 else "")
    if d > 0 >= u:
        return "❌ Best settings didn't survive the unseen years"
    return "❌ Not profitable"


def portfolio(best, series, unseen_from):
    """Combines the strategies whose best version made money in discovery, more money to the calmer ones."""
    picks = best[best["disc_avg"] > 0]
    if picks.empty:
        return None
    rets = pd.DataFrame({s: series[("BEST", s)] for s in picks["side"]}).fillna(0)
    disc = rets[rets.index < unseen_from]
    vol = disc.where(disc != 0).std().replace(0, np.nan)          # how wild each one is in the weeks it trades
    w = (1 / vol).fillna(0)
    w = w / w.sum() if w.sum() > 0 else w
    combo = (rets * w).sum(axis=1)
    equal = rets.mean(axis=1)
    return dict(weights=w, combo=combo, equal=equal, corr=rets.corr(),
                disc=_stats(combo[combo.index < unseen_from]), unseen=_stats(combo[combo.index >= unseen_from]),
                trust=trust(combo))


def option_effects(grid):
    """
    The ROBUST way to judge an option: its average effect across every other setting and strategy, rather than
    the single best combination (which, the more combinations you try, is ever more likely to be luck).
    An option is trustworthy if it helps on average in discovery AND unseen.
    """
    rows = []
    for col, label in (("exit", "Exit rule"), ("hold_weeks", "Holding period (weeks)"), ("min_move", "Minimum move %"),
                       ("only_while_working", "Only while working"), ("skip_wild", "Skip wild commodities")):
        if col not in grid:
            continue
        base_d, base_u = grid["disc_avg"].mean(), grid["unseen_avg"].mean()
        for val, g in grid.groupby(col):
            d, u = g["disc_avg"].mean() - base_d, g["unseen_avg"].mean() - base_u
            rows.append(dict(option=label, choice=str(val), disc_effect=d, unseen_effect=u, settings=len(g),
                             verdict="✅ helps in both" if d > 0 and u > 0 else "❌ hurts in both" if d < 0 and u < 0 else "mixed"))
    return pd.DataFrame(rows)


# ================================================================= v27: THE COMMODITIES MODEL (only what worked)

MODEL_SIDES = ["Momentum 12-1", "Trust-weighted momentum", "52-week high", "Averages agree + momentum"]
# v37 (30 Oct 2026): Monte Carlo: trend continues and Quiet climbers parked after testing each strategy alone and the
# model without each. Without both: 2017-26 +19.7%/yr (was +15.5), 2001-16 +7.4% (was +5.8), new commodities +13.1%
# (was +11.4). Quiet climbers was spotted on the built-on years (+2.7%/yr alone) and Monte Carlo there too (+1 point
# without it); both fresh tests then agreed.
PARKED_SIDES = {  # strategy: why it was parked (from every commodity test up to Oct 2026)
    "Box breakers": "Lost money on the unseen years with every setting, in every test.",
    "Monte Carlo: bounce back": "Lost money on the unseen years with every setting, in every test.",
    "One-week reversal": "Lost money on the unseen years with every setting except one tiny result (+1.5%/yr).",
    "Short last week's winners": "Lost money in every period with every setting (up to -36%/yr).",
    "Trend following": "Lost money on the unseen years with every setting, in every test.",
    "Turn of month": "Almost never trades, and never made money on the practice years with fixed settings.",
    "Monte Carlo: trend continues": "v37: dragged the model down. Alone it made +1.0%/yr on 2001-16 (fresh). More simulations "
                                    "(2,000) and a 4-week horizon didn't fix it. Model without it: better on 2 of 3 tests.",
    "Quiet climbers": "v37: dragged the model down. Alone it made +2.7%/yr on 2017-26. Model without it: better on all 3 tests.",
}
MODEL_START = "2017-01-06"      # fixed, so the 4-week cycle always lines up the same way
UNSEEN_FROM = "2023-01-06"      # everything before this = practice years
LIVE_FROM = "2026-10-23"        # the model was fixed on this Friday: every week after it is a truly fresh test
MODEL_HOLD, MODEL_STOP = 4, -8.0
MODEL_RULES = [
    ("Use 4 strategies, equal money in each",
     "Momentum 12-1, Trust-weighted momentum, 52-week high, Averages agree + momentum. Each was tested alone and the "
     "model was tested without each one (v37): these four all earn their place. Monte Carlo and Quiet climbers were parked."),
    ("Each strategy buys the top 20% of commodities by its own score",
     "Only buys, never shorts: shorting commodities lost money in our tests and costs more overnight."),
    ("Hold for 4 weeks, then pick again",
     "Holding 2-4 weeks helped in BOTH the practice and the unseen years. Re-picking every week did worse."),
    ("Sell early if a holding is down 8% at a Friday close",
     "The -8% stop helped in both periods and cut the worst drop. Checked once a week (a daily stop hurt)."),
    ("Skip commodities that are unusually wild",
     "If a commodity's recent swings are over 1.5x its normal, it's skipped that round. A small but steady help."),
    ("Pause after 3 losing weeks in a row (Improved)",
     "Sell everything and sit in cash; restart after the model's first winning week (it's followed on paper "
     "meanwhile). Better than always trading on 2017-26 and the new commodities, slightly worse on 2001-16."),
    ("Real costs included",
     "Spread when buying and selling, plus Trading 212's overnight fee on buys (default 0.10% a week)."),
]
CUT = [  # what we tested and threw out, so nothing is missed
    ("Take-profit / stop-loss exits", "Hurt in both periods (sold winners too early)."),
    ("'Only while it's working' switch", "Mixed: helped one period, hurt the other."),
    ("Minimum expected move filter", "Mixed: no reliable help."),
    ("Picking each strategy's 'best settings'", "Fooled by luck: the best picks fell to about 0% on unseen years."),
    ("Pattern-lab adjustments (VIX, S&P, herding, season...)", "Real patterns, but adjusting the model with them didn't beat leaving it alone."),
    ("Moon phase", "Noise: no more patterns than luck would give."),
    ("Weather", "Now tested commodity by commodity in the personality section (where it's grown or used)."),
    ("Daily stop-loss", "Hurt: it sold on normal daily wobbles that recovered."),
    ("News sentiment", "Earlier tests: no edge on commodities."),
    ("The 6 parked strategies", "See the PARKED list: they lost on the unseen years whatever the settings."),
    ("Company shares and accounts (v37 test)", "The industry's share prices and SEC accounts (revenue, profit, stock levels, "
     "industry breadth) for producers, refiners, miners and buyers. Accounts had no link to the next 4 weeks; adding "
     "share-price signals as a 5th strategy made the model worse (2017-26 +15.5 to +18.5%/yr vs +19.7)."),
]


def _compound(r):
    r = r.dropna()
    return ((1 + r / 100).prod() - 1) * 100 if len(r) else np.nan


def _per_year(r):
    r = r.dropna()
    return ((1 + r / 100).prod() ** (52 / len(r)) - 1) * 100 if len(r) >= 4 else np.nan


def _worst_drop(r):
    c = (1 + r.fillna(0) / 100).cumprod()
    return float(((c / c.cummax()) - 1).min() * 100) if len(c) else np.nan


def pause_state(weekly, n=3):
    """
    Pause rule (chosen by Hamish, 27 Oct 2026): after n losing weeks in a row the model stops trading (money in cash).
    It keeps being followed on paper, and restarts after its first winning week. Returns which weeks were traded and
    where things stand now (for the next week).
    """
    on, streak, paused, since = [], 0, False, None
    for d, x in zip(weekly.index, weekly.shift(1).fillna(0)):
        if n:
            if paused and x > 0:
                paused, streak, since = False, 0, None
            elif not paused:
                streak = streak + 1 if x < 0 else 0
                if streak >= n:
                    paused, since = True, d
        on.append(not paused)
    # the decision for the coming week uses every finished week, including the latest
    last = weekly.iloc[-1] if len(weekly) else 0.0
    now_paused, now_streak = paused, streak
    if n and len(weekly):
        if paused and last > 0:
            now_paused, now_streak = False, 0
        elif not paused:
            now_streak = streak + 1 if last < 0 else 0
            now_paused = now_streak >= n
    recent = [float(v) for v in weekly.tail(max(n, 3)).values]
    return dict(on=pd.Series(on, index=weekly.index), paused=bool(now_paused), streak=int(now_streak), n=n,
                since=since, recent=recent, last_week=weekly.index[-1] if len(weekly) else None)


def _reassess_losers(ret, w, W, Fi, fridays, med, ret12m, fin_long, min_move=0.2):
    """
    Hamish's idea (tested 27 Oct 2026): at the end of each round, a holding the model is about to sell that LOST money
    in the round is reassessed. If the model still expects it to rise (expected move >= min_move next week and its
    12-month trend is up) it is held for ONE more week, with that money joining the new picks a week later.
    """
    out = ret.copy()
    for i in range(MODEL_HOLD, len(fridays), MODEL_HOLD):
        t2, b0 = fridays[i], fridays[i - MODEL_HOLD]
        wp, wn = w.iloc[i - 1], w.iloc[i]
        keep = [a for a in w.columns if wp[a] > 0 and wn[a] == 0
                and W.at[t2, a] / W.at[b0, a] - 1 < 0
                and (med.at[t2, a] if t2 in med.index else np.nan) >= min_move
                and (ret12m.at[t2, a] if t2 in ret12m.index else np.nan) > 0]
        if not keep:
            continue
        e = float(sum(wp[a] for a in keep))
        extra = float(sum(wp[a] * (Fi.at[t2, a] if Fi.at[t2, a] == Fi.at[t2, a] else 0.0) for a in keep))
        out.iloc[i] = (1 - e) * ret.iloc[i] + extra - e * fin_long
    return out


def period_of(d):
    d = pd.Timestamp(d)
    return "Practice" if d < pd.Timestamp(UNSEEN_FROM) else "Unseen" if d < pd.Timestamp(LIVE_FROM) else "Live"


FILTER_CUT = 0.30          # the personality filter skips picks scoring in the worst 30% (cut-off set on 2022-23)


def final_model(prices, ohlc=None, proxies=None, fin_long=LONG_FINANCING_WEEK, n_sims=500, progress=None, budget=1000.0,
                ctx=None, weather=None, use_personality=True, start=None, end=None, fresh_label=None,
                trend_rule=False, min_move=0.0, cls="Commodities", reassess=False, pause_after=0):
    """
    The commodities model: only the strategies and options that held up in every test, with nothing to choose.
    Returns weekly returns (combined, each strategy, buying everything), year-by-year and period tables, which
    commodities made the money, and what the model holds right now.
    """
    if end is not None:          # a fresh test on old years: the model never sees anything after `end`
        end = pd.Timestamp(end)
        prices = prices[prices.index <= end]
        ohlc = {k: v[v.index <= end] for k, v in ohlc.items()} if ohlc else ohlc
        proxies = proxies[proxies.index <= end] if proxies is not None else None
    prices = prices.dropna(axis=1, how="all")
    labels = (fresh_label,) if fresh_label else ("Practice", "Unseen", "Live")
    per_of = (lambda d: fresh_label) if fresh_label else period_of
    if fresh_label or cls != "Commodities":
        use_personality = False
    if cls == "Commodities":
        clean, cohlc, fixes = clean_rolls(prices, ohlc, proxies)
    else:
        clean, cohlc, fixes = prices, ohlc, []
    W, R, F = backtest.weekly_frames(clean)
    fridays = W.index[W.index >= pd.Timestamp(start or MODEL_START)]
    if len(fridays) < 60:
        return None
    f = backtest.features(clean, W)
    mc_parts = {}
    for i, col in enumerate(clean.columns):
        if progress:
            progress(0.8 * i / len(clean.columns), f"Monte Carlo through history: {col}")
        m = backtest.mc_at_dates(clean[col], fridays, 5, n_sims=n_sims, seed=i)
        if not m.empty:
            mc_parts[col] = m
    if not mc_parts:
        return None
    mc = {k: pd.DataFrame({c: m[k] for c, m in mc_parts.items() if k in m}).reindex(index=W.index, columns=W.columns)
          for k in next(iter(mc_parts.values())).columns}
    Fi, vol = F.loc[fridays], f["vol60"].loc[fridays]
    volz = (f["vol60"] / f["vol60"].rolling(104, min_periods=26).median()).loc[fridays]
    calm = ~(volz > 1.5)
    round_day = fridays[((len(fridays) - 1) // MODEL_HOLD) * MODEL_HOLD]      # the Friday this 4-week round was picked
    wanted = {}                                                                # what each strategy wanted that day (before filters)
    def run_sides(exclude=(), allow=None, keep_fees=False):
        rets, contrib, holds = {}, {}, {}
        for si, side in enumerate(MODEL_SIDES):
            if progress and not exclude and allow is None:
                progress(0.80 + 0.05 * si / len(MODEL_SIDES), f"Running: {side}")
            keep_cols = [c for c in W.columns if c not in exclude]      # exclude = pretend these never existed
            f2 = {k: v[keep_cols] for k, v in f.items()} if exclude else f
            mc2 = {k: v[keep_cols] for k, v in mc.items()} if exclude else mc
            pos0 = backtest.side_positions(side, cls, f2, R[keep_cols], mc2, {}).reindex(
                index=W.index, columns=W.columns).fillna(0).loc[fridays]
            if trend_rule:                   # only buy a commodity whose own 12-month trend is up
                pos0 = pos0.where(f["ret12m"].reindex(index=pos0.index, columns=pos0.columns) > 0, 0.0)
            if min_move:                     # only buy if the Monte Carlo expects at least this move next week
                pos0 = backtest.min_move_filter(pos0, mc["median_trend"].reindex(index=pos0.index, columns=pos0.columns),
                                                min_move)
            if allow is not None:            # the personality filter: skip picks whose own patterns look bad
                pos0 = pos0.where(allow.reindex(index=pos0.index, columns=pos0.columns).fillna(True), 0.0)
            if keep_fees and round_day in pos0.index:
                wanted[side] = pos0.loc[round_day]
            pos = _block_stop(_hold(pos0.where(calm, 0.0), fridays, MODEL_HOLD), Fi, MODEL_HOLD, MODEL_STOP)
            ret, w = backtest.side_returns(pos, Fi, cls, vol, True, True)
            fee = (w.clip(lower=0).sum(axis=1) * fin_long).where(ret != 0, 0.0)
            ret = ret - fee
            if reassess:
                ret = _reassess_losers(ret, w, W, Fi, fridays, mc["median_trend"], f["ret12m"], fin_long, max(min_move, 0.2))
            rets[side] = ret
            if keep_fees:
                fees[side] = fee
                wts[side] = w
            contrib[side] = w * Fi.fillna(0)                 # each commodity's part of the week (before costs)
            holds[side] = w.iloc[-1]
        S = pd.DataFrame(rets).fillna(0)
        S = S.iloc[:-1] if Fi.iloc[-1].isna().all() else S          # the latest week hasn't happened yet
        return S, contrib, holds

    fees, wts = {}, {}
    S, contrib, holds = run_sides(keep_fees=True)
    # ---- data for the stats check: every 4th Friday (rounds don't overlap), each commodity's signals at that
    # Friday and what it did over the NEXT 4 weeks, plus whether the model bought it
    fwd4 = (W.shift(-MODEL_HOLD) / W - 1) * 100
    held = sum((w_.reindex(index=fridays, columns=W.columns).fillna(0) > 0).astype(int) for w_ in wts.values())
    sig_rows = []
    for d in fridays[::MODEL_HOLD]:
        for c in W.columns:
            y = fwd4.at[d, c] if d in fwd4.index else np.nan
            if y != y:
                continue
            sig_rows.append({"date": d, "commodity": c, "next 4 weeks %": y, "picked": bool(held.at[d, c] > 0),
                             "12-1 momentum": f["mom"].at[d, c], "Closeness to 52-week high": f["high52"].at[d, c],
                             "12-month trend": f["ret12m"].at[d, c],
                             "Monte Carlo expected move": mc["median_trend"].at[d, c] if d in mc["median_trend"].index else np.nan,
                             "Volatility vs normal": volz.at[d, c]})
    signal_points = pd.DataFrame(sig_rows)
    combined = S.mean(axis=1)
    shadow = combined.copy()                      # the model as if it always traded (watched while paused)
    pause = pause_state(shadow, pause_after)
    if pause_after:
        combined = combined.where(pause["on"], 0.0)
    before_fees = combined + pd.DataFrame(fees).reindex(S.index).fillna(0).mean(axis=1).where(pause["on"], 0.0)
    bench = Fi.loc[S.index].mean(axis=1).fillna(0)
    bench_cfd = bench - fin_long                     # buying everything on the same CFD account pays the same fee
    by_cmdty = (sum(contrib.values()) / len(contrib)).loc[S.index]

    # ---- year by year
    rows, grow, grow_b = [], budget, budget
    for y, g in combined.groupby(combined.index.year):
        b = bench[g.index]
        grow *= 1 + _compound(g) / 100
        grow_b *= 1 + _compound(b) / 100
        per = sorted({per_of(d) for d in g.index}, key=list(labels).index)
        row = {"Year": str(y) + (" (so far)" if y == pd.Timestamp.now().year else ""), "Period": " + ".join(per),
               "Model %": _compound(g), "Buy everything %": _compound(b),
               "Model minus buy everything": _compound(g) - _compound(b),
               "Worst drop in the year %": _worst_drop(g), "Winning weeks %": float((g[g != 0] > 0).mean() * 100),
               "£ grows to": grow, "Buy everything £ grows to": grow_b}
        for s in MODEL_SIDES:
            row[s] = _compound(S[s][g.index])
        rows.append(row)
    years = pd.DataFrame(rows)

    # ---- the three periods
    prow = []
    for name in labels + (() if fresh_label else ("Whole history",)):
        idx = combined.index if name == "Whole history" else combined.index[[per_of(d) == name for d in combined.index]]
        if len(idx) == 0:
            continue
        g, b = combined[idx], bench[idx]
        yrs = [r["Model %"] for _, r in years.iterrows()
               if name == "Whole history" or r["Period"] == name]
        prow.append({"Period": name, "From": idx[0], "To": idx[-1] + pd.Timedelta(days=7), "Weeks": len(idx),
                     "Model % a year": _per_year(g), "Model total %": _compound(g),
                     "£ grows to": budget * (1 + _compound(g) / 100),
                     "Worst drop %": _worst_drop(g), "Model before overnight fees % a year": _per_year(before_fees[idx]),
                     "Buy everything on CFDs % a year": _per_year(bench_cfd[idx]),
                     "Buy everything on CFDs worst drop %": _worst_drop(bench_cfd[idx]),
                     "Buy everything % a year": _per_year(b),
                     "Buy everything total %": _compound(b), "Buy everything worst drop %": _worst_drop(b),
                     "Full years up": f"{sum(1 for v in yrs if v > 0)} of {len(yrs)}" if yrs else ""})
    periods = pd.DataFrame(prow)

    # ---- strategies per period
    srows = []
    for s in MODEL_SIDES:
        r = {"Strategy": s}
        for name in labels:
            idx = [d for d in S.index if per_of(d) == name]
            r[f"{name} % a year"] = _per_year(S[s][idx]) if len(idx) >= 4 else (_compound(S[s][idx]) if idx else np.nan)
        r["Worst drop %"] = _worst_drop(S[s])
        srows.append(r)
    strategies = pd.DataFrame(srows)

    # ---- which commodities made the money (sum of weekly parts, before costs)
    yc = by_cmdty.groupby(by_cmdty.index.year).sum().T
    yc.columns = [str(c) for c in yc.columns]
    yc["All years"] = yc.sum(axis=1)
    yc = yc[yc.abs().sum(axis=1) > 0].sort_values("All years", ascending=False)

    # ---- luck check: would it still work without its single best commodity?
    without = None
    if len(yc) > 3:
        top = yc.index[0]
        S2, _, _ = run_sides((top,))
        c2 = S2.mean(axis=1)
        wrow = []
        for name in (labels if fresh_label else ("Practice", "Unseen")):
            idx = [d for d in c2.index if per_of(d) == name]
            if idx:
                wrow.append({"Period": name, "With everything % a year": _per_year(combined[idx]),
                             f"Without {top} % a year": _per_year(c2[idx]),
                             "Buy everything % a year": _per_year(bench[idx])})
        without = dict(ticker=top, table=pd.DataFrame(wrow), weekly=c2)

    # ---- the personality filter (each commodity's own patterns)
    filt = None
    if use_personality:
        try:
            import pattern_lab
            prep = dict(clean=clean, cohlc=cohlc, fixes=fixes, W=W, R=R, F=F, fr=fridays, f=f, mc=mc)
            pers = pattern_lab.personality(prep, ctx, weather, progress=progress)
        except Exception as exc:          # never let the extra test break the model
            pers, filt = None, dict(error=f"{type(exc).__name__}: {exc}")
        if pers is not None and not pers["scores"].empty:
            sc = pers["scores"].reindex(index=fridays, columns=W.columns).fillna(0.0)
            blocks = fridays[::MODEL_HOLD]
            conf = blocks[(blocks >= pers["find_end"]) & (blocks < pers["confirm_end"])]
            picked = []
            for side in MODEL_SIDES:
                p0 = backtest.side_positions(side, cls, f, R, mc, {}).reindex(index=W.index, columns=W.columns
                                                                               ).fillna(0).loc[fridays].where(calm, 0.0)
                vals = sc.loc[conf].values[p0.loc[conf].values > 0]
                picked.extend(vals.tolist())
            cut = float(np.percentile(picked, FILTER_CUT * 100)) if picked else -np.inf
            allow = sc > cut
            S_f, _, holds_f = run_sides(allow=allow)
            comb_f = S_f.mean(axis=1)
            frows = []
            for y, g in combined.groupby(combined.index.year):
                gf = comb_f.reindex(g.index).fillna(0)
                frows.append({"Year": str(y) + (" (so far)" if y == pd.Timestamp.now().year else ""),
                              "Kind": "honest test" if pd.Timestamp(f"{y}-01-01") >= pers["confirm_end"]
                              else ("used to set the cut-off" if pd.Timestamp(f"{y}-01-01") >= pers["find_end"]
                                    else "used to find the patterns"),
                              "Without filter %": _compound(g), "With filter %": _compound(gf),
                              "Difference": _compound(gf) - _compound(g)})
            hon = combined.index >= pers["confirm_end"]
            Hf = pd.DataFrame(holds_f).fillna(0) / len(MODEL_SIDES)
            nf = Hf.sum(axis=1)
            nf = nf[nf > 1e-9].sort_values(ascending=False)
            filt = dict(weekly=comb_f, years=pd.DataFrame(frows), cut=cut, personality=pers,
                        honest=dict(without=_per_year(combined[hon]), with_=_per_year(comb_f.reindex(combined.index)[hon].fillna(0)),
                                    dd_without=_worst_drop(combined[hon]), dd_with=_worst_drop(comb_f.reindex(combined.index)[hon].fillna(0)),
                                    since=pers["confirm_end"]),
                        now_allow=allow.iloc[-1], now_scores=sc.iloc[-1],
                        holding=pd.DataFrame({"Ticker": nf.index, "Share of the money %": nf.values * 100,
                                              "£": nf.values * budget}))

    # ---- what it holds now (after the latest Friday close)
    last = fridays[-1]
    i_last = len(fridays) - 1
    picked_on = fridays[(i_last // MODEL_HOLD) * MODEL_HOLD]
    next_change = picked_on + pd.Timedelta(weeks=MODEL_HOLD)
    H = pd.DataFrame(holds).fillna(0) / len(MODEL_SIDES)       # share of the whole model
    now = H.sum(axis=1)
    now = now[now > 1e-9].sort_values(ascending=False)
    holding = pd.DataFrame({"Ticker": now.index, "Share of the money %": (now.values * 100),
                            "£": now.values * budget,
                            "Held by": [", ".join(s for s in MODEL_SIDES if H.at[t, s] > 1e-9) for t in now.index]})
    # prices for the trade ticket: the latest close (not roll-adjusted, so it matches the quoted price) and
    # how much the commodity normally moves in 4 weeks
    last_px = {t: prices[t].dropna() for t in holding["Ticker"]}
    holding["Price"] = [float(v.iloc[-1]) if len(v) else np.nan for v in last_px.values()]
    holding["Price date"] = [v.index[-1] if len(v) else pd.NaT for v in last_px.values()]
    v60 = f["vol60"].iloc[-1]
    holding["Normal 4-week move %"] = [float(v60.get(t, np.nan)) * np.sqrt(MODEL_HOLD / 52) for t in holding["Ticker"]]
    now_signals = pd.DataFrame({"expected": mc["median_trend"].reindex(index=W.index).loc[fridays].iloc[-1],
                                "trend_up": f["ret12m"].loc[fridays].iloc[-1] > 0})
    # ---- how this round was decided: every commodity's readings on the pick day, what each strategy wanted, what passed
    rd, rows_ = round_day, []
    held_now = pd.DataFrame(holds).fillna(0)
    for c in W.columns:
        get = lambda fr: fr.at[rd, c] if (rd in fr.index and c in fr.columns) else np.nan
        want = [s for s in MODEL_SIDES if s in wanted and float(wanted[s].get(c, 0) or 0) > 0]
        hold = [s for s in MODEL_SIDES if c in held_now.index and s in held_now.columns and held_now.at[c, s] > 1e-9]
        rows_.append({"Ticker": c, "12-1 momentum %": get(f["mom"]), "Distance from 52-week high %": get(f["high52"]),
                      "12-month trend %": get(f["ret12m"]), "Monte Carlo expected move %": get(mc["median_trend"]),
                      "Volatility vs normal": get(volz), "Calm enough": bool(get(calm)) if get(calm) == get(calm) else False,
                      "Wanted by": ", ".join(want), "Bought by": ", ".join(hold)})
    decision = pd.DataFrame(rows_)
    return dict(weekly=combined, strategies_weekly=S, bench=bench, bench_cfd=bench_cfd, before_fees=before_fees, years=years,
                now_signals=now_signals, reassess=reassess, min_move=min_move, pause=pause, shadow=shadow,
                switch=switch_state(combined), periods=periods, strategies=strategies,
                by_commodity=yc, holding=holding, last_friday=last, picked_on=picked_on, next_change=next_change,
                fixes=fixes, budget=budget, fin_long=fin_long, without=without, filter=filt,
                signal_points=signal_points, shadow_pause=pause, decision=decision, round_day=round_day)


def year_sentence(r, budget=1000.0):
    """One plain-English line for a year of the model."""
    m, b = r["Model %"], r["Buy everything %"]
    sides = {s: r[s] for s in MODEL_SIDES if s in r and pd.notna(r[s])}
    best = max(sides, key=sides.get) if sides else None
    worst = min(sides, key=sides.get) if sides else None
    verdict = ("beat" if m > b else "trailed") + f" buying everything ({b:+.1f}%)"
    tag = {"Practice": "practice year", "Unseen": "unseen year", "Live": "LIVE"}.get(
        r["Period"], "never-seen year" if str(r["Period"]).startswith("Fresh") else r["Period"].lower())
    out = f"**{r['Year']}** ({tag}): **{m:+.1f}%**, {verdict}. Worst drop {r['Worst drop in the year %']:.1f}%."
    if best:
        out += f" Best: {best} ({sides[best]:+.1f}%); worst: {worst} ({sides[worst]:+.1f}%)."
    return out



# ================================================================= v30: FRESH TESTS on data the model has never seen

FRESH_OLD = dict(start="2001-01-05", end="2016-12-30", label="Fresh: 2001-2016")
NEW_COMMODITIES = {"PA=F": "Palladium", "ZO=F": "Oats", "OJ=F": "Orange juice", "HE=F": "Lean hogs",
                   "GF=F": "Feeder cattle", "ZL=F": "Soybean oil", "ZM=F": "Soybean meal", "KE=F": "Kansas wheat",
                   "ZR=F": "Rough rice"}
FRESH_NEW = dict(start=MODEL_START, label="Fresh: new commodities")


VERSIONS = {
    "Improved": dict(trend_rule=True, min_move=0.2, reassess=True, pause_after=3),
    "Original": dict(trend_rule=False, min_move=0.0),
}
VERSION_HELP = {
    "Improved": "Only buys a commodity whose own 12-month trend is up, and only if the Monte Carlo expects it to "
                "rise at least 0.2% next week. At the end of a round, a losing holding the model still expects to "
                "rise is kept one more week (your reassessment idea). After 3 losing weeks in a row it pauses (sells "
                "and sits in cash) until it has a winning week again.",
    "Original": "The model exactly as first built (v27): no trend rule, no minimum move, no reassessment, no pause.",
}
MIN_MOVE_TEST = [  # % a year after fees (worst drop), from the 27 Oct 2026 test on Hamish's data
    ("0% (original)", "+12.8% (−31%)", "+4.2% (−57%)", "+7.3% (−31%)", "85%"),
    ("0.2%", "+14.3% (−32%)", "+5.9% (−49%)", "+9.2% (−26%)", "77%"),
    ("0.5%", "+11.5% (−27%)", "+7.3% (−52%)", "+6.0% (−28%)", "60%"),
    ("0.8%", "+11.4% (−35%)", "−0.1% (−48%)", "+4.5% (−34%)", "38%"),
    ("1.0%", "+10.7% (−33%)", "+1.5% (−48%)", "+0.8% (−33%)", "28%"),
    ("1.5%", "+4.8% (−13%)", "−4.3% (−57%)", "−1.5% (−34%)", "8%"),
    ("0.2% + trend rule", "+14.5% (−30%)", "+6.4% (−49%)", "+8.9% (−25%)", "75%"),
    ("0.2% + trend rule + reassess losers", "+14.9% (−33%)", "+6.5% (−49%)", "+10.3% (−23%)", "75%"),
    ("... + pause after 3 losing weeks (v34-v36)", "+15.5% (−30%)", "+5.8% (−50%)", "+11.4% (−24%)", "about 70%"),
    ("... + Monte Carlo and Quiet climbers parked (Improved, v37)", "+19.7% (−30%)", "+7.4% (−52%)", "+13.1% (−20%)", "about 70%"),
]


def fresh_summary(res):
    """Plain numbers for a fresh test: per year, total, worst drop, years up and years beating buy-everything."""
    if not res:
        return None
    w, b = res["weekly"], res["bench"]
    Y = res["years"]
    full = Y[~Y["Year"].str.contains("so far")]
    bc = res.get("bench_cfd", b - LONG_FINANCING_WEEK)
    bf = res.get("before_fees", w)
    return dict(model_year=_per_year(w), bench_year=_per_year(b), model_total=_compound(w), bench_total=_compound(b),
                cfd_year=_per_year(bc), cfd_dd=_worst_drop(bc), before_fees_year=_per_year(bf),
                model_dd=_worst_drop(w), bench_dd=_worst_drop(b), years=len(full),
                years_up=int((full["Model %"] > 0).sum()), years_beat=int((full["Model minus buy everything"] > 0).sum()),
                median_year=float(full["Model %"].median()) if len(full) else np.nan,
                start=w.index[0], end=w.index[-1] + pd.Timedelta(days=7))



# ================================================================= v32: the model together with the S&P 500

MIX_SHARES = (1.0, 0.5, 0.3, 0.0)        # share of money in the model; the rest in an S&P 500 fund


def spx_weekly(spx_prices, index):
    """Next-week S&P 500 return (total return if the prices are dividend-adjusted, e.g. SPY), lined up with the model."""
    s = spx_prices.dropna()
    Wk = s.resample("W-FRI").last()
    Wk = Wk[Wk.index <= s.index.max()]
    return ((Wk.pct_change(fill_method=None) * 100).shift(-1)).reindex(index).fillna(0.0)


SWITCH_WEEKS = 26     # the 6-month switch (chosen 27 Oct 2026)


def switch_state(model_weekly, n=SWITCH_WEEKS):
    """
    The 6-month switch: if the model has LOST money over its last n weeks (on paper), its money goes into the S&P
    500 too; when its last n weeks turn positive again, back to the normal split. Returns which weeks were
    switched, and the state for the coming week (using every finished week).
    """
    g = (1 + model_weekly / 100).rolling(n, min_periods=n).apply(np.prod, raw=True) - 1
    switched = (g.shift(1) < 0).fillna(False)
    last6 = float(g.iloc[-1] * 100) if len(g) and g.iloc[-1] == g.iloc[-1] else np.nan
    return dict(switched=switched, now=bool(last6 < 0) if last6 == last6 else False, last6=last6, n=n)


def mix_table(model_weekly, spx_week):
    rows, years = [], {}
    sw = switch_state(model_weekly)["switched"].reindex(model_weekly.index).fillna(False)
    mixes = [(sh, sh * model_weekly + (1 - sh) * spx_week) for sh in MIX_SHARES]
    mixes.insert(2, ("switch", pd.Series(np.where(sw, spx_week, 0.5 * model_weekly + 0.5 * spx_week),
                                         index=model_weekly.index)))
    for sh, z in mixes:
        name = ("50/50 + 6-month switch" if sh == "switch" else "Model only" if sh == 1 else
                "S&P 500 only" if sh == 0 else f"{int(sh * 100)}% model + {int(round((1 - sh) * 100))}% S&P 500")
        sd = z.std()
        rows.append({"Mix": name, "% a year": _per_year(z), "Worst drop %": _worst_drop(z),
                     "Return per unit of risk": float(z.mean() / sd * np.sqrt(52)) if sd > 0 else np.nan,
                     "Losing years": int((z.groupby(z.index.year).apply(_compound) < 0).sum())})
        years[name] = z.groupby(z.index.year).apply(_compound)
    return pd.DataFrame(rows), pd.DataFrame(years)


# ================================================================= v32: recording the futures curve (for a future carry test)

CURVE = {  # ticker: (Yahoo contract root, exchange suffix, months the contract trades)
    "CL=F": ("CL", "NYM", "FGHJKMNQUVXZ"), "HO=F": ("HO", "NYM", "FGHJKMNQUVXZ"), "RB=F": ("RB", "NYM", "FGHJKMNQUVXZ"),
    "NG=F": ("NG", "NYM", "FGHJKMNQUVXZ"), "BZ=F": ("BZ", "NYM", "FGHJKMNQUVXZ"), "GC=F": ("GC", "CMX", "GJMQVZ"),
    "SI=F": ("SI", "CMX", "HKNUZ"), "HG=F": ("HG", "CMX", "HKNUZ"), "PL=F": ("PL", "NYM", "FJNV"),
    "ZC=F": ("ZC", "CBT", "HKNUZ"), "ZS=F": ("ZS", "CBT", "FHKNQUX"), "ZW=F": ("ZW", "CBT", "HKNUZ"),
    "KC=F": ("KC", "NYB", "HKNUZ"), "SB=F": ("SB", "NYB", "HKNV"), "CC=F": ("CC", "NYB", "HKNUZ"),
    "CT=F": ("CT", "NYB", "HKNVZ"), "LE=F": ("LE", "CME", "GJMQVZ"),
}
MONTH_CODES = "FGHJKMNQUVXZ"


def contract_candidates(ticker, today, n=4):
    """The next n listed contracts, e.g. CLZ26.NYM, with how many months ahead each one is."""
    root, ex, months = CURVE[ticker]
    out, d = [], pd.Timestamp(today).replace(day=1)
    for k in range(1, 19):          # this month's contract has usually expired or is about to
        m = d + pd.DateOffset(months=k)
        code = MONTH_CODES[m.month - 1]
        if code in months:
            out.append((f"{root}{code}{m.strftime('%y')}.{ex}", k))
        if len(out) >= n:
            break
    return out


def curve_snapshot(download, today=None):
    """Latest price of the two nearest contracts for each commodity -> carry (positive = backwardation)."""
    today = pd.Timestamp(today or pd.Timestamp.now().normalize())
    cands = {t: contract_candidates(t, today) for t in CURVE}
    tickers = tuple(sorted({c for v in cands.values() for c, _ in v}))
    px = download(tickers)
    last = pd.Series(dtype=float)
    if px is not None and len(px):
        fresh = [c for c in px.columns if px[c].last_valid_index() is not None
                 and px[c].last_valid_index() >= today - pd.Timedelta(days=7)]      # ignore expired, stale contracts
        last = px[fresh].ffill().iloc[-1] if fresh else last
    rows = []
    for t, cs in cands.items():
        got = [(c, k, float(last[c])) for c, k in cs if c in last and last[c] == last[c] and last[c] > 0]
        if len(got) < 2:
            rows.append(dict(date=today, ticker=t, front=None, front_price=np.nan, next=None, next_price=np.nan,
                             months_apart=np.nan, carry_year=np.nan))
            continue
        (c1, k1, p1), (c2, k2, p2) = got[0], got[1]
        gap = max(1, k2 - k1)
        rows.append(dict(date=today, ticker=t, front=c1, front_price=p1, next=c2, next_price=p2, months_apart=gap,
                         carry_year=(p1 / p2 - 1) * 12 / gap * 100))
    return pd.DataFrame(rows)



# ================================================================= v42: explain the model in plain English with the statistics
def _p_from_t(t, n):
    """Two-sided p-value for a t statistic (normal approximation, fine for n > 30; a bit generous for small n)."""
    import math
    if t != t or n < 3:
        return np.nan
    return math.erfc(abs(t) / math.sqrt(2))


def _ttest(a):
    a = pd.Series(a).dropna()
    if len(a) < 3 or a.std() == 0:
        return np.nan, np.nan
    t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
    return float(t), float(_p_from_t(t, len(a)))


def explain(res):
    """The evidence behind the model, from its own history: does each signal predict the next 4 weeks (rank
    correlation each round, then a t-test across rounds), do the picks beat the rest, and is the model's own
    return different from zero and from buying everything. Returns small tables for the page."""
    out = {}
    sp = res.get("signal_points")
    if sp is not None and not sp.empty:
        rows = []
        for sig in ["12-1 momentum", "Closeness to 52-week high", "12-month trend", "Monte Carlo expected move", "Volatility vs normal"]:
            if sig not in sp:
                continue
            ics = sp.groupby("date").apply(lambda g: g[sig].rank().corr(g["next 4 weeks %"].rank()) if g[sig].notna().sum() > 4 else np.nan).dropna()
            t, p = _ttest(ics)
            rows.append({"Signal": sig, "Rounds": len(ics), "Average rank correlation with the next 4 weeks": ics.mean(),
                         "Rounds it pointed the right way %": (ics > 0).mean() * 100 if len(ics) else np.nan, "t": t, "p-value": p})
        out["signals"] = pd.DataFrame(rows)
        pk, rest = sp[sp["picked"]]["next 4 weeks %"], sp[~sp["picked"]]["next 4 weeks %"]
        if len(pk) > 5 and len(rest) > 5:
            diff = pk.mean() - rest.mean()
            se = np.sqrt(pk.var(ddof=1) / len(pk) + rest.var(ddof=1) / len(rest))
            t = diff / se if se else np.nan
            out["picks"] = dict(picked=pk.mean(), rest=rest.mean(), n_picked=len(pk), n_rest=len(rest), diff=diff, t=t,
                                p=_p_from_t(t, len(pk) + len(rest)), hit=(pk > 0).mean() * 100, hit_rest=(rest > 0).mean() * 100)
    w, b = res.get("weekly"), res.get("bench")
    if w is not None and len(w):
        rows = []
        for name in ("Practice", "Unseen", "Live"):
            idx = [d for d in w.index if period_of(d) == name]
            if len(idx) < 8:
                continue
            g, gb = w[idx], b.reindex(idx).fillna(0) if b is not None else None
            t, p = _ttest(g[g != 0])
            t2, p2 = _ttest((g - gb)) if gb is not None else (np.nan, np.nan)
            rows.append({"Period": name, "Weeks": len(idx), "Model % a year": _per_year(g), "Buy everything % a year": _per_year(gb) if gb is not None else np.nan,
                         "Winning weeks %": float((g[g != 0] > 0).mean() * 100) if (g != 0).any() else np.nan,
                         "p-value (model above zero)": p, "p-value (model above buy everything)": p2})
        out["periods"] = pd.DataFrame(rows)
    return out
