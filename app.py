"""
app.py - HF Macro (Hamish Finlayson's macro terminal). Run it with:  py -m streamlit run app.py

Navigation lives in the address bar, e.g.
  ?p=UK          -> the UK page
  ?p=UK&t=UKCPI  -> the full-screen chart for UK CPI
so any view can be bookmarked or shared, and the browser back button works.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from forecast import (ar_forecast, change_over, forecast_direction, lead_lag, macro_momentum,
                      percentile_rank,
                      periods_from_flags, recession_probability, regime_periods, risk_appetite,
                      star_rating, taylor_rule, technical_recessions)
from indicators import (CALENDAR_RELEASES, COMMODITY_MONITOR, COUNTRIES, DEFAULT_WATCHLIST,
                        EQUITY_MONITOR, EVENTS, FX_TABLE_CURRENCIES, HEATMAP_CURRENCIES,
                        IMF_INDICATORS, INDICATORS, MAJOR_ECONOMIES, NEWS_FEEDS, NEWS_QUERIES,
                        NEWS_TOPICS, RECESSIONS, REFERENCE_LINES, RISK_COMPONENTS, SHADES, SIGNALS,
                        YIELD_CURVES, RESTRICTED_IDS, TV_EQUITY_TABS, TV_COMMODITY_TABS,
                        TV_CHART_CHOICES, COMMODITY_MONTHLY)
from glossary import ABOUT, TERMS
from sources import (SOURCE_NAMES, compute_derived, currency_strength, fetch_calendar, fetch_fred,
                     fetch_fx_history, fetch_fx_table, fetch_imf, fetch_imf_countries, fetch_news,
                     fetch_news_search, fetch_policy_rates, fetch_yahoo, fetch_yahoo_batch,
                     get_fred_key, load_curve, load_indicator, load_pmi, load_us_recession_flags,
                     monthly_performance, performance_table, public_mode, source_url)

APP_NAME = "HF Macro"
HERE = Path(__file__).parent
PMI_FILE = HERE / "data" / "pmi.csv"
WATCHLIST_FILE = HERE / "data" / "watchlist.json"

PAGES = {
    "HOME": ("Home", "Recession and risk gauges, watchlist, scorecard, calendar, headlines"),
    "US": ("US", "US economy: jobs, inflation, growth, consumer, housing, trade, credit, rates"),
    "UK": ("UK", "UK economy: growth, inflation, labour, consumer, trade, rates"),
    "EA": ("Euro area", "Euro area inflation, unemployment, ECB rate, Euro Stoxx 50"),
    "MKT": ("Markets", "Key equity indices, volatility and commodities with full history"),
    "WEI": ("World equities", "23 global stock indices: 1D / 1W / 1M / YTD / 1Y performance"),
    "CMDTY": ("Commodities", "Energy, metals and agriculture futures performance"),
    "FX": ("FX", "GBP snapshot, currency strength heatmap and 20 currency pairs"),
    "GLOB": ("Global", "IMF world map, major economies and central bank rates board"),
    "CTRY": ("Country", "One-page profile for 20 economies"),
    "NEWS": ("News", "FX snapshot, IMF growth and filtered headlines, plus a news search"),
    "CRV": ("Curves", "Yield curves and the yield-curve recession signal"),
    "CAL": ("Calendar", "Upcoming US data releases and UK calendar links"),
    "LAB": ("Lab", "Correlation and lead/lag explorer, Taylor rule"),
    "PMI": ("PMI", "Purchasing managers' indices (kept on your PC)"),
    "HELP": ("Help", "Every command and ticker, plus tips"),
}
TAPE = ["ftse100", "ftse250", "sp500", "nasdaq", "stoxx50", "dax", "nikkei", "vix", "brent", "gold",
        "copper", "gbpusd", "gbpeur", "eurusd", "usdjpy", "dxy", "us_10y", "uk_10y", "uk_bankrate",
        "us_fedfunds", "ecb_dfr", "uk_cpi", "us_cpi", "ea_hicp"]
PERIODS = {"1Y": 1, "2Y": 2, "5Y": 5, "10Y": 10, "20Y": 20, "50Y": 50, "MAX": None}
MOUSE = {"Zoom": "zoom", "Pan": "pan", "Line": "drawline", "Draw": "drawopenpath",
         "Box": "drawrect", "Circle": "drawcircle"}

LOGO = HERE / "assets" / "logo.png"
st.set_page_config(page_title=APP_NAME, page_icon=str(LOGO) if LOGO.exists() else "📈",
                   layout="wide", initial_sidebar_state="collapsed")

# Online (public) version hides series whose owners don't allow free republishing.
PUBLIC = public_mode()
ACTIVE = [i for i in INDICATORS if not (PUBLIC and i["id"] in RESTRICTED_IDS)]
ui.inject_css()

# ================================================================= load all data

with st.spinner("Loading market and economic data (first load takes a minute)..."):
    LOADED = {ind["id"]: (ind, load_indicator(ind)) for ind in ACTIVE}
    for ind in ACTIVE:                                 # calculated indicators go second
        if ind["source"] == "derived":
            LOADED[ind["id"]] = (ind, compute_derived(ind, LOADED))
    BY_TICKER = {ind["ticker"]: ind["id"] for ind in ACTIVE}

    us_flags = load_us_recession_flags()
    REC = {"US": periods_from_flags(us_flags) if us_flags is not None else []}
    uk_gdp = LOADED[RECESSIONS["UK"]["from_id"]][1]["series"]
    REC["UK"] = technical_recessions(uk_gdp) if uk_gdp is not None else []
    SHADE_PERIODS = {name: (regime_periods(rule, LOADED, REC), colour)
                     for name, (rule, colour) in SHADES.items()
                     if rule[0] == "recession" or rule[1] in LOADED}

    FORECASTS = {}
    for ind_id, (ind, res) in LOADED.items():
        if not ind.get("forecast") or res["series"] is None or ind_id not in SIGNALS:
            continue
        try:
            fc = ar_forecast(res["series"])
            fc_dir, fc_change = forecast_direction(res["series"], fc)
            stars, table, agree, counted = star_rating(fc_dir, SIGNALS[ind_id], LOADED)
            FORECASTS[ind_id] = dict(fc=fc, dir=fc_dir, change=fc_change, stars=stars,
                                     table=table, agree=agree, counted=counted, error=None)
        except Exception as exc:
            FORECASTS[ind_id] = dict(error=str(exc))

SOURCE_HEALTH = {}
for _ind, _res in LOADED.values():
    label = {"fred": "FRED", "fred_ratio": "FRED", "ons": "ONS", "boe": "BOE", "ecb": "ECB",
             "yahoo": "YAHOO", "derived": None}.get(_ind["source"])
    if label:
        SOURCE_HEALTH[label] = SOURCE_HEALTH.get(label, False) or _res["error"] is None


def ids_for(region, group=None):
    return [i["id"] for i in ACTIVE
            if i["region"] == region and (group is None or i["group"] == group)]


def groups_for(region):
    seen = []
    for i in ACTIVE:
        if i["region"] == region and i["group"] not in seen:
            seen.append(i["group"])
    return seen


# ================================================================= watchlist

def load_watchlist():
    try:
        return [i for i in json.loads(WATCHLIST_FILE.read_text()) if i in LOADED]
    except Exception:
        return list(DEFAULT_WATCHLIST)


def save_watchlist(items):
    try:
        WATCHLIST_FILE.write_text(json.dumps(items))
    except Exception:
        pass


# ================================================================= navigation

qp = st.query_params
PAGE = qp.get("p", "HOME") if qp.get("p", "HOME") in PAGES else "HOME"
TICKER = qp.get("t") if qp.get("t") in BY_TICKER else None

COMMANDS = {f"{code:<6} {label.upper()} — page": ("page", code) for code, (label, _) in PAGES.items()}
COMMANDS.update({f"{ind['ticker']:<9} {ind['name']} [{ind['region']}]": ("ticker", ind["ticker"])
                 for ind in ACTIVE})


def go_to(page=None, ticker=None):
    st.query_params.clear()
    st.query_params["p"] = page or PAGE
    if ticker:
        st.query_params["t"] = ticker
    st.session_state.nav = None if ticker else (page or PAGE)


ui.DATA.update(loaded=LOADED, forecasts=FORECASTS, go_to=go_to)


def on_command():
    choice = st.session_state.get("cmd")
    if choice:
        kind, code = COMMANDS[choice]
        if kind == "page":
            go_to(page=code)
        else:
            go_to(ticker=code)
        st.session_state.cmd = None


def on_nav():
    if st.session_state.get("nav"):
        go_to(page=st.session_state.nav)


if "nav" not in st.session_state:
    st.session_state.nav = None if TICKER else PAGE

c_brand, c_cmd, c_clock = st.columns([1.25, 3.4, 1.1])
c_brand.markdown("<div class='brand'><span class='logo'>HF</span>MACRO<small>HFM &lt;GO&gt;</small></div>",
                 unsafe_allow_html=True)
c_cmd.selectbox("Command", list(COMMANDS), index=None, key="cmd", on_change=on_command,
                placeholder="▸ ENTER COMMAND · ticker (UKCPI, GBPUSD, BRENT), page (WEI, CTRY, NEWS) "
                            "or keyword (inflation, gilt, yen)",
                label_visibility="collapsed")
c_clock.markdown(f"<div class='clock'><span class='live'>● LIVE</span> &nbsp;"
                 f"{datetime.now():%a %d %b %Y %H:%M}".upper() + "</div>", unsafe_allow_html=True)
ui.ticker_tape(TAPE)
st.segmented_control("Pages", list(PAGES), format_func=lambda c: PAGES[c][0].upper(), key="nav",
                     on_change=on_nav, label_visibility="collapsed")
if not get_fred_key():
    st.warning("No FRED key found, so US data won't load. Add it to .streamlit/secrets.toml.")


# ================================================================= shared pieces

def chart_panel(ind_id, height=220):
    """Compact chart. Drag to zoom, double-click to reset, OPEN for the full toolkit."""
    ind, res = LOADED[ind_id]
    with st.container(border=True):
        f = FORECASTS.get(ind_id)
        conf = ui.conf_html(f["stars"]) if f and not f.get("error") else ""
        left, right = st.columns([5, 1.1])
        if res["error"]:
            left.markdown(f"<div class='pt'><b>{ui.escape(ind['name'])}</b><span>{ind['ticker']}</span></div>"
                          f"<div class='err'>{ui.escape(res['error'])}</div>", unsafe_allow_html=True)
            return
        change = None if res["previous"] is None else res["latest"] - res["previous"]
        left.markdown(
            f"<div class='pt'><b>{ui.escape(ind['name'])}{ui.info(ind_id, ind['name'])}</b>"
            f"<span>{ind['ticker']}</span></div>"
            f"<span class='hv'>{ui.fmt(res['latest'], ind)}</span> {ui.change_html(ind, change)} "
            f"<span class='hs'>{ui.date_label(ind, res['latest_date'])}</span> &nbsp;{conf}"
            f"{ui.info('confidence', 'Confidence') if conf else ''}",
            unsafe_allow_html=True)
        right.button("OPEN ↗", key=f"open_{ind_id}", on_click=go_to,
                     kwargs=dict(ticker=ind["ticker"]), width="stretch")
        default_shade = "UK recessions" if ind["region"] == "UK" else "US recessions" \
            if ind["region"] in ("US", "Markets") else None
        shades = [(default_shade, *SHADE_PERIODS[default_shade])] if default_shade else []
        fc = f["fc"] if f and not f.get("error") else None
        fig = ui.build_figure(ind, ui.window(res["series"], 10), height=height, forecast=fc,
                              shades=shades, ref_lines=REFERENCE_LINES.get(ind_id, []))
        st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"panel_{ind_id}")


def panel_grid(ids, columns=2):
    for start in range(0, len(ids), columns):
        cols = st.columns(columns, gap="small")
        for col, ind_id in zip(cols, ids[start:start + columns]):
            with col:
                chart_panel(ind_id)


def region_page(region, intro):
    st.caption(intro + " Click any card or OPEN ↗ for the full-screen chart. Drag across a chart "
               "to zoom, double-click to reset.")
    ui.card_grid(ids_for(region), columns=6)
    for n, group in enumerate(groups_for(region), start=1):
        ui.section(group, code=f"{n:02d}")
        panel_grid(ids_for(region, group))


def gauge(value, key, steps, height=170, suffix="%"):
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(suffix=suffix, font=dict(size=30, color=ui.TEXT, family=ui.MONO)),
        gauge=dict(axis=dict(range=[0, 100], tickcolor=ui.DIM, tickfont=dict(size=9)),
                   bar=dict(color=ui.ACCENT, thickness=0.25), bgcolor=ui.PANEL_2, borderwidth=0,
                   steps=[dict(range=r, color=c) for r, c in steps])))
    fig.update_layout(height=height, margin=dict(l=34, r=34, t=14, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=ui.MONO))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def recession_gauge(key="gauge_rec"):
    ind, res = LOADED["us_3m10y"]
    if res["series"] is None:
        st.caption("Needs the 3m10y Treasury spread (FRED).")
        return
    probs = recession_probability(res["series"])
    gauge(float(probs.iloc[-1]), key, [([0, 30], "#0E2016"), ([30, 50], "#262010"), ([50, 100], "#2A1012")])
    st.caption(f"P(US recession by {probs.index[-1]:%b %Y}) · NY Fed yield-curve model · "
               f"10y-3m = {res['latest']:+.2f}%")


def momentum_gauge(key="gauge_mom"):
    items = [LOADED[i] for i in LOADED if LOADED[i][0]["region"] in ("US", "UK", "EA")]
    score, better, counted = macro_momentum(items)
    if score is None:
        st.caption("Not enough data yet.")
        return
    gauge(score, key, [([0, 40], "#2A1012"), ([40, 60], "#16191E"), ([60, 100], "#0E2016")], suffix="")
    st.caption(f"{better} of {counted} indicators improved over 3 months · above 50 = more improving "
               "than worsening")


def risk_meter(key="gauge_risk", table=False):
    score, comps = risk_appetite(RISK_COMPONENTS, LOADED)
    if score is None:
        st.caption("Needs VIX, credit spreads, copper/gold, dollar and S&P 500 data.")
        return
    gauge(score, key, [([0, 30], "#2A1012"), ([30, 45], "#221A10"), ([45, 55], "#16191E"),
                       ([55, 70], "#13200F"), ([70, 100], "#0E2016")], suffix="")
    mood = ("EXTREME RISK-OFF" if score < 20 else "RISK-OFF" if score < 45 else "NEUTRAL"
            if score <= 55 else "RISK-ON" if score <= 80 else "EXTREME RISK-ON")
    st.caption(f"{mood} · 0 = fear, 100 = greed · VIX, HY spreads, copper/gold, dollar, S&P vs 200d")
    if table:
        st.dataframe(comps, hide_index=True, width="stretch")


def fx_snapshot():
    try:
        table, as_of = fetch_fx_table(tuple(FX_TABLE_CURRENCIES))
        show = table[["Currency", "1 GBP buys", "1 day %", "1 month %"]]
        st.dataframe(show.style.format({"1 GBP buys": "{:.4f}", "1 day %": "{:+.2f}%",
                                        "1 month %": "{:+.2f}%"})
                     .map(lambda v: f"color: {ui.UP if v > 0 else ui.DOWN}" if isinstance(v, float)
                          and not pd.isna(v) else "", subset=["1 day %", "1 month %"]),
                     hide_index=True, width="stretch")
        st.caption(f"ECB reference rates via Frankfurter · {as_of:%d %b %Y}")
    except Exception as exc:
        st.caption(f"FX rates unavailable right now ({type(exc).__name__}).")


def strength_heatmap():
    base = st.segmented_control("Measured against", ["USD", "GBP", "EUR"], default="USD",
                                key="heat_base")
    try:
        rates = fetch_fx_history(base or "USD", tuple(HEATMAP_CURRENCIES))
        table = currency_strength(rates).reset_index().rename(columns={"index": "Currency"})
        table = table.sort_values("1M", ascending=False)
        ui.heat_table(table, "Currency", ["1D", "1W", "1M", "3M", "YTD", "1Y"], scale=4)
        st.caption(f"% change in each currency's value against the {base or 'USD'} "
                   "(green = stronger). ECB reference rates via Frankfurter.")
    except Exception as exc:
        st.caption(f"Currency history unavailable right now ({type(exc).__name__}).")


EMPTY_NEWS = pd.DataFrame(columns=["time", "source", "headline", "link", "topics"])


def load_news():
    try:
        return fetch_news(tuple(NEWS_FEEDS), tuple((k, tuple(v)) for k, v in NEWS_TOPICS.items()))
    except Exception as exc:
        reason = "the news library isn't installed (run the pip install step)" \
            if isinstance(exc, ImportError) else type(exc).__name__
        return EMPTY_NEWS, [f"all feeds ({reason})"]


def search_news(query):
    try:
        return fetch_news_search(query)
    except Exception:
        return None


def calendar_rows(df, limit=None):
    if df is None or df.empty:
        st.caption("No upcoming releases found.")
        return
    df = df.head(limit) if limit else df
    st.markdown("".join(
        f"<div class='nr'><span class='t' style='min-width:84px;color:{ui.ACCENT}'>"
        + f"{r['date']:%a %d %b}".upper() + f"</span><span style='font-size:.8rem'>"
        f"{ui.escape(r['release_name'])}</span></div>" for _, r in df.iterrows()),
        unsafe_allow_html=True)


def load_calendar():
    key = get_fred_key()
    if not key:
        return None, "Needs your FRED key."
    try:
        cal = fetch_calendar(key, tuple(CALENDAR_RELEASES))
        if cal is not None and not cal.empty:
            cal = cal[~cal["release_name"].str.contains("FOMC Press Release", case=False)]
            cal = cal[cal["date"].dt.dayofweek < 5]
        return cal, None
    except Exception as exc:
        return None, f"Calendar unavailable ({type(exc).__name__})."


def news_query(ind):
    return NEWS_QUERIES.get(ind["id"], re.sub(r"\(.*?\)", "", ind["name"]).strip())


def performance_view(groups, key):
    tickers = tuple(t for items in groups.values() for t, _ in items)
    try:
        prices = fetch_yahoo_batch(tickers)
    except Exception as exc:
        st.info(f"Yahoo Finance unavailable right now ({type(exc).__name__}).")
        return
    pct_cols = ["1D %", "1W %", "1M %", "YTD %", "1Y %"]
    colour = (lambda v: "" if v is None or pd.isna(v) else
              f"color: {ui.UP if v > 0 else ui.DOWN}; background-color: {ui.heat_colour(v, 8)}")
    allrows = []
    for n, (group, items) in enumerate(groups.items(), start=1):
        table = performance_table(prices, items)
        if table.empty:
            continue
        allrows.append(table)
        ui.section(group, code=f"{n:02d}")
        st.dataframe(
            table[["Name", "Ticker", "Last", *pct_cols, "Trend (1Y)"]].style
            .format({"Last": "{:,.2f}", **{c: "{:+.2f}%" for c in pct_cols}}, na_rep="-")
            .map(colour, subset=pct_cols),
            column_config={"Trend (1Y)": st.column_config.LineChartColumn("Trend (1Y)", width="medium")},
            hide_index=True, width="stretch")
    if allrows:
        everything = pd.concat(allrows).dropna(subset=["YTD %"]).sort_values("YTD %")
        ui.section("Year-to-date ranking", code="▲▼")
        fig = go.Figure()
        fig.add_bar(y=everything["Name"], x=everything["YTD %"], orientation="h",
                    marker_color=[ui.UP if v > 0 else ui.DOWN for v in everything["YTD %"]],
                    hovertemplate="%{y}: %{x:+.2f}%<extra></extra>")
        ui.base_layout(fig, max(320, 22 * len(everything)), unit="%")
        fig.update_layout(hovermode="closest", xaxis=dict(ticksuffix="%", showspikes=False))
        st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"{key}_ytd")
        st.caption(f"Prices via Yahoo Finance (unofficial, may be delayed) · last close "
                   f"{everything['As of'].max():%d %b %Y}.")


# ================================================================= pages

def page_home():
    watch = st.session_state.setdefault("watchlist", load_watchlist())
    c1, c2, c3, c4 = st.columns([1, 1, 1.1, 1.5], gap="small")
    with c1, st.container(border=True):
        ui.panel_title("US recession probability", "12M AHEAD", about="recession probability")
        recession_gauge()
    with c2, st.container(border=True):
        if PUBLIC:
            ui.panel_title("Macro momentum", "US · UK · EA · 3M", about="macro momentum")
            momentum_gauge()
        else:
            ui.panel_title("Risk appetite", "RISK-OFF ◄ ► RISK-ON", about="risk appetite")
            risk_meter()
    with c3, st.container(border=True):
        ui.panel_title("Economic calendar", "US · NEXT RELEASES", about="NFP")
        cal, err = load_calendar()
        if err:
            st.caption(err)
        else:
            calendar_rows(cal, limit=8)
    with c4, st.container(border=True):
        ui.panel_title("Top headlines", "LIVE FEEDS")
        news, _ = load_news()
        ui.headlines(news, limit=8)

    ui.section("Watchlist", "pin or unpin any indicator from its full-screen view", code="01",
               about="watchlist")
    ui.card_grid(watch, columns=6)

    ui.section("Macro scorecard", "latest, recent change and position in its 20-year range",
               code="02", about="scorecard")
    cols = st.columns(3, gap="small")
    for col, region in zip(cols, ("US", "UK", "EA")):
        with col, st.container(border=True):
            ui.panel_title({"US": "United States", "UK": "United Kingdom", "EA": "Euro area"}[region])
            rows = []
            for ind_id in ids_for(region):
                ind, res = LOADED[ind_id]
                s = res["series"]
                rows.append((ind, res, change_over(s, 3) if s is not None else None,
                             change_over(s, 12) if s is not None else None,
                             percentile_rank(s) if s is not None else None))
            ui.scorecard(rows)


def page_detail(ticker):
    ind_id = BY_TICKER[ticker]
    ind, res = LOADED[ind_id]
    f = FORECASTS.get(ind_id)
    k = ticker                                      # widget keys are per ticker
    watch = st.session_state.setdefault("watchlist", load_watchlist())

    b1, b2, b3 = st.columns([0.8, 6, 1.3])
    b1.button("◄ BACK", on_click=go_to, kwargs=dict(page=PAGE), width="stretch")
    pinned = ind_id in watch
    if b3.button("★ UNPIN" if pinned else "☆ PIN TO HOME", width="stretch"):
        if pinned:
            watch.remove(ind_id)
        else:
            watch.append(ind_id)
        save_watchlist(watch)
        st.rerun()
    if res["error"]:
        b2.markdown(f"<div class='pt'><b>{ui.escape(ind['name'])}</b><span>{ticker}</span></div>",
                    unsafe_allow_html=True)
        st.error(res["error"])
        return
    change = None if res["previous"] is None else res["latest"] - res["previous"]
    conf = ui.conf_html(f["stars"]) if f and not f.get("error") else ""
    b2.markdown(
        f"<div class='pt'><b style='font-size:.95rem'>{ui.escape(ind['name'])}{ui.info(ind_id, ind['name'])}</b>"
        f"<span>{ticker} · {ind['region'].upper()} · {ind['group'].upper()}</span></div>"
        f"<span class='hv' style='font-size:1.6rem'>{ui.fmt(res['latest'], ind)}</span> "
        f"{ui.change_html(ind, change)} <span class='hs'>{ui.date_label(ind, res['latest_date'])}</span>"
        f" &nbsp;{conf}{ui.info('confidence', 'Confidence') if conf else ''}", unsafe_allow_html=True)

    s_full = res["series"]
    first, last = s_full.index[0].to_pydatetime(), s_full.index[-1].to_pydatetime()
    range_key = f"d_range_{k}"

    def set_period():
        years = PERIODS.get(st.session_state.get(f"d_period_{k}") or "10Y")
        start = first if years is None else max(first, (s_full.index[-1] - pd.DateOffset(years=years)).to_pydatetime())
        st.session_state[range_key] = (start, last)

    if range_key not in st.session_state:
        st.session_state[f"d_period_{k}"] = "10Y"
        set_period()

    with st.container(border=True):
        r1 = st.columns([2.3, 1, 1.6, 2.4], gap="small")
        r1[0].segmented_control("Period", list(PERIODS), key=f"d_period_{k}", on_change=set_period,
                                help="How far back the chart goes. MAX = all available history.")
        default_kind = "Bar" if ind["chart"] == "bar" else "Line"
        kind = r1[1].selectbox("Chart", ["Line", "Area", "Bar"],
                               index=["Line", "Area", "Bar"].index(default_kind), key=f"d_kind_{k}")
        view = r1[2].selectbox("View", ["As shown", "Change vs previous", "% change y/y",
                                        "3-month average", "12-month average"], key=f"d_view_{k}",
                            help=ui.tip("views"))
        mouse = r1[3].segmented_control("Mouse", list(MOUSE), default="Zoom", key=f"d_mouse_{k}",
                                        help="Zoom/Pan to navigate. Line, Draw, Box and Circle draw "
                                             "on the chart; erase with the eraser icon (top right).")
        r2 = st.columns([2.2, 2.2, 1.4], gap="small")
        others = {f"{i['ticker']} · {i['name']}": i["id"] for i in ACTIVE if i["id"] != ind_id}
        compare = r2[0].multiselect("Compare (up to 3)", list(others), max_selections=3,
                                    key=f"d_cmp_{k}", placeholder="Overlay other indicators",
                                    help="Draws up to 3 other indicators on the same chart, on a second "
                                         "axis (or the same axis if Rebase 100 is on).")
        default_shades = ["UK recessions"] if ind["region"] == "UK" else \
            ["US recessions"] if ind["region"] in ("US", "Markets") else []
        shade_names = r2[1].multiselect("Shade periods", list(SHADE_PERIODS), default=default_shades,
                                        help=ui.tip("shading"),
                                        key=f"d_shade_{k}", placeholder="Recessions, hiking cycles...")
        levels_text = r2[2].text_input("Level lines", key=f"d_levels_{k}", placeholder="e.g. 2, 4.5",
                                       help=ui.tip("level lines"))
        r3 = st.columns(7, gap="small")
        has_fc = bool(f and not f.get("error"))
        show_fc = r3[0].toggle("Forecast", value=has_fc, disabled=not has_fc, key=f"d_fc_{k}",
                               help=ui.tip("forecast"))
        targets = r3[1].toggle("Targets", value=ind_id in REFERENCE_LINES,
                               disabled=ind_id not in REFERENCE_LINES, key=f"d_tg_{k}",
                               help=ui.tip("inflation target"))
        news_on = r3[2].toggle("News", value=ind["region"] in ("FX", "Markets"), key=f"d_news_{k}",
                               help=ui.tip("news markers"))
        events = r3[3].toggle("Events", value=False, key=f"d_ev_{k}", help=ui.tip("events"))
        rebase = r3[4].toggle("Rebase 100", value=False, key=f"d_rb_{k}", help=ui.tip("rebase"))
        log = r3[5].toggle("Log", value=False, key=f"d_log_{k}", help=ui.tip("log scale"))
        slider = r3[6].toggle("Slider", value=False, key=f"d_sl_{k}",
                              help="Adds a mini overview strip under the chart that you can drag.")

    start, end = st.session_state[range_key]
    base = ui.transform_view(s_full, view)
    shown = base[(base.index >= pd.Timestamp(start)) & (base.index <= pd.Timestamp(end))]
    comps = []
    for label in compare:
        c_ind, c_res = LOADED[others[label]]
        if c_res["series"] is not None:
            comps.append((c_ind, ui.transform_view(c_res["series"], view)))
    at_latest = pd.Timestamp(end) >= s_full.index[-1]
    fc = f["fc"] if (show_fc and has_fc and view == "As shown" and at_latest) else None
    shades = [(n, *SHADE_PERIODS[n]) for n in shade_names]
    lines = list(REFERENCE_LINES.get(ind_id, [])) if targets else []
    for part in (levels_text or "").replace(";", ",").split(","):
        try:
            lines.append((float(part.strip()), f"{float(part.strip()):g}"))
        except ValueError:
            pass
    news = None
    if news_on:
        try:
            news = search_news(news_query(ind))
        except Exception:
            news = None

    fig = ui.build_figure(ind, shown, height=540, kind=kind, compare=comps, rebase=rebase,
                          shades=shades, forecast=fc, events=events, log=log, slider=slider,
                          ref_lines=lines, news=news, dragmode=MOUSE.get(mouse or "Zoom"))
    st.plotly_chart(fig, width="stretch", config=ui.DRAW_CONFIG, key=f"detail_{k}")
    st.slider("Zoom to dates (the y-axis refits automatically)", min_value=first, max_value=last,
              key=range_key, format="MMM YYYY", label_visibility="visible")
    notes = ["Drag to zoom · double-click to reset · camera icon saves a PNG · drawings stay "
             "until you change the date range"]
    if shades:
        notes.append("shaded: " + ", ".join(shade_names))
    if fc is not None:
        notes.append("dotted line + band = forecast (not advice)")
    elif show_fc and has_fc:
        notes.append("forecast shows with View = As shown and the range ending today")
    if news is not None and not news.empty:
        notes.append("◆ = headline (hover to read)")
    st.caption(" · ".join(notes))

    stats = st.columns(7, gap="small")
    last10 = ui.window(s_full, 10)
    year_ago = s_full.asof(s_full.index[-1] - pd.DateOffset(years=1))
    pct = percentile_rank(s_full)
    stats[0].metric("Last", ui.fmt(res["latest"], ind))
    stats[1].metric("1Y ago", ui.fmt(year_ago, ind))
    stats[2].metric("1Y change", ui.fmt(None if pd.isna(year_ago) else res["latest"] - year_ago, ind, True))
    stats[3].metric("5Y avg", ui.fmt(ui.window(s_full, 5).mean(), ind))
    stats[4].metric("10Y high", ui.fmt(last10.max(), ind))
    stats[5].metric("10Y low", ui.fmt(last10.min(), ind))
    stats[6].metric("20Y pctl", "-" if pct is None else f"{pct:.0f}", help=ui.tip("percentile"))

    col_a, col_b, col_c = st.columns([1.3, 0.9, 1.3], gap="small")
    with col_a, st.container(border=True):
        ui.panel_title("Description & forecast", about=ind_id)
        url, src = source_url(ind), SOURCE_NAMES.get(ind["source"], ind["source"])
        st.markdown(
            (f"**Source:** [{src}]({url})" if url else f"**Source:** {src}")
            + f"  \n**Series:** `{ind['code']}`"
            + (f"  \n**Official title:** {res['official_title']}" if res["official_title"] else "")
            + f"  \n**Coverage:** {res['first_date']:%b %Y} to {res['latest_date']:%d %b %Y}"
            + "  \n**Shown as:** " + {"level": "the published figure",
                                      "change": "the change from the previous period",
                                      "yoy": "% change on a year earlier"}[ind["transform"]])
        if has_fc:
            endrow = f["fc"].iloc[-1]
            st.markdown(
                f"**Forecast {f['fc'].index[-1]:%b %Y}:** {ui.fmt(endrow['median'], ind)} "
                f"(80% range {ui.fmt(endrow['low'], ind)} to {ui.fmt(endrow['high'], ind)})  \n"
                f"**Confidence:** {ui.conf_html(f['stars'])} &nbsp; {f['agree']} of "
                f"{f['counted']} related indicators with data point {ui.WORDS[f['dir']]}.",
                unsafe_allow_html=True)
            st.dataframe(f["table"], hide_index=True, width="stretch")
            st.caption("Autoregressive model, last 25 years, pandemic months excluded, 2,000 "
                       "simulations. " + ui.DISCLAIMER)
    with col_b, st.container(border=True):
        ui.panel_title("Data", f"{len(s_full):,} OBS")
        recent = s_full.sort_index(ascending=False).head(30).rename("value").to_frame()
        recent.index = recent.index.strftime("%d %b %Y")
        st.dataframe(recent, width="stretch", height=320)
        st.download_button("⭳ Full history CSV", s_full.rename(ind["name"]).to_csv(),
                           file_name=f"{ticker}.csv", mime="text/csv", width="stretch")
    with col_c, st.container(border=True):
        ui.panel_title("Related news", "LAST 30 DAYS")
        if news is None:
            try:
                news = search_news(news_query(ind))
            except Exception:
                news = None
        if news is None:
            st.caption("News search unavailable right now.")
        else:
            ui.headlines(news, limit=10, empty="No recent headlines found.")
        biggest_moves(ind, s_full, news)


def biggest_moves(ind, series, news):
    """The largest recent moves, with any headlines from the same days."""
    daily = ui.is_daily(ind)
    recent = series[series.index >= series.index[-1] - pd.Timedelta(days=90 if daily else 730)]
    if len(recent) < 3:
        return
    moves = recent.diff() if ind["unit"] == "%" or not daily else recent.pct_change() * 100
    top = moves.dropna().abs().sort_values(ascending=False).head(5).index
    st.markdown(f"<div class='pt' style='margin-top:10px'><b>Biggest moves{ui.info('biggest moves', 'Biggest moves')}</b>"
                f"<span>{'90 DAYS' if daily else '2 YEARS'}</span></div>", unsafe_allow_html=True)
    rows = []
    for when in sorted(top, reverse=True):
        mv = moves[when]
        label = f"{mv:+.2f}%" if daily and ind["unit"] != "%" else ui.fmt(mv, ind, True)
        why = ""
        if news is not None and not news.empty:
            near = news[(news["time"] >= when - pd.Timedelta(days=1)) &
                        (news["time"] <= when + pd.Timedelta(days=2))]
            if not near.empty:
                r = near.iloc[0]
                why = (f"<a href='{ui.escape(str(r['link']))}' target='_blank'>"
                       f"{ui.escape(str(r['headline'])[:110])}</a>")
        rows.append(f"<div class='nr'><span class='t' style='min-width:74px'>"
                    + f"{when:%d %b %y}".upper() + f"</span><span class='chg {'up' if mv > 0 else 'dn'}' style='min-width:64px'>{label}</span>"
                    f"<span>{why or '<span class=hs>no matching headline</span>'}</span></div>")
    st.markdown("".join(rows), unsafe_allow_html=True)


def tv_chart_picker(key, default=0):
    labels = [f"{name} · {sym}" for sym, name in TV_CHART_CHOICES]
    choice = st.selectbox("Chart", labels, index=default, key=key,
                          help="A full TradingView chart: drag, zoom, change timeframe, add indicators "
                               "and drawings with the left toolbar. You can also type any symbol in it.")
    ui.tv_advanced_chart(TV_CHART_CHOICES[labels.index(choice)][0], height=560)


def page_wei():
    st.markdown("World Equity Monitor · live prices " + ui.info("TradingView", "TradingView"),
                unsafe_allow_html=True)
    left, right = st.columns([1, 1.5], gap="small")
    with left, st.container(border=True):
        ui.panel_title("Markets overview", "LIVE · TRADINGVIEW")
        ui.tv_market_overview(TV_EQUITY_TABS, height=600)
    with right, st.container(border=True):
        ui.panel_title("Chart", "LIVE · TRADINGVIEW")
        tv_chart_picker("wei_chart", 0)
    if not PUBLIC:
        ui.section("Performance table", "Yahoo Finance · your PC only", code="02")
        performance_view(EQUITY_MONITOR, "wei")


def page_cmdty():
    left, right = st.columns([1, 1.5], gap="small")
    with left, st.container(border=True):
        ui.panel_title("Commodities overview", "LIVE · TRADINGVIEW", about="futures")
        ui.tv_market_overview(TV_COMMODITY_TABS, height=600)
    with right, st.container(border=True):
        ui.panel_title("Chart", "LIVE · TRADINGVIEW")
        tv_chart_picker("cmdty_chart", 8)
    ui.section("Monthly commodity prices", "IMF primary commodity prices via FRED", code="02",
               about="IMF")
    key = get_fred_key()
    if not key:
        st.caption("Needs your FRED key.")
    else:
        for n, (group, items) in enumerate(COMMODITY_MONTHLY.items(), start=1):
            series = {}
            for code, name, unit in items:
                try:
                    series[(name, unit)] = fetch_fred(code, key)
                except Exception:
                    pass
            table = monthly_performance(series)
            if table.empty:
                continue
            st.markdown(f"<div class='pt'><b>{group}</b><span>MONTHLY AVERAGE PRICES</span></div>",
                        unsafe_allow_html=True)
            pct = ["1M %", "3M %", "1Y %", "5Y %"]
            st.dataframe(
                table[["Commodity", "Unit", "Last", *pct, "Trend (5Y)", "Month"]].style
                .format({"Last": "{:,.2f}", **{c: "{:+.1f}%" for c in pct}}, na_rep="-")
                .map(lambda v: "" if v is None or pd.isna(v) else
                     f"color: {ui.UP if v > 0 else ui.DOWN}; background-color: {ui.heat_colour(v, 15)}",
                     subset=pct),
                column_config={"Trend (5Y)": st.column_config.LineChartColumn("Trend (5Y)", width="medium")},
                hide_index=True, width="stretch")
        st.caption("Source: IMF Primary Commodity Prices (monthly averages), via FRED.")
    if not PUBLIC:
        ui.section("Futures performance", "Yahoo Finance · your PC only", code="03")
        performance_view(COMMODITY_MONITOR, "cmdty")


def page_global():
    this_year = datetime.now().year
    years = list(range(this_year - 8, this_year + 4))
    c1, c2 = st.columns([1.3, 2])
    code = c1.selectbox("Measure", list(IMF_INDICATORS), format_func=lambda c: IMF_INDICATORS[c][0],
                        help="IMF World Economic Outlook data. " + (ui.tip("current account") or ""))
    year = c2.select_slider("Year", options=years, value=this_year)
    try:
        df = fetch_imf(code, tuple(years))
        names = fetch_imf_countries()
    except Exception as exc:
        st.info(f"IMF data unavailable right now ({type(exc).__name__}).")
        df, names = None, {}
    if df is not None:
        label, unit = IMF_INDICATORS[code]
        countries = df[df.index.isin(list(names))] if names else df[df.index.str.len() == 3]
        if year in countries.columns:
            vals = countries[year].dropna()
            fig = go.Figure()
            fig.add_trace(go.Choropleth(
                locations=vals.index, z=vals.values, text=[names.get(c, c) for c in vals.index],
                colorscale=[[0, "#1B3A5C"], [0.5, "#14181E"], [1, "#E8212B"]],
                zmid=float(vals.median()), marker_line_color="#000", marker_line_width=0.3,
                colorbar=dict(title=dict(text=unit), thickness=8, tickfont=dict(family=ui.MONO, size=9)),
                hovertemplate="%{text}<br>%{z:.1f}" + unit + "<extra></extra>"))
            fig.update_layout(height=440, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                              font=dict(family=ui.MONO, color="#AEB8C2"),
                              geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False, showcoastlines=False,
                                       landcolor="#11161C", projection_type="natural earth",
                                       showocean=False, showcountries=True, countrycolor="#000"))
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="world_map")
        st.caption(f"{label}, {year}. Years after the latest actual data are IMF projections "
                   "(World Economic Outlook).")
        ui.section("Major economies", f"{label} · IMF", code="01", about="WEO")
        cols = [y for y in (this_year - 1, this_year, this_year + 1) if y in df.columns]
        table = df.reindex(MAJOR_ECONOMIES)[cols].copy()
        table.index = [names.get(c, c) for c in table.index]
        left, right = st.columns([1, 1.3], gap="small")
        left.dataframe(table.style.format("{:.1f}" + unit, na_rep="-"), width="stretch", height=540)
        with right:
            fig = go.Figure()
            for y, colour in zip(cols, ["#3A434E", ui.ACCENT, ui.CYAN]):
                fig.add_bar(x=table.index, y=table[y], name=str(y), marker_color=colour)
            ui.base_layout(fig, 540, unit=unit, legend=True)
            fig.update_layout(barmode="group", hovermode="x unified",
                              xaxis=dict(showspikes=False, tickangle=-45))
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="major_bars")

    ui.section("Central bank rates board", "policy rates from the Bank for International Settlements",
               code="02", about="policy rate")
    try:
        rates = fetch_policy_rates(tuple(sorted({c["bis"] for c in COUNTRIES.values()})))
        area_names = {}
        for c in COUNTRIES.values():
            area_names.setdefault(c["bis"], "Euro area" if c["bis"] == "XM" else c["name"])
        rows = []
        for area in rates.columns:
            s = rates[area].dropna()
            if s.empty:
                continue
            moves = s.diff()
            last_move = moves[moves != 0].dropna()
            rows.append({"Central bank": area_names.get(area, area), "Rate %": s.iloc[-1],
                         "3M chg": change_over(s, 3), "12M chg": change_over(s, 12),
                         "Last move": f"{last_move.index[-1]:%b %Y}" if len(last_move) else "-",
                         "Direction": ("▲ hiking" if len(last_move) and last_move.iloc[-1] > 0 else
                                       "▼ cutting" if len(last_move) else "-"),
                         "As of": f"{s.index[-1]:%b %Y}"})
        board = pd.DataFrame(rows).sort_values("Rate %", ascending=False)
        left, right = st.columns([1.2, 1.3], gap="small")
        left.dataframe(board.style.format({"Rate %": "{:.2f}", "3M chg": "{:+.2f}", "12M chg": "{:+.2f}"},
                                          na_rep="-"), hide_index=True, width="stretch", height=560)
        with right:
            pick = st.multiselect("Compare policy rates", board["Central bank"].tolist(),
                                  default=[n for n in ["United States", "United Kingdom", "Euro area",
                                                       "Japan"] if n in board["Central bank"].tolist()],
                                  key="cb_pick")
            inv = {v: k for k, v in area_names.items()}
            fig = go.Figure()
            for i, name in enumerate(pick):
                s = rates[inv[name]].dropna()
                s = s[s.index >= s.index[-1] - pd.DateOffset(years=20)]
                fig.add_scatter(x=s.index, y=s.values, mode="lines", name=name, line=dict(width=1.5),
                                line_shape="hv")
            ui.base_layout(fig, 470, unit="%", legend=True)
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="cb_chart")
        st.caption("Source: BIS central bank policy rates (monthly). The euro area appears once "
                   "for the ECB.")
    except Exception as exc:
        st.info(f"BIS policy rates unavailable right now ({type(exc).__name__}).")


def page_country():
    codes = list(COUNTRIES)
    iso = st.selectbox("Country", codes, index=codes.index("GBR"),
                       format_func=lambda c: f"{c} · {COUNTRIES[c]['name']}", key="ctry")
    c = COUNTRIES[iso]
    this_year = datetime.now().year
    years = tuple(range(2000, this_year + 6))
    imf = {}
    for code in IMF_INDICATORS:
        try:
            imf[code] = fetch_imf(code, years).loc[iso].dropna()
        except Exception:
            imf[code] = pd.Series(dtype=float)
    try:
        rates = fetch_policy_rates(tuple(sorted({x["bis"] for x in COUNTRIES.values()})))
        policy = rates[c["bis"]].dropna() if c["bis"] in rates.columns else pd.Series(dtype=float)
    except Exception:
        policy = pd.Series(dtype=float)
    fx = pd.Series(dtype=float)
    key = get_fred_key()
    if c["fx"] and key:
        try:
            raw = fetch_fred(c["fx"][0], key)
            fx = raw if c["fx"][1] == "per_usd" else 1 / raw
        except Exception:
            pass
    equity = pd.Series(dtype=float)
    if c["equity"] and not PUBLIC:
        try:
            equity = fetch_yahoo(c["equity"])
        except Exception:
            pass

    ui.section(c["name"], f"{iso} · currency {c['ccy']}", code="CTRY", about="WEO")
    tiles = st.columns(6, gap="small")

    def tile(col, label, value, sub, about=None):
        with col, st.container(border=True):
            st.markdown(f"<div class='k-name'>{label}{ui.info(about, label) if about else ''}</div>"
                        f"<div class='k-val'>{value}</div>"
                        f"<div class='k-foot'><span>{sub}</span></div>", unsafe_allow_html=True)

    def imf_val(code, yr):
        s = imf.get(code, pd.Series(dtype=float))
        return f"{s[yr]:.1f}%" if yr in s.index else "-"
    tile(tiles[0], "GDP growth", imf_val("NGDP_RPCH", this_year), f"IMF {this_year}", "GDP")
    tile(tiles[1], "Inflation", imf_val("PCPIPCH", this_year), f"IMF {this_year}", "CPI")
    tile(tiles[2], "Unemployment", imf_val("LUR", this_year), f"IMF {this_year}", "unemployment rate")
    tile(tiles[3], "Govt debt / GDP", imf_val("GGXWDG_NGDP", this_year), f"IMF {this_year}",
         "government debt")
    tile(tiles[4], "Policy rate", f"{policy.iloc[-1]:.2f}%" if len(policy) else "-",
         f"BIS {policy.index[-1]:%b %Y}".upper() if len(policy) else "BIS", "policy rate")
    tile(tiles[5], f"{c['ccy']} per USD", f"{fx.dropna().iloc[-1]:,.4f}" if len(fx.dropna()) else "-",
         f"FRED {fx.dropna().index[-1]:%d %b %y}".upper() if len(fx.dropna()) else "USD base",
         "currency pair")

    left, right = st.columns(2, gap="small")
    for col, code in ((left, "NGDP_RPCH"), (right, "PCPIPCH")):
        with col, st.container(border=True):
            s = imf.get(code, pd.Series(dtype=float))
            ui.panel_title(IMF_INDICATORS[code][0], "IMF · ACTUAL + PROJECTION", about="WEO")
            if s.empty:
                st.caption("No IMF data.")
                continue
            fig = go.Figure()
            fig.add_bar(x=[int(y) for y in s.index], y=s.values,
                        marker_color=[ui.ACCENT if int(y) < this_year else "#5C1A1E" for y in s.index],
                        hovertemplate="%{x}: %{y:.1f}%<extra></extra>")
            ui.base_layout(fig, 250, unit="%")
            fig.update_layout(xaxis=dict(showspikes=False))
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"ctry_{code}")
            st.caption("Darker bars = IMF projections.")
    l2, m2, r2 = st.columns(3, gap="small")
    for col, title, s, unit, kk in ((l2, "Policy rate", policy, "%", "pol"),
                                    (m2, f"{c['ccy']} per USD", fx, "", "fx"),
                                    (r2, f"Equity index ({c['equity'] or 'n/a'})", equity, "", "eq")):
        with col, st.container(border=True):
            ui.panel_title(title, "20Y")
            s = s.dropna()
            if s.empty:
                st.caption("See the World Equities page for live index charts."
                           if PUBLIC and kk == "eq" else "Not available for this country.")
                continue
            s = s[s.index >= s.index[-1] - pd.DateOffset(years=20)]
            fig = go.Figure()
            fig.add_scatter(x=s.index, y=s.values, mode="lines", line=dict(color=ui.ACCENT, width=1.4),
                            line_shape="hv" if kk == "pol" else "linear")
            ui.base_layout(fig, 230, unit=unit)
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"ctry_{kk}")
    with st.container(border=True):
        ui.panel_title(f"{c['name']} economy headlines", "GOOGLE NEWS · 30 DAYS")
        try:
            ui.headlines(search_news(f"{c['name']} economy"), limit=12, empty="News search unavailable right now.")
        except Exception:
            st.caption("News search unavailable right now.")
    st.caption("Sources: IMF World Economic Outlook, BIS policy rates, FRED exchange rates, "
               "Yahoo Finance index prices, Google News.")


def page_news():
    left, right = st.columns([1, 2], gap="small")
    with left:
        with st.container(border=True):
            ui.panel_title("FX snapshot", "1 GBP BUYS")
            fx_snapshot()
        ui.card_grid(["dxy", "eurusd", "usdjpy", "gbpusd"], columns=2)
        with st.container(border=True):
            ui.panel_title("World growth", "IMF")
            try:
                yrs = tuple(range(datetime.now().year - 1, datetime.now().year + 2))
                gdp = fetch_imf("NGDP_RPCH", yrs)
                if "WEOWORLD" in gdp.index:
                    st.markdown("  ·  ".join(f"**{y}:** {v:.1f}%" for y, v in gdp.loc["WEOWORLD"].dropna().items()))
                    st.caption("World real GDP growth, IMF estimates and projections.")
                else:
                    st.caption("World total not available; see the Global page.")
            except Exception:
                st.caption("IMF data unavailable right now.")
    with right:
        with st.container(border=True):
            ui.panel_title("Search any topic", "GOOGLE NEWS · 30 DAYS")
            q = st.text_input("Search", placeholder="e.g. tariffs, Bank of Japan, Chinese exports",
                              key="n_q", label_visibility="collapsed")
            if q:
                try:
                    ui.headlines(search_news(q), limit=15, empty="No results (or news search unavailable).")
                except Exception:
                    st.caption("News search unavailable right now.")
        with st.container(border=True):
            news, failed = load_news()
            ui.panel_title("Live feeds", f"{len(news)} HEADLINES")
            f1, f2 = st.columns([2.4, 1.6])
            topic = f1.segmented_control("Topic", ["All", *NEWS_TOPICS], default="All", key="n_topic")
            sources = f2.multiselect("Sources", sorted(news["source"].unique()) if not news.empty else [],
                                     key="n_src", placeholder="All sources")
            view = news
            if not view.empty:
                if topic and topic != "All":
                    view = view[view["topics"].apply(lambda t: topic in t)]
                if sources:
                    view = view[view["source"].isin(sources)]
            ui.headlines(view, limit=60)
            note = "Headlines and links only, from public RSS feeds, refreshed every 30 minutes."
            if failed:
                note += " Unavailable: " + ", ".join(failed) + "."
            st.caption(note)


def page_fx():
    left, right = st.columns([1, 1.6], gap="small")
    with left, st.container(border=True):
        ui.panel_title("GBP snapshot", "1 GBP BUYS", about="ECB reference rates")
        fx_snapshot()
    with right, st.container(border=True):
        ui.panel_title("Currency strength heatmap", "% CHANGE", about="currency strength")
        strength_heatmap()
    region_page("FX", "Sterling, the majors, commodity currencies and emerging markets. "
                      "Full-screen views show related news and the biggest recent moves.")


def page_curves():
    st.markdown("Yield at each maturity today vs one year ago " + ui.info("yield curve", "Yield curve")
                + ui.info("inversion", "Inversion"), unsafe_allow_html=True)
    cols = st.columns(len(YIELD_CURVES), gap="small")
    for col, (name, curve) in zip(cols, YIELD_CURVES.items()):
        with col, st.container(border=True):
            ui.panel_title(name, about="zero coupon" if "zero" in name else "yield curve")
            table, today, year_ago, error = load_curve(curve)
            if error:
                st.caption(error)
                continue
            fig = go.Figure()
            fig.add_scatter(x=table["Maturity"], y=table["1 year ago"], mode="lines+markers",
                            name=f"{year_ago:%d %b %Y}", line=dict(color="#55606C", dash="dot"))
            fig.add_scatter(x=table["Maturity"], y=table["Latest"], mode="lines+markers",
                            name=f"{today:%d %b %Y}", line=dict(color=ui.ACCENT, width=2.2))
            ui.base_layout(fig, 290, unit="%", legend=True)
            fig.update_layout(xaxis=dict(showspikes=False, type="category"))
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"curve_{name}")
            st.dataframe(table.style.format({"Latest": "{:.2f}%", "1 year ago": "{:.2f}%"}, na_rep="-"),
                         hide_index=True, width="stretch")
    ui.section("Yield-curve recession signal", "NY Fed model · P(US recession in 12 months)", code="02",
               about="recession probability")
    ind, res = LOADED["us_3m10y"]
    if res["series"] is None:
        st.caption("Needs the 3m10y spread from FRED.")
        return
    probs = recession_probability(res["series"])
    p_ind = dict(name="Recession probability", decimals=0, unit="%", chart="line", region="US",
                 group="Rates", id="rp", ticker="RECPROB", good_when="down")
    fig = ui.build_figure(p_ind, probs, height=320, shades=[("US recessions", *SHADE_PERIODS["US recessions"])],
                          slider=True, ref_lines=[(30, "30% warning")])
    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="recprob")
    st.caption("Each point = the model's probability for that month, from the spread 12 months "
               "earlier. Grey bands = actual NBER recessions. Educational only.")


def page_calendar():
    left, right = st.columns([1.4, 1], gap="small")
    with left, st.container(border=True):
        ui.panel_title("US key releases", "NEXT 45 DAYS · FRED", about="NFP")
        st.markdown("Key terms: " + ui.info("NFP", "NFP") + " payrolls · " + ui.info("CPI", "CPI")
                    + " inflation · " + ui.info("GDP", "GDP") + " growth · " + ui.info("FOMC", "FOMC")
                    + " Fed decisions", unsafe_allow_html=True)
        cal, err = load_calendar()
        if err:
            st.caption(err)
        else:
            calendar_rows(cal)
    with right, st.container(border=True):
        ui.panel_title("UK and Europe calendars", about="MPC")
        st.markdown(
            "- [ONS release calendar](https://www.ons.gov.uk/releasecalendar): GDP, CPI, labour "
            "market, retail sales, trade\n"
            "- [Bank of England MPC dates](https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates)\n"
            "- [ECB monetary policy meetings](https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html)\n"
            "- [Eurostat release calendar](https://ec.europa.eu/eurostat/news/release-calendar)\n"
            "- [OBR forecasts](https://obr.uk/)")


def page_lab():
    tab1, tab2, tab3 = st.tabs(["Correlation & lead/lag", "Taylor rule",
                                "Macro momentum" if PUBLIC else "Risk appetite"])
    options = {f"{i['ticker']} · {i['name']}": i["id"] for i in ACTIVE
               if LOADED[i["id"]][1]["series"] is not None}
    with tab1:
        st.caption("Does one indicator move before another? Pick two to see how closely they "
                   "track and whether one tends to lead.")
        labels = list(options)
        if len(labels) >= 2:
            c1, c2, c3 = st.columns([2, 2, 1])
            x_label = c1.selectbox("Indicator X", labels, index=0, key="lab_x")
            y_label = c2.selectbox("Indicator Y", labels, index=1, key="lab_y")
            yrs = c3.selectbox("Years", [5, 10, 20, 30], index=2, key="lab_years")
            x_ind, x_res = LOADED[options[x_label]]
            y_ind, y_res = LOADED[options[y_label]]
            lags = lead_lag(x_res["series"], y_res["series"], years=yrs)
            if lags.dropna().empty:
                st.caption("These two don't overlap enough to compare.")
            else:
                best = int(lags.abs().idxmax())
                left, right = st.columns(2, gap="small")
                with left, st.container(border=True):
                    ui.panel_title("Scatter", "EACH DOT = 1 MONTH", about="correlation")
                    joined = pd.concat([x_res["series"].resample("MS").mean(),
                                        y_res["series"].resample("MS").mean()], axis=1, sort=True).dropna()
                    joined = joined[joined.index >= joined.index[-1] - pd.DateOffset(years=yrs)]
                    fig = go.Figure()
                    fig.add_scatter(x=joined.iloc[:, 0], y=joined.iloc[:, 1], mode="markers",
                                    marker=dict(color=list(range(len(joined))), colorscale="Reds",
                                                size=6, opacity=0.85),
                                    text=joined.index.strftime("%b %Y"),
                                    hovertemplate="%{text}<br>X %{x:.2f} · Y %{y:.2f}<extra></extra>")
                    ui.base_layout(fig, 360)
                    fig.update_layout(hovermode="closest", xaxis=dict(title=x_ind["ticker"], showspikes=False),
                                      yaxis=dict(title=y_ind["ticker"]))
                    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="lab_scatter")
                with right, st.container(border=True):
                    ui.panel_title("Lead / lag", "CORRELATION BY SHIFT", about="lead/lag")
                    fig = go.Figure()
                    fig.add_bar(x=lags.index, y=lags.values,
                                marker_color=[ui.ACCENT if l == best else "#2E3742" for l in lags.index])
                    ui.base_layout(fig, 360)
                    fig.update_layout(xaxis=dict(title="months X leads Y", showspikes=False),
                                      yaxis=dict(range=[-1, 1]))
                    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="lab_lags")
                lead = (f"X leads Y by {best} months" if best > 0 else
                        f"Y leads X by {-best} months" if best < 0 else "they move together")
                st.markdown(f"**Same-month correlation:** {lags.get(0, float('nan')):+.2f} · "
                            f"**Strongest:** {lags[best]:+.2f} when {lead}.")
                st.caption("Correlation shows association, not cause and effect.")
    with tab2:
        st.markdown("The Taylor rule " + ui.info("Taylor rule", "Taylor rule")
                    + " · neutral rate " + ui.info("neutral rate", "Neutral rate (r*)"),
                    unsafe_allow_html=True)
        c = st.columns(6)
        region = c[0].selectbox("Economy", ["UK", "US"], key="tr_region")
        r_star = c[1].slider("Neutral real rate", -1.0, 3.0, 0.5, 0.25, key="tr_r")
        target = c[2].slider("Inflation target", 0.0, 4.0, 2.0, 0.25, key="tr_t")
        a = c[3].slider("Weight: inflation", 0.0, 2.0, 0.5, 0.1, key="tr_a")
        b = c[4].slider("Weight: jobs gap", 0.0, 2.0, 1.0, 0.1, key="tr_b")
        u_star = c[5].slider("Natural unemployment", 3.0, 7.0, 4.5 if region == "UK" else 4.2, 0.1,
                             key="tr_u")
        infl, unemp, rate = (("uk_cpi", "uk_unemp", "uk_bankrate") if region == "UK"
                             else ("us_cpi", "us_unemp", "us_fedfunds"))
        if any(LOADED[i][1]["series"] is None for i in (infl, unemp, rate)):
            st.caption("Needs inflation, unemployment and the policy rate to load.")
        else:
            rule = ui.window(taylor_rule(LOADED[infl][1]["series"], LOADED[unemp][1]["series"],
                                         r_star, target, a, b, u_star), 25)
            actual = ui.window(LOADED[rate][1]["series"].resample("MS").mean(), 25)
            fig = go.Figure()
            fig.add_scatter(x=actual.index, y=actual.values, name="Actual policy rate",
                            line=dict(color=ui.CYAN, width=1.6, shape="hv"))
            fig.add_scatter(x=rule.index, y=rule.values, name="Taylor rule",
                            line=dict(color=ui.ACCENT, width=1.6, dash="dot"))
            ui.base_layout(fig, 400, unit="%", legend=True)
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="taylor")
            gap = float(rule.iloc[-1] - actual.dropna().iloc[-1])
            st.markdown(f"**Rule: {rule.iloc[-1]:.2f}%** vs actual {actual.dropna().iloc[-1]:.2f}% → "
                        f"policy looks **{'looser' if gap > 0 else 'tighter'}** than the rule by "
                        f"{abs(gap):.2f}pp.")
            st.caption("rate = r* + inflation + a·(inflation − target) + b·(u* − unemployment). "
                       "A teaching tool, not how central banks decide.")
    with tab3:
        if PUBLIC:
            st.markdown("Macro momentum " + ui.info("macro momentum", "Macro momentum"), unsafe_allow_html=True)
            momentum_gauge(key="gauge_mom_lab")
        else:
            st.markdown("Risk appetite " + ui.info("risk appetite", "Risk appetite"), unsafe_allow_html=True)
            risk_meter(key="gauge_risk_lab", table=True)


def page_pmi():
    pmi = load_pmi(PMI_FILE)
    st.markdown("Purchasing Managers' Index " + ui.info("PMI", "PMI"), unsafe_allow_html=True)
    st.caption("Above 50 = expansion, below 50 = contraction. Headline S&P Global / ISM figures, "
               "added monthly, kept on your PC only.")
    if pmi.empty:
        st.info("No PMI figures yet. They get added to data/pmi.csv each month.")
        return
    for region in sorted(pmi["region"].unique()):
        with st.container(border=True):
            ui.panel_title(region)
            fig = go.Figure()
            for survey, rows in pmi[pmi["region"] == region].groupby("survey"):
                fig.add_scatter(x=rows["date"], y=rows["value"], mode="lines+markers", name=survey)
            fig.add_hline(y=50, line_dash="dash", line_color="#55606C")
            ui.base_layout(fig, 280, legend=True)
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"pmi_{region}")


def page_help():
    st.markdown("#### Getting around")
    st.markdown(
        "- **Command line** (top): type a ticker (`UKCPI`, `GBPUSD`, `BRENT`), a page code "
        "(`WEI`, `CTRY`, `NEWS`) or any word (*inflation*, *gilt*, *yen*) and pick from the list.\n"
        "- **Click any card**, ticker-tape item or scorecard row to open it full screen.\n"
        "- **Full screen**: period buttons, a date slider that refits the axis, line/area/bar, "
        "views (change, y/y, averages), up to 3 overlays, rebase to 100, log scale, shaded "
        "periods (recessions, hiking cycles, inversions, bear markets, stress), target and custom "
        "level lines, events, related news markers, biggest moves, forecast, CSV download, pin.\n"
        "- **Drawing**: choose Line, Draw, Box or Circle under Mouse, then drag on the chart. "
        "Erase with the eraser icon. Save with the camera icon.\n"
        "- **Zoom**: drag across the chart, double-click to reset, or use the date slider.\n"
        "- **Links are shareable**: the address bar changes as you move around.\n"
        "- **Not sure what something means?** Click any small **i** icon, or search the glossary below.")
    st.markdown("#### Page codes")
    st.dataframe(pd.DataFrame([(c, l, d) for c, (l, d) in PAGES.items()],
                              columns=["Code", "Page", "What's there"]), hide_index=True, width="stretch")
    st.markdown("#### Tickers")
    rows = []
    for ind in ACTIVE:
        res = LOADED[ind["id"]][1]
        rows.append(dict(Ticker=ind["ticker"], Name=ind["name"], Region=ind["region"], Group=ind["group"],
                         Source=SOURCE_NAMES.get(ind["source"], ind["source"]),
                         Since="-" if res["first_date"] is None else f"{res['first_date']:%Y}",
                         Status="OK" if res["error"] is None else res["error"],
                         Forecast="yes" if ind["id"] in FORECASTS else ""))
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=600)
    st.markdown("#### Shading options")
    st.dataframe(pd.DataFrame([(n, len(SHADE_PERIODS[n][0])) for n in SHADE_PERIODS],
                              columns=["Shade", "Episodes found"]), hide_index=True)
    st.markdown("#### Glossary")
    q = st.text_input("Search the glossary", placeholder="e.g. inflation, yield, VIX", key="gloss_q")
    terms = pd.DataFrame(sorted(TERMS.items(), key=lambda kv: kv[0].lower()), columns=["Term", "Meaning"])
    about = pd.DataFrame([(i["ticker"], i["name"], ABOUT.get(i["id"], "")) for i in ACTIVE],
                         columns=["Ticker", "Indicator", "What it is"])
    if q:
        terms = terms[terms.apply(lambda r: q.lower() in (r["Term"] + r["Meaning"]).lower(), axis=1)]
        about = about[about.apply(lambda r: q.lower() in " ".join(r).lower(), axis=1)]
    st.dataframe(terms, hide_index=True, width="stretch", height=420,
                 column_config={"Meaning": st.column_config.TextColumn(width="large")})
    st.dataframe(about, hide_index=True, width="stretch", height=420,
                 column_config={"What it is": st.column_config.TextColumn(width="large")})
    if PUBLIC:
        st.caption("Online version: " + TERMS["public mode"])
    st.markdown("#### Events marked on charts")
    st.dataframe(pd.DataFrame(EVENTS, columns=["Date", "Event"]), hide_index=True)


# ================================================================= router

if TICKER:
    page_detail(TICKER)
elif PAGE == "HOME":
    page_home()
elif PAGE == "US":
    region_page("US", "The US economy.")
elif PAGE == "UK":
    region_page("UK", "The UK economy.")
elif PAGE == "EA":
    region_page("EA", "The euro area economy (ECB data).")
elif PAGE == "MKT":
    region_page("Markets", "Key indices, volatility and commodities with full history.")
elif PAGE == "WEI":
    page_wei()
elif PAGE == "CMDTY":
    page_cmdty()
elif PAGE == "FX":
    page_fx()
elif PAGE == "GLOB":
    page_global()
elif PAGE == "CTRY":
    page_country()
elif PAGE == "NEWS":
    page_news()
elif PAGE == "CRV":
    page_curves()
elif PAGE == "CAL":
    page_calendar()
elif PAGE == "LAB":
    page_lab()
elif PAGE == "PMI":
    page_pmi()
elif PAGE == "HELP":
    page_help()

ui.status_bar(SOURCE_HEALTH, f"{sum(1 for _, r in LOADED.values() if r['error'] is None)}/"
                             f"{len(LOADED)} SERIES · CACHE 6H" + (" · PUBLIC EDITION" if PUBLIC else ""))
st.caption("Personal educational project. " + ui.DISCLAIMER + " Sources: FRED (Federal Reserve "
           "Bank of St. Louis; this product uses the FRED® API but is not endorsed or certified by "
           "it) · ONS (Open Government Licence v3.0) · Bank of England · ECB · BIS · IMF · ECB rates "
           "via Frankfurter · Yahoo Finance · Google News and public RSS feeds (headlines and links "
           "only). Not affiliated with Bloomberg L.P. · Built by Hamish Finlayson.")
