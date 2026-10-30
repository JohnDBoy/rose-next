"""A 3D view of a zone's walk grid (<ZONE FOLDER>.lnav) round a spot, as one HTML page.

    python scripts/nav-view.py 62 5790 5240             Shady Jungle, 45 m round (5790, 5240) m
    python scripts/nav-view.py 62 5660 5200 --radius 30 the high bridge
    python scripts/nav-view.py 31 5162 5057 --png       Goblin B1, plus a still picture
    python scripts/nav-view.py 52 5576 4622 --lnav build/nav/lnav-before-stairs/.../LP01.lnav --tag before
    python scripts/nav-view.py 62 5796 5258 --radius 22 --zmax 40   the stump ramp, without the deck above
    python scripts/nav-view.py 62 5804 5246 --radius 30 --pitch 1.15 --walkable   the whole ramp, from the side
    python scripts/nav-view.py 71 5200 5235 --radius 34 --walkable --by-height    Muris' spawn pyramid
    python scripts/nav-view.py 25 5385 5205 --radius 100 --by-height --spawns --water   Anima Lake's middle

Every floor the bake stored is drawn as a 1 m tile at its real height: walkable ground,
walkable floors on map objects (decks, ramps, bridges, platforms), and, in grey, surfaces
that are not walkable (roofs, pillar tops, unreached floors). The page needs nothing else:
drag to turn it, the wheel to zoom, hover a tile for its height and kind. It shows what the
server walks on, layer by layer; build/nav/<FOLDER>.png (nav-bake.py) flattens the same data.

Writes build/nav/view-<FOLDER>-<x>-<y>.html (and .png with --png). Read-only.
"""

import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mapgen import navbake  # noqa: E402
from rosefmt import ifo, lnav  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILE_CM = 16000
CELL_CM = 100
WR = lnav.WALK | lnav.REACHED
GROUND, OBJECT, OTHER, WATER = 0, 1, 2, 3
KIND_NAMES = ["walkable ground", "walkable floor on an object", "not walkable", "water surface"]


def terrain_z(t, lx, ly):
    """Bilinear terrain height (cm) at tile-local cm, over the 2.5 m vertices (row 0 = south)."""
    fx, fy = lx / 250.0, ly / 250.0
    ix, iy = min(int(fx), lnav.TILE_VERTS - 2), min(int(fy), lnav.TILE_VERTS - 2)
    tx, ty = fx - ix, fy - iy
    h = t.heights.astype(np.float64)
    return (h[iy, ix] * (1 - tx) * (1 - ty) + h[iy, ix + 1] * tx * (1 - ty)
            + h[iy + 1, ix] * (1 - tx) * ty + h[iy + 1, ix + 1] * tx * ty)


def water(zone_dir, pts, cx, cy):
    """Water-surface tiles (x, y, level m, WATER) over the floors in pts that lie under one of
    the zone's flat water rectangles (IFO lump 9: corners x, level, y, client cm less the
    520000 origin). One tile per cell, at the highest level covering it."""
    rects = []
    for f in os.listdir(zone_dir):
        if re.match(r"\d+_\d+\.ifo$", f, re.I):
            o = ifo.parse(open(os.path.join(zone_dir, f), "rb").read()).lump(ifo.OCEAN)
            for sx, sz, sy, ex, ez, ey in (o.rects if o is not None else []):
                rects.append((min(sx, ex) + 520000, max(sx, ex) + 520000,
                              min(sy, ey) + 520000, max(sy, ey) + 520000, sz))
    low = {}
    for x, y, z, k in pts:
        if k != WATER and z < low.get((x, y), 1e9):
            low[(x, y)] = z
    out = []
    for (x, y), z in low.items():
        wx, wy = cx + x * 100, cy + y * 100
        lv = max((r[4] for r in rects if r[0] <= wx <= r[1] and r[2] <= wy <= r[3] and z * 100 < r[4]),
                 default=None)
        if lv is not None:
            out.append((x, y, lv / 100.0, WATER))
    return out


def floors(nav, cx, cy, radius_m):
    """[(x m, y m, z m, kind)] of every stored floor within radius_m of (cx, cy) cm, x/y relative."""
    out = []
    r_cm = radius_m * 100
    for (sx, sy), t in nav.tiles.items():
        x0, y0 = sx * TILE_CM, sy * TILE_CM
        if x0 > cx + r_cm or x0 + TILE_CM < cx - r_cm or y0 > cy + r_cm or y0 + TILE_CM < cy - r_cm:
            continue
        cmask = t.complex_mask.reshape(-1)
        simple = t.simple.reshape(-1)
        idx = np.flatnonzero(cmask)
        rank = {int(ci): k for k, ci in enumerate(idx)}
        offs = np.concatenate([[0], np.cumsum(t.cells["n_spans"].astype(np.int64))]) if len(idx) else None
        c0 = max(0, int((cx - r_cm - x0) // CELL_CM))
        c1 = min(lnav.TILE_CELLS - 1, int((cx + r_cm - x0) // CELL_CM))
        r0 = max(0, int((cy - r_cm - y0) // CELL_CM))
        r1 = min(lnav.TILE_CELLS - 1, int((cy + r_cm - y0) // CELL_CM))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                wx, wy = x0 + (c + 0.5) * CELL_CM, y0 + (r + 0.5) * CELL_CM
                if (wx - cx) ** 2 + (wy - cy) ** 2 > r_cm * r_cm:
                    continue
                i = r * lnav.TILE_CELLS + c
                rx, ry = (wx - cx) / 100.0, (wy - cy) / 100.0
                if not cmask[i]:
                    z = terrain_z(t, wx - x0, wy - y0)
                    out.append((rx, ry, z / 100.0, GROUND if simple[i] else OTHER))
                    continue
                k = rank[i]
                for s in t.spans[offs[k]:offs[k + 1]]:
                    fl = int(s["flags"])
                    if (fl & WR) == WR:
                        kind = GROUND if fl & lnav.TERRAIN else OBJECT
                    else:
                        kind = OTHER
                    out.append((rx, ry, int(s["z"]) / 100.0, kind))
    return out


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
.viz-root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --grid: #e4e3df;
  --series-ground: #1baf7a;
  --series-object: #2a78d6;
  --neutral-other: #c3c2bb;
  --height-low: #b8d2f3;
  --height-high: #123e8a;
  --mark: #d9480f;
  --water: #3d8fd6;
  --mark2: #6b2fb3;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --grid: #33322f;
    --series-ground: #199e70;
    --series-object: #3987e5;
    --neutral-other: #55544f;
    --height-low: #1e3a63;
    --height-high: #a8cbf7;
    --mark: #ff8a4c;
    --water: #4aa3ef;
    --mark2: #b48cf2;
  }
}
html, body { margin: 0; height: 100%; }
.viz-root { height: 100%; display: flex; flex-direction: column; background: var(--surface-1);
  color: var(--text-primary); font: 14px/1.4 system-ui, "Segoe UI", sans-serif; }
header { padding: 14px 18px 6px; }
h1 { font-size: 17px; margin: 0 0 4px; font-weight: 600; }
.sub { color: var(--text-secondary); margin: 0; max-width: 980px; }
.legend { display: flex; gap: 18px; padding: 8px 18px; flex-wrap: wrap; color: var(--text-secondary); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; background: var(--mark);
  box-shadow: 0 0 0 2px var(--surface-1); }
.ramp { width: 120px; height: 12px; border-radius: 3px; display: inline-block;
  background: linear-gradient(90deg, var(--height-low), var(--height-high)); }
.stage { position: relative; flex: 1; min-height: 300px; }
canvas { width: 100%; height: 100%; display: block; cursor: grab; }
canvas:active { cursor: grabbing; }
.tip { position: absolute; pointer-events: none; padding: 6px 9px; border-radius: 6px;
  background: var(--surface-1); color: var(--text-primary); border: 1px solid var(--grid);
  box-shadow: 0 2px 8px rgba(0,0,0,.15); font-size: 13px; display: none; white-space: nowrap; }
.hint { position: absolute; right: 14px; bottom: 10px; color: var(--text-secondary); font-size: 12px; }
</style>
</head>
<body>
<div class="viz-root">
  <header>
    <h1>__TITLE__</h1>
    <p class="sub">__SUB__</p>
  </header>
  <div class="legend" id="legend"></div>
  <div class="stage">
    <canvas id="c"></canvas>
    <div class="tip" id="tip"></div>
    <div class="hint">Drag to turn &middot; wheel to zoom &middot; hover a tile</div>
  </div>
</div>
<script>
const D = __DATA__;            // flat: x, y, z (m), kind
const NAMES = __NAMES__;
const BY_HEIGHT = __BY_HEIGHT__;   // colour walkable floors by height (one hue, light = low)
const MARKS = __MARKS__;           // regen points: x, y, z (m), drawn on top
const MARKS2 = __MARKS2__;         // --mark spots (a path's corners): x, y, z (m), joined in order
const N = D.length / 4;
const root = document.querySelector('.viz-root');
const css = n => getComputedStyle(root).getPropertyValue(n).trim();
let COLORS, SURFACE, LOW, HIGH, MARK;
const rgb = hex => { const n = parseInt(hex.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
function readColors() {
  COLORS = [css('--series-ground'), css('--series-object'), css('--neutral-other'), css('--water')];
  SURFACE = css('--surface-1');
  LOW = rgb(css('--height-low')); HIGH = rgb(css('--height-high'));
  MARK = css('--mark');
}
readColors();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readColors(); draw(); });

// legend with counts (identity never colour alone: names beside the swatches)
const counts = [0, 0, 0, 0];
for (let i = 0; i < N; i++) counts[D[i * 4 + 3]]++;
const SWATCH = ['--series-ground', '--series-object', '--neutral-other', '--water'];
const swatch = k => `<span><i class="sw" style="background:var(${SWATCH[k]})${k === 3 ? ';opacity:.5' : ''}"></i>${NAMES[k]} (${counts[k].toLocaleString()})</span>`;
document.getElementById('legend').innerHTML = [0, 1, 2, 3].filter(k => k < 3 || counts[k]).map(swatch).join('');

let zMin = Infinity, zMax = -Infinity;
for (let i = 0; i < N; i++) { const z = D[i * 4 + 2]; if (z < zMin) zMin = z; if (z > zMax) zMax = z; }
const zMid = (zMin + zMax) / 2;
// the height ramp's range: the 2nd-98th percentile of the walkable floors, so a few tiles on a
// tall structure do not wash out the ground's relief (beyond it, the ends of the ramp)
let rLo = zMin, rHi = zMax;
if (BY_HEIGHT) {
  const zs = [];
  for (let i = 0; i < N; i++) if (D[i * 4 + 3] < 2) zs.push(D[i * 4 + 2]);
  zs.sort((a, b) => a - b);
  if (zs.length) { rLo = zs[Math.floor(zs.length * 0.02)]; rHi = zs[Math.min(zs.length - 1, Math.floor(zs.length * 0.98))]; }
  if (rHi - rLo < 0.5) rHi = rLo + 0.5;
}
if (BY_HEIGHT)   // walkable floors on the height scale; not walkable stays grey
  document.getElementById('legend').innerHTML =
    `<span>walkable, by height: ${rLo.toFixed(1)} m <i class="ramp"></i> ${rHi.toFixed(1)} m `
    + `(${(counts[0] + counts[1]).toLocaleString()})</span>`
    + swatch(2) + (counts[3] ? swatch(3) : '');
if (MARKS.length)
  document.getElementById('legend').insertAdjacentHTML('beforeend',
    `<span><i class="dot"></i>regen point (${MARKS.length / 3})</span>`);
if (MARKS2.length)
  document.getElementById('legend').insertAdjacentHTML('beforeend',
    `<span><i class="dot" style="background:var(--mark2)"></i>marked spots, in order (${MARKS2.length / 3})</span>`);

const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let yaw = __YAW__, pitch = __PITCH__, zoom = 1, W = 0, H = 0, dpr = 1;
let fit = 1, offX = 0, offY = 0;   // the opening view fits the whole model, centred
function resize() {
  dpr = window.devicePixelRatio || 1;
  W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  fit = 1; offX = 0; offY = 0;
  project();
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (let j = 0; j < N * 8; j += 2) {
    x0 = Math.min(x0, P[j]); x1 = Math.max(x1, P[j]);
    y0 = Math.min(y0, P[j + 1]); y1 = Math.max(y1, P[j + 1]);
  }
  fit = 0.92 * Math.min(W / Math.max(1, x1 - x0), H / Math.max(1, y1 - y0));
  offX = -((x0 + x1) / 2 - W / 2) * fit;
  offY = -((y0 + y1) / 2 - H / 2) * fit;
  draw();
}
window.addEventListener('resize', resize);

// orthographic camera: turn round z by yaw, tilt by pitch; screen y grows down
const P = new Float32Array(N * 8), depth = new Float32Array(N), order = new Uint32Array(N);
const CORNERS = [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]];
function project() {
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const scale = Math.min(W, H) / (__RADIUS__ * 2.4) * zoom * fit;
  for (let i = 0; i < N; i++) {
    const x = D[i * 4], y = D[i * 4 + 1], z = D[i * 4 + 2] - zMid;
    for (let k = 0; k < 4; k++) {
      const px = x + CORNERS[k][0], py = y + CORNERS[k][1];
      const rx = px * cy - py * sy, ry = px * sy + py * cy;
      P[i * 8 + k * 2] = W / 2 + offX + rx * scale;
      P[i * 8 + k * 2 + 1] = H / 2 + offY - (ry * cp + z * sp) * scale;
    }
    const rx = x * cy - y * sy, ry = x * sy + y * cy;
    depth[i] = ry * sp - z * cp;    // larger = farther from the viewer
    order[i] = i;
  }
  order.sort((a, b) => depth[b] - depth[a]);   // painter's: far first
}
function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => Math.round(v * f));
  return `rgb(${c.map(v => Math.max(0, Math.min(255, v))).join(',')})`;
}
function draw() {
  if (!W) return;
  project();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = SURFACE; ctx.fillRect(0, 0, W, H);
  const span = Math.max(1, zMax - zMin);
  // zoomed in: a thin gap between tiles shows the grid; zoomed out: the tile's own colour
  // round its edge closes the hairline seams, which read as stripes on a big floor
  const tileGap = zoom > 1.6 ? 0.6 : 0;
  ctx.lineWidth = tileGap || 0.8;
  for (let n = 0; n < N; n++) {
    const i = order[n];
    if (D[i * 4 + 3] === 3) {
      // water: a translucent surface over the floor beneath, no seam stroke (it would double up)
      ctx.globalAlpha = 0.45; ctx.fillStyle = COLORS[3];
      ctx.beginPath();
      ctx.moveTo(P[i * 8], P[i * 8 + 1]);
      for (let k = 1; k < 4; k++) ctx.lineTo(P[i * 8 + k * 2], P[i * 8 + k * 2 + 1]);
      ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
      continue;
    }
    if (BY_HEIGHT && D[i * 4 + 3] !== 2) {
      const t = Math.max(0, Math.min(1, (D[i * 4 + 2] - rLo) / (rHi - rLo)));
      ctx.fillStyle = `rgb(${LOW.map((v, c) => Math.round(v + (HIGH[c] - v) * t)).join(',')})`;
    } else {
      // height cue: higher tiles a touch lighter, within the same hue
      const f = 0.82 + 0.3 * (D[i * 4 + 2] - zMin) / span;
      ctx.fillStyle = shade(COLORS[D[i * 4 + 3]], f);
    }
    ctx.beginPath();
    ctx.moveTo(P[i * 8], P[i * 8 + 1]);
    for (let k = 1; k < 4; k++) ctx.lineTo(P[i * 8 + k * 2], P[i * 8 + k * 2 + 1]);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = tileGap ? SURFACE : ctx.fillStyle;
    ctx.stroke();
  }
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const scale = Math.min(W, H) / (__RADIUS__ * 2.4) * zoom * fit;
  for (let j = 0; j < MARKS.length; j += 3) {
    const x = MARKS[j], y = MARKS[j + 1], z = MARKS[j + 2] - zMid;
    const rx = x * cy - y * sy, ry = x * sy + y * cy;
    const px = W / 2 + offX + rx * scale, py = H / 2 + offY - (ry * cp + z * sp) * scale;
    ctx.beginPath(); ctx.arc(px, py, 5.5, 0, 2 * Math.PI);
    ctx.fillStyle = MARK; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = SURFACE; ctx.stroke();
  }
  // marked spots: a line through them in order, then the dots
  const m2 = css('--mark2'), pts2 = [];
  for (let j = 0; j < MARKS2.length; j += 3) {
    const x = MARKS2[j], y = MARKS2[j + 1], z = MARKS2[j + 2] - zMid;
    const rx = x * cy - y * sy, ry = x * sy + y * cy;
    pts2.push([W / 2 + offX + rx * scale, H / 2 + offY - (ry * cp + z * sp) * scale]);
  }
  if (pts2.length > 1) {
    ctx.beginPath(); ctx.moveTo(pts2[0][0], pts2[0][1]);
    for (const q of pts2.slice(1)) ctx.lineTo(q[0], q[1]);
    ctx.lineWidth = 2; ctx.strokeStyle = m2; ctx.stroke();
  }
  for (const q of pts2) {
    ctx.beginPath(); ctx.arc(q[0], q[1], 5.5, 0, 2 * Math.PI);
    ctx.fillStyle = m2; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = SURFACE; ctx.stroke();
  }
}
function inQuad(i, mx, my) {
  let inside = false;
  for (let a = 0, b = 3; a < 4; b = a++) {
    const xa = P[i * 8 + a * 2], ya = P[i * 8 + a * 2 + 1], xb = P[i * 8 + b * 2], yb = P[i * 8 + b * 2 + 1];
    if ((ya > my) !== (yb > my) && mx < (xb - xa) * (my - ya) / (yb - ya) + xa) inside = !inside;
  }
  return inside;
}
let drag = null;
cv.addEventListener('mousedown', e => { drag = { x: e.clientX, y: e.clientY, yaw, pitch }; tip.style.display = 'none'; });
window.addEventListener('mouseup', () => { drag = null; });
const tip = document.getElementById('tip');
cv.addEventListener('mousemove', e => {
  if (drag) {
    yaw = drag.yaw + (e.clientX - drag.x) * 0.01;
    pitch = Math.max(0.05, Math.min(1.55, drag.pitch + (e.clientY - drag.y) * 0.01));
    draw();
    return;
  }
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  for (let n = N - 1; n >= 0; n--) {           // nearest first
    const i = order[n];
    if (inQuad(i, mx, my)) {
      tip.innerHTML = `<b>${NAMES[D[i * 4 + 3]]}</b><br>height ${D[i * 4 + 2].toFixed(1)} m &middot; `
        + `at (${(__CX__ + D[i * 4]).toFixed(0)}, ${(__CY__ + D[i * 4 + 1]).toFixed(0)}) m`;
      tip.style.display = 'block';
      tip.style.left = Math.min(mx + 14, W - tip.offsetWidth - 4) + 'px';
      tip.style.top = (my + 14) + 'px';
      return;
    }
  }
  tip.style.display = 'none';
});
cv.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
cv.addEventListener('wheel', e => {
  e.preventDefault();
  zoom = Math.max(0.4, Math.min(8, zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
  draw();
}, { passive: false });
resize();
</script>
</body>
</html>
"""


def write_png(path, pts, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    colors = ["#1baf7a", "#2a78d6", "#c3c2bb"]
    fig = plt.figure(figsize=(11, 8), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    for kind in (OTHER, GROUND, OBJECT):
        quads = [[(x - .5, y - .5, z), (x + .5, y - .5, z), (x + .5, y + .5, z), (x - .5, y + .5, z)]
                 for x, y, z, k in pts if k == kind]
        if quads:
            ax.add_collection3d(Poly3DCollection(quads, facecolors=colors[kind], edgecolors="none",
                                                 label="%s (%d)" % (KIND_NAMES[kind], len(quads))))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(min(ys), max(ys))
    ax.set_zlim(min(zs), max(zs))
    ax.set_box_aspect((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
    ax.view_init(elev=35, azim=-55)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_zlabel("height (m)")
    ax.set_title(title, fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    fig.savefig(path, bbox_inches="tight")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zone", type=int, help="LIST_ZONE row")
    ap.add_argument("x", type=float, help="centre, world metres (the minimap's numbers)")
    ap.add_argument("y", type=float)
    ap.add_argument("--radius", type=float, default=45.0, help="metres round the centre (default 45)")
    ap.add_argument("--png", action="store_true", help="also a still picture (matplotlib)")
    ap.add_argument("--lnav", help="read this .lnav instead of the zone's (an older bake, to compare)")
    ap.add_argument("--tag", default="", help="added to the output name (with --lnav)")
    ap.add_argument("--zmax", type=float, help="leave out floors higher than this (metres): a deck over the spot")
    ap.add_argument("--walkable", action="store_true", help="only walkable floors (no grey): a cleaner picture")
    ap.add_argument("--yaw", type=float, default=-0.6, help="opening camera turn, radians (default -0.6)")
    ap.add_argument("--by-height", action="store_true",
                    help="colour walkable floors by height (light = low) instead of by kind; not walkable stays grey")
    ap.add_argument("--spawns", action="store_true", help="mark the regen points (the bake's anchors)")
    ap.add_argument("--water", action="store_true", help="draw the zone's water surfaces over the floors")
    ap.add_argument("--mark", action="append", default=[], metavar="X,Y,Z",
                    help="mark a spot, world metres (repeatable): the corners /nav path whispers")
    ap.add_argument("--pitch", type=float, default=0.75,
                    help="opening camera tilt, radians: 0 looks straight down, 1.55 from the side (default 0.75)")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "nav"))
    a = ap.parse_args()

    name, zon_path, folder, _deco, _cnst = navbake.zone_row(a.data, a.zone)
    fname = os.path.basename(os.path.normpath(folder))
    lnav_path = a.lnav or os.path.join(folder, fname + ".lnav")
    if not os.path.exists(lnav_path):
        raise SystemExit("no walk grid: %s (run scripts/nav-bake.py %d)" % (lnav_path, a.zone))
    nav = lnav.parse(open(lnav_path, "rb").read())
    pts = floors(nav, a.x * 100, a.y * 100, a.radius)
    if a.zmax is not None:
        pts = [p for p in pts if p[2] <= a.zmax]
    if a.walkable:
        pts = [p for p in pts if p[3] != OTHER]
    if a.water:
        pts += water(folder, pts, a.x * 100, a.y * 100)
    if not pts:
        raise SystemExit("no floors there")

    os.makedirs(a.out, exist_ok=True)
    stem = os.path.join(a.out, "view-%s-%d-%d%s" % (fname, round(a.x), round(a.y), ("-" + a.tag) if a.tag else ""))
    title = "%s walk grid, %d m round (%d, %d) m" % (name, round(a.radius), round(a.x), round(a.y))
    sub = ("Every floor the server walks on, as a 1 m tile at its real height (scripts/nav-bake.py). "
           "Where floors are stacked (a bridge over the ground, a ramp over a lower turn) each one is "
           "its own tile: the server keeps a list of floors per metre, not one height.")
    marks = []
    if a.spawns:
        for an in nav.anchors:
            if (an.x - a.x * 100) ** 2 + (an.y - a.y * 100) ** 2 <= (a.radius * 100) ** 2:
                marks += [round((an.x - a.x * 100) / 100, 1), round((an.y - a.y * 100) / 100, 1), round(an.z / 100, 2)]
    marks2 = []
    for m in a.mark:
        v = [float(t) for t in m.split(",")]
        marks2 += [round(v[0] - a.x, 1), round(v[1] - a.y, 1), round(v[2] if len(v) > 2 else 0.0, 2)]
    flat = []
    for x, y, z, k in pts:
        flat += [round(x, 1), round(y, 1), round(z, 2), k]
    page = (PAGE.replace("__TITLE__", title).replace("__SUB__", sub)
            .replace("__DATA__", json.dumps(flat, separators=(",", ":")))
            .replace("__NAMES__", json.dumps(KIND_NAMES))
            .replace("__RADIUS__", str(a.radius)).replace("__CX__", str(a.x)).replace("__CY__", str(a.y))
            .replace("__BY_HEIGHT__", "true" if a.by_height else "false")
            .replace("__MARKS__", json.dumps(marks))
            .replace("__MARKS2__", json.dumps(marks2))
            .replace("__YAW__", str(a.yaw)).replace("__PITCH__", str(max(0.05, min(1.55, a.pitch)))))
    with open(stem + ".html", "w", encoding="utf-8") as f:
        f.write(page)
    counts = [sum(1 for p in pts if p[3] == k) for k in range(len(KIND_NAMES))]
    print("%s: %d tiles (%s)" % (stem + ".html", len(pts),
                                 ", ".join("%s %d" % (KIND_NAMES[k], counts[k]) for k in range(len(KIND_NAMES)))))
    if a.png:
        write_png(stem + ".png", pts, title)
        print(stem + ".png")


if __name__ == "__main__":
    main()
