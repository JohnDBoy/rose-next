#!/usr/bin/env python3
r"""Three top-tier gloves asked for a third job, which nobody can have.

THE DEFECT
----------
An item's class requirement is LIST_*.STB **column 16** (`ITEM_EQUIP_REQUIRE_CLASS`,
`src/common/include/rose/io/stb.h`), a row of `LIST_CLASS.STB` whose columns 1-8 list
the jobs allowed. Client (`CUserDATA::Check_JobCollection`, the red/green tooltip line)
and server (the same function in `sho_gameserver`) both refuse the item unless the
character's job is in that list.

Rows 56-59 of LIST_CLASS are "<family> 3rd Advanced Jobs" (131/132, 231/232, 331/332,
431/432). There is no third job in the game, so an item pointing at one of them can
never be worn. Tester report (2026-11-25): "Legend Redfield Chairman Gloves require a
third job".

An audit of every equippable table (cap, body, arms, foot, face item, back, jewel,
weapon, sub-weapon, plus LIST_PAT col 65 and LIST_SKILL col 35) for a class row whose
jobs are *all* third jobs finds exactly three rows, all in LIST_ARMS:

    442  Heaven's Gloves           57 Muse 3rd    -> 52 Muse 2nd
    542  Wild Hawker Gloves        58 Hawker 3rd  -> 53 Hawker 2nd
    642  Redfield Chairman Gloves  59 Dealer 3rd  -> 54 Dealer 2nd

WHY THE 2ND-JOB ROW
-------------------
They are the gloves of the four top sets (Plate / Heaven's / Wild Hawker / Redfield
Chairman, stat requirement 126-129). Every other piece of those sets -- cap, body,
foot, and the Soldier's Plate Gauntlets (LIST_ARMS 342) -- requires its family's
2nd-job row (51-54), as do the glove rows just below them (338-341, 438-441, 538-541,
638-641). So the three are typos of the same column, not a design choice; nothing
else in the rows is touched.

Idempotent; --dry-run, --verify, --restore (cell-level, build/third-job-gloves/).
The server caches STBs: restart it, and re-bake for the client.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

ROOT = os.path.dirname(HERE)
ARMS = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_ARMS.STB")
CLASS = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_CLASS.STB")
MANIFEST = os.path.join(ROOT, "build", "third-job-gloves", "manifest.json")
CLASS_COL = 16

# row -> (col-0 name, broken class, fixed class)
ROWS = {
    442: ("Heavens Gloves", 57, 52),
    542: ("Wild Hawker Gloves", 58, 53),
    642: ("Redfield Chairman Gloves", 59, 54),
}


def class_jobs(cls, r):
    jobs = []
    for c in range(8):
        j = cls.i(r, 1 + c)
        if not j:
            break
        jobs.append(j)
    return jobs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    arms = Stb(ARMS)
    cls = Stb(CLASS)

    if args.restore:
        if not os.path.exists(MANIFEST):
            sys.exit("no manifest at %s -- nothing to restore" % MANIFEST)
        with open(MANIFEST) as fh:
            old = json.load(fh)
        for r, v in old.items():
            print("  %-4s class -> %s" % (r, v))
            arms.set(int(r), CLASS_COL, v.encode("latin-1"))
        arms.save(args.dry_run, keep_backup=False)
        if not args.dry_run:
            os.remove(MANIFEST)
        print("restored." if not args.dry_run else "DRY RUN - nothing written.")
        return

    # The targets must be 2nd-job rows, and the old values 3rd-job-only rows.
    for r, (name, bad, good) in ROWS.items():
        bj, gj = class_jobs(cls, bad), class_jobs(cls, good)
        if not bj or not all(j % 100 // 10 == 3 for j in bj):
            sys.exit("LIST_CLASS %d is no longer a third-job row: %s" % (bad, bj))
        if not gj or not all(j % 100 // 10 == 2 for j in gj):
            sys.exit("LIST_CLASS %d is no longer a second-job row: %s" % (good, gj))

    if args.verify:
        fails = 0
        for r, (name, bad, good) in sorted(ROWS.items()):
            cur = arms.i(r, CLASS_COL)
            ok = cur == good
            fails += not ok
            print("  %-4d %-26s class %-3d %s" % (r, name, cur, "OK" if ok else "*** expected %d ***" % good))
        sys.exit(1 if fails else 0)

    old = {}
    for r, (name, bad, good) in sorted(ROWS.items()):
        got = arms.s(r, 0).strip()
        if got != name:
            sys.exit("row %d is %r, expected %r -- table shifted, refusing" % (r, got, name))
        cur = arms.i(r, CLASS_COL)
        if cur == good:
            print("  %-4d %-26s already %d" % (r, name, good))
            continue
        if cur != bad:
            sys.exit("row %d (%s) has class %d, expected %d (broken) or %d (fixed) -- not guessing"
                     % (r, name, cur, bad, good))
        print("  %-4d %-26s class %d (%s) -> %d (%s)"
              % (r, name, cur, cls.s(bad, 0), good, cls.s(good, 0)))
        old[str(r)] = arms.s(r, CLASS_COL)
        arms.set_i(r, CLASS_COL, good)

    if not old:
        print("nothing to do.")
        return
    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        return

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    prev = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as fh:
            prev = json.load(fh)
    prev.update(old)
    with open(MANIFEST, "w") as fh:
        json.dump(prev, fh, indent=1)
    arms.save(False, keep_backup=False)

    check = Stb(ARMS)
    assert (check.rows, check.cols) == (arms.rows, arms.cols), "table shape changed"
    for r, (_n, _b, good) in ROWS.items():
        assert check.i(r, CLASS_COL) == good, "row %d did not take" % r
    print("\nverified: %d row(s) fixed.  Restart the gameserver (it caches STBs) and re-bake."
          % len(old))


if __name__ == "__main__":
    main()
