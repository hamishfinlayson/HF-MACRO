"""scenes_assets.py - the v42 page animations (generated from the preview; edit the preview, not this file)."""
SCENES_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HF Macro page features</title>
__FONTS__
<style>
:root { --bg:#050506; --p:#09090B; --hl:#16151A; --hl2:#222027; --t:#CFCBC7; --hi:#F1EEEA; --m:#6F6C72; --m2:#9A969D; --red:#FF2A2A; --cy:#57D3F2; --up:#3FD68A; --dn:#FF5C6C;
        --sans:"Inter","Helvetica Neue",Helvetica,Arial,sans-serif; --mono:"JetBrains Mono","SF Mono",Consolas,Menlo,monospace; --e:cubic-bezier(.16,1,.3,1); --io:cubic-bezier(.65,0,.35,1); }
* { box-sizing:border-box; } html,body { margin:0; background:var(--bg); color:var(--t); font-family:var(--sans); font-weight:300; }
body.embed { background:transparent; overflow:hidden; }
.mono { font-family:var(--mono); } .up { color:var(--up); } .dn { color:var(--dn); }
#tabs { position:sticky; top:0; z-index:9; display:flex; flex-wrap:wrap; gap:2px; justify-content:center; padding:12px; background:linear-gradient(var(--bg) 70%, transparent); }
#tabs button { background:none; border:1px solid transparent; color:var(--m); font:10px var(--mono); letter-spacing:.14em; padding:7px 11px; cursor:pointer; text-transform:uppercase; }
#tabs button.on { color:var(--hi); border-color:var(--hl2); } #tabs .rp { color:var(--red); border-color:var(--hl2); margin-left:12px; }
#view { max-width:1320px; margin:0 auto; padding:6px 28px 60px; position:relative; } body.embed #view { max-width:none; padding:0; }
.hd { display:flex; align-items:baseline; gap:16px; padding-bottom:12px; margin:18px 0 14px; border-bottom:1px solid var(--hl2); }
.hd .n { font:10px var(--mono); color:var(--red); letter-spacing:.16em; } .hd .t { font-size:24px; color:var(--hi); } .hd .s { font-size:11px; color:var(--m); }
.stage { position:relative; height:580px; border:1px solid var(--hl); background:radial-gradient(60% 55% at 45% 45%, rgba(255,42,42,.04), transparent 70%), #070709; overflow:hidden; }
body.embed .stage { height:100vh; border:0; }
.stage canvas { position:absolute; inset:0; width:100%; height:100%; }
.note { font:9px var(--mono); color:var(--m); letter-spacing:.12em; margin-top:14px; text-transform:uppercase; line-height:1.8; }
.side { position:absolute; right:0; top:0; bottom:0; width:290px; border-left:1px solid var(--hl); background:rgba(9,9,11,.82); padding:22px; z-index:3; }
.side .h { font:9px var(--mono); letter-spacing:.22em; color:var(--m); margin:0 0 8px; text-transform:uppercase; } .side .big { font:300 28px var(--mono); color:var(--hi); margin-bottom:16px; }
.row { display:flex; justify-content:space-between; gap:10px; font-size:12px; padding:7px 0; border-bottom:1px solid var(--hl); transition:all .7s var(--e); }
.ctl { position:absolute; z-index:4; display:flex; gap:2px; flex-wrap:wrap; } .ctl button { background:rgba(5,5,6,.8); border:1px solid var(--hl2); color:var(--m); font:10px var(--mono); letter-spacing:.12em; padding:6px 10px; cursor:pointer; }
.ctl button.on { color:var(--bg); background:var(--hi); border-color:var(--hi); }
.holo { background:linear-gradient(rgba(87,211,242,.06) 50%, transparent 50%) 0 0/100% 4px, rgba(9,12,14,.85); border-left:1px solid rgba(87,211,242,.4); }
.holo .big { color:#9BE7F8; text-shadow:0 0 12px rgba(87,211,242,.6); }
.hud { position:absolute; font:10px var(--mono); letter-spacing:.16em; color:var(--m2); z-index:3; pointer-events:none; }
</style></head><body>
<div id="tabs"></div><div id="view"></div>
<script>
const D = __D__;
const EMBED = !!D.scene; if (EMBED) document.body.classList.add('embed');
const $ = (s, r = document) => r.querySelector(s), view = $('#view');
const ease = u => u * u * u * (u * (u * 6 - 15) + 10), cl = v => Math.max(0, Math.min(1, v)), eo = u => 1 - Math.pow(1 - u, 3);
let rafs = [], timers = [];
const loop = f => { let last = performance.now(); const g = t => { last = performance.now(); f(t); rafs.push(requestAnimationFrame(g)); }; rafs.push(requestAnimationFrame(g));
  timers.push(setInterval(() => { if (performance.now() - last > 450) { try { f(performance.now()); } catch (e) {} } }, 120)); };
const later = (f, ms) => timers.push(setTimeout(f, ms));
function canvas(stage) { const c = document.createElement('canvas'); stage.appendChild(c); const W = stage.clientWidth, H = stage.clientHeight, dpr = Math.min(2, devicePixelRatio || 1);
  c.width = W * dpr; c.height = H * dpr; const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); return [g, W, H]; }
function shell(code, title, sub, note) {
  view.innerHTML = EMBED ? `<div class="stage"></div>` : `<div class="hd"><span class="n">${code}</span><span class="t">${title}</span><span class="s">${sub}</span></div><div class="stage"></div><div class="note">${note}</div>`; return $('.stage'); }
function hud(st, html, css) { const h = document.createElement('div'); h.className = 'hud'; h.style.cssText = css; h.innerHTML = html; st.appendChild(h); return h; }
// continents (rough outlines, longitude/latitude) for the globes
const LAND = [[[-168,65],[-140,70],[-95,72],[-80,63],[-60,55],[-66,45],[-75,35],[-81,25],[-97,26],[-105,20],[-95,16],[-83,9],[-78,8],[-90,15],[-105,22],[-117,32],[-125,40],[-124,48],[-135,58],[-150,60],[-165,60]],
  [[-50,60],[-20,70],[-30,83],[-60,82],[-70,76]], [[-80,10],[-60,10],[-50,0],[-35,-7],[-40,-22],[-55,-35],[-68,-55],[-75,-50],[-72,-30],[-80,-5]],
  [[-10,36],[0,43],[-5,48],[-2,51],[5,54],[8,57],[12,56],[20,60],[28,70],[40,68],[45,55],[40,45],[28,41],[20,40],[15,38],[8,44],[3,43]],
  [[-17,15],[-15,28],[-5,36],[10,37],[32,31],[35,28],[43,12],[51,11],[40,-10],[35,-25],[20,-35],[12,-17],[9,4],[-8,4]],
  [[28,41],[40,45],[45,55],[40,68],[70,73],[110,77],[140,72],[180,68],[160,60],[142,52],[130,42],[122,30],[110,20],[105,10],[100,13],[98,8],[92,21],[80,15],[77,8],[72,20],[60,25],[50,30],[57,23],[52,16],[43,13],[35,30],[36,36]],
  [[114,-22],[122,-18],[131,-12],[142,-11],[146,-18],[153,-28],[150,-37],[140,-38],[132,-32],[115,-34]], [[130,31],[135,34],[140,36],[142,40],[141,45],[139,42],[135,35]],
  [[-5,50],[1,51],[0,53],[-3,56],[-6,58],[-5,55]], [[95,5],[105,-6],[120,-9],[140,-8],[130,-2],[118,5],[108,2]]];
const inPoly = (x, y, P) => { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, yi] = P[i], [xj, yj] = P[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
const sph = (lat, lon) => { const la = lat * Math.PI / 180, lo = lon * Math.PI / 180; return [Math.cos(la) * Math.cos(lo), Math.sin(la), Math.cos(la) * Math.sin(lo)]; };
function globeDots(n, oceanEvery) { const pts = []; for (let i = 0; i < n; i++) { const y = 1 - 2 * (i + .5) / n, r = Math.sqrt(1 - y * y), th = i * 2.399963, x = Math.cos(th) * r, z = Math.sin(th) * r;
    const lat = Math.asin(y) * 180 / Math.PI, lon = Math.atan2(z, x) * 180 / Math.PI, land = LAND.some(P => inPoly(lon, lat, P)); if (land || i % oceanEvery === 0) pts.push({ p: [x, y, z], land }); } return pts; }
function rotator(cx, cy, R) { return (v, rot, tilt, scale = 1) => { const [x, y, z] = v, cr = Math.cos(rot), sr = Math.sin(rot), ct = Math.cos(tilt), stl = Math.sin(tilt);
  const x1 = x * cr - z * sr, z1 = x * sr + z * cr, y1 = y * ct - z1 * stl, z2 = y * stl + z1 * ct; return [cx + x1 * R * scale, cy - y1 * R * scale, z2]; }; }

// ================================================================ 1. MARKETS: night globe with light beams
function markets() {
  const st = shell('MKT · WEI', 'Night globe', 'the Earth forms from particles · each market fires a beam as its session opens · arcs join markets moving the same way',
    'Markets / World equities · real daily moves in the app (sample here): green beams up, red beams down, height = size of the move; the camera pulls back to show the web');
  const [g, W, H] = canvas(st), cx = W * .4, cy = H * .52, R = Math.min(W * .3, H * .38), proj = rotator(cx, cy, R), M = D.mkts;
  const dots = globeDots(7000, 7); dots.forEach(d => { const s = 1.6 + Math.random() * 2.4, a = Math.random() * 6.283, b = Math.random() * 3.14; d.s = [Math.cos(a) * Math.sin(b) * s, Math.cos(b) * s, Math.sin(a) * Math.sin(b) * s]; d.dl = Math.random() * .8; });
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = '<div class="h">Sessions opened</div><div class="big" id="mo">0 / ' + M.length + '</div><div class="h">Biggest moves</div><div id="ml"></div>'; st.appendChild(side);
  const order = M.map((m, i) => [m.lon, i]).sort((a, b) => b[0] - a[0]).map(([, i]) => i); M.forEach((m, k) => m.fire = 2.4 + order.indexOf(k) * .38);
  const pairs = []; for (let a = 0; a < M.length; a++) for (let b = a + 1; b < M.length; b++) if (Math.sign(M[a].d) === Math.sign(M[b].d) && Math.abs(M[a].lon - M[b].lon) > 25 && (a * 7 + b) % 3 === 0) pairs.push([a, b]);
  const t0 = performance.now(); let shown = 0;
  loop(now => { const t = (now - t0) / 1000, rot = -1.2 + t * .12, tilt = .32, sc = .78 + .22 * ease(cl(t / 3)); g.clearRect(0, 0, W, H);
    const gl = g.createRadialGradient(cx, cy, R * .2 * sc, cx, cy, R * 1.25 * sc); gl.addColorStop(0, 'rgba(87,211,242,.05)'); gl.addColorStop(.8, 'rgba(87,211,242,.03)'); gl.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gl; g.beginPath(); g.arc(cx, cy, R * 1.25 * sc, 0, 7); g.fill();
    dots.forEach(d => { const k = ease(cl((t - d.dl) / 1.6)), v = k >= 1 ? d.p : [d.s[0] + (d.p[0] - d.s[0]) * k, d.s[1] + (d.p[1] - d.s[1]) * k, d.s[2] + (d.p[2] - d.s[2]) * k];
      const [x, y, z] = proj(v, rot, tilt, sc); if (z < -.05 && k >= 1) return; g.fillStyle = d.land ? `rgba(241,238,234,${(.1 + Math.max(0, z) * .55) * (k < 1 ? .7 : 1)})` : `rgba(87,211,242,${.05 + Math.max(0, z) * .08})`; const s = d.land ? 1.5 : 1; g.fillRect(x, y, s, s); });
    // arcs between markets moving the same way
    pairs.forEach(([a, b]) => { const A = M[a], B = M[b], ta = Math.max(A.fire, B.fire); if (t < ta) return; const k = ease(cl((t - ta) / 1.2)), pa = sph(A.lat, A.lon), pb = sph(B.lat, B.lon);
      g.strokeStyle = A.d >= 0 ? 'rgba(63,214,138,.35)' : 'rgba(255,92,108,.35)'; g.beginPath(); let vis = true;
      for (let j = 0; j <= 30 * k; j++) { const u = j / 30, lift = 1 + .28 * Math.sin(u * Math.PI); let v = [pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u, pa[2] + (pb[2] - pa[2]) * u]; const n = Math.hypot(...v); v = v.map(c => c / n * lift);
        const [x, y, z] = proj(v, rot, tilt, sc); if (z < -.2) vis = false; j ? g.lineTo(x, y) : g.moveTo(x, y); } if (vis) g.stroke(); });
    // beams
    M.forEach(m => { if (t < m.fire) return; const k = eo(cl((t - m.fire) / .8)), base = sph(m.lat, m.lon), len = 1 + (.08 + Math.min(.5, Math.abs(m.d) * .3)) * k;
      const [x0, y0, z0] = proj(base, rot, tilt, sc), [x1, y1] = proj(base.map(c => c * len), rot, tilt, sc); if (z0 < -.1) return;
      const col = m.d >= 0 ? '63,214,138' : '255,92,108'; const gr = g.createLinearGradient(x0, y0, x1, y1); gr.addColorStop(0, `rgba(${col},.95)`); gr.addColorStop(1, `rgba(${col},0)`);
      g.strokeStyle = gr; g.lineWidth = 3; g.shadowColor = `rgb(${col})`; g.shadowBlur = 14; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); g.shadowBlur = 0; g.lineWidth = 1;
      g.fillStyle = `rgb(${col})`; g.beginPath(); g.arc(x0, y0, 2.6, 0, 7); g.fill();
      const age = t - m.fire; if (age < 1) { g.strokeStyle = `rgba(${col},${1 - age})`; g.beginPath(); g.arc(x0, y0, 3 + age * 26, 0, 7); g.stroke(); }
      if (z0 > .2) { g.fillStyle = 'rgba(241,238,234,.85)'; g.font = '10px JetBrains Mono, monospace'; g.fillText(`${m.n} ${m.d >= 0 ? '+' : ''}${m.d.toFixed(1)}%`, x1 + 6, y1); } });
    const op = M.filter(m => t >= m.fire); if (op.length !== shown) { shown = op.length; $('#mo', side).textContent = shown + ' / ' + M.length;
      $('#ml', side).innerHTML = [...op].sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 10).map(m => `<div class="row"><span>${m.n}</span><span class="mono ${m.d >= 0 ? 'up' : 'dn'}">${m.d >= 0 ? '+' : ''}${m.d.toFixed(2)}%</span></div>`).join(''); }
    if (t > 2.4 + M.length * .38 + 8) { M.forEach(m => m.fire += M.length * .38 + 9); } });
}

// ================================================================ 2. FX: solar system around the dollar
function fxg() {
  const st = shell('FX', 'The currency solar system', 'the dollar is the sun · currencies condense from dust into planets · stronger ones swing out to bigger, brighter orbits',
    'FX page · real strength against the dollar (13 Nov rates here): switch the period and every planet flies to its new orbit');
  const [g, W, H] = canvas(st), cx = W * .46, cy = H * .5, C = D.fx.filter(c => c.c !== 'USD'); let per = 'w1';
  const ctl = document.createElement('div'); ctl.className = 'ctl'; ctl.style.cssText = 'left:16px;top:16px'; ctl.innerHTML = ['d1', 'w1', 'm1', 'y1'].map(p => `<button data-p="${p}" class="${p === per ? 'on' : ''}">${{ d1: '1 DAY', w1: '1 WEEK', m1: '1 MONTH', y1: '1 YEAR' }[p]}</button>`).join(''); st.appendChild(ctl);
  const P = C.map((c, i) => ({ ...c, a: i * 2.4, orb: 120, tor: 120, r: 0, tr: 8, sp: .2 + Math.random() * .2, dust: Array.from({ length: 50 }, () => ({ a: Math.random() * 6.283, d: 30 + Math.random() * 60, s: .5 + Math.random() })) }));
  function target() { const v = P.map(p => p[per]), lo = Math.min(...v), hi = Math.max(...v); const rk = [...P].sort((a, b) => a[per] - b[per]);
    P.forEach(p => { const s = (p[per] - lo) / ((hi - lo) || 1), k = rk.indexOf(p); p.tor = 70 + k * (Math.min(W, H * 1.6) * .42 - 70) / (P.length - 1); p.tr = 5 + s * 13; p.s = s; }); }
  ctl.onclick = e => { const p = e.target.dataset.p; if (!p) return; per = p; ctl.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.p === p)); target(); };
  target(); const t0 = performance.now(); P.forEach(p => p.orb = p.tor * (1.6 + Math.random()));
  loop(now => { const t = (now - t0) / 1000, F = ease(cl((t - .4) / 2.2)); g.clearRect(0, 0, W, H);
    // the sun
    const sr = 26 + 4 * Math.sin(t * 2), sg = g.createRadialGradient(cx, cy, 2, cx, cy, sr * 3.4); sg.addColorStop(0, 'rgba(255,235,210,1)'); sg.addColorStop(.25, 'rgba(255,140,60,.9)'); sg.addColorStop(.6, 'rgba(255,42,42,.25)'); sg.addColorStop(1, 'rgba(255,42,42,0)');
    g.fillStyle = sg; g.beginPath(); g.arc(cx, cy, sr * 3.4 * ease(cl(t / 1)), 0, 7); g.fill(); g.fillStyle = '#050506'; g.font = '600 11px JetBrains Mono, monospace'; g.textAlign = 'center'; g.globalAlpha = cl(t); g.fillText('USD', cx, cy + 4); g.globalAlpha = 1;
    P.forEach((p, i) => { p.orb += (p.tor - p.orb) * .035; p.a += p.sp * .006 * (300 / p.orb); p.r += (p.tr * F - p.r) * .06; const x = cx + Math.cos(p.a) * p.orb, y = cy + Math.sin(p.a) * p.orb * .45;
      g.strokeStyle = `rgba(241,238,234,${.05 + (p.s || 0) * .07})`; g.beginPath(); g.ellipse(cx, cy, p.orb, p.orb * .45, 0, 0, 7); g.stroke();
      const col = p[per] >= 0 ? [63, 214, 138] : [255, 92, 108];
      p.dust.forEach(d => { d.a += .02 * d.s; d.d += ((1 - F) * (30 + d.s * 50) - d.d) * .05; g.fillStyle = `rgba(${col},${.5 * (1 - F) + .05})`; g.fillRect(x + Math.cos(d.a) * d.d, y + Math.sin(d.a) * d.d * .6, 1.3, 1.3); });
      if (p.r > .5) { const pg = g.createRadialGradient(x - p.r * .35, y - p.r * .35, 1, x, y, p.r * 1.3); pg.addColorStop(0, `rgba(${col},1)`); pg.addColorStop(1, `rgba(${col},.1)`); g.fillStyle = pg; g.shadowColor = `rgb(${col})`; g.shadowBlur = 8 + (p.s || 0) * 18; g.beginPath(); g.arc(x, y, p.r, 0, 7); g.fill(); g.shadowBlur = 0;
        g.fillStyle = '#F1EEEA'; g.font = '10px JetBrains Mono, monospace'; g.fillText(p.c, x, y - p.r - 6); g.fillStyle = `rgb(${col})`; g.fillText((p[per] >= 0 ? '+' : '') + p[per].toFixed(2) + '%', x, y + p.r + 12); } });
    g.textAlign = 'left'; g.fillStyle = '#6F6C72'; g.font = '9px JetBrains Mono, monospace'; g.fillText('OUTER ORBIT = STRONGER AGAINST THE DOLLAR', 18, H - 18); });
}

// ================================================================ 3. YIELD CURVES: 3D yield surface
function curves() {
  const st = shell('CRV', 'The yield surface', '20 years of US Treasury curves as a 3D landscape · a scan plane sweeps through time · red valleys = inverted',
    'Yield curves page · real FRED yields in the app (illustrative here): the surface rises out of the floor slice by slice, then a red scan plane walks forward through time while the camera flies along it');
  const [g, W, H] = canvas(st), K = D.curves, TEN = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y'], XM = [0, .08, .16, .3, .52, .76, 1];
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = '<div class="h">Scan date</div><div class="big" id="sd">—</div><div class="h">10-year minus 3-month</div><div class="big" id="ss">—</div><div class="h" id="sr"></div>'; st.appendChild(side);
  // interpolate to 4 slices per frame for a smooth surface
  const S = []; for (let k = 0; k < K.length - 1; k++) for (let q = 0; q < 4; q++) { const u = q / 4; S.push({ d: K[k].d, y: K[k].y.map((a, i) => a + (K[k + 1].y[i] - a) * u), rec: K[k].rec }); } S.push(K[K.length - 1]);
  const N = S.length, PW = W - 300;
  const P3 = (x, y, z, cam) => { // x: 0..1 maturity, z: 0..1 time, y: yield %
    let X = (x - .5) * 2.4, Y = y / 6 * 1.2 - .35, Z = (z - .5) * 3.0; const ca = Math.cos(cam.a), sa = Math.sin(cam.a); const x1 = X * ca - Z * sa, z1 = X * sa + Z * ca;
    const ce = Math.cos(cam.e), se = Math.sin(cam.e); const y1 = Y * ce - z1 * se, z2 = Y * se + z1 * ce + cam.d; const f = PW * .78 / z2; return [PW * .5 + x1 * f, H * .6 - y1 * f, z2]; };
  const t0 = performance.now();
  loop(now => { const t = (now - t0) / 1000, rise = t / 2.2, scan = cl((t - 2.6) / 16), cam = { a: -1.0 + Math.sin(t * .12) * .15 + scan * .35, e: .4, d: 4.3 - ease(cl(t / 2.5)) * .6 };
    g.clearRect(0, 0, W, H);
    // floor grid
    g.strokeStyle = 'rgba(241,238,234,.05)'; for (let i = 0; i <= 6; i++) { const a = P3(XM[i], 0, 0, cam), b = P3(XM[i], 0, 1, cam); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); }
    // time slices (maturity lines), back to front
    for (let s = N - 1; s >= 0; s--) { const z = s / (N - 1), k = ease(cl(rise - s / N * 1.2)); if (k <= 0) continue; const c = S[s], inv = c.y[5] - c.y[0] < 0, past = z <= scan;
      g.strokeStyle = inv ? `rgba(255,42,42,${past ? .9 : .35})` : `rgba(87,211,242,${past ? .55 : .18})`; g.lineWidth = past && Math.abs(z - scan) < .02 ? 2.2 : 1;
      g.beginPath(); c.y.forEach((y, i) => { const p = P3(XM[i], y * k, z, cam); i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); }); g.stroke();
      if (c.rec && s % 4 === 0 && k >= 1) { const a = P3(0, 0, z, cam), b = P3(0, 5.5, z, cam); g.strokeStyle = 'rgba(255,42,42,.25)'; g.setLineDash([2, 4]); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); g.setLineDash([]); } }
    g.lineWidth = 1;
    // tenor ridges (lines through time)
    for (let i = 0; i < 7; i++) { g.strokeStyle = 'rgba(241,238,234,.12)'; g.beginPath(); for (let s = 0; s < N; s++) { const k = ease(cl(rise - s / N * 1.2)), p = P3(XM[i], S[s].y[i] * k, s / (N - 1), cam); s ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); } g.stroke();
      const lp = P3(XM[i], 0, 0, cam); g.fillStyle = '#6F6C72'; g.font = '9px JetBrains Mono, monospace'; g.fillText(TEN[i], lp[0] - 8, lp[1] + 16); }
    // scan plane
    if (t > 2.6) { const z = scan, q = [P3(0, 0, z, cam), P3(1, 0, z, cam), P3(1, 6, z, cam), P3(0, 6, z, cam)]; g.fillStyle = 'rgba(255,42,42,.07)'; g.beginPath(); q.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.fill();
      g.strokeStyle = 'rgba(255,42,42,.7)'; g.beginPath(); g.moveTo(q[0][0], q[0][1]); g.lineTo(q[1][0], q[1][1]); g.stroke();
      const c = S[Math.round(scan * (N - 1))], sp = c.y[5] - c.y[0]; $('#sd', side).textContent = c.d; $('#ss', side).innerHTML = `<span class="${sp < 0 ? 'dn' : 'up'}">${sp >= 0 ? '+' : ''}${sp.toFixed(2)}</span>`;
      $('#sr', side).innerHTML = (sp < 0 ? '<span style="color:var(--red)">INVERTED</span>' : 'NORMAL') + (c.rec ? '<br><span style="color:var(--red)">■ RECESSION PERIOD</span>' : ''); }
    [['2006', 0], ['TODAY', 1]].forEach(([l, z]) => { const p = P3(1.05, 0, z, cam); g.fillStyle = '#9A969D'; g.font = '10px JetBrains Mono, monospace'; g.fillText(l, p[0] + 6, p[1]); });
    if (t > 20) { /* loop the scan */ } });
}

// ================================================================ 4. TAKEOVERS: deal network
function takeovers() {
  const st = shell('TAKEOVERS', 'The deal network', 'private-equity firms light up as hubs · a predator line shoots from each buyer to the company it is filing for and reels it in',
    'Takeovers page · real SEC filings in the app (sample here): each strike flashes the filing type, and the target drifts into its buyer\'s web');
  const [g, W, H] = canvas(st), T = D.deals, PW = W - 290, cx = PW / 2, cy = H / 2;
  const buyers = [...new Set(T.map(d => d.b))], hub = {}; buyers.forEach((b, i) => { const a = i / buyers.length * 6.283 - 1.2; hub[b] = { x: cx + Math.cos(a) * PW * .17, y: cy + Math.sin(a) * H * .2, t: .3 + i * .25 }; });
  const tg = T.map((d, i) => { const a = i / T.length * 6.283 + .3; return { ...d, x: cx + Math.cos(a) * PW * .42, y: cy + Math.sin(a) * H * .4, tt: 1.6 + i * .7, hit: 0 }; });
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = '<div class="h">Strikes</div><div class="big" id="tk">0</div><div id="tl"></div>'; st.appendChild(side);
  const bg = Array.from({ length: 140 }, () => ({ x: Math.random() * PW, y: Math.random() * H, v: Math.random() })); const t0 = performance.now(); let n = 0;
  loop(now => { const t = (now - t0) / 1000; g.clearRect(0, 0, W, H);
    bg.forEach(p => { g.fillStyle = `rgba(241,238,234,${.05 + .08 * Math.sin(t + p.v * 6)})`; g.fillRect(p.x, p.y, 1, 1); });
    tg.forEach(d => { const h = hub[d.b], k = ease(cl((t - d.tt) / .6)); if (t < d.tt - .4) { g.fillStyle = 'rgba(241,238,234,.2)'; g.beginPath(); g.arc(d.x, d.y, 2, 0, 7); g.fill(); return; }
      if (k >= 1 && !d.hit) { d.hit = 1; n++; $('#tk', side).textContent = n; const r = document.createElement('div'); r.className = 'row'; r.innerHTML = `<span><b style="color:var(--hi);font-weight:400">${d.t}</b><br><span style="color:var(--m);font-size:10px">${d.b} · ${d.f}</span></span>`; $('#tl', side).prepend(r); }
      const pull = ease(cl((t - d.tt - .6) / 2.5)) * .35, x = d.x + (h.x - d.x) * pull, y = d.y + (h.y - d.y) * pull, hx = h.x + (x - h.x) * k, hy = h.y + (y - h.y) * k;
      g.strokeStyle = 'rgba(255,42,42,.55)'; g.lineWidth = 1.2; g.beginPath(); g.moveTo(h.x, h.y); g.quadraticCurveTo((h.x + hx) / 2 + 30, (h.y + hy) / 2 - 30, hx, hy); g.stroke(); g.lineWidth = 1;
      if (k < 1) { g.fillStyle = '#FFF'; g.shadowColor = '#FF2A2A'; g.shadowBlur = 16; g.beginPath(); g.arc(hx, hy, 3, 0, 7); g.fill(); g.shadowBlur = 0; return; }
      const age = t - d.tt - .6; if (age < .8) { g.strokeStyle = `rgba(255,42,42,${1 - age / .8})`; g.beginPath(); g.arc(x, y, 6 + age * 40, 0, 7); g.stroke(); g.fillStyle = `rgba(255,42,42,${1 - age / .8})`; g.font = '600 10px JetBrains Mono, monospace'; g.fillText(d.f, (h.x + x) / 2 + 8, (h.y + y) / 2 - 22); }
      g.fillStyle = '#FF2A2A'; g.beginPath(); g.arc(x, y, 4, 0, 7); g.fill(); g.fillStyle = '#F1EEEA'; g.font = '10px JetBrains Mono, monospace'; g.fillText(d.t, x + 8, y + 4); });
    buyers.forEach(b => { const h = hub[b], k = ease(cl((t - h.t) / .7)); if (k <= 0) return; const pr = 10 + 3 * Math.sin(t * 3 + h.x);
      const hg = g.createRadialGradient(h.x, h.y, 1, h.x, h.y, pr * 2.4 * k); hg.addColorStop(0, 'rgba(255,42,42,.9)'); hg.addColorStop(1, 'rgba(255,42,42,0)'); g.fillStyle = hg; g.beginPath(); g.arc(h.x, h.y, pr * 2.4 * k, 0, 7); g.fill();
      g.fillStyle = '#F1EEEA'; g.font = '600 11px JetBrains Mono, monospace'; g.textAlign = 'center'; g.globalAlpha = k; g.fillText(b.toUpperCase(), h.x, h.y - pr - 10); g.globalAlpha = 1; g.textAlign = 'left'; });
    if (t > tg[tg.length - 1].tt + 6) { tg.forEach((d, i) => { d.tt = t + 1 + i * .7; d.hit = 0; }); n = 0; $('#tl', side).innerHTML = ''; } });
}

// ================================================================ 5. EVENT LAB: strategy tournament
function graveyard() {
  const st = shell('EVENT LAB', 'The strategy tournament', `${D.pub.total} published strategies race up the track · at the publication line most fall off the cliff · ${D.pub.after} survive`,
    'Event Lab · real numbers from your Open Asset Pricing test: before publication they averaged ' + D.pub.before_avg + '% a year, after only ' + D.pub.after_avg + '%; the survivors lock into the wall on the right');
  const [g, W, H] = canvas(st), N = D.pub.total, S = D.pub.after, PW = W - 290, PX = PW * .55, rnd = i => { const x = Math.sin(i * 9301 + 49297) * 233280; return x - Math.floor(x); };
  const side = document.createElement('div'); side.className = 'side'; side.innerHTML = `<div class="h">Still standing</div><div class="big" id="gs">${N}</div><div class="h">Average return a year</div><div style="font-size:12px;line-height:2">Before publication <b class="mono" style="color:var(--hi)">${D.pub.before_avg}%</b><br>After publication <b class="mono" style="color:var(--hi)">${D.pub.after_avg}%</b></div><div class="h" style="margin-top:18px">What survived</div>${D.pub.themes.map(t => `<div class="row"><span>${t[0]}</span><span class="mono">${t[1]}</span></div>`).join('')}`; st.appendChild(side);
  const live = new Set([...Array(N).keys()].sort((a, b) => rnd(a) - rnd(b)).slice(0, S));
  const A = [...Array(N).keys()].map(i => ({ i, live: live.has(i), y0: H * .88 - rnd(i + 3) * 40, slope: .55 + rnd(i + 9) * .6, sp: .9 + rnd(i + 5) * .3, shards: null, wall: [...live].indexOf(i) }));
  const t0 = performance.now(); let standing = N;
  loop(now => { const t = (now - t0) / 1000; g.clearRect(0, 0, W, H);
    g.strokeStyle = 'rgba(255,42,42,.5)'; g.setLineDash([4, 6]); g.beginPath(); g.moveTo(PX, 30); g.lineTo(PX, H - 20); g.stroke(); g.setLineDash([]);
    g.fillStyle = '#FF2A2A'; g.font = '10px JetBrains Mono, monospace'; g.fillText('PUBLISHED', PX + 8, 44); g.fillStyle = '#6F6C72'; g.fillText('BEFORE: THE BACKTEST', 24, 44); g.fillText('AFTER: REAL LIFE', PX + 8, 60);
    let cnt = 0;
    A.forEach(a => { const u = (t - .3 - rnd(a.i + 1) * .9) * .22 * a.sp; if (u < 0) return; const x = 24 + u * PX, yRun = a.y0 - (x - 24) * a.slope * .9;
      if (x < PX) { g.fillStyle = 'rgba(241,238,234,.55)'; g.fillRect(x, yRun, 2, 2); cnt++; return; }
      const after = (x - PX) / (PW - PX);
      if (a.live) { const wc = 6, gx = PW - 20 - (wc - (a.wall % wc)) * 16, gy = 80 + Math.floor(a.wall / wc) * 16, k = ease(cl(after * 3)), yA = a.y0 - (PX - 24) * a.slope * .9;
        const xx = PX + (gx - PX) * k, yy = yA + (gy - yA) * k; g.fillStyle = '#3FD68A'; g.shadowColor = '#3FD68A'; g.shadowBlur = k >= 1 ? 8 : 0; g.fillRect(xx - 5, yy - 5, k >= 1 ? 12 : 3, k >= 1 ? 12 : 3); g.shadowBlur = 0; cnt++; return; }
      if (!a.shards) { a.shards = Array.from({ length: 6 }, () => ({ vx: (Math.random() - .3) * 60, vy: -Math.random() * 40, x: PX, y: a.y0 - (PX - 24) * a.slope * .9, t: t })); }
      a.shards.forEach(s => { const dt = t - s.t, x = s.x + s.vx * dt, y = s.y + s.vy * dt + 160 * dt * dt; if (y < H) { g.fillStyle = `rgba(255,92,108,${Math.max(0, .8 - dt * .4)})`; g.fillRect(x, y, 1.6, 1.6); } }); });
    if (cnt !== standing && t > 2) { standing = Math.max(S, cnt); $('#gs', side).textContent = standing; }
    if (t > 16) { A.forEach(a => a.shards = null); later(() => {}, 0); } });
}

// ================================================================ 6. COUNTRY: satellite zoom
function globe() {
  const st = shell('CTRY', 'Satellite view', 'satellites link into a mesh that becomes the globe · pick a country and a targeting laser locks on and zooms in',
    'Country page · real IMF figures in the app (sample here): the figures beam up into holographic panels');
  const [g, W, H] = canvas(st), C = D.countries, PW = W - 290, cx = PW * .5, cy = H * .52, R = Math.min(PW, H) * .36, proj = rotator(cx, cy, R);
  const side = document.createElement('div'); side.className = 'side holo'; st.appendChild(side);
  const ctl = document.createElement('div'); ctl.className = 'ctl'; ctl.style.cssText = 'left:16px;top:16px;max-width:520px'; ctl.innerHTML = C.map((c, i) => `<button data-i="${i}">${c.code}</button>`).join(''); st.appendChild(ctl);
  const dots = globeDots(6000, 8), sats = Array.from({ length: 70 }, (_, i) => ({ a: Math.random() * 6.283, inc: Math.random() * 3.14, r: 1.35 + Math.random() * .3, sp: .2 + Math.random() * .4 }));
  let rot = 0, trot = 0, zoom = 1, tz = 1, cur = 0, pickT = 0; const t0 = performance.now();
  function pick(i) { cur = i; pickT = performance.now(); const c = C[i]; trot = -c.lon * Math.PI / 180 + Math.PI / 2; tz = 1.55; ctl.querySelectorAll('button').forEach((b, j) => b.classList.toggle('on', j === i));
    side.innerHTML = `<div class="h">TARGET LOCKED · ${c.code}</div><div style="font-size:24px;color:#9BE7F8;margin-bottom:18px">${c.name}</div>` + c.k.map(([n, v, u]) => `<div class="h">${n}</div><div class="big" data-v="${v}" data-u="${u}">0</div>`).join('') + (c.k.length ? '' : '<div class="h" style="line-height:1.8">IMF figures appear once the Country page has downloaded them</div>');
    side.querySelectorAll('[data-v]').forEach((el, j) => { const to = +el.dataset.v, ts = performance.now() + 900 + j * 150; (function f(tt) { const k = ease(cl((tt - ts) / 1200)); el.textContent = (to * k).toFixed(1) + el.dataset.u; if (k < 1) requestAnimationFrame(f); })(ts); }); }
  ctl.onclick = e => { if (e.target.dataset.i) pick(+e.target.dataset.i); }; later(() => pick(0), 2600);
  let auto = performance.now() + 2600; loop(now => { const t = (now - t0) / 1000, F = ease(cl((t - .8) / 1.8)); if (now - auto > 7000) { auto = now; pick((cur + 1) % C.length); }
    let d = trot - rot; d = Math.atan2(Math.sin(d), Math.cos(d)); rot += d * .05; if (now - pickT > 4500) tz = 1; zoom += (tz - zoom) * .05; g.clearRect(0, 0, W, H);
    const tilt = .3;
    // satellites orbit and link into a mesh, then dissolve into the globe
    const sp = sats.map(s => { s.a += s.sp * .01; const r = s.r * (1 - F) + F, v = [Math.cos(s.a) * r, Math.sin(s.a) * Math.cos(s.inc) * r, Math.sin(s.a) * Math.sin(s.inc) * r]; return proj(v, rot, tilt, zoom); });
    if (F < 1) { g.strokeStyle = `rgba(87,211,242,${.25 * (1 - F)})`; for (let a = 0; a < sp.length; a++) for (let b = a + 1; b < sp.length; b++) { const dx = sp[a][0] - sp[b][0], dy = sp[a][1] - sp[b][1]; if (dx * dx + dy * dy < 9000) { g.beginPath(); g.moveTo(sp[a][0], sp[a][1]); g.lineTo(sp[b][0], sp[b][1]); g.stroke(); } }
      sp.forEach(([x, y]) => { g.fillStyle = `rgba(155,231,248,${1 - F})`; g.fillRect(x - 1.5, y - 1.5, 3, 3); }); }
    dots.forEach(o => { const [x, y, z] = proj(o.p, rot, tilt, zoom); if (z < 0) return; const a = F * (o.land ? .15 + z * .6 : .05 + z * .08); if (a <= .01) return; g.fillStyle = o.land ? `rgba(155,231,248,${a})` : `rgba(87,211,242,${a})`; g.fillRect(x, y, o.land ? 1.5 : 1, o.land ? 1.5 : 1); });
    g.strokeStyle = `rgba(87,211,242,${.15 * F})`; g.beginPath(); g.arc(cx, cy, R * zoom, 0, 7); g.stroke();
    if (F >= 1 && pickT) { const c = C[cur], [x, y, z] = proj(sph(c.lat, c.lon), rot, tilt, zoom), age = (now - pickT) / 1000;
      if (z > 0) { const k = eo(cl(age / .6)); g.strokeStyle = `rgba(255,42,42,${.9 * (1 - cl((age - 1.2) / 1))})`; g.lineWidth = 1.5; g.beginPath(); g.moveTo(PW - 10, 20); g.lineTo(PW - 10 + (x - PW + 10) * k, 20 + (y - 20) * k); g.stroke(); g.lineWidth = 1;
        const rr = 26 - 14 * ease(cl(age / .8)); g.strokeStyle = '#FF2A2A'; g.beginPath(); g.arc(x, y, rr, 0, 7); g.moveTo(x - rr - 8, y); g.lineTo(x - rr + 4, y); g.moveTo(x + rr - 4, y); g.lineTo(x + rr + 8, y); g.moveTo(x, y - rr - 8); g.lineTo(x, y - rr + 4); g.moveTo(x, y + rr - 4); g.lineTo(x, y + rr + 8); g.stroke();
        g.fillStyle = '#FF2A2A'; g.beginPath(); g.arc(x, y, 3, 0, 7); g.fill(); g.fillStyle = '#F1EEEA'; g.font = '11px JetBrains Mono, monospace'; g.fillText(c.name.toUpperCase(), x + rr + 12, y - 6); } } });
}

// ================================================================ 7. CALENDAR: mission control
function calendar() {
  const st = shell('CAL', 'Mission control', 'every release is a launch on the countdown arc · the next one charges up · T-minus to the second',
    'Calendar page · real FRED release dates in the app (sample here); the last release launches off the pad as the screen opens');
  const [g, W, H] = canvas(st), E = D.cal, now0 = Date.now(), DAY = 864e5, cxA = W / 2, cyA = H * 1.85, RA = H * 1.2;
  const big = hud(st, '', 'left:0;right:0;top:26px;text-align:center'); const t0 = performance.now();
  const ang = h => -Math.PI / 2 - .55 + (h / (14 * 24)) * 1.1, pos = h => [cxA + Math.cos(ang(h)) * RA, cyA + Math.sin(ang(h)) * RA];
  loop(now => { const t = (now - t0) / 1000, F = ease(cl(t / 1.6)), nowMs = Date.now(), nx = E.find(e => now0 + e.h * 36e5 > nowMs) || E[0], left = now0 + nx.h * 36e5 - nowMs;
    const d = Math.floor(left / DAY), h = Math.floor(left % DAY / 36e5), m = Math.floor(left % 36e5 / 6e4), s = Math.floor(left % 6e4 / 1e3), cs = Math.floor(left % 1e3 / 10), sc = t < 1.3;
    const dg = v => sc ? String(Math.floor(Math.random() * 100)).padStart(2, '0') : String(v).padStart(2, '0');
    big.innerHTML = `<div style="letter-spacing:.3em;color:var(--m)">T-MINUS · ${nx.n.toUpperCase()}</div><div style="font:300 58px var(--mono);color:var(--hi);margin:10px 0;letter-spacing:.02em">${dg(d)}<span style="font-size:15px;color:var(--m)">D </span>${dg(h)}<span style="font-size:15px;color:var(--m)">H </span>${dg(m)}<span style="font-size:15px;color:var(--m)">M </span>${dg(s)}<span style="font-size:20px;color:var(--red)">.${dg(cs)}</span></div><div style="color:var(--m2)">${nx.c}</div>`;
    g.clearRect(0, 0, W, H);
    // the arc draws in
    g.strokeStyle = 'rgba(241,238,234,.18)'; g.lineWidth = 1.5; g.beginPath(); g.arc(cxA, cyA, RA, ang(0) - .1, ang(0) - .1 + (1.3) * F); g.stroke(); g.lineWidth = 1;
    for (let k = 0; k <= 14; k++) { if (k / 14 > F) break; const [x, y] = pos(k * 24); g.strokeStyle = 'rgba(241,238,234,.25)'; g.beginPath(); g.moveTo(x, y - 5); g.lineTo(x, y + 5); g.stroke(); if (k % 2 === 0) { g.fillStyle = '#6F6C72'; g.font = '9px JetBrains Mono, monospace'; g.fillText(new Date(now0 + k * DAY).toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit' }).toUpperCase(), x - 18, y + 22); } }
    const [nxp, nyp] = pos((nowMs - now0) / 36e5); g.fillStyle = '#FF2A2A'; g.beginPath(); g.arc(nxp, nyp, 4, 0, 7); g.fill(); g.font = '9px JetBrains Mono, monospace'; g.fillText('NOW', nxp - 10, nyp - 12);
    E.forEach((e, i) => { if (i / E.length > F) return; const [x, y] = pos(e.h), isN = e === nx, charge = isN ? cl(1 - left / (3 * DAY)) * .8 + .2 * (.5 + .5 * Math.sin(t * 6)) : 0;
      // rocket
      g.save(); g.translate(x, y - 14); g.fillStyle = isN ? '#F1EEEA' : 'rgba(87,211,242,.8)'; g.beginPath(); g.moveTo(0, -12); g.lineTo(5, 0); g.lineTo(5, 8); g.lineTo(-5, 8); g.lineTo(-5, 0); g.closePath(); g.fill();
      if (isN) { g.fillStyle = '#FF2A2A'; g.fillRect(-8, 10, 16 * charge, 2); g.strokeStyle = 'rgba(255,42,42,.6)'; g.strokeRect(-8, 10, 16, 2); }
      g.restore(); g.fillStyle = isN ? '#F1EEEA' : '#9A969D'; g.font = (isN ? '600 ' : '') + '10px JetBrains Mono, monospace'; g.textAlign = 'center'; g.fillText(e.n, x, y - 34 - (i % 2) * 14); g.textAlign = 'left'; });
    // the last release launches off the pad at the start
    if (t < 4.5) { const u = cl((t - .6) / 3.5), x = W * .14, y = H * .82 - eo(u) * H * .95; for (let k = 0; k < 24; k++) { g.fillStyle = `rgba(255,${120 + k * 5},60,${(1 - k / 24) * (1 - u * .5)})`; g.fillRect(x - 2 + (Math.random() - .5) * 4, y + 16 + k * 5, 4, 4); }
      g.fillStyle = '#F1EEEA'; g.beginPath(); g.moveTo(x, y - 16); g.lineTo(x + 7, y); g.lineTo(x + 7, y + 12); g.lineTo(x - 7, y + 12); g.lineTo(x - 7, y); g.closePath(); g.fill();
      g.font = '10px JetBrains Mono, monospace'; g.fillStyle = 'rgba(241,238,234,.8)'; g.fillText('LAST RELEASE · ' + (D.last || 'JOBLESS CLAIMS'), x + 14, y); } });
}

// ================================================================ 8. HEARTBEAT: holographic body scan
function heartbeat() {
  const st = shell('US · UK · EA', 'Economy body scan', 'a hologram of the economy forms from scan lines · each part glows by how it is doing · the heartbeat pulses through it',
    'US / UK / Euro area pages · real indicators in the app (sample here): green = improving, red = weakening; the ECG underneath beats faster when the economy improves faster');
  const [g, W, H] = canvas(st), Z = D.beat, O = D.organs, bx = W * .34, by = H * .44, s = Math.min(W, H) / 560;
  const tag = hud(st, '', 'right:24px;top:22px;text-align:right'); const buf = []; let off = 0, last = performance.now(); const t0 = performance.now();
  const body = [['head', 0, -190, 30, 34], ['chest', 0, -95, 70, 62], ['belly', 0, 10, 58, 52], ['hipL', -30, 95, 26, 34], ['hipR', 30, 95, 26, 34]];
  const limbs = [[-70, -125, -112, 40], [70, -125, 112, 40], [-30, 120, -38, 240], [30, 120, 38, 240]];
  function beatShape(u, z) { const a = .4 + Math.max(0, z) * .4; if (u < .1) return 0; if (u < .14) return -.15 * a; if (u < .18) return a; if (u < .22) return -.45 * a; if (u < .3) return .12 * a * Math.sin((u - .22) / .08 * Math.PI); return 0; }
  loop(now => { const t = (now - t0) / 1000, dt = (now - last) / 1000; last = now; const i = Math.floor(now / 2400) % Z.length, z = Z[i].z, bpm = 52 + z * 30, per = 60 / bpm, scanY = by - 240 * s + ((t * 140) % (520 * s)), F = ease(cl(t / 2));
    g.clearRect(0, 0, W, H);
    // hologram outline drawn by scan lines
    g.save(); g.beginPath(); g.rect(0, 0, W, by - 240 * s + 520 * s * F); g.clip();
    for (let yy = by - 240 * s; yy < by + 280 * s; yy += 4) { g.strokeStyle = 'rgba(87,211,242,.05)'; g.beginPath(); g.moveTo(bx - 140 * s, yy); g.lineTo(bx + 140 * s, yy); g.stroke(); }
    g.strokeStyle = 'rgba(87,211,242,.55)'; g.shadowColor = '#57D3F2'; g.shadowBlur = 10; g.lineWidth = 1.4;
    body.forEach(([, x, y, rx, ry]) => { g.beginPath(); g.ellipse(bx + x * s, by + y * s, rx * s, ry * s, 0, 0, 7); g.stroke(); });
    limbs.forEach(([x1, y1, x2, y2]) => { g.beginPath(); g.moveTo(bx + x1 * s, by + y1 * s); g.lineTo(bx + x2 * s, by + y2 * s); g.stroke(); });
    g.shadowBlur = 0; g.lineWidth = 1; g.restore();
    // organs = indicator groups
    O.forEach((o, j) => { const k = ease(cl((t - 1 - j * .25) / .8)); if (k <= 0) return; const x = bx + o.x * s, y = by + o.y * s, col = o.z > .2 ? '63,214,138' : o.z < -.2 ? '255,92,108' : '255,179,71', pulse = 1 + .12 * Math.max(0, beatShape((off % per) / per, z)) * 3;
      const og = g.createRadialGradient(x, y, 1, x, y, 26 * s * k * pulse); og.addColorStop(0, `rgba(${col},.9)`); og.addColorStop(1, `rgba(${col},0)`); g.fillStyle = og; g.beginPath(); g.arc(x, y, 26 * s * k * pulse, 0, 7); g.fill();
      const ly = by + (-150 + j * 62) * s; g.strokeStyle = `rgba(${col},.5)`; g.beginPath(); g.moveTo(x + 18 * s, y); g.lineTo(bx + 150 * s, ly); g.lineTo(bx + 170 * s, ly); g.stroke();
      g.fillStyle = '#F1EEEA'; g.font = '11px JetBrains Mono, monospace'; g.globalAlpha = k; g.fillText(o.n.toUpperCase(), bx + 178 * s, ly - 2); g.fillStyle = `rgb(${col})`; g.font = '10px JetBrains Mono, monospace'; g.fillText((o.z > .2 ? 'IMPROVING' : o.z < -.2 ? 'WEAKENING' : 'STEADY') + ` · ${o.z >= 0 ? '+' : ''}${o.z.toFixed(2)}`, bx + 178 * s, ly + 12); g.globalAlpha = 1; });
    g.fillStyle = 'rgba(87,211,242,.25)'; g.fillRect(bx - 150 * s, scanY, 300 * s, 1.5);
    // ECG along the bottom
    const fill = buf.length < W - 4; for (let k = 0; k < (fill ? Math.ceil(W / 75) : 2); k++) { off += fill ? 1 / 120 : Math.min(dt, .05) / 2; buf.push(beatShape((off % per) / per, z)); } while (buf.length > W) buf.shift();
    const mid = H - 70, amp = 46; g.strokeStyle = z > .4 ? '#3FD68A' : z < -.2 ? '#FF5C6C' : '#57D3F2'; g.lineWidth = 2; g.shadowColor = g.strokeStyle; g.shadowBlur = 10; g.beginPath(); buf.forEach((v, x) => x ? g.lineTo(x, mid - v * amp) : g.moveTo(x, mid - v * amp)); g.stroke(); g.shadowBlur = 0; g.lineWidth = 1;
    tag.innerHTML = `<div style="letter-spacing:.22em;color:var(--m)">${Z[i].d} · ${Z[i].r}</div><div style="font:300 44px var(--mono);color:var(--hi);margin:6px 0">${Math.round(bpm)}<span style="font-size:14px;color:var(--m)"> BPM</span></div><div style="color:${z > .4 ? 'var(--up)' : z < -.2 ? 'var(--dn)' : 'var(--cy)'}">${z > .4 ? 'IMPROVING FAST' : z < -.2 ? 'WEAKENING' : 'STEADY'}</div>`; });
}

const PAGES = [['Markets', markets], ['FX', fxg], ['Yield curves', curves], ['Takeovers', takeovers], ['Event Lab', graveyard], ['Country', globe], ['Calendar', calendar], ['Heartbeat', heartbeat]];
if (EMBED) { $('#tabs').remove(); ({ markets, fxg, curves, takeovers, graveyard, globe, calendar, heartbeat }[D.scene] || markets)();
  if (D.owner) { const fe = window.frameElement; let shownAt = 0, closing = false;
    const close = () => { if (closing || !fe) return; closing = true; fe.style.opacity = 0; setTimeout(() => fe.remove(), shownAt ? 600 : 0); };
    setTimeout(() => { if (fe && fe.isConnected && !closing) { fe.style.opacity = 1; fe.style.pointerEvents = 'auto'; shownAt = performance.now(); } }, D.force ? 0 : 150);
    addEventListener('click', close);
    setInterval(() => { let gone = true; try { gone = !parent.document.querySelector('[data-hfl-owner="' + D.owner + '"]'); } catch (e) {}
      if (D.force && shownAt && performance.now() - shownAt > (D.min || 9000)) return close();
      if (!gone || closing) return; if (!shownAt) return close(); if (performance.now() - shownAt > (D.min || 9000)) close(); }, 200); } }
else {
  const tabs = $('#tabs'); let curp = 0;
  const show = i => { curp = i; rafs.forEach(cancelAnimationFrame); timers.forEach(x => { clearTimeout(x); clearInterval(x); }); rafs = []; timers = []; [...tabs.querySelectorAll('button:not(.rp)')].forEach((b, j) => b.classList.toggle('on', j === i)); view.innerHTML = ''; requestAnimationFrame(() => PAGES[i][1]()); };
  PAGES.forEach(([n], i) => { const b = document.createElement('button'); b.textContent = n; b.onclick = () => show(i); tabs.appendChild(b); });
  const rp = document.createElement('button'); rp.className = 'rp'; rp.textContent = '↻ Replay'; rp.onclick = () => show(curp); tabs.appendChild(rp);
  show(+(location.hash.slice(1) || 0));
}
</script></body></html>
'''
