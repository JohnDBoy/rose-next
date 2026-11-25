"""Monster and NPC AI lines that say placeholder text: re-point or remove them.

An AI "say" action (AIACT02, record type 0x03: an overhead bubble) and a "shout"
(AIACT28, 0x1d: bubble + field/zone/world chat) carry a line number into
`3DDATA/AI/AI_S.STB` (iStrID = row + 1; the game reads the language column
server.toml names, English = 1). Nothing checks the row, and retail shipped a few
that read as nonsense in game (tester report, 2026-11-25: "the Woopie King shouts
something like 'Shout line number ...'"):

- **Woopie King (205), `wolf1_boss.aip`**: its when-hit event (below 50% HP, 20% a
  hit: drop an item, run 6 m away) says row 86, "Shout within the current field."
  -- rows 86-88 are the AI editor's own labels for the shout kinds (field / zone /
  world), not lines. Re-pointed to row 5, "Eeeek~ Run away!", which is what the
  event does.
- **[Boy in the Hut] Huey (1021) and [Little Street Vendor] Pony (1035),
  `npc_nor_a1.aip`**: their idle chatter says rows 53 / 54, the Arumic researcher
  Carasia's recruiting lines ("Oops, I'm running out of supplies for magic
  spells!"), and row 55, a developer note ("10 seconds have passed, run
  QS00-001-2-031"). All three removed; the two NPCs simply stay quiet.
- **Leprechaun (3003), `Ev_Leprechaun.aip`**: five lines name rows 306-310, past
  the end of our 225-row table, which the loader turns into "unknown". Removed.

Until the same day only the client spoke AIACT02 lines (the server's Say_MESSAGE is
an empty virtual), from its own copy of the AI on its own dice; the server now sends
them as local chat like AIACT28's (`F_AIACT02`), so client and server ship together.

`--audit` (the default report) also lists any say/shout in any FILE_AI file whose
row is past the table, blank in English, or one of the known placeholder rows --
run it after importing AI files.

    python scripts/fix-ai-say-lines.py --dry-run
    python scripts/fix-ai-say-lines.py
    python scripts/fix-ai-say-lines.py --verify
    python scripts/fix-ai-say-lines.py --restore

Whole-file originals and the written files' hashes in build/ai-say-lines/;
--restore refuses a file changed since. Re-bake the client data and restart the
servers (both load the AI). `data/` is gitignored, so this file is the record.
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rosefmt import aip, stb  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(REPO, "data")
AI_DIR = os.path.join(DATA, "3DDATA", "AI")
AI_S = os.path.join(AI_DIR, "AI_S.STB")
FILE_AI = os.path.join(DATA, "3DDATA", "STB", "FILE_AI.STB")
BACKUP_DIR = os.path.join(REPO, "build", "ai-say-lines")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

SAY, SHOUT = 0x03, 0x1D
ENGLISH = 1
# Rows that are not lines: the editor's shout-kind labels, a keyboard mash, a dev note.
PLACEHOLDER_ROWS = {55, 86, 87, 88, 92}

# (file, pattern, event, old row, new row or None = remove the action) -- reviewed
FIXES = [
    ("wolf1_boss.aip", 3, 6, 86, 5),
    ("npc_nor_a1.aip", 1, 1, 53, None),
    ("npc_nor_a1.aip", 1, 2, 54, None),
    ("npc_nor_a1.aip", 1, 3, 55, None),
    ("Ev_Leprechaun.aip", 5, 1, 306, None),
    ("Ev_Leprechaun.aip", 5, 2, 307, None),
    ("Ev_Leprechaun.aip", 5, 3, 308, None),
    ("Ev_Leprechaun.aip", 5, 4, 309, None),
    ("Ev_Leprechaun.aip", 5, 5, 310, None),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def line_row(rec):
    """(kind, row) of a say/shout action, else None."""
    t = struct.unpack_from("<i", rec, 4)[0] & 0xFF
    if t == SAY:
        return "say", struct.unpack_from("<i", rec, 8)[0] - 1
    if t == SHOUT:
        return "shout", struct.unpack_from("<i", rec, 12)[0] - 1
    return None


def ai_files():
    t = stb.Stb(FILE_AI)
    seen = []
    for r in range(t.rows):
        f = t.s(r, 0).strip()
        if f and f.lower() not in [s.lower() for s in seen]:
            seen.append(f)
    return [os.path.join(DATA, f.replace("\\", os.sep)) for f in seen]


def audit(lines):
    bad = []
    for path in ai_files():
        (_h, _t, pats, _tail) = aip.parse(open(path, "rb").read())
        for pi, (_pn, evs) in enumerate(pats):
            for ei, (_en, _c, acts) in enumerate(evs):
                for a in acts:
                    lr = line_row(a)
                    if not lr:
                        continue
                    kind, row = lr
                    text = lines.s(row, ENGLISH).strip() if 0 <= row < lines.rows else None
                    if text is None or not text or row in PLACEHOLDER_ROWS:
                        bad.append((os.path.basename(path), pi, ei, kind, row, text))
    return bad


def apply_fixes(blob, fixes):
    """(new blob, [(fix, state)]); state = 'done' / 'applied' / 'missing'."""
    (h, title, pats, tail) = aip.parse(blob)
    pats = [(pn, [(en, list(c), list(a)) for en, c, a in evs]) for pn, evs in pats]
    out = []
    for fix in fixes:
        _f, pi, ei, old, new = fix
        acts = pats[pi][1][ei][2] if pi < len(pats) and ei < len(pats[pi][1]) else []
        hit = [i for i, a in enumerate(acts) if line_row(a) == ("say", old)]
        if not hit:
            done = (new is not None and any(line_row(a) == ("say", new) for a in acts)) or new is None
            out.append((fix, "done" if done else "missing"))
            continue
        i = hit[0]
        if new is None:
            del acts[i]
        else:
            rec = bytearray(acts[i])
            struct.pack_into("<i", rec, 8, new + 1)
            acts[i] = bytes(rec)
        out.append((fix, "applied"))
    return aip.build(h, title, [(pn, [(en, c, a) for en, c, a in evs]) for pn, evs in pats], tail), out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--audit", action="store_true", help="report only")
    a = ap.parse_args()

    if a.restore:
        if not os.path.isfile(MANIFEST):
            print("nothing to restore (%s not found)" % MANIFEST)
            return 0
        man = json.load(open(MANIFEST))
        for f, written in man["files"].items():
            path = os.path.join(AI_DIR, f)
            if sha(open(path, "rb").read()) != written:
                print("REFUSED: %s changed since this script wrote it" % f)
                return 1
        for f in man["files"]:
            shutil.copyfile(os.path.join(BACKUP_DIR, "orig", f), os.path.join(AI_DIR, f))
            print("restored", f)
        os.remove(MANIFEST)
        return 0

    lines = stb.Stb(AI_S)
    by_file = {}
    for fix in FIXES:
        by_file.setdefault(fix[0], []).append(fix)

    pending, writes, problems = 0, {}, []
    for f, fixes in by_file.items():
        path = os.path.join(AI_DIR, f)
        blob = open(path, "rb").read()
        if aip.build(*aip.parse(blob)) != blob:
            problems.append("%s does not round-trip through rosefmt.aip" % f)
            continue
        new, states = apply_fixes(blob, fixes)
        for (_f, pi, ei, old, nw), st in states:
            what = "remove" if nw is None else "-> row %d %r" % (nw, lines.s(nw, ENGLISH))
            print("   %-18s p%d e%d say row %d %s: %s" % (f, pi, ei, old, what, st))
            if st == "missing":
                problems.append("%s p%d e%d: no say of row %d" % (f, pi, ei, old))
            elif st == "applied":
                pending += 1
        if new != blob:
            writes[f] = (blob, new)

    bad = [b for b in audit(lines) if not any(b[0].lower() == fx[0].lower() and b[1:3] == fx[1:3]
                                               and b[4] == fx[3] for fx in FIXES if fx[0] in writes)]
    for f, pi, ei, kind, row, text in bad:
        print("   AUDIT %-18s p%d e%d %s row %d: %r" % (f, pi, ei, kind, row, text))

    if a.audit:
        return 0
    if a.verify:
        if pending or problems or bad:
            print("VERIFY FAILED: %d fix(es) pending, %d problem(s), %d bad line(s)"
                  % (pending, len(problems), len(bad)))
            return 1
        print("ALL CHECKS PASSED -- no AI line names a placeholder or missing row.")
        return 0
    for p in problems:
        print("   " + p)
    if problems:
        print("ABORT, unresolved.")
        return 1
    if not writes:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written (%d file(s) would change)" % len(writes))
        return 0

    os.makedirs(os.path.join(BACKUP_DIR, "orig"), exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else {"files": {}}
    for f, (old, new) in writes.items():
        orig = os.path.join(BACKUP_DIR, "orig", f)
        if not os.path.isfile(orig):
            open(orig, "wb").write(old)
        open(os.path.join(AI_DIR, f), "wb").write(new)
        man["files"][f] = sha(new)
        print("wrote", f)
    json.dump(man, open(MANIFEST, "w"), indent=1)

    left = audit(lines)
    if left:
        print("VERIFY FAILED after write: %d bad line(s) left" % len(left))
        return 1
    print("verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
