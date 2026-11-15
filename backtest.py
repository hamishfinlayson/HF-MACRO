"""
backtest.py - ASSET LAB testing engine (PC version only).

WALK-FORWARD TESTING
For every Friday in the chosen period, pretend it's that Friday: use only prices up to that day,
make the Monte Carlo prediction and every strategy side's picks, then check what actually
happened the following week. Nothing from the future is used.

STRATEGY SIDES ("sleeves")
Each idea is scored on its own: weekly return after realistic costs, win rate, the chance the
result is luck (p-value), and a "choose on the first half, confirm on the second half" check.

WHY WE MISSED
Every Monte Carlo miss (actual move minus our median) is split into:
  whole market + sector + our drift + noise
so we can see which part of the model is responsible.

Just for fun and learning. Not financial advice.
"""

import zlib
from math import erf, sqrt

import numpy as np
import pandas as pd

LAM = 0.94

# Round-trip trading costs in % (Trading 212 practice assumptions: spread, plus FX fee, plus stamp duty)
COST_ROUND_TRIP = {"UK stocks": 0.20, "US stocks": 0.10 + 0.30, "World indices": 0.10,
                   "Commodities": 0.10, "FX": 0.03, "Crypto": 0.60}
UK_STAMP_DUTY = 0.50          # % on UK share purchases
SHORT_FINANCING_WEEK = 0.125   # % per week for holding a CFD short (about 6.5% a year)

SIDES = {
    # name: (description, kind, applies to)
    "Momentum 12-1": ("PROVEN. Buy the top 20% by return over the last 12 months, skipping the most recent month.",
                      "proven", None),
    "One-week reversal": ("PROVEN. Buy the 20% that fell most last week (the bounce-back effect).", "proven", None),
    "Short last week's winners": ("PROVEN (contrarian). Short the 20% that rose most last week.", "proven", None),
    "Low volatility": ("PROVEN. Buy the calmest 20% (lowest 60-day volatility).", "proven",
                       ("UK stocks", "US stocks", "World indices")),
    "52-week high": ("PROVEN. Buy the 20% trading closest to their 52-week high.", "proven",
                     ("UK stocks", "US stocks", "World indices", "Commodities")),
    "Trend following": ("PROVEN. Long anything up over 12 months, short anything down.", "proven",
                        ("World indices", "Commodities", "FX", "Crypto")),
    "FX carry": ("PROVEN. Long the currency with the higher central bank rate.", "proven", ("FX",)),
    "Turn of month": ("PROVEN. Hold the whole class only in weeks that include a month-end.", "proven", None),
    "Monte Carlo: trend continues": ("MODEL. Buy the top 20% by simulated median move per unit of risk "
                                     "(trend-continues view).", "model", None),
    "Monte Carlo: bounce back": ("MODEL. Buy the top 20% by simulated median move per unit of risk "
                                 "(bounce-back view).", "model", None),
    "Averages agree + momentum": ("CREATIVE. Momentum picks, but only where the simulated mean, median and "
                                  "mode all point up.", "creative", None),
    "Box breakers": ("CREATIVE. Follow assets whose move last week broke out of their 90% range.", "creative", None),
    "Quiet climbers": ("CREATIVE. Steady 12-week risers with below-average volatility.", "creative", None),
    "Trust-weighted momentum": ("CREATIVE. Momentum, betting more on assets whose ranges have been reliable.",
                                "creative", None),
    "Macro tilt": ("CREATIVE. If the NY Fed recession probability is over 30%, buy the calmest stocks; "
                   "otherwise buy momentum.", "creative", ("UK stocks", "US stocks", "World indices")),
    "Laggard catch-up": ("CREATIVE. When oil, gold or copper moves and its linked assets haven't followed, "
                         "bet on the laggard catching up.", "creative", "cross"),
}
NOT_BACKTESTABLE = {
    "Under the radar": "Needs past news and Wikipedia attention, which only exists from now on (Prediction log).",
    "Bounce-back x attention": "Needs past news counts, so it can only be tested going forward (Prediction log).",
}
# leader -> [(follower, relationship)]  (+1 moves with, -1 moves against)
LINKS = {"BZ=F": [("USDNOK=X", -1), ("BP.L", +1), ("SHEL.L", +1)],
         "GC=F": [("AUDUSD=X", +1)],
         "HG=F": [("GLEN.L", +1), ("AAL.L", +1)]}


def normal_p(t):
    """Two-sided p-value for a t-statistic (normal approximation)."""
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


# ================================================================= Monte Carlo through time

def ewma_series(r):
    var = np.empty(len(r))
    var[0] = np.var(r[:20]) if len(r) >= 20 else np.var(r)
    for t in range(1, len(r)):
        var[t] = LAM * var[t - 1] + (1 - LAM) * r[t - 1] ** 2
    return np.maximum(var, 1e-12)


def mc_at_dates(price, dates, days, n_sims=1000, seed=0):
    """
    Monte Carlo prediction made at each date in `dates`, using only data up to that date.
    Returns a DataFrame (index = dates) with median, mean, mode, p5, p95, p_up and sd for
    each drift view (suffix _trend, _none, _bounce).
    """
    from assetlab import recency_weights
    p = price.dropna()
    p = p[p > 0]
    lr = np.log(p).diff().dropna()
    if len(lr) < 260:
        return pd.DataFrame()
    r = lr.values
    var = ewma_series(r)
    z_all = r / np.sqrt(var)
    idx = lr.index
    rng = np.random.default_rng(seed)
    rows = {}
    for d in dates:
        k = idx.searchsorted(d, side="right") - 1          # last trading day on or before d
        if k < 252:
            continue
        z = z_all[max(0, k - 2519):k + 1]
        z = (z - z.mean()) / z.std()
        w = recency_weights(len(z))
        v = np.full(n_sims, LAM * var[k] + (1 - LAM) * r[k] ** 2)
        L = np.zeros(n_sims)
        for _ in range(days):
            ret = np.sqrt(v) * rng.choice(z, size=n_sims, p=w)
            L += ret
            v = LAM * v + (1 - LAM) * ret ** 2
        out = {}
        mus = {"trend": 0.5 * r[max(0, k - 62):k + 1].mean() * days,
               "none": 0.0,
               "bounce": -0.5 * r[max(0, k - 4):k + 1].sum()}
        for name, c in mus.items():
            pct = (np.exp(L + c) - 1) * 100
            q5, q25, q50, q75, q95 = np.percentile(pct, [5, 25, 50, 75, 95])
            counts, edges = np.histogram(pct, bins=40)
            j = int(np.argmax(counts))
            out.update({f"median_{name}": q50, f"mean_{name}": pct.mean(), f"mode_{name}": (edges[j] + edges[j + 1]) / 2,
                        f"p5_{name}": q5, f"p25_{name}": q25, f"p75_{name}": q75,
                        f"p95_{name}": q95, f"pup_{name}": (pct > 0).mean() * 100,
                        f"sd_{name}": pct.std()})
        rows[d] = out
    return pd.DataFrame.from_dict(rows, orient="index")


# ================================================================= signals and sides

def weekly_frames(prices):
    """Weekly (Friday) prices, this week's return and NEXT week's return (what we're predicting)."""
    W = prices.resample("W-FRI").last()
    W = W[W.index <= prices.index.max()]          # drop an unfinished week (e.g. when run on a Monday)
    R = W.pct_change(fill_method=None) * 100
    F = R.shift(-1)
    return W, R, F


def features(prices, W):
    """Signals known at each Friday (only past data)."""
    daily = prices.ffill(limit=5)
    lr = np.log(daily).diff()
    at = lambda df: df.resample("W-FRI").last().reindex(W.index)
    mom = at(daily.shift(21) / daily.shift(252) - 1) * 100
    vol60 = at(lr.rolling(60, min_periods=40).std() * np.sqrt(252) * 100)
    high52 = at(daily / daily.rolling(252, min_periods=200).max())
    ret12m = at(daily / daily.shift(252) - 1) * 100
    r12w = (W / W.shift(12) - 1) * 100
    vol12w = W.pct_change(fill_method=None).rolling(12).std() * 100
    return dict(mom=mom, vol60=vol60, high52=high52, ret12m=ret12m, r12w=r12w, vol12w=vol12w)


def pick_top(score, frac=0.2, ascending=False, mask=None):
    """1 for the top `frac` of each week's cross-section (at least one asset), else 0."""
    s = score.where(mask) if mask is not None else score
    rank = s.rank(axis=1, ascending=ascending, pct=False)
    n = s.notna().sum(axis=1)
    cutoff = np.maximum(1, np.floor(n * frac))
    return (rank.le(cutoff, axis=0) & s.notna()).astype(float)


def weights(picks, vol=None, vol_target=False):
    """Turn 1/0 (or +1/-1) picks into weights that add up to 100% (equal, or more on calmer assets)."""
    w = picks.copy()
    if vol_target and vol is not None:
        w = w / vol.where(vol > 0)
    w = w.fillna(0)
    total = w.abs().sum(axis=1).replace(0, np.nan)
    return w.div(total, axis=0).fillna(0)


def side_positions(name, cls, f, R, mc, extra):
    """Positions (+ long, - short) decided each Friday for one side within one asset class."""
    idx = R.index
    cols = R.columns
    zero = pd.DataFrame(0.0, index=idx, columns=cols)
    if name == "Momentum 12-1":
        return pick_top(f["mom"])
    if name == "One-week reversal":
        return pick_top(R, ascending=True)
    if name == "Short last week's winners":
        return -pick_top(R)
    if name == "Low volatility":
        return pick_top(f["vol60"], ascending=True)
    if name == "52-week high":
        return pick_top(f["high52"])
    if name == "Trend following":
        return np.sign(f["ret12m"]).fillna(0)
    if name == "FX carry":
        carry = extra.get("carry")
        return np.sign(carry.reindex(index=idx, columns=cols)).fillna(0) if carry is not None else zero
    if name == "Turn of month":
        month_end_week = pd.Series(idx.month, index=idx).shift(-1) != idx.month
        return zero.add(month_end_week.astype(float), axis=0).where(R.notna(), 0)
    if name in ("Monte Carlo: trend continues", "Monte Carlo: bounce back"):
        key = "trend" if "trend" in name else "bounce"
        score = mc[f"median_{key}"] / mc[f"sd_{key}"]
        return pick_top(score)
    if name == "Averages agree + momentum":
        agree = (mc["median_trend"] > 0) & (mc["mean_trend"] > 0) & (mc["mode_trend"] > 0)
        return pick_top(f["mom"], mask=agree)
    if name == "Box breakers":
        lo, hi = mc["p5_none"].shift(1), mc["p95_none"].shift(1)       # last week's predicted range
        broke_up, broke_down = R > hi, R < lo
        return broke_up.astype(float) - broke_down.astype(float)
    if name == "Quiet climbers":
        smooth = f["r12w"] / f["vol12w"]
        calm = f["vol12w"].lt(f["vol12w"].median(axis=1), axis=0) & (f["r12w"] > 0)
        return pick_top(smooth, mask=calm)
    if name == "Trust-weighted momentum":
        inside = ((R >= mc["p5_none"].shift(1)) & (R <= mc["p95_none"].shift(1))).astype(float)
        reliability = inside.rolling(26, min_periods=8).mean().shift(0)
        return pick_top(f["mom"]) * reliability.fillna(0.5)
    if name == "Macro tilt":
        rec = extra.get("recession")
        if rec is None:
            return zero
        stress = rec.reindex(idx, method="ffill") > 30
        calm_picks, mom_picks = pick_top(f["vol60"], ascending=True), pick_top(f["mom"])
        return calm_picks.mul(stress.astype(float), axis=0) + mom_picks.mul((~stress).astype(float), axis=0)
    return zero


MIN_MOVES = [0.0, 0.2, 0.5, 0.8, 1.0, 1.5]


def min_move_filter(pos, expected, min_move):
    """Keep a trade only if the expected move is at least min_move % in the trade's direction."""
    if not min_move:
        return pos
    e = expected.reindex(index=pos.index, columns=pos.columns)
    keep = ((pos > 0) & (e >= min_move)) | ((pos < 0) & (e <= -min_move))
    return pos.where(keep, 0.0)


def threshold_table(name, cls, pos, expected, F, vol, vol_target, costs):
    """How a side would have done with different minimum-move rules (hold to Friday)."""
    rows = []
    base_trades = int((pos != 0).sum().sum())
    for m in MIN_MOVES:
        p = min_move_filter(pos, expected, m)
        n = int((p != 0).sum().sum())
        if n == 0:
            rows.append(dict(side=name, cls=cls, min_move=m, trades=0, kept=0.0, avg_week=np.nan, win_rate=np.nan,
                             total=0.0, weeks=0))
            continue
        r, _ = side_returns(p, F, cls, vol, vol_target, costs)
        a = r[r != 0]
        rows.append(dict(side=name, cls=cls, min_move=m, trades=n, kept=n / max(1, base_trades) * 100,
                         avg_week=a.mean() if len(a) else np.nan, win_rate=(a > 0).mean() * 100 if len(a) else np.nan,
                         total=((1 + r / 100).prod() - 1) * 100, weeks=int(len(a))))
    return rows


def side_returns(pos, F, cls, vol=None, vol_target=False, costs=True):
    """Weekly return of a side (in %), after costs."""
    w = weights(pos, vol, vol_target)
    gross = (w * F.fillna(0)).sum(axis=1)
    if not costs:
        return gross, w
    change = w.diff().abs().fillna(w.abs())
    cost = change.sum(axis=1) * COST_ROUND_TRIP.get(cls, 0.1) / 2
    if cls == "UK stocks":
        cost += w.diff().clip(lower=0).fillna(w.clip(lower=0)).sum(axis=1) * UK_STAMP_DUTY
    cost += w.clip(upper=0).abs().sum(axis=1) * SHORT_FINANCING_WEEK
    active = w.abs().sum(axis=1) > 0
    return (gross - cost).where(active, 0.0), w


def stats(ret, bench=None):
    """Scorecard for a weekly return series (in %)."""
    r = ret.dropna()
    active = r[r != 0]
    n = len(active)
    if n < 4:
        return None
    mean, sd = active.mean(), active.std()
    t = mean / sd * np.sqrt(n) if sd > 0 else 0
    curve = (1 + r / 100).cumprod()
    out = dict(weeks=n, avg_week=mean, win_rate=(active > 0).mean() * 100, annual=mean * 52,
               vol=sd * np.sqrt(52), sharpe=(mean / sd * np.sqrt(52)) if sd > 0 else 0,
               max_dd=((curve / curve.cummax()) - 1).min() * 100, t=t, p=normal_p(t), total=(curve.iloc[-1] - 1) * 100)
    if bench is not None:
        ex = (r - bench.reindex(r.index)).where(r != 0).dropna()
        if len(ex) > 3 and ex.std() > 0:
            out["excess_week"] = ex.mean()
            out["excess_t"] = ex.mean() / ex.std() * np.sqrt(len(ex))
            out["excess_p"] = normal_p(out["excess_t"])
    return out


def verdict(first, second):
    """Choose on the first half, confirm on the second."""
    if not first or not second:
        return "Not enough data"
    a, b = first.get("excess_week", first["avg_week"]), second.get("excess_week", second["avg_week"])
    if a > 0 and b > 0:
        p = second.get("excess_p", second["p"])
        return "✅ Worked in both halves" + (" (and unlikely to be luck)" if p < 0.05 else " (could still be luck)")
    if a > 0 >= b:
        return "⚠️ Worked first, failed to confirm"
    if a <= 0 < b:
        return "⚠️ Only worked in the second half"
    return "❌ Didn't work in either half"




# ================================================================= trade rules: take-profit, stop-loss, Monday entry

TRADE_RULES = {
    "Hold to Friday": "Buy (or short) and sell at the next Friday's close, whatever happens in between.",
    "Take-profit + stop-loss": "Sell automatically as soon as the price hits your target (take-profit) or your "
                               "loss limit (stop-loss); otherwise sell at Friday's close.",
}
ENTRIES = {
    "Friday close": "Trade at Friday's closing price (the moment the prediction is made).",
    "Monday open": "Trade at Monday's opening price, as you would in practice. Weekend price jumps are missed.",
}
TP_MODES = ["Model's good week (75th percentile)", "Model's median move", "Fixed %"]
SL_MODES = ["Model's bad week (5th percentile)", "Model's weak week (25th percentile)", "Fixed %"]


def trade_levels(mc_row, direction, tp_mode, sl_mode, tp_fixed, sl_fixed):
    """Take-profit and stop-loss distances (in %, both positive) for one trade."""
    if mc_row is None:
        return tp_fixed, sl_fixed
    up = direction > 0
    if tp_mode == "Fixed %":
        tp = tp_fixed
    elif tp_mode == "Model's median move":
        tp = abs(mc_row.get("median_none", tp_fixed))
    else:
        tp = mc_row.get("p75_none", tp_fixed) if up else -mc_row.get("p25_none", -tp_fixed)
    if sl_mode == "Fixed %":
        sl = sl_fixed
    elif sl_mode == "Model's weak week (25th percentile)":
        sl = -mc_row.get("p25_none", -sl_fixed) if up else mc_row.get("p75_none", sl_fixed)
    else:
        sl = -mc_row.get("p5_none", -sl_fixed) if up else mc_row.get("p95_none", sl_fixed)
    tp = tp if (tp == tp and tp > 0.05) else max(0.05, abs(tp_fixed))
    sl = sl if (sl == sl and sl > 0.05) else max(0.05, abs(sl_fixed))
    return float(tp), float(sl)


class TradeSim:
    """Plays out one week's trade day by day using daily open/high/low/close."""

    def __init__(self, ohlc, close):
        self.close = close
        if ohlc is None:
            ohlc = {"open": close, "high": close, "low": close, "close": close}
        self.days = close.index
        cols = list(close.columns)
        self.col = {c: i for i, c in enumerate(cols)}
        get = lambda f: ohlc[f].reindex(index=self.days, columns=cols).values
        self.O, self.H, self.L, self.C = get("open"), get("high"), get("low"), close.values
        self.cache = {}

    def outcome(self, ticker, t, t_next, direction, entry, rule, tp, sl):
        """Returns (% return, how it ended: 'target', 'stop' or 'friday')."""
        key = (ticker, t, direction, entry, rule, round(tp, 3), round(sl, 3))
        if key in self.cache:
            return self.cache[key]
        j = self.col.get(ticker)
        if j is None:
            return None
        a = self.days.searchsorted(t, side="right") - 1
        b = self.days.searchsorted(t_next, side="right") - 1
        if a < 0 or b <= a:
            return None
        C, O, H, L = self.C[:, j], self.O[:, j], self.H[:, j], self.L[:, j]
        if entry == "Monday open":
            first = a + 1
            px = O[first] if O[first] == O[first] else C[a]
        else:
            first = a + 1
            px = C[a]
        if not (px == px) or px <= 0:
            return None
        last = C[b] if C[b] == C[b] else np.nan
        result = None
        if rule == "Take-profit + stop-loss":
            up = direction > 0
            tp_px = px * (1 + tp / 100) if up else px * (1 - tp / 100)
            sl_px = px * (1 - sl / 100) if up else px * (1 + sl / 100)
            for k in range(first, b + 1):
                o, h, l = O[k], H[k], L[k]
                c = C[k]
                h = h if h == h else c
                l = l if l == l else c
                if not (h == h):
                    continue
                gap_day = not (entry == "Monday open" and k == first)
                if up:
                    if gap_day and o == o and o <= sl_px:
                        result = (o, "stop"); break
                    if gap_day and o == o and o >= tp_px:
                        result = (o, "target"); break
                    if l <= sl_px:                       # both touched the same day: assume the stop came first
                        result = (sl_px, "stop"); break
                    if h >= tp_px:
                        result = (tp_px, "target"); break
                else:
                    if gap_day and o == o and o >= sl_px:
                        result = (o, "stop"); break
                    if gap_day and o == o and o <= tp_px:
                        result = (o, "target"); break
                    if h >= sl_px:
                        result = (sl_px, "stop"); break
                    if l <= tp_px:
                        result = (tp_px, "target"); break
        if result is None:
            if not (last == last):
                return None
            result = (last, "friday")
        exit_px, how = result
        ret = (exit_px / px - 1) * 100 * (1 if direction > 0 else -1)
        self.cache[key] = (ret, how)
        return ret, how


def rule_side_returns(w, fridays, sim, cls, mc_rows, entry, rule, tp_mode, sl_mode, tp_fixed, sl_fixed, costs=True):
    """
    Weekly returns of a side when every trade follows the trade rules, plus the same trades with a coin
    toss for direction (the average of betting up and betting down), and how trades ended.
    """
    rets, coin, ends = [], [], {"target": 0, "stop": 0, "friday": 0}
    rt = COST_ROUND_TRIP.get(cls, 0.1)
    for i, t in enumerate(fridays[:-1]):
        t_next = fridays[i + 1]
        row = w.loc[t]
        row = row[row != 0]
        if row.empty:
            rets.append(0.0); coin.append(0.0)
            continue
        week, week_coin, wsum = 0.0, 0.0, 0.0
        for ticker, wt in row.items():
            d = 1 if wt > 0 else -1
            mrow = mc_rows.get((ticker, t))
            tp, sl = trade_levels(mrow, d, tp_mode, sl_mode, tp_fixed, sl_fixed)
            res = sim.outcome(ticker, t, t_next, d, entry, rule, tp, sl)
            if res is None:
                continue
            r, how = res
            ends[how] += 1
            tp2, sl2 = trade_levels(mrow, -d, tp_mode, sl_mode, tp_fixed, sl_fixed)
            other = sim.outcome(ticker, t, t_next, -d, entry, rule, tp2, sl2)
            c = (r + other[0]) / 2 if other else r
            cost = 0.0
            if costs:
                cost = rt + (UK_STAMP_DUTY if (cls == "UK stocks" and d > 0) else 0) + (SHORT_FINANCING_WEEK if d < 0 else 0)
                c_cost = rt + (UK_STAMP_DUTY / 2 if cls == "UK stocks" else 0) + SHORT_FINANCING_WEEK / 2
            else:
                c_cost = 0.0
            a = abs(wt)
            week += a * (r - cost)
            week_coin += a * (c - c_cost)
            wsum += a
        rets.append(week / wsum if wsum else 0.0)
        coin.append(week_coin / wsum if wsum else 0.0)
    idx = fridays[:-1]
    return pd.Series(rets, index=idx), pd.Series(coin, index=idx), ends


# ================================================================= the full run

def run(prices_by_class, start, end, horizon_days_fn, sectors=None, rates=None, recession=None,
        vol_target=False, costs=True, n_sims=1000, progress=None, ohlc_by_class=None,
        entry="Friday close", rule="Hold to Friday", tp_mode=TP_MODES[0], sl_mode=SL_MODES[0],
        tp_fixed=3.0, sl_fixed=3.0, min_move=0.0):
    """
    Walk-forward test between `start` and `end` for every asset class given.
    min_move: only take a trade if the Monte Carlo ('trend continues' view) expects at least this % move
    in the trade's direction (0 = take every trade).
    Returns a dict with: predictions (one row per asset-week), sides (weekly returns per side and
    class), scorecards, and the class benchmarks.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    preds, side_rets, benches, scorecards, weights_by = [], {}, {}, [], {}
    coin_rets, trade_ends, hold_rets = {}, {}, {}
    thresholds = []
    use_rules = not (rule == "Hold to Friday" and entry == "Friday close")
    total_assets = sum(p.shape[1] for p in prices_by_class.values())
    done = 0
    weekly_all = {}
    for cls, prices in prices_by_class.items():
        prices = prices.dropna(axis=1, how="all")
        if prices.empty:
            continue
        W, R, F = weekly_frames(prices)
        fridays = W.index[(W.index >= start) & (W.index <= end)]
        if len(fridays) < 4:
            continue
        # ---- Monte Carlo predictions at each Friday
        mc_parts = {}
        for col in prices.columns:
            m = mc_at_dates(prices[col], fridays, horizon_days_fn(cls), n_sims=n_sims, seed=zlib.crc32(col.encode()) % 10000)
            if not m.empty:
                mc_parts[col] = m
            done += 1
            if progress:
                progress(done / max(total_assets, 1), f"{cls}: {col}")
        if not mc_parts:
            continue
        mc = {k: pd.DataFrame({c: m[k] for c, m in mc_parts.items() if k in m}).reindex(index=W.index, columns=W.columns)
              for k in next(iter(mc_parts.values())).columns}
        # ---- one row per asset-week
        for col, m in mc_parts.items():
            df = m.copy()
            df["actual"] = F[col].reindex(df.index)
            df["this_week"] = R[col].reindex(df.index)
            df["ticker"], df["cls"] = col, cls
            df["sector"] = (sectors or {}).get(col, cls)
            preds.append(df.reset_index().rename(columns={"index": "date"}))
        # ---- strategy sides
        f = features(prices, W)
        extra = {"recession": recession}
        if cls == "FX" and rates is not None:
            extra["carry"] = carry_matrix(W.columns, rates)
        bench = F.mean(axis=1)
        benches[cls] = bench.loc[fridays]
        weekly_all[cls] = (W, R, F)
        sim = TradeSim((ohlc_by_class or {}).get(cls), prices)
        mc_rows = {(col, d): m.loc[d].to_dict() for col, m in mc_parts.items() for d in m.index}
        for name, (desc, kind, applies) in SIDES.items():
            if applies == "cross" or (applies and cls not in applies):
                continue
            pos = side_positions(name, cls, f, R, mc, extra).reindex(index=W.index, columns=W.columns).fillna(0)
            med = mc.get("median_trend")
            if med is not None:
                thresholds += threshold_table(name, cls, pos.loc[fridays], med.loc[fridays], F.loc[fridays],
                                              f["vol60"].loc[fridays], vol_target, costs)
                pos = min_move_filter(pos, med, min_move)
            ret, w = side_returns(pos.loc[fridays], F.loc[fridays], cls, f["vol60"].loc[fridays], vol_target, costs)
            if (w.abs().sum(axis=1) > 0).sum() < 4:
                continue
            hold_rets[(name, cls)] = ret
            r_rule, r_coin, ends = rule_side_returns(w, list(fridays), sim, cls, mc_rows, entry, rule, tp_mode,
                                                     sl_mode, tp_fixed, sl_fixed, costs)
            side_rets[(name, cls)] = r_rule if use_rules else ret
            coin_rets[(name, cls)] = r_coin
            trade_ends[(name, cls)] = ends
            weights_by[(name, cls)] = w
    # ---- cross-asset side: laggard catch-up
    lag = laggard_returns(weekly_all, start, end, costs)
    if lag is not None:
        side_rets[("Laggard catch-up", "Cross-asset")] = lag
    # ---- scorecards
    for (name, cls), ret in side_rets.items():
        bench = benches.get(cls)
        half = len(ret) // 2
        s_all = stats(ret, bench)
        if not s_all:
            continue
        s1, s2 = stats(ret.iloc[:half], bench), stats(ret.iloc[half:], bench)
        extra_cols = {}
        coin = coin_rets.get((name, cls))
        if coin is not None:
            active = ret != 0
            extra_cols["coin_week"] = float(coin[active.reindex(coin.index, fill_value=False)].mean()) if active.any() else None
            diff = (ret - coin.reindex(ret.index)).where(active).dropna()
            if len(diff) > 3 and diff.std() > 0:
                extra_cols["vs_coin_week"] = diff.mean()
                extra_cols["vs_coin_p"] = normal_p(diff.mean() / diff.std() * np.sqrt(len(diff)))
        hold = hold_rets.get((name, cls))
        if hold is not None and use_rules:
            extra_cols["hold_week"] = float(hold[hold != 0].mean()) if (hold != 0).any() else None
        ends = trade_ends.get((name, cls))
        if ends and sum(ends.values()):
            n = sum(ends.values())
            extra_cols.update(hit_target=ends["target"] / n * 100, hit_stop=ends["stop"] / n * 100,
                              to_friday=ends["friday"] / n * 100, trades=n)
        scorecards.append(dict(side=name, cls=cls, kind=SIDES[name][1], **s_all, verdict=verdict(s1, s2),
                               first_half=(s1 or {}).get("excess_week", (s1 or {}).get("avg_week")),
                               second_half=(s2 or {}).get("excess_week", (s2 or {}).get("avg_week")),
                               **extra_cols))
    predictions = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()
    return dict(predictions=predictions, side_returns=side_rets, scorecards=pd.DataFrame(scorecards),
                benches=benches, weights=weights_by, start=start, end=end, coin_returns=coin_rets,
                thresholds=pd.DataFrame(thresholds), min_move=min_move,
                settings=dict(entry=entry, rule=rule, tp_mode=tp_mode, sl_mode=sl_mode, tp_fixed=tp_fixed,
                              sl_fixed=sl_fixed, ohlc=bool(ohlc_by_class)))


def carry_matrix(pairs, rates):
    """+1 if the pair's first currency has the higher central bank rate, -1 if lower (monthly, forward-filled)."""
    from reference import CURRENCIES
    out = {}
    for pair in pairs:
        base, quote = pair[:3], pair[3:6]
        b = CURRENCIES.get(base, {}).get("bis")
        q = CURRENCIES.get(quote, {}).get("bis")
        if b in rates.columns and q in rates.columns:
            out[pair] = (rates[b] - rates[q]).resample("W-FRI").last().ffill()
    return pd.DataFrame(out) if out else None


def laggard_returns(weekly_all, start, end, costs=True):
    """Laggard catch-up across asset classes."""
    R_all = pd.concat([v[1] for v in weekly_all.values()], axis=1) if weekly_all else None
    F_all = pd.concat([v[2] for v in weekly_all.values()], axis=1) if weekly_all else None
    if R_all is None:
        return None
    R_all = R_all.loc[:, ~R_all.columns.duplicated()]
    F_all = F_all.loc[:, ~F_all.columns.duplicated()]
    idx = R_all.index[(R_all.index >= start) & (R_all.index <= end)]
    rets = []
    for leader, followers in LINKS.items():
        if leader not in R_all:
            continue
        for fol, rel in followers:
            if fol not in R_all:
                continue
            gap = rel * R_all[leader] - R_all[fol]
            pos = np.sign(gap).where(gap.abs() > 1.5, 0)          # only when the gap is over 1.5 points
            r = pos * F_all[fol] - (pos.diff().abs().fillna(0) * 0.1 if costs else 0)
            rets.append(r.loc[idx])
    if not rets:
        return None
    df = pd.concat(rets, axis=1)
    active = (df != 0).sum(axis=1)
    return (df.sum(axis=1) / active.replace(0, np.nan)).fillna(0)


# ================================================================= model accuracy and "why we missed"

def accuracy(pred, view="none"):
    """How good were the Monte Carlo predictions? (one row per asset-week)"""
    d = pred.dropna(subset=["actual", f"median_{view}"]).copy()
    if d.empty:
        return None
    med, act = d[f"median_{view}"], d["actual"]
    moved = act != 0
    hit = (np.sign(med[moved]) == np.sign(act[moved])).mean() * 100
    inside = ((act >= d[f"p5_{view}"]) & (act <= d[f"p95_{view}"])).mean() * 100
    p = d[f"pup_{view}"] / 100
    brier = ((p - (act > 0)) ** 2).mean()
    return dict(n=len(d), hit=hit, mae=(act - med).abs().mean(), mae_naive=act.abs().mean(),
                coverage=inside, brier=brier, brier_coin=((0.5 - (act > 0)) ** 2).mean())


def calibration_table(pred, view="none", bins=10):
    d = pred.dropna(subset=["actual", f"pup_{view}"])
    if d.empty:
        return pd.DataFrame()
    b = pd.cut(d[f"pup_{view}"], np.linspace(0, 100, bins + 1), include_lowest=True)
    t = d.groupby(b, observed=True).agg(said=(f"pup_{view}", "mean"), happened=("actual", lambda x: (x > 0).mean() * 100),
                                        n=("actual", "size"))
    return t.reset_index(drop=True)


def breakdown(pred, view="none", lookback=52):
    """
    Splits each miss (actual - our median) into:
      market : the asset class's average move that week x the asset's sensitivity to it (beta)
      sector : how its sector did versus the class that week (stocks only)
      drift  : minus our predicted median (the part of the miss caused by our drift view)
      noise  : everything else (company news, random moves)
    The four pieces add up exactly to the miss.
    """
    d = pred.dropna(subset=["actual", f"median_{view}"]).copy()
    if d.empty:
        return None, None
    d["mkt"] = d.groupby(["cls", "date"])["actual"].transform("mean")
    d["sec_avg"] = d.groupby(["cls", "sector", "date"])["actual"].transform("mean")
    d = d.sort_values(["ticker", "date"])
    # beta (sensitivity to the class average) from this asset's own past weeks only (no look-ahead)
    d["mkt_now"] = d.groupby(["cls", "date"])["this_week"].transform("mean")
    roll = lambda s: s.groupby(d["ticker"]).transform(lambda v: v.rolling(lookback, min_periods=12).mean())
    cov = roll(d["this_week"] * d["mkt_now"]) - roll(d["this_week"]) * roll(d["mkt_now"])
    var = roll(d["mkt_now"] ** 2) - roll(d["mkt_now"]) ** 2
    d["beta"] = (cov / var.where(var > 0)).clip(-3, 3).fillna(1.0)
    d["market"] = d["beta"] * d["mkt"]
    is_stock = d["cls"].isin(["UK stocks", "US stocks"])
    d["sector_part"] = np.where(is_stock, d["sec_avg"] - d["mkt"], 0.0)
    d["drift"] = -d[f"median_{view}"]
    d["miss"] = d["actual"] - d[f"median_{view}"]
    d["noise"] = d["miss"] - d["market"] - d["sector_part"] - d["drift"]
    band = (d[f"p95_{view}"] - d[f"p5_{view}"]) / 3.29
    d["event_like"] = d["noise"].abs() > 3 * band
    d["outside_range"] = (d["actual"] < d[f"p5_{view}"]) | (d["actual"] > d[f"p95_{view}"])
    parts = ["market", "sector_part", "drift", "noise"]
    total = (d["miss"] ** 2).sum()
    share = {p: float((d[p] * d["miss"]).sum() / total * 100) if total else 0 for p in parts}
    summary = dict(share=share, avg_abs={p: float(d[p].abs().mean()) for p in parts},
                   avg_miss=float(d["miss"].abs().mean()), bias=float(d["miss"].mean()),
                   event_rate=float(d["event_like"].mean() * 100), outside=float(d["outside_range"].mean() * 100))
    return summary, d


# ================================================================= this week's live picks

def current_picks(prices_by_class, horizon_days_fn, rates=None, recession=None, n_sims=1000):
    """What each side would buy (or short) this week, using the latest prices."""
    out = []
    weekly_all = {}
    for cls, prices in prices_by_class.items():
        prices = prices.dropna(axis=1, how="all")
        if prices.empty:
            continue
        W, R, F = weekly_frames(prices)
        last = W.index[-1]
        recent = W.index[-30:]
        mc_parts = {}
        for col in prices.columns:
            m = mc_at_dates(prices[col], recent[-2:], horizon_days_fn(cls), n_sims=n_sims, seed=zlib.crc32(col.encode()) % 10000)
            if not m.empty:
                mc_parts[col] = m
        if not mc_parts:
            continue
        mc = {k: pd.DataFrame({c: m[k] for c, m in mc_parts.items() if k in m}).reindex(index=W.index, columns=W.columns)
              for k in next(iter(mc_parts.values())).columns}
        f = features(prices, W)
        extra = {"recession": recession}
        if cls == "FX" and rates is not None:
            extra["carry"] = carry_matrix(W.columns, rates)
        weekly_all[cls] = (W, R, F)
        for name, (desc, kind, applies) in SIDES.items():
            if applies == "cross" or (applies and cls not in applies):
                continue
            pos = side_positions(name, cls, f, R, mc, extra).reindex(index=W.index, columns=W.columns).fillna(0)
            row = pos.loc[last]
            for ticker, v in row[row != 0].items():
                g = lambda k: mc[k].at[last, ticker] if k in mc and ticker in mc[k].columns else np.nan
                up = v > 0
                out.append(dict(side=name, cls=cls, ticker=ticker, direction="BUY" if up else "SHORT",
                                this_week=R.loc[last, ticker], expected=g("median_trend"),
                                tp=g("p75_none") if up else -g("p25_none"), sl=-g("p5_none") if up else g("p95_none"),
                                normal=g("sd_none"), date=last))
    # laggard catch-up, live
    if weekly_all:
        R_all = pd.concat([v[1] for v in weekly_all.values()], axis=1)
        R_all = R_all.loc[:, ~R_all.columns.duplicated()]
        last = R_all.index[-1]
        for leader, followers in LINKS.items():
            for fol, rel in followers:
                if leader in R_all and fol in R_all:
                    gap = rel * R_all.loc[last, leader] - R_all.loc[last, fol]
                    if abs(gap) > 1.5:
                        out.append(dict(side="Laggard catch-up", cls="Cross-asset", ticker=fol,
                                        direction="BUY" if gap > 0 else "SHORT", this_week=R_all.loc[last, fol]))
    return pd.DataFrame(out)


# ================================================================= prediction log

LOG_COLUMNS = ["logged", "target", "ticker", "name", "cls", "horizon", "view", "median", "best", "best_type",
               "p5", "p95", "p_up", "attention", "attn_vs_normal", "news", "views", "under_radar"]


def log_predictions(scan_df, att_df, horizon, view, path):
    """Saves every asset's prediction so it can be scored once the week (or month) is over."""
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now().normalize()
    target = now + pd.Timedelta(days=7 if horizon == "Next week" else 30)
    df = scan_df.copy()
    extra = att_df.set_index("ticker")[["attention", "attn_vs_normal", "news", "views"]] if att_df is not None and len(att_df) else None
    if extra is not None:
        df = df.join(extra, on="ticker")
    top = set(att_df.sort_values("radar", ascending=False).head(3)["ticker"]) if att_df is not None and "radar" in att_df else set()
    rows = pd.DataFrame({
        "logged": now, "target": target, "ticker": df["ticker"], "name": df["name"], "cls": df["cls"],
        "horizon": horizon, "view": view, "median": df["median"], "best": df["best"], "best_type": df["best_type"],
        "p5": df["p5"], "p95": df["p95"], "p_up": df["p_up"],
        "attention": df.get("attention"), "attn_vs_normal": df.get("attn_vs_normal"),
        "news": df.get("news"), "views": df.get("views"), "under_radar": df["ticker"].isin(top)})
    if path.exists():
        old = pd.read_csv(path, parse_dates=["logged", "target"])
        # one entry per asset, day, horizon and view
        old = old[~((old["logged"] == now) & (old["horizon"] == horizon) & (old["view"] == view))]
        rows = pd.concat([old, rows], ignore_index=True)
    rows.to_csv(path, index=False)
    return len(rows)


def score_log(path, price_lookup):
    """Fills in what actually happened for every logged prediction whose target date has passed."""
    from pathlib import Path
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    log = pd.read_csv(path, parse_dates=["logged", "target"])
    today = pd.Timestamp.now().normalize()
    actual = []
    for _, r in log.iterrows():
        if r["target"] > today:
            actual.append(np.nan)
            continue
        s = price_lookup(r["ticker"])
        if s is None or s.empty:
            actual.append(np.nan)
            continue
        a, b = s.asof(r["logged"]), s.asof(r["target"])
        actual.append((b / a - 1) * 100 if a and not pd.isna(a) and not pd.isna(b) else np.nan)
    log["actual"] = actual
    log["inside"] = (log["actual"] >= log["p5"]) & (log["actual"] <= log["p95"])
    log["right_way"] = np.sign(log["median"]) == np.sign(log["actual"])
    return log


# ================================================================= risk: simulate picks together

def joint_simulation(prices, days, n_sims=10000, seed=3):
    """
    Simulates several assets TOGETHER: every simulated day replays the same real past day for all
    of them, so assets that tend to move together (e.g. Shell and BP) still do in the simulation.
    Returns a DataFrame of % changes (simulations x assets).
    """
    from assetlab import recency_weights
    lr = np.log(prices.ffill(limit=3)).diff().dropna(how="any").iloc[-2520:]
    if len(lr) < 120 or lr.shape[1] < 1:
        raise ValueError("not enough shared history")
    r = lr.values
    var = np.column_stack([ewma_series(r[:, j]) for j in range(r.shape[1])])
    z = r / np.sqrt(var)
    z = (z - z.mean(axis=0)) / z.std(axis=0)
    v = LAM * var[-1] + (1 - LAM) * r[-1] ** 2
    rng = np.random.default_rng(seed)
    w = recency_weights(len(z))
    v = np.tile(v, (n_sims, 1))
    L = np.zeros_like(v)
    for _ in range(days):
        rows = rng.choice(len(z), size=n_sims, p=w)
        ret = np.sqrt(v) * z[rows]
        L += ret
        v = LAM * v + (1 - LAM) * ret ** 2
    return pd.DataFrame((np.exp(L) - 1) * 100, columns=lr.columns)
