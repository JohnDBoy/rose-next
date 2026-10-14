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
RX_EFFECT = re.compile(TS + r".*SkillStatusTrace client effect: caster (\d+) target (\d+) "
                       r"skill (\d+) type \d+ success_bits (\d+)")


def _t(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()


def parse(path, since=None):
    """hits [(t, kind, attacker, defender, event, damage, hp_after, lethal)] in client
    ids, and `sk`: casts (server ids), regs / impacts (client caster, server target),
    effects (client ids, success_bits = which state slots landed)."""
    hits, seen = [], set()
    sk = dict(casts=[], regs=[], impacts=[], effects=[])
    t0 = _t(since) if since else None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "Trace" not in line:
                continue
            m = RX_SWING.match(line)
            if m:
                ts, a, d, ev, dmg, hp, leth = m.groups()
                t = _t(ts)
                key = (int(a), int(d), int(ev))
                if (not t0 or t >= t0) and key not in seen:
                    seen.add(key)
                    hits.append((t, "swing", int(a), int(d), int(ev), int(dmg), int(hp),
                                 int(leth)))
                continue
            m = RX_FLAT.match(line)
            if m:
                ts, a, d, ev, kind, dmg, hp = m.groups()
                t = _t(ts)
                key = (int(a), int(d), int(ev))
                if (not t0 or t >= t0) and key not in seen:
                    seen.add(key)
                    hits.append((t, "event", int(a), int(d), int(ev), int(dmg), int(hp),
                                 1 if int(hp) <= 0 or int(hp) == -30000 else 0))
                continue
            for name, rx in (("casts", RX_CAST), ("regs", RX_REG), ("impacts", RX_IMPACT),
                             ("effects", RX_EFFECT)):
                m = rx.match(line)
                if m:
                    t = _t(m.group(1))
                    if not t0 or t >= t0:
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
    # The server hands a dead monster's object id to the next spawn, so a kill closes
    # that id's fight and its next event opens a new one.
    out, gen = {}, {}
    for h in sorted(hits):
        t, kind, a, d, ev, dmg, hp, leth = h
        if a == player:
            mob = d
        elif d == player:
            mob = a
        else:
            continue
        key = (mob, gen.get(mob, 0))
        f = out.setdefault(key, dict(mob=mob, p=[], m=[], casts=[]))
        f["p" if a == player else "m"].append(h)
        if a == player and leth:
            gen[mob] = gen.get(mob, 0) + 1
    res = []
    for f in out.values():
        if not f["p"]:
            continue
        ev = sorted(f["p"] + f["m"])
        f["start"], f["end"] = ev[0][0], ev[-1][0]
        f["killed"] = any(h[7] for h in f["p"])
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


def compare(gd, sim, path, since=None, player=None, n=1000):
    hits, casts = parse(path, since)
    player, fs = fights(hits, casts, player, sim.make_player().max_hp)
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
    if iv and sim.p_attack_motion:
        exp = sim.p_attack_motion.duration_ms(sim.make_player().total_aspd / 100.0) / 1000
        row("  seconds per swing (mean of fights)", f"{statistics.mean(iv):.2f}", f"{exp:.2f}",
            "ok" if abs(statistics.mean(iv) - exp) < 0.15 * exp else "CHECK (skills or "
            "walking stretch it)")
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
    if mskill:
        row("  monster skill hits (not simulated)", len(mskill),
            f"{statistics.mean(mskill):.0f} avg", "excluded from the swing numbers")
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
    if miv and sim.m_attack_motion:
        exp = sim.m_attack_motion.duration_ms(sim.make_monster().total_aspd / 100.0) / 1000
        row("  seconds per swing (mean of fights)", f"{statistics.mean(miv):.2f}", f"{exp:.2f}",
            "ok" if abs(statistics.mean(miv) - exp) < 0.15 * exp else "CHECK (debuffs/stuns "
            "or walking stretch it)")
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
        m_dmg = sum(h[5] for h in f["m"])
        w(f"  {i:>2}. mob {f['mob']}: {f['end'] - f['start'] + 1:.0f} s, "
          f"{'killed' if f['killed'] else 'not killed'}, dealt {p_dmg}, taken {m_dmg}, "
          f"{len(f['p'])} hits out / {len(f['m'])} in")
    return "\n".join(L)
