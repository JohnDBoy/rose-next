"""Share a quest monster's kill with the killer's party (LIST_NPC col 38).

A monster whose row names a death event (LIST_NPC col 41, a QSD trigger) asks the
client to check that trigger when it dies (`classUSER::Send_gsv_CHECK_NPC_EVENT`).
By default only the player credited with the kill is asked; col 38
(`NPC_QUEST_TYPE`) non-zero asks every party member in the zone within the EXP
share range instead -- retail's switch for its party bosses (Grandmaster Golem 169,
Worm Dragon 201, Grandmaster Goblin 287, the Junon guardians 401-410). Each client
checks the trigger against its own quests, so only members on that quest get its
reward. Until 2026-11-25 such a monster gave a killer outside any party nothing at
all; the server now sends the event to them alone.

- **Woopie King (205)**: its death event 113-31 (quest 113, "Hourglass of
  Purification") starts the hand-over of the Crystal Key. Tester report
  (2026-11-25): a party farms the Woopies until a spawn point sends the king, then
  only one of them gets the key and the rest must farm it again.

    python scripts/share-quest-kills.py --dry-run
    python scripts/share-quest-kills.py
    python scripts/share-quest-kills.py --verify
    python scripts/share-quest-kills.py --restore

Cell-level undo in build/share-quest-kills/. Needs the 2026-11-25 sho_gameserver
(else a solo killer of a shared monster gets no event); restart the servers, re-bake.
`data/` is gitignored, so this file is the record.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import stb  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, ".."))
NPC = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_NPC.STB")
BACKUP_DIR = os.path.join(REPO, "build", "share-quest-kills")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

COL_QUEST_TYPE, COL_DEAD_EVENT = 38, 41
SHARED = {205: ("Woopie King", "113-31")}   # row: (col 0 name, death event) -- reviewed


def plan(t):
    todo, problems = [], []
    for row, (name, event) in sorted(SHARED.items()):
        if t.s(row, 0).strip() != name or t.s(row, COL_DEAD_EVENT).strip() != event:
            problems.append("row %d is %r / %r, expected %r / %r" % (
                row, t.s(row, 0), t.s(row, COL_DEAD_EVENT), name, event))
        elif t.i(row, COL_QUEST_TYPE) == 0:
            todo.append(row)
    return todo, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    t = stb.Stb(NPC)
    if t.to_bytes() != open(NPC, "rb").read():
        print("ABORT: the STB writer does not round-trip LIST_NPC.STB")
        return 1

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        for row, old in man["cells"].items():
            if t.i(int(row), COL_QUEST_TYPE) != 1:
                print("REFUSED: row %s col %d changed since" % (row, COL_QUEST_TYPE))
                return 1
            t.set(int(row), COL_QUEST_TYPE, old.encode("latin-1"))
        open(NPC, "wb").write(t.to_bytes())
        os.remove(MANIFEST)
        print("restored %d cell(s)" % len(man["cells"]))
        return 0

    todo, problems = plan(t)
    for p in problems:
        print("   " + p)
    if a.verify:
        if todo or problems:
            print("VERIFY FAILED: %d row(s) not shared, %d problem(s)" % (len(todo), len(problems)))
            return 1
        print("ALL CHECKS PASSED -- every listed kill is shared with the party.")
        return 0
    if problems:
        print("ABORT, unresolved.")
        return 1
    if not todo:
        print("nothing to do.")
        return 0
    for row in todo:
        print("   LIST_NPC %d %s: col %d 0 -> 1" % (row, SHARED[row][0], COL_QUEST_TYPE))
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}}
    for row in todo:
        man["cells"].setdefault(str(row), t.get(row, COL_QUEST_TYPE).decode("latin-1"))
        t.set_i(row, COL_QUEST_TYPE, 1)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    open(NPC, "wb").write(t.to_bytes())
    todo2, problems2 = plan(stb.Stb(NPC))
    if todo2 or problems2:
        print("VERIFY FAILED after write")
        return 1
    print("wrote LIST_NPC.STB, verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
