"""
model.py - the COMBINER MODEL (PC version only).

The Signal Lab tests each ingredient on its own. The model puts them together:

1. Every Friday, for every asset, it takes all the ingredient scores (z-scores: how unusual each one is).
2. It learns how much weight each ingredient deserves from everything that happened BEFORE that Friday
   (a "walk-forward" regression). Recent years count more than old ones (half-life 3 years).
3. "Shrinkage" (ridge regression) pulls every weight towards zero, so the model only leans on an
   ingredient when the past evidence for it is strong. More shrinkage = more cautious.
4. The model's output is an expected move for next week. Its SIGN is the direction call.
5. The Monte Carlo is then used for what it's good at: how big the move could be, which sets the
   take-profit and stop-loss levels when trade rules are on.

Everything is checked like the BACKTEST: after costs, against holding the whole class, against a
coin toss, and on a discovery period and an unseen period.

Just for fun and learning. Not financial advice.
"""

import zlib

import numpy as np
import pandas as pd

import backtest
import risk
import signals

SHRINK = {"Light": 0.1, "Medium": 0.5, "Heavy": 2.0}
SIDES = {
    "Model: every call": "Bet on every asset in the direction the model says (equal size, or volatility-targeted).",
    "Model: strongest 3": "Only the 3 assets where the model is most confident (expected move vs normal move), "
                          "in the direction it says.",
    "Model: best 3 buys": "The 3 assets with the biggest expected rise. Buys only, no shorting.",
    "Model: strongest 10": "The 10 most confident calls. More positions = company-specific surprises cancel out more.",
    "Model: strongest 3, hedged": "The strongest 3, with the whole class sold against them (e.g. an index CFD), so a "
                                  "market-wide move can't cause a miss: only the model's call matters.",
    "Baseline: 3-month momentum": "No model: just bet that each asset keeps doing what it did in the last 3 months. "
                                  "The model should beat this simple rule.",
}
BASE_SIDES = [s for s in SIDES if s != "Model: strongest 3, hedged"]
HEDGE_COST = 0.05          # % per change in hedge size (index CFD spread)
HEDGE_FINANCE = 0.01       # % per week of overnight financing on the hedge


def hold_for(pos, idx, reb):
    """Positions chosen on rebalance Fridays and held until the next one."""
    p = pos.reindex(idx)
    p.loc[~p.index.isin(reb)] = np.nan
    return p.ffill().fillna(0)


def _cube(z, keys, dates, cols):
    X = np.stack([z[k].reindex(index=dates, columns=cols).values.astype(float) for k in keys], axis=2)
    return X


def ridge_walk_forward(z, keys, F, vol_w, pred_start, pred_end, shrink=0.5, halflife=156, min_rows=200, horizon=1):
    """
    Walk-forward ridge regression. At each Friday t the weights are fitted only on weeks whose result
    was already known (targets up to the week ending at t). Returns (predicted % move, weights over time).
    """
    dates, cols = F.index, F.columns
    keys = list(keys)
    T, N, K = len(dates), len(cols), len(keys)
    preds = pd.DataFrame(np.nan, index=dates, columns=cols)
    if K == 0 or T < 30:
        return preds, pd.DataFrame()
    X = _cube(z, keys, dates, cols)
    have = np.isfinite(X).sum(axis=2) >= max(1, K // 3)
    X = np.nan_to_num(X, nan=0.0)
    vw = vol_w.reindex(index=dates, columns=cols).values * np.sqrt(horizon)    # normal move over the horizon
    Y = np.clip(F.values / np.where(vw > 0, vw, np.nan), -4, 4)
    h = int(horizon)
    p = K + 1
    A, b, n = np.zeros((p, p)), np.zeros(p), 0.0
    delta = 0.5 ** (1 / halflife)
    pen = np.eye(p)
    pen[0, 0] = 0.0
    betas = {}
    out = np.full((T, N), np.nan)
    for i in range(T):
        if i >= h:                                   # the h-week result that started at i-h has just finished
            ok = have[i - h] & np.isfinite(Y[i - h])
            A *= delta
            b *= delta
            n *= delta
            if ok.any():
                Xi = np.column_stack([np.ones(ok.sum()), X[i - h][ok]])
                A += Xi.T @ Xi
                b += Xi.T @ Y[i - h][ok]
                n += ok.sum()
        t = dates[i]
        if pred_start <= t <= pred_end and n >= min_rows:
            try:
                beta = np.linalg.solve(A + shrink * n * pen, b)
            except np.linalg.LinAlgError:
                continue
            betas[t] = beta
            ok = have[i] & np.isfinite(vw[i]) & (vw[i] > 0)
            if ok.any():
                out[i, ok] = (beta[0] + X[i][ok] @ beta[1:]) * vw[i][ok]
    preds = pd.DataFrame(out, index=dates, columns=cols)
    B = pd.DataFrame(betas, index=["(average drift)"] + keys).T if betas else pd.DataFrame()
    return preds, B


def contributions(z, keys, beta, t, cols):
    """How much each ingredient pushed this week's prediction for each asset (weight x score)."""
    rows = {}
    for k in keys:
        if k in z and k in beta.index:
            rows[k] = z[k].reindex(columns=cols).loc[t].fillna(0) * beta[k]
    return pd.DataFrame(rows)


def drivers_text(row, n=3):
    """'1-month momentum (+), VIX link (−)': the ingredients that pushed this prediction most, and which way."""
    top = row.reindex(row.abs().sort_values(ascending=False).index).head(n)
    return ", ".join(f"{signals.INGREDIENTS.get(k, (k,))[0]} ({'+' if v > 0 else '−'})" for k, v in top.items() if abs(v) > 0.01)


def model_positions(name, pred, vol_w, raw):
    conf = pred / vol_w.where(vol_w > 0)
    if name == "Model: every call":
        return np.sign(pred).fillna(0)
    if name in ("Model: strongest 3", "Model: strongest 10"):
        k = 3 if name.endswith("3") else 10
        r = conf.abs().rank(axis=1, ascending=False)
        return (np.sign(pred) * (r <= k)).fillna(0)
    if name == "Model: best 3 buys":
        c = conf.where(pred > 0)
        r = c.rank(axis=1, ascending=False)
        return (r <= 3).astype(float)
    if name == "Baseline: 3-month momentum":
        m = raw.get("mom_3m")
        return np.sign(m).reindex_like(pred).fillna(0) if m is not None else pred * 0
    return pred * 0


def mc_rows_for(prices, w, cls, n_sims=500):
    """Monte Carlo percentiles for every (asset, Friday) the model actually traded (for take-profit/stop-loss)."""
    import assetlab
    out = {}
    days = assetlab.horizon_days(cls, "Next week")
    for col in w.columns:
        dates = w.index[w[col] != 0]
        if len(dates) == 0 or col not in prices:
            continue
        m = backtest.mc_at_dates(prices[col], dates, days, n_sims=n_sims, seed=zlib.crc32(col.encode()) % 10000)
        for d in m.index:
            out[(col, d)] = m.loc[d].to_dict()
    return out


def _split_stats(ret, bench, cut):
    d, u = ret[ret.index < cut], ret[ret.index >= cut]
    return backtest.stats(d, bench), backtest.stats(u, bench), backtest.stats(ret, bench)


def model_verdict(d, u):
    if not d or not u:
        return "Not enough data"
    a, b = d.get("excess_week", d["avg_week"]), u.get("excess_week", u["avg_week"])
    if a > 0 and b > 0:
        return "✅ Worked in discovery and unseen" + (" (unlikely luck)" if u.get("excess_p", u["p"]) < 0.05 else "")
    if a > 0 >= b:
        return "⚠️ Worked in discovery, failed unseen"
    if a <= 0 < b:
        return "⚠️ Only worked in the unseen period"
    return "❌ Didn't beat holding the class"


def prediction_quality(pred, F, idx):
    p, f = pred.reindex(idx), F.reindex(idx)
    ok = p.notna() & f.notna() & (p != 0) & (f != 0)
    if ok.sum().sum() < 20:
        return {}
    hit = (np.sign(p) == np.sign(f)).where(ok).stack().mean() * 100
    ics = []
    for d in idx:
        a, b = p.loc[d], f.loc[d]
        m = a.notna() & b.notna()
        if m.sum() >= 5 and a[m].nunique() > 1:
            ics.append(a[m].rank().corr(b[m].rank()))
    ret = signals.signal_returns(p.where(ok), f).dropna()
    t = ret.mean() / ret.std() * np.sqrt(len(ret)) if len(ret) > 3 and ret.std() > 0 else np.nan
    return dict(hit=hit, ic=np.nanmean(ics) if ics else np.nan, edge=ret.mean() if len(ret) else np.nan, t=t,
                calls=int(ok.sum().sum()))


def choose_keys(built_cls, start, cut, mode, cls=None):
    """Which ingredients the model may use. 'Discovery winners' only looks at the discovery period."""
    keys = [k for k in built_cls["z"] if not k.startswith("ctx_")]
    if mode == "All ingredients":
        return keys
    if mode == "Focus ingredients (not parked)":
        import focus
        return focus.focus_keys(cls, keys)
    keep = []
    idx = built_cls["F"].index
    for k in keys:
        st = signals._part_stats(built_cls["z"][k], built_cls["F"], idx[(idx >= start) & (idx < cut)])
        if st and abs(st["t"]) >= 1.5:
            keep.append(k)
    return keep


def run_model(prices_by_class, ohlc_by_class, ctx, start, end, unseen_frac=0.3, shrink="Medium",
              key_mode="All ingredients", vol_target=True, costs=True, entry="Friday close",
              rule="Hold to Friday", tp_mode=None, sl_mode=None, tp_fixed=3.0, sl_fixed=3.0,
              ablation=True, engine="ridge", progress=None, built=None, horizon=1, risk_test=True, min_move=0.0):
    """Builds the model for each asset class, backtests its sides, and makes this week's calls."""
    horizon = int(horizon)
    if horizon > 1:                       # trade rules are checked within one week; longer holds sell at the end
        rule, entry = "Hold to Friday", "Friday close"
    tp_mode = tp_mode or backtest.TP_MODES[0]
    sl_mode = sl_mode or backtest.SL_MODES[0]
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    use_rules = not (rule == "Hold to Friday" and entry == "Friday close")
    need_mc = rule != "Hold to Friday" and (tp_mode != "Fixed %" or sl_mode != "Fixed %")
    res = dict(cards=[], quality=[], ablation=[], weights={}, preds={}, latest={}, curves={}, keys={}, cut=None,
               risk={}, risk_flags={}, thresholds=[],
               settings=dict(shrink=shrink, key_mode=key_mode, engine=engine, entry=entry, rule=rule, horizon=horizon,
                             min_move=min_move,
                             tp_mode=tp_mode, sl_mode=sl_mode, tp_fixed=tp_fixed, sl_fixed=sl_fixed))
    built = built or {}
    n = max(1, len(prices_by_class))
    for ci, (cls, prices) in enumerate(prices_by_class.items()):
        if progress:
            progress(ci / n, f"{cls}: building ingredients...")
        if cls not in built:
            raw, z, W, R, F, vol_w = signals.build_ingredients(cls, prices, (ohlc_by_class or {}).get(cls), ctx)
            built[cls] = dict(raw=raw, z=z, W=W, R=R, F=F, vol_w=vol_w)
        b = built[cls]
        F, vol_w = b["F"], b["vol_w"]
        idx = F.index[(F.index >= start) & (F.index <= end) & F.notna().any(axis=1)]
        if len(idx) < 12:
            continue
        cut = idx[int(len(idx) * (1 - unseen_frac))]
        res["cut"] = cut
        keys = choose_keys(b, start, cut, key_mode, cls)
        res["keys"][cls] = keys
        if not keys:
            continue
        if progress:
            progress((ci + 0.3) / n, f"{cls}: walk-forward model ({len(keys)} ingredients)...")
        info = {}
        pred, B = fit_predict(engine, b, keys, start, F.index[-1], shrink, info, horizon)
        Fh = F if horizon == 1 else forward_returns(b["W"], horizon)
        reb = idx[::horizon]                              # the Fridays when positions are (re)chosen
        if engine == "ml":
            info["importance"] = B
            res.setdefault("learned", {})[cls] = ml_learned(info)
        res["preds"][cls] = pred
        res["weights"][cls] = B
        # quality of the predictions themselves (before costs)
        for part, sub in (("Discovery", reb[reb < cut]), ("Unseen", reb[reb >= cut])):
            q = prediction_quality(pred, Fh, sub)
            if q:
                res["quality"].append(dict(cls=cls, part=part, **q))
        # sides, after costs, with trade rules and the coin toss
        sim = backtest.TradeSim((ohlc_by_class or {}).get(cls), prices.dropna(axis=1, how="all"))
        bench = F.mean(axis=1).reindex(idx)
        def positions(s, m):
            p = model_positions(s, pred, vol_w, b["raw"])
            if s.startswith("Model"):
                p = backtest.min_move_filter(p, pred, m)
            return hold_for(p, idx, reb)
        side_pos = {s: positions(s, min_move) for s in SIDES if s in BASE_SIDES}
        for s in ("Model: every call", "Model: strongest 3"):
            base_n = int((positions(s, 0.0) != 0).sum().sum())
            for m in backtest.MIN_MOVES:
                p = positions(s, m)
                n_tr = int((p != 0).sum().sum())
                r, _ = backtest.side_returns(p, F.reindex(idx), cls, vol_w.reindex(idx), vol_target, costs)
                act = r[r != 0]
                res["thresholds"].append(dict(side=s, cls=cls, min_move=m, trades=n_tr, kept=n_tr / max(1, base_n) * 100,
                                              avg_week=act.mean() if len(act) else np.nan,
                                              win_rate=(act > 0).mean() * 100 if len(act) else np.nan,
                                              total=((1 + r / 100).prod() - 1) * 100, weeks=int(len(act))))
        side_pos = {s: p for s, p in side_pos.items() if (p.abs().sum(axis=1) > 0).sum() >= 4}
        mc_rows = {}
        if need_mc and side_pos:
            if progress:
                progress((ci + 0.4) / n, f"{cls}: Monte Carlo take-profit and stop-loss levels...")
            traded = sum(p.abs() for p in side_pos.values())
            mc_rows = mc_rows_for(prices, traded, cls)
        side_runs = {}
        for side, pos in side_pos.items():
            ret, w = backtest.side_returns(pos, F.reindex(idx), cls, vol_w.reindex(idx), vol_target, costs)
            if use_rules:
                r_rule, r_coin, ends = backtest.rule_side_returns(w, list(idx) + [idx[-1] + pd.Timedelta(days=7)], sim, cls,
                                                                  mc_rows, entry, rule, tp_mode, sl_mode, tp_fixed, sl_fixed, costs)
                r_rule, r_coin = r_rule.reindex(idx).fillna(0), r_coin.reindex(idx).fillna(0)
            else:
                gross = (w * F.reindex(idx).fillna(0)).sum(axis=1)
                r_rule, r_coin, ends = ret, (ret - gross), {}        # a coin toss earns nothing on average, minus the same costs
            side_runs[side] = (r_rule if use_rules else ret, r_coin, ends, w)
        if "Model: strongest 3" in side_runs:
            r3, c3, e3, w3 = side_runs["Model: strongest 3"]
            net = w3.sum(axis=1)
            hcost = (net.diff().abs().fillna(net.abs()) * HEDGE_COST + net.abs() * HEDGE_FINANCE) if costs else 0
            hedge_pnl = net * bench.fillna(0)
            side_runs["Model: strongest 3, hedged"] = ((r3 - hedge_pnl - hcost).where(r3 != 0, 0.0),
                                                        (c3 - hcost).where(r3 != 0, 0.0), e3, w3)
        res["weights_used"] = res.get("weights_used", {})
        for side, (final, r_coin, ends, w) in side_runs.items():
            res["weights_used"][(side, cls)] = w
            res["curves"][(side, cls)] = final
            d, u, a = _split_stats(final, bench, cut)
            active = final != 0
            diff = (final - r_coin).where(active).dropna()
            cu = diff[diff.index >= cut]
            card = dict(side=side, cls=cls, verdict=model_verdict(d, u),
                        disc_week=(d or {}).get("avg_week"), unseen_week=(u or {}).get("avg_week"),
                        unseen_vs_class=(u or {}).get("excess_week"), win_rate=(a or {}).get("win_rate"),
                        sharpe=(a or {}).get("sharpe"), max_dd=(a or {}).get("max_dd"), weeks=(a or {}).get("weeks"),
                        coin_week=float(r_coin[active].mean()) if active.any() else None,
                        vs_coin_week=diff.mean() if len(diff) else None,
                        vs_coin_p=signals.normal_p(diff.mean() / diff.std() * np.sqrt(len(diff))) if len(diff) > 3 and diff.std() > 0 else None,
                        unseen_vs_coin=cu.mean() if len(cu) else None)
            tot = sum(ends.values())
            if tot:
                card.update(hit_target=ends["target"] / tot * 100, hit_stop=ends["stop"] / tot * 100,
                            to_friday=ends["friday"] / tot * 100)
            res["cards"].append(card)
        # the risk layer: test every check with and without, then this week's traffic lights
        flag_tables, proven = {}, set()
        if risk_test and {"Model: every call", "Model: strongest 3"} <= set(side_pos):
            if progress:
                progress((ci + 0.45) / n, f"{cls}: testing the risk checks...")
            live = pred.index[pred.index >= start]
            p_live = pred.loc[live]
            top3 = model_positions("Model: strongest 3", p_live, vol_w.reindex(live), b["raw"])
            ml_pred = ((ctx or {}).get("_ml_preds") or {}).get(cls)
            flag_tables = risk.flags(cls, b, p_live, ctx, prices, ml_pred=ml_pred, top3=top3, horizon=horizon)
            rt = risk.test_checks(cls, {s: side_pos[s] for s in ("Model: every call", "Model: strongest 3")},
                                  F, vol_w, idx, reb, cut, flag_tables, costs, vol_target)
            res["risk"][cls] = rt
            if not rt.empty:
                proven = set(rt[rt["verdict"].str.startswith("✅") & ~rt["check"].str.startswith("★")]["check"])
        # this week's calls (the last Friday, whose result isn't known yet)
        t = F.index[-1]
        if t in pred.index and pred.loc[t].notna().any():
            last = pd.DataFrame({"pred": pred.loc[t], "normal": vol_w.loc[t]}).dropna()
            last["confidence"] = last["pred"] / last["normal"]
            if not B.empty and engine == "ridge":
                con = contributions(b["z"], keys, B.iloc[-1], t, last.index)
                last["drivers"] = [drivers_text(con.loc[a]) for a in last.index]
            last["normal"] = last["normal"] * np.sqrt(horizon)
            last["confidence"] = last["pred"] / last["normal"]
            if flag_tables:
                lights = risk.traffic_lights(t, last.index, flag_tables, proven)
                last["risk"] = [lights[a][0] for a in last.index]
                last["risk_why"] = [lights[a][1] for a in last.index]
                res["risk_flags"][cls] = sorted(proven)
            res["latest"][cls] = (t, last.sort_values("confidence", key=np.abs, ascending=False))
        # does each ingredient add anything?
        if ablation and engine == "ridge" and len(keys) > 1:
            base_d = prediction_quality(pred, Fh, reb[reb < cut])
            base_u = prediction_quality(pred, Fh, reb[reb >= cut])
            for j, k in enumerate(keys):
                if progress:
                    progress((ci + 0.5 + 0.5 * j / len(keys)) / n, f"{cls}: does '{signals.INGREDIENTS.get(k, (k,))[0]}' add anything?")
                p2, _ = ridge_walk_forward(b["z"], [x for x in keys if x != k], Fh, vol_w, start, end, SHRINK[shrink],
                                           horizon=horizon)
                dq = prediction_quality(p2, Fh, reb[reb < cut])
                uq = prediction_quality(p2, Fh, reb[reb >= cut])
                if not (dq and uq and base_d and base_u):
                    continue
                res["ablation"].append(dict(
                    cls=cls, key=k, ingredient=signals.INGREDIENTS.get(k, (k,))[0],
                    disc_gain=base_d["edge"] - dq["edge"], unseen_gain=base_u["edge"] - uq["edge"],
                    disc_hit_gain=base_d["hit"] - dq["hit"], unseen_hit_gain=base_u["hit"] - uq["hit"]))
    if progress:
        progress(1.0, "Done")
    res["cards"] = pd.DataFrame(res["cards"])
    res["thresholds"] = pd.DataFrame(res["thresholds"])
    res["quality"] = pd.DataFrame(res["quality"])
    abl = pd.DataFrame(res["ablation"])
    if not abl.empty:
        abl["adds"] = np.where((abl["disc_gain"] > 0) & (abl["unseen_gain"] > 0), "✅ helps in both",
                       np.where((abl["disc_gain"] <= 0) & (abl["unseen_gain"] <= 0), "❌ model is better without it",
                                "🟡 mixed"))
    res["ablation"] = abl
    res["built"] = built
    return res


def forward_returns(W, h):
    """% change over the next h weeks (h=1 is next week)."""
    return (W.shift(-h) / W - 1) * 100


def fit_predict(engine, b, keys, start, last, shrink, info=None, horizon=1):
    Fh = b["F"] if horizon == 1 else forward_returns(b["W"], horizon)
    if engine == "ridge":
        return ridge_walk_forward(b["z"], keys, Fh, b["vol_w"], start, last, SHRINK[shrink], horizon=horizon)
    if engine == "ml":
        ctx_keys = [k for k in b["z"] if k.startswith("ctx_")]
        return gbm_walk_forward(b["z"], list(keys) + ctx_keys, Fh, b["vol_w"], start, last, shrink, info,
                                horizon=horizon)
    raise ValueError(f"unknown engine {engine}")


# ================================================================= v20: machine learning (gradient boosting)

ML_SETTINGS = {"Light": dict(max_iter=250, min_samples_leaf=100, learning_rate=0.06),
               "Medium": dict(max_iter=150, min_samples_leaf=250, learning_rate=0.05),
               "Heavy": dict(max_iter=80, min_samples_leaf=600, learning_rate=0.04)}


def ml_available():
    try:
        import sklearn  # noqa: F401
        return True
    except Exception:
        return False


def gbm_walk_forward(z, keys, F, vol_w, pred_start, pred_end, shrink="Medium", info=None, retrain_every=13,
                     max_rows=120_000, halflife=156, horizon=1):
    """
    Walk-forward gradient boosting: hundreds of small decision trees, each correcting the last. Unlike the
    ridge model it can learn combinations ("momentum works, but only when the VIX is low"). Retrained every
    13 weeks on finished weeks only. Missing ingredients are allowed (trees handle gaps).
    """
    from sklearn.ensemble import HistGradientBoostingRegressor
    dates, cols = F.index, F.columns
    T, N, K = len(dates), len(cols), len(keys)
    out = np.full((T, N), np.nan)
    if K == 0 or T < 60:
        return pd.DataFrame(out, index=dates, columns=cols), pd.DataFrame()
    X = _cube(z, keys, dates, cols)
    vw = vol_w.reindex(index=dates, columns=cols).values * np.sqrt(horizon)
    Y = np.clip(F.values / np.where(vw > 0, vw, np.nan), -4, 4)
    have = np.isfinite(X).sum(axis=2) >= max(1, K // 4)
    est, last_fit, fits = None, -10 ** 9, []
    pred_idx = [i for i in range(T) if pred_start <= dates[i] <= pred_end]
    for i in pred_idx:
        if est is None or i - last_fit >= retrain_every:
            tr = [j for j in range(i - int(horizon) + 1) if np.isfinite(Y[j]).any()]   # results already finished
            rows_x, rows_y, rows_w = [], [], []
            for j in tr:
                ok = have[j] & np.isfinite(Y[j])
                if ok.any():
                    rows_x.append(X[j][ok]); rows_y.append(Y[j][ok])
                    rows_w.append(np.full(ok.sum(), 0.5 ** ((i - j) / halflife)))
            if not rows_x:
                continue
            Xt, yt, wt = np.vstack(rows_x), np.concatenate(rows_y), np.concatenate(rows_w)
            if len(yt) > max_rows:
                Xt, yt, wt = Xt[-max_rows:], yt[-max_rows:], wt[-max_rows:]
            if len(yt) < 500:
                continue
            est = HistGradientBoostingRegressor(max_depth=3, l2_regularization=1.0, random_state=0, early_stopping=False,
                                                **ML_SETTINGS.get(shrink, ML_SETTINGS["Medium"]))
            # skip ingredients with no usable values yet (e.g. seasonal patterns need 3 years of history)
            use = np.array([np.unique(c[np.isfinite(c)]).size > 1 for c in Xt.T])
            if not use.any():
                continue
            est.fit(Xt[:, use], yt, sample_weight=wt)
            est.use_cols_ = use
            last_fit = i
            fits.append(dates[i])
            if info is not None:
                info["train"] = (Xt[-20000:][:, est.use_cols_], yt[-20000:])
        ok = have[i] & np.isfinite(vw[i]) & (vw[i] > 0)
        if est is not None and ok.any():
            out[i, ok] = est.predict(X[i][ok][:, est.use_cols_]) * vw[i][ok]
    imp = pd.DataFrame()
    if est is not None and info is not None:
        info["estimator"], info["keys"], info["fits"] = est, [k for k, u in zip(keys, est.use_cols_) if u], fits
        try:
            from sklearn.inspection import permutation_importance
            Xt, yt = info["train"]
            pi = permutation_importance(est, Xt, yt, n_repeats=3, random_state=0)
            imp = pd.DataFrame([pi.importances_mean * 1000], index=[dates[last_fit]], columns=info["keys"])
        except Exception:
            pass
    return pd.DataFrame(out, index=dates, columns=cols), imp


def ml_learned(info, top=3):
    """What the trees learned: average prediction for low/high values of the top ingredients, in calm vs fearful markets."""
    est, keys = info.get("estimator"), info.get("keys", [])
    if est is None or "train" not in info:
        return pd.DataFrame()
    Xt, _ = info["train"]
    pred = est.predict(Xt)
    rows = []
    vix_j = keys.index("ctx_vix") if "ctx_vix" in keys else None
    imp = info.get("importance")
    order = list(imp.iloc[-1].drop("ctx_vix", errors="ignore").drop("ctx_vol", errors="ignore")
                 .sort_values(ascending=False).index[:top]) if imp is not None and not imp.empty else keys[:top]
    for k in order:
        j = keys.index(k)
        x = Xt[:, j]
        m = np.isfinite(x)
        if m.sum() < 200:
            continue
        lo, hi = np.nanpercentile(x[m], [20, 80])
        for regime, mask in ([("All markets", np.ones(len(x), bool))] +
                             ([("Calm (VIX below normal)", Xt[:, vix_j] < 0), ("Fearful (VIX above normal)", Xt[:, vix_j] >= 0)]
                              if vix_j is not None else [])):
            mm = m & mask
            low = pred[mm & (x <= lo)].mean() if (mm & (x <= lo)).any() else np.nan
            high = pred[mm & (x >= hi)].mean() if (mm & (x >= hi)).any() else np.nan
            rows.append(dict(ingredient=signals.INGREDIENTS.get(k, (k,))[0], markets=regime,
                             when_low=low, when_high=high, difference=high - low))
    return pd.DataFrame(rows)


def arena(results):
    """Side-by-side: each model (and the simple baseline) on the discovery and unseen periods."""
    rows = []
    for name, res in results.items():
        q, cards = res["quality"], res["cards"]
        for cls in sorted(set(q["cls"])) if not q.empty else []:
            qd = q[(q["cls"] == cls) & (q["part"] == "Discovery")]
            qu = q[(q["cls"] == cls) & (q["part"] == "Unseen")]
            ec = cards[(cards["cls"] == cls) & (cards["side"] == "Model: every call")]
            s3 = cards[(cards["cls"] == cls) & (cards["side"] == "Model: strongest 3")]
            rows.append(dict(cls=cls, model=name,
                             disc_hit=qd["hit"].iloc[0] if len(qd) else np.nan, unseen_hit=qu["hit"].iloc[0] if len(qu) else np.nan,
                             unseen_ic=qu["ic"].iloc[0] if len(qu) else np.nan, unseen_edge=qu["edge"].iloc[0] if len(qu) else np.nan,
                             unseen_t=qu["t"].iloc[0] if len(qu) else np.nan,
                             every_call_unseen=ec["unseen_week"].iloc[0] if len(ec) else np.nan,
                             strongest3_unseen=s3["unseen_week"].iloc[0] if len(s3) else np.nan,
                             unseen_vs_coin=ec["unseen_vs_coin"].iloc[0] if len(ec) else np.nan))
        if name == list(results)[0]:
            for cls in sorted(set(cards["cls"])) if not cards.empty else []:
                b = cards[(cards["cls"] == cls) & (cards["side"] == "Baseline: 3-month momentum")]
                if len(b):
                    rows.append(dict(cls=cls, model="Baseline: 3-month momentum", every_call_unseen=b["unseen_week"].iloc[0],
                                     unseen_vs_coin=b["unseen_vs_coin"].iloc[0]))
    df = pd.DataFrame(rows)
    winners = {}
    if not df.empty:
        for cls, g in df.groupby("cls"):
            g = g.dropna(subset=["every_call_unseen"])
            if g.empty:
                continue
            best = g.sort_values("every_call_unseen", ascending=False).iloc[0]
            sure = "" if (best.get("unseen_t", np.nan) or 0) >= 2 else " (not enough evidence to rule out luck yet)"
            winners[cls] = f"{best['model']}{sure}"
    return df, winners
