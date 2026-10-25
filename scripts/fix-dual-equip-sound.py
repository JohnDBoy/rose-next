#!/usr/bin/env python3
r"""Point the dual-wield weapons at a real equip sound instead of an empty row.

THE DEFECT
----------
`ITEM_EQUIP_SOUND` is **column 11** of every item STB
(`src/common/include/rose/io/stb.h`), played by `CObjUSER::Set_ITEM` when an item
lands in an equipment slot:

    g_pSoundLIST->IDX_PlaySound(ITEM_EQUIP_SOUND(sITEM.GetTYPE(), sITEM.GetItemNO()))

The value is a row index into `FILE_SOUND.STB`, whose column 0 is the .wav path.
Five dual-wield weapons point at **row 742, which is empty**, so equipping them
plays nothing:

    1366  Dual Viper Blades   (ours, pre-existing -- the source of the other four)
    1414  Mirere Blades       1415  Escada Blades
    1416  Giranda             1445  Hecatoncheir

The four imports inherited it honestly: `import-item.py --art-only` clones every
column from a template row, and their template is 1366.

WHY 577 AND NOT A NEW SOUND
---------------------------
Row 742 is **empty in all seven reference dumps** (667, Evo 137, Jrose,
QQ-iROSE, RoseZA, ruff, titanRose) -- it was never a sound in any lineage, so
filling it would be inventing data. Meanwhile **every dual weapon in every dump
uses 577** = `Sound\item\Item_weapon2.wav`: 392 rows in 667, 329 in RoseZA,
156 in Evo 137, 54 in ruff, 53 in titanRose, and **41 of our own 46 duals**.
Only Dual Viper Blades diverges, and QQ-iROSE carries the same defect on four
rows, which places it upstream of us rather than in anything we did.

So this is not a judgement call about which sound suits a dual sword -- it
restores the value the rest of the table, and every other dump, already uses.

The .wav files themselves ship **loose in the game directory** (`sound/item/`),
not in the VFS: there are no `.wav` under `data/` at all. 576/577/578 all
resolve there, so no asset work is needed.

SCOPE
-----
These 5 rows are the *only* dangling equip sounds in the game: an audit of all
13 item tables (face/cap/body/arms/foot/back/jewel/weapon/subwpn/useitem/
jemitem/natural/pat) found 3,806 rows with a valid sound and exactly these 5
without.

Idempotent; --dry-run and --verify supported.
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OURS = "data"
STB_REL = os.path.join("3DDATA", "STB", "LIST_WEAPON.STB")
SND_REL = os.path.join("3DDATA", "STB", "FILE_SOUND.STB")
EQUIP_SOUND_COL = 11
WEAPON_TYPE_COL = 4
DUAL = "252"
BROKEN, WANT = "742", "577"

# row -> expected name, so the pass refuses to rewrite a shifted table
ROWS = {
    1414: "Mirere Blades",
    1415: "Escada Blades",
    1416: "Giranda",
}
# 1445 Hecatoncheir and 1366 Dual Viper Blades were erased on 2026-10-25
# (replace-235-weapons.py, replace-210-weapons.py); their rows are blank. Their
# replacements, Jawbreaker Doon (999) and Resilience Dual Wield (452), cloned the
# fixed sound from them.


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

    # The target sound must actually resolve, or this trades silence for silence.
    _d2, _o2, srows, _sc, sdata = ii.stb_read(os.path.join(OURS, SND_REL))
    want_i = int(WANT)
    wav = sdata[want_i][0].decode("latin-1").strip() if want_i < srows else ""
    if not wav:
        sys.exit("FILE_SOUND row %s is empty -- refusing to point weapons at it" % WANT)
    print("target sound: FILE_SOUND row %s -> %s" % (WANT, wav))

    if args.verify:
        bad = 0
        for r, name in sorted(ROWS.items()):
            cur = data[r][EQUIP_SOUND_COL].decode("latin-1").strip()
            ok = cur == WANT
            bad += 0 if ok else 1
            print("  %-5d %-20s equip_sound=%-5s %s"
                  % (r, name, cur, "OK" if ok else "*** expected %s ***" % WANT))
        sys.exit(1 if bad else 0)

    changed = 0
    for r, name in sorted(ROWS.items()):
        if not 0 <= r < len(data):
            sys.exit("row %d out of range" % r)
        got = data[r][0].decode("latin-1").strip()
        if got != name:
            sys.exit("row %d is %r, expected %r -- the table has shifted, refusing to "
                     "rewrite the wrong row" % (r, got, name))
        wtype = data[r][WEAPON_TYPE_COL].decode("latin-1").strip()
        if wtype != DUAL:
            sys.exit("row %d (%s) is weapon type %s, not dual (%s)" % (r, name, wtype, DUAL))
        cur = data[r][EQUIP_SOUND_COL].decode("latin-1").strip()
        if cur == WANT:
            print("  %-5d %-20s already %s" % (r, name, WANT))
            continue
        if cur != BROKEN:
            sys.exit("row %d (%s) has equip sound %r, expected %s (broken) or %s (fixed) -- "
                     "something else changed it; not guessing" % (r, name, cur, BROKEN, WANT))
        print("  %-5d %-20s equip_sound %s -> %s" % (r, name, cur, WANT))
        ii.stb_set_cell(path, r, EQUIP_SOUND_COL, WANT, args.dry_run)
        changed += 1

    if not args.dry_run and changed:
        _d3, _o3, r2, c2, d2 = ii.stb_read(path)
        assert (r2, c2) == (rows, cols), "table shape changed"
        for r in ROWS:
            assert d2[r][EQUIP_SOUND_COL].decode("latin-1").strip() == WANT, \
                "row %d did not take" % r
        print("verified: %d row(s) repointed, shape unchanged (%dx%d)" % (changed, r2 - 1, c2 - 1))
    print("\n%s" % ("DRY RUN - nothing written." if args.dry_run
                    else "done.  Restart the gameserver (it caches STBs) and re-bake."))


if __name__ == "__main__":
    main()
