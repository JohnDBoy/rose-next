"""Name the LIST_NPC rows the server refused only because column 0 was blank (2026-10-13).

    python scripts/fix-nameless-npc-rows.py --dry-run
    python scripts/fix-nameless-npc-rows.py
    python scripts/fix-nameless-npc-rows.py --verify
    python scripts/fix-nameless-npc-rows.py --restore

The server's NPC_NAME is LIST_NPC column 0 and `get_cstr` returns nullptr for a
blank cell, so every spawn path -- `CZoneTHREAD::RegenCharacter` (zone regen,
AI summons, skill summons), `CObjNPC::Change_CHAR`, `zonefile.cpp` placements
-- treats such a row as nonexistent and refuses it silently, however complete
the rest of the row is. audit-spawned-npcs.py used to call a row blank only
when it had no name *and* no model, so it passed these; the GM item browser
listed them as broken ("no table name"). Of the 223 rows the browser flagged,
these four were the ones live content still reaches:

1. **322, the Junon Ent** (Sunshine Coast, zone 37): all 73 summer-event spawn
   points (`Junon/Sum_Event`) hold 322 + 323 + 324, and 323/324 are blank as in
   every iROSE-lineage dump (667/RoseZA: "Mr. Large Cannie" / "Mr. Large
   Baggie" -- left blank by choice), so every point spawned nothing. 322 is not
   Mr. Cannie: its model is `NPC/etc/ent`, a tree creature, while the real Mr
   Cannie is row 299 (`mrcan`, a can) and already spawns at 245 points there.
   It only borrowed Mr Cannie's STL key LNPC0299 -- retail's mistake (667:
   "(1) Mr. Cannie (Basic)" on ent.mon; ruff/titan "Junon Ant", a misreading of
   the Korean 앤트). It gets **"Junon Ent"** and its own STL entry LNPC0322
   (user, 2026-10-13), like Alpha Turak in fix-spawned-npc-gaps.py.
2. **306/307/308, Woopie Hooligan** (lv 35/75/105, `wolf3`): not the low-level
   Woopie family (101-103, 205) but retail's seasonal event mob. Seven AI
   files spawn them on death, 20-30 %, gated on NPC variable 0 of [Event Info]
   Judy (1201, Zant) == 1, each tier from monsters of its level (Candle Ghosts
   -> 306/307; Yigore Ghost, Vulcan, Yeti, Ruper -> 308); var 0 == 3 is the
   Cherry Smouly event (309-313, named, so it always worked). Nothing in the
   data sets the variable -- a GM starts the event with `/npc 1201 var 0 1` --
   so the event stays dormant; the name only makes it work when started. Every
   dump has the same rows; their STL key LNPC0306 already reads "Woopie
   Hooligan" and is kept.

Stats are left as they are. Writes LIST_NPC.STB cols 0 (and 40 for 322) and
appends one LIST_NPC_S.STL entry (the same text in every language block, as
stl.append does). Undo is cell-level: `build/nameless-npc-rows/undo.json` holds
the old cells and the keys added, and --restore puts back only what still
holds this script's values. Server and client both read LIST_NPC; restart the
servers and re-bake.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rosedata as oro  # noqa: E402

REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, "data")
BUILD = os.path.join(REPO, "build", "nameless-npc-rows")
UNDO = os.path.join(BUILD, "undo.json")

NPC_STB = r"3DDATA\STB\LIST_NPC.STB"
NPC_STL = r"3DDATA\STB\LIST_NPC_S.STL"
NPC_MON_COL = 1
NPC_STRID_COL = oro.NPC_STRID_COL            # 40
# row -> (col-0 name, STL key, the row's mon file: refuse if the row is no longer that monster)
ROWS = {
    322: ("Junon Ent", "LNPC0322", "ent.mon"),
    306: ("Woopie Hooligan", "LNPC0306", "wolf3.mon"),
    307: ("Woopie Hooligan", "LNPC0306", "wolf3.mon"),
    308: ("Woopie Hooligan", "LNPC0306", "wolf3.mon"),
}


def P(rel):
    return oro.rel_path(DATA, rel)


def run(dry):
    npc = oro.Stb(P(NPC_STB))
    stl = oro.Stl(P(NPC_STL))
    undo = json.load(open(UNDO)) if os.path.exists(UNDO) else {}
    for row, (_name, _key, mon) in ROWS.items():
        if npc.s(row, NPC_MON_COL).strip().lower() != mon:
            raise SystemExit("LIST_NPC %d is %r, not %s: refusing" % (row, npc.s(row, NPC_MON_COL), mon))
    stl_changed = npc_changed = False
    for row, (name, key, _mon) in ROWS.items():
        if not stl.has(key):
            stl.append(key, row, name)
            undo.setdefault("stl_added", [])
            if key not in undo["stl_added"]:
                undo["stl_added"].append(key)
            stl_changed = True
            print("  LIST_NPC_S.STL += %s %r" % (key, name))
        elif stl.name(key, 1) != name:
            raise SystemExit("LIST_NPC_S.STL has %s as %r, not %r: refusing" % (key, stl.name(key, 1), name))
        for col, value in ((0, name), (NPC_STRID_COL, key)):
            if npc.s(row, col) == value:
                continue
            undo.setdefault("cells", {}).setdefault("%d:%d" % (row, col), npc.s(row, col))
            print("  LIST_NPC %d col %d %r -> %r" % (row, col, npc.s(row, col), value))
            npc.set(row, col, value)
            npc_changed = True
    if not (stl_changed or npc_changed):
        print("  already done")
        return
    if dry:
        print("  dry run, nothing written")
        return
    os.makedirs(BUILD, exist_ok=True)
    with open(UNDO, "w", encoding="utf-8") as fh:
        json.dump(undo, fh, indent=1)
    if stl_changed:
        stl.save(dry, keep_backup=False)
    if npc_changed:
        npc.save(dry, keep_backup=False)
    print("  done -- restart the servers and re-bake")


def verify():
    npc = oro.Stb(P(NPC_STB))
    stl = oro.Stl(P(NPC_STL))
    ok = True
    for row, (name, key, _mon) in ROWS.items():
        good = npc.s(row, 0) == name and npc.s(row, NPC_STRID_COL) == key and stl.name(key, 1) == name
        ok &= good
        print("  %s LIST_NPC %d: %r key %s -> STL %r"
              % ("ok  " if good else "FAIL", row, npc.s(row, 0), npc.s(row, NPC_STRID_COL), stl.name(key, 1)))
    print("verify:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def restore():
    if not os.path.exists(UNDO):
        raise SystemExit("nothing to restore (no %s)" % UNDO)
    undo = json.load(open(UNDO))
    npc = oro.Stb(P(NPC_STB))
    stl = oro.Stl(P(NPC_STL))
    npc_changed = False
    for cell, old in undo.get("cells", {}).items():
        row, col = map(int, cell.split(":"))
        name, key, _mon = ROWS[row]
        ours = name if col == 0 else key
        if npc.s(row, col) != ours:
            print("  LIST_NPC %d col %d changed since (%r): left alone" % (row, col, npc.s(row, col)))
            continue
        npc.set(row, col, old)
        npc_changed = True
        print("  LIST_NPC %d col %d -> %r" % (row, col, old))
    names = {key: name for name, key, _mon in ROWS.values()}
    gone = []
    for key in undo.get("stl_added", []):
        if stl.has(key) and stl.name(key, 1) == names[key]:
            gone.append(key)
        elif stl.has(key):
            print("  LIST_NPC_S.STL %s renamed since (%r): left alone" % (key, stl.name(key, 1)))
    if gone:
        stl.remove(gone)
        stl.save(False, keep_backup=False)
        print("  LIST_NPC_S.STL -= %s" % ", ".join(gone))
    if npc_changed:
        npc.save(False, keep_backup=False)
    os.remove(UNDO)
    print("  restored")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.verify:
        return verify()
    if a.restore:
        restore()
        return 0
    run(a.dry_run)
    return verify() if not a.dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
