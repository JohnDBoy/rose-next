"""Five tsuki weapons fill the katar, dual-sword and 2H-sword gaps of the endgame ladder
(2026-10-20).

The weapon survey after the ladder pass found, by type and level:

    katar, dual swords   nothing at 220 (the Tsunemoto drop set has 11 types)
    every type           nothing at 225 (the Rose set went to 100)
    2H sword, spear, axe nothing at 235 (the Jotunn drop set has 10 types)

The user's picks from the tsuki client, "for now":

    row  name                     type          ours   tsuki row
    125  Justice Blades           dual swords   220    1450
    424  Frostbitten Knuckles     katar         220    377   (the note said 337: Flame Wand)
    126  Elemental Dual Swords    dual swords   225    451
    425  Stormcrystal Claws       katar         225    427   (tsuki: "Katar 1")
    124  Asmodeus Ritual Blade    2H sword      235    127

**Rows below 1000, written in place** (`--target-row`): an id above 999 can be
dropped (the wide drop encoding) but never granted by a quest nor used by a recipe.
Free rows -- blank, no STL key, empty object, referenced by no STB cell -- in the
retail type blocks: the katar block's 424/425 and the 2H block's 124-126 (the dual
block 431-460 is full; row numbers carry no meaning in code).

All five models and textures are new to us. tsuki is the late NARose lineage with
57-column item tables and its own type numbering (its dual swords are type 251, our
katar), so **nothing is read from its rows but the model, icon, ground-drop model and
gem anchor** (`import-item.py --art-only`). The gem anchor (col 43, a dummy-point
index into the weapon's own model) must be the source's: Frostbitten Knuckles puts it
on dummy 1 of 4, and the template's 4 would point past the model -- no gem glow.

--- the numbers are ours

Every other column is cloned from the type's next tier down (Mirere Katar / Mirere
Blades at 215, Flesh Reaver at 230): type, speed, motion, range, sounds, effects.
The tier columns -- price, quality, level, stat requirement, both bonus slots,
durability, ATK -- are interpolated between that row and the type's next tier up
(Juxtapose Katar / Arcidian Dual Hand at 230, Bahamut at 240), at the new weapon's
level. A bonus slot whose ability differs between the two (Bahamut's crit against
Flesh Reaver's ATK) keeps the lower row's. Effective ATK (ATK + ATK bonus):

    katar   215 367 | 220 378 | 225 388 | 230 398
    dual    215 533 | 220 547 | 225 560 | 230 574
    2H      230 448 | 235 476 | 240 495 (+crit)

The rows are on `weapon-identity-pass.py`'s post-pass scale, so they are in its SKIP.
No shop or drop yet: where they come from is the user's to decide.

    python scripts/import-tsuki-weapons.py --dry-run
    python scripts/import-tsuki-weapons.py
    python scripts/import-tsuki-weapons.py --verify
    python scripts/import-tsuki-weapons.py --restore

Undo in `build/import-tsuki-weapons/`: whole-file originals of the touched tables
(LIST_WEAPON STB/STL/ZSC, LIST_FieldITEM.ZSC, ITEM1.TSI and the icon sheets) with
the hash of what this wrote -- restore refuses a file changed since -- and the
copied art removed. `data/` is gitignored, so this file is the record. Restart the
servers, re-bake the VFS.
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
TSUKI = r"C:\Users\Thomas\Desktop\Testclients\tsuki"
STB = os.path.join(DATA, "STB", "LIST_WEAPON.STB")
BACKUP_DIR = os.path.join(ROOT, "build", "import-tsuki-weapons")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

COL_PRICE, COL_QUALITY, COL_LEVEL, COL_REQ_TYPE, COL_REQ = 5, 8, 20, 21, 22
BONUS = ((23, 24, 25), (26, 27, 28))          # (condition, ability, amount) x2
COL_DURABILITY, COL_ATK, COL_GEM = 29, 35, 43

# row: (tsuki row, level, lower tier row = template, upper tier row, name, description)
WEAPONS = {
    125: (1450, 220, 1414, 1378, "Justice Blades",
           "Twin violet sickles with a verdict etched along each edge. They pass "
           "sentence from both sides at once."),
    424: (377, 220, 1411, 1377, "Frostbitten Knuckles",
           "Black iron claws grown over with ice that never melts. The cold reaches "
           "the wound before the steel does."),
    126: (451, 225, 1414, 1378, "Elemental Dual Swords",
           "A molten blade and a frozen one, forged to be swung together. Neither "
           "hand ever strikes the same way twice."),
    425: (427, 225, 1411, 1377, "Stormcrystal Claws",
           "Gilded talons set with crystals that crackle with caught lightning. "
           "Every strike lands with a flash."),
    124: (127, 235, 1370, 1389, "Asmodeus Ritual Blade",
           "A greatsword carved for a rite nobody should finish. It is heavier "
           "than it looks, and it looks heavy."),
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def touched_files():
    res = os.path.join(DATA, "CONTROL", "RES")
    return ([STB, os.path.join(DATA, "STB", "LIST_WEAPON_S.STL"),
             os.path.join(DATA, "WEAPON", "LIST_WEAPON.ZSC"),
             os.path.join(DATA, "ITEM", "LIST_FieldITEM.ZSC"),
             os.path.join(res, "ITEM1.TSI")] + sorted(glob.glob(os.path.join(res, "icon5*.dds"))))


def tier_cells(w, row):
    """{col: str} for one new weapon: the tier columns interpolated on its type's ladder."""
    _src, lv, lo, hi, _n, _d = WEAPONS[row]
    llv, hlv = w.i(lo, COL_LEVEL), w.i(hi, COL_LEVEL)
    t = (lv - llv) / float(hlv - llv)

    def lerp(c):
        return w.i(lo, c) + (w.i(hi, c) - w.i(lo, c)) * t

    out = {COL_LEVEL: str(lv), COL_REQ_TYPE: w.s(lo, COL_REQ_TYPE).strip(),
           COL_PRICE: str(int(round(lerp(COL_PRICE) / 50.0)) * 50),
           COL_QUALITY: str(int(round(lerp(COL_QUALITY)))),
           COL_REQ: str(int(round(lerp(COL_REQ)))),
           COL_DURABILITY: str(int(round(lerp(COL_DURABILITY)))),
           COL_ATK: str(int(round(lerp(COL_ATK))))}
    for cond, ab, amt in BONUS:
        a = w.s(lo, ab).strip()
        out[cond] = w.s(lo, cond).strip()
        out[ab] = a
        if a and a == w.s(hi, ab).strip():
            out[amt] = str(int(round(lerp(amt))))
        else:
            out[amt] = w.s(lo, amt).strip()
    return out


def tsuki_gem(src):
    s = Stb(os.path.join(TSUKI, "3Ddata", "STB", "LIST_WEAPON.STB"))
    return s.s(src, COL_GEM).strip()


def import_one(row, dry):
    src, lv, lo, _hi, name, desc = WEAPONS[row]
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
           "--source", TSUKI, "--source-row", str(src), "--target-row", str(row), "--art-only",
           "--template-row", str(lo), "--name", name, "--desc", desc,
           "--copy-icon", "--copy-field-model"]
    if dry:
        cmd.append("--dry-run")
    env = dict(os.environ, PYTHONIOENCODING="utf-8:replace")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check(w):
    bad = []
    z = Zsc(os.path.join(DATA, "WEAPON", "LIST_WEAPON.ZSC"))
    for row, (src, lv, lo, hi, name, _d) in WEAPONS.items():
        if w.s(row, 0).strip() != name:
            bad.append("row %d: name %r, want %r" % (row, w.s(row, 0), name))
            continue
        for c, v in tier_cells_frozen(row).items():
            if w.s(row, c).strip() != v:
                bad.append("%s: col %d %r, want %r" % (name, c, w.s(row, c), v))
        for c in (4, 33, 34, 36, 38, 39, 40, 41, 42):
            if c == 34 and row == 124:
                continue           # its own stance column: asmodeus-stance.py owns it
            if w.s(row, c) != w.s(lo, c):
                bad.append("%s: col %d differs from its template's" % (name, c))
        if w.s(row, COL_GEM).strip() != tsuki_gem(src):
            bad.append("%s: gem anchor %r, tsuki's %r" % (name, w.s(row, COL_GEM), tsuki_gem(src)))
        o = z.objects[row] if row < len(z.objects) else None
        if not o or not o[1]:
            bad.append("%s: no model" % name)
            continue
        gem = int(tsuki_gem(src) or 0)
        if gem >= len(o[2]):
            bad.append("%s: gem anchor %d past the model's %d dummies" % (name, gem, len(o[2])))
        for m, t, _p in o[1]:
            for p in (z.meshes[m], z.materials[t][0]):
                f = os.path.join(DATA, *p.decode("latin-1").replace("/", "\\").split("\\")[1:])
                if not os.path.isfile(f):
                    bad.append("%s: missing %s" % (name, p.decode("latin-1")))
    return bad


_FROZEN = {}


def tier_cells_frozen(row):
    """The tier cells as planned on the first run (the manifest), so --verify keeps
    meaning something if a neighbour row is retuned later."""
    if not _FROZEN and os.path.isfile(MANIFEST):
        man = json.load(open(MANIFEST))
        _FROZEN.update({int(r): {int(c): v for c, v in cells.items()}
                        for r, cells in man.get("plan", {}).items()})
    return _FROZEN.get(row, {})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.restore:
        return restore()

    w = Stb(STB)
    if a.verify:
        bad = check(w) if os.path.isfile(MANIFEST) else ["not applied"]
        print("%d problem(s)%s" % (len(bad), (":\n  " + "\n  ".join(bad[:20])) if bad else ""))
        if not bad:
            print("ALL CHECKS PASSED -- the five tsuki weapons are in place.")
        return 1 if bad else 0

    if os.path.isfile(MANIFEST):
        print("already applied (--verify to check, --restore to undo)")
        return 0
    for row in WEAPONS:
        if any(c.strip() for c in w.d[row]):
            sys.exit("ABORT: LIST_WEAPON row %d is not blank (%r)" % (row, w.s(row, 0)))
    plan = {row: tier_cells(w, row) for row in WEAPONS}
    for row, cells in plan.items():
        name = WEAPONS[row][4]
        atk = int(cells[COL_ATK]) + (int(cells[25]) if cells[24] == "18" else 0)
        print("  %d %-22s lv%s ATK %s (effective %d) req %s  bonus %s:%s %s:%s  gem %s"
              % (row, name, cells[COL_LEVEL], cells[COL_ATK], atk, cells[COL_REQ],
                 cells[24], cells[25], cells[27], cells[28], tsuki_gem(WEAPONS[row][0])))

    man = {"plan": {str(r): {str(c): v for c, v in cells.items()} for r, cells in plan.items()},
           "sha": {}, "copied": []}
    if not a.dry_run:
        os.makedirs(os.path.join(BACKUP_DIR, "orig"), exist_ok=True)
        for f in touched_files():
            rel = os.path.relpath(f, DATA)
            dst = os.path.join(BACKUP_DIR, "orig", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(f, dst)
        man["orig"] = [os.path.relpath(f, DATA) for f in touched_files()]

    for row in sorted(WEAPONS):
        rc, out = import_one(row, a.dry_run)
        if rc:
            print("  FAILED %d %s\n%s" % (row, WEAPONS[row][4], out.strip()[-800:]))
            if not a.dry_run:
                json.dump(man, open(MANIFEST, "w"), indent=1)
                print("stopped; --restore puts everything back")
            return 1
        man["copied"] += [ln.split(":", 1)[1].strip() for ln in out.splitlines()
                          if ln.startswith("copied:")]
        print("  %s %d %s" % ("would import" if a.dry_run else "imported", row, WEAPONS[row][4]))
    for b in glob.glob(os.path.join(DATA, "**", "*.bak*"), recursive=True):
        os.makedirs(os.path.join(BACKUP_DIR, "bak"), exist_ok=True)   # pack.ps1 refuses a .bak
        shutil.move(b, os.path.join(BACKUP_DIR, "bak", os.path.basename(b)))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    w = Stb(STB)
    for row, cells in plan.items():
        if w.s(row, 0).strip() != WEAPONS[row][4]:
            sys.exit("ABORT: row %d is %r after the import" % (row, w.s(row, 0)))
        cells = dict(cells)
        cells[COL_GEM] = tsuki_gem(WEAPONS[row][0])
        for c, v in cells.items():
            w.set(row, c, v.encode("latin-1"))
    open(STB, "wb").write(w.to_bytes())
    for f in touched_files():
        man["sha"][os.path.relpath(f, DATA)] = sha(f)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    bad = check(Stb(STB))
    print("%d problem(s)%s" % (len(bad), (":\n  " + "\n  ".join(bad[:20])) if bad else ""))
    return 1 if bad else 0


def restore():
    if not os.path.isfile(MANIFEST):
        print("nothing to restore")
        return 0
    man = json.load(open(MANIFEST))
    for rel, digest in man["sha"].items():
        cur = os.path.join(DATA, rel)
        if os.path.isfile(cur) and sha(cur) != digest:
            sys.exit("ABORT: %s changed since this import -- restore by hand" % rel)
    for rel in man.get("orig", []):
        shutil.copy2(os.path.join(BACKUP_DIR, "orig", rel), os.path.join(DATA, rel))
    for rel in man["copied"]:
        p = os.path.join(DATA, *rel.replace("/", "\\").split("\\")[1:])
        if os.path.isfile(p):
            os.remove(p)
    os.remove(MANIFEST)
    print("restored %d file(s), removed %d copied asset(s)" % (len(man.get("orig", [])),
                                                           len(man["copied"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
