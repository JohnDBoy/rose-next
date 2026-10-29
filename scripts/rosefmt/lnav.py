"""<ZONE FOLDER>.lnav: the server's layered walk grid for one zone (our format).

Written by scripts/nav-bake.py, read by the game server (src/sho_gameserver/src/nav/).
Design and rules: doc/pathfinding-and-z-plan.md, section 3.1.

The grid has 1 m cells, cut into 160 x 160-cell tiles, one per map chunk (160 m).
Every cell holds a short list of floors ("spans"), lowest first. Most cells are
plain terrain, and those are not stored: the tile's heightmap gives their height,
and a 2-bit class says whether they are walkable. Only the other ("complex") cells
carry a span list.

Coordinates: world cm as the server uses them (IFO position + 520,000). Chunk slot
(sx, sy) covers x in [sx * 16000, +16000) and y in [sy * 16000, +16000); its tile
row 0 is the south edge, as is the heightmap's row 0 here (the HIM file's is north).

Layout, little endian:

    "LNAV"  u16 version  u16 cell_cm
    i16 step_cm  i16 body_lo_cm  i16 body_hi_cm  i16 hazard_cm   (bake rules, for the record)
    u16 n_inputs   { u8 len, name bytes, u32 crc32 } * n     (files the bake read)
    u16 n_tiles    { i16 sx, i16 sy, u32 offset, u32 size } * n
    u32 n_anchors  { f32 x, f32 y, i16 z, u16 flags } * n     (regen points, resolved floor)
    tiles, each:
        i16 heights[65 * 65]      terrain vertices, cm, row 0 = south (2.5 m apart)
        u8  simple[6400]          2 bits per cell, cell i at byte i // 4, bits 2 * (i % 4):
                                  0 = not walkable (blocked or unreachable), 1..3 = walkable,
                                  with that clearance class
        u8  complex[3200]         1 bit per cell (bit i % 8 of byte i // 8): has a span list
        u16 main_component        component of every walkable simple cell, unless...
        u8  dense_components      ...this is 1: then u16 component[25600] follows
        u32 n_complex
        { i16 visual_top, u8 n_spans, u8 pad } * n_complex       in cell order
        { i16 z, u8 flags, u8 clearance, u16 component, u8 below, u8 above } * (sum of n_spans)
                                  (version 1: without below/above, read as 0)

Span flags: WALK (no geometry 30-180 cm above it), REACHED (connected to a seed:
an event point, a regen point or an NPC), TERRAIN, UP (an up-facing or terrain
floor), HAZARD (the client would draw a monster here more than 3 m up, on a roof or
a deck: today's GetHeightTop), STAIRS (a floor on HEIGHTONLY parts: it links to its
neighbours at the terrain's 135 cm, not the 60 cm of other object floors). visual_top is
that height for the cell, or NO_HEIGHT when it is the terrain's.

below/above (version 2, 2026-10-29): the floor's surface spans z - below .. z + above cm in
its cell (0 on the terrain). A ramp or a flight of steps rises through its cell, so two of
its floors can be 78 cm apart (Muris' great stairs) yet joined: the server links object
floors within 60 cm, or within 135 when the higher one starts within 60 of the lower one's
top (Nav::StepLinks).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from .binio import FormatError, Reader, Writer

MAGIC = b"LNAV"
VERSION = 2
TILE_CELLS = 160
TILE_VERTS = 65
NO_HEIGHT = -32768

WALK, REACHED, TERRAIN, UP, HAZARD, STAIRS = 1, 2, 4, 8, 16, 32

SPAN_DTYPE = np.dtype([("z", "<i2"), ("flags", "u1"), ("clearance", "u1"), ("component", "<u2"),
                       ("below", "u1"), ("above", "u1")])
SPAN_DTYPE_V1 = np.dtype([("z", "<i2"), ("flags", "u1"), ("clearance", "u1"), ("component", "<u2")])
CELL_DTYPE = np.dtype([("visual_top", "<i2"), ("n_spans", "u1"), ("pad", "u1")])


@dataclass
class Tile:
    sx: int
    sy: int
    heights: np.ndarray            # (65, 65) int16 cm, row 0 = south
    simple: np.ndarray             # (160, 160) uint8 0..3
    complex_mask: np.ndarray       # (160, 160) bool
    main_component: int = 0
    components: np.ndarray = None  # (160, 160) uint16, or None when main_component covers it
    cells: np.ndarray = None       # CELL_DTYPE, one per complex cell in cell order
    spans: np.ndarray = None       # SPAN_DTYPE, every complex cell's spans, in order


@dataclass
class Anchor:
    x: float
    y: float
    z: int
    flags: int = 0                 # 1 = resolved onto a reached floor


@dataclass
class Lnav:
    cell_cm: int = 100
    step_cm: int = 135
    body_lo_cm: int = 30
    body_hi_cm: int = 180
    hazard_cm: int = 300
    inputs: List[Tuple[bytes, int]] = field(default_factory=list)
    tiles: Dict[Tuple[int, int], Tile] = field(default_factory=dict)
    anchors: List[Anchor] = field(default_factory=list)


def _pack_bits(values, bits):
    v = values.reshape(-1).astype(np.uint8)
    per = 8 // bits
    v = v.reshape(-1, per)
    out = np.zeros(len(v), np.uint8)
    for k in range(per):
        out |= (v[:, k] & ((1 << bits) - 1)) << (bits * k)
    return out


def _unpack_bits(data, bits, count):
    per = 8 // bits
    out = np.zeros((len(data), per), np.uint8)
    for k in range(per):
        out[:, k] = (data >> (bits * k)) & ((1 << bits) - 1)
    return out.reshape(-1)[:count]


def _build_tile(t):
    w = Writer()
    n = TILE_CELLS * TILE_CELLS
    w.raw(np.ascontiguousarray(t.heights, "<i2").tobytes())
    w.raw(_pack_bits(t.simple, 2).tobytes())
    w.raw(_pack_bits(t.complex_mask, 1).tobytes())
    w.u16(t.main_component)
    w.u8(0 if t.components is None else 1)
    if t.components is not None:
        w.raw(np.ascontiguousarray(t.components, "<u2").tobytes())
    cells = t.cells if t.cells is not None else np.zeros(0, CELL_DTYPE)
    spans = t.spans if t.spans is not None else np.zeros(0, SPAN_DTYPE)
    if len(cells) != int(t.complex_mask.sum()):
        raise FormatError("tile %d,%d: %d cell records for %d complex cells"
                          % (t.sx, t.sy, len(cells), int(t.complex_mask.sum())))
    if int(cells["n_spans"].sum()) != len(spans):
        raise FormatError("tile %d,%d: span count mismatch" % (t.sx, t.sy))
    w.u32(len(cells))
    w.raw(cells.astype(CELL_DTYPE).tobytes())
    w.raw(spans.astype(SPAN_DTYPE).tobytes())
    assert n % 8 == 0
    return w.getvalue()


def _parse_tile(r, sx, sy, version=VERSION):
    n = TILE_CELLS * TILE_CELLS
    heights = r.array("<i2", TILE_VERTS * TILE_VERTS).reshape(TILE_VERTS, TILE_VERTS)
    simple = _unpack_bits(r.array("u1", n // 4), 2, n).reshape(TILE_CELLS, TILE_CELLS)
    cmask = _unpack_bits(r.array("u1", n // 8), 1, n).reshape(TILE_CELLS, TILE_CELLS).astype(bool)
    main = r.u16()
    dense = r.u8()
    comps = r.array("<u2", n).reshape(TILE_CELLS, TILE_CELLS) if dense else None
    nc = r.u32()
    if nc != int(cmask.sum()):
        raise FormatError("tile %d,%d: %d cell records for %d complex cells" % (sx, sy, nc, int(cmask.sum())))
    cells = r.array(CELL_DTYPE, nc)
    if version >= 2:
        spans = r.array(SPAN_DTYPE, int(cells["n_spans"].sum()))
    else:
        old = r.array(SPAN_DTYPE_V1, int(cells["n_spans"].sum()))
        spans = np.zeros(len(old), SPAN_DTYPE)
        for name in SPAN_DTYPE_V1.names:
            spans[name] = old[name]
    return Tile(sx, sy, heights, simple, cmask, main, comps, cells, spans)


def build(nav):
    tiles = [_build_tile(nav.tiles[k]) for k in sorted(nav.tiles)]
    w = Writer()
    w.raw(MAGIC)
    w.u16(VERSION)
    w.u16(nav.cell_cm)
    for v in (nav.step_cm, nav.body_lo_cm, nav.body_hi_cm, nav.hazard_cm):
        w.i16(v)
    w.u16(len(nav.inputs))
    for name, crc in nav.inputs:
        w.bstr(name)
        w.u32(crc)
    w.u16(len(tiles))
    index_at = w.tell()
    for _ in tiles:
        w.raw(b"\0" * 12)
    w.u32(len(nav.anchors))
    for a in nav.anchors:
        w.f32(a.x)
        w.f32(a.y)
        w.i16(a.z)
        w.u16(a.flags)
    offsets = []
    for blob in tiles:
        offsets.append((w.tell(), len(blob)))
        w.raw(blob)
    buf = bytearray(w.getvalue())
    for i, (key, (off, size)) in enumerate(zip(sorted(nav.tiles), offsets)):
        idx = Writer()
        idx.i16(key[0])
        idx.i16(key[1])
        idx.u32(off)
        idx.u32(size)
        buf[index_at + 12 * i:index_at + 12 * (i + 1)] = idx.getvalue()
    return bytes(buf)


def parse(data):
    r = Reader(data)
    if r.raw(4) != MAGIC:
        raise FormatError("not an LNAV file")
    version = r.u16()
    if version not in (1, VERSION):
        raise FormatError("LNAV version %d, expected 1 or %d" % (version, VERSION))
    nav = Lnav(cell_cm=r.u16())
    nav.step_cm, nav.body_lo_cm, nav.body_hi_cm, nav.hazard_cm = r.i16(), r.i16(), r.i16(), r.i16()
    for _ in range(r.u16()):
        name = r.bstr()
        nav.inputs.append((name, r.u32()))
    index = []
    for _ in range(r.u16()):
        index.append((r.i16(), r.i16(), r.u32(), r.u32()))
    for _ in range(r.u32()):
        x, y = r.f32(), r.f32()
        nav.anchors.append(Anchor(x, y, r.i16(), r.u16()))
    for sx, sy, off, size in index:
        tr = Reader(data, off, off + size)
        nav.tiles[(sx, sy)] = _parse_tile(tr, sx, sy, version)
        if tr.remaining():
            raise FormatError("tile %d,%d: %d bytes left over" % (sx, sy, tr.remaining()))
    return nav
