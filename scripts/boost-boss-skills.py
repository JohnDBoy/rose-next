"""Boss skills that hit weaker than the boss's own swing get a boss-only stronger copy
(2026-10-15).

After the king/skull HP pass the user asked that a boss's skills hit harder than its
normal attack -- unless the skill is there for a debuff (Deader Rex's Toxic Rain poisons
and Silencing Wave silences: left alone). Measured in the combat simulator (skill hit /
normal hit against the five-class panel at the boss's level), only one skill came out
below 1x with no state:

    #3042 (area, magic, power 90, no state): Crowned Asper King 0.6x, Giant Fiery
    Snapper 0.6x (Grand Master Devourer 1.2x)

#3042 is cast by 31 monsters (Sikukus, the Asper family ...), so the row itself is not
touched: it is copied once to a new LIST_SKILL row at power NEW_POWER (magic skill damage
is linear in power: 90 -> 240 lifts 0.6x to ~1.6x) and the two bosses' own AI files
(each is the only user of its file) cast the copy instead. Bosses that never cast a skill
got a small ATK lift in rebalance-monster-roles.py instead.

    python scripts/boost-boss-skills.py --dry-run
    python scripts/boost-boss-skills.py
    python scripts/boost-boss-skills.py --verify
    python scripts/boost-boss-skills.py --restore

The new row goes after the table's last row (a restore blanks it); the manifest
(build/boss-skills/) records it and the original AI files (whole-file copies are safe here: nothing else writes these
two boss-only files). LIST_SKILL is read by both server and client, the .aip by the
server: restart it and re-bake.
"""

import argparse
import glob
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402
from rosefmt import aip  # noqa: E402

SKILL_STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_SKILL.STB")
AI_DIR = os.path.join(REPO, "data", "3DDATA", "AI")
BACKUP_DIR = os.path.join(REPO, "build", "boss-skills")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")
SOURCE, NEW_POWER, COL_POWER = 3042, 240, 9
BOSS_AI = {"OR_kingasper1.aip": "Crowned Asper King", "OR_giantsnapper1.aip": "Giant Fiery Snapper"}
AIACT_SKILL, SKILL_OFFSET = 24, 10          # AIACT24 "cast skill": <Bxhh target, skill, motion
                                            # (a record's type byte is the action number + 1)


def ai_path(name):
    hit = [p for p in glob.glob(os.path.join(AI_DIR, "*")) if os.path.basename(p).lower() == name.lower()]
    if not hit:
        raise SystemExit(f"ABORT: {name} not found under {AI_DIR}")
    return hit[0]


def recast(b, old, new):
    """The AI file with every AIACT24 casting `old` casting `new`; (bytes, count)."""
    header, title, pats, tail = aip.parse(b)
    n = 0
    out = []
    for pname, evs in pats:
        e2 = []
        for ename, conds, acts in evs:
            a2 = []
            for a in acts:
                if (aip.record_type(a) & 0xFF) - 1 == AIACT_SKILL and \
                        struct.unpack_from("<h", a, SKILL_OFFSET)[0] == old:
                    a = bytearray(a)
                    struct.pack_into("<h", a, SKILL_OFFSET, new)
                    a = bytes(a)
                    n += 1
                a2.append(a)
            e2.append((ename, conds, a2))
        out.append((pname, e2))
    return aip.build(header, title, out, tail), n


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    raw = open(SKILL_STB, "rb").read()
    stb = oro.Stb(SKILL_STB)
    if stb.to_bytes() != raw:
        print("ABORT: the STB writer does not round-trip LIST_SKILL.STB byte-for-byte")
        return 1
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else None

    if args.restore:
        if not man:
            print("nothing to restore")
            return 0
        row = man["row"]
        for c in range(stb.cols):           # the appended row stays, blank (harmless)
            stb.set(row, c, b"")
        open(SKILL_STB, "wb").write(stb.to_bytes())
        for name in man["ai"]:
            shutil.copyfile(os.path.join(BACKUP_DIR, name), ai_path(name))
        os.remove(MANIFEST)
        print(f"restored LIST_SKILL (row {row} blanked) and {len(man['ai'])} AI files")
        return 0

    row = man["row"] if man else stb.rows
    files = {name: ai_path(name) for name in BOSS_AI}
    if args.verify:
        if not man:
            print("VERIFY FAILED: not applied")
            return 1
        ok = stb.i(row, COL_POWER) == NEW_POWER and all(
            stb.get(row, c) == stb.get(SOURCE, c) for c in range(stb.cols) if c != COL_POWER)
        for name, p in files.items():
            _b, n_old = recast(open(p, "rb").read(), SOURCE, row)
            _b, n_new = recast(open(p, "rb").read(), row, row)
            ok = ok and n_old == 0 and n_new > 0
        print("ALL CHECKS PASSED -- the bosses cast their own copy." if ok else "VERIFY FAILED")
        return 0 if ok else 1
    if man:
        print(f"already applied (row {row}); --restore first to redo")
        return 0
    counts = {}
    for name, p in files.items():
        _b, counts[name] = recast(open(p, "rb").read(), SOURCE, row)
        if not counts[name]:
            print(f"ABORT: {name} does not cast {SOURCE}")
            return 1
    print(f"copy LIST_SKILL {SOURCE} (power {stb.i(SOURCE, COL_POWER)}) to new row {row} at power "
          f"{NEW_POWER}; recast: " + ", ".join(f"{BOSS_AI[n]} ({c} cast(s))" for n, c in counts.items()))
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stb.grow_to(row + 1)
    for c in range(stb.cols):
        stb.set(row, c, stb.get(SOURCE, c))
    stb.set(row, COL_POWER, str(NEW_POWER).encode())
    open(SKILL_STB, "wb").write(stb.to_bytes())
    for name, p in files.items():
        shutil.copyfile(p, os.path.join(BACKUP_DIR, name))
        b, _n = recast(open(p, "rb").read(), SOURCE, row)
        open(p, "wb").write(b)
    json.dump(dict(row=row, ai=list(files)), open(MANIFEST, "w"), indent=1)
    print(f"wrote LIST_SKILL row {row} and {len(files)} AI files (undo: --restore)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
