"""Erase the five Jrose lv210 weapons that wore the lv230 Arcidian line's models
(2026-10-20).

    1420 Strike Hammer    = Befoul Hammer's model       (LIST_WEAPON 1369)
    1421 Assault Sword    = Flesh Reaver's              (1370)
    1422 Final Axe        = Befoul Axe's                (1372)
    1423 Hyper Railgun    = Heat Ray Gun's              (1374)
    1425 Force Wand       = Intrepid Wand's             (1376)

Byte-identical meshes and textures, kept in a second folder
(`3Ddata\\WEAPON\\WEAPON\\onehand|twohand|far|magic\\...`). After weapon-ladder-pass.py
moved the Arcidian line to 230, the user's rule became **no weapon may wear a higher
tier's look**; they were first retired (sold and dropped nowhere), and then -- "I meant
strip the row also, it's confusing" -- erased. The house meaning of delete is **fully
erased, no stub**:

    LIST_WEAPON.STB     the five rows blanked (every cell; the row numbers stay, ids
                        are load-bearing and the next row is 1426)
    LIST_WEAPON_S.STL   their LWEA keys removed (every language block)
    LIST_WEAPON.ZSC     their objects emptied, and the 7 mesh + 7 material records only
                        they used removed (`rosefmt.zsc.Zsc.without`, every other
                        object's indices remapped)
    the five folders    holding only those 14 files, moved out of data/

Refused if anything still names them: any STB cell (shops, drops, crafting ...) in the
legacy or wide item encoding, or another ZSC referencing the files. Checked by hand when
this was written: no character in the dev database owned one (`item.type_id = 8`,
`game_data_id` in the five), so no inventory is left holding a blank row -- check again
before running it on a database with players. The icon sprites stay in ITEM1.TSI
(nothing else points at them; the atlas is never renumbered).

    python scripts/erase-retired-weapons.py --dry-run
    python scripts/erase-retired-weapons.py
    python scripts/erase-retired-weapons.py --verify
    python scripts/erase-retired-weapons.py --restore

Undo in `build/erase-retired-weapons/`: STB cells and STL entries recorded, the ZSC as a
whole-file original with the hash of what this wrote (restore refuses a file changed
since), the folders moved back. `data/` is gitignored, so this file is the record.
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
BACKUP_DIR = os.path.join(REPO, "build", "erase-retired-weapons")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

ROWS = {1420: "Strike Hammer", 1421: "Assault Sword", 1422: "Final Axe",
        1423: "Hyper Railgun", 1425: "Force Wand"}
FOLDERS = ["WEAPON/WEAPON/onehand/210_hammer", "WEAPON/WEAPON/twohand/210_axe",
           "WEAPON/WEAPON/twohand/210_sword", "WEAPON/WEAPON/far/210gun",
           "WEAPON/WEAPON/magic/210rod"]
T_WEAPON, WIDE_BASE = 8, 100000


def sha(b):
    return hashlib.sha256(b).hexdigest()


def norm(p):
    return p.decode("latin-1").replace("/", "\\").lower()


def live_references():
    """Every STB cell holding one of the five, in either item encoding."""
    codes = {str(T_WEAPON * WIDE_BASE + r) for r in ROWS}
    hits = []
    for p in glob.glob(os.path.join(DATA, "STB", "*.STB")):
        t = Stb(p)
        for r, row in enumerate(t.d):
            for c, b in enumerate(row):
                if b.strip().decode("latin-1") in codes:
                    hits.append("%s row %d col %d" % (os.path.basename(p), r, c))
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.restore:
        return restore()

    stb = Stb(STB)
    stl = Stl(STL)
    zraw = open(ZSC, "rb").read()
    z = Zsc(ZSC)
    if stb.to_bytes() != open(STB, "rb").read() or stl.to_bytes() != open(STL, "rb").read():
        sys.exit("ABORT: LIST_WEAPON.STB / _S.STL does not round-trip")
    if z.without() != zraw[:z.obj_end]:
        sys.exit("ABORT: LIST_WEAPON.ZSC does not round-trip")

    keys = {r: "LWEA%d" % r for r in ROWS}
    stb_left = [r for r in ROWS if any(c.strip() for c in stb.d[r])]
    stl_left = [k for k in keys.values() if stl.has(k)]
    obj_left = [r for r in ROWS if z.objects[r][1]]
    dir_left = [d for d in FOLDERS if os.path.isdir(os.path.join(DATA, *d.split("/")))]

    print("rows still holding cells: %s" % stb_left)
    print("STL keys still present:   %s" % stl_left)
    print("ZSC objects with a model: %s" % obj_left)
    print("folders still in data/:   %s" % dir_left)
    pending = stb_left or stl_left or obj_left or dir_left
    if a.verify:
        hits = live_references()
        for h in hits:
            print("   still referenced: " + h)
        if pending or hits:
            print("VERIFY FAILED")
            return 1
        print("ALL CHECKS PASSED -- the five weapons are erased.")
        return 0
    if not pending:
        print("nothing to do.")
        return 0

    for r, nm in ROWS.items():
        cur = stb.get(r, 0).decode("latin-1").strip()
        if r in stb_left and cur != nm:
            sys.exit("ABORT: LIST_WEAPON %d is %r, expected %r" % (r, cur, nm))
    hits = live_references()
    if hits:
        sys.exit("ABORT: still referenced:\n  " + "\n  ".join(hits))

    # the ZSC records only these objects use, and nothing outside LIST_WEAPON.ZSC
    mine_m = {m for r in ROWS for m, _t, _p in z.objects[r][1]}
    mine_t = {t for r in ROWS for _m, t, _p in z.objects[r][1]}
    for i, (_c, parts, _d, _b) in enumerate(z.objects):
        if i in ROWS:
            continue
        mine_m -= {m for m, _t, _p in parts}
        mine_t -= {t for _m, t, _p in parts}
    paths = {norm(z.meshes[m]) for m in mine_m} | {norm(z.materials[t][0]) for t in mine_t}
    for p in glob.glob(os.path.join(DATA, "**", "*.ZSC"), recursive=True):
        if os.path.samefile(p, ZSC):
            continue
        blob = open(p, "rb").read().lower()
        for q in paths:
            if q.encode("latin-1") in blob:
                sys.exit("ABORT: %s also references %s" % (p, q))
    files = []
    for d in dir_left:
        for f in os.listdir(os.path.join(DATA, *d.split("/"))):
            files.append(("3ddata\\" + d.replace("/", "\\") + "\\" + f).lower())
    stray = sorted(set(files) - paths)
    if stray:
        sys.exit("ABORT: the folders hold files the five do not use: %s" % stray)

    print("would remove %d mesh and %d material record(s), %d folder(s), %d file(s)"
          % (len(mine_m), len(mine_t), len(dir_left), len(files)))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(os.path.join(BACKUP_DIR, "files"), exist_ok=True)
    man = {"cells": {}, "stl": {}, "zsc_orig": "LIST_WEAPON.ZSC", "zsc_sha": "", "folders": []}
    for r in stb_left:
        man["cells"][str(r)] = [c.decode("latin-1") for c in stb.d[r]]
        stb.d[r] = [b"" for _ in stb.d[r]]
    for k in stl_left:
        j = stl.index(k)
        man["stl"][k] = {"id": stl.keys[j][1],
                         "langs": [[f.decode("latin-1") for f in rows[j]] for rows in stl.langs]}
    stl.remove(stl_left)
    for r in obj_left:
        cyl = z.objects[r][0]
        z.objects[r] = (cyl, [], [], b"")
    out = z.without(mine_m, mine_t)

    open(os.path.join(BACKUP_DIR, "LIST_WEAPON.ZSC"), "wb").write(zraw)
    open(STB, "wb").write(stb.to_bytes())
    open(STL, "wb").write(stl.to_bytes())
    open(ZSC, "wb").write(out)
    man["zsc_sha"] = sha(out)
    for d in dir_left:
        dst = os.path.join(BACKUP_DIR, "files", *d.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(os.path.join(DATA, *d.split("/")), dst)
        man["folders"].append(d)
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
    stb, stl = Stb(STB), Stl(STL)
    for r, cells in man["cells"].items():
        stb.d[int(r)] = [c.encode("latin-1") for c in cells]
    for k, e in man["stl"].items():
        stl.append(k, e["id"], *e["langs"][0])
        j = stl.index(k)
        for li, fields in enumerate(e["langs"]):
            stl.langs[li][j] = [f.encode("latin-1") for f in fields]
    open(STB, "wb").write(stb.to_bytes())
    open(STL, "wb").write(stl.to_bytes())
    shutil.copy2(os.path.join(BACKUP_DIR, "LIST_WEAPON.ZSC"), ZSC)
    for d in man["folders"]:
        shutil.move(os.path.join(BACKUP_DIR, "files", *d.split("/")), os.path.join(DATA, *d.split("/")))
    os.remove(MANIFEST)
    print("restored the five rows, their STL keys, the ZSC and %d folder(s)" % len(man["folders"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
