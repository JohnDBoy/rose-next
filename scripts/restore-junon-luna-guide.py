"""Put [Station Guide] Alphonso back in Junon Polis: the Junon -> Luna route.

Nothing in Junon could take a player to Luna. Eldeon could ([Station Guide] Chacha,
EJT01, EM61-009) and Luna could take them home ([Station Guide] Illiya, Eucar,
EM51-018), but the Junon end of the triangle was missing. It was not lost data, only
the placement:

    LIST_NPC 1118 "[Guide] Alphonso"        type 999, model, CHR entry: all present
    LIST_EVENT 218 -> EM02-038.con          present
    EM02-038.CON                            present and intact (retail Lua)
    TUTORIAL.QSD "travelmoney01"/"gotoLunar"/"gotoEldeon"   present
    JPT01 MOB lump                          **no record for 1118**

Jrose and tsuki both still place him in chunk 34_33 on the harbour front, by the
info kiosk (LIST_CNST_JPT 15) and the docked ships. The record below is Jrose's,
verbatim; tsuki's is ~0.7 m away and names the dialog by LIST_EVENT row ("218")
rather than by file, which our gameserver does not match.

His dialog, traced under lua4:

    "Yes, let's go to Luna."    -> TA_132on        (level >= 41) price + AT_gotoLunar
                                   TA_132off       (level 21-40) "explore Junon first"
                                   TA_levelUnder40 (level < 21)  "come back at 41"
    "I'll go to Eldeon"         -> TA_level90over  (level >= 90) price + AT_gotoEldeon
                                   TA_level90under (level < 90)  "come back at 90"

The level gates are **client-side only**: the server triggers check and take the
Zuly and warp, nothing else (gotoLunar: 5,000 -> zone 51 Eucar; gotoEldeon:
20,000 -> zone 61). So lifting them is a dialog change, done the house way: a QEX1
appendix block that redefines the TA_ functions (the appendix runs after the
retail bytecode in the same lua_State, so the later definition wins). No node is
edited and the retail Lua is untouched. Exactly one branch of each menu passes, so
no speech node closes another's window (see unlock-karkia-idle-dialog.py).

No level gate, at the user's request (2026-10-13), and for the reason Oro, Karkia
and Skaaj have none: the gate is the monsters. Both of Alphonso's options lose it.
The prices stay retail (5,000 to Luna, 20,000 to Eldeon), which the dialog text
already quotes.

[Station Guide] Illiya (1188, Eucar, EM51-018) gets the same block for her
Luna -> Eldeon option (level 90, the same two TA_ names; user's request the same
day), so no station guide gates a trip by level. Her price stays 13,000 as her text
quotes: her option fires "gotoEldeon-0", whose condition and reward are 13,000.

The way back already works with no level gate: [Akram Ambassador] Eliot (1172,
Eucar, EM51-002) sets the "Lunar language" switch for free, without which Illiya
speaks gibberish; after it she offers Junon for 5,000. Alphonso's own greeting
warns the player to save their respawn point on arrival.

The gameserver reads the IFO (restart it); the client reads it and the .CONs from
the VFS (bake).

Idempotent. `--dry-run` / `--verify` / `--restore`. Backups go to build/, never
next to the data (a .bak under data/ gets baked into the .vfs).
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt import condialog, ifo  # noqa: E402

DATA = os.path.join(ROOT, "data")
IFO = os.path.join(DATA, "3DDATA", "MAPS", "JUNON", "JPT01", "34_33.IFO")
EVENT = os.path.join(DATA, "3DDATA", "EVENT")
BACKUP = os.path.join(ROOT, "build", "junon-luna-guide")

NPC_ID = 1118
# Jrose's 3Ddata/MAPS/JUNON/JPT01/34_33.IFO, copied field for field.
ALPHONSO = ifo.Mob(
    name=b"", warp_id=0, event_id=0, obj_type=3, obj_id=NPC_ID, map_x=32, map_y=22,
    rot=(0.0, 0.0, -0.9996573328971863, -0.026175804436206818),
    pos=(32056.0, -13634.0, 0.0), scale=(1.0, 1.0, 1.0),
    ai=0, con_file=b"EM02-038.con")

KEY = "NoLevelGate"
BEGIN = ("-- QE:BEGIN %s\n" % KEY).encode()
END = ("-- QE:END %s\n" % KEY).encode()
# The marker format is the quest editor's (convo.rs appendix_upsert_named), so a
# later con-append / con-warp on these NPCs keeps this block.
HEADER = b"-- restore-junon-luna-guide.py: no level gate on this guide's trips.\n"
LUNA = (b"function TA_132on() return 1 end\n"
        b"function TA_132off() return 0 end\n"
        b"function TA_levelUnder40() return 0 end\n")
ELDEON = (b"function TA_level90over() return 1 end\n"
          b"function TA_level90under() return 0 end\n")

# (.CON, who, appendix body). The retail Lua must define every function the body
# redefines, or the override means nothing -- plan() checks.
DIALOGS = [
    ("EM02-038.CON", "[Guide] Alphonso, Junon Polis", HEADER + LUNA + ELDEON),
    ("EM51-018.CON", "[Station Guide] Illiya, Eucar", HEADER + ELDEON),
]


def redefined(body):
    return [ln.split(b"(")[0][len(b"function "):]
            for ln in body.splitlines() if ln.startswith(b"function ")]


def upsert(appendix, body, con):
    """The quest editor's upsert: drop any old block, append the new one."""
    s = appendix
    i = s.find(BEGIN)
    if i >= 0:
        j = s.find(END, i)
        if j < 0:
            raise SystemExit("%s: unterminated %s block" % (con, KEY))
        s = s[:i] + s[j + len(END):]
    if s and not s.endswith(b"\n"):
        s += b"\n"
    return s + BEGIN + body + END


def placed(m):
    return [r for r in (m.lump(ifo.MOB) or []) if r.obj_id == NPC_ID]


def plan():
    """(new ifo bytes or None, {con path: new bytes}, report lines)."""
    report = []
    with open(IFO, "rb") as fh:
        ifo_old = fh.read()
    m = ifo.parse(ifo_old)
    if ifo.build(m) != ifo_old:
        raise SystemExit("%s: the IFO codec does not round-trip this file" % IFO)
    mobs = m.lump(ifo.MOB)
    if mobs is None:
        raise SystemExit("%s: no MOB lump" % IFO)
    ifo_new = None
    if placed(m):
        report.append("JPT01 34_33: Alphonso already placed")
    else:
        mobs.append(ALPHONSO)
        ifo_new = ifo.build(m)
        report.append("JPT01 34_33: place Alphonso (1118, EM02-038.con) at "
                      "(32056, -13634), %d -> %d MOB records" % (len(mobs) - 1, len(mobs)))

    cons = {}
    for con, who, body in DIALOGS:
        path = os.path.join(EVENT, con)
        with open(path, "rb") as fh:
            con_old = fh.read()
        head, lua, appendix, tail = condialog.split_ex(con_old)
        if condialog.join(head, lua, appendix, tail) != con_old:
            raise SystemExit("%s: the .CON codec does not round-trip this file" % path)
        missing = [f.decode() for f in redefined(body) if f not in lua]
        if missing:
            raise SystemExit("%s: retail Lua lacks %s -- not the dialog this script "
                             "was written for" % (path, ", ".join(missing)))
        new_appendix = upsert(appendix, body, con)
        if new_appendix == appendix:
            report.append("%s (%s): level gates already lifted" % (con, who))
            continue
        cons[path] = condialog.join(head, lua, new_appendix, tail)
        report.append("%s (%s): lift the level gates (QEX1 block %r, %d -> %d bytes)"
                      % (con, who, KEY, len(con_old), len(cons[path])))
    return ifo_new, cons, report


def verify():
    bad = []
    with open(IFO, "rb") as fh:
        n = len(placed(ifo.parse(fh.read())))
    if n != 1:
        bad.append("Alphonso placed %d times in 34_33" % n)
    for con, _who, body in DIALOGS:
        with open(os.path.join(EVENT, con), "rb") as fh:
            _h, _l, appendix, _t = condialog.split_ex(fh.read())
        if BEGIN + body + END not in appendix:
            bad.append("%s: %s block missing or stale" % (con, KEY))
    print("station guides: " + ("ok" if not bad else "; ".join(bad)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    if args.verify:
        return verify()
    if args.restore:
        n = 0
        for path in [IFO] + [os.path.join(EVENT, c) for c, _w, _b in DIALOGS]:
            bak = os.path.join(BACKUP, os.path.basename(path))
            if os.path.isfile(bak):
                shutil.copyfile(bak, path)
                n += 1
        print("restored %d files from %s" % (n, os.path.relpath(BACKUP, ROOT)))
        return 0

    ifo_new, cons, report = plan()
    print("\n".join(report))
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    if ifo_new is None and not cons:
        print("already applied")
        return 0
    os.makedirs(BACKUP, exist_ok=True)
    for path, new in [(IFO, ifo_new)] + list(cons.items()):
        if new is None:
            continue
        bak = os.path.join(BACKUP, os.path.basename(path))
        if not os.path.exists(bak):
            shutil.copyfile(path, bak)
        with open(path, "wb") as fh:
            fh.write(new)
    print("written; backups in %s" % os.path.relpath(BACKUP, ROOT))
    return verify()


if __name__ == "__main__":
    sys.exit(main())
