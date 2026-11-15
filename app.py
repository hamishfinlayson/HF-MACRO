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

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import ui
from forecast import (ar_forecast, change_over, forecast_direction, history_check, lead_lag,
                      macro_momentum, market_stats, return_correlation,
                      percentile_rank,
                      periods_from_flags, recession_probability, regime_periods, risk_appetite,
                      star_rating, taylor_rule, technical_recessions)
from indicators import (CALENDAR_RELEASES, COMMODITY_MONITOR, COUNTRIES, DEFAULT_WATCHLIST,
                        EQUITY_MONITOR, EVENTS, FX_TABLE_CURRENCIES, HEATMAP_CURRENCIES,
                        IMF_INDICATORS, INDICATORS, MAJOR_ECONOMIES, NEWS_FEEDS, NEWS_QUERIES,
                        NEWS_TOPICS, RECESSIONS, REFERENCE_LINES, RISK_COMPONENTS, SHADES, SIGNALS,
                        YIELD_CURVES, RESTRICTED_IDS, TV_EQUITY_TABS, TV_COMMODITY_TABS,
                        TV_CHART_CHOICES, COMMODITY_MONTHLY, MARKET_FORECASTS, OIL_DASHBOARD,
                        TV_CRYPTO_TABS, TV_CRYPTO_CHART, CRYPTO_TOP_N)
from glossary import ABOUT, TERMS
import legal
from reference import BENCHMARK, COMMODITIES, CRYPTO, CURRENCIES, FX_COMMON, FX_PAIRS, INDICES, RELEASES
from sources import (SOURCE_NAMES, compute_derived, currency_strength, fetch_calendar, fetch_fred,
                     fetch_fx_history, fetch_fx_table, fetch_imf, fetch_imf_countries, fetch_news,
                     fetch_news_search, fetch_policy_rates, fetch_yahoo, fetch_yahoo_batch,
                     get_fred_key, load_curve, load_indicator, load_pmi, load_us_recession_flags,
                     monthly_performance, performance_table, public_mode, source_url,
                     fetch_coin_markets, fetch_crypto_global, fetch_fear_greed, fetch_fred_first_release)
import models
import learn
import assetlab
import backtest
import signals
import model
import companies
import risk
import news
import focus
import workshop
import pattern_lab
import bubble
import stats
import smart
import takeovers
import eventlab
import fx

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
    "CMDTY": ("Commodities", "Oil dashboard, energy, metals and agriculture"),
    "CRYPTO": ("Crypto", "Top 20 coins, market cap, Bitcoin dominance, Fear & Greed, TradingView charts"),
    "FX": ("FX", "GBP snapshot, currency strength heatmap and 20 currency pairs"),
    "GLOB": ("Global", "IMF world map, major economies and central bank rates board"),
    "CTRY": ("Country", "One-page profile for 20 economies"),
    "NEWS": ("News", "FX snapshot, IMF growth and filtered headlines, plus a news search"),
    "CRV": ("Curves", "Yield curves and the yield-curve recession signal"),
    "CAL": ("Calendar", "Upcoming US data releases and UK calendar links"),
    "LAB": ("Lab", "Correlation and lead/lag explorer, Taylor rule"),
    "PMI": ("PMI", "Purchasing managers' indices (kept on your PC)"),
    "LEARN": ("Learn", "Lessons with live charts, case studies and quizzes"),
    "HELP": ("Help", "Every command and ticker, plus tips"),
    "LEGAL": ("Legal", "Disclaimer, terms, privacy, cookies, accessibility and contact"),
}
TAPE = ["ftse100", "ftse250", "sp500", "nasdaq", "stoxx50", "dax", "nikkei", "vix", "brent", "gold",
        "copper", "gbpusd", "gbpeur", "eurusd", "usdjpy", "dxy", "us_10y", "uk_10y", "uk_bankrate",
        "us_fedfunds", "ecb_dfr", "uk_cpi", "us_cpi", "ea_hicp", "btc", "eth"]
PERIODS = {"1Y": 1, "2Y": 2, "5Y": 5, "10Y": 10, "20Y": 20, "50Y": 50, "MAX": None}
MOUSE = {"Zoom": "zoom", "Pan": "pan", "Line": "drawline", "Draw": "drawopenpath",
         "Box": "drawrect", "Circle": "drawcircle"}

LOGO = HERE / "assets" / "logo.png"
st.set_page_config(page_title=APP_NAME, page_icon=str(LOGO) if LOGO.exists() else "📈",
                   layout="wide", initial_sidebar_state="expanded")

# Online (public) version hides series whose owners don't allow free republishing.
PUBLIC = public_mode()
ACTIVE = [i for i in INDICATORS if not (PUBLIC and i["id"] in RESTRICTED_IDS)]
if not PUBLIC:                                   # PC version only: the Monte Carlo playground
    PAGES = {**{k: v for k, v in PAGES.items() if k not in ("HELP", "LEGAL")},
             "ALAB": ("Asset Lab", "Monte Carlo simulations for stocks, indices, commodities, FX and crypto"),
             "BUBBLE": ("Bubble Watch", "Checklist of the warning signs that came before past bubbles burst, with a score and time estimate"),
             "SMART": ("Smart Money", "What hedge funds, star stock-pickers and company insiders are buying, and whether copying them works"),
             "TAKEOVERS": ("Takeovers", "New private-equity takeover filings, activist funds pushing for a sale, and takeover rumours"),
             "EVENTLAB": ("Event Lab", "Big batch tests of published strategies and company events, and what is waiting for data"),
             "HELP": PAGES["HELP"], "LEGAL": PAGES["LEGAL"]}


# ================================================================= consent (age, terms, cookies)
# "a" = accepted all cookies, "e" = essential only, None = not asked yet.
# The choice travels in every link (&k=) and in a small strictly-necessary cookie.

def read_consent():
    for value in (st.query_params.get("k"), st.session_state.get("consent")):
        if value in ("a", "e"):
            return value
    try:
        value = st.context.cookies.get(legal.CONSENT_COOKIE)
    except Exception:
        value = None
    return value if value in ("a", "e") else None


def set_consent(value):
    st.session_state.consent = value
    st.session_state.write_cookie = value or "clear"
    if value:
        st.query_params["k"] = value
    elif "k" in st.query_params:
        del st.query_params["k"]


CONSENT = read_consent()
st.session_state.consent = CONSENT
ui.DATA.update(consent=CONSENT, set_consent=set_consent)
ui.inject_css(load_fonts=CONSENT == "a")
if st.session_state.get("write_cookie"):
    choice = st.session_state.pop("write_cookie")
    ui.remember_consent(None if choice == "clear" else choice, legal.CONSENT_COOKIE)


def consent_gate():
    """First visit: confirm age, agree to the terms and choose cookies. Nothing is pre-ticked,
    and both cookie buttons look the same (no nudging)."""
    ui.restore_consent(legal.CONSENT_COOKIE)        # returning visitor: reload with their saved choice
    st.markdown("<div class='brand'><span class='logo'>HF</span>MACRO<small>HFM &lt;GO&gt;</small></div>",
                unsafe_allow_html=True)
    ui.disclaimer_bar(legal.DISCLAIMER_SHORT)
    _, mid, _ = st.columns([1, 2.4, 1])
    with mid, st.container(border=True):
        st.markdown("## Welcome to HF Macro")
        st.markdown("A free, educational dashboard for economic and market data, built by "
                    f"{legal.OWNER}. Before you start, please confirm the following.")
        age = st.checkbox(f"I am {legal.MIN_AGE} or over", key="gate_age")
        terms = st.checkbox("I have read and agree to the Terms of service, and I understand that nothing "
                            "on HF Macro is financial advice", key="gate_terms")
        st.markdown("<div class='legal-links'>"
                    f"<a href='{ui.page_link('LEGAL', s='terms')}' target='_self'>Terms of service</a>"
                    f"<a href='{ui.page_link('LEGAL', s='disclaimer')}' target='_self'>Disclaimer</a>"
                    f"<a href='{ui.page_link('LEGAL', s='privacy')}' target='_self'>Privacy policy</a>"
                    f"<a href='{ui.page_link('LEGAL', s='cookies')}' target='_self'>Cookie policy</a></div>",
                    unsafe_allow_html=True)
        st.markdown("#### Cookies")
        st.markdown("HF Macro uses one strictly necessary cookie to remember these choices and sets no "
                    "advertising or tracking cookies of its own. The free hosting service (Streamlit "
                    "Community Cloud) sets its own cookies, including analytics, which HF Macro can't "
                    "control (see the Cookie policy). **Optional:** TradingView's charts (which "
                    "set TradingView cookies) and Google Fonts (which receives your IP address). With "
                    "*Essential only* the site works fully except that TradingView charts stay off until "
                    "you load them.")
        ready = age and terms
        c1, c2 = st.columns(2)
        c1.button("Accept all", on_click=set_consent, args=("a",), disabled=not ready, width="stretch",
                  key="gate_all")
        c2.button("Essential only", on_click=set_consent, args=("e",), disabled=not ready, width="stretch",
                  key="gate_ess")
        if not ready:
            st.caption(f"Tick both boxes to continue. HF Macro is only for people aged {legal.MIN_AGE} and over.")


if CONSENT is None and st.query_params.get("p") != "LEGAL":
    consent_gate()
    st.stop()

# ================================================================= load all data

import look
import contextlib
import importlib
import scenes
if getattr(look, "VERSION", None) != "43.2" or not hasattr(workshop, "explain") or not hasattr(scenes, "heartbeat_data"):   # a running app picks up updated files
    import look_assets, scenes_assets
    importlib.reload(look_assets)
    look = importlib.reload(look)
    workshop = importlib.reload(workshop)
    importlib.reload(scenes_assets)
    scenes = importlib.reload(scenes)


def show_scene(name, data, height, caption=None):
    """v42 page animations (scenes.py). Skipped quietly when the data isn't there."""
    if not data:
        return
    try:
        components.html(scenes.html(name, data, CONSENT == "a"), height=height)
        if caption:
            st.caption(caption)
    except Exception:
        pass


@st.cache_resource(ttl=1800, show_spinner=False)
def load_everything(ids, public):
    """Every indicator, recession dates, chart shading and forecasts. Kept in memory for 30 minutes so moving between
    pages is instant (the downloads underneath are cached for longer)."""
    active = [i for i in INDICATORS if i["id"] in ids]
    loaded = {ind["id"]: (ind, load_indicator(ind)) for ind in active}
    for ind in active:                                 # calculated indicators go second
        if ind["source"] == "derived":
            loaded[ind["id"]] = (ind, compute_derived(ind, loaded))
    by_ticker = {ind["ticker"]: ind["id"] for ind in active}
    us_flags = load_us_recession_flags()
    rec = {"US": periods_from_flags(us_flags) if us_flags is not None else []}
    uk_gdp = loaded[RECESSIONS["UK"]["from_id"]][1]["series"]
    rec["UK"] = technical_recessions(uk_gdp) if uk_gdp is not None else []
    shade = {name: (regime_periods(rule, loaded, rec), colour)
             for name, (rule, colour) in SHADES.items() if rule[0] == "recession" or rule[1] in loaded}
    forecasts = {}
    for ind_id, (ind, res) in loaded.items():
        if not ind.get("forecast") or res["series"] is None or ind_id not in SIGNALS:
            continue
        try:
            fc = ar_forecast(res["series"])
            fc_dir, fc_change = forecast_direction(res["series"], fc)
            stars, table, agree, counted = star_rating(fc_dir, SIGNALS[ind_id], loaded)
            forecasts[ind_id] = dict(fc=fc, dir=fc_dir, change=fc_change, stars=stars,
                                     table=table, agree=agree, counted=counted, error=None)
        except Exception as exc:
            forecasts[ind_id] = dict(error=str(exc))
    return loaded, by_ticker, rec, shade, forecasts


_first_load = not st.session_state.get("_hf_loaded")      # the big loading screen only on the very first load
with (ui.loading("Loading market and economic data", scene="feeds", sources=look.source_counts(ACTIVE))
      if _first_load else contextlib.nullcontext()):
    LOADED, BY_TICKER, REC, SHADE_PERIODS, FORECASTS = load_everything(tuple(i["id"] for i in ACTIVE), PUBLIC)
st.session_state["_hf_loaded"] = True

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
    if PUBLIC:                                    # public site: pins live only in your visit
        return list(DEFAULT_WATCHLIST)
    try:
        return [i for i in json.loads(WATCHLIST_FILE.read_text()) if i in LOADED]
    except Exception:
        return list(DEFAULT_WATCHLIST)


def save_watchlist(items):
    if PUBLIC:                                    # never store visitors' choices on the server
        return
    try:
        WATCHLIST_FILE.write_text(json.dumps(items))
    except Exception:
        pass


# ================================================================= navigation

qp = st.query_params
PAGE = qp.get("p", "HOME") if qp.get("p", "HOME") in PAGES else "HOME"
TICKER = qp.get("t") if qp.get("t") in BY_TICKER else None
VIEW = qp.get("v", "CHART") if qp.get("v", "CHART") in ("CHART", "DES", "DRIVERS") else "CHART"
CCY = qp.get("c") if qp.get("c") in CURRENCIES and not TICKER else None

COMMANDS = {f"{code:<6} {label.upper()} — page": ("page", code) for code, (label, _) in PAGES.items()}
COMMANDS.update({f"{ind['ticker']:<9} {ind['name']} [{ind['region']}]": ("ticker", ind["ticker"])
                 for ind in ACTIVE})
COMMANDS.update({f"{code:<9} {c['name']} — currency profile": ("ccy", code) for code, c in CURRENCIES.items()})


def go_to(page=None, ticker=None, view=None, ccy=None):
    st.query_params.clear()
    st.query_params["p"] = page or PAGE
    if ticker:
        st.query_params["t"] = ticker
    if ticker and view and view != "CHART":
        st.query_params["v"] = view
    if ccy and not ticker:
        st.query_params["c"] = ccy
    if st.session_state.get("consent"):
        st.query_params["k"] = st.session_state.consent
    st.session_state.nav = None if (ticker or ccy) else (page or PAGE)


ui.DATA.update(loaded=LOADED, forecasts=FORECASTS, go_to=go_to)


def on_command():
    choice = st.session_state.get("cmd")
    if choice:
        kind, code = COMMANDS[choice]
        if kind == "page":
            go_to(page=code)
        elif kind == "ccy":
            go_to(page="FX", ccy=code)
        else:
            go_to(ticker=code)
        st.session_state.cmd = None


def on_nav():
    if st.session_state.get("nav"):
        go_to(page=st.session_state.nav)


if "nav" not in st.session_state:
    st.session_state.nav = None if (TICKER or CCY) else PAGE

NAV_GROUPS = [("Overview", ["HOME", "NEWS", "CAL", "LEARN"]), ("Economies", ["US", "UK", "EA", "GLOB", "CTRY"]),
              ("Markets", ["MKT", "WEI", "FX", "CMDTY", "CRYPTO", "CRV"]), ("Research", ["LAB", "PMI"]),
              ("Models (PC)", ["ALAB", "BUBBLE", "SMART", "TAKEOVERS", "EVENTLAB"]), ("More", ["HELP", "LEGAL"])]
NAV_NAMES = {"US": "United States", "UK": "United Kingdom", "EA": "Euro area", "MKT": "Markets", "GLOB": "Global",
             "CTRY": "Country profiles", "CRV": "Yield curves", "CAL": "Calendar", "WEI": "World equities",
             "LAB": "Correlation lab", "PMI": "PMI surveys", "ALAB": "Asset Lab", "HELP": "Help", "LEGAL": "Legal"}
_grouped = {c for _, cs in NAV_GROUPS for c in cs}
NAV_GROUPS[-1][1].extend(c for c in PAGES if c not in _grouped)
_counts = {}
for _i in ACTIVE:
    _counts[_i["region"]] = _counts.get(_i["region"], 0) + 1
NAV_COUNT = {"US": _counts.get("US"), "UK": _counts.get("UK"), "EA": _counts.get("EA"), "MKT": _counts.get("Markets"),
             "FX": _counts.get("FX"), "CRYPTO": _counts.get("Crypto")}


def on_nav_group(key):
    if st.session_state.get(key):
        go_to(page=st.session_state[key])


with st.sidebar:
    st.markdown(look.brand_html(PUBLIC), unsafe_allow_html=True)
    for gi, (gname, codes) in enumerate(NAV_GROUPS):
        codes = [c for c in codes if c in PAGES]
        if not codes:
            continue
        gkey = f"nav_g{gi}"
        st.session_state[gkey] = (PAGE if PAGE in codes and not (TICKER or CCY) else None)
        st.markdown(f"<div class='hf-navh'>{gname}</div>", unsafe_allow_html=True)
        st.segmented_control(gname, codes, key=gkey, on_change=on_nav_group, args=(gkey,), label_visibility="collapsed",
                             format_func=lambda c: NAV_NAMES.get(c, PAGES[c][0]))
    st.toggle("Animations", key="anim", value=True,
              help="Page animations, rolling numbers and chart draw-ins. Turn off for a calmer screen.")
    st.markdown("<div class='hf-foot'><i>●</i> DELAYED DATA<br>FRED · ONS · BOE · ECB · BIS · IMF<br>NOT FINANCIAL ADVICE</div>",
                unsafe_allow_html=True)

c_cmd, c_clock = st.columns([4.4, 1.1])
c_cmd.selectbox("Command", list(COMMANDS), index=None, key="cmd", on_change=on_command,
                placeholder="▸ ENTER COMMAND · ticker (UKCPI, GBPUSD, BRENT), currency (USD, GBP), "
                            "page (WEI, NEWS) or keyword (inflation, gilt)",
                label_visibility="collapsed")
clock_text = f"{datetime.now():%a %d %b %Y %H:%M}".upper()
c_clock.markdown("<div class='clock' title='Data is cached for up to 6 hours and may be delayed'>"
                 "<span class='live'>●</span> DELAYED DATA &nbsp;" + clock_text + "</div>",
                 unsafe_allow_html=True)
ui.ticker_tape(TAPE)
ui.disclaimer_bar(legal.DISCLAIMER_SHORT)
ui.keyboard_shortcuts()
ui.show_off_effects()
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
        right.button("INFO", key=f"info_{ind_id}", on_click=go_to, help="Description and key facts",
                     kwargs=dict(ticker=ind["ticker"], view="DES"), width="stretch")
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
    if region in ("US", "UK", "EA"):
        show_scene("heartbeat", scenes.heartbeat_data([(LOADED[i][0], LOADED[i][1]["series"]) for i in ids_for(region)],
                                                     {"US": "US", "UK": "UK", "EA": "EURO AREA"}[region]), 300,
                   "The heartbeat: each month, every growth and jobs indicator's 3-month change compared with its own history, "
                   "pointed so that better is up, then averaged. Faster, taller beats = improving faster; flat = weakening.")
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
        ui.heat_table(table, "Currency", ["1D", "1W", "1M", "3M", "YTD", "1Y"], scale=4,
                      links=lambda r: ui.ccy_link(r["Currency"]) if r["Currency"] in CURRENCIES else None)
        st.caption(f"% change in each currency's value against the {base or 'USD'} "
                   "(green = stronger). ECB reference rates via Frankfurter.")
    except Exception as exc:
        st.caption(f"Currency history unavailable right now ({type(exc).__name__}).")


EMPTY_NEWS = pd.DataFrame(columns=["time", "source", "headline", "link", "topics"])


def load_news():
    try:
        out = fetch_news(tuple(NEWS_FEEDS), tuple((k, tuple(v)) for k, v in NEWS_TOPICS.items()))
        try:
            df = out[0]
            if df is not None and not df.empty:
                look.remember("headlines", [[f"{pd.Timestamp(r['time']):%H:%M}" if pd.notna(r["time"]) else "", str(r["headline"])[:110],
                                             str(r["source"]).upper()[:14]] for _, r in df.head(14).iterrows()])
        except Exception:
            pass
        return out
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
            noise = "FOMC Press Release|Debt to Gross|State Unemployment|Gross Domestic Product by"
            cal = cal[~cal["release_name"].str.contains(noise, case=False)]
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
    every = pd.concat([performance_table(prices, items) for items in groups.values()], ignore_index=True)
    if not every.empty:
        with st.container(border=True):
            ui.panel_title("Winners & losers", "PICK A PERIOD")
            period = st.segmented_control("Period", ["1D", "1W", "1M", "YTD", "1Y"], default="1W",
                                          key=f"{key}_mv")
            ui.ranked_lists(every, "Name", f"{period or '1W'} %", n=5,
                            title_up=f"Top 5 winners ({period or '1W'})", title_down=f"Top 5 losers ({period or '1W'})")
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

HERO_READOUTS = ["sp500", "ftse100", "stoxx50", "nikkei", "gbpusd", "eurusd", "us_10y", "uk_10y", "brent", "gold", "btc"]


def home_hero():
    """v42: every indicator as one particle map (real counts per part of the site) beside the latest closes."""
    regions = [("United States", NAV_COUNT.get("US") or 0, ui.page_link("US")), ("United Kingdom", NAV_COUNT.get("UK") or 0, ui.page_link("UK")),
               ("Euro area", NAV_COUNT.get("EA") or 0, ui.page_link("EA")), ("Markets", NAV_COUNT.get("MKT") or 0, ui.page_link("MKT")),
               ("FX", NAV_COUNT.get("FX") or 0, ui.page_link("FX")), ("Crypto", NAV_COUNT.get("CRYPTO") or 0, ui.page_link("CRYPTO"))]
    ro, newest = [], None
    for ind_id in HERO_READOUTS:
        if ind_id not in LOADED:
            continue
        ind, res = LOADED[ind_id]
        s = res["series"]
        if s is None or len(s) < 2:
            continue
        last, prev = float(s.iloc[-1]), float(s.iloc[-2])
        newest = max(newest, s.index[-1]) if newest is not None else s.index[-1]
        ro.append(dict(name=ind["name"].replace(" (USD)", ""), last=ui.fmt(last, ind), href=ui.link(ind["ticker"], page="MKT"),
                       d=None if ind.get("unit") == "%" or not prev else round((last / prev - 1) * 100, 2)))
    title = "LATEST CLOSES" + (f" · {pd.Timestamp(newest):%d %b %Y}".upper() if newest is not None else "")
    components.html(look.hero(regions, ro[:10], title, load_fonts=CONSENT == "a"), height=450)


def page_home():
    watch = st.session_state.setdefault("watchlist", load_watchlist())
    home_hero()
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
        ui.panel_title("Top headlines", "RSS FEEDS")
        with ui.loading("Checking the news", ["Sending the spider across the news feeds", "Reading BBC, Guardian, CNBC, the Fed and the Bank of England", "Tagging headlines by topic", "Ranking the top stories"], scene="web"):
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
    b2.caption(freshness_text(ind, res))

    # Bloomberg-style function bar: CHART · DES (description) · DRIVERS (what moves it)
    views = ["CHART", "DES"] + (["DRIVERS"] if f and not f.get("error") else [])
    labels = {"CHART": "GP · CHART", "DES": "DES · DESCRIPTION", "DRIVERS": "DRV · DRIVERS"}
    fn_key = f"fn_{k}"
    if fn_key not in st.session_state or st.session_state.get(f"fn_seen_{k}") != VIEW:
        st.session_state[fn_key] = VIEW if VIEW in views else "CHART"
        st.session_state[f"fn_seen_{k}"] = VIEW
    view = st.segmented_control("Function", views, format_func=lambda v: labels[v], key=fn_key,
                                on_change=lambda: go_to(ticker=ticker, view=st.session_state[fn_key]),
                                label_visibility="collapsed") or "CHART"
    if view == "DES":
        des_view(ind, res)
        return
    if view == "DRIVERS":
        drivers_view(ind, res, f)
        return

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
            ui.signal_table(f["table"], f["dir"])
            st.button("Open the drivers screen ↗", key=f"drv_btn_{k}", on_click=go_to,
                      kwargs=dict(ticker=ticker, view="DRIVERS"))
            if ind_id in MARKET_FORECASTS:
                st.markdown("<div class='disc'>" + ui.escape(TERMS["market forecast"]) + "</div>",
                            unsafe_allow_html=True)
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


def fx_rate_info(code):
    """Latest policy rate for a currency: from our own indicators, else the BIS board."""
    cur = CURRENCIES.get(code, {})
    pid = cur.get("policy_id")
    if pid and pid in LOADED and LOADED[pid][1]["series"] is not None:
        s = LOADED[pid][1]["series"]
        return float(s.iloc[-1]), s.index[-1]
    try:
        rates = fetch_policy_rates(tuple(sorted({c["bis"] for c in COUNTRIES.values()} |
                                                {c["bis"] for c in CURRENCIES.values()})))
        s = rates[cur.get("bis")].dropna()
        return float(s.iloc[-1]), s.index[-1]
    except Exception:
        return None, None


REGION_NAMES = {"US": "United States", "UK": "United Kingdom", "EA": "Euro area (20 countries)",
                "Markets": "Global markets", "FX": "Currencies", "Crypto": "Crypto"}


def econ_facts(ind, res, freq):
    """Key facts for an economic series: latest, previous, history, records and the forecast."""
    s = res["series"].dropna()
    ind_id = ind["id"]
    last = float(s.iloc[-1])
    rows = [("Country / area", REGION_NAMES.get(ind["region"], ind["region"])), ("Category", ind["group"]),
            ("Release", RELEASES.get(ind_id, freq)), ("Frequency", freq),
            ("Latest", f"<b>{ui.fmt(last, ind)}</b> <span class='hs'>({ui.date_label(ind, s.index[-1])})</span>")]
    if res["previous"] is not None:
        rows.append(("Previous", f"{ui.fmt(res['previous'], ind)} &nbsp;{ui.change_html(ind, last - res['previous'])}"))
    year_ago = s.asof(s.index[-1] - pd.DateOffset(years=1))
    if not pd.isna(year_ago):
        rows.append(("A year ago", f"{ui.fmt(year_ago, ind)} &nbsp;{ui.change_html(ind, last - float(year_ago))}"))
    five = s[s.index >= s.index[-1] - pd.DateOffset(years=5)]
    rows.append(("5-year average", ui.fmt(five.mean(), ind)))
    rows.append(("Long-run average", f"{ui.fmt(s.mean(), ind)} <span class='hs'>(since {s.index[0]:%Y})</span>"))
    pct = percentile_rank(s)
    if pct is not None:
        rows.append(("20-year percentile", f"{pct:.0f} / 100 {ui.percentile_bar(pct, ind)}", "percentile"))
    rows += [("Record high", f"{ui.fmt(s.max(), ind)} <span class='hs'>({ui.date_label(ind, s.idxmax())})</span>"),
             ("Record low", f"{ui.fmt(s.min(), ind)} <span class='hs'>({ui.date_label(ind, s.idxmin())})</span>")]
    target = {"uk_cpi": 2.0, "us_cpi": 2.0, "us_core_cpi": 2.0, "ea_hicp": 2.0, "ea_core": 2.0}.get(ind_id)
    if target is not None:
        gap = last - target
        rows.append(("Vs 2% target", f"{gap:+.1f}pp {'above' if gap > 0 else 'below'} target", "inflation target"))
    f = FORECASTS.get(ind_id)
    if f and not f.get("error"):
        end = f["fc"].iloc[-1]
        rows.append(("12M forecast", f"{ui.ARROWS[f['dir']]} {ui.fmt(end['median'], ind)} by {f['fc'].index[-1]:%b %Y} "
                     f"&nbsp;{ui.conf_html(f['stars'])} <a class='drv' href='{ui.link(ind['ticker'], view='DRIVERS')}' "
                     f"target='_self'>drivers ↗</a>", "forecast"))
    return rows


def what_moves_it(ind):
    """Links to the indicators that usually push this one up or down."""
    signals = [(sid, rel) for sid, rel in SIGNALS.get(ind["id"], []) if sid in LOADED]
    if not signals:
        return
    ui.panel_title("What moves it", "CLICK FOR INFO")
    rows = []
    for sid, rel in signals:
        s_ind, s_res = LOADED[sid]
        latest = "-" if s_res["error"] else ui.fmt(s_res["latest"], s_ind)
        rows.append((s_ind["name"], f"<a class='drv' href='{ui.link(s_ind['ticker'], view='DES')}' target='_self'>"
                     f"{s_ind['ticker']} ↗</a> &nbsp;{latest} &nbsp;<span class='hs'>"
                     f"{'moves WITH it' if rel > 0 else 'moves AGAINST it'}</span>"))
    ui.des_table(rows)


def page_currency(code):
    """Currency profile (like Bloomberg's currency DES): who issues it, its rate, how it's doing."""
    c = CURRENCIES[code]
    b1, b2 = st.columns([0.8, 7.3])
    b1.button("◄ FX", on_click=go_to, kwargs=dict(page="FX"), width="stretch")
    rate, rate_date = fx_rate_info(code)
    b2.markdown(f"<div class='pt'><b style='font-size:.95rem'>{code} · {ui.escape(c['name'])}</b>"
                f"<span>CURRENCY PROFILE · {ui.escape(c['country']).upper()}</span></div>",
                unsafe_allow_html=True)
    left, mid, right = st.columns([1.2, 1.1, 1.2], gap="small")

    with left, st.container(border=True):
        ui.panel_title("Description", "DES")
        st.markdown(f"<div class='des-head'>{ui.escape(c['name'])} ({code})</div>"
                    f"<div class='des-note'>The official currency of {ui.escape(c['country'])}, issued by the "
                    f"{ui.autolink(c['bank'], exclude=None)}.</div>", unsafe_allow_html=True)
        rows = [("Code", code), ("Country / area", c["country"]), ("Central bank", c["bank"]),
                ("Regime", c["regime"], "currency pair")]
        pid = c.get("policy_id")
        if rate is not None:
            value = f"{rate:.2f}% <span class='hs'>({rate_date:%b %Y})</span>"
            if pid and pid in LOADED:
                value += f" <a class='drv' href='{ui.link(LOADED[pid][0]['ticker'])}' target='_self'>chart ↗</a>"
            rows.append(("Policy rate", value, "policy rate"))
        pairs = [(i, FX_PAIRS[i]) for i in FX_PAIRS if code in FX_PAIRS[i][:2] and i in LOADED]
        if pairs:
            rows.append(("Pairs on HF Macro", " ".join(
                f"<a class='drv' href='{ui.link(LOADED[i][0]['ticker'], view='DES')}' target='_self'>"
                f"{LOADED[i][0]['ticker']}</a>" for i, _ in pairs)))
        nick = [p[2] for _, p in pairs if p[2]]
        if nick:
            rows.append(("Nicknames", ", ".join(nick)))
        rows += [(k2, v2) for k2, v2 in FX_COMMON.items() if k2 != "Type"]
        ui.des_table(rows)

    with mid, st.container(border=True):
        ui.panel_title("Performance", f"{code} VS EACH BASE")
        try:
            perf = []
            for base in ("USD", "GBP", "EUR"):
                if base == code:
                    continue
                strength = currency_strength(fetch_fx_history(base, tuple(HEATMAP_CURRENCIES)))
                if code in strength.index:
                    row = strength.loc[code]
                    perf.append({"Against": base, **{p: row[p] for p in ("1D", "1W", "1M", "3M", "YTD", "1Y")}})
            if perf:
                ui.heat_table(pd.DataFrame(perf), "Against", ["1D", "1W", "1M", "YTD", "1Y"], scale=4,
                              links=lambda r: ui.ccy_link(r["Against"]))
                st.caption(f"% change in the value of 1 {code} (green = {code} stronger).")
            period = st.segmented_control("Period", ["1W", "1M", "3M", "YTD", "1Y"], default="1M",
                                          key=f"ccy_mv_{code}")
            vs = currency_strength(fetch_fx_history(code, tuple(HEATMAP_CURRENCIES)))
            vs = vs[vs.index != code]
            col = period or "1M"
            # vs[col] = how much each OTHER currency gained against this one; flip it to this one's view
            mine = pd.DataFrame({"Currency": vs.index, "Change": (100 / (1 + vs[col] / 100) - 100).values})
            mine["link"] = [ui.ccy_link(x) if x in CURRENCIES else None for x in mine["Currency"]]
            mine["Currency"] = [f"vs {x} · {CURRENCIES.get(x, {}).get('name', x)}" for x in mine["Currency"]]
            ui.ranked_lists(mine, "Currency", "Change", n=5, link_col="link",
                            title_up=f"{code} gained most against ({col})",
                            title_down=f"{code} lost most against ({col})")
        except Exception as exc:
            st.caption(f"Currency history unavailable right now ({type(exc).__name__}).")

    with right, st.container(border=True):
        other = "EUR" if code == "USD" else "USD"
        ui.panel_title(f"1 {code} in {other}", "LAST 12 MONTHS")
        try:
            rates = fetch_fx_history(other, (code,))
            line = (1 / rates[code]).dropna()
            line = line[line.index >= line.index[-1] - pd.DateOffset(years=1)]
            fig = go.Figure(go.Scatter(x=line.index, y=line.values, mode="lines",
                                       line=dict(color=ui.CYAN, width=1.6),
                                       hovertemplate="%{x|%d %b %Y}: %{y:.4f}<extra></extra>"))
            st.plotly_chart(ui.base_layout(fig, 240), width="stretch", config=ui.PLOT_CONFIG,
                            key=f"ccy_chart_{code}")
            st.caption("ECB reference rates via Frankfurter.")
        except Exception as exc:
            st.caption(f"Chart unavailable right now ({type(exc).__name__}).")
        ui.panel_title("Latest news", "GOOGLE NEWS")
        ui.headlines(search_news(f'"{c["name"]}"'), limit=6, empty="No recent headlines found.")


def des_view(ind, res):
    """DES: what this instrument is, the key facts, and its performance and risk numbers."""
    ind_id, s = ind["id"], res["series"]
    is_price = ind["unit"] != "%"
    daily = ui.is_daily(ind)
    stats = market_stats(s, pct=is_price, daily=daily)
    unit = "%" if is_price else "pp"
    left, mid, right = st.columns([1.25, 1.1, 1.1], gap="small")

    with left, st.container(border=True):
        ui.panel_title("Description", "DES")
        rows = []
        if ind_id in FX_PAIRS:
            base, quote, nick = FX_PAIRS[ind_id]
            b, q = CURRENCIES[base], CURRENCIES[quote]
            st.markdown(f"<div class='des-head'>{base}{quote} spot exchange rate: price of 1 {ui.ccy_html(base)} "
                        f"in {ui.ccy_html(quote)}</div>"
                        f"<div class='des-note'>The {ui.ccy_html(base, b['name'])} is the official currency of "
                        f"{b['country']}. The {ui.ccy_html(quote, q['name'])} is the official currency of "
                        f"{q['country']}. Click a currency for its full profile.</div>", unsafe_allow_html=True)
            rows += [(k2, v2) for k2, v2 in FX_COMMON.items()]
            rows.append(("Currency profiles", f"<a class='drv' href='{ui.ccy_link(base)}' target='_self'>{base} ↗</a> "
                                              f"<a class='drv' href='{ui.ccy_link(quote)}' target='_self'>{quote} ↗</a>"))
            rows += [("Nickname", nick or "-"),
                     (f"{base} central bank", b["bank"]), (f"{quote} central bank", q["bank"]),
                     (f"{base} regime", b["regime"], "currency pair"), (f"{quote} regime", q["regime"])]
            rb, rb_date = fx_rate_info(base)
            rq, rq_date = fx_rate_info(quote)
            if rb is not None:
                rows.append((f"{base} policy rate", f"{rb:.2f}% <span class='hs'>({rb_date:%b %Y})</span>", "policy rate"))
            if rq is not None:
                rows.append((f"{quote} policy rate", f"{rq:.2f}% <span class='hs'>({rq_date:%b %Y})</span>"))
            if rb is not None and rq is not None:
                diff = rb - rq
                rows.append(("Rate differential", "None: both rates are the same" if abs(diff) < 0.005 else
                             f"{abs(diff):.2f}pp in favour of {base if diff > 0 else quote}", "rate differential"))
        elif ind_id in INDICES:
            facts = INDICES[ind_id]
            st.markdown(f"<div class='des-head'>{ui.escape(ind['name'])}: stock index</div>"
                        f"<div class='des-note'>{ui.autolink(facts['Note'], exclude=ind['ticker'])}</div>"
                        f"<div class='des-note' style='color:#AEB8C2'>{ui.autolink(ABOUT.get(ind_id, ''), exclude=ind['ticker'])}</div>",
                        unsafe_allow_html=True)
            rows += [(k2, v2) for k2, v2 in facts.items() if k2 != "Note"]
        elif ind_id in COMMODITIES:
            facts = COMMODITIES[ind_id]
            st.markdown(f"<div class='des-head'>{ui.escape(ind['name'])}: commodity</div>"
                        f"<div class='des-note'>{ui.autolink(facts['Note'], exclude=ind['ticker'])}</div>"
                        f"<div class='des-note' style='color:#AEB8C2'>{ui.autolink(ABOUT.get(ind_id, ''), exclude=ind['ticker'])}</div>",
                        unsafe_allow_html=True)
            rows += [(k2, v2) for k2, v2 in facts.items() if k2 != "Note"]
        elif ind_id in CRYPTO:
            facts = CRYPTO[ind_id]
            st.markdown(f"<div class='des-head'>{ui.escape(ind['name'])}: cryptocurrency</div>"
                        f"<div class='des-note'>{ui.autolink(facts['Note'], exclude=ind['ticker'])}</div>",
                        unsafe_allow_html=True)
            rows += [(k2, v2) for k2, v2 in facts.items() if k2 != "Note"]
        else:
            st.markdown(f"<div class='des-head'>{ui.escape(ind['name'])}</div>"
                        f"<div class='des-note'>{ui.autolink(ABOUT.get(ind_id, ''), region=ind['region'], exclude=ind['ticker'])}</div>",
                        unsafe_allow_html=True)
            freq = {"M": "Monthly", "Q": "Quarterly", "D": "Daily / weekly"}.get(
                "D" if daily else ("Q" if (s.index[-1] - s.index[-2]).days > 60 else "M"), "")
            rows += econ_facts(ind, res, freq)
        url = source_url(ind)
        src = SOURCE_NAMES.get(ind["source"], ind["source"])
        rows += [("Source", f"<a href='{url}' target='_blank'>{ui.escape(src)} ↗</a>" if url else ui.escape(src)),
                 ("Series code", ui.escape(ind["code"])),
                 ("History", f"{res['first_date']:%b %Y} to {res['latest_date']:%d %b %Y}"),
                 ("Freshness", ui.escape(freshness_text(ind, res)))]
        ui.des_table(rows)
        what_moves_it(ind)

    with mid, st.container(border=True):
        ui.panel_title("Performance", "CHANGE")
        perf = [(label, ui.pct_html(stats.get(label), 2, unit)) for label in ("1D", "1W", "1M", "3M", "YTD", "1Y")
                if stats.get(label) is not None]
        perf += [("52-week high", ui.fmt(stats["52W high"], ind)), ("52-week low", ui.fmt(stats["52W low"], ind))]
        if stats.get("52W position") is not None:
            perf.append(("Position in 52W range", f"{stats['52W position']:.0f}% "
                         + ui.percentile_bar(stats["52W position"], ind)))
        ui.des_table(perf)
        if stats.get("Volatility 1Y") is not None:
            ui.panel_title("Risk", "ANNUALISED")
            risk = [("Volatility 1M", f"{stats['Volatility 1M']:.1f}%" if stats.get("Volatility 1M") else "-"),
                    ("Volatility 1Y", f"{stats['Volatility 1Y']:.1f}%"),
                    ("Max drawdown 1Y", ui.pct_html(stats["Max drawdown 1Y"], 1))]
            bench = BENCHMARK.get(ind["region"])
            if bench and bench != ind_id and bench in LOADED and LOADED[bench][1]["series"] is not None:
                corr = return_correlation(s, LOADED[bench][1]["series"])
                if corr is not None:
                    risk.append((f"Correlation with {LOADED[bench][0]['ticker']} (1Y)", f"{corr:+.2f}", "correlation"))
            ui.des_table(risk)

    with right, st.container(border=True):
        ui.panel_title("Last 3 months", "PRICE")
        recent = s[s.index >= s.index[-1] - pd.DateOffset(months=3)]
        fig = ui.build_figure(ind, recent, height=230)
        st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"des_chart_{ind_id}")
        related = [i["id"] for i in ACTIVE if i["group"] == ind["group"] and i["id"] != ind_id
                   and i["id"] in LOADED][:8]
        if related:
            ui.panel_title(f"More in {ind['group']}")
            st.markdown(" ".join(f"<a class='drv' href='{ui.link(LOADED[r][0]['ticker'], view='DES')}' "
                                 f"target='_self'>{LOADED[r][0]['ticker']}</a>" for r in related),
                        unsafe_allow_html=True)
        revisions_panel(ind)
    with st.container(border=True):
        ui.panel_title("Research & news", "LAST 30 DAYS")
        ui.headlines(search_news(news_query(ind)), limit=8, empty="News search unavailable right now.")
    expectations_panel(ind)



# ================================================================= model comparison, expectations, freshness

FREQ_WORDS = {"M": "monthly", "Q": "quarterly", "D": "daily"}
INFO_KEY = {"No change": "no change", "VAR(2)": "VAR", "Phillips curve": "Phillips curve",
            "Average of models": "ensemble", "AR(2)": "forecast"}


def fmt_err(value, ind):
    """A forecast error: percentage-point units for % series."""
    return f"{value:,.{ind['decimals']}f}" + ("pp" if ind["unit"] == "%" else ind["unit"])


def freshness_text(ind, res):
    """'Latest data 16 Oct 2026 · released monthly · checked 2 hours ago'"""
    from forecast import infer_freq
    s = res["series"]
    freq = "D" if ui.is_daily(ind) else infer_freq(s)
    parts = [f"Latest data {ui.date_label(ind, res['latest_date'])}",
             f"published {FREQ_WORDS.get(freq, 'regularly')}"]
    checked = res.get("checked")
    if checked is not None:
        mins = max(0, int((pd.Timestamp.now(tz="Europe/London") - checked).total_seconds() // 60))
        parts.append("checked just now" if mins < 2 else f"checked {mins} min ago" if mins < 90
                     else f"checked {mins // 60} hours ago")
    return " · ".join(parts)


def model_comparison(ind, res, f):
    """Every model that applies, its 12-month forecast and its 10-year track record."""
    ind_id = ind["id"]
    with st.container(border=True):
        ui.panel_title("Model comparison & track record", "10-YEAR BACKTEST", about="backtest")
        with ui.loading("Testing each model on the last 10 years", ["Loading history", "Walking forward year by year", "Scoring the forecasts", "Ranking the models"]):
            try:
                results = models.evaluate_cached(ind_id, LOADED)
            except Exception as exc:
                st.caption(f"Backtest unavailable ({type(exc).__name__}).")
                return
        ar_end = float(f["fc"]["median"].iloc[-1])
        for r in results:
            if r["name"] == "AR(2)":
                r["end"], r["forecast"] = ar_end, f["fc"]
        ends = [r["end"] for r in results if r["name"] not in ("No change", "Average of models") and r["end"] is not None]
        for r in results:
            if r["name"] == "Average of models" and ends:
                r["end"] = float(sum(ends) / len(ends))
        naive = next((r["mae"] for r in results if r["name"] == "No change"), None)
        scored = [r for r in results if r["mae"] is not None]
        best = min(scored, key=lambda r: r["mae"]) if scored else None

        left, right = st.columns([1.25, 1], gap="small")
        with left:
            rows = []
            for r in results:
                hit_txt = "-" if r["hit_rate"] is None else f"{r['hit_rate']:.0f}%"
                miss_txt = "-" if r["mae"] is None else f"{r['mae']:,.{ind['decimals']}f}" + (
                    "pp" if ind["unit"] == "%" else ind["unit"])
                skill = "-" if (r["mae"] is None or naive in (None, 0) or r["name"] == "No change") else \
                    f"{(1 - r['mae'] / naive) * 100:+.0f}%"
                tag = " <span class='up'>★ best</span>" if best is r else ""
                rows.append(
                    f"<tr><td>{ui.escape(r['name'])}{ui.info(INFO_KEY.get(r['name'], 'forecast'), r['name'])}{tag}</td>"
                    f"<td class='n'>{ui.fmt(r['end'], ind) if r['end'] is not None else '-'}</td>"
                    f"<td class='n'>{miss_txt}</td>"
                    f"<td class='n'>{hit_txt}</td>"
                    f"<td class='n'>{skill}</td></tr>")
            st.markdown("<table class='t'><tr><th>Model</th><th style='text-align:right'>12M forecast</th>"
                        f"<th style='text-align:right'>Avg miss{ui.info('average miss', 'Average miss')}</th>"
                        f"<th style='text-align:right'>Direction{ui.info('direction hit rate', 'Direction hit rate')}</th>"
                        "<th style='text-align:right'>vs no change</th></tr>" + "".join(rows) + "</table>",
                        unsafe_allow_html=True)
            if best is not None and naive:
                if best["name"] == "No change":
                    verdict = ("No model has beaten the simple 'no change' forecast here over the last 10 years. "
                               "That's common for market prices and a useful reminder of how hard forecasting is.")
                else:
                    verdict = (f"Best track record: **{best['name']}**, whose average miss was "
                               f"{(1 - best['mae'] / naive) * 100:.0f}% smaller than just assuming no change.")
                st.markdown(verdict)
            st.caption("Each model is re-run at every month of the last 10 years using only the data available "
                       "then, and compared with what actually happened (pandemic months left out). It uses "
                       "today's revised data, so real-time accuracy would be a little worse.")
        with right:
            fig = go.Figure()
            hist = ui.window(res["series"], 5)
            if ui.is_daily(ind):
                hist = hist.resample("MS").mean()
            fig.add_scatter(x=hist.index, y=hist.values, mode="lines", name="Actual",
                            line=dict(color=ui.TEXT, width=1.4))
            colours = {"AR(2)": ui.CYAN, "VAR(2)": "#C792EA", "Phillips curve": "#5EE6C9"}
            for r in results:
                fc = r.get("forecast")
                if fc is None or r["name"] not in colours:
                    continue
                fig.add_scatter(x=[hist.index[-1]] + list(fc.index), y=[hist.iloc[-1]] + list(fc["median"]),
                                mode="lines", name=r["name"], line=dict(color=colours[r["name"]], dash="dot", width=2))
            st.plotly_chart(ui.base_layout(fig, 260, unit=ind["unit"] if ind["unit"] == "%" else "", legend=True),
                            width="stretch", config=ui.PLOT_CONFIG, key=f"models_{ind_id}")
            ar_res = next((r["results"] for r in results if r["name"] == "AR(2)" and r["results"] is not None), None)
            if ar_res is not None and len(ar_res):
                with st.expander("How the AR(2) forecasts did in the past"):
                    fig2 = go.Figure()
                    fig2.add_scatter(x=ar_res["target"], y=ar_res["actual"], mode="lines", name="What happened",
                                     line=dict(color=ui.TEXT, width=1.3))
                    fig2.add_scatter(x=ar_res["target"], y=ar_res["pred"], mode="lines", name="What AR(2) forecast 12M earlier",
                                     line=dict(color=ui.CYAN, dash="dot"))
                    st.plotly_chart(ui.base_layout(fig2, 220, legend=True), width="stretch",
                                    config=ui.PLOT_CONFIG, key=f"bt_{ind_id}")


SEP_SERIES = {
    "us_fedfunds": [("FEDTARMD", "Fed funds rate, end of year"), ("FEDTARMDLR", "Fed funds rate, longer run")],
    "us_2y": [("FEDTARMD", "Fed funds rate, end of year")],
    "us_cpi": [("PCECTPIMD", "PCE inflation, Q4 on Q4 (the Fed's preferred measure, usually a little below CPI)")],
    "us_core_cpi": [("JCXFEMD", "Core PCE inflation, Q4 on Q4")],
    "us_unemp": [("UNRATEMD", "Unemployment rate, Q4 average")],
    "us_gdp": [("GDPC1MD", "Real GDP growth, Q4 on Q4")],
}
IMF_FOR = {"us_cpi": ("PCPIPCH", "USA", "inflation"), "uk_cpi": ("PCPIPCH", "GBR", "inflation"),
           "us_gdp": ("NGDP_RPCH", "USA", "annual GDP growth"), "uk_gdp": ("NGDP_RPCH", "GBR", "annual GDP growth"),
           "us_unemp": ("LUR", "USA", "unemployment rate"), "uk_unemp": ("LUR", "GBR", "unemployment rate")}
MARKET_FOR = {"us_fedfunds", "us_2y", "us_cpi", "us_core_cpi", "us_10y"}


def latest_fred(code):
    s = fetch_fred(code, get_fred_key())
    return s.dropna()


def expectations_panel(ind):
    """What markets, the Fed and the IMF expect, next to the site's own models."""
    ind_id = ind["id"]
    if ind_id not in SEP_SERIES and ind_id not in IMF_FOR and ind_id not in MARKET_FOR:
        return
    with st.container(border=True):
        ui.panel_title("What others expect", "MARKETS · FED · IMF", about="market-implied")
        cols = st.columns(3, gap="small")
        with cols[0]:
            st.markdown("**Markets**")
            shown = False
            if ind_id in ("us_fedfunds", "us_2y", "us_10y"):
                try:
                    ys = {k: float(latest_fred(c).iloc[-1]) for k, c in
                          (("3M", "DGS3MO"), ("6M", "DGS6MO"), ("1Y", "DGS1"), ("2Y", "DGS2"))}
                    path = models.implied_path(ys)
                    ui.des_table([(k, f"{v:.2f}%") for k, v in path.items()] +
                                 [("Fed funds now", ui.fmt(LOADED["us_fedfunds"][1]["latest"], LOADED["us_fedfunds"][0])
                                   if "us_fedfunds" in LOADED and LOADED["us_fedfunds"][1]["latest"] is not None else "-")])
                    st.caption("Short-term interest rates the Treasury market is pricing for the future (forward "
                               "rates from 3-month to 2-year yields). Approximate: they include a small term "
                               "premium " + "(see the (i)).")
                    st.markdown(ui.info("forward rate", "Forward rate") + ui.info("term premium", "Term premium"),
                                unsafe_allow_html=True)
                    shown = True
                except Exception:
                    st.caption("Treasury yields unavailable right now.")
            if ind_id in ("us_cpi", "us_core_cpi"):
                rows = [(LOADED[i][0]["name"], ui.fmt(LOADED[i][1]["latest"], LOADED[i][0]))
                        for i in ("us_be5", "us_breakeven", "us_5y5y") if i in LOADED and LOADED[i][1]["latest"] is not None]
                if rows:
                    ui.des_table(rows)
                    st.caption("Average inflation the bond market expects (from inflation-protected Treasuries). "
                               "These measure CPI inflation.")
                    shown = True
            if not shown:
                st.caption("No market measure for this one.")
        with cols[1]:
            st.markdown("**The Fed (latest projections)**")
            if ind_id in SEP_SERIES and get_fred_key():
                rows = []
                for code, label in SEP_SERIES[ind_id]:
                    try:
                        s = latest_fred(code)
                        if code.endswith("LR"):
                            rows.append((label, f"{s.iloc[-1]:.1f}%"))
                        else:
                            rows += [(f"{label} · {d:%Y}", f"{v:.1f}%") for d, v in s.items()
                                     if d.year >= pd.Timestamp.now().year]
                    except Exception:
                        continue
                if rows:
                    ui.des_table(rows)
                    st.markdown("Median of Fed officials' projections " + ui.info("SEP", "SEP"), unsafe_allow_html=True)
                else:
                    st.caption("Fed projections unavailable right now.")
            else:
                st.caption("The Fed doesn't publish a projection for this.")
        with cols[2]:
            st.markdown("**IMF (World Economic Outlook)**")
            spec = IMF_FOR.get(ind_id)
            if spec:
                code, country, label = spec
                year = pd.Timestamp.now().year
                try:
                    table = fetch_imf(code, tuple(range(year - 1, year + 3)))
                    if country in table.index and "projections" in table.attrs.get("source", ""):
                        row = table.loc[country]
                        ui.des_table([(f"{label.capitalize()} · {y}", f"{float(v):.1f}%")
                                      for y, v in row.items() if not pd.isna(v)])
                        st.caption("Annual figures (calendar-year averages), so not directly comparable with "
                                   "monthly or quarterly readings.")
                    else:
                        st.caption("IMF projections unavailable right now.")
                except Exception:
                    st.caption("IMF projections unavailable right now.")
            else:
                st.caption("No IMF projection for this.")


def revisions_panel(ind):
    """First published estimate vs today's figure (US GDP)."""
    if ind["id"] != "us_gdp" or not get_fred_key():
        return
    ui.panel_title("First estimate vs latest", "REVISIONS", about="first estimate")
    try:
        first = fetch_fred_first_release(ind["code"], get_fred_key())
        latest = LOADED[ind["id"]][1]["series"]
        both = pd.concat({"First estimate": first, "Latest": latest}, axis=1).dropna()
        both = both[both.index >= both.index[-1] - pd.DateOffset(years=8)]
        if both.empty:
            raise ValueError("no overlap")
        fig = go.Figure()
        fig.add_bar(x=both.index, y=both["First estimate"], name="First estimate", marker_color="#55606C")
        fig.add_bar(x=both.index, y=both["Latest"], name="Latest", marker_color=ui.CYAN)
        fig.update_layout(barmode="group")
        st.plotly_chart(ui.base_layout(fig, 230, unit="%", legend=True), width="stretch",
                        config=ui.PLOT_CONFIG, key="rev_us_gdp")
        avg = (both["Latest"] - both["First estimate"]).abs().mean()
        st.caption(f"Over these years the first GDP estimate was revised by {avg:.1f}pp on average. "
                   "Source: FRED/ALFRED archive.")
    except Exception as exc:
        st.caption(f"Revision history unavailable right now ({type(exc).__name__}).")


def forecast_scorecard():
    """Every forecast's 10-year track record against 'no change'."""
    st.markdown("How good is each forecast? Every model is tested on the last 10 years "
                + ui.info("backtest", "Backtest"), unsafe_allow_html=True)
    rows = []
    with ui.loading("Backtesting every forecast", ["Loading history", "Re-running past forecasts", "Measuring hits and misses", "Building the scorecard"]):
        for ind_id in FORECASTS:
            if FORECASTS[ind_id].get("error"):
                continue
            ind = LOADED[ind_id][0]
            try:
                sc = models.evaluate_cached(ind_id, LOADED, simple=True)
            except Exception:
                continue
            ar_, nv = sc.get("AR(2)"), sc.get("No change")
            if not ar_ or not nv or not nv["mae"]:
                continue
            rows.append({"Indicator": f"{ind['ticker']} · {ind['name']}", "link": ui.link(ind["ticker"], view="DRIVERS"),
                         "skill": (1 - ar_["mae"] / nv["mae"]) * 100, "hit": ar_["hit_rate"],
                         "miss": ar_["mae"], "naive": nv["mae"], "ind": ind})
    if not rows:
        st.caption("No forecasts to test right now.")
        return
    rows.sort(key=lambda r: -r["skill"])
    body = []
    for r in rows:
        cls = "up" if r["skill"] > 0 else "dn"
        hit_txt = "-" if r["hit"] is None else f"{r['hit']:.0f}%"
        body.append(f"<tr><td><a href='{r['link']}' target='_self'>{ui.escape(r['Indicator'])}</a></td>"
                    f"<td class='n'>{fmt_err(r['miss'], r['ind'])}</td><td class='n'>{fmt_err(r['naive'], r['ind'])}</td>"
                    f"<td class='n'><span class='{cls}'>{r['skill']:+.0f}%</span></td>"
                    f"<td class='n'>{hit_txt}</td></tr>")
    beat = sum(1 for r in rows if r["skill"] > 0)
    st.markdown(f"**The main AR(2) model beat 'no change' for {beat} of {len(rows)} indicators** over the last "
                "10 years. It tends to do better on slow-moving economic data (inflation, unemployment, rates) "
                "than on market prices, which are close to unpredictable.")
    st.markdown("<table class='t'><tr><th>Indicator</th><th style='text-align:right'>AR(2) avg miss</th>"
                "<th style='text-align:right'>No-change avg miss</th>"
                f"<th style='text-align:right'>Improvement{ui.info('no change', 'No change')}</th>"
                f"<th style='text-align:right'>Direction right{ui.info('direction hit rate', 'Direction hit rate')}</th></tr>"
                + "".join(body) + "</table>", unsafe_allow_html=True)
    st.caption("Click any row to open its drivers screen, where inflation, unemployment and interest rates are "
               "also compared with the VAR and Phillips curve models. " + ui.DISCLAIMER)


def drivers_view(ind, res, f):
    """DRIVERS: the forecast, then a chart for each of the five indicators behind its confidence score."""
    ind_id = ind["id"]
    signals = SIGNALS.get(ind_id, [])
    top_l, top_r = st.columns([1.6, 1], gap="small")
    with top_l, st.container(border=True):
        ui.panel_title(f"{ind['name']}: forecast", "5Y + 12M FORECAST", about="forecast")
        fig = ui.build_figure(ind, ui.window(res["series"], 5), height=280, forecast=f["fc"])
        st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"drv_main_{ind_id}")
    with top_r, st.container(border=True):
        end = f["fc"].iloc[-1]
        ui.panel_title("Verdict", "CONFIDENCE", about="confidence")
        st.markdown(
            f"<div class='des-head'>Forecast: {ui.WORDS[f['dir']].upper()} to {ui.fmt(end['median'], ind)} "
            f"by {f['fc'].index[-1]:%b %Y}</div>"
            f"<div class='hs'>80% range {ui.fmt(end['low'], ind)} to {ui.fmt(end['high'], ind)}</div>"
            f"<div style='margin:10px 0'>{ui.conf_html(f['stars'])} &nbsp; <b>{f['agree']} of {f['counted']}</b> "
            f"drivers point the same way</div>", unsafe_allow_html=True)
        st.markdown("<div class='des-note'>" + ui.escape(
            "Each driver below shows the last 5 years, with the last 6 months shaded: that's the move the "
            "confidence score looks at. The history check shows whether the rule of thumb has actually "
            "held over the past 10 years.") + "</div>", unsafe_allow_html=True)
        if ind_id in MARKET_FORECASTS:
            st.caption(TERMS["market forecast"])

    table = f["table"].set_index("id") if "id" in f["table"].columns else None
    for start in range(0, len(signals), 3):
        cols = st.columns(3, gap="small")
        for col, (sig_id, rel) in zip(cols, signals[start:start + 3]):
            with col, st.container(border=True):
                if sig_id not in LOADED or LOADED[sig_id][1]["series"] is None:
                    st.markdown(f"<div class='pt'><b>{ui.escape(sig_id)}</b></div>", unsafe_allow_html=True)
                    st.caption("Not available in this edition.")
                    continue
                s_ind, s_res = LOADED[sig_id]
                row = table.loc[sig_id] if table is not None and sig_id in table.index else None
                agrees = row is not None and row["Agrees"] == "yes"
                verdict = ("<span class='up'>■ AGREES</span>" if agrees else "<span class='dn'>□ DISAGREES</span>"
                           if row is not None and row["Agrees"] == "no" else "<span class='nc'>-</span>")
                corr, check = history_check(res["series"], s_res["series"], rel)
                st.markdown(
                    f"<div class='pt'><b><a href='{ui.link(s_ind['ticker'])}' target='_self'>{ui.escape(s_ind['name'])}</a>"
                    f"{ui.info(sig_id, s_ind['name'])}</b><span>{s_ind['ticker']}</span></div>"
                    f"<div class='hs'>Usually moves {'WITH' if rel > 0 else 'AGAINST'} {ind['ticker']} · "
                    f"last 6M: {ui.escape(str(row['Moved'])) if row is not None else '-'}</div>"
                    f"<div>Points <b>{ui.escape(str(row['Implies']).upper()) if row is not None else '-'}</b> → {verdict}</div>",
                    unsafe_allow_html=True)
                window = ui.window(s_res["series"], 5)
                recent_start = window.index[-1] - pd.DateOffset(months=6)
                fig = ui.build_figure(s_ind, window, height=190,
                                      shades=[("last 6 months", [(recent_start, window.index[-1])],
                                               "rgba(232,33,43,0.14)")])
                st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"drv_{ind_id}_{sig_id}")
                st.markdown(f"<div class='hs'>History check (10Y, 6-month moves): "
                            f"{'-' if corr is None else f'{corr:+.2f}'} · {ui.escape(check)}"
                            f"{ui.info('correlation', 'Correlation')}</div>", unsafe_allow_html=True)
    model_comparison(ind, res, f)
    expectations_panel(ind)


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


def world_day():
    """The trading day around the world: latest daily move of each stock market (PC: Yahoo; website: the indices it can show)."""
    data = None
    if not PUBLIC:
        try:
            tick = tuple(t for items in EQUITY_MONITOR.values() for t, _ in items)
            perf = pd.concat([performance_table(fetch_yahoo_batch(tick), items) for items in EQUITY_MONITOR.values()], ignore_index=True)
            data = scenes.markets_data(perf)
        except Exception:
            data = None
    if data is None:                         # fall back to the indices already loaded (works on the website too)
        rows = []
        for ind_id, tk in (("sp500", "^GSPC"), ("nasdaq", "^IXIC"), ("ftse100", "^FTSE"), ("ftse250", "^FTMC"), ("dax", "^GDAXI"),
                           ("stoxx50", "^STOXX50E"), ("nikkei", "^N225")):
            if ind_id in LOADED and LOADED[ind_id][1]["series"] is not None and len(LOADED[ind_id][1]["series"]) > 2:
                sr = LOADED[ind_id][1]["series"].dropna()
                rows.append({"Ticker": tk, "Name": LOADED[ind_id][0]["name"], "1D %": (float(sr.iloc[-1]) / float(sr.iloc[-2]) - 1) * 100})
        data = scenes.markets_data(pd.DataFrame(rows)) if rows else None
    if data:
        ui.section("The trading day around the world", "each market lights up as its session opens · glow = latest daily move", code="★")
        show_scene("markets", data, 560, "Latest daily moves (may be delayed). The red band is daylight sweeping west: Asia opens first, "
                   "then Europe, then the Americas. Ranked on the right.")


def page_wei():
    world_day()
    st.markdown("World Equity Monitor · prices from TradingView (may be delayed) " + ui.info("TradingView", "TradingView"),
                unsafe_allow_html=True)
    left, right = st.columns([1, 1.5], gap="small")
    with left, st.container(border=True):
        ui.panel_title("Markets overview", "TRADINGVIEW · MAY BE DELAYED")
        ui.tv_market_overview(TV_EQUITY_TABS, height=600)
    with right, st.container(border=True):
        ui.panel_title("Chart", "TRADINGVIEW · MAY BE DELAYED")
        tv_chart_picker("wei_chart", 0)
    equity_ids = ["ftse100", "ftse250", "sp500", "nasdaq", "dax", "stoxx50", "nikkei"]
    ui.section("Equity outlook", "12-month forecasts and what the drivers say", code="02",
               about="market forecast")
    with st.container(border=True):
        ui.outlook_table(equity_ids, empty=(
            "Index forecasts need historical index prices, which can't be republished on the public "
            "edition. They're available when you run HF Macro on your own PC."))
        if any(i in FORECASTS for i in equity_ids):
            ui.forecast_movers(equity_ids)
    if not PUBLIC:
        ui.section("Performance table", "Yahoo Finance · your PC only", code="03")
        performance_view(EQUITY_MONITOR, "wei")


def page_cmdty():
    ui.section("Oil dashboard", "prices, US supply and demand, forecasts and news", code="01",
               about="inventories")
    ui.card_grid([i for i in OIL_DASHBOARD if i in LOADED], columns=8)
    left, mid, right = st.columns([1.15, 1.15, 1], gap="small")
    with left:
        chart_panel("brent", height=240)
    with mid:
        chart_panel("us_crude_stocks", height=240)
    with right, st.container(border=True):
        ui.panel_title("Oil headlines", "OPEC · EIA · 30 DAYS")
        ui.headlines(search_news("oil prices OPEC Brent"), limit=9,
                     empty="News search unavailable right now.")
    with st.container(border=True):
        ui.panel_title("Commodity outlook", "FORECAST · CONFIDENCE", about="outlook board")
        ui.outlook_table(["brent", "wti", "natgas", "gold", "copper"])
        ui.forecast_movers(["brent", "wti", "natgas", "gold", "copper"])
    ui.section("Live futures", "TradingView", code="02", about="futures")
    left, right = st.columns([1, 1.5], gap="small")
    with left, st.container(border=True):
        ui.panel_title("Commodities overview", "TRADINGVIEW · MAY BE DELAYED", about="futures")
        ui.tv_market_overview(TV_COMMODITY_TABS, height=600)
    with right, st.container(border=True):
        ui.panel_title("Chart", "TRADINGVIEW · MAY BE DELAYED")
        tv_chart_picker("cmdty_chart", 8)
    ui.section("Monthly commodity prices", "IMF primary commodity prices via FRED", code="03",
               about="IMF")
    key = get_fred_key()
    if not key:
        st.caption("Needs your FRED key.")
    else:
        all_monthly = []
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
            all_monthly.append(table)
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
        if all_monthly:
            with st.container(border=True):
                ui.panel_title("Winners & losers", "MONTHLY PRICES · PICK A PERIOD")
                period = st.segmented_control("Period", ["1M", "3M", "1Y", "5Y"], default="1Y", key="imf_mv")
                ui.ranked_lists(pd.concat(all_monthly, ignore_index=True), "Commodity", f"{period or '1Y'} %",
                                n=5, title_up=f"Top 5 risers ({period or '1Y'})",
                                title_down=f"Top 5 fallers ({period or '1Y'})")
        st.caption("Source: IMF Primary Commodity Prices (monthly averages), via FRED.")
    if not PUBLIC:
        ui.section("Futures performance", "Yahoo Finance · your PC only", code="04")
        performance_view(COMMODITY_MONITOR, "cmdty")


def page_crypto():
    # ---- headline numbers
    c1, c2, c3 = st.columns([1, 1, 1.6], gap="small")
    with c1, st.container(border=True):
        ui.panel_title("Crypto Fear & Greed", "ALTERNATIVE.ME", about="fear and greed")
        try:
            fng, mood = fetch_fear_greed()
            gauge(float(fng.iloc[-1]), "gauge_fng", [([0, 25], "#2A1012"), ([25, 45], "#221A10"),
                                                     ([45, 55], "#16191E"), ([55, 75], "#13200F"),
                                                     ([75, 100], "#0E2016")], suffix="")
            st.markdown(f"<div class='hs'>{ui.escape(mood.upper())} · "
                        f"<a href='https://alternative.me/crypto/fear-and-greed-index/' target='_blank'>"
                        f"Fear &amp; Greed Index by alternative.me</a></div>", unsafe_allow_html=True)
        except Exception as exc:
            fng = None
            st.caption(f"Fear & Greed index unavailable right now ({type(exc).__name__}).")
    with c2, st.container(border=True):
        ui.panel_title("Crypto market", "COINGECKO", about="market cap")
        try:
            g = fetch_crypto_global()
            chg = g["change_24h"] or 0
            st.markdown(
                f"<div class='k-name'>Total market cap{ui.info('market cap', 'Market cap')}</div>"
                f"<div class='k-val'>${g['market_cap_bn'] / 1000:,.2f}tn "
                f"<span class='chg {'up' if chg > 0 else 'dn'}'>{'▲' if chg > 0 else '▼'}{abs(chg):.2f}%</span></div>"
                f"<div class='k-name' style='margin-top:8px'>Bitcoin dominance"
                f"{ui.info('bitcoin dominance', 'Bitcoin dominance')}</div>"
                f"<div class='k-val'>{g['btc_dominance']:.1f}%</div>"
                f"<div class='k-name' style='margin-top:8px'>Ethereum share · 24H volume</div>"
                f"<div class='k-val' style='font-size:1rem'>{g['eth_dominance']:.1f}% · ${g['volume_bn']:,.0f}bn</div>"
                f"<div class='hs' style='margin-top:6px'><a href='https://www.coingecko.com' target='_blank'>"
                f"Data provided by CoinGecko</a></div>", unsafe_allow_html=True)
        except Exception as exc:
            st.caption(f"CoinGecko unavailable right now ({type(exc).__name__}). Its free service "
                       "limits how often it can be asked; try again in a minute.")
    with c3, st.container(border=True):
        ui.panel_title("Fear & Greed history", "90 DAYS")
        if fng is not None:
            ind = dict(id="fng", ticker="FNG", name="Crypto Fear & Greed", decimals=0, unit="",
                       chart="line", region="Crypto", group="Crypto", good_when="neutral")
            fig = ui.build_figure(ind, fng, height=250, ref_lines=[(25, "extreme fear"), (75, "extreme greed")])
            fig.update_layout(yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="fng_hist")
        else:
            st.caption("Unavailable right now.")

    # ---- top coins
    ui.section(f"Top {CRYPTO_TOP_N} coins", "by market cap · CoinGecko", code="01", about="crypto")
    try:
        coins = fetch_coin_markets(CRYPTO_TOP_N)
        pct = ["24H %", "7D %", "30D %"]
        st.dataframe(
            coins.style.format({"Price $": "{:,.4g}", "Market cap $bn": "{:,.1f}", "Volume 24H $bn": "{:,.2f}",
                                **{c: "{:+.2f}%" for c in pct}}, na_rep="-")
            .map(lambda v: "" if v is None or pd.isna(v) else
                 f"color: {ui.UP if v > 0 else ui.DOWN}; background-color: {ui.heat_colour(v, 15)}",
                 subset=pct),
            column_config={"7D trend": st.column_config.LineChartColumn("7D trend", width="medium")},
            hide_index=True, width="stretch", height=740)
        st.markdown("<div class='hs'>Prices update every 10 minutes · "
                    "<a href='https://www.coingecko.com' target='_blank'>Data provided by CoinGecko</a>"
                    f" · stablecoins such as USDT/USDC sit near $1 {ui.info('stablecoin', 'Stablecoins')}</div>",
                    unsafe_allow_html=True)
    except Exception as exc:
        st.info(f"CoinGecko unavailable right now ({type(exc).__name__}). Its free service limits how "
                "often it can be asked; refresh in a minute.")

    # ---- live charts
    ui.section("Live charts", "TradingView", code="02", about="TradingView")
    left, right = st.columns([1, 1.5], gap="small")
    with left, st.container(border=True):
        ui.panel_title("Crypto overview", "TRADINGVIEW · MAY BE DELAYED")
        ui.tv_market_overview(TV_CRYPTO_TABS, height=560)
    with right, st.container(border=True):
        ui.panel_title("Chart", "TRADINGVIEW · MAY BE DELAYED")
        ui.tv_advanced_chart(TV_CRYPTO_CHART, height=560)

    # ---- forecasts (PC edition) and news
    ui.section("Bitcoin & Ethereum outlook", "forecast and what the drivers say", code="03",
               about="market forecast")
    crypto_ids = [i for i in ("btc", "eth") if i in LOADED]
    if crypto_ids:
        panel_grid(crypto_ids)
        with st.container(border=True):
            ui.outlook_table(crypto_ids)
    else:
        st.caption("Bitcoin and Ethereum forecasts need long price histories, which can't be "
                   "republished on the public edition. They're available when you run HF Macro on your PC.")
    with st.container(border=True):
        ui.panel_title("Crypto headlines", "GOOGLE NEWS · 30 DAYS")
        ui.headlines(search_news("bitcoin OR ethereum OR crypto market"), limit=12,
                     empty="News search unavailable right now.")


def page_global():
    this_year = datetime.now().year
    years = list(range(this_year - 8, this_year + 4))
    c1, c2 = st.columns([1.3, 2])
    code = c1.selectbox("Measure", list(IMF_INDICATORS), format_func=lambda c: IMF_INDICATORS[c][0],
                        help="IMF World Economic Outlook data. " + (ui.tip("current account") or ""))
    try:
        df = fetch_imf(code, tuple(years))
        names = fetch_imf_countries()
    except Exception as exc:
        df, names = None, {}
    # only offer years that actually have data for a good number of countries
    if df is not None:
        filled = [y for y in years if y in df.columns and df[y].notna().sum() >= max(5, 0.3 * len(df))]
        options = filled or years
        default = this_year if this_year in options else max(y for y in options if y <= this_year) \
            if any(y <= this_year for y in options) else options[-1]
        year = c2.select_slider("Year", options=options, value=default)
    else:
        c2.select_slider("Year", options=years, value=this_year, disabled=True)
        st.info("Global data (IMF and World Bank) unavailable right now.")
    if df is not None:
        label, unit = IMF_INDICATORS[code]
        countries = df[df.index.isin(list(names))] if names else df[df.index.str.len() == 3]
        # each country's figure for the chosen year, or its latest one up to 2 years earlier
        # (big economies often publish to the World Bank months after smaller ones)
        usable = [y for y in countries.columns if year - 2 <= y <= year]
        if usable:
            window_df = countries[usable].apply(pd.to_numeric, errors="coerce")
            vals = window_df.ffill(axis=1).iloc[:, -1].dropna()
            used = window_df.apply(lambda r: r.last_valid_index(), axis=1).reindex(vals.index)
            labels = [f"{names.get(c, c)}" + ("" if used[c] == year else f" ({int(used[c])})")
                      for c in vals.index]
            fig = go.Figure()
            fig.add_trace(go.Choropleth(
                locations=vals.index, z=vals.values, text=labels,
                colorscale=[[0, "#1B3A5C"], [0.5, "#14181E"], [1, "#E8212B"]],
                zmid=float(vals.median()),
                # colour by the middle 90% of countries so a few extremes don't wash everything out
                zmin=float(vals.quantile(0.05)), zmax=float(vals.quantile(0.95)),
                marker_line_color="#000", marker_line_width=0.3,
                colorbar=dict(title=dict(text=unit), thickness=8, tickfont=dict(family=ui.MONO, size=9)),
                hovertemplate="%{text}<br>%{z:.1f}" + unit + "<extra></extra>"))
            fig.update_layout(height=440, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                              font=dict(family=ui.MONO, color="#AEB8C2"),
                              dragmode=False,
                              geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False, showcoastlines=False,
                                       landcolor="#3A414B", projection_type="natural earth",
                                       projection_rotation=dict(lon=0, lat=0, roll=0),
                                       center=dict(lon=0, lat=10), lataxis_range=[-58, 85],
                                       showocean=False, showcountries=True, countrycolor="#000"))
            # the map is locked in place (America left, Asia right); hover still shows each country
            st.plotly_chart(fig, width="stretch", key="world_map",
                            config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})
        src = df.attrs.get("source", "IMF World Economic Outlook")
        st.caption(f"{label}, {year}. Grey = no data. Countries that haven't published {year} yet "
                   f"show their latest figure (year in brackets when you hover). Source: {src}."
                   + (" Years after the latest actual data are IMF projections." if src.startswith("IMF")
                      else ""))
        from_imf = df.attrs.get("source", "IMF").startswith("IMF")
        ui.section("Major economies", f"{label} · {'IMF' if from_imf else 'World Bank'}", code="01",
                   about="WEO")
        majors = df.reindex(MAJOR_ECONOMIES).apply(pd.to_numeric, errors="coerce")
        if from_imf:     # last year, this year and next year (IMF forecasts)
            cols = [y for y in (this_year - 1, this_year, this_year + 1) if y in majors.columns]
        else:            # the latest 3 years that most of these economies have published
            ready = [y for y in sorted(majors.columns) if y <= this_year
                     and majors[y].notna().sum() >= len(MAJOR_ECONOMIES) // 2]
            cols = ready[-3:]
        table = majors[cols].astype(float).copy()
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


def country_globe(tables=None):
    """The spinning globe. Shown at once from the last saved IMF figures (the IMF site can be slow), and the saved
    figures are refreshed whenever the Country page downloads new ones."""
    try:
        yr = datetime.now().year
        names = {k: v["name"] for k, v in COUNTRIES.items()}
        if tables:
            fresh = scenes.countries_data(tables, names, yr)
            if fresh:
                look.remember("globe", fresh)
            return
        data = look.recall("globe") or {"countries": [{"code": iso, "name": names[iso], "lat": la, "lon": lo, "k": []}
                                                       for iso, (la, lo) in scenes.COUNTRY_PLACES.items() if iso in names]}
        show_scene("globe", data, 560,
                   f"IMF World Economic Outlook figures for {yr} (forecasts for the current year). Click a country, or let the globe turn by itself.")
    except Exception:
        pass


def page_country():
    country_globe()
    codes = list(COUNTRIES)
    iso = st.selectbox("Country", codes, index=codes.index("GBR"),
                       format_func=lambda c: f"{c} · {COUNTRIES[c]['name']}", key="ctry")
    c = COUNTRIES[iso]
    this_year = datetime.now().year
    years = tuple(range(2000, this_year + 6))
    imf, imf_tables = {}, {}
    for code in IMF_INDICATORS:
        try:
            table = fetch_imf(code, years)
            imf_tables[code] = table
            imf[code] = table.loc[iso].dropna()
            imf[code].attrs["source"] = table.attrs.get("source", "IMF")
        except Exception:
            imf[code] = pd.Series(dtype=float)
    if imf_tables:
        country_globe(imf_tables)
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

    def imf_val(code):
        """This year's figure if there is one (IMF), otherwise the latest actual (World Bank)."""
        s = imf.get(code, pd.Series(dtype=float))
        src = "IMF" if s.attrs.get("source", "IMF").startswith("IMF") else "WORLD BANK"
        if this_year in s.index:
            return f"{s[this_year]:.1f}%", f"{src} {this_year}"
        past = s[s.index <= this_year]
        if len(past):
            return f"{past.iloc[-1]:.1f}%", f"{src} {past.index[-1]}"
        return "-", src
    for col, code, label, about in ((tiles[0], "NGDP_RPCH", "GDP growth", "GDP"),
                                    (tiles[1], "PCPIPCH", "Inflation", "CPI"),
                                    (tiles[2], "LUR", "Unemployment", "unemployment rate"),
                                    (tiles[3], "GGXWDG_NGDP", "Govt debt / GDP", "government debt")):
        value, sub = imf_val(code)
        tile(col, label, value, sub, about)
    tile(tiles[4], "Policy rate", f"{policy.iloc[-1]:.2f}%" if len(policy) else "-",
         f"BIS {policy.index[-1]:%b %Y}".upper() if len(policy) else "BIS", "policy rate")
    tile(tiles[5], f"{c['ccy']} per USD" if c["fx"] else "Currency",
         f"{fx.dropna().iloc[-1]:,.4f}" if len(fx.dropna()) else c["ccy"],
         f"FRED {fx.dropna().index[-1]:%d %b %y}".upper() if len(fx.dropna()) else "BASE CURRENCY",
         "currency pair")

    left, right = st.columns(2, gap="small")
    for col, code in ((left, "NGDP_RPCH"), (right, "PCPIPCH")):
        with col, st.container(border=True):
            s = imf.get(code, pd.Series(dtype=float))
            from_imf = s.attrs.get("source", "IMF").startswith("IMF")
            ui.panel_title(IMF_INDICATORS[code][0],
                           "IMF · ACTUAL + PROJECTION" if from_imf else "WORLD BANK · ACTUAL", about="WEO")
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
            st.caption("Darker bars = IMF projections." if from_imf else "Source: World Bank (actual figures).")
    l2, m2, r2 = st.columns(3, gap="small")
    for col, title, s, unit, kk in ((l2, "Policy rate", policy, "%", "pol"),
                                    (m2, f"{c['ccy']} per USD", fx, "", "fx"),
                                    (r2, f"Equity index ({c['equity'] or 'n/a'})", equity, "", "eq")):
        with col, st.container(border=True):
            ui.panel_title(title, "20Y")
            s = s.dropna()
            if s.empty:
                st.caption("See the World Equities page for index charts."
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
    st.caption("Sources: IMF World Economic Outlook (or World Bank when the IMF is unreachable), "
               "BIS policy rates, FRED exchange rates, "
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
                    st.caption(gdp.attrs.get("source", ""))
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
            with ui.loading("Checking the news", ["Sending the spider across the news feeds", "Reading BBC, Guardian, CNBC, the Fed and the Bank of England", "Tagging headlines by topic", "Ranking the top stories"], scene="web", once="news"):
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
    try:
        _str = currency_strength(fetch_fx_history("USD", tuple(HEATMAP_CURRENCIES)))
        ui.section("Currency gravity", "each currency is a planet sized and placed by its strength against the dollar · switch the period", code="★")
        show_scene("fxg", scenes.fx_data(_str), 560, "Strength against the US dollar from ECB reference rates (via Frankfurter). Strong currencies "
                   "float up and grow; the dotted thread joins the strongest and the weakest.")
    except Exception:
        pass
    left, right = st.columns([1, 1.6], gap="small")
    with left, st.container(border=True):
        ui.panel_title("GBP snapshot", "1 GBP BUYS", about="ECB reference rates")
        fx_snapshot()
    with right, st.container(border=True):
        ui.panel_title("Currency strength heatmap", "% CHANGE", about="currency strength")
        strength_heatmap()
    ui.section("Winners & losers", "strongest and weakest currencies", code="FX", about="currency strength")
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        period = c1.segmented_control("Period", ["1D", "1W", "1M", "3M", "YTD", "1Y"], default="1W",
                                      key="fx_mv_period")
        base = c2.segmented_control("Against", ["USD", "GBP", "EUR"], default="USD", key="fx_mv_base")
        try:
            rates = fetch_fx_history(base or "USD", tuple(HEATMAP_CURRENCIES))
            strength = currency_strength(rates).reset_index().rename(columns={"index": "Currency"})
            strength = strength[strength["Currency"] != (base or "USD")]
            strength["link"] = [ui.ccy_link(c) if c in CURRENCIES else None for c in strength["Currency"]]
            strength["Currency"] = [f"{c} · {CURRENCIES.get(c, {}).get('name', c)}" for c in strength["Currency"]]
            ui.ranked_lists(strength, "Currency", period or "1W", n=5, link_col="link",
                            title_up=f"Top 5 winners vs {base or 'USD'} ({period or '1W'})",
                            title_down=f"Top 5 losers vs {base or 'USD'} ({period or '1W'})")
        except Exception as exc:
            st.caption(f"Currency history unavailable right now ({type(exc).__name__}).")
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
    _key = get_fred_key()
    if _key:
        try:
            _ten = {n: fetch_fred(c, _key) for n, c in YIELD_CURVES["US Treasuries"]["points"] if n in ("3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y")}
            ui.section("The yield curve through time", "US Treasuries, 2006 to today · red = inverted (short rates above long rates)", code="★")
            show_scene("curves", scenes.curves_data(_ten, REC.get("US", [])), 560, "Real US Treasury yields from FRED, one curve per year-end plus "
                       "the latest. Recession years are flagged; inversions came before the last recessions.")
        except Exception:
            pass
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
    _cal, _err = load_calendar()
    if not _err:
        show_scene("calendar", scenes.calendar_data(_cal), 420, "Release dates from FRED's calendar. Most US data comes out at 8:30am New York "
                   "time (13:30 UK), which the countdown assumes.")
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
    tab0, tab_sc, tab1, tab2, tab3 = st.tabs(["Outlook board", "Forecast scorecard", "Correlation & lead/lag",
                                              "Taylor rule", "Macro momentum" if PUBLIC else "Risk appetite"])
    with tab_sc:
        forecast_scorecard()
    with tab0:
        st.markdown("Every forecast in one place, highest confidence first "
                    + ui.info("outlook board", "Outlook board"), unsafe_allow_html=True)
        with st.container(border=True):
            ui.panel_title("Markets: biggest projected moves", "COMMODITIES · EQUITIES · CRYPTO · FX")
            ui.forecast_movers([i for i in FORECASTS if i in MARKET_FORECASTS and LOADED[i][0]["unit"] != "%"])
        for label, region_ids in (
                ("Economy", [i["id"] for i in ACTIVE if i["region"] in ("US", "UK", "EA")
                             and i["id"] not in ("us_10y", "uk_10y", "stoxx50")]),
                ("Markets: commodities, equities and crypto", [i["id"] for i in ACTIVE
                                                       if i["region"] in ("Markets", "Crypto")
                                                       or i["id"] == "stoxx50"]),
                ("Currencies and bond yields", [i["id"] for i in ACTIVE
                                                if i["region"] == "FX" or i["id"] in ("us_10y", "uk_10y")])):
            with st.container(border=True):
                ui.panel_title(label)
                ui.outlook_table([i for i in region_ids if i in FORECASTS])
        st.caption(ui.DISCLAIMER)
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



# ================================================================= LEARN

def now_sentence(key):
    """One line about what today's data shows, for each lesson."""
    def get(i):
        return LOADED[i] if i in LOADED and LOADED[i][1]["latest"] is not None else (None, None)
    try:
        if key == "payrolls":
            ind, res = get("us_payrolls")
            u_ind, u_res = get("us_unemp")
            if ind:
                return (f"US payrolls changed by {ui.fmt(res['latest'], ind)} in the latest month "
                        f"({ui.date_label(ind, res['latest_date'])}), and unemployment is "
                        f"{ui.fmt(u_res['latest'], u_ind) if u_ind else 'n/a'}.")
        if key == "uk_inflation":
            ind, res = get("uk_cpi")
            b_ind, b_res = get("uk_bankrate")
            if ind and b_ind:
                gap = res["latest"] - 2
                real = b_res["latest"] - res["latest"]
                return (f"UK CPI inflation is {ui.fmt(res['latest'], ind)}, {abs(gap):.1f}pp "
                        f"{'above' if gap > 0 else 'below'} the 2% target. Bank Rate is "
                        f"{ui.fmt(b_res['latest'], b_ind)}, so the real rate is {real:+.1f}%: policy is "
                        f"{'restrictive (holding the economy back)' if real > 1 else 'roughly neutral' if real > -0.5 else 'still loose'}.")
        if key == "curve":
            ind, res = get("us_3m10y")
            if ind:
                p = recession_probability(res["series"]).iloc[-1]
                return (f"The US 10-year minus 3-month spread is {res['latest']:+.2f}pp "
                        f"({'inverted' if res['latest'] < 0 else 'not inverted'}). The NY Fed model gives a "
                        f"{p:.0f}% chance of a US recession in 12 months.")
        if key == "fx":
            ind, res = get("gbpusd")
            d_ind, d_res = get("uk_us_rates")
            if ind:
                return (f"GBP/USD is {ui.fmt(res['latest'], ind)}" + (
                    f", and UK rates are {d_res['latest']:+.2f}pp versus US rates." if d_ind else "."))
        if key == "bonds":
            ind, res = get("us_2y")
            f_ind, f_res = get("us_fedfunds")
            if ind and f_ind:
                gap = res["latest"] - f_res["latest"]
                return (f"The 2-year Treasury yield is {ui.fmt(res['latest'], ind)} versus a Fed funds rate of "
                        f"{ui.fmt(f_res['latest'], f_ind)}: markets are pricing "
                        f"{'rate cuts' if gap < -0.25 else 'rate rises' if gap > 0.25 else 'roughly steady rates'}.")
        if key == "oil":
            ind, res = get("brent")
            if ind:
                s = res["series"]
                yr = s.asof(s.index[-1] - pd.DateOffset(years=1))
                return (f"Brent crude is {ui.fmt(res['latest'], ind)}, "
                        f"{(res['latest'] / yr - 1) * 100:+.0f}% on a year ago.")
        if key == "scorecard":
            return "Open LAB → Forecast scorecard to see which of HF Macro's forecasts actually beat 'no change'."
    except Exception:
        return None
    return None


def page_learn():
    lessons = {l["key"]: l for l in learn.LESSONS}
    cases = {c["key"]: c for c in learn.CASES}
    sel = st.query_params.get("l")
    if sel not in lessons and sel not in cases:
        st.markdown("### Learn macro with live data")
        st.markdown("Short lessons that use HF Macro's real charts, in the order of Bloomberg Market Concepts' "
                    "economics and currencies modules. Each ends with a quick quiz.")
        cols = st.columns(3, gap="small")
        for n, l in enumerate(learn.LESSONS):
            with cols[n % 3], st.container(border=True):
                st.markdown(f"<div class='des-head'><a href='{ui.page_link('LEARN', l=l['key'])}' target='_self'>"
                            f"{ui.escape(l['title'])}</a></div><div class='hs'>{l['minutes']} min read</div>"
                            f"<div class='des-note' style='color:#AEB8C2'>{ui.escape(l['summary'])}</div>",
                            unsafe_allow_html=True)
        st.markdown("### Case studies")
        cols = st.columns(4, gap="small")
        for n, c in enumerate(learn.CASES):
            with cols[n % 4], st.container(border=True):
                st.markdown(f"<div class='des-head'><a href='{ui.page_link('LEARN', l=c['key'])}' target='_self'>"
                            f"{ui.escape(c['title'])}</a></div>", unsafe_allow_html=True)
        st.caption("Educational content, not financial advice.")
        return

    st.markdown(f"<a class='drv' href='{ui.page_link('LEARN')}' target='_self'>◄ ALL LESSONS</a>",
                unsafe_allow_html=True)
    if sel in lessons:
        l = lessons[sel]
        region = "UK" if sel in ("inflation",) else None
        st.markdown(f"## {l['title'][3:]}")
        st.caption(f"{l['minutes']} min read · {l['summary']}")
        for kind, *rest in l["parts"]:
            if kind == "text":
                st.markdown(rest[0])
            elif kind == "chart":
                ids, years, caption = rest
                ids = [i for i in ids if i in LOADED and LOADED[i][1]["series"] is not None]
                if not ids:
                    continue
                with st.container(border=True):
                    main_ind, main_res = LOADED[ids[0]]
                    compare = [(LOADED[i][0], ui.window(LOADED[i][1]["series"], years)) for i in ids[1:]]
                    shade = "US recessions" if main_ind["region"] in ("US", "Markets", "FX") else \
                        "UK recessions" if main_ind["region"] == "UK" else None
                    shades = [(shade, *SHADE_PERIODS[shade])] if shade in SHADE_PERIODS else []
                    fig = ui.build_figure(main_ind, ui.window(main_res["series"], years), height=300,
                                          compare=compare, shades=shades)
                    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"learn_{sel}_{ids[0]}")
                    st.markdown(" ".join(f"<a class='drv' href='{ui.link(LOADED[i][0]['ticker'], view='DES')}' "
                                         f"target='_self'>{LOADED[i][0]['ticker']} ↗</a>" for i in ids)
                                + f" <span class='hs'>{ui.escape(caption)}</span>", unsafe_allow_html=True)
            elif kind == "now":
                text = now_sentence(rest[0])
                if text:
                    st.markdown(f"<div class='disc' style='border-color:{ui.CYAN};background:rgba(63,182,255,.08);"
                                f"color:#D9DEE3'><b>RIGHT NOW:</b> {ui.autolink(text, region=region)}</div>",
                                unsafe_allow_html=True)
        quiz(sel, l["quiz"])
        keys = list(lessons)
        i = keys.index(sel)
        nav = []
        if i > 0:
            nav.append(f"<a class='drv' href='{ui.page_link('LEARN', l=keys[i - 1])}' target='_self'>◄ PREVIOUS</a>")
        if i < len(keys) - 1:
            nav.append(f"<a class='drv' href='{ui.page_link('LEARN', l=keys[i + 1])}' target='_self'>NEXT LESSON ►</a>")
        st.markdown(" ".join(nav), unsafe_allow_html=True)
    else:
        c = cases[sel]
        st.markdown(f"## {c['title']}")
        st.markdown(c["story"])
        start, end = pd.Timestamp(c["start"]), pd.Timestamp(c["end"])
        ids = [i for i in c["ids"] if i in LOADED and LOADED[i][1]["series"] is not None]
        cols = st.columns(2, gap="small")
        for n, i in enumerate(ids):
            ind, res = LOADED[i]
            s = res["series"][(res["series"].index >= start) & (res["series"].index <= end)]
            if s.empty:
                continue
            with cols[n % 2], st.container(border=True):
                ui.panel_title(ind["name"], ind["ticker"])
                fig = ui.build_figure(ind, s, height=230)
                for d, label in c["events"]:
                    fig.add_vline(x=pd.Timestamp(d), line=dict(color=ui.ACCENT, dash="dot", width=1))
                    fig.add_annotation(x=pd.Timestamp(d), y=1, yref="paper", text=label, showarrow=False,
                                       textangle=-90, xanchor="right", yanchor="top",
                                       font=dict(size=9, color="#E8A33D"))
                st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"case_{sel}_{i}")
        st.caption("Red dotted lines mark the key events. " + ui.DISCLAIMER)


def quiz(key, questions):
    with st.container(border=True):
        ui.panel_title("Quick quiz", f"{len(questions)} QUESTIONS")
        score = 0
        answered = 0
        for n, (q, options, correct, why) in enumerate(questions):
            choice = st.radio(f"{n + 1}. {q}", options, index=None, key=f"quiz_{key}_{n}")
            if choice is not None:
                answered += 1
                if options.index(choice) == correct:
                    score += 1
                    st.markdown(f"<span class='up'>✔ Correct.</span> {ui.escape(why)}", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='dn'>✘ Not quite.</span> The answer is "
                                f"<b>{ui.escape(options[correct])}</b>. {ui.escape(why)}", unsafe_allow_html=True)
        if answered == len(questions):
            st.markdown(f"**Score: {score} / {len(questions)}**")


def page_guide(page):
    tips = learn.GUIDES.get(page)
    if not tips:
        return
    with st.expander("📘 How to read this page"):
        st.markdown("\n".join(f"- {ui.autolink(t)}" for t in tips), unsafe_allow_html=True)
        lesson = learn.GUIDE_LESSON.get(page)
        if lesson:
            title = next(l["title"] for l in learn.LESSONS if l["key"] == lesson)
            st.markdown(f"Learn more: <a href='{ui.page_link('LEARN', l=lesson)}' target='_self'>{ui.escape(title)}</a>",
                        unsafe_allow_html=True)



# ================================================================= ASSET LAB (PC version only)

LAB_MAIN = {
    "MY TRADES": "The commodities model's picks as trade tickets for the demo account (amount, stop-loss, sell date), "
                 "and a tracker for the trades you've placed",
    "THIS WEEK": "The trades to place this week: focus strategies and the model, big enough moves only, with "
                 "take-profit, stop-loss and a practice-account size",
    "WHAT'S WORKING": "The positives so far, in plain English, plus the winners' cumulative return",
    "TEST": "Backtest strategies, test ingredients (Signal Lab) and build the model",
    "LEARN FROM MISSES": "Why we missed, and every saved prediction scored",
    "PARKED": "Ideas that are losing for now: saved with their numbers so we can come back to them",
    "EXPLORE": "The Monte Carlo playground: scanner, full analysis, contrarian test, strategy picks, risk simulator",
}
LAB_SUBS = {"TEST": ["Commodities model", "Model + S&P 500", "Fresh test", "Idea log", "Commodities workshop", "Pattern lab", "Backtest", "Signal Lab", "Model"], "LEARN FROM MISSES": ["Why we missed", "Prediction log"],
            "EXPLORE": ["Scanner", "Analysis", "Contrarian", "Strategies", "Risk simulator"]}
LAB_ALIASES = {"COMMODITIES MODEL": ("TEST", "Commodities model"), "IDEA LOG": ("TEST", "Idea log"), "MIX": ("TEST", "Model + S&P 500"), "FRESH TEST": ("TEST", "Fresh test"), "BACKTEST": ("TEST", "Backtest"), "SIGNAL LAB": ("TEST", "Signal Lab"), "MODEL": ("TEST", "Model"),
               "WHY WE MISSED": ("LEARN FROM MISSES", "Why we missed"),
               "PREDICTION LOG": ("LEARN FROM MISSES", "Prediction log"),
               "SCANNER": ("EXPLORE", "Scanner"), "ANALYSIS": ("EXPLORE", "Analysis"),
               "CONTRARIAN": ("EXPLORE", "Contrarian"), "STRATEGIES": ("EXPLORE", "Strategies"),
               "RISK": ("EXPLORE", "Risk simulator")}
LAB_SECTIONS = {
    "SCANNER": "Monte Carlo for every asset, expected move vs attention, top 3 under the radar",
    "ANALYSIS": "10,000 simulated futures for one asset, every statistic explained",
    "CONTRARIAN": "Short last week's top winner, buy the top loser",
    "STRATEGIES": "This week's picks from every strategy side",
    "SIGNAL LAB": "Test every ingredient (indicator) on its own: does it call direction better than a coin toss?",
    "MODEL": "Combine every ingredient into one model, backtest it, and see this week's calls",
    "BACKTEST": "Test the model and every side on any asset classes and dates",
    "WHY WE MISSED": "Split every miss into market, sector, our drift and noise",
    "PREDICTION LOG": "Every saved prediction, scored once the week is over",
    "RISK": "Simulate your picks together, and how correlated they are",
}
PREDICTION_LOG = HERE / "data" / "predictions.csv"


@st.cache_data(ttl=30 * 60, show_spinner=False)
def lab_prices(classes):
    """10 years of cleaned, dividend-adjusted daily prices for each asset class."""
    uni = assetlab.universe(classes)
    prices, fixes = {}, []
    for c, members in uni.items():
        try:
            p, fx = assetlab.load_class_prices(c, tuple(t for t, _, _ in members))
            prices[c] = p
            fixes += [(c, *f) for f in fx]
        except Exception:
            pass
    return uni, prices, fixes


@st.cache_data(ttl=30 * 60, show_spinner=False)
def lab_scan(classes, horizon, drift):
    uni, prices, _ = lab_prices(classes)
    df = assetlab.scan(prices, uni, horizon, drift)
    if df.empty:
        return df, df
    return df, assetlab.attention(df)


def lab_extras():
    """Central bank rates (for FX carry) and the NY Fed recession probability (for the macro tilt)."""
    rates, rec = None, None
    try:
        from reference import CURRENCIES
        rates = fetch_policy_rates(tuple(sorted({c["bis"] for c in CURRENCIES.values()})))
    except Exception:
        pass
    try:
        if "us_3m10y" in LOADED and LOADED["us_3m10y"][1]["series"] is not None:
            rec = recession_probability(LOADED["us_3m10y"][1]["series"])
            rec.index = rec.index - pd.DateOffset(months=12)          # the probability as known at that date
    except Exception:
        pass
    return rates, rec


def name_of(ticker, uni):
    for members in uni.values():
        for t, n, _ in members:
            if t == ticker:
                return n
    return ticker


def stats_table(rows):
    body = "".join(f"<tr><td class='l'>{ui.escape(n)}</td><td class='v'><b>{ui.escape(v)}</b></td>"
                   f"<td style='color:#AEB8C2'>{ui.escape(what)}</td><td>{ui.escape(means)}</td></tr>"
                   for n, v, what, means in rows)
    st.markdown("<table class='des'><tr><td class='l'>STATISTIC</td><td class='l'>VALUE</td>"
                "<td class='l'>WHAT IT IS</td><td class='l'>WHAT IT TELLS US HERE</td></tr>" + body + "</table>",
                unsafe_allow_html=True)


def distribution_charts(sims, key, short=False):
    x = -sims if short else sims
    lo, hi = np.percentile(x, [0.5, 99.5])
    counts, edges = np.histogram(x[(x >= lo) & (x <= hi)], bins=60)
    mids = (edges[:-1] + edges[1:]) / 2
    fig = go.Figure()
    fig.add_bar(x=mids, y=counts, marker_color=[ui.UP if m > 0 else ui.DOWN for m in mids], name="Simulations")
    mean, med, mode = float(x.mean()), float(np.median(x)), assetlab.kde_mode(x)
    for v, label, colour in ((mean, "mean", "#FFD166"), (med, "median", ui.CYAN), (mode, "mode", "#FFFFFF")):
        fig.add_vline(x=v, line=dict(color=colour, dash="dot", width=1.5))
        fig.add_annotation(x=v, y=1, yref="paper", text=label, showarrow=False, font=dict(size=10, color=colour))
    fig = ui.base_layout(fig, 260)
    fig.update_layout(bargap=0.02, xaxis_title="% change" if not short else "% return on the short")
    c1, c2 = st.columns([2.2, 1], gap="small")
    c1.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"hist_{key}")
    box = go.Figure()
    box.add_box(y=x, name="", marker_color=ui.CYAN, boxpoints=False)
    c2.plotly_chart(ui.base_layout(box, 260, unit="%"), width="stretch", config=ui.PLOT_CONFIG, key=f"box_{key}")


def average_panel(s):
    """Mean vs median vs mode, the checks, and which one fits best (and why)."""
    c = s["checks"]
    ui.panel_title("Which average fits best?", "MEAN · MEDIAN · MODE")
    rows = []
    for name, val in (("Mean", c["mean"]), ("Median", c["median"]), ("Mode", c["mode"])):
        tag = " <span class='up'>★ best fit</span>" if name == s["best_type"] else ""
        rows.append((name, f"{val:+.2f}%{tag}"))
    rows += [("Skewness", f"{c['skew']:+.2f} <span class='hs'>(over ±0.5 = skewed)</span>"),
             ("Outliers", f"{c['outliers']:.1f}% <span class='hs'>(beyond 1.5 × IQR from Q1/Q3; over 5% = many)</span>"),
             ("Mean–median gap", f"{c['gap']:.0f}% of the IQR <span class='hs'>(over 10% = the mean is being pulled)</span>"),
             ("Range vs IQR", f"{c['range']:.1f}pp vs {c['iqr']:.1f}pp" + (
                 f" <span class='hs'>(range is {c['range_to_iqr']:.1f}× the IQR: long tails)</span>" if c["range_to_iqr"] else "")),
             ("Clusters (peaks)", f"{c['peaks']}")]
    ui.des_table(rows)
    st.markdown(f"**Verdict: {s['best_type']}.** {s['best_reason']}")
    st.caption("Rule of thumb: mean for symmetrical data with few outliers; median for skewed data or data with "
               "outliers (extremes pull the mean and stretch the range, but the median barely moves); mode when the "
               "data has separate clusters.")


def lab_line_chart(series_dict, height, key, unit="%", title=None, zero=True):
    fig = go.Figure()
    colours = list(assetlab.CLASS_COLOURS.values()) + [ui.CYAN, "#FFD166", "#C792EA", "#5EE6C9", ui.ACCENT]
    for n, (name, s) in enumerate(series_dict.items()):
        fig.add_scatter(x=s.index, y=s.values, mode="lines", name=name, line=dict(width=1.6, color=colours[n % len(colours)]))
    if zero:
        fig.add_hline(y=0, line=dict(color="#55606C", width=1))
    fig = ui.base_layout(fig, height, unit=unit, legend=True)
    if title:
        fig.update_layout(yaxis_title=title)
    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=key)


# ---------------------------------------------------------------- sections

def lab_scanner(scan_df, att, horizon, classes):
    with st.container(border=True):
        ui.panel_title("Expected move vs attention", "CLICK A DOT FOR THE FULL ANALYSIS")
        fig = go.Figure()
        top3 = att.sort_values("radar", ascending=False).head(3)
        for c in classes:
            d = att[att["cls"] == c]
            if d.empty:
                continue
            fig.add_scatter(
                x=d["attention"], y=d["median"].abs(), mode="markers", name=c,
                marker=dict(size=11, color=assetlab.CLASS_COLOURS[c],
                            symbol=["triangle-up" if m > 0 else "triangle-down" for m in d["median"]],
                            line=dict(width=1, color="#000")),
                customdata=np.column_stack([
                    d["ticker"], d["name"], d["median"].round(2), d["score"].round(2),
                    [("n/a" if pd.isna(v) else f"{int(v):,}") for v in d["news"]],
                    [("n/a" if pd.isna(v) else f"{int(v):,}") for v in d["views"]],
                    [("n/a" if pd.isna(v) else f"{v:.1f}×") for v in d["attn_vs_normal"]]]),
                hovertemplate="<b>%{customdata[1]}</b> (%{customdata[0]})<br>Expected (median): %{customdata[2]}%"
                              "<br>Per unit of risk: %{customdata[3]}<br>News (7d): %{customdata[4]}"
                              "<br>Wikipedia views (7d): %{customdata[5]}<br>Attention vs its normal: "
                              "%{customdata[6]}<extra></extra>")
        for _, r in top3.iterrows():
            fig.add_annotation(x=r["attention"], y=abs(r["median"]), text=f"★ {r['name']}", showarrow=True,
                               arrowcolor=ui.ACCENT, font=dict(color="#fff", size=11), bgcolor=ui.ACCENT)
        fig = ui.base_layout(fig, 460, legend=True)
        fig.update_layout(xaxis_title="Attention score (0 = least covered, 100 = most) · news + Wikipedia, last 7 days",
                          yaxis_title=f"Expected move {horizon.lower()} (%, size, median)",
                          xaxis=dict(range=[0, 103]),
                          yaxis=dict(range=[0, float(att["median"].abs().max()) * 1.15 or 1], ticksuffix="%", side="left"))
        try:
            fig.update_layout(xaxis=dict(minallowed=0, maxallowed=103), yaxis=dict(minallowed=0))
        except Exception:
            pass
        event = st.plotly_chart(fig, width="stretch", config={**ui.PLOT_CONFIG, "scrollZoom": False}, key="al_scatter",
                                on_select="rerun", selection_mode="points")
        st.caption("▲ = expected to rise, ▼ = expected to fall. Height = size of the expected move (the median, so "
                   "every asset is measured the same way). ★ = top 3 under the radar, ranked by expected move PER UNIT "
                   "OF RISK (so they're not just the most volatile assets) against attention.")
    try:
        pts = event.selection.points if event else []
        if pts:
            st.session_state["al_pick"] = str(pts[0]["customdata"][0])
            st.caption("Selected: open ANALYSIS to see its full breakdown.")
    except Exception:
        pass
    st.markdown("#### ★ Top 3 under the radar")
    cols = st.columns(3, gap="small")
    for col, (_, r) in zip(cols, top3.iterrows()):
        with col, st.container(border=True):
            arrow = "▲" if r["median"] > 0 else "▼"
            st.markdown(f"<div class='des-head'>{ui.escape(r['name'])} <span class='hs'>{r['ticker']} · "
                        f"{r['cls']}</span></div>"
                        f"<span class='hv' style='font-size:1.4rem'><span class='{'up' if r['median'] > 0 else 'dn'}'>"
                        f"{arrow} {r['median']:+.2f}%</span></span> <span class='hs'>median, {horizon.lower()}</span>",
                        unsafe_allow_html=True)
            ui.des_table([("Chance it rises", f"{r['p_up']:.0f}%"), ("90% range", f"{r['p5']:+.1f}% to {r['p95']:+.1f}%"),
                          ("Move per unit of risk", f"{r['score']:+.2f}"),
                          ("Attention score", f"{r['attention']:.0f} / 100"),
                          ("Attention vs its normal", "-" if pd.isna(r.get("attn_vs_normal")) else f"{r['attn_vs_normal']:.1f}×"),
                          ("News headlines (7d)", "-" if pd.isna(r["news"]) else f"{int(r['news'])}"),
                          ("Wikipedia views (7d)", "-" if pd.isna(r["views"]) else f"{int(r['views']):,}")])
    with st.expander("Top pick in each asset class"):
        best = att.sort_values("radar", ascending=False).groupby("cls").head(1)
        st.dataframe(best[["cls", "name", "ticker", "median", "score", "p_up", "attention", "attn_vs_normal", "news", "views"]]
                     .rename(columns={"cls": "Class", "name": "Asset", "ticker": "Ticker", "median": "Expected % (median)",
                                      "score": "Per unit of risk", "p_up": "Chance up %", "attention": "Attention",
                                      "attn_vs_normal": "Attention vs normal", "news": "News (7d)",
                                      "views": "Wiki views (7d)"}).round(2), hide_index=True, width="stretch")
    c1, c2 = st.columns([1, 3])
    if c1.button("💾 Save these predictions to the log", key="al_save"):
        n = backtest.log_predictions(scan_df, att, st.session_state.get("al_h") or "Next week",
                                     st.session_state.get("al_drift") or "Trend continues", PREDICTION_LOG)
        c2.success(f"Saved. The log now holds {n:,} predictions. Score them in PREDICTION LOG once the week is over.")


def lab_analysis(scan_df, att, prices, horizon, drift):
    options = {f"{r['name']} ({r['ticker']}) · {r['cls']}": r["ticker"]
               for _, r in pd.concat([att.sort_values("radar", ascending=False), scan_df]).drop_duplicates("ticker").iterrows()}
    labels = list(options)
    picked = st.session_state.get("al_pick")
    index = next((i for i, l in enumerate(labels) if options[l] == picked), 0)
    label = st.selectbox("Asset", labels, index=index, key=f"al_sel_{picked}")
    ticker = options[label]
    row = scan_df[scan_df["ticker"] == ticker].iloc[0]
    series = prices[row["cls"]][ticker].dropna()
    sims = assetlab.simulate(series, assetlab.horizon_days(row["cls"], horizon), n_sims=10000, drift=drift)
    with st.container(border=True):
        ui.panel_title(f"{row['name']}: 10,000 simulated futures", f"{horizon.upper()} · {drift.upper()}")
        distribution_charts(sims, ticker)
        rows, s = assetlab.describe(sims, row["name"], horizon.lower())
        average_panel(s)
        stats_table(rows)
        st.markdown(f"**In short:** the median is **{s['median']:+.2f}%** (best-fit average: {s['best_type'].lower()}, "
                    f"{s['best']:+.2f}%), with a {s['p_pos']:.0f}% chance of a rise. But the 90% range runs from "
                    f"{s['p5']:+.1f}% to {s['p95']:+.1f}%, so the spread of outcomes ({s['sd']:.1f}pp standard deviation) "
                    "is far bigger than the expected move. That's normal for markets: the risk matters more than the "
                    "'prediction'.")
        st.caption("The simulation replays up to 10 years of this asset's real daily shocks, with the last two years "
                   "counting most, scaled to how volatile it is right now.")


def lab_contrarian(prices, uni, classes, drift):
    st.caption("For each asset class: if you SHORT the asset that rose most last week, how likely is it to fall "
               "next week? And if you BUY the one that fell most, how likely is it to bounce? The simulation "
               "answers that for next week; the history check shows how often it actually worked over ~2 years.")
    names = [c for c in classes if c in prices]
    if not names:
        return
    tabs = st.tabs(names)
    for tab, c in zip(tabs, names):
        with tab:
            winner, loser = assetlab.weekly_extremes(prices[c], uni[c])
            if not winner:
                st.caption("Not enough data.")
                continue
            hist = assetlab.contrarian_history(prices[c], uni[c])
            left, right = st.columns(2, gap="small")
            for col, (tick, name, move), short in ((left, winner, True), (right, loser, False)):
                with col, st.container(border=True):
                    s_ser = prices[c][tick].dropna()
                    sims_c = assetlab.simulate(s_ser, assetlab.horizon_days(c, "Next week"), n_sims=10000,
                                               drift=drift, seed=7)
                    rows_c, sc = assetlab.describe(sims_c, name, "next week", short=short)
                    ui.panel_title(f"{'SHORT' if short else 'BUY'} {name}", f"{tick} · LAST WEEK {move:+.1f}%")
                    st.markdown(
                        f"<span class='hv' style='font-size:1.3rem'>{sc['p_pos']:.0f}%</span> "
                        f"<span class='hs'>chance the {'short makes money (price falls)' if short else 'bounce happens (price rises)'}</span>",
                        unsafe_allow_html=True)
                    ui.des_table([("Expected return (median)", f"{sc['median']:+.2f}%"),
                                  ("90% range", f"{sc['p5']:+.1f}% to {sc['p95']:+.1f}%"),
                                  ("Bad week (5th percentile)", f"{sc['p5']:+.1f}%")])
                    if hist:
                        rate = hist["winner_fell"] if short else hist["loser_rose"]
                        avg = -hist["winner_avg_next"] if short else hist["loser_avg_next"]
                        st.markdown(f"**History check ({hist['n']} weeks):** the class's top "
                                    f"{'winner fell' if short else 'loser rose'} the next week **{rate:.0f}%** of "
                                    f"the time, with an average {'short' if short else 'long'} return of {avg:+.2f}% "
                                    "(before costs).")
                    with st.expander("Full data analysis"):
                        distribution_charts(sims_c, f"{c}_{tick}_{short}", short=short)
                        average_panel(sc)
                        stats_table(rows_c)
    st.caption("Shorting means profiting when a price falls. In a Trading 212 practice account this is done with "
               "CFDs, which charge overnight fees. Just for fun, not financial advice.")


@st.cache_data(ttl=30 * 60, show_spinner=False)
def lab_live_picks(classes):
    uni, prices, _ = lab_prices(classes)
    rates, rec = lab_extras()
    return backtest.current_picks(prices, lambda c: assetlab.horizon_days(c, "Next week"), rates=rates, recession=rec)


def lab_strategies(classes, uni):
    st.caption("Every strategy side, and what it would buy or short THIS week. Run a BACKTEST to see which sides "
               "have actually worked; the verdicts from your last backtest appear here.")
    with ui.loading("Working out this week's picks", ["Downloading commodity prices", "Scoring markets on 4 strategies", "Applying stop-losses and pauses", "Building this week's picks"], scene="model"):
        try:
            picks = lab_live_picks(tuple(classes))
        except Exception as exc:
            st.error(f"Couldn't work out the picks ({type(exc).__name__}: {exc}).")
            return
    last = st.session_state.get("al_bt_scores")
    for kind, title in (("proven", "Proven ideas"), ("model", "Monte Carlo model"), ("creative", "Your creative ideas")):
        st.markdown(f"#### {title}")
        for name, (desc, k, applies) in backtest.SIDES.items():
            if k != kind:
                continue
            p = picks[picks["side"] == name] if not picks.empty else picks
            with st.expander(f"{name} · {len(p)} picks this week"):
                st.caption(desc)
                if last is not None and not last.empty:
                    v = last[last["side"] == name]
                    if not v.empty:
                        st.markdown("**Last backtest:** " + " · ".join(f"{r['cls']}: {r['verdict']}" for _, r in v.iterrows()))
                if p.empty:
                    st.caption("No picks this week.")
                    continue
                show = p.assign(asset=[name_of(t, uni) for t in p["ticker"]])[["cls", "asset", "ticker", "direction", "this_week"]]
                st.dataframe(show.rename(columns={"cls": "Class", "asset": "Asset", "ticker": "Ticker",
                                                  "direction": "Action", "this_week": "Last week %"}).round(2),
                             hide_index=True, width="stretch")
    st.markdown("#### Forward-test only")
    for name, why in backtest.NOT_BACKTESTABLE.items():
        st.markdown(f"- **{name}:** {why}")


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_backtest(classes, start, end, vol_target, costs, entry="Friday close", rule="Hold to Friday",
                 tp_mode=backtest.TP_MODES[0], sl_mode=backtest.SL_MODES[0], tp_fixed=3.0, sl_fixed=3.0, min_move=0.0):
    uni, prices, _ = lab_prices(classes)
    rates, rec = lab_extras()
    sectors = assetlab.sector_map(classes)
    ohlc = {}
    for c in prices:
        try:
            o = assetlab.load_class_ohlc(c, tuple(t for t, _, _ in uni.get(c, [])))
            if o:
                ohlc[c] = o
        except Exception:
            pass
    return backtest.run(prices, start, end, lambda c: assetlab.horizon_days(c, "Next week"), sectors=sectors,
                        rates=rates, recession=rec, vol_target=vol_target, costs=costs, ohlc_by_class=ohlc,
                        entry=entry, rule=rule, tp_mode=tp_mode, sl_mode=sl_mode, tp_fixed=tp_fixed, sl_fixed=sl_fixed,
                        min_move=min_move)


# ---------------------------------------------------------------- v23: easy tables, focus list, minimum move

COUNT_WORDS = ("trades", "weeks", "calls", "count", "kept #", "assets")


def smart_table(df, key, height=None, column_config=None, totals=True, note=None):
    """
    A table with Excel-style filters (pick which columns to show, and which values to keep in any column)
    and a TOTAL row underneath: counts are added up, %s and ratios are averaged. Tick rows to total just those.
    """
    if df is None or len(df) == 0:
        st.info("Nothing to show for these settings.")
        return df
    df = df.reset_index(drop=True)
    with st.expander("🔎 Filter / hide columns", expanded=False):
        cols = st.multiselect("Columns to show", list(df.columns), default=list(df.columns), key=f"{key}_cols")
        fcols = st.multiselect("Filter by column", list(df.columns), key=f"{key}_fcols",
                               help="Pick a column, then choose which values (or which range) to keep.")
        for c in fcols:
            s = df[c]
            if pd.api.types.is_numeric_dtype(s) and s.notna().any():
                lo, hi = float(np.nanmin(s)), float(np.nanmax(s))
                if lo < hi:
                    r = st.slider(c, lo, hi, (lo, hi), key=f"{key}_f_{c}")
                    if isinstance(r, (tuple, list)) and len(r) == 2:
                        df = df[df[c].isna() | ((df[c] >= r[0]) & (df[c] <= r[1]))]
            else:
                vals = sorted({str(v) for v in s.dropna()})
                keep = st.multiselect(c, vals, default=vals, key=f"{key}_f_{c}")
                df = df[df[c].astype(str).isin(keep)]
    view = df[[c for c in cols if c in df.columns]] if cols else df
    extra = {}
    if height:                       # newer Streamlit refuses height=None: only pass it when set
        extra["height"] = int(height)
    if column_config:
        extra["column_config"] = column_config
    event = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row",
                         key=f"{key}_tbl", **extra)
    rows = []
    try:
        rows = list(event.selection.rows) if event is not None else []
    except Exception:
        rows = []
    if totals and len(view):
        sel = view.iloc[[r for r in rows if r < len(view)]] if rows else view
        tot = {}
        first = True
        for c in view.columns:
            s = sel[c]
            if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                tot[c] = s.sum() if any(w in str(c).lower() for w in COUNT_WORDS) else s.mean()
            else:
                tot[c] = (f"TOTAL · {len(sel)} ticked" if rows else f"TOTAL · all {len(sel)} shown") if first else ""
                first = False
        st.dataframe(pd.DataFrame([tot]).round(3), hide_index=True, width="stretch", key=f"{key}_tot")
        st.caption(note or "Total row: counts (trades, weeks) are added up; %s and ratios are averaged. "
                           "Tick rows in the table to total just those.")
    return view


LAST = focus.PATH.parent / "last_results.pkl"


def save_last(name, value):
    try:
        old = pd.read_pickle(LAST) if LAST.exists() else {}
    except Exception:
        old = {}
    old[name] = dict(value, saved=pd.Timestamp.now())
    try:
        LAST.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle(old, LAST)
    except Exception:
        pass


def load_last():
    try:
        return pd.read_pickle(LAST) if LAST.exists() else {}
    except Exception:
        return {}


def backtest_focus(cards, params):
    """Adds Focus / Parked status to each strategy side and updates the parked shelf."""
    if cards.empty:
        return cards
    rows = []
    for _, r in cards.iterrows():
        keep, why = focus.rule_strategy(r.get("avg_week"), r.get("vs_coin_week"), r.get("vs_coin_p"))
        rows.append(dict(name=r["side"], cls=r["cls"], keep=keep, reason=why, avg_week=r.get("avg_week"),
                         vs_coin_week=r.get("vs_coin_week"), verdict=r.get("verdict")))
    out = focus.sync("Strategy", rows, settings=params)
    cards = cards.copy()
    cards["status"] = [o["status"] for o in out]
    cards["focus_reason"] = [o["reason"] for o in out]
    return cards


def lab_focus_winners(cards, side_returns, start, end, key):
    if cards.empty or "status" not in cards:
        st.info("Nothing to show yet.")
        return
    f = cards[cards["status"].str.startswith("🎯")]
    sure = f[(f.get("vs_coin_week", 0) > 0) & (f.get("vs_coin_p", 1) < 0.05)] if "vs_coin_p" in f else f.iloc[0:0]
    st.markdown(f"**🎯 {len(f)} of {len(cards)} strategy sides are in focus** "
                f"({len(sure)} clearly beat the coin toss). **🅿️ {len(cards) - len(f)} parked** for later: see PARKED.")
    only_sure = st.toggle("Only show the ones that clearly beat the coin toss (✅)", value=False, key=f"{key}_sure")
    pick = sure if only_sure else f
    if pick.empty:
        st.info("None in this group yet.")
        return
    curves, rets = {}, []
    for _, r in pick.iterrows():
        s = side_returns.get((r["side"], r["cls"]))
        if s is None:
            continue
        curves[f"{r['side']} · {r['cls']}"] = ((1 + s.fillna(0) / 100).cumprod() - 1) * 100
        rets.append(s.fillna(0).rename(f"{r['side']} · {r['cls']}"))
    if rets:
        combo = pd.concat(rets, axis=1).mean(axis=1)
        curves = {"★ ALL OF THEM TOGETHER (equal split)": ((1 + combo / 100).cumprod() - 1) * 100, **curves}
    if len(curves) > 13:
        st.caption(f"Showing the combined line and the 12 best of {len(curves) - 1}.")
        best = sorted([k for k in curves if not k.startswith("★")], key=lambda k: curves[k].iloc[-1], reverse=True)[:12]
        curves = {k: v for k, v in curves.items() if k.startswith("★") or k in best}
    lab_line_chart(curves, 420, f"{key}_winners", title="Cumulative return % (after costs)")
    mid = pd.Timestamp(start) + (pd.Timestamp(end) - pd.Timestamp(start)) / 2
    st.caption(f"The combined line splits your money equally across the strategies shown. The verdict's 'second "
               f"half' (the confirming part) starts around {mid:%d %b %Y}: check the lines keep rising after it.")
    show = pick.reindex(columns=["side", "cls", "avg_week", "vs_coin_week", "win_rate", "max_dd", "weeks", "verdict",
                                 "focus_reason"]).rename(columns={
        "side": "Side", "cls": "Class", "avg_week": "Avg week %", "vs_coin_week": "Edge over coin %",
        "win_rate": "Winning weeks %", "max_dd": "Worst drop %", "weeks": "Weeks", "verdict": "Verdict",
        "focus_reason": "Why it's in focus"})
    smart_table(show.sort_values("Avg week %", ascending=False).round(2), f"{key}_focus")


def lab_threshold_tab(th, key, current=0.0):
    st.caption("What if you only traded when the expected move was big enough? Each row re-runs a side keeping "
               "only trades where the expected move (in the trade's direction) was at least that %. Fewer trades "
               "aren't automatically better: look for the level where 'Avg week' rises without 'Trades' collapsing.")
    if th is None or len(th) == 0:
        st.info("No expected-move data for these settings.")
        return
    th = th.copy()
    sides = sorted(th["side"].unique())
    default = [s for s in sides if s.startswith("Model")] or sides[:3]
    pick = st.multiselect("Sides", sides, default=default[:4], key=f"{key}_th_sides")
    t = th[th["side"].isin(pick)] if pick else th
    t = t.rename(columns={"side": "Side", "cls": "Class", "min_move": "Minimum move %", "trades": "Trades",
                          "kept": "Trades kept %", "avg_week": "Avg week %", "win_rate": "Winning weeks %",
                          "total": "Total return %", "weeks": "Weeks traded"})
    smart_table(t.round(2), f"{key}_th")
    if current:
        st.caption(f"This run used a minimum move of {current}%.")


def lab_trade_rules_tab(cards, settings):
    st.caption("Did each side beat a coin toss? The coin toss makes the same trades on the same assets and weeks, "
               "with the same rules and costs, but flips a coin for buy or sell (we use the average of both). "
               "Beating it means the side's direction calls add something, not just the choice of asset or rules.")
    if cards.empty or "coin_week" not in cards:
        st.info("No trades to check in this period.")
        return
    show = cards.copy()
    show["Beats coin toss?"] = [
        ("✅ yes (p<0.05)" if p < 0.05 else "🟡 slightly" if p < 0.2 else "≈ no difference") if (d == d and d > 0)
        else ("❌ worse" if d == d and p == p and p < 0.2 else "≈ no difference") if d == d else "—"
        for d, p in zip(show.get("vs_coin_week", pd.Series(np.nan, index=show.index)),
                        show.get("vs_coin_p", pd.Series(np.nan, index=show.index)))]
    cols = {"status": "Status", "side": "Side", "cls": "Class", "avg_week": "Avg week %", "coin_week": "Coin toss week %",
            "vs_coin_week": "Edge over coin %", "Beats coin toss?": "Beats coin toss?"}
    if "hold_week" in show:
        cols["hold_week"] = "Same side, hold to Friday %"
    for k, v in {"hit_target": "Hit target %", "hit_stop": "Hit stop %", "to_friday": "Closed Friday %",
                 "trades": "Trades"}.items():
        if k in show:
            cols[k] = v
    show = show[[c for c in cols if c in show]].rename(columns=cols)
    smart_table(show.sort_values("Edge over coin %", ascending=False, na_position="last").round(2), "bt_coin")
    edge = cards.get("vs_coin_week")
    if edge is not None and edge.notna().any():
        n_beat = int(((cards["vs_coin_week"] > 0) & (cards["vs_coin_p"] < 0.05)).sum())
        st.markdown(f"**{n_beat} of {int(edge.notna().sum())}** sides beat the coin toss clearly (p<0.05).")
    if settings.get("rule") == "Take-profit + stop-loss" and "hold_week" in cards:
        better = (cards["avg_week"] > cards["hold_week"]).sum()
        st.markdown(f"Take-profit + stop-loss did better than holding to Friday for **{int(better)} of "
                    f"{int(cards['hold_week'].notna().sum())}** sides.")
        st.caption("Tip: lots of 'Hit stop' with few 'Hit target' usually means the stop is too tight for normal "
                   "day-to-day wobbles. Try the 5th percentile stop or a wider fixed %.")


def lab_backtest_section(classes_default):
    st.caption("Walk-forward test: for every Friday in your chosen period, the model only sees prices up to that "
               "day, makes its predictions and every side's picks, then gets checked against what really happened "
               "the next week. Nothing from the future is used.")
    c1, c2, c3 = st.columns([2.2, 1, 1])
    classes = c1.multiselect("Asset classes to test", assetlab.CLASSES, default=list(classes_default), key="bt_cls")
    today = pd.Timestamp.now().normalize()
    start = c2.date_input("From", value=(today - pd.DateOffset(weeks=52)).date(),
                          min_value=(today - pd.DateOffset(years=9)).date(), max_value=(today - pd.DateOffset(weeks=6)).date(),
                          key="bt_start")
    end = c3.date_input("To", value=(today - pd.DateOffset(days=7)).date(), key="bt_end")
    c4, c5, c6 = st.columns([1, 1, 2])
    vol_target = c4.toggle("Volatility targeting", value=True, key="bt_vt",
                           help="Bet less on wild assets and more on calm ones, so each holding carries similar risk.")
    costs = c5.toggle("Include trading costs", value=True, key="bt_costs",
                      help="Spreads, Trading 212's 0.15% FX fee on US stocks, 0.5% UK stamp duty, CFD overnight fees on shorts.")
    weeks = max(1, (pd.Timestamp(end) - pd.Timestamp(start)).days // 7)
    if weeks < 26:
        st.warning(f"That's only {weeks} weeks. Results over less than about 6 months are mostly luck, and some "
                   "numbers (like 'vs holding the class' and the two-halves verdict) need more weeks to work out. "
                   "Try at least a year.")
    c6.caption(f"{weeks} weeks × your chosen classes. One year of everything takes a few minutes the first time; "
               "ten years can take 10–20 minutes. Results are saved for 6 hours.")
    st.markdown("**Trade rules** · how each practice trade is placed and closed")
    r1, r2 = st.columns(2)
    entry = r1.radio("Enter at", list(backtest.ENTRIES), horizontal=True, key="bt_entry",
                     help=" ".join(f"{k}: {v}" for k, v in backtest.ENTRIES.items()))
    rule = r2.radio("Exit rule", list(backtest.TRADE_RULES), horizontal=True, key="bt_rule",
                    help=" ".join(f"{k}: {v}" for k, v in backtest.TRADE_RULES.items()))
    tp_mode, sl_mode, tp_fixed, sl_fixed = backtest.TP_MODES[0], backtest.SL_MODES[0], 3.0, 3.0
    if rule == "Take-profit + stop-loss":
        r3, r4, r5, r6 = st.columns([1.6, 0.7, 1.6, 0.7])
        tp_mode = r3.selectbox("Take-profit level", backtest.TP_MODES, key="bt_tp_mode",
                               help="Where to bank the profit. 'Good week' = the model's 75th percentile move in your "
                                    "favour (only 1 in 4 simulated weeks went further).")
        tp_fixed = float(r4.number_input("Fixed TP %", 0.1, 50.0, 3.0, 0.5, key="bt_tp_fixed",
                                         disabled=tp_mode != "Fixed %"))
        sl_mode = r5.selectbox("Stop-loss level", backtest.SL_MODES, key="bt_sl_mode",
                               help="Where to cut the loss. 'Bad week' = the model's 5th percentile (only 1 in 20 "
                                    "simulated weeks were worse). 'Weak week' = 25th percentile, a much tighter stop.")
        sl_fixed = float(r6.number_input("Fixed SL %", 0.1, 50.0, 3.0, 0.5, key="bt_sl_fixed",
                                         disabled=sl_mode != "Fixed %"))
        st.caption("Checked every day using that day's high and low. If the price opens past a level (a gap), the "
                   "trade closes at the open price. If both levels are touched the same day we assume the stop came "
                   "first (the cautious choice). If neither is hit, the trade closes at Friday's close.")
    min_move = float(st.number_input("Only trade if the expected move is at least (%) · 0 = take every trade",
                                     0.0, 5.0, 0.0, 0.1, key="bt_min",
                                     help="Uses the Monte Carlo's 'trend continues' median for each pick, in the "
                                          "trade's direction (+0.8% to buy, −0.8% to short). The 'Minimum move' tab "
                                          "shows what different levels would have done."))
    if not classes:
        return
    if not st.button("▶ Run the backtest", key="bt_run"):
        if "al_bt" not in st.session_state:
            return
    else:
        st.session_state["al_bt"] = (tuple(classes), str(start), str(end), vol_target, costs, entry, rule,
                                     tp_mode, sl_mode, tp_fixed, sl_fixed, min_move)
    params = st.session_state["al_bt"]
    with ui.loading("Walking forward through history", scene="model", steps=["Loading 25 years of prices", "Replaying every Friday", "Adding costs and stop-losses", "Comparing with the S&P 500", "Running the statistics"]):
        try:
            res = lab_backtest(*params)
        except Exception as exc:
            st.error(f"The backtest failed ({type(exc).__name__}: {exc}).")
            with st.expander("Technical details"):
                st.exception(exc)
            return
    st.session_state["al_bt_scores"] = res["scorecards"]
    pred, cards = res["predictions"], res["scorecards"]
    if cards.empty and pred.empty:
        st.warning("Not enough data in that period. Try a longer period or more asset classes.")
        return
    st.success(f"Tested {res['start']:%d %b %Y} to {res['end']:%d %b %Y}: {len(pred):,} Monte Carlo predictions and "
               f"{len(cards)} strategy sides.")
    settings = res.get("settings", {})
    rule_txt = settings.get("rule", "Hold to Friday")
    if rule_txt != "Hold to Friday":
        rule_txt += f" (TP: {settings.get('tp_mode')}, SL: {settings.get('sl_mode')})"
    st.caption(f"Trade rules used: enter at **{settings.get('entry', 'Friday close')}**, exit rule **{rule_txt}**."
               + ("" if settings.get("ohlc") else " Daily highs/lows were unavailable, so closing prices were used."))
    cards = backtest_focus(cards, params)
    save_last("backtest", dict(cards=cards, params=params, side_returns=res["side_returns"],
                               start=res["start"], end=res["end"], thresholds=res.get("thresholds")))
    t0, t1, t5, t6, t2, t3, t4 = st.tabs(["⭐ Focus winners", "All strategies", "Trade rules check", "Minimum move",
                                          "Strategy race", "Model accuracy", "Calibration & charts"])
    with t0:
        lab_focus_winners(cards, res["side_returns"], res["start"], res["end"], "bt")
    with t5:
        lab_trade_rules_tab(cards, settings)
    with t6:
        lab_threshold_tab(res.get("thresholds"), "bt", res.get("min_move", 0))
    with t1:
        st.caption("Every side's average weekly return after costs, compared with holding the whole asset class and "
                   "with a coin toss. 'Verdict' uses the first half of the period to choose and the second half to "
                   "confirm. Tick rows to total just those.")
        show = cards.copy()
        show = show.reindex(columns=list(dict.fromkeys(list(show.columns) + ["p", "excess_week", "vs_coin_week"])))
        show["Luck?"] = show["p"].map(lambda p: "unlikely (p<0.05)" if p < 0.05 else "possible" if p < 0.2 else
                                      "likely" if p == p else "too few weeks")
        show = show.reindex(columns=["status", "side", "cls", "verdict", "avg_week", "vs_coin_week", "excess_week",
                                     "win_rate", "sharpe", "max_dd", "weeks", "Luck?", "focus_reason"]).rename(columns={
            "status": "Status", "side": "Side", "cls": "Class", "verdict": "Verdict", "avg_week": "Avg week %",
            "vs_coin_week": "Edge over coin %", "excess_week": "vs holding class %", "win_rate": "Winning weeks %",
            "sharpe": "Sharpe", "max_dd": "Worst drop %", "weeks": "Weeks", "focus_reason": "Why focus / parked"})
        smart_table(show.sort_values("Avg week %", ascending=False).round(2), "bt_all")
        worked = cards[cards["verdict"].str.startswith("✅")]
        st.markdown(f"**{len(worked)} of {len(cards)}** sides worked in both halves. "
                    + ("With this many sides, expect one or two to pass by luck alone: watch whether they keep "
                       "working in the PREDICTION LOG." if len(cards) > 10 else ""))
    with t2:
        cls_pick = st.selectbox("Asset class", sorted({c for _, c in res["side_returns"]}), key="bt_race_cls")
        curves = {n: ((1 + r / 100).cumprod() - 1) * 100 for (n, c), r in res["side_returns"].items() if c == cls_pick}
        if cls_pick in res["benches"]:
            curves["(Hold the whole class)"] = ((1 + res["benches"][cls_pick].fillna(0) / 100).cumprod() - 1) * 100
        lab_line_chart(curves, 420, "bt_race", title="Cumulative return %")
        st.caption("Each line is one side's practice-account profit over the test period, after costs.")
    if pred.empty:
        return
    with t3:
        view = st.segmented_control("Model's view", ["none", "trend", "bounce"], default="none", key="bt_view",
                                    format_func={"none": "No view", "trend": "Trend continues", "bounce": "Bounce back"}.get) or "none"
        rows = []
        for c in ["All"] + sorted(pred["cls"].unique()):
            a = backtest.accuracy(pred if c == "All" else pred[pred["cls"] == c], view)
            if a:
                rows.append(dict(Class=c, Predictions=a["n"], **{
                    "Right direction %": a["hit"], "Avg miss (pp)": a["mae"], "'No change' avg miss (pp)": a["mae_naive"],
                    "Inside 90% range %": a["coverage"], "Brier score": a["brier"], "Coin-toss Brier": a["brier_coin"]}))
        st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
        st.caption("Right direction above 50% = better than a coin toss. Avg miss below 'no change' = the model "
                   "beats assuming nothing moves. Inside 90% range should be close to 90% (lower = ranges too narrow). "
                   "Brier score: lower is better; below the coin-toss Brier = the probabilities add something.")
        d = pred.dropna(subset=["actual"])
        d = d.assign(right=(np.sign(d[f"median_{view}"]) == np.sign(d["actual"])).astype(float))
        roll = d.groupby("date")["right"].mean().rolling(8, min_periods=3).mean() * 100
        lab_line_chart({"Right direction % (8-week rolling)": roll}, 260, "bt_roll", unit="%", zero=False)
        said_up, went_up = d[f"median_{view}"] > 0, d["actual"] > 0
        st.markdown("**Up/down scorecard**")
        st.dataframe(pd.DataFrame({"It went up": [int((said_up & went_up).sum()), int((~said_up & went_up).sum())],
                                   "It went down": [int((said_up & ~went_up).sum()), int((~said_up & ~went_up).sum())]},
                                  index=["We said up", "We said down"]), width="stretch")
    with t4:
        view = st.session_state.get("bt_view") or "none"
        cal = backtest.calibration_table(pred, view)
        c1, c2 = st.columns(2, gap="small")
        with c1, st.container(border=True):
            ui.panel_title("Calibration", "WE SAID X% · IT HAPPENED Y%")
            fig = go.Figure()
            fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines", name="Perfect", line=dict(color="#55606C", dash="dot"))
            if not cal.empty:
                fig.add_scatter(x=cal["said"], y=cal["happened"], mode="lines+markers", name="Our model",
                                marker=dict(size=[max(6, min(18, n / 40)) for n in cal["n"]]), line=dict(color=ui.CYAN))
            st.plotly_chart(ui.base_layout(fig, 300, legend=True), width="stretch", config=ui.PLOT_CONFIG, key="bt_cal")
            st.caption("If the model says '60% chance of a rise', it should rise about 60% of the time. Points on the "
                       "dotted line = honest probabilities.")
        with c2, st.container(border=True):
            ui.panel_title("Predicted vs actual", "EVERY ASSET-WEEK")
            sample = pred.dropna(subset=["actual"]).sample(min(3000, len(pred.dropna(subset=["actual"]))), random_state=1)
            fig = go.Figure()
            fig.add_scatter(x=sample[f"median_{view}"], y=sample["actual"], mode="markers", name="",
                            marker=dict(size=4, color=ui.CYAN, opacity=0.35))
            fig = ui.base_layout(fig, 300)
            fig.update_layout(xaxis_title="Predicted (median %)", yaxis_title="Actual %")
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="bt_pva")
            st.caption("A tilt from bottom-left to top-right would mean the predictions carry information. A flat "
                       "cloud means the actual moves are mostly noise compared with what we predicted.")


def lab_why_we_missed():
    params = st.session_state.get("al_bt")
    if not params:
        st.info("Run a BACKTEST first. This section breaks down that backtest's misses.")
        return
    res = lab_backtest(*params)
    pred = res["predictions"]
    if pred.empty:
        st.warning("No predictions in the last backtest.")
        return
    view = st.segmented_control("Model's view", ["none", "trend", "bounce"], default="trend", key="wm_view",
                                format_func={"none": "No view", "trend": "Trend continues", "bounce": "Bounce back"}.get) or "trend"
    summary, d = backtest.breakdown(pred, view)
    if not summary:
        st.warning("Not enough data to break down.")
        return
    st.caption("Every miss (what actually happened minus our median) is split into four pieces that add up exactly "
               "to the miss: the WHOLE MARKET (the class's average move × how sensitive this asset usually is to it), "
               "its SECTOR (stocks only), OUR DRIFT (the part caused by the view we chose) and NOISE (company news "
               "and randomness).")
    labels = {"market": "Whole market", "sector_part": "Sector", "drift": "Our drift view", "noise": "Noise / company news"}
    c1, c2 = st.columns([1.3, 1], gap="small")
    with c1, st.container(border=True):
        ui.panel_title("Where the misses came from", "SHARE OF TOTAL MISS")
        fig = go.Figure()
        vals = [summary["share"][k] for k in labels]
        fig.add_bar(x=list(labels.values()), y=vals, marker_color=[ui.CYAN, "#C792EA", "#FFD166", "#55606C"])
        st.plotly_chart(ui.base_layout(fig, 300, unit="%"), width="stretch", config=ui.PLOT_CONFIG, key="wm_bar")
    with c2, st.container(border=True):
        ui.panel_title("Key numbers")
        ui.des_table([("Average miss", f"{summary['avg_miss']:.2f}pp"),
                      ("Bias (average of misses)", f"{summary['bias']:+.2f}pp " + (
                          "<span class='hs'>(we're too pessimistic)</span>" if summary["bias"] > 0.1 else
                          "<span class='hs'>(we're too optimistic)</span>" if summary["bias"] < -0.1 else
                          "<span class='hs'>(no consistent lean)</span>")),
                      ("Outside the 90% range", f"{summary['outside']:.1f}% <span class='hs'>(should be ~10%)</span>"),
                      ("Event-sized surprises", f"{summary['event_rate']:.1f}% <span class='hs'>(noise over 3× the expected spread)</span>")])
    biggest = max(labels, key=lambda k: summary["share"][k])
    advice = {
        "market": "Most of the miss came from the whole market moving. A single-asset model can't fix that; the "
                  "fix is to predict the market itself, or judge assets RELATIVE to their class.",
        "sector_part": "Sectors moving together caused a big share. Adding sector signals (e.g. sector momentum) could help.",
        "drift": "Our drift view is a big part of the miss, so that view is making things WORSE than no view. Try "
                 "'No view' or 'Bounce back', or a smaller drift.",
        "noise": "Most of the miss is noise: company news and random moves the model can't see. You can't predict it "
                 "away, but you can dodge and dilute it: MODEL → Risk checks (skip event weeks and wild assets), more "
                 "positions ('strongest 10'), hedged sides, and 2- or 4-week holds. Use 'What caused the biggest "
                 "misses' below to see how much of it was scheduled (avoidable).",
    }
    st.markdown(f"**Biggest source: {labels[biggest]}.** {advice[biggest]}")
    if summary["outside"] > 13:
        st.markdown("**The 90% ranges are too narrow:** reality landed outside them more than 10% of the time. "
                    "The volatility estimate needs widening.")
    elif summary["outside"] < 7:
        st.markdown("**The 90% ranges are too wide:** reality almost always landed inside, so the ranges are "
                    "over-cautious.")
    with st.container(border=True):
        ui.panel_title("By asset class", "AVERAGE SIZE OF EACH PIECE (pp)")
        by = d.groupby("cls")[["miss", "market", "sector_part", "drift", "noise"]].apply(lambda g: g.abs().mean())
        by["outside 90% range %"] = d.groupby("cls")["outside_range"].mean() * 100
        by["bias"] = d.groupby("cls")["miss"].mean()
        st.dataframe(by.rename(columns={"miss": "Avg miss", **labels}).round(2), width="stretch")
    with st.container(border=True):
        ui.panel_title("The biggest misses", "WHAT EXPLAINS EACH")
        worst = d.reindex(d["miss"].abs().sort_values(ascending=False).index).head(25)
        worst = worst.assign(main=[labels[max(labels, key=lambda k: abs(r[k]))] for _, r in worst.iterrows()])
        st.dataframe(worst[["date", "ticker", "cls", f"median_{view}", "actual", "miss", "market", "sector_part",
                            "drift", "noise", "main", "event_like"]].rename(columns={
            "date": "Week of", "ticker": "Ticker", "cls": "Class", f"median_{view}": "Predicted %", "actual": "Actual %",
            "miss": "Miss", "market": "Market", "sector_part": "Sector", "drift": "Our drift", "noise": "Noise",
            "main": "Main reason", "event_like": "Event-sized?"}).round(2), hide_index=True, width="stretch")
    st.caption("A single miss is mostly noise and shouldn't be 'fixed' on its own (that's overfitting). Look for "
               "patterns across thousands of misses: a consistent bias, ranges that are too narrow, or one piece "
               "that keeps dominating.")
    with st.container(border=True):
        ui.panel_title("What caused the biggest misses", "CREDIBLE SOURCES ONLY")
        st.caption("Looks up each big miss in official sources first (company filings to the SEC, the earnings "
                   "calendar, Fed and inflation dates), then trusted newsrooms (Reuters, Bloomberg, FT, WSJ, AP, CNBC…) "
                   "with re-written copies removed. 📅 Scheduled = we could have known the date (avoidable). "
                   "⚡ Unscheduled = genuine bad luck. US stocks get company news; other classes get event dates.")
        n_tag = st.slider("How many of the biggest misses to check", 10, 60, 25, 5, key="wm_n")
        recent = d[d["date"] >= d["date"].max() - pd.Timedelta(days=365)]
        if st.button("🔎 Find the causes", key="wm_tag"):
            st.session_state["wm_tag_params"] = (tuple(params), view, n_tag)
        if st.session_state.get("wm_tag_params") == (tuple(params), view, n_tag):
            worst_recent = recent.reindex(recent["miss"].abs().sort_values(ascending=False).index).head(n_tag)
            tags, errs = lab_tag_misses(worst_recent[["date", "ticker", "cls", "miss"]].reset_index(drop=True))
            if tags.empty:
                st.info("Nothing to check.")
            else:
                share = tags["type"].str[:1].value_counts(normalize=True) * 100
                st.markdown(f"**📅 Scheduled: {share.get('📅', 0):.0f}%** · ⚡ Unscheduled: {share.get('⚡', 0):.0f}% · "
                            f"❔ Unexplained: {share.get('❔', 0):.0f}% of the biggest misses in the last year.")
                if share.get("📅", 0) >= 25:
                    st.markdown("A big share was scheduled, so these misses were avoidable: check whether the "
                                "**Event next week** risk check earns a ✅ in MODEL → Risk checks.")
                st.dataframe(tags.rename(columns={"date": "Week of", "ticker": "Ticker", "cls": "Class", "miss": "Miss (pp)",
                                                  "type": "Type", "cause": "Cause", "source": "Source", "headline": "Headline",
                                                  "link": "Link", "other_sources": "Other matches"}).round(2),
                             hide_index=True, width="stretch",
                             column_config={"Link": st.column_config.LinkColumn("Link", display_text="open")})
            for e in errs:
                st.caption(f"⚠ {e}")


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def lab_tag_misses(worst):
    classes = tuple(sorted(worst["cls"].unique()))
    ctx, _ = lab_context(classes)
    earnings = {}
    for t in worst.loc[worst["cls"].isin(["US stocks", "UK stocks"]), "ticker"].unique():
        e = companies._load("fh_earnings", t)
        if e:
            earnings[t] = pd.DatetimeIndex(companies.parse_earnings(e)["date"])
    return news.tag_misses(worst, ctx, earnings, max_items=len(worst), progress=_progress_cb())


def lab_prediction_log(prices):
    st.caption("Every time you press 'Save these predictions' in SCANNER, every asset's prediction is stored. Once "
               "the week (or month) is over, it's scored against what actually happened. This is the only honest "
               "test of the attention-based ideas, because past news counts aren't available.")
    if not PREDICTION_LOG.exists():
        st.info("No predictions saved yet. Go to SCANNER and press '💾 Save these predictions to the log'.")
        return

    def lookup(ticker):
        for p in prices.values():
            if ticker in p.columns:
                return p[ticker].dropna()
        return None
    log = backtest.score_log(PREDICTION_LOG, lookup)
    scored = log.dropna(subset=["actual"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Predictions saved", f"{len(log):,}")
    c2.metric("Scored so far", f"{len(scored):,}")
    if len(scored):
        c3.metric("Right direction", f"{scored['right_way'].mean() * 100:.0f}%")
        c4.metric("Inside 90% range", f"{scored['inside'].mean() * 100:.0f}%")
        radar = scored[scored["under_radar"] == True]   # noqa: E712
        if len(radar):
            st.markdown(f"**Under-the-radar top 3 picks:** {len(radar)} scored, right direction "
                        f"{radar['right_way'].mean() * 100:.0f}%, average move in the predicted direction "
                        f"{(np.sign(radar['median']) * radar['actual']).mean():+.2f}%.")
        if "attn_vs_normal" in scored and scored["attn_vs_normal"].notna().sum() > 20:
            q = scored.dropna(subset=["attn_vs_normal"])
            low = q[q["attn_vs_normal"] < 1]
            st.markdown(f"**Quieter than usual (attention < 1×):** right direction "
                        f"{low['right_way'].mean() * 100:.0f}% vs {q['right_way'].mean() * 100:.0f}% overall.")
    st.dataframe(log.sort_values("logged", ascending=False)[["logged", "target", "ticker", "name", "cls", "view", "median",
                                                            "p5", "p95", "actual", "right_way", "inside", "under_radar"]]
                 .rename(columns={"logged": "Saved", "target": "Scored on", "ticker": "Ticker", "name": "Asset",
                                  "cls": "Class", "view": "View", "median": "Predicted %", "p5": "5th pct",
                                  "p95": "95th pct", "actual": "Actual %", "right_way": "Right way?",
                                  "inside": "Inside range?", "under_radar": "Top 3?"}).round(2),
                 hide_index=True, width="stretch")


def lab_risk(scan_df, att, prices, uni, horizon):
    st.caption("Picks that move together are really one bet. This simulates your picks TOGETHER (every simulated "
               "day replays the same real past day for all of them) and shows how correlated they are.")
    options = {f"{r['name']} ({r['ticker']})": (r["ticker"], r["cls"])
               for _, r in pd.concat([att.sort_values("radar", ascending=False), scan_df]).drop_duplicates("ticker").iterrows()}
    default = list(options)[:3]
    chosen = st.multiselect("Your picks", list(options), default=default, key="risk_picks")
    if len(chosen) < 2:
        st.caption("Choose at least two.")
        return
    cols = {options[c][0]: prices[options[c][1]][options[c][0]] for c in chosen}
    frame = pd.DataFrame(cols)
    days = max(assetlab.horizon_days(options[c][1], horizon) for c in chosen)
    try:
        sims = backtest.joint_simulation(frame, days)
    except Exception as exc:
        st.warning(f"Couldn't simulate them together ({exc}).")
        return
    port = sims.mean(axis=1)
    c1, c2 = st.columns([1.3, 1], gap="small")
    with c1, st.container(border=True):
        ui.panel_title("Equal-weight portfolio of your picks", f"{horizon.upper()} · 10,000 JOINT SIMULATIONS")
        distribution_charts(port.values, "risk_port")
        ui.des_table([("Median", f"{port.median():+.2f}%"), ("Chance of a gain", f"{(port > 0).mean() * 100:.0f}%"),
                      ("90% range", f"{port.quantile(.05):+.1f}% to {port.quantile(.95):+.1f}%"),
                      ("Bad week (5th percentile)", f"{port.quantile(.05):+.1f}%"),
                      ("Diversification benefit", f"{(1 - port.std() / sims.std().mean()) * 100:.0f}% less spread than "
                                                  "an average single pick")])
    with c2, st.container(border=True):
        ui.panel_title("Correlation", "WEEKLY RETURNS, LAST YEAR")
        wk = frame.resample("W-FRI").last().pct_change(fill_method=None).iloc[-52:]
        corr = wk.corr()
        fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1,
                                   colorscale=[[0, ui.DOWN], [0.5, "#11161C"], [1, ui.UP]],
                                   text=corr.round(2).values, texttemplate="%{text}"))
        st.plotly_chart(ui.base_layout(fig, 300), width="stretch", config=ui.PLOT_CONFIG, key="risk_corr")
        st.caption("+1 = always move together, 0 = unrelated, -1 = opposites. Picks above about 0.7 are close to "
                   "being the same bet.")



# ---------------------------------------------------------------- v18: SIGNAL LAB and MODEL

@st.cache_data(ttl=60 * 60, show_spinner=False)
def lab_key_check():
    return signals.check_keys()


def lab_ohlc(classes, uni, prices):
    out = {}
    for c in prices:
        try:
            o = assetlab.load_class_ohlc(c, tuple(t for t, _, _ in uni.get(c, [])))
            if o:
                out[c] = o
        except Exception:
            pass
    return out


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_context(classes):
    signals.STATUS.clear()
    ctx = signals.build_context(classes)
    ctx["company"] = lab_company_data(classes, ctx) if "lab_company_data" in globals() else {}
    return ctx, dict(signals.STATUS)


def lab_company_data(classes, ctx):
    """Company-data ingredients (earnings, analysts, directors, accounts) for the stock classes, from the disk cache."""
    out = {}
    stock = [c for c in classes if c in ("UK stocks", "US stocks")]
    if not stock:
        return out
    uni, prices, _ = lab_prices(tuple(classes))
    sectors = assetlab.sector_map(classes)
    for c in stock:
        if c in prices:
            try:
                out[c] = companies.company_ingredients(c, prices[c].resample("W-FRI").last(), sectors)
            except Exception as exc:
                signals._status(f"Company data ({c})", False, exc)
    return out


def company_panel(classes):
    stock = [c for c in classes if c in ("UK stocks", "US stocks")]
    if not stock:
        return
    uni = assetlab.universe(stock)
    tickers = [t for c in stock for t, _, _ in uni.get(c, [])]
    with st.expander("Company data (earnings, analysts, directors, accounts)", expanded=False):
        cov = companies.coverage(tickers)
        st.dataframe(pd.DataFrame([{"Data": companies.DATASETS[k][2], "Source": companies.DATASETS[k][0].upper(),
                                    "Companies downloaded": f"{v} of {len(tickers)}"} for k, v in cov.items()]),
                     hide_index=True, width="stretch")
        st.caption("Free plans have limits, so this downloads in batches and saves everything on your PC. FMP's free "
                   "plan allows 250 requests a day (2 per company), so the accounts data takes a few days to fill. "
                   "UK companies may not be covered by the free plans.")
        mins = st.slider("Minutes to spend downloading", 2, 30, 8, key="co_mins")
        if st.button("⬇ Download company data", key="co_dl"):
            with ui.loading("Downloading company data", ["Contacting the data provider", "Reading the accounts", "Building the company view"]):
                summary = companies.download(tickers, max_minutes=mins, progress=_progress_cb())
            st.success(f"Downloaded {summary['done']} items. {summary['remaining']} still to go (press again later).")
            for src, errs in summary["errors"].items():
                st.caption(f"{src}: {len(errs)} problems, e.g. {errs[0]}")
            st.cache_data.clear()


def _progress_cb():
    bar = st.progress(0.0, text="Starting...")
    return lambda f, msg: bar.progress(min(1.0, max(0.0, float(f))), text=msg)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_signal_run(classes, start, end, unseen_frac):
    uni, prices, _ = lab_prices(classes)
    ohlc = lab_ohlc(classes, uni, prices)
    ctx, status = lab_context(classes)
    league, details, _ = signals.run_lab(prices, ohlc, ctx, start, end, unseen_frac, progress=_progress_cb())
    return league, details, status


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_model_run(classes, start, end, unseen_frac, shrink, key_mode, vol_target, costs, entry, rule,
                  tp_mode, sl_mode, tp_fixed, sl_fixed, ablation, engine="ridge", horizon=1, min_move=0.0):
    uni, prices, _ = lab_prices(classes)
    ohlc = lab_ohlc(classes, uni, prices)
    ctx, status = lab_context(classes)
    built, ml = None, None
    if engine == "arena":         # machine learning first, so the ridge run can check whether the two models agree
        ml = model.run_model(prices, ohlc, ctx, start, end, unseen_frac, shrink, key_mode, vol_target, costs, entry, rule,
                             tp_mode, sl_mode, tp_fixed, sl_fixed, ablation=False, engine="ml", progress=_progress_cb(),
                             horizon=horizon, risk_test=False, min_move=min_move)
        built = ml.pop("built", None)
        ctx = dict(ctx, _ml_preds=ml["preds"])
    first = "ridge" if engine == "arena" else engine
    res = model.run_model(prices, ohlc, ctx, start, end, unseen_frac, shrink, key_mode, vol_target, costs, entry, rule,
                          tp_mode, sl_mode, tp_fixed, sl_fixed, ablation=ablation and first == "ridge", engine=first,
                          progress=_progress_cb(), built=built, horizon=horizon, min_move=min_move)
    res.pop("built", None)
    if ml is not None:
        res["arena"] = model.arena({"Combiner (ridge)": res, "Machine learning": ml})
        res["learned"] = ml.get("learned", {})
        res["ml_weights"] = ml["weights"]
        res["ml_latest"] = ml["latest"]
    res["status"] = status
    res["names"] = {t: n for members in uni.values() for t, n, _ in members}
    # Monte Carlo take-profit / stop-loss levels for this week's strongest calls
    levels = {}
    for cls, (t, last) in res["latest"].items():
        for tick in list(last.index[:5]):
            try:
                m = backtest.mc_at_dates(prices[cls][tick], [t], assetlab.horizon_days(cls, "Next week"), n_sims=2000)
                if not m.empty:
                    levels[tick] = m.iloc[-1].to_dict()
            except Exception:
                pass
    res["levels"] = levels
    return res


def data_sources_panel(status):
    with st.expander("Data sources and API keys", expanded=False):
        rows = [(k, "✅" if ok else "❌", msg) for k, (ok, msg) in status.items()]
        rows += [(label, s, d) for label, s, d in lab_key_check()]
        st.dataframe(pd.DataFrame(rows, columns=["Source", "Status", "Detail"]), hide_index=True, width="stretch")
        st.caption("Anything with ❌ just means those ingredients are skipped; everything else still runs. "
                   "Keys live in .streamlit/secrets.toml on your PC only.")


def period_controls(prefix, default_weeks=156):
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1.2])
    classes = c1.multiselect("Asset classes", assetlab.CLASSES, default=["FX", "Commodities", "World indices"],
                             key=f"{prefix}_cls")
    today = pd.Timestamp.now().normalize()
    start = c2.date_input("From", value=(today - pd.DateOffset(weeks=default_weeks)).date(),
                          min_value=(today - pd.DateOffset(years=8)).date(), max_value=(today - pd.DateOffset(weeks=20)).date(),
                          key=f"{prefix}_start")
    end = c3.date_input("To", value=(today - pd.DateOffset(days=7)).date(), key=f"{prefix}_end")
    if (pd.Timestamp(end) - pd.Timestamp(start)).days < 26 * 7:
        st.warning("That period is under 6 months: too short to split into discovery and unseen parts. "
                   "Try at least a year (3 years is better).")
    unseen = c4.slider("Kept unseen (%)", 20, 50, 30, 5, key=f"{prefix}_unseen",
                       help="The last part of the period is hidden while choosing, and only used to confirm. "
                            "An idea only counts if it works on both parts.")
    return classes, start, end, unseen / 100


VERDICT_HELP = ("**How to read the verdicts.** Each ingredient is scored on the discovery period and again on the "
                "unseen period. *t* says how sure we can be it isn't luck: around 2 or more is convincing, below 1 "
                "is noise. ✅ Confirmed = worked in both. 🔄 = worked backwards in both (still useful: the model "
                "just flips it). 🟡 = right direction in both but weak. ⚠️ = only the unseen period. ❌ = no edge, "
                "or it didn't survive the unseen period.")


def lab_signal_section():
    st.caption("Every idea is an *ingredient*: a score for each asset each Friday (higher = more likely to go up), "
               "using only what was known that day. Each one gets the same test.")
    classes, start, end, unseen = period_controls("sl")
    if not classes:
        return
    company_panel(classes)
    if st.button("▶ Test every ingredient", key="sl_run"):
        st.session_state["sl_params"] = (tuple(classes), str(start), str(end), unseen)
    if "sl_params" not in st.session_state:
        st.info("Pick asset classes and a period, then press the button. The first run downloads positioning, "
                "inventory and cross-asset data (a few minutes); after that it's quick.")
        data_sources_panel({})
        return
    try:
        league, details, status = lab_signal_run(*st.session_state["sl_params"])
    except Exception as exc:
        st.error(f"The Signal Lab failed ({type(exc).__name__}: {exc}).")
        with st.expander("Technical details"):
            st.exception(exc)
        return
    data_sources_panel(status)
    if league.empty:
        st.warning("Not enough data in that period. Try a longer period.")
        return
    league = ingredient_focus(league, st.session_state["sl_params"])
    save_last("signal", dict(league=league, params=st.session_state["sl_params"]))
    counts = league["verdict"].str[:1].value_counts()
    n = len(league)
    groups = {
        "works": ("✅ What works", ["✅", "🔄"], "#4CC38A"),
        "maybe": ("🟡 Maybe", ["🟡", "⚠"], "#FFD166"),
        "failed": ("❌ Didn't work", ["❌", "N"], "#FF6B6B"),
    }
    lab_tiles(league, counts, n)
    st.caption(f"Reality check: with {n} tests, pure luck alone would make roughly {max(1, round(n * 0.02))} look "
               "'confirmed'. The MODEL and the prediction log check what really survives.")
    maths = st.toggle("Show the maths (t-stats, rank correlation)", value=False, key="sl_maths")
    detail = st.session_state.get("sl_detail")
    if detail and tuple(detail) in details:
        with st.container(border=True):
            lab_ingredient_detail(tuple(detail), details, league)
            if st.button("✕ Close", key="sl_close"):
                st.session_state["sl_detail"] = None
    tabs = st.tabs([groups["works"][0], groups["maybe"][0], groups["failed"][0], "By asset class", "All (table)",
                    "Ingredient guide"])
    with tabs[0]:
        sub = league[league["verdict"].str[:1].isin(groups["works"][1])]
        st.caption("Worked in the discovery period AND held up on the unseen period. 🔄 = works backwards "
                   "(the model just flips it).")
        lab_cards(sub, details, "w", maths)
    with tabs[1]:
        sub = league[league["verdict"].str[:1].isin(groups["maybe"][1])]
        st.caption("Pointing the right way but not convincing yet, or only working recently. Watch these in the "
                   "prediction log before trusting them.")
        lab_cards(sub, details, "m", maths)
    with tabs[2]:
        sub = league[league["verdict"].str[:1].isin(groups["failed"][1])]
        st.caption("Grouped by WHY they failed, so we learn something from each one.")
        reasons = {
            "❌ Failed to confirm": "🎲 Looked good, then failed on unseen data (luck, or the effect faded)",
            "❌ No effect": "😐 Never had an edge (indistinguishable from a coin toss)",
            "Not enough data": "📭 Not enough data (rare events, or the data didn't load)",
        }
        for v, title in reasons.items():
            g = sub[sub["verdict"] == v]
            if g.empty:
                continue
            with st.expander(f"{title} · {len(g)}", expanded=v == "❌ Failed to confirm"):
                lab_cards(g, details, f"f{v[:3]}", maths, compact=True)
    with tabs[3]:
        cls_tabs = st.tabs(sorted(league["cls"].unique()))
        for ct, cls in zip(cls_tabs, sorted(league["cls"].unique())):
            with ct:
                g = league[league["cls"] == cls]
                c = g["verdict"].str[:1].value_counts()
                st.markdown(f"**{cls}:** ✅ {c.get('✅', 0)} · 🔄 {c.get('🔄', 0)} · 🟡 {c.get('🟡', 0)} · "
                            f"⚠️ {c.get('⚠', 0)} · ❌ {c.get('❌', 0) + c.get('N', 0)} of {len(g)} ingredients")
                best = g[g["verdict"].str[:1].isin(["✅", "🔄", "🟡", "⚠"])]
                lab_cards(best if not best.empty else g.head(6), details, f"c{cls[:3]}", maths)
    with tabs[4]:
        st.markdown(VERDICT_HELP)
        cols = ["status", "ingredient", "family", "cls", "verdict", "disc_edge", "unseen_edge", "hit", "weeks", "why"]
        if maths:
            cols[6:6] = ["disc_t", "unseen_t", "ic"]
        smart_table(league[cols].rename(columns={"status": "Status",
            "ingredient": "Ingredient", "family": "Family", "cls": "Class", "verdict": "Verdict",
            "disc_edge": "Discovery % / week", "disc_t": "Discovery t", "unseen_edge": "Unseen % / week",
            "unseen_t": "Unseen t", "hit": "Right direction %", "ic": "Rank correlation", "weeks": "Weeks",
            "why": "Why (learn from it)"}).round(3), "sl_all", height=520)
    with tabs[5]:
        for fam, desc in signals.FAMILIES.items():
            items = [(k, v) for k, v in signals.INGREDIENTS.items() if v[1] == fam]
            if not items:
                continue
            with st.expander(f"{fam} · {len(items)}"):
                st.markdown(desc)
                for k, (name, _, what, why) in items:
                    st.markdown(f"- **{name}**: {what} *Why:* {why}")


VERDICT_COLOURS = {"✅": "#4CC38A", "🔄": "#4CC38A", "🟡": "#FFD166", "⚠": "#FFD166", "❌": "#FF6B6B", "N": "#55606C"}


def ingredient_focus(league, params):
    rows = []
    for _, r in league.iterrows():
        keep, why = focus.rule_ingredient(r["verdict"], r.get("unseen_edge"))
        rows.append(dict(name=r["key"], cls=r["cls"], keep=keep, reason=why, label=r["ingredient"]))
    out = focus.sync("Ingredient", rows, settings=params)
    league = league.copy()
    league["status"] = [o["status"] for o in out]
    return league


def lab_tiles(league, counts, n):
    tiles = [("✅ Confirmed", counts.get("✅", 0), "#4CC38A"), ("🔄 Reverse", counts.get("🔄", 0), "#4CC38A"),
             ("🟡 Promising", counts.get("🟡", 0), "#FFD166"), ("⚠️ Recent only", counts.get("⚠", 0), "#FFD166"),
             ("❌ No edge", counts.get("❌", 0) + counts.get("N", 0), "#FF6B6B")]
    cols = st.columns(len(tiles))
    for col, (label, v, colour) in zip(cols, tiles):
        col.markdown(f"<div style='border:1px solid {colour};border-left:6px solid {colour};border-radius:6px;"
                     f"padding:8px 12px'><div style='font-size:12px;opacity:.8'>{label}</div>"
                     f"<div style='font-size:26px;font-weight:700'>{v}</div>"
                     f"<div style='font-size:11px;opacity:.6'>of {n} tests</div></div>", unsafe_allow_html=True)


def plain_line(r):
    hit = r.get("hit")
    edge = r.get("unseen_edge")
    v = str(r.get("verdict", ""))
    held = ("held up on unseen data" if v[:1] in ("✅", "🔄") else "weak on unseen data" if v[:1] in ("🟡",)
            else "only recently" if v[:1] == "⚠" else "didn't hold up" if v.startswith("❌ Failed") else "no edge")
    hit_txt = f"right {hit:.0f}% of the time" if hit == hit and hit is not None else ""
    edge_txt = f"{edge:+.2f}% a week unseen" if edge == edge and edge is not None else ""
    return " · ".join(x for x in (hit_txt, edge_txt, held) if x)


def lab_cards(df, details, prefix, maths=False, compact=False, per_row=3):
    if df.empty:
        st.info("Nothing here for these settings.")
        return
    rows = list(df.iterrows())
    for start in range(0, len(rows), per_row):
        cols = st.columns(per_row)
        for col, (i, r) in zip(cols, rows[start:start + per_row]):
            colour = VERDICT_COLOURS.get(str(r["verdict"])[:1], "#55606C")
            extra = (f"<div style='font-size:11px;opacity:.7'>t = {r['disc_t']:.1f} then {r['unseen_t']:.1f} · "
                     f"rank corr {r['ic']:.3f}</div>" if maths and r.get("disc_t") == r.get("disc_t") else "")
            with col:
                st.markdown(
                    f"<div style='border:1px solid #2A313A;border-left:6px solid {colour};border-radius:6px;"
                    f"padding:8px 12px;margin-bottom:6px'><div style='font-weight:700'>{r['ingredient']}</div>"
                    f"<div style='font-size:12px;opacity:.75'>{r['cls']} · {r['family']} · {r.get('status', '')}</div>"
                    f"<div style='font-size:13px;margin-top:4px'>{r['verdict']}</div>"
                    f"<div style='font-size:12px;opacity:.85'>{plain_line(r)}</div>{extra}"
                    + ("" if compact else f"<div style='font-size:11px;opacity:.6;margin-top:4px'>{r['why']}</div>")
                    + "</div>", unsafe_allow_html=True)
                if st.button("More ›", key=f"sl_more_{prefix}_{r['key']}_{r['cls']}"):
                    st.session_state["sl_detail"] = (r["key"], r["cls"])
                    st.rerun()


def lab_ingredient_detail(kc, details, league):
    k, c = kc
    res = details[(k, c)]
    name, fam, what, why = signals.INGREDIENTS.get(k, (k, "Other", "", ""))
    st.markdown(f"#### {name} · {c}\n{what}  \n*Why it might work:* {why}")
    st.markdown(f"**Verdict: {res['verdict']}.** {res['why']}")
    curve = res["curve"].fillna(0)
    fig = go.Figure()
    fig.add_scatter(x=curve.index, y=curve.cumsum(), mode="lines", name="Cumulative % (before costs)",
                    line=dict(color=ui.CYAN, width=1.8))
    fig.add_vline(x=res["cut"], line=dict(color="#FFD166", dash="dot"))
    fig.add_annotation(x=res["cut"], y=1, yref="paper", text="unseen →", showarrow=False, xanchor="left",
                       font=dict(color="#FFD166"))
    fig.add_hline(y=0, line=dict(color="#55606C", width=1))
    st.plotly_chart(ui.base_layout(fig, 300, unit="%"), width="stretch", config=ui.PLOT_CONFIG, key="sl_curve")
    rows = []
    for part in ("disc", "unseen", "all"):
        s = res[part]
        if s:
            rows.append({"Period": {"disc": "Discovery", "unseen": "Unseen", "all": "Whole period"}[part],
                         "Right direction %": s["hit"], "% / week": s["edge"], "t": s["t"], "Luck chance (p)": s["p"],
                         "Rank correlation": s["ic"], "Weeks": s["weeks"], "Calls": s["calls"]})
    st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
    others = league[league["key"] == k][["cls", "verdict"]].rename(columns={"cls": "Class", "verdict": "Verdict"})
    st.markdown("**Same ingredient in other classes:** " + " · ".join(f"{r['Class']}: {r['Verdict']}" for _, r in others.iterrows()))


def trade_rule_controls(prefix):
    r1, r2 = st.columns(2)
    entry = r1.radio("Enter at", list(backtest.ENTRIES), horizontal=True, key=f"{prefix}_entry")
    rule = r2.radio("Exit rule", list(backtest.TRADE_RULES), horizontal=True, key=f"{prefix}_rule")
    tp_mode, sl_mode, tp_fixed, sl_fixed = backtest.TP_MODES[0], backtest.SL_MODES[0], 3.0, 3.0
    if rule == "Take-profit + stop-loss":
        r3, r4, r5, r6 = st.columns([1.6, 0.7, 1.6, 0.7])
        tp_mode = r3.selectbox("Take-profit level", backtest.TP_MODES, key=f"{prefix}_tp_mode")
        tp_fixed = float(r4.number_input("Fixed TP %", 0.1, 50.0, 3.0, 0.5, key=f"{prefix}_tp_fixed",
                                         disabled=tp_mode != "Fixed %"))
        sl_mode = r5.selectbox("Stop-loss level", backtest.SL_MODES, key=f"{prefix}_sl_mode")
        sl_fixed = float(r6.number_input("Fixed SL %", 0.1, 50.0, 3.0, 0.5, key=f"{prefix}_sl_fixed",
                                         disabled=sl_mode != "Fixed %"))
    return entry, rule, tp_mode, sl_mode, tp_fixed, sl_fixed


ENGINES = {"ridge": "Combiner (ridge regression)", "ml": "Machine learning (gradient boosting)",
           "arena": "Arena: run both and compare"}


def lab_model_section():
    st.caption("The model combines every ingredient into one expected move per asset per week. It learns the "
               "weights walk-forward (only from weeks already finished), so every prediction is out of sample.")
    classes, start, end, unseen = period_controls("md")
    c1, c2, c3 = st.columns([1.4, 1.6, 2])
    engine = c1.selectbox("Model", list(ENGINES), format_func=ENGINES.get, key="md_engine",
                          help="Ridge: a weighted sum of ingredients (simple, explainable). Machine learning: hundreds "
                               "of small decision trees that can learn combinations. Arena: both, side by side.")
    if engine != "ridge" and not model.ml_available():
        st.warning("The machine-learning model needs the scikit-learn library. Close HF Macro and open it again with "
                   "'Open HF Macro.bat' (it installs it automatically), then come back.")
        engine = "ridge"
    shrink = c1.segmented_control("Caution (shrinkage)", list(model.SHRINK), default="Medium", key="md_shrink",
                                  help="How strongly weights are pulled towards zero. Heavy = only trust ingredients "
                                       "with lots of evidence.") or "Medium"
    key_mode = c2.radio("Ingredients", ["Focus ingredients (not parked)", "All ingredients", "Only discovery winners"],
                        key="md_keys",
                        help="Focus = everything except ingredients parked by the Signal Lab. 'Only discovery winners' "
                             "keeps ingredients with |t| ≥ 1.5 in the discovery period (the unseen period is never "
                             "looked at when choosing).")
    vol_target = c3.toggle("Volatility targeting", value=True, key="md_vt")
    costs = c3.toggle("Include trading costs", value=True, key="md_costs")
    ablation = c3.toggle("Test what each ingredient adds (slower)", value=True, key="md_abl")
    min_move = float(c2.number_input("Only trade if the expected move is at least (%)", 0.0, 5.0, 0.8, 0.1, key="md_min",
                                     help="+0.8% or more to buy, −0.8% or more to short. Smaller calls are skipped "
                                          "that week. 0 = take every call. The 'Minimum move' tab compares levels."))
    horizon = st.segmented_control("Hold each trade for", [1, 2, 4], default=1, key="md_h",
                                   format_func=lambda h: f"{h} week" + ("s" if h > 1 else ""),
                                   help="Longer holds: the model predicts the move over 2 or 4 weeks and trades less "
                                        "often. Slow ingredients (value, momentum) may work better, and weekly noise "
                                        "averages out.") or 1
    st.markdown("**Trade rules**" + (" (only 'hold' applies to 2- and 4-week trades)" if horizon > 1 else ""))
    entry, rule, tp_mode, sl_mode, tp_fixed, sl_fixed = trade_rule_controls("md")
    if not classes:
        return
    if st.button("▶ Build and test the model", key="md_run"):
        st.session_state["md_params"] = (tuple(classes), str(start), str(end), unseen, shrink, key_mode, vol_target,
                                         costs, entry, rule, tp_mode, sl_mode, tp_fixed, sl_fixed, ablation, engine,
                                         horizon, min_move)
    if "md_params" not in st.session_state:
        st.info("Choose your settings and press the button. Building the model takes a few minutes the first time.")
        return
    try:
        res = lab_model_run(*st.session_state["md_params"])
    except Exception as exc:
        st.error(f"The model failed ({type(exc).__name__}: {exc}).")
        with st.expander("Technical details"):
            st.exception(exc)
        return
    data_sources_panel(res.get("status", {}))
    cards = res["cards"]
    if cards.empty:
        st.warning("Not enough data to build the model in that period.")
        return
    cut = res["cut"]
    st.success(f"Model built. Discovery period up to {cut:%d %b %Y}, unseen after. "
               f"Ingredients used: " + "; ".join(f"{c}: {len(k)}" for c, k in res["keys"].items()))
    risk_focus(res)
    save_last("model", dict(cards=cards, params=st.session_state["md_params"], latest=res["latest"],
                            levels=res.get("levels", {}), names=res.get("names", {}), risk=res.get("risk", {}),
                            risk_flags=res.get("risk_flags", {}), curves=res["curves"], cut=cut,
                            settings=res.get("settings", {}), arena=res.get("arena")))
    if res.get("settings", {}).get("min_move"):
        st.caption(f"Minimum move: only calls expected to move at least {res['settings']['min_move']}% (up or down) "
                   "were traded. See the 'Minimum move' tab for other levels.")
    names = ["This week's calls", "Scorecard", "Risk checks", "Minimum move", "Prediction quality", "What it trusts",
             "Adds to model?", "Strategy race"] + (["Arena"] if "arena" in res else [])
    tabs = dict(zip(names, st.tabs(names)))
    with tabs["Risk checks"]:
        lab_risk_tab(res)
    with tabs["Minimum move"]:
        lab_threshold_tab(res.get("thresholds"), "md", res.get("settings", {}).get("min_move", 0))
    tabs = [tabs[n] for n in names if n not in ("Risk checks", "Minimum move")]
    with tabs[0]:
        lab_model_calls(res)
    with tabs[1]:
        show = cards.copy()
        cols = {"side": "Side", "cls": "Class", "verdict": "Verdict", "disc_week": "Discovery % / week",
                "unseen_week": "Unseen % / week", "unseen_vs_class": "Unseen vs holding class",
                "coin_week": "Coin toss % / week", "vs_coin_week": "Edge over coin", "unseen_vs_coin": "Unseen edge over coin",
                "win_rate": "Winning weeks %", "sharpe": "Sharpe", "max_dd": "Worst drop %", "weeks": "Weeks"}
        for k, v in {"hit_target": "Hit target %", "hit_stop": "Hit stop %", "to_friday": "Closed Friday %"}.items():
            if k in show:
                cols[k] = v
        smart_table(show[[c for c in cols if c in show]].rename(columns=cols).round(3), "md_cards")
        st.caption("All after costs (if switched on). 'Edge over coin' = same trades, same rules, but a coin chose "
                   "buy or sell: positive means the model's direction calls add something. The baseline row is a "
                   "plain 3-month momentum rule; a model that can't beat it isn't worth its complexity.")
        for side, desc in model.SIDES.items():
            st.markdown(f"- **{side}:** {desc}")
    with tabs[2]:
        q = res["quality"]
        if not q.empty:
            st.dataframe(q.rename(columns={"cls": "Class", "part": "Period", "hit": "Right direction %", "ic": "Rank correlation",
                                           "edge": "% / week (before costs)", "t": "t", "calls": "Calls"}).round(3),
                         hide_index=True, width="stretch")
        st.caption("How good the predictions themselves are, before any trading rules or costs. Right direction "
                   "above 50% beats a coin toss; the unseen rows are the honest ones.")
    with tabs[3]:
        W_ = res["weights"]
        w_opts = [c for c in W_ if not W_[c].empty]
        cls_pick = st.selectbox("Asset class", w_opts, key="md_w_cls") if w_opts else None
        if cls_pick not in w_opts:          # e.g. a class remembered from an earlier run that has no weights now
            cls_pick = w_opts[0] if w_opts else None
        if cls_pick:
            B = W_[cls_pick]
            last = B.iloc[-1].drop("(average drift)", errors="ignore").sort_values()
            labels = [signals.INGREDIENTS.get(k, (k,))[0] for k in last.index]
            fig = go.Figure(go.Bar(x=last.values, y=labels, orientation="h",
                                   marker_color=[ui.CYAN if v > 0 else "#FF6B6B" for v in last.values]))
            fig = ui.base_layout(fig, max(300, 22 * len(last)))
            fig.update_layout(xaxis_title="Weight (latest)")
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="md_wbar")
            st.caption("Blue = the model trusts it in its normal direction; red = it uses it backwards. Longer bar = "
                       "more weight. Weights are in 'normal weekly moves per unit of the ingredient's z-score'.")
            if len(B) > 3:
                top = B.drop(columns="(average drift)", errors="ignore").abs().iloc[-1].sort_values(ascending=False).head(6).index
                lab_line_chart({signals.INGREDIENTS.get(k, (k,))[0]: B[k] for k in top}, 300, "md_wlines", unit="", title="Weight")
                st.caption("How the six most important weights changed as the model learned week by week.")
            else:
                st.caption("Machine learning: bars show importance (how much worse the model gets when that ingredient "
                           "is scrambled), not direction.")
                t = res.get("learned", {}).get(cls_pick)
                if t is not None and not t.empty:
                    st.dataframe(t.rename(columns={"ingredient": "Ingredient", "markets": "Markets",
                                                   "when_low": "Predicted move when it's low", "when_high": "When it's high",
                                                   "difference": "Difference"}).round(3), hide_index=True, width="stretch")
    with tabs[4]:
        abl = res["ablation"]
        if isinstance(abl, pd.DataFrame) and not abl.empty:
            st.dataframe(abl[["ingredient", "cls", "adds", "disc_gain", "unseen_gain", "disc_hit_gain", "unseen_hit_gain"]]
                         .rename(columns={"ingredient": "Ingredient", "cls": "Class", "adds": "Verdict",
                                          "disc_gain": "Discovery gain (% / week)", "unseen_gain": "Unseen gain (% / week)",
                                          "disc_hit_gain": "Discovery gain (direction %)", "unseen_hit_gain": "Unseen gain (direction %)"})
                         .sort_values("Unseen gain (% / week)", ascending=False).round(4), hide_index=True, width="stretch")
            st.caption("Each ingredient is removed in turn and the whole model rebuilt. Gain = how much worse the "
                       "model got without it. ✅ = it helps in both periods. ❌ = the model is better without it "
                       "(it's adding noise: a candidate to switch off).")
        else:
            st.info("Switch on 'Test what each ingredient adds' and run again.")
    with tabs[5]:
        cls_pick = st.selectbox("Asset class", sorted({c for _, c in res["curves"]}), key="md_race_cls")
        curves = {s: ((1 + r / 100).cumprod() - 1) * 100 for (s, c), r in res["curves"].items() if c == cls_pick}
        lab_line_chart(curves, 380, "md_race", title="Cumulative return %")
        st.caption(f"After costs. The unseen period starts {cut:%d %b %Y}.")
    if "arena" in res:
        with tabs[6]:
            lab_arena(res)


def lab_model_calls(res):
    if not res["latest"]:
        st.info("No predictions for the latest week.")
        return
    lv = res.get("levels", {})
    for cls, (t, last) in res["latest"].items():
        with st.container(border=True):
            h = res.get("settings", {}).get("horizon", 1)
            ui.panel_title(f"{cls}", f"MADE ON {t:%d %b %Y} · FOR THE " + ("WEEK AFTER" if h == 1 else f"NEXT {h} WEEKS"))
            df = last.copy()
            df.insert(0, "Name", [res["names"].get(x, x) for x in df.index])
            df["Call"] = np.where(df["pred"] > 0, "▲ up", "▼ down")
            rows = []
            for tick, r in df.iterrows():
                up = r["pred"] > 0
                m = lv.get(tick)
                tp = sl = None
                if m:
                    tp = m.get("p75_none") if up else -m.get("p25_none", np.nan)
                    sl = -m.get("p5_none") if up else m.get("p95_none")
                rows.append({"Ticker": tick, "Name": r["Name"], "Call": r["Call"], "Risk": r.get("risk", ""),
                             "Expected move %": r["pred"],
                             "Normal weekly move %": r["normal"], "Confidence": abs(r["confidence"]),
                             "Take-profit (MC) %": tp, "Stop-loss (MC) %": sl, "Main drivers": r.get("drivers", ""),
                             "Risk flags": r.get("risk_why", "")})
            st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, width="stretch")
    stock_calls = [t for c, (_, last) in res["latest"].items() if c == "US stocks" for t in last.index[:10]]
    if stock_calls:
        with st.expander("Cross-check these stock prices with Tiingo"):
            if st.button("Check the top 10 US calls", key="md_tiingo"):
                uni, prices, _ = lab_prices(("US stocks",))
                chk, msg = companies.tiingo_check(stock_calls, prices.get("US stocks", pd.DataFrame()))
                if not chk.empty:
                    st.dataframe(chk.round(2), hide_index=True, width="stretch")
                st.caption(msg or "Typical gap = how different Yahoo's and Tiingo's weekly returns usually are (should be "
                                  "near 0). A big worst gap means one source has a glitch that week.")
    st.caption("Confidence = expected move ÷ normal weekly move. Even the strongest calls are small compared with "
               "normal noise; that's what real edges look like. Take-profit/stop-loss come from the Monte Carlo "
               "(75th percentile target, 5th percentile stop) for the top 5 calls. Practice account only.")


def risk_focus(res):
    """Adds Focus / Parked status to every risk check (per class and side)."""
    for cls, df in (res.get("risk") or {}).items():
        if df.empty:
            continue
        rows = []
        for _, r in df.iterrows():
            keep, why = focus.rule_risk(r["verdict"])
            rows.append(dict(name=f"{r['check']} ({r['side']})", cls=cls, keep=keep, reason=why))
        out = focus.sync("Risk check", rows, settings=res.get("settings"))
        df["status"] = [o["status"] for o in out]


def lab_risk_tab(res):
    st.caption("Should we take a trade even when the signal is good? Each check flags risky trades. It is tested "
               "by re-running the model's trades WITHOUT the flagged ones, on the discovery and unseen periods. "
               "Skipping trades always cuts losses, so a check only counts (✅) if return per unit of risk (Sharpe) "
               "improves in both periods. 🛡 = smaller losses but not better overall. Tested with hold-to-Friday.")
    rt = res.get("risk", {})
    if not rt:
        st.info("No risk tests for these settings.")
        return
    cls_list = [c for c in rt if not rt[c].empty]
    if not cls_list:
        st.info("No risk tests for these settings.")
        return
    for ct, cls in zip(st.tabs(cls_list), cls_list):
        with ct:
            df = rt[cls]
            proven = res.get("risk_flags", {}).get(cls, [])
            st.markdown(f"**Proven checks for {cls}:** " + (", ".join(f"★ {p}" for p in proven) if proven else
                        "none yet. The traffic lights still show every flag, but none have earned a 🔴 on their own."))
            for side in df["side"].unique():
                d = df[df["side"] == side]
                st.markdown(f"##### {side}")
                show = d[["status", "check", "level", "verdict", "trades_kept", "unseen_sharpe_before", "unseen_sharpe_after",
                          "unseen_win_before", "unseen_win_after", "unseen_worst_before", "unseen_worst_after",
                          "unseen_dd_before", "unseen_dd_after", "disc_sharpe_before", "disc_sharpe_after", "detail"]]
                smart_table(show.rename(columns={
                    "status": "Status", "check": "Check", "level": "Level", "verdict": "Verdict", "trades_kept": "Trades kept %",
                    "unseen_sharpe_before": "Unseen Sharpe before", "unseen_sharpe_after": "after",
                    "unseen_win_before": "Unseen win % before", "unseen_win_after": "after ",
                    "unseen_worst_before": "Unseen worst week before", "unseen_worst_after": "after  ",
                    "unseen_dd_before": "Unseen biggest drop before", "unseen_dd_after": "after   ",
                    "disc_sharpe_before": "Discovery Sharpe before", "disc_sharpe_after": "after    ",
                    "detail": "Combined checks"}).round(2), f"md_risk_{cls[:3]}_{side[-2:].strip()}")
    with st.expander("What each check means"):
        for name, (level, what, why) in risk.CHECKS.items():
            st.markdown(f"- **{name}** ({level}): {what} *Why it might help:* {why}")
    st.caption("Traffic lights in 'This week's calls': 🟢 no flags · 🟡 one or two flags (trade smaller) · 🔴 a "
               "★ proven check fired, or three or more flags (skip it).")


def lab_arena(res):
    df, winners = res["arena"]
    if df.empty:
        st.info("Not enough data for the arena.")
        return
    st.markdown("**Who wins on the unseen period?** " + " · ".join(f"{c}: **{w}**" for c, w in winners.items()))
    show = df.rename(columns={"cls": "Class", "model": "Model", "disc_hit": "Discovery right direction %",
                              "unseen_hit": "Unseen right direction %", "unseen_ic": "Unseen rank correlation",
                              "unseen_edge": "Unseen % / week (before costs)", "unseen_t": "Unseen t",
                              "every_call_unseen": "Every call, unseen % / week (after costs)",
                              "strongest3_unseen": "Strongest 3, unseen % / week", "unseen_vs_coin": "Unseen edge over coin"})
    st.dataframe(show.sort_values(["Class", "Model"]).round(3), hide_index=True, width="stretch")
    st.caption("Same ingredients, same weeks, same costs and trade rules. Only the unseen columns are a fair fight: "
               "the discovery period is where we were allowed to look. If the simple baseline wins, the extra "
               "complexity isn't paying for itself (yet).")
    learned = res.get("learned", {})
    if learned:
        st.markdown("#### What the machine-learning model learned")
        cls = st.selectbox("Asset class", list(learned), key="md_learn_cls")
        t = learned.get(cls)
        if t is not None and not t.empty:
            st.dataframe(t.rename(columns={"ingredient": "Ingredient", "markets": "Markets",
                                           "when_low": "Predicted move when it's low", "when_high": "When it's high",
                                           "difference": "Difference"}).round(3), hide_index=True, width="stretch")
            st.caption("Predicted next-week move (in 'normal weekly moves') when each top ingredient is low (bottom "
                       "20%) or high (top 20%), split by calm and fearful markets. If the difference flips sign "
                       "between calm and fearful, the model has found a combination the ridge model can't see.")
        imp = res.get("ml_weights", {}).get(cls)
        if imp is not None and not imp.empty:
            last = imp.iloc[-1].sort_values()
            fig = go.Figure(go.Bar(x=last.values, y=[signals.INGREDIENTS.get(k, (k,))[0] for k in last.index],
                                   orientation="h", marker_color=ui.CYAN))
            fig = ui.base_layout(fig, max(300, 22 * len(last)))
            fig.update_layout(xaxis_title="Importance (how much worse it gets when this is scrambled)")
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="md_ml_imp")


def page_assetlab():
    if PUBLIC:
        st.info("Asset Lab is only available in the PC version.")
        return
    st.markdown(look.page_header("Models · PC only", "Asset Lab",
                                 "Your commodities model and every test behind it. <b>My trades</b> turns this round's picks into "
                                 "Trading 212 demo tickets and explains how they were chosen; <b>Test</b> shows the backtests. "
                                 "Statistical tests built from past prices, just for fun on a practice account. Not financial advice."),
                unsafe_allow_html=True)
    q = st.query_params.get("s")
    main0, sub0 = LAB_ALIASES.get(q, (q, None)) if q else ("MY TRADES", None)
    if main0 not in LAB_MAIN:
        main0 = "MY TRADES"
    section = st.segmented_control("Asset Lab section", list(LAB_MAIN), default=main0, key="al_sec",
                                   label_visibility="collapsed") or main0
    st.caption(LAB_MAIN[section])
    sub = None
    if section in LAB_SUBS:
        opts = LAB_SUBS[section]
        d = sub0 if (sub0 in opts and section == main0) else (st.query_params.get("t") if st.query_params.get("t") in opts else opts[0])
        sub = st.segmented_control("Part", opts, default=d, key=f"al_sub_{section}", label_visibility="collapsed") or d
    if section == "MY TRADES":
        page_my_trades()
    elif section == "THIS WEEK":
        page_this_week()
    elif section == "WHAT'S WORKING":
        page_whats_working()
    elif section == "PARKED":
        page_parked()
    elif section == "TEST":
        {"Backtest": lambda: lab_backtest_section(st.session_state.get("al_cls") or assetlab.CLASSES),
         "Signal Lab": lab_signal_section, "Model": lab_model_section,
         "Commodities model": lab_cmodel_section, "Fresh test": lab_fresh_section,
         "Model + S&P 500": lab_mix_section, "Idea log": page_idea_log,
         "Commodities workshop": lab_workshop_section, "Pattern lab": lab_pattern_section}[sub]()
    elif section == "LEARN FROM MISSES":
        if sub == "Why we missed":
            lab_why_we_missed()
        else:
            classes = st.session_state.get("al_cls") or assetlab.CLASSES
            _, prices, _ = lab_prices(tuple(classes))
            lab_prediction_log(prices)
    else:
        lab_explore(sub)


def lab_explore(sub):
    c1, c2, c3 = st.columns([1.1, 1.1, 2.8])
    horizon = c1.segmented_control("Horizon", ["Next week", "Next month"], default="Next week", key="al_h") or "Next week"
    drift = c2.selectbox("Model's view", list(assetlab.DRIFTS), key="al_drift")
    classes = c3.multiselect("Asset classes", assetlab.CLASSES, default=assetlab.CLASSES, key="al_cls")
    st.caption(f"**{drift}:** {assetlab.DRIFTS[drift]}")
    if not classes:
        return
    if sub == "Strategies":
        uni, _, _ = lab_prices(tuple(classes))
        lab_strategies(classes, uni)
        return
    if not st.session_state.get("al_go"):
        st.button("▶ Run the simulations", key="al_start", on_click=lambda: st.session_state.update(al_go=True))
        st.caption("The first run downloads 10 years of prices for ~700 assets and checks the news, so it can take "
                   "a few minutes. Prices are then saved on your PC for 12 hours.")
        return
    with ui.loading("Running the asset lab", ["Downloading prices", "Running Monte Carlo simulations", "Checking news coverage", "Building the results"]):
        try:
            scan_df, att = lab_scan(tuple(classes), horizon, drift)
        except Exception as exc:
            st.error(f"Couldn't run the simulations ({type(exc).__name__}: {exc}).")
            with st.expander("Technical details (send a screenshot of this to fix it)"):
                st.exception(exc)
            return
    if scan_df.empty:
        st.warning("No price data came back. Yahoo Finance may be busy; try again in a few minutes.")
        return
    uni, prices, fixes = lab_prices(tuple(classes))
    wiki_n = int(att["views"].notna().sum())
    st.caption(f"{len(scan_df)} assets simulated · news and Wikipedia checked for the 15 biggest expected movers "
               f"in each class · Wikipedia views found for {wiki_n} of {len(att)}"
               + (f" (last problem: {assetlab.WIKI_STATUS['last_error']})" if assetlab.WIKI_STATUS["last_error"] else "")
               + (f" · {len(fixes)} price glitches cleaned" if fixes else ""))
    if fixes:
        with st.expander(f"Price glitches cleaned ({len(fixes)})"):
            st.dataframe(pd.DataFrame(fixes, columns=["Class", "Ticker", "Days fixed", "Problem"]),
                         hide_index=True, width="stretch")
    if sub == "Scanner":
        lab_scanner(scan_df, att, horizon, classes)
    elif sub == "Analysis":
        lab_analysis(scan_df, att, prices, horizon, drift)
    elif sub == "Contrarian":
        lab_contrarian(prices, uni, classes, drift)
    elif sub == "Risk simulator":
        lab_risk(scan_df, att, prices, uni, horizon)


# ---------------------------------------------------------------- v23: THIS WEEK, WHAT'S WORKING, PARKED

def _size(budget, n, light=""):
    if not n:
        return None
    s = budget / n
    return round(s / 2 if str(light).startswith("🟡") else 0 if str(light).startswith("🔴") else s, 0)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_workshop_run(start, end, unseen_from, entry, fin_long, cls="Commodities", skip=()):
    uni, prices, _ = lab_prices((cls,))
    ohlc = lab_ohlc((cls,), uni, prices).get(cls)
    proxies = None
    if cls == "Commodities":
        try:
            proxies = signals._disk_cache("etf_proxies", 12, lambda: assetlab.download_prices(tuple(workshop.ETF_PROXY.values())))
        except Exception:
            proxies = None
    _, rec = lab_extras()
    return workshop.run(prices[cls], ohlc, start, end, unseen_from, proxies=proxies, recession=rec,
                        entry=entry, fin_long=fin_long, progress=_progress_cb(), cls=cls, skip=tuple(skip))


def lab_workshop_section():
    st.info("👉 For the finished commodities model (only what worked, year by year), use **TEST → Commodities "
            "model**. This workshop is where new ideas get tested.")
    st.caption("Commodities is where the strategies did best, so this perfects them one at a time. It cleans the "
               "futures roll jumps, adds real CFD overnight fees, then tries every combination of exit rule, holding "
               "period, minimum move and an 'only trade it while it's working' switch. Each strategy's best settings "
               "are chosen on the DISCOVERY years only; the UNSEEN years then show the honest result.")
    today = pd.Timestamp.now().normalize()
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.3, 1.2])
    start = c1.date_input("From", value=pd.Timestamp("2017-01-06").date(), key="ws_start")
    unseen_from = c2.date_input("Unseen from", value=pd.Timestamp("2023-01-06").date(), key="ws_unseen",
                                help="Everything before this is discovery (where settings are chosen). After it is "
                                     "the unseen test.")
    end = c3.date_input("To", value=(today - pd.DateOffset(days=7)).date(), key="ws_end")
    entry = c4.radio("Enter at", list(backtest.ENTRIES), index=1, horizontal=True, key="ws_entry")
    fin = float(c5.number_input("Overnight fee on buys (% a week)", 0.0, 1.0, workshop.LONG_FINANCING_WEEK, 0.01,
                                key="ws_fin", help="Trading 212 CFDs charge overnight fees on buys as well as shorts. "
                                                   "0.10% a week is about 5% a year."))
    cls = st.selectbox("Sector", assetlab.CLASSES, index=assetlab.CLASSES.index("Commodities"), key="ws_cls",
                       help="Commodities first; the same workshop works for any sector.")
    parked_now = [s_ for s_ in workshop.PARKED_SIDES if focus.is_parked("Commodity strategy", s_, "Commodities")]
    with_parked = st.checkbox(f"Also test the {len(parked_now)} parked strategies", value=False, key="ws_parked",
                              help="They lost on the unseen years whatever the settings, so they're left out unless "
                                   "you want to re-check them.") if (cls == "Commodities" and parked_now) else True
    skip = () if with_parked else tuple(parked_now)
    problem = workshop.check_dates(start, unseen_from, end)
    if problem:
        st.error(problem)
    if st.button("▶ Run the workshop", key="ws_run", disabled=bool(problem)):
        st.session_state["ws_params"] = (str(start), str(end), str(unseen_from), entry, fin, cls, skip)
    if "ws_params" not in st.session_state:
        st.info("Press the button. It tests ~500 setting combinations over 8+ years, so the first run takes a few "
                "minutes. Results are saved for 6 hours.")
        return
    try:
        res = lab_workshop_run(*st.session_state["ws_params"])
    except Exception as exc:
        st.error(f"The workshop failed ({type(exc).__name__}: {exc}).")
        with st.expander("Technical details"):
            st.exception(exc)
        return
    if not res or res["best"].empty:
        st.warning("Not enough data. Try an earlier start date.")
        return
    best, port, uf = res["best"], res["portfolio"], res["unseen_from"]
    good = best[best["verdict"].str.startswith("✅")]
    st.success(f"{len(best)} strategies perfected. **{len(good)}** made money in BOTH the discovery and the unseen years "
               f"with their best settings. {len(res['fixes'])} futures roll jumps were removed first.")
    if port and port.get("unseen"):
        u = port["unseen"]
        st.markdown(f"**Combined portfolio on the unseen years:** {u['avg_week']:+.2f}% a week, {u['total']:+.1f}% in "
                    f"total, worst drop {u['max_dd']:.1f}%, winning weeks {u['win']:.0f}%.")
    save_last("workshop", dict(best=best, portfolio_unseen=(port or {}).get("unseen"), params=st.session_state["ws_params"]))
    tabs = st.tabs(["Which options really help", "Best settings (often luck)", "Portfolio", "Year by year", "By group",
                    "How long to trust it", "Roll-jump cleaning", "Every setting tried"])
    tabs = [tabs[1], tabs[0]] + list(tabs[2:])
    with tabs[1]:
        ef = res.get("effects")
        if ef is None or ef.empty:
            st.info("Not available for this run.")
        else:
            st.caption("The single 'best' combination for a strategy is often luck: the more combinations tried, the "
                       "more likely the winner is a fluke. The robust test is each option's AVERAGE effect across "
                       "every other setting and strategy (% per week vs the overall average). Trust options that "
                       "help in both discovery and unseen.")
            smart_table(ef.rename(columns={"option": "Option", "choice": "Choice", "disc_effect": "Discovery effect",
                                           "unseen_effect": "Unseen effect", "settings": "Settings averaged",
                                           "verdict": "Verdict"}).round(3), "ws_eff", totals=False)
    tabs = [tabs[0]] + list(tabs[2:])
    with tabs[0]:
        show = best.reindex(columns=["verdict", "side", "settings", "disc_avg", "unseen_avg", "default_unseen_avg",
                                     "unseen_sharpe", "unseen_total", "unseen_dd", "years_up", "years", "unseen_weeks"])
        smart_table(show.rename(columns={
            "verdict": "Verdict", "side": "Strategy", "settings": "Best settings (chosen on discovery)",
            "disc_avg": "Discovery % / week", "unseen_avg": "Unseen % / week",
            "default_unseen_avg": "Unseen with basic settings", "unseen_sharpe": "Unseen Sharpe",
            "unseen_total": "Unseen total %", "unseen_dd": "Unseen worst drop %", "years_up": "Years up",
            "years": "Years", "unseen_weeks": "Unseen weeks"}).round(3), "ws_best")
        st.warning("Careful: each strategy's 'best' settings are picked from hundreds of combinations, so many of them "
                   "are luck and fall apart on the unseen years. Trust the 'Which options really help' tab instead.")
        st.caption("'Unseen with basic settings' = the same strategy held one week with no extras. If the best "
                   "settings beat it on the UNSEEN years, the tuning genuinely helped; if not, it was fitting noise.")
    with tabs[1]:
        if not port:
            st.info("No strategy made money in the discovery years, so there's no portfolio to build.")
        else:
            curves = {"★ Combined (more money to calmer strategies)": ((1 + port["combo"] / 100).cumprod() - 1) * 100,
                      "Equal split": ((1 + port["equal"] / 100).cumprod() - 1) * 100,
                      "Just holding every commodity": ((1 + res["bench"].fillna(0) / 100).cumprod() - 1) * 100}
            lab_line_chart(curves, 380, "ws_port", title="Cumulative return % (after costs)")
            st.caption(f"Unseen years start {uf:%d %b %Y}. Only strategies that made money in discovery are included.")
            wts = port["weights"].sort_values(ascending=False)
            st.dataframe(pd.DataFrame({"Strategy": wts.index, "Share of money %": (wts.values * 100).round(1)}),
                         hide_index=True, width="stretch")
            corr = port["corr"]
            fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1,
                                       colorscale="RdBu"))
            st.plotly_chart(ui.base_layout(fig, 360), width="stretch", config=ui.PLOT_CONFIG, key="ws_corr")
            st.caption("How closely the strategies move together (1 = identical, 0 = unrelated, -1 = opposite). "
                       "Low or negative numbers are good: one can win while another loses, so the total is smoother.")
    with tabs[2]:
        yrs = pd.DataFrame({s: res["series"][("YEARS", s)] for s in best["side"] if ("YEARS", s) in res["series"]}).T
        yrs.columns = [str(c) for c in yrs.columns]
        st.dataframe(yrs.round(1), width="stretch")
        st.caption("Return each calendar year with the best settings, after costs. A real edge makes money in most "
                   "years, not one lucky one.")
    with tabs[3]:
        gcols = [c for c in best.columns if c.startswith("group_")]
        g = best[["side"] + gcols].rename(columns={"side": "Strategy", **{c: c[6:] + " % / week" for c in gcols}})
        smart_table(g.round(3), "ws_grp")
        st.caption("The same best settings run on each group of commodities on its own (whole period). Shows "
                   "whether a strategy works across commodities or only in one corner, e.g. only metals.")
    with tabs[4]:
        tc = ["trust_1 month", "trust_3 months", "trust_6 months", "trust_12 months", "trust_longest_underwater_weeks", "trust_max_dd"]
        t = best[["side"] + [c for c in tc if c in best]].rename(columns={
            "side": "Strategy", "trust_1 month": "Profitable 1-month spells %", "trust_3 months": "3-month spells %",
            "trust_6 months": "6-month spells %", "trust_12 months": "12-month spells %",
            "trust_longest_underwater_weeks": "Longest time below its best (weeks)", "trust_max_dd": "Worst drop %"})
        smart_table(t.round(1), "ws_trust")
        st.caption("If a strategy is in profit in, say, 85% of 6-month spells, a losing 2 months is normal and no "
                   "reason to panic; judge it after 6. 'Longest time below its best' is the longest wait for a new "
                   "high in the past: expect waits like that again.")
    with tabs[5]:
        fx = pd.DataFrame(res["fixes"], columns=["Commodity", "Day", "Raw move %", "Replaced with %", "How it was spotted"])
        if fx.empty:
            st.info("No roll jumps found.")
        else:
            smart_table(fx.round(2), "ws_fix")
        st.caption("A roll jump is the price stepping from one futures contract to the next, not a real gain or loss. "
                   "Left in, they create fake 'reversals' that strategies can wrongly learn from.")
    with tabs[6]:
        g = res["grid"].rename(columns={"side": "Strategy", "min_move": "Min move %", "hold_weeks": "Hold weeks",
                                        "skip_wild": "Skip wild commodities",
                                        "exit": "Exit rule", "only_while_working": "Only while working",
                                        "disc_avg": "Discovery % / week", "disc_sharpe": "Discovery Sharpe",
                                        "disc_weeks": "Discovery weeks", "unseen_avg": "Unseen % / week",
                                        "unseen_sharpe": "Unseen Sharpe", "unseen_weeks": "Unseen weeks",
                                        "unseen_total": "Unseen total %", "unseen_dd": "Unseen worst drop %",
                                        "unseen_win": "Unseen winning weeks %"})
        smart_table(g.round(3), "ws_grid", height=500)
        st.caption("Every combination tried. Don't pick the best-looking UNSEEN row by hand: that's choosing with "
                   "hindsight. The 'Best honest versions' tab picks on discovery only.")


# ---------------------------------------------------------------- v27: THE COMMODITIES MODEL

def _p(x, d=1):
    try:
        x = float(x)
        return f"{x:+.{d}f}%" if np.isfinite(x) else "–"
    except (TypeError, ValueError):
        return "–"


def _gbp(x):
    try:
        x = float(x)
        return f"£{x:,.0f}" if np.isfinite(x) else "–"
    except (TypeError, ValueError):
        return "–"


def md_table(df):
    """A simple table written like the ones in chat (easy to read, no scrolling)."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def park_commodity_strategies():
    """Puts the strategies that failed every commodity test on the PARKED shelf (saved, not deleted)."""
    rows = [dict(name=s, cls="Commodities", keep=False, reason=why) for s, why in workshop.PARKED_SIDES.items()]
    rows += [dict(name=s, cls="Commodities", keep=True, reason="in the commodities model") for s in workshop.MODEL_SIDES]
    try:
        focus.sync("Commodity strategy", rows, settings="hold 4 weeks, -8% weekly stop, skip wild (v27)")
    except Exception:
        pass


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_cmodel_run(fin_long, day, version="Improved"):
    uni, prices, _ = lab_prices(("Commodities",))
    ohlc = lab_ohlc(("Commodities",), uni, prices).get("Commodities")
    try:
        proxies = signals._disk_cache("etf_proxies", 12, lambda: assetlab.download_prices(tuple(workshop.ETF_PROXY.values())))
    except Exception:
        proxies = None
    try:
        ctx, _ = lab_context(("Commodities",))
    except Exception:
        ctx = None
    weather, notes = None, []
    try:
        weather, errs = pattern_lab.load_weather(pd.Timestamp(workshop.MODEL_START) - pd.DateOffset(years=6),
                                                 pd.Timestamp.now().normalize(), progress=_progress_cb())
        notes += [f"Weather not loaded for {e}" for e in errs]
    except Exception as exc:
        notes.append(f"Weather not loaded ({type(exc).__name__})")
    res = workshop.final_model(prices["Commodities"], ohlc, proxies, fin_long=fin_long, progress=_progress_cb(),
                               ctx=ctx, weather=weather, **workshop.VERSIONS.get(version, {}))
    if res:
        res["names"] = {t: name_of(t, uni) for t in prices["Commodities"].columns}
        res["notes"] = notes
        res["version"] = version
    return res


def current_version():
    v = setting_get("model_version", "Improved")
    return v if v in workshop.VERSIONS else "Improved"


def version_picker(key):
    """Choose the model version (remembered). Returns the chosen name."""
    saved = current_version()
    v = st.segmented_control("Model version", list(workshop.VERSIONS), default=saved, key=key) or saved
    if v != saved:
        setting_set("model_version", v)
    st.caption(f"**{v}:** {workshop.VERSION_HELP[v]}")
    return v


SETTINGS = focus.PATH.parent / "settings.json"


def setting_get(key, default=None):
    try:
        return json.loads(SETTINGS.read_text()).get(key, default)
    except Exception:
        return default


def setting_set(key, value):
    try:
        d = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
    except Exception:
        d = {}
    d[key] = value
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(d))
    except Exception:
        pass


def filter_toggle(key, filt):
    """The on/off switch for the personality filter (remembered between sessions)."""
    saved = bool(setting_get("personality_filter", False))
    on = st.toggle("Use the commodity personality filter for my picks", value=saved, key=key,
                   disabled=filt is None or "error" in (filt or {}),
                   help="Skips picks whose OWN past patterns pointed to weaker-than-normal weeks.")
    if bool(on) != saved:
        setting_set("personality_filter", bool(on))
    return bool(on) and filt is not None and "error" not in filt


def filter_verdict(filt):
    h = filt["honest"]
    d = h["with_"] - h["without"]
    if d > 2:
        return "✅", f"it helped: {_p(h['with_'])} a year with it vs {_p(h['without'])} without"
    if d < -2:
        return "❌", f"it didn't help: {_p(h['with_'])} a year with it vs {_p(h['without'])} without"
    return "➖", f"it made little difference: {_p(h['with_'])} a year with it vs {_p(h['without'])} without"


def lab_cmodel_section():
    st.markdown("#### 🛢️ The commodities model")
    st.markdown("Everything we tested on commodities, boiled down to **only what worked**. There are no settings to "
                "choose and no dates to type in, so it can't be tuned to look good by accident. It shows what the model "
                "would have made **every year since 2017**, split into three kinds of years:")
    st.markdown("- **Practice years (2017–2022):** the years our first tests learned from. The model's final "
                "rules were checked on these AND the unseen years.\n"
                "- **Unseen years (2023 → 23 Oct 2026):** the years used to check the tests. ⚠️ We chose which "
                "strategies to keep by looking at these, so they flatter the model a bit.\n"
                f"- **Live (after {pd.Timestamp(workshop.LIVE_FROM):%d %b %Y}):** the model was fixed on that day. Every "
                "week after it is a completely fresh test that nobody could have tuned for. **This is the number to "
                "trust most** once it has a few months in it.")
    c1, c2, c3 = st.columns([1, 1, 2])
    budget = float(c1.number_input("Practice money (£)", 100.0, 1_000_000.0, 1000.0, 100.0, key="cm_budget"))
    fin = float(c2.number_input("Overnight fee on buys (% a week)", 0.0, 1.0, workshop.LONG_FINANCING_WEEK, 0.01,
                                key="cm_fin", help="Trading 212 charges an overnight fee to hold a commodity CFD. "
                                                   "0.10% a week is about 5% a year."))
    go_ = c3.button("▶ Run the commodities model", key="cm_run", type="primary")
    version_picker("cm_version")
    if go_:
        st.session_state["cm_go"] = True
    if not st.session_state.get("cm_go"):
        st.info("Press the button. It takes about 3 minutes the first time (it replays every week since 2017 and "
                "looks for each commodity's own patterns). Results are saved for 6 hours.")
        return
    park_commodity_strategies()
    try:
        with ui.loading("Walking forward through history", scene="model", once="model"):
            res = lab_cmodel_run(fin, pd.Timestamp.now().strftime("%Y-%m-%d"), current_version())
            if res and "decision" not in res:          # a result saved by an older version: work it out again once
                lab_cmodel_run.clear()
                res = lab_cmodel_run(fin, pd.Timestamp.now().strftime("%Y-%m-%d"), current_version())
    except Exception as exc:
        st.error(f"The model failed ({type(exc).__name__}: {exc}).")
        with st.expander("Technical details"):
            st.exception(exc)
        return
    if not res:
        st.warning("Not enough commodity prices came back. Try again in a few minutes.")
        return
    k = budget / res["budget"]
    names = res.get("names", {})
    nm = lambda t: f"{names.get(t, t)}"
    P = res["periods"].set_index("Period")
    Y = res["years"]
    save_last("cmodel", dict(periods=res["periods"], years=Y, holding=res["holding"], names=names, version=res.get("version"),
                             picked_on=res["picked_on"], next_change=res["next_change"], last_friday=res["last_friday"]))

    # ---- the answer in one line
    if "Unseen" in P.index and "Practice" in P.index:
        u, pr, w = P.loc["Unseen"], P.loc["Practice"], P.loc["Whole history"]
        st.success(f"**In one line:** on the unseen years the model made **{_p(u['Model % a year'])} a year** "
                   f"({_gbp(budget)} → {_gbp(u['£ grows to'] * k)}), against {_p(u.get('Buy everything on CFDs % a year'))} "
                   f"for buying every commodity on the same CFD account. On the practice years it made "
                   f"{_p(pr['Model % a year'])} a year (buying everything on CFDs: "
                   f"{_p(pr.get('Buy everything on CFDs % a year'))}). Over the whole {len(Y)} years: "
                   f"**{_p(w['Model % a year'])} a year**, {_gbp(budget)} → {_gbp(w['£ grows to'] * k)}. "
                   f"The fresh test (TEST → Fresh test) shows what to expect on years it never saw: much less.")

    swd = res.get("switch") or {}
    if swd:
        st.markdown(f"🔁 **6-month switch:** the model is {_p(swd.get('last6'))} over its last 6 months, so its money "
                    + ("should be **in the S&P 500** right now." if swd.get("now") else "stays in the model."))
    pz = res.get("pause") or {}
    if pz.get("n"):
        st.markdown(("⏸ **The model is PAUSED right now** (3 losing weeks in a row); it restarts after a winning week."
                     if pz.get("paused") else
                     f"▶️ **The model is trading.** Losing weeks in a row: {pz.get('streak', 0)} (it pauses at {pz['n']})."))

    # ---- 1. what's in it
    st.markdown("### 1. What's in the model")
    st.markdown("\n".join(f"{i}. **{a}.** {b}" for i, (a, b) in enumerate(workshop.MODEL_RULES, 1)))
    st.markdown(f"**The {len(workshop.MODEL_SIDES)} strategies:** " + " · ".join(workshop.MODEL_SIDES) + ". (Momentum 12-1 and "
                "Trust-weighted momentum almost always pick the same commodities, so momentum is really about half the money.)")
    with st.expander("What we tested and cut out, so nothing is missed"):
        st.markdown(md_table(pd.DataFrame(workshop.CUT, columns=["Cut", "Why"])))
        st.markdown("**Parked strategies** (saved on the PARKED page, not deleted):")
        st.markdown(md_table(pd.DataFrame(list(workshop.PARKED_SIDES.items()), columns=["Strategy", "Why it was parked"])))

    # ---- 2. by period
    st.markdown("### 2. The answer, period by period")
    rows = []
    for name, r in P.iterrows():
        rows.append({"Period": f"**{name}**", "Dates": f"{r['From']:%b %Y} → {r['To']:%b %Y}",
                     "Model a year": f"**{_p(r['Model % a year'])}**", f"{_gbp(budget)} grows to": _gbp(r["£ grows to"] * k),
                     "Worst drop": _p(r["Worst drop %"]), "Before overnight fees": _p(r.get("Model before overnight fees % a year")),
                     "Buy everything on CFDs (same fees)": _p(r.get("Buy everything on CFDs % a year")),
                     "Buy everything, no fees": _p(r["Buy everything % a year"]), "Full years up": r["Full years up"]})
    st.markdown(md_table(pd.DataFrame(rows)))
    st.caption("'A year' = the average yearly growth over that period (compounded, after costs). 'Worst drop' = the "
               "biggest fall from a high point to a low point. 'Buy everything on CFDs' = the same money split across "
               "every commodity and held on the same account, paying the same overnight fee: the fair thing to beat. "
               "'No fees' = the same but held without an overnight fee (e.g. through ETFs).")
    with st.expander("How the Improved version was chosen (testing a higher minimum expected move)"):
        st.markdown("Your idea: only buy when the Monte Carlo expects a bigger move. Tested on all three data sets, % a "
                    "year after fees (worst drop):")
        st.markdown(md_table(pd.DataFrame(workshop.MIN_MOVE_TEST, columns=[
            "Minimum expected move", "2017–26 (built on)", "2001–16 (fresh)", "New commodities (fresh)",
            "Time invested (2017–26)"])))
        st.markdown("- A **small** minimum (0.2%) helped on all three: it skips the weakest picks.\n"
                    "- A **big** minimum (0.8% and up) hurt: the model sits in cash most of the time and misses big "
                    "moves, because the expected move is only a rough guide, not a promise.\n"
                    "- Adding the 12-month trend rule on top gave the best balance, so that's the **Improved** version.\n"
                    "- Honest caveat: it was chosen after looking at all three data sets, so the live weeks are its "
                    "real test.")
    if "Live" not in P.index:
        st.info(f"**Live:** nothing yet. The first fresh week is the one after {pd.Timestamp(workshop.LIVE_FROM):%d %b %Y}. "
                "Come back and rerun each weekend: this line will start filling in.")

    # ---- 3. year by year
    st.markdown("### 3. Year by year")
    st.markdown("This is the best way to gauge what returns are really like: good years, bad years, and how often it "
                "beats just buying everything.")
    yrows = []
    for _, r in Y.iterrows():
        yrows.append({"Year": f"**{r['Year']}**", "Kind": r["Period"], "Model": f"**{_p(r['Model %'])}**",
                      "Buy everything": _p(r["Buy everything %"]),
                      "Beat it by": _p(r["Model minus buy everything"]),
                      "Worst drop in year": _p(r["Worst drop in the year %"]),
                      "Winning weeks": f"{r['Winning weeks %']:.0f}%",
                      f"{_gbp(budget)} from 2017 →": _gbp(r["£ grows to"] * k),
                      "Buy everything →": _gbp(r["Buy everything £ grows to"] * k)})
    st.markdown(md_table(pd.DataFrame(yrows)))
    st.markdown("**What happened each year:**")
    st.markdown("\n".join("- " + workshop.year_sentence(r) for _, r in Y.iterrows()))
    full = Y[~Y["Year"].str.contains("so far")]
    if len(full):
        m = full["Model %"]
        beat = int((full["Model minus buy everything"] > 0).sum())
        st.markdown(f"**A typical year** (the {len(full)} full years): the middle year made **{_p(m.median())}**. "
                    f"Best year {_p(m.max())} ({full.loc[m.idxmax(), 'Year']}), worst {_p(m.min())} "
                    f"({full.loc[m.idxmin(), 'Year']}). It made money in **{int((m > 0).sum())} of {len(full)}** years "
                    f"and beat buying everything in **{beat} of {len(full)}**. So expect some flat or losing years even "
                    "if it works: judge it over 2–3 years, not 2–3 months.")
    curves = {"★ The model": (1 + res["weekly"] / 100).cumprod() * budget,
              "Buy every commodity": (1 + res["bench"] / 100).cumprod() * budget}
    fig = go.Figure()
    for (n, s), c in zip(curves.items(), [ui.CYAN, "#8A94A6"]):
        fig.add_scatter(x=s.index, y=s.values, mode="lines", name=n, line=dict(width=2 if "★" in n else 1.4, color=c))
    for d, label in ((workshop.UNSEEN_FROM, "unseen →"), (workshop.LIVE_FROM, "live →")):
        fig.add_vline(x=pd.Timestamp(d), line=dict(color="#FFD166", dash="dot"))
        fig.add_annotation(x=pd.Timestamp(d), y=1, yref="paper", text=label, showarrow=False, xanchor="left",
                           font=dict(color="#FFD166"))
    fig = ui.base_layout(fig, 380, unit="", legend=True)
    fig.update_layout(yaxis_title=f"{_gbp(budget)} grows to (£)")
    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key="cm_curve")
    try:
        import streamlit.components.v1 as components
        st.markdown("**🏁 Race replay:** the same two lines, drawn week by week (press REPLAY to watch again).")
        components.html(fx.race({"★ The model": res["weekly"], "Buy every commodity": res["bench"]}, colours=[ui.ACCENT, "#8A96A3"],
                                start_money=budget, title=f"{_gbp(budget)} RACE"), height=440)
    except Exception:
        pass

    # ---- 4. personalities
    personality_section(res, names)

    # ---- 4. each strategy
    st.markdown(f"### 5. Each of the {len(workshop.MODEL_SIDES)} strategies")
    S = res["strategies"]
    st.markdown(md_table(pd.DataFrame([{"Strategy": f"**{r['Strategy']}**", "Practice a year": _p(r["Practice % a year"]),
                                        "Unseen a year": _p(r["Unseen % a year"]),
                                        "Live": _p(r["Live % a year"]), "Worst drop": _p(r["Worst drop %"])}
                                       for _, r in S.iterrows()])))
    yy = pd.DataFrame({"Year": Y["Year"]})
    for s in workshop.MODEL_SIDES:
        yy[s] = [_p(v) for v in Y[s]]
    with st.expander("Each strategy year by year"):
        st.markdown(md_table(yy))
    st.caption("Notice how they take turns: when one has a bad year another often has a good one. That's why the "
               "model splits the money four ways instead of betting on the 'best' one.")

    # ---- 5. which commodities
    st.markdown("### 6. Which commodities made the money")
    C = res["by_commodity"]
    top = C.head(5)
    bottom = C.tail(3)
    st.markdown("Each number is how much that commodity added to (or took off) the model's return that year, in "
                "percentage points, before costs.")
    show = C.copy()
    show.index = [nm(t) for t in show.index]
    show = show.map(lambda v: _p(v) if abs(v) >= 0.05 else "·")
    show.insert(0, "Commodity", [f"**{i}**" for i in show.index])
    st.markdown(md_table(show))
    st.markdown(f"- **Biggest helpers:** " + ", ".join(f"{nm(t)} ({_p(v)})" for t, v in top["All years"].items()) + ".\n"
                f"- **Biggest drags:** " + ", ".join(f"{nm(t)} ({_p(v)})" for t, v in bottom["All years"].items()) + ".")
    wo = res.get("without")
    if wo is not None and not wo["table"].empty:
        t = wo["table"]
        wcol = f"Without {wo['ticker']} % a year"
        st.markdown(f"**Luck check: what if we'd never traded {nm(wo['ticker'])} (the biggest helper)?**")
        st.markdown(md_table(pd.DataFrame([{"Period": r["Period"], "With everything": _p(r["With everything % a year"]),
                                            f"Without {nm(wo['ticker'])}": "**" + _p(r[wcol]) + "**",
                                            "Buy everything": _p(r["Buy everything % a year"])} for _, r in t.iterrows()])))
        ur = t[t["Period"] == "Unseen"]
        if len(ur):
            ur = ur.iloc[0]
            wv = ur[f"Without {wo['ticker']} % a year"]
            st.markdown(("Without it the model **still beats** buying everything on the unseen years, so it isn't one "
                         "lucky trade. But a big part of the unseen result came from that one commodity, so the real "
                         "everyday edge is closer to the 'without' number."
                         if wv > ur["Buy everything % a year"] else
                         "Without it the model **no longer beats** buying everything on the unseen years: much of the "
                         "result was one lucky commodity. Treat the headline number with care."))

    # ---- 6. holding now
    st.markdown("### 7. What it holds right now")
    H = res["holding"]
    if H.empty:
        st.info("The model holds nothing right now (every strategy is sitting out).")
    else:
        hrows = [{"Commodity": f"**{nm(r['Ticker'])}**", "Ticker": r["Ticker"], "Action": "BUY",
                  "Share": f"{r['Share of the money %']:.0f}%", f"Of {_gbp(budget)}": _gbp(r["£"] * k),
                  "Chosen by": r["Held by"]} for _, r in H.iterrows()]
        st.markdown(md_table(pd.DataFrame(hrows)))
        st.markdown(f"- These were picked on **{res['picked_on']:%a %d %b %Y}** (with prices up to "
                    f"{res['last_friday']:%d %b}).\n"
                    f"- The next re-pick is after the close on **{res['next_change']:%a %d %b %Y}**. Until then, keep "
                    "holding, unless one of them closes a Friday down 8% from when it was bought: then sell it.\n"
                    "- On the practice account: buy at Friday's close (or as close as you can on Monday), split as "
                    "above. Log it in LEARN FROM MISSES → Prediction log so the live record builds up.")

    # ---- 7. honest warnings
    st.markdown("### 8. Honest warnings")
    uns = _p(P.loc["Unseen", "Model % a year"]) if "Unseen" in P.index else "unseen"
    warn = ["**The unseen years flatter it.** We kept the strategies that did well on them, so some of that "
            f"{uns} a year is hindsight. The practice years and the live weeks are the fairer guide."]
    if "Practice" in P.index and P.loc["Practice", "Model % a year"] < P.loc["Practice", "Buy everything % a year"]:
        warn.append(f"**On the practice years it trailed simply buying everything** "
                    f"({_p(P.loc['Practice', 'Model % a year'])} vs {_p(P.loc['Practice', 'Buy everything % a year'])} a "
                    "year). Most of its edge came from 2024–2025, when commodities trended strongly. Momentum strategies "
                    "do best in trending years and struggle in choppy ones like 2018–2020.")
    warn.append("**Losing stretches are normal.** The worst drop over the whole history was "
                f"{_p(P.loc['Whole history', 'Worst drop %'])}. If you can't sit through that on the practice account, "
                "you won't on a real one.")
    warn.append("**A sensible expectation** is somewhere between the practice and unseen numbers, not the best one. "
                "The live weeks will tell us where.")
    st.markdown("\n".join(f"- {w}" for w in warn))
    curve_section(names)
    try:
        stats_section("### 10. Stats check: skill or luck?", res, workshop.UNSEEN_FROM, "cm_stats")
    except Exception as exc:
        st.warning(f"The stats check couldn't run ({type(exc).__name__}: {exc}).")
    st.caption("Just for fun and learning with a practice account. Past results don't guarantee future ones. "
               "Not financial advice.")


# ---------------------------------------------------------------- v28: MY TRADES (the model's picks as trade tickets)

MY_TRADES = focus.PATH.parent / "my_trades.csv"
SAFETY_STOP = -15.0
TRADE_COLS = ["id", "ticker", "name", "opened", "cycle_start", "sell_on", "ref_price", "buy_price", "amount",
              "status", "closed", "sell_ref_price"]


def trades_load():
    try:
        df = pd.read_csv(MY_TRADES)
        for c in ("opened", "cycle_start", "sell_on", "closed"):
            df[c] = pd.to_datetime(df[c], errors="coerce")
        return df.reindex(columns=TRADE_COLS)
    except Exception:
        return pd.DataFrame(columns=TRADE_COLS)


def trades_save(df):
    MY_TRADES.parent.mkdir(parents=True, exist_ok=True)
    df.reindex(columns=TRADE_COLS).to_csv(MY_TRADES, index=False)


def _px(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "–"
    if not np.isfinite(x):
        return "–"
    return f"{x:,.4f}" if x < 10 else f"{x:,.2f}"


def page_my_trades():
    st.markdown("#### 📋 My trades")
    st.markdown("The **commodities model's** picks written out as trade tickets you can copy onto your Trading 212 "
                "**demo** account: what to buy, how much, where the stop-loss goes, and the date to sell. Then press "
                "*I've placed these* and this page tracks them for you.")
    c1, c2, c3 = st.columns([1, 1, 2])
    budget = float(c1.number_input("Demo money to use (£)", 100.0, 1_000_000.0, 1000.0, 100.0, key="mt_budget"))
    fin = float(st.session_state.get("cm_fin", workshop.LONG_FINANCING_WEEK))
    pressed = c2.button("▶ Get the latest picks", key="mt_run", type="primary")
    if pressed:
        st.session_state["cm_go"] = True
    version_picker("mt_version")
    labels = {1.0: "All in the model", 0.5: "50% model / 50% S&P 500", 0.3: "30% model / 70% S&P 500"}
    saved_share = model_share()
    share = st.segmented_control("How to split the money", list(labels), default=saved_share,
                                 format_func=labels.get, key="mt_share") or saved_share
    if share != saved_share:
        setting_set("model_share", share)
    model_money = budget * share
    sw_on = st.toggle("6-month switch: when the model has lost money over its last 6 months, put its money in the "
                      "S&P 500 too", value=switch_on_setting(), key="mt_switch")
    if sw_on != switch_on_setting():
        setting_set("six_month_switch", bool(sw_on))
    if share < 1:
        st.caption(f"**{_gbp(budget * (1 - share))} in an S&P 500 fund** (e.g. an S&P 500 ETF, bought normally, not "
                   f"as a CFD, so no overnight fee): buy it once and hold. **{_gbp(model_money)} for the model's "
                   "trades below.** At each re-pick, if the split has drifted by more than 10 points, move money to "
                   "put it back. TEST → Model + S&P 500 shows why: similar returns to the S&P with smaller falls.")
    c3.caption("Takes about a minute the first time (it replays the model since 2017 to know where the 4-week cycle "
               "is). Rerun it every weekend.")
    if not st.session_state.get("cm_go"):
        st.info("Press **▶ Get the latest picks**.")
        _my_trades_tracker(None, budget)
        return
    try:
        with ui.loading("Walking forward through history", scene="model", once="model", force=pressed):
            res = lab_cmodel_run(fin, pd.Timestamp.now().strftime("%Y-%m-%d"), current_version())
            if res and "decision" not in res:          # a result saved by an older version: work it out again once
                lab_cmodel_run.clear()
                res = lab_cmodel_run(fin, pd.Timestamp.now().strftime("%Y-%m-%d"), current_version())
    except Exception as exc:
        st.error(f"Couldn't run the model ({type(exc).__name__}: {exc}).")
        with st.expander("Technical details"):
            st.exception(exc)
        _my_trades_tracker(None, budget)
        return
    if not res:
        st.warning("Not enough commodity prices came back. Try again in a few minutes.")
        return
    names = res.get("names", {})
    H = res["holding"].copy()
    filt = res.get("filter")
    swd = res.get("switch") or {}
    if switch_active(res):
        st.warning(f"🔁 **6-MONTH SWITCH IS ON.** The model has lost {_p(swd.get('last6'))} over its last 6 months, so "
                   f"**its money ({_gbp(model_money)}) goes into the S&P 500 too: sell the model's holdings at Friday's "
                   "close and buy more of your S&P fund.** No model trades until its last 6 months (followed on paper) "
                   "turn positive again; this page will tell you.")
        st.info("No tickets while the switch is on. The tracker below shows what to sell.")
        model_explainer(res, empty=True, why=f"<b>The 6-month switch is on.</b> Over its last 6 months the model lost {_p(swd.get('last6'))}, "
                        "so its money sits in the S&P 500 instead (you turned this rule on above, to stop long losing runs). The model keeps "
                        "picking on paper (below) and trading restarts by itself when its last 6 months turn positive.")
        _my_trades_tracker(res, budget)
        return
    elif swd and switch_on_setting():
        st.caption(f"6-month switch: the model is {_p(swd.get('last6'))} over its last 6 months, so it trades as normal "
                   "(the switch moves its money into the S&P only if that goes negative).")
    pz = res.get("pause") or {}
    if pz.get("n"):
        rec = " · ".join(_p(v) for v in pz.get("recent", []))
        if pz.get("paused"):
            st.warning(f"⏸ **MODEL PAUSED.** It has lost {pz['n']} weeks in a row (last weeks: {rec}). **Sell the model's "
                     "holdings at Friday's close and don't buy new ones.** Keep running this page each weekend: it "
                     "restarts by itself after the model's first winning week (it's still followed on paper). The S&P "
                     "half stays as it is.")
        elif pz.get("streak", 0) == pz["n"] - 1:
            st.warning(f"⚠️ The model has lost {pz['streak']} weeks in a row ({rec}). One more losing week and it "
                       "pauses.")
        else:
            st.caption(f"Pause rule: after {pz['n']} losing weeks in a row the model pauses. Losing weeks in a row "
                       f"right now: {pz.get('streak', 0)}.")
    skipped = pd.DataFrame()
    if filter_toggle("mt_filter", filt):
        Hf = filt["holding"]
        skipped = H[~H["Ticker"].isin(Hf["Ticker"])]
        H = H[H["Ticker"].isin(Hf["Ticker"])].drop(columns=["Share of the money %", "£"]).merge(Hf, on="Ticker")
        H = H.sort_values("Share of the money %", ascending=False).reset_index(drop=True)
        icon, txt = filter_verdict(filt)
        st.caption(f"Personality filter ON. On the honest years {txt.replace('**', '')}. Turn it off to follow the "
                   "model exactly as tested.")
    today = pd.Timestamp.now().normalize()
    sell_on = pd.Timestamp(res["next_change"])
    days_left = max(0, (sell_on - today).days)
    weeks_left = max(1, int(np.ceil(days_left / 7)))

    # ---- 1. this round at a glance
    st.markdown("### 1. This round at a glance")
    st.markdown(md_table(pd.DataFrame([{
        "Round started": f"{res['picked_on']:%a %d %b %Y}", "Sell date (end of round)": f"**{sell_on:%a %d %b %Y}**",
        "Days left": f"{days_left}", "Commodities to buy": f"{len(H)}", "Money for the model": _gbp(model_money)}])))
    if pz.get("paused"):
        st.info("No tickets while the model is paused. The tracker below shows what to sell.")
        model_explainer(res, empty=True, why=f"<b>The model is paused</b> after {pz.get('n')} losing weeks in a row. It keeps picking on paper "
                        "(below) and restarts by itself after its first winning week.")
        _my_trades_tracker(res, budget)
        return
    if H.empty:
        st.info("The model holds nothing this round: every strategy is sitting out. Nothing to buy; check again after "
                f"the close on {sell_on:%a %d %b}. Below: exactly why.")
        model_explainer(res, empty=True)
        _my_trades_tracker(res, budget)
        return
    if days_left <= 7:
        st.warning(f"⏳ **This round ends in {days_left} days** (on {sell_on:%a %d %b}). You can either:\n"
                   f"1. **Wait** (simplest): rerun this page after the close on {sell_on:%a %d %b} and buy the NEW "
                   "picks for a full 4-week round, or\n"
                   f"2. **Join now** with the tickets below and sell on {sell_on:%a %d %b}. You'll only hold for "
                   f"{days_left} days, which is mostly paying the spread.\n\nThe model would wait.")

    # ---- 2. the tickets
    st.markdown("### 2. Your trade tickets")
    st.caption("Exactly what to type into Trading 212's order screen. Everything else is in 'Why these settings?' "
               "below.")
    rows = []
    for i, r in H.iterrows():
        t, p = r["Ticker"], r["Price"]
        nm_ = names.get(t, t)
        amt = r["Share of the money %"] / 100 * model_money
        stop, safety = p * 0.92, p * (1 + SAFETY_STOP / 100)
        rows.append({"Commodity": f"**{nm_}**", "Buy (value)": f"**{_gbp(amt)}**", "Stop loss": _px(safety),
                     "Take profit": "leave empty", "Sell on": f"{sell_on:%a %d %b}",
                     "Friday check: sell if below": _px(stop)})
        with st.container(border=True):
            st.markdown(f"##### {nm_}")
            st.markdown(md_table(pd.DataFrame([
                {"Trading 212 setting": "Order", "Enter": "**Buy**, market order"},
                {"Trading 212 setting": "Value", "Enter": f"**{_gbp(amt)}**"},
                {"Trading 212 setting": "Stop loss", "Enter": f"**{_px(safety)}**"},
                {"Trading 212 setting": "Take profit", "Enter": "leave empty"}])))
            st.markdown(f"📅 **Sell on {sell_on:%a %d %b}** · 🔴 **Sell early** if a Friday close is below "
                        f"**{_px(stop)}**")
            with st.expander("Bought at a different price?"):
                fill = st.number_input(f"Your buy price for {nm_}", 0.0, 1e9, 0.0, key=f"mt_fill_{t}")
                if fill:
                    st.markdown(f"Stop loss: **{_px(fill * (1 + SAFETY_STOP / 100))}** · Friday check: sell if below "
                                f"**{_px(fill * 0.92)}**")
    with st.expander("Why these settings?"):
        st.markdown(
            "- **Stop loss (−15%)** is a safety net for a crash. The model's real exit is the **Friday check**: sell if "
            "a Friday close is 8% or more below your buy price. A stop that fires at any time of day sold on normal "
            "wobbles and did worse in our tests.\n"
            "- **No take profit:** take-profits sold winners too early in every test. The few big winners make most of "
            "the money.\n"
            "- **Sell date:** the end of the 4-week round. Keep it instead if the next round picks it again"
            + (", or if it lost money but the model still expects it to rise (keep it one more week)" if res.get("reassess") else "")
            + ". The tracker below tells you which.\n"
            "- Prices are Yahoo's latest futures closes; Trading 212's CFD price can differ a little, so use "
            "'Bought at a different price?' to recalculate from your own price.\n"
            "- Picked by: " + "; ".join(f"{names.get(r_['Ticker'], r_['Ticker'])}: {r_['Held by']}" for _, r_ in H.iterrows()) + ".")
    if not skipped.empty:
        sc = filt["personality"]["scores"]
        st.markdown("**⛔ Skipped by the personality filter:** " + "; ".join(
            f"**{names.get(t, t)}** (its own patterns scored {_p(sc.at[pd.Timestamp(res['picked_on']), t] if t in sc and pd.Timestamp(res['picked_on']) in sc.index else np.nan, 2)} "
            "when this round was picked: weaker weeks than normal usually followed)" for t in skipped["Ticker"]) + ".")
    st.markdown("**All tickets in one table:**")
    st.markdown(md_table(pd.DataFrame(rows)))

    # ---- 3. how to place them
    st.markdown("### 3. Steps")
    st.markdown(
        "1. Trading 212 → **Practice** account → **CFD**. Search each commodity and enter its settings above.\n"
        "2. **Every Friday about 6pm UK time:** sell anything below its Friday-check price (the tracker marks it 🔴).\n"
        f"3. **{sell_on:%a %d %b}:** rerun this page after the close; the tracker says what to sell, keep or buy.\n"
        "4. Press **📌 I've placed these trades** so the page can track them.")
    if st.button("📌 I've placed these trades", key="mt_place"):
        T = trades_load()
        open_ = T[T["status"] == "open"]
        new = []
        for _, r in H.iterrows():
            if ((open_["ticker"] == r["Ticker"]) & (pd.to_datetime(open_["cycle_start"]) == pd.Timestamp(res["picked_on"]))).any():
                continue
            fill = float(st.session_state.get(f"mt_fill_{r['Ticker']}", 0.0) or 0.0)
            new.append(dict(id=f"{r['Ticker']}|{today:%Y%m%d}|{len(T) + len(new)}", ticker=r["Ticker"],
                            name=names.get(r["Ticker"], r["Ticker"]), opened=today, cycle_start=res["picked_on"],
                            sell_on=sell_on, ref_price=r["Price"], buy_price=fill or r["Price"],
                            amount=r["Share of the money %"] / 100 * model_money, status="open", closed=pd.NaT,
                            sell_ref_price=np.nan))
        if new:
            trades_save(pd.concat([T, pd.DataFrame(new)], ignore_index=True))
            st.success(f"Saved {len(new)} trades. They're tracked below.")
        else:
            st.info("These are already saved.")
    model_explainer(res)
    _my_trades_tracker(res, budget)
    st.caption("Just for fun and learning on a demo account. Not financial advice.")


def _light_p(p):
    return "🟢" if p == p and p < 0.05 else ("🟠" if p == p and p < 0.2 else "🔴")


def model_explainer(res, empty=False, why=None):
    """v42: how the model decided this round, in plain English, and the statistics behind it."""
    names = res.get("names", {})
    dec = res.get("decision")
    rd = res.get("round_day")
    st.markdown("### " + ("Why there are no trades this round" if empty else "How the model decided this round"))
    if dec is None or dec.empty:
        st.caption("Press ▶ Get the latest picks again to see how the model decided.")
        return
    d = dec.copy()
    d["Name"] = [names.get(t, t) for t in d["Ticker"]]
    wanted = d[d["Wanted by"] != ""]
    bought = d[d["Bought by"] != ""]
    jumpy = wanted[~wanted["Calm enough"]]
    stopped = wanted[wanted["Calm enough"] & (wanted["Bought by"] == "")]
    top = d.sort_values("12-1 momentum %", ascending=False).head(3)
    top_txt = ", ".join(f"{n} ({v:+.0f}%)" for n, v in zip(top["Name"], top["12-1 momentum %"]) if v == v)
    steps = [
        ("Read every commodity", f"On <b>{pd.Timestamp(rd):%a %d %b %Y}</b> (the start of this 4-week round) the model measured all "
         f"{len(d)} commodities: 12-month momentum (skipping the latest month), how close each is to its 52-week high, its "
         "12-month trend, a Monte Carlo simulation of next week, and how jumpy it is compared with normal."),
        ("Four strategies pick their top 20%", "Momentum 12-1, Trust-weighted momentum, 52-week high and Averages agree + momentum each "
         "pick the strongest few. " + (f"This round they wanted: <b>{', '.join(sorted(set(wanted['Name'])))}</b>." if len(wanted)
                                      else "This round <b>none of them wanted anything</b>: nothing passed its strategy's test. "
                                           f"The strongest by momentum were {top_txt}.")),
        ("Safety filters", "A pick is skipped when the commodity is more than 1.5x as jumpy as normal (big swings wipe out the edge), "
         "and any holding that falls 8% during the round is sold. "
         + (f"Skipped for being too jumpy: <b>{', '.join(f'{n} ({v:.1f}x normal)' for n, v in zip(jumpy['Name'], jumpy['Volatility vs normal']))}</b>. "
            if len(jumpy) else "Nothing was too jumpy. ")
         + (f"Bought, then sold during the round by the 8% stop-loss: <b>{', '.join(stopped['Name'])}</b>." if len(stopped) else "")),
        ("Result", (f"On paper the model holds <b>{', '.join(bought['Name'])}</b>." + (" (Not traded: see the first point.)" if why else "") if len(bought) else
                    ("<b>The model holds nothing.</b> Everything it bought this round has already been sold by the 8% stop-loss, so it "
                     "sits in cash until the next round." if len(stopped) else
                     "<b>The model holds nothing.</b> No commodity passed every test this round, so it sits in cash until the next round."))
         + f" Next decision: <b>{pd.Timestamp(res['next_change']):%a %d %b}</b>."),
    ]
    if why:
        steps.insert(0, ("Why there are no trades right now", why))
    st.markdown("".join(f"<div class='hf-step'><span class='n'>0{i + 1}</span><div><b>{t}</b><p>{x}</p></div></div>"
                        for i, (t, x) in enumerate(steps)), unsafe_allow_html=True)

    def f(v, fmt="{:+.1f}%"):
        return "–" if v != v else fmt.format(v)

    tbl = d.assign(_b=d["Bought by"] != "", _w=d["Wanted by"] != "").sort_values(["_b", "_w", "12-1 momentum %"], ascending=False)
    rows = [{"": "🟢 bought" if r["_b"] else ("🟠 wanted, then skipped" if r["_w"] else "⚪ not picked"), "Commodity": r["Name"],
             "12-1 momentum": f(r["12-1 momentum %"]), "Price vs 52-week high": f(r["Distance from 52-week high %"] * 100, "{:.0f}% of the high"),
             "12-month trend": f(r["12-month trend %"]), "Monte Carlo next week": f(r["Monte Carlo expected move %"], "{:+.2f}%"),
             "Jumpiness vs normal": f(r["Volatility vs normal"], "{:.2f}x"), "Wanted by": r["Wanted by"] or "–"}
            for _, r in tbl.iterrows()]
    with st.expander(f"Every commodity's readings on {pd.Timestamp(rd):%d %b %Y}", expanded=empty):
        st.markdown(md_table(pd.DataFrame(rows)))
    # ---- the statistics
    ex = workshop.explain(res)
    st.markdown("### The evidence behind the model")
    st.caption("Worked out from the model's own history since 2017, round by round. A **p-value** is the chance of a result this good "
               "by pure luck if the signal were useless: under 0.05 🟢 is strong evidence, 0.05-0.2 🟠 is a hint, above 0.2 🔴 could "
               "easily be luck. **Rank correlation** runs from -1 to +1: above 0 means higher readings were followed by better 4-week returns.")
    sg = ex.get("signals")
    if sg is not None and not sg.empty:
        st.markdown("**1. Does each reading predict the next 4 weeks?**")
        st.markdown(md_table(pd.DataFrame([{"": _light_p(r["p-value"]), "Reading": r["Signal"], "Rounds tested": int(r["Rounds"]),
                                            "Average rank correlation": f"{r['Average rank correlation with the next 4 weeks']:+.3f}",
                                            "Pointed the right way": f"{r['Rounds it pointed the right way %']:.0f}% of rounds",
                                            "t": f"{r['t']:.2f}", "p-value": f"{r['p-value']:.3f}"} for _, r in sg.iterrows()])))
    pk = ex.get("picks")
    if pk:
        st.markdown(f"**2. Did the picks beat the rest?** Picked commodities went on to make **{pk['picked']:+.2f}%** over the next 4 weeks "
                    f"on average ({pk['n_picked']} picks, up {pk['hit']:.0f}% of the time) against **{pk['rest']:+.2f}%** for the ones it "
                    f"didn't pick ({pk['n_rest']}, up {pk['hit_rest']:.0f}% of the time). Difference **{pk['diff']:+.2f} points**, "
                    f"t = {pk['t']:.2f}, p = {pk['p']:.3f} {_light_p(pk['p'])}.")
    pr = ex.get("periods")
    if pr is not None and not pr.empty:
        st.markdown("**3. Is the model's own return real?** Practice = the years it was built on; Unseen = years it never saw while "
                    "being built; Live = since it went live.")
        st.markdown(md_table(pd.DataFrame([{"Period": r["Period"], "Weeks": int(r["Weeks"]), "Model a year": f"{r['Model % a year']:+.1f}%",
                                            "Buy everything a year": f"{r['Buy everything % a year']:+.1f}%",
                                            "Winning weeks": f(r["Winning weeks %"], "{:.0f}%"),
                                            "p (above zero)": f"{_light_p(r['p-value (model above zero)'])} {f(r['p-value (model above zero)'], '{:.3f}')}",
                                            "p (beats buy everything)": f"{_light_p(r['p-value (model above buy everything)'])} {f(r['p-value (model above buy everything)'], '{:.3f}')}"}
                                           for _, r in pr.iterrows()])))
    st.caption("Information from past prices only. Not financial advice.")


def _my_trades_tracker(res, budget):
    T = trades_load()
    st.markdown("### 4. My open trades")
    if T.empty:
        st.caption("Nothing saved yet. After placing the trades, press 📌 I've placed these trades.")
        return
    try:
        _, prices, _ = lab_prices(("Commodities",))
        P = prices["Commodities"]
    except Exception:
        P = pd.DataFrame()
    today = pd.Timestamp.now().normalize()
    picks = set(res["holding"]["Ticker"]) if res is not None and not res["holding"].empty else None
    new_round = res is not None and pd.Timestamp(res["picked_on"]) > pd.to_datetime(T["cycle_start"]).max()
    rows = []
    for _, r in T[T["status"] == "open"].iterrows():
        s = P[r["ticker"]].dropna() if r["ticker"] in P else pd.Series(dtype=float)
        now = float(s.iloc[-1]) if len(s) else np.nan
        chg = (now / r["ref_price"] - 1) * 100 if now == now else np.nan
        fr = s[s.index > pd.Timestamp(r["opened"])].resample("W-FRI").last().dropna()
        fr = fr[fr.index <= s.index.max()] if len(s) else fr
        stopped = bool(len(fr)) and bool(((fr / r["ref_price"] - 1) * 100 <= -8).any())
        sig = res.get("now_signals") if res is not None else None
        still_up = (sig is not None and r["ticker"] in sig.index and bool(sig.at[r["ticker"], "trend_up"])
                    and float(sig.at[r["ticker"], "expected"]) >= max(0.2, float(res.get("min_move") or 0)))
        if res is not None and switch_active(res):
            status = "🔁 SELL at Friday's close: the 6-month switch is on (this money goes into the S&P)"
        elif res is not None and (res.get("pause") or {}).get("paused"):
            status = "⏸ SELL at Friday's close: the model is paused (3 losing weeks in a row)"
        elif new_round and picks is not None:
            if r["ticker"] in picks:
                status = "🔁 Picked again: KEEP"
            elif res.get("reassess") and chg == chg and chg < 0 and still_up:
                status = (f"⏳ KEEP 1 more week (reassessed: it lost, but the model still expects it to rise). Sell "
                          f"near the close on {pd.Timestamp(res['picked_on']) + pd.Timedelta(days=7):%a %d %b}")
            else:
                status = "⏰ SELL: not in the new round"
        elif today >= pd.Timestamp(r["sell_on"]):
            status = "⏰ SELL: the round is over (rerun the model first: keep it if it's picked again)"
        elif stopped:
            status = "🔴 SELL: a Friday close was 8%+ below your buy price"
        elif chg == chg and chg <= -8:
            status = "🟡 Below the −8% level: sell if it's still there at Friday's close"
        else:
            status = "✅ Hold"
        rows.append({"Commodity": f"**{r['name']}**", "Bought": f"{pd.Timestamp(r['opened']):%d %b}",
                     "Amount": _gbp(r["amount"]), "Your buy price": _px(r["buy_price"]),
                     "Change": _p(chg), "Profit / loss": _gbp(r["amount"] * chg / 100) if chg == chg else "–",
                     "Sell if Friday close below": _px(r["buy_price"] * 0.92), "Sell on": f"{pd.Timestamp(r['sell_on']):%a %d %b}",
                     "What to do": f"**{status}**", "_pl": r["amount"] * chg / 100 if chg == chg else 0.0})
    if rows:
        D = pd.DataFrame(rows)
        st.markdown(md_table(D.drop(columns="_pl")))
        st.markdown(f"**Open profit / loss: {_gbp(D['_pl'].sum())}** on {_gbp(T[T['status'] == 'open']['amount'].sum())} "
                    "(from the futures price moves, before fees; your Trading 212 figure will be close but not identical).")
        if new_round and picks is not None:
            held = set(T[T["status"] == "open"]["ticker"])
            buy_new = [t for t in picks if t not in held]
            if buy_new:
                nm_ = (res.get("names") or {})
                st.markdown("**New round: also BUY** " + ", ".join(f"**{nm_.get(t, t)}**" for t in buy_new) +
                            " (tickets above).")
        labels = {r["id"]: f"{r['name']} (bought {pd.Timestamp(r['opened']):%d %b})" for _, r in T[T["status"] == "open"].iterrows()}
        c1, c2 = st.columns([3, 1])
        pick = c1.selectbox("Sold one? Mark it here", list(labels), format_func=labels.get, key="mt_sold_pick")
        if c2.button("✔ Mark as sold", key="mt_sold") and pick:
            i = T.index[T["id"] == pick][0]
            t = T.at[i, "ticker"]
            s = P[t].dropna() if t in P else pd.Series(dtype=float)
            T.at[i, "status"], T.at[i, "closed"] = "closed", today
            T.at[i, "sell_ref_price"] = float(s.iloc[-1]) if len(s) else np.nan
            trades_save(T)
            st.success(f"Marked as sold: {labels[pick]}.")
            st.rerun()
    else:
        st.caption("No open trades.")
    C = T[T["status"] == "closed"]
    if not C.empty:
        st.markdown("### 5. Closed trades (your live record)")
        pl = (C["sell_ref_price"] / C["ref_price"] - 1) * 100
        st.markdown(md_table(pd.DataFrame({"Commodity": C["name"], "Bought": pd.to_datetime(C["opened"]).dt.strftime("%d %b %Y"),
                                           "Sold": pd.to_datetime(C["closed"]).dt.strftime("%d %b %Y"),
                                           "Amount": [_gbp(a) for a in C["amount"]], "Result": [_p(x) for x in pl],
                                           "Profit / loss": [_gbp(a * x / 100) for a, x in zip(C["amount"], pl)]})))
        tot = float((C["amount"] * pl / 100).sum())
        st.markdown(f"**Total: {_gbp(tot)}** from {len(C)} trades, {int((pl > 0).sum())} winners. "
                    "This is the truest test of the model there is.")


def personality_section(res, names):
    filt = res.get("filter")
    nm = lambda t: names.get(t, t)
    st.markdown("### 4. Each commodity's personality (new)")
    st.markdown("Like rock-paper-scissors: what wins depends on who you're playing. Each commodity has its own "
                "\"players\" (hedge funds, producers, the dollar, the season, the weather where it's grown), so this "
                "looks for patterns in **each commodity on its own**, using every week since 2017. Patterns are found "
                "in 2017–21, must repeat in 2022–23, pass a luck check, and are then judged on **2024 onwards**, "
                "which the search never saw. The **filter** skips a pick when its own patterns point to weaker weeks.")
    if filt is None:
        st.info("Not available for this run.")
        return
    if "error" in filt:
        st.warning(f"The personality test couldn't run this time ({filt['error']}). The rest of the model is fine.")
        return
    icon, txt = filter_verdict(filt)
    h = filt["honest"]
    st.markdown(f"**{icon} On the honest years (2024 →), {txt}.** Worst drop {_p(h['dd_with'])} with it vs "
                f"{_p(h['dd_without'])} without.")
    Y = filt["years"]
    st.markdown(md_table(pd.DataFrame([{"Year": f"**{r['Year']}**", "What the year was used for": r["Kind"],
                                        "Without filter": _p(r["Without filter %"]), "With filter": _p(r["With filter %"]),
                                        "Difference": f"**{_p(r['Difference'])}**" if r["Kind"] == "honest test" else _p(r["Difference"])}
                                       for _, r in Y.iterrows()])))
    st.caption("Only the 'honest test' years count: the earlier years were used to find the patterns, so of course "
               "the filter looks great there. That gap is exactly why we test on unseen years.")
    filter_toggle("cm_filter", filt)
    st.caption("Off = the model exactly as tested. On = MY TRADES skips the flagged picks and splits the money over "
               "the rest. The live weeks will show which is better; you can change it any time.")
    with st.expander("Each commodity's patterns (open to explore)"):
        P = filt["personality"]
        sm = P["summary"].copy()
        sm["Commodity"] = [f"**{nm(t)}**" for t in sm["Commodity"]]
        sm["Held %"] = [f"{v:.0f}%" if v == v else "–" for v in sm["Held %"]]
        st.markdown(md_table(sm))
        st.caption("'More than luck?' compares how many patterns each commodity had with how many pure luck makes. "
                   "'Held %' = of the patterns that passed, how many still pointed the same way from 2024. A coin "
                   "toss would give about 50%, so well above 50% is the sign of a real personality.")
        opts = [t for t in P["summary"]["Commodity"]]
        if opts:
            pick = st.selectbox("Commodity", opts, format_func=nm, key="cm_pers_pick")
            Pa, luck = P["results"][pick]
            sel = Pa[Pa["beats_luck"]].copy()
            good = sel[sel["edge_find"] > 0].sort_values("edge_confirm", ascending=False).head(8)
            bad = sel[sel["edge_find"] < 0].sort_values("edge_confirm").head(8)
            fmt = lambda r: (f"- {pattern_lab._short(r)}: {_p(r['edge_find'], 2)} then {_p(r['edge_confirm'], 2)} a week "
                             f"vs normal; since 2024: {_p(r['edge_final'], 2)} {r['held_final'][:1]}")
            st.markdown(f"**{nm(pick)} did BETTER than normal after:**\n" + ("\n".join(fmt(r) for _, r in good.iterrows()) or "- nothing reliable"))
            st.markdown(f"**{nm(pick)} did WORSE than normal after:**\n" + ("\n".join(fmt(r) for _, r in bad.iterrows()) or "- nothing reliable"))
            now = P["now"].get(pick, {})
            if now:
                st.markdown(f"**Right now:** score {_p(now.get('score'), 2)}. Switched on: "
                            + (", ".join(x["text"] for x in now.get("good", [])[:3]) or "no good signs")
                            + " | warnings: " + (", ".join(x["text"] for x in now.get("bad", [])[:3]) or "none") + ".")
            st.caption("✅ = the pattern kept pointing the same way from 2024, ❌ = it flipped. Numbers are % per "
                       "week compared with that commodity's normal week.")


# ---------------------------------------------------------------- v30: FRESH TEST (data the model has never seen)

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def lab_fresh_run(which, fin_long, day, version="Improved"):
    if which == "old":
        uni, _, _ = lab_prices(("Commodities",))
        tick = tuple(t for t, _, _ in uni.get("Commodities", []))
        names = {t: n for t, n, _ in uni.get("Commodities", [])}
        period, cfg = "max", workshop.FRESH_OLD
        etf = tuple(workshop.ETF_PROXY.values())
    else:
        tick, names, period, cfg = tuple(workshop.NEW_COMMODITIES), dict(workshop.NEW_COMMODITIES), "10y", workshop.FRESH_NEW
        etf = ()
    try:
        raw_ohlc = signals._disk_cache(f"fresh_{which}_ohlc", 24 * 7, lambda: assetlab.download_ohlc(tick, period=period))
        raw = raw_ohlc["close"]
    except Exception:
        raw_ohlc = None
        raw = signals._disk_cache(f"fresh_{which}_prices", 24 * 7, lambda: assetlab.download_prices(tick, period=period))
    prices, _ = assetlab.clean_prices(raw, "Commodities")          # same glitch cleaning as everywhere else
    try:
        ohlc = assetlab.clean_ohlc(raw_ohlc, prices) if raw_ohlc is not None else None
    except Exception:
        ohlc = None
    proxies = None
    if etf:
        try:
            proxies = signals._disk_cache("fresh_old_etf", 24 * 7, lambda: assetlab.download_prices(etf, period="max"))
        except Exception:
            proxies = None
    res = workshop.final_model(prices, ohlc, proxies, fin_long=fin_long, progress=_progress_cb(), use_personality=False,
                               start=cfg["start"], end=cfg.get("end"), fresh_label=cfg["label"],
                               **workshop.VERSIONS.get(version, {}))
    if res:
        res["names"] = names
        res["tickers_found"] = [t for t in tick if t in prices.columns and prices[t].notna().sum() > 250]
        res["first_dates"] = {t: prices[t].first_valid_index() for t in res["tickers_found"]}
    return res


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_fresh_sector_run(cls, fin_long, day, version="Improved"):
    """The commodity model's rules, unchanged, on another sector (fresh for this model)."""
    uni, prices, _ = lab_prices((cls,))
    if cls not in prices:
        return None
    ohlc = lab_ohlc((cls,), uni, prices).get(cls)
    res = workshop.final_model(prices[cls], ohlc, None, fin_long=fin_long, progress=_progress_cb(), use_personality=False,
                               start=workshop.MODEL_START, fresh_label=f"Fresh: {cls}", cls=cls,
                               **workshop.VERSIONS.get(version, {}))
    if res:
        res["names"] = {t: n for t, n, _ in uni.get(cls, [])}
        res["tickers_found"] = [t for t in prices[cls].columns if prices[cls][t].notna().sum() > 250]
        res["first_dates"] = {t: prices[cls][t].first_valid_index() for t in res["tickers_found"]}
    return res


def _fresh_block(title, intro, res, budget, key):
    st.markdown(f"### {title}")
    st.markdown(intro)
    if not res:
        st.warning("Not enough prices came back for this test. Try again later (Yahoo Finance may be busy).")
        return None
    sm = workshop.fresh_summary(res)
    names = res.get("names", {})
    found = res.get("tickers_found", [])
    firsts = res.get("first_dates", {})
    st.caption(f"{len(found)} commodities with prices: " + ", ".join(
        f"{names.get(t, t)} (from {pd.Timestamp(firsts[t]):%Y})" for t in found if t in firsts) + ".")
    good, beat = sm["model_year"] > 0, sm["model_year"] > sm["cfd_year"]
    line = (f"**{_p(sm['model_year'])} a year** after fees from {sm['start']:%b %Y} to {sm['end']:%b %Y} "
            f"({_gbp(budget)} → {_gbp(budget * (1 + sm['model_total'] / 100))}). Worst drop {_p(sm['model_dd'])}. "
            f"Made money in {sm['years_up']} of {sm['years']} full years.")
    (st.success if good and beat else st.warning)(
        ("✅ It worked on data it had never seen: " if good and beat else
         "🟡 It made money, but no more than buying everything on the same account: " if good else
         "❌ It lost money on data it had never seen: ") + line)
    st.markdown(md_table(pd.DataFrame([
        {"": "**The model**", "% a year": f"**{_p(sm['model_year'])}**", "Worst drop": _p(sm["model_dd"])},
        {"": "The model before the overnight fee", "% a year": _p(sm["before_fees_year"]), "Worst drop": "–"},
        {"": "Buy everything on CFDs (same fee: the fair comparison)", "% a year": _p(sm["cfd_year"]),
         "Worst drop": _p(sm["cfd_dd"])},
        {"": "Buy everything with no overnight fee (e.g. ETFs)", "% a year": _p(sm["bench_year"]),
         "Worst drop": _p(sm["bench_dd"])}])))
    Y = res["years"]
    st.markdown(md_table(pd.DataFrame([{
        "Year": f"**{r['Year'][:4]}**", "Model": f"**{_p(r['Model %'])}**", "Buy everything": _p(r["Buy everything %"]),
        "Beat it by": _p(r["Model minus buy everything"]), "Worst drop in year": _p(r["Worst drop in the year %"]),
        f"{_gbp(budget)} grows to": _gbp(r["£ grows to"] * budget / res["budget"]),
        "Buy everything →": _gbp(r["Buy everything £ grows to"] * budget / res["budget"])} for _, r in Y.iterrows()])))
    with st.expander("What happened each year, and which commodities made the money"):
        st.markdown("\n".join("- " + workshop.year_sentence(r) for _, r in Y.iterrows()))
        C = res["by_commodity"]["All years"]
        st.markdown("**Biggest helpers:** " + ", ".join(f"{names.get(t, t)} ({_p(v)})" for t, v in C.head(5).items()) +
                    ".  \n**Biggest drags:** " + ", ".join(f"{names.get(t, t)} ({_p(v)})" for t, v in C.tail(3).items()) + ".")
        wo = res.get("without")
        if wo is not None and not wo["table"].empty:
            r = wo["table"].iloc[0]
            st.markdown(f"**Luck check:** without its best commodity ({names.get(wo['ticker'], wo['ticker'])}), "
                        f"{_p(r.iloc[2])} a year (with it: {_p(r.iloc[1])}).")
    fig = go.Figure()
    fig.add_scatter(x=res["weekly"].index, y=(1 + res["weekly"] / 100).cumprod() * budget, mode="lines",
                    name="★ The model", line=dict(width=2, color=ui.CYAN))
    fig.add_scatter(x=res["bench"].index, y=(1 + res["bench"] / 100).cumprod() * budget, mode="lines",
                    name="Buy every commodity", line=dict(width=1.4, color="#8A96A3"))
    fig = ui.base_layout(fig, 320, unit="", legend=True)
    fig.update_layout(yaxis_title=f"{_gbp(budget)} grows to (£)")
    st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG, key=f"ft_{key}")
    with st.expander("📐 Stats check for this fresh test: skill or luck?"):
        try:
            stats_section("", res, workshop.UNSEEN_FROM, f"ft_stats_{key}", fresh=True)
        except Exception as exc:
            st.warning(f"The stats check couldn't run ({type(exc).__name__}: {exc}).")
    return sm


def lab_fresh_section():
    st.markdown("#### 🧪 Fresh test: data the model has never seen")
    st.markdown("Every rule in the commodities model (the 4 strategies, hold 4 weeks, the −8% Friday stop, skip wild "
                "commodities) was chosen using **2016–2026**. So the fairest test is data that played no part in "
                "choosing them. This runs the model **exactly as it is**, nothing to set, on:\n"
                "1. **The old years, 2001–2016**, on our 17 commodities: the 2008 crash, the 2011 commodity peak and "
                "the 2014–15 oil collapse.\n"
                "2. **9 commodities it has never traded** (palladium, oats, orange juice, lean hogs, feeder cattle, "
                "soybean oil, soybean meal, Kansas wheat, rough rice), 2017–2026.")
    c1, c2 = st.columns([1, 3])
    budget = float(c1.number_input("Money (£)", 100.0, 1_000_000.0, 1000.0, 100.0, key="ft_budget"))
    if c2.button("▶ Run both fresh tests", key="ft_run", type="primary"):
        st.session_state["ft_go"] = True
    if not st.session_state.get("ft_go"):
        st.info("Press the button. The first run downloads 25 years of prices, so allow about 5 minutes. "
                "Prices are then saved for a week.")
        return
    version = version_picker("ft_version")
    fin = float(st.session_state.get("cm_fin", workshop.LONG_FINANCING_WEEK))
    out = {}
    for which, title, intro in (
            ("old", "1. The old years (2001–2016)", "Same 17 commodities, years the model never saw. Most prices "
             "go back to 2000; the first year is used to warm up the 12-month signals."),
            ("new", "2. Commodities it has never traded (2017–2026)", "Same years as before, different markets. With "
             "only 9 commodities each strategy picks just 1–2 at a time, so expect bigger swings.")):
        try:
            res = lab_fresh_run(which, fin, pd.Timestamp.now().strftime("%Y-%m-%d"), version)
        except Exception as exc:
            st.markdown(f"### {title}")
            st.error(f"This test couldn't run ({type(exc).__name__}: {exc}).")
            with st.expander("Technical details"):
                st.exception(exc)
            continue
        sm = _fresh_block(title, intro, res, budget, which)
        if sm:
            out[which] = sm
    if out:
        save_last("fresh", dict(summary=out, version=version))
        st.markdown("### What it means")
        ok = {k: v["model_year"] > 0 for k, v in out.items()}
        beat = {k: v["model_year"] > v["cfd_year"] for k, v in out.items()}
        if len(out) == 2 and all(ok.values()) and all(beat.values()):
            msg = ("✅ **Strong evidence the edge is real.** It made money and beat buying everything on years AND "
                   "markets it had never seen. Keep following it on the practice account.")
        elif all(ok.values()):
            msg = ("🟡 **It makes money on fresh data, but not reliably more than buying everything on the same "
                   "account.** The trend-"
                   "following idea works; the extra edge from 2023–26 may have been partly a good spell.")
        elif any(ok.values()):
            msg = ("🟡 **Mixed.** It worked on one fresh test and not the other. Treat the 2023–26 results as the "
                   "optimistic end and keep the practice account small until the live weeks build up.")
        else:
            msg = ("❌ **It failed on fresh data.** The good 2023–26 results were most likely a lucky spell for "
                   "momentum. Good to find out now, on a practice account.")
        st.markdown(msg)
        last = load_last().get("cmodel")
        if last is not None:
            P = last["periods"].set_index("Period")
            if "Whole history" in P.index:
                st.caption(f"For comparison, the years used to build it (2017–2026): "
                           f"{_p(P.loc['Whole history', 'Model % a year'])} a year vs "
                           f"{_p(P.loc['Whole history', 'Buy everything % a year'])} for buying everything.")
    st.markdown("### 3. Other sectors")
    st.markdown("The same rules, unchanged, on a different kind of market. Commodities trend because supply and demand "
                "take time to adjust; other markets may not, so this shows whether the edge travels.")
    sec = st.selectbox("Sector", ["World indices", "FX", "Crypto"], key="ft_sector")
    if st.button(f"▶ Run on {sec}", key="ft_sec_run"):
        st.session_state["ft_sec_go"] = sec
    if st.session_state.get("ft_sec_go") == sec:
        try:
            rs = lab_fresh_sector_run(sec, fin, pd.Timestamp.now().strftime("%Y-%m-%d"), version)
            _fresh_block(f"{sec} (2017–2026)", "Same model, same rules, never tuned on this sector.", rs, budget, "sec")
        except Exception as exc:
            st.warning(f"This sector couldn't run ({type(exc).__name__}: {exc}).")
    st.caption("Just for fun and learning. Past results don't guarantee future ones. Not financial advice.")


# ---------------------------------------------------------------- v32: THE MODEL + THE S&P 500, and the futures-curve log

CURVE_LOG = focus.PATH.parent / "curve_log.csv"


def spx_prices():
    """SPY with dividends reinvested (Yahoo's adjusted prices), as long a history as Yahoo has."""
    p = signals._disk_cache("spy_max", 24, lambda: assetlab.download_prices(("SPY",), period="max"))
    return p["SPY"] if "SPY" in p else p.iloc[:, 0]


def switch_on_setting():
    return bool(setting_get("six_month_switch", True))


def switch_active(res):
    """True when the 6-month switch says the model's money should be in the S&P this week."""
    return switch_on_setting() and bool((res or {}).get("switch", {}).get("now"))


def model_share():
    v = setting_get("model_share", 0.5)
    return v if v in workshop.MIX_SHARES[:-1] else 0.5


def _mix_block(title, model_weekly, budget, key):
    st.markdown(f"#### {title}")
    sw = workshop.spx_weekly(spx_prices(), model_weekly.index)
    T, Y = workshop.mix_table(model_weekly, sw)
    st.markdown(md_table(pd.DataFrame([{
        "Mix": f"**{r['Mix']}**", "% a year": f"**{_p(r['% a year'])}**", "Worst drop": _p(r["Worst drop %"]),
        "Return per unit of risk": f"{r['Return per unit of risk']:.2f}", "Losing years": r["Losing years"],
        f"{_gbp(budget)} grows to": _gbp(budget * (1 + r["% a year"] / 100) ** (len(model_weekly) / 52))}
        for _, r in T.iterrows()])))
    with st.expander("Year by year"):
        Yt = Y.copy()
        Yt.index = [str(i) for i in Yt.index]
        st.markdown(md_table(pd.DataFrame({"Year": [f"**{i}**" for i in Yt.index],
                                           **{c: [_p(v) for v in Yt[c]] for c in Yt.columns}})))
    return T


def lab_mix_section():
    st.markdown("#### 🧩 The model + the S&P 500 together")
    st.markdown("The quant research says the way to beat the S&P isn't to replace it, it's to **add something that "
                "wins in different years**. Trend-following commodities did well in 2008 and 2022 when the S&P fell. "
                "This splits the money between the commodities model (on CFDs, with fees) and an S&P 500 fund (SPY, "
                "dividends included, no overnight fee), rebalanced every week, on the years used to build the model "
                "AND on the fresh 2001–2016 years. **'50/50 + 6-month switch'** puts the model's half into the S&P too "
                "whenever the model has lost money over its last 6 months.")
    c1, c2 = st.columns([1, 3])
    budget = float(c1.number_input("Money (£)", 100.0, 1_000_000.0, 1000.0, 100.0, key="mx_budget"))
    if c2.button("▶ Run the mix test", key="mx_run", type="primary"):
        st.session_state["mx_go"] = True
    version = version_picker("mx_version")
    if not st.session_state.get("mx_go"):
        st.info("Press the button. It reuses the model and fresh-test runs (a few minutes the first time) and downloads "
                "the S&P 500's history.")
        return
    fin = float(st.session_state.get("cm_fin", workshop.LONG_FINANCING_WEEK))
    day = pd.Timestamp.now().strftime("%Y-%m-%d")
    out = {}
    try:
        res = lab_cmodel_run(fin, day, version)
        out["built"] = _mix_block("1. 2017–2026 (the years the model was built on)", res["weekly"], budget, "b")
    except Exception as exc:
        st.warning(f"The 2017–2026 mix couldn't run ({type(exc).__name__}: {exc}).")
    try:
        old = lab_fresh_run("old", fin, day, version)
        if old:
            out["fresh"] = _mix_block("2. 2001–2016 (fresh: the model never saw these years)", old["weekly"], budget, "f")
    except Exception as exc:
        st.warning(f"The 2001–2016 mix couldn't run ({type(exc).__name__}: {exc}).")
    if out:
        st.markdown("#### What it means")
        lines = []
        for k, T in out.items():
            t = T.set_index("Mix")
            half, spx, swr = t.loc["50% model + 50% S&P 500"], t.loc["S&P 500 only"], t.loc["50/50 + 6-month switch"]
            lab = "2017–2026" if k == "built" else "2001–2016 (fresh)"
            lines.append(f"- **{lab}:** 50/50 + switch {_p(swr['% a year'])} a year (worst drop {_p(swr['Worst drop %'])}); "
                         f"plain 50/50 {_p(half['% a year'])} ({_p(half['Worst drop %'])}); S&P alone "
                         f"{_p(spx['% a year'])} ({_p(spx['Worst drop %'])}).")
        st.markdown("\n".join(lines))
        both = all(T.set_index("Mix").loc["50% model + 50% S&P 500", "Return per unit of risk"] >
                   T.set_index("Mix").loc["S&P 500 only", "Return per unit of risk"] for T in out.values())
        st.markdown("✅ **The mix gave more return for each unit of risk than the S&P alone in every period tested.** "
                    "That's the honest way to 'beat the S&P': similar returns, smaller falls." if both else
                    "🟡 The mix didn't beat the S&P on risk in every period. Look at the years above before using it.")
        save_last("mix", dict(tables={k: v for k, v in out.items()}, version=version))
    st.caption("SPY = an S&P 500 fund with dividends reinvested. Held in a normal (non-CFD) account it has no "
               "overnight fee. Just for fun and learning; past results don't guarantee future ones. Not financial advice.")


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def lab_curve_snapshot(day):
    snap = workshop.curve_snapshot(lambda t: assetlab.download_prices(t, period="5d"), day)
    try:
        old = pd.read_csv(CURVE_LOG, parse_dates=["date"]) if CURVE_LOG.exists() else pd.DataFrame()
        allr = pd.concat([old, snap], ignore_index=True).drop_duplicates(["date", "ticker"], keep="last")
        CURVE_LOG.parent.mkdir(parents=True, exist_ok=True)
        allr.to_csv(CURVE_LOG, index=False)
    except Exception:
        allr = snap
    return snap, allr


def curve_section(names):
    st.markdown("### 9. Futures curve log (so we can test 'carry' properly later)")
    st.markdown("The best idea in the research was combining trends with **carry**: buying commodities whose next "
                "futures contract is cheaper than the current one (backwardation). Yahoo has no history of the next "
                "contract, so this page now **records it every time you run the model**. After a few months there'll "
                "be enough to test it honestly.")
    try:
        snap, allr = lab_curve_snapshot(pd.Timestamp.now().strftime("%Y-%m-%d"))
    except Exception as exc:
        st.caption(f"Couldn't record the curve this time ({type(exc).__name__}). It'll try again next run.")
        return
    ok = snap.dropna(subset=["carry_year"])
    days = allr["date"].nunique() if not allr.empty else 0
    st.caption(f"Recorded on {days} day(s) so far; {len(ok)} of {len(snap)} commodities had two live contracts today.")
    if not ok.empty:
        ok = ok.sort_values("carry_year", ascending=False)
        st.markdown(md_table(pd.DataFrame([{"Commodity": f"**{names.get(r['ticker'], r['ticker'])}**",
                                            "Front": r["front"], "Next": r["next"],
                                            "Carry a year": _p(r["carry_year"]),
                                            "Curve": "backwardation (pays to hold)" if r["carry_year"] > 0 else "contango (costs to hold)"}
                                           for _, r in ok.iterrows()])))


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def lab_pattern_run(cls, sides, hold, start, find_end, confirm_end, end, use_weather, use_hourly):
    uni, prices, _ = lab_prices((cls,))
    ohlc = lab_ohlc((cls,), uni, prices).get(cls)
    proxies = None
    if cls == "Commodities":
        try:
            proxies = signals._disk_cache("etf_proxies", 12, lambda: assetlab.download_prices(tuple(workshop.ETF_PROXY.values())))
        except Exception:
            proxies = None
    ctx, status = lab_context((cls,))
    notes = []
    weather = None
    if use_weather:
        weather, errs = pattern_lab.load_weather(pd.Timestamp(start) - pd.DateOffset(years=6), end, progress=_progress_cb())
        notes += [f"Weather not loaded for {e}" for e in errs]
    hourly = None
    if use_hourly:
        try:
            hourly = pattern_lab.load_hourly(tuple(prices[cls].columns))
        except Exception as exc:
            notes.append(f"Hourly prices not available ({type(exc).__name__})")
    res = pattern_lab.run(prices[cls], ohlc, start, end, find_end, confirm_end, list(sides), hold=hold, proxies=proxies,
                          ctx=ctx, weather=weather, hourly=hourly, progress=_progress_cb())
    if res:
        res["notes"] = notes
    return res


def lab_pattern_section():
    st.caption("Every trade is a test case. For each one we record everything we can measure at the moment it was "
               "placed (its chart, the whole market, the calendar, the moon, the Fed and data releases, the fear "
               "index, the dollar, hedge-fund positioning, inventories and the WEATHER where it's grown or used), "
               "then look for conditions that came before wins or losses. Patterns are FOUND in the first years, must "
               "REPEAT in the confirm years, and are then tried on the FINAL years that the search never saw.")
    c1, c2, c3 = st.columns([1.2, 2.6, 0.8])
    cls = c1.selectbox("Sector", assetlab.CLASSES, index=assetlab.CLASSES.index("Commodities"), key="pl_cls")
    options = [n for n, (_, _, ap) in backtest.SIDES.items() if ap != "cross" and (ap is None or cls in ap)]
    default = [s for s in ("Momentum 12-1", "52-week high", "Monte Carlo: trend continues") if s in options]
    sides = c2.multiselect("Strategies whose trades to study", options, default=default, key="pl_sides")
    hold = int(c3.selectbox("Hold (weeks)", [1, 2, 4], index=2, key="pl_hold"))
    d1, d2, d3, d4 = st.columns(4)
    start = d1.date_input("From", value=pd.Timestamp("2017-01-06").date(), key="pl_start")
    find_end = d2.date_input("Confirm from", value=pd.Timestamp("2022-01-01").date(), key="pl_find")
    confirm_end = d3.date_input("Final test from", value=pd.Timestamp("2024-01-01").date(), key="pl_conf")
    end = d4.date_input("To", value=(pd.Timestamp.now().normalize() - pd.DateOffset(days=7)).date(), key="pl_end")
    e1, e2 = st.columns(2)
    use_weather = e1.toggle("Include weather (downloads ~10 years for 11 places, first time only)", value=True, key="pl_wx")
    use_hourly = e2.toggle("Include hour-of-day (last 2 years of hourly prices)", value=True, key="pl_hr")
    ok = pd.Timestamp(start) < pd.Timestamp(find_end) < pd.Timestamp(confirm_end) < pd.Timestamp(end)
    if not ok:
        st.error("Dates must go From → Confirm from → Final test from → To.")
    if not sides:
        return
    if st.button("▶ Find the patterns", key="pl_run", disabled=not ok):
        st.session_state["pl_params"] = (cls, tuple(sides), hold, str(start), str(find_end), str(confirm_end), str(end),
                                         use_weather, use_hourly)
    if "pl_params" not in st.session_state:
        st.info("Press the button. The first run downloads weather and hourly prices, so it takes a few minutes.")
        return
    try:
        res = lab_pattern_run(*st.session_state["pl_params"])
    except Exception as exc:
        st.error(f"The Pattern lab failed ({type(exc).__name__}: {exc}).")
        with st.expander("Technical details"):
            st.exception(exc)
        return
    if not res or res["patterns"].empty:
        st.warning("Not enough trades to find patterns. Try more strategies or a longer period.")
        return
    P, luck, T, base = res["patterns"], res["luck"], res["trades"], res["base"]
    for n_ in res.get("notes", []):
        st.caption(f"⚠ {n_}")
    real = max(0, luck["found"] - luck["luck_mean"])
    held = P[(P["verdict"] != "mixed / noise")]
    n_held = int((held["held_final"] == "✅ held").sum())
    st.success(f"{len(T)} trades × {P['key'].nunique()} conditions = {len(P)} things tested. **{luck['found']}** "
               f"patterns repeated in find AND confirm, but pure luck makes about **{luck['luck_mean']:.0f}** "
               f"(up to {luck['luck_95']:.0f}), so roughly **{real:.0f}** may be real. In the FINAL years, "
               f"**{n_held} of {len(held)}** kept their direction.")
    save_last("patterns", dict(patterns=P, luck=luck, model=res["model"], timing=res["timing"],
                               params=st.session_state["pl_params"]))
    tabs = st.tabs(["Strongest patterns", "Does it improve the model?", "When is the money made?", "Weather",
                    "Every condition tested", "Luck check"])
    with tabs[0]:
        st.caption("Patterns that repeated in both the find and confirm years and beat the luck check, with whether "
                   "they then held in the final years. ✅ held = still worked on years never used to find it.")
        show = held[held["beats_luck"]] if held["beats_luck"].any() else held
        for title, part in (("Before WINS", show[show["edge_find"] > 0]), ("Before LOSSES", show[show["edge_find"] < 0])):
            st.markdown(f"#### {title}")
            if part.empty:
                st.caption("None.")
            for _, r in part.sort_values("held_final").iterrows():
                st.markdown(f"- {r['held_final'].split(' ')[0]} **{r['condition']}: {r['level']}**"
                            + (f" ({r['range']})" if r["key"] not in pattern_lab.CATEGORICAL else "")
                            + f" · find {r['edge_find']:+.2f}, confirm {r['edge_confirm']:+.2f}, final "
                            + (f"{r['edge_final']:+.2f}" if r["edge_final"] == r["edge_final"] else "n/a")
                            + f" pts vs normal · held in {r['years_held']} of {r['years_tested']} years · "
                            + f"{int(r['n_find'] + r['n_confirm'] + r['n_final'])} trades")
    with tabs[1]:
        st.caption("Each trade gets a score from the patterns it matched when it was placed. The worst-scoring 30% "
                   "are skipped and the best get 1.5x the money. Cut-offs are set on the confirm years; the results "
                   "below are ONLY the final years, which the search never touched.")
        MT = res["model"]
        if MT.empty:
            st.info("Not enough final-year trades.")
        else:
            smart_table(MT.rename(columns={"version": "Version", "rules": "Patterns used", "trades": "Trades",
                                           "win_rate": "Winning trades %", "avg_trade": "Avg trade %",
                                           "per_year": "Per year %", "worst_drop": "Worst drop %",
                                           "big_losses": "Losses worse than -8%"}).round(2), "pl_mt", totals=False)
            b0 = MT.iloc[0]
            best = MT.iloc[2:].sort_values("per_year", ascending=False).iloc[0] if len(MT) > 2 else None
            if best is not None:
                st.markdown(f"**Verdict:** as it was, the final years made {b0['per_year']:+.1f}% a year. The best "
                            f"pattern-adjusted version made {best['per_year']:+.1f}% "
                            + ("— the patterns genuinely helped." if best["per_year"] > b0["per_year"] + 2 else
                               "— no real improvement: most patterns were luck, or stopped working."))
    with tabs[2]:
        st.caption("Where each trade's result came from: overnight (from one day's close to the next open) or during "
                   "the day (open to close), and on which weekday. Shown for winning and losing trades separately.")
        st.dataframe(res["timing"].round(2), width="stretch")
        per = T.assign(Period=pattern_lab.periods(T, *st.session_state["pl_params"][4:6]))
        st.dataframe(per.groupby("Period")[["overnight", "daytime", "day_Mon", "day_Tue", "day_Wed", "day_Thu", "day_Fri"]]
                     .mean().round(2).rename(columns={"overnight": "Overnight %", "daytime": "Daytime %"}), width="stretch")
        st.caption("The same split for each period: a timing pattern is only worth using if it shows up in all three.")
        if res.get("hourly") is not None and not res["hourly"].empty:
            st.markdown("**By hour of day (New York time, last 2 years)**")
            st.dataframe(res["hourly"].round(3), width="stretch")
    with tabs[3]:
        wx = P[P["family"] == "Weather"]
        if wx.empty:
            st.info("No weather data in this run (switch it on, or the download failed).")
        else:
            smart_table(wx[["condition", "level", "range", "avg_find", "avg_confirm", "avg_final", "years_held",
                            "years_tested", "verdict", "held_final"]].round(2), "pl_wx", totals=False)
            st.caption("Weather where each commodity is grown or used (e.g. Iowa for corn, Ivory Coast for cocoa, "
                       "Houston for oil), plus New York and London 'trader weather'. Temperatures and rain are vs "
                       "the normal for that time of year in earlier years.")
    with tabs[4]:
        cols = ["family", "condition", "level", "range", "n_find", "avg_find", "n_confirm", "avg_confirm", "n_final",
                "avg_final", "years_held", "years_tested", "luck_chance", "verdict", "held_final"]
        smart_table(P[cols].rename(columns={"family": "Family", "condition": "Condition", "level": "Level",
                                            "range": "Range", "n_find": "Trades (find)", "avg_find": "Avg % (find)",
                                            "n_confirm": "Trades (confirm)", "avg_confirm": "Avg % (confirm)",
                                            "n_final": "Trades (final)", "avg_final": "Avg % (final)",
                                            "years_held": "Years held", "years_tested": "Years tested",
                                            "luck_chance": "Chance it's luck", "verdict": "Verdict",
                                            "held_final": "Final years"}).round(3), "pl_all", height=520)
        st.caption(f"Normal trade: find {base['find']:+.2f}%, confirm {base['confirm']:+.2f}%, final "
                   f"{base['final']:+.2f}% per {st.session_state['pl_params'][2]}-week trade, after costs.")
    with tabs[5]:
        st.markdown(f"We tested **{len(P)}** condition levels. If NOTHING was real, shuffling the results randomly "
                    f"still produces about **{luck['luck_mean']:.0f}** 'patterns' that repeat in both periods "
                    f"(95% of shuffles produce at most {luck['luck_95']:.0f}). We found **{luck['found']}**.")
        st.markdown("So the honest reading is: **some** patterns are real, but most of the list could be chance. "
                    "That's why the final years and the live prediction log are the real judges.")


def page_this_week():
    last = load_last()
    bt, md = last.get("backtest"), last.get("model")
    c1, c2, c3 = st.columns([1, 1, 2])
    budget = float(c1.number_input("Practice money to use (£)", 100.0, 1_000_000.0, 1000.0, 100.0, key="tw_budget"))
    min_move = float(c2.number_input("Minimum expected move (%)", 0.0, 5.0, 0.8, 0.1, key="tw_min",
                                     help="Only trades expected to move at least this much (up to buy, down to short)."))
    c3.caption("How to use: 1) In TEST, run a Backtest and the Model (they decide what's in focus). "
               "2) Come back here each weekend: these are the trades that pass every filter. "
               "3) Place them on the practice account and save them in LEARN FROM MISSES → Prediction log.")
    cm = last.get("cmodel")
    with st.container(border=True):
        ui.panel_title("Commodities model", "HOLD 4 WEEKS · -8% WEEKLY STOP")
        if not cm:
            st.caption("Run TEST → Commodities model once to see what it holds.")
        else:
            H, nmap = cm["holding"], cm.get("names", {})
            if H.empty:
                st.markdown("Holding nothing right now.")
            else:
                st.markdown(md_table(pd.DataFrame([{"Commodity": f"**{nmap.get(r['Ticker'], r['Ticker'])}**",
                                                    "Action": "BUY", "Share": f"{r['Share of the money %']:.0f}%",
                                                    f"Of {_gbp(budget)}": _gbp(r['Share of the money %'] / 100 * budget)}
                                                   for _, r in H.iterrows()])))
            st.caption(f"Picked {cm['picked_on']:%d %b}; next re-pick after the close on {cm['next_change']:%a %d %b}. "
                       f"Sell any holding early if a Friday close is 8% below where you bought it. "
                       f"(From the run on {cm['saved']:%d %b %H:%M}: rerun it each weekend.)")
    rows = []
    # 1. focus strategies' picks this week
    if bt and "cards" in bt and not bt["cards"].empty:
        cards = bt["cards"]
        focus_pairs = {(r["side"], r["cls"]) for _, r in cards.iterrows() if str(r.get("status", "")).startswith("🎯")}
        classes = tuple(sorted({c for _, c in focus_pairs})) or tuple(bt["params"][0])
        try:
            picks = lab_live_picks(classes)
        except Exception as exc:
            picks = pd.DataFrame()
            st.warning(f"Couldn't work out the strategies' picks ({type(exc).__name__}: {exc}).")
        if not picks.empty:
            uni, _, _ = lab_prices(classes)
            for _, p in picks.iterrows():
                if (p["side"], p["cls"]) not in focus_pairs:
                    continue
                e = p.get("expected", np.nan)
                up = p["direction"] == "BUY"
                if min_move and not (e == e and ((up and e >= min_move) or (not up and e <= -min_move))):
                    continue
                rows.append(dict(Source=f"Strategy: {p['side']}", Class=p["cls"], Asset=name_of(p["ticker"], uni),
                                 Ticker=p["ticker"], Action=p["direction"], Risk="",
                                 **{"Expected move %": e, "Take-profit %": p.get("tp"), "Stop-loss %": p.get("sl"),
                                    "Normal week %": p.get("normal")}))
    # 2. the model's calls
    if md and md.get("latest"):
        for cls, (t, lastc) in md["latest"].items():
            for tick, r in lastc.iterrows():
                if abs(r["pred"]) < min_move or str(r.get("risk", "")).startswith("🔴"):
                    continue
                m = md.get("levels", {}).get(tick) or {}
                up = r["pred"] > 0
                rows.append(dict(Source="Model", Class=cls, Asset=md.get("names", {}).get(tick, tick), Ticker=tick,
                                 Action="BUY" if up else "SHORT", Risk=r.get("risk", ""),
                                 **{"Expected move %": r["pred"],
                                    "Take-profit %": (m.get("p75_none") if up else -m.get("p25_none", np.nan)) if m else None,
                                    "Stop-loss %": (-m.get("p5_none", np.nan) if up else m.get("p95_none")) if m else None,
                                    "Normal week %": r.get("normal")}))
    if not bt and not md:
        if cm:
            return
        st.info("Nothing to show yet. Go to TEST → Backtest and TEST → Model and run them once: they decide which "
                "strategies are in focus and make the model's calls. Then come back here.")
        return
    if not rows:
        st.warning(f"No trade passes every filter this week (focus strategies, model, at least {min_move}% expected "
                   "move, no 🔴 risk). That's a valid answer: sitting out is a position. Try a lower minimum move to "
                   "see what's close.")
        return
    df = pd.DataFrame(rows)
    df["Practice £"] = [_size(budget, len(df), r) for r in df["Risk"]]
    st.markdown(f"**{len(df)} trades pass every filter.** Split equally across £{budget:,.0f} (half size for 🟡 risk).")
    smart_table(df.round(2), "tw")
    made = [f"backtest {bt['saved']:%d %b %H:%M}" if bt else "", f"model {md['saved']:%d %b %H:%M}" if md else ""]
    st.caption("Based on your last runs: " + ", ".join(x for x in made if x) + ". Expected moves are for the next "
               "week. Take-profit and stop-loss come from the Monte Carlo (the 75th percentile target and 5th "
               "percentile stop), as % from the entry price.")


def _pc(x):
    try:
        x = float(x)
        return f"{x:+.2f}%" if np.isfinite(x) else "n/a"
    except (TypeError, ValueError):
        return "n/a"


def page_whats_working():
    last = load_last()
    if not last:
        st.info("Run TEST → Commodities model (or Backtest, Signal Lab and Model) first. This page then sums up what's working.")
        return
    bt, sl, md = last.get("backtest"), last.get("signal"), last.get("model")
    if bt:
        cards = bt["cards"]
        with st.container(border=True):
            ui.panel_title("Strategies", f"LAST BACKTEST {bt['saved']:%d %b %Y} · {bt['start']:%b %Y} TO {bt['end']:%b %Y}")
            sure = cards[(cards.get("vs_coin_week", pd.Series(dtype=float)) > 0) & (cards.get("vs_coin_p", pd.Series(dtype=float)) < 0.05)] \
                if "vs_coin_p" in cards else cards.iloc[0:0]
            foc = cards[cards.get("status", pd.Series("", index=cards.index)).astype(str).str.startswith("🎯")]
            lines = [f"- **{r['side']}** on **{r['cls']}**: {_pc(r['avg_week'])} a week, {_pc(r['vs_coin_week'])} better than a coin toss ✅"
                     for _, r in sure.sort_values("vs_coin_week", ascending=False).head(6).iterrows()]
            st.markdown(f"**{len(foc)} of {len(cards)}** strategy sides are in focus; **{len(sure)}** clearly beat the coin toss.")
            if lines:
                st.markdown("\n".join(lines))
            if "hold_week" in cards and cards["hold_week"].notna().any():
                better = int((cards["avg_week"] > cards["hold_week"]).sum())
                st.markdown(f"- Take-profit + stop-loss did better than holding to Friday for **{better} of "
                            f"{int(cards['hold_week'].notna().sum())}** sides.")
            lab_focus_winners(cards, bt["side_returns"], bt["start"], bt["end"], "ww")
    if sl:
        lg = sl["league"]
        with st.container(border=True):
            ui.panel_title("Ingredients", f"LAST SIGNAL LAB {sl['saved']:%d %b %Y}")
            good = lg[lg["verdict"].str[:1].isin(["✅", "🔄"])]
            prom = lg[lg["verdict"].str[:1].isin(["🟡", "⚠"])]
            st.markdown(f"**{len(good)}** confirmed (✅ or 🔄 reverse), **{len(prom)}** promising, out of {len(lg)} tests.")
            for _, r in good.head(10).iterrows():
                st.markdown(f"- **{r['ingredient']}** on **{r['cls']}**: {plain_line(r)}")
    if md:
        with st.container(border=True):
            ui.panel_title("The model", f"LAST RUN {md['saved']:%d %b %Y}")
            c = md["cards"]
            if not c.empty and "unseen_vs_coin" in c:
                best = c.sort_values("unseen_vs_coin", ascending=False).groupby("cls").head(1)
                for _, r in best.iterrows():
                    st.markdown(f"- **{r['cls']}**: best side **{r['side']}**, {_pc(r['unseen_week'])} a week on the "
                                f"unseen period, {_pc(r['unseen_vs_coin'])} vs a coin toss. {r['verdict']}")
            proven = {k: v for k, v in (md.get("risk_flags") or {}).items() if v}
            if proven:
                st.markdown("**Risk checks that proved themselves:** " +
                            "; ".join(f"{k}: {', '.join(v)}" for k, v in proven.items()))
            if md.get("arena"):
                st.markdown("**Arena winners:** " + " · ".join(f"{k}: {v}" for k, v in md["arena"][1].items()))
    cm = last.get("cmodel")
    if cm:
        with st.container(border=True):
            ui.panel_title("Commodities model", f"LAST RUN {cm['saved']:%d %b %Y}")
            P = cm["periods"].set_index("Period")
            for name, r in P.iterrows():
                st.markdown(f"- **{name}** ({r['From']:%b %Y} → {r['To']:%b %Y}): **{_p(r['Model % a year'])} a year**, "
                            f"worst drop {_p(r['Worst drop %'])}; buying everything {_p(r['Buy everything % a year'])} a year.")
            Y = cm["years"]
            st.markdown("**By year:** " + " · ".join(f"{r['Year'][:4]} {_p(r['Model %'], 0)}" for _, r in Y.iterrows()))
    ws = last.get("workshop")
    if ws is not None and isinstance(ws.get("best"), pd.DataFrame) and not ws["best"].empty:
        with st.container(border=True):
            ui.panel_title("Commodities workshop", f"LAST RUN {ws['saved']:%d %b %Y}")
            b = ws["best"]
            g = b[b["verdict"].str.startswith("✅")].sort_values("unseen_avg", ascending=False)
            st.markdown(f"**{len(g)} of {len(b)}** commodity strategies made money in both discovery and unseen years:")
            for _, r in g.iterrows():
                st.markdown(f"- **{r['side']}** ({r['settings']}): {_pc(r['unseen_avg'])} a week unseen, "
                            f"up in {r['years_up']} of {r['years']} years")
            u = ws.get("portfolio_unseen")
            if u:
                st.markdown(f"- **Combined:** {_pc(u['avg_week'])} a week on the unseen years, {_pc(u['total'])} in total.")
    p = focus.parked_table()
    with st.container(border=True):
        ui.panel_title("Parked for later", f"{len(p)} ITEMS")
        if p.empty:
            st.caption("Nothing parked yet.")
        else:
            st.markdown(" · ".join(f"{k}: **{v}**" for k, v in p["kind"].value_counts().items()) +
                        ". See PARKED for the reasons, and to bring any back.")


def page_parked():
    st.caption("Parked = losing for now, so it's hidden from focus. Nothing is deleted: each item keeps the date, the "
               "reason and its numbers. Rerunning a test un-parks anything that has improved. Bring one back by hand "
               "and it stays in focus until you park it again.")
    p = focus.parked_table()
    if p.empty:
        st.info("Nothing parked yet. Running TEST → Backtest, Signal Lab or Model parks anything that's clearly losing.")
        return
    show = p.rename(columns={"kind": "Type", "name": "Name", "cls": "Class", "parked_on": "Parked on", "reason": "Why"})
    smart_table(show.drop(columns=["id"]), "pk")
    labels = {r["id"]: f"{r['kind']} · {r['name']} · {r['cls']}" for _, r in p.iterrows()}
    c1, c2 = st.columns([3, 1])
    pick = c1.selectbox("Bring one back into focus", list(labels), format_func=labels.get, key="pk_pick")
    if c2.button("↩ Bring back", key="pk_back") and pick:
        focus.bring_back(pick)
        st.success(f"Brought back: {labels[pick]}. It stays in focus until you park it again.")
        st.rerun()


def page_legal():
    keys = list(legal.SECTIONS)
    start = st.query_params.get("s") if st.query_params.get("s") in keys else "disclaimer"
    choice = st.segmented_control("Section", keys, default=start, key="legal_s",
                                  format_func=lambda k: legal.SECTIONS[k][0].upper(),
                                  label_visibility="collapsed") or start
    if CONSENT is None:
        st.button("◄ Back to the start", on_click=go_to, kwargs=dict(page="HOME"))
    with st.container(border=True):
        st.markdown(legal.SECTIONS[choice][1])
    if choice == "cookies":
        with st.container(border=True):
            ui.panel_title("Cookie settings", "CHANGE ANY TIME")
            now = {"a": "Accept all (TradingView charts and Google Fonts on)",
                   "e": "Essential only (TradingView charts and Google Fonts off)"}.get(CONSENT, "No choice made yet")
            st.markdown(f"**Your current choice:** {now}")
            if CONSENT is not None:
                c1, c2, c3 = st.columns(3)
                c1.button("Accept all", on_click=set_consent, args=("a",), width="stretch", key="ck_all")
                c2.button("Essential only", on_click=set_consent, args=("e",), width="stretch", key="ck_ess")
                c3.button("Withdraw and ask me again", on_click=set_consent, args=(None,), width="stretch",
                          key="ck_clear")
            else:
                st.caption("Go back to the start to make your choice.")



# ================================================================= BUBBLE WATCH (PC version only)

def _bubble_yahoo(code):
    import yfinance as yf
    h = yf.Ticker(code).history(period="max", auto_adjust=True)
    idx = pd.DatetimeIndex(h.index).tz_localize(None).normalize()
    return pd.Series(h["Close"].values, index=idx), pd.Series(h["Volume"].values, index=idx)


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def bubble_run(day):
    """Downloads (kept on your PC for 12 hours) and works out the whole checklist. `day` refreshes it daily."""
    bar = st.progress(0.0, text="Downloading bubble data...")
    df = signals._disk_cache("bubble_data", 12, lambda: bubble.download(
        _bubble_yahoo, fetch_fred, get_fred_key(),
        progress=lambda f, c: bar.progress(min(f, 1.0), text=f"Downloading {c}...")))
    bar.progress(1.0, text="Working out the checklist...")
    S = bubble.from_rows(df)
    D = bubble.Data(S)
    signs, extras = bubble.build(D)
    score, st_tab = bubble.score_table(signs)
    nas = S.get("^IXIC")
    fwd = bubble.bear_ahead(nas, D.W)
    tp = bubble.tops(nas, fall=20)
    wtt = bubble.weeks_to_top(nas, D.W)
    built = pd.Series(D.W < pd.Timestamp("2011-01-01"), index=D.W) & (score["available"] >= 25)
    unseen = pd.Series(D.W >= pd.Timestamp("2011-01-01"), index=D.W)
    key_b = bubble.key_table(score, fwd, wtt, built)
    key_u = bubble.key_table(score, fwd, wtt, unseen)
    key_all = bubble.key_table(score, fwd, wtt, score["available"] >= 25)
    test, base = bubble.sign_test(signs, st_tab, fwd, score["available"] >= 25)
    giants = extras["giants"] if extras["giants"] is not None else nas
    matches = bubble.analog_match(S, giants)
    matches_n = bubble.analog_match(S, nas)
    try:
        BS = bubble_stats(S, nas, score, signs)
    except Exception:
        BS = None
    bar.empty()
    for s in signs:                                 # keep only what the page shows
        s["now"] = s["value"].dropna().iloc[-1] if s["value"].notna().any() else np.nan
        s["light"] = s["status"].dropna().iloc[-1] if s["status"].notna().any() else np.nan
        s["light_now"] = s["status_now"].dropna().iloc[-1] if s["status_now"].notna().any() else np.nan
        s["status_now"] = s["status_now"].iloc[-260:]
        s["value"] = s["value"].iloc[-260:]
        s["status"] = s["status"].iloc[-260:]
    picks = extras["picks"]
    lead_now = picks[max(picks)] if picks else []
    src = giants
    tw = src.resample("W-FRI").last().dropna().iloc[-156:]
    today_path = (tw / tw.iloc[0] * 100).values if len(tw) == 156 else None
    return dict(signs=signs, score=score, tops=tp, key_b=key_b, key_u=key_u, key_all=key_all, test=test, base=base,
                matches=matches, matches_n=matches_n, leaders_now=lead_now, nasdaq=nas.resample("W-FRI").last(),
                asof=D.W[-1], sources=len(S), today_path=today_path, stats=BS)


def _bubble_fmt(s):
    v = s["now"]
    if v != v:
        return "no data"
    u = s["unit"]
    if s["id"] == "cross":
        return {0: "neither", 1: "one of the two", 2: "both"}.get(int(v), f"{v:.0f}")
    if u == "pct":
        if v >= 99.5:
            return "highest ever"
        if v <= 0.5:
            return "lowest ever"
        return f"top {100 - v:.0f}% of history" if v >= 50 else f"bottom {v:.0f}% of history"
    if u == "x":
        return f"{v:.2f}x"
    if u == "wks":
        return f"{v:.0f} weeks ago"
    if u == "days":
        return f"{v:.0f} days"
    if u == "pts":
        return f"{v:+.2f}"
    if u == "%":
        return f"{v:+.1f}%" if s["id"] not in ("narrow", "leadbreak", "worldbreak", "world") else f"{v:.0f}%"
    return f"{v:.2f}"


def _bubble_weeks(w):
    if w != w:
        return "–"
    if w < 0.5:
        return "already past"
    if w < 8:
        return f"{w:.0f} weeks"
    return f"{w / 4.35:.0f} months"


def page_bubble():
    if PUBLIC:
        st.info("Bubble Watch is only available in the PC version.")
        return
    st.markdown(look.page_header("Models · PC only", "Bubble Watch"), unsafe_allow_html=True)
    st.caption("A checklist of the warning signs that came before past bubbles burst: Nasdaq 1987, 2000, 2008, 2022 and "
               "2025, Japan 1989, China 2007 and 2015, Hong Kong, Bitcoin. Built on 1985-2010, checked on 2011-2026. "
               "Not financial advice.")
    try:
        with ui.loading("Checking the warning signs", scene="bubble", once="bubble"):
            R = bubble_run(pd.Timestamp.now().strftime("%Y-%m-%d"))
    except Exception as e:
        st.warning(f"Couldn't load the bubble data ({type(e).__name__}). Check your internet and FRED key, then reload.")
        return
    signs, sc = R["signs"], R["score"]
    try:
        _lit = {str(x.get("name")): x.get("light") for x in signs}
        look.remember("bubble_lights", [int(_lit[n["name"]]) if _lit.get(n["name"]) == _lit.get(n["name"]) and n["name"] in _lit else 3
                                        for n in look._snapshot()["signs"]])
    except Exception:
        pass
    now = sc.iloc[-1]
    n = int(now["available"])
    pts = now["points"]
    band, band_text = bubble.band_of(now["pct"])
    key = R["key_all"].set_index("band")
    kr = key.loc[band].to_dict() if band in key.index else None
    est = bubble.time_estimate(kr, R["matches"])
    colour = {"Calm": "⚪", "Warming up": "🟡", "Frothy": "🟠", "Danger zone": "🔴", "High alert": "🚨"}.get(band, "")

    # ---------------- 1. the headline
    st.markdown(f"## {pts:g} / {n} &nbsp; {colour} {band.upper()}")
    st.markdown(f"**{int(now['greens'])} 🟢 happening · {int(now['ambers'])} 🟠 some sign · "
                f"{n - int(now['greens']) - int(now['ambers'])} 🔴 no sign yet** &nbsp;(score = greens + half the ambers)  \n"
                f"{band_text}")
    if kr and kr["chance"] == kr["chance"]:
        st.markdown(f"**In the past, at this score:** the Nasdaq ended up in a 20%+ fall within a year **{kr['chance']:.0f}%** "
                    f"of the time (normal: {R['base']:.0f}%).")
    if est:
        st.markdown(f"**⏱ Time estimate to the top:** about **{_bubble_weeks(est['mid'])}** "
                    f"(range {_bubble_weeks(est['lo'])} – {_bubble_weeks(est['hi'])}), from past scores like this and the "
                    f"closest look-alike bubbles below. Treat it as a rough guide: timing tops is the hardest part.")
    chg4 = pts - sc["points"].iloc[-5] if len(sc) > 5 else 0
    st.caption(f"Data to {R['asof']:%d %b %Y} · {chg4:+g} points vs 4 weeks ago · updates every day you open it")

    try:
        import streamlit.components.v1 as components
        rs = []
        for sg in signs:
            v = sg["status"].dropna()
            rs.append(dict(name=sg["name"], stage=int(sg["stage"]), light=int(v.iloc[-1]) if len(v) else None))
        components.html(fx.bubble_radar(rs, bubble.STAGES, f"{pts:g}/{n}", band), height=520)
        st.caption("📡 Radar: every warning sign as a dot in its stage. 🟢 happening · 🟠 some sign · 🔴 no sign · grey = no data. "
                   "Hover a dot for its name.")
    except Exception:
        pass

    # ---------------- 2. the fuse
    st.markdown("### 1. The fuse: how far along are we?")
    st.caption("Bubbles burst in stages. The further down the fuse the lights are, the closer the bang.")
    cols = st.columns(6)
    for i, (k, (nm, txt)) in enumerate(bubble.STAGES.items()):
        v = now[f"stage{k}"]
        ids = [s for s in signs if s["stage"] == k]
        g = sum(1 for s in ids if s["light"] == 2)
        a = sum(1 for s in ids if s["light"] == 1)
        with cols[i]:
            st.markdown(f"**{k}. {nm}**")
            st.progress(min(max((v or 0) / 100, 0), 1.0))
            st.caption(f"{g} 🟢 · {a} 🟠 of {len(ids)}  \n{txt}")

    # ---------------- 3. the key
    st.markdown("### 2. The key: what the score means")
    kb, ku = R["key_b"].set_index("band"), R["key_u"].set_index("band")
    rows = []
    for lo, hi, nm, txt in bubble.BANDS:
        a, b_ = kb.loc[nm], ku.loc[nm]
        here = " ⬅ **NOW**" if nm == band else ""
        rows.append({"Score": f"{lo * n / 100:.0f}–{min(hi, 100) * n / 100:.0f} / {n}",
                     "Meaning": f"**{nm}**{here}",
                     "20%+ fall within a year (built on 1986-2010)": "–" if a["chance"] != a["chance"] else f"{a['chance']:.0f}%",
                     "Same on unseen 2011-2026": "–" if b_["chance"] != b_["chance"] else f"{b_['chance']:.0f}%",
                     "Typical time to the top": "–" if key.loc[nm, "t_med"] != key.loc[nm, "t_med"] else
                     ("usually already past the top" if key.loc[nm, "t_hi"] < 0.5 else
                      f"{_bubble_weeks(key.loc[nm, 't_med'])} ({_bubble_weeks(key.loc[nm, 't_lo'])}–{_bubble_weeks(key.loc[nm, 't_hi'])})"),
                     "What it's like": txt})
    st.markdown(md_table(pd.DataFrame(rows)))
    st.caption(f"'20%+ fall within a year' = the Nasdaq was 20%+ below its high at some point in the next 12 months (falls "
               f"already under way count). Normal for any week: {R['base']:.0f}%. 'Time to the top' = how long after a week "
               "with that score the Nasdaq hit the high before its next 20%+ fall (0 = the top had already passed).")

    # ---------------- 4. looks most like
    st.markdown("### 3. Today looks most like...")
    m = R["matches"][:3]
    lead = ", ".join(R["leaders_now"])
    st.caption("Today's last 3 years of the AI giants (Nvidia, Microsoft, Alphabet, Meta, Amazon, Apple, Broadcom, Tesla, "
               "equal weight) slid along every past bubble to find where the shape fits best. 'Match' = how closely the shapes line up.")
    if m:
        rows = [{"Past bubble": x["name"], "Best fit at": f"{x['at']:%b %Y}", "Match": f"{x['fit'] * 100:.0f}%",
                 "Then the top came": "at the top" if x["weeks_to_top"] < 1 else f"{_bubble_weeks(x['weeks_to_top'])} later",
                 "Extra rise to the top": f"{x['gain_to_top']:+.0f}%", "Fall after the top": f"{x['fall_after']:.0f}%"} for x in m]
        st.markdown(md_table(pd.DataFrame(rows)))
        fig = go.Figure()
        top = m[0]
        L = len(top["path_then"])
        x_then = list(range(-L + 1, 1))
        fig.add_scatter(x=x_then, y=top["path_then"], name=f"{top['name']} (up to {top['at']:%b %Y})", line=dict(color=ui.DIM, width=2))
        fig.add_scatter(x=list(range(1, len(top["path_after"]) + 1)), y=top["path_after"] * top["path_then"][-1] / 100,
                        name="...what happened next", line=dict(color=ui.DOWN, width=2, dash="dot"))
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor=ui.BG, plot_bgcolor=ui.BG,
                          font=dict(color=ui.TEXT), xaxis_title="weeks (0 = today's position)", yaxis_title="start = 100",
                          legend=dict(orientation="h", y=1.12))
        if R.get("today_path") is not None:
            fig.add_scatter(x=x_then, y=R["today_path"], name="Today", line=dict(color=ui.CYAN, width=3))
        st.plotly_chart(fig, config=ui.PLOT_CONFIG, key="bubble_analog")
    else:
        st.caption("Not enough data for the look-alike check.")

    # ---------------- 5. the checklist
    st.markdown("### 4. The checklist")
    st.caption("🔴 = no sign of it yet · 🟠 = some sign · 🟢 = happening now or has happened. Build-up, Pricey and Fuel signs "
               "stay lit for a year after they fire (the froth is still in the system). "
               f"'Tested' = how often the Nasdaq was in a 20%+ fall within a year when that sign was 🟢 (normal: {R['base']:.0f}%).")
    test = R["test"]
    only_lit = st.toggle("Only show signs that are lit (🟠 or 🟢)", value=False, key="bub_lit")
    for k, (nm, txt) in bubble.STAGES.items():
        ss = [s for s in signs if s["stage"] == k]
        g = sum(1 for s in ss if s["light"] == 2)
        a = sum(1 for s in ss if s["light"] == 1)
        st.markdown(f"#### {k}. {nm} — {g} 🟢 · {a} 🟠 · {len(ss) - g - a} 🔴")
        st.caption(txt)
        rows = []
        for s in ss:
            if only_lit and s["light"] not in (1, 2):
                continue
            t = test.loc[s["id"]] if s["id"] in test.index else None
            tested = "too rare to test" if t is None or t["chance"] != t["chance"] else f"{t['chance']:.0f}%"
            light = "⚪" if s["light"] != s["light"] else bubble.LIGHT[int(s["light"])]
            if s["stage"] <= 3 and s["light"] == s["light"] and s["light_now"] == s["light_now"] and s["light_now"] < s["light"]:
                light += " (earlier this year)"
            rows.append({"": light, "Sign": f"**{s['name']}**", "Now": _bubble_fmt(s), "Rule": s["rule"], "Tested": tested})
        if rows:
            st.markdown(md_table(pd.DataFrame(rows)))
        with st.expander(f"What each {nm.lower()} sign means and when it happened before"):
            st.markdown("\n".join(f"- **{s['name']}:** {s['what']} *{s['lesson']}*" for s in ss))

    # ---------------- 6. score over time
    st.markdown("### 5. The score through history")
    hist = sc[sc["available"] >= 25]
    fig = go.Figure()
    fig.add_scatter(x=hist.index, y=hist["pct"], name="Bubble score (% of signs lit)", line=dict(color=ui.ACCENT, width=2), yaxis="y")
    nq = R["nasdaq"].reindex(hist.index)
    fig.add_scatter(x=nq.index, y=nq, name="Nasdaq (right, log)", line=dict(color=ui.CYAN, width=1.3), yaxis="y2")
    for t in R["tops"]:
        if t["peak"] >= hist.index[0]:
            fig.add_vrect(x0=t["peak"], x1=t["trough"], fillcolor=ui.DOWN, opacity=0.12, line_width=0)
    for lo, hi, nm, _ in bubble.BANDS[1:]:
        fig.add_hline(y=lo, line=dict(color=ui.DIM, width=1, dash="dot"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor=ui.BG, plot_bgcolor=ui.BG,
                      font=dict(color=ui.TEXT), legend=dict(orientation="h", y=1.1),
                      yaxis=dict(title="score %"), yaxis2=dict(overlaying="y", side="right", type="log", showgrid=False))
    st.plotly_chart(fig, config=ui.PLOT_CONFIG, key="bubble_hist")
    st.caption("Red shading = from each Nasdaq top to the bottom of a 20%+ fall. Dotted lines = the key's bands.")
    rows = []
    for t in R["tops"]:
        if t["peak"] < hist.index[0]:
            continue
        p = sc["points"].asof(t["peak"]); av = sc["available"].asof(t["peak"]); pc = sc["pct"].asof(t["peak"])
        p26 = sc["pct"].asof(t["peak"] - pd.Timedelta(weeks=26))
        rows.append({"Nasdaq top": f"{t['peak']:%b %Y}", "Fall": f"{t['fall']:.0f}%",
                     "Score 6 months before": f"{p26:.0f}%", "Score at the top": f"{p:g} / {av:.0f} ({pc:.0f}%)",
                     "Band at the top": bubble.band_of(pc)[0], "Built on / unseen": "built on" if t["peak"].year < 2011 else "unseen"})
    if rows:
        st.markdown(md_table(pd.DataFrame(rows)))

    # ---------------- 7. stats check
    if R.get("stats"):
        bubble_stats_section(R["stats"])

    # ---------------- 8. honest warnings
    st.markdown("### 8. Honest warnings")
    st.markdown(
        "- **There are only about a dozen big tops to learn from**, so every percentage here is rough.\n"
        "- **Bubbles can stay frothy for years.** In 1996 Greenspan warned of 'irrational exuberance'; the Nasdaq then "
        "tripled before it burst. A high score means *risk is high*, not *sell tomorrow*.\n"
        "- **Some crashes come from nowhere** (Covid 2020) and no checklist would have seen them.\n"
        "- **Some signs only have recent data** (junk bond spreads, speculative stocks, VIX curve), so they can't be tested "
        "far back. Those show 'too rare to test'.\n"
        "- The data is FRED and Yahoo Finance. FRED figures are moved to the day they were actually published, so the past "
        "scores only use what was known at the time.\n"
        "- Not financial advice.")



# ================================================================= STATS CHECK (v38): skill or luck?

IDEA_BASE = focus.PATH.parent


def _stats_info(term):
    return ui.info(term, term)


def _stats_light_table(rows):
    st.markdown(md_table(pd.DataFrame(rows)))


def stats_edge_rows(series_by_name, bench, periods):
    """Paired t-test rows: each (name, model weekly) vs the S&P over each (period label, start, end)."""
    rows, tests = [], {}
    for pname, a, b in periods:
        for name, w in series_by_name.items():
            m = w[(w.index >= a) & (w.index < b)] if a is not None else w
            t = stats.edge_vs_benchmark(m, bench.reindex(m.index))
            tests[(pname, name)] = t
            rows.append({"": t["light"], "Period": pname, "Strategy": name, "Verdict": t["verdict"],
                         "Rounds": f"{t['n']}" + (" ⚠" if t["n"] < stats.MIN_N else ""),
                         "Difference % a year (95% range)": "–" if t["n"] < 2 else
                         f"{t['year']:+.1f} ({t['year_lo']:+.1f} to {t['year_hi']:+.1f})",
                         "p-value": stats.fmt_p(t["p"]),
                         "Smallest edge it could spot": "–" if t["mde_year"] != t["mde_year"] else f"{t['mde_year']:.0f}% a year"})
    return rows, tests


def stats_section(heading, R, unseen_from, key, fresh=False):
    """The full stats check for the commodities model (or one fresh test)."""
    st.markdown(heading)
    st.markdown("The tests from a Data Analysis course, used to tell a real edge from a lucky run. Each **round** is "
                "4 weeks (the model's holding time), so rounds don't overlap. Significance level: 5%. "
                f"{_stats_info('p-value')} {_stats_info('confidence interval')} {_stats_info('paired t-test')}",
                unsafe_allow_html=True)
    try:
        spx = workshop.spx_weekly(spx_prices(), R["weekly"].index)
    except Exception as exc:
        st.warning(f"Couldn't load the S&P 500 for the comparison ({type(exc).__name__}). Check your internet.")
        return
    model = R["weekly"]
    sw = workshop.switch_state(model)["switched"].reindex(model.index).fillna(False)
    setup = pd.Series(np.where(sw, spx, 0.5 * model + 0.5 * spx), index=model.index)
    series = {"Model only": model, "Your setup (50/50 + 6-month switch)": setup}
    if fresh:
        periods = [("Fresh years", None, None)]
    else:
        u = pd.Timestamp(unseen_from)
        periods = [("Built on (to 2022)", model.index[0], u), ("Held out (2023 on)", u, model.index[-1] + pd.Timedelta(days=1)),
                   ("Whole history", model.index[0], model.index[-1] + pd.Timedelta(days=1))]

    # ---- 1. is the edge real?
    st.markdown("**1. Does it beat the S&P 500?** Paired t-test: the model and the S&P are measured over the same "
                "4-week rounds, starting from 'no difference'.")
    rows, tests = stats_edge_rows(series, spx, periods)
    _stats_light_table(rows)
    main = tests.get((periods[1][0] if len(periods) > 1 else periods[0][0], "Model only"))
    if main:
        st.markdown(f"**Plain English (held-out years):** {main['light']} {main['verdict']}")
    st.caption("🟢 evidence of an edge · 🟠 not enough data, or real but too small to matter · 🔴 no evidence. "
               "'Smallest edge it could spot' = with this many rounds, a true edge would need to be about this big for "
               "the test to catch it 80% of the time. If that's larger than the edge you're hoping for, a 'no' could "
               "just be too little data (a Type II error).")

    # ---- 2. how sure is each number?
    st.markdown("**2. How sure is each number?** 95% ranges beside every average.")
    t_all = tests[(periods[-1][0], "Model only")]
    rm, rb = t_all["rounds_m"], t_all["rounds_b"]
    SP = R.get("signal_points")
    rows = [{"Number": "Model: average 4-week round", "Value (95% range) · n": stats.fmt_ci(stats.mean_ci(rm))},
            {"Number": "S&P 500: average 4-week round", "Value (95% range) · n": stats.fmt_ci(stats.mean_ci(rb))},
            {"Number": "Rounds the model made money", "Value (95% range) · n": stats.fmt_rate(t_all["win"])},
            {"Number": "Rounds the model beat the S&P", "Value (95% range) · n": stats.fmt_rate(t_all["beat"])}]
    for s in workshop.MODEL_SIDES:
        if s in R["strategies_weekly"]:
            rows.append({"Number": f"Strategy: {s} (average round)",
                         "Value (95% range) · n": stats.fmt_ci(stats.mean_ci(stats.rounds(R["strategies_weekly"][s])))})
    if SP is not None and not SP.empty:
        pk = SP[SP["picked"]]["next 4 weeks %"]
        rows += [{"Number": "Each pick: next 4 weeks (before costs and stops)", "Value (95% range) · n": stats.fmt_ci(stats.mean_ci(pk))},
                 {"Number": "Picks that went up", "Value (95% range) · n": stats.fmt_rate(stats.proportion_ci(int((pk > 0).sum()), len(pk)))},
                 {"Number": "Average winning pick", "Value (95% range) · n": stats.fmt_ci(stats.mean_ci(pk[pk > 0]))},
                 {"Number": "Average losing pick", "Value (95% range) · n": stats.fmt_ci(stats.mean_ci(pk[pk <= 0]))}]
    _stats_light_table(rows)
    st.caption("⚠ under 30 = too few to trust the number much. Win rates use the interval for a proportion (Wilson).")

    if SP is None or SP.empty:
        return
    # ---- 3. correlation
    st.markdown(f"**3. Does each signal line up with what happens next?** Correlation (r) between each signal at a "
                f"Friday and that commodity's next 4 weeks. {_stats_info('correlation')}", unsafe_allow_html=True)
    sigs = ["12-1 momentum", "Closeness to 52-week high", "12-month trend", "Monte Carlo expected move", "Volatility vs normal"]
    cut = pd.Timestamp(unseen_from)
    rows = []
    for s in sigs:
        c_b = stats.corr_test(SP[SP.date < cut][s], SP[SP.date < cut]["next 4 weeks %"]) if not fresh else None
        c_u = stats.corr_test(SP[SP.date >= cut][s], SP[SP.date >= cut]["next 4 weeks %"]) if not fresh else \
            stats.corr_test(SP[s], SP["next 4 weeks %"])
        def cell(c):
            if c is None or c["r"] != c["r"]:
                return "–"
            return f"r = {c['r']:+.3f} ({c['strength']} {c['direction']}), p = {stats.fmt_p(c['p'])}, n = {c['n']}"
        light = stats.light_p(c_u["p"], c_u["r"] > 0 if s != "Volatility vs normal" else True, c_u["n"])
        rows.append({"": light, "Signal": s, ("Fresh years" if fresh else "Built on (to 2022)"): cell(c_u if fresh else c_b),
                     **({} if fresh else {"Held out (2023 on)": cell(c_u)})})
    _stats_light_table(rows)
    tabs = st.tabs(sigs)
    for tab, s in zip(tabs, sigs):
        with tab:
            d = SP[[s, "next 4 weeks %", "date"]].dropna()
            d = d[(d[s].abs() < d[s].abs().quantile(0.995))]
            fig = go.Figure()
            for lab, m_, col in (("Built on", d.date < cut, ui.DIM), ("Held out", d.date >= cut, ui.ACCENT)):
                if fresh and lab == "Built on":
                    continue
                dd_ = d[m_] if not fresh else d
                fig.add_scatter(x=dd_[s], y=dd_["next 4 weeks %"], mode="markers", name=lab if not fresh else "Fresh years",
                                marker=dict(size=4, color=col, opacity=0.5))
            if len(d) > 3:
                k, b0 = np.polyfit(d[s], d["next 4 weeks %"], 1)
                xs = np.linspace(d[s].min(), d[s].max(), 20)
                fig.add_scatter(x=xs, y=k * xs + b0, mode="lines", name="best-fit line", line=dict(color=ui.UP, width=2))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor=ui.BG, plot_bgcolor=ui.BG,
                              font=dict(color=ui.TEXT), xaxis_title=s, yaxis_title="next 4 weeks %",
                              legend=dict(orientation="h", y=1.12))
            st.plotly_chart(fig, config=ui.PLOT_CONFIG, key=f"{key}_sc_{s}")
    st.caption("Correlation doesn't prove causation. The obvious thing driving both: the whole commodity market. When the "
               "dollar falls or the world economy picks up, most commodities rise together, so momentum and the next 4 "
               "weeks can both be up for the same outside reason. Small r values are normal for trading signals: an r of "
               "0.05–0.10 that holds on held-out years can still be worth money.")

    # ---- 4. two groups
    st.markdown(f"**4. Does a signal split good times from bad?** Average next 4 weeks when the signal is ON vs OFF "
                f"(independent samples t-test). {_stats_info('independent samples t-test')}", unsafe_allow_html=True)
    test_sp = SP if fresh else SP[SP.date >= cut]
    groups = [("The model picked it", test_sp["picked"]),
              ("Momentum in the top 20%", test_sp["12-1 momentum"] >= test_sp.groupby("date")["12-1 momentum"].transform(lambda x: x.quantile(0.8))),
              ("12-month trend up", test_sp["12-month trend"] > 0),
              ("Within 5% of its 52-week high", test_sp["Closeness to 52-week high"] >= 0.95),
              ("Calm (volatility normal)", test_sp["Volatility vs normal"] <= 1.5)]
    rows = []
    for name, on in groups:
        on = on.fillna(False).astype(bool)
        w = stats.welch_test(test_sp.loc[on, "next 4 weeks %"], test_sp.loc[~on, "next 4 weeks %"])
        ok = w["diff"] > 0 if w["diff"] == w["diff"] else False
        light = stats.light_p(w["p"], ok, min(w["n_on"], w["n_off"]))
        rows.append({"": light, "Signal ON means": name, "ON: avg next 4 weeks": f"{w['mean_on']:+.2f}% (n={w['n_on']})",
                     "OFF: avg next 4 weeks": f"{w['mean_off']:+.2f}% (n={w['n_off']})",
                     "Difference (95% range)": "–" if w["diff"] != w["diff"] else f"{w['diff']:+.2f} ({w['lo']:+.2f} to {w['hi']:+.2f})",
                     "p-value": stats.fmt_p(w["p"])})
    # the pause and switch rules: what the model did in the weeks each rule was on vs off
    shadow = R.get("shadow")
    if shadow is not None:
        pz = R["pause"]["on"].reindex(shadow.index).fillna(True)
        rr = stats.rounds(shadow)
        on_ = pz.reindex(rr.index).fillna(True).astype(bool)
        w = stats.welch_test(rr[~on_], rr[on_])
        rows.append({"": stats.light_p(w["p"], (w["diff"] < 0) if w["diff"] == w["diff"] else False, min(w["n_on"], w["n_off"])),
                     "Signal ON means": "Pause rule ON (model would have traded)",
                     "ON: avg next 4 weeks": f"{w['mean_on']:+.2f}% (n={w['n_on']})",
                     "OFF: avg next 4 weeks": f"{w['mean_off']:+.2f}% (n={w['n_off']})",
                     "Difference (95% range)": "–" if w["diff"] != w["diff"] else f"{w['diff']:+.2f} ({w['lo']:+.2f} to {w['hi']:+.2f})",
                     "p-value": stats.fmt_p(w["p"])})
    _stats_light_table(rows)
    st.caption(("Fresh years only." if fresh else "Held-out years only (2023 on), so nothing here was used to build the rules.")
               + " For the pause rule, 🟢 would mean the model really did worse during paused rounds.")

    # ---- 5. the two ways of being wrong
    ideas = stats.load_ideas(IDEA_BASE)
    st.markdown(f"**5. The two ways of being wrong** {_stats_info('Type I error')} {_stats_info('Type II error')}",
                unsafe_allow_html=True)
    st.markdown(f"- **Type I (trading a dud):** {stats.luck_line(len(ideas))} The full list is on TEST → Idea log.\n"
                f"- **Type II (binning a good idea):** see 'Smallest edge it could spot' above. With ~{t_all['n']} rounds, "
                f"only an edge of about {t_all['mde_year']:.0f}% a year or more would reliably show up. A smaller real edge "
                "could pass unnoticed, so 'no evidence' is not the same as 'proof it doesn't work'.\n"
                f"- **Significant but too small:** an edge under {stats.MATTERS_PCT_YEAR:.0f}% a year is flagged 🟠 even if "
                "the test passes, because spreads, overnight fees and tax can eat it.")


def bubble_stats(S, nas, score, signs, step=13):
    """Bubble Watch stats: what the Nasdaq did over the next 3 months after each band and each sign's lights.
    Readings are taken every 13 weeks so the 3-month windows don't overlap."""
    w = nas.resample("W-FRI").last().reindex(score.index).ffill()
    fwd3 = (w.shift(-13) / w - 1) * 100
    fwd12 = (w.shift(-52) / w - 1) * 100
    ok = score["available"] >= 25
    idx = score.index[ok][::step]
    out = {}
    rows = []
    for lo, hi, nm, _ in bubble.BANDS:
        m = [d for d in idx if lo <= score.at[d, "pct"] < hi]
        c = stats.mean_ci(fwd3.reindex(m))
        rows.append(dict(band=nm, ci=c))
    out["bands"] = rows
    hot = [d for d in idx if score.at[d, "pct"] >= 30]
    cold = [d for d in idx if score.at[d, "pct"] < 30]
    out["hot_vs_cold"] = stats.welch_test(fwd3.reindex(hot), fwd3.reindex(cold))
    out["corr3"] = stats.corr_test(score["pct"].reindex(idx), fwd3.reindex(idx))
    idx52 = score.index[ok][::52]
    out["corr12"] = stats.corr_test(score["pct"].reindex(idx52), fwd12.reindex(idx52))
    out["scatter"] = pd.DataFrame({"score": score["pct"].reindex(idx), "next3": fwd3.reindex(idx)}).dropna()
    srows = []
    for s in signs:
        st_ = s["status"].reindex(idx)
        g, r = fwd3.reindex(idx)[st_ == 2], fwd3.reindex(idx)[st_ == 0]
        srows.append(dict(id=s["id"], name=s["name"], stage=s["stage"], test=stats.welch_test(g, r)))
    out["signs"] = srows
    return out


def bubble_stats_section(BS):
    st.markdown("### 7. Stats check: does the score really warn of falls?")
    st.markdown("What the Nasdaq did over the **next 3 months** after past readings. Readings are taken every 13 weeks so "
                f"the windows don't overlap. {_stats_info('confidence interval')} {_stats_info('independent samples t-test')}",
                unsafe_allow_html=True)
    rows = [{"Band": b["band"], "Avg next 3 months (95% range) · n": stats.fmt_ci(b["ci"])} for b in BS["bands"]]
    _stats_light_table(rows)
    w = BS["hot_vs_cold"]
    worse = w["diff"] == w["diff"] and w["hi"] < 0
    light = "🟢" if worse and min(w["n_on"], w["n_off"]) >= stats.MIN_N else ("🟠" if min(w["n_on"], w["n_off"]) < stats.MIN_N else "🔴")
    st.markdown(f"**{light} Danger zone or higher vs below it:** next 3 months averaged {w['mean_on']:+.1f}% (n={w['n_on']}) vs "
                f"{w['mean_off']:+.1f}% (n={w['n_off']}). Difference {w['diff']:+.1f} points (95%: {w['lo']:+.1f} to {w['hi']:+.1f}), "
                f"p = {stats.fmt_p(w['p'])}. "
                + ("Evidence that high scores are followed by worse markets." if worse else
                   "No clear evidence yet that high scores are followed by worse 3-month returns."))
    for lab, c in (("next 3 months", BS["corr3"]), ("next 12 months", BS["corr12"])):
        if c["r"] == c["r"]:
            st.markdown(f"- Score vs the Nasdaq's {lab}: r = {c['r']:+.2f} ({c['strength']} {c['direction']}), "
                        f"p = {stats.fmt_p(c['p'])}, n = {c['n']}" + (" ⚠ under 30" if c["small"] else ""))
    d = BS["scatter"]
    if len(d) > 3:
        fig = go.Figure()
        fig.add_scatter(x=d["score"], y=d["next3"], mode="markers", marker=dict(size=7, color=ui.ACCENT, opacity=0.7), name="readings")
        k, b0 = np.polyfit(d["score"], d["next3"], 1)
        xs = np.linspace(d["score"].min(), d["score"].max(), 20)
        fig.add_scatter(x=xs, y=k * xs + b0, mode="lines", name="best-fit line", line=dict(color=ui.DOWN, width=2))
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor=ui.BG, plot_bgcolor=ui.BG,
                          font=dict(color=ui.TEXT), xaxis_title="bubble score %", yaxis_title="Nasdaq next 3 months %",
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, config=ui.PLOT_CONFIG, key="bubble_stats_scatter")
    with st.expander("Each sign: what the Nasdaq did after 🟢 vs 🔴 readings"):
        rows = []
        for s in BS["signs"]:
            t = s["test"]
            if t["n_on"] < 2:
                continue
            worse = t["diff"] == t["diff"] and t["hi"] < 0
            light = "🟠" if min(t["n_on"], t["n_off"]) < stats.MIN_N else ("🟢" if worse else "🔴")
            rows.append({"": light, "Sign": s["name"], "After 🟢": f"{t['mean_on']:+.1f}% (n={t['n_on']})",
                         "After 🔴": f"{t['mean_off']:+.1f}% (n={t['n_off']})",
                         "Difference (95% range)": f"{t['diff']:+.1f} ({t['lo']:+.1f} to {t['hi']:+.1f})", "p-value": stats.fmt_p(t["p"])})
        if rows:
            _stats_light_table(rows)
        st.caption("🟢 = the market really did worse after this sign was green · 🟠 = too few readings to tell (most signs) · "
                   "🔴 = no evidence. With 66 signs tested at 5%, about 3 will look meaningful by luck alone.")
    st.caption("Correlation isn't causation: high scores and falls can both be driven by the same thing (for example the "
               "Fed raising rates). The score is a warning light, not a timer.")


def page_idea_log():
    st.markdown("#### 📒 Idea log")
    ideas = stats.load_ideas(IDEA_BASE)
    st.markdown("Every idea tested on HF Macro, what happened and **why**, so the lesson carries into the next one. "
                f"{_stats_info('Type I error')}", unsafe_allow_html=True)
    st.info(stats.luck_line(len(ideas)))
    kept = sum(1 for i in ideas if i["result"] == "kept")
    st.markdown(f"**{len(ideas)} ideas** · {kept} kept · {sum(1 for i in ideas if i['result'] == 'parked')} parked · "
                f"{sum(1 for i in ideas if i['result'] == 'cut')} cut")
    icon = {"kept": "✅", "parked": "🅿️", "cut": "❌", "testing": "🧪"}
    st.markdown(md_table(pd.DataFrame([{"": icon.get(i["result"], ""), "When": i["date"], "Area": i["area"],
                                        "Idea": f"**{i['idea']}**", "Result": i["result"], "Why / lesson": i["why"]}
                                       for i in reversed(ideas)])))
    with st.expander("➕ Log a new idea"):
        c1, c2 = st.columns(2)
        area = c1.text_input("Area (e.g. Commodities, Bubble, Pairs)", key="il_area")
        res = c2.selectbox("Result", ["testing", "kept", "parked", "cut"], key="il_res")
        idea = st.text_input("The idea", key="il_idea")
        why = st.text_input("Why it might work / why it failed", key="il_why")
        if st.button("Save to the log", key="il_save") and idea.strip():
            ideas.append(dict(date=pd.Timestamp.now().strftime("%Y-%m-%d"), area=area or "Other", idea=idea.strip(),
                              result=res, why=why.strip(), p=None))
            stats.save_ideas(IDEA_BASE, ideas)
            st.success("Saved.")
            st.rerun()



# ================================================================= SMART MONEY (v39, PC version only)

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def smart_cftc_run(day):
    raw = signals._disk_cache("smart_cftc", 72, lambda: smart.cftc_download("2018-01-01"))
    return smart.cftc_table(raw)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def smart_13f_run(day, contact):
    h = signals._disk_cache("smart_13f", 72, lambda: smart.latest_13f(contact))
    return smart.fund_moves(h) if h is not None and not h.empty else ({}, pd.DataFrame())


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def smart_insider_run(day, contact):
    return signals._disk_cache("smart_insiders", 24 * 7, lambda: smart.recent_insider_clusters(contact))


def page_smart():
    if PUBLIC:
        st.info("Smart Money is only available in the PC version.")
        return
    st.markdown(look.page_header("Models · PC only", "Smart Money"), unsafe_allow_html=True)
    st.caption("What the big players are doing, from free official sources: the CFTC's weekly positions report, the SEC "
               "filings of 16 star stock-pickers, and directors buying their own company's shares. Each idea was tested "
               "before this page was built. Not financial advice.")
    st.markdown("**The tests in one line:** " + smart.HEADLINE)
    day = pd.Timestamp.now().strftime("%Y-%m-%d")

    # ---------------- 1. commodity positioning
    st.markdown("### 1. Who's betting on each commodity (CFTC, weekly)")
    st.caption("Hedge funds = 'managed money'. Producers = companies that make or use the commodity (oil firms, farmers, "
               "food makers), who mostly hedge. Net position = longs minus shorts, as a % of all open contracts. "
               "'vs 3 years' = where today sits in its own last 3 years (100% = the most long it's been).")
    try:
        ct = smart_cftc_run(day)
    except Exception as exc:
        ct = pd.DataFrame()
        st.warning(f"Couldn't load the CFTC report ({type(exc).__name__}). Check your internet and reload.")
    if not ct.empty:
        rows = [{"Commodity": r["name"], "Hedge funds net": f"{r['hf_net']:+.0f}%",
                 "vs 3 years": f"{r['hf_pct']:.0f}%", "Change in 4 weeks": f"{r['hf_chg4']:+.1f} pts",
                 "Producers net": "–" if r["prod_net"] != r["prod_net"] else f"{r['prod_net']:+.0f}%",
                 "Reading": r["flag"]} for _, r in ct.sort_values("hf_z", ascending=False).iterrows()]
        st.markdown(md_table(pd.DataFrame(rows)))
        st.caption(f"Positions as of {pd.Timestamp(ct['asof'].max()):%a %d %b %Y} (published the following Friday). "
                   "🔥/🧊 = more than 2 'normal wobbles' from the 3-year average. **Information only:** the tests found "
                   "following, fading or filtering on these doesn't improve your commodity trades (section 4).")

    # ---------------- SEC contact
    contact = setting_get("sec_contact", "")
    if "@" not in str(contact):
        st.markdown("### 2. Star funds and 3. Insiders")
        st.info("The SEC asks everyone who downloads its filings to include a contact email. Type yours once; it's "
                "saved only in this PC's settings file and sent only to the SEC with each request.")
        c = st.text_input("Your email for SEC requests", key="sm_contact")
        if st.button("Save", key="sm_save") and "@" in c:
            setting_set("sec_contact", c.strip())
            st.rerun()
    else:
        # ---------------- 2. funds
        st.markdown("### 2. What the star stock-pickers bought and sold (SEC 13F)")
        st.caption("Funds managing over $100m must file their US share holdings each quarter, up to 45 days after the "
                   "quarter ends. So this is what they held weeks ago, long positions only (no shorts, bonds or currencies).")
        try:
            with ui.loading("Reading SEC 13F filings", scene="filings", once="smart"):
                funds, crowd = smart_13f_run(day, contact)
        except Exception as exc:
            funds, crowd = {}, pd.DataFrame()
            st.warning(f"Couldn't load the SEC filings ({type(exc).__name__}).")
        if crowd is not None and not crowd.empty:
            st.markdown("**Bought or added by 2+ of these funds last quarter:**")
            st.markdown(md_table(pd.DataFrame([{"Company": r["issuer"], "Funds": len(r["fund"]),
                                                "Who": ", ".join(r["fund"])} for _, r in crowd.head(12).iterrows()])))
        for fund, f in funds.items():
            with st.expander(f"{fund} ({smart.FUND_PEOPLE.get(fund, '')}) · quarter to {f['period']} · filed {f['filed']}"):
                def tbl(d, label):
                    if d is None or d.empty:
                        return f"*{label}: none*"
                    return f"**{label}:** " + ", ".join(f"{r['issuer']} ({r['weight']:.1f}%)" for _, r in d.iterrows())
                st.markdown("\n\n".join([tbl(f["top"], "Biggest holdings"), tbl(f["new"], "New buys"),
                                         tbl(f["added"], "Added to"), tbl(f["sold"], "Sold completely")]))
        # ---------------- 3. insiders
        st.markdown("### 3. Directors buying their own company's shares (SEC Form 4)")
        st.caption("Cluster buys: 2+ insiders (at least one director or officer) buying on the open market with their own "
                   "money, $100k+ in total, within 45 days. From the SEC's quarterly bulk files, so the newest data can be "
                   "a few months old.")
        try:
            with ui.loading("Reading SEC insider filings", scene="filings"):
                ins, asof = smart_insider_run(day, contact)
        except Exception as exc:
            ins, asof = pd.DataFrame(), None
            st.warning(f"Couldn't load the SEC insider files ({type(exc).__name__}).")
        if ins is not None and not ins.empty:
            st.markdown(md_table(pd.DataFrame([{"Company": f"{r['ISSUERNAME']} ({str(r['ISSUERTRADINGSYMBOL']).upper()})",
                                                "Insiders buying": int(r["insiders"]), "Total bought": _gbp(r["value"]).replace("£", "$"),
                                                "Last filing": f"{r['last']:%d %b %Y}"} for _, r in ins.head(15).iterrows()])))
            st.caption(f"Newest filing in the SEC files: {pd.Timestamp(asof):%d %b %Y}.")
        ui.section("Money river", "every executive and director purchase, flowing into the company it was made in", code="★")
        _sd = look.snapshot_dates()
        components.html(look.river_html(CONSENT == "a"), height=620)
        st.caption(f"Real SEC Form 4 open-market purchases by executives and directors filed {_sd['river_from']} to {_sd['river_to']} "
                   "(a saved snapshot of the latest full quarter in your Smart Money data), top 10 companies by money in. Each particle "
                   "stream is one purchase; thicker ribbons carried more money. Information only, not financial advice.")

    # ---------------- 4. tests
    st.markdown("### 4. Do any of these make money? (tested before building this page)")
    st.caption("Rules fixed before testing, built on early years, checked on later years the test never saw, Trading 212 "
               "costs included, compared with the S&P 500 (paired t-test, 95% range).")
    st.markdown(md_table(pd.DataFrame([{"": t["light"], "Idea": f"**{t['idea']}**", "Build years": t["build"],
                                        "Held-out years": t["held"], "Verdict": t["verdict"], "Why": t["why"]}
                                       for t in smart.TESTS + smart.TESTS_PENDING])))
    st.markdown("### 5. Honest warnings")
    st.markdown(
        "- **Everything here is public and late.** CFTC positions are 3 days old when published, fund filings up to 45 days, "
        "and the insider bulk files months. Big players have usually moved by the time we see it.\n"
        "- **Fund filings miss most of the picture:** no shorts, no bonds, no currencies, no options direction. A holding "
        "can be a hedge rather than a bet. Big banks' filings are mostly client and market-making positions, which is why "
        "they're not listed.\n"
        "- **Shares of companies that went bust or were bought out** are missing from Yahoo's price history, which flatters "
        "the copy-the-funds and insider tests (more for insiders, who buy lots of small companies).\n"
        "- **Never trade on a tip that isn't public.** Using inside information about a company is a crime in the UK.\n"
        "- Not financial advice.")



# ================================================================= TAKEOVERS (v40, PC version only)

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def to_deals_run(day, contact):
    return signals._disk_cache("to_deals", 12, lambda: takeovers.recent_deals(contact))


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def to_activists_run(day, contact):
    return signals._disk_cache("to_activists", 12, lambda: takeovers.recent_activists(contact))


@st.cache_data(ttl=60 * 60, show_spinner=False)
def to_rumours_run(hour):
    return signals._disk_cache("to_rumours", 1, lambda: takeovers.rumours(signals.get_key("FINNHUB_API_KEY")))


def _to_link(text, url):
    return f"[{text}]({url})" if url else text


def page_takeovers():
    if PUBLIC:
        st.info("Takeovers is only available in the PC version.")
        return
    st.markdown(look.page_header("Models · PC only", "Takeovers"), unsafe_allow_html=True)
    st.caption("Private-equity takeovers and the legal ways to spot them early: official SEC filings and news wires only. "
               "Trading on a public rumour is legal; trading on a tip from someone inside a deal is insider dealing, a crime "
               "in the UK. Not financial advice.")
    st.markdown("**The tests in one line:** " + takeovers.HEADLINE)
    contact = setting_get("sec_contact", "")
    now = pd.Timestamp.now()
    if "@" not in str(contact):
        st.info("The SEC asks everyone who downloads its filings to include a contact email. Type yours once (it's shared "
                "with the Smart Money page and saved only on this PC).")
        c = st.text_input("Your email for SEC requests", key="to_contact")
        if st.button("Save", key="to_save") and "@" in c:
            setting_set("sec_contact", c.strip())
            st.rerun()
    else:
        st.markdown("### 1. New PE takeover filings (last 60 days)")
        st.caption("Official SEC documents that name one of ~50 big private-equity firms. These come days to weeks AFTER the "
                   "deal is announced, so the big jump has usually already happened.")
        try:
            with ui.loading("Reading SEC takeover filings", scene="radar", once="takeovers"):
                dl = to_deals_run(now.strftime("%Y-%m-%d"), contact)
            _dd = scenes.deals_data(dl)
            if _dd:
                look.remember("deals", _dd["deals"])
        except Exception as exc:
            dl = pd.DataFrame()
            st.warning(f"Couldn't load the SEC filings ({type(exc).__name__}).")
        if dl is not None and not dl.empty:
            show_scene("takeovers", scenes.deals_data(dl), 520, "The radar locks on to each company named in a new SEC takeover filing, "
                       "with the private-equity firm and the type of document. The full list is below.")
            st.markdown(md_table(pd.DataFrame([{"Filed": r["filed"], "Company": _to_link(r["company"], r["link"]),
                                                "Document": r["what"], "PE firm named": r["sponsor"]}
                                               for _, r in dl.head(30).iterrows()])))
        elif dl is not None:
            st.caption("No matching filings in the last 60 days.")
        st.markdown("### 2. Activist watch: funds pushing for a sale (SEC 13D, last 90 days)")
        st.caption("A fund that buys 5%+ of a company must file a 13D within 10 days. These ones mention 'strategic "
                   "alternatives' or a 'sale of the company'. **Tested:** such companies were 5-7x more likely to be taken "
                   "private within 2 years (12% vs 1.7%), but buying them all still lagged the S&P (section 4).")
        try:
            ac = to_activists_run(now.strftime("%Y-%m-%d"), contact)
        except Exception as exc:
            ac = pd.DataFrame()
            st.warning(f"Couldn't load the 13D filings ({type(exc).__name__}).")
        if ac is not None and not ac.empty:
            st.markdown(md_table(pd.DataFrame([{"Filed": r["filed"], "Company": _to_link(r["company"], r["link"]),
                                                "Filed by": r["fund"], "Mentions": r["phrase"]}
                                               for _, r in ac.head(30).iterrows()])))
    st.markdown("### 3. Takeover rumours in the news")
    st.caption("Headlines from news wires (Finnhub's merger news) with words like 'explores sale', 'takeover approach' or "
               "'people familiar'. ✅ = Reuters, Bloomberg, FT, WSJ and similar. **Not tested** (no free history of headlines).")
    try:
        rm = to_rumours_run(now.strftime("%Y-%m-%d %H"))
    except Exception as exc:
        rm = pd.DataFrame()
        st.warning(f"Couldn't load the news ({type(exc).__name__}).")
    if rm is not None and not rm.empty:
        st.markdown(md_table(pd.DataFrame([{"When": f"{r['date']:%d %b %H:%M}", "": "✅" if r["trusted"] else "",
                                            "Headline": _to_link(r["headline"], r["link"]), "Source": r["source"],
                                            "Tickers": r["tickers"]} for _, r in rm.iterrows()])))
    elif rm is not None:
        st.caption("No takeover-rumour headlines right now (or no Finnhub key in secrets.toml).")
    st.markdown("### 4. What the tests found")
    st.caption("Built on early years, checked on later years, costs included, compared with the S&P 500.")
    st.markdown(md_table(pd.DataFrame([{"": t["light"], "Idea": f"**{t['idea']}**", "Result": t["result"], "Why": t["why"]}
                                       for t in takeovers.TESTS])))
    st.markdown("### 5. Honest warnings")
    st.markdown(
        "- **The jump happens at the announcement** (usually +20-40% in a day). Filings and most news arrive after it.\n"
        "- **Most activist targets are never sold**, and failed deals can drop 20-30% in a day.\n"
        "- **Rumours on social media** are often wrong, and some are deliberate pump-and-dumps.\n"
        "- **Yahoo deletes companies once they're bought out**, so price tests of 'buy the targets' miss the winners.\n"
        "- Not financial advice.")



# ================================================================= EVENT LAB (v41, PC version only)

def page_eventlab():
    if PUBLIC:
        st.info("Event Lab is only available in the PC version.")
        return
    st.markdown(look.page_header("Models · PC only", "Event Lab"), unsafe_allow_html=True)
    st.caption("Ideas copied from published research and company events, tested in big batches the honest way: rules set "
               "on early years, then checked on years they never saw, after costs, against the S&P 500 and a small-company "
               "index. Not financial advice.")
    st.markdown("**In one line:** " + eventlab.HEADLINE)
    show_scene("graveyard", scenes.eventlab_data(eventlab.PUBLISHED), 600, f"Every one of the {eventlab.PUBLISHED['total']} published strategies "
               f"in the Open Asset Pricing test drops in, then the {eventlab.PUBLISHED['after']} that kept working after they were published light up.")
    st.markdown("### 1. Finished tests")
    st.markdown(md_table(pd.DataFrame([{"": r[0], "Group": r[1], "Idea": f"**{r[2]}**", "Build years": r[3],
                                        "Years it never saw": r[4], "Why": r[5]} for r in eventlab.RESULTS])))
    st.caption("🟢 evidence of an edge on both periods · 🟠 positive but not proven · 🔴 no evidence. Every test is also in the Idea log.")
    st.markdown("### 2. Built and waiting for data")
    st.caption("The tests are written and checked; they run as soon as the price data that includes bought-out and delisted "
               "companies arrives (EODHD). Without it, every stock test is missing the winners that got bought out.")
    st.markdown(md_table(pd.DataFrame([{"Idea": f"**{w[0]}**", "Trade": w[1], "Needs": w[2]} for w in eventlab.WAITING])))
    p = eventlab.PUBLISHED
    st.markdown("### 3. Which published strategies still work?")
    st.markdown(f"Of **{p['total']}** published stock strategies (Open Source Asset Pricing, Federal Reserve economists), "
                f"**{p['after']}** kept working after they were published and **{p['since2015']}** still work since 2015. "
                f"Average return fell from **+{p['before_avg']}%** a year before publication to **+{p['after_avg']}%** after - "
                "once everyone knows, the edge shrinks.")
    st.markdown(md_table(pd.DataFrame([{"Theme of the survivors": t[0], "Strategies": t[1], "What it means for us": t[2]}
                                       for t in p["themes"]])))
    st.caption("Academic long-short figures before costs, mostly on tiny companies - our own versions must be tested on "
               "bigger companies after costs.")
    st.markdown("### 4. Crash insurance (for Bubble Watch)")
    st.markdown(eventlab.CRASH_SWITCH)
    st.markdown("### 5. Honest warnings")
    st.markdown("- Testing many ideas means about 1 in 20 looks good on one period by pure luck - that's why both periods must pass.\n"
                "- Strategies that worked in the past fade once they are published and traded by big funds.\n"
                "- Results include costs, but real fills on small companies can be worse.\n"
                "- Not financial advice.")


# ================================================================= v41: show-off visuals that draw real data

WEB_MARKETS = {"ftse100": ("FTSE 100", "Stocks"), "sp500": ("S&P 500", "Stocks"), "nasdaq": ("Nasdaq", "Stocks"), "dax": ("DAX", "Stocks"),
               "nikkei": ("Nikkei", "Stocks"), "brent": ("Brent", "Commodities"), "wti": ("WTI", "Commodities"),
               "natgas": ("Nat gas", "Commodities"), "gold": ("Gold", "Commodities"), "copper": ("Copper", "Commodities"),
               "btc": ("Bitcoin", "Crypto"), "eth": ("Ethereum", "Crypto"), "gbpusd": ("GBP/USD", "Currencies"),
               "eurusd": ("EUR/USD", "Currencies"), "usdjpy": ("USD/JPY", "Currencies"), "audusd": ("AUD/USD", "Currencies"),
               "usdcad": ("USD/CAD", "Currencies"), "dxy": ("Dollar index", "Currencies")}


def market_web_section():
    import streamlit.components.v1 as components
    ser = {}
    for i in WEB_MARKETS:
        if i in LOADED:
            s_ = LOADED[i][1].get("series")
            if s_ is not None and len(s_) > 60: ser[i] = s_
    if len(ser) < 5:
        return
    df = pd.DataFrame(ser).sort_index().resample("W-FRI").last().pct_change(fill_method=None).iloc[-52:] * 100
    df = df.loc[:, df.notna().sum() >= 40]
    if df.shape[1] < 5:
        return
    ui.section("Market web", "which markets move together · last 52 weeks · click any point", code="★")
    links = {i: ui.link(LOADED[i][0]["ticker"], page="MKT") for i in df.columns}
    components.html(fx.market_web(df, {i: WEB_MARKETS[i][0] for i in df.columns}, {i: WEB_MARKETS[i][1] for i in df.columns}, links),
                    height=610)
    st.caption("Each thread joins two markets whose weekly moves were closely linked over the last year (green = move the same "
               "way, red = opposite ways, thicker = stronger; only links of 0.45 or more are drawn). The spider walks the strongest "
               "links and tags each stop with its closest partner. Hover a thread or point for the number.")

# ================================================================= router

if not TICKER and not CCY:
    page_guide(PAGE)
if TICKER:
    page_detail(TICKER)
elif CCY:
    page_currency(CCY)
elif PAGE == "HOME":
    page_home()
elif PAGE == "US":
    region_page("US", "The US economy.")
elif PAGE == "UK":
    region_page("UK", "The UK economy.")
elif PAGE == "EA":
    region_page("EA", "The euro area economy (ECB data).")
elif PAGE == "MKT":
    world_day()
    region_page("Markets", "Key indices, volatility and commodities with full history.")
    market_web_section()
elif PAGE == "WEI":
    page_wei()
elif PAGE == "CMDTY":
    page_cmdty()
elif PAGE == "CRYPTO":
    page_crypto()
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
elif PAGE == "LEGAL":
    page_legal()
elif PAGE == "LEARN":
    page_learn()
elif PAGE == "ALAB":
    page_assetlab()
elif PAGE == "BUBBLE":
    page_bubble()
elif PAGE == "SMART":
    page_smart()
elif PAGE == "TAKEOVERS":
    page_takeovers()
elif PAGE == "EVENTLAB":
    page_eventlab()

ui.status_bar(SOURCE_HEALTH, f"{sum(1 for _, r in LOADED.values() if r['error'] is None)}/"
                             f"{len(LOADED)} SERIES · CACHE 6H" + (" · PUBLIC EDITION" if PUBLIC else ""))
st.caption("Personal educational project. " + ui.DISCLAIMER + " Sources: FRED (Federal Reserve "
           "Bank of St. Louis; this product uses the FRED® API but is not endorsed or certified by "
           "it) · ONS (Open Government Licence v3.0) · Bank of England · ECB · BIS · IMF · ECB rates "
           "via Frankfurter · Yahoo Finance · Google News and public RSS feeds (headlines and links "
           "only). Not affiliated with Bloomberg L.P. · Built by Hamish Finlayson.")
ui.legal_footer()
