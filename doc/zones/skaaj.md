### Skaaj Is Jrose's Cat-Folk Island (imported 2026-09-18, validated in game)

Jrose zone 79 (スカ, planet 5): a small tropical town, eleven cat-folk NPCs on the
`ronya` skeleton, butterflies and clownfish for spawns, no monsters, no drops. Jrose
used it as the hub of its housing and pet systems; we take the map, the townsfolk
and the trip there. `scripts/import-skaaj.py` (`--stage 1-4`, `--dry-run`,
`--verify`, `--selftest`) puts it at **our zone 89** (79 is the Wasteland) with STL
key LZON100. Things that will bite:

- **The xadet map editor hid it because its sky column is blank.** `IsValidMap`
  rejected the row; the client reads the cell as an integer (blank = sky 0). The
  editor now resolves it the client's way (`MapManager.SkyIndex`) and the importer
  writes an explicit 0. Eleven Jrose maps were invisible for this reason.
- **The whole town is gated on quest switch 90.** Every NPC's real greeting sits
  behind `chk-Skaaj-Language-QSW`; the ungated line before it is cat-language.
  `CEvent::Conversation` walks every root node and each NPCSAY replaces the last,
  so the later gated line wins once the switch is on. Miakis, the divine envoy, is
  the only one you understand and her "Thank you!" fires `Skaaj-Language-QSW-ON`.
  Switch 90 is free here, so the QSD entities are copied verbatim into QP401.QSD.

- **Jrose's `LIST_ZONE_S.STL` is the old `I_NUM` dialect** the editor cannot parse,
  so its Open list shows keys (`LZON079`); open by ID. NPC 1774 is dead in Jrose too
  (nameless, no CHR entry, placement names `EM79-012.con` while the file is
  `EM79-12.CON`) and is dropped. Our `LIST_NPC.CHR` holds orphan "noname" entries at
  1753-1759 that `import_characters` would keep; the importer clears them first.
