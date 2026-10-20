"""Two Jrose armour sets join the endgame, and the 220-240 ladder steps every 5 levels
(2026-10-20).

    220  Legendary Crystal                         unchanged
    225  Royal Guardian / Sun Prophet / ...       Egyptian, down from 240
    230  Fighter / Magical / Thief / Gunner       NEW -- the OG cinematic outfits
    235  Legionnaire / Spitfire / Spinosaur ...   up from 230
    240  Fenrir / Eir / Sleipnir / Forseti        NEW -- Jrose's Norse line

The user's survey of Jrose (2026-10-20). **The OG set** is the first-job look of the
original ROSE Online cinematic -- high nostalgia, high value -- and Jrose ships it three
times per class (a level-100 original, a no-level "Replica" and a red "Dark" recolour,
one model): the Replica rows are taken (Fighter 48/50, Magical 78/80, Thief 108/110,
Gunner 138/140; the Fighter helm row is labelled "weak", same art). **The Norse set**
is Jrose's lv210-art second-job line (Fenrir = Champion, Eir = Cleric, Sleipnir =
Raider, Forseti = Artisan; its sisters Thor, Odin, Ullr and Hvedrung sit next to them
and are not taken -- the user picked one per class line, like every 220+ tier here).
Both sets are complete on both sexes and **all art is new** to us (20 + 35 textures by
texture signature). The user's call: OG 230, Norse 240, Egyptian -- "very Oro-coded"
-- lower; the 5-level steps mirror the weapon ladder so no tier holds two looks.

--- the numbers stay on the curve the monsters were tuned against

Every tier is a point on the line from Legendary Crystal (220) to Egyptian's old 240
values, per class and slot, so the curve's ends do not move:

    225 Egyptian      25%  (Soldier set 1006 DEF -- the old Refined Steam)
    230 OG            50%  (1113 -- the old Unit Core)
    235 Legionnaire   its own pieces x line(235)/line(230), so it keeps its trade:
                      more DEF, less RES, slower boots (import-legionnaire-armour.py)
    240 Norse         Egyptian's old 240 values exactly

Derived from the live rows when this was written and frozen below, so `--verify`
keeps meaning something. Price follows the same line; Legionnaire's DEF lands near
Norse's (1318 vs 1324 for the Soldier set) because of its profile -- the step to 240
is mostly RES.

--- import

`import-item.py --art-only` into the blank rows 266-269 (OG) and 270-273 (Norse) of
all four tables, Soldier / Muse / Hawker / Dealer in order -- free in the STB, the STL
and both sex ZSCs. Every column but the model, icon (cropped from Jrose's atlas), name
and description is cloned from the **matching Egyptian piece**: class gate, the
class-stat bonus pair, the body's Max HP, the boots' move speed, quality, weight. Then
level, DEF, RES and price are ours, and **a cap's hair setting (LIST_CAP col 33) is
Jrose's** -- it belongs to the model (how hair shows under it), not to the template.

--- drops

None of the four are sold: the OG set drops from Karkia's lv228-240 field tables and
Norse from its boss tables only (`add-karkia-drops.py`, the user's "boss-level
monsters for now"; more sources are planned). Egyptian keeps its Oro sources
(Fossil Sanctuary, lv225-240, `add-oro-drops.py`), which still fit at 225.

    python scripts/armour-endgame-sets.py --dry-run
    python scripts/armour-endgame-sets.py
    python scripts/armour-endgame-sets.py --verify
    python scripts/armour-endgame-sets.py --restore

Undo in `build/armour-endgame-sets/`: the re-tier is cell-level; the import is
whole-file originals of the touched tables (STB, STL, ZSC, ITEM1.TSI and its sheet)
with the hash of what this wrote -- restore refuses a file changed since -- and the
copied art is removed. `data/` is gitignored, so this file is the record. Afterwards:
`add-dds-mipmaps.py` over the new art if it ships without mips, restart the servers,
re-bake the VFS.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Stb, Zsc  # noqa: E402

DATA = os.path.join(ROOT, "data", "3DDATA")
JROSE = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
BACKUP_DIR = os.path.join(ROOT, "build", "armour-endgame-sets")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

CLASSES = ("Soldier", "Muse", "Hawker", "Dealer")
SLOTS = ("cap", "body", "arms", "foot")
TABLE = {"cap": "LIST_CAP", "body": "LIST_BODY", "arms": "LIST_ARMS", "foot": "LIST_FOOT"}
ZSCS = {"cap": ("LIST_MCAP", "LIST_WCAP"), "body": ("LIST_MBODY", "LIST_WBODY"),
        "arms": ("LIST_MARMS", "LIST_WARMS"), "foot": ("LIST_MFOOT", "LIST_WFOOT")}
COL_PRICE, COL_ICON, COL_LEVEL, COL_DEF, COL_RES, COL_HAIR = 5, 9, 20, 31, 32, 33

EGYPT = {"cap": 989, "body": 916, "arms": 892, "foot": 890}      # + class index
LEGION = {"cap": 262, "body": 262, "arms": 262, "foot": 262}

# (DEF, RES, price) per slot and class, frozen from the live rows on 2026-10-20
EGYPT_225 = {
    "cap": {"Soldier": (247, 61, 315000), "Muse": (158, 121, 315000), "Hawker": (167, 92, 315000), "Dealer": (165, 90, 315000)},
    "body": {"Soldier": (354, 88, 168750), "Muse": (367, 314, 168750), "Hawker": (428, 252, 168750), "Dealer": (419, 250, 168750)},
    "arms": {"Soldier": (222, 55, 315000), "Muse": (121, 51, 315000), "Hawker": (149, 51, 315000), "Dealer": (147, 51, 315000)},
    "foot": {"Soldier": (183, 46, 360450), "Muse": (188, 30, 360450), "Hawker": (192, 24, 360450), "Dealer": (190, 24, 360450)},
}
OG_230 = {
    "cap": {"Soldier": (276, 68, 350000), "Muse": (176, 134, 350000), "Hawker": (186, 103, 350000), "Dealer": (184, 100, 350000)},
    "body": {"Soldier": (386, 96, 187500), "Muse": (400, 343, 187500), "Hawker": (466, 274, 187500), "Dealer": (457, 272, 187500)},
    "arms": {"Soldier": (247, 62, 350000), "Muse": (135, 56, 350000), "Hawker": (166, 56, 350000), "Dealer": (164, 56, 350000)},
    "foot": {"Soldier": (204, 52, 400300), "Muse": (208, 34, 400300), "Hawker": (214, 26, 400300), "Dealer": (212, 26, 400300)},
}
LEGION_235 = {
    "cap": {"Soldier": (329, 58, 385000), "Muse": (209, 116, 385000), "Hawker": (222, 88, 385000), "Dealer": (219, 86, 385000)},
    "body": {"Soldier": (452, 81, 206250), "Muse": (468, 290, 206250), "Hawker": (545, 232, 206250), "Dealer": (535, 230, 206250)},
    "arms": {"Soldier": (295, 53, 385000), "Muse": (161, 48, 385000), "Hawker": (198, 48, 385000), "Dealer": (195, 48, 385000)},
    "foot": {"Soldier": (242, 45, 440150), "Muse": (247, 30, 440150), "Hawker": (254, 22, 440150), "Dealer": (252, 22, 440150)},
}
NORSE_240 = {
    "cap": {"Soldier": (332, 82, 420000), "Muse": (212, 162, 420000), "Hawker": (225, 124, 420000), "Dealer": (221, 121, 420000)},
    "body": {"Soldier": (450, 112, 225000), "Muse": (467, 400, 225000), "Hawker": (544, 320, 225000), "Dealer": (533, 317, 225000)},
    "arms": {"Soldier": (298, 74, 420000), "Muse": (163, 68, 420000), "Hawker": (201, 68, 420000), "Dealer": (197, 68, 420000)},
    "foot": {"Soldier": (244, 62, 480000), "Muse": (250, 40, 480000), "Hawker": (256, 32, 480000), "Dealer": (254, 32, 480000)},
}

# the two imported sets: Jrose row per slot, our first row, names, flavour, the
# texture token every imported model must carry (checked by --verify)
SETS = {
    "OG": {
        "level": 230, "stats": OG_230, "first": 266,
        "src": {"Soldier": {"cap": 48, "body": 50, "arms": 48, "foot": 48},
                "Muse": {"cap": 78, "body": 80, "arms": 78, "foot": 78},
                "Hawker": {"cap": 108, "body": 110, "arms": 108, "foot": 108},
                "Dealer": {"cap": 138, "body": 140, "arms": 138, "foot": 138}},
        "names": {"Soldier": ("Fighter Helm", "Fighter Armor", "Fighter Gauntlets", "Fighter Boots"),
                  "Muse": ("Magical Cap", "Magical Dress", "Magical Gloves", "Magical Shoes"),
                  "Hawker": ("Thief's Hat", "Thief's Clothes", "Thief's Gloves", "Thief's Shoes"),
                  "Dealer": ("Gunner Cap", "Gunner Shirt", "Gunner Gloves", "Gunner Shoes")},
        "desc": {"Soldier": "The plate the first fighters wore out of Junon, remade for the "
                            "end of the road. Everyone knows the silhouette.",
                 "Muse": "The dress of the first Muses, stitched again from the old pattern "
                         "with threads that hold a spell now.",
                 "Hawker": "Cut like the first thieves' gear, light and close, every buckle "
                           "where a quick hand expects it.",
                 "Dealer": "The gunner's outfit from the old days, goggles and all, rebuilt "
                           "to take what the new days throw."},
        "token": {"Soldier": "soldier_", "Muse": "myu", "Hawker": "hawker", "Dealer": "dealer_"},
    },
    "Norse": {
        "level": 240, "stats": NORSE_240, "first": 270,
        "src": {"Soldier": {"cap": 50, "body": 52, "arms": 52, "foot": 52},
                "Muse": {"cap": 83, "body": 83, "arms": 83, "foot": 83},
                "Hawker": {"cap": 110, "body": 112, "arms": 110, "foot": 110},
                "Dealer": {"cap": 140, "body": 142, "arms": 140, "foot": 140}},
        "names": {"Soldier": ("Fenrir Helm", "Fenrir Armor", "Fenrir Gauntlets", "Fenrir Boots"),
                  "Muse": ("Eir Hat", "Eir Coat", "Eir Gloves", "Eir Shoes"),
                  "Hawker": ("Sleipnir Hat", "Sleipnir Coat", "Sleipnir Gloves", "Sleipnir Boots"),
                  "Dealer": ("Forseti Headgear", "Forseti Suit", "Forseti Gloves", "Forseti Boots")},
        "desc": {"Soldier": "Black plate named for the wolf that swallows the sun. It was "
                            "made to be the last thing a monster sees.",
                 "Muse": "White robes of the healer of the old gods, cut for a battlefield "
                         "rather than a temple.",
                 "Hawker": "A long coat for the eight-legged horse: built for whoever gets "
                           "there first and leaves before anyone else.",
                 "Dealer": "The judge's suit, red and exact. Every seam is a ruling and "
                           "none of them is ever appealed."},
        "token": {"Soldier": "champ", "Muse": "cleric", "Hawker": "ladar", "Dealer": "artisan"},
    },
}
SLOT_INDEX = {"cap": 0, "body": 1, "arms": 2, "foot": 3}

# Two Jrose texture names carry a full-width letter (cp932 0x8294 'ｔ', 0x8286 'ｆ'):
# import-item.py's copy step reads paths as ASCII and cannot find them, and the
# client could not open them on a non-Japanese code page anyway. Each has an ASCII
# sibling that says what was meant (DEALER_HAT.ZMS, LV210_ARTISANBOOTS_M_...), so
# the file is copied under that name and the material records repointed.
ASCII_NAMES = {
    b"3DDATA\\AVATAR\\CAP\\dealer_ha\x82\x94.dds":
        b"3DDATA\\AVATAR\\CAP\\DEALER_HAT.DDS",                        # Gunner Cap
    b"3DDATA\\AVATAR\\FOOT\\lv210_artisanboots_\x82\x86_red_0118_cr.dds":
        b"3DDATA\\AVATAR\\FOOT\\LV210_ARTISANBOOTS_F_RED_0118_CR.DDS",  # Forseti Boots (f)
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def stb_path(slot):
    return os.path.join(DATA, "STB", TABLE[slot] + ".STB")


def touched_files():
    out = []
    for slot in SLOTS:
        out += [stb_path(slot), os.path.join(DATA, "STB", TABLE[slot] + "_S.STL")]
        out += [os.path.join(DATA, "AVATAR", z + ".ZSC") for z in ZSCS[slot]]
    res = os.path.join(DATA, "CONTROL", "RES")
    out += [os.path.join(res, "ITEM1.TSI")] + sorted(glob.glob(os.path.join(res, "icon5*.dds")))
    return out


def pieces():
    for setname, s in SETS.items():
        for ci, cls in enumerate(CLASSES):
            for slot in SLOTS:
                d, r, price = s["stats"][slot][cls]
                yield dict(set=setname, cls=cls, slot=slot, row=s["first"] + ci,
                           src=s["src"][cls][slot], tmpl=EGYPT[slot] + ci,
                           name=s["names"][cls][SLOT_INDEX[slot]], desc=s["desc"][cls],
                           level=s["level"], dfn=d, res=r, price=price,
                           token=s["token"][cls])


def retier():
    """{(slot, row, col): str} moving Egyptian to 225 and Legionnaire to 235."""
    out = {}
    for (base, lv, stats) in ((EGYPT, 225, EGYPT_225), (LEGION, 235, LEGION_235)):
        for ci, cls in enumerate(CLASSES):
            for slot in SLOTS:
                d, r, price = stats[slot][cls]
                row = base[slot] + ci
                out.update({(slot, row, COL_LEVEL): str(lv), (slot, row, COL_DEF): str(d),
                            (slot, row, COL_RES): str(r), (slot, row, COL_PRICE): str(price)})
    return out


def jrose_hair(slot, row):
    s = Stb(os.path.join(JROSE, "3Ddata", "STB", "LIST_CAP.STB"), "cp932")
    return s.s(row, COL_HAIR).strip()


def fix_ascii_names(man, dry):
    """Copy the two full-width-named Jrose textures under ASCII names and repoint
    every material record that names them. Returns the number of records moved."""
    def under(root, zpath):
        parts = zpath.decode("latin-1").split("\\")[1:]          # drop "3DDATA"
        return os.path.join(root, *parts)
    moved = 0
    for slot in SLOTS:
        for zn in ZSCS[slot]:
            path = os.path.join(DATA, "AVATAR", zn + ".ZSC")
            z = Zsc(path)
            hit = [i for i, (p, _f) in enumerate(z.materials) if p in ASCII_NAMES]
            for i in hit:
                old, flags = z.materials[i]
                z.materials[i] = (ASCII_NAMES[old], flags)
                src = under(os.path.join(JROSE, "3Ddata"), old)
                dst = under(DATA, ASCII_NAMES[old])
                if not os.path.isfile(dst):
                    if not dry:
                        shutil.copy2(src, dst)
                        man["copied"].append(ASCII_NAMES[old].decode("latin-1"))
                    print("  %s %s <- %s" % ("would copy" if dry else "copied",
                                             ASCII_NAMES[old].decode(), os.path.basename(src)))
            if hit:
                moved += len(hit)
                print("  %s: %d material record(s) renamed to ASCII" % (zn, len(hit)))
                if not dry:
                    open(path, "wb").write(z.without())
    return moved


def import_piece(it, dry):
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"),
           "--type", it["slot"], "--source", JROSE,
           "--source-row", str(it["src"]), "--target-row", str(it["row"]),
           "--art-only", "--template-row", str(it["tmpl"]),
           "--name", it["name"], "--desc", it["desc"],
           "--req-level", str(it["level"]), "--def", str(it["dfn"]),
           "--res", str(it["res"]), "--price", str(it["price"]), "--copy-icon"]
    if dry:
        cmd.append("--dry-run")
    env = dict(os.environ, PYTHONIOENCODING="utf-8:replace")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check(stbs):
    """Problems with the imported rows and the re-tier, as strings."""
    bad = []
    for it in pieces():
        s = stbs[it["slot"]]
        r = it["row"]
        if s.s(r, 0).strip() != it["name"]:
            bad.append("%s %d: name %r" % (it["slot"], r, s.s(r, 0)))
            continue
        for what, col, want in (("level", COL_LEVEL, it["level"]), ("DEF", COL_DEF, it["dfn"]),
                                ("RES", COL_RES, it["res"]), ("price", COL_PRICE, it["price"])):
            if s.i(r, col) != want:
                bad.append("%s: %s %d, want %d" % (it["name"], what, s.i(r, col), want))
        for c in (16, 24, 25, 27, 28, 33 if it["slot"] == "foot" else 16):
            if s.s(r, c) != s.s(it["tmpl"], c):
                bad.append("%s: col %d %r differs from Egyptian's %r"
                           % (it["name"], c, s.s(r, c), s.s(it["tmpl"], c)))
        if it["slot"] == "cap" and s.s(r, COL_HAIR).strip() != jrose_hair("cap", it["src"]):
            bad.append("%s: hair setting %r, Jrose's is %r"
                       % (it["name"], s.s(r, COL_HAIR), jrose_hair("cap", it["src"])))
        for zn in ZSCS[it["slot"]]:
            z = Zsc(os.path.join(DATA, "AVATAR", zn + ".ZSC"))
            o = z.objects[r] if r < len(z.objects) else None
            if not o or not o[1]:
                bad.append("%s: %s has no model" % (it["name"], zn))
                continue
            tex = [z.materials[p[1]][0].decode("latin-1").lower() for p in o[1]]
            if not any(it["token"] in t for t in tex):
                bad.append("%s: %s carries none of %r" % (it["name"], zn, it["token"]))
            for m, t, _p in o[1]:
                for p in (z.meshes[m], z.materials[t][0]):
                    if any(b > 127 for b in p):
                        bad.append("%s: %s names a non-ASCII file %r" % (it["name"], zn, p))
                    elif not os.path.isfile(os.path.join(DATA, *p.decode().replace("/", "\\").split("\\")[1:])):
                        bad.append("%s: %s file missing %s" % (it["name"], zn, p.decode()))
    seen = {}
    for it in pieces():
        key = (it["slot"], stbs[it["slot"]].i(it["row"], COL_ICON))
        if key in seen:
            bad.append("%s: icon shared with %s" % (it["name"], seen[key]))
        seen[key] = it["name"]
    for (slot, row, col), v in retier().items():
        if stbs[slot].s(row, col).strip() != v:
            bad.append("%s %d col %d: %r, want %s" % (TABLE[slot], row, col, stbs[slot].s(row, col), v))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.restore:
        return restore()

    stbs = {slot: Stb(stb_path(slot)) for slot in SLOTS}
    if a.verify:
        bad = check(stbs)
        print("%d problem(s)%s" % (len(bad), (":\n  " + "\n  ".join(bad[:20])) if bad else ""))
        if not bad:
            print("ALL CHECKS PASSED -- OG at 230, Norse at 240, Egyptian 225, Legionnaire 235.")
        return 1 if bad else 0

    todo = [it for it in pieces() if stbs[it["slot"]].s(it["row"], 0).strip() != it["name"]]
    for it in todo:
        if any(c.strip() for c in stbs[it["slot"]].d[it["row"]]):
            sys.exit("ABORT: %s row %d is not blank" % (TABLE[it["slot"]], it["row"]))
    for slot, eg in EGYPT.items():
        if not stbs[slot].s(eg, 0).startswith("Royal Guardian"):
            sys.exit("ABORT: %s %d is %r, not the Egyptian Soldier piece" % (TABLE[slot], eg, stbs[slot].s(eg, 0)))
        if not stbs[slot].s(LEGION[slot], 0).startswith("Legionnaire"):
            sys.exit("ABORT: %s %d is not Legionnaire" % (TABLE[slot], LEGION[slot]))

    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {
        "cells": {}, "orig": {}, "sha": {}, "copied": []}
    if todo and not a.dry_run and not man["orig"]:
        os.makedirs(os.path.join(BACKUP_DIR, "orig"), exist_ok=True)
        for f in touched_files():
            rel = os.path.relpath(f, DATA)
            dst = os.path.join(BACKUP_DIR, "orig", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(f, dst)
            man["orig"][rel] = True

    failed = 0
    for it in todo:
        rc, out = import_piece(it, a.dry_run)
        tag = "would import" if a.dry_run else "imported"
        if rc:
            failed += 1
            print("  FAILED %-5s %d %s\n%s" % (it["slot"], it["row"], it["name"], out.strip()[-800:]))
            break
        man["copied"] += [ln.split(":", 1)[1].strip() for ln in out.splitlines()
                          if ln.startswith("copied:")]
        print("  %s %-5s row %d  %-18s lv%d DEF %3d RES %3d" % (tag, it["slot"], it["row"],
                                                             it["name"], it["level"], it["dfn"], it["res"]))
    for b in glob.glob(os.path.join(DATA, "**", "*.bak*"), recursive=True):
        os.makedirs(os.path.join(BACKUP_DIR, "bak"), exist_ok=True)   # pack.ps1 refuses a .bak
        shutil.move(b, os.path.join(BACKUP_DIR, "bak", os.path.basename(b)))
    if failed:
        json.dump(man, open(MANIFEST, "w"), indent=1)
        print("stopped on a failure; --restore puts everything back")
        return 1
    if not a.dry_run or not todo:
        fix_ascii_names(man, a.dry_run)

    # caps: Jrose's hair setting; then the re-tier
    stbs = {slot: Stb(stb_path(slot)) for slot in SLOTS}
    cells = {}
    for it in pieces():
        if it["slot"] == "cap":
            cells[("cap", it["row"], COL_HAIR)] = jrose_hair("cap", it["src"])
    cells.update(retier())
    changes = {k: v for k, v in cells.items() if stbs[k[0]].s(k[1], k[2]).strip() != v}
    print("re-tier and hair cells to change: %d" % len(changes))
    for (slot, row, col), v in sorted(changes.items()):
        if col == COL_LEVEL:
            print("   %-9s %4d %-26s lv%s -> lv%s" % (TABLE[slot], row, stbs[slot].s(row, 0),
                                                    stbs[slot].s(row, col), v))
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    for (slot, row, col), v in changes.items():
        man["cells"].setdefault("%s,%d,%d" % (slot, row, col), stbs[slot].s(row, col))
        stbs[slot].set(row, col, v.encode("latin-1"))
    for slot in SLOTS:
        if any(k[0] == slot for k in changes):
            open(stb_path(slot), "wb").write(stbs[slot].to_bytes())
    for f in touched_files():
        man["sha"][os.path.relpath(f, DATA)] = sha(f)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    bad = check(stbs)
    print("%d problem(s)%s" % (len(bad), (":\n  " + "\n  ".join(bad[:20])) if bad else ""))
    return 1 if bad else 0


def restore():
    if not os.path.isfile(MANIFEST):
        print("nothing to restore")
        return 0
    man = json.load(open(MANIFEST))
    for rel in man["orig"]:
        cur = os.path.join(DATA, rel)
        if man["sha"].get(rel) and os.path.isfile(cur) and sha(cur) != man["sha"][rel]:
            sys.exit("ABORT: %s changed since this pass wrote it -- restore by hand" % rel)
    for rel in man["orig"]:
        shutil.copy2(os.path.join(BACKUP_DIR, "orig", rel), os.path.join(DATA, rel))
    for rel in man["copied"]:
        p = os.path.join(ROOT, "data", *rel.replace("\\", "/").split("/")[1:]) \
            if rel.lower().startswith("3ddata") else os.path.join(DATA, rel)
        if os.path.isfile(p):
            os.remove(p)
    os.remove(MANIFEST)
    print("restored %d file(s), removed %d copied asset(s)" % (len(man["orig"]), len(man["copied"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
