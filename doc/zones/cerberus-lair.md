### The Cerberus Lair Is A Drawn Instance (zone 49, built and validated in game 2026-10-08)

tsuki's Cerberus Lair as zone 49 (`scripts/import-cerberus.py`, stages 1-4) plus a
game-server controller (`src/sho_gameserver/src/cerberus_lair.*`); design and status
in [doc/cerberus-lair-brief.md](../cerberus-lair-brief.md). Every hour, on the
hour, [Arumic Seal Keeper] Yelena (NPC 4149, at the Arumic temple in Arumic Valley)
opens registration for 10 minutes; at :10 up to five level-140+ registrants are
drawn, charged 100,000 zuly on arrival, partied and sent in; two packs of Hellhound
Whelps (2680) and the Warden of the Seal (2681, Seal Burst 7023) stand in the way,
an **ice wall** seals the crater where Cerberus sleeps in view, and the Warden's
death drops the wall and makes Cerberus hostile; it wakes (2683 -> 2682) by AI
action 9 when approached or hit; its death plus a minute, or 20
minutes, evicts everyone; there is no way out before that (no gate, save-point revive
and warp scrolls refused in the lair: `CCerberusLair::IsLair`). Loot is mostly items
nothing else drops (importer docstring, "Loot"). Test with
`/cerberus open|draw|status|reset` and `/cerberus wall up|down`.

Things that will bite:

- **The controller owns every monster, not a regen point** (`CRegenPOINT::Reset`
  cannot force a respawn). The lair's IFO has no spawn point; the C++ spawns the
  whelps, the Warden and the sleeper when a run starts (`RUN_SPAWNS`, `CRATER_X/Y`);
  between runs the lair is kept empty.
- **Seal Burst draws its circle on the ground** while the Warden winds it up (2026-10-18,
  awaiting the in-game test): `LIST_SKILL` col 83 = 1 (`SK_TELEGRAPH` in the importer),
  drawn by the client (`src/client/groundtelegraph.h`). Any monster skill gets the same by
  setting that cell. The importer's skill builders keep the `LMobSkill<row>` name keys
  `name-monster-skills-players.py` gave them (col 86), so stage 2 no longer reverts them.
- **The sleeper is on `TEAMNO_NPC` until the seal breaks.** `Is_ALLIED` makes team 1
  allied with everyone (same team, or a team product <= 100), so nothing can target
  it and its "enemies near" wake never fires -- a Hawk Shot reaches the crater from
  the ridge, a hit wakes it, and monsters do not collide with the wall. There is no
  live team-change packet: the seal break removes it silently (`Sub_DIRECT` +
  `delete`, the GM `npc DEL` pattern) and spawns a `TEAMNO_MOB` sleeper.
- **The ice wall is `scripts/cerberus-wall.py`'s** (design and log:
  [doc/cerberus-ice-wall.md](../cerberus-ice-wall.md)): the "crater rim" is a
  walkable terrain ridge, open over the top and around its south end, so the script
  rasterises the lair's real collision (`mapgen/catalogue.Footprints`), lays
  invisible panels along the ridge and single-spike ice crystals (`mauice05/07`;
  the cluster models have see-through holes) across the southern gap, and refuses
  to emit `ICE_WALL` unless a flood fill from the start still reaches the Warden and
  no longer reaches Cerberus. Re-run `--emit` after any change to the lair's objects.
- **Constants live in both** the importer and `cerberus_lair.cpp` (zone, NPC, rows,
  landing event, trigger name, fee, crater). Change them together.
