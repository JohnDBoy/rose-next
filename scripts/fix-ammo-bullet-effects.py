#!/usr/bin/env python3
r"""Give six arrow/bullet/shell items a projectile that exists, so their shots are visible.

THE DEFECT
----------
A ranged shot's projectile comes from the ammo, not the weapon:
`NATURAL_BULLET_NO(item)` is **column 17** of `LIST_NATURAL.STB`
(`src/common/include/rose/io/stb.h`) and names a `LIST_EFFECT.STB` row, whose column 11
(`EFFECT_BULLET_NORMAL`) is the `FILE_EFFECT.STB` entry the client flies
(`CObjAVT::Get_BulletNO` -> `CBullet`, `src/client/bullet.cpp`). Six ammo rows point at
an effect row that has no projectile:

    329  Zuly Bullet     -> effect 182   row exists, no projectile file
    334  Vortex Bullet   -> effect 607   empty row
    335  Nova Bullet     -> effect 598   empty row
    346  Rock Shell      -> effect 190   row exists, no projectile file
    347  Cluster Shell   -> effect 189   row exists, no projectile file
    348  Molten Shell    -> effect 599   empty row

so a gun or launcher loaded with any of them fires nothing you can see -- the shot
still lands and deals damage (the server never reads the effect), it just has no model.
Found 2026-10-14 when the combat simulator's test Artisan was handed Nova Bullet, the
best-quality bullet, and its shots were invisible.

THE FIX
-------
Point each one at the retail projectile of its own kind, the one the next tier down
already uses:

    bullets -> effect 181   `_gun_firing_04.eft`     (Chromium Bullet's)
    shells  -> effect 191   `_bowgun_firing_01.eft`  (every retail shell's)

Both files are in data/3DDATA/EFFECT. The three empty effect rows (598/599/607) look
like slots an import meant to fill with its own projectiles; if those assets ever turn
up, importing them is the better fix and this pass can be --restore'd first. Nothing
but column 17 is touched: quality, which feeds ATK, stays as it is.

Client-only data (the server never reads an effect), so re-bake the VFS; no server
restart needed. Idempotent; --dry-run, --verify and --restore supported.
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OURS = "data"
NATURAL_REL = os.path.join("3DDATA", "STB", "LIST_NATURAL.STB")
EFFECT_REL = os.path.join("3DDATA", "STB", "LIST_EFFECT.STB")
FILE_EFFECT_REL = os.path.join("3DDATA", "STB", "FILE_EFFECT.STB")
BULLET_COL = 17                 # NATURAL_BULLET_NO
TYPE_COL = 4                    # 431 arrow, 432 bullet, 433 shell
EFFECT_BULLET_NORMAL = 11

# row -> (expected name, ammo type, broken effect, fixed effect)
ROWS = {
    329: ("Zuly Bullet", "432", "182", "181"),
    334: ("Vortex Bullet", "432", "607", "181"),
    335: ("Nova Bullet", "432", "598", "181"),
    346: ("Rock Shell", "433", "190", "191"),
    347: ("Cluster Shell", "433", "189", "191"),
    348: ("Molten Shell", "433", "599", "191"),
}
AMMO_TYPES = ("431", "432", "433")


def cell(data, r, c):
    return data[r][c].decode("latin-1").strip() if 0 <= r < len(data) and c < len(data[r]) \
        else ""


def projectile(eff, fe, effect_row):
    """The FILE_EFFECT path an effect row flies, or '' (EFFECT_BULLET_NORMAL)."""
    try:
        e = int(effect_row)
    except ValueError:
        return ""
    f = cell(eff, e, EFFECT_BULLET_NORMAL)
    if not f or f == "0":
        return ""
    return cell(fe, int(f), 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true", help="put the broken effects back")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(OURS, "3DDATA")):
        sys.exit("run from the repo root (data/3DDATA not found)")
    spec = importlib.util.spec_from_file_location("ii", os.path.join(HERE, "import-item.py"))
    ii = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ii)

    path = os.path.join(OURS, NATURAL_REL)
    _d, _o, rows, cols, data = ii.stb_read(path)
    eff = ii.stb_read(os.path.join(OURS, EFFECT_REL))[4]
    fe = ii.stb_read(os.path.join(OURS, FILE_EFFECT_REL))[4]

    def flies(effect_row):
        p = projectile(eff, fe, effect_row)
        return p and os.path.exists(os.path.join(OURS, p.replace("\\", "/")))

    if args.verify:
        bad = 0
        for r, (name, _t, _old, new) in sorted(ROWS.items()):
            cur = cell(data, r, BULLET_COL)
            ok = cur == new
            bad += 0 if ok else 1
            print("  %-4d %-14s effect=%-4s %s" % (r, name, cur,
                                                     "OK" if ok else "*** expected %s ***" % new))
        # the whole table, so ammo imported later with a dead projectile is caught too
        for r in range(1, len(data)):
            if cell(data, r, TYPE_COL) in AMMO_TYPES and cell(data, r, 0) \
                    and not flies(cell(data, r, BULLET_COL)):
                bad += 1
                print("  %-4d %-14s effect %s has no projectile file"
                      % (r, cell(data, r, 0), cell(data, r, BULLET_COL)))
        sys.exit(1 if bad else 0)

    for _r, (_n, _t, _old, new) in ROWS.items():
        if not flies(new):
            sys.exit("effect %s has no projectile on disk -- the target itself is broken" % new)

    changed = 0
    for r, (name, atype, old, new) in sorted(ROWS.items()):
        src, dst = (new, old) if args.restore else (old, new)
        got = cell(data, r, 0)
        if got != name:
            sys.exit("row %d is %r, expected %r -- the table has shifted, refusing to "
                     "rewrite the wrong row" % (r, got, name))
        if cell(data, r, TYPE_COL) != atype:
            sys.exit("row %d (%s) is ammo type %s, expected %s"
                     % (r, name, cell(data, r, TYPE_COL), atype))
        cur = cell(data, r, BULLET_COL)
        if cur == dst:
            print("  %-4d %-14s already %s" % (r, name, dst))
            continue
        if cur != src:
            sys.exit("row %d (%s) has effect %r, expected %s or %s -- something else "
                     "changed it; not guessing" % (r, name, cur, src, dst))
        print("  %-4d %-14s effect %s -> %s  (%s)" % (r, name, cur, dst,
                                                       projectile(eff, fe, dst) or "none"))
        ii.stb_set_cell(path, r, BULLET_COL, dst, args.dry_run)
        changed += 1

    if not args.dry_run and changed:
        _d3, _o3, r2, c2, d2 = ii.stb_read(path)
        assert (r2, c2) == (rows, cols), "table shape changed"
        for r, (_n, _t, old, new) in ROWS.items():
            assert cell(d2, r, BULLET_COL) == (old if args.restore else new), \
                "row %d did not take" % r
        diff = sum(1 for a, b in zip(data, d2) for x, y in zip(a, b) if x != y)
        assert diff == changed, "%d cells differ, expected %d" % (diff, changed)
        print("verified: %d cell(s) written, nothing else differs, shape unchanged (%dx%d)"
              % (changed, r2 - 1, c2 - 1))
    print("\n%s" % ("DRY RUN - nothing written." if args.dry_run
                    else "done.  Re-bake the VFS (client-only data)."))


if __name__ == "__main__":
    main()
