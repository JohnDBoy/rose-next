# Pathfinding and Z support: implementation plan

Status: plan only, nothing built (2026-10-28). It was put together from:
- a seven-report research sweep;
- three competing designs (our own layered grid, Recast/Detour, and a value-first version), each scored by three reviewers;
- two fact-checking passes against the code and data.

The full research is archived locally in `build/nav-research/` (not in git): `reports/` holds the seven reports, `design/` the proposals, verdicts and fact-checks, and `scripts/` the measurement scripts.

Path prefixes: `S/` = `src/sho_gameserver/src/`, `C/` = `src/client/`, `E/` = `src/engine/src/`. Other paths are from the repo root.

## 1. Executive summary

**What we build.** An offline Python bake (over `scripts/rosefmt` and `scripts/mapgen`) turns each zone's terrain and collision meshes into `<ZONFOLDER>.lnav`: a **layered walk grid with 1 m cells**, each cell listing the floors ("spans") at that X/Y. The game server uses it three ways:
- as a **height oracle**;
- for a **vertical band** on AoE and aggro (later, attack range);
- as the **A\* graph** for monsters and summons.

A zone without a file behaves as today.

**Key choices** (the alternatives are in §3.0):
1. **Data:** our own layered grid; Recast/Detour is the fallback.
2. **Floors:** slope plus reachability from seeds, never the collision flag.
3. **Z:** every vertical verdict uses the Z the client draws.
4. **AoE:** the 2D shape plus a flared band, |dz| ≤ 5 m + 0.7·d. A sphere measured worse: it loses 6–7% of hillside hits, and excludes fewer cliffs than a band that loses 1–2.4%.
5. **Paths:** straight first, A\* only when blocked, with waypoints sent as target-less `CharacterMove`s.
6. **Players:** never pathed; `m_nPosZ` untouched.
7. **Safety:** a switch and a live GM toggle for every behaviour, rolled out per zone.

| Phase | Ships | Client? | Player notices |
|---|---|---|---|
| 0 | Meters and a waypoint presentation probe | no | nothing |
| 1 | Bug fixes: AoE scan, Z reads (MOV docs only; MOV is retired in Phase 4) | no | AoE hits the whole pack every time |
| 2 | Bake; the server loads it and tracks Z | no | nothing (`/nav` GM tool) |
| 3 | Vertical band and roof-spawn rejection | no | **AoE from a bridge or cliff stops hitting monsters far below; monsters below stop aggroing; no monsters on Muris/Zant roofs** |
| 4 | Idle moves and spawns respect walls | no | idle monsters stop walking through houses, trees and cave walls; nothing spawns in rock or outside the Goblin tunnels |
| 5 | Pathfinding | no | **monsters and summons go around obstacles** |
| 6 | The client draws monsters on the server's floor | lockstep | monsters under a bridge stay under it; none on invisible wall tops |
| 7 | 3D attack/cast range, aiming onto decks (optional) | lockstep | attacks respect floors; ground AoE can target a deck |

**Cost (estimates):**
- **Code:** about 4,500 lines of C++ (about 700 of them client-side) plus 1,500 lines of Python.
- **Memory:** 45–55 MB of nav data (bound 75 MB) plus at most 27 MB of search scratch, in a server that is not large-address-aware.

## 2. What the research found

The numbers come from read-only scripts over `rosefmt` (see the Appendix).

**Server movement**
- **2D, straight lines, no clamp.** The server ticks at 10 Hz (`S/gs_threadzone.cpp:93-94`) and moves objects with one line, `m_PosCUR += m_MoveVEC * dt`. There is no walkability test and no arrival clamp (`S/cobjchar.cpp:2074-2091`). Arrival is tested after the step (`S/common/cobjai.cpp:618-633`), so a move overshoots by up to one step: about 33–85 cm at 100 ms for run speeds of 330–850 cm/s, about half that on average.
- **Object work stretches the tick.** The zone waits out 100 ms minus its pre-work, and only *then* runs every object's `Proc` (`S/gs_threadzone.cpp:175-180, 187-218`). Any time the planner spends lengthens the tick, and the uncapped `dwPassTIME` then lengthens every step. None of this is instrumented.
- **Scale.** About 67 zone threads run in one process. Their 6,103 regen points have summed caps of 13,868 monsters; Sikuku alone has 2,118 points with cap 1.
  - That is the cap sum, not a simulated population: the real count can exceed caps where `tacticPoint` is low (`scripts/CLAUDE.md`). Phase 0 counts live monsters.
  - The process is **not large-address-aware** (PE flags 0x102; no vcxproj sets it).
- **Thin walkability checks.** `IsMovablePOS` checks only the destination cell of `SetCMD_MOVE2D` moves (`S/cobjchar.cpp:921-935`), and it treats an off-grid X as walkable (`S/zonefile.h:131-136`). Chases, players, CTRL+click and spawns bypass it entirely.
- **No Z anywhere.**
  - Spawns are uniform in a ±range square with no checks (`S/gs_threadzone.cpp:761-786`).
  - IFO Z (regen, NPC, event objects) is skipped unread with an `fseek` (`S/zonefile.cpp:163`). ZON event-point Z is read and discarded (`:501-504`), and `tagEVENTPOS` has no Z (`S/zonefile.h:12-16`).
  - `.HIM` is never opened, and monster `m_nPosZ` is always 0 (`S/cobjnpc.cpp:71`).

**MOV mirror.** `LoadMOV` puts file row 0 at the tile's south edge (`S/zonefile.cpp:310-321`), but the data is north-first, like HIM. With the rows flipped:
- regen points on blocked cells fall from 85/736 to 0/736;
- the share of LZ01 wall cells that are blocked rises from 55% to 100%.

The proof is statistical; nobody has checked it in game yet. The same south-first reading is written into:
- `scripts/rosefmt/chunk.py:6`;
- `docs/mapgen/FORMATS.md:418-426`;
- `xadet/rose-online-map-editor/Map Editor/Engine/FileManager/Map/MOV.cs:5`, with its tests in `xadet/rose-online-map-editor/tests/MovementTests.cs`.

**MOV coverage is thin.**
- Only 18 zones have painted MOVs.
- A 19th, ODRP01, has 2 stray blocked cells and is counted with the 32 effectively all-zero zones (Shady Jungle, Sikuku, Eldeon…).
- 16 zones ship none.

The painted cells are brush bands 10–15 m wide along walls. **MOV cannot be the nav source.**

**What the client draws** (everything else has to fit around this)
- **The client re-snaps monsters and NPCs to `GetHeightTop` every frame.**
  - `GetHeightTop` = max(terrain, highest hit on any non-NOTMOVEABLE colliding node) (`C/cobjchar_collision.cpp:321-358`, `E/zz_interface.cpp:9067-9152`).
  - It covers objects in the frustum, and those within 40 m of the avatar (`C/cobjchar.cpp:5776-5823`). Others keep their last Z.
  - It samples at the model's centre of mass, not the server X/Y.
  - Spawns use the same rule via `DropFromSky` (`C/cobjchar.cpp:5150-5158`).
  - Any server Z for a monster is ignored.
- **The local avatar uses a relative rule:** the highest surface ≤ foot + 135 cm, no climbing at 54° or steeper, never below the terrain (`C/cobjchar_collision.cpp:1355-1469, 1525`). Unlike monsters, it **keeps flag-12 nodes** (:617-622). Its ray test is two-sided.
- **Monsters collide with nothing on the client** except 116 tree cylinders in imported tables. Server X/Y waypoints therefore need no client change.

**Where the layers really are**
- **Today's roof spawns happen in towns, not caves:**
  - Muris: 16.5% of spawn samples (9 of 37 points; one at 100%, up to +53 m);
  - Zant: 3.6%;
  - Fossil Sanctuary: 13 of 123 points;
  - Sikuku: 11 of 2,118 points.

  Goblin Cave and Shady Jungle are at 0%, because their ceilings and tree crowns are flag 12. Counting flag-12 surfaces as floors would put 40% of Goblin B1 spawn samples on ceilings.
- **Bridges are common:** 21 zones have a walk-on bridge at least 5 m up. Examples: Shady `dari` (deck +62–73 m), Zant +47 m, Eucar +45 m, Gorge +44 m, Arumic +37 m, Goblin B1 `domdari` (about +108 m), B2 +27 m, Ulverick +22 m.
- **Lump-11 collision panels are upright walls that are also walk-on (flag 4).**
  - Of 3,125 panels, 31 pass the bake's cos 54° surface test (17 JD04, 7 LP05, 5 VALLEY002, 1 ODGR01, 1 TOWN). The rest are walls.
  - Shady Jungle has 66 panels. 37 of them are 78.8 m tall and 4.5 m thick, centred on the ground, so a monster standing inside one is drawn about 39 m up. The others are 7–60 m tall.
  - The panels account for 27,619 m² of that zone's 31,519 m² "overhang".
  - The Cerberus lair's 7 panels may explain the hounds that were "heard, never seen".
  - Do not reflag `LIST_DECO_SPECIAL` object 2 to 12: the flat panels must stay walk-on.
- **Shady Jungle is mostly cliffs.** 81 of 392 regen points have terrain more than 10 m higher within 20 m. Regen centres are 187–200 m from the bridge.
- **Goblin Cave.** The floor is terrain. Walls and ceilings are single-sided, down-facing flag-12 meshes. B1's chamber stacks four surfaces at one X/Y. B3 has two regen points on its altar (+8.4 m and +8.8 m). Spawn squares spill 4–19% outside the tunnels.
- **Regen Z is a good layer hint** (93.9% within 50 cm of the terrain). The exceptions are 195 z = 0 points off the terrain: 190 written by importers (Desolate Cemetery 113, Spire Village 77), 4 in Muris and 1 in Ulverick.

**Range and AoE**
- **One test per scan.** Every circular scan is decided at `S/gs_threadzone.cpp:991`. All area damage goes through `Skill_DamageToAROUND` (`S/cobjchar.cpp:1628-1735`), which never re-tests plain circles.
- **The scan iterator is shared per zone and is not re-entrant** (`S/gs_threadzone.h:78-83`). The chain `Apply_DAMAGE` → `Do_DamagedAI` (`S/cobjchar.cpp:1223`) → `AI_Check` → COND02 → `FindFirstCHAR` overwrites the outer AoE scan. 238 of 541 AIP files scan on DAMAGED. This was traced in code, not observed in game.
- **Reach is capped by sector hysteresis:** 0.8·s around a point and 0.6·s around a character (40 m and 30 m in 46 zones), while skill radii reach 50 m (median 11.6 m).

**Protocol**
- **Waypoints must be target-less `CharacterMove` packets (74 bytes).**
  - Anything that carries a target makes the client home on it. `CharacterMove` goes through `C/network/cnetwork.cpp:1053-1077` into `CObjAI::SetCMD_MOVE` (`C/common/cobjai.cpp:855-862`); spawn packets go through `Recv_tag_ADD_CHAR` (`C/network/recvpacket.cpp:1134-1163`).
  - Both builders always write the target (`S/network.cpp:97`, `:118`).
- **The client never speeds up to catch up** (`C/cobjchar.cpp:142-206`).
  - Each corner costs either a 0–100 ms stop or a cut.
  - A non-player that falls more than 1 s of walking behind the server snaps forward, the known "position snapped forward" teleport (`:168-195`).
- **Monster and NPC spawn packets carry no Z.** Their variable-length tail forces any new field into the fixed part (`net_prototype.h:898-910`).
  - `gsv_AVT_CHAR.m_nPosZ` exists but is never written.
  - `Vec3.z` is always 0.
- **Player Z is unreliable:** `CANTMOVE` reads the wrong struct (`S/gs_user.cpp:2836`), and the client never writes the `JOIN_ZONE` Z.
- **`m_nPosZ` is broadcast to other clients** (`S/cobjchar.cpp:318`, `C/network/recvpacket.cpp:1885`).

**Tooling**
- **How data reaches a production server is not recorded in the repo.**
  - The repo's server dist script, `scripts/server-data.ps1:11-14`, copies only `*.him/*.mov/*.ifo/*.zon`, so no map meshes.
  - Its only caller is `scripts/dist.ps1:74`, which reads `bin/assets`. That folder does not exist in this checkout.
  - The game server loads from `server.toml`'s `data_dir`; dev servers read `data/` directly.
  - The bake therefore has to be a server-side artefact next to the ZON. Decision 14 asks how it gets deployed.
- The config FFI reads only ints and strings (`src/common-lib/src/ffi/toml.rs:36, 68`).

## 3. Design

### 3.0 Where the proposals disagreed

| Question | Chosen | Over | Why |
|---|---|---|---|
| Nav representation | layered 1 m grid | Recast/Detour | Recast's RAM (60–250 MB, unmeasured) is the largest risk in a non-LAA server, and its bake needs two languages. Floor classification is custom either way. Recast stays the fallback |
| Go/no-go experiment | `/nav trail` probe (Phase 0) | A\* on the painted MOV | MOV is unfit as nav data, and costs measured on 5 m cells do not carry over to 1 m. The probe tests corner presentation, the real risk, with no data at all |
| Monster Z before the client change | visual top (what is drawn) | nav continuity | keeps the server consistent with the screen |
| AoE vertical rule | flared band, plus an opt-in same-surface check | cylinder + surface check; Recast's gate; sphere | measured (§3.4). The surface check must ignore walls, or trees on a hillside exclude targets |
| Z on the wire | `gsv_MOB_CHAR` | `tag_ADD_CHAR` | `tag_ADD_CHAR` is also the base of `gsv_AVT_CHAR`, so player spawn packets would change too |
| Player server Z | new `m_nNavZ` | `m_nPosZ` | `m_nPosZ` is broadcast to other clients |
| Path state | pointer on the server `CObjCHAR` | side table | the class is server-only; a side table risks object-index reuse |
| Monster attack band | Phase 7, with the player band | Phase 2 or 4 | a band on one side only creates safe spots |
| Unreached floors | kept as Z-only (up-facing only) | dropped | players can stand on them; ceilings are still dropped to bound RAM |
| Whose view of a player's Z | the owner's (their own client keeps flag-12 floors) | observers' (they skip flag 12, `C/cobjchar_collision.cpp:625-633`) | a monster AoE is judged on where the targeted player sees themselves |
| Summon follow before A\* | straight fallback | line gate only | a summon must never be stranded |
| Spawn spread | square, as today | reachable circle | no visible change to how spawns spread |
| Bake versions | one bake, consumers staged | heights first, walls later | one body test covers both walls and headroom |

### 3.1 Nav data and bake

**Cells.** 1 m cells, each holding sorted spans `{int16 z_cm, u8 flags, u8 clearance}`.
- 50 cm cells would cost about 160–200 MB.
- 2.5 m cells leak one-cell faces.
- At 1 m, the avatar's 135 cm step equals a 53.5° slope on orthogonal links, which matches its 54° rule. Diagonals keep the 135 cm limit (about 44°) and need both side links.

**Bake.** The CLI is `scripts/nav-bake.py`, the logic lives in `scripts/mapgen/navbake.py`, and the codec is `scripts/rosefmt/lnav.py`, with a round-trip test.
- Game files are read only through existing codecs: LIST_ZONE columns 1/11/12, ZON event points, the stitched HIM (`prefab._zone_field`), IFO lumps 1/3 via `relight.Zone.placed()`, lump 11 as `LIST_DECO_SPECIAL` object 2, and water as a flag.
- **New readers are needed** for lump 10 (warp gates) and lump 12 (event objects). Each applies the same `objlight.client_accepts` filter:
  - warp gates are `LIST_DECO_SPECIAL.ZSC` object 1, collision 4, so walk-on (`C/object.cpp:588-620`);
  - event objects come from the event ZSC the client loads into `m_ModelEvent`.

  `relight.Zone.placed()` covers lumps 1 and 3 only (`scripts/mapgen/relight.py:283-297`), and `catalogue.Footprints` knows only the OBJECT, CNST and COLLISION ZSCs.
- ZSC parts with collision ≠ 0 go through `catalogue._to_model` (following the parent chain), together with their cylinders and ZMS triangles.
- MORPH is reported but not used.
- The server reads only our `.lnav`.

**Passes:**
1. **Terrain span** per cell: bilinear HIM, as in `CMAP::GetHEIGHT` (`C/io_terrain.cpp:1947-1957`) over `GetHeightsByCoordinates` (`:2890-2915`). It always exists.
2. **Classify each colliding triangle by its normal, two-sided:** a surface if |n_z| ≥ cos 54°, otherwise a wall. Flags do not decide.
3. **Rasterise surfaces** (at 33 cm or finer) and cluster each cell's samples by z; a gap over 50 cm starts a new span.
4. **Body test.** A span is blocked if a sample of another surface or wall lies 30–180 cm above it. This catches walls, low slabs, rock interiors and panel footprints. HEIGHTONLY parts (flag 36, stairs) never block; cylinders block discs.
5. **Links** join walkable neighbouring spans whose |Δz| ≤ 135 cm.
6. **Flood** from seeds: event points, regen centres, NPCs and warps, plus `scripts/nav/seeds/<ZONFOLDER>.json` (in git).
   - A seed snaps to the span nearest its authored Z within 3 m, otherwise to the terrain. This covers the 190 z = 0 points.
   - Reached spans get a component id.
   - Unreached **up-facing** spans are kept as Z-only. A player may stand there after a fall; paths and spawns ignore them.
   - Unreached down-facing spans (cave ceilings) are dropped and only provide headroom.
7. **Clearance class:** 1 = beside an obstacle, 2 = at least 1.5 m clear, 3 = at least 2.5 m. Ledges count as obstacles.
8. **Visual top and HAZARD.** For each cell, store where today's client draws a monster, using a `GetHeightTop` replica: an up-ray from z = 0 taking the farthest hit, otherwise a down-ray taking the nearest, over non-NOTMOVEABLE nodes only. It is stored sparsely, and a span whose visual top is more than 3 m above it is flagged **HAZARD**.

   The replica is close but not exact:
   - MORPH objects and runtime `GSV_ZONE_OBJECTS` are in the client's scene but not in the bake;
   - the client samples at a model's centre of mass, so large models at a ledge or deck edge can resolve a different layer than the server X/Y.

   Expect small drift there.
9. **Regen anchors:** each regen point's resolved span and Z.

**Result:**
- Goblin ceilings only supply headroom.
- Crowns and panel tops are unreachable.
- A roof counts only if stairs reach it.
- The `dari` deck, B1's bridges and the B3 altar become second layers.

**File.** `<ZONFOLDER>.lnav` sits next to the ZON with a **lowercase** extension, because the `pack.rs` globs are case-sensitive (`scripts/pack.ps1:50-61`).
- **Header:** version, bake parameters, CRC32 of each input HIM/IFO/ZON, and a tile table.
- **Per 160 m tile:**
  - terrain heights, 65×65 int16 (8,450 B). The server samples terrain from here, matching the client to the centimetre;
  - a 2-bit simple-cell mask (6,400 B): 0 = terrain not walkable, 1–3 = walkable main-component terrain with its clearance class;
  - a complex-cell bitmap and rank (3,520 B), plus span lists for every other cell;
  - sparse visual tops and sparse component ids.
- **Optional trailer:** DECO wall footprints, for dynamic objects.

**RAM.**
- **Total:** about 45–55 MB, bounded at about 75 MB.
  - 29 MB is fixed: 18.4 KB × 1,588 unique tiles. The bake covers 66 ZON folders for 67 zone rows, because zones that share a ZON load one read-only copy.
  - 15–25 MB is sparse data.
- **A\* scratch:** about 0.4 MB per zone thread.
- **Levers if memory is tight:**
  - drop Z-only spans more than 20 m above the highest reachable span in their column;
  - use 2 m cells in open zones;
  - enable zones one at a time;
  - make the server large-address-aware: one linker flag, giving 4 GB on 64-bit Windows. The earlier "LAA parked" decision covered only the client, so this is a separate question (decision 12).

**Shipping and checks.**
- **Shipping:**
  - the bake writes into `data/` next to each ZON, so dev servers pick it up with no change;
  - `pack.ps1` excludes `"*.lnav"` and `"*.LNAV"`;
  - the server runs locally on `data/`, so writing the file is the whole deploy (decision 14);
  - reports go to `build/nav/`.
- **Staleness:** a CRC mismatch logs `nav: zone N stale`; with `stale_disable = 1` the zone falls back to today's behaviour. `--check` lists stale zones.
- **Per-zone report and PNG:** failed seeds, unseeded islands over 500 m², spawn spill, HAZARD area.
- **MOV agreement:** the share of painted-blocked cells (after the flip) that the bake also blocks. The research expects 82–100%.
- **Deliberate mistakes** (see `doc/jrose-catacombs-collision-investigation.md`): without lump 11, the Shady edge walls must vanish; with one Goblin wall removed, the leak check must fire.
- **Offline A\*:** `nav-bake.py --path` cross-checks the server's paths.

### 3.2 Server runtime pathing

**Code.**
- New `S/nav/` with three units: `nav_data` (load, `SpansAt`, `FollowZ`, `SnapZ`, `VisualTopZ`, `LineWalk`, `SurfaceLinked`), `nav_path` (A\*, smoothing, per-zone search context) and `nav_agent` (leg follower, timers, budgets).
- The server `CObjCHAR` (server-only header) gains `short m_nNavZ` (−32768 = unknown) and `CNavAgent* m_pNav` (pooled; null when not on a path). This is one server-only layout change, so `sho_gameserver` needs a clean rebuild.

| Movement | Phase 4 (walls, no A\*) | Phase 5 (A\*) |
|---|---|---|
| Wander AIACT_03/04 (and AIACT_05, a move to a found character) | the destination must snap to a walkable span and `LineWalk` must succeed; at most 3 tries, then skip this idle tick | same; **wander never runs A\*** |
| Flee AIACT_08 | shortened to the last walkable point on the line | same |
| Leash `Run_AWAY` | a point reachable from home (at most 6 tries), otherwise straight as today | A\* home |
| Summon follow (`CObjSUMMON::Proc` loop, `S/cobjnpc.cpp:801-831`, and AIACT_29, `S/ai_lib/ai_action.cpp:846-867`) | line-checked, with a **straight fallback** so it is never stranded | A\* when blocked |
| CTRL+click move (`PlayerOrderMoveTo`, `S/cobjnpc.cpp:684-695`) | unchanged | A\* to the click, snapped within 5 m, otherwise straight; never refused |
| Chase, skill approach, CTRL+click attack | straight | line check, then A\* legs |
| Players | not pathed; Z tracked | not pathed |

**Hooks:**
- **`Goto_TARGET`** (`S/common/cobjai.cpp:606-615`) follows an active path and must not call `Restart_MOVE(pTarget->m_PosCUR)` while it does.
  - The target's position differs from the waypoint in `m_PosGOTO`, so the same-goal early return (:262) never fires.
  - The leg would otherwise be replaced by a straight move toward the target on every tick.
- **`ProcCMD_ATTACK`'s out-of-range branch** (:715-720) needs its own hook. It sets `m_PosGOTO` and calls `Start_MOVE` directly, bypassing `Goto_TARGET`.
- **`ProcCMD_MOVE` / `ProcCMD_PICK_ITEM`** (the latter also runs `CMD_RUNAWAY`) start the next leg on arrival.
- **`SetCMD_MOVE2D`** gets the nav gate (one point in, accept or refuse).
  - The **re-roll on refusal** belongs in the callers, which each draw a single point today: `F_AIACT03/04` (`S/ai_lib/ai_action.cpp:71-124`), `F_AIACT08` and `CObjMOB::Run_AWAY` (`S/cobjnpc.cpp:457-475`).
  - `PlayerOrderMoveTo` gets its own hook, because it bypasses `SetCMD_MOVE2D`.
- **`Init_ADD_CHAR`** (`S/cobjchar.cpp:732-750`) reports a monster on a leg as `CMD_MOVE` with target 0 and the current waypoint.
- **`Resync_MoveSPEED`** (:345-379) re-sends the leg with no target. It must also cover `CMD_RUNAWAY`: today it only re-sends for `CMD_ATTACK`/`CMD_MOVE` (:358-361), so a leash path that is slowed mid-way would drift.
- **`RealProc`** gets the step clamp and carries leftover time into the next leg (at most 2 legs per pass).
  - Movement dt gets **its own** 500 ms cap, tracked per `Proc` call. `Proc` splits one tick's `dwPassTIME` into several `RealProc` calls at motion-loop boundaries (`S/cobjchar.cpp:2209-2231`).
  - Do not cap `GetPassTIME` globally: the same value drives status timers.

**When path state is dropped:**
- on a **target change**, or when the **goal moves more than 4 m**;
- **when a cast starts**, because type-7 aim reuses `m_PosGOTO` (`S/cobjchar.cpp:2059-2063`).

It is **not** dropped on every `SetCMD_*`.
- `CObjSUMMON::Proc` re-issues `SetCMD_MOVE2D` every 300 ms while following (`S/cobjnpc.cpp:806-829`), and AI attack-move patterns re-issue `SetCMD_RUNnATTACK` on the same target. Dropping on each would re-plan constantly and burn the search budget.
- The follower's own legs never go through `SetCMD_*`.

Exclusion flags are checked before any move is issued.

**Chase.**
- Every 300 ms (staggered by index % 3), a chaser runs `LineWalk` toward its target. The line counts as clear only if it **ends on the target's own span**: a line from the ravine reaches the X/Y under a player on the deck, but ends on another span.
- A blocked line triggers A\*. A target in a different component is unreachable at once, with no search.
- While on a path, every 300 ms:
  - if the line has cleared, go back to a straight chase with one `CharacterMoveAttack`;
  - if the target is more than 4 m from the planned goal, re-plan.

**A\*.**
- 8 neighbours, octile costs 10/14, heuristic weighted ×1.2.
- A 128×128 window, with the start kept at least 8 cells inside it; at most 4 layers per cell.
- Generation-stamped arrays and a binary heap. When the search is exhausted it returns the best partial path, which is accepted only if it ends at least 2 m closer.
- Start snaps within 2 m, goal within 3 m.
- **Soft clearance:** a cell below the agent's preferred class costs ×3, so bosses prefer wide routes but never get stuck. The preferred class comes from NPC scale: under 120% → 1, up to 250% → 2, above that → 3.
- **Smoothing:** greedy string-pulling into at most 16 waypoints that carry Z, preferring class-2 cells. It is **Z-aware**: a leg is kept only if the span Z along it stays within ±100 cm of the straight chord.

**Budgets** (server.toml):
- 4,000 expansions per search.
- Per zone tick: 6 searches, 8,000 expansions and **3 ms of nav time measured with QPC**.
- Over budget: keep the current leg and retry next tick.
- A failed search walks straight for 2.5 s. This keeps today's reach, so pathing alone creates no safe spots.
- `NavStats` per zone every 60 s.

**Corners.**
- Leg k+1 is sent once no more than speed × `leg_lead_ms` of leg k remains (default 100 ms, 0 = off). The server itself still clamps exactly at the corner.
- The client cuts the corner by about 55 cm, which class-2 waypoints absorb, and each leg end re-syncs the two sides.
- A busy corridor costs about 2.2 KB/s per player.
- **Watch the 1 s forward snap.** A slow, a deferred leg (over budget) or a 2.5 s straight fallback can leave the client copy more than 1 s of walking behind. That shows up as the "position snapped forward" teleport, not a corner stop.

**Spawns.** `SnapSpawn` serves every spawn site:
- `RegenCharacter`/`RegenMOB` (`S/gs_threadzone.cpp:761-786, 693-719`);
- `Create_PET` and skill summons (`S/cobjchar.cpp:172-200, 1948-1955`);
- REWD_008 (`src/common/shared/io_quest.cpp:1667-1722`);
- Cerberus (`S/cerberus_lair.cpp:424-485`).

It draws in today's ±range **square** around the baked anchor. It rejects HAZARD spans (Phase 3) and points that `LineWalk` cannot reach from the centre (Phase 4). After 6 tries it uses the centre. A point that always falls back needs a data fix.

**`SnapSpawn` can run on another zone's thread.** REWD_008 with `btWho == 2` spawns into a different zone through `CZoneLIST::RegenCharacter(..., true)` (`S/zonelist.cpp:261-270`, `src/common/shared/io_quest.cpp:1718-1725`). That calls the target zone's `RegenMOB` on the caller's thread. Route such spawns through the delayed `m_MobCALLED` queue (`bImmediate = false`), so the target zone's dynamic overlay is only ever read by its own thread.

**Dynamic obstacles.** `SetZoneObjects` (`S/gs_threadzone.cpp:461`) holds a mutex, so it only queues the change. The zone thread applies the queue at the top of its Proc loop to a sparse overlay:
- kind-1 panels are rasterised from their placement;
- kind-0 objects use the footprint trailer.

**Config and GM tools.**
- `[nav]` sits beside `[game]` (`src/common/include/rose/common/server_config.h:142-146`). It uses ints and strings only (`aoe_band_slope_pct = 70`, `path_zones = "31,32,33,56,62"`), so the Rust FFI is unchanged.
- GM commands:
  - `/nav`: the spans, visual top and component at your position, plus the last client hint;
  - `/nav <switch> on|off`;
  - `/nav path x y`: marker items at the waypoints for 15 s;
  - `/nav stats`.

### 3.3 Z model

**Principle: every vertical verdict uses the Z the client draws.** Otherwise the server contradicts the screen: an AoE cast on a deck would miss a monster drawn on that deck.

| Entity | Stage A (Phases 2–5, unmodified client) | Stage B (Phase 6 on) |
|---|---|---|
| Monster, summon | `VisualTopZ(x, y)`, i.e. what `GetHeightTop` draws, looked up only when a band test needs it | `FollowZ` from the spawn span, kept in `m_nNavZ` and sent on the wire |
| Map NPC | `VisualTopZ`, as for monsters: the client draws `OBJ_NPC` through `AdjustHeight_Monster` (`C/cobjchar_collision.cpp:76-84`) | the authored IFO Z, snapped to a span |
| Player | `m_nNavZ`: `FollowZ` along the server's segment, re-anchored by client hints. Every span counts, Z-only and flag-12 spans included (the owner's view; observers skip flag 12). On zone-in: the visual top at the arrival point (mirrors `DropFromSky`) | same, plus the `JOIN_ZONE` Z once the client writes it |
| AoE centre | type 17: the caster's Z. Player type 7: the span at the aim X/Y nearest the caster's Z. Monster aimed type 7: the target's Z, copied with its X/Y at cast start | plus the client's aim Z (Phase 7) |

**`FollowZ`** applies the avatar's rule: at a new X/Y, take the highest span with z ≤ previous Z + 135 cm, otherwise the terrain. It runs **cell by cell along the step**, so a long tick cannot jump a ramp or tunnel under a deck.

**Client hints** (`MOUSECMD` at move start, the fixed `CANTMOVE`, and later `JOIN_ZONE`) only choose among real spans: the nearest one within 3 m. A forged hint can only pick a floor that exists at the player's own X/Y. `m_nPosZ` keeps its meaning and its broadcast.

**NavAudit** logs, rate-limited, every hint that is more than 1 m from every span. Ordinary play then audits the bake.

**Accepted Stage A gaps:**
- A monster that wanders under a walk-on deck is drawn on the deck, and the server agrees with that. HAZARD keeps spawns away from such spots, and Phase 6 fixes the rest.
- "The Z the client draws" holds only approximately. The client samples at the model's centre of mass and only re-snaps within the frustum or 40 m, and the bake has no MORPH or runtime objects. Large models at ledges can come out one layer off.

### 3.4 AoE and range in 3D

**Rule.** The 2D tests stay exactly as they are (`S/gs_threadzone.cpp:991`; cones and strips at `S/cobjchar.cpp:1683-1695`). One test is added: |z_target − z_centre| ≤ `base` + `slope`·d, where d is the horizontal distance to the centre (for cones and strips, to the caster). Defaults: 500 cm and 0.70.

**Measured against the sphere you suggested.** Shady Jungle (EJ01) terrain, 12,000 random caster–target pairs per radius:
- a *hillside pair* has a straight line between the two points that is never steeper than 54°;
- a *cliff pair* has no such line and dz > 5 m.

| Rule | Hillside hits wrongly lost (R 11.6 / 20 m) | Cliff pairs excluded, dz 5–10 m | 10–20 m | > 20 m | Today's hit pairs removed |
|---|---|---|---|---|---|
| Sphere of radius R | 6.8% / 5.7% | 44% / 14% | 100% / 63% | 100% / 100% | 14.7% / 15.5% |
| **Band 5 m + 0.7·d (default)** | **0.03% / 0.25%** | 10% / 4% | 80% / 47% | 100% / 100% | 6.5% / 9.5% |
| Band 4 m + 0.6·d | 0.5% / 1.4% | 38% / 15% | 98% / 71% | 100% / 100% | 8.9% / 12.4% |
| Band 4 m + 0.5·d | 1.2% / 2.4% | 53% / 21% | 100% / 85% | 100% / 100% | 10.2% / 14.4% |
| Cylinder H = max(4 m, R) | 0.13% / 0.06% | 0% / 0% | 75% / 0% | 100% / 100% | 5.9% / 6.0% |
| Gate 3 m + tan 54°·d | 0% / 0% | 5% / 2% | 34% / 11% | 100% / 68% | 3.9% / 4.8% |
| Band + same-surface check | 0.03% / 0.25% | 100% | 100% | 100% | ≈ 11% / 16% |

**Reading the table:**
- **The sphere is dominated.** On a hillside it keeps only cos θ of the disc. The 4 m + 0.5·d band excludes more cliffs and loses only a fifth to two-fifths as many hits.
- **Other zones agree.** Across the four hilliest zones at the median radius, the sphere loses 2.0–9.4% and the default band 0.01–0.19%.
- Cones and strips cannot be spheres.
- **Caveat:** the samples are terrain-only and uniform. Phase 3 re-measures with objects and regen weighting.

**What the default band still admits.** Of the 220 damage circles: none reaches the Shady, Gorge or Eucar decks; 2 reach Goblin B2; 14 reach Ulverick; 215 reach the B3 altar (beyond 4.9 m); 151 reach a 10 m cliff (beyond 7.1 m).

**Optional same-surface check** (`aoe_surface`, off by default):
- A candidate with |dz| > 4 m is kept only if `SurfaceLinked(centre span → target span)` holds.
- `SurfaceLinked` is a DDA that applies only the 135 cm link rule, **ignoring walls and clearance**, so trees and rocks on a hillside exclude nobody.
- It separates every layer at every radius, and it needs only the Phase 2 bake.
- Its price in Shady Jungle: about one random pair in nine is excluded, against one in fifteen with the band alone (decision 2).

`aoe_vertical` switches the rule live (0 off, 1 band, 2 sphere, 3 cylinder).

| Check | Phase | Rule |
|---|---|---|
| A1/A2 area damage, types 7/17, circles, cones, strips | 3 | band (+ surface check if on) |
| A4/A5 area statuses (`S/cobjchar.cpp:1582` serves types 3–6, 8/12, 9/13; `:1767` serves 10/11). Both sites mix friendly and hostile skills | 3 | band only the targets of hostile skills, chosen by the skill's target filter rather than by call site |
| Friendly area buffs and heals (149 rows) | — | 2D (decision 6) |
| Aggro scans C1/C4/C6/C7 (COND02/08/27, ACT06); help calls C9/C10 (ACT11/14/18) | 3 | band, for OBJ_MOB finders |
| Attack and cast range B1/B2 on both sides; COND04 | 7 | band (the client tests the full \|dz\|, the server adds 100 cm of slack); no surface check, since the client has no nav data |
| Leash, summon distance, despawn, party/trade/quest checks | — | 2D |

**Implementation.**
- **Collect, then apply (Phase 1).** `CollectCHARs(pos, radius, band, out[], ≤ 128)` stores object indices. Each target is re-fetched and its HP checked before damage is applied, and circles get an explicit radius re-test. Callers:
  - `S/cobjchar.cpp:1604, 1681, 1784`;
  - `src/common/shared/io_quest.cpp:2388` (server branch only);
  - `S/cheatcmd.cpp:1043`.
- **AI scans** do not call out, so they keep the zone iterator.
  - Their band goes into the iterator state (`S/gs_threadzone.h:78-83`): `FindFirstCHAR` stores the centre Z and band, and `FindNextCHAR` tests them next to the 2D test at `S/gs_threadzone.cpp:991`.
  - The server `AI_FindFirstOBJ` overloads (`S/cobjchar.cpp:120-136`) pass the finder's Z in.
  - `AI_FindNextOBJ` takes no parameters, so it cannot carry the band itself.
  - The shared `CAI_OBJ::AI_FindFirstOBJ` signature (`src/common/shared/cai_lib.h:123`, also compiled into the client) does not change.
- **Unknown Z** (no bake) means no band.
- The band is a post-filter and does not change sector reach.
- A log line every minute reports exclusions.

### 3.5 Line of sight

Out of scope, for three reasons:
- the server has no wall tops;
- a walk test is not a sight test (a fence stops walking, not arrows);
- an attack check without matching client logic would refuse swings silently.

Attacks and aggro through a thin wall within 2D range therefore stay possible. Phase 8 offers walk-line checks for monsters only.

### 3.6 Protocol changes

| Change | Lockstep? | Phase |
|---|---|---|
| `build_char_move_leg_packet` (target_id 0, leg length); the attack builder switches to `CharacterMoveAttackBuilder` (same bytes; today it uses `CharacterMoveBuilder`, `S/network.cpp:116`) | no | 0 |
| Zero `gsv_STOP.m_nPosZ` (heap garbage today, `S/cobjchar.cpp:293-296`) | no | 1 |
| `short m_nPosZ` in `gsv_MOB_CHAR` after `m_nQuestIDX`, in the fixed part, inherited by `gsv_NPC_CHAR` (−32768 = unknown). Not in `tag_ADD_CHAR`, so `gsv_AVT_CHAR` keeps its layout. Readers use `sizeof` (`C/network/recvpacket.cpp:1308, 1353, 1445`; `C/cobjchar.cpp:955, 4661, 4693`; `S/cobjnpc.cpp:138, 887`). **Caveat:** the summon path copies only `sizeof(gsv_MOB_CHAR)` into `m_SummonMob` and then reads the variable status tail from it (`C/cobjchar.cpp:4661, 4693`). That tail is already garbage today, so check that path by hand when the field goes in | **yes** | 6 |
| Fill `Vec3.z` in `CharacterMove`, `CharacterMoveAttack` and `CombatSwing`; fill `gsv_STOP.m_nPosZ` | no | 6 |
| The client writes `cli_JOIN_ZONE.m_nPosZ`; inline drops (`tag_DROPITEM`) take the dead monster's drawn Z | no | 6 |
| Size-gated Z on `gsv_ADD_FIELDITEM` (precedent: `gsv_SKILL_START.m_PosAIM`, `net_prototype.h:1555-1563`) | tolerant | 6, optional |
| Size-gated aim Z on `cli_POSITION_SKILL` and `gsv_SKILL_START`; band constants in the zone-join reply | tolerant / yes | 7 |

### 3.7 Client changes (Phases 6–7)

**Phase 6: monster and NPC height** (`AdjustHeight_Monster` and `DropFromSky`, only for `OBJ_MOB`/`OBJ_NPC` with a server Z):
- z = max(terrain, nearest **up-facing** hit below ref + 135 cm over all colliding nodes, NOTMOVEABLE included);
- **reject down-facing hits.** The engine's ray test is two-sided (`D3DXIntersectTri`), so a plain down-ray would land on the undersides of flag-12 cave ceilings, overhangs and low tree crowns within 135 cm, where the bake has no span. `shootRayVec3Ex` returns the contact normal, so the filter is cheap;
- ref = the previous drawn Z;
- the leg interpolation wins when it differs from ref by more than 3 m, or when the height data is stale (`C/cobjchar.cpp:5777-5827`);
- with no surface near ref, draw at ref;
- the helper is a down-only copy of `getWorldObjectHeightInScene` (`E/zz_interface.cpp:9067`), about 40 lines;
- with no server Z, behaviour is exactly today's. Avatars are untouched.

**Phase 7:** client `IsInRANGE` (`C/cobjchar.h:321-327`), the aim pick (`C/skillaim.cpp:87-126`) and telegraphs (`C/groundtelegraph.cpp:255-262`).

## 4. Phases

**Rules.** A phase is committed only after in-game validation. Each phase has its own switches and can be enabled zone by zone.

**Order.** The phases run in numbered order, Z first (decision 3). Possible merges: 2 with 3, and 6 with 7.

### Phase 0: measure and probe (go/no-go)

- **Goal:** before building anything, find out whether there is tick and address-space headroom, whether the iterator bug bites, and whether multi-leg moves look acceptable on the unmodified client.
- **Changes:**
  - QPC timing of each zone's Proc loop (`S/gs_threadzone.cpp:187-218`): average, p99 and max every 60 s;
  - Private Bytes, after load and then hourly; live monster count per zone;
  - counters for move rejections, `Run_AWAY` failures and iterator clobbering;
  - the leg follower (§3.2);
  - **the probe,** `/nav trail`: the targeted monster walks the GM's move corners from the last 60 s (`MOUSECMD` starts, `CANTMOVE` stops) as legs, then chases.
- **Test:**
  - an hour in Sikuku and Sunshine Coast with a party;
  - `/nav trail` round a Goblin B1 bend at walk and run speed, with a lead of 0, 100 and 150 ms;
  - a second account arriving mid-trail sees the legs, not a monster homing through rock;
  - a slow applied mid-leg;
  - CombatTrace orphan sweeps, and `client.log` "position snapped forward" lines.
- **Exit / decision:**
  - You judge the corners. If no lead value works, pathing waits for a client fix in Phase 6, and the Z track continues.
  - If Private Bytes + 110 MB exceeds 1.7 GB, pick a RAM lever.
  - If busy-zone p99 tick time exceeds 130 ms, halve the budgets.
- **Kill switch / size:** the probe is GM-only and the clamp is invisible. About 400 lines of C++, with one server-only layout change.
- **Player notices:** nothing.

**Status (2026-10-28): validated in game.** Server only: `src/sho_gameserver/src/nav/`.

**Results:**
- **Corners.** `lead 100` looked good, and even `lead 0` did not look bad. 100 ms stays the default, so **corner presentation is a go: no client change is needed for pathing.**
- **Slowed monster:** it stayed on the corners, just slower.
- **Chase hand-off** worked.
- **Second viewer:** an account arriving mid-route saw the monster on the correct legs.
- **Load:** the party hour was skipped; the server lines from the test session cover it.
  - 67 zones and 14,151 live monsters.
  - The worst per-tick object work was Sikuku Prison at a p99 of 3.4 ms. Goblin Cave B1 averages 0.04 ms.
  - The longest tick was 112 ms, which is timer granularity.
  - Memory: 450 MB private, 646 of 2,047 MB of address space.
  - So there is ample CPU and address-space headroom; the nav budgets and the 45–75 MB of nav data stand.
- **Open:** the test session's AoE-clobber count was 0, probably because nothing cast AoE. The meter keeps counting in normal play; check it before Phase 1's scan fix.
- The test server runs from `Exes/`; its log is `Exes/log/gameserver-<date>.log`.

What was built:
- **`nav_agent`, the leg follower.**
  - Target-less `CharacterMove` per leg (`build_char_move_leg_packet`).
  - Exact clamp at each corner, carrying leftover time into the next leg.
  - A 500 ms step cap.
  - `lead_ms` early send.
  - It is dropped as soon as anything re-commands the monster.
  - New viewers and speed re-syncs get the leg the clients were last told.
  - The step clamp applies only to path legs; ordinary moves are unchanged.
- **`nav_stats`, the zone meter.**
  - Per zone, once a minute while the zone has players (or when its p99 is 30 ms or more): `nav: zone N …` with object work avg/p99/max, longest tick, monsters, players, AI moves refused, leash points refused, and AoE scans clobbered.
  - Server-wide, after a minute and then every 5 minutes: `nav: server: …` with zones, monsters, worst p99, private bytes and address space used.
- **`nav_probe`, the `/nav` command:**
  - `/nav rec` starts recording your click-move corners;
  - `/nav mark` adds a corner where you stand;
  - `/nav trail [lead_ms] [walk|run] [chase]` makes your target, or the nearest monster within 30 m, walk the corners, and replays the same trail until the next `rec`;
  - `/nav stats` shows this zone's last minute plus the server line.
- `CharacterMoveAttack` is now built with its own builder (same bytes).

**In-game test (GM):**
1. **Corner feel.** In Goblin Cave B1, at a corridor bend:
   - `/nav rec`, click-walk round the bend (each click is a corner), then `/mon <id> 1` near the start of the route.
   - `/nav trail 0`, then `/nav trail 100`, then `/nav trail 150`, then `/nav trail 100 walk`.
   - Watch every corner: a short stop (lead 0) against a small cut (100/150). Note which lead looks best, or whether none does.
2. **Second viewer.** Have a second account arrive while the monster is mid-trail: it must see the monster walking the legs, not homing through rock.
3. **Slow mid-leg.** Slow the monster mid-trail: it keeps to the corners, with no teleport. Check `client.log` for "position snapped forward".
4. **Chase hand-off.** `/nav trail 100 chase`: at the last corner the monster runs at you and attacks normally. Combat looks normal, and CombatTrace shows no orphan sweeps.
5. **Meter.** Spend an hour with a party in Sikuku Prison and Sunshine Coast, then read the `nav: zone …` and `nav: server: …` lines. Also note the `AoE scans clobbered` count after AoE-ing packs.

### Phase 1: ground fixes

- **Changes:**
  - **no in-game MOV flip** (decision 8: MOV is retired in Phase 4). Only the docs are corrected: the `chunk.py` docstring, FORMATS.md, and the editor's `MOV.cs` and tests now say row 0 = north;
  - X bounds check in `IsMovablePOS`;
  - collect-then-apply in the five outer scans;
  - `CANTMOVE` reads its own Z and calls `UpdateSECTOR` (`S/gs_user.cpp:2836, 2848`);
  - `gsv_STOP` Z zeroed;
  - AIACT_08 zero-distance guard.
  - (The movement dt cap shipped in Phase 0 with the step clamp.)
- **Test:**
  - AoE a pack whose AIP scans on DAMAGED: CombatTrace shows every monster inside the radius hit, and none outside it;
  - a player stopped by a wall (`CANTMOVE`) keeps a sane Z and sector;
  - a monster fleeing from a target standing on its exact spot.
- **Exit:** no regression in AoE or movement.
- **Kill switch / size:** none needed; these are bug fixes. About 200 lines.
- **Player notices:** AoE hits the whole pack every time.

### Phase 2: bake and server Z (invisible)

- **Changes:**
  - the full bake (§3.1); walls are computed now but used only from Phase 4;
  - loader after the map loop (`S/zonefile.cpp:640-645`);
  - regen, NPC and event Z read (`tagEVENTPOS` gains a Z);
  - player `FollowZ` and client hints;
  - `/nav`, NavAudit, and the shipping lines.
- **Data:** bake all 67 zones. You review the PNGs of Goblin B1–B3, Shady Jungle, Junon Polis, Sikuku, Muris and Shadow Canyon's planks.
- **Test:** run `/nav` on and under the `dari` deck (two floors, about 72 m and 5 m), at B1 `domdari`, on the B3 altar (about 479 cm), on a Junon floor and in the street below it, on a Shady edge panel (no walkable top) and on a Muris roof. Then play for 20 minutes across 5 zones.
- **Exit:**
  - NavAudit misses over 1 m stay under 2% of hints, each one explained;
  - every seed resolves or is listed;
  - the bake without lump 11 drops about 27,600 m² of Shady panel tops;
  - Private Bytes rise by at most 80 MB and load time by at most 5 s;
  - no `.lnav` in the packed index. `pack.ps1` has no dry-run mode (its only parameters are in, out and pipeline), so list the index after a real pack, or add a `-WhatIf` flag.
- **Kill switch / size:** `enabled = 0`, or delete the file. About 1,000 lines of Python and 600 of C++.
- **Player notices:** nothing.

### Phase 3: vertical band and roof spawns (server only)

- **Changes:**
  - Stage A Z, the band, AoE centres and aim Z (§3.3–3.4);
  - the surface check (off) and `aoe_vertical`;
  - `SnapSpawn` with HAZARD rejection and counters per regen point;
  - `scripts/nav-band-calibrate.py`.
- **Test:**
  - from a Shady cliff ledge, and from the `dari` deck with monsters pulled below, the largest AoE hits nothing below and draws no aggro from below;
  - at the B3 altar edge, AoE still hits monsters on the altar;
  - EJ02 and JD03 hillside packs take the same hits with the band on and off (try `aoe_vertical 2` to feel the sphere);
  - 10 minutes of respawns in Muris, Zant and Fossil Sanctuary: none on a roof.
- **Exit:**
  - hillside tests identical;
  - layer cases excluded;
  - exclusion rates reviewed against the calibration;
  - any regen point still at 100% fallback (Muris has one under a roof) is listed and moved as a data fix.
- **Kill switch / size:** `aoe_band`, `mob_layer_aggro`, `spawn_hazard`. About 400 lines of C++ and 200 of Python.
- **Player notices:** AoE from a bridge or cliff top no longer reaches far below; monsters below stop aggroing and stop answering help calls through floors; no monsters on Muris and Zant roofs.

### Phase 4: walls for idle moves and spawns (server only)

- **Changes:**
  - `LineWalk` and the `SetCMD_MOVE2D` gate (§3.2 table), with straight fallbacks for leash and follow;
  - `SnapSpawn` reachability;
  - the footprint trailer;
  - MOV retired in baked zones: the bake replaces it as the walkability source, and its grid is freed (decision 8).
- **Data:** review walls, clearance, MOV agreement and both deliberate-mistake bakes; fix the rules and re-bake.
- **Test:** Goblin B1/B3 respawns stay out of rock and inside the tunnels. Watch wanderers near walls, Junon houses and Shady trees; wander in a Karkia zone with no MOV; and a summon following through a doorway.
- **Exit:** spawn fallback at most 1% per zone, with no point at 100%; MOV agreement at least 80%; no monster frozen for 60 s.
- **Kill switch / size:** `ai_moves`, `spawn_reach`. About 300 lines of Python and 400 of C++.
- **Player notices:** idle monsters stop walking through houses, trees and cave walls; nothing spawns in rock or outside the Goblin tunnels.

### Phase 5: pathfinding (server only)

- **Changes:**
  - `nav_path` and every §3.2 hook, skill chases included;
  - the QPC budget cap;
  - the dynamic overlay (decision 10);
  - `/nav path` and NavStats;
  - `path_zones` rollout: Goblin B1–B3, LZ01 and Shady Jungle first.
- **Test:**
  - in B1, a monster dragged round a 90° bend follows the corridor, with at most one visible stop per corner (A/B the lead);
  - Junon buildings; Adventurer's Plain rocks;
  - from the Shady deck, a valley monster climbs a ramp when one lies in the search window, and otherwise stays below as today;
  - summons follow across the deck; CTRL+click a summon behind a house;
  - Cerberus with the wall up;
  - Sikuku with a party.
- **Exit:** in Sikuku and Sunshine Coast, nav time averages at most 2 ms per tick and p99 tick time rises by at most 5 ms; deferrals under 5%; no chaser stuck for more than 5 s; no new orphan sweeps.
- **Kill switch / size:** `pathing`, `path_zones`, `/nav pathing off`. About 1,300 lines of C++.
- **Player notices:** monsters and summons go around obstacles; leashing monsters walk home along corridors. **Leashes trigger more often in caves**, because paths are longer than the straight-line leash distance.

### Phase 6: the client draws the server's floor (lockstep)

- **Changes:**
  - server: `m_nNavZ` from `FollowZ` for monsters, summons and NPCs; the band switches to Stage B; the Phase 6 rows of §3.6;
  - client: §3.7;
  - clean-rebuild both and ship them together with the data.
- **Test:** a monster lured under the Shady bridge or a B1 bridge walks the floor below it, seen from both levels. The B3 altar is unchanged, nothing hangs on the Shady or Cerberus panels, stairs are smooth, and unbaked zones are unchanged.
- **Exit:** nothing drawn more than 1 m off its server layer at the test sites; leg-end snaps over 3 m are rare; CombatTrace clean.
- **Kill switch / size:** `send_z = 0` sends −32768, and the client falls back to `GetHeightTop`. About 350 lines of client and 150 of server.
- **Player notices:** monsters, NPCs and summons stand on the floor they are really on.

### Phase 7: 3D attack range and aim (lockstep, optional)

- **Changes:**
  - the band in `IsInRANGE` and `Goto_TARGET` on both sides (server +100 cm slack), with the constants sent at zone join;
  - the monster attack band and the vertical give-up (decision 4);
  - the "another level" message;
  - aim picks on objects, aim Z tails and telegraph Z;
  - a cast band from the caster to the aim point.
- **Test:**
  - melee from the deck into the ravine is refused with the message, with no endless walk;
  - an archer on a 20 m cliff;
  - a monster under the deck neither hits upward nor waits forever;
  - hillside attacks are the same with the switch on or off;
  - ground AoE aimed at the deck lands there, and its telegraph draws there.
- **Exit:** no chase parks short of its target; both sides refuse layer cases identically.
- **Kill switch / size:** `vertical_range`, sent at zone join. About 350 lines of client and 250 of server.
- **Player notices:** attacks and casts respect floors; ground skills can be aimed onto decks.

### Phase 8: optional, each on its own

- OBJ_MOB walk-line checks.
- Remote-player spawn Z via the unused `gsv_AVT_CHAR.m_nPosZ` (a change to player presentation, so it needs your sign-off).
- Drop edges.
- 5×5 sector scans for large radii.
- `CANTMOVE`/`SETPOS` validation.
- An OBJ_MOB `more_legs` flag.
- The Recast/Detour fallback: two small static-lib vcxprojs, like `thirdparty/fmt.vcxproj`.

## 5. Pre-existing bugs

| Bug | Evidence | Fixed in |
|---|---|---|
| MOV mirrored north–south inside each tile | `S/zonefile.cpp:310-321` | docs in 1; MOV retired in 4 (decision 8) |
| `IsMovablePOS` treats an off-grid X as walkable | `S/zonefile.h:131-136` | 1 |
| Shared scan iterator not re-entrant | `S/gs_threadzone.h:78-83`, `S/cobjchar.cpp:1223` | counted in 0, fixed in 1 |
| `CANTMOVE` reads Z through `cli_MOUSECMD`, and teleports without a sector update | `S/gs_user.cpp:2836, 2848` | 1 |
| `JOIN_ZONE` Z never written by the client | `C/network/sendpacket.cpp:209-214` | ignored from 2; written in 6 |
| `gsv_STOP.m_nPosZ` is heap garbage | `S/cobjchar.cpp:293-296` | zeroed in 1, filled in 6 |
| No arrival clamp (overshoot 33–85 cm); uncapped `dwPassTIME` | `S/cobjchar.cpp:2074-2091` | 0 / 1 |
| AIACT_08 divides by zero when both stand on the same spot (inferred) | `S/ai_lib/ai_action.cpp:224-255` | 1 |
| `CharacterMoveAttack` built with `CharacterMoveBuilder` | `S/network.cpp:116` | 0 |
| IFO, regen and event Z discarded | `S/zonefile.cpp:161-163, 501-504` | 2 |
| Quest COND_006/021 radius ×10,000 (15 COND_006 + 24 COND_021 = 39 triggers in 7 QSDs pass at almost any distance); the comment at :990-997 claiming 343 COND_021 is stale | `src/common/shared/io_quest.cpp:539, 998` (check-time ×100) and `:3170-3175` (load-time ×100 in `Init_COND`) | left alone (decision 11) |
| Item pickup has no range check | `S/gs_user.cpp:4417-4475` | out of scope |
| Shield reflect is 4,000 cm; the comment says 4 m | `S/cobjchar.cpp:1315` | out of scope |
| AIACT_37 range not ×100 at load | `src/common/shared/cai_file.cpp` | out of scope; check |
| Client CLAUDE.md says five `AdjustHeight_*` paths; there are seven | `C/cobjchar_collision.h:84-90` | doc fix |

## 6. Decisions (answered by the user, 2026-10-28)

These answers override anything earlier in this document that disagrees with them.

1. **Shady Jungle spot:** both the `dari` bridge and the cliff tops are tested.
2. **AoE vertical rule:**
   - the band, 5 m + 0.7·d, is the default (tighten to 4 m + 0.6·d if cliffs still feel wrong);
   - the sphere is available only as a switch value;
   - the same-surface check is off by default.
3. **Order:** Z first, so phases run in their numbered order, 0 → 7.
4. **Unreachable targets:** the hybrid, **without the heal.**
   - A failed search walks straight.
   - From Phase 7, the monster gives up after 3 s, but only when the target is outside the band.
   - A leashing monster still takes damage without fighting back. That is accepted as old-school exploitable fun.
5. **Phases 6 and 7 both happen,** one right after the other.
6. **Friendly area buffs and heals stay 2D.**
7. **Ground AoE from a deck aimed below** is allowed within the caster-to-aim band, and refused with the "another level" message outside it.
8. **MOV is retired once the bake drives walkability (Phase 4).**
   - **Phase 1 therefore drops the in-game row flip**, so there are fewer AI changes to validate and no 18-zone behaviour shift for a grid that is going away.
   - What stays:
     - the documentation fixes (`chunk.py` docstring, FORMATS.md, `MOV.cs` and its tests);
     - the bake's MOV-agreement metric, computed on flipped rows. If the bake agrees with the flipped rows 82–100% of the time, that confirms the orientation offline.
   - Zones with no bake keep today's MOV behaviour unchanged.
9. **Spawn fallback:** the regen centre, and points that keep falling back get their data fixed.
10. **Cerberus ice wall:** monsters path around it, behind its own switch, after one test run.
11. **Quest COND_006/021 radius bug: left alone.**
    - Today those 39 conditions ("be within N m of a spot or NPC") pass from almost anywhere.
    - Fixing them would make players really stand there, and any quest with a slightly wrong position in its data would become impossible to complete.
    - The user will not re-test 39 quests, so this stays a known quirk outside this project.
12. **RAM:** approved; there is plenty of headroom.
13. **Water:** monsters keep walking lake beds as designed. No deep-water cost, so the Phase 8 deep-water item is dropped.
14. **Deployment:** the server runs locally and reads `data/` directly (`C:\Users\Thomas\Desktop\Rose\rose-next-classic\data`).
    - The bake writes `.lnav` next to each ZON under `data/`, and that is the whole deploy.
    - `server-data.ps1` is not involved.
    - The only shipping rule left is that `pack.ps1` must exclude `*.lnav` / `*.LNAV` from `rose.vfs`.

## 7. Risks and containment

| Risk | Containment |
|---|---|
| The bake misclassifies floors or walls | PNG review, NavAudit, deliberate mistakes, MOV agreement, manual seeds, per-zone kill |
| RAM in a non-LAA process | Phase 0 headroom, Phase 2 exit ≤ 80 MB, §3.1 levers |
| Tick stretch | expansion and QPC caps, no A\* for wander, Phase 5 p99 exit |
| Corner hitches | Phase 0 probe, `leg_lead_ms`, class-2 waypoints |
| Gameplay shifts (the band removes 6.5–9.5% of random Shady pairs, mostly across cliffs; more leashes in caves) | live switches for A/B, logged numbers, tunable constants |
| New safe spots | straight fallback; vertical give-up only once both sides are banded; no evade heal (decision 4, accepted) |
| Client and server Z disagree after Phase 6 | continuity with an interpolation fallback, Z-aware smoothing, leg-end snap, sentinel |
| An old client misreads `gsv_MOB_CHAR` | ship client, server and data together |
| Stale bake; MOV flip wrong | CRC check and `--check`; the flip's own switch |
| Nav file packed into `rose.vfs` | lowercase extension, excludes for both cases, dry run |
| Not modelled: moving platforms, MORPH, water depth | listed in the report; behaviour there is unchanged |

## 8. EVO-REFORGED: what we borrow and what we do differently

EVO has no licence. We borrow ideas and tuning values only; no code is copied or transcribed.

**Borrowed:**
- **Search:** line check first, A\* only when blocked; per-tick budgets; 2.5 s of straight walking after a failure.
- **A\* internals:** generation stamps, a centred window, best partial path, weighted octile heuristic.
- **Paths:** snap tolerances; smoothing to 16 waypoints; target-less legs shown to new viewers; a re-plan after the target moves 4 m.
- **Bake:** a body-height wall band, cylinders as walls, preview PNGs, a grid shared per ZON.

**Done differently:**
- **Data model:** layers instead of the max of the tops. Floors come from geometry and reachability, not from "flag 12 = wall". Clearance classes replace a point agent.
- **Obstacles:** lump 11, water, warps and event objects are all included.
- **Movement:** an arrival clamp, which EVO's arrival test relies on and our mover lacks.
- **Cost control:** budgets sized for 10 Hz, plus a wall-clock cap.
- **Hook coverage:** the hooks also catch CTRL+click orders and skill chases. Exclusion flags are checked before moving; `GS_BOSS.cpp:555` gets that order wrong.
- **Implementation:** `_to_model` transforms, an overlay on baked grids, and path state behind a pointer.
- **Z support:** EVO has none.

## Appendix: evidence

The measurement scripts are research scratch, archived **locally** in `build/nav-research/` (gitignored, not in the repo). They are read-only Python over `scripts/rosefmt`, run with `python -I`; some import siblings from their own folder.

Promote any of them into `scripts/` when a phase needs it. Phase 3 turns the band measurement into `scripts/nav-band-calibrate.py`.

| What | File (under `build/nav-research/`) |
|---|---|
| Research reports | `reports/` (server movement, range checks, client height, map data, EVO pathing, protocol, critic) |
| Proposals, judges, fact-checks | `design/` |
| AoE band and sphere table | `scripts/synth/band_frontier.py`, `design/band.py` |
| Panels | `design/panels_all.py` |
| Quest radius triggers | `design/qcond.py` |
| Roof spawns per zone | `scripts/proto_layers.py`, results in `scripts/critic/layers_<row>.txt` |
| `GetHeightTop` replica | `scripts/clientz_heighttop.py` |
| MOV row-order tests | `scripts/mov_orient2.py`, `scripts/mov_slope.py`, `scripts/mapfmt/mov_regen.py`, `scripts/mapfmt/mov_vs.py` |
| Layers and bridges | `scripts/mapfmt/layers.py`, `scripts/mapfmt/bridges.py`, `scripts/critic/bridges_all.py` |