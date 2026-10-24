"""Fearsome Terrasaurus King: Charge becomes a telegraphed lunge down a strip (2026-10-24).

The first boss skill retrofitted with a ground telegraph after the Cerberus Lair
(import-cerberus.py, src/client/groundtelegraph.h). Charge (LIST_SKILL 3603, imported
by import-monster-skills.py) was a single-target strike (type 3, range 5 m, power
190) on a 1.4 s wind-up -- but its release clip, thornie_skill1, already throws the
whole body forward: the root travels ~240 model units between frames 23 and 29,
~11 m at the boss's size 450. The skill now matches what the animation shows:

    type 7, aimed frontal strip (io_skill.h SKILL_SCOPE_FRONTAL): 15 m x 7 m from
    the boss's centre toward where its target stood when the wind-up began
    (CObjCHAR::Casting_START) -- everyone in the strip is hit, nobody behind it.
    Range 10 m: it can open on a target at mid range instead of walking up first.
    Power 300 (was 190): dodgeable, so it hits harder (the user's rule from the
    Hellfire Breath). LIST_SKILL col 83 = 1: the strip is drawn while it winds up.

The wind-up is the telegraph, and the server applies the damage when the action
clip starts (Skill_START), so the clips are re-cut at the lunge, as the breath was:

    slot 6 (cast)    thornie_ChargeA (33 frames, the held charge pose) + thornie_skill1
                     frames 0-22 (the rear-back), joined: 56 frames, ~2.3 s at
                     natural speed -- no slow-motion
    slot 7 (action)  thornie_skill1 frames 23-60: the lunge, the hold, the hop back.
                     Its frame 3 carries the area event 24 (the client presents the
                     hits there, ~0.1 s after the server applied them); the old 35/25
                     strike events are cleared

The wind-up keeps skill1's event 74 two frames before the jump (casting effect 2,
FILE_EFFECT 1881, the authored charge moment) and ChargeA's event 44 (casting effect 0,
empty on this row). The new clips
are the king's own (LIST_NPC.CHR entry 2265, slots 6/7); every other thornie keeps the
originals. Fireball (slot 8/9) is untouched.

    python scripts/terrasaurus-charge.py --dry-run
    python scripts/terrasaurus-charge.py
    python scripts/terrasaurus-charge.py --verify
    python scripts/terrasaurus-charge.py --restore

Restore puts back the skill cells and the CHR slots; the two clip files and their
CHR motion entries stay (unreferenced, harmless). The manifest (build/terrasaurus-
charge/) records the original cells. Re-running import-monster-skills.py rewrites row
3603 -- run this script again after it. LIST_SKILL and LIST_NPC.CHR are read by both
the server and the client: restart the game server and re-bake.

Charge more often, at any HP (user, 2026-10-24, after the first test: "a fun
mechanic"). RoseZA's AI rolled Charge when hit (18%) only at 60% HP or more and paid for
it from the cast counter it shares with Fireball (AI var 0 <= 5, +1 a cast; the
in-combat cooldown on that counter is fix-boss-cast-cooldowns.py's, the same day), so a
fight saw two or three. The DAMAGED pattern's Charge event is replaced by two events of
ours, on a counter of its own (AI var 1, unused by this file; zeroed at spawn):

    "charge cooldown"  var1 >= 1 AND CHARGE_TICK%  -> var1 - 1     (first in the pattern)
    "charge"           CHARGE_PCT% AND var1 <= 0   -> cast Charge, var1 = CHARGE_GAP
                                                      (just before the first Fireball)

Events are first-match-wins, so the cooldown event only takes hit reactions while a
Charge is cooling down. Spacing is counted in DAMAGED runs (~40% of the hits the king
takes) -- the AI has no clock in combat -- so a group sees it more often than a solo
player. The original event is kept in the manifest and put back by --restore. The
server reads .aip files: a restart is enough for this part.
"""

import argparse
import json
import struct
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402
from rosefmt import aip, zmo  # noqa: E402

DATA = os.path.join(REPO, "data")
SKILL_STB = os.path.join(DATA, "3DDATA", "STB", "LIST_SKILL.STB")
NPC_CHR = os.path.join(DATA, "3DDATA", "NPC", "LIST_NPC.CHR")
BACKUP_DIR = os.path.join(REPO, "build", "terrasaurus-charge")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

KING = 2265                         # Fearsome Terrasaurus King (OR_THORNIE.AIP)
CHARGE = 3603
CAST_SLOT = 6                       # the AI casts Charge on nMotion 6; released on 7
LENGTH, WIDTH = 1500, 700           # cm: the lunge's ~11 m plus the head, the body's width
CELLS = {5: 7,                                  # type 7: an aimed area
         6: 1000,                               # range, cm
         8: LENGTH * 10000 + WIDTH,             # SKILL_SCOPE_FRONTAL
         9: 300,                                # power (magic formula, col 15 = 2)
         83: 1}                                 # SKILL_TELEGRAPH
SRC_HOLD = r"3Ddata\Motion\NPC\thornie\thornie_ChargeA.ZMO"
SRC_LUNGE = r"3Ddata\Motion\NPC\thornie\thornie_skill1.ZMO"
WINDUP = r"3Ddata\Motion\NPC\thornie\thornie_king_charge_windup.ZMO"
LUNGE = r"3Ddata\Motion\NPC\thornie\thornie_king_charge_lunge.ZMO"
SPLIT = 23                          # skill1's last still frame before the lunge
LUNGE_EVENTS = {3: 24}              # the area hit, mid-lunge
AI_FILE = r"3DDATA\AI\OR_THORNIE.AIP"
DAMAGED = 3                         # AI pattern: when hit
ACT_SKILL, SKILL_OFFSET = 24, 10    # AIACT24 cast skill; record type = number + 1
COND_RANDOM, COND_AI_VAR, ACT_SET_VAR = 7, 28, 35
OP_GE, OP_LE, OP_SET, OP_SUB = 2, 4, 5, 7
CHARGE_VAR = 1                      # AI var: Charge's own cooldown
CHARGE_PCT = 25                     # % a DAMAGED run casts Charge once it is ready
CHARGE_GAP = 3                      # cooldown steps after a Charge ...
CHARGE_TICK = 50                    # ... each taken at this % of DAMAGED runs
EV_COOLDOWN, EV_CHARGE = b"charge cooldown", b"charge"


def find_ci(rel):
    """The file for a data-relative path, matched case-insensitively per component."""
    cur = DATA
    for part in rel.replace("\\", "/").split("/"):
        hit = [f for f in os.listdir(cur) if f.lower() == part.lower()] if os.path.isdir(cur) else []
        cur = os.path.join(cur, hit[0] if hit else part)
    return cur


def clips():
    """{data-relative path: bytes} for the king's two clips, built from the originals."""
    hold = open(find_ci(SRC_HOLD), "rb").read()
    src = open(find_ci(SRC_LUNGE), "rb").read()
    ev = zmo.events(src)[1]
    if not ev or ev[21] != 74 or ev[24] != 35 or ev[26] != 25 or zmo.read_header(src)[1] != 61:
        raise SystemExit(f"{SRC_LUNGE} is not the 61-frame clip with events 74/35/25 at "
                         "21/24/26 this was cut for -- refusing")
    windup = zmo.joined(hold, zmo.sliced(src, 0, SPLIT))
    lunge = zmo.sliced(src, SPLIT, 61)
    changes = {i: 0 for i, e in enumerate(zmo.events(lunge)[1]) if e}
    changes.update(LUNGE_EVENTS)
    return {WINDUP: windup, LUNGE: zmo.with_events(lunge, changes)}


def motion_index(chr_, rel, add):
    key = rel.encode("latin-1")
    hit = [i for i, m in enumerate(chr_.motions) if m.lower() == key.lower()]
    if hit:
        return hit[0]
    if not add:
        return None
    chr_.motions.append(key)
    return len(chr_.motions) - 1


def king_anims(chr_, add):
    """The king's anims with the new clips in slots 6/7 (None if they are not listed)."""
    want = {CAST_SLOT: motion_index(chr_, WINDUP, add), CAST_SLOT + 1: motion_index(chr_, LUNGE, add)}
    if None in want.values():
        return None
    anims = chr_.chars[KING]["anims"]
    if {s for s, _i in anims} & set(want) != set(want):
        raise SystemExit(f"LIST_NPC.CHR entry {KING} has no slot {CAST_SLOT}/{CAST_SLOT + 1} -- refusing")
    return [(s, want.get(s, i)) for s, i in anims]


def kind(rec):
    return (aip.record_type(rec) & 0xFF) - 1


def charge_event(pats):
    """Index of the one DAMAGED event that casts Charge."""
    hits = [i for i, (_n, _c, acts) in enumerate(pats[DAMAGED][1])
            if any(kind(a) == ACT_SKILL and struct.unpack_from("<h", a, SKILL_OFFSET)[0] == CHARGE
                   for a in acts)]
    if len(hits) != 1:
        raise SystemExit(f"{AI_FILE}: {len(hits)} DAMAGED events cast {CHARGE}, expected 1 -- refusing")
    return hits[0]


def name32(b):
    return b.split(b"\0", 1)[0]


def records(pats):
    """A random-% and an AI-variable condition and a set-variable action from the file."""
    out = {}
    for _pn, evs in pats:
        for _en, conds, acts in evs:
            for c in conds:
                out.setdefault(("c", kind(c)), c)
            for a in acts:
                out.setdefault(("a", kind(a)), a)
    try:
        return out[("c", COND_RANDOM)], out[("c", COND_AI_VAR)], out[("a", ACT_SET_VAR)]
    except KeyError:
        raise SystemExit(f"{AI_FILE}: no random / AI-variable / set-variable record to copy")


def var_rec(template, var, value, op):
    r = bytearray(template)
    struct.pack_into("<h2xiB", r, 8, var, value, op)
    return bytes(r)


def pct_rec(template, pct):
    r = bytearray(template)
    struct.pack_into("<B", r, 8, pct)
    return bytes(r)


def is_ours(ev):
    return name32(ev[0]) in (EV_COOLDOWN, EV_CHARGE)


def casts(ev, skill=None):
    return any(kind(a) == ACT_SKILL and (skill is None or
                                         struct.unpack_from("<h", a, SKILL_OFFSET)[0] == skill)
               for a in ev[2])


def rewired(b):
    """(new bytes, (index, original event)): the Charge event replaced by ours."""
    header, title, pats, tail = aip.parse(b)
    rnd, avar, setv = records(pats)
    pname, evs = pats[DAMAGED]
    evs = list(evs)
    k = charge_event(pats)
    orig = evs.pop(k)
    cast = next(a for a in orig[2] if kind(a) == ACT_SKILL)
    charge = (EV_CHARGE.ljust(32, b"\0"),
              [pct_rec(rnd, CHARGE_PCT), var_rec(avar, CHARGE_VAR, 0, OP_LE)],
              [cast, var_rec(setv, CHARGE_VAR, CHARGE_GAP, OP_SET)])
    cool = (EV_COOLDOWN.ljust(32, b"\0"),
            [var_rec(avar, CHARGE_VAR, 1, OP_GE), pct_rec(rnd, CHARGE_TICK)],
            [var_rec(setv, CHARGE_VAR, 1, OP_SUB)])
    first_cast = next(i for i, ev in enumerate(evs) if casts(ev))
    evs.insert(first_cast, charge)
    evs.insert(0, cool)
    pats[DAMAGED] = (pname, evs)
    return aip.build(header, title, pats, tail), (k, orig)


def unwired(b, k, orig):
    header, title, pats, tail = aip.parse(b)
    pname, evs = pats[DAMAGED]
    evs = [ev for ev in evs if not is_ours(ev)]
    evs.insert(k, orig)
    pats[DAMAGED] = (pname, evs)
    return aip.build(header, title, pats, tail)


def is_rewired(b):
    _h, _t, pats, _tail = aip.parse(b)
    evs = pats[DAMAGED][1]
    return (sorted(name32(ev[0]) for ev in evs if is_ours(ev)) == sorted([EV_COOLDOWN, EV_CHARGE])
            and [name32(ev[0]) for ev in evs if casts(ev, CHARGE)] == [EV_CHARGE])


def ev_json(ev):
    return [ev[0].hex(), [c.hex() for c in ev[1]], [a.hex() for a in ev[2]]]


def ev_from(j):
    return (bytes.fromhex(j[0]), [bytes.fromhex(c) for c in j[1]], [bytes.fromhex(a) for a in j[2]])


def cast_ms(blob):
    fps, frames, _ch = zmo.read_header(blob)
    return 1000 * frames // fps


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    raw_stb, raw_chr = open(SKILL_STB, "rb").read(), open(NPC_CHR, "rb").read()
    stb, chr_ = oro.Stb(SKILL_STB), oro.Chr(NPC_CHR)
    if stb.to_bytes() != raw_stb or chr_.to_bytes() != raw_chr:
        print("ABORT: a codec does not round-trip LIST_SKILL.STB / LIST_NPC.CHR byte-for-byte")
        return 1
    if stb.get(CHARGE, 0).strip() != b"Charge":
        print(f"ABORT: LIST_SKILL {CHARGE} is not Charge")
        return 1
    if KING >= len(chr_.chars) or not chr_.chars[KING]:
        print(f"ABORT: LIST_NPC.CHR has no entry {KING}")
        return 1
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else None
    ai_file = find_ci(AI_FILE)
    ai_raw = open(ai_file, "rb").read()
    h, t, pats, tail = aip.parse(ai_raw)
    if aip.build(h, t, pats, tail) != ai_raw:
        print(f"ABORT: {AI_FILE} does not round-trip through the codec")
        return 1

    if args.restore:
        if not man:
            print("nothing to restore")
            return 0
        if man.get("charge_ai"):
            if is_rewired(ai_raw):
                k, ev = man["charge_ai"]
                open(ai_file, "wb").write(unwired(ai_raw, k, ev_from(ev)))
            print(f"restored the Charge event of {AI_FILE}")
        for c, v in man["cells"].items():
            stb.set(CHARGE, int(c), v.encode("latin-1"))
        chr_.chars[KING]["anims"] = [tuple(a) for a in man["anims"]]
        stb.save(False, keep_backup=False)
        chr_.save(False, keep_backup=False)
        os.remove(MANIFEST)
        print(f"restored LIST_SKILL {CHARGE} cells {sorted(map(int, man['cells']))} and "
              f"LIST_NPC.CHR entry {KING} slots {CAST_SLOT}/{CAST_SLOT + 1}")
        return 0

    built = clips()
    if args.verify:
        ok = man is not None
        for c, v in CELLS.items():
            if stb.i(CHARGE, c) != v:
                print(f"  LIST_SKILL {CHARGE} col {c} = {stb.get(CHARGE, c)!r}, want {v}")
                ok = False
        for rel, blob in built.items():
            if not os.path.isfile(find_ci(rel)) or open(find_ci(rel), "rb").read() != blob:
                print(f"  {rel} missing or not the expected clip")
                ok = False
        anims = king_anims(chr_, add=False)
        if anims is None or anims != chr_.chars[KING]["anims"]:
            print(f"  LIST_NPC.CHR entry {KING} slots {CAST_SLOT}/{CAST_SLOT + 1} are not the new clips")
            ok = False
        if not is_rewired(ai_raw) or not (man or {}).get("charge_ai"):
            print(f"  {AI_FILE}: Charge is not on its own counter")
            ok = False
        print("ALL CHECKS PASSED -- the king charges down a telegraphed strip." if ok else "VERIFY FAILED")
        return 0 if ok else 1
    if man:
        if man.get("charge_ai"):
            print("already applied; --restore first to redo")
            return 0
        return rewire(man, ai_file, ai_raw, args.dry_run)

    before = {c: stb.get(CHARGE, c) for c in CELLS}
    print(f"LIST_SKILL {CHARGE} Charge:")
    for c, v in CELLS.items():
        print(f"    col {c:2d}  {before[c].decode('latin-1') or '(blank)':>10s} -> {v}")
    for rel, blob in built.items():
        _b, ev = zmo.events(blob)
        print(f"    {os.path.basename(rel):34s} {zmo.read_header(blob)[1]:3d} frames, "
              f"{cast_ms(blob)} ms, events {[(i, e) for i, e in enumerate(ev) if e]}")
    print(f"    telegraph: {LENGTH / 100:g} x {WIDTH / 100:g} m strip for ~{cast_ms(built[WINDUP])} ms")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    json.dump(dict(cells={str(c): v.decode("latin-1") for c, v in before.items()},
                   anims=chr_.chars[KING]["anims"]), open(MANIFEST, "w"), indent=1)
    for rel, blob in built.items():
        path = find_ci(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(blob)
    for c, v in CELLS.items():
        stb.set(CHARGE, c, str(v))
    chr_.chars[KING]["anims"] = king_anims(chr_, add=True)
    stb.save(False, keep_backup=False)
    chr_.save(False, keep_backup=False)
    print(f"wrote LIST_SKILL {CHARGE}, LIST_NPC.CHR entry {KING} and 2 clips (undo: --restore)")
    return rewire(json.load(open(MANIFEST)), ai_file, ai_raw, False)


def rewire(man, ai_file, ai_raw, dry):
    """Charge on its own counter, at any HP (the docstring's two events)."""
    if is_rewired(ai_raw):
        raise SystemExit(f"{AI_FILE} already has our Charge events but the manifest does not")
    new, (k, orig) = rewired(ai_raw)
    print(f"{AI_FILE}: DAMAGED event {k} (Charge 18%, HP >= 60%, shared counter) -> "
          f"Charge {CHARGE_PCT}% on var{CHARGE_VAR}, {CHARGE_GAP} cooldown steps at {CHARGE_TICK}%")
    if dry:
        print("dry run: nothing written")
        return 0
    open(ai_file, "wb").write(new)
    man["charge_ai"] = [k, ev_json(orig)]
    json.dump(man, open(MANIFEST, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
