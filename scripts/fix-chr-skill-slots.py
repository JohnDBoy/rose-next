"""Apply import-karkia.py's CHR_MOTION_OVERRIDE to LIST_NPC.CHR without a --stage 3.

A monster casts a skill with the AI action's nMotion: the client plays CHR slot
nMotion to cast and slot nMotion+1 to release, and only the release clip's action
frames (24/34 launch the bullet, 26 fires it, 25 presents the hit) make the skill
land on screen. Orgeid (2723, Karkia cemetery) casts on nMotion 8, and Jrose's
CHR -- copied verbatim by the Karkia import -- holds casting_01.ZMO, a clip with
no action frames, in BOTH slot 8 and slot 9, while the real release clip
status_01.ZMO sits unused in slot 7. So the bolt never fired: the damage landed
on a later melee frame with no visual and the status payload timed out (the
2026-09-14 "projectile skill with no launch frame" survey). Revived Veteran
Warrior (2688, unspawned) is the same shape.

The table of corrections lives in `import-karkia.py` (`CHR_MOTION_OVERRIDE`) so
that a future `--stage 3`, which rebuilds the CHR from Jrose, re-applies it; this
script applies the same table to the shipped CHR now. Backups go to
`build/chr-skill-slots/`, never beside the CHR (`pack.ps1` hard-errors on a `.bak`
under data/).

    python scripts/fix-chr-skill-slots.py --dry-run
    python scripts/fix-chr-skill-slots.py
    python scripts/fix-chr-skill-slots.py --verify
    python scripts/fix-chr-skill-slots.py --restore

`data/` is gitignored, so this file and the table are the only committed record.
"""

import argparse
import base64
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
CHR = os.path.join(REPO, "data", "3DDATA", "NPC", "LIST_NPC.CHR")
BACKUP_DIR = os.path.join(REPO, "build", "chr-skill-slots")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    finally:
        sys.argv = saved
    return m


import rosedata as oro  # the shared data layer (was import-oro.py)
kk = load("import_karkia", "import-karkia.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        open(CHR, "wb").write(base64.b64decode(man["original"]))
        os.remove(MANIFEST)
        print("restored LIST_NPC.CHR")
        return 0

    original = open(CHR, "rb").read()
    chr_ = oro.Chr(CHR)
    if chr_.to_bytes() != original:
        print("ABORT: the CHR writer does not round-trip this file byte-for-byte")
        return 1
    changed = kk.chr_override_motions(chr_)

    if a.verify:
        if changed:
            print("VERIFY FAILED: %d slot(s) still differ: %s" % (len(changed), changed))
            return 1
        print("ALL CHECKS PASSED -- every CHR_MOTION_OVERRIDE slot points at its clip.")
        return 0

    if not changed:
        print("nothing to do -- every override already applied.")
        return 0
    for c in changed:
        print("   " + c)
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.isfile(MANIFEST):
        json.dump({"original": base64.b64encode(original).decode("ascii"), "changed": changed},
                  open(MANIFEST, "w"), indent=1)
    open(CHR, "wb").write(chr_.to_bytes())
    print("wrote LIST_NPC.CHR (backup in %s)" % BACKUP_DIR)

    if kk.chr_override_motions(oro.Chr(CHR)):
        print("VERIFY FAILED after write")
        return 1
    print("verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
