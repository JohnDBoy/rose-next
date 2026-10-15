"""Boss skills that lock after a cast or two: give their cast counter an in-combat cooldown
(2026-10-15).

The Giant Fiery Snapper cast its skill once and then never again (user, testing the king /
skull HP pass). Its AI (RoseZA lineage) gates every cast on an AI variable -- cast only
while var0 <= 10, each cast adds 14 -- and the only events that lower it sit in the STOP
pattern, which runs while the monster idles. In a fight the counter never comes back down:
one cast, then nothing until the boss wanders again. With boss fights now 1.5-3 minutes,
that left the skill a one-off. scripts/../cast_lock audit (combat sim reading of every
.aip) found the same lock in these boss files (fixed here) and in ~40 regular monsters'
(the Oro Asper/Snapper families, Sikuku fighters, Yeti Riders ...; not touched).

Deliberately NOT changed: Executor Kera, the Ulverick bosses and the Hebarn officers
(ks_ / uv_ / ed_s_kera files). Their main attack (Kera Stun Blast) already resets in
combat; what stays capped is a set number of charges -- Dispel Buffs / Area Slow 5 per
fight, a low-HP self skill 4 -- which reads as intended.

The fix: one event first in the DAMAGED pattern, named EVENT_NAME: a 7% chance (user: "10%
looks better, even smaller -- 7% -- with raiders and 5+ people") to lower the counter by
DEC. The damaged pattern itself runs on ~40% of hits once the boss has a target, so that is
~2.8% per hit taken: with five players a cast every ~10-25 s, solo about a minute. Events
are first-match-wins, so this event costs the boss at most 7% of its other hit reactions.

    python scripts/fix-boss-cast-cooldowns.py --dry-run
    python scripts/fix-boss-cast-cooldowns.py
    python scripts/fix-boss-cast-cooldowns.py --verify
    python scripts/fix-boss-cast-cooldowns.py --restore

Restore removes the event by name (it does not copy files back), so it composes with
boost-boss-skills.py, which also edits the Snapper's and the Asper King's files. The server
reads .aip files: restart it (no bake needed, but the client is harmless to re-bake).
"""

import argparse
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from rosefmt import aip  # noqa: E402

AI_DIR = os.path.join(REPO, "data", "3DDATA", "AI")
EVENT_NAME = b"combat cooldown"
PCT = 7
DAMAGED = 3
COND_RANDOM, ACT_SET_VAR, OP_SUB = 7, 35, 7
# file: (bosses, counter variable, decrement)
FIXES = {
    "OR_giantsnapper1.aip": ("Giant Fiery Snapper", 0, 4),
    "OR_kingasper1.aip": ("Crowned Asper King", 0, 4),
    "OR_GMdevourer1.aip": ("Grand Master Devourer", 0, 4),
    "clownboss.aip": ("Wise Clown", 0, 1),
    "ed_heavygear.aip": ("Ikaness Mecha (and the Ikaness Heavygear elite)", 0, 1),
}


def kind(rec):
    return (aip.record_type(rec) & 0xFF) - 1


def ai_path(name):
    hit = [p for p in glob.glob(os.path.join(AI_DIR, "*")) if os.path.basename(p).lower() == name.lower()]
    if not hit:
        raise SystemExit(f"ABORT: {name} not found under {AI_DIR}")
    return hit[0]


def templates(pats):
    """A random-% condition and a set-AI-variable action from the file itself."""
    cond = act = None
    for _pn, evs in pats:
        for _en, conds, acts in evs:
            cond = cond or next((c for c in conds if kind(c) == COND_RANDOM), None)
            act = act or next((a for a in acts if kind(a) == ACT_SET_VAR), None)
    if cond is None or act is None:
        raise SystemExit("ABORT: no random-% condition / set-variable action to copy")
    return cond, act


def name32(b):
    return b.split(b"\0", 1)[0]


def has_event(pats):
    return any(name32(en) == EVENT_NAME for en, _c, _a in pats[DAMAGED][1])


def add_event(b, var, dec):
    header, title, pats, tail = aip.parse(b)
    if has_event(pats):
        return b, False
    cond, act = templates(pats)
    cond = bytearray(cond)
    struct.pack_into("<B", cond, 8, PCT)
    act = bytearray(act)
    struct.pack_into("<h2xiB", act, 8, var, dec, OP_SUB)
    pname, evs = pats[DAMAGED]
    ev = (EVENT_NAME.ljust(32, b"\0"), [bytes(cond)], [bytes(act)])
    pats[DAMAGED] = (pname, [ev] + list(evs))
    return aip.build(header, title, pats, tail), True


def drop_event(b):
    header, title, pats, tail = aip.parse(b)
    pname, evs = pats[DAMAGED]
    keep = [e for e in evs if name32(e[0]) != EVENT_NAME]
    if len(keep) == len(evs):
        return b, False
    pats[DAMAGED] = (pname, keep)
    return aip.build(header, title, pats, tail), True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    bad = 0
    for name, (who, var, dec) in FIXES.items():
        p = ai_path(name)
        b = open(p, "rb").read()
        h, t, pats, tail = aip.parse(b)
        if aip.build(h, t, pats, tail) != b:
            print(f"ABORT: {name} does not round-trip through the codec")
            return 1
        if args.restore:
            nb, changed = drop_event(b)
            if changed:
                open(p, "wb").write(nb)
            print(f"   {name:<24} {'event removed' if changed else 'not applied'}")
            continue
        if args.verify:
            ok = has_event(pats)
            bad += not ok
            print(f"   {name:<24} {'OK' if ok else 'MISSING'}  ({who})")
            continue
        nb, changed = add_event(b, var, dec)
        print(f"   {name:<24} var{var} -{dec} at {PCT}% per damaged event: "
              f"{'add' if changed else 'already there'}  ({who})")
        if changed and not args.dry_run:
            open(p, "wb").write(nb)
    if args.verify:
        print("ALL CHECKS PASSED" if not bad else f"VERIFY FAILED: {bad} file(s)")
        return 1 if bad else 0
    if args.dry_run:
        print("dry run: nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
