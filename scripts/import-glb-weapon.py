#!/usr/bin/env python3
"""Turn a glTF binary (.glb) weapon -- Meshy, Blender, anything -- into a ROSE weapon.

WHY THIS EXISTS
---------------
The game reads only its own formats: a `.ZMS` mesh, a `.DDS` texture, and the
weapon's row in `LIST_WEAPON.STB` / object in `LIST_WEAPON.ZSC`. Nothing in the
pipeline ever read a generic 3D file (doc/custom-equipment-asset-feasibility.md,
2026-09-05), so an AI-generated or hand-modelled weapon had no way in. glb is the
intermediate we chose: one self-contained file with triangulated geometry,
normals, UVs and the base-colour texture embedded, and a small enough spec that
this script needs only numpy and Pillow.

`import-item.py` stays the registration authority: this script builds an
in-memory "source table" holding exactly one object and hands it to that tool's
`zsc_build_append` / `stb_append_row` / `stl_append`, so the ZSC remap, the
STB/ZSC/STL index invariants and the 11-bit id guard are the same code that
every other import went through. Stats are cloned from one of OUR rows
(`--template-row`), never read from the model file, for the same reason
`--art-only` exists: ability ids in the STB are unchecked array indices on both
sides.

CONVENTIONS (measured on the stock staffs, 2026-10-11)
-----------------------------------------------------
* ZMS0008, vertex format 0x86 (position | normal | uv0), no bones, no material
  ids, no strip, pool 0 (MST41.ZMS, STAFF_220.ZMS, snake_rod_1214_cr.zms).
* Units are metres in the file; the engine multiplies v7/v8 positions by 100.
* The shaft runs along +Z, the head at the top; the origin is the right-hand
  grip. Stock staffs are 1.95-2.18 m long with the grip 22-31% up from the
  foot (Vengeance Staff: z -0.47 .. 1.62). The wide axis of a flat head is X,
  the thin one Y. The ZSC part transform is NOT applied to character parts
  (CCharPART::Load skips the transform tags -- the Vengeance Staff ships a zero
  quaternion and draws fine), so placement is baked into the geometry here.
* Triangle winding: counter-clockwise seen from outside, i.e.
  cross(b - a, c - a) . normal > 0, on every stock mesh checked -- the same as
  glTF, so a proper rotation (det +1) keeps it and nothing is flipped.
* UV origin is top-left in both glTF and D3D: no V flip.
* Textures are DXT5 with a full mip chain, 128x256 to 512x512; material flags
  alpha 0, alpha test 1 (ref 128), z-write 1, z-test 1, blend 0.

glTF is Y-up, right-handed. The default mapping is (x, y, z) -> (x, -z, y):
Y-up becomes Z-up, the model's front (-Z in glTF) faces +Y. The staff is then
yawed so its wider horizontal extent lies along X (`--no-auto-face` to skip),
scaled to the template mesh's length and shifted so the grip sits at the
template's grip fraction (`--length` / `--grip` override).

DECIMATION (`--max-triangles N`, off by default)
------------------------------------------------
ZMS counts are 16-bit and the engine asserts faces < 100000, but the budget is
artistic: stock weapons are 100-2,500 triangles, Meshy's "remesh" export ~10k.
`--max-triangles` runs MeshLab's texture-aware quadric edge collapse (pymeshlab,
`pip install pymeshlab`; it is imported only when the option is used). Two
things make it work on a glTF: the file splits every vertex along a UV seam, so
positions are **welded first** (else each seam is a boundary and the collapse
stalls -- the scepter stopped at 7,644 of a 3,000 target), and the UVs ride as
**wedge** coordinates through the collapse, then are split back into per-vertex
UVs for the ZMS. Measured on the scepter: 10,140 -> 3,000 triangles is not
distinguishable in a textured render; 2,000 is still clean. A model already
under the cap is left alone. Without the option, anything over the 16-bit limit
is refused.

SPINNING PIECES (`--spin INDEX:SECONDS[:circular]`, repeatable)
----------------------------------------------------------------
A detached shell of the model can rotate about its own vertical axis for ever,
the way the Jrose back items' wings and magic circle move. The mesh is split
into its connected shells (welded by position, sorted by triangle count, index 0
= the largest; `--dry-run` prints the table), the chosen shell leaves the weapon
part and becomes a mesh inside an `.EFT` of its own, attached to the weapon
object by a `POINT_EFFECT_ORIENTED` dummy at the shell's centre. No weapon in
the retail data does this; three Jrose backs do, through the same code path
(`CObjCHAR::New_ModelDummyEFFECT`). What the effect holds, and why:

* the shell's ZMS, re-centred on its own bounding-box centre so the rotation
  is about its axis; the dummy carries the centre (cm) and parent part 1;
* a node motion (`_spin.ZMO`: one position channel at 0 and one rotation
  channel turning about Z, 30 fps, last frame = first) on the entry's
  *animation* slot (`attachMotion(GetANIMATABLE())`, loop count 0 = for ever).
  Retail's `rotate_01.ZMO` (the attack-speed rings) is this shape;
* **no** morph motion (the *mesh ani* slot is empty): the piece is rigid.
  `CEffectLIST::Proc` deletes an effect once `IsFinish()`, which used to ask
  only the **morpher's** state, and a morpher with no motion is never
  "playing" -- the first cut shipped a two-frame no-op morph to stay alive,
  at the price of re-uploading the piece's vertex buffer every frame. Since
  2026-10-12 `CEffect::IsFinish` also counts a running node animation, so the
  entry needs nothing else (every retail animated mesh morphs, which is why
  only the morpher was ever asked). An older client deletes these effects;
* alpha 0, alpha test 1, z-write 1 (retail wings are additive and z-write 0;
  a solid gold ring is not). Effect meshes are drawn **unlit** (`loadMorpher`
  gets no light), so a spinning piece is a shade brighter than the part.

`circular` rescales the shell's XY to its smaller radius first: the scepter's
ring is an oval that would sweep 4 cm into the gold arms at a quarter turn.
A negative SECONDS turns the other way. Spinning pieces do not take the refine
glow (it is set on the part visibles only).

WHAT IT DOES NOT DO
-------------------
Multiple textures are not atlased: every primitive must share one base-colour
image. Normal, metallic and roughness maps are ignored -- the engine draws
diffuse only. Fused geometry cannot be split: the scepter's arms are welded
into the crystal's surface, so only its detached ring and top gem can move.

USAGE
-----
    python scripts/import-glb-weapon.py model.glb --name "Celestial Frost Scepter" \
        --template-row 322 --icon icon.png [--desc "..."] [--texture-size 512] \
        [--length 2.1] [--grip 0.22] [--dry-run]

Backups of every table touched go to build/glb-weapons/<id>/ (never beside the
data: pack.ps1 refuses a .bak under data/). Undo = scripts/remove-trailing-items.py
plus deleting data/3DDATA/WEAPON/CUSTOM/<slug>/. Restart the servers (they cache
the STB) and re-bake the VFS afterwards; the client reads the .vfs, not data/.
"""
import argparse
import importlib.util
import io
import json
import math
import os
import re
import shutil
import struct
import sys
import types

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OURS = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
from rosefmt import zms as _zms  # noqa: E402
from rosefmt.binio import FormatError  # noqa: E402

STB_REL = r"3DDATA\STB\LIST_WEAPON.STB"
ZSC_REL = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
STL_REL = r"3DDATA\STB\LIST_WEAPON_S.STL"
KEY_PREFIX = "LWEA"
CUSTOM_DIR = r"3DDATA\WEAPON\CUSTOM"
BACKUP_DIR = os.path.join(ROOT, "build", "glb-weapons")

VF_POSITION, VF_NORMAL, VF_UV0 = 1 << 1, 1 << 2, 1 << 7
MAX_INDEX = 32767          # 16-bit counts; some tools read them signed


def load_module(fname, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ glTF

COMP = {5120: "<i1", 5121: "<u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Glb:
    def __init__(self, path):
        d = open(path, "rb").read()
        magic, version, length = struct.unpack_from("<4sII", d, 0)
        if magic != b"glTF" or version != 2:
            sys.exit("%s: not a glTF 2.0 binary" % path)
        off, self.json, self.bin = 12, None, b""
        while off < min(length, len(d)):
            clen, ctype = struct.unpack_from("<I4s", d, off)
            off += 8
            if ctype == b"JSON":
                self.json = json.loads(d[off:off + clen])
            elif ctype == b"BIN\0":
                self.bin = d[off:off + clen]
            off += clen
        if self.json is None:
            sys.exit("%s: no JSON chunk" % path)
        if any("uri" in b for b in self.json.get("buffers", [])):
            sys.exit("%s: external buffers are not supported; export as a single .glb" % path)

    def view(self, i):
        v = self.json["bufferViews"][i]
        s = v.get("byteOffset", 0)
        return self.bin[s:s + v["byteLength"]], v.get("byteStride")

    def accessor(self, i):
        a = self.json["accessors"][i]
        if "sparse" in a or "bufferView" not in a:
            sys.exit("sparse / empty accessors are not supported")
        data, stride = self.view(a["bufferView"])
        dt, n = COMP[a["componentType"]], NCOMP[a["type"]]
        size = np.dtype(dt).itemsize * n
        s = a.get("byteOffset", 0)
        if stride and stride != size:
            rows = np.frombuffer(data, "u1")[s:s + stride * (a["count"] - 1) + size]
            out = np.lib.stride_tricks.as_strided(rows, (a["count"], size), (stride, 1)).copy()
            arr = out.view(dt).reshape(a["count"], n)
        else:
            arr = np.frombuffer(data, dt, a["count"] * n, s).reshape(a["count"], n)
        if a.get("normalized") and dt != "<f4":
            arr = arr.astype(np.float64) / np.iinfo(np.dtype(dt)).max
        return arr

    def image(self, i):
        im = self.json["images"][i]
        if "bufferView" not in im:
            sys.exit("image %d is external (uri); export with embedded textures" % i)
        data, _ = self.view(im["bufferView"])
        return Image.open(io.BytesIO(data))


def node_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T   # column-major
    t = np.array(node.get("translation", [0, 0, 0]), dtype=np.float64)
    q = np.array(node.get("rotation", [0, 0, 0, 1]), dtype=np.float64)
    s = np.array(node.get("scale", [1, 1, 1]), dtype=np.float64)
    x, y, z, w = q / (np.linalg.norm(q) or 1.0)
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R * s[None, :]
    M[:3, 3] = t
    return M


def gather(glb):
    """Merge every triangle primitive of the default scene into one mesh in
    glTF world space: (positions, normals, uvs, faces, base-colour image)."""
    js = glb.json
    scene = js["scenes"][js.get("scene", 0)]
    P, N, UV, F, images = [], [], [], [], {}
    base = 0

    def visit(ni, parent):
        nonlocal base
        node = js["nodes"][ni]
        M = parent @ node_matrix(node)
        if "mesh" in node:
            for prim in js["meshes"][node["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4:
                    sys.exit("primitive mode %d: only triangle lists are supported" % prim["mode"])
                att = prim["attributes"]
                pos = glb.accessor(att["POSITION"]).astype(np.float64)
                if "NORMAL" not in att or "TEXCOORD_0" not in att:
                    sys.exit("a primitive lacks NORMAL or TEXCOORD_0; re-export with both")
                nrm = glb.accessor(att["NORMAL"]).astype(np.float64)
                uv = glb.accessor(att["TEXCOORD_0"]).astype(np.float64)
                if "indices" in prim:
                    idx = glb.accessor(prim["indices"]).reshape(-1).astype(np.int64)
                else:
                    idx = np.arange(len(pos))
                faces = idx.reshape(-1, 3)
                R = M[:3, :3]
                pos = pos @ R.T + M[:3, 3]
                nrm = nrm @ np.linalg.inv(R).T
                if np.linalg.det(R) < 0:
                    faces = faces[:, [0, 2, 1]]
                mat = js["materials"][prim["material"]] if "material" in prim else {}
                tex = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture")
                if tex is None:
                    sys.exit("material %r has no baseColorTexture" % mat.get("name"))
                src = js["textures"][tex["index"]]["source"]
                images.setdefault(src, glb.image(src))
                if len(images) > 1:
                    sys.exit("primitives use more than one base-colour texture; the engine wants "
                             "one texture per part -- bake them to a single atlas first")
                P.append(pos)
                N.append(nrm)
                UV.append(uv)
                F.append(faces + base)
                base += len(pos)
        for c in node.get("children", []):
            visit(c, M)

    for ni in scene["nodes"]:
        visit(ni, np.eye(4))
    if not P:
        sys.exit("the scene has no triangle geometry")
    return (np.concatenate(P), np.concatenate(N), np.concatenate(UV),
            np.concatenate(F), next(iter(images.values())))


# ------------------------------------------------------------------ ZMS

def read_zms_v8(path):
    """(positions m, normals, uv0, faces) of a v7/v8 rigid mesh -- enough to
    measure a template and to verify our own output (``rosefmt.zms``)."""
    m = _zms.parse(path)
    if m.version not in (7, 8):
        sys.exit("%s: ZMS%04d is not a v7/v8 mesh" % (path, m.version))
    pos = m.positions.astype(np.float64)
    nrm = m.normals.astype(np.float64) if m.normals is not None else None
    uv = m.uvs[0].astype(np.float64) if m.uvs else None
    return pos, nrm, uv, m.faces.astype(np.int64)


def write_zms_v8(pos, nrm, uv, faces, pool=0):
    """pool 0 = static (a weapon part), 1 = dynamic -- what every retail effect
    mesh uses and what zz_morpher asserts (`mesh->get_dynamic()`), since the
    morpher rewrites the vertex buffer every frame. (``rosefmt.zms.rigid_v8``)"""
    nv, nf = len(pos), len(faces)
    if nv > MAX_INDEX or nf > MAX_INDEX:
        sys.exit("%d vertices / %d triangles: ZMS counts are 16-bit (keep both under %d). "
                 "Use the generator's remesh/retopology export, or decimate first -- stock "
                 "weapons are 100-2,500 triangles." % (nv, nf, MAX_INDEX))
    try:
        return _zms.build(_zms.rigid_v8(pos, nrm, uv, faces, pool))
    except FormatError as e:
        sys.exit("%s. Use the generator's remesh/retopology export, or decimate first -- "
                 "stock weapons are 100-2,500 triangles." % e)


def decimate(pos, nrm, uv, faces, target):
    """Texture-aware quadric edge collapse to `target` triangles.

    Returns (pos, nrm, uv, faces) with vertices split per (position, uv) again,
    normals recomputed on the welded surface so seams stay smooth. See the
    module docstring for why welding and wedge UVs are both required."""
    try:
        import pymeshlab
    except ImportError:
        sys.exit("--max-triangles needs pymeshlab: python -m pip install pymeshlab")
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=np.ascontiguousarray(pos, dtype=np.float64),
                               face_matrix=np.ascontiguousarray(faces, dtype=np.int32),
                               v_tex_coords_matrix=np.ascontiguousarray(uv, dtype=np.float64)), "m")
    # per-vertex -> wedge UVs (this also tags every face as textured, which the
    # collapse filter insists on), then weld the seam-split positions
    ms.compute_texcoord_transfer_vertex_to_wedge()
    ms.meshing_remove_duplicate_vertices()
    welded = ms.current_mesh().vertex_number()
    ms.meshing_decimation_quadric_edge_collapse_with_texture(
        targetfacenum=int(target), qualitythr=0.3, preserveboundary=True,
        optimalplacement=True, planarquadric=True)
    ms.compute_normal_per_vertex()
    cm = ms.current_mesh()
    V, F, W, N = cm.vertex_matrix(), cm.face_matrix(), cm.wedge_tex_coord_matrix(), cm.vertex_normal_matrix()
    corner_v = F.reshape(-1)
    key = np.concatenate([corner_v[:, None].astype(np.float64), np.round(W, 6)], 1)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    vid = uniq[:, 0].astype(int)
    out_n = N[vid]
    out_n /= np.maximum(np.linalg.norm(out_n, axis=1, keepdims=True), 1e-12)
    print("decimated: %d -> %d triangles (%d welded vertices -> %d, %d after the UV split)"
          % (len(faces), len(F), welded, len(V), len(vid)))
    if len(F) > target * 1.05:
        print("WARNING: the collapse stopped short of the target; the mesh has many "
              "boundaries or tiny islands. The result is kept.")
    return V[vid], out_n, uniq[:, 1:3], inv.reshape(-1, 3).astype(np.int64)


def connected_shells(pos, faces):
    """Label each face by the connected shell it belongs to, welding vertices by
    position (a glb splits them on UV seams). Returns labels renumbered so 0 is
    the shell with the most faces."""
    key = np.round(pos, 5)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    wf = inv.reshape(-1)[faces] if inv.ndim > 1 else inv[faces]
    parent = np.arange(len(uniq))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in wf:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[rc] = ra
    roots = np.array([find(i) for i in range(len(uniq))])
    lab = roots[wf[:, 0]]
    ids, counts = np.unique(lab, return_counts=True)
    order = ids[np.argsort(-counts, kind="stable")]
    remap = {old: new for new, old in enumerate(order)}
    return np.array([remap[v] for v in lab])


def submesh(pos, nrm, uv, faces, mask):
    """The faces where mask is true, with vertices re-indexed."""
    f = faces[mask]
    used, inv = np.unique(f.reshape(-1), return_inverse=True)
    return pos[used], nrm[used], uv[used], inv.reshape(-1, 3)


def clip_at_z(pos, nrm, uv, faces, zc):
    """Split a mesh by the plane z = zc. Triangles crossing it are cut exactly,
    with position, normal and UV interpolated, so both sides end on the same
    closed curve and a part turning against the other shows no gap. Returns
    (above, below) as (pos, nrm, uv, faces) tuples, each re-indexed."""
    P, N, U = list(map(tuple, pos)), list(map(tuple, nrm)), list(map(tuple, uv))
    above, below = [], []
    cache = {}

    def cut(i, j):
        key = (min(i, j), max(i, j))
        if key not in cache:
            zi, zj = P[i][2], P[j][2]
            t = (zc - zi) / (zj - zi)
            P.append(tuple(a + (b - a) * t for a, b in zip(P[i], P[j])))
            n = [a + (b - a) * t for a, b in zip(N[i], N[j])]
            ln = math.sqrt(sum(c * c for c in n)) or 1.0
            N.append(tuple(c / ln for c in n))
            U.append(tuple(a + (b - a) * t for a, b in zip(U[i], U[j])))
            cache[key] = len(P) - 1
        return cache[key]

    for tri in faces:
        side = [P[v][2] >= zc for v in tri]
        if all(side):
            above.append(tuple(tri))
            continue
        if not any(side):
            below.append(tuple(tri))
            continue
        # walk the edges, Sutherland-Hodgman style, into two polygons
        up, down = [], []
        for k in range(3):
            i, j = tri[k], tri[(k + 1) % 3]
            (up if side[k] else down).append(i)
            if side[k] != side[(k + 1) % 3]:
                m = cut(i, j)
                up.append(m)
                down.append(m)
        for poly, dest in ((up, above), (down, below)):
            for k in range(1, len(poly) - 1):             # fan, keeps the winding
                dest.append((poly[0], poly[k], poly[k + 1]))
    P, N, U = np.array(P), np.array(N), np.array(U)

    def pack(tris):
        f = np.array(tris, dtype=np.int64).reshape(-1, 3)
        used, inv = np.unique(f.reshape(-1), return_inverse=True)
        return P[used], N[used], U[used], inv.reshape(-1, 3)

    rim = np.array([P[i] for i in cache.values()])
    return pack(above), pack(below), rim


def collar_mesh(centre, radius, height, uv, segments=32):
    """A closed cylinder (side + two caps) around the Z axis through `centre`,
    one flat UV: a band that hides the seam of a --spin-above cut on a shaft
    whose cross-section is not round (a spiral ridge, a square grip)."""
    cx, cy, cz = centre
    z0, z1 = cz - height / 2.0, cz + height / 2.0
    P, N, U, F = [], [], [], []
    ring_lo, ring_hi = [], []
    for k in range(segments):
        a = 2.0 * math.pi * k / segments
        c, s = math.cos(a), math.sin(a)
        for z, ring in ((z0, ring_lo), (z1, ring_hi)):
            ring.append(len(P))
            P.append((cx + radius * c, cy + radius * s, z))
            N.append((c, s, 0.0))
            U.append(uv)
    for k in range(segments):
        a, b = ring_lo[k], ring_lo[(k + 1) % segments]
        c, d = ring_hi[k], ring_hi[(k + 1) % segments]
        F += [(a, b, d), (a, d, c)]                       # CCW seen from outside
    for z, nz, ring in ((z1, 1.0, ring_hi), (z0, -1.0, ring_lo)):
        ctr = len(P)
        P.append((cx, cy, z))
        N.append((0.0, 0.0, nz))
        U.append(uv)
        for k in range(segments):
            a, b = ring[k], ring[(k + 1) % segments]
            F.append((ctr, a, b) if nz > 0 else (ctr, b, a))
    # the side ring vertices carry a sideways normal; the cap fans reuse them,
    # which shades the caps a little off -- invisible on a 2 cm band
    return (np.array(P), np.array(N), np.array(U), np.array(F, dtype=np.int64))


def face_adjacency_components(pos, faces, mask):
    """Connected components (by shared welded vertex) among the faces where
    mask is true; returns a label per face (-1 outside the mask)."""
    key = np.round(pos, 5)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    idx = np.nonzero(mask)[0]
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    owner = {}
    for fi in idx:
        root = find(("f", fi))
        for v in faces[fi]:
            w = inv[v]
            if w in owner:
                parent[find(owner[w])] = root
                root = find(root)
            else:
                owner[w] = ("f", fi)
    labels = np.full(len(faces), -1, dtype=np.int64)
    roots = {}
    for fi in idx:
        r = find(("f", fi))
        labels[fi] = roots.setdefault(r, len(roots))
    return labels


def select_frame(pos, uv, faces, hsv, zc, keep_hues, keep_radius, island_min):
    """Mask of the faces that form a frame around a core: everything whose
    centroid is above zc, except faces whose texel hue is a kept hue (the
    crystal), faces within keep_radius of the vertical axis (the stem, and
    highlights the hue test misses), and small islands either way."""
    th, tw = hsv.shape[:2]
    cuv = uv[faces].mean(1)
    tx = np.clip((cuv[:, 0] % 1.0) * tw, 0, tw - 1).astype(int)
    ty = np.clip((cuv[:, 1] % 1.0) * th, 0, th - 1).astype(int)
    h, s = hsv[ty, tx, 0] / 255.0, hsv[ty, tx, 1] / 255.0
    cz = pos[faces][:, :, 2].mean(1)
    cr = np.hypot(pos[faces][:, :, 0].mean(1), pos[faces][:, :, 1].mean(1))
    kept = np.zeros(len(faces), bool)
    for lo, hi in keep_hues:
        kept |= (h >= lo) & (h <= hi) & (s > 0.15)
    rot = (cz >= zc) & ~kept & (cr >= keep_radius)
    for _ in range(2):                                   # islands: specks of one set inside the other
        lab = face_adjacency_components(pos, faces, rot)
        for L in np.unique(lab[lab >= 0]):
            m = lab == L
            if m.sum() < island_min:
                rot[m] = False
        lab = face_adjacency_components(pos, faces, ~rot & (cz >= zc - 0.05))
        sizes = {L: int((lab == L).sum()) for L in np.unique(lab[lab >= 0])}
        if sizes:
            main = max(sizes, key=sizes.get)
            for L, n in sizes.items():
                if L != main and n < island_min:
                    rot[lab == L] = True
    return rot


def write_zmo(fps, frames):
    """ZMO0002 from [(channel_type, refer_id, values_per_frame[]), ...]: the
    engine's zz_motion::load layout (cstr magic; u32 fps, frames, channels;
    per channel u32 type + u32 refer; then per frame, per channel, floats).
    Positions are in cm (the loader applies ZZ_XFORM_IN); rotations w,x,y,z."""
    n = len(frames[0][2])
    out = [b"ZMO0002\0", struct.pack("<III", fps, n, len(frames))]
    for ctype, refer, _ in frames:
        out.append(struct.pack("<II", ctype, refer))
    for fi in range(n):
        for _, _, vals in frames:
            out.append(struct.pack("<%df" % len(vals[fi]), *vals[fi]))
    return b"".join(out)


CTYPE_POSITION, CTYPE_ROTATION = 1 << 1, 1 << 2


def spin_motion(seconds, fps=30):
    """A node motion turning about +Z once per `seconds` (negative = the other
    way), last frame equal to the first so the loop is seamless."""
    n = max(2, int(round(abs(seconds) * fps))) + 1
    sign = -1.0 if seconds < 0 else 1.0
    pos = [(0.0, 0.0, 0.0)] * n
    rot = []
    for i in range(n):
        a = sign * 2.0 * math.pi * i / (n - 1)
        rot.append((math.cos(a / 2), 0.0, 0.0, math.sin(a / 2)))      # w, x, y, z
    return write_zmo(fps, [(CTYPE_POSITION, 0, pos), (CTYPE_ROTATION, 0, rot)])


def _s(text):
    b = text.encode("ascii")
    return struct.pack("<i", len(b)) + b


def write_eft(mesh_rel, morph_rel, tex_rel, spin_rel, label):
    """An .EFT holding one solid, unlit, endlessly spinning mesh and nothing
    else -- the fields in CEffectDATA::Load's order (src/client/io_effect.cpp)."""
    out = [_s(""),                          # effect name (blank = the file name)
           struct.pack("<i", 0),            # use sound
           _s(""),                          # sound file
           struct.pack("<i", 1),            # sound loop count (retail writes 1)
           struct.pack("<i", 0),            # particles
           struct.pack("<i", 1)]            # mesh animations
    out += [_s(label + ".mrp"), _s(""), struct.pack("<i", 0),
            _s(mesh_rel), _s(morph_rel), _s(tex_rel),
            struct.pack("<8i", 0, 0, 1, 1, 1,      # alpha, two-sided, alpha test, z test, z write
                        5, 6, 1),                  # blend src/dst/op (unused: alpha is off)
            struct.pack("<i", 1), _s(spin_rel),    # use animation file + its path
            struct.pack("<ii", 0, 0),              # loop count (0 = for ever), stb index
            struct.pack("<3f", 0.0, 0.0, 0.0),     # position
            struct.pack("<4f", 0.0, 0.0, 0.0, 0.0),  # yaw/pitch/roll (w unused)
            struct.pack("<3i", 0, 0, 1)]           # delay, morph repeat (0 = for ever), linked
    return b"".join(out)


def read_eft(b):
    """Mirror of CEffectDATA::Load, for verification."""
    q = [0]

    def i32():
        v = struct.unpack_from("<i", b, q[0])[0]
        q[0] += 4
        return v

    def s():
        n = i32()
        v = b[q[0]:q[0] + n].decode("latin-1")
        q[0] += n
        return v

    out = {"name": s(), "use_sound": i32(), "sound": s(), "sound_loop": i32()}
    out["particles"] = i32()
    if out["particles"]:
        raise ValueError("particles are not written by this tool")
    out["meshes"] = []
    for _ in range(i32()):
        m = {"label": s(), "uniq": s(), "stb": i32(), "mesh": s(), "morph": s(), "tex": s()}
        m["flags"] = struct.unpack_from("<8i", b, q[0])
        q[0] += 32
        m["use_ani"] = i32()
        m["ani"] = s()
        m["loop"], m["ani_stb"] = i32(), i32()
        m["pos"] = struct.unpack_from("<3f", b, q[0])
        q[0] += 12
        m["rot"] = struct.unpack_from("<4f", b, q[0])
        q[0] += 16
        m["delay"], m["repeat"], m["link"] = i32(), i32(), i32()
        out["meshes"].append(m)
    if q[0] != len(b):
        raise ValueError("EFT has %d trailing bytes" % (len(b) - q[0]))
    return out


def read_zmo_header(b):
    e = b.index(b"\0")
    fps, n, nc = struct.unpack_from("<III", b, e + 1)
    chans = [struct.unpack_from("<II", b, e + 13 + 8 * i) for i in range(nc)]
    size = sum({CTYPE_POSITION: 12, CTYPE_ROTATION: 16}[t] for t, _ in chans)
    assert len(b) == e + 13 + 8 * nc + n * size, "ZMO size mismatch"
    return b[:e].decode(), fps, n, chans


def winding_agreement(pos, nrm, faces):
    a, b, c = pos[faces[:, 0]], pos[faces[:, 1]], pos[faces[:, 2]]
    fn = np.cross(b - a, c - a)
    vn = nrm[faces[:, 0]] + nrm[faces[:, 1]] + nrm[faces[:, 2]]
    d = np.einsum("ij,ij->i", fn, vn)
    return int((d > 0).sum()), int((d < 0).sum())


# ------------------------------------------------------------------ placement

UP_MAPS = {
    # glTF axis -> ROSE axis, as a rotation matrix applied to column vectors
    "y": np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64),   # Y-up, front -Z -> +Y
    "z": np.eye(3),
    "-y": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64),
}


def yaw(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def place(pos, nrm, up, length, grip, auto_face, extra_yaw):
    R = UP_MAPS[up]
    if extra_yaw:
        R = yaw(extra_yaw) @ R
    p = pos @ R.T
    if auto_face:
        ext = p.max(0) - p.min(0)
        if ext[1] > ext[0]:
            R = yaw(90.0) @ R
            p = pos @ R.T
    n = nrm @ R.T
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    zmin, zmax = p[:, 2].min(), p[:, 2].max()
    s = length / (zmax - zmin)
    p = p * s
    p[:, 2] += -grip * length - p[:, 2].min()
    # centre the shaft on the origin in X/Y: a glb author rarely puts the
    # pivot on the shaft axis, and a stock staff's cross-section straddles 0
    p[:, 0] -= (p[:, 0].max() + p[:, 0].min()) / 2
    p[:, 1] -= (p[:, 1].max() + p[:, 1].min()) / 2
    return p, n, R, s


# ------------------------------------------------------------------ main

def slugify(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return s[:24] or "custom"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glb")
    ap.add_argument("--name", required=True, help="item name (STL English block + STB col 0)")
    ap.add_argument("--desc", default="", help="item description")
    ap.add_argument("--template-row", type=int, required=True,
                    help="OUR LIST_WEAPON.STB row to clone every stat column from; its model "
                         "also sets the default length/grip and the material flags")
    ap.add_argument("--slug", help="folder/file name under 3DDATA/WEAPON/CUSTOM (default: from --name)")
    ap.add_argument("--icon", help="PNG for the inventory icon (any size; added to ITEM1.TSI). "
                                   "Without it the template's icon is reused")
    ap.add_argument("--icon-index", type=int, help="reuse an icon already in ITEM1.TSI (a re-import)")
    ap.add_argument("--gem-point", metavar="X,Y,Z",
                    help="where a socketed gem's glow sits, metres in placed coordinates (default: "
                         "on the axis at 70%% of the height, where retail staffs and swords put it). "
                         "Every weapon gets the three retail anchors: trail start at the tip, trail "
                         "end near the grip, gem point -- LIST_WEAPON col 43 names index 2 and the "
                         "client drops the gem effect on a weapon without it")
    ap.add_argument("--max-triangles", type=int,
                    help="decimate to at most this many triangles (texture-aware, needs "
                         "pymeshlab); stock weapons are 100-2,500, 3000 is invisible on a "
                         "Meshy remesh. Default: no decimation")
    ap.add_argument("--spin", action="append", default=[], metavar="INDEX:SECONDS[:circular]",
                    help="make detached shell INDEX (see the dry-run table) an effect mesh "
                         "turning about its own vertical axis once per SECONDS (negative = "
                         "the other way); 'circular' first rounds its outline to its smaller "
                         "radius. Repeatable")
    ap.add_argument("--spin-above", metavar="Z:SECONDS",
                    help="cut whatever is left of the model at height Z metres (placed "
                         "coordinates, grip = 0) and spin everything above it once per "
                         "SECONDS about the cut's centre; triangles are split exactly at the "
                         "plane. Pick a Z on a plain round stretch of the shaft")
    ap.add_argument("--spin-frame", metavar="Z:SECONDS",
                    help="spin the *frame* above height Z around a still core: whole faces are "
                         "selected (no plane cut) -- everything above Z except faces of a "
                         "--keep-hue colour, faces within --keep-radius of the axis, and specks "
                         "smaller than --island-min faces. Add a --sleeve over the fused joint")
    ap.add_argument("--keep-hue", action="append", default=[], metavar="LO-HI",
                    help="with --spin-frame: texel hue range (0-1) that stays still, e.g. the "
                         "crystal's cyan 0.45-0.60. Repeatable")
    ap.add_argument("--keep-radius", type=float, default=0.05, metavar="M",
                    help="with --spin-frame: faces closer than this to the axis stay still (default 0.05)")
    ap.add_argument("--island-min", type=int, default=50,
                    help="with --spin-frame: a connected patch smaller than this joins the other side")
    ap.add_argument("--sleeve", metavar="R:Z0:Z1",
                    help="with --spin-frame: a closed cylinder of radius R from Z0 to Z1 (metres) "
                         "added to the still part, in the frame's own colour, hiding the fused "
                         "joint the selection tears open")
    ap.add_argument("--sleeve-uv", metavar="U,V", help="texel for the sleeve (default: nearest frame face)")
    ap.add_argument("--collar", type=float, default=0.0, metavar="CM",
                    help="with --spin-above: add a closed band this tall around the cut, 5 mm "
                         "wider than the rim, textured with the shaft's texel just below the "
                         "cut, so a non-round seam stays hidden while the head turns")
    ap.add_argument("--texture-size", type=int, default=512,
                    help="square DDS size; stock weapons use 128x256..512x512 (default 512)")
    ap.add_argument("--up", choices=sorted(UP_MAPS), default="y", help="the model's up axis (glTF: y)")
    ap.add_argument("--yaw", type=float, default=0.0, help="extra rotation about the shaft, degrees")
    ap.add_argument("--no-auto-face", action="store_true",
                    help="do not turn the wider horizontal extent onto X")
    ap.add_argument("--length", type=float, help="total length in metres (default: the template mesh's)")
    ap.add_argument("--grip", type=float,
                    help="grip height as a fraction of the length from the foot (default: the template's)")
    ap.add_argument("--dry-run", action="store_true", help="measure and report, write nothing")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(OURS, "3DDATA")):
        sys.exit("run from the repo root (data/3DDATA not found)")
    ii = load_module("import-item.py", "import_item")

    # ---- our tables and the template
    stb_path = os.path.join(OURS, STB_REL)
    zsc_path = os.path.join(OURS, ZSC_REL)
    stl_path = os.path.join(OURS, STL_REL)
    _, _, orows, ocols, odata = ii.stb_read(stb_path)
    ours = ii.Zsc(zsc_path)
    if len(ours.objects) != orows - 1:
        sys.exit("LIST_WEAPON.ZSC holds %d objects but the STB has %d rows -- fix that first"
                 % (len(ours.objects), orows - 1))
    if not 0 <= args.template_row < len(odata) or not odata[args.template_row][0].strip():
        sys.exit("--template-row %d is not an occupied row" % args.template_row)
    tmpl = odata[args.template_row]
    tcyl, tparts, _, _ = ours.objects[args.template_row]
    if not tparts:
        sys.exit("template row %d has no model to take conventions from" % args.template_row)
    tmesh_idx, tmat_idx, tprops = tparts[0]
    tmesh_rel = ours.meshes[tmesh_idx].decode("latin-1").replace("\\", "/")
    tpos, _, _, _ = read_zms_v8(os.path.join(OURS, tmesh_rel))
    for mi, _, _ in tparts[1:]:                     # a multi-part template: whole-object extent
        extra, _, _, _ = read_zms_v8(os.path.join(OURS, ours.meshes[mi].decode("latin-1").replace("\\", "/")))
        tpos = np.concatenate([tpos, extra])
    t_len = float(tpos[:, 2].max() - tpos[:, 2].min())
    t_grip = float(-tpos[:, 2].min() / t_len)
    length = args.length if args.length is not None else t_len
    grip = args.grip if args.grip is not None else t_grip
    tmat_path, tmat_flags = ours.materials[tmat_idx]
    print("template: row %d %r, mesh %s, %.3f m long, grip %.0f%% up, material flags %s"
          % (args.template_row, tmpl[0].decode("euc-kr", "replace"), tmesh_rel, t_len,
             t_grip * 100, struct.unpack("<9h", tmat_flags[:18])))

    new_id = orows - 1
    if new_id > 2047:
        sys.exit("new ID %d exceeds the 11-bit item number limit" % new_id)
    if new_id > 999:
        print("WARNING: id %d is above 999, so this item can never be dropped, granted by a "
              "quest or used as a recipe input (fine for a shop/GM item)" % new_id)
    slug = args.slug or slugify(args.name)
    rel_dir = os.path.join(CUSTOM_DIR, slug)
    mesh_rel = os.path.join(rel_dir, slug + ".ZMS")
    tex_rel = os.path.join(rel_dir, slug + ".DDS")
    for rel in (mesh_rel, tex_rel):
        if os.path.exists(os.path.join(OURS, rel.replace("\\", os.sep))):
            sys.exit("%s already exists; pick another --slug" % rel)
    if any(ii.norm(m) == ii.norm(mesh_rel.encode()) for m in ours.meshes):
        sys.exit("the ZSC already lists %s" % mesh_rel)

    # ---- the model
    glb = Glb(args.glb)
    P, N, UV, F, image = gather(glb)
    print("glb: %d vertices, %d triangles, %d primitive(s) merged, base colour %dx%d %s"
          % (len(P), len(F), len(glb.json["meshes"]), image.size[0], image.size[1], image.mode))
    agree, disagree = winding_agreement(P, N, F)
    if disagree > agree:
        print("note: winding is clockwise-out in the source; flipping")
        F = F[:, [0, 2, 1]]
    if args.max_triangles is not None:
        if args.max_triangles < 100:
            sys.exit("--max-triangles %d is absurdly low" % args.max_triangles)
        if len(F) > args.max_triangles:
            P, N, UV, F = decimate(P, N, UV, F, args.max_triangles)
            a2, d2 = winding_agreement(P, N, F)
            if d2 > a2:                       # never seen; cheap to guard
                F = F[:, [0, 2, 1]]
        else:
            print("decimation: %d triangles already under %d, left alone" % (len(F), args.max_triangles))
    ext = P.max(0) - P.min(0)
    print("     extent in source axes: %.3f x %.3f x %.3f" % tuple(ext))
    pos, nrm, R, scale = place(P, N, args.up, length, grip, not args.no_auto_face, args.yaw)
    lo, hi = pos.min(0), pos.max(0)
    print("placed: scale x%.3f, x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f m (grip at z=0)"
          % (scale, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    if (UV.min() < -0.01) or (UV.max() > 1.01):
        print("note: UVs leave 0..1 (%.2f..%.2f); the texture wraps" % (UV.min(), UV.max()))

    # ---- detached shells, and the ones that spin
    spins = []
    for spec in args.spin:
        bits = spec.split(":")
        try:
            idx, secs = int(bits[0]), float(bits[1])
            circular = len(bits) > 2 and bits[2] == "circular"
            if len(bits) > 3 or (len(bits) == 3 and not circular) or secs == 0:
                raise ValueError
        except (ValueError, IndexError):
            sys.exit("--spin wants INDEX:SECONDS[:circular], got %r" % spec)
        spins.append((idx, secs, circular))
    shells = connected_shells(pos, F)
    n_shells = int(shells.max()) + 1
    if spins or args.dry_run:
        print("detached shells (index: triangles, extent in metres):")
        for s_i in range(min(n_shells, 12)):
            sp = pos[F[shells == s_i]].reshape(-1, 3)
            slo, shi = sp.min(0), sp.max(0)
            print("  %2d: %5d  x %6.3f..%6.3f  y %6.3f..%6.3f  z %6.3f..%6.3f"
                  % (s_i, int((shells == s_i).sum()), slo[0], shi[0], slo[1], shi[1], slo[2], shi[2]))
        if n_shells > 12:
            print("  ... %d more" % (n_shells - 12))
    spin_pieces = []                         # (label, pos, nrm, uv, faces, centre_m, seconds)
    body_mask = np.ones(len(F), bool)
    for k, (idx, secs, circular) in enumerate(spins):
        if not 0 <= idx < n_shells or idx == 0:
            sys.exit("--spin shell %d: must be 1..%d (0 is the body)" % (idx, n_shells - 1))
        mask = shells == idx
        if not mask.any() or not body_mask[mask].all():
            sys.exit("--spin shell %d is already taken" % idx)
        body_mask &= ~mask
        sp, sn, su, sf = submesh(pos, nrm, UV, F, mask)
        slo, shi = sp.min(0), sp.max(0)
        centre = (slo + shi) / 2.0
        sp = sp - centre
        if circular:
            rx, ry = np.abs(sp[:, 0]).max(), np.abs(sp[:, 1]).max()
            r = min(rx, ry)
            sp[:, 0] *= r / rx
            sp[:, 1] *= r / ry
            sn[:, 0] *= r / rx                   # a non-uniform scale on the normals,
            sn[:, 1] *= r / ry                   # renormalised: close enough for a ring
            sn /= np.maximum(np.linalg.norm(sn, axis=1, keepdims=True), 1e-12)
            print("  shell %d made circular: radius %.3f x %.3f -> %.3f m" % (idx, rx, ry, r))
        label = "%s_spin%d" % (slug, k)
        spin_pieces.append((label, sp, sn, su, sf, centre, secs))
        print("  shell %d spins once per %.1f s about (%.3f, %.3f, %.3f) m, %d triangles -> %s"
              % (idx, abs(secs), centre[0], centre[1], centre[2], len(sf), label))
    if spin_pieces:
        pos, nrm, UV, F = submesh(pos, nrm, UV, F, body_mask)
    if args.spin_frame:
        try:
            zc, secs = (float(x) for x in args.spin_frame.split(":"))
            hues = [tuple(float(x) for x in h.split("-")) for h in args.keep_hue]
            if secs == 0 or any(len(h) != 2 for h in hues):
                raise ValueError
        except ValueError:
            sys.exit("--spin-frame wants Z:SECONDS and --keep-hue LO-HI")
        hsv = np.asarray(image.convert("RGB").resize((512, 512), Image.LANCZOS).convert("HSV"))
        rot = select_frame(pos, UV, F, hsv, zc, hues, args.keep_radius, args.island_min)
        if rot.sum() < args.island_min or (~rot).sum() == 0:
            sys.exit("--spin-frame selected %d faces; check Z / --keep-hue" % int(rot.sum()))
        fp, fn_, fu, ff = submesh(pos, nrm, UV, F, rot)
        pos, nrm, UV, F = submesh(pos, nrm, UV, F, ~rot)
        # the axis: the still core's own centre just above the cut (the stem)
        cz = pos[F][:, :, 2].mean(1)
        core = (cz >= zc) & (cz <= zc + 0.10)
        axis_xy = pos[F[core]].reshape(-1, 3)[:, :2].mean(0) if core.any() else fp[:, :2].mean(0)
        centre = np.array([axis_xy[0], axis_xy[1], (fp[:, 2].min() + fp[:, 2].max()) / 2.0])
        print("  frame: %d faces turn once per %.1f s about (%.3f, %.3f), z %.3f..%.3f; %d faces stay "
              "(core %d above the cut)" % (len(ff), abs(secs), centre[0], centre[1],
                                           fp[:, 2].min(), fp[:, 2].max(), len(F), int(core.sum())))
        label = "%s_spin%d" % (slug, len(spin_pieces))
        spin_pieces.append((label, fp - centre, fn_, fu, ff, centre, secs))
        if args.sleeve:
            try:
                sr, sz0, sz1 = (float(x) for x in args.sleeve.split(":"))
            except ValueError:
                sys.exit("--sleeve wants R:Z0:Z1")
            if args.sleeve_uv:
                texel = tuple(float(x) for x in args.sleeve_uv.split(","))
            else:
                # the frame face nearest the sleeve's wall at mid-height: on a
                # plate that is where the frame's own material is
                fc = fp[ff].mean(1)                              # frame-local (centre subtracted)
                zmid_local = (sz0 + sz1) / 2.0 - centre[2]
                dist = np.abs(np.hypot(fc[:, 0], fc[:, 1]) - sr) + np.abs(fc[:, 2] - zmid_local)
                texel = tuple(fu[ff[int(np.argmin(dist))]].mean(0))
            tx, ty = int(texel[0] % 1.0 * 511), int(texel[1] % 1.0 * 511)
            rgb = np.asarray(image.convert("RGB").resize((512, 512), Image.LANCZOS))[ty, tx]
            cp, cn, cu, cf = collar_mesh((centre[0], centre[1], (sz0 + sz1) / 2.0), sr, sz1 - sz0, texel)
            F = np.concatenate([F, cf + len(pos)])
            pos, nrm, UV = np.concatenate([pos, cp]), np.concatenate([nrm, cn]), np.concatenate([UV, cu])
            print("  sleeve: radius %.3f, z %.3f..%.3f, texel uv (%.3f, %.3f) = rgb %s"
                  % (sr, sz0, sz1, texel[0], texel[1], tuple(int(v) for v in rgb)))
    elif args.sleeve or args.keep_hue:
        sys.exit("--sleeve / --keep-hue need --spin-frame")
    if args.spin_above:
        try:
            zc, secs = (float(x) for x in args.spin_above.split(":"))
            if secs == 0:
                raise ValueError
        except ValueError:
            sys.exit("--spin-above wants Z:SECONDS, got %r" % args.spin_above)
        if not pos[:, 2].min() < zc < pos[:, 2].max():
            sys.exit("--spin-above: z=%.3f is outside the model (%.3f..%.3f)"
                     % (zc, pos[:, 2].min(), pos[:, 2].max()))
        (hp, hn, hu, hf), (pos, nrm, UV, F), rim = clip_at_z(pos, nrm, UV, F, zc)
        if len(hf) == 0 or len(F) == 0:
            sys.exit("--spin-above: the cut leaves one side empty")
        centre = np.array([rim[:, 0].mean(), rim[:, 1].mean(), zc])
        rr = np.hypot(rim[:, 0] - centre[0], rim[:, 1] - centre[1])
        print("  cut at z=%.3f: rim of %d points, radius %.3f..%.3f m about (%.3f, %.3f); "
              "%d triangles above spin once per %.1f s, %d stay"
              % (zc, len(rim), rr.min(), rr.max(), centre[0], centre[1], len(hf), abs(secs), len(F)))
        if rr.max() - rr.min() > 0.02:
            print("  WARNING: the rim is not round (%.1f cm spread): the seam will show while "
                  "turning. Cut on a plain stretch of the shaft." % ((rr.max() - rr.min()) * 100))
        label = "%s_spin%d" % (slug, len(spin_pieces))
        spin_pieces.append((label, hp - centre, hn, hu, hf, centre, secs))
        if args.collar > 0:
            # texel of the shaft just under the cut, so the band takes its colour
            near = np.argmax(pos[:, 2])
            cp, cn, cu, cf = collar_mesh(centre, rr.max() + 0.005, args.collar / 100.0, tuple(UV[near]))
            F = np.concatenate([F, cf + len(pos)])
            pos, nrm, UV = np.concatenate([pos, cp]), np.concatenate([nrm, cn]), np.concatenate([UV, cu])
            print("  collar: %.1f cm tall, radius %.3f m, %d triangles, texel uv (%.3f, %.3f)"
                  % (args.collar, rr.max() + 0.005, len(cf), cu[0][0], cu[0][1]))
        elif rr.max() - rr.min() > 0.01:
            print("  hint: --collar 2 would hide that seam")
    elif args.collar > 0:
        sys.exit("--collar needs --spin-above")
    lo, hi = pos.min(0), pos.max(0)
    zms = write_zms_v8(pos, nrm, UV, F)

    spin_files = []                          # (rel path, bytes)
    # The three anchors every retail weapon carries (measured on swords and
    # staffs): 0 = trail start at the tip, 1 = trail end about a quarter up the
    # weapon, 2 = the socketed gem's glow. LoadTRAIL wants at least three points
    # and reads 0/1; the gem effect reads WEAPON_GEMMING_POSITION (col 43) = 2.
    top = float(max(hi[2], max([(sp[:, 2].max() + c[2]) for _, sp, _, _, _, c, _ in spin_pieces] or [hi[2]])))
    if args.gem_point:
        try:
            gem = tuple(float(x) for x in args.gem_point.split(","))
            assert len(gem) == 3
        except (ValueError, AssertionError):
            sys.exit("--gem-point wants X,Y,Z in metres")
    else:
        gem = (0.0, 0.0, 0.70 * top)

    def anchor(p):
        return (None, 0, struct.pack("<BB3f", 1, 12, *(np.array(p) * 100.0))
                + struct.pack("<BB4f", 2, 16, 1.0, 0.0, 0.0, 0.0)
                + struct.pack("<BB3f", 3, 12, 1.0, 1.0, 1.0)
                + struct.pack("<BBh", 7, 2, 1) + b"\x00")

    dummies = [anchor((0.0, 0.0, top - 0.02)), anchor((0.0, 0.0, 0.25 * top)), anchor(gem)]
    print("anchors: trail %.2f..%.2f m up the axis, gem glow at (%.2f, %.2f, %.2f) m"
          % (0.25 * top, top - 0.02, *gem))
    for label, sp, sn, su, sf, centre, secs in spin_pieces:
        rels = {ext: os.path.join(rel_dir, label + ext) for ext in (".ZMS", ".EFT")}
        rels["_morph.ZMO"] = os.path.join(rel_dir, label + "_morph.ZMO")
        rels["_spin.ZMO"] = os.path.join(rel_dir, label + "_spin.ZMO")
        spin_files.append((rels[".ZMS"], write_zms_v8(sp, sn, su, sf, pool=1)))
        spin_files.append((rels["_spin.ZMO"], spin_motion(secs)))
        # no morph motion: the piece is rigid, and since 2026-10-12 the client's
        # CEffect::IsFinish keeps an effect alive on its node animation alone
        spin_files.append((rels[".EFT"], write_eft(rels[".ZMS"], "", tex_rel,
                                                   rels["_spin.ZMO"], label)))
        props = (struct.pack("<BB3f", 1, 12, *(centre * 100.0))
                 + struct.pack("<BB4f", 2, 16, 1.0, 0.0, 0.0, 0.0)        # w, x, y, z
                 + struct.pack("<BB3f", 3, 12, 1.0, 1.0, 1.0)
                 + struct.pack("<BBh", 7, 2, 1) + b"\x00")
        dummies.append((rels[".EFT"].encode("ascii"), 3, props))         # POINT_EFFECT_ORIENTED

    # ---- the texture
    from mapgen import lighting
    tex = image.convert("RGB")
    if tex.size != (args.texture_size, args.texture_size):
        tex = tex.resize((args.texture_size, args.texture_size), Image.LANCZOS)
    dds = lighting.encode_dds({"t": np.asarray(tex, dtype=np.uint8)}, mips=0)["t"]
    print("texture: %dx%d -> %dx%d DXT5, %d bytes, %d mips"
          % (image.size[0], image.size[1], args.texture_size, args.texture_size, len(dds),
             struct.unpack_from("<I", dds, 28)[0]))

    # ---- the one-object source table import-item's appender expects
    bb = struct.pack("<6f", *(lo * 100.0), *(hi * 100.0))
    src = types.SimpleNamespace(
        meshes=[mesh_rel.encode("ascii")],
        materials=[(tex_rel.encode("ascii"), tmat_flags)],
        effects=[],
        objects=[(tcyl, [(0, 0, tprops)], [], bb)])
    for eft_rel, _, _ in dummies:
        if eft_rel is not None and any(ii.norm(e) == ii.norm(eft_rel) for e in ours.effects):
            sys.exit("the ZSC already lists %s" % eft_rel.decode())
    obj_id, files_needed, zsc_blob = ii.zsc_build_append(zsc_path, src, 0, source=OURS,
                                                         extra_dummies=dummies)
    if obj_id != new_id:
        sys.exit("STB/ZSC index drift: row %d vs object %d" % (new_id, obj_id))
    assert {ii.norm(mesh_rel.encode()), ii.norm(tex_rel.encode())} <= set(ii.norm(f) for f in files_needed)

    # ---- the STB row: the template's stats, our identity
    new_key = ("%s%d" % (KEY_PREFIX, new_id)).encode("ascii")
    row = list(tmpl[0:ocols - 2]) + [new_key]
    row[0] = args.name.encode("euc-kr", "replace")
    row[1] = b""
    icon_note = "template's icon %s (shared)" % row[9].decode()
    if args.icon_index is not None:
        if args.icon:
            sys.exit("pass --icon or --icon-index, not both")
        row[9] = str(args.icon_index).encode("ascii")
        icon_note = "icon %d (existing)" % args.icon_index
    row[43] = b"2"                           # gem anchor index, see `anchor`

    print("importing %s as ID %d (key %s, name %r, class %s, motion set %s)"
          % (os.path.basename(args.glb), new_id, new_key.decode(), args.name,
             row[4].decode(), row[34].decode()))
    print("files: %s, %s" % (mesh_rel, tex_rel))
    if args.dry_run:
        print("dry run: nothing written (icon: %s)" % icon_note)
        return 0

    # ---- backups, then write everything
    bdir = os.path.join(BACKUP_DIR, str(new_id))
    os.makedirs(bdir, exist_ok=True)
    tsi_path = os.path.join(OURS, "3DDATA", "CONTROL", "RES", "ITEM1.TSI")
    for p in (stb_path, zsc_path, stl_path, tsi_path):
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bdir, os.path.basename(p)))

    if args.icon:
        icon_mod = load_module("add-item-icon.py", "add_item_icon")
        cwd = os.getcwd()
        os.chdir(ROOT)                                  # its paths are relative
        try:
            idx = icon_mod.add_icon(Image.open(args.icon), "%s%d" % (KEY_PREFIX.lower(), new_id), False)
        finally:
            os.chdir(cwd)
        row[9] = str(idx).encode("ascii")
        icon_note = "icon %d" % idx
    else:
        print("note: no --icon, reusing the %s" % icon_note)

    out_dir = os.path.join(OURS, rel_dir.replace("\\", os.sep))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(OURS, mesh_rel.replace("\\", os.sep)), "wb") as fh:
        fh.write(zms)
    with open(os.path.join(OURS, tex_rel.replace("\\", os.sep)), "wb") as fh:
        fh.write(dds)
    for rel, blob in spin_files:
        with open(os.path.join(OURS, rel.replace("\\", os.sep)), "wb") as fh:
            fh.write(blob)
    with open(zsc_path, "wb") as fh:
        fh.write(zsc_blob)
    ii.stb_append_row(stb_path, row, False)
    ii.stl_append(stl_path, new_key, new_id, args.name.encode("utf-8"), args.desc.encode("utf-8"), False)

    manifest = {"id": new_id, "key": new_key.decode(), "name": args.name, "glb": os.path.abspath(args.glb),
                "template_row": args.template_row, "mesh": mesh_rel, "texture": tex_rel,
                "icon": row[9].decode(), "length_m": length, "grip": grip, "scale": scale,
                "rotation": R.tolist(), "vertices": int(len(pos)), "triangles": int(len(F)),
                "spin": [{"label": label, "seconds": secs, "centre_m": [float(c) for c in centre],
                          "triangles": int(len(sf))} for label, _, _, _, sf, centre, secs in spin_pieces],
                "spin_args": args.spin}
    with open(os.path.join(bdir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    # ---- verify from the bytes on disk
    _, _, vrows, vcols, vdata = ii.stb_read(stb_path)
    assert vrows - 1 == new_id + 1 and vdata[new_id][vcols - 2] == new_key
    vz = ii.Zsc(zsc_path)
    assert len(vz.objects) == new_id + 1
    _, vparts, _, _ = vz.objects[new_id]
    assert ii.norm(vz.meshes[vparts[0][0]]) == ii.norm(mesh_rel.encode())
    assert ii.norm(vz.materials[vparts[0][1]][0]) == ii.norm(tex_rel.encode())
    keys, langs = ii.stl_read(stl_path)
    assert keys[-1] == (new_key, new_id) and langs[-1][-1][0] == args.name.encode("utf-8")
    vpos, vnrm, vuv, vfaces = read_zms_v8(os.path.join(OURS, mesh_rel.replace("\\", os.sep)))
    assert len(vpos) == len(pos) and len(vfaces) == len(F)
    assert np.allclose(vpos, pos, atol=1e-5) and np.allclose(vuv, UV, atol=1e-6)
    a2, d2 = winding_agreement(vpos, vnrm, vfaces)
    assert a2 >= d2, (a2, d2)
    _, _, vdummies, _ = vz.objects[new_id]
    assert len(vdummies) == 3 + len(spin_pieces), (len(vdummies), len(spin_pieces))
    for a, _ in vdummies[:3]:
        assert struct.unpack("<hh", a) == (-1, 0)
    assert vdata[new_id][43] == b"2"
    for (a, _), (label, sp, _, _, sf, centre, secs) in zip(vdummies[3:], spin_pieces):
        eft_idx, eff_type = struct.unpack("<hh", a)
        assert eff_type == 3 and 0 <= eft_idx < len(vz.effects)
        eft_path = os.path.join(OURS, vz.effects[eft_idx].decode("ascii").replace("\\", os.sep))
        eft = read_eft(open(eft_path, "rb").read())
        m = eft["meshes"][0]
        assert m["morph"] == ""
        for rel in (m["mesh"], m["ani"], m["tex"]):
            assert os.path.exists(os.path.join(OURS, rel.replace("\\", os.sep))), rel
        p2, _, _, f2 = read_zms_v8(os.path.join(OURS, m["mesh"].replace("\\", os.sep)))
        assert len(p2) == len(sp) and len(f2) == len(sf) and np.allclose(p2, sp, atol=1e-5)
        magic, fps, n, chans = read_zmo_header(open(os.path.join(OURS, m["ani"].replace("\\", os.sep)), "rb").read())
        assert magic == "ZMO0002" and n == int(round(abs(secs) * 30)) + 1 and len(chans) == 2
        assert m["loop"] == 0 and m["repeat"] == 0 and m["link"] == 1 and m["use_ani"] == 1
        print("verified: %s -> effect %d (%s): %d triangles, %d frames at %d fps, no morph"
              % (label, eft_idx, os.path.basename(eft_path), len(f2), n, fps))
    print("verified: STB row %d, ZSC object %d, STL key %s, mesh %d/%d, %s"
          % (new_id, new_id, new_key.decode(), len(vpos), len(vfaces), icon_note))
    print("backups in %s. Next: restart the servers, bake the VFS, `/item 8 %d` "
          "(8 = weapon item type)." % (bdir, new_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
