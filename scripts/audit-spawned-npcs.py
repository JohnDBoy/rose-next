"""Audit every monster and NPC the game can put in the world, end to end. Read-only.

    python scripts/audit-spawned-npcs.py              # every zone in LIST_ZONE
    python scripts/audit-spawned-npcs.py --zone 131   # one zone
    python scripts/audit-spawned-npcs.py --json build/audit-spawned-npcs.json

Walks the chain a character has to survive to appear on screen, and reports
every broken link with the place that reaches it:

    REGEN / MOB lump of every chunk of every zone row ─┐
    AI actions that spawn or morph into a monster ─────┤  (Change_CHAR, Create_PET,
                                                        │   CallToAttack, Summon, SummonMaster*)
    LIST_NPC row ─ has a name; AI row -> .aip on disk; hands -> LIST_WEAPON / LIST_SUBWPN.ZSC
    LIST_NPC.CHR entry ─ present; skeleton in range and on disk
    PART_NPC.ZSC models ─ in range, with parts; every mesh and texture on disk;
                          part motion paths on disk
    motions / effects ─ in range (the 0xCDCD padding excepted) and on disk

Severity: ERROR is what crashes a client or leaves an invisible, unclickable
body (a blank row reached by Change_CHAR double-freed the heap and the server
refuses to spawn it; a missing CHR entry or model gives a character with no
engine node; a missing mesh is survivable since 2026-09 but still a hole in
the model). WARN is what degrades with a log line (a texture, a motion clip,
an effect or an AI file that is not there; a hand item past its table, which
logs on every launch). The exit status is 1 when there is any ERROR, so
pack.ps1 can refuse to bake on one.

**A row exists only if column 0 has a name.** That cell is the server's
NPC_NAME, `get_cstr` returns nullptr for a blank one, and every spawn path
(`RegenCharacter` for regen and summons, `Change_CHAR`, the placements in
`zonefile.cpp`) refuses the row on it, silently. Until 2026-10-13 this audit
called a row blank only when it had no name *and* no model, so a row with a
model, stats and an STL name but a blank column 0 passed while the server
refused it: the Junon Ent under 73 Sunshine Coast spawn points and the Woopie
Hooligans seven AI files summon (fix-nameless-npc-rows.py). Such a row is an
ERROR wherever it is reached -- it is evidently meant to spawn. A row with
neither name nor model is retail padding: WARN in a spawn lump (eleven known),
ERROR when an AI action reaches it.

Every case here is one that was found by hand first: the Ghost Seed's
Change_CHAR into blank rows 2734-2738, the Basilisk Captain's missing CHR
entry under 31 spawn points, the Ikaness Worker's weapon object with no
parts, Gangster Pangs' weapon id typed into the sub-weapon hand, and the
missing-asset retry storm. The readers are rosefmt's and the schema
rosedata's; nothing is parsed here.
"""
import argparse
import json
import os
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rosedata as oro  # noqa: E402
from rosefmt import ifo  # noqa: E402
from rosefmt.binio import FormatError  # noqa: E402

REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, "data")

NPC_STB = r"3DDATA\STB\LIST_NPC.STB"
ZONE_STB = r"3DDATA\STB\LIST_ZONE.STB"
AI_STB = r"3DDATA\STB\FILE_AI.STB"
WEAPON_ZSC = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
SUBWPN_ZSC = r"3DDATA\WEAPON\LIST_SUBWPN.ZSC"
NPC_NAME_COL, NPC_MON_COL = 0, 1
ZONE_ZON_COL = 1
PAD_INDEX, PAD_TYPE = 52685, 65535          # 0xCDCD under anim type 0xFFFF: dead padding

# AI actions that carry `WORD cMonster` at offset 8 (audit-ai-monster-refs.py)
G = 0x0B000000
MONSTER_ACTS = {0x0A | G: "Change_CHAR", 0x0B | G: "Create_PET", 0x13 | G: "CallToAttack",
                0x15 | G: "Summon", 0x25 | G: "SummonMaster", 0x26 | G: "SummonMasterDist"}


# ----------------------------------------------------------------- files
class Files:
    """Every file under data/3DDATA as a case- and separator-insensitive set."""

    def __init__(self, root):
        self.have = set()
        base = os.path.join(root, "3DDATA")
        for dp, _dirs, fs in os.walk(base):
            rel = os.path.relpath(dp, root)
            for f in fs:
                self.have.add(oro.norm(os.path.join(rel, f)))

    def exists(self, rel):
        if isinstance(rel, bytes):
            rel = rel.decode("latin-1")
        rel = rel.rstrip("\0")
        k = oro.norm(rel)
        while "//" in k:                     # the VFS collapses doubled separators
            k = k.replace("//", "/")
        return bool(rel) and k in self.have


# ----------------------------------------------------------------- spawns
def zone_rows(zone_stb, only):
    """(zone id, name, map folder) for every zone row with a .zon path."""
    out = []
    for r in range(zone_stb.rows):
        zon = zone_stb.s(r, ZONE_ZON_COL).strip()
        if not zon.lower().endswith(".zon"):
            continue
        if only and r not in only:
            continue
        out.append((r, zone_stb.s(r, NPC_NAME_COL).strip(), os.path.dirname(zon)))
    return out


def spawns_of_zone(folder_rel, placed):
    """{npc id: [where]} from the REGEN and MOB lumps of every chunk; ``placed``
    collects {npc id: .CON name} for the NPC placements."""
    found = defaultdict(list)
    folder = oro.rel_path(DATA, folder_rel)
    if not os.path.isdir(folder):
        return found, "map folder missing: %s" % folder_rel
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(".ifo"):
            continue
        with open(os.path.join(folder, f), "rb") as fh:
            try:
                m = ifo.parse(fh.read())
            except (FormatError, ValueError) as e:
                found[-1].append("%s: unreadable IFO (%s)" % (f, e))
                continue
        stem = f[:-4]
        for g in m.lump(ifo.REGEN) or []:
            for mob in list(g.basic) + list(g.tactic):
                if mob.mob > 0 and mob.count > 0:
                    found[mob.mob].append("%s regen %s" % (stem, g.point_name.decode("latin-1", "replace") or "?"))
        for rec in m.lump(ifo.MOB) or []:
            if rec.obj_id > 0:
                found[rec.obj_id].append("%s npc" % stem)
                placed[rec.obj_id] = rec.con_file
    return found, None


def ai_monsters(aip_path):
    """[(action label, monster id)] named by an AI file's actions."""
    out = []
    try:
        _hdr, _title, pats, _tail = _aip(aip_path)
    except (OSError, FormatError, struct.error, ValueError):
        return None
    for _pname, evs in pats:
        for _ename, _conds, acts in evs:
            for a in acts:
                if len(a) < 10:
                    continue
                typ, = struct.unpack_from("<I", a, 4)
                if typ in MONSTER_ACTS:
                    out.append((MONSTER_ACTS[typ], struct.unpack_from("<H", a, 8)[0]))
    return out


def _aip(path):
    from rosefmt import aip
    with open(path, "rb") as fh:
        return aip.parse(fh.read())


# ----------------------------------------------------------------- checks
class Audit:
    def __init__(self, files):
        self.files = files
        self.npc = oro.Stb(oro.rel_path(DATA, NPC_STB))
        self.ai_stb = oro.Stb(oro.rel_path(DATA, AI_STB))
        self.chr = oro.Chr(oro.rel_path(DATA, oro.NPC_CHR_REL))
        self.parts = oro.Zsc(oro.rel_path(DATA, oro.PART_NPC_ZSC_REL))
        self.hands = {5: ("LIST_WEAPON.ZSC", oro.Zsc(oro.rel_path(DATA, WEAPON_ZSC))),
                      6: ("LIST_SUBWPN.ZSC", oro.Zsc(oro.rel_path(DATA, SUBWPN_ZSC)))}
        self.findings = []          # (severity, npc, text)
        self.seen_model = {}        # PART_NPC object -> [findings]
        self.seen_ai = {}

    def add(self, sev, npc, text):
        self.findings.append((sev, npc, text))

    def name(self, i):
        return self.npc.s(i, NPC_NAME_COL).strip()

    def row_blank(self, i):
        """Neither name nor model: retail padding."""
        return not (self.npc.get(i, NPC_NAME_COL).strip() or self.npc.get(i, NPC_MON_COL).strip())

    def row_refused(self, i):
        """No column-0 name: the server's NPC_NAME is null and every spawn path refuses the row."""
        return not self.npc.get(i, NPC_NAME_COL).strip()

    def ai_file(self, i):
        """The .aip a row's AI column names, or (None, why)."""
        row = self.npc.i(i, oro.NPC_AI_COL)
        if row <= 0:
            return None, None
        if row >= self.ai_stb.rows:
            return None, "AI row %d past FILE_AI.STB (%d rows)" % (row, self.ai_stb.rows)
        rel = self.ai_stb.s(row, 0).strip()
        if not rel:
            return None, "AI row %d is blank in FILE_AI.STB" % row
        if rel.lower().endswith(".ai"):
            rel = rel[:-3] + ".aip"
        if not self.files.exists(rel):
            return None, "AI file missing: %s" % rel
        return oro.rel_path(DATA, rel), None

    def check_model(self, oid):
        """PART_NPC.ZSC object `oid`: cached per object."""
        if oid in self.seen_model:
            return self.seen_model[oid]
        out = []
        z = self.parts
        if not 0 <= oid < len(z.objects):
            out.append(("ERROR", "model %d past PART_NPC.ZSC (%d objects)" % (oid, len(z.objects))))
        else:
            _cyl, parts, _dummies, _bb = z.objects[oid]
            if not parts:
                out.append(("ERROR", "model %d has no parts" % oid))
            for mid, tid, props in parts:
                if not 0 <= mid < len(z.meshes):
                    out.append(("ERROR", "model %d: mesh index %d past the table" % (oid, mid)))
                elif not self.files.exists(z.meshes[mid]):
                    out.append(("ERROR", "model %d: mesh missing %s" % (oid, z.meshes[mid].decode("latin-1"))))
                if not 0 <= tid < len(z.materials):
                    out.append(("WARN", "model %d: material index %d past the table" % (oid, tid)))
                elif not self.files.exists(z.materials[tid][0]):
                    out.append(("WARN", "model %d: texture missing %s" % (oid, z.materials[tid][0].decode("latin-1"))))
                for mp in oro.prop_paths(props):
                    if not self.files.exists(mp):
                        out.append(("WARN", "model %d: part motion missing %s" % (oid, mp)))
        self.seen_model[oid] = out
        return out

    def check_hand(self, i, col):
        v = self.npc.i(i, col)
        if v <= 0:
            return
        label, z = self.hands[col]
        if v >= len(z.objects):
            self.add("WARN", i, "hand col %d = %d past %s (%d objects): logs on every launch"
                     % (col, v, label, len(z.objects)))
            return
        _cyl, parts, _d, _b = z.objects[v]
        if not parts:
            self.add("WARN", i, "hand col %d = %s object %d has no parts (invisible weapon)" % (col, label, v))
            return
        for mid, tid, _props in parts:
            if 0 <= mid < len(z.meshes) and not self.files.exists(z.meshes[mid]):
                self.add("WARN", i, "hand %s %d: mesh missing %s" % (label, v, z.meshes[mid].decode("latin-1")))
            if 0 <= tid < len(z.materials) and not self.files.exists(z.materials[tid][0]):
                self.add("WARN", i, "hand %s %d: texture missing %s" % (label, v, z.materials[tid][0].decode("latin-1")))

    def check_npc(self, i, via_ai):
        if not 0 <= i < self.npc.rows:
            self.add("ERROR" if via_ai else "WARN", i, "id past LIST_NPC.STB (%d rows)" % self.npc.rows)
            return
        if self.row_blank(i):
            if via_ai:
                self.add("ERROR", i, "blank LIST_NPC row reached by an AI action (a client crashed on Change_CHAR into one)")
            else:
                self.add("WARN", i, "blank LIST_NPC row in a spawn lump (the server refuses it: a dead spawn slot)")
            return
        if self.row_refused(i):
            self.add("ERROR", i, "LIST_NPC col 0 (name) is blank although the row has a model (%s): the server's "
                     "NPC_NAME is null, so every spawn path refuses it silently"
                     % self.npc.s(i, NPC_MON_COL).strip())
            return
        # AI
        path, why = self.ai_file(i)
        if why:
            self.add("WARN", i, why + " (the monster will stand still)")
        # hands
        self.check_hand(i, oro.NPC_R_WEAPON_COL)
        self.check_hand(i, oro.NPC_L_WEAPON_COL)
        # CHR
        c = self.chr.chars[i] if i < len(self.chr.chars) else None
        if c is None:
            self.add("ERROR", i, "no LIST_NPC.CHR entry (no skeleton, parts or motions: invisible and unclickable)")
            return
        sk = c["skel"]
        if not 0 <= sk < len(self.chr.skeletons):
            self.add("ERROR", i, "skeleton index %d past the pool (%d)" % (sk, len(self.chr.skeletons)))
        elif not self.files.exists(self.chr.skeletons[sk]):
            self.add("ERROR", i, "skeleton missing %s" % self.chr.skeletons[sk].decode("latin-1"))
        if not c["models"]:
            self.add("ERROR", i, "CHR entry names no model")
        for oid in c["models"]:
            for sev, text in self.check_model(oid):
                self.add(sev, i, text)
        for t, a in c["anims"]:
            if a >= len(self.chr.motions):
                if not (a == PAD_INDEX and t == PAD_TYPE):
                    self.add("WARN", i, "anim type %d: motion index %d past the pool (%d)" % (t, a, len(self.chr.motions)))
            elif not self.files.exists(self.chr.motions[a]):
                self.add("WARN", i, "anim type %d: motion missing %s" % (t, self.chr.motions[a].decode("latin-1")))
        for t, e in c["effects"]:
            if e >= len(self.chr.effects):
                if not (e == PAD_INDEX and t == PAD_TYPE):
                    self.add("WARN", i, "effect type %d: effect index %d past the pool (%d)" % (t, e, len(self.chr.effects)))
            elif not self.files.exists(self.chr.effects[e]):
                self.add("WARN", i, "effect type %d: effect missing %s" % (t, self.chr.effects[e].decode("latin-1")))


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zone", type=int, action="append", help="only this zone row (repeatable)")
    ap.add_argument("--json", help="write every finding here too")
    ap.add_argument("--no-ai", action="store_true", help="do not follow AI summons / morphs")
    a = ap.parse_args()

    files = Files(DATA)
    audit = Audit(files)
    zones = zone_rows(oro.Stb(oro.rel_path(DATA, ZONE_STB)), set(a.zone or []))

    # 1. what the zones spawn
    reach = defaultdict(list)                  # npc id -> ["zone 131 The Burned Forest: 31_30 regen ..."]
    zone_problems = []
    placed = {}
    for zid, zname, folder in zones:
        found, problem = spawns_of_zone(folder, placed)
        if problem:
            zone_problems.append("zone %d %s: %s" % (zid, zname, problem))
            continue
        for i, wheres in found.items():
            if i == -1:
                zone_problems.extend("zone %d %s: %s" % (zid, zname, w) for w in wheres)
                continue
            reach[i].append("zone %d %s (%s%s)" % (zid, zname, wheres[0], " +%d" % (len(wheres) - 1) if len(wheres) > 1 else ""))

    # 2. the AI closure: whatever a reachable monster can summon or become
    if not a.no_ai:
        queue = list(reach)
        done = set()
        while queue:
            i = queue.pop()
            # a refused row never spawns, so its AI never runs
            if i in done or not 0 <= i < audit.npc.rows or audit.row_refused(i):
                continue
            done.add(i)
            path, _why = audit.ai_file(i)
            if not path:
                continue
            acts = audit.seen_ai.get(path)
            if acts is None:
                acts = audit.seen_ai[path] = ai_monsters(path) or []
            for label, mid in acts:
                reach[mid].append("ai %s %s from %d %s" % (os.path.basename(path), label, i, audit.name(i)))
                if mid not in done:
                    queue.append(mid)

    # 3. every reachable id through the chain
    for i in sorted(reach):
        audit.check_npc(i, via_ai=any(w.startswith("ai ") for w in reach[i]))
    # 4. NPC placements: zonefile.cpp spawns one only when its row's NPC_TYPE is 999
    events = oro.Stb(oro.rel_path(DATA, oro.EVENT_STB_REL))
    con_rows = {os.path.basename(events.s(r, oro.EVENT_FILE_COL)).lower() for r in range(events.rows)}
    for i, con in sorted(placed.items()):
        if not 0 <= i < audit.npc.rows or audit.row_refused(i):     # reported by check_npc
            continue
        if audit.npc.s(i, oro.NPC_TYPE_COL).strip() != "999":
            audit.add("ERROR", i, "placed as an NPC but LIST_NPC type is %r, not 999: the server skips the placement silently"
                      % audit.npc.s(i, oro.NPC_TYPE_COL).strip())
        if con and con.decode("latin-1").lower() not in con_rows:
            audit.add("WARN", i, "placement names dialog %s, which no LIST_EVENT row has (mute NPC)" % con.decode("latin-1"))

    # report
    by_sev = defaultdict(list)
    for sev, i, text in audit.findings:
        by_sev[sev].append((i, text))
    print("audit-spawned-npcs: %d zones, %d distinct ids reachable (%d from spawn lumps, %d via AI only)"
          % (len(zones), len(reach), sum(1 for i in reach if any(w.startswith("zone") for w in reach[i])),
             sum(1 for i in reach if not any(w.startswith("zone") for w in reach[i]))))
    for p in zone_problems:
        print("  [ZONE] " + p)
    for sev in ("ERROR", "WARN"):
        items = by_sev.get(sev, [])
        print("%s: %d" % (sev, len(items)))
        for i, text in items:
            where = reach[i][0] + (" +%d more" % (len(reach[i]) - 1) if len(reach[i]) > 1 else "")
            print("  [%s] npc %d %r <- %s: %s" % (sev, i, audit.name(i), where, text))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"zones": len(zones), "reachable": {str(k): v for k, v in reach.items()},
                       "zone_problems": zone_problems,
                       "findings": [{"severity": s, "npc": i, "name": audit.name(i), "text": t,
                                     "reached_from": reach[i]} for s, i, t in audit.findings]},
                      fh, indent=1)
        print("wrote %s" % a.json)
    return 1 if by_sev.get("ERROR") or zone_problems else 0


if __name__ == "__main__":
    sys.exit(main())
