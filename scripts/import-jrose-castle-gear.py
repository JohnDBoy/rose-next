"""Import Jrose's castle gear sets (74 parts) into LIST_PAT rows 512-585.

Survey (2026-10-14), the reasons this is safe:
  - Jrose's castle gear skeleton (PAT/CastleGear/CastleGear02/CastleGear02.ZMD)
    is byte-identical to ours, and every Jrose set is pet type 31 (LIST_PAT col
    16), so each part rides our skeleton and our walk/stand/attack clips
    (TYPE_MOTION 311-315; Jrose's own 311/317 are shuffled, ours are not, so
    TYPE_MOTION is not imported).
  - The parts' LIST_PAT.ZSC objects carry no dummy points and the table no
    effects: the gear bodies have no particles. Meshes are ZMS v8, max bone 27.
  - Only the three ranged arms need effects: their projectiles are LIST_EFFECT
    774/775/776 -> FILE_EFFECT 1947/1102/1103 (rocket fist, crossbow bolt,
    missile), each a mesh + motion + texture; the particles they use we already
    ship. All six rows are blank here and written in place at Jrose's index by
    import-monster-skills.py's `Plan`, as import-arrow-bullets.py does.
  - Jrose still wears the classic CG02 engine (its "Insect Engine" 1173 is a
    row on that mesh), so these sets are worn with our Fornef / Sheft / Luxem
    engines (131-133). Our server requires an engine (fuel, leg + engine speed).

What is written. Each part goes through `import-item.py --type pat --art-only
--target-row N --copy-icon`: the model and the icon come from Jrose, every stat
from one of OUR baseline rows (TEMPLATE below). Jrose's numbers are not wanted
-- its arms hit ~15x ours (4350-6714 ATK against 300-440).

Stats: the tier ladder (2026-10-14; `--restat` rewrites just these cells).
The user's brief: castle gear is the game's emblem, each set a little
stronger than the last, the top one able to do endgame content; the extra
arms accompany tiers. The sets are five models in colourways, ordered by look
(LEVEL below): Insect Mk I 90-110, Worm 120-130, Insect Mk II 140-155, Kaiser
165-190, Garter 200-240 -- a new model is a jump, a colourway a step. Every
stat is linear in the set's level between the level-90 and level-240 ends of
LADDER, on the classic rows' own bonus pattern (body DEF+RES, legs DEF+RES and
speed, arms DEF+CRITICAL), so the bottom tier sits just above classic gear.

Why these sizes, measured with balance-sim.py's formulas (median field
monster, synthetic player): mounted ATK is `3*level + CON + arms ATK`
(rose/common/mounted_stats.h) and the server refuses skills while riding, so
a castle gear fights with auto-attacks alone. Classic Punch Arms (300) already
kill 1.2-1.4x faster than a Champion using a skill on cooldown, but fall behind
at 240, where monster DEF outgrows a fixed arms ATK and the classic +170 DEF.
That model's synthetic player has no refines, gems or passives, and the first
ladder built on it (650 ATK at the top) hit for ~40% of a real level-240
character on foot -- arms ATK is now calibrated on in-game ATK readings
instead (FOOT_ATK). Defence was right: the monster hit for the floor (5). Mounted DEF is 80% of
the on-foot formula plus the parts' bonuses, and past about +400 bonus DEF the
level-240 median monster drops to the damage floor -- so the top tier stays
under it. Ranged extras get +10% ATK for their slower cannon swing (spd 12).

Every part carries the level requirement (31:level) and its PART_VER = level.
The version check (a part fits only a body of equal or higher version) lives
in the client's equip UI alone; the server enforces only the level, which is
why the requirement is on legs and arms too, unlike the classic rows. Classic
parts (versions 30-40) and the engines still fit every new body.

Arms animate from their template. LIST_PAT col 40 of the ARMS picks the column
of TYPE_MOTION every castle gear clip is read from (CObjCART::Get_MOTION): 0
punch, 1 drill, 2 sword wheel, 3 cannon, 4 spear -- the five retail arms, and
Jrose's arms reuse those same clips. So each arm clones the retail arm it looks
like, which brings that arm's range and sounds along with its motion set:
Punch Arms for fists and claws, Spear Arms for the Garter knuckles (spear and
shield) and Tank Defender (twin shields), Sword Wheel Arms for Gigant Axe,
Cannon Arms for the ranged ones, which also get their own bullet in col 55.
Jrose itself leaves col 40 blank on the Garter and the axe, so they swung
their spears and axe with the punch clips (first in-game test, 2026-10-14).

The projectile meshes are rewritten as ZMS pool 1. The engine morphs an effect
mesh and asserts `mesh->get_dynamic()` (zz_morpher.cpp) on a static one; Jrose
ships these three as pool 0, the only pool-0 meshes in our EFFECTMESH folder
(144 are pool 1), and the first shot of each popped the assert.

Gigant Axe gets its own copy of the shared knuckle mesh. The sword wheel clips
spin bone 16 (Bone34, the wheel hub: 3600 degrees over the idle clip) and
Retail Sword Wheel Arms skin nothing else to it; Jrose's hand_0602_cr puts the
right knuckle (80 vertices) on bone 16, so on the sword wheel set the knuckle
spun in place while the axe, on bone 15, swung correctly. The copy
(hand_0602_axe_cr.ZMS) binds those vertices to bone 15 (Bone33, 16's parent),
by rewriting the palette entry only. Tank Defender and Keraunos Shot keep the
original: the spear and cannon sets do not spin bone 16.
Names are rough translations of Jrose's Japanese; how players obtain the gear
is undecided, so nothing references these rows yet (spawn with /item 14:N).

Rows: the blank band 512-699 of LIST_PAT (no STB cells, no ZSC parts, no drop /
shop / recipe references), rather than appending past 709. LPAT600/601 are
stale STL keys in that band with no row, which is why the batch stops at 585.
Our ids 452-454 are taken by the Camo cart engines -- Jrose ids are not portable.

  python scripts/import-jrose-castle-gear.py --dry-run
  python scripts/import-jrose-castle-gear.py
  python scripts/import-jrose-castle-gear.py --verify
  python scripts/import-jrose-castle-gear.py --restat    # after editing LEVEL / LADDER
  python scripts/import-jrose-castle-gear.py --restore

Undo: every table and atlas it touches is saved whole in
build/jrose-castle-gear/orig/ with a manifest of the files it added; --restore
puts them back and deletes the added files. As with any whole-file backup,
restoring also reverts any later edit to those files made by another script.
The per-item `.import-<id>.bak` files import-item.py leaves beside each table
are moved to build/jrose-castle-gear/import-baks/ so the bake does not refuse.

Data: LIST_PAT.STB is read by the servers too -- restart them; then bake.
`data/` is gitignored, so this docstring is the only committed record of the change.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(REPO, "data")
JROSE = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
WORK = os.path.join(REPO, "build", "jrose-castle-gear")
ORIG = os.path.join(WORK, "orig")
MANIFEST = os.path.join(WORK, "manifest.json")

sys.path.insert(0, HERE)
from rosefmt import Stb, stl, tsi, zms  # noqa: E402
from rosefmt.zsc import Zsc  # noqa: E402

STB_DIR = os.path.join("3DDATA", "STB")
PAT_STB = os.path.join(STB_DIR, "LIST_PAT.STB")
PAT_STL = os.path.join(STB_DIR, "LIST_PAT_S.STL")
PAT_ZSC = os.path.join("3DDATA", "PAT", "LIST_PAT.ZSC")
RES = os.path.join("3DDATA", "CONTROL", "RES")
ITEM_TSI = os.path.join(RES, "ITEM1.TSI")
EFFECT_TABLES = (os.path.join(STB_DIR, "FILE_EFFECT.STB"), os.path.join(STB_DIR, "LIST_EFFECT.STB"))
# folders whose new files the import may create (models, effects, icon sheets)
WATCHED = (os.path.join("3DDATA", "PAT"), os.path.join("3DDATA", "EFFECT"), RES)

# LIST_PAT columns (rose/io/stb.h)
C_TYPE, C_PART_TYPE, C_MOTION, C_BULLET = 4, 16, 40, 55
PET_TYPE_CASTLE_GEAR = 31
PART_ITEM_TYPE = {"body": 512, "legs": 532, "arms": 552, "spear": 552, "wheel": 552, "ranged": 552}

# Our baseline rows every stat column is cloned from, with their names as a
# tripwire: a template that moved would silently re-stat the whole batch.
TEMPLATE = {
    "body": (31, "Wooden Stock Core"),
    "legs": (231, "Standard Legs"),
    "arms": (331, "Punch Arms"),
    "spear": (335, "Spear Arms"),
    "wheel": (333, "Sword Wheel Arms"),
    "ranged": (334, "Cannon Arms"),
}

# Jrose ranged arms -> the LIST_EFFECT bullet row they fire (Jrose's index,
# written at the same index here).
BULLETS = {1003: 774, 1005: 776, 1006: 775}
# Gigant Axe's knuckle, rebound off the spinning wheel-hub bone (docstring).
AXE_ROW, AXE_KNUCKLE_BONE = 1002, (16, 15)
AXE_KNUCKLE_SRC = rb"3Ddata\PAT\CastleGear\Extend_Arms\ARMS\hand_0602_cr.ZMS"
AXE_KNUCKLE = rb"3Ddata\PAT\CastleGear\Extend_Arms\ARMS\hand_0602_axe_cr.ZMS"
# Their meshes, which must be dynamic (pool 1) -- see the docstring.
EFFECT_MESHES = [os.path.join("3DDATA", "EFFECT", "EFFECTMESH", n) for n in
                 ("ROCKET_ARM_0602_CR.ZMS", "ARROW_0609_CR.ZMS", "MISSILE_0609_CR.ZMS")]

# (set, description, [(jrose row, part, name)]) -- parts in body, arms, legs order.
SETS = [
    ("Insect Gear", "A Castle Gear built in the image of a giant beetle.",
     [(453, "body", "Insect Gear Body"), (452, "arms", "Insect Gear Arms"),
      (454, "legs", "Insect Gear Legs")]),
    ("Insect Gear 2015", "A Castle Gear built in the image of a giant beetle.",
     [(928, "body", "Insect Gear 2015 Body"), (929, "arms", "Insect Gear 2015 Arms"),
      (930, "legs", "Insect Gear 2015 Legs")]),
    ("Black Kaiser", "A heavily armoured Kaiser-series Castle Gear.",
     [(939, "body", "Black Kaiser Core"), (940, "arms", "Black Kaiser Knuckle"),
      (941, "legs", "Black Kaiser Legs")]),
    ("Red Kaiser", "A heavily armoured Kaiser-series Castle Gear.",
     [(942, "body", "Red Kaiser Core"), (943, "arms", "Red Kaiser Knuckle"),
      (944, "legs", "Red Kaiser Legs")]),
    ("Blue Kaiser", "A heavily armoured Kaiser-series Castle Gear.",
     [(945, "body", "Blue Kaiser Core"), (946, "arms", "Blue Kaiser Knuckle"),
      (947, "legs", "Blue Kaiser Legs")]),
    ("Proto Kaiser Type-W", "A prototype of the Kaiser-series Castle Gear.",
     [(948, "body", "Proto Kaiser Core Type-W"), (949, "arms", "Proto Kaiser Knuckle Type-W"),
      (950, "legs", "Proto Kaiser Legs Type-W")]),
    ("Proto Kaiser Type-Y", "A prototype of the Kaiser-series Castle Gear.",
     [(951, "body", "Proto Kaiser Core Type-Y"), (952, "arms", "Proto Kaiser Knuckle Type-Y"),
      (953, "legs", "Proto Kaiser Legs Type-Y")]),
    ("Burning Insect", "A Castle Gear built in the image of a giant beetle.",
     [(1008, "body", "Burning Insect Body"), (1007, "arms", "Burning Insect Arms"),
      (1009, "legs", "Burning Insect Legs")]),
    ("Junon Garter", "A Castle Gear in the colours of the Junon Order.",
     [(1048, "body", "Junon Garter Breast"), (1049, "spear", "Junon Garter Knuckle"),
      (1050, "legs", "Junon Garter Legs")]),
    ("Junon Garter Red", "A Castle Gear in the colours of the Junon Order.",
     [(1051, "body", "Junon Garter Red Breast"), (1052, "spear", "Junon Garter Red Knuckle"),
      (1053, "legs", "Junon Garter Red Legs")]),
    ("Junon Garter Purple", "A Castle Gear in the colours of the Junon Order.",
     [(1054, "body", "Junon Garter Purple Breast"), (1055, "spear", "Junon Garter Purple Knuckle"),
      (1056, "legs", "Junon Garter Purple Legs")]),
    ("Cerulean Insect", "A Castle Gear built in the image of a giant beetle.",
     [(1075, "body", "Cerulean Insect Body"), (1074, "arms", "Cerulean Insect Arms"),
      (1076, "legs", "Cerulean Insect Legs")]),
    ("Union Garter Green", "A Castle Gear built for the Union.",
     [(1123, "body", "Union Garter Green Breast"), (1124, "spear", "Union Garter Green Knuckle"),
      (1125, "legs", "Union Garter Green Legs")]),
    ("Union Garter Blue", "A Castle Gear built for the Union.",
     [(1126, "body", "Union Garter Blue Breast"), (1127, "spear", "Union Garter Blue Knuckle"),
      (1128, "legs", "Union Garter Blue Legs")]),
    ("Union Garter Black", "A Castle Gear built for the Union.",
     [(1129, "body", "Union Garter Black Breast"), (1130, "spear", "Union Garter Black Knuckle"),
      (1131, "legs", "Union Garter Black Legs")]),
    ("Scarlet Insect", "A Castle Gear built in the image of a giant beetle.",
     [(1136, "body", "Scarlet Insect Body"), (1135, "arms", "Scarlet Insect Arms"),
      (1137, "legs", "Scarlet Insect Legs")]),
    ("Cobalt Insect", "A Castle Gear built in the image of a giant beetle.",
     [(1168, "body", "Cobalt Insect Body"), (1167, "arms", "Cobalt Insect Arms"),
      (1169, "legs", "Cobalt Insect Legs")]),
    ("Nero Insect", "A Castle Gear built in the image of a giant beetle.",
     [(1171, "body", "Nero Insect Body"), (1170, "arms", "Nero Insect Arms"),
      (1172, "legs", "Nero Insect Legs")]),
    ("Silk Worm", "A Castle Gear built in the image of a giant insect.",
     [(1188, "body", "Silk Worm Body"), (1187, "arms", "Silk Worm Arms"),
      (1189, "legs", "Silk Worm Legs")]),
    ("Reiban Volante", "A Castle Gear built in the image of a giant beetle.",
     [(1205, "body", "Reiban Volante Body"), (1204, "arms", "Reiban Volante Arms"),
      (1206, "legs", "Reiban Volante Legs")]),
    ("Milk Worm", "A Castle Gear built in the image of a giant insect.",
     [(1214, "body", "Milk Worm Body"), (1213, "arms", "Milk Worm Arms"),
      (1215, "legs", "Milk Worm Legs")]),
    ("Black Worm", "A Castle Gear built in the image of a giant insect.",
     [(1247, "body", "Black Worm Body"), (1246, "arms", "Black Worm Arms"),
      (1248, "legs", "Black Worm Legs")]),
    ("Ocean Insect", "A Castle Gear built in the image of a giant beetle.",
     [(1283, "body", "Ocean Insect Body"), (1282, "arms", "Ocean Insect Arms"),
      (1284, "legs", "Ocean Insect Legs")]),
    ("Extended Arms", None,
     [(1002, "wheel", "Gigant Axe", "Castle Gear arms that swing a giant axe."),
      (1003, "ranged", "Rocket Punch", "Castle Gear arms that launch their fist at the enemy."),
      (1004, "spear", "Tank Defender", "Castle Gear arms fitted with twin shields."),
      (1005, "ranged", "Missile Launcher", "Castle Gear arms that fire missiles."),
      (1006, "ranged", "Keraunos Shot", "Castle Gear arms with a giant crossbow.")]),
]
FIRST_ROW = 512

# The approved tier order: set -> required level (also its PART_VER).
LEVEL = {
    "Insect Gear": 90, "Insect Gear 2015": 95, "Burning Insect": 100,
    "Cobalt Insect": 105, "Ocean Insect": 110,
    "Silk Worm": 120, "Milk Worm": 125, "Black Worm": 130,
    "Cerulean Insect": 140, "Scarlet Insect": 145, "Nero Insect": 150, "Reiban Volante": 155,
    "Proto Kaiser Type-Y": 165, "Proto Kaiser Type-W": 170, "Red Kaiser": 175,
    "Blue Kaiser": 180, "Black Kaiser": 190,
    "Junon Garter": 200, "Junon Garter Red": 205, "Junon Garter Purple": 210,
    "Union Garter Green": 220, "Union Garter Blue": 230, "Union Garter Black": 240,
}
# Extra arms: jrose row -> (level, ATK, bonus slot 2 (ability, value), DEF added to slot 1).
# Each sits a little above its tier's set arms, with Jrose's flavour at our scale.
EXTRA_ARMS = {
    1006: (105, 1.10, (22, 40), 0),    # Keraunos Shot: ranged; AVOID (Jrose 22:85)
    1003: (135, 1.10, (20, 40), 0),    # Rocket Punch: ranged; HIT (Jrose 20:200)
    1004: (170, 0.95, (26, 25), 120),  # Tank Defender: lower ATK, DEF +120 (Jrose 19:350)
    1005: (195, 1.10, (38, 400), 0),   # Missile Launcher: ranged; MAX HP (Jrose 38:1200)
    1002: (220, 1.10, (26, 60), 0),    # Gigant Axe: slow wheel swing; CRITICAL (Jrose 26:150)
}
# Arms ATK, calibrated in game (2026-10-14). A level-240 character read ATK 2395
# on foot and 1719 mounted on the first ladder's 650 arms: mounted hit for ~40%
# of on-foot damage. Mounted ATK is 3*level + CON + arms + item ATK bonuses and
# ignores weapon, refines, gems and weapon passives, so it lags a geared
# character more the higher the level. On-foot ATK anchors: 2395 at 240 and
# ~900 at 140 (a refine-5 character read 962), exponential between them; the
# CON + bonus share of the mounted base is taken from the same character (349
# at 240) and scaled with level. Arms then make mounted ATK MOUNTED_OVER_FOOT
# times the on-foot value at the set's level (~25% more damage per hit), never
# under ARMS_FLOOR, which keeps the early sets above the classic arms (300-440):
# the floor rules up to ~175, where the mounted base alone is already strong.
FOOT_ATK = ((140, 900.0), (240, 2395.0))
MOUNT_CON_AT_240 = 349
MOUNTED_OVER_FOOT = 1.10
ARMS_FLOOR = (450, 2)          # ATK at level 90, + per level
# (level-90 value, level-240 value), linear in the level between them.
LADDER = {
    "arms_q": (50, 70), "arms_def": (30, 50), "arms_crit": (20, 40),
    "body_def": (100, 200), "body_res": (40, 100),
    "legs_def": (40, 80), "legs_res": (20, 40), "legs_speed": (44, 52),
}
AT_DEF, AT_RES, AT_CRITICAL, AT_LEVEL = 19, 21, 26, 31
C_QUALITY, C_PART_VER, C_NEED, C_BONUS1, C_BONUS2 = 8, 17, 21, 24, 27
C_MOV_SPD, C_ATK_POW = 33, 36


def ladder(key, level):
    lo, hi = LADDER[key]
    return lo + (hi - lo) * (level - 90) / 150.0


def arms_atk(level):
    """Set arms ATK at a level -- see FOOT_ATK."""
    import math
    (l1, a1), (l2, a2) = FOOT_ATK
    foot = a1 * math.exp(math.log(a2 / a1) * (level - l1) / (l2 - l1))
    base = 3 * level + MOUNT_CON_AT_240 * level / 240.0
    return max(ARMS_FLOOR[0] + ARMS_FLOOR[1] * (level - 90), MOUNTED_OVER_FOOT * foot - base)


def r5(v):
    return int(round(v / 5.0) * 5)


def stats_for(src, part, set_name):
    """{col: value} for one part -- the whole stat ladder lives here."""
    if src in EXTRA_ARMS:
        level, atk_mult, (bid, bval), extra_def = EXTRA_ARMS[src]
    else:
        level = LEVEL[set_name]
    out = {C_PART_VER: level, C_NEED: AT_LEVEL, C_NEED + 1: level}
    if part == "body":
        out.update({C_BONUS1: AT_DEF, C_BONUS1 + 1: r5(ladder("body_def", level)),
                    C_BONUS2: AT_RES, C_BONUS2 + 1: r5(ladder("body_res", level))})
    elif part == "legs":
        out.update({C_BONUS1: AT_DEF, C_BONUS1 + 1: r5(ladder("legs_def", level)),
                    C_BONUS2: AT_RES, C_BONUS2 + 1: r5(ladder("legs_res", level)),
                    C_MOV_SPD: int(round(ladder("legs_speed", level)))})
    else:
        out.update({C_QUALITY: int(round(ladder("arms_q", level))),
                    C_BONUS1: AT_DEF, C_BONUS1 + 1: r5(ladder("arms_def", level))})
        if src in EXTRA_ARMS:
            out.update({C_ATK_POW: r5(arms_atk(level) * atk_mult), C_BONUS1 + 1: out[C_BONUS1 + 1] + extra_def,
                        C_BONUS2: bid, C_BONUS2 + 1: bval})
        else:
            out.update({C_ATK_POW: r5(arms_atk(level)),
                        C_BONUS2: AT_CRITICAL, C_BONUS2 + 1: r5(ladder("arms_crit", level))})
    return out


def part_stats():
    """[(dest, name, {col: value})] for every imported part."""
    out, dest = [], FIRST_ROW
    for set_name, _desc, parts in SETS:
        for p in parts:
            out.append((dest, p[2], stats_for(p[0], p[1], set_name)))
            dest += 1
    return out


def apply_stats(root):
    pat = Stb(os.path.join(root, PAT_STB))
    for dest, name, cells in part_stats():
        if pat.s(dest, 0) != name:
            sys.exit("row %d is %r, expected %r -- not re-statting" % (dest, pat.s(dest, 0), name))
        for c, v in cells.items():
            pat.set(dest, c, str(v).encode())
    pat.write(os.path.join(root, PAT_STB))
    print("   stats applied to %d parts" % len(part_stats()))


def items():
    """(dest row, jrose row, part, name, description), in dest order."""
    out, dest = [], FIRST_ROW
    for _set, desc, parts in SETS:
        for p in parts:
            src, part, name = p[:3]
            out.append((dest, src, part, name, p[3] if len(p) > 3 else desc))
            dest += 1
    return out


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = saved
    return m


def bullet_plan(root):
    ms = load("import_monster_skills", "import-monster-skills.py")
    plan = ms.Plan(root, [])
    plan.src = JROSE
    plan.s = plan._tables("Jrose")
    for src, bullet in sorted(BULLETS.items()):
        plan._need_bullet(bullet, "Jrose arms %d" % src)
    # Walk assets only from the FILE_EFFECT rows we write (import-arrow-bullets.py:
    # a row we already have keeps our own .eft).
    new = {cells[1].decode("latin-1").lower() for cells in plan.effect_rows.values()}
    plan.efts = {(s, rel) for s, rel in plan.efts if rel.lower() in new}
    return ms, plan


def snapshot_files(root):
    rels = [PAT_STB, PAT_STL, PAT_ZSC, ITEM_TSI, *EFFECT_TABLES]
    rels += [os.path.join(RES, n) for n in os.listdir(os.path.join(root, RES))
             if n.lower().startswith("icon") and n.lower().endswith(".dds")]
    return rels


def listing(root):
    out = set()
    for w in WATCHED:
        for r, _ds, fs in os.walk(os.path.join(root, w)):
            for f in fs:
                out.add(os.path.relpath(os.path.join(r, f), root))
    return out


def preflight(root):
    problems = []
    pat = Stb(os.path.join(root, PAT_STB))
    jpat = Stb(os.path.join(JROSE, PAT_STB), encoding="cp932")
    zsc = Zsc(os.path.join(root, PAT_ZSC))
    keys, _langs = stl.read_table(os.path.join(root, PAT_STL))
    taken_keys = {k for k, _i in keys}
    for part, (row, name) in TEMPLATE.items():
        if pat.s(row, 0) != name:
            problems.append("template %s row %d is %r, expected %r" % (part, row, pat.s(row, 0), name))
    for dest, src, part, name, _desc in items():
        if any(pat.s(dest, c).strip() for c in range(pat.cols)):
            problems.append("row %d is occupied (%r)" % (dest, pat.s(dest, 0)))
        if zsc.objects[dest][1]:
            problems.append("LIST_PAT.ZSC object %d has parts" % dest)
        if ("LPAT%d" % dest).encode() in taken_keys:
            problems.append("STL key LPAT%d exists" % dest)
        if jpat.i(src, C_PART_TYPE) != PET_TYPE_CASTLE_GEAR or jpat.i(src, C_TYPE) != PART_ITEM_TYPE[part]:
            problems.append("Jrose row %d is type %s / pet type %s, not a castle gear %s"
                            % (src, jpat.s(src, C_TYPE), jpat.s(src, C_PART_TYPE), part))
        if (part == "ranged") != (src in BULLETS):
            problems.append("Jrose row %d: ranged part without a bullet or the reverse" % src)
    return problems


def run_imports(root, dry):
    for dest, src, part, name, desc in items():
        cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "pat",
               "--source", JROSE, "--source-row", str(src), "--art-only",
               "--template-row", str(TEMPLATE[part][0]), "--name", name, "--desc", desc,
               "--copy-icon", "--target-row", str(dest)]
        if dry:
            cmd.append("--dry-run")
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        tail = [l for l in r.stdout.splitlines() if l.startswith(("icon", "WARNING", "verified", "DRY"))]
        print("   %d <- Jrose %d  %-28s %s" % (dest, src, name, " | ".join(tail)))
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            return False
    return True


def set_bullets(root):
    pat = Stb(os.path.join(root, PAT_STB))
    for dest, src, part, _name, _desc in items():
        if part == "ranged":
            pat.set(dest, C_BULLET, str(BULLETS[src]).encode())
    pat.write(os.path.join(root, PAT_STB))


def axe_knuckle(root):
    """Write the rebound knuckle mesh and point Gigant Axe's object at it."""
    dest = next(d for d, src, *_ in items() if src == AXE_ROW)
    old, new = AXE_KNUCKLE_BONE
    m = zms.parse(os.path.join(root, AXE_KNUCKLE_SRC.decode()))
    m.bones = [new if b == old else b for b in m.bones]
    open(os.path.join(root, AXE_KNUCKLE.decode()), "wb").write(zms.build(m))
    path = os.path.join(root, PAT_ZSC)
    z = Zsc(path)
    if AXE_KNUCKLE.lower() not in [x.lower() for x in z.meshes]:
        open(path, "wb").write(z.to_bytes(extra_meshes=[AXE_KNUCKLE]))
        z = Zsc(path)
    lower = [x.lower() for x in z.meshes]
    src_i, new_i = lower.index(AXE_KNUCKLE_SRC.lower()), lower.index(AXE_KNUCKLE.lower())
    cyl, parts, dummies, bb = z.objects[dest]
    z.objects[dest] = (cyl, [(new_i if mid == src_i else mid, tid, pr) for mid, tid, pr in parts],
                       dummies, bb)
    open(path, "wb").write(z.rebuild())
    print("   %d Gigant Axe knuckle -> %s (bone %d -> %d)" % (dest, AXE_KNUCKLE.decode(), old, new))


def verify(root):
    bad = []
    pat = Stb(os.path.join(root, PAT_STB))
    zsc = Zsc(os.path.join(root, PAT_ZSC))
    keys, langs = stl.read_table(os.path.join(root, PAT_STL))
    names = {k: langs[1][i][0] for i, (k, _idx) in enumerate(keys)}
    sprites = sum(c for c, _ in tsi.read(os.path.join(root, ITEM_TSI), False)[1])
    fe = Stb(os.path.join(root, EFFECT_TABLES[0]))
    le = Stb(os.path.join(root, EFFECT_TABLES[1]))
    for dest, src, part, name, _desc in items():
        why = "%d %s" % (dest, name)
        if pat.s(dest, 0) != name:
            bad.append("%s: STB name %r" % (why, pat.s(dest, 0)))
        key = ("LPAT%d" % dest).encode()
        if pat.get(dest, pat.cols - 1) != key or names.get(key) != name.encode():
            bad.append("%s: STL key/name missing" % why)
        if pat.i(dest, C_PART_TYPE) != PET_TYPE_CASTLE_GEAR or pat.i(dest, C_TYPE) != PART_ITEM_TYPE[part]:
            bad.append("%s: not a castle gear %s" % (why, part))
        if not 0 <= pat.i(dest, 9) < sprites:
            bad.append("%s: icon %d outside the atlas (%d)" % (why, pat.i(dest, 9), sprites))
        parts = zsc.objects[dest][1]
        if not parts:
            bad.append("%s: no model" % why)
        for mid, tid, _props in parts:
            for rel in (zsc.meshes[mid], zsc.materials[tid][0]):
                rel = rel.decode("latin-1")
                if not os.path.isfile(os.path.join(root, rel)):
                    bad.append("%s: missing %s" % (why, rel))
        if pat.i(dest, C_MOTION) != pat.i(TEMPLATE[part][0], C_MOTION):
            bad.append("%s: motion set %d, template has %d"
                       % (why, pat.i(dest, C_MOTION), pat.i(TEMPLATE[part][0], C_MOTION)))
        if part == "ranged":
            b = pat.i(dest, C_BULLET)
            if b != BULLETS[src] or not le.s(b, 11).strip():
                bad.append("%s: bullet %d" % (why, b))
            else:
                for c in (9, 10, 11, 12):
                    i = le.i(b, c)
                    if i and not os.path.isfile(os.path.join(root, fe.s(i, 1))):
                        bad.append("%s: bullet %d effect %s missing" % (why, b, fe.s(i, 1)))
    axe = next(d for d, src, *_ in items() if src == AXE_ROW)
    for mid, _tid, _pr in zsc.objects[axe][1]:
        if AXE_KNUCKLE_BONE[0] in zms.parse(os.path.join(root, zsc.meshes[mid].decode())).bones:
            bad.append("%d Gigant Axe: %s is skinned to the spinning bone %d"
                       % (axe, zsc.meshes[mid].decode(), AXE_KNUCKLE_BONE[0]))
    for rel in EFFECT_MESHES:
        if zms.parse(os.path.join(root, rel)).pool != 1:
            bad.append("%s is not pool 1 (zz_morpher asserts)" % rel)
    for dest, name, cells in part_stats():
        wrong = [c for c, v in cells.items() if pat.i(dest, c) != v]
        if wrong:
            bad.append("%d %s: stat cols %s off the ladder" % (dest, name, wrong))
    for b in bad:
        print("   " + b)
    print("   %d parts, %s" % (len(items()), "all OK" if not bad else "%d problem(s)" % len(bad)))
    return not bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--restat", action="store_true",
                    help="rewrite only the stat cells of the imported rows from the ladder")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        for rel in man["added"]:
            p = os.path.join(root, rel)
            if os.path.isfile(p):
                os.remove(p)
        print("   removed %d added file(s)" % len(man["added"]))
        for rel in man["saved"]:
            shutil.copyfile(os.path.join(ORIG, rel), os.path.join(root, rel))
            print("   restored %s" % rel)
        os.remove(MANIFEST)
        return 0
    if a.restat:
        if not os.path.isfile(MANIFEST):
            sys.exit("nothing imported (no %s) -- run the import first" % MANIFEST)
        apply_stats(root)
        print("verify:")
        return 0 if verify(root) else 1
    if a.verify:
        print("verify:")
        return 0 if verify(root) else 1

    problems = preflight(root)
    ms, plan = bullet_plan(root)
    files = plan.files()
    print("bullets:")
    plan.report(files)
    problems += plan.problems
    if problems:
        print("\nABORT:")
        for p in problems:
            print("   " + p)
        return 1
    if os.path.isfile(MANIFEST):
        print("\nABORT: %s exists -- --restore first" % MANIFEST)
        return 1

    if a.dry_run:
        print("\nparts (dry run):")
        ok = run_imports(root, True)
        print("\ndry run: nothing written" if ok else "\ndry run FAILED")
        return 0 if ok else 1

    saved = snapshot_files(root)
    for rel in saved:
        os.makedirs(os.path.dirname(os.path.join(ORIG, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(root, rel), os.path.join(ORIG, rel))
    before = listing(root)
    json.dump({"saved": saved, "added": []}, open(MANIFEST, "w"), indent=1)

    for idx, cells in plan.effect_rows.items():
        for c, v in enumerate(cells):
            plan.o["FILE_EFFECT.STB"].set(idx, c, v)
    for idx, cells in plan.bullet_rows.items():
        for c, v in enumerate(cells):
            plan.o["LIST_EFFECT.STB"].set(idx, c, v)
    for src, rel, have in files:
        if not have:
            d = ms.oro.rel_path(root, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(ms.oro.rel_path(src, rel), d)
    for n in ("FILE_EFFECT.STB", "LIST_EFFECT.STB"):
        open(os.path.join(root, STB_DIR, n), "wb").write(plan.o[n].to_bytes())
    for rel in EFFECT_MESHES:
        m = zms.parse(os.path.join(root, rel))
        if m.pool != 1:
            m.pool = 1
            open(os.path.join(root, rel), "wb").write(zms.build(m))
            print("   %s -> ZMS pool 1" % rel)

    print("\nparts:")
    ok = run_imports(root, False)
    if ok:
        set_bullets(root)
        axe_knuckle(root)
        apply_stats(root)

    # import-item.py's per-item backups, and add-item-icon.py's, out of data/
    baks = os.path.join(WORK, "import-baks")
    os.makedirs(baks, exist_ok=True)
    for d in (os.path.join(root, STB_DIR), os.path.join(root, "3DDATA", "PAT"), os.path.join(root, RES)):
        for n in os.listdir(d):
            if ".import-" in n and n.endswith(".bak") or n.endswith(".bak-icons"):
                shutil.move(os.path.join(d, n), os.path.join(baks, n))

    added = sorted(listing(root) - before)
    json.dump({"saved": saved, "added": added}, open(MANIFEST, "w"), indent=1)
    print("\n%d file(s) added; undo with --restore" % len(added))
    if not ok:
        print("an import FAILED -- run --restore before retrying")
        return 1
    print("\nverify:")
    return 0 if verify(root) else 1


if __name__ == "__main__":
    sys.exit(main())
