# Rose Data Tool — Project Memory and Plan

This file is the durable project memory for AI-assisted work on the Rose data
tool. Read it before continuing after a model/session change. Update decisions,
status, evidence, and the next action as work progresses; do not rely on chat
history as the only record.

## Goal

Build a standalone tool that lets users search and understand relationships
between quests, mobs, and items in Rose Next game data. The eventual goal is to
unify and replace the relevant capabilities of `quest-editor-ui.exe` and
`gm-item-browser.exe`. The standalone tool comes first; whether or how it later
integrates into the game client is undecided.

The tool should support both end users discovering content and developers
inspecting and maintaining game data, with equal importance. The exact
permissions and workflow for any future in-game feature remain open.

## Confirmed decisions

- **End state:** unified replacement for relevant quest-editor and
  gm-item-browser workflows, not just a companion search page.
- **First proof of value:** cross-domain search across quests, mobs, and items.
- **Initial behavior:** read-only search and inspection. Editing is a later
  phase, not a prerequisite for the search MVP.
- **Data authority:** static game data files; do not depend on a live server or
  database for the initial tool.
- **Input layouts:** support both loose extracted data and packed `data.idx` /
  VFS data, reusing existing code where possible.
- **Foreign data:** default to Rose Next data. Also support opening other client
  dumps to examine quests and, in a later import/porting workflow, bring
  compatible quests into Rose Next. Initially support only foreign clients
  already represented in our sources; do not add support for new client formats
  yet.
- **Audience:** give end users and developers equal support; neither is the
  secondary audience.
- **Coverage:** aim for robust discovery across all relevant static data. If
  existing readers or scripts miss sources, fix or extend them and add
  regression checks. Report any remaining gaps instead of silently treating
  them as absent.
- **Text encodings:** do not assume one encoding for every file or client.
  The local data includes UTF-8 STL text, CP949 AI labels, wide UTF-16LE
  `ULNGTB` dialog strings, and narrow CP949 `LNGTB` strings. Foreign client
  dumps may use other supported codecs. Use the source/file-specific codec,
  preserve undecoded bytes and provenance when decoding is uncertain, and
  never silently discard text.
- **Mob-AI cascades:** include mobs spawned by another mob's AI on attack or
  death, and items granted/dropped by that AI outside `ITEM_DROP.STB`. Follow
  the chain through each spawned mob's own AI and its possible spawns/items;
  `ITEM_DROP.STB` is not a complete drop inventory.
- **Integration:** standalone first. Decide about in-game use only after the
  standalone experience is proven.
- **Existing tools:** keep them available while the new tool is developed;
  replacement/cutover is a later decision.

## Working principles for AI contributors

- Verify current code and data behavior before treating notes here as fact.
- Reuse existing codecs/readers, especially `scripts/rosefmt` and `scripts/rosedata`.
  Do not implement another parser for a format that already has a supported codec.
- Improve supporting readers, audits, or scripts when they prevent complete and
  accurate data discovery; test fixes against real data and preserve their
  existing safety guarantees.
- Preserve provenance for every result: source file, row/key/trigger, and how
  the relationship was derived.
- Distinguish confirmed relationships from inferred, incomplete, or unresolved
  ones. Never invent a quest giver, spawn source, reward, or map association.
- Start read-only. Before any future write feature, require validation, a clear
  diff/preview, backups, and a recoverable change record.
- Keep this document useful as memory: record durable decisions and blockers,
  not every transient implementation detail. Link to subsystem documentation
  for deeper technical notes.

## Product scope

### First milestone: read-only cross-domain search

Users should be able to search by the names/IDs and relevant attributes of
quests, mobs, and items, then follow verified links between them:

- **Mobs:** name/ID, level, map/spawn source, associated quest/event logic, and
  related drops or rewards where the data supports those links. Follow
  attack/death AI actions transitively: a mob may spawn another mob, whose own
  AI may spawn more mobs or grant items.
- **Items:** name/type/ID, mobs that drop them, quests that grant or require
  them, and AI-scripted sources outside `ITEM_DROP.STB` where verifiable.
- **Quests:** name/ID, level/requirements, map or event context, giver/turn-in
  source, objectives, and rewards where verifiable.
- **Relationships:** navigate quest ↔ mob ↔ item links, with their provenance
  and confidence/limitations visible. Show the triggering AI/action and
  conditions along cascade paths, and handle cycles without losing alternate
  provenance paths.

The first milestone is not just text search. It must demonstrate useful
cross-domain navigation while retaining a way to inspect the underlying record.
After the source inventory, choose representative real quest/mob/item examples
that exercise the different relationship paths; these become acceptance cases.
The user does not need to know the example IDs before that inventory.

#### User-provided quest test scenarios

Resolve these descriptions to exact quest names/IDs and relevant NPCs from the
default Rose Next data during the source inventory:

- A level-1 NPC gives new players food, with availability limited by a level
  threshold.
- An NPC gives a quest to deliver a price chart to Zant.
- An NPC starts a main/episode quest about talking to Sayon about a problem.
- An NPC gives Dealer training.
- An NPC gives Soldier training.

These are candidate acceptance cases, not yet verified quest titles or IDs.
After mapping them, propose additional real quests to cover relationship paths
or edge cases missing from this set; review the combined test list with the user.

### Later milestone: safe editing

- Support editing existing quests, not only creating new ones.
- Support examining quests from other client dumps and importing/porting
  compatible quests from client formats already represented in our sources into
  the default Rose Next data set. Identify source/target differences,
  unsupported features, and required conversions; never assume a foreign quest
  can be copied unchanged. Do not implement new client formats at this stage.
- Decide which related mob/item edits belong in scope after the search model is
  proven.
- Validate all affected references and show a diff before saving.
- Back up changed files and record what changed and why.
- Define delete semantics carefully; never imply that deleting one record
  automatically cleans up every reference unless that is verified.

### Deferred

- In-game/client integration.
- Replacing or removing the existing tools before feature parity and migration
  needs are understood.
- Any live server/database dependency.

## Existing tool baseline (verified so far)

### `quest-editor`

See `src/tools/quest-editor/PROGRESS.md` and the crate under
`src/tools/quest-editor/`.

- It has a QSD codec/verification CLI and a GUI quest creation workflow.
- It reads quest, NPC/monster, and item tables; it also has quest classification,
  dialog/IFO support, and data-writer code.
- It can manage quests created by the editor (the `QX-<SN>.QSD` convention),
  including edit/recreate and delete workflows. It does **not** provide a
  general-purpose editor for arbitrary pre-existing retail quests.
- Its current implementation is therefore more capable than “new quests only,”
  but still does not satisfy the broader existing-quest editing/search goal.
- Its existing QSD, STB/STL, dialog, and IFO work is potential reusable prior
  art; inspect boundaries before deciding whether to reuse or replace it.

### `gm-item-browser`

See `src/tools/npc-shop-editor/README.md` and
`src/tools/npc-shop-editor/src/`.

- It is read-only and catalogs item and monster rows from static data.
- Item search includes names/IDs and item attributes; monster search includes
  names/IDs, level/HP/status filters, validation checks, and optional previews.
- It supports loose extracted data and `data.idx`/VFS input, and reports data
  warnings.
- It is aimed at tester `/item` and `/mon` commands. It does not currently
  provide the requested item-drop/quest-reward relationship search or full
  quest discovery.
- The NPC shop editor in the same crate is a separate editor for shop tables;
  do not conflate it with the read-only GM browser.

## Initial data-source map (partially verified)

Use the existing readers/codecs below as the starting point. The exact
relationship rules and coverage still need a focused inventory before
implementation.

| Domain / relationship | Known sources and prior art | Remaining verification |
|---|---|---|
| Mob identity, names, level | `3DDATA/STB/LIST_NPC.STB`, `LIST_NPC_S.STL`; readers in `src/tools/quest-editor/src/data.rs` and `src/tools/npc-shop-editor/src/monsters.rs` | Agree on row ID vs root label, NPC-vs-monster classification, translated-name fallback, and fields needed for search. |
| Natural map spawns | Zone/map IFO `REGEN` and `MOB` lumps; codecs in `scripts/rosefmt/ifo.py`; existing traversal in `scripts/audit-spawned-npcs.py` and quest-editor IFO code | Trace zone IDs/names and exact spawn records into normalized map/location results. |
| Scripted mob spawns/morphs | `FILE_AI.STB` and `.AIP` actions; existing audit in `scripts/audit-spawned-npcs.py` and `scripts/audit-ai-monster-refs.py` | Enumerate all relevant spawn actions and distinguish direct, conditional, and indirect references. |
| Mob-AI cascade | Attack/death-triggered `.AIP` behavior can spawn further mobs; traverse each spawned mob's AI transitively and retain the chain of conditions/actions | Verify AI trigger timing, action semantics, termination/cycle handling, and how to avoid confusing a possible conditional spawn with a guaranteed spawn. |
| Quest definitions and metadata | `LIST_Quest.STB`, `LIST_QuestDATA.STB`, `3DDATA/QUESTDATA/*.QSD`, `Quest_s.STB`, `LIST_QUEST_S.STL`; QSD codec in `scripts/rosefmt/qsd.py` and `src/tools/quest-editor/src/qsd.rs` | Verify each ID/name/text join and what level/class/condition semantics can be reliably extracted. |
| Quest progress from mob kills | `LIST_NPC.STB` col 41 dead-event trigger name plus QSD trigger chains; mechanics verified in `src/tools/quest-editor/PROGRESS.md` | Determine which existing quests use this path and resolve shared/chained triggers without claiming a single trigger belongs to one quest. Keep kill-progress effects distinct from granting type-13 quest items; a dead-event trigger alone does not prove an item award. |
| Quest start/turn-in and dialogs | `LIST_EVENT.STB`, `.CON` files, zone IFO NPC placement, and `ULNGTB_CON.LTB`/`LNGTB_CON.LTB`; dialog codec in `scripts/rosefmt/condialog.py`, `scripts/rosefmt/ltb.py` | Establish coverage for direct NPC links, appended QEX1 dialogs, event scripts, compiled Lua checks/rewards, and quests triggered without a normal dialog. Do not treat NPC col 41 as general quest-giver wiring. |
| Item identity/names | `LIST_*` item STBs and corresponding `_S.STL` files; `npc-shop-editor/src/data.rs` and `quest-editor/src/data.rs` | Reconcile table-specific IDs and name/translation fallback across all item classes. Type-13 quest items live in the quest window, not player inventory, and are not player-interactable; keep their quest-state flow separate from ordinary inventory items and drops. |
| Table-driven mob drops | `3DDATA/STB/ITEM_DROP.STB`; `LIST_NPC.STB` columns 18/20; `CCal::Get_DropITEM` in `src/common/calculation.cpp`; shared encoding in `src/common/include/rose/common/drop_item_code.h` | Verified: a roll selects the mob's `NPC_DROP_TYPE` row when `NPC_DROP_ITEM` succeeds, otherwise the zone-number row; the monster inspector displays their deduplicated union. Slots 0–29 are searched, and redirect sentinels 1–4 expand to `26+5g` through `30+5g`. Preserve both provenance paths; a displayed possibility is not a guaranteed drop. |
| AI-scripted item drops/grants | `.AIP` AIACT17 (`0x0B000012`) calls `CObjMOB::Drop_ITEM` with one of five packed item slots; AIACT34 calls `Recv_ITEM` on the mob's caller | Action semantics and packed IDs are verified. Preserve trigger/pattern, conditions, all item slots, caller-vs-field destination, and conditional provenance; reuse the loader's historical record-layout normalization. |
| Quest item requirements/rewards | QSD conditions/rewards; helpers `item_refs` and `quest_refs` in `scripts/rosefmt/qsd.py` | `item_refs` covers `COND_004`, `REWD_001`, and `REWD_032`; retain opcode, operation, trigger, and raw bytes. Type-13 items are quest-window state, not player-inventory items. `REWD_001` op 0 consumes/removes the quest item; op 1 grants it. A same-item condition plus grant is not an independent acquisition source: trace how the item is first obtained and connect each trigger to its quest context. |
| Event/script item or mob sources | `.AIP`, `.CON`/LTB, `.QSD`, event Lua/scripts, and map event-object data as relevant | Inventory supported script references and label anything not statically resolvable; avoid claiming exhaustive coverage until tested. |

### Verified quest and dialog findings

- **Price chart delivery:** quest 5031 is accepted through Seyon's dialog,
  NPC row 1036 (`5031-01`), and turned in through Ulysses, NPC row 1012
  (`5031-02` / `5031-03`). This matches Seyon asking for the Daily Price
  Check to be delivered to Ulysses in Zant.
- **Sayon/Seyon episode quest:** NPC row 1037, Old Fisherman Myad, offers
  quest 101 (`101-01`); its text directs the player to Seyon. Seyon (1036)
  offers the next quest 102 (`102-03`). Use the in-data spelling “Seyon” in
  labels and retain the user's “Sayon” as a search alias if useful.
- **Soldier training:** NPC row 1008, Raffle, offers quest 855
  (`855-01`), followed by training steps 856 and 857. This is distinct from
  the Soldier job-change chain 851–854.
- **Dealer job change:** Warren (NPC 1002) starts the 1001 chain, which then
  proceeds through Crow (NPC 1004), quests 1001–1004. Trigger `1001-01`
  requires quest 801 and also advances quest 1001. The existing
  `con-triggers` CLI reports only the turn-in for 801 in this case, hiding the
  next quest transition; the search model must retain both effects. The user
  selected the marketplace quest as the intended Dealer-training example:
  Ulysses (NPC 1012) offers quest 1005, “An Eye for the Marketplace,” with
  quest 1006 as its continuation. Keep the 1001–1004 job-change chain separate
  as a possible additional coverage case.
- **Marketplace quest item path (user-confirmed):** the original task is
  to hunt Beetles in Breezy Hills for Beetle Shells (13:132), then return to
  the original quest giver, Ulysses, to exchange them for Cobra Leather
  (13:116). The inspected `QJ411-01.QSD` triggers `1005-04` through `1005-06`
  are this later exchange step: each requires and consumes 15 Beetle Shells,
  then grants 5, 4, or 3 Cobra Leather; `1006-01` through `1006-04` continue
  with Cobra Leather. Zone row 23 is Breezy Hills; its natural spawns include
  NPC rows 81 Beetle and 82 Beetle Fighter. Their `LIST_NPC` dead-event
  triggers are `855-31` and `855-32`, not the marketplace 1005 trigger names.
  `LIST_QUESTITEM` row 132 associates Beetle Shell with quest 1005. The parsed
  1005-01 through 1005-03 QSD triggers do not contain an explicit 13:132 item
  reward. The user has tested the quest in-game and confirms Beetle Shells are
  awarded from hunting Beetles, but not on every kill. Gameplay is confirmed;
  the exact award mechanism and chance/eligibility logic remain to be traced.
  Do not model each eligible kill as a guaranteed Shell or infer which trigger
  or server mechanism implements the award.
- **Level-limited free food:** the quoted “Old timer, I'm having a hard time
  on my adventures. Can you help me out?” line is in Myad's
  `EM22-007.CON` (NPC 1037), LTB string 2682. Its dialog option has check
  function `TA_underLevel8`; the next menu has `TA_level1` through
  `TA_level8` plus mid/already branches, and the text offers fruit/juice
  gifts. This is a `.CON` scripted gift, not a confirmed QSD quest. The
  function names suggest a level-8 gate, but the exact threshold and reward
  item IDs still need confirmation from the compiled Lua/runtime behavior.
  This checkout's loose data has no `ULNGTB_CON.LTB`; the packed
  `Exes/data.idx` does. Use the existing `rosefmt.idx` and `rosefmt.ltb`
  readers for packed dialog text, and report missing LTB inputs rather than
  treating unresolved text as an empty dialog.

### Verified item/drop findings and gaps

- The authoritative drop roll is `CCal::Get_DropITEM` in
  `src/common/calculation.cpp`. It chooses the mob-specific row
  (`NPC_DROP_TYPE`) only when the mob's `NPC_DROP_ITEM` chance succeeds;
  otherwise it reads the zone-number row. It selects among up to 30 base slots,
  expands redirect sentinels 1–4 into five-slot ranges beginning at `26 + 5g`,
  then decodes legacy or wide item codes with
  `Rose::Drop::decode_drop_item`. The Monster Inspector intentionally shows a
  deduplicated union of mob and zone tables, not a promise that a roll can pick
  every shown item.
- QSD item identities can be resolved through the corresponding item STL. For
  example, `QJ411-01.QSD` references Beetle Shell (13:132), Cobra Leather
  (13:116), and other quest items in quests 1005–1006. `QJ111-01.QSD` uses
  Queen Bibi's Staff (13:131) in the 857 triggers.
- Type-13 items are held in the quest window, not the player's inventory, and
  cannot be interacted with directly by the player. QSD conditions and rewards
  therefore describe quest-state flow, not ordinary inventory or mob loot.
- QSD rewards are potential quest-state sources, but an item reference alone is
  ambiguous: `REWD_001` op 0 consumes/removes the item, while op 1 grants it. In
  `QJ411-01.QSD`, triggers `1005-04` through `1005-06` each require and consume
  15 Beetle Shell (13:132), then grant 5, 4, or 3 Cobra Leather (13:116);
  `1006-01` through `1006-04` require Cobra Leather. This verifies a
  quest-item transformation chain, but does not identify how Beetle Shell is
  first acquired.
- In `QJ111-01.QSD`, triggers `857-01` through `857-03` each require and
  consume four Queen Bibi's Staff items (13:131). Separate local files
  `QN-034.QSD` and `QN-068.QSD` have trigger `857-31`, which requires and
  grants one Staff. Because the grant trigger already requires that item, it
  is not evidence of an independent initial source. Preserve file and trigger
  identity; the shared numeric prefix does not make these the same source.
- A scan of local QSDs found 158 distinct type-13 condition item codes and 172
  distinct type-13 item codes appearing in grant records. These are counts of
  references, not proof that each item can be acquired on an intended quest
  path; same-item condition/grant triggers and quest reachability still need
  analysis.
- A scan of the local QSD-referenced type-13 item codes found no direct matches
  in `ITEM_DROP.STB` or in AIACT17 field-drop/AIACT34 caller-grant slots. This
  is a useful completeness check, not evidence that quest items should come
  from those ordinary-drop paths. Other QSD, dialog/event, packed-only, or
  stale/incomplete quest content may explain how an item first enters quest
  state. Do not invent a mob source from a quest requirement or item
  description.
- Candidate complementary QSD coverage includes Clan House Extension quests
  2751–2753: their item conditions overlap ordinary `ITEM_DROP.STB` entries
  (for example 12:006 Silver Iron, 12:036 Pine Wood, and 12:162 Blue Crystal).
  Exact mob, zone, redirect, and quest-gating paths are not yet verified.

### Verified AI source findings

- Server pattern indexes are explicit in `cai_file.h`: 3 = damaged, 4 = kill,
  and 5 = dead. The AI action type is not always its human-facing action
  number: `AIACT17` is raw type `0x0B000012`. Its handler chooses one of five
  item slots and calls `CObjMOB::Drop_ITEM`, so it is a separate field-drop
  source from `ITEM_DROP.STB`.
- The local NPC-referenced AI set contains 748 `AIACT17` records across 466
  AI rows (202 20-byte, 544 24-byte, and 2 32-byte records). These are static
  action occurrences, not guaranteed drops; event conditions, empty slots,
  random selection, and source-format normalization all matter. The loader
  normalizes historical record layouts, so tooling should reuse that logic
  rather than assume one fixed payload size.
- There are also 46 `AIACT34` records in that set. `F_AIACT34` gives an item
  directly to the mob's caller via `Recv_ITEM`; model this separately from a
  field drop. Existing `audit-use-items.py` does not yet cover either AI item
  action, and `audit-spawned-npcs.py` checks direct references rather than
  proving complete transitive cascade coverage.
- Verified candidate acceptance path: NPC row 2 Jelly Bean (AI 102) can spawn
  row 4 Royal Jelly Bean (AI 104) on its dead pattern, subject to three event
  conditions. The Royal Jelly Bean's dead pattern has `AIACT17` slots
  `[10043, 10043, 10043, 10043, 0]`; packed item `10043` is use-item 10:43,
  Royal Jelly. That packed value is absent from the local `ITEM_DROP.STB`, and
  its item text says it can only be obtained from monsters. Treat the whole
  chain as a possible, provenance-bearing path, not a guaranteed result.
- Verified deeper candidate cascade: row 134 Grunter can summon row 344 Yeti
  Captain, which can summon row 343 Yeti Guard; that can create row 391 Silver
  Yeti, whose AI can summon row 308 Woopie Hooligan. These are separate,
  condition-bearing AI events, so the path is possible rather than guaranteed.
  The Woopie Hooligan's AI has `AIACT17` actions for packed item `10142`,
  use-item 10:142 Rice Cake Soup, on damaged/dead patterns. The item is absent
  from the local `ITEM_DROP.STB`. This is a stronger recursive-cascade
  acceptance candidate than the two-mob Jelly Bean example.
- AIP pattern labels can contain CP949 text even when other data for the
  client uses another encoding. Keep raw source bytes available and decode
  labels using the applicable file/client codec.

### Foreign-client source inventory (provisional)

- The NPC shop/item browser documentation explicitly names Jrose, RoseZA,
  QQ-iROSE, and China Rose reference dumps. Its per-file text reader supports
  Shift-JIS/legacy STL, Korean, Chinese GBK, and UTF-8 cases; this demonstrates
  item/monster-browser input support, **not** complete quest-data support.
- Existing import documentation provides richer source evidence: Jrose has
  AI/NPC/dialog data; RoseZA supplies the Ulverick source and compatible AI
  used by some imports; China Rose and its tsuki series appear in map imports;
  the 667 Oro source lacks AI and readable dialogs, which are supplied from
  RoseZA. 668 is named in monster-import guidance, but its source completeness
  is not established here.
- Other names previously found in project references (including titanRose,
  EVO, and Rose Brasil) must be classified as full client dumps, partial data
  sources, version labels, or tooling references before claiming support.
  Maintain a source profile of available file families, codecs, and tested
  readers; do not turn every source mention into a separate supported client.
- Foreign-character support includes rendering, not decoding alone. Reuse the
  existing CJK font fallback where practical; preserve original strings and
  source-language variants rather than silently replacing unknown glyphs.

### Proposed supplementary acceptance cases

- **Selected by the user — Forgotten Temple Investigation 2051–2053:** QSD
  `QP201.QSD` has each stage require 12:144 Ice Key Fragment. That item is in
  the zone rows for Lunar 51–57, including Forgotten Temple B1/B2 (zones 56
  and 57), and in mob-specific drop row 361. NPC row 342, Yeti Hunter (level
  95, AI 125, `da_yeti2.aip`), is naturally spawned in Arumic Valley (zone
  53); its drop row 361 has the item in slots 10 and 13, while zone row 53 has
  it in slot 5. This is a verified possible quest → item → mob/map path, not a
  guaranteed drop. Keep the table roll's mob-versus-zone choice and slot
  reachability in the result provenance.
- **Still optional — Clan House Extension 2751–2753:** QSD item conditions
  overlap ordinary `ITEM_DROP.STB` entries (for example 12:006 Silver Iron,
  12:036 Pine Wood, and 12:162 Blue Crystal). Exact mob/zone and redirect paths
  still need tracing.
- **Still optional — Dealer job-change 1001–1004:** separate from the selected
  marketplace training chain. It tests a QSD trigger that both requires quest
  801 and advances quest 1001, which the current `con-triggers` summary
  collapses.
- **Recursive mob-AI cascade:** Grunter → Yeti Captain → Yeti Guard → Silver
  Yeti → Woopie Hooligan, ending in AI-scripted 10:142 Rice Cake Soup. Test
  conditional provenance and a drop absent from `ITEM_DROP.STB`.
- **Foreign and packed-data checks:** compare a foreign-client quest/dialog
  sample after the source inventory is complete, and read Myad's free-food LTB
  string from packed `Exes/data.idx` because the loose string table is absent.

Game data is primarily under `data/` and is not necessarily fully represented by
the tracked repository contents. Distinguish missing/unavailable source data
from an empty result.

**Memory-file persistence:** `dev/` is gitignored, so this `tracking_plan.md`
persists in this local checkout but is not included in commits or shared with
other clones. Keep using this location for the requested model/session memory;
if cross-machine sharing becomes necessary, decide on a tracked documentation
location rather than force-adding the ignored file without approval.

## Roadmap

1. **Finish source/capability inventory (current step).** Verify what the
   existing tools do, identify existing readers/codecs, document exact joins
   and known limits for all three domains, and fix supporting discovery
   scripts/readers where they miss relevant data.
2. **Specify the cross-domain MVP.** Select representative quest/mob/item cases
   from the inventory and write acceptance criteria for search, navigation,
   provenance, packed/loose inputs, and incomplete/ambiguous results.
3. **Choose the implementation boundary.** Compare reuse vs a new standalone
   app only after the inventory; do not preselect a UI framework or crate split.
4. **Implement read-only ingestion and search.** Build on existing codecs and
   validate against the MVP cases.
5. **Prove coverage and usability.** Test natural and scripted spawns, drops,
   quest prerequisites/rewards/dialogs, and malformed or missing data.
6. **Plan safe editing and migration.** Expand to arbitrary existing quest
   editing, then decide when the new tool can replace old workflows.
7. **Revisit in-game integration.** Decide whether it is player-facing,
   GM/developer-only, or unnecessary based on standalone results.

## Status and next action

**Status:** planning/discovery; no product code has been written for this tool.

**Completed in discovery:** confirmed the intended unified-replacement direction,
read-only cross-domain first proof, static-data authority, standalone-first
decision, loose and packed data support, optional foreign-client quest
examination/import with Rose Next as the default, equal end-user/developer
priority, and robust coverage as a goal (including fixing supporting scripts
when needed). Inspected the existing quest-editor and GM browser documentation
and the main Rust data-reader entry points. Confirmed substantial prior art
exists, but the two tools do not currently provide the requested unified
quest↔mob↔item discovery. Mapped the price-chart, Sayon/Seyon, Soldier-training,
Dealer-marketplace, Dealer-job-change, and Myad free-food scenarios to local
dialog/QSD records; the user selected the marketplace chain as the Dealer
training case. The user also selected Forgotten Temple Investigation
2051–2053 as a supplementary acceptance case; the Ice Key Fragment item,
Yeti Hunter source row, and Arumic Valley spawn are verified as a possible
path. Verified the `ITEM_DROP.STB` mob-versus-zone row selection,
redirect expansion, and the QSD item-reference opcodes. Myad's exact
compiled-Lua level gate and rewards, plus the mechanism and chance/eligibility
for the user-tested Beetle Shell hunting reward, remain open. Verified server AI
trigger indexes, the `AIACT17` field-drop path, the separate `AIACT34`
caller-grant path, and real recursive cascades whose AI drops are not
represented by `ITEM_DROP.STB` alone. Found that local QSD references to
type-13 items do not directly appear in the table or those two AI action types.
The user clarified
that type-13 items live in the quest window, not player inventory, and cannot
be interacted with by the player. QSD grant/consume records must therefore be
modeled as quest-state transitions, not ordinary loot. A targeted follow-up
found a 1005–1006 quest-item transformation (Beetle Shell to Cobra Leather),
which the user clarified is preceded by hunting Beetles in Breezy Hills. The
user tested the quest and confirms Shells are not awarded on every kill. The
gameplay path is validated, but the award mechanism and chance/eligibility
remain untraced; same-item condition/grant triggers are not independent initial
sources. The QSD operation and file/trigger identity are essential provenance.
Confirmed text inputs span UTF-8, CP949, and UTF-16LE sources, and some required
dialog text is only present in the packed data index.

**Next action:** finish the read-only source inventory by tracing the remaining
item-grant/source gaps and natural plus scripted spawn relationships,
classifying the known foreign data sources by completeness and codecs, and
resolving Myad's compiled-Lua gate/rewards if feasible. The Forgotten Temple
case is selected; the other proposed cases remain optional. Do not start
product implementation until the cross-domain MVP and its data coverage are
clear.

### Next discovery follow-ups

- Verify the Myad gift's compiled-Lua level checks and direct item rewards
  without assuming the UI text alone proves the runtime grant.
- Trace how type-13 quest items first enter quest state; distinguish QSD
  condition/consume/grant transitions from ordinary inventory and mob-drop
  sources. Do not count same-item condition/grant triggers as initial sources
  without another verified acquisition path. For the selected marketplace
  case, find the mechanism and chance/eligibility for the user-tested Beetle →
  Beetle Shell reward in Breezy Hills; it is not awarded on every kill. Retain
  unresolved provenance.
- Find representative mob-AI cases that demonstrate attack/death spawns,
  AI-scripted items outside `ITEM_DROP.STB`, and multi-hop cascades; retain the
  Jelly Bean and Grunter/Yeti/Woopie Hooligan examples as candidate fixtures,
  then validate their full condition and encoding details.
- Inventory which foreign client formats are already represented in the
  repository's scripts, tools, and reference sources; include their
  source-specific text encodings and do not expand beyond that set unless the
  user later changes scope.

### Issue and decision log

- **2026-11-17 — Existing quest editing scope:** the existing quest-editor
  manages its own `QX-<SN>.QSD` quests, but not arbitrary existing quests.
  Decision: retain it during development; the unified tool's broader editing
  capability remains a later goal.
- **2026-11-17 — First product proof:** cross-domain search across quests, mobs,
  and items, not a quest-only vertical slice.
- **2026-11-17 — Product boundary:** standalone first; in-game integration
  deferred until the standalone tool is proven.
- **2026-11-17 — Data inputs:** support both loose extracted data and packed
  `data.idx`/VFS data; reuse existing readers where possible.
- **2026-11-17 — Foreign quest data:** default to Rose Next, but allow other
  client dumps as sources for quest examination and later import/porting of
  compatible quests into Rose Next. Limit initial foreign-format support to
  clients already represented in our sources; no new client formats for now.
- **2026-11-17 — Quest test cases:** use the five user-described scenarios
  above, resolve them to actual Rose Next quest/NPC records, and add an
  AI-proposed set of complementary cases after the data inventory.
- **2026-11-17 — Audience:** end-user discovery and developer inspection/
  maintenance have equal priority.
- **2026-11-17 — Coverage goal:** pursue robust, broad static-data discovery;
  fix supporting scripts/readers when needed and test those fixes. Residual
  gaps must be explicit.
- **2026-11-17 — Mob-AI cascade:** include attack/death-triggered mob spawns and
  AI-scripted item drops/grants outside `ITEM_DROP.STB`; recursively follow
  spawned mobs' own AI possibilities. Treat `ITEM_DROP.STB` as incomplete on its
  own and preserve the conditions/provenance of each possible path.
