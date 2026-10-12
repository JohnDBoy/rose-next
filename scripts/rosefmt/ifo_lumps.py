"""IFO map chunks as raw lumps -- the importers' view (``x_y.IFO``).

**The structured codec is ``mapgen.ifo``** (records with fields, every lump
decoded, proven on all 9,035 map files); use it for anything new. This module
is the older, byte-level view the region importers were written against: a
lump is a block of bytes, an object record is ``(name, fixed, extra)`` with the
few fields the importers filter on decoded, and a rewrite replaces whole
blocks. Both round-trip; this one is kept because fifteen importers speak it.

Layout: ``i32 lump_count | lump_count x (i32 type, i32 absolute_offset)`` then
the blocks contiguously in table order. The object record shared by every
object lump::

    u8 name_len + name | i16 warp_id | i16 event_id | i32 obj_type | i32 obj_id
    | i32 map_x | i32 map_y | 16B quat | 12B pos | 12B scale

Per-lump extras: MOB adds ``i32 AI`` + pascal .CON name; REGEN a point name,
two mob lists and four i32s; EVENT_OBJECT two **varint** strings (every other
string is plain u8 -- reading an event-object trigger as u8 silently
under-consumes the lump); EFFECT a .eft name; SOUND a .wav name, range (cm)
and interval (s). Undecoded lumps are copied byte for byte. The *final* lump's
block runs to EOF and RoseZA's map editor leaves junk after it, which is
captured as ``trailing`` and re-emitted.

Positions are cm relative to the zone centre (world = pos + 520000); chunk
folder ``x_y`` is slot ``(x, 64 - y)``.
"""
import struct

from .binio import read_file

LUMP_OBJECT, LUMP_MOB, LUMP_REGEN = 1, 2, 8
LUMP_SOUND, LUMP_EFFECT = 4, 5
LUMP_WARP, LUMP_COLLISION, LUMP_EVENT_OBJECT = 10, 11, 12
LUMP_MAPINFO, LUMP_NPC = 0, 3
LUMP_WIDEWATER, LUMP_OCEAN, LUMP_WATER = 6, 7, 9
OBJ_FIXED = 2 + 2 + 4 + 4 + 4 + 4 + 16 + 12 + 12


class IfoReader:
    def __init__(self, buf, o=0):
        self.b, self.o = buf, o

    def i32(self):
        v, = struct.unpack_from("<i", self.b, self.o)
        self.o += 4
        return v

    def u8(self):
        v = self.b[self.o]
        self.o += 1
        return v

    def take(self, n):
        s = self.b[self.o:self.o + n]
        if len(s) != n:
            raise ValueError("truncated .IFO")
        self.o += n
        return s

    def bstr(self):
        """u8 length + bytes -- what ReadByte + Read/Seek does."""
        return self.take(self.u8())

    def vstr(self):
        """7-bit varint length + bytes -- what CFileSystem::ReadPascalString does."""
        b = self.u8()
        if b & 0x80:
            b = ((self.u8() << 7) | (b - 0x80))
        return self.take(b)


def put_bstr(s):
    if len(s) > 255:
        raise ValueError("name too long")
    return bytes([len(s)]) + s


def parse_object_lump(buf, start, end, lump_type, exact=True):
    """Decode an object lump. Returns (objects, trailing_bytes).

    Every lump but the last consumes its block exactly, and ``exact`` makes a
    shortfall an error there -- that is how a misread field gets caught rather
    than silently absorbed.
    """
    r = IfoReader(buf, start)
    count = r.i32()
    objs = []
    for _ in range(count):
        name = r.bstr()
        fixed = r.take(OBJ_FIXED)
        warp_id, event_id = struct.unpack_from("<hh", fixed, 0)
        obj_id, = struct.unpack_from("<i", fixed, 8)
        raw_start = r.o
        if lump_type == LUMP_MOB:
            r.take(4)                       # i32 AI
            r.bstr()                        # .CON file
        elif lump_type == LUMP_EVENT_OBJECT:
            r.vstr(); r.vstr()              # trigger name, .CON file
        elif lump_type == LUMP_EFFECT:
            r.bstr()                        # .eft file
        elif lump_type == LUMP_SOUND:
            r.bstr(); r.i32(); r.i32()      # .wav file, range (cm), interval (sec)
        elif lump_type == LUMP_REGEN:
            r.bstr()                        # regen point name
            for _ in range(2):              # basic list, then tactics list
                for _ in range(r.i32()):
                    r.bstr(); r.i32(); r.i32()
            r.take(16)                      # interval, limit, range, tactics point
        objs.append(dict(name=name, fixed=fixed, extra=buf[raw_start:r.o],
                         warp_id=warp_id, event_id=event_id, obj_id=obj_id))
    if r.o > end or (exact and r.o != end):
        raise ValueError("lump %d: parsed to %d, block ends at %d" % (lump_type, r.o, end))
    return objs, buf[r.o:end]


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
    r = IfoReader(buf)
    n = r.i32()
    lumps = [(r.i32(), r.i32()) for _ in range(n)]
    header_end = r.o
    offsets = [o for _, o in lumps]
    if offsets != sorted(offsets):
        raise ValueError("%s: lump offsets are not in table order" % label)
    if offsets and offsets[0] != header_end:
        raise ValueError("%s: first lump at %d, header ends at %d"
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
