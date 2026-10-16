#!/usr/bin/env python3
"""Import the retail unique weapons we were missing, from the 668 dump (2026-10-16).

Uniques are the violet-named weapons (LIST_WEAPON col 44 = 21, see
set-boss-loot-tier.py) with **no level requirement, only a stat one** (STR, DEX,
INT or CON in the second requirement pair, game cols 21/22). Ours were rows
901-993: 34 weapons on a ladder of two or three tiers per weapon type. The
official Rednim client (doc/668-survey.md) ships the same family with the gaps
filled -- a fourth tier for most types, a third and fourth spear, a third
crossbow / mace / 2H sword / axe / launcher, and a second Egyptian dual weapon.
This takes those 15, at their retail item numbers, so the drop tables can name
them (an item number above 999 can never drop: `Get_DropITEM`).

Art only. Every number is ours: 668 rescaled its whole weapon table (Falchion
ATK 21 there, 89 here; speed in milliseconds), so nothing is read from its rows
except the model, the ground-drop model and the icon index. The icons are
already in our ITEM1.TSI at the same indices (compared visually; the bytes
differ only by 668's DXT re-encode), so no atlas cell is added.

The stats -- **a weapon for a level-180 player that carries them to ~210**
(user, 2026-10-16, after the first in-game look: the first cut, one step above
our old unique ladder, sat at half a level-180 weapon's ATK). Per weapon type,
against our regular weapons after the identity pass:
  * ATK = the type's regular weapon at ~level 205 (midway between its level-200
    retail row and its level-210 set row; duals count their type-wide ATK bonus,
    folded into the column). It beats anything a level-180 player can wear and,
    with its two bonuses, stays level with the 210 gear.
  * Requirement = the stat a regular level-180 weapon of the type asks
    (interpolated); still no level requirement -- that is what makes a unique.
  * Quality = the higher of the level-200 and level-210 rows; durability the
    level-210 row's; price 1.25x the level-200 row's.
  * Bonuses: slot 1 keeps the type's own identity where it has one (bow AVOID
    +72, katar CRIT +70, staff/wand INT +55/+50, crossbow ATK_SPD +29), so a Mage
    loses no INT by equipping one; the other slot (both, for types without one)
    is the unique's flavour from 668 on our scale: ATK +35, CRIT +50, AVOID +35,
    HIT +40, DEF/RES +65, ATK_SPD +25, MP cost -30, Max MP +250. Crook-Flail's
    CHARM +20 became Max HP +450 (charm did nothing for a dual wielder).
  * Template = our top unique of the same weapon type (speed, range, motion,
    effects, sounds, requirement ability). Maces stay with maces (our 212; 668
    files them under 211), and Crook-Flail templates on the dual swords.
The two spears and the two duals share a power level and differ in bonuses.
They now sit far above our older uniques (901-993, ATK ~60-250), which keep
their own low-level ladder.

Re-running applies the table to rows already imported (cell by cell), so the
numbers are edited here and replayed.

Two models were already in our LIST_WEAPON.ZSC behind blank rows (904 Death
Render, 936 Crescent Moon); import-item.py keeps an object that is exactly the
source's model. Oblivion Wand goes to 979, because our 978 is Icicle.

The rows are listed in weapon-identity-pass.py's SKIP: it rescales from its
manifest's originals, and these are already on the post-pass scale -- a re-run
would apply the type factors twice.

Not imported: the "200" series (908, 915 ... 999, one per type, level 200 + a
stat), the dinosaur set (1476-1488, level 250) and the frost set (1448-1460,
level 165, rows taken here) -- they carry a level requirement, so they are
not this family. Drops are a separate step: these 15 drop from nothing yet.

    python scripts/import-668-uniques.py --dry-run
    python scripts/import-668-uniques.py
    python scripts/import-668-uniques.py --verify
    python scripts/import-668-uniques.py --restore

--restore puts back the whole files saved before the first write and deletes
the asset files the import added; it refuses if a table changed since (another
script ran after this one). Restart the servers (they read LIST_WEAPON) and
re-bake.
"""
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = r"C:\Users\Thomas\Desktop\Testclients\668\Extracted"
BACKUP = os.path.join(ROOT, "build", "668-uniques")
MANIFEST = os.path.join(BACKUP, "manifest.json")
TABLES = [r"3DDATA\STB\LIST_WEAPON.STB", r"3DDATA\STB\LIST_WEAPON_S.STL",
          r"3DDATA\WEAPON\LIST_WEAPON.ZSC", r"3DDATA\ITEM\LIST_FieldITEM.ZSC"]
ASSET_ROOT = r"3DDATA\WEAPON\UNIK"
COL_QUALITY, COL_DURABILITY, COL_PREFIX = 8, 29, 44

# our row, 668 row, template, icon, name, requirement, ATK, quality, durability, price, bonuses
ROWS = [
    (904, 904, 903, 944,  "Death Render",      "10:293", 432, 109, 72,  889500, ("18:35", "21:65")),
    (911, 911, 910, 981,  "Sand Hand",         "10:310", 492,  99, 72,  893125, ("18:35", "19:65")),
    (918, 918, 917, 1025, "Cross Bones",       "10:238", 352, 110, 90,  874815, ("26:50", "24:29")),
    (922, 922, 921, 1071, "Reaper",            "10:297", 388,  99, 72,  833375, ("18:35", "20:40")),
    (929, 929, 928, 1148, "Eclipse",           "10:304", 450,  89, 72, 1197190, ("18:35", "19:65")),
    (935, 935, 934, 1111, "Razor Spear",       "10:282", 367, 109, 72, 1190690, ("24:25", "22:35")),
    (936, 936, 934, 1112, "Crescent Moon",     "10:282", 367, 109, 72, 1190690, ("26:50", "18:35")),
    (943, 943, 942, 1203, "Bow of Talons",     "11:278", 407, 109, 72,  799375, ("22:72", "26:50")),
    (955, 955, 954, 1241, "Firelock",          "13:277", 373, 109, 72, 1094190, ("26:50", "24:25")),
    (962, 962, 961, 1277, "Rock Launcher",     "10:154", 416, 101, 90, 1498875, ("18:35", "19:65")),
    (970, 970, 969, 1319, "Cursed Staff",      "12:275", 350,  99, 72, 1167065, ("12:55", "39:250")),
    (979, 978, 977, 1371, "Oblivion Wand",     "12:289", 307,  99, 72, 1227440, ("12:50", "29:30")),
    (986, 986, 985, 1404, "Scorpion Claw",     "11:279", 330, 109, 72,  911375, ("26:70", "24:25")),
    (994, 994, 993, 1447, "Dual Death Render", "11:213", 515,  99, 72,  904500, ("20:40", "26:50")),
    (995, 995, 993, 1448, "Crook-Flail",       "11:213", 515,  99, 72,  904500, ("26:50", "38:450")),
]

# 668's English descriptions, ASCII only (our STL is latin-1).
DESC = {
    904: "A small blade used to wound an enemy in battle, but keep them alive as long as possible.",
    911: "A clump of sand in the shape of a hand, used for slapping your enemies silly.",
    918: "A mysterious crossbow fashioned from the very bones of its defeated victims.",
    922: "This two-handed weapon bears the memory of slayings from a distant time... and a distant plane.",
    929: "This double-sided axe weapon will strike true on a night with no day, and day with no night.",
    935: "An otherworldly spear with sharp teeth and deadly range.",
    936: "With the rise of the crescent moon, the enemies of Hiria shall fall.",
    943: "An otherworldly bow said to be used by the Orlean Prince Horace himself.",
    955: "An otherworldly gun said to have belonged to the fastest hand in all of Orlo.",
    962: "Made from the heart and soul of Orlean golems, this launcher will utterly destroy anything in your path.",
    970: "An otherworldly staff said to be used by Orlean arcane priests long ago.",
    979: "An otherworldly wand said to be used by the Orlean Princess Urubis herself.",
    986: "Lethal claws, made from the spirits of the scorpions, and the venom of oblivion.",
    994: "A pair of blades used to wound your enemies in battle, but keep them alive as long as possible.",
    995: "The pharaoh's instruments of power. To raise followers from oblivion, and topple entire planetary kingdoms.",
}


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def asset_files():
    root = os.path.join(ROOT, "data", ASSET_ROOT)
    return {os.path.relpath(os.path.join(d, f), root)
            for d, _, fs in os.walk(root) for f in fs}


def expected(row, tmpl_row, r):
    """{col: bytes} this script owns on the row (the rest is the template's)."""
    our, _src, _tmpl, icon, _name, req, atk, q, dur, price, bonus = r
    rid, rval = req.split(":")
    want = {9: str(icon), 35: str(atk), COL_QUALITY: str(q), COL_DURABILITY: str(dur),
            5: str(price), COL_PREFIX: "21"}
    for slot, b in zip((24, 27), bonus):
        bid, bval = b.split(":")
        want[slot], want[slot + 1] = bid, bval
    slot = 21 if tmpl_row[21].strip() == rid.encode() else 19
    want[slot], want[slot + 1] = rid, rval
    return {c: v.encode() for c, v in want.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    os.chdir(ROOT)
    ii = load("import_item", "import-item.py")
    stb_path = os.path.join("data", TABLES[0])

    if a.restore:
        if not os.path.exists(MANIFEST):
            sys.exit("nothing to restore (%s not found)" % MANIFEST)
        man = json.load(open(MANIFEST))
        # "after" is written once the batch completes; a batch that died midway
        # has none, and its originals are still the right thing to put back.
        changed = [t for t in TABLES if sha(os.path.join("data", t)) != man["after"].get(t)]
        if man["after"] and changed:
            sys.exit("refusing: changed since the import: %s" % ", ".join(changed))
        for t in TABLES:
            print("restore %s" % t)
            if not a.dry_run:
                shutil.copy2(os.path.join(BACKUP, "orig", os.path.basename(t)),
                             os.path.join("data", t))
        for f in sorted(asset_files() - set(man["assets_before"])):
            print("delete %s" % f)
            if not a.dry_run:
                os.remove(os.path.join("data", ASSET_ROOT, f))
        if not a.dry_run:
            os.remove(MANIFEST)
        return 0

    _, _, _, _, data = ii.stb_read(stb_path)
    names = {r[0]: data[r[0]][0].decode("latin-1").strip() for r in ROWS}

    if a.verify:
        bad = 0
        for r in ROWS:
            row = data[r[0]]
            if names[r[0]] != r[4]:
                print("row %d: name %r, expected %r" % (r[0], names[r[0]], r[4]))
                bad += 1
                continue
            if row[4] != data[r[2]][4]:
                print("row %d: type %r, template %d is %r" % (r[0], row[4], r[2], data[r[2]][4]))
                bad += 1
            for c, v in expected(r[0], data[r[2]], r).items():
                if row[c].strip() != v:
                    print("row %d col %d: %r, expected %r" % (r[0], c, row[c], v))
                    bad += 1
        if bad:
            print("VERIFY FAILED: %d problem(s)" % bad)
            return 1
        print("ALL CHECKS PASSED -- %d uniques in place." % len(ROWS))
        return 0

    todo = [r for r in ROWS if names[r[0]] != r[4]]
    for r in todo:
        if names[r[0]]:
            sys.exit("row %d is %r -- not blank, refusing" % (r[0], names[r[0]]))
    if not todo:
        return restat(a.dry_run, stb_path)

    if not a.dry_run and not os.path.exists(MANIFEST):
        os.makedirs(os.path.join(BACKUP, "orig"), exist_ok=True)
        for t in TABLES:
            shutil.copy2(os.path.join("data", t), os.path.join(BACKUP, "orig", os.path.basename(t)))
        json.dump({"after": {}, "assets_before": sorted(asset_files())},
                  open(MANIFEST, "w"), indent=1)

    for our, src, tmpl, icon, name, req, atk, q, dur, price, bonus in todo:
        print("== %d %s (668 row %d, template %d)" % (our, name, src, tmpl))
        cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
               "--source", SOURCE, "--source-row", str(src), "--art-only",
               "--template-row", str(tmpl), "--target-row", str(our),
               "--name", name, "--desc", DESC[our], "--icon", str(icon),
               "--copy-field-model", "--req-stat", req, "--atk", str(atk),
               "--price", str(price)]
        for b in bonus:
            cmd += ["--bonus", b]
        if a.dry_run:
            cmd.append("--dry-run")
        res = subprocess.run(cmd)
        if res.returncode:
            sys.exit("import-item.py failed on row %d -- stopping (undo: --restore)" % our)
        if not a.dry_run:
            ii.stb_set_cell(stb_path, our, COL_QUALITY, str(q).encode(), False)
            ii.stb_set_cell(stb_path, our, COL_DURABILITY, str(dur).encode(), False)

    if a.dry_run:
        print("dry run: nothing written")
        return 0

    # import-item.py leaves <table>.import-<id>.bak beside each table, and
    # pack.ps1 refuses to bake while a .bak sits under data/.
    for t in TABLES:
        d = os.path.dirname(os.path.join("data", t))
        for f in os.listdir(d):
            if f.endswith(".bak") and ".import-" in f:
                shutil.move(os.path.join(d, f), os.path.join(BACKUP, f))
    man = json.load(open(MANIFEST))
    print("imported %d unique(s); %d asset file(s) added; backups in %s"
          % (len(todo), len(asset_files() - set(man["assets_before"])), BACKUP))
    return restat(False, stb_path)


def restat(dry, stb_path):
    """Bring every imported row's own columns to the table above, cell by cell."""
    from rosefmt import Stb
    t = Stb(stb_path)
    changes = 0
    for r in ROWS:
        our = r[0]
        if t.s(our, 0).strip() != r[4]:
            continue                      # not imported yet (a dry run of the first pass)
        for c, v in sorted(expected(our, t.d[r[2]], r).items()):
            if t.get(our, c).strip() != v:
                print("row %d %-18s col %2d: %s -> %s" % (our, r[4], c,
                      t.get(our, c).decode("latin-1").strip() or "-", v.decode()))
                t.set(our, c, v)
                changes += 1
    if not changes:
        print("nothing to do -- every unique matches the table.")
        return 0
    if dry:
        print("dry run: %d cell(s) would change" % changes)
        return 0
    t.write(stb_path)
    # --restore checks the tables against these hashes before putting the
    # originals back, so they follow every write this script makes.
    man = json.load(open(MANIFEST))
    man["after"] = {p: sha(os.path.join("data", p)) for p in TABLES}
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print("wrote %d cell(s) in LIST_WEAPON.STB" % changes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
