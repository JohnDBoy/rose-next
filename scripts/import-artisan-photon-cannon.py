"""Import Photon Cannon, the Artisan's bazooka, from the Jrose client.

    python scripts/import-artisan-photon-cannon.py --dry-run
    python scripts/import-artisan-photon-cannon.py
    python scripts/import-artisan-photon-cannon.py --verify
    python scripts/import-artisan-photon-cannon.py --restore

then the icon (that tool owns the atlas and its undo; the PNG is written by --icon-png):

    python scripts/import-artisan-photon-cannon.py --icon-png build/artisan-photon-cannon/icon.png
    python scripts/add-skill-icon.py build/artisan-photon-cannon/icon.png --name photon_cannon --skill-row <first>-<last>

Why
---
The Artisan had one exclusive attack skill (Calibrated Burst) against three to five for
every other class, and the user's identity for it is "the crafter": a class that
*builds* its weapons. Jrose (2024) carries exactly that -- "Photon Wave" (LIST_SKILL
4271, class 68, gun + launcher): the Artisan hauls out a bazooka and fires it. It plays
a three-part animation no other dump has (`skill_cannon_m01` wind-up 2.7 s, `m02`
loop, `m03` shot 2.2 s), and its cast effect `at_skill_cannon.eft` is a real bazooka
*mesh* (ZMS0008 with its own ZMO0002) plus a laser, ground sigils and six particle
systems. Presentation only is taken; every number is ours.

What changed from Jrose's skill, and why (two in-game test rounds, 2026-10-17)
----------------------------------------------------------------------------
* **Single target, not an area at a spot.** Jrose's is type 7: the client sends the
  target's position *at the key press* (`CSkillCommand::Execute`) and the server
  detonates there when the 2.7 s wind-up ends (`Skill_DamageToAROUND(m_PosGOTO)`), so
  a monster that moved is missed -- 3 of 4 test casts hit nothing -- and a position
  skill fires no projectile (`CFireToPositionSkill::Action` needs a target), so the
  digits popped before the shot. Here it is type 3 on the target.
* **The shot clip fires on event 26.** A gun skill launches its bullet on frame event 26
  (`ActionImmediateSkill`); Jrose's `m03` carries 24 (spell cast) and 34 (fire sound),
  made for its type 7, so a type-3 copy never launched and its damage waited for the
  10 s `projectile timeout discard`. Our copy of `m03` has frame 20 rewritten 24 -> 26
  (`rosefmt.zmo.with_events`); 26 is in the server's attack-frame list as well, so the
  damage timing there does not move.
* **SKILL_ACTION_MODE 1** (attack the target afterwards). Mode 2 returns to the command
  before the skill -- "stop" when it opens a fight -- so the Artisan stood idle until
  the monster's first hit.
* **The area survives as a debuff.** A type-3 skill with SKILL_SCOPE set damages only
  its target, but `Skill_ChangeIngSTATUS` applies its status to every enemy within the
  scope *of the target* (Final Strike and Poison Fang use the same rule): Accuracy
  Down (status 25, `AT_HIT`), "the flash blinds them". Nothing in the gun line used
  it, and it protects a fragile class -- the pack misses more.

The numbers
-----------
Ranks 1 -> 10, linear:

    power 700 -> 1600    cd 20 -> 15 s    MP 90 -> 170
    Accuracy Down 15 -> 25% for 8 -> 12 s within 4 -> 6 m of the target
    success ratio 70 -> 110 (Artisan INT is ~15: 100 lands ~85% at lv 100, ~58% at 200)

**The animation is sped up: wind-up x1.6, shot x1.4** (SKILL_ANI_CASTING_SPEED 160,
SKILL_ANI_ACTION_SPEED 140), so the cast takes ~3.3 s instead of ~5 s (2.7 + 0.1 + 2.2
at Jrose's 100). At full length it was a DPS trap: the combat sim (auto-builds, typical
play, gun) had the Artisan *lose* 9-25% on plain monsters and 4-10% on stars from level
130, because five seconds of wind-up is four Gun Smashes or Sniping Shots. Power alone
could not fix it without a one-shot (x1.5: +96% at 100, -10% at 200). Sped up, with the
power above, against no Photon Cannon:

    level              100     130     160     200
    plain monsters    +65%    +22%    +10%    +12%
    star monsters     +33%    +14%    +20%    +12%

The bazooka mesh runs on its own clock, so at these speeds it may linger a moment past
the shot -- the in-game check for this choice.

Gates: Artisan (class 68), level 100, Calibrated Burst rank 5 -- the burst leads to the
cannon, and its own gate is Craft Mastery rank 6, so the chain stays the crafter's.

How a player gets it
--------------------
* **Book.** Rank 1 of a class skill is learned only from its book (`CLI_SKILL_LEARN_REQ`
  is compiled out on the server). LIST_USEITEM 855 (blank) is a copy of Refine Item's
  book 849, sold in Darren's second-job tab 468 col 49, beside Calibrated Burst's.
* **Trees.** UI2 builds itself from the class set and prerequisite columns. The classic
  tree's node and painted box are owned by `scripts/dealer-tree-layout.py` (run it after
  the imports) since 2026-10-17, when the user moved the Dealer's new skills: this one
  now sits after Calibrated Burst on the Gunshot Mastery page.
* **Icon:** Jrose's own (sprite 867 of its SKILLICON.TSI: the Artisan aiming the glowing
  cannon, with Jrose's "U" badge for its unique skills -- the user kept the badge),
  cut to a PNG by `--icon-png` and appended by `add-skill-icon.py`, which owns the
  atlas. This script writes the resulting index `ICON` directly so a re-import keeps it.
  Note `upgrade-skill-icons.py --restore` restores the sheets whole-file and would drop
  it (that script's own docstring warns of exactly this).

What it changes
---------------
    LIST_SKILL.STB / _S.STL      10 rows appended, 1 key
    LIST_USEITEM.STB / _S.STL    row 855 (book), key LUSE855
    LIST_SELL.STB                tab 468 col 49
    FILE_MOTION.STB              rows 569-571; TYPE_MOTION.STB rows 232-234 (Jrose's numbers)
    FILE_EFFECT.STB              row 25 (Jrose's number)
    MOTION/AVATAR                + skill_cannon_m01/m02/m03.ZMO (m03 with the fire event)
    EFFECT, EFFECTMESH, PARTICLES  at_skill_cannon.eft and its chain (25 files)

The hit-dummy sound Jrose names (FILE_SOUND 1000, `u_skill_b.wav`) is left out: the dump
does not ship it, and our sounds are loose files in the launch folder. Every Jrose id
written is checked first (motion rows blank here, effect row blank, projectile row
LIST_EFFECT 221 identical to ours). Cell-level undo and the copied files live in
`build/artisan-photon-cannon/`.

Deploy: restart the server (LIST_SKILL, LIST_USEITEM, LIST_SELL, the motion tables and
clips), re-bake, and run `dealer-tree-layout.py` for the classic tree.
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
JROSE = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
J_STB = os.path.join(JROSE, "3Ddata", "STB")
OUT = os.path.join(ROOT, "build", "artisan-photon-cannon")
MANIFEST = os.path.join(OUT, "manifest.json")

SRC_SKILL = 4271
CLIPS = ["skill_cannon_m01.ZMO", "skill_cannon_m02.ZMO", "skill_cannon_m03.ZMO"]
FIRE_EVENT = {20: 26}           # m03: 24 (spell cast) -> 26 (gun fire)
CAST_SPEED, ACTION_SPEED = 160, 140   # Jrose's 100/100 made the cast ~5 s (see above)
FILE_MOTION_ROWS = [569, 570, 571]
TYPE_MOTION_ROWS = [232, 233, 234]
FX_ROW = 25
EFT = "3DDATA/EFFECT/at_skill_cannon.eft"

RANKS = 10
NAME = "Photon Cannon"
DESC = ("Haul out the cannon you built yourself and fire a shell of light. It hits one "
        "target hard, and the flash blinds every enemy around it, lowering their Accuracy.")
CLASS_ARTISAN, LEVEL = 68, 100
PREREQ = (7002, 5)              # Calibrated Burst rank 5
ICON = 521                      # Jrose sprite 867 via add-skill-icon.py
JROSE_ICON = 867
AT_MP, AT_HIT, AT_LEVEL = 17, 20, 31
ST_ACCURACY_DOWN = 25

BOOK, BOOK_TEMPLATE = 855, 849
SHOP_TAB, SHOP_COL = 468, 49



def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


POWER = lin(700, 1600)
RELOAD = lin(100, 75)           # x0.2 s -> 20 -> 15 s
MP = lin(90, 170)
SP = lin(35, 130)
SCOPE = lin(400, 600)
RATE = lin(15, 25)
DURATION = lin(8, 12)
SUCCESS = lin(70, 110)

tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def jload(name):
    return rd.Stb(os.path.join(J_STB, name), "cp932")


# --------------------------------------------------------------- planning
def plan_cells(base):
    """[(table, row, col, new)] -- every in-place cell, blank-checked."""
    fm8, tm8, fe8 = jload("FILE_MOTION.STB"), jload("TYPE_MOTION.STB"), jload("FILE_EFFECT.STB")
    fm, tm, fe = load("FILE_MOTION.STB"), load("TYPE_MOTION.STB"), load("FILE_EFFECT.STB")
    out = []
    for r, clip in zip(FILE_MOTION_ROWS, CLIPS):
        assert fm8.s(r, 0).strip().lower().endswith(clip.lower()), (r, fm8.d[r])
        want = [b"3DDATA\\MOTION\\AVATAR\\" + clip.encode()] + [b""] * (fm.cols - 1)
        if any(fm.d[r]) and fm.d[r] != want:
            sys.exit(f"FILE_MOTION row {r} is in use here ({fm.d[r][0]!r}) -- refusing")
        out += [("FILE_MOTION.STB", r, c, v) for c, v in enumerate(want)]
    for r, fmr in zip(TYPE_MOTION_ROWS, FILE_MOTION_ROWS):
        assert tm8.i(r, 12) == fmr and tm8.i(r, 9) == fmr, (r, tm8.d[r])
        want = str(fmr).encode()
        if any(tm.d[r]) and any(v != want for v in tm.d[r]):
            sys.exit(f"TYPE_MOTION row {r} is in use here -- refusing")
        out += [("TYPE_MOTION.STB", r, c, want) for c in range(tm.cols)]
    path = fe8.d[FX_ROW][1]
    assert path.lower().endswith(b"at_skill_cannon.eft"), fe8.d[FX_ROW]
    if any(fe.d[FX_ROW]) and fe.d[FX_ROW][1] != path:
        sys.exit(f"FILE_EFFECT row {FX_ROW} is in use here -- refusing")
    out += [("FILE_EFFECT.STB", FX_ROW, c, fe8.d[FX_ROW][c]) for c in range(fe.cols)]

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
    over = {0: NAME.encode(), 20: str(base).encode(), 27: f"LUSE{BOOK}".encode()}
    out += [("LIST_USEITEM.STB", BOOK, c, over.get(c, ui.d[BOOK_TEMPLATE][c]))
            for c in range(ui.cols)]
    out.append(("LIST_SELL.STB", SHOP_TAB, SHOP_COL, code))
    return [(t, r, c, v) for t, r, c, v in out if load(t).d[r][c] != v]


def asset_files():
    clips = [f"3DDATA/MOTION/AVATAR/{c}" for c in CLIPS]
    uniq = {}
    for f in clips + sorted(ro.effect_chain([EFT], JROSE)):
        uniq.setdefault(ro.norm(f).replace("//", "/"),
                        f.replace("\\\\", "\\").replace("//", "/"))
    return sorted(uniq.values())


def skill_rows(base):
    sk8 = jload("LIST_SKILL.STB")
    le, le8 = load("LIST_EFFECT.STB"), jload("LIST_EFFECT.STB")
    bullet = sk8.i(SRC_SKILL, 71)
    if le.d[bullet] != le8.d[bullet]:
        sys.exit(f"LIST_EFFECT {bullet} differs from Jrose's -- refusing")
    rows = []
    for n in range(RANKS):
        c = {0: NAME, 1: base, 2: n + 1, 3: SP[n], 4: 1,
             5: 3,                  # attack-motion skill on the target (not Jrose's 7)
             7: 5, 8: SCOPE[n],     # enemies; scope = the debuff's radius around the target
             9: POWER[n], 10: 1,
             11: ST_ACCURACY_DOWN, 13: SUCCESS[n], 14: DURATION[n],
             15: 1,                 # weapon formula
             16: AT_MP, 17: MP[n], 20: RELOAD[n],
             21: AT_HIT, 23: RATE[n],
             29: 1,                 # SKILL_ACTION_MODE: attack the target afterwards
             30: 232, 31: 233, 51: ICON, 86: f"LSkill{base}"}
        if n == 0:
            c.update({35: CLASS_ARTISAN, 39: PREREQ[0], 40: PREREQ[1],
                      45: AT_LEVEL, 46: LEVEL})
        for col in range(52, 82):   # Jrose presentation; its sound (col 82) is not shipped
            v = sk8.i(SRC_SKILL, col)
            if v:
                c[col] = v
        c[53], c[69] = CAST_SPEED, ACTION_SPEED
        rows.append([str(c.get(i, "")).encode("latin-1") for i in range(87)])
    return rows


# --------------------------------------------------------------- main
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
        print(f"already imported at row {m['base']} -- nothing to do (--restore first)")
        return

    sk = load("LIST_SKILL.STB")
    base = sk.rows
    cells = plan_cells(base)
    files = asset_files()
    new_files = [f for f in files if not os.path.isfile(ro.rel_path(DATA, f))]
    rows = skill_rows(base)

    print(f"{NAME}: LIST_SKILL {base}-{base + RANKS - 1}, book {BOOK}, "
          f"tab {SHOP_TAB} col {SHOP_COL}")
    print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'acc-':>6}{'dur':>5}{'ratio':>7}"
          f"{'scope':>7}{'SP':>5}")
    for n in range(RANKS):
        print(f"  {n + 1:>4}{POWER[n]:>7}{RELOAD[n] * 0.2:>6.1f}{MP[n]:>5}{RATE[n]:>5}%"
              f"{DURATION[n]:>5}{SUCCESS[n]:>7}{SCOPE[n]:>7}{SP[n]:>5}")
    print(f"  {len(cells)} cells in place, {len(new_files)} files to copy "
          f"({len(files) - len(new_files)} already here)")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)

    for f in new_files:
        d = ro.rel_path(DATA, f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(ro.rel_path(JROSE, f), d)
    clip = ro.rel_path(DATA, f"3DDATA/MOTION/AVATAR/{CLIPS[2]}")
    raw = open(clip, "rb").read()
    open(clip, "wb").write(zmo.with_events(raw, FIRE_EVENT))

    undo = [[t, r, c, load(t).d[r][c].hex(), v.hex()] for t, r, c, v in cells]
    for t, r, c, v in cells:
        load(t).d[r][c] = v
    for t in {x[0] for x in cells}:
        load(t).save(False, keep_backup=False)
    sk.grow_to(base + RANKS)
    for n, r in enumerate(rows):
        sk.d[base + n] = r
    sk.save(False, keep_backup=False)

    t = Stl(os.path.join(STB_DIR, "LIST_SKILL_S.STL"))
    t.append(f"LSkill{base}", base, NAME, DESC)
    t.save(False, keep_backup=False)
    t = Stl(os.path.join(STB_DIR, "LIST_USEITEM_S.STL"))
    t.append(f"LUSE{BOOK}", BOOK, NAME, DESC)
    t.save(False, keep_backup=False)


    json.dump(dict(base=base, cells=undo, files=new_files), open(MANIFEST, "w"), indent=1)
    print(f"done -- now the icon: --icon-png, then add-skill-icon.py ... --skill-row "
          f"{base}-{base + RANKS - 1}; restart the server, re-bake, then scripts/dealer-tree-layout.py")


def icon_png(path):
    """Cut Jrose's sprite JROSE_ICON out of its atlas, through the icon tools' reader."""
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
    sk.save(False, keep_backup=False)
    for t, r, c, old, _ in m["cells"]:
        load(t).d[r][c] = bytes.fromhex(old)
    for t in {x[0] for x in m["cells"]}:
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
    print("restored: skill rows, book, shop slot, motion/effect rows, files, tree node, art")


def verify(m):
    if not m:
        sys.exit("not imported")
    ok = True
    sk = load("LIST_SKILL.STB")
    for n in range(RANKS):
        r = m["base"] + n
        if sk.d[r][0].decode("latin-1") != NAME or int(sk.d[r][2]) != n + 1:
            ok = False
            print(f"  row {r} is not {NAME} rank {n + 1}")
    for t, r, c, _, new in m["cells"]:
        if load(t).d[r][c] != bytes.fromhex(new):
            ok = False
            print(f"  {t} {r}/{c} differs")
    for f in asset_files():
        if not os.path.isfile(ro.rel_path(DATA, f)):
            ok = False
            print(f"  missing {f}")
    _, ev = zmo.events(open(ro.rel_path(DATA, f"3DDATA/MOTION/AVATAR/{CLIPS[2]}"), "rb").read())
    if any(ev[f] != e for f, e in FIRE_EVENT.items()):
        ok = False
        print("  the shot clip lacks its fire event")
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
