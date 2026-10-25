"""Shared engine of the weapon-tier replacements: replace-235-weapons.py (668's
dinosaur set over the Jotunn line) and replace-210-weapons.py (tsuki's 220 set over
the Viper line). A script describes its tier -- source dump, rows, the line it
erases -- and calls `main(tier)`; the reasoning lives in each script's docstring.

The steps, all from the repo root:

    <script> --dry-run
    <script>                 import the new rows (import-item.py --art-only, one per row,
                             at its --target-row) and set the cells the tier owns
    (re-plan the drop tables / shops that name the old line -- see the script)
    <script> --erase         strip the old line: rows blanked (ids kept), LWEA keys
                             removed, ZSC objects emptied, the mesh/material records only
                             they used removed and those files moved out of data/, file
                             by file. Refuses while any STB cell or monster hand names one.
    <script> --verify
    <script> --restore       whole-file originals back, added files deleted, erased
                             files moved back; refuses if a table changed since the
                             script last wrote it (hash in the manifest)

What a new row owns, beyond the template's columns: name, type, level, the cells its
script lists (requirement, bonuses, ATK), the icon, and **the gem anchor (col 43),
always the source's** -- it indexes the model's own dummy points, so a template's
value can sit on the wrong point or past the model (no glow).

Ground models: a source whose drop object names other files than the weapon's -- byte
for byte the same (668 points at its level-200 copies) -- is repointed at the weapon's
files and the copies deleted, so no mesh lands in data/ twice.
"""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Stb, Stl, Zsc  # noqa: E402

DATA = os.path.join(ROOT, "data")
STB_REL = r"3DDATA\STB\LIST_WEAPON.STB"
STL_REL = r"3DDATA\STB\LIST_WEAPON_S.STL"
ZSC_REL = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
FIELD_REL = r"3DDATA\ITEM\LIST_FieldITEM.ZSC"
NPC_REL = r"3DDATA\STB\LIST_NPC.STB"
RES_REL = r"3DDATA\CONTROL\RES"
TSI_REL = RES_REL + r"\ITEM1.TSI"
ASSET_ROOTS = [r"3DDATA\WEAPON", RES_REL]
T_WEAPON, WIDE_BASE = 8, 100000
COL_ICON, COL_GEM, COL_PREFIX = 9, 43, 44
NPC_RIGHT_HAND = 5                  # a monster's weapon, a LIST_WEAPON row number


@dataclass
class Row:
    our: int                        # target row (blank, under 1000)
    src: int                        # source row
    tmpl: int                       # our row whose columns it clones
    wtype: int
    name: str
    desc: str
    cells: Dict[int, str]           # tier cells: requirement, bonuses, ATK ...
    icon: Optional[int] = None      # an index already in our atlas; None = copy the source's


@dataclass
class Tier:
    key: str                        # build/<key>/
    source: str                     # dump root holding 3DDATA
    level: int
    rows: List[Row]
    old: Dict[int, str]             # the line --erase strips: row -> name
    restock: Optional[Callable] = None      # (tier, dry) -> None, first thing --erase does
    check: Optional[Callable] = None        # () -> [problem], run by --verify
    backup: str = field(init=False)
    manifest: str = field(init=False)

    def __post_init__(self):
        self.backup = os.path.join(ROOT, "build", self.key)
        self.manifest = os.path.join(self.backup, "manifest.json")

    @property
    def copy_icon(self):
        return any(r.icon is None for r in self.rows)

    def tables(self):
        """Files saved whole before the first write."""
        out = [STB_REL, STL_REL, ZSC_REL, FIELD_REL]
        if self.copy_icon:
            # add-item-icon.py writes ITEM1.TSI and the last extension sheet
            out.append(TSI_REL)
            out += [os.path.relpath(p, DATA) for p in sorted(glob.glob(data(RES_REL, "icon[5-9][0-9].dds")))]
        return out


def data(*rel):
    return os.path.join(DATA, *rel)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def asset_files():
    return {os.path.relpath(os.path.join(d, f), DATA)
            for root in ASSET_ROOTS for d, _, fs in os.walk(data(root)) for f in fs}


def norm(p):
    return p.decode("latin-1").replace("/", "\\").lower()


def resolve(root, p):
    """The file a ZSC path names under `root` (case-insensitive, as the VFS is)."""
    cur = root
    for part in norm(p).split("\\"):
        if not os.path.isdir(cur):
            return None
        hit = [e for e in os.listdir(cur) if e.lower() == part]
        if not hit:
            return None
        cur = os.path.join(cur, hit[0])
    return cur


def load_manifest(tier):
    man = json.load(open(tier.manifest))
    man.setdefault("icons", {})
    man.setdefault("sell", {})
    return man


def save(tier, man):
    man["after"] = {t: sha(data(t)) for t in man["tables"]}
    json.dump(man, open(tier.manifest, "w"), indent=1)


def expected(tier, r, src_stb, man):
    """{col: bytes} a new row owns (everything else is its template's)."""
    want = {0: r.name, 4: str(r.wtype), 19: "31", 20: str(tier.level), COL_PREFIX: "",
            COL_GEM: src_stb.get(r.src, COL_GEM).decode("latin-1").strip()}
    want.update(r.cells)
    icon = r.icon if r.icon is not None else man.get("icons", {}).get(str(r.our))
    if icon is not None:
        want[COL_ICON] = str(icon)
    return {c: v.encode("latin-1") for c, v in want.items()}


# ------------------------------------------------------------------ import
def do_import(tier, dry):
    stb = Stb(data(STB_REL))
    todo = [r for r in tier.rows if stb.get(r.our, 0).decode("latin-1").strip() != r.name]
    for r in todo:
        cur = stb.get(r.our, 0).decode("latin-1").strip()
        if cur:
            sys.exit("row %d is %r -- not blank, refusing" % (r.our, cur))
        if int(stb.get(r.tmpl, 4) or 0) != r.wtype:
            sys.exit("template %d (%s) is type %s, expected %d" % (
                r.tmpl, stb.get(r.tmpl, 0).decode("latin-1"), stb.get(r.tmpl, 4).decode(), r.wtype))
        for s in (r.name, r.desc):
            s.encode("ascii")           # our STL is latin-1; keep imports plain ASCII
    if not todo:
        print("all %d imported already" % len(tier.rows))
        return restat(tier, dry)

    if not dry and not os.path.exists(tier.manifest):
        os.makedirs(os.path.join(tier.backup, "orig"), exist_ok=True)
        tables = tier.tables()
        for t in tables:
            shutil.copy2(data(t), os.path.join(tier.backup, "orig", os.path.basename(t)))
        json.dump({"tables": tables, "after": {}, "assets_before": sorted(asset_files()),
                   "erased": [], "icons": {}, "sell": {}},
                  open(tier.manifest, "w"), indent=1)

    for r in todo:
        print("== %d %s (source row %d, template %d)" % (r.our, r.name, r.src, r.tmpl))
        cmd = [sys.executable, os.path.join(HERE, "import-item.py"), "--type", "weapon",
               "--source", tier.source, "--source-row", str(r.src), "--art-only",
               "--template-row", str(r.tmpl), "--target-row", str(r.our),
               "--name", r.name, "--desc", r.desc, "--copy-field-model"]
        cmd += ["--copy-icon"] if r.icon is None else ["--icon", str(r.icon)]
        if dry:
            cmd.append("--dry-run")
        if subprocess.run(cmd, cwd=ROOT).returncode:
            # an import that dies late leaves atlas cells behind: --restore puts the
            # whole atlas back, which reclaims them
            sys.exit("import-item.py failed on row %d -- stopping (undo: --restore)" % r.our)
        if not dry and r.icon is None:
            man = load_manifest(tier)
            man["icons"][str(r.our)] = int(Stb(data(STB_REL)).get(r.our, COL_ICON))
            json.dump(man, open(tier.manifest, "w"), indent=1)
    if dry:
        print("dry run: nothing written")
        return 0

    # import-item.py leaves <table>.import-<id>.bak beside each table and
    # add-item-icon.py ITEM1.TSI.bak-icons; pack.ps1 refuses to bake while a .bak
    # sits under data/.
    for d in {os.path.dirname(data(t)) for t in tier.tables()}:
        for f in os.listdir(d):
            if f.endswith(".bak") and ".import-" in f or f.endswith(".bak-icons"):
                shutil.move(os.path.join(d, f), os.path.join(tier.backup, f))
    repoint_field(tier)
    return restat(tier, False)


def repoint_field(tier):
    stb, wz, fz = Stb(data(STB_REL)), Zsc(data(ZSC_REL)), Zsc(data(FIELD_REL))
    ours = {int(stb.get(r.our, 10)) for r in tier.rows}
    mesh_to, mat_to = {}, {}
    for r in tier.rows:
        fid = int(stb.get(r.our, 10))
        wparts, fparts = wz.objects[r.our][1], fz.objects[fid][1]
        if len(wparts) != len(fparts):
            continue                    # a ground model of its own: leave it
        for (wm, wt, _), (fm, ft, _) in zip(wparts, fparts):
            for old, new, out, i in ((fz.meshes[fm], wz.meshes[wm], mesh_to, fm),
                                     (fz.materials[ft][0], wz.materials[wt][0], mat_to, ft)):
                if norm(old) == norm(new):
                    continue
                a, b = resolve(tier.source, old), resolve(tier.source, new)
                if a and b and open(a, "rb").read() == open(b, "rb").read():
                    out[i] = new
    if not mesh_to and not mat_to:
        print("ground models: already the weapons' own files")
        return
    for i, (_c, parts, _d, _b) in enumerate(fz.objects):
        if i not in ours and any(m in mesh_to or t in mat_to for m, t, _p in parts):
            sys.exit("ground model %d also uses a record being repointed" % i)
    old_paths = {fz.meshes[i] for i in mesh_to} | {fz.materials[i][0] for i in mat_to}
    for i, new in mesh_to.items():
        fz.meshes[i] = new
    for i, new in mat_to.items():
        fz.materials[i] = (new, fz.materials[i][1])
    open(data(FIELD_REL), "wb").write(fz.without())
    before = set(load_manifest(tier)["assets_before"])
    gone = 0
    for p in sorted(old_paths):
        f = resolve(DATA, p)
        if f and os.path.relpath(f, DATA) not in before:
            os.remove(f)
            gone += 1
            d = os.path.dirname(f)
            while not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
    print("ground models: %d mesh + %d material record(s) repointed at the weapons' "
          "files, %d duplicate file(s) removed" % (len(mesh_to), len(mat_to), gone))


def restat(tier, dry):
    t, src = Stb(data(STB_REL)), Stb(os.path.join(tier.source, STB_REL))
    man = load_manifest(tier) if os.path.exists(tier.manifest) else {"icons": {}}
    changes = 0
    for r in tier.rows:
        if t.get(r.our, 0).decode("latin-1").strip() != r.name:
            continue                    # not imported yet (dry run)
        for c, v in sorted(expected(tier, r, src, man).items()):
            if t.get(r.our, c).strip() != v:
                print("row %d %-26s col %2d: %s -> %s" % (r.our, r.name, c,
                      t.get(r.our, c).decode("latin-1").strip() or "-", v.decode() or "-"))
                t.set(r.our, c, v)
                changes += 1
    if not changes:
        print("stats: every row matches the table")
        return 0
    if dry:
        print("dry run: %d cell(s) would change" % changes)
        return 0
    t.write(data(STB_REL))
    save(tier, man)
    print("wrote %d cell(s) in LIST_WEAPON.STB" % changes)
    return 0


# ------------------------------------------------------------------ erase
def live_references(tier):
    codes = {str(T_WEAPON * WIDE_BASE + r) for r in tier.old}
    codes |= {str(T_WEAPON * 1000 + r) for r in tier.old if r <= 999}
    hits = []
    for p in glob.glob(data(r"3DDATA\STB\*.STB")):
        t = Stb(p)
        for r, row in enumerate(t.d):
            for c, b in enumerate(row):
                if b.strip().decode("latin-1") in codes:
                    hits.append("%s row %d col %d" % (os.path.basename(p), r, c))
    npc = Stb(data(NPC_REL))
    for r in range(npc.rows):
        v = npc.get(r, NPC_RIGHT_HAND).strip()
        if v.isdigit() and int(v) in tier.old:
            hits.append("LIST_NPC row %d holds weapon %s" % (r, v.decode()))
    return hits


def erase(tier, dry):
    if not os.path.exists(tier.manifest):
        sys.exit("import first (no manifest)")
    if tier.restock:
        tier.restock(tier, dry)
    stb, stl, z = Stb(data(STB_REL)), Stl(data(STL_REL)), Zsc(data(ZSC_REL))
    left = [r for r in tier.old if any(c.strip() for c in stb.d[r])]
    keys = [k for k in ("LWEA%d" % r for r in tier.old) if stl.has(k)]
    objs = [r for r in tier.old if z.objects[r][1]]
    if not (left or keys or objs):
        print("nothing to erase")
        return 0
    for r in left:
        cur = stb.get(r, 0).decode("latin-1").strip()
        if cur != tier.old[r]:
            sys.exit("LIST_WEAPON %d is %r, expected %r" % (r, cur, tier.old[r]))
    hits = live_references(tier)
    if hits and not dry:
        sys.exit("still referenced (re-plan the drops / shops first):\n  " + "\n  ".join(hits))
    for h in hits:
        print("  (dry run) still referenced: " + h)

    mine_m = {m for r in tier.old for m, _t, _p in z.objects[r][1]}
    mine_t = {t for r in tier.old for _m, t, _p in z.objects[r][1]}
    for i, (_c, parts, _d, _b) in enumerate(z.objects):
        if i not in tier.old:
            mine_m -= {m for m, _t, _p in parts}
            mine_t -= {t for _m, t, _p in parts}
    paths = sorted({norm(z.meshes[m]) for m in mine_m} | {norm(z.materials[t][0]) for t in mine_t})
    for p in glob.glob(data(r"3DDATA\**\*.ZSC"), recursive=True):
        if os.path.samefile(p, data(ZSC_REL)):
            continue
        blob = open(p, "rb").read().lower().replace(b"/", b"\\")
        for q in paths:
            if q.encode("latin-1") in blob:
                sys.exit("%s also references %s" % (p, q))
    files = [f for f in (resolve(DATA, p.encode("latin-1")) for p in paths) if f]
    print("erase %d row(s), %d STL key(s), %d object(s); %d mesh + %d material record(s), "
          "%d file(s)" % (len(left), len(keys), len(objs), len(mine_m), len(mine_t), len(files)))
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
    man = load_manifest(tier)
    for f in files:
        rel = os.path.relpath(f, DATA)
        dst = os.path.join(tier.backup, "erased", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(f, dst)
        man["erased"].append(rel)
    save(tier, man)
    print("erased; restart the servers and re-bake the VFS")
    return 0


# ------------------------------------------------------------------ verify / restore
def verify(tier):
    bad = []
    stb, stl = Stb(data(STB_REL)), Stl(data(STL_REL))
    z, fz = Zsc(data(ZSC_REL)), Zsc(data(FIELD_REL))
    src = Stb(os.path.join(tier.source, STB_REL))
    man = load_manifest(tier)
    for r in tier.rows:
        for c, v in expected(tier, r, src, man).items():
            if stb.get(r.our, c).strip() != v:
                bad.append("row %d col %d: %r, expected %r" % (r.our, c, stb.get(r.our, c), v))
        if r.icon is None and str(r.our) not in man["icons"]:
            bad.append("row %d: copied icon not recorded" % r.our)
        if not stl.has("LWEA%d" % r.our) or stl.name("LWEA%d" % r.our) != r.name:
            bad.append("row %d: STL name" % r.our)
        parts = z.objects[r.our][1]
        fparts = fz.objects[int(stb.get(r.our, 10) or 0)][1]
        if not parts or not fparts:
            bad.append("row %d: weapon or ground model is empty" % r.our)
        for zz, pp in ((z, parts), (fz, fparts)):
            for m, t, _p in pp:
                for p in (zz.meshes[m], zz.materials[t][0]):
                    if not resolve(DATA, p):
                        bad.append("row %d: %s missing from data/" % (r.our, p.decode()))
    for r in tier.old:
        if any(c.strip() for c in stb.d[r]) or stl.has("LWEA%d" % r) or z.objects[r][1]:
            bad.append("row %d (%s) not erased" % (r, tier.old[r]))
    bad += ["still referenced: " + h for h in live_references(tier)]
    if tier.check:
        bad += tier.check(tier)
    for b in bad:
        print("  " + b)
    print("VERIFY FAILED: %d problem(s)" % len(bad) if bad else
          "ALL CHECKS PASSED -- %d weapons at %d, the old line erased."
          % (len(tier.rows), tier.level))
    return 1 if bad else 0


def restore(tier, dry):
    if not os.path.exists(tier.manifest):
        sys.exit("nothing to restore")
    man = load_manifest(tier)
    changed = [t for t in man["tables"] if man["after"] and sha(data(t)) != man["after"].get(t)]
    if changed:
        sys.exit("refusing: changed since this script wrote them: %s" % ", ".join(changed))
    for t in man["tables"]:
        print("restore %s" % t)
        if not dry:
            shutil.copy2(os.path.join(tier.backup, "orig", os.path.basename(t)), data(t))
    for rel in man["erased"]:
        print("move back %s" % rel)
        if not dry:
            os.makedirs(os.path.dirname(data(rel)), exist_ok=True)
            shutil.move(os.path.join(tier.backup, "erased", rel), data(rel))
    for f in sorted(asset_files() - set(man["assets_before"])):
        print("delete %s" % f)
        if not dry:
            os.remove(data(f))
    if man["sell"]:
        sell = Stb(data(r"3DDATA\STB\LIST_SELL.STB"))
        for k, v in man["sell"].items():
            r, c = (int(x) for x in k.split(","))
            sell.set(r, c, v.encode("latin-1"))
        print("restore %d LIST_SELL cell(s)" % len(man["sell"]))
        if not dry:
            open(data(r"3DDATA\STB\LIST_SELL.STB"), "wb").write(sell.to_bytes())
    if not dry:
        os.remove(tier.manifest)
    print("restored; re-plan the drop tables with the old line (see the script)")
    return 0


def main(tier):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--erase", action="store_true", help="strip the old line")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.verify:
        return verify(tier)
    if a.restore:
        return restore(tier, a.dry_run)
    if a.erase:
        return erase(tier, a.dry_run)
    return do_import(tier, a.dry_run)
