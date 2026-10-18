"""Finish the Dealer line: Exceed Break for the Bourgeois, and Calibrated Burst's new look.

    python scripts/import-exceed-break.py --dry-run
    python scripts/import-exceed-break.py            # a fresh install, or upgrades one in place
    python scripts/import-exceed-break.py --verify
    python scripts/import-exceed-break.py --restore

then the icon (that tool owns the atlas; the PNG is cut by --icon-png):

    python scripts/import-exceed-break.py --icon-png build/exceed-break/icon.png
    python scripts/add-skill-icon.py build/exceed-break/icon.png --name exceed_break --skill-row <first>-<last>

Why
---
After Photon Cannon (`import-artisan-photon-cannon.py`) the user asked to finish the
Dealer line: the Bourgeois's own Jrose animation, and a less ordinary Calibrated Burst.
Both were picked in game from GM test rows (2026-10-17).

* **Exceed Break** is Jrose's Bourgeois skill 6151 ("a great barrage that destroys
  everything in front; sets the target burning"). Its identity is the Bourgeois's:
  **launcher only** -- the gun/launcher masteries are shared, so skills are the only place
  the two jobs part -- and it **costs Zuly as well as MP**, like Zuly Storm: you pay for
  the shells.

  **Version 2 (2026-10-18): the frontal barrage, as Jrose built it.** Version 1 was a
  type-3 shot with Fire Burn's fireball and a Burning splash around the target; the user
  felt it was not what Jrose meant, and it was not:

  - Jrose's 6151 is type 7 with the packed scope `40002500`, which its engine reads as a
    rectangle in front of the caster. Ours reads it too now: a SKILL_SCOPE of 10000 or
    more is **length x 10000 + width** in cm, a strip from the caster toward the spot the
    skill was aimed at (io_skill.h SKILL_SCOPE_FRONTAL, `CObjCHAR::Skill_DamageToAROUND`;
    no skill had such a scope before, so no other skill changed). Every monster in the
    strip takes the hit, the `_mana_hit_04` burst and a Burning roll. The strip grows with
    rank, 25 x 15 m -> 40 x 25 m (Jrose's full size from rank 1 cleared screens).
  - Jrose's row has no area effect; in game "the player just holds the launcher in the
    air". `exceed_break_wave.eft` (FILE_EFFECT 2900, blank in ours, Jrose and 667; authored
    here with `rosefmt.eft.build`) is a rolling wave: a muzzle flash, then ten rows of fire
    blasts 4 m apart from 3 to 39 m ahead, two or three lanes across, 20 ms apart --
    pieces of Jrose's own Exceed Break blast (`_blowup_12`, `_spreas_12`; its LIST_EFFECT
    330 is *named* Exceed Break) and `_fire_07` flames. A character's front is the model's
    -Y (`zz_model::pivot_front_axis`). It plays from casting-effect slot 2 (col 62), on
    frame event 74, and stays in the world where it was cast.
  - **The server applies a skill's damage when its action motion starts** (`Do_SKILL`:
    Set_MOTION, then Skill_START), and the client shows a hit at once if it arrives after
    the cast (`Recv_gsv_DAMAGE_OF_SKILL`). Jrose's shot `skill_cannon_m03` fires at frame
    20 of 68, so the digits beat the cannon by half a second; moving the clip's events
    could not help. The shot is **split at its firing frame** (`rosefmt.zmo.sliced`):
    `skill_cannon_m03_windup` (frames 0-19) is the cast's loop, played once (cols 54/55),
    and `skill_cannon_m03_shot` (20-67) the action, with the wave (74) at frame 0, the area
    event (24) at 1 and Jrose's fire sound (34) at 2 -- FILE_MOTION 610 / 609, TYPE_MOTION
    100 / 99, cut from Jrose's original. Photon Cannon's `skill_cannon_m03` (gun fire
    event 26) is untouched. The cast plays at 120%: the wind-up now counts as cast time.
  - A type-7 skill aims where the target stood at the key press; for a strip only the
    direction matters, so a moving target barely changes what it hits.

* **Calibrated Burst** keeps `gun_3attack` -- no dump has a new rapid-fire gun clip
  (the only gun-adjacent one is Jrose's crossbow "Shot Master", a 1.9 s aim and a single
  shot) -- and takes the "Nightmare" effect kit of four tried: the wind-up flare is
  Jrose's `_mana_hit_05` (the cannon-blast burst), the round Jrose Night Mare Blitz's
  `_mana_firing_00` (LIST_EFFECT 252, already ours). Only cols 56 and 71 change, on all
  ten ranks; `import-artisan-skill.py`'s row template carries the same values.

Jrose's FILE_EFFECT numbering matches ours and both Jrose effects' rows are blank here,
so `_heavy_casting_03` and `_mana_hit_05` go in at Jrose's own rows 1047 and 1126.

The numbers (Exceed Break, ranks 1 -> 10, linear)
-------------------------------------------------
    power 600 -> 1400    cd 14 -> 11 s    MP 60 -> 120 + Zuly 800 -> 6000
    strip 25 x 15 m -> 40 x 25 m in front, reach 16 m
    Burning (150/s) for 6 -> 10 s on every monster hit, ratio 60 -> 100
    Bourgeois (class 67), launcher, level 100, Gun Smash rank 5

Version 1 was sized in the combat sim at 800 -> 1800 on one target (+16% / +29% plain /
star at level 200). Version 2 hits a whole strip, so it takes ~0.75x per target; see SIM
in the commit and `scripts/CLAUDE.md`. The sim is one-on-one: the strip is beyond it.

How a player gets it
--------------------
* Book LIST_USEITEM 856 (blank; copy of Refine Item's 849), sold in Darren's tab 468
  col 25, beside Zuly Storm's book.
* Trees: UI2 builds itself from the class set and prerequisite. The classic tree's node
  and painted box are owned by `scripts/dealer-tree-layout.py`.
* Icon: Jrose's own (its sprite 255, an explosion), appended by `add-skill-icon.py`;
  this script writes the resulting index `ICON` so a re-import keeps it.

What it changes
---------------
    LIST_SKILL.STB / _S.STL    10 rows appended, 1 key; Calibrated Burst cols 56, 71 x 10
    LIST_USEITEM.STB / _S.STL  row 856, key LUSE856;   LIST_SELL.STB tab 468 col 25
    FILE_EFFECT.STB            rows 1047, 1126 (Jrose's numbers), 2900 (the wave)
    TYPE_MOTION / FILE_MOTION  rows 99, 100 / 609, 610 (the split shot)
    EFFECT, PARTICLES, MOTION  _heavy_casting_03.eft, _mana_hit_05.eft and their .ptl (4
                               files); exceed_break_wave.eft; the two clips

Run on an install of version 1 it upgrades in place: it rewrites the changed cells of its
own rows (they no longer sit at the end of LIST_SKILL, so it cannot truncate and
re-append) and records every old value. Cell-level undo and the copied files in
`build/exceed-break/`. Deploy: the sho_gameserver with the frontal area, restart, re-bake,
then `dealer-tree-layout.py` for the classic tree; the client with the frontal area for
the "40 x 25 m" tooltip.
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
from rosefmt import eft, zmo  # noqa: E402
import rosedata as ro  # noqa: E402

_spec = importlib.util.spec_from_file_location("rd", os.path.join(HERE, "rose-data-reader.py"))
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

DATA = os.path.join(ROOT, "data")
STB_DIR = os.path.join(DATA, "3DDATA", "STB")
JROSE = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
J_STB = os.path.join(JROSE, "3Ddata", "STB")
OUT = os.path.join(ROOT, "build", "exceed-break")
MANIFEST = os.path.join(OUT, "manifest.json")
VERSION = 2

FX_ROWS = [1047, 1126]          # _heavy_casting_03, _mana_hit_05 -- at Jrose's numbers

# the split shot: Jrose's skill_cannon_m03 cut at its firing frame
SRC_CLIP = os.path.join(JROSE, "3Ddata", "MOTION", "AVATAR", "skill_cannon_m03.ZMO")
FIRE_FRAME = 20
WINDUP = (r"3DDATA\MOTION\AVATAR\skill_cannon_m03_windup.ZMO", 610, 100)   # FM, TM
SHOT = (r"3DDATA\MOTION\AVATAR\skill_cannon_m03_shot.ZMO", 609, 99)
SHOT_EVENTS = {0: 74, 1: 24, 2: 34}   # the wave, the area event, Jrose's fire sound

# the rolling wave
WAVE_FE = 2900
WAVE_REL = r"3DDATA\EFFECT\exceed_break_wave.eft"
ROW_DELAY = 20                  # ms between rows: 39 m in 0.18 s
PTL = r"3DDATA\EFFECT\PARTICLES\{}.ptl"

# Calibrated Burst, ranks 1-10: the "Nightmare" kit
CB_ROWS = range(7002, 7012)
CB_LOOK = {56: 1126, 71: 252}   # wind-up flare _mana_hit_05; round _mana_firing_00

RANKS = 10
NAME = "Exceed Break"
DESC = ("Load the launcher with shells that cost real money and fire a barrage that rolls "
        "through everything in front of you, setting it Burning. Costs Zuly as well as MP.")
CLASS_BOURGEOIS, LEVEL = 67, 100
PREREQ = (2281, 5)              # Gun Smash rank 5 (was Zuly Storm 5)
ICON = 522                      # Jrose sprite 255 via add-skill-icon.py
JROSE_ICON = 255
AT_MP, AT_LEVEL, AT_MONEY = 17, 31, 40
ST_BURNING = 62


def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


POWER = lin(600, 1400)          # v1 (one target): 800 -> 1800
RELOAD = lin(70, 55)            # x0.2 s -> 14 -> 11 s
MP = lin(60, 120)
ZULY = lin(800, 6000)
SP = lin(35, 130)
STRIP_LEN = lin(2500, 4000)     # cm in front
STRIP_WIDTH = lin(1500, 2500)   # cm across
SCOPE = [l * 10000 + w for l, w in zip(STRIP_LEN, STRIP_WIDTH)]   # io_skill.h SKILL_SCOPE_FRONTAL
REACH = 1600                    # Jrose's
DURATION = lin(6, 10)
SUCCESS = lin(60, 100)

BOOK, BOOK_TEMPLATE = 856, 849
SHOP_TAB, SHOP_COL = 468, 25    # beside Zuly Storm's book (col 24)

tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def jload(name):
    return rd.Stb(os.path.join(J_STB, name), "cp932")


def data_path(rel):
    return os.path.join(DATA, rel.replace("\\", "/"))


# --- table cells ---------------------------------------------------------------------

def table_cells(base):
    """Every cell this import owns outside its own LIST_SKILL rows, as (table, row, col, value)."""
    jfe = jload("FILE_EFFECT.STB")
    fe, sk, fm, tm = load("FILE_EFFECT.STB"), load("LIST_SKILL.STB"), load("FILE_MOTION.STB"), load("TYPE_MOTION.STB")
    out = []
    for r in FX_ROWS:
        want = [jfe.d[r][c] for c in range(fe.cols)]
        if any(fe.d[r]) and fe.d[r] != want:
            sys.exit(f"FILE_EFFECT {r} is in use here ({fe.d[r][1]!r}) -- refusing")
        out += [("FILE_EFFECT.STB", r, c, v) for c, v in enumerate(want)]
    if any(fe.d[WAVE_FE]) and fe.d[WAVE_FE][1] != WAVE_REL.encode():
        sys.exit(f"FILE_EFFECT {WAVE_FE} is in use -- refusing")
    out += [("FILE_EFFECT.STB", WAVE_FE, c, WAVE_REL.encode() if c == 1 else
             (b"exceed_break_wave" if c == 0 else b"")) for c in range(fe.cols)]
    for rel, fm_row, tm_row in (WINDUP, SHOT):
        if any(fm.d[fm_row]) and fm.d[fm_row][0] != rel.encode():
            sys.exit(f"FILE_MOTION {fm_row} is in use -- refusing")
        out += [("FILE_MOTION.STB", fm_row, c, rel.encode() if c == 0 else b"") for c in range(fm.cols)]
        if any(tm.d[tm_row]) and set(tm.d[tm_row]) != {str(fm_row).encode()}:
            sys.exit(f"TYPE_MOTION {tm_row} is in use -- refusing")
        out += [("TYPE_MOTION.STB", tm_row, c, str(fm_row).encode()) for c in range(tm.cols)]
    for r in CB_ROWS:
        if sk.d[r][0] != b"Calibrated Burst":
            sys.exit(f"LIST_SKILL {r} is not Calibrated Burst -- refusing")
        out += [("LIST_SKILL.STB", r, c, str(v).encode()) for c, v in CB_LOOK.items()]
    ui, sell = load("LIST_USEITEM.STB"), load("LIST_SELL.STB")
    code = str(10000 + BOOK).encode()
    over = {0: NAME.encode(), 20: str(base).encode(), 27: f"LUSE{BOOK}".encode()}
    out += [("LIST_USEITEM.STB", BOOK, c, over.get(c, ui.d[BOOK_TEMPLATE][c]))
            for c in range(ui.cols)]
    out.append(("LIST_SELL.STB", SHOP_TAB, SHOP_COL, code))
    return out


def check_fresh_book():
    ui, sell = load("LIST_USEITEM.STB"), load("LIST_SELL.STB")
    if any(ui.d[BOOK]):
        sys.exit(f"LIST_USEITEM {BOOK} is in use ({ui.d[BOOK][0]!r}) -- refusing")
    code = str(10000 + BOOK).encode()
    for t in ("LIST_SELL.STB", "ITEM_DROP.STB"):
        hits = [r for r in range(load(t).rows) if code in load(t).d[r]]
        if hits:
            sys.exit(f"{t} rows {hits} already name item 10:{BOOK} -- refusing")
    if sell.d[SHOP_TAB][SHOP_COL].strip(b"0"):
        sys.exit(f"shop tab {SHOP_TAB} col {SHOP_COL} holds {sell.d[SHOP_TAB][SHOP_COL]!r}")


def skill_rows(base):
    rows = []
    for n in range(RANKS):
        c = {0: NAME, 1: base, 2: n + 1, 3: SP[n],
             4: 1,                  # SKILL_TAB_TYPE: the attack tab (blank = Basic)
             5: 7, 6: REACH, 7: 5, 8: SCOPE[n], 9: POWER[n], 10: 1,
             11: ST_BURNING, 13: SUCCESS[n], 14: DURATION[n], 15: 1,
             16: AT_MP, 17: MP[n], 18: AT_MONEY, 19: ZULY[n], 20: RELOAD[n],
             29: 2,                 # SKILL_ACTION_MODE: back to the running command, like Luna Stone
             30: 233,               # launcher only
             51: ICON,
             # stock launcher wind-up, Jrose's cast flare, then Jrose's wind-up once (the
             # cast loop) and the shot from its firing frame; the wave on cast slot 2
             52: 95, 53: 120, 54: WINDUP[2], 55: 1, 56: 1047, 57: 3, 58: 131,
             62: WAVE_FE, 63: 999,
             68: SHOT[2], 69: 140, 70: 1,
             73: 148,                       # the cannon's fire sound
             74: 1125, 75: 999, 76: 67,     # _mana_hit_04 on every monster hit, as Jrose
             86: f"LSkill{base}"}
        if n == 0:
            c.update({35: CLASS_BOURGEOIS, 39: PREREQ[0], 40: PREREQ[1],
                      45: AT_LEVEL, 46: LEVEL})
        rows.append([str(c.get(i, "")).encode("latin-1") for i in range(87)])
    return rows


# --- generated and copied files ------------------------------------------------------

def jrose_files():
    jfe = jload("FILE_EFFECT.STB")
    efts = [jfe.s(r, 1).strip().replace("\\", "/") for r in FX_ROWS]
    uniq = {}
    for f in sorted(ro.effect_chain(efts, JROSE)):
        uniq.setdefault(ro.norm(f).replace("//", "/"), f.replace("\\\\", "\\").replace("//", "/"))
    return sorted(uniq.values())


def clips():
    """(windup, shot) cut from Jrose's original shot at its firing frame."""
    raw = open(SRC_CLIP, "rb").read()
    ev = zmo.events(raw)[1]
    if not ev or ev[FIRE_FRAME] != 24:
        sys.exit(f"Jrose's skill_cannon_m03 lacks its area event (frame {FIRE_FRAME} = 24) -- refusing")
    shot = zmo.sliced(raw, FIRE_FRAME, zmo.read_header(raw)[1])
    changes = {i: 0 for i, e in enumerate(zmo.events(shot)[1]) if e in (24, 34, 74)}
    changes.update(SHOT_EVENTS)
    return zmo.sliced(raw, 0, FIRE_FRAME), zmo.with_events(shot, changes)


def wave_bytes():
    """The rolling wave: a muzzle flash, then rows of fire blasts marching down -Y."""
    parts = []

    def blast(x, y, z, delay, fire=True):
        parts.append(dict(ptl=PTL.format("_blowup_12"), pos=(x, y, z), delay=delay))
        parts.append(dict(ptl=PTL.format("_spreas_12"), pos=(x, y, z), delay=delay))
        if fire:
            parts.append(dict(ptl=PTL.format("_fire_07"), pos=(x, y, 0.0), delay=delay))

    blast(0.0, -150.0, 110.0, 0, fire=False)              # the muzzle
    for k in range(10):
        lanes = (-700.0, 700.0) if k % 2 == 0 else (-1100.0, 0.0, 1100.0)
        for x in lanes:
            blast(x, -(300.0 + 400.0 * k), 30.0, ROW_DELAY * k)
    return eft.build(dict(name="exceed_break_wave", particles=parts, meshes=[]))


def generated():
    windup, shot = clips()
    return {WINDUP[0]: windup, SHOT[0]: shot, WAVE_REL: wave_bytes()}


def write_files(files_new):
    for f in files_new:
        d = ro.rel_path(DATA, f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(ro.rel_path(JROSE, f), d)
    for rel, blob in generated().items():
        open(data_path(rel), "wb").write(blob)


# --- the icon ------------------------------------------------------------------------

def icon_png(path):
    import numpy as np
    from PIL import Image
    spec = importlib.util.spec_from_file_location("usi", os.path.join(HERE, "upgrade-skill-icons.py"))
    usi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(usi)
    cell = usi.Atlas(os.path.join(JROSE, "3Ddata")).cell(JROSE_ICON)
    if cell is None or usi.is_blank(cell):
        sys.exit(f"Jrose sprite {JROSE_ICON} is blank or missing")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Image.fromarray(np.clip(cell, 0, 255).astype(np.uint8), "RGB").save(path)
    print(f"wrote {path}")


# --- main ----------------------------------------------------------------------------

def print_table(base):
    print(f"{NAME} v{VERSION}: LIST_SKILL {base}-{base + RANKS - 1}, book {BOOK}, tab {SHOP_TAB} col {SHOP_COL}")
    print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'Zuly':>6}{'strip m':>10}{'dur':>5}{'ratio':>7}{'SP':>5}")
    for n in range(RANKS):
        print(f"  {n + 1:>4}{POWER[n]:>7}{RELOAD[n] * 0.2:>6.1f}{MP[n]:>5}{ZULY[n]:>6}"
              f"{STRIP_LEN[n] / 100:>5.0f}x{STRIP_WIDTH[n] / 100:<4.0f}{DURATION[n]:>5}{SUCCESS[n]:>7}{SP[n]:>5}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--icon-png", metavar="PATH", help="write Jrose's icon as a 40x40 PNG and stop")
    args = ap.parse_args()
    if args.icon_png:
        return icon_png(args.icon_png)
    m = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else None
    if args.restore:
        return restore(m)
    if args.verify:
        return verify(m)
    if m:
        return upgrade(m, args.dry_run)

    sk = load("LIST_SKILL.STB")
    base = sk.rows
    check_fresh_book()
    cells = [(t, r, c, v) for t, r, c, v in table_cells(base) if load(t).d[r][c] != v]
    new_files = [f for f in jrose_files() if not os.path.isfile(ro.rel_path(DATA, f))]
    rows = skill_rows(base)
    print_table(base)
    print(f"  Calibrated Burst rows {CB_ROWS.start}-{CB_ROWS.stop - 1}: cols {CB_LOOK}")
    print(f"  {len(cells)} cells in place, {len(new_files)} files to copy, 3 to generate")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    write_files(new_files)
    undo = [[t, r, c, load(t).d[r][c].hex(), v.hex()] for t, r, c, v in cells]
    for t, r, c, v in cells:
        load(t).d[r][c] = v
    sk.grow_to(base + RANKS)
    for n, r in enumerate(rows):
        sk.d[base + n] = r
    for t in {x[0] for x in cells} | {"LIST_SKILL.STB"}:
        load(t).save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL"))
    t.append(f"LSkill{base}", base, NAME, DESC)
    t.save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_USEITEM_S.STL"))
    t.append(f"LUSE{BOOK}", BOOK, NAME, DESC)
    t.save(False, keep_backup=False)
    json.dump(dict(base=base, version=VERSION, cells=undo, files=new_files + list(generated())),
              open(MANIFEST, "w"), indent=1)
    print(f"done -- now the icon: --icon-png, then add-skill-icon.py ... --skill-row "
          f"{base}-{base + RANKS - 1}; restart the server, re-bake, then scripts/dealer-tree-layout.py")


def upgrade(m, dry_run):
    """Bring an earlier install to VERSION in place: rewrite the changed cells of its own
    rows and add the cells and files it lacks, recording every old value."""
    sk = load("LIST_SKILL.STB")
    base = m["base"]
    if any(sk.d[base + n][0] != NAME.encode() for n in range(RANKS)):
        sys.exit(f"rows {base}-{base + RANKS - 1} are not {NAME} -- refusing")
    rows = skill_rows(base)
    cells = [("LIST_SKILL.STB", base + n, c, v) for n, r in enumerate(rows) for c, v in enumerate(r)]
    cells += table_cells(base)
    cells = [(t, r, c, v) for t, r, c, v in cells if load(t).d[r][c] != v]
    new_files = [f for f in jrose_files() if not os.path.isfile(ro.rel_path(DATA, f))]
    stale = [rel for rel, blob in generated().items()
             if not os.path.isfile(data_path(rel)) or open(data_path(rel), "rb").read() != blob]
    stl = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL")).by_key(1).get(f"LSkill{base}")
    print_table(base)
    print(f"  upgrade from v{m.get('version', 1)}: {len(cells)} cells, {len(new_files)} files to copy, "
          f"{len(stale)} to (re)generate, description {'current' if stl and stl[1] == DESC else 'to update'}")
    if dry_run:
        print("dry run -- nothing written")
        return
    if not cells and not new_files and not stale and stl and stl[1] == DESC:
        print("already current -- nothing to do")
        return
    write_files(new_files)
    undo = [[t, r, c, load(t).d[r][c].hex(), v.hex()] for t, r, c, v in cells]
    for t, r, c, v in cells:
        load(t).d[r][c] = v
    for t in {x[0] for x in cells}:
        load(t).save(False, keep_backup=False)
    for name, key, row in (("LIST_SKILL_S.STL", f"LSkill{base}", base), ("LIST_USEITEM_S.STL", f"LUSE{BOOK}", BOOK)):
        t = Stl(os.path.join(STB_DIR, name))
        t.remove([key])
        t.append(key, row, NAME, DESC)
        t.save(False, keep_backup=False)
    seen = {tuple(x[:3]) for x in m["cells"]}
    m["cells"] += [x for x in undo if tuple(x[:3]) not in seen]   # keep the oldest original
    m["files"] = sorted(set(m["files"]) | set(new_files) | set(generated()))
    m["version"] = VERSION
    json.dump(m, open(MANIFEST, "w"), indent=1)
    print(f"upgraded to v{VERSION} -- restart the server (new sho_gameserver), re-bake")


def restore(m):
    if not m:
        sys.exit("no manifest -- nothing to restore")
    sk = load("LIST_SKILL.STB")
    base = m["base"]
    tail = b"\x00\x00" * RANKS
    if sk.rows != base + RANKS or not sk.header.endswith(tail):
        sys.exit("rows were appended after this import -- refusing to truncate")
    sk.header, sk.d, sk.rows = sk.header[:-len(tail)], sk.d[:base], base
    if sk.rownames:
        del sk.rownames[-RANKS:]
    for t, r, c, old, _ in m["cells"]:
        if t == "LIST_SKILL.STB" and r >= base:
            continue                     # the truncated rows themselves
        load(t).d[r][c] = bytes.fromhex(old)
    for t in {x[0] for x in m["cells"]} | {"LIST_SKILL.STB"}:
        load(t).save(False, keep_backup=False)
    for name, key in (("LIST_SKILL_S.STL", f"LSkill{base}"), ("LIST_USEITEM_S.STL", f"LUSE{BOOK}")):
        t = Stl(os.path.join(STB_DIR, name))
        t.remove([key])
        t.save(False, keep_backup=False)
    for f in m["files"]:
        p = ro.rel_path(DATA, f)
        if os.path.isfile(p):
            os.remove(p)
    os.remove(MANIFEST)
    print("restored: skill rows, Calibrated Burst's look, book, shop, effects, clips, files")


def verify(m):
    if not m:
        sys.exit("not imported")
    ok = True
    sk = load("LIST_SKILL.STB")
    rows = skill_rows(m["base"])
    for n in range(RANKS):
        r = m["base"] + n
        diff = [c for c in range(87) if c != 51 and sk.d[r][c] != rows[n][c]]
        if diff:
            ok = False
            print(f"  row {r} ({NAME} rank {n + 1}) differs in cols {diff} -- run without --verify to upgrade")
    for t, r, c, v in table_cells(m["base"]):
        if load(t).d[r][c] != v:
            ok = False
            print(f"  {t} {r}/{c} differs")
    for f in jrose_files():
        if not os.path.isfile(ro.rel_path(DATA, f)):
            ok = False
            print(f"  missing {f}")
    for rel, blob in generated().items():
        if not os.path.isfile(data_path(rel)) or open(data_path(rel), "rb").read() != blob:
            ok = False
            print(f"  {rel} is missing or stale")
    for name, key in (("LIST_SKILL_S.STL", f"LSkill{m['base']}"), ("LIST_USEITEM_S.STL", f"LUSE{BOOK}")):
        if not Stl(os.path.join(STB_DIR, name)).has(key):
            ok = False
            print(f"  {name} lacks {key}")
    icon = int(sk.d[m["base"]][51] or b"0")
    if icon != ICON:
        print(f"  note: icon is {icon}, not {ICON} -- add it with add-skill-icon.py (see the docstring)")
    print("verify:", "ok" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
