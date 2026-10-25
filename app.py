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
                   layout="wide", initial_sidebar_state="collapsed")

# Online (public) version hides series whose owners don't allow free republishing.
PUBLIC = public_mode()
ACTIVE = [i for i in INDICATORS if not (PUBLIC and i["id"] in RESTRICTED_IDS)]


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

c_brand, c_cmd, c_clock = st.columns([1.25, 3.4, 1.1])
c_brand.markdown("<div class='brand'><span class='logo'>HF</span>MACRO<small>HFM &lt;GO&gt;</small></div>",
                 unsafe_allow_html=True)
c_cmd.selectbox("Command", list(COMMANDS), index=None, key="cmd", on_change=on_command,
                placeholder="▸ ENTER COMMAND · ticker (UKCPI, GBPUSD, BRENT), currency (USD, GBP), "
                            "page (WEI, NEWS) or keyword (inflation, gilt)",
                label_visibility="collapsed")
clock_text = f"{datetime.now():%a %d %b %Y %H:%M}".upper()
c_clock.markdown("<div class='clock' title='Data is cached for up to 6 hours and may be delayed'>"
                 "<span class='live'>●</span> DELAYED DATA &nbsp;" + clock_text + "</div>",
                 unsafe_allow_html=True)
ui.ticker_tape(TAPE)
st.segmented_control("Pages", list(PAGES), format_func=lambda c: PAGES[c][0].upper(), key="nav",
                     on_change=on_nav, label_visibility="collapsed")
ui.disclaimer_bar(legal.DISCLAIMER_SHORT)
ui.keyboard_shortcuts()
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
        ui.panel_title("Top headlines", "RSS FEEDS")
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
        with st.spinner("Testing each model on the last 10 years..."):
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
    with st.spinner("Backtesting every forecast (first time takes a minute)..."):
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


def page_wei():
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
            table = fetch_imf(code, years)
            imf[code] = table.loc[iso].dropna()
            imf[code].attrs["source"] = table.attrs.get("source", "IMF")
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
    region_page("Markets", "Key indices, volatility and commodities with full history.")
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

ui.status_bar(SOURCE_HEALTH, f"{sum(1 for _, r in LOADED.values() if r['error'] is None)}/"
                             f"{len(LOADED)} SERIES · CACHE 6H" + (" · PUBLIC EDITION" if PUBLIC else ""))
st.caption("Personal educational project. " + ui.DISCLAIMER + " Sources: FRED (Federal Reserve "
           "Bank of St. Louis; this product uses the FRED® API but is not endorsed or certified by "
           "it) · ONS (Open Government Licence v3.0) · Bank of England · ECB · BIS · IMF · ECB rates "
           "via Frankfurter · Yahoo Finance · Google News and public RSS feeds (headlines and links "
           "only). Not affiliated with Bloomberg L.P. · Built by Hamish Finlayson.")
ui.legal_footer()
