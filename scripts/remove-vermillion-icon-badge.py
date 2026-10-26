"""Paint Rose Brasil's "IM" badge out of the 13 Cursed Vermillion icons (2026-10-26).

import-vermillion-weapons.py copied the set's icons from Brazil's ICON64.DDS, and
Brazil painted its item-mall mark -- gold "IM" letters with a brown outline -- into
the bottom-right corner of every one. The user wanted it gone.

The badge is not the same pixels on every icon (Brazil's sheet was compressed, so it
shifts a little), so it is found by colour inside the corner box (rows 26-36, cols
21-36 of the 40 px cell, inside the gold frame): every pixel there that is **not
weapon** -- red-dominant or pale grey -- is replaced by the cell's own background
10 rows up (a blue pixel there), or by the median background of the 13 icons at that
spot when the weapon covers it. The blue frame texture carries through; weapon pixels
inside the box are left as they are. Weapon art the badge covered in Brazil's file
was never there to recover.

The sheet (`icon55.dds`) is uncompressed BGRA with no mip chain -- refused otherwise
-- and only the changed pixels' bytes are written, in place: nothing else on the sheet
moves. The plan is computed from the original cells kept in the manifest, so a re-run
is a no-op; `--restore` writes the original cells back (refuses if the cells changed
since). `--preview out.png` writes a before/after strip. `data/` is gitignored, so
this file is the record. Re-bake the VFS.

    python scripts/remove-vermillion-icon-badge.py --dry-run [--preview out.png]
    python scripts/remove-vermillion-icon-badge.py
    python scripts/remove-vermillion-icon-badge.py --verify
    python scripts/remove-vermillion-icon-badge.py --restore
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
BACKUP_DIR = os.path.join(ROOT, "build", "remove-vermillion-icon-badge")
MANIFEST = os.path.join(BACKUP_DIR, "manifest.json")

ROWS = (28, 59, 81, 129, 155, 188, 254, 260, 289, 327, 359, 451, 453)   # the 225 set
NAME = "Cursed Vermillion"
COL_ICON, CELL = 9, 40
Y0, Y1, X0, X1 = 26, 37, 21, 37          # badge box, inside the frame
UP = 10                                   # background borrowed from this many rows up


def sheet_path(name):
    hit = [f for f in os.listdir(RES) if f.lower() == os.path.basename(name).lower()]
    if not hit:
        sys.exit("no sheet %s under %s" % (name, RES))
    return os.path.join(RES, hit[0])


def cells_of():
    """[(row, sheet path, x, y)] from the weapon rows' icon column and ITEM1.TSI."""
    w = Stb(STB)
    names, sprites = tsi.sprites(os.path.join(RES, "ITEM1.TSI"))
    out = []
    for r in ROWS:
        if not w.s(r, 0).strip().startswith(NAME):
            sys.exit("LIST_WEAPON %d is %r, not the %s set" % (r, w.s(r, 0).strip(), NAME))
        t, x1, y1, x2, y2 = sprites[w.i(r, COL_ICON)]
        if (x2 - x1, y2 - y1) != (CELL, CELL):
            sys.exit("row %d: icon cell is %dx%d" % (r, x2 - x1, y2 - y1))
        out.append((r, sheet_path(names[t]), x1, y1))
    return out


def open_sheet(path):
    b = bytearray(open(path, "rb").read())
    h = dds.parse_header(bytes(b))
    if h.compressed or h.bit_count != 32 or h.mip_count > 1:
        sys.exit("%s: not an uncompressed BGRA sheet without mips" % path)
    return b, h


def read_cell(b, h, x, y):
    """The cell's BGRA bytes, row by row."""
    o = h.payload_offset
    return b"".join(bytes(b[o + ((y + j) * h.width + x) * 4:o + ((y + j) * h.width + x + CELL) * 4])
                    for j in range(CELL))


def write_cell(b, h, x, y, cell):
    o = h.payload_offset
    for j in range(CELL):
        s = o + ((y + j) * h.width + x) * 4
        b[s:s + CELL * 4] = cell[j * CELL * 4:(j + 1) * CELL * 4]


def to_rgb(cell):
    a = np.frombuffer(cell, np.uint8).reshape(CELL, CELL, 4).astype(float)
    return a[..., [2, 1, 0]]                         # B,G,R -> R,G,B


def plan(originals):
    """{row: cleaned BGRA cell bytes} from the original cells."""
    I = np.stack([to_rgb(c) for c in originals.values()])
    bluish = I[..., 2] > I[..., 0] + 20
    ref = np.full((CELL, CELL, 3), np.nan)
    for yy in range(CELL):
        for xx in range(CELL):
            k = bluish[:, yy, xx]
            if k.any():
                ref[yy, xx] = np.median(I[k, yy, xx], 0)
    out = {}
    for (row, cell), c in zip(originals.items(), I):
        r, g, b = c[..., 0], c[..., 1], c[..., 2]
        weapon = (((r - g > 70) & (r - b > 50))
                  | ((abs(r - g) < 25) & (abs(g - b) < 25) & (r > 140)))
        new = np.frombuffer(cell, np.uint8).reshape(CELL, CELL, 4).copy()
        for yy in range(Y0, Y1):
            for xx in range(X0, X1):
                if weapon[yy, xx]:
                    continue
                src = c[yy - UP, xx]
                if src[2] > src[0] + 20:
                    rgb = src
                elif not np.isnan(ref[yy - UP, xx]).any():
                    rgb = ref[yy - UP, xx]
                else:
                    rgb = c[yy, X0 - 1]
                new[yy, xx, :3] = np.round(rgb[::-1]).clip(0, 255).astype(np.uint8)
        out[row] = new.tobytes()
    return out


def preview(path, originals, cleaned):
    from PIL import Image
    strip = lambda cells: np.concatenate([np.frombuffer(c, np.uint8).reshape(CELL, CELL, 4)[..., [2, 1, 0, 3]]
                                          for c in cells], 1)
    grid = np.concatenate([strip(originals.values()), strip(cleaned.values())], 0)
    Image.fromarray(grid).resize((grid.shape[1] * 4, grid.shape[0] * 4), Image.NEAREST).save(path)
    print("preview: %s" % path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--preview", metavar="PNG")
    a = ap.parse_args()

    cells = cells_of()
    sheets = {p: open_sheet(p) for p in {p for _r, p, _x, _y in cells}}
    man = json.load(open(MANIFEST)) if os.path.isfile(MANIFEST) else None
    sha = lambda b: hashlib.sha256(b).hexdigest()

    if a.restore:
        if not man:
            print("nothing to restore")
            return 0
        for r, p, x, y in cells:
            b, h = sheets[p]
            if sha(read_cell(b, h, x, y)) != man["after"][str(r)]:
                sys.exit("refusing: row %d's icon cell changed since this script wrote it" % r)
            write_cell(b, h, x, y, base64.b64decode(man["orig"][str(r)]))
        for p, (b, _h) in sheets.items():
            open(p, "wb").write(b)
        os.remove(MANIFEST)
        print("restored %d icon cell(s)" % len(cells))
        return 0

    if man:
        originals = {r: base64.b64decode(man["orig"][str(r)]) for r in ROWS}
    else:
        originals = {r: read_cell(*sheets[p], x, y) for r, p, x, y in cells}
    cleaned = plan(originals)
    todo = [(r, p, x, y) for r, p, x, y in cells if read_cell(*sheets[p], x, y) != cleaned[r]]
    changed = sum(int((np.frombuffer(originals[r], np.uint8) != np.frombuffer(cleaned[r], np.uint8))
                      .reshape(-1, 4).any(1).sum()) for r in ROWS)
    print("%d icon(s), %d pixel(s) repainted in all; %d cell(s) to write" % (len(cells), changed, len(todo)))
    if a.preview:
        preview(a.preview, originals, cleaned)

    if a.verify:
        if todo:
            print("VERIFY FAILED: rows %s" % ", ".join(str(r) for r, _p, _x, _y in todo))
            return 1
        print("ALL CHECKS PASSED -- the badge is out of the %d icons." % len(cells))
        return 0
    if not todo:
        print("nothing to do.")
        return 0
    if a.dry_run:
        print("dry run: nothing written")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    for r, p, x, y in todo:
        write_cell(*sheets[p], x, y, cleaned[r])
    for p, (b, _h) in sheets.items():
        open(p, "wb").write(b)
    json.dump({"orig": {str(r): base64.b64encode(originals[r]).decode() for r in ROWS},
               "after": {str(r): sha(cleaned[r]) for r in ROWS}}, open(MANIFEST, "w"), indent=1)
    print("wrote %d icon cell(s) (undo: --restore). Re-bake the VFS." % len(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
