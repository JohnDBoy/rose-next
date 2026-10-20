"""The armour ladder after the user's survey (2026-10-20): three vanity sets become
level-10 cosmetics, Crystal takes Rose Brasil's "Legendary Crystal" look, and the
lv210 caps get the female models they never had.

The survey (user, 2026-10-20) graded every set from 200 up by how it looks:

    240  Royal Guardian / Sun Prophet / Jackal / Serpent   end game, Oro-coded   keep
    230  Legionnaire / Spitfire / Spinosaur / Assailant    end game              keep
    230  Unit Core (Sol / Jupiter / Diana / Pluto)         vanity, power-ranger  -> lv10
    225  Refined Steam                                     vanity                -> lv10
    220  Steam                                             vanity                -> lv10
    220  Crystal                                           end game, incomplete  -> Legendary look
    210  Viking / Vampire / Witch ... (8 classes)          end game              keep
    200  vanilla                                           keep

The ladder keeps its levels (200/210/220/230/240, the user's choice "A"): every tier
that stays already sits on the line the monster balance was tuned against -- Unit Core
was the 50% point between Crystal and Egyptian -- so nothing else moves. New end-game
sets are expected to reshuffle it later. Legionnaire keeps its more-DEF, less-RES
profile for now ("we'll see how it goes"), though the Unit Core it was a trade against
is gone (import-legionnaire-armour.py's docstring describes that trade).

--- 1. the vanity sets become cosmetics (rows 250-261 of all four tables)

Same rows, so every copy a player owns converts in place. **Level 10 and still
class-locked**: the costume slots go through `Check_EquipCondition` (gs_user.cpp,
receive_client_equip_costume_item), so a Soldier-line set is a costume for any
Soldier-line character -- that is the whole use, with no code change. The first cut
put them at 70 / 90 / 110 and sold them in Junon Polis; the user's verdict was that
the level limit "was a bad idea" and a shop "just confusing", so they are level 10
and **sold nowhere** (where they come from is the user's to decide). Re-running this
script puts the first cut's Junon cells back: any cell an earlier run wrote that the
plan no longer covers returns to its recorded original.

Stats are the vanilla level-10 class set of the same line (row 31 + 30 per class:
Soldier Armor, Spiritual Vest, Hunter Chest, Brown Vest ...), then:

    DEF, RES        x0.9 -- a cosmetic is never an upgrade over the real set
    bonus           the class line's own piece bonus x0.9 (the Muse body's +MP)
    price, quality, durability, boots move speed   the vanilla values
    rare type (col 30)   1, as the vanilla rows (12/14/24/35 behaved as 0 anyway:
                    only 3 and 4 mean anything, `drop_rule_from_int`)

The 220+ bonus pair (+85 / +72 class stats, +1,075 Max HP on the body) is dropped.
Names and descriptions stay: they never mentioned a tier. Weight and the craft columns
are left alone. **The combat sim skips them** (`combatsim/autobuild.COSMETIC_ARMOUR`),
or the level-10 tier would hold four sets.

--- 2. Crystal takes the Legendary Crystal look (CAP 977-980, BODY 904-907, ARMS
880-883, FOOT 878-881)

Our Crystal rows had **no female cap at all** (the four LIST_WCAP objects were empty:
the import came from a dump whose caps were male-only), and the Muse cap and boots
carried stray textures. Rose Brasil's "Legendary Crystal" (its LIST_* rows 1040-1043:
Warrior / Magical / Battle / Enginer = our Soldier / Muse / Hawker / Dealer) is the
same career_a silhouette with its own textures (career_a_009-012), complete on all
four slots for both sexes.

**We already shipped all of that art**, unreferenced: the 009-012 DDS files sit in
`AVATAR\\<slot>\\` beside the `CRYSTAL\\` subfolder our rows use, DXT5 where Brasil's
are uncompressed -- the same pictures (mean pixel difference 2-7 of 255, DXT noise).
So the swap is a re-wiring: each object is rebuilt from Brasil's, every mesh resolved
to a byte-identical file we already reference (our `CRYSTAL\\` copies) or hold, every
texture to our copy; a file we lack would be copied from Brasil (none at the time of
writing). Stats, prices and shop slots are untouched -- the rows keep their numbers.
Icons are Brasil's own, cropped from its atlas into ours (`import-item.py
copy_source_icon`). Names become "Legendary Crystal <class> <piece>".

--- 3. the lv210 caps get female models (LIST_WCAP 981-988)

The same defect as Crystal's: all eight lv210 caps (Viking ... Craftmans) had an empty
female object, so a female character's helm vanished. QQ-iROSE (our lineage; its
`CAP\\JAROSE\\<line>\\` is our `CAP\\<line>\\`) has them at LIST_WCAP 256-263. Each female
object takes QQ's geometry (meshes, part transforms, bounding box) and **our male
object's texture per part** -- the female meshes are the `_F` twins of ours and the
parts line up one to one, which the script asserts. Only the `_F` meshes are copied
(into our male object's folder); the Dealer heads are unisex in QQ too. Orlean Saga
has no QQ row of its own: it takes Magic Witch's female mesh (`CAP_F49811.ZMS`, which
is literally Orlean's) with its own texture, as Jrose's LIST_WCAP 75 does.

--- 4. Karkia's Astraea

Her tabs were materials (565), Refined Steam (566) and Unit Core (567). A Starsteel
Armourer with no armour would be odd, so 566 becomes "Legendary Crystal lv220" (the
Karkia grid: cap / body / gloves / boots down, class across), 567 is emptied and
unreferenced, and her third tab is Sulfa's 568 (Legionnaire): the reason to keep the
two lv230 sets on separate counters is gone with Unit Core. `add-karkia-shops.py`'s
plan says the same, so its `--verify` still passes.

    python scripts/armour-ladder-pass.py --dry-run
    python scripts/armour-ladder-pass.py
    python scripts/armour-ladder-pass.py --verify
    python scripts/armour-ladder-pass.py --restore

Undo: STB cells and STL fields are cell-level; the six touched ZSCs are whole-file
originals with the hash of what this pass wrote (restore refuses a file changed since);
copied files are removed. Appended icons stay in the atlas (other scripts append after
them); restore points the STB icon cells back. Everything lives in
`build/armour-ladder-pass/`. `data/` is gitignored, so this file is the record.

Afterwards: restart the servers (STBs, LIST_NPC, LIST_SELL), re-bake the VFS.
The superseded importers' `--verify` (import-steam-armour, import-midtier-armour)
report the new levels as drift; that is expected.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from rosefmt import Stb, Stl, Zsc  # noqa: E402

DATA = os.path.join(REPO, "data", "3DDATA")
STB_DIR = os.path.join(DATA, "STB")
BRASIL = r"C:\Users\Thomas\Desktop\Testclients\rose brazil\Extracted"
QQ = r"C:\Users\Thomas\Desktop\Testclients\QQ-iROSE Online\QQiroseData"
BRASIL_3D, QQ_3D = os.path.join(BRASIL, "3DDATA"), os.path.join(QQ, "3DDATA")
BACKUP_DIR = os.path.join(REPO, "build", "armour-ladder-pass")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

CLASSES = ("Soldier", "Muse", "Hawker", "Dealer")
SLOTS = ("cap", "body", "arms", "foot")
TABLE = {"cap": "LIST_CAP", "body": "LIST_BODY", "arms": "LIST_ARMS", "foot": "LIST_FOOT"}
ZSCS = {"cap": ("LIST_MCAP", "LIST_WCAP"), "body": ("LIST_MBODY", "LIST_WBODY"),
        "arms": ("LIST_MARMS", "LIST_WARMS"), "foot": ("LIST_MFOOT", "LIST_WFOOT")}
ITEM_TYPE = {"cap": 2, "body": 3, "arms": 4, "foot": 5}

COL_NAME, COL_PRICE, COL_QUALITY, COL_ICON = 0, 5, 8, 9
COL_LEVEL = 20
COL_BONUS = (23, 24, 25, 26, 27, 28)      # two (condition, ability, amount) triples
COL_DURABILITY, COL_RARE, COL_DEF, COL_RES = 29, 30, 31, 32
COL_SPEED = 33                             # LIST_FOOT only

# --- 1. cosmetics -----------------------------------------------------------
# Level 10 for all three (user, 2026-10-20: the first cut's 70/90/110 "was a bad idea")
COSMETIC = {"Steam": (250, 10), "Refined Steam": (254, 10), "Unit Core": (258, 10)}
# vanilla class sets of the Soldier line; + 30 per class line (Muse 61.., Hawker 91..)
VANILLA = {10: 31, 70: 34, 88: 35, 104: 36, 120: 37}
COSMETIC_SHARE = 0.9

# --- 2. Legendary Crystal ---------------------------------------------------
CRYSTAL_ROW = {"cap": 977, "body": 904, "arms": 880, "foot": 878}
BRASIL_ROW = {"Soldier": 1040, "Muse": 1041, "Hawker": 1042, "Dealer": 1043}
PIECE = {"cap": "Cap", "body": "Suit", "arms": "Gloves", "foot": "Boots"}
LEGENDARY_DESC = {
    "Soldier": "Crystal grown over a war-plate frame and cut back by hand until only "
               "the hard facets were left. It rings when struck and does not crack.",
    "Muse":    "Crystal spun thin enough to drape, set with stones that catch the "
               "light of whatever spell is near. Heavier than it looks.",
    "Hawker":  "Smoky crystal plates laced over leather, every edge filed down so it "
               "makes no sound in the brush.",
    "Dealer":  "Crystal panels bolted into a working frame and polished bright: a "
               "craftsman's armour, and a showcase of what the craftsman can do.",
}

# --- 3. lv210 female caps: our row -> (expected name, QQ LIST_WCAP object) ----
FEMALE_210 = {
    981: ("Viking Helm", 256),
    982: ("Vampires Helm", 257),
    983: ("Magic Witch Bonnet", 259),
    984: ("Orlean Saga Bonnet", 259),     # same mesh, its own texture (Jrose WCAP 75)
    985: ("gentleman Head", 260),
    986: ("Golden Arrow Head", 261),
    987: ("Billionaire Head", 263),
    988: ("Craftmans Head", 262),
}

# --- 4. shops ---------------------------------------------------------------
GRID_COLS, SELL_SLOTS = 8, 48
ASTRAEA, ASTRAEA_TABS = 4108, (565, 566, 568)
TAB_COLS = (21, 22, 23)
LEGENDARY_TAB, LEGENDARY_CAPTION = 566, "Legendary Crystal lv220"
RETIRED_TAB = 567
KARKIA_ROW = {"cap": 0, "body": 1, "arms": 2, "foot": 3}


def load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def sha(b):
    return hashlib.sha256(b).hexdigest()


def stb_path(name):
    return os.path.join(STB_DIR, name + ".STB")


def zsc_path(name, root=DATA):
    return os.path.join(root, "AVATAR", name + ".ZSC")


def data_file(root, zsc_rel):
    """A ZSC path (`3DDATA\\AVATAR\\...`) -> the file under `root`, a 3DDATA folder."""
    rel = zsc_rel.decode("latin-1").replace("/", "\\")
    if rel.lower().startswith("3ddata\\"):
        rel = rel.split("\\", 1)[1]
    return os.path.join(root, *rel.split("\\"))


def base(p):
    return p.decode("latin-1").replace("/", "\\").rsplit("\\", 1)[-1].upper()


def cell(stb, r, c):
    return stb.get(r, c).decode("latin-1").strip()


def num(stb, r, c):
    v = cell(stb, r, c)
    return int(v) if v.lstrip("-").isdigit() else 0


# ------------------------------------------------------------------ planning
def cosmetic_plan(stbs):
    """{(slot, row): {col: str}} for the twelve cosmetic sets."""
    plan = {}
    for setname, (first, level) in COSMETIC.items():
        lo = max(l for l in VANILLA if l <= level)
        hi = min(l for l in VANILLA if l >= level)
        t = 0.0 if hi == lo else (level - lo) / (hi - lo)
        for ci, cls in enumerate(CLASSES):
            for slot in SLOTS:
                s = stbs[slot]
                a, b = VANILLA[lo] + 30 * ci, VANILLA[hi] + 30 * ci

                def lerp(col):
                    return num(s, a, col) + (num(s, b, col) - num(s, a, col)) * t

                row = first + ci
                want = {
                    COL_LEVEL: str(level),
                    COL_PRICE: str(int(round(lerp(COL_PRICE) / 50.0)) * 50),
                    COL_QUALITY: str(int(round(lerp(COL_QUALITY)))),
                    COL_DURABILITY: str(int(round(lerp(COL_DURABILITY)))),
                    COL_RARE: "1",
                    COL_DEF: str(int(round(lerp(COL_DEF) * COSMETIC_SHARE))),
                    COL_RES: str(int(round(lerp(COL_RES) * COSMETIC_SHARE))),
                }
                for c in COL_BONUS:
                    want[c] = ""
                ability = num(s, a, 24)
                if ability and ability == num(s, b, 24):
                    want[24] = str(ability)
                    want[25] = str(max(1, int(round(lerp(25) * COSMETIC_SHARE))))
                if slot == "foot":
                    want[COL_SPEED] = str(int(round(lerp(COL_SPEED))))
                plan[(slot, row)] = want
    return plan


def legendary_names():
    """{(slot, row): (name, description)}"""
    return {(slot, CRYSTAL_ROW[slot] + ci):
            ("Legendary Crystal %s %s" % (cls, PIECE[slot]), LEGENDARY_DESC[cls])
            for ci, cls in enumerate(CLASSES) for slot in SLOTS}


class Rewire:
    """Rebuilds objects of one of our ZSCs in place, appending any mesh or material
    path it does not hold yet. Paths are resolved by the caller."""

    def __init__(self, name):
        self.name = name
        self.path = zsc_path(name)
        self.original = open(self.path, "rb").read()
        self.z = Zsc(self.path)
        if self.z.rebuild() != self.original[:self.z.obj_end]:
            sys.exit("ABORT: %s does not re-serialise byte for byte" % name)
        self.mesh_idx = {m.upper(): i for i, m in enumerate(self.z.meshes)}
        self.mat_idx = {p.upper(): i for i, (p, _) in enumerate(self.z.materials)}
        self.new_meshes, self.new_mats = [], []
        self.changed = []

    def mesh(self, path):
        k = path.upper()
        if k not in self.mesh_idx:
            self.mesh_idx[k] = len(self.z.meshes) + len(self.new_meshes)
            self.new_meshes.append(path)
        return self.mesh_idx[k]

    def mat(self, path, flags):
        k = path.upper()
        if k not in self.mat_idx:
            self.mat_idx[k] = len(self.z.materials) + len(self.new_mats)
            self.new_mats.append((path, flags))
        return self.mat_idx[k]

    def paths(self, row):
        o = self.z.objects[row]
        return [(self.z.meshes[m].upper(), self.z.materials[t][0].upper()) for m, t, _ in o[1]]

    def place(self, row, cyl, parts, dummies, bb):
        """parts: [(mesh path, (material path, flags), props)]"""
        new = (cyl, [(self.mesh(m), self.mat(*t), p) for m, t, p in parts], dummies, bb)
        old = self.z.objects[row]
        if [(self.z.meshes[m].upper(), self.z.materials[t][0].upper(), p)
                for m, t, p in old[1]] == [(m.upper(), t[0].upper(), p) for m, t, p in parts] \
                and old[0] == cyl and old[2] == dummies and old[3] == bb:
            return False
        self.z.objects[row] = new
        self.changed.append(row)
        return True

    def out(self):
        if self.z.trailing:
            print("   NOTE: %s drops %d trailing bytes" % (self.name, self.z.trailing))
        return self.z.rebuild_with(self.new_meshes, self.new_mats)


class Files:
    """Resolves source paths to ours and records the files to copy."""

    def __init__(self):
        self.copies = {}      # our absolute path -> source absolute path
        self.notes = []

    def resolve(self, src_root, src_path, ours, prefer_dir=None, must_match=True):
        """Our ZSC path for a source file.

        1. a path one of `ours` already references, same name, same bytes;
        2. the source's own relative path (or `prefer_dir` + the name) if we hold that
           file -- byte-identical for a mesh; a texture is accepted as the same art
           (ours are DXT5 re-encodes of the same pictures);
        3. otherwise it is copied there from the source.
        """
        src_file = data_file(src_root, src_path)
        if not os.path.isfile(src_file):
            sys.exit("ABORT: source file missing: %s" % src_file)
        src_bytes = open(src_file, "rb").read()
        name = base(src_path)
        for rw in ours:
            for p in list(rw.z.meshes) + [m for m, _ in rw.z.materials]:
                if base(p) == name:
                    f = data_file(DATA, p)
                    if os.path.isfile(f) and open(f, "rb").read() == src_bytes:
                        return p
        if prefer_dir is not None:
            target = prefer_dir + b"\\" + name.encode("latin-1")
        else:
            target = src_path.decode("latin-1").replace("/", "\\").upper().encode("latin-1")
            if target.startswith(b"3DDATA\\") is False:
                target = b"3DDATA\\" + target.split(b"\\", 1)[1]
        ours_file = data_file(DATA, target)
        if os.path.isfile(ours_file):
            if open(ours_file, "rb").read() != src_bytes:
                if must_match:
                    sys.exit("ABORT: %s differs from the source's %s" % (ours_file, src_file))
                self.notes.append("%s: our copy differs from the source's (same art, "
                                  "kept ours)" % name)
            return target
        self.copies[ours_file] = src_file
        return target


def legendary_objects(rewires, files):
    """Rebuild the 32 Crystal objects (16 rows x 2 sexes) from Brasil's."""
    for slot in SLOTS:
        for sex, zname in zip("MW", ZSCS[slot]):
            src = Zsc(zsc_path(zname, BRASIL_3D))
            rw = rewires[zname]
            twin = rewires[ZSCS[slot][1 if sex == "M" else 0]]
            for ci, cls in enumerate(CLASSES):
                cyl, sparts, sdum, sbb = src.objects[BRASIL_ROW[cls]]
                if not sparts:
                    sys.exit("ABORT: Brasil %s %d has no model" % (zname, BRASIL_ROW[cls]))
                if sdum:
                    sys.exit("ABORT: Brasil %s %d carries dummy points; not expected"
                             % (zname, BRASIL_ROW[cls]))
                parts = []
                for m, t, props in sparts:
                    mp = files.resolve(BRASIL_3D, src.meshes[m], (rw, twin))
                    tpath, flags = src.materials[t]
                    tp = files.resolve(BRASIL_3D, tpath, (rw, twin), must_match=False)
                    parts.append((mp, (tp, flags), props))
                rw.place(CRYSTAL_ROW[slot] + ci, cyl, parts, [], sbb)


def female_210_objects(rewires, files, mcap):
    """LIST_WCAP 981-988 from QQ's geometry and our male textures."""
    rw = rewires["LIST_WCAP"]
    src = Zsc(zsc_path("LIST_WCAP", QQ_3D))
    for row, (_name, qq) in FEMALE_210.items():
        cyl, sparts, sdum, sbb = src.objects[qq]
        male = mcap.z.objects[row][1]
        if len(male) != len(sparts):
            sys.exit("ABORT: WCAP %d: QQ %d has %d parts, our male %d"
                     % (row, qq, len(sparts), len(male)))
        parts = []
        for (m, t, props), (mm, mt, _mp) in zip(sparts, male):
            male_mesh = mcap.z.meshes[mm]
            male_tex, flags = mcap.z.materials[mt]
            if row != 984 and base(src.materials[t][0]) != base(male_tex):
                sys.exit("ABORT: WCAP %d: QQ texture %s vs our male %s"
                         % (row, base(src.materials[t][0]), base(male_tex)))
            if base(src.meshes[m]) == base(male_mesh):
                mp = male_mesh              # a unisex part (the Dealer heads): ours
            else:
                folder = male_mesh.rsplit(b"\\", 1)[0].upper()
                mp = files.resolve(QQ_3D, src.meshes[m], (rw,), prefer_dir=folder)
            parts.append((mp, (male_tex, flags), props))
        rw.place(row, cyl, parts, sdum, sbb)


def shop_plan(sell):
    """{(row, col): str} for LIST_SELL. The cosmetics are sold nowhere: the first cut's
    Junon Polis slots go back to what they held, through `retired_cells`."""
    out = {}
    for s in range(SELL_SLOTS):
        out[(LEGENDARY_TAB, 2 + s)] = ""
        out[(RETIRED_TAB, 2 + s)] = ""
    for slot in SLOTS:
        for ci in range(len(CLASSES)):
            out[(LEGENDARY_TAB, 2 + KARKIA_ROW[slot] * GRID_COLS + ci)] = \
                str(ITEM_TYPE[slot] * 1000 + CRYSTAL_ROW[slot] + ci)
    out[(LEGENDARY_TAB, 0)] = LEGENDARY_CAPTION
    # empty cells are written as "0" where the tab already uses "0" for a blank
    for (r, c), v in list(out.items()):
        if v == "" and c >= 2 and cell(sell, r, c) == "0":
            out[(r, c)] = "0"
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    os.chdir(REPO)                      # add-item-icon.py works from the repo root

    if a.restore:
        return restore()

    stbs = {slot: Stb(stb_path(TABLE[slot])) for slot in SLOTS}
    stls = {slot: Stl(os.path.join(STB_DIR, TABLE[slot] + "_S.STL")) for slot in SLOTS}
    sell = Stb(stb_path("LIST_SELL"))
    sell_stl = Stl(os.path.join(STB_DIR, "LIST_SELL_S.STL"))
    npc = Stb(stb_path("LIST_NPC"))
    for path, t in [(stb_path(TABLE[s]), stbs[s]) for s in SLOTS] + \
            [(stb_path("LIST_SELL"), sell), (stb_path("LIST_NPC"), npc)]:
        if t.to_bytes() != open(path, "rb").read():
            sys.exit("ABORT: %s does not round-trip" % path)

    # ---- sanity: the rows are what this pass was written against
    for setname, (first, _lv) in COSMETIC.items():
        word = {"Steam": "Steam ", "Refined Steam": "Refined Steam ", "Unit Core": ""}[setname]
        for ci, cls in enumerate(CLASSES):
            nm = cell(stbs["body"], first + ci, COL_NAME)
            if setname != "Unit Core" and not nm.startswith(word + cls):
                sys.exit("ABORT: LIST_BODY %d is %r" % (first + ci, nm))
    unit_core = ("Sol Core", "Jupiter Core", "Diana Core", "Pluto Core")
    for ci, nm in enumerate(unit_core):
        if cell(stbs["body"], 258 + ci, COL_NAME) != nm:
            sys.exit("ABORT: LIST_BODY %d is %r" % (258 + ci, cell(stbs["body"], 258 + ci, 0)))
    names = legendary_names()
    for (slot, row), (new, _d) in names.items():
        nm = cell(stbs[slot], row, COL_NAME)
        old = new.replace("Legendary Crystal", "Crystal")
        if nm not in (old, new):
            sys.exit("ABORT: %s %d is %r" % (TABLE[slot], row, nm))
    for row, (nm, _q) in FEMALE_210.items():
        if cell(stbs["cap"], row, COL_NAME) != nm:
            sys.exit("ABORT: LIST_CAP %d is %r" % (row, cell(stbs["cap"], row, 0)))

    # ---- plan the table cells
    cells = {}          # (file key, row, col) -> new str
    for (slot, row), want in cosmetic_plan(stbs).items():
        for c, v in want.items():
            cells[(TABLE[slot], row, c)] = v
    for (slot, row), (new, _d) in names.items():
        cells[(TABLE[slot], row, COL_NAME)] = new
    for (r, c), v in shop_plan(sell).items():
        cells[("LIST_SELL", r, c)] = v
    for c, tab in zip(TAB_COLS, ASTRAEA_TABS):
        cells[("LIST_NPC", ASTRAEA, c)] = str(tab)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {}
    # a cell an earlier run wrote that the plan no longer covers goes back to what it
    # held (the first cut's Junon Polis shop slots); icon cells are tracked on their own
    for key, old in man.get("cells", {}).items():
        t, r, c = key.split(",")
        k = (t, int(r), int(c))
        if k not in cells and not (k[2] == COL_ICON and "%s,%s" % (t, r) in man.get("icons", {})):
            cells[k] = old
    tables = {TABLE[s]: stbs[s] for s in SLOTS}
    tables.update({"LIST_SELL": sell, "LIST_NPC": npc})
    cell_todo = {k: v for k, v in cells.items() if cell(tables[k[0]], k[1], k[2]) != v}

    stl_todo = {}       # (stl file, key, field) -> new str
    for (slot, row), (new, desc) in names.items():
        key = cell(stbs[slot], row, stbs[slot].key_column())
        for field, v in ((0, new), (1, desc)):
            if stls[slot].field(key, field) != v:
                stl_todo[(TABLE[slot] + "_S", key, field)] = v
    lsel = "LSEL%d" % LEGENDARY_TAB
    for li in range(len(sell_stl.langs)):
        if sell_stl.name(lsel, li) != LEGENDARY_CAPTION:
            stl_todo[("LIST_SELL_S", lsel, 0)] = LEGENDARY_CAPTION
    stl_files = {TABLE[s] + "_S": stls[s] for s in SLOTS}
    stl_files["LIST_SELL_S"] = sell_stl

    # ---- plan the models
    rewires = {n: Rewire(n) for s in SLOTS for n in ZSCS[s]}
    files = Files()
    legendary_objects(rewires, files)
    female_210_objects(rewires, files, rewires["LIST_MCAP"])

    # ---- icons: Brasil's own, unless a previous run already placed them
    icon_rows = {}
    for slot in SLOTS:
        brz = Stb(os.path.join(BRASIL, "3DDATA", "STB", TABLE[slot] + ".STB"))
        for ci, cls in enumerate(CLASSES):
            row = CRYSTAL_ROW[slot] + ci
            placed = man.get("icons", {}).get("%s,%d" % (TABLE[slot], row))
            if placed is not None and num(stbs[slot], row, COL_ICON) == placed:
                continue
            icon_rows[(slot, row)] = num(brz, BRASIL_ROW[cls], COL_ICON)

    # ---- report
    print("Cosmetics (rows 250-261, sold nowhere):")
    for setname, (first, level) in COSMETIC.items():
        for ci, cls in enumerate(CLASSES):
            d = sum(int(cells[(TABLE[s], first + ci, COL_DEF)]) for s in SLOTS)
            r = sum(int(cells[(TABLE[s], first + ci, COL_RES)]) for s in SLOTS)
            b = cells[("LIST_BODY", first + ci, 24)], cells[("LIST_BODY", first + ci, 25)]
            print("   lv%-3d %-14s %-8s set DEF %3d RES %3d  body bonus %s:%s"
                  % (level, setname, cls, d, r, *b))
    print("Models:")
    for n, rw in rewires.items():
        if rw.changed:
            print("   %-11s %2d object(s) %s; +%d mesh, +%d material path(s)"
                  % (n, len(rw.changed), rw.changed, len(rw.new_meshes), len(rw.new_mats)))
    for f, s in files.copies.items():
        print("   copy %s <- %s" % (os.path.relpath(f, REPO), s))
    if files.notes:
        print("   %d texture(s) differ from the source's bytes (ours are DXT5 re-encodes "
              "of the same art) -- ours are used" % len(set(files.notes)))
    print("Icons to add: %d" % len(icon_rows))
    print("Table cells to change: %d, STL fields: %d" % (len(cell_todo), len(stl_todo)))

    pending = cell_todo or stl_todo or icon_rows or files.copies or \
        any(rw.changed for rw in rewires.values())
    if a.verify:
        if pending:
            for k, v in list(cell_todo.items())[:20]:
                print("   %s %d col %d: %r, expected %r"
                      % (k[0], k[1], k[2], cell(tables[k[0]], k[1], k[2]), v))
            print("VERIFY FAILED")
            return 1
        print("ALL CHECKS PASSED -- the armour ladder pass is in place.")
        return 0
    if not pending:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    # ---- write
    os.makedirs(os.path.join(BACKUP_DIR, "orig"), exist_ok=True)
    man.setdefault("cells", {})
    man.setdefault("stl", {})
    man.setdefault("zsc", {})
    man.setdefault("copied", [])
    man.setdefault("icons", {})
    man.setdefault("icon_old", {})

    if icon_rows:
        ii = load("import-item")
        for (slot, row), src_idx in sorted(icon_rows.items()):
            label = cells[(TABLE[slot], row, COL_NAME)].lower()
            idx = ii.copy_source_icon(BRASIL, src_idx, label, False)
            key = "%s,%d" % (TABLE[slot], row)
            man["icon_old"].setdefault(key, cell(stbs[slot], row, COL_ICON))
            man["icons"][key] = idx
            cell_todo[(TABLE[slot], row, COL_ICON)] = str(idx)
        bak = os.path.join(DATA, "CONTROL", "RES", "ITEM1.TSI.bak-icons")
        if os.path.exists(bak):           # pack.ps1 refuses a .bak under data/
            shutil.move(bak, os.path.join(BACKUP_DIR, "ITEM1.TSI.bak-icons"))

    for (tname, row, col), v in cell_todo.items():
        key = "%s,%d,%d" % (tname, row, col)
        man["cells"].setdefault(key, cell(tables[tname], row, col))
        tables[tname].set(row, col, v.encode("latin-1"))
    for tname, t in tables.items():
        if any(k[0] == tname for k in cell_todo):
            open(stb_path(tname), "wb").write(t.to_bytes())

    for (sname, key, field), v in stl_todo.items():
        st = stl_files[sname]
        mk = "%s,%s,%d" % (sname, key, field)
        man["stl"].setdefault(mk, [st.field(key, field, li) for li in range(len(st.langs))])
        st.set_field(key, field, v)
    for sname, st in stl_files.items():
        if any(k[0] == sname for k in stl_todo):
            open(os.path.join(STB_DIR, sname + ".STL"), "wb").write(st.to_bytes())

    for dst, src in files.copies.items():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        man["copied"].append(os.path.relpath(dst, REPO))
    for n, rw in rewires.items():
        if not rw.changed:
            continue
        orig = os.path.join(BACKUP_DIR, "orig", n + ".ZSC")
        if n not in man["zsc"]:
            open(orig, "wb").write(rw.original)
        out = rw.out()
        open(rw.path, "wb").write(out)
        man["zsc"][n] = sha(out)

    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("written (undo: --restore). Restart the servers and re-bake the VFS.")
    return 0


def restore():
    if not os.path.isfile(MANIFEST):
        print("nothing to restore (%s not found)" % MANIFEST)
        return 0
    man = json.load(open(MANIFEST))
    by_table = {}
    for key, old in man["cells"].items():
        t, r, c = key.split(",")
        by_table.setdefault(t, []).append((int(r), int(c), old))
    for key, old in man.get("icon_old", {}).items():
        t, r = key.split(",")
        by_table.setdefault(t, []).append((int(r), COL_ICON, old))
    for t, items in by_table.items():
        s = Stb(stb_path(t))
        for r, c, old in items:
            s.set(r, c, old.encode("latin-1"))
        open(stb_path(t), "wb").write(s.to_bytes())
        print("   restored %d cell(s) in %s.STB" % (len(items), t))
    by_stl = {}
    for key, olds in man["stl"].items():
        sname, k, field = key.split(",")
        by_stl.setdefault(sname, []).append((k, int(field), olds))
    for sname, items in by_stl.items():
        p = os.path.join(STB_DIR, sname + ".STL")
        st = Stl(p)
        for k, field, olds in items:
            for li, old in enumerate(olds):
                st.set_field(k, field, old, li)
        open(p, "wb").write(st.to_bytes())
        print("   restored %d field(s) in %s.STL" % (len(items), sname))
    for n, digest in man["zsc"].items():
        p = zsc_path(n)
        if sha(open(p, "rb").read()) != digest:
            print("   SKIP %s: changed since this pass wrote it" % n)
            continue
        shutil.copy2(os.path.join(BACKUP_DIR, "orig", n + ".ZSC"), p)
        print("   restored %s.ZSC" % n)
    for rel in man["copied"]:
        p = os.path.join(REPO, rel)
        if os.path.isfile(p):
            os.remove(p)
    if man["copied"]:
        print("   removed %d copied file(s)" % len(man["copied"]))
    if man.get("icons"):
        print("   the %d appended icon(s) stay in ITEM1.TSI, unreferenced" % len(man["icons"]))
    os.remove(MANIFEST)
    print("restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
