"""Give walk-through map decorations collision (ZSC part collision level).

    python scripts/set-deco-collision.py --dry-run     what would change
    python scripts/set-deco-collision.py               write it
    python scripts/set-deco-collision.py --verify      check the file holds the change
    python scripts/set-deco-collision.py --restore     put the original back

**Eldeon jungle set, 2026-10-29** (3DDATA/ELDEON/LIST_DECO_EJ.ZSC, shared by Xita Refuge,
Shady Jungle, Forest of Wandering and Marsh of Ghosts: zone rows 61-64). Once monsters
started walking round walls (doc/pathfinding-and-z-plan.md), players and monsters
walking straight through these looked wrong. The user picked them from
`scripts`-side survey of every object placed in Xita with no colliding part, measured
at body height (0.3-1.8 m over its base):

* object 45, `eldeongrass016` -- the giant rafflesia-like flower (a mound of leaves,
  petals on top, vines on the ground; 30 placed in the four zones): **all four parts**.
* object 104, `ummak01` -- the dome hut on poles (19 placed): **part 0 only**, the frame
  and poles. Part 1 is the cover, 6 m and more up.
* objects 94 and 95, `gidung01` / `gidung02` -- banner poles (8 and 11 placed): **part 0
  only**, the pole. Part 1 is the cloth (alpha), 13 m and more up.

Level 12 = polygon (4) + "not moveable" (8), what the set's trees already use (138
parts): the avatar's foot and body collision treat it as solid, and GetHeightTop skips
it, so spawns, NPCs and item drops still land on the ground rather than on a petal or a
pole top (doc/pathfinding-and-z-plan.md, the rope bridge note).

Left as they are, by the user: the low wide ferns and bushes (`eldeongrass001-004`,
`006`, `008b`; hundreds placed, leaves spread 5-12 m at body height -- they would wall
off whole areas) and the tall palm-leaf plants.

After writing: re-bake the four zones' walk grids (`python scripts/nav-bake.py 61 62 63
64`) so the server's monsters walk round them too, and re-pack the client data
(`scripts/pack.ps1`): the client reads the ZSC from rose.vfs. The whole original file is
kept, hash-checked, in build/deco-collision/.
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rosefmt.zsc import TAG_COLLISION, Zsc, decode_props, serialize_object  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UNDO = os.path.join(ROOT, "build", "deco-collision")

LEVEL = 12            # polygon + not moveable, as the trees
CHANGES = {
    "3DDATA/ELDEON/LIST_DECO_EJ.ZSC": {
        # object: {part: (expected mesh file, level)}
        45: {0: ("eldeongrass016.zms", LEVEL), 1: ("eldeongrass016d.zms", LEVEL),
             2: ("eldeongrass016s.zms", LEVEL), 3: ("eldeongrass016t.zms", LEVEL)},
        104: {0: ("ummak01.zms", LEVEL)},
        94: {0: ("gidung01.zms", LEVEL)},
        95: {0: ("gidung02.zms", LEVEL)},
    },
}


def set_collision(props, level):
    """The proplist with its collision tag set to `level` (added before the end if absent)."""
    out, o, done = bytearray(), 0, False
    while o < len(props):
        tag = props[o]
        if tag == 0:
            break
        ln = props[o + 1]
        val = props[o + 2:o + 2 + ln]
        if tag == TAG_COLLISION and ln >= 2:
            val = struct.pack("<h", level) + val[2:]
            done = True
        out += bytes([tag, ln]) + val
        o += 2 + ln
    if not done:
        out += bytes([TAG_COLLISION, 2]) + struct.pack("<h", level)
    out += b"\x00"
    return bytes(out)


def plan(rel):
    """(Zsc, [(object, part, mesh, old level, new level)]) for one file; refuses a mismatch."""
    z = Zsc(os.path.join(DATA, rel))
    if z.trailing:
        raise SystemExit("%s: %d bytes after the last object" % (rel, z.trailing))
    rows = []
    for oid, parts in CHANGES[rel].items():
        if not 0 <= oid < len(z.objects):
            raise SystemExit("%s: no object %d" % (rel, oid))
        obj_parts = z.objects[oid][1]
        for pi, (mesh_name, level) in parts.items():
            if not 0 <= pi < len(obj_parts):
                raise SystemExit("%s: object %d has no part %d" % (rel, oid, pi))
            mesh, _mat, props = obj_parts[pi]
            got = os.path.basename(z.meshes[mesh].decode("latin-1")).lower()
            if got != mesh_name:
                raise SystemExit("%s: object %d part %d is %s, expected %s" % (rel, oid, pi, got, mesh_name))
            rows.append((oid, pi, got, decode_props(props)["collision"], level))
    return z, rows


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    os.makedirs(UNDO, exist_ok=True)
    manifest_path = os.path.join(UNDO, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}

    for rel in CHANGES:
        path = os.path.join(DATA, rel)
        orig = os.path.join(UNDO, rel.replace("/", "__"))
        if a.restore:
            if rel not in manifest or not os.path.exists(orig) or sha(orig) != manifest[rel]["orig_sha"]:
                raise SystemExit("%s: no intact original in %s" % (rel, UNDO))
            shutil.copyfile(orig, path)
            print("%s: restored the original" % rel)
            continue
        z, rows = plan(rel)
        todo = [r for r in rows if r[3] != r[4]]
        for oid, pi, mesh, old, new in rows:
            print("  %s object %d part %d %-22s collision %d -> %d%s" % (
                rel, oid, pi, mesh, old, new, "" if old != new else "  (already)"))
        if a.verify:
            if todo:
                raise SystemExit("%s: %d parts not set" % (rel, len(todo)))
            print("%s: verified" % rel)
            continue
        if a.dry_run or not todo:
            print("%s: %s" % (rel, "dry run" if a.dry_run else "nothing to do"))
            continue
        if rel not in manifest:
            shutil.copyfile(path, orig)
            manifest[rel] = {"orig_sha": sha(orig)}
            json.dump(manifest, open(manifest_path, "w"), indent=1)
        before = [serialize_object(o) for o in z.objects]
        for oid, pi, _mesh, _old, new in todo:
            cyl, parts, dummies, bb = z.objects[oid]
            parts = list(parts)
            m, t, props = parts[pi]
            parts[pi] = (m, t, set_collision(props, new))
            z.objects[oid] = (cyl, parts, dummies, bb)
        data = z.rebuild()
        # check: re-parse, the targets hold the level, every other object is byte-identical
        z2 = Zsc(data)
        assert len(z2.objects) == len(z.objects) and z2.meshes == z.meshes and z2.materials == z.materials
        touched = {oid for oid, *_ in todo}
        for i, o in enumerate(z2.objects):
            if i not in touched:
                assert serialize_object(o) == before[i], "object %d changed" % i
        for oid, pi, _mesh, _old, new in todo:
            assert decode_props(z2.objects[oid][1][pi][2])["collision"] == new
        open(path, "wb").write(data)
        print("%s: %d parts set, written (original in %s)" % (rel, len(todo), UNDO))


if __name__ == "__main__":
    main()
