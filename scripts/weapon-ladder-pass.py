"""The weapon ladder after the user's look survey (2026-10-20): the lv210 line and the
plain lv230 line trade places, and the Rose set leaves the end game for level 100.

The survey (user, 2026-10-20) graded every set from 210 up by how it looks:

    240  Aerie ... Quetzalcoatl            end level                  keep
    235  Jotunn ... Kumbhakarna            end level                  keep
    230  Kunihoroboshi ... (red name)      dungeon weapons            keep
    230  Viper / Akela / Matrix / Oasis    good, not lv230-worthy     -> 210
    225  Rosengarten ... (the Rose set)    vanity, not lv200+         -> 100
    220  Tsunemoto ... Hepri               end game                   keep
    215  Mirere                            dark, Karkia-coded         keep
    210  Arcidian / Befoul ... Photon Cannon  end level stuff         -> 230

--- 1. the swap (rows 1355-1367 <-> 1368-1379 + 1424)

"Current level 210 weapons go to 230 and vice versa" (the red set excepted). Both lines
are one weapon per type -- the lv210 line's launcher is Photon Cannon (1424, Jrose) --
so each type swaps its **tier columns** with its partner: price, quality, required
level, the stat requirement, both bonus slots (the ATK / class-stat bonuses
fix-weapon-atk-bonus-loss.py and rebalance-raider-weapons.py put there are tier-scaled,
so they travel with the tier), durability and ATK. Model, range, motion, speed,
sounds and effects stay with the weapon.

The other five Jrose lv210 rows (Strike Hammer, Assault Sword, Final Axe, Hyper
Railgun, Force Wand) load byte-identical meshes and textures to Befoul Hammer, Flesh
Reaver, Befoul Axe, Heat Ray Gun and Intrepid Wand, kept in two folders. The first
cut moved them to 230 with the line, which left the tier with doubles; the user's rule
is that **lv230 non-red weapons have no doubles**, so they are not touched here, and
then the stricter rule: **no weapon may wear a higher tier's look** -- they are
**erased** (`erase-retired-weapons.py`; first out of every shop and out of the Golden
Ring pool, `add-oro-drops.py` `WPN_ORO_210` `--rewrite`). Photon Cannon (1424), in the
same pool, is the line's launcher: it goes to 230 and left the Ring pool too.

Dual Tornado Rifles (381, dual guns, a test weapon) stays at 210: no lv230 dual gun
exists to trade with.

--- 2. the Rose set -> level 100 (rows 1382-1418, step 3)

"A fun set people can use": **full stats for its level**, a sidegrade, not the
armour cosmetics' 90% -- a weapon cannot be worn as a costume (the costume weapon
slots were never wired), so a weaker one would never be carried. Every tier column is
the vanilla weapon ladder of its type interpolated at 100 (Ice Sword 102 / Katana 95
for the 1H sword ...), bonuses included, so each weapon carries its type's own bonus
(bow AVOID, katar CRIT, staff INT ...) instead of the lv225 tier's generic +25.

Sold in the Magic City of Eucar (Luna, the level-100 town), beside the vanilla weapons
of its type: Pavrick's melee tab 520 (a column of its own beside the sword / mace /
2H / axe / spear rows, katar and dual in the empty bottom row) and long-range tab 521
(bow, crossbow), Sergei's guns 525 (gun, launcher), Pabel's magic 529 (staff, wand).

--- 3. shops

Huzam (Muris): tab 6 "Weapons lv210" = Dual Tornado Rifles + the Viper line, tab 7
"Weapons lv230" = the Arcidian line + Photon Cannon, one weapon per type, poured in
row order the way `stock-muris-shops.py` lays them out (its plan now leaves red boss
loot and the five drop-only look-alikes out of its level counts). Gelt and Belfa (Karkia) lose tab 562 (the Rose set at 225);
`add-karkia-shops.py` plans the same.

    python scripts/weapon-ladder-pass.py --dry-run
    python scripts/weapon-ladder-pass.py
    python scripts/weapon-ladder-pass.py --verify
    python scripts/weapon-ladder-pass.py --restore

All rows touched here are in `weapon-identity-pass.py`'s SKIP: the values written are
post-pass values, and a re-run of that pass from its originals would undo the swap.
Undo is per cell (`build/weapon-ladder-pass/manifest.json`); `data/` is gitignored, so
this file is the record. Restart the servers (LIST_WEAPON, LIST_SELL, LIST_NPC) and
re-bake the VFS.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

STB_DIR = os.path.join(REPO, "data", "3DDATA", "STB")
BACKUP_DIR = os.path.join(REPO, "build", "weapon-ladder-pass")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

# price, quality, required level, stat requirement (type, amount), both bonus slots,
# durability, ATK
TIER_COLS = (5, 8, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 35)
COL_LEVEL, COL_ATK, COL_PREFIX = 20, 35, 44
BOSS_LOOT = "22"

# weapon type -> (lv210 row, lv230 row)
SWAP = {
    211: (1368, 1355), 212: (1369, 1356), 221: (1370, 1357), 222: (1371, 1358),
    223: (1372, 1359), 231: (1373, 1360), 232: (1374, 1361), 233: (1424, 1362),
    241: (1375, 1363), 242: (1376, 1364), 251: (1377, 1365), 252: (1378, 1366),
    271: (1379, 1367),
}

ROSE_LEVEL = 100
ROSE = {211: 1382, 212: 1385, 221: 1388, 222: 1391, 223: 1394, 231: 1397, 232: 1400,
        233: 1403, 241: 1406, 242: 1409, 251: 1412, 252: 1415, 271: 1418}
ROSE_NAMES = ("Rosengarten Sabre", "Sommermorgen Maul", "La Bella Greatsword",
              "Amorosa Glaive", "Ducat Axe", "Whimy Longbow", "Confetti Pistol",
              "Rubra Cannon", "Elfe Staff", "Angela Wand", "Georgette Claws",
              "Escada Blades", "Tabris Crossbow")

# LIST_SELL: tab -> {weapon type: (grid row, grid col)} for the Rose set
GRID_COLS, SELL_SLOTS = 8, 48
ROSE_SHOP = {
    520: {211: (0, 6), 212: (1, 6), 221: (2, 6), 223: (3, 6), 222: (4, 6),
          251: (5, 6), 252: (5, 7)},                          # [Smith] Pavrick
    521: {231: (0, 6), 271: (1, 6)},                          # [Smith] Pavrick
    525: {232: (0, 6), 233: (1, 6)},                          # [Ferrell Trader] Sergei
    529: {241: (0, 5), 242: (1, 5)},                          # [Magic Goods Seller] Pabel
}
# Taken over by replace-210-weapons.py (2026-10-25): the Viper line is erased (tsuki's
# 220 set is the lv210 tier) and Huzam's lv210 tab restocked there. The plan below is
# frozen in the manifest, so these keys are dropped from it for --verify, a re-run and
# --restore alike -- restoring them would write pass values into blank rows.
SUPERSEDED_ROWS = set(range(1355, 1368))
SUPERSEDED_SELL = {6}
# The lv230 line's ATK, re-stepped by weapon-tier-steps.py (2026-10-26): restore that
# pass first.
SUPERSEDED_ATK = set(range(1368, 1380)) | {1424}


def superseded(key):
    n, r, c = key
    return ((n == "LIST_WEAPON" and (r in SUPERSEDED_ROWS or (r in SUPERSEDED_ATK and c == COL_ATK)))
            or (n == "LIST_SELL" and r in SUPERSEDED_SELL))


HUZAM_TABS = {6: [381] + list(range(1355, 1368)),
              7: list(range(1368, 1380)) + [1424]}
KARKIA_ROSE_TAB = 562
KARKIA_SELLERS = {4019: (561, 564, 0), 4103: (561, 564, 0)}  # Gelt, Belfa
TAB_COLS = (21, 22, 23)
WIDE_BASE, LEGACY_MAX_NO, T_WEAPON = 100000, 999, 8


def encode(no):
    """Rose::Store::encode_store_item"""
    return T_WEAPON * 1000 + no if no <= LEGACY_MAX_NO else T_WEAPON * WIDE_BASE + no


def cell(t, r, c):
    return t.get(r, c).decode("latin-1").strip()


def num(t, r, c):
    v = cell(t, r, c)
    return int(v) if v.lstrip("-").isdigit() else 0


def level(t, r):
    return num(t, r, COL_LEVEL) if cell(t, r, 19) == "31" else 0


def vanilla_bracket(w, wtype, lv):
    """The two plain vanilla weapons of a type around a level (rows below 1000, no
    prefix: the retail ladder every type climbs)."""
    ladder = sorted((level(w, r), r) for r in range(1, 1000)
                    if cell(w, r, 0) and num(w, r, 4) == wtype and cell(w, r, COL_PREFIX) == ""
                    and level(w, r) > 0)
    lo = max((x for x in ladder if x[0] <= lv), default=None)
    hi = min((x for x in ladder if x[0] >= lv), default=None)
    if lo is None or hi is None:
        sys.exit("ABORT: no vanilla weapons of type %d around level %d" % (wtype, lv))
    return lo, hi


def plan_weapons(w):
    """{(row, col): str} for LIST_WEAPON, from the live (pre-pass) values."""
    out = {}
    for wtype, (a, b) in SWAP.items():
        for c in TIER_COLS:
            out[(a, c)] = cell(w, b, c)
            out[(b, c)] = cell(w, a, c)
    for wtype, row in ROSE.items():
        (llv, lo), (hlv, hi) = vanilla_bracket(w, wtype, ROSE_LEVEL)
        t = 0.0 if hlv == llv else (ROSE_LEVEL - llv) / (hlv - llv)

        def lerp(c):
            return num(w, lo, c) + (num(w, hi, c) - num(w, lo, c)) * t

        want = {COL_LEVEL: str(ROSE_LEVEL), 21: cell(w, lo, 21),
                5: str(int(round(lerp(5) / 50.0)) * 50),
                8: str(int(round(lerp(8)))), 22: str(int(round(lerp(22)))),
                29: str(int(round(lerp(29)))), COL_ATK: str(int(round(lerp(COL_ATK))))}
        for slot in ((23, 24, 25), (26, 27, 28)):
            cond, ab, amt = slot
            if cell(w, lo, ab) and cell(w, lo, ab) == cell(w, hi, ab):
                want[cond] = cell(w, lo, cond)
                want[ab] = cell(w, lo, ab)
                want[amt] = str(int(round(lerp(amt))))
            else:
                want[cond] = want[ab] = want[amt] = ""
        for c, v in want.items():
            out[(row, c)] = v
    return out


def plan_sell(sell, w):
    out = {}
    for tab, rows in HUZAM_TABS.items():
        for s in range(SELL_SLOTS):
            out[(tab, 2 + s)] = str(encode(rows[s])) if s < len(rows) else "0"
    for s in range(SELL_SLOTS):
        out[(KARKIA_ROSE_TAB, 2 + s)] = "0" if cell(sell, KARKIA_ROSE_TAB, 2 + s) == "0" else ""
    for tab, places in ROSE_SHOP.items():
        for wtype, (r, c) in places.items():
            key = (tab, 2 + r * GRID_COLS + c)
            cur = cell(sell, *key)
            if cur not in ("", "0", str(encode(ROSE[wtype]))):
                sys.exit("ABORT: LIST_SELL %d slot %d is taken (%s)" % (tab, key[1] - 2, cur))
            out[key] = str(encode(ROSE[wtype]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    paths = {n: os.path.join(STB_DIR, n + ".STB") for n in ("LIST_WEAPON", "LIST_SELL", "LIST_NPC")}
    tables = {n: Stb(p) for n, p in paths.items()}
    for n, t in tables.items():
        if t.to_bytes() != open(paths[n], "rb").read():
            sys.exit("ABORT: %s does not round-trip" % n)
    w, sell, npc = tables["LIST_WEAPON"], tables["LIST_SELL"], tables["LIST_NPC"]
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"cells": {}, "plan": {}}

    if a.restore:
        if not man["cells"]:
            print("nothing to restore")
            return 0
        for key, old in man["cells"].items():
            n, r, c = key.split(",")
            if superseded((n, int(r), int(c))):
                continue
            tables[n].set(int(r), int(c), old.encode("latin-1"))
        for n, t in tables.items():
            open(paths[n], "wb").write(t.to_bytes())
        os.remove(MANIFEST)
        print("restored %d cell(s)" % len(man["cells"]))
        return 0

    for row, nm in zip(sorted(ROSE.values()), ROSE_NAMES):
        if cell(w, row, 0) != nm:
            sys.exit("ABORT: LIST_WEAPON %d is %r, expected %r" % (row, cell(w, row, 0), nm))
    for wtype, (a210, b230) in SWAP.items():
        if b230 in SUPERSEDED_ROWS:
            if num(w, a210, 4) != wtype:
                sys.exit("ABORT: row %d is not type %d" % (a210, wtype))
            continue
        if num(w, a210, 4) != wtype or num(w, b230, 4) != wtype:
            sys.exit("ABORT: swap pair %d/%d is not type %d" % (a210, b230, wtype))
        if cell(w, a210, COL_PREFIX) == BOSS_LOOT or cell(w, b230, COL_PREFIX) == BOSS_LOOT:
            sys.exit("ABORT: a boss-loot row is in the swap")

    # The plan is fixed on the first run (the swap reads the very cells it writes),
    # so later runs and --verify compare against the stored plan.
    if man["plan"]:
        plan = {tuple(k.split(",")): v for k, v in man["plan"].items()}
        plan = {(n, int(r), int(c)): v for (n, r, c), v in plan.items()}
    else:
        for wtype, (a210, b230) in SWAP.items():
            if level(w, a210) != 210 or level(w, b230) != 230:
                sys.exit("ABORT: rows %d / %d are not at 210 / 230 -- already swapped? "
                         "(no manifest found)" % (a210, b230))
        plan = {("LIST_WEAPON", r, c): v for (r, c), v in plan_weapons(w).items()}
        plan.update({("LIST_SELL", r, c): v for (r, c), v in plan_sell(sell, w).items()})
        for nid, tabs in KARKIA_SELLERS.items():
            for c, t in zip(TAB_COLS, tabs):
                plan[("LIST_NPC", nid, c)] = str(t) if t else ""

    plan = {k: v for k, v in plan.items() if not superseded(k)}
    todo = {k: v for k, v in plan.items() if cell(tables[k[0]], k[1], k[2]) != v}

    print("Swap (lv210 <-> lv230), ATK / level after:")
    for wtype, (a210, b230) in SWAP.items():
        if b230 in SUPERSEDED_ROWS:          # the Viper side, erased
            print("   %-22s -> lv%s ATK %s" % (cell(w, a210, 0), plan[("LIST_WEAPON", a210, COL_LEVEL)],
                                               cell(w, a210, COL_ATK)))
            continue
        print("   %-22s -> lv%s ATK %s   |   %-22s -> lv%s ATK %s"
              % (cell(w, a210, 0), plan[("LIST_WEAPON", a210, COL_LEVEL)],
                 plan.get(("LIST_WEAPON", a210, COL_ATK), cell(w, a210, COL_ATK)), cell(w, b230, 0),
                 plan[("LIST_WEAPON", b230, COL_LEVEL)], plan[("LIST_WEAPON", b230, COL_ATK)]))
    print("Rose set -> lv%d:" % ROSE_LEVEL)
    for wtype, row in ROSE.items():
        b = [plan[("LIST_WEAPON", row, c)] for c in (24, 25, 27, 28)]
        print("   %-22s ATK %4s  req %s  bonus %s:%s %s:%s  $%s"
              % (cell(w, row, 0), plan[("LIST_WEAPON", row, COL_ATK)],
                 plan[("LIST_WEAPON", row, 22)], *b, plan[("LIST_WEAPON", row, 5)]))
    print("cells to change: %d" % len(todo))

    if a.verify:
        if todo:
            for k, v in list(todo.items())[:15]:
                print("   %s %d col %d: %r, expected %r" % (k[0], k[1], k[2],
                                                          cell(tables[k[0]], k[1], k[2]), v))
            print("VERIFY FAILED")
            return 1
        print("ALL CHECKS PASSED -- the weapon ladder pass is in place.")
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    man["plan"] = {"%s,%d,%d" % k: v for k, v in plan.items()}
    for (n, r, c), v in todo.items():
        man["cells"].setdefault("%s,%d,%d" % (n, r, c), cell(tables[n], r, c))
        tables[n].set(r, c, v.encode("latin-1"))
    for n, t in tables.items():
        if any(k[0] == n for k in todo):
            open(paths[n], "wb").write(t.to_bytes())
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("wrote %d cell(s) (undo: --restore). Restart the servers and re-bake the VFS."
          % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
