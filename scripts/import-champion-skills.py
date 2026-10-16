"""Import three Champion weapon-signature skills from the 668 client.

    python scripts/import-champion-skills.py --dry-run
    python scripts/import-champion-skills.py
    python scripts/import-champion-skills.py --verify
    python scripts/import-champion-skills.py --restore

Why
---
The Champion had two exclusive attack skills, and neither told its three weapons
apart: Champion Hit takes the two-handed sword, the spear and the axe alike, and
Space Attack any melee weapon. The class pitch is "the three-weapon attacker", so
each weapon gets a signature skill with a mechanical identity of its own -- shock,
fire, execution -- rather than three copies of "big hit":

    Voltage Crush    2H sword  lv 70   Two-Handed Mastery r6   single hit, Attack Speed Down
    Dance of Flames  spear     lv 85   Two-Handed Mastery r8   spin around you, Burning
    Final Strike     axe       lv 100  Two-Handed Mastery r10  huge hit for HP, Defense
                                                               Down on everything around
                                                               the target

All three come from the 668 (official Rednim) client, which carries the full Evolution
Champion kit. Only presentation is taken; every gameplay number is ours.

* **Voltage Crush** keeps 668's presentation verbatim, including its animation --
  `ths_pstrike_start/repeat/cast.ZMO`, new in 668 and the reason it was picked. Those
  clips animate 21 channels where all of ours animate 22; tested in game on
  2026-10-17 (GM test rows, since removed) and they play correctly.
* **Dance of Flames** is Spin Attack's animation with 668's `_blaze_01.eft` ring of
  fire: the effect and its `.ptl` are copied (the texture is already ours) and
  FILE_EFFECT row 2019, blank here, takes the same row 668 uses.
* **Final Strike** is *not* 668's: theirs is Heavy Attack's clip with Heavy Attack's
  effects. Four unused clips we already ship were tested in game, each with a
  different ground burst, and the user picked "D": `skill_Longinus_01` (TYPE_MOTION
  185, never used by any skill even in 668) at x1.5, with Quake Impact's
  `holy_sword_01.eft` on the target, under 668 Final Strike's heavy wind-up.

The numbers
-----------
Ranks 1 -> 10, linear:

    Voltage Crush    power 380 -> 950    cd 9 -> 7 s    MP 45 -> 85
                     Attack Speed Down 15 -> 30% for 6 -> 9 s
    Dance of Flames  power 450 -> 820    cd 14 -> 11 s  MP 70 -> 135   radius 6 -> 8 m
                     Burning (new status, 150 per second) for 6 -> 10 s
    Final Strike     power 500 -> 1150   cd 16 -> 13 s  HP 150 -> 350 + MP 40 -> 80
                     Defense Down 12 -> 25% for 8 -> 12 s, within 4 -> 6 m of the target

Measured against Champion Hit (1200 power, 11 s), the Champion's reference, because
the Champion is already the strongest class in the sweep (Berserk's permanent +52%,
kept by decision). What the three add is identity -- the sword keeps a target numbed,
the spear finally gives the Champion an area skill of its own, the axe softens a pack
-- not a new top hit:

* **Final Strike stays under Champion Hit.** The first cut (650 -> 1500) out-hit it,
  and since the sim's rotation opens with the biggest skill, an axe Champion
  one-shot plain monsters from level 100 (TTK 1.25 -> 0.4 s) and tripled its damage
  on them. Star monsters (longer fights) went +40% at 100-130 and +268% at 160.
* **All three hang off Two-Handed Mastery** (row 221, Champion-only, 10 ranks), the
  user's call: the first cut tied each to a weapon skill (Space Attack r5, Spin
  Attack r5, Champion Hit r5) and the placements read as arbitrary. The rank tracks
  each skill's level gate -- the auto-builds reach Two-Handed Mastery r5 at level
  70, r8 at 85, r10 at 100 -- so the mastery and the level open together, high
  without one requirement idling behind the other. (An earlier Spin Attack r10 for
  Dance kept the spear without its skill until ~160.)
* Sustained damage against star monsters, sword/spear, with the skill vs without
  (combat sim, typical play, auto-builds): +18% / 0% at 100, +46% / +25% at 130,
  +16% / +12% at 200; -16% / -17% at 160, where the auto-build spends the skill
  points on the new skill instead of Blood Attack (a choice, not a loss in the skill) Measured
  with the first prerequisites; the Two-Handed Mastery gate moves when a build
  learns each skill (sword ~lv 85, spear 85, axe 100), not what it does.

* **Debuff chance at Champion INT.** A harmful status lands on
  `ratio * (LV*2 + INT + 20) / (RES*0.6 + 5 + AVOID)` against 1-100, and a Champion
  carries ~15 INT, so the same ratio decays with level: 100 lands ~85% at level 100
  and ~58% at level 200 on plain monsters (the sim's `harmful_state_chance`). Ratios
  climb with rank -- 60 -> 100 (Voltage, Dance), 70 -> 110 (Final Strike).
* **Final Strike's spread is free in the engine.** A type-3 skill with SKILL_SCOPE set
  still damages only its target (`Skill_START_03_04_05`), but `Skill_ChangeIngSTATUS`
  applies its status to every enemy within SKILL_SCOPE *of the target*. Poison Fang
  has always worked this way.
* **Burning needed its own row.** LIST_STATUS 58 burns for a flat 30 per second --
  noise at level 85+, and monster fire bolts use it, so it cannot be raised. Row 62
  is a copy at 150 per second (`STATE_APPLY_ABILITY_VALUE`, ticked once a second by
  `StatusEffects::Proc` for the ING_POISONED slot, which poison shares: the newer of
  the two wins).
* Costs: Final Strike pays in blood like Champion Hit (`AT_HP` + a little MP); the
  client deducts it and `Skill_GetAbilityValue(AT_HP)` keeps 1 HP back, so it cannot
  kill you. Skill points per rank copy Space Attack's curve (Voltage) and Champion
  Hit's (the other two).

How a player gets them
----------------------
* **Books.** Rank 1 of a class skill is learned only from its book
  (`CLI_SKILL_LEARN_REQ` is compiled out on the server); ranks 2+ are raised with
  skill points. LIST_USEITEM 693-695 (blank, right after Champion Hit's 692) become
  the three books, a copy of 692, sold in Darren's "Soldier" tab (LIST_SELL 462,
  shared with the four Akram Ministers and Arua's Fairy).
* **Gates.** Class set 62 (Champion) on rank 1, the prerequisite on rank 1, and an
  `AT_LEVEL` requirement (col 45/46) on rank 1 -- checked by the server's
  `Skill_CheckNeedABILITY` and shown in both skill windows.
* **Trees.** UI2's tree builds itself from the class set and prerequisite columns.
  The classic tree gets XML nodes and painted boxes (recipe: `doc/skill-tree-art.md`):
  a bracket under Two-Handed Mastery on the Weapon Mastery page, sword / spear / axe
  left to right, drawn in the style of the existing bracket above One- and
  Two-Handed Mastery (plain lines -- an arrowhead would mean "higher rank").
* **Icons** are 668's own (the user: fine for skills that are entirely new), added
  as sprites on skill04.dds by `upgrade-skill-icons.py --pick 7027=82 --pick
  7037=104` (-> 517, 518) and `--pick 7047=109` (-> 520): 667 holds the same art at
  those indices, and that tool owns the atlas and its undo. Final Strike first took
  668's own icon (69 -> 519, now orphaned); the user found it dull and too close to
  an existing one and picked 668's *Champion Hit* art (two axes, fiery arc) -- our
  Champion Hit keeps its classic icon, so nothing is shown twice. Run the picks
  after this import (they patch col 51 by skill name); this script writes 517 / 518
  / 520 directly so a re-import keeps them.

What it changes
---------------
    LIST_SKILL.STB        30 rows appended (3 skills x 10 ranks)
    LIST_SKILL_S.STL      3 keys
    LIST_STATUS.STB       row 62 appended; LIST_STATUS_S.STL key LSTA062
    LIST_USEITEM.STB      rows 693-695 (books); LIST_USEITEM_S.STL keys LUSE693-695
    LIST_SELL.STB         tab 462, three empty slots
    FILE_MOTION.STB       rows 662-664; TYPE_MOTION.STB rows 168-170 (Voltage Crush)
    FILE_EFFECT.STB       row 2019 (_blaze_01.eft)
    MOTION/AVATAR         + ths_pstrike_start/repeat/cast.ZMO       (from 668)
    EFFECT                + _BLAZE_01.EFT, PARTICLES/_BLAZE_01.ptl   (from 668)
    skilltree_soldier.xml 3 nodes; SOLDIER_WEAPON_MASTERY.DDS painted

Every 668 effect/sound id is checked to name the same file in our tables before it is
written. Cell-level undo, the appended-row counts, copied files and the two page
originals live in `build/champion-skills/` (never under data/: pack.rs would bake a
backup). `scripts/fix-skill-book-names.py` keeps a reviewed EXPECTED set and will list
the three new books as newcomers; their names already match their skills.

Deploy: the server reads LIST_SKILL, LIST_STATUS, LIST_USEITEM, LIST_SELL and the
motion tables and clips -- restart it. Re-bake the client, and copy
`skilltree_soldier.xml` loose into the launch folder's 3DDATA/CONTROL/XML (it is read
with fopen, never from the VFS).
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
import rosedata as ro  # noqa: E402

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
RES_DIR = os.path.join(DATA, "3DDATA", "CONTROL", "RES")
TREE_XML = os.path.join(DATA, "3DDATA", "CONTROL", "xml", "skilltree_soldier.xml")
SRC = r"C:\Users\Thomas\Desktop\Testclients\668\Extracted"
SRC_STB = os.path.join(SRC, "3DDATA", "STB")
OUT = os.path.join(ROOT, "build", "champion-skills")
MANIFEST = os.path.join(OUT, "manifest.json")

RANKS = 10
CLASS_CHAMPION = 62
AT_HP, AT_MP, AT_DEF, AT_ATK_SPD, AT_LEVEL = 16, 17, 19, 24, 31
ST_ATK_SPD_DOWN, ST_DEF_DOWN, ST_BURNING_SRC = 17, 21, 58
BURN_PER_SECOND = 150

# Voltage Crush's clips: 668's own FILE_MOTION / TYPE_MOTION rows, blank here
ZMOS = ["THS_PSTRIKE_START.ZMO", "THS_PSTRIKE_REPEAT.ZMO", "THS_PSTRIKE_CAST.ZMO"]
FILE_MOTION_ROWS = [662, 663, 664]
TYPE_MOTION_ROWS = [168, 169, 170]
BLAZE_FX = 2019                 # FILE_EFFECT row, blank here, 668's row for _blaze_01
BLAZE_FILES = ["3DDATA/EFFECT/_BLAZE_01.EFT"]

BOOK_ROWS = [693, 694, 695]     # LIST_USEITEM, blank, after Champion Hit's book 692
BOOK_TEMPLATE = 692
SHOP_TAB = 462                  # Darren's "Soldier" tab
SHOP_COLS = [16, 17, 25]        # empty slots: row 2 after Champion Hit's book, row 3's end

FX_COLS = (56, 59, 62, 65, 74, 77, 80, 83)          # FILE_EFFECT rows
SND_COLS = (58, 61, 64, 67, 73, 76, 79, 82, 84)     # FILE_SOUND rows


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


# --------------------------------------------------------------- the three skills
# "src": 668 LIST_SKILL row whose cols 52-85 are copied (then "pres" overrides)
SKILLS = [
    dict(
        key="voltage", name="Voltage Crush", weapon=221, level=70,
        prereq=(221, 6), sp_from=661, icon=517,
        desc=("Bring your blade down charged with lightning. The shock runs up the "
              "target's arms and lowers its Attack Speed for a few seconds."),
        type=3, scope=[0] * RANKS,
        power=lin(380, 950), reload=lin(45, 35), cost=[(AT_MP, lin(45, 85))],
        status=ST_ATK_SPD_DOWN, ability=(AT_ATK_SPD, [0] * RANKS, lin(15, 30)),
        success=lin(60, 100), duration=lin(6, 9),
        src=664, pres={},
        tree=dict(page="SOLDIER_WEAPON_MASTERY.DDS", anchor='<SKILL INDEX="221" OFFSETX="348" OFFSETY="341"/>',
                  from_box=(327, 264), box=(259, 330)),
    ),
    dict(
        key="dance", name="Dance of Flames", weapon=222, level=85,
        prereq=(221, 8), sp_from=671, icon=518,
        desc=("Whirl your spear through a ring of fire, cutting every enemy around you "
              "and leaving them Burning."),
        type=17, scope=lin(600, 800),
        power=lin(450, 820), reload=lin(70, 55), cost=[(AT_MP, lin(70, 135))],
        status="burning", ability=None,
        success=lin(60, 100), duration=lin(6, 10),
        src=714, pres={},
        tree=dict(page="SOLDIER_WEAPON_MASTERY.DDS", anchor='<SKILL INDEX="221" OFFSETX="348" OFFSETY="341"/>',
                  from_box=(327, 264), box=(327, 330)),
    ),
    dict(
        key="final", name="Final Strike", weapon=223, level=100,
        prereq=(221, 10), sp_from=671, icon=520,
        desc=("Bring your axe down in one last blow that cracks the earth. The target "
              "takes the full weight of it, and the shockwave lowers the Defense of "
              "every enemy around it. Costs HP as well as MP."),
        type=3, scope=lin(400, 600),
        power=lin(500, 1150), reload=lin(80, 65),
        cost=[(AT_HP, lin(150, 350)), (AT_MP, lin(40, 80))],
        status=ST_DEF_DOWN, ability=(AT_DEF, [0] * RANKS, lin(12, 25)),
        success=lin(70, 110), duration=lin(8, 12),
        # 668 Final Strike's heavy wind-up (52-67), then test "D": skill_Longinus_01
        # at x1.5 with holy_sword_01 on the target and a heavy spark on the hit dummy
        src=755, pres={68: 185, 69: 150, 70: 1, 71: 0, 72: 0, 73: 0,
                       74: 243, 75: 999, 76: 139, 77: 1040, 78: 999, 79: 67,
                       80: 0, 81: 0, 82: 0, 83: 0, 84: 0},
        tree=dict(page="SOLDIER_WEAPON_MASTERY.DDS", anchor='<SKILL INDEX="221" OFFSETX="348" OFFSETY="341"/>',
                  from_box=(327, 264), box=(395, 330)),
    ),
]

# classic tree art (doc/skill-tree-art.md): art + (20, 75) = dialog; icon at box + (1, 2)
ART_ORIGIN = (20, 75)
ART_LINE_RGBA = (74, 81, 99, 255)
ART_BOX_SIZE = 42


def stb(name, root=STB_DIR):
    return Stb(os.path.join(root, name))


def stl(name):
    return Stl(os.path.join(STB_DIR, name))


def i(cell):
    try:
        return int(cell or b"0")
    except ValueError:
        return 0


def path_of(table, row, col):
    if not (0 < row < table.rows):
        return None
    return table.d[row][col].decode("latin-1").strip().upper() or None


class Ids:
    """Checks a 668 effect/sound id names the same file in our tables."""

    def __init__(self, extra_fx=()):
        self.fe, self.fe8 = stb("FILE_EFFECT.STB"), stb("FILE_EFFECT.STB", SRC_STB)
        self.fs, self.fs8 = stb("FILE_SOUND.STB"), stb("FILE_SOUND.STB", SRC_STB)
        self.extra_fx = set(extra_fx)       # rows this run fills (blank until then)

    def check(self, col, v):
        if not v or (col in FX_COLS and v in self.extra_fx):
            return
        t_ours, t_8, c = (self.fe, self.fe8, 1) if col in FX_COLS else (self.fs, self.fs8, 0)
        a, b = path_of(t_ours, v, c), path_of(t_8, v, c)
        if not a or a != b:
            sys.exit(f"col {col} id {v}: ours names {a!r}, 668 names {b!r} -- refusing")


def tree_offset(box):
    return box[0] + ART_ORIGIN[0] + 1, box[1] + ART_ORIGIN[1] + 2


def skill_rows(base_of, sk8, ids, burn_row):
    """{skill key: [87 cells] x RANKS}."""
    out = {}
    for s in SKILLS:
        base = base_of[s["key"]]
        sp_rows = [s["sp_from"] + n for n in range(RANKS)]
        sp = [i(stb_cache["LIST_SKILL.STB"].d[r][3]) for r in sp_rows]
        rows = []
        for n in range(RANKS):
            c = {
                0: s["name"], 1: base, 2: n + 1, 3: sp[n], 4: 1,
                5: s["type"], 7: 5, 8: s["scope"][n],
                9: s["power"][n], 10: 1,
                11: burn_row if s["status"] == "burning" else s["status"],
                13: s["success"][n], 14: s["duration"][n], 15: 1,
                20: s["reload"][n],
                29: 2,                  # SKILL_ACTION_MODE: back to the running command
                30: s["weapon"],
                51: s["icon"],
                86: f"LSkill{base}",
            }
            for t, (ab, vals) in enumerate(s["cost"]):
                c[16 + 2 * t], c[17 + 2 * t] = ab, vals[n]
            if s["ability"]:
                ab, flat, rate = s["ability"]
                c[21], c[22], c[23] = ab, flat[n], rate[n]
            if n == 0:
                c[35] = CLASS_CHAMPION
                c[39], c[40] = s["prereq"]
                c[45], c[46] = AT_LEVEL, s["level"]
            for col in range(52, 86):
                v = i(sk8.d[s["src"]][col])
                if v:
                    c[col] = v
            for col, v in s["pres"].items():
                if v:
                    c[col] = v
                else:
                    c.pop(col, None)
            for col, v in c.items():
                if col in FX_COLS or col in SND_COLS:
                    ids.check(col, v)
            rows.append([str(c.get(k, "")).encode("latin-1") for k in range(87)])
        out[s["key"]] = rows
    return out


stb_cache = {}


def load(name, root=STB_DIR):
    key = name if root == STB_DIR else (root, name)
    if key not in stb_cache:
        stb_cache[key] = Stb(os.path.join(root, name))
    return stb_cache[key]


# --------------------------------------------------------------- cell edits
class Cells:
    """In-place cell writes with old values recorded for --restore."""

    def __init__(self):
        self.items = []         # [table, row, col, old_hex, new_hex], one per cell
        self._at = {}

    def set(self, table, r, c, new):
        """A cell written twice keeps its first original and its last value."""
        s = load(table)
        new = new if isinstance(new, bytes) else str(new).encode("latin-1")
        k = (table, r, c)
        if k in self._at:
            self.items[self._at[k]][4] = new.hex()
        elif s.d[r][c] != new:
            self._at[k] = len(self.items)
            self.items.append([table, r, c, s.d[r][c].hex(), new.hex()])
        s.d[r][c] = new


def require_blank(table, rows, allow_equal_to=None):
    s = load(table)
    for r in rows:
        if any(s.d[r]) and not (allow_equal_to and s.d[r] == allow_equal_to(r)):
            sys.exit(f"{table} row {r} is in use here ({s.d[r][0]!r}) -- refusing")


def references_book(item_no):
    """LIST_SELL / ITEM_DROP cells that already name type-10 item `item_no`."""
    code = str(10000 + item_no).encode()
    hits = []
    for t in ("LIST_SELL.STB", "ITEM_DROP.STB"):
        s = load(t)
        for r in range(s.rows):
            if code in s.d[r]:
                hits.append((t, r))
    return hits


# --------------------------------------------------------------- tree
def tree_nodes(base_of):
    raw = open(TREE_XML, encoding="utf-8", newline="").read()
    out = raw
    nodes = []
    for s in SKILLS:
        t, base = s["tree"], base_of[s["key"]]
        x, y = tree_offset(t["box"])
        node = f'\n         <SKILL INDEX="{base}" OFFSETX="{x}" OFFSETY="{y}"/>'
        if f'INDEX="{base}"' in out:
            continue
        if t["anchor"] not in out:
            sys.exit(f"tree: anchor {t['anchor']} not found -- refusing")
        out = out.replace(t["anchor"], t["anchor"] + node, 1)
        nodes.append(node)
    return raw, out, nodes


def page_path(name):
    hit = [f for f in os.listdir(RES_DIR) if f.upper() == name.upper()]
    if not hit:
        sys.exit(f"tree art {name} not found")
    return os.path.join(RES_DIR, hit[0])


def art_paint(im, from_box, box):
    """A plain bracket leg from the parent box's bottom centre down to the child box,
    and the 42x42 outline. Children sharing a parent share the stem and the bar."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    half = ART_BOX_SIZE // 2
    px, py = from_box[0] + half, from_box[1] + ART_BOX_SIZE - 1
    cx, cy = box[0] + half, box[1]
    bar = (py + cy) // 2
    d.line([(px, py), (px, bar)], fill=ART_LINE_RGBA)
    d.line([(px, bar), (cx, bar)], fill=ART_LINE_RGBA)
    d.line([(cx, bar), (cx, cy)], fill=ART_LINE_RGBA)
    d.rectangle([box[0], box[1], box[0] + ART_BOX_SIZE - 1, box[1] + ART_BOX_SIZE - 1],
                outline=ART_LINE_RGBA)


def art_has_box(path, box):
    from PIL import Image
    return Image.open(path).convert("RGBA").load()[box[0], box[1]][3] > 8


# --------------------------------------------------------------- appended rows
def truncate(table, n):
    """Drop the last n rows this script appended (blank row labels)."""
    s = load(table)
    tail = b"\x00\x00" * n
    if not s.header.endswith(tail):
        sys.exit(f"{table}: row labels are not the ones this script wrote -- refusing")
    s.header = s.header[:-len(tail)]
    s.d = s.d[:-n]
    s.rows -= n
    if s.rownames:
        del s.rownames[-n:]


def save(table):
    load(table).save(False, keep_backup=False)


# --------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    m = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else None

    if args.restore:
        return restore(m)
    if args.verify:
        return verify(m)
    if m:
        print(f"already imported at rows {m['skill_base']} -- nothing to do (--restore first)")
        return

    sk = load("LIST_SKILL.STB")
    st = load("LIST_STATUS.STB")
    sk8 = load("LIST_SKILL.STB", SRC_STB)
    skill_base = sk.rows
    base_of = {s["key"]: skill_base + k * RANKS for k, s in enumerate(SKILLS)}
    burn_row = st.rows
    ids = Ids(extra_fx=[BLAZE_FX])
    rows = skill_rows(base_of, sk8, ids, burn_row)
    cells = Cells()

    # motions (Voltage Crush) and the blaze effect row
    fm, tm = load("FILE_MOTION.STB"), load("TYPE_MOTION.STB")
    fm8, tm8 = load("FILE_MOTION.STB", SRC_STB), load("TYPE_MOTION.STB", SRC_STB)
    require_blank("FILE_MOTION.STB", FILE_MOTION_ROWS, lambda r: fm8.d[r][:fm.cols])
    require_blank("TYPE_MOTION.STB", TYPE_MOTION_ROWS)
    for r in FILE_MOTION_ROWS:
        for c in range(fm.cols):
            cells.set("FILE_MOTION.STB", r, c, fm8.d[r][c])
    for r in TYPE_MOTION_ROWS:
        want = tm8.d[r][0]
        assert want and all(x == want for x in tm8.d[r]), (r, tm8.d[r])
        for c in range(tm.cols):            # ours has one weapon column more than 668
            cells.set("TYPE_MOTION.STB", r, c, want)
    fe, fe8 = load("FILE_EFFECT.STB"), load("FILE_EFFECT.STB", SRC_STB)
    require_blank("FILE_EFFECT.STB", [BLAZE_FX])
    assert path_of(fe8, BLAZE_FX, 1) == "3DDATA\\EFFECT\\_BLAZE_01.EFT", fe8.d[BLAZE_FX]
    for c in range(fe.cols):
        cells.set("FILE_EFFECT.STB", BLAZE_FX, c, fe8.d[BLAZE_FX][c])

    # books and the shop
    ui = load("LIST_USEITEM.STB")
    require_blank("LIST_USEITEM.STB", BOOK_ROWS)
    for b in BOOK_ROWS:
        if references_book(b):
            sys.exit(f"book row {b} is referenced by {references_book(b)} -- refusing")
    for s, b in zip(SKILLS, BOOK_ROWS):
        for c in range(ui.cols):
            cells.set("LIST_USEITEM.STB", b, c, ui.d[BOOK_TEMPLATE][c])
        cells.set("LIST_USEITEM.STB", b, 0, s["name"])
        cells.set("LIST_USEITEM.STB", b, 20, base_of[s["key"]])
        cells.set("LIST_USEITEM.STB", b, 27, f"LUSE{b}")
    sell = load("LIST_SELL.STB")
    for c, b in zip(SHOP_COLS, BOOK_ROWS):
        if sell.d[SHOP_TAB][c].strip(b"0") :
            sys.exit(f"shop tab {SHOP_TAB} slot col {c} holds {sell.d[SHOP_TAB][c]!r} -- refusing")
        cells.set("LIST_SELL.STB", SHOP_TAB, c, 10000 + b)

    # files from 668
    files = [f"3DDATA/MOTION/AVATAR/{z}" for z in ZMOS]
    files += sorted(ro.effect_chain(BLAZE_FILES, SRC))
    files = [f for f in files if not os.path.isfile(ro.rel_path(DATA, f))]
    files = sorted({ro.norm(f): f for f in files}.values())

    raw_xml, new_xml, nodes = tree_nodes(base_of)

    print(f"skills at LIST_SKILL {skill_base}-{skill_base + RANKS * len(SKILLS) - 1}, "
          f"Burning at LIST_STATUS {burn_row}, books {BOOK_ROWS}")
    for s in SKILLS:
        b = base_of[s["key"]]
        print(f"\n  {s['name']} (rows {b}-{b + RANKS - 1}, weapon {s['weapon']}, "
              f"lv {s['level']}, needs {s['prereq'][0]} r{s['prereq'][1]})")
        print(f"    {'rank':>4}{'power':>7}{'cd s':>6}{'cost':>16}{'ratio':>7}{'dur':>5}{'scope':>7}{'SP':>5}")
        for n in range(RANKS):
            cost = " + ".join(f"{'HP' if a == AT_HP else 'MP'} {v[n]}" for a, v in s["cost"])
            r = rows[s["key"]][n]
            print(f"    {n + 1:>4}{s['power'][n]:>7}{s['reload'][n] * 0.2:>6.1f}{cost:>16}"
                  f"{s['success'][n]:>7}{s['duration'][n]:>5}{s['scope'][n]:>7}{i(r[3]):>5}")
    print(f"\n  {len(cells.items)} cells in place, files to copy: {files}")
    print(f"  tree nodes: {len(nodes)}")
    if args.dry_run:
        print("\ndry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    # art first (the only step that can fail on a missing dependency)
    art = []
    for s in SKILLS:
        t = s["tree"]
        p = page_path(t["page"])
        backup = os.path.join(OUT, os.path.basename(p) + ".orig")
        if not os.path.exists(backup):
            shutil.copyfile(p, backup)
        if not art_has_box(p, t["box"]):
            from PIL import Image
            im = Image.open(p).convert("RGBA")
            art_paint(im, t["from_box"], t["box"])
            im.save(p)
        art.append([p, backup])

    for f in files:
        d = ro.rel_path(DATA, f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(ro.rel_path(SRC, f), d)

    for t in {it[0] for it in cells.items}:
        save(t)

    sk.grow_to(skill_base + RANKS * len(SKILLS))
    for s in SKILLS:
        for n, r in enumerate(rows[s["key"]]):
            sk.d[base_of[s["key"]] + n] = r
    save("LIST_SKILL.STB")

    st.grow_to(burn_row + 1)
    st.d[burn_row] = list(st.d[ST_BURNING_SRC])
    st.d[burn_row][0] = b"Burning (Dance of Flames)"
    st.d[burn_row][5] = str(burn_row).encode()          # STATE_APPLY_ING_STB (self)
    st.d[burn_row][6] = str(BURN_PER_SECOND).encode()   # STATE_APPLY_ABILITY_VALUE
    st.d[burn_row][20] = f"LSTA{burn_row:03d}".encode()
    save("LIST_STATUS.STB")

    t = stl("LIST_SKILL_S.STL")
    for s in SKILLS:
        t.append(f"LSkill{base_of[s['key']]}", base_of[s["key"]], s["name"], s["desc"])
    t.save(False, keep_backup=False)
    t = stl("LIST_STATUS_S.STL")
    src_fields = [t.field(f"LSTA{ST_BURNING_SRC:03d}", n, 1) for n in range(t.nfields)]
    t.append(f"LSTA{burn_row:03d}", burn_row, *src_fields)
    t.save(False, keep_backup=False)
    t = stl("LIST_USEITEM_S.STL")
    for s, b in zip(SKILLS, BOOK_ROWS):
        t.append(f"LUSE{b}", b, s["name"], s["desc"])
    t.save(False, keep_backup=False)

    open(TREE_XML, "w", encoding="utf-8", newline="").write(new_xml)

    json.dump(dict(skill_base=skill_base, skill_rows=RANKS * len(SKILLS),
                   base_of=base_of, burn_row=burn_row, cells=cells.items,
                   files=files, tree_nodes=nodes, art=art), open(MANIFEST, "w"), indent=1)
    print("\ndone -- restart the game server, re-bake, and copy skilltree_soldier.xml loose "
          "into the launch folder")


def restore(m):
    if not m:
        sys.exit("no manifest -- nothing to restore")
    sk, st = load("LIST_SKILL.STB"), load("LIST_STATUS.STB")
    if sk.rows != m["skill_base"] + m["skill_rows"] or st.rows != m["burn_row"] + 1:
        sys.exit("rows were appended after this import -- refusing to truncate")
    truncate("LIST_SKILL.STB", m["skill_rows"])
    truncate("LIST_STATUS.STB", 1)
    save("LIST_SKILL.STB")
    save("LIST_STATUS.STB")
    for table in {c[0] for c in m["cells"]}:
        s = load(table)
        for t, r, c, old, _ in m["cells"]:
            if t == table:
                s.d[r][c] = bytes.fromhex(old)
        save(table)
    for name, keys in (("LIST_SKILL_S.STL", [f"LSkill{b}" for b in m["base_of"].values()]),
                       ("LIST_STATUS_S.STL", [f"LSTA{m['burn_row']:03d}"]),
                       ("LIST_USEITEM_S.STL", [f"LUSE{b}" for b in BOOK_ROWS])):
        t = stl(name)
        t.remove(keys)
        t.save(False, keep_backup=False)
    for f in m["files"]:
        p = ro.rel_path(DATA, f)
        if os.path.isfile(p):
            os.remove(p)
    raw = open(TREE_XML, encoding="utf-8", newline="").read()
    for node in m["tree_nodes"]:
        raw = raw.replace(node, "", 1)
    open(TREE_XML, "w", encoding="utf-8", newline="").write(raw)
    for p, backup in {tuple(a) for a in m["art"]}:
        if os.path.exists(backup):
            shutil.copyfile(backup, p)
    os.remove(MANIFEST)
    print("restored: skill rows, Burning row, cells, STL keys, files, tree nodes and art")


def verify(m):
    if not m:
        sys.exit("not imported")
    ok = True
    sk = load("LIST_SKILL.STB")
    for s in SKILLS:
        b = m["base_of"][s["key"]]
        for n in range(RANKS):
            if sk.d[b + n][0].decode("latin-1") != s["name"] or i(sk.d[b + n][2]) != n + 1:
                ok = False
                print(f"  row {b + n} is not {s['name']} rank {n + 1}")
    for t, r, c, _, new in m["cells"]:
        if load(t).d[r][c] != bytes.fromhex(new):
            ok = False
            print(f"  {t} {r}/{c} differs")
    for name, keys in (("LIST_SKILL_S.STL", [f"LSkill{b}" for b in m["base_of"].values()]),
                       ("LIST_STATUS_S.STL", [f"LSTA{m['burn_row']:03d}"]),
                       ("LIST_USEITEM_S.STL", [f"LUSE{b}" for b in BOOK_ROWS])):
        t = stl(name)
        for k in keys:
            if not t.has(k):
                ok = False
                print(f"  {name} lacks {k}")
    for f in m["files"]:
        if not os.path.isfile(ro.rel_path(DATA, f)):
            ok = False
            print(f"  missing {f}")
    raw = open(TREE_XML, encoding="utf-8", newline="").read()
    for node in m["tree_nodes"]:
        if node not in raw:
            ok = False
            print(f"  tree node missing: {node.strip()}")
    for s in SKILLS:
        if not art_has_box(page_path(s["tree"]["page"]), s["tree"]["box"]):
            ok = False
            print(f"  {s['name']}: box not painted")
    print("verify:", "ok" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
