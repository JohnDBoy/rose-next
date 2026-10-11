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

WHAT IT DOES NOT DO
-------------------
Multiple textures are not atlased: every primitive must share one base-colour
image. Normal, metallic and roughness maps are ignored -- the engine draws
diffuse only.

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
    measure a template and to verify our own output."""
    b = open(path, "rb").read()
    e = b.index(b"\0")
    magic = b[:e].decode("latin-1")
    if magic not in ("ZMS0007", "ZMS0008"):
        sys.exit("%s: %s is not a v7/v8 mesh" % (path, magic))
    p = e + 1
    fmt = struct.unpack_from("<I", b, p)[0]
    p += 4 + 24
    nb = struct.unpack_from("<H", b, p)[0]
    p += 2 + 2 * nb
    nv = struct.unpack_from("<H", b, p)[0]
    p += 2
    pos = np.frombuffer(b, "<f4", nv * 3, p).reshape(nv, 3).astype(np.float64)
    p += 12 * nv
    nrm = None
    if fmt & VF_NORMAL:
        nrm = np.frombuffer(b, "<f4", nv * 3, p).reshape(nv, 3).astype(np.float64)
        p += 12 * nv
    if fmt & 8:
        p += 16 * nv
    if (fmt & 16) and (fmt & 32):
        p += 24 * nv
    if fmt & 64:
        p += 12 * nv
    uv = None
    for bit in (128, 256, 512, 1024):
        if fmt & bit:
            u = np.frombuffer(b, "<f4", nv * 2, p).reshape(nv, 2).astype(np.float64)
            uv = u if uv is None else uv
            p += 8 * nv
    nf = struct.unpack_from("<H", b, p)[0]
    p += 2
    faces = np.frombuffer(b, "<u2", nf * 3, p).reshape(nf, 3).astype(np.int64)
    return pos, nrm, uv, faces


def write_zms_v8(pos, nrm, uv, faces):
    nv, nf = len(pos), len(faces)
    if nv > MAX_INDEX or nf > MAX_INDEX:
        sys.exit("%d vertices / %d triangles: ZMS counts are 16-bit (keep both under %d). "
                 "Use the generator's remesh/retopology export, or decimate first -- stock "
                 "weapons are 100-2,500 triangles." % (nv, nf, MAX_INDEX))
    out = [b"ZMS0008\0", struct.pack("<I", VF_POSITION | VF_NORMAL | VF_UV0)]
    out.append(struct.pack("<3f", *pos.min(0)))
    out.append(struct.pack("<3f", *pos.max(0)))
    out.append(struct.pack("<H", 0))                              # bones
    out.append(struct.pack("<H", nv))
    out.append(pos.astype("<f4").tobytes())
    out.append(nrm.astype("<f4").tobytes())
    out.append(uv.astype("<f4").tobytes())
    out.append(struct.pack("<H", nf))
    out.append(faces.astype("<u2").tobytes())
    out.append(struct.pack("<H", 0))                              # material ids
    out.append(struct.pack("<H", 0))                              # strip indices
    out.append(struct.pack("<H", 0))                              # pool: static
    return b"".join(out)


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
    ap.add_argument("--max-triangles", type=int,
                    help="decimate to at most this many triangles (texture-aware, needs "
                         "pymeshlab); stock weapons are 100-2,500, 3000 is invisible on a "
                         "Meshy remesh. Default: no decimation")
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
    zms = write_zms_v8(pos, nrm, UV, F)

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
    obj_id, files_needed, zsc_blob = ii.zsc_build_append(zsc_path, src, 0)
    if obj_id != new_id:
        sys.exit("STB/ZSC index drift: row %d vs object %d" % (new_id, obj_id))
    assert set(ii.norm(f) for f in files_needed) == {ii.norm(mesh_rel.encode()), ii.norm(tex_rel.encode())}

    # ---- the STB row: the template's stats, our identity
    new_key = ("%s%d" % (KEY_PREFIX, new_id)).encode("ascii")
    row = list(tmpl[0:ocols - 2]) + [new_key]
    row[0] = args.name.encode("euc-kr", "replace")
    row[1] = b""
    icon_note = "template's icon %s (shared)" % row[9].decode()

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
    with open(zsc_path, "wb") as fh:
        fh.write(zsc_blob)
    ii.stb_append_row(stb_path, row, False)
    ii.stl_append(stl_path, new_key, new_id, args.name.encode("utf-8"), args.desc.encode("utf-8"), False)

    manifest = {"id": new_id, "key": new_key.decode(), "name": args.name, "glb": os.path.abspath(args.glb),
                "template_row": args.template_row, "mesh": mesh_rel, "texture": tex_rel,
                "icon": row[9].decode(), "length_m": length, "grip": grip, "scale": scale,
                "rotation": R.tolist(), "vertices": int(len(pos)), "triangles": int(len(F))}
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
    print("verified: STB row %d, ZSC object %d, STL key %s, mesh %d/%d, %s"
          % (new_id, new_id, new_key.decode(), len(vpos), len(vfaces), icon_note))
    print("backups in %s. Next: restart the servers, bake the VFS, `/item 2 %d`." % (bdir, new_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
