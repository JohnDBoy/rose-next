# Importing a monster from another dump

The order of work for bringing one monster across from a reference client (Jrose, tsuki,
667, 668, RoseZA ...). It is the playbook; [making-monsters.md](making-monsters.md) is the
list of traps, and you need both. Worked examples, newest first:

- `scripts/import-shadow-soldier.py` (2026-10-27, Jrose): two telegraphed skills, its
  own sword, authored AI. **Validated first try; start from this one.**
- `scripts/import-necromancer.py` (2026-10-24, tsuki): one legacy skill (a drain), its
  own staff, authored AI.
- `scripts/import-cerberus.py`: a whole boss lair (telegraphs, summons, a controller).

The fixed rules of the house, whatever the variant:

- **Stats are ours.** Never copy a source's HP / ATK / DEF / skill power: every dump is on
  another scale (Jrose's 2290 had 4000 HP per level at level 250).
- **The AI: the source's or ours, decided per monster by the user.** Some dumps ship
  their `.aip` files (**Jrose ships ~1,200**, Karkia's AIs are Jrose's), others none
  (tsuki). When one ships, read it, report what it does, and **ask** whether to take it or
  author ours -- never assume either way. The Shadow Soldier's `mst_boss1.aip` casts the
  same two skills and summons its three Shadow siblings; the user preferred our authored
  AI (telegraphs, no summons). Section 7 has both routes.
- **The script is the record.** `data/` is not in git. One `import-<name>.py` writes the
  row, the model, the clips, the skills, the AI and the weapon, with `--dry-run` and
  `--verify`, and its docstring says why every number is what it is.

## 1. Survey the source row

**Run `python scripts/survey-monster.py <dump folder> <row>` first** (~10 s, read-only;
`--profile` draws the skill clips' motion as bars). It prints everything below: both
names, the neighbours (siblings), whether our row is free and the nearest free runs, a
model of ours with the same meshes, every anim slot with its events and the skills that use
the clip, motion profiles and loop seams, the weapon against ours, and the source AI's
casts and summons if the file ships. What it does by hand is below, for when it is not
enough. Underneath it reads with `scripts/rose-data-reader.py`'s rules (each dump's
encoding, STL dialect and key column; `doc/jrose-survey.md` section 2). Note:

- **LIST_NPC row:** name, model text, walk/run, size (col 4), right weapon (col 5), AI row
  (col 16), mark (col 27), glow (col 39). Cosmetic cells may be kept; stats never.
- **LIST_NPC.CHR entry:** skeleton, model parts, and the **anim slots**. Skills hide here:
  a monster casts on slot `nMotion` and releases on `nMotion + 1`, so pairs at 6/7 and
  8/9 are its skills even when the AI that cast them is missing. For each clip, check
  whether we ship it (same path under `data/`) and read its frame events
  (`rosefmt.zmo.events`).
- **What each skill was.** A release clip we also use for a player skill identifies the
  skill: find the clip's FILE_MOTION row, the TYPE_MOTION row that points at it, and the
  LIST_SKILL rows whose col 68 is that TYPE_MOTION row. That is how the Shadow Soldier's
  slots turned out to be Impact Wave (`s_holysword01`) and Lightning Crasher
  (`s_rightingcration`) -- names the user did not recognise from the animations alone.
- **The weapon** (col 5 -> the source's LIST_WEAPON row and its LIST_WEAPON.ZSC object):
  compare its mesh and texture paths with ours. Same mesh + same texture means we have it;
  same mesh + another texture (Jrose's rusted Dairo) means a new item.

## 2. Pick the rows

- **LIST_NPC:** the source's number if it is blank here and has no CHR entry; otherwise
  the first free run (name blank **and** CHR hole) near related monsters, leaving room
  for the source's siblings. Never a row that only looks blank: check the CHR too.
- **LIST_SKILL / FILE_AI / AI_s.STB:** append (one past the end). Monster skill keys are
  `LMobSkill<row>`.
- **LIST_WEAPON:** a blank row **under 1000** in the weapon type's band (an id above 999
  cannot drop or be a reward). Look for gaps after the type's last row.

## 3. The model

`rosedata.import_characters([our_row], ours, src, dry, name, src_of={our_row: src_row})`
copies the CHR entry with every index remapped and brings the missing meshes/textures.
Then `add-dds-mipmaps.py --subdir <folder>` on every folder it copied textures into.

A clip you change (split, loop, new events) becomes **this monster's own copy** under
`3Ddata\MOTION\NPC\<NAME>\`, and its CHR slots are repointed (`set_clip_slots` in the
Shadow Soldier script). Never edit a shared clip: players or other monsters use it.

## 4. The weapon (when it has one we lack)

`import-item.py --type weapon --source <dump> --source-row N --art-only --template-row T
--target-row R --name ... --desc ... --icon I`, called from the import script (see
`sword()`):

- `--art-only`: only the model and texture come across; every stat is cloned from our
  row T. Never import a foreign weapon's stats: its ability ids can corrupt character
  state (`scripts/CLAUDE.md`, Item Import Tooling).
- **Template:** our weapon of the same type whose required level (col 20) is nearest under
  the monster's level.
- **Icon:** a row of ours on the same mesh, until someone draws one.
- The weapon row also decides how the monster's hits look and sound (LIST_WEAPON
  39/40/42), so a real weapon row gives it a proper impact.

## 5. Stats

The live level trend times a role profile, frozen in the script:

1. The trend at level L: the **median** of each stat over plain-role (mark 1-7) spawned
   monsters within L +/- 10, excluding `balance-trend-exclude.py` rows. HP is per level
   (col 8 x level = max HP). The query: `combatsim.sweep.spawned_monsters(GameData())`,
   then the medians (as `rebalance-monster-roles.py` `plan()` does).
2. Times the role's `TARGET` row in `rebalance-monster-roles.py` (Guard, Warrior,
   Magician ... bronze/silver/gold star).
3. EXP is only seeded (`rebalance-exp-rewards.py` owns it).
4. Copy a **template row** of ours at about that level with the right body type, for the
   cells we do not set (sounds, death effect, drop table); blank the template's sounds
   if they do not fit (a beast's grunts on a human).
5. Add the row to `balance-trend-exclude.py`.

## 6. The skills: three variants

Decide per skill with the user:

| Variant | What it means |
|---|---|
| **1. Interactive** | we author the skill around a ground telegraph (or another mechanic) |
| **2. Legacy** | the source's cast/release pair, made to work, no telegraph |
| **3. None** | the monster fights with normal attacks only |

A monster can mix them (one interactive skill, one legacy). Any skill row is a **copy of
one of ours of the same type**, then overwritten (`skill_row()`); never the source's row.

### Variant 1: interactive (telegraphed) skills

What exists (LIST_SKILL **col 83 = 1** draws it on the ground while the monster casts; the
client's `groundtelegraph.h`):

| Shape | Type (col 5) | Scope (col 8) |
|---|---|---|
| circle around the caster | 17 | radius in cm (e.g. 800) |
| cone toward the target | 7 | `100000000 + length_cm * 10000 + full_angle_deg` |
| frontal strip ("line") | 7 | `length_cm * 10000 + width_cm` |

The cone and the strip are aimed at where the target stood **when the cast began**;
moving out during the wind-up is the dodge. **Soaks, stack markers, chained areas and
anything else are not built**: they need server and client code first.

How the timing works, and therefore how to cut the clips:

- The telegraph is drawn for **one play of the cast clip** (slot `nMotion`, at the cast
  speed in col 53), then flashes. The server applies the damage **when the action clip
  starts**. The cast clip *is* the wind-up the player reads: aim for **1.5-2.5 s**.
- The action clip (slot `nMotion + 1`) should reach its blow as early as possible, or the
  digits come late after the flash. Two ways:
  - **Split** the release clip just before the blow with `rosefmt.zmo.sliced` (the raise
    becomes the cast, the slam the action). Find the split by measuring per-frame bone
    rotation (`rosefmt.zmo.frame_values`): the blow is a spike, the wind-up before it is
    calmer. Shadow Soldier: `s_holysword01` split at frame 21.
  - **Loop a quiet cast clip** with `rosefmt.zmo.joined` when the release is active from
    frame 0 (a leap). Check the seam first (last frame vs first frame, near zero degrees).
    Shadow Soldier: `near_casting01` x5. Then speed the release up with col 69.
  - A joined clip of two *different* clips pops inside the clip (no blending), so join only
    a clip to itself or poses that match. Between the cast clip and the action clip the
    engine blends, so a mismatch there is fine.
- **Events in the action clip:** the area event is **24** for both type 17 and type 7 (25
  takes the single-target melee path). 74 plays casting effect 2 (cols 62-64) at the blow;
  44 on the cast clip plays casting effect 0 (cols 56-58). Clear events you do not want
  (`cleared()`).
- Size the area for the body: radii are measured from the caster's centre. Gate the AI's
  cast on the target being **inside** the area (reach a metre or two under the radius).

### Variant 2: legacy skills

Keep the source's pair if the release clip has an event that presents the skill (24/34
projectile, 25/35 or 10/20 strike, 26 gun; `making-monsters.md` section 3). If it has none, give the
monster its own copy with the event added, or pick another clip. Statuses go in col 11
(13 success, 14 seconds). Run `audit-ai-skill-refs.py` and read its release-clip warnings.

### Skill damage (all variants)

- **Use the magic formula (col 15 = 2) for an elite or boss.** The physical formula adds
  0.2 x the monster's ATK to the power (241 at ATK 1207), so it floors high and barely
  follows the power: the Shadow Soldier's first cut at physical 200 took 40% of a squishy
  character's HP, and halving the power took off only a quarter of that. Magic damage is
  proportional to the power.
- **Size against a peer.** Find a spawned monster of the same level and role that casts an
  area skill, run both in the combat sim with the same auto-builds, and compare. A
  dodgeable skill hits harder than a peer's undodgeable one (~1.5x).
- Effects attached to a character (cols 56-67, 74, 77, 80) must be **one-shot**: every
  `.ptl` sequence `loops 1` (`rosefmt.eft.read` -> `rosefmt.ptl.parse`).

## 7. The AI

First the choice: the source's AI or ours (below, "Taking the source's AI, or not"). An
authored AI is built in the script with `import-hebarn.py`'s encoders (`heb.pat`, `heb.ev`, `c_*`, `a_*`)
and `audit-ai-monster-refs.py`'s `build_aip`; registered in FILE_AI and LIST_NPC col 16.
The Shadow Soldier's `build_ai()` is the template:

- `created` and `stop`: seek; `stop` also leashes (a regen spawn never runs `created`).
- `attack move` (runs only while it chases): leash, and a chase skill if it has one.
- `damaged` (header `(n, 2, 100)` = every hit taken): first match wins, so in order:
  the once-per-life event (HP threshold, var 4), the skills on a hit counter (var 2 >=
  N; var 3 alternates which comes next), retaliate, count.
- `kill`: a line, if it wants one. Lines are AI_s.STB rows; kind 0 = local chat.
- **Size N with the sim**: a solo fight's length decides how many casts a player sees.
  At 10 the Shadow Soldier showed one skill per 10 s fight; at 5, both.

### Taking the source's AI, or not

When the survey shows a shipped `.aip`, summarise it for the user (its casts, its summons,
its HP phases) and let them choose:

- **Take it** when its behaviour is what they want -- typically a monster left legacy
  (variant 3) or kept close to the original. Copy the file, register it, then run
  `audit-ai-skill-refs.py` (`--remap` for skill ids that mean something else here,
  `--remotion` for a slot layout that does not match the model) and
  `audit-ai-monster-refs.py`. Every skill and monster id in it is the source's
  numbering: a cast needs its skill imported or remapped, a summon needs that monster
  imported too (or the action stripped). Then check its throttles the way
  `fix-boss-cast-cooldowns.py` describes (casts that lock after one use, gates nobody can
  pass).
- **Author ours** when the skills are being made interactive (variant 1) or the source's
  behaviour is not wanted -- the Shadow Soldier's case. The shipped file is still worth
  reading for its design: which skill it opens with, its HP thresholds, what it summons.
- **Mix**: start from ours and borrow one idea from the source (an HP phase, a summon),
  written with our encoders.

## 8. Check, deploy, test

1. `import-<name>.py --dry-run`, then a real run, then `--verify`.
2. `audit-ai-skill-refs.py --dry-run`, `audit-ai-monster-refs.py --dry-run`,
   `audit-spawned-npcs.py` (once it is spawned).
3. `combat-sim.py ai --mob <row>` (the AI reads as intended), then
   `combat-sim.py new --job J --level L` and `run --mob <row> --play typical` for a few
   classes (Knight 121, Mage 221, Raider 321, Scout 322, Artisan 422).
4. Bake: `scripts/pack.ps1 -out build\bake-<name>`; copy `data.idx` and every
   `rose*.vfs` into `C:\Users\Thomas\Desktop\ROSEProject` (client and servers stopped).
5. Restart the servers (they read LIST_NPC, the CHR, LIST_SKILL, FILE_AI, AI_s, the
   `.aip` and the clips). Test with `/mon <row> 1` on a character **of the monster's
   level** (a 240 takes nothing and resists every status from a level-190 monster).
6. Commit after the user has seen it in game.

## Starting a new import script

Copy `scripts/import-shadow-soldier.py` and change, top to bottom: `DEFAULT_SRC`, the
monster block (rows, names, STL key, `TEMPLATE`, `STATS`), the weapon block (or drop
`sword()`), the skill blocks and `SKILLS`, `CLIPS` and `build_clips()` (each source clip
is checked against its expected frame count and events, so a different dump refuses
instead of cutting the wrong frames), the AI constants and `build_ai()`, and the
docstring. Keep `keep_originals` / `sweep_baks` / `verify` as they are.
