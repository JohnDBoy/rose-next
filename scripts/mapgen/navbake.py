"""Bake a zone's layered walk grid (<ZONE FOLDER>.lnav) from its terrain and collision meshes.

The server's map knowledge for pathfinding and Z (doc/pathfinding-and-z-plan.md, section 3.1;
format in rosefmt/lnav.py). Run through scripts/nav-bake.py.

Inputs, all through existing codecs:
  * the stitched heightmap (prefab._zone_field), sampled bilinearly like CMAP::GetHEIGHT;
  * every placed record with colliding parts, as the client builds it: IFO lump 1 (LIST_ZONE
    col 11 ZSC), 3 (col 12), 10 warp gates (LIST_DECO_SPECIAL object 1), 11 invisible collision
    panels (LIST_DECO_SPECIAL object 2) and 12 event objects (EVENT_OBJECT.ZSC); records the
    client drops (objlight.client_accepts) are left out; parts with collision 0 are not solid;
  * seeds: ZON event points (start, revive, every warp landing), IFO regen points and NPCs.
    Not warp gate records: a gate's pivot can stand past the end of its corridor, outside the
    walls (Goblin Cave B1, 2026-10-28); the landing points already seed the warps.

Rules (each one decided in the plan; the numbers are the client avatar's):
  1. Every colliding triangle is a SURFACE when its normal is within 54 degrees of vertical, up
     or down (|n.z| >= cos 54), and a WALL otherwise. The collision flag does not decide: flag 12
     ("not moveable") covers cave ceilings, walls and some floors alike.
  2. Surfaces are sampled about every 33 cm. Per 1 m cell, samples closer than 50 cm in height
     form one candidate floor. One within 50 cm of the terrain merges into it (a slab on the
     ground); one more than 50 cm below the terrain is buried and dropped (the client never goes
     below the terrain).
  3. A floor is WALK when no other geometry (wall or surface, HEIGHTONLY stairs excepted) lies
     30-180 cm above it in its cell: the body would not fit. This blocks walls, trunks, rock
     interiors, low slabs and the 4.5 m thick collision panels' edges. The band starts from the
     top of the floor's own up-facing surface, at most 60 cm over its height (2026-10-29): a 1 m
     cell of a fine flight holds several treads, and the risers up to the top one are steps the
     client climbs, not a ceiling. Muris' great stairs and the stairs by its spawn came out in
     strips, and monsters went up the side ridges. A terrain floor's surface is what merged into
     it: Goblin Cave B3's revive platform sits 0.5 m lower than B1's, each stair's bottom tread
     merged into the ground, and the stairs ended a cell short of the cave floor.
     3b. A step, not a ceiling (2026-10-29): when everything above a floor in that band lies at
     most 75 cm up, and an up-facing floor (the next tread) lies 15-75 cm up in its cell or a
     neighbour, the floor is walkable. A terrain floor only below a floor of level treads (the
     foot of a flight, Muris' lower stairs): terrain under a thin skin of sloped mesh (a snow
     drift) stays shut. Stairs made of ordinary meshes (not HEIGHTONLY) failed 3:
     a 1 m cell holds the next tread and its riser, which looked like a low ceiling. The Goblin
     Cave B3 revive platform's stairs were all unwalkable (scripts/nav-view.py showed it).
  4. Neighbouring walkable floors link when they differ by at most 135 cm on terrain and on
     HEIGHTONLY stairs (the avatar's step; over a 1 m cell that is 53.5 degrees, its 54-degree
     slope rule). Where an object floor is involved, by at most 60 cm, or by at most 135 when
     the higher floor's surface starts within 60 cm of the lower one's top: the client walks up
     any mesh under 54 degrees, and stops on a steeper face only when it rises above about 0.7
     of the avatar's centre of mass over its feet (UpdateFootHeight_Avatar), so a riser, not a
     cell's average rise, is the limit. A ramp or a fine flight rises through its cell: Muris'
     great stairs rise 78 cm a metre and were cut into 1 m islands. Each floor stores how far
     its surface reaches below and above its height (.lnav version 2) and the server applies
     the same rule (Nav::StepLinks). With 135 on average heights, Goblin Cave B1 leaked out of
     its tunnels over a 7 m rock (2026-10-28): steep faces between a rock's facets leave a gap.
     The object step was 45 cm until 2026-10-29; the B3 stairs' risers are up to 53 cm.
     Terrain: the client refuses every move but downhill on a 2.5 m quad of 54 degrees or more
     (its slope from the south-west corner along both edges, CMAP::GetNormal), so a link out of
     such a quad must head downhill, both ways. Bilinear heights 1 m apart hid it: the Gorge of
     Silence's walls, 56-71 degrees, linked its floor to plateaus 80-100 m up (2026-10-29).
  5. A floor is REACHED when a seed's floor links to it. Unreached floors are kept as Z-only when
     they face up (a player may still stand there) and dropped when they face down (cave
     ceilings: they only ever mattered as headroom). Paths and spawns use reached floors only.
  6. A seed snaps first to where the client puts it today: every spawn, NPC and warp landing is
     dropped onto GetHeightTop (DropFromSky), so where the cell's visual top is raised and a
     walkable floor lies at most 3 m under it, that floor. Muris' plaza is a platform 3.9 m over
     flat terrain, and regen points written at Z = 0 had seeded the hidden ground beneath it
     (2026-10-28). Else the walkable floor nearest its own Z within 3 m, else the terrain, else
     the nearest cell within 3 with a walkable floor within 3 m of its Z (a regen point on a
     pillar must not snap onto the roof above: Sikuku), else the nearest walkable floor.
  7. VISUAL TOP: where today's client draws a monster, GetHeightTop = the terrain or the highest
     hit on any colliding part that is not "not moveable" (both ray directions reduce to the
     highest hit). A reached floor more than 3 m under it is a HAZARD (a roof spawn).
  8. Clearance class from the 2D reached area: 1 next to an obstacle, 2 with 1.5 m clear around,
     3 with 2.5 m.
"""

import math
import os
import re
import zlib

import numpy as np

from . import catalogue, objlight, prefab
from rosefmt import chunk, ifo, lnav, zon as zonfmt
from rosefmt.stb import Stb

ORIGIN = 520000.0
CHUNK_CM = 16000
CELL = 100                               # cm per cell
TC = lnav.TILE_CELLS                     # cells per chunk side
STEP_CM = 135.0
OBJ_STEP_CM = 60.0
BODY_LO, BODY_HI = 30.0, 180.0
STEP_LOW_MAX = 75.0                      # 3b: what lies at most this high is a step...
TREAD_MIN = 15.0                         # ...when a tread lies this much (to STEP_LOW_MAX) higher
FLAT_NZ = math.cos(math.radians(8.0))    # a tread: an up-facing sample this close to level
TREAD_SHARE = 0.8                        # a floor of treads: this share of its up samples flat
STEEP_GRAD = math.tan(0.3 * math.pi)     # the client's terrain slope limit (54 degrees)
ON_TERRAIN_CM = 15.0                     # ...applied while the feet are this close to the terrain
SURFACE_NZ = math.cos(math.radians(54.0))
CLUSTER_GAP = 50.0
TERRAIN_MERGE = 50.0
SAMPLE_CM = 33.0
HAZARD_CM = 300.0
VISUAL_RAISED = 50.0
SEED_SNAP = 300.0
SEED_RADIUS = 3
COLL_NOTMOVEABLE, COLL_HEIGHTONLY = 8, 32
EVENT_ZSC = os.path.join("3DDATA", "SPECIAL", "EVENT_OBJECT.ZSC")
WARP_OBJECT = 1                          # object.h SPECIAL_WARP_OBJECT
KEYM, ZOFF = 1.0e6, 5.0e5                # (cell, z) sort keys

KIND_UP, KIND_DOWN, KIND_WALL = 0, 1, 2


# ------------------------------------------------------------------ inputs

def _rel(p):
    p = p.strip().replace("\\", "/")
    return re.sub(r"/+", "/", p)


def zone_row(data_dir, row):
    """(name, zon path, zone folder, deco ZSC rel, cnst ZSC rel) of a LIST_ZONE row."""
    s = Stb(os.path.join(data_dir, "3DDATA", "STB", "LIST_ZONE.STB"))
    zon_rel = _rel(s.s(row, 1))
    if not zon_rel:
        raise SystemExit("LIST_ZONE row %d has no ZON" % row)
    zon_path = os.path.join(data_dir, zon_rel)
    return (s.s(row, 0).strip(), zon_path, os.path.dirname(zon_path),
            _rel(s.s(row, 11)), _rel(s.s(row, 12)))


class Models:
    """Colliding triangles of map objects, in model space, with each triangle's collision value."""

    def __init__(self, data_dir, deco_rel, cnst_rel):
        self.data_dir = data_dir
        self.zsc = {}
        for key, rel in (("OBJECT", deco_rel), ("CNST", cnst_rel),
                         ("SPECIAL", catalogue.SPECIAL_ZSC), ("EVENT", EVENT_ZSC)):
            path = os.path.join(data_dir, rel) if rel else ""
            self.zsc[key] = catalogue.read_zsc(path) if path and os.path.exists(path) else ([], [])
        self.cache = {}

    def triangles(self, key, oid):
        k = (key, oid)
        if k not in self.cache:
            meshes, objs = self.zsc[key]
            tris, coll = [], []
            if 0 <= oid < len(objs):
                parts = objs[oid]["parts"]
                for i, part in enumerate(parts):
                    if not part["collision"] or not 0 <= part["mesh"] < len(meshes):
                        continue
                    t = catalogue.mesh_triangles(self.data_dir, meshes[part["mesh"]])
                    if t is None or not len(t):
                        continue
                    tris.append(catalogue._to_model(parts, i, t.reshape(-1, 3)).reshape(-1, 3, 3))
                    coll.append(np.full(len(t), part["collision"], np.int32))
            self.cache[k] = ((np.concatenate(tris), np.concatenate(coll)) if tris
                             else (np.zeros((0, 3, 3)), np.zeros(0, np.int32)))
        return self.cache[k]


LUMPS = ((ifo.OBJECT, "OBJECT"), (ifo.CNST, "CNST"), (ifo.WARP, "SPECIAL"),
         (ifo.COLLISION, "SPECIAL"), (ifo.EVENT_OBJECT, "EVENT"))


def _object_id(lump, rec):
    if lump == ifo.WARP:
        return WARP_OBJECT
    if lump == ifo.COLLISION:
        return catalogue.COLLISION_BOX
    return rec.obj_id


# ------------------------------------------------------------------ geometry

def _sample(w):
    """Points spread over each triangle about SAMPLE_CM apart: (points (m, 3), triangle (m,))."""
    edge = np.max(np.linalg.norm(w - np.roll(w, 1, axis=1), axis=2), axis=1)
    kk = np.clip(np.ceil(edge / SAMPLE_CM).astype(int), 1, 1000)
    pts, idx = [], []
    for k in np.unique(kk):
        sel = np.nonzero(kk == k)[0]
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1))
        keep = i + j <= k
        a, b = i[keep] / k, j[keep] / k
        t = w[sel]
        p = (t[:, None, 0] * (1 - a - b)[None, :, None] + t[:, None, 1] * a[None, :, None]
             + t[:, None, 2] * b[None, :, None])
        pts.append(p.reshape(-1, 3))
        idx.append(np.repeat(sel, len(a)))
    return np.concatenate(pts), np.concatenate(idx)


def _bilinear(field, fx, fy):
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    ok = (ix >= 0) & (iy >= 0) & (ix < field.shape[1] - 1) & (iy < field.shape[0] - 1)
    ix, iy = np.clip(ix, 0, field.shape[1] - 2), np.clip(iy, 0, field.shape[0] - 2)
    tx, ty = fx - ix, fy - iy
    h = (field[iy, ix] * (1 - tx) * (1 - ty) + field[iy, ix + 1] * tx * (1 - ty)
         + field[iy + 1, ix] * (1 - tx) * ty + field[iy + 1, ix + 1] * tx * ty)
    return np.where(ok, h, np.nan)


def _components(n, ea, eb):
    """Connected-component root of each of n nodes (union by smallest root, pointer jumping)."""
    parent = np.arange(n, dtype=np.int64)
    ea, eb = ea.astype(np.int64), eb.astype(np.int64)
    while len(ea):
        pa, pb = parent[ea], parent[eb]
        diff = pa != pb
        if not diff.any():
            break
        ea, eb, pa, pb = ea[diff], eb[diff], pa[diff], pb[diff]
        np.minimum.at(parent, np.maximum(pa, pb), np.minimum(pa, pb))
        while True:
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
    return parent


def _erode(mask, radius):
    """Cells whose every neighbour within radius (cells) is in mask."""
    out = mask.copy()
    r = int(math.floor(radius))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > radius * radius or (dx == 0 and dy == 0):
                continue
            sh = np.zeros_like(mask)
            ys = slice(max(0, -dy), mask.shape[0] - max(0, dy))
            xs = slice(max(0, -dx), mask.shape[1] - max(0, dx))
            yd = slice(max(0, dy), mask.shape[0] - max(0, -dy))
            xd = slice(max(0, dx), mask.shape[1] - max(0, -dx))
            sh[ys, xs] = mask[yd, xd]
            out &= sh
    return out


# ------------------------------------------------------------------ the bake

class Bake:
    """Everything one zone's bake produces; .nav is the rosefmt.lnav.Lnav to write."""


def bake(data_dir, row, log=print):
    name, zon_path, zdir, deco_rel, cnst_rel = zone_row(data_dir, row)
    folder = os.path.basename(zdir)
    field, (x0, y0) = prefab._zone_field(zdir)
    nty, ntx = (field.shape[0] - 1) // 64, (field.shape[1] - 1) // 64
    NY, NX = nty * TC, ntx * TC
    NC = NY * NX
    log("zone %d %s (%s): %d x %d chunks, %d x %d cells" % (row, name, folder, ntx, nty, NX, NY))

    # terrain at cell centres
    gr, gc = np.mgrid[0:NY, 0:NX]
    tz = _bilinear(field, (gc + 0.5) * CELL / 250.0, (gr + 0.5) * CELL / 250.0).reshape(-1)
    valid = ~np.isnan(tz)

    # chunks and inputs
    inputs, chunks = [], {}
    for f in sorted(os.listdir(zdir)):
        m = re.match(r"(\d+)_(\d+)\.(ifo|him)$", f, re.I)
        if not m:
            continue
        with open(os.path.join(zdir, f), "rb") as fh:
            data = fh.read()
        inputs.append((f.encode("latin-1"), zlib.crc32(data)))
        if f.lower().endswith(".ifo"):
            chunks[(int(m.group(1)), 64 - int(m.group(2)))] = ifo.parse(data)
    for rel in (os.path.relpath(zon_path, data_dir), deco_rel, cnst_rel, catalogue.SPECIAL_ZSC, EVENT_ZSC):
        p = os.path.join(data_dir, rel) if rel else ""
        if p and os.path.exists(p):
            with open(p, "rb") as fh:
                inputs.append((_rel(rel).encode("latin-1")[-255:], zlib.crc32(fh.read())))

    models = Models(data_dir, deco_rel, cnst_rel)
    cells, zs, kinds, flags = [], [], [], []      # flags: 1 heightonly, 2 visual (not "not moveable"), 4 level
    nrec = {}
    for slot, parsed in chunks.items():
        for lump, key in LUMPS:
            for rec in (r for body in parsed.lumps(lump) for r in body):
                if not objlight.client_accepts(rec.pos, slot):
                    continue
                t, coll = models.triangles(key, _object_id(lump, rec))
                if not len(t):
                    continue
                nrec[ifo.LUMP_NAMES[lump]] = nrec.get(ifo.LUMP_NAMES[lump], 0) + 1
                pos = np.array([rec.pos[0] + ORIGIN - x0 * CHUNK_CM,
                                rec.pos[1] + ORIGIN - y0 * CHUNK_CM, rec.pos[2]])
                w = ((t.reshape(-1, 3) * np.array(rec.scale)) @ catalogue._quat(rec.rot) + pos).reshape(-1, 3, 3)
                n = np.cross(w[:, 1] - w[:, 0], w[:, 2] - w[:, 0])
                ln = np.linalg.norm(n, axis=1)
                ok = ln > 1e-6
                w, coll, nz = w[ok], coll[ok], n[ok, 2] / ln[ok]
                if not len(w):
                    continue
                p, ti = _sample(w)
                c = (p[:, 0] // CELL).astype(np.int64)
                r = (p[:, 1] // CELL).astype(np.int64)
                inside = (c >= 0) & (c < NX) & (r >= 0) & (r < NY)
                p, ti, ci = p[inside], ti[inside], (r * NX + c)[inside]
                keep = valid[ci]
                p, ti, ci = p[keep], ti[keep], ci[keep]
                k = np.where(nz[ti] >= SURFACE_NZ, KIND_UP, np.where(nz[ti] <= -SURFACE_NZ, KIND_DOWN, KIND_WALL))
                fl = (((coll[ti] & COLL_HEIGHTONLY) != 0).astype(np.uint8)
                      | (((coll[ti] & COLL_NOTMOVEABLE) == 0).astype(np.uint8) << 1)
                      | ((nz[ti] >= FLAT_NZ).astype(np.uint8) << 2))
                cells.append(ci.astype(np.int32))
                zs.append(p[:, 2].astype(np.float32))
                kinds.append(k.astype(np.int8))
                flags.append(fl)
    if cells:
        cell = np.concatenate(cells); z = np.concatenate(zs).astype(np.float64)
        kind = np.concatenate(kinds); fl = np.concatenate(flags)
    else:
        cell = np.zeros(0, np.int32); z = np.zeros(0); kind = np.zeros(0, np.int8); fl = np.zeros(0, np.uint8)
    log("  records with colliding parts %s; %d samples" % (nrec, len(cell)))

    order = np.lexsort((z, cell))
    cell, z, kind, fl = cell[order], z[order], kind[order], fl[order]
    heightonly = (fl & 1) != 0

    # 7. visual top: the terrain or the highest hit on a part that is not "not moveable"
    vt = tz.copy()
    vis = (fl & 2) != 0
    if vis.any():
        vc, vz = cell[vis], z[vis]
        last = np.r_[vc[1:] != vc[:-1], True]      # sorted by (cell, z): the last of a cell is its max
        vt[vc[last]] = np.fmax(vt[vc[last]], vz[last])

    # 2. surface clusters
    surf = kind != KIND_WALL
    s_idx = np.nonzero(surf)[0]
    sc, sz, sk = cell[s_idx], z[s_idx], kind[s_idx]
    owner = np.full(len(cell), -1, np.int64)
    tnode = np.full(NC, -1, np.int64)
    tnode[valid] = np.arange(int(valid.sum()))
    n_terrain = int(valid.sum())
    t_z = tz[valid].copy()
    t_top = t_z.copy()             # the top of the surface merged into each terrain floor (3.)
    obj_cell, obj_z, obj_up, obj_ho = [], [], [], []
    obj_tread, obj_lo, obj_hi = [], [], []
    if len(s_idx):
        brk = np.r_[True, (sc[1:] != sc[:-1]) | (sz[1:] - sz[:-1] > CLUSTER_GAP)]
        starts = np.nonzero(brk)[0]
        cid = np.cumsum(brk) - 1
        isup = (sk == KIND_UP).astype(np.float64)
        n_up = np.add.reduceat(isup, starts)
        sum_up = np.add.reduceat(sz * isup, starts)
        cnt = np.add.reduceat(np.ones(len(sz)), starts)
        tot = np.add.reduceat(sz, starts)
        cz = np.where(n_up > 0, sum_up / np.maximum(n_up, 1), tot / cnt)
        ccell = sc[starts]
        cup = n_up > 0
        cho = np.maximum.reduceat(heightonly[s_idx].astype(np.uint8), starts) > 0
        # a floor of level treads (3b at the foot of a flight), and the lowest and highest point
        # of its up-facing surface (4: a ramp or a flight rises through its cell)
        isflat = (sk == KIND_UP) & ((fl[s_idx] & 4) != 0)
        n_flat = np.add.reduceat(isflat.astype(np.float64), starts)
        ctread = cup & (n_flat >= TREAD_SHARE * n_up)
        isupk = sk == KIND_UP
        clo = np.where(cup, np.minimum.reduceat(np.where(isupk, sz, np.inf), starts), cz)
        chi = np.where(cup, np.maximum.reduceat(np.where(isupk, sz, -np.inf), starts), cz)
        ct = tz[ccell]
        near = np.abs(cz - ct) <= TERRAIN_MERGE
        above = cz > ct + TERRAIN_MERGE
        # a floor on the ground merges into the terrain floor
        merge = near & cup
        if merge.any():
            tn = tnode[ccell[merge]]
            np.maximum.at(t_z, tn, cz[merge])
            np.maximum.at(t_top, tn, chi[merge])
            cluster_owner = np.full(len(starts), -1, np.int64)
            cluster_owner[merge] = tn
        else:
            cluster_owner = np.full(len(starts), -1, np.int64)
        obj_cell, obj_z, obj_up, obj_ho = ccell[above], cz[above], cup[above], cho[above]
        obj_tread, obj_lo, obj_hi = ctread[above], clo[above], chi[above]
        cluster_owner[above] = n_terrain + np.arange(int(above.sum()))
        owner[s_idx] = cluster_owner[cid]

    # nodes: every valid cell's terrain floor, then the object floors
    ncell = np.r_[np.nonzero(valid)[0], np.asarray(obj_cell, np.int64)]
    nz = np.r_[t_z, np.asarray(obj_z, np.float64)]
    nterrain = np.r_[np.ones(n_terrain, bool), np.zeros(len(obj_cell), bool)]
    nup = np.r_[np.ones(n_terrain, bool), np.asarray(obj_up, bool)]
    nho = np.r_[np.zeros(n_terrain, bool), np.asarray(obj_ho, bool)]
    N = len(ncell)
    # a floor of level treads, and its lowest and highest tread (a terrain floor is one tread)
    ntread = np.r_[np.ones(n_terrain, bool), np.asarray(obj_tread, bool)]
    zr = np.round(np.r_[t_z, np.asarray(obj_z, np.float64)])
    nbelow = np.r_[np.zeros(n_terrain), np.clip(np.round(zr[n_terrain:] - np.asarray(obj_lo, np.float64)), 0, 255)]
    nabove = np.r_[np.zeros(n_terrain), np.clip(np.round(np.asarray(obj_hi, np.float64) - zr[n_terrain:]), 0, 255)]
    nlo, nhi = zr - nbelow, zr + nabove
    # the client's terrain slope (CMAP::GetNormal): the 2.5 m quad under the walker, from its
    # south-west corner along both edges; at 54 degrees or more it refuses every move that is not
    # downhill (CObjCHAR_Collision::ApplySliding), while the feet are on the terrain
    qx = np.clip(((np.nonzero(valid)[0] % NX) + 0.5) * CELL // 250.0, 0, field.shape[1] - 2).astype(int)
    qy = np.clip(((np.nonzero(valid)[0] // NX) + 0.5) * CELL // 250.0, 0, field.shape[0] - 2).astype(int)
    h0 = field[qy, qx]
    nux = np.zeros(N)
    nuy = np.zeros(N)
    nux[:n_terrain] = np.nan_to_num(field[qy, qx + 1] - h0)      # uphill along +x
    nuy[:n_terrain] = np.nan_to_num(field[qy + 1, qx] - h0)      # uphill along +y
    nsteep = np.zeros(N, bool)
    nsteep[:n_terrain] = ((np.hypot(nux[:n_terrain], nuy[:n_terrain]) / 250.0 >= STEEP_GRAD)
                          & (t_z <= tz[valid] + ON_TERRAIN_CM))
    log("  floors: %d terrain + %d on objects" % (n_terrain, N - n_terrain))

    # 3. body test: other geometry 30-180 cm above the floor in its cell, from the top of the
    # floor's own surface (at most an object step above its height): a flight's risers up to its
    # top tread in the cell are steps. A terrain floor's surface is what merged into it (the
    # bottom tread of a flight sunk into the ground: Goblin Cave B3's revive platform)
    obst = ~heightonly
    okey = cell[obst] * KEYM + (z[obst] + ZOFF)                     # sorted: cell, then z
    top = np.r_[t_top, nhi[n_terrain:]]
    body_lo = nz + np.minimum(np.maximum(top - nz, 0.0), OBJ_STEP_CM) + BODY_LO
    nkey_lo = ncell * KEYM + (body_lo + ZOFF)
    nkey_hi = ncell * KEYM + (nz + BODY_HI + ZOFF)
    total = np.searchsorted(okey, nkey_hi, "right") - np.searchsorted(okey, nkey_lo, "right")
    own_m = obst & (owner >= 0)
    if own_m.any():
        k2 = owner[own_m] * KEYM + (z[own_m] + ZOFF)
        k2.sort()
        nid = np.arange(N)
        own = (np.searchsorted(k2, nid * KEYM + (nz + BODY_HI + ZOFF), "right")
               - np.searchsorted(k2, nid * KEYM + (body_lo + ZOFF), "right"))
    else:
        own = np.zeros(N, np.int64)
    walk = (total - own) == 0
    # 3b. the part of the band above STEP_LOW_MAX: empty means only a low step is in the way
    nkey_low = ncell * KEYM + (nz + STEP_LOW_MAX + ZOFF)
    high = np.searchsorted(okey, nkey_hi, "right") - np.searchsorted(okey, nkey_low, "right")
    if own_m.any():
        own_high = (np.searchsorted(k2, nid * KEYM + (nz + BODY_HI + ZOFF), "right")
                    - np.searchsorted(k2, nid * KEYM + (nz + STEP_LOW_MAX + ZOFF), "right"))
    else:
        own_high = np.zeros(N, np.int64)
    low_only = (high - own_high) == 0

    # 4. links: per cell, its floors lowest first (the terrain floor is always the lowest)
    order_n = np.lexsort((nz, ncell))
    per_cell = np.bincount(ncell, minlength=NC)
    K = int(per_cell.max()) if N else 1
    first = np.zeros(NC, np.int64)
    first[1:] = np.cumsum(per_cell)[:-1]
    slot = np.zeros(N, np.int64)
    slot[order_n] = np.arange(N) - first[ncell[order_n]]
    table = np.full((NC, K), -1, np.int32)
    table[ncell, slot] = np.arange(N)

    # 3b. a floor blocked only by a low step, with the next tread beside or above it: walkable.
    # A terrain floor only below a level tread (the foot of a flight: Muris' lower stairs): terrain
    # under a thin skin of sloped mesh (a snow drift) must stay shut.
    cand = ~walk & low_only & nup
    if cand.any():
        ci = np.nonzero(cand)[0]
        cx, cy = ncell[ci] % NX, ncell[ci] // NX
        tread = np.zeros(len(ci), bool)
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            nx_, ny_ = cx + dx, cy + dy
            ok = (nx_ >= 0) & (nx_ < NX) & (ny_ >= 0) & (ny_ < NY)
            nbc = np.where(ok, ny_ * NX + nx_, 0)
            for k in range(K):
                nb = np.where(ok, table[nbc, k], -1)
                m = nb >= 0
                nbs = np.maximum(nb, 0)
                dzv = nz[nbs] - nz[ci]
                tread |= (m & nup[nbs] & (dzv >= TREAD_MIN) & (dzv <= STEP_LOW_MAX)
                          & (~nterrain[ci] | (ntread[nbs] & ~nterrain[nbs])))
        walk[ci[tread]] = True
        log("  floors made walkable by the step rule (3b): %d" % int(tread.sum()))

    ea, eb = [], []
    for dy, dx in ((0, 1), (1, 0)):
        a = np.arange(NC).reshape(NY, NX)[: NY - dy, : NX - dx].reshape(-1)
        b = a + dy * NX + dx
        multi = (per_cell[a] > 1) | (per_cell[b] > 1)
        for k1 in range(K):
            for k2 in range(K):
                sel = slice(None) if (k1 == 0 and k2 == 0) else multi
                aa, bb = a[sel], b[sel]
                na, nb = table[aa, k1], table[bb, k2]
                m = (na >= 0) & (nb >= 0)
                na, nb = na[m], nb[m]
                step = np.where((nterrain[na] | nho[na]) & (nterrain[nb] | nho[nb]), STEP_CM, OBJ_STEP_CM)
                dz = np.abs(zr[na] - zr[nb])            # as stored: the server sees these
                # a ramp or a flight steeper than the object step (Muris' great stairs, 78 cm a
                # metre): the higher floor starts within a riser of the lower one's top
                gap = np.where(zr[na] <= zr[nb], nlo[nb] - nhi[na], nlo[na] - nhi[nb])
                ramp = (gap <= OBJ_STEP_CM) & (dz <= STEP_CM) & (dz > OBJ_STEP_CM) & (step < STEP_CM)
                if ramp.any():
                    # ...unless a higher floor in the cell stepped into is within reach: the
                    # client lands on the highest surface under its feet + 135 cm. A pyramid's
                    # skirt runs on under Muris' plaza deck to the ground, and a ramp link down
                    # it opened the hidden ground beneath the whole city
                    ri = np.nonzero(ramp)[0]
                    ra, rb = na[ri], nb[ri]
                    shadow = np.zeros(len(ri), bool)
                    for src, dst, dcell in ((ra, rb, bb[m][ri]), (rb, ra, aa[m][ri])):
                        for k3 in range(K):
                            o = table[dcell, k3]
                            ok3 = o >= 0
                            o = np.maximum(o, 0)
                            shadow |= ok3 & nup[o] & (zr[o] > zr[dst]) & (zr[o] <= zr[src] + STEP_CM)
                    ramp[ri[shadow]] = False
                # the client's terrain slope rule, both ways (a link is walked both ways)
                up_ab = nux[na] * dx + nuy[na] * dy
                up_ba = -(nux[nb] * dx + nuy[nb] * dy)
                slope_ok = (~nsteep[na] | (up_ab < 0)) & (~nsteep[nb] | (up_ba < 0))
                m = walk[na] & walk[nb] & ((dz <= step) | ramp) & slope_ok
                ea.append(na[m])
                eb.append(nb[m])
    ea = np.concatenate(ea) if ea else np.zeros(0, np.int64)
    eb = np.concatenate(eb) if eb else np.zeros(0, np.int64)
    root = _components(N, ea, eb)
    log("  links: %d" % len(ea))

    # 5./6. seeds
    raised = vt > tz + VISUAL_RAISED
    seeds = []
    zon = zonfmt.parse(open(zon_path, "rb").read())
    for e in zon.lump(zonfmt.EVENTS) or []:
        seeds.append(("event", e.x + ORIGIN, e.y + ORIGIN, e.z, e.name.decode("latin-1", "replace")))
    regens = []
    for slot_xy, parsed in chunks.items():
        for lump, kind_name in ((ifo.REGEN, "regen"), (ifo.MOB, "npc")):
            for rec in (r for body in parsed.lumps(lump) for r in body):
                seeds.append((kind_name, rec.pos[0] + ORIGIN, rec.pos[1] + ORIGIN, rec.pos[2],
                              rec.name.decode("latin-1", "replace")))
                if lump == ifo.REGEN:
                    regens.append((rec.pos[0] + ORIGIN, rec.pos[1] + ORIGIN, rec.pos[2], rec.range_m,
                                   len(seeds) - 1))
    seed_node = np.full(len(seeds), -1, np.int64)
    for i, (_, wx, wy, wz, _) in enumerate(seeds):
        seed_node[i] = _snap(wx - x0 * CHUNK_CM, wy - y0 * CHUNK_CM, wz, NX, NY, table, nz, walk, nterrain,
                             vt, raised)
    good = seed_node[seed_node >= 0]
    seed_roots = np.unique(root[good]) if len(good) else np.zeros(0, np.int64)
    reached = np.isin(root, seed_roots) & walk

    # 8. clearance from the 2D reached area
    reached_cell = np.zeros(NC, bool)
    reached_cell[ncell[reached]] = True
    rc2 = reached_cell.reshape(NY, NX)
    clear = (1 + _erode(rc2, 1.5).astype(np.uint8) + _erode(rc2, 2.5).astype(np.uint8)).reshape(-1)
    clear[~reached_cell] = 0

    hazard = reached & (vt[ncell] > nz + HAZARD_CM)

    # component ids 1..n for reached floors
    comp = np.zeros(N, np.int64)
    if reached.any():
        _, inv = np.unique(root[reached], return_inverse=True)
        comp[reached] = inv + 1

    # spans kept: terrain floors, object floors that are reached or face up
    keep = nterrain | reached | nup
    complex_cell = np.zeros(NC, bool)
    complex_cell[ncell[~nterrain & keep]] = True
    complex_cell |= raised & valid
    complex_cell[ncell[hazard]] = True

    nav = lnav.Lnav(cell_cm=CELL, step_cm=int(STEP_CM), body_lo_cm=int(BODY_LO),
                    body_hi_cm=int(BODY_HI), hazard_cm=int(HAZARD_CM), inputs=inputs)
    tile_of = (ncell // NX) // TC * ntx + (ncell % NX) // TC
    korder = np.nonzero(keep)[0]
    korder = korder[np.lexsort((nz[korder], ncell[korder], tile_of[korder]))]
    kt = tile_of[korder]
    flags_n = (walk.astype(np.uint8) * lnav.WALK | reached.astype(np.uint8) * lnav.REACHED
               | nterrain.astype(np.uint8) * lnav.TERRAIN | nup.astype(np.uint8) * lnav.UP
               | hazard.astype(np.uint8) * lnav.HAZARD | nho.astype(np.uint8) * lnav.STAIRS)
    tnode2 = tnode.reshape(NY, NX)
    for ty in range(nty):
        for tx in range(ntx):
            sl = (slice(ty * TC, (ty + 1) * TC), slice(tx * TC, (tx + 1) * TC))
            h = field[ty * 64: ty * 64 + 65, tx * 64: tx * 64 + 65]
            if np.isnan(h).all():
                continue
            tid = ty * ntx + tx
            cm = complex_cell.reshape(NY, NX)[sl]
            tn = tnode2[sl]
            simple = np.zeros((TC, TC), np.uint8)
            okt = tn >= 0
            tw = np.zeros((TC, TC), bool)
            tw[okt] = reached[tn[okt]]
            simple[tw] = clear.reshape(NY, NX)[sl][tw]
            simple[cm] = 0
            tcomp = np.zeros((TC, TC), np.int64)
            tcomp[okt] = comp[tn[okt]]
            sc_comp = tcomp[(simple > 0)]
            main, dense = 0, None
            if len(sc_comp):
                vals, counts = np.unique(sc_comp, return_counts=True)
                main = int(vals[np.argmax(counts)])
                if len(vals) > 1:
                    dense = np.where(simple > 0, tcomp, 0).astype(np.uint16)
            lo, hi = np.searchsorted(kt, tid, "left"), np.searchsorted(kt, tid, "right")
            nodes = korder[lo:hi]
            nodes = nodes[complex_cell[ncell[nodes]]]
            ccells = np.nonzero(cm.reshape(-1))[0]
            g_ccells = ((ccells // TC) + ty * TC) * NX + (ccells % TC) + tx * TC
            nspan = np.bincount(np.searchsorted(g_ccells, ncell[nodes]), minlength=len(ccells))
            crec = np.zeros(len(ccells), lnav.CELL_DTYPE)
            vtc = vt[g_ccells]
            crec["visual_top"] = np.where(raised[g_ccells], np.clip(np.round(vtc), -32767, 32767), lnav.NO_HEIGHT)
            crec["n_spans"] = nspan
            srec = np.zeros(len(nodes), lnav.SPAN_DTYPE)
            srec["z"] = np.clip(np.round(nz[nodes]), -32767, 32767)
            srec["flags"] = flags_n[nodes]
            srec["clearance"] = np.where(reached[nodes], clear[ncell[nodes]], 0)
            srec["component"] = comp[nodes]
            srec["below"] = nbelow[nodes]
            srec["above"] = nabove[nodes]
            hh = np.round(np.nan_to_num(h, nan=0.0)).astype(np.int16)
            nav.tiles[(x0 + tx, y0 + ty)] = lnav.Tile(x0 + tx, y0 + ty, hh, simple, cm, main, dense, crec, srec)

    # regen anchors: each point's resolved floor
    for wx, wy, wz, _range, si in regens:
        n = seed_node[si]
        nav.anchors.append(lnav.Anchor(float(wx), float(wy),
                                       int(np.clip(round(nz[n] if n >= 0 else wz), -32767, 32767)),
                                       1 if n >= 0 and reached[n] else 0))

    b = Bake()
    b.row, b.name, b.folder, b.zdir, b.nav = row, name, folder, zdir, nav
    b.x0, b.y0, b.NX, b.NY = x0, y0, NX, NY
    b.tz, b.valid, b.vt, b.raised = tz, valid, vt, raised
    b.ncell, b.nz, b.nterrain, b.nup, b.walk, b.reached, b.hazard = ncell, nz, nterrain, nup, walk, reached, hazard
    b.keep, b.comp, b.clear, b.complex_cell = keep, comp, clear, complex_cell
    b.seeds, b.seed_node, b.regens = seeds, seed_node, regens
    b.nrec, b.samples = nrec, len(cell)
    b.ea, b.eb = ea, eb
    b.ntread, b.nlo, b.nhi, b.nsteep = ntread, nlo, nhi, nsteep         # diagnostics
    return b


def _snap(lx, ly, wz, NX, NY, table, nz, walk, nterrain, vt, raised):
    """Node a seed stands on (field-local cm), or -1."""
    c, r = int(lx // CELL), int(ly // CELL)
    if not (0 <= c < NX and 0 <= r < NY):
        return -1
    ids = table[r * NX + c]
    ids = ids[ids >= 0]
    cand = ids[walk[ids]] if len(ids) else ids
    top = vt[r * NX + c]
    if len(cand) and raised[r * NX + c]:
        under = cand[(nz[cand] <= top + TERRAIN_MERGE) & (nz[cand] >= top - SEED_SNAP)]
        if len(under):
            return int(under[np.argmax(nz[under])])
    if len(cand):
        best = cand[np.argmin(np.abs(nz[cand] - wz))]
        if abs(nz[best] - wz) <= SEED_SNAP:
            return int(best)
        t = cand[nterrain[cand]]
        if len(t):
            return int(t[0])
    best, bd = -1, None
    for dy in range(-SEED_RADIUS, SEED_RADIUS + 1):
        for dx in range(-SEED_RADIUS, SEED_RADIUS + 1):
            rr, cc = r + dy, c + dx
            if not (0 <= cc < NX and 0 <= rr < NY):
                continue
            ids = table[rr * NX + cc]
            ids = ids[(ids >= 0)]
            ids = ids[walk[ids]] if len(ids) else ids
            if not len(ids):
                continue
            n = ids[np.argmin(np.abs(nz[ids] - wz))]
            # a floor at the seed's own height first: a regen point whose own cell is a pillar
            # must not snap onto the roof 20 m above it (Sikuku Prison, 2026-10-28)
            d = (abs(nz[n] - wz) > SEED_SNAP, dx * dx + dy * dy, abs(nz[n] - wz))
            if bd is None or d < bd:
                best, bd = int(n), d
    return best


# ------------------------------------------------------------------ checks and pictures

def report(b, data_dir):
    """Plain-text numbers for one bake."""
    lines = []
    cells = int(b.valid.sum())
    reached_cell = np.zeros(len(b.valid), bool)
    reached_cell[b.ncell[b.reached]] = True
    per = np.bincount(b.ncell[b.reached], minlength=len(b.valid))
    lines.append("zone %d %s (%s)" % (b.row, b.name, b.folder))
    lines.append("records with colliding parts: %s; surface/wall samples: %d" % (b.nrec, b.samples))
    lines.append("cells on terrain: %d (%.1f km2)" % (cells, cells / 1e6))
    lines.append("cells with a reached floor: %d (%.1f%%)" % (reached_cell.sum(), 100.0 * reached_cell.sum() / max(cells, 1)))
    lines.append("cells with 2+ reached floors (layers): %d" % int((per >= 2).sum()))
    lines.append("reached floors on objects (decks, raised floors): %d" % int((b.reached & ~b.nterrain).sum()))
    lines.append("terrain floors blocked by geometry (body test): %d" % int((b.nterrain & ~b.walk).sum()))
    lines.append("Z-only floors (unreached, facing up): %d" % int((b.keep & ~b.reached & ~b.nterrain).sum()))
    lines.append("hazard floors (client would draw a monster 3 m+ higher): %d" % int(b.hazard.sum()))
    lines.append("complex cells: %d of %d" % (int(b.complex_cell.sum()), cells))
    fails = [s for s, n in zip(b.seeds, b.seed_node) if n < 0]
    unreached = [s for s, n in zip(b.seeds, b.seed_node) if n >= 0 and not b.reached[n]]
    lines.append("seeds: %d, failed to snap: %d" % (len(b.seeds), len(fails)))
    for s in fails[:20]:
        lines.append("   FAILED %s '%s' at (%.0f, %.0f) z %.0f" % (s[0], s[4], s[1] / 100, s[2] / 100, s[3]))
    # spawn spill: share of each regen square with no reached floor
    spill = []
    for wx, wy, wz, rng, si in b.regens:
        lx, ly = wx - b.x0 * CHUNK_CM, wy - b.y0 * CHUNK_CM
        r = max(1, int(rng * 100 // CELL))
        c0, c1 = int(lx // CELL) - r, int(lx // CELL) + r
        r0, r1 = int(ly // CELL) - r, int(ly // CELL) + r
        c0, c1, r0, r1 = max(0, c0), min(b.NX - 1, c1), max(0, r0), min(b.NY - 1, r1)
        if c1 < c0 or r1 < r0:
            continue
        sq = reached_cell.reshape(b.NY, b.NX)[r0:r1 + 1, c0:c1 + 1]
        spill.append(1.0 - sq.mean())
    if spill:
        sp = np.array(spill) * 100
        lines.append("regen squares with no reached floor: median %.1f%%, p90 %.1f%%, max %.1f%% (%d points)"
                     % (np.median(sp), np.percentile(sp, 90), sp.max(), len(sp)))
    hz = np.zeros(len(b.valid), bool)
    hz[b.ncell[b.hazard]] = True
    hzs = []
    for wx, wy, wz, rng, si in b.regens:
        lx, ly = wx - b.x0 * CHUNK_CM, wy - b.y0 * CHUNK_CM
        r = max(1, int(rng * 100 // CELL))
        c0, r0 = max(0, int(lx // CELL) - r), max(0, int(ly // CELL) - r)
        c1, r1 = min(b.NX - 1, int(lx // CELL) + r), min(b.NY - 1, int(ly // CELL) + r)
        if c1 >= c0 and r1 >= r0:
            hzs.append(hz.reshape(b.NY, b.NX)[r0:r1 + 1, c0:c1 + 1].mean())
    if hzs:
        lines.append("regen points whose square touches a hazard cell: %d" % sum(1 for h in hzs if h > 0))
    mov = mov_agreement(b)
    if mov is not None:
        lines.append("painted MOV cells (rows flipped) the bake also leaves unreached or blocked: %.1f%% of %d"
                     % (100 * mov[0], mov[1]))
    size = len(lnav.build(b.nav))
    lines.append("lnav: %d tiles, %d anchors, %.2f MB on disk" % (len(b.nav.tiles), len(b.nav.anchors), size / 1e6))
    if unreached:
        lines.append("seeds on a floor nobody else links to (their own island): %d" % len(unreached))
    return "\n".join(lines)


def mov_agreement(b):
    """Share of painted-blocked MOV cells (read north-first) with no reached floor in most of their 5 x 5 cells."""
    reached_cell = np.zeros(len(b.valid), bool)
    reached_cell[b.ncell[b.reached]] = True
    rc = reached_cell.reshape(b.NY, b.NX)
    agree = total = 0
    for f in os.listdir(b.zdir):
        m = re.match(r"(\d+)_(\d+)\.mov$", f, re.I)
        if not m:
            continue
        sx, sy = int(m.group(1)), 64 - int(m.group(2))
        tx, ty = sx - b.x0, sy - b.y0
        if not (0 <= tx < b.NX // TC and 0 <= ty < b.NY // TC):
            continue
        mv = chunk.parse_mov(open(os.path.join(b.zdir, f), "rb").read())
        cells = mv.cells[::-1]                            # row 0 = south
        for mr, mc in zip(*np.nonzero(cells)):
            r0, c0 = ty * TC + mr * 5, tx * TC + mc * 5
            block = rc[r0:r0 + 5, c0:c0 + 5]
            total += 1
            agree += block.mean() < 0.5
    return (agree / total, total) if total else None


def preview(b, path):
    """1 px = 1 m, north up. Green: reached ground (darker = lower). Blue: reached floor on an
    object. Cyan: 2+ reached floors (deck over ground). Orange: hazard (roof). Red: ground
    blocked by geometry. Grey: walkable but unreached. Yellow: regen points; white: other seeds;
    magenta: seeds that failed to snap."""
    from PIL import Image
    NY, NX = b.NY, b.NX
    img = np.zeros((NY * NX, 3), np.uint8)
    tz = np.nan_to_num(b.tz, nan=0.0)
    lo, hi = np.percentile(tz[b.valid], [2, 98]) if b.valid.any() else (0, 1)
    shade = np.clip((tz - lo) / max(hi - lo, 1.0), 0, 1)
    per = np.bincount(b.ncell[b.reached], minlength=NY * NX)
    obj_reached = np.zeros(NY * NX, bool)
    obj_reached[b.ncell[b.reached & ~b.nterrain]] = True
    t_walk = np.zeros(NY * NX, bool)
    t_walk[b.ncell[b.nterrain & b.walk]] = True
    hz = np.zeros(NY * NX, bool)
    hz[b.ncell[b.hazard]] = True
    base = (40 + 60 * shade).astype(np.uint8)
    img[b.valid] = np.stack([base, base, base], 1)[b.valid]                       # unreached
    blocked = b.valid & ~t_walk & (per == 0)
    img[blocked] = np.array([150, 30, 30], np.uint8)
    g = (70 + 150 * shade).astype(np.uint8)
    reached_ground = (per >= 1)
    img[reached_ground] = np.stack([g // 3, g, g // 3], 1)[reached_ground]
    img[obj_reached & (per == 1)] = np.array([60, 110, 255], np.uint8)
    img[per >= 2] = np.array([40, 230, 230], np.uint8)
    img[hz] = np.array([255, 150, 0], np.uint8)
    img = img.reshape(NY, NX, 3)

    def dot(lx, ly, col, rad):
        c, r = int(lx // CELL), int(ly // CELL)
        img[max(0, r - rad):min(NY, r + rad + 1), max(0, c - rad):min(NX, c + rad + 1)] = col

    for (kind, wx, wy, wz, _), n in zip(b.seeds, b.seed_node):
        lx, ly = wx - b.x0 * CHUNK_CM, wy - b.y0 * CHUNK_CM
        if n < 0:
            dot(lx, ly, (255, 0, 255), 2)
        else:
            dot(lx, ly, (255, 230, 0) if kind == "regen" else (255, 255, 255), 1)
    Image.fromarray(img[::-1]).save(path)
