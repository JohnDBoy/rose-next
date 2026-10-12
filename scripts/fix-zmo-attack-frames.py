"""Repair a monster attack clip whose action-frame events are the wrong family.

A normal attack lands on screen at an action frame of the attacker's motion:
21 (melee hit), 22 (bow: fire the bullet) or 23 (gun: fire the bullet), each
with a sibling sound frame (31/32/33). The client's ActionBow/ActionGun fire
whatever Get_BulletNO() returns; for a bare-handed monster that is 0, so a
ranged clip on a bare-handed monster never calls Hitted() at all. The queued
swing then sits until the 8 s orphan sweep folds it silently: the player takes
the damage with no digit, no impact and no HP movement (alpha #2, Hebarn
Officer Pazugenti 2685).

The Lich01 attack clip (Lich01\\attack_01.ZMO, 61 frames) is the one clip in
our tree whose event trailer disagrees with the clip's source: Jrose, QQ, ruff,
titan and tsuki all ship it with 21/31 (melee), while RoseZA, 667 and Evo --
and our copy, dated April 2026 from the original dump -- carry 23/33 (gun).
Same 54,032 bytes; the two files differ in exactly two shorts of the EZMO
trailer (frames 28 and 30). The Karkia officers 2685/2686 (bare-handed, hand
hit effect 402) and the retail Liches 962/963 use it. This script rewrites
those two events, in place, and nothing else.

The client also presents a fireless 22/23 frame as a melee hit now
(CObjCHAR::PresentFirelessRangedFrame), which covers the monsters whose clip
is 22/23 in *every* dump (Candle Ghost 927, Bebeg 1704, Sikuku Tiger Captain
1703, Sikuku Resident Shi 1261 ...) -- the data fix here is for the clip that
is simply wrong, so the swing lands at its authored moment with the melee
sound path (frame 31 takes NPC_ATTACK_SOUND for a bare-handed mob).

    python scripts/fix-zmo-attack-frames.py --dry-run
    python scripts/fix-zmo-attack-frames.py
    python scripts/fix-zmo-attack-frames.py --verify
    python scripts/fix-zmo-attack-frames.py --restore
    python scripts/fix-zmo-attack-frames.py --audit     # bullet-less ranged clips

`--audit` is the read-only survey behind the list above: every occupied
LIST_NPC row whose attack slot (MOB_ANI_ATTACK = 2 in LIST_NPC.CHR) is a clip
with no frame 21 but a 22/23, and whose right-hand weapon (col 5) has no
WEAPON_BULLET_EFFECT (LIST_WEAPON col 38). Those monsters depend on the client
fallback. Backups go to build/zmo-attack-frames/ (never a .bak beside the file:
pack.ps1 hard-errors on one, and pack.rs would bake it). `data/` is gitignored,
so this file is the record.

EZMO trailer layout (the same reader audit-ai-skill-refs.py uses):
    ... ZMO body ... | u16 n | n x i16 event-per-frame | u32 trailer_offset | "EZMO"
"""

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(REPO, "data")
BACKUP_DIR = os.path.join(REPO, "build", "zmo-attack-frames")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

# data-relative clip -> {frame_event_before: frame_event_after}. Reviewed.
REPAIRS = {
    "3DDATA/MOTION/NPC/LICH01/ATTACK_01.ZMO": {33: 31, 23: 21},
}

NPC_STB = "3DDATA/STB/LIST_NPC.STB"
WEAPON_STB = "3DDATA/STB/LIST_WEAPON.STB"
NPC_CHR = "3DDATA/NPC/LIST_NPC.CHR"
MOB_ANI_ATTACK = 2
NPC_R_WEAPON_COL = 5
WEAPON_BULLET_COL = 38
RANGED_FRAMES = {22, 23, 42, 43}


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    finally:
        sys.argv = saved
    return m


def resolve_ci(root, rel):
    """data/ is case-inconsistent on disk; resolve a data-relative path case-insensitively."""
    cur = root
    for part in rel.replace("\\", "/").split("/"):
        if not os.path.isdir(cur):
            return None
        hit = next((e for e in os.listdir(cur) if e.lower() == part.lower()), None)
        if hit is None:
            return None
        cur = os.path.join(cur, hit)
    return cur if os.path.isfile(cur) else None


def trailer(d):
    """(events_offset, [event per frame]) or None when the clip has no EZMO trailer."""
    if len(d) < 8 or d[-4:] not in (b"EZMO", b"3ZMO"):
        return None
    off, = struct.unpack_from("<I", d, len(d) - 8)
    n, = struct.unpack_from("<H", d, off)
    return off + 2, list(struct.unpack_from("<%dh" % n, d, off + 2))


def sha(d):
    return hashlib.sha256(d).hexdigest()


def plan(root):
    """[(rel, path, [(frame, before, after)])] still to apply; problems as strings."""
    out, problems = [], []
    for rel, remap in sorted(REPAIRS.items()):
        p = resolve_ci(root, rel)
        if not p:
            problems.append("%s: missing" % rel)
            continue
        d = open(p, "rb").read()
        t = trailer(d)
        if t is None:
            problems.append("%s: no EZMO trailer" % rel)
            continue
        _, events = t
        edits = [(f, e, remap[e]) for f, e in enumerate(events) if e in remap]
        already = all(e in remap.values() for e in events if e)
        if not edits:
            if not already:
                problems.append("%s: events %s match neither the before nor the after set"
                                % (rel, sorted({e for e in events if e})))
            continue
        out.append((rel, p, edits))
    return out, problems


def apply(root, dry):
    todo, problems = plan(root)
    for msg in problems:
        print("PROBLEM:", msg)
    if not todo:
        print("nothing to do" if not problems else "nothing applicable")
        return 1 if problems else 0
    man = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    for rel, p, edits in todo:
        d = bytearray(open(p, "rb").read())
        off, _ = trailer(bytes(d))
        for f, before, after in edits:
            print("%s %s frame %d: %d -> %d" % ("would set" if dry else "set", rel, f, before, after))
            struct.pack_into("<h", d, off + 2 * f, after)
        if dry:
            continue
        os.makedirs(BACKUP_DIR, exist_ok=True)
        orig = open(p, "rb").read()
        bpath = os.path.join(BACKUP_DIR, os.path.basename(p) + "." + sha(orig)[:12])
        if not os.path.exists(bpath):
            open(bpath, "wb").write(orig)
        man[rel] = {"backup": bpath, "before_sha": sha(orig), "after_sha": sha(bytes(d)),
                    "edits": [[f, b, a] for f, b, a in edits]}
        open(p, "wb").write(bytes(d))
        json.dump(man, open(MANIFEST, "w"), indent=1)
    if not dry:
        return verify(root)
    return 0


def verify(root):
    ok = True
    for rel, remap in sorted(REPAIRS.items()):
        p = resolve_ci(root, rel)
        if not p:
            print("FAIL %s: missing" % rel)
            ok = False
            continue
        t = trailer(open(p, "rb").read())
        if t is None:
            print("FAIL %s: no trailer" % rel)
            ok = False
            continue
        events = sorted({e for e in t[1] if e})
        stale = [e for e in events if e in remap]
        if stale:
            print("FAIL %s: still carries %s (events %s)" % (rel, stale, events))
            ok = False
        else:
            print("ok   %s: events %s" % (rel, events))
    return 0 if ok else 1


def restore(root):
    if not os.path.exists(MANIFEST):
        print("no manifest; nothing to restore")
        return 0
    man = json.load(open(MANIFEST))
    for rel, rec in sorted(man.items()):
        p = resolve_ci(root, rel)
        if not p:
            print("skip %s: missing" % rel)
            continue
        cur = open(p, "rb").read()
        if sha(cur) != rec["after_sha"]:
            print("skip %s: changed since this script wrote it (sha mismatch)" % rel)
            continue
        open(p, "wb").write(open(rec["backup"], "rb").read())
        print("restored %s" % rel)
    os.remove(MANIFEST)
    return 0


def audit(root):
    """Bullet-less monsters on a ranged attack clip: the rows the client fallback carries."""
    rd = load("rose_data_reader", "rose-data-reader.py")
    import rosedata as oro  # the shared data layer (was import-oro.py)
    npc = rd.Stb(os.path.join(root, NPC_STB), "latin-1")
    weapons = rd.Stb(os.path.join(root, WEAPON_STB), "latin-1")
    chr_ = oro.Chr(os.path.join(root, NPC_CHR))
    cache = {}

    def events(path):
        k = path.lower()
        if k not in cache:
            p = resolve_ci(root, path.decode("latin-1"))
            t = trailer(open(p, "rb").read()) if p else None
            cache[k] = None if p is None else ({e for e in t[1] if e} if t else set())
        return cache[k]

    rows = []
    for r in range(npc.rows):
        if not npc.occupied(r) or r >= len(chr_.chars) or chr_.chars[r] is None:
            continue
        anims = dict(chr_.chars[r]["anims"])
        if MOB_ANI_ATTACK not in anims:
            continue
        clip = chr_.motions[anims[MOB_ANI_ATTACK]]
        ev = events(clip)
        if ev is None or 21 in ev or not (ev & RANGED_FRAMES):
            continue
        rw = npc.s(r, NPC_R_WEAPON_COL).strip()
        rwi = int(rw) if rw.isdigit() else 0
        bullet = weapons.s(rwi, WEAPON_BULLET_COL).strip() if rwi > 0 else ""
        if bullet:
            continue
        rows.append((r, rd.scrub(npc.s(r, 0)) or "(nameless)", rwi, clip.decode("latin-1"), sorted(ev)))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for r, name, rwi, clip, ev in rows:
        print("%5d  %-36s weapon %-4d %s %s" % (r, name[:36], rwi, ev, clip))
    print("%d rows on a bullet-less ranged clip (present via the client fallback)" % len(rows))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=DATA)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--restore", action="store_true")
    g.add_argument("--audit", action="store_true")
    a = ap.parse_args(argv)
    if a.verify:
        return verify(a.root)
    if a.restore:
        return restore(a.root)
    if a.audit:
        return audit(a.root)
    return apply(a.root, a.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
