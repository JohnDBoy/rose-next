"""Make the Frostworm line's breath land when it is breathed.

Weapon 1094 ("Frostworm ranged attack") fires LIST_EFFECT 451 -> FILE_EFFECT 1306
``_smoke_firing_01.eft``: an invisible homing carrier (``_UNBULLET_01.ZMS`` with
``_BLACK_01.DDS``, the same nothing the Evil Fairy's gem rode on) trailing a
faint additive world-space smoke. The visible attack is the breath the monster
plays itself; the bullet only times the damage digit (``presentation_kind``
ProjectileImpact waits for the impact).

Col 15 (speed) is 1000 cm/s -- the only 1000 cm/s direction bullet in the table,
and the speed the Fairy's carrier had before ``fix-evil-fairy-bullet.py``. Over
the 15 m attack range that is 1.5 s of flight with nothing on screen, and a
running player (6-9 m/s) is barely gained on, so the hit lands when they stop.
Alpha report 2026-10-30: the worm breathes, no projectile, the hit comes later.
The log that day (attacker 1133) has swing-to-impact 3 s on three swings -- one
of them landing the second the avatar stopped -- and 7 s on a fourth while the
avatar ran. Every hit was a real bullet ``Hitted()``; no fallback or sweep fired.
The "heal-in-flight guard" lines beside them are a symptom: the regen ticks the
server sent during the flight were newer than the late hit's ``hp_after``.

The fix is the official one: 667 and 668 (Rednim) ship row 451 at 7000 cm/s,
every other cell identical (Jrose still has 1000). The hit then lands 0.2 s
after the fire frame at full range. Seen in our table before (row 279 is 7000).

Row 451 is used by weapon 1094 only, and no LIST_SKILL row; the server never
reads bullet speed (it applies the damage at swing start). Weapon 1094 arms
eight monsters, all fixed by the one cell: FrostWorm 361, Elder FrostWorm 362,
Basilisk Captain 372, Little FrostWorm 1466, Frozen Drake 1467, Mega Drake 1468,
Deadly Drake Alpha 2699, Deadly Drake 2729.

    python scripts/fix-frostworm-bullet.py --dry-run
    python scripts/fix-frostworm-bullet.py
    python scripts/fix-frostworm-bullet.py --verify
    python scripts/fix-frostworm-bullet.py --restore

Client-only data: re-bake the VFS. Undo is per cell; backup in
build/frostworm-bullet/.
"""

import argparse
import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, ".."))
EFFECT_STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_EFFECT.STB")
BACKUP_DIR = os.path.join(REPO, "build", "frostworm-bullet")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

EFFECT_ROW = 451
SPEED_COL = 15            # EFFECT_BULLET_SPEED
BULLET_COL = 11           # EFFECT_BULLET_NORMAL
BULLET_FILE = 1306        # _smoke_firing_01.eft
SPEED_FROM, SPEED_TO = 1000, 7000


def plan(stb):
    """[(row, col, old, new)] still to apply; raises on a state not seen in review."""
    if stb.i(EFFECT_ROW, BULLET_COL) != BULLET_FILE:
        raise SystemExit("ABORT: LIST_EFFECT %d col %d is %d, expected %d (_smoke_firing_01.eft)"
                         % (EFFECT_ROW, BULLET_COL, stb.i(EFFECT_ROW, BULLET_COL), BULLET_FILE))
    cur = stb.i(EFFECT_ROW, SPEED_COL)
    if cur == SPEED_TO:
        return []
    if cur != SPEED_FROM:
        raise SystemExit("ABORT: LIST_EFFECT %d col %d is %d, expected %d or %d"
                         % (EFFECT_ROW, SPEED_COL, cur, SPEED_FROM, SPEED_TO))
    return [(EFFECT_ROW, SPEED_COL, stb.get(EFFECT_ROW, SPEED_COL), str(SPEED_TO))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    original = open(EFFECT_STB, "rb").read()
    stb = Stb(EFFECT_STB)
    if stb.to_bytes() != original:
        print("ABORT: the STB writer does not round-trip LIST_EFFECT byte-for-byte")
        return 1

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        for key, rec in man["stb"].items():
            r, c = map(int, key.split(","))
            if stb.get(r, c) != rec["new"].encode():
                print("ABORT: LIST_EFFECT %d col %d changed since this script wrote it" % (r, c))
                return 1
            stb.set(r, c, base64.b64decode(rec["old"]))
        open(EFFECT_STB, "wb").write(stb.to_bytes())
        os.remove(MANIFEST)
        print("restored LIST_EFFECT %d col %d" % (EFFECT_ROW, SPEED_COL))
        return 0

    todo = plan(stb)
    if a.verify:
        if todo:
            print("VERIFY FAILED: bullet %d still at %d cm/s" % (EFFECT_ROW, SPEED_FROM))
            return 1
        print("ALL CHECKS PASSED -- bullet %d at %d cm/s." % (EFFECT_ROW, SPEED_TO))
        return 0
    if not todo:
        print("nothing to do -- already applied.")
        return 0
    for r, c, _old, _new in todo:
        print("   LIST_EFFECT %d col %d (bullet speed): %d -> %d" % (r, c, SPEED_FROM, SPEED_TO))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"stb": {}}
    for r, c, old, new in todo:
        man["stb"]["%d,%d" % (r, c)] = {"old": base64.b64encode(old).decode("ascii"), "new": new}
        stb.set(r, c, new)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    open(EFFECT_STB, "wb").write(stb.to_bytes())
    print("written (undo data in %s)" % BACKUP_DIR)

    if plan(Stb(EFFECT_STB)):
        print("VERIFY FAILED after write")
        return 1
    print("verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
