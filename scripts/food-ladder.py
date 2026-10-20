"""Food ladder: level-gated heal-over-time tiers to level 240 (2026-10-20).

Self heal has two halves: food ("fruits"), which heals over time, and the Vital /
Spiritual Waters, the instant restores with a cooldown (scripts/water-restores.py).
Food stopped at ShavShav, 700 HP at 30 HP/s, about 8% of a level-240 Knight's bar,
and nothing was level gated. The user chose the 668 model (the official Rednim
client): every food heals over the same time, a higher tier heals more, and each
tier opens at a level. One tier every 15 levels, HP and MP, levels 1 to 240.

The code (citem.h UseItem_PotionDurationMS / UseItem_PotionCanReplace, the server's
classUSER::Use_pITEM, the client's status icon, prediction, tooltip and use check)
reads, on a heal-over-time row (a LIST_STATUS row of type HP / MP recovery):

    col 17/18  use requirement (AT_LEVEL 31, min level)
    col 20     total restored        col 21  seconds it takes (blank = retail rate)
    col 24     status row (1 HP / 4 MP for food; 2-3 / 5-6 for Vials and Bottles)

One heal over time runs per HP / MP, and a new one only replaces it if it heals at
least what that one still has to give.

Sizing (scripts/combatsim average-gear builds): an HP tier heals ~50-65% of the
median class's bar at its level (~30% of the tankiest); an MP tier is sized on the
bar halfway between the median class's MP and a Mage's. Food takes 20 s and costs
~0.3 zuly per HP / 0.5 per MP. The Health / Mana Vials and Bottles are the fast,
expensive tier: 10 s, ~4x the price per point, seven steps (1, 35, 70 ... 210), each
healing what the food tier of its level does. Herbal Medicine and the foods left out
of the ladder (Kiwi, Orange, Mango, Peach, Strawberry, Tomato, Plum, Meatball, the
breads, three juices) leave the shops; their rows are untouched, so drops of them
keep their retail values.

Art: the ladder reuses the food we ship. 668's top foods (the Snapper and Cactus
lines, Passionfruit Juice) already sit in our item atlas at 668's own icon indices
(upgrade-item-icons.py brought the sheets over), so they only need rows: 668's row
numbers where ours are free (139, 194-197), 198-199 for the two whose 668 rows hold
our Clan Point / Job Change. Levels 225 and 240 take three Jrose icons, appended to
the atlas (add-item-icon.py) and found again by their TSI label on a re-run. The
juices get 668's own glasses (ours were three pictures for nine juices).

Shops, by the level band each seller's town serves: Zant and the starter vendors
1-30, Junon Polis (and Juri's copy of its shop) to 75, Eucar 75-120, Xita Refuge
120-210, Karkia / the Abandoned Church 195-240, the potion sellers the matching fast
tiers. Every other item in those tabs keeps its slot order after the restores. Oro
had no seller at all: two new tabs, Food (195-240) and Potions (Bottles L/XL and the
Waters L/XL), for the bar owner in Muris and the Lojala trader at the Ancient Oasis
Shrine (both dialogs already had a store entry); their captions go to LIST_SELL_S.STL.

    python scripts/food-ladder.py --dry-run
    python scripts/food-ladder.py
    python scripts/food-ladder.py --verify
    python scripts/food-ladder.py --restore

Cell-level undo in build/food-ladder/manifest.json (STB cells, STL entries). The
three appended icons stay in the atlas on --restore (unused, harmless). `data/` is
gitignored, so this file is the record. The server reads LIST_USEITEM and LIST_SELL:
restart it, and re-bake the VFS.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from rosefmt.stb import Stb  # noqa: E402
from rosefmt.stl import Stl  # noqa: E402
from rosefmt.tsi import tsi_read  # noqa: E402

STB = os.path.join(REPO, "data", "3DDATA", "STB")
USE = os.path.join(STB, "LIST_USEITEM.STB")
SELL = os.path.join(STB, "LIST_SELL.STB")
NPC = os.path.join(STB, "LIST_NPC.STB")
NAMES = os.path.join(STB, "LIST_USEITEM_S.STL")
SELL_NAMES = os.path.join(STB, "LIST_SELL_S.STL")
TABLES = (("use", USE), ("sell", SELL), ("npc", NPC))
BACKUP_DIR = os.path.join(REPO, "build", "food-ladder")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")
JROSE_RES = r"C:\Users\Thomas\Desktop\Testclients\Jrose\3Ddata\Control\Res"

AT_LEVEL, AT_HP, AT_MP = 31, 16, 17
FOOD_SECONDS, FAST_SECONDS = 20, 10
FOOD_ZULY_HP, FOOD_ZULY_MP = 0.3, 0.5
FAST_ZULY_HP, FAST_ZULY_MP = 1.2, 2.0

# (level, row, amount). Rows above 137 are new (NEW_ROWS).
HP_FOOD = [
    (1, 101, 100), (15, 102, 150), (30, 103, 250), (45, 107, 350), (60, 108, 450),
    (75, 109, 600), (90, 132, 750), (105, 133, 900), (120, 114, 1000), (135, 136, 1100),
    (150, 116, 1250), (165, 115, 1350), (180, 198, 1500), (195, 199, 1600),
    (210, 194, 1800), (225, 140, 2300), (240, 229, 2700),
]
MP_FOOD = [
    (1, 120, 60), (15, 121, 80), (30, 122, 140), (45, 123, 200), (60, 125, 275),
    (75, 124, 350), (90, 134, 425), (105, 135, 500), (120, 127, 650), (135, 137, 750),
    (150, 126, 850), (165, 130, 925), (180, 195, 1000), (195, 196, 1050),
    (210, 197, 1100), (225, 139, 1400), (240, 230, 1500),
]
# the fast tier: what the food tier of its level heals, in half the time
HP_FAST = [(1, 1, 100), (35, 2, 250), (70, 3, 450), (105, 4, 900), (140, 5, 1100),
           (175, 6, 1350), (210, 35, 1800)]
MP_FAST = [(1, 21, 60), (35, 22, 140), (70, 23, 275), (105, 24, 500), (140, 25, 750),
           (175, 26, 925), (210, 36, 1100)]
FAST_TEXT = {
    1: "A potion that restores HP quickly.", 2: "A potion that restores HP quickly.",
    3: "A potion that restores HP quickly.",
    4: "A strong medicine that restores HP quickly.",
    5: "A strong medicine that restores HP quickly.",
    6: "A strong medicine that restores HP quickly.",
    35: "A strong medicine that restores HP quickly.",
    21: "A potion that restores MP quickly.", 22: "A potion that restores MP quickly.",
    23: "A potion that restores MP quickly.",
    24: "A strong potion that restores MP quickly.",
    25: "A strong potion that restores MP quickly.",
    26: "A strong potion that restores MP quickly.",
    36: "A strong potion that restores MP quickly.",
}

HP_TEMPLATE, MP_TEMPLATE = 109, 125          # Cooked Meat, Orange Juice
# new rows: name, description, template, icon (int = an atlas index, str = a Jrose
# icon appended under that TSI label), field model (col 10)
NEW_ROWS = {
    198: ("Seared Snapper", "A snapper fillet seared over an open flame.", HP_TEMPLATE, 3162, 143),
    199: ("Snapper Stew", "Snapper simmered slowly with root vegetables.", HP_TEMPLATE, 3163, 143),
    194: ("Hot Snapper Goulash", "A fiery snapper goulash that warms to the bone.", HP_TEMPLATE, 3164, 143),
    140: ("Mutton Grill", "Mutton and vegetables grilled together on a hot iron dome.", HP_TEMPLATE, "food_mutton_grill", 143),
    229: ("Roast Turkey", "A whole roast turkey, golden and fit for a feast.", HP_TEMPLATE, "food_roast_turkey", 143),
    195: ("Cactus Root", "A tough root that stores water deep underground.", MP_TEMPLATE, 3165, 144),
    196: ("Cactus Water", "Cool water pressed from a desert cactus.", MP_TEMPLATE, 3166, 144),
    197: ("Rift Cactus Extract", "A strange extract from cacti grown by the rift.", MP_TEMPLATE, 3167, 144),
    139: ("Passionfruit Juice", "A sweet and tart tropical juice.", MP_TEMPLATE, 4093, 144),
    230: ("Frost Shaved Ice", "Shaved ice drizzled with syrup. Clears the head.", MP_TEMPLATE, "food_frost_shaved_ice", 144),
}
JROSE_ICONS = {"food_mutton_grill": 5531, "food_roast_turkey": 1673,
               "food_frost_shaved_ice": 3486}
# 668's own juice glasses (ours were three pictures for nine juices)
JUICE_ICONS = {123: 3048, 124: 1623, 125: 1621, 126: 3049, 127: 1620, 129: 1622,
               130: 3050, 131: 3051}

# shop tabs (LIST_SELL rows) -> HP tiers and MP tiers they sell, by level
FOOD_TABS = {
    249: (1, 30),           # Sharlin, Zant
    307: (1, 15),           # Huey, Arua's Fairy, Pony (Birth Island, Adventurer's Plain)
    390: (1, 30),           # Mile, Breezy Hills
    494: (1, 75),           # Harin, Junon Polis; Juri, Live House SEVEN
    532: (75, 120),         # Anzhelika, Eucar
    555: (120, 210),        # Peppie, Xita Refuge
    563: (195, 240),        # Ginias (Karkia), Nemo (Abandoned Church): food + potions
}
FAST_TABS = {
    222: (1, 35),           # Tryteh (Zant), the two teleporters
    471: (1, 105),          # Chester (Junon), Med (Gorge), clan house, Shimasaburo, Juri
    528: (70, 140),         # Pabel, Eucar
    551: (140, 210),        # Catherine Clara, Xita Refuge
    563: (175, 210),        # Ginias, Nemo
}
SHOP_FIRST_COL = 2

# Oro (2026-10-20, after the first in-game test): nobody there sold a restore. Two new
# tabs (free LIST_SELL rows, picked once and kept in the manifest) for the bar owner in
# Muris, whose dialog already had a store entry and no tab, and for the Lojala trader at
# the Ancient Oasis Shrine, the Wasteland's outpost, after his guns. Oro runs ~205-240.
ORO_TABS = (
    ("oro_food", "Food", dict(food=(195, 240))),
    ("oro_potions", "Potions", dict(fast=(175, 210), extra=(12, 13, 31, 32))),  # + Waters L/XL
)
ORO_SELLERS = {2125: "[Oro Bar Owner] Sahrazod", 2112: "[Lojala Trader] Brizo"}
NPC_TAB_COLS = (21, 22, 23, 24)


def num(b):
    s = b.strip()
    return int(s) if s.lstrip(b"-").isdigit() else 0


def enc(v):
    return v if isinstance(v, bytes) else str(v).encode()


def price(amount, rate):
    return int(round(amount * rate / 5.0)) * 5


def managed_rows(use):
    """Every heal-over-time HP / MP row (status 1-6) plus the new rows: the items the
    shop tabs are rebuilt around."""
    rows = {r for r in range(1, use.rows) if use.occupied(r)
            and 1 <= num(use.get(r, 24)) <= 6 and num(use.get(r, 19)) in (AT_HP, AT_MP)}
    return rows | set(NEW_ROWS)


# ------------------------------------------------------------------ icons
def find_icon(label):
    """Atlas index of a sprite by its TSI label, or None."""
    sys.path.insert(0, HERE)
    aii = _tool("add-item-icon")
    textures, blocks = tsi_read(os.path.join(REPO, aii.TSI))
    want = label.encode("ascii")
    for flat, bi, slot, *_ in aii.iter_sprites(blocks):
        raw = blocks[bi][1][slot * 54:(slot + 1) * 54]
        if raw[22:54].rstrip(b"\0") == want:
            return flat
    return None


def _tool(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"),
                                                  os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jrose_icon(index):
    """One 40x40 icon of the Jrose item atlas as an RGBA image."""
    from PIL import Image
    aii = _tool("add-item-icon")
    uii = _tool("upgrade-item-icons")
    files = {f.lower(): f for f in os.listdir(JROSE_RES)}
    textures, blocks = tsi_read(os.path.join(JROSE_RES, files["item1.tsi"]))
    for flat, _b, _s, tex, x1, y1, x2, y2 in aii.iter_sprites(blocks):
        if flat == index:
            sheet = files[os.path.basename(textures[tex][0]).lower()]
            rgb, _ = uii.read_sheet(os.path.join(JROSE_RES, sheet))
            return Image.fromarray(rgb[y1:y2, x1:x2]).convert("RGBA")
    raise SystemExit("Jrose icon %d not found in %s" % (index, JROSE_RES))


def resolve_icons(dry):
    """{label: atlas index}, appending the Jrose icons not in the atlas yet."""
    out = {}
    for label, jidx in JROSE_ICONS.items():
        idx = find_icon(label)
        if idx is None:
            if dry:
                print("   icon %-22s would be appended (Jrose %d)" % (label, jidx))
                continue
            cwd = os.getcwd()
            os.chdir(REPO)                       # add-item-icon works from the repo root
            try:
                idx = _tool("add-item-icon").add_icon(jrose_icon(jidx), label, False)
            finally:
                os.chdir(cwd)
        out[label] = idx
    return out


# ------------------------------------------------------------------ plan
def plan_use(use, icons):
    """{(row, col): bytes} for LIST_USEITEM."""
    out = {}

    def tier(row, level, amount, status, seconds, zuly, desc_only=False):
        out[(row, 17)] = enc(AT_LEVEL) if level > 1 else b""
        out[(row, 18)] = enc(level) if level > 1 else b""
        out[(row, 20)] = enc(amount)
        out[(row, 21)] = enc(seconds)
        out[(row, 24)] = enc(status)
        out[(row, 5)] = enc(price(amount, zuly))

    for row, (name, _desc, tpl, icon, model) in NEW_ROWS.items():
        for c in range(use.cols):
            out[(row, c)] = use.get(tpl, c)
        out[(row, 0)] = name.encode()
        out[(row, 9)] = enc(icons.get(icon, 0) if isinstance(icon, str) else icon)
        out[(row, 10)] = enc(model)
        out[(row, 27)] = b"LUSE%03d" % row
    for level, row, amount in HP_FOOD:
        tier(row, level, amount, 1, FOOD_SECONDS, FOOD_ZULY_HP)
    for level, row, amount in MP_FOOD:
        tier(row, level, amount, 4, FOOD_SECONDS, FOOD_ZULY_MP)
    for level, row, amount in HP_FAST:
        tier(row, level, amount, num(use.get(row, 24)), FAST_SECONDS, FAST_ZULY_HP)
    for level, row, amount in MP_FAST:
        tier(row, level, amount, num(use.get(row, 24)), FAST_SECONDS, FAST_ZULY_MP)
    for row, icon in JUICE_ICONS.items():
        out[(row, 9)] = enc(icon)
    return out


def code(row):
    return b"%d" % (10 * 1000 + row)


def shop_spec(oro_rows):
    """{tab: dict(food=(lo, hi), fast=(lo, hi), extra=rows, name=caption)}."""
    spec = {}
    for tab, band in FOOD_TABS.items():
        spec.setdefault(tab, {})["food"] = band
    for tab, band in FAST_TABS.items():
        spec.setdefault(tab, {})["fast"] = band
    for key, name, s in ORO_TABS:
        spec[oro_rows[key]] = dict(s, name=name)
    return spec


def free_sell_rows(sell, npc, need):
    """Empty LIST_SELL rows no NPC points at (stock-muris-shops.py's rule)."""
    used = {npc.i(r, c) for r in range(npc.rows) for c in NPC_TAB_COLS}
    out = [r for r in range(1, sell.rows)
           if r not in used and not any(sell.get(r, c).strip() for c in range(sell.cols))]
    if len(out) < need:
        raise SystemExit("only %d free LIST_SELL rows, need %d" % (len(out), need))
    return out[:need]


def plan_npc(npc, original, oro_rows):
    """The Oro sellers' tab columns: what they had, then the new tabs."""
    new = [oro_rows[key] for key, _n, _s in ORO_TABS]
    out = {}
    for row in ORO_SELLERS:
        had = [num(original.get((row, c), npc.get(row, c))) for c in NPC_TAB_COLS]
        tabs = [t for t in had if t and t not in new] + new
        if len(tabs) > len(NPC_TAB_COLS):
            raise SystemExit("NPC %d: %d tabs for %d columns" % (row, len(tabs), len(NPC_TAB_COLS)))
        tabs += [0] * (len(NPC_TAB_COLS) - len(tabs))
        for c, t in zip(NPC_TAB_COLS, tabs):
            out[(row, c)] = enc(t) if t else b""
    return out


def plan_sell(sell, original, managed, spec):
    """Each tab: its tiers first (HP, MP; food then the fast tier), then whatever else
    it sold, in its old order, closed up."""
    out = {}
    for tab in sorted(spec):
        s = spec[tab]
        cells = [original.get((tab, c), sell.get(tab, c)).strip()
                 for c in range(SHOP_FIRST_COL, sell.cols)]
        kept = [v for v in cells if v and not (num(v) // 1000 == 10 and num(v) % 1000 in managed
                                               and num(v) < 100000)]
        new = []
        if "food" in s:
            lo, hi = s["food"]
            new += [code(r) for lv, r, _ in HP_FOOD if lo <= lv <= hi]
            new += [code(r) for lv, r, _ in MP_FOOD if lo <= lv <= hi]
        if "fast" in s:
            lo, hi = s["fast"]
            new += [code(r) for lv, r, _ in HP_FAST if lo <= lv <= hi]
            new += [code(r) for lv, r, _ in MP_FAST if lo <= lv <= hi]
        new += [code(r) for r in s.get("extra", ()) if code(r) not in kept]
        if "name" in s:
            out[(tab, 0)] = s["name"].encode()
            out[(tab, 1)] = b"LSEL%d" % tab
        items = new + kept
        if len(items) > len(cells):
            raise SystemExit("shop tab %d: %d items for %d slots" % (tab, len(items), len(cells)))
        items += [b""] * (len(cells) - len(items))
        for i, v in enumerate(items):
            out[(tab, SHOP_FIRST_COL + i)] = v
    return out


def plan_names():
    """{STL key: (name, description)}: the new rows, and the fast tier's text (it no
    longer heals "slowly")."""
    out = {"LUSE%03d" % r: (name, desc) for r, (name, desc, *_x) in NEW_ROWS.items()}
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    tables = {}
    for key, path in TABLES:
        raw = open(path, "rb").read()
        tables[key] = Stb(path)
        if tables[key].to_bytes() != raw:
            print("ABORT: the STB writer does not round-trip %s byte-for-byte" % path)
            return 1
    names = Stl(NAMES, encoding="utf-8")
    tab_names = Stl(SELL_NAMES, encoding="utf-8")
    for stl, path in ((names, NAMES), (tab_names, SELL_NAMES)):
        if stl.to_bytes() != open(path, "rb").read():
            print("ABORT: the STL writer does not round-trip %s byte-for-byte" % path)
            return 1
    man = (json.load(open(MANIFEST, encoding="utf-8")) if os.path.isfile(MANIFEST)
           else {"use": {}, "sell": {}, "stl_new": [], "stl_text": {}, "icons": {}})
    for k, v in (("npc", {}), ("oro_rows", {}), ("sell_stl_new", [])):
        man.setdefault(k, v)

    def originals(key):
        return {tuple(int(x) for x in k.split(",")): v.encode("latin-1")
                for k, v in man[key].items()}

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        for key, path in TABLES:
            stb = tables[key]
            for (r, c), old in originals(key).items():
                stb.set(r, c, old)
            open(path, "wb").write(stb.to_bytes())
        names.remove(man["stl_new"])
        for k, old in man["stl_text"].items():
            names.set_field(k, 1, old)
        names.write(NAMES)
        tab_names.remove(man["sell_stl_new"])
        tab_names.write(SELL_NAMES)
        os.remove(MANIFEST)
        print("restored LIST_USEITEM, LIST_SELL, LIST_NPC and the two STLs "
              "(the appended icons stay in the atlas)")
        return 0

    use, sell, npc = tables["use"], tables["sell"], tables["npc"]
    for row, name in ORO_SELLERS.items():
        if npc.get(row, 0).strip() != name.encode():
            print("ABORT: LIST_NPC %d is %r, expected %r" % (row, npc.get(row, 0).strip(), name))
            return 1
    if not man["oro_rows"]:
        picked = free_sell_rows(sell, npc, len(ORO_TABS))
        man["oro_rows"] = {key: r for (key, _n, _s), r in zip(ORO_TABS, picked)}
    oro_rows = man["oro_rows"]
    spec = shop_spec(oro_rows)
    for row in NEW_ROWS:
        if use.occupied(row) and (row, 0) not in originals("use") \
                and use.get(row, 0).strip() != NEW_ROWS[row][0].encode():
            print("ABORT: LIST_USEITEM %d is taken (%r)" % (row, use.get(row, 0).strip()))
            return 1
    for row, (name, *_x) in NEW_ROWS.items():
        k = "LUSE%03d" % row
        if names.has(k) and k not in man["stl_new"] and names.name(k) != name:
            print("ABORT: STL key %s is taken (%r)" % (k, names.name(k)))
            return 1

    managed = managed_rows(use)
    icons = resolve_icons(a.dry_run or a.verify)
    if a.verify and len(icons) != len(JROSE_ICONS):
        print("VERIFY FAILED: Jrose icons missing from the atlas: %s"
              % sorted(set(JROSE_ICONS) - set(icons)))
        return 1
    todo = {"use": plan_use(use, icons),
            "sell": plan_sell(sell, originals("sell"), managed, spec),
            "npc": plan_npc(npc, originals("npc"), oro_rows)}
    pending = {k: {rc: v for rc, v in cells.items() if tables[k].get(*rc).strip() != v.strip()}
               for k, cells in todo.items()}
    new_names = {k: v for k, v in plan_names().items()
                 if names.name(k) != v[0] or names.field(k, 1) != v[1]}
    new_text = {"LUSE%03d" % r: t for r, t in FAST_TEXT.items()
                if names.field("LUSE%03d" % r, 1) != t}
    # the client draws a tab's caption from LIST_SELL_S.STL (col 1's key), never col 0
    new_tabs = {"LSEL%d" % oro_rows[key]: (oro_rows[key], name) for key, name, _s in ORO_TABS
                if tab_names.name("LSEL%d" % oro_rows[key]) != name}

    for title, table in (("HP food", HP_FOOD), ("MP food", MP_FOOD),
                         ("HP fast", HP_FAST), ("MP fast", MP_FAST)):
        print("%s:" % title)
        for lv, row, amount in table:
            nm = NEW_ROWS[row][0] if row in NEW_ROWS else use.get(row, 0).strip().decode()
            print("   lv %3d  %4d %-22s %5d  %s" % (
                lv, row, nm, amount, todo["use"][(row, 5)].decode() + " z"))
    for tab in sorted(spec):
        vals = [todo["sell"][(tab, c)] for c in range(SHOP_FIRST_COL, sell.cols)
                if todo["sell"][(tab, c)]]
        print("   shop tab %d%s: %s" % (tab, " (%s, new)" % spec[tab]["name"] if "name" in spec[tab]
                                        else "", b" ".join(vals).decode()))
    for row, name in ORO_SELLERS.items():
        print("   %s tabs: %s" % (name, " ".join(
            todo["npc"][(row, c)].decode() for c in NPC_TAB_COLS if todo["npc"][(row, c)])))

    n = (sum(len(v) for v in pending.values()) + len(new_names) + len(new_text)
         + len(new_tabs))
    if a.verify:
        if n:
            print("VERIFY FAILED: %d cell(s) / name(s) differ from the plan" % n)
            for k, cells in pending.items():
                for rc in sorted(cells)[:10]:
                    print("   %s %s: %r != %r" % (k, rc, tables[k].get(*rc), cells[rc]))
            return 1
        print("ALL CHECKS PASSED -- ladder rows, new items, icons, names and shop tabs "
              "are as planned.")
        return 0
    if not n:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: %d cell(s) / name(s) would change, nothing written" % n)
        return 0
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for key, (row, name) in new_tabs.items():
        if tab_names.has(key):
            tab_names.set_name(key, name)
        else:
            tab_names.append(key, row, name)
            man["sell_stl_new"].append(key)
    tab_names.write(SELL_NAMES)
    for key, path in TABLES:
        stb = tables[key]
        for (r, c), v in pending[key].items():
            man[key].setdefault("%d,%d" % (r, c), stb.get(r, c).decode("latin-1"))
            stb.set(r, c, v)
        open(path, "wb").write(stb.to_bytes())
    for k, (name, desc) in new_names.items():
        if names.has(k):
            names.set_name(k, name)
            names.set_field(k, 1, desc)
        else:
            names.append(k, int(k[4:]), name, desc)
            man["stl_new"].append(k)
    for k, text in new_text.items():
        man["stl_text"].setdefault(k, names.field(k, 1))
        names.set_field(k, 1, text)
    names.write(NAMES)
    man["icons"] = icons
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    print("wrote %d cell(s) / name(s) (undo: --restore, manifest in %s)" % (n, BACKUP_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
