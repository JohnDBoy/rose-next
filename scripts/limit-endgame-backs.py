"""Give the four level-180 "boss" backs a class, by theme (2026-10-15).

LIST_BACK 953-956 came from the 667/tsuki lineage with no class requirement (col 16,
ITEM_EQUIP_REQUIRE_CLASS, blank in every reference dump), and each is far beyond its
level-180 peers (30-55 DEF): any class could wear the tank's shell. The user's call after
the weapon identity test:

    954 Snapper Shell       DEF 307, DEF +80, max HP +1600 -> Knight Job (61: Knight, Paladin)
    953 Doctor's Back Arms  ATK +50, attack speed +20        -> Dealer Job (44)
    955 Hecado's Grace      HP/MP recovery +75               -> Muse Job (42)
    956 Ardemia's Grace     HP/MP recovery +75               -> Muse Job (42)

Their stats are left as they are. The class rows are LIST_CLASS's own (61, 44, 42 list
the jobs; CUserDATA::Check_JobCollection reads them on the server, the tooltip on the
client).

    python scripts/limit-endgame-backs.py --dry-run
    python scripts/limit-endgame-backs.py
    python scripts/limit-endgame-backs.py --verify
    python scripts/limit-endgame-backs.py --restore

Rows are checked by name before anything is written. Undo is per cell
(build/endgame-backs/manifest.json). `data/` is gitignored, so this file is the record.
The server reads LIST_BACK: restart it, and re-bake the VFS for the client.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_BACK.STB")
BACKUP_DIR = os.path.join(REPO, "build", "endgame-backs")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")
COL_CLASS = 16
# row: (name, LIST_CLASS row)
PLAN = {
    953: (b"Doctor's Back Arms", 44),
    954: (b"Snapper Shell", 61),
    955: (b"Hecado's Grace", 42),
    956: (b"Ardemia's Grace", 42),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    original = open(STB, "rb").read()
    stb = oro.Stb(STB)
    if stb.to_bytes() != original:
        print("ABORT: the STB writer does not round-trip LIST_BACK.STB byte-for-byte")
        return 1

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        for key, old in man["cells"].items():
            row, col = (int(x) for x in key.split(","))
            if stb.get(row, col).strip() != str(PLAN[row][1]).encode():
                print("   skip %s: edited since (%r)" % (key, stb.get(row, col)))
                continue
            stb.set(row, col, old.encode("latin-1"))
        open(STB, "wb").write(stb.to_bytes())
        os.remove(MANIFEST)
        print("restored LIST_BACK.STB")
        return 0

    for row, (name, _cls) in PLAN.items():
        if stb.get(row, 0).strip() != name:
            print("ABORT: LIST_BACK %d is %r, expected %r" % (row, stb.get(row, 0).strip(), name))
            return 1
    todo = {row: cls for row, (_n, cls) in PLAN.items()
            if stb.get(row, COL_CLASS).strip() != str(cls).encode()}
    for row, (name, cls) in PLAN.items():
        print("   %d %-20s class %r -> %d%s" % (row, name.decode(), stb.get(row, COL_CLASS).strip(),
                                               cls, "" if row in todo else " (done)"))
    if a.verify:
        if todo:
            print("VERIFY FAILED: %d row(s) without their class" % len(todo))
            return 1
        print("ALL CHECKS PASSED -- the four backs carry their class.")
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: %d cell(s) would change, nothing written" % len(todo))
        return 0
    os.makedirs(BACKUP_DIR, exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}}
    for row, cls in todo.items():
        man["cells"].setdefault("%d,%d" % (row, COL_CLASS),
                                stb.get(row, COL_CLASS).decode("latin-1"))
        stb.set(row, COL_CLASS, str(cls).encode())
    json.dump(man, open(MANIFEST, "w"), indent=1)
    open(STB, "wb").write(stb.to_bytes())
    print("wrote %d cell(s) in LIST_BACK.STB (undo: --restore)" % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
