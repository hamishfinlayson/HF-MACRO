"""
risk.py - the RISK LAYER (PC version only).

The model says which way. The risk layer asks: should we actually take this trade this week, even
though the signal is good? Each check flags trades that look risky (wild markets, wild assets, events,
weak calls, the same bet twice...). Every check is TESTED like an ingredient: the model's trades with
and without it, on the discovery period and the unseen period. A check only counts if it improves
return per unit of risk (Sharpe) in both, not just if it cuts losses (skipping trades always does that).

Just for fun and learning. Not financial advice.
"""

import numpy as np
import pandas as pd

import backtest

# name: (level, what it flags, why it might help)
CHECKS = {
    "VIX high": ("Market", "The fear index is well above its last 2 years (more than 1 standard deviation).",
                 "Markets move more and more randomly when fear is high, so signals drown in noise."),
    "VIX jumped": ("Market", "The fear index jumped more than 20% last week.",
                   "Sudden fear spikes often keep going for a while: risky week to bet on anything."),
    "Credit stress": ("Market", "Junk-bond spreads widened unusually fast over the last 4 weeks.",
                      "Bond investors usually spot trouble first."),
    "Dollar spike": ("Market", "The dollar moved unusually far (more than 2 standard deviations) last week.",
                     "A dollar shock hits commodities, emerging markets and every USD currency pair at once."),
    "Asset is wild": ("Asset", "This asset's own volatility is in the top 20% of its last 2 years.",
                      "Wild spells mean bigger, more random moves: the same signal is worth less."),
    "Just had a huge move": ("Asset", "Last week it moved more than 3x its normal week.",
                             "Usually a news shock still playing out; the past patterns may not apply."),
    "Event next week": ("Asset", "Earnings (stocks) or Fed/CPI week (FX, indices, crypto) in the week ahead.",
                        "Scheduled surprises are a big share of misses; skipping them avoids noise we can see coming."),
    "Costs eat the move": ("Trade", "The expected move is less than 2x the trading costs.",
                           "If the edge is smaller than costs, even a right call barely pays."),
    "Weak call": ("Trade", "The call is less confident than the week's median call.",
                  "Weak calls are closest to a coin toss."),
    "Models disagree": ("Trade", "The ridge and machine-learning models point opposite ways (Arena only).",
                        "When two different methods disagree, the signal is probably weak."),
    "Fat-tail crash risk": ("Trade", "The Monte Carlo's bad week (5th percentile) against us is more than 2x a normal week.",
                            "Some assets have crash-prone tails; a right call can still be wiped out by one gap."),
    "Same bet twice": ("Portfolio", "A pick moves almost exactly with a stronger pick (correlation above 0.7).",
                       "Two picks that are really one bet double the risk without doubling the edge."),
    "Losing streak brake": ("Portfolio", "After a bad 4 weeks, trade at half size until it recovers.",
                            "Signals sometimes stop working for a while; a brake limits the damage."),
}
TOP3_ONLY = {"Fat-tail crash risk", "Same bet twice"}
EVENT_FLAGS = {"UK stocks": ["earn_next"], "US stocks": ["earn_next"], "FX": ["fomc_next", "cpi_next"],
               "World indices": ["fomc_next", "cpi_next"], "Crypto": ["fomc_next", "cpi_next"], "Commodities": []}


def _zs(s, window=104, min_periods=26):
    return (s - s.rolling(window, min_periods=min_periods).mean()) / s.rolling(window, min_periods=min_periods).std()


def _broadcast(series, idx, cols):
    s = series.reindex(idx).fillna(False).astype(bool)
    return pd.DataFrame(np.repeat(s.values[:, None], len(cols), axis=1), index=idx, columns=cols)


def flags(cls, b, pred, ctx, prices=None, ml_pred=None, top3=None, horizon=1):
    """Every risk check as a True/False table (Friday x asset): True = risky."""
    W, R, vol_w, raw = b["W"], b["R"], b["vol_w"], b["raw"]
    idx, cols = pred.index, pred.columns
    out = {}
    fac = (ctx or {}).get("factors")
    if fac is not None and not fac.empty:
        fw = fac.resample("W-FRI").last().reindex(idx, method="ffill")
        if "vix" in fw:
            out["VIX high"] = _broadcast(_zs(fw["vix"]) > 1, idx, cols)
            out["VIX jumped"] = _broadcast(fw["vix"].pct_change() > 0.20, idx, cols)
        if "credit" in fw:
            out["Credit stress"] = _broadcast(_zs(fw["credit"] - fw["credit"].shift(4)) > 1.5, idx, cols)
        if "dollar" in fw:
            out["Dollar spike"] = _broadcast(_zs(fw["dollar"].pct_change()).abs() > 2, idx, cols)
    q80 = vol_w.rolling(104, min_periods=26).quantile(0.8)
    out["Asset is wild"] = (vol_w > q80).reindex(index=idx, columns=cols).fillna(False)
    out["Just had a huge move"] = (R.abs() > 3 * vol_w.shift(1)).reindex(index=idx, columns=cols).fillna(False)
    ev = [raw[k] for k in EVENT_FLAGS.get(cls, []) if k in raw]
    if ev:
        e = sum((x.reindex(index=idx, columns=cols).fillna(0) > 0).astype(int) for x in ev) > 0
        out["Event next week"] = e
    cost = backtest.COST_ROUND_TRIP.get(cls, 0.1) + (backtest.UK_STAMP_DUTY if cls == "UK stocks" else 0)
    out["Costs eat the move"] = (pred.abs() < 2 * cost) & pred.notna()
    conf = (pred / vol_w.reindex(index=idx, columns=cols)).abs()
    out["Weak call"] = conf.lt(conf.median(axis=1), axis=0) & conf.notna()
    if ml_pred is not None:
        m = ml_pred.reindex(index=idx, columns=cols)
        out["Models disagree"] = (np.sign(m) != np.sign(pred)) & m.notna() & pred.notna()
    if top3 is not None and prices is not None:
        out.update(_top3_flags(cls, top3, prices, R, vol_w))
    return out


def _top3_flags(cls, top3, prices, R, vol_w):
    """Checks that only make sense for a handful of picks (Monte Carlo tails, overlapping bets)."""
    import model
    tail = pd.DataFrame(False, index=top3.index, columns=top3.columns)
    same = pd.DataFrame(False, index=top3.index, columns=top3.columns)
    mc = model.mc_rows_for(prices, top3, cls, n_sims=400)
    corr_src = R.rolling(26, min_periods=13)
    for t in top3.index:
        row = top3.loc[t]
        picks = row[row != 0]
        if picks.empty:
            continue
        for a, d in picks.items():
            m = mc.get((a, t))
            v = vol_w.at[t, a] if (t in vol_w.index and a in vol_w.columns) else np.nan
            if m and v == v and v > 0:
                bad = -m.get("p5_none", np.nan) if d > 0 else m.get("p95_none", np.nan)
                tail.at[t, a] = bool(bad == bad and bad > 2 * v)
        # weaker picks that move with a stronger one (picks are ordered strongest first by the model)
        names = list(picks.index)
        if len(names) > 1 and t in R.index:
            hist = R.loc[:t].tail(26)[names]
            c = hist.corr()
            for i, a in enumerate(names[1:], start=1):
                for s in names[:i]:
                    if c.at[a, s] * np.sign(picks[a]) * np.sign(picks[s]) > 0.7:
                        same.at[t, a] = True
    return {"Fat-tail crash risk": tail, "Same bet twice": same}


def _apply(pos, flag, idx, reb):
    p = pos.copy()
    f = flag.reindex(index=p.index, columns=p.columns).fillna(False)
    f.loc[~f.index.isin(reb)] = False          # only decide on rebalance Fridays
    p[f] = 0.0
    p.loc[~p.index.isin(reb)] = np.nan
    return p.ffill().fillna(0)


def _brake(ret_base, pos, idx, reb):
    """Half size after a bad 4 weeks (uses only finished weeks)."""
    typical = ret_base.abs().rolling(26, min_periods=8).median().shift(1)
    bad = ret_base.rolling(4, min_periods=4).sum().shift(1) < -2 * typical
    scale = pd.Series(np.where(bad, 0.5, 1.0), index=ret_base.index)
    return pos.mul(scale.reindex(pos.index).fillna(1.0), axis=0)


def _metrics(r, cut):
    out = {}
    for part, s in (("disc", r[r.index < cut]), ("unseen", r[r.index >= cut])):
        a = s[s != 0]
        if len(a) < 4:
            out[part] = None
            continue
        sd = a.std()
        curve = (1 + s / 100).cumprod()
        out[part] = dict(avg=a.mean(), sharpe=a.mean() / sd * np.sqrt(52) if sd > 0 else 0, win=(a > 0).mean() * 100,
                         worst=a.min(), dd=((curve / curve.cummax()) - 1).min() * 100, weeks=len(a))
    return out


def judge(base, new):
    if not all([base.get("disc"), base.get("unseen"), new.get("disc"), new.get("unseen")]):
        return "Not enough trades left"
    if all(abs(new[p]["sharpe"] - base[p]["sharpe"]) < 1e-9 for p in ("disc", "unseen")):
        return "➖ No change (it never flagged these trades)"
    better = [new[p]["sharpe"] > base[p]["sharpe"] for p in ("disc", "unseen")]
    safer = [new[p]["dd"] > base[p]["dd"] and new[p]["worst"] >= base[p]["worst"] for p in ("disc", "unseen")]
    if all(better):
        return "✅ Better return for the risk in both periods"
    if all(safer):
        return "🛡 Safer (smaller losses) but not better per unit of risk"
    if not any(better):
        return "❌ Worse: skipping these trades cost more than it saved"
    return "🟡 Mixed: helped in one period only"


def test_checks(cls, sides, F, vol_w, idx, reb, cut, flag_tables, costs=True, vol_target=True):
    """Each check applied on its own to each side, and all discovery winners together."""
    rows = []
    Fi, vi = F.reindex(idx), vol_w.reindex(idx)
    for side, pos in sides.items():
        base_ret, _ = backtest.side_returns(pos, Fi, cls, vi, vol_target, costs)
        base = _metrics(base_ret, cut)
        kept_base = (pos != 0).sum().sum()
        winners = []
        names = [n for n in flag_tables if side == "Model: strongest 3" or n not in TOP3_ONLY]
        for name in names + ["Losing streak brake"]:
            if name == "Losing streak brake":
                p2 = _brake(base_ret, pos, idx, reb)
            else:
                p2 = _apply(pos, flag_tables[name], idx, reb)
            if (p2 != 0).sum().sum() == 0:
                continue
            r2, _ = backtest.side_returns(p2, Fi, cls, vi, vol_target, costs)
            new = _metrics(r2, cut)
            v = judge(base, new)
            if new.get("disc") and base.get("disc") and new["disc"]["sharpe"] > base["disc"]["sharpe"]:
                winners.append(name)
            rows.append(_row(cls, side, name, base, new, v, (p2 != 0).sum().sum() / max(1, kept_base) * 100))
        # all checks that helped in the discovery period, together (chosen without looking at the unseen period)
        if winners:
            p2 = pos
            for name in winners:
                p2 = _brake(base_ret, p2, idx, reb) if name == "Losing streak brake" else _apply(p2, flag_tables[name], idx, reb)
            if (p2 != 0).sum().sum() > 0:
                r2, _ = backtest.side_returns(p2, Fi, cls, vi, vol_target, costs)
                new = _metrics(r2, cut)
                rows.append(_row(cls, side, "★ All discovery winners together", base, new, judge(base, new),
                                 (p2 != 0).sum().sum() / max(1, kept_base) * 100, ", ".join(winners)))
    return pd.DataFrame(rows)


def _row(cls, side, name, base, new, verdict, kept, detail=""):
    g = lambda d, p, k: (d.get(p) or {}).get(k, np.nan)
    return dict(cls=cls, side=side, check=name, level=CHECKS.get(name, ("Combined",))[0], verdict=verdict,
                trades_kept=kept, detail=detail,
                disc_sharpe_before=g(base, "disc", "sharpe"), disc_sharpe_after=g(new, "disc", "sharpe"),
                unseen_sharpe_before=g(base, "unseen", "sharpe"), unseen_sharpe_after=g(new, "unseen", "sharpe"),
                unseen_avg_before=g(base, "unseen", "avg"), unseen_avg_after=g(new, "unseen", "avg"),
                unseen_win_before=g(base, "unseen", "win"), unseen_win_after=g(new, "unseen", "win"),
                unseen_worst_before=g(base, "unseen", "worst"), unseen_worst_after=g(new, "unseen", "worst"),
                unseen_dd_before=g(base, "unseen", "dd"), unseen_dd_after=g(new, "unseen", "dd"))


def traffic_lights(t, assets, flag_tables, proven):
    """🟢 take it, 🟡 take it smaller, 🔴 skip it, with the reasons. ★ = a check proven to help for this class."""
    rows = {}
    for a in assets:
        hit = [n for n, f in flag_tables.items() if t in f.index and a in f.columns and bool(f.at[t, a])]
        strong = [n for n in hit if n in proven]
        if strong or len(hit) >= 3:
            light = "🔴 skip"
        elif hit:
            light = "🟡 smaller"
        else:
            light = "🟢 take it"
        reasons = ", ".join(("★ " if n in proven else "") + n for n in hit) or "no risk flags"
        rows[a] = (light, reasons)
    return rows
