# CLAUDE.md — ROSE Online Map Editor (xadet)

## What This Is

The legacy **xadet** ROSE Online Map Editor, vendored into the Rose Next Classic
workspace at `xadet/rose-online-map-editor/`. It is a standalone C# desktop app
(circa 2007) used to author ROSE map/zone data — terrain, tiles, objects, NPCs,
monsters, spawns, warps, water, effects, sounds, and event triggers.

Treat it as an isolated subproject. It does **not** share build tooling, language,
or runtime with the rest of the workspace (which is C++/Rust). The only coupling is
the ROSE *data* it reads/writes from `../../data`.

- **UI:** WPF (`.NET Framework 3.5`)
- **Rendering:** XNA 3.1 (DirectX 9 era), hosted inside a WinForms panel in the WPF window
- **Audio:** irrKlang (`irrKlang.NET2.0.dll`)
- **Platform:** x86 only, `WinExe`, root namespace `Map_Editor`
- **License:** Apache 2.0

> **Vendored, not a submodule.** This tree is a copy of upstream
> [jackwakefield/rose-online-map-editor](https://github.com/jackwakefield/rose-online-map-editor)
> at commit `7f0462e`, committed straight into this repo (Apache 2.0, `LICENSE`
> kept). There is no nested `.git` and no upstream remote — our changes can't go
> back upstream, because they target this project's data layout rather than the
> retail-era layout the editor was written for. `git log -- xadet/` splits into
> exactly two commits: the pristine vendor, then everything we changed.

## Build, Deploy, Run

Build with **VS2019 MSBuild, Release, x86**. The `irrKlang.NET2.0.dll` reference is
stale, so point `ReferencePath` at the workspace `data` folder where the DLL lives.

```powershell
& 'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe' `
  'Map Editor.sln' /p:Configuration=Release /p:Platform=x86 `
  /p:ReferencePath='C:\Users\Thomas\Desktop\Rose\rose-next-classic\data' /m:1 /v:minimal
```

**Editing source is not enough.** The user runs `../../data/Map Editor.exe`, so after
any change you must rebuild and copy the binaries into `data`:

```powershell
Copy-Item 'Map Editor\bin\x86\Release\Map Editor.exe' '..\..\data\Map Editor.exe' -Force
Copy-Item 'Map Editor\bin\x86\Release\Map Editor.pdb' '..\..\data\Map Editor.pdb' -Force
```

The editor's working directory is `../../data`. ROSE data paths come from the
STB/ZON/ZSC/IFO files and often use legacy mixed-case paths like `3Ddata`.

## Unattended screenshots (`--shots`)

`"Map Editor.exe" --shots job.txt` (run with `data` as the working directory)
loads one zone, renders it from each view in the job, saves the back buffer
as `<view>.png`, writes `shots.txt` (one line per view, then `done`) and
exits. It is driven by the map generator (`scripts/mapgen-zone.py shots
SPEC`, which writes the job and a contact sheet), so a generated map can be
looked at with no one at the editor. Code: `Engine/ShotRunner.cs`, hooked
into `Engine/Main.cs` (begin after the splash, update every frame, capture
right after the world is drawn, before gizmos and tooltips) and
`Perspective.SetLookAt` (a scripted camera that ignores mouse and keyboard).

Job directives: `zone N`, `out <folder>`, `hide <Draw settings...>` (editing
helpers such as Collision, SpawnPoints, GridOutline; set in memory only, the
config file is not saved), `settle <frames>`, and
`view <name> ex ey ez tx ty tz` (eye and target in editor metres: world cm
/ 100, Z up). The run gives up after 5 minutes (a failed map load opens a
message box) and exits 1. It needs an unlocked desktop session: the editor
opens its window as usual. Captures are the render panel's size.

Minimap directives (2026-10-06, `scripts/make-minimap.py`):
`ortho <name> x0 y0 x1 y1 width height` looks straight down on that
rectangle (editor metres, north up) through the orthographic camera
(`Orthographic.SetTopDown`, which also stops it reading the keyboard) and
renders into an off-screen target of exactly width x height
(`BeforeWorldDraw` swaps the render target and depth buffer in, and
`AfterWorldDraw` swaps them back), so the picture does not depend on the
window. `water r g b` makes `Water.Draw` paint every water plane opaque in
that colour, still depth-tested, so the script can key the water out
(`DrawKeyed`); it applies to the whole job. `minimap <file.png>` runs
Tools > Make minimap's capture and styling with its default options and
writes the PNG (shots.txt gets `minimap WxH difference D`); views are optional.

## Tools > Make minimap (2026-10-06)

The zone's minimap made from the open map, for modders with no Python: a C#
port of `scripts/make-minimap.py` (which stays for batch runs and style
tuning). Code: `Engine/Minimap/` and `Forms/Tools/MinimapWindow.xaml(.cs)`.

- **Capture** (`MinimapCapture`): inside the editor's own draw loop, unsaved
  edits included. Tiles of up to 2048 px at 4x (2x "Draft"), one tile every
  3 frames, each averaged down to minimap pixels as it is read back. Hides the
  editing helpers, sky, NPCs and monsters in memory and keys the water (same
  `Water.DrawKeyed` path as `water`); `Main.Draw` returns after the world while
  it runs. The window calls `Main.ReleaseTool()` first (the first half of
  `Tool_Click`, extracted): tool modes change how terrain draws (height brush,
  tile highlights, selection boxes).
- **Placement** (`MinimapZone`): 64 px a chunk with a one-chunk margin, top-left
  chunk = LIST_ZONE game cols 9/10 (`CMinimapDLG::CalculateDisplayPos`). A zone
  with a minimap keeps its extent, so old and new line up pixel for pixel; one
  without gets its HIM files' bounding box.
- **Style** (`MinimapStyle`, off the UI thread): water painted blue by distance
  from shore (exact EDT), missing chunks push-pull filled (water where the void
  is bordered by water), a retail frame (`FRAME_SOURCE`, JPT01) cut to size by
  whole ornament periods, warp gates marked and named (GDI+ text, rotated on the
  sides). "Match the original" fits an affine land grade and the water colours
  to the zone's original minimap (robust least squares). No relief shading and
  no sharpening, on purpose: measured, retail is the plain lightmapped render
  box-filtered from 4x. Scores against retail match the Python version within
  0.2 on all eight zones measured.
- **Files** (`DdsCodec`): DXT1/3/5 and 24/32-bit decoding on the CPU (identical
  to Pillow on retail minimaps); DXT5 encoding with a full mip chain, halving
  with round-down like texconv (384 -> 9 levels), error 2.8/255 on a fresh
  minimap (texconv 2.6). No D3DX, no GPU.
- **Install / Restore**: writes the DDS; for a NOMAP zone also LIST_ZONE cols
  8-10, **patched byte for byte** (`SetCells`) -- `STB.Save` round-trips every
  cell through EUC-KR. The first Install copies what it replaces to
  `MinimapBackups\<FOLDER>\` (beside the editor, i.e. `data/`; excluded from the
  bake in `scripts/pack.ps1`) with `installed.txt` recording the old cells;
  Restore puts them back and deletes the folder. Refused when the file or
  LIST_ZONE is packed (`GameData.IsArchived`), like Save.
- `tests/Run-MinimapTests.ps1 [-FreshPicture x.png]`: codec against real
  minimaps, Install/Restore round trips on a scratch copy of the data (LIST_ZONE
  byte-identical after Restore), and the window built off screen
  (`build/minimap-tests/window.png`). Not yet driven by hand in the GUI.

## Object browser and placement (2026-10-11)

The decoration and construction panels share `Forms/Controls/ObjectBrowser` (a
searchable thumbnail grid) and `RotationEditor` (degrees), and the object tool
(`Engine/ToolManager/Tools/Objects/Object.cs`) places differently. Not yet tried
by hand in the GUI; the headless tests below pass.

- **A placement is an index into the zone's own ZSC** (LIST_ZONE cols 12/13), so
  "All zones" scope (`ZscCatalog`: every table LIST_ZONE names, 46 tables / 2,825
  objects, 1,945 once identical copies are folded by `ZscRaw.ContentHash`) can only
  *show* other tables' objects. Using one (Add, Clone, double-click) calls
  `ZSC.AppendFrom`, which copies the object into the zone's table with meshes,
  materials (path + 36 flag bytes) and effects deduplicated by path, and marks it
  `Dirty`; `Save_Click` writes dirty tables after the LITs (previous file kept in
  `%LOCALAPPDATA%\RoseNextMapEditor\zsc-backups`). Appending never moves an id, so
  nothing else on the shared table changes, but every zone on that table sees the
  new object and the client needs a re-bake. There is no undo for an append; an
  unused appended object is harmless.
- **`ZscRaw` is the writer**, a byte-level mirror of `scripts/import-oro.py`'s `Zsc`
  (the parsed `ZSC` class is lossy: cylinder /100, collision bits folded, unknown
  part properties skipped). Two traps it handles: a dummy point's effect `0xFFFF`
  means *no effect* and must not be remapped; a source table can list one mesh
  path under two indices, so the lookup is repeated right before each append or
  the second part gets a duplicate mesh. `"Map Editor.exe" --zsc-selftest` (run
  from `data/`) round-trips all 62 tables byte for byte, appends every object of
  one table into another for six pairs and checks both readers plus the rotation
  maths; it found both traps.
- **Thumbnails** come from `Engine/RenderManager/ObjectThumbnails`: one worker
  thread with its own XNA device, newest request first, PNGs cached under
  `%LOCALAPPDATA%\RoseNextMapEditor\thumbnails` keyed by content hash (so an edited
  object gets a new picture and a copy in another table reuses one). Nothing waits
  for them: no "please wait" modal, and an object can be picked by name before its
  picture exists. The old per-tool copies of the render loop in `DecorationTool` /
  `ConstructionTool` are gone (`ConstructionTool` is still a sed-derived copy of
  `DecorationTool`; regenerate it from the decoration files rather than editing both).
- **Placement**: the tool says what it is doing. `HudManager` draws a mode line
  at the top left of the 3D view every frame (PLACING / SELECTED / idle, with what
  the next click does) and a four-second notice after each placement; the same
  text goes to the status bar and to a banner in the panel, which shows a Stop
  button while placing. The ghost carries a green box and a "Placing: name" label
  so it is never taken for a placed object. "Keep placing after each click" (on by
  default, `[Placement] KeepPlacing`) decides whether a click leaves you placing or
  places one and selects it; Shift+click does the opposite of the checkbox. Escape
  (or Stop) leaves the mode, the mouse wheel turns the ghost by the yaw snap step
  (5° when snapping is off; the camera never used the wheel), and the other
  options (Random heading, Vary size ±10%, Align to slope) apply to each copy. A click on empty ground deselects;
  Paste makes a new object under the mouse (or 2 m beside the original) instead of
  overwriting the selection, and refuses a copy from another zone's table. Follow
  Terrain is on by default. Also fixed on the way: `Select()` added gizmo handlers
  on every call and never removed them; the closest-hit loop indexed the wrong
  list; Delete fired while typing in a panel field (now only with the mouse over
  the map). `Place()` refuses a spot no block file covers instead of indexing
  `IFOs[-1]`.
- **A WPF `TextBox` in the main window never receives keystrokes.** `App.Engine.Run()`
  (XNA) pumps the window's messages from `Window_Loaded`, so WPF keyboard input, which
  is delivered through `ComponentDispatcher` by the WPF loop, never arrives; mouse input
  does (it goes through the window procedure), and the shortcuts are bound to `KeyUp`
  for the same reason. That is why the original water tool's Z field is a WinForms
  box in a `WindowsFormsHost`: do the same for any typed field in a side panel (the
  browser's search box and the degree fields are). Dialogs (`New`, `Open`, `Search`)
  are separate windows with their own loop and may use WPF boxes.
- **Rotation** is yaw / pitch / roll in degrees for a Z-up world
  (`Engine/Extensions/Rotation.cs`: roll about Y, then pitch about X, then yaw
  about Z, built and decomposed through XNA's row-vector matrices; the self-test
  proves the round trip). The old sliders mapped yaw and roll to each other's
  handler. The property grid still shows the raw quaternion.
- **Survey bug sweep (2026-10-11), applied to every tool and panel**: Delete is
  honoured only with the mouse over the map; selection is edge-triggered on the
  press; the closest-hit loop indexes `worldObjects[mouseSelections[i]]`; each
  tool's `Select()` unsubscribes its gizmo handlers first; W/A/S/D ignore the
  camera while Control is held (Ctrl+S used to walk backwards); the window's
  Ctrl+Z/Y/X/C/V skip a focused text field; a tile or brush stroke is one undo
  command (merged per cell while the button is down, pushed on release) instead of
  one per frame, which used to fill the 100-slot stack in a drag; all six
  remaining panels use `RotationEditor` (the old sliders mapped yaw and roll to
  each other and recorded an undo entry on every mouse-up); Animation's thumbnail
  cache check was off by one (regenerated every open) and its Find validated
  against the decoration table; the Tile tooltip showed the top-texture id while
  Find took the tile index; an empty brush palette crashed `SelectTile(0)`; the
  NPC name search started at row 0 for a list that starts at 1; a monster "add"
  recorded no undo and "clone" never refreshed the scene; the water Z field
  recorded an undo per keystroke; the Height inner radius started at 0 with a
  minimum of 1 and could exceed the outer. Regression: `tests/Run-MovementTests.ps1`
  (tile/brush undo, tools) and `tests/Run-ObjectBrowserTests.ps1`.
- **Terrain picking hit a flat plane, not the ground** (fixed 2026-10-11).
  `Heightmap.PickPosition` built both test triangles of a cell with every corner
  at the cell box's `Max.Z`, and that box took its height range from only two
  diagonal corners. On any slope the cursor hit a horizontal plane at one
  corner's height, up to a cell's rise off the real surface, and the hit slid
  along the view ray. Every placement, the cursor move and the status bar's
  position went through it. It now intersects the two triangles the terrain is
  drawn with (`Indices`: the diagonal runs west-north to east-south, the same
  diagonal `TryGetHeight` interpolates on), and the cell boxes span all four
  corners. `Heightmaps.GroundHeight(x, y)` is the interpolated ground height
  with the old nearest-vertex `Height.GetHeight` as fallback; Follow Terrain
  and the cursor move use it (they used the nearest vertex, so a dragged object
  stepped by half a cell's rise). `Height.GetHeight` remains for the height
  brush, which edits vertices.
- **`BoundingBox.Draw` created a Direct3D vertex declaration per call and
  never disposed it** -- hundreds a frame with "Draw bounding boxes" on, released
  by the finalizer and the 5-second forced GC: the stutter people see while
  placing. `BoundingBoxBatch` keeps one declaration per device (both Draw
  overloads use it) and draws every visible box of the object tool in one call;
  the other tools still draw per box but no longer leak. The placement ghost's
  box comes from each part's object-space box made once in StartAdding, not
  from every vertex per frame.
- **View > Frame statistics** (`[Debug] FrameStats`, `Engine/FrameStats.cs`)
  writes one line every two seconds: average and worst frame, update / draw /
  pick / ghost / boxes time per frame, boxes drawn, thumbnails pending, gen-2
  collections, plus the worst frame's own split (update / draw / ui / other).
  First measurement (2026-10-11, Birth Island, boxes on): steady 16.7 ms
  (vsync), draw 5-8 ms, pick 0.1, ghost 0.03, 600 boxes 0.35 ms. Every
  interval with a gen-2 collection had a 31-35 ms worst frame against 18-20
  without: the forced `GC.Collect()` every 5 s in `Main.xaml.cs` cost ~15 ms
  each time and is gone (it dated from the leak above). The 90-330 ms spikes
  were "other" time: the thumbnail worker (its GPU read-back stalls the
  device the editor draws with) and WPF work on the shared UI thread while
  the palette is in use. The worker now sleeps 8 ms between renders and
  waits while `ObjectThumbnails.Busy` (placing, or the button down over the
  map). The browser's UI-thread work is measured as `ui`.
- `tests/Run-ObjectBrowserTests.ps1` builds the editor, then against the real
  data: catalogue and search, a foreign crane appended into Junon Polis' table
  and saved to `build/object-browser-tests/` and read back by both readers with
  every original index and byte intact, thumbnails made and cached, the browser
  and rotation editor drawn to `browser.png` / `rotation.png`.

## Fullscreen view (F11)

**View > Fullscreen** or **F11** shows the map alone over the whole screen, for
hand-taken screenshots; F11 or Escape leaves it. It hides the menu, toolbars,
status bar, output and tool panel, makes the window borderless and maximized,
and draws the world only (no gizmos, tooltips or preview panel, like
`--shots`). It also switches off the editing helpers `--shots` jobs hide
(`SHOT_HIDE`: Collision, SpawnPoints, WarpGates, Sounds, Effects,
EventTriggers, GridOutline, GridNumbers) **in memory only**, and puts them
back on leaving. Closing the editor while fullscreen leaves it first, so the
config file never saves the hidden state. Code: `Main.ToggleFullScreen`
(`Main.xaml.cs`) and the early return in `Engine/Main.cs` `Draw`; the
backbuffer already follows the render panel's size every frame.

## Architecture

Entry flow:

1. `App.xaml.cs` — application entry. Installs three global exception handlers
   (WPF dispatcher, AppDomain, WinForms thread) that all funnel to `Output.WriteException`.
   Loads config via `ConfigurationManager`, then creates and shows the `Main` window.
2. `Main.xaml(.cs)` — the WPF main window. Hosts the XNA render surface in a WinForms
   `Panel` (`RenderPanelHost.Child`, exposed as `RenderPanel`). Wires up timers,
   menus, manipulation modes, and the right-side tool panels.
3. `Engine/Main.cs` — the XNA `Game`-style render/update loop driving everything below.

Globals live on `App`: `App.Form` (the WPF window) and `App.Engine` (the XNA engine).

### Engine manager layout (`Map Editor/Engine/`)

The engine is organized into single-responsibility *managers*:

- **`FileManager/`** — binary readers/writers for ROSE formats. This is the
  serialization heart of the editor.
  - `Data/` — `STB` (tables), `STL` (localized strings), `TileSet`, `LTB`
  - `Map/` — `ZON` (zone metadata), `IFO` (per-block objects/NPCs/events/water/collision/sounds), `HIM` (heightmap), `TIL` (tiles), `LIT` (lightmaps), `MOV` (movement/walkability)
  - `Models/` — `ZSC` (object defs), `ZMS` (meshes), `ZMO` (motions)
  - `Character/` — `CHR` (NPC/monster model defs)
  - `FileManager.cs` / `FileHandler.cs` — dispatch + low-level binary IO
- **`MapManager/`** — runtime, in-memory map objects grouped by domain:
  `Terrain/` (Heightmaps, Water), `Objects/` (Decoration, Construction, Animation,
  Collision, EventTriggers), `Characters/` (NPCs, Monsters), `Events/` (SpawnPoints,
  WarpGates), `Misc/` (Effects, Sounds, Sky). `MapManager.cs` orchestrates load/save.
- **`ToolManager/`** — interactive editing tools, one per editable object type,
  mirroring the MapManager domains. `Manipulation/` holds Translate / CursorTranslate
  gizmos; `ITool` is the common interface.
- **`RenderManager/`** — `ObjectManager`, `AnimationManager`, `TextureManager`, and
  debug `Primitives/` (Cone, Cylinder, Sphere, Radius).
- **`ShaderManager/`** — one wrapper class per HLSL effect (Height, HeightEditing,
  Object, NPC, Animation, TileRotation, SimpleColour, SimpleTexture). Compiled
  shaders ship as `.xnb` under `Content/`.
- **`CameraManager/`** — Orthographic + Perspective camera types.
- **`SpriteManager/`** — `FontManager`, `ToolTipManager`.
- **`UndoManager/`** — command pattern. Each editable type has a `Commands/<Type>/`
  folder with `Added` / `Removed` / `Positioned` / `ValueChanged` (and type-specific)
  commands implementing `ICommand`. Touching edit behavior usually means touching
  the matching undo command too.

### UI (`Map Editor/Forms/`)

- `Forms/Controls/*.xaml(.cs)` — the right-side editing panel for each tool
  (BrushTool, HeightTool, TileTool, WaterTool, DecorationTool, ConstructionTool,
  AnimationTool, CollisionTool, EventTriggerTool, NPCTool, MonsterTool,
  SpawnPointTool, WarpGateTool, EffectTool, SoundTool, plus `NPC/PreviewPanel`).
- `Forms/New`, `Forms/Open`, `Forms/Search`, `Forms/Tools/Options` — dialogs.

### Misc (`Map Editor/Misc/`)

- `ConfigurationManager.cs` — loads/validates editor config.
- `Output.cs` — logging. Every output line and all exceptions are mirrored to
  `../../data/Map Editor.log`.

### Editor-local data

- `ESTB/` — editor-only tileset helper STBs (`Table_Tileset_*`, `TileLookup_Type_*`,
  `EDITOR_System_Object.STB`) checked into this project. The editor resolves these
  from **both** `3Ddata\ESTB` (old layout) and root `ESTB` (current Rose Next layout)
  — keep both lookups working.

## ROSE Data File Reference

| Ext | Purpose |
|-----|---------|
| `STB` / `STL` | data tables / localized strings (e.g. `LIST_ZONE.STB`, `LIST_ZONE_S.STL`) |
| `ZON` | zone-level metadata, textures, spawn points |
| `IFO` | per-block objects, NPCs, monsters, events, water, collision, sounds |
| `HIM` / `TIL` | terrain heightmap / tile indices |
| `MOV` | per-tile walkability/movement |
| `LIT` | object/building lightmaps |
| `ZSC` / `ZMS` / `ZMO` | object definitions / meshes / optional motions |
| `CHR` | NPC/monster character model definitions |

## Debugging Workflow

The editor logs to `../../data/Map Editor.log`. When a bug is reported:

1. Read the tail of the log — it records the load *stage* and full stack traces.
2. Trust the logged stage/trace before guessing.
3. Patch source → rebuild Release x86 → copy `.exe` + `.pdb` into `../../data`.
4. Clear the log before asking the user to retest.

```powershell
Get-Content '..\..\data\Map Editor.log' -Tail 200
Clear-Content '..\..\data\Map Editor.log'
```

## Editing Guidelines

- **Keep changes narrow.** This is old UI/tooling code with many implicit
  assumptions; avoid broad refactors and formatting churn.
- **Be tolerant of optional assets.** Log missing optional models/textures/motions
  and continue; only abort a map load when a *required* file is missing. Never
  silently swallow new exceptions in load paths — log context + the full exception.
- **WPF threading.** Updates to WPF controls from background threads must go through
  the dispatcher.
- **Don't touch game data** to fix editor code unless the user explicitly asks.
  Editing `../../data` is a separate concern from editing this source tree.
- **A saved map reaches the two halves of the game differently.** The servers
  read `data/` directly (`server.toml` `data_dir`), so a save applies on their
  next restart; the client reads maps from `rose.vfs` (no loose `3ddata/maps` in
  the launch folder), so the same save needs a VFS re-bake + deploy before it is
  visible in game.
- **Saving is all-or-nothing and has no undo.** `Save_Click` rewrites the ZON,
  every IFO, every TIL, every HIM and all LITs of the loaded map, with no dirty
  tracking and no backup — and `data/` is git-untracked by design. Back up the
  zone folder before an editing session.

## Compatibility Fixes Already Made

- **NPCs and monsters are drawn in their stand pose (2026-10-06).** The editor used to
  draw a skinned character mesh's raw vertices, i.e. the bind pose the artist skinned
  it in: most characters stood in a T/A-pose, and rigs whose bind pose is far from
  standing came apart -- Rose Brasil's `[God] Hebarn` (LIST_NPC 4350, `BOSS_weilian`,
  a 3ds Max Biped used as a horse plus a rider on custom bones) showed the rider
  floating above the saddle and the whole model ~3 m off its placement.
  `CharacterPose.ForCharacter(id)` (`Engine/FileManager/Character/`) reads the
  character's skeleton and motion slot 0 from `LIST_NPC.CHR` and poses each mesh with
  frame 0 on the CPU, once, when the mesh is loaded -- the engine's own maths (motion
  channels replace the ZMD bind rotation/translation; vertex moves by inverse(bind
  world) x posed world, row-vector, quaternions stored w,x,y,z, ZMD in cm). `ZMS.Load`
  now keeps the bone table and skin weights it used to skip (same bytes read);
  `ZMD.cs` is new. All four character builders use it: map NPCs, map monster spawns,
  the NPC preview panel, the monster tool's thumbnail. `ObjectManager.AddPosed` caches
  a posed mesh under path + pose, so it never shares a buffer with an unposed copy.
  Anything that cannot be posed is drawn as before: no skeleton or slot-0 motion, a
  missing file (logged once: `drawn unposed`), a ZMS6-or-older mesh (centimetre
  vertices, skipped on purpose), or a bone reference outside the skeleton. Picking and
  selection boxes follow, since they are built from the posed vertices. Only the
  editor's view changes; nothing is written. Verified 2026-10-06 with `--shots`
  old/new pairs: Hebarn (Brasil zone 111) seated and centred; Junon Polis and Xita
  Refuge NPCs and spawns in their idle stance, 0-2.5% of pixels changed, no log
  errors. Still not done: animation (the editor shows frame 0 only).

- **Packed clients open directly (2026-10-04).** Copy the editor into any client
  folder and run it there: if the folder has a `data.idx`, `GameData.Mount` (called
  from `FileManager.Initialize`) opens it and every `.vfs` it names, and all reads go
  loose-first, then archive. Every reader routes through `Engine/FileManager/GameData.cs`
  (`OpenRead` in `FileHandler`, `Exists`, `GetFiles` for map folders, `LoadTexture`
  for every `Texture2D.FromFile` on game data); new code that reads game files must
  use it too, or it silently works on loose data only. Archive keys are normalized
  (upper case, `/` and doubled `\\` collapsed, root-relative). The cipher is detected
  per index by decoding a sample of STB/ZMS/ZMO/ZMD/DDS files with each
  `VfsCipher.All` entry (`Engine/FileManager/VfsArchive.cs`): plain (retail, iROSE,
  Rose Next) and **Wish Online** (Taiwan 2010: per file, a size-bucketed rotation, the
  key = the stored byte at that rotation = the file's first byte, the rest XORed with
  it; files of 128 bytes or less are stored plain). The log says
  `cipher ... (n/24 sample files read)`; a new client's scheme goes into `VfsCipher.All`.
  **Archived files are read-only**: Save, the MOV panel and New Map refuse when the
  map or LIST_ZONE comes from an archive, and `FileHandler` refuses to write any
  archived path as a backstop -- a loose copy would shadow the packed one from then
  on. Verified 2026-10-04 with `--shots` on Wish zones 49 (Oblivion Temple), 42
  (Pyramid Tombs) and 26 (Forest of Wisdom): 24/24 cipher samples, no missing files,
  full render; our `data/` and tsuki (loose) load unchanged; movement tests pass.
  Not handled: compressed index entries (skipped and counted; no known client uses
  them), and a client with no `LIST_DECO_SPECIAL.ZSC` still crashes at startup in
  `WarpGates`/`Collision`, which index objects 1 and 2 unconditionally.

- **Saving a Karkia or Skaaj map destroyed its IFOs (2026-09-23).** Every Jrose-origin
  IFO (all 141 in `KARKIA\*` and `SKAAJ\SKTOWN`) has no MapInfo lump 0, so
  `MapInfo.MapName` stayed null and `IFO.Save` threw inside `BinaryWriter.Write`.
  `FileHandler` opens for writing with `FileMode.Create`, so the first IFO was left
  as a 188-byte stub (every object, NPC, spawn and warp gone), and the exception on
  the raw save thread took the editor down with the ZON already rewritten.
  `FileHandler.Write<BString>` now writes null as empty. Both the client
  (`CMAP::ReadMapINFO`) and the server ignore lump 0, so the empty MapInfo lump the
  editor now adds is inert, like the empty object/water lumps it always wrote.
  Verified with a headless load-and-save of every map file through the editor's own
  readers and writers (all Karkia zones, Skaaj, Zant JDT01, Sunshine Coast SUM_EVENT):
  no failures, every object field and extra byte-identical, positions within 0.02 cm,
  TIL and LIT byte-identical, HIM heights identical. The one intended difference: the
  HIM trailer's per-patch height bounds, which Jrose stores as real values, are
  rewritten as the +/-FLT_MAX placeholders every retail Junon HIM already carries --
  conservative for culling, and correct after the terrain is reshaped.
- **Deleting a placed decoration/construction object misassigns lightmaps (known,
  not fixed).** LIT entries are keyed by 1-based ordinal within the block's lump and
  `RemoveAt` does not renumber them, so every later object takes its neighbour's
  lightmap; the client's `LoadLightMapINFO` also indexes `m_pObjectIndex` with that
  ordinal unchecked. Move or sink an object instead of deleting it. New objects are
  appended, get no LIT entry, and render without baked lighting. Since mapgen phase 8
  step 3 (2026-10-03) generated zones (`MAPGEN*`) ship full LITs too, so this applies
  to them: change the layout and rebuild with `scripts/mapgen-zone.py` rather than
  editing and saving a generated zone here.

- **A blank sky column no longer hides a map (2026-09-17).** `IsValidMap` rejected any
  LIST_ZONE row whose sky cell (editor column 8, game column 7) was empty, and the load
  path did `Convert.ToInt32` on it. The client reads that cell as an integer, so blank
  means sky 0 -- Jrose leaves it blank on 11 maps (Skaaj `LZON079`, MyRoom2, 8, 9, 36,
  73, 93, 133, 138, 140, 144) and none of them appeared in the Open dialog.
  `MapManager.SkyIndex` now resolves the row the client's way (blank/unparsable/out of
  range -> 0, with a log line for the latter two). Jrose's `LIST_ZONE_S.STL` is the old
  `I_NUM` dialect the STL reader cannot parse, so its Open list shows keys (`LZON079`)
  rather than names; the ID column is the reliable handle. Verified with a headless
  `FileManager.Initialize()` harness against the Jrose data: 100 maps listed,
  `IsValidMap(79)` true, `SkyIndex(79)` 0.
- **Movement painting (2026-09-13).** Open a map, then **Tools > Movement (.MOV) >
  Paint movement permissions**, or the **MOV** toolbar button. Left-drag paints
  5 m cells with 1/3/5/7-cell square brushes; one drag is one undo command.
  Green = allowed, red = blocked; blue/purple = missing-file allowed/blocked
  defaults; yellow previews the brush. The overlay follows HIM triangles.
  **The current game has two effective MOV states, not three:** `0` permits
  `SetCMD_MOVE2D`; every nonzero byte blocks it. Players and attack chasing do not
  consult MOV. Existing nonzero bytes are preserved until explicitly painted.
  `MovementMaps.Find` follows the server: filename `x_y` maps to server block
  `(x, 64-y)`, with MOV rows growing northwards (the reverse of HIM rows).
  The panel's **Save / generate MOV files** writes only movement files; normal
  Save includes pending MOV edits. Creating the first file also generates all
  missing blocks, preserving the server's no-MOV fallback instead of accidentally
  blocking untouched terrain. Existing partial coverage defaults missing blocks
  to blocked. Each replacement is atomic and backs up the previous file under
  `.mov-backups/<timestamp-id>/`; the whole map is not a single transaction.
  Failed writes retain unsaved edits for retry. Malformed MOV disables movement
  editing without preventing the rest of the map from opening. Closing/opening
  another map prompts for unsaved movement edits. Restart the server to apply.
  Run `tests/Run-MovementTests.ps1`: builds Release x86, checks actual MOV files
  byte-for-byte, server coordinates, coverage generation, backup/retry behavior,
  cross-block brush + undo/redo, and actual XNA rendering/state restoration.
  Passed against 1,369 map MOV files; interactive in-editor/in-game retest pending.

- **Karkia lightmap trailers and zero-height spawn previews (2026-09-12).** All 98
  Cemetery LITs end after the object records; the trailing DDS catalogue is optional
  and the game never reads it. `LIT.Load` accepts EOF there, preserves whether the
  catalogue existed on save, closes its reader on failure, and logs actual exceptions.
  All 847 Cemetery regen entries store Z=0 although ground is 5-43 m higher. Monster
  previews now sample terrain triangles for zero-height entries; explicit nonzero
  heights and stored IFO coordinates stay intact. Model bounds, inactive/empty markers,
  selection handles and radius overlays use the display position. The minimap preview
  already worked because it only needs XY. Real XNA loader checks passed Cemetery
  (847 spawns) and Spire Village (278); all 220 Karkia LITs and the Lion's Plains LITs
  round-tripped byte-identically to temporary files. Terrain interpolation, selection
  bounds and unchanged stored spawn positions passed; GUI retest pending.
- **Transform terrain relative to its block origin.** Lion's Plains (667, JPVP04)
  decoration 158 in `34_33.IFO` is the circular `m-kwangjangside` paving. Its lowest
  surface sits about 2 mm above the terrain near world coordinates (5440, 5067).
  Multiplying large terrain coordinates by a combined view/projection matrix in
  the vertex shader lost enough precision to draw the ground through the paving
  as the camera moved. `Heightmap.Draw` now supplies a block origin and a combined
  translation/view/projection matrix; both Height shaders subtract that origin
  before transforming. Stored vertices, culling, picking, brush world coordinates,
  and game assets remain unchanged. Default editor depth was already Depth24.
  Verified 2026-09-12 with actual XNA draws of the platform and underlying terrain
  at 15 camera positions, in normal and height-editing modes: up to 106,093 platform
  pixels were incorrectly covered before; zero after, against platform-only renders
  (RGB total-difference tolerance 20). Release x86 build passed; GUI retest pending.
- **Morph materials must use their STB depth/transparency flags.** Kenji's shoreline
  waves (`LIST_MORPH_OBJECT` rows 1-3) have depth testing on and depth writing off.
  The editor previously ignored those flags: transparent wave triangles wrote depth
  and cut polygon-shaped holes in the water drawn afterwards. `Objects.Animation`
  reads alpha/two-sided/alpha-test/Z-test/Z-write/blend-op from editor cells
  5/6/7/8/9/12 (game column + 1), and `AnimationManager.Draw` applies them and
  restores the caller's depth/cull state afterwards. Material-cache identity includes
  render settings as well as the texture path; distinct materials share image storage
  without sharing flags. Verified 2026-09-12 with actual XNA GPU draws of all three
  Kenji wave meshes/motions at three views: the original blocked 32,195-40,960 pixels
  of a diagnostic background plane; fixed draws blocked zero. Wave-only images were
  pixel-identical before/after. Material disposal/state restoration and ODP01/ODFS01
  terrain/scenery/NPC/monster loading also passed; user confirmed the Kenji fix.
- **Share object lightmaps by full path.** Fossil Sanctuary (667, ODFS01) has
  2,710 lightmapped part instances sharing 112 atlas textures across decoration
  and construction. Loading a DDS per part consumed about 2,247 MiB of nominal
  base texture storage instead of 70 MiB and exhausted the x86 editor while
  loading objects. `ObjectManager.LoadLightmap` caches by case-insensitive full
  path; parts retain independent UV transforms. The manager owns these textures
  until `Clear`, including textures detached from draw batches by editing/undo.
  `ClearBatch` must not dispose them; `Clear` disposes each texture once and also
  releases mesh vertex/index buffers. Tested with real XNA terrain, scenery, NPC
  and monster loads for ODP01 -> ODGR01 -> ODFS01 -> ODGR01 -> ODFS01, including
  disposal checks after clearing draw batches (2026-09-11). GUI retest remains
  separate from this loader check.
- Tileset helper STBs resolve from both `3Ddata\ESTB` and `ESTB`.
- **A bad global table no longer kills startup.** `FileManager.Add` registers an empty
  placeholder for a missing or unreadable STB/STL/ZSC/CHR and continues, and `STB.Load`
  checks the `STB` signature up front so the log names the file instead of dying with a
  bare `EndOfStreamException`. This is what foreign data sets trip over — QQ-iROSE ships
  an *encrypted* `3Ddata\TERRAIN\TILES\ZONETYPEINFO.STB` (editor-only data; the game
  itself never reads that table), which used to abort `Initialize()` and leave every
  later dictionary lookup throwing `KeyNotFoundException`. With no zone-type table,
  `GetTileSetFile` falls through to `InferTileSetFile`, so maps still load and only the
  tile brush palette is empty. The default constructors of STB/STL/ZSC/CHR allocate
  their collections so a placeholder is safe to read.
- Out-of-range object references in an IFO are skipped with a log line rather than
  aborting the map load (`Object.Add` bounds-checks the IFO's object ID against the
  zone ZSC, and each part's model/texture ID against the ZSC's lists).
- Map loading wrapped in stage-specific exception logging with UI unfreeze on failure.
- `Output` mirrors every line and full exceptions to `Map Editor.log`.
- Heightmap fallback allocates `ShadowMapRaw` before filling a default shadow texture.
- Empty/missing optional ZSC motion paths are skipped instead of opening an empty `.ZMO`.
- Monster list remove guards against `SelectedIndex == -1`.
- Tactical monster removal uses `TacticalList.SelectedIndex` (not `BasicList`).
- Newly added monster row is auto-selected after adding to a spawn.

## Verification Checklist

**Map-load fixes:** open a Junon and a non-Junon map; confirm the log reaches
`Loading Completed`; review missing-optional-asset logs for acceptability.

**Monster/spawn UI:** select a spawn; add+delete a Basic monster; add+delete a
Tactical monster; try Delete/Remove with nothing selected (must not throw); test
undo/redo if undo commands were touched.

**Object/terrain:** open a map with decoration + construction; pan to force
rendering; confirm load finishes and the UI unfreezes after any failure.
