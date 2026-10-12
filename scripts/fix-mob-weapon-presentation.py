"""Fill a blank mob weapon row's hit effect and sounds from a donor row.

A monster that equips a weapon (LIST_NPC col 5/6) presents its normal attack
through the *weapon* row: LIST_WEAPON col 39 (hit effect, a LIST_EFFECT row),
40 (swing sound, FILE_SOUND) and 42 (hit sound, LIST_HITSOUND). The NPC-level
fallbacks -- LIST_NPC col 33 hand-hit effect, col 31 attack sound -- apply only
when the monster has NO weapon. So a mob weapon row whose presentation columns
are empty is worse than no weapon at all: the damage digit appears and nothing
else does, no impact and no sound (see the mob-attack-presentation notes; the
Karkia Revived Quarantine Officer's 1137 was the first, repaired inside
import-karkia.py).

Moon Sister Inguz (654) is the second: her staff, weapon 1130
(mob_melendino01.zms), is blank in our table and in every dump we own (RoseZA,
ruff carry only the model path). Melendino 1473 shares the row. The donor is
1143, the Sikuku Jailer's staff: LIST_EFFECT 141 (the two-handed blunt impact
family), swing sound 63, hit sound 5 -- the most common triple on our mob
weapon rows (8 of 36 in the 1100 band).

    python scripts/fix-mob-weapon-presentation.py --dry-run
    python scripts/fix-mob-weapon-presentation.py
    python scripts/fix-mob-weapon-presentation.py --verify
    python scripts/fix-mob-weapon-presentation.py --restore

Only rows whose presentation columns are ALL blank are touched. Backups go to
build/mob-weapon-presentation/ (never a .bak beside the STB: pack.ps1 errors on
it). `data/` is gitignored, so this file is the record.
"""

import argparse
import base64
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_WEAPON.STB")
BACKUP_DIR = os.path.join(REPO, "build", "mob-weapon-presentation")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

PRESENTATION_COLS = (38, 39, 40, 41, 42)   # bullet fx, hit fx, swing snd, fire snd, hit snd
DONOR = {
    1130: 1143,   # Moon Sister Inguz / Melendino staff <- Sikuku Jailer staff (141 / 63 / 5)
}


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    finally:
        sys.argv = saved
    return m


import rosedata as oro  # the shared data layer (was import-oro.py)


def plan(stb):
    """[(row, donor, {col: value})] for rows still blank; problems as strings."""
    out, problems = [], []
    for row, donor in sorted(DONOR.items()):
        if row >= stb.rows or donor >= stb.rows:
            problems.append("row %d or donor %d past the table (%d rows)" % (row, donor, stb.rows))
            continue
        cur = {c: stb.get(row, c).strip() for c in PRESENTATION_COLS}
        want = {c: stb.get(donor, c).strip() for c in PRESENTATION_COLS}
        if not any(want.values()):
            problems.append("donor %d has no presentation columns itself" % donor)
            continue
        if all(cur[c] == want[c] for c in PRESENTATION_COLS):
            continue                                  # already applied
        if any(cur.values()):
            problems.append("row %d is not blank (%s) -- not a repair target" % (row, cur))
            continue
        out.append((row, donor, want))
    return out, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        open(STB, "wb").write(base64.b64decode(man["original"]))
        os.remove(MANIFEST)
        print("restored LIST_WEAPON.STB")
        return 0

    original = open(STB, "rb").read()
    stb = oro.Stb(STB)
    if stb.to_bytes() != original:
        print("ABORT: the STB writer does not round-trip this file byte-for-byte")
        return 1
    todo, problems = plan(stb)
    for p in problems:
        print("   " + p)

    if a.verify:
        if todo or problems:
            print("VERIFY FAILED: %d row(s) still blank, %d problem(s)" % (len(todo), len(problems)))
            return 1
        print("ALL CHECKS PASSED -- every DONOR row carries its presentation columns.")
        return 0
    if problems:
        print("ABORT, unresolved.")
        return 1
    if not todo:
        print("nothing to do -- every DONOR row already repaired.")
        return 0
    for row, donor, want in todo:
        print("   LIST_WEAPON %d <- %d : %s" % (row, donor,
              ", ".join("col %d = %s" % (c, v.decode()) for c, v in sorted(want.items()) if v)))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.isfile(MANIFEST):
        json.dump({"original": base64.b64encode(original).decode("ascii"),
                   "rows": {str(r): d for r, d, _ in todo}}, open(MANIFEST, "w"), indent=1)
    for row, _donor, want in todo:
        for c, v in want.items():
            stb.set(row, c, v)
    open(STB, "wb").write(stb.to_bytes())
    print("wrote LIST_WEAPON.STB (backup in %s)" % BACKUP_DIR)

    todo2, problems2 = plan(oro.Stb(STB))
    if todo2 or problems2:
        print("VERIFY FAILED after write")
        return 1
    print("verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
