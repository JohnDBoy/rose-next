# CLAUDE.md — Rose Dev Studio

Loaded when a file under src/tools/dev-studio/ is read; the root CLAUDE.md index points here.

### Rose Dev Studio (`src/tools/dev-studio/`, 2026-10-13)

A Python/PyQt6 desktop editor over `rosefmt` (`just studio`), the foundation of a GUI
"dev studio": STB and STL editing so far, one format at a time after that. It **imports**
the codecs and never re-implements one; every save re-reads its own bytes and refuses on
mismatch, backs the original up once per session to `build/dev-studio/backups/` (never a
`.bak` under `data/`), and writes through a hidden `.tmp` + rename. STB rows are ids, so
rows are appended or cleared, never deleted. A new format = a `Document` over its codec +
an `EditorBase` subclass + one line in `app.EDITORS` and `workspace.KINDS`. **The client reads
STL slot 1 only** (`CStringManager::GetLanguageIDInGame`: the Windows charset picks the
slot, and ANSI lands on `LANGUAGE_USA` = 1); slots 0/2/3/4 are Korean, Japanese, Chinese
Traditional/Simplified by the client's `LANGUAGE_TYPE`, mostly English copies here, and the
studio hides them by default. **STL text is UTF-8 in every slot, slot 1 included**: the client
runs each string through `CLocalizing::UTF8ToMBCS` on load (`CP_UTF8` -> wide -> the Windows
code page, in `CStringManager::LoadTypeTable`), so a UTF-8 `…` shows as `…` in game (checked on
the Amulet Necklace tooltip, 2026-10-13) and a latin-1 `é` would be garbage. All 72,970 strings
in our 33 STLs decode strictly as UTF-8; write new STL text as UTF-8. **STB cells are read raw**
(no conversion) and mix codecs: 5,112 non-ASCII cells are UTF-8 (Korean labels in
`LIST_TERRAIN_OBJECT_*`/`LIST_CNST_*`, AI_S, PRODUCT ...) and 535 are cp949 (the map editor's
`TileLookup_Type_*`, LIST_EVENT), so decode **per cell** (`devstudio.documents.cell_codec`),
never with one codec per file. Test it headless with
`QT_QPA_PLATFORM=offscreen` plus `QT_QPA_FONTDIR=C:/Windows/Fonts` (without the font dir
every glyph is a box) and `widget.grab()`. Details: its README.

**Combat Simulator tab** (`combat_editor.py` over `scripts/combatsim`, 2026-10-14): a
build JSON is a `BuildDocument` (`.json` opens only if it has job/level/stats); the
engine runs on a `QThread` and stale results are dropped by a generation counter. A
headless test must point `QSettings` at a scratch INI (`app.QSettings` and
`editor_base.QSettings`), or it rewrites the user's session and recent files. Combo boxes
there take `combo()` (min-contents sizing): a plain `QComboBox` sizes to its longest skill
description and pushes the form wider than its pane.
