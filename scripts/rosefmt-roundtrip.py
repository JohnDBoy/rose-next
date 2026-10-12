"""Round-trip every shipped data file through the rosefmt codecs.

For every STB, STL, ZSC, CHR, LTB, AIP, TSI, QSD, CON and IFO under ``data/``
(or ``--root``), this parses the file, serialises the model back and compares
the bytes. A format passes only when every file is byte-identical; a reader
without a writer (ZMO, the VFS index) is only parsed.

The map formats proper (ZON, HIM, TIL, MOV, IFO as records, LIT) are covered by
``scripts/mapgen-roundtrip.py``; the IFO check here is the raw-lump view the
importers use (``rosefmt.ifo_lumps``).

    python scripts/rosefmt-roundtrip.py                 # data/
    python scripts/rosefmt-roundtrip.py --root <dump>   # a reference client
    python scripts/rosefmt-roundtrip.py --only stb,stl  # one or two formats
    python scripts/rosefmt-roundtrip.py --selftest      # edit-a-field checks

Exit status 0 when every file round-trips (and the selftest passes), 1 otherwise.
Read-only: nothing under the root is written.
"""
import argparse
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rosefmt import Chr, Ltb, Stb, Stl, Zsc, aip, condialog as con, ifo_lumps, idx, qsd, tsi, zmo  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOT = os.path.join(REPO, "data")


def rt_stb(p):
    return Stb(p).to_bytes()


def rt_stl(p):
    return Stl(p).to_bytes()


def rt_zsc(p):
    z = Zsc(p)
    # editors leave junk after the last object; the game and the writer drop it
    return z.to_bytes() + z.d[z.obj_end:]


def rt_zsc_rebuild(p):
    z = Zsc(p)
    return z.rebuild() + z.d[z.obj_end:]


def rt_chr(p):
    return Chr(p).to_bytes()


def rt_ltb(p):
    return Ltb(p).to_bytes()


def rt_aip(p):
    return aip.build(*aip.parse(p))


def rt_tsi(p):
    t, b = tsi.read(p, strict=False)
    return tsi.build(t, b, total=tsi.declared_total(p))


def rt_qsd(p):
    return qsd.build(qsd.parse(p))


def rt_con(p):
    with open(p, "rb") as fh:
        b = fh.read()
    return con.join(*con.split_ex(b))


def rt_ifo(p):
    buf, bounds = ifo_lumps.read_ifo(p)
    repl = {}
    for t, off, end in bounds:
        if t in (ifo_lumps.LUMP_OBJECT, ifo_lumps.LUMP_MOB, ifo_lumps.LUMP_REGEN,
                 ifo_lumps.LUMP_SOUND, ifo_lumps.LUMP_EFFECT, ifo_lumps.LUMP_WARP,
                 ifo_lumps.LUMP_COLLISION, ifo_lumps.LUMP_EVENT_OBJECT, ifo_lumps.LUMP_NPC):
            objs, trailing = ifo_lumps.read_lump(buf, bounds, t)
            repl[t] = ifo_lumps.build_object_lump(objs, trailing)
    return ifo_lumps.build_ifo(bounds, buf, repl)


def parse_zmo(p):
    zmo.read_header(p)
    zmo.events(p)
    return None


def parse_idx(p):
    idx.parse(p)
    return None


FORMATS = {
    "stb": (".stb", rt_stb),
    "stl": (".stl", rt_stl),
    "zsc": (".zsc", rt_zsc),
    "zsc-rebuild": (".zsc", rt_zsc_rebuild),
    "chr": (".chr", rt_chr),
    "ltb": (".ltb", rt_ltb),
    "aip": (".aip", rt_aip),
    "tsi": (".tsi", rt_tsi),
    "qsd": (".qsd", rt_qsd),
    "con": (".con", rt_con),
    "ifo": (".ifo", rt_ifo),
    "zmo": (".zmo", parse_zmo),
    "idx": (".idx", parse_idx),
}


def walk(root, ext):
    seen = set()
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(ext):
                p = os.path.join(dirpath, f)
                k = os.path.normcase(p)
                if k not in seen:
                    seen.add(k)
                    yield p


def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n if len(a) != len(b) else -1


def run(root, only, verbose):
    failed = 0
    for name, (ext, fn) in FORMATS.items():
        if only and name not in only:
            continue
        ok = bad = err = 0
        problems = []
        for p in walk(root, ext):
            try:
                out = fn(p)
            except Exception as e:  # noqa: BLE001 - a codec error is a finding
                err += 1
                problems.append("%s: %s: %s" % (os.path.relpath(p, root), type(e).__name__, e))
                if verbose:
                    traceback.print_exc()
                continue
            if out is None:
                ok += 1
                continue
            with open(p, "rb") as fh:
                orig = fh.read()
            if out == orig:
                ok += 1
            else:
                bad += 1
                problems.append("%s: differs at byte %d (%d -> %d bytes)"
                                % (os.path.relpath(p, root), first_diff(orig, out), len(orig), len(out)))
        total = ok + bad + err
        verdict = "OK " if not (bad or err) else "BAD"
        print("%s %-12s %6d files  identical=%d differ=%d error=%d"
              % (verdict, name, total, ok, bad, err))
        for line in problems[:20]:
            print("      " + line)
        if len(problems) > 20:
            print("      ... %d more" % (len(problems) - 20))
        failed += bad + err
    return failed


def selftest():
    """Edit-a-field checks on synthetic tables: the writers must honour edits."""
    import struct
    import io

    # STB: build a 2x3 table, edit, re-read
    hdr = struct.pack("<I", 20) + struct.pack("<5H", 10, 10, 10, 10, 10)   # raw_cols + 1 widths
    for nm in (b"root", b"a", b"b", b"c", b"title", b"r0", b"r1"):
        hdr += struct.pack("<H", len(nm)) + nm
    cells = b""
    for r in range(2):
        for c in range(3):
            v = ("%d%d" % (r, c)).encode()
            cells += struct.pack("<H", len(v)) + v
    blob = b"STB1" + struct.pack("<III", 16 + len(hdr), 3, 4) + hdr + cells
    t = Stb(blob)
    assert t.rows == 2 and t.cols == 3 and t.s(1, 2) == "12" and t.i(0, 1) == 1
    assert t.colname(0) == "a" and t.rowname(1) == "r1"
    assert t.to_bytes() == blob
    t.set(0, 0, "x")
    t.grow_to(3, {2: "r2"})
    t2 = Stb(t.to_bytes())
    assert t2.s(0, 0) == "x" and t2.rows == 3 and t2.rowname(2) == "r2" and t2.s(2, 1) == ""

    # STL: modern, two languages
    s = Stl.__new__(Stl)
    s.path, s.encoding, s.fmt, s.tag = None, "latin-1", b"ITST01", b"ITST01"
    s.nfields, s.legacy, s.keys = 2, False, [(b"K1", 1), (b"K2", 2)]
    s.langs = [[[b"one", b"d1"], [b"two", b"d2"]], [[b"un", b""], [b"deux", b""]]]
    s.count = 2
    blob = s.to_bytes()
    s2 = Stl(blob)
    assert s2.name("K2", 1) == "deux" and s2.field("K1", 1) == "d1" and s2.to_bytes() == blob
    s2.append("K3", 3, "three", "d3")
    s2.set_name("K1", "uno", lang=1)
    s3 = Stl(s2.to_bytes())
    assert s3.name("K3") == "three" and s3.name("K1", 1) == "uno" and s3.name("K1") == "one"
    assert s3.remove(["K2"]) == 1 and Stl(s3.to_bytes()).name("K3") == "three"
    # legacy dialect
    leg = struct.pack("<B", 5) + b"I_NUM" + struct.pack("<I", 1) + b"\x02K9" + struct.pack("<I", 9)
    leg += bytes([3]) + b"abc" + bytes([0])
    L = Stl(leg)
    assert L.legacy and L.name("K9") == "abc" and L.to_bytes() == leg

    # QSD: build, append, drop
    cond = struct.pack("<Iihh", 12, 0x00000004, 7, 0)
    rew = struct.pack("<Ii", 8, 0x01000001)
    trig = qsd.build_trigger("T1", [cond], [rew])
    blob = struct.pack("<II", 12, 0) + qsd.pstr("desc")
    blob = qsd.append_pattern(blob, "P1", [trig])
    assert qsd.has_trigger(blob, "T1") and qsd.build(qsd.parse(blob)) == blob
    assert qsd.find_entity(blob, "T1", 0x01000001) == rew
    out, removed = qsd.drop_conditions(blob, {("T1", 4, 7)})
    assert removed == [("T1", 4, 7)] and qsd.parse(out)["patterns"][0][1][0]["conds"] == []

    # AIP
    pat = (b"p".ljust(32, b"\0"), [(b"e".ljust(32, b"\0"), [struct.pack("<Ii", 8, 1)], [])])
    blob = aip.build((1, 0, 0), b"t", [pat], b"")
    assert aip.build(*aip.parse(blob)) == blob

    # ZMO trailer edit
    body = b"ZMO0002\0" + struct.pack("<III", 30, 3, 0)
    trailer = struct.pack("<H3h", 3, 0, 21, 0)
    clip = body + trailer + struct.pack("<I", len(body)) + b"EZMO"
    assert zmo.event_set(clip) == {21}
    assert zmo.event_set(zmo.with_events(clip, {1: 22, 2: 23})) == {22, 23}

    # TSI
    tex = [tsi.texture_entry("a.dds")]
    blocks = [(1, tsi.sprite_entry(0, 0, 0, 40, 40, "x"))]
    blob = tsi.build(tex, blocks)
    t, b = tsi.read(blob)
    assert tsi.build(t, b) == blob and list(tsi.iter_sprites(b))[0][3:] == (0, 0, 0, 40, 40)

    # CON: header + lua + appendix
    head = bytearray(524)
    struct.pack_into("<I", head, 520, 524)
    lua, app = b"return 1", b"AT_x = function() end"
    blob = con.join(bytes(head), lua, app)
    assert con.split(blob) == (bytes(head), lua, app)
    assert con.join(*con.split(con.join(bytes(head), lua))) == con.join(bytes(head), lua)
    print("selftest OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--only", default="", help="comma-separated format names")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    rc = 0
    if a.selftest:
        rc |= selftest()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    if not a.selftest or only:
        rc |= 1 if run(a.root, only, a.verbose) else 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
