#!/usr/bin/env python3
"""Give the imported Jrose weapons (LIST_WEAPON 1381-1453) back the ATK their
template carried as a bonus and `--bonus` overwrote.

THE DEFECT
----------
An item row has exactly **two** bonus slots, (ability, value) pairs at game cols
24/25 and 27/28. `import-item.py --bonus` fills them in order, so the first
`--bonus` lands in slot 1 -- and slot 1 is where every one of our 13 level-230
flagships keeps its ATK bonus:

    1355 Viper Blade        ATK+10        1362 Matrix Cannon   ATK+10
    1356 Viper Sting        ATK+10        1363 Oasis Staff     ATK+30, INT+60
    1357 Viper Sword        ATK+10        1364 Oasis Wand      ATK+30, INT+50
    1358 Viper Spear        ATK+10        1365 Akela Katar     ATK+30, CRIT+75
    1359 Viper Axe          ATK+10        1366 Dual Viper      ATK+90, DEX+10
    1360 Akela Bow          ATK+10, AVOID+80   1367 Akela Bowgun    ATK+10
    1361 Matrix Rifle       ATK+10

`--art-only` clones the template's columns and then overrides only what the
command line names, so a row that passed no `--bonus` at all kept ATK+10 while
its set-mates lost it. 52 of the 73 imported rows are missing it.

Mostly that is 10 points and does not matter. On the four types whose flagship
carries a bigger ATK bonus it does: **dual is ATK+90**, and both imported dual
weapons landed *below* the level-230 weapon they were scaled up from --

    Dual Viper Blades  lv230  ATK 467 + 90 = 557
    Hecatoncheir       lv235  ATK 495       (-62)
    Giranda            lv240  ATK 523       (-34)

Giranda is the set's mythic-tier flagship. Five rows invert this way (also
Bergelmir, Nephilim, Mistcalf, by 6-9 points).

THE FIX
-------
Fold the lost bonus into the ATK column rather than trying to put it back in a
slot: there are only two slots, and on bow/staff/wand/katar/dual **both** are
already occupied by the template, so an item cannot carry the template's ATK
bonus, the template's characteristic second bonus (INT for casters, CRIT for
katars, AVOID for bows) *and* its own set bonus. Damage reads the weapon's ATK
column and `m_iAddValue[AT_ATK]` into the same ATK term, so folding is
equivalent for combat and keeps the set bonus and the type's character intact.

Each new value restores the multiplier the batch was designed around, applied to
the flagship's *effective* ATK instead of its base:

    new_atk = cur_atk + round(template_atk_bonus * cur_atk / template_atk)

which reproduces x0.90/x0.96/x1.12 (batch 1) and x0.85/x0.98/x1.06 (batch 2) on
effective ATK -- Giranda 523 -> 624 = 557 x 1.12 exactly.

WHY THE TABLE IS SPELLED OUT
----------------------------
The old and new values are both listed so the pass is idempotent and auditable:
a row already at its new value is skipped, a row at neither value aborts the run.
Deriving the correction from the live table instead would be self-amplifying --
the condition that identifies an affected row ("no ATK bonus") stays true after
the fix, so a second run would bump every row again.

The manifests doc/jrose-weapon-batch1.txt and batch2.txt carry the corrected ATK
values, so a replay from them reproduces this state directly and does not need
this script.

Idempotent; --dry-run and --verify supported.
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OURS = "data"
STB_REL = os.path.join("3DDATA", "STB", "LIST_WEAPON.STB")
ATK_COL = 35

# row -> (expected name, old ATK, corrected ATK)
FIXES = {
    1382: ("Rosengarten Sabre", 391, 401),
    1383: ("Aerie", 456, 467),
    1385: ("Sommermorgen Maul", 418, 428),
    1386: ("Catoblepas", 487, 498),
    1388: ("La Bella Greatsword", 432, 442),
    1389: ("Bahamut", 504, 515),
    1391: ("Amorosa Glaive", 414, 424),
    1392: ("Oberon", 483, 494),
    1394: ("Ducat Axe", 449, 459),
    1395: ("Albion", 524, 535),
    1397: ("Whimy Longbow", 424, 434),
    1398: ("Phoenix", 495, 506),
    1400: ("Confetti Pistol", 437, 447),
    1401: ("Hellhound", 510, 521),
    1403: ("Rubra Cannon", 474, 484),
    1404: ("Griffon", 553, 564),
    1406: ("Elfe Staff", 385, 414),
    1407: ("Unicorn", 449, 483),
    1409: ("Angela Wand", 342, 371),
    1410: ("Mermaid", 399, 433),
    1412: ("Georgette Claws", 363, 392),
    1413: ("Spriggan", 423, 457),
    1415: ("Escada Blades", 448, 534),
    1416: ("Giranda", 523, 624),
    1418: ("Tabris Crossbow", 386, 396),
    1419: ("Quetzalcoatl", 450, 461),
    1426: ("Tsunemoto", 399, 409),
    1427: ("Anansi", 426, 436),
    1428: ("Dairo", 441, 451),
    1429: ("Apollyon", 422, 432),
    1430: ("Goggy", 459, 469),
    1431: ("Selket", 433, 443),
    1432: ("Shelob", 446, 456),
    1433: ("Myrmecoleon", 484, 494),
    1434: ("Arachne", 393, 422),
    1435: ("Psyche", 349, 378),
    1436: ("Hepri", 394, 404),
    # 1437-1446 (the lv235 Jotunn line) were erased on 2026-10-25 by
    # replace-235-weapons.py; their rows are blank, so they left this table.
    1447: ("Grenade Bowgun", 378, 387),
    1448: ("Cyclone Bowgun", 354, 363),
    1450: ("Dreamvine Stave", 381, 410),
    1451: ("Omega Staff", 361, 388),
    1452: ("Serpent Rod", 337, 362),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(OURS, "3DDATA")):
        sys.exit("run from the repo root (data/3DDATA not found)")
    spec = importlib.util.spec_from_file_location("ii", os.path.join(HERE, "import-item.py"))
    ii = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ii)

    path = os.path.join(OURS, STB_REL)
    _d, _o, rows, cols, data = ii.stb_read(path)

    if args.verify:
        bad = 0
        for r, (name, old, new) in sorted(FIXES.items()):
            cur = int(data[r][ATK_COL].decode("latin-1") or 0)
            ok = cur == new
            bad += 0 if ok else 1
            if not ok:
                print("  %-4d %-24s ATK %s *** expected %d ***" % (r, name[:24], cur, new))
        print("%d row(s) checked, %d not at the corrected value" % (len(FIXES), bad))
        sys.exit(1 if bad else 0)

    changed = 0
    for r, (name, old, new) in sorted(FIXES.items()):
        if not 0 <= r < len(data):
            sys.exit("row %d out of range" % r)
        got = data[r][0].decode("latin-1").strip()
        if got != name:
            sys.exit("row %d is %r, expected %r -- the table has shifted, refusing to "
                     "rewrite the wrong row" % (r, got, name))
        cur = int(data[r][ATK_COL].decode("latin-1") or 0)
        if cur == new:
            print("  %-4d %-24s already ATK %d" % (r, name[:24], new))
            continue
        if cur != old:
            sys.exit("row %d (%s) has ATK %d, expected %d (pre-fix) or %d (post-fix) -- "
                     "something else changed it; not guessing" % (r, name, cur, old, new))
        print("  %-4d %-24s ATK %4d -> %d  (+%d)" % (r, name[:24], cur, new, new - cur))
        ii.stb_set_cell(path, r, ATK_COL, str(new), args.dry_run)
        changed += 1

    if not args.dry_run and changed:
        _d, _o, r2, c2, d2 = ii.stb_read(path)
        assert (r2, c2) == (rows, cols), "table shape changed"
        for r, (_n, _old, new) in FIXES.items():
            assert int(d2[r][ATK_COL].decode("latin-1")) == new, "row %d did not take" % r
        print("verified: %d row(s) corrected, shape unchanged (%dx%d)" % (changed, r2 - 1, c2 - 1))
    print("\n%s" % ("DRY RUN - nothing written." if args.dry_run
                    else "done.  Restart the gameserver (it caches STBs) and re-bake."))


if __name__ == "__main__":
    main()
