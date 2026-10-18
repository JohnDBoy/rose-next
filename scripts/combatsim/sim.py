"""Set up a fight from a build and a LIST_NPC row, run it many times, summarise it."""
import random
import statistics

from . import ai as AI
from . import formulas as F
from .data import ING, ING_LABEL, ING_NAME, JOBS
from .fight import TICK_MS, Combatant, Fight
from .player import StatBlock

AVT_ANI_ATTACK = 8            # datatype.h, avatar attack motion row in TYPE_MOTION
MOB_ANI_ATTACK = 2            # datatype.h, monster attack slot in LIST_NPC.CHR
MAX_MOB_ANI = 11              # datatype.h: CCharDATA::GetMOTION returns NULL past it
SURVIVAL_CAP_S = 300          # simulated seconds per survival run before projecting
GRIND_S = 600                 # a grinding run: ten minutes of back-to-back kills
GRIND_GAP_S = 5               # walking to the next monster

# Everything the simulator decides that the server code does not.
ASSUMPTIONS = [
    "1v1, both sides in range from the first tick; the monster fights back at once. "
    "No walking, no aggro delay, no other monsters. They stand at the shorter of the "
    "two attack ranges (weapon range + 120 / NPC range + scale x 120).",
    f"Zone tick is exactly {TICK_MS} ms (the server waits for 100 ms plus the time the "
    "previous object loop took).",
    "Buffs are kept up for the whole fight (cast before the pull, refreshed between "
    "fights). Debuffs and damage skills are cast in the rotation's priority order "
    "whenever they are off cooldown and affordable, at least 1 s apart (the client's "
    "skill delay) and after the build's 'auto-attacks between skills'; a debuff is "
    "recast once it drops.",
    "The player stands while fighting (standing regen) and is never mounted.",
    "Equipment is at full durability with life > 0; a gem/option on an item counts "
    "(the server needs it appraised or socketed).",
    "Monster AI: the DAMAGED pattern runs on every player hit or miss and every harmful "
    "status (gated by the file's percent once the monster has a target); the STOP pattern "
    "runs on its timer while the monster stands idle. ATTACK-MOVE never runs (nobody "
    "walks), KILL and DEAD end the fight. Of the CREATED pattern only AI variables are "
    "kept: the monster spawned before the pull. The monster's skills ignore their cast "
    "range (it never has to walk to cast).",
    "A stunned or sleeping monster stops and forgets its target (SetCMD_STOP); with an AI "
    "file it fights again only when an AI pattern orders it (a monster without one simply "
    "resumes). A player hit, hit or miss, wakes it from sleep. Poison ticks every second "
    "for its LIST_STATUS value and never kills. A stunned or sleeping player acts again "
    "the moment the state ends.",
    "Survival runs: a monster that would die is replaced at once by a fresh one (full HP, "
    "no debuffs, AI reset), so HP-triggered AI phases repeat.",
    "Summons are called before the pull and stand by the player (same distance to the "
    "monster, 3.5 m from their owner); the player calls a dead one again before anything "
    "else in the rotation. The monster's target searches meet the player first, then the "
    "summons. Summons do not wander, follow or walk.",
    "Potions: drunk the moment HP/MP drops under the threshold, at most every 500 ms "
    "per kind (the client's delay; the server enforces no cooldown).",
    "Arithmetic is double precision; the server uses 32-bit float, so a result sitting "
    "on an integer boundary can differ by one point.",
    "Play (PLAY): 'skilled' is a perfect player -- every skill the moment the 1 s skill "
    "delay allows, every buff and debuff recast the tick it drops, a ranged player never "
    "inside a monster's area skill. 'typical' adds a 0-1 s reaction before each skill, "
    "recasts a buff or debuff 2-8 s after it drops (the first cast of a fight is on time), "
    "and catches a player standing outside the area in 1 of 3 of the monster's area "
    "skills (bunching up, the monster turning, walking in to loot or heal).",
]

# How well the player plays (user, 2026-10-16: "you assume people play perfectly").
# reaction_ms: extra delay drawn after each cast, on top of the 1 s skill delay;
# refresh_lag_ms: how long a dropped buff/debuff stays down before it is recast;
# caught: the share of the monster's area skills that hit a player standing out of range.
PLAY = {
    "skilled": dict(reaction_ms=(0, 0), refresh_lag_ms=(0, 0), caught=0.0),
    "typical": dict(reaction_ms=(0, 1000), refresh_lag_ms=(2000, 8000), caught=1 / 3),
}


class Simulation:
    def __init__(self, gd, build, npc_row, fix_passive_bugs=False, play="skilled"):
        self.gd, self.build, self.npc_row = gd, build, npc_row
        self.play_name, self.play = play, PLAY[play]
        self.stats = StatBlock(gd, build, fix_passive_bugs)
        self.npc = gd.npc(npc_row)
        self.notes = list(self.stats.notes)
        st = self.stats
        wmt = st.weapon_motion_type
        self.p_attack_motion = gd.file_motion(wmt, AVT_ANI_ATTACK, build.female)
        if self.p_attack_motion is None:
            self.notes.append("no attack motion for this weapon: normal attacks never happen")
        self.rotation, self.p_cast_motion, self.p_action_motion = [], {}, {}
        for row in build.rotation:
            sk = gd.skill(row)
            if sk.is_passive():
                continue
            self.rotation.append(sk)
            self.p_cast_motion[row] = gd.file_motion(wmt, sk.ani_casting, build.female) \
                if sk.ani_casting else None
            self.p_action_motion[row] = gd.file_motion(wmt, sk.ani_action, build.female)
            wt = st.wtype
            need = [w for w in sk.need_weapon if w]
            if need and wt not in need and (wt // 10) not in need:
                self.notes.append(f"{sk.name}: needs weapon type {need}, build has {wt}")
            if sk.type in (7, 17):
                self.notes.append(f"{sk.name}: area skill, simulated on the one target")
        self.m_attack_motion = gd.npc_motion(npc_row, MOB_ANI_ATTACK)
        if self.m_attack_motion is None:
            self.notes.append("monster has no attack motion: it never deals damage")
        elif not self.m_attack_motion.attack_frames:
            self.notes.append("monster attack clip has no event trailer: it deals no damage")
        self._npc_motions, self._summon_ai = {}, {}
        self._summons(build)
        # CObjMOB::Get_AttackRange: NPC_ATK_RANGE + NPC_SCALE/100 * 120
        n = self.npc
        self.m_range = int(n.range + n.scale / 100.0 * 120)
        self.distance = min(st.attack_range, self.m_range)
        self._m_motions, self._m_skills = {}, {}
        self.ai = AI.load_for_npc(gd, npc_row)
        self.ai_name = None
        if self.ai is None:
            self.notes.append("monster has no AI file: it fights back and resumes after a "
                              "stun on its own (the server would leave it idle)")
        else:
            self.ai_name = gd.stb("FILE_AI").s(n.ai, 0).strip()
            self._ai_notes()

    def _ai_notes(self):
        ai, gd = self.ai, self.gd
        live = (AI.STOP, AI.DAMAGED)
        for c in sorted(ai.assumed_conditions(live)):
            self.notes.append(f"AI condition '{AI.COND_LABEL[c]}' answered by assumption: "
                              f"{AI.ASSUMED_COND[c]}")
        kinds = ai.action_kinds(live) - AI.SIMULATED_ACTS - AI.HARMLESS_ACTS
        if kinds:
            self.notes.append("AI actions not simulated (counted when they fire): " + ", ".join(
                f"{AI.ACT_LABEL.get(k, k)} (act {k})" for k in sorted(kinds)))
        seen = set()
        for pat in live:
            for row, motion, tgt in ai.skills(pat):
                if row in seen:
                    continue
                seen.add(row)
                sk = self.m_skill(row)
                if sk is None:
                    self.notes.append(f"AI casts skill {row}, a blank LIST_SKILL row: "
                                      "the server refuses the order")
                    continue
                act = self.m_motion(motion + 1)
                if sk.is_damage() and sk.type not in (7, 17):
                    if act is None:
                        self.notes.append(f"monster skill {sk.name} (#{row}): action slot "
                                          f"{motion + 1} unmapped -- the clip already "
                                          "playing gives its timing and hit count")
                    elif not act.attack_frames:
                        self.notes.append(f"monster skill {sk.name} (#{row}): action clip "
                                          "has no hit event -- it deals 0 damage")
                # only a targeted order walks into range first (ProcCMD_Skill2OBJECT ->
                # Goto_TARGET); a self-cast (target 2) is cast where the monster stands
                if tgt != 2 and sk.distance and sk.distance < self.distance:
                    self.notes.append(f"monster skill {sk.name} (#{row}): range "
                                      f"{sk.distance} < {self.distance}; the walk to cast "
                                      "is not simulated (it is cast from the closer spot)")
                if sk.type in (7, 17) and sk.scope < self.cast_distance(sk, tgt == 2):
                    self.notes.append(f"monster skill {sk.name} (#{row}): area {sk.scope} "
                                      f"does not reach the player at {self.distance}")
                if sk.type == 14:
                    self.notes.append(f"monster skill {sk.name} (#{row}) summons: the "
                                      "summon is not simulated")

    def cast_distance(self, sk, self_cast):
        """Where the player stands when a monster skill lands: a targeted cast first
        closes to the skill's range (Goto_TARGET); a self-cast goes off where it is."""
        if not self_cast and sk.distance:
            return min(self.distance, sk.distance)
        return self.distance

    def m_motion(self, slot):
        """CCharDATA::GetMOTION for the monster: None for an unmapped or invalid slot."""
        return self.npc_motion(self.npc_row, slot)

    def npc_motion(self, row, slot):
        """CCharDATA::GetMOTION for any NPC row (the monster, a summon)."""
        k = (row, slot)
        if k not in self._npc_motions:
            self._npc_motions[k] = self.gd.npc_motion(row, slot) \
                if 0 <= slot < MAX_MOB_ANI else None
        return self._npc_motions[k]

    # ------------------------------------------------------------ summons
    def _summons(self, build):
        """build.summons -> the summon Skills kept out, within CUserDATA::GetMax_SummonCNT
        (the client refuses a call past it: CSkillManager::CheckSummonCapacity)."""
        gd, st = self.gd, self.stats
        self.summons = []
        used = 0
        for row in build.summons:
            sk = gd.skill(row)
            npc = self.summon_row(sk)
            if sk.type != 14 or npc <= 0:
                self.notes.append(f"{sk.name} (#{row}) is not a summon skill: ignored")
                continue
            need = gd.stb("LIST_NPC").i(npc, 21)     # NPC_NEED_SUMMON_CNT
            if used + need > st.summon_capacity:
                self.notes.append(f"{sk.name}: summon capacity {st.summon_capacity} is full "
                                  f"({used} used, it needs {need}): left out")
                continue
            used += need
            self.summons.append(sk)
            self.p_cast_motion[row] = (gd.file_motion(st.weapon_motion_type, sk.ani_casting,
                                                      build.female) if sk.ani_casting else None)
            self.p_action_motion[row] = gd.file_motion(st.weapon_motion_type, sk.ani_action,
                                                       build.female)
            ai = self.summon_ai(sk)
            if ai is None:
                self.notes.append(f"{sk.name}: its NPC has no AI file -- it never attacks")
            elif not (ai.action_kinds((1, 3)) & {6, 12, 13, 15, 19, 24, 31}):
                self.notes.append(f"{sk.name}: its AI never attacks or casts")
        self.summon_used = used

    def summon_row(self, sk):
        return self.gd.sk(sk.row, 28)                 # SKILL_SUMMON_PET

    def summon_ai(self, sk):
        row = self.summon_row(sk)
        if row not in self._summon_ai:
            self._summon_ai[row] = AI.load_for_npc(self.gd, row)
        return self._summon_ai[row]

    def make_summon(self, sk):
        """CObjMOB::Init + CObjSUMMON::SetCallerOBJ (cobjnpc.cpp:635): the NPC row scaled by
        the summon skill's rank and the owner's level. Level, INT and SENSE are the owner's
        level; critical stays NPC_LEVEL*0.6 and attack speed NPC_ATK_SPEED."""
        n = self.gd.npc(self.summon_row(sk))
        L, OL = sk.level, self.build.level
        hp = max(1, int(n.hp_col * (L + 16) * (OL + 85) / 2600.0))
        c = Combatant(n.name, OL,
                      int(n.atk * (L + 22) * (OL + 100) / 4000.0),
                      int(n.hit * (L + 30) * (OL + 50) / 3200.0),
                      int(n.df * (L + 30) * (OL + 80) / 4400.0),
                      int(n.res * (L + 24) * (OL + 90) / 3600.0),
                      int(n.avoid * (L + 22) * (OL + 90) / 3400.0),
                      int(n.level * 0.6), n.aspd, hp, 100, OL, OL, bool(n.magic), False)
        return c

    def m_skill(self, row):
        """The Skill an AI action names, or None when F_AIACT24 would refuse it."""
        if row not in self._m_skills:
            gd = self.gd
            stb = gd.stb("LIST_SKILL")
            sk = None
            if 1 <= row < stb.rows:
                sk = gd.skill(row)
                if sk.type == 0 and not gd.names("LIST_SKILL").get(row) \
                        and not stb.get(row, 0).strip():
                    sk = None
            self._m_skills[row] = sk
        return self._m_skills[row]

    # ------------------------------------------------------------ combatants
    def make_player(self):
        st, b, srv = self.stats, self.build, self.gd.server
        p = Combatant(b.name, b.level, st.attack_power, st.hit_rate, st.defence, st.resist,
                      st.avoid, st.critical, st.attack_speed, st.max_hp, st.max_mp,
                      st.cur["INT"], st.cur["SENSE"], st.magic, True,
                      base_atk=srv.base_attack_power, base_hit=srv.base_hit,
                      base_aspd=srv.base_attack_speed)
        p.base_value = st.base_ability
        p.charm = st.cur["CHARM"]
        p.katar_crit = b.job in F.KATAR_CRIT_JOBS and st.wtype == F.WEAPON_TYPE_KATAR
        p.shield_def = st.shield_def
        for buff in b.buffs:
            self._apply_buff(p, buff)
        p.hp, p.mp = p.max_hp, p.max_mp
        return p

    def _apply_buff(self, p, buff):
        gd, st = self.gd, self.stats
        sk = gd.skill(buff["skill"])
        cint = buff["caster_int"] or st.cur["INT"]
        for n, stb_row in enumerate(sk.states):
            if not stb_row:
                continue
            ab, flat, rate = sk.ability[n]
            value = F.skill_adjust_value(st.base_ability(ab), rate, flat, cint)
            if p.st.can_apply(gd, stb_row, value):
                ing = p.st.apply(gd, stb_row, None, value, sk.row)
                if ing == ING["DUMMY_DAMAGE"]:
                    p.dummy_skill_power = sk.power
                    p.refresh()

    def make_monster(self):
        n = self.npc
        hp = max(1, min(2 ** 31 - 1, n.level * n.hp_col))       # ClampedMobMaxHP
        return Combatant(n.name, n.level, n.atk, n.hit, n.df, n.res, n.avoid,
                         int(n.level * 0.6), n.aspd, hp, 100, n.level, n.level,
                         bool(n.magic), False)

    def buff_summary(self):
        p = self.make_player()
        out = []
        for ing, v in sorted(p.st.val.items()):
            out.append((ING_LABEL.get(ing, ING_NAME.get(ing, ing)), v, self.gd.name("LIST_SKILL", p.st.skill[ing])))
        return out

    # ------------------------------------------------------------ running
    def run(self, n=300, seed=1, max_seconds=600, survival=True):
        rng = random.Random(seed)
        fights = [Fight(self, rng, max_seconds=max_seconds).run() for _ in range(n)]
        surv = []
        if survival:
            # SURVIVAL_CAP_S of real simulation; a character still standing then has its
            # death time projected from its late-fight HP loss (Fight._extrapolate)
            surv = [Fight(self, rng, immortal_monster=True, max_seconds=SURVIVAL_CAP_S).run()
                    for _ in range(max(20, n // 10))]
        return Report(self, fights, surv)

    def grind(self, runs=3, seconds=GRIND_S, gap_s=GRIND_GAP_S, seed=1):
        """Grinding: `runs` stretches of `seconds` killing fresh copies of the monster back
        to back, `gap_s` apart, HP / MP / cooldowns / summons carried over and food eaten as
        the build says. A death ends its run."""
        rng = random.Random(seed)
        logs = [Fight(self, rng, immortal_monster=True, max_seconds=seconds,
                      gap_ms=int(gap_s * 1000)).run() for _ in range(runs)]
        t = sum(lg.end_ms for lg in logs) / 1000 or 1
        kills = sum(lg.kills for lg in logs)
        return dict(
            seconds=t, kills=kills, kills_per_min=kills * 60 / t,
            food_hp=sum(lg.potions["hp"] for lg in logs) / max(1, kills),
            food_mp=sum(lg.potions["mp"] for lg in logs) / max(1, kills),
            deaths=sum(1 for lg in logs if lg.result == "loss"), runs=runs,
            rest_share=sum(lg.rest_ms for lg in logs) / 1000 / t,
            died_after=[lg.end_ms / 1000 for lg in logs if lg.result == "loss"])


def _label(ing):
    return ING_LABEL.get(ing, ING_NAME.get(ing, ing))


def _pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


class Report:
    """Aggregates over Monte Carlo fights; every field the text and GUI views show."""

    def __init__(self, sim, fights, surv):
        self.sim = sim
        n = len(fights)
        self.n = n
        wins = [f for f in fights if f.result == "win"]
        self.win_rate = len(wins) / n if n else 0
        self.timeouts = sum(1 for f in fights if f.result == "timeout")
        self.ttk = [f.end_ms / 1000 for f in wins]
        tot_ms = sum(f.end_ms for f in fights) or 1

        sw = sum(f.p_swings for f in fights)
        hi = sum(f.p_hits for f in fights)
        self.p_swings_per_fight = sw / n if n else 0
        self.p_land = hi / sw if sw else 0
        self.p_crit = sum(f.p_crits for f in fights) / hi if hi else 0
        self.p_hit_dmg = sum(f.p_dmg for f in fights) / hi if hi else 0
        p_auto = sum(f.p_dmg for f in fights)
        self.skills = {}
        p_skill = 0
        for f in fights:
            for row, s in f.skills.items():
                a = self.skills.setdefault(row, dict(casts=0, landed=0, dmg=0, states=0,
                                                     state_tries=0, dot=0, drain=0,
                                                     heal=0))
                for k in a:
                    a[k] += s[k]
                p_skill += s["dmg"] + s["dot"]
        self.dps_auto = p_auto * 1000 / tot_ms
        self.dps_skill = p_skill * 1000 / tot_ms
        self.dps_summon = sum(f.s_dmg for f in fights) * 1000 / tot_ms
        self.dps = self.dps_auto + self.dps_skill + self.dps_summon
        # the player's summons
        ssw = sum(f.s_swings for f in fights)
        self.s_swings = ssw / n if n else 0
        self.s_land = sum(f.s_hits for f in fights) / ssw if ssw else 0
        self.s_hit_dmg = (sum(sum(f.s_samples) for f in fights)
                          / max(1, sum(len(f.s_samples) for f in fights)))
        self.s_deaths = sum(f.s_deaths for f in fights) / n if n else 0
        self.s_calls = sum(f.s_calls for f in fights) / n if n else 0
        self.s_taken = sum(f.ms_dmg for f in fights) * 1000 / tot_ms
        self.ms_swings = sum(f.ms_swings for f in fights) / n if n else 0
        self.s_samples = [d for f in fights for d in f.s_samples]
        self.s_swing_s = [(f.s_swing_t[1] - f.s_swing_t[0]) / 1000 / (f.s_swings - 1)
                          for f in fights if f.s_swings >= 4]
        self.m_on_summon = sum(f.m_on_summon_ms for f in fights) / tot_ms
        self.s_skills = {}
        for f in fights:
            for row, a in f.s_skills.items():
                d = self.s_skills.setdefault(row, dict.fromkeys(a, 0))
                for k in a:
                    d[k] += a[k]
        self.s_unsim = {}
        for f in fights:
            for k, v in f.s_unsim.items():
                self.s_unsim[k] = self.s_unsim.get(k, 0) + v
        self.s_unsim = {k: v / n for k, v in self.s_unsim.items()}

        msw = sum(f.m_swings for f in fights)
        mhi = sum(f.m_hits for f in fights)
        self.m_land = mhi / msw if msw else 0
        self.m_crit = sum(f.m_crits for f in fights) / mhi if mhi else 0
        self.m_hit_dmg = sum(f.m_dmg for f in fights) / mhi if mhi else 0
        self.m_skills = {}
        for f in fights:
            for row, a in f.m_skills.items():
                d = self.m_skills.setdefault(row, dict.fromkeys(a, 0))
                for k in a:
                    d[k] += a[k]
        m_skill_dmg = sum(f.m_skill_dmg for f in fights)
        self.dtps_auto = sum(f.m_dmg for f in fights) * 1000 / tot_ms
        self.dtps_skill = m_skill_dmg * 1000 / tot_ms
        self.dtps_dot = sum(f.m_dot_dmg for f in fights) * 1000 / tot_ms
        self.dtps = self.dtps_auto + self.dtps_skill + self.dtps_dot
        self.m_skill_samples = {}
        for f in fights:
            for row, xs in f.m_skill_samples.items():
                self.m_skill_samples.setdefault(row, []).extend(xs)
        self.ai_damaged = sum(f.ai_damaged for f in fights) / n if n else 0
        self.ai_stop = sum(f.ai_stop for f in fights) / n if n else 0
        self.ai_events = {}
        for f in fights:
            for k, v in f.ai_events.items():
                self.ai_events[k] = self.ai_events.get(k, 0) + v
        self.ai_unsim = {}
        for f in fights:
            for k, v in f.ai_unsim.items():
                self.ai_unsim[k] = self.ai_unsim.get(k, 0) + v
        self.ai_unsim = {k: v / n for k, v in self.ai_unsim.items()}
        self.m_idle = sum(f.m_idle_ms for f in fights) / tot_ms
        self.player_disabled = sum(f.player_disabled_ms for f in fights) / tot_ms
        self.player_states = {}
        self.monster_buffs = {}
        for f in fights:
            for k, v in f.player_state_ms.items():
                self.player_states[k] = self.player_states.get(k, 0) + v
            for k, v in f.monster_buff_ms.items():
                self.monster_buffs[k] = self.monster_buffs.get(k, 0) + v
        self.player_states = {k: v / tot_ms for k, v in self.player_states.items()}
        self.monster_buffs = {k: v / tot_ms for k, v in self.monster_buffs.items()}
        self.suicides = sum(f.suicides for f in fights)
        self.regen_hps = sum(f.regen_hp for f in fights) * 1000 / tot_ms
        self.regen_mps = sum(f.regen_mp for f in fights) * 1000 / tot_ms
        self.mp_per_s = sum(f.mp_spent for f in fights) * 1000 / tot_ms
        self.potions = {k: sum(f.potions[k] for f in fights) / n for k in ("hp", "mp")}
        self.potion_hps = sum(f.potion_hp for f in fights) * 1000 / tot_ms

        self.hp_left = [f.hp_left for f in wins]
        self.mp_left = [f.mp_left for f in wins]
        self.max_hp = fights[0].max_hp if fights else 0
        self.max_mp = fights[0].max_mp if fights else 0
        self.debuff_uptime = {}
        for f in fights:
            for ing, ms in f.debuff_ms.items():
                self.debuff_uptime[ing] = self.debuff_uptime.get(ing, 0) + ms
        self.debuff_uptime = {k: v / tot_ms for k, v in self.debuff_uptime.items()}
        self.monster_disabled = sum(f.monster_disabled_ms for f in fights) / tot_ms
        self.p_samples = [d for f in fights for d in f.p_samples]
        self.m_samples = [d for f in fights for d in f.m_samples]
        self.skill_samples = {}
        for f in fights:
            for row, xs in f.skill_samples.items():
                self.skill_samples.setdefault(row, []).extend(xs)
        self.m_swings_per_fight = msw / n if n else 0

        # seconds per swing over each fight, first to last swing (what compare-trace
        # measures): casts, stops and stuns between swings count
        def interval(f, who):
            k, ts = (f.p_swings, f.p_swing_t) if who == "p" else (f.m_swings, f.m_swing_t)
            return (ts[1] - ts[0]) / 1000 / (k - 1) if k >= 4 else None
        self.p_swing_s = [x for x in (interval(f, "p") for f in fights) if x]
        self.m_swing_s = [x for x in (interval(f, "m") for f in fights) if x]
        self.fight_s = [f.end_ms / 1000 for f in fights]

        self.surv_cap = SURVIVAL_CAP_S
        self.surv = ([f.end_ms / 1000 for f in surv if f.result == "loss"]
                     + [f.surv_est for f in surv if f.result != "loss" and f.surv_est])
        self.surv_projected = sum(1 for f in surv if f.result != "loss" and f.surv_est)
        self.surv_never = sum(1 for f in surv if f.result != "loss" and not f.surv_est)
        self.surv_n = len(surv)
        self.oom = [f.oom_ms / 1000 for f in surv if f.oom_ms is not None]

    # ------------------------------------------------------------ plain data
    def summary(self):
        """Everything a viewer shows, as JSON-safe data (the GUI gets this from a worker
        process, so it never holds game tables or fight objects)."""
        s = self.sim
        st, b, npc, gd = s.stats, s.build, s.npc, s.gd
        p, m = s.make_player(), s.make_monster()
        pm, mm = s.p_attack_motion, s.m_attack_motion

        def block(u, mot):
            return dict(hp=u.max_hp, mp=u.max_mp, atk=u.total_atk, hit=u.total_hit,
                        df=u.get_def, res=u.get_res, avoid=u.get_avoid, crit=u.get_crit,
                        aspd=u.total_aspd,
                        swing_ms=mot.duration_ms(u.total_aspd / 100.0) if mot else None)

        def spread(xs):
            return dict(median=statistics.median(xs), p10=_pct(xs, .1), p90=_pct(xs, .9)) \
                if xs else None

        skill_dmg = max(1, sum(a["dmg"] for a in self.skills.values()))
        skills = []
        for row, a in self.skills.items():
            sk = gd.skill(row)
            skills.append(dict(
                row=row, name=sk.name, rank=sk.level, damage=sk.is_damage(),
                casts=a["casts"] / self.n,
                land=a["landed"] / a["casts"] if a["casts"] else 0,
                per_hit=a["dmg"] / a["landed"] if a["landed"] else 0,
                dps=self.dps_skill * a["dmg"] / skill_dmg,
                mp=sk.mp_cost(st.rate_use_mp), cooldown=sk.reload_ms / 1000,
                state_land=a["states"] / a["state_tries"] if a["state_tries"] else None,
                poison=a["dot"] / self.n, drain=a["drain"] / self.n))
        return dict(
            build=b.name, job=JOBS.get(b.job, b.job), level=b.level, female=b.female,
            npc=npc.name, npc_level=npc.level, npc_row=npc.row,
            server=dict(atk=gd.server.base_attack_power, hit=gd.server.base_hit,
                        aspd=gd.server.base_attack_speed),
            n=self.n, win_rate=self.win_rate, timeouts=self.timeouts,
            ttk=spread(self.ttk), hp_left=statistics.median(self.hp_left) if self.hp_left else None,
            mp_left=statistics.median(self.mp_left) if self.mp_left else None,
            max_hp=self.max_hp, max_mp=self.max_mp,
            surv=spread(self.surv), surv_n=self.surv_n, surv_never=self.surv_never,
            surv_projected=self.surv_projected, surv_cap=self.surv_cap,
            oom=statistics.median(self.oom) if self.oom else None,
            dps=self.dps, dps_auto=self.dps_auto, dps_skill=self.dps_skill, dtps=self.dtps,
            dps_summon=self.dps_summon, summons=self._summon_summary(),
            regen_hps=self.regen_hps, regen_mps=self.regen_mps, potion_hps=self.potion_hps,
            mp_per_s=self.mp_per_s, potions_on=b.potions["enabled"], potions=self.potions,
            player=block(p, pm), monster=block(m, mm),
            buffs=[list(x) for x in s.buff_summary()],
            normal=dict(per_fight=self.p_swings_per_fight, land=self.p_land, crit=self.p_crit,
                        per_hit=self.p_hit_dmg, dps=self.dps_auto),
            skills=skills,
            debuffs=[[ING_LABEL.get(k, ING_NAME.get(k, k)), v]
                     for k, v in self.debuff_uptime.items()],
            m_land=self.m_land, m_crit=self.m_crit, m_hit_dmg=self.m_hit_dmg,
            monster_disabled=self.monster_disabled,
            dtps_auto=self.dtps_auto, dtps_skill=self.dtps_skill,
            monster_swings=self.m_swings_per_fight,
            m_skills=self._m_skill_rows(), ai=self._ai_summary(),
            player_disabled=self.player_disabled, monster_idle=self.m_idle,
            player_states=[[_label(k), v] for k, v in self.player_states.items()],
            monster_buffs=[[_label(k), v] for k, v in self.monster_buffs.items()],
            notes=list(s.notes), text=self.text())

    def _summon_summary(self):
        """The build's summons: their stats as called, and how they fought."""
        s = self.sim
        if not s.summons:
            return None
        units = []
        for sk in s.summons:
            u = s.make_summon(sk)
            mot = s.npc_motion(s.summon_row(sk), 2)
            units.append(dict(
                name=u.name, skill=sk.name, rank=sk.level, row=sk.row,
                npc=s.summon_row(sk), level=u.level, hp=u.max_hp, atk=u.total_atk,
                hit=u.total_hit, df=u.get_def, res=u.get_res, avoid=u.get_avoid,
                crit=u.get_crit, aspd=u.total_aspd,
                swing_ms=mot.duration_ms(u.total_aspd / 100.0) if mot else None))
        gd = s.gd
        skills = [dict(row=r, name=gd.skill(r).name, casts=a["casts"] / self.n,
                       land=a["landed"] / a["casts"] if a["casts"] else None,
                       per_hit=a["dmg"] / a["landed"] if a["landed"] else 0,
                       state_land=a["states"] / a["state_tries"] if a["state_tries"] else None)
                  for r, a in sorted(self.s_skills.items())]
        return dict(units=units, capacity=s.stats.summon_capacity, used=s.summon_used,
                    dps=self.dps_summon, swings=self.s_swings, land=self.s_land,
                    per_hit=self.s_hit_dmg, deaths=self.s_deaths, calls=self.s_calls,
                    taken=self.s_taken, monster_on_them=self.m_on_summon, skills=skills,
                    unsimulated=[[AI.ACT_LABEL.get(k, str(k)), v]
                                 for k, v in sorted(self.s_unsim.items(), key=str)])

    def _m_skill_rows(self):
        gd, out = self.sim.gd, []
        tot = max(1, sum(a["dmg"] for a in self.m_skills.values()))
        for row, a in sorted(self.m_skills.items(), key=lambda kv: -kv[1]["casts"]):
            sk = gd.skill(row)
            out.append(dict(
                row=row, name=sk.name, type=sk.type, damage=sk.is_damage(),
                mode=sk.action_mode, orders=a["orders"] / self.n, casts=a["casts"] / self.n,
                land=a["landed"] / a["casts"] if a["casts"] and sk.is_damage() else None,
                per_hit=a["dmg"] / a["landed"] if a["landed"] else 0,
                dps=self.dtps_skill * a["dmg"] / tot,
                state_land=a["states"] / a["state_tries"] if a["state_tries"] else None))
        return out

    def _ai_summary(self):
        s = self.sim
        if s.ai is None:
            return None
        return dict(file=s.ai_name, damaged_rate=s.ai.damaged_rate,
                    stop_s=s.ai.stop_ms / 1000, damaged_runs=self.ai_damaged,
                    stop_runs=self.ai_stop, distance=s.distance,
                    unsimulated=[[AI.ACT_LABEL.get(k, str(k)), v]
                                 for k, v in sorted(self.ai_unsim.items(), key=str)],
                    suicides=self.suicides)

    # ------------------------------------------------------------ text
    def text(self):
        s = self.sim
        st, b, npc, gd = s.stats, s.build, s.npc, s.gd
        srv = gd.server
        p = s.make_player()
        m = s.make_monster()
        L = []
        w = L.append
        w(f"== {b.name}: {JOBS.get(b.job, b.job)} {b.level}  vs  {npc.name} "
          f"(NPC {npc.row}, level {npc.level})  [{s.play_name} play]")
        w("")
        w("Player (totals the combat formulas read; server.toml adds "
          f"ATK +{srv.base_attack_power}, HIT +{srv.base_hit}, ASPD +{srv.base_attack_speed})")
        c = st.cur
        w(f"  STR {c['STR']}  DEX {c['DEX']}  INT {c['INT']}  CON {c['CON']}  "
          f"CHA {c['CHARM']}  SEN {c['SENSE']}")
        w(f"  HP {p.max_hp}  MP {p.max_mp}  ATK {p.total_atk}  HIT {p.total_hit}  "
          f"DEF {p.get_def}  RES {p.get_res}  AVOID {p.get_avoid}  CRIT {p.get_crit}  "
          f"ASPD {p.total_aspd}  {'magic' if p.magic else 'physical'}")
        if p.st.val:
            w("  buffs: " + ", ".join(f"{n} {v:+d} ({sk})" for n, v, sk in s.buff_summary()))
        w(f"  regen (standing) every 2 s: "
          f"HP {int((st.recover_hp + (c['CON'] + 40) / 6.0) / 6.0)}  "
          f"MP {int((st.recover_mp + (c['CON'] + 40) / 6.0) / 6.0)};  MP cost x{st.rate_use_mp:.2f}")
        w("Monster")
        w(f"  HP {m.max_hp}  ATK {m.total_atk}  HIT {m.total_hit}  DEF {m.get_def}  "
          f"RES {m.get_res}  AVOID {m.get_avoid}  CRIT {m.get_crit}  ASPD {m.total_aspd}  "
          f"{'magic' if m.magic else 'physical'}")
        w("")
        pm, mm = s.p_attack_motion, s.m_attack_motion
        w("Swing timing")
        if pm:
            w(f"  player: {pm.duration_ms(p.total_aspd / 100.0)} ms per swing "
              f"({pm.total} frames @ {pm.fps} fps, x{pm.attack_frames} hit)")
        if mm:
            w(f"  monster: {mm.duration_ms(m.total_aspd / 100.0)} ms per swing "
              f"({mm.total} frames @ {mm.fps} fps, x{mm.attack_frames} hit)")
        w("")
        w(f"Player damage ({self.n} fights)")
        w(f"  normal attack: lands {self.p_land:.0%}, crit {self.p_crit:.0%} of landed, "
          f"{self.p_hit_dmg:.0f} per landed hit, {self.p_swings_per_fight:.1f} swings/fight")
        for row, a in self.skills.items():
            sk = gd.skill(row)
            per = a["dmg"] / a["landed"] if a["landed"] else 0
            parts = [f"{a['casts'] / self.n:.1f} casts/fight"]
            if sk.is_damage():
                parts.append(f"lands {a['landed'] / a['casts']:.0%}" if a["casts"] else "")
                parts.append(f"{per:.0f} per landed cast")
            if a["state_tries"]:
                parts.append(f"state lands {a['states'] / a['state_tries']:.0%}")
            if a["dot"]:
                parts.append(f"poison/burn {a['dot'] / self.n:.0f} damage/fight")
            if a["drain"]:
                parts.append(f"drains {a['drain'] / self.n:.0f} HP/fight back")
            if a["heal"]:
                parts.append(f"restores {a['heal'] / self.n:.0f} "
                             f"{(sk.restores() or 'hp').upper()}/fight")
            parts.append(f"{sk.mp_cost(st.rate_use_mp)} MP, {sk.reload_ms / 1000:.1f} s cd")
            w(f"  {sk.name} (#{row}): " + ", ".join(x for x in parts if x))
        w(f"  DPS {self.dps:.0f}  (normal {self.dps_auto:.0f} + skills {self.dps_skill:.0f}"
          + (f" + summons {self.dps_summon:.0f})" if s.summons else ")"))
        if self.debuff_uptime:
            w("  debuff uptime on the monster: " + ", ".join(
                f"{ING_LABEL.get(k, ING_NAME.get(k, k))} {v:.0%}" for k, v in self.debuff_uptime.items()))
        w("")
        sm = self._summon_summary()
        if sm:
            w(f"Summons (capacity {sm['used']}/{sm['capacity']}; out when the fight starts, "
              f"called again when they die)")
            for u in sm["units"]:
                w(f"  {u['name']} ({u['skill']} rank {u['rank']}, NPC {u['npc']}): level "
                  f"{u['level']}  HP {u['hp']}  ATK {u['atk']}  HIT {u['hit']}  DEF {u['df']}  "
                  f"RES {u['res']}  AVOID {u['avoid']}  CRIT {u['crit']}  ASPD {u['aspd']}"
                  + (f"  ({u['swing_ms']} ms per swing)" if u["swing_ms"] else ""))
            w(f"  together: {sm['swings']:.1f} swings/fight, lands {sm['land']:.0%}, "
              f"{sm['per_hit']:.0f} per landed hit, {sm['dps']:.0f} DPS")
            for k in sm["skills"]:
                w(f"  cast {k['name']} (#{k['row']}): {k['casts']:.1f}/fight"
                  + (f", lands {k['land']:.0%}" if k["land"] is not None
                     and gd.skill(k["row"]).is_damage() else "")
                  + (f", {k['per_hit']:.0f} per landed cast" if k["per_hit"] else "")
                  + (f", state lands {k['state_land']:.0%}" if k["state_land"] is not None
                     else ""))
            w(f"  the monster hits them for {sm['taken']:.1f}/s and is on them "
              f"{sm['monster_on_them']:.0%} of the fight; {sm['deaths']:.2f} deaths and "
              f"{sm['calls']:.2f} calls per fight")
            if sm["unsimulated"]:
                w("  their AI did, not simulated, per fight: " + ", ".join(
                    f"{k} {v:.1f}" for k, v in sm["unsimulated"]))
            w("")
        w("Monster damage")
        w(f"  normal attack: lands {self.m_land:.0%}, crit {self.m_crit:.0%}, "
          f"{self.m_hit_dmg:.0f} per landed hit"
          + (f";  stunned/asleep {self.monster_disabled:.0%} of the fight"
             if self.monster_disabled else ""))
        for r in self._m_skill_rows():
            parts = [f"{r['casts']:.1f} casts/fight"]
            if r["orders"] > r["casts"] + 0.05:
                parts.append(f"{r['orders']:.1f} orders")
            if r["land"] is not None:
                parts += [f"lands {r['land']:.0%}", f"{r['per_hit']:.0f} per landed cast"]
            if r["state_land"] is not None:
                parts.append(f"state lands {r['state_land']:.0%}")
            parts.append({1: "then attacks", 2: "then resumes"}.get(r["mode"], "then STOPS"))
            w(f"  skill {r['name']} (#{r['row']}, type {r['type']}): " + ", ".join(parts))
        if self.m_idle > 0.005:
            w(f"  stands idle (stopped, no target) {self.m_idle:.0%} of the fight")
        if self.monster_buffs:
            w("  its buffs' uptime: " + ", ".join(
                f"{_label(k)} {v:.0%}" for k, v in self.monster_buffs.items()))
        if self.player_states:
            w("  states on the player: " + ", ".join(
                f"{_label(k)} {v:.0%}" for k, v in self.player_states.items())
              + (f";  player stunned/asleep {self.player_disabled:.0%}"
                 if self.player_disabled else ""))
        w(f"  damage taken {self.dtps:.0f}/s"
          + (f" (normal {self.dtps_auto:.0f} + skills {self.dtps_skill:.0f}"
             + (f" + poison/burn {self.dtps_dot:.0f}" if self.dtps_dot else "") + ")"
             if self.dtps_skill or self.dtps_dot else "")
          + f";  regen {self.regen_hps:.1f} HP/s"
          + (f";  potions {self.potion_hps:.1f} HP/s" if b.potions["enabled"] else ""))
        if self.surv_n:
            proj = (f"; {self.surv_projected}/{self.surv_n} projected past "
                    f"{self.surv_cap:.0f} s" if self.surv_projected else "")
            if self.surv_never * 2 > self.surv_n:
                w(f"  never dies: regen outpaces it ({self.surv_never}/{self.surv_n} runs)")
            elif self.surv:
                w(f"  survives {statistics.median(self.surv):.1f} s against fresh copies back to "
                  f"back (median; "
                  f"{_pct(self.surv, .1):.1f}-{_pct(self.surv, .9):.1f} s p10-p90){proj}")
        w("")
        w("Outcome")
        w(f"  wins {self.win_rate:.0%}" + (f", {self.timeouts} timeouts" if self.timeouts else ""))
        if self.ttk:
            w(f"  time to kill {statistics.median(self.ttk):.1f} s median "
              f"({_pct(self.ttk, .1):.1f}-{_pct(self.ttk, .9):.1f} s p10-p90)")
            hp = statistics.median(self.hp_left)
            mp = statistics.median(self.mp_left)
            w(f"  left after a win: HP {hp:.0f}/{self.max_hp} ({hp / self.max_hp:.0%}), "
              f"MP {mp:.0f}/{self.max_mp} ({mp / max(1, self.max_mp):.0%}) (median)")
        w(f"  MP spent {self.mp_per_s:.1f}/s vs regen {self.regen_mps:.1f}/s"
          + (f"; out of skill MP after {statistics.median(self.oom):.0f} s"
             if self.oom else ""))
        if b.potions["enabled"]:
            w(f"  potions per fight: HP {self.potions['hp']:.1f}, MP {self.potions['mp']:.1f}")
        ai = self._ai_summary()
        if ai:
            w("")
            w(f"Monster AI ({ai['file']}): damaged pattern {ai['damaged_runs']:.1f} runs/fight "
              f"(gate {ai['damaged_rate']}% once it has a target), stop pattern "
              f"{ai['stop_runs']:.1f} runs/fight (every {ai['stop_s']:g} s idle); "
              f"distance {ai['distance']} cm")
            if ai["unsimulated"]:
                w("  fired but not simulated, per fight: " + ", ".join(
                    f"{k} {v:.1f}" for k, v in ai["unsimulated"]))
            if ai["suicides"]:
                w(f"  suicided in {ai['suicides']} fights")
        if s.notes:
            w("")
            w("Warnings")
            for n in s.notes:
                w(f"  ! {n}")
        w("")
        w("Assumptions")
        for a in ASSUMPTIONS:
            w(f"  - {a}")
        return "\n".join(L)
