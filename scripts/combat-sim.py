"""Combat simulator: how a character build fares against a monster, by the server's formulas.

Every formula is ported from the server source (src/common/calculation.cpp, the
game server's cuserdata.cpp / cobjavt.cpp / cobjchar.cpp / status_effects.cpp) with a
file:line reference in scripts/combatsim/. What the simulator decides by itself is
printed under "Assumptions" with every report.

Usage
-----
    python scripts/combat-sim.py run BUILD.json --mob 1234          # NPC row
    python scripts/combat-sim.py run BUILD.json --mob "Grizzly"     # name search
    python scripts/combat-sim.py run BUILD.json --mob 1234 --fix-passive-bugs
    python scripts/combat-sim.py stats BUILD.json                   # stat block only
    python scripts/combat-sim.py new --job 221 --level 180 -o scripts/combatsim/builds/my-mage.json
    python scripts/combat-sim.py find npc "Grizzly"                 # npc|weapon|skill|...
    python scripts/combat-sim.py skills --job 221                   # rotation candidates
    python scripts/combat-sim.py ai --mob 1403                      # what a monster's AI does
    python scripts/combat-sim.py sweep --job 122 221 --level 50 100   # balance sweep by icon

Builds are JSON (see scripts/combatsim/builds/); the Rose Dev Studio "Combat
Simulator" tab edits the same files.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from combatsim import Build, GameData, Simulation, find_rows  # noqa: E402
from combatsim.autobuild import make_build, skill_choices  # noqa: E402

FIND_TABLES = dict(npc="LIST_NPC", weapon="LIST_WEAPON", subwpn="LIST_SUBWPN",
                   cap="LIST_CAP", body="LIST_BODY", arms="LIST_ARMS", foot="LIST_FOOT",
                   back="LIST_BACK", jewel="LIST_JEWEL", gem="LIST_JEMITEM",
                   skill="LIST_SKILL", useitem="LIST_USEITEM", natural="LIST_NATURAL")


def resolve_mob(gd, spec):
    if str(spec).isdigit():
        return int(spec)
    hits = find_rows(gd, "LIST_NPC", spec, limit=20)
    hits = [(r, n) for r, n in hits if gd.npc(r).atk > 0]
    if not hits:
        raise SystemExit(f"no monster matches {spec!r}")
    if len(hits) > 1:
        print(f"{len(hits)} monsters match {spec!r}; using the first:", file=sys.stderr)
        for r, n in hits[:10]:
            print(f"  {r:>5}  {n}  (level {gd.npc(r).level})", file=sys.stderr)
    return hits[0][0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data folder (default: repo data/)")
    ap.add_argument("--server-toml", help="server.toml for the [game] base_* bonuses")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="simulate a build against a monster")
    r.add_argument("build")
    r.add_argument("--mob", required=True, help="LIST_NPC row or name")
    r.add_argument("-n", type=int, default=300, help="fights to simulate (default 300)")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--max-seconds", type=int, default=600)
    r.add_argument("--fix-passive-bugs", action="store_true",
                   help="show the stats the passives were meant to give")
    r.add_argument("--potions", action="store_true", help="force potions on")

    s = sub.add_parser("stats", help="print the build's stat block")
    s.add_argument("build")
    s.add_argument("--fix-passive-bugs", action="store_true")

    nb = sub.add_parser("new", help="write an auto-generated starting build")
    nb.add_argument("--job", type=int, required=True)
    nb.add_argument("--level", type=int, required=True)
    nb.add_argument("--female", action="store_true")
    nb.add_argument("--gear", choices=("average", "best"), default="average",
                    help="average: what a typical player runs (default); best: best in slot")
    nb.add_argument("-o", "--out", required=True)

    f = sub.add_parser("find", help="search a table by in-game name")
    f.add_argument("table", choices=sorted(FIND_TABLES))
    f.add_argument("query")

    k = sub.add_parser("skills", help="list a job's non-passive skills (top ranks)")
    k.add_argument("--job", type=int, required=True)

    sd = sub.add_parser("seed", help="write a build into the game DB as a GM character")
    sd.add_argument("build")
    sd.add_argument("--account", required=True)
    sd.add_argument("--password", required=True)
    sd.add_argument("--name", required=True, help="character name (3-16 letters/digits)")
    sd.add_argument("--access", type=int, default=2048, help="access_level (2048 = GM)")
    sd.add_argument("--replace", action="store_true", help="delete a character of that name first")
    sd.add_argument("--dry-run", action="store_true", help="print the SQL, write nothing")

    ai = sub.add_parser("ai", help="print a monster's AI file as readable rules")
    ai.add_argument("--mob", required=True, help="LIST_NPC row or name")

    sw = sub.add_parser("sweep", help="auto-builds vs the spawned monsters of their level, "
                                      "grouped by the monster's icon")
    sw.add_argument("--job", type=int, nargs="+", required=True)
    sw.add_argument("--level", type=int, nargs="+", required=True)
    sw.add_argument("--band", type=int, default=5, help="monster levels within +/- this")
    sw.add_argument("-n", type=int, default=80, help="fights per monster")
    sw.add_argument("--json", help="also write every result here")

    sc = sub.add_parser("scenarios", help="predictions for the in-game test scenarios")
    sc.add_argument("-n", type=int, default=500)
    ct = sub.add_parser("compare-trace", help="compare a client CombatTrace log with the sim")
    ct.add_argument("log", help="client-<date>.log with [LOG] LEVEL=debug")
    ct.add_argument("--scenario", type=int, help="test scenario id (scenarios.json)")
    ct.add_argument("--build", help="or: a build file ...")
    ct.add_argument("--mob", help="... and a monster")
    ct.add_argument("--since", help="ignore lines before 'YYYY-MM-DD HH:MM:SS' (log time is UTC)")
    ct.add_argument("--exclude", type=int, nargs="*", default=[],
                    help="fight numbers (as listed under 'Per fight') to leave out")
    ct.add_argument("--until", help="ignore lines after 'YYYY-MM-DD HH:MM:SS'")
    ct.add_argument("--player", type=int, help="the player's object id, if guessed wrong")
    ss = sub.add_parser("seed-scenarios", help="seed every test scenario's GM character")
    ss.add_argument("--password", required=True)
    ss.add_argument("--replace", action="store_true")
    ss.add_argument("--dry-run", action="store_true")

    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gd = GameData(a.data, a.server_toml)

    if a.cmd == "run":
        b = Build.load(a.build)
        if a.potions:
            b.potions["enabled"] = True
        sim = Simulation(gd, b, resolve_mob(gd, a.mob), a.fix_passive_bugs)
        print(sim.run(n=a.n, seed=a.seed, max_seconds=a.max_seconds).text())
    elif a.cmd == "stats":
        b = Build.load(a.build)
        sim = Simulation(gd, b, 1, a.fix_passive_bugs)
        p = sim.make_player()
        st = sim.stats
        print(f"{b.name}: STR {st.cur['STR']} DEX {st.cur['DEX']} INT {st.cur['INT']} "
              f"CON {st.cur['CON']} CHA {st.cur['CHARM']} SEN {st.cur['SENSE']}")
        print(f"HP {p.max_hp} MP {p.max_mp} ATK {p.total_atk} HIT {p.total_hit} "
              f"DEF {p.get_def} RES {p.get_res} AVOID {p.get_avoid} CRIT {p.get_crit} "
              f"ASPD {p.total_aspd}")
        print(f"(before server.toml bases: ATK {st.attack_power} HIT {st.hit_rate} "
              f"ASPD {st.attack_speed})")
        for n in sim.notes:
            print(f"! {n}")
    elif a.cmd == "new":
        b = make_build(gd, a.job, a.level, a.female, a.gear)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        b.save(a.out)
        print(f"wrote {a.out}")
    elif a.cmd == "find":
        for row, name in find_rows(gd, FIND_TABLES[a.table], a.query, limit=60):
            extra = ""
            if a.table == "npc":
                n = gd.npc(row)
                extra = f"  level {n.level}  HP {n.level * n.hp_col}"
            print(f"{row:>6}  {name}{extra}")
    elif a.cmd == "seed":
        from combatsim.seed import seed
        sql, summary = seed(gd, Build.load(a.build), a.account, a.password, a.name, a.access,
                            a.replace, a.dry_run, a.server_toml)
        print(sql or f"seeded: {summary}")
    elif a.cmd in ("scenarios", "seed-scenarios"):
        import json
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combatsim")
        scen = json.load(open(os.path.join(here, "scenarios.json"), encoding="utf-8"))
        for s in scen["scenarios"]:
            b = Build.load(os.path.join(here, s["build"]))
            if a.cmd == "seed-scenarios":
                from combatsim.seed import seed
                sql, summary = seed(gd, b, s["account"], a.password, s["character"], 2048,
                                    a.replace, a.dry_run, a.server_toml)
                print(sql or f"scenario {s['id']}: seeded {s['account']} / {s['character']} "
                      f"({summary['items']} items, {summary['skills']} skills, "
                      f"hotbar {summary['hotbar']})")
                continue
            sim = Simulation(gd, b, s["mob"])
            print("#" * 78)
            print(f"# Scenario {s['id']}: {s['title']}")
            print(f"# login {s['account']} / character {s['character']}; spawn: /mon {s['mob']} 1")
            print(f"# how to play: {s['play']}")
            print("#" * 78)
            print(sim.run(n=a.n, seed=1).text().split("\nAssumptions")[0])
            print()
    elif a.cmd == "compare-trace":
        import json
        from combatsim.trace import compare
        if a.scenario:
            here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combatsim")
            scen = json.load(open(os.path.join(here, "scenarios.json"), encoding="utf-8"))
            s = next(x for x in scen["scenarios"] if x["id"] == a.scenario)
            b, mob = Build.load(os.path.join(here, s["build"])), s["mob"]
        elif a.build and a.mob:
            b, mob = Build.load(a.build), resolve_mob(gd, a.mob)
        else:
            raise SystemExit("give --scenario N, or --build and --mob")
        print(compare(gd, Simulation(gd, b, mob), a.log, a.since, a.player, until=a.until,
                      exclude=a.exclude))
    elif a.cmd == "ai":
        from combatsim import ai as AI
        row = resolve_mob(gd, a.mob)
        n = gd.npc(row)
        f = AI.load_for_npc(gd, row)
        print(f"{n.name} (NPC {row}, level {n.level}): "
              + (gd.stb("FILE_AI").s(n.ai, 0).strip() if f else "no AI file"))
        if f:
            print("\n".join(AI.describe(f, gd)))
            for r_ in sorted({x[0] for x in f.skills(AI.DAMAGED) + f.skills(AI.STOP)}):
                sk = gd.skill(r_)
                print(f"skill {r_} {sk.name}: type {sk.type}, damage type {sk.damage_type}, "
                      f"power {sk.power}, action mode {sk.action_mode}, range {sk.distance}, "
                      f"area {sk.scope}, states {[x for x in sk.states if x]}")
    elif a.cmd == "sweep":
        import json
        from combatsim import sweep
        rows = sweep.run(gd, a.job, a.level, a.band, a.n,
                         progress=lambda r: print(f"  {r['job']} {r['level']} vs {r['name']}",
                                                  file=sys.stderr))
        if a.json:
            json.dump(rows, open(a.json, "w", encoding="utf-8"), indent=1)
        print(sweep.text(gd, rows))
    elif a.cmd == "skills":
        for row, name, t in skill_choices(gd, a.job):
            sk = gd.skill(row)
            print(f"{row:>6}  {name:<28} type {t:>2}  power {sk.power:>4}  "
                  f"lv {sk.level}  cd {sk.reload_ms / 1000:.1f}s")


if __name__ == "__main__":
    main()
