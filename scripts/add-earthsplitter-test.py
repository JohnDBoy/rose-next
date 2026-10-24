"""Earthsplitter: a GM test skill built with SlopStudio's animation toolkit.

    python scripts/add-earthsplitter-test.py --dry-run
    python scripts/add-earthsplitter-test.py
    python scripts/add-earthsplitter-test.py --restore

then restart the server, re-bake, and in game: `/add skill <row>` (printed), with a
two-handed sword equipped.

Why
---
2026-10-24: someone shared the SlopRose repo (`C:\\Users\\Thomas\\Desktop\\Rose\\sloprose`), whose
SlopStudio carries a Claude skill, `slopstudio/.claude/skills/rose-anim-toolkit`, that
authors player motions procedurally -- stock clips retimed and exaggerated, the left
hand IK'd onto the grip -- and effects, including mesh effects that rise out of the
ground. The user asked to try it on a skill and see it in game. This is that test: one
GM row, no book, shop, tree or class gate. Its look is the question, not its numbers.

The source files in `build/earthsplitter/src/` were made by the toolkit (a copy patched
to read our loose `data/`: their VFS reader does not parse our `data.idx`, and our
Junior cap names dummy 65535 for "none"):

* `EARTHSPLIT_M1.ZMO` -- 71 frames: TWOSWD_3ATTACK's lean-back raise (16 frames, chest
  and pelvis twisted further), a 4-frame gather, a hop, the slam coming over, the
  blade buried at frame 29 (TWOSWD_HEAVYATTACK's impact, crouched deeper), a 7-frame
  tremor and HEAVYATTACK's crouched rise back to TWOSWD_STOP1. Toolkit builder:
  charged.py's swing 3 as a standalone skill, in the session scratchpad's
  `kit/earthsplitter.py`.
* `EARTHSPLIT_HOLD_M1.ZMO` -- 10 frames: frame 23 (the coil's anticipation dip, blade
  raised behind) trembling at 9 Hz, three whole cycles so it loops.
* `rocks/` -- `rock_spike_fx.py --write`: a cluster of four rocks (an `_ICE_02` shard
  re-textured STONE007, a point-up Junon stalactite JONGUSTONE05, two JONGUSTONE06
  needles) that erupt in 3 frames, hold with a tremble to 1 s and sink (38 frames at
  30 fps), each rock a ZMS copy resting in its buried pose plus a per-vertex ZMO,
  with `_DUST_02` and `Z_SPLINTER_01` bursts.

What this script does with them (rosefmt only):

* **The clip is split before the hop** (`rosefmt.zmo.sliced`): the cast (col 52) is
  frames 0-23 -- raise and gather -- and the action (col 68) the hop, the slam, the
  impact and the rise: 34 at 3, 74 (the ring) at 4 as the blade meets the ground, 24
  (the area event) at 5 on the impact. The cast's events are cleared. The hold is the
  cast loop (col 54, count 0): it plays while the client waits for the server's
  go-ahead. **v1 split on the impact itself**, since an area skill's damage lands when
  its action starts (`scripts/CLAUDE.md`, Exceed Break); in game (2026-10-24) the
  blade then sat in the ground through that wait, and the rocks came a beat late. The
  digits now start ~170 ms before the impact -- they used to land after the rocks.
* **Two effects.** `EARTHSPLIT_ROCKS.eft` is the toolkit's cluster, renamed, as the hit
  effect (col 74) under every monster hit. `EARTHSPLIT_RING.eft` (casting slot 2, col
  62, on event 74) is that cluster repeated: one where the blade lands, six at 3 m,
  nine at 4.8 m, each ring later than the last. Copies are turned 0 or 180 degrees
  only: the toolkit's preview turns an entry by +yaw about up, and our engine's
  YawPitchRoll swizzle may run the other way, which a half-turn does not care about.
* **The row**: type 17 (around the caster) like Impact Wave (511), whose sounds it
  keeps; radius 5 m, power 600, 10 s, 60 MP, two-handed sword only (col 30 = 221).
  Icon: Impact Wave's.

What it changes
---------------
    LIST_SKILL.STB / _S.STL  1 row appended, 1 key
    FILE_MOTION.STB          3 rows appended (cast, hold, action)
    TYPE_MOTION.STB          3 rows appended, every weapon column
    FILE_EFFECT.STB          2 blank rows filled (the first two after 3001)
    MOTION/AVATAR            EARTHSPLIT_CAST/_HOLD/_ACTION_M1.ZMO
    EFFECT                   EARTHSPLIT_ROCKS.eft, EARTHSPLIT_RING.eft,
                             EFFECTMESH/EARTHSPLIT_<rock>.ZMS/.ZMO (8 files)

`--restore` truncates the appended rows (only while they are still last), blanks the
FILE_EFFECT rows, removes the key and the files. Manifest in `build/earthsplitter/`.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt.stb import Stb  # noqa: E402
from rosefmt.stl import Stl  # noqa: E402
from rosefmt.binio import write_pstr16  # noqa: E402
from rosefmt import eft, zmo  # noqa: E402

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
OUT = os.path.join(ROOT, "build", "earthsplitter")
SRC = os.path.join(OUT, "src")
MANIFEST = os.path.join(OUT, "manifest.json")

NAME = "Earthsplitter"
DESC = ("Coil back, leap and bury the blade in the ground: the earth splits in rings "
        "around you and rocks erupt under every enemy within 5 m. (Test skill.)")
IMPACT = 29                       # the buried-blade frame of EARTHSPLIT_M1
SPLIT = 24                        # the first action frame: the hop
# in action frames: the cue, the rings as the blade meets the ground (frame 28 -- a
# frame early, the rocks take three to break the surface), the area event on the impact
ACTION_EVENTS = {IMPACT - SPLIT - 2: 34, IMPACT - SPLIT - 1: 74, IMPACT - SPLIT: 24}

AVATAR = "3DDATA\\MOTION\\AVATAR\\"
CLIPS = [("EARTHSPLIT_CAST_M1.ZMO", "earthsplit cast"),
         ("EARTHSPLIT_HOLD_M1.ZMO", "earthsplit hold"),
         ("EARTHSPLIT_ACTION_M1.ZMO", "earthsplit action")]
ROCKS_EFT = "3DDATA\\EFFECT\\EARTHSPLIT_ROCKS.eft"
RING_EFT = "3DDATA\\EFFECT\\EARTHSPLIT_RING.eft"
MESH_DIR = "3DDATA\\EFFECT\\EFFECTMESH\\"
ROCK_NAMES = ("SHARDS", "FANG", "NEEDLE", "NEEDLE_SMALL")

# where the cluster repeats in the ring: (x, y) cm in the caster's frame (front = -Y),
# turn (0 / 180 only, see the docstring), delay ms
BLADE = (0.0, -150.0)


def ring_layout():
    out = [(BLADE, 0.0, 0)]
    for radius, count, start, delay in ((300.0, 6, 30.0, 70), (480.0, 9, 0.0, 140)):
        for k in range(count):
            a = math.radians(start + 360.0 * k / count)
            out.append(((radius * math.sin(a), -radius * math.cos(a)), 180.0 * (k % 2), delay))
    return out


tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def data_path(rel):
    return os.path.join(DATA, *rel.split("\\"))


def last_used(t):
    return max(r for r in range(t.rows) if any(t.d[r]))


# --- files ---------------------------------------------------------------------------

def clips():
    full = open(os.path.join(SRC, "EARTHSPLIT_M1.ZMO"), "rb").read()
    total = zmo.read_header(full)[1]
    ev = zmo.events(full)[1]
    if ev[IMPACT] != 25:
        sys.exit(f"EARTHSPLIT_M1 has no skill hit at frame {IMPACT} -- rebuild it")
    cast = zmo.sliced(full, 0, SPLIT)
    cast = zmo.with_events(cast, {i: 0 for i, e in enumerate(zmo.events(cast)[1]) if e})
    action = zmo.sliced(full, SPLIT, total)
    changes = {i: 0 for i, e in enumerate(zmo.events(action)[1]) if e}
    changes.update(ACTION_EVENTS)
    action = zmo.with_events(action, changes)
    hold = open(os.path.join(SRC, "EARTHSPLIT_HOLD_M1.ZMO"), "rb").read()
    return [cast, hold, action]


def rename_rock(path):
    stem = path.split("\\")[-1].rsplit(".", 1)
    for rock in ROCK_NAMES:
        if stem[0].upper() == "ROCKSPIKE_" + rock:
            return MESH_DIR + "EARTHSPLIT_" + rock + "." + stem[1]
    return path


def cluster():
    c = eft.read(open(os.path.join(SRC, "rocks", "ROCK_SPIKE.EFT"), "rb").read())
    for m in c["meshes"]:
        m["zms"], m["zmo"] = rename_rock(m["zms"]), rename_rock(m["zmo"])
    c["name"] = "EARTHSPLIT_ROCKS"
    return c


def ring(c):
    parts, meshes = [], []
    for (cx, cy), turn, delay in ring_layout():
        a = math.radians(turn)
        ca, sa = math.cos(a), math.sin(a)

        def place(e):
            e = dict(e)
            x, y, z = e["pos"]
            e["pos"] = (cx + ca * x - sa * y, cy + sa * x + ca * y, z)
            r = list(e["rot"])
            r[1] = (r[1] + turn) % 360.0
            e["rot"] = tuple(r)
            e["delay"] = e["delay"] + delay
            return e
        parts += [place(p) for p in c["particles"]]
        meshes += [place(m) for m in c["meshes"]]
    return dict(c, name="EARTHSPLIT_RING", particles=parts, meshes=meshes)


def generated():
    files = {AVATAR + name: blob for (name, _), blob in zip(CLIPS, clips())}
    c = cluster()
    files[ROCKS_EFT] = eft.build(c)
    files[RING_EFT] = eft.build(ring(c))
    for rock in ROCK_NAMES:
        for ext in ("ZMS", "ZMO"):
            files[f"{MESH_DIR}EARTHSPLIT_{rock}.{ext}"] = open(
                os.path.join(SRC, "rocks", f"ROCKSPIKE_{rock}.{ext}"), "rb").read()
    return files


# --- tables --------------------------------------------------------------------------

def skill_row(base, tm, fe):
    template = load("LIST_SKILL.STB").d[511]          # Impact Wave
    if template[0] != b"Impact Wave":
        sys.exit("LIST_SKILL 511 is not Impact Wave -- refusing")
    row = list(template)
    blank = (3, 11, 12, 13, 14, 31, 32, 33, 34, 35, 39, 40, 45, 46, 55, 56, 57, 58, 59, 60, 61)
    for col in blank:
        row[col] = b""
    over = {0: NAME, 1: base, 2: 1, 8: 500, 9: 600, 17: 60, 20: 50, 30: 221,
            52: tm[0], 53: 100, 54: tm[1], 62: fe[1], 63: 999, 68: tm[2], 69: 100,
            74: fe[0], 75: 999, 86: f"LSkill{base}"}
    for col, v in over.items():
        row[col] = str(v).encode("latin-1")
    return row


def plan():
    sk, fm, tm, fe = (load(n) for n in ("LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB", "FILE_EFFECT.STB"))
    first_fe = last_used(fe) + 1
    fe_rows = [first_fe, first_fe + 1]
    if any(any(fe.d[r]) for r in fe_rows) or fe_rows[1] >= fe.rows:
        sys.exit(f"FILE_EFFECT {fe_rows} not blank -- refusing")
    return dict(skill=sk.rows, fm=[fm.rows + k for k in range(3)], tm=[tm.rows + k for k in range(3)], fe=fe_rows)


def install(dry):
    if os.path.exists(MANIFEST):
        sys.exit("already installed -- --restore first")
    p = plan()
    sk, fm, tm, fe = (load(n) for n in ("LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB", "FILE_EFFECT.STB"))
    files = generated()
    clash = [rel for rel in files if os.path.exists(data_path(rel))]
    if clash:
        sys.exit(f"files already exist: {clash} -- refusing")
    row = skill_row(p["skill"], p["tm"], p["fe"])
    print(f"{NAME}: LIST_SKILL {p['skill']}, FILE_MOTION {p['fm']}, TYPE_MOTION {p['tm']}, FILE_EFFECT {p['fe']}")
    print("  row:", {c: v.decode("latin-1") for c, v in enumerate(row) if v})
    c = cluster()
    print(f"  ring: {len(ring_layout())} clusters, {len(ring(c)['meshes'])} rock meshes; "
          f"{len(files)} files")
    if dry:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    for rel, blob in files.items():
        os.makedirs(os.path.dirname(data_path(rel)), exist_ok=True)
        open(data_path(rel), "wb").write(blob)

    labels = {}
    fm.grow_to(fm.rows + 3, {r: lbl for r, (_, lbl) in zip(p["fm"], CLIPS)})
    for r, (name, _) in zip(p["fm"], CLIPS):
        fm.d[r][0] = (AVATAR + name).encode("latin-1")
    tm.grow_to(tm.rows + 3, {r: lbl for r, (_, lbl) in zip(p["tm"], CLIPS)})
    for r, f in zip(p["tm"], p["fm"]):
        tm.d[r] = [str(f).encode() for _ in range(tm.cols)]
    for r, rel, name in ((p["fe"][0], ROCKS_EFT, b"EARTHSPLIT_ROCKS"), (p["fe"][1], RING_EFT, b"EARTHSPLIT_RING")):
        fe.d[r][0], fe.d[r][1] = name, rel.encode("latin-1")
    sk.grow_to(sk.rows + 1)
    sk.d[p["skill"]] = row
    for t in (sk, fm, tm, fe):
        t.save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL"))
    t.append(f"LSkill{p['skill']}", p["skill"], NAME, DESC)
    t.save(False, keep_backup=False)
    labels = {"FILE_MOTION.STB": [lbl for _, lbl in CLIPS], "TYPE_MOTION.STB": [lbl for _, lbl in CLIPS],
              "LIST_SKILL.STB": [""]}
    json.dump(dict(plan=p, labels=labels, files=sorted(files)), open(MANIFEST, "w"), indent=1)
    print(f"done -- restart the server, re-bake, then in game: /add skill {p['skill']} "
          f"(two-handed sword equipped)")


def restore():
    if not os.path.exists(MANIFEST):
        sys.exit("no manifest -- nothing to restore")
    m = json.load(open(MANIFEST))
    p = m["plan"]
    appended = {"LIST_SKILL.STB": p["skill"], "FILE_MOTION.STB": p["fm"][0], "TYPE_MOTION.STB": p["tm"][0]}
    for name, base in appended.items():
        t = load(name)
        labels = m["labels"][name]
        tail = b"".join(write_pstr16(lbl.encode("latin-1")) for lbl in labels)
        if t.rows != base + len(labels) or not t.header.endswith(tail):
            sys.exit(f"{name}: rows were appended after this test -- refusing to truncate")
    for name, base in appended.items():
        t = load(name)
        labels = m["labels"][name]
        tail = b"".join(write_pstr16(lbl.encode("latin-1")) for lbl in labels)
        t.header, t.d, t.rows = t.header[:-len(tail)], t.d[:base], base
        if t.rownames:
            del t.rownames[-len(labels):]
        t.save(False, keep_backup=False)
    fe = load("FILE_EFFECT.STB")
    for r in p["fe"]:
        fe.d[r] = [b"" for _ in range(fe.cols)]
    fe.save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL"))
    t.remove([f"LSkill{p['skill']}"])
    t.save(False, keep_backup=False)
    for rel in m["files"]:
        if os.path.isfile(data_path(rel)):
            os.remove(data_path(rel))
    os.remove(MANIFEST)
    print("restored: rows, key and files removed")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    if args.restore:
        return restore()
    install(args.dry_run)


if __name__ == "__main__":
    main()
