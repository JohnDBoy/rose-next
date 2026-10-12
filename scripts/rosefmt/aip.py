"""AIP monster AI (``3DDATA/AI/*.aip``): patterns of events with conditions and actions.

Layout (``CAI_FILE::Load`` -> ``CAI_PATTERN::Load`` -> ``CAI_EVENT::Load``)::

    i32 pattern_count | i32 sec | i32 secatk | i32 title_len | title
    per pattern: char[32] name | i32 event_count
    per event:   char[32] name | i32 cond_count | conds | i32 act_count | acts
    a cond/act: u32 size (incl. this field) | i32 type | payload

Conditions and actions are kept as raw records (size + type + payload); the
audits decode the few fields they filter on. Six action types carry a monster
id as a WORD at offset 8 (09 Change_CHAR, 10 Create_PET, 18, 20, 36, 37) and
action 24 a ``short`` skill id at offset 10; **nothing in the game validates
either**, so an imported ``.aip`` that names a blank row crashes the client
(``scripts/audit-ai-monster-refs.py``, ``audit-ai-skill-refs.py``). Pattern
events are first-match-wins. Anything after the last pattern is kept (``tail``).

Round-trips byte for byte on all 509 files we ship.
"""
import struct

from .binio import read_file


def parse(b):
    """(header, title, patterns, tail).

    ``header`` = (pattern_count, sec, secatk); ``patterns`` =
    ``[(name32, [(name32, [cond_bytes], [act_bytes])])]``.
    """
    b = read_file(b)
    o = 0

    def i32():
        nonlocal o
        v, = struct.unpack_from("<i", b, o)
        o += 4
        return v

    npat, sec, secatk, ntitle = i32(), i32(), i32(), i32()
    title = b[o:o + ntitle]
    o += ntitle
    pats = []
    for _ in range(npat):
        pname = b[o:o + 32]
        o += 32
        nev = i32()
        evs = []
        for _ in range(nev):
            ename = b[o:o + 32]
            o += 32
            conds = []
            for _ in range(i32()):
                sz, = struct.unpack_from("<I", b, o)
                conds.append(b[o:o + sz])
                o += sz
            acts = []
            for _ in range(i32()):
                sz, = struct.unpack_from("<I", b, o)
                acts.append(b[o:o + sz])
                o += sz
            evs.append((ename, conds, acts))
        pats.append((pname, evs))
    return (npat, sec, secatk), title, pats, b[o:]


def build(header, title, pats, tail=b""):
    out = bytearray()
    out += struct.pack("<iiii", len(pats), header[1], header[2], len(title))
    out += title
    for pname, evs in pats:
        out += pname
        out += struct.pack("<i", len(evs))
        for ename, conds, acts in evs:
            out += ename
            out += struct.pack("<i", len(conds))
            for c in conds:
                out += c
            out += struct.pack("<i", len(acts))
            for a in acts:
                out += a
    out += tail
    return bytes(out)


def record_type(rec):
    """The i32 type of a condition/action record."""
    return struct.unpack_from("<i", rec, 4)[0]


parse_aip, build_aip = parse, build
