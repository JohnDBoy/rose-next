# 668 Survey (official Rednim client)

**Status:** survey only. Nothing has been imported and no data or code was changed.
Import was deferred on 2026-10-16.
**Date:** 2026-10-16.
**Dump:** `C:\Users\Thomas\Desktop\Testclients\668\Extracted`
**Compared against:** the 667 test client, `C:\Users\Thomas\Desktop\Testclients\667\extracted data`

---

## 1. Verdict up front

**668 is not "667 plus one".** It is a different line of the game. 667 is a late
evolution-era private build, with VFS dates from 2018–2019. 668 was dumped on
2026-09-24 from the **official Rednim Games client** (`dump.log`: profile `rednim`,
an encrypted `data.idx` plus a single ~3.5 GiB `rose.vfs`). It is the newer of the
two and carries real new content:

| | |
|---|---|
| New zones | **Orlo Clan Field** (ORLOCF) + its temple (ORLOCFBOSS), **Age of Zatana** (ZATANA), 5 CvC arena rows, a Birth Island stress test |
| New monsters | Level 265–275 dinosaur tier (Enraged / Scorched / Primal), the boss **Zatana**, Pterodactyl, Aurum Sentry summon |
| New systems | Quest tracker, boss-summon effigies (`LIST_MONSTER_SPAWN`), refine table, duel consumables, hair colours |
| New items | Dinosaur weapon tier, three costume weapon sets, ~130 cart parts, 66 effigy use items |
| Retuning | EXP changed on ~1,150 monsters (median x1.15); drop columns on ~1,200 |
| Pruning | Item tables lost 30–60 % of their rows (Brave* / Old* weapons, most armour duplicates) |
| Assets | ~5,000 textures re-saved **with full mip chains**. Same art, not new art |
| Still missing | No `.AIP` AI. Dialogs are encrypted `.CXE` (427), not `.CON`. These are the same gaps as 667 |

If anything gets imported, the best candidates are **Zatana** (it ships `.MOV`
walkability, which 667 never had) and **Orlo Clan Field**, together with the dinosaur
tier that lives there.

**Imported so far:** the 15 unique weapons we were missing (violet name, stat
requirement only), at their retail item numbers 904-995 with stats scaled onto our
own unique ladder: `scripts/import-668-uniques.py` (2026-10-16). Not yet on any drop
table. Still available in the same family: the level-200 uniques (908, 915 … 999).

---

## 2. How to read this dump (traps)

1. **Missing from 668 almost never means missing.** The Rednim index stores only
   `blake3(lowercased path)`, so the dumper had to *guess* paths. It recovered
   **43,525 of ~49,658** entries. Of the 4,911 files that are in 667 but not in 668,
   only **8** are confirmed absent: they appear in `Extracted\noexist.json`, which
   lists paths the dumper probed and the index rejected. The rest were never probed.
   That covers 31 STBs such as `LIST_CNST_*`, `LIST_TERRAIN_OBJECT_*`,
   `LIST_PARTICLES`, `FILE_SKEL` and `PART_NPC`. **Check `noexist.json` before
   concluding anything is gone.** The 8 confirmed absent are 5 files under
   `MAPS\ORO`, `LIST_CNST_ODD.ZSC`, `LIST_DECO_ODD.ZSC` and one `PAT\CART` file.
2. **The STLs are in `Extracted\LANGUAGE\`**, not next to the STBs. Language block
   **0 is Korean and block 1 is English** (7 blocks). Text is UTF-8 inside the
   latin-1 bytes, so decode with `s.encode("latin-1").decode("utf-8")`.
   `Stl.by_key(0)` returns Korean.
3. `noexist.json` is UTF-8. Open it with `encoding="utf-8"`, because the Windows
   default codec chokes on it.
4. Column labels are present in the STB headers (`Stb.colname`), and they are the
   most reliable guide to 668's new columns.
5. **Sound** appears only in 668 (`SOUND\`, 286 WAV + 30 OGG). That is an artifact of
   how 667 was extracted (its sound sits outside `extracted data`), not new content.

Every read here used `scripts/rosefmt` (`Stb`, `Stl`). No new parser is needed.

---

## 3. What changed, file by file

Raw counts: 37,004 paths are in both dumps. 30,173 of them are byte-identical and
6,831 differ.

| Kind | Changed | What it actually is |
|---|---:|---|
| `.DDS` | 5,122 | Mostly **mip chains added** (0 mips → 7–10) at the same size and format. 388 terrain tiles went DXT3/DXT1 → DXT5 with mips. 24 were resized (non-power-of-two → POT) |
| `.HIM` | 556 | Same size. ~27 % of heights moved, by **at most 0.84 m**. A light reshape in EJ01/EJ02/EJT01/EJ04/EZ01, LP01/LP02/LMT01/LPVP01/LSF01, JG01/JG05/JD01/JD02/JDT01/JPVP01/JPVP05 |
| `.IFO` | 558 | Object placements differ (243 change size) |
| `.ZSC` | 81 | Different object tables, e.g. `LIST_DECO_JG.ZSC` 94 KB → 53 KB |
| `.CXE` | 190 | Dialog changes (encrypted; not decoded) |
| `.QSD` | 97 | Every QSD the two dumps share differs |
| `.LIT` | 92 | Lightmap placement lists |
| `.STB` | 66 | Every STB the two dumps share differs. See §5 |

The mip-chain re-save is what our own full-mipmaps experiment explores. Rednim shipped it.

---

## 4. New zones

All five are in `LIST_ZONE` (col 0 = name, col 1 = `.zon` path).

| Row | Zone | Folder | HIM tiles | Files | `.MOV` |
|---:|---|---|---:|---:|---:|
| 15 | Birth Island | `MAPS\JUNON\BIRTH_ISLAND_STRESS_TEST` | 49 | 348 | 0 |
| 16 / 100 | Castle / (CvC) Castle | reuses `TITLE_JPT` | – | – | – |
| 89 | (ORLOCF) Orlo Clan Field | `MAPS\ORO\ORLOCF` | 25 | 234 | 0 |
| 90 | (ORLOCFBOSS) Orlo Clan Field Temple | `MAPS\ORO\ORLOCFBOSS` | 3 | 27 | 0 |
| 91 | (ZATANA) Age of Zatana (Free Tour) | `MAPS\ORO\ZATANA` | 64 | 737 | **64** |
| 174 | (ZATANA) Age of Zatana | same map as 91 | | | |
| 101–104 | (CvC) Lion's Plains, Sunshine Coast, Tree House, Title Map | reuse JPVP04, JB01, ELDEON\Title, TITLE_JG01 | – | – | – |
| – | (no zone row found) | `MAPS\LUNAR\WIN_EVENT_NEW` | 16 | 182 | **16** |

Zatana's objects table is `3ddata/oro/list_deco_orlo.zsc`. Oro is spelled **"Orlo"**
throughout 668's new content and renamed NPCs.

Map folders that exist only in 667 (AGIT02–04, JGT01, JZP_PVP01, LPVP05, WIN_EVENT,
ODC01, ODD01–03, ODE01) are most likely just unprobed paths (§2.1), not removed maps.

**`LIST_ZONE` grew from 48 to 79 columns.** The new columns are: Zone Leave Trigger,
Skill Rules, Duel Sessions, a Fog Override flag with density + RGB + min/max for each
of Morning/Day/Evening/Night, and a Script column.

---

## 5. Tables

### New tables (no 667 counterpart)

| Table | Size | Content |
|---|---|---|
| `QUEST_TRACKER` | 7,037 rows x 3 | Per-quest type (0 normal, 1 hero, 2 daily, 3 game arena, 4 repeatable, 5 event) + an objective STL key (`QTRK#####`) |
| `QUEST_TRACKER_ITEM` | 7,238 x 6 | Item ID, quest ID, amount, droppable flag, objective key (`IQTK#####`) |
| `LIST_MONSTER_SPAWN` | 74 x 5 | Name, NPC ID, quantity, map announcement, "block garden spawn". It backs the **Imbued Effigy** use items, which spawn a boss |
| `LIST_REFINE` | 18 x 20 | A "Refine 1–20" grid with values 1–3: a refine/upgrade tier table |
| `LIST_DUEL_CONSUMABLES` | 525 x 5 | Per use item: is potion / buff / offensive / summon. Says what is allowed in duels |
| `LIST_HAIRCOLOR` | 204 x 5 | Colour name, allowed at character create, allowed at style change |

### Tables that changed shape

| Table | Rows 667 → 668 (occupied) | Cols | Note |
|---|---|---|---|
| `LIST_ZONE` | 71 → 82 | 48 → 79 | §4 |
| `LIST_NPC` | 3,748 → 3,796 | 108 → 113 | §6 |
| `LIST_PAT` | 588 → 718 | 78 → 81 | +131 cart parts |
| `LIST_MOUNT` | 322 → 313 | 39 → 42 | |
| `LIST_USEITEM` | 2,732 → 2,284 | 42 → 45 | "Can Use Multiple" set on ~1,640 rows |
| `LIST_HAIR` | 105 → 185 | 43 → 45 | +80 hairstyles |
| `LIST_FACE` | 148 → 232 | 3 → 5 | +84 faces |
| `LIST_GAMEARENA` | 26 → 11 | 11 → 13 | |
| `TYPE_MOTION` | 185 → 222 | 20 | |
| `LIST_CAMERA` | 9 → 15 | 11 | |

### Item tables: pruned, with a new tier added

| Table | Occupied 667 → 668 | New rows (range) | Gone rows |
|---|---|---|---:|
| `LIST_WEAPON` | 6,210 → 3,978 | 79 (488–9494) | 2,311 |
| `LIST_CAP` | 3,101 → 1,771 | 282 (381–4594) | 1,612 |
| `LIST_BODY` | 2,662 → 1,780 | 319 (250–4596) | 1,201 |
| `LIST_ARMS` | 2,442 → 1,544 | 271 (250–4592) | 1,169 |
| `LIST_FOOT` | 2,702 → 1,687 | 298 (196–4596) | 1,313 |
| `LIST_BACK` | 2,539 → 1,137 | 107 (796–4519) | 1,509 |
| `LIST_FACEITEM` | 584 → 293 | 28 | 319 |
| `LIST_JEWEL` | 832 → 399 | 40 (300–617) | 473 |
| `LIST_SUBWPN` | 375 → 324 | 37 | 88 |
| `LIST_USEITEM` | 2,732 → 2,284 | 79 (357–3701) | 527 |
| `LIST_PAT` | 588 → 718 | 131 (1120–1818) | 1 |

Removed weapons include the whole **Brave** series (25–28, 54–57, 84–85, 123–126, …)
and the **Old** series (2013–2030). Rows 2001–2005 were renamed to test items
("One handed Blunt Test", …). Use items 441–499 (skill books / craft research) are gone.

The **weapon model column changed on 3,611 rows, but only the path prefix differs**
(`weapon\onehand\osw15\osw15.txt` → `3ddata/weapon/weapon/onehand\osw15\osw15.txt`).
That is not a real change.

Notable new items:
- **Dinosaur weapon tier**, `LIST_WEAPON` 1476–1488: Extinction Ruin, Fossil Endless,
  Saurian Eternity, Primal Cleave, Titan Unyielding, Ptero Pierce, Raptor Reverberation,
  Dino Rifter, Fossil Flare, Bone Shatter, Apex Savior, Jawbreaker Doon, Saurian Retribution.
- **Costume weapon sets**: Green Onion (9421–9433), Necro Requiem (9441–9454),
  Golden Sun (9461–9474), Dark Oblivion (9481+); Heart weapons 1733–1735; Phoenix (488);
  Unique Weapon Fragment (900).
- **Imbued \<Boss\> Effigy**, `LIST_USEITEM` 3001–3066: one per boss (Aplysia King …
  Wolf King, Varus, King Turak). They pair with `LIST_MONSTER_SPAWN`.
- **Carts**, `LIST_PAT` 1120–1818: Magic Bed, Flying Block Horse Carriage, Monkey
  Cart, UFO, Carp Cart, ~35 named cars (1201–1235), engines and wheels. PAT 191–194
  are named "Zatana Engine / Core / Legs / Arms Prototype". The matching cart boxes
  are `LIST_USEITEM` 2144–2147.
- `LIST_BACK` 401–402: Zatana Wing / Zatana Back.
- Return scroll 357: Ancient Oasis Shrine.
- Clan Point items 181–191 are now x100 (+10 → +1000 … +1000 → +100000).

---

## 6. New monsters and NPCs (`LIST_NPC`)

There are 80 new occupied rows; these are the named ones. Level is col 7 and EXP is
col 17. Col 8 is listed as found (probably HP).

| Row | Name | Lv | Col 8 | EXP | Role (col 0) |
|---:|---|---:|---:|---:|---|
| 776–780 | Aurum Sentry | 100 | 80–120 | 0 | Summon, 5 levels |
| 3891 | Enraged Mastyx | 265 | 644 | 128,717 | Guard |
| 3892 | Enraged Devourer | 265 | 581 | 132,370 | Warrior |
| 3893 | Enraged Terrasaurus | 265 | 518 | 109,414 | Basic |
| 3894 | Enraged Snapper | 265 | 511 | 98,382 | Basic |
| 3903 | Pterodactyl | 235 | 62 | 95,811 | |
| 3905–3908 | Scorched Mastyx / Duneclaw Devourer / Swampstalker Terrasaurus / Lavasurge Snapper | 275 | 12,320 | same as Enraged | |
| 3910–3913 | Primal Mastyx / Devourer / Terrasaurus / Snapper | 275 | 43,120 | same as Enraged | |
| 3914 | **Zatana** | 275 | 43,120 | 185,655 | Warrior (boss) |
| 3916 | Giant Cobweb | 250 | 100 | 0 | "Zatana Wall" NPC |
| 4401–4404 | Junon / Luna / Eldeon / Orlo Chest | 1 | 1 | 0 | |
| 4501–4511, 4601 | "Worm Dragon" | 95 | 66 | 0 | col 0 says Fairy Wing, Angel Wing, Astarot Wing, Jeff Backpack … These look like back-item display NPCs with a copy-pasted name, not monsters |

Rows 4069–4108 and a few others are occupied but have no English name.

These levels sit **above our 240 cap**, just as in Mors (see
[mors-survey.md](mors-survey.md)).

Renames worth knowing: 985 Giant Mother Choropy → Giant Choropy, 2125 "[Oro Bar Owner]"
→ "[Orlo Bar Owner]". Rows 2175–2176 and 2651–2657 now have names: Alexander
Coffington, Heatfist, the Scorpio / Golden Scarab family.

**Retuning on rows present in both:** EXP changed on 2,050 rows; 1,150 of them are
non-zero on both sides, with a median ratio of **x1.15** (range x0.10–x15.4), e.g.
(219) Shadow Ghost 76,622 → 119,824. All seven drop columns (91–101) changed on 1,196 rows.

---

## 7. New skills (`LIST_SKILL`)

There are 123 new rows. Named ones, with id ranges:

| Skill | Ids |
|---|---|
| Target Ally / Despawn Summons / Duel | 22 / 23 / 35 |
| **Monster Inspector** | 60. Rednim has its own; ours is 7001 |
| Dual Scratch / Stone Throw | 101 / 102. Dual Scratch moved from 100 |
| Jump | 21 (row existed in 667, unnamed) |
| Critical Chant | 2705–2709 |
| Summon Aurum Sentry | 2710–2714 |
| Terror Challenge, Crippling Strike, Judgment Cataclysm | 3007, 3008, 3009 |
| Seismic Challenge, Rending Bite | 3029, 3030 |
| Frost Nova, Cinder Pulse | 3047, 3051 |
| Astarot King's Jealousy (I/II) | 6376–6381 |
| Heal Dampening | 6800–6809 |
| Nausea I–V | 6810–6814 |
| Zen | 6906–6910 |
| Drop bonuses (Common … Legendary, Drop Quantity) | 8155–8187. They replace 667's 8147–8152 |

Renamed: Weapon Launcher (760–764) → **Axe Launcher**. Most other "renames" are
trailing-space cleanups.

---

## 8. Reproducing this comparison

Walk both trees into `{upper-cased relative path: file}` dicts, then hash the common
paths. To separate re-encodes from real art changes, compare each DDS header
(width, height, mip count at offset 28, FourCC at offset 84). For tables, load
both sides with `rosefmt.stb.Stb` and diff occupied rows. Get names from
`Stl(...).by_key(1)` on 668 (English) through the STB's `key_column()`. Before
calling a 667-only file "removed", check it against `noexist.json`.
