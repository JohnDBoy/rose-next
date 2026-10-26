#!/usr/bin/env python3
r"""Give named equipment items back the model and icon art upstream left blank.

THE DEFECTS
-----------
**Models.** An item's look is object[item_no] of its type's ZSC (the STB's .txt
model column is vestigial; see import-item.py). Four named items point at an
**empty object**, so they equip, show their icon, and draw nothing:

    back 811  Kriento's Wooden Keg Pack   LIST_BACK.ZSC
    back 813  Servant's Mantle            LIST_BACK.ZSC
    back 814  Vassal's Mantle             LIST_BACK.ZSC
    foot 171  KROSE Soccer Cleats         LIST_MFOOT.ZSC + LIST_WFOOT.ZSC

An audit of every avatar and weapon table (back, face, cap, body, arms, foot,
weapon, subwpn: a named row whose object holds no part) found exactly these.

**Icons.** Our ITEM1.TSI sheets hold 1,196 copies of one plain blue placeholder
tile. Nine items point their icon (col 9) at one of them, so their icon is a blue
square (reported on the KROSE cleats once their model was back):

    607  foot 170-174  the five Soccer Cleats   <- 668 cell 607
    737  back 808      Gingerbread Man          <- 668 cell 737
    738  back 806      Christmas Wreath         <- 668 cell 738
    739  back 807      Snowflake                <- 668 cell 739
    736  back 809      Winter Spirits Wing      <- 668 cell 8841

The two atlases share their layout up to here, so 668's cell at the same index is
the art these rows were given -- except 736, which 668 uses for its Military
Backpack; its Winter Spirits Wing (668 row 4287) is cell 8841, pasted into our
736 because no other row of ours uses that cell. Each cell is used by these rows
only, so filling it changes no other item.

WHY THEY ARE BLANK
------------------
Upstream, not us. Our data descends from the Evo 137/139 client, where all three
back objects are already blank; so is RoseZA. Every retail-line dump has them
(667, 668, Jrose, tsuki, titanRose, ruff), at the **same row numbers under the
same names** -- the row ids line up, only the art was missing. The cleats' mesh
and texture files were even on disk here already (``FOOT/foot1_21010.ZMS``,
``foot2_21010.ZMS``, ``BODY/BODY1_21010.DDS``, shared with the KROSE uniform);
only the object was blank.

THE FIX
-------
Models: each object is written in place from **668** (the official client)
through ``import-item.py``'s ``zsc_build_append(target=row)``, the same path as
``--target-row``: meshes and materials already in our table are reused, missing
ones appended, and missing files copied from 668 (the Follower_Cape mesh and its
two textures, the SperosWoodenKegPack mesh and texture). None of the four carries
a dummy point, so no effect is involved.

Icons: the 40x40 cell is pasted from 668's sheet into ours (both uncompressed
BGRA, ours without a mip chain, which this atlas never samples).

No STB or STL cell is touched -- names, stats, icon indices and ground models
were already right. Refuses a row whose name differs from the expected one (a
shifted table), and an icon cell that is neither the placeholder tile nor the
art already pasted. Done work is skipped, so a re-run is a no-op.

Undo: whole-file originals of the ZSCs and sheets, their hashes before and
after, and the list of copied files are in ``build/restore-missing-item-art/``.
``--restore`` puts them back only while each file still hashes to what this
script wrote, so it cannot undo a later change to the same file.

    python scripts/restore-missing-item-art.py --dry-run
    python scripts/restore-missing-item-art.py
    python scripts/restore-missing-item-art.py --verify
    python scripts/restore-missing-item-art.py --restore

Then re-bake; the client loads the ZSCs and the atlas at startup.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import dds  # noqa: E402
from rosefmt.stb import Stb  # noqa: E402
from rosefmt.tsi import sprites  # noqa: E402
from rosefmt.zsc import Zsc  # noqa: E402

OURS = "data"
SOURCE = r"C:\Users\Thomas\Desktop\Testclients\668\Extracted"
BACKUP = os.path.join("build", "restore-missing-item-art")
RES = os.path.join("3DDATA", "CONTROL", "RES")
CELL = 40
# An unused cell of ours holding the placeholder tile, to recognise the others by.
BLANK_CELL = 593

# (STB, row, expected name, ZSCs that index the row)
ITEMS = [
    ("LIST_BACK", 811, "Kriento's Wooden Keg Pack", ["LIST_BACK"]),
    ("LIST_BACK", 813, "Servant's Mantle", ["LIST_BACK"]),
    ("LIST_BACK", 814, "Vassal's Mantle", ["LIST_BACK"]),
    ("LIST_FOOT", 171, "KROSE Soccer Cleats", ["LIST_MFOOT", "LIST_WFOOT"]),
]

# our icon cell -> (668 icon cell, [(STB, row, expected name)] that use it)
ICONS = {
    607: (607, [("LIST_FOOT", 170, "Soccer Cleats"),
                ("LIST_FOOT", 171, "KROSE Soccer Cleats"),
                ("LIST_FOOT", 172, "JROSE Soccer Cleats"),
                ("LIST_FOOT", 173, "ROSE NA Soccer Cleats"),
                ("LIST_FOOT", 174, "PROSE Soccer Cleats")]),
    736: (8841, [("LIST_BACK", 809, "Winter Spirits Wing")]),
    737: (737, [("LIST_BACK", 808, "Gingerbread Man")]),
    738: (738, [("LIST_BACK", 806, "Christmas Wreath")]),
    739: (739, [("LIST_BACK", 807, "Snowflake")]),
}


def zsc_rel(name):
    return os.path.join("3DDATA", "AVATAR", name + ".ZSC")


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def stb(name, root=OURS, _cache={}):
    key = (root, name)
    if key not in _cache:
        _cache[key] = Stb(os.path.join(root, "3DDATA", "STB", name + ".STB"))
    return _cache[key]


def check_names():
    rows = [(s, r, n) for s, r, n, _z in ITEMS]
    rows += [u for _src, users in ICONS.values() for u in users]
    for table, row, name in rows:
        got = stb(table).s(row, 0).strip()
        if got != name:
            sys.exit("%s row %d is %r, expected %r -- the table has shifted, refusing"
                     % (table, row, got, name))
    for cell, (_src, users) in ICONS.items():
        for table, row, name in users:
            if stb(table).i(row, 9) != cell:
                sys.exit("%s row %d (%s) has icon %d, expected %d"
                         % (table, row, name, stb(table).i(row, 9), cell))


# ---------------------------------------------------------------- icons
class Atlas:
    """One ITEM1.TSI with its sheets loaded on demand as RGBA images."""

    def __init__(self, root, ours):
        self.root, self.ours = root, ours
        self.names, self.sp = sprites(os.path.join(root, RES, "ITEM1.TSI"))
        self.sheets = {}

    def where(self, cell):
        t, x1, y1, _x2, _y2 = self.sp[cell]
        return self.names[t], (x1, y1, x1 + CELL, y1 + CELL)

    def sheet(self, name):
        if name not in self.sheets:
            path = os.path.join(self.root, RES, name)
            if self.ours:
                self.sheets[name] = dds.read_bgra(path)
            else:
                from PIL import Image
                self.sheets[name] = Image.open(path).convert("RGBA")
        return self.sheets[name]

    def cell(self, cell):
        name, box = self.where(cell)
        return self.sheet(name).crop(box)


def icon_state(ours, src):
    """{our cell: 'blank' | 'done' | 'other'} plus the 668 art per cell."""
    blank = ours.cell(BLANK_CELL).tobytes()
    out = {}
    for cell, (src_cell, _users) in ICONS.items():
        art = src.cell(src_cell)
        cur = ours.cell(cell).tobytes()
        out[cell] = ("done" if cur == art.tobytes() else
                     "blank" if cur == blank else "other", art)
    return out


# ---------------------------------------------------------------- verify / restore
def verify():
    bad = 0
    for table, row, name, zscs in ITEMS:
        for z in zscs:
            zsc = Zsc(os.path.join(OURS, zsc_rel(z)))
            parts = zsc.objects[row][1]
            missing = []
            for m, t, _p in parts:
                for p in (zsc.meshes[m], zsc.materials[t][0]):
                    rel = p.decode("latin-1").replace("\\", "/").split("/", 1)[1]
                    if not os.path.exists(os.path.join(OURS, "3DDATA", rel)):
                        missing.append(rel)
            ok = parts and not missing
            bad += 0 if ok else 1
            print("  model %-10s %4d %-26s %-11s %s" % (table, row, name, z,
                  "OK (%d part)" % len(parts) if ok
                  else "*** %s ***" % ("missing " + ", ".join(missing) if parts else "empty")))
    state = icon_state(Atlas(OURS, True), Atlas(SOURCE, False))
    for cell, (src_cell, users) in sorted(ICONS.items()):
        ok = state[cell][0] == "done"
        bad += 0 if ok else 1
        print("  icon  %5d <- 668 %-5d %-38s %s" % (cell, src_cell,
              ", ".join(n for _t, _r, n in users)[:38],
              "OK" if ok else "*** %s ***" % state[cell][0]))
    return bad


def restore():
    man_path = os.path.join(BACKUP, "manifest.json")
    if not os.path.exists(man_path):
        sys.exit("no manifest in %s -- nothing to restore" % BACKUP)
    man = json.load(open(man_path))
    for rel, h in man["files"].items():
        if sha(os.path.join(OURS, rel)) != h["after"]:
            sys.exit("%s changed since this script wrote it -- refusing a whole-file "
                     "restore that would undo that change" % rel)
    for rel in man["files"]:
        shutil.copyfile(os.path.join(BACKUP, os.path.basename(rel)), os.path.join(OURS, rel))
        print("restored %s" % rel)
    for rel in man["copied"]:
        p = os.path.join(OURS, rel)
        if os.path.exists(p):
            os.remove(p)
            print("removed %s" % rel)
    os.remove(man_path)


# ---------------------------------------------------------------- main
def build_models(ii):
    """{rel: new bytes} for the ZSCs, and the asset files the new objects need."""
    blobs, files = {}, []
    for table, row, name, zscs in ITEMS:
        if stb(table, SOURCE).s(row, 0).strip() != name:
            sys.exit("668 %s row %d is %r, not %r"
                     % (table, row, stb(table, SOURCE).s(row, 0).strip(), name))
        for z in zscs:
            rel = zsc_rel(z)
            cur = blobs.get(rel) or open(os.path.join(OURS, rel), "rb").read()
            if Zsc(cur).objects[row][1]:
                print("  model %-10s %4d %-26s %-11s already has a model" % (table, row, name, z))
                continue
            # later rows of the same table build on the earlier ones' bytes
            src = ii.Zsc(os.path.join(SOURCE, rel))
            tmp = os.path.join(BACKUP, "_work.zsc")
            with open(tmp, "wb") as fh:
                fh.write(cur)
            _i, needed, blob = ii.zsc_build_append(tmp, src, row, SOURCE, target=row)
            os.remove(tmp)
            blobs[rel] = blob
            files += needed
            print("  model %-10s %4d %-26s %-11s <- 668 %s" % (table, row, name, z,
                  ", ".join(src.meshes[m].decode() for m, _t, _p in src.objects[row][1])))
    return blobs, list(dict.fromkeys(files))


def build_icons():
    """{rel: RGBA sheet} for the sheets that change."""
    ours, src = Atlas(OURS, True), Atlas(SOURCE, False)
    changed = {}
    for cell, (state, art) in sorted(icon_state(ours, src).items()):
        src_cell, users = ICONS[cell]
        label = ", ".join(n for _t, _r, n in users)
        if state == "done":
            print("  icon  %5d %-40s already filled" % (cell, label[:40]))
            continue
        if state == "other":
            sys.exit("icon cell %d holds art that is neither the placeholder nor 668's "
                     "cell %d -- something else filled it; not overwriting" % (cell, src_cell))
        name, box = ours.where(cell)
        ours.sheet(name).paste(art, box[:2])
        changed[os.path.join(RES, name)] = ours.sheet(name)
        print("  icon  %5d %-40s <- 668 cell %d (%s)" % (cell, label[:40], src_cell, name))
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(OURS, "3DDATA")):
        sys.exit("run from the repo root (data/3DDATA not found)")
    if args.restore:
        return restore()
    check_names()
    if args.verify:
        sys.exit(1 if verify() else 0)

    spec = importlib.util.spec_from_file_location("ii", os.path.join(HERE, "import-item.py"))
    ii = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ii)

    # Build everything in memory first; write only at the end.
    os.makedirs(BACKUP, exist_ok=True)
    blobs, files = build_models(ii)
    sheets = build_icons()
    if not blobs and not sheets:
        print("nothing to do.")
        return
    copied = [os.path.join("3DDATA", f.decode("ascii").replace("/", "\\").split("\\", 1)[1])
              for f in files]
    copied = [c for c in copied if not os.path.exists(os.path.join(OURS, c))]
    ii.copy_assets(files, SOURCE, args.dry_run)
    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        return

    man_path = os.path.join(BACKUP, "manifest.json")
    man = (json.load(open(man_path)) if os.path.exists(man_path)
           else {"files": {}, "copied": []})
    man["copied"] += [c for c in copied if c not in man["copied"]]

    def write(rel, write_fn):
        path = os.path.join(OURS, rel)
        if rel not in man["files"]:           # keep the first original across runs
            shutil.copyfile(path, os.path.join(BACKUP, os.path.basename(rel)))
            man["files"][rel] = {"before": sha(path)}
        write_fn(path)
        man["files"][rel]["after"] = sha(path)

    for rel, blob in blobs.items():
        n_before = len(Zsc(os.path.join(OURS, rel)).objects)
        write(rel, lambda p: open(p, "wb").write(blob))
        assert len(Zsc(os.path.join(OURS, rel)).objects) == n_before, \
            "%s object count changed" % rel
    for rel, img in sheets.items():
        write(rel, lambda p: dds.write_bgra(p, img))
    with open(man_path, "w") as fh:
        json.dump(man, fh, indent=1)
    print()
    if verify():
        sys.exit("verify failed")
    print("\ndone. Re-bake; the client loads the ZSCs and the atlas at startup.")


if __name__ == "__main__":
    main()
