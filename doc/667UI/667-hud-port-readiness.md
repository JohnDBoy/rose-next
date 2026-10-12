# 667 HUD: final focused static pass

> The investigation tools this document runs (`audit-667-ui.py`, `inspect-667-hud-assets.py`, `trace-667-ui.py`) were removed from `scripts/` on 2026-10-12 once the investigation was closed; they are in git history before commit d17ceb1c.

This completes the three follow-ups from [the HUD investigation](667-avatar-hud.md).
The result is sufficient to start an avatar HUD prototype, not a claim that the
entire 667 UI has been reconstructed. No production game code was changed.
Addresses below refer only to the two SHA-256-guarded binaries accepted by
`scripts/trace-667-ui.py` (EXE base `0x400000`, DLL base `0x66000000`).

## Font keys and text placement

EXE `0x444300` registers the font keys used by DLGINFO.XML:

| XML key | Registration name | Size argument | Style |
| --- | --- | --- | --- |
| 100010 | FONT_NORMAL_10 | 10 | Regular |
| 110009 | FONT_BOLD_09 | 9 | Bold |
| 210010 | FONT_OUTLINE_BOLD_10 | 10 | Bold, outline type 1; white text, black outline |

These are lookup keys, not indices into our existing small font array.
CTFontImpl's rectangle draw (`0x500170`) and point draw (`0x5001d0`) look up
the engine font handle through the map at the object referenced by `0x813808`,
offset `0xac`, then call the imported `drawFont` overloads. Implement an explicit
mapping in the port rather than indexing our font storage with these numbers.

The face is locale-dependent: selector `0x495760` includes Verdana (also the
fallback), SimSun, MingLiU, and a Japanese font-enumeration branch. This does not
establish the active donor runtime locale. Size above means the argument passed
to `loadFont`/`loadFontOutline`, not a proven pixel height. The matching local
engine signatures are in `src/engine/src/zz_interface.cpp`; donor engine rasterization
and installed-font fallback still need visual validation.

The caption omits FONT. `MakeCaptionByXML2` (`0x66031880`) reads the mutable default
at `0x6609e57c`, whose on-disk initial value is **210010**. It is not safe to assume
the caption inherits HP's 100010 font; initialization could also change that default.

XML HALIGN and VALIGN are combined with bitwise OR. Caption/Image SetAlign
(`0x66028690`, `0x66048db0`) store the flags unchanged and also forward them to
CSinglelineString. Their setters do not add a single-line flag. Values match the
DrawText alignment convention: left/top 0, center 1, right 2, vertical center 4,
bottom 8. The inspected rectangle font adapter forwards flags to the engine;
downstream engine treatment remains outside this static result.

Text offsets move the drawing origin; alignment still acts within the control's
width/height rectangle. In particular, HP/MP use right+bottom alignment with
offset (-51,-6), while their separate percentage IMAGE controls use (-6,-6).
The level/job/weight labels combine their own offsets with a 187x16 rectangle.
Do not replace this with a common centered label or use the animated fill width
as the text rectangle. Caption Draw (`0x660286f0`) likewise translates by control
position plus text offset, then draws into a local width/height rectangle.

## Caption dragging versus self-target

The inspected normal input route is:

1. CTDialog::Process (`0x660402d0`) processes child controls before its caption.
   A nonzero child result returns immediately.
2. CTPane::Process (`0x6604e130`) delegates to CJContainer::Process (`0x66008210`),
   which stops at the first nonzero result.
3. CTButton::Process (`0x660227a0`) consumes left-down inside its enabled, visible
   bounds, sets its pressed state, and returns its ID. A valid left-up returns
   the ID as well.
4. DLGINFO's no-image button 10 covers the full 210x100 panel. Its left-down
   therefore prevents CTCaption::Process (`0x660284e0`) from starting a drag on
   this route. The avatar dialog handles its release as the self-target action.

Dragging exists in the framework: caption left-down sets its clicked/exclusive
state; CTDialog::Update (`0x66040760`) checks IsClicked and moves the dialog by
the mouse delta. Having a CAPTION in XML alone does **not** make this panel
draggable through the overlapping button. For the first prototype, preserve
self-target and treat drag support as a deliberate input-design change.
Runtime validation should include press, release, leaving/reentering the button,
and other UI mouse capture; the static result is scoped to the route above.

## Status icons and auxiliary gauges

EXE `0x4f4260` obtains STATUS_EFFECT from dialog 26, reads **GetOffset**, width
and height, and builds status rectangles without adding the HUD's screen origin.
With this XML the anchor is (12,102), dimensions 15x15. Scale divides width by
the constant 20.0 at `0x785540`, so the scale is 0.75. Repeated icons in the
inspected mode-2/3 paths advance horizontally by width+1 (16); rows advance by
height (15). Caller `0x506f50` supplies a shared row counter, initially zero,
and invokes modes 4, 3, 2 in that order. Nonempty passes advance that counter.
These numbers identify call modes; their gameplay category names are not asserted.

The status drawing helper (`0x4f3640`) uses the supplied screen rectangle for
both drawing and tooltip hit-testing. Its scaled sprite adapter (`0x4ffae0`)
constructs a transform from the supplied coordinates/scale, calls drawSprite,
then resets the transform. It does not add the HUD origin either. This establishes
a screen-coordinate contract for this path, rather than ordinary child anchoring.

SUMMON_GAUGE and PAT_GAUGE are real child controls outside the panel's 210x100
bounds. The external routine updates their visibility, values, text and tooltip
rectangles; tooltip placement reads their actual control positions. Their XML
offsets are (220,72) and (220,84), both 100x10. Do not clip them to panel bounds.

Summon visibility requires positive current and maximum values. Text is current /
maximum and the value is normalized to the gauge's unit size. Maximum helper
`0x4d7c50` starts with 50 and adds stat contributions; it is not a fixed capacity.
Use our existing summon capacity getters, not donor avatar byte offsets.

PAT has several vehicle-state predicates before it is shown. It reads an item
life value through donor item index 136, multiplies by 10 and normalizes against
10000.0 (`0x788818`); thus life 1000 represents 100%. Its interpretation as vehicle
fuel is supported by the analogous local endurance code. Some donor predicates,
including a zero check at avatar offset `0x584`, remain semantically unnamed.
Use our vehicle/fuel model and validate visibility in the prototype rather than
copying these offsets or silently assuming every donor gate is understood.

If the prototype permits HUD movement, unify status draw and tooltip coordinates
with a shared HUD anchor. That would intentionally improve the donor's inspected
fixed-coordinate behavior; preserve it explicitly if exact donor behavior is wanted.

## Reproduce this pass

Run from the repository root (Python with pefile and capstone installed):

```powershell
python scripts/trace-667-ui.py --entry 444300:Font_registration --entry 495760:Font_face --entry 500170:Font_rect --entry 5001d0:Font_point --output build/667-ui-audit/final-fonts
python scripts/trace-667-ui.py --binary TGameCtrl_r.dll --entry 66031880:MakeCaption --entry 66028690:Caption_SetAlign --entry 66048db0:Image_SetAlign --entry 660286f0:Caption_Draw --output build/667-ui-audit/final-alignment
python scripts/trace-667-ui.py --binary TGameCtrl_r.dll --entry 660402d0:Dialog_Process --entry 66040760:Dialog_Update --entry 660284e0:Caption_Process --entry 660227a0:Button_Process --entry 6604e130:Pane_Process --entry 66008210:Container_Process --output build/667-ui-audit/final-input
python scripts/trace-667-ui.py --entry 506f50:Status_pass_caller --entry 4f4260:Status_and_aux --entry 4f3640:Status_icon_draw --entry 4ffae0:Sprite_scaled_draw --entry 4d7c50:Summon_max --output build/667-ui-audit/final-status
```

The tracer now includes the verified button-message and font-face switch tables,
in addition to the previous avatar-dialog switch. Hash guards reject other builds.
No unresolved jumps remain in these selected traces; indirect calls still require
manual interpretation, and this is not proof of complete program coverage.

## Readiness decision

Start a bounded avatar HUD prototype using the resolved art, explicit font mapping,
text-bearing images, donor gauge geometry/animation, and our existing gameplay data.
Validate font metrics, clicks/capture, animated bars, status tooltips and conditional
vehicle/summon visibility in a running client. Another broad static pass is not
needed before that prototype. Inventory slots, drag/drop, other dialogs and global
UI routing remain separate work toward the larger UI adaptation.
