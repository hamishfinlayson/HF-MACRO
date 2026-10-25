"""
models.py - the more advanced forecasting tools, and an honest test of how well each one works.

There are four kinds of model here. Each gives a 12-month (or 4-quarter) forecast:

1. NO CHANGE (the benchmark)
   "In a year it'll be where it is today." Simple, but surprisingly hard to beat.
   A model is only worth using if it beats this.

2. AR(2): AUTOREGRESSIVE (the site's main model, in forecast.py)
   Uses only the indicator's own last two readings.

3. VAR(2): VECTOR AUTOREGRESSION (a standard model in central banks' toolkits)
   Forecasts several indicators together. Each one is predicted from the last two
   readings of ALL of them, so inflation can respond to unemployment and interest
   rates, rates can respond to inflation, and so on.

4. PHILLIPS CURVE (inflation only)
   An economic theory: when unemployment is below normal (a "tight" jobs market),
   wages and prices tend to rise faster. Here it's estimated directly: next year's
   change in inflation is explained by how tight the jobs market is, how far inflation
   is from its usual level, and how much oil prices have moved.

BACKTESTING
   For every month in the last 10 years, each model is re-estimated using ONLY the data
   that existed then, makes its forecast, and is then compared with what actually
   happened. The average size of the miss (mean absolute error) shows which model has
   the best track record. Pandemic months (Feb 2020 to Dec 2021) are left out.
"""

import numpy as np
import pandas as pd

from forecast import PANDEMIC, to_regular

# Which indicators are forecast together in each VAR system
VAR_SYSTEMS = {
    "US": ["us_cpi", "us_unemp", "us_fedfunds"],
    "UK": ["uk_cpi", "uk_unemp", "uk_bankrate"],
    "EA": ["ea_hicp", "ea_unemp", "ecb_dfr"],
}
# Phillips curve inputs: inflation, unemployment, wage growth (or None), oil price
PHILLIPS = {
    "us_cpi": ("us_cpi", "us_unemp", None, "brent"),
    "uk_cpi": ("uk_cpi", "uk_unemp", "uk_pay", "brent"),
    "ea_hicp": ("ea_hicp", "ea_unemp", None, "brent"),
}
MODEL_INFO = {
    "No change": "Assumes it stays where it is today. The benchmark every model has to beat.",
    "AR(2)": "Uses only this indicator's own last two readings (the site's main forecast).",
    "VAR(2)": "Forecasts inflation, unemployment and the interest rate together, so each "
              "one responds to the others.",
    "Phillips curve": "Explains next year's change in inflation by how tight the jobs market is, "
                      "how far inflation is from normal and oil prices.",
    "Average of models": "The simple average of every model above. Combining models often "
                         "beats any single one.",
}


def _in_pandemic(dates):
    return (dates >= PANDEMIC[0]) & (dates <= PANDEMIC[1])


def _horizon(freq):
    return 12 if freq == "M" else 4


def _monthly(series):
    s = series.dropna()
    return s.resample("MS").last().dropna() if len(s) else s


# ---------------------------------------------------------------- AR(2), point forecasts

def ar_fit(values, dates, lags=2):
    pandemic = _in_pandemic(dates)
    X, y = [], []
    for t in range(lags, len(values)):
        if pandemic[t - lags:t + 1].any():
            continue
        X.append([1.0] + [values[t - i] for i in range(1, lags + 1)])
        y.append(values[t])
    if len(y) < 20:
        return None
    beta, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    return beta


def ar_path(values, beta, horizon, lags=2):
    state = list(values[-lags:][::-1])
    out = []
    for _ in range(horizon):
        nxt = beta[0] + float(np.dot(beta[1:], state))
        out.append(nxt)
        state = [nxt] + state[:-1]
    return np.array(out)


def ar_point(train, horizon, lookback_years=25):
    train = train[train.index >= train.index[-1] - pd.DateOffset(years=lookback_years)]
    beta = ar_fit(train.values.astype(float), train.index)
    if beta is None:
        return None
    return float(ar_path(train.values.astype(float), beta, horizon)[-1])


# ---------------------------------------------------------------- VAR(2)

def _var_frame(series_by_id, lookback_years=None, end=None):
    df = pd.concat({k: _monthly(v) for k, v in series_by_id.items()}, axis=1).dropna()
    if end is not None:
        df = df[df.index <= end]
    if lookback_years and len(df):
        df = df[df.index >= df.index[-1] - pd.DateOffset(years=lookback_years)]
    return df


def var_fit(df, lags=2):
    values, dates = df.values.astype(float), df.index
    pandemic = _in_pandemic(dates)
    X, Y = [], []
    for t in range(lags, len(values)):
        if pandemic[t - lags:t + 1].any():
            continue
        X.append(np.concatenate([[1.0]] + [values[t - i] for i in range(1, lags + 1)]))
        Y.append(values[t])
    if len(Y) < 40:
        return None, None
    X, Y = np.array(X), np.array(Y)
    B, *_ = np.linalg.lstsq(X, Y, rcond=None)
    return B, Y - X @ B


def var_paths(df, B, residuals, horizon=12, lags=2, n_sims=1000, seed=7):
    """Simulated futures for every variable. Returns array (sims, horizon, variables)."""
    rng = np.random.default_rng(seed)
    k = df.shape[1]
    hist = df.values.astype(float)[-lags:][::-1]          # most recent first
    state = np.tile(hist, (n_sims, 1, 1))                   # (sims, lags, k)
    out = np.empty((n_sims, horizon, k))
    for h in range(horizon):
        X = np.concatenate([np.ones((n_sims, 1)), state.reshape(n_sims, lags * k)], axis=1)
        shock = residuals[rng.integers(0, len(residuals), n_sims)] if residuals is not None else 0
        nxt = X @ B + shock
        out[:, h, :] = nxt
        state = np.concatenate([nxt[:, None, :], state[:, :-1, :]], axis=1)
    return out


def var_forecast(series_by_id, target, horizon=12, lookback_years=25):
    df = _var_frame(series_by_id, lookback_years)
    B, resid = var_fit(df)
    if B is None:
        raise ValueError("not enough shared history for the VAR")
    paths = var_paths(df, B, resid, horizon)[:, :, list(df.columns).index(target)]
    future = pd.date_range(df.index[-1] + pd.DateOffset(months=1), periods=horizon, freq="MS")
    return pd.DataFrame({"median": np.median(paths, axis=0), "low": np.percentile(paths, 10, axis=0),
                         "high": np.percentile(paths, 90, axis=0)}, index=future)


def var_point(series_by_id, target, end, horizon=12, lookback_years=25):
    df = _var_frame(series_by_id, lookback_years, end=end)
    if len(df) < 60:
        return None
    B, _ = var_fit(df)
    if B is None:
        return None
    path = var_paths(df, B, None, horizon, n_sims=1)[0, :, list(df.columns).index(target)]
    return float(path[-1])


# ---------------------------------------------------------------- Phillips curve (direct 12-month model)

def _phillips_frame(infl, unemp, wages, oil):
    d = {"infl": _monthly(infl), "unemp": _monthly(unemp), "oil": _monthly(oil)}
    if wages is not None:
        d["wages"] = _monthly(wages)
    df = pd.concat(d, axis=1).ffill(limit=2).dropna()
    df["gap"] = df["unemp"] - df["unemp"].rolling(120, min_periods=60).mean()   # vs 10-year norm
    df["infl_dev"] = df["infl"] - df["infl"].rolling(60, min_periods=36).mean()  # vs 5-year norm
    df["oil_yy"] = (df["oil"] / df["oil"].shift(12) - 1) * 100
    if "wages" in df:
        df["real_wage"] = df["wages"] - df["infl"]
    df["target"] = df["infl"].shift(-12) - df["infl"]
    return df


def _phillips_cols(df):
    return ["gap", "infl_dev", "oil_yy"] + (["real_wage"] if "real_wage" in df else [])


def phillips_fit(df, end=None, lookback_years=25):
    train = df.dropna(subset=_phillips_cols(df) + ["target"])
    if end is not None:
        # only use outcomes that were already known at `end`
        train = train[train.index <= end - pd.DateOffset(months=12)]
    train = train[train.index >= (end or train.index[-1]) - pd.DateOffset(years=lookback_years)]
    # leave out rows whose 12-month window touches the pandemic
    bad = (train.index >= PANDEMIC[0] - pd.DateOffset(months=12)) & (train.index <= PANDEMIC[1])
    train = train[~bad]
    if len(train) < 48:
        return None, None
    X = np.column_stack([np.ones(len(train))] + [train[c].values for c in _phillips_cols(df)])
    beta, *_ = np.linalg.lstsq(X, train["target"].values, rcond=None)
    return beta, train["target"].values - X @ beta


def phillips_forecast(infl, unemp, wages, oil, horizon=12):
    df = _phillips_frame(infl, unemp, wages, oil)
    beta, resid = phillips_fit(df)
    if beta is None:
        raise ValueError("not enough history for the Phillips curve")
    row = df.dropna(subset=_phillips_cols(df)).iloc[-1]
    x = np.concatenate([[1.0], [row[c] for c in _phillips_cols(df)]])
    start = float(_monthly(infl).iloc[-1])
    change = float(x @ beta)
    lo, hi = np.percentile(resid, [10, 90])
    steps = np.arange(1, horizon + 1) / horizon
    last = _monthly(infl).index[-1]
    future = pd.date_range(last + pd.DateOffset(months=1), periods=horizon, freq="MS")
    return pd.DataFrame({"median": start + change * steps, "low": start + (change + lo) * steps,
                         "high": start + (change + hi) * steps}, index=future), \
        dict(zip(["constant"] + _phillips_cols(df), beta))


def phillips_point(df, end):
    beta, _ = phillips_fit(df, end=end)
    if beta is None:
        return None
    rows = df.dropna(subset=_phillips_cols(df))
    rows = rows[rows.index <= end]
    if rows.empty:
        return None
    row = rows.iloc[-1]
    x = np.concatenate([[1.0], [row[c] for c in _phillips_cols(df)]])
    return float(row["infl"] + x @ beta)


# ---------------------------------------------------------------- backtesting

def backtest(series, predictors, years=10):
    """
    series: the indicator. predictors: {name: function(origin_date, train_series, horizon) -> value}.
    Re-runs every model at each past date using only data available then.
    Returns {name: {mae, hit_rate, n, results DataFrame}}.
    """
    s, freq = to_regular(series.dropna())
    if freq not in ("M", "Q"):
        raise ValueError("needs monthly or quarterly data")
    h = _horizon(freq)
    step = pd.DateOffset(months=1 if freq == "M" else 3)
    start = s.index[-1] - pd.DateOffset(years=years) - step * h
    rows = []
    for i in range(len(s) - h):
        origin, target_date = s.index[i], s.index[i + h]
        if origin < start or _in_pandemic(pd.DatetimeIndex([target_date]))[0] \
                or _in_pandemic(pd.DatetimeIndex([origin]))[0]:
            continue
        train = s.iloc[:i + 1]
        actual, now = float(s.iloc[i + h]), float(s.iloc[i])
        row = {"origin": origin, "target": target_date, "actual": actual, "now": now}
        for name, fn in predictors.items():
            try:
                row[name] = fn(origin, train, h)
            except Exception:
                row[name] = None
        rows.append(row)
    table = pd.DataFrame(rows)
    out = {}
    if table.empty:
        return out
    typical = (table["actual"] - table["now"]).abs().median()
    for name in predictors:
        col = pd.to_numeric(table[name], errors="coerce")
        ok = col.notna()
        if ok.sum() < 12:
            continue
        err = (col[ok] - table.loc[ok, "actual"]).abs()
        moved = (table.loc[ok, "actual"] - table.loc[ok, "now"])
        pred_move = col[ok] - table.loc[ok, "now"]
        big = moved.abs() > 0.25 * typical
        hits = (np.sign(pred_move[big]) == np.sign(moved[big])).mean() * 100 if big.any() else None
        out[name] = dict(mae=float(err.mean()), hit_rate=None if name == "No change" else hits,
                         n=int(ok.sum()), results=table.loc[ok, ["target", "actual"]].assign(pred=col[ok]))
    return out


def evaluate(ind_id, loaded, years=10):
    """
    Runs every model that applies to `ind_id`: forecasts + 10-year backtest.
    Returns a list of dicts: name, forecast (DataFrame or None), end value, mae, hit_rate, n, about.
    """
    ind, res = loaded[ind_id]
    series = res["series"]
    s_reg, freq = to_regular(series.dropna())
    h = _horizon(freq)
    preds = {"No change": lambda o, tr, hh: float(tr.iloc[-1]),
             "AR(2)": lambda o, tr, hh: ar_point(tr, hh)}
    extra_fc = {}

    system = next((ids for ids in VAR_SYSTEMS.values() if ind_id in ids), None)
    if freq == "M" and system and all(i in loaded and loaded[i][1]["series"] is not None for i in system):
        sys_series = {i: loaded[i][1]["series"] for i in system}
        try:
            extra_fc["VAR(2)"] = var_forecast(sys_series, ind_id)
            preds["VAR(2)"] = lambda o, tr, hh: var_point(sys_series, ind_id, o, hh)
        except Exception:
            pass

    spec = PHILLIPS.get(ind_id)
    if freq == "M" and spec:
        infl_id, unemp_id, wage_id, oil_id = spec
        need = [infl_id, unemp_id, oil_id] + ([wage_id] if wage_id else [])
        if all(i in loaded and loaded[i][1]["series"] is not None for i in need):
            g = lambda i: loaded[i][1]["series"] if i else None
            try:
                extra_fc["Phillips curve"], _ = phillips_forecast(g(infl_id), g(unemp_id), g(wage_id), g(oil_id))
                pdf = _phillips_frame(g(infl_id), g(unemp_id), g(wage_id), g(oil_id))
                preds["Phillips curve"] = lambda o, tr, hh: phillips_point(pdf, o)
            except Exception:
                pass

    if len(preds) > 2:
        names = [n for n in preds if n != "No change"]
        def combo(o, tr, hh, names=names):
            vals = [preds[n](o, tr, hh) for n in names]
            vals = [v for v in vals if v is not None]
            return float(np.mean(vals)) if vals else None
        preds["Average of models"] = combo

    scores = backtest(series, preds, years=years)
    last = float(s_reg.iloc[-1])
    out = []
    for name in preds:
        fc = extra_fc.get(name)
        if name == "No change":
            end = last
        elif name == "AR(2)":
            end = None                              # filled in by the caller from the main forecast
        elif name == "Average of models":
            end = None
        else:
            end = float(fc["median"].iloc[-1]) if fc is not None else None
        sc = scores.get(name, {})
        out.append(dict(name=name, forecast=fc, end=end, mae=sc.get("mae"), hit_rate=sc.get("hit_rate"),
                        n=sc.get("n"), results=sc.get("results"), about=MODEL_INFO.get(name, "")))
    return out


# ---------------------------------------------------------------- market-implied expectations

def implied_path(yields):
    """
    yields: {"3M": %, "6M": %, "1Y": %, "2Y": %} latest Treasury yields.
    Forward rates: the rate the market is pricing for a FUTURE period.
    e.g. the 6m-to-1y forward = what 6-month money is expected to cost in six months' time.
    (Uses simple compounding; ignores the small 'term premium', so treat it as approximate.)
    """
    def fwd(y1, t1, y2, t2):
        return ((1 + y2 / 100) ** t2 / (1 + y1 / 100) ** t1) ** (1 / (t2 - t1)) * 100 - 100
    out = {}
    if "3M" in yields:
        out["Now (3-month bill)"] = yields["3M"]
    if "6M" in yields and "1Y" in yields:
        out["In 6 months (6m→1y forward)"] = fwd(yields["6M"], 0.5, yields["1Y"], 1.0)
    if "1Y" in yields and "2Y" in yields:
        out["In 1 year (1y→2y forward)"] = fwd(yields["1Y"], 1.0, yields["2Y"], 2.0)
    return out


# ---------------------------------------------------------------- caching
# Backtests re-fit each model ~120 times, so results are kept until the data changes.
_CACHE = {}


def _stamp(loaded, ids):
    out = []
    for i in ids:
        s = loaded.get(i, (None, {}))[1].get("series") if i in loaded else None
        out.append((i, None if s is None else (len(s), str(s.index[-1]), float(s.iloc[-1]))))
    return tuple(out)


def evaluate_cached(ind_id, loaded, simple=False):
    """simple=True runs only No change and AR(2) (fast, used for the scorecard of every forecast)."""
    related = [ind_id]
    if not simple:
        for ids in VAR_SYSTEMS.values():
            if ind_id in ids:
                related += ids
        related += [i for i in PHILLIPS.get(ind_id, ()) if i]
    key = (ind_id, simple, _stamp(loaded, related))
    if key not in _CACHE:
        if simple:
            series = loaded[ind_id][1]["series"]
            scores = backtest(series, {"No change": lambda o, tr, hh: float(tr.iloc[-1]),
                                       "AR(2)": lambda o, tr, hh: ar_point(tr, hh)})
            _CACHE[key] = scores
        else:
            _CACHE[key] = evaluate(ind_id, loaded)
    return _CACHE[key]
