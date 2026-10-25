"""Push LIST_CAMERA's terrain fade out for the 5x5 map window, and add camera rows 6-8.

Two things in LIST_CAMERA.STB limit how far the game shows, besides the map-cell
window itself (src/client/terrain/mapwindow.h):

Alpha fog (game columns 7/8)
----------------------------
Terrain fades to *transparent* (into the sky) between these two distances, in
metres: the terrain vertex shaders write oD0.w = (end - depth) / (end - start)
(disassemble data/SHADERS/TERRAIN_FIRST_FOG.VSO with fxc /dumpbin). It is not
the colour fog (columns 9/10, 240 -> 480 m), which tints and stays as shipped.

Shipped, the default "Normal" view faded the ground out by 220 m (160 m in
camera-type-3 zones: Muris, Zant, the Oro gate), well inside the old 3x3
window's 160-320 m reach. With the window at 5x5 the ground reaches at least
320 m in every direction, so:

    Near    unchanged                       (rows 0, 3)
    Normal  200 -> 320 m: seamless anywhere (rows 1, 4)
    Far     260 -> 450 m: past the 320 m guarantee, so a hard edge can show
            in the last stretch when you stand at a cell border looking out
            (rows 2, 5)

With [VIDEO] TERRAIN_RADIUS=1 (3x3) these values show the window's hard edge
far more often; they are tuned for 5x5.

Rows 6-8 (camera type 6)
------------------------
The camera row is the view option (0 Near / 1 Normal / 2 Far) plus LIST_ZONE
column 21 (ZONE_CAMERA_TYPE). Seven Oro zones (14 Colosseum, 73 ODP01, 78/79
ODD04/05, 80 ODOS01, 81 ODRP01, 83 ODGR01, 85 ODFS01) carry type 6, but the
table had six rows. So ApplyCameraOption skipped them (they kept the previous
zone's fog) and CPatchManager::CalculateViewFrustumCulling read
CAMERA_MAX_RANGE as 0, which puts the terrain frustum's far plane *at the
camera*: only the ~120 m proximity keep-alive ring drew terrain there. Rows
6-8 are copies of the outdoor rows 0-2 (with the new fade).

Client-only data; re-bake after running. Backup of the shipped file in
build/camera-fog/ (never beside the STB: pack.rs bakes any .bak it finds).

    python scripts/set-camera-fog.py --dry-run
    python scripts/set-camera-fog.py
    python scripts/set-camera-fog.py --verify
    python scripts/set-camera-fog.py --restore
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import Stb  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
STB = os.path.join(ROOT, "data", "3DDATA", "STB", "LIST_CAMERA.STB")
BACKUP = os.path.join(ROOT, "build", "camera-fog", "LIST_CAMERA.STB")

ALPHA_NEAR_COL, ALPHA_FAR_COL = 7, 8   # CAMERA_NEAR/FAR_ALPHA_FOG, rose/io/stb.h
SHIPPED_ROWS = 6
TARGET_ROWS = 9

# game row -> (alpha fog start, end) in metres
ALPHA_FOG = {1: (200, 320), 4: (200, 320), 2: (260, 450), 5: (260, 450)}
# new game row -> row it copies (after ALPHA_FOG is applied)
COPY_ROWS = {6: 0, 7: 1, 8: 2}


def show(stb, title):
    print(title)
    for r in range(stb.rows):
        print("  row %d  max_range=%-4s alpha_fog=%s..%s  fog=%s..%s" % (
            r, stb.s(r, 4), stb.s(r, ALPHA_NEAR_COL), stb.s(r, ALPHA_FAR_COL),
            stb.s(r, 9), stb.s(r, 10)))


def wanted_problems(stb):
    bad = []
    if stb.rows != TARGET_ROWS:
        bad.append("%d rows, want %d" % (stb.rows, TARGET_ROWS))
        return bad
    for r, (near, far) in ALPHA_FOG.items():
        got = (stb.s(r, ALPHA_NEAR_COL), stb.s(r, ALPHA_FAR_COL))
        if got != (str(near), str(far)):
            bad.append("row %d alpha fog %s..%s, want %d..%d" % (r, got[0], got[1], near, far))
    for r, src in COPY_ROWS.items():
        if [stb.s(r, c) for c in range(stb.cols)] != [stb.s(src, c) for c in range(stb.cols)]:
            bad.append("row %d is not a copy of row %d" % (r, src))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="report and exit")
    ap.add_argument("--restore", action="store_true", help="put the shipped file back")
    args = ap.parse_args()

    if args.restore:
        if not os.path.exists(BACKUP):
            print("no backup at %s" % BACKUP)
            return 1
        shutil.copyfile(BACKUP, STB)
        show(Stb(STB), "restored %s from %s" % (STB, BACKUP))
        return 0

    stb = Stb(STB)
    show(stb, "LIST_CAMERA.STB now:")
    if args.verify:
        bad = wanted_problems(stb)
        print("\n" + ("OK" if not bad else "NOT APPLIED: " + "; ".join(bad)))
        return 0 if not bad else 1

    if not wanted_problems(stb):
        print("\nalready applied -- nothing to do")
        return 0
    if stb.rows != SHIPPED_ROWS:
        print("\nexpected the shipped %d rows, found %d -- refusing (use --restore first)"
              % (SHIPPED_ROWS, stb.rows))
        return 1

    for r, (near, far) in ALPHA_FOG.items():
        stb.set_i(r, ALPHA_NEAR_COL, near)
        stb.set_i(r, ALPHA_FAR_COL, far)
    stb.grow_to(TARGET_ROWS, labels={r: stb.rownames[src + 1] for r, src in COPY_ROWS.items()}
                if stb.rownames else None)
    for r, src in COPY_ROWS.items():
        stb.d[r] = list(stb.d[src])

    show(stb, "\n%s:" % ("would write" if args.dry_run else "writing"))
    if args.dry_run:
        return 0

    if not os.path.exists(BACKUP):
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        shutil.copyfile(STB, BACKUP)
        print("backup: %s" % BACKUP)
    stb.save(dry=False, keep_backup=False)

    bad = wanted_problems(Stb(STB))
    print("\n" + ("verified" if not bad else "VERIFY FAILED: " + "; ".join(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
