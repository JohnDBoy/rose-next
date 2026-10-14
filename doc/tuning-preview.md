# Tuning mounted-stat preview

The original inventory draws its seven stat boxes as part of
`UI_INV_EQUIP_PAT`; it never populated them. `CItemDlg` now overlays values from
a server-side hypothetical mounted calculation. No XML or texture change is needed.

## Contract

- The request contains only a sequence number. The server reads the requesting
  user's equipment and abilities; the client cannot submit an invented loadout.
- Type, physical defence, magic resistance, engine fuel consumption, movement
  speed, attack power and attack speed use the game's numeric stat units.
- Missing bodies show no values; incomplete assemblies retain type and fuel
  consumption where known. Unarmed carts retain defence/resistance/speed.
- Broken parts follow the existing formulas (including the engine/leg movement
  fallback); the preview does not invent repairs or extra combat restrictions.
- Fuel is the engine's cost per deduction: on mounting, every fuel tick (currently
  ten seconds), and when attacking. It is not fuel per second or remaining fuel.
- While unmounted, only copied part records lose the mounting fuel cost. Only a
  copied `StatusEffects` has `ClearAllGOOD()` applied. Surviving debuffs, goddess
  and fairy effects use server semantics.
- While already driving, valid combined fields report the current authoritative
  totals, including their existing cached values and effects. There is no second
  hypothetical mounting deduction or removal of buffs applied after mounting.
- Riding restrictions for the current zone do not suppress the preview. Animal
  mounts (body type 513) are outside this cart/castle-gear feature.

## Calculation boundaries

`rose/common/mounted_stats.h` contains the value-only calculator and arithmetic
shared with live server ATK, ASPD, movement, DEF, RES and carrying-capacity paths.
`mounted_item_bonuses.h` shares equipment/gem/union bonus accumulation with live
`CUserDATA`; `tuning_preview.cpp` resolves the player's inputs and effects.

Preserve these existing gameplay details when changing the formulas:

- Mounted DEF/RES still include ordinary armour. Mounting replaces most ordinary
  equipment bonuses, but retains its weight bonus and both passive ranges.
- The server's `Cal_BattleAbility` used to clear the second passive range
  (`AT_PSV_RES`..`AT_PSV_IMMUNITY`); since 2026-10-14 it keeps it, and the preview
  reads those passives too rather than rebuilding them from skill tables.
- Integer conversions include intermediate **short** stores. Do not replace the
  float expressions or move casts when extracting additional formulas.
- `classUSER::UpdateAbility` calculates speed twice; its final fairy movement
  adjustment uses the new mounted base speed. The legacy fairy defence adjustment
  remains cached. This feature does not repair unrelated fairy behavior.
- The initial movement calculation uses the current server weight bracket.
  The preview also projects mounted carrying capacity and the subsequent weight
  bracket reported by the client, applying that final speed cap. Already-mounted
  previews always use the actual server total.

## Networking and lifetime

The FlatBuffers union appends `TuningPreviewRequest` and `TuningPreviewResponse`;
existing type IDs stay unchanged. `common-lib/build.rs` generates both languages.

The client polls only while Tuning is visible, at most once per 500 ms, with one
request outstanding and a two-second timeout. Generation checks invalidate
responses after equipment/condition changes, closing the panel, or clearing the
world during zone/character transitions. Responses never update avatar stats.

The server processes requests on the normal user/zone thread. Its request gate
defers early arrivals until the next 500 ms calculation slot instead of dropping
them. Only the requester receives the result. An in-flight request received
during zone teardown is ignored safely.

## Verification

Build through the solution, release/x86:

```powershell
MSBuild.exe rose-next.sln '-p:Configuration=release;Platform=x86' '-t:sho_gameserver;client;tuning_preview_tests'
bin/release/tuning_preview_tests.exe
```

The test executable covers legacy formula parity over level/attribute/refinement
and rounding boundaries, equipment/gem/union accumulation, transport carts,
incomplete/broken assemblies, fuel exhaustion, effect/config adjustments, weight
caps, snapshot immutability, packet round trips, timeouts, rate limiting and stale
responses. Table adapters make bonus fixtures independent of private game assets.

In-game validation: the user confirmed on 2026-09-13 that the panel works and
shows the correct stat numbers. Release/x86 client and server builds and the
automated regression suite passed before deployment.

For future regression checks, compare the unmounted preview with authoritative
mounted totals, swap parts rapidly, exercise removable/surviving effects and
weight thresholds, then change zones and reopen the panel. Opening the panel
must leave fuel, HP/MP and buffs unchanged. These individual edge cases were not
separately confirmed in the user's in-game report.
The ordinary character panel has legacy client-side DEF/RES calculations, so it
is not an independent authority for those two fields.

Deploy the new client and game server together. The client launch directory for
this workspace is `C:\Users\Thomas\Desktop\ROSEProject`; server output is
`bin/release/sho_gameserver.exe`. Keep the client executable and `znzin.dll` paired.
No database migration or asset bake is required.
