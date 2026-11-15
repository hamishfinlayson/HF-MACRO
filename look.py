"""
look.py - the v42 redesign: the new intro, the full-screen loading screens, page animations and the
home-page map. Everything here is decoration; the app works the same if any of it fails.

How it plugs in:
  * css()            extra styles, added after ui.inject_css (new colours, type, motion)
  * effects(anim)    the intro (once per browser session), the page animations and the screensaver
  * Loading(kind)    `with look.Loading("model"):` shows a full-screen animated loading screen while slow work runs
  * hero(...)        the "every indicator, one map" particle map for the home page
  * river_html(...)  the insider money river for the Smart Money page
"""

import json
import random
import time
from html import escape
from pathlib import Path

import look_assets as A

HERE = Path(__file__).parent
VERSION = "43.2"
CACHE = HERE / "data" / "cache" / "look_cache.json"
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@125,800"
             "&family=JetBrains+Mono:wght@300;400;500;600&family=Inter:wght@300;400;500;600&display=swap")

# ---------------------------------------------------------------- small cache of the latest real headlines / bubble lights
def remember(key, value):
    """Keep the latest real data the loading screens can show next time (headlines, bubble lights)."""
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        d = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        d[key] = value
        CACHE.write_text(json.dumps(d))
    except Exception:
        pass


def recall(key, default=None):
    try:
        return json.loads(CACHE.read_text()).get(key, default) if CACHE.exists() else default
    except Exception:
        return default


def _snapshot():
    if not hasattr(_snapshot, "d"):
        _snapshot.d = json.loads(A.SNAPSHOT)
    return _snapshot.d


def _fonts(load_fonts):
    return f'<link href="{FONTS_URL}" rel="stylesheet">' if load_fonts else ""


def _js(s):
    """A Python string as a JavaScript string literal that is safe inside a <script> tag."""
    return json.dumps(s).replace("</", "<\\/").replace("<!--", "<\\!--")


# ---------------------------------------------------------------- loading screens
KINDS = ("feeds", "model", "filings", "river", "news", "decoder", "bubble", "radar")
SOURCES = {"fred": ("FRED", "api.stlouisfed.org · US data"), "fred_ratio": ("FRED", "api.stlouisfed.org · US data"),
           "ons": ("ONS", "api.ons.gov.uk · UK data"), "yahoo": ("YAHOO", "query1.finance.yahoo.com · markets"),
           "ecb": ("ECB", "data-api.ecb.europa.eu · euro area"), "eia": ("EIA", "api.eia.gov · energy"),
           "boe": ("BOE", "bankofengland.co.uk · Bank Rate, gilts"), "derived": ("DERIVED", "computed in HF Macro")}


def source_counts(indicators):
    out = {}
    for ind in indicators:
        name, desc = SOURCES.get(ind.get("source"), (str(ind.get("source", "OTHER")).upper(), "official source"))
        out.setdefault(name, [name, 0, desc])[1] += 1
    return sorted(out.values(), key=lambda r: -r[1])


FULL_RUN_MS = {"radar": 9000, "feeds": 6500, "model": 16500, "filings": 14500, "river": 14500, "news": 11000, "decoder": 17000, "bubble": 7500}


def loader_data(kind, **extra):
    """The real data each loading screen draws."""
    s = _snapshot()
    d = {"kind": kind, "min": FULL_RUN_MS.get(kind, 6000)}
    if kind == "feeds":
        d.update(sources=extra.get("sources") or [["FRED", 48, "api.stlouisfed.org"]], logoSvg=s["logoSvg"])
    elif kind == "model":
        d.update(m3=s["m3"], m3eq=s["m3eq"])
    elif kind == "filings":
        d.update(tsla=s["tsla"][:16])
    elif kind == "river":
        d.update(river=s["river"])
    elif kind == "news":
        d.update(headlines=(recall("headlines") or s["headlines"])[:8], realNews=bool(recall("headlines")))
    elif kind == "decoder":
        d.update(headlines2=(recall("headlines") or s["headlines2"])[:14], realNews=bool(recall("headlines")))
    elif kind == "bubble":
        d.update(signs=s["signs"], stages=s["stages"])
        lights = recall("bubble_lights")
        if lights and len(lights) == len(s["signs"]):
            d["lights"] = lights
    return d


def loader_doc(kind, load_fonts=False, owner="", delay=150, embed=False, force=False, **extra):
    d = loader_data(kind if kind in KINDS else "feeds", **extra)
    d.update(owner=owner, delay=delay, embed=embed, force=force)
    return (A.LOADERS_HTML.replace("__FONTS__", _fonts(load_fonts))
            .replace("const D = __DATA__;", "const D = " + json.dumps(d, separators=(",", ":")).replace("</", "<\\/") + ";"))


def guess_kind(message):
    m = (message or "").lower()
    if "news" in m or "headline" in m:
        return "decoder"
    if any(w in m for w in ("picks", "walking forward", "commodit", "strateg")):
        return "model"
    if any(w in m for w in ("filing", "insider", "sec", "company data", "takeover", "fund")):
        return "filings"
    if "bubble" in m or "warning sign" in m:
        return "bubble"
    return "feeds"


def overlay_script(doc):
    """Runs inside a zero-height st.components frame: puts a full-screen frame with the loading screen
    over the whole app. The loading screen removes itself when this little frame disappears
    (Streamlit removes it as soon as the slow work is done)."""
    return f"""<script>(function () {{
  try {{
    const me = window.frameElement, P = window.parent.document; if (!me) return;
    const id = 'hfl' + Math.random().toString(36).slice(2); me.setAttribute('data-hfl-owner', id);
    P.querySelectorAll('iframe.hfl-ov').forEach(f => f.remove());
    const f = P.createElement('iframe'); f.className = 'hfl-ov'; f.title = 'Loading';
    f.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:2147483000;opacity:0;pointer-events:none;transition:opacity .45s cubic-bezier(.16,1,.3,1);background:#050506';
    f.srcdoc = {_js(doc)}.replace('__OWNER__', id); P.body.appendChild(f);
  }} catch (e) {{}}
}})();</script>"""


class Loading:
    """with look.Loading("model", "Working out this week's picks"): slow_work()"""
    def __init__(self, kind=None, message="", steps=None, load_fonts=False, once=None, force=False, **extra):
        self.kind = kind if kind in KINDS else guess_kind(message)
        self.load_fonts, self.extra, self.box, self.once, self.force = load_fonts, extra, None, once, bool(force)

    def __enter__(self):
        try:
            import streamlit as st
            import streamlit.components.v1 as components
            if self.once and not st.session_state.get("hfl_seen_" + self.once):
                # first visit this session: always show this page's loading screen for a few seconds (click to skip),
                # even when the data is already saved and arrives instantly
                st.session_state["hfl_seen_" + self.once] = True
                self.force = True
            self.box = st.empty()
            if self.kind == "radar":
                import scenes
                deals = recall("deals") or [{"t": "Waiting for the first SEC read", "b": "—", "f": ""}]
                doc = scenes.html("takeovers", {"deals": deals}, self.load_fonts, owner="__OWNER__", min_ms=FULL_RUN_MS["radar"], force=self.force)
            else:
                doc = loader_doc(self.kind, self.load_fonts, owner="__OWNER__", force=self.force, delay=0 if self.force else 150, **self.extra)
            with self.box.container():
                components.html(overlay_script(doc), height=0)
        except Exception:
            self.box = None
        return self

    def __exit__(self, *exc):
        try:
            if self.box is not None and not self.force:
                self.box.empty()
        except Exception:
            pass
        return False


# ---------------------------------------------------------------- intro, page animations
def intro_doc(load_fonts=False):
    return (A.INTRO_HTML.replace("__FONTS__", _fonts(load_fonts)).replace("__SPX__", A.INTRO_SPX)
            .replace("__FROM__", A.INTRO_FROM).replace("__TO__", A.INTRO_TO))


def intro_script(load_fonts=False):
    """The approved intro: once per browser session, in a full-screen frame over the app."""
    return f"""<script>(function () {{
  try {{
    const W = window.parent, P = W.document;
    if (W.sessionStorage.getItem('hf42_intro')) return; W.sessionStorage.setItem('hf42_intro', '1');
    const f = P.createElement('iframe'); f.className = 'hf-intro'; f.title = 'HF Macro intro';
    f.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:2147483600;background:transparent';
    f.setAttribute('allowtransparency', 'true'); f.srcdoc = {_js(intro_doc(load_fonts))}; P.body.appendChild(f);
    setTimeout(() => {{ if (f.isConnected) f.remove(); }}, 15000);
  }} catch (e) {{}}
}})();</script>"""


# The page-animation engine. It is copied into the main page once (so it keeps running between reruns) and only ever
# adds data-attributes or short-lived overlay elements: it never changes elements that Streamlit draws itself.
ENGINE = r"""
(function () {
  if (window.__hf42) return; window.__hf42 = true;
  const D = document, ease = 'cubic-bezier(.16,1,.3,1)';
  const on = () => D.body.getAttribute('data-hf-anim') !== 'off';
  const main = () => D.querySelector('[data-testid="stMain"]') || D.querySelector('section.main') || D.body;
  const block = () => D.querySelector('[data-testid="stMainBlockContainer"]') || D.querySelector('.block-container');
  const key = () => { const q = new URLSearchParams(location.search); return [q.get('p') || 'HOME', q.get('t') || '', q.get('c') || '', q.get('v') || ''].join('|'); };
  let last = key(), cur = null, curT = 0, lastMut = performance.now();
  // 1. page change: a curtain covers the page while Streamlit redraws it (no flicker), then a red scan line wipes it away
  const running = () => { const a = D.querySelector('.stApp'); return a && a.getAttribute('data-test-script-state') === 'running'; };
  function curtain(label) {
    if (!on()) return; if (cur) { cur.querySelector('.t').textContent = label || ''; curT = performance.now(); return; }
    const sb = D.querySelector('section[data-testid="stSidebar"]'), left = sb && sb.getAttribute('aria-expanded') !== 'false' ? sb.getBoundingClientRect().right : 0;
    cur = D.createElement('div'); cur.className = 'hf-curtain'; cur.style.left = Math.max(0, left) + 'px';
    cur.innerHTML = `<div class="in"><div class="k">HF MACRO · OPENING</div><div class="t"></div><div class="bar"><i></i></div></div>`;
    cur.querySelector('.t').textContent = label || ''; D.body.appendChild(cur); curT = performance.now();
    requestAnimationFrame(() => cur && cur.classList.add('on'));
  }
  function lift() {
    if (!cur) return; const c = cur; cur = null; c.classList.add('off'); setTimeout(() => c.remove(), 900); setTimeout(flourish, 120);
  }
  let idleSince = 0;
  setInterval(() => {
    if (key() !== last) { last = key(); if (!cur) curtain(''); }
    const now = performance.now(); if (running()) idleSince = 0; else if (!idleSince) idleSince = now;
    if (cur) { const t = now - curT;
      if ((t > 650 && idleSince && now - idleSince > 220) || t > 9000) lift(); }
  }, 60);
  D.addEventListener('pointerdown', e => {
    const b = e.target.closest && e.target.closest('section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button');
    if (b && b.getAttribute('aria-checked') !== 'true') curtain((b.innerText || '').trim());
  }, true);
  function enter() { setTimeout(flourish, 300); }
  // 2. flourishes on what is visible after a page change: headings fall into place letter by letter, numbers roll
  function overlayOn(el, html, cls, ms) {
    const r = el.getBoundingClientRect(); if (r.width < 4 || r.bottom < 0 || r.top > innerHeight) return;
    const cs = getComputedStyle(el), o = D.createElement('div'); o.className = 'hf-ov ' + cls; o.innerHTML = html;
    o.style.cssText = `left:${r.left}px;top:${r.top}px;width:${r.width + 40}px;height:${r.height}px;font:${cs.font};color:${cs.color};letter-spacing:${cs.letterSpacing};text-transform:${cs.textTransform};line-height:${cs.lineHeight};text-align:${cs.textAlign}`;
    el.setAttribute('data-hf-hide', '1'); D.body.appendChild(o);
    setTimeout(() => { el.removeAttribute('data-hf-hide'); o.remove(); }, ms);
  }
  function flourish() {
    if (!on()) return;
    let n = 0;
    D.querySelectorAll('.sec h3, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3').forEach(h => {
      if (n > 10) return; const t = (h.innerText || '').trim(); if (!t || t.length > 70 || h.querySelector('img,svg,a')) return; n++;
      const html = [...t].map((c, i) => `<span style="animation-delay:${(i * .022 + n * .05).toFixed(3)}s">${c === ' ' ? '&nbsp;' : c.replace(/[<&]/g, '')}</span>`).join('');
      overlayOn(h, html, 'hf-letters', 1300 + t.length * 22);
    });
    let k = 0;
    D.querySelectorAll('.k-val, [data-testid="stMetricValue"], .hv').forEach(v => {
      if (k > 24) return; const t = (v.innerText || '').trim(); if (!t || t.length > 18 || !/\d/.test(t)) return; k++;
      const digits = [...t].filter(c => /\d/.test(c)).length; let j = 0;
      const html = [...t].map(c => /\d/.test(c) ? `<span class="hf-od"><span class="hf-reel" style="--d:${c};transition-delay:${(k * .04 + (digits - j++) * .06).toFixed(2)}s">0<br>1<br>2<br>3<br>4<br>5<br>6<br>7<br>8<br>9<br>0<br>1<br>2<br>3<br>4<br>5<br>6<br>7<br>8<br>9</span></span>` : `<span class="hf-oc">${c.replace(/[<&]/g, '')}</span>`).join('');
      overlayOn(v, html, 'hf-odo', 2300);
    });
    requestAnimationFrame(() => requestAnimationFrame(() => D.querySelectorAll('.hf-odo .hf-reel').forEach(r => r.classList.add('go'))));
    reveal();
  }
  // 3. scroll reveals: blocks further down the page rise in as they come into view
  let io = null;
  function reveal() {
    const b = block(); if (!b || !on()) return;
    if (!io) io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.setAttribute('data-hf-sr', '1'); io.unobserve(e.target); } }), { root: null, threshold: .08 });
    b.querySelectorAll(':scope > [data-testid="stVerticalBlock"] > div, :scope > div > [data-testid="stVerticalBlock"] > div').forEach(el => {
      if (el.hasAttribute('data-hf-sr')) return; const r = el.getBoundingClientRect();
      if (r.top > innerHeight * .98) { el.setAttribute('data-hf-sr', '0'); io.observe(el); }
    });
    setTimeout(() => D.querySelectorAll('[data-hf-sr="0"]').forEach(el => { const r = el.getBoundingClientRect(); if (r.top < innerHeight) el.setAttribute('data-hf-sr', '1'); }), 2500);
  }
  // 4. charts draw themselves in from left to right when they first appear
  const mo = new MutationObserver(ms => {
    lastMut = performance.now();
    if (!on()) return;
    for (const m of ms) for (const nd of m.addedNodes) { if (nd.nodeType !== 1) continue;
      const plots = nd.matches && nd.matches('.js-plotly-plot') ? [nd] : (nd.querySelectorAll ? nd.querySelectorAll('.js-plotly-plot') : []);
      plots.forEach(p => { if (!p.hasAttribute('data-hf-draw')) { p.setAttribute('data-hf-draw', '0'); requestAnimationFrame(() => requestAnimationFrame(() => p.setAttribute('data-hf-draw', '1'))); } });
    }
  });
  mo.observe(D.body, { childList: true, subtree: true });
  // 5. cards: a soft spotlight follows the mouse and the card lifts
  D.addEventListener('pointermove', e => {
    const c = e.target.closest && e.target.closest('div[class*="st-key-card_"], [data-testid="stVerticalBlockBorderWrapper"], .hf-card');
    if (!c) return; const r = c.getBoundingClientRect(); c.style.setProperty('--mx', (e.clientX - r.left) + 'px'); c.style.setProperty('--my', (e.clientY - r.top) + 'px');
  }, { passive: true });
  setTimeout(enter, 900);
})();
"""


def engine_script(anim=True):
    return f"""<script>(function () {{
  try {{
    const P = window.parent.document; P.body.setAttribute('data-hf-anim', {_js('on' if anim else 'off')});
    if (!window.parent.__hf42) {{ const s = P.createElement('script'); s.textContent = {_js(ENGINE)}; P.head.appendChild(s); }}
  }} catch (e) {{}}
}})();</script>"""


def effects(anim=True, load_fonts=False, idle_seconds=120):
    """Intro + animation engine + the existing idle screensaver, in one zero-height frame."""
    import streamlit.components.v1 as components
    import fx
    html = intro_script(load_fonts) + engine_script(anim)
    try:
        html += fx.screensaver(idle_seconds)
    except Exception:
        pass
    components.html(html, height=0)


# ---------------------------------------------------------------- styles
BG, PANEL, PANEL_2, BORDER, BORDER_2 = "#050506", "#09090B", "#0F0F12", "#1A191E", "#222027"
INK, TEXT, MUTED, DIM = "#F1EEEA", "#CFCBC7", "#9A969D", "#6F6C72"
RED, CYAN, UP, DOWN = "#FF2A2A", "#57D3F2", "#3FD68A", "#FF5C6C"
SANS = "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'Cascadia Mono', Consolas, Menlo, monospace"
DISPLAY = "'Archivo', 'Arial Narrow', Arial, sans-serif"


def css(anim=True):
    motion = "" if anim else """
*, *:before, *:after { animation: none !important; transition: none !important; }
[data-hf-sr="0"] { opacity: 1 !important; transform: none !important; filter: none !important; }"""
    return f"""<style>
/* ===================== HF Macro v42 · professional, scientific: near-black, hairlines, one red ===================== */
:root {{ --hf-e: cubic-bezier(.16,1,.3,1); --hf-io: cubic-bezier(.65,0,.35,1); }}
.stApp {{ background: radial-gradient(70% 50% at 60% 0%, rgba(255,42,42,.035), transparent 70%), {BG} !important; }}
.stApp, .stMarkdown, label, input, textarea, button p, [data-baseweb="select"] div {{ font-family: {SANS} !important; }}
p, li {{ font-weight: 300; color: {TEXT}; }}
h1, h2, h3 {{ font-family: {SANS} !important; font-weight: 300 !important; color: {INK} !important; letter-spacing: -.01em; }}
h4 {{ font-family: {MONO} !important; font-weight: 400 !important; color: {RED} !important; font-size: .7rem !important; letter-spacing: .2em !important; }}
strong, b {{ font-weight: 500; }}
header[data-testid="stHeader"] {{ display: block !important; background: transparent !important; height: 0 !important; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}
.block-container, [data-testid="stMainBlockContainer"] {{ padding: 1.1rem 2rem 3.4rem !important; }}
/* ---------- sidebar: the v42 navigation */
section[data-testid="stSidebar"] {{ background: {PANEL} !important; border-right: 1px solid {BORDER} !important; min-width: 236px !important; max-width: 236px !important; }}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding-top: .4rem; }}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding: 0 16px 24px !important; }}
.hf-brand {{ display: flex; align-items: center; gap: 12px; padding: 14px 0 18px; border-bottom: 1px solid {BORDER}; margin-bottom: 8px; }}
.hf-brand svg {{ width: 34px; height: 34px; flex: none; }}
.hf-brand .w {{ font-family: {DISPLAY}; font-stretch: 125%; font-weight: 800; font-size: 17px; letter-spacing: .06em; color: {INK}; line-height: 1; }}
.hf-brand .w b {{ color: {RED}; font-weight: 800; }}
.hf-brand small {{ display: block; font: 9px {MONO}; letter-spacing: .22em; color: {DIM}; margin-top: 5px; }}
.hf-navh {{ font: 9px {MONO}; letter-spacing: .24em; color: {DIM}; text-transform: uppercase; margin: 18px 0 8px; }}
section[data-testid="stSidebar"] [data-testid="stElementContainer"], section[data-testid="stSidebar"] .stButtonGroup, section[data-testid="stSidebar"] [data-testid="stButtonGroup"] {{ width: 100% !important; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button > div {{ justify-content: flex-start !important; width: 100%; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button p {{ white-space: nowrap !important; overflow: visible !important; text-overflow: clip !important; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0 !important; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] > div {{ display: flex !important; flex-direction: column !important; gap: 0 !important; width: 100%; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button {{ width: 100% !important; justify-content: flex-start !important; text-align: left !important;
  background: transparent !important; border: 0 !important; border-left: 1px solid transparent !important; border-radius: 0 !important; color: {MUTED} !important;
  font-family: {SANS} !important; font-size: .82rem !important; font-weight: 300 !important; letter-spacing: 0 !important; text-transform: none !important;
  padding: 6px 10px !important; min-height: 30px !important; transition: color .3s, border-color .3s, background .3s, padding .4s var(--hf-e) !important; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button p {{ font-family: {SANS} !important; font-size: .82rem !important; text-transform: none !important; letter-spacing: 0 !important; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button:hover {{ color: {INK} !important; padding-left: 14px !important; }}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[kind*="Active"], section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[aria-checked="true"] {{
  color: {INK} !important; border-left-color: {RED} !important; background: linear-gradient(90deg, rgba(255,42,42,.10), transparent) !important; }}
.hf-foot {{ font: 9px/1.9 {MONO}; letter-spacing: .14em; color: {DIM}; margin-top: 22px; padding-top: 14px; border-top: 1px solid {BORDER}; }}
.hf-foot i {{ color: {UP}; font-style: normal; animation: hfpulse 2s infinite; }} @keyframes hfpulse {{ 50% {{ opacity: .3; }} }}
/* ---------- top line, tape, command bar */
.brand {{ display: none !important; }}
.clock {{ font-family: {MONO} !important; font-size: .66rem !important; letter-spacing: .14em; color: {DIM} !important; }}
.tape {{ background: transparent !important; border-color: {BORDER} !important; }}
.tape a {{ font-family: {MONO} !important; font-size: .7rem !important; color: {MUTED} !important; }} .tape a .tk {{ color: {INK} !important; }}
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextInput input {{ background: {PANEL} !important; border-color: {BORDER} !important; border-radius: 0 !important; }}
/* ---------- section headings: the hairline draws itself */
.sec {{ border-bottom: 0 !important; position: relative; padding-bottom: 8px !important; margin: 1.6rem 0 .8rem !important; }}
.sec:after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1px; background: {BORDER_2}; transform-origin: left; animation: hfline 1.5s var(--hf-io) both; }}
@keyframes hfline {{ from {{ transform: scaleX(0); }} }}
.sec b {{ font-family: {MONO} !important; color: {RED} !important; font-size: .64rem !important; letter-spacing: .16em; }}
.sec h3 {{ font-family: {SANS} !important; font-weight: 300 !important; font-size: 1.25rem !important; letter-spacing: -.01em !important; text-transform: none !important; color: {INK} !important; }}
.sec span {{ color: {DIM} !important; }}
.pt {{ border-left: 0 !important; padding-left: 0 !important; }}
.pt b {{ font-family: {MONO} !important; font-weight: 400 !important; font-size: .64rem !important; letter-spacing: .2em !important; color: {MUTED} !important; }}
/* ---------- panels and cards: square hairlines, spotlight + lift on hover */
[data-testid="stVerticalBlockBorderWrapper"], div[class*="st-key-card_"] {{ background: {PANEL} !important; border: 1px solid {BORDER} !important; border-radius: 0 !important;
  position: relative; transition: transform .6s var(--hf-e), border-color .4s, background .4s !important; }}
[data-testid="stVerticalBlockBorderWrapper"]:before, div[class*="st-key-card_"]:before {{ content: ""; position: absolute; inset: 0; pointer-events: none; opacity: 0; transition: opacity .5s; z-index: 0;
  background: radial-gradient(260px circle at var(--mx, 50%) var(--my, 50%), rgba(255,255,255,.055), transparent 65%); }}
[data-testid="stVerticalBlockBorderWrapper"]:hover:before, div[class*="st-key-card_"]:hover:before {{ opacity: 1; }}
div[class*="st-key-card_"]:hover {{ transform: translateY(-3px); border-color: rgba(255,42,42,.55) !important; background: #0B0B0E !important; }}
.k-tk {{ color: {RED} !important; }} .k-name {{ color: {MUTED} !important; font-family: {MONO} !important; font-size: .6rem !important; letter-spacing: .14em !important; }}
.k-val {{ font-family: {MONO} !important; font-weight: 300 !important; font-size: 1.45rem !important; color: {INK} !important; }}
.up {{ color: {UP} !important; }} .dn {{ color: {DOWN} !important; }}
[data-testid="stMetricValue"] {{ font-family: {MONO} !important; font-weight: 300 !important; color: {INK} !important; }}
[data-testid="stMetricLabel"] p {{ font-family: {MONO} !important; font-size: .6rem !important; letter-spacing: .16em !important; color: {MUTED} !important; }}
/* ---------- buttons, tabs, widgets */
.stButton button, .stDownloadButton button {{ border-radius: 0 !important; background: transparent !important; border: 1px solid {BORDER_2} !important; font-family: {MONO} !important;
  letter-spacing: .12em !important; transition: border-color .3s, color .3s, background .3s !important; }}
.stButton button:hover {{ border-color: {RED} !important; color: {INK} !important; background: rgba(255,42,42,.08) !important; }}
[data-testid="stMain"] [data-testid="stButtonGroup"] button {{ border-radius: 0 !important; background: transparent !important; border-color: {BORDER_2} !important; color: {MUTED} !important; }}
[data-testid="stMain"] [data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stMain"] [data-testid="stButtonGroup"] button[aria-checked="true"] {{
  background: {INK} !important; color: {BG} !important; border-color: {INK} !important; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background: {RED} !important; }}
[data-testid="stTabs"] button p {{ font-family: {MONO} !important; letter-spacing: .14em !important; font-size: .68rem !important; }}
[data-testid="stExpander"] details {{ border-radius: 0 !important; border-color: {BORDER} !important; background: {PANEL}; }}
label p, [data-testid="stWidgetLabel"] p {{ font-family: {MONO} !important; font-size: .6rem !important; letter-spacing: .16em !important; color: {DIM} !important; }}
/* ---------- page headers and markdown tables */
.hf-ph {{ margin: .4rem 0 1.4rem; padding-bottom: 14px; border-bottom: 1px solid {BORDER}; position: relative; }}
.hf-ph:after {{ content: ""; position: absolute; left: 0; bottom: -1px; width: 64px; height: 1px; background: {RED}; }}
.hf-ph .k {{ font: 9px {MONO}; letter-spacing: .26em; color: {RED}; text-transform: uppercase; }}
.hf-ph h1 {{ font: 300 2rem {SANS} !important; color: {INK} !important; margin: 6px 0 6px !important; padding: 0 !important; letter-spacing: -.015em; }}
.hf-ph p {{ font-size: .86rem; color: {MUTED}; max-width: 820px; margin: 0; line-height: 1.6; }}
.hf-tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); border-left: 1px solid {BORDER}; border-top: 1px solid {BORDER}; margin: 0 0 1.4rem; }}
.hf-tile {{ border-right: 1px solid {BORDER}; border-bottom: 1px solid {BORDER}; padding: 14px 16px; background: {PANEL}; }}
.hf-tile .k {{ font: 9px {MONO}; letter-spacing: .18em; color: {DIM}; text-transform: uppercase; }}
.hf-tile .v {{ font: 300 1.5rem {MONO}; color: {INK}; margin: 8px 0 4px; }}
.hf-tile .s {{ font: 10px {MONO}; color: {MUTED}; }}
.hf-step {{ display: grid; grid-template-columns: 34px 1fr; gap: 14px; padding: 12px 0; border-bottom: 1px solid {BORDER}; }}
.hf-step .n {{ font: 11px {MONO}; color: {RED}; padding-top: 2px; }}
.hf-step b {{ color: {INK}; font-weight: 500; }} .hf-step p {{ margin: 4px 0 0; color: {MUTED}; font-size: .84rem; line-height: 1.6; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] table {{ border-collapse: collapse; width: 100%; font-size: .8rem; margin: .4rem 0 1rem; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] th {{ font: 400 .58rem {MONO}; letter-spacing: .16em; text-transform: uppercase; color: {DIM}; text-align: left;
  padding: 9px 10px; border: 0; border-bottom: 1px solid {BORDER_2}; background: transparent; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] td {{ padding: 9px 10px; border: 0; border-bottom: 1px solid {BORDER}; color: {TEXT}; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] tbody tr {{ animation: hfrow .8s var(--hf-e) both; transition: background .25s; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] tbody tr:hover {{ background: rgba(255,255,255,.025); }}
{''.join(f'[data-testid="stMain"] [data-testid="stMarkdownContainer"] tbody tr:nth-child({i}) {{ animation-delay: {0.1 + i * 0.03:.2f}s; }} ' for i in range(1, 25))}
[data-testid="stMain"] h3 {{ font-size: 1.3rem !important; margin-top: 1.6rem !important; padding-bottom: 8px; border-bottom: 1px solid {BORDER}; }}
[data-testid="stAlert"] {{ border-radius: 0 !important; background: {PANEL} !important; border: 1px solid {BORDER} !important; border-left: 2px solid {CYAN} !important; }}
/* ---------- tables: rows cascade in, hairline rules */
table.t th {{ font-family: {MONO} !important; font-size: .58rem !important; letter-spacing: .18em !important; color: {DIM} !important; border-bottom-color: {BORDER_2} !important; }}
table.t td {{ border-bottom-color: {BORDER} !important; }} table.t td.n {{ font-family: {MONO} !important; }}
table.t tbody tr {{ animation: hfrow .8s var(--hf-e) both; }}
{''.join(f'table.t tbody tr:nth-child({i}) {{ animation-delay: {0.12 + i * 0.035:.3f}s; }} ' for i in range(1, 25))}
@keyframes hfrow {{ from {{ opacity: 0; transform: translateX(-8px); }} }}
.nr {{ border-bottom-color: {BORDER} !important; animation: hfrise .9s var(--hf-e) both; }} .nr .s {{ color: {RED} !important; }}
{''.join(f'.nr:nth-child({i}) {{ animation-delay: {0.1 + i * 0.04:.2f}s; }} ' for i in range(1, 20))}
.nr a {{ background: linear-gradient({RED}, {RED}) no-repeat 0 100% / 0 1px; transition: background-size .6s var(--hf-e), color .3s !important; }}
.nr a:hover {{ background-size: 100% 1px; color: {INK} !important; }}
.disc {{ border: 0 !important; border-left: 1px solid {RED} !important; background: rgba(255,42,42,.05) !important; color: {MUTED} !important; font-family: {MONO} !important;
  font-size: .62rem !important; letter-spacing: .08em; }}
.status {{ background: rgba(5,5,6,.92) !important; border-top-color: {BORDER} !important; backdrop-filter: blur(6px); }}
.status b {{ color: {RED} !important; }}
/* ---------- motion: page entry, scroll reveals, chart draw-in, page wipe, overlays */
@keyframes hfrise {{ from {{ opacity: 0; transform: translateY(14px); filter: blur(3px); }} to {{ opacity: 1; transform: none; filter: none; }} }}
@keyframes hfrise2 {{ from {{ opacity: 0; transform: translateY(14px); filter: blur(3px); }} to {{ opacity: 1; transform: none; filter: none; }} }}
[data-hf-sr="0"] {{ opacity: 0; transform: translateY(26px); filter: blur(4px); }}
[data-hf-sr="1"] {{ opacity: 1; transform: none; filter: none; transition: opacity 1.1s var(--hf-e), transform 1.1s var(--hf-e), filter 1.1s var(--hf-e); }}
.js-plotly-plot[data-hf-draw="0"] .plot {{ clip-path: inset(0 100% 0 0); }}
.js-plotly-plot[data-hf-draw="1"] .plot {{ clip-path: inset(0 0 0 0); transition: clip-path 1.6s var(--hf-io); }}
.hf-curtain {{ position: fixed; top: 0; right: 0; bottom: 0; z-index: 99985; background: radial-gradient(60% 50% at 50% 45%, rgba(255,42,42,.05), transparent 70%), {BG};
  display: grid; place-items: center; opacity: 0; transition: opacity .18s ease; pointer-events: none; }}
.hf-curtain.on {{ opacity: 1; }}
.hf-curtain .in {{ text-align: center; }}
.hf-curtain .k {{ font: 9px {MONO}; letter-spacing: .3em; color: {DIM}; }}
.hf-curtain .t {{ font: 300 34px {SANS}; color: {INK}; letter-spacing: -.01em; margin: 12px 0 18px; min-height: 40px; animation: hfrise .7s var(--hf-e) both; }}
.hf-curtain .bar {{ width: 220px; height: 1px; background: {BORDER_2}; margin: 0 auto; overflow: hidden; position: relative; }}
.hf-curtain .bar i {{ position: absolute; left: -40%; top: 0; bottom: 0; width: 40%; background: linear-gradient(90deg, transparent, {RED}, {INK}); animation: hfbar 1s var(--hf-io) infinite; }}
@keyframes hfbar {{ to {{ left: 100%; }} }}
.hf-curtain.off {{ opacity: 1; animation: hfwipe .8s var(--hf-io) forwards; }}
.hf-curtain.off:after {{ content: ""; position: absolute; left: 0; right: 0; height: 1px; background: {RED}; box-shadow: 0 0 14px {RED}, 0 0 40px rgba(255,42,42,.5); animation: hfline2 .8s var(--hf-io) forwards; }}
@keyframes hfwipe {{ from {{ clip-path: inset(0 0 0 0); }} to {{ clip-path: inset(100% 0 0 0); }} }}
@keyframes hfline2 {{ from {{ top: 0; }} to {{ top: 100%; }} }}
.hf-scan {{ position: fixed; left: 0; right: 0; top: 0; height: 1px; z-index: 99990; pointer-events: none; background: {RED};
  box-shadow: 0 0 12px {RED}, 0 0 40px rgba(255,42,42,.5); animation: hfscan .95s var(--hf-io) forwards; }}
.hf-scan:after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 1px; height: 80px; background: linear-gradient(transparent, rgba(255,42,42,.06)); }}
@keyframes hfscan {{ 0% {{ top: 0; opacity: 1; }} 85% {{ opacity: 1; }} 100% {{ top: 100vh; opacity: 0; }} }}
[data-hf-hide="1"] {{ visibility: hidden !important; }}
.hf-ov {{ position: fixed; z-index: 99980; pointer-events: none; white-space: nowrap; overflow: visible; margin: 0; padding: 0; }}
.hf-letters span {{ display: inline-block; opacity: 0; transform: translateY(.55em) rotate(5deg); filter: blur(4px); animation: hfrise .9s var(--hf-e) forwards; }}
.hf-od {{ display: inline-block; height: 1.2em; overflow: hidden; vertical-align: top; line-height: 1.2em; }}
.hf-oc {{ display: inline-block; height: 1.2em; line-height: 1.2em; vertical-align: top; }}
.hf-reel {{ display: block; line-height: 1.2em; transform: translateY(0); transition: transform 1.8s var(--hf-e); }}
.hf-reel.go {{ transform: translateY(calc(-1.2em * (10 + var(--d)))); }}
.hf-odo {{ line-height: 1.2em !important; }}
{motion}
</style>"""


# ---------------------------------------------------------------- the logo (H and F share a stem; the H's crossbar is the S&P 500)
def logo_svg(size=34):
    spx = json.loads(A.INTRO_SPX)
    import math
    lg = [math.log(v) for v in spx]
    sm = [sum(lg[max(0, i - 26):i + 27]) / len(lg[max(0, i - 26):i + 27]) for i in range(len(lg))]
    lo, hi = min(sm), max(sm)
    pts = sm[::6] + [sm[-1]]
    d = "M" + "L".join(f"{22 + 70 * i / (len(pts) - 1):.1f},{66 - (v - lo) / (hi - lo) * 39:.1f}" for i, v in enumerate(pts))
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" aria-hidden="true"><rect x="8" y="0" width="14" height="100" fill="{INK}"/>'
            f'<rect x="44" y="0" width="14" height="100" fill="{INK}"/><rect x="58" y="0" width="34" height="14" fill="{INK}"/>'
            f'<path d="{d}" fill="none" stroke="{BG}" stroke-width="16" stroke-linejoin="round"/><circle cx="92" cy="27" r="11" fill="{BG}"/>'
            f'<path d="{d}" fill="none" stroke="{RED}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"/><circle cx="92" cy="27" r="7" fill="{RED}"/></svg>')


def page_header(kicker, title, sub=""):
    return (f"<div class='hf-ph'><div class='k'>{escape(kicker)}</div><h1>{escape(title)}</h1>"
            + (f"<p>{sub}</p>" if sub else "") + "</div>")


def tiles(items):
    """items: [(label, value, small)] -> a row of hairline stat tiles"""
    return "<div class='hf-tiles'>" + "".join(f"<div class='hf-tile'><div class='k'>{escape(k)}</div><div class='v'>{v}</div>"
                                              f"<div class='s'>{s}</div></div>" for k, v, s in items) + "</div>"


def brand_html(public=False):
    return (f"<div class='hf-brand'>{logo_svg()}<div><div class='w'><b>HF</b> MACRO</div>"
            f"<small>TERMINAL · V42{' · PUBLIC' if public else ''}</small></div></div>")


# ---------------------------------------------------------------- home page: every indicator, one map
HERO_HTML = r"""<!doctype html><html><head><meta charset="utf-8">__FONTS__<style>
:root { --bg:#050506; --hl:#16151A; --hl2:#222027; --t:#CFCBC7; --hi:#F1EEEA; --m:#6F6C72; --m2:#9A969D; --red:#FF2A2A; --cy:#57D3F2; --up:#3FD68A; --dn:#FF5C6C;
  --sans:"Inter","Segoe UI","Helvetica Neue",Arial,sans-serif; --mono:"JetBrains Mono","Cascadia Mono",Consolas,Menlo,monospace; --e:cubic-bezier(.16,1,.3,1); }
* { box-sizing:border-box; } html,body { margin:0; background:transparent; color:var(--t); font-family:var(--sans); font-weight:300; overflow:hidden; }
.hero { display:grid; grid-template-columns: 1fr 290px; height:440px; border-bottom:1px solid var(--hl); }
.mapw { position:relative; }
canvas { position:absolute; left:0; top:0; width:100%; height:100%; display:block; }
.cap { position:absolute; left:0; top:12px; pointer-events:none; }
.cap .k { font:9px var(--mono); letter-spacing:.24em; color:var(--m); }
.cap .t { font-size:28px; font-weight:300; color:var(--hi); margin-top:8px; letter-spacing:-.01em; }
.cap .s { font-size:12px; color:var(--m); margin-top:6px; max-width:360px; line-height:1.6; }
a.lbl { position:absolute; transform:translateX(-50%); font:10px var(--mono); letter-spacing:.16em; color:var(--m2); text-decoration:none; border:1px solid var(--hl2); background:rgba(5,5,6,.75);
  padding:4px 8px; white-space:nowrap; opacity:0; transition:opacity 1.2s var(--e), border-color .3s, color .3s; }
a.lbl span { color:var(--red); margin-left:8px; } a.lbl:hover { color:var(--hi); border-color:var(--red); }
.ro-col { border-left:1px solid var(--hl); padding:16px 0 12px 20px; overflow:hidden; }
.h { font:9px var(--mono); letter-spacing:.24em; color:var(--m); margin-bottom:8px; text-transform:uppercase; }
.ro { display:grid; grid-template-columns: 1fr auto auto; gap:12px; align-items:baseline; padding:8px 0; border-bottom:1px solid var(--hl); font-size:12px;
  opacity:0; transform:translateY(10px); filter:blur(3px); animation: rise 1s var(--e) forwards; text-decoration:none; color:inherit; }
.ro:hover .n { color:var(--hi); }
.ro .n { color:var(--m2); font-size:11px; letter-spacing:.06em; transition:color .3s; } .ro .v { font:13px var(--mono); color:var(--hi); } .ro .c { font:11px var(--mono); width:62px; text-align:right; }
.up { color:var(--up); } .dn { color:var(--dn); }
.rise { opacity:0; transform:translateY(14px); filter:blur(3px); animation: rise 1.2s var(--e) forwards; }
@keyframes rise { to { opacity:1; transform:none; filter:none; } }
@media (max-width: 760px) { .hero { grid-template-columns: 1fr; height:auto; } .mapw { height:340px; } .cap { position:static; padding:10px 0 4px; } .cap .t { font-size:22px; } .ro-col { border-left:0; padding-left:0; } }
</style></head><body>
<div class="hero">
  <div class="mapw"><canvas id="map"></canvas>
    <div class="cap rise" style="animation-delay:.2s"><div class="k">THE TERMINAL AT A GLANCE</div><div class="t">Every indicator, one map.</div>
      <div class="s">Each point is one data series; clusters are the parts of the site, sized by how many indicators they hold. Click a label to open it.</div></div>
    <div id="labels"></div></div>
  <div class="ro-col rise" style="animation-delay:.35s"><div class="h" id="roh"></div><div id="ro"></div></div>
</div>
<script>
const D = __D__;
const $ = s => document.querySelector(s);
$('#roh').textContent = D.roTitle;
$('#ro').innerHTML = D.ro.map((m, i) => `<a class="ro" target="_parent" href="${m.href}" style="animation-delay:${.45 + i * .05}s"><span class="n">${m.name}</span><span class="v">${m.last}</span><span class="c ${m.d >= 0 ? 'up' : 'dn'}">${m.d == null ? '' : (m.d >= 0 ? '+' : '−') + Math.abs(m.d).toFixed(2) + '%'}</span></a>`).join('');
(function () {
  const cv = $('#map'), ctx = cv.getContext('2d'), dpr = Math.min(2, devicePixelRatio || 1), box = cv.parentElement;
  let W, H, pts = [], clusters = [];
  function setup() { W = box.clientWidth; H = box.clientHeight; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    pts = []; clusters = []; $('#labels').innerHTML = '';
    D.reg.forEach((g, ci) => { const [px, py] = g.pos, R = (24 + Math.sqrt(g.n) * 14) * Math.min(1, W / 850), cx = W * px, cy = H * py; clusters.push({ cx, cy, R });
      for (let k = 0; k < g.n * 60; k++) { const th = Math.random() * 6.283, ph = Math.acos(2 * Math.random() - 1), rr = R * Math.cbrt(Math.random());
        pts.push({ c: ci, x: rr * Math.sin(ph) * Math.cos(th), y: rr * Math.cos(ph) * .8, z: rr * Math.sin(ph) * Math.sin(th), s: Math.random() < .06, red: Math.random() < .02, ph: Math.random() * 6.28 }); }
      const l = document.createElement('a'); l.className = 'lbl'; l.target = '_parent'; l.href = g.href; l.innerHTML = `${g.name}<span>${g.n}</span>`;
      l.style.left = cx + 'px'; l.style.top = (cy > H * .6 ? cy + R * .8 + 16 : cy - R - 18) + 'px'; l.style.transitionDelay = (1.6 + ci * .12) + 's, 0s, 0s';
      $('#labels').appendChild(l); requestAnimationFrame(() => requestAnimationFrame(() => l.style.opacity = 1)); }); }
  setup(); addEventListener('resize', setup);
  const t0 = performance.now();
  (function frame(now) { const t = (now - t0) / 1000, g = Math.min(1, Math.max(0, (t - .3) / 2.6)), e = g * g * g * (g * (g * 6 - 15) + 10);
    ctx.clearRect(0, 0, W, H); ctx.strokeStyle = 'rgba(241,238,234,.07)'; ctx.lineWidth = 1;
    for (let a = 0; a < clusters.length; a++) for (let b = a + 1; b < clusters.length; b++) { if ((a + b) % 2) continue; ctx.globalAlpha = e; ctx.beginPath(); ctx.moveTo(clusters[a].cx, clusters[a].cy); ctx.lineTo(clusters[b].cx, clusters[b].cy); ctx.stroke(); }
    ctx.globalAlpha = 1;
    for (const p of pts) { const C = clusters[p.c], a = t * .1 + p.c, ca = Math.cos(a), sa = Math.sin(a), x = p.x * ca - p.z * sa, z = p.x * sa + p.z * ca, d = (z + C.R) / (2 * C.R);
      const X = C.cx + x * e + Math.sin(t * .6 + p.ph), Y = C.cy + p.y * e + Math.cos(t * .5 + p.ph);
      ctx.fillStyle = p.red ? `rgba(255,42,42,${.5 + .4 * d})` : (p.s ? `rgba(87,211,242,${.35 + .5 * d})` : `rgba(241,238,234,${(.12 + .5 * d) * e})`); const s = p.s ? 1.6 : 1; ctx.fillRect(X, Y, s, s); }
    requestAnimationFrame(frame); })(t0);
})();
setTimeout(() => document.querySelectorAll('.rise, .ro').forEach(e => { e.style.animation = 'none'; e.style.opacity = 1; e.style.transform = 'none'; e.style.filter = 'none'; }), 3500);
</script></body></html>"""

POSITIONS = [[.36, .62], [.55, .32], [.74, .66], [.84, .32], [.57, .72], [.92, .76], [.2, .3], [.16, .78]]


def hero(regions, readouts, ro_title, load_fonts=False):
    """regions: [(label, count, href)], readouts: [dict(name, last, d, href)]"""
    reg = [{"name": n.upper(), "n": int(c), "href": h, "pos": POSITIONS[i % len(POSITIONS)]} for i, (n, c, h) in enumerate(regions) if c]
    d = {"reg": reg, "ro": readouts, "roTitle": ro_title}
    return HERO_HTML.replace("__FONTS__", _fonts(load_fonts)).replace("__D__", json.dumps(d).replace("</", "<\\/"))


def river_html(load_fonts=False):
    """The insider money river (real SEC Form 4 purchases, latest quarter in the snapshot), as an embedded page view."""
    return loader_doc("river", load_fonts, embed=True)


def snapshot_dates():
    s = _snapshot()
    return {"model": s["m3"]["dates"][-1], "river_from": s["river"]["from"], "river_to": s["river"]["to"]}
