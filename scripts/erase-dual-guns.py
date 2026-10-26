"""Erase the 21 dual guns (LIST_WEAPON 361-381, weapon type 253) (2026-10-26).

Dual Bubble Guns (lv 10) ... Dual Tornado Rifles (lv 210), one every ten levels, each
a two-part model: an ordinary gun's mesh on dummy 0 (`far\\fguN`) and a left-hand
mesh on dummy 1 (`dgu\\DGUN`). They never worked: TYPE_MOTION column 20 (their
animation set) has no stance or attack clip -- FILE_MOTION 278-281 are blank -- and no
dump of ours has one. QQiROSE's `dualpistols_*` clips were tried from EVO-REFORGED's
client the same day and worked, but the user judged dual guns not worth pursuing and
confusing next to the gun line: **fully erased, no stub** (the house meaning of delete).

    LIST_WEAPON.STB     the 21 rows blanked (row numbers stay; 382 is a katar)
    LIST_WEAPON_S.STL   their LWEA keys removed
    LIST_WEAPON.ZSC     their objects emptied; the mesh/material records only they used
                        removed (`rosefmt.zsc.Zsc.without`, other objects remapped) --
                        the right-hand meshes are the gun line's and stay
    dgu\\               the left-hand meshes moved out of data/, plus anything else in
                        that folder no ZSC names (DGU13: a mesh pair and two textures
                        no row ever used)
    LIST_SELL row 6     Huzam's "Weapons lv210": Dual Tornado Rifles (8381) out, the
                        other 13 kept in row order (stock-muris-shops.py now expects 13)
    ITEM_DROP row 49    Cerberus: Dual Steam Shockers (8377, a common slot, lv 170) ->
                        Ballista Rifle 251 (lv 175); Bastard & Brave Gun (8376, group 3,
                        lv 160) -> White Night Gun 249 (lv 155). Every common slot stays
                        filled, as `import-cerberus.py`'s drop_table (updated to match)
                        wants; the replacements are ordinary guns of the same band.

Left alone on purpose: the icon sprites (the atlas is never renumbered), the ground
models in LIST_FIELDITEM.ZSC (as erase-retired-weapons.py), TYPE_MOTION column 20
(column numbers are load-bearing) and every code path for type 253 (dead, harmless).
Refused if any STB cell still names a row in either item encoding (`8000+row`,
`800000+row`) after the two edits above, or a ZSC outside LIST_WEAPON.ZSC names a file
it would move. No character in the dev database owned one (`item.type_id = 8`,
`game_data_id` 361-381; the one test character seeded for the clip test was deleted)
-- check again on a database with players.

    python scripts/erase-dual-guns.py --dry-run
    python scripts/erase-dual-guns.py
    python scripts/erase-dual-guns.py --verify
    python scripts/erase-dual-guns.py --restore

Undo in `build/erase-dual-guns/`: STB cells and STL entries recorded, the ZSC as a
whole-file original with the hash of what this wrote (restore refuses a file changed
since), the files moved back. `data/` is gitignored, so this file is the record.
Restart the servers, re-bake the VFS.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from rosefmt import Stb, Stl, Zsc  # noqa: E402

DATA = os.path.join(REPO, "data", "3DDATA")
STB = os.path.join(DATA, "STB", "LIST_WEAPON.STB")
STL = os.path.join(DATA, "STB", "LIST_WEAPON_S.STL")
ZSC = os.path.join(DATA, "WEAPON", "LIST_WEAPON.ZSC")
SELL = os.path.join(DATA, "STB", "LIST_SELL.STB")
DROP = os.path.join(DATA, "STB", "ITEM_DROP.STB")
DGU = "WEAPON/WEAPON/dgu"
BACKUP_DIR = os.path.join(REPO, "build", "erase-dual-guns")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

ROWS = {361: "Dual Bubble Guns", 362: "Air & Bubble Guns", 363: "Dual Gloria Guns",
        364: "Iron Rifle & Gloria Gun", 365: "Iron Shotgun & Iron Rifle",
        366: "Dual Sorden Guns", 367: "Edge & Sworden Gun", 368: "Showdown & Edge Gun",
        369: "Dual Berettas", 370: "Sniper Gun & Beretta", 371: "Justice Cannon & Sniper Gun",
        372: "Dual RP-911s", 373: "Piercing Gun & RP-911", 374: "Remington & Piercing Gun",
        375: "Dual Brave Guns", 376: "Bastard & Brave Gun", 377: "Dual Steam Shockers",
        378: "Shock Impact Gun & Steam Shocker", 379: "Dual White Night Guns",
        380: "Winchester & White Night Gun", 381: "Dual Tornado Rifles"}
T_WEAPON, LEGACY_BASE, WIDE_BASE, DUAL_GUN_TYPE = 8, 1000, 100000, 253
HUZAM_TAB, HUZAM_FIRST, HUZAM_LAST = 6, 2, 49          # LIST_SELL row, item cols
CERBERUS_ROW = 49
DROP_SWAPS = {14: (8377, 8251), 44: (8376, 8249)}      # col: (old, new)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def norm(p):
    return p.decode("latin-1").replace("/", "\\").lower()


def codes():
    return ({str(T_WEAPON * LEGACY_BASE + r) for r in ROWS}
            | {str(T_WEAPON * WIDE_BASE + r) for r in ROWS})


def live_references():
    """Every STB cell holding one of the 21, in either item encoding."""
    want = codes()
    hits = []
    for p in glob.glob(os.path.join(DATA, "STB", "*.STB")):
        t = Stb(p)
        for r, row in enumerate(t.d):
            for c, b in enumerate(row):
                if b.strip().decode("latin-1") in want:
                    hits.append("%s row %d col %d" % (os.path.basename(p), r, c))
    return hits


def huzam_plan(sell):
    """LIST_SELL row 6's item cells with 8381 taken out and the rest kept in order."""
    cells = [sell.get(HUZAM_TAB, c) for c in range(HUZAM_FIRST, HUZAM_LAST + 1)]
    kept = [c for c in cells if c.strip() and c.strip() != b"0" and c.strip().decode("latin-1") not in codes()]
    return kept + [b"0"] * (len(cells) - len(kept))


def dgu_files():
    """{ZSC-style lower-case path: file on disk} for everything under dgu\\."""
    out = {}
    for p in glob.glob(os.path.join(DATA, *DGU.split("/"), "**", "*"), recursive=True):
        if os.path.isfile(p):
            out[("3ddata\\" + os.path.relpath(p, DATA)).replace("/", "\\").lower()] = p
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.restore:
        return restore()

    stb, stl, sell, drop = Stb(STB), Stl(STL), Stb(SELL), Stb(DROP)
    zraw = open(ZSC, "rb").read()
    z = Zsc(ZSC)
    for t, p in ((stb, STB), (stl, STL), (sell, SELL), (drop, DROP)):
        if t.to_bytes() != open(p, "rb").read():
            sys.exit("ABORT: %s does not round-trip" % os.path.basename(p))
    if z.without() != zraw[:z.obj_end]:
        sys.exit("ABORT: LIST_WEAPON.ZSC does not round-trip")

    keys = {r: "LWEA%d" % r for r in ROWS}
    stb_left = [r for r in ROWS if any(c.strip() for c in stb.d[r])]
    stl_left = [k for k in keys.values() if stl.has(k)]
    obj_left = [r for r in ROWS if z.objects[r][1]]
    dgu_left = dgu_files()
    sell_new = huzam_plan(sell)
    sell_old = [sell.get(HUZAM_TAB, c) for c in range(HUZAM_FIRST, HUZAM_LAST + 1)]
    drop_left = {c: v for c, v in DROP_SWAPS.items() if drop.get(CERBERUS_ROW, c).strip() != str(v[1]).encode()}

    print("rows still holding cells: %s" % stb_left)
    print("STL keys still present:   %d" % len(stl_left))
    print("ZSC objects with a model: %s" % obj_left)
    print("files left under dgu\\:    %d" % len(dgu_left))
    print("Huzam tab 6 to restock:   %s" % (sell_new != sell_old))
    print("Cerberus cells to swap:   %s" % sorted(drop_left))
    pending = stb_left or stl_left or obj_left or dgu_left or sell_new != sell_old or drop_left
    if a.verify:
        hits = live_references()
        for h in hits:
            print("   still referenced: " + h)
        if pending or hits:
            print("VERIFY FAILED")
            return 1
        print("ALL CHECKS PASSED -- the 21 dual guns are erased.")
        return 0
    if not pending:
        print("nothing to do.")
        return 0

    for r, nm in ROWS.items():
        if r in stb_left:
            cur = stb.get(r, 0).decode("latin-1").strip()
            if cur != nm or stb.i(r, 4) != DUAL_GUN_TYPE:
                sys.exit("ABORT: LIST_WEAPON %d is %r type %d, expected %r type %d"
                         % (r, cur, stb.i(r, 4), nm, DUAL_GUN_TYPE))
    for c, (old, new) in drop_left.items():
        if drop.get(CERBERUS_ROW, c).strip() != str(old).encode():
            sys.exit("ABORT: ITEM_DROP %d col %d is %r, expected %d"
                     % (CERBERUS_ROW, c, drop.get(CERBERUS_ROW, c), old))
        if stb.i(new % LEGACY_BASE, 4) not in (232, 233):
            sys.exit("ABORT: replacement %d is not a gun" % new)

    # what is left once the shop and drop cells change must be nothing
    for c, (old, new) in drop_left.items():
        drop.set(CERBERUS_ROW, c, str(new).encode())
    for i, v in enumerate(sell_new):
        sell.set(HUZAM_TAB, HUZAM_FIRST + i, v)
    left = []
    for t, name in ((drop, "ITEM_DROP.STB"), (sell, "LIST_SELL.STB")):
        for r, row in enumerate(t.d):
            for c, b in enumerate(row):
                if b.strip().decode("latin-1") in codes():
                    left.append("%s row %d col %d" % (name, r, c))
    others = [h for h in live_references()
              if not h.startswith(("ITEM_DROP.STB ", "LIST_SELL.STB "))]
    if left or others:
        sys.exit("ABORT: still referenced:\n  " + "\n  ".join(left + others))

    # the ZSC records only these objects use, and nothing outside LIST_WEAPON.ZSC
    mine_m = {m for r in ROWS for m, _t, _p in z.objects[r][1]}
    mine_t = {t for r in ROWS for _m, t, _p in z.objects[r][1]}
    for i, (_c, parts, _d, _b) in enumerate(z.objects):
        if i in ROWS:
            continue
        mine_m -= {m for m, _t, _p in parts}
        mine_t -= {t for _m, t, _p in parts}
    # A dual gun's right hand is the gun line's file under its own record: the record
    # goes, the file stays while any surviving record names it.
    named = {norm(z.meshes[m]) for i, (_c, parts, _d, _b) in enumerate(z.objects) if i not in ROWS
             for m, _t, _p in parts} | {norm(z.materials[t][0]) for i, (_c, parts, _d, _b) in
                                         enumerate(z.objects) if i not in ROWS for _m, t, _p in parts}
    paths = ({norm(z.meshes[m]) for m in mine_m} | {norm(z.materials[t][0]) for t in mine_t}) - named
    outside = paths - set(dgu_left)
    if outside:
        sys.exit("ABORT: files only the dual guns use live outside dgu\\: %s" % sorted(outside))
    moving = set(dgu_left)
    for p in glob.glob(os.path.join(DATA, "**", "*.ZSC"), recursive=True):
        blob = open(p, "rb").read().lower()
        for q in moving:
            if (not os.path.samefile(p, ZSC) and q.encode("latin-1") in blob) or q in named:
                sys.exit("ABORT: %s still references %s" % (p, q))

    print("would swap %d drop cell(s), restock tab %d (%d items), blank %d rows, remove %d "
          "STL keys, %d mesh and %d material record(s), move %d file(s) (%d not used by the rows)"
          % (len(drop_left), HUZAM_TAB, sum(1 for v in sell_new if v != b"0"), len(stb_left),
             len(stl_left), len(mine_m), len(mine_t), len(moving), len(moving - paths)))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(os.path.join(BACKUP_DIR, "files"), exist_ok=True)
    man = {"cells": {}, "stl": {}, "sell": [v.decode("latin-1") for v in sell_old],
           "drop": {str(c): str(old) for c, (old, _n) in drop_left.items()},
           "zsc_sha": "", "files": []}
    for r in stb_left:
        man["cells"][str(r)] = [c.decode("latin-1") for c in stb.d[r]]
        stb.d[r] = [b"" for _ in stb.d[r]]
    for k in stl_left:
        j = stl.index(k)
        man["stl"][k] = {"id": stl.keys[j][1],
                         "langs": [[f.decode("latin-1") for f in rows[j]] for rows in stl.langs]}
    stl.remove(stl_left)
    for r in obj_left:
        z.objects[r] = (z.objects[r][0], [], [], b"")
    out = z.without(mine_m, mine_t)

    open(os.path.join(BACKUP_DIR, "LIST_WEAPON.ZSC"), "wb").write(zraw)
    open(STB, "wb").write(stb.to_bytes())
    open(STL, "wb").write(stl.to_bytes())
    open(SELL, "wb").write(sell.to_bytes())
    open(DROP, "wb").write(drop.to_bytes())
    open(ZSC, "wb").write(out)
    man["zsc_sha"] = sha(out)
    for rel in sorted(moving):
        src = dgu_left[rel]
        dst = os.path.join(BACKUP_DIR, "files", os.path.relpath(src, DATA))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        man["files"].append(os.path.relpath(src, DATA))
    shutil.rmtree(os.path.join(DATA, *DGU.split("/")))   # only empty folders are left
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("erased (undo: --restore). Restart the servers and re-bake the VFS.")
    return 0


def restore():
    if not os.path.isfile(MANIFEST):
        print("nothing to restore")
        return 0
    man = json.load(open(MANIFEST))
    if sha(open(ZSC, "rb").read()) != man["zsc_sha"]:
        sys.exit("ABORT: LIST_WEAPON.ZSC changed since this erased -- restore by hand")
    stb, stl, sell, drop = Stb(STB), Stl(STL), Stb(SELL), Stb(DROP)
    for r, cells in man["cells"].items():
        stb.d[int(r)] = [c.encode("latin-1") for c in cells]
    for k, e in man["stl"].items():
        stl.append(k, e["id"], *e["langs"][0])
        j = stl.index(k)
        for li, fields in enumerate(e["langs"]):
            stl.langs[li][j] = [f.encode("latin-1") for f in fields]
    for i, v in enumerate(man["sell"]):
        sell.set(HUZAM_TAB, HUZAM_FIRST + i, v.encode("latin-1"))
    for c, old in man["drop"].items():
        drop.set(CERBERUS_ROW, int(c), old.encode("latin-1"))
    open(STB, "wb").write(stb.to_bytes())
    open(STL, "wb").write(stl.to_bytes())
    open(SELL, "wb").write(sell.to_bytes())
    open(DROP, "wb").write(drop.to_bytes())
    shutil.copy2(os.path.join(BACKUP_DIR, "LIST_WEAPON.ZSC"), ZSC)
    for rel in man["files"]:
        dst = os.path.join(DATA, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(os.path.join(BACKUP_DIR, "files", rel), dst)
    os.remove(MANIFEST)
    print("restored the 21 rows, their STL keys, the ZSC, Huzam's tab, Cerberus's two "
          "cells and %d file(s)" % len(man["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
