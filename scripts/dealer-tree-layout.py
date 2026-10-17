"""The Dealer tree's placement of Calibrated Burst, Photon Cannon, Exceed Break and Jewel Item Craft.

    python scripts/dealer-tree-layout.py --dry-run
    python scripts/dealer-tree-layout.py
    python scripts/dealer-tree-layout.py --verify
    python scripts/dealer-tree-layout.py --restore

Run it after `import-artisan-skill.py`, `import-artisan-photon-cannon.py` and
`import-exceed-break.py`: they own their skill rows, this owns where the classic skill
tree draws them (2026-10-17). UI2's tree needs nothing -- it lays itself out from the
class set and prerequisite columns.

Why
---
The user's layout, after playing the Dealer line's new skills:

* **Calibrated Burst and Photon Cannon are gun skills**, so they belong under Gunshot
  Mastery, not Craft Mastery. Calibrated Burst now needs **Gunshot Mastery rank 10**
  (Sniping Shot's gate; it was Craft Mastery rank 6); Photon Cannon still follows it at
  rank 5.
* **Exceed Break follows Gun Smash** (rank 5; it hung off Zuly Storm rank 5).
* **Jewel Item Craft stood alone**: it had no prerequisite at all, so UI2 put it in the
  lone-skill lane, and the classic tree never drew it. It now needs **Craft Mastery
  rank 6** -- the free step in its siblings' ladder (Refine Item 5, Gem Cutting 7, Cart
  Craft 8, Castle Gear Craft 10).

The prerequisite cells of 7002 / 7067 are also written by their import scripts' row
templates; here they are only migrated on an install imported before the move. Jewel
Item Craft (2641) is a retail row, so its prerequisite is this script's.

The classic tree
----------------
Every box and connector is painted into the page DDS (`doc/skill-tree-art.md`):

* **Gunshot Mastery page** (`DEALER_GUNSHOT_MASTERY.DDS`) was 512x128 with room for two
  rows only, so the canvas grows to 512x256 (it is blitted at its own size). A third
  row hangs off the spine: Calibrated Burst (art 110,110) -> Photon Cannon (258,110),
  drawn like Power Gun Shot -> Sniping Shot.
* **Craft Mastery page**: the box Calibrated Burst used (178,355, hung off the spine)
  becomes Jewel Item Craft's -- it is exactly a Craft Mastery branch. Photon Cannon's
  box and connector beside it are erased (that area was empty in the retail art).
* **Combat Mastery page**: Exceed Break's box moves from right of Zuly Storm (erased,
  empty in the retail art) to right of Gun Smash (351,2).

Undo: the pages and the XML as they were before the first run, and the prerequisite
cells, in `build/dealer-tree-layout/`; `--restore` puts them back (the files whole --
nothing else edits these three pages or the Dealer XML). The retail Craft Mastery page
that `import-artisan-skill.py` once kept hidden beside the art
(`.DEALER_CRAFT_MASTERY.DDS.orig`) is moved there too, as `pristine-...`.

Deploy: restart the server (prerequisites), re-bake (pages), copy `skilltree_dealer.xml`
loose into the launch folder (it is read with fopen, never from the VFS).
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt.stb import Stb  # noqa: E402

DATA = os.path.join(ROOT, "data")
STB = os.path.join(DATA, "3DDATA", "STB", "LIST_SKILL.STB")
RES_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "RES")
TREE_XML = os.path.join(DATA, "3DDATA", "CONTROL", "xml", "skilltree_dealer.xml")
OUT = os.path.join(ROOT, "build", "dealer-tree-layout")
MANIFEST = os.path.join(OUT, "manifest.json")
OLD_HIDDEN = os.path.join(RES_DIR, ".DEALER_CRAFT_MASTERY.DDS.orig")

CB, PC, EB, JEWEL = 7002, 7057, 7067, 2641
PREREQS = {CB: (2021, 10), EB: (2281, 5), JEWEL: (2081, 6)}   # rank-1 row: cols 39/40
NAMES = {CB: b"Calibrated Burst", PC: b"Photon Cannon", EB: b"Exceed Break",
         JEWEL: b"Jewel Item Craft"}

ART_ORIGIN, BOX_SIZE, LINE = (20, 75), 42, (74, 81, 99, 255)
SPINE_X = 74                    # every page's left spine


def icon_at(box):
    return box[0] + ART_ORIGIN[0] + 1, box[1] + ART_ORIGIN[1] + 2


# page -> (size it must have, boxes to paint, lines to paint, rects to clear)
GUN_CB, GUN_PC = (110, 110), (258, 110)
CRAFT_JEWEL = (178, 355)
COMBAT_EB = (351, 2)
PAGES = {
    "DEALER_GUNSHOT_MASTERY.DDS": dict(
        size=(512, 256),
        boxes=[GUN_CB, GUN_PC],
        lines=[((SPINE_X, 76), (SPINE_X, GUN_CB[1] + 21)),           # spine down a row
               ((SPINE_X, GUN_CB[1] + 21), (GUN_CB[0], GUN_CB[1] + 21)),
               ((GUN_CB[0] + 41, GUN_CB[1] + 21), (GUN_PC[0], GUN_PC[1] + 21))],
        clear=[]),
    "DEALER_CRAFT_MASTERY.DDS": dict(
        size=None,
        boxes=[CRAFT_JEWEL],
        lines=[((SPINE_X, 296), (SPINE_X, CRAFT_JEWEL[1] + 21)),     # as the 2621 branch
               ((SPINE_X, CRAFT_JEWEL[1] + 21), (CRAFT_JEWEL[0], CRAFT_JEWEL[1] + 21))],
        clear=[(220, 355, 303, 396)]),                               # Photon Cannon's old box
    "DEALER_COMBAT_MASTERY.DDS": dict(
        size=None,
        boxes=[COMBAT_EB],
        lines=[((300, 23), (COMBAT_EB[0], 23))],                     # from Gun Smash (259,2)
        clear=[(393, 160, 483, 201)]),                               # Exceed Break's old box
}

# XML: drop any node for these skills, then insert at these anchors
NODE_RE = r'\n[ \t]*<SKILL INDEX="(?:7002|7057|7067|2641)"[^>]*/>'
X_CB, X_PC, X_EB, X_JEWEL = icon_at(GUN_CB), icon_at(GUN_PC), icon_at(COMBAT_EB), icon_at(CRAFT_JEWEL)
INSERTS = [
    # Gunshot Mastery page: a third branch of the 2021 root, closing after Twin Shot's
    ('         <SKILL INDEX="2221" OFFSETX="280" OFFSETY="133" LEVEL="11"/>\n      </SKILL>',
     f'\n      <SKILL INDEX="{CB}" OFFSETX="{X_CB[0]}" OFFSETY="{X_CB[1]}">'
     f'\n         <SKILL INDEX="{PC}" OFFSETX="{X_PC[0]}" OFFSETY="{X_PC[1]}"/>'
     f'\n      </SKILL>'),
    ('<SKILL INDEX="2281" OFFSETX="280" OFFSETY="79"/>',
     f'\n         <SKILL INDEX="{EB}" OFFSETX="{X_EB[0]}" OFFSETY="{X_EB[1]}"/>'),
    ('<SKILL INDEX="2621" OFFSETX="199" OFFSETY="352"/>',
     f'\n      <SKILL INDEX="{JEWEL}" OFFSETX="{X_JEWEL[0]}" OFFSETY="{X_JEWEL[1]}"/>'),
]


def page_path(name):
    hit = [f for f in os.listdir(RES_DIR) if f.upper() == name]
    if not hit:
        sys.exit(f"tree art {name} not found")
    return os.path.join(RES_DIR, hit[0])


def target_xml(raw):
    out = re.sub(NODE_RE, "", raw)
    # drop a CB block left by a previous run (it is not self-closing)
    out = re.sub(r'\n[ \t]*<SKILL INDEX="7002"[^>]*>.*?\n[ \t]*</SKILL>', "", out, flags=re.S)
    for anchor, node in INSERTS:
        if anchor not in out:
            sys.exit(f"tree: anchor not found ({anchor[:50]}...) -- refusing")
        out = out.replace(anchor, anchor + node, 1)
    return out


def painted(im, box):
    return im.load()[box[0], box[1]][3] > 8


def draw_page(path, spec):
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGBA")
    if spec["size"] and im.size != spec["size"]:
        grown = Image.new("RGBA", spec["size"], (0, 0, 0, 0))
        grown.paste(im, (0, 0))
        im = grown
    px = im.load()
    for x0, y0, x1, y1 in spec["clear"]:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[x, y] = (0, 0, 0, 0)
    d = ImageDraw.Draw(im)
    for a, b in spec["lines"]:
        d.line([a, b], fill=LINE)
    for bx, by in spec["boxes"]:
        d.rectangle([bx, by, bx + BOX_SIZE - 1, by + BOX_SIZE - 1], outline=LINE)
    return im


def page_ok(path, spec):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    if spec["size"] and im.size != spec["size"]:
        return False
    if not all(painted(im, b) for b in spec["boxes"]):
        return False
    px = im.load()
    return all(px[x, y][3] == 0 for x0, y0, x1, y1 in spec["clear"]
               for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))


def prereq_cells(sk):
    """Rank 1 always; a later rank too when it carries a prerequisite of its own --
    Calibrated Burst's import writes it on all ten, and a rank's level-up checks its
    own row, so moving rank 1 alone left ranks 2-10 asking for Craft Mastery."""
    out = []
    for first, (skill, rank) in PREREQS.items():
        if sk.d[first][0] != NAMES[first]:
            sys.exit(f"LIST_SKILL {first} is {sk.d[first][0]!r}, not {NAMES[first]!r} -- refusing")
        rows = [r for r in range(first, min(sk.rows, first + 40))
                if sk.d[r][0] == NAMES[first] and int(sk.d[r][1] or first) == first]
        for row in rows:
            if row != first and not sk.d[row][39]:
                continue
            for c, v in ((39, skill), (40, rank)):
                want = str(v).encode()
                if sk.d[row][c] != want:
                    out.append([row, c, sk.d[row][c].hex(), want.hex()])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    m = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else None

    if args.restore:
        if not m:
            sys.exit("no manifest -- nothing to restore")
        sk = Stb(STB)
        for row, c, old, _ in m["cells"]:
            sk.d[row][c] = bytes.fromhex(old)
        sk.save(False, keep_backup=False)
        for name, saved in m["pages"].items():
            shutil.copyfile(saved, page_path(name))
        shutil.copyfile(m["xml"], TREE_XML)
        os.remove(MANIFEST)
        print("restored: prerequisites, the three pages and the Dealer XML")
        return

    sk = Stb(STB)
    raw = open(TREE_XML, encoding="utf-8", newline="").read()
    want_xml = target_xml(raw)

    if args.verify:
        ok = not prereq_cells(sk)
        ok &= want_xml == raw
        for name, spec in PAGES.items():
            good = page_ok(page_path(name), spec)
            ok &= good
            print(f"  {name}: {'ok' if good else 'NOT laid out'}")
        print(f"  prerequisites: {'ok' if not prereq_cells(sk) else 'differ'}; "
              f"XML: {'ok' if want_xml == raw else 'differs'}")
        print("verify:", "ok" if ok else "FAILED")
        sys.exit(0 if ok else 1)

    cells = prereq_cells(sk)
    todo = [n for n, spec in PAGES.items() if not page_ok(page_path(n), spec)]
    print(f"prerequisite cells to write: {[(r, c) for r, c, _, _ in cells]}")
    print(f"pages to lay out: {todo}")
    print(f"XML: {'unchanged' if want_xml == raw else 'nodes for 7002/7057/7067/2641 move'}")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    m = m or {"cells": [], "pages": {}, "xml": None}
    if not m["xml"]:
        m["xml"] = os.path.join(OUT, "skilltree_dealer.xml")
        shutil.copyfile(TREE_XML, m["xml"])
    if os.path.exists(OLD_HIDDEN):
        shutil.move(OLD_HIDDEN, os.path.join(OUT, "pristine-DEALER_CRAFT_MASTERY.DDS"))
    for name in todo:
        p = page_path(name)
        if name not in m["pages"]:
            m["pages"][name] = os.path.join(OUT, name)
            shutil.copyfile(p, m["pages"][name])
        draw_page(p, PAGES[name]).save(p)
    for row, c, old, new in cells:
        sk.d[row][c] = bytes.fromhex(new)
    if cells:
        sk.save(False, keep_backup=False)
    m["cells"] += [x for x in cells if not any(x[:2] == y[:2] for y in m["cells"])]
    open(TREE_XML, "w", encoding="utf-8", newline="").write(want_xml)
    json.dump(m, open(MANIFEST, "w"), indent=1)
    print("done -- restart the server, re-bake, copy skilltree_dealer.xml loose")


if __name__ == "__main__":
    main()
