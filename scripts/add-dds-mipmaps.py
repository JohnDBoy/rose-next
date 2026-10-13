#!/usr/bin/env python3
"""Give shipped DDS textures a real mip chain, so the client stops building one at runtime.

WHY
---
Character-spawn hitches were fixed first (see the motion-parser change in
zz_motion::load); what remained were 20-140 ms frames whose entire cost was
`shadow` -> immediate flush -> D3DXCreateTextureFromFileInMemoryEx. Splitting
that call showed the file read is ~0.1 ms per texture and the *create* is
everything else, at anywhere between 0.20 ms and 11.13 ms for a single
texture -- a 55x spread, so not a fixed overhead.

zz_renderer_d3d.cpp carries a note from the original team explaining it:

    512x512 texture
    DXT1 - miplevel1 = 0.729ms, 131KB
    DXT1 - miplevel2 = 57ms, 131KB

Same file, same size. The cost is D3DX *generating* a mip chain rather than
copying the file's, which for a DXT source means decompress, box-filter and
recompress for every level. No D3DXCreateTextureFromFileInMemoryEx flag avoids
the recompress, so this cannot be tuned away in the renderer.

data/SCRIPTS/INIT.LUA asks for 3 mip levels via setMipmapLevel(3), and that cap
is load-bearing -- object lightmaps are a gutterless atlas and a deeper chain
would bleed between neighbouring cells (see src/engine/CLAUDE.md). Taking 3 levels
from a file that ships its own chain is a cheap copy. Building 3 levels for a
file that ships none is the expensive path, and it is pure waste: the same work,
on every client, on every load, forever.

An in-game capture settled it beyond correlation. Every slow create logged by
"r_d3d: slow texture create" -- 196 of 196, no exceptions -- had src_mips=1,
costing 1300 ms in one short session across 163 distinct files.

WHAT IT DOES
------------
Rewrites every DDS under data/ that has no mip chain, adding a full one and
keeping the pixel format, the dimensions and the legacy DX9 header. Files that
already have a chain are skipped, so re-running is a no-op and safe.

Object lightmaps are excluded by default (see is_excluded). `--lightmaps` opts
them in, capped at LIGHTMAP_MIPS levels; `--selftest` measures whether the filter
can bleed across an atlas cell boundary before any data is touched.

RUNS ON RECORD (data/ is gitignored, so this list is the only committed history)
-------------------------------------------------------------------------------
- The original pass: 419 non-lightmap textures across data/.
- 2026-09-07, `--subdir 3DDATA/MAPS/KARKIA --lightmaps`: 282 Karkia lightmaps,
  42.7 -> 56.1 MB (+13.3 MB, +31%). Karkia's lightmaps are the only ones in the
  game that reach 2048 px, at 100.6 ms each to build at load; they were 8,711 ms
  of the 8,747 ms of slow texture creates Karkia logged. Its *other* textures were
  already fine from the original pass -- only 33 ms remained. Oro's 354 lightmaps
  were left alone on purpose, to keep the first lightmap run easy to clean up;
  they are 32-512 px and cost ~1.0 s in total.
  Undo exactly this run with
  `--subdir 3DDATA/MAPS/KARKIA --restore-excluded`.
- 2026-09-08, full pass: **31 files**, all that remained in data/ without a chain.
  29 are NPC textures that arrived *after* the original pass (the Karkia and Oro
  imports: karkia, dark_drake, stony, orobaba, oro_seto, ronwea_black, dark_ent,
  LICH01/02, MUMMY_FEMALE02, zorg_egg, KUPER) plus one avatar cap and one
  particle texture. Every entry in a fresh in-game log with `src_mips=1` is in
  this set. **What is left in that log is not fixable this way**: the 2048 px
  Karkia lightmaps already carry `src_mips=3 req_mips=3` and are simply large,
  and `LUNAR/Sky02/DAY01.DDS` + `NIGHT01.DDS` are 1024x1024 **uncompressed** with a full
  11-level chain -- 5.5 MB each, so their cost is raw size, not mip generation.
  Compressing a smooth sky gradient to DXT is exactly where banding shows, and
  they load once per zone, so they were left alone deliberately.

- 2026-09-08, `--subdir 3DDATA/AVATAR/{CAP,BODY,ARMS,FOOT}`: **106 files**, every
  texture the four armour imports of that day brought in (Egyptian lv240, Steam
  lv220, Refined Steam lv225, Unit Core lv230). 3.85 -> 4.59 MB (+0.74 MB, +19%).
  A fresh in-game log had 14 distinct `src_mips=1` armour textures at ~3 ms each;
  the other colours are the same files and would have logged the same on first
  wear. Scoped per folder rather than run whole because the ask was to touch only
  the armour -- though a check first proved the two sets were identical: every DDS
  under `AVATAR/{ARMS,BODY,CAP,FOOT}` without a chain came from those imports, and
  nothing else in `data/` was left un-mipped.

  Verified independently of this script's own check, by decoding pixels with
  Pillow and comparing against the pre-conversion backups: worst mip-0 deviation
  **1.69/255** (DXT1 re-encode noise, unavoidable and invisible) and worst
  generated-mip deviation **0.00/255** against a BOX resize computed outside
  texconv, over 120 files. For scale, the WIC darkening `-nowic` exists to prevent
  measured 36% and 71%, i.e. ~92 and ~181 out of 255. The black-band failure mode
  is three orders of magnitude away, measured rather than argued.

Uses thirdparty/directxtex-2020.9.30/texconv.exe, which was already vendored in
this repo and used by nothing at all.

TRAPS
-----
- **-dx9 is mandatory.** DirectXTex defaults to writing a "DX10" extended DDS
  header for some formats, and the client's D3DX9 loader cannot read those. A
  converted file would simply fail to load, and the engine's degrade-not-die
  path would draw the object untextured rather than tell you why. --verify
  rejects a DX10 header explicitly for that reason.
- **Backups go outside data/.** src/pipeline/src/pack.rs walks the data tree
  filtering only *hidden* entries -- there is no extension filter -- so a .bak
  left beside a texture gets baked into the .vfs. They go to
  build/dds-mipmap-backup/ instead.
- **-nowic is mandatory, and this one shipped a visible bug before it was found.**
  texconv filters through the Windows Imaging Component by default, and WIC
  darkens RGB badly when downsampling these textures -- measured at 36% on a
  terrain tile and 71% on an NPC body, with the alpha channel untouched. Only the
  lower mips are affected, so on screen it is a black wash that appears at
  distance and clears as you walk in. -if TRIANGLE also happens to avoid it, but
  only because WIC has no triangle filter and silently falls back to the same
  code path; -nowic is the flag that actually says what is meant. -if BOX on top
  matches what D3DX generated at runtime before any of this, keeping the visual
  result as close to the old behaviour as possible.
- **DirectXTex's own mip generator is power-of-two only** and returns
  E_FAIL [mipmaps] otherwise, so NPOT textures are skipped. No loss: they are
  minimaps, UI resources and effect strips, and the engine forces miplevels=1 for
  image textures regardless (zz_renderer_d3d download_texture, get_for_image()).
- **--verify samples decoded mip brightness, not just its presence.** The first
  version of this script checked dimensions, format and mip count, passed
  cleanly, and shipped chains that were 36-71% too dark. "The mips exist" and
  "the mips are correct" are different claims, and a verifier that cannot fail
  the actual defect is decoration. Needs Pillow; it says so when it cannot check.
- **Re-encoding a DXT file is lossy.** The top level is decompressed and
  recompressed, so the result is not bit-identical to the original. BC1/2/3
  endpoint selection is near-idempotent in practice, but this is why --restore
  exists.
- **The lightmap exclusion rested on a filter claim, and the claim is testable.**
  It named texconv's *default FANT filter, whose support reaches past one texel*
  -- but this script has passed `-if BOX` since the WIC fix. `--selftest` measures
  it on the worst geometry we ship (2048 px atlas, 8x8 grid of 256 px cells):
  BOX 0/255, FANT 0/255, TRIANGLE 36/255. A strict 2x2 box cannot cross a cell
  boundary while the cell stays even (256 -> 128 -> 64). Note also that the
  symptom which prompted the exclusion -- a dark wash at distance that clears as
  you walk in -- is the same symptom the -nowic trap above describes, and -nowic
  is what fixed that one. Lightmaps stay off by default anyway; the cap at
  LIGHTMAP_MIPS is what makes opting in safe rather than merely untested, since
  it leaves no level deeper than the engine loads for display quality 3-4 to
  reach.
- **A full chain is roughly a third larger.** The no-mip files total ~194 MB, so
  expect ~65 MB of growth. A .vfs has a hard 4 GB offset limit (the packer rolls
  over to rose_2.vfs at 4.2 GB) whose failure mode is silent and extremely
  confusing (see scripts/CLAUDE.md, "The .vfs Offset Limit"), so re-check the
  archive size after the next bake.
- Since data/ is gitignored, this docstring is the only committed record of the
  change. Put new reasoning here, not just in a commit message.
"""

import argparse
import collections
import os
import pathlib
import struct
import subprocess
import tempfile
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
TEXCONV = REPO / "thirdparty" / "directxtex-2020.9.30" / "texconv.exe"
BACKUP = REPO / "build" / "dds-mipmap-backup"

# INIT.LUA's setMipmapLevel(3) is what the engine loads, so this is every level a
# lightmap can ever need. Writing more would only create levels small enough to
# bleed across the gutterless atlas, reachable at display quality 3-4.
LIGHTMAP_MIPS = 3

DDSD_MIPMAPCOUNT = 0x20000
DDPF_FOURCC = 0x4
DDPF_ALPHAPIXELS = 0x1
DDSCAPS2_CUBEMAP = 0x200
DDSCAPS2_VOLUME = 0x200000


class Header(object):
    __slots__ = ("width", "height", "mips", "fourcc", "bits", "amask",
                 "pf_flags", "caps2")


def read_header(path):
    """Parse the parts of a DDS header we care about, or None if it is not a DDS
    (``rosefmt.dds.header``)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from rosefmt import dds
    d = dds.header(path)
    if d is None:
        return None
    h = Header()
    h.height, h.width, h.mips = d.height, d.width, d.mips
    h.pf_flags, h.fourcc, h.bits, h.amask, h.caps2 = d.pf_flags, d.fourcc, d.bit_count, d.a_mask, d.caps2
    return h


def target_format(h):
    """DXGI format for texconv -f that preserves what the file already is.

    Returns None for anything we would rather leave alone than guess at.
    """
    if h.pf_flags & DDPF_FOURCC:
        return {
            b"DXT1": "BC1_UNORM",
            b"DXT3": "BC2_UNORM",
            b"DXT5": "BC3_UNORM",
        }.get(h.fourcc)

    has_alpha = bool(h.pf_flags & DDPF_ALPHAPIXELS) and h.amask != 0
    if h.bits == 32:
        return "B8G8R8A8_UNORM" if has_alpha else "B8G8R8X8_UNORM"
    if h.bits == 24:
        # No 24bpp DXGI format exists, so promoting to 32bpp is the only option
        # and costs a third more bytes. Only a handful of files are affected.
        return "B8G8R8X8_UNORM"
    if h.bits == 16:
        if h.amask in (0xF000, 0x000F):
            return "B4G4R4A4_UNORM"
        if has_alpha:
            return "B5G5R5A1_UNORM"
        return "B5G6R5_UNORM"
    return None


def is_pow2(v):
    return v > 0 and (v & (v - 1)) == 0


def is_excluded(path, allow_lightmaps=False):
    """Textures that must never be given a mip chain, with the reason.

    Object lightmaps are a **gutterless atlas**: each map-object part owns one
    cell of a shared texture and SetLightMap addresses it with a UV transform, so
    there is no padding between cells and a filter that knows nothing about the
    grid blends a part's lighting into its neighbours'. src/engine/CLAUDE.md spells
    this out and says a full chain is unsafe for them.

    That was the original reasoning, and it named texconv's *default FANT filter,
    whose support reaches past one texel*. This script has passed `-if BOX` since
    the WIC fix, and --selftest measures the actual claim on the worst geometry we
    ship (a 2048 px atlas of 256 px cells): BOX and FANT both bleed **0/255** at
    the 3 levels the engine loads, while TRIANGLE bleeds 36/255. A strict 2x2 box
    cannot cross a cell boundary, because every block it averages lies wholly
    inside one cell as long as the cell stays even -- 256 -> 128 -> 64 here.

    Worth knowing when weighing this: the symptom that prompted the exclusion (a
    dark wash at distance that clears as you walk in) is the same symptom the
    -nowic trap above describes, and -nowic is what fixed that one. The exclusion
    may have been treating a bug that a different flag had already solved.

    So lightmaps are still excluded by default -- the conservative choice, and it
    keeps --restore-excluded working as a one-command undo for exactly this set --
    but --lightmaps opts them in, capped at LIGHTMAP_MIPS levels so nothing deeper
    than the engine loads even exists to be reached by a higher quality setting.

    The premise that made the blanket exclusion cheap was "these are 32-512 px
    textures and contribute almost nothing to load cost". That held for Junon and
    Oro. It does not hold for Karkia, whose lightmaps run to 2048 px -- 16x the
    area -- at 100.6 ms each to build at load, and which account for 8,711 ms of
    Karkia's 8,747 ms of logged slow texture creates.
    """
    u = str(path).upper().replace("/", chr(92))
    if "LIGHTMAP" in u and not allow_lightmaps:
        return "object lightmap atlas (gutterless, must not be mipped)"
    if chr(92) + "CONTROL" + chr(92) + "RES" + chr(92) in u:
        # UI resources, drawn at 1:1, and the engine forces miplevels=1 for image
        # textures anyway (download_texture -> tex->get_for_image()), so a chain
        # here is never sampled -- it is only file size. Most of this folder is
        # already skipped as non-power-of-two for an unrelated reason; the item and
        # skill icon atlases are 512x512 and slip through that branch.
        #
        # They are also the same gutterless-atlas shape as a lightmap: a 13x13 grid
        # of 40x40 cells with no padding. At the 3 levels the engine loads a cell
        # stays 10 px so nothing would actually bleed, but there is no upside to
        # weigh against it -- and a mip chain here has broken tooling before. When
        # icon51.dds came back from an unrelated pass with a 10-level chain it
        # tripped add-item-icon.py's total-file-length assert and blocked *every*
        # new icon until that script was taught to read only the top mip.
        #
        # icon51/52 still carry that chain and are left alone; this rule stops new
        # sheets acquiring one, it does not undo the old ones.
        return "UI resource (drawn 1:1, engine forces miplevels=1)"
    return None


def is_lightmap(path):
    return "LIGHTMAP" in str(path).upper()


def collect(root, allow_lightmaps=False):
    """Every DDS under root with no mip chain, plus a tally of what was skipped."""
    todo = []
    skipped = collections.Counter()
    for p in sorted(root.rglob("*")):
        if p.suffix.upper() != ".DDS" or not p.is_file():
            continue
        h = read_header(p)
        if h is None:
            skipped["not a DDS"] += 1
            continue
        if h.mips > 1:
            skipped["already has mips"] += 1
            continue
        why = is_excluded(p, allow_lightmaps)
        if why:
            skipped[why] += 1
            continue
        if h.caps2 & (DDSCAPS2_CUBEMAP | DDSCAPS2_VOLUME):
            skipped["cubemap/volume"] += 1
            continue
        if h.width < 2 or h.height < 2:
            skipped["too small to mip"] += 1
            continue
        if not (is_pow2(h.width) and is_pow2(h.height)):
            # DirectXTex's own mip generator (which -nowic selects, and which we
            # need because WIC darkens the result) only handles power-of-two
            # sizes; it returns E_FAIL [mipmaps] otherwise. No loss: every NPOT
            # texture here is a minimap, a UI resource or an effect strip, and the
            # engine forces miplevels=1 for image textures anyway
            # (zz_renderer_d3d download_texture, tex->get_for_image()). They are
            # drawn at 1:1 and loaded once.
            skipped["non-power-of-two (UI/minimap, never mipped)"] += 1
            continue
        fmt = target_format(h)
        if fmt is None:
            skipped["unrecognised pixel format"] += 1
            continue
        todo.append((p, h, fmt))
    return todo, skipped


def convert(todo, dry_run):
    """Run texconv, batched by (output directory, format, levels) to avoid 1200 spawns."""
    groups = collections.defaultdict(list)
    for p, _h, fmt in todo:
        # Lightmaps get exactly the levels the engine loads and no more. A full
        # chain would put levels 4+ on disk where nothing normally reads them --
        # until setDisplayQualityLevel 3 or 4 asks for the file's own chain
        # (mipmap_level = -1), at which point the cells are small enough to bleed.
        # Capping is what makes opting them in safe rather than merely untested.
        levels = str(LIGHTMAP_MIPS) if is_lightmap(p) else "0"
        groups[(p.parent, fmt, levels)].append(p)

    converted = 0
    failed = []
    for (out_dir, fmt, levels), paths in sorted(groups.items()):
        rel = out_dir.relative_to(DATA)
        if dry_run:
            print("  would convert %3d file(s) -> %-16s %-7s %s"
                  % (len(paths), fmt, "%s lvl" % (levels if levels != "0" else "full"),
                     rel))
            converted += len(paths)
            continue

        for p in paths:
            b = BACKUP / p.relative_to(DATA)
            b.parent.mkdir(parents=True, exist_ok=True)
            if not b.exists():
                b.write_bytes(p.read_bytes())

        # -nowic and -if BOX are both load-bearing:
        #
        #   -nowic  texconv filters through the Windows Imaging Component by
        #           default, and WIC darkens RGB badly when it downsamples these
        #           textures -- measured at 36% on a terrain tile and 71% on an
        #           NPC body, with the alpha channel untouched. On screen that is
        #           a black wash that appears at distance and clears as you walk
        #           in, because only the lower mips are affected. Forcing
        #           DirectXTex's own filters reproduces mip0's brightness exactly.
        #           (-if TRIANGLE also works, but only because WIC has no triangle
        #           filter and it silently falls back to the same code path.)
        #   -if BOX a strict 2x2 box is what D3DX generated at runtime before any
        #           of this, so it keeps the visual result as close to the old
        #           behaviour as possible. This is a load-time fix, not a
        #           re-authoring.
        cmd = [str(TEXCONV), "-nologo", "-y", "-dx9", "-m", levels, "-nowic",
               "-if", "BOX", "-f", fmt, "-o", str(out_dir)] + [str(p) for p in paths]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            failed.append((rel, fmt, (proc.stdout or proc.stderr).strip()[:200]))
            continue
        converted += len(paths)
        print("  %3d file(s) -> %-16s %s" % (len(paths), fmt, rel))
    return converted, failed


def mip_mean_rgb(path, level, blk):
    """Mean RGB of one mip level, by rebuilding it as a standalone single-level DDS.

    Needs Pillow. Returns None if it is unavailable or the level cannot be read.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    import io as _io
    try:
        d = open(path, "rb").read()
    except OSError:
        return None
    if len(d) < 128:
        return None
    head = bytearray(d[:128])
    flags = struct.unpack_from("<I", head, 8)[0]
    h, w = struct.unpack_from("<II", d, 12)
    off = 128
    for lv in range(level + 1):
        lw, lh = max(1, w >> lv), max(1, h >> lv)
        sz = max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4) * blk
        if off + sz > len(d):
            return None
        if lv == level:
            hh = bytearray(head)
            struct.pack_into("<II", hh, 12, lh, lw)
            struct.pack_into("<I", hh, 28, 1)
            struct.pack_into("<I", hh, 8, flags & ~DDSD_MIPMAPCOUNT)
            struct.pack_into("<I", hh, 20, sz)
            try:
                im = Image.open(_io.BytesIO(bytes(hh) + d[off:off + sz])).convert("RGBA")
            except Exception:
                return None
            px = im.load()
            total = 0
            for y in range(lh):
                for x in range(lw):
                    r, g, b, _a = px[x, y]
                    total += r + g + b
            return total / (lw * lh * 3.0)
        off += sz
    return None


def verify_brightness(touched, sample=40):
    """Compare mip0 and mip1 mean RGB on a sample of converted files.

    This exists because the first version of this script checked only that a mip
    chain was *present* -- right dimensions, right format, DX9 header -- and
    shipped chains whose RGB was 36-71% too dark, because texconv filters through
    WIC by default. "The mips exist" and "the mips are correct" are different
    claims and only the second one matters. A verifier that cannot fail the actual
    defect is decoration.
    """
    bad = []
    checked = 0
    step = max(1, len(touched) // sample)
    for p, h, _fmt in touched[::step]:
        if not (h.pf_flags & DDPF_FOURCC):
            continue  # only the block formats are laid out predictably enough
        blk = 8 if h.fourcc == b"DXT1" else 16
        m0 = mip_mean_rgb(p, 0, blk)
        m1 = mip_mean_rgb(p, 1, blk)
        if m0 is None or m1 is None:
            continue
        checked += 1
        if m0 > 1.0 and (1.0 - m1 / m0) > 0.15:
            bad.append((p, "mip1 is %.0f%% darker than mip0 (%.0f vs %.0f)"
                        % (100.0 * (1.0 - m1 / m0), m1, m0)))
    return bad, checked


def verify_converted(touched):
    """Re-read every touched file: mips must exist, geometry must be unchanged."""
    bad = []
    for p, h, _fmt in touched:
        h2 = read_header(p)
        if h2 is None:
            bad.append((p, "no longer a readable DDS"))
        elif h2.mips <= 1:
            bad.append((p, "still has no mip chain"))
        elif (h2.width, h2.height) != (h.width, h.height):
            bad.append((p, "dimensions changed %dx%d -> %dx%d"
                        % (h.width, h.height, h2.width, h2.height)))
        elif (h2.pf_flags & DDPF_FOURCC) and h2.fourcc == b"DX10":
            bad.append((p, "written with a DX10 header (client cannot read it)"))
        elif is_lightmap(p) and h2.mips > LIGHTMAP_MIPS:
            # The cap is the safety property, so assert it rather than trust the
            # flag: a lightmap with a deeper chain has levels whose cells are
            # small enough to bleed, reachable at display quality 3-4.
            bad.append((p, "lightmap has %d mip levels, cap is %d"
                        % (h2.mips, LIGHTMAP_MIPS)))
    return bad


def selftest():
    """Measure the claim the lightmap exclusion rests on, before touching data.

    Builds a synthetic atlas with the geometry of the worst lightmap we ship
    (2048 px, an 8x8 grid of 256 px cells, each a flat contrasting colour) and
    runs it through the real texconv invocation. If the filter stays inside cells,
    every texel of every generated level is still exactly its own cell's colour;
    anything else is bleeding, measured rather than argued.
    """
    try:
        from PIL import Image
    except ImportError:
        print("selftest needs Pillow (pip install Pillow)")
        return 1

    size, cell = 2048, 256
    grid = size // cell
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ddsmip-selftest"))
    src = tmp / "atlas.png"
    img = Image.new("RGB", (size, size))
    px = img.load()
    colours = {}
    for cy in range(grid):
        for cx in range(grid):
            c = (((cx * 37) % 8) * 31 + 8, ((cy * 53) % 8) * 31 + 8,
                 (((cx + cy) * 71) % 8) * 31 + 8)
            colours[(cx, cy)] = c
            for y in range(cy * cell, (cy + 1) * cell):
                for x in range(cx * cell, (cx + 1) * cell):
                    px[x, y] = c
    img.save(src)

    rc = 0
    for filt in ("BOX", "FANT", "TRIANGLE"):
        out = tmp / filt
        out.mkdir(exist_ok=True)
        # uncompressed on purpose: DXT endpoint error must not be mistaken for
        # filter bleed
        proc = subprocess.run(
            [str(TEXCONV), "-nologo", "-y", "-dx9", "-m", str(LIGHTMAP_MIPS),
             "-nowic", "-if", filt, "-f", "R8G8B8A8_UNORM", "-o", str(out), str(src)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            print("  %-9s texconv failed: %s"
                  % (filt, ((proc.stdout or "") + (proc.stderr or "")).strip()[:120]))
            rc = 1
            continue
        d = (out / "atlas.dds").read_bytes()
        hsize, = struct.unpack_from("<I", d, 4)
        height, width = struct.unpack_from("<II", d, 12)
        mips, = struct.unpack_from("<I", d, 28)
        off, worst = 4 + hsize, 0
        for lvl in range(mips):
            w, h, c = width >> lvl, height >> lvl, cell >> lvl
            plane = d[off:off + w * h * 4]
            off += w * h * 4
            for cy in range(grid):
                for cx in range(grid):
                    want = colours[(cx, cy)]
                    for dy in (0, c // 2, c - 1):
                        for dx in (0, 1, c - 2, c - 1):
                            i = ((cy * c + dy) * w + cx * c + dx) * 4
                            worst = max(worst, max(abs(a - b) for a, b in
                                                   zip(plane[i:i + 3], want)))
        verdict = "clean" if worst == 0 else "BLEEDS"
        print("  %-9s %d levels  worst deviation on a cell edge %3d/255  %s"
              % (filt, mips, worst, verdict))
        if filt == "BOX" and worst != 0:
            rc = 1
    print("\n%s" % ("BOX is a strict 2x2 and cannot cross a cell boundary -- "
                    "lightmaps are safe to mip at this depth" if rc == 0 else
                    "FAIL: BOX bled; do not use --lightmaps"))
    return rc


def restore(only_excluded=False, subdir=None):
    """Put originals back. only_excluded limits it to files the current rules say
    should never have been converted, which is how a bad exclusion is corrected
    without undoing the whole pass. subdir narrows it further, so a run that was
    deliberately scoped small can be undone equally small -- the backup tree keeps
    every original this script has ever replaced, including sets that were already
    rolled back once, and rewriting those is a no-op that still muddies a diff."""
    if not BACKUP.is_dir():
        print("no backups at %s" % BACKUP)
        return 1
    root = (DATA / subdir).resolve() if subdir else None
    n = 0
    for b in BACKUP.rglob("*"):
        if not b.is_file():
            continue
        target = DATA / b.relative_to(BACKUP)
        if only_excluded and not is_excluded(target):
            continue
        if root is not None and root not in target.resolve().parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b.read_bytes())
        n += 1
    scope = "excluded " if only_excluded else ""
    scope += "" if subdir is None else "under %s " % subdir
    print("restored %d %sfile(s) from %s" % (n, scope, BACKUP))
    if only_excluded and n:
        print("re-bake the VFS for this to reach the client")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and touch nothing")
    ap.add_argument("--verify", action="store_true",
                    help="only check that no DDS under data/ is missing a mip chain")
    ap.add_argument("--restore", action="store_true",
                    help="put every pre-conversion original back")
    ap.add_argument("--restore-excluded", action="store_true",
                    help="put back only the files the current exclusion rules say "
                         "should never have been converted; combine with --subdir "
                         "to undo one scoped run (e.g. --subdir 3DDATA/MAPS/KARKIA "
                         "--restore-excluded)")
    ap.add_argument("--subdir", default=None,
                    help="limit to a subtree of data/, e.g. 3DDATA/TERRAIN")
    ap.add_argument("--lightmaps", action="store_true",
                    help="also mip object lightmaps, capped at %d levels. Off by "
                         "default: they are a gutterless atlas (see is_excluded). "
                         "Run --selftest first, and prefer --subdir to keep the "
                         "blast radius small; --restore-excluded undoes exactly "
                         "this set." % LIGHTMAP_MIPS)
    ap.add_argument("--selftest", action="store_true",
                    help="measure whether the mip filter bleeds across atlas cell "
                         "boundaries, on the worst geometry we ship. Touches no data.")
    args = ap.parse_args()

    if args.selftest:
        if not TEXCONV.is_file():
            print("texconv.exe not found at %s" % TEXCONV)
            return 1
        print("filter bleed on a 2048 px atlas of 256 px cells, %d levels:"
              % LIGHTMAP_MIPS)
        return selftest()

    if args.restore or args.restore_excluded:
        return restore(only_excluded=args.restore_excluded, subdir=args.subdir)

    if not DATA.is_dir():
        print("no data/ directory at %s" % DATA)
        return 1
    if not args.verify and not TEXCONV.is_file():
        print("texconv.exe not found at %s" % TEXCONV)
        return 1

    root = DATA / args.subdir if args.subdir else DATA
    if not root.is_dir():
        print("no such subtree: %s" % root)
        return 1

    todo, skipped = collect(root, args.lightmaps)
    total_bytes = sum(p.stat().st_size for p, _h, _f in todo)

    print("scanned %s" % root)
    for k, v in skipped.most_common():
        print("  skipped %-28s %5d" % (k, v))
    print("  need a mip chain             %5d  (%.1f MB)"
          % (len(todo), total_bytes / 1048576.0))
    for fmt, n in collections.Counter(f for _p, _h, f in todo).most_common():
        print("      %-16s %5d" % (fmt, n))

    if args.verify:
        conv = []
        if BACKUP.is_dir():
            for b in sorted(BACKUP.rglob("*")):
                if not b.is_file() or b.suffix.upper() != ".DDS":
                    continue
                cur = DATA / b.relative_to(BACKUP)
                h = read_header(cur)
                if h is not None and h.mips > 1:
                    conv.append((cur, h, None))
        dark, checked = verify_brightness(conv)
        if dark:
            print("\nFAIL: generated mips are too dark on %d of %d sampled file(s)"
                  % (len(dark), checked))
            for pp, why in dark[:10]:
                print("   %-52s %s" % (pp.relative_to(DATA), why))
            return 1
        if checked:
            print("  brightness checked on            %5d sampled converted file(s)"
                  % checked)
        elif conv:
            print("  brightness NOT checked (install Pillow to enable it)")

        if todo:
            print("\nFAIL: %d file(s) still have no mip chain" % len(todo))
            for p, _h, _f in todo[:20]:
                print("   %s" % p.relative_to(DATA))
            return 1
        print("\nOK: every DDS carries a mip chain")
        return 0

    if not todo:
        print("\nnothing to do")
        return 0

    print()
    converted, failed = convert(todo, args.dry_run)

    if args.dry_run:
        print("\ndry run: %d file(s) would be converted" % converted)
        print("originals would be backed up under %s" % BACKUP)
        return 0

    print("\nconverted %d file(s)" % converted)
    for rel, fmt, msg in failed:
        print("  FAILED %-16s %s: %s" % (fmt, rel, msg))

    bad = verify_converted(todo)
    if bad:
        print("\nVERIFY FAILED on %d file(s):" % len(bad))
        for p, why in bad[:20]:
            print("   %-58s %s" % (p.relative_to(DATA), why))
        print("\nrun with --restore to put the originals back")
        return 1

    dark, checked = verify_brightness(todo)
    if dark:
        print("\nVERIFY FAILED: generated mips are too dark on %d of %d sampled file(s):"
              % (len(dark), checked))
        for p, why in dark[:10]:
            print("   %-52s %s" % (p.relative_to(DATA), why))
        print("\nrun with --restore to put the originals back")
        return 1

    print("verified: all %d file(s) now carry a mip chain, "
          "with unchanged dimensions and a DX9 header" % len(todo))
    if checked:
        print("verified: mip brightness matches mip0 on %d sampled file(s)" % checked)
    else:
        print("NOTE: mip brightness was NOT sampled (no block-format files in this "
              "batch, or Pillow missing) -- run --verify to check the whole set")
    print("\nRe-bake the VFS (pack.ps1 verifies the archive and rolls over at 4.2 GB).")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
