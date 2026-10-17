"""The Raider's two signature skills from Jrose: Eruption (katar) and Shun'ei-zan (dual).

    python scripts/import-raider-skills.py --dry-run
    python scripts/import-raider-skills.py
    python scripts/import-raider-skills.py --verify
    python scripts/import-raider-skills.py --restore

then the icons (that tool owns the atlas; the PNGs are cut by --icon-png):

    python scripts/import-raider-skills.py --icon-png build/raider-skills
    python scripts/add-skill-icon.py build/raider-skills/eruption.png --name eruption --skill-row <first>-<last>
    python scripts/add-skill-icon.py build/raider-skills/shuneizan.png --name shuneizan --skill-row <first>-<last>

Why
---
The class identity pass (2026-10-18): the Raider had one exclusive attack per weapon
(Power Burst on the katar, Prime Hit on dual blades) and no look of its own. The only new
Raider animations in any dump are two Jrose Raider skills, one per weapon -- the same
per-weapon signature the Champion got. Both were picked in game from GM test rows
(`raider-anim-test.py`, since removed).

* **Eruption** (Jrose 4321, katar): the stock melee wind-up, then `hawker_u_skill_katar03`
  (2.3 s, new), a flurry of slashes. Ours is the katar's **area strike**: type 17, every
  enemy within 4.5 -> 6 m of you. The katar skill critical (`Is_KatarSkillCRITICAL`) rolls
  per target, so a pack lights up with critical digits.
* **Shun'ei-zan** (Jrose 4311, dual): its own three-part set, all new --
  `hawker_u_skill_dsw01` (cast) / `dsw02` (loop) / `dsw03` (strike) -- with Jrose's cast
  circle `hawker_skill_circle01` (FILE_EFFECT 53, new). The dual blades' **signature
  strike with a critical burst**: one target, and it rolls its own critical (LIST_SKILL
  cols 49/50, `SKILL_CRITICAL_ROLL` / `SKILL_CRITICAL_RATE`, server
  `CCal::Get_SkillDAMAGE`, added for this skill) under 30 instead of a swing's 20, for
  double damage. A dual Raider crits ~40-50% of its swings; under 30 it is ~80% at level
  100 and every hit from 130 on (auto-builds), so the stat still matters early.

  `dsw03` ends in ~1 s of stillness (frames 61-90 move under half a degree per frame),
  which read in game as the character stuck in place: our copy is cut to its first 61
  frames (`rosefmt.zmo.truncated`; its events sit at frames 8-10).

Jrose fills its motion rows only in the weapon's column (dual 7, katar 16); they go in
cell for cell at Jrose's numbers, blank here -- TYPE_MOTION 241-243 and 246, FILE_MOTION
578-580 and 583, FILE_EFFECT 53 -- with Jrose's "0" TYPE_MOTION cells left blank. The hit
effects are ours (Jrose's FILE_EFFECT 44 is blank there too): Power Burst's on Eruption,
Prime Hit's on Shun'ei-zan.

The numbers (ranks 1 -> 10, linear)
-----------------------------------
    Eruption     power 300 -> 750    cd 12 -> 9 s    MP 55 -> 120    area 4.5 -> 6 m
                 Raider, katar, level 100, Power Burst rank 5
    Shun'ei-zan  power 250 -> 600    cd 15 -> 12 s   MP 70 -> 150    crit roll 30, x2
                 Raider, dual, level 120, Prime Hit rank 5

Sized in the combat sim (`scripts/combatsim` mirrors the critical burst), auto-builds,
typical play, DPS change against no new skill, plain / star monsters:

    level            100          130          160          200
    Eruption       -13 / -11    +7 / -5     +24 / +12    +13 / +12    (katar)
    Shun'ei-zan     0 / 0      +15 / +16    +34 / +69    +10 / +31    (dual)

Plain fights last ~4 s, so a skill counts mostly as an opener, and the steps follow
one-shot thresholds (160 is the jumpy level). Level 100's dip is the auto-build buying
Power Burst rank 5 to unlock Eruption -- the price of the prerequisite, as with Exceed
Break. Shun'ei-zan's rank 10 is Prime Hit's per cast once doubled (600 x2 vs 1150);
the first cut, 450 -> 1100, doubled it and added +75-135%. The sim is one-on-one, so
Eruption's area is not in its numbers: alone it is a modest single-target skill.

How a player gets them
----------------------
* Books LIST_USEITEM 857 / 858 (blank; copies of Power Burst's 767 / Prime Hit's 765),
  in Darren's Hawker tab 466 cols 8 / 9, beside Power Burst's and Prime Hit's.
* Trees: UI2 builds itself from the class set and prerequisites. The classic tree (Blow
  Mastery page, `HOWKER_BLOW_MASTERY.DDS`, art grid `doc/skill-tree-art.md`): Eruption's
  box right of Power Burst's, Shun'ei-zan's under Prime Hit's (the page is 512 wide and
  Prime Hit already sits in the last column), and their nodes in `skilltree_howker.xml`.
* Icons: Jrose's own (sprites 856 and 882, with Jrose's "U" badge -- kept, 2026-10-18),
  appended by `add-skill-icon.py`; ICONS records the indices so a re-import keeps them.

What it changes
---------------
    LIST_SKILL.STB / _S.STL     20 rows appended (10 + 10), 2 keys
    LIST_USEITEM.STB / _S.STL   rows 857, 858;   LIST_SELL.STB tab 466 cols 8, 9
    TYPE_MOTION / FILE_MOTION   rows 241-243, 246 / 578-580, 583;   FILE_EFFECT row 53
    MOTION/AVATAR, EFFECT ...   4 clips (dsw03 cut), the circle effect (4 files)
    HOWKER_BLOW_MASTERY.DDS, skilltree_howker.xml (xml/ -- the folder the client reads)

Cell-level undo, the copied files and the page/XML as they were: `build/raider-skills/`.
Deploy: restart the server (LIST_SKILL, motion tables; the critical burst needs the new
sho_gameserver), re-bake, copy `skilltree_howker.xml` loose into the launch folder.
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
from rosefmt import zmo  # noqa: E402
import rosedata as ro  # noqa: E402

_spec = importlib.util.spec_from_file_location("rd", os.path.join(HERE, "rose-data-reader.py"))
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
RES_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "RES")
TREE_XML = os.path.join(DATA, "3DDATA", "CONTROL", "xml", "skilltree_howker.xml")
PAGE = "HOWKER_BLOW_MASTERY.DDS"
JROSE = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
J_STB = os.path.join(JROSE, "3Ddata", "STB")
OUT = os.path.join(ROOT, "build", "raider-skills")
MANIFEST = os.path.join(OUT, "manifest.json")

TYPE_ROWS = [241, 242, 243, 246]        # Shun'ei-zan cast/loop/strike, Eruption strike
FILE_ROWS = [578, 579, 580, 583]
FX_ROWS = [53]                          # hawker_skill_circle01.eft
CUT = {"hawker_u_skill_dsw03.ZMO": 61}  # clip -> frames kept

RANKS = 10
AT_MP, AT_LEVEL = 17, 31
CLASS_RAIDER = 65
KATAR, DUAL = 251, 252


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


SKILLS = [
    dict(key="eruption", name="Eruption", jrose=4321, jicon=856, book=857, book_template=767,
         shop_col=8, level=100, prereq=(1511, 5),
         desc=("Your katars blur into a storm of slashes that tears through every enemy "
               "around you. Each cut can land as a critical hit."),
         power=lin(300, 750), reload=lin(60, 45), mp=lin(55, 120), sp=lin(35, 130),
         scope=lin(450, 600),
         cols={5: 17, 15: 1, 29: 2, 30: KATAR,
               # stock melee wind-up at Jrose's x2, the flurry; Power Burst's hit
               52: 111, 53: 200, 54: 131, 56: 1359, 68: 246, 69: 100, 70: 1,
               74: 1040, 75: 999, 76: 67}),
    dict(key="shuneizan", name="Shun'ei-zan", jrose=4311, jicon=882, book=858, book_template=765,
         shop_col=9, level=120, prereq=(1611, 5),
         desc=("You vanish into a shadow that cuts through the target faster than the eye "
               "can follow. Shun'ei-zan lands as a critical hit almost every time, and "
               "its critical hits deal double damage."),
         power=lin(250, 600), reload=lin(75, 60), mp=lin(70, 150), sp=lin(40, 140),
         scope=None,
         cols={5: 3, 6: 1000, 15: 1, 29: 1, 30: DUAL,
               49: 30, 50: 200,       # SKILL_CRITICAL_ROLL / SKILL_CRITICAL_RATE
               # Jrose's own cast / loop / strike, its cast circle; Prime Hit's hit
               52: 241, 53: 100, 54: 242, 56: 53, 57: 999, 68: 243, 69: 100, 70: 1,
               74: 1666, 75: 999, 76: 137}),
]
ICONS = {"eruption": 523, "shuneizan": 524}     # from add-skill-icon.py (2026-10-18)
PLACEHOLDER_ICON = 512

SHOP_TAB = 466

# classic tree: art boxes (page pixels; icon = box + ART_ORIGIN + (1, 2))
ART_ORIGIN, BOX_SIZE, LINE = (20, 75), 42, (74, 81, 99, 255)
BOX_E = (398, 2)                # right of Power Burst (259,2)
BOX_S = (398, 164)              # under Prime Hit (398,110)
PAGE_LINES = [((300, 23), (BOX_E[0], 23)),                         # Power Burst -> Eruption
              ((419, 151), (419, BOX_S[1]))]                        # Prime Hit -> Shun'ei-zan


def icon_at(box):
    return box[0] + ART_ORIGIN[0] + 1, box[1] + ART_ORIGIN[1] + 2


tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def jload(name):
    return rd.Stb(os.path.join(J_STB, name), "cp932")


def plan_cells():
    out = []
    for table, rows in (("TYPE_MOTION.STB", TYPE_ROWS), ("FILE_MOTION.STB", FILE_ROWS),
                        ("FILE_EFFECT.STB", FX_ROWS)):
        ours, theirs = load(table), jload(table)
        for r in rows:
            want = [theirs.d[r][c] if c < theirs.cols else b"" for c in range(ours.cols)]
            if table == "TYPE_MOTION.STB":
                want = [b"" if v == b"0" else v for v in want]
            if any(ours.d[r]) and ours.d[r] != want:
                sys.exit(f"{table} row {r} is in use here -- refusing")
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
        if sell.d[SHOP_TAB][s["shop_col"]].strip(b"0"):
            sys.exit(f"shop tab {SHOP_TAB} col {s['shop_col']} holds {sell.d[SHOP_TAB][s['shop_col']]!r}")
        over = {0: s["name"].encode(), 20: str(s["base"]).encode(), 27: f"LUSE{book}".encode()}
        out += [("LIST_USEITEM.STB", book, c, over.get(c, ui.d[s["book_template"]][c]))
                for c in range(ui.cols)]
        out.append(("LIST_SELL.STB", SHOP_TAB, s["shop_col"], code))
    return [(t, r, c, v) for t, r, c, v in out if load(t).d[r][c] != v]


def asset_files():
    jfm, jfe = jload("FILE_MOTION.STB"), jload("FILE_EFFECT.STB")
    files = [jfm.s(r, 0).strip().replace("\\", "/") for r in FILE_ROWS]
    efts = [jfe.s(r, 1).strip().replace("\\", "/") for r in FX_ROWS]
    files += sorted(ro.effect_chain(efts, JROSE))
    uniq = {}
    for f in files:
        uniq.setdefault(ro.norm(f).replace("//", "/"), f.replace("\\\\", "\\").replace("//", "/"))
    return sorted(uniq.values())


def clip_path(clip):
    d = os.path.join(DATA, "3DDATA", "MOTION", "AVATAR")
    names = {f.lower(): f for f in os.listdir(d)}
    return os.path.join(d, names.get(clip.lower(), clip))


def trim_clips():
    """Cut the clips in CUT to their frame count (idempotent)."""
    for clip, keep in CUT.items():
        p = clip_path(clip)
        raw = open(p, "rb").read()
        if zmo.read_header(raw)[1] > keep:
            open(p, "wb").write(zmo.truncated(raw, keep))
            print(f"  {clip}: cut to {keep} frames")


def skill_rows(s):
    rows = []
    icon = ICONS[s["key"]] or PLACEHOLDER_ICON
    for n in range(RANKS):
        c = {0: s["name"], 1: s["base"], 2: n + 1, 3: s["sp"][n],
             4: 1,                  # SKILL_TAB_TYPE: the attack tab (blank = Basic)
             7: 5, 9: s["power"][n], 10: 1,
             16: AT_MP, 17: s["mp"][n], 20: s["reload"][n], 51: icon,
             86: f"LSkill{s['base']}"}
        c.update(s["cols"])
        if s["scope"]:
            c[8] = s["scope"][n]
        if n == 0:
            c.update({35: CLASS_RAIDER, 39: s["prereq"][0], 40: s["prereq"][1],
                      45: AT_LEVEL, 46: s["level"]})
        rows.append([str(c.get(i, "")).encode("latin-1") for i in range(87)])
    return rows


# --- the classic tree ---------------------------------------------------------------

def page_path():
    hit = [f for f in os.listdir(RES_DIR) if f.upper() == PAGE]
    if not hit:
        sys.exit(f"tree art {PAGE} not found")
    return os.path.join(RES_DIR, hit[0])


def page_ok(path):
    from PIL import Image
    px = Image.open(path).convert("RGBA").load()
    return all(px[x, y][3] > 8 for x, y in (BOX_E, BOX_S))


def draw_page(path):
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGBA")
    px = im.load()
    for bx, by in (BOX_E, BOX_S):
        if any(px[x, y][3] for y in range(by, by + BOX_SIZE) for x in range(bx, bx + BOX_SIZE)):
            sys.exit(f"{PAGE}: the area at {bx},{by} is not empty -- refusing")
    d = ImageDraw.Draw(im)
    for a, b in PAGE_LINES:
        d.line([a, b], fill=LINE)
    for bx, by in (BOX_E, BOX_S):
        d.rectangle([bx, by, bx + BOX_SIZE - 1, by + BOX_SIZE - 1], outline=LINE)
    return im


def target_xml(raw, base_e, base_s):
    out = raw
    xe, ye = icon_at(BOX_E)
    xs, ys = icon_at(BOX_S)
    inserts = [('<SKILL INDEX="1511" OFFSETX="280" OFFSETY="79"/>',
                '<SKILL INDEX="1511" OFFSETX="280" OFFSETY="79">'
                f'\n            <SKILL INDEX="{base_e}" OFFSETX="{xe}" OFFSETY="{ye}"/>'
                '\n         </SKILL>'),
               ('<SKILL INDEX="1611" OFFSETX="419" OFFSETY="187"/>',
                '<SKILL INDEX="1611" OFFSETX="419" OFFSETY="187">'
                f'\n               <SKILL INDEX="{base_s}" OFFSETX="{xs}" OFFSETY="{ys}"/>'
                '\n            </SKILL>')]
    for anchor, node in inserts:
        if anchor in out:
            out = out.replace(anchor, node, 1)
        elif node not in out:
            sys.exit(f"tree: anchor not found ({anchor}) -- refusing")
    return out


def icon_pngs(out_dir):
    import numpy as np
    from PIL import Image
    spec = importlib.util.spec_from_file_location("usi", os.path.join(HERE, "upgrade-skill-icons.py"))
    usi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(usi)
    atlas = usi.Atlas(os.path.join(JROSE, "3Ddata"))
    os.makedirs(out_dir, exist_ok=True)
    for s in SKILLS:
        cell = atlas.cell(s["jicon"])
        if cell is None or usi.is_blank(cell):
            sys.exit(f"Jrose sprite {s['jicon']} is blank or missing")
        p = os.path.join(out_dir, s["key"] + ".png")
        Image.fromarray(np.clip(cell, 0, 255).astype(np.uint8), "RGB").save(p)
        print(f"wrote {p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--icon-png", metavar="DIR", help="write Jrose's two icons as 40x40 PNGs and stop")
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
    new_files = [f for f in files if not os.path.isfile(ro.rel_path(DATA, f))]
    raw_xml = open(TREE_XML, encoding="utf-8", newline="").read()
    want_xml = target_xml(raw_xml, SKILLS[0]["base"], SKILLS[1]["base"])

    for s in SKILLS:
        print(f"{s['name']}: LIST_SKILL {s['base']}-{s['base'] + RANKS - 1}, book {s['book']}, "
              f"tab {SHOP_TAB} col {s['shop_col']}, level {s['level']}, after {s['prereq']}")
        print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'SP':>5}{'scope':>7}")
        for n in range(RANKS):
            print(f"  {n + 1:>4}{s['power'][n]:>7}{s['reload'][n] * 0.2:>6.1f}{s['mp'][n]:>5}"
                  f"{s['sp'][n]:>5}{s['scope'][n] if s['scope'] else '':>7}")
    print(f"  {len(cells)} cells in place, {len(new_files)} files to copy, tree page "
          f"{'already drawn' if page_ok(page_path()) else 'to draw'}")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    saved_page = os.path.join(OUT, PAGE)
    saved_xml = os.path.join(OUT, "skilltree_howker.xml")
    shutil.copyfile(page_path(), saved_page)
    shutil.copyfile(TREE_XML, saved_xml)
    for f in new_files:
        d = ro.rel_path(DATA, f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(ro.rel_path(JROSE, f), d)
    trim_clips()
    undo = [[t, r, c, load(t).d[r][c].hex(), v.hex()] for t, r, c, v in cells]
    for t, r, c, v in cells:
        load(t).d[r][c] = v
    sk.grow_to(base + RANKS * len(SKILLS))
    for s in SKILLS:
        for n, r in enumerate(skill_rows(s)):
            sk.d[s["base"] + n] = r
    for t in {x[0] for x in cells} | {"LIST_SKILL.STB"}:
        load(t).save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL"))
    for s in SKILLS:
        t.append(f"LSkill{s['base']}", s["base"], s["name"], s["desc"])
    t.save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_USEITEM_S.STL"))
    for s in SKILLS:
        t.append(f"LUSE{s['book']}", s["book"], s["name"], s["desc"])
    t.save(False, keep_backup=False)
    if not page_ok(page_path()):
        draw_page(page_path()).save(page_path())
    open(TREE_XML, "w", encoding="utf-8", newline="").write(want_xml)
    json.dump(dict(bases=[s["base"] for s in SKILLS], cells=undo, files=new_files,
                   page=saved_page, xml=saved_xml), open(MANIFEST, "w"), indent=1)
    rows = " / ".join(f"{s['base']}-{s['base'] + RANKS - 1}" for s in SKILLS)
    print(f"done ({rows}) -- now the icons (--icon-png, then add-skill-icon.py); restart the "
          f"server, re-bake, copy skilltree_howker.xml loose")


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
    shutil.copyfile(m["page"], page_path())
    shutil.copyfile(m["xml"], TREE_XML)
    os.remove(MANIFEST)
    print("restored: skill rows, books, shop, motion and effect rows, files, tree page and XML")


def verify(m):
    if not m:
        sys.exit("not imported")
    ok = True
    sk = load("LIST_SKILL.STB")
    for s, base in zip(SKILLS, m["bases"]):
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
    for f in asset_files():
        if not os.path.isfile(ro.rel_path(DATA, f)):
            ok = False
            print(f"  missing {f}")
    for clip, keep in CUT.items():
        if zmo.read_header(open(clip_path(clip), "rb").read())[1] != keep:
            ok = False
            print(f"  {clip} is not cut to {keep} frames")
    for name, key in [("LIST_SKILL_S.STL", f"LSkill{b}") for b in m["bases"]] + \
                     [("LIST_USEITEM_S.STL", f"LUSE{s['book']}") for s in SKILLS]:
        if not Stl(os.path.join(STB_DIR, name)).has(key):
            ok = False
            print(f"  {name} lacks {key}")
    raw = open(TREE_XML, encoding="utf-8", newline="").read()
    if target_xml(raw, *m["bases"]) != raw:
        ok = False
        print("  skilltree_howker.xml lacks the nodes")
    if not page_ok(page_path()):
        ok = False
        print(f"  {PAGE} lacks the boxes")
    print("verify:", "ok" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
