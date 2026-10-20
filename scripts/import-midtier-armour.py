"""Fill the 225 and 230 gap between Crystal/Steam (220) and Egyptian (240).

**Superseded 2026-10-20:** `armour-ladder-pass.py` made Steam Refined a level-90
and Unit Core a level-110 cosmetic set (the user graded both looks vanity, not end
game), so `--verify` here reports their stats and levels as drift. The 225 gap is
simply gone; the ladder steps 200/210/220/230/240.

Thirty-two items -- two tiers x four class lines x four slots -- written into
blank rows **254-257** (225) and **258-261** (230) of all four armour tables.

    210  Oro suits
    220  Crystal  |  Steam          <- two looks, identical stats
    225  Steam Refined              <- this script
    230  Unit Core                  <- this script
    240  Royal Guardian / Sun Prophet / Jackal Bandit / Serpent Trader

--- why these two, in this order

**Steam Refined** (Jrose's 洗練な line) is the same steampunk silhouette as the
Steam set at 220, in deeper colours. Putting a recolour *directly above its own
base* makes it read as an upgrade of a set the player already owns. That is the
opposite of the mistake the alpha monsters make, where the art is byte-identical
and the two versions are a zone apart pretending to be different creatures.

**Unit Core** (Jrose's `Hirosuit` line) is a genuinely new silhouette -- a
five-part armoured suit (`body` + `arm` + `arm2` + `leg` + `shoulder`) unlike
anything we ship -- so the tier immediately below the cap looks like an arrival
rather than another recolour. Its eight colours are named for Roman gods; we take
Sol, Jupiter, Diana and Pluto, whose red/blue/green/yellow keeps the class-colour
convention the Steam sets already established.

Both source lines sit at absurd levels in Jrose (476 and 1254 -- their cap is far
above ours). That is irrelevant under `--art-only`, which reads no source cell:
level, DEF, RES and price all come from here.

--- source rows are resolved by COLOUR, never by arithmetic

The two families interleave their variants differently in each slot table: for
Steam Refined the Knight body is row 5171 while row 5171 in the *cap* table is
the Scout, and its arms and boots live 70 rows away at 5100 and 5111. Picking
"body row + N" would have silently dressed each class in another's gloves. Every
row below was resolved by matching the texture's colour token, and
`--verify` re-checks the imported model's texture against the same token.

--- stats are interpolated, not invented

Each piece is a linear interpolation between the Crystal row it clones (220) and
the matching Egyptian row (240), at 25% for 225 and 50% for 230, so the four
tiers sit on one line. Read off the live tables when this was written; if Crystal
or Egyptian is ever retuned, re-derive rather than editing these by hand.

Idempotent: `--target-row` refuses an occupied row, so a re-run stops rather than
duplicating. `--dry-run` / `--verify`.

After running: restart the servers and re-bake the VFS. Spawn with
`/item 2:254` (cap) through `5:261` (foot) -- GM access 2048.
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

# our Crystal set -- the template every piece clones (class gates, bonus ability,
# sound, everything we do not override)
TEMPLATE = {
    "cap":  {"Soldier": 977, "Muse": 978, "Hawker": 979, "Dealer": 980},
    "body": {"Soldier": 904, "Muse": 905, "Hawker": 906, "Dealer": 907},
    "arms": {"Soldier": 880, "Muse": 881, "Hawker": 882, "Dealer": 883},
    "foot": {"Soldier": 878, "Muse": 879, "Hawker": 880, "Dealer": 881},
}

TIERS = {
    225: {
        "name": "Steam Refined",
        "row": {"Soldier": 254, "Muse": 255, "Hawker": 256, "Dealer": 257},
        # resolved by texture colour, not by row arithmetic -- see the docstring
        "src": {"cap":  {"Soldier": 5166, "Muse": 5168, "Hawker": 5170, "Dealer": 5172},
                "body": {"Soldier": 5171, "Muse": 5173, "Hawker": 5175, "Dealer": 5177},
                "arms": {"Soldier": 5100, "Muse": 5102, "Hawker": 5104, "Dealer": 5106},
                "foot": {"Soldier": 5111, "Muse": 5113, "Hawker": 5115, "Dealer": 5117}},
        "colour": {"Soldier": "deepred", "Muse": "deepblue",
                   "Hawker": "deepgreen", "Dealer": "deepyellow"},
        "piece": {"cap": "Gear", "body": "Cloak", "arms": "Gloves", "foot": "Boots"},
        "stats": {
            "cap":  {"Soldier": (247, 61), "Muse": (158, 121), "Hawker": (167, 92), "Dealer": (165, 90)},
            "body": {"Soldier": (354, 88), "Muse": (367, 314), "Hawker": (428, 252), "Dealer": (419, 250)},
            "arms": {"Soldier": (222, 55), "Muse": (121, 51), "Hawker": (149, 51), "Dealer": (147, 51)},
            "foot": {"Soldier": (183, 46), "Muse": (188, 30), "Hawker": (192, 24), "Dealer": (190, 24)},
        },
        "price": {"cap": 315000, "body": 168750, "arms": 315000, "foot": 360436},
        "flavour": {
            "Soldier": "The same brass, worked again and fired darker. It holds "
                       "pressure now where the old plate vented it.",
            "Muse":    "Deep blue enamel over the copper. The gauge no longer "
                       "flickers, whatever the wearer is feeling.",
            "Hawker":  "Green leather boiled black at the edges, and a spine that "
                       "has stopped ticking audibly.",
            "Dealer":  "Lacquer laid four times over. The pockets have pockets, "
                       "and none of them are where they look.",
        },
    },
    230: {
        "name": "Unit Core",
        "row": {"Soldier": 258, "Muse": 259, "Hawker": 260, "Dealer": 261},
        "src": {"cap":  {"Soldier": 5207, "Muse": 5209, "Hawker": 5212, "Dealer": 5213},
                "body": {"Soldier": 5223, "Muse": 5225, "Hawker": 5228, "Dealer": 5229},
                "arms": {"Soldier": 5141, "Muse": 5143, "Hawker": 5146, "Dealer": 5147},
                "foot": {"Soldier": 5151, "Muse": 5153, "Hawker": 5156, "Dealer": 5157}},
        "colour": {"Soldier": "_red_", "Muse": "_blue_",
                   "Hawker": "_green_", "Dealer": "_yellow_"},
        "piece": {"cap": "Guard", "body": "Core", "arms": "Arm Guards", "foot": "Leg Plates"},
        # the source names each colour for a Roman god; kept, because they are
        # better than anything a colour would give us
        "god": {"Soldier": "Sol", "Muse": "Jupiter", "Hawker": "Diana", "Dealer": "Pluto"},
        "stats": {
            "cap":  {"Soldier": (276, 68), "Muse": (176, 134), "Hawker": (186, 103), "Dealer": (184, 100)},
            "body": {"Soldier": (386, 96), "Muse": (400, 343), "Hawker": (466, 274), "Dealer": (457, 272)},
            "arms": {"Soldier": (247, 62), "Muse": (135, 56), "Hawker": (166, 56), "Dealer": (164, 56)},
            "foot": {"Soldier": (204, 52), "Muse": (208, 34), "Hawker": (214, 26), "Dealer": (212, 26)},
        },
        "price": {"cap": 350000, "body": 187500, "arms": 350000, "foot": 400291},
        "flavour": {
            "Soldier": "A sealed suit built around a burning core. Sol's plate runs "
                       "hot enough to read by.",
            "Muse":    "Jupiter's frame, storm-blue and heavier than it looks. The "
                       "shoulder vents discharge on their own.",
            "Hawker":  "Diana's core, cut for speed. The leg assembly folds when the "
                       "wearer does.",
            "Dealer":  "Pluto's suit, gold and unhurried. Built by someone who could "
                       "afford not to compromise.",
        },
    },
}
STB_FILE = {"cap": "LIST_CAP.STB", "body": "LIST_BODY.STB",
            "arms": "LIST_ARMS.STB", "foot": "LIST_FOOT.STB"}
ZSCS = {"cap": ("LIST_MCAP.ZSC", "LIST_WCAP.ZSC"),
        "body": ("LIST_MBODY.ZSC", "LIST_WBODY.ZSC"),
        "arms": ("LIST_MARMS.ZSC", "LIST_WARMS.ZSC"),
        "foot": ("LIST_MFOOT.ZSC", "LIST_WFOOT.ZSC")}
SIDECAR = os.path.join(ROOT, "build", "midtier-armour-zsc-fingerprint.json")


def label(tier, cls, slot):
    t = TIERS[tier]
    piece = t["piece"][slot]
    if tier == 230:
        return "%s %s" % (t["god"][cls], piece)
    return "Refined Steam %s %s" % (cls, piece)


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
    for tier in sorted(TIERS):
        t = TIERS[tier]
        for cls in CLASSES:
            for slot in SLOTS:
                d, r = t["stats"][slot][cls]
                yield dict(tier=tier, cls=cls, slot=slot,
                           name=label(tier, cls, slot),
                           src=t["src"][slot][cls], row=t["row"][cls],
                           tmpl=TEMPLATE[slot][cls], dfn=d, res=r,
                           price=t["price"][slot], colour=t["colour"][cls],
                           desc=t["flavour"][cls])


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
           "--req-level", str(it["tier"]), "--def", str(it["dfn"]),
           "--res", str(it["res"]), "--price", str(it["price"]), "--copy-icon"]
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
        if lv != it["tier"]:
            bad.append("%s: level %d, want %d" % (it["name"], lv, it["tier"]))
        if s.i(it["row"], 31) != it["dfn"]:
            bad.append("%s: DEF %d, want %d" % (it["name"], s.i(it["row"], 31), it["dfn"]))
        if s.i(it["row"], 32) != it["res"]:
            bad.append("%s: RES %d, want %d" % (it["name"], s.i(it["row"], 32), it["res"]))
        # the model must carry this class's colour -- the mismatch this whole
        # colour-resolution exists to prevent
        for zn in ZSCS[it["slot"]]:
            z = imp.Zsc(os.path.join(DATA, "AVATAR", zn))
            o = z.objects[it["row"]] if it["row"] < len(z.objects) else None
            if not o or not o[1]:
                bad.append("%s: %s object %d has no parts" % (it["name"], zn, it["row"]))
                continue
            t = z.materials[o[1][0][1]][0].decode("latin-1").lower()
            if it["colour"].strip("_") not in t:
                bad.append("%s: %s texture %s does not carry %r"
                           % (it["name"], zn, t.rsplit(chr(92), 1)[-1], it["colour"]))
    drift = []
    if os.path.exists(SIDECAR):
        with open(SIDECAR, encoding="utf-8") as fh:
            before = json.load(fh)
        now = fingerprint()
        targets = {it["row"] for it in plan()}
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
          % (n, len(bad), (":\n  " + "\n  ".join(bad[:8])) if bad else ""))
    if os.path.exists(SIDECAR):
        print("untouched-object check: %d drift(s)%s"
              % (len(drift), (":\n  " + "\n  ".join(drift[:6])) if drift else
                 " -- every object outside the 8 target rows is byte-identical"))
    elif os.path.exists(SIDECAR + ".verified"):
        print("drift check: already passed at import time (%s); the baseline is "
              "retired, since later imports into other rows would fail it for no "
              "reason" % os.path.basename(SIDECAR + ".verified"))
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
    for it in plan():
        rc, out = run(it, args.dry_run)
        if rc == 0:
            done += 1
            print("  %-13s lv%d %-5s row %3d  %s"
                  % ("would import" if args.dry_run else "imported",
                     it["tier"], it["slot"], it["row"], it["name"]))
        else:
            failed.append(it["name"])
            print("  %-13s lv%d %-5s row %3d  %s\n     %s"
                  % ("FAILED", it["tier"], it["slot"], it["row"], it["name"],
                     out.strip()[-400:]))
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
