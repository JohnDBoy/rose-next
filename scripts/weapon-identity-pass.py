"""Weapon identity pass: LIST_WEAPON speed, ATK and quality for play without server.toml's
combat bonuses (2026-10-15).

server.toml gave every player +70 ATK, +80 HIT and +35 attack speed (the original team's
replacement for cleric buffs). That made the early game trivial (a level-1 starter sword
one-shot a choropy) and erased weapon identity (everyone swung at ~0.9 s). The bonuses go
to 0 (move speed stays) and the weapons carry the difference:

- Speed (col 36): one value per weapon type. Swing times for a level-120 character of the
  type's natural class, with its speed passives: katar 0.60 s, dual swords 0.82, spear 0.88,
  1H sword 0.92, gun 0.84, 2H sword 0.96, bow 1.00, 1H mace 1.18, axe 1.20, launcher 1.28
  (today ~0.9 s for nearly everything). Spear fast, axe slow and heavy, 2H in between.
- ATK (col 35): original x SCALE x TYPE_FACTOR x R(level). R is the shared compensation
  curve for the missing +70 ATK, calibrated in the combat simulator so the 2H sword's
  normal-attack DPS is 0.9x today's (with bonuses) from level 70 up and 0.5x at levels
  1-20 (a starter sword now takes 2-3 hits on a choropy). TYPE_FACTOR puts each type's
  normal DPS at its agreed index against the 2H sword (spear 0.98, axe 0.99, 1H sword 0.82,
  1H mace 0.81, katar 0.99, dual swords 1.03, bow 0.86, gun 0.95, launcher 0.92); one
  factor per type, not one per level, so tier-to-tier ups and downs survive -- small
  imbalances are wanted. SCALE 0.95 makes physical classes a little slower than today.
  The gun's factor came out at 0.778 on normal attacks, but the Artisan is a skill class
  and its skills scale with ATK: with the gun-only Artisan build it killed 20-50% slower
  than today. 0.95 puts it a few percent under today (the class sweep), like the rest.
- Accuracy: the weapon's own hit rate. The code change WEAPON_HIT_PER_QUALITY (citem.h,
  0.6 -> 1.4) replaces the +80 HIT; quality (col 8) is nudged x1.10 for the accurate types
  (spear, 1H sword, katar, bow, gun) and x0.90 for the axe. Quality also sets price,
  upgrade cost and crafting odds, which is why the multiplier moved instead of quality.
- Crossbows (the kiting Knight's niche): ATK x SCALE x R(level), and ATK_SPD +29 in the
  first free add slot (cols 23-28), back to about today's swing. Row 1379 has no free slot.

Staffs, wands and dual guns (a test weapon) are untouched. Weapons with no level
requirement (event and quest rows) take the level of the same-type weapon nearest in
original ATK; the GM Sword is skipped. Simulator result (scripts/combatsim, the class
sweep with skills, summons and grinding): second jobs grind at about today's pace with
the bonuses gone, land rates within 3 points of today's.

    python scripts/weapon-identity-pass.py --dry-run
    python scripts/weapon-identity-pass.py
    python scripts/weapon-identity-pass.py --verify
    python scripts/weapon-identity-pass.py --restore

New values are computed from the originals kept in the manifest, so a re-run is a no-op
and a changed table re-applies cleanly. Undo is per cell (build/weapon-identity-pass/) --
never a whole-file copy, which would revert every later script's LIST_WEAPON edits.
`data/` is gitignored, so this file is the record. The server reads LIST_WEAPON: restart
it, and re-bake the VFS for the client.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_WEAPON.STB")
BACKUP_DIR = os.path.join(REPO, "build", "weapon-identity-pass")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

COL_TYPE, COL_QUALITY, COL_ATK, COL_SPEED = 4, 8, 35, 36
AT_LEVEL, AT_ATK_SPD = 31, 24
SCALE = 0.95
# type: (label, speed, ATK factor, quality nudge)
TYPES = {
    221: ("2H sword", 7, 1.000, 1.00),
    222: ("spear", 6, 0.974, 1.10),
    223: ("axe", 10, 1.114, 0.90),
    211: ("1H sword", 6, 1.212, 1.10),
    212: ("1H mace", 9, 1.309, 1.00),
    251: ("katar", 5, 1.001, 1.10),
    252: ("dual swords", 7, 1.065, 1.00),
    231: ("bow", 7, 1.051, 1.10),
    232: ("gun", 6, 0.950, 1.10),       # see the docstring: raised from 0.778
    233: ("launcher", 11, 0.989, 1.00),
}
CROSSBOW, CROSSBOW_ASPD = 271, 29
# R(level): (level, multiplier) knots, linear between them, flat outside
R_KNOTS = [(10, 1.896), (20, 1.384), (56, 1.384), (73, 1.216), (250, 1.000)]
R_FLOOR = 0.3
SKIP = {1380: "GM Sword"}
# Uniques imported after this pass by import-668-uniques.py, authored on the
# post-pass scale: a re-run would take them as originals and scale them twice.
SKIP.update({r: "668 unique" for r in (904, 911, 918, 922, 929, 935, 936, 943, 955,
                                       962, 970, 979, 986, 994, 995)})


def R(level):
    if level <= R_KNOTS[0][0]:
        return R_KNOTS[0][1]
    for (a, ra), (b, rb) in zip(R_KNOTS, R_KNOTS[1:]):
        if level <= b:
            return ra + (rb - ra) * (level - a) / (b - a)
    return R_KNOTS[-1][1]


def num(b):
    s = b.strip()
    return int(s) if s else 0


def req_level(get, row):
    for c in range(2):
        if num(get(row, 19 + 2 * c)) == AT_LEVEL:
            return num(get(row, 20 + 2 * c))
    return 0


def plan(stb, man):
    """{(row, col): (original bytes, new bytes)} for every cell the pass sets."""
    def get(row, col):
        k = "%d,%d" % (row, col)
        return man["cells"][k].encode("latin-1") if k in man["cells"] else stb.get(row, col)

    rows = [r for r in range(1, stb.rows) if stb.occupied(r) and r not in SKIP
            and num(get(r, COL_ATK)) > 0
            and (num(get(r, COL_TYPE)) in TYPES or num(get(r, COL_TYPE)) == CROSSBOW)]
    level = {r: req_level(get, r) for r in rows}
    for r in rows:
        if level[r] == 0:          # no level requirement: nearest same-type weapon by ATK
            wt, atk = num(get(r, COL_TYPE)), num(get(r, COL_ATK))
            peers = [p for p in rows if num(get(p, COL_TYPE)) == wt and level[p] > 0]
            if peers:
                level[r] = min(peers, key=lambda p: abs(num(get(p, COL_ATK)) - atk))
                level[r] = req_level(get, level[r])

    out = {}

    def put(row, col, value):
        old = get(row, col)
        new = str(value).encode("latin-1")
        if new != old.strip():
            out[(row, col)] = (old, new)

    for r in rows:
        wt = num(get(r, COL_TYPE))
        atk = num(get(r, COL_ATK))
        if wt == CROSSBOW:
            put(r, COL_ATK, max(1, round(atk * SCALE * max(R_FLOOR, R(level[r])))))
            slots = [(num(get(r, 24 + 3 * k)), k) for k in range(2)]
            k = next((k for t, k in slots if t == AT_ATK_SPD), None)
            if k is None:
                k = next((k for t, k in slots if t == 0), None)
            if k is not None:
                if num(get(r, 23 + 3 * k)):     # no union requirement (blank, as on every slot)
                    put(r, 23 + 3 * k, 0)
                put(r, 24 + 3 * k, AT_ATK_SPD)
                put(r, 25 + 3 * k, CROSSBOW_ASPD)
            continue
        label, speed, factor, nudge = TYPES[wt]
        put(r, COL_ATK, max(1, round(atk * SCALE * factor * max(R_FLOOR, R(level[r])))))
        put(r, COL_SPEED, speed)
        if nudge != 1.0:
            put(r, COL_QUALITY, round(num(get(r, COL_QUALITY)) * nudge))
    return out, rows, level


def report(stb, todo, rows, level):
    by = {}
    for (r, c), (old, new) in todo.items():
        wt = num(stb.get(r, COL_TYPE))
        by.setdefault(wt, {}).setdefault(c, []).append((r, old, new))
    for wt in list(TYPES) + [CROSSBOW]:
        label = TYPES[wt][0] if wt in TYPES else "crossbow"
        cells = by.get(wt, {})
        n = sum(1 for r in rows if num(stb.get(r, COL_TYPE)) == wt)
        atk = cells.get(COL_ATK, [])
        ratio = [num(new) / num(old) for _, old, new in atk if num(old)]
        print("%-12s %3d weapons: ATK %d cells (x%.2f..x%.2f), speed %d, quality %d, "
              "add slot %d" % (label, n, len(atk), min(ratio) if ratio else 1,
                               max(ratio) if ratio else 1, len(cells.get(COL_SPEED, [])),
                               len(cells.get(COL_QUALITY, [])),
                               sum(len(v) for c, v in cells.items() if 23 <= c <= 28)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--list", action="store_true", help="print every changed cell")
    a = ap.parse_args()

    original = open(STB, "rb").read()
    stb = oro.Stb(STB)
    if stb.to_bytes() != original:
        print("ABORT: the STB writer does not round-trip LIST_WEAPON.STB byte-for-byte")
        return 1
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}, "set": {}}

    if a.restore:
        if not man["cells"]:
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        skipped = 0
        for key, old in man["cells"].items():
            row, col = (int(x) for x in key.split(","))
            if stb.get(row, col).strip() != man["set"][key].encode("latin-1"):
                print("   skip %s: %r was edited since" % (key, stb.get(row, col)))
                skipped += 1
                continue
            stb.set(row, col, old.encode("latin-1"))
        open(STB, "wb").write(stb.to_bytes())
        if not skipped:
            os.remove(MANIFEST)
        print("restored %d cell(s) of LIST_WEAPON.STB, %d skipped"
              % (len(man["cells"]) - skipped, skipped))
        return 0

    todo, rows, level = plan(stb, man)
    pending = {k: v for k, v in todo.items() if stb.get(*k).strip() != v[1]}

    if a.verify:
        if pending:
            print("VERIFY FAILED: %d cell(s) differ from the pass" % len(pending))
            for (r, c), (old, new) in sorted(pending.items())[:20]:
                print("   %d,%d is %r, pass wants %r" % (r, c, stb.get(r, c), new))
            return 1
        print("ALL CHECKS PASSED -- %d cells carry the weapon identity pass." % len(todo))
        return 0

    report(stb, todo, rows, level)
    if a.list:
        for (r, c), (old, new) in sorted(todo.items()):
            print("   %4d %-34s lv %3d col %2d: %s -> %s" % (
                r, stb.get(r, 0).decode("latin-1").strip()[:34], level[r], c,
                old.decode("latin-1").strip(), new.decode("latin-1")))
    if not pending:
        print("nothing to do -- the pass is already applied.")
        return 0
    if a.dry_run:
        print("dry run: %d cell(s) would change, nothing written" % len(pending))
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    for (r, c), (old, new) in pending.items():
        k = "%d,%d" % (r, c)
        man["cells"].setdefault(k, old.decode("latin-1"))
        man["set"][k] = new.decode("latin-1")
        stb.set(r, c, new)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    open(STB, "wb").write(stb.to_bytes())
    print("wrote %d cell(s) in LIST_WEAPON.STB (undo: --restore, manifest in %s)"
          % (len(pending), BACKUP_DIR))

    check = oro.Stb(STB)
    left = {k: v for k, v in plan(check, man)[0].items() if check.get(*k).strip() != v[1]}
    if left:
        print("VERIFY FAILED after write: %d cell(s) differ" % len(left))
        return 1
    print("verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
