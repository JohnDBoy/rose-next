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
  shown on their own only when they add something: LIST_WEAPON gets them,
  LIST_NPC does not (its column 0 already says the same), FILE_AI has no STL.
  The `T` button toggles them per tab.
- **Filter.** Rows can be filtered across all columns or one column. `#123`
  jumps to row 123, and there is a toggle to hide empty rows. Sorting (on the
  column header's context menu) only changes the view, never the file.
- **Row inspector (Ctrl+I).** The current row as a form, one labelled field per
  column. It links to the row's STL entry.
- **STL grid.** Opens on **English, the only slot the game reads**: the client
  picks a slot from the Windows charset (`CStringManager::GetLanguageIDInGame`)
  and a Western install lands on slot 1. The other four (Korean, Japanese,
  Chinese Traditional/Simplified, named after the client's `LANGUAGE_TYPE`)
  stay hidden behind the globe button. Each slot is read and written in its
  own encoding: English is latin-1, the others UTF-8. Descriptions are edited
  in the inspector, which links back to the STB rows that use the key.
- **Editing.** Undo and redo cover every change. Copy and paste use
  tab-separated text, so they work with Excel. Delete clears a cell. A cell
  that differs from the file on disk is tinted, with a marker in its corner.
- **Command palette.** Ctrl+P opens a file; Ctrl+Shift+P (or a leading `>`)
  runs any menu command.
- **Themes.** Dark and light.

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
| `explorer.py`, `palette.py`, `welcome.py`, `widgets.py` | The shell's pieces. |
| `theme.py`, `icons.py` | Every colour is a token of a `Theme`; the stylesheet and all custom painting read the same tokens. The icons are drawn on a 24-unit grid and tinted at render time. |

To add a format:

1. Write a `Document` over its `rosefmt` codec.
2. Write an `EditorBase` subclass.
3. Add a line to `EDITORS` in `app.py`.
4. Add a line to `KINDS` in `workspace.py`.

## Known gaps

- Only STB and STL files are supported so far.
- The studio does not know what the columns mean beyond their names, so it
  cannot tell you which table a column points into.
- Find-and-replace across files is not built yet.
- Text input goes through Qt, so it handles any script, but nothing checks that
  a string will display in the game client's fonts.
