"""One fight, tick by tick, the way a zone thread runs it.

Timing is a literal port of `CObjCHAR::Proc` (cobjchar.cpp:2054): every tick each
actor advances its current motion; when a motion completes inside the tick, the
next action starts at once and the leftover milliseconds carry into it. A normal
swing applies its damage when the attack motion *starts* (`Start_ATTACK` ->
`Attack_START`), multiplied by the clip's attack-frame count. A skill pays its MP
when the cast motion starts and lands at frame 0 of the action motion
(`CObjAI::Do_SKILL`).
"""
import random

from . import formulas as F
from .data import AT, ING

TICK_MS = 100                 # gs_threadzone.cpp: _FRAME_PER_SECOND 10
RECOVERY_MS = 2000            # GameStaticConfig::RECOVERY_RATE_TIME
SKILL_DELAY_MS = 500          # gs_user.cpp SKILL_DELAY_TIME (any two casts)
POTION_DELAY_MS = 500         # client useitemdelay.h (the server enforces none)
SELF_TYPES = (8, 10, 12)      # SKILL_TYPE_08/10/12: stat/status change on the caster

# Which ING slot a buff or debuff on AT_x lands in; (raise, lower)
ING_FOR_AT = {
    AT["ATK"]: ("INC_APOWER", "DEC_APOWER"), AT["DEF"]: ("INC_DPOWER", "DEC_DPOWER"),
    AT["RES"]: ("INC_RES", "DEC_RES"), AT["HIT"]: ("INC_HIT", "DEC_HIT"),
    AT["CRITICAL"]: ("INC_CRITICAL", "DEC_CRITICAL"), AT["AVOID"]: ("INC_AVOID", "DEC_AVOID"),
    AT["ATK_SPD"]: ("INC_ATK_SPD", "DEC_ATK_SPD"), AT["SPEED"]: ("INC_MOV_SPD", "DEC_MOV_SPD"),
    AT["MAX_HP"]: ("INC_MAX_HP", None), AT["MAX_MP"]: ("INC_MAX_MP", None),
}


class Status:
    """StatusEffects: one slot per ING type, value + remaining 1-second ticks.

    `on_change` is called whenever a slot is set or cleared, so the owner can
    recompute its totals once instead of on every read.
    """

    def __init__(self, on_change=None):
        self.val = {}         # ing -> value
        self.ticks = {}       # ing -> remaining ticks (None = permanent)
        self.stb = {}         # ing -> LIST_STATUS row
        self.skill = {}       # ing -> skill row that applied it
        self.acc = 0
        self.on_change = on_change

    def get(self, name):
        return self.val.get(ING[name], 0)

    def is_set(self, ing):
        return ing in self.val

    def can_apply(self, gd, stb_row, value):
        """IsEnableApplay: a set slot accepts only a duplicable state of >= value."""
        ing = gd.state_type(stb_row)
        if ing in self.val:
            if not gd.state_can_dup(stb_row):
                return False
            if self.val[ing] > value:
                return False
        return True

    def apply(self, gd, stb_row, duration, value, skill_row):
        ing = gd.state_type(stb_row)
        self.val[ing] = value
        self.ticks[ing] = duration
        self.stb[ing] = stb_row
        self.skill[ing] = skill_row
        if self.on_change:
            self.on_change()
        return ing

    def clear(self, ing):
        if ing not in self.val:
            return
        for d in (self.val, self.ticks, self.stb, self.skill):
            d.pop(ing, None)
        if self.on_change:
            self.on_change()

    def disabled(self):
        """StatusEffects::IsIgnoreSTATUS: sleep or faint blocks every command."""
        return _SLEEP in self.val or _FAINT in self.val

    def proc(self, ms):
        """StatusEffects::Proc: once per accumulated second, `if (m_nTICKs[i]-- <= 0) clear`."""
        self.acc += ms
        if self.acc < 1000:
            return False
        changed = False
        while self.acc >= 1000:
            self.acc -= 1000
            for ing in list(self.ticks):
                t = self.ticks[ing]
                if t is None:
                    continue
                if t <= 0:
                    for d in (self.val, self.ticks, self.stb, self.skill):
                        d.pop(ing, None)
                    changed = True
                else:
                    self.ticks[ing] = t - 1
        if changed and self.on_change:
            self.on_change()
        return changed


_SLEEP, _FAINT, _DUMMY = ING["SLEEP"], ING["FAINTING"], ING["DUMMY_DAMAGE"]
_I = {k: ING[k] for k in ("INC_APOWER", "DEC_APOWER", "INC_HIT", "DEC_HIT", "INC_ATK_SPD",
                          "DEC_ATK_SPD", "INC_DPOWER", "DEC_DPOWER", "INC_RES", "DEC_RES",
                          "INC_AVOID", "DEC_AVOID", "INC_CRITICAL", "DEC_CRITICAL",
                          "INC_MAX_HP", "INC_MAX_MP")}


class Combatant:
    """The getters calculation.cpp calls, over a base stat block + live status.

    The totals are plain attributes, recomputed by `refresh()` whenever the status
    changes (or a base field is edited): the formulas read them thousands of times
    per fight, statuses change a few times.
    """

    def __init__(self, name, level, attack_power, hit_rate, defence, resist, avoid,
                 critical, attack_speed, max_hp, max_mp, int_, sense, magic, is_user,
                 base_atk=0, base_hit=0, base_aspd=0):
        self.name, self.level = name, level
        self.attack_power, self.hit_rate = attack_power, hit_rate
        self.defence, self.resist, self.avoid, self.critical = defence, resist, avoid, critical
        self.attack_speed = attack_speed
        self.ori_max_hp, self.ori_max_mp = max_hp, max_mp
        self.int_, self.sense, self.magic, self.is_user = int_, sense, magic, is_user
        self.get_int, self.get_sense = int_, sense
        self.base_atk, self.base_hit, self.base_aspd = base_atk, base_hit, base_aspd
        self.dummy_skill_power = 0
        self.st = Status(self.refresh)
        self.refresh()
        self.hp, self.mp = max_hp, max_mp

    def refresh(self):
        v = self.st.val.get
        I = _I  # noqa: E741
        # CObjCHAR::total_* (+ classUSER's server.toml bases). Unsigned in C++: a debuff
        # bigger than the stat wraps to a huge number; clamped here.
        self.total_atk = max(0, self.attack_power + v(I["INC_APOWER"], 0)
                             - v(I["DEC_APOWER"], 0) + self.base_atk)
        self.total_hit = max(0, self.hit_rate + v(I["INC_HIT"], 0) - v(I["DEC_HIT"], 0)
                             + self.base_hit)
        self.total_aspd = max(1, self.attack_speed + v(I["INC_ATK_SPD"], 0)
                              - v(I["DEC_ATK_SPD"], 0) + self.base_aspd)
        # CObjCHAR::Get_* floor at 10
        self.get_def = max(10, self.defence + v(I["INC_DPOWER"], 0) - v(I["DEC_DPOWER"], 0))
        self.get_res = max(10, self.resist + v(I["INC_RES"], 0) - v(I["DEC_RES"], 0))
        self.get_avoid = max(10, self.avoid + v(I["INC_AVOID"], 0) - v(I["DEC_AVOID"], 0))
        self.get_crit = max(10, self.critical + v(I["INC_CRITICAL"], 0)
                            - v(I["DEC_CRITICAL"], 0))
        self.max_hp = self.ori_max_hp + v(I["INC_MAX_HP"], 0)
        self.max_mp = self.ori_max_mp + v(I["INC_MAX_MP"], 0)
        self.dummy_power = self.dummy_skill_power if _DUMMY in self.st.val else 0

    def current_ability(self, at):
        """CObjMOB::Get_AbilityValue: a monster's percentage base is its live value."""
        return {AT["ATK"]: self.total_atk, AT["DEF"]: self.get_def, AT["HIT"]: self.total_hit,
                AT["RES"]: self.get_res, AT["AVOID"]: self.get_avoid,
                AT["ATK_SPD"]: self.total_aspd, AT["CRITICAL"]: self.get_crit,
                AT["MAX_HP"]: self.max_hp}.get(at, 0)


class Actor:
    """Motion clock for one combatant (CObjCHAR::Proc + ProcMotionFrame)."""

    def __init__(self, unit):
        self.u = unit
        self.motion = None
        self.ratio = 1.0
        self.cur = 0
        self.acc = 0.0

    def set_motion(self, motion, ratio):
        self.motion, self.ratio = motion, ratio
        self.cur, self.acc = 0, 0.0

    def advance(self, ms, on_complete):
        m = self.motion
        if m is None:
            on_complete()
            return
        remain = m.total - self.cur
        need = max(1, m.need_time(remain, self.ratio))
        while ms >= need:
            self.cur += remain
            on_complete()                       # RealProc: next action starts now
            ms -= need
            self.cur, self.acc = 0, 0.0
            m = self.motion
            if m is None:
                return
            remain = m.total
            need = max(1, m.need_time(remain, self.ratio))
        self.acc += m.pass_frame(ms, self.ratio)
        r = int(self.acc)
        if r:
            self.acc -= r
            self.cur += r


class Log:
    def __init__(self):
        self.p_swings = self.p_hits = self.p_crits = self.p_dmg = 0
        self.m_swings = self.m_hits = self.m_crits = self.m_dmg = 0
        self.skills = {}          # row -> dict(casts, landed, dmg, states_landed)
        self.mp_spent = 0
        self.potions = {"hp": 0, "mp": 0}
        self.regen_hp = self.regen_mp = self.potion_hp = self.potion_mp = 0
        self.debuff_ms = {}       # ing -> ms active on the monster
        self.oom_ms = None
        self.monster_disabled_ms = 0
        self.p_samples, self.m_samples = [], []   # landed hit damages, for percentiles
        self.skill_samples = {}                   # skill row -> landed damages
        self.end_ms = 0
        self.result = None        # "win" | "loss" | "timeout"

    def skill(self, row):
        return self.skills.setdefault(row, dict(casts=0, landed=0, dmg=0, states=0,
                                                state_tries=0))


class Fight:
    def __init__(self, sim, rng=None, immortal_monster=False, max_seconds=600):
        self.sim, self.gd = sim, sim.gd
        self.rng = rng or random.Random()
        self.p = sim.make_player()
        self.m = sim.make_monster()
        if immortal_monster:
            self.m.ori_max_hp = self.m.hp = 10 ** 12
            self.m.refresh()
        self.immortal = immortal_monster
        rate = sim.stats.rate_use_mp
        self.cost = {sk.row: sk.mp_cost(rate) for sk in sim.rotation}
        self.min_cost = min(self.cost.values()) if self.cost else None
        self.hp_trace = []        # (ms, hp) every 2 s, for survival extrapolation
        self.max_ms = max_seconds * 1000
        self.log = Log()
        self.pa, self.ma = Actor(self.p), Actor(self.m)
        self.t = 0
        self.p_state = "idle"     # idle | attack | cast | action
        self.p_pending = None     # skill being cast
        self.last_cast = {}       # skill row -> accept time
        self.last_any_cast = -10 ** 9
        self.regen_acc = 0
        self.last_potion = {"hp": -10 ** 9, "mp": -10 ** 9}
        self.potion_run = {}      # "hp"/"mp" -> dict(total, acc_value, tot_time, acc_time, stb)

    # ------------------------------------------------------------ player decisions
    def _skill_ready(self, sk):
        if self.t - self.last_any_cast < SKILL_DELAY_MS:
            return False
        if self.t - self.last_cast.get(sk.row, -10 ** 9) < sk.reload_ms:
            return False
        if self.p.mp < self.cost[sk.row]:
            return False
        if sk.hp_cost() and self.p.hp <= sk.hp_cost():
            return False
        if not sk.is_damage():
            # a pure (de)buff is recast only when one of its states has dropped off
            who = self.p if sk.type in SELF_TYPES else self.m
            states = [s for s in sk.states if s]
            if states and all(who.st.is_set(self.gd.state_type(s)) for s in states):
                return False
        return True

    def _player_next(self):
        """What the player does when its current motion ends (or at t=0)."""
        if self.p_state == "cast":
            self._skill_action(self.p_pending)
            return
        for sk in self.sim.rotation:
            if self._skill_ready(sk):
                self._skill_start(sk)
                return
        self._player_swing()

    def _player_swing(self):
        mot = self.sim.p_attack_motion
        self.p_state = "attack"
        self.pa.set_motion(mot, self.p.total_aspd / 100.0)
        if mot is None or not mot.attack_frames:
            return
        if self.sim.stats.shot is not None and not self.sim.build.ammo:
            return
        lg = self.log
        lg.p_swings += 1
        dmg, crit = F.normal_attack(self.rng, self.p, self.m, mot.attack_frames)
        self.m.st.clear(ING["SLEEP"])       # Apply_DAMAGE: an attack wakes a sleeper
        if dmg:
            lg.p_hits += 1
            lg.p_crits += crit
            lg.p_dmg += dmg
            lg.p_samples.append(dmg)
            self.m.hp -= dmg

    def _skill_start(self, sk):
        """Do_SKILL first half: pay, then cast motion (or straight to the action)."""
        self.last_cast[sk.row] = self.t
        self.last_any_cast = self.t
        cost = self.cost[sk.row]
        self.p.mp -= cost
        self.p.hp -= sk.hp_cost()
        self.log.mp_spent += cost
        self.log.skill(sk.row)["casts"] += 1
        cast = self.sim.p_cast_motion.get(sk.row)
        if cast is not None:
            self.p_state, self.p_pending = "cast", sk
            self.pa.set_motion(cast, sk.casting_speed())
        else:
            self._skill_action(sk)

    def _skill_action(self, sk):
        """Do_SKILL second half: action motion starts, Skill_START applies at once."""
        act = self.sim.p_action_motion.get(sk.row)
        self.p_state, self.p_pending = "action", None
        self.pa.set_motion(act, sk.action_speed())
        rec = self.log.skill(sk.row)
        if sk.is_damage():
            hit_cnt = 1 if sk.type in (7, 17) else (act.attack_frames if act else 1)
            dmg = F.skill_damage(self.rng, self.p, self.m, sk, hit_cnt)
            self.m.st.clear(ING["SLEEP"])
            if dmg:
                rec["landed"] += 1
                rec["dmg"] += dmg
                self.log.skill_samples.setdefault(sk.row, []).append(dmg)
                self.m.hp -= dmg
        # Skill_ChangeIngSTATUS runs after the damage for 3/4/5/6, on its own for 9/13;
        # 8/10/12 are self-cast
        target = self.p if sk.type in SELF_TYPES else self.m
        self._apply_states(sk, self.p, target, rec)

    def _apply_states(self, sk, caster, target, rec):
        """Skill_ApplyIngSTATUS for each state slot of the skill (cobjchar.cpp:1411)."""
        gd = self.gd
        for n, stb_row in enumerate(sk.states):
            if not stb_row:
                continue
            rec["state_tries"] += 1
            if sk.success:
                if gd.state_harmful(stb_row):
                    if not F.harmful_state_lands(self.rng, sk.success, caster.level,
                                                 caster.get_int, target):
                        continue
                elif sk.success < target.level - caster.level + 1 + F.R(self.rng, 100):
                    continue
            ab, flat, rate = sk.ability[n]
            value = F.skill_adjust_value(target.current_ability(ab), rate, flat, caster.get_int)
            if not target.st.can_apply(gd, stb_row, value):
                continue
            ing = target.st.apply(gd, stb_row, sk.duration, value, sk.row)
            if ing == ING["DUMMY_DAMAGE"]:
                target.dummy_skill_power = sk.power
                target.refresh()
            if target is self.m and ing in (ING["SLEEP"], ING["FAINTING"]):
                self.ma.motion = None       # UpdateIngSTATUS -> SetCMD_STOP
            rec["states"] += 1

    def _on_player_motion_end(self):
        if self.p.hp <= 0 or self.m.hp <= 0:
            self.pa.motion = None
            return
        self._player_next()

    # ------------------------------------------------------------ monster
    def _monster_swing(self):
        mot = self.sim.m_attack_motion
        self.ma.set_motion(mot, self.m.total_aspd / 100.0)
        if mot is None or not mot.attack_frames or self.p.hp <= 0:
            return
        lg = self.log
        lg.m_swings += 1
        dmg, crit = F.normal_attack(self.rng, self.m, self.p, mot.attack_frames)
        if dmg:
            lg.m_hits += 1
            lg.m_crits += crit
            lg.m_dmg += dmg
            lg.m_samples.append(dmg)
            self.p.hp -= dmg

    def _on_monster_motion_end(self):
        if self.p.hp <= 0 or self.m.hp <= 0:
            self.ma.motion = None
            return
        self._monster_swing()

    # ------------------------------------------------------------ upkeep
    def _regen(self, ms):
        """CObjAVT::Check_PerFRAME, not sitting: every 2 s, (Recover + (CON+40)/6.f)/6.f."""
        self.regen_acc += ms
        while self.regen_acc >= RECOVERY_MS:
            self.regen_acc -= RECOVERY_MS
            if self.p.hp <= 0:
                return
            if self.immortal:
                self.hp_trace.append((self.t, self.p.hp))
            con = self.sim.stats.cur["CON"]
            hp = int((self.sim.stats.recover_hp + (con + 40) / 6.0) / 6.0)
            mp = int((self.sim.stats.recover_mp + (con + 40) / 6.0) / 6.0)
            gain = min(hp, self.p.max_hp - self.p.hp)
            self.p.hp += gain
            self.log.regen_hp += gain
            gain = min(mp, self.p.max_mp - self.p.mp)
            self.p.mp += gain
            self.log.regen_mp += gain

    def _potions(self, ms):
        pot = self.sim.build.potions
        if not pot["enabled"]:
            return
        gd = self.gd
        # running over-time potions (StatusEffects::Proc_IngPOTION)
        for kind in ("hp", "mp"):
            run = self.potion_run.get(kind)
            if not run:
                continue
            run["acc_time"] += ms
            cur = int(run["acc_time"] * run["total"] / run["tot_time"])
            diff = (run["total"] - run["acc"]) if cur >= run["total"] else cur - run["acc"]
            run["acc"] += diff
            if kind == "hp":
                self.p.hp = min(self.p.max_hp, self.p.hp + diff)
                self.log.potion_hp += diff
                full = self.p.hp >= self.p.max_hp
            else:
                self.p.mp = min(self.p.max_mp, self.p.mp + diff)
                self.log.potion_mp += diff
                full = self.p.mp >= self.p.max_mp
            if full or run["acc"] >= run["total"]:
                del self.potion_run[kind]
        # drink when below the threshold
        for kind, cur, mx in (("hp", self.p.hp, self.p.max_hp), ("mp", self.p.mp, self.p.max_mp)):
            row = pot[kind]
            if not row or self.p.hp <= 0 or cur * 100 >= mx * pot[kind + "_below"]:
                continue
            if self.t - self.last_potion[kind] < POTION_DELAY_MS or kind in self.potion_run:
                continue
            ui = gd.stb("LIST_USEITEM")
            status = ui.i(row, 24)
            total = ui.i(row, 20)
            self.last_potion[kind] = self.t
            self.log.potions[kind] += 1
            if status:
                per_sec = next((v for _, v in (gd.state_apply(status, n) for n in range(2)) if v), 0)
                if per_sec:
                    self.potion_run[kind] = dict(total=total, acc=0, acc_time=0,
                                                 tot_time=max(1, 1000 * total // per_sec))
            else:
                if kind == "hp":
                    gain = min(total, self.p.max_hp - self.p.hp)
                    self.p.hp += gain
                    self.log.potion_hp += gain
                else:
                    gain = min(total, self.p.max_mp - self.p.mp)
                    self.p.mp += gain
                    self.log.potion_mp += gain

    def _extrapolate(self):
        """Still alive at the cap against an unkillable monster: project the death time
        from the HP lost over the second half of the run (the steady state, once the
        opening MP pool and any potions have played out). None = never dies."""
        tr = self.hp_trace
        if len(tr) < 8:
            return None
        h = len(tr) // 2
        q = h + (len(tr) - h) // 2
        a, b = tr[h:q], tr[q:]
        mean_a = sum(x for _, x in a) / len(a)
        mean_b = sum(x for _, x in b) / len(b)
        dt = (sum(t for t, _ in b) / len(b) - sum(t for t, _ in a) / len(a)) / 1000.0
        loss = (mean_a - mean_b) / dt if dt > 0 else 0
        if loss <= 0.05:          # under 0.05 HP/s net: regen keeps up
            return None
        return self.t / 1000.0 + max(0, self.p.hp) / loss

    # ------------------------------------------------------------ run
    def run(self):
        lg = self.log
        self._player_next()           # both open on the first tick in range
        self._monster_swing()
        while True:
            if self.m.hp <= 0:
                lg.result = "win"
                break
            if self.p.hp <= 0:
                lg.result = "loss"
                break
            if self.t >= self.max_ms:
                lg.result = "timeout"
                break
            self.t += TICK_MS
            if self.p.st.ticks:
                self.p.st.proc(TICK_MS)
            if self.m.st.val:
                for ing in self.m.st.val:
                    lg.debuff_ms[ing] = lg.debuff_ms.get(ing, 0) + TICK_MS
                self.m.st.proc(TICK_MS)
            self.pa.advance(TICK_MS, self._on_player_motion_end)
            if self.m.hp > 0:
                if self.m.st.disabled():
                    lg.monster_disabled_ms += TICK_MS
                elif self.ma.motion is None:
                    self._monster_swing()   # back on its feet: the AI re-issues the attack
                else:
                    self.ma.advance(TICK_MS, self._on_monster_motion_end)
            if self.p.hp > 0:
                self._regen(TICK_MS)
                self._potions(TICK_MS)
            if lg.oom_ms is None and self.min_cost is not None and self.p.mp < self.min_cost:
                lg.oom_ms = self.t
        lg.end_ms = self.t
        lg.surv_est = self._extrapolate() if self.immortal and lg.result == "timeout" else None
        lg.hp_left, lg.mp_left = max(0, self.p.hp), max(0, self.p.mp)
        lg.max_hp, lg.max_mp = self.p.max_hp, self.p.max_mp
        lg.monster_hp_left = max(0, self.m.hp)
        return lg
