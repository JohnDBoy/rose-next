"""Remove the RoseZA-era Oro import so the 667 build's Oro can replace it.

WHAT IS REMOVED (and only this):

    maps       data/3DDATA/MAPS/ORO/<12 folders>/*   except *.MOV (walkability
               grids: 667 ships none, ours stay in place for the shared folders)
    zones      LIST_ZONE.STB rows 71-82, every cell (row labels and STL keys stay)
    monsters   LIST_NPC.STB rows 2101-2265, every cell; LIST_NPC.CHR entries
               2101-2265 (STL keys stay and are refreshed by the import)
    gates      WARP.STB rows placed by an Oro map (27 of them, all internal)
    quests     31 QSD files, their LIST_QUESTDATA rows, LIST_QUEST rows 4400-4599
               and their LQUE keys; QP401.QSD is rebuilt holding ONLY the two travel
               triggers (Oro-TravelToOrlo / Oro-TravelToJunon) so Jones and Nova
               keep working

WHAT IS DELIBERATELY LEFT ALONE, because the 667 dump cannot replace it and the
re-import reuses it as-is:

    the 43 EM7x/EM8x .CON dialogs, their LIST_EVENT rows and ulngtb_con.ltb text
    (667 ships only encrypted .CXE and no text table); the 38 OR_*/qst_venasper1
    .aip files and FILE_AI rows (667 ships no AI at all); the Arua/Hebarn fate
    skills 2880-2883 and the QP101 triggers (user decision); LIST_SKY row 10,
    ZONETYPEINFO rows 14-17, the ODD/ODT editor STBs; every quest item, icon and
    STL entry; LIST_SELL rows 1-7 (stock-muris-shops.py re-creates them);
    PART_NPC.ZSC objects 709-791 (Karkia's block sits above, so they cannot be
    truncated -- they are dead entries now, harmless); the 3DDATA/ORO art tree
    and the tiles (the import is add-only there).

PRECONDITIONS it refuses to run without: every sidecar that pins an Oro row has
been --restore'd (rebalance-exp-rewards, rebalance-endgame-curve def/res,
rebalance-oro-bosses, rebalance-oro-accuracy, stock-muris-shops --revert,
audit-ai-monster-refs --restore) and the TUTORIAL.LUA oro-quest-scripts block is
gone. Otherwise a later --restore of one of those would write stale Oro values
into rows that by then hold different monsters (reference_whole_file_backup_hazard).

UNDO: everything goes into build/oro-removal/ -- deleted files are MOVED there,
blanked cells and CHR entries are recorded in manifest.json -- and --restore puts
it all back. Never a .bak under data/ (pack.ps1 refuses them).

    python scripts/remove-oro.py --dry-run
    python scripts/remove-oro.py
    python scripts/remove-oro.py --verify
    python scripts/remove-oro.py --restore
"""
import argparse
import base64
import datetime
import importlib.util
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ORO_FOLDERS = ["TOWN", "OROIP", "ODP01", "ODC01", "ODD01", "ODD02", "ODD03",
               "ODD04", "ODD05", "ODOS01", "ODRP01", "ODE01"]
ZONE_ROWS = range(71, 83)
NPC_ROWS = range(2101, 2266)
QUEST_ROWS = range(4400, 4600)
TRAVEL_TRIGGERS = ["Oro-TravelToOrlo", "Oro-TravelToJunon"]
TRAVEL_PATTERN = "OroTravel"
TRAVEL_QSD = "QP401.QSD"
ORO_QSDS = ["QP402.QSD", "QU02-001.QSD"] + [
    f"QN-{n}.QSD" for n in (2177, 2197, 2198, 2199, 2200, 2201, 2202, 2203, 2204,
                            2205, 2206, 2207, 2211, 2215, 2218, 2225)] + [
    f"QN-{n}.QSD" for n in ("DESERTSCAVENGER", "DEVOURER", "DEVOURERBOSS",
                            "DRYSCORPION", "FIERYSNAPPERBOSS", "GOLDENSCORPION",
                            "MASTYX", "MASTYXBOSS", "MASTYXLEADER",
                            "STINGERSCORPION", "TERRASAURUS", "TERRASAURUSBOSS",
                            "TERRASAURUSLEADER")]
assert len(ORO_QSDS) == 31

SIDECARS_MUST_BE_GONE = [
    "3DDATA/STB/LIST_NPC.oro-accuracy.json",
    "3DDATA/STB/LIST_NPC.oro-bosses.json",
    "3DDATA/STB/LIST_NPC.endgame-def.json",
    "3DDATA/STB/LIST_NPC.endgame-res.json",
    "3DDATA/STB/LIST_NPC.exp-rewards.json",
    "3DDATA/STB/LIST_SELL.muris-shops.json",
]
BACKUP_DIR = os.path.join("build", "oro-removal")
FILES_DIR = "files"
MANIFEST = "manifest.json"

STB_ZONE = "3DDATA/STB/LIST_ZONE.STB"
STB_NPC = "3DDATA/STB/LIST_NPC.STB"
STB_WARP = "3DDATA/STB/WARP.STB"
STB_QUESTDATA = "3DDATA/STB/LIST_QUESTDATA.STB"
STB_QUEST = "3DDATA/STB/LIST_QUEST.STB"
STL_QUEST = "3DDATA/STB/LIST_QUEST_S.STL"
CHR_NPC = "3DDATA/NPC/LIST_NPC.CHR"
QSD_DIR = "3DDATA/QUESTDATA"
MAPS_ORO = "3DDATA/MAPS/ORO"


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = saved
    return mod


import rosedata as oro  # the shared data layer (was import-oro.py)
fate = load("import_oro_fate", "import-oro-fate.py")


def write_bytes(path, blob, dry):
    if dry:
        return
    with open(path, "wb") as fh:
        fh.write(blob)


def b2s(b):
    return b.decode("latin-1")


def s2b(s):
    return s.encode("latin-1")


# ---------------------------------------------------------------- preflight
def preflight(data, root, restoring):
    bad = []
    for rel in SIDECARS_MUST_BE_GONE:
        if os.path.exists(os.path.join(data, rel)):
            bad.append(f"sidecar still applied: {rel} -- run its --restore first")
    if os.path.exists(os.path.join(root, "build", "ai-monster-refs", "manifest.json")):
        bad.append("audit-ai-monster-refs.py has stripped files -- run --restore first")
    for base, _d, files in os.walk(data):
        for f in files:
            if f.lower().endswith(".bak"):
                bad.append(f".bak under data/: {os.path.join(base, f)}")
    lua = os.path.join(data, "SCRIPTS", "TUTORIAL.LUA")
    if os.path.exists(lua) and b"oro-quest-scripts" in open(lua, "rb").read():
        bad.append("TUTORIAL.LUA still carries the oro-quest-scripts block")
    mpath = os.path.join(root, BACKUP_DIR, MANIFEST)
    if not restoring and os.path.exists(mpath):
        bad.append(f"{mpath} exists -- removal already ran (use --verify or --restore)")
    if bad:
        for b in bad:
            print("  !", b)
        sys.exit("preflight failed")


# ---------------------------------------------------------------- pieces
def oro_ifos(data):
    d = os.path.join(data, MAPS_ORO)
    out = {}
    for folder in ORO_FOLDERS:
        fd = os.path.join(d, folder)
        if not os.path.isdir(fd):
            continue
        for f in os.listdir(fd):
            if f.lower().endswith(".ifo"):
                out[os.path.normcase(os.path.join(fd, f))] = os.path.join(fd, f)
    return sorted(out.values())


def placed_warp_ids(data):
    ids = set()
    for p in oro_ifos(data):
        buf, bounds = oro.read_ifo(p)
        objs, _ = oro.read_lump(buf, bounds, oro.LUMP_WARP)
        for o in objs or []:
            ids.add(o["warp_id"])
    return ids


def travel_only_qsd(blob):
    """Header + one pattern holding just the two travel triggers, byte-lifted."""
    trigs = []
    for name in TRAVEL_TRIGGERS:
        raw = fate.qsd_trigger_bytes(blob, name)
        if raw is None:
            sys.exit(f"{TRAVEL_QSD}: trigger {name} not found -- cannot rebuild")
        trigs.append(raw)
    o = 8
    n, = struct.unpack_from("<h", blob, o)
    header = blob[:4] + struct.pack("<I", 1) + blob[o:o + 2 + n]
    out = header + struct.pack("<I", len(trigs)) + fate.qsd_pstr(TRAVEL_PATTERN) + b"".join(trigs)
    ok, consumed = fate.qsd_parse_ok(out)
    if not ok:
        sys.exit(f"rebuilt {TRAVEL_QSD} does not re-parse ({consumed}/{len(out)})")
    names = [t for t, _, _ in fate.qsd_walk(out)]
    if names != TRAVEL_TRIGGERS:
        sys.exit(f"rebuilt {TRAVEL_QSD} holds {names}")
    return out


def blank_rows(stb, rows, rel, cells, label, dry):
    hit = 0
    for r in rows:
        if not stb.occupied(r):
            continue
        hit += 1
        cells.setdefault(rel, {})[str(r)] = {str(c): b2s(stb.get(r, c))
                                            for c in range(stb.cols) if stb.get(r, c)}
        for c in range(stb.cols):
            stb.set(r, c, b"")
    print(f"    {label:28s} {hit:5d} rows blanked")
    return hit


# ---------------------------------------------------------------- remove
def remove(root, data, dry):
    preflight(data, root, restoring=False)
    bdir = os.path.join(root, BACKUP_DIR)
    fdir = os.path.join(bdir, FILES_DIR)
    man = {"created": datetime.datetime.now().isoformat(timespec="seconds"),
           "files_moved": [], "cells": {}, "chr": {}, "stl_keys": {}, "qsd": {}}

    # 1. gates -- read the ids out of the maps before the maps go
    warp_ids = placed_warp_ids(data)
    warp = oro.Stb(os.path.join(data, STB_WARP))
    for w in sorted(warp_ids):
        dst = warp.get(w, 1)
        try:
            dz = int(dst)
        except ValueError:
            dz = -1
        if dz not in ZONE_ROWS:
            sys.exit(f"WARP.STB row {w}: placed by an Oro map but goes to zone {dst!r}")
    print(f"  gates: {len(warp_ids)} warp rows placed by Oro maps: {sorted(warp_ids)}")
    blank_rows(warp, sorted(warp_ids), STB_WARP, man["cells"], "WARP.STB", dry)

    # 2. quests
    qdir = os.path.join(data, QSD_DIR)
    on_disk = {f.lower(): f for f in os.listdir(qdir)}
    travel_path = os.path.join(qdir, on_disk[TRAVEL_QSD.lower()])
    blob = open(travel_path, "rb").read()
    fresh = travel_only_qsd(blob)
    man["qsd"][TRAVEL_QSD] = {"original": base64.b64encode(blob).decode(),
                              "rebuilt": base64.b64encode(fresh).decode()}
    print(f"  {TRAVEL_QSD}: {len(blob)} -> {len(fresh)} bytes, travel triggers only")
    write_bytes(travel_path, fresh, dry)
    moved = []
    for name in ORO_QSDS:
        real = on_disk.get(name.lower())
        if not real:
            print(f"    ! already absent: {name}")
            continue
        moved.append(os.path.join(QSD_DIR, real))
    qd = oro.Stb(os.path.join(data, STB_QUESTDATA))
    want = {n.lower() for n in ORO_QSDS}
    qrows = [r for r in range(qd.rows)
             if os.path.basename(qd.get(r, 0).replace(b"\\", b"/")).decode("latin-1").lower() in want]
    blank_rows(qd, qrows, STB_QUESTDATA, man["cells"], "LIST_QUESTDATA.STB", dry)
    if len(qrows) != len(moved):
        print(f"    ! {len(qrows)} LIST_QUESTDATA rows vs {len(moved)} QSD files")
    lq = oro.Stb(os.path.join(data, STB_QUEST))
    blank_rows(lq, QUEST_ROWS, STB_QUEST, man["cells"], "LIST_QUEST.STB 4400-4599", dry)
    stl = oro.Stl(os.path.join(data, STL_QUEST))
    drop = [i for i, (k, _) in enumerate(stl.keys)
            if k.startswith(b"LQUE") and k[4:].isdigit() and int(k[4:]) in QUEST_ROWS]
    rec = []
    for i in sorted(drop, reverse=True):
        k, idx = stl.keys.pop(i)
        langs = [[b2s(f) for f in rows.pop(i)] for rows in stl.langs]
        rec.append({"index": i, "key": b2s(k), "idx": idx, "langs": langs})
    man["stl_keys"][STL_QUEST] = sorted(rec, key=lambda x: x["index"])
    print(f"    {'LIST_QUEST_S.STL':28s} {len(drop):5d} keys removed")

    # 3. zones
    zone = oro.Stb(os.path.join(data, STB_ZONE))
    blank_rows(zone, ZONE_ROWS, STB_ZONE, man["cells"], "LIST_ZONE.STB 71-82", dry)

    # 4. monsters / NPCs
    npc = oro.Stb(os.path.join(data, STB_NPC))
    blank_rows(npc, NPC_ROWS, STB_NPC, man["cells"], "LIST_NPC.STB 2101-2265", dry)
    chr_ = oro.Chr(os.path.join(data, CHR_NPC))
    n = 0
    for r in NPC_ROWS:
        if r < len(chr_.chars) and chr_.chars[r] is not None:
            c = chr_.chars[r]
            man["chr"][str(r)] = dict(skel=c["skel"], name=b2s(c["name"]),
                                      models=c["models"], anims=c["anims"],
                                      effects=c["effects"])
            chr_.chars[r] = None
            n += 1
    print(f"    {'LIST_NPC.CHR 2101-2265':28s} {n:5d} entries cleared")

    # 5. maps (everything but the walkability grids)
    kept, freed, mfiles = 0, 0, []
    for folder in ORO_FOLDERS:
        fd = os.path.join(data, MAPS_ORO, folder)
        if not os.path.isdir(fd):
            continue
        for base, _d, files in os.walk(fd):
            for f in files:
                p = os.path.join(base, f)
                if f.lower().endswith(".mov"):
                    kept += 1
                    continue
                freed += os.path.getsize(p)
                mfiles.append(os.path.relpath(p, data).replace("\\", "/"))
    moved += mfiles
    print(f"  maps: {len(mfiles)} files to move ({freed / 1048576:.1f} MB), {kept} .MOV kept")

    if dry:
        print("\ndry run -- nothing written")
        return
    for rel in moved:
        src = os.path.join(data, rel)
        dst = os.path.join(fdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
    man["files_moved"] = moved
    for s in (warp, qd, lq, zone, npc):
        write_bytes(s.path, s.to_bytes(), dry)
    write_bytes(stl.path, stl.to_bytes(), dry)
    write_bytes(chr_.path, chr_.to_bytes(), dry)
    os.makedirs(bdir, exist_ok=True)
    with open(os.path.join(bdir, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(man, fh)
    print(f"\nwritten. undo record: {os.path.join(bdir, MANIFEST)} ({len(moved)} files moved)")


# ---------------------------------------------------------------- verify
def verify(root, data):
    mpath = os.path.join(root, BACKUP_DIR, MANIFEST)
    if not os.path.exists(mpath):
        sys.exit("no manifest -- removal has not run")
    man = json.load(open(mpath, encoding="utf-8"))
    bad = 0
    for rel in man["files_moved"]:
        if os.path.exists(os.path.join(data, rel)):
            bad += 1
            print(f"  ! still present: {rel}")
    for rel, rows in man["cells"].items():
        stb = oro.Stb(os.path.join(data, rel))
        for r in rows:
            if stb.occupied(int(r)):
                bad += 1
                print(f"  ! {rel} row {r} is occupied")
    chr_ = oro.Chr(os.path.join(data, CHR_NPC))
    for r in man["chr"]:
        if chr_.chars[int(r)] is not None:
            bad += 1
            print(f"  ! CHR entry {r} present")
    stl = oro.Stl(os.path.join(data, STL_QUEST))
    for rec in man["stl_keys"].get(STL_QUEST, []):
        if stl.has(rec["key"]):
            bad += 1
            print(f"  ! STL key {rec['key']} present")
    blob = open(os.path.join(data, QSD_DIR, TRAVEL_QSD), "rb").read()
    names = [t for t, _, _ in fate.qsd_walk(blob)]
    if names != TRAVEL_TRIGGERS:
        bad += 1
        print(f"  ! {TRAVEL_QSD} holds {names}")
    movs = sum(1 for f in oro_ifos_all(data) if f.lower().endswith(".mov"))
    print(f"  {len(man['files_moved'])} files gone, {sum(len(v) for v in man['cells'].values())} "
          f"rows blank, {len(man['chr'])} CHR entries clear, "
          f"{len(man['stl_keys'].get(STL_QUEST, []))} STL keys gone, {movs} .MOV kept, "
          f"{TRAVEL_QSD} = {names}")
    if bad:
        sys.exit(f"{bad} problem(s)")
    print("verify OK")


def oro_ifos_all(data):
    out = []
    for folder in ORO_FOLDERS:
        fd = os.path.join(data, MAPS_ORO, folder)
        if os.path.isdir(fd):
            out += [os.path.join(fd, f) for f in os.listdir(fd)]
    return out


# ---------------------------------------------------------------- restore
def restore(root, data, dry):
    mpath = os.path.join(root, BACKUP_DIR, MANIFEST)
    if not os.path.exists(mpath):
        sys.exit("no manifest -- nothing to restore")
    man = json.load(open(mpath, encoding="utf-8"))
    fdir = os.path.join(root, BACKUP_DIR, FILES_DIR)
    print(f"  {len(man['files_moved'])} files to move back")
    if not dry:
        for rel in man["files_moved"]:
            src = os.path.join(fdir, rel)
            dst = os.path.join(data, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
    for rel, rows in man["cells"].items():
        stb = oro.Stb(os.path.join(data, rel))
        for r, cols in rows.items():
            for c, v in cols.items():
                stb.set(int(r), int(c), s2b(v))
        print(f"  {rel}: {len(rows)} rows restored")
        write_bytes(stb.path, stb.to_bytes(), dry)
    chr_ = oro.Chr(os.path.join(data, CHR_NPC))
    for r, c in man["chr"].items():
        chr_.chars[int(r)] = dict(skel=c["skel"], name=s2b(c["name"]),
                                  models=c["models"],
                                  anims=[tuple(a) for a in c["anims"]],
                                  effects=[tuple(e) for e in c["effects"]])
    print(f"  CHR: {len(man['chr'])} entries restored")
    write_bytes(chr_.path, chr_.to_bytes(), dry)
    stl = oro.Stl(os.path.join(data, STL_QUEST))
    for rec in sorted(man["stl_keys"].get(STL_QUEST, []), key=lambda x: x["index"]):
        stl.keys.insert(rec["index"], (s2b(rec["key"]), rec["idx"]))
        for rows, fields in zip(stl.langs, rec["langs"]):
            rows.insert(rec["index"], [s2b(f) for f in fields])
    print(f"  STL: {len(man['stl_keys'].get(STL_QUEST, []))} keys restored")
    write_bytes(stl.path, stl.to_bytes(), dry)
    for name, rec in man["qsd"].items():
        write_bytes(os.path.join(data, QSD_DIR, name), base64.b64decode(rec["original"]), dry)
        print(f"  {name}: original bytes restored")
    if not dry:
        os.remove(mpath)
        shutil.rmtree(fdir, ignore_errors=True)
    print("restored." if not dry else "dry run -- nothing written")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    data = os.path.join(a.root, "data")
    if a.verify:
        verify(a.root, data)
    elif a.restore:
        restore(a.root, data, a.dry_run)
    else:
        remove(a.root, data, a.dry_run)


if __name__ == "__main__":
    main()
