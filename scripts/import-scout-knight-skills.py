"""Two Scout and two crossbow-Knight signatures: Arrow Shower, Deadly Snipe, Volcanic Shot, Star Gazer.

    python scripts/import-scout-knight-skills.py --dry-run
    python scripts/import-scout-knight-skills.py
    python scripts/import-scout-knight-skills.py --verify
    python scripts/import-scout-knight-skills.py --restore

then the icons (that tool owns the atlas; the PNGs are cut by --icon-png):

    python scripts/import-scout-knight-skills.py --icon-png build/scout-knight-skills
    python scripts/add-skill-icon.py build/scout-knight-skills/<key>.png --name <key> --skill-row <first>-<last>

Why
---
The class identity pass after the Raider (2026-10-18). The user picked the four from the
dump survey (`doc/skill-candidates.md`) and approved their looks in game from GM test rows
(`scout-knight-anim-test.py`, since removed):

* **Arrow Shower** (667 1870) -- the **Scout's first area skill**, on bow or crossbow.
  667's new `bow_arrowshower_m1` clip, then a rain of arrows (`_ARROW_RAIN_01.eft`, ours,
  unused by any row until now) on the target's spot, **poisoning** what it hits -- the
  Scout wears a pack down (667 had a "Poison Arrow Shower" variant). Follows Poison Arrow.
* **Deadly Snipe** (Jrose 6111) -- the Scout's **finisher** with a bow: the longest shot in
  the class and its heaviest single hit, on the triple-shot clip with Jrose's heavy-arrow
  effects. It lowers the target's **Dodge** so what follows lands. **No stun**, though the
  design asked for "a short stun": a skill's two statuses share one duration (LIST_SKILL
  col 14, `Skill_ApplyIngSTATUS`), so the stun would have been as long as the Dodge Down,
  and Eagle Shot (Hawk Shot rank 10) already gives the Scout a stun. Follows Hawk Shot.
* **Volcanic Shot** (Jrose 5202) -- the crossbow Knight's **defensive bolt**: a meteor on
  the crossbow triple shot that sets the target **Burning** and lowers its **Attack Power**
  -- the Knight's self-sufficiency at range. Follows Range Bow Shot.
* **Star Gazer** (Jrose 6121) -- the crossbow Knight's **crowd tool** (its only area
  skills belonged to the melee kit): star shards on the target's spot that **slow**
  everything there and lower its **Defense** -- Slow Shot for a pack. Follows Slow Shot.

Arrow Shower and Star Gazer are type 7, like Luna Stone and Ice Bang: they land where the
target stood at the key press, and the client plays the bullet's effect at that spot.
Volcanic Shot and Deadly Snipe are type 3 with mode 1 (attack the target after); our own
bow shots are type 6, but the test proved type 3 with a bullet.

Each status rolls on its own (chance = ratio x (level x 2 + INT + 20) / (RES x 0.6 + 5 +
Dodge)); with these classes' ~15 INT, ratio 70 -> 100 lands 50-65% per target and 80 ->
110 lands 55-70%, both rising with rank because the chance decays with level.

Presentation, as tested
-----------------------
* Arrow Shower's clip goes in at **FILE_MOTION 669 / TYPE_MOTION 98** -- 667's own 681/221
  collide with Jrose's Shot Master and Star Gazer rows, and Jrose's numbering matches ours.
  Its rain is 667's FILE_EFFECT 2018 / LIST_EFFECT 279 "Arrow Rain".
* Star Gazer's motions are ours (`hoke_*`, FILE_MOTION 673-675); Jrose's TYPE_MOTION
  220-222 point at them. **Its rune circle is patched**: Jrose's `_runaston_03_yellow_green`
  draws its flat ground mesh with the depth test on, which z-fought the terrain and
  flickered; every ground scope mesh we ship has it off (`rosefmt.eft.with_mesh_flags`).
* Every other effect and bullet row goes in at its source's number (all blank here):
  FILE_EFFECT 1069 / 1057 / 2536 / 1464 / 1639, LIST_EFFECT 272 / 47 / 320.

The numbers (ranks 1 -> 10, linear; full table with --dry-run)
--------------------------------------------------------------
    Arrow Shower    power 250 -> 600     cd 14 -> 10 s  MP 60 -> 130   6 -> 8 m   Poison III
    Deadly Snipe    power 100 -> 230 x3  cd 20 -> 15 s  MP 70 -> 150   38 -> 42 m Dodge Down 20 -> 35%
    Volcanic Shot   power  40 ->  85 x3  cd 12 ->  9 s  MP 50 -> 110   Burning + Attack Power Down 15 -> 25%
    Star Gazer      power 250 -> 650     cd 20 -> 16 s  MP 80 -> 160   7 -> 9 m   slow 30 -> 45% + Defense Down 15 -> 25%

**Deadly Snipe and Volcanic Shot hit three times**: the server multiplies a skill's damage
by the attack frames in its action clip (the triple shots carry 56/66/26), not by col 70,
so their power is per arrow, like the Hawker's triple shot. And each frame repeats the
formula's Attack Power term, so a triple-frame skill keeps a large floor whatever its
power: the first cut (600 -> 1400 and 400 -> 1000, sized as whole casts) one-shot
everything for 9999 from level 130, and a longer cooldown changed nothing -- plain
fights last one cast. They are sized per cast against the class's own big shot.

Combat sim, auto-builds (average gear), the new skills put first in the rotation (the
auto-build ranks by raw power and never picks a triple-frame skill on its own), star
monsters: per cast at level 200, Deadly Snipe 1.5x Eagle Shot, Volcanic Shot 1.1x
Range Bow Shot, Arrow Shower 0.86x Eagle Shot, Star Gazer 0.8x Range Bow Shot.
DPS against the auto-build without them:

    level              100       130       160       200
    crossbow Knight   +0/+6    -4/+4     +1/+12    +41/+34   (plain/star %)
    bow Scout         -6/+1   +14/+12   +57/+27    +82/+40

Plain swings follow one-shot thresholds. At 200 against stars that puts the Scout
(1701) and the crossbow Knight (1728) beside the Raider (1298 katar, 1894 dual). The
sim is one-on-one: the two area skills' reach and every crowd-control uptime is beyond
it, and it plays the slows and Dodge Down perfectly.

How a player gets them
----------------------
* Books LIST_USEITEM 859-862 (blank; copies of the Hawk Shot / Range Bow Shot books):
  Scout in Darren's Hawker tab 466 cols 30/31 (the Scout row), Knight in his Soldier tab
  462 cols 45/46 (beside the crossbow books).
* Trees: UI2 builds itself. Classic boxes are painted into `HOWKER_BOW_MASTERY.DDS` (Arrow
  Shower right of Poison Arrow, Deadly Snipe under Hawk Shot's rank-6 box) and
  `SOLDIER_CROSSBOW_MASTERY.DDS` (Star Gazer right of Slow Shot, Volcanic Shot right of
  Range Bow Shot); nodes in `skilltree_howker.xml` / `skilltree_soldier.xml`.
* Icons: 667's for Arrow Shower (new skills may take 667/668 art, 2026-10-17) and Jrose's
  for the other three, appended by `add-skill-icon.py`; ICONS records the indices.

Cell-level undo, the copied files, the pages and XML as they were: `build/scout-knight-skills/`.
Deploy: restart the server, re-bake, copy both tree XMLs loose into the launch folder.
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt.stb import Stb  # noqa: E402
from rosefmt.stl import Stl  # noqa: E402
from rosefmt import eft  # noqa: E402
import rosedata as ro  # noqa: E402

_spec = importlib.util.spec_from_file_location("rd", os.path.join(HERE, "rose-data-reader.py"))
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
RES_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "RES")
XML_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "xml")
DUMPS = {
    "jrose": (r"C:\Users\Thomas\Desktop\Testclients\Jrose", "3Ddata", "cp932"),
    "667": (r"C:\Users\Thomas\Desktop\Testclients\667\extracted data", "3DDATA", "latin-1"),
}
OUT = os.path.join(ROOT, "build", "scout-knight-skills")
MANIFEST = os.path.join(OUT, "manifest.json")

# rows copied cell for cell from a dump, at the dump's own number
COPY = [("jrose", "TYPE_MOTION.STB", [220, 221, 222]),
        ("667", "FILE_EFFECT.STB", [2018]), ("667", "LIST_EFFECT.STB", [279]),
        ("jrose", "FILE_EFFECT.STB", [1069, 1057, 2536, 1464, 1639]),
        ("jrose", "LIST_EFFECT.STB", [272, 47, 320])]
SHOWER_FM_SRC, SHOWER_FM, SHOWER_TM = 681, 669, 98
GROUND_MESH_FIX = {"3DDATA/EFFECT/_runaston_03_yellow_green.eft": 0}   # file -> mesh index

RANKS = 10
AT_MP, AT_LEVEL = 17, 31
AT_ATK, AT_DEF, AT_AVOID, AT_SPEED = 18, 19, 22, 23
ST_POISON_3, ST_SLOW, ST_ATK_DOWN, ST_DEF_DOWN, ST_DODGE_DOWN, ST_BURNING = 9, 15, 19, 21, 29, 62
CLASS_KNIGHT, CLASS_SCOUT = 61, 66
BOW, XBOW = 231, 271
LOOK_COLS = list(range(52, 77)) + [83, 84]   # motions, cast fx/sounds, action, bullet, hit fx


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


# statuses: [(LIST_STATUS row, ability, rate per rank or None)] -- slot 0 then slot 1
SKILLS = [
    dict(key="arrow_shower", name="Arrow Shower", dump="667", src=1870, jicon=443,
         cls=CLASS_SCOUT, level=90, prereq=(1621, 5), book=859, book_template=775,
         tab=466, shop_col=30, xml="skilltree_howker.xml", page="HOWKER_BOW_MASTERY.DDS",
         box=(398, 157), line=((300, 178), (398, 178)),
         anchor=('<SKILL INDEX="1621" OFFSETX="280" OFFSETY="234"/>', 9),
         desc=("You loose a volley high into the sky. It comes down as a rain of arrows on "
               "the spot your target stands, striking every enemy there and poisoning them."),
         power=lin(250, 600), reload=lin(70, 50), mp=lin(60, 130), sp=lin(35, 130),
         dist=lin(2000, 2400), scope=lin(600, 800), duration=lin(8, 12), ratio=lin(70, 100),
         statuses=[(ST_POISON_3, None, None)],
         cols={5: 7, 29: 2, 30: BOW, 31: XBOW, 68: SHOWER_TM}),
    dict(key="deadly_snipe", name="Deadly Snipe", dump="jrose", src=6111, jicon=251,
         cls=CLASS_SCOUT, level=120, prereq=(1701, 6), book=860, book_template=775,
         tab=466, shop_col=31, xml="skilltree_howker.xml", page="HOWKER_BOW_MASTERY.DDS",
         box=(398, 56), line=((419, 43), (419, 56)),
         anchor=('<SKILL INDEX="1701" OFFSETX="419" OFFSETY="79" LEVEL="6"/>', 12),
         desc=("You draw the bow to its limit and put everything into one long shot. It "
               "hits harder than anything else you fire and leaves the target unable to "
               "dodge for a while."),
         power=lin(100, 230), reload=lin(100, 75), mp=lin(70, 150), sp=lin(40, 140),
         dist=lin(3800, 4200), scope=None, duration=lin(8, 12), ratio=lin(80, 110),
         statuses=[(ST_DODGE_DOWN, AT_AVOID, lin(20, 35))],
         cols={5: 3, 29: 1, 30: BOW}),
    dict(key="volcanic_shot", name="Volcanic Shot", dump="jrose", src=5202, jicon=413,
         cls=CLASS_KNIGHT, level=100, prereq=(501, 5), book=861, book_template=675,
         tab=462, shop_col=45, xml="skilltree_soldier.xml", page="SOLDIER_CROSSBOW_MASTERY.DDS",
         box=(439, 149), line=((341, 170), (439, 170)),
         anchor=('<SKILL INDEX="501" OFFSETX="321" OFFSETY="226"/>', 6),
         desc=("You fire a bolt wrapped in burning rock. The target can be set Burning, and "
               "its Attack Power lowered, so it hits you softer while you keep your distance."),
         power=lin(40, 85), reload=lin(60, 45), mp=lin(50, 110), sp=lin(35, 130),
         dist=lin(2400, 2800), scope=None, duration=lin(6, 10), ratio=lin(80, 110),
         statuses=[(ST_BURNING, None, None), (ST_ATK_DOWN, AT_ATK, lin(15, 25))],
         cols={5: 3, 29: 1, 30: XBOW}),
    dict(key="star_gazer", name="Star Gazer", dump="jrose", src=6121, jicon=252,
         cls=CLASS_KNIGHT, level=130, prereq=(491, 8), book=862, book_template=675,
         tab=462, shop_col=46, xml="skilltree_soldier.xml", page="SOLDIER_CROSSBOW_MASTERY.DDS",
         box=(439, 100), line=((341, 121), (439, 121)),
         anchor=('<SKILL INDEX="491" OFFSETX="321" OFFSETY="177"/>', 6),
         desc=("You call down a shower of falling stars on the spot your target stands. "
               "Every enemy there can be slowed and have its Defense lowered."),
         power=lin(250, 650), reload=lin(100, 80), mp=lin(80, 160), sp=lin(40, 140),
         dist=lin(2000, 2400), scope=lin(700, 900), duration=lin(8, 12), ratio=lin(70, 100),
         statuses=[(ST_SLOW, AT_SPEED, lin(30, 45)), (ST_DEF_DOWN, AT_DEF, lin(15, 25))],
         cols={5: 7, 29: 2, 30: XBOW, 70: 1}),
]
ICONS = {"arrow_shower": 525, "deadly_snipe": 526,   # from add-skill-icon.py (2026-10-18)
         "volcanic_shot": 527, "star_gazer": 528}
PLACEHOLDER_ICON = 512

ART_ORIGIN, BOX_SIZE, LINE = (20, 75), 42, (74, 81, 99, 255)

tables = {}


def icon_at(box):
    return box[0] + ART_ORIGIN[0] + 1, box[1] + ART_ORIGIN[1] + 2


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def dump_root(d):
    return DUMPS[d][0]


def dload(d, name, _cache={}):
    if (d, name) not in _cache:
        root, sub, enc = DUMPS[d]
        _cache[(d, name)] = rd.Stb(os.path.join(root, sub, "STB", name), enc)
    return _cache[(d, name)]


# --- table rows and files ------------------------------------------------------------

def plan_cells():
    out = []
    for d, table, rows in COPY:
        ours, theirs = load(table), dload(d, table)
        for r in rows:
            want = [theirs.d[r][c] if c < theirs.cols else b"" for c in range(ours.cols)]
            if table == "TYPE_MOTION.STB":
                want = [b"" if v == b"0" else v for v in want]
            # a few blank LIST_EFFECT rows carry a stray "100" in col 8
            if any(v.strip(b"0") for v in ours.d[r] if v != b"100") and ours.d[r] != want:
                sys.exit(f"{table} row {r} is in use here ({ours.d[r][:2]}) -- refusing")
            out += [(table, r, c, v) for c, v in enumerate(want)]
    fm, tm = load("FILE_MOTION.STB"), load("TYPE_MOTION.STB")
    clip = dload("667", "FILE_MOTION.STB").d[SHOWER_FM_SRC]
    if any(fm.d[SHOWER_FM]) and fm.d[SHOWER_FM][0] != clip[0]:
        sys.exit(f"FILE_MOTION {SHOWER_FM} is in use here -- refusing")
    out += [("FILE_MOTION.STB", SHOWER_FM, c, clip[c] if c < len(clip) else b"") for c in range(fm.cols)]
    if any(tm.d[SHOWER_TM]) and set(tm.d[SHOWER_TM]) != {str(SHOWER_FM).encode()}:
        sys.exit(f"TYPE_MOTION {SHOWER_TM} is in use here -- refusing")
    out += [("TYPE_MOTION.STB", SHOWER_TM, c, str(SHOWER_FM).encode()) for c in range(tm.cols)]

    ui, sell = load("LIST_USEITEM.STB"), load("LIST_SELL.STB")
    for s in SKILLS:
        book = s["book"]
        if any(ui.d[book]):
            sys.exit(f"LIST_USEITEM {book} is in use ({ui.d[book][0]!r}) -- refusing")
        code = str(10000 + book).encode()
        for t in ("LIST_SELL.STB", "ITEM_DROP.STB"):
            hits = [r for r in range(load(t).rows) if code in load(t).d[r]]
            if hits:
                sys.exit(f"{t} rows {hits} already name item 10:{book} -- refusing")
        if sell.d[s["tab"]][s["shop_col"]].strip(b"0"):
            sys.exit(f"shop tab {s['tab']} col {s['shop_col']} holds {sell.d[s['tab']][s['shop_col']]!r}")
        over = {0: s["name"].encode(), 20: str(s["base"]).encode(), 27: f"LUSE{book}".encode()}
        out += [("LIST_USEITEM.STB", book, c, over.get(c, ui.d[s["book_template"]][c]))
                for c in range(ui.cols)]
        out.append(("LIST_SELL.STB", s["tab"], s["shop_col"], code))
    return [(t, r, c, v) for t, r, c, v in out if load(t).d[r][c] != v]


def asset_files():
    """[(dump, path)] for every file the skills need, ours or not."""
    out = {}
    clip = dload("667", "FILE_MOTION.STB").s(SHOWER_FM_SRC, 0).strip().replace("\\", "/")
    out[ro.norm(clip)] = ("667", clip)
    for d in DUMPS:
        fe = dload(d, "FILE_EFFECT.STB")
        efts = [fe.s(r, 1).strip().replace("\\", "/") for dd, t, rows in COPY
                if dd == d and t == "FILE_EFFECT.STB" for r in rows]
        for f in sorted(ro.effect_chain(efts, dump_root(d))):
            f = f.replace("\\\\", "\\").replace("//", "/")
            out.setdefault(ro.norm(f).replace("//", "/"), (d, f))
    return sorted(out.values())


def fix_ground_meshes():
    """Depth test off on the flat ground meshes in GROUND_MESH_FIX (idempotent)."""
    for f, mesh in GROUND_MESH_FIX.items():
        p = ro.rel_path(DATA, f)
        raw = open(p, "rb").read()
        if eft.read(raw)["meshes"][mesh]["flags"]["z_test"]:
            open(p, "wb").write(eft.with_mesh_flags(raw, mesh, z_test=0))
            print(f"  {os.path.basename(f)}: ground mesh {mesh} z_test 1 -> 0")


def ground_meshes_ok():
    return all(not eft.read(ro.rel_path(DATA, f))["meshes"][m]["flags"]["z_test"]
               for f, m in GROUND_MESH_FIX.items())


def skill_rows(s):
    sk = dload(s["dump"], "LIST_SKILL.STB")
    look = {c: sk.i(s["src"], c) for c in LOOK_COLS if sk.i(s["src"], c)}
    rows = []
    for n in range(RANKS):
        c = {0: s["name"], 1: s["base"], 2: n + 1, 3: s["sp"][n],
             4: 1,                  # SKILL_TAB_TYPE: the attack tab (blank = Basic)
             6: s["dist"][n], 7: 5, 9: s["power"][n], 10: 1,
             13: s["ratio"][n], 14: s["duration"][n], 15: 1,
             16: AT_MP, 17: s["mp"][n], 20: s["reload"][n],
             51: ICONS[s["key"]] or PLACEHOLDER_ICON, 86: f"LSkill{s['base']}"}
        c.update(look)
        c.update(s["cols"])
        if s["scope"]:
            c[8] = s["scope"][n]
        for slot, (status, ability, rate) in enumerate(s["statuses"]):
            c[11 + slot] = status
            if ability:
                c[21 + 3 * slot] = ability
                c[23 + 3 * slot] = rate[n]
        if n == 0:
            c.update({35: s["cls"], 39: s["prereq"][0], 40: s["prereq"][1],
                      45: AT_LEVEL, 46: s["level"]})
        rows.append([str(c.get(i, "")).encode("latin-1") for i in range(87)])
    return rows


# --- the classic trees ---------------------------------------------------------------

def res_path(name):
    hit = [f for f in os.listdir(RES_DIR) if f.upper() == name]
    if not hit:
        sys.exit(f"tree art {name} not found")
    return os.path.join(RES_DIR, hit[0])


def page_ok(page):
    from PIL import Image
    px = Image.open(res_path(page)).convert("RGBA").load()
    return all(px[s["box"][0], s["box"][1]][3] > 8 for s in SKILLS if s["page"] == page)


def draw_page(page):
    from PIL import Image, ImageDraw
    p = res_path(page)
    im = Image.open(p).convert("RGBA")
    px = im.load()
    mine = [s for s in SKILLS if s["page"] == page]
    for s in mine:
        bx, by = s["box"]
        if any(px[x, y][3] for y in range(by, by + BOX_SIZE) for x in range(bx, bx + BOX_SIZE)):
            sys.exit(f"{page}: the area at {bx},{by} is not empty -- refusing")
    d = ImageDraw.Draw(im)
    for s in mine:
        d.line(list(s["line"]), fill=LINE)
        bx, by = s["box"]
        d.rectangle([bx, by, bx + BOX_SIZE - 1, by + BOX_SIZE - 1], outline=LINE)
    im.save(p)


def target_xml(name, raw):
    out = raw
    for s in SKILLS:
        if s["xml"] != name:
            continue
        anchor, indent = s["anchor"]
        x, y = icon_at(s["box"])
        pad = " " * indent
        node = (anchor[:-2] + ">"
                + f'\n{pad}   <SKILL INDEX="{s["base"]}" OFFSETX="{x}" OFFSETY="{y}"/>'
                + f"\n{pad}</SKILL>")
        if anchor in out:
            out = out.replace(anchor, node, 1)
        elif node not in out:
            sys.exit(f"{name}: anchor not found ({anchor}) -- refusing")
    return out


def icon_pngs(out_dir):
    import numpy as np
    from PIL import Image
    spec = importlib.util.spec_from_file_location("usi", os.path.join(HERE, "upgrade-skill-icons.py"))
    usi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(usi)
    os.makedirs(out_dir, exist_ok=True)
    for s in SKILLS:
        root, sub, _ = DUMPS[s["dump"]]
        cell = usi.Atlas(os.path.join(root, sub)).cell(s["jicon"])
        if cell is None or usi.is_blank(cell):
            sys.exit(f"{s['dump']} sprite {s['jicon']} is blank or missing")
        p = os.path.join(out_dir, s["key"] + ".png")
        Image.fromarray(np.clip(cell, 0, 255).astype(np.uint8), "RGB").save(p)
        print(f"wrote {p}")


# --- main ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--icon-png", metavar="DIR", help="write the four source icons as 40x40 PNGs and stop")
    args = ap.parse_args()
    if args.icon_png:
        return icon_pngs(args.icon_png)
    m = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else None
    if args.restore:
        return restore(m)
    if args.verify:
        return verify(m)
    if m:
        print(f"already imported at rows {m['bases']} -- nothing to do (--restore first)")
        return

    sk = load("LIST_SKILL.STB")
    base = sk.rows
    for k, s in enumerate(SKILLS):
        s["base"] = base + k * RANKS
    cells = plan_cells()
    files = asset_files()
    new_files = [(d, f) for d, f in files if not os.path.isfile(ro.rel_path(DATA, f))]
    xmls = {s["xml"] for s in SKILLS}
    raw = {x: open(os.path.join(XML_DIR, x), encoding="utf-8", newline="").read() for x in xmls}
    want = {x: target_xml(x, raw[x]) for x in xmls}

    for s in SKILLS:
        print(f"{s['name']}: LIST_SKILL {s['base']}-{s['base'] + RANKS - 1}, class {s['cls']}, "
              f"level {s['level']}, after {s['prereq']}, book {s['book']} (tab {s['tab']} col {s['shop_col']})")
        print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'dur':>5}{'ratio':>7}{'range':>7}{'scope':>7}  rates")
        for n in range(RANKS):
            rates = "/".join(str(r[n]) for _, _, r in s["statuses"] if r)
            print(f"  {n + 1:>4}{s['power'][n]:>7}{s['reload'][n] * 0.2:>6.1f}{s['mp'][n]:>5}"
                  f"{s['duration'][n]:>5}{s['ratio'][n]:>7}{s['dist'][n]:>7}"
                  f"{s['scope'][n] if s['scope'] else '':>7}  {rates}")
    print(f"  {len(cells)} cells in place, {len(new_files)} files to copy, pages to draw: "
          f"{[p for p in {s['page'] for s in SKILLS} if not page_ok(p)]}")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    saved = {}
    for p in {s["page"] for s in SKILLS}:
        saved[p] = os.path.join(OUT, p)
        shutil.copyfile(res_path(p), saved[p])
    for x in xmls:
        saved[x] = os.path.join(OUT, x)
        shutil.copyfile(os.path.join(XML_DIR, x), saved[x])
    for d, f in new_files:
        dst = ro.rel_path(DATA, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(ro.rel_path(dump_root(d), f), dst)
    fix_ground_meshes()
    undo = [[t, r, c, load(t).d[r][c].hex(), v.hex()] for t, r, c, v in cells]
    for t, r, c, v in cells:
        load(t).d[r][c] = v
    sk.grow_to(base + RANKS * len(SKILLS))
    for s in SKILLS:
        for n, r in enumerate(skill_rows(s)):
            sk.d[s["base"] + n] = r
    for t in {x[0] for x in cells} | {"LIST_SKILL.STB"}:
        load(t).save(False, keep_backup=False)
    for name, key_fmt, num in (("LIST_SKILL_S.STL", "LSkill{}", "base"), ("LIST_USEITEM_S.STL", "LUSE{}", "book")):
        t = Stl(os.path.join(STB_DIR, name))
        for s in SKILLS:
            t.append(key_fmt.format(s[num]), s[num], s["name"], s["desc"])
        t.save(False, keep_backup=False)
    for p in {s["page"] for s in SKILLS}:
        if not page_ok(p):
            draw_page(p)
    for x in xmls:
        open(os.path.join(XML_DIR, x), "w", encoding="utf-8", newline="").write(want[x])
    json.dump(dict(bases=[s["base"] for s in SKILLS], cells=undo,
                   files=[f for _, f in new_files], saved=saved),
              open(MANIFEST, "w"), indent=1)
    rows = ", ".join(f"{s['name']} {s['base']}-{s['base'] + RANKS - 1}" for s in SKILLS)
    print(f"done ({rows}) -- now the icons (--icon-png, then add-skill-icon.py); restart the "
          f"server, re-bake, copy skilltree_howker.xml and skilltree_soldier.xml loose")


def restore(m):
    if not m:
        sys.exit("no manifest -- nothing to restore")
    sk = load("LIST_SKILL.STB")
    base, n = m["bases"][0], RANKS * len(SKILLS)
    tail = b"\x00\x00" * n
    if sk.rows != base + n or not sk.header.endswith(tail):
        sys.exit("rows were appended after this import -- refusing to truncate")
    sk.header, sk.d, sk.rows = sk.header[:-len(tail)], sk.d[:base], base
    if sk.rownames:
        del sk.rownames[-n:]
    for t, r, c, old, _ in m["cells"]:
        load(t).d[r][c] = bytes.fromhex(old)
    for t in {x[0] for x in m["cells"]} | {"LIST_SKILL.STB"}:
        load(t).save(False, keep_backup=False)
    keys = {"LIST_SKILL_S.STL": [f"LSkill{b}" for b in m["bases"]],
            "LIST_USEITEM_S.STL": [f"LUSE{s['book']}" for s in SKILLS]}
    for name, ks in keys.items():
        t = Stl(os.path.join(STB_DIR, name))
        t.remove(ks)
        t.save(False, keep_backup=False)
    for f in m["files"]:
        p = ro.rel_path(DATA, f)
        if os.path.isfile(p):
            os.remove(p)
    for name, src in m["saved"].items():
        dst = res_path(name) if name.upper().endswith(".DDS") else os.path.join(XML_DIR, name)
        shutil.copyfile(src, dst)
    os.remove(MANIFEST)
    print("restored: skill rows, books, shop, motion and effect rows, files, tree pages and XML")


def verify(m):
    if not m:
        sys.exit("not imported")
    ok = True
    sk = load("LIST_SKILL.STB")
    for s, base in zip(SKILLS, m["bases"]):
        s["base"] = base
        for n in range(RANKS):
            r = base + n
            if sk.d[r][0].decode("latin-1") != s["name"] or int(sk.d[r][2]) != n + 1:
                ok = False
                print(f"  row {r} is not {s['name']} rank {n + 1}")
        icon = int(sk.d[base][51] or b"0")
        if icon != (ICONS[s["key"]] or PLACEHOLDER_ICON):
            print(f"  note: {s['name']} icon is {icon} -- record it in ICONS")
    for t, r, c, _, new in m["cells"]:
        if load(t).d[r][c] != bytes.fromhex(new):
            ok = False
            print(f"  {t} {r}/{c} differs")
    for _, f in asset_files():
        if not os.path.isfile(ro.rel_path(DATA, f)):
            ok = False
            print(f"  missing {f}")
    if not ground_meshes_ok():
        ok = False
        print("  Star Gazer's ground mesh still depth-tests")
    for name, key in [("LIST_SKILL_S.STL", f"LSkill{b}") for b in m["bases"]] + \
                     [("LIST_USEITEM_S.STL", f"LUSE{s['book']}") for s in SKILLS]:
        if not Stl(os.path.join(STB_DIR, name)).has(key):
            ok = False
            print(f"  {name} lacks {key}")
    for x in {s["xml"] for s in SKILLS}:
        raw = open(os.path.join(XML_DIR, x), encoding="utf-8", newline="").read()
        if target_xml(x, raw) != raw:
            ok = False
            print(f"  {x} lacks the nodes")
    for p in {s["page"] for s in SKILLS}:
        if not page_ok(p):
            ok = False
            print(f"  {p} lacks the boxes")
    print("verify:", "ok" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
