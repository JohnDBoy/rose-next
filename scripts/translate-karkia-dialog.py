#!/usr/bin/env python3
"""Put English into Karkia's NPC dialog.

WHERE THE TEXT ACTUALLY IS

Not in the `.CON`. A conversation node carries a `str_id`, and that indexes
`3Ddata\\Event\\ulngtb_con.ltb` -- **row = the string id**, col 0 a key, cols 1..N
the per-language display text, stored **UTF-16LE**
(`GetEventString(id) = GetMbcsString(lang+1, id)`). So translating Karkia means
writing rows into that table, and touching no `.CON` at all.

The quest editor writes the same text into *every* language column, and this does
the same: whatever language the client is set to, it gets the English.

WHY IT NEEDS NO ID REMAP

Karkia's node ids run 21135..33071 and our table has 20876 rows, so **not one of
them collides** -- the only id-space in this whole import that was free by luck
rather than by arrangement. The table is grown to fit and the new rows are ours
alone.

SCOPE

Jrose ships 2,383 translatable strings across the 32 dialogs, 67k Japanese
characters. Most of it is branches for quest chains we deliberately did not
import, and the same lines repeat hard -- "I'll pass" appears 96 times. Filtering
to nodes that are not gated behind a check function and de-duplicating leaves
**654 distinct strings for the 20 reachable NPCs**, which is the real job:

    Church (10 NPCs)          381 distinct
    Spire Village (5)         170
    Foot of the Tower (5)     115
    Memories + Garden (12)    -- skipped; those zones are behind a quest we have
                                 not written, so their text is not reachable

Translations live in `scripts/karkia-dialog-en.json` (`{japanese: english}`), which
is committed -- `data/` is gitignored, so authored text kept only there would be
lost. Anything with no entry is left in Japanese rather than guessed at, and
`--report` lists what is still missing.

Idempotent, verifiable and reversible through a sidecar. Re-running after adding
translations only writes the new ones.

Usage:
    python scripts/translate-karkia-dialog.py --report
    python scripts/translate-karkia-dialog.py --dry-run
    python scripts/translate-karkia-dialog.py
    python scripts/translate-karkia-dialog.py --verify
    python scripts/translate-karkia-dialog.py --restore
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Ltb  # noqa: E402
SRC = r"C:\Users\Thomas\Desktop\Testclients\Jrose"
OUR_LTB = os.path.join(ROOT, "data", "3DDATA", "EVENT", "ulngtb_con.ltb")
SRC_LTB = os.path.join(SRC, "3DDATA", "EVENT", "ulngtb_con.ltb")
SRC_EVENT = os.path.join(SRC, "3DDATA", "EVENT")
# Gates are read from OUR copies, not the Jrose originals: unlock-karkia-idle-
# dialog.py blanks check functions in data/, and a node it exposes has to
# become collectable here or its line stays Japanese.
OUR_EVENT = os.path.join(ROOT, "data", "3DDATA", "EVENT")
TRANSLATIONS = os.path.join(HERE, "karkia-dialog-en.json")
SIDECAR = os.path.join(ROOT, "data", "3DDATA", "EVENT", "ulngtb_con.karkia.json")

# ORDERING TRAP, learned the hard way 2026-09-08.
#
# This script writes each string at its **source str_id**, growing the table to
# max(str_id) + 1. `quest-editor con-warp` / `con-store` instead *append* their
# rows at the current end of the table. So a row appended before a translate run
# that grows past it is silently overwritten -- Magia's warp confirm/accept/
# decline landed on 31212-31214, which are her own source ids for the class-reset
# lines, and came back reading "I want my Champion experience erased."
#
# Rule: **translate first, append second.** Karkia's source ids top out at 33071,
# so any appended row at 33072 or above is safe for good; the table is padded to
# that floor. If a future import raises the ceiling, pad again before appending.
# Backups go OUTSIDE data/: pack.rs walks the data tree filtering only hidden
# entries -- no extension filter -- so a .bak left beside the table gets baked
# into the .vfs.
BACKUP = os.path.join(ROOT, "build", "karkia-dialog-backup", "ulngtb_con.ltb")

JA_COL = 3          # the column Jrose keeps Japanese display text in
NAME_COL = 1        # structural node name ("Root", "MainMenu", "npc1190_1", ...)
STRUCTURAL = {"Root", "BasicMenu", "MainMenu", "Conversation", "Quest", "Union",
              "Arbite", "Slot", "End"}

# The 20 NPCs a player can currently reach, by the .CON each one uses.
CHURCH = ["EM86-001.CON", "EM86-002.CON", "EM86-003.CON", "EM86-004.CON",
          "EM86-005.CON", "EM86-006.CON", "EM86-007.CON", "EM86-008.CON",
          "EM86-009.CON", "EM03-007.CON"]
SPIRE = ["EM86-010.CON", "EM86-011.CON", "EM86-012.CON", "EM86-013.CON",
         "EM02-108.CON"]
TOWER = ["EM02-111.CON", "EM02-112.CON", "EM02-113.CON", "EM02-114.CON",
         "EM02-115.CON"]
UNREACHABLE = ["EM03-001.CON", "EM03-002.CON", "EM03-003.CON", "EM03-004.CON",
               "EM03-005.CON", "EM03-006.CON", "EM03-008.CON", "EM03-009.CON",
               "EM03-010.CON", "EM03-011.CON", "EM04-006.CON", "EM04-007.CON"]
REACHABLE = CHURCH + SPIRE + TOWER


# ------------------------------------------------------------------ .CON reader
def _cstr(b, o, n):
    f = b[o:o + n]
    z = f.find(b"\0")
    return f[:z if z >= 0 else n]


def con_nodes(path):
    """[(str_id, check_func)] for every message and menu item in a .CON.

    Layout from src/tools/quest-editor/src/convo.rs. A menu collection's body is
    XOR'd with (num_sub if odd else length) & 0xff, and its items are reached
    through an offset table inside the collection -- not a fixed stride.
    """
    b = open(path, "rb").read()
    conv_off, _script_off = struct.unpack_from("<II", b, 516)
    msg_num, msg_off, menu_num, menu_off = struct.unpack_from("<iIiI", b, 524)
    out = []
    base = conv_off + msg_off
    for i in range(max(0, msg_num)):
        mmt, = struct.unpack_from("<I", b, base + i * 4)
        o = base + mmt
        out.append((struct.unpack_from("<i", b, o + 76)[0],
                    _cstr(b, o + 12, 32).decode("latin-1")))
    base = conv_off + menu_off
    for i in range(max(0, menu_num)):
        mmt, = struct.unpack_from("<I", b, base + i * 4)
        c = base + mmt
        length, num_sub = struct.unpack_from("<ii", b, c)
        if length < 8 or c + length > len(b):
            continue
        coll = bytearray(b[c:c + length])
        key = (num_sub if num_sub & 1 else length) & 0xFF
        for k in range(8, len(coll)):
            coll[k] ^= key
        for j in range(max(0, num_sub)):
            if 8 + j * 4 + 4 > len(coll):
                break
            o, = struct.unpack_from("<I", coll, 8 + j * 4)
            if o + 80 > len(coll):
                break
            out.append((struct.unpack_from("<i", coll, o + 76)[0],
                        _cstr(coll, o + 12, 32).decode("latin-1")))
    return out


# ------------------------------------------------------------------ .LTB codec: rosefmt.ltb
# ------------------------------------------------------------------ the work
def collect(scope):
    """{str_id: japanese} for the .CONs in `scope`, structural nodes dropped."""
    src = Ltb(SRC_LTB)
    want = {}
    for con in scope:
        p = os.path.join(OUR_EVENT, con)
        if not os.path.isfile(p):
            raise SystemExit(f"missing source dialog {con}")
        for sid, check in con_nodes(p):
            if not sid or check.strip():
                continue          # gated on a quest state we did not import
            ja = src.text(sid, JA_COL)
            if not ja or src.text(sid, NAME_COL) in STRUCTURAL:
                continue
            want[sid] = ja
    return want


def load_translations():
    if not os.path.exists(TRANSLATIONS):
        return {}
    with open(TRANSLATIONS, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="what is translated and what is still missing")
    ap.add_argument("--scope", default="reachable",
                    choices=("church", "spire", "tower", "reachable", "all"))
    args = ap.parse_args()

    scope = {"church": CHURCH, "spire": SPIRE, "tower": TOWER,
             "reachable": REACHABLE, "all": REACHABLE + UNREACHABLE}[args.scope]

    if args.restore:
        if not os.path.exists(SIDECAR):
            sys.exit("no sidecar -- nothing to restore")
        with open(SIDECAR, encoding="utf-8") as fh:
            saved = json.load(fh)
        ltb = Ltb(OUR_LTB)
        del ltb.rows[saved["orig_rows"]:]
        for row, cells in saved["rows"].items():
            ltb.rows[int(row)] = [bytes.fromhex(c) for c in cells]
        with open(OUR_LTB, "wb") as fh:
            fh.write(ltb.to_bytes())
        os.remove(SIDECAR)
        print(f"restored ulngtb_con.ltb to {saved['orig_rows']} rows")
        return 0

    want = collect(scope)
    en = load_translations()
    have = {sid: en[ja] for sid, ja in want.items() if ja in en}
    missing = {sid: ja for sid, ja in want.items() if ja not in en}

    if args.report:
        distinct_missing = sorted({ja for ja in missing.values()})
        print(f"scope {args.scope}: {len(want)} nodes, "
              f"{len({v for v in want.values()})} distinct strings")
        print(f"   translated : {len(have)} nodes")
        print(f"   missing    : {len(missing)} nodes, "
              f"{len(distinct_missing)} distinct, "
              f"{sum(len(s) for s in distinct_missing)} chars")
        for con in scope:
            ids = {s for s, _c in con_nodes(os.path.join(OUR_EVENT, con))}
            m = len([s for s in missing if s in ids])
            t = len([s for s in have if s in ids])
            print(f"      {con:<14} {t:>4} done  {m:>4} missing")
        return 0

    ltb = Ltb(OUR_LTB)
    orig_rows = len(ltb.rows)
    if args.verify:
        if not os.path.exists(SIDECAR):
            sys.exit("no sidecar -- not applied")
        bad = [sid for sid, txt in have.items() if ltb.text(sid, 1) != txt]
        print(f"{len(have)} translated nodes; {len(bad)} do not match"
              + (f": {bad[:8]}" if bad else ""))
        return 1 if bad else 0

    if not have:
        print("nothing translated yet -- add entries to "
              f"{os.path.basename(TRANSLATIONS)} (see --report)")
        return 0

    saved = {"orig_rows": orig_rows, "rows": {}}
    ltb.grow_to(max(have) + 1)
    for sid in sorted(have):
        if sid < orig_rows:
            saved["rows"][str(sid)] = [c.hex() for c in ltb.rows[sid]]
        ltb.set_all_langs(sid, f"KARKIA-{sid}", have[sid])

    print(f"ulngtb_con.ltb {orig_rows} -> {len(ltb.rows)} rows, "
          f"{len(have)} strings written, {len(missing)} still Japanese")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    blob = ltb.to_bytes()
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    if not os.path.exists(BACKUP):
        with open(BACKUP, "wb") as fh:
            fh.write(open(OUR_LTB, "rb").read())
    with open(OUR_LTB, "wb") as fh:
        fh.write(blob)
    if not os.path.exists(SIDECAR):
        with open(SIDECAR, "w", encoding="utf-8") as fh:
            json.dump(saved, fh)

    check = Ltb(OUR_LTB)
    bad = [sid for sid, txt in have.items() if check.text(sid, 1) != txt]
    if bad:
        sys.exit(f"VERIFY FAILED on {len(bad)} rows: {bad[:8]}")
    print(f"verified: all {len(have)} rows read back exactly")
    print("re-bake the VFS; ulngtb_con.ltb ships inside it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
