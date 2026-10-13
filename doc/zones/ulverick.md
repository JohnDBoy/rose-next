### Cave Of Ulverick Is RoseZA's Spider Dungeon, Opened Up (imported 2026-10-04/05, validated in game)

RoseZA's party instance under Desert of the Dead (map `JZC01`, its zone rows 90-94),
imported as our **open zone 34** by `scripts/import-ulverick.py` (`--stage 1-5`,
`--dry-run`, `--verify`, `--selftest`; backups `build/ulverick/`). Only RoseZA ships it
whole. **In: [Bone Warden] Ossian** (LIST_NPC 1158, at the cave mouth, JD04 36_33)
takes a toll of 10 Animal Leg Bone + 10 Animal Backbone (Desert of the Dead drops) and
warps you to the cave's `start` -- one QSD trigger, `Ulverick-EnterCave` in QP401.QSD,
and a have/lack dialog written by `quest-editor con-toll`. Out: the cave's own gate,
re-pointed from RoseZA row 80 (our Pyramid gate) to 100, landing on `WARP-JZC01-JD04`
in `JD04.ZON`. Kept: the map; its 55 points binned into 17 camps of Ulverick's Minion
(531, lv128); one lone boss per room -- King Ulverick (534, lv151, 30 min) in the round
middle room (the hardest to reach), the General (533, lv145, 20 min) in the big
north-west room, the Leader
(532, lv135, 10 min) in the small south-east one -- each with its own authored table
(819-822, zone row 34 mirrors 819), the first source of the Jrose back items 957-1061.
The minimap is 2.5 m a pixel from (4800, 5600) m -- how the rooms were located.
Things that will bite:

- The spider skeleton has the event-less `casting_01` in slots 6-8, so the bosses'
  motion-6 casts are moved to 8 (release on slot 9, `action_skill01`). **AI speech
  (AIACT28) is cut**: its text is a row number into the AI string table, another
  lineage's here, and the Leader's spawn line was a server-wide announcement.

- **Torches that stay dark until you die** were a retail client bug, not the import
  (fixed 2026-10-05): every map flame is a night-only dummy effect
  (`POINT_EFFECT_DAYNNIGHT`), and `CDayNNightProc::IsDay()` compared the `DN_DAY`/
  `DN_NIGHT` state against `TIME_DN_MORNING`/`TIME_DN_DAY` -- the same numbers 0/1 -- so
  it always said "day" and `PushEffect` hid every night effect created after the last
  `Start()` (zone entry, dusk): objects that stream in as you walk stayed unlit. Every
  zone's night lamps had it; the cave (always night: its day columns are 0) showed it.
