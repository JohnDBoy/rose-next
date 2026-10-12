"""ZMS meshes (``*.ZMS``): the engine's vertex/face format, versions 5-8.

Layout is ``zz_mesh_tool::load_mesh_8`` / ``load_mesh_6``
(``src/engine/src/zz_mesh_tool.cpp``); the vertex-format bits are
``zz_vertex_format.h``::

    cstr magic "ZMS0007" / "ZMS0008" | u32 format | 3f min | 3f max
    u16 bone_count + u16 bone index each
    u16 vertex_count, then per attribute a block of vertex_count records:
        3f position (always) | 3f normal (NORMAL) | 4f colour (COLOR)
        | 4f weights + 4 x u16 bone slots (BLEND_WEIGHT and BLEND_INDEX both)
        | 3f tangent (TANGENT) | 2f per UV channel set (UV0..UV3)
    u16 face_count + 3 x u16 per face
    u16 matid_count + u16 faces-per-material each
    u16 strip_index_count + u16 each
    u16 pool (v8 only: 0 static, 1 dynamic, 2 system)

Version 6 (and 5, which has no material ids) is the same sequence with
**32-bit counts and a u32 record index in front of every record** (bones,
vertices in every attribute block, faces); the codec keeps those index
columns so the eleven v6 meshes we ship round-trip. A ``format`` may carry
bits the engine does not know (``0x400086`` on 18 meshes); they are kept.

Units: **v7/v8 headers and positions are metres, v6 are centimetres**
(``load_mesh_minmax`` applies ``ZZ_XFORM_IN`` for version < 7 only). Use
``positions_cm`` / ``bbox_cm`` rather than scaling by hand. The header bbox is
the real extent of the mesh and is what the client culls from -- the box the
ZSC caches is wrong in every ZSC (doc/zsc-bounding-boxes.md).

Writing: ``build(mesh)`` reproduces any parsed mesh byte for byte and writes a
``Mesh`` built from scratch (``rigid_v8`` is the constructor the glb importer
uses: position + normal + uv0, no bones, pool 0/1). Counts are 16-bit in
v7/v8: a mesh over 65,535 vertices or faces is refused. An effect mesh must be
pool 1 or ``zz_morpher`` asserts ``get_dynamic()``.
"""
import struct
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .binio import FormatError, read_cstr, read_file

VF_NONE, VF_POSITION, VF_NORMAL, VF_COLOR = 1, 2, 4, 8
VF_BLEND_WEIGHT, VF_BLEND_INDEX, VF_TANGENT = 16, 32, 64
VF_UV0, VF_UV1, VF_UV2, VF_UV3 = 128, 256, 512, 1024
UV_BITS = (VF_UV0, VF_UV1, VF_UV2, VF_UV3)
MESH_SCALE = {5: 1.0, 6: 1.0, 7: 100.0, 8: 100.0}            # header units -> cm
MAX_INDEX = 0xFFFF


@dataclass
class Mesh:
    version: int = 8
    format: int = VF_POSITION | VF_NORMAL | VF_UV0
    bbox_min: tuple = (0.0, 0.0, 0.0)
    bbox_max: tuple = (0.0, 0.0, 0.0)
    bones: List[int] = field(default_factory=list)
    positions: np.ndarray = None          # (n, 3) <f4, file units
    normals: Optional[np.ndarray] = None  # (n, 3)
    colors: Optional[np.ndarray] = None   # (n, 4) <f4
    weights: Optional[np.ndarray] = None  # (n, 4) <f4
    bone_slots: Optional[np.ndarray] = None   # (n, 4) <u2 (v7/8) or <u4 (v6)
    tangents: Optional[np.ndarray] = None
    uvs: List[np.ndarray] = field(default_factory=list)   # per set channel, (n, 2)
    faces: np.ndarray = None              # (m, 3)
    matids: list = field(default_factory=list)    # v7/8: [numfaces]; v6: [(mat_index, numfaces)]
    strip: np.ndarray = None              # <u2 strip indices (v7/8)
    pool: Optional[int] = None            # v8 only
    # v7/v8 trailer fields actually present. Four shipped meshes end before
    # the strip count or the pool; the engine's read fails silently and the
    # mesh loads, so a short trailer is kept short.
    trailer: tuple = ("matids", "strip", "pool")
    v6_index: dict = field(default_factory=dict)  # block -> u32 index column (v5/v6)
    tail: bytes = b""

    # ------------------------------------------------------------ helpers
    @property
    def scale_cm(self):
        return MESH_SCALE[self.version]

    def positions_cm(self):
        return self.positions.astype(np.float64) * self.scale_cm

    def bbox_cm(self):
        s = self.scale_cm
        return (np.array(self.bbox_min, dtype=np.float64) * s,
                np.array(self.bbox_max, dtype=np.float64) * s)

    def triangles_cm(self):
        """(m, 3, 3) corners in cm, or None when a face indexes past the vertices."""
        if len(self.faces) and self.faces.max() >= len(self.positions):
            return None
        return self.positions_cm()[self.faces.astype(np.int64)]

    @property
    def uv_channels(self):
        return [b for b in UV_BITS if self.format & b]

    def uv(self, channel):
        """UV set for channel 0-3 (file order follows the set bits), or None."""
        bits = self.uv_channels
        bit = UV_BITS[channel]
        return self.uvs[bits.index(bit)] if bit in bits else None


def _magic(b):
    magic, o = read_cstr(b, 0)
    if magic[:3] != b"ZMS" or not magic[3:].isdigit():
        raise FormatError("not a ZMS mesh (%r)" % magic[:8])
    return int(magic[3:]), o


def version_of(path_or_blob):
    """The ZMS version of a file, or None when it is not one."""
    try:
        return _magic(read_file(path_or_blob)[:16])[0]
    except FormatError:
        return None


def header(path_or_blob):
    """(version, format, bbox_min, bbox_max) from the first bytes -- what
    ``load_mesh_minmax`` reads, cheaply."""
    b = read_file(path_or_blob)
    ver, o = _magic(b)
    fmt, = struct.unpack_from("<I", b, o)
    lo = struct.unpack_from("<3f", b, o + 4)
    hi = struct.unpack_from("<3f", b, o + 16)
    return ver, fmt, lo, hi


def parse(path_or_blob):
    b = read_file(path_or_blob)
    ver, o = _magic(b)
    m = Mesh(version=ver)
    m.format, = struct.unpack_from("<I", b, o)
    o += 4
    m.bbox_min = struct.unpack_from("<3f", b, o)
    m.bbox_max = struct.unpack_from("<3f", b, o + 12)
    o += 24
    fmt = m.format
    wide = ver < 7

    def arr(dtype, count, cols):
        nonlocal o
        dt = np.dtype(dtype)
        n = dt.itemsize * count * cols
        if o + n > len(b):
            raise FormatError("ZMS v%d: truncated at byte %d" % (ver, o))
        a = np.frombuffer(b, dt, count * cols, o).reshape(count, cols).copy() if cols > 1 \
            else np.frombuffer(b, dt, count, o).copy()
        o += n
        return a

    def count():
        nonlocal o
        if wide:
            v, = struct.unpack_from("<I", b, o)
            o += 4
        else:
            v, = struct.unpack_from("<H", b, o)
            o += 2
        return v

    def indexed(dtype, n, cols, block):
        """A v6 block is (u32 index, record) per row: split into the two."""
        if not wide:
            return arr(dtype, n, cols)
        rec = np.dtype([("i", "<u4"), ("v", dtype, (cols,))])
        a = arr(rec, n, 1)
        m.v6_index[block] = a["i"].copy()
        return a["v"].copy()

    nb = count()
    if wide:
        bones = arr(np.dtype([("i", "<u4"), ("b", "<u4")]), nb, 1)
        m.v6_index["bones"] = bones["i"].copy()
        m.bones = [int(x) for x in bones["b"]]
    else:
        m.bones = [int(x) for x in arr("<u2", nb, 1)]
    nv = count()
    m.positions = indexed("<f4", nv, 3, "positions")
    if fmt & VF_NORMAL:
        m.normals = indexed("<f4", nv, 3, "normals")
    if fmt & VF_COLOR:
        m.colors = indexed("<f4", nv, 4, "colors")
    if (fmt & VF_BLEND_WEIGHT) and (fmt & VF_BLEND_INDEX):
        if wide:
            rec = np.dtype([("i", "<u4"), ("w", "<f4", (4,)), ("s", "<u4", (4,))])
            a = arr(rec, nv, 1)
            m.v6_index["skin"] = a["i"].copy()
            m.weights, m.bone_slots = a["w"].copy(), a["s"].copy()
        else:
            rec = np.dtype([("w", "<f4", (4,)), ("s", "<u2", (4,))])
            a = arr(rec, nv, 1)
            m.weights, m.bone_slots = a["w"].copy(), a["s"].copy()
    if fmt & VF_TANGENT:
        m.tangents = indexed("<f4", nv, 3, "tangents")
    for k, bit in enumerate(UV_BITS):
        if fmt & bit:
            m.uvs.append(indexed("<f4", nv, 2, "uv%d" % k))
    nf = count()
    if wide:
        rec = np.dtype([("i", "<u4"), ("f", "<u4", (3,))])
        a = arr(rec, nf, 1)
        m.v6_index["faces"] = a["i"].copy()
        m.faces = a["f"].copy()
    else:
        m.faces = arr("<u2", nf, 3)
    if wide:
        if ver >= 6:
            nm = count()
            pairs = arr(np.dtype([("m", "<u4"), ("n", "<u4")]), nm, 1)
            m.matids = [(int(x["m"]), int(x["n"])) for x in pairs]
    else:
        present = []
        m.strip = np.zeros(0, "<u2")
        if o + 2 <= len(b):
            nm = count()
            m.matids = [int(x) for x in arr("<u2", nm, 1)]
            present.append("matids")
            if o + 2 <= len(b):
                ns = count()
                m.strip = arr("<u2", ns, 1)
                present.append("strip")
                if ver >= 8 and o + 2 <= len(b):
                    m.pool, = struct.unpack_from("<H", b, o)
                    o += 2
                    present.append("pool")
        m.trailer = tuple(present)
    m.tail = b[o:]
    return m


def build(m):
    ver = m.version
    wide = ver < 7
    out = [b"ZMS%04d\0" % ver, struct.pack("<I", m.format),
           struct.pack("<3f", *m.bbox_min), struct.pack("<3f", *m.bbox_max)]
    nv = len(m.positions)

    def count(v):
        if not wide and v > MAX_INDEX:
            raise FormatError("ZMS v%d counts are 16-bit; %d does not fit" % (ver, v))
        return struct.pack("<I" if wide else "<H", v)

    def idx(block, n):
        a = m.v6_index.get(block)
        return a if a is not None and len(a) == n else np.arange(n, dtype="<u4")

    def block(a, dtype, cols, name):
        a = np.ascontiguousarray(a, dtype=dtype).reshape(len(a), cols)
        if not wide:
            return a.tobytes()
        rec = np.empty(len(a), dtype=np.dtype([("i", "<u4"), ("v", dtype, (cols,))]))
        rec["i"] = idx(name, len(a))
        rec["v"] = a
        return rec.tobytes()

    out.append(count(len(m.bones)))
    if wide:
        rec = np.empty(len(m.bones), dtype=np.dtype([("i", "<u4"), ("b", "<u4")]))
        rec["i"] = idx("bones", len(m.bones))
        rec["b"] = m.bones
        out.append(rec.tobytes())
    else:
        out.append(np.asarray(m.bones, dtype="<u2").tobytes())
    out.append(count(nv))
    out.append(block(m.positions, "<f4", 3, "positions"))
    fmt = m.format
    if fmt & VF_NORMAL:
        out.append(block(m.normals, "<f4", 3, "normals"))
    if fmt & VF_COLOR:
        out.append(block(m.colors, "<f4", 4, "colors"))
    if (fmt & VF_BLEND_WEIGHT) and (fmt & VF_BLEND_INDEX):
        if wide:
            rec = np.empty(nv, dtype=np.dtype([("i", "<u4"), ("w", "<f4", (4,)), ("s", "<u4", (4,))]))
            rec["i"] = idx("skin", nv)
        else:
            rec = np.empty(nv, dtype=np.dtype([("w", "<f4", (4,)), ("s", "<u2", (4,))]))
        rec["w"] = np.asarray(m.weights, dtype="<f4").reshape(nv, 4)
        rec["s"] = np.asarray(m.bone_slots).reshape(nv, 4)
        out.append(rec.tobytes())
    if fmt & VF_TANGENT:
        out.append(block(m.tangents, "<f4", 3, "tangents"))
    chans = [k for k, bit in enumerate(UV_BITS) if fmt & bit]
    if len(chans) != len(m.uvs):
        raise FormatError("format has %d UV channels, mesh holds %d" % (len(chans), len(m.uvs)))
    for k, a in zip(chans, m.uvs):
        out.append(block(a, "<f4", 2, "uv%d" % k))
    nf = len(m.faces)
    out.append(count(nf))
    if wide:
        rec = np.empty(nf, dtype=np.dtype([("i", "<u4"), ("f", "<u4", (3,))]))
        rec["i"] = idx("faces", nf)
        rec["f"] = np.asarray(m.faces).reshape(nf, 3)
        out.append(rec.tobytes())
        if ver >= 6:
            out.append(count(len(m.matids)))
            rec = np.empty(len(m.matids), dtype=np.dtype([("m", "<u4"), ("n", "<u4")]))
            for i, (mi, n) in enumerate(m.matids):
                rec[i] = (mi, n)
            out.append(rec.tobytes())
    else:
        out.append(np.ascontiguousarray(m.faces, dtype="<u2").reshape(nf, 3).tobytes())
        if "matids" in m.trailer:
            out.append(count(len(m.matids)))
            out.append(np.asarray(m.matids, dtype="<u2").tobytes())
        if "strip" in m.trailer:
            strip = m.strip if m.strip is not None else np.zeros(0, "<u2")
            out.append(count(len(strip)))
            out.append(np.ascontiguousarray(strip, dtype="<u2").tobytes())
        if ver >= 8 and "pool" in m.trailer:
            out.append(struct.pack("<H", 0 if m.pool is None else m.pool))
    out.append(m.tail)
    return b"".join(out)


def rigid_v8(positions, normals, uv0, faces, pool=0):
    """A v8 mesh from geometry (metres): position + normal + uv0, no bones."""
    pos = np.ascontiguousarray(positions, dtype="<f4").reshape(-1, 3)
    m = Mesh(version=8, format=VF_POSITION | VF_NORMAL | VF_UV0,
             bbox_min=tuple(float(x) for x in pos.min(0)),
             bbox_max=tuple(float(x) for x in pos.max(0)),
             positions=pos,
             normals=np.ascontiguousarray(normals, dtype="<f4").reshape(-1, 3),
             uvs=[np.ascontiguousarray(uv0, dtype="<f4").reshape(-1, 2)],
             faces=np.ascontiguousarray(faces, dtype="<u2").reshape(-1, 3),
             strip=np.zeros(0, "<u2"), pool=pool)
    if len(pos) > MAX_INDEX or len(m.faces) > MAX_INDEX:
        raise FormatError("%d vertices / %d triangles: ZMS counts are 16-bit (keep both under %d)"
                          % (len(pos), len(m.faces), MAX_INDEX))
    return m
