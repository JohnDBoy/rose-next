"""Bake the server's layered walk grid (<ZONE FOLDER>.lnav) for one or more zones.

    python scripts/nav-bake.py 31 62              bake Goblin Cave B1 and Shady Jungle
    python scripts/nav-bake.py 31 --no-write      numbers and picture only
    python scripts/nav-bake.py 31 --data D:/data  another data folder

Each zone writes:
  * data/<zone folder>/<FOLDER>.lnav, read by the game server (it lives in data/ like the
    rest of the map: the local server reads data/ directly; scripts/pack.ps1 keeps it out
    of rose.vfs);
  * build/nav/<FOLDER>.png, a 1 px = 1 m picture (legend in mapgen.navbake.preview);
  * build/nav/<FOLDER>.txt, the numbers: reached area, layers, hazards, seeds, spawn
    spill, agreement with the hand-painted MOV.

The rules and why: scripts/mapgen/navbake.py and doc/pathfinding-and-z-plan.md (3.1).
The written file is parsed back and must rebuild byte for byte.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mapgen import navbake  # noqa: E402
from rosefmt import lnav  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zones", type=int, nargs="+", help="LIST_ZONE rows")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "nav"), help="pictures and reports")
    ap.add_argument("--no-write", action="store_true", help="do not write the .lnav")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    for row in a.zones:
        t0 = time.time()
        b = navbake.bake(a.data, row)
        blob = lnav.build(b.nav)
        if lnav.build(lnav.parse(blob)) != blob:
            raise SystemExit("lnav round trip failed for zone %d" % row)
        text = navbake.report(b, a.data)
        text += "\nbake time: %.1f s" % (time.time() - t0)
        print(text)
        with open(os.path.join(a.out, b.folder + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        navbake.preview(b, os.path.join(a.out, b.folder + ".png"))
        if not a.no_write:
            path = os.path.join(b.zdir, b.folder + ".lnav")
            with open(path, "wb") as fh:
                fh.write(blob)
            print("wrote %s (%.2f MB)" % (os.path.relpath(path, ROOT), len(blob) / 1e6))
        print()


if __name__ == "__main__":
    main()
