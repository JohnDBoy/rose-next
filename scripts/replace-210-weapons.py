#!/usr/bin/env python3
"""Replace the level-210 Viper line with tsuki's level-220 set (2026-10-25).

The Viper / Akela / Matrix / Oasis line (LIST_WEAPON 1355-1367, one per type, at 210
since weapon-ladder-pass.py) had disappointing visuals (user). The tsuki client
carries a complete 13-type set at level 220 in consecutive rows of its table (27 ...
452: Blaze Dancer, Glacier Cutter ... Resilience Dual Wield), the user's pick from its
many 220 weapons. Checked against every weapon of ours, mesh and texture:

  * all 13 meshes are new to us;
  * Resilience Dual Wield shares a texture with Dual Monarch Swords (1354, the
    custom dual with no level requirement) on a different mesh -- left to the eye;
  * not taken: Holy Grand Slasher (tsuki 530, the other 1H candidate) -- its mesh
    is the blade of our Elemental Dual Swords (126, level 225), and no weapon may
    wear a higher tier's look. Golden Eagle Slayer (559, mace) and Legend Hydra
    Crossbow (576) were the clean alternatives to Glacier Cutter and Nepheramun.

Each lands at **its own tsuki row number**: all 13 are blank rows with empty model
objects here and referenced by nothing, and under 1000 (quests and recipes can name
them). tsuki is the late NARose lineage with its own type numbering (its 221 covers
every two-hander, its 251 is dual swords), so it is art-only: the type comes from the
template, which is the **Viper-line weapon of the same type -- every tier column is
inherited exactly** (level 210, requirement, both bonuses, ATK, speed, motion,
sounds; the values are listed below so --verify needs no erased row). The gem anchor
(col 43) is tsuki's, as for the earlier tsuki import: four rows carry none there
(Lava Axe, Mana Shooter, Plasmatic Fusion Launcher, Oblivion Staff), so a gem
glows on dummy 0 on those. All dummies come across (no effects on any), so the
indices hold.

Icons are copied from tsuki's atlas (`--copy-icon`): ours holds other art at those
indices. Ground models: tsuki's drop objects are the weapons' own files. Names and
descriptions are tsuki's English, lightly corrected (the spear's grammar, "yin-yang",
"katar").

Dual Tornado Rifles (381, dual guns) stays at 210: the set has no dual gun.

Warmaster Sword wears the Asmodeus Ritual Blade's stance (TYPE_MOTION column 21,
asmodeus-stance.py; the user's call after seeing it in tsuki, where every 2H sword
has it): `STANCE` below. asmodeus-stance.py --restore refuses while it does.

--- the order

    python scripts/replace-210-weapons.py --dry-run
    python scripts/replace-210-weapons.py              # import the 13
    python scripts/replace-210-weapons.py --erase      # restock Huzam's tab, strip 1355-1367
    python scripts/replace-210-weapons.py --verify

The line's only live reference was **Huzam's "Weapons lv210" tab** (Muris, LIST_SELL
row 6; no drop table, quest, recipe or monster hand names it). `--erase` restocks it
first, the way stock-muris-shops.py plans it -- every level-210 weapon that is not
red boss loot, in row order, now the 13 and Dual Tornado Rifles -- so that script's
--verify holds, and records the old cells for --restore. weapon-ladder-pass.py, whose
swap put the Viper line at 210, no longer verifies or restores those rows and that
tab (`SUPERSEDED`).

Engine, erase and undo: `weapon_tier.py`. No character in the dev database owned a
Viper-line weapon (`item.type_id = 8`); check again on a database with players. All
13 rows are in weapon-identity-pass.py's SKIP. `data/` is gitignored, so this file
is the record. Restart the servers, re-bake the VFS.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from weapon_tier import Row, Tier, data, load_manifest, main, save  # noqa: E402
from rosefmt import Stb  # noqa: E402

TSUKI = r"C:\Users\Thomas\Desktop\Testclients\tsuki"
LEVEL = 210

# row (ours = tsuki's), Viper template, type, name, requirement, bonus 1, bonus 2, ATK, description
ROWS = [
    (27, 1355, 211, "Blaze Dancer", "10:281", "20:40", "10:15", 442,
     "A blade with the ability to burn the enemy on every strike."),
    (58, 1356, 212, "Glacier Cutter", "10:365", "20:40", "10:15", 510,
     "The core of this mace is taken from a nevermelting glacier. It freezes everything it cuts."),
    (128, 1357, 221, "Warmaster Sword", "10:281", "20:40", "10:15", 403,
     "A sword with a dark aura that feels like being possessed when touching it."),
    (187, 1358, 222, "Deadly Avarice", "10:290", "20:40", "10:15", 376,
     "Humanity's excessive avarice, gathered into a single point, gives this spear its deadly edge."),
    (154, 1359, 223, "Lava Axe of Athoum", "10:316", "20:40", "10:15", 467,
     "An ancient axe that was owned by the lava god lord Athoum in the dark era to annihilate demons."),
    (229, 1360, 231, "Carnival Bow", "11:222", "20:50", "22:73", 417,
     "A bow that was infused with fire spirits in the middle of a spiritual carnival in order to give unlimited power."),
    (259, 1361, 232, "Mana Shooter", "13:202", "20:40", "13:15", 387,
     "A thin and weak looking gun with an immense amount of power."),
    (288, 1362, 233, "Plasmatic Fusion Launcher", "10:151", "18:10", "", 414,
     "A launcher that can fuse materials inside it to create a deadly projectile which is capable of making a crater."),
    (326, 1363, 241, "Oblivion Staff", "12:320", "20:40", "12:55", 360,
     "It's said that this staff has a hidden spell that can erase the memory from any living being."),
    (358, 1364, 242, "Void Conjurer", "12:330", "20:40", "12:46", 320,
     "A legendary wand with a stone in it to help focus the mana power when a spell is being cast."),
    (426, 1365, 251, "Ritual Wrist Blade", "11:335", "20:40", "26:69", 338,
     "A seven-edged katar that is used by oriental priests for their rituals."),
    (452, 1366, 252, "Resilience Dual Wield", "11:235", "20:40", "18:82", 446,
     "A pair of swords that hold positive and negative energy, like the yin-yang circle."),
    (80, 1367, 271, "Nepheramun Crossbow", "11:308", "20:40", "11:15", 360,
     "A crossbow that was lost and found after several centuries in a volcano. It's still in great shape."),
]

OLD = {1355: "Viper Blade", 1356: "Viper Sting", 1357: "Viper Sword", 1358: "Viper Spear",
       1359: "Viper Axe", 1360: "Akela Bow", 1361: "Matrix Rifle", 1362: "Matrix Cannon",
       1363: "Oasis Staff", 1364: "Oasis Wand", 1365: "Akela Katar",
       1366: "Dual Viper Blades", 1367: "Akela Bowgun"}

# Warmaster Sword wears the Asmodeus stance (user, 2026-10-25, after seeing it in the
# tsuki preview -- tsuki gives every 2H sword that stance): TYPE_MOTION column 21 from
# asmodeus-stance.py, which replaces only stop / walk / run; attacks and skills stay
# the 2H sword's.
STANCE = {128: "21"}
COL_MOTION = 34

SELL_REL = r"3DDATA\STB\LIST_SELL.STB"
TAB_LABEL = "Weapons lv210"


def row(our, tmpl, wtype, name, req, b1, b2, atk, desc):
    cells = {35: str(atk)}
    for (cid, cval), pair in zip(((21, 22), (24, 25), (27, 28)), (req, b1, b2)):
        cells[cid], cells[cval] = pair.split(":") if pair else ("", "")
    if our in STANCE:
        cells[COL_MOTION] = STANCE[our]
    return Row(our, our, tmpl, wtype, name, desc, cells)


def muris():
    spec = importlib.util.spec_from_file_location(
        "stock_muris_shops", os.path.join(HERE, "stock-muris-shops.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def huzam_tab(tier):
    """(LIST_SELL row, {slot: encoded item}) as stock-muris-shops.py plans the tab,
    with the old line already left out."""
    sm = muris()
    sell = Stb(data(SELL_REL))
    rows = json.load(open(sm.SIDECAR))["rows"]
    tab = [r for r in rows if sell.get(r, 0).decode("latin-1") == TAB_LABEL]
    if len(tab) != 1:
        sys.exit("no single %r tab among stock-muris-shops.py's rows %s" % (TAB_LABEL, rows))
    items = [r for r in sm.rows_at_level(sm.load_importer(), "LIST_WEAPON", LEVEL)
             if r not in tier.old]
    expect = {w[0]: w[4] for w in sm.WEAPON_TABS}[TAB_LABEL]
    if len(items) != expect:
        sys.exit("%d weapons at level %d, stock-muris-shops.py expects %d"
                 % (len(items), LEVEL, expect))
    return tab[0], {i: sm.encode_item(8, r) for i, r in enumerate(items)}


def restock(tier, dry):
    tab, slots = huzam_tab(tier)
    sell = Stb(data(SELL_REL))
    man = load_manifest(tier)
    changes = 0
    for i in range(48):
        c = 2 + i
        want = str(slots[i]).encode() if i in slots else b"0"
        cur = sell.get(tab, c).strip()
        if cur != want and not (i not in slots and cur in (b"", b"0")):
            man["sell"].setdefault("%d,%d" % (tab, c), cur.decode("latin-1"))
            sell.set(tab, c, want)
            changes += 1
    print("Huzam's %r tab (LIST_SELL %d): %d slot(s) %s" % (TAB_LABEL, tab, changes,
          "to change" if dry else "restocked"))
    if changes and not dry:
        open(data(SELL_REL), "wb").write(sell.to_bytes())
        save(tier, man)


def check(tier):
    tab, slots = huzam_tab(tier)
    sell = Stb(data(SELL_REL))
    got = {i: int(sell.get(tab, 2 + i).strip() or 0) for i in range(48)}
    want = {i: slots.get(i, 0) for i in range(48)}
    return [] if got == want else ["Huzam's %r tab differs from the plan" % TAB_LABEL]


TIER = Tier(key="replace-210-weapons", source=TSUKI, level=LEVEL,
            rows=[row(*r) for r in ROWS], old=OLD, restock=restock, check=check)

if __name__ == "__main__":
    sys.exit(main(TIER))
