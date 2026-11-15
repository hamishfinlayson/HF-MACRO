"""
pattern_lab.py - the PATTERN LAB (PC version only).

Takes every trade a strategy made and records everything we can measure about the moment it was placed:
the commodity's own chart, the whole market, the calendar, the moon, holidays and data releases, the fear
index and the dollar, what hedge funds were holding, oil and gas inventories, and the WEATHER where each
commodity is grown or used. It also breaks every trade down by WHEN the money was made: overnight or during
the day, which weekday, and (for the last two years) which hour.

Then it asks, for every condition: "were trades placed in this condition better or worse than normal?"

Three rules keep it honest, because testing hundreds of things always finds some by luck:
  1. FIND, CONFIRM, FINAL: patterns are found in the first years, must repeat in the next years, and the
     model adjusted with them is judged on the final years, which the search never touched.
  2. RECURRENCE: for each pattern we count in how many separate years it held.
  3. LUCK CHECK: the trade results are shuffled hundreds of times to see how many "patterns" pure chance
     produces. Only patterns that beat the shuffles are used.

Just for fun and learning. Not financial advice.
"""

import json
import math
import time as _time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import backtest
import workshop

CACHE = Path(__file__).parent / "data" / "cache" / "weather"
UA = {"User-Agent": "HF-Macro/1.3 (personal educational dashboard)"}

# ================================================================= weather

REGIONS = {  # name: (lat, lon, why it matters)
    "Iowa (corn & soy belt)": (41.59, -93.62, "corn and soybean growing"),
    "Kansas (wheat)": (37.69, -97.34, "winter wheat growing"),
    "Houston (oil & gas coast)": (29.76, -95.37, "refineries, hurricanes"),
    "New York (heating demand, traders)": (40.71, -74.01, "heating fuel demand and trader mood"),
    "Chicago (heating demand, grain traders)": (41.88, -87.63, "heating demand and the grain exchange"),
    "Minas Gerais, Brazil (coffee)": (-21.55, -45.43, "coffee growing"),
    "Sao Paulo state, Brazil (sugar)": (-21.18, -47.81, "sugar cane growing"),
    "Ivory Coast (cocoa)": (6.88, -6.45, "cocoa growing"),
    "West Texas (cotton)": (33.58, -101.86, "cotton growing"),
    "Texas Panhandle (cattle)": (35.22, -101.83, "cattle and feed"),
    "London (traders)": (51.51, -0.13, "trader mood"),
}
ASSET_REGION = {"ZC=F": "Iowa (corn & soy belt)", "ZS=F": "Iowa (corn & soy belt)", "ZW=F": "Kansas (wheat)",
                "CL=F": "Houston (oil & gas coast)", "BZ=F": "Houston (oil & gas coast)", "RB=F": "Houston (oil & gas coast)",
                "NG=F": "New York (heating demand, traders)", "HO=F": "Chicago (heating demand, grain traders)",
                "KC=F": "Minas Gerais, Brazil (coffee)", "SB=F": "Sao Paulo state, Brazil (sugar)",
                "CC=F": "Ivory Coast (cocoa)", "CT=F": "West Texas (cotton)", "LE=F": "Texas Panhandle (cattle)"}
TRADER_REGION = "New York (heating demand, traders)"


def fetch_weather(region, start, end):
    """Daily mean temperature, rain and cloud cover from Open-Meteo's free historical archive (saved on disk)."""
    lat, lon, _ = REGIONS[region]
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{region.split(' ')[0].replace(',', '')}_{lat}_{lon}.json"
    old = None
    if p.exists():
        try:
            old = json.loads(p.read_text())
            if _time.time() - p.stat().st_mtime < 7 * 86400:
                return parse_weather(old)
        except Exception:
            old = None
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive",
                         params={"latitude": lat, "longitude": lon, "start_date": str(pd.Timestamp(start).date()),
                                 "end_date": str(pd.Timestamp(end).date()), "timezone": "UTC",
                                 "daily": "temperature_2m_mean,precipitation_sum,cloud_cover_mean"},
                         headers=UA, timeout=30)
        r.raise_for_status()
        data = r.json()
        p.write_text(json.dumps(data))
        return parse_weather(data)
    except Exception:
        if old is not None:
            return parse_weather(old)
        raise


def parse_weather(data):
    d = data.get("daily", {})
    df = pd.DataFrame({"temp": d.get("temperature_2m_mean"), "rain": d.get("precipitation_sum"),
                       "cloud": d.get("cloud_cover_mean")}, index=pd.to_datetime(d.get("time", [])))
    return df.apply(pd.to_numeric, errors="coerce")


def anomaly(s, window=7):
    """How unusual the last `window` days were vs the same time of year in PREVIOUS years only."""
    roll = s.rolling(window, min_periods=max(3, window // 2)).mean()
    doy = roll.index.dayofyear
    out = pd.Series(np.nan, index=roll.index)
    years = sorted(set(roll.index.year))
    for y in years[1:]:
        past = roll[roll.index.year < y]
        if past.empty:
            continue
        clim = past.groupby(past.index.dayofyear).mean()
        clim = clim.reindex(range(1, 367)).interpolate(limit_direction="both").rolling(15, center=True, min_periods=1).mean()
        cur = roll[roll.index.year == y]
        out[cur.index] = cur.values - clim.reindex(cur.index.dayofyear).values
    return out


def load_weather(start, end, progress=None):
    out, errors = {}, []
    for i, reg in enumerate(REGIONS):
        if progress:
            progress(i / len(REGIONS), f"Weather history: {reg}")
        try:
            out[reg] = fetch_weather(reg, start, end)
        except Exception as exc:
            errors.append(f"{reg}: {type(exc).__name__}")
    return out, errors


# ================================================================= the moon, holidays and other calendar facts

NEW_MOON = pd.Timestamp("2000-01-06 18:14")
SYNODIC = 29.530588853


def moon_phase(dates):
    age = ((pd.DatetimeIndex(dates) - NEW_MOON).total_seconds() / 86400) % SYNODIC
    lab = np.select([age < 3.7, age < 11.1, age < 18.5, age < 25.8], ["New moon", "Waxing", "Full moon", "Waning"], "New moon")
    return pd.Series(lab, index=pd.DatetimeIndex(dates))


def us_holidays(start, end):
    from pandas.tseries.holiday import USFederalHolidayCalendar
    return USFederalHolidayCalendar().holidays(start=start, end=end)


def dst_switches(start, end):
    out = []
    for y in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        mar = pd.date_range(f"{y}-03-01", f"{y}-03-31", freq="W-SUN")[1]
        nov = pd.date_range(f"{y}-11-01", f"{y}-11-30", freq="W-SUN")[0]
        out += [mar, nov]
    return pd.DatetimeIndex(out)


# ================================================================= trades

def build_trades(prep, sides, hold=4, fin_long=workshop.LONG_FINANCING_WEEK, cls="Commodities"):
    """Every trade each side made: held for `hold` weeks from a Friday close. Includes the daily path."""
    W, R, f, mc, fr = prep["W"], prep["R"], prep["f"], prep["mc"], prep["fr"]
    clean, ohlc = prep["clean"], prep.get("cohlc") or {}
    close = clean.ffill(limit=5)
    op = ohlc.get("open")
    op = op.reindex(index=close.index, columns=close.columns) if op is not None else None
    rt = backtest.COST_ROUND_TRIP.get(cls, 0.1)
    rows = []
    for side in sides:
        P = backtest.side_positions(side, cls, f, R, mc, {}).reindex(index=W.index, columns=W.columns).fillna(0).loc[fr]
        for b in range(0, len(fr) - hold, hold):
            t, t_end = fr[b], fr[b + hold]
            for a in P.columns[P.loc[t] != 0]:
                d = 1.0 if P.at[t, a] > 0 else -1.0
                path = close[a].loc[t:t_end].dropna()
                if len(path) < 3:
                    continue
                cum = (path / path.iloc[0] - 1) * 100 * d
                gross = cum.iloc[-1]
                cost = rt + (fin_long * hold if d > 0 else backtest.SHORT_FINANCING_WEEK * hold)
                stop_hit = (cum.iloc[1:] <= -8).any()
                stop_ret = cum.iloc[1:][cum.iloc[1:] <= -8].iloc[0] if stop_hit else gross
                days = path.index[1:]
                prev = path.shift(1).loc[days]
                over = intra = 0.0
                wd = {k: 0.0 for k in ("Mon", "Tue", "Wed", "Thu", "Fri")}
                for dd_ in days:
                    pc, c_ = prev[dd_], path[dd_]
                    o_ = op.at[dd_, a] if op is not None and dd_ in op.index else np.nan
                    tot = (c_ / pc - 1) * 100 * d
                    if o_ == o_ and o_ > 0:
                        over += (o_ / pc - 1) * 100 * d
                        intra += (c_ / o_ - 1) * 100 * d
                    name = dd_.strftime("%a")
                    if name in wd:
                        wd[name] += tot
                rows.append(dict(strategy=side, asset=a, date=t, exit=t_end, direction="BUY" if d > 0 else "SHORT",
                                 gross=gross, ret=gross - cost, ret_stop8=stop_ret - cost, worst_point=cum.min(),
                                 best_point=cum.max(), overnight=over, daytime=intra,
                                 **{f"day_{k}": v for k, v in wd.items()}))
    T = pd.DataFrame(rows)
    if not T.empty:
        T["win"] = T["ret"] > 0
    return T


# ================================================================= conditions known at the moment of the trade

CONDITIONS = {}   # key: (label, family, description)


def _c(key, label, family, desc):
    CONDITIONS[key] = (label, family, desc)


for k, l, fam, d in [
    ("vol_level", "Volatility (yearly %)", "Its own chart", "How much the commodity normally moves, last 60 days."),
    ("vol_vs_normal", "Volatility vs its normal", "Its own chart", "Wilder (>1) or calmer (<1) than its usual 2 years."),
    ("stretch", "Stretch above its 50-day average", "Its own chart", "How far above its recent average, in normal moves."),
    ("trend_quality", "Trend smoothness", "Its own chart", "+1 = a perfectly smooth 12-week climb, near 0 = zig-zag."),
    ("near_52w_high", "Price vs 52-week high", "Its own chart", "1 = at its high, 0.8 = 20% below it."),
    ("off_52w_low", "% above 52-week low", "Its own chart", "How far it has bounced off its lowest price of the year."),
    ("last_week", "Last week's move %", "Its own chart", "The week right before the trade."),
    ("last_4w", "Last 4 weeks' move %", "Its own chart", ""),
    ("last_13w", "Last 13 weeks' move %", "Its own chart", ""),
    ("streak", "Up/down weeks in a row", "Its own chart", "+3 = three up weeks in a row."),
    ("rsi", "RSI (14 days)", "Its own chart", "Above 70 = 'overbought', below 30 = 'oversold'."),
    ("ma_gap", "50-day vs 200-day average %", "Its own chart", "The 'golden cross' gap."),
    ("volume_vs_normal", "Trading volume vs normal", "Its own chart", "Last week's volume vs the 50-day average."),
    ("gaps_last_week", "Overnight jumps last week %", "Its own chart", "Sum of the open-vs-previous-close jumps."),
    ("range_last_week", "Daily range last week %", "Its own chart", "Average (high - low) / close."),
    ("mc_median", "Monte Carlo expected move %", "Its own chart", "The simulation's median for the next week."),
    ("mc_up_chance", "Monte Carlo chance of a rise %", "Its own chart", ""),
    ("seasonal", "Same month in past years %", "Its own chart", "How it did in this calendar month before."),
    ("mom_rank", "Momentum rank (0-1)", "Its own chart", "1 = strongest 12-month trend of all commodities."),
    ("breadth", "% of commodities in uptrends", "Whole market", "Share above their 200-day average."),
    ("avg_momentum", "Average commodity trend %", "Whole market", "Average 12-month move of all commodities."),
    ("dispersion", "How different the trends are", "Whole market", "Spread of 12-month moves across commodities."),
    ("market_vol_vs_normal", "Market volatility vs normal", "Whole market", ""),
    ("herding", "How much commodities move together", "Whole market", "Average correlation over the last 13 weeks."),
    ("same_group_picks", "Picks in the same group", "Whole market", "How many of this side's picks share the group."),
    ("strategy_last_13w", "Strategy's own last 13 weeks %", "Whole market", "Was the strategy on a winning or losing run?"),
    ("vix", "VIX (fear index)", "Macro", ""), ("vix_change", "VIX change last week %", "Macro", ""),
    ("dollar_4w", "Dollar index, last 4 weeks %", "Macro", ""), ("stocks_4w", "S&P 500, last 4 weeks %", "Macro", ""),
    ("us2y_4w", "US 2-year yield change, 4 weeks (bp)", "Macro", ""), ("credit_4w", "Junk-bond spread change, 4 weeks (bp)", "Macro", ""),
    ("cot_extreme", "Hedge-fund positioning vs 3 years (z)", "Positioning & inventories", "Speculators' net bet on this commodity."),
    ("cot_change", "Hedge-fund positioning change, 4 weeks", "Positioning & inventories", ""),
    ("inventory_surprise", "Inventory surprise (energy)", "Positioning & inventories", "Stocks vs normal change for the season."),
    ("month", "Month", "Calendar", ""), ("quarter", "Quarter", "Calendar", ""),
    ("week_of_month", "Week of the month", "Calendar", ""), ("season", "Season", "Calendar", ""),
    ("fomc_in_trade", "Fed decision during the trade", "Calendar", ""), ("cpi_in_trade", "US inflation data during the trade", "Calendar", ""),
    ("holiday_in_trade", "US holiday during the trade", "Calendar", ""), ("opex_in_trade", "Options expiry during the trade", "Calendar", ""),
    ("clock_change_in_trade", "Clocks change during the trade", "Calendar", ""), ("year_end", "Over the year end", "Calendar", ""),
    ("election_year", "US election year", "Calendar", ""), ("moon", "Moon phase at entry", "Calendar", ""),
    ("region_temp", "Temperature vs normal where it's grown/used (°C)", "Weather", "Last 7 days, vs the same time in earlier years."),
    ("region_rain", "Rain vs normal where it's grown/used (mm/day)", "Weather", ""),
    ("ny_cloud", "Cloud cover in New York (trader mood) %", "Weather", "Research found sunny days lift markets."),
    ("ny_temp", "New York temperature vs normal (°C)", "Weather", ""),
    ("london_cloud", "Cloud cover in London %", "Weather", ""),
]:
    _c(k, l, fam, d)
CATEGORICAL = {"month", "quarter", "week_of_month", "season", "fomc_in_trade", "cpi_in_trade", "holiday_in_trade",
               "opex_in_trade", "clock_change_in_trade", "year_end", "election_year", "moon", "group", "asset",
               "direction", "strategy"}
CONDITIONS.update({"group": ("Commodity group", "Which commodity", ""), "asset": ("Commodity", "Which commodity", ""),
                   "direction": ("Buy or short", "Which commodity", ""), "strategy": ("Strategy", "Which commodity", "")})


def add_conditions(T, prep, ctx=None, weather=None):
    if T.empty:
        return T
    W, R, f, mc, fr, clean = prep["W"], prep["R"], prep["f"], prep["mc"], prep["fr"], prep["clean"]
    ohlc = prep.get("cohlc") or {}
    daily = clean.ffill(limit=5)
    at = lambda df: df.resample("W-FRI").last().reindex(W.index)
    lr = np.log(daily).diff()
    feats = {}
    feats["vol_level"] = f["vol60"]
    feats["vol_vs_normal"] = f["vol60"] / f["vol60"].rolling(104, min_periods=26).median()
    ma50 = daily.rolling(50, min_periods=40).mean()
    sd = lr.rolling(60, min_periods=40).std()
    feats["stretch"] = at((daily / ma50 - 1) / (sd * np.sqrt(50)))
    feats["trend_quality"] = ((W / W.shift(12) - 1) / (R.abs().rolling(12, min_periods=10).sum() / 100)).clip(-1, 1)
    feats["near_52w_high"] = f["high52"]
    feats["off_52w_low"] = at(daily / daily.rolling(252, min_periods=200).min() - 1) * 100
    feats["last_week"] = R
    feats["last_4w"] = (W / W.shift(4) - 1) * 100
    feats["last_13w"] = (W / W.shift(13) - 1) * 100
    sgn = np.sign(R.fillna(0))
    streak = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for c in R.columns:
        cur, vals = 0.0, []
        for v in sgn[c].values:
            cur = (cur + v if np.sign(cur) == v else v) if v != 0 else 0.0
            vals.append(max(-6, min(6, cur)))
        streak[c] = vals
    feats["streak"] = streak
    dlt = daily.diff()
    up = dlt.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-dlt.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    feats["rsi"] = at(100 - 100 / (1 + up / dn.replace(0, np.nan)))
    feats["ma_gap"] = at(daily.rolling(50, min_periods=40).mean() / daily.rolling(200, min_periods=150).mean() - 1) * 100
    if ohlc.get("volume") is not None:
        v = ohlc["volume"].reindex(index=daily.index, columns=daily.columns).where(lambda x: x > 0)
        feats["volume_vs_normal"] = at(v.rolling(5, min_periods=3).mean() / v.rolling(50, min_periods=30).mean())
    if ohlc.get("open") is not None:
        o = ohlc["open"].reindex(index=daily.index, columns=daily.columns)
        feats["gaps_last_week"] = at(((o / daily.shift(1) - 1) * 100).rolling(5, min_periods=3).sum())
        if ohlc.get("high") is not None and ohlc.get("low") is not None:
            h = ohlc["high"].reindex(index=daily.index, columns=daily.columns)
            lo = ohlc["low"].reindex(index=daily.index, columns=daily.columns)
            feats["range_last_week"] = at(((h - lo) / daily * 100).rolling(5, min_periods=3).mean())
    feats["mc_median"] = mc.get("median_trend")
    feats["mc_up_chance"] = mc.get("pup_trend")
    month_ret = daily.resample("ME").last().pct_change(fill_method=None) * 100
    feats["mom_rank"] = f["mom"].rank(axis=1, pct=True)
    above200 = at(daily > daily.rolling(200, min_periods=150).mean()).astype(float)
    market = {"breadth": above200.mean(axis=1) * 100, "avg_momentum": f["mom"].mean(axis=1),
              "dispersion": f["mom"].std(axis=1)}
    avol = f["vol60"].mean(axis=1)
    market["market_vol_vs_normal"] = avol / avol.rolling(104, min_periods=26).median()
    herd = pd.Series(np.nan, index=R.index)
    for i in range(13, len(R)):
        c = R.iloc[i - 13:i].corr().values
        herd.iloc[i] = np.nanmean(c[np.triu_indices_from(c, 1)])
    market["herding"] = herd
    fac = (ctx or {}).get("factors")
    if fac is not None and not fac.empty:
        fw = fac.resample("W-FRI").last().reindex(W.index, method="ffill")
        if "vix" in fw:
            market["vix"] = fw["vix"]
            market["vix_change"] = fw["vix"].pct_change() * 100
        if "dollar" in fw:
            market["dollar_4w"] = (fw["dollar"] / fw["dollar"].shift(4) - 1) * 100
        if "spx" in fw:
            market["stocks_4w"] = (fw["spx"] / fw["spx"].shift(4) - 1) * 100
        if "us2y" in fw:
            market["us2y_4w"] = (fw["us2y"] - fw["us2y"].shift(4)) * 100
        if "credit" in fw:
            market["credit_4w"] = (fw["credit"] - fw["credit"].shift(4)) * 100
    cot = (ctx or {}).get("cot")
    cot_z = cot_chg = None
    if cot is not None and not cot.empty:
        cw = cot.resample("W-FRI").last().reindex(W.index, method="ffill", limit=2)
        cot_z = (cw - cw.rolling(156, min_periods=52).mean()) / cw.rolling(156, min_periods=52).std()
        cot_chg = cw - cw.shift(4)
    inv = {}
    import signals
    for name, (_, _, assets) in signals.EIA_SERIES.items():
        s = ((ctx or {}).get("eia") or {}).get(name)
        if s is not None:
            sur = -signals.inventory_surprise(s).resample("W-FRI").last().reindex(W.index, method="ffill", limit=1)
            for a in assets:
                inv[a] = sur
    cal_fomc = getattr(signals, "FOMC", pd.DatetimeIndex([]))
    cpi = (ctx or {}).get("cpi")
    cpi = cpi if cpi is not None else pd.DatetimeIndex([])
    hol = us_holidays(fr.min() - pd.Timedelta(days=30), fr.max() + pd.Timedelta(days=60))
    dst = dst_switches(fr.min(), fr.max() + pd.Timedelta(days=60))
    opex = pd.date_range(fr.min() - pd.Timedelta(days=40), fr.max() + pd.Timedelta(days=60), freq="WOM-3FRI")
    ud = pd.DatetimeIndex(sorted(set(T["date"])))
    moon = dict(zip(ud, moon_phase(ud).values))          # one value per date (many trades share a date)
    grp = {c: g for g, cs in workshop.GROUPS.items() for c in cs}
    rec13 = {}
    for side, g in T.groupby("strategy"):
        s = g.groupby("date")["ret"].mean()
        rec13[side] = s.shift(1).rolling(3, min_periods=2).sum()       # last 3 trades = about 13 weeks
    wx_anoms = {}
    if weather:
        for reg, df in weather.items():
            if df is None or df.empty:
                continue
            wx_anoms[reg] = dict(temp=anomaly(df["temp"]), rain=anomaly(df["rain"]), cloud=df["cloud"])
    def look(df, t, a):
        try:
            return float(df.at[t, a])
        except Exception:
            return np.nan
    out = {k: [] for k in list(feats) + list(market) + ["seasonal", "same_group_picks", "strategy_last_13w", "cot_extreme",
                                                         "cot_change", "inventory_surprise", "month", "quarter",
                                                         "week_of_month", "season", "fomc_in_trade", "cpi_in_trade",
                                                         "holiday_in_trade", "opex_in_trade", "clock_change_in_trade",
                                                         "year_end", "election_year", "moon", "group", "region_temp",
                                                         "region_rain", "ny_cloud", "ny_temp", "london_cloud"]}
    picks_by = T.groupby(["strategy", "date"])["asset"].apply(list).to_dict()
    for _, r in T.iterrows():
        t, a, e = r["date"], r["asset"], r["exit"]
        for k, df in feats.items():
            out[k].append(look(df, t, a) if df is not None else np.nan)
        for k, s in market.items():
            out[k].append(float(s.get(t, np.nan)))
        m = (t + pd.Timedelta(days=14)).month
        hist = month_ret[a][(month_ret.index.month == m) & (month_ret.index < t)] if a in month_ret else []
        out["seasonal"].append(float(np.mean(hist)) if len(hist) >= 3 else np.nan)
        picks = picks_by.get((r["strategy"], t), [])
        out["same_group_picks"].append(sum(1 for p in picks if grp.get(p) == grp.get(a)))
        out["strategy_last_13w"].append(float(rec13.get(r["strategy"], pd.Series(dtype=float)).get(t, np.nan)))
        key = {"BZ=F": "CL=F"}.get(a, a)
        out["cot_extreme"].append(look(cot_z, t, key) if cot_z is not None and key in cot_z.columns else np.nan)
        out["cot_change"].append(look(cot_chg, t, key) if cot_chg is not None and key in cot_chg.columns else np.nan)
        out["inventory_surprise"].append(float(inv[a].get(t, np.nan)) if a in inv else np.nan)
        win = lambda dates: bool(((dates > t) & (dates <= e)).any())
        out["month"].append(t.strftime("%m %b"))
        out["quarter"].append(f"Q{(t.month - 1) // 3 + 1}")
        out["week_of_month"].append(f"Week {min(5, (t.day - 1) // 7 + 1)}")
        out["season"].append({12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
                              6: "Summer", 7: "Summer", 8: "Summer"}.get(t.month, "Autumn"))
        out["fomc_in_trade"].append("Yes" if win(cal_fomc) else "No")
        out["cpi_in_trade"].append("Yes" if win(cpi) else "No")
        out["holiday_in_trade"].append("Yes" if win(hol) else "No")
        out["opex_in_trade"].append("Yes" if win(opex) else "No")
        out["clock_change_in_trade"].append("Yes" if win(dst) else "No")
        out["year_end"].append("Yes" if e.year != t.year else "No")
        out["election_year"].append("Yes" if t.year % 4 == 0 else "No")
        out["moon"].append(moon.get(t, "?"))
        out["group"].append(grp.get(a, "Other"))
        reg = ASSET_REGION.get(a)
        def wx(region, var):
            d_ = wx_anoms.get(region, {}).get(var)
            if d_ is None:
                return np.nan
            v_ = d_.loc[:t].dropna()
            return float(v_.iloc[-1]) if len(v_) else np.nan
        out["region_temp"].append(wx(reg, "temp") if reg else np.nan)
        out["region_rain"].append(wx(reg, "rain") if reg else np.nan)
        out["ny_cloud"].append(wx(TRADER_REGION, "cloud"))
        out["ny_temp"].append(wx(TRADER_REGION, "temp"))
        out["london_cloud"].append(wx("London (traders)", "cloud"))
    T = T.copy()
    for k, v in out.items():
        T[k] = v
    return T


# ================================================================= the analysis

def periods(T, find_end, confirm_end):
    find_end, confirm_end = pd.Timestamp(find_end), pd.Timestamp(confirm_end)
    return np.where(T["date"] < find_end, "find", np.where(T["date"] < confirm_end, "confirm", "final"))


def _bins(T, key, find_mask):
    if key in CATEGORICAL:
        lab = T[key].astype(str)
        counts = lab[find_mask].value_counts()
        keep = set(counts[counts >= 12].index)
        return lab.where(lab.isin(keep)), None
    x = T[key].astype(float)
    fx = x[find_mask].dropna()
    if fx.nunique() < 5:
        return pd.Series(np.nan, index=T.index), None
    cuts = np.unique(np.nanpercentile(fx, [0, 20, 40, 60, 80, 100]))
    if len(cuts) < 4:
        return pd.Series(np.nan, index=T.index), None
    edges = cuts.copy()
    edges[0], edges[-1] = -np.inf, np.inf
    names = ["lowest 20%", "low", "middle", "high", "highest 20%"][:len(edges) - 1] if len(edges) == 6 else \
        [f"band {i + 1}" for i in range(len(edges) - 1)]
    lab = pd.cut(x, edges, labels=names).astype(object)
    ranges = {n: (cuts[i], cuts[i + 1]) for i, n in enumerate(names)}
    return lab, ranges


def analyse(T, find_end, confirm_end, n_shuffles=300, threshold=0.5, seed=1):
    """Every condition, every level: results in the find / confirm / final periods, years it held, and luck check."""
    T = T.copy()
    T["period"] = periods(T, find_end, confirm_end)
    find, conf = (T["period"] == "find").values, (T["period"] == "confirm").values
    ret = T["ret"].values.astype(float)
    years = T["date"].dt.year.values
    base = {p: T.loc[T["period"] == p, "ret"].mean() for p in ("find", "confirm", "final")}
    rows, codes = [], []
    for key in CONDITIONS:
        if key not in T or T[key].isna().all():
            continue
        lab, ranges = _bins(T, key, find)
        for name in [n for n in pd.unique(lab.dropna())]:
            m = (lab == name).values
            if m[find].sum() < 12 or m[conf].sum() < 8:
                continue
            row = dict(key=key, condition=CONDITIONS[key][0], family=CONDITIONS[key][1], level=str(name),
                       range=(f"{ranges[name][0]:.2f} to {ranges[name][1]:.2f}" if ranges and name in ranges else str(name)))
            for p, mask in (("find", find), ("confirm", conf), ("final", (T["period"] == "final").values)):
                mm = m & mask
                row[f"n_{p}"] = int(mm.sum())
                row[f"win_{p}"] = float((ret[mm] > 0).mean() * 100) if mm.any() else np.nan
                row[f"avg_{p}"] = float(ret[mm].mean()) if mm.any() else np.nan
                row[f"edge_{p}"] = row[f"avg_{p}"] - base[p] if mm.any() else np.nan
            held = tot = 0
            for y in np.unique(years):
                ym = years == y
                if (m & ym).sum() >= 3 and (~m & ym).sum() >= 3:
                    tot += 1
                    better = ret[m & ym].mean() > ret[ym].mean()
                    held += better if row["edge_find"] > 0 else (not better)
            row["years_held"], row["years_tested"] = held, tot
            rows.append(row)
            codes.append(m)
    P = pd.DataFrame(rows)
    if P.empty:
        return P, dict(found=0, luck_mean=0, luck_95=0), base
    better = (P["edge_find"] > threshold) & (P["edge_confirm"] > threshold)
    worse = (P["edge_find"] < -threshold) & (P["edge_confirm"] < -threshold)
    P["verdict"] = np.where(better, "✅ Better in find AND confirm", np.where(worse, "❌ Worse in find AND confirm", "mixed / noise"))
    # luck check: shuffle results within each period, count how many 'patterns' appear by chance
    M = np.array(codes, dtype=bool)
    rng = np.random.default_rng(seed)
    obs_ef, obs_ec = P["edge_find"].values, P["edge_confirm"].values
    beats = np.zeros(len(P))
    luck_counts = []
    idx_f, idx_c = np.where(find)[0], np.where(conf)[0]
    for _ in range(n_shuffles):
        r = ret.copy()
        r[idx_f] = rng.permutation(r[idx_f])
        r[idx_c] = rng.permutation(r[idx_c])
        sf = (M[:, idx_f] @ r[idx_f]) / np.maximum(M[:, idx_f].sum(axis=1), 1) - r[idx_f].mean()
        sc = (M[:, idx_c] @ r[idx_c]) / np.maximum(M[:, idx_c].sum(axis=1), 1) - r[idx_c].mean()
        luck_counts.append(int((((sf > threshold) & (sc > threshold)) | ((sf < -threshold) & (sc < -threshold))).sum()))
        same = np.sign(obs_ef)
        beats += ((sf * same >= np.abs(obs_ef)) & (sc * same >= obs_ec * same)).astype(float)
    P["luck_chance"] = beats / n_shuffles
    P["held_final"] = np.where(P["edge_final"].isna(), "no final trades",
                               np.where(np.sign(P["edge_final"]) == np.sign(P["edge_find"]), "✅ held", "❌ flipped"))
    P["beats_luck"] = (P["verdict"] != "mixed / noise") & (P["luck_chance"] < 0.05)
    P["sentence"] = [sentence(r) for _, r in P.iterrows()]
    luck = dict(found=int((P["verdict"] != "mixed / noise").sum()), luck_mean=float(np.mean(luck_counts)),
                luck_95=float(np.percentile(luck_counts, 95)), beat=int(P["beats_luck"].sum()))
    return P.sort_values(["beats_luck", "edge_confirm"], ascending=[False, False]), luck, base


def sentence(r):
    good = r["edge_find"] > 0
    lvl = r["level"] if r["key"] in CATEGORICAL else f"{r['level']} ({r['range']})"
    return (f"{'Before WINS' if good else 'Before LOSSES'}: {r['condition']} = {lvl}. Trades did "
            f"{r['edge_find']:+.2f} pts in find and {r['edge_confirm']:+.2f} in confirm vs normal; "
            f"held in {r['years_held']} of {r['years_tested']} years; {r['n_find'] + r['n_confirm']} trades.")


# ================================================================= when is the money made?

def timing(T):
    """Overnight vs daytime, and each weekday's share of the result, for winners and losers."""
    if T.empty:
        return pd.DataFrame()
    cols = ["overnight", "daytime", "day_Mon", "day_Tue", "day_Wed", "day_Thu", "day_Fri"]
    g = T.assign(outcome=np.where(T["win"], "Winning trades", "Losing trades"))
    out = g.groupby("outcome")[cols].mean()
    out.loc["All trades"] = T[cols].mean()
    return out.rename(columns={"overnight": "Overnight (close → open) %", "daytime": "During the day (open → close) %",
                               "day_Mon": "Mondays %", "day_Tue": "Tuesdays %", "day_Wed": "Wednesdays %",
                               "day_Thu": "Thursdays %", "day_Fri": "Fridays %"})


def load_hourly(tickers):
    import yfinance as yf
    frame = yf.download(list(tickers), period="729d", interval="1h", auto_adjust=True, progress=False, threads=True)
    if frame is None or frame.empty:
        raise ValueError("no hourly prices")
    close = frame.xs("Close", axis=1, level=0) if isinstance(frame.columns, pd.MultiIndex) else frame[["Close"]]
    idx = pd.DatetimeIndex(close.index)
    close.index = idx.tz_convert("America/New_York").tz_localize(None) if idx.tz is not None else idx
    return close


def hourly_profile(T, hourly):
    """For trades in the last two years: average move by hour of day (New York time) in the trade's direction."""
    rows = []
    if hourly is None or hourly.empty:
        return pd.DataFrame()
    hr = hourly.pct_change(fill_method=None) * 100
    for _, r in T[T["date"] >= hourly.index.min()].iterrows():
        a = r["asset"]
        if a not in hr:
            continue
        seg = hr[a].loc[r["date"] + pd.Timedelta(hours=18): r["exit"] + pd.Timedelta(hours=17)].dropna()
        d = 1 if r["direction"] == "BUY" else -1
        for ts, v in seg.items():
            rows.append(dict(hour=ts.hour, weekday=ts.strftime("%a"), move=v * d, win=r["win"]))
    if not rows:
        return pd.DataFrame()
    H = pd.DataFrame(rows)
    tab = H.pivot_table(index="hour", columns="win", values="move", aggfunc="mean").rename(
        columns={True: "Winning trades %", False: "Losing trades %"})
    tab["All trades %"] = H.groupby("hour")["move"].mean()
    tab["Hours sampled"] = H.groupby("hour").size()
    tab.index = [f"{h:02d}:00" for h in tab.index]
    return tab


# ================================================================= does adjusting the model help? (final years only)

def pattern_score(T, P, find_end, use="beats_luck"):
    """Each trade's score: the sum of the (find + confirm) edges of every pattern it matched at entry."""
    find = (periods(T, find_end, find_end) == "find")
    sel = P[P[use]] if use in P else P.iloc[0:0]
    score = np.zeros(len(T))
    hits_good, hits_bad = np.zeros(len(T), int), np.zeros(len(T), int)
    cache = {}
    for _, r in sel.iterrows():
        if r["key"] not in cache:
            cache[r["key"]] = _bins(T, r["key"], find)[0].astype(str).values
        m = cache[r["key"]] == str(r["level"])
        e = (r["edge_find"] + r["edge_confirm"]) / 2
        score[m] += e
        (hits_good if e > 0 else hits_bad)[m] += 1
    return score, hits_good, hits_bad


def model_test(T, P, find_end, confirm_end, cut=0.3):
    """The strategy as it was, vs adjusted with the patterns: each trade gets a score from the patterns it matched;
    the worst-scoring 30% are skipped and the best-scoring 30% get 1.5x the money. The cut-offs are set on the
    CONFIRM years; everything is judged ONLY on the FINAL years that the pattern search never saw."""
    T = T.copy()
    T["period"] = periods(T, find_end, confirm_end)
    out = []
    if P.empty:
        return pd.DataFrame()
    P = P.assign(verdict_any=P["verdict"] != "mixed / noise")
    fm = (T["period"] == "final").values
    cm = (T["period"] == "confirm").values
    F = T[fm]
    def row(name, rets, mask, w, rules=""):
        r, ww = rets[mask], w[mask]
        if not len(r):
            return
        d = F["date"].values[mask]
        blocks = pd.Series(r * ww, index=d).groupby(level=0).sum() / pd.Series(ww, index=d).groupby(level=0).sum()
        blocks = blocks.reindex(sorted(set(F["date"]))).fillna(0)
        curve = (1 + blocks / 100).cumprod()
        yrs = max(0.25, (F["date"].max() - F["date"].min()).days / 365.25)
        out.append(dict(version=name, rules=rules, trades=int(mask.sum()), win_rate=float((r > 0).mean() * 100),
                        avg_trade=float(np.average(r, weights=ww)), per_year=float((curve.iloc[-1] ** (1 / yrs) - 1) * 100),
                        worst_drop=float(((curve / curve.cummax()) - 1).min() * 100), big_losses=int((r < -8).sum())))
    ones = np.ones(fm.sum())
    row("As it was", F["ret"].values, np.ones(fm.sum(), bool), ones)
    row("+ 8% stop-loss (checked at each day's close)", F["ret_stop8"].values, np.ones(fm.sum(), bool), ones)
    for use, title in (("beats_luck", "patterns that beat the luck check"), ("verdict_any", "all repeating patterns")):
        score, good, bad = pattern_score(T, P, find_end, use)
        n_rules = int(P[use].sum())
        if not cm.any():
            continue
        lo, hi = np.nanpercentile(score[cm], [cut * 100, 100 - cut * 100])
        keep = score[fm] > lo
        w = np.where(score[fm] >= hi, 1.5, 1.0)
        row(f"Skip the worst-scoring {int(cut * 100)}% ({title})", F["ret"].values, keep, ones, f"{n_rules} patterns")
        row(f"Skip worst + 1.5x money on best-scoring {int(cut * 100)}% ({title})", F["ret"].values, keep, w, f"{n_rules} patterns")
        row(f"Only the best-scoring {int(cut * 100)}% ({title})", F["ret"].values, score[fm] >= hi, ones, f"{n_rules} patterns")
    return pd.DataFrame(out)


# ================================================================= one call does everything

def prepare(prices, ohlc, start, end, proxies=None, n_sims=400, progress=None):
    clean, cohlc, fixes = workshop.clean_rolls(prices.dropna(axis=1, how="all"), ohlc, proxies)
    W, R, F = backtest.weekly_frames(clean)
    fr = W.index[(W.index >= pd.Timestamp(start)) & (W.index <= pd.Timestamp(end))]
    f = backtest.features(clean, W)
    parts = {}
    for i, c in enumerate(clean.columns):
        if progress:
            progress(0.3 * i / len(clean.columns), f"Monte Carlo through history: {c}")
        m = backtest.mc_at_dates(clean[c], fr, 5, n_sims=n_sims, seed=i)
        if not m.empty:
            parts[c] = m
    mc = {k: pd.DataFrame({c: m[k] for c, m in parts.items() if k in m}).reindex(index=W.index, columns=W.columns)
          for k in next(iter(parts.values())).columns} if parts else {}
    return dict(clean=clean, cohlc=cohlc, fixes=fixes, W=W, R=R, F=F, fr=fr, f=f, mc=mc)


def run(prices, ohlc, start, end, find_end, confirm_end, sides, hold=4, proxies=None, ctx=None, weather=None,
        hourly=None, progress=None, n_shuffles=300):
    prep = prepare(prices, ohlc, start, end, proxies, progress=progress)
    if progress:
        progress(0.35, "Collecting every trade...")
    T = build_trades(prep, sides, hold)
    if T.empty:
        return None
    if progress:
        progress(0.5, f"Recording {len(CONDITIONS)} conditions for {len(T)} trades...")
    T = add_conditions(T, prep, ctx, weather)
    if progress:
        progress(0.75, f"Testing every condition and shuffling {n_shuffles} times for the luck check...")
    P, luck, base = analyse(T, find_end, confirm_end, n_shuffles=n_shuffles)
    MT = model_test(T, P, find_end, confirm_end) if not P.empty else pd.DataFrame()
    if progress:
        progress(1.0, "Done")
    return dict(trades=T, patterns=P, luck=luck, base=base, model=MT, timing=timing(T),
                hourly=hourly_profile(T, hourly) if hourly is not None else pd.DataFrame(), fixes=len(prep["fixes"]))


# ================================================================= v29: each commodity's own "personality"

PERSONAL_SKIP = {"same_group_picks", "strategy_last_13w", "asset", "group", "direction", "strategy"}


def weekly_cases(prep):
    """Every commodity, every week: bought at a Friday close and sold at the next one. The last Friday is included
    with no result yet, so today's conditions can be scored."""
    W, fr = prep["W"], prep["fr"]
    Wf = W.loc[fr]
    rows = []
    for a in Wf.columns:
        s = Wf[a]
        for i, t in enumerate(fr):
            if pd.isna(s.iloc[i]):
                continue
            nxt = s.iloc[i + 1] if i + 1 < len(fr) else np.nan
            ret = (nxt / s.iloc[i] - 1) * 100 if nxt == nxt else np.nan
            rows.append(dict(strategy="Every week", asset=a, date=t, exit=t + pd.Timedelta(days=7), direction="BUY",
                             gross=ret, ret=ret))
    return pd.DataFrame(rows)


def personality(prep, ctx=None, weather=None, find_end="2022-01-01", confirm_end="2024-01-01", n_shuffles=200,
                progress=None, threshold=0.25):
    """
    Looks for patterns in each commodity ON ITS OWN, using every week since the start (about 500 per commodity).
    Patterns are found in the find years, must repeat in the confirm years, and are checked for luck. Each
    commodity-week then gets a score: the sum of the edges of the patterns that were switched on.
    """
    T = weekly_cases(prep)
    if T.empty:
        return None
    if progress:
        progress(0.86, f"Recording conditions for {len(T):,} commodity-weeks...")
    T = add_conditions(T, prep, ctx, weather)
    for k in PERSONAL_SKIP & set(T.columns):
        if k not in ("asset", "strategy", "direction"):
            T[k] = np.nan
    fe = pd.Timestamp(find_end)
    scores = pd.DataFrame(0.0, index=prep["fr"], columns=prep["W"].columns)
    results, summ, now = {}, [], {}
    keys_saved = dict(CONDITIONS)
    for k in PERSONAL_SKIP:
        CONDITIONS.pop(k, None)
    try:
        assets = sorted(T["asset"].unique())
        for n, a in enumerate(assets):
            if progress:
                progress(0.88 + 0.1 * n / len(assets), f"Looking for {a}'s own patterns (and the luck check)...")
            ga = T[T["asset"] == a].reset_index(drop=True)
            g = ga[ga["ret"].notna()].reset_index(drop=True)
            if len(g) < 150:
                continue
            P, luck, base = analyse(g, find_end, confirm_end, n_shuffles=n_shuffles, threshold=threshold)
            if P.empty:
                continue
            results[a] = (P, luck)
            sel = P[P["beats_luck"]]
            fmask = (ga["date"] < fe).values
            sc = np.zeros(len(ga))
            last = len(ga) - 1
            good, bad = [], []
            cache = {}
            for _, r in sel.iterrows():
                if r["key"] not in cache:
                    cache[r["key"]] = _bins(ga, r["key"], fmask)[0].astype(str).values
                m = cache[r["key"]] == str(r["level"])
                e = (r["edge_find"] + r["edge_confirm"]) / 2
                sc[m] += e
                if m[last] and ga["ret"].isna().iloc[last]:
                    (good if e > 0 else bad).append(dict(text=_short(r), edge=e, held=r["held_final"]))
            scores.loc[ga["date"].values, a] = sc
            now[a] = dict(score=float(sc[last]) if ga["ret"].isna().iloc[last] else np.nan,
                          good=sorted(good, key=lambda x: -x["edge"]), bad=sorted(bad, key=lambda x: x["edge"]))
            held = sel["held_final"].eq("✅ held").sum()
            summ.append({"Commodity": a, "Weeks tested": len(g), "Patterns found": luck["found"],
                         "Luck alone would give": round(luck["luck_mean"]), "More than luck?":
                         "✅ yes" if luck["found"] > luck["luck_95"] else ("🟡 a little" if luck["found"] > luck["luck_mean"] else "❌ no"),
                         "Passed the luck check": int(len(sel)), "Still held 2024 →": int(held),
                         "Held %": round(held / len(sel) * 100) if len(sel) else np.nan})
    finally:
        CONDITIONS.clear()
        CONDITIONS.update(keys_saved)
    return dict(results=results, summary=pd.DataFrame(summ), scores=scores, now=now, find_end=fe,
                confirm_end=pd.Timestamp(confirm_end))


def _short(r):
    lvl = r["level"] if r["key"] in CATEGORICAL else f"{r['level']} ({r['range']})"
    return f"{r['condition']} = {lvl}"
