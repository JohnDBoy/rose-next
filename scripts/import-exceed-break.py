"""Finish the Dealer line: Exceed Break for the Bourgeois, and Calibrated Burst's new look.

    python scripts/import-exceed-break.py --dry-run
    python scripts/import-exceed-break.py
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
  everything in front; sets the target burning"). The only new animation any dump has
  for the Bourgeois is the cannon shot it plays, `skill_cannon_m03` -- Photon Cannon's
  shot, after the stock launcher wind-up instead of the bazooka. Ours is the type-3
  version of it, for the reasons Photon Cannon's docstring gives (a type-7 blast aims
  at the target's old spot; the shot clip needs the gun fire event 26, which our copy
  of `m03` already carries), with the Champion's Burning (LIST_STATUS 62, 150/s) spread
  around the target through the type-3 SKILL_SCOPE rule.

  Its identity is the Bourgeois's: **launcher only** -- the gun/launcher masteries are
  shared, so skills are the only place the two jobs part -- and it **costs Zuly as well
  as MP**, like Zuly Storm: you pay for the shells.

  **The round is Fire Burn's fireball (LIST_EFFECT 263)**, not Jrose's. Jrose's real 6151
  has no projectile at all (a type-7 area blast); the test row first took the one on
  Jrose's leftover test copy 6211, `dragon_firing_hit02.eft` -- an impact flash, which
  died before reaching anything, so no shell ever landed and its damage and Burning
  waited for the 10 s projectile timeout (the burn had expired server-side by then,
  which is why it never showed). 263 is a proven flying round and fits "burning".
  The test row also lacked SKILL_TAB_TYPE (col 4), which filed it under Basic skills.

* **Calibrated Burst** keeps `gun_3attack` -- no dump has a new rapid-fire gun clip
  (the only gun-adjacent one is Jrose's crossbow "Shot Master", a 1.9 s aim and a single
  shot) -- and takes the "Nightmare" effect kit of four tried: the wind-up flare is
  Jrose's `_mana_hit_05` (the cannon-blast burst), the round Jrose Night Mare Blitz's
  `_mana_firing_00` (LIST_EFFECT 252, already ours). Only cols 56 and 71 change, on all
  ten ranks; `import-artisan-skill.py`'s row template carries the same values, so its
  `--verify` agrees.

Jrose's FILE_EFFECT numbering matches ours and both new effects' rows are blank here,
so `_heavy_casting_03` and `_mana_hit_05` go in at Jrose's own rows 1047 and 1126.

The numbers (Exceed Break, ranks 1 -> 10, linear)
-------------------------------------------------
    power 800 -> 1800    cd 14 -> 11 s    MP 60 -> 120 + Zuly 800 -> 6000
    Burning (150/s) for 6 -> 10 s within 4 -> 6 m of the target, ratio 60 -> 100
    Bourgeois (class 67), launcher, level 100, Gun Smash rank 5 (first Zuly Storm r5;
    the user moved it to follow Gun Smash, 2026-10-17)

Sized in the combat sim (auto-builds, launcher, typical play, against no Exceed Break):
the first cut, 600 -> 1400, added at most +4% / +15% (plain / star) at level 200 and
lost ground at 160. At 800 -> 1800 (x1.3): +5% / +11% at 130, about even / +5% at 160,
+16% / +29% at 200; x1.6 one-shot plain monsters at 200. Level 100 dips ~20% in every
variant -- the auto-build was spending its points on Zuly Storm r5 (the prerequisite at
the time) to unlock it, the price of the prerequisite rather than of the skill.

How a player gets it
--------------------
* Book LIST_USEITEM 856 (blank; copy of Refine Item's 849), sold in Darren's tab 468
  col 25, beside Zuly Storm's book.
* Trees: UI2 builds itself from the class set and prerequisite. The classic tree's node
  and painted box are owned by `scripts/dealer-tree-layout.py`: a box right of Gun
  Smash's on `DEALER_COMBAT_MASTERY.DDS` (first right of Zuly Storm's).
* Icon: Jrose's own (its sprite 255, an explosion), appended by `add-skill-icon.py`;
  this script writes the resulting index `ICON` so a re-import keeps it.

What it changes
---------------
    LIST_SKILL.STB / _S.STL    10 rows appended, 1 key; Calibrated Burst cols 56, 71 x 10
    LIST_USEITEM.STB / _S.STL  row 856, key LUSE856;   LIST_SELL.STB tab 468 col 25
    FILE_EFFECT.STB            rows 1047, 1126 (Jrose's numbers)
    EFFECT, PARTICLES          _heavy_casting_03.eft, _mana_hit_05.eft and their .ptl (4 files)

Needs `import-artisan-photon-cannon.py` first (the shot clip and its motion rows).
Cell-level undo and the copied files in `build/exceed-break/`.
Deploy: restart the server, re-bake, run `dealer-tree-layout.py` for the classic tree.
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
OUT = os.path.join(ROOT, "build", "exceed-break")
MANIFEST = os.path.join(OUT, "manifest.json")

FX_ROWS = [1047, 1126]          # _heavy_casting_03, _mana_hit_05 -- at Jrose's numbers
SHOT_ACTION = 234               # TYPE_MOTION row -> skill_cannon_m03 (Photon Cannon's import)

# Calibrated Burst, ranks 1-10: the "Nightmare" kit
CB_ROWS = range(7002, 7012)
CB_LOOK = {56: 1126, 71: 252}   # wind-up flare _mana_hit_05; round _mana_firing_00

RANKS = 10
NAME = "Exceed Break"
DESC = ("Load the launcher with shells that cost real money and fire a barrage into the "
        "target. Every enemy around it is set Burning. Costs Zuly as well as MP.")
CLASS_BOURGEOIS, LEVEL = 67, 100
PREREQ = (2281, 5)              # Gun Smash rank 5 (was Zuly Storm 5)
ICON = 522                      # Jrose sprite 255 via add-skill-icon.py
JROSE_ICON = 255
AT_MP, AT_LEVEL, AT_MONEY = 17, 31, 40
ST_BURNING = 62

BOOK, BOOK_TEMPLATE = 856, 849
SHOP_TAB, SHOP_COL = 468, 25    # beside Zuly Storm's book (col 24)



def lin(a, b, n=RANKS):
    return [round(a + (b - a) * k / (n - 1)) for k in range(n)]


POWER = lin(800, 1800)
RELOAD = lin(70, 55)            # x0.2 s -> 14 -> 11 s
MP = lin(60, 120)
ZULY = lin(800, 6000)
SP = lin(35, 130)
SCOPE = lin(400, 600)
DURATION = lin(6, 10)
SUCCESS = lin(60, 100)

tables = {}


def load(name):
    if name not in tables:
        tables[name] = Stb(os.path.join(STB_DIR, name))
    return tables[name]


def jload(name):
    return rd.Stb(os.path.join(J_STB, name), "cp932")


def plan_cells(base):
    jfe = jload("FILE_EFFECT.STB")
    fe, sk = load("FILE_EFFECT.STB"), load("LIST_SKILL.STB")
    out = []
    for r in FX_ROWS:
        want = [jfe.d[r][c] for c in range(fe.cols)]
        if any(fe.d[r]) and fe.d[r] != want:
            sys.exit(f"FILE_EFFECT {r} is in use here ({fe.d[r][1]!r}) -- refusing")
        out += [("FILE_EFFECT.STB", r, c, v) for c, v in enumerate(want)]
    for r in CB_ROWS:
        if sk.d[r][0] != b"Calibrated Burst":
            sys.exit(f"LIST_SKILL {r} is not Calibrated Burst -- refusing")
        out += [("LIST_SKILL.STB", r, c, str(v).encode()) for c, v in CB_LOOK.items()]
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
    jfe = jload("FILE_EFFECT.STB")
    efts = [jfe.s(r, 1).strip().replace("\\", "/") for r in FX_ROWS]
    uniq = {}
    for f in sorted(ro.effect_chain(efts, JROSE)):
        uniq.setdefault(ro.norm(f).replace("//", "/"), f.replace("\\\\", "\\").replace("//", "/"))
    return sorted(uniq.values())


def require_shot():
    """Photon Cannon's import brought the shot clip, with the fire event, and its row."""
    tm, fm = load("TYPE_MOTION.STB"), load("FILE_MOTION.STB")
    r = tm.i(SHOT_ACTION, 9)
    clip = fm.s(r, 0).strip() if r else ""
    if not clip.lower().endswith("skill_cannon_m03.zmo"):
        sys.exit("TYPE_MOTION 234 is not the cannon shot -- run import-artisan-photon-cannon.py first")
    _, ev = zmo.events(open(ro.rel_path(DATA, clip), "rb").read())
    if not ev or ev[20] != 26:
        sys.exit("skill_cannon_m03 lacks its gun fire event (frame 20 = 26) -- refusing")


def skill_rows(base):
    le = load("LIST_EFFECT.STB")
    if not le.s(263, 11).strip():
        sys.exit("LIST_EFFECT 263 (Fire Burn's round) is blank here -- refusing")
    rows = []
    for n in range(RANKS):
        c = {0: NAME, 1: base, 2: n + 1, 3: SP[n],
             4: 1,                  # SKILL_TAB_TYPE: the attack tab (blank = Basic)
             5: 3, 7: 5, 8: SCOPE[n], 9: POWER[n], 10: 1,
             11: ST_BURNING, 13: SUCCESS[n], 14: DURATION[n], 15: 1,
             16: AT_MP, 17: MP[n], 18: AT_MONEY, 19: ZULY[n], 20: RELOAD[n],
             29: 1,                 # SKILL_ACTION_MODE: attack the target afterwards
             30: 233,               # launcher only
             51: ICON,
             # stock launcher wind-up, Jrose's cast flare, the cannon shot at x1.4
             52: 95, 53: 100, 54: 96, 56: 1047, 57: 3, 58: 131,
             68: SHOT_ACTION, 69: 140, 70: 1,
             71: 263, 72: 1, 73: 148,       # Fire Burn's fireball
             74: 1125, 75: 999, 76: 67,     # _mana_hit_04, as Jrose
             86: f"LSkill{base}"}
        if n == 0:
            c.update({35: CLASS_BOURGEOIS, 39: PREREQ[0], 40: PREREQ[1],
                      45: AT_LEVEL, 46: LEVEL})
        rows.append([str(c.get(i, "")).encode("latin-1") for i in range(87)])
    return rows


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

    require_shot()
    sk = load("LIST_SKILL.STB")
    base = sk.rows
    cells = plan_cells(base)
    files = asset_files()
    new_files = [f for f in files if not os.path.isfile(ro.rel_path(DATA, f))]
    rows = skill_rows(base)

    print(f"{NAME}: LIST_SKILL {base}-{base + RANKS - 1}, book {BOOK}, tab {SHOP_TAB} col {SHOP_COL}")
    print(f"  {'rank':>4}{'power':>7}{'cd s':>6}{'MP':>5}{'Zuly':>6}{'dur':>5}{'ratio':>7}{'scope':>7}{'SP':>5}")
    for n in range(RANKS):
        print(f"  {n + 1:>4}{POWER[n]:>7}{RELOAD[n] * 0.2:>6.1f}{MP[n]:>5}{ZULY[n]:>6}"
              f"{DURATION[n]:>5}{SUCCESS[n]:>7}{SCOPE[n]:>7}{SP[n]:>5}")
    print(f"  Calibrated Burst rows {CB_ROWS.start}-{CB_ROWS.stop - 1}: cols {CB_LOOK}")
    print(f"  {len(cells)} cells in place, {len(new_files)} files to copy")
    if args.dry_run:
        print("dry run -- nothing written")
        return

    os.makedirs(OUT, exist_ok=True)
    for f in new_files:
        d = ro.rel_path(DATA, f)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(ro.rel_path(JROSE, f), d)
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
    json.dump(dict(base=base, cells=undo, files=new_files), open(MANIFEST, "w"), indent=1)
    print(f"done -- now the icon: --icon-png, then add-skill-icon.py ... --skill-row "
          f"{base}-{base + RANKS - 1}; restart the server, re-bake, then scripts/dealer-tree-layout.py")


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
    print("restored: skill rows, Calibrated Burst's look, book, shop, effects, files, tree, art")


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
