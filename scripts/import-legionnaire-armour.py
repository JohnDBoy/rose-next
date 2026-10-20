"""Import the 667 client's level-220 class sets as a second level-230 tier.

**Level 235 since 2026-10-20:** `armour-ladder-pass.py` made Unit Core a level-10
cosmetic, and `armour-endgame-sets.py` put the OG cinematic set at 230 and moved this
line up to 235, scaling every piece by the ladder's 235/230 ratio so the trade below
(more DEF, less RES, slower boots) is kept -- the user's call ("we'll see how it
goes"). Astraea sells it beside Sulfa. The frozen numbers below are the import's.

Sixteen items -- four class lines x four slots -- written into blank rows
**262-265** of all four armour tables, alongside Unit Core rather than above it:

    210  Oro suits
    220  Crystal  |  Steam                      <- two looks, identical stats
    225  Refined Steam
    230  Unit Core  |  **Legionnaire line**     <- two looks, DIFFERENT stats
    240  Royal Guardian / Sun Prophet / Jackal Bandit / Serpent Trader

The source is the 667 dump's own 220 tier -- Legionnaire (Soldier), Spitfire
(Muse), Spinosaur (Hawker), Assailant (Dealer). Its level requirement is not
kept: at 220 it would collide with Crystal/Steam, and it is much better art than
that tier deserves. It is re-gated to 230 as a genuine *alternative* to Unit
Core, not a recolour of it -- the 220 pair is already a cosmetic-only choice and
a second one would be dull.

--- source rows need no colour resolution here

Unlike the Jrose imports, 667 lays all four slots out on one stride: the
Legionnaire set is row 46 in LIST_CAP, LIST_BODY, LIST_ARMS *and* LIST_FOOT, and
the other three lines are 76, 106 and 136 the same way. Nothing interleaves, so
there is no chance of dressing a class in another's gloves. `--verify` still
re-checks each imported model's texture against the class token (`soldier220`,
`muse220`, ...), because the assumption is cheap to test and expensive to get
wrong.

Note the meshes are named `*_200*` while their textures are `*_220*`: retail
reused the 200-tier geometry and reskinned it. That is the source's business, not
a mismatch.

--- the trade, and why it is close to neutral

Unit Core and this line are meant to be a real choice, so the profiles differ:

    DEF          x1.08      more plate, where it is worth the most
    RES          x0.78      magic gets through
    MaxHP (body) x1.12      more to spend on the hits that do land
    move speed   x0.92      the price of the plate
    weight       x1.4       flavour; nothing but the carry cap reads it
    HIT bonus    unchanged  -- see below
    class stat   unchanged  -- that pair IS the class identity

DEF is worth strictly more than RES per point: physical damage carries DEF twice
(`(ATK - DEF + 250) / (DEF + AVOID*0.4 + 5)`) while magic damage carries it once
as `-DEF*0.8` in the numerator *and* divides by RES. So a budget-neutral DEF/RES
swap is not neutral, and the ratios above are not a swap. Weighting them by how
much magic our endgame actually fields -- 15-25% of monsters at level 220-259
have LIST_NPC col 15 set -- expected damage taken comes out at 0.8*0.95 +
0.2*1.17 ~= 0.99 of Unit Core's. Within the noise, paid for by the slower boots.

**HIT is deliberately untouched.** It is the one number on these rows that can
break a character: `Get_SuccessRATE` is a cliff, not a slope, and at level 200 a
by-the-book build sits at HIT 273 against a 285 requirement with its own buff
carrying it over (doc/balance-analysis.md section 2). Trading the set's +245 HIT
for CRITICAL or ATK would have read as flavour and played as a 7%-land-rate
character. Nothing here moves it.

The numbers below were derived from the live Unit Core rows 258-261 when this was
written and then frozen, so `--verify` keeps meaning something. If Unit Core is
ever retuned, re-derive with `--derive` rather than hand-editing.

Idempotent: `--target-row` refuses an occupied row, so a re-run stops rather than
duplicating. `--dry-run` / `--verify` / `--derive`.

After running: `add-dds-mipmaps.py --subdir` over the new art, restart the
servers, re-bake the VFS. Spawn with `/item 2:262` (cap) through `5:265` (foot)
-- GM access 2048. These rows are in no shop and no drop table yet.
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
SOURCE = r"C:\Users\Thomas\Desktop\Testclients\667\extracted data"

CLASSES = ("Soldier", "Muse", "Hawker", "Dealer")
SLOTS = ("cap", "body", "arms", "foot")

# our Unit Core set -- both the template every piece clones (class gates, bonus
# ability pair, sound, hair settings, everything not overridden below) and the
# set these numbers are derived from
TEMPLATE = {"Soldier": 258, "Muse": 259, "Hawker": 260, "Dealer": 261}

# 667 lays every slot out on one row per class; see the docstring
SRC_ROW = {"Soldier": 46, "Muse": 76, "Hawker": 106, "Dealer": 136}

TARGET_ROW = {"Soldier": 262, "Muse": 263, "Hawker": 264, "Dealer": 265}

# the transform, applied to Unit Core and frozen -- run --derive to re-check
FACTOR = {"def": 1.08, "res": 0.78, "hp": 1.12, "speed": 0.92, "weight": 1.4}

NAME = {
    "Soldier": {"cap": "Legionnaire Helmet", "body": "Legionnaire Armor",
                "arms": "Legionnaire Gauntlets", "foot": "Legionnaire Greaves"},
    "Muse":    {"cap": "Spitfire Headpiece", "body": "Spitfire Clothes",
                "arms": "Spitfire Wraps", "foot": "Spitfire Shoes"},
    "Hawker":  {"cap": "Spinosaur Helmet", "body": "Spinosaur Suit",
                "arms": "Spinosaur Gloves", "foot": "Spinosaur Boots"},
    "Dealer":  {"cap": "Assailant Helm", "body": "Assailant Gear",
                "arms": "Assailant Gloves", "foot": "Assailant Boots"},
}

# one line per class, shared by its four pieces, as the other armour imports do
FLAVOUR = {
    "Soldier": "Banded iron on a pattern a thousand years older than any core "
               "suit, and still closing the gap. Heavy, loud, and honest about "
               "both.",
    "Muse":    "Ash-scorched silk that went through a fire and came out stiffer. "
               "It turns a blade better than it turns a spell.",
    "Hawker":  "Ridged hide off something that outgrew its own predators. Cut "
               "close, sewn tight, and not remotely quiet.",
    "Dealer":  "Layered leather and strap steel, for a trade where the other "
               "party may object. Weighs exactly what it protects.",
}

# the class token every imported model's texture must carry
TOKEN = {"Soldier": "soldier220", "Muse": "muse220",
         "Hawker": "hawker220", "Dealer": "dealer220"}

# --- derived from Unit Core rows 258-261 and frozen (see --derive) -----------
# (DEF, RES) per slot per class
STATS = {
    "cap":  {"Soldier": (298, 53), "Muse": (190, 105), "Hawker": (201, 80), "Dealer": (199, 78)},
    "body": {"Soldier": (417, 75), "Muse": (432, 268), "Hawker": (503, 214), "Dealer": (494, 212)},
    "arms": {"Soldier": (267, 48), "Muse": (146, 44), "Hawker": (179, 44), "Dealer": (177, 44)},
    "foot": {"Soldier": (220, 41), "Muse": (225, 27), "Hawker": (231, 20), "Dealer": (229, 20)},
}
# body bonus slot 1 is AT_MAX_HP (id 38); the amount is the only bonus we move
MAXHP = {"Soldier": 1204, "Muse": 1316, "Hawker": 1316, "Dealer": 1316}
# foot col 33, the only mechanical cost of the extra plate
SPEED = {"Soldier": 78, "Muse": 112, "Hawker": 130, "Dealer": 123}
# col 7, flavour only -- nothing but Cal_MaxWEIGHT reads it
WEIGHT = {
    "cap":  {"Soldier": 14, "Muse": 3, "Hawker": 3, "Dealer": 3},
    "body": {"Soldier": 28, "Muse": 28, "Hawker": 28, "Dealer": 28},
    "arms": {"Soldier": 11, "Muse": 3, "Hawker": 4, "Dealer": 3},
    "foot": {"Soldier": 14, "Muse": 4, "Hawker": 4, "Dealer": 4},
}
# unchanged from Unit Core: same tier, same cost
PRICE = {"cap": 350000, "body": 187500, "arms": 350000, "foot": 400291}
AT_MAX_HP = 38
REQ_LEVEL = 230

STB_FILE = {"cap": "LIST_CAP.STB", "body": "LIST_BODY.STB",
            "arms": "LIST_ARMS.STB", "foot": "LIST_FOOT.STB"}
ZSCS = {"cap": ("LIST_MCAP.ZSC", "LIST_WCAP.ZSC"),
        "body": ("LIST_MBODY.ZSC", "LIST_WBODY.ZSC"),
        "arms": ("LIST_MARMS.ZSC", "LIST_WARMS.ZSC"),
        "foot": ("LIST_MFOOT.ZSC", "LIST_WFOOT.ZSC")}
SIDECAR = os.path.join(ROOT, "build", "legionnaire-armour-zsc-fingerprint.json")


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
            d, r = STATS[slot][cls]
            yield dict(cls=cls, slot=slot, name=NAME[cls][slot],
                       src=SRC_ROW[cls], row=TARGET_ROW[cls], tmpl=TEMPLATE[cls],
                       dfn=d, res=r, price=PRICE[slot], token=TOKEN[cls],
                       weight=WEIGHT[slot][cls], desc=FLAVOUR[cls],
                       maxhp=MAXHP[cls] if slot == "body" else None,
                       speed=SPEED[cls] if slot == "foot" else None)


def derive():
    """Re-run the transform against the live Unit Core rows and print the table.

    The numbers above are frozen so --verify keeps meaning something; this is how
    to regenerate them if Unit Core is ever retuned.
    """
    rd = load("rose-data-reader")
    print("Unit Core (live)                 ->  Legionnaire (x%.2f DEF, x%.2f RES)"
          % (FACTOR["def"], FACTOR["res"]))
    for slot in SLOTS:
        s = rd.Stb(os.path.join(DATA, "STB", STB_FILE[slot]), "utf-8")
        out = {}
        for cls in CLASSES:
            t = TEMPLATE[cls]
            d, r = s.i(t, 31), s.i(t, 32)
            nd, nr = round(d * FACTOR["def"]), round(r * FACTOR["res"])
            out[cls] = (nd, nr)
            flag = "" if STATS[slot][cls] == (nd, nr) else \
                "   <-- FROZEN %s DIFFERS" % (STATS[slot][cls],)
            extra = ""
            if slot == "body":
                hp = round(s.i(t, 25) * FACTOR["hp"])
                extra = "  maxhp %4d -> %4d%s" % (
                    s.i(t, 25), hp, "" if MAXHP[cls] == hp else " <-- FROZEN %d" % MAXHP[cls])
            if slot == "foot":
                sp = round(s.i(t, 33) * FACTOR["speed"])
                extra = "  speed %4d -> %4d%s" % (
                    s.i(t, 33), sp, "" if SPEED[cls] == sp else " <-- FROZEN %d" % SPEED[cls])
            w = round(s.i(t, 7) * FACTOR["weight"])
            extra += "  weight %d -> %d%s" % (
                s.i(t, 7), w, "" if WEIGHT[slot][cls] == w else
                " <-- FROZEN %d" % WEIGHT[slot][cls])
            print("  %-5s %-8s DEF %4d RES %4d  ->  DEF %4d RES %4d%s%s"
                  % (slot, cls, d, r, nd, nr, extra, flag))
        tot = sum(out[c][0] for c in CLASSES)
        print("        (slot DEF total %d)" % tot)
    print("\nset totals (4 pieces):")
    for cls in CLASSES:
        od = sum(load_int(slot, TEMPLATE[cls], 31) for slot in SLOTS)
        orr = sum(load_int(slot, TEMPLATE[cls], 32) for slot in SLOTS)
        nd = sum(STATS[slot][cls][0] for slot in SLOTS)
        nr = sum(STATS[slot][cls][1] for slot in SLOTS)
        print("  %-8s Unit Core DEF %4d RES %4d  ->  DEF %4d (%+.1f%%) RES %4d (%+.1f%%)"
              % (cls, od, orr, nd, 100.0 * (nd - od) / od, nr, 100.0 * (nr - orr) / orr))
    return 0


_STB_CACHE = {}


def load_int(slot, row, col):
    if slot not in _STB_CACHE:
        rd = load("rose-data-reader")
        _STB_CACHE[slot] = rd.Stb(os.path.join(DATA, "STB", STB_FILE[slot]), "utf-8")
    return _STB_CACHE[slot].i(row, col)


def fingerprint():
    imp = load("import-item")
    out = {}
    for slot in SLOTS:
        for zn in ZSCS[slot]:
            z = imp.Zsc(os.path.join(DATA, "AVATAR", zn))
            out[zn] = [imp.zsc_serialize_object(o).hex() for o in z.objects]
    return out


def run(it, dry):
    cmd = [sys.executable, os.path.join(HERE, "import-item.py"),
           "--type", it["slot"], "--source", SOURCE,
           "--source-row", str(it["src"]), "--target-row", str(it["row"]),
           "--art-only", "--template-row", str(it["tmpl"]),
           "--name", it["name"], "--desc", it["desc"],
           "--req-level", str(REQ_LEVEL), "--def", str(it["dfn"]),
           "--res", str(it["res"]), "--price", str(it["price"]), "--copy-icon"]
    if it["maxhp"] is not None:
        # slot 1 only; slot 2 keeps the template's class stat, which is the class
        cmd += ["--bonus", "%d:%d" % (AT_MAX_HP, it["maxhp"])]
    if dry:
        cmd.append("--dry-run")
    env = dict(os.environ, PYTHONIOENCODING="utf-8:replace")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def patch_cells(it, dry):
    """Weight (col 7) and boot move speed (col 33) have no import-item flag."""
    imp = load("import-item")
    path = os.path.join(DATA, "STB", STB_FILE[it["slot"]])
    imp.stb_set_cell(path, it["row"], 7, str(it["weight"]), dry)
    if it["speed"] is not None:
        imp.stb_set_cell(path, it["row"], 33, str(it["speed"]), dry)


def verify():
    rd = load("rose-data-reader")
    imp = load("import-item")
    bad = []
    for it in plan():
        s = rd.Stb(os.path.join(DATA, "STB", STB_FILE[it["slot"]]), "utf-8")
        got = rd.scrub(s.s(it["row"], 0)).strip()
        if got != it["name"]:
            bad.append("%s row %d: name is %r" % (it["slot"], it["row"], got))
            continue
        lv = 0
        for c in (19, 21):
            if s.i(it["row"], c) == 31:
                lv = s.i(it["row"], c + 1)
        checks = [("level", lv, REQ_LEVEL),
                  ("DEF", s.i(it["row"], 31), it["dfn"]),
                  ("RES", s.i(it["row"], 32), it["res"]),
                  ("weight", s.i(it["row"], 7), it["weight"])]
        if it["maxhp"] is not None:
            checks += [("bonus 1 id", s.i(it["row"], 24), AT_MAX_HP),
                       ("max HP", s.i(it["row"], 25), it["maxhp"])]
        if it["speed"] is not None:
            checks.append(("move speed", s.i(it["row"], 33), it["speed"]))
        # the class stat pair must have survived the --bonus write untouched
        tmpl_id, tmpl_val = s.i(it["tmpl"], 27), s.i(it["tmpl"], 28)
        checks += [("class stat id", s.i(it["row"], 27), tmpl_id),
                   ("class stat", s.i(it["row"], 28), tmpl_val)]
        for what, gotv, want in checks:
            if gotv != want:
                bad.append("%s: %s %d, want %d" % (it["name"], what, gotv, want))
        # the model must be this class's -- cheap to test, expensive to get wrong
        for zn in ZSCS[it["slot"]]:
            z = imp.Zsc(os.path.join(DATA, "AVATAR", zn))
            o = z.objects[it["row"]] if it["row"] < len(z.objects) else None
            if not o or not o[1]:
                bad.append("%s: %s object %d has no parts" % (it["name"], zn, it["row"]))
                continue
            tex = [z.materials[p[1]][0].decode("latin-1").lower() for p in o[1]]
            if not any(it["token"] in t for t in tex):
                bad.append("%s: %s carries none of %r (%s)"
                           % (it["name"], zn, it["token"],
                              ", ".join(t.rsplit(chr(92), 1)[-1] for t in tex)))
    # icons must be distinct: 16 pieces, 16 sprites, none shared with Unit Core
    icons = {}
    for it in plan():
        s = rd.Stb(os.path.join(DATA, "STB", STB_FILE[it["slot"]]), "utf-8")
        ic = s.i(it["row"], 9)
        key = (it["slot"], ic)
        if ic == s.i(it["tmpl"], 9):
            bad.append("%s: icon %d is Unit Core's" % (it["name"], ic))
        if key in icons:
            bad.append("%s: icon %d already used by %s" % (it["name"], ic, icons[key]))
        icons[key] = it["name"]

    drift = []
    if os.path.exists(SIDECAR):
        with open(SIDECAR, encoding="utf-8") as fh:
            before = json.load(fh)
        now = fingerprint()
        targets = set(TARGET_ROW.values())
        for zn, objs in before.items():
            cur = now.get(zn, [])
            if len(cur) != len(objs):
                drift.append("%s object count %d -> %d" % (zn, len(objs), len(cur)))
                continue
            for i, (a, b) in enumerate(zip(objs, cur)):
                if a != b and i not in targets:
                    drift.append("%s object %d changed and is not a target" % (zn, i))
    n = len(list(plan()))
    print("%d pieces; %d problem(s)%s"
          % (n, len(bad), (":\n  " + "\n  ".join(bad[:10])) if bad else ""))
    if os.path.exists(SIDECAR):
        print("untouched-object check: %d drift(s)%s"
              % (len(drift), (":\n  " + "\n  ".join(drift[:6])) if drift else
                 " -- every object outside the 4 target rows is byte-identical"))
    elif os.path.exists(SIDECAR + ".verified"):
        print("drift check: already passed at import time; the baseline is retired, "
              "since later imports into other rows would fail it for no reason")
    return 1 if bad or drift else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--derive", action="store_true",
                    help="re-run the transform against the live Unit Core rows")
    args = ap.parse_args()
    if args.derive:
        return derive()
    if args.verify:
        return verify()

    if not args.dry_run:
        os.makedirs(os.path.dirname(SIDECAR), exist_ok=True)
        if not os.path.exists(SIDECAR):
            with open(SIDECAR, "w", encoding="utf-8") as fh:
                json.dump(fingerprint(), fh)
            print("recorded a pre-write fingerprint of every ZSC object")

    done, failed = 0, []
    for it in plan():
        rc, out = run(it, args.dry_run)
        if rc == 0:
            patch_cells(it, args.dry_run)
            done += 1
            print("  %-13s %-5s row %3d  %-22s DEF %3d RES %3d"
                  % ("would import" if args.dry_run else "imported",
                     it["slot"], it["row"], it["name"], it["dfn"], it["res"]))
        else:
            failed.append(it["name"])
            print("  %-13s %-5s row %3d  %s\n     %s"
                  % ("FAILED", it["slot"], it["row"], it["name"], out.strip()[-500:]))
    print("\n%d %s, %d failed" % (done, "planned" if args.dry_run else "imported",
                                  len(failed)))
    if failed:
        return 1
    if args.dry_run:
        return 0
    rc = verify()
    # The fingerprint proves THIS write left its neighbours alone, which is only
    # meaningful at write time: keep it and the next legitimate import into other
    # rows reports every one of them as drift. Retire on success, keep on failure.
    if rc == 0 and os.path.exists(SIDECAR):
        os.replace(SIDECAR, SIDECAR + ".verified")
        print("drift baseline retired to %s" % os.path.basename(SIDECAR + ".verified"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
