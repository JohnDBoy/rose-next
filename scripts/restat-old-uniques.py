"""Re-stat the older uniques' ATK so each one carries a player for a while (2026-10-26).

Uniques (violet name, STR_ITEMPREFIX 21) have no level requirement, only a stat one, and
are meant to be rare drops stronger than what you would have at the level that stat
comes with -- a weapon that carries you for a while. The audit that day (the combat
simulator's stat curves against the ordinary weapon ladder) found the 15 imported from
668 (import-668-uniques.py) doing that -- a median 1.27x the best ordinary weapon at the
level a typical build meets the requirement, overtaken ~50 levels later -- but the 34
older retail ones not: a median 1.10x, overtaken a median 4 levels later, seven already
weaker than the shop weapon on the day they can be worn.

The user's target, "not an exact science": **about 1.25x the best ordinary weapon of the
type at the level a typical build can wear it, overtaken about 20 levels later.** For
each unique:

    gate     the first level the class that uses the type meets the stat requirement
             with the auto-build's stat spend (combatsim autobuild.PROFILES /
             auto_stats; the crossbow reads the Knight's, the kiting Knight's weapon)
             -- the typical build, the user's choice over a stat-focused one
    target   effective ATK (ATK + an ATK bonus line) halfway between 1.25x the best
             ordinary weapon at the gate and the best one 20 levels on

Only ATK (col 35) moves, less the unique's own ATK bonus line; requirements and the
other bonuses (crit, attack speed, max HP, MP cost ...) stay. Ordinary weapons are the
same-type rows with a level requirement, no unique prefix and no event/holiday row.
Result: 1.16-1.50x at the gate, overtaken 8-39 levels on (median ~17; wands least, their
ladder moves in big steps). Most go up; four come down, being far above the target --
Composite Bow Gun 135 -> 113, Knight Killer 199 -> 152 (the crossbow ladder is low),
Gatling Multi Launcher 130 -> 123, Gladius 136 -> 130.

The 668 tier is not touched (the user: Rock Launcher's low STR is fine, a Bourgeois is
not STR-built). The plan is frozen in the manifest on the first run, so a later ladder
change does not move these rows silently; the rows are in weapon-identity-pass.py's
SKIP. Undo is per cell (`build/restat-old-uniques/manifest.json`); `data/` is
gitignored, so this file is the record. Restart the servers (LIST_WEAPON), re-bake.

    python scripts/restat-old-uniques.py --dry-run
    python scripts/restat-old-uniques.py
    python scripts/restat-old-uniques.py --verify
    python scripts/restat-old-uniques.py --restore
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
BACKUP_DIR = os.path.join(REPO, "build", "restat-old-uniques")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

COL_TYPE, COL_ATK = 4, 35
UNIQUE = 21                        # STR_ITEMPREFIX: violet name
AT_ATK = 18
BONUS = ((24, 25), (27, 28))
STATS = {10: "STR", 11: "DEX", 12: "INT", 13: "CON", 14: "CHARM", 15: "SENSE"}
RATIO, CARRY = 1.25, 20
CROSSBOW, KNIGHT = 271, 121
# the 668 tier (import-668-uniques.py), already where it should be
NEW_TIER = {904, 911, 918, 922, 929, 935, 936, 943, 955, 962, 970, 979, 986, 994, 995}
ROWS = [901, 902, 903, 909, 910, 916, 917, 920, 921, 927, 928, 933, 934, 940, 941, 942,
        952, 953, 954, 960, 961, 967, 968, 969, 975, 976, 977, 978, 983, 984, 985, 991,
        992, 993]


def atk_bonus(s, r):
    return sum(s.i(r, amt) for ab, amt in BONUS if s.i(r, ab) == AT_ATK)


def plan(s):
    """{row: new ATK} from the live tables and the combat simulator's stat curves."""
    from combatsim.data import GameData
    from combatsim.autobuild import PROFILES, _ok, con_floor, prefix_id
    from combatsim.player import auto_stats
    gd = GameData()
    w = gd.stb("LIST_WEAPON")
    eff = lambda r: w.i(r, COL_ATK) + atk_bonus(w, r)
    found = sorted(r for r in range(1, w.rows) if w.occupied(r) and prefix_id(gd, "LIST_WEAPON", r) == UNIQUE
                   and r not in NEW_TIER)
    if found != ROWS:
        sys.exit("ABORT: the older uniques are %s, expected %s" % (found, ROWS))
    ladder = {}
    for r in range(1, w.rows):
        if (not w.occupied(r) or w.i(r, COL_ATK) <= 0 or prefix_id(gd, "LIST_WEAPON", r) == UNIQUE
                or not _ok(gd, "LIST_WEAPON", r, 999)):
            continue
        lv = gd.item_req_level(8, r)
        if lv > 0:
            ladder.setdefault(w.i(r, COL_TYPE), []).append((lv, eff(r)))

    def best_at(wt, level):
        return max((e for lv, e in ladder[wt] if lv <= level), default=0)

    curves = {}

    def gate(r, job):
        prof = PROFILES[job]
        if job not in curves:
            curves[job] = [auto_stats(L, prof["w"], con_floor(job)) for L in range(251)]
        need = [(STATS[w.i(r, t)], w.i(r, t + 1)) for t in (19, 21) if w.i(r, t) in STATS and w.i(r, t + 1) > 0]
        for L in range(1, 251):
            if all(curves[job][L][k] >= a for k, a in need):
                return L
        return None

    out = {}
    for r in ROWS:
        wt = w.i(r, COL_TYPE)
        jobs = [KNIGHT] if wt == CROSSBOW else [j for j, p in PROFILES.items() if wt in p["wt"]]
        levels = [L for L in (gate(r, j) for j in jobs) if L]
        if not levels:
            sys.exit("ABORT: row %d (%s): no class meets its requirement" % (r, gd.name("LIST_WEAPON", r)))
        L = min(levels)
        target = round((RATIO * best_at(wt, L) + best_at(wt, min(250, L + CARRY))) / 2)
        out[r] = dict(atk=target - atk_bonus(w, r), level=L, eff_before=eff(r), eff=target,
                      ladder=best_at(wt, L), name=gd.name("LIST_WEAPON", r))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    s = Stb(STB)
    if s.to_bytes() != open(STB, "rb").read():
        sys.exit("ABORT: LIST_WEAPON does not round-trip")
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else None

    if a.restore:
        if not man:
            print("nothing to restore")
            return 0
        for r, old in man["cells"].items():
            s.set(int(r), COL_ATK, old.encode("latin-1"))
        open(STB, "wb").write(s.to_bytes())
        os.remove(MANIFEST)
        print("restored %d cell(s)" % len(man["cells"]))
        return 0

    p = {int(r): v for r, v in man["plan"].items()} if man else plan(s)
    todo = {r: v for r, v in p.items() if s.i(r, COL_ATK) != v["atk"]}
    print("%-4s %-24s %5s %6s | %5s %5s -> %-5s | %s" % ("row", "unique", "gate", "ladder", "ATK", "eff", "eff", "x ladder"))
    for r, v in sorted(p.items(), key=lambda kv: kv[1]["level"]):
        print("%-4d %-24s %5d %6d | %5d %5d -> %-5d | %.2f -> %.2f" % (
            r, v["name"][:24], v["level"], v["ladder"], v["atk"], v["eff_before"], v["eff"],
            v["eff_before"] / v["ladder"], v["eff"] / v["ladder"]))
    print("cells to change: %d" % len(todo))

    if a.verify:
        if todo:
            print("VERIFY FAILED: rows %s" % sorted(todo))
            return 1
        print("ALL CHECKS PASSED -- the %d older uniques carry their new ATK." % len(p))
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    cells = man["cells"] if man else {}
    for r, v in todo.items():
        cells.setdefault(str(r), s.s(r, COL_ATK).strip())
        s.set(r, COL_ATK, str(v["atk"]).encode("latin-1"))
    open(STB, "wb").write(s.to_bytes())
    json.dump({"plan": {str(r): v for r, v in p.items()}, "cells": cells}, open(MANIFEST, "w"), indent=1)
    print("wrote %d cell(s) (undo: --restore). Restart the servers and re-bake the VFS." % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
