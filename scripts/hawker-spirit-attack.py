"""Hawker Spirit raises Attack Power as well as Accuracy (2026-10-16).

The combat simulator put the Raider at the bottom of the class sweep from level 120 up:
0.57-0.77x the median class's damage on level-matched monsters, against 2-2.6x for the
Champion. At level 237 the Raider has the Champion's ATK on paper (2349 vs 2384) and
attacks faster, but fights without a damage buff: Berserk keeps the Champion at +52% ATK
for the whole fight, while the Hawker line's buffs are Hawker Spirit (Accuracy), Sprint
and Stealth. Berserk stays as it is (user); the Raider gets a buff of its own instead.

Hawker Spirit (LIST_SKILL 1451-1460, the Hawker's rank 1-10 self buff, type 8) had a free
second status slot. This fills it:

    col 12 (SKILL_STATE_STB 2)      18  Attack Power Up (the status Berserk uses)
    col 24 (ability 2)              18  AT_ATK
    col 25 (flat)                    0
    col 26 (rate %)            6 .. 15  rank 1 -> rank 10, linear

so rank 10 is +15% ATK (percent of the pre-buff stat, like every buff). Critical Up was
tried first and barely moved the needle: crit chance is close to saturated at these
levels. Sim (dual swords, the common Raider build, vs the median class): 0.97/0.85/0.57/
0.68/0.77 -> 1.00/0.91/1.00/0.85/0.98 at levels 80/120/160/200/237. The Scout keeps its
numbers -- it does not keep Hawker Spirit up past the early levels -- and loses a few
points at 80-120 to the cast time. Katar Raiders stay weak (0.6-0.75); that is the weapon,
handled separately.

The texts follow: fix-skill-descriptions.py (LSkill1451) and fix-skill-book-names.py
(book 754) carry the new sentence; re-run both after this one.

    python scripts/hawker-spirit-attack.py --dry-run
    python scripts/hawker-spirit-attack.py
    python scripts/hawker-spirit-attack.py --verify
    python scripts/hawker-spirit-attack.py --restore

Cell-level manifest in build/hawker-spirit-attack/ ([old, written] per cell); restore puts
back the cells nobody edited since. The server reads LIST_SKILL: restart it, and re-bake
the VFS for the client (the tooltip lists the new status).
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_SKILL.STB")
MANIFEST = os.path.join(REPO, "build", "hawker-spirit-attack", "manifest.json")
RANKS = range(1451, 1461)
NAME = "Hawker Spirit"
ST_ATK_UP, AT_ATK = 18, 18
RATE_FIRST, RATE_LAST = 6, 15
C_STATE2, C_AB2, C_FLAT2, C_RATE2 = 12, 24, 25, 26


def plan(stb):
    out = {}
    n = len(RANKS) - 1
    for i, r in enumerate(RANKS):
        rate = round(RATE_FIRST + (RATE_LAST - RATE_FIRST) * i / n)
        for c, v in ((C_STATE2, ST_ATK_UP), (C_AB2, AT_ATK), (C_FLAT2, 0), (C_RATE2, rate)):
            out[(r, c)] = str(v)
    return out


def check(stb):
    """The rows must still be Hawker Spirit with the second slot free."""
    bad = []
    for r in RANKS:
        name = stb.get(r, 0).strip().decode("latin-1")
        if name != NAME:
            bad.append(f"row {r} is {name!r}, not {NAME}")
        for c in (C_STATE2, C_AB2, C_FLAT2, C_RATE2):
            v = stb.get(r, c).strip()
            if v not in (b"", b"0"):
                bad.append(f"row {r} col {c} already holds {v.decode('latin-1')}")
    return bad


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
    man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.isfile(MANIFEST) else None

    if args.restore or args.verify:
        if not man:
            print("not applied")
            return 0 if args.restore else 1
        bad = 0
        for key, (old, new) in man["cells"].items():
            r, c = (int(x) for x in key.split(","))
            if stb.get(r, c).strip() != new.encode("latin-1"):
                bad += 1
                if args.restore:
                    print(f"   skip {key}: edited since")
                continue
            if args.restore:
                stb.set(r, c, old.encode("latin-1"))
        if args.verify:
            print("ALL CHECKS PASSED" if not bad else f"VERIFY FAILED: {bad} cell(s) differ")
            return 1 if bad else 0
        open(STB, "wb").write(stb.to_bytes())
        os.remove(MANIFEST)
        print(f"restored {len(man['cells']) - bad} cell(s)")
        return 0
    if man:
        print(f"already applied ({len(man['cells'])} cells); --restore first to redo")
        return 0

    bad = check(stb)
    if bad:
        print("ABORT:\n   " + "\n   ".join(bad))
        return 1
    todo = plan(stb)
    for r in RANKS:
        print(f"   {r} rank {r - RANKS[0] + 1:>2}: + Attack Power Up {todo[(r, C_RATE2)]}%")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    cells = {}
    for (r, c), v in todo.items():
        cells[f"{r},{c}"] = [stb.get(r, c).strip().decode("latin-1"), v]
        stb.set(r, c, v.encode("latin-1"))
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump({"cells": cells}, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    open(STB, "wb").write(stb.to_bytes())
    print(f"wrote {len(cells)} cell(s) (undo: --restore)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
