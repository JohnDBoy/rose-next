"""Give Calibrated Burst (LIST_SKILL 7002) the skill book it never had.

    python scripts/add-calibrated-burst-book.py --dry-run
    python scripts/add-calibrated-burst-book.py
    python scripts/add-calibrated-burst-book.py --verify
    python scripts/add-calibrated-burst-book.py --restore

Why
---
`scripts/import-artisan-skill.py` (2026-09-01) gave the Artisan its only exclusive
attack skill, with rows, name, tree node and icon -- but no book. Rank 1 of a class
skill is learned **only** from its book: the server's `CLI_SKILL_LEARN_REQ` handler is
compiled out, so the skill tree shows a skill but cannot teach it. Until now
Calibrated Burst could be had only through the GM `/add skill 7002` (found
2026-10-17 while adding the Champion's books).

What it changes
---------------
    LIST_USEITEM.STB    row 854 (blank, past the Artisan books 845-850) <- a copy of
                        849 (Refine Item, the Artisan's other book), teaching 7002
    LIST_USEITEM_S.STL  LUSE854: the skill's own name and description, as
                        fix-skill-book-names.py wants every book to read
    LIST_SELL.STB       tab 468 ("Dealer", Darren's second-job tab, shared with the
                        four Akram Ministers and Arua's Fairy) slot col 48, right
                        after the Artisan's crafting books

Rows 851-853 are skipped on purpose: they are the type-314 stubs of books pruned by
`prune-dead-skill-books.py`. The book carries no class or prerequisite of its own --
the learn condition reads the *skill's* (Artisan class set 68, Craft Mastery r6).
`fix-skill-book-names.py` keeps a reviewed EXPECTED set and will list this book as a
newcomer; its name already matches its skill.

Cell-level undo in `build/calibrated-burst-book/`. The server reads LIST_USEITEM and
LIST_SELL (restart it); the client needs a re-bake.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt.stb import Stb  # noqa: E402
from rosefmt.stl import Stl  # noqa: E402

STB_DIR = os.path.join(ROOT, "data", "3DDATA", "STB")
OUT = os.path.join(ROOT, "build", "calibrated-burst-book")
MANIFEST = os.path.join(OUT, "manifest.json")

SKILL = 7002
BOOK, TEMPLATE = 854, 849
SHOP_TAB, SHOP_COL = 468, 48
KEY = f"LUSE{BOOK}"

tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def planned():
    """[(table, row, col, new bytes)] -- the book row and the shop slot."""
    ui = load("LIST_USEITEM.STB")
    out = [("LIST_USEITEM.STB", BOOK, c, ui.d[TEMPLATE][c]) for c in range(ui.cols)]
    skill_name = load("LIST_SKILL.STB").d[SKILL][0]
    over = {0: skill_name, 20: str(SKILL).encode(), 27: KEY.encode()}
    out = [(t, r, c, over.get(c, v)) for t, r, c, v in out]
    out.append(("LIST_SELL.STB", SHOP_TAB, SHOP_COL, str(10000 + BOOK).encode()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    m = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else None
    stl_path = os.path.join(STB_DIR, "LIST_USEITEM_S.STL")

    if args.restore:
        if not m:
            sys.exit("no manifest -- nothing to restore")
        for t, r, c, old, _ in m["cells"]:
            load(t).d[r][c] = bytes.fromhex(old)
        for t in {c[0] for c in m["cells"]}:
            load(t).save(False, keep_backup=False)
        stl = Stl(stl_path)
        stl.remove([KEY])
        stl.save(False, keep_backup=False)
        os.remove(MANIFEST)
        print(f"restored: book row {BOOK}, shop slot {SHOP_TAB}/{SHOP_COL}, {KEY}")
        return

    if args.verify:
        if not m:
            sys.exit("not applied")
        bad = [(t, r, c) for t, r, c, _, new in m["cells"]
               if load(t).d[r][c] != bytes.fromhex(new)]
        has = Stl(stl_path).has(KEY)
        for b in bad:
            print("  differs:", b)
        print(f"  {KEY} present: {has}")
        print("verify:", "ok" if not bad and has else "FAILED")
        sys.exit(0 if not bad and has else 1)

    if m:
        print("already applied -- nothing to do (--restore first)")
        return

    sk, ui, sell = load("LIST_SKILL.STB"), load("LIST_USEITEM.STB"), load("LIST_SELL.STB")
    if sk.d[SKILL][0] != b"Calibrated Burst":
        sys.exit(f"LIST_SKILL {SKILL} is {sk.d[SKILL][0]!r}, not Calibrated Burst -- "
                 "run import-artisan-skill.py first")
    taught = [r for r in range(1, ui.rows) if ui.i(r, 4) == 314 and ui.i(r, 20) == SKILL]
    if taught:
        sys.exit(f"a book already teaches {SKILL}: LIST_USEITEM {taught}")
    if any(ui.d[BOOK]):
        sys.exit(f"LIST_USEITEM {BOOK} is in use ({ui.d[BOOK][0]!r}) -- refusing")
    if sell.d[SHOP_TAB][SHOP_COL].strip(b"0"):
        sys.exit(f"shop tab {SHOP_TAB} col {SHOP_COL} holds {sell.d[SHOP_TAB][SHOP_COL]!r}")
    code = str(10000 + BOOK).encode()
    for t in ("LIST_SELL.STB", "ITEM_DROP.STB"):
        s = load(t)
        hits = [r for r in range(s.rows) if code in s.d[r]]
        if hits:
            sys.exit(f"{t} rows {hits} already name item 10:{BOOK} -- refusing")

    cells = [[t, r, c, load(t).d[r][c].hex(), v.hex()] for t, r, c, v in planned()
             if load(t).d[r][c] != v]
    print(f"book {BOOK} (copy of {TEMPLATE}) teaches {SKILL} "
          f"{sk.d[SKILL][0].decode()}; sold in tab {SHOP_TAB} col {SHOP_COL}; "
          f"{len(cells)} cells")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    for t, r, c, _, new in cells:
        load(t).d[r][c] = bytes.fromhex(new)
    for t in {c[0] for c in cells}:
        load(t).save(False, keep_backup=False)
    desc = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL")).field(f"LSkill{SKILL}", 1, 1)
    stl = Stl(stl_path)
    stl.append(KEY, BOOK, sk.d[SKILL][0].decode("latin-1"), desc)
    stl.save(False, keep_backup=False)
    os.makedirs(OUT, exist_ok=True)
    json.dump({"cells": cells}, open(MANIFEST, "w"), indent=1)
    print("done -- restart the game server and re-bake")


if __name__ == "__main__":
    main()
