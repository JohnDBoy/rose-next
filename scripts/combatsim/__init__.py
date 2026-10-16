"""Combat simulator: a character build against one monster, using the server's formulas.

    from combatsim import GameData, Build, Simulation
    gd = GameData()
    sim = Simulation(gd, Build.load("scripts/combatsim/builds/test-champion-150.json"), npc_row=2684)
    print(sim.run(n=300).text())

Modules: data (tables, motions, server.toml), formulas (calculation.cpp), player (the
stat block: items, refines, gems, passives), fight (the tick loop), sim (setup, Monte
Carlo, report), autobuild (starting builds). CLI: scripts/combat-sim.py.
"""
from .data import GameData, find_rows  # noqa: F401
from .player import Build, StatBlock  # noqa: F401
from .sim import ASSUMPTIONS, PLAY, Report, Simulation  # noqa: F401
