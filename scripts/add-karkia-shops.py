"""Stage 6d: give Karkia working shops.

Karkia shipped six NPCs with shop tabs, and none of them sold anything useful:

  Gelt      4019  Spire Village      tab 585 -- past the end of LIST_SELL.STB
  Nemo      4142  Abandoned Church   tab 584 -- past the end of LIST_SELL.STB
  Belfa     4103  Foot of the Tower  tabs 478-481, shared with Crune
  Orentark  4104  Foot of the Tower  tabs 245/248, shared -- Materials, Dealer Skill
  Ginias    4089  Memories           tab 593 -- past the end of LIST_SELL.STB
  Astraea   4108  Memories           tab 594 -- past the end, *and* union-gated

Two findings shaped what this script does, both from reading the client rather
than from the tables:

**A shop only exists if the NPC's .CON calls `GF_openStore`.** Exactly three
Karkia conversations do it in the shipped data: EM86-001 (Nemo), EM86-013
(Gelt), EM02-114 (Orentark), EM03-002 (Ginias) and EM03-011 (Astraea). Belfa
did **not**, and was given one by `quest-editor con-store` (a QEX1 appendix)
in a later pass; his tabs are wired here. Sulfa (4017, EM86-011) is the same
case, added 2026-09-13 to sell the second lv230 armour set.

The two that still have no store call are recorded so nobody re-investigates
them:

  Ash        4088  EM03-001  calls only GF_openBank -- he is the Memories
                             *storagekeeper*, so a bank and no shop is correct.
                             He carries no tab and needs none.
  Bordeaux   4097  EM03-010  calls nothing at all. His four tabs (512-515) are
                             therefore inert exactly as Belfa's were: 512 is a
                             "Skill Book" row shared with Olleck, and 513-515
                             have no STL key and no stock. Giving him a shop
                             means a con-store append first; left alone
                             deliberately.

All three call `GF_openStore(owner, 0)`, and the client only draws the fourth
tab for `bSpecialTab = 1`. So **only LIST_NPC cols 21-23 are usable**; col 24
is written as 0.

**A shop NPC's union number lives in the drop-chance column.**
`NPC_UNION_NO(I)` is `#define`d to `NPC_DROP_ITEM(I)` -- game col 20, the same
cell that means "roll my own drop table" on a monster. Both `CStore::ChangeStore`
and the server's trade handler refuse the shop when that value is non-zero and
does not equal the player's union. Astraea shipped with **20**, and
`CObjAVT::SetCur_UNION` rejects anything `>= MAX_UNION_COUNT` (10) while the DB
column defaults to 0 -- so no player can ever hold union 20 and her shop was
shut for everyone, whatever her tab pointed at. She is the only Karkia NPC with
a non-zero union; this script clears it. Note only tabs 0-2 (cols 21-23) are
gated by nothing else: `ChangeStore` always draws them and reads col 24 only
for `openStore(npc, 1)`.

**A dangling tab row is safe but blank.** `STBDATA::value` bounds-checks the
flat index and returns a default, so rows 584/585 read as empty rather than
out of bounds -- an empty nameless tab, not a crash. (Note the client's
`CStringManager::GetStoreTabName` guards with `iIndex > row_count`, an
off-by-one that lets `iIndex == row_count` through; harmless for the same
reason, but it is a real off-by-one.)

Rather than pad LIST_SELL out to row 585 with 22 dead rows, this appends four
rows at 561-564 and repoints the two NPCs onto them.

--- what is sold, and why

`Rose::Store::encode_store_item` has a **wide form** -- `type * 100000 + no`
for ids above 999 -- supported by the client, the server and the shop editor.
That is what makes the imported Jrose weapons sellable at all: at ids 1381-1453
they are unreachable through the legacy `type * 1000 + no` packing, the same
wall that stops them ever dropping (see doc/project-drops.md).

None of the 73 imported weapons is sold anywhere today, so all of them are
Karkia-exclusive by construction. They fall into clean level tiers, and Oro's
weapon merchant (Huzam, tabs 5 and 6) already occupies 210 and 230:

    Oro sells        210, 230
    Karkia sells     215, 225      <- this script
    Karkia drops     220, 235, 240 <- reserved, doc/project-drops.md

The level-240 set is the mythical-name tier (Bahamut, Phoenix, Griffon,
Unicorn, Albion, Quetzalcoatl, ...) and is deliberately left for drops, as are
220 and 235. Two tiers left over are used by neither: the partial level-210 set
(1420-1425) duplicates Oro's tier, and the low oddments (1447-1453, levels
150-205) sit far below Karkia's 215-240 band.

Requirements are on our own scale, not inflated -- our level-230 Viper weapons
already ask STR 335-365, and the level-215 tier here asks 277-321.

Astraea, Karkia's armourer, sells the **materials** her own dialog asks for --
Memories became reachable in stage 7a and stage 8 imported them, so she is the one
NPC in the game for whom that stock was already written into her lines.

She also sells the **armour**, in her two remaining tab columns: the level-225
Refined Steam and level-230 Unit Core tiers, 16 items each (since 2026-10-20 the
level-220 Legendary Crystal and the Legionnaire line instead: armour-ladder-pass.py
turned those two into level 90/110 cosmetics). She is the only armour
seller Karkia has -- the [Starsteel Armourer], and the only NPC there whose `.CON`
opens a store *and* whose role fits -- so there is nothing to split across. The
level-240 Egyptian tier is deliberately **not** sold: it is the cap tier and is
reserved for loot, the same split the weapons use.

Both armour tabs are laid out as a grid rather than poured in from slot 0, matching
Muris' Azim: **one set per column, one body part per row** -- cap over body over
gloves over boots, classes left to right. A tab is 8 columns x 6 rows and the client
places each icon at its slot index, so pouring 16 items in sequentially would run all
four caps along the top row and wrap each set across a line break.

Idempotent. `--dry-run` / `--verify` / `--restore`. Backups go to build/, never
beside the data: src/pipeline/src/pack.rs walks the data tree filtering only
*hidden* entries -- no extension filter -- so a .bak in data/3DDATA/STB gets
baked into the .vfs.

After running: restart the servers (they cache STBs at startup) and re-bake the
client VFS.
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STB = os.path.join(ROOT, "data", "3DDATA", "STB")
SELL_STB = os.path.join(STB, "LIST_SELL.STB")
SELL_STL = os.path.join(STB, "LIST_SELL_S.STL")
NPC_STB = os.path.join(STB, "LIST_NPC.STB")
BACKUP = os.path.join(ROOT, "build", "karkia-shops-backup")
SIDECAR = os.path.join(ROOT, "build", "karkia-shops.json")

WIDE_BASE = 100000          # Rose::Store::kWideBase
LEGACY_MAX_NO = 999         # Rose::Store::kLegacyMaxItemNo
MAX_ITEM_NO = 2047          # tagBaseITEM: m_nItemNo is 11 bits
SLOTS = 48                  # LIST_SELL is 2 + 48 columns

T_WEAPON, T_USE, T_NATURAL = 8, 10, 12
T_CAP, T_BODY, T_ARMS, T_FOOT = 2, 3, 4, 5

# A shop tab is 8 columns x 6 rows (dlgstore.xml stacks six 41px STORE_MIDDLE
# strips over 48 slots) and the client positions each icon by its slot index, so
# an empty slot is a real gap rather than something the next item slides into.
# Armour is therefore laid out as a grid, the same way Muris' Azim is:
# one set per column, one body part per row, ascending level left to right.
GRID_COLS = 8
ARMOUR_PIECES = ((T_CAP, "cap"), (T_BODY, "body"), (T_ARMS, "arms"), (T_FOOT, "foot"))


def armour_grid(first_row, classes=4):
    """{slot: (type, item no)} for one armour tier.

    `first_row` is the Soldier row; the four class variants are consecutive, and
    every slot table uses the same row number for a given class -- which is true
    because import-midtier-armour.py wrote them that way on purpose. A tier whose
    tables disagree (the retail-numbered Crystal set) passes {type: Soldier row}.
    """
    out = {}
    for r, (typ, _name) in enumerate(ARMOUR_PIECES):
        first = first_row[typ] if isinstance(first_row, dict) else first_row
        for c in range(classes):
            out[r * GRID_COLS + c] = (typ, first + c)
    return out

# LIST_NPC shop-tab columns. Col 24 is the fourth tab, which the client draws
# only for openStore(npc, 1); every Karkia seller passes 0, so it stays empty.
TAB_COLS = (21, 22, 23, 24)

# NPC_UNION_NO is #defined to NPC_DROP_ITEM -- game col 20. Non-zero means
# "union shop"; MAX_UNION_COUNT is 10 and SetCur_UNION rejects anything at or
# above it, so any value >= 10 is a shop no player can ever open.
COL_UNION = 20
MAX_UNION_COUNT = 10        # datatype.h

# The imported Jrose weapons, by level tier. Complete coverage of all 13 weapon
# types in each of the two tiers we sell.
ARMS_215 = [1381, 1384, 1387, 1390, 1393, 1396, 1399, 1402, 1405, 1408, 1411,
            1414, 1417]
ARMS_225 = [1382, 1385, 1388, 1391, 1394, 1397, 1400, 1403, 1406, 1409, 1412,
            1415, 1418]

# Reserved for drops -- listed so the split is recorded in one place, and so
# --verify can prove none of them leaked into a shop.
DROP_ONLY = (
    [1426, 1427, 1428, 1429, 1430, 1431, 1432, 1433, 1434, 1435, 1436] +   # 220
    [1437, 1438, 1439, 1440, 1441, 1442, 1443, 1444, 1445, 1446] +         # 235
    [1383, 1386, 1389, 1392, 1395, 1398, 1401, 1404, 1407, 1410, 1413,
     1416, 1419]                                                           # 240
)

# The 25 materials imported in stage 8 (LIST_NATURAL 740-764). Astraea sells
# them because they are what *her own translated dialog* asks for -- Starlight,
# the Tomes, the Arcane Sigil, Black Iron Gears, the colour cores, Stella Libra,
# Sol Niger Horns. Until stage 8 those were names with nothing behind them.
#
# Split on the same principle as the weapon tiers above: the ordinary reagents
# are bought over a counter, and the ones the dialog treats as hard to come by
# are not for sale at any price. Graphistone is "found only in the Tower of
# Despair"; Starlight is what the Starsteel armourers demand you bring *them*;
# the Tomes are asked for fifty at a time; the Sacred Demon Crystals break
# Nagia's seal. Selling those would contradict the lines that make them worth
# having, so they are earned instead: `add-karkia-drops.py` put all thirteen into
# the drop tables on 2026-09-12, several onto the very monster their own
# description names. Graphistone alone is still unobtainable, deliberately --
# it says it is found only in the Tower of Despair, which has no population yet.
MATERIALS_SOLD = [742,                    # Black Iron Gear
                  743, 744, 745, 746,     # the four lesser Scrolls
                  751,                    # Talisman of Enchantment
                  753, 754, 755, 756,     # the four Latin colour cores
                  757,                    # Stella Libra
                  763]                    # Tamahagane
MATERIALS_RESERVED = [740, 741,           # Graphistone, Starlight
                      747, 748, 749, 750, # the four Tomes
                      752,                # Arcane Sigil of Enchantment
                      758,                # Sol Niger Horn
                      759, 760, 761, 762, # Nagia's seal chain, Fafnir's stone
                      764]                # Stardust Lantern

ARROWS = [301, 302, 303, 304, 305, 306, 311, 312, 313, 314, 315, 316, 317]
BULLETS = [321, 322, 323, 324, 325, 326, 327, 331, 332, 333]
SHELLS = [341, 342, 343, 344, 345, 351, 352, 353]
REPAIR_HAMMER = 291

# Endgame consumables only -- the church has little, but what it has is potent.
SUPPLIES = [3, 6, 35,        # Health Vial (L), Health Bottle (L) / (XL)
            23, 26, 36,      # Mana Vial (L), Mana Bottle (L) / (XL)
            9,               # Herbal Medicine (L)
            12, 13, 14,      # Vital Water (L) / (XL) / (XXL)
            31, 32, 33,      # Spiritual Water (L) / (XL) / (XXL)
            352]             # Junon Polis Return Scroll

# (row, tab caption, [(item type, item no), ...])
#
# 563 and 564 are chosen to land on LSEL563 "Potions" and LSEL564 "Ammo/Arrows",
# two orphan STL keys that were already in LIST_SELL_S.STL with no matching STB
# row. Reusing them means the captions are right with no new strings -- and it
# is why the potion tab is 563 and the ammunition tab 564, rather than the other
# way round. The caption written to col 0 is only a dev label; the client shows
# the STL text, so `check_captions` asserts the two agree.
NEW_TABS = [
    (561, "Karkia Arms lv215", [(T_WEAPON, n) for n in ARMS_215]),
    (562, "Karkia Arms lv225", [(T_WEAPON, n) for n in ARMS_225]),
    (563, "Potions", [(T_USE, n) for n in SUPPLIES]),
    (564, "Ammo/Arrows",
     [(T_NATURAL, n) for n in ARROWS + BULLETS + SHELLS]
     + [(T_USE, REPAIR_HAMMER)]),
    (565, "Karkia Materials", [(T_NATURAL, n) for n in MATERIALS_SOLD]),
    # A 4x4 block per tab: class across, body part down. 566/567 first held the
    # two mid tiers, Refined Steam lv225 and Unit Core lv230; armour-ladder-pass.py
    # (2026-10-20) made those level 90/110 cosmetics, sold in Junon Polis, so 566
    # sells the lv220 tier (Legendary Crystal) and 567 is empty and unreferenced.
    (566, "Legendary Crystal lv220",
     armour_grid({T_CAP: 977, T_BODY: 904, T_ARMS: 880, T_FOOT: 878})),
    (567, "Unit Core lv230", {}),
    # The second lv230 set (import-legionnaire-armour.py, rows 262-265). It was
    # first kept off Astraea's counter on purpose, so the choice between two lv230
    # sets was made by profile in two zones; with Unit Core gone it is the tier,
    # and both Sulfa and Astraea sell it.
    (568, "Forgotten Armors", armour_grid(262)),
]

# npc row -> the three drawable tabs, in order
#
# Belfa carries the same arms and ammunition as Gelt, deliberately. He is the
# Master Smith at the Foot of the Tower, which is the staging zone -- gear
# should be buyable where you prepare, not only in the deep field. Sharing the
# rows costs nothing and keeps one place to edit the stock.
#
# His old tabs 478-481 are *our* low-level rows, shared with Crune: level 38-77
# stock in a level 215-240 zone. Repointing leaves Crune untouched.
NPC_TABS = {
    4019: (561, 562, 564),   # [Spire Warrior] Gelt  -- arms and ammunition
    # Sulfa stands beside Gelt in Spire Village and sold nothing: no tabs, and a
    # dialog with no store call. She is a Spire *warrior*, so plate is in
    # character, and the village is the first Karkia zone a player reaches --
    # which puts the heavier lv230 set on the road in and the lighter one deep
    # in Memories, where you need it against the casters. Her store call is a
    # QEX1 append (`quest-editor con-store ../data 4017 sulfa`), the same
    # mechanism Belfa got.
    4017: (568, 0, 0),       # [Spire Warrior] Sulfa -- the Legionnaire tier
    4103: (561, 562, 564),   # [Master Smith] Belfa  -- the Tower staging shop
    4142: (563, 0, 0),       # [Shrine Maiden] Nemo  -- "short of supplies"
    # Memories, reachable since stage 7a. Ginias is the General Store, so he
    # carries the church's consumables and the ammunition -- both rows already
    # exist, so he costs no new stock. Astraea is the armourer and sells the
    # reagents she talks about; armour when there is armour to sell.
    4089: (563, 564, 0),     # [General Store] Ginias
    4108: (565, 566, 568),   # [Starsteel Armourer] Astraea -- materials, lv220, lv230
}

# Sellers whose union column must be cleared, or the shop refuses to open for
# every player alive. See the union note in the module docstring.
CLEAR_UNION = {4108}
NPC_NAMES = {4019: "[Spire Warrior] Gelt", 4103: "[Master Smith] Belfa",
             4017: "[Spire Warrior] Sulfa",
             4142: "[Shrine Maiden] Nemo", 4089: "[General Store] Ginias",
             4108: "[Starsteel Armourer] Astraea"}

# STB tables an item type is validated against, for the don't-sell / range check
TYPE_TABLE = {T_WEAPON: "LIST_WEAPON.STB", T_USE: "LIST_USEITEM.STB",
              T_NATURAL: "LIST_NATURAL.STB", T_CAP: "LIST_CAP.STB",
              T_BODY: "LIST_BODY.STB", T_ARMS: "LIST_ARMS.STB",
              T_FOOT: "LIST_FOOT.STB"}

ITEM_DONT_SELL = 0x01


def load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def encode(item_type, item_no):
    """Rose::Store::encode_store_item."""
    if not 0 < item_no <= MAX_ITEM_NO:
        raise SystemExit(f"item no {item_no} outside 1..{MAX_ITEM_NO}")
    return (item_type * 1000 + item_no if item_no <= LEGACY_MAX_NO
            else item_type * WIDE_BASE + item_no)


def authored():
    """{row: caption} as of the last successful run, from the sidecar.

    A caption is only safe to *change* if we wrote it. Without this the two
    guards below cannot tell "renaming our own tab" from "stealing a retail
    key", and both refuse -- which is right for the second case and wrong for
    the first. Empty before the first run, which is also correct: nothing is
    ours yet.
    """
    if not os.path.exists(SIDECAR):
        return {}
    with open(SIDECAR, encoding="utf-8") as fh:
        return {int(r): n for r, n in json.load(fh).get("tabs", [])}


def check_captions(oro):
    """A pre-existing STL key must say what we think it says.

    LSEL563/LSEL564 already existed as orphans with no STB row. Reusing a key
    is only safe if its text matches the stock we are about to put behind it --
    otherwise the client draws someone else's caption over our tab.
    """
    stl = oro.Stl(SELL_STL)
    lookup = {k.decode("latin-1"): j for j, (k, _i) in enumerate(stl.keys)}
    mine = authored()
    bad = []
    for row, name, _items in NEW_TABS:
        key = f"LSEL{row}"
        j = lookup.get(key)
        if j is None:
            continue                      # we will append it ourselves
        texts = {r[j][0].decode("latin-1") for r in stl.langs if r[j][0]}
        if texts == {name}:
            continue
        if texts == {mine.get(row)}:
            continue                      # our own caption, being renamed
        bad.append(f"{key} already reads {sorted(texts)}, "
                   f"but this tab is {name!r}")
    return bad


def tab_slots(items):
    """The 48 packed cells for one tab, from either a flat list or a {slot: item} map.

    A list is poured in from slot 0 (fine for a bag of consumables); a dict places
    each item at an exact slot, which is what the armour grid needs.
    """
    out = [0] * SLOTS
    if isinstance(items, dict):
        for slot, pair in items.items():
            out[slot] = encode(*pair)
    else:
        for i, pair in enumerate(items):
            out[i] = encode(*pair)
    return out


def stock_pairs(items):
    return list(items.values()) if isinstance(items, dict) else list(items)


def check_stock(rd):
    """Refuse to stock anything missing, or flagged not-for-sale."""
    bad = []
    for _row, _name, items in NEW_TABS:
        if isinstance(items, dict):
            over = [k for k in items if not 0 <= k < SLOTS]
            if over:
                bad.append(f"row {_row}: slots outside 0..{SLOTS - 1}: {over}")
        elif len(items) > SLOTS:
            bad.append(f"row {_row}: {len(items)} items exceeds {SLOTS} slots")
        for ty, no in stock_pairs(items):
            tbl = rd.Stb(os.path.join(STB, TYPE_TABLE[ty]), "utf-8")
            if no >= tbl.rows or not rd.scrub(tbl.s(no, 0)).strip():
                bad.append(f"type {ty} no {no}: no such item")
                continue
            if tbl.i(no, 3) & ITEM_DONT_SELL:
                bad.append(f"type {ty} no {no} "
                           f"({rd.scrub(tbl.s(no, 0))}): flagged don't-sell")
    leaked = [n for _r, _nm, items in NEW_TABS for ty, n in stock_pairs(items)
              if ty == T_WEAPON and n in DROP_ONLY]
    if leaked:
        bad.append(f"drop-only weapons leaked into a shop: {leaked}")
    held = [n for _r, _nm, items in NEW_TABS for ty, n in stock_pairs(items)
            if ty == T_NATURAL and n in MATERIALS_RESERVED]
    if held:
        bad.append(f"reserved materials leaked into a shop: {held}")
    overlap = sorted(set(MATERIALS_SOLD) & set(MATERIALS_RESERVED))
    if overlap:
        bad.append(f"materials both sold and reserved: {overlap}")
    return bad


def apply(oro, dry):
    sell = oro.Stb(SELL_STB)
    npc = oro.Stb(NPC_STB)
    stl = oro.Stl(SELL_STL)
    report = []

    want_rows = max(r for r, _n, _i in NEW_TABS) + 1
    if sell.rows < want_rows:
        report.append(f"LIST_SELL.STB {sell.rows} -> {want_rows} rows")
        sell.grow_to(want_rows)

    mine = authored()
    for row, name, items in NEW_TABS:
        if sell.occupied(row):
            cur = sell.get(row, 0).decode("latin-1")
            if cur != name and cur != mine.get(row):
                raise SystemExit(
                    f"LIST_SELL row {row} is occupied by {cur!r} -- refusing "
                    "to overwrite a row we did not author")
        key = f"LSEL{row}"
        sell.set(row, 0, name.encode("latin-1"))
        sell.set(row, 1, key.encode("latin-1"))
        for slot, packed in enumerate(tab_slots(items)):
            sell.set(row, 2 + slot, str(packed).encode("latin-1") if packed
                     else b"")
        # The client draws the STL text, never col 0, so a caption change that
        # updates only the STB is invisible -- the tab keeps its old name and
        # nothing says why.
        if not stl.has(key):
            stl.append(key, row, name)
            report.append(f"  STL +{key} = {name!r}")
        elif stl.name(key) != name:
            was = stl.name(key)
            stl.set_name(key, name)
            report.append(f"  STL ~{key} = {was!r} -> {name!r}")
        report.append(f"  row {row} {name!r}: {len(stock_pairs(items))} items")

    for nid, tabs in NPC_TABS.items():
        before = [npc.get(nid, c).decode("latin-1") or "0" for c in TAB_COLS]
        for c, v in zip(TAB_COLS, list(tabs) + [0]):
            npc.set(nid, c, str(v).encode("latin-1") if v else b"0")
        after = [npc.get(nid, c).decode("latin-1") for c in TAB_COLS]
        report.append(f"  npc {nid} {NPC_NAMES[nid]}: {before} -> {after}")
        if nid in CLEAR_UNION:
            was = npc.get(nid, COL_UNION).decode("latin-1") or "0"
            npc.set(nid, COL_UNION, b"0")
            report.append(f"    union {was} -> 0 (was an unopenable union shop)")

    if dry:
        return report, None
    return report, (sell.to_bytes(), npc.to_bytes(), stl.to_bytes())


def verify(oro, rd):
    sell = oro.Stb(SELL_STB)
    npc = oro.Stb(NPC_STB)
    stl = oro.Stl(SELL_STL)
    bad = []
    for row, name, items in NEW_TABS:
        if sell.rows <= row:
            bad.append(f"LIST_SELL has no row {row}")
            continue
        if sell.get(row, 0).decode("latin-1") != name:
            bad.append(f"row {row}: caption is "
                       f"{sell.get(row, 0).decode('latin-1')!r}")
        if not stl.has(f"LSEL{row}"):
            bad.append(f"row {row}: no STL key LSEL{row}")
        elif stl.name(f"LSEL{row}") != name:
            bad.append(f"row {row}: STL caption is "
                       f"{stl.name(f'LSEL{row}')!r}, not {name!r} -- the client "
                       "draws this one, so the tab would show the old name")
        got = [int(sell.get(row, 2 + s) or 0) for s in range(SLOTS)]
        want = tab_slots(items)
        if got != want:
            bad.append(f"row {row}: stock differs from plan")
    for nid, tabs in NPC_TABS.items():
        got = tuple(int(npc.get(nid, c) or 0) for c in TAB_COLS)
        if got != tuple(list(tabs) + [0]):
            bad.append(f"npc {nid}: tabs are {got}, expected "
                       f"{tuple(list(tabs) + [0])}")
    # nothing reserved for drops may be on sale anywhere in the table
    for row in range(sell.rows):
        for s in range(SLOTS):
            v = int(sell.get(row, 2 + s) or 0)
            if v <= 0:
                continue
            ty, no = ((v // WIDE_BASE, v % WIDE_BASE) if v >= WIDE_BASE
                      else (v // 1000, v % 1000))
            if ty == T_WEAPON and no in DROP_ONLY:
                bad.append(f"row {row} slot {s}: drop-only weapon {no} on sale")
            if ty == T_NATURAL and no in MATERIALS_RESERVED:
                bad.append(f"row {row} slot {s}: reserved material {no} on sale")
    # a seller whose union no player can hold has a permanently closed shop
    for nid in NPC_TABS:
        u = int(npc.get(nid, COL_UNION) or 0)
        if u >= MAX_UNION_COUNT:
            bad.append(f"npc {nid} {NPC_NAMES[nid]}: union {u} >= "
                       f"MAX_UNION_COUNT ({MAX_UNION_COUNT}), shop cannot open")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    import rosedata as oro  # the shared data layer (was import-oro.py)
    rd = load("rose-data-reader")

    if args.restore:
        if not os.path.isdir(BACKUP):
            sys.exit("no backup -- nothing to restore")
        n = 0
        for path in (SELL_STB, NPC_STB, SELL_STL):
            src = os.path.join(BACKUP, os.path.basename(path))
            if os.path.isfile(src):
                shutil.copyfile(src, path)
                n += 1
        if os.path.exists(SIDECAR):
            os.remove(SIDECAR)
        print(f"restored {n} table(s) from {os.path.relpath(BACKUP, ROOT)}")
        return 0

    if args.verify:
        bad = verify(oro, rd)
        print(f"{len(NEW_TABS)} tabs, {len(NPC_TABS)} NPCs; "
              f"{len(bad)} problem(s)"
              + ("\n  " + "\n  ".join(bad) if bad else ""))
        return 1 if bad else 0

    bad = check_captions(oro) + check_stock(rd)
    if bad:
        print("refusing to write:")
        for b in bad:
            print("  " + b)
        return 1

    report, blobs = apply(oro, args.dry_run)
    print("\n".join(report))
    total = sum(len(stock_pairs(i)) for _r, _n, i in NEW_TABS)
    print(f"\n{len(NEW_TABS)} tabs, {total} items, "
          f"{len(DROP_ONLY)} weapons reserved for drops")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP, exist_ok=True)
    for path in (SELL_STB, NPC_STB, SELL_STL):
        bak = os.path.join(BACKUP, os.path.basename(path))
        if not os.path.exists(bak):
            shutil.copyfile(path, bak)
    for path, blob in zip((SELL_STB, NPC_STB, SELL_STL), blobs):
        with open(path, "wb") as fh:
            fh.write(blob)
    with open(SIDECAR, "w", encoding="utf-8") as fh:
        json.dump({"tabs": [[r, n] for r, n, _i in NEW_TABS],
                   "npcs": {str(k): list(v) for k, v in NPC_TABS.items()}},
                  fh, indent=1)

    bad = verify(oro, rd)
    if bad:
        print("VERIFY FAILED after writing:")
        for b in bad:
            print("  " + b)
        return 1
    print("written and verified; restart the servers and re-bake the VFS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
