"""Balance sweep: auto-built characters against the monsters the maps spawn at their level.

For each class and level, an auto-build (average gear, food) fights every monster that a
zone's REGEN lumps spawn within `band` levels of it. Results are grouped by the monster's
type mark -- LIST_NPC col 27, the icon beside its name (scripts/fix-monster-marks.py) --
so the report says whether the icons mean something in a fight: a Warrior should hit
harder than a Basic monster of its level, a Guard last longer, a star be a tougher fight.
Each monster is also compared with the median of the plain role monsters of its band
(marks 1-7, no star, crown or skull) -- how fix-monster-marks.py grades the stars.
"""
import importlib.util
import os
import statistics

from .autobuild import make_build
from .data import JOBS, SCRIPTS
from .sim import Simulation

MARKS = {
    1: "Basic", 2: "Guard", 3: "Fighter", 4: "Warrior", 5: "Ranger (bow)",
    6: "Hunter (crossbow)", 7: "Magician (staff)", 8: "Leader (bronze star)",
    9: "Captain (silver star)", 10: "Sub-boss (gold star)", 11: "King (crown)",
    12: "Jrose crown", 13: "Jrose star", 15: "Event", 16: "Elite / boss (skull)",
}
MARK_COL = 27                    # NPC_TYPE
GROUP = (11, 12, 16)             # crown and skull: group content, never solo
PLAIN = range(1, 8)              # Basic .. Magician: the reference of a band


def _audit_module():
    p = os.path.join(SCRIPTS, "audit-spawned-npcs.py")
    spec = importlib.util.spec_from_file_location("audit_spawned_npcs", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def spawned_monsters(gd):
    """{npc row: [zone names]} for every monster a zone's REGEN lumps spawn."""
    if getattr(gd, "_spawned", None) is None:
        a = _audit_module()
        zones = a.zone_rows(a.oro.Stb(a.oro.rel_path(a.DATA, a.ZONE_STB)), set())
        out = {}
        for zid, zname, folder in zones:
            found, problem = a.spawns_of_zone(folder, {})
            if problem:
                continue
            for i, wheres in found.items():
                if i > 0 and any(" regen " in w for w in wheres):
                    out.setdefault(i, []).append(zname or f"zone {zid}")
        gd._spawned = out
    return gd._spawned


def run(gd, jobs, levels, band=5, n=80, progress=None):
    """One record per (job, level, monster)."""
    spawned = spawned_monsters(gd)
    npc = gd.stb("LIST_NPC")
    rows = []
    for job in jobs:
        for lv in levels:
            b = make_build(gd, job, lv, gear="average")
            mobs = [r for r in spawned if abs(gd.npc(r).level - lv) <= band
                    and gd.npc(r).atk > 0 and gd.npc(r).hp_col > 0]
            for r in sorted(mobs):
                sim = Simulation(gd, b, r)
                rep = sim.run(n=n, seed=1)
                g = sim.grind(runs=2)
                rows.append(dict(
                    job=job, level=lv, npc=r, name=gd.npc(r).name, npc_level=gd.npc(r).level,
                    mark=npc.i(r, MARK_COL), zones=spawned[r][:2],
                    win=rep.win_rate,
                    ttk=statistics.median(rep.ttk) if rep.ttk else None,
                    dtps=rep.dtps, dps=rep.dps,
                    surv=statistics.median(rep.surv) if rep.surv else None,
                    surv_never=rep.surv_never * 2 > rep.surv_n,
                    hp_left=(statistics.median(rep.hp_left) / max(1, rep.max_hp)
                             if rep.hp_left else 0.0),
                    m_land=rep.m_land, p_land=rep.p_land,
                    kpm=g["kills_per_min"], food_hp=g["food_hp"], food_mp=g["food_mp"],
                    rest=g["rest_share"], grind_deaths=g["deaths"], grind_runs=g["runs"]))
                if progress:
                    progress(rows[-1])
    return rows


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def text(gd, rows):
    """The sweep as readable tables: by mark (relative to Basic), then the outliers."""
    L = []
    w = L.append
    groups = {}
    for x in rows:
        groups.setdefault((x["job"], x["level"]), []).append(x)
    for (job, lv), xs in sorted(groups.items()):
        basic = [x for x in xs if x["mark"] in PLAIN]
        b_ttk = _med(x["ttk"] for x in basic)
        b_dtps = _med(x["dtps"] for x in basic)
        w(f"== {JOBS.get(job, job)} {lv} (average gear, food) vs {len(xs)} spawned monsters "
          f"of level {lv - 5}-{lv + 5}; grinding = 10 min back to back, 5 s walks, sitting "
          f"when under 50% HP / 30% MP")
        w(f"   {'icon':<24}{'n':>3}{'win':>6}{'ttk s':>8}{'x plain':>8}"
          f"{'dmg in/s':>10}{'x plain':>8}{'hp left':>9}"
          f"{'kills/min':>10}{'food/kill':>10}{'rest':>6}{'deaths':>8}")
        by_mark = {}
        for x in xs:
            by_mark.setdefault(x["mark"], []).append(x)
        order = sorted(by_mark, key=lambda m: (m in GROUP, m))
        for mark in order:
            ms = by_mark[mark]
            if mark in GROUP and mark == next(m for m in order if m in GROUP):
                w("   -- group content (crown / skull: never meant solo) --")
            ttk = _med(x["ttk"] for x in ms)
            dtps = _med(x["dtps"] for x in ms)
            win = sum(x["win"] for x in ms) / len(ms)
            hp = _med(x["hp_left"] for x in ms)
            kpm = _med(x["kpm"] for x in ms)
            food = _med(x["food_hp"] + x["food_mp"] for x in ms)
            rest = _med(x["rest"] for x in ms)
            died = sum(x["grind_deaths"] for x in ms)
            runs = sum(x["grind_runs"] for x in ms)
            w(f"   {MARKS.get(mark, mark)!s:<24}{len(ms):>3}{win:>6.0%}"
              f"{(f'{ttk:.1f}' if ttk else '-'):>8}"
              f"{(f'{ttk / b_ttk:.2f}' if ttk and b_ttk else '-'):>8}"
              f"{dtps:>10.0f}{(f'{dtps / b_dtps:.2f}' if b_dtps else '-'):>8}"
              f"{(f'{hp:.0%}' if hp is not None else '-'):>9}"
              f"{kpm:>10.1f}{food:>10.2f}{rest:>6.0%}{f'{died}/{runs}':>8}")
        # the monsters furthest from their band's Basic median
        w("   outliers (vs the plain-role median of the band):")
        scored = []
        b_food = _med(x["food_hp"] + x["food_mp"] for x in basic)
        for x in xs:
            if x["mark"] in GROUP:
                continue
            if b_food and (x["food_hp"] + x["food_mp"]) > 0:
                scored.append(((x["food_hp"] + x["food_mp"]) / b_food, "food", x))
            if x["grind_deaths"]:
                scored.append((98, "dies", x))
            if b_ttk and x["ttk"]:
                scored.append((x["ttk"] / b_ttk, "ttk", x))
            if b_dtps and x["dtps"]:
                scored.append((x["dtps"] / b_dtps, "dmg", x))
            if x["win"] < 0.5:
                scored.append((99, "loses", x))
        seen = set()
        for k, what, x in sorted(scored, key=lambda s: -abs(s[0] - 1) if s[0] < 98 else -s[0]):
            if x["npc"] in seen or (0.6 < k < 1.67 and what not in ("loses", "dies")):
                continue
            seen.add(x["npc"])
            w(f"     {x['npc']:>5} {x['name'][:24]:<24} lv{x['npc_level']:>3} "
              f"{MARKS.get(x['mark'], x['mark'])!s:<22} "
              + (f"wins only {x['win']:.0%}" if what == "loses" else
                 f"dies grinding it ({x['grind_deaths']}/{x['grind_runs']} runs, "
                 f"{x['food_hp'] + x['food_mp']:.1f} food/kill)" if what == "dies" else
                 f"{dict(ttk='time to kill', dmg='damage taken', food='food per kill')[what]} "
                 f"x{k:.1f}")
              + f"  ({', '.join(x['zones'])})")
            if len(seen) >= 8:
                break
        w("")
    return "\n".join(L)
