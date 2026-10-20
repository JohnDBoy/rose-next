"""Rename NPC shop tabs (2026-10-20, the user's shop notes).

A tab's caption is **not** LIST_SELL game col 0: the client draws the LIST_SELL_S.STL
entry whose key sits in col 1 (`CStringManager::GetStoreTabName`), English in language
block 1. Col 0 is a dev label the editors show; it is kept in step so the two never
disagree (`add-karkia-shops.py` asserts the same for its tabs). A key shared by several
tabs would rename all of them, so a row whose key another tab also uses is refused.

    521  [Smith] Pavrick (Magic City of Eucar)  "Arrows" -> "Distance Weapons"
         (bows, crossbows, their arrows and bolts -- and since weapon-ladder-pass.py
         the Rose set's bow and crossbow)

Add a row to `RENAMES` for the next one. Only an exact expected old caption is
renamed, so a re-run is a no-op and an edit made since is never overwritten.

    python scripts/rename-shop-tabs.py --dry-run
    python scripts/rename-shop-tabs.py
    python scripts/rename-shop-tabs.py --verify
    python scripts/rename-shop-tabs.py --restore

Undo per cell and per STL field in `build/rename-shop-tabs/manifest.json`. The client
reads the STL from the VFS: re-bake; restart the server for the col-0 label.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Stb, Stl  # noqa: E402

STB = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_SELL.STB")
STL = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_SELL_S.STL")
BACKUP_DIR = os.path.join(ROOT, "build", "rename-shop-tabs")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")
ENGLISH = 1          # language block the client draws here

# tab: (expected old caption, new caption)
RENAMES = {
    521: ("Arrows", "Distance Weapons"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    sell, stl = Stb(STB), Stl(STL)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}, "stl": {}}

    if a.restore:
        for key, old in man["cells"].items():
            r, c = (int(x) for x in key.split(","))
            sell.set(r, c, old.encode("latin-1"))
        for key, old in man["stl"].items():
            stl.set_name(key, old, ENGLISH)
        open(STB, "wb").write(sell.to_bytes())
        open(STL, "wb").write(stl.to_bytes())
        if os.path.isfile(MANIFEST):
            os.remove(MANIFEST)
        print("restored %d label(s) and %d caption(s)" % (len(man["cells"]), len(man["stl"])))
        return 0

    keys = {}
    for r in range(sell.rows):
        k = sell.s(r, 1).strip()
        if k:
            keys.setdefault(k, []).append(r)
    todo, bad = [], []
    for tab, (old, new) in RENAMES.items():
        k = sell.s(tab, 1).strip()
        if not k or not stl.has(k):
            bad.append("tab %d has no caption key" % tab)
            continue
        if len(keys[k]) > 1:
            bad.append("tab %d shares key %s with %s -- refusing" % (tab, k, keys[k]))
            continue
        cur = stl.name(k, ENGLISH)
        if cur == new and sell.s(tab, 0).strip() == new:
            print("   %d %-8s %r (done)" % (tab, k, new))
            continue
        if cur not in (old, new):
            bad.append("tab %d caption is %r, expected %r" % (tab, cur, old))
            continue
        print("   %d %-8s %r -> %r" % (tab, k, cur, new))
        todo.append((tab, k, new))
    if bad:
        print("\n".join("PROBLEM: " + b for b in bad))
        return 1
    if a.verify:
        if todo:
            print("VERIFY FAILED: %d tab(s) not renamed" % len(todo))
            return 1
        print("ALL CHECKS PASSED -- the shop tabs carry their names.")
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for tab, k, new in todo:
        man["cells"].setdefault("%d,0" % tab, sell.s(tab, 0))
        man["stl"].setdefault(k, stl.name(k, ENGLISH))
        sell.set(tab, 0, new.encode("latin-1"))
        stl.set_name(k, new, ENGLISH)
    open(STB, "wb").write(sell.to_bytes())
    open(STL, "wb").write(stl.to_bytes())
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("renamed %d tab(s) (undo: --restore). Re-bake the VFS." % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
