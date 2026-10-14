# Rose Dev Studio

A desktop editor for ROSE Online data files. It starts with **STB tables** and
**STL string tables**, and is meant to grow one format at a time.

```powershell
just studio                         # or: pythonw src/tools/dev-studio/run.pyw
just studio data/3DDATA/STB/LIST_NPC.STB
python -m devstudio                 # from src/tools/dev-studio, with a console for tracebacks
```

It needs Python 3.12 and PyQt6 (`pip install PyQt6`). The first run opens the
repo's `data/` folder. Use **File > Open Data Folder** to open a reference dump
instead (anything that holds `3DDATA`).

## What it does

- **Explorer.** Every `.STB` and `.STL` under the data folder, with row and
  column counts read from each header. A dot marks an open file with unsaved
  changes.
- **STB grid.** Each column header shows the *game* column number above the
  column's name (the editor column number is in the tooltip). Row names come
  only from the companion `<NAME>_S.STL`, through whichever column holds its
  keys (found by matching cells against the STL, not hardcoded). They are
  **off by default** -- most rows repeat column 0, so an untitled name column
  read as a ghost copy of it -- and the `T` button turns on a titled
  "In-game name" column (remembered), which shows where the two differ
  (LIST_FOOT 152: `Red Santa Boots` in the table, `Santa Boots` in game).
- **Filter.** Rows can be filtered across all columns or one column. `#123`
  jumps to row 123, and there is a toggle to hide empty rows. Sorting (on the
  column header's context menu) only changes the view, never the file.
- **Row inspector (Ctrl+I).** The current row as a form, one labelled field per
  column. It links to the row's STL entry.
- **STL grid.** Opens on **English, the only slot the game reads**: the client
  picks a slot from the Windows charset (`CStringManager::GetLanguageIDInGame`)
  and a Western install lands on slot 1. The other four (Korean, Japanese,
  Chinese Traditional/Simplified, named after the client's `LANGUAGE_TYPE`)
  stay hidden behind the globe button. **STL text is UTF-8 in every slot**: the
  client decodes each string with `CP_UTF8` on load
  (`CLocalizing::UTF8ToMBCS`), so the studio reads and writes UTF-8 and the
  status bar warns about an entry that is not (the game would garble it;
  re-typing it fixes it). Descriptions are edited in the inspector, which
  links back to the STB rows that use the key.
- **STB text encodings, per cell.** The client reads STB cells raw, and one
  table can mix three codecs: latin-1 English, UTF-8 (5,112 cells -- Korean
  labels such as LIST_TERRAIN_OBJECT_*'s `큰나무01`) and cp949 (535 cells --
  the map editor's TileLookup tables, LIST_EVENT). Each cell is sniffed on its
  own (strict UTF-8 first, then cp949 only if it yields Hangul/CJK) and an
  edit is written back in the codec the cell already had; new Korean in a
  latin-1 cell is stored as UTF-8. The status bar names a cell's codec when it
  is not latin-1. Every non-ASCII string in `data/` decodes and re-encodes to
  the same bytes.
- **Editing.** Undo and redo cover every change. Copy and paste use
  tab-separated text, so they work with Excel. Delete clears a cell. A cell
  that differs from the file on disk is tinted, with a marker in its corner.
- **Command palette.** Ctrl+P opens a file; Ctrl+Shift+P (or a leading `>`)
  runs any menu command.
- **Themes.** Dark and light.
- **Combat Simulator.** **Tools > New Combat Build** (pick a class and level) or
  **Open Combat Build** opens a character build from `scripts/combatsim/builds/`
  as a tab. The left side edits the build: stats with a bonus-point counter,
  every equipment slot with its refine grade and gem or option, ammo, passive
  ranks, a rotation of damage skills and debuffs in priority order, buffs kept up
  (with the caster's INT for party buffs; Cleric buffs are left out), summons
  (against the class's summon capacity; each runs its own AI), and potions (off
  by default). **Auto-build** fills it for the class and level:
  **Average gear** (what a typical player runs -- their class's armour set of the
  newest tier, a better weapon and body, low refines; only those upgrades carry a
  prefix) or
  **Best in slot** (well refined). Both put CON near the level, spend exactly the
  skill points the level grants on a mix of passives and actives (own weapon
  mastery first), and fill the rotation from the skills learned (debuffs that hit
  the monster first, then damage skills, strongest first) with "auto-attacks
  between skills" at 0 for casters (they spam) and 1 for everyone else. A
  Bourgeois also learns its summons and Employ Troops and fills its summon bar
  (strongest first). Buffs and potions are left alone. The skill-point chip
  splits passives from actives (an action learned only counts once it is in the
  build: test builds made before 2026-10-14 list passives only). A chip under
  "Passive skills" counts skill points used against the level's total. Item names carry
  their in-game prefix (Saint, Dark ...). The right side picks a monster and shows how the
  fight goes over a few hundred simulated fights: win rate, time to kill, how
  long the character survives fresh copies of the monster back to back, HP and
  MP left, damage dealt and taken per second, both stat blocks, per-skill
  numbers and debuff uptime. The monster runs its AI file: the skills it casts
  get their own rows (casts, damage, the states they put on the player, and
  whether it attacks, resumes or stops afterwards), and AI actions the
  simulator cannot play out (summons, wandering, running away) are counted
  under the table. **Fix passive bugs** shows what the passives were
  meant to give. **Run** simulates in a worker process; **Auto-run** (off by
  default) repeats it after every edit. A new build is unsaved until you save
  it, and "Don't save" deletes its file. The engine is `scripts/combatsim` (also a command-line tool,
  `scripts/combat-sim.py`); see `scripts/CLAUDE.md` "Combat Simulator".

## Saving

Saving goes through the same codec the data scripts use (`scripts/rosefmt`),
so the studio never has its own copy of a file format.

1. The file is written with the codec's `to_bytes`.
2. Those bytes are read back and compared with the editor's contents. If they
   do not match, the save is refused and the file on disk is left untouched.
3. The first save of each file in a session copies the original to
   `build/dev-studio/backups/<session>/`. It is never copied beside the file,
   because `pack.ps1` refuses to bake while a `.bak` is under `data/`.
4. The new bytes go to a hidden `.tmp` sibling, which is then renamed over the
   file.

An untouched file serialises byte for byte. This is checked on LIST_NPC,
LIST_NPC_S, LIST_STRING_S and LIST_SKILL_S.

If another tool or script changes an open file on disk, the studio reloads it
without asking when you have no unsaved changes there. When you do, it shows a
banner offering to reload or keep your version.

Rules the studio enforces:

- **An STB row is an id.** Every other table, script and the C++ address rows
  by number. Rows can be appended or cleared, but never deleted or inserted in
  the middle.
- **An STL entry is a key.** Entries can be appended or removed (with undo).
  The client reads entries in file order, so new ones always go at the end.
- **Shared language blocks stay shared.** In `LIST_STRING_S.STL` five slots
  point at one block. An edit applies to every slot that shares the block and
  still holds the same text.

## Layout

| Module | Role |
| --- | --- |
| `app.py` | Main window: activity bar, explorer, tabs, status bar, menus, session restore, file watcher. `EDITORS` maps a file extension to its document and editor classes. |
| `documents.py` | `Document` (undo stack, verified save, backups), `StbDocument`, `StlDocument`. All mutation goes through `QUndoCommand`s. |
| `workspace.py` | Scans the data folder, pairs STB and STL files, finds the key column, does reverse lookups. |
| `grid.py` | The custom-painted grid: cell delegate, two-line column header, named row header, spreadsheet keys. |
| `stb_editor.py`, `stl_editor.py` | The two editors and their inspectors. |
| `build_doc.py`, `combat_editor.py` | Combat Simulator: a build JSON as a document (one whole-record undo command per edit) and its tab. `.json` opens here only if it is a build. |
| `explorer.py`, `palette.py`, `welcome.py`, `widgets.py` | The shell's pieces. |
| `theme.py`, `icons.py` | Every colour is a token of a `Theme`; the stylesheet and all custom painting read the same tokens. The icons are drawn on a 24-unit grid and tinted at render time. |

To add a format:

1. Write a `Document` over its `rosefmt` codec.
2. Write an `EditorBase` subclass.
3. Add a line to `EDITORS` in `app.py`.
4. Add a line to `KINDS` in `workspace.py`.

## Known gaps

- Only STB and STL files are supported so far (plus combat-simulator builds).
- The studio does not know what the columns mean beyond their names, so it
  cannot tell you which table a column points into.
- Find-and-replace across files is not built yet.
- Text input goes through Qt, so it handles any script, but nothing checks that
  a string will display in the game client's fonts.
