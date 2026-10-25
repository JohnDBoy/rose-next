"""Skyrend: the Raider's level-150 dual-sword skill, a flurry that ends in an aerial slam.

    python scripts/import-skyrend.py --dry-run
    python scripts/import-skyrend.py
    python scripts/import-skyrend.py --verify
    python scripts/import-skyrend.py --restore

Deploy: restart the game server (it reads LIST_SKILL, LIST_USEITEM, LIST_SELL, the
motion tables and the clips), re-bake, and copy `skilltree_howker.xml` loose into the
launch folder's 3DDATA/CONTROL/XML (read with fopen, never from the VFS).

Why
---
2026-10-25, an experiment the user asked for after Earthsplitter (`import-earthsplitter.py`):
push SlopStudio's `rose-anim-toolkit` (the SlopRose repo,
`C:\\Users\\Thomas\\Desktop\\Rose\\sloprose`) further -- a Raider dual-weapon skill with an
elaborate choreography, a flurry of blows ending in an aerial strike, with lots of
particles. Tested in game as a GM row (`add-skyrend-test.py`, now this script); the user
found it fun and made it real: **a level-150 skill gated on Battle Mastery** "for a
change" (every other Raider skill hangs off an active one), since we have almost no
level-150 actives (Shadow Servant at 140 was the highest). Icon by the user.

The sources in `build/skyrend/src/` were made in that session's scratchpad (`kit2/`, the
toolkit refreshed to its 2026-10-24 aerial commits, with our two patches -- loose `data/`
reader, cap dummy 65535 -- and a third: charge_fx's texture loader read its author's own
game folder); the two builders are kept beside them:

* `skyrend.py`, on aerial.py's `Aerial` class (the dual-sword aerial chain's builder):
  - `SKYREND_CAST_M1` (15 f): the swords rise crossed overhead (TWOHAND_ATTACK03's
    raise), event 44 at f9 as they cross.
  - `SKYREND_HOLD_M1` (10 f): that pose trembling at 9 Hz, three whole cycles.
  - `SKYREND_ACTION_M1` (114 f, 3.8 s): six ground blows about a fifth of a second
    apart (TWOHAND_ATTACK01's diagonal, ATTACK02's sweep, 3ATTACK's three cuts,
    KARTAR_2ATTACK's thrust); KARTAR_3ATTACK's coil and rising spin up to the hover
    height (250 cm, baked into the clip -- the server tracks no height); a sweep and a
    thrust in the air; ATTACK03's crossed raise and spin into ATTACK01's chop, falling
    onto the ground; a crouched landing with a tremor and the rise into TWOHAND_STOP1.
* `skyrend_fx.py`, on blink_fx's helpers (real seconds, finite emitters): seven
  crimson-and-violet particle effects (`fx/`), listed under "Effects" below.

How the client plays it (rose-next, `ActionImmediateSkill`, type 3)
-------------------------------------------------------------------
* Events 10 / 20 alternate on the nine blows before the slam: each plays the skill's
  hit-dummy effect and sound on the target -- cols 77-79 (SLASH_A, a crimson "/",
  Sword_H01) and 80-82 (SLASH_B, a violet "\", Sword_H02). 25 on the landing is the
  hit: the damage digit, col 74 (FINAL, a big X) and col 76 (`point_heavy01`).
* Casting effects: 44 in the cast (slot 0, GATHER, at the feet); in the action 64 at the
  takeoff (slot 1, LAUNCH, at the feet), 74 at the top of the rise (slot 2, APEX, on
  **dummy 3, the back**, so it is up in the air with the character -- the model root
  stays on the ground), 84 a frame before the landing (slot 3, IMPACT, at the feet).
  The client links them to the caster (type 3), so they follow it.
* Slashes are `_WIND_02` streaks turned by a rotation key; sprites are billboards, so a
  slash keeps its angle on screen from any side.

The numbers (ranks 1 -> 10, linear)
-----------------------------------
    power 5 -> 20 per blow    cd 20 -> 16 s    MP 120 -> 190    distance 2 m
    Raider (class 65), dual swords (252), level 150, Battle Mastery (1461) rank 15

**The server multiplies a skill's damage by its clip's attack frames** (10, 20-28) --
ten here -- and the Attack Power term rides along on every one, so a blow is worth
about a strong auto-attack whatever the power: in the combat sim (RaiderSky, Raider 150
with Demise Dual Weapon +4, vs Hellhound 2684, level 150, 6750 HP) power 10 gives 6064
per cast and each point adds ~26. Power only tunes a narrow band, so the cooldown and MP
carry the balance (the user's "cooldown/MP before power"): ~5900 -> ~6330 per cast,
40-50% over Shun'ei-zan rank 10 (4323) and Prime Hit (3620), and level with them per
second of cooldown -- before the 4.3 s it holds the Raider still, ~4 auto-attacks it
does not swing. Rank 10 stays under a plain level-150 monster's HP: at power 30 the
crits one-shot some Hellhounds (p10 time to kill 0.5 s), the rejected Final Strike case.
Skill points per rank copy Shun'ei-zan's.

How a player gets it
--------------------
* **Book**: LIST_USEITEM 867 (blank, after the import books 857-866; a copy of
  Shun'ei-zan's 858), sold in Darren's "Hawker" tab (LIST_SELL 466) at col 25, under
  Shun'ei-zan's book (col 9), two rows down.
* **Gates** on rank 1: class set 65, Battle Mastery (1461) rank 15, `AT_LEVEL` 150.
* **Trees**: UI2's builds itself from the class set and prerequisite. The classic tree:
  Battle Mastery is the base of the HOWKER_COMBAT_MASTERY.DDS page, whose skills hang
  off its left spine (art x 74, branches every 55 px at y 130 / 185 / 239). Skyrend is
  a fourth branch: the spine extended to y 294, a stub across, a 42x42 box at art
  (174, 273) -- the icon at dialog (195, 350), the column of the branches above it.
* **Icon** 534 (skill04.dds cell 27): the user's art, cropped to its frame and added by
  `add-skill-icon.py build/skyrend/icon.png --name skyrend`; written into col 51 here
  so a re-import keeps it.

Effects (FILE_EFFECT rows filled in the first blank rows after the last used)
------------------------------------------------------------------------------
    SKYREND_GATHER   violet aura, crimson glow where the swords cross, sparkles rising
    SKYREND_SLASH_A  crimson "/" streak, white flash, sparks
    SKYREND_SLASH_B  violet "\" streak, lilac flash, sparks
    SKYREND_LAUNCH   dust thrown out, violet ring, column of light, sparks shooting up
    SKYREND_APEX     two streaks spinning a ring, violet aura, crimson halo, sparks
    SKYREND_IMPACT   white flash, crimson glow, two shock rings, ray burst, 46 sparks,
                     dust, embers drifting up
    SKYREND_FINAL    big crossed crimson/violet X, flash, sparks

What it changes
---------------
    LIST_SKILL.STB / _S.STL      10 rows appended, 1 key
    FILE_MOTION / TYPE_MOTION    3 rows appended each (cast, hold, action)
    FILE_EFFECT.STB              7 blank rows filled
    LIST_USEITEM.STB / _S.STL    row 867, key LUSE867
    LIST_SELL.STB                tab 466 col 25
    MOTION/AVATAR                SKYREND_CAST/_HOLD/_ACTION_M1.ZMO
    EFFECT, PARTICLES            SKYREND_*.EFT / .PTL (7 + 7)
    skilltree_howker.xml         1 node; HOWKER_COMBAT_MASTERY.DDS painted

`--restore` truncates the appended rows (only while they are still last), puts every
other cell back, removes the keys, files and node, and restores the page from
`build/skyrend/` (never under data/: pack.rs would bake a backup).
`scripts/fix-skill-book-names.py` will list book 867 as a newcomer; its name matches.
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt.stb import Stb  # noqa: E402
from rosefmt.stl import Stl  # noqa: E402
from rosefmt.binio import write_pstr16  # noqa: E402
from rosefmt import eft, ptl, zmo  # noqa: E402

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
RES_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "RES")
TREE_XML = os.path.join(DATA, "3DDATA", "CONTROL", "xml", "skilltree_howker.xml")
OUT = os.path.join(ROOT, "build", "skyrend")
SRC = os.path.join(OUT, "src")
MANIFEST = os.path.join(OUT, "manifest-skill.json")

NAME = "Skyrend"
DESC = ("Cut into your target in a storm of six blows, spring into the air with a rising "
        "spin, strike twice from above, then dive and come down on it with both blades. "
        "Ten hits in all.")
RANKS = 10
CLASS_RAIDER, WEAPON_DUAL, LEVEL = 65, 252, 150
PREREQ = (1461, 15)               # Battle Mastery rank 15
AT_MP, AT_LEVEL = 17, 31
ICON = 534
SP_FROM = 7087                    # Shun'ei-zan's skill points per rank
DISTANCE = 200


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


POWER = lin(5, 20)                # per blow: the server multiplies by the clip's ten attack frames
RELOAD = lin(100, 80)             # x0.2 s -> 20 -> 16 s
MP = lin(120, 190)

HIT_SOUND, SOUND_A, SOUND_B = 1551, 43, 44   # point_heavy01, Sword_H01, Sword_H02
APEX_POINT = 3                   # dummy p_03, the back: rides up with the character

BOOK, BOOK_TEMPLATE = 867, 858
SHOP_TAB, SHOP_COL = 466, 25

TREE_PAGE = "HOWKER_COMBAT_MASTERY.DDS"
TREE_ANCHOR = '<SKILL INDEX="1861" OFFSETX="419" OFFSETY="403"/>\n      </SKILL>'
SPINE_X, SPINE_END, STUB_Y = 74, 239, 294
BOX = (174, 273)
ART_ORIGIN, ART_LINE_RGBA, ART_BOX_SIZE = (20, 75), (74, 81, 99, 255), 42

AVATAR = "3DDATA\\MOTION\\AVATAR\\"
CLIPS = [("SKYREND_CAST_M1.ZMO", "skyrend cast"), ("SKYREND_HOLD_M1.ZMO", "skyrend hold"),
         ("SKYREND_ACTION_M1.ZMO", "skyrend action")]
FX = ["GATHER", "SLASH_A", "SLASH_B", "LAUNCH", "APEX", "IMPACT", "FINAL"]
EFFECT = "3DDATA\\EFFECT\\"
PARTICLES = "3DDATA\\EFFECT\\PARTICLES\\"

tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def save(name):
    load(name).save(False, keep_backup=False)


def data_path(rel):
    return os.path.join(DATA, *rel.split("\\"))


def last_used(t):
    return max(r for r in range(t.rows) if any(t.d[r]))


# --- files ---------------------------------------------------------------------------

def files():
    """{data-relative path: bytes}, each checked with our codecs."""
    out = {}
    for name, _ in CLIPS:
        blob = open(os.path.join(SRC, name), "rb").read()
        if not zmo.read_header(blob):
            sys.exit(f"{name} is not a ZMO -- refusing")
        out[AVATAR + name] = blob
    action = zmo.events(out[AVATAR + "SKYREND_ACTION_M1.ZMO"])[1]
    hits = [e for e in action if e in (10, 20, 25)]
    if hits.count(25) != 1 or len(hits) != 10:
        sys.exit(f"the action clip's hits are {hits}, not nine dummies and one 25 -- rebuild it")
    for fx in FX:
        e_blob = open(os.path.join(SRC, "fx", "3DDATA", "EFFECT", f"SKYREND_{fx}.EFT"), "rb").read()
        p_blob = open(os.path.join(SRC, "fx", "3DDATA", "EFFECT", "PARTICLES", f"SKYREND_{fx}.PTL"), "rb").read()
        e = eft.read(e_blob)
        if [q["ptl"].upper() for q in e["particles"]] != [f"{PARTICLES}SKYREND_{fx}.PTL"]:
            sys.exit(f"SKYREND_{fx}.EFT names {[q['ptl'] for q in e['particles']]} -- refusing")
        ptl.parse(p_blob)
        out[f"{EFFECT}SKYREND_{fx}.EFT"] = e_blob
        out[f"{PARTICLES}SKYREND_{fx}.PTL"] = p_blob
    return out


# --- tables --------------------------------------------------------------------------

class Cells:
    """In-place cell writes with old values recorded for --restore."""

    def __init__(self):
        self.items = []         # [table, row, col, old_hex, new_hex]

    def set(self, table, r, c, new):
        s = load(table)
        new = new if isinstance(new, bytes) else str(new).encode("latin-1")
        if s.d[r][c] != new:
            self.items.append([table, r, c, s.d[r][c].hex(), new.hex()])
            s.d[r][c] = new


def skill_rows(base, tm, fe):
    sp = [load("LIST_SKILL.STB").d[SP_FROM + n][3].decode() for n in range(RANKS)]
    fx = dict(zip(FX, fe))
    rows = []
    for n in range(RANKS):
        c = {0: NAME, 1: base, 2: n + 1, 3: sp[n], 4: 1,
             5: 3, 6: DISTANCE, 7: 5, 9: POWER[n], 10: 1, 15: 1,
             16: AT_MP, 17: MP[n], 20: RELOAD[n],
             29: 2,                     # SKILL_ACTION_MODE: back to the running command
             30: WEAPON_DUAL, 51: ICON,
             52: tm[0], 53: 100, 54: tm[1],
             56: fx["GATHER"], 57: 999,
             59: fx["LAUNCH"], 60: 999,
             62: fx["APEX"], 63: APEX_POINT,
             65: fx["IMPACT"], 66: 999,
             68: tm[2], 69: 100, 70: 1,
             74: fx["FINAL"], 75: 999, 76: HIT_SOUND,
             77: fx["SLASH_A"], 78: 999, 79: SOUND_A,
             80: fx["SLASH_B"], 81: 999, 82: SOUND_B,
             86: f"LSkill{base}"}
        if n == 0:
            c.update({35: CLASS_RAIDER, 39: PREREQ[0], 40: PREREQ[1], 45: AT_LEVEL, 46: LEVEL})
        rows.append([str(c.get(k, "")).encode("latin-1") for k in range(87)])
    return rows


def plan():
    sk, fm, tm, fe = (load(n) for n in ("LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB", "FILE_EFFECT.STB"))
    first = last_used(fe) + 1
    fe_rows = list(range(first, first + len(FX)))
    if fe_rows[-1] >= fe.rows:
        sys.exit("FILE_EFFECT has too few blank rows left -- refusing")
    if sk.d[PREREQ[0]][0] != b"Battle Mastery" or sk.d[PREREQ[0] + PREREQ[1] - 1][2] != str(PREREQ[1]).encode():
        sys.exit(f"LIST_SKILL {PREREQ[0]} is not Battle Mastery with a rank {PREREQ[1]} -- refusing")
    if sk.rows + RANKS > 16383:
        sys.exit("LIST_SKILL would pass 16383 (doc/skill-tree-art.md) -- refusing")
    return dict(skill=sk.rows, fm=[fm.rows + k for k in range(3)], tm=[tm.rows + k for k in range(3)], fe=fe_rows)


def check_book():
    ui = load("LIST_USEITEM.STB")
    if any(ui.d[BOOK]):
        sys.exit(f"LIST_USEITEM {BOOK} is in use ({ui.d[BOOK][0]!r}) -- refusing")
    code = str(10000 + BOOK).encode()
    for t in ("LIST_SELL.STB", "ITEM_DROP.STB"):
        hits = [r for r in range(load(t).rows) if code in load(t).d[r]]
        if hits:
            sys.exit(f"{t} rows {hits} already name item 10:{BOOK} -- refusing")
    if load("LIST_SELL.STB").d[SHOP_TAB][SHOP_COL].strip(b"0"):
        sys.exit(f"shop tab {SHOP_TAB} col {SHOP_COL} is taken -- refusing")


# --- tree ----------------------------------------------------------------------------

def tree_node(base):
    x, y = BOX[0] + ART_ORIGIN[0] + 1, BOX[1] + ART_ORIGIN[1] + 2
    return f'\n      <SKILL INDEX="{base}" OFFSETX="{x}" OFFSETY="{y}"/>'


def page_path():
    hit = [f for f in os.listdir(RES_DIR) if f.upper() == TREE_PAGE]
    if not hit:
        sys.exit(f"tree art {TREE_PAGE} not found")
    return os.path.join(RES_DIR, hit[0])


def art_has_box(path):
    from PIL import Image
    return Image.open(path).convert("RGBA").load()[BOX[0], BOX[1]][3] > 8


def art_paint(path):
    """The spine carried down to a fourth branch, the stub across, the 42x42 box."""
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGBA")
    px = im.load()
    if px[SPINE_X, SPINE_END][3] < 100 or px[SPINE_X, SPINE_END + 2][3] > 8:
        sys.exit(f"{TREE_PAGE}: the spine does not end at art ({SPINE_X}, {SPINE_END}) -- refusing")
    d = ImageDraw.Draw(im)
    d.line([(SPINE_X, SPINE_END), (SPINE_X, STUB_Y)], fill=ART_LINE_RGBA)
    d.line([(SPINE_X, STUB_Y), (BOX[0] - 1, STUB_Y)], fill=ART_LINE_RGBA)
    d.rectangle([BOX[0], BOX[1], BOX[0] + ART_BOX_SIZE - 1, BOX[1] + ART_BOX_SIZE - 1], outline=ART_LINE_RGBA)
    im.save(path)


# --- main ----------------------------------------------------------------------------

def install(dry):
    if os.path.exists(MANIFEST):
        sys.exit("already installed -- --verify, or --restore first")
    p = plan()
    check_book()
    sk, fm, tm, fe = (load(n) for n in ("LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB", "FILE_EFFECT.STB"))
    blobs = files()
    clash = [rel for rel in blobs if os.path.exists(data_path(rel))]
    if clash:
        sys.exit(f"files already exist: {clash} -- refusing")
    raw_xml = open(TREE_XML, encoding="utf-8", newline="").read()
    if TREE_ANCHOR not in raw_xml:
        sys.exit("tree: anchor (the last Combat Mastery branch) not found -- refusing")
    node = tree_node(p["skill"])
    rows = skill_rows(p["skill"], p["tm"], p["fe"])

    base = p["skill"]
    print(f"{NAME}: LIST_SKILL {base}-{base + RANKS - 1}, FILE_MOTION {p['fm']}, TYPE_MOTION {p['tm']}, "
          f"FILE_EFFECT {p['fe']}, book {BOOK}, shop {SHOP_TAB}/{SHOP_COL}, icon {ICON}")
    print(f"  Raider, dual swords, level {LEVEL}, Battle Mastery rank {PREREQ[1]}; distance {DISTANCE / 100:.0f} m")
    print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'SP':>5}")
    for n in range(RANKS):
        print(f"  {n + 1:>4}{POWER[n]:>7}{RELOAD[n] * 0.2:>6.1f}{MP[n]:>5}{rows[n][3].decode():>5}")
    print(f"  tree node:{node}")
    print(f"  {len(blobs)} files")
    if dry:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    page = page_path()
    page_backup = os.path.join(OUT, os.path.basename(page) + ".orig")
    if not os.path.exists(page_backup):
        shutil.copyfile(page, page_backup)
    if not art_has_box(page):
        art_paint(page)

    for rel, blob in blobs.items():
        os.makedirs(os.path.dirname(data_path(rel)), exist_ok=True)
        open(data_path(rel), "wb").write(blob)

    cells = Cells()
    for r, fx in zip(p["fe"], FX):
        cells.set("FILE_EFFECT.STB", r, 0, f"SKYREND_{fx}")
        cells.set("FILE_EFFECT.STB", r, 1, f"{EFFECT}SKYREND_{fx}.EFT")
    ui = load("LIST_USEITEM.STB")
    over = {0: NAME, 20: base, 27: f"LUSE{BOOK}"}
    for c in range(ui.cols):
        cells.set("LIST_USEITEM.STB", BOOK, c, over.get(c, ui.d[BOOK_TEMPLATE][c]))
    cells.set("LIST_SELL.STB", SHOP_TAB, SHOP_COL, 10000 + BOOK)

    fm.grow_to(fm.rows + 3, {r: lbl for r, (_, lbl) in zip(p["fm"], CLIPS)})
    for r, (name, _) in zip(p["fm"], CLIPS):
        fm.d[r][0] = (AVATAR + name).encode("latin-1")
    tm.grow_to(tm.rows + 3, {r: lbl for r, (_, lbl) in zip(p["tm"], CLIPS)})
    for r, f in zip(p["tm"], p["fm"]):
        tm.d[r] = [str(f).encode() for _ in range(tm.cols)]
    sk.grow_to(sk.rows + RANKS)
    for n, row in enumerate(rows):
        sk.d[base + n] = row
    for t in {"LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB"} | {x[0] for x in cells.items}:
        save(t)
    for name, key, row in (("LIST_SKILL_S.STL", f"LSkill{base}", base), ("LIST_USEITEM_S.STL", f"LUSE{BOOK}", BOOK)):
        t = Stl(os.path.join(STB_DIR, name))
        t.append(key, row, NAME, DESC)
        t.save(False, keep_backup=False)
    # after the last branch's block: a direct child of Battle Mastery, like the others
    open(TREE_XML, "w", encoding="utf-8", newline="").write(raw_xml.replace(TREE_ANCHOR, TREE_ANCHOR + node, 1))

    labels = {"FILE_MOTION.STB": [lbl for _, lbl in CLIPS], "TYPE_MOTION.STB": [lbl for _, lbl in CLIPS],
              "LIST_SKILL.STB": [""] * RANKS}
    json.dump(dict(plan=p, labels=labels, cells=cells.items, files=sorted(blobs), tree_node=node,
                   page=[page, page_backup]), open(MANIFEST, "w"), indent=1)
    print("done -- restart the server, re-bake, copy skilltree_howker.xml loose into the launch folder")


def restore():
    if not os.path.exists(MANIFEST):
        sys.exit("no manifest -- nothing to restore")
    m = json.load(open(MANIFEST))
    p = m["plan"]
    appended = {"LIST_SKILL.STB": p["skill"], "FILE_MOTION.STB": p["fm"][0], "TYPE_MOTION.STB": p["tm"][0]}
    tails = {}
    for name, base in appended.items():
        t = load(name)
        labels = m["labels"][name]
        tail = b"".join(write_pstr16(lbl.encode("latin-1")) for lbl in labels)
        if t.rows != base + len(labels) or not t.header.endswith(tail):
            sys.exit(f"{name}: rows were appended after this import -- refusing to truncate")
        tails[name] = (tail, len(labels))
    for name, base in appended.items():
        t = load(name)
        tail, n = tails[name]
        t.header, t.d, t.rows = t.header[:-len(tail)], t.d[:base], base
        if t.rownames:
            del t.rownames[-n:]
        save(name)
    for table in {c[0] for c in m["cells"]}:
        s = load(table)
        for t, r, c, old, _ in m["cells"]:
            if t == table:
                s.d[r][c] = bytes.fromhex(old)
        save(table)
    for name, key in (("LIST_SKILL_S.STL", f"LSkill{p['skill']}"), ("LIST_USEITEM_S.STL", f"LUSE{BOOK}")):
        t = Stl(os.path.join(STB_DIR, name))
        t.remove([key])
        t.save(False, keep_backup=False)
    for rel in m["files"]:
        if os.path.isfile(data_path(rel)):
            os.remove(data_path(rel))
    raw = open(TREE_XML, encoding="utf-8", newline="").read()
    open(TREE_XML, "w", encoding="utf-8", newline="").write(raw.replace(m["tree_node"], "", 1))
    page, backup = m["page"]
    if os.path.exists(backup):
        shutil.copyfile(backup, page)
    os.remove(MANIFEST)
    print("restored: rows, cells, keys, files, tree node and page")


def verify():
    if not os.path.exists(MANIFEST):
        sys.exit("not imported")
    m = json.load(open(MANIFEST))
    p = m["plan"]
    ok = True
    sk = load("LIST_SKILL.STB")
    want = skill_rows(p["skill"], p["tm"], p["fe"])
    for n in range(RANKS):
        diff = [c for c in range(87) if sk.d[p["skill"] + n][c] != want[n][c]]
        if diff:
            ok = False
            print(f"  row {p['skill'] + n} ({NAME} rank {n + 1}) differs in cols {diff}")
    for t, r, c, _, new in m["cells"]:
        if load(t).d[r][c] != bytes.fromhex(new):
            ok = False
            print(f"  {t} {r}/{c} differs")
    for rel, blob in files().items():
        if not os.path.isfile(data_path(rel)) or open(data_path(rel), "rb").read() != blob:
            ok = False
            print(f"  {rel} is missing or stale")
    for name, key in (("LIST_SKILL_S.STL", f"LSkill{p['skill']}"), ("LIST_USEITEM_S.STL", f"LUSE{BOOK}")):
        if not Stl(os.path.join(STB_DIR, name)).has(key):
            ok = False
            print(f"  {name} lacks {key}")
    if m["tree_node"] not in open(TREE_XML, encoding="utf-8", newline="").read():
        ok = False
        print("  tree node missing")
    if not art_has_box(page_path()):
        ok = False
        print("  tree box not painted")
    print("verify:", "ok" if ok else "FAILED")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    if args.restore:
        return restore()
    if args.verify:
        return verify()
    install(args.dry_run)


if __name__ == "__main__":
    main()
