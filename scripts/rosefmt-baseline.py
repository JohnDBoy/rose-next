"""Before/after harness for codec or tooling changes: prove the scripts still say the same.

Captures the output of every read-only script command (``--verify``,
``--selftest``, ``--dry-run``, the reports) and hashes what the shared readers
return for every ZSC, ZMS and DDS under ``data/``. Run it before touching the
codecs, again after, and diff the two:

    python scripts/rosefmt-baseline.py run build/baseline/before
    ... change scripts/rosefmt, scripts/mapgen, a script ...
    python scripts/rosefmt-baseline.py run build/baseline/after
    python scripts/rosefmt-baseline.py diff build/baseline/before build/baseline/after

``diff`` reports every command whose exit code or output changed (a listing
that differs only in line order, from a set, is reported as "order only") and
every file whose reader output changed. This is how the rosefmt consolidation
was proven (doc/data-codecs.md): the round-trip script proves the bytes, this
proves the behaviour of the 65 commands built on them.

A full run takes ~25 minutes, almost all of it ``fix-coplanar-object-overlaps.py
--verify``; ``--quick`` skips it. Read-only: nothing under ``data/`` is written.
Add a new read-only command to ``COMMANDS`` when you add a script.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, "data")
EXES = os.path.join(REPO, "Exes")

COMMANDS = {
    "import-oro-667.selftest": ["import-oro-667.py", "--selftest"],
    "import-oro-667.verify": ["import-oro-667.py", "--verify"],
    "import-karkia.selftest": ["import-karkia.py", "--selftest"],
    "import-karkia.verify": ["import-karkia.py", "--verify"],
    "import-skaaj.selftest": ["import-skaaj.py", "--selftest"],
    "import-skaaj.verify": ["import-skaaj.py", "--verify"],
    "import-shibuya.selftest": ["import-shibuya.py", "--selftest"],
    "import-shibuya.verify": ["import-shibuya.py", "--verify"],
    "import-ulverick.selftest": ["import-ulverick.py", "--selftest"],
    "import-ulverick.verify": ["import-ulverick.py", "--verify"],
    "import-cerberus.selftest": ["import-cerberus.py", "--selftest"],
    "import-cerberus.verify": ["import-cerberus.py", "--verify"],
    "import-hebarn.verify": ["import-hebarn.py", "--verify"],
    "import-oro-fate.selftest": ["import-oro-fate.py", "--selftest"],
    "import-oro-fate.dryrun": ["import-oro-fate.py", "--dry-run"],
    "audit-ai-monster-refs.selftest": ["audit-ai-monster-refs.py", "--selftest"],
    "audit-ai-monster-refs.verify": ["audit-ai-monster-refs.py", "--verify"],
    "audit-ai-skill-refs.selftest": ["audit-ai-skill-refs.py", "--selftest"],
    "audit-ai-skill-refs.verify": ["audit-ai-skill-refs.py", "--verify"],
    "convert-buffs.verify": ["convert-buffs-to-percent.py", "--verify"],
    "rebalance-exp.verify": ["rebalance-exp-rewards.py", "--verify"],
    "rebalance-endgame-def.verify": ["rebalance-endgame-curve.py", "--stat", "def", "--verify"],
    "rebalance-endgame-res.verify": ["rebalance-endgame-curve.py", "--stat", "res", "--verify"],
    "rebalance-karkia.verify": ["rebalance-karkia.py", "--verify"],
    "rebalance-oro-667.verify": ["rebalance-oro-667.py", "--verify"],
    "rebalance-oro-bosses.verify": ["rebalance-oro-bosses.py", "--verify"],
    "rebalance-eldeon-outliers.verify": ["rebalance-eldeon-outliers.py", "--verify"],
    "fix-hair-block0.verify": ["fix-hair-block0.py", "--verify"],
    "fix-skill-action-mode.verify": ["fix-skill-action-mode.py", "--verify"],
    "fix-monster-marks.verify": ["fix-monster-marks.py", "--verify"],
    "fix-npc-hand-models.verify": ["fix-npc-hand-models.py", "--verify"],
    "prune-dead-skill-books.verify": ["prune-dead-skill-books.py", "--verify"],
    "fix-skill-book-names.verify": ["fix-skill-book-names.py", "--verify"],
    "fix-chr-skill-slots.verify": ["fix-chr-skill-slots.py", "--verify"],
    "fix-diamond-gem-effects.verify": ["fix-diamond-gem-effects.py", "--verify"],
    "repackage-subweapons.verify": ["repackage-subweapons.py", "--verify"],
    "fix-zmo-attack-frames.verify": ["fix-zmo-attack-frames.py", "--verify"],
    "fix-mob-weapon-presentation.verify": ["fix-mob-weapon-presentation.py", "--verify"],
    "add-oro-drops.verify": ["add-oro-drops.py", "--verify"],
    "add-karkia-drops.verify": ["add-karkia-drops.py", "--verify"],
    "fix-dreadnaught-model.verify": ["fix-dreadnaught-model.py", "--verify"],
    "fix-basilisk-captain-model.verify": ["fix-basilisk-captain-model.py", "--verify"],
    "translate-karkia-dialog.verify": ["translate-karkia-dialog.py", "--verify"],
    "fix-item-names.verify": ["fix-item-names.py", "--verify"],
    "fix-skill-descriptions.verify": ["fix-skill-descriptions.py", "--verify"],
    "stock-muris-shops.verify": ["stock-muris-shops.py", "--verify"],
    "check-shop-tabs": ["check-shop-tabs.py"],
    "balance-sim": ["balance-sim.py"],
    "verify-vfs": ["verify-vfs.py", EXES],
    "rose-data-reader.npc": ["rose-data-reader.py", os.path.join(DATA, "3DDATA", "STB", "LIST_NPC.STB"), "--rows", "30"],
    "rose-data-reader.stl": ["rose-data-reader.py", os.path.join(DATA, "3DDATA", "STB", "LIST_NPC_S.STL"), "--rows", "30"],
    "mapgen-roundtrip.selftest": ["mapgen-roundtrip.py", "--selftest"],
    "rosefmt-roundtrip.selftest": ["rosefmt-roundtrip.py", "--selftest"],
    "audit-lightmap-index": ["audit-lightmap-index.py"],
    "audit-lightmap-index.zone29": ["audit-lightmap-index.py", "--zone", "29"],
    "fill-zsc-gaps.verify": ["fill-zsc-gaps.py", "--verify"],
    "fix-lightmap-index.verify": ["fix-lightmap-index.py", "--verify"],
    "restore-warp-gates.selftest": ["restore-warp-gates.py", "--selftest"],
    "restore-warp-gates.verify": ["restore-warp-gates.py", "--verify"],
    "fix-coplanar.verify": ["fix-coplanar-object-overlaps.py", "--verify"],
    "relight-zone.settings": ["relight-zone.py", "settings"],
    "audit-zsc-bounds": ["audit-zsc-bounds.py"],
    "mapgen-zone.help": ["mapgen-zone.py", "--help"],
    "make-minimap.help": ["make-minimap.py", "--help"],
    "cerberus-wall.help": ["cerberus-wall.py", "--help"],
}
SLOW = {"fix-coplanar.verify"}


# ------------------------------------------------------------------ run
def run_commands(outdir, quick):
    os.makedirs(outdir, exist_ok=True)
    summary = []
    for name, args in COMMANDS.items():
        if quick and name in SLOW:
            continue
        cmd = [sys.executable, "-X", "utf8", os.path.join(HERE, args[0])] + args[1:]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=1800)
            out = p.stdout + b"\n--- stderr ---\n" + p.stderr
            rc = p.returncode
        except subprocess.TimeoutExpired:
            out, rc = b"TIMEOUT", -1
        with open(os.path.join(outdir, name + ".txt"), "wb") as fh:
            fh.write(out + ("\n--- exit %d ---\n" % rc).encode())
        summary.append("%-40s rc=%3d  %6.1fs" % (name, rc, time.time() - t0))
        print(summary[-1], flush=True)
    with open(os.path.join(outdir, "_summary.txt"), "w") as fh:
        fh.write("\n".join(summary) + "\n")


def _hash(obj):
    import numpy as np

    def norm(o):
        if isinstance(o, np.ndarray):
            return {"__nd__": o.dtype.str, "shape": list(o.shape),
                    "sha": hashlib.sha1(np.ascontiguousarray(o).tobytes()).hexdigest()}
        if isinstance(o, (list, tuple)):
            return [norm(x) for x in o]
        if isinstance(o, dict):
            return {str(k): norm(v) for k, v in o.items()}
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, bytes):
            return o.decode("latin-1")
        return o
    return hashlib.sha1(json.dumps(norm(obj), sort_keys=True).encode()).hexdigest()


def _walk(ext):
    seen = set()
    for dp, _, fs in os.walk(DATA):
        for f in fs:
            if f.lower().endswith(ext):
                p = os.path.join(dp, f)
                k = os.path.normcase(p)
                if k not in seen:
                    seen.add(k)
                    yield p


def snapshot_readers(outdir):
    """Hash what the shared readers return for every ZSC / ZMS / DDS."""
    sys.path.insert(0, HERE)
    from mapgen import catalogue, lighting, objlight  # noqa: E402
    res = {"zsc": {}, "zms": {}, "dds": {}}
    for p in _walk(".zsc"):
        rel = os.path.relpath(p, DATA)
        try:
            res["zsc"][rel] = _hash(catalogue.read_zsc(p))
        except Exception as e:  # noqa: BLE001 - an error is a finding
            res["zsc"][rel] = "ERR %s: %s" % (type(e).__name__, e)
    for p in _walk(".zms"):
        rel = os.path.relpath(p, DATA)
        try:
            res["zms"][rel] = _hash([objlight.read_zms(DATA, rel), catalogue.mesh_box(DATA, rel),
                                     catalogue.mesh_vertices(DATA, rel), catalogue.mesh_triangles(DATA, rel)])
        except Exception as e:  # noqa: BLE001
            res["zms"][rel] = "ERR %s: %s" % (type(e).__name__, e)
    for p in _walk(".dds"):
        rel = os.path.relpath(p, DATA)
        try:
            with open(p, "rb") as f:
                res["dds"][rel] = list(lighting.dds_info(f.read(148)))
        except Exception as e:  # noqa: BLE001
            res["dds"][rel] = "ERR %s: %s" % (type(e).__name__, e)
    with open(os.path.join(outdir, "_readers.json"), "w") as f:
        json.dump(res, f, sort_keys=True, indent=0)
    print("readers: zsc %d  zms %d  dds %d" % (len(res["zsc"]), len(res["zms"]), len(res["dds"])))


# ----------------------------------------------------------------- diff
def _strip_timing(line):
    """Elapsed-time stamps vary run to run: the summary's trailing seconds and
    the per-zone ``[3s]`` of the coplanar scan."""
    import re
    line = re.sub(r" +[0-9.]+s$", "", line)
    return re.sub(r"\[\d+s\]", "[s]", line)


def _norm_lines(blob):
    return [_strip_timing(l) for l in blob.decode("utf-8", "replace").splitlines()]


def diff(before, after):
    problems = 0
    sa = [_strip_timing(l) for l in open(os.path.join(before, "_summary.txt")).read().splitlines()]
    sb = [_strip_timing(l) for l in open(os.path.join(after, "_summary.txt")).read().splitlines()]
    if sa != sb:
        problems += 1
        print("EXIT CODES differ:")
        for a, b in zip(sa, sb):
            if a != b:
                print("  before: %s\n  after:  %s" % (a, b))
    else:
        print("exit codes: identical (%d commands)" % len(sa))
    same = order = 0
    for f in sorted(os.listdir(before)):
        if not f.endswith(".txt") or f.startswith("_"):
            continue
        pa, pb = os.path.join(before, f), os.path.join(after, f)
        if not os.path.exists(pb):
            print("MISSING after: %s" % f)
            problems += 1
            continue
        la, lb = _norm_lines(open(pa, "rb").read()), _norm_lines(open(pb, "rb").read())
        if la == lb:
            same += 1
        elif sorted(la) == sorted(lb):
            order += 1
            print("order only: %s" % f)
        else:
            problems += 1
            print("DIFFERS: %s" % f)
            shown = 0
            for i in range(max(len(la), len(lb))):
                x = la[i] if i < len(la) else "<none>"
                y = lb[i] if i < len(lb) else "<none>"
                if x != y:
                    print("  line %d\n    before: %s\n    after:  %s" % (i + 1, x[:160], y[:160]))
                    shown += 1
                    if shown >= 5:
                        break
    print("outputs: %d identical, %d order-only, %d differ" % (same, order, problems))
    ra, rb = os.path.join(before, "_readers.json"), os.path.join(after, "_readers.json")
    if os.path.exists(ra) and os.path.exists(rb):
        a, b = json.load(open(ra)), json.load(open(rb))
        for k in a:
            d = [f for f in a[k] if a[k][f] != b.get(k, {}).get(f)]
            print("readers %s: %d files, %d differ%s" % (k, len(a[k]), len(d), (" " + str(d[:3])) if d else ""))
            problems += len(d)
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="capture every command's output and the reader hashes")
    r.add_argument("outdir")
    r.add_argument("--quick", action="store_true", help="skip the 25-minute coplanar scan")
    r.add_argument("--no-readers", action="store_true", help="skip the reader snapshot")
    d = sub.add_parser("diff", help="compare two captures")
    d.add_argument("before")
    d.add_argument("after")
    a = ap.parse_args()
    if a.cmd == "run":
        run_commands(a.outdir, a.quick)
        if not a.no_readers:
            snapshot_readers(a.outdir)
        return 0
    return diff(a.before, a.after)


if __name__ == "__main__":
    sys.exit(main())
