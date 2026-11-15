"""
fx.py - HF Macro's show-off visuals (v41). Each returns a self-contained HTML string shown with
streamlit.components.v1.html (a small sandboxed frame that is allowed to run scripts). The data-driven ones
(market web, race replay, bubble radar) draw REAL numbers handed in from the app; the intro and the
screensaver are decoration. Everything respects 'reduce motion' and never sends data anywhere.
"""
import json, math
from html import escape

RED, TEXT, MUTED, DIM, UP, DOWN = "#E8212B", "#D9DEE3", "#8A96A3", "#55606C", "#2ECC71", "#FF6B6B"
MONO = "Consolas, Menlo, monospace"


def _j(x):
    return json.dumps(x, separators=(",", ":"))


# ================================================================== 1. boot-up intro (once per browser session)
def boot_intro(art_uri, version="v41"):
    lines = ["HF MACRO TERMINAL " + version, "> loading modules: macro · markets · commodities · bubble · smart money",
             "> linking data feeds: FRED · ECB · BIS · CFTC · SEC EDGAR · Yahoo",
             "> warming up the commodity model", "> releasing the spider", "> ready_"]
    return f"""<script>
(function() {{
  const P = window.parent, D = P.document;
  try {{ if (P.sessionStorage.getItem('hfm_boot') === '1') return; P.sessionStorage.setItem('hfm_boot', '1'); }} catch (e) {{ if (P.__hfmBoot) return; }}
  P.__hfmBoot = true;
  if (P.matchMedia && P.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const o = D.createElement('div'); o.id = 'hfm-boot';
  o.innerHTML = `<style>
   #hfm-boot {{ position:fixed; inset:0; z-index:1000000; background:#000; font-family:{MONO}; color:{TEXT}; overflow:hidden; transition:opacity .8s; }}
   #hfm-boot .t {{ position:absolute; left:8vw; top:12vh; font-size:15px; line-height:1.9; white-space:pre; }}
   #hfm-boot .t div:first-child {{ color:{RED}; font-size:20px; letter-spacing:.2em; margin-bottom:8px; }}
   #hfm-boot img {{ position:absolute; inset:0; width:100%; height:100%; object-fit:contain; opacity:0; transition:opacity 1s; }}
   #hfm-boot .skip {{ position:absolute; right:28px; bottom:24px; border:1px solid {DIM}; color:{MUTED}; background:none;
     font-family:{MONO}; font-size:12px; letter-spacing:.15em; padding:6px 12px; cursor:pointer; }}
   #hfm-boot .skip:hover {{ border-color:{RED}; color:{RED}; }}
   #hfm-boot .scan {{ position:absolute; left:0; right:0; height:140px; background:linear-gradient(transparent, rgba(232,33,43,.10), transparent); animation:hfmscan 2.6s linear infinite; }}
   @keyframes hfmscan {{ from {{ top:-140px; }} to {{ top:100%; }} }}
  </style><div class="scan"></div><div class="t"></div><img alt=""><button class="skip">SKIP ▸</button>`;
  D.body.appendChild(o);
  const t = o.querySelector('.t'), img = o.querySelector('img'), lines = {_j(lines)};
  let done = false;
  const end = () => {{ if (done) return; done = true; o.style.opacity = 0; setTimeout(() => o.remove(), 850); }};
  o.querySelector('.skip').onclick = end; o.addEventListener('click', end);
  D.addEventListener('keydown', (e) => {{ if (e.key === 'Escape') end(); }}, {{once: true}});
  let li = 0, ci = 0, div = null;
  (function type() {{
    if (done) return;
    if (li >= lines.length) {{ setTimeout(() => {{ t.style.transition = 'opacity .6s'; t.style.opacity = 0; img.src = {_j(art_uri)}; img.style.opacity = 1; }}, 250);
                             setTimeout(end, 4600); return; }}
    if (!div) {{ div = D.createElement('div'); t.appendChild(div); }}
    div.textContent = lines[li].slice(0, ++ci);
    if (ci >= lines[li].length) {{ li++; ci = 0; div = null; setTimeout(type, 110); }} else setTimeout(type, li === 0 ? 35 : 7);
  }})();
}})();
</script>"""


# ================================================================== 2. screensaver: ticker rain after a while idle
def screensaver(idle_seconds=90, words=None):
    words = words or ["WTI", "BRENT", "GOLD", "SILVER", "COPPER", "NATGAS", "CORN", "WHEAT", "SPX", "NDX", "DXY", "UST10",
                      "EURUSD", "GBPUSD", "USDJPY", "BTC", "VIX", "HF", "▲", "▼", "σ", "β", "Δ"]
    return f"""<script>
(function() {{
  const P = window.parent, D = P.document;
  if (P.__hfmSaver) return; P.__hfmSaver = true;
  if (P.matchMedia && P.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const W = {_j(words)}, IDLE = {int(idle_seconds) * 1000};
  let last = Date.now(), on = false, cv, ctx, cols, drops, raf, box;
  const wake = () => {{ last = Date.now(); if (on) stop(); }};
  ['mousemove', 'mousedown', 'keydown', 'wheel', 'touchstart', 'scroll'].forEach(ev => D.addEventListener(ev, wake, {{passive: true, capture: true}}));
  function start() {{
    on = true; box = D.createElement('div');
    box.style.cssText = 'position:fixed;inset:0;z-index:1000001;background:#000;opacity:0;transition:opacity 1.2s;cursor:none';
    cv = D.createElement('canvas'); box.appendChild(cv);
    const msg = D.createElement('div');
    msg.innerHTML = '<div style="font:700 64px {MONO};letter-spacing:.12em"><span style="background:{RED};color:#fff;padding:0 14px">HF</span> <span style="color:#fff">MACRO</span></div>'
      + '<div style="font:12px {MONO};color:{MUTED};letter-spacing:.35em;margin-top:18px">MOVE THE MOUSE TO RETURN</div>';
    msg.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-shadow:0 0 30px rgba(232,33,43,.9)';
    box.appendChild(msg); D.body.appendChild(box);
    ctx = cv.getContext('2d'); size(); P.addEventListener('resize', size);
    requestAnimationFrame(() => box.style.opacity = 1); loop();
  }}
  function size() {{ cv.width = P.innerWidth; cv.height = P.innerHeight; cols = Math.floor(cv.width / 22); drops = Array.from({{length: cols}}, () => Math.random() * -60); }}
  function loop() {{
    ctx.fillStyle = 'rgba(0,0,0,0.08)'; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.font = '15px {MONO}';
    for (let i = 0; i < cols; i++) {{
      const w = W[(i * 7 + Math.floor(drops[i])) % W.length], y = drops[i] * 22;
      ctx.fillStyle = Math.random() < 0.05 ? '#fff' : (i % 3 ? '{UP}' : '{RED}');
      ctx.fillText(w, i * 22, y);
      if (y > cv.height && Math.random() > 0.975) drops[i] = Math.random() * -20;
      drops[i] += 0.55;
    }}
    raf = requestAnimationFrame(loop);
  }}
  function stop() {{ on = false; cancelAnimationFrame(raf); P.removeEventListener('resize', size); if (box) box.remove(); }}
  setInterval(() => {{ if (!on && Date.now() - last > IDLE && !D.hidden) start(); }}, 2000);
}})();
</script>"""


# ================================================================== 3. market web: real correlations, spider walks the strongest links
def market_web(rets, names, groups, links, height=600):
    """rets: weekly % returns DataFrame (columns = ids). names/groups/links: dicts by id. Real data only."""
    import numpy as np
    C = rets.corr()
    ids = [c for c in C.columns if C[c].notna().sum() > 2]
    C = C.loc[ids, ids]
    order = sorted(ids, key=lambda i: (groups.get(i, "zz"), names.get(i, i)))
    n = len(order); W, H, cx, cy = 1200, 600, 600, 300
    pos = {}
    for k, i in enumerate(order):
        a = 2 * math.pi * k / n - math.pi / 2
        pos[i] = (cx + 470 * math.cos(a), cy + 245 * math.sin(a))
    edges = []
    for a_ in range(n):
        for b_ in range(a_ + 1, n):
            i, j = order[a_], order[b_]; r = C.loc[i, j]
            if r == r and abs(r) >= 0.45: edges.append((abs(r), r, i, j))
    edges.sort(reverse=True)
    # spider's walk: start on the strongest link, always take the strongest unused link from where it stands
    walk, used = [], set()
    if edges:
        _, _, i, j = edges[0]; walk = [i, j]; used.add((i, j))
        for _ in range(14):
            cur = walk[-1]
            nxt = [(s, r, a, b) for s, r, a, b in edges if (a == cur or b == cur) and (a, b) not in used]
            if not nxt: break
            s, r, a, b = nxt[0]; used.add((a, b)); walk.append(b if a == cur else a)
    route = walk + walk[-2::-1] if len(walk) > 1 else walk
    pts = [pos[i] for i in route]
    d = ("M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)) if len(pts) > 1 else ""
    seg = [math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]; tot = sum(seg) or 1; cum = [0]
    for s in seg: cum.append(cum[-1] + s)
    T = max(10.0, tot / 120)
    lines = "".join(f'<line x1="{pos[i][0]:.1f}" y1="{pos[i][1]:.1f}" x2="{pos[j][0]:.1f}" y2="{pos[j][1]:.1f}" stroke="{UP if r > 0 else DOWN}" '
                    f'stroke-opacity="{0.15 + 0.6 * (s - .45) / .55:.2f}" stroke-width="{1 + 5 * (s - .45) / .55:.1f}"><title>{escape(names.get(i, i))} ↔ {escape(names.get(j, j))}: {r:+.2f}</title></line>'
                    for s, r, i, j in edges)
    gcol = {}
    pal = [RED, "#4FC3F7", "#FFD166", UP, "#C792EA", "#FF9E64"]
    for g in sorted(set(groups.get(i, "Other") for i in order)): gcol[g] = pal[len(gcol) % len(pal)]
    best = {}
    for s, r, i, j in edges:
        best.setdefault(i, (r, j)); best.setdefault(j, (r, i))
    nodes = []
    for i in order:
        x, y = pos[i]; g = groups.get(i, "Other"); lab = names.get(i, i)
        tip = f"{lab} ({g})" + (f" · moves most with {names.get(best[i][1], best[i][1])} ({best[i][0]:+.2f})" if i in best else " · no strong links")
        anchor = "start" if x >= cx else "end"; dx = 12 if x >= cx else -12
        nodes.append(f'<a href="{escape(links.get(i, "#"))}" target="_parent"><g class="node"><title>{escape(tip)}</title>'
                     f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#000" stroke="{gcol[g]}" stroke-width="2.4"/>'
                     f'<text x="{x + dx:.1f}" y="{y + 4:.1f}" text-anchor="{anchor}">{escape(lab)}</text></g></a>')
    hits = []
    seen = set()
    for k, i in enumerate(route):
        if i in seen and k < len(walk): continue
        seen.add(i); x, y = pos[i]; delay = cum[k] / tot * T - T
        tag = f"{names.get(best[i][1], best[i][1])} {best[i][0]:+.2f}" if i in best else ""
        hits.append(f'<g class="hit" style="animation-delay:{delay:.2f}s"><circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="none" stroke="{RED}" stroke-width="3"/>'
                    f'<text x="{x:.1f}" y="{y - 16:.1f}" text-anchor="middle" class="tag">↔ {escape(tag)}</text></g>')
    from loader_art import spider_svg
    legend = " ".join(f'<tspan fill="{c}">● {escape(g)}</tspan>' for g, c in gcol.items())
    spider = f'<g>{spider_svg(1.3)}<animateMotion dur="{T:.1f}s" repeatCount="indefinite" rotate="auto" path="{d}"/></g>' if d else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body {{ margin:0; background:transparent; overflow:hidden; }}
svg {{ width:100%; height:{height}px; display:block; }}
text {{ font-family:{MONO}; font-size:12px; fill:{TEXT}; }}
.node:hover circle {{ fill:{RED}; }} .node {{ cursor:pointer; }}
.tag {{ fill:{UP}; font-size:13px; }}
.hit {{ opacity:0; animation: hit {T:.1f}s linear infinite; }}
@keyframes hit {{ 0% {{ opacity:1; }} 18% {{ opacity:.9; }} 26% {{ opacity:0; }} 100% {{ opacity:0; }} }}
.draw line {{ stroke-dasharray:1200; stroke-dashoffset:1200; animation: draw 2.5s ease-out forwards; }}
@keyframes draw {{ to {{ stroke-dashoffset:0; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation:none !important; }} .draw line {{ stroke-dashoffset:0; }} }}
</style></head><body>
<svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<g class="draw">{lines}</g>{"".join(hits)}{"".join(nodes)}{spider}
<text x="{cx}" y="{cy - 6}" text-anchor="middle" style="font-size:15px;fill:{RED};letter-spacing:.25em">MARKET WEB</text>
<text x="{cx}" y="{cy + 16}" text-anchor="middle" style="font-size:11px;fill:{MUTED}">{len(edges)} strong links · last 52 weeks</text>
<text x="{cx}" y="{H - 6}" text-anchor="middle" style="font-size:11px">{legend}</text>
</svg></body></html>"""


# ================================================================== 4. model race replay (real weekly results)
def race(series, colours=None, start_money=1000, height=430, title="THE RACE"):
    """series: {name: weekly % returns (pd.Series)}. Draws each line week by week like a race."""
    import pandas as pd
    df = pd.concat(series, axis=1).dropna()
    eq = (1 + df / 100).cumprod() * start_money
    data = dict(dates=[d.strftime("%Y-%m-%d") for d in eq.index], names=list(eq.columns),
                vals=[[round(float(v), 2) for v in eq[c]] for c in eq.columns],
                cols=colours or [RED, "#8A96A3", "#4FC3F7", "#FFD166"][:len(eq.columns)], money=start_money, title=title)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body {{ margin:0; background:transparent; font-family:{MONO}; color:{TEXT}; overflow:hidden; }}
#wrap {{ position:relative; height:{height}px; }} canvas {{ width:100%; height:100%; display:block; }}
#ctl {{ position:absolute; right:10px; top:6px; }}
button {{ background:#11161C; color:{TEXT}; border:1px solid #1C232B; font-family:{MONO}; font-size:11px; letter-spacing:.08em; padding:4px 10px; cursor:pointer; }}
button:hover {{ border-color:{RED}; color:{RED}; }}
</style></head><body><div id="wrap"><canvas id="c"></canvas><div id="ctl"><button id="b">▶ REPLAY</button></div></div>
<script>
const D = {_j(data)}, cv = document.getElementById('c'), ctx = cv.getContext('2d');
const N = D.dates.length, dpr = window.devicePixelRatio || 1;
let k = 0, raf = null;
function fmt(v) {{ return '£' + Math.round(v).toLocaleString('en-GB'); }}
function size() {{ cv.width = cv.clientWidth * dpr; cv.height = cv.clientHeight * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); draw(); }}
function draw() {{
  const w = cv.clientWidth, h = cv.clientHeight, L = 70, R = 170, T = 34, B = 28;
  ctx.clearRect(0, 0, w, h);
  const all = D.vals.flat(), lo = Math.min(...all) * .95, hi = Math.max(...all) * 1.05;
  const X = i => L + (w - L - R) * i / (N - 1), Y = v => T + (h - T - B) * (1 - (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)));
  ctx.strokeStyle = '#1C232B'; ctx.fillStyle = '{DIM}'; ctx.font = '11px {MONO}'; ctx.lineWidth = 1;
  for (let g = 0; g < 5; g++) {{ const v = lo * Math.pow(hi / lo, g / 4), y = Y(v); ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(w - R, y); ctx.stroke(); ctx.fillText(fmt(v), 4, y + 4); }}
  let yr = '';
  D.dates.forEach((d, i) => {{ if (d.slice(0, 4) !== yr) {{ yr = d.slice(0, 4); if (+yr % 2 === 0) ctx.fillText(yr, X(i) - 14, h - 8); }} }});
  ctx.fillStyle = '{RED}'; ctx.font = '13px {MONO}'; ctx.fillText(D.title + '  ·  ' + D.dates[Math.min(k, N - 1)].slice(0, 7), L, 18);
  const ends = [];
  D.vals.forEach((vs, s) => {{
    ctx.strokeStyle = D.cols[s]; ctx.lineWidth = s === 0 ? 2.6 : 1.6; ctx.shadowColor = D.cols[s]; ctx.shadowBlur = s === 0 ? 10 : 0;
    ctx.beginPath(); for (let i = 0; i <= Math.min(k, N - 1); i++) {{ i ? ctx.lineTo(X(i), Y(vs[i])) : ctx.moveTo(X(i), Y(vs[i])); }} ctx.stroke(); ctx.shadowBlur = 0;
    const i = Math.min(k, N - 1); ends.push([Y(vs[i]), s, vs[i]]);
    ctx.fillStyle = D.cols[s]; ctx.beginPath(); ctx.arc(X(i), Y(vs[i]), s === 0 ? 5 : 3.5, 0, 7); ctx.fill();
  }});
  ends.sort((a, b) => a[0] - b[0]); let prev = -99;
  const leader = ends.reduce((m, e) => e[2] > m[2] ? e : m, ends[0])[1];
  ends.forEach(([y, s, v]) => {{ y = Math.max(y, prev + 30); prev = y; ctx.fillStyle = D.cols[s]; ctx.font = (s === leader ? 'bold ' : '') + '12px {MONO}';
    ctx.fillText((s === leader ? '▲ ' : '  ') + D.names[s], w - R + 12, y - 2); ctx.fillStyle = '{TEXT}'; ctx.fillText('  ' + fmt(v), w - R + 12, y + 13); }});
}}
function play() {{ cancelAnimationFrame(raf); k = 0; const step = Math.max(1, Math.round(N / 420));
  (function f() {{ k += step; draw(); if (k < N - 1) raf = requestAnimationFrame(f); }})(); }}
document.getElementById('b').onclick = play;
window.addEventListener('resize', size);
const io = new IntersectionObserver(es => {{ if (es[0].isIntersecting) {{ play(); io.disconnect(); }} }}); 
size(); if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {{ k = N - 1; draw(); }} else io.observe(cv);
</script></body></html>"""


# ================================================================== 5. bubble radar (real signs and lights)
def bubble_radar(signs, stages, score_text, band, height=520):
    """signs: list of dicts {name, stage (1-6), light (0 red / 1 amber / 2 green / None)}. stages: {n: (short, long)}."""
    data = dict(signs=signs, stages={str(k): v[0] for k, v in stages.items()}, score=score_text, band=band)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body {{ margin:0; background:transparent; font-family:{MONO}; color:{TEXT}; overflow:hidden; }}
canvas {{ width:100%; height:{height}px; display:block; }}
#tip {{ position:absolute; pointer-events:none; background:#0A0D11; border:1px solid #1C232B; padding:4px 8px; font-size:12px; display:none; max-width:280px; }}
</style></head><body><canvas id="c"></canvas><div id="tip"></div>
<script>
const D = {_j(data)}, cv = document.getElementById('c'), ctx = cv.getContext('2d'), tip = document.getElementById('tip');
const dpr = window.devicePixelRatio || 1, COL = ['{DOWN}', '#FFB347', '{UP}'];
let ang = -Math.PI / 2, dots = [], last = performance.now(), still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function rnd(s) {{ const x = Math.sin(s * 9301 + 49297) * 233280; return x - Math.floor(x); }}
function layout() {{
  cv.width = cv.clientWidth * dpr; cv.height = cv.clientHeight * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = cv.clientWidth, h = cv.clientHeight, cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 40;
  const byStage = {{}}; D.signs.forEach(s => (byStage[s.stage] = byStage[s.stage] || []).push(s));
  dots = [];
  for (let st = 1; st <= 6; st++) {{
    const list = byStage[st] || [], a0 = -Math.PI / 2 + (st - 1) * Math.PI / 3;
    list.forEach((s, i) => {{ const a = a0 + Math.PI / 3 * (0.12 + 0.76 * (i + 0.5) / list.length), r = R * (0.32 + 0.6 * rnd(st * 31 + i));
      dots.push({{ ...s, a: a, x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), glow: 0 }}); }});
  }}
  return {{ w, h, cx, cy, R }};
}}
let G = layout();
function frame(now) {{
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (!still) ang += dt * 1.1;
  const {{ w, h, cx, cy, R }} = G; ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = 'rgba(232,33,43,.25)'; ctx.lineWidth = 1;
  [0.33, 0.66, 1].forEach(f => {{ ctx.beginPath(); ctx.arc(cx, cy, R * f, 0, 7); ctx.stroke(); }});
  ctx.font = '11px {MONO}'; ctx.textAlign = 'center';
  for (let st = 1; st <= 6; st++) {{
    const a = -Math.PI / 2 + (st - 1) * Math.PI / 3; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a)); ctx.stroke();
    const am = a + Math.PI / 6; ctx.fillStyle = '{MUTED}'; ctx.fillText(st + ' · ' + D.stages[st], cx + (R + 22) * Math.cos(am), cy + (R + 22) * Math.sin(am) + 4);
  }}
  const g = ctx.createConicGradient ? ctx.createConicGradient(ang - 0.9, cx, cy) : null;
  if (g) {{ g.addColorStop(0, 'rgba(232,33,43,0)'); g.addColorStop(0.14, 'rgba(232,33,43,.38)'); g.addColorStop(0.145, 'rgba(232,33,43,0)'); g.addColorStop(1, 'rgba(232,33,43,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fill(); }}
  ctx.strokeStyle = '{RED}'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + R * Math.cos(ang), cy + R * Math.sin(ang)); ctx.stroke();
  dots.forEach(d => {{
    let diff = ((ang - d.a) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
    if (diff < 0.08) d.glow = 1; d.glow = still ? 0.6 : Math.max(0, d.glow - dt * 0.35);
    const c = d.light == null ? '{DIM}' : COL[d.light];
    ctx.globalAlpha = 0.35 + 0.65 * d.glow; ctx.fillStyle = c; ctx.shadowColor = c; ctx.shadowBlur = 18 * d.glow;
    ctx.beginPath(); ctx.arc(d.x, d.y, 4 + 3 * d.glow, 0, 7); ctx.fill(); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
  }});
  ctx.fillStyle = '#000'; ctx.beginPath(); ctx.arc(cx, cy, 46, 0, 7); ctx.fill(); ctx.strokeStyle = '{RED}'; ctx.stroke();
  ctx.fillStyle = '{TEXT}'; ctx.font = 'bold 18px {MONO}'; ctx.fillText(D.score, cx, cy + 2);
  ctx.fillStyle = '{RED}'; ctx.font = '10px {MONO}'; ctx.fillText(D.band.toUpperCase(), cx, cy + 18);
  requestAnimationFrame(frame);
}}
requestAnimationFrame(frame);
window.addEventListener('resize', () => {{ G = layout(); }});
cv.addEventListener('mousemove', e => {{ const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
  const hit = dots.find(d => Math.hypot(d.x - x, d.y - y) < 9);
  if (hit) {{ tip.style.display = 'block'; tip.style.left = (x + 14) + 'px'; tip.style.top = (y + 10) + 'px';
    tip.innerHTML = ['🔴 no sign', '🟠 some sign', '🟢 happening'][hit.light] ? (['🔴 no sign', '🟠 some sign', '🟢 happening'][hit.light] + ' · ') : '⚪ no data · ';
    tip.innerHTML += hit.name.replace(/</g, '&lt;'); }} else tip.style.display = 'none'; }});
</script></body></html>"""
