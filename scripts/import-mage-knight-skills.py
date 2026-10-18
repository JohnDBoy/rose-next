"""Two Mage spells and two melee-Knight skills: Diabolos' Curse, Shadow Servant, Shield Bash, Gaia Presser.

    python scripts/import-mage-knight-skills.py --dry-run
    python scripts/import-mage-knight-skills.py
    python scripts/import-mage-knight-skills.py --verify
    python scripts/import-mage-knight-skills.py --restore

then the icons (that tool owns the atlas; the PNGs are cut by --icon-png):

    python scripts/import-mage-knight-skills.py --icon-png build/mage-knight-skills
    python scripts/add-skill-icon.py build/mage-knight-skills/<key>.png --name <key> --skill-row <first>-<last>

Why
---
The class identity pass after the Scout and crossbow Knight (2026-10-18). The user picked
the four from the dump survey (`doc/skill-candidates.md`) and approved their looks in game
from GM test rows (`mage-knight-anim-test.py`, since removed):

* **Diabolos' Curse** (Jrose 4251) -- the Mage's curse bolt, the only Mage candidate with
  its own animation (`skill_magic_abnormality_m01/03/02`: cast, hold, release) and a
  demonic pentagram and fire bolt. It **strips the target's buffs** (LIST_STATUS 37,
  ING_CLEAR_GOOD -- only monster skills dispelled before) and **slows** it: the Mage's
  answer to a boss that buffs itself. Follows Silence.
* **Shadow Servant** (Jrose 6061) -- the Mage's capstone nuke: dark crosses rise on the
  target's spot (type 7, like Luna Stone), lowering **Magic Resistance** (the Mage's own
  follow-up spells hit harder) and **Accuracy** (Jrose also lowered Defense; a skill holds
  two statuses). Follows Luna Stone.
* **Shield Bash** (667 575) -- the sword-and-board Knight's own skill, on the shield-bash
  clip `s_shielda_m1` that we shipped and nothing played. It **requires a shield** (col 30
  = 261 matches the off-hand) and **hits with it**: the server adds 2% damage per point of
  the shield's own Defense, refine included, capped at +250% (`calculation.cpp`
  Is_ShieldSKILL, added for it). It batters the enemy's weapon arm -- **Attack Power** and
  **Attack Speed** down -- the Knight's self-sufficiency; Lightning Crasher owns the stun.
  Follows Shield Barrier.
* **Gaia Presser** (Jrose 6031) -- the stock spin attack with Jrose's swirl, every enemy
  around you: **Defense** and **Movement Speed** down (Jrose also raised your own Attack
  Power; a damage skill's statuses land on its targets). One-handed sword **or mace**:
  the spin clip is in every weapon column, Jrose's mace-only was data (the user's call).
  Follows Impact Wave.

Each status rolls on its own (chance = ratio x (level x 2 + INT + 20) / (RES x 0.6 + 5 +
Dodge)) and both share one duration (col 14): with ~300 INT, Mage ratio 45 -> 65 lands
about 55-75%; with ~15 INT, Knight ratio 70 -> 110 lands 50-70%.

Presentation, as tested
-----------------------
* Diabolos' Curse's clips go in at Jrose's TYPE_MOTION 225-227 / FILE_MOTION 563-565, its
  effects at FILE_EFFECT 20-22 / LIST_EFFECT 310. **Its pentagram is patched**: a flat mesh
  at the caster's feet drawn with the depth test on -- what made Star Gazer's star z-fight
  the terrain -- so ours draws without it (`rosefmt.eft.with_mesh_flags`, z_test 0).
* Shadow Servant's crosses: FILE_EFFECT 2543 / LIST_EFFECT 327. They stand up out of the
  ground and keep their depth test.
* Gaia Presser's swirl (FILE_EFFECT 1616) sits in casting-effect slot 2 (col 62) and its
  wind-up in slot 1 (col 59), as Spin Attack's do. Slots fire on frame events
  (`ActionSkillCastingFrame`: slot 0 on 44, 1 on 64, 2 on 74); Jrose's slots 0/1 never
  fired here, and the first test showed a bare spin.

The numbers (ranks 1 -> 10, linear; the full table with --dry-run)
-----------------------------------------------------------------
    Diabolos' Curse   power 400 -> 900   cd 20 -> 15 s  MP 90 -> 170   dispel + slow 30 -> 45%
    Shadow Servant    power 500 -> 1200  cd 25 -> 20 s  MP 150 -> 280  7 -> 9 m, Magic Resistance
                                                                       and Accuracy down 15 -> 25%
    Shield Bash       power 200 -> 520   cd 12 ->  9 s  MP 40 -> 90    + 2%/shield DEF, Attack Power
                                                                       and Attack Speed down 15 -> 25%
    Gaia Presser      power 350 -> 800   cd 14 -> 11 s  MP 70 -> 140   5 -> 7 m, Defense down
                                                                       15 -> 25%, slow 30 -> 45%

Combat sim, average gear, the new skills forced into the rotation (`scripts/CLAUDE.md`),
star monsters, per cast at level 200: Shadow Servant ~1.0x Luna Stone (it was 1.17-1.3x
at 600 -> 1400), Diabolos' Curse 0.63x (a utility bolt), Gaia Presser ~1.0x Impact Wave
(plus its debuffs). Shield Bash by the shield's own Defense, against Impact Wave (3675):

    shield DEF    25 (weak)    70 (strong)    205 (lv 240, +9)
    level 200     4522 1.2x    7236 2.0x      9999 (the damage cap)
    level 130     1788 1.0x    2860 1.5x      (rank 6)

Melee Knight DPS against the auto-build without them: +6/+1/+20/+15% on stars at
100/130/160/200 (plain +20/+5/+20/+28%). The Mage's DPS barely moves and dips where the
forced rotation opens with Diabolos' Curse: the sim cannot value a dispel or a slow, and
the auto-build already leans on Luna Stone. Both area skills' reach is beyond a
one-on-one sim.

How a player gets them
----------------------
* Books LIST_USEITEM 863-866 (blank; copies of the Silence / Lunar Stone / Shield Barrier /
  Impact Wave books): Mage in Darren's Muse tab 464 cols 23 / 7 (beside Silence and Lunar
  Stone), Knight in his Soldier tab 462 cols 31 / 32.
* Trees: UI2 builds itself. Classic boxes on `MUSE_SPELLMASTERY.DDS` (Diabolos' Curse right
  of Silence), `MUSE_MAGICARMSMASTERY.DDS` (Shadow Servant under Luna Stone),
  `SOLDIER_HARDENBODY.DDS` (Shield Bash right of Shield Barrier's rank-6 box) and
  `SOLDIER_WEAPON_MASTERY.DDS` (Gaia Presser right of Impact Wave); nodes in
  `skilltree_muse.xml` / `skilltree_soldier.xml`.
* Icons: Jrose's for the three Jrose skills, 667's for Shield Bash; ICONS records them.

Cell-level undo, the copied files, the pages and XML as they were: `build/mage-knight-skills/`.
Deploy: the new `sho_gameserver` (the shield rule), restart, re-bake, copy both tree XMLs loose.
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
OUT = os.path.join(ROOT, "build", "mage-knight-skills")
MANIFEST = os.path.join(OUT, "manifest.json")

# rows copied cell for cell from a dump, at the dump's own number
COPY = [("jrose", "TYPE_MOTION.STB", [225, 226, 227]),
        ("jrose", "FILE_MOTION.STB", [563, 564, 565]),
        ("jrose", "FILE_EFFECT.STB", [20, 21, 22, 2543, 1616]),
        ("jrose", "LIST_EFFECT.STB", [310, 327])]
GROUND_MESH_FIX = {"3DDATA/EFFECT/muse_skill01_casting.eft": 1}   # file -> mesh index

RANKS = 10
AT_MP, AT_LEVEL = 17, 31
AT_ATK, AT_DEF, AT_HIT, AT_RES, AT_SPEED, AT_ATK_SPD = 18, 19, 20, 21, 23, 24
ST_SLOW, ST_ATK_SPD_DOWN, ST_ATK_DOWN, ST_DEF_DOWN, ST_RES_DOWN, ST_HIT_DOWN, ST_DISPEL = \
    15, 17, 19, 21, 23, 25, 37
CLASS_KNIGHT, CLASS_MAGE = 61, 63
STAFF, WAND, ONE_HAND, MACE, SHIELD = 241, 242, 211, 212, 261
LOOK_COLS = list(range(52, 85))   # motions, cast fx/sounds, action, bullet, hit fx and dummies


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


# statuses: [(LIST_STATUS row, ability, rate per rank or None)] -- slot 0 then slot 1
SKILLS = [
    dict(key="diabolos_curse", name="Diabolos' Curse", dump="jrose", src=4251, jicon=864,
         cls=CLASS_MAGE, level=110, prereq=(1071, 3), book=863, book_template=724,
         tab=464, shop_col=23, xml="skilltree_muse.xml", page="MUSE_SPELLMASTERY.DDS",
         box=(398, 207), line=((300, 228), (398, 228)),
         anchor=('<SKILL INDEX="1071" OFFSETX="280" OFFSETY="284"/>', 9),
         desc=("You draw a demon's seal in the air and hurl its fire at the target. The curse "
               "can strip away every blessing on it and slow it down."),
         power=lin(400, 900), reload=lin(100, 75), mp=lin(90, 170), sp=lin(40, 140),
         dist=lin(1800, 2200), scope=None, duration=lin(6, 10), ratio=lin(45, 65),
         statuses=[(ST_DISPEL, None, None), (ST_SLOW, AT_SPEED, lin(30, 45))],
         cols={5: 6, 15: 2, 29: 2, 30: STAFF, 31: WAND, 70: 1}),
    dict(key="shadow_servant", name="Shadow Servant", dump="jrose", src=6061, jicon=245,
         cls=CLASS_MAGE, level=140, prereq=(1091, 5), book=864, book_template=726,
         tab=464, shop_col=7, xml="skilltree_muse.xml", page="MUSE_MAGICARMSMASTERY.DDS",
         box=(398, 164), line=((419, 151), (419, 164)),
         anchor=('<SKILL INDEX="1091" OFFSETX="419" OFFSETY="187"/>', 12),
         desc=("You call the shadows up out of the ground where your target stands. Dark "
               "crosses tear through every enemy there and can weaken their Magic "
               "Resistance and Accuracy."),
         power=lin(500, 1200), reload=lin(125, 100), mp=lin(150, 280), sp=lin(45, 150),
         dist=lin(1850, 2200), scope=lin(700, 900), duration=lin(8, 12), ratio=lin(40, 60),
         statuses=[(ST_RES_DOWN, AT_RES, lin(15, 25)), (ST_HIT_DOWN, AT_HIT, lin(15, 25))],
         cols={5: 7, 15: 2, 29: 2, 30: STAFF, 31: WAND, 70: 1}),
    dict(key="shield_bash", name="Shield Bash", dump="667", src=575, jicon=85,
         cls=CLASS_KNIGHT, level=90, prereq=(381, 6), book=865, book_template=664,
         tab=462, shop_col=31, xml="skilltree_soldier.xml", page="SOLDIER_HARDENBODY.DDS",
         box=(439, 2), line=((341, 23), (439, 23)),
         anchor=('<SKILL INDEX="381" OFFSETX="321" OFFSETY="79" LEVEL="6"/>', 12),
         desc=("You drive your shield into the enemy three times. The heavier your shield, "
               "the harder it hits, and the battered target can lose Attack Power and "
               "Attack Speed. Requires a shield."),
         power=lin(200, 520), reload=lin(60, 45), mp=lin(40, 90), sp=lin(35, 130),
         dist=None, scope=None, duration=lin(6, 10), ratio=lin(80, 110),
         statuses=[(ST_ATK_DOWN, AT_ATK, lin(15, 25)), (ST_ATK_SPD_DOWN, AT_ATK_SPD, lin(15, 25))],
         cols={5: 3, 15: 1, 29: 1, 30: SHIELD}),
    dict(key="gaia_presser", name="Gaia Presser", dump="jrose", src=6031, jicon=258,
         cls=CLASS_KNIGHT, level=110, prereq=(511, 5), book=866, book_template=676,
         tab=462, shop_col=32, xml="skilltree_soldier.xml", page="SOLDIER_WEAPON_MASTERY.DDS",
         box=(398, 149), line=((300, 170), (398, 170)),
         anchor=('<SKILL INDEX="511" OFFSETX="280" OFFSETY="226"/>', 9),
         desc=("You spin with your weapon and slam the ground, and the earth crushes every "
               "enemy around you. They can lose Defense and Movement Speed."),
         power=lin(350, 800), reload=lin(70, 55), mp=lin(70, 140), sp=lin(40, 140),
         dist=None, scope=lin(500, 700), duration=lin(6, 10), ratio=lin(70, 100),
         statuses=[(ST_DEF_DOWN, AT_DEF, lin(15, 25)), (ST_SLOW, AT_SPEED, lin(30, 45))],
         # slot 0 (event 44) never fires on scope_casting01: wind-up in slot 1, swirl in slot 2
         cols={5: 17, 15: 1, 29: 2, 30: ONE_HAND, 31: MACE,
               56: None, 57: None, 58: None,
               59: 1607, 60: 999, 61: 142, 62: 1616, 63: 999, 64: 142}),
]
ICONS = {"diabolos_curse": 529, "shadow_servant": 530,   # from add-skill-icon.py (2026-10-18)
         "shield_bash": 531, "gaia_presser": 532}
PLACEHOLDER_ICON = 512

ART_ORIGIN, BOX_SIZE, LINE = (20, 75), 42, (74, 81, 99, 255)

tables = {}


def icon_at(box):
    return box[0] + ART_ORIGIN[0] + 1, box[1] + ART_ORIGIN[1] + 2


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


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
    for d in DUMPS:
        fm, fe = dload(d, "FILE_MOTION.STB"), dload(d, "FILE_EFFECT.STB")
        for dd, t, rows in COPY:
            if dd == d and t == "FILE_MOTION.STB":
                for r in rows:
                    f = fm.s(r, 0).strip().replace("\\", "/")
                    out[ro.norm(f)] = (d, f)
        efts = [fe.s(r, 1).strip().replace("\\", "/") for dd, t, rows in COPY
                if dd == d and t == "FILE_EFFECT.STB" for r in rows]
        for f in sorted(ro.effect_chain(efts, DUMPS[d][0])):
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
             7: 5, 9: s["power"][n], 10: 1,
             13: s["ratio"][n], 14: s["duration"][n],
             16: AT_MP, 17: s["mp"][n], 20: s["reload"][n],
             51: ICONS[s["key"]] or PLACEHOLDER_ICON, 86: f"LSkill{s['base']}"}
        c.update(look)
        c.update(s["cols"])
        if s["dist"]:
            c[6] = s["dist"][n]
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
        c = {k: v for k, v in c.items() if v is not None}
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
                  f"{s['duration'][n]:>5}{s['ratio'][n]:>7}{s['dist'][n] if s['dist'] else '':>7}"
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
        shutil.copyfile(ro.rel_path(DUMPS[d][0], f), dst)
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
    print(f"done ({rows}) -- now the icons (--icon-png, then add-skill-icon.py); deploy the new "
          f"sho_gameserver, restart, re-bake, copy skilltree_muse.xml and skilltree_soldier.xml loose")


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
        print("  Diabolos' Curse's pentagram still depth-tests")
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
