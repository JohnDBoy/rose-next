"""Monster AI (.aip) the way the game server runs it, reduced to a 1v1 fight.

The file is read with `rosefmt.aip` (never a new parser); this module only decodes
the fields of each condition / action record and evaluates them.

Server semantics (src/common/shared/cai_file.cpp, src/sho_gameserver/src/ai_lib/):

* A record's dispatch index is `Type & 0xFF` = N+1 for AICOND_N / AIACT_N.
* `CAI_PATTERN::Check`: events are tried in order and the FIRST whose conditions
  all pass runs all of its actions; nothing after it is tried. Conditions are
  AND-ed and short-circuit, so a random roll in a later condition is only drawn
  when every earlier one passed. One `t_AIPARAM` is shared by every event of one
  evaluation: `m_pFindCHAR` / `m_pNearCHAR` set by a failed event carry over.
* Header: `iSecond` is the STOP pattern's interval (s); `iSecondOfAttackMove` is
  misnamed -- it is the percent gate of the DAMAGED pattern (`AI_WhenDAMAGED`:
  when the monster has a target the pattern runs only if `rate >= AI_SysRANDOM(100)`).
* Distances in conditions 02/03/04/08/18/27 are metres on disk; the loader
  multiplies them by 100 (cai_file.cpp:121-185).

What a 1v1 fight cannot know is answered by `Context` and listed by
`assumed_conditions` so the report can say which answers the AI depended on.
"""
import os
import struct

from rosefmt import aip

CREATED, STOP, ATTACKMOVE, DAMAGED, KILL, DEAD = range(6)
PATTERN_NAMES = ("created", "stop", "attack-move", "damaged", "kill", "dead")

# condition N -> (struct format after the 8-byte header, field names); natural alignment
COND_FMT = {
    1: ("<iB", ("damage", "give")),
    2: ("<iBxhhH", ("dist", "allied", "lv_lo", "lv_hi", "num")),
    3: ("<i", ("dist",)),
    4: ("<iB", ("dist", "less")),
    5: ("<B3xiB", ("ab", "value", "less")),
    6: ("<IB", ("hp", "less")),
    7: ("<B", ("pct",)),
    8: ("<ihhB", ("dist", "lv_lo", "lv_hi", "allied")),
    10: ("<BB", ("ab", "less")),
    11: ("<B3xiB", ("ab", "value", "less")),
    12: ("<B", ("when",)),
    13: ("<BBB", ("target", "kind", "have")),
    14: ("<h2xiB", ("var", "value", "op")),
    15: ("<h2xiB", ("var", "value", "op")),
    16: ("<h2xiB", ("var", "value", "op")),
    17: ("<i", ("npc",)),
    18: ("<iB", ("dist", "op")),
    19: ("<II", ("t0", "t1")),
    20: ("<B3xiB", ("ab", "value", "op")),
    23: ("<II", ("t0", "t1")),
    26: ("<HH", ("x", "y")),
    27: ("<iBxhhHB", ("dist", "allied", "lv_lo", "lv_hi", "num", "op")),
    28: ("<h2xiB", ("var", "value", "op")),
    29: ("<B", ("who",)),
    30: ("<i", ("sec",)),
}
COND_METRES = (2, 3, 4, 8, 18, 27)

ACT_FMT = {
    6: ("<iBB", ("dist", "ab", "less")),
    24: ("<Bxhh", ("target", "skill", "motion")),
    35: ("<h2xiB", ("var", "value", "op")),
}

ACT_METRES = (6,)

COND_LABEL = {
    1: "damage taken >= X", 2: "N characters near", 3: "distance from spawn",
    4: "distance to target", 5: "target ability", 6: "own HP %", 7: "random %",
    8: "a character near", 9: "target is not the attacker", 10: "attacker vs target",
    11: "attacker ability (no target)", 12: "day / night", 13: "status flags",
    14: "event NPC variable", 15: "world variable", 16: "economy variable",
    17: "event NPC in zone", 18: "distance to owner", 19: "zone time", 20: "own ability",
    21: "has no owner", 22: "owner has a target", 23: "world time", 24: "real date/time",
    25: "real weekday/time", 26: "channel", 27: "count near", 28: "AI variable",
    29: "clan master", 30: "alive N seconds",
}
ACT_LABEL = {
    0: "stop", 1: "emote", 2: "say", 3: "wander", 4: "wander near spawn",
    5: "move to found character", 6: "attack by ability", 7: "special attack (no-op)",
    8: "move away from target", 9: "transform", 10: "summon", 11: "call for help",
    12: "attack nearest", 13: "attack found character", 14: "call same monsters",
    15: "attack the attacker", 16: "run away", 17: "drop item", 18: "call monsters",
    19: "attack nearest", 20: "summon", 23: "suicide", 24: "cast skill",
    25: "set NPC variable", 26: "set world variable", 27: "set economy variable",
    28: "shout", 29: "move to owner", 30: "trigger", 31: "attack owner's target",
    33: "regen on/off", 34: "give item", 35: "set AI variable", 36: "summon", 37: "summon",
}
# conditions a 1v1 fight answers with a fixed assumption (report wording)
ASSUMED_COND = {
    3: "distance from spawn = 0 (fought at the spawn point)",
    12: "it is daytime",
    14: "no event NPC in the zone",
    17: "no event NPC in the zone",
    15: "world variables are 0", 16: "economy variables are 0",
    19: "zone-time window never matches", 23: "world-time window never matches",
    24: "real-time window never matches", 25: "real-time window never matches",
    26: "channel 1",
    29: "nobody is a clan master",
    30: "the monster spawned when the fight started",
}
# actions the fight carries out; anything else that fires is counted as "not simulated"
SIMULATED_ACTS = {0, 6, 12, 13, 15, 19, 23, 24, 31, 35}
HARMLESS_ACTS = {1, 2, 7, 17, 21, 22, 25, 26, 27, 28, 29, 31, 32, 33, 34}


def check_op(op, a, b):
    """Check_AiOP (cai_file.h:1049)."""
    if op == 0:
        return a == b
    if op == 1:
        return a > b
    if op == 2:
        return a >= b
    if op == 3:
        return a < b
    if op == 4:
        return a <= b
    if op == 10:
        return a != b
    return False


def result_op(op, cur, val):
    """Result_AiOP (cai_file.h:1079)."""
    if op == 5:
        return val
    if op == 6:
        return cur + val
    if op == 7:
        return cur - val
    return 0


class Record:
    __slots__ = ("n", "f", "ok")

    def __init__(self, rec, fmts, metres=()):
        self.n = (aip.record_type(rec) & 0xFF) - 1
        self.f = {}
        self.ok = True
        fmt = fmts.get(self.n)
        if fmt:
            size = struct.calcsize(fmt[0])
            if len(rec) < 8 + size:
                self.ok = False             # an old short record: the loader rejects these
            else:
                self.f = dict(zip(fmt[1], struct.unpack_from(fmt[0], rec, 8)))
                if self.n in metres:
                    self.f["dist"] *= 100


class AiFile:
    def __init__(self, path):
        self.path = path
        (_n, sec, rate), _title, pats, _tail = aip.parse(open(path, "rb").read())
        self.stop_ms = sec * 1000            # m_ulCheckStopAI
        self.damaged_rate = rate             # m_iRateDamagedAI
        self.patterns = []
        for _pname, evs in pats:
            self.patterns.append([
                ([Record(c, COND_FMT, COND_METRES) for c in conds],
                 [Record(a, ACT_FMT, ACT_METRES) for a in acts])
                for _ename, conds, acts in evs])
        while len(self.patterns) < 6:
            self.patterns.append([])

    def events(self, pattern):
        return self.patterns[pattern]

    def skills(self, pattern):
        """(skill, motion, target) of every AIACT24 in a pattern."""
        return [(a.f["skill"], a.f["motion"], a.f["target"])
                for _c, acts in self.patterns[pattern] for a in acts if a.n == 24 and a.ok]

    def assumed_conditions(self, patterns):
        out = set()
        for p in patterns:
            for conds, _a in self.patterns[p]:
                out.update(c.n for c in conds if c.n in ASSUMED_COND)
        return out

    def action_kinds(self, patterns):
        out = set()
        for p in patterns:
            for _c, acts in self.patterns[p]:
                out.update(a.n for a in acts)
        return out


def load_for_npc(gd, npc_row):
    """NPC_AI_TYPE (LIST_NPC col 16) -> FILE_AI col 0 -> AiFile, or None."""
    ai = gd.npc(npc_row).ai
    fai = gd.stb("FILE_AI")
    if ai <= 0 or ai >= fai.rows:
        return None
    rel = fai.s(ai, 0).strip()
    if not rel:
        return None
    path = os.path.join(gd.data_dir, rel.replace("\\", "/"))
    if not os.path.exists(path):
        return None
    return AiFile(path)


class Param:
    """t_AIPARAM: one per pattern evaluation, shared by its events."""
    __slots__ = ("dest", "damage", "find", "near")

    def __init__(self, dest, damage):
        self.dest, self.damage = dest, damage
        self.find = self.near = None


def ability(u, t):
    """AI_Get_Ability (cai_file.cpp:44)."""
    if t == 0:
        return u.level
    if t == 1:
        return u.total_atk
    if t == 2:
        return u.get_def
    if t == 3:
        return u.get_res
    if t == 4:
        return u.hp
    if t == 5:
        return u.charm
    return 0


class Brain:
    """Evaluates one NPC's patterns. `view` (fight.Mob) supplies the world:

        view.m                    the NPC itself (a Combatant)
        view.m_target             its current target, or None
        view.candidates()         the hostile characters AI_FindFirstOBJ can meet
        view.distance             cm between the fighters
        view.t, view.rng
        view.has_owner, view.owner_has_target(), view.owner_distance()   summons
        view.status_flags(who, kind), view.ai_action(rec, param)
    """

    def __init__(self, ai, fight):
        self.ai, self.f = ai, fight
        self.var = {}

    # ---------------------------------------------------------------- characters
    def _matches(self, dist, allied, lo, hi):
        """AI_FindFirstOBJ(d) walk: the hostile characters within `dist` whose level
        difference (this NPC minus them) is in [lo, hi], in walk order. An allied search
        finds nothing: no other monsters, and a summon's owner is not modelled as one."""
        f = self.f
        if allied or f.distance > dist:
            return []
        lv = f.m.level
        return [c for c in f.candidates() if c.hp > 0 and lo <= lv - c.level <= hi]

    # ---------------------------------------------------------------- conditions
    def cond(self, c, prm):
        if not c.ok:
            return False
        f, n, a = self.f, c.n, c.f
        m = f.m
        tgt = f.m_target if (f.m_target is not None and f.m_target.hp > 0) else None
        if n == 1:
            return not a["give"] and prm.damage >= a["damage"]
        if n in (2, 27):
            found = self._matches(a["dist"], a["allied"], a["lv_lo"], a["lv_hi"])
            if found:
                prm.near = found[0]         # all stand at the same distance
            if n == 2:                      # returns at the wChrNum-th match
                k = max(1, a["num"])
                if len(found) >= k:
                    prm.find = found[k - 1]
                    return True
                return False
            prm.find = prm.near
            return check_op(a["op"], len(found), a["num"])
        if n == 3:
            return 0 >= a["dist"]
        if n == 4:
            if tgt is None:
                return False
            return f.distance <= a["dist"] if a["less"] else f.distance >= a["dist"]
        if n == 5:
            if tgt is None:
                return False
            v = ability(tgt, a["ab"])
            return v <= a["value"] if a["less"] else v >= a["value"]
        if n == 6:
            pct = m.hp * 100 // max(1, m.max_hp)
            return pct <= a["hp"] if a["less"] else pct >= a["hp"]
        if n == 7:
            return f.rng.randrange(100) < a["pct"]
        if n == 8:
            found = self._matches(a["dist"], a["allied"], a["lv_lo"], a["lv_hi"])
            if found:
                prm.find = prm.near = found[0]
                return True
            return False
        if n == 9:
            return tgt is not prm.dest
        if n == 10:
            if tgt is None or prm.dest is None:
                return False
            v1, v2 = ability(prm.dest, a["ab"]), ability(tgt, a["ab"])
            return v1 < v2 if a["less"] else v1 > v2
        if n == 11:
            if tgt is not None or prm.dest is None:
                return False
            v = ability(prm.dest, a["ab"])
            return v <= a["value"] if a["less"] else v >= a["value"]
        if n == 12:
            return a["when"] != 1                 # Is_DAY() == 1
        if n == 13:
            who = m if not a["target"] else tgt
            if who is None:
                return False
            has = f.status_flags(who, a["kind"])
            return bool(a["have"]) if has else not a["have"]
        if n in (15, 16):
            return check_op(a["op"], 0, a["value"])
        if n == 20:
            return check_op(a["op"], ability(m, a["ab"]), a["value"])
        if n == 18:                               # distance to owner
            return f.has_owner and check_op(a["op"], f.owner_distance(), a["dist"])
        if n == 21:
            return not f.has_owner                # "has no owner"
        if n == 22:
            return f.has_owner and f.owner_has_target()
        if n == 26:
            return a["x"] >= 1 and a["y"] <= 1    # reversed in the server, as ported
        if n == 28:
            return check_op(a["op"], self.var.get(a["var"], 0), a["value"])
        if n == 30:
            return f.t // 1000 >= a["sec"]
        # 0, 14, 17, 19, 23, 24, 25, 29, 31+: false in this fight
        return False

    # ---------------------------------------------------------------- running
    def run(self, pattern, dest=None, damage=0):
        """CAI_PATTERN::Check. Returns the number of the event that fired, or None."""
        prm = Param(dest, damage)
        for i, (conds, acts) in enumerate(self.ai.patterns[pattern]):
            if all(self.cond(c, prm) for c in conds):
                for act in acts:
                    if act.ok:
                        self.f.ai_action(act, prm)
                return i
        return None

    def set_var(self, var, op, value):
        """F_AIACT35 + CObjMOB::Set_AiVAR (clamped 0..500)."""
        v = result_op(op, self.var.get(var, 0), value)
        self.var[var] = max(0, min(500, v))


def describe(ai, gd=None):
    """The AI file as readable lines (combat-sim.py ai)."""
    out = [f"stop pattern every {ai.stop_ms / 1000:g} s; damaged pattern gate "
           f"{ai.damaged_rate}% once the monster has a target"]
    for p, evs in enumerate(ai.patterns):
        if not evs:
            continue
        out.append(f"[{PATTERN_NAMES[p]}]")
        for i, (conds, acts) in enumerate(evs):
            cs = " AND ".join(_fmt(c, COND_LABEL) for c in conds) or "always"
            acs = "; ".join(_fmt(a, ACT_LABEL, gd) for a in acts) or "nothing"
            out.append(f"  {i:>2}. if {cs}")
            out.append(f"      -> {acs}")
    return out


def _fmt(rec, labels, gd=None):
    name = labels.get(rec.n, f"#{rec.n}")
    if not rec.ok:
        return f"{name} (short record: rejected)"
    f = dict(rec.f)
    if rec.n == 24 and labels is ACT_LABEL:
        tgt = {0: "found char", 1: "target", 2: "self"}.get(f["target"], f["target"])
        sk = f"skill {f['skill']}"
        if gd is not None:
            try:
                sk += f" {gd.name('LIST_SKILL', f['skill'])}"
            except Exception:   # noqa: BLE001 -- a bad row id is shown, not fatal
                pass
        return f"{name} {sk} at {tgt}, motion {f['motion']}"
    return name + (" " + " ".join(f"{k}={v}" for k, v in f.items()) if f else "")
