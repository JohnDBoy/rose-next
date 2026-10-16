"""The Terror Knight taunts: the Bourgeois's guard summon pulls monsters off its owner
(2026-10-16).

The class sweep found the Bourgeois's summons worth 6-21% of its damage and drawing almost
no attacks (monsters spent 0-6% of their time on them): a monster turns on a summon only
when its own AI says so. For the class whose identity is its summons, the guard now does
what a guard does (user: "it would be awesome to give the terror knight a taunt").

LIST_SKILL: a new row (after the last one), a copy of the Knight's Taunt rank 3 (row 413:
type 9, status 56 Taunted, 25 m) for the summon alone, so the Knight's skill is untouched:
  * duration 13 s (user; the Knight's is 25 s), so a monster can slip back to the owner and
    Ctrl+click matters;
  * success 120 (413: 90). A summon's INT is its level, which is its owner's level
    (CObjMOB::Get_INT, CObjSUMMON::SetCallerOBJ), so the roll is level against the
    monster's RES*0.6 + AVOID: 120 lands ~always on regular monsters and ~93% on the Giant
    Fiery Snapper at 237 (90 gave 57-100% / 69%);
  * the learning cells (rank, required level, tab, MP cost, requirements) are left out like
    on every monster skill; the name key stays LSkill0411, so players see "Taunt".
The server already supports a taunting summon: a landed Taunt makes the monster attack the
caster (Skill_ApplyIngSTATUS -> SetCMD_RUNnATTACK) and, for its duration, its own AI cannot
retarget anyone else (Is_TauntSTATUS); walking (an AI move) breaks it.

sur_guard.aip (only the ten Terror Knight rows use it) gets three named events:
  * "tk taunt engage" (STOP pattern, before "owner has a target -> attack owner's target"):
    joining the owner's fight from idle, it attacks the owner's target and taunts it;
  * "tk taunt order" (ATTACK-MOVE pattern, after the no-owner suicide): AI variable 3 set
    means its owner just Ctrl+clicked a monster (CZoneTHREAD::CommandSummons_Attack sets it
    and runs this pattern once, SUMMON_ORDER_AI_VAR); it taunts that monster and clears it;
  * "tk taunt hold" (DAMAGED pattern, after the Dread Sweep events, so its own skill keeps
    its odds): 60% to taunt its target again -- of a pattern that runs on 30% of the hits
    it takes, about a third of which get this far -- roughly every 10-20 s while the monster
    is on it. It also ticks Dread Sweep's cooldown (var 1 -4), which the file's last,
    "always" event would otherwise have done.
The cast plays the Knight's own skill motion slot (8, Dread Sweep's).

    python scripts/terror-knight-taunt.py --dry-run
    python scripts/terror-knight-taunt.py
    python scripts/terror-knight-taunt.py --verify
    python scripts/terror-knight-taunt.py --restore

Manifest in build/terror-knight-taunt/: restore blanks the row (it stays, harmless, as with
boost-boss-skills.py; a re-run reuses trailing blank rows) and removes the events by name. The server reads both LIST_SKILL and
the .aip: restart it (needs the CommandSummons_Attack change for "tk taunt order"); re-bake
for the client to name the skill.
"""

import argparse
import glob
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402
from rosefmt import aip  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB", "LIST_SKILL.STB")
AI_DIR = os.path.join(REPO, "data", "3DDATA", "AI")
AI_FILE = "sur_guard.aip"
MANIFEST = os.path.join(REPO, "build", "terror-knight-taunt", "manifest.json")

SOURCE = 413                      # Taunt rank 3
LABEL = "Taunt (Terror Knight)"
DURATION_S, SUCCESS = 13, 120
C_LABEL, C_FIRST, C_SUCCESS, C_DURATION = 0, 1, 13, 14
LEARN_COLS = (2, 3, 4, 16, 17, 39, 40, 71, 72, 73)   # absent on monster skills
DREAD_SWEEP = 3031

STOP, ATTACK_MOVE, DAMAGED = 1, 2, 3
COND_RANDOM, COND_OWNER_TARGET, COND_AI_VAR = 7, 22, 28
ACT_CAST, ACT_OWNER_TARGET, ACT_SET_VAR = 24, 31, 35
ORDER_VAR = 3                     # CObjSUMMON::SUMMON_ORDER_AI_VAR
HOLD_PCT = 60
OP_EQ, OP_SET = 0, 5
CAST_AT_TARGET = 1                # AIACT24 btTarget: the current attack target
EVENTS = (b"tk taunt engage", b"tk taunt order", b"tk taunt hold")


def kind(rec):
    return (aip.record_type(rec) & 0xFF) - 1


def name32(b):
    return b.split(b"\0", 1)[0]


def ai_path():
    hit = [p for p in glob.glob(os.path.join(AI_DIR, "*")) if os.path.basename(p).lower() == AI_FILE]
    if not hit:
        raise SystemExit(f"ABORT: {AI_FILE} not found under {AI_DIR}")
    return hit[0]


def first(pats, want, where):
    for _pn, evs in pats:
        for _en, conds, acts in evs:
            for r in conds if where == "cond" else acts:
                if kind(r) == want:
                    return bytes(r)
    raise SystemExit(f"ABORT: no {where} {want} in {AI_FILE} to copy")


def dread_sweep_cast(pats):
    for _pn, evs in pats:
        for _en, _c, acts in evs:
            for a in acts:
                if kind(a) == ACT_CAST and struct.unpack_from("<h", a, 10)[0] == DREAD_SWEEP:
                    return bytes(a)
    raise SystemExit("ABORT: the Dread Sweep cast is not in the file")


def add_events(b, row):
    header, title, pats, tail = aip.parse(b)
    if any(name32(e[0]) in EVENTS for _p, evs in pats for e in evs):
        return b, False
    cast = bytearray(dread_sweep_cast(pats))
    struct.pack_into("<B", cast, 8, CAST_AT_TARGET)
    struct.pack_into("<h", cast, 10, row)
    cast = bytes(cast)
    owner_target = first(pats, COND_OWNER_TARGET, "cond")
    attack_owner_target = first(pats, ACT_OWNER_TARGET, "act")
    var_is = bytearray(first(pats, COND_AI_VAR, "cond"))
    struct.pack_into("<h2xiB", var_is, 8, ORDER_VAR, 1, OP_EQ)
    var_set = bytearray(first(pats, ACT_SET_VAR, "act"))
    struct.pack_into("<h2xiB", var_set, 8, ORDER_VAR, 0, OP_SET)
    rnd = bytearray(first(pats, COND_RANDOM, "cond"))
    struct.pack_into("<B", rnd, 8, HOLD_PCT)
    tick = next(a for _e, _c, acts in pats[DAMAGED][1] for a in acts
                if kind(a) == ACT_SET_VAR and struct.unpack_from("<h2xiB", a, 8) == (1, 4, 7))

    def ev(name, conds, acts):
        return (name.ljust(32, b"\0"), [bytes(c) for c in conds], [bytes(a) for a in acts])

    # STOP: before the plain "owner has a target -> attack owner's target"
    pn, evs = pats[STOP]
    i = next(k for k, (_n, c, a) in enumerate(evs)
             if any(kind(x) == COND_OWNER_TARGET for x in c)
             and any(kind(x) == ACT_OWNER_TARGET for x in a))
    evs = list(evs)
    evs.insert(i, ev(EVENTS[0], [owner_target], [attack_owner_target, cast]))
    pats[STOP] = (pn, evs)
    # ATTACK-MOVE: right after the no-owner suicide; DAMAGED: after the last Dread Sweep
    dmg = pats[DAMAGED][1]
    after_sweep = 1 + max(k for k, (_n, _c, acts) in enumerate(dmg)
                          if any(kind(a) == ACT_CAST and struct.unpack_from("<h", a, 10)[0]
                                 == DREAD_SWEEP for a in acts))
    for pat, at, e in ((ATTACK_MOVE, 1, ev(EVENTS[1], [var_is], [cast, var_set])),
                       (DAMAGED, after_sweep, ev(EVENTS[2], [rnd], [cast, tick]))):
        pn, evs = pats[pat]
        evs = list(evs)
        evs.insert(at, e)
        pats[pat] = (pn, evs)
    return aip.build(header, title, pats, tail), True


def drop_events(b):
    header, title, pats, tail = aip.parse(b)
    n = 0
    for k, (pn, evs) in enumerate(pats):
        keep = [e for e in evs if name32(e[0]) not in EVENTS]
        n += len(evs) - len(keep)
        pats[k] = (pn, keep)
    return aip.build(header, title, pats, tail), n


def count_events(b):
    _h, _t, pats, _tail = aip.parse(b)
    return sum(1 for _p, evs in pats for e in evs if name32(e[0]) in EVENTS)


def plan_row(stb, row):
    cells = {}
    for c in range(stb.cols):
        v = stb.get(SOURCE, c).strip()
        if c in LEARN_COLS:
            v = b""
        cells[c] = v
    cells[C_LABEL] = LABEL.encode()
    cells[C_FIRST] = str(row).encode()
    cells[C_SUCCESS] = str(SUCCESS).encode()
    cells[C_DURATION] = str(DURATION_S).encode()
    return cells


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
    ap_path = ai_path()
    ab = open(ap_path, "rb").read()
    h, t, pats, tail = aip.parse(ab)
    if aip.build(h, t, pats, tail) != ab:
        print(f"ABORT: {AI_FILE} does not round-trip through the codec")
        return 1
    man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.isfile(MANIFEST) else None

    if args.restore:
        if not man:
            print("not applied")
            return 0
        row = man["row"]
        for c in range(stb.cols):
            stb.set(row, c, b"")
        open(STB, "wb").write(stb.to_bytes())
        nb, n = drop_events(ab)
        open(ap_path, "wb").write(nb)
        os.remove(MANIFEST)
        print(f"restored: row {row} blanked, {n} event(s) removed from {AI_FILE}")
        return 0
    if args.verify:
        if not man:
            print("VERIFY FAILED: not applied")
            return 1
        row = man["row"]
        want = plan_row(stb, row)
        bad = [c for c, v in want.items() if stb.get(row, c).strip() != v]
        n = count_events(ab)
        print(f"row {row}: {'OK' if not bad else f'{len(bad)} cell(s) differ: {bad}'}; "
              f"{AI_FILE}: {n}/{len(EVENTS)} events")
        ok = not bad and n == len(EVENTS)
        print("ALL CHECKS PASSED" if ok else "VERIFY FAILED")
        return 0 if ok else 1
    if man:
        print(f"already applied (row {man['row']}); --restore first to redo")
        return 0

    # the first of the trailing blank rows (a restore leaves its row blank), else a new one
    row = stb.rows
    while row - 1 > SOURCE and not stb.occupied(row - 1):
        row -= 1
    cells = plan_row(stb, row)
    nb, changed = add_events(ab, row)
    print(f"LIST_SKILL {SOURCE} (Taunt rank 3) -> new row {row} '{LABEL}': "
          f"success {SUCCESS}, {DURATION_S} s, no learning cells")
    print(f"{AI_FILE}: {'add' if changed else 'already has'} {', '.join(e.decode() for e in EVENTS)}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    stb.grow_to(row + 1)
    for c, v in cells.items():
        stb.set(row, c, v)
    open(STB, "wb").write(stb.to_bytes())
    if changed:
        open(ap_path, "wb").write(nb)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(dict(row=row), open(MANIFEST, "w"), indent=1)
    print(f"wrote row {row} and {AI_FILE} (undo: --restore)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
