#!/usr/bin/env python3
"""Import Rose Brazil's Cursed Vermillion set as the level-225 tier (2026-10-26).

Level 225 was empty: the two tsuki weapons that held it (Elemental Dual Swords,
Stormcrystal Claws) moved to 220 the same day (weapon-tier-steps.py). The user
picked Rose Brasil's "Cursed Vermillion" set to fill it: "it looks very good ...
I tend to see them as particular". Where it drops or sells is decided later.

The source (`Testclients\\rose brazil\\Extracted`, LIST_WEAPON 1901-1914) is a
vanity set there -- ATK 10, price 1, no level -- so nothing but the art is read
(`--art-only`): model, icon, gem anchor. The art is Brazil's own, a folder of its
own (`3ddata\\weapon\\weapon\\custom\\Cursed_Vermillion\\`, 32 files, ~5 MB), and
not one mesh or texture matches a file already in our data/ (checked by hash), so
it cannot wear another tier's look. Brazil's fourteenth, a dual gun (1914), is
left out: dual guns are the test weapon we erased (03be568e). Its type numbers
are ours, one weapon per type.

--- the numbers

Template = the type's 220 weapon (Tsunemoto ... Hepri; Justice Blades and
Frostbitten Knuckles for dual and katar): speed, motion, range, sounds, effects,
price, quality, durability and **both bonus slots** (the 220 line's AVOID+20) come
from it, so the weapon type keeps its identity. The tier columns are halfway
between the type's 220 and 230 (Arcidian) weapons, the way weapon-tier-steps.py
placed 215 and 230:

    stat requirement   midpoint of the two
    ATK                effective ATK (ATK + an ATK bonus line) at the midpoint,
                       less the template's ATK bonus (dual +90, katar +30)

Ground model: Brazil has none of its own -- every weapon points at the generic drop
bag (object 246) and no ground file names the set -- so each lies on the ground as
**its own model** (`WEAPON_MODEL`: a LIST_FieldITEM object copied from the weapon's,
parts and transforms included), the way Blaze Dancer and Justice Blades do. The
first run used the bag; a re-run swaps it.

Gem: Brazil leaves the axe's gem anchor blank (no glow), though the model carries
the socket -- dummy point 2, at the head, with the same orientation as the hammer's
and the two-hand sword's point 2, where their gems sit. The axe takes 2 too.

**Red name** (col 44 = 22, `CItem::GetItemNameColor`; see set-boss-loot-tier.py):
the user's call, "I tend to see them as particular". 22 adds no prefix word.

    python scripts/import-vermillion-weapons.py --dry-run
    python scripts/import-vermillion-weapons.py
    python scripts/import-vermillion-weapons.py --verify
    python scripts/import-vermillion-weapons.py --restore

The engine is `weapon_tier.py`; nothing is erased (`--erase` has no line to strip).
The 13 rows are in weapon-identity-pass.py's SKIP (post-pass values). `data/` is
gitignored, so this file is the record. Restart the servers, re-bake the VFS.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weapon_tier import WEAPON_MODEL, Row, Tier, main  # noqa: E402

LEVEL = 225
RED = "22"
AXE, AXE_GEM = 155, "2"
DESC = ("Steel forged under a curse that stained it the colour of old blood. "
        "It has never been clean since.")

# our row, Brazil row, template (the type's 220), type, name, requirement, ATK
ROWS = [
    (28, 1901, 1426, 211, "Cursed Vermillion Dagger",         "10:332", 498),
    (59, 1902, 1427, 212, "Cursed Vermillion Hammer",         "10:346", 574),
    (129, 1904, 1428, 221, "Cursed Vermillion Two-hand Sword", "10:318", 453),
    (188, 1906, 1429, 222, "Cursed Vermillion Spear",          "10:300", 423),
    (155, 1905, 1430, 223, "Cursed Vermillion Axe",            "10:319", 526),
    (254, 1907, 1431, 231, "Cursed Vermillion Bow",            "11:318", 468),
    (260, 1908, 1432, 232, "Cursed Vermillion Gun",            "13:268", 436),
    (289, 1909, 1433, 233, "Cursed Vermillion Launcher",       "10:169", 492),
    (327, 1910, 1434, 241, "Cursed Vermillion Staff",          "12:304", 434),
    (359, 1911, 1435, 242, "Cursed Vermillion Wand",           "12:314", 388),
    (451, 1912, 424, 251, "Cursed Vermillion Katar",           "11:322", 361),
    (453, 1913, 125, 252, "Cursed Vermillion Dual Wield",      "11:250", 478),
    (81, 1903, 1436, 271, "Cursed Vermillion Bowgun",          "10:162", 406),
]


def row(our, src, tmpl, wtype, name, req, atk):
    rid, rval = req.split(":")
    cells = {21: rid, 22: rval, 35: str(atk), 44: RED}
    if our == AXE:
        cells[43] = AXE_GEM
    return Row(our, src, tmpl, wtype, name, DESC, cells, field=WEAPON_MODEL)


TIER = Tier(key="import-vermillion-weapons",
            source=r"C:\Users\Thomas\Desktop\Testclients\rose brazil\Extracted",
            level=LEVEL, rows=[row(*r) for r in ROWS], old={})

if __name__ == "__main__":
    sys.exit(main(TIER))
