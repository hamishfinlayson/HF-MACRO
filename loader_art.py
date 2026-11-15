"""loader_art.py - the animated scenes behind HF Macro's loading screen (v41). Pure SVG (CSS + SMIL animation),
delivered as an <img> so it plays anywhere without scripts. Decorative only: the tags are not real data."""
import base64, math, random

RED, WHITE, DIM, GREEN = "#E8212B", "#D9DEE3", "#55606C", "#2ECC71"
FONT = "Consolas, 'IBM Plex Mono', Menlo, monospace"
CX, CY = 800, 450

def _uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

# ------------------------------------------------------------------ spider web + HF compass
def web_scene(seed=7, T=18.0):
    rng = random.Random(seed)
    K, RADII, SX = 12, [205, 265, 325, 385, 440], 1.55
    def pt(ring, k):
        a = math.radians(k * 360 / K - 90); r = RADII[ring - 1]
        return (round(CX + SX * r * math.cos(a), 1), round(CY + r * math.sin(a), 1))
    out = []
    # web: spokes + rings (straight threads between spokes, like a real orb web)
    threads = []
    for k in range(K):
        a, b = pt(1, k), pt(5, k)
        threads.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" pathLength="100"/>')
    for ring in range(1, 6):
        pts = " ".join(f"{pt(ring, k)[0]},{pt(ring, k)[1]}" for k in range(K + 1))
        threads.append(f'<polyline points="{pts}" fill="none" pathLength="100"/>')
    out.append(f'<g class="web" stroke="{WHITE}" stroke-opacity=".22" stroke-width="1.2">{"".join(threads)}</g>')
    # spider's route: a closed loop along rings and spokes
    legs = [(3, 0, 5), (5, 3, 2), (2, 6, 4), (4, 9, 3)]
    route = []
    for ring, k0, nxt in legs:                       # walk along `ring` from spoke k0 for 3 spokes, then along the spoke to ring `nxt`
        for k in range(k0, k0 + 3 + 1): route.append(pt(ring, k % K))
        route.append(pt(nxt, (k0 + 3) % K))
    route.append(route[0])
    clean = [route[0]] + [p for i, p in enumerate(route[1:], 1) if p != route[i - 1]]
    d = "M " + " L ".join(f"{x},{y}" for x, y in clean)
    seg = [math.dist(clean[i], clean[i + 1]) for i in range(len(clean) - 1)]
    tot = sum(seg); cum = [0]
    for s in seg: cum.append(cum[-1] + s)
    tags = ["MOM ▲ 0.82", "CORR 0.64", "σ +2.1", "SIGNAL 07", "VOL 14.2", "NODE CL-3", "Δ 0.31", "SCAN ✓", "BETA 1.07",
            "ALPHA?", "TREND ▲", "Z −1.4", "HIT 58%", "LAG 4W", "RANK 03", "FLOW +", "EDGE?", "PAIR GC/SI"]
    nodes, seen = [], set()
    for i, p in enumerate(clean[:-1]):
        if p in seen: continue
        seen.add(p); f = cum[i] / tot; delay = round(f * T - T, 2); tag = tags[len(nodes) % len(tags)]
        dx = 14 if p[0] >= CX else -14; anchor = "start" if dx > 0 else "end"
        nodes.append(f'<g style="animation-delay:{delay}s" class="hit"><circle cx="{p[0]}" cy="{p[1]}" r="5" fill="{RED}"/>'
                     f'<circle cx="{p[0]}" cy="{p[1]}" r="5" fill="none" stroke="{RED}" class="ring" style="animation-delay:{delay}s"/>'
                     f'<text x="{p[0] + dx}" y="{p[1] - 10}" text-anchor="{anchor}">{tag}</text></g>')
    out.append("".join(nodes))
    # faint static intersections
    out.append("".join(f'<circle cx="{pt(r, k)[0]}" cy="{pt(r, k)[1]}" r="1.8" fill="{WHITE}" fill-opacity=".35"/>' for r in range(1, 6) for k in range(K)))
    # the spider (drawn facing right; animateMotion turns it along the path)
    spider = spider_svg(1.9)
    out.append(f'<path d="{d}" fill="none" stroke="{RED}" stroke-opacity=".18" stroke-width="2" stroke-dasharray="4 8"/>')
    out.append(f'<g>{spider}<animateMotion dur="{T}s" repeatCount="indefinite" rotate="auto" path="{d}"/></g>')
    # centre: H and F slide together, a compass draws itself around them, then the needle spins
    circ = 2 * math.pi * 150
    ticks = "".join(f'<line x1="{CX}" y1="{CY - 150}" x2="{CX}" y2="{CY - (136 if k % 3 else 124)}" transform="rotate({k * 15} {CX} {CY})"/>' for k in range(24))
    out.append(f'''
<circle cx="{CX}" cy="{CY}" r="168" fill="#000" fill-opacity=".85"/>
<g font-family="{FONT}" font-weight="700" font-size="120" text-anchor="middle">
  <text x="{CX - 46}" y="{CY + 42}" fill="{RED}" opacity="0">H
    <animate attributeName="x" from="{CX - 520}" to="{CX - 46}" dur="1.2s" begin="0.2s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
    <animate attributeName="opacity" values="0;1;1;.22" keyTimes="0;.15;.62;1" dur="3.2s" begin="0.2s" fill="freeze"/></text>
  <text x="{CX + 46}" y="{CY + 42}" fill="{WHITE}" opacity="0">F
    <animate attributeName="x" from="{CX + 520}" to="{CX + 46}" dur="1.2s" begin="0.2s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
    <animate attributeName="opacity" values="0;1;1;.22" keyTimes="0;.15;.62;1" dur="3.2s" begin="0.2s" fill="freeze"/></text>
</g>
<circle cx="{CX}" cy="{CY}" r="150" fill="none" stroke="{RED}" stroke-width="3" stroke-dasharray="{circ:.0f}" stroke-dashoffset="{circ:.0f}" transform="rotate(-90 {CX} {CY})" filter="url(#glow)">
  <animate attributeName="stroke-dashoffset" from="{circ:.0f}" to="0" dur="1s" begin="1.3s" fill="freeze"/></circle>
<g stroke="{WHITE}" stroke-width="2" opacity="0">{ticks}<animate attributeName="opacity" from="0" to=".8" dur=".5s" begin="2.1s" fill="freeze"/></g>
<g font-family="{FONT}" font-size="20" fill="{WHITE}" text-anchor="middle" opacity="0">
  <text x="{CX}" y="{CY - 98}">N</text><text x="{CX + 106}" y="{CY + 7}">E</text><text x="{CX}" y="{CY + 112}">S</text><text x="{CX - 106}" y="{CY + 7}">W</text>
  <animate attributeName="opacity" from="0" to="1" dur=".5s" begin="2.3s" fill="freeze"/></g>
<g opacity="0">
  <animate attributeName="opacity" from="0" to="1" dur=".4s" begin="2.5s" fill="freeze"/>
  <g>
    <polygon points="{CX},{CY - 118} {CX + 13},{CY} {CX - 13},{CY}" fill="{RED}" filter="url(#glow)"/>
    <polygon points="{CX},{CY + 118} {CX + 13},{CY} {CX - 13},{CY}" fill="{WHITE}"/>
    <circle cx="{CX}" cy="{CY}" r="8" fill="#000" stroke="{RED}" stroke-width="3"/>
    <animateTransform attributeName="transform" type="rotate" begin="2.5s" dur="4s" repeatCount="indefinite"
      values="0 {CX} {CY};400 {CX} {CY};330 {CX} {CY};370 {CX} {CY};360 {CX} {CY}" keyTimes="0;.35;.6;.8;1"
      calcMode="spline" keySplines=".3 0 .2 1;.4 0 .6 1;.4 0 .6 1;.4 0 .6 1"/>
  </g>
</g>''')
    style = f'''<style>
.web * {{ stroke-dasharray: 100; stroke-dashoffset: 100; animation: draw 2.4s ease-out .3s forwards; }}
@keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
.hit {{ opacity: 0; animation: hit {T}s linear infinite; }}
.hit text {{ font-family: {FONT}; font-size: 15px; fill: {GREEN}; letter-spacing: .06em; }}
@keyframes hit {{ 0% {{ opacity: 1; }} 22% {{ opacity: .9; }} 30% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
.ring {{ transform-box: fill-box; transform-origin: center; animation: ring {T}s ease-out infinite; }}
@keyframes ring {{ 0% {{ transform: scale(1); opacity: 1; }} 6% {{ transform: scale(5); opacity: 0; }} 100% {{ opacity: 0; }} }}
</style>'''
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid meet">'
           f'<defs><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/>'
           f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>{style}{"".join(out)}</svg>')
    return _uri(svg)

# ------------------------------------------------------------------ roulette wheel
ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
def roulette_scene():
    n = len(ORDER); R1, R2, R3 = 300, 245, 205
    def p(r, a): a = math.radians(a - 90); return CX + r * math.cos(a), CY + r * math.sin(a)
    pockets = []
    for i, num in enumerate(ORDER):
        a0, a1 = i * 360 / n, (i + 1) * 360 / n
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p(R1, a0), p(R1, a1), p(R2, a1), p(R2, a0)
        col = "#0E7A3A" if num == 0 else ("#B5121B" if i % 2 else "#111")
        pockets.append(f'<path d="M{x0:.1f},{y0:.1f} A{R1},{R1} 0 0,1 {x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f} A{R2},{R2} 0 0,0 {x3:.1f},{y3:.1f} Z" fill="{col}" stroke="#C9A24A" stroke-width="1.2"/>')
        tx, ty = p((R1 + R2) / 2, (a0 + a1) / 2)
        pockets.append(f'<text x="{tx:.1f}" y="{ty:.1f}" transform="rotate({(a0 + a1) / 2:.1f} {tx:.1f} {ty:.1f})" text-anchor="middle" dominant-baseline="central">{num}</text>')
    spokes = "".join(f'<line x1="{CX}" y1="{CY}" x2="{p(R3, k * 45)[0]:.1f}" y2="{p(R3, k * 45)[1]:.1f}"/>' for k in range(8))
    frets = "".join(f'<line x1="{p(R2, i * 360 / n)[0]:.1f}" y1="{p(R2, i * 360 / n)[1]:.1f}" x2="{p(R3, i * 360 / n)[0]:.1f}" y2="{p(R3, i * 360 / n)[1]:.1f}"/>' for i in range(n))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid meet">
<defs><radialGradient id="wood" cx="50%" cy="50%" r="50%"><stop offset="80%" stop-color="#2a1608"/><stop offset="100%" stop-color="#4a2a10"/></radialGradient>
<radialGradient id="cone" cx="50%" cy="45%" r="55%"><stop offset="0%" stop-color="#3a3a3a"/><stop offset="100%" stop-color="#0c0c0c"/></radialGradient>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<style>text {{ font-family: {FONT}; font-weight: 700; font-size: 17px; fill: #fff; }}
.bets {{ font-size: 22px; letter-spacing: .5em; fill: {RED}; animation: blink 1.1s steps(1) infinite; }} @keyframes blink {{ 50% {{ opacity: .15; }} }}</style>
<circle cx="{CX}" cy="{CY}" r="372" fill="url(#wood)" stroke="#C9A24A" stroke-width="3"/>
<circle cx="{CX}" cy="{CY}" r="340" fill="#120a04" stroke="#6b4a1e" stroke-width="2"/>
<g><animateTransform attributeName="transform" type="rotate" from="0 {CX} {CY}" to="360 {CX} {CY}" dur="7s" repeatCount="indefinite"/>
  {"".join(pockets)}
  <g stroke="#C9A24A" stroke-width="1.5">{frets}</g>
  <circle cx="{CX}" cy="{CY}" r="{R2}" fill="none" stroke="#C9A24A" stroke-width="2"/>
  <circle cx="{CX}" cy="{CY}" r="{R3}" fill="url(#cone)" stroke="#C9A24A" stroke-width="2"/>
  <g stroke="#C9A24A" stroke-width="5" stroke-linecap="round">{spokes}</g>
  <circle cx="{CX}" cy="{CY}" r="52" fill="#000" stroke="{RED}" stroke-width="3" filter="url(#glow)"/>
  <text x="{CX}" y="{CY + 2}" text-anchor="middle" dominant-baseline="central" style="font-size:44px"><tspan fill="{RED}">H</tspan><tspan fill="#fff">F</tspan></text>
</g>
<g><animateTransform attributeName="transform" type="rotate" values="0 {CX} {CY};-1260 {CX} {CY};-1440 {CX} {CY}" keyTimes="0;.7;1" calcMode="spline" keySplines=".1 .6 .4 1;.4 0 .6 1" dur="7s" repeatCount="indefinite"/>
  <circle cx="{CX}" cy="{CY - 322}" r="10" fill="#fff" filter="url(#glow)">
    <animate attributeName="cy" values="{CY - 322};{CY - 322};{CY - 288};{CY - 300};{CY - 272};{CY - 272}" keyTimes="0;.5;.66;.74;.84;1" dur="7s" repeatCount="indefinite"/></circle>
</g>
<text x="{CX}" y="868" text-anchor="middle" class="bets">NO MORE BETS</text>
</svg>'''
    return _uri(svg)


def spider_svg(scale=1.9):
    """The spider (facing right, centred on 0,0)."""
    leg_svg = []
    for side in (-1, 1):
        for i, (rx, kx, ky, fx, fy) in enumerate([(9, 22, 20, 34, 30), (5, 12, 26, 16, 40), (1, -6, 26, -10, 40), (-3, -20, 20, -34, 32)]):
            bx, by = rx, side * 5
            ph = "0s" if (i + (side > 0)) % 2 else "0.2s"
            leg_svg.append(f'<polyline points="{bx},{by} {kx},{side * ky} {fx},{side * fy}" fill="none" stroke="#9AA4AE" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
                           f'<animateTransform attributeName="transform" type="rotate" values="-10 {bx} {by};10 {bx} {by};-10 {bx} {by}" dur="0.4s" begin="{ph}" repeatCount="indefinite"/></polyline>')
    spider = (f'<g filter="url(#glow)" transform="scale({scale})">{"".join(leg_svg)}'
              f'<ellipse cx="-14" cy="0" rx="16" ry="12" fill="#0b0b0b" stroke="{RED}" stroke-width="1.6"/>'
              f'<path d="M-24,0 L-8,0 M-16,-6 L-16,6" stroke="{RED}" stroke-width="2"/>'
              f'<ellipse cx="6" cy="0" rx="9" ry="8" fill="#0b0b0b" stroke="{RED}" stroke-width="1.4"/>'
              f'<circle cx="12" cy="-3" r="1.8" fill="{RED}"/><circle cx="12" cy="3" r="1.8" fill="{RED}"/>'
              f'<circle cx="14" cy="-1" r="1.1" fill="{RED}"/><circle cx="14" cy="1.2" r="1.1" fill="{RED}"/></g>')
    return spider


SCENES = {"web": web_scene, "roulette": roulette_scene}
