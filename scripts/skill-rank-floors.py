"""First-job "spark" skills: lift their weak first ranks (2026-10-15).

The user felt first jobs lacked a spark. Measured in the combat simulator: their big
skills already take ~100% of a same-level plain monster's HP per cast by level 30-50, so
the gap was not damage size -- it was the first ranks, which sat at 15-32% of rank 10
(Lightning 89 vs 598, Holding Arrow 70 vs 360). Front-loading them hard (rank 1 at 55%)
made Dealer and Soldier openers one-shot plain monsters (kill time 3.1 s -> 0.2 s), the
opposite of the slower early game. The user's call: "up them slightly, nothing crazy,
just feeling better".

So each skill's SKILL_POWER (LIST_SKILL col 9) gets a floor: rank k is at least
FLOOR x rank-10 power at rank 1, rising linearly to rank 10, which is unchanged (second
jobs and the endgame do not move); no rank is ever lowered.

    Leap Attack (Soldier), Lightning and Ice Bolt (Muse), Screw Attack and Holding Arrow
    (Hawker): FLOOR 0.35        Gun Smash (Dealer): 0.25 (0.35 one-shot at rank 2)

Simulated (class sweep, plain monsters, levels 20-60): Soldier unchanged; Muse 40 kills in
5.9 s instead of 8.6 (Lightning joins its rotation); Dealer 60 1.4 s instead of 2.0;
kills per minute move by under 0.5 except the Muse's +0.7.

    python scripts/skill-rank-floors.py --dry-run
    python scripts/skill-rank-floors.py
    python scripts/skill-rank-floors.py --verify
    python scripts/skill-rank-floors.py --restore

Cell-level undo in build/skill-rank-floors/. The server and the client both read
LIST_SKILL: restart the server and re-bake. `data/` is gitignored, so this file is the
record.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402
from combatsim import GameData  # noqa: E402
from combatsim.autobuild import class_skills, skill_ranks  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_SKILL.STB")
MANIFEST = os.path.join(REPO, "build", "skill-rank-floors", "manifest.json")
COL_POWER = 9
# skill name: (a class that learns it, floor, rank count reviewed)
FLOORS = {
    "Leap Attack": (111, 0.35, 10),
    "Lightning": (211, 0.35, 10),
    "Ice Bolt": (211, 0.35, 10),
    "Screw Attack": (311, 0.35, 10),
    "Holding Arrow": (311, 0.35, 10),
    "Gun Smash": (411, 0.25, 10),
}


def num(b):
    s = b.strip()
    return int(s) if s.lstrip(b"-").isdigit() else 0


def plan(stb, gd, man):
    """{(row, col): new value}, computed from the original powers."""
    out = {}
    for name, (job, floor, n) in FLOORS.items():
        first = next((f for f in class_skills(gd, job) if gd.name("LIST_SKILL", f) == name), None)
        if first is None:
            raise SystemExit(f"ABORT: {name} not found in class {job}'s skills")
        rows = skill_ranks(gd, first)
        if len(rows) != n:
            raise SystemExit(f"ABORT: {name} has {len(rows)} ranks, reviewed with {n}")

        def orig(r):
            k = f"{r},{COL_POWER}"
            return int(man["cells"][k]) if k in man["cells"] else num(stb.get(r, COL_POWER))
        top = orig(rows[-1])
        for k, r in enumerate(rows):
            want = round(top * (floor + (1 - floor) * k / (n - 1)))
            out[(r, COL_POWER)] = max(orig(r), want)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    raw = open(STB, "rb").read()
    stb = oro.Stb(STB)
    if stb.to_bytes() != raw:
        print("ABORT: the STB writer does not round-trip LIST_SKILL.STB byte-for-byte")
        return 1
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}}

    if args.restore:
        if not man["cells"]:
            print("nothing to restore")
            return 0
        for key, old in man["cells"].items():
            r, c = (int(v) for v in key.split(","))
            stb.set(r, c, str(old).encode())
        open(STB, "wb").write(stb.to_bytes())
        os.remove(MANIFEST)
        print(f"restored {len(man['cells'])} cell(s) of LIST_SKILL.STB")
        return 0

    gd = GameData()
    todo = plan(stb, gd, man)
    pending = {k: v for k, v in todo.items() if num(stb.get(*k)) != v}
    for name, (job, floor, n) in FLOORS.items():
        rows = [r for r, _c in todo if gd.name("LIST_SKILL", r).startswith(name)][:n]
        print(f"   {name:<14} floor {floor:.2f}: " + " ".join(
            f"{num(stb.get(r, COL_POWER))}>{todo[(r, COL_POWER)]}" for r in sorted(rows)))
    if args.verify:
        if pending:
            print(f"VERIFY FAILED: {len(pending)} cell(s) differ")
            return 1
        print("ALL CHECKS PASSED -- the rank floors are in place.")
        return 0
    if not pending:
        print("nothing to do.")
        return 0
    if args.dry_run:
        print(f"dry run: {len(pending)} cell(s) would change, nothing written")
        return 0
    for (r, c), v in pending.items():
        man["cells"].setdefault(f"{r},{c}", num(stb.get(r, c)))
        stb.set(r, c, str(v).encode())
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    open(STB, "wb").write(stb.to_bytes())
    print(f"wrote {len(pending)} cell(s) (undo: --restore)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
