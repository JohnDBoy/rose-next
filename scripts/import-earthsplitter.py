"""Earthsplitter: the Champion's two-handed-sword area skill, an aimed cone of rising rock.

    python scripts/import-earthsplitter.py --dry-run
    python scripts/import-earthsplitter.py
    python scripts/import-earthsplitter.py --verify
    python scripts/import-earthsplitter.py --restore

Deploy: restart the game server (it reads LIST_SKILL, LIST_USEITEM, LIST_SELL, the
motion tables and the clips), re-bake, and copy `skilltree_soldier.xml` loose into the
launch folder's 3DDATA/CONTROL/XML (read with fopen, never from the VFS).

Why
---
2026-10-24: someone shared the SlopRose repo (`C:\\Users\\Thomas\\Desktop\\Rose\\sloprose`),
whose SlopStudio carries a Claude skill, `slopstudio/.claude/skills/rose-anim-toolkit`,
that authors player motions procedurally -- stock clips retimed and exaggerated, the
left hand IK'd onto the grip -- and mesh effects that rise out of the ground. The user
asked to try it on a skill; this began as a GM test row (`add-earthsplitter-test.py`,
5bdff268 / ddd27981), was reshaped in game into an aimed cone, and the user then made
it a real skill: the Champion's fourth weapon skill, **two-handed sword, after Voltage
Crush** -- the sword's area skill, as Dance of Flames is the spear's. Icon by the user,
in the style of the classic Soldier icons (reference sheet from
`build/earthsplitter/icon-reference/`).

The source files in `build/earthsplitter/src/` were made by the toolkit (a copy patched
to read our loose `data/`: their VFS reader does not parse our `data.idx`, and our
Junior cap names dummy 65535 for "none"):

* `EARTHSPLIT_M1.ZMO` -- 71 frames: TWOSWD_3ATTACK's lean-back raise (16 frames, chest
  and pelvis twisted further), a 4-frame gather, a hop, the slam coming over, the
  blade buried at frame 29 (TWOSWD_HEAVYATTACK's impact, crouched deeper), a 7-frame
  tremor and HEAVYATTACK's crouched rise back to TWOSWD_STOP1. Toolkit builder:
  charged.py's swing 3 as a standalone skill (`kit/earthsplitter.py` in that session's
  scratchpad).
* `EARTHSPLIT_HOLD_M1.ZMO` -- 10 frames: frame 23 (the coil's anticipation dip, blade
  raised behind) trembling at 9 Hz, three whole cycles so it loops.
* `rocks/` -- `rock_spike_fx.py --write`: a cluster of four rocks (an `_ICE_02` shard
  re-textured STONE007, a point-up Junon stalactite JONGUSTONE05, two JONGUSTONE06
  needles) that erupt in 3 frames, hold with a tremble to 1 s and sink (38 frames at
  30 fps), each rock a ZMS copy resting in its buried pose plus a per-vertex ZMO,
  with `_DUST_02` and `Z_SPLINTER_01` bursts.

What this script does with them (rosefmt only):

* **The clip is split before the hop** (`rosefmt.zmo.sliced`): the cast (col 52) is
  frames 0-23 -- raise and gather -- and the action (col 68) the hop, the slam, the
  impact and the rise: 34 at 3, 74 (the fissure) at 4 as the blade meets the ground,
  24 (the area event) at 5 on the impact. The cast's events are cleared. The hold is
  the cast loop (col 54, count 0): it plays while the client waits for the server's
  go-ahead. Split on the impact itself (an area skill's damage lands when its action
  starts, `scripts/CLAUDE.md`, Exceed Break), the blade sat in the ground through
  that wait and the rocks came a beat late.
* **Two effects.** `EARTHSPLIT_ROCKS.eft` is the toolkit's cluster, renamed, as the hit
  effect (col 74) under every monster hit. `EARTHSPLIT_FISSURE.eft` (casting slot 2,
  col 62, on event 74) is that cluster repeated down the cone: a row every 1.5 m from
  where the blade lands to 7.5 m, 1 -> 4 clusters as the cone widens, each row 100 ms
  after the last (15 m/s), so the crack runs away from the blade. It plays in the
  caster's frame (front = -Y), and the caster faces the aim. Copies are turned 0 or 180
  degrees only: the toolkit's preview turns an entry by +yaw about up, and our engine's
  YawPitchRoll swizzle may run the other way, which a half-turn does not care about.
  44 mesh entries in one effect needs the 5bdff268 client (`CEffectDATA::Load` used to
  wrap its string buffer after ~20).
* **The cone** (the user's idea): type 7 with the cone scope `100000000 + 800 * 10000 +
  60` (io_skill.h SKILL_SCOPE_CONE, built for Cerberus's breath), so pressing it shows
  the 8 m / 60 degree cone from the player toward the mouse (`CSkillAim`) and a click
  casts it; every monster in it is hit. Aim range (col 6) = the cone's length; only the
  direction matters. The cone does not grow with rank: the fissure is one effect file,
  drawn for 8 m. Damage lands when the action starts, so far targets' digits come
  before the crack reaches them.
* **The hit sound** (col 76) is `point_heavy01.wav` (1551, Gun Smash's) -- a skill's
  only noise is its hit sound on what it hits (the casting-slot sound columns are read
  by nothing; Impact Wave too is silent with nothing in range). Impact Wave's
  `Skill_magic01` (139) is a soft sparkle, played in 3D 4-8 m away;  `point_heavy01` is
  the loudest heavy hit we ship (peak RMS 22656 vs 12960) and peaks within 20 ms. It
  plays because ddd27981 gave the late-payload branch of Recv_gsv_DAMAGE_OF_SKILL the
  hit effect and sound -- the local avatar's type-7 payload always lands there.

The numbers (ranks 1 -> 10, linear)
-----------------------------------
    power 480 -> 880    cd 14 -> 11 s    MP 70 -> 135    cone 8 m / 60 deg
    Champion (class 62), two-handed sword (221), level 90, Voltage Crush rank 5

Sized against Dance of Flames (450 -> 820, 14 -> 11 s, 70 -> 135 MP, radius 6 -> 8 m,
level 85), the Champion's other area skill: the same budget, a little more power
because there is no Burning on top, and a front cone the player aims instead of a
circle around them. Both stay well under Champion Hit (1200), the Champion's single-
target reference -- an area skill trades power per target for count (Exceed Break took
~0.75x). The combat sim is one-on-one and does not model a cone. Skill points per rank
copy Dance of Flames'.

How a player gets it
--------------------
* **Book**: LIST_USEITEM 696 (blank, after the three Champion books 693-695; a copy of
  Champion Hit's 692), sold in Darren's "Soldier" tab (LIST_SELL 462) at col 33, the
  end of row 4 under Final Strike's book.
* **Gates** on rank 1: class set 62, Voltage Crush (7027) rank 5, `AT_LEVEL` 90.
* **Trees**: UI2's builds itself from the class set and prerequisite. The classic tree
  gets a node under Voltage Crush on the Weapon Mastery page and a box painted at art
  (259, 388), joined to Voltage Crush's box (259, 330) by a plain line (an arrowhead
  would mean "higher rank", `doc/skill-tree-art.md`). The box sits 16 px under its
  parent rather than the page's usual 24: the dialog's content ends at y 509, and the
  icon (dialog y 465-505) has to clear it.
* **Icon** 533 (skill04.dds cell 26): the user's art, cropped to its frame and added by
  `add-skill-icon.py build/earthsplitter/icon.png --name earthsplitter`; that tool owns
  the atlas and its undo. Written into col 51 here so a re-import keeps it.

What it changes
---------------
    LIST_SKILL.STB / _S.STL      10 rows appended, 1 key
    FILE_MOTION.STB              3 rows appended (cast, hold, action)
    TYPE_MOTION.STB              3 rows appended, every weapon column
    FILE_EFFECT.STB              2 blank rows filled (the first two after 3001)
    LIST_USEITEM.STB / _S.STL    row 696, key LUSE696
    LIST_SELL.STB                tab 462 col 33
    MOTION/AVATAR                EARTHSPLIT_CAST/_HOLD/_ACTION_M1.ZMO
    EFFECT                       EARTHSPLIT_ROCKS.eft, EARTHSPLIT_FISSURE.eft,
                                 EFFECTMESH/EARTHSPLIT_<rock>.ZMS/.ZMO (8 files)
    skilltree_soldier.xml        1 node; SOLDIER_WEAPON_MASTERY.DDS painted

`--restore` truncates the appended rows (only while they are still last), puts every
other cell back, removes the keys, files and node, and restores the page from
`build/earthsplitter/` (never under data/: pack.rs would bake a backup).
`scripts/fix-skill-book-names.py` will list book 696 as a newcomer; its name matches.
"""
import argparse
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt.stb import Stb  # noqa: E402
from rosefmt.stl import Stl  # noqa: E402
from rosefmt.binio import write_pstr16  # noqa: E402
from rosefmt import eft, zmo  # noqa: E402

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
RES_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "RES")
TREE_XML = os.path.join(DATA, "3DDATA", "CONTROL", "xml", "skilltree_soldier.xml")
OUT = os.path.join(ROOT, "build", "earthsplitter")
SRC = os.path.join(OUT, "src")
MANIFEST = os.path.join(OUT, "manifest-skill.json")

NAME = "Earthsplitter"
DESC = ("Leap and drive your blade into the ground. The earth splits open in a cone in "
        "front of you, and rocks burst up under every enemy in it.")
RANKS = 10
CLASS_CHAMPION, WEAPON_2H_SWORD, LEVEL = 62, 221, 90
PREREQ = (7027, 5)                # Voltage Crush rank 5
AT_MP, AT_LEVEL = 17, 31
ICON = 533
SP_FROM = 7037                    # Dance of Flames' skill points per rank


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


POWER = lin(480, 880)
RELOAD = lin(70, 55)              # x0.2 s -> 14 -> 11 s
MP = lin(70, 135)

CONE_CM, CONE_DEG = 800, 60
SCOPE = 100000000 + CONE_CM * 10000 + CONE_DEG   # io_skill.h SKILL_SCOPE_CONE
HIT_SOUND = 1551                  # point_heavy01.wav (Gun Smash's), see the docstring
IMPACT = 29                       # the buried-blade frame of EARTHSPLIT_M1
SPLIT = 24                        # the first action frame: the hop
# in action frames: the cue, the fissure as the blade meets the ground (frame 28 -- a
# frame early, the rocks take three to break the surface), the area event on the impact
ACTION_EVENTS = {IMPACT - SPLIT - 2: 34, IMPACT - SPLIT - 1: 74, IMPACT - SPLIT: 24}

BOOK, BOOK_TEMPLATE = 696, 692
SHOP_TAB, SHOP_COL = 462, 33

TREE_PAGE = "SOLDIER_WEAPON_MASTERY.DDS"
TREE_ANCHOR = '<SKILL INDEX="7027" OFFSETX="280" OFFSETY="407"/>'
PARENT_BOX, BOX = (259, 330), (259, 388)
ART_ORIGIN, ART_LINE_RGBA, ART_BOX_SIZE = (20, 75), (74, 81, 99, 255), 42

AVATAR = "3DDATA\\MOTION\\AVATAR\\"
CLIPS = [("EARTHSPLIT_CAST_M1.ZMO", "earthsplit cast"),
         ("EARTHSPLIT_HOLD_M1.ZMO", "earthsplit hold"),
         ("EARTHSPLIT_ACTION_M1.ZMO", "earthsplit action")]
ROCKS_EFT = "3DDATA\\EFFECT\\EARTHSPLIT_ROCKS.eft"
FISSURE_EFT = "3DDATA\\EFFECT\\EARTHSPLIT_FISSURE.eft"
MESH_DIR = "3DDATA\\EFFECT\\EFFECTMESH\\"
ROCK_NAMES = ("SHARDS", "FANG", "NEEDLE", "NEEDLE_SMALL")

# the fissure: a row of clusters every ROW_CM from the blade (1.5 m) to the cone's end,
# spread ROW_SPACING_CM apart across the cone (kept HALF_SPREAD inside its 30-degree
# half-angle), each row ROW_MS after the last
ROW_CM, ROW_SPACING_CM, HALF_SPREAD, ROW_MS = 150.0, 170.0, 24.0, 100
ONE_OFFSET = (0.0, 7.0, -7.0)     # a row of one: alternate sides so the rows do not line up


def fissure_layout():
    """[((x, y) cm in the caster's frame, front = -Y), turn (0 / 180 only, see the
    docstring), delay ms] for every cluster."""
    out = []
    rows = int(CONE_CM // ROW_CM)
    for i in range(rows):
        r = ROW_CM * (i + 1)
        arc = r * math.radians(2 * HALF_SPREAD)
        n = max(1, round(arc / ROW_SPACING_CM))
        if n == 1:
            angles = [ONE_OFFSET[i % len(ONE_OFFSET)]]
        else:
            angles = [-HALF_SPREAD + 2 * HALF_SPREAD * k / (n - 1) for k in range(n)]
        for k, deg in enumerate(angles):
            a = math.radians(deg)
            out.append(((r * math.sin(a), -r * math.cos(a)), 180.0 * ((i + k) % 2), ROW_MS * i))
    return out


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

def clips():
    full = open(os.path.join(SRC, "EARTHSPLIT_M1.ZMO"), "rb").read()
    total = zmo.read_header(full)[1]
    ev = zmo.events(full)[1]
    if ev[IMPACT] != 25:
        sys.exit(f"EARTHSPLIT_M1 has no skill hit at frame {IMPACT} -- rebuild it")
    cast = zmo.sliced(full, 0, SPLIT)
    cast = zmo.with_events(cast, {i: 0 for i, e in enumerate(zmo.events(cast)[1]) if e})
    action = zmo.sliced(full, SPLIT, total)
    changes = {i: 0 for i, e in enumerate(zmo.events(action)[1]) if e}
    changes.update(ACTION_EVENTS)
    action = zmo.with_events(action, changes)
    hold = open(os.path.join(SRC, "EARTHSPLIT_HOLD_M1.ZMO"), "rb").read()
    return [cast, hold, action]


def rename_rock(path):
    stem = path.split("\\")[-1].rsplit(".", 1)
    for rock in ROCK_NAMES:
        if stem[0].upper() == "ROCKSPIKE_" + rock:
            return MESH_DIR + "EARTHSPLIT_" + rock + "." + stem[1]
    return path


def cluster():
    c = eft.read(open(os.path.join(SRC, "rocks", "ROCK_SPIKE.EFT"), "rb").read())
    for m in c["meshes"]:
        m["zms"], m["zmo"] = rename_rock(m["zms"]), rename_rock(m["zmo"])
    c["name"] = "EARTHSPLIT_ROCKS"
    return c


def fissure(c):
    parts, meshes = [], []
    for (cx, cy), turn, delay in fissure_layout():
        a = math.radians(turn)
        ca, sa = math.cos(a), math.sin(a)

        def place(e):
            e = dict(e)
            x, y, z = e["pos"]
            e["pos"] = (cx + ca * x - sa * y, cy + sa * x + ca * y, z)
            r = list(e["rot"])
            r[1] = (r[1] + turn) % 360.0
            e["rot"] = tuple(r)
            e["delay"] = e["delay"] + delay
            return e
        parts += [place(p) for p in c["particles"]]
        meshes += [place(m) for m in c["meshes"]]
    return dict(c, name="EARTHSPLIT_FISSURE", particles=parts, meshes=meshes)


def generated():
    files = {AVATAR + name: blob for (name, _), blob in zip(CLIPS, clips())}
    c = cluster()
    files[ROCKS_EFT] = eft.build(c)
    files[FISSURE_EFT] = eft.build(fissure(c))
    for rock in ROCK_NAMES:
        for ext in ("ZMS", "ZMO"):
            files[f"{MESH_DIR}EARTHSPLIT_{rock}.{ext}"] = open(
                os.path.join(SRC, "rocks", f"ROCKSPIKE_{rock}.{ext}"), "rb").read()
    return files


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
    sp = [load("LIST_SKILL.STB").d[SP_FROM + n][3] for n in range(RANKS)]
    rows = []
    for n in range(RANKS):
        c = {0: NAME, 1: base, 2: n + 1, 3: sp[n].decode(), 4: 1,
             5: 7, 6: CONE_CM, 7: 5, 8: SCOPE, 9: POWER[n], 10: 1, 15: 1,
             16: AT_MP, 17: MP[n], 20: RELOAD[n],
             29: 2,                     # SKILL_ACTION_MODE: back to the running command
             30: WEAPON_2H_SWORD, 51: ICON,
             52: tm[0], 53: 100, 54: tm[1],
             62: fe[1], 63: 999,        # the fissure, on event 74, in the caster's frame
             68: tm[2], 69: 100, 70: 1,
             74: fe[0], 75: 999, 76: HIT_SOUND,
             86: f"LSkill{base}"}
        if n == 0:
            c.update({35: CLASS_CHAMPION, 39: PREREQ[0], 40: PREREQ[1], 45: AT_LEVEL, 46: LEVEL})
        rows.append([str(c.get(k, "")).encode("latin-1") for k in range(87)])
    return rows


def plan():
    sk, fm, tm, fe = (load(n) for n in ("LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB", "FILE_EFFECT.STB"))
    first_fe = last_used(fe) + 1
    fe_rows = [first_fe, first_fe + 1]
    if fe_rows[1] >= fe.rows:
        sys.exit("FILE_EFFECT has no blank rows left -- refusing")
    if sk.d[PREREQ[0]][0] != b"Voltage Crush":
        sys.exit(f"LIST_SKILL {PREREQ[0]} is not Voltage Crush -- refusing")
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
    return f'\n         <SKILL INDEX="{base}" OFFSETX="{x}" OFFSETY="{y}"/>'


def page_path():
    hit = [f for f in os.listdir(RES_DIR) if f.upper() == TREE_PAGE]
    if not hit:
        sys.exit(f"tree art {TREE_PAGE} not found")
    return os.path.join(RES_DIR, hit[0])


def art_has_box(path):
    from PIL import Image
    return Image.open(path).convert("RGBA").load()[BOX[0], BOX[1]][3] > 8


def art_paint(path):
    """A plain line from Voltage Crush's box down to the new 42x42 box."""
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGBA")
    d = ImageDraw.Draw(im)
    half = ART_BOX_SIZE // 2
    d.line([(PARENT_BOX[0] + half, PARENT_BOX[1] + ART_BOX_SIZE - 1), (BOX[0] + half, BOX[1])],
           fill=ART_LINE_RGBA)
    d.rectangle([BOX[0], BOX[1], BOX[0] + ART_BOX_SIZE - 1, BOX[1] + ART_BOX_SIZE - 1],
                outline=ART_LINE_RGBA)
    im.save(path)


# --- main ----------------------------------------------------------------------------

def install(dry):
    if os.path.exists(MANIFEST):
        sys.exit("already installed -- --verify, or --restore first")
    p = plan()
    check_book()
    sk, fm, tm, fe = (load(n) for n in ("LIST_SKILL.STB", "FILE_MOTION.STB", "TYPE_MOTION.STB", "FILE_EFFECT.STB"))
    files = generated()
    clash = [rel for rel in files if os.path.exists(data_path(rel))]
    if clash:
        sys.exit(f"files already exist: {clash} -- refusing")
    raw_xml = open(TREE_XML, encoding="utf-8", newline="").read()
    if TREE_ANCHOR not in raw_xml:
        sys.exit(f"tree: anchor {TREE_ANCHOR} not found -- refusing")
    node = tree_node(p["skill"])
    rows = skill_rows(p["skill"], p["tm"], p["fe"])

    base = p["skill"]
    print(f"{NAME}: LIST_SKILL {base}-{base + RANKS - 1}, FILE_MOTION {p['fm']}, TYPE_MOTION {p['tm']}, "
          f"FILE_EFFECT {p['fe']}, book {BOOK}, shop {SHOP_TAB}/{SHOP_COL}, icon {ICON}")
    print(f"  Champion, two-handed sword, level {LEVEL}, Voltage Crush rank {PREREQ[1]}; "
          f"cone {CONE_CM / 100:.0f} m / {CONE_DEG} deg")
    print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'SP':>5}")
    for n in range(RANKS):
        print(f"  {n + 1:>4}{POWER[n]:>7}{RELOAD[n] * 0.2:>6.1f}{MP[n]:>5}{rows[n][3].decode():>5}")
    print(f"  tree node:{node}")
    print(f"  {len(files)} files, fissure {len(fissure_layout())} clusters")
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

    for rel, blob in files.items():
        os.makedirs(os.path.dirname(data_path(rel)), exist_ok=True)
        open(data_path(rel), "wb").write(blob)

    cells = Cells()
    for r, rel in zip(p["fe"], (ROCKS_EFT, FISSURE_EFT)):
        cells.set("FILE_EFFECT.STB", r, 0, rel.split("\\")[-1].rsplit(".", 1)[0])
        cells.set("FILE_EFFECT.STB", r, 1, rel)
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
    open(TREE_XML, "w", encoding="utf-8", newline="").write(raw_xml.replace(TREE_ANCHOR, TREE_ANCHOR + node, 1))

    labels = {"FILE_MOTION.STB": [lbl for _, lbl in CLIPS], "TYPE_MOTION.STB": [lbl for _, lbl in CLIPS],
              "LIST_SKILL.STB": [""] * RANKS}
    json.dump(dict(plan=p, labels=labels, cells=cells.items, files=sorted(files), tree_node=node,
                   page=[page, page_backup]), open(MANIFEST, "w"), indent=1)
    print(f"done -- restart the server, re-bake, copy skilltree_soldier.xml loose into the launch folder")


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
    for rel, blob in generated().items():
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
