### [God] Hebarn Is A Talk-Then-Fight Boss (Oasis Shrine, zone 80)

`scripts/import-hebarn.py` (`--dry-run`, `--verify`); its docstring holds the kit, stats
and loot. TALK NPC 4147 and BOSS 4148 share one model. QP401.QSD `Hebarn-Challenge`
takes the offering, **hides TALK (REWD_034) and spawns BOSS at its feet (REWD_008
btWho 1)**; BOSS's AI (`HEBARN.AIP`) fires `Hebarn-Return` (REWD_034 show) on death or
after 15 min idle. Return the NPC from the AI's dead pattern, never LIST_NPC col 41:
that column asks the killer's *client* to fire the event.
