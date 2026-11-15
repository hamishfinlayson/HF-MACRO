"""scenes_assets.py - the v42 page animations (generated from the preview; edit the preview, not this file)."""
SCENES_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HF Macro page features</title>
__FONTS__
<style>
:root { --bg:#050506; --p:#09090B; --hl:#16151A; --hl2:#222027; --t:#CFCBC7; --hi:#F1EEEA; --m:#6F6C72; --m2:#9A969D; --red:#FF2A2A; --cy:#57D3F2; --up:#3FD68A; --dn:#FF5C6C; --am:#FFB347;
        --sans:"Inter","Helvetica Neue",Helvetica,Arial,sans-serif; --mono:"JetBrains Mono","SF Mono",Consolas,Menlo,monospace; --e:cubic-bezier(.16,1,.3,1); --io:cubic-bezier(.65,0,.35,1); }
* { box-sizing:border-box; } html,body { margin:0; background:transparent; color:var(--t); font-family:var(--sans); font-weight:300; overflow:hidden; }
.mono { font-family:var(--mono); } .up { color:var(--up); } .dn { color:var(--dn); }
#tabs { position:sticky; top:0; z-index:9; display:flex; flex-wrap:wrap; gap:2px; justify-content:center; padding:12px; background:linear-gradient(var(--bg) 70%, transparent); }
#tabs button { background:none; border:1px solid transparent; color:var(--m); font:10px var(--mono); letter-spacing:.14em; padding:7px 11px; cursor:pointer; text-transform:uppercase; transition:color .3s, border-color .3s; }
#tabs button.on { color:var(--hi); border-color:var(--hl2); } #tabs .rp { color:var(--red); border-color:var(--hl2); margin-left:12px; }
#view { position:relative; }
.hd { display:flex; align-items:baseline; gap:16px; padding-bottom:12px; margin:18px 0 14px; position:relative; }
.hd:after { content:""; position:absolute; left:0; right:0; bottom:0; height:1px; background:var(--hl2); transform-origin:left; animation:line 1.5s var(--io) both; } @keyframes line { from { transform:scaleX(0); } }
.hd .n { font:10px var(--mono); color:var(--red); letter-spacing:.16em; } .hd .t { font-size:24px; color:var(--hi); } .hd .s { font-size:11px; color:var(--m); }
.stage { position:relative; height:100vh; border:1px solid var(--hl); background:radial-gradient(60% 50% at 50% 45%, rgba(255,42,42,.035), transparent 70%), var(--p); overflow:hidden; }
.stage canvas, .stage svg { position:absolute; inset:0; width:100%; height:100%; }
.note { font:9px var(--mono); color:var(--m); letter-spacing:.12em; margin-top:14px; text-transform:uppercase; line-height:1.8; }
.lbl { position:absolute; font:10px var(--mono); letter-spacing:.12em; color:var(--m2); pointer-events:none; white-space:nowrap; }
.rise { opacity:0; transform:translateY(12px); filter:blur(3px); animation:rise 1s var(--e) forwards; } @keyframes rise { to { opacity:1; transform:none; filter:none; } }
.ctl { position:absolute; z-index:4; display:flex; gap:2px; } .ctl button { background:rgba(5,5,6,.8); border:1px solid var(--hl2); color:var(--m); font:10px var(--mono); letter-spacing:.12em; padding:6px 10px; cursor:pointer; }
.ctl button.on { color:var(--bg); background:var(--hi); border-color:var(--hi); }
.side { position:absolute; right:0; top:0; bottom:0; width:300px; border-left:1px solid var(--hl); background:rgba(9,9,11,.85); padding:22px; z-index:3; }
.side .h { font:9px var(--mono); letter-spacing:.22em; color:var(--m); margin:0 0 10px; text-transform:uppercase; } .side .big { font:300 30px var(--mono); color:var(--hi); margin-bottom:18px; }
.row { display:flex; justify-content:space-between; font-size:12px; padding:7px 0; border-bottom:1px solid var(--hl); transition:all .7s var(--e); }
.card { position:absolute; width:150px; height:58px; border:1px solid var(--hl2); background:#0B0B0E; padding:8px 10px; font-size:10px; line-height:1.35; color:var(--m2); transition:all 1.2s var(--e); overflow:hidden; }
.card b { display:block; font:500 10px var(--mono); color:var(--hi); margin-bottom:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card.live { border-color:var(--up); box-shadow:0 0 18px rgba(63,214,138,.25); } .card.dead { opacity:.18; filter:grayscale(1); }
</style></head><body>
<div id="view"></div>
<script>
const D = __D__;
const $ = (s, r = document) => r.querySelector(s), view = $('#view'), NS = 'http://www.w3.org/2000/svg';
const ease = u => u * u * u * (u * (u * 6 - 15) + 10), cl = v => Math.max(0, Math.min(1, v));
let rafs = [], timers = [];
const loop = f => { let last = performance.now(); const g = t => { last = performance.now(); f(t); rafs.push(requestAnimationFrame(g)); }; rafs.push(requestAnimationFrame(g));
  timers.push(setInterval(() => { if (performance.now() - last > 450) { try { f(performance.now()); } catch (e) {} } }, 120)); };  // keeps drawing if the browser pauses frames
const later = (f, ms) => timers.push(setTimeout(f, ms));
function canvas(stage) { const c = document.createElement('canvas'); stage.appendChild(c); const W = stage.clientWidth, H = stage.clientHeight, dpr = Math.min(2, devicePixelRatio || 1);
  c.width = W * dpr; c.height = H * dpr; const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); return [g, W, H]; }
function shell() { view.innerHTML = `<div class="stage rise"></div>`; return $('.stage'); }

// ================================================================ 1. MARKETS: the trading day around the world
function markets() {
  const st = shell('MKT · WEI', 'The trading day around the world', 'each market lights up as its session opens · glow = today\'s move',
    'Markets and World equities · a sunlight band sweeps west across the world clock; every index opens with a pulse and its move, then the board ranks them · sample moves in this preview, the app uses the real ones');
  const [g, W, H] = canvas(st), M = D.mkts, X = lon => 40 + (W - 360) * (lon + 130) / 290, Y = lat => H * .55 - lat * 5.2;
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = '<div class="h">Ranked by today</div><div id="rk" style="position:relative"></div>'; st.appendChild(side);
  const rk = $('#rk', side); const rows = M.map(m => { const d = document.createElement('div'); d.className = 'row'; d.style.cssText += ';position:absolute;left:0;right:0;opacity:0'; d.innerHTML = `<span>${m.n}</span><span class="mono ${m.d >= 0 ? 'up' : 'dn'}">${m.d >= 0 ? '+' : ''}${m.d.toFixed(2)}%</span>`; rk.appendChild(d); return d; });
  const placed = []; M.forEach(m => { let ly = Y(m.lat) - 6; const lx = X(m.lon) + 10; while (placed.some(([px, py]) => Math.abs(px - lx) < 120 && Math.abs(py - ly) < 15)) ly += 15; placed.push([lx, ly]); m.ly = ly; });
  const labels = M.map(m => { const l = document.createElement('div'); l.className = 'lbl'; l.style.left = (X(m.lon) + 10) + 'px'; l.style.top = m.ly + 'px'; l.style.opacity = 0; l.style.transition = 'opacity .6s'; l.innerHTML = `${m.n} <span class="${m.d >= 0 ? 'up' : 'dn'}">${m.d >= 0 ? '+' : ''}${m.d.toFixed(1)}%</span>`; st.appendChild(l); return l; });
  const t0 = performance.now(), opened = new Set();
  loop(now => { const t = (now - t0) / 1000, sweep = 1 - cl(t / 7) ; const sx = 40 + (W - 360) * sweep; g.clearRect(0, 0, W, H);
    // hour grid + equator
    g.strokeStyle = 'rgba(241,238,234,.05)'; for (let lon = -120; lon <= 160; lon += 20) { g.beginPath(); g.moveTo(X(lon), 30); g.lineTo(X(lon), H - 30); g.stroke(); }
    g.fillStyle = 'rgba(241,238,234,.25)'; g.font = '9px JetBrains Mono, monospace'; ['NEW YORK', 'LONDON', 'FRANKFURT', 'MUMBAI', 'HONG KONG', 'TOKYO', 'SYDNEY'].forEach((c, i) => { const lon = [-74, 0, 9, 73, 114, 140, 151][i]; g.fillText(c, X(lon) - 20, H - 14); });
    // sunlight band
    const gr = g.createLinearGradient(sx - 160, 0, sx + 40, 0); gr.addColorStop(0, 'rgba(255,42,42,0)'); gr.addColorStop(.8, 'rgba(255,42,42,.08)'); gr.addColorStop(1, 'rgba(255,42,42,0)');
    g.fillStyle = gr; g.fillRect(sx - 160, 0, 200, H); g.strokeStyle = 'rgba(255,42,42,.6)'; g.beginPath(); g.moveTo(sx, 20); g.lineTo(sx, H - 30); g.stroke();
    M.forEach((m, i) => { const x = X(m.lon), y = Y(m.lat), on = x >= sx - 2; if (on && !opened.has(i)) { opened.add(i); m.t = t; labels[i].style.opacity = 1; }
      const col = m.d >= 0 ? '63,214,138' : '255,92,108', age = on ? t - m.t : 0, r = on ? 3 + Math.min(14, Math.abs(m.d) * 7) : 2;
      if (on) { g.fillStyle = `rgba(${col},.12)`; g.beginPath(); g.arc(x, y, r * 2.2, 0, 7); g.fill(); if (age < 1.2) { g.strokeStyle = `rgba(${col},${1 - age / 1.2})`; g.beginPath(); g.arc(x, y, r + age * 40, 0, 7); g.stroke(); } }
      g.fillStyle = on ? `rgb(${col})` : '#2A2830'; g.beginPath(); g.arc(x, y, on ? 3.5 : 2.5, 0, 7); g.fill(); });
    // ranking appears as markets open
    const order = M.map((m, i) => [m.d, i]).filter(([, i]) => opened.has(i)).sort((a, b) => b[0] - a[0]);
    order.forEach(([, i], r) => { rows[i].style.top = (r * 31) + 'px'; rows[i].style.opacity = 1; }); });
}

// ================================================================ 2. FX: currency gravity
function fxg() {
  const st = shell('FX', 'Currency gravity', 'each currency is a planet sized and placed by its strength · switch the period',
    'FX page · real closing rates (13 Nov 2026): strong currencies drift to the top-right and swell, weak ones sink; changing the period sends every planet gliding to its new orbit · threads join the strongest and weakest pair');
  const [g, W, H] = canvas(st), C = D.fx; let per = 'w1';
  const ctl = document.createElement('div'); ctl.className = 'ctl'; ctl.style.cssText = 'left:16px;top:16px'; ctl.innerHTML = ['d1', 'w1', 'm1', 'y1'].map(p => `<button data-p="${p}" class="${p === per ? 'on' : ''}">${{ d1: '1 DAY', w1: '1 WEEK', m1: '1 MONTH', y1: '1 YEAR' }[p]}</button>`).join(''); st.appendChild(ctl);
  ctl.onclick = e => { const p = e.target.dataset.p; if (!p) return; per = p; ctl.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.p === p)); target(); };
  const P = C.map((c, i) => ({ ...c, x: W / 2, y: H / 2, tx: 0, ty: 0, r: 10, tr: 10, a: i * 2.4 }));
  function target() { const v = P.map(p => p[per]), lo = Math.min(...v), hi = Math.max(...v);
    P.forEach((p, i) => { const s = (p[per] - lo) / ((hi - lo) || 1); const ang = -Math.PI * .85 + i * (Math.PI * 1.7 / (P.length - 1)); p.tx = W * .12 + W * .76 * (i / (P.length - 1)); p.ty = H * .82 - s * H * .64 + Math.sin(i * 1.7) * 18; p.tr = 9 + s * 22; p.s = s; }); }
  target(); const t0 = performance.now();
  loop(now => { const t = (now - t0) / 1000; g.clearRect(0, 0, W, H);
    g.strokeStyle = 'rgba(241,238,234,.05)'; for (let k = 1; k < 5; k++) { g.beginPath(); g.moveTo(0, H * k / 5); g.lineTo(W, H * k / 5); g.stroke(); }
    g.fillStyle = '#6F6C72'; g.font = '9px JetBrains Mono, monospace'; g.fillText('STRONGER ▲', 18, 70); g.fillText('WEAKER ▼', 18, H - 20);
    P.forEach(p => { p.x += (p.tx - p.x) * .06; p.y += (p.ty - p.y) * .06 + Math.sin(t * .8 + p.a) * .15; p.r += (p.tr - p.r) * .06; });
    const s = [...P].sort((a, b) => b[per] - a[per]), a = s[0], b = s[s.length - 1];
    g.strokeStyle = 'rgba(255,42,42,.35)'; g.setLineDash([3, 5]); g.lineDashOffset = -t * 20; g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke(); g.setLineDash([]);
    P.forEach(p => { const col = p[per] >= 0 ? [63, 214, 138] : [255, 92, 108]; const gr = g.createRadialGradient(p.x - p.r * .3, p.y - p.r * .3, 1, p.x, p.y, p.r);
      gr.addColorStop(0, `rgba(${col},.95)`); gr.addColorStop(1, `rgba(${col},.15)`); g.fillStyle = gr; g.beginPath(); g.arc(p.x, p.y, p.r, 0, 7); g.fill();
      g.strokeStyle = `rgba(${col},.35)`; g.beginPath(); g.ellipse(p.x, p.y, p.r * 1.7, p.r * .5, -.3, 0, 7); g.stroke();
      g.fillStyle = '#F1EEEA'; g.font = '11px JetBrains Mono, monospace'; g.textAlign = 'center'; g.fillText(p.c, p.x, p.y - p.r - 8);
      g.fillStyle = col[0] > 200 ? '#FF5C6C' : '#3FD68A'; g.font = '10px JetBrains Mono, monospace'; g.fillText((p[per] >= 0 ? '+' : '') + p[per].toFixed(2) + '%', p.x, p.y + p.r + 14); g.textAlign = 'left'; }); });
}

// ================================================================ 3. YIELD CURVES: morphing through time
function curves() {
  const st = shell('CRV', 'The yield curve through time', 'US Treasury curve, 2006 → today · red years = recession',
    'Yield curves page · the curve morphs year by year; when the short end rises above the long end (inverted) the area turns red and the recession clock starts; a trail of past curves fades behind · illustrative curves in this preview, the app uses real FRED Treasury yields');
  const [g, W, H] = canvas(st), K = D.curves, TEN = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y'], XM = [0, .08, .16, .3, .52, .76, 1];
  const X = i => 90 + (W - 380) * XM[i], Y = v => H - 70 - v * (H - 140) / 6;
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = '<div class="h">Date</div><div class="big" id="cy">—</div><div class="h">10-year minus 3-month</div><div class="big" id="cs">—</div><div class="h" id="cr"></div>'; st.appendChild(side);
  const t0 = performance.now(), per = 1.6, trail = [];
  loop(now => { const t = (now - t0) / 1000, f = Math.min(K.length - 1.001, t / per), k = Math.floor(f), u = ease(f - k), A = K[k], B = K[k + 1];
    const v = A.y.map((a, i) => a + (B.y[i] - a) * u), spread = v[5] - v[0], inv = spread < 0, rec = (u < .5 ? A : B).rec;
    g.clearRect(0, 0, W, H); g.strokeStyle = 'rgba(241,238,234,.06)'; g.fillStyle = '#6F6C72'; g.font = '10px JetBrains Mono, monospace';
    for (let p = 0; p <= 6; p++) { g.beginPath(); g.moveTo(80, Y(p)); g.lineTo(W - 320, Y(p)); g.stroke(); g.fillText(p + '%', 50, Y(p) + 4); }
    TEN.forEach((n, i) => g.fillText(n, X(i) - 8, H - 44));
    if (Math.floor(t / per) !== trail.lastK) { trail.lastK = Math.floor(t / per); trail.push(A.y.slice()); if (trail.length > 8) trail.shift(); }
    trail.forEach((tr, j) => { g.strokeStyle = `rgba(241,238,234,${.03 + j * .012})`; g.beginPath(); tr.forEach((y, i) => i ? g.lineTo(X(i), Y(y)) : g.moveTo(X(i), Y(y))); g.stroke(); });
    const gr = g.createLinearGradient(0, Y(6), 0, Y(0)); gr.addColorStop(0, inv ? 'rgba(255,42,42,.28)' : 'rgba(87,211,242,.22)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.beginPath(); v.forEach((y, i) => i ? g.lineTo(X(i), Y(y)) : g.moveTo(X(i), Y(y))); g.lineTo(X(6), Y(0)); g.lineTo(X(0), Y(0)); g.fill();
    g.strokeStyle = inv ? '#FF2A2A' : '#57D3F2'; g.lineWidth = 2.4; g.beginPath(); v.forEach((y, i) => i ? g.lineTo(X(i), Y(y)) : g.moveTo(X(i), Y(y))); g.stroke(); g.lineWidth = 1;
    v.forEach((y, i) => { g.fillStyle = '#F1EEEA'; g.beginPath(); g.arc(X(i), Y(y), 3, 0, 7); g.fill(); });
    if (rec) { g.fillStyle = 'rgba(255,42,42,.9)'; g.font = '11px JetBrains Mono, monospace'; g.fillText('■ US RECESSION', 96, 40); }
    $('#cy', side).textContent = (u < .5 ? A : B).d; $('#cs', side).innerHTML = `<span class="${inv ? 'dn' : 'up'}">${spread >= 0 ? '+' : ''}${spread.toFixed(2)}</span>`;
    $('#cr', side).innerHTML = inv ? '<span style="color:var(--red)">INVERTED · short rates above long rates</span>' : 'NORMAL · long rates above short rates';
    if (t > per * (K.length + 2)) { trail.length = 0; } });
}

// ================================================================ 4. TAKEOVERS: deal radar
function takeovers() {
  const st = shell('TAKEOVERS', 'Deal radar', 'the sweep reads new SEC filings · a lock-on box marks each company a big private-equity firm is buying',
    'Takeovers page · its own animation instead of the spider: a radar sweep, targets appear as blips, then a lock-on box closes on each one with the buyer and the filing type · sample deals in this preview, the app uses the real SEC filings');
  const [g, W, H] = canvas(st), cx = W * .38, cy = H * .5, R = Math.min(W, H) * .42, T = D.deals;
  const pts = T.map((d, i) => ({ ...d, a: (i * 2.399) % 6.283, r: R * (.38 + .55 * ((i * .618) % 1)), seen: 0 }));
  const log = document.createElement('div'); log.className = 'side'; log.innerHTML = '<div class="h">Locked targets</div><div id="dl"></div>'; st.appendChild(log);
  let ang = -Math.PI / 2, last = performance.now();
  loop(now => { const dt = Math.min(.05, (now - last) / 1000); last = now; ang += dt * 1.1; g.clearRect(0, 0, W, H);
    g.strokeStyle = 'rgba(255,42,42,.18)'; [.25, .5, .75, 1].forEach(f => { g.beginPath(); g.arc(cx, cy, R * f, 0, 7); g.stroke(); });
    g.beginPath(); g.moveTo(cx - R, cy); g.lineTo(cx + R, cy); g.moveTo(cx, cy - R); g.lineTo(cx, cy + R); g.stroke();
    const gr = g.createConicGradient ? g.createConicGradient(ang - 1, cx, cy) : null; if (gr) { gr.addColorStop(0, 'rgba(255,42,42,0)'); gr.addColorStop(.159, 'rgba(255,42,42,.28)'); gr.addColorStop(.16, 'rgba(255,42,42,0)'); gr.addColorStop(1, 'rgba(255,42,42,0)'); g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, R, 0, 7); g.fill(); }
    g.strokeStyle = '#FF2A2A'; g.lineWidth = 1.5; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + R * Math.cos(ang), cy + R * Math.sin(ang)); g.stroke(); g.lineWidth = 1;
    pts.forEach(p => { const diff = ((ang - p.a) % 6.283 + 6.283) % 6.283; const x = cx + p.r * Math.cos(p.a), y = cy + p.r * Math.sin(p.a);
      if (diff < .05 && !p.seen) { p.seen = now; const d = document.createElement('div'); d.className = 'row'; d.style.opacity = 0; d.innerHTML = `<span><b style="color:var(--hi);font-weight:400">${p.t}</b><br><span style="color:var(--m);font-size:10px">${p.b} · ${p.f}</span></span><span class="mono" style="color:var(--red);font-size:10px">LOCK</span>`; $('#dl', log).prepend(d); requestAnimationFrame(() => d.style.opacity = 1); }
      if (!p.seen) { g.fillStyle = 'rgba(241,238,234,.15)'; g.beginPath(); g.arc(x, y, 1.5, 0, 7); g.fill(); return; }
      const age = (now - p.seen) / 1000, k = ease(cl(age / .9)), s = 40 - 26 * k;
      g.fillStyle = '#FF2A2A'; g.beginPath(); g.arc(x, y, 3, 0, 7); g.fill();
      g.strokeStyle = `rgba(255,42,42,${.4 + .6 * k})`; g.beginPath(); [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([a, b]) => { g.moveTo(x + a * s, y + b * s); g.lineTo(x + a * s - a * 6, y + b * s); g.moveTo(x + a * s, y + b * s); g.lineTo(x + a * s, y + b * s - b * 6); }); g.stroke();
      if (k > .9) { g.fillStyle = '#F1EEEA'; g.font = '10px JetBrains Mono, monospace'; g.fillText(p.t, x + 20, y - 6); g.fillStyle = '#6F6C72'; g.fillText(p.b, x + 20, y + 8); } });
    if (pts.every(p => p.seen) && now - Math.max(...pts.map(p => p.seen)) > 4000) { pts.forEach(p => p.seen = 0); $('#dl', log).innerHTML = ''; } });
}

// ================================================================ 5. EVENT LAB: the strategy graveyard
function graveyard() {
  const st = shell('EVENT LAB', 'The strategy graveyard', `${D.pub.total} published strategies · only ${D.pub.after} still worked after they were published`,
    'Event Lab · every published strategy falls into place as a card; then the test runs: the ones that kept working after publication light up green and the rest fade to grey; the counter shows the real numbers from your Open Asset Pricing test · real figures');
  const N = D.pub.total, cols = 26, cw = (st.clientWidth - 330) / cols, ch = (st.clientHeight - 16) / Math.ceil(N / cols);
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = `<div class="h">Still working after publication</div><div class="big" id="gc">0 / ${N}</div><div class="h">Average return per year</div><div style="font-size:12px;line-height:2">Before publication <b class="mono" style="color:var(--hi)">${D.pub.before_avg}%</b><br>After publication <b class="mono" style="color:var(--hi)">${D.pub.after_avg}%</b><br>Still working since 2015 <b class="mono" style="color:var(--hi)">${D.pub.since2015}</b></div><div class="h" style="margin-top:20px">What survived</div>${D.pub.themes.map(t => `<div class="row"><span>${t[0]}</span><span class="mono">${t[1]}</span></div>`).join('')}`; st.appendChild(side);
  const live = new Set(); const rnd = i => { const x = Math.sin(i * 9301 + 49297) * 233280; return x - Math.floor(x); };
  const idx = [...Array(N).keys()].sort((a, b) => rnd(a) - rnd(b)).slice(0, D.pub.after); idx.forEach(i => live.add(i));
  const cells = []; for (let i = 0; i < N; i++) { const d = document.createElement('div'); d.style.cssText = `position:absolute;left:${(i % cols) * cw + 8}px;top:${-40}px;width:${cw - 4}px;height:${ch - 4}px;border:1px solid var(--hl2);background:#0D0D10;opacity:0;transition:top 1s var(--e) ${(i % cols) * .015 + Math.floor(i / cols) * .05}s, opacity .6s ${(i % cols) * .015 + Math.floor(i / cols) * .05}s, background .8s, border-color .8s, box-shadow .8s`; st.appendChild(d); cells.push(d); }
  requestAnimationFrame(() => requestAnimationFrame(() => cells.forEach((d, i) => { d.style.top = (Math.floor(i / cols) * ch + 8) + 'px'; d.style.opacity = 1; })));
  let n = 0; const order = [...Array(N).keys()].sort((a, b) => rnd(a + 7) - rnd(b + 7));
  later(() => { order.forEach((i, k) => later(() => { const d = cells[i]; if (live.has(i)) { d.style.background = 'rgba(63,214,138,.55)'; d.style.borderColor = '#3FD68A'; d.style.boxShadow = '0 0 10px rgba(63,214,138,.4)'; n++; $('#gc', side).textContent = n + ' / ' + N; } else { d.style.background = '#111013'; d.style.opacity = .3; } }, k * 22)); }, 2200);
}

const LAND = [[[-168,65],[-140,70],[-95,72],[-80,63],[-60,55],[-66,45],[-75,35],[-81,25],[-97,26],[-105,20],[-95,16],[-83,9],[-78,8],[-90,15],[-105,22],[-117,32],[-125,40],[-124,48],[-135,58],[-150,60],[-165,60]],
  [[-50,60],[-20,70],[-30,83],[-60,82],[-70,76]], [[-80,10],[-60,10],[-50,0],[-35,-7],[-40,-22],[-55,-35],[-68,-55],[-75,-50],[-72,-30],[-80,-5]],
  [[-10,36],[0,43],[-5,48],[-2,51],[5,54],[8,57],[12,56],[20,60],[28,70],[40,68],[45,55],[40,45],[28,41],[20,40],[15,38],[8,44],[3,43]],
  [[-17,15],[-15,28],[-5,36],[10,37],[32,31],[35,28],[43,12],[51,11],[40,-10],[35,-25],[20,-35],[12,-17],[9,4],[-8,4]],
  [[28,41],[40,45],[45,55],[40,68],[70,73],[110,77],[140,72],[180,68],[160,60],[142,52],[130,42],[122,30],[110,20],[105,10],[100,13],[98,8],[92,21],[80,15],[77,8],[72,20],[60,25],[50,30],[57,23],[52,16],[43,13],[35,30],[36,36]],
  [[114,-22],[122,-18],[131,-12],[142,-11],[146,-18],[153,-28],[150,-37],[140,-38],[132,-32],[115,-34]], [[130,31],[135,34],[140,36],[142,40],[141,45],[139,42],[135,35]],
  [[-5,50],[1,51],[0,53],[-3,56],[-6,58],[-5,55]], [[95,5],[105,-6],[120,-9],[140,-8],[130,-2],[118,5],[108,2]]];
const inPoly = (x, y, P) => { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, yi] = P[i], [xj, yj] = P[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
// ================================================================ 6. COUNTRY: the globe
function globe() {
  const st = shell('CTRY', 'Country profiles', 'the globe spins to the country you pick and its numbers count up',
    'Country page · a dotted globe turns to the chosen economy, a pin drops, and its IMF figures roll in beside it; click another country to fly there · sample figures in this preview, the app uses the real IMF data');
  const [g, W, H] = canvas(st), cx = W * .36, cy = H * .5, R = Math.min(W, H) * .42, C = D.countries;
  const side = document.createElement('div'); side.className = 'side'; st.appendChild(side);
  const ctl = document.createElement('div'); ctl.className = 'ctl'; ctl.style.cssText = 'left:16px;top:16px;flex-wrap:wrap;max-width:520px'; ctl.innerHTML = C.map((c, i) => `<button data-i="${i}">${c.code}</button>`).join(''); st.appendChild(ctl);
  const pts = []; for (let i = 0; i < 9000; i++) { const y = 1 - 2 * (i + .5) / 9000, r = Math.sqrt(1 - y * y), th = i * 2.399963, x = Math.cos(th) * r, z = Math.sin(th) * r;
    const lat = Math.asin(y) * 180 / Math.PI, lon = Math.atan2(z, x) * 180 / Math.PI, land = LAND.some(P => inPoly(lon, lat, P)); if (land || i % 9 === 0) pts.push([x, y, z, land]); }
  let rot = 0, trot = 0, tilt = .3, cur = 0;
  function pick(i) { cur = i; const c = C[i]; trot = -c.lon * Math.PI / 180 + Math.PI / 2; ctl.querySelectorAll('button').forEach((b, j) => b.classList.toggle('on', j === i));
    side.innerHTML = `<div class="h">${c.code}</div><div style="font-size:24px;color:var(--hi);margin-bottom:18px">${c.name}</div>` + c.k.map(([n, v, u]) => `<div class="h">${n}</div><div class="big" data-v="${v}" data-u="${u}">0</div>`).join('') + (c.k.length ? '' : '<div class="h" style="line-height:1.8">IMF figures appear here once the Country page has downloaded them</div>');
    side.querySelectorAll('[data-v]').forEach((el, j) => { const to = +el.dataset.v, t0 = performance.now() + 600 + j * 120; (function f(t) { const k = ease(cl((t - t0) / 1400)); el.textContent = (to * k).toFixed(1) + el.dataset.u; if (k < 1) requestAnimationFrame(f); })(t0); }); }
  ctl.onclick = e => { if (e.target.dataset.i) pick(+e.target.dataset.i); }; pick(0);
  let auto = performance.now(); loop(now => { if (now - auto > 6000) { auto = now; pick((cur + 1) % C.length); }
    let d = trot - rot; d = Math.atan2(Math.sin(d), Math.cos(d)); rot += d * .05; g.clearRect(0, 0, W, H);
    const gr = g.createRadialGradient(cx - R * .3, cy - R * .3, R * .1, cx, cy, R * 1.1); gr.addColorStop(0, 'rgba(87,211,242,.06)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, R, 0, 7); g.fill();
    g.strokeStyle = 'rgba(241,238,234,.1)'; g.beginPath(); g.arc(cx, cy, R, 0, 7); g.stroke();
    const cr = Math.cos(rot), sr = Math.sin(rot), ct = Math.cos(tilt), stt = Math.sin(tilt);
    const proj = ([x, y, z]) => { const x1 = x * cr - z * sr, z1 = x * sr + z * cr, y1 = y * ct - z1 * stt, z2 = y * stt + z1 * ct; return [cx + x1 * R, cy - y1 * R, z2]; };
    pts.forEach(p => { const [x, y, z] = proj(p); if (z < 0) return; g.fillStyle = p[3] ? `rgba(241,238,234,${.18 + z * .6})` : `rgba(87,211,242,${.04 + z * .08})`; const sz = p[3] ? 1.6 : 1; g.fillRect(x, y, sz, sz); });
    C.forEach((c, i) => { const la = c.lat * Math.PI / 180, lo = c.lon * Math.PI / 180; const [x, y, z] = proj([Math.cos(la) * Math.cos(lo), Math.sin(la), Math.cos(la) * Math.sin(lo)]); if (z < 0) return;
      const on = i === cur; g.fillStyle = on ? '#FF2A2A' : 'rgba(87,211,242,.7)'; g.beginPath(); g.arc(x, y, on ? 5 : 2.5, 0, 7); g.fill();
      if (on) { const p = (now / 1000) % 1.4 / 1.4; g.strokeStyle = `rgba(255,42,42,${1 - p})`; g.beginPath(); g.arc(x, y, 5 + p * 30, 0, 7); g.stroke(); g.fillStyle = '#F1EEEA'; g.font = '11px JetBrains Mono, monospace'; g.fillText(c.name.toUpperCase(), x + 12, y - 8); } }); });
}

// ================================================================ 7. CALENDAR: countdown timeline
function calendar() {
  const st = shell('CAL', 'Next releases', 'a live countdown to the next big number · the timeline slides as each one arrives',
    'Calendar page · the timeline of upcoming releases glides left in real time; the next one gets a ticking countdown and the previous reading beside it · sample dates in this preview, the app uses the real FRED release calendar');
  const [g, W, H] = canvas(st), E = D.cal, now0 = Date.now(), DAY = 864e5, X = ms => 80 + (ms - now0) / (14 * DAY) * (W - 160);
  const big = document.createElement('div'); big.style.cssText = 'position:absolute;left:0;right:0;top:70px;text-align:center'; st.appendChild(big);
  loop(() => { const now = Date.now(), nx = E.find(e => now0 + e.h * 36e5 > now) || E[0], left = now0 + nx.h * 36e5 - now;
    const d = Math.floor(left / DAY), h = Math.floor(left % DAY / 36e5), m = Math.floor(left % 36e5 / 6e4), s = Math.floor(left % 6e4 / 1e3), ms = Math.floor(left % 1e3 / 10);
    big.innerHTML = `<div style="font:9px var(--mono);letter-spacing:.24em;color:var(--m)">NEXT · ${nx.n.toUpperCase()}</div><div style="font:300 64px var(--mono);color:var(--hi);margin:12px 0">${d}<span style="font-size:18px;color:var(--m)">d </span>${String(h).padStart(2, '0')}<span style="font-size:18px;color:var(--m)">h </span>${String(m).padStart(2, '0')}<span style="font-size:18px;color:var(--m)">m </span>${String(s).padStart(2, '0')}<span style="font-size:22px;color:var(--red)">.${String(ms).padStart(2, '0')}</span></div><div style="font:11px var(--mono);color:var(--m2)">previous ${nx.prev} · ${nx.c}</div>`;
    g.clearRect(0, 0, W, H); const y = H * .68; g.strokeStyle = 'rgba(241,238,234,.15)'; g.beginPath(); g.moveTo(40, y); g.lineTo(W - 40, y); g.stroke();
    for (let k = 0; k <= 14; k++) { const x = X(now0 + k * DAY - (now - now0) * 0); g.strokeStyle = 'rgba(241,238,234,.12)'; g.beginPath(); g.moveTo(x, y - 6); g.lineTo(x, y + 6); g.stroke(); g.fillStyle = '#6F6C72'; g.font = '9px JetBrains Mono, monospace'; g.fillText(new Date(now0 + k * DAY).toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit' }).toUpperCase(), x - 16, y + 24); }
    const xn = X(now); g.strokeStyle = '#FF2A2A'; g.beginPath(); g.moveTo(xn, y - 60); g.lineTo(xn, y + 40); g.stroke(); g.fillStyle = '#FF2A2A'; g.fillText('NOW', xn - 10, y - 66);
    E.forEach((e, i) => { const x = X(now0 + e.h * 36e5), up = i % 2 ? -1 : 1, isN = e === nx; g.strokeStyle = isN ? '#FF2A2A' : 'rgba(87,211,242,.5)'; g.beginPath(); g.moveTo(x, y); g.lineTo(x, y - up * 50); g.stroke();
      g.fillStyle = isN ? '#FF2A2A' : '#57D3F2'; g.beginPath(); g.arc(x, y, isN ? 5 : 3.5, 0, 7); g.fill(); g.fillStyle = isN ? '#F1EEEA' : '#9A969D'; g.font = '10px JetBrains Mono, monospace'; g.fillText(e.n, x - 30, y - up * 58 + (up < 0 ? 12 : 0)); }); });
}

// ================================================================ 8. ECONOMY HEARTBEAT
function heartbeat() {
  const st = shell('US · UK · EA', 'The economy\'s heartbeat', 'one pulse line built from the key indicators · it beats faster and taller when the economy runs hot',
    'US / UK / Euro area pages · an ECG-style line scrolls across the top of each economy page; each beat is the latest monthly reading of growth, jobs and inflation combined, so a hot economy beats fast and tall and a cooling one goes flat · sample readings in this preview, the app uses the real indicators');
  const [g, W, H] = canvas(st), Z = D.beat; let off = 0, last = performance.now(); const buf = [];
  const tag = document.createElement('div'); tag.style.cssText = 'position:absolute;right:24px;top:22px;text-align:right'; st.appendChild(tag);
  function beatShape(u, z) { const a = .35 + Math.max(0, z) * .45; if (u < .1) return 0; if (u < .14) return -.15 * a; if (u < .18) return 1.0 * a; if (u < .22) return -.45 * a; if (u < .3) return .12 * a * Math.sin((u - .22) / .08 * Math.PI); return 0; }
  for (let k = 0; k < W; k++) { const z0 = Z[0].z, per0 = 60 / (52 + z0 * 30); off += 1 / 120; buf.push(beatShape((off % per0) / per0, z0)); }
  loop(now => { const dt = (now - last) / 1000; last = now; const i = Math.floor(now / 2400) % Z.length, z = Z[i].z, bpm = 52 + z * 30, period = 60 / bpm;
    for (let k = 0; k < 2; k++) { off += Math.min(dt, .05) / 2; const u = (off % period) / period; buf.push(beatShape(u, z)); } while (buf.length > W) buf.shift();
    g.clearRect(0, 0, W, H); g.strokeStyle = 'rgba(255,42,42,.06)'; for (let x = 0; x < W; x += 24) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); } for (let y = 0; y < H; y += 24) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
    const mid = H * .55, amp = H * .32; g.strokeStyle = z > .4 ? '#FF2A2A' : z < -.2 ? '#57D3F2' : '#3FD68A'; g.lineWidth = 2; g.shadowColor = g.strokeStyle; g.shadowBlur = 10;
    g.beginPath(); buf.forEach((v, x) => x ? g.lineTo(x, mid - v * amp) : g.moveTo(x, mid - v * amp)); g.stroke(); g.shadowBlur = 0; g.lineWidth = 1;
    g.fillStyle = g.strokeStyle; g.beginPath(); g.arc(buf.length - 1, mid - buf[buf.length - 1] * amp, 4, 0, 7); g.fill();
    tag.innerHTML = `<div style="font:9px var(--mono);letter-spacing:.22em;color:var(--m)">${Z[i].d} · ${Z[i].r}</div><div style="font:300 44px var(--mono);color:var(--hi);margin:6px 0">${Math.round(bpm)}<span style="font-size:14px;color:var(--m)"> BPM</span></div><div style="font:11px var(--mono);color:${z > .4 ? 'var(--red)' : z < -.2 ? 'var(--cy)' : 'var(--up)'}">${z > .4 ? 'IMPROVING FAST' : z < -.2 ? 'WEAKENING' : 'STEADY'} · score ${z >= 0 ? '+' : ''}${z.toFixed(2)}</div>`; });
}

const SCENES = { markets, fxg, curves, takeovers, graveyard, globe, calendar, heartbeat };
(SCENES[D.scene] || markets)();
if (D.owner) {   // used as a full-screen loading screen: fade in, play for at least D.min ms, go when the app is done
  const fe = window.frameElement; let shownAt = 0, closing = false;
  const close = () => { if (closing || !fe) return; closing = true; fe.style.opacity = 0; setTimeout(() => fe.remove(), shownAt ? 600 : 0); };
  setTimeout(() => { if (fe && fe.isConnected && !closing) { fe.style.opacity = 1; fe.style.pointerEvents = 'auto'; shownAt = performance.now(); } }, D.force ? 0 : 150);
  addEventListener('click', close);
  setInterval(() => { let gone = true; try { gone = !parent.document.querySelector('[data-hfl-owner="' + D.owner + '"]'); } catch (e) {}
    if (D.force && shownAt && performance.now() - shownAt > (D.min || 9000)) return close();
    if (!gone || closing) return; if (!shownAt) return close(); if (performance.now() - shownAt > (D.min || 9000)) close(); }, 200);
}
</script></body></html>
'''
