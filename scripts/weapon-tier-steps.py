"""Even out the endgame weapon steps (2026-10-26): the 215 and 230 tiers get real ATK
steps over the tier below, and the two lv225 tsuki weapons join the 220 tier.

The user's rules: "215 should be above 210, 230 should be above 220, the level 225
weapons should fit into a tier -- all while respecting weapon identity".

Effective ATK (ATK + an ATK bonus line) per type before this pass, 2H sword:

    210 Warmaster 403 | 215 Mirere 411 | 220 Dairo 444 | 230 Flesh Reaver 448 | 235 Primal 471

Every type was already ascending once the bonus line is counted, but by +5..10 from
210 to 215 and +2..9 from 220 to 230 (then +25 to 235): the 215 Mirere set and the 230
line (Arcidian + the red dungeon set) were not worth the level.

--- the steps

Each type is placed between its **own** neighbours, by level, on effective ATK:

    215 = halfway between the type's 210 and 220 weapons
    230 = two thirds of the way from its 220 weapon to its 235 (the dinosaur set)

so the identity pass's type ratios carry over from the neighbours (a mace stays a
mace's distance above a 2H sword) and speed, quality, the bonus lines and everything
else stay as they are -- only ATK (col 35) moves. A 215 weapon already above its
midpoint is never lowered (staff, wand and katar: their +30 ATK line puts them there).
The red set gets the same ATK as its Arcidian twin, as before. 2H sword reads Primal
Cleave at 235, not Asmodeus (a side pick at that tier).

    type      215 before > after      230 before > after   (effective)
    2H        411 > 424               448 > 462
    dual      533 > 538               574 > 588
    katar     367 (kept)              398 > 405

--- the 225 pair -> 220 (the user's pick, over 230 or a future 225 tier)

Elemental Dual Swords (126) and Stormcrystal Claws (425) take the tier columns of
their 220 partners from the same tsuki import, Justice Blades (125) and Frostbitten
Knuckles (424): price, quality, level, stat requirement, both bonus slots, durability,
ATK. Two looks per type at 220 for dual and katar, same stats. Still no shop or drop.

    python scripts/weapon-tier-steps.py --dry-run
    python scripts/weapon-tier-steps.py
    python scripts/weapon-tier-steps.py --verify
    python scripts/weapon-tier-steps.py --restore

The plan is frozen in the manifest on the first run, so a later edit to a neighbour
tier does not move these rows silently. Rows written here are in
`weapon-identity-pass.py`'s SKIP; `weapon-ladder-pass.py` no longer owns the 230
line's ATK and `import-tsuki-weapons.py --verify` no longer checks 126/425's tier
columns -- restore this pass before restoring either of those. Undo is per cell
(`build/weapon-tier-steps/manifest.json`); `data/` is gitignored, so this file is the
record. Restart the servers (LIST_WEAPON) and re-bake the VFS.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_WEAPON.STB")
BACKUP_DIR = os.path.join(REPO, "build", "weapon-tier-steps")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

COL_TYPE, COL_LEVEL, COL_ATK = 4, 20, 35
AT_LEVEL, AT_ATK = "31", "18"
BONUS = ((24, 25), (27, 28))                 # (ability, amount) x2
# price, quality, required level, stat requirement (type, amount), both bonus slots,
# durability, ATK -- as weapon-ladder-pass.py
TIER_COLS = (5, 8, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 35)

# type: (210, 215 Mirere, 220, 230 Arcidian line, 230 red set, 235 dinosaur set)
LADDER = {
    211: (27, 1381, 1426, 1368, 1462, 908),      # 1H sword
    212: (58, 1384, 1427, 1369, 1467, 915),      # 1H mace
    221: (128, 1387, 1428, 1370, 1461, 926),     # 2H sword
    222: (187, 1390, 1429, 1371, 1457, 939),     # spear
    223: (154, 1393, 1430, 1372, 1465, 932),     # axe
    231: (229, 1396, 1431, 1373, 1460, 947),     # bow
    232: (259, 1399, 1432, 1374, 1464, 959),     # gun
    233: (288, 1402, 1433, 1424, 1456, 966),     # launcher
    241: (326, 1405, 1434, 1375, 1463, 974),     # staff
    242: (358, 1408, 1435, 1376, 1459, 982),     # wand
    251: (426, 1411, 424, 1377, 1458, 990),      # katar
    252: (452, 1414, 125, 1378, 1466, 999),      # dual swords
    271: (80, 1417, 1436, 1379, 1468, 950),      # crossbow
}
LEVELS = (210, 215, 220, 230, 230, 235)
# 225 row -> its 220 partner
TO_220 = {126: 125, 425: 424}


def cell(w, r, c):
    return w.get(r, c).decode("latin-1").strip()


def num(w, r, c):
    v = cell(w, r, c)
    return int(v) if v.lstrip("-").isdigit() else 0


def level(w, r):
    return num(w, r, COL_LEVEL) if cell(w, r, 19) == AT_LEVEL else 0


def bonus_atk(w, r):
    return sum(num(w, r, amt) for ab, amt in BONUS if cell(w, r, ab) == AT_ATK)


def eff(w, r):
    return num(w, r, COL_ATK) + bonus_atk(w, r)


def plan_cells(w):
    """{(row, col): str} from the live values."""
    out = {}
    for wtype, rows in LADDER.items():
        for r, lv in zip(rows, LEVELS):
            if num(w, r, COL_TYPE) != wtype or level(w, r) != lv:
                sys.exit("ABORT: row %d (%s) is not type %d at level %d"
                         % (r, cell(w, r, 0), wtype, lv))
        r210, r215, r220, r230, red, r235 = rows
        want = round((eff(w, r210) + eff(w, r220)) / 2.0)
        out[(r215, COL_ATK)] = str(max(num(w, r215, COL_ATK), want - bonus_atk(w, r215)))
        want = round(eff(w, r220) + (eff(w, r235) - eff(w, r220)) * (230 - 220) / (235 - 220))
        for r in (r230, red):
            out[(r, COL_ATK)] = str(want - bonus_atk(w, r))
    for row, partner in TO_220.items():
        if level(w, row) not in (220, 225) or num(w, row, COL_TYPE) != num(w, partner, COL_TYPE):
            sys.exit("ABORT: row %d (%s) is not a lv225 %d" % (row, cell(w, row, 0),
                                                             num(w, partner, COL_TYPE)))
        for c in TIER_COLS:
            out[(row, c)] = cell(w, partner, c)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    w = Stb(STB)
    if w.to_bytes() != open(STB, "rb").read():
        sys.exit("ABORT: LIST_WEAPON does not round-trip")
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}, "plan": {}}

    if a.restore:
        if not man["cells"]:
            print("nothing to restore")
            return 0
        for key, old in man["cells"].items():
            r, c = map(int, key.split(","))
            w.set(r, c, old.encode("latin-1"))
        open(STB, "wb").write(w.to_bytes())
        os.remove(MANIFEST)
        print("restored %d cell(s)" % len(man["cells"]))
        return 0

    if man["plan"]:
        plan = {tuple(map(int, k.split(","))): v for k, v in man["plan"].items()}
    else:
        plan = plan_cells(w)
    todo = {k: v for k, v in plan.items() if cell(w, *k) != v}

    def after(r, c):
        return plan.get((r, c), cell(w, r, c))

    def eff_after(r):
        return int(after(r, COL_ATK)) + sum(int(after(r, amt) or 0) for ab, amt in BONUS
                                            if after(r, ab) == AT_ATK)

    print("effective ATK      210   215 now > new     220   230 now > new     235")
    for wtype, (r210, r215, r220, r230, red, r235) in LADDER.items():
        print("   %-12s  %5d   %5d > %-5d   %5d   %5d > %-5d   %5d"
              % (cell(w, r220, 0)[:12], eff(w, r210), eff(w, r215), eff_after(r215),
                 eff(w, r220), eff(w, r230), eff_after(r230), eff(w, r235)))
        if eff_after(red) != eff_after(r230):
            print("      (red twin %s: %d)" % (cell(w, red, 0), eff_after(red)))
    for row, partner in TO_220.items():
        print("   %s -> lv%s, ATK %s (as %s)" % (cell(w, row, 0), after(row, COL_LEVEL),
                                               after(row, COL_ATK), cell(w, partner, 0)))
    print("cells to change: %d" % len(todo))

    if a.verify:
        bad = ["row %d col %d: %r, expected %r" % (r, c, cell(w, r, c), v)
               for (r, c), v in todo.items()]
        for wtype, rows in LADDER.items():
            steps = [eff(w, r) for r in rows]
            if not (steps[0] < steps[1] < steps[2] < steps[3] < steps[5]):
                bad.append("type %d does not ascend: %s" % (wtype, steps))
        if bad:
            print("\n".join("   " + b for b in bad[:20]))
            print("VERIFY FAILED")
            return 1
        print("ALL CHECKS PASSED -- the weapon tier steps are in place.")
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    man["plan"] = {"%d,%d" % k: v for k, v in plan.items()}
    for (r, c), v in todo.items():
        man["cells"].setdefault("%d,%d" % (r, c), cell(w, r, c))
        w.set(r, c, v.encode("latin-1"))
    open(STB, "wb").write(w.to_bytes())
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("wrote %d cell(s) (undo: --restore). Restart the servers and re-bake the VFS."
          % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
