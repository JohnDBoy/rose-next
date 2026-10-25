#!/usr/bin/env python3
"""Replace the level-235 Jotunn line with 668's dinosaur set (2026-10-25).

The Jotunn line (LIST_WEAPON 1437-1446, Jrose) read as recolours of the level-240
mythicals (user: "mostly just recolors of the level 240 ones"). The official Rednim
client (668, doc/668-survey.md) ships a complete level-250 "dinosaur" set at its rows
1476-1488 -- Extinction Ruin, Fossil Endless ... Saurian Retribution, a folder of
their own (`3DDATA/WEAPON/ZATANA/`) -- with a "TBC" placeholder icon (9995). Those
meshes **and** textures are byte-identical to retail's level-200 unique series
(Endless Blade, Devastation, Sundering Force ...), which we never imported, so:

  * each lands at **its retail item number** (908, 915 ... 999): blank rows and
    empty model objects in our tables, and under 1000, so quests and recipes can
    name them (drops can name anything since the wide drop encoding);
  * the icon is the retail series' own -- already in our ITEM1.TSI at the same
    indices (icon25.dds 4095-4108, compared visually against 668's), used by no
    other item, so no atlas cell is added;
  * the level-200 unique series can never come in as well: same art.

Level 235, beside Asmodeus Ritual Blade (124, kept: the tier has two 2H swords).
668's stats are on its own scale (ATK 160-278) and are not read (`--art-only`).
The ten types the Jotunn line had **inherit its row exactly** (template = the old
row: requirement, both bonuses -- 16:120 in slot 1 is the tier's mark --, ATK,
speed, motion, sounds). The three it lacked (2H sword, spear, axe) template on
their level-240 weapon and take the line's own 235/240 ratios, medians over the
ten pairs: stat requirement x0.929, ATK x0.952 --

    Primal Cleave     (Bahamut 352 / 495)  ->  STR 327, ATK 471
    Titan Unyielding  (Oberon  331 / 463)  ->  STR 308, ATK 441
    Saurian Eternity  (Albion  353 / 573)  ->  STR 328, ATK 546

Extinction Ruin is the Devastation mace: 668 files it as a 1H sword (211, retail's
own slip -- it carries the mace motion 3 and mace sound), so it templates on
Naglfar and is our 1H mace (212). The thirteen are a full set, one per type.

Ground-drop models: 668's point at the *level-200* paths
(`WEAPON/WEAPON/onehand/OSW001/onehand200.*`), the same bytes again. Copied as they
are, that would put a second copy of each mesh in another folder, so the 13
field objects are repointed at the ZATANA files (byte equality checked on the
source first) and the copies deleted.

Name text: 668 has no descriptions for the set; one line for the whole tier, the
way the 235 and 240 lines carry one each.

--- the order

    python scripts/replace-235-weapons.py --dry-run
    python scripts/replace-235-weapons.py              # import the 13 + stats
    python scripts/add-karkia-drops.py --rewrite       # WPN_235 now names the 13
    python scripts/add-oro-drops.py --rewrite
    python scripts/replace-235-weapons.py --erase      # strip 1437-1446
    python scripts/replace-235-weapons.py --verify

`--erase` is the house meaning of delete (cf. erase-retired-weapons.py): the ten
rows blanked (ids kept), their LWEA keys removed from every language block, their
ZSC objects emptied and the mesh/material records only they used removed, those
files moved out of data/ -- file by file: their `t_unique_*` folders also hold the
level-240 line's art. It refuses while any STB cell names one of them. No
character in the dev database owned one (`item.type_id = 8`); check again before
running it on a database with players. Their icon cells stay in ITEM1.TSI.

Undo: `--restore` puts back the four tables saved before the first write, deletes
the asset files the import added and moves the erased files back; it refuses if a
table changed since this script last wrote it. The drop tables are not this
script's: re-run the two drop scripts with the old WPN_235 after a restore. All
13 rows are in weapon-identity-pass.py's SKIP (post-pass values). `data/` is
gitignored, so this file is the record. Restart the servers, re-bake the VFS.

The engine is `weapon_tier.py` (shared with replace-210-weapons.py since the same
day). Moving to it brought one correction: **the gem anchor (col 43) is the
source's** -- it indexes the model's own dummy points, and the first run had taken
the template's, so Fossil Flare (blank -> 1) and Apex Savior (2 -> 0) set their gem
glow on the wrong point. A plain re-run applies it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weapon_tier import Row, Tier, main  # noqa: E402

LEVEL = 235
BONUS_1 = ("16", "120")     # the 235 line's mark (the 230 line has ATK+10, the 240 CRIT+18)
DESC = "Cut from the bones of something that ruled the world before anyone was there to name it."

# our row, 668 row, template, type, icon, name, requirement, ATK, bonus slot 2
ROWS = [
    (908, 1477, 1437, 211, 4104, "Fossil Endless",       "10:341", 518, None),
    (915, 1476, 1438, 212, 4102, "Extinction Ruin",      "10:356", 598, None),
    (926, 1479, 1389, 221, 4106, "Primal Cleave",        "10:327", 471, None),
    (939, 1480, 1392, 222, 4105, "Titan Unyielding",     "10:308", 441, None),
    (932, 1478, 1395, 223, 4095, "Saurian Eternity",     "10:328", 546, None),
    (947, 1481, 1439, 231, 4096, "Ptero Pierce",         "11:327", 488, "22:80"),
    (959, 1483, 1440, 232, 4099, "Dino Rifter",          "13:275", 453, None),
    (966, 1484, 1441, 233, 4101, "Fossil Flare",         "10:174", 512, None),
    (974, 1485, 1442, 241, 4103, "Bone Shatter",         "12:312", 457, "12:60"),
    (982, 1486, 1443, 242, 4108, "Apex Savior",          "12:322", 409, "12:50"),
    (990, 1488, 1444, 251, 4100, "Saurian Retribution",  "11:327", 419, "26:75"),
    (999, 1487, 1445, 252, 4098, "Jawbreaker Doon",      "11:254", 608, "11:10"),
    (950, 1482, 1446, 271, 4097, "Raptor Reverberation", "10:166", 423, "24:29"),
]

OLD = {1437: "Jotunn", 1438: "Naglfar", 1439: "Goliath", 1440: "Titan",
       1441: "Gigantes", 1442: "Mistcalf", 1443: "Bergelmir", 1444: "Nephilim",
       1445: "Hecatoncheir", 1446: "Kumbhakarna"}


def row(our, src, tmpl, wtype, icon, name, req, atk, bonus2):
    rid, rval = req.split(":")
    b2 = bonus2.split(":") if bonus2 else ("", "")
    cells = {21: rid, 22: rval, 24: BONUS_1[0], 25: BONUS_1[1], 27: b2[0], 28: b2[1],
             35: str(atk)}
    return Row(our, src, tmpl, wtype, name, DESC, cells, icon)


TIER = Tier(key="replace-235-weapons", source=r"C:\Users\Thomas\Desktop\Testclients\668\Extracted",
            level=LEVEL, rows=[row(*r) for r in ROWS], old=OLD)

if __name__ == "__main__":
    sys.exit(main(TIER))
