#!/usr/bin/env python3
"""Make hair style 1 zero-based, like every other style and every other client.

The symptom (2026-10-11): the Dimple Bonnet (LIST_CAP 73), a wig shipped as
mage/cleric headgear, showed orange patches of "broken hair texture" on
Magetester.  The mesh and texture are byte-identical to every reference dump
we own; the patches were the character's *own* hair, drawn inside the wig.

How a cap picks the hair under it (client ``CObjAVT::Create`` /
``CJustModelAVT``, macro ``HELMET_HAIR_TYPE`` = LIST_CAP game col 33)::

    hair model index = character hair id + cap hair type (0..4)

so retail lays every hair style out as a block of five consecutive ids in
``LIST_HAIR.STB`` / ``LIST_MHAIR.ZSC`` / ``LIST_WHAIR.ZSC``: the base hair,
three flattened "under a hat" variants, and an **empty** fifth slot.  Type 4
is "no hair at all" -- wigs and full helms (91 of our caps) -- and it works
only because the fifth slot of every block is empty.

Our custom ``newhair`` set had its first block shifted one slot down: id 0
empty, style 1 at 1-4.  ``SYSTEMFUNC.LUA`` offered hair 1 as the first style and
the world server refused hair 0 (``hair_id > 0``), so 11 of the 21 characters in
the database wear hair 1 -- and under a type-4 cap the client resolves
1 + 4 = 5, the *base of style 2*, a whole head of hair through the wig.  Every
other style lands on its empty slot.  (The reference dumps -- tsuki, ruff, 139,
titan, Jrose -- all have style 1 at 0-3 with 4 empty.)

What this script changes (all under ``data/``, so this file is the record):

* ``3DDATA/AVATAR/LIST_MHAIR.ZSC`` and ``LIST_WHAIR.ZSC``: objects 1-4 move to
  0-3, object 4 becomes empty.  Objects 5+ untouched, byte for byte.
* ``3DDATA/STB/LIST_HAIR.STB``: rows 1-4 move to 0-3, row 4 is blanked with the
  label ``1-4`` (the other blocks' convention: ``2-4``, ``3-4`` ...).
* ``SCRIPTS/SYSTEMFUNC.LUA``: the first creation hair is id 0, not 1.

The companions, outside ``data/``: the world server accepts hair 0 at creation
(``ws_threadsql.cpp``), the client sends it (``cnetwork.cpp``), and migration
``database/migrations/0004-hair-zero-based`` moves existing characters from
hair 1 to 0 and makes 0 the column default.  Ship client, data and servers
together: old data with the new servers lets a player create a bald character
(hair 0 is empty), and the old client refuses to send hair 0.

Faces are one-based too (``LIST_MFACE.ZSC`` object 0 is empty) but faces have no
block structure, so nothing collides; they are left alone.

Usage::

    python scripts/fix-hair-block0.py --dry-run     # report, write nothing
    python scripts/fix-hair-block0.py               # apply (backs up first)
    python scripts/fix-hair-block0.py --verify      # exit 1 unless fixed
    python scripts/fix-hair-block0.py --restore     # put the originals back

Backups go to ``build/hair-block0/`` (never beside the files: ``pack.ps1``
refuses a ``.bak`` under ``data/``).  Re-bake the VFS and restart both servers
afterwards -- they read ``LIST_HAIR.STB`` at startup.
"""
import argparse
import importlib.util
import json
import os
import shutil
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BACKUP = os.path.join(ROOT, "build", "hair-block0")
ZSCS = ["3DDATA/AVATAR/LIST_MHAIR.ZSC", "3DDATA/AVATAR/LIST_WHAIR.ZSC"]
STB = "3DDATA/STB/LIST_HAIR.STB"
LUA = "SCRIPTS/SYSTEMFUNC.LUA"
LUA_OLD = b'SC_AddSelectItem4CreateAvatar( 2 , "1", 1);'
LUA_NEW = b'SC_AddSelectItem4CreateAvatar( 2 , "1", 0);'
BLOCK = 5


def load_oro():
    """The shared data layer (scripts/rosedata): codecs, table schema, importer helpers."""
    import rosedata
    return rosedata


def dpath(rel):
    return os.path.join(DATA, rel.replace("/", os.sep))


def zsc_bytes(z, objects):
    return (z.d[:z.objcnt_pos] + struct.pack("<H", len(objects))
            + b"".join(z.object_bytes(*o) for o in objects))


def part_mesh(z, obj):
    return os.path.basename(z.meshes[obj[1][0][0]].decode("latin-1")) if obj[1] else ""


def zsc_state(z):
    """'shifted' (style 1 at 1-4), 'fixed' (at 0-3, 4 empty) or 'unknown'."""
    names = [part_mesh(z, z.objects[i]).lower() for i in range(BLOCK + 1)]
    if (names[0] == "" and all(names[i].endswith("_0110%d.zms" % (i - 1)) for i in range(1, 5))
            and names[5].endswith("_01200.zms")):
        return "shifted"
    if (all(names[i].endswith("_0110%d.zms" % i) for i in range(4)) and names[4] == ""
            and names[5].endswith("_01200.zms")):
        return "fixed"
    return "unknown"


def stb_state(stb):
    r = [stb.get(i, 0) for i in range(BLOCK + 1)]
    if r[0] == b"" and r[1:5] == [b"1-0", b"1-1", b"1-2", b"1-3"] and r[5] == b"2-0":
        return "shifted"
    if r[0:5] == [b"1-0", b"1-1", b"1-2", b"1-3", b"1-4"] and r[5] == b"2-0":
        return "fixed"
    return "unknown"


def lua_state(raw):
    if LUA_OLD in raw:
        return "shifted"
    if LUA_NEW in raw:
        return "fixed"
    return "unknown"


def survey(oro):
    out = {}
    for rel in ZSCS:
        z = oro.Zsc(dpath(rel))
        if zsc_bytes(z, z.objects) != z.d:
            raise SystemExit("%s: the ZSC codec does not round-trip this file" % rel)
        out[rel] = (zsc_state(z), z)
    stb = oro.Stb(dpath(STB))
    out[STB] = (stb_state(stb), stb)
    raw = open(dpath(LUA), "rb").read()
    out[LUA] = (lua_state(raw), raw)
    return out


def fixed_zsc(z):
    empty = z.objects[0]
    assert not empty[1], "object 0 is not empty"
    objects = z.objects[1:BLOCK] + [empty] + z.objects[BLOCK:]
    return zsc_bytes(z, objects)


def fixed_stb(stb):
    for r in range(BLOCK - 1):
        for c in range(stb.cols):
            stb.set(r, c, stb.get(r + 1, c))
    for c in range(stb.cols):
        stb.set(BLOCK - 1, c, b"")
    stb.set(BLOCK - 1, 0, b"1-4")
    return stb.to_bytes()


def backup(rel):
    os.makedirs(BACKUP, exist_ok=True)
    dst = os.path.join(BACKUP, os.path.basename(rel))
    if not os.path.exists(dst):
        shutil.copy2(dpath(rel), dst)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    oro = load_oro()

    if args.restore:
        manifest = os.path.join(BACKUP, "manifest.json")
        if not os.path.exists(manifest):
            raise SystemExit("nothing to restore: no %s" % manifest)
        for rel in json.load(open(manifest))["files"]:
            shutil.copy2(os.path.join(BACKUP, os.path.basename(rel)), dpath(rel))
            print("restored", rel)
        return

    states = survey(oro)
    for rel, (state, _) in states.items():
        print("%-32s %s" % (rel, state))
    if args.verify:
        ok = all(s == "fixed" for s, _ in states.values())
        print("VERIFY", "OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)
    if any(s == "unknown" for s, _ in states.values()):
        raise SystemExit("a file is in neither the shifted nor the fixed layout; refusing")
    todo = [rel for rel, (s, _) in states.items() if s == "shifted"]
    if not todo:
        print("already fixed")
        return

    new = {}
    for rel in todo:
        _, obj = states[rel]
        if rel in ZSCS:
            new[rel] = fixed_zsc(obj)
            z2 = _parse_zsc_bytes(oro, new[rel])      # prove the result by re-parsing it
            assert zsc_state(z2) == "fixed", rel
            assert z2.objects[BLOCK:] == obj.objects[BLOCK:], "%s: objects past the block changed" % rel
        elif rel == STB:
            new[rel] = fixed_stb(obj)
            s2 = _parse_stb_bytes(oro, new[rel])
            assert stb_state(s2) == "fixed"
            assert [s2.get(r, c) for r in range(BLOCK, s2.rows) for c in range(s2.cols)] == \
                [obj.get(r, c) for r in range(BLOCK, obj.rows) for c in range(obj.cols)]
        else:
            new[rel] = obj.replace(LUA_OLD, LUA_NEW, 1)
            assert lua_state(new[rel]) == "fixed"
    if args.dry_run:
        print("dry run: would rewrite", ", ".join(todo))
        return
    for rel in todo:
        backup(rel)
        with open(dpath(rel), "wb") as f:
            f.write(new[rel])
        print("wrote", rel)
    with open(os.path.join(BACKUP, "manifest.json"), "w") as f:
        json.dump({"files": todo}, f, indent=1)
    states = survey(oro)
    bad = [rel for rel, (s, _) in states.items() if s != "fixed"]
    if bad:
        raise SystemExit("post-write verify failed for %s" % bad)
    print("VERIFY OK -- re-bake the VFS and restart both servers")


def _parse_zsc_bytes(oro, raw):
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ZSC") as t:
        t.write(raw)
    try:
        return oro.Zsc(t.name)
    finally:
        os.unlink(t.name)


def _parse_stb_bytes(oro, raw):
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".STB") as t:
        t.write(raw)
    try:
        return oro.Stb(t.name)
    finally:
        os.unlink(t.name)


if __name__ == "__main__":
    main()
