"""Swap our DXT5-compressed item icons for crisp copies found in other clients.

Usage (from the repo root):
    python scripts/upgrade-item-icons.py --survey             # match, write review sheets (build/ only)
    python scripts/upgrade-item-icons.py --apply [--dry-run]  # paste the reviewed matches
    python scripts/upgrade-item-icons.py --verify
    python scripts/upgrade-item-icons.py --restore

Why (2026-10-18): our item icon sheets ICON01-50.DDS came DXT5-compressed in the
original dump, like the skill sheets did (see upgrade-skill-icons.py). DXT5
keeps four colours per 4x4 block, so a 40 px icon is left with ~300-400 colours,
smeared lines and block noise. Most retail-lineage clients ship the same sheets
uncompressed: 668 as 32-bit, tsuki as 24/32-bit, 667/Jrose/RoseZA/139/ruff as
16-bit R5G6B5. Our extension sheets (icon51+) are already uncompressed.

Our items come from several clients, and the reference dumps number and lay out
their sheets differently (668's ICON22 holds our ICON33), so nothing is matched
by sheet or position. Every non-blank cell of ours is compared by *picture*
against every 40 px cell of every reference sheet:

  1. coarse: 4x4 block means (10x10 RGB), the part DXT5 keeps nearly intact,
     top candidates by L2 distance;
  2. fine: mean abs diff over the full cell, for those candidates;
  3. among candidates within FINE_TIE of the best, the highest bit depth wins.

A candidate is useless if it is itself a decoded DXT image (some dumps store
DXT-decoded sheets as 24/32-bit): nearly every aligned 4x4 block then has at
most four colours. Such candidates are skipped.

Verdicts, by the block-mean distance of the chosen candidate (RMS over the
10x10 block means, 0-255 scale). The full-pixel diff is mostly DXT noise (one
broad hump from 4 to 24 for true twins), so it only breaks ties; the block
distance separates: 5,762 pairs at 0-6, then a thin tail (2026-10-18 survey).
  match     block <= MATCH_BLOCK and fine <= MAX_FINE: same art
  doubtful  block <= DOUBT_BLOCK: probably the same art, check by eye
Whatever the averages, a pair whose worst 4x4 block differs by more than
WORST_BLOCK is not a twin: a label drawn on the icon ("+10" vs "+50", a scroll's
town name) changes a few blocks by ~110 and barely moves the average; DXT noise
on a true twin stays under ~60.
  none      nothing close enough: the cell stays as it is

Output, build/item-icon-quality/ (nothing is written under data/):
  summary.txt          per sheet: cells, blanks, matches, doubtfuls, nones, by source
  sheet-ICONnn.png     every non-blank cell: ours (left) | candidate (right), 2x,
                       framed green (match), orange (doubtful), grey (none)
  doubtful.png         all doubtful pairs, 3x, for a focused look
  plan.json            sprite index -> chosen source (dump, file, x, y), verdict

--apply reads plan.json -- the plan that was reviewed, not a fresh match -- and
pastes every "match" and "doubtful" twin (the user reviewed both, 2026-10-19:
"the icons correspond"; cells with no twin stay as they are) over our cell,
whole 40x40 cell, RGB only: our alpha channel is kept. Each touched sheet is
rewritten as 512x512 uncompressed 32-bit BGRA, the format of the extension
sheets icon51+ and of the skill sheets, with no mip chain (zz_renderer_d3d
forces miplevels = 1 for image textures, so a chain is never sampled; see
add-item-icon.py). No sprite index or TSI entry moves. Cost: ~1 MB per sheet
instead of ~340 KB, so ~+33 MB in the .vfs for all 50.

Undo: every sheet is copied to build/item-icons-crisp/ before its first write,
with a manifest of the pasted cells; --restore copies them back (whole file:
an icon added to one of ICON01-50 afterwards would be lost -- add-item-icon.py
only ever appends to the last sheet, icon51+). --verify re-reads every pasted
cell and compares it with its source, and checks each touched sheet is 32-bit.

Deploy: client-only data (the sheets are in the VFS). Re-bake; no server restart.
"""
import argparse, io, json, os, struct, sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from rosefmt import tsi, dds  # noqa: E402

RES = os.path.join("data", "3DDATA", "CONTROL", "RES")
OUT = os.path.join("build", "item-icon-quality")
BACKUP = os.path.join("build", "item-icons-crisp")
MANIFEST = os.path.join(BACKUP, "manifest.json")
SHEET = 512
TC = r"C:\Users\Thomas\Desktop\Testclients"
# (label, RES folder) -- best bit depth first; ties go to the earlier source
SOURCES = [
    ("668", os.path.join(TC, "668", "Extracted", "3DDATA", "CONTROL", "RES")),
    ("tsuki", os.path.join(TC, "tsuki", "3Ddata", "CONTROL", "RES")),
    ("667", os.path.join(TC, "667", "extracted data", "3DDATA", "CONTROL", "RES")),
    ("Jrose", os.path.join(TC, "Jrose", "3Ddata", "Control", "RES")),
    ("RoseZA", os.path.join(TC, "RoseZA test client", "data", "3DDATA", "CONTROL", "RES")),
    ("139", os.path.join(TC, "139", "extracted data", "3DDATA", "CONTROL", "RES")),
    ("ruff", os.path.join(TC, "ruff", "extracted data", "3DDATA", "CONTROL", "RES")),
]
CELL, BLOCK = 40, 4
TOPK = 6
FINE_TIE = 2.0
MATCH_BLOCK, DOUBT_BLOCK = 6.0, 12.0
MAX_FINE = 30.0
WORST_BLOCK = 75.0          # true twins <= ~60; a changed label ~110
BLANK_SAT = 10.0


# ---------------------------------------------------------------- reading
def read_sheet(path):
    """RGB uint8 array + bit depth label; uncompressed DDS decoded by mask, DXT via PIL."""
    h = dds.parse_header(path)
    if h.compressed:
        return np.asarray(Image.open(path).convert("RGB")), h.fourcc.decode("latin-1")
    raw = open(path, "rb").read()
    off, bpp, w, ht = h.payload_offset, h.bit_count // 8, h.width, h.height
    pitch = w * bpp
    buf = np.frombuffer(raw, np.uint8, count=pitch * ht, offset=off).reshape(ht, w, bpp)
    px = np.zeros((ht, w), np.uint32)
    for i in range(bpp):
        px |= buf[:, :, i].astype(np.uint32) << (8 * i)
    out = np.zeros((ht, w, 3), np.uint8)
    for ch, mask in enumerate((h.r_mask, h.g_mask, h.b_mask)):
        if not mask:
            continue
        shift = (mask & -mask).bit_length() - 1
        top = mask >> shift
        out[:, :, ch] = ((px & mask) >> shift) * 255 // top
    return out, "%d-bit" % h.bit_count


def cells_of(sheet):
    """Every 40 px grid cell; cells past the edge padded with -1 (invalid)."""
    hgt, wid = sheet.shape[:2]
    for y in range(0, hgt, CELL):
        for x in range(0, wid, CELL):
            a = np.full((CELL, CELL, 3), -1, np.int16)
            part = sheet[y:y + CELL, x:x + CELL]
            a[:part.shape[0], :part.shape[1]] = part
            yield x, y, a


def blocks(a):
    """10x10x3 block means, invalid pixels ignored (blocks wholly invalid -> 0)."""
    v = (a[:, :, 0] >= 0)
    a = np.where(a >= 0, a, 0).astype(np.float32)
    s = a.reshape(10, BLOCK, 10, BLOCK, 3).sum(axis=(1, 3))
    n = v.reshape(10, BLOCK, 10, BLOCK).sum(axis=(1, 3))[:, :, None]
    return np.where(n > 0, s / np.maximum(n, 1), 0).reshape(-1)


def is_blank(a):
    inner = a[5:35, 5:35]
    valid = inner[inner[:, :, 0] >= 0]
    return len(valid) == 0 or (valid.max(axis=1) - valid.min(axis=1)).mean() < BLANK_SAT


def dxt_origin(a):
    """True if nearly every aligned 4x4 block holds at most 4 colours."""
    full = a[:CELL - CELL % BLOCK, :CELL - CELL % BLOCK]
    if (full < 0).any():
        full = full[:32, :32]
        if (full < 0).any():
            return False
    k = full.shape[0] // BLOCK
    small = 0
    for by in range(k):
        for bx in range(k):
            blk = full[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4].reshape(-1, 3)
            if len(np.unique(blk, axis=0)) <= 4:
                small += 1
    return small >= 0.9 * k * k


def worst_block(a, b):
    """Largest mean abs diff of any 4x4 block: a changed label ("+10" vs "+50", a
    scroll's town name) moves a few blocks a lot and the cell average hardly at all."""
    m = (a[:, :, 0] >= 0) & (b[:, :, 0] >= 0)
    d = np.where(m[:, :, None], np.abs(a.astype(np.int32) - b.astype(np.int32)), 0).sum(axis=2) / 3.0
    n = m.reshape(10, BLOCK, 10, BLOCK).sum(axis=(1, 3))
    s = d.reshape(10, BLOCK, 10, BLOCK).sum(axis=(1, 3))
    return float((s / np.maximum(n, 1))[n > 0].max()) if (n > 0).any() else 1e9


def fine(a, b):
    m = (a[:, :, 0] >= 0) & (b[:, :, 0] >= 0)
    return float(np.abs(a[m] - b[m]).mean()) if m.any() else 1e9


# ---------------------------------------------------------------- survey
def survey():
    names, sprites = tsi.sprites(os.path.join(RES, "ITEM1.TSI"))
    ours = {}
    for t, nm in enumerate(names):
        p = os.path.join(RES, os.path.basename(nm))
        if os.path.exists(p) and dds.parse_header(p).compressed:
            ours[t] = read_sheet(p)[0]
    print("our DXT sheets:", len(ours))

    ref_meta, ref_blocks, ref_cells = [], [], []
    for label, folder in SOURCES:
        if not os.path.isdir(folder):
            print("  (missing source %s)" % label)
            continue
        n0 = len(ref_meta)
        for f in sorted(os.listdir(folder)):
            if not (f.lower().startswith("icon") and f.lower().endswith(".dds")):
                continue
            try:
                sh, depth = read_sheet(os.path.join(folder, f))
            except Exception as e:
                print("  skip %s/%s: %s" % (label, f, e))
                continue
            if not depth.endswith("bit"):
                continue                      # compressed in that dump too
            for x, y, a in cells_of(sh):
                if is_blank(a):
                    continue
                ref_meta.append((label, f, x, y, depth))
                ref_blocks.append(blocks(a))
                ref_cells.append(a)
        print("  %-7s %6d cells" % (label, len(ref_meta) - n0))
    R = np.stack(ref_blocks).astype(np.float32)
    R2 = (R ** 2).sum(axis=1)

    plan, rows = {}, defaultdict(list)
    todo = []
    for idx, (t, x1, y1, x2, y2) in enumerate(sprites):
        if t not in ours:
            continue
        sh = ours[t]
        a = np.full((CELL, CELL, 3), -1, np.int16)
        part = sh[y1:y1 + CELL, x1:x1 + CELL]
        a[:part.shape[0], :part.shape[1]] = part
        todo.append((idx, t, x1, y1, a))
    print("our sprites on DXT sheets:", len(todo))

    dxt_cache = {}
    for start in range(0, len(todo), 512):
        chunk = todo[start:start + 512]
        Q = np.stack([blocks(c[4]) for c in chunk]).astype(np.float32)
        D = (Q ** 2).sum(axis=1)[:, None] + R2[None] - 2 * Q @ R.T
        top = np.argpartition(D, TOPK, axis=1)[:, :TOPK]
        for k, (idx, t, x1, y1, a) in enumerate(chunk):
            sheetname = os.path.basename(names[t]).upper()
            if is_blank(a):
                rows[sheetname].append((idx, "blank", a, None, None))
                continue
            cands = []
            for j in top[k]:
                if j not in dxt_cache:
                    dxt_cache[j] = dxt_origin(ref_cells[j])
                if dxt_cache[j]:
                    continue
                blk = float(np.sqrt(max(D[k, j], 0) / 300.0))
                cands.append((fine(a, ref_cells[j]), blk, int(j)))
            if not cands:
                rows[sheetname].append((idx, "none", a, None, None))
                continue
            best_fine = min(c[0] for c in cands)
            near = [c for c in cands if c[0] <= best_fine + FINE_TIE]
            order = {lbl: n for n, (lbl, _) in enumerate(SOURCES)}
            f_, b_, j = min(near, key=lambda c: (order[ref_meta[c[2]][0]], c[0]))
            wb = worst_block(a, ref_cells[j])
            if wb > WORST_BLOCK:
                verdict = "none"              # a different label on the same art
            elif b_ <= MATCH_BLOCK and f_ <= MAX_FINE:
                verdict = "match"
            elif b_ <= DOUBT_BLOCK and f_ <= MAX_FINE:
                verdict = "doubtful"
            else:
                verdict = "none"
            lbl, f, x, y, depth = ref_meta[j]
            if verdict != "none":
                plan[idx] = dict(sheet=sheetname, x=x1, y=y1, verdict=verdict, source=lbl, file=f,
                                 sx=x, sy=y, depth=depth, fine=round(f_, 1), block=round(b_, 1),
                                 worst=round(wb, 1))
            rows[sheetname].append((idx, verdict, a, ref_cells[j] if verdict != "none" else None,
                                    "%s %s b%.0f w%.0f" % (lbl, depth.replace("-bit", "b"), b_, wb) if verdict != "none" else None))
    write_outputs(rows, plan)


# ---------------------------------------------------------------- output
COL = {"match": (60, 200, 90), "doubtful": (240, 150, 40), "none": (110, 110, 110)}


def font(size):
    try:
        return ImageFont.truetype("segoeui.ttf", size)
    except Exception:
        return ImageFont.load_default()


def tile(a, s):
    return Image.fromarray(np.where(a >= 0, a, 0).astype(np.uint8), "RGB").resize((CELL * s, CELL * s), Image.NEAREST)


def pair_sheet(items, title, path, s=2, cols=10):
    f = font(11)
    cw, ch = 2 * CELL * s + 18, CELL * s + 18
    rowsn = (len(items) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw + 10, 34 + rowsn * ch), (26, 26, 30))
    d = ImageDraw.Draw(img)
    d.text((8, 8), title, font=font(14), fill=(240, 240, 240))
    for n, (idx, verdict, a, b, label) in enumerate(items):
        x, y = 8 + (n % cols) * cw, 34 + (n // cols) * ch
        d.rectangle((x - 2, y - 2, x + 2 * CELL * s + 4, y + CELL * s + 1), outline=COL[verdict], width=2)
        img.paste(tile(a, s), (x, y))
        if b is not None:
            img.paste(tile(b, s), (x + CELL * s + 3, y))
        d.text((x, y + CELL * s + 2), "#%d %s" % (idx, label or "no twin"), font=f, fill=(200, 200, 200))
    img.save(path)


def write_outputs(rows, plan):
    os.makedirs(OUT, exist_ok=True)
    total = Counter()
    lines = ["sheet        cells blank match doubt none   sources (match+doubtful)"]
    doubtful = []
    for sheetname in sorted(rows):
        items = rows[sheetname]
        c = Counter(v for _, v, *_ in items)
        total.update(c)
        src = Counter(plan[i]["source"] for i, v, *_ in items if v in ("match", "doubtful"))
        lines.append("%-12s %5d %5d %5d %5d %5d   %s" % (sheetname, len(items), c["blank"], c["match"],
                                                     c["doubtful"], c["none"],
                                                     ", ".join("%s %d" % kv for kv in src.most_common())))
        shown = [it for it in items if it[1] != "blank"]
        if shown:
            pair_sheet(shown, "%s: ours | candidate (green match, orange doubtful, grey no twin)" % sheetname,
                       os.path.join(OUT, "sheet-%s.png" % os.path.splitext(sheetname)[0]))
        doubtful += [it for it in items if it[1] == "doubtful"]
    lines.append("%-12s %5d %5d %5d %5d %5d" % ("TOTAL", sum(total.values()), total["blank"], total["match"],
                                                total["doubtful"], total["none"]))
    if doubtful:
        pair_sheet(doubtful, "Doubtful pairs (%d): ours | candidate" % len(doubtful),
                   os.path.join(OUT, "doubtful.png"), s=3, cols=8)
    with open(os.path.join(OUT, "summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(OUT, "plan.json"), "w") as f:
        json.dump(plan, f, indent=1)
    print("\n".join(lines))
    print("\nwritten to %s" % OUT)


# ---------------------------------------------------------------- apply / verify / restore
def find_in(folder, name):
    for f in os.listdir(folder):
        if f.lower() == name.lower():
            return os.path.join(folder, f)
    return None


def source_cell(rec, cache):
    """The 40x40 RGB cell the plan names, from its reference sheet."""
    folder = dict(SOURCES)[rec["source"]]
    key = (rec["source"], rec["file"].lower())
    if key not in cache:
        cache[key] = read_sheet(os.path.join(folder, rec["file"]))[0]
    sh = cache[key]
    return sh[rec["sy"]:rec["sy"] + CELL, rec["sx"]:rec["sx"] + CELL]


def load_manifest():
    if os.path.exists(MANIFEST):
        return json.load(open(MANIFEST))
    return {"backed_up": [], "pasted": {}}


def apply(dry):
    import shutil
    plan_path = os.path.join(OUT, "plan.json")
    if not os.path.exists(plan_path):
        sys.exit("no %s: run --survey and review the sheets first" % plan_path)
    plan = json.load(open(plan_path))
    m = load_manifest()
    by_sheet = defaultdict(list)
    for idx, rec in plan.items():
        if rec["verdict"] in ("match", "doubtful"):
            by_sheet[rec["sheet"]].append((int(idx), rec))
    cache = {}
    total = 0
    for sheetname in sorted(by_sheet):
        path = find_in(RES, sheetname)
        if path is None:
            print("  %s: not found, skipped" % sheetname)
            continue
        h = dds.parse_header(path)
        if h.compressed:
            img = Image.open(path).convert("RGBA")
        else:
            img = dds.read_bgra(path, size=(SHEET, SHEET))     # a re-run on a sheet already converted
        px = np.asarray(img).copy()
        for idx, rec in by_sheet[sheetname]:
            cell = source_cell(rec, cache)
            x, y = rec["x"], rec["y"]
            hh = min(CELL, SHEET - y, cell.shape[0])
            ww = min(CELL, SHEET - x, cell.shape[1])
            px[y:y + hh, x:x + ww, :3] = cell[:hh, :ww]
            m["pasted"][str(idx)] = rec
        total += len(by_sheet[sheetname])
        if not dry:
            os.makedirs(BACKUP, exist_ok=True)
            dst = os.path.join(BACKUP, os.path.basename(path))
            if not os.path.exists(dst):
                shutil.copy2(path, dst)
                m["backed_up"].append(os.path.basename(path))
            dds.write_bgra(path, Image.fromarray(px, "RGBA"))
        print("  %s: %d icons%s" % (sheetname, len(by_sheet[sheetname]), " (dry run)" if dry else ""))
    if not dry:
        with open(MANIFEST, "w") as f:
            json.dump(m, f, indent=1)
    print("%d icons on %d sheets%s" % (total, len(by_sheet), " -- DRY RUN, nothing written" if dry else ""))


def verify():
    m = load_manifest()
    if not m["pasted"]:
        print("nothing applied")
        return True
    cache, sheets, bad = {}, {}, 0
    for idx, rec in m["pasted"].items():
        name = rec["sheet"]
        if name not in sheets:
            path = find_in(RES, name)
            h = dds.parse_header(path)
            if h.compressed or h.bit_count != 32:
                print("  %s is not 32-bit uncompressed" % name)
                bad += 1
            sheets[name] = np.asarray(dds.read_bgra(path).convert("RGB")) if not h.compressed else None
        ours = sheets[name]
        if ours is None:
            continue
        cell = source_cell(rec, cache)
        x, y = rec["x"], rec["y"]
        hh, ww = min(CELL, SHEET - y, cell.shape[0]), min(CELL, SHEET - x, cell.shape[1])
        if not np.array_equal(ours[y:y + hh, x:x + ww], cell[:hh, :ww]):
            print("  icon %s differs from its source %s %s (%d,%d)" % (idx, rec["source"], rec["file"], rec["sx"], rec["sy"]))
            bad += 1
    print("verify: %d icons on %d sheets, %d problems" % (len(m["pasted"]), len(sheets), bad))
    return bad == 0


def restore():
    import shutil
    m = load_manifest()
    for n in m["backed_up"]:
        dst = find_in(RES, n) or os.path.join(RES, n)
        shutil.copy2(os.path.join(BACKUP, n), dst)
        print("  restored %s" % n)
    if os.path.exists(MANIFEST):
        os.remove(MANIFEST)
    print("restored %d sheets" % len(m["backed_up"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--survey", action="store_true", help="match and write the review sheets (writes only build/)")
    ap.add_argument("--apply", action="store_true", help="paste the reviewed plan.json matches into data/")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.restore:
        return restore()
    if args.verify:
        return sys.exit(0 if verify() else 1)
    if args.apply:
        return apply(args.dry_run)
    if not args.survey:
        ap.print_help()
        return
    survey()


if __name__ == "__main__":
    main()
