# 667 UI reverse-engineering investigation

> The investigation tools this document runs (`audit-667-ui.py`, `inspect-667-hud-assets.py`, `trace-667-ui.py`) were removed from `scripts/` on 2026-10-12 once the investigation was closed; they are in git history before commit d17ceb1c.

Initial static reconnaissance, 2026-09-23. Source client:
`C:\Users\Thomas\Desktop\Testclients\667`.

Follow-up: [avatar-info HUD behavior and framework differences](667-avatar-hud.md)
and [final focused pass / HUD prototype readiness](667-hud-port-readiness.md).
traces the compact shipped layout, text-capable images, gauge animation, input,
and external status/gauge ownership. It includes reproducible disassembly and an
art-only reconstruction.

## Finding

Adapting this UI is a credible engineering project. We have the layouts, atlas,
named control-library exports, and executable RTTI needed to locate dialog code.
This investigation establishes that starting point; it does **not** claim a complete
behavioral reconstruction or a working port. No game code or assets were changed,
and the donor executable has not been launched.

The work needs to cover the control framework, individual dialog behavior, and
bindings to our game state. Understanding everything in the executable is not a
prerequisite for adapting a particular dialog. Identical appearance does not require
importing donor gameplay systems, inventory limits, or network packets.

## Reproduce the evidence

Run from the repository root (Python with `pefile` and `capstone`):

```powershell
python scripts/audit-667-ui.py
```

The tool reads donor binaries/assets and our layouts. It writes only its output
directory, by default `build/667-ui-audit/`:

- `audit.json`: XML node trees, ID/type differences, PE hashes/imports/exports,
  selected strings, candidate calls through the UI imports, selected RTTI method
  tables, and UI2 texture presence/counts.
- `TGameCtrl_r.dll.asm.txt`: bounded disassembly previews of selected named methods.
- `TRose.exe.asm.txt`: empty, since the executable has no exports.

The audit ran successfully against all three layout sets without XML parse errors.
TSI decoding consumed the file exactly and recovered 1,012 sprite records, matching
the declared total. These checks validate extraction, not runtime compatibility.

Binary SHA-256 identities:

| File | SHA-256 |
| --- | --- |
| TRose.exe | `21802bf965fdca1fd475d6c5fe9025ba8b28c0cdcf388b58ff34090610f00e52` |
| TGameCtrl_r.dll | `2158f01f52f2807c5b4623f30fc2cd494549108c0b3de1c2449470b764afa583` |

## Assets and structural differences

667's loose layouts are under `3Ddata/Control/Xml`; its extracted textures and
atlases are under `extracted data/3DDATA/CONTROL/RES`. Looking only in the extracted
CONTROL directory misses the layouts.

| Measurement | Result |
| --- | --- |
| Donor XML files | 78 |
| Current XML files | 56 |
| Current dormant XMLNEW files | 63 |
| Shared donor/current filenames | 53 |
| Shared files missing at least one current nonzero ID | 38 |
| Shared files with different tag sets for a shared nonzero ID | 7 |
| Shared donor/XMLNEW files byte-identical | 2 of 61 |
| UI2 textures | 45, all present |
| UI2 sprites | 1,012 |

The ID comparisons aggregate by file, not parent scope. They identify investigation
targets, not a count of guaranteed crashes: some IDs are decorative, duplicate IDs
may live in separate panes, and some controls are built in code. Full hierarchy is
retained in the JSON for the semantic comparison.

Examples:

- Inventory: our 287x537 layout becomes 306x468. IDs 5, 11, 21, 22, 31, 41,
  and 42 disappear; ID 400 is added. Our `CItemDlg` still names ID 11 as its
  iconize button and creates equipment/inventory slots with compiled offsets in
  `src/client/interface/dlgs/citemdlg.cpp`. Moving XML alone cannot move those slots.
- Quickbar: 401x63 becomes 530x70; the ID set changes substantially and a separate
  `DlgQuickBarExt.xml` exists. Its exact slot/key behavior still needs tracing.
- Options: 225x260 becomes 350x306. IDs 55, 60, 65, 70, and 75 change from
  RADIOBOX to CHECKBOX. C++ casts and event semantics must be checked explicitly.
- Chat: 392x321 becomes 405x340, removes ID 5 and adds 8/9. Similar ID sets do
  not establish equivalent behavior.

Donor-only filenames include storage, skill HUD, world map, arena, reinforcement,
empowerment, and multiple item-mall dialogs. File presence alone does not establish
which are active. Port scope should distinguish shared windows from systems absent
in our game.

667 uses module 11 / UI2 in its inventory XML. The executable contains paths to
`Control\XML\UI2_strID.ID` and `Control\Res\UI2.TSI`. Its atlas includes
`ui00_2.dds` through later numbered sheets, `glassui_*`, map images, and skill-tree
art. It is not the five-sheet UI20-UI24 asset set described in the old XMLNEW notes.
Those historical notes explain past failures but cannot substitute for this audit.

## Binary footholds

Both binaries identify as x86. The PE sections are ordinary `.text`, `.rdata`,
`.data`, etc.; imports, RTTI strings, and sampled instructions are readable. This
does not prove every part of the executable is unobfuscated.

- `TGameCtrl_r.dll` has 1,169 named exports, including overloaded `Find`, XML
  construction, image drawing, button processing, and layout hooks.
- `TRose.exe` imports 297 entries from that library. Linear executable-section
  disassembly found 2,657 candidate indirect call/jump sites through those IAT
  entries. This is a navigation index, not an exhaustive call graph.
- The EXE retains RTTI names for dialog, slot, icon, and drag-command classes.
- Embedded PDB paths are `e:\rosenatrunk\src\client\Release\TRose.pdb` and
  `e:\rosenatrunk\src\common\TGameCtrl\Libs\TGameCtrl_r.pdb`. These are
  build-machine path strings, not recovered debug symbols. The root folder's
  `Map Editor.pdb` is not a replacement for either PDB.

All addresses below are **preferred-image virtual addresses**, not file offsets
or guaranteed runtime addresses. DLL image base: `0x66000000`; EXE: `0x00400000`.

| Control-library entry | Address |
| --- | --- |
| CTControlMgr::MakeDialogByXML | `0x6602e060` |
| CTDialog::Find(int) | `0x66040b90` |
| CTDialog::Find(const char*) | `0x66040c40` |
| CTImage::Draw() | `0x660481b0` |
| CTButton::Process | `0x660227a0` |
| CTDialog::RefreshDlg | `0x66041490` |
| CTDialog::SetInterfacePos_After | `0x660414c0` |

RTTI links type descriptors to complete object locators and method tables. The
primary tables below each contain 48 consecutive pointers into executable sections;
secondary tables are separately recorded in the JSON. Named import thunks establish
shared virtual slots. Local override names inferred from those slots remain subject
to body validation.

| Class | Primary method table | MoveWindow(POINT), slot 39 | RefreshDlg, slot 47 |
| --- | --- | --- | --- |
| CItemDlg | `0x78bf1c` | `0x545720` | imported base method |
| CAvatarInfoDlg | `0x78a6a4` | `0x527910` | `0x527ef0` |
| CChatDLG | `0x78bcdc` | imported base method | `0x53d720` |

### A confirmed behavioral difference

667's base `CTDialog::RefreshDlg` calls the named `CWinCtrl::GetPosition` at
`0x66004270`, pushes the returned POINT, then calls virtual slot `0x9c / 4 = 39`.
The executable's chat method table resolves slot 39 to the named
`CTDialog::MoveWindow(POINT)` import. Thus this base method refreshes placement by
calling the virtual MoveWindow with the existing position. Our
`src/tgamectrl/src/tdialog.cpp` defines `CTDialog::RefreshDlg()` as an empty method.

That is an example of behavior we can recover beyond XML, and a real difference
to investigate before adapting the newer layout. It does not by itself justify
changing the base method globally. The donor base `SetInterfacePos_After` sampled
here is empty; useful behavior may instead be in dialog overrides.

## Route to a verified adaptation

1. Trace asset resolution completely: module IDs, string IDs, TSI rectangles,
   nine-piece backgrounds, SIZEFIT, alpha conventions, clipping and draw order.
   Build static per-dialog previews as an aid; do not mistake them for runtime proof.
2. Recover each required dialog's constructor/Create, draw/update, Process,
   MoveWindow/RefreshDlg, control lookup and dynamic slot construction. Label
   functions from exports, RTTI tables and our corresponding source, then validate
   their bodies. Record control parent scope as well as IDs and types.
3. Start with the avatar-info HUD as a bounded end-to-end pilot. It has identified
   method-table entries and exercises positioning, gauges and dynamic text. Inventory
   is the next useful pilot because it exposes the C++ slot-layout problem.
4. For each pilot, write a specification covering dimensions, anchoring, visible
   states, input, tooltips and data bindings. Implement it against our existing game
   model; handle donor-only capabilities explicitly. Preserve our custom behavior
   such as item links, previews and tuning rather than silently replacing it.
5. Validate against observed donor behavior and in our client: hover/click/drag,
   keyboard focus, resolution changes, panel persistence, and interactions between
   overlapping windows. Inventory adds equip/use/split/drag-drop and server updates.
6. Expand dialog by dialog, keeping a matrix of confirmed, inferred, implemented
   and runtime-validated behavior. This is the meaningful definition of completion.

Runtime validation is still outstanding. This donor folder lacks several DLLs named
by the EXE's import table, including `znzin.dll` and `steam_api.dll`; a working
matching installation/runtime must be located before assuming it can launch.
An in-game session is also needed to verify state-dependent interactions. No missing
DLLs were borrowed from unrelated builds, and no connection attempt was made.

The original C++ source, local variable names, and all developer intent cannot be
promised from these artifacts. A behaviorally faithful UI specification and staged
port are much more realistic deliverables, supported by the evidence above.
