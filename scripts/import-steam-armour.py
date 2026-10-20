"""Import Jrose's Steam set as a level-220 **alternate** to Crystal.

**Superseded 2026-10-20:** `armour-ladder-pass.py` made these rows a level-70
cosmetic set (the user graded the look vanity, not end game), so `--verify` here
reports its stats and level as drift. The import itself is still how the rows got
their models.

Sixteen items -- four class lines x four slots -- written into blank rows
**250-253** of `LIST_CAP`, `LIST_BODY`, `LIST_ARMS` and `LIST_FOOT`.

--- what this is for

Crystal is our only level-220 set, and it is not to everyone's taste. This gives
the tier a second look at identical power, so the choice is cosmetic: **no stat
is overridden at all.** Each piece clones the matching Crystal row wholesale --
level 220, DEF, RES, price, the per-class bonus ability -- and changes only the
name, the description, the icon and the model. Two sets, same numbers, different
silhouette.

The source is Jrose's level-219 Steam line (`スチームソルジャー…` etc.), whose four
colours map cleanly onto our four classes: red Soldier, blue Muse, green Hawker,
yellow Dealer. Jrose ships a second, identically-textured variant one grade up
(`技巧のスチーム…`, "of Skill"); as with 667's seven Egyptian grades, that is a
stat tier over the same art, so only the base rows are taken.

--- this is the first in-place model import

`--target-row` used to be refused outright for anything with a model, because
`zsc_build_append` could only append and the object would have landed at the end
of the ZSC rather than at the row. That made the 999 ceiling look like a hard
limit on armour -- it is not, and the tables are mostly empty: `LIST_CAP` alone
has 588 rows that are blank in the STB, unnamed in the STL, empty in **both** sex
ZSCs and unreferenced by any drop cell or shop slot. 416 rows are free that way
in all four tables at once.

So the builder learned to write at an index. Writing in place rebuilds the whole
object section rather than splicing onto the end, which is only safe if
re-serialising an untouched object reproduces it exactly -- `import-item.py
--selftest` proves that across all 57 ZSCs we ship, and this script's `--verify`
re-checks that nothing outside the sixteen target rows moved.

Row 250-253 is taken from the middle of the 242-287 run that is free in all four
tables, well clear of both the retail block and our own appends.

--- the free test, which is stricter than "the STB row is blank"

A row is free only if it is blank in the STB **and** unnamed in the STL **and**
empty in both sex ZSCs **and** unreferenced by drops or shops. The STL clause is
not theoretical: `LIST_NATURAL` rows 455-489 read blank in the STB while the STL
still names them ("Yellow petals", "Big green herb") -- retail items whose STB
rows were lost in our dump. Writing there would have destroyed the only
surviving record of what they were.

Idempotent: `--target-row` refuses an occupied row, so a re-run stops rather than
duplicating. `--dry-run` / `--verify`.

After running: restart the servers and re-bake the VFS. Spawn with
`/item 2:250` (cap), `3:250` body, `4:250` arms, `5:250` foot -- GM access 2048.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "3DDATA")
SOURCE = r"C:\Users\Thomas\Desktop\Testclients\Jrose"

CLASSES = ("Soldier", "Muse", "Hawker", "Dealer")
SLOTS = ("cap", "body", "arms", "foot")
TARGET = {"Soldier": 250, "Muse": 251, "Hawker": 252, "Dealer": 253}

# Jrose's base Steam rows -- red / blue / green / yellow onto our four classes.
SRC = {
    "cap":  {"Soldier": 5128, "Muse": 5129, "Hawker": 5130, "Dealer": 5131},
    "body": {"Soldier": 5132, "Muse": 5133, "Hawker": 5134, "Dealer": 5135},
    "arms": {"Soldier": 5071, "Muse": 5072, "Hawker": 5073, "Dealer": 5074},
    "foot": {"Soldier": 5082, "Muse": 5083, "Hawker": 5084, "Dealer": 5085},
}
# our Crystal set: the template each piece clones, stats and all
TEMPLATE = {
    "cap":  {"Soldier": 977, "Muse": 978, "Hawker": 979, "Dealer": 980},
    "body": {"Soldier": 904, "Muse": 905, "Hawker": 906, "Dealer": 907},
    "arms": {"Soldier": 880, "Muse": 881, "Hawker": 882, "Dealer": 883},
    "foot": {"Soldier": 878, "Muse": 879, "Hawker": 880, "Dealer": 881},
}
# the source's own piece nouns, which are more characterful than Crystal's and
# still read as one set
PIECE = {"cap": "Gear", "body": "Cloak", "arms": "Gloves", "foot": "Boots"}
FLAVOUR = {
    "Soldier": "Riveted brass over a heavy coat, and a gorget that vents steam "
               "when the wearer exerts himself.",
    "Muse":    "Copper filigree and blue glass. The pressure gauge at the collar "
               "is said to read the wearer's temper.",
    "Hawker":  "Oiled green leather with a clockwork spine. Quiet, until it is not.",
    "Dealer":  "Polished yellow lacquer and a great many pockets, most of them "
               "not where they appear to be.",
}
STB_FILE = {"cap": "LIST_CAP.STB", "body": "LIST_BODY.STB",
            "arms": "LIST_ARMS.STB", "foot": "LIST_FOOT.STB"}
ZSCS = {"cap": ("LIST_MCAP.ZSC", "LIST_WCAP.ZSC"),
        "body": ("LIST_MBODY.ZSC", "LIST_WBODY.ZSC"),
        "arms": ("LIST_MARMS.ZSC", "LIST_WARMS.ZSC"),
        "foot": ("LIST_MFOOT.ZSC", "LIST_WFOOT.ZSC")}
SIDECAR = os.path.join(ROOT, "build", "steam-armour-zsc-fingerprint.json")


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


def plan():
    for cls in CLASSES:
        for slot in SLOTS:
            yield (slot, cls, "Steam %s %s" % (cls, PIECE[slot]),
                   SRC[slot][cls], TARGET[cls], TEMPLATE[slot][cls])


def fingerprint():
    """Every ZSC object, serialised, keyed by (file, index).

    An in-place write rebuilds the whole object section, so the thing worth
    proving is not that the target changed -- it is that nothing else did.
    """
    imp = load("import-item")
    out = {}
    for slot in SLOTS:
        for zn in ZSCS[slot]:
            z = imp.Zsc(os.path.join(DATA, "AVATAR", zn))
            out[zn] = [imp.zsc_serialize_object(o).hex() for o in z.objects]
    return out


def run(item, dry):
    slot, cls, name, srow, target, tmpl = item
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"),
           "--type", slot, "--source", SOURCE,
           "--source-row", str(srow), "--target-row", str(target),
           "--art-only", "--template-row", str(tmpl),
           "--name", name, "--desc", FLAVOUR[cls], "--copy-icon"]
    if dry:
        cmd.append("--dry-run")
    env = dict(os.environ, PYTHONIOENCODING="utf-8:replace")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def verify():
    rd = load("rose-data-reader")
    imp = load("import-item")
    bad = []
    for slot, cls, name, _srow, target, tmpl in plan():
        s = rd.Stb(os.path.join(DATA, "STB", STB_FILE[slot]), "utf-8")
        got = rd.scrub(s.s(target, 0)).strip()
        if got != name:
            bad.append("%s row %d: name is %r, want %r" % (slot, target, got, name))
            continue
        t = rd.Stb(os.path.join(DATA, "STB", STB_FILE[slot]), "utf-8")
        for col, what in ((31, "DEF"), (32, "RES"), (5, "price")):
            if s.i(target, col) != t.i(tmpl, col):
                bad.append("%s %s: %s %d != Crystal's %d"
                           % (slot, name, what, s.i(target, col), t.i(tmpl, col)))
        for zn in ZSCS[slot]:
            z = imp.Zsc(os.path.join(DATA, "AVATAR", zn))
            if target >= len(z.objects) or not z.objects[target][1]:
                bad.append("%s: %s object %d has no parts" % (name, zn, target))
    # nothing outside the target rows may have moved
    drift = []
    if os.path.exists(SIDECAR):
        with open(SIDECAR, encoding="utf-8") as fh:
            before = json.load(fh)
        now = fingerprint()
        targets = set(TARGET.values())
        for zn, objs in before.items():
            cur = now.get(zn, [])
            if len(cur) != len(objs):
                drift.append("%s object count %d -> %d" % (zn, len(objs), len(cur)))
                continue
            for i, (a, b) in enumerate(zip(objs, cur)):
                if a != b and i not in targets:
                    drift.append("%s object %d changed and is not a target" % (zn, i))
    print("%d pieces; %d problem(s)%s"
          % (len(list(plan())), len(bad), (":\n  " + "\n  ".join(bad[:8])) if bad else ""))
    if os.path.exists(SIDECAR):
        print("untouched-object check: %d drift(s)%s"
              % (len(drift), (":\n  " + "\n  ".join(drift[:8])) if drift else
                 " -- every object outside rows %s is byte-identical"
                 % sorted(set(TARGET.values()))))
    elif os.path.exists(SIDECAR + ".verified"):
        print("drift check: already passed at import time (%s); the baseline is "
              "retired, since later imports into other rows would fail it for no "
              "reason" % os.path.basename(SIDECAR + ".verified"))
    else:
        print("no pre-write fingerprint on disk, so the drift check was skipped")
    return 1 if bad or drift else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify()

    if not args.dry_run:
        os.makedirs(os.path.dirname(SIDECAR), exist_ok=True)
        if not os.path.exists(SIDECAR):
            with open(SIDECAR, "w", encoding="utf-8") as fh:
                json.dump(fingerprint(), fh)
            print("recorded a pre-write fingerprint of every ZSC object")

    done, failed = 0, []
    for item in plan():
        rc, out = run(item, args.dry_run)
        slot, _cls, name, _s, target = item[0], item[1], item[2], item[3], item[4]
        if rc == 0:
            done += 1
            print("  %-13s %-5s row %3d  %s"
                  % ("would import" if args.dry_run else "imported", slot, target, name))
        else:
            failed.append(name)
            print("  %-13s %-5s row %3d  %s\n     %s"
                  % ("FAILED", slot, target, name, out.strip()[-400:]))
    print("\n%d %s, %d failed" % (done, "planned" if args.dry_run else "imported",
                                  len(failed)))
    if failed:
        return 1
    if args.dry_run:
        return 0
    rc = verify()
    # The fingerprint proves THIS write left its neighbours alone. That proof is
    # only meaningful at write time: keep the baseline afterwards and the next
    # legitimate import into other rows reports every one of them as drift. So
    # retire it on success, and leave it in place on failure for diagnosis.
    if rc == 0 and os.path.exists(SIDECAR):
        os.replace(SIDECAR, SIDECAR + ".verified")
        print("drift baseline retired to %s" % os.path.basename(SIDECAR + ".verified"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
