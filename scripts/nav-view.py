"""A 3D view of a zone's walk grid (<ZONE FOLDER>.lnav) round a spot, as one HTML page.

    python scripts/nav-view.py 62 5790 5240             Shady Jungle, 45 m round (5790, 5240) m
    python scripts/nav-view.py 62 5660 5200 --radius 30 the high bridge
    python scripts/nav-view.py 31 5162 5057 --png       Goblin B1, plus a still picture

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
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mapgen import navbake  # noqa: E402
from rosefmt import lnav  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILE_CM = 16000
CELL_CM = 100
WR = lnav.WALK | lnav.REACHED
GROUND, OBJECT, OTHER = 0, 1, 2
KIND_NAMES = ["walkable ground", "walkable floor on an object", "not walkable"]


def terrain_z(t, lx, ly):
    """Bilinear terrain height (cm) at tile-local cm, over the 2.5 m vertices (row 0 = south)."""
    fx, fy = lx / 250.0, ly / 250.0
    ix, iy = min(int(fx), lnav.TILE_VERTS - 2), min(int(fy), lnav.TILE_VERTS - 2)
    tx, ty = fx - ix, fy - iy
    h = t.heights.astype(np.float64)
    return (h[iy, ix] * (1 - tx) * (1 - ty) + h[iy, ix + 1] * tx * (1 - ty)
            + h[iy + 1, ix] * (1 - tx) * ty + h[iy + 1, ix + 1] * tx * ty)


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
const N = D.length / 4;
const root = document.querySelector('.viz-root');
const css = n => getComputedStyle(root).getPropertyValue(n).trim();
let COLORS, SURFACE;
function readColors() {
  COLORS = [css('--series-ground'), css('--series-object'), css('--neutral-other')];
  SURFACE = css('--surface-1');
}
readColors();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readColors(); draw(); });

// legend with counts (identity never colour alone: names beside the swatches)
const counts = [0, 0, 0];
for (let i = 0; i < N; i++) counts[D[i * 4 + 3]]++;
document.getElementById('legend').innerHTML = NAMES.map((n, k) =>
  `<span><i class="sw" style="background:var(${['--series-ground','--series-object','--neutral-other'][k]})"></i>${n} (${counts[k].toLocaleString()})</span>`).join('');

let zMin = Infinity, zMax = -Infinity;
for (let i = 0; i < N; i++) { const z = D[i * 4 + 2]; if (z < zMin) zMin = z; if (z > zMax) zMax = z; }
const zMid = (zMin + zMax) / 2;

const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let yaw = -0.6, pitch = 0.75, zoom = 1, W = 0, H = 0, dpr = 1;
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
  const tileGap = zoom > 1.6 ? 0.6 : 0;
  ctx.lineWidth = tileGap; ctx.strokeStyle = SURFACE;
  for (let n = 0; n < N; n++) {
    const i = order[n];
    // height cue: higher tiles a touch lighter, within the same hue
    const f = 0.82 + 0.3 * (D[i * 4 + 2] - zMin) / span;
    ctx.fillStyle = shade(COLORS[D[i * 4 + 3]], f);
    ctx.beginPath();
    ctx.moveTo(P[i * 8], P[i * 8 + 1]);
    for (let k = 1; k < 4; k++) ctx.lineTo(P[i * 8 + k * 2], P[i * 8 + k * 2 + 1]);
    ctx.closePath(); ctx.fill();
    if (tileGap) ctx.stroke();
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
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "nav"))
    a = ap.parse_args()

    name, zon_path, folder, _deco, _cnst = navbake.zone_row(a.data, a.zone)
    fname = os.path.basename(os.path.normpath(folder))
    lnav_path = os.path.join(folder, fname + ".lnav")
    if not os.path.exists(lnav_path):
        raise SystemExit("no walk grid: %s (run scripts/nav-bake.py %d)" % (lnav_path, a.zone))
    nav = lnav.parse(open(lnav_path, "rb").read())
    pts = floors(nav, a.x * 100, a.y * 100, a.radius)
    if not pts:
        raise SystemExit("no floors there")

    os.makedirs(a.out, exist_ok=True)
    stem = os.path.join(a.out, "view-%s-%d-%d" % (fname, round(a.x), round(a.y)))
    title = "%s walk grid, %d m round (%d, %d) m" % (name, round(a.radius), round(a.x), round(a.y))
    sub = ("Every floor the server walks on, as a 1 m tile at its real height (scripts/nav-bake.py). "
           "Where floors are stacked (a bridge over the ground, a ramp over a lower turn) each one is "
           "its own tile: the server keeps a list of floors per metre, not one height.")
    flat = []
    for x, y, z, k in pts:
        flat += [round(x, 1), round(y, 1), round(z, 2), k]
    page = (PAGE.replace("__TITLE__", title).replace("__SUB__", sub)
            .replace("__DATA__", json.dumps(flat, separators=(",", ":")))
            .replace("__NAMES__", json.dumps(KIND_NAMES))
            .replace("__RADIUS__", str(a.radius)).replace("__CX__", str(a.x)).replace("__CY__", str(a.y)))
    with open(stem + ".html", "w", encoding="utf-8") as f:
        f.write(page)
    counts = [sum(1 for p in pts if p[3] == k) for k in range(3)]
    print("%s: %d tiles (%s)" % (stem + ".html", len(pts),
                                 ", ".join("%s %d" % (KIND_NAMES[k], counts[k]) for k in range(3))))
    if a.png:
        write_png(stem + ".png", pts, title)
        print(stem + ".png")


if __name__ == "__main__":
    main()
