"""IFO map chunks as raw lumps -- the importers' view, built on ``rosefmt.ifo``.

**The structured codec is ``rosefmt.ifo``** (records with fields, every lump
decoded, proven on all 9,035 map files); use it for anything new. This module
is the older, byte-level view fifteen region importers were written against:
a lump is a block of bytes, an object record is ``(name, fixed, extra)`` with
the few fields the importers filter on decoded, and a rewrite replaces whole
blocks. The record *layout* is not repeated here: each record is walked with
the structured codec's own readers and its byte span sliced, so there is one
place that knows where a field sits.

Lump table: ``i32 lump_count | lump_count x (i32 type, i32 absolute_offset)``,
then the blocks contiguously in table order; a block runs to the next table
entry's offset, the last to EOF. Every lump but the last must be consumed
exactly (``exact``): an under-consumed lump is how a misread field is caught
(an event-object trigger read as u8 instead of varint, for instance). The
*final* lump's block may carry editor junk, kept as ``trailing``.

Positions are cm relative to the zone centre (world = pos + 520000); chunk
folder ``x_y`` is slot ``(x, 64 - y)``.
"""
import struct

from . import ifo
from .binio import FormatError, Reader, read_file

LUMP_MAPINFO, LUMP_OBJECT, LUMP_MOB, LUMP_CNST = ifo.MAPINFO, ifo.OBJECT, ifo.MOB, ifo.CNST
LUMP_SOUND, LUMP_EFFECT, LUMP_MORPH, LUMP_WATER = ifo.SOUND, ifo.EFFECT, ifo.MORPH, ifo.WATER
LUMP_REGEN, LUMP_OCEAN, LUMP_WARP = ifo.REGEN, ifo.OCEAN, ifo.WARP
LUMP_COLLISION, LUMP_EVENT_OBJECT = ifo.COLLISION, ifo.EVENT_OBJECT
OBJ_FIXED = 2 + 2 + 4 + 4 + 4 + 4 + 16 + 12 + 12

# per object lump: (record class, extra-fields reader) from the structured codec
_RECORD = {
    LUMP_OBJECT: (ifo.Record, None), LUMP_CNST: (ifo.Record, None),
    LUMP_MORPH: (ifo.Record, None), LUMP_WARP: (ifo.Record, None),
    LUMP_COLLISION: (ifo.Record, None),
    LUMP_MOB: (ifo.Mob, ifo._rx_mob), LUMP_SOUND: (ifo.Sound, ifo._rx_sound),
    LUMP_EFFECT: (ifo.Effect, ifo._rx_effect), LUMP_REGEN: (ifo.Regen, ifo._rx_regen),
    LUMP_EVENT_OBJECT: (ifo.EventObject, ifo._rx_event),
}


class IfoReader(Reader):
    """The cursor the old code exposed; ``rosefmt.binio.Reader`` with ``.o``."""

    def __init__(self, buf, o=0):
        super().__init__(buf, o)

    @property
    def o(self):
        return self.pos

    @o.setter
    def o(self, v):
        self.pos = v

    def take(self, n):
        return self.raw(n)

    def vstr(self):
        return self.pstr()


def put_bstr(s):
    if len(s) > 255:
        raise ValueError("name too long")
    return bytes([len(s)]) + s


def parse_object_lump(buf, start, end, lump_type, exact=True):
    """Decode an object lump. Returns (objects, trailing_bytes).

    Each object is ``dict(name, fixed, extra, warp_id, event_id, obj_id, rec)``:
    ``fixed`` the 60 header bytes after the name, ``extra`` the per-lump
    fields as bytes, ``rec`` the structured record.
    """
    cls, rx = _RECORD.get(lump_type, (ifo.Record, None))
    r = Reader(buf, start, end)
    count = r.i32()
    if count < 0 or count > 100000:
        raise FormatError("lump %d: implausible record count %d" % (lump_type, count))
    objs = []
    for _ in range(count):
        s0 = r.pos
        rec = ifo._read_header(r, cls)
        s1 = r.pos
        if rx:
            rx(r, rec)
        s2 = r.pos
        fixed = buf[s0 + 1 + len(rec.name):s1]
        objs.append(dict(name=rec.name, fixed=bytes(fixed), extra=bytes(buf[s1:s2]),
                         warp_id=rec.warp_id, event_id=rec.event_id, obj_id=rec.obj_id, rec=rec))
    if r.pos > end or (exact and r.pos != end):
        raise FormatError("lump %d: parsed to %d, block ends at %d" % (lump_type, r.pos, end))
    return objs, bytes(buf[r.pos:end])


def build_object_lump(objs, trailing=b""):
    out = [struct.pack("<i", len(objs))]
    for o in objs:
        out.append(put_bstr(o["name"]))
        out.append(o["fixed"])
        out.append(o["extra"])
    out.append(trailing)
    return b"".join(out)


def parse_ifo(buf, label="ifo"):
    """(buf, bounds) with bounds = [(lump_type, start, end)] in table order."""
    r = Reader(buf)
    n = r.i32()
    lumps = [(r.i32(), r.i32()) for _ in range(n)]
    header_end = r.pos
    offsets = [o for _, o in lumps]
    if offsets != sorted(offsets):
        raise FormatError("%s: lump offsets are not in table order" % label)
    if offsets and offsets[0] != header_end:
        raise FormatError("%s: first lump at %d, header ends at %d"
                          % (label, offsets[0], header_end))
    bounds = [(t, off, lumps[i + 1][1] if i + 1 < n else len(buf))
              for i, (t, off) in enumerate(lumps)]
    return buf, bounds


def read_ifo(path):
    return parse_ifo(read_file(path), str(path))


def build_ifo(bounds, buf, replacements):
    """``replacements``: {lump_type: raw block bytes}. The lump table is kept."""
    blocks = [replacements.get(t, buf[off:end]) for t, off, end in bounds]
    n = len(bounds)
    out = [struct.pack("<i", n)]
    cur = 4 + 8 * n
    for (t, _, _), blk in zip(bounds, blocks):
        out.append(struct.pack("<ii", t, cur))
        cur += len(blk)
    out.extend(blocks)
    return b"".join(out)


def lump_block(bounds, lump_type):
    for t, off, end in bounds:
        if t == lump_type:
            return off, end
    return None, None


def read_lump(buf, bounds, lump_type):
    """(objects, trailing) for a lump, or (None, None) if the file has none."""
    off, end = lump_block(bounds, lump_type)
    if off is None:
        return None, None
    return parse_object_lump(buf, off, end, lump_type,
                             exact=(lump_type != bounds[-1][0]))
