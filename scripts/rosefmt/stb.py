"""STB1 tables (``3DDATA/STB/*.STB``): the game's data tables.

Layout, read out of ``src/lib_util/src/classstb.cpp`` (``classSTB::Open``), the
only C++ that parses the header rather than seeking past it::

    "STB1" u32 data_offset u32 raw_rows u32 raw_cols
    u32 row_height
    (raw_cols + 1) x u16 column width      <- note the +1, it is easy to miss
    raw_cols      x pstr16 column name
    raw_rows      x pstr16 row name        <- the first is the column-title line
    @data_offset: (raw_rows-1) x (raw_cols-1) x pstr16 cell

**Game indices drop the header row and the root column**, so ``get(r, c)`` is
what ``get_int32(r, c)`` returns on the C++ side, and editor column N is game
column N-1. The header region is kept as raw bytes (``header``) so a rewrite is
byte-identical; ``colnames`` / ``rownames`` are parsed from it for display only
(reference dumps label their columns, ours mostly do not). Row labels are the
last thing in the header, so appending rows means appending label strings to it.
Editors sometimes leave junk after the last cell; it is kept in ``tail``.

Encoding: **ours is latin-1**. Jrose is Shift-JIS (cp932), RoseZA is Korean
(cp949/euc-kr). Decoding with the wrong codec does not raise -- it yields
mojibake that looks like a corrupt file. Pass ``encoding`` for a foreign dump.

Round-trips byte for byte on every STB we ship (``scripts/rosefmt-roundtrip.py``).
"""
import io
import os
import re
import shutil
import struct

from .binio import FormatError, read_file, read_pstr16, write_pstr16

MAGIC = b"STB1"


def backup(path):
    """Copy ``path`` to ``path.bak`` once. ``scripts/pack.ps1`` refuses to bake
    while a ``.bak`` sits under ``data/``, which is the reminder to move it."""
    if not os.path.exists(path + ".bak"):
        shutil.copyfile(path, path + ".bak")


class Stb:
    def __init__(self, path, encoding="latin-1"):
        self.path = path if not isinstance(path, (bytes, bytearray)) else None
        self.encoding = encoding
        raw = read_file(path)
        if raw[:4] != MAGIC:
            raise FormatError("%s: not an STB1 file (%r)" % (self.path, raw[:4]))
        self.data_offset, raw_rows, raw_cols = struct.unpack_from("<III", raw, 4)
        self.rows, self.cols = raw_rows - 1, raw_cols - 1
        self.header = raw[16:self.data_offset]
        self._parse_header(raw_rows, raw_cols)

        f = io.BytesIO(raw)
        f.seek(self.data_offset)

        def cell():
            n, = struct.unpack("<H", f.read(2))
            return f.read(n)

        try:
            self.d = [[cell() for _ in range(self.cols)] for _ in range(self.rows)]
        except struct.error:
            raise FormatError("%s: truncated at byte %d (%d x %d cells declared)"
                              % (self.path, f.tell(), self.rows, self.cols))
        self.tail = f.read()          # editors sometimes leave junk; preserved

    def _parse_header(self, raw_rows, raw_cols):
        """Display fields only; a header the parse cannot follow leaves them empty."""
        self.row_height, self.widths, self.colnames, self.rownames = 0, (), [], []
        try:
            h = self.header
            self.row_height, = struct.unpack_from("<I", h, 0)
            o = 4
            self.widths = struct.unpack_from("<%dH" % (raw_cols + 1), h, o)
            o += 2 * (raw_cols + 1)
            names = []
            for _ in range(raw_cols + raw_rows):
                s, o = read_pstr16(h, o)
                names.append(s)
            self.colnames, self.rownames = names[:raw_cols], names[raw_cols:]
        except (struct.error, IndexError):
            self.colnames, self.rownames = [], []

    # ------------------------------------------------------------ reading
    def get(self, r, c):
        """Raw bytes for a game cell, or b"" when out of range."""
        return self.d[r][c] if 0 <= r < self.rows and 0 <= c < self.cols else b""

    def s(self, r, c):
        """A cell as text (not stripped)."""
        return self.get(r, c).decode(self.encoding, "replace")

    def i(self, r, c):
        """A cell as an int; 0 for blank or non-numeric (what the client does)."""
        v = self.get(r, c).strip()
        try:
            return int(v)
        except ValueError:
            return 0

    def occupied(self, r):
        return 0 <= r < self.rows and any(x.strip() for x in self.d[r])

    def rowname(self, r):
        # rownames[0] labels the column-title line, so game row r is rownames[r+1]
        return (self.rownames[r + 1].decode(self.encoding, "replace")
                if r + 1 < len(self.rownames) else "")

    def colname(self, c):
        # colnames[0] labels the root column, so game col c is colnames[c+1]
        return (self.colnames[c + 1].decode(self.encoding, "replace")
                if c + 1 < len(self.colnames) else "")

    def key_column(self):
        """Index of the column holding STL keys (LWEA001, LNPC0001, ...).

        Ours is 45 on LIST_WEAPON; Jrose uses the last column. Sniffing beats
        hardcoding either, because the wrong guess yields a wrong name rather
        than an error.
        """
        best, score = None, 0.0
        for c in range(self.cols):
            vals = [self.s(r, c).strip() for r in range(self.rows) if self.occupied(r)]
            vals = [v for v in vals if v]
            if not vals:
                continue
            hit = sum(1 for v in vals if re.fullmatch(r"[A-Za-z]{3,6}\d{3,5}", v))
            frac = hit / float(len(vals))
            if frac > score:
                best, score = c, frac
        return best if score > 0.7 else None

    # ------------------------------------------------------------ writing
    def set(self, r, c, v):
        if isinstance(v, str):
            v = v.encode(self.encoding)
        self.d[r][c] = v

    def set_i(self, r, c, v):
        self.d[r][c] = str(int(v)).encode("ascii")

    def grow_to(self, game_rows, labels=None):
        """Extend to ``game_rows``, appending blank rows and their row labels.

        ``labels`` maps a new game row to its label; unlabelled rows get an
        empty one (the editor shows the row number either way).
        """
        add = game_rows - self.rows
        if add <= 0:
            return 0
        extra = io.BytesIO()
        for k in range(add):
            lbl = b""
            if labels:
                lbl = labels.get(self.rows + k, b"")
                if isinstance(lbl, str):
                    lbl = lbl.encode(self.encoding)
            extra.write(write_pstr16(lbl))
            if self.rownames:
                self.rownames.append(lbl)
        self.header += extra.getvalue()
        self.d.extend([[b"" for _ in range(self.cols)] for _ in range(add)])
        self.rows = game_rows
        return add

    def to_bytes(self):
        out = io.BytesIO()
        out.write(MAGIC)
        out.write(struct.pack("<III", 16 + len(self.header), self.rows + 1, self.cols + 1))
        out.write(self.header)
        for row in self.d:
            for cell in row:
                out.write(struct.pack("<H", len(cell)))
                out.write(cell)
        out.write(self.tail)
        return out.getvalue()

    def write(self, path):
        with open(path, "wb") as fh:
            fh.write(self.to_bytes())

    def save(self, dry, keep_backup=True):
        """Write back to ``path`` (after a one-time ``.bak``); nothing when dry."""
        blob = self.to_bytes()
        if dry:
            return
        if keep_backup:
            backup(self.path)
        with open(self.path, "wb") as fh:
            fh.write(blob)
