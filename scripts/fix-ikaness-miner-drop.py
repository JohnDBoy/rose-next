#!/usr/bin/env python3
r"""Ikaness Miner dropped a nameless material: 12:309 is a typo for 12:39.

THE DEFECT
----------
ITEM_DROP.STB row 74 is the Ikaness Miner's (LIST_NPC 1577, col 18). A kill rolls
one of its columns 1-30 (`CCal::Get_DropITEM`, src/common/calculation.cpp) and the
cell names an item as `type * 1000 + id`. Column 3 holds **12309**, LIST_NATURAL row
309, which is blank: the roll paid out a material with no name, no icon, no use
(tester report, 2026-11-25).

WHY 12039
---------
- The six other Ikaness tables of that band (73 Worker, 75 Leader, 76 Guard,
  77 Soldier, 950 Engineer, 951 Heavygear) carry the same 23-cell material list in
  columns 1-23, and all six have **12039** in column 3; the Miner's other 22 cells
  match them exactly.
- 12039 is Otherworldly Wood, a class-424 wood like its neighbours in the list
  (12037 Cinnamon Wood, 12038 Red Sandalwood, 12040 Sephiroth Wood).
- The typo is upstream: ruff, our lineage, ships the same 12309; titanRose, the same
  lineage, ships 12039 in that cell -- someone there fixed it the same way.

SCOPE
-----
A scan of every ITEM_DROP cell for an item row with no name found five: this one,
and Moss Golem's table 942 columns 36-39 (blank LIST_USEITEM 226/227/231/235).
Those four sit in redirect group 2's window (columns 36-40), and table 942 has no
group-2 cell -- its only redirect is a 3 (columns 41-45) -- so no roll can reach them.
They are inert and left alone.

The Miner's other differences from its siblings (no column-30 redirect, no column 41)
are consistent with each other -- a table without a valuable tier -- and are not
touched.

Idempotent; --dry-run, --verify, --restore (cell-level, build/ikaness-miner-drop/).
The server caches STBs: restart it. The client reads ITEM_DROP only for the Monster
Inspector's drop list: re-bake.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

ROOT = os.path.dirname(HERE)
STB = os.path.join(ROOT, "data", "3DDATA", "STB")
DROP = os.path.join(STB, "ITEM_DROP.STB")
NPC = os.path.join(STB, "LIST_NPC.STB")
NATURAL = os.path.join(STB, "LIST_NATURAL.STB")
MANIFEST = os.path.join(ROOT, "build", "ikaness-miner-drop", "manifest.json")

MINER_NPC, MINER_NAME = 1577, "Ikaness Miner"
TABLE, COL = 74, 3
BROKEN, WANT = 12309, 12039
SIBLINGS = (73, 75, 76, 77, 950, 951)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    drop = Stb(DROP)

    if args.restore:
        if not os.path.exists(MANIFEST):
            sys.exit("no manifest at %s -- nothing to restore" % MANIFEST)
        with open(MANIFEST) as fh:
            old = json.load(fh)
        print("  table %d col %d -> %s" % (TABLE, COL, old["value"]))
        drop.set(TABLE, COL, old["value"])
        drop.save(args.dry_run, keep_backup=False)
        if not args.dry_run:
            os.remove(MANIFEST)
        print("restored." if not args.dry_run else "DRY RUN - nothing written.")
        return

    cur = drop.i(TABLE, COL)
    if args.verify:
        ok = cur == WANT
        print("  table %d col %d = %d  %s" % (TABLE, COL, cur, "OK" if ok else "*** expected %d ***" % WANT))
        sys.exit(0 if ok else 1)

    # Refuse if the table no longer belongs to the Miner, or the evidence moved.
    npc = Stb(NPC)
    if npc.s(MINER_NPC, 0).strip() != MINER_NAME or npc.i(MINER_NPC, 18) != TABLE:
        sys.exit("LIST_NPC %d is no longer %s on drop table %d" % (MINER_NPC, MINER_NAME, TABLE))
    nat = Stb(NATURAL)
    if not nat.s(WANT % 1000, 0).strip():
        sys.exit("LIST_NATURAL %d is blank -- refusing to point the drop at it" % (WANT % 1000))
    if nat.s(BROKEN % 1000, 0).strip():
        sys.exit("LIST_NATURAL %d now has a name (%r) -- re-check before changing the drop"
                 % (BROKEN % 1000, nat.s(BROKEN % 1000, 0)))
    for t in SIBLINGS:
        if drop.i(t, COL) != WANT:
            sys.exit("sibling table %d col %d is %s, not %d -- the pattern changed"
                     % (t, COL, drop.s(t, COL), WANT))

    if cur == WANT:
        print("  table %d col %d already %d" % (TABLE, COL, WANT))
        return
    if cur != BROKEN:
        sys.exit("table %d col %d is %d, expected %d (broken) or %d (fixed) -- not guessing"
                 % (TABLE, COL, cur, BROKEN, WANT))
    print("  table %d (%s) col %d: %d -> %d (%s)"
          % (TABLE, MINER_NAME, COL, cur, WANT, nat.s(WANT % 1000, 0).strip()))
    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        return

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w") as fh:
        json.dump({"value": drop.s(TABLE, COL)}, fh, indent=1)
    drop.set_i(TABLE, COL, WANT)
    drop.save(False, keep_backup=False)

    check = Stb(DROP)
    assert (check.rows, check.cols) == (drop.rows, drop.cols), "table shape changed"
    assert check.i(TABLE, COL) == WANT, "cell did not take"
    print("\nverified.  Restart the gameserver (it caches STBs) and re-bake.")


if __name__ == "__main__":
    main()
