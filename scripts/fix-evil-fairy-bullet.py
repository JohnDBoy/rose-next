"""Make the Evil Fairy's thrown gem visible and land on time.

The Evil Fairy (LIST_NPC 2725, Jrose's Arua quest boss) fights with weapon 1156,
an invisible placeholder whose only job is its bullet: LIST_WEAPON col 38 ->
LIST_EFFECT 631 -> FILE_EFFECT 1461 ``QUESTARUA_GEM.EFT``. Its normal attack is
therefore a projectile (``presentation_kind`` ProjectileImpact): the damage digit
waits for the bullet to reach you. Alpha report (2026-10-13): run away and the
Fairy plays her throw, nothing comes after you, then damage appears out of
nowhere -- and even in melee nothing is seen between the throw and the hit.

Every row and file is byte-identical to Jrose's; the shot was authored as two
things that do not travel together:

* **The damage carrier is invisible and slow.** The ``.eft``'s mesh is
  ``_UNBULLET_01.ZMS`` with ``_BLACK_01.DDS`` (an additive black quad: nothing),
  and LIST_EFFECT 631 col 15 (speed) is 1000 cm/s -- the slowest bullet in the
  game (140 direction bullets run at 3000). A running player is 6-9 m/s, so the
  homing carrier barely gains, and the queued hit lands when the player *stops*:
  the 2026-10-13 log has two swings at 12:01:06/08 presented together at
  12:01:13, one second after the avatar stood still.
* **The visible gem does not follow it.** ``QESTARUA_GEM.PTL`` sequence 0 (a
  1.3 m animated gem sprite, 8 s life, one particle) is ``update_coord`` WORLD
  with its own velocity of 2000 cm/s along the emitter's facing: a
  self-propelled straight shot at where the player *was* when it left. It is
  born at the bullet's launch point -- the skeleton's root dummy, i.e. the
  pelvis inside a scale-200 body -- and flies off in a line whatever the carrier
  does. The only particle that rides the carrier (sequence 1, a yellow glow,
  LOCAL_WORLD) is emitted once and fades out within 2 s.

The fix glues the gem to the carrier and speeds the carrier up:

* LIST_EFFECT 631 col 15: 1000 -> 3000 (the house speed for a direction bullet).
* QESTARUA_GEM.PTL and QESTARUA_GEM2.PTL (identical; the ``.eft`` uses both),
  sequence 0: ``update_coord`` WORLD -> LOCAL_WORLD and its velocity event
  zeroed, so the gem rides the homing bullet and is deleted with it on impact
  (``CBulletDIRECTION::Proc`` returns 0 on the hit; nothing is left on the
  target). Nothing else uses these files or row 631 (weapon 1156 only).

The invisible weapon model added by ``fix-spawned-npc-gaps.py`` is unrelated:
the bullet and its timing come from the weapon *row*, which the Fairy has had
since its import.

    python scripts/fix-evil-fairy-bullet.py --dry-run
    python scripts/fix-evil-fairy-bullet.py
    python scripts/fix-evil-fairy-bullet.py --verify
    python scripts/fix-evil-fairy-bullet.py --restore

Client-only data: re-bake the VFS. Undo is per cell for the STB and per file
(hash-checked) for the two PTLs; backups in build/evil-fairy-bullet/.
"""

import argparse
import base64
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import Stb, ptl  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(REPO, "data")
EFFECT_STB = os.path.join(DATA, "3DDATA", "STB", "LIST_EFFECT.STB")
PTL_DIR = os.path.join(DATA, "3DDATA", "EFFECT", "PARTICLES")
PTLS = ("QESTARUA_GEM.PTL", "QESTARUA_GEM2.PTL")
BACKUP_DIR = os.path.join(REPO, "build", "evil-fairy-bullet")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

EFFECT_ROW = 631
SPEED_COL = 15            # EFFECT_BULLET_SPEED
SPEED_FROM, SPEED_TO = 1000, 3000
GEM_SEQ = 0               # the '"star01"' gem sprite with the 8 s life


def sha(b):
    return hashlib.sha256(b).hexdigest()


def gem_state(seq):
    """(coord, velocity values) of the gem sequence."""
    vel = seq.events_of(ptl.EVENT_VELOCITY)
    return seq.update_coord, [list(e.values) for e in vel]


def patched_ptl(blob):
    """The fixed bytes for one gem PTL, or None when already fixed. Raises on surprise."""
    seqs, tail = ptl.parse(blob)
    gem = seqs[GEM_SEQ]
    if gem.name != b'"star01"' or b"ef_arua_gem" not in gem.texture:
        raise SystemExit("ABORT: sequence %d is not the arua gem (%r, %r)"
                         % (GEM_SEQ, gem.name, gem.texture))
    coord, vels = gem_state(gem)
    if coord == ptl.COORD_LOCAL_WORLD and all(not any(v) for v in vels):
        return None
    if coord != ptl.COORD_WORLD or len(vels) != 1:
        raise SystemExit("ABORT: gem sequence changed since review (coord %d, %d velocity events)"
                         % (coord, len(vels)))
    gem.update_coord = ptl.COORD_LOCAL_WORLD
    for e in gem.events_of(ptl.EVENT_VELOCITY):
        e.values = [0.0] * len(e.values)
    return ptl.build(seqs, tail)


def plan():
    """[(kind, target, old, new)] still to apply; raises on a state not seen in review."""
    todo = []
    stb = Stb(EFFECT_STB)
    cur = stb.i(EFFECT_ROW, SPEED_COL)
    if cur == SPEED_FROM:
        todo.append(("stb", (EFFECT_ROW, SPEED_COL), stb.get(EFFECT_ROW, SPEED_COL), str(SPEED_TO)))
    elif cur != SPEED_TO:
        raise SystemExit("ABORT: LIST_EFFECT %d col %d is %d, expected %d or %d"
                         % (EFFECT_ROW, SPEED_COL, cur, SPEED_FROM, SPEED_TO))
    for name in PTLS:
        path = os.path.join(PTL_DIR, name)
        blob = open(path, "rb").read()
        new = patched_ptl(blob)
        if new is not None:
            todo.append(("ptl", name, blob, new))
    return todo


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        for name, rec in man["ptl"].items():
            path = os.path.join(PTL_DIR, name)
            if sha(open(path, "rb").read()) != rec["written"]:
                print("ABORT: %s changed since this script wrote it" % name)
                return 1
        stb = Stb(EFFECT_STB)
        for key, rec in man["stb"].items():
            r, c = map(int, key.split(","))
            if stb.get(r, c) != rec["new"].encode():
                print("ABORT: LIST_EFFECT %d col %d changed since this script wrote it" % (r, c))
                return 1
            stb.set(r, c, base64.b64decode(rec["old"]))
        open(EFFECT_STB, "wb").write(stb.to_bytes())
        for name, rec in man["ptl"].items():
            open(os.path.join(PTL_DIR, name), "wb").write(base64.b64decode(rec["original"]))
        os.remove(MANIFEST)
        print("restored LIST_EFFECT %d and %s" % (EFFECT_ROW, ", ".join(man["ptl"])))
        return 0

    original_stb = open(EFFECT_STB, "rb").read()
    if Stb(EFFECT_STB).to_bytes() != original_stb:
        print("ABORT: the STB writer does not round-trip LIST_EFFECT byte-for-byte")
        return 1
    todo = plan()

    if a.verify:
        if todo:
            print("VERIFY FAILED: %d change(s) not applied" % len(todo))
            return 1
        print("ALL CHECKS PASSED -- bullet %d at %d cm/s, gem rides the bullet in both PTLs."
              % (EFFECT_ROW, SPEED_TO))
        return 0
    if not todo:
        print("nothing to do -- already applied.")
        return 0
    for kind, target, _old, _new in todo:
        if kind == "stb":
            print("   LIST_EFFECT %d col %d (bullet speed): %d -> %d" % (*target, SPEED_FROM, SPEED_TO))
        else:
            print("   %s: gem sequence WORLD -> LOCAL_WORLD, velocity 2000 cm/s -> 0" % target)
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"stb": {}, "ptl": {}}
    stb = Stb(EFFECT_STB)
    for kind, target, old, new in todo:
        if kind == "stb":
            r, c = target
            man["stb"]["%d,%d" % (r, c)] = {"old": base64.b64encode(old).decode("ascii"), "new": new}
            stb.set(r, c, new)
        else:
            man["ptl"][target] = {"original": base64.b64encode(old).decode("ascii"),
                                  "written": sha(new)}
    json.dump(man, open(MANIFEST, "w"), indent=1)
    for kind, target, _old, new in todo:
        if kind == "ptl":
            open(os.path.join(PTL_DIR, target), "wb").write(new)
    open(EFFECT_STB, "wb").write(stb.to_bytes())
    print("written (undo data in %s)" % BACKUP_DIR)

    if plan():
        print("VERIFY FAILED after write")
        return 1
    print("verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
