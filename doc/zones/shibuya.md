### SHIBUYA Is Jrose's SECONDWALL Collab (imported 2026-09-28, validated in game)

Jrose zones 126 (SHIBUYA, a Tokyo street walk) and 127 (Live House SEVEN, the
survivors' shelter) from a 2017 band collab, at their **native** numbers. The band
and the survivors tell their story, Shimasaburo and Juri run shops (our Junon Polis
tabs), Sarasa the storage. In via Jones (Junon Polis), out via the SECONDWALL
mascot. `scripts/import-shibuya.py` (`--stage 1-7`, `--dry-run`, `--verify`,
`--selftest`). **The tribute (2026-09-29)** turns it into a level
60-80 zone: stage 4 imports the Deaders (twelve monsters at their Jrose ids with
our stats, their AI rebuilt from Jrose's with our edits, the police guns, a
15-skill kit through `import-monster-skills.py`), the Rot Tracker as a 5% rare
spawn off any field kill, and Deader Rex as the finale boss; stage 5 the 72
camps, Rex's plaza and drop tables 960-966 (+ zone row 126, whose legacy table
moved to 960); stage 6 the SECONDWALL cosmetics (quest rewards, the mascot set
behind a class-322 box -- package 920 in `gs_user.cpp` -- and the Rot Tracker's
headphones); stage 7 the band's six quests (`scripts/shibuya-quests.json`, a
quest-editor pack: five one-time hunts, then Kanna's Deader Rex finale, which
requires all five). **The Deaders are listed in
`scripts/balance-trend-exclude.py`**: new monsters in levels 60-199 move the trend
every monster balance pass fits and verifies against -- add any future import's
ids there too. **Re-running `--stage 3` rebuilds the band's
`.CON`s from source and drops their quest options** -- always follow it with
`--stage 7`. Things that will bite:

- **Jrose warp rows 176/177 are Oro gates here**: the pair is 182/183 and the gate
  objects are re-pointed. Shibuya's 108 regen points were editor templates
  (all Mini-Jelly Bean) and are emptied.
- **Shibuya ships no lightmaps**: objects load unlit, the terrain uses
  `3DDATA\TERRAIN\default_light.dds`. Expect flat lighting; it is the source.
- Zone 128 (the "782" dungeon) is instanced and zone 36 (outdoor stage) separate;
  neither is imported.
- **Entering the live house crashed the client with no dump** (fixed 2026-09-28):
  its stage-light effect `SW_Light.eft` has three static meshes with an *empty*
  animation path, and `CFileLIST::Add_FILE("")` registered the first under a
  non-zero key with a NULL name, so the second handed NULL to `_strcmpi` -- a CRT
  invalid-parameter fail-fast. `Add_FILE` now returns 0 for an empty name.
