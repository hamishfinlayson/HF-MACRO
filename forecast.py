"""
forecast.py - the simple forecasting model, the star ratings and recession dates.

How the forecast works (in plain English)
-----------------------------------------
1. Take the last 25 years of the indicator (pandemic months are left out
   because they were so extreme they would distort everything).
2. Fit an "autoregressive" model: next value = a + b1 * last value + b2 * value before.
   It learns how the indicator usually moves on from where it is now.
3. Run 2,000 simulated futures, each time adding a randomly picked past
   "surprise" (the model's historical errors).
4. The middle of those simulations is the forecast line; the range that
   80% of them land in is the shaded band.

It only uses the indicator's own history, so it can't see shocks coming.
That's why the star rating cross-checks it against five related indicators.
"""

import numpy as np
import pandas as pd

PANDEMIC = (pd.Timestamp("2020-02-01"), pd.Timestamp("2021-12-31"))


def infer_freq(series):
    """'M' monthly, 'Q' quarterly, 'D' daily (or None if it can't tell)."""
    if len(series) < 3:
        return None
    gap = pd.Series(series.index).diff().dt.days.median()
    if gap <= 7:
        return "D"
    if gap <= 40:
        return "M"
    if gap <= 100:
        return "Q"
    return None


def to_regular(series):
    """Daily data is turned into monthly averages so every forecast is monthly or quarterly."""
    freq = infer_freq(series)
    if freq == "D":
        return series.resample("MS").mean().dropna(), "M"
    return series, freq


def ar_forecast(series, lags=2, lookback_years=25, n_sims=2000, seed=42):
    """
    Returns a table indexed by future dates with columns:
    median (forecast line), low and high (80% range).
    """
    s, freq = to_regular(series.dropna())
    if freq not in ("M", "Q"):
        raise ValueError("forecasts need monthly or quarterly data")
    horizon = 12 if freq == "M" else 4
    s = s[s.index >= s.index[-1] - pd.DateOffset(years=lookback_years)]

    values, dates = s.values.astype(float), s.index
    in_pandemic = (dates >= PANDEMIC[0]) & (dates <= PANDEMIC[1])
    X, y = [], []
    for t in range(lags, len(values)):
        if in_pandemic[t - lags:t + 1].any():
            continue
        X.append([1.0] + [values[t - i] for i in range(1, lags + 1)])
        y.append(values[t])
    if len(y) < 20:
        raise ValueError("not enough history to forecast")
    X, y = np.array(X), np.array(y)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ beta

    rng = np.random.default_rng(seed)
    state = np.tile(values[-lags:][::-1], (n_sims, 1))  # most recent value first
    paths = np.empty((n_sims, horizon))
    for h in range(horizon):
        prediction = beta[0] + state @ beta[1:]
        paths[:, h] = prediction + rng.choice(residuals, size=n_sims)
        state = np.column_stack([paths[:, h], state[:, :-1]])

    step = pd.DateOffset(months=1 if freq == "M" else 3)
    future = pd.date_range(dates[-1] + step, periods=horizon,
                           freq="MS" if freq == "M" else "QS")
    return pd.DataFrame({
        "median": np.median(paths, axis=0),
        "low": np.percentile(paths, 10, axis=0),
        "high": np.percentile(paths, 90, axis=0),
    }, index=future)


# ---------------------------------------------------------------- star ratings

def typical_move(series, months=6):
    """How much this indicator normally moves over `months` (median absolute change)."""
    m = series.resample("MS").last().dropna()
    m = m[m.index >= m.index[-1] - pd.DateOffset(years=20)]
    changes = (m - m.shift(months)).abs().dropna()
    return float(changes.median()) if len(changes) else 0.0


def direction(change, typical, threshold=0.25):
    """+1 rising, -1 falling, 0 flat (a move smaller than a quarter of a typical move)."""
    if typical <= 0 or abs(change) < threshold * typical:
        return 0
    return 1 if change > 0 else -1


def recent_direction(series, months=6):
    s = series.dropna()
    past = s.asof(s.index[-1] - pd.DateOffset(months=months))
    if pd.isna(past):
        return 0, 0.0
    change = float(s.iloc[-1] - past)
    return direction(change, typical_move(s, months)), change


def forecast_direction(series, fc):
    """Compares the end of the forecast (12 months ahead) with the latest value."""
    change = float(fc["median"].iloc[-1] - series.dropna().iloc[-1])
    return direction(change, typical_move(series.dropna(), 12)), change


def star_rating(target_dir, signal_list, loaded):
    """
    signal_list: [(indicator id, relationship), ...]
    loaded: {indicator id: (indicator settings, result dict)}
    Returns (stars 0-5, table of how each signal voted).
    """
    rows, agree, counted = [], 0, 0
    for sig_id, relationship in signal_list:
        if sig_id not in loaded or loaded[sig_id][1]["series"] is None:
            rows.append(dict(Signal=sig_id, Moved="no data", Implies="-", Agrees="-"))
            continue
        ind, res = loaded[sig_id]
        sig_dir, change = recent_direction(res["series"])
        implied = sig_dir * relationship
        ok = implied == target_dir
        agree += ok
        counted += 1
        arrow = {1: "up", -1: "down", 0: "flat"}
        rows.append(dict(
            Signal=ind["name"],
            Moved=f"{arrow[sig_dir]} ({change:+.{ind['decimals']}f}) over 6 months",
            Implies=arrow[implied],
            Agrees="yes" if ok else "no",
        ))
    stars = round(agree / len(signal_list) * 5) if signal_list else 0
    return stars, pd.DataFrame(rows), agree, counted


# ---------------------------------------------------------------- analytics

def normal_cdf(x):
    from math import erf, sqrt
    return 0.5 * (1 + erf(x / sqrt(2)))


def recession_probability(spread_10y3m):
    """
    Chance of a US recession in 12 months' time, using the yield-curve model
    published by the New York Fed:  P = N(-0.5333 - 0.6330 x spread),
    where spread = 10-year minus 3-month Treasury yield (monthly average)
    and N is the standard normal distribution.
    Returns a monthly Series of probabilities (0-100%), dated 12 months ahead.
    """
    monthly = spread_10y3m.resample("MS").mean().dropna()
    probs = monthly.apply(lambda s: normal_cdf(-0.5333 - 0.6330 * s) * 100)
    probs.index = probs.index + pd.DateOffset(months=12)
    return probs


def percentile_rank(series, years=20):
    """Where the latest reading sits in its own history (0 = lowest, 100 = highest)."""
    s = series.dropna()
    s = s[s.index >= s.index[-1] - pd.DateOffset(years=years)]
    if len(s) < 5:
        return None
    return float((s < s.iloc[-1]).mean() * 100)


def change_over(series, months):
    s = series.dropna()
    past = s.asof(s.index[-1] - pd.DateOffset(months=months))
    return None if pd.isna(past) else float(s.iloc[-1] - past)


def lead_lag(x, y, max_lag=12, years=20):
    """
    Correlation between x and y when x is shifted by -max_lag..+max_lag months.
    Positive lag = x moves first (x leads y by that many months).
    """
    xm = x.resample("MS").mean().dropna()
    ym = y.resample("MS").mean().dropna()
    start = max(xm.index[0], ym.index[0], ym.index[-1] - pd.DateOffset(years=years))
    xm, ym = xm[xm.index >= start], ym[ym.index >= start]
    out = {}
    for lag in range(-max_lag, max_lag + 1):
        shifted = xm.copy()
        shifted.index = shifted.index + pd.DateOffset(months=lag)
        joined = pd.concat([shifted, ym], axis=1, sort=True).dropna()
        out[lag] = joined.iloc[:, 0].corr(joined.iloc[:, 1]) if len(joined) > 24 else np.nan
    return pd.Series(out)


def taylor_rule(inflation, unemployment, neutral_real=0.5, target=2.0,
                infl_weight=0.5, unemp_weight=1.0, natural_unemp=4.5):
    """
    A simple Taylor rule for where the policy rate 'should' be:
      rate = neutral real rate + inflation
             + infl_weight  x (inflation - target)
             + unemp_weight x (natural unemployment - unemployment)
    (The unemployment term stands in for the output gap.)
    """
    joined = pd.concat([inflation.resample("MS").last(),
                        unemployment.resample("MS").last()], axis=1, sort=True).ffill(limit=2).dropna()
    infl, unemp = joined.iloc[:, 0], joined.iloc[:, 1]
    return (neutral_real + infl + infl_weight * (infl - target)
            + unemp_weight * (natural_unemp - unemp))


# ---------------------------------------------------------------- shading regimes

def merge_periods(periods, gap_days=62):
    """Joins periods separated by short gaps so one episode isn't split into many."""
    merged = []
    for start, end in sorted(periods):
        if merged and (start - merged[-1][1]).days <= gap_days:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def regime_periods(rule, loaded, recessions):
    """Turns a SHADES rule from indicators.py into a list of (start, end) dates."""
    kind = rule[0]
    if kind == "recession":
        return recessions.get(rule[1], [])
    series = loaded.get(rule[1], (None, {"series": None}))[1]["series"]
    if series is None or series.empty:
        return []
    if kind in ("rising", "falling"):
        m = series.resample("MS").mean().dropna()
        move = m - m.shift(6)
        flags = (move >= rule[2]) if kind == "rising" else (move <= -rule[2])
        return merge_periods(periods_from_flags(flags.astype(int)), 120)
    if kind in ("below", "above"):
        daily = series.dropna()
        flags = (daily < rule[2]) if kind == "below" else (daily > rule[2])
        return merge_periods(periods_from_flags(flags.astype(int)), 45)
    if kind == "drawdown":
        s = series.dropna()
        drawdown = (s / s.cummax() - 1) * 100
        return merge_periods(periods_from_flags((drawdown <= -rule[2]).astype(int)), 45)
    return []


# ---------------------------------------------------------------- risk appetite

def risk_appetite(components, loaded, years=3):
    """
    Risk-on / risk-off score from 0 (extreme fear) to 100 (extreme greed).
    Each component's latest 1-month average is compared with its last `years` years
    (a z-score), flipped where a rise means less risk appetite (e.g. VIX), then the
    average z-score is turned into 0-100 with the normal distribution.
    Returns (score, table of components).
    """
    rows, zs = [], []
    for ind_id, sign in components:
        if ind_id not in loaded or loaded[ind_id][1]["series"] is None:
            continue
        ind, res = loaded[ind_id]
        s = res["series"].dropna()
        if ind_id in ("sp500",):           # use the gap to the 200-day average for equities
            s = (s / s.rolling(200).mean() - 1) * 100
        m = s.resample("MS").mean().dropna()
        m = m[m.index >= m.index[-1] - pd.DateOffset(years=years)]
        if len(m) < 12 or m.std() == 0:
            continue
        z = float((m.iloc[-1] - m.mean()) / m.std()) * sign
        zs.append(z)
        rows.append(dict(Component=ind["name"] + (" vs 200-day avg" if ind_id == "sp500" else ""),
                         Reading=round(float(m.iloc[-1]), 2), Signal="risk-on" if z > 0.25 else
                         "risk-off" if z < -0.25 else "neutral", Score=round(z, 2)))
    if not zs:
        return None, pd.DataFrame(rows)
    return normal_cdf(float(np.mean(zs))) * 100, pd.DataFrame(rows)


# ---------------------------------------------------------------- recessions

def periods_from_flags(flags):
    """Turns a 0/1 series (1 = in recession) into a list of (start, end) dates."""
    periods, start = [], None
    flags = flags.dropna().astype(int)
    for when, flag in flags.items():
        if flag and start is None:
            start = when
        elif not flag and start is not None:
            periods.append((start, when))
            start = None
    if start is not None:
        periods.append((start, flags.index[-1]))
    return periods


def technical_recessions(gdp_growth, min_quarters=2):
    """UK rule of thumb: 2+ consecutive quarters of negative GDP growth."""
    g = gdp_growth.dropna()
    periods, run = [], []
    for when, value in g.items():
        if value < 0:
            run.append(when)
        else:
            if len(run) >= min_quarters:
                periods.append((run[0], run[-1] + pd.DateOffset(months=3)))
            run = []
    if len(run) >= min_quarters:
        periods.append((run[0], run[-1] + pd.DateOffset(months=3)))
    return periods
