"""Drop the hidden 20-kill counter from the second-job Stone Golem relic steps.

Three second-job chains send the player to hunt Stone Golems (LIST_NPC 164,
lv 74) in the Gorge of Silence for one relic each: quest 1059 Token of
Friendship, 1072 Phoenix Writing Quill, 1078 Lillith's Scales. The golem's
death event (LIST_NPC col 41 = ``1059-31``) runs a trigger chain in
``QN-164.QSD``, and for each of the three quests it held a pair:

* ``<q>-31`` -- quest var 2 < 20  ->  var 2 += 1          (the counter)
* ``<q>-32`` -- 10 % roll, var 2 >= 20, relic < 1  ->  give the relic

A chain stops at the first trigger that succeeds
(``CQuestDATA::CheckQUEST``, ``io_quest.cpp``), so for the first 20 kills the
counter succeeded and the drop trigger never ran. Nothing in the quest log
says so, and the quest felt broken until kill 21. The fourth chain, 1066
(Hairpin of Oblivious x5, 15 % a kill), never had a counter.

The patch is two i16 pokes per pair, the trigger names and chain left as they
are (no LIST_NPC edit): the counter becomes ``var 2 < 0``, which never passes,
and the drop becomes ``var 2 >= 0``, which always does. A player part-way
through the counter drops straight into the 10 % phase. Average kills for one
relic go from ~30 to ~10.

Patched everywhere the pairs appear:

* ``QN-164.QSD`` pattern 1 (``1059-31``..): Stone Golem 164, the Gorge spawn.
* ``QN-164.QSD`` pattern 2 (``1059-31-0``..): reached from ``135-31``, the
  death event of the other two "Stone Golem" rows (254, 1381).
* ``QN-762.QSD``: the same names again for Supreme Stone Golem 762, whose
  col 41 is empty, so it never fires. Trigger names are global and the loader
  keeps whichever file loads first, so it is patched too rather than left as a
  second copy that could win.

The other readers of quest var 2 were checked: there are none (the turn-in
triggers in QJx11-06 check the relic item only).

The QSD is read by both sides: the client evaluates the death event (it rolls
the 10 %, ``F_QSTCOND010`` is client-only) and the server re-checks it. So
re-bake **and** restart the game server.

Idempotent, --dry-run, verifies after writing. Backups in
build/fix-second-job-golem-counter/.
"""
import argparse
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt import qsd  # noqa: E402
from rosefmt.binio import read_file  # noqa: E402

QUEST_DIR = os.path.join(ROOT, "data", "3DDATA", "QUESTDATA")
FILES = {"QN-164.QSD": ("", "-0"), "QN-762.QSD": ("",)}  # file -> name suffixes
BACKUP_DIR = os.path.join(ROOT, "build", "fix-second-job-golem-counter")

QUESTS = (1059, 1072, 1078)
COND_QUEST_VAR = 1
COUNTER_VAR = 2
OP_GE, OP_LT = 2, 3
OLD_LIMIT, NEW_LIMIT = 20, 0


def targets(suffixes):
    """{trigger name: expected btOp} for every counter / drop trigger."""
    out = {}
    for q in QUESTS:
        for suffix in suffixes:
            out["%d-31%s" % (q, suffix)] = OP_LT
            out["%d-32%s" % (q, suffix)] = OP_GE
    return out


def var_checks(blob, want):
    """[(trigger, offset of nValue, nValue, btOp)] for the quest-var-2 checks."""
    out = []
    base = 0
    for name, ents, raw in qsd.walk(blob):
        base = blob.index(raw, base)
        if name not in want:
            base += len(raw)
            continue
        at = base + 1 + 8 + 2 + struct.unpack_from("<h", raw, 9)[0]
        for etype, ent in ents:
            if etype == COND_QUEST_VAR:
                cnt, var_no, var_type, value, op = struct.unpack_from("<iHHhB", ent, 8)
                if cnt == 1 and var_no == COUNTER_VAR and var_type == 0:
                    out.append((name, at + 16, value, op))
            at += len(ent)
        base += len(raw)
    return out


def patch(blob, want):
    """Return (new blob, [(trigger, old, new)], {trigger names seen})."""
    b = bytearray(blob)
    changes = []
    found = set()
    for name, off, value, op in var_checks(blob, want):
        if op != want[name]:
            raise SystemExit("%s: unexpected comparison op %d" % (name, op))
        found.add(name)
        if value == OLD_LIMIT:
            struct.pack_into("<h", b, off, NEW_LIMIT)
            changes.append((name, value, NEW_LIMIT))
        elif value != NEW_LIMIT:
            raise SystemExit("%s: unexpected limit %d" % (name, value))
    return bytes(b), changes, found


def verify(path, want):
    problems = []
    blob = read_file(path)
    ok, _ = qsd.parse_ok(blob)
    if not ok:
        problems.append("%s: does not parse" % path)
    _, changes, found = patch(blob, want)
    if changes:
        problems.append("%s: %d checks still at %d" % (path, len(changes), OLD_LIMIT))
    if found != set(want):
        problems.append("%s: missing %s" % (path, sorted(set(want) - found)))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    problems = []
    for fn, suffixes in FILES.items():
        want = targets(suffixes)
        path = os.path.join(QUEST_DIR, fn)
        blob = read_file(path)
        new, changes, found = patch(blob, want)
        missing = set(want) - found
        if missing:
            raise SystemExit("%s: triggers not found: %s" % (fn, sorted(missing)))
        for name, old, value in changes:
            print("%s %-10s var %d limit %d -> %d" % (fn, name, COUNTER_VAR, old, value))
        if not changes:
            print("%s: already patched" % fn)
            continue
        if args.dry_run:
            continue
        os.makedirs(BACKUP_DIR, exist_ok=True)
        bak = os.path.join(BACKUP_DIR, fn)
        if not os.path.exists(bak):
            shutil.copyfile(path, bak)
        with open(path, "wb") as fh:
            fh.write(new)
        problems += verify(path, want)

    if args.dry_run:
        print("dry run: nothing written")
    elif problems:
        raise SystemExit("\n".join(problems))
    else:
        print("verified. Re-bake and restart the game server.")


if __name__ == "__main__":
    main()
