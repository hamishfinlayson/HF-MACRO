"""
ui.py - the look of the dashboard: colours, styles, cards, charts and tables.
app.py decides WHAT goes on each page; this file decides HOW it looks.

Design: professional terminal style (think Bloomberg / Refinitiv / Oracle):
black background, square panels with thin borders, amber headings,
condensed uppercase labels and monospaced numbers.
"""

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from glossary import lookup
from indicators import EVENTS, MARKET_FORECASTS

# Shared with app.py (filled in once data has loaded)
DATA = {"loaded": {}, "forecasts": {}, "go_to": None}

# ---------------------------------------------------------------- palette
BG, PANEL, PANEL_2, BORDER = "#000000", "#0A0D11", "#11161C", "#1C232B"
TEXT, MUTED, DIM = "#D9DEE3", "#8A96A3", "#55606C"
ACCENT = "#E8212B"            # HF Macro red
CYAN = "#3FB6FF"
UP, DOWN = "#2ECC71", "#FF6B6B"
GRID = "#12171D"
SERIES_COLOURS = [CYAN, "#C792EA", "#5EE6C9"]
MONO = "IBM Plex Mono, Consolas, monospace"
SANS = "IBM Plex Sans Condensed, IBM Plex Sans, Arial Narrow, sans-serif"

PLOT_CONFIG = {
    "displaylogo": False, "scrollZoom": True, "displayModeBar": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "zoomIn2d", "zoomOut2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "hf-macro-chart"},
}
DRAW_CONFIG = {**PLOT_CONFIG, "modeBarButtonsToAdd": [
    "drawline", "drawopenpath", "drawrect", "drawcircle", "eraseshape"]}

DISCLAIMER = ("Forecasts are simple statistical projections for educational purposes only. "
              "They are not financial advice and should not be relied on for any decision.")


def inject_css():
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
.stApp {{ background: {BG}; }}
.stApp, .stMarkdown, .stCaption, label, input, textarea, button p, [data-baseweb="select"] div,
[data-testid="stMetricLabel"], [data-testid="stTable"], .stDataFrame {{
    font-family: {SANS} !important; }}
.block-container {{ padding: .6rem 1.2rem 3.2rem; max-width: 100%; }}
header[data-testid="stHeader"] {{ display: none; }}
p, li {{ font-size: .86rem; }}
h4 {{ font-family: {SANS}; font-weight: 600; text-transform: uppercase; letter-spacing: .08em;
      font-size: .9rem !important; color: {ACCENT}; }}
/* panels: square, thin, dark */
[data-testid="stVerticalBlockBorderWrapper"], div[class*="st-key-card_"] {{
    background: {PANEL}; border: 1px solid {BORDER} !important; border-radius: 1px !important; }}
/* widgets */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextInput input {{
    background: {PANEL} !important; border-radius: 1px !important; border-color: {BORDER} !important;
    font-size: .8rem !important; min-height: 32px; }}
.stButton button, .stDownloadButton button {{ border-radius: 1px; border: 1px solid {BORDER};
    background: {PANEL_2}; font-family: {MONO} !important; font-size: .74rem; text-transform: uppercase;
    letter-spacing: .04em; min-height: 30px; padding: 2px 10px; }}
.stButton button:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
[data-testid="stButtonGroup"] button {{ border-radius: 1px !important; font-family: {MONO} !important;
    font-size: .72rem !important; letter-spacing: .05em; padding: 3px 10px !important;
    min-height: 26px !important; }}
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {{
    background: {ACCENT} !important; color: #000 !important; border-color: {ACCENT} !important; }}
label p, [data-testid="stWidgetLabel"] p {{ font-size: .68rem !important; color: {MUTED} !important;
    text-transform: uppercase; letter-spacing: .07em; }}
[data-testid="stMetricValue"] {{ font-family: {MONO} !important; font-size: 1.15rem !important; }}
[data-testid="stMetricLabel"] p {{ font-size: .66rem !important; text-transform: uppercase;
    letter-spacing: .07em; color: {MUTED}; }}
[data-testid="stExpander"] details {{ border-radius: 1px; border-color: {BORDER}; }}
[data-testid="stTabs"] button p {{ font-family: {MONO} !important; font-size: .74rem;
    text-transform: uppercase; letter-spacing: .05em; }}
.stCaption, [data-testid="stCaptionContainer"] p {{ color: {DIM} !important; font-size: .72rem !important; }}
/* clickable cards: the whole card is a button */
div[class*="st-key-card_"] {{ position: relative; padding: 8px 10px 4px !important; gap: 0 !important;
    min-height: 118px; transition: border-color .12s; }}
div[class*="st-key-card_"]:hover {{ border-color: {ACCENT} !important; }}
div[class*="st-key-cbtn_"] {{ position: absolute !important; inset: 0; z-index: 4; margin: 0 !important; }}
div[class*="st-key-cbtn_"] button {{ width: 100%; height: 100%; opacity: 0; cursor: pointer; }}
/* top bar */
.brand {{ font-family: {MONO}; font-weight: 600; font-size: 1.05rem; letter-spacing: .14em;
          color: {ACCENT}; padding-top: .3rem; white-space: nowrap; }}
.brand span {{ color: {TEXT}; }}
.logo {{ background: {ACCENT}; color: #fff; padding: 1px 7px 2px; margin-right: 8px; font-weight: 700; letter-spacing: .04em; }}
.brand small {{ color: {DIM}; font-size: .62rem; letter-spacing: .1em; margin-left: 8px; }}
.clock {{ font-family: {MONO}; color: {MUTED}; font-size: .74rem; text-align: right;
          padding-top: .45rem; white-space: nowrap; }}
.live {{ color: {UP}; }}
/* ticker tape */
.tape {{ overflow: hidden; white-space: nowrap; border-top: 1px solid {BORDER};
         border-bottom: 1px solid {BORDER}; background: {PANEL}; margin: .35rem 0 .4rem; padding: 4px 0; }}
.tape-inner {{ display: inline-block; animation: tape 110s linear infinite; }}
.tape:hover .tape-inner {{ animation-play-state: paused; }}
@keyframes tape {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
.tape a {{ text-decoration: none; margin-right: 26px; font-family: {MONO}; font-size: .74rem; color: {TEXT}; }}
.tape a .tk {{ color: {ACCENT}; margin-right: 6px; }}
/* section headers */
.sec {{ display: flex; align-items: baseline; gap: 12px; margin: .9rem 0 .45rem;
        border-bottom: 1px solid {BORDER}; padding-bottom: 4px; }}
.sec b {{ font-family: {MONO}; color: {ACCENT}; font-size: .72rem; font-weight: 500; }}
.sec h3 {{ margin: 0; padding: 0; font-family: {SANS}; font-size: .86rem; font-weight: 600;
           letter-spacing: .1em; text-transform: uppercase; color: {TEXT}; }}
.sec span {{ color: {DIM}; font-size: .72rem; }}
/* panel titles */
.pt {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
       border-left: 2px solid {ACCENT}; padding: 0 0 0 8px; margin-bottom: 4px; }}
.pt b {{ font-family: {SANS}; font-weight: 600; font-size: .78rem; letter-spacing: .09em;
         text-transform: uppercase; color: {TEXT}; }}
.pt span {{ font-family: {MONO}; font-size: .68rem; color: {DIM}; }}
/* cards */
.k-top {{ display: flex; justify-content: space-between; align-items: baseline; }}
.k-tk {{ font-family: {MONO}; font-size: .7rem; color: {ACCENT}; letter-spacing: .04em; }}
.k-name {{ font-family: {SANS}; font-size: .68rem; color: {MUTED}; text-transform: uppercase;
           letter-spacing: .05em; white-space: normal; line-height: 1.25; }}
.k-val {{ font-family: {MONO}; font-size: 1.3rem; color: {TEXT}; line-height: 1.35; }}
.k-foot {{ display: flex; justify-content: space-between; font-family: {MONO}; font-size: .62rem; color: {DIM}; }}
.up {{ color: {UP}; }} .dn {{ color: {DOWN}; }} .nc {{ color: {MUTED}; }}
.chg {{ font-family: {MONO}; font-size: .72rem; }}
.conf {{ font-family: {MONO}; font-size: .66rem; color: {ACCENT}; letter-spacing: 1px; }}
.conf i {{ font-style: normal; color: #2A323C; }}
.err {{ color: {DOWN}; font-size: .7rem; font-family: {MONO}; }}
/* headline value block */
.hv {{ font-family: {MONO}; font-size: 1.15rem; color: {ACCENT}; }}
.hs {{ font-family: {MONO}; font-size: .68rem; color: {DIM}; }}
/* tables */
table.t {{ width: 100%; border-collapse: collapse; font-size: .76rem; }}
table.t th {{ color: {MUTED}; font-family: {SANS}; font-weight: 500; text-align: left; padding: 4px 6px;
              border-bottom: 1px solid {BORDER}; font-size: .64rem; text-transform: uppercase; letter-spacing: .07em; }}
table.t td {{ padding: 4px 6px; border-bottom: 1px solid {GRID}; color: {TEXT}; font-family: {SANS}; }}
table.t td.n {{ font-family: {MONO}; text-align: right; }}
table.t tr:hover td {{ background: {PANEL_2}; }}
table.t a {{ color: {TEXT}; text-decoration: none; }}
table.t a:hover {{ color: {ACCENT}; }}
.bar {{ height: 6px; background: {PANEL_2}; position: relative; min-width: 80px; border: 1px solid {BORDER}; }}
.bar i {{ position: absolute; top: -4px; width: 2px; height: 12px; }}
.heat {{ font-family: {MONO}; text-align: right; }}
/* news / calendar rows */
.nr {{ display: flex; gap: 10px; padding: 5px 2px; border-bottom: 1px solid {GRID}; align-items: baseline; }}
.nr .t {{ font-family: {MONO}; color: {DIM}; font-size: .68rem; min-width: 44px; }}
.nr .s {{ font-family: {MONO}; color: {ACCENT}; font-size: .64rem; min-width: 104px; max-width: 104px;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-transform: uppercase; }}
.nr a {{ color: {TEXT}; text-decoration: none; font-size: .8rem; font-family: {SANS}; }}
.nr a:hover {{ color: {ACCENT}; }}
.tag {{ font-family: {MONO}; font-size: .58rem; color: {MUTED}; border: 1px solid {BORDER};
        padding: 0 4px; margin-left: 6px; text-transform: uppercase; }}
.disc {{ border: 1px solid #3A1214; background: #130607; padding: 5px 10px; font-size: .7rem;
         color: #D6A9AB; font-family: {SANS}; margin: .2rem 0 .4rem; }}
/* status bar */
.status {{ position: fixed; left: 0; right: 0; bottom: 0; z-index: 999; background: #050607;
           border-top: 1px solid {BORDER}; padding: 3px 14px; font-family: {MONO}; font-size: .64rem;
           color: {DIM}; display: flex; gap: 16px; white-space: nowrap; overflow: hidden; }}
.status b {{ color: {ACCENT}; font-weight: 500; }}
.dot-ok {{ color: {UP}; }} .dot-bad {{ color: {DOWN}; }}
/* (i) info popovers: click to open, click again to close */
details.info {{ display: inline-block; position: relative; z-index: 6; margin-left: 5px;
                vertical-align: 1px; text-transform: none; letter-spacing: 0; }}
details.info summary {{ list-style: none; cursor: pointer; width: 13px; height: 13px; line-height: 11px;
    border: 1px solid #4A5560; border-radius: 50%; text-align: center; font: 600 8.5px {MONO};
    color: {MUTED}; user-select: none; }}
details.info summary::-webkit-details-marker {{ display: none; }}
details.info summary:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
details.info[open] summary {{ background: {ACCENT}; border-color: {ACCENT}; color: #fff; }}
details.info > div {{ position: absolute; top: 18px; left: -10px; width: 270px; z-index: 60;
    background: {PANEL_2}; border: 1px solid {ACCENT}; padding: 8px 10px; font: 400 .76rem/1.45 {SANS};
    color: {TEXT}; white-space: normal; box-shadow: 0 8px 22px rgba(0,0,0,.7); text-align: left; }}
details.info > div b {{ color: {ACCENT}; font-weight: 600; display: block; margin-bottom: 3px;
    font-family: {MONO}; font-size: .68rem; text-transform: uppercase; letter-spacing: .06em; }}
.tv {{ border: 1px solid {BORDER}; }}
a.drv {{ font-family: {MONO}; color: {ACCENT} !important; text-decoration: none; border: 1px solid {BORDER};
         padding: 1px 6px; }}
a.drv:hover {{ border-color: {ACCENT}; background: rgba(232,33,43,.12); }}
table.des {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
table.des td {{ padding: 4px 8px; border-bottom: 1px solid {GRID}; vertical-align: top; }}
table.des td.l {{ color: {ACCENT}; font-family: {SANS}; white-space: nowrap; width: 38%;
                  text-transform: uppercase; letter-spacing: .05em; font-size: .7rem; padding-top: 6px; }}
table.des td.v {{ color: {TEXT}; font-family: {MONO}; }}
.des-head {{ color: {CYAN}; font-family: {MONO}; font-size: .9rem; margin: 2px 0 6px; }}
.des-note {{ color: #E8A33D; font-family: {SANS}; font-size: .84rem; line-height: 1.45; margin: 4px 0 8px; }}
code {{ color: {ACCENT} !important; background: {PANEL_2} !important; border-radius: 1px; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers

def fmt(value, ind, signed=False):
    """Formats a number for display. signed=True is used for changes (adds + and uses pp)."""
    if value is None or pd.isna(value):
        return "-"
    value = round(float(value), ind["decimals"]) + 0.0
    unit = ind["unit"]
    if signed and unit == "%":
        unit = "pp"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:,.{ind['decimals']}f}{unit}"


def is_daily(ind):
    return ind["region"] in ("FX", "Markets", "Crypto") or ind["group"] in ("Rates", "Money & credit", "Markets") \
        or ind["id"] in ("us_claims", "us_mortgage")


def date_label(ind, when):
    return f"{when:%d %b %y}".upper() if is_daily(ind) else f"{when:%b %Y}".upper()


def tone(ind, change):
    """css class for a change: up (good), dn (bad), nc (neutral/no change)."""
    if change is None or pd.isna(change) or round(change, ind["decimals"]) == 0:
        return "nc"
    if ind["good_when"] == "neutral":
        return "up" if change > 0 else "dn"
    return "up" if (change > 0) == (ind["good_when"] == "up") else "dn"


def change_html(ind, change):
    if change is None or pd.isna(change):
        return ""
    arrow = "▲" if change > 0 else "▼" if change < 0 else "■"
    return f"<span class='chg {tone(ind, change)}'>{arrow}{fmt(abs(change), ind, False)}</span>" \
        if ind["unit"] != "%" else \
        f"<span class='chg {tone(ind, change)}'>{arrow}{fmt(abs(change), ind, True).lstrip('+')}</span>"


def conf_html(n, with_info=False):
    """Confidence meter: five blocks, filled = signals agreeing."""
    if n is None:
        return ""
    return (f"<span class='conf'>CONF {'■' * n}<i>{'■' * (5 - n)}</i></span>"
            + (info("confidence", "Confidence") if with_info else ""))


def info(key, title=None):
    """A small (i) icon. Click it to see a plain-English explanation of `key`."""
    text = lookup(key)
    if not text:
        return ""
    label = escape(title or str(key))
    return (f"<details class='info'><summary title='What is this?'>i</summary>"
            f"<div><b>{label}</b>{escape(text)}</div></details>")


def tip(key):
    """The same explanation as plain text, for Streamlit widgets' help= tooltips."""
    return lookup(key) or None


ARROWS = {1: "▲", -1: "▼", 0: "►"}
WORDS = {1: "up", -1: "down", 0: "flat"}


def link(ticker, page=None, view=None):
    page = page or st.query_params.get("p", "HOME")
    return f"?p={page}&t={ticker}" + (f"&v={view}" if view else "")


def section(title, subtitle="", code="", about=None):
    st.markdown(f"<div class='sec'>{f'<b>{code}</b>' if code else ''}<h3>{escape(title)}"
                f"{info(about, title) if about else ''}</h3>"
                f"<span>{escape(subtitle)}</span></div>", unsafe_allow_html=True)


def panel_title(title, meta="", about=None):
    st.markdown(f"<div class='pt'><b>{escape(title)}{info(about, title) if about else ''}</b>"
                f"<span>{escape(meta)}</span></div>", unsafe_allow_html=True)


def window(series, years):
    if years is None or series is None or series.empty:
        return series
    return series[series.index >= series.index[-1] - pd.DateOffset(years=years)]


def day_change(ind, res):
    if res["previous"] is None:
        return None, ""
    if ind["unit"] == "%":
        d = res["latest"] - res["previous"]
        return d, fmt(d, ind, True)
    if res["previous"]:
        pct = (res["latest"] / res["previous"] - 1) * 100
        return pct, f"{'+' if pct > 0 else ''}{pct:.2f}%"
    return None, ""


def heat_colour(value, scale=3.0):
    """Green for positive, red for negative, stronger for bigger moves."""
    if value is None or pd.isna(value):
        return "transparent"
    strength = min(abs(value) / scale, 1.0)
    rgb = "46,204,113" if value > 0 else "255,77,77"
    return f"rgba({rgb},{0.08 + 0.5 * strength:.2f})"


# ---------------------------------------------------------------- top bar pieces

def ticker_tape(ids):
    items = []
    for ind_id in ids:
        if ind_id not in DATA["loaded"]:
            continue
        ind, res = DATA["loaded"][ind_id]
        if res["error"]:
            continue
        change, text = day_change(ind, res)
        cls = "nc" if not change else ("up" if change > 0 else "dn")
        arrow = "" if not change else ("▲" if change > 0 else "▼")
        items.append(f"<a href='{link(ind['ticker'])}' target='_self'><span class='tk'>"
                     f"{ind['ticker']}</span>{fmt(res['latest'], ind)} "
                     f"<span class='{cls}'>{arrow}{text}</span></a>")
    if items:
        strip = "".join(items)
        st.markdown(f"<div class='tape'><div class='tape-inner'>{strip}{strip}</div></div>",
                    unsafe_allow_html=True)


def status_bar(source_health, extra=""):
    dots = " ".join(f"<span class='{'dot-ok' if ok else 'dot-bad'}'>●</span> {name}"
                    for name, ok in source_health.items())
    st.markdown(f"<div class='status'><b>HF MACRO</b><span>{dots}</span>"
                f"<span>{escape(extra)}</span><span>EDUCATIONAL USE · NOT INVESTMENT ADVICE</span></div>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------- cards

def sparkline_svg(series, colour, width=220, height=34):
    s = window(series.dropna(), 3)
    if len(s) > 120:
        s = s.iloc[:: max(1, len(s) // 120)]
    if len(s) < 2:
        return ""
    lo, hi = float(s.min()), float(s.max())
    span = (hi - lo) or 1.0
    pts = [(i / (len(s) - 1) * width, height - 3 - (v - lo) / span * (height - 6))
           for i, v in enumerate(s.values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (f"<svg viewBox='0 0 {width} {height}' width='100%' height='{height}' "
            f"preserveAspectRatio='none' style='display:block;margin:2px 0'>"
            f"<polygon points='0,{height} {line} {width},{height}' fill='{colour}' fill-opacity='0.07'/>"
            f"<polyline points='{line}' fill='none' stroke='{colour}' stroke-width='1.2'/></svg>")


def kpi_card(ind, res):
    """A compact card. The whole card is clickable and opens the full-screen chart."""
    with st.container(key=f"card_{ind['id']}"):
        top = (f"<div class='k-top'><span class='k-tk'>{ind['ticker']}</span>"
               f"{'' if res['error'] else change_html(ind, None if res['previous'] is None else res['latest'] - res['previous'])}</div>"
               f"<div class='k-name' title='{escape(ind['name'])}'>{escape(ind['name'])}"
               f"{info(ind['id'], ind['name'])}</div>")
        if res["error"]:
            st.markdown(top + f"<div class='k-val'>N/A</div><div class='err'>{escape(res['error'])}</div>",
                        unsafe_allow_html=True)
        else:
            change = None if res["previous"] is None else res["latest"] - res["previous"]
            colour = {"up": UP, "dn": DOWN}.get(tone(ind, change), ACCENT) \
                if ind["good_when"] != "neutral" else ACCENT
            f = DATA["forecasts"].get(ind["id"])
            outlook = f"{ARROWS[f['dir']]} {conf_html(f['stars'])}" if f and not f.get("error") else ""
            st.markdown(top + f"<div class='k-val'>{fmt(res['latest'], ind)}</div>"
                        f"{sparkline_svg(res['series'], colour)}"
                        f"<div class='k-foot'><span>{date_label(ind, res['latest_date'])}</span>"
                        f"<span>{outlook}</span></div>", unsafe_allow_html=True)
        st.button("open", key=f"cbtn_{ind['id']}", on_click=DATA["go_to"],
                  kwargs=dict(ticker=ind["ticker"]))


def card_grid(ids, columns=4):
    pairs = [DATA["loaded"][i] for i in ids if i in DATA["loaded"]]
    for start in range(0, len(pairs), columns):
        cols = st.columns(columns, gap="small")
        for col, (ind, res) in zip(cols, pairs[start:start + columns]):
            with col:
                kpi_card(ind, res)


# ---------------------------------------------------------------- charts

def transform_view(series, view):
    if view == "Change vs previous":
        return series.diff().dropna()
    if view == "% change y/y":
        s = series[~series.index.duplicated()].sort_index()
        year_ago = s.reindex(s.index - pd.DateOffset(years=1), method="nearest",
                             tolerance=pd.Timedelta(days=6))
        return ((s / pd.Series(year_ago.values, index=s.index) - 1) * 100).dropna()
    if view == "3-month average":
        return series.rolling("92D").mean()
    if view == "12-month average":
        return series.rolling("366D").mean()
    return series


def base_layout(fig, height, unit="", log=False, legend=False, x_range=None, slider=False,
                dragmode="zoom", uirevision=None):
    fig.update_layout(
        template="plotly_dark", height=height, margin=dict(l=4, r=4, t=6, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=MONO, size=10.5, color="#AEB8C2"),
        hovermode="x", dragmode=dragmode, showlegend=legend, bargap=0.12,
        uirevision=uirevision,
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=PANEL_2, bordercolor=ACCENT, font=dict(family=MONO, size=11)),
        newshape=dict(line=dict(color=ACCENT, width=2), fillcolor="rgba(232,33,43,0.12)"),
        yaxis=dict(ticksuffix=unit, gridcolor=GRID, zeroline=False, side="right",
                   type="log" if log else "linear", tickfont=dict(size=10), fixedrange=False,
                   showline=True, linecolor=BORDER),
        xaxis=dict(gridcolor=GRID, range=x_range, showline=True, linecolor=BORDER,
                   showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot",
                   spikecolor="#5B6570", spikethickness=1, tickfont=dict(size=10),
                   rangeslider=dict(visible=slider, thickness=0.05, bgcolor=PANEL_2,
                                    bordercolor=BORDER, borderwidth=1)),
    )
    return fig


def build_figure(ind, series, *, height=240, kind=None, compare=(), rebase=False, shades=(),
                 forecast=None, events=False, log=False, slider=False, ref_lines=(),
                 news=None, dragmode="zoom", x_range=None):
    """
    Draws one indicator plus optional extras:
    compare  - [(indicator, series)] overlaid on a second axis (or rebased to 100)
    shades   - [(label, [(start, end)], colour)] shaded periods
    forecast - forecast table (median / low / high)
    ref_lines- [(value, label)] horizontal level lines
    news     - headlines table (time, headline, source) shown as markers
    """
    kind = kind or ("Bar" if ind["chart"] == "bar" else "Line")
    s = series.dropna()
    if rebase and len(s):
        s = s / s.iloc[0] * 100
    unit = "" if rebase else ind["unit"]
    dec = 1 if rebase else ind["decimals"]
    hover = f"%{{y:,.{dec}f}}{unit}<extra>{escape(ind['ticker'])}</extra>"
    fig = go.Figure()
    if kind == "Bar":
        fig.add_bar(x=s.index, y=s.values, name=ind["name"], hovertemplate=hover,
                    marker_color=[UP if v >= 0 else DOWN for v in s.values], marker_line_width=0)
    else:
        fig.add_scatter(x=s.index, y=s.values, mode="lines", name=ind["name"], hovertemplate=hover,
                        line=dict(color=ACCENT, width=1.6),
                        fill="tozeroy" if kind == "Area" else None,
                        fillcolor="rgba(232,33,43,0.08)" if kind == "Area" else None)
    if not len(s):
        return base_layout(fig, height)
    x0, x1 = s.index[0], s.index[-1]

    if forecast is not None and not rebase:
        fc = forecast
        fig.add_scatter(x=fc.index, y=fc["high"], mode="lines", line=dict(width=0),
                        showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=fc.index, y=fc["low"], mode="lines", line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(232,33,43,0.15)", name="80% range", hoverinfo="skip")
        fig.add_scatter(x=[x1, *fc.index], y=[float(s.iloc[-1]), *fc["median"]], mode="lines",
                        name="Forecast", line=dict(color=ACCENT, width=1.6, dash="dot"),
                        hovertemplate=f"FCST %{{y:,.{dec}f}}{unit}<extra></extra>")
        x1 = fc.index[-1]

    for colour, (c_ind, c_series) in zip(SERIES_COLOURS, compare):
        c = c_series.dropna()
        c = c[(c.index >= x0) & (c.index <= x1)]
        if c.empty:
            continue
        if rebase:
            c = c / c.iloc[0] * 100
        fig.add_scatter(x=c.index, y=c.values, mode="lines", name=c_ind["name"],
                        yaxis="y" if rebase else "y2", line=dict(color=colour, width=1.3),
                        hovertemplate=f"%{{y:,.{c_ind['decimals']}f}}{'' if rebase else c_ind['unit']}"
                                      f"<extra>{escape(c_ind['ticker'])}</extra>")
    if compare and not rebase:
        fig.update_layout(yaxis2=dict(overlaying="y", side="left", showgrid=False,
                                      tickfont=dict(color=SERIES_COLOURS[0], size=10)))

    for label, periods, colour in shades:
        for start, end in periods:
            if end >= x0 and start <= x1:
                fig.add_vrect(x0=max(start, x0), x1=min(end, x1), line_width=0, layer="below",
                              fillcolor=colour)

    for value, label in ref_lines:
        fig.add_hline(y=value, line_width=1, line_dash="dash", line_color="#7A4A4C",
                      annotation_text=label, annotation_position="top left",
                      annotation_font=dict(size=9, color="#C99A9C"))

    if events:
        for when, label in EVENTS:
            when = pd.Timestamp(when)
            if x0 <= when <= x1:
                fig.add_vline(x=when, line_width=1, line_dash="dot", line_color="#4A5560")
                fig.add_annotation(x=when, y=1, yref="paper", text=label.upper(), showarrow=False,
                                   textangle=-90, xanchor="right", yanchor="top",
                                   font=dict(size=9, color=MUTED, family=MONO))

    if news is not None and not news.empty and not rebase:
        pts = news.dropna(subset=["time"])
        pts = pts[(pts["time"] >= x0) & (pts["time"] <= s.index[-1] + pd.Timedelta(days=1))]
        if not pts.empty:
            ys = [float(s.asof(t)) if not pd.isna(s.asof(t)) else float(s.iloc[0]) for t in pts["time"]]
            text = [f"{escape(h[:90])}<br><i>{escape(src)}</i>" for h, src in zip(pts["headline"], pts["source"])]
            fig.add_scatter(x=pts["time"], y=ys, mode="markers", name="News",
                            marker=dict(symbol="diamond", size=8, color=CYAN,
                                        line=dict(color="#000", width=1)),
                            text=text, hovertemplate="%{text}<extra>NEWS</extra>")

    if s.min() < 0 < s.max() and not log:
        fig.add_hline(y=0, line_color="#2E3742", line_width=1)

    legend = bool(compare) or forecast is not None or (news is not None and not news.empty)
    return base_layout(fig, height, unit=unit, log=log, legend=legend,
                       x_range=x_range or [x0, x1], slider=slider, dragmode=dragmode,
                       uirevision=f"{ind['id']}|{x_range}")


# ---------------------------------------------------------------- tables

def percentile_bar(pct, ind):
    if pct is None:
        return "-"
    if ind["good_when"] == "neutral":
        colour = ACCENT
    else:
        good = pct >= 50 if ind["good_when"] == "up" else pct < 50
        colour = UP if good else DOWN
    return f"<div class='bar'><i style='left:calc({pct:.0f}% - 1px);background:{colour}'></i></div>"


def scorecard(rows):
    """rows: list of (ind, res, change_3m, change_12m, percentile)."""
    body = []
    for ind, res, c3, c12, pct in rows:
        if res["error"]:
            continue
        body.append(
            f"<tr><td><a href='{link(ind['ticker'])}' target='_self'><span class='k-tk'>"
            f"{ind['ticker']}</span>&nbsp; {escape(ind['name'])}</a>{info(ind['id'], ind['name'])}</td>"
            f"<td class='n'>{fmt(res['latest'], ind)}</td>"
            f"<td class='n'>{change_html(ind, c3)}</td><td class='n'>{change_html(ind, c12)}</td>"
            f"<td>{percentile_bar(pct, ind)}</td>"
            f"<td class='n'>{'-' if pct is None else f'{pct:.0f}'}</td></tr>")
    st.markdown("<table class='t'><tr><th>Indicator</th><th style='text-align:right'>Last</th>"
                f"<th style='text-align:right'>3M{info('change', '3M / 12M change')}</th>"
                "<th style='text-align:right'>12M</th>"
                f"<th>20Y range{info('percentile', '20-year range')}</th>"
                f"<th style='text-align:right'>Pctl{info('percentile', 'Percentile')}</th></tr>"
                + "".join(body) + "</table>", unsafe_allow_html=True)


def heat_table(df, label_col, value_cols, scale=3.0, digits=2, suffix="%", links=None, about=None):
    """A table where each value cell is shaded green/red by size (e.g. % changes)."""
    head = "".join(f"<th style='text-align:right'>{escape(c)}</th>" for c in value_cols)
    rows = []
    for _, r in df.iterrows():
        name = escape(str(r[label_col]))
        if links:
            name = f"<a href='{links(r)}' target='_self'>{name}</a>"
        cells = "".join(
            f"<td class='n heat' style='background:{heat_colour(r[c], scale)}'>"
            f"{'-' if pd.isna(r[c]) else f'{r[c]:+.{digits}f}{suffix}'}</td>" for c in value_cols)
        rows.append(f"<tr><td>{name}</td>{cells}</tr>")
    st.markdown(f"<table class='t'><tr><th>{escape(label_col)}{info(about, label_col) if about else ''}</th>"
                f"{head}</tr>{''.join(rows)}</table>",
                unsafe_allow_html=True)


def time_ago(when):
    if when is None or pd.isna(when):
        return ""
    mins = (pd.Timestamp.now(tz="UTC").tz_localize(None) - when).total_seconds() / 60
    if mins < 60:
        return f"{max(mins, 0):.0f}M"
    if mins < 60 * 24:
        return f"{mins / 60:.0f}H"
    return f"{mins / 1440:.0f}D"


def headlines(df, limit=25, empty="No headlines match."):
    if df is None or df.empty:
        st.caption(empty)
        return
    rows = []
    for _, r in df.head(limit).iterrows():
        tags = "".join(f"<span class='tag'>{t}</span>" for t in (r["topics"] or []))
        rows.append(f"<div class='nr'><span class='t'>{time_ago(r['time'])}</span>"
                    f"<span class='s'>{escape(str(r['source']))}</span><span>"
                    f"<a href='{escape(str(r['link']))}' target='_blank'>{escape(str(r['headline']))}</a>"
                    f"{tags}</span></div>")
    st.markdown("".join(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------- TradingView widgets
# TradingView allows its widgets to be embedded on websites for free, as long as
# the small "TradingView" link underneath stays. These show live, licensed prices.

def _tv_html(script, config, height):
    import json
    return (f"<div class='tradingview-widget-container' style='height:{height}px'>"
            f"<div class='tradingview-widget-container__widget' style='height:{height - 32}px'></div>"
            f"<div class='tradingview-widget-copyright' style='font:11px {SANS};color:{DIM}'>"
            f"<a href='https://www.tradingview.com/' rel='noopener nofollow' target='_blank' "
            f"style='color:{MUTED}'>Live data by TradingView</a></div>"
            f"<script type='text/javascript' src='https://s3.tradingview.com/external-embedding/{script}' "
            f"async>{json.dumps(config)}</script></div>")


def tv_market_overview(tabs, height=560):
    import streamlit.components.v1 as components
    config = {
        "colorTheme": "dark", "dateRange": "12M", "showChart": True, "locale": "en",
        "isTransparent": True, "showSymbolLogo": False, "showFloatingTooltip": True,
        "width": "100%", "height": height - 32,
        "plotLineColorGrowing": ACCENT, "plotLineColorFalling": ACCENT,
        "gridLineColor": "rgba(42,46,57,0)", "scaleFontColor": MUTED,
        "belowLineFillColorGrowing": "rgba(232,33,43,0.12)", "belowLineFillColorFalling": "rgba(232,33,43,0.12)",
        "belowLineFillColorGrowingBottom": "rgba(232,33,43,0)", "belowLineFillColorFallingBottom": "rgba(232,33,43,0)",
        "symbolActiveColor": "rgba(232,33,43,0.15)",
        "tabs": [{"title": name, "symbols": [{"s": s, "d": d} for s, d in items]}
                 for name, items in tabs.items()],
    }
    components.html(_tv_html("embed-widget-market-overview.js", config, height), height=height)


def tv_advanced_chart(symbol, height=560):
    import streamlit.components.v1 as components
    config = {"autosize": False, "width": "100%", "height": height - 40, "symbol": symbol,
              "interval": "D", "timezone": "Europe/London",
              "theme": "dark", "style": "1", "locale": "en", "allow_symbol_change": True,
              "hide_side_toolbar": False, "calendar": False, "backgroundColor": "rgba(0,0,0,1)",
              "gridColor": "rgba(26,32,40,1)", "withdateranges": True, "details": True}
    components.html(_tv_html("embed-widget-advanced-chart.js", config, height), height=height)


# ---------------------------------------------------------------- forecast tables

def signal_table(table, target_dir):
    """
    The five drivers behind a confidence score. Each driver links to its own chart and its
    official source, so you can check the evidence yourself.
    """
    from sources import SOURCE_NAMES, source_url
    rows = []
    for _, r in table.iterrows():
        sig_id = r.get("id")
        pair = DATA["loaded"].get(sig_id)
        if pair is None:
            rows.append(f"<tr><td colspan='5' class='hs'>{escape(str(sig_id))}: not available in this "
                        f"edition</td></tr>")
            continue
        ind, _res = pair
        rel = "moves with it" if r.get("relationship", 1) > 0 else "moves against it"
        verdict = {"yes": "<span class='up'>■ AGREES</span>", "no": "<span class='dn'>□ DISAGREES</span>"}.get(
            r["Agrees"], "<span class='nc'>- NO DATA</span>")
        url = source_url(ind)
        src = (f"<a href='{escape(url)}' target='_blank' title='{escape(SOURCE_NAMES.get(ind['source'], ''))}'>"
               f"source ↗</a>") if url else "<span class='hs'>calculated</span>"
        rows.append(
            f"<tr><td><a href='{link(ind['ticker'])}' target='_self'><span class='k-tk'>{ind['ticker']}</span>"
            f"&nbsp;{escape(ind['name'])}</a>{info(ind['id'], ind['name'])}<br><span class='hs'>{rel}</span></td>"
            f"<td class='n'>{escape(str(r['Moved']))}</td><td class='n'>{escape(str(r['Implies']).upper())}</td>"
            f"<td>{verdict}</td><td class='n'>{src}</td></tr>")
    st.markdown("<table class='t'><tr><th>Driver" + info("drivers", "Drivers") + "</th>"
                "<th style='text-align:right'>Last 6 months</th><th style='text-align:right'>Points</th>"
                "<th>Vs forecast (" + WORDS.get(target_dir, "flat").upper() + ")</th>"
                "<th style='text-align:right'>Data</th></tr>" + "".join(rows) + "</table>",
                unsafe_allow_html=True)


def outlook_table(ids, empty="No forecasts available here."):
    """Every forecast in `ids`: last value, 12-month projection, range, direction and confidence."""
    rows = []
    for ind_id in ids:
        f = DATA["forecasts"].get(ind_id)
        pair = DATA["loaded"].get(ind_id)
        if not f or f.get("error") or pair is None:
            continue
        ind, res = pair
        end = f["fc"].iloc[-1]
        arrow_cls = {1: "up", -1: "dn", 0: "nc"}[f["dir"]]
        warn = " <span class='tag'>market</span>" if ind_id in MARKET_FORECASTS else ""
        rows.append((f["stars"], f"<tr><td><a href='{link(ind['ticker'])}' target='_self'><span class='k-tk'>"
                     f"{ind['ticker']}</span>&nbsp;{escape(ind['name'])}</a>{info(ind_id, ind['name'])}{warn}</td>"
                     f"<td class='n'>{fmt(res['latest'], ind)}</td>"
                     f"<td class='n'><span class='{arrow_cls}'>{ARROWS[f['dir']]}</span> {fmt(end['median'], ind)}</td>"
                     f"<td class='n hs'>{fmt(end['low'], ind)} to {fmt(end['high'], ind)}</td>"
                     f"<td>{conf_html(f['stars'])}</td>"
                     f"<td class='n'><a class='drv' href='{link(ind['ticker'], view='DRIVERS')}' target='_self' "
                     f"title='See the charts of the drivers'>{f['agree']}/{f['counted']} ↗</a></td></tr>"))
    if not rows:
        st.caption(empty)
        return
    rows.sort(key=lambda r: -r[0])
    st.markdown("<table class='t'><tr><th>Indicator</th><th style='text-align:right'>Last</th>"
                "<th style='text-align:right'>12M forecast" + info("forecast", "Forecast") + "</th>"
                "<th style='text-align:right'>80% range</th><th>Confidence" + info("confidence", "Confidence")
                + "</th><th style='text-align:right'>Drivers</th></tr>" + "".join(r for _, r in rows) + "</table>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------- DES and rankings

def des_table(rows):
    """Bloomberg-style description table: [(label, value, optional info key)]."""
    body = []
    for row in rows:
        label, value = row[0], row[1]
        about = row[2] if len(row) > 2 else None
        if value in (None, "", "-"):
            continue
        body.append(f"<tr><td class='l'>{escape(label)}{info(about, label) if about else ''}</td>"
                    f"<td class='v'>{value}</td></tr>")
    st.markdown("<table class='des'>" + "".join(body) + "</table>", unsafe_allow_html=True)


def pct_html(v, digits=2, unit="%"):
    if v is None or pd.isna(v):
        return "-"
    cls = "up" if v > 0 else "dn" if v < 0 else "nc"
    return f"<span class='{cls}'>{'+' if v > 0 else ''}{v:.{digits}f}{unit}</span>"


def ranked_lists(df, label_col, value_col, n=5, unit="%", digits=2, title_up="Top gainers",
                 title_down="Top losers", link_col=None):
    """Two side-by-side lists: the n biggest rises and the n biggest falls."""
    d = df.dropna(subset=[value_col])
    if d.empty:
        st.caption("No data for this period.")
        return
    up = d.sort_values(value_col, ascending=False).head(n)
    down = d.sort_values(value_col, ascending=True).head(n)
    left, right = st.columns(2, gap="small")
    for col, title, rows in ((left, title_up, up), (right, title_down, down)):
        lines = []
        for k, (_, r) in enumerate(rows.iterrows(), start=1):
            name = escape(str(r[label_col]))
            if link_col and r.get(link_col):
                name = f"<a href='{r[link_col]}' target='_self'>{name}</a>"
            lines.append(f"<tr><td class='n hs' style='width:24px'>{k}</td><td>{name}</td>"
                         f"<td class='n'>{pct_html(r[value_col], digits, unit)}</td></tr>")
        col.markdown(f"<div class='pt'><b>{escape(title)}</b></div><table class='t'>{''.join(lines)}</table>",
                     unsafe_allow_html=True)


def forecast_movers(ids, n=5):
    """Top forecast rises and falls (12-month projection vs today) among `ids`."""
    rows = []
    for ind_id in ids:
        f = DATA["forecasts"].get(ind_id)
        pair = DATA["loaded"].get(ind_id)
        if not f or f.get("error") or pair is None:
            continue
        ind, res = pair
        end = float(f["fc"]["median"].iloc[-1])
        last = float(res["latest"])
        change = (end - last) if ind["unit"] == "%" else ((end / last - 1) * 100 if last else None)
        rows.append({"Indicator": f"{ind['ticker']} · {ind['name']} · conf {f['stars']}/5",
                     "Change": change, "link": link(ind["ticker"], view="DRIVERS")})
    if not rows:
        st.caption("No forecasts available here.")
        return
    ranked_lists(pd.DataFrame(rows), "Indicator", "Change", n=n, title_up="Top forecast rises (12M)",
                 title_down="Top forecast falls (12M)", link_col="link")
