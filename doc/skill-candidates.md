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
`scripts/import-champion-skills.py` (668) and `scripts/artisan-bazooka-test.py` (Jrose).

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
| Exceed Break | Jrose 6151 (Bourgeois, launcher, lv 210) | new (cannon set) | 2 new files | Wide barrage that sets enemies burning. Shares the Artisan's clips, so it costs little once Photon Wave is in |

## Champion

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Unnamed 2H-sword skill | Jrose 4340 (Champion, lv 190, area) | **new**: `THS_U_SKILL02` | 8 new files | No name in Jrose's STL |
| Unnamed axe skill | Jrose 4343 (Champion, lv 190) | **new**: `THA_U_SKILL03` | ours | `rosefmt.zmo` cannot read the clip's events -- check before use |
| Dance of Wind / Ice | 668 715 / 720 | ours (Spin Attack's) | ours | Dance of Flames' siblings |
| Seismic Strike / Impact | 668 670 / 675 | ours (Impact Wave's) | ours (Moss Golem / Vivec bursts) | 2H-sword area |
| Axe Wrath, Axe Launcher | 668 765 / 760 | ours | ours; Axe Launcher's projectile unchecked | |

## Raider (katar / dual)

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| **Eruption** (Irapushon) | Jrose 4321 (Raider, katar, lv 180) | **new**: `HAWKER_U_SKILL_KATAR03` | ours | "Ultra-fast combination slashing every enemy in range" |
| **Shun'ei-zan** (Shadow Flash Slash) | Jrose 4311 (Raider, dual, lv 200) | **new**: `HAWKER_U_SKILL_DSW03` | 4 new files | "A shadow dashes past faster than the eye; heavy damage on success" |

## Scout (bow / crossbow)

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Angel Arrow | Jrose 4301 (Scout, bow, lv 100) | **new**: `HAWKER_U_SKILL_BOW03` | 4 new files | A party heal over time: an arrow of light rains blessing |
| Doping Shot | Jrose 6131 (Scout, crossbow, lv 210) | new (same bow clip) | 4 new files | Party buff: ATK, DEF and Movement Speed |
| Shot Master | Jrose (crossbow) | **new**: `MASTAR_BOWGUN_SKILL_02` (0.4 s) | -- | Not traced yet |
| Arrow Shower | 667 1870 | **new** motion `bow_arrowshower_m1` | | From the 667 shortlist |

## Knight

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Rain of Arrows | 667 620 (crossbow) | **new** motion `bow_arrowshower_m1` | | Area for the crossbow Knight |
| Shield Reflect | 667 565 | ours | `_reflect_01.eft` (new) | |

## Mage / Cleric / Muse

| Skill | From | Animation | Effects | Notes |
|---|---|---|---|---|
| Diabolos' Curse | Jrose 4251 (Mage, staff, lv 180) | **new**: `SKILL_MAGIC_ABNORMALITY_M02` | 13 new files | Strips the target's buffs and slows it |
| Holy Heal | Jrose 1331 (wand, lv 220, no class set) | **new**: `MASTAR_WAND_SKILL_03` | 7 new files | Heals allies around you; you cannot move while it runs (Cleric material) |
| Hailstorm | 667 915 (Muse) | ours | 6 new files, 5.3 KB | The cleanest import found in 2026-08 |
| Frost Ring, Blaze, Elemental Wave | 667 1190 / 1250 / 1265 (Mage) | ours | 1-2 new effects each | |

## Hunting for more

- `doc/skill-import-investigation.md` §7 holds the 667 shortlist this file absorbed.
- Jrose has ~2,800 skills we do not, but most reuse animations we already ship. The
  scan that found the new clips compares each dump's `MOTION/AVATAR` against ours and
  maps the missing clips back through `TYPE_MOTION` / `FILE_MOTION` to the skills
  that play them; 295 Jrose clips are missing here, almost all emotes and dances.
- Our own data holds clips no skill uses (`skill_Uppercut_01`, `skill_ThirdStab_01`,
  `skill_Prick_01`, `skill_Slice_01`, `skill_ThrowAxe_01`, `bliding_01`,
  `s_blindblade_m1`). Final Strike's `skill_Longinus_01` came from that pool.
