#!/usr/bin/env python3
"""Import tsuki's Valley002 ("LZON151") as zone 151, Shadow Canyon.

A walled canyon from the Chinese custom map series tsuki carries (zone rows
147-164 there; the series numbers its maps M001-M028 in its warp points). This
one is the series' M014. Scenery only: no NPC, no spawn, no sound or effect
object. Its BGM is `BGM_AYXG` (absent from tsuki) and its props `ANYING_*`, so its
Chinese name was most likely 暗影峡谷, "Shadow Canyon"; tsuki's STL has no text
for LZON151.

Staged like scripts/import-cerberus.py; every stage is idempotent, --dry-run
previews, --verify re-derives the state, --selftest proves every writer
round-trips byte-identically before anything is touched:

    --stage 1   the canyon: the map folder (the two dead warp boxes removed, the
                morph objects re-pointed, one chunk's object lightmap index
                repaired), its decoration table LIST_DECO_AG.ZSC and art, the
                new tile textures, morph rows 47/48, sky row 11, the zone row
                and its name.

Next (not written yet): Karkia ID09, tsuki's "Mysterious Cavern" (its row 156),
through a gate at the canyon's south-west columns.

The map (surveyed 2026-10-23)
-----------------------------
  * **6 x 6 chunks, 29_29 to 34_34** (960 m square), a ~600 m floor inside a ring
    of cliffs up to 150 m (terrain -13 .. 151 m): a river with a waterfall pool
    in the north, two rope bridges, ruins, grass to the south-west and east, a
    windmill pocket in the south-east. **There is no way out on foot**, the map
    is reached by warp only.
  * 503 decorations (72 of LIST_DECO_AG's 250 objects), no building (LIST_CNST_FK,
    13 empty objects, is copied anyway: the editor lists a zone only if both ZSC
    cells are set, and the cavern names it too), 7 morph objects, 202 invisible
    walls, 36 water lumps and 247 ocean rectangles. `.MOV` all zero (every cell
    walkable): nothing is spawned here yet, so it is left as shipped.
  * **The series' links** (every tsuki .ZON's `WARP-Mxxx` points, scanned): the
    canyon carries arrival points for M001 (on `start`, south centre), M012 (a
    trail into the east cliff, 35 m up; also the hub of tsuki's Lunar ID06-08),
    M022 (the windmill pocket, south-east) and M020 (the carved columns, south-west,
    world (4918, 5011) m). **M020 is Karkia ID09**, which carries the matching
    `WARP-M020-M014` points and starts on them. M001, M012 and M022 are in no dump
    we own. The points are kept with their series names: the cavern's gate will
    land on them, and the others are ready places for a gate later.
  * **No WARP lump.** Two EVENT_OBJECT records (EVENT_OBJECT row 10, the invisible
    warp box, at (5278, 5403) and (5325, 5166) m) fire triggers `42-e-1` and
    `274-e-1`, which are in no QSD of ours or tsuki's: dead in tsuki too. Removed
    (DEAD_BOXES); lump 12 has no lightmap entries, so nothing shifts.
  * **The economy lump is editor junk** (zone name "0", bgm "button1", all values
    0). Kept: `CEconomy::Load` divides by none of them and turns a town counter
    <= 1 into a day, as for Cerberus Lair.

Lightmaps are tsuki's, kept
---------------------------
They look right in the editor, and once the audit reads their names (below) they
are clean everywhere but **34_33's object index** -- the windmill pocket. One of
four `tree004` placements in a row was deleted after the bake (15 entries, 14
records), so entries 8-15 belong to records 7-14 and the last one points past
the lump; two others lit part 1 of a one-part object. In our client those are
out-of-bounds reads and writes (`CMAP::LoadLightMapINFO` checks nothing). LIT_FIXES
drops entry 7 and renumbers the rest: which of the four trees was deleted cannot
be read from the files, so at worst one tree shows its neighbour's lighting.
`audit-lightmap-index.py` flagged 337 other entries over Valley002 and ID09 as
"baked for another mesh": its name parser, not the maps -- this baker kept only
the last two `_`/`-` pieces of each mesh name (`VLY002_veg_tree002_A` ->
`tree002_A`). Fixed there the same day (`same_mesh`); no zone of ours changed.

The tables
----------
  * **Zone 151**, as in tsuki: our table ends at 144, so it grows to 152 rows and
    any later map of the series can keep its number. Columns 0-26 are tsuki's
    except: the name; the BGM (`BGM_AYXG` is in no dump: Gorge of Silence's canyon
    track for now, ZONE_MUSIC); sky 34 -> 11; camera 9 -> blank (col 21 indexes
    LIST_CAMERA, 6 rows here and 9 in tsuki: past both). Col 20 (zone type, the
    LIST_STEPSOUND column) stays tsuki's 4, Junon Polis's. Cols 27-35 are a Junon
    field's: party EXP 4/4, riding allowed, water collision 25. No revive zone:
    dying here revives on the canyon's own `restore`.
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
    STITCH_PATCHES), 2 cm under them, same material and collision. Measured with
    1 cm vertical rays on 13 lines across each walking band: 1,276 / 567 / 1,357 /
    2,264 open samples before, none after. **The part is invisible** (user,
    2026-10-24: the filled joints looked out of place, the open cracks are part of
    the charm): it wears retail's invisible-wall material (STITCH_MATERIAL, the
    Collision01 panel's `chake01.dds`, alpha 0 everywhere under an alpha test), so
    it only stops the fall. It has no .lit entry.
  * **Not a data matter -- the client draws a 3x3 window of map cells** around the
    one you stand in (CTERRAIN::ReOrginazationPatch, a 48x48 patch pool), so past
    160-320 m the terrain is simply not there; a 960 m canyon with 150 m walls shows
    it where open fields hide it (first test: "the map stopped drawing" on the
    ridge at (5239, 5278), a cell corner). The invisible walls there are tsuki's.
  * **The minimap is halved** (put_minimap). The series draws 128 px a chunk
    (Valley002 1024 px, ID09 640, Haian, Yulin likewise); our client places the
    avatar at 64 plus a one-chunk border (CMinimapDLG::CalculateDisplayPos), so
    the first test showed the arrow far from the bridge it stood on. Cerberus
    Lair, also from tsuki, was already at 64. The picture names the four links in
    Chinese: SW 暗影洞穴一层 "Shadow Cave, floor 1" (ID09), S 梦幻城堡 "Dream
    Castle" (M001), SE 纷争草原 "Plains of Strife" (M022), E 镜花雪原 "Mirror-Flower
    Snowfield" (M012; 镜花 is the "illusion" of 镜花水月). **Repainted in English**
    (MINIMAP_LABELS): "Mysterious Cavern" -- the name the cavern will carry, not the
    literal one -- "Dream Castle", "Plains of Strife", "Mirage Snowfield". The last
    three name places no dump has; the stars stay.

After running: `add-dds-mipmaps.py --dry-run --subdir <dir>` for the folders the
stage lists (about half the deco textures ship no mip chain), and `--subdir
3DDATA/MAPS/JUNON/VALLEY002 --lightmaps` (the object lightmaps ship none either:
578 ms of slow creates in the first test), then
`audit-lightmap-index.py --zone 151`, `mapgen-roundtrip.py --selftest`, rebake
the VFS, restart the servers (they read LIST_ZONE and the map). Way in until the
cavern's gate: `/mm 151 521 503` (GM; 10 m units, `Cheat_mm`: the start point at
(5209, 5034) m). Backups: build/valley002/.
"""
import argparse
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
from rosefmt import dds, ifo, lit, zms, zon  # noqa: E402
from rosefmt.zsc import TAG_PARENT, TAG_POS, TAG_ROT, TAG_SCALE, decode_props  # noqa: E402

# --------------------------------------------------------------------- config
DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\tsuki"
BUILD_DIR = os.path.join(ROOT, "build", "valley002")

ZONE = SRC_ZONE = 151
ZONE_NAME = "Shadow Canyon"
ZONE_STL_KEY = "LZON151"
ZONE_STB_REL = r"3DDATA\STB\LIST_ZONE.STB"
ZONE_STL_REL = r"3DDATA\STB\LIST_ZONE_S.STL"
ZONE_COPY_COLS = 27                 # 0..26 from tsuki; 27-35 are ZONE_FIELD_COLS
ZONE_NAME_COL, ZONE_STL_COL = 0, 26
ZONE_MUSIC_DAY_COL, ZONE_MUSIC_NIGHT_COL = 5, 6
ZONE_MUSIC = rb"Sound\BGM\Canyon01_junon.ogg"   # Gorge of Silence's (zone 28)
ZONE_SKY_COL, ZONE_CAMERA_COL = 7, 21
ZONE_FIELD_COLS = {28: b"4", 29: b"4", 30: b"0", 34: b"0", 35: b"25"}   # Adventurer's Plain's
MAPS_REL = r"3DDATA\MAPS\JUNON\VALLEY002"
ZON_NAME = "VALLEY002.ZON"
# tsuki's editor dump of the .ZON, and a 1408x896 picture nothing references
# (LIST_SKY 34 names day_valley002.dds, not this)
SKIP_FILES = {"valley002.zon.txt", "valley002.dds"}
DECO_ZSC_REL = r"3DDATA\MAPOBJ\LIST_DECO_AG.ZSC"
CNST_ZSC_REL = r"3DDATA\MAPOBJ\LIST_CNST_FK.ZSC"

MORPH_STB_REL = r"3DDATA\STB\LIST_MORPH_OBJECT.STB"
MORPH_ROWS = {42: 47, 63: 48}       # tsuki row -> ours (pokpo01 waterfall, fc02 windmill)
MORPH_FILE_COLS = (1, 2, 3)
SKY_STB_REL = r"3DDATA\STB\LIST_SKY.STB"
SKY_ROWS = {34: 11}
SKY_FILE_COLS = (0, 1, 2)

EVENT_BOX = 10                      # EVENT_OBJECT.STB row 10, the invisible warp box
DEAD_BOXES = {"32_31.IFO": b"42-e-1", "33_32.IFO": b"274-e-1"}
# (chunk, lit file) -> the entry baked for a record deleted after the bake, with
# the tga prefix it must carry; later entries move down one ordinal
LIT_FIXES = {("34_33", "OBJECTLIGHTMAPDATA.LIT"): (7, b"tree004_", 15)}
LIT_NAMES = ("OBJECTLIGHTMAPDATA.LIT", "BUILDINGLIGHTMAPDATA.LIT")
# lumps the canyon must not carry: a surprise here means the source changed
EMPTY_LUMPS = (ifo.MOB, ifo.CNST, ifo.SOUND, ifo.EFFECT, ifo.REGEN, ifo.WARP)

# Walkable bridges (LIST_DECO_AG objects, collision 4) whose decks are plank
# segments with open joints, some ~3 cm wide: the client's ground ray falls
# through one and the planks then hold the body inside the deck (2026-10-23 test,
# daqiao01: stuck 2 m below the planks). Each gets its joints stitched shut by
# an extra part (deck_stitches).
BRIDGES = (32, 33, 35, 36, 244)     # xiaoqiao01/02, daqiao01/02, shiqiao01
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
STITCH_MATERIAL = (r"3DDATA\SPECIAL\LIST_DECO_SPECIAL.ZSC", 2)

MINIMAP_NAME = "MINIMAP.DDS"
MINIMAP_PX_PER_CHUNK = 64           # cminimapdlg.cpp MINIMAP_RESOLUTION_PER_MAP; tsuki's series: 128
# The four Chinese labels, repainted in English (user, 2026-10-23): the text's box
# on tsuki's 1024 px picture (erased there), our name, and where it is drawn on the
# 512 px one -- centred on the old text, or right-aligned before its star (east).
MINIMAP_LABELS = (
    ((297, 694, 407, 709), "Mysterious Cavern", "mm", None),   # 暗影洞穴一层 Shadow Cave 1F (ID09)
    ((517, 693, 587, 708), "Dream Castle", "mm", None),        # 梦幻城堡 (M001)
    ((707, 686, 779, 701), "Plains of Strife", "mm", None),    # 纷争草原 (M022)
    ((708, 565, 777, 580), "Mirage Snowfield", "rm", (388, 286)),   # 镜花雪原 (M012)
)
MINIMAP_FONT = (r"C:\Windows\Fonts\arialbd.ttf", 11)
MINIMAP_TEXT, MINIMAP_OUTLINE, MINIMAP_SHADOW = (255, 255, 255), (35, 28, 20), (20, 16, 12)
TEXCONV = os.path.join(ROOT, "thirdparty", "directxtex-2020.9.30", "texconv.exe")

BAK_TRACKED = [ZONE_STB_REL, ZONE_STL_REL, MORPH_STB_REL, SKY_STB_REL]


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


# ------------------------------------------------------------------- stage 1
def canyon_ifo(src_map, name):
    """A tsuki canyon .IFO as we ship it: morphs re-pointed, the dead box gone."""
    raw = open(os.path.join(src_map, name), "rb").read()
    m = ifo.parse(raw)
    for lt in EMPTY_LUMPS:
        if m.lump(lt):
            raise SystemExit(f"{name}: unexpected records in lump {ifo.LUMP_NAMES[lt]}")
    changed = False
    for r in m.lump(ifo.MORPH) or []:
        if r.obj_id not in MORPH_ROWS:
            raise SystemExit(f"{name}: morph object {r.obj_id} has no mapping")
        r.obj_id = MORPH_ROWS[r.obj_id]
        changed = True
    boxes = m.lump(ifo.EVENT_OBJECT)
    if boxes:
        dead = DEAD_BOXES.get(name.upper())
        if [(b.obj_id, b.trigger) for b in boxes] != [(EVENT_BOX, dead)]:
            raise SystemExit(f"{name}: event objects {[(b.obj_id, b.trigger) for b in boxes]}, "
                             f"expected one dead warp box")
        boxes.clear()
        changed = True
    elif name.upper() in DEAD_BOXES:
        raise SystemExit(f"{name}: the dead warp box is missing from the source")
    return ifo.build(m) if changed else raw


def canyon_lit(src_map, chunk, lit_name):
    """A chunk's .lit as we ship it: LIT_FIXES applied, every other one verbatim."""
    raw = open(os.path.join(src_map, chunk, "LIGHTMAP", lit_name), "rb").read()
    fix = LIT_FIXES.get((chunk, lit_name.upper()))
    if fix is None:
        return raw
    drop, prefix, count = fix
    L = lit.parse_lit(raw)
    if len(L.objects) != count or L.objects[drop - 1].obj_index != drop \
            or not all(p.tga_name.startswith(prefix) and b"_Object_%d_" % drop in p.tga_name
                       for p in L.objects[drop - 1].parts):
        raise SystemExit(f"{chunk}/{lit_name}: not the bake LIT_FIXES was written for")
    del L.objects[drop - 1]
    for o in L.objects:
        if o.obj_index > drop:
            o.obj_index -= 1
    return lit.build_lit(L)


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
    count, seg = {}, {}
    for t in tops:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ka, kb = tuple(np.round(a, 1)), tuple(np.round(b, 1))
            k = (min(ka, kb), max(ka, kb))
            count[k] = count.get(k, 0) + 1
            seg[k] = (a, b)
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


def plan_covered(tris, p):
    """Whether any triangle covers point p (x, y) in plan."""
    a, b, c = tris[:, 0, :2], tris[:, 1, :2], tris[:, 2, :2]
    d1 = (b[:, 0] - a[:, 0]) * (p[1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (p[0] - a[:, 0])
    d2 = (c[:, 0] - b[:, 0]) * (p[1] - b[:, 1]) - (c[:, 1] - b[:, 1]) * (p[0] - b[:, 0])
    d3 = (a[:, 0] - c[:, 0]) * (p[1] - c[:, 1]) - (a[:, 1] - c[:, 1]) * (p[0] - c[:, 0])
    return bool((((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))).any())


def stitch_mesh(quads):
    """The stitches as a ZMS: both windings (whatever the engine culls, the ray
    meets one), normals up, uv0 the plan position (1 m a repeat)."""
    pos = (quads.reshape(-1, 3) / 100.0)            # ZMS v8 stores metres
    faces = []
    for q in range(len(quads)):
        v = 4 * q
        faces += [(v, v + 1, v + 2), (v, v + 2, v + 3), (v, v + 2, v + 1), (v, v + 3, v + 2)]
    return zms.rigid_v8(pos, np.tile((0.0, 0.0, 1.0), (len(pos), 1)), pos[:, :2], faces)


def deco_zsc(src):
    """tsuki's LIST_DECO_AG.ZSC with a stitch part on every BRIDGES object:
    (table bytes, {data-relative mesh path: ZMS bytes}, {object: stitches}).

    The part is a **child of the deck part** (child_props), with the deck's
    collision and the invisible-wall material (STITCH_MATERIAL, appended to the
    table's materials once). The client applies a placement's rotation and scale
    to the model's root part alone (CObjFIXED::SetScale/SetRotation on
    m_nRootPART) and takes the *last* parentless part as that root (CMODEL::Load):
    a second root part stole the rotation, and on the diagonal bridges the planks
    stood unrotated -- drawn and collided wrong (second test, 2026-10-24; the
    editor transforms every part, so its renders looked right). Appended last, no
    .lit entry names it: lightmap sequence 0 is still the deck, and a child is
    sequence 1, which no entry uses."""
    z = oro.Zsc(P(src, DECO_ZSC_REL))
    new_meshes, files, stitched = [], {}, {}
    special = oro.Zsc(P(src, STITCH_MATERIAL[0]))
    wall_mat = special.materials[special.objects[STITCH_MATERIAL[1]][1][0][1]]
    if not wall_mat[0].lower().endswith(b"chake01.dds"):
        raise SystemExit(f"{STITCH_MATERIAL[0]} object {STITCH_MATERIAL[1]} is not the invisible wall")
    invisible = len(z.materials)
    for oid in BRIDGES:
        cyl, parts, dummies, bb = z.objects[oid]
        walkable = [k for k, p in enumerate(parts) if decode_props(p[2])["collision"]]
        if len(walkable) != 1:
            raise SystemExit(f"LIST_DECO_AG object {oid}: {len(walkable)} colliding parts, expected one deck")
        deck_i = walkable[0]
        mesh_i, mat_i, props = parts[deck_i]
        if decode_props(props)["parent"] != -1 or len(parts) != 1:
            raise SystemExit(f"LIST_DECO_AG object {oid}: the deck is not the lone root part")
        rel = z.meshes[mesh_i].decode("latin-1")
        quads = deck_stitches(np.asarray(zms.parse(open(P(src, rel), "rb").read()).triangles_cm(), float))
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
        files[walk] = zms.build(stitch_mesh(quads))
        new_meshes.append(walk.encode("latin-1"))
        z.objects[oid] = (cyl, parts + [(len(z.meshes) + len(new_meshes) - 1, invisible,
                                          child_props(props, deck_i))], dummies, bb)
        stitched[oid] = len(quads)
    return z.rebuild_with(extra_meshes=new_meshes, extra_mats=[wall_mat] if new_meshes else []), files, stitched


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


def erase_labels(a):
    """tsuki's labels painted out of an (h, w, 3) float picture, in place: the
    white text, its outline and its down-right shadow are masked inside each box
    and filled from the pixels around them (repeated 4-neighbour averaging)."""
    pad = 4
    for (x0, y0, x1, y1), *_ in MINIMAP_LABELS:
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


def minimap_bytes(s_map):
    """tsuki's minimap at our scale, labelled in English, as DDS bytes.

    The Chinese series draws 128 px a chunk and our client places the avatar at 64
    (2026-10-23 test: the arrow stood far from the bridge it was on), so the 1024 px
    picture is halved. The labels are erased at full size, the picture is box-halved,
    the English is drawn at 512 px (a halved label would be 7 px tall), and texconv
    encodes DXT1 with a full chain (-nowic -if BOX: add-dds-mipmaps.py's reasons).
    DXT1 fringes the 11 px text a little; compared with uncompressed it stays
    readable, and the minimap keeps its usual size and cost."""
    sp = os.path.join(s_map, MINIMAP_NAME)
    w, h = minimap_size(s_map)
    sw, sh, _ = dds_size(sp)
    if (sw, sh) != (2 * w, 2 * h):
        raise SystemExit(f"tsuki's minimap is {sw}x{sh}, expected {2 * w}x{2 * h} (128 px a chunk)")
    with tempfile.TemporaryDirectory() as tmp:
        png = texconv(["-ft", "png", "-m", "1", "-o", tmp, sp],
                      os.path.join(tmp, os.path.splitext(MINIMAP_NAME)[0] + ".png"))
        a = np.asarray(Image.open(png).convert("RGB")).astype(np.float32)
        erase_labels(a)
        im = Image.fromarray(np.clip(np.rint(a), 0, 255).astype(np.uint8)).reduce(2)
        draw = ImageDraw.Draw(im)
        font = ImageFont.truetype(*MINIMAP_FONT)
        for (x0, y0, x1, y1), text, anchor, at in MINIMAP_LABELS:
            x, y = at or ((x0 + x1) / 4, (y0 + y1) / 4)
            draw.text((x + 1, y + 1), text, font=font, anchor=anchor, fill=MINIMAP_SHADOW)
            draw.text((x, y), text, font=font, anchor=anchor, fill=MINIMAP_TEXT,
                      stroke_width=1, stroke_fill=MINIMAP_OUTLINE)
        os.makedirs(os.path.join(tmp, "out"))
        label_png = os.path.join(tmp, "MINIMAP.png")
        im.save(label_png)
        out = texconv(["-dx9", "-m", "0", "-nowic", "-if", "BOX", "-f", "BC1_UNORM",
                       "-o", os.path.join(tmp, "out"), label_png], os.path.join(tmp, "out", "MINIMAP.dds"))
        return open(out, "rb").read()


def put_minimap(s_map, d_map, dry):
    return write_if_changed(os.path.join(d_map, MINIMAP_NAME), minimap_bytes(s_map), dry)


def zone_row(s_z, d_z):
    row = [s_z.get(SRC_ZONE, c) for c in range(ZONE_COPY_COLS)]
    row += [b""] * (d_z.cols - ZONE_COPY_COLS)
    row[ZONE_NAME_COL] = ZONE_NAME.encode()
    row[ZONE_STL_COL] = ZONE_STL_KEY.encode()
    row[ZONE_MUSIC_DAY_COL] = row[ZONE_MUSIC_NIGHT_COL] = ZONE_MUSIC
    row[ZONE_SKY_COL] = str(SKY_ROWS[int(txt(s_z.get(SRC_ZONE, ZONE_SKY_COL)))]).encode()
    row[ZONE_CAMERA_COL] = b""
    for c, v in ZONE_FIELD_COLS.items():
        row[c] = v
    return row


def table_rows(src, ours, rel, rows):
    """{our row: wanted cells} for a row-for-row copy out of a tsuki table."""
    s, d = oro.Stb(P(src, rel)), oro.Stb(P(ours, rel))
    return {dst: [s.get(sr, c) for c in range(d.cols)] for sr, dst in rows.items()}


def row_files(want, cols):
    return {txt(cells[c]) for cells in want.values() for c in cols if txt(cells[c])}


def canyon_assets(src):
    """Every data-relative file the canyon needs besides its map folder."""
    deco = oro.Zsc(P(src, DECO_ZSC_REL))
    art = {a for a in oro.zsc_asset_refs(deco) if "\\" in a or "/" in a}
    art |= oro.effect_chain({a for a in art if a.lower().endswith(".eft")}, src)
    tiles = {t for t in oro.zon_tiles(P(src, MAPS_REL + "\\" + ZON_NAME)) if "\\" in t or "/" in t}
    morph = row_files(table_rows(src, src, MORPH_STB_REL, {r: r for r in MORPH_ROWS}), MORPH_FILE_COLS)
    sky = row_files(table_rows(src, src, SKY_STB_REL, {r: r for r in SKY_ROWS}), SKY_FILE_COLS)
    return {"object tables": {DECO_ZSC_REL, CNST_ZSC_REL}, "decoration art": art,
            "terrain tiles": tiles, "morph art": morph, "sky": sky}


def map_files(s_map):
    """(sub, name) of every source map file we ship, in walk order."""
    for base, _, names in os.walk(s_map):
        sub = os.path.relpath(base, s_map)
        for name in sorted(names):
            if name.lower() not in SKIP_FILES:
                yield sub, name


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


def stage1(ours, src, dry):
    print("stage 1 -- the canyon: map, art, tables, zone row")
    s_map, d_map = P(src, MAPS_REL), P(ours, MAPS_REL)
    copied = rewritten = 0
    for sub, name in map_files(s_map):
        sp = os.path.join(s_map, sub, name)
        dp = os.path.normpath(os.path.join(d_map, sub, name))
        if name.lower().endswith(".ifo"):
            rewritten += write_if_changed(dp, canyon_ifo(s_map, name), dry)
            continue
        if name.upper() in LIT_NAMES:
            rewritten += write_if_changed(dp, canyon_lit(s_map, sub.split(os.sep)[0], name), dry)
            continue
        if sub == "." and name.upper() == MINIMAP_NAME:
            if put_minimap(s_map, d_map, dry):
                print(f"    {MINIMAP_NAME:26s} halved to %dx%d (our 64 px a chunk), labels in English"
                      % minimap_size(s_map))
            continue
        if os.path.isfile(dp):
            continue
        if not dry:
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copyfile(sp, dp)
        copied += 1
    print(f"    {'VALLEY002':26s} {copied:5d} files copied, {rewritten} .IFO/.lit written")

    new_dds = []
    for label, rels in canyon_assets(src).items():
        new_dds += [r for r in rels if r.lower().endswith(".dds") and not os.path.isfile(P(ours, r))]
        oro.copy_files(rels, src, ours, dry, label)

    table, walks, stitched = deco_zsc(src)
    wrote = sum(write_if_changed(P(ours, rel), blob, dry) for rel, blob in walks.items())
    wrote += write_if_changed(P(ours, DECO_ZSC_REL), table, dry)
    print(f"    {'bridge joints stitched':26s} " + ", ".join(f"{o}: {n}" for o, n in stitched.items())
          + (f"  ({wrote} files written)" if wrote else "  (already in place)"))

    put_rows(ours, MORPH_STB_REL, table_rows(src, ours, MORPH_STB_REL, MORPH_ROWS),
             "LIST_MORPH_OBJECT.STB", dry)
    put_rows(ours, SKY_STB_REL, table_rows(src, ours, SKY_STB_REL, SKY_ROWS), "LIST_SKY.STB", dry)

    s_z, d_z = oro.Stb(P(src, ZONE_STB_REL)), oro.Stb(P(ours, ZONE_STB_REL))
    if txt(s_z.get(SRC_ZONE, 1)).lower().replace("\\\\", "\\") != (MAPS_REL + "\\" + ZON_NAME).lower():
        raise SystemExit(f"tsuki LIST_ZONE row {SRC_ZONE} is {s_z.get(SRC_ZONE, 1)!r}")
    grown = d_z.grow_to(ZONE + 1, labels={ZONE: ZONE_NAME})
    cur = txt(d_z.get(ZONE, ZONE_NAME_COL))
    if cur and cur != ZONE_NAME:
        raise SystemExit(f"our LIST_ZONE row {ZONE} is {cur!r}")
    want = zone_row(s_z, d_z)
    if d_z.d[ZONE] != want or grown:
        d_z.d[ZONE] = want
        d_z.save(dry)
        print(f"    {'LIST_ZONE.STB':26s} row {ZONE} written" + (f" (+{grown} rows)" if grown else ""))
    else:
        print(f"    {'LIST_ZONE.STB':26s} row {ZONE} already in place")
    stl = oro.Stl(P(ours, ZONE_STL_REL))
    if not stl.has(ZONE_STL_KEY):
        stl.append(ZONE_STL_KEY, ZONE, ZONE_NAME)
        stl.save(dry)
        print(f"    {'LIST_ZONE_S.STL':26s} +1 key {ZONE_STL_KEY}")
    else:
        print(f"    {'LIST_ZONE_S.STL':26s} {ZONE_STL_KEY} already in place")

    if new_dds:
        dirs = sorted({os.path.dirname(d).replace("\\", "/") for d in new_dds})
        print(f"\n    NOTE: {len(new_dds)} new .dds, some without mip chains. Check with")
        print("          scripts/add-dds-mipmaps.py --dry-run --subdir <dir> for each of:")
        for d in dirs:
            print(f"            {d}")


# ---------------------------------------------------------------- verify etc.
def verify(ours, src):
    bad = 0

    def check(ok, what):
        nonlocal bad
        bad += not ok
        print(f"    {'ok  ' if ok else 'FAIL'} {what}")

    print("verify")
    s_map, d_map = P(src, MAPS_REL), P(ours, MAPS_REL)
    same = os.path.isdir(d_map)
    for sub, name in map_files(s_map) if same else []:
        dp = os.path.normpath(os.path.join(d_map, sub, name))
        if name.lower().endswith(".ifo"):
            want = canyon_ifo(s_map, name)
        elif name.upper() in LIT_NAMES:
            want = canyon_lit(s_map, sub.split(os.sep)[0], name)
        elif name.lower().endswith(".dds"):
            same &= os.path.isfile(dp)     # add-dds-mipmaps.py gives them a chain
            continue
        else:
            want = open(os.path.join(s_map, sub, name), "rb").read()
        same &= os.path.isfile(dp) and open(dp, "rb").read() == want
    check(same, "map folder (morphs re-pointed, dead boxes gone, 34_33 lit repaired)")
    mp = os.path.join(d_map, MINIMAP_NAME)
    check(os.path.isfile(mp) and open(mp, "rb").read() == minimap_bytes(s_map),
          "minimap at our scale (%dx%d), labels in English" % minimap_size(s_map))
    boxes = warps = 0
    for name in ifo_files(d_map) if os.path.isdir(d_map) else []:
        m = ifo.parse(open(os.path.join(d_map, name), "rb").read())
        boxes += len(m.lump(ifo.EVENT_OBJECT) or [])
        warps += len(m.lump(ifo.WARP) or [])
    check(boxes == 0 and warps == 0, "no event box, no gate (yet)")
    ev = {e.name for e in zon.parse(open(os.path.join(d_map, ZON_NAME), "rb").read()).lump(zon.EVENTS)} \
        if os.path.isfile(os.path.join(d_map, ZON_NAME)) else set()
    check(ev >= {b"start", b"restore", b"WARP-M020-M014"}, "start / restore / the cavern's landing point")

    missing = []
    for rels in canyon_assets(src).values():
        missing += [r for r in rels if os.path.isfile(P(src, r)) and not os.path.isfile(P(ours, r))]
    check(not missing, f"every asset the canyon names is here ({len(missing)} missing)")
    table, walks, stitched = deco_zsc(src)
    same = all(os.path.isfile(P(ours, rel)) and open(P(ours, rel), "rb").read() == blob
               for rel, blob in list(walks.items()) + [(DECO_ZSC_REL, table)])
    check(same, f"LIST_DECO_AG.ZSC is tsuki's + bridge stitches on {sorted(stitched)}")
    z = oro.Zsc(table)
    roots = {oid: [k for k, p in enumerate(z.objects[oid][1]) if decode_props(p[2])["parent"] < 0]
             for oid in stitched}
    check(all(r == [0] for r in roots.values()),
          "each stitched bridge has one root part, its deck (CMODEL::Load keeps the last parentless part)")
    p = P(ours, CNST_ZSC_REL)
    check(os.path.isfile(p) and open(p, "rb").read() == open(P(src, CNST_ZSC_REL), "rb").read(),
          f"{os.path.basename(CNST_ZSC_REL)} is tsuki's")
    for rel, rows, label in ((MORPH_STB_REL, MORPH_ROWS, "LIST_MORPH_OBJECT"), (SKY_STB_REL, SKY_ROWS, "LIST_SKY")):
        d = oro.Stb(P(ours, rel))
        want = table_rows(src, ours, rel, rows)
        check(all(d.d[r] == cells for r, cells in want.items()), f"{label} rows {sorted(want)}")
    z = oro.Stb(P(ours, ZONE_STB_REL))
    check(z.rows > ZONE and z.d[ZONE] == zone_row(oro.Stb(P(src, ZONE_STB_REL)), z), f"LIST_ZONE row {ZONE}")
    stl = oro.Stl(P(ours, ZONE_STL_REL))
    check(stl.has(ZONE_STL_KEY) and stl.name(ZONE_STL_KEY) == ZONE_NAME, f"{ZONE_STL_KEY} = {ZONE_NAME}")
    baks = [rel for rel in BAK_TRACKED if os.path.isfile(P(ours, rel) + ".bak")]
    check(not baks, "no .bak left under data/")

    r = subprocess.run([sys.executable, os.path.join(HERE, "audit-lightmap-index.py"), "--zone", str(ZONE)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()
    check(r.returncode == 0 and "0 CRASH, 0 RISK, 0 VISUAL" in last, f"audit-lightmap-index --zone {ZONE}: {last}")
    print("verify " + ("OK" if not bad else f"FAILED ({bad})"))
    return 1 if bad else 0


def selftest(ours, src):
    print("selftest -- every writer must reproduce its input byte for byte")
    s_map = P(src, MAPS_REL)
    n = 0
    for sub, name in map_files(s_map):
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
    print(f"    {n} canyon .IFO / .lit / .ZON files round-trip")
    for rel in (ZONE_STB_REL, MORPH_STB_REL, SKY_STB_REL):
        p = P(ours, rel)
        assert oro.Stb(p).to_bytes() == open(p, "rb").read(), rel
    p = P(ours, ZONE_STL_REL)
    assert oro.Stl(p).to_bytes() == open(p, "rb").read(), ZONE_STL_REL
    print("    LIST_ZONE / LIST_MORPH_OBJECT / LIST_SKY / LIST_ZONE_S round-trip")
    print("    selftest OK")


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", type=int, choices=(1,), action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--source", default=DEFAULT_SRC)
    args = ap.parse_args()
    ours = os.path.join(args.root, "data")
    src = args.source
    if not os.path.isdir(P(src, MAPS_REL)):
        raise SystemExit(f"source is not a tsuki client with Valley002: {src}")
    if args.selftest:
        selftest(ours, src)
        return 0
    if args.verify:
        return verify(ours, src)
    if not args.stage:
        ap.error("give --stage 1, --verify or --selftest")
    for st in sorted(set(args.stage)):
        {1: stage1}[st](ours, src, args.dry_run)
        print()
    if args.dry_run:
        print("dry run: nothing written")
    else:
        sweep_baks(ours)
        print(f"done. Next: --verify, add-dds-mipmaps.py on the folders above, rebake the VFS,")
        print("restart the servers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
