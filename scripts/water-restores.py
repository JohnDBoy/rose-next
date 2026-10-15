"""Vital and Spiritual Waters: level tiers, flat + % heal, server cooldowns (2026-10-15).

The waters are the instant restores (LIST_USEITEM: no status row, adds HP or MP). They
healed a flat 250-1250 HP / 200-1000 MP with nothing between two of them but the
client's 500 ms -- a level-10 character could drink four times its HP bar, and nothing
stopped a stack being chugged mid-fight. The user's design: a cooldown so they stay a
strong emergency heal, HP and MP on separate timers (MP much faster), a flat + % heal so
a tier stays useful while levelling, level limits per tier, and the XXL kept as an
over-the-top GM/test potion. The code (citem.h UseItem_*, the server's
classUSER::Use_InventoryITEM, the client's item delay, prediction and tooltip) reads:

    col 17/18  use requirement (AT_LEVEL 31, min level)
    col 20     flat amount          col 21  % of the maximum
    col 26     cooldown in ms (one HP timer, one MP timer; 0 = none)

Tiers below (each restores about 25-35% of the bar at the level it opens). The XXL pair
has no level limit and no cooldown and heals flat + 100%; it leaves the one shop that
sold it (LIST_SELL tab 563 "Potions", Ginias and Nemo; the tab is closed up) and no drop
table carries it, so only a GM hands it out.

Also cleared: col 26 on the other instant restores (event foods: Candy Cane, Churros ...)
held a stray 1 from another lineage; under the new rule it would start the HP timer and
lock the waters for 8 s after a candy.

    python scripts/water-restores.py --dry-run
    python scripts/water-restores.py
    python scripts/water-restores.py --verify
    python scripts/water-restores.py --restore

Cell-level undo in build/water-restores/manifest.json. `data/` is gitignored, so this file
is the record. The server reads both tables: restart it, and re-bake the VFS.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rosedata as oro  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB")
USE = os.path.join(STB, "LIST_USEITEM.STB")
SELL = os.path.join(STB, "LIST_SELL.STB")
BACKUP_DIR = os.path.join(REPO, "build", "water-restores")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

AT_LEVEL, AT_HP, AT_MP = 31, 16, 17
HP_COOLDOWN_MS, MP_COOLDOWN_MS = 8000, 3000
# row: (name, min level, flat, percent, cooldown ms)
WATERS = {
    10: (b"Vital Water (S)", 0, 60, 8, HP_COOLDOWN_MS),
    11: (b"Vital Water (M)", 30, 120, 10, HP_COOLDOWN_MS),
    12: (b"Vital Water (L)", 70, 250, 12, HP_COOLDOWN_MS),
    13: (b"Vital Water (XL)", 120, 400, 15, HP_COOLDOWN_MS),
    14: (b"Vital Water (XXL)", 0, 1250, 100, 0),          # GM / test
    29: (b"Spiritual Water (S)", 0, 40, 8, MP_COOLDOWN_MS),
    30: (b"Spiritual Water (M)", 30, 80, 10, MP_COOLDOWN_MS),
    31: (b"Spiritual Water (L)", 70, 160, 12, MP_COOLDOWN_MS),
    32: (b"Spiritual Water (XL)", 120, 250, 15, MP_COOLDOWN_MS),
    33: (b"Spiritual Water (XXL)", 0, 1000, 100, 0),      # GM / test
}
GM_ONLY = (10014, 10033)            # LIST_SELL item codes (type 10 * 1000 + row)
SHOP_TAB, SHOP_FIRST_COL = 563, 2


def num(b):
    s = b.strip()
    return int(s) if s.lstrip(b"-").isdigit() else 0


def plan_use(stb):
    """{(row, col): new bytes} for LIST_USEITEM."""
    out = {}
    for row, (name, level, flat, pct, cool) in WATERS.items():
        out[(row, 17)] = str(AT_LEVEL).encode() if level else b""
        out[(row, 18)] = str(level).encode() if level else b""
        out[(row, 20)] = str(flat).encode()
        out[(row, 21)] = str(pct).encode()
        out[(row, 26)] = str(cool).encode() if cool else b""
    for row in range(1, stb.rows):        # the other instant restores: no stray cooldown
        if row in WATERS or not stb.occupied(row):
            continue
        if num(stb.get(row, 24)) == 0 and num(stb.get(row, 19)) in (AT_HP, AT_MP) \
                and stb.get(row, 26).strip():
            out[(row, 26)] = b""
    return out


def plan_sell(stb, original):
    """The shop tab without the GM waters, closed up (from the tab as it was)."""
    cells = [original.get((SHOP_TAB, c), stb.get(SHOP_TAB, c)).strip()
             for c in range(SHOP_FIRST_COL, stb.cols)]
    kept = [v for v in cells if v and num(v) not in GM_ONLY]
    kept += [b""] * (len(cells) - len(kept))
    return {(SHOP_TAB, SHOP_FIRST_COL + i): v for i, v in enumerate(kept)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    tables = {}
    for key, path in (("use", USE), ("sell", SELL)):
        raw = open(path, "rb").read()
        tables[key] = oro.Stb(path)
        if tables[key].to_bytes() != raw:
            print("ABORT: the STB writer does not round-trip %s byte-for-byte" % path)
            return 1
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"use": {}, "sell": {}}

    def originals(key):
        return {tuple(int(x) for x in k.split(",")): v.encode("latin-1")
                for k, v in man[key].items()}

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        for key, path in (("use", USE), ("sell", SELL)):
            stb = tables[key]
            for (r, c), old in originals(key).items():
                stb.set(r, c, old)
            open(path, "wb").write(stb.to_bytes())
        os.remove(MANIFEST)
        print("restored LIST_USEITEM and LIST_SELL tab %d" % SHOP_TAB)
        return 0

    use, sell = tables["use"], tables["sell"]
    for row, (name, *_rest) in WATERS.items():
        if use.get(row, 0).strip() != name:
            print("ABORT: LIST_USEITEM %d is %r, expected %r" % (row, use.get(row, 0).strip(), name))
            return 1
    todo = {"use": plan_use(use), "sell": plan_sell(sell, originals("sell"))}
    pending = {k: {rc: v for rc, v in cells.items() if tables[k].get(*rc).strip() != v}
               for k, cells in todo.items()}

    for row, (name, level, flat, pct, cool) in WATERS.items():
        print("   %2d %-22s lv %3s  %4d + %3d%%  cooldown %s" % (
            row, name.decode(), level or "-", flat, pct, "%g s" % (cool / 1000) if cool else "none"))
    stray = [r for (r, c) in todo["use"] if r not in WATERS]
    print("   stray cooldowns cleared on %d other instant restores" % len(stray))
    print("   shop tab %d: %s" % (SHOP_TAB, b" ".join(v for v in todo["sell"].values() if v).decode()))

    n = sum(len(v) for v in pending.values())
    if a.verify:
        if n:
            print("VERIFY FAILED: %d cell(s) differ from the plan" % n)
            return 1
        print("ALL CHECKS PASSED -- waters, stray cooldowns and the shop tab are as planned.")
        return 0
    if not n:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: %d cell(s) would change, nothing written" % n)
        return 0
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for key, path in (("use", USE), ("sell", SELL)):
        stb = tables[key]
        for (r, c), v in pending[key].items():
            man[key].setdefault("%d,%d" % (r, c), stb.get(r, c).decode("latin-1"))
            stb.set(r, c, v)
        open(path, "wb").write(stb.to_bytes())
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("wrote %d cell(s) (undo: --restore, manifest in %s)" % (n, BACKUP_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
