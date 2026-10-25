#!/usr/bin/env python3
"""Replace the level-235 Jotunn line with 668's dinosaur set (2026-10-25).

The Jotunn line (LIST_WEAPON 1437-1446, Jrose) read as recolours of the level-240
mythicals (user: "mostly just recolors of the level 240 ones"). The official Rednim
client (668, doc/668-survey.md) ships a complete level-250 "dinosaur" set at its rows
1476-1488 -- Extinction Ruin, Fossil Endless ... Saurian Retribution, a folder of
their own (`3DDATA/WEAPON/ZATANA/`) -- with a "TBC" placeholder icon (9995). Those
meshes **and** textures are byte-identical to retail's level-200 unique series
(Endless Blade, Devastation, Sundering Force ...), which we never imported, so:

  * each lands at **its retail item number** (908, 915 ... 999): blank rows and
    empty model objects in our tables, and under 1000, so quests and recipes can
    name them (drops can name anything since the wide drop encoding);
  * the icon is the retail series' own -- already in our ITEM1.TSI at the same
    indices (icon25.dds 4095-4108, compared visually against 668's), used by no
    other item, so no atlas cell is added;
  * the level-200 unique series can never come in as well: same art.

Level 235, beside Asmodeus Ritual Blade (124, kept: the tier has two 2H swords).
668's stats are on its own scale (ATK 160-278) and are not read (`--art-only`).
The ten types the Jotunn line had **inherit its row exactly** (template = the old
row: requirement, both bonuses -- 16:120 in slot 1 is the tier's mark --, ATK,
speed, motion, sounds). The three it lacked (2H sword, spear, axe) template on
their level-240 weapon and take the line's own 235/240 ratios, medians over the
ten pairs: stat requirement x0.929, ATK x0.952 --

    Primal Cleave     (Bahamut 352 / 495)  ->  STR 327, ATK 471
    Titan Unyielding  (Oberon  331 / 463)  ->  STR 308, ATK 441
    Saurian Eternity  (Albion  353 / 573)  ->  STR 328, ATK 546

Extinction Ruin is the Devastation mace: 668 files it as a 1H sword (211, retail's
own slip -- it carries the mace motion 3 and mace sound), so it templates on
Naglfar and is our 1H mace (212). The thirteen are a full set, one per type.

Ground-drop models: 668's point at the *level-200* paths
(`WEAPON/WEAPON/onehand/OSW001/onehand200.*`), the same bytes again. Copied as they
are, that would put a second copy of each mesh in another folder, so the 13
field objects are repointed at the ZATANA files (byte equality checked on the
source first) and the copies deleted.

Name text: 668 has no descriptions for the set; one line for the whole tier, the
way the 235 and 240 lines carry one each.

--- the order

    python scripts/replace-235-weapons.py --dry-run
    python scripts/replace-235-weapons.py              # import the 13 + stats
    python scripts/add-karkia-drops.py --rewrite       # WPN_235 now names the 13
    python scripts/add-oro-drops.py --rewrite
    python scripts/replace-235-weapons.py --erase      # strip 1437-1446
    python scripts/replace-235-weapons.py --verify

`--erase` is the house meaning of delete (cf. erase-retired-weapons.py): the ten
rows blanked (ids kept), their LWEA keys removed from every language block, their
ZSC objects emptied and the mesh/material records only they used removed, those
files moved out of data/ -- file by file: their `t_unique_*` folders also hold the
level-240 line's art. It refuses while any STB cell names one of them. No
character in the dev database owned one (`item.type_id = 8`); check again before
running it on a database with players. Their icon cells stay in ITEM1.TSI.

Undo: `--restore` puts back the four tables saved before the first write, deletes
the asset files the import added and moves the erased files back; it refuses if a
table changed since this script last wrote it. The drop tables are not this
script's: re-run the two drop scripts with the old WPN_235 after a restore. All
13 rows are in weapon-identity-pass.py's SKIP (post-pass values). `data/` is
gitignored, so this file is the record. Restart the servers, re-bake the VFS.
"""
import argparse, glob, hashlib, importlib.util, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Stb, Stl, Zsc  # noqa: E402

SOURCE = r"C:\Users\Thomas\Desktop\Testclients\668\Extracted"
BACKUP = os.path.join(ROOT, "build", "replace-235-weapons")
MANIFEST = os.path.join(BACKUP, "manifest.json")
DATA = os.path.join(ROOT, "data")
STB_REL = r"3DDATA\STB\LIST_WEAPON.STB"
STL_REL = r"3DDATA\STB\LIST_WEAPON_S.STL"
ZSC_REL = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
FIELD_REL = r"3DDATA\ITEM\LIST_FieldITEM.ZSC"
TABLES = [STB_REL, STL_REL, ZSC_REL, FIELD_REL]
ASSET_ROOT = r"3DDATA\WEAPON"
T_WEAPON, WIDE_BASE = 8, 100000
LEVEL = 235

# our row, 668 row, template, type, icon, name, requirement, ATK, bonus slot 2
ROWS = [
    (908, 1477, 1437, 211, 4104, "Fossil Endless",       "10:341", 518, None),
    (915, 1476, 1438, 212, 4102, "Extinction Ruin",      "10:356", 598, None),
    (926, 1479, 1389, 221, 4106, "Primal Cleave",        "10:327", 471, None),
    (939, 1480, 1392, 222, 4105, "Titan Unyielding",     "10:308", 441, None),
    (932, 1478, 1395, 223, 4095, "Saurian Eternity",     "10:328", 546, None),
    (947, 1481, 1439, 231, 4096, "Ptero Pierce",         "11:327", 488, "22:80"),
    (959, 1483, 1440, 232, 4099, "Dino Rifter",          "13:275", 453, None),
    (966, 1484, 1441, 233, 4101, "Fossil Flare",         "10:174", 512, None),
    (974, 1485, 1442, 241, 4103, "Bone Shatter",         "12:312", 457, "12:60"),
    (982, 1486, 1443, 242, 4108, "Apex Savior",          "12:322", 409, "12:50"),
    (990, 1488, 1444, 251, 4100, "Saurian Retribution",  "11:327", 419, "26:75"),
    (999, 1487, 1445, 252, 4098, "Jawbreaker Doon",      "11:254", 608, "11:10"),
    (950, 1482, 1446, 271, 4097, "Raptor Reverberation", "10:166", 423, "24:29"),
]
BONUS_1 = "16:120"      # the 235 line's mark (the 230 line has ATK+10, the 240 CRIT+18)
DESC = "Cut from the bones of something that ruled the world before anyone was there to name it."

OLD = {1437: "Jotunn", 1438: "Naglfar", 1439: "Goliath", 1440: "Titan",
       1441: "Gigantes", 1442: "Mistcalf", 1443: "Bergelmir", 1444: "Nephilim",
       1445: "Hecatoncheir", 1446: "Kumbhakarna"}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def data(rel):
    return os.path.join(DATA, rel)


def asset_files():
    root = data(ASSET_ROOT)
    return {os.path.relpath(os.path.join(d, f), root)
            for d, _, fs in os.walk(root) for f in fs}


def norm(p):
    return p.decode("latin-1").replace("/", "\\").lower()


def on_disk(p):
    """The file a ZSC path names, under data/ (case-insensitive, as the VFS is)."""
    parts = norm(p).split("\\")
    cur = DATA
    for part in parts:
        if not os.path.isdir(cur):
            return None
        hit = [e for e in os.listdir(cur) if e.lower() == part]
        if not hit:
            return None
        cur = os.path.join(cur, hit[0])
    return cur


def source_file(p):
    rel = norm(p).split("\\")
    cur = SOURCE
    for part in rel:
        hit = [e for e in os.listdir(cur) if e.lower() == part]
        if not hit:
            return None
        cur = os.path.join(cur, hit[0])
    return cur


def save_after(man):
    man["after"] = {t: sha(data(t)) for t in TABLES}
    json.dump(man, open(MANIFEST, "w"), indent=1)


def expected(r):
    """{col: bytes} this script owns on a new row (the rest is the template's)."""
    our, _src, _tmpl, wtype, icon, name, req, atk, bonus2 = r
    rid, rval = req.split(":")
    b1id, b1val = BONUS_1.split(":")
    b2id, b2val = bonus2.split(":") if bonus2 else ("", "")
    want = {0: name, 4: str(wtype), 9: str(icon), 19: "31", 20: str(LEVEL),
            21: rid, 22: rval, 24: b1id, 25: b1val, 27: b2id, 28: b2val,
            35: str(atk), 44: ""}
    return {c: v.encode("latin-1") for c, v in want.items()}


# ------------------------------------------------------------------ import
def do_import(dry):
    stb = Stb(data(STB_REL))
    todo = [r for r in ROWS if stb.get(r[0], 0).decode("latin-1").strip() != r[5]]
    for r in todo:
        cur = stb.get(r[0], 0).decode("latin-1").strip()
        if cur:
            sys.exit("row %d is %r -- not blank, refusing" % (r[0], cur))
        tname = stb.get(r[2], 0).decode("latin-1").strip()
        if int(stb.get(r[2], 4) or 0) != r[3]:
            sys.exit("template %d (%s) is type %s, expected %d"
                     % (r[2], tname, stb.get(r[2], 4).decode(), r[3]))
    if not todo:
        print("all 13 imported already")
        return restat(dry)

    if not dry and not os.path.exists(MANIFEST):
        os.makedirs(os.path.join(BACKUP, "orig"), exist_ok=True)
        for t in TABLES:
            shutil.copy2(data(t), os.path.join(BACKUP, "orig", os.path.basename(t)))
        json.dump({"after": {}, "assets_before": sorted(asset_files()), "erased": []},
                  open(MANIFEST, "w"), indent=1)

    for our, src, tmpl, _t, icon, name, _req, _atk, _b2 in todo:
        print("== %d %s (668 row %d, template %d)" % (our, name, src, tmpl))
        cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
               "--source", SOURCE, "--source-row", str(src), "--art-only",
               "--template-row", str(tmpl), "--target-row", str(our),
               "--name", name, "--desc", DESC, "--icon", str(icon),
               "--copy-field-model"]
        if dry:
            cmd.append("--dry-run")
        if subprocess.run(cmd, cwd=ROOT).returncode:
            sys.exit("import-item.py failed on row %d -- stopping (undo: --restore)" % our)
    if dry:
        print("dry run: nothing written")
        return 0

    # import-item.py leaves <table>.import-<id>.bak beside each table, and
    # pack.ps1 refuses to bake while a .bak sits under data/.
    for t in TABLES:
        d = os.path.dirname(data(t))
        for f in os.listdir(d):
            if f.endswith(".bak") and ".import-" in f:
                shutil.move(os.path.join(d, f), os.path.join(BACKUP, f))
    repoint_field()
    return restat(False)


def repoint_field():
    """Point the 13 ground models at the ZATANA files instead of the copied
    level-200 ones, then delete those copies (only ones this import added)."""
    stb, wz, fz = Stb(data(STB_REL)), Zsc(data(ZSC_REL)), Zsc(data(FIELD_REL))
    ours = {int(stb.get(r[0], 10)) for r in ROWS}
    mesh_to, mat_to = {}, {}
    for r in ROWS:
        fid = int(stb.get(r[0], 10))
        wparts, fparts = wz.objects[r[0]][1], fz.objects[fid][1]
        if len(wparts) != len(fparts):
            sys.exit("row %d: weapon has %d parts, ground model %d" % (r[0], len(wparts), len(fparts)))
        for (wm, wt, _), (fm, ft, _) in zip(wparts, fparts):
            for old, new, out in ((fz.meshes[fm], wz.meshes[wm], mesh_to.setdefault(fm, [])),
                                  (fz.materials[ft][0], wz.materials[wt][0], mat_to.setdefault(ft, []))):
                a, b = source_file(old), source_file(new)
                if not a or not b or open(a, "rb").read() != open(b, "rb").read():
                    sys.exit("row %d: %s is not byte-identical to %s in 668 -- not repointing"
                             % (r[0], old.decode(), new.decode()))
                out.append(new)
    for i, (_c, parts, _d, _b) in enumerate(fz.objects):
        if i in ours:
            continue
        for m, t, _p in parts:
            if m in mesh_to or t in mat_to:
                sys.exit("ground model %d also uses a record being repointed" % i)
    old_paths = set()
    for i, news in mesh_to.items():
        old_paths.add(fz.meshes[i])
        fz.meshes[i] = news[0]
    for i, news in mat_to.items():
        old_paths.add(fz.materials[i][0])
        fz.materials[i] = (news[0], fz.materials[i][1])
    if old_paths & set(fz.meshes) | old_paths & {m[0] for m in fz.materials}:
        sys.exit("another ground model still names a level-200 path")
    open(data(FIELD_REL), "wb").write(fz.without())
    before = set(json.load(open(MANIFEST))["assets_before"])
    gone = 0
    for p in sorted(old_paths):
        f = on_disk(p)
        if f and os.path.relpath(f, data(ASSET_ROOT)) not in before:
            os.remove(f)
            gone += 1
            d = os.path.dirname(f)
            while d != data(ASSET_ROOT) and not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
    print("ground models: %d mesh + %d material record(s) repointed at ZATANA, "
          "%d level-200 copy file(s) removed" % (len(mesh_to), len(mat_to), gone))


def restat(dry):
    t = Stb(data(STB_REL))
    changes = 0
    for r in ROWS:
        if t.get(r[0], 0).decode("latin-1").strip() != r[5]:
            continue                    # not imported yet (dry run)
        for c, v in sorted(expected(r).items()):
            if t.get(r[0], c).strip() != v:
                print("row %d %-20s col %2d: %s -> %s" % (r[0], r[5], c,
                      t.get(r[0], c).decode("latin-1").strip() or "-", v.decode() or "-"))
                t.set(r[0], c, v)
                changes += 1
    if not changes:
        print("stats: every row matches the table")
        return 0
    if dry:
        print("dry run: %d cell(s) would change" % changes)
        return 0
    t.write(data(STB_REL))
    save_after(json.load(open(MANIFEST)))
    print("wrote %d cell(s) in LIST_WEAPON.STB" % changes)
    return 0


# ------------------------------------------------------------------ erase
def live_references():
    codes = {str(T_WEAPON * WIDE_BASE + r) for r in OLD}
    hits = []
    for p in glob.glob(os.path.join(DATA, "3DDATA", "STB", "*.STB")):
        t = Stb(p)
        for r, row in enumerate(t.d):
            for c, b in enumerate(row):
                if b.strip().decode("latin-1") in codes:
                    hits.append("%s row %d col %d" % (os.path.basename(p), r, c))
    return hits


def erase(dry):
    if not os.path.exists(MANIFEST):
        sys.exit("import first (no manifest)")
    stb, stl, z = Stb(data(STB_REL)), Stl(data(STL_REL)), Zsc(data(ZSC_REL))
    left = [r for r in OLD if any(c.strip() for c in stb.d[r])]
    keys = [k for k in ("LWEA%d" % r for r in OLD) if stl.has(k)]
    objs = [r for r in OLD if z.objects[r][1]]
    if not (left or keys or objs):
        print("nothing to erase")
        return 0
    for r in left:
        cur = stb.get(r, 0).decode("latin-1").strip()
        if cur != OLD[r]:
            sys.exit("LIST_WEAPON %d is %r, expected %r" % (r, cur, OLD[r]))
    hits = live_references()
    if hits:
        sys.exit("still referenced (re-run the drop scripts first):\n  " + "\n  ".join(hits))

    mine_m = {m for r in OLD for m, _t, _p in z.objects[r][1]}
    mine_t = {t for r in OLD for _m, t, _p in z.objects[r][1]}
    for i, (_c, parts, _d, _b) in enumerate(z.objects):
        if i not in OLD:
            mine_m -= {m for m, _t, _p in parts}
            mine_t -= {t for _m, t, _p in parts}
    paths = sorted({norm(z.meshes[m]) for m in mine_m} | {norm(z.materials[t][0]) for t in mine_t})
    for p in glob.glob(os.path.join(DATA, "3DDATA", "**", "*.ZSC"), recursive=True):
        if os.path.samefile(p, data(ZSC_REL)):
            continue
        blob = open(p, "rb").read().lower().replace(b"/", b"\\")
        for q in paths:
            if q.encode("latin-1") in blob:
                sys.exit("%s also references %s" % (p, q))
    files = [on_disk(p.encode("latin-1")) for p in paths]
    print("erase %d row(s), %d STL key(s), %d object(s); %d mesh + %d material record(s), "
          "%d file(s)" % (len(left), len(keys), len(objs), len(mine_m), len(mine_t),
                          sum(1 for f in files if f)))
    if dry:
        print("dry run: nothing written")
        return 0

    for r in left:
        stb.d[r] = [b"" for _ in stb.d[r]]
    stl.remove(keys)
    for r in objs:
        z.objects[r] = (z.objects[r][0], [], [], b"")
    out = z.without(mine_m, mine_t)
    open(data(STB_REL), "wb").write(stb.to_bytes())
    open(data(STL_REL), "wb").write(stl.to_bytes())
    open(data(ZSC_REL), "wb").write(out)
    man = json.load(open(MANIFEST))
    for f in files:
        if not f:
            continue
        rel = os.path.relpath(f, DATA)
        dst = os.path.join(BACKUP, "erased", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(f, dst)
        man["erased"].append(rel)
    save_after(man)
    print("erased; restart the servers and re-bake the VFS")
    return 0


# ------------------------------------------------------------------ verify / restore
def verify():
    bad = []
    stb, stl, z, fz = Stb(data(STB_REL)), Stl(data(STL_REL)), Zsc(data(ZSC_REL)), Zsc(data(FIELD_REL))
    for r in ROWS:
        for c, v in expected(r).items():
            if stb.get(r[0], c).strip() != v:
                bad.append("row %d col %d: %r, expected %r" % (r[0], c, stb.get(r[0], c), v))
        if not stl.has("LWEA%d" % r[0]) or stl.name("LWEA%d" % r[0]) != r[5]:
            bad.append("row %d: STL name" % r[0])
        parts = z.objects[r[0]][1]
        if not parts or any(b"zatana" not in z.meshes[m].lower() for m, _t, _p in parts):
            bad.append("row %d: weapon model is not the ZATANA mesh" % r[0])
        fparts = fz.objects[int(stb.get(r[0], 10) or 0)][1]
        if not fparts or any(b"zatana" not in fz.meshes[m].lower() for m, _t, _p in fparts):
            bad.append("row %d: ground model is not the ZATANA mesh" % r[0])
        for m, t, _p in parts + fparts:
            src = z if (m, t, _p) in parts else fz
            for p in (src.meshes[m], src.materials[t][0]):
                if not on_disk(p):
                    bad.append("row %d: %s missing from data/" % (r[0], p.decode()))
    for r in OLD:
        if any(c.strip() for c in stb.d[r]) or stl.has("LWEA%d" % r) or z.objects[r][1]:
            bad.append("row %d (%s) not erased" % (r, OLD[r]))
    bad += ["still referenced: " + h for h in live_references()]
    for b in bad:
        print("  " + b)
    print("VERIFY FAILED: %d problem(s)" % len(bad) if bad
          else "ALL CHECKS PASSED -- 13 dinosaur weapons at 235, the Jotunn line erased.")
    return 1 if bad else 0


def restore(dry):
    if not os.path.exists(MANIFEST):
        sys.exit("nothing to restore")
    man = json.load(open(MANIFEST))
    changed = [t for t in TABLES if man["after"] and sha(data(t)) != man["after"].get(t)]
    if changed:
        sys.exit("refusing: changed since this script wrote them: %s" % ", ".join(changed))
    for t in TABLES:
        print("restore %s" % t)
        if not dry:
            shutil.copy2(os.path.join(BACKUP, "orig", os.path.basename(t)), data(t))
    for rel in man["erased"]:
        print("move back %s" % rel)
        if not dry:
            os.makedirs(os.path.dirname(os.path.join(DATA, rel)), exist_ok=True)
            shutil.move(os.path.join(BACKUP, "erased", rel), os.path.join(DATA, rel))
    for f in sorted(asset_files() - set(man["assets_before"])):
        print("delete %s" % f)
        if not dry:
            os.remove(os.path.join(data(ASSET_ROOT), f))
    if not dry:
        os.remove(MANIFEST)
    print("restored; re-run the drop scripts with the old WPN_235")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--erase", action="store_true", help="strip the Jotunn line (1437-1446)")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.verify:
        return verify()
    if a.restore:
        return restore(a.dry_run)
    if a.erase:
        return erase(a.dry_run)
    return do_import(a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
