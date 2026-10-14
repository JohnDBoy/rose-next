"""Set up a fight from a build and a LIST_NPC row, run it many times, summarise it."""
import random
import statistics

from . import formulas as F
from .data import ING, ING_LABEL, ING_NAME, JOBS
from .fight import TICK_MS, Combatant, Fight
from .player import StatBlock

AVT_ANI_ATTACK = 8            # datatype.h, avatar attack motion row in TYPE_MOTION
MOB_ANI_ATTACK = 2            # datatype.h, monster attack slot in LIST_NPC.CHR
SURVIVAL_CAP_S = 300          # simulated seconds per survival run before projecting

# Everything the simulator decides that the server code does not.
ASSUMPTIONS = [
    "1v1, both sides in range from the first tick; the monster fights back at once. "
    "No walking, no aggro delay, no other monsters.",
    f"Zone tick is exactly {TICK_MS} ms (the server waits for 100 ms plus the time the "
    "previous object loop took).",
    "Buffs are kept up for the whole fight (cast before the pull, refreshed between "
    "fights). Debuffs and damage skills are cast in the rotation's priority order "
    "whenever they are off cooldown and affordable; a debuff is recast once it drops.",
    "The player stands while fighting (standing regen) and is never mounted.",
    "Equipment is at full durability with life > 0; a gem/option on an item counts "
    "(the server needs it appraised or socketed).",
    "Monsters only use normal attacks (their AI skills are not simulated yet).",
    "A stunned or sleeping monster stops (SetCMD_STOP) and resumes attacking on the tick "
    "the state ends; any player attack, hit or miss, wakes it from sleep. Poison damage "
    "(DoTs) is not simulated.",
    "Potions: drunk the moment HP/MP drops under the threshold, at most every 500 ms "
    "per kind (the client's delay; the server enforces no cooldown).",
    "Arithmetic is double precision; the server uses 32-bit float, so a result sitting "
    "on an integer boundary can differ by one point.",
]


class Simulation:
    def __init__(self, gd, build, npc_row, fix_passive_bugs=False):
        self.gd, self.build, self.npc_row = gd, build, npc_row
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
            if sk.type == 19:
                self.notes.append(f"{sk.name}: drain part (self HP/MP gain) not simulated")
            if any(s and gd.state_type(s) == ING["POISONED"] for s in sk.states):
                self.notes.append(f"{sk.name}: its poison (DoT) damage is not simulated")
        self.m_attack_motion = gd.npc_motion(npc_row, MOB_ANI_ATTACK)
        if self.m_attack_motion is None:
            self.notes.append("monster has no attack motion: it never deals damage")
        elif not self.m_attack_motion.attack_frames:
            self.notes.append("monster attack clip has no event trailer: it deals no damage")

    # ------------------------------------------------------------ combatants
    def make_player(self):
        st, b, srv = self.stats, self.build, self.gd.server
        p = Combatant(b.name, b.level, st.attack_power, st.hit_rate, st.defence, st.resist,
                      st.avoid, st.critical, st.attack_speed, st.max_hp, st.max_mp,
                      st.cur["INT"], st.cur["SENSE"], st.magic, True,
                      base_atk=srv.base_attack_power, base_hit=srv.base_hit,
                      base_aspd=srv.base_attack_speed)
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
                                                     state_tries=0))
                for k in a:
                    a[k] += s[k]
                p_skill += s["dmg"]
        self.dps_auto = p_auto * 1000 / tot_ms
        self.dps_skill = p_skill * 1000 / tot_ms
        self.dps = self.dps_auto + self.dps_skill

        msw = sum(f.m_swings for f in fights)
        mhi = sum(f.m_hits for f in fights)
        self.m_land = mhi / msw if msw else 0
        self.m_crit = sum(f.m_crits for f in fights) / mhi if mhi else 0
        self.m_hit_dmg = sum(f.m_dmg for f in fights) / mhi if mhi else 0
        self.dtps = sum(f.m_dmg for f in fights) * 1000 / tot_ms
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
                state_land=a["states"] / a["state_tries"] if a["state_tries"] else None))
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
            notes=list(s.notes), text=self.text())

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
          f"(NPC {npc.row}, level {npc.level})")
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
            parts.append(f"{sk.mp_cost(st.rate_use_mp)} MP, {sk.reload_ms / 1000:.1f} s cd")
            w(f"  {sk.name} (#{row}): " + ", ".join(x for x in parts if x))
        w(f"  DPS {self.dps:.0f}  (normal {self.dps_auto:.0f} + skills {self.dps_skill:.0f})")
        if self.debuff_uptime:
            w("  debuff uptime on the monster: " + ", ".join(
                f"{ING_LABEL.get(k, ING_NAME.get(k, k))} {v:.0%}" for k, v in self.debuff_uptime.items()))
        w("")
        w("Monster damage")
        w(f"  lands {self.m_land:.0%}, crit {self.m_crit:.0%}, {self.m_hit_dmg:.0f} per landed hit"
          + (f";  stunned/asleep {self.monster_disabled:.0%} of the fight"
             if self.monster_disabled else ""))
        w(f"  damage taken {self.dtps:.0f}/s;  regen {self.regen_hps:.1f} HP/s"
          + (f";  potions {self.potion_hps:.1f} HP/s" if b.potions["enabled"] else ""))
        if self.surv_n:
            proj = (f"; {self.surv_projected}/{self.surv_n} projected past "
                    f"{self.surv_cap:.0f} s" if self.surv_projected else "")
            if self.surv_never * 2 > self.surv_n:
                w(f"  never dies: regen outpaces it ({self.surv_never}/{self.surv_n} runs)")
            elif self.surv:
                w(f"  survives {statistics.median(self.surv):.1f} s against it (median; "
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
