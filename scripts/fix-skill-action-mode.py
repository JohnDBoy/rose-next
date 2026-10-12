#!/usr/bin/env python3
"""Keep the character fighting after an area attack skill.

Alpha feedback (2026-10-11): casting Luna Stone or Ice Bang mid-fight made the
character stop, and the player had to click the monster again.

What decides it is one LIST_SKILL column, game col 29 ``SKILL_ACTION_MODE``
(``src/common/io_skill.h``), read by ``SetNewCommandAfterSkill`` on the client
(``src/client/common/cobjai.cpp``) and by the server's skill action
(``src/sho_gameserver/src/common/cobjai.cpp``):

    0 / blank  SA_STOP     stand still once the skill has fired
    1          SA_ATTACK   attack the target (the server sets CMD_ATTACK even
                           with no target, so this is for targeted skills only)
    2          SA_RESTORE  go back to the command that was running when the
                           skill was ordered -- attacking resumes, standing
                           stays standing

Every retail-lineage dump (tsuki, ruff, QQ) ships the eight skills below with a
blank column: it is how the original game behaved, not a corruption. The rest
of the damage family -- Mana Bolt, Fire Ring, Ice Bolt, Spin Attack, Impact
Wave, Holy Blood, Spiral Kick, every imported monster skill -- carries 2, so 2
is the house value: it answers "I was fighting, keep fighting" and leaves a
skill opened from idle as it was. (1 would also make a cast from idle start
auto-attacking; it is what the Hawker's arrows use. Not chosen, so the mage kit
stays consistent with Mana Bolt.)

Rows: every rank of the eight -- the Mage's Lightning (951-955), Wind Storm
(1081-1085), Tornado (1086-1090), Luna Stone (1091-1100), Ice Bang (1101-1110),
Curse (1141-1150), the Raider's Red Cloud (1861-1870) and the Bourgeois' Zuly
Storm (2301-2310). Buffs on allies (type 9, target filter 3) are blank too and
are left alone: there is nothing to resume. Rows 5360-5369 are a nameless
Tornado remnant with no type and are not touched.

Idempotent, verifiable and reversible through a sidecar next to the STB
(``LIST_SKILL.action-mode.json``) holding the previous cell bytes. The selection
is the reviewed table above; a row that no longer matches it (type, target
filter or name changed since review) fails the run unless ``--allow-new``.

    python scripts/fix-skill-action-mode.py --dry-run
    python scripts/fix-skill-action-mode.py
    python scripts/fix-skill-action-mode.py --verify
    python scripts/fix-skill-action-mode.py --restore

Re-bake the VFS (the client reads the column) and restart the game server (it
reads the column too).
"""
import argparse
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STB = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_SKILL.STB")
SIDECAR = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_SKILL.action-mode.json")
COL_NAME, COL_TYPE, COL_TARGET, COL_MODE = 0, 5, 7, 29
NEW_MODE = b"2"
ENEMY = b"5"                                   # SKILL_TARGET_FILTER_ENEMY_ALL

# name -> (first row, last row, skill type)
REVIEWED = {
    b"Lightning": (951, 955, b"6"),
    b"Wind Storm": (1081, 1085, b"17"),
    b"Tornado": (1086, 1090, b"17"),
    b"Luna Stone": (1091, 1100, b"7"),
    b"Ice Bang": (1101, 1110, b"7"),
    b"Curse": (1141, 1150, b"6"),
    b"Red Cloud": (1861, 1870, b"17"),
    b"Zuly Storm": (2301, 2310, b"17"),
}


def load_oro():
    """The shared data layer (scripts/rosedata): codecs, table schema, importer helpers."""
    import rosedata
    return rosedata


def rows():
    for name, (a, b, _) in REVIEWED.items():
        for r in range(a, b + 1):
            yield r, name


def check(stb, allow_new):
    bad = []
    for r, name in rows():
        t = REVIEWED[name][2]
        if stb.get(r, COL_NAME) != name or stb.get(r, COL_TYPE) != t or stb.get(r, COL_TARGET) != ENEMY:
            bad.append((r, stb.get(r, COL_NAME), stb.get(r, COL_TYPE), stb.get(r, COL_TARGET)))
    if bad and not allow_new:
        for b in bad:
            print("row %d no longer matches the reviewed table: %r" % (b[0], b[1:]))
        sys.exit("refusing; re-review and pass --allow-new")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--restore", action="store_true")
    ap.add_argument("--allow-new", action="store_true")
    args = ap.parse_args()
    oro = load_oro()
    stb = oro.Stb(STB)

    if args.restore:
        if not os.path.exists(SIDECAR):
            sys.exit("no sidecar -- nothing to restore")
        saved = json.load(open(SIDECAR))
        for k, v in saved["cells"].items():
            r, c = map(int, k.split(":"))
            stb.set(r, c, v.encode("latin-1"))
        with open(STB, "wb") as f:
            f.write(stb.to_bytes())
        os.remove(SIDECAR)
        print("restored %d cells; sidecar removed" % len(saved["cells"]))
        return

    check(stb, args.allow_new)
    todo = [(r, name) for r, name in rows() if stb.get(r, COL_MODE) != NEW_MODE]
    if args.verify:
        if todo:
            for r, name in todo:
                print("row %d %s: mode %r" % (r, name.decode(), stb.get(r, COL_MODE)))
            sys.exit("VERIFY FAILED: %d rows still not %s" % (len(todo), NEW_MODE.decode()))
        print("VERIFY OK: %d rows at action mode %s" % (sum(1 for _ in rows()), NEW_MODE.decode()))
        return
    if not todo:
        print("already applied")
        return
    for r, name in todo:
        print("row %4d %-11s mode %-4r -> %s" % (r, name.decode(), stb.get(r, COL_MODE), NEW_MODE.decode()))
    if args.dry_run:
        print("dry run: %d rows would change" % len(todo))
        return
    record = json.load(open(SIDECAR)) if os.path.exists(SIDECAR) else {"cells": {}}
    for r, _ in todo:
        key = "%d:%d" % (r, COL_MODE)
        record["cells"].setdefault(key, stb.get(r, COL_MODE).decode("latin-1"))
        stb.set(r, COL_MODE, NEW_MODE)
    with open(STB, "wb") as f:
        f.write(stb.to_bytes())
    with open(SIDECAR, "w") as f:
        json.dump(record, f, indent=1)
    again = oro.Stb(STB)
    left = [r for r, _ in rows() if again.get(r, COL_MODE) != NEW_MODE]
    if left:
        sys.exit("post-write verify failed for rows %s" % left)
    print("wrote %d rows; VERIFY OK -- re-bake the VFS and restart the game server" % len(todo))


if __name__ == "__main__":
    main()
