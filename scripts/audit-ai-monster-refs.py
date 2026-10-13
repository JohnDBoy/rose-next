"""Strip AI actions that name a monster missing from LIST_NPC.STB.

Six AI action types carry a monster id as a WORD at offset 8 of the action
record: 09 Change_CHAR, 10 Create_PET, 18 CallToAttack, 20 Summon,
36 SummonMaster, 37 SummonMasterDist. Nothing between the .aip and the server
validates that id -- `F_AIACT09` reads the WORD and hands it straight to
`CObjMOB::Change_CHAR`, which (before 2026-09-12) broadcast it unchecked.

Why this is not cosmetic
------------------------
A dangling Change_CHAR crashed the client. The chain, from the 2026-09-12
Karkia session:

  * `kak_ghost_cemetery.aip` (NPC 2731 "Ghost Seed", summoned by the whole
    Burned Forest roster -- kak_deadent, kak_fairy01/02, kak_gargo01,
    kak_wolverine) does Change_CHAR -> 2734..2738. All five are **blank rows**
    in our LIST_NPC: the Jrose import brought in 45 monsters and these were not
    among them.
  * Client `CObjMOB::Change_CHAR` calls `DeleteCHAR()` and *then* `Create()`.
    `CreateCHAR` bails at its part-count check, so the object stayed alive with
    no engine model node -- invisible, unclickable, and logging
    "interface: getVisibility() failed" every frame for the rest of the session.
  * `CCharMODEL::DeleteBoneEFFECT` took its argument by value, so the failed
    change left `m_ppBoneEFFECT` dangling. At zone teardown `~CObjCHAR` ->
    `DeleteCHAR` walked freed memory and freed the array a second time. The
    heap corruption fail-fasts past `SetUnhandledExceptionFilter`, which is why
    the installed crash handler produced no dump -- only a truncated log.

The code side of that is fixed (client and server both validate now, and a
failed change restores the previous character or removes the object). This
script removes the cause rather than relying on the guards: an action that can
only ever be refused is dead weight, and leaving it in place means the next
person to read the AI sees a transformation that never happens.

What it does
------------
Removes the offending action record from its event and decrements that event's
action count. Everything else in the file -- patterns, conditions, the other
actions, the trailing bytes -- is copied through byte-for-byte. An event left
with zero actions is kept as-is: `CAI_EVENT::Load` guards its allocation with
`if (m_iActionCNT > 0)` and the execution loops are count-driven, so an empty
event evaluates its conditions and does nothing.

Backups go to `build/ai-monster-refs/` and **not** next to the .aip: `pack.rs`
walks the data tree filtering only hidden entries, and `scripts/pack.ps1` now
hard-errors on any `.bak` under data/ for exactly that reason.

`data/` is gitignored, so this file is the only committed record of the change.
"""

import argparse, base64, json, os, shutil, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosefmt.aip import parse_aip, build_aip  # noqa: E402,F401

G = 0x0B000000
# action type -> label. Every one of these carries `WORD cMonster` at offset 8.
MONSTER_ACTS = {
    0x0A | G: "Change_CHAR(09)",
    0x0B | G: "Create_PET(10)",
    0x13 | G: "CallToAttack(18)",
    0x15 | G: "Summon(20)",
    0x25 | G: "SummonMaster(36)",
    0x26 | G: "SummonMasterDist(37)",
}

AI_DIR = os.path.join("data", "3DDATA", "AI")
NPC_STB = os.path.join("data", "3DDATA", "STB", "LIST_NPC.STB")
BACKUP_DIR = os.path.join("build", "ai-monster-refs")
MANIFEST = "manifest.json"


# --------------------------------------------------------------------------- #
# LIST_NPC


def load_npc_rows(root):
    """(name, monfile) per row, using the reader that copes with any dump."""
    import importlib.util

    p = os.path.join(root, "scripts", "rose-data-reader.py")
    spec = importlib.util.spec_from_file_location("rdr", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    stb = m.Stb(os.path.join(root, NPC_STB))
    rows = []
    for r in range(stb.rows):
        rows.append((stb.d[r][0].decode("latin-1"), stb.d[r][1].decode("latin-1")))
    return rows


def npc_problem(rows, idx):
    """None if the id is usable, else why it is not.

    A blank row is the fatal case -- it is what the server's own
    `!NPC_NAME(i)` guard rejects, since STBDATA::get_cstr returns nullptr for an
    empty cell. A row with a name but no .mon is reported separately: the client
    cannot build a model for it either, but it may be a deliberate invisible
    entity, so it is left alone unless --include-modelless is given.

    A row with a .mon but no name is refused the same way -- the guard reads the
    name cell only. This check used to require both blank, so it passed rows
    like the Woopie Hooligans (306-308) that every summon of theirs was refused
    on (2026-10-13; audit-spawned-npcs.py had the same gap).
    """
    if idx < 1 or idx >= len(rows):
        return "out of range"
    name, mon = rows[idx]
    if not name.strip() and not mon.strip():
        return "BLANK ROW"
    if not name.strip():
        return "NO NAME (mon=%r)" % mon
    if not mon:
        return "no .mon model (name=%r)" % name
    return None


def is_fatal(why):
    return bool(why) and (why in ("out of range", "BLANK ROW") or why.startswith("NO NAME"))


# --------------------------------------------------------------------------- #
# .aip container


def act_monster(a):
    """(type, monster id) if this action names a monster, else None."""
    if len(a) < 10:
        return None
    typ, = struct.unpack_from("<I", a, 4)
    if typ not in MONSTER_ACTS:
        return None
    mid, = struct.unpack_from("<H", a, 8)
    return (typ, mid)


def aip_files(root):
    d = os.path.join(root, AI_DIR)
    seen, out = set(), []
    for dirpath, _dirs, files in os.walk(d):
        for f in files:
            if not f.lower().endswith(".aip"):
                continue
            p = os.path.join(dirpath, f)
            k = os.path.normcase(p)
            if k not in seen:
                seen.add(k)
                out.append(p)
    return sorted(out)


# --------------------------------------------------------------------------- #


def scan(root, rows, include_modelless):
    """[(path, [(pat_i, ev_i, act_i, label, mid, why)])] for files needing edits."""
    todo = []
    for p in aip_files(root):
        b = open(p, "rb").read()
        hdr, title, pats, tail = parse_aip(b)
        hits = []
        for pi, (_pn, evs) in enumerate(pats):
            for ei, (_en, _cs, acts) in enumerate(evs):
                for ai, a in enumerate(acts):
                    mm = act_monster(a)
                    if not mm:
                        continue
                    typ, mid = mm
                    why = npc_problem(rows, mid)
                    if why is None:
                        continue
                    if not is_fatal(why) and not include_modelless:
                        continue
                    hits.append((pi, ei, ai, MONSTER_ACTS[typ], mid, why))
        if hits:
            todo.append((p, hits))
    return todo


def strip(b, hits):
    hdr, title, pats, tail = parse_aip(b)
    drop = {}
    for pi, ei, ai, _lbl, _mid, _why in hits:
        drop.setdefault((pi, ei), set()).add(ai)
    newpats = []
    for pi, (pn, evs) in enumerate(pats):
        newevs = []
        for ei, (en, cs, acts) in enumerate(evs):
            kill = drop.get((pi, ei), set())
            newevs.append((en, cs, [a for ai, a in enumerate(acts) if ai not in kill]))
        newpats.append((pn, newevs))
    return build_aip(hdr, title, newpats, tail)


def selftest(root):
    """Every .aip must re-serialize byte-identically before any are edited."""
    ok = True
    files = aip_files(root)
    for p in files:
        b = open(p, "rb").read()
        try:
            if build_aip(*parse_aip(b)) != b:
                print("    FAIL round-trip %s" % os.path.basename(p))
                ok = False
        except Exception as e:
            print("    FAIL parse %s: %s" % (os.path.basename(p), e))
            ok = False
    print("    %-34s %s   %d files" % ("AIP round-trip", "OK" if ok else "FAIL", len(files)))
    return ok


def do_restore(root):
    bdir = os.path.join(root, BACKUP_DIR)
    mpath = os.path.join(bdir, MANIFEST)
    if not os.path.isfile(mpath):
        print("nothing to restore (%s not found)" % mpath)
        return 0
    man = json.load(open(mpath))
    n = 0
    for rel, rec in sorted(man["files"].items()):
        dst = os.path.join(root, rel)
        open(dst, "wb").write(base64.b64decode(rec["original"]))
        n += 1
    os.remove(mpath)
    print("restored %d file(s) from %s" % (n, bdir))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--dry-run", action="store_true", help="preview without writing")
    ap.add_argument("--verify", action="store_true", help="check that no dangling refs remain")
    ap.add_argument("--restore", action="store_true", help="undo from build/ai-monster-refs/")
    ap.add_argument("--selftest", action="store_true", help="prove the rewriter round-trips")
    ap.add_argument("--include-modelless", action="store_true",
                    help="also strip refs to rows that have a name but no .mon file")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    if a.restore:
        return do_restore(root)

    print("self-test (the rewriter must reproduce every file byte-identically):")
    if not selftest(root):
        print("\nABORT: rewriter is not byte-exact; nothing was touched.")
        return 1
    if a.selftest:
        return 0

    rows = load_npc_rows(root)
    todo = scan(root, rows, a.include_modelless)

    if a.verify:
        if todo:
            print("\nVERIFY FAILED: %d file(s) still carry dangling monster refs" % len(todo))
            for p, hits in todo:
                for _pi, _ei, _ai, lbl, mid, why in hits:
                    print("   %-32s %-20s -> %-5d %s" % (os.path.basename(p), lbl, mid, why))
            return 1
        print("\nALL CHECKS PASSED -- no AI action names a missing monster.")
        return 0

    if not todo:
        print("\nnothing to do -- no AI action names a missing monster.")
        return 0

    nrefs = sum(len(h) for _p, h in todo)
    print("\n%d dangling reference(s) in %d file(s):" % (nrefs, len(todo)))
    for p, hits in todo:
        for _pi, _ei, _ai, lbl, mid, why in hits:
            print("   %-32s %-20s -> %-5d %s" % (os.path.basename(p), lbl, mid, why))

    if a.dry_run:
        print("\ndry run: nothing written")
        return 0

    bdir = os.path.join(root, BACKUP_DIR)
    os.makedirs(bdir, exist_ok=True)
    mpath = os.path.join(bdir, MANIFEST)
    man = json.load(open(mpath)) if os.path.isfile(mpath) else {"files": {}}

    for p, hits in todo:
        b = open(p, "rb").read()
        rel = os.path.relpath(p, root).replace("\\", "/")
        # Keep the *first* original seen, so a second run stays undoable to the
        # true pre-edit bytes rather than to an already-stripped file.
        man["files"].setdefault(rel, {})
        man["files"][rel].setdefault("original", base64.b64encode(b).decode("ascii"))
        man["files"][rel]["stripped"] = [
            {"action": lbl, "npc": mid, "why": why} for _pi, _ei, _ai, lbl, mid, why in hits
        ]
        out = strip(b, hits)
        # Re-parse the result: the record we removed must be gone and nothing else
        # may have moved.
        _h, _t, pats, _tl = parse_aip(out)
        left = sum(1 for _pn, evs in pats for _en, _cs, acts in evs
                   for act in acts
                   if (lambda mm: mm and is_fatal(npc_problem(rows, mm[1])))(act_monster(act)))
        if left:
            print("\nABORT: %s still has %d dangling ref(s) after strip" % (p, left))
            return 1
        open(p, "wb").write(out)

    json.dump(man, open(mpath, "w"), indent=1)
    print("\nstripped %d action(s) from %d file(s)" % (nrefs, len(todo)))
    print("backups + manifest: %s" % bdir)
    print("Next: --verify, then rebake the client VFS and restart the servers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
