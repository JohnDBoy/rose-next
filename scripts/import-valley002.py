#!/usr/bin/env python3
"""Import tsuki's Valley002 ("LZON151") as zone 151, Shadow Canyon, and its cave,
tsuki's Karkia ID09, as zone 156, Mysterious Cavern, joined by a gate.

Both come from the Chinese custom map series tsuki carries (its zone rows
147-164; the series numbers its maps M001-M028 in its warp points): the canyon
is the series' M014, the cave its M020. Scenery only: no NPC, no spawn, no sound
or effect object. The canyon's BGM is `BGM_AYXG` and the cave's `BGM_AYDX`
(neither in tsuki), its props `ANYING_*`: most likely 暗影峡谷 "Shadow Canyon" and
暗影洞穴 "Shadow Cave"; tsuki's STL has no text for either row.

Staged like scripts/import-cerberus.py; every stage is idempotent, --dry-run
previews, --verify re-derives the state, --selftest proves every writer
round-trips byte-identically before anything is touched:

    --stage 1   the canyon: the map folder (the two dead warp boxes removed, the
                morph objects re-pointed, one chunk's object lightmap index
                repaired), its decoration table LIST_DECO_AG.ZSC and art (the
                rope bridges' joints stitched), the new tile textures, morph
                rows 47/48, sky row 11, the zone row and its name.
    --stage 2   the cave: its map folder (a dead warp box removed, its floor's
                cracks and edges closed with invisible floors and walls),
                LIST_DECO_SG.ZSC and art, tiles, sky row 12,
                the zone row and its name; then **the gate**: WARP rows 194/195,
                an Eucar teleporter platform with its warp trigger on each side,
                and the arrival points beside them. Run after stage 1.

The canyon (surveyed 2026-10-23)
--------------------------------
  * **6 x 6 chunks, 29_29 to 34_34** (960 m square), a ~600 m floor inside a ring
    of cliffs up to 150 m (terrain -13 .. 151 m): a river with a waterfall pool
    in the north, two rope bridges, ruins, grass to the south-west and east, a
    windmill pocket in the south-east. **There is no way out on foot**, the map
    is reached by warp only.
  * 503 decorations (72 of LIST_DECO_AG's 250 objects), no building (LIST_CNST_FK,
    13 empty objects, is copied anyway: the editor lists a zone only if both ZSC
    cells are set, and the cave names it too), 7 morph objects, 202 invisible
    walls, 36 water lumps and 247 ocean rectangles. `.MOV` all zero (every cell
    walkable): nothing is spawned here yet, so it is left as shipped.
  * **The series' links** (every tsuki .ZON's `WARP-Mxxx` points, scanned): the
    canyon carries arrival points for M001 (on `start`, south centre), M012 (a
    trail into the east cliff, 35 m up; also the hub of tsuki's Lunar ID06-08),
    M022 (the windmill pocket, south-east) and M020 (the carved columns, south-west,
    world (4918, 5011) m). **M020 is Karkia ID09**, the cave. M001, M012 and M022
    are in no dump we own; their points are kept as ready places for a gate later.
  * **No WARP lump.** Two EVENT_OBJECT records (EVENT_OBJECT row 10, the invisible
    warp box, at (5278, 5403) and (5325, 5166) m) fire triggers `42-e-1` and
    `274-e-1`, which are in no QSD of ours or tsuki's: dead in tsuki too. Removed
    (dead_boxes); lump 12 has no lightmap entries, so nothing shifts.
  * **The economy lump is editor junk** (zone name "0", bgm "button1", all values
    0) in both maps. Kept: `CEconomy::Load` divides by none of them and turns a
    town counter <= 1 into a day, as for Cerberus Lair.

Lightmaps are tsuki's, kept
---------------------------
They look right in the editor, and once the audit reads their names (below) they
are clean everywhere but **the canyon's 34_33 object index** -- the windmill
pocket. One of four `tree004` placements in a row was deleted after the bake (15
entries, 14 records), so entries 8-15 belong to records 7-14 and the last one
points past the lump; two others lit part 1 of a one-part object. In our client
those are out-of-bounds reads and writes (`CMAP::LoadLightMapINFO` checks
nothing). lit_fixes drops entry 7 and renumbers the rest: which of the four trees
was deleted cannot be read from the files, so at worst one tree shows its
neighbour's lighting. `audit-lightmap-index.py` flagged 337 other entries over
the two maps as "baked for another mesh": its name parser, not the maps -- this
baker kept only the last two `_`/`-` pieces of each mesh name
(`VLY002_veg_tree002_A` -> `tree002_A`). Fixed there the same day (`same_mesh`);
no zone of ours changed. The cave's lightmaps are clean.

The canyon's tables
-------------------
  * **Zone 151**, as in tsuki: our table ended at 144, so it grew to 152 rows and
    any later map of the series can keep its number. Columns 0-26 are tsuki's
    except: the name; the BGM (Gorge of Silence's canyon track); sky 34 -> 11;
    camera 9 -> blank (col 21 indexes LIST_CAMERA, 6 rows here and 9 in tsuki:
    past both). Col 20 (zone type, the LIST_STEPSOUND column) stays tsuki's 4,
    Junon Polis's. Cols 27-35 are a Junon field's: party EXP 4/4, riding allowed,
    water collision 25. No revive zone: dying here revives on its own `restore`.
  * **Morph rows 42 / 63 -> 47 / 48.** tsuki's 42 is pokpo01 (the six waterfalls)
    and 63 fc02 (the windmill's sails); ours are a cart ability and blank. Our
    47-64 are free.
  * **Sky row 34 -> 11** (ours ends at 17, 11-16 blank). Its `MAPOBJ\\Sky\\day01.zms`
    is not our `JUNON\\Sky\\day01.zms` (different bytes), so it comes along.
  * **Tile textures**: 35 of the 45 are new (T1301-T1306, T210). T027/T033 we have
    in a better encoding (ours DXT5 with mips, tsuki DXT3 with none); copy_files
    never overwrites, so ours stay.
  * Effects: TWINKLE_01 / POKPOSU01 are byte-identical to ours; RAINBOW.EFT and
    its mesh, motion and texture are new (effect_chain).
  * **The bridges' joints are stitched** (deck_stitches, 2026-10-24). The four rope
    bridges (LIST_DECO_AG 32/33/35/36; the stone one, 244, is whole) are plank
    segments with open joints, 3-20 cm, a few 45-61 cm steps, and two faces missing
    from the mesh. The client's ground ray falls through a joint and the planks
    then hold the body inside the deck: first test, the north bridge, stuck 2 m
    under the planks. Each bridge gets one more part, a mesh of quads joining the
    facing open edges of its plank tops (plus the missing faces: STITCH_MAX_HOLE,
    STITCH_PATCHES), 2 cm under them, same collision. Measured with 1 cm vertical
    rays on 13 lines across each walking band: 1,276 / 567 / 1,357 / 2,264 open
    samples before, none after. **The part is invisible** (user, 2026-10-24: the
    filled joints looked out of place, the open cracks are part of the charm): it
    wears retail's invisible-wall material (INVISIBLE_MATERIAL, the Collision01
    panel's `chake01.dds`, alpha 0 everywhere under an alpha test), so it only
    stops the fall. It has no .lit entry.
  * **Not a data matter -- the client draws a 3x3 window of map cells** around the
    one you stand in (CTERRAIN::ReOrginazationPatch, a 48x48 patch pool), so past
    160-320 m the terrain is simply not there; a 960 m canyon with 150 m walls shows
    it where open fields hide it (first test: "the map stopped drawing" on the
    ridge at (5239, 5278), a cell corner). The invisible walls there are tsuki's.
  * **The minimap is halved** (minimap_bytes). The series draws 128 px a chunk
    (Valley002 1024 px, ID09 640, Haian, Yulin likewise); our client places the
    avatar at 64 plus a one-chunk border (CMinimapDLG::CalculateDisplayPos), so
    the first test showed the arrow far from the bridge it stood on. Cerberus
    Lair, also from tsuki, was already at 64. The canyon's picture names the four
    links in Chinese: SW 暗影洞穴一层 "Shadow Cave, floor 1" (ID09), S 梦幻城堡
    "Dream Castle" (M001), SE 纷争草原 "Plains of Strife" (M022), E 镜花雪原
    "Mirror-Flower Snowfield" (M012; 镜花 is the "illusion" of 镜花水月).
    **Repainted in English** (labels): "Mysterious Cavern" -- the cave's name, not
    the literal one -- "Dream Castle", "Plains of Strife", "Mirage Snowfield". The
    last three name places no dump has; the stars stay. The cave's has no label.

The cave (surveyed 2026-10-24)
------------------------------
  * **7 chunks in a plus, 31_31 to 33_32**: a tunnel from the cave mouth in the
    south-east of 32_33 north to a large chamber, a passage east to a round second
    chamber and a dead-end niche, M021's link (5325, 5140) -- a cave in no dump.
    234 decorations of LIST_DECO_SG (new to us, all 104 files it places in tsuki),
    19 invisible walls, 7 water lumps, no ocean, `.MOV` all zero, 10 new tiles
    (T207, T209). One dead warp box again (`407-e-1`, 32_32).
  * **The floor is objects, the terrain is flat at 0 m**: every HIM is 0 and the
    walking surfaces are LIST_DECO_SG floor meshes (collision 4) at 7-31 m, the
    walls collision 12. Three things follow. (1) **Anywhere a floor stops, you
    drop onto the hidden terrain, 7-31 m down in the dark**, and stay under the
    cave. Two checks, two fixes, all new LIST_DECO_SG objects in the invisible
    material, each placed once, last in its chunk's OBJECT lump (no .lit entry, no
    ordinal moves):
      - cracks between floor meshes (floor_seams: open-edge probes 3 cm out on the
        union of every floor; none inside any one mesh) -- the tip of a crevice in
        the north chamber (5209.5, 5316) and a 50 cm opening at the far niche
        (5312.5, 5139), each closed by floor_patch (a 2 cm raster, holes filled
        at their neighbours' height, 2 cm under it);
      - **walking off an edge** (Walker: a body flooding a 50 cm grid of the floors
        from the arrival point, blocked by every wall face and tsuki's invisible
        panels at knee and chest height, three rays a body apart). It found 105
        steps into the void, in five places: most floors run under their walls,
        but along a cliff in the west (5120-5140, 5210-5270), the north crevice
        (1-1.5 m wide, 15 m long) and three short stretches the floor stops 0.9-2.3 m
        short of the rock -- wider than the client's body sphere keeps you from a
        wall (40 cm ahead, 30 cm radius). void_fill closes a band that meets
        walls within VOID_FILL_REACH with invisible floor (you walk on to the rock,
        as the picture shows), and a band still open past it -- the cave's mouth
        (5166, 4990), the crevice's north end -- with an invisible **wall** on the
        floor's edge (collision 12, like the cave's): 10 floors and 2 walls. After
        them --verify walks 34,240 m2 with no void step, and the 7 seam probes left
        are all within SEAM_WALL_CLEAR of a wall. (2) Monsters follow
    the terrain alone, so the cave cannot host spawns as it is. (3) Arrival puts
    you on the *highest* surface at the spot (CObjCHAR::DropFromSky ->
    GetHeightTop -> getWorldObjectHeightInScene, any non-"not moveable" object):
    the cave's roof shell (collision 0) is higher than its floor, so you appear on
    the roof and drop through it onto the floor, as tsuki's players did.
  * **Zone 156**, tsuki's row: name, BGM `Sound\\BGM\\Dungeon_junon.ogg` (user's
    pick; Goblin Cave's), sky 30 -> our 12 (`MAPOBJ\\Sky\\deongen01.dds`, new), col
    20/21 Goblin Cave's (step sound 5, camera 3), cols 27-35 the canyon's. **Col 4
    "underground" stays 1**: `classUSER::Check_WarpPayment` refuses an underground
    zone to an account without the retail BATTLE / DUNGEON_ADV pay flags (a
    Japanese billing gate), but our accounts carry them -- Goblin Cave, Ulverick,
    the Forgotten Temple and seven more are underground and reached every day.

The gate (2026-10-24, the user's design)
----------------------------------------
Eucar's teleporter platform (EVENT_OBJECT.ZSC object 11, `warp_gate02.zms`, 7.4 m
across, 0.7 m high, its blue portal always on since fix-warp-gate-effect.py) on
each side, placed as a pure visual: trigger and script `EMPTY` (the client skips
an `EMPTY` script; an `EMPTY` trigger fails its quest check silently, as Eucar's
own does). Inside each, the walk-in trigger, a WARP lump record: the invisible
`SPECIAL_WARP_OBJECT` box (warp01.zms, 16.6 x 26.9 m at scale 1, its origin 7.8 m
from its centre) scaled to 9.5 m square and 3.6 m tall around the platform --
the platform is collision 12, solid, so the trigger reaches past it and you warp
as you walk up to it. Both are tilted to the plane fitted under them (the cave's
floor slopes ~0.2 m a metre). **Arrival points stand 14-15 m away**, clear of the
trigger: retail's are 8-180 m from the nearest gate.
  * Canyon: platform at (4919, 5004) m, by the ruined columns under the
    minimap's "Mysterious Cavern" star, clear of the fallen column (which ends at
    y 4997); WARP 194 -> zone 156 `WARP-M014-M020`. Arrivals from the cave on the
    canyon's `WARP-M020-M014`, moved to (4919, 5018).
  * Cave: platform at (5156, 5013) m, near the mouth, clear of the camp's crates
    and brazier; WARP 195 -> zone 151 `WARP-M020-M014`. Arrivals from the canyon on
    the cave's `WARP-M014-M020`, moved 15 m up the tunnel to (5146, 5024), and
    `start` / `restore` beside it (they sat 6 m from the new platform: a revive
    there could step into the trigger).
**A gate must never name a blank WARP row**: `Recv_cli_TELEPORT_REQ` calls that
hacking (`IS_HACKING`). So every gate piece belongs to stage 2, after its rows;
the canyon's files carry their gate only once row 194 is in place (gates_on), and
--verify checks whichever state is installed.

After running: `add-dds-mipmaps.py --dry-run --subdir <dir>` for the folders a
stage lists, and `--subdir <map folder> --lightmaps` (object lightmaps ship no
chain: 578 ms of slow creates in the canyon's first test), then
`audit-lightmap-index.py --zone 151 --zone 156`, `mapgen-roundtrip.py
--selftest`, rebake the VFS, restart the servers (they read LIST_ZONE, WARP and
the maps' event points). GM ways in: `/mm 151 521 503` (canyon start; 10 m units,
`Cheat_mm`), `/mm 156 515 502` (cave). Backups: build/valley002/.
"""
import argparse
import collections
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
import rosedata as oro  # noqa: E402  the shared data layer
from mapgen import prefab  # noqa: E402  the zone heightfield
from rosefmt import dds, ifo, lit, zms, zon  # noqa: E402
from rosefmt.zsc import TAG_PARENT, TAG_POS, TAG_ROT, TAG_SCALE, decode_props  # noqa: E402

# --------------------------------------------------------------------- config
DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\tsuki"
BUILD_DIR = os.path.join(ROOT, "build", "valley002")

ZONE_STB_REL = r"3DDATA\STB\LIST_ZONE.STB"
ZONE_STL_REL = r"3DDATA\STB\LIST_ZONE_S.STL"
ZONE_COPY_COLS = 27                 # 0..26 from tsuki; 27-35 are field_cols
ZONE_NAME_COL, ZONE_STL_COL = 0, 26
ZONE_MUSIC_DAY_COL, ZONE_MUSIC_NIGHT_COL = 5, 6
ZONE_SKY_COL, ZONE_TYPE_COL, ZONE_CAMERA_COL = 7, 20, 21
FIELD_COLS = {28: b"4", 29: b"4", 30: b"0", 34: b"0", 35: b"25"}     # Adventurer's Plain's
CNST_ZSC_REL = r"3DDATA\MAPOBJ\LIST_CNST_FK.ZSC"
MORPH_STB_REL = r"3DDATA\STB\LIST_MORPH_OBJECT.STB"
MORPH_FILE_COLS = (1, 2, 3)
SKY_STB_REL = r"3DDATA\STB\LIST_SKY.STB"
SKY_FILE_COLS = (0, 1, 2)
WARP_STB_REL = r"3DDATA\STB\WARP.STB"
EVENT_BOX = 10                      # EVENT_OBJECT.STB row 10, the invisible warp box
LIT_NAMES = ("OBJECTLIGHTMAPDATA.LIT", "BUILDINGLIGHTMAPDATA.LIT")
# lumps a source map must not carry: a surprise here means the source changed
EMPTY_LUMPS = (ifo.MOB, ifo.CNST, ifo.SOUND, ifo.EFFECT, ifo.REGEN, ifo.WARP)

CANYON = dict(
    key="canyon", zone=151, src_zone=151, name="Shadow Canyon", stl_key="LZON151",
    maps_rel=r"3DDATA\MAPS\JUNON\VALLEY002", zon="VALLEY002.ZON",
    # tsuki's editor dump of the .ZON, and a 1408x896 picture nothing references
    # (LIST_SKY 34 names day_valley002.dds, not this)
    skip={"valley002.zon.txt", "valley002.dds"},
    deco=r"3DDATA\MAPOBJ\LIST_DECO_AG.ZSC",
    music=rb"Sound\BGM\Canyon01_junon.ogg",          # Gorge of Silence's (zone 28)
    zone_type=None, camera=b"",                      # tsuki's 4; tsuki's 9 is past LIST_CAMERA
    morph_rows={42: 47, 63: 48},                     # pokpo01 waterfall, fc02 windmill
    sky_rows={34: 11},
    dead_boxes={"32_31.IFO": b"42-e-1", "33_32.IFO": b"274-e-1"},
    # (chunk, lit file) -> the entry baked for a record deleted after the bake,
    # the tga prefix it must carry and the entry count; later entries move down
    lit_fixes={("34_33", "OBJECTLIGHTMAPDATA.LIT"): (7, b"tree004_", 15)},
    # The four Chinese labels, repainted in English (user, 2026-10-23): the text's
    # box on tsuki's 1024 px picture (erased there), our name, and where it is drawn
    # on the 512 px one -- centred on the old text, or right-aligned before its star.
    labels=(
        ((297, 694, 407, 709), "Mysterious Cavern", "mm", None),   # 暗影洞穴一层 Shadow Cave 1F (ID09)
        ((517, 693, 587, 708), "Dream Castle", "mm", None),        # 梦幻城堡 (M001)
        ((707, 686, 779, 701), "Plains of Strife", "mm", None),    # 纷争草原 (M022)
        ((708, 565, 777, 580), "Mirage Snowfield", "rm", (388, 286)),   # 镜花雪原 (M012)
    ),
    bridges=(32, 33, 35, 36, 244),                   # xiaoqiao01/02, daqiao01/02, shiqiao01
    floor_patches=(),
    void_fill=False,                                 # terrain everywhere: nothing to fall to
    walk_from=None,
)
CAVE = dict(
    key="cave", zone=156, src_zone=156, name="Mysterious Cavern", stl_key="LZON156",
    maps_rel=r"3DDATA\MAPS\KARKIA\ID09", zon="ID09.ZON",
    skip={"id09.zon.txt"},
    deco=r"3DDATA\MAPOBJ\LIST_DECO_SG.ZSC",
    music=rb"Sound\BGM\Dungeon_junon.ogg",           # Goblin Cave's (user, 2026-10-24)
    zone_type=b"5", camera=b"3",                     # Goblin Cave's
    morph_rows={},
    sky_rows={30: 12},
    dead_boxes={"32_32.IFO": b"407-e-1"},
    lit_fixes={},
    labels=(),
    bridges=(),
    # the holes floor_seams found between the cave's floor meshes (world m); a patch
    # covers FLOOR_PATCH_HALF around each
    floor_patches=((5209.5, 5316.0), (5312.5, 5139.0)),
    # the gaps between a floor's edge and the wall behind it (void_fill), walked
    # from the arrival point
    void_fill=True,
    walk_from=(5146.0, 5024.0),
)
MAPS = (CANYON, CAVE)

# Walkable bridges (LIST_DECO_AG objects, collision 4) whose decks are plank
# segments with open joints, some ~3 cm wide: the client's ground ray falls
# through one and the planks then hold the body inside the deck (2026-10-23 test,
# daqiao01: stuck 2 m below the planks). Each gets its joints stitched shut by
# an extra part (deck_stitches).
STITCH_UP = 0.6                     # normal z of a deck top (the tops wind +z on all five)
STITCH_MAX_GAP = 70.0               # cm between the two open edges a stitch joins (daqiao02: 62)
STITCH_MIN_GAP = 0.2                # cm: closer than this they already touch
STITCH_MAX_DZ = 65.0                # cm of height across it (daqiao02 has a 45-61 cm step joint; rails sit ~1 m up)
STITCH_PARALLEL = 0.8               # |cos| between the two edges (xiaoqiao01 has a 30-degree wedge)
STITCH_SINK = 2.0                   # cm under the plank edges: never coplanar with a plank top
STITCH_MAX_HOLE = 1.0               # m2: triangle holes (three open edges) filled up to this;
                                    # tsuki's decks miss a face here and there (daqiao02: 0.74),
                                    # the 3-4 m2 loops are the deck ends, left alone
# Holes no rule above can see, as polygons in model cm, fanned from their first
# corner. daqiao02's wedge on the deck's centre line (0.6 m across, seen from above
# in the editor): its corners stop 7 and 24 cm short of the neighbouring planks'
# edge ends instead of sharing them, so it is no loop of open edges.
STITCH_PATCHES = {
    36: [[(1532, 251, 6691), (1652, 327, 6695), (1654, 320, 6682), (1509, 43, 6672), (1504, 67, 6683)]],
}
STITCH_SUFFIX = "_walk.zms"
# retail's invisible-wall material: LIST_DECO_SPECIAL object 2 (the IFO lump 11 panel)
INVISIBLE_MATERIAL = (r"3DDATA\SPECIAL\LIST_DECO_SPECIAL.ZSC", 2)

# The cave's floors: walkable parts (collision polygon, not "not moveable") with
# at least FLOOR_MIN_AREA of top surface -- the brazier and skull props are left out.
FLOOR_MIN_AREA = 50.0               # m2
SEAM_STEP = 20.0                    # cm between probes along a floor's open edges
SEAM_REACH = (10, 20, 35, 50, 70)   # cm out from an open edge where a floor may resume
SEAM_MAX_DZ = 40.0                  # cm: and only at about the same height
SEAM_WALL_CLEAR = 40.0              # cm: a probe this close to a wall is out of reach (the
                                    # client's body sphere, 30 cm, plus the probe's own 10 cm)
FLOOR_PATCH_HALF = 200.0            # cm, the raster box around a hole
FLOOR_PATCH_STEP = 2.0              # cm, its cells
FLOOR_PATCH_SUFFIX = "ID09_floor_patch_%d.zms"
# The walker (Walker, void_fill): a body on a grid over the floors.
WALK_STEP = 50.0                    # cm between cells
WALK_DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0))
WALK_STEP_UP = 60.0                 # cm a step may climb
WALK_RAYS = ((60.0, -30.0), (60.0, 0.0), (60.0, 30.0), (150.0, -30.0), (150.0, 0.0), (150.0, 30.0))
WALK_BODY = 30.0                    # cm past the next cell a blocker still stops the step
                                    # (AVATAR_BODY_FRONT_RADIUS: the client's body sphere)
WALK_BUCKET = 200.0                 # cm, the blockers' spatial hash
VOID_FILL_REACH = 300.0             # cm past a floor's edge a void band may run and be filled
FLOOR_COLLISION, WALL_COLLISION = 4, 12
WALL_BELOW, WALL_ABOVE = 100.0, 400.0   # cm under / over the floor an invisible wall runs
WALL_OVERLAP = 2.0                  # cm each wall quad runs past its cell boundary
# the root part properties of a placed floor: no transform, root, collision 4
FLOOR_PART_PROPS = bytes.fromhex("010c000000000000000000000000"
                                 "0210000080bf000000000000000000000000"
                                 "030c0000803f0000803f0000803f070200001d0204001f02000000")

# The gate. Each side: the platform (world m, x y), the WARP row it fires, and the
# arrival point other gates land on (name, world m). Arrival points the gate also
# moves: `moves`.
GATE_ROWS = {
    194: ("VALLEY002 -> ID09 (Shadow Canyon -> Mysterious Cavern)", 156, "WARP-M014-M020"),
    195: ("ID09 -> VALLEY002 (Mysterious Cavern -> Shadow Canyon)", 151, "WARP-M020-M014"),
}
GATES = {
    "canyon": dict(platform=(4919.0, 5004.0), warp=194,
                   moves={"WARP-M020-M014": (4919.0, 5018.0)}),
    "cave": dict(platform=(5156.0, 5013.0), warp=195,
                 moves={"WARP-M014-M020": (5146.0, 5024.0), "start": (5146.0, 5024.0),
                        "restore": (5145.0, 5023.0)}),
}
PLATFORM = 11                       # EVENT_OBJECT.ZSC object 11, Eucar's warp_gate02
PLATFORM_RADIUS = 370.0             # cm, its footprint (bbox +-3.7 m)
PLATFORM_SINK = 10.0                # cm under the fitted ground at its centre
PLATFORM_SCRIPT = b"EMPTY"          # trigger and con: a pure visual
WARP_BOX = (-827.0, -562.0, 838.0, 2128.0, 178.0)   # warp01.zms bbox cm (x0, y0, x1, y1, height)
WARP_SIZE, WARP_HEIGHT, WARP_BASE = 950.0, 356.0, 50.0   # cm: footprint, height, depth under the platform
MAX_TILT_DEG = 15.0

MINIMAP_NAME = "MINIMAP.DDS"
MINIMAP_PX_PER_CHUNK = 64           # cminimapdlg.cpp MINIMAP_RESOLUTION_PER_MAP; tsuki's series: 128
MINIMAP_FONT = (r"C:\Windows\Fonts\arialbd.ttf", 11)
MINIMAP_TEXT, MINIMAP_OUTLINE, MINIMAP_SHADOW = (255, 255, 255), (35, 28, 20), (20, 16, 12)
TEXCONV = os.path.join(ROOT, "thirdparty", "directxtex-2020.9.30", "texconv.exe")

CHUNK_CM, GRID_CM, ORIGIN_CM = 16000.0, 250.0, 520000.0

BAK_TRACKED = [ZONE_STB_REL, ZONE_STL_REL, MORPH_STB_REL, SKY_STB_REL, WARP_STB_REL]


# -------------------------------------------------------------------- helpers
def P(root, rel):
    return os.path.join(root, rel.replace("\\", "/"))


def ifo_files(folder):
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(".ifo"))


def write_if_changed(path, blob, dry):
    if os.path.isfile(path) and open(path, "rb").read() == blob:
        return False
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.isfile(path):
            keep = os.path.join(BUILD_DIR, "orig", os.path.relpath(path, ROOT))
            if not os.path.isfile(keep):
                os.makedirs(os.path.dirname(keep), exist_ok=True)
                shutil.copyfile(path, keep)
        with open(path, "wb") as fh:
            fh.write(blob)
    return True


def sweep_baks(ours):
    """Move the codecs' .bak files out of data/ -- pack.ps1 refuses to bake them."""
    moved = 0
    for rel in BAK_TRACKED:
        bak = P(ours, rel) + ".bak"
        if not os.path.isfile(bak):
            continue
        dest = os.path.join(BUILD_DIR, "bak", rel.replace("\\", "/") + ".bak")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.isfile(dest):
            os.remove(bak)             # keep the oldest pre-import copy
        else:
            shutil.move(bak, dest)
        moved += 1
    if moved:
        print(f"moved {moved} .bak file(s) to {os.path.join(BUILD_DIR, 'bak')}")


def txt(cell):
    return cell.decode("latin-1").strip()


def chunk_of(x_cm, y_cm):
    """(ifo name, (map_x, map_y)) of a zone-centre position in cm."""
    wx, wy = x_cm + ORIGIN_CM, y_cm + ORIGIN_CM
    cx, cy = int(wx // CHUNK_CM), int(wy // CHUNK_CM)
    lx, ly = wx - cx * CHUNK_CM, wy - cy * CHUNK_CM
    return f"{cx}_{64 - cy}.IFO", (int(lx // GRID_CM), 63 - int(ly // GRID_CM))


def to_local(m):
    """World metres -> zone-centre cm."""
    return (m - ORIGIN_CM / 100.0) * 100.0


def f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def tri_cover(tris, pts):
    """Per point, the highest z of the triangles covering it in plan (NaN if none)."""
    out = np.full(len(pts), np.nan)
    if not len(tris):
        return out
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    nn = np.cross(b - a, c - a)
    ok = np.abs(nn[:, 2]) > 1e-9
    a, b, c, nn = a[ok], b[ok], c[ok], nn[ok]
    if not len(a):
        return out
    for s in range(0, len(pts), 512):
        p = pts[s:s + 512][:, None, :]
        d1 = (b[:, 0] - a[:, 0]) * (p[..., 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (p[..., 0] - a[:, 0])
        d2 = (c[:, 0] - b[:, 0]) * (p[..., 1] - b[:, 1]) - (c[:, 1] - b[:, 1]) * (p[..., 0] - b[:, 0])
        d3 = (a[:, 0] - c[:, 0]) * (p[..., 1] - c[:, 1]) - (a[:, 1] - c[:, 1]) * (p[..., 0] - c[:, 0])
        ins = ((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))
        z = a[:, 2] - (nn[:, 0] * (p[..., 0] - a[:, 0]) + nn[:, 1] * (p[..., 1] - a[:, 1])) / nn[:, 2]
        zz = np.where(ins, z, -np.inf).max(1)
        out[s:s + 512] = np.where(np.isfinite(zz), zz, np.nan)
    return out


# --------------------------------------------------------------- map files
def map_files(spec, s_map):
    """(sub, name) of every source map file we ship, in walk order."""
    for base, _, names in os.walk(s_map):
        sub = os.path.relpath(base, s_map)
        for name in sorted(names):
            if name.lower() not in spec["skip"]:
                yield sub, name


def map_ifo(spec, src, name, gates):
    """A tsuki .IFO as we ship it: morphs re-pointed, the dead box gone, the floor
    patches appended to OBJECT and, with `gates`, the gate in EVENT_OBJECT/WARP."""
    s_map = P(src, spec["maps_rel"])
    raw = open(os.path.join(s_map, name), "rb").read()
    m = ifo.parse(raw)
    for lt in EMPTY_LUMPS:
        if m.lump(lt):
            raise SystemExit(f"{name}: unexpected records in lump {ifo.LUMP_NAMES[lt]}")
    changed = False
    for r in m.lump(ifo.MORPH) or []:
        if r.obj_id not in spec["morph_rows"]:
            raise SystemExit(f"{name}: morph object {r.obj_id} has no mapping")
        r.obj_id = spec["morph_rows"][r.obj_id]
        changed = True
    boxes = m.lump(ifo.EVENT_OBJECT)
    dead = spec["dead_boxes"].get(name.upper())
    if boxes:
        if [(b.obj_id, b.trigger) for b in boxes] != [(EVENT_BOX, dead)]:
            raise SystemExit(f"{name}: event objects {[(b.obj_id, b.trigger) for b in boxes]}, "
                             f"expected one dead warp box")
        boxes.clear()
        changed = True
    elif dead:
        raise SystemExit(f"{name}: the dead warp box is missing from the source")
    adds = dict(patch_records(spec, src).get(name.upper(), {}))
    if gates:
        for lump, recs in gate_records(spec["key"], src).get(name.upper(), {}).items():
            adds[lump] = adds.get(lump, []) + recs
    for lump, recs in adds.items():
        if m.lump(lump) is None:
            raise SystemExit(f"{name}: no {ifo.LUMP_NAMES[lump]} lump to append to")
        m.lump(lump).extend(recs)
        changed = True
    return ifo.build(m) if changed else raw


def map_lit(spec, s_map, chunk, lit_name):
    """A chunk's .lit as we ship it: lit_fixes applied, every other one verbatim."""
    raw = open(os.path.join(s_map, chunk, "LIGHTMAP", lit_name), "rb").read()
    fix = spec["lit_fixes"].get((chunk, lit_name.upper()))
    if fix is None:
        return raw
    drop, prefix, count = fix
    L = lit.parse_lit(raw)
    if len(L.objects) != count or L.objects[drop - 1].obj_index != drop \
            or not all(p.tga_name.startswith(prefix) and b"_Object_%d_" % drop in p.tga_name
                       for p in L.objects[drop - 1].parts):
        raise SystemExit(f"{chunk}/{lit_name}: not the bake lit_fixes was written for")
    del L.objects[drop - 1]
    for o in L.objects:
        if o.obj_index > drop:
            o.obj_index -= 1
    return lit.build_lit(L)


def map_zon(spec, src, gates):
    """The map's .ZON, with `gates` its arrival points moved (GATES[...]["moves"])."""
    raw = open(P(src, spec["maps_rel"] + "\\" + spec["zon"]), "rb").read()
    if not gates:
        return raw
    z = zon.parse(raw)
    events = z.lump(zon.EVENTS)
    for name, (x, y) in GATES[spec["key"]]["moves"].items():
        hit = [e for e in events if e.name == name.encode()]
        if len(hit) != 1:
            raise SystemExit(f"{spec['zon']}: {len(hit)} event points named {name}")
        hit[0].x, hit[0].y = f32(to_local(x)), f32(to_local(y))
        hit[0].z = f32(ground_at(spec, src, to_local(x), to_local(y)))
    return zon.build(z)


# ------------------------------------------------------------ surfaces
_CACHE = {}


def walk_tops(spec, src, min_area=0.0):
    """Every placed walkable top triangle of a map (collision polygon, not "not
    moveable", normal z >= STITCH_UP), zone-centre cm; with `min_area`, only parts
    whose top surface reaches it (m2)."""
    key = ("tops", spec["key"], src, min_area)
    if key in _CACHE:
        return _CACHE[key]
    z = oro.Zsc(P(src, spec["deco"]))
    out = []
    for name in ifo_files(P(src, spec["maps_rel"])):
        for r in ifo.parse(open(os.path.join(P(src, spec["maps_rel"]), name), "rb").read()).lump(ifo.OBJECT) or []:
            for mi, ma, props in z.objects[r.obj_id][1]:
                level = decode_props(props)["collision"]
                if not level & 4 or level & 8:
                    continue
                t = mesh_tris(src, z.meshes[mi].decode("latin-1"))
                n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
                area = np.linalg.norm(n, axis=1) / 2
                up = (n[:, 2] / (2 * area + 1e-9)) >= STITCH_UP
                if area[up].sum() / 1e4 < max(min_area, 1e-9):
                    continue
                out.append(place(t[up], r))
    _CACHE[key] = np.concatenate(out) if out else np.zeros((0, 3, 3))
    return _CACHE[key]


def mesh_tris(src, rel):
    key = ("mesh", src, rel)
    if key not in _CACHE:
        _CACHE[key] = np.asarray(zms.parse(open(P(src, rel), "rb").read()).triangles_cm(), float)
    return _CACHE[key]


def place(t, r):
    """Model-space triangles placed by an IFO record (scale, rotation, position)."""
    x, y, z, w = r.rot
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    return (t * np.array(r.scale)) @ R.T + np.array(r.pos)


def ground_at(spec, src, x, y):
    """The ground a player stands on at a zone-centre cm point: the highest
    walkable object top, else the terrain."""
    h = tri_cover(walk_tops(spec, src), np.array([[x, y]]))[0]
    if h == h:
        return float(h)
    key = ("field", spec["key"], src)
    if key not in _CACHE:
        _CACHE[key] = prefab._zone_field(P(src, spec["maps_rel"]))
    field, (x0, y0) = _CACHE[key]
    return float(prefab._height(field, x0, y0, x + ORIGIN_CM, y + ORIGIN_CM))


# ------------------------------------------------------- bridges (canyon)
def deck_stitches(tris):
    """Quads closing a deck's open joints, as (n, 4, 3) cm, model space.

    The deck is the mesh's faces whose normal z >= STITCH_UP -- the tops: counting
    the undersides too paired each plank's top edge with its own bottom edge 1-2 cm
    away in plan and left the joint beside it open. Its open edges are
    those only one deck face uses (vertices matched to 1 mm). Each open edge is
    joined to the open edges across a gap of STITCH_MIN_GAP..STITCH_MAX_GAP that
    run alongside it (|cos| >= STITCH_PARALLEL, overlapping it, within
    STITCH_MAX_DZ of its height there): always the nearest, and any other whose
    midpoint faces open air (no plank between them). A stitch lies on the plank edges,
    STITCH_SINK under them, so it is at deck level; a raster fill missed the 3 cm
    joints (first try, 2026-10-23) and a sheet under the deck sank 60 cm where a
    beam ran beneath a joint."""
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nz = n[:, 2] / (np.linalg.norm(n, axis=1) + 1e-9)
    tops = tris[nz >= STITCH_UP]
    count, seg = open_edges(tops)
    edges = np.array([seg[k] for k, c in count.items() if c == 1])
    if not len(edges):
        return np.zeros((0, 4, 3))
    mid = edges.mean(1)
    d = edges[:, 1, :2] - edges[:, 0, :2]
    length = np.linalg.norm(d, axis=1)
    u = d / (length[:, None] + 1e-9)
    quads, done = [], set()
    for i in np.nonzero(length >= 1.0)[0]:
        rel = mid[:, :2] - edges[i, 0, :2]
        along = rel @ u[i]
        perp = np.abs(rel[:, 0] * u[i, 1] - rel[:, 1] * u[i, 0])
        # height of edge i where it faces each candidate's midpoint: the edges run
        # metres along a sagging deck, so their midpoints' heights do not compare
        t = np.clip(along / max(length[i], 1e-9), 0.0, 1.0)
        z_here = edges[i, 0, 2] + (edges[i, 1, 2] - edges[i, 0, 2]) * t
        ok = ((np.abs(u @ u[i]) >= STITCH_PARALLEL) & (perp > STITCH_MIN_GAP) & (perp <= STITCH_MAX_GAP)
              & (along > -10) & (along < length[i] + 10) & (length >= 1.0)
              & (np.abs(mid[:, 2] - z_here) <= STITCH_MAX_DZ))
        ok[i] = False
        if not ok.any():
            continue
        # the nearest always; any other only if no plank lies between (a long
        # edge faces several short planks along its length, one per joint)
        first = np.nonzero(ok)[0][np.argmin(perp[ok])]
        picks = [first]
        for j in np.nonzero(ok)[0]:
            if j == first:
                continue
            foot = edges[i, 0, :2] + u[i] * np.clip(along[j], 0, length[i])
            if not plan_covered(tops, (foot + mid[j, :2]) / 2):
                picks.append(j)
        for j in picks:
            if (min(i, j), max(i, j)) in done:
                continue
            done.add((min(i, j), max(i, j)))
            a0, a1 = edges[i]
            b0, b1 = edges[j]
            if np.dot(b1[:2] - b0[:2], u[i]) < 0:
                b0, b1 = b1, b0
            quads.append((a0, a1, b1, b0))
    # a missing face: three open edges closing a loop; filled as a quad whose
    # last corner repeats its third
    adj = {}
    for (ka, kb), c in count.items():
        if c == 1:
            adj.setdefault(ka, set()).add(kb)
            adj.setdefault(kb, set()).add(ka)
    holes = set()
    for a in adj:
        for b in adj[a]:
            for c in adj[a] & adj.get(b, set()):
                holes.add(tuple(sorted((a, b, c))))
    for hole in sorted(holes):
        p = np.array(hole)
        if 0.5 * np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])) <= STITCH_MAX_HOLE * 1e4:
            quads.append((p[0], p[1], p[2], p[2]))
    out = np.array(quads) if quads else np.zeros((0, 4, 3))
    out[..., 2] -= STITCH_SINK
    return out


def open_edges(tops):
    """({edge key: use count}, {edge key: (a, b)}) over triangles, vertices at 1 mm."""
    count, seg = {}, {}
    for t in tops:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ka, kb = tuple(np.round(a, 1)), tuple(np.round(b, 1))
            k = (min(ka, kb), max(ka, kb))
            count[k] = count.get(k, 0) + 1
            seg[k] = (a, b)
    return count, seg


def plan_covered(tris, p):
    """Whether any triangle covers point p (x, y) in plan."""
    a, b, c = tris[:, 0, :2], tris[:, 1, :2], tris[:, 2, :2]
    d1 = (b[:, 0] - a[:, 0]) * (p[1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (p[0] - a[:, 0])
    d2 = (c[:, 0] - b[:, 0]) * (p[1] - b[:, 1]) - (c[:, 1] - b[:, 1]) * (p[0] - b[:, 0])
    d3 = (a[:, 0] - c[:, 0]) * (p[1] - c[:, 1]) - (a[:, 1] - c[:, 1]) * (p[0] - c[:, 0])
    return bool((((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))).any())


def quad_mesh(quads):
    """Quads as a ZMS: both windings (whatever the engine culls, the ray meets
    one), normals up, uv0 the plan position (1 m a repeat)."""
    pos = (quads.reshape(-1, 3) / 100.0)            # ZMS v8 stores metres
    faces = []
    for q in range(len(quads)):
        v = 4 * q
        faces += [(v, v + 1, v + 2), (v, v + 2, v + 3), (v, v + 2, v + 1), (v, v + 3, v + 2)]
    return zms.rigid_v8(pos, np.tile((0.0, 0.0, 1.0), (len(pos), 1)), pos[:, :2], faces)


def child_props(props, parent):
    """A part's property list with an identity transform (position 0, rotation
    w=1, scale 1) and `parent` as its parent (stored 1-based), everything else
    (collision, range set) kept: the same space as the parent's mesh."""
    out, o, has_parent = bytearray(), 0, False
    while o < len(props) and props[o]:
        tag, ln = props[o], props[o + 1]
        val = bytes(props[o + 2:o + 2 + ln])
        if tag == TAG_POS:
            val = struct.pack("<3f", 0.0, 0.0, 0.0)
        elif tag == TAG_ROT:
            val = struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)          # w, x, y, z
        elif tag == TAG_SCALE:
            val = struct.pack("<3f", 1.0, 1.0, 1.0)
        elif tag == TAG_PARENT:
            val, has_parent = struct.pack("<h", parent + 1), True
        out += bytes((tag, len(val))) + val
        o += 2 + ln
    if not has_parent:
        out += bytes((TAG_PARENT, 2)) + struct.pack("<h", parent + 1)
    return bytes(out) + b"\0"


def invisible_material(src):
    special = oro.Zsc(P(src, INVISIBLE_MATERIAL[0]))
    mat = special.materials[special.objects[INVISIBLE_MATERIAL[1]][1][0][1]]
    if not mat[0].lower().endswith(b"chake01.dds"):
        raise SystemExit(f"{INVISIBLE_MATERIAL[0]} object {INVISIBLE_MATERIAL[1]} is not the invisible wall")
    return mat


# ---------------------------------------------------- floor holes (cave)
def floor_seams(tops):
    """Holes between floors: [(x, y) cm] where, just past a floor's open edge,
    nothing covers the ground but a floor resumes SEAM_REACH further on at about
    the same height. Probes every SEAM_STEP along every open edge of the union of
    the floors, both sides: the cave's floors are separate meshes, and a per-mesh
    check cannot see the joints between them."""
    count, seg = open_edges(tops)
    probes, meta = [], []
    for k, c in count.items():
        if c != 1:
            continue
        p, q = seg[k]
        d = q[:2] - p[:2]
        L = float(np.linalg.norm(d))
        if L < 5:
            continue
        u = d / L
        nrm = np.array([-u[1], u[0]])
        for t in np.arange(10.0, L - 9, SEAM_STEP):
            base = p[:2] + u * t
            zb = p[2] + (q[2] - p[2]) * t / L
            for s in (-1, 1):
                probes.append(base + nrm * s * 3)
                meta.append((base, zb, nrm * s))
    if not probes:
        return []
    near = tri_cover(tops, np.array(probes))
    far, owner = [], []
    for k in np.nonzero(np.isnan(near))[0]:
        base, zb, n = meta[k]
        for dd in SEAM_REACH:
            far.append(base + n * dd)
            owner.append((k, zb))
    zf = tri_cover(tops, np.array(far)) if far else []
    found, seen = [], set()
    for (k, zb), pt, z in zip(owner, far, zf):
        if k in seen or z != z or abs(z - zb) > SEAM_MAX_DZ:
            continue
        seen.add(k)
        found.append((float(pt[0]), float(pt[1])))
    return found


def floor_patch(tops, cx, cy):
    """Quads (n, 4, 3) zone-centre cm closing the holes in the floors around
    (cx, cy): a FLOOR_PATCH_STEP raster of the highest floor top in a box of
    FLOOR_PATCH_HALF, each open cell bounded within SEAM_REACH[-1] on both sides
    (along x or y) by floor within SEAM_MAX_DZ of each other filled at their
    interpolated height, STITCH_SINK under it."""
    st, half = FLOOR_PATCH_STEP, FLOOR_PATCH_HALF
    xs = np.arange(cx - half, cx + half + st / 2, st)
    ys = np.arange(cy - half, cy + half + st / 2, st)
    box = tops[(tops[:, :, 0].max(1) >= xs[0]) & (tops[:, :, 0].min(1) <= xs[-1])
               & (tops[:, :, 1].max(1) >= ys[0]) & (tops[:, :, 1].min(1) <= ys[-1])]
    gx, gy = np.meshgrid(xs, ys)
    top = tri_cover(box, np.stack([gx.ravel(), gy.ravel()], 1)).reshape(gx.shape)
    k = int(SEAM_REACH[-1] / st)
    fill = {}
    for grid, flip in ((top, False), (top.T, True)):
        for j, row in enumerate(grid):
            have = np.nonzero(~np.isnan(row))[0]
            for a, b in zip(have[:-1], have[1:]):
                if 1 < b - a <= k + 1 and abs(row[a] - row[b]) <= SEAM_MAX_DZ:
                    for i in range(a + 1, b):
                        z = row[a] + (row[b] - row[a]) * (i - a) / (b - a)
                        key = (i, j) if flip else (j, i)
                        fill[key] = min(fill.get(key, z), z)
    h = st / 2 + 0.3                                # a hair of overlap, no slivers
    quads = []
    for (j, i), z in sorted(fill.items()):
        x, y, zz = xs[i], ys[j], z - STITCH_SINK
        quads.append(((x - h, y - h, zz), (x + h, y - h, zz), (x + h, y + h, zz), (x - h, y + h, zz)))
    return np.array(quads) if quads else np.zeros((0, 4, 3))


def blockers(spec, src):
    """Every face that stops a walking body (zone-centre cm): the steep faces of
    the colliding objects, and the invisible walls (IFO lump 11, each an instance
    of LIST_DECO_SPECIAL object 2, SPECIAL_COLLISION_OBJECT)."""
    key = ("blockers", spec["key"], src)
    if key in _CACHE:
        return _CACHE[key]
    z = oro.Zsc(P(src, spec["deco"]))
    special = oro.Zsc(P(src, INVISIBLE_MATERIAL[0]))
    panel = mesh_tris(src, special.meshes[special.objects[2][1][0][0]].decode("latin-1"))
    out = []
    for name in ifo_files(P(src, spec["maps_rel"])):
        m = ifo.parse(open(os.path.join(P(src, spec["maps_rel"]), name), "rb").read())
        for r in m.lump(ifo.OBJECT) or []:
            for mi, ma, props in z.objects[r.obj_id][1]:
                if not decode_props(props)["collision"]:
                    continue
                t = place(mesh_tris(src, z.meshes[mi].decode("latin-1")), r)
                n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
                out.append(t[np.abs(n[:, 2] / (np.linalg.norm(n, axis=1) + 1e-9)) < STITCH_UP])
        out += [place(panel, r) for r in m.lump(ifo.COLLISION) or []]
    _CACHE[key] = np.concatenate(out) if out else np.zeros((0, 3, 3))
    return _CACHE[key]


def grid_top(tris, x0, y0, nx, ny):
    """(ny, nx) highest top of `tris` at the centres of a WALK_STEP grid whose
    first centre is (x0, y0); NaN where nothing covers. One triangle at a time
    over its own cells -- tri_cover against a whole cave is minutes."""
    H = np.full((ny, nx), -np.inf)
    st = WALK_STEP
    for a, b, c in tris:
        i0 = max(int(math.ceil((min(a[0], b[0], c[0]) - x0) / st)), 0)
        i1 = min(int(math.floor((max(a[0], b[0], c[0]) - x0) / st)), nx - 1)
        j0 = max(int(math.ceil((min(a[1], b[1], c[1]) - y0) / st)), 0)
        j1 = min(int(math.floor((max(a[1], b[1], c[1]) - y0) / st)), ny - 1)
        if i1 < i0 or j1 < j0:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            continue
        px, py = np.meshgrid(x0 + st * np.arange(i0, i1 + 1), y0 + st * np.arange(j0, j1 + 1))
        l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
        l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
        l3 = 1 - l1 - l2
        ins = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        zz = np.where(ins, l1 * a[2] + l2 * b[2] + l3 * c[2], -np.inf)
        H[j0:j1 + 1, i0:i1 + 1] = np.maximum(H[j0:j1 + 1, i0:i1 + 1], zz)
    return np.where(np.isfinite(H), H, np.nan)


class Walker:
    """A body walking a map's floors on a WALK_STEP grid, from spec["walk_from"].

    A step to a neighbouring cell is taken if the floor there is at most
    WALK_STEP_UP higher (any lower: a ledge onto a lower floor is a fall the
    client lands, a void is not) and no blocker crosses the way at knee and chest
    height (WALK_RAYS: three rays a body's width apart -- one ray slips through
    the cracks between two wall meshes, a body does not). A step from a reached
    cell into a cell with no floor at all is a **void step**: the client's
    ground ray would find only the hidden terrain, 7-31 m down."""

    def __init__(self, spec, src, extra=(), extra_block=()):
        tops = [walk_tops(spec, src)] + [t for t in extra if len(t)]
        self.W = np.concatenate(tops)
        B = np.concatenate([blockers(spec, src)] + [t for t in extra_block if len(t)])
        lo = self.W.reshape(-1, 3).min(0)[:2] - 4 * WALK_STEP
        hi = self.W.reshape(-1, 3).max(0)[:2] + 4 * WALK_STEP
        self.x0, self.y0 = float(lo[0]), float(lo[1])
        self.nx = int((hi[0] - lo[0]) // WALK_STEP) + 1
        self.ny = int((hi[1] - lo[1]) // WALK_STEP) + 1
        self.H = grid_top(self.W, self.x0, self.y0, self.nx, self.ny)
        cells = {}
        bmin, bmax = B.min(1), B.max(1)
        for k in range(len(B)):
            for bx in range(int(bmin[k, 0] // WALK_BUCKET) - 1, int(bmax[k, 0] // WALK_BUCKET) + 2):
                for by in range(int(bmin[k, 1] // WALK_BUCKET) - 1, int(bmax[k, 1] // WALK_BUCKET) + 2):
                    cells.setdefault((bx, by), []).append(k)
        self.B, self.buckets = B, {k: np.array(v) for k, v in cells.items()}

    def xy(self, j, i):
        return self.x0 + i * WALK_STEP, self.y0 + j * WALK_STEP

    def blocked(self, p, q):
        ids = self.buckets.get((int(p[0] // WALK_BUCKET), int(p[1] // WALK_BUCKET)))
        if ids is None:
            return False
        T = self.B[ids]
        d = np.array(q, float) - np.array(p, float)
        L = float(np.linalg.norm(d))
        d /= L
        side = np.array([-d[1], d[0], 0.0])
        side /= np.linalg.norm(side) + 1e-9
        o = np.array([np.array(p, float) + (0, 0, up) + side * off for up, off in WALK_RAYS])
        e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
        h = np.cross(d, e2)
        a = (e1 * h).sum(1)
        ok = np.abs(a) > 1e-9
        f = np.where(ok, 1 / np.where(ok, a, 1), 0)
        s = o[:, None, :] - T[None, :, 0]                  # (rays, tris, 3)
        u = f * (s * h).sum(2)
        qq = np.cross(s, e1)
        v = f * (qq @ d)
        t = f * (qq * e2).sum(2)
        return bool((ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0) & (t < L + WALK_BODY)).any())

    def flood(self, start):
        """(reached cells, [(cell, void neighbour)])."""
        H, (ny, nx) = self.H, self.H.shape
        sj = int(round((start[1] - self.y0) / WALK_STEP))
        si = int(round((start[0] - self.x0) / WALK_STEP))
        if H[sj, si] != H[sj, si]:
            raise SystemExit("the walker's start has no floor")
        seen, voids = {(sj, si)}, []
        todo = collections.deque([(sj, si)])
        while todo:
            j, i = todo.popleft()
            h = H[j, i]
            p = (*self.xy(j, i), h)
            for dj, di in WALK_DIRS:
                jj, ii = j + dj, i + di
                if not (0 <= jj < ny and 0 <= ii < nx) or (jj, ii) in seen:
                    continue
                h2 = H[jj, ii]
                if h2 != h2:
                    if not self.blocked(p, (*self.xy(jj, ii), h)):
                        voids.append(((j, i), (jj, ii)))
                    continue
                if h2 > h + WALK_STEP_UP or self.blocked(p, (*self.xy(jj, ii), max(h, h2))):
                    continue
                seen.add((jj, ii))
                todo.append((jj, ii))
        return seen, voids


def void_fill(spec, src):
    """[(pivot (x, y) cm, quads in pivot space, collision)] closing every void band
    the walker reaches. From each void step it goes on through void cells, at the
    height of the floor it left, until a blocker stops it.

      * A band that ends at blockers within VOID_FILL_REACH is the gap at a wall's
        foot: the band plus the floor cells around it (within WALK_STEP_UP of it:
        never the floor below a cliff) become an invisible **floor** (collision 4),
        each corner averaged from the cells around it within WALK_STEP_UP,
        STITCH_SINK under the floor. You walk on to the rock, as the picture says.
      * A band still open past VOID_FILL_REACH is open void (the cave's mouth): a
        floor there would carry you out into the dark, so instead an invisible
        **wall** (collision 12, the cave walls' level) stands on the edge cells'
        boundary with the void, WALL_BELOW under the floor to WALL_ABOVE over it;
        the body sphere stops you ~70 cm before it."""
    walker = Walker(spec, src)
    seen, voids = walker.flood(to_local_xy(spec["walk_from"]))
    H, (ny, nx) = walker.H, walker.H.shape
    fill, escaped, todo = {}, set(), collections.deque()
    for (j, i), (jj, ii) in voids:
        if (jj, ii) not in fill:
            fill[(jj, ii)] = (H[j, i], 1)
            todo.append((jj, ii))
    while todo:
        j, i = todo.popleft()
        z, n = fill[(j, i)]
        p = (*walker.xy(j, i), z)
        for dj, di in WALK_DIRS:
            jj, ii = j + dj, i + di
            if (jj, ii) in fill or not (0 <= jj < ny and 0 <= ii < nx):
                continue
            if H[jj, ii] == H[jj, ii] or walker.blocked(p, (*walker.xy(jj, ii), z)):
                continue
            if n >= VOID_FILL_REACH / WALK_STEP:
                escaped.add((j, i))
                continue
            fill[(jj, ii)] = (z, n + 1)
            todo.append((jj, ii))
    sheet = {c: z for c, (z, _) in fill.items()}
    for (j, i), (z, _) in fill.items():
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                c = (j + dj, i + di)
                if c in seen and c not in sheet and abs(H[c] - z) <= WALK_STEP_UP:
                    sheet[c] = H[c]
    out, left = [], set(sheet)
    while left:                                            # connected pieces
        piece, todo = [], [min(left)]
        left.discard(todo[0])
        while todo:
            c = todo.pop()
            piece.append(c)
            for dj, di in WALK_DIRS:
                nb = (c[0] + dj, c[1] + di)
                if nb in left:
                    left.discard(nb)
                    todo.append(nb)
        piece.sort()
        cx = float(np.mean([walker.xy(*c)[0] for c in piece]))
        cy = float(np.mean([walker.xy(*c)[1] for c in piece]))
        quads = []
        if escaped & set(piece):
            cells = set(piece)
            for (j, i), (jj, ii) in voids:
                if (jj, ii) not in cells:
                    continue
                (x, y), (x2, y2) = walker.xy(j, i), walker.xy(jj, ii)
                mx, my = (x + x2) / 2 - cx, (y + y2) / 2 - cy
                ux, uy = (y2 - y) / WALK_STEP, -(x2 - x) / WALK_STEP     # along the boundary
                h = WALL_OVERLAP + WALK_STEP / 2
                z0, z1 = H[j, i] - WALL_BELOW, H[j, i] + WALL_ABOVE
                quads.append(((mx - ux * h, my - uy * h, z0), (mx + ux * h, my + uy * h, z0),
                              (mx + ux * h, my + uy * h, z1), (mx - ux * h, my - uy * h, z1)))
            out.append(((cx, cy), np.array(quads), WALL_COLLISION))
            continue
        for j, i in piece:
            corners = []
            for cj, ci in ((0, 0), (0, 1), (1, 1), (1, 0)):        # SW SE NE NW
                zs = [sheet[(j + a, i + b)] for a in (cj - 1, cj) for b in (ci - 1, ci)
                      if (j + a, i + b) in sheet and abs(sheet[(j + a, i + b)] - sheet[(j, i)]) <= WALK_STEP_UP]
                x, y = walker.xy(j, i)
                corners.append((x + (ci - 0.5) * WALK_STEP - cx, y + (cj - 0.5) * WALK_STEP - cy,
                                float(np.mean(zs)) - STITCH_SINK))
            quads.append(corners)
        out.append(((cx, cy), np.array(quads), FLOOR_COLLISION))
    return out


def to_local_xy(m):
    return to_local(m[0]), to_local(m[1])


def floor_patches(spec, src):
    """[(pivot (x, y) cm, quads in pivot space, collision)]: spec["floor_patches"]'s
    seam patches, then with spec["void_fill"] the walker's floors and walls."""
    key = ("patches", spec["key"], src)
    if key in _CACHE:
        return _CACHE[key]
    out = []
    tops = walk_tops(spec, src, FLOOR_MIN_AREA)
    for wx, wy in spec["floor_patches"]:
        cx, cy = to_local(wx), to_local(wy)
        q = floor_patch(tops, cx, cy)
        if not len(q):
            raise SystemExit(f"{spec['key']}: no hole found around ({wx}, {wy}) m")
        out.append(((cx, cy), q - np.array([cx, cy, 0.0]), FLOOR_COLLISION))
    if spec["void_fill"]:
        out += void_fill(spec, src)
    _CACHE[key] = out
    return out


def blocker_distance(block, ground, x, y):
    """Plan distance (cm) from (x, y) to the nearest blocker face at body height
    over the ground there (its highest within 60 cm)."""
    zs = tri_cover(ground, np.array([[x + dx, y + dy] for dx in (-60, 0, 60) for dy in (-60, 0, 60)]))
    z = np.nanmax(zs) if np.isfinite(zs).any() else 0.0
    T = block[(block[:, :, 2].max(1) > z + 30) & (block[:, :, 2].min(1) < z + 200)]
    if not len(T):
        return float("inf")
    p, best = np.array([x, y]), float("inf")
    for k in range(3):
        a, b = T[:, k, :2], T[:, (k + 1) % 3, :2]
        t = np.clip(((p - a) * (b - a)).sum(1) / (((b - a) ** 2).sum(1) + 1e-9), 0, 1)
        best = min(best, float(np.linalg.norm(a + (b - a) * t[:, None] - p, axis=1).min()))
    return best


def patch_tris(patches, collision):
    """Placed patch quads of one collision level as triangles (zone-centre cm)."""
    return [np.array([t for qd in q + np.array([c[0], c[1], 0.0])
                      for t in ((qd[0], qd[1], qd[2]), (qd[0], qd[2], qd[3]))])
            for c, q, level in patches if level == collision]


def patch_records(spec, src):
    """{ifo name: {OBJECT: [records]}} placing the floor patches (deco_zsc's new
    objects, numbered after the table's own)."""
    if not spec["floor_patches"] and not spec["void_fill"]:
        return {}
    first = len(oro.Zsc(P(src, spec["deco"])).objects)
    out = {}
    for n, ((cx, cy), _, _) in enumerate(floor_patches(spec, src)):
        name, mxy = chunk_of(cx, cy)
        rec = ifo.Record(name=b"", warp_id=0, event_id=0, obj_type=1, obj_id=first + n,
                         map_x=mxy[0], map_y=mxy[1], rot=(0.0, 0.0, 0.0, 1.0),
                         pos=(f32(cx), f32(cy), 0.0), scale=(1.0, 1.0, 1.0))
        out.setdefault(name, {}).setdefault(ifo.OBJECT, []).append(rec)
    return out


# ---------------------------------------------------------- the deco table
def deco_zsc(spec, src):
    """The map's decoration table as we ship it: (bytes, {data-relative mesh path:
    ZMS bytes}, {what: count}).

    Canyon: tsuki's LIST_DECO_AG with a stitch part on every bridge, a **child of
    the deck part** (child_props), with the deck's collision and the invisible
    material appended once. The client applies a placement's rotation and scale to
    the model's root part alone (CObjFIXED::SetScale/SetRotation on m_nRootPART)
    and takes the *last* parentless part as that root (CMODEL::Load): a second
    root part stole the rotation, and on the diagonal bridges the planks stood
    unrotated -- drawn and collided wrong (second test, 2026-10-24; the editor
    transforms every part, so its renders looked right). Appended last, no .lit
    entry names it: lightmap sequence 0 is still the deck, a child is sequence 1.

    Cave: tsuki's LIST_DECO_SG with one new object per floor patch, a single root
    part (FLOOR_PART_PROPS: no transform, collision 4) in the invisible material."""
    z = oro.Zsc(P(src, spec["deco"]))
    new_meshes, files, info = [], {}, {}
    invisible = len(z.materials)
    for oid in spec["bridges"]:
        cyl, parts, dummies, bb = z.objects[oid]
        walkable = [k for k, p in enumerate(parts) if decode_props(p[2])["collision"]]
        if len(walkable) != 1:
            raise SystemExit(f"{spec['deco']} object {oid}: {len(walkable)} colliding parts, expected one deck")
        deck_i = walkable[0]
        mesh_i, mat_i, props = parts[deck_i]
        if decode_props(props)["parent"] != -1 or len(parts) != 1:
            raise SystemExit(f"{spec['deco']} object {oid}: the deck is not the lone root part")
        rel = z.meshes[mesh_i].decode("latin-1")
        quads = deck_stitches(mesh_tris(src, rel))
        fan = []
        for poly in STITCH_PATCHES.get(oid, ()):
            p = np.array(poly, float)
            c = p.mean(0)
            p[:, :2] = c[:2] + (p[:, :2] - c[:2]) * 1.05    # overlap the planks: corners are cm-rounded
            fan += [(p[0], p[k], p[k + 1], p[k + 1]) for k in range(1, len(p) - 1)]
        if fan:
            patch = np.array(fan, float)
            patch[..., 2] -= STITCH_SINK
            quads = np.concatenate([quads, patch]) if len(quads) else patch
        if not len(quads):
            continue
        walk = rel[:-4] + STITCH_SUFFIX
        files[walk] = zms.build(quad_mesh(quads))
        new_meshes.append(walk.encode("latin-1"))
        z.objects[oid] = (cyl, parts + [(len(z.meshes) + len(new_meshes) - 1, invisible,
                                          child_props(props, deck_i))], dummies, bb)
        info[f"bridge {oid}"] = len(quads)
    if spec["floor_patches"] or spec["void_fill"]:
        folder = os.path.dirname(z.meshes[z.objects[2][1][0][0]].decode("latin-1"))
        patches = floor_patches(spec, src)
        for n, (_, quads, level) in enumerate(patches):
            rel = folder + "\\" + FLOOR_PATCH_SUFFIX % n
            files[rel] = zms.build(quad_mesh(quads))
            new_meshes.append(rel.encode("latin-1"))
            lo, hi = quads.reshape(-1, 3).min(0), quads.reshape(-1, 3).max(0)
            props = FLOOR_PART_PROPS.replace(b"\x1d\x02\x04\x00", b"\x1d\x02" + struct.pack("<h", level))
            z.objects.append((struct.pack("<3i", 0, 0, 0),
                              [(len(z.meshes) + len(new_meshes) - 1, invisible, props)],
                              [], struct.pack("<6f", *lo, *hi)))
        info["floor patches"] = sum(level == FLOOR_COLLISION for _, _, level in patches)
        info["walls"] = sum(level == WALL_COLLISION for _, _, level in patches)
    mats = [invisible_material(src)] if new_meshes else []
    return z.rebuild_with(extra_meshes=new_meshes, extra_mats=mats), files, info


# ----------------------------------------------------------------- the gate
def gates_on(ours):
    """Whether the gate's WARP rows are in place: the gate pieces follow them."""
    p = P(ours, WARP_STB_REL)
    if not os.path.isfile(p):
        return False
    w = oro.Stb(p)
    return all([w.get(r, c) for c in range(3)] == warp_cells(r) for r in GATE_ROWS)


def warp_cells(row):
    label, zone_no, event = GATE_ROWS[row]
    return [label.encode("latin-1"), str(zone_no).encode(), event.encode()]


def fitted_ground(spec, src, cx, cy):
    """(height at the centre, unit normal) of the plane fitted to the ground under
    a platform at (cx, cy) zone-centre cm."""
    pts = [(cx + dx, cy + dy) for dx in np.arange(-PLATFORM_RADIUS, PLATFORM_RADIUS + 1, 50.0)
           for dy in np.arange(-PLATFORM_RADIUS, PLATFORM_RADIUS + 1, 50.0)
           if math.hypot(dx, dy) <= PLATFORM_RADIUS]
    z = np.array([ground_at(spec, src, x, y) for x, y in pts])
    if np.isnan(z).any():
        raise SystemExit(f"{spec['key']}: no ground under part of the platform at ({cx}, {cy})")
    A = np.array([[x - cx, y - cy, 1.0] for x, y in pts])
    (a, b, c), *_ = np.linalg.lstsq(A, z, rcond=None)
    n = np.array([-a, -b, 1.0])
    n /= np.linalg.norm(n)
    tilt = math.degrees(math.acos(n[2]))
    if tilt > MAX_TILT_DEG:
        raise SystemExit(f"{spec['key']}: the platform's ground is {tilt:.1f} degrees steep")
    return float(c), n


def tilt_quat(n):
    """(x, y, z, w) turning +z onto n, no yaw."""
    axis = np.cross([0.0, 0.0, 1.0], n)
    s = np.linalg.norm(axis)
    if s < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    angle = math.atan2(s, n[2])
    axis /= s
    h = math.sin(angle / 2)
    return tuple(float(v) for v in (axis[0] * h, axis[1] * h, axis[2] * h, math.cos(angle / 2)))


def rotate(q, v):
    """v turned by quaternion q (x, y, z, w)."""
    x, y, z, w = q
    u = np.array([x, y, z])
    v = np.asarray(v, float)
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def gate_records(key, src):
    """{ifo name: {EVENT_OBJECT: [platform], WARP: [trigger]}} for one side."""
    ck = ("gate", key, src)
    if ck in _CACHE:
        return _CACHE[ck]
    spec, g = {"canyon": CANYON, "cave": CAVE}[key], GATES[key]
    cx, cy = to_local(g["platform"][0]), to_local(g["platform"][1])
    zc, n = fitted_ground(spec, src, cx, cy)
    q = tilt_quat(n)
    pname, pxy = chunk_of(cx, cy)
    platform = ifo.EventObject(name=b"", warp_id=0, event_id=0, obj_type=12, obj_id=PLATFORM,
                               map_x=pxy[0], map_y=pxy[1], rot=q,
                               pos=(f32(cx), f32(cy), f32(zc - PLATFORM_SINK)), scale=(1.0, 1.0, 1.0),
                               trigger=PLATFORM_SCRIPT, con_file=PLATFORM_SCRIPT)
    x0, y0, x1, y1, height = WARP_BOX
    sx, sy, sz = WARP_SIZE / (x1 - x0), WARP_SIZE / (y1 - y0), WARP_HEIGHT / height
    centre = np.array([(x0 + x1) / 2 * sx, (y0 + y1) / 2 * sy, 0.0])
    origin = np.array([cx, cy, zc - PLATFORM_SINK - WARP_BASE]) - rotate(q, centre)
    wname, wxy = chunk_of(origin[0], origin[1])
    trigger = ifo.Record(name=b"", warp_id=g["warp"], event_id=0, obj_type=10, obj_id=10,
                         map_x=wxy[0], map_y=wxy[1], rot=q,
                         pos=tuple(f32(v) for v in origin), scale=(f32(sx), f32(sy), f32(sz)))
    out = {}
    out.setdefault(pname.upper(), {}).setdefault(ifo.EVENT_OBJECT, []).append(platform)
    out.setdefault(wname.upper(), {}).setdefault(ifo.WARP, []).append(trigger)
    _CACHE[ck] = out
    return out


def in_trigger(rec, x, y):
    """Whether (x, y) zone-centre cm lies in a WARP record's footprint (plan)."""
    x0, y0, x1, y1, _ = WARP_BOX
    yaw = 2 * math.atan2(rec.rot[2], rec.rot[3])            # tilt is small; plan test
    dx, dy = x - rec.pos[0], y - rec.pos[1]
    lx = (dx * math.cos(-yaw) - dy * math.sin(-yaw)) / rec.scale[0]
    ly = (dx * math.sin(-yaw) + dy * math.cos(-yaw)) / rec.scale[1]
    return x0 <= lx <= x1 and y0 <= ly <= y1


# ------------------------------------------------------------- tables
def zone_row(spec, s_z, d_z):
    src_zone = spec["src_zone"]
    row = [s_z.get(src_zone, c) for c in range(ZONE_COPY_COLS)]
    row += [b""] * (d_z.cols - ZONE_COPY_COLS)
    row[ZONE_NAME_COL] = spec["name"].encode()
    row[ZONE_STL_COL] = spec["stl_key"].encode()
    row[ZONE_MUSIC_DAY_COL] = row[ZONE_MUSIC_NIGHT_COL] = spec["music"]
    row[ZONE_SKY_COL] = str(spec["sky_rows"][int(txt(s_z.get(src_zone, ZONE_SKY_COL)))]).encode()
    if spec["zone_type"] is not None:
        row[ZONE_TYPE_COL] = spec["zone_type"]
    row[ZONE_CAMERA_COL] = spec["camera"]
    for c, v in FIELD_COLS.items():
        row[c] = v
    return row


def table_rows(src, ours, rel, rows):
    """{our row: wanted cells} for a row-for-row copy out of a tsuki table."""
    s, d = oro.Stb(P(src, rel)), oro.Stb(P(ours, rel))
    return {dst: [s.get(sr, c) for c in range(d.cols)] for sr, dst in rows.items()}


def row_files(want, cols):
    return {txt(cells[c]) for cells in want.values() for c in cols if txt(cells[c])}


def map_assets(spec, src):
    """Every data-relative file a map needs besides its map folder."""
    deco = oro.Zsc(P(src, spec["deco"]))
    art = {a for a in oro.zsc_asset_refs(deco) if "\\" in a or "/" in a}
    art |= oro.effect_chain({a for a in art if a.lower().endswith(".eft")}, src)
    tiles = {t for t in oro.zon_tiles(P(src, spec["maps_rel"] + "\\" + spec["zon"])) if "\\" in t or "/" in t}
    morph = row_files(table_rows(src, src, MORPH_STB_REL, {r: r for r in spec["morph_rows"]}), MORPH_FILE_COLS)
    sky = row_files(table_rows(src, src, SKY_STB_REL, {r: r for r in spec["sky_rows"]}), SKY_FILE_COLS)
    return {"object tables": {spec["deco"], CNST_ZSC_REL}, "decoration art": art,
            "terrain tiles": tiles, "morph art": morph, "sky": sky}


def put_rows(ours, rel, want, label, dry):
    d = oro.Stb(P(ours, rel))
    wrote = []
    for r, cells in sorted(want.items()):
        if d.d[r] == cells:
            continue
        if d.occupied(r):
            raise SystemExit(f"our {label} row {r} is {d.get(r, 0)!r}")
        d.d[r] = cells
        wrote.append(r)
    if wrote:
        d.save(dry)
    print(f"    {label:26s} rows {wrote or 'already in place'}")


# -------------------------------------------------------------- minimap
def dds_size(path):
    """(width, height, mip count) from a DDS header."""
    h = dds.parse_header(path)
    return h.width, h.height, h.mip_count


def minimap_size(folder):
    """The minimap our client expects for a map folder: its chunk span plus a
    one-chunk border, at MINIMAP_PX_PER_CHUNK (CMinimapDLG::CalculateDisplayPos)."""
    chunks = [f[:-4].split("_") for f in os.listdir(folder) if f.lower().endswith(".him")]
    xs, ys = {int(c[0]) for c in chunks}, {int(c[1]) for c in chunks}
    return ((max(xs) - min(xs) + 3) * MINIMAP_PX_PER_CHUNK,
            (max(ys) - min(ys) + 3) * MINIMAP_PX_PER_CHUNK)


def texconv(args, out):
    r = subprocess.run([TEXCONV, "-nologo", "-y"] + args, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise SystemExit("texconv failed: %s" % (r.stdout or r.stderr)[-400:])
    return out


def erase_labels(a, labels):
    """tsuki's labels painted out of an (h, w, 3) float picture, in place: the
    white text, its outline and its down-right shadow are masked inside each box
    and filled from the pixels around them (repeated 4-neighbour averaging)."""
    pad = 4
    for (x0, y0, x1, y1), *_ in labels:
        sub = a[y0 - pad:y1 + pad + 1, x0 - pad:x1 + pad + 1]
        white = sub.min(axis=2) > 150
        mask = white.copy()
        for dy in range(-2, 4):
            for dx in range(-2, 4):
                mask |= np.roll(np.roll(white, dy, 0), dx, 1)
        mask[[0, -1], :] = False
        mask[:, [0, -1]] = False
        for _ in range(400):
            nb = (np.roll(sub, 1, 0) + np.roll(sub, -1, 0) + np.roll(sub, 1, 1) + np.roll(sub, -1, 1)) / 4
            sub[mask] = nb[mask]


def minimap_bytes(spec, s_map):
    """tsuki's minimap at our scale, labelled in English, as DDS bytes.

    The Chinese series draws 128 px a chunk and our client places the avatar at 64
    (2026-10-23 test: the arrow stood far from the bridge it was on), so the
    picture is halved. The labels are erased at full size, the picture is
    box-halved, the English is drawn at the halved size (a halved label would be
    7 px tall), and texconv encodes DXT1 with a full chain (-nowic -if BOX:
    add-dds-mipmaps.py's reasons). DXT1 fringes the 11 px text a little; compared
    with uncompressed it stays readable, and the minimap keeps its usual cost."""
    sp = os.path.join(s_map, MINIMAP_NAME)
    w, h = minimap_size(s_map)
    sw, sh, _ = dds_size(sp)
    if (sw, sh) != (2 * w, 2 * h):
        raise SystemExit(f"tsuki's minimap is {sw}x{sh}, expected {2 * w}x{2 * h} (128 px a chunk)")
    with tempfile.TemporaryDirectory() as tmp:
        png = texconv(["-ft", "png", "-m", "1", "-o", tmp, sp],
                      os.path.join(tmp, os.path.splitext(MINIMAP_NAME)[0] + ".png"))
        a = np.asarray(Image.open(png).convert("RGB")).astype(np.float32)
        erase_labels(a, spec["labels"])
        im = Image.fromarray(np.clip(np.rint(a), 0, 255).astype(np.uint8)).reduce(2)
        draw = ImageDraw.Draw(im)
        font = ImageFont.truetype(*MINIMAP_FONT)
        for (x0, y0, x1, y1), text, anchor, at in spec["labels"]:
            x, y = at or ((x0 + x1) / 4, (y0 + y1) / 4)
            draw.text((x + 1, y + 1), text, font=font, anchor=anchor, fill=MINIMAP_SHADOW)
            draw.text((x, y), text, font=font, anchor=anchor, fill=MINIMAP_TEXT,
                      stroke_width=1, stroke_fill=MINIMAP_OUTLINE)
        os.makedirs(os.path.join(tmp, "out"))
        label_png = os.path.join(tmp, "MINIMAP.png")
        im.save(label_png)
        # DirectXTex's BOX filter takes power-of-two sizes only (ID09's 320 px fails);
        # the picture has no alpha, so LINEAR's bleed does not matter there
        pow2 = w & (w - 1) == 0 and h & (h - 1) == 0
        out = texconv(["-dx9", "-m", "0", "-nowic", "-if", "BOX" if pow2 else "LINEAR", "-f", "BC1_UNORM",
                       "-o", os.path.join(tmp, "out"), label_png], os.path.join(tmp, "out", "MINIMAP.dds"))
        return open(out, "rb").read()


# ------------------------------------------------------------------- stages
def install(spec, ours, src, dry, gates):
    """One map: its folder, art, tables, zone row and name."""
    s_map, d_map = P(src, spec["maps_rel"]), P(ours, spec["maps_rel"])
    folder = os.path.basename(spec["maps_rel"])
    copied = rewritten = 0
    for sub, name in map_files(spec, s_map):
        sp = os.path.join(s_map, sub, name)
        dp = os.path.normpath(os.path.join(d_map, sub, name))
        if name.lower().endswith(".ifo"):
            rewritten += write_if_changed(dp, map_ifo(spec, src, name, gates), dry)
            continue
        if name.upper() in LIT_NAMES:
            rewritten += write_if_changed(dp, map_lit(spec, s_map, sub.split(os.sep)[0], name), dry)
            continue
        if sub == "." and name.upper() == spec["zon"].upper():
            rewritten += write_if_changed(dp, map_zon(spec, src, gates), dry)
            continue
        if sub == "." and name.upper() == MINIMAP_NAME:
            if write_if_changed(os.path.join(d_map, MINIMAP_NAME), minimap_bytes(spec, s_map), dry):
                print(f"    {MINIMAP_NAME:26s} halved to %dx%d (our 64 px a chunk)" % minimap_size(s_map)
                      + (", labels in English" if spec["labels"] else ""))
            continue
        if os.path.isfile(dp):
            continue
        if not dry:
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copyfile(sp, dp)
        copied += 1
    print(f"    {folder:26s} {copied:5d} files copied, {rewritten} .IFO/.lit/.ZON written"
          + (" (with the gate)" if gates else ""))

    new_dds = []
    for label, rels in map_assets(spec, src).items():
        new_dds += [r for r in rels if r.lower().endswith(".dds") and not os.path.isfile(P(ours, r))]
        oro.copy_files(rels, src, ours, dry, label)

    table, extra, info = deco_zsc(spec, src)
    wrote = sum(write_if_changed(P(ours, rel), blob, dry) for rel, blob in extra.items())
    wrote += write_if_changed(P(ours, spec["deco"]), table, dry)
    if info:
        print(f"    {os.path.basename(spec['deco']):26s} " + ", ".join(f"{k}: {n}" for k, n in info.items())
              + (f"  ({wrote} files written)" if wrote else "  (already in place)"))

    if spec["morph_rows"]:
        put_rows(ours, MORPH_STB_REL, table_rows(src, ours, MORPH_STB_REL, spec["morph_rows"]),
                 "LIST_MORPH_OBJECT.STB", dry)
    put_rows(ours, SKY_STB_REL, table_rows(src, ours, SKY_STB_REL, spec["sky_rows"]), "LIST_SKY.STB", dry)

    zone, name = spec["zone"], spec["name"]
    s_z, d_z = oro.Stb(P(src, ZONE_STB_REL)), oro.Stb(P(ours, ZONE_STB_REL))
    want_zon = (spec["maps_rel"] + "\\" + spec["zon"]).lower()
    if txt(s_z.get(spec["src_zone"], 1)).lower().replace("\\\\", "\\") != want_zon:
        raise SystemExit(f"tsuki LIST_ZONE row {spec['src_zone']} is {s_z.get(spec['src_zone'], 1)!r}")
    grown = d_z.grow_to(zone + 1, labels={zone: name})
    cur = txt(d_z.get(zone, ZONE_NAME_COL))
    if cur and cur != name:
        raise SystemExit(f"our LIST_ZONE row {zone} is {cur!r}")
    want = zone_row(spec, s_z, d_z)
    if d_z.d[zone] != want or grown:
        d_z.d[zone] = want
        d_z.save(dry)
        print(f"    {'LIST_ZONE.STB':26s} row {zone} written" + (f" (+{grown} rows)" if grown else ""))
    else:
        print(f"    {'LIST_ZONE.STB':26s} row {zone} already in place")
    stl = oro.Stl(P(ours, ZONE_STL_REL))
    if not stl.has(spec["stl_key"]):
        stl.append(spec["stl_key"], zone, name)
        stl.save(dry)
        print(f"    {'LIST_ZONE_S.STL':26s} +1 key {spec['stl_key']}")
    else:
        print(f"    {'LIST_ZONE_S.STL':26s} {spec['stl_key']} already in place")

    if new_dds:
        dirs = sorted({os.path.dirname(d).replace("\\", "/") for d in new_dds})
        print(f"\n    NOTE: {len(new_dds)} new .dds, some without mip chains. Check with")
        print("          scripts/add-dds-mipmaps.py --dry-run --subdir <dir> for each of:")
        for d in dirs:
            print(f"            {d}")


def stage1(ours, src, dry):
    print("stage 1 -- the canyon: map, art, tables, zone row")
    install(CANYON, ours, src, dry, gates_on(ours))


def stage2(ours, src, dry):
    print("stage 2 -- the cave, then the gate between the two")
    if not oro.Stb(P(ours, ZONE_STB_REL)).rows > CANYON["zone"] or \
            txt(oro.Stb(P(ours, ZONE_STB_REL)).get(CANYON["zone"], 0)) != CANYON["name"]:
        raise SystemExit("run --stage 1 first: the gate needs the canyon")
    w = oro.Stb(P(ours, WARP_STB_REL))
    wrote = []
    for row in sorted(GATE_ROWS):
        want, cur = warp_cells(row), [w.get(row, c) for c in range(3)]
        if cur == want:
            continue
        if any(c.strip() for c in cur):
            raise SystemExit(f"our WARP.STB row {row} is {cur[0]!r}")
        for c, v in enumerate(want):
            w.set(row, c, v)
        wrote.append(row)
    if wrote:
        w.save(dry)
    print(f"    {'WARP.STB':26s} rows {wrote or 'already in place'}")
    # the gate's records follow its rows: on a dry run the rows are not written,
    # so the preview shows the gate as it will be
    install(CAVE, ours, src, dry, True)
    print("  the canyon's side of the gate")
    install(CANYON, ours, src, dry, True)


# ---------------------------------------------------------------- verify etc.
def verify(ours, src):
    bad = 0

    def check(ok, what):
        nonlocal bad
        bad += not ok
        print(f"    {'ok  ' if ok else 'FAIL'} {what}")

    gates = gates_on(ours)
    z_ours = oro.Stb(P(ours, ZONE_STB_REL))
    for spec in MAPS:
        zone = spec["zone"]
        if spec is CAVE and not (z_ours.rows > zone and txt(z_ours.get(zone, 0))):
            print(f"verify {spec['key']}: stage 2 not installed")
            continue
        print(f"verify {spec['key']} (zone {zone})" + (" with the gate" if gates else ""))
        s_map, d_map = P(src, spec["maps_rel"]), P(ours, spec["maps_rel"])
        same = os.path.isdir(d_map)
        for sub, name in map_files(spec, s_map) if same else []:
            dp = os.path.normpath(os.path.join(d_map, sub, name))
            if name.lower().endswith(".ifo"):
                want = map_ifo(spec, src, name, gates)
            elif name.upper() in LIT_NAMES:
                want = map_lit(spec, s_map, sub.split(os.sep)[0], name)
            elif sub == "." and name.upper() == spec["zon"].upper():
                want = map_zon(spec, src, gates)
            elif name.lower().endswith(".dds"):
                same &= os.path.isfile(dp)     # add-dds-mipmaps.py gives them a chain
                continue
            else:
                want = open(os.path.join(s_map, sub, name), "rb").read()
            same &= os.path.isfile(dp) and open(dp, "rb").read() == want
        check(same, "map folder as built (dead boxes gone, patches, lit fixes, gate)")
        mp = os.path.join(d_map, MINIMAP_NAME)
        check(os.path.isfile(mp) and open(mp, "rb").read() == minimap_bytes(spec, s_map),
              "minimap at our scale (%dx%d)" % minimap_size(s_map))
        boxes, warps = [], []
        for name in ifo_files(d_map) if os.path.isdir(d_map) else []:
            m = ifo.parse(open(os.path.join(d_map, name), "rb").read())
            boxes += m.lump(ifo.EVENT_OBJECT) or []
            warps += m.lump(ifo.WARP) or []
        want_gate = GATES[spec["key"]] if gates else None
        check([b.obj_id for b in boxes] == ([PLATFORM] if want_gate else [])
              and [w.warp_id for w in warps] == ([want_gate["warp"]] if want_gate else []),
              "no dead box; " + (f"one platform and warp {want_gate['warp']}" if want_gate else "no gate"))
        ev = {e.name: e for e in zon.parse(open(os.path.join(d_map, spec["zon"]), "rb").read()).lump(zon.EVENTS)} \
            if os.path.isfile(os.path.join(d_map, spec["zon"])) else {}
        check({b"start", b"restore"} <= set(ev), "start / restore")
        if want_gate:
            clear = all(not in_trigger(w, e.x, e.y) for w in warps for e in ev.values())
            check(clear, "no event point inside the gate's trigger")

        missing = []
        for rels in map_assets(spec, src).values():
            missing += [r for r in rels if os.path.isfile(P(src, r)) and not os.path.isfile(P(ours, r))]
        check(not missing, f"every asset the map names is here ({len(missing)} missing)")
        table, extra, info = deco_zsc(spec, src)
        same = all(os.path.isfile(P(ours, rel)) and open(P(ours, rel), "rb").read() == blob
                   for rel, blob in list(extra.items()) + [(spec["deco"], table)])
        check(same, f"{os.path.basename(spec['deco'])} is tsuki's" + (f" + {', '.join(info)}" if info else ""))
        zt = oro.Zsc(table)
        roots = {oid: [k for k, p in enumerate(zt.objects[oid][1]) if decode_props(p[2])["parent"] < 0]
                 for oid in spec["bridges"] if len(zt.objects[oid][1]) > 1}
        if roots:
            check(all(r == [0] for r in roots.values()),
                  "each stitched bridge has one root part, its deck (CMODEL::Load keeps the last parentless part)")
        if spec["floor_patches"] or spec["void_fill"]:
            tops = walk_tops(spec, src, FLOOR_MIN_AREA)
            patched = patch_tris(floor_patches(spec, src), FLOOR_COLLISION)
            walls = patch_tris(floor_patches(spec, src), WALL_COLLISION)
            before, left = floor_seams(tops), floor_seams(np.concatenate([tops] + patched))
            ground = np.concatenate([walk_tops(spec, src)] + patched)
            block = np.concatenate([blockers(spec, src)] + walls)
            open_ = [(x, y) for x, y in left if blocker_distance(block, ground, x, y) > SEAM_WALL_CLEAR]
            check(not open_, f"no hole between the floors ({len(before)} probes open before the patches, "
                             f"{len(left) - len(open_)} after against a wall, {len(open_)} open)")
            for x, y in open_:
                print(f"           open at ({x / 100 + 5200:.2f}, {y / 100 + 5200:.2f})")
            _, voids = Walker(spec, src).flood(to_local_xy(spec["walk_from"]))
            walker = Walker(spec, src, patched, walls)
            seen, after = walker.flood(to_local_xy(spec["walk_from"]))
            check(not after, f"no walk off a floor into the void ({len(voids)} steps before the patches, "
                             f"{len(after)} after; {len(seen) * WALK_STEP ** 2 / 1e4:.0f} m2 walked)")
            for (j, i), _ in after[:20]:
                x, y = walker.xy(j, i)
                print(f"           void step at ({x / 100 + 5200:.2f}, {y / 100 + 5200:.2f})")
        for rel, rows, label in ((MORPH_STB_REL, spec["morph_rows"], "LIST_MORPH_OBJECT"),
                                 (SKY_STB_REL, spec["sky_rows"], "LIST_SKY")):
            if not rows:
                continue
            d = oro.Stb(P(ours, rel))
            want = table_rows(src, ours, rel, rows)
            check(all(d.d[r] == cells for r, cells in want.items()), f"{label} rows {sorted(want)}")
        check(z_ours.rows > zone and z_ours.d[zone] == zone_row(spec, oro.Stb(P(src, ZONE_STB_REL)), z_ours),
              f"LIST_ZONE row {zone}")
        stl = oro.Stl(P(ours, ZONE_STL_REL))
        check(stl.has(spec["stl_key"]) and stl.name(spec["stl_key"]) == spec["name"],
              f"{spec['stl_key']} = {spec['name']}")
        r = subprocess.run([sys.executable, os.path.join(HERE, "audit-lightmap-index.py"), "--zone", str(zone)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()
        check(r.returncode == 0 and "0 CRASH, 0 RISK, 0 VISUAL" in last, f"audit-lightmap-index --zone {zone}: {last}")
    if gates:
        print("verify the gate")
        for row, (label, zone_no, event) in GATE_ROWS.items():
            dest = {CANYON["zone"]: CANYON, CAVE["zone"]: CAVE}[zone_no]
            zp = P(ours, dest["maps_rel"] + "\\" + dest["zon"])
            names = {e.name for e in zon.parse(open(zp, "rb").read()).lump(zon.EVENTS)} if os.path.isfile(zp) else set()
            check(event.encode() in names, f"WARP {row} -> zone {zone_no} {event}")
    baks = [rel for rel in BAK_TRACKED if os.path.isfile(P(ours, rel) + ".bak")]
    check(not baks, "no .bak left under data/")
    print("verify " + ("OK" if not bad else f"FAILED ({bad})"))
    return 1 if bad else 0


def selftest(ours, src):
    print("selftest -- every writer must reproduce its input byte for byte")
    for spec in MAPS:
        s_map = P(src, spec["maps_rel"])
        n = 0
        for sub, name in map_files(spec, s_map):
            p = os.path.join(s_map, sub, name)
            blob = open(p, "rb").read()
            if name.lower().endswith(".ifo"):
                assert ifo.build(ifo.parse(blob)) == blob, name
            elif name.upper() in LIT_NAMES:
                assert lit.build_lit(lit.parse_lit(blob)) == blob, (sub, name)
            elif name.lower().endswith(".zon"):
                assert zon.build(zon.parse(blob)) == blob, name
            else:
                continue
            n += 1
        z = oro.Zsc(P(src, spec["deco"]))
        assert z.rebuild_with() == z.d[:z.obj_end], spec["deco"]
        print(f"    {spec['key']}: {n} .IFO / .lit / .ZON files and {os.path.basename(spec['deco'])} round-trip")
    for rel in (ZONE_STB_REL, MORPH_STB_REL, SKY_STB_REL, WARP_STB_REL):
        p = P(ours, rel)
        assert oro.Stb(p).to_bytes() == open(p, "rb").read(), rel
    p = P(ours, ZONE_STL_REL)
    assert oro.Stl(p).to_bytes() == open(p, "rb").read(), ZONE_STL_REL
    print("    LIST_ZONE / LIST_MORPH_OBJECT / LIST_SKY / WARP / LIST_ZONE_S round-trip")
    print("    selftest OK")


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", type=int, choices=(1, 2), action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--source", default=DEFAULT_SRC)
    args = ap.parse_args()
    ours = os.path.join(args.root, "data")
    src = args.source
    for spec in MAPS:
        if not os.path.isdir(P(src, spec["maps_rel"])):
            raise SystemExit(f"source is not a tsuki client with {spec['maps_rel']}: {src}")
    if args.selftest:
        selftest(ours, src)
        return 0
    if args.verify:
        return verify(ours, src)
    if not args.stage:
        ap.error("give --stage 1, --stage 2, --verify or --selftest")
    for st in sorted(set(args.stage)):
        {1: stage1, 2: stage2}[st](ours, src, args.dry_run)
        print()
    if args.dry_run:
        print("dry run: nothing written")
    else:
        sweep_baks(ours)
        print("done. Next: --verify, add-dds-mipmaps.py on the folders above, rebake the VFS,")
        print("restart the servers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
