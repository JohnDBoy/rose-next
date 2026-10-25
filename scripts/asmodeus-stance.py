"""Give the Asmodeus Ritual Blade (LIST_WEAPON 124) its own idle, walk and run
(2026-10-20).

tsuki animates every two-handed sword with its own stance -- `THS_STAND` (+ a female
`THS_STAND_F1`), `THS_WALK`, `THS_RUN` -- where we use the retail `twoswd_*` set; its
attacks are the retail ones. The user liked that stance on the Asmodeus Ritual Blade
(import-tsuki-weapons.py) and wanted it for that blade alone, so it feels unique.

**A weapon's animations are one column of TYPE_MOTION**: LIST_WEAPON col 34 is the
column index (`WEAPON_MOTION_TYPE`), every row an action (stop, walk, run, attacks,
skills ...), every cell a FILE_MOTION row (`FILE_MOTION(type, action)`, read by the
client's `CObjAVT::Get_MOTION` and the server's). So this adds **column 21, "Asmodeus
Blade"**: a copy of column 5 (two-handed sword) with only rows 0/1 (stop 1 and 2, both
`THS_STAND`, as tsuki has them), 2 (walk) and 3 (run) replaced. Attacks, skills, the
battle stance and sitting stay the 2H sword's, so swing timing and every skill clip
are unchanged on the client, the server and the combat sim. A new column rather than
one of the unused ones (2, 4, 13, 17-19): "Shield" and "Empty Skill" may mean
something to code, and a fresh column means nothing else. `rosefmt.stb.Stb.add_column`
rebuilds the header (proved byte-exact against all 83 parsed shipped headers).

The clips are tsuki's files, copied as they are. The male clips drive 21 bone channels
against our 22 -- the same mismatch 668's Voltage Crush clips have, which plays fine --
and a blank female file falls back to the male clip (`CMotionLIST::IDX_GetMOTION`),
which is how tsuki plays its walk and run on women too.

    python scripts/asmodeus-stance.py --dry-run
    python scripts/asmodeus-stance.py
    python scripts/asmodeus-stance.py --verify
    python scripts/asmodeus-stance.py --restore

Undo in `build/asmodeus-stance/`: whole-file originals of FILE_MOTION and TYPE_MOTION
with the hash of what this wrote, LIST_WEAPON's one cell, and the copied clips. The
server reads both motion tables: restart it, and re-bake the VFS.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

DATA = os.path.join(ROOT, "data", "3DDATA")
TSUKI_MOTION = r"C:\Users\Thomas\Desktop\Testclients\tsuki\3Ddata\MOTION\AVATAR"
FILE_MOTION = os.path.join(DATA, "STB", "FILE_MOTION.STB")
TYPE_MOTION = os.path.join(DATA, "STB", "TYPE_MOTION.STB")
WEAPON = os.path.join(DATA, "STB", "LIST_WEAPON.STB")
BACKUP_DIR = os.path.join(ROOT, "build", "asmodeus-stance")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

BLADE, BLADE_NAME, COL_MOTION = 124, "Asmodeus Ritual Blade", 34
BASE_TYPE, COLUMN_NAME = 5, "Asmodeus Blade"
CLIP_DIR = "3DDATA\\MOTION\\AVATAR\\"
# FILE_MOTION rows to add: (label, male clip, female clip or "")
CLIPS = [("ths stand", "THS_STAND.ZMO", "THS_STAND_F1.ZMO"),
         ("ths walk", "THS_WALK.ZMO", ""),
         ("ths run", "THS_RUN.ZMO", "")]
# TYPE_MOTION action row -> index into CLIPS
ACTIONS = {0: 0, 1: 0, 2: 1, 3: 2}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def find_rows(fm):
    """FILE_MOTION rows already holding our clips, by male path."""
    want = {CLIP_DIR + m: i for i, (_l, m, _f) in enumerate(CLIPS)}
    out = {}
    for r in range(fm.rows):
        k = fm.s(r, 0).strip()
        if k in want:
            out[want[k]] = r
    return out


def find_column(tm):
    for c in range(tm.cols):
        if tm.colname(c) == COLUMN_NAME:
            return c
    return None


def check():
    bad = []
    fm, tm, w = Stb(FILE_MOTION), Stb(TYPE_MOTION), Stb(WEAPON)
    rows = find_rows(fm)
    if len(rows) != len(CLIPS):
        bad.append("FILE_MOTION holds %d of the %d clips" % (len(rows), len(CLIPS)))
    for i, (_l, m, f) in enumerate(CLIPS):
        for clip in (m, f):
            if clip and not os.path.isfile(os.path.join(DATA, "MOTION", "AVATAR", clip)):
                bad.append("clip missing: " + clip)
        if i in rows and fm.s(rows[i], 1).strip() != (CLIP_DIR + f if f else ""):
            bad.append("FILE_MOTION %d female cell is %r" % (rows[i], fm.s(rows[i], 1)))
    col = find_column(tm)
    if col is None:
        bad.append("TYPE_MOTION has no %r column" % COLUMN_NAME)
    else:
        for r in range(tm.rows):
            want = str(rows.get(ACTIONS[r], -1)) if r in ACTIONS else tm.s(r, BASE_TYPE).strip()
            if tm.s(r, col).strip() != want:
                bad.append("TYPE_MOTION row %d col %d: %r, want %r" % (r, col, tm.s(r, col), want))
                if len(bad) > 10:
                    break
    if w.s(BLADE, 0).strip() != BLADE_NAME:
        bad.append("LIST_WEAPON %d is %r" % (BLADE, w.s(BLADE, 0)))
    elif col is not None and w.s(BLADE, COL_MOTION).strip() != str(col):
        bad.append("%s motion type %r, want %d" % (BLADE_NAME, w.s(BLADE, COL_MOTION), col))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.restore:
        return restore()
    if a.verify:
        bad = check()
        print("%d problem(s)%s" % (len(bad), (":\n  " + "\n  ".join(bad)) if bad else ""))
        if not bad:
            print("ALL CHECKS PASSED -- the Asmodeus Ritual Blade has its own stance.")
        return 1 if bad else 0
    if os.path.isfile(MANIFEST):
        print("already applied (--verify to check, --restore to undo)")
        return 0

    w = Stb(WEAPON)
    if w.s(BLADE, 0).strip() != BLADE_NAME or w.s(BLADE, COL_MOTION).strip() != str(BASE_TYPE):
        sys.exit("ABORT: LIST_WEAPON %d is %r with motion type %r, expected %s / %d"
                 % (BLADE, w.s(BLADE, 0), w.s(BLADE, COL_MOTION), BLADE_NAME, BASE_TYPE))
    fm, tm = Stb(FILE_MOTION), Stb(TYPE_MOTION)
    for p, t in ((FILE_MOTION, fm), (TYPE_MOTION, tm)):
        if t.to_bytes() != open(p, "rb").read():
            sys.exit("ABORT: %s does not round-trip" % p)
    if find_column(tm) is not None or find_rows(fm):
        sys.exit("ABORT: the column or the clip rows exist without a manifest")
    for _l, m, f in CLIPS:
        for clip in (m, f):
            if clip and os.path.exists(os.path.join(DATA, "MOTION", "AVATAR", clip)):
                sys.exit("ABORT: %s already exists in our data" % clip)

    first = fm.rows
    fm.grow_to(first + len(CLIPS), {first + i: lbl for i, (lbl, _m, _f) in enumerate(CLIPS)})
    for i, (_l, m, f) in enumerate(CLIPS):
        fm.set(first + i, 0, CLIP_DIR + m)
        fm.set(first + i, 1, CLIP_DIR + f if f else "")
    col = tm.add_column(COLUMN_NAME)
    for r in range(tm.rows):
        tm.set(r, col, tm.get(r, BASE_TYPE))
    for r, i in ACTIONS.items():
        tm.set(r, col, str(first + i))
    print("FILE_MOTION rows %d-%d: %s" % (first, first + len(CLIPS) - 1,
                                          ", ".join(m for _l, m, _f in CLIPS)))
    print("TYPE_MOTION column %d %r: column %d with stop 1/2, walk, run replaced"
          % (col, COLUMN_NAME, BASE_TYPE))
    print("LIST_WEAPON %d %s: motion type %d -> %d" % (BLADE, BLADE_NAME, BASE_TYPE, col))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    for p in (FILE_MOTION, TYPE_MOTION):
        shutil.copy2(p, os.path.join(BACKUP_DIR, os.path.basename(p)))
    copied = []
    for _l, m, f in CLIPS:
        for clip in (m, f):
            if clip:
                shutil.copy2(os.path.join(TSUKI_MOTION, clip),
                             os.path.join(DATA, "MOTION", "AVATAR", clip))
                copied.append(clip)
    open(FILE_MOTION, "wb").write(fm.to_bytes())
    open(TYPE_MOTION, "wb").write(tm.to_bytes())
    old = w.s(BLADE, COL_MOTION)
    w.set(BLADE, COL_MOTION, str(col))
    open(WEAPON, "wb").write(w.to_bytes())
    json.dump({"weapon_cell": old, "copied": copied,
               "sha": {os.path.basename(p): sha(p) for p in (FILE_MOTION, TYPE_MOTION)}},
              open(MANIFEST, "w"), indent=1)
    bad = check()
    print("%d problem(s)%s" % (len(bad), (":\n  " + "\n  ".join(bad)) if bad else ""))
    return 1 if bad else 0


def restore():
    if not os.path.isfile(MANIFEST):
        print("nothing to restore")
        return 0
    man = json.load(open(MANIFEST))
    for p in (FILE_MOTION, TYPE_MOTION):
        if sha(p) != man["sha"][os.path.basename(p)]:
            sys.exit("ABORT: %s changed since this pass wrote it -- restore by hand" % p)
    # Other weapons wear the stance too since 2026-10-25 (Warmaster Sword, 128:
    # replace-210-weapons.py). Removing the column would leave them pointing past
    # TYPE_MOTION.
    col = find_column(Stb(TYPE_MOTION))
    w = Stb(WEAPON)
    others = [r for r in range(w.rows) if r != BLADE and col is not None
              and w.s(r, COL_MOTION).strip() == str(col)]
    if others:
        sys.exit("ABORT: LIST_WEAPON %s also use the stance column %d -- move them back "
                 "to %d first" % (others, col, BASE_TYPE))
    for p in (FILE_MOTION, TYPE_MOTION):
        shutil.copy2(os.path.join(BACKUP_DIR, os.path.basename(p)), p)
    w = Stb(WEAPON)
    w.set(BLADE, COL_MOTION, man["weapon_cell"])
    open(WEAPON, "wb").write(w.to_bytes())
    for clip in man["copied"]:
        p = os.path.join(DATA, "MOTION", "AVATAR", clip)
        if os.path.isfile(p):
            os.remove(p)
    os.remove(MANIFEST)
    print("restored the motion tables, the blade's motion type and removed %d clip(s)"
          % len(man["copied"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
