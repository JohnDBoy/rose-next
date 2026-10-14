"""Compare a client CombatTrace log with the simulator, for one test scenario.

The client logs (with `[LOG] LEVEL=debug`) every damage event it receives:

    CombatTrace combat swing received: attacker A defender D event E seq S damage X
        hp_after H lethal L                                   (normal attacks)
    CombatTrace FlatDamageEvent queued: attacker A defender D event E seq S kind K
        damage X hp_after H                                   (skills and others)
    CombatTrace GSV_TARGET_SKILL: caster C target T skill N ...   (a cast)

Timestamps have one-second resolution, so swing intervals are averaged over whole
fights. Crits are not flagged on the wire; they show up in the damage spread. A miss is
damage 0.

Which id is the player: the attacker that fought the most distinct opponents (one per
kill), or --player. Each opponent id is one fight; a `lethal 1` hit on it is the kill.
"""
import math
import re
import statistics
from datetime import datetime

TS = r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"
RX_SWING = re.compile(TS + r".*CombatTrace combat swing received: attacker (\d+) defender (\d+) "
                      r"event (\d+) seq \d+ damage (-?\d+) hp_after (-?\d+) lethal (\d)")
RX_FLAT = re.compile(TS + r".*CombatTrace FlatDamageEvent queued: attacker (\d+) defender (\d+) "
                     r"event (\d+) seq \d+ kind (\d+) damage (-?\d+) hp_after (-?\d+)")
RX_CAST = re.compile(TS + r".*CombatTrace GSV_TARGET_SKILL: caster (\d+) target (\d+) skill (\d+)")
# The cast lines above carry SERVER object ids; these carry the caster's CLIENT id.
RX_IMPACT = re.compile(TS + r".*CombatTrace projectile impact: caster (\d+) target (\d+) skill (\d+)")
RX_REG = re.compile(TS + r".*CombatTrace projectile cast registered: caster (\d+) target (\d+) "
                    r"skill (\d+)")
# Every skill's damage as the server sent it (legacy packet; SERVER ids for both sides).
# Monster skills reach the log only this way: the client may still abandon presenting
# one ("skill payload cancelled ... cast abandoned"), but the server applied it.
RX_DMG_SKILL = re.compile(TS + r".*CombatTrace GSV_DAMAGE_OF_SKILL: caster (\d+) target (\d+) "
                          r"skill (\d+) type \d+ bullet \d+ damage -?\d+ value (\d+) hp_after "
                          r"-?\d+ success_bits (\d+)")
RX_EFFECT = re.compile(TS + r".*SkillStatusTrace client effect: caster (\d+) target (\d+) "
                       r"skill (\d+) type \d+ success_bits (\d+)")


def _t(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()


def parse(path, since=None, until=None):
    """hits [(t, kind, attacker, defender, event, damage, hp_after, lethal)] in client
    ids, and `sk`: casts (server ids), regs / impacts (client caster, server target),
    effects (client ids, success_bits = which state slots landed)."""
    hits, seen = [], set()
    sk = dict(casts=[], regs=[], impacts=[], effects=[], dmg_skill=[])
    t0 = _t(since) if since else None
    t1 = _t(until) if until else None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "Trace" not in line:
                continue
            m = RX_SWING.match(line)
            if m:
                ts, a, d, ev, dmg, hp, leth = m.groups()
                t = _t(ts)
                key = (int(a), int(d), int(ev))
                if (not t0 or t >= t0) and (not t1 or t <= t1) and key not in seen:
                    seen.add(key)
                    hits.append((t, "swing", int(a), int(d), int(ev), int(dmg), int(hp),
                                 int(leth)))
                continue
            m = RX_FLAT.match(line)
            if m:
                ts, a, d, ev, kind, dmg, hp = m.groups()
                t = _t(ts)
                key = (int(a), int(d), int(ev))
                if (not t0 or t >= t0) and (not t1 or t <= t1) and key not in seen:
                    seen.add(key)
                    hits.append((t, "event", int(a), int(d), int(ev), int(dmg), int(hp),
                                 1 if int(hp) <= 0 or int(hp) == -30000 else 0))
                continue
            for name, rx in (("casts", RX_CAST), ("regs", RX_REG), ("impacts", RX_IMPACT),
                             ("effects", RX_EFFECT), ("dmg_skill", RX_DMG_SKILL)):
                m = rx.match(line)
                if m:
                    t = _t(m.group(1))
                    if (not t0 or t >= t0) and (not t1 or t <= t1):
                        sk[name].append((t,) + tuple(int(x) for x in m.groups()[1:]))
                    break
    return hits, sk


def guess_player(hits, player_hp=None):
    """The id that trades blows with the most opponents; on a tie (a single fight), the
    one whose HP looks like the simulated player's."""
    pairs = {(a, d) for _t, _k, a, d, *_ in hits}
    mutual = {}
    for a, d in pairs:
        if (d, a) in pairs:
            mutual.setdefault(a, set()).add(d)
    pool = mutual or {}
    if not pool:
        for a, d in pairs:
            pool.setdefault(a, set()).add(d)
    if not pool:
        return None
    top = max(len(v) for v in pool.values())
    cands = [k for k, v in pool.items() if len(v) == top]
    if len(cands) == 1 or not player_hp:
        return cands[0]
    peak = {}
    for _t, _k, a, d, _e, dmg, hp, _l in hits:
        if hp > 0:
            peak[d] = max(peak.get(d, 0), hp + dmg)
    return min(cands, key=lambda k: abs(peak.get(k, 10 ** 9) - player_hp))


def fights(hits, casts, player=None, player_hp=None):
    if player is None:
        player = guess_player(hits, player_hp)
        if player is None:
            return None, []
    # The player's summons: whatever else hits the monsters the player hits (a GM-spawned
    # test monster fights nobody else). Their swings ("s") and the monster's swings at
    # them ("ms") join the fight; a summon's kill closes it like the player's.
    opp = {d for _t, _k, a, d, *_ in hits if a == player}
    allies = {a for _t, _k, a, d, *_ in hits if d in opp and a != player and a not in opp}
    # The server hands a dead monster's object id to the next spawn, so a kill closes
    # that id's fight and its next event opens a new one.
    out, gen = {}, {}
    for h in sorted(hits):
        t, kind, a, d, ev, dmg, hp, leth = h
        if a == player or a in allies:
            mob, side = d, ("p" if a == player else "s")
        elif d == player or d in allies:
            mob, side = a, ("m" if d == player else "ms")
        else:
            continue
        if mob == player or mob in allies:
            continue
        key = (mob, gen.get(mob, 0))
        f = out.setdefault(key, dict(mob=mob, p=[], m=[], s=[], ms=[], casts=[]))
        f[side].append(h)
        if side in ("p", "s") and leth:
            gen[mob] = gen.get(mob, 0) + 1
    res = []
    for f in out.values():
        if not f["p"]:
            continue
        ev = sorted(f["p"] + f["m"] + f["s"] + f["ms"])
        f["start"], f["end"] = ev[0][0], ev[-1][0]
        f["killed"] = any(h[7] for h in f["p"] + f["s"])
        res.append(f)
    res.sort(key=lambda f: f["start"])
    return player, res


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def crit_cut(xs):
    """Crits are not flagged in the log, but a crit uses a different formula and lands
    in its own cluster: split at the widest gap if it is clearly a gap (> 20% of the
    median). None when the damage is one cluster."""
    xs = sorted(xs)
    if len(xs) < 10:
        return None
    gap, at = max((xs[i + 1] - xs[i], i) for i in range(len(xs) - 1))
    if gap < 0.2 * xs[len(xs) // 2] or at < 1 or at > len(xs) - 3:
        return None
    return (xs[at] + xs[at + 1]) / 2


def _mean_flag(game, sim):
    """'ok' unless the sim mean is > 3 standard errors from the game mean."""
    if len(game) < 5 or not sim:
        return "few samples"
    sd = statistics.pstdev(game) or 1.0
    se = sd / math.sqrt(len(game))
    z = abs(statistics.mean(game) - statistics.mean(sim)) / se
    return "ok" if z < 3 else f"MISMATCH ({z:.1f} SE)"


def _rate_flag(k, n, p):
    if n < 10:
        return "few samples"
    se = math.sqrt(max(p * (1 - p), 1e-4) / n)
    z = abs(k / n - p) / se
    return "ok" if z < 3 else f"MISMATCH ({z:.1f} SE)"


def _count_flag(k, fights, per_fight):
    """Poisson check of an event count over whole fights."""
    lam = fights * per_fight
    if fights < 5 or lam < 3:
        return "few samples"
    z = abs(k - lam) / math.sqrt(lam)
    return "ok" if z < 3 else f"MISMATCH ({z:.1f} SE)"


def compare(gd, sim, path, since=None, player=None, n=1000, until=None, exclude=()):
    hits, casts = parse(path, since, until)
    player, fs = fights(hits, casts, player, sim.make_player().max_hp)
    # --exclude: fight numbers as "Per fight" prints them (another monster joined, ...)
    fs = [f for i, f in enumerate(fs, 1) if i not in set(exclude)]
    rep = sim.run(n=n, seed=7, survival=False)
    L = []
    w = L.append
    w(f"== Trace {path}")
    if not fs:
        w("   no fights found (is [LOG] LEVEL=debug set, and --since right?)")
        return "\n".join(L)
    w(f"   player id {player}; {len(fs)} opponents, {sum(f['killed'] for f in fs)} killed")
    w(f"   vs sim: {sim.build.name} vs {sim.npc.name} ({n} simulated fights)")
    w("")
    w(f"{'metric':<34}{'game':>16}{'sim':>16}   verdict")

    def row(name, g, s, verdict=""):
        w(f"{name:<34}{g:>16}{s:>16}   {verdict}")

    # player normal attacks
    sw = [h for f in fs for h in f["p"] if h[1] == "swing"]
    landed = [h[5] for h in sw if h[5] > 0]
    row("player swings (normal)", len(sw), f"{rep.p_swings_per_fight:.1f}/fight")
    if sw:
        row("  lands", f"{len(landed) / len(sw):.0%} ({len(landed)}/{len(sw)})",
            f"{rep.p_land:.0%}", _rate_flag(len(landed), len(sw), rep.p_land))
    if landed:
        row("  damage per landed hit (mean)", f"{statistics.mean(landed):.0f}",
            f"{rep.p_hit_dmg:.0f}", _mean_flag(landed, rep.p_samples))
        row("  p10 / p50 / p90",
            f"{_pct(landed, .1)}/{_pct(landed, .5)}/{_pct(landed, .9)}",
            f"{_pct(rep.p_samples, .1)}/{_pct(rep.p_samples, .5)}/{_pct(rep.p_samples, .9)}")
        row("  max", max(landed), max(rep.p_samples) if rep.p_samples else "-")
        cut = crit_cut(landed)
        if cut:
            k = sum(1 for x in landed if x > cut)
            row("  crit share (split at the gap)", f"{k / len(landed):.0%} ({k}/{len(landed)})",
                f"{rep.p_crit:.0%}", _rate_flag(k, len(landed), rep.p_crit))
    # swing interval: seconds per normal swing inside each fight
    iv = []
    for f in fs:
        ts = [h[0] for h in f["p"] if h[1] == "swing"]
        if len(ts) >= 4:
            iv.append((ts[-1] - ts[0]) / (len(ts) - 1))
    if iv and rep.p_swing_s:
        exp = statistics.mean(rep.p_swing_s)
        row("  seconds per swing (mean of fights)", f"{statistics.mean(iv):.2f}", f"{exp:.2f}",
            "ok" if abs(statistics.mean(iv) - exp) < 0.15 * exp else "CHECK (walking or "
            "human pauses stretch it)")
    # player skills: damage events are attributed through "projectile impact" (client
    # caster id); casts and debuffs through the server-id cast lines, mapped to the
    # player by matching "projectile cast registered" (client id) on time and skill
    lo = min(f["start"] for f in fs) - 3
    hi = max(f["end"] for f in fs) + 3
    impacts = [x for x in casts["impacts"] if x[1] == player and lo <= x[0] <= hi]
    regs = [x for x in casts["regs"] if x[1] == player and lo <= x[0] <= hi]
    votes = {}
    for t, c, tg, skl in casts["casts"]:
        if any(r[3] == skl and abs(r[0] - t) <= 1 for r in regs):
            votes[c] = votes.get(c, 0) + 1
    server_id = max(votes, key=votes.get) if votes else None
    my_casts = [x for x in casts["casts"] if x[1] == server_id and lo <= x[0] <= hi]
    effects = [x for x in casts["effects"] if x[1] == player and lo <= x[0] <= hi]
    skill_hits = {}
    for f in fs:
        for h in f["p"]:
            if h[1] != "event":
                continue
            near = [x for x in impacts if abs(x[0] - h[0]) <= 1]
            if near:
                skl = min(near, key=lambda x: abs(x[0] - h[0]))[3]
                skill_hits.setdefault(gd.sk(skl, 1) or skl, []).append(h[5])
    sim_dmg, sim_states = {}, {}
    for row_, xs in rep.skill_samples.items():
        sim_dmg.setdefault(gd.sk(row_, 1) or row_, []).extend(xs)
    for row_, a in rep.skills.items():
        g = gd.sk(row_, 1) or row_
        sim_states[g] = (a["states"], a["state_tries"], a["casts"] / rep.n)
    groups = {}
    for t, c, tg, skl in my_casts:
        if tg != c:                                 # self-cast buffs are listed apart
            groups.setdefault(gd.sk(skl, 1) or skl, []).append((t, tg, skl))
    if my_casts or skill_hits:
        w("")
        selfc = sorted({gd.name("LIST_SKILL", x[3]) for x in my_casts if x[2] == x[1]})
        if selfc:
            w(f"self buffs cast: {', '.join(selfc)}")
    for g, cs in sorted(groups.items()):
        skl = cs[0][2]
        sk_ = gd.skill(skl)
        st = sim_states.get(g)
        row(f"skill {sk_.name} (rank {sk_.level}) casts", len(cs),
            f"{st[2]:.1f}/fight" if st else "not in rotation")
        dm = [x for x in skill_hits.get(g, []) if x > 0]
        if dm:
            sx = sim_dmg.get(g, [])
            row("  damage per landed cast (mean)", f"{statistics.mean(dm):.0f}",
                f"{statistics.mean(sx):.0f}" if sx else "-", _mean_flag(dm, sx) if sx else "")
            row("  p10 / p50 / p90", f"{_pct(dm, .1)}/{_pct(dm, .5)}/{_pct(dm, .9)}",
                f"{_pct(sx, .1)}/{_pct(sx, .5)}/{_pct(sx, .9)}" if sx else "-")
        slots = sum(1 for x in sk_.states if x)
        if slots:
            eff = [e for e in effects if (gd.sk(e[3], 1) or e[3]) == g]
            landed_slots = sum(bin(e[4]).count("1") for e in eff)
            tries = len(cs) * slots
            sim_rate = st[0] / st[1] if st and st[1] else None
            row("  debuff slots landed", f"{landed_slots / tries:.0%} ({landed_slots}/{tries})",
                f"{sim_rate:.0%}" if sim_rate is not None else "-",
                _rate_flag(landed_slots, tries, sim_rate) if sim_rate is not None else "")
    # monster attacks
    msw = [h for f in fs for h in f["m"] if h[1] == "swing"]
    mland = [h[5] for h in msw if h[5] > 0]
    mskill = [h[5] for f in fs for h in f["m"] if h[1] != "swing"]
    w("")
    row("monster swings", len(msw), f"{rep.m_swings_per_fight:.1f}/fight")
    if msw:
        row("  lands", f"{len(mland) / len(msw):.0%} ({len(mland)}/{len(msw)})",
            f"{rep.m_land:.0%}", _rate_flag(len(mland), len(msw), rep.m_land))
    if mland:
        row("  damage per landed hit (mean)", f"{statistics.mean(mland):.0f}",
            f"{rep.m_hit_dmg:.0f}", _mean_flag(mland, rep.m_samples))
        row("  p10 / p50 / p90",
            f"{_pct(mland, .1)}/{_pct(mland, .5)}/{_pct(mland, .9)}",
            f"{_pct(rep.m_samples, .1)}/{_pct(rep.m_samples, .5)}/{_pct(rep.m_samples, .9)}")
    miv = []
    for f in fs:
        ts = [h[0] for h in f["m"] if h[1] == "swing"]
        if len(ts) >= 4:
            miv.append((ts[-1] - ts[0]) / (len(ts) - 1))
    if miv and rep.m_swing_s:
        exp = statistics.mean(rep.m_swing_s)
        clip = sim.m_attack_motion.duration_ms(sim.make_monster().total_aspd / 100.0) / 1000
        row("  seconds per swing (mean of fights)", f"{statistics.mean(miv):.2f}",
            f"{exp:.2f}", ("ok" if abs(statistics.mean(miv) - exp) < 0.15 * exp
                           else "CHECK (walking stretches it)")
            + (f"  (clip alone {clip:.2f})" if abs(clip - exp) > 0.05 else ""))
    # monster skills: GSV_DAMAGE_OF_SKILL lines (server ids). The player's server id is the
    # target hit by skills from two or more casters (a monster is only ever hit by the
    # player); the fight windows keep other players' fights out.
    by_target = {}
    for t, c, tg, skl, val, bits in casts["dmg_skill"]:
        if lo <= t <= hi:
            by_target.setdefault(tg, set()).add(c)
    p_srv = max(by_target, key=lambda k: len(by_target[k]), default=None)
    m_dmg = []
    if p_srv is not None and len(by_target[p_srv]) >= 2:
        m_dmg = [x for x in casts["dmg_skill"] if x[2] == p_srv and lo <= x[0] <= hi
                 and any(f["start"] - 1 <= x[0] <= f["end"] + 1 for f in fs)]
    sim_hits = sum(a["casts"] for r_, a in rep.m_skills.items() if gd.skill(r_).is_damage())
    if m_dmg or sim_hits:
        w("")
        sim_pf = sim_hits / rep.n
        row("monster skill casts (damage)", f"{len(m_dmg) / len(fs):.1f}/fight ({len(m_dmg)})",
            f"{sim_pf:.1f}/fight", _count_flag(len(m_dmg), len(fs), sim_pf))
        for skl in sorted({x[3] for x in m_dmg} | set(rep.m_skills)):
            sk_ = gd.skill(skl)
            g = [x for x in m_dmg if x[3] == skl]
            a = rep.m_skills.get(skl)
            row(f"  {sk_.name} (#{skl})", f"{len(g) / len(fs):.2f}/fight",
                f"{a['casts'] / rep.n:.2f}/fight" if a else "not cast")
            ml = [x[4] for x in g if x[4] > 0]
            sx = rep.m_skill_samples.get(skl, [])
            if g and a and a["casts"]:
                sim_land = a["landed"] / a["casts"]
                row("    lands", f"{len(ml) / len(g):.0%} ({len(ml)}/{len(g)})",
                    f"{sim_land:.0%}", _rate_flag(len(ml), len(g), sim_land))
            if ml:
                row("    damage per landed cast (mean)", f"{statistics.mean(ml):.0f}",
                    f"{statistics.mean(sx):.0f}" if sx else "-", _mean_flag(ml, sx) if sx else "")
                row("    p10 / p50 / p90", f"{_pct(ml, .1)}/{_pct(ml, .5)}/{_pct(ml, .9)}",
                    f"{_pct(sx, .1)}/{_pct(sx, .5)}/{_pct(sx, .9)}" if sx else "-")
            slots = sum(1 for x in sk_.states if x)
            if slots and g and a:
                landed_slots = sum(bin(x[5]).count("1") for x in g)
                tries = len(g) * slots
                sim_rate = a["states"] / a["state_tries"] if a["state_tries"] else 0
                row("    states landed on the player",
                    f"{landed_slots / tries:.0%} ({landed_slots}/{tries})", f"{sim_rate:.0%}",
                    _rate_flag(landed_slots, tries, sim_rate))
        for f in fs:
            f["m_skill"] = sum(x[4] for x in m_dmg if f["start"] - 1 <= x[0] <= f["end"] + 1)
    # the player's summons
    ssw = [h for f in fs for h in f["s"] if h[1] == "swing"]
    if ssw or rep.s_swings:
        w("")
        sl = [h[5] for h in ssw if h[5] > 0]
        row("summon swings", f"{len(ssw) / len(fs):.1f}/fight ({len(ssw)})",
            f"{rep.s_swings:.1f}/fight", _count_flag(len(ssw), len(fs), rep.s_swings))
        if ssw:
            row("  lands", f"{len(sl) / len(ssw):.0%} ({len(sl)}/{len(ssw)})",
                f"{rep.s_land:.0%}", _rate_flag(len(sl), len(ssw), rep.s_land))
        sx = rep.s_samples
        if sl:
            row("  damage per landed hit (mean)", f"{statistics.mean(sl):.0f}",
                f"{statistics.mean(sx):.0f}" if sx else "-", _mean_flag(sl, sx) if sx else "")
            row("  p10 / p50 / p90", f"{_pct(sl, .1)}/{_pct(sl, .5)}/{_pct(sl, .9)}",
                f"{_pct(sx, .1)}/{_pct(sx, .5)}/{_pct(sx, .9)}" if sx else "-")
        siv = []
        for f in fs:
            ts = [h[0] for h in f["s"] if h[1] == "swing"]
            if len(ts) >= 4:
                siv.append((ts[-1] - ts[0]) / (len(ts) - 1))
        if siv and rep.s_swing_s:
            exp = statistics.mean(rep.s_swing_s)
            row("  seconds per swing (mean of fights)", f"{statistics.mean(siv):.2f}",
                f"{exp:.2f}", "ok" if abs(statistics.mean(siv) - exp) < 0.15 * exp
                else "CHECK (walking stretches it)")
        msw_s = [h for f in fs for h in f["ms"] if h[1] == "swing"]
        row("monster swings at the summons", f"{len(msw_s) / len(fs):.1f}/fight ({len(msw_s)})",
            f"{rep.ms_swings:.1f}/fight", _count_flag(len(msw_s), len(fs), rep.ms_swings))
        sk_kills = sum(1 for f in fs if any(h[7] for h in f["s"]))
        if sk_kills:
            w(f"   the summon landed the killing blow in {sk_kills} of {len(fs)} fights")
    # kills
    ttk = [f["end"] - f["start"] + 1 for f in fs if f["killed"]]
    if ttk:
        w("")
        row("time to kill (median, s)", f"{statistics.median(ttk):.0f}",
            f"{statistics.median(rep.ttk):.1f}" if rep.ttk else "-",
            "(1 s log resolution; includes the walk-in)")
    w("")
    w("Per fight:")
    for i, f in enumerate(fs, 1):
        p_dmg = sum(h[5] for h in f["p"])
        taken = sum(h[5] for h in f["m"])
        sk_taken = f.get("m_skill", 0)
        s_dmg = sum(h[5] for h in f["s"])
        w(f"  {i:>2}. mob {f['mob']}: {f['end'] - f['start'] + 1:.0f} s, "
          f"{'killed' if f['killed'] else 'not killed'}, dealt {p_dmg}, taken {taken}"
          + (f" + {sk_taken} from skills" if sk_taken else "")
          + f", {len(f['p'])} hits out / {len(f['m'])} in"
          + (f"; summon dealt {s_dmg} in {len(f['s'])} hits, took {len(f['ms'])}"
             if f["s"] or f["ms"] else ""))
    return "\n".join(L)
