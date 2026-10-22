"""Restore Eldeon's falling leaves (zone weather type 3).

A zone's weather is LIST_ZONE column 27 (`ZONE_WEATHER_TYPE`). On zone join the
client calls `SE_WeatherEffect(avatar, type)` in `SCRIPTS/GLOBALSCR.LUA`, which
maps the number to an .eft and attaches it to the avatar.

**Type 3, Eldeon leaves** (EJT01, EJ01, EJ02, EJ03). Every reference client maps
it to `_ed_leaf01.eft`; ours had the line replaced by a stub "intentionally
disabled due to client performance issues", written before this repo's history
(the file is dated April 2026), so what was measured then is unknown. Restored
2026-10-22 and validated in game: 800 small (20-50 cm) alpha-blended leaves
spread over 80 x 80 m, 15-25 m up -- 1.6x the Luna snow (type 1, 500 particles)
that ten zones already run. Alpha-blended, so not batched: one emitter in the
HUD's `PartBatch: fallback=`, about 8 draws. EJ01 with it on held vsync's 60 FPS
with ~7 ms of the frame spare.

**Type 5, Karkia -- left unmapped on purpose.** KCemetery, KSpireVil,
KBurnedForest and KTowerPlace carry type 5 because their LIST_ZONE rows came
verbatim from Jrose, where 5 means `rm_mist.eft` (weather numbering is
per-client: 667/668 use 5 for Luna clover, QQ for rain). Jrose's mist was
imported and tried in game on 2026-10-22 and rejected -- it looked bad on our
maps -- so the type stays without a Lua branch and Karkia has no weather. Do not
wire it up again without the user asking.

GLOBALSCR.LUA is CP949 with Korean comments, so it is patched as bytes (an
editor that re-encodes it destroys them). The disabled stub had CRLF lines in an
otherwise-LF file; the replacement is LF.

The client reads GLOBALSCR.LUA from the VFS: re-bake. Client only -- the server
never reads it.

Idempotent, --dry-run, verifies after writing.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rosefmt import eft, stb  # noqa: E402

LUA = os.path.join("SCRIPTS", "GLOBALSCR.LUA")
LEAF_EFT = os.path.join("3DDATA", "EFFECT", "_ED_LEAF01.EFT")

ZONE_WEATHER_COL = 27
ELDEON_ZONES = (61, 62, 63, 64)

LEAVES_STUB = (b"\t-- Weather type 3 (Eldeon leaves) is intentionally disabled due to\r\n"
               b"\t-- client performance issues on outdoor Eldeon zones.\r\n"
               b"\tif iWeatherType == 3 then\r\n"
               b"\t\t-- Intentionally no effect.\r\n"
               b"\tend\n")
LEAVES_LINE = b'GF_GetEffectUseFile( "3DDATA/Effect/_ed_leaf01.eft" )'
LEAVES_BLOCK = (b"\t-- Eldeon leaves (EJT01, EJ01-EJ03). Was disabled for performance; restored\n"
                b"\t-- 2026-10-22 after particle batching: 800 small particles, cheaper than it looked.\n"
                b"\tif iWeatherType == 3 then\n"
                b"\t\tiEffect = " + LEAVES_LINE + b"\n"
                b"\t\tGF_WeatherEffectOnObject( iObject, iEffect );\n"
                b"\tend\n")


def patch_lua(b):
    """Return (new bytes, changed)."""
    if LEAVES_LINE in b:
        return b, False
    if b.count(LEAVES_STUB) != 1:
        raise SystemExit("GLOBALSCR.LUA: neither the type-3 stub nor the leaves line found")
    return b.replace(LEAVES_STUB, LEAVES_BLOCK), True


def verify(data):
    problems = []
    b = open(os.path.join(data, LUA), "rb").read()
    if b.count(LEAVES_LINE) != 1:
        problems.append("GLOBALSCR.LUA: expected one leaves line")
    if b"Intentionally no effect" in b:
        problems.append("GLOBALSCR.LUA: the disabled stub is still there")
    if b"iWeatherType == 5" in b:
        problems.append("GLOBALSCR.LUA: type 5 is mapped (Karkia's weather was rejected)")
    e = eft.read(os.path.join(data, LEAF_EFT))
    if not e["particles"]:
        problems.append("_ED_LEAF01.EFT has no particle system")
    zones = stb.Stb(os.path.join(data, "3DDATA", "STB", "LIST_ZONE.STB"))
    for row in ELDEON_ZONES:
        got = zones.get(row, ZONE_WEATHER_COL)
        if str(got.decode() if isinstance(got, bytes) else got).strip() != "3":
            problems.append("LIST_ZONE row %d weather %r, expected 3" % (row, got))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="preview without writing")
    ap.add_argument("--verify", action="store_true", help="only check the result")
    ap.add_argument("--root", default=ROOT, help="repo root")
    args = ap.parse_args()
    data = os.path.join(args.root, "data")

    if not args.verify:
        lua_path = os.path.join(data, LUA)
        after, changed = patch_lua(open(lua_path, "rb").read())
        print("lua     type 3 -> _ed_leaf01.eft" if changed else "ok      GLOBALSCR.LUA (already patched)")
        if args.dry_run:
            print("dry run: nothing written")
            return
        if changed:
            with open(lua_path, "wb") as fh:
                fh.write(after)

    problems = verify(data)
    for p in problems:
        print("FAIL    " + p)
    if problems:
        sys.exit(1)
    print("verified: Eldeon leaves on, Karkia unmapped")


if __name__ == "__main__":
    main()
