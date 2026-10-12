"""LTB dialog text tables (``ulngtb_con.ltb``): the strings a .CON dialog shows.

Layout: ``i32 cols | i32 rows | index[row][col] = (i32 file_pos, i16 len)
| string pool``. Column 0 is the key, the rest one column per language. An
empty cell is ``(0, 0)`` in the index. A .CON node's ``str_id`` is a row here.

Two dialects, told apart by the index itself (``wide``):

* ``ULNGTB_*.LTB`` (the ``U`` is Unicode): ``len`` counts UTF-16LE wide chars,
  the pool is UTF-16LE. **This is what the client reads**
  (``CStringManager``), and what every importer writes.
* ``LNGTB_*.LTB``: the retail-era narrow twin, ``len`` in bytes, the pool in
  the ANSI code page (cp949 for the Korean originals). Nothing of ours reads
  it; it is carried so the tree round-trips.

Cells are kept as raw bytes so every existing string round-trips byte for
byte; only the ones a script writes are re-encoded. **An empty LTB cell kills
a dialog**: NPCSAY with an empty string closes the conversation.

Round-trips byte for byte on all six files we ship.
"""
import struct

from .binio import FormatError, read_file
from .stb import backup

INDEX_ENTRY = 6
LTB_INDEX_ENTRY = INDEX_ENTRY  # the name import-oro.py exported


def _detect_wide(idx):
    """True when lengths count wide chars: consecutive cells sit 2*len apart."""
    votes_wide = votes_narrow = 0
    prev = None
    for fp, ln in idx:
        if fp and ln:
            if prev is not None:
                pfp, pln = prev
                if pfp + 2 * pln == fp:
                    votes_wide += 1
                elif pfp + pln == fp:
                    votes_narrow += 1
            prev = (fp, ln)
    if votes_wide == votes_narrow == 0:
        return True
    return votes_wide >= votes_narrow


class Ltb:
    def __init__(self, path, narrow_encoding="cp949"):
        self.path = path if not isinstance(path, (bytes, bytearray)) else None
        self.narrow_encoding = narrow_encoding
        b = read_file(path)
        self.cols, nrows = struct.unpack_from("<ii", b, 0)
        if not (0 <= self.cols <= 64 and 0 <= nrows <= 1_000_000):
            raise FormatError("%s: implausible LTB dims %dx%d" % (self.path, self.cols, nrows))
        idx, o = [], 8
        for _ in range(nrows * self.cols):
            fp, ln = struct.unpack_from("<ih", b, o)
            idx.append((fp, max(0, ln)))
            o += INDEX_ENTRY
        self.wide = _detect_wide(idx)
        unit = 2 if self.wide else 1
        # A zero-length cell can carry a stale, non-zero position (LNGTB_CON.LTB
        # row 515): meaningless to a reader, kept so the index round-trips.
        self._stale_pos = {}
        self.rows, k = [], 0
        for ri in range(nrows):
            r = []
            for ci in range(self.cols):
                fp, ln = idx[k]
                k += 1
                if fp and not ln:
                    self._stale_pos[(ri, ci)] = fp
                r.append(b[fp:fp + ln * unit] if fp and ln else b"")
            self.rows.append(r)

    # ------------------------------------------------------------ text
    def text(self, row, col):
        if not (0 <= row < len(self.rows)) or not (0 <= col < self.cols):
            return ""
        cell = self.rows[row][col]
        if self.wide:
            return cell.decode("utf-16-le", "replace").rstrip("\0")
        return cell.decode(self.narrow_encoding, "replace").rstrip("\0")

    def encode(self, s):
        if self.wide:
            return (s + "\0").encode("utf-16-le")
        return (s + "\0").encode(self.narrow_encoding)

    def set_text(self, row, col, text):
        self.rows[row][col] = self.encode(text)

    def set_all_langs(self, row, key, text):
        """Key into col 0, text into every language column, as the editor does."""
        self.rows[row][0] = self.encode(key)
        for c in range(1, self.cols):
            self.rows[row][c] = self.encode(text)

    def grow_to(self, n):
        add = n - len(self.rows)
        if add > 0:
            self.rows.extend([[b""] * self.cols for _ in range(add)])
        return max(0, add)

    # ------------------------------------------------------------ bytes
    def to_bytes(self):
        unit = 2 if self.wide else 1
        out = bytearray()
        out += struct.pack("<ii", self.cols, len(self.rows))
        index_at = len(out)
        out += b"\0" * (INDEX_ENTRY * len(self.rows) * self.cols)
        positions = []
        for ri, r in enumerate(self.rows):
            for ci, cell in enumerate(r):
                if not cell:
                    positions.append((self._stale_pos.get((ri, ci), 0), 0))
                    continue
                positions.append((len(out), len(cell) // unit))
                out += cell
        o = index_at
        for fp, ln in positions:
            struct.pack_into("<ih", out, o, fp, ln)
            o += INDEX_ENTRY
        return bytes(out)

    def write(self, path):
        with open(path, "wb") as fh:
            fh.write(self.to_bytes())

    def save(self, dry, keep_backup=True):
        blob = self.to_bytes()
        if dry:
            return
        if keep_backup:
            backup(self.path)
        with open(self.path, "wb") as fh:
            fh.write(blob)
