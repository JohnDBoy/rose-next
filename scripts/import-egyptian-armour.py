"""Import the 667 "Egyptian" armour as our level-240 tier -- the first full set
above Crystal, and the first armour import this project has done.

**Level 225 since 2026-10-20** (`armour-endgame-sets.py`): Jrose's Norse set took
240 and the user moved this "very Oro-coded" set down, onto the 25% point of the
Crystal->old-240 line. Its Oro drops (Fossil Sanctuary, lv225-240) still fit.

Sixteen items: four class lines x four slots, appended to `LIST_CAP`,
`LIST_BODY`, `LIST_ARMS` and `LIST_FOOT`.

--- why this set, out of thousands

Surveyed by *texture signature* rather than by name, because the names lie in
both directions and each lie costs a wasted import:

* **667 looks like it has seven level-240 sets** -- Brave, Courage, Luminous,
  Precious, Glorious, Chivalrous and a base grade. All seven point at the **same
  mesh and the same textures** (`body1_egyptian_soldier01.ZMS` seven times).
  They are stat tiers over one look, so this is one set, not seven. Grade
  "Brave" is taken arbitrarily; any of the seven would give identical art.
* **Jrose's obvious candidate is art we already ship.** Its level 190-199 band
  carries a handsome eight-class line -- Gaia, Tartaros, Cybele, Idea, Hermes,
  Artemis, Ares, Hephaestus -- and every piece resolves to `knight_body01.dds`,
  `champ_body01_190.dds`, `magician_body01_m.dds` and friends. Importing it
  would have added nothing at all.

What is left after that filter is small. This set survives it: four textures new
to us, all four slots, male **and** female models on every row, English names,
and already at level 240 so nothing needs re-levelling.

--- the numbers are extrapolated from our own curve, not invented

Median DEF per slot across our armour runs 200 -> 210 -> 220 in near-constant
steps: cap +38, arms +34, foot +42, body +71. Continuing that for the two steps
to 240 gives per-slot medians of cap 223, body 499, arms 199, foot 252, i.e.
a factor of ~1.52 / 1.40 / 1.52 / 1.50 over Crystal. Each piece is scaled by its
slot's factor, so the **shape** of the Crystal set is preserved and only the tier
moves.

Sanity-checked against what it has to survive, because a big DEF jump can
trivialise content: damage is `ATK - DEF + 250`, total armour DEF goes 803 ->
1173, and Karkia's monsters run a median ATK of 1612 at levels 230-239 and 2785
at 240+. So the set is a 17-35% damage reduction, not immunity -- there is no
level at which these four pieces out-scale the incoming hit.

**One inherited oddity is deliberately propagated.** Crystal's Soldier cap (219)
and gloves (196) are ~50% above their own slot medians where the level-210 tier
spreads only 12%; scaling keeps that lead rather than quietly re-balancing a set
players already own. If it should be flattened, that is a `SCALE` edit here, not
a new import.

--- why --art-only

667's schema is 57 columns to our 36-37, and its stat columns are ability ids
fed into an unbounded `m_iAddValue[nType] += nValue` on both sides. `--art-only`
reads **no source cell at all**: it takes the model, plus the icon, and clones
every column from one of our own rows. The template is the matching Crystal
piece per class and slot, which carries the things that make a class line feel
like one -- the per-class bonus ability (type 10 Soldier / 11 Hawker / 12 Muse /
13 Dealer) and the RES shape. Only level, DEF, RES and price are overridden.

Note the Crystal rows carry **no class gate** -- their only requirement is
`(31, 220)`, a level. The class in the name is advisory, and that is inherited
here too: any class can wear any of these.

--- row space

Armour is sex-split, so each import appends one object to `LIST_M*.ZSC` and one
to `LIST_W*.ZSC` in lockstep. That is also why `--target-row` cannot be used:
the ZSC can only be appended to, so an item written into a blank STB row lower
down would find its art at the wrong index.

`LIST_CAP` is the binding table -- its highest named row is 988, leaving **11
ids** below the 999 ceiling that drop cells, QSD rewards and recipe inputs all
share. This set takes 4 of them and the Steam set will take 4 more, which fits;
a *third* set will not, and would need `zsc_build_append` taught to write at an
index before the table's blank rows lower down become usable.

Idempotent: a re-run appends duplicates, so it refuses to run if the names are
already present. `--dry-run` / `--verify`.

After running: restart the servers and re-bake the VFS. Spawn with
`/item 2:<id>` (cap), `3:` body, `4:` arms, `5:` foot -- GM access 2048.
"""
import argparse
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = r"C:\Users\Thomas\Desktop\Testclients\667\extracted data"

# 667 puts the whole grade on one row number in every slot table.
SRC_ROW = {"Soldier": 6092, "Muse": 6112, "Hawker": 6132, "Dealer": 6152}

# our Crystal set, by slot then class -- the template each piece clones
TEMPLATE = {
    "cap":  {"Soldier": 977, "Muse": 978, "Hawker": 979, "Dealer": 980},
    "body": {"Soldier": 904, "Muse": 905, "Hawker": 906, "Dealer": 907},
    "arms": {"Soldier": 880, "Muse": 881, "Hawker": 882, "Dealer": 883},
    "foot": {"Soldier": 878, "Muse": 879, "Hawker": 880, "Dealer": 881},
}

# (DEF, RES) at 240, = Crystal's value x the slot factor derived above.
STATS = {
    "cap":  {"Soldier": (332, 82), "Muse": (212, 162), "Hawker": (225, 124), "Dealer": (221, 121)},
    "body": {"Soldier": (450, 112), "Muse": (467, 400), "Hawker": (544, 320), "Dealer": (533, 317)},
    "arms": {"Soldier": (298, 74), "Muse": (163, 68), "Hawker": (201, 68), "Dealer": (197, 68)},
    "foot": {"Soldier": (244, 62), "Muse": (250, 40), "Hawker": (256, 32), "Dealer": (254, 32)},
}
PRICE = {"cap": 420000, "body": 225000, "arms": 420000, "foot": 480000}

# Per-class names rather than one set name with a class suffix. That is the
# idiomatic shape for a ROSE tier -- Jrose's endgame line is Gaia / Tartaros /
# Cybele / Idea rather than "X Soldier / X Muse" -- and 667's own names are
# already good English, so they are kept.
LINE = {"Soldier": "Royal Guardian", "Muse": "Sun Prophet",
        "Hawker": "Jackal Bandit", "Dealer": "Serpent Trader"}
PIECE = {
    "Soldier": {"cap": "Helm", "body": "Armour", "arms": "Gauntlets", "foot": "Greaves"},
    "Muse":    {"cap": "Headdress", "body": "Vestment", "arms": "Gloves", "foot": "Sandals"},
    "Hawker":  {"cap": "Mask", "body": "Chestguard", "arms": "Bracers", "foot": "Boots"},
    "Dealer":  {"cap": "Cowl", "body": "Coat", "arms": "Gloves", "foot": "Boots"},
}
FLAVOUR = {
    "Soldier": "Plate in the old desert pattern, gilded at the shoulder. Worn by "
               "guards who never left their post.",
    "Muse":    "Sun-bleached linen and gold leaf. The prophets read the glare off "
               "it and called it scripture.",
    "Hawker":  "Jackal-cut leather, dark and quiet. Made for people who wanted the "
               "dunes to forget them.",
    "Dealer":  "Serpent-scale over merchant's cloth. Traders wore their fortune "
               "where it could be seen.",
}
SLOTS = ("cap", "body", "arms", "foot")
CLASSES = ("Soldier", "Muse", "Hawker", "Dealer")
REQ_LEVEL = 240
STL_KEY = {"cap": "LCAP", "body": "LBOD", "arms": "LARM", "foot": "LFOO"}
STB_FILE = {"cap": "LIST_CAP.STB", "body": "LIST_BODY.STB",
            "arms": "LIST_ARMS.STB", "foot": "LIST_FOOT.STB"}


def plan():
    for cls in CLASSES:
        for slot in SLOTS:
            name = "%s %s" % (LINE[cls], PIECE[cls][slot])
            d, r = STATS[slot][cls]
            yield (slot, cls, name, SRC_ROW[cls], TEMPLATE[slot][cls], d, r)


def run(item, dry):
    slot, cls, name, srow, tmpl, dfn, res = item
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"),
           "--type", slot, "--source", SOURCE,
           "--source-row", str(srow), "--art-only", "--template-row", str(tmpl),
           "--name", name, "--desc", FLAVOUR[cls],
           "--req-level", str(REQ_LEVEL), "--def", str(dfn), "--res", str(res),
           "--price", str(PRICE[slot]), "--copy-icon"]
    if dry:
        cmd.append("--dry-run")
    env = dict(os.environ, PYTHONIOENCODING="utf-8:replace")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load_reader():
    spec = importlib.util.spec_from_file_location(
        "rd", os.path.join(HERE, "rose-data-reader.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def present():
    """{name: (slot, row)} for any of our 16 names already in the tables."""
    rd = load_reader()
    want = {n for _s, _c, n, _sr, _t, _d, _r in plan()}
    found = {}
    for slot in SLOTS:
        s = rd.Stb(os.path.join(ROOT, "data", "3DDATA", "STB", STB_FILE[slot]), "utf-8")
        for r in range(s.rows):
            n = rd.scrub(s.s(r, 0)).strip()
            if n in want:
                found[n] = (slot, r)
    return found


def verify():
    rd = load_reader()
    found = present()
    bad = []
    for slot, cls, name, _sr, _t, dfn, res in plan():
        if name not in found:
            bad.append("%s: missing" % name)
            continue
        got_slot, row = found[name]
        if got_slot != slot:
            bad.append("%s: landed in %s, expected %s" % (name, got_slot, slot))
            continue
        s = rd.Stb(os.path.join(ROOT, "data", "3DDATA", "STB", STB_FILE[slot]), "utf-8")
        lv = 0
        for c in (19, 21):
            if s.i(row, c) == 31:
                lv = s.i(row, c + 1)
        if lv != REQ_LEVEL:
            bad.append("%s: required level %d, want %d" % (name, lv, REQ_LEVEL))
        elif s.i(row, 31) != dfn:
            bad.append("%s: DEF %d, want %d" % (name, s.i(row, 31), dfn))
        elif s.i(row, 32) != res:
            bad.append("%s: RES %d, want %d" % (name, s.i(row, 32), res))
        elif row > 999:
            bad.append("%s: row %d is above the 999 ceiling" % (name, row))
    print("%d pieces; %d problem(s)%s"
          % (len(list(plan())), len(bad),
             (":\n  " + "\n  ".join(bad[:8])) if bad else ""))
    if not bad:
        for slot in SLOTS:
            rows = sorted(r for n, (s, r) in found.items() if s == slot)
            print("  %-5s rows %s   (%d left below 999)"
                  % (slot, rows, 999 - max(rows)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify()

    already = present()
    if already and not args.dry_run:
        print("refusing to run: %d of the 16 names are already in the tables "
              "(appending would duplicate them):" % len(already))
        for n, (s, r) in sorted(already.items()):
            print("  %-32s %s row %d" % (n, s, r))
        return 1

    done, failed = 0, []
    for item in plan():
        rc, out = run(item, args.dry_run)
        slot, _cls, name = item[0], item[1], item[2]
        if rc == 0:
            done += 1
            print("  %-13s %-5s %s" % ("would import" if args.dry_run else "imported",
                                       slot, name))
        else:
            failed.append(name)
            print("  %-13s %-5s %s\n     %s" % ("FAILED", slot, name, out.strip()[-400:]))
    print("\n%d %s, %d failed" % (done, "planned" if args.dry_run else "imported",
                                  len(failed)))
    if failed:
        return 1
    return 0 if args.dry_run else verify()


if __name__ == "__main__":
    sys.exit(main())
