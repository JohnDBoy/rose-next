"""Boss skills that lock after a cast or two: give their cast counter an in-combat cooldown
(2026-10-15).

The Giant Fiery Snapper cast its skill once and then never again (user, testing the king /
skull HP pass). Its AI (RoseZA lineage) gates every cast on an AI variable -- cast only
while var0 <= 10, each cast adds 14 -- and the only events that lower it sit in the STOP
pattern, which runs while the monster idles. In a fight the counter never comes back down:
one cast, then nothing until the boss wanders again. With boss fights now 1.5-3 minutes,
that left the skill a one-off. An audit of every .aip (the combat sim's reader) found the
same lock in five boss files and in 31 regular monsters' files (the Oro Asper/Snapper
families, Sikuku fighters / trackers, Hooks, Yeti Riders, Beeberu, a clan-field Tirwin, the
Karkia ents); all are fixed here (user: "only fair that the game actually works").
Not fixed, by design: the Sikuku prison family's one-time self-buff (Prison Slumber, the
Cannibal buff: the counter is *set* to 1 and the cast needs it < 1 -- once per fight), and
the Sikuku Infiltrator's 5 Dispel / Slow charges.

Added 2026-10-24: the Fearsome Terrasaurus King (OR_THORNIE.AIP), missed by that audit
(each cast adds only 1, against var0 <= 5) and found in game -- six casts at the pull, then
none until it leashed home or killed someone. Its counter gets one cast back per cooldown
event (DEC 1).

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
    # -- regular monsters (user: "it's only fair that the game actually works"): the same
    # idle-only counter (+13/+14 per cast, <= 10; Beeberu +18 <= 20; Tirwin 397 +10 <= 5;
    # +1 <= 5 for the Karkia ents)
    "OR_assassinasper1.aip": ("Hooded Asper Assassin", 0, 4),
    "OR_babyasper1.aip": ("Baby Desert Asper", 0, 4),
    "OR_barbedsnapper1.aip": ("Barbed Snapper", 0, 4),
    "OR_brutesnapper1.aip": ("Barbed Snapper Brute", 0, 4),
    "OR_captainsnapper1.aip": ("Fiery Snapper Captain", 0, 4),
    "OR_commanderasper1.aip": ("Crowned Asper Commander", 0, 4),
    "OR_crownedasper1.aip": ("Crowned Asper", 0, 4),
    "OR_desertasper1.aip": ("Desert Asper", 0, 4),
    "OR_elderasper1.aip": ("Elder Desert Asper", 0, 4),
    "OR_fierysnapper1.aip": ("Fiery Snapper", 0, 4),
    "OR_guardsnapper1.aip": ("Venerable Snapper Guard", 0, 4),
    "OR_healersnapper1.aip": ("Venerable Snapper Healer", 0, 4),
    "OR_hoodedasper1.aip": ("Hooded Asper", 0, 4),
    "OR_hunterasper1.aip": ("Hooded Asper Hunter", 0, 4),
    "OR_leaderasper1.aip": ("Hooded Asper Leader", 0, 4),
    "OR_leadersnapper1.aip": ("Fiery Snapper Leader", 0, 4),
    "OR_vensnapper1.aip": ("Venerable Snapper", 0, 4),
    "OR_viciousasper1.AIP": ("Vicious Desert Asper", 0, 4),
    "OR_warriorsnapper1.aip": ("Barbed Snapper Warrior", 0, 4),
    "OR_wisesnapper1.aip": ("Wise Venerable Snapper", 0, 4),
    "qst_venasper1.aip": ("Venomous Hooded Asper", 0, 4),
    "ed_fighter.aip": ("Sikuku Spearman / Leader / Fighter / Veteran", 0, 4),
    "ed_hooker.aip": ("Hook, King Hook", 0, 4),
    "ed_tracer.aip": ("Sikuku Hunter / Tracker / Captain / Butcher", 0, 4),
    "at_rider1.aip": ("Yeti Rider", 0, 4),
    "kfgdg2549.aip": ("Beeberu", 0, 5),
    "CLAN_MOB8.aip": ("Tirwin 397 (Luna Clan Field, Forgotten Temple B1)", 1, 3),
    "OR_THORNIE.AIP": ("Fearsome Terrasaurus King", 0, 1),
    "ed_treeboss.aip": ("Cursed Ant Vagabond", 0, 1),
    "kak_deadent.aip": ("Dark Tower", 0, 1),
    "kak_ent.aip": ("Element Battler", 0, 1),
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
