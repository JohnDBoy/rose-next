#!/usr/bin/env python3
"""Give socketed Diamonds their glow (tsuki's effect rows).

Symptom (2026-10-12): a weapon socketed with a Diamond [2] or [3] shows no gem
effect; a Garnet on the same weapon glows.

Cause: a socketed gem's glow is `GEMITEM_ATTACK_EFFECT` (LIST_JEMITEM game col 21),
a LIST_EFFECT row whose `EFFECT_POINT` columns (2-5) name FILE_EFFECT rows
(`CObjAVT::CreateGemmingEffect`). Every gem family sits on a five-step ladder of
effect rows -- Garnet 1-3, Ruby 6-8, Sapphire 11-13, Topaz 16-18, Emerald 21-23,
Peridot 26-28, Pink Opal 36-38 -- and retail Diamond is 31-33
(`_jemitem_effect07/17/27.eft`, which we ship). Our seven Diamond rows (361-367)
instead point at **74, 75, 76**, and those LIST_EFFECT rows are blank here, so
`Add_EffectWithIDX` gets nothing and the gem draws nothing.

Where that came from: our gem table has the tsuki layout. In the tsuki dump
LIST_EFFECT 74-76 are a newer "Diamond" effect set (FILE_EFFECT 1188-1190 ->
`_JEMITEM_DIAMOND02/12/22.eft`, the `DIAMauro_*` particles and the `PINKAURO_*`
motions); only the gem table's pointer came across, not the two tables' rows. The
effect files themselves and every particle, texture and motion they pull in are
already in our data (presumably with the Pink Opal import, which shares them), so
the repair is six rows written in place at the source index: LIST_EFFECT 74-76
and FILE_EFFECT 1188-1190, all blank here. Jrose still uses retail 31-33; the
tsuki look is what the data was aiming for, and re-pointing to 31-33 remains the
one-cell alternative if it disappoints.

The FILE_EFFECT rows go through `import-monster-skills.py`'s `Plan._need_effect`
(refuses an occupied row that differs, walks the .eft dependencies); the
LIST_EFFECT rows are plain copies of tsuki's, checked blank here first.

  python scripts/fix-diamond-gem-effects.py --dry-run
  python scripts/fix-diamond-gem-effects.py
  python scripts/fix-diamond-gem-effects.py --verify
  python scripts/fix-diamond-gem-effects.py --restore

Undo is cell-level: `build/diamond-gem-effects/manifest.json` keeps the previous
cells of exactly the six rows (not whole files, so another script's later edits to
these tables survive a restore). Client-only data: re-bake the VFS, no server
restart. `data/` is gitignored, so this docstring is the record of the change.
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(REPO, "data")
TSUKI = r"C:\Users\Thomas\Desktop\Testclients\tsuki"
BACKUP_DIR = os.path.join(REPO, "build", "diamond-gem-effects")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

DIAMOND_ROWS = range(361, 368)              # LIST_JEMITEM Diamond [1]..[7]
C_GEM_EFFECT = 21
EFFECT_ROWS = (74, 75, 76)                  # LIST_EFFECT, tsuki's Diamond set
FILE_ROWS = (1188, 1189, 1190)              # FILE_EFFECT they point at
POINT_COLS = (2, 3, 4, 5)                   # EFFECT_POINT(I, 0..3)


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = saved
    return m


ms = load("import_monster_skills", "import-monster-skills.py")
oro, STB = ms.oro, ms.STB


def tables(root):
    return {n: oro.Stb(os.path.join(root, STB, n)) for n in ("LIST_EFFECT.STB", "FILE_EFFECT.STB", "LIST_JEMITEM.STB")}


def check_pointers(jem, problems):
    for r in DIAMOND_ROWS:
        name = jem.get(r, 0).decode("latin-1")
        e = ms.ival(jem, r, C_GEM_EFFECT)
        if "Diamond" not in name or e not in EFFECT_ROWS:
            problems.append("LIST_JEMITEM %d is %r -> effect %d; expected a Diamond pointing at %s"
                            % (r, name, e, list(EFFECT_ROWS)))


def verify(root):
    o = tables(root)
    problems = []
    check_pointers(o["LIST_JEMITEM.STB"], problems)
    le, fe = o["LIST_EFFECT.STB"], o["FILE_EFFECT.STB"]
    for r in EFFECT_ROWS:
        if ms.blank_row(le, r):
            problems.append("LIST_EFFECT %d blank" % r)
            continue
        for c in POINT_COLS:
            i = ms.ival(le, r, c)
            if not i:
                problems.append("LIST_EFFECT %d col %d has no point" % (r, c))
                continue
            rel = fe.get(i, 1).decode("latin-1")
            if not rel.strip():
                problems.append("FILE_EFFECT %d blank" % i)
            elif not os.path.isfile(oro.rel_path(root, rel)):
                problems.append("missing %s" % rel)
    for p in problems:
        print("   " + p)
    print("   %s" % ("OK: every Diamond grade resolves to an effect file" if not problems else "FAIL"))
    return not problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        o = tables(root)
        for n, rows in man["cells"].items():
            for r, cells in rows.items():
                for c, v in enumerate(cells):
                    o[n].set(int(r), c, v.encode("latin-1"))
            open(os.path.join(root, STB, n), "wb").write(o[n].to_bytes())
            print("   restored %d row(s) of %s" % (len(rows), n))
        os.remove(MANIFEST)
        return 0
    if a.verify:
        print("verify:")
        return 0 if verify(root) else 1

    print("self-test (the STB writer must reproduce every table byte-identically):")
    for n in ("LIST_EFFECT.STB", "FILE_EFFECT.STB"):
        p = os.path.join(root, STB, n)
        same = oro.Stb(p).to_bytes() == open(p, "rb").read()
        print("   %-18s %s" % (n, "OK" if same else "FAIL"))
        if not same:
            return 1

    ms.SOURCES["tsuki"] = TSUKI
    plan = ms.Plan(root, [])
    plan.src = TSUKI
    plan.s = plan._tables("tsuki")
    o = tables(root)
    check_pointers(o["LIST_JEMITEM.STB"], plan.problems)
    le_o, le_s = o["LIST_EFFECT.STB"], plan.s["LIST_EFFECT.STB"]
    if le_o.cols != le_s.cols:
        plan.problems.append("LIST_EFFECT has %d cols here and %d in tsuki" % (le_o.cols, le_s.cols))
    effect_rows = {}
    for r in EFFECT_ROWS:
        if not ms.blank_row(le_o, r):
            same = all(le_o.get(r, c).strip() == le_s.get(r, c).strip() for c in range(1, le_o.cols))
            if not same:
                plan.problems.append("LIST_EFFECT %d is occupied here and differs from tsuki's" % r)
            continue
        points = {ms.ival(le_s, r, c) for c in POINT_COLS}
        if not points <= set(FILE_ROWS):
            plan.problems.append("tsuki LIST_EFFECT %d points at %s, expected %s" % (r, sorted(points), list(FILE_ROWS)))
        effect_rows[r] = [le_s.get(r, c) for c in range(le_o.cols)]
        for i in points:
            plan._need_effect(i, "Diamond effect row %d" % r)
    files = plan.files()
    print("\nplan:")
    for r, cells in effect_rows.items():
        print("   LIST_EFFECT %d <- tsuki: points %s" % (r, [cells[c].decode() for c in POINT_COLS]))
    plan.report(files)
    if plan.problems:
        print("\nABORT, unresolved:")
        for p in plan.problems:
            print("   " + p)
        return 1
    if not effect_rows and not plan.effect_rows:
        print("\nnothing to write")
        return 0 if verify(root) else 1
    if a.dry_run:
        print("\ndry run: nothing written")
        return 0
    if os.path.isfile(MANIFEST):
        print("\nABORT: %s exists -- --restore first" % MANIFEST)
        return 1
    missing = [rel for _, rel, have in files if not have]
    if missing:
        print("\nABORT: files expected to be present already are not: %s" % missing)
        return 1

    man = {"cells": {"LIST_EFFECT.STB": {}, "FILE_EFFECT.STB": {}}}
    fe_o = o["FILE_EFFECT.STB"]
    for r, cells in effect_rows.items():
        man["cells"]["LIST_EFFECT.STB"][str(r)] = [le_o.get(r, c).decode("latin-1") for c in range(le_o.cols)]
        for c, v in enumerate(cells):
            le_o.set(r, c, v)
    for r, cells in plan.effect_rows.items():
        man["cells"]["FILE_EFFECT.STB"][str(r)] = [fe_o.get(r, c).decode("latin-1") for c in range(fe_o.cols)]
        for c, v in enumerate(cells):
            fe_o.set(r, c, v)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    for n in ("LIST_EFFECT.STB", "FILE_EFFECT.STB"):
        open(os.path.join(root, STB, n), "wb").write(o[n].to_bytes())
        print("   wrote %s" % n)
    print("\nverify:")
    return 0 if verify(root) else 1


if __name__ == "__main__":
    sys.exit(main())
