"""Long-lived simulation worker for a GUI: JSON requests in on stdin, results out on stdout.

A GUI that runs the simulation on a thread of its own process freezes anyway: the
engine is pure Python and holds the GIL. Run as its own process, the window stays
responsive whatever a run costs. The game tables load once, at start-up.

    python scripts/combatsim/worker.py [--data DIR] [--server-toml FILE]

Protocol, one JSON object per line:
    in:  {"id": 7, "build": {...Build JSON...}, "mob": 1560, "n": 300, "fix": false}
    out: {"ready": true}                       once the tables are loaded
         {"id": 7, "summary": {...}}           Report.summary()
         {"id": 7, "error": "ValueError: ..."}
"""
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from combatsim import Build, GameData, Simulation  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--server-toml")
    a = ap.parse_args()
    out = sys.stdout
    try:
        gd = GameData(a.data, a.server_toml)
        # warm the lazy tables now, so the first request costs a run and nothing more
        for t in ("LIST_SKILL", "LIST_NPC", "LIST_STATUS", "LIST_CLASS"):
            gd.names(t)
        for t in ("LIST_WEAPON", "LIST_SUBWPN", "LIST_CAP", "LIST_BODY", "LIST_ARMS",
                  "LIST_FOOT", "LIST_BACK", "LIST_FACEITEM", "LIST_JEWEL", "LIST_JEMITEM",
                  "LIST_GRADE", "LIST_NATURAL", "LIST_USEITEM", "TYPE_MOTION", "FILE_MOTION"):
            gd.stb(t)
        gd.chr()
    except BaseException as e:   # SystemExit included: report it, never die silently
        out.write(json.dumps({"fatal": f"{type(e).__name__}: {e}"}) + "\n")
        out.flush()
        return 1
    out.write(json.dumps({"ready": True}) + "\n")
    out.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("id")
            sim = Simulation(gd, Build(req["build"]), int(req["mob"]), bool(req.get("fix")))
            rep = sim.run(n=int(req.get("n", 300)), seed=int(req.get("seed", 1)))
            msg = {"id": rid, "summary": rep.summary()}
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            msg = {"id": rid, "error": f"{type(e).__name__}: {e}"}
        out.write(json.dumps(msg) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
