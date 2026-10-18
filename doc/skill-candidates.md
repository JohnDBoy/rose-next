# Skill Candidates by Class

A running list of skills in the reference dumps that could become new skills here,
kept so a class pass starts from a shortlist instead of a fresh survey. Started
2026-10-17 during the Champion and Artisan passes.

**How to read it.** A candidate is worth something only if it *looks* different from
what the class already has, so each entry says where its animation and effects come
from: *new* means a file we do not ship, *ours* means a file we already have (and,
usually, a look some existing skill already uses). Every gameplay number is always
ours; only presentation is taken. The import method and its traps are in
[skill-import-investigation.md](skill-import-investigation.md); the worked examples are
`scripts/import-champion-skills.py` (668) and `scripts/import-raider-skills.py` (Jrose).

Dumps: `668` = official Rednim client (`Testclients/668/Extracted`), `667` = the Evo test
client, `Jrose` = the Japanese 2024 dump (`Testclients/Jrose`, cp932, see
`scripts/rose-data-reader.py`). QQ-iROSE was checked and adds nothing (one dual clip
Jrose also has, one Muse buff).

## Done

| Class | Skill | From | Script |
|---|---|---|---|
| Champion | Voltage Crush, Dance of Flames, Final Strike | 668 + a never-shipped clip | `import-champion-skills.py` |
| Artisan | Calibrated Burst | RoseZA | `import-artisan-skill.py` (+ `add-calibrated-burst-book.py`) |
| Artisan | Photon Cannon (Jrose's Photon Wave, made single-target) | Jrose | `import-artisan-photon-cannon.py` |
| Bourgeois | Exceed Break (launcher, Burning splash, costs Zuly) | Jrose | `import-exceed-break.py` |
| Artisan | Calibrated Burst: new "Nightmare" look (effects only) | Jrose | `import-exceed-break.py` |
| Raider | Eruption (katar area), Shun'ei-zan (dual, critical burst) | Jrose | `import-raider-skills.py` |
| Scout | Arrow Shower (area, poison), Deadly Snipe (bow finisher) | 667 + Jrose | `import-scout-knight-skills.py` |
| Knight | Volcanic Shot, Star Gazer (crossbow) | Jrose | `import-scout-knight-skills.py` |
| Mage | Diabolos' Curse (dispel + slow), Shadow Servant (area nuke) | Jrose | `import-mage-knight-skills.py` |
| Knight | Shield Bash (requires a shield, scales with it), Gaia Presser (1H area) | 667 + Jrose | `import-mage-knight-skills.py` |

## Artisan (gun + launcher)

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| ~~Photon Wave~~ | Jrose 4271 | | | **Done** as Photon Cannon. Note for the two below: the cannon clips are **already ours** now, and a type-3 version needs the shot clip's fire event (26), which our copy has |
| Frost Edge Shot | Jrose 6161 (Artisan, gun, lv 210) | new (the same cannon set) | 4 new files (ice bullet) | Defense Down + slow on the enemies around the target |
| Sleeping Phantom | Jrose 6171 (Artisan, launcher, lv 210) | new (cannon set) | 11 new files (Sandman smoke) | Sleep + Defense Down |
| Daze Attack | 668 2680 | ours (Gun Smash's) | ours | Could take our unused `skill_Uppercut_01` instead: a rifle-butt uppercut |
| Acid / Poison / Magic Shot | 668 2685-2695 | ours (Aim Point's) | ours, identical for all three | Only the numbers differ in 668 |
| Hypno Shot | 668 2675 | ours (Aim Point's) | Curse's projectile + an unused poison splash | |
| Summon Aurum Sentry | 668 2710 (NPC 776) | -- | -- | A placeable sentry (668: detects stealth). As a gun turret it is the Artisan's best identity, but needs its own AI file (668 ships none) and summon tuning |

## Bourgeois (launcher)

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| ~~Exceed Break~~ | Jrose 6151 | | | **Done** (`import-exceed-break.py`), as a type-3 shot with Fire Burn's fireball. **Not what Jrose built, and kept that way (user, 2026-10-18):** Jrose's LIST_EFFECT 330 is *named* Exceed Break -- `dragon_firing_hit02`, a blast that a type-7 skill plays at the target spot (its test rows 6211-6213), not a projectile; 6151's scope `40002500` is a packed ~40 x 25 m frontal rectangle our engine cannot do. A type-7 blast test (6 m on the spot, Jrose's untouched m03 with area event 24 -- our shared copy carries Photon Cannon's 26) looked no better in game. Revisit only with a frontal-area shape ("fancy stuff later") |

## Champion

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Unnamed 2H-sword skill | Jrose 4340 (Champion, lv 190, area) | **new**: `THS_U_SKILL02` | 8 new files | No name in Jrose's STL |
| Unnamed axe skill | Jrose 4343 (Champion, lv 190) | **new**: `THA_U_SKILL03` | ours | `rosefmt.zmo` cannot read the clip's events -- check before use |
| Dance of Wind / Ice | 668 715 / 720 | ours (Spin Attack's) | ours | Dance of Flames' siblings |
| Seismic Strike / Impact | 668 670 / 675 | ours (Impact Wave's) | ours (Moss Golem / Vivec bursts) | 2H-sword area |
| Axe Wrath, Axe Launcher | 668 765 / 760 | ours | ours; Axe Launcher's projectile unchecked | |

## Raider (katar / dual)

Both Jrose Raider skills are **done** (`import-raider-skills.py`); no dump has another new Raider clip.

## Scout (bow / crossbow)

Surveyed 2026-10-18 (Jrose, 667, 668). **Done:** Arrow Shower, Deadly Snipe (Scout), Volcanic Shot, Star Gazer (crossbow Knight) -- `import-scout-knight-skills.py`. Traps are next for the Scout, later (they need AI and code). The Scout's exclusives are Poison Arrow, Detect,
Sharpen Arrow, Hawk Shot and Call Hawk; its other bow skills are shared Hawker ones.

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Arrow Shower | 667/668 1870 (bow), 1920 (crossbow) | **new**: `bow_arrowshower_m1` (0.7 s) | **ours, unused**: `_ARROW_RAIN_01.eft` (rain), `_scope_rotate_01`, `_bow_casting_01`, `_bow_hit_heavy01` | Type 7 rain, 15 m in 667. LIST_EFFECT 279 / FILE_EFFECT 2018 are blank here. 667's Poison Arrow Shower (4706) is the same with poison |
| Traps (Steel, Flash, Siphon, Freezing, Sand) | 667/668 1950-1960, 2145-2150 | -- | -- | Type 14 summons of trap NPCs 2800-2820. Our `NPC/ETC/TRAP` mesh, bone and 3 textures sit **orphaned** (no CHR entry); 667 adds 2 textures and 3 motions. 667 ships no AI, so the trap AI is ours to write. Stationary summons already work (the Bonfire) |
| Star Gazer | Jrose 6121 (crossbow, lv 210) | ours (`hoke_firing01`) | 38 new files (star-shard rain) | Area: slows, lowers defense |
| Deadly Snipe | Jrose 6111 (bow, lv 210) | ours (`bow_3attack`, the triple shot) | 9 new files (heavy arrow) | Strong volley, Dodge Down and a short stun |
| Volcanic shot | Jrose 5202 (crossbow, lv 170) | ours (`bowgun_3attack`) | 2 new (`volcanic_bullet.eft`) | A meteor bolt that lowers Attack Power |
| Angel Arrow | Jrose 4301 (bow, lv 100) | **new**: `HAWKER_U_SKILL_BOW03` (2.7 s) | 4 new files | Party HP/MP regeneration |
| Doping Shot | Jrose 6131 (crossbow, lv 210) | new (same clip) | 4 new files | Party buff: ATK, DEF and Movement Speed |
| Shot Master | Jrose (crossbow, not class-gated) | **new**: `MASTAR_BOWGUN_SKILL_02` (1.9 s aim, one shot) | -- | Not traced yet |
| Stun Arrow | 668 1595 (Hawker, bow) | **new**: `kneel_bow_cast` | ours | A kneeling shot |
| Zero Range Shot | Jrose 4291 (crossbow) | `skill_Longinus_01` -- **now Final Strike's** | 3 new | Skip: it would look like the Champion's skill |

## Knight (melee)

Surveyed 2026-10-18; **done:** Shield Bash and Gaia Presser. **A skill can require a shield**: col 30 = 261 matches the off-hand
(`CUserDATA` need-weapon check compares `SUBWPN_TYPE(L)` too).

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Shield Bash / Lunge / Throw | 667/668 575 / 570 / 580 (Knight, shield) | **ours, unused**: `s_shielda_m1` (2.0 s, three blows) -- no skill plays it | ours (`_shiedla_01`, `image_cut_*`) | Zero new files. Bash stuns 2 s, Lunge debuffs, Throw reaches 15 m. One clip for all three |
| Third Step | Jrose 481 (Knight, 1H sword / mace, lv 100) | **ours, unused**: `skill_ThirdStab_01` (3 stabs) | ours | Slows Movement and Attack Speed. Zero new files |
| Gaia Presser | Jrose 6031 (Knight, mace, lv 210) | ours (spin attack) | 7 new | Area: Defense and Movement Speed down (Jrose also raises your ATK) |
| Gale Smash | Jrose 6021 (Knight, 1H sword, lv 210) | ours | 9 new | A draining strike. Drain heals are never announced to the client (open item) |
| Shield Reflect | 667 565 | ours | ours | Self buff |
| Rain of Arrows | 667 620 (crossbow) | `bow_arrowshower_m1` (now ours: Arrow Shower) | | Same look as Arrow Shower |

## Mage / Cleric / Muse

Surveyed 2026-10-18 (Mage); **done:** Diabolos' Curse and Shadow Servant. **Dispel works**: LIST_STATUS 37 "Dispelled" (ING_CLEAR_GOOD)
strips every beneficial status; only monster skills use it today.

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Diabolos' Curse | Jrose 4251 (Mage, staff, lv 180) | **new**: `skill_magic_abnormality_m02` (0.9 s) | 13 new (pentagram + demon-fire bolt, `muse_skill01*`) | Strips the target's buffs and slows it -- no player skill dispels |
| Shadow Servant | Jrose 6061 (Mage, staff, lv 210) | ours (`extent_skill01`) | 7 new (a dark cross) | Type 7 area nuke; Defense, Magic Resistance and Accuracy down (two fit) |
| Hailstorm | 667 915 (Muse) | ours | 6 new | Around you |
| Frost Ring, Elemental Wave | 667 1190 / 1265 (Mage) | ours | 5 / 3 new | Around you |
| Holy Heal | Jrose 1331 (wand, lv 220, no class set) | **new**: `MASTAR_WAND_SKILL_03` | 7 new | Cleric material (the Cleric is being redone) |

## Hunting for more

- `doc/skill-import-investigation.md` §7 holds the 667 shortlist this file absorbed.
- Jrose has ~2,800 skills we do not, but most reuse animations we already ship. The
  scan that found the new clips compares each dump's `MOTION/AVATAR` against ours and
  maps the missing clips back through `TYPE_MOTION` / `FILE_MOTION` to the skills
  that play them; 295 Jrose clips are missing here, almost all emotes and dances.
- Our own data holds clips no skill uses (`skill_Uppercut_01`, `skill_ThirdStab_01`,
  `skill_Prick_01`, `skill_Slice_01`, `skill_ThrowAxe_01`, `bliding_01`,
  `s_blindblade_m1`). Final Strike's `skill_Longinus_01` came from that pool.
