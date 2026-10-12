# 667 avatar-info HUD: recovered behavior

> The investigation tools this document runs (`audit-667-ui.py`, `inspect-667-hud-assets.py`, `trace-667-ui.py`) were removed from `scripts/` on 2026-10-12 once the investigation was closed; they are in git history before commit d17ceb1c.

Second investigation, 2026-09-23. Static evidence from the exact EXE/DLL hashes in
[667-ui-investigation.md](667-ui-investigation.md), compared with the current
`avatarinfodlg.cpp`, `tcontrolmgr.cpp`, `timage.cpp`, `tguage.cpp`, and `ctfontimpl.cpp`.
No game code/assets changed; no donor runtime session performed.

## Result

The shipped HUD is a **compact 210x100 panel**, not the screen-wide HUD described
by our dormant `_NEWUI` branches. Its visible features are recoverable, but it
depends on newer control-library behavior and some logic outside `CAvatarInfoDlg`.
Simply enabling `_NEWUI` would select the wrong layout logic and data bindings.

This pass recovered the main Create/MoveWindow/Show/Refresh/Draw/Update/Process
paths, constructor, gauge animation, and external status/gauge references.
Function bodies establish behavior; XML determines which optional paths can run.
Unresolved virtual data getters are named below by their strongly supported UI
role, not claimed to be recovered original symbol names.

An art-only reconstruction is generated at
`build/667-ui-audit/hud-assets/hud-art-preview.png`. It uses the actual DDS sprites
and XML positions. Gauges are full, text/status icons are omitted, and both auxiliary
gauges are shown regardless of runtime conditions. It is **not a game screenshot**
or proof of exact D3D filtering, alpha, clipping, or typography.

## Method map and an ABI finding

| Routine | Preferred VA | Evidence |
| --- | --- | --- |
| Constructor | `0x528320` | Base constructor, three table writes, 40x40 slot, offset (186,36) |
| Create | `0x5278e0` | Named CTDialog::Create import, virtual RefreshDlg on success |
| MoveWindow(POINT) | `0x527910` | Named base movement import, slot move, optional WEAPON_SLOT lookup |
| RefreshDlg | `0x527ef0` | Named/ID lookups, layout operations, final virtual MoveWindow |
| Show | `0x528dd0` | Named base Show import, named-control state changes, refresh |
| Draw | `0x528440` | Named base Draw import followed by field text updates |
| Update(POINT) | `0x528f10` | Named base Update import; caption, gauges, tooltip checks; ret 8 |
| Process | `0x528a20` | Named base Process import; WM_LBUTTONDOWN/UP; ret 12 |
| Observer Update | `0x527990` | CTEventItem check, item/slot attach-detach paths |
| Post-position hook | `0x5289f0` | Layout helper followed by virtual MoveWindow |
| Minimap-related helper | `0x5281a0` | Dialog lookup 10; conditional EXP coordinate passed onward |
| External status/auxiliary gauge routine | `0x4f4260` | STATUS_EFFECT, SUMMON_GAUGE, PAT_GAUGE lookups |

The method table at `0x78a690` is the **secondary control interface at object +32**:
destructor adjustor, Process, Update, Draw. Its first pointer `0x528310` subtracts
32 from `this` and jumps to the deleting destructor. The DLL exports also identify
CTGuage tables as `CTObject` and `ITControl` tables. This is why guessing method
order from our current C++ header would mislabel functions. The tracer's final
names reflect the actual calls and argument cleanup, not that initial guess.

This ABI difference is another reason to adapt behavior in our source rather than
drop the donor DLL into our build. Offsets and vtable indices in this report are
evidence for this binary only.

## Layout and bindings

The root is initially visible, top-left anchored, with adjustments (3,3). Its pane
and caption are 210x100. Nine background images actually extend to x=211/y=104;
declared hit bounds and painted bounds are not identical. Auxiliary gauges are
outside those bounds at x=220. Runtime clipping/hit dispatch still needs verification.

| Element | XML placement | Recovered binding |
| --- | --- | --- |
| Caption, unnamed | 210x100; text offset (15,11) | Update assigns the avatar name through CTCaption::SetString |
| HP, ID 6 | (12,27), 187x24 | Gauge value, current/max text, separate HP_PERCENT text |
| MP, ID 7 | (12,48), 187x24 | Same structure for MP |
| EXP_MINI, ID 0 | (12,69), 187x11 | Name-based lookup; value approximately EXP/requiredEXP * 1000; empty gauge text |
| HP_PERCENT / MP_PERCENT | Same rectangles as HP/MP; text offset (-6,-6) | IMAGE controls receive integer percent strings through virtual SetText |
| INFO_LEV_VALUE | (10,79), 187x16; text X offset -78 | Level formatted as `%d` |
| INFO_JOB_VALUE | Same rectangle; text X offset +27 | Job-name lookup from the avatar's job |
| INFO_WEIGHT | Same rectangle; text X offset +42 | Localized label (string lookup 107) |
| INFO_WEIGHTAGE_VALUE | Same rectangle; text X offset +79 | Integer current/max-weight percentage, `%d%%` |
| STATUS_EFFECT | (12,102), 15x15 | Position and dimensions consumed by external status drawing |
| SUMMON_GAUGE | (220,72), 100x10 | External routine hides first, shows when positive current/maximum values exist, sets ratio and `%d / %d` |
| PAT_GAUGE | (220,84), 100x10 | External routine hides first, conditionally shows under vehicle/item gates, sets value and percent text |

HP/MP Update clamps displayed negative current values to zero and skips the gauge
update when maximum is zero. Gauge unit size defaults to 1000 in the donor DLL.
The avatar percentage helpers at `0x4baad0` / `0x4bac60` compute current/max*100,
cap above 100, and maintain interpolation state. **This HUD calls them with false**,
selecting the immediate percentage. Smoothing for these XML gauges instead comes
from CTGuage's ANIMATE behavior below. Numeric text and percentage labels therefore
need not match the partially transitioned bar at every instant.

The compact EXP path computes its ratio with floating-point conversion and does
not show the zero-denominator guard used in the legacy ID-8 path. Its denominator
includes an additional avatar field. Preserve our own 64-bit EXP model/requirements
when adapting; the donor's integer layout is not a suitable model to copy.

EXP's nine tick marks are repeated `GEN_DECO38` images. This compact panel uses
one continuously filled gauge with decorative ticks, **not ten independent gauges**.

When EXP_MINI is visible and the pointer is inside it, Update registers a tooltip
formatted as `%s %d/%d (%.2f%%)` at mouse position minus (20,20). The first string
comes from localized string ID 814. Tooltip work is skipped when another dialog
owns mouse-over. The numeric fields in Draw are assigned after CTDialog::Draw;
the assignment order is confirmed, while frame-visible latency needs runtime testing.

## Active versus dormant behavior

- Click ID 10 on WM_LBUTTONUP calls `0x41d2f0`, which reads the local avatar index,
  tests it through the input state, and passes it to target selection. Together with
  the corresponding current source this strongly identifies self-targeting. It is
  **not** the minimize action in our `_NEWUI` branch.
- Donor Process retains expand/collapse paths for IDs 11 and 14 and option paths
  for 100-103. Those controls are absent from this DLGINFO. They are not reachable
  from this XML's buttons. The four-entry switch was explicitly decoded; the tracer
  does not silently skip its indirect jump.
- The binary supports a WEAPON_SLOT anchor and still constructs the old slot. Draw
  and Update guard it by that name; the shipped layout has no WEAPON_SLOT, so it
  does not draw/update the weapon icon there. Observer item bookkeeping remains.
- ID 8, EXP, EXP00-EXP09, Exp_BG, Info_bg, WindowMode, FullMode, DETAIL_PAN,
  named Caption, SOUND, CHAT, TIP, and CTRL are absent. Their legacy full-width
  refresh and toggle paths remain compiled but their guarded lookups miss.
- The caption is an actual CAPTION with an empty NAME, so its direct SetString
  works while `Find("Caption")` misses. Consequently the Show path's conditional
  screen-width expansion does not run for this file.
- Refresh still ends by applying MoveWindow to the current position. The
  minimap-related helper's expanded-state adjustment requires the absent EXP
  control, so this layout does not trigger that adjustment through this path.

## Framework changes that matter

### IMAGE controls gained text rendering

The donor `MakeImageByXML2` (`0x66030f80`) reads FONT, text offsets, HALIGN/VALIGN,
RGB properties and ELLIPSIS. `CTImage::Draw` (`0x660481b0`) includes a font draw
path after its sprite path. Blank GID images can therefore act as labels.

Our image parser reads geometry/sprites/scales but not those text properties, and
our CTImage Draw is sprite-only. Our avatar Update also casts HP_PERCENT and
MP_PERCENT to CTStatic; the donor XML declares IMAGE. That cast must not be carried
into a port. Implement suitable text-capable controls or translate these nodes to
an explicit supported text type and update their bindings.

Font values such as 100010, 110009 and 210010 need translation. Our CTFontImpl
accepts indices bounded by MAX_FONT. The precise donor font encoding, face/style,
metrics and ellipsis rules remain unresolved; copying the integers is not enough.

### Gauges gained animated fill and configurable text layout

`MakeGuageByXML` (`0x660383b0`) reads ANIMATE and calls SetAnimated, and also
handles FONT/alignment/text offsets. All five gauges in this HUD set ANIMATE=1.
Our current gauge parser does not read these properties; Create also overwrites
its height with 15, regardless of the XML height.

Donor SetValue (`0x66047ac0`) stores the target integer. Get_PercentValue
(`0x66047c00`) normalizes against unit size and uses this state machine:

1. First read initializes both interpolation endpoints to the current percentage.
2. Later reads interpolate between the previous start and target using a clamped
   elapsed-time fraction and a duration of **400 ms** (`0x190`).
3. On a changed target, the current interpolated value becomes the new start,
   the target is replaced, and the clock restarts.
4. ANIMATE chooses interpolated output versus the immediate percentage.

Draw turns the resulting percentage into a pixel width and caps it at control
width. Values are set during Update; animation is sampled while drawing. The
first-read timestamp has a special `now + 400` initialization and unsigned elapsed
arithmetic; exact first-frame/timer-wrap behavior is not runtime-validated.

This is display behavior only. A port must consume our existing presented HP/MP
and authoritative data flow, not import donor combat state or reconciliation.

### Status effects and extra gauges are owned elsewhere

`0x4f4260` fetches dialog 26 and reads STATUS_EFFECT offsets, width, and height
to position/scale status icons. The same function looks up SUMMON_GAUGE and
PAT_GAUGE, supplies values/text, controls visibility, and registers tooltips.
These are functional controls, not unused decorations outside the window.

The exact donor vehicle predicates, summon maximum, caller coordinate convention,
and tooltip strings still need mapping. Their byte offsets must not be treated as
our game-model offsets. This pass establishes ownership and integration points.

## Asset evidence and checks

All **20 distinct referenced sprite names** resolve through UI2_strID.ID into
UI2.TSI, with texture files present and crop rectangles inside texture bounds.
The asset report retains the numeric indices, rectangles, texture names and all
12 named controls. Images use glassui_00.dds, glassui_02.dds, glassui_04.dds,
and ui10_2.dds.

The frame's SIZEFIT strips stretch to XML dimensions; other images use atlas
dimensions. For example GEN_DECO42's sprite is 43x43 although its declared control
rectangle is 21x21. A reconstruction that resizes every image to WIDTH/HEIGHT
would silently change it. The PNG preview was generated and visually inspected.

The static tracer follows conditional/direct branches, stops on returns, annotates
named imports and string references, and guards both input binary hashes. Its
JSON reports unresolved indirect jumps; **indirect calls are not fully resolved**.
No unresolved jumps remain in the selected HUD/control routines after the verified
Process switch entries are included. This does not imply a complete call graph.

## Reproduce

```powershell
python scripts/trace-667-ui.py
python scripts/inspect-667-hud-assets.py
python scripts/trace-667-ui.py --entry 528320:CAvatarInfoDlg_ctor --entry 4f4260:status_and_aux_gauges --output build/667-ui-audit/hud-external
python scripts/trace-667-ui.py --binary TGameCtrl_r.dll --entry 66030f80:MakeImageByXML2 --entry 660383b0:MakeGuageByXML --entry 660475f0:Guage_ctor --entry 66047770:Guage_Draw --entry 66047ac0:Guage_SetValue --entry 66047ba0:Guage_GetValueUnitSize --entry 660481b0:Image_Draw --output build/667-ui-audit/controls
python scripts/trace-667-ui.py --binary TGameCtrl_r.dll --entry 66047c00:Guage_GetPercentValue --output build/667-ui-audit/gauge-animation
```

## Follow-up completed

Completed in [the final focused HUD pass](667-hud-port-readiness.md), including
the font mapping, child-before-caption input behavior, and status screen-coordinate
contract. The remaining checks now belong in a running HUD prototype.

Inventory can reuse that knowledge while exposing dynamic slot placement and
drag/drop contracts. Runtime validation remains necessary before calling either
reconstruction complete.
