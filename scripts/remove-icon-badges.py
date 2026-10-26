"""Paint the corner letters out of three weapon tiers' icons (2026-10-26).

Three endgame lines came in with a letter stamped in the bottom-right corner of
their icon, a mark from the server they were taken from that means nothing here
(the user: "those aren't unique anymore"):

    U  the level-240 line (Aerie ... Quetzalcoatl, 1383-1419 step 3)    blue frame
    E  the level-220 line (Tsunemoto ... Hepri, 1426-1436)               red frame
    M  the red level-230 set (Kunihoroboshi ... Kekkando, 1456-1468)     gold frame

(remove-vermillion-icon-badge.py did Rose Brasil's "IM" the same day; that badge
was found by colour.) Each letter is stamped the same on every icon of its set, so
it is found where the set's icons agree and the weapons do not:

  * U -- a solid plate, rows 26-35 x cols 25-35 of the 40 px cell, **pixel-identical**
    on all 13. The 240 icons are drawn on the classic blue background, which 54
    badge-free icons elsewhere in the atlas share exactly; the background under the
    plate is, per pixel, the colour most of them agree on (9 to 53 of 54 agree on
    the exact value). That is the real background, not an estimate.
  * E, M -- their frames exist nowhere else in the atlas (E) or only under
    compression noise (M), so the background comes from 11 rows up, the median over
    the set (a weapon crossing that spot on one icon does not leak). The letter is
    every pixel in a box round it close to the set's median there -- the median *is*
    the letter, since it sits on every icon -- so a weapon pixel inside the box is
    kept. E is a cream-bordered plate with a translucent red tab above it; M a red
    glyph with a cream outline blended into the background, hence the looser match.

Weapon art the letter covered was never in the files to recover. Only the changed
pixels are written, in place (sheets are uncompressed BGRA -- refused otherwise;
icon51/52 carry a mip chain, and the cell's footprint in each smaller level is
re-averaged with the same 2x2 box add-dds-mipmaps.py built it with), and the manifest keeps each original and cleaned cell, so the result is
frozen on the first run, `--verify` is exact and `--restore` puts the originals back
(refusing a cell changed since). `--preview out.png` shows before/after. `data/` is
gitignored, so this file is the record. Re-bake the VFS.

    python scripts/remove-icon-badges.py --dry-run [--preview out.png]
    python scripts/remove-icon-badges.py
    python scripts/remove-icon-badges.py --verify
    python scripts/remove-icon-badges.py --restore
"""
import argparse
import base64
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from rosefmt import Stb, dds, tsi  # noqa: E402

DATA = os.path.join(ROOT, "data", "3DDATA")
STB = os.path.join(DATA, "STB", "LIST_WEAPON.STB")
RES = os.path.join(DATA, "CONTROL", "RES")
BACKUP_DIR = os.path.join(ROOT, "build", "remove-icon-badges")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")
COL_ICON, CELL = 9, 40

# set: rows (first and last names checked), box (y0, y1, x0, x1, ends exclusive), method,
#      match threshold (max channel difference from the set's median), rows up to borrow from
SETS = {
    "U": dict(rows=list(range(1383, 1420, 3)), names=("Aerie", "Quetzalcoatl"),
              box=(26, 36, 25, 36), method="template"),
    "E": dict(rows=list(range(1426, 1437)), names=("Tsunemoto", "Hepri"),
              box=(24, 37, 26, 37), method="median", thr=60, up=11),
    "M": dict(rows=list(range(1456, 1469)), names=("Kunihoroboshi", "Kekkando"),
              box=(25, 37, 23, 37), method="median", thr=80, up=11),
}
SIBLING_MATCH = 0.5           # template: share of the set's common pixels a sibling matches


def sheet_path(name):
    hit = [f for f in os.listdir(RES) if f.lower() == os.path.basename(name).lower()]
    if not hit:
        sys.exit("no sheet %s under %s" % (name, RES))
    return os.path.join(RES, hit[0])


def open_sheet(path):
    b = bytearray(open(path, "rb").read())
    h = dds.parse_header(bytes(b))
    if h.compressed or h.bit_count != 32:
        sys.exit("%s: not an uncompressed BGRA sheet" % path)
    return b, h


def update_mips(b, h, x, y):
    """Re-average a changed cell's footprint down the sheet's mip chain, if it has one
    (icon51/52 do: add-dds-mipmaps.py, `-if BOX`) -- the same strict 2x2 box, so the
    smaller levels show the cleaned icon and nothing outside the cell moves."""
    if h.mip_count <= 1:
        return
    offs, o = [], h.payload_offset
    for k in range(h.mip_count):
        offs.append(o)
        o += max(1, h.width >> k) * max(1, h.height >> k) * 4
    for k in range(1, h.mip_count):
        pw, ph = max(1, h.width >> (k - 1)), max(1, h.height >> (k - 1))
        cw, ch = max(1, h.width >> k), max(1, h.height >> k)
        x0, y0 = x >> k, y >> k
        x1, y1 = min(cw, -(-(x + CELL) >> k)), min(ch, -(-(y + CELL) >> k))
        prev = np.frombuffer(bytes(b[offs[k - 1]:offs[k - 1] + pw * ph * 4]), np.uint8).reshape(ph, pw, 4)
        src = prev[2 * y0:2 * y1, 2 * x0:2 * x1].astype(np.uint32)
        if pw == 1 or ph == 1:
            return                       # a 1-px level cannot be a 2x2 box; 40 px cells never reach it
        avg = ((src[0::2, 0::2] + src[1::2, 0::2] + src[0::2, 1::2] + src[1::2, 1::2] + 2) // 4).astype(np.uint8)
        for j in range(y1 - y0):
            s = offs[k] + ((y0 + j) * cw + x0) * 4
            b[s:s + (x1 - x0) * 4] = avg[j].tobytes()


def read_cell(b, h, x, y):
    o = h.payload_offset
    return b"".join(bytes(b[o + ((y + j) * h.width + x) * 4:o + ((y + j) * h.width + x + CELL) * 4])
                    for j in range(CELL))


def write_cell(b, h, x, y, cell):
    o = h.payload_offset
    for j in range(CELL):
        s = o + ((y + j) * h.width + x) * 4
        b[s:s + CELL * 4] = cell[j * CELL * 4:(j + 1) * CELL * 4]


def arr(cell):
    return np.frombuffer(cell, np.uint8).reshape(CELL, CELL, 4)


def key(a):
    """Exact RGB as one int per pixel (B,G,R byte order is irrelevant for equality)."""
    a = a[..., :3].astype(np.int64)
    return a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]


def cells_of(sprites, names):
    """{set: [(row, sheet path, x, y)]}"""
    w = Stb(STB)
    out = {}
    for s, cfg in SETS.items():
        rows = cfg["rows"]
        for r, want in ((rows[0], cfg["names"][0]), (rows[-1], cfg["names"][1])):
            if w.s(r, 0).strip() != want:
                sys.exit("LIST_WEAPON %d is %r, expected %r" % (r, w.s(r, 0).strip(), want))
        out[s] = []
        for r in rows:
            t, x1, y1, x2, y2 = sprites[w.i(r, COL_ICON)]
            if (x2 - x1, y2 - y1) != (CELL, CELL):
                sys.exit("row %d: icon cell is %dx%d" % (r, x2 - x1, y2 - y1))
            out[s].append((r, sheet_path(names[t]), x1, y1))
    return out


def all_cells(sprites, names, sheets):
    """Every 40 px item icon cell in the atlas: {(sheet path, x, y): BGRA array}."""
    out = {}
    for t, x1, y1, x2, y2 in sprites:
        if (x2 - x1, y2 - y1) != (CELL, CELL):
            continue
        try:
            p = sheet_path(names[t])
        except SystemExit:
            continue
        if (p, x1, y1) in out:
            continue
        if p not in sheets:
            try:
                sheets[p] = open_sheet(p)
            except SystemExit:
                continue
        b, h = sheets[p]
        if x1 + CELL <= h.width and y1 + CELL <= h.height:
            out[(p, x1, y1)] = arr(read_cell(b, h, x1, y1))
    return out


def clean_template(cfg, I, atlas, own):
    """The plate (pixel-identical on every icon of the set, inside the box) replaced by
    the background the badge-free icons on the same template agree on."""
    y0, y1, x0, x1 = cfg["box"]
    K = np.stack([key(a) for a in I])
    box = np.zeros((CELL, CELL), bool)
    box[y0:y1, x0:x1] = True
    same = (K == K[0]).all(0)
    plate = box & same
    common = same & ~box                         # the template outside the plate
    sibs = []
    for k, a in atlas.items():
        if k in own:
            continue
        ka = key(a)
        if (ka == K[0])[common].mean() >= SIBLING_MATCH and not (ka == K[0])[plate].any():
            sibs.append(a)
    if len(sibs) < 5:
        sys.exit("only %d badge-free icons share the template" % len(sibs))
    S = np.stack(sibs)
    SK = np.stack([key(a) for a in sibs])
    bg = np.zeros((CELL, CELL, 4), np.uint8)
    for y, x in zip(*np.nonzero(plate)):
        v, c = np.unique(SK[:, y, x], return_counts=True)
        if c.max() < 3:
            sys.exit("background at (%d, %d): no agreement among %d icons" % (y, x, len(sibs)))
        bg[y, x] = S[np.nonzero(SK[:, y, x] == v[c.argmax()])[0][0], y, x]
    out = []
    for a in I:
        n = a.copy()
        n[plate, :3] = bg[plate, :3]
        out.append(n)
    print("  %d px plate, background from %d badge-free icons" % (int(plate.sum()), len(sibs)))
    return out


def clean_median(cfg, I):
    y0, y1, x0, x1 = cfg["box"]
    F = np.stack(I).astype(float)
    med = np.median(F, 0)
    box = np.zeros((CELL, CELL), bool)
    box[y0:y1, x0:x1] = True
    out = []
    for a, f in zip(I, F):
        m = box & (np.abs(f[..., :3] - med[..., :3]).max(-1) <= cfg["thr"])
        n = a.copy()
        ys, xs = np.nonzero(m)
        n[ys, xs, :3] = np.round(med[ys - cfg["up"], xs, :3]).clip(0, 255).astype(np.uint8)
        out.append(n)
    print("  box %dx%d, background from %d rows up (median of %d)" % (
        y1 - y0, x1 - x0, cfg["up"], len(I)))
    return out


def preview(path, originals, cleaned):
    from PIL import Image
    rows = []
    for s in SETS:
        o = np.concatenate([arr(originals[s][r]) for r in SETS[s]["rows"]], 1)
        c = np.concatenate([arr(cleaned[s][r]) for r in SETS[s]["rows"]], 1)
        rows.append(np.concatenate([o, c], 0))
    wmax = max(r.shape[1] for r in rows)
    g = np.concatenate([np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows], 0)
    Image.fromarray(g[..., [2, 1, 0, 3]]).resize((g.shape[1] * 3, g.shape[0] * 3), Image.NEAREST).save(path)
    print("preview: %s" % path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--preview", metavar="PNG")
    a = ap.parse_args()

    names, sprites = tsi.sprites(os.path.join(RES, "ITEM1.TSI"))
    cells = cells_of(sprites, names)
    sheets = {}
    for lst in cells.values():
        for _r, p, _x, _y in lst:
            if p not in sheets:
                sheets[p] = open_sheet(p)
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else None
    sha = lambda b: hashlib.sha256(b).hexdigest()
    flat = [(s, r, p, x, y) for s, lst in cells.items() for r, p, x, y in lst]

    if a.restore:
        if not man:
            print("nothing to restore")
            return 0
        for s, r, p, x, y in flat:
            b, h = sheets[p]
            if read_cell(b, h, x, y) != base64.b64decode(man["clean"][s][str(r)]):
                sys.exit("refusing: row %d's icon cell changed since this script wrote it" % r)
            write_cell(b, h, x, y, base64.b64decode(man["orig"][s][str(r)]))
            update_mips(b, h, x, y)
        for p, (b, _h) in sheets.items():
            open(p, "wb").write(b)
        os.remove(MANIFEST)
        print("restored %d icon cell(s)" % len(flat))
        return 0

    if man:
        originals = {s: {int(r): base64.b64decode(v) for r, v in d.items()} for s, d in man["orig"].items()}
        cleaned = {s: {int(r): base64.b64decode(v) for r, v in d.items()} for s, d in man["clean"].items()}
    else:
        originals = {s: {r: read_cell(*sheets[p], x, y) for r, p, x, y in lst} for s, lst in cells.items()}
        atlas = None
        cleaned = {}
        for s, cfg in SETS.items():
            print("%s: %d icons" % (s, len(cfg["rows"])))
            I = [arr(originals[s][r]) for r in cfg["rows"]]
            if cfg["method"] == "template":
                if atlas is None:
                    atlas = all_cells(sprites, names, dict(sheets))
                own = {(p, x, y) for _r, p, x, y in cells[s]}
                out = clean_template(cfg, I, atlas, own)
            else:
                out = clean_median(cfg, I)
            cleaned[s] = {r: o.tobytes() for r, o in zip(cfg["rows"], out)}

    todo = [(s, r, p, x, y) for s, r, p, x, y in flat if read_cell(*sheets[p], x, y) != cleaned[s][r]]
    px = sum(int((arr(originals[s][r]) != arr(cleaned[s][r])).any(-1).sum()) for s, r, *_ in flat)
    print("%d icon(s), %d pixel(s) repainted in all; %d cell(s) to write" % (len(flat), px, len(todo)))
    if a.preview:
        preview(a.preview, originals, cleaned)

    if a.verify:
        if todo:
            print("VERIFY FAILED: rows %s" % ", ".join(str(r) for _s, r, *_ in todo))
            return 1
        print("ALL CHECKS PASSED -- the U, E and M marks are out of %d icons." % len(flat))
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    for s, r, p, x, y in todo:
        write_cell(*sheets[p], x, y, cleaned[s][r])
        update_mips(*sheets[p], x, y)
    for p in {p for _s, _r, p, _x, _y in todo}:
        open(p, "wb").write(sheets[p][0])
    enc = lambda d: {s: {str(r): base64.b64encode(v).decode() for r, v in c.items()} for s, c in d.items()}
    json.dump({"orig": enc(originals), "clean": enc(cleaned),
               "after": {s: {str(r): sha(v) for r, v in c.items()} for s, c in cleaned.items()}},
              open(MANIFEST, "w"), indent=1)
    print("wrote %d icon cell(s) (undo: --restore). Re-bake the VFS." % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
