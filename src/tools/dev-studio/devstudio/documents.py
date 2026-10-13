"""Open files as editable documents: the codec, an undo stack, and safe saving.

A document owns one ``rosefmt`` object and never parses bytes itself -- the
studio is a front end over the same reader/writer the 73 scripts use, so a file
the studio saves is a file the scripts' round-trip test has already proven.

Every change goes through a ``QUndoCommand``; nothing writes to the codec's
lists directly from the UI. Saving:

1. serialise with the codec's ``to_bytes``;
2. re-parse those bytes and compare them with what the editor holds -- a save
   that would not read back is refused, the file on disk is untouched;
3. copy the original once per session to ``build/dev-studio/backups/<session>/``
   (never beside the file: ``pack.ps1`` refuses to bake while a ``.bak`` sits
   under ``data/``);
4. write a hidden ``.tmp`` sibling and rename it over the file, so a crash
   mid-write cannot leave half a table (``*.tmp`` is in pack.ps1's excludes).
"""
import os
import re
import shutil
import time
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoCommand, QUndoStack

from rosefmt import Stb, Stl
from rosefmt.binio import FormatError

REPO_ROOT = Path(__file__).resolve().parents[4]
SESSION = time.strftime("%Y%m%d-%H%M%S")
BACKUP_ROOT = REPO_ROOT / "build" / "dev-studio" / "backups" / SESSION

ENCODINGS = [
    ("latin-1", "Western (latin-1)", "Our data and most English dumps"),
    ("cp949", "Korean (cp949)", "RoseZA, retail Korean tables"),
    ("cp932", "Japanese (Shift-JIS)", "Jrose"),
    ("utf-8", "UTF-8", "Rare; some editor-written headers"),
]
ENCODING_NAMES = {e: n for e, n, _ in ENCODINGS}

_backed_up = set()


def decode_label(b):
    """Column/row titles were written by many editors: try the strict codecs
    first so Korean titles show as Korean rather than mojibake."""
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("latin-1")


def is_number(s):
    s = s.strip()
    if not s:
        return False
    if s[0] in "+-":
        s = s[1:]
    return s.replace(".", "", 1).isdigit()


def _backup_once(path):
    if path in _backed_up:
        return None
    p = Path(path)
    dest = BACKUP_ROOT / Path(*p.parts[1:]) if p.is_absolute() else BACKUP_ROOT / p
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, dest)
    _backed_up.add(path)
    return dest


class Document(QObject):
    dirtyChanged = pyqtSignal(bool)
    contentChanged = pyqtSignal()
    saved = pyqtSignal()
    kind = ""

    def __init__(self, path, encoding):
        super().__init__()
        self.path = os.path.normpath(os.path.abspath(path))
        self.encoding = encoding
        self.undo = QUndoStack(self)
        # bound methods, not lambdas: Qt drops these connections when the
        # document is destroyed, a lambda would fire into a deleted object
        self.undo.cleanChanged.connect(self._clean_changed)
        self.undo.indexChanged.connect(self._index_changed)
        self._stat()

    def _clean_changed(self, clean):
        self.dirtyChanged.emit(not clean)

    def _index_changed(self, _i):
        self.contentChanged.emit()

    def _stat(self):
        st = os.stat(self.path)
        self.disk_stamp = (st.st_mtime_ns, st.st_size)

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def dirty(self):
        return not self.undo.isClean()

    def changed_on_disk(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return False
        return (st.st_mtime_ns, st.st_size) != self.disk_stamp

    def save(self):
        """Returns the backup path (or None if this session already made one)."""
        blob = self.to_bytes()
        self.verify(blob)
        backup = _backup_once(self.path)
        folder, base = os.path.split(self.path)
        tmp = os.path.join(folder, ".%s.devstudio.tmp" % base)
        with open(tmp, "wb") as fh:
            fh.write(blob)
        os.replace(tmp, self.path)
        self._stat()
        self._mark_saved()
        self.undo.setClean()
        self.saved.emit()
        return backup

    # subclasses
    def to_bytes(self):
        raise NotImplementedError

    def verify(self, blob):
        raise NotImplementedError

    def _mark_saved(self):
        raise NotImplementedError


# =================================================================== STB
class _SetCells(QUndoCommand):
    def __init__(self, doc, cells, text):
        super().__init__(text)
        self.doc, self.cells = doc, cells     # [(r, c, old_bytes, new_bytes)]

    def redo(self):
        self.doc._apply_cells(self.cells, 3)

    def undo(self):
        self.doc._apply_cells(self.cells, 2)


class _AppendRows(QUndoCommand):
    def __init__(self, doc, n):
        super().__init__("Append %d row%s" % (n, "s" if n != 1 else ""))
        self.doc, self.n, self.state = doc, n, None

    def redo(self):
        self.state = self.doc._append_rows(self.n)

    def undo(self):
        self.doc._unappend_rows(self.state)


class StbDocument(Document):
    """An STB table. Rows are ids: there is deliberately no insert or delete in
    the middle, because every other table, script and the C++ address rows by
    number. Rows are appended at the end, or cleared."""
    kind = "stb"
    cellsChanged = pyqtSignal(int, int, int, int)      # r0, c0, r1, c1 inclusive
    rowsAboutToBeAppended = pyqtSignal(int, int)
    rowsAppended = pyqtSignal()
    rowsAboutToBeRemoved = pyqtSignal(int, int)
    rowsRemoved = pyqtSignal()
    labelsChanged = pyqtSignal()

    def __init__(self, path, encoding="latin-1"):
        super().__init__(path, encoding)
        self.stb = Stb(self.path, encoding)
        self._colnames = [decode_label(self.stb.colnames[c + 1]) if c + 1 < len(self.stb.colnames)
                          else "" for c in range(self.stb.cols)]
        self._row_text = {}
        self.key_col = None
        self.names = {}
        self.strings_path = None
        self._mark_saved()

    # ---------------------------------------------------------- reading
    @property
    def rows(self):
        return self.stb.rows

    @property
    def cols(self):
        return self.stb.cols

    def raw(self, r, c):
        return self.stb.d[r][c]

    def text(self, r, c):
        return self.stb.d[r][c].decode(self.encoding, "replace")

    def colname(self, c):
        return self._colnames[c] if c < len(self._colnames) else ""

    def occupied(self, r):
        return any(x.strip() for x in self.stb.d[r])

    def row_text(self, r):
        t = self._row_text.get(r)
        if t is None:
            t = "\x1f".join(x.decode(self.encoding, "replace") for x in self.stb.d[r]).lower()
            self._row_text[r] = t
        return t

    def row_label(self, r):
        """The row's in-game name from the companion STL, or "" -- never a copy
        of a cell, which the grid already shows."""
        d = self.stb.d[r]
        if self.key_col is not None and self.key_col < len(d):
            return self.names.get(d[self.key_col].strip(), "")
        return ""

    def row_title(self, r):
        """A heading for the row: its STL name, else its first cell."""
        return self.row_label(r) or (self.stb.d[r][0].decode(self.encoding, "replace").strip()
                                     if self.stb.d[r] else "")

    def labels_informative(self):
        """True when the STL names say something the first column does not: in
        LIST_NPC they mostly repeat column 0, in LIST_WEAPON column 0 is blank."""
        seen = same = 0
        for r in range(self.rows):
            lab = self.row_label(r)
            if not lab:
                continue
            seen += 1
            if lab.strip() == self.stb.d[r][0].decode(self.encoding, "replace").strip():
                same += 1
            if seen >= 600:
                break
        return seen > 0 and same < 0.8 * seen

    def string_key(self, r):
        if self.key_col is None:
            return ""
        return self.stb.d[r][self.key_col].decode("latin-1").strip()

    def is_modified(self, r, c):
        return r >= len(self._saved) or self._saved[r][c] != self.stb.d[r][c]

    def row_modified(self, r):
        return r >= len(self._saved) or self._saved[r] != self.stb.d[r]

    def modified_count(self):
        n = 0
        for r, row in enumerate(self.stb.d):
            if r >= len(self._saved):
                n += sum(1 for x in row if x)
            else:
                s = self._saved[r]
                if s != row:
                    n += sum(1 for a, b in zip(s, row) if a != b)
        return n

    # ---------------------------------------------------------- strings link
    def attach_strings(self, path, names, key_col):
        self.strings_path, self.names, self.key_col = path, names, key_col
        self.labelsChanged.emit()

    # ---------------------------------------------------------- editing
    def encode(self, value):
        try:
            b = value.encode(self.encoding)
        except UnicodeEncodeError as e:
            raise ValueError("'%s' cannot be stored as %s" % (value[e.start:e.end],
                                                              ENCODING_NAMES.get(self.encoding, self.encoding)))
        if len(b) > 0xFFFF:
            raise ValueError("A cell holds at most 65,535 bytes")
        return b

    def set_cells(self, changes, label="Edit cell"):
        """``changes``: [(r, c, str)]. Raises ValueError (nothing applied) when
        a value cannot be encoded. Returns the number of cells that changed."""
        cells = []
        for r, c, v in changes:
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                continue
            new = self.encode(v)
            old = self.stb.d[r][c]
            if new != old:
                cells.append((r, c, old, new))
        if cells:
            if len(cells) > 1 and label == "Edit cell":
                label = "Edit %d cells" % len(cells)
            self.undo.push(_SetCells(self, cells, label))
        return len(cells)

    def append_rows(self, n):
        if n > 0:
            self.undo.push(_AppendRows(self, n))

    def _apply_cells(self, cells, which):
        r0 = c0 = 1 << 30
        r1 = c1 = -1
        for cell in cells:
            r, c = cell[0], cell[1]
            self.stb.d[r][c] = cell[which]
            self._row_text.pop(r, None)
            r0, r1, c0, c1 = min(r0, r), max(r1, r), min(c0, c), max(c1, c)
        if r1 >= 0:
            self.cellsChanged.emit(r0, c0, r1, c1)

    def _append_rows(self, n):
        old = self.stb.rows
        state = (old, len(self.stb.header), len(self.stb.rownames))
        self.rowsAboutToBeAppended.emit(old, old + n - 1)
        self.stb.grow_to(old + n)
        self.rowsAppended.emit()
        return state

    def _unappend_rows(self, state):
        old, hlen, nlen = state
        self.rowsAboutToBeRemoved.emit(old, self.stb.rows - 1)
        del self.stb.d[old:]
        self.stb.header = self.stb.header[:hlen]
        del self.stb.rownames[nlen:]
        self.stb.rows = old
        for r in [r for r in self._row_text if r >= old]:
            del self._row_text[r]
        self.rowsRemoved.emit()

    # ---------------------------------------------------------- saving
    def to_bytes(self):
        return self.stb.to_bytes()

    def verify(self, blob):
        back = Stb(blob, self.encoding)
        if (back.rows, back.cols) != (self.stb.rows, self.stb.cols):
            raise FormatError("read-back has %dx%d cells, expected %dx%d"
                              % (back.rows, back.cols, self.stb.rows, self.stb.cols))
        if back.header != self.stb.header or back.tail != self.stb.tail:
            raise FormatError("read-back header differs")
        if back.d != self.stb.d:
            bad = next((r for r in range(back.rows) if back.d[r] != self.stb.d[r]), -1)
            raise FormatError("read-back differs from row %d" % bad)

    def _mark_saved(self):
        self._saved = [list(r) for r in self.stb.d]


# =================================================================== STL
FIELD_NAMES = {
    1: ["Name"],
    2: ["Name", "Description"],
    4: ["Name", "Description", "Start message", "End message"],
}

KEY_RE = re.compile(r"^([A-Za-z_]*?)(\d+)$")

# The client's LANGUAGE_TYPE (src/client/gamecommon/stringmanager.h): slot n of a
# five-slot STL is this language whatever text it happens to hold -- most of our
# non-English slots are English copies.
SLOT_LANGUAGES = ("Korean", "English", "Japanese", "Chinese (Traditional)", "Chinese (Simplified)")
CLIENT_SLOT = 1


def _has_hangul(s):
    return any(0xAC00 <= ord(ch) <= 0xD7A3 for ch in s)


def _detect_slot_encoding(rows, default):
    """Our STLs keep English in slot 1 as latin-1, and Korean (slot 0), Japanese
    (2) and Chinese (3, 4) as **UTF-8** -- every non-ASCII entry of those slots
    decodes strictly, across all 33 files. Latin-1 accents almost never form
    valid UTF-8, so a slot whose non-ASCII entries (nearly) all decode is shown
    and edited as UTF-8; a Korean dump's cp949 slot is recognised by its Hangul.
    Anything else uses the document encoding."""
    if default != "latin-1":
        return default
    nonascii = [f for row in rows for f in row if any(b > 127 for b in f)][:600]
    if len(nonascii) < 2:
        return default
    ok8 = hangul = 0
    for f in nonascii:
        try:
            f.decode("utf-8")
            ok8 += 1
            continue
        except UnicodeDecodeError:
            pass
        try:
            if _has_hangul(f.decode("cp949")):
                hangul += 1
        except UnicodeDecodeError:
            pass
    if ok8 >= 0.9 * len(nonascii):
        return "utf-8"
    if hangul >= 0.8 * len(nonascii):
        return "cp949"
    return default


def _script_label(rows, enc):
    """Name a slot by what its text is written in, not by a guessed slot order."""
    filled = [row[0] for row in rows if row and row[0].strip()]
    if not filled:
        return "empty"
    hangul = kana = han = latin = 0
    for f in filled[:600]:
        for ch in f.decode(enc, "replace"):
            o = ord(ch)
            if 0xAC00 <= o <= 0xD7A3:
                hangul += 1
            elif 0x3040 <= o <= 0x30FF:
                kana += 1
            elif 0x4E00 <= o <= 0x9FFF:
                han += 1
            elif ch.isalpha():
                latin += 1
    if hangul and hangul >= max(kana, han * 0.3):
        return "Korean"
    if kana:
        return "Japanese"
    if han and han >= latin * 0.2:
        return "Chinese"
    ascii_ = sum(1 for f in filled if all(b < 128 for b in f))
    return "English" if ascii_ >= 0.9 * len(filled) else "Latin"


class _SetFields(QUndoCommand):
    def __init__(self, doc, edits, text):
        super().__init__(text)
        self.doc, self.edits = doc, edits     # [(e, f, slot, old, new)]

    def redo(self):
        self.doc._apply_fields(self.edits, 4)

    def undo(self):
        self.doc._apply_fields(self.edits, 3)


class _SetKey(QUndoCommand):
    def __init__(self, doc, e, old, new, text):
        super().__init__(text)
        self.doc, self.e, self.old, self.new = doc, e, old, new   # (key bytes, id)

    def redo(self):
        self.doc._apply_key(self.e, self.new)

    def undo(self):
        self.doc._apply_key(self.e, self.old)


class _InsertEntries(QUndoCommand):
    """Insert (or, inverted, remove) whole entries. ``items``: ascending
    [(index, (key, id), [fields per slot])]."""

    def __init__(self, doc, items, insert, text):
        super().__init__(text)
        self.doc, self.items, self.insert = doc, items, insert

    def redo(self):
        (self.doc._insert_entries if self.insert else self.doc._remove_entries)(self.items)

    def undo(self):
        (self.doc._remove_entries if self.insert else self.doc._insert_entries)(self.items)


class StlDocument(Document):
    """A string table. Entries are addressed by *key* by everything else, so
    unlike an STB row an entry can be added at the end or removed."""
    kind = "stl"
    entriesChanged = pyqtSignal(int, int)
    entriesAboutToBeInserted = pyqtSignal(int, int)
    entriesInserted = pyqtSignal()
    entriesAboutToBeRemoved = pyqtSignal(int, int)
    entriesRemoved = pyqtSignal()

    def __init__(self, path, encoding="latin-1"):
        super().__init__(path, encoding)
        self.stl = Stl(self.path, encoding)
        self.slot_enc = [_detect_slot_encoding(rows, encoding) for rows in self.stl.langs]
        if len(self.stl.langs) == len(SLOT_LANGUAGES):
            self.slot_names = list(SLOT_LANGUAGES)
        else:
            self.slot_names = [_script_label(rows, enc) for rows, enc in zip(self.stl.langs, self.slot_enc)]
        self.field_names = FIELD_NAMES.get(self.stl.nfields,
                                           ["Field %d" % (i + 1) for i in range(self.stl.nfields)])
        self._search = {}
        self._mark_saved()

    # ---------------------------------------------------------- reading
    @property
    def count(self):
        return len(self.stl.keys)

    @property
    def nfields(self):
        return self.stl.nfields

    @property
    def nslots(self):
        return len(self.stl.langs)

    @property
    def format_tag(self):
        return self.stl.fmt.decode("latin-1")

    def key(self, e):
        return self.stl.keys[e][0].decode("latin-1")

    def ident(self, e):
        return self.stl.keys[e][1]

    def field(self, e, f, slot):
        return self.stl.langs[slot][e][f].decode(self.slot_enc[slot], "replace")

    def raw_field(self, e, f, slot):
        return self.stl.langs[slot][e][f]

    def index_of(self, key):
        kb = key.encode("latin-1") if isinstance(key, str) else key
        for i, (k, _) in enumerate(self.stl.keys):
            if k == kb:
                return i
        return None

    def search_text(self, e, slot):
        t = self._search.get((e, slot))
        if t is None:
            t = "\x1f".join([self.key(e), str(self.ident(e))] +
                            [self.field(e, f, slot) for f in range(self.nfields)]).lower()
            self._search[(e, slot)] = t
        return t

    def slot_label(self, slot):
        return "%d · %s" % (slot, self.slot_names[slot])

    def shared_slots(self, slot):
        """Slots that point at the same block as ``slot`` on disk."""
        for g in getattr(self.stl, "lang_groups", None) or []:
            if slot in g:
                return list(g)
        return [slot]

    def display_slot(self):
        """The slot the game client reads: ``CStringManager`` picks it from the
        Windows charset, and an ANSI/Western install lands on LANGUAGE_USA = 1.
        A single-slot (legacy) table has only slot 0."""
        return CLIENT_SLOT if self.nslots > CLIENT_SLOT else 0

    def names_by_key(self):
        slot = self.display_slot()
        enc = self.slot_enc[slot]
        return {k: row[0].decode(enc, "replace") for (k, _), row in zip(self.stl.keys, self.stl.langs[slot])}

    def key_modified(self, e):
        return self.stl.keys[e][0] not in self._saved

    def id_modified(self, e):
        s = self._saved.get(self.stl.keys[e][0])
        return s is None or s[0] != self.stl.keys[e][1]

    def is_modified(self, e, f, slot):
        s = self._saved.get(self.stl.keys[e][0])
        return s is None or s[1][slot][f] != self.stl.langs[slot][e][f]

    def entry_modified(self, e):
        s = self._saved.get(self.stl.keys[e][0])
        if s is None or s[0] != self.stl.keys[e][1]:
            return True
        return any(s[1][sl] != self.stl.langs[sl][e] for sl in range(self.nslots))

    def suggest_key(self):
        keys = {k for k, _ in self.stl.keys}
        for k, _ in reversed(self.stl.keys):
            m = KEY_RE.match(k.decode("latin-1"))
            if m:
                prefix, digits = m.group(1), m.group(2)
                n = int(digits) + 1
                while True:
                    cand = "%s%0*d" % (prefix, len(digits), n)
                    if cand.encode("latin-1") not in keys:
                        return cand
                    n += 1
        return ""

    def suggest_id(self):
        return max((i for _, i in self.stl.keys), default=-1) + 1

    # ---------------------------------------------------------- editing
    def encode_for(self, slot, value):
        enc = self.slot_enc[slot]
        try:
            return value.encode(enc)
        except UnicodeEncodeError as e:
            raise ValueError("'%s' cannot be stored as %s"
                             % (value[e.start:e.end], ENCODING_NAMES.get(enc, enc)))

    def targets(self, e, f, slot):
        """An edit applies to every slot that shares this block on disk and still
        holds the same text, so LIST_STRING_S.STL's five slots stay one block."""
        cur = self.stl.langs[slot][e][f]
        return [s for s in self.shared_slots(slot) if self.stl.langs[s][e][f] == cur]

    def set_field(self, e, f, slot, value):
        edits = []
        for s in self.targets(e, f, slot):
            new = self.encode_for(s, value)
            old = self.stl.langs[s][e][f]
            if new != old:
                edits.append((e, f, s, old, new))
        if edits:
            self.undo.push(_SetFields(self, edits, "Edit %s of %s" % (self.field_names[f].lower(), self.key(e))))
        return bool(edits)

    def validate_key(self, value, exclude=None):
        if not value:
            return "A key cannot be empty"
        try:
            kb = value.encode("ascii")
        except UnicodeEncodeError:
            return "Keys are plain ASCII"
        if len(kb) > 255:
            return "A key holds at most 255 characters"
        for i, (k, _) in enumerate(self.stl.keys):
            if k == kb and i != exclude:
                return "%s is already used by entry %d" % (value, i)
        return None

    def set_key(self, e, value):
        err = self.validate_key(value, exclude=e)
        if err:
            raise ValueError(err)
        old = self.stl.keys[e]
        new = (value.encode("ascii"), old[1])
        if new != old:
            self.undo.push(_SetKey(self, e, old, new, "Rename key %s" % self.key(e)))

    def set_ident(self, e, value):
        try:
            v = int(str(value).strip())
        except ValueError:
            raise ValueError("The id is a whole number")
        if not 0 <= v <= 0xFFFFFFFF:
            raise ValueError("The id is an unsigned 32-bit number")
        old = self.stl.keys[e]
        if v != old[1]:
            self.undo.push(_SetKey(self, e, old, (old[0], v), "Change id of %s" % self.key(e)))

    def add_entry(self, key, ident, name):
        err = self.validate_key(key)
        if err:
            raise ValueError(err)
        fields = []
        for s in range(self.nslots):
            row = [self.encode_for(s, name)] + [b""] * (self.nfields - 1)
            fields.append(row)
        item = (self.count, (key.encode("ascii"), int(ident)), fields)
        self.undo.push(_InsertEntries(self, [item], True, "Add %s" % key))
        return self.count - 1

    def remove_entries(self, indices):
        items = []
        for e in sorted(set(indices)):
            items.append((e, self.stl.keys[e], [list(self.stl.langs[s][e]) for s in range(self.nslots)]))
        if items:
            label = "Remove %s" % self.key(items[0][0]) if len(items) == 1 else "Remove %d entries" % len(items)
            self.undo.push(_InsertEntries(self, items, False, label))

    def _apply_fields(self, edits, which):
        lo, hi = 1 << 30, -1
        for ed in edits:
            e, f, s = ed[0], ed[1], ed[2]
            self.stl.langs[s][e][f] = ed[which]
            self._search.pop((e, s), None)
            lo, hi = min(lo, e), max(hi, e)
        if hi >= 0:
            self.entriesChanged.emit(lo, hi)

    def _apply_key(self, e, kv):
        self.stl.keys[e] = kv
        for s in range(self.nslots):
            self._search.pop((e, s), None)
        self.entriesChanged.emit(e, e)

    def _insert_entries(self, items):
        for e, kv, fields in items:          # ascending: each index is final
            self.entriesAboutToBeInserted.emit(e, e)
            self.stl.keys.insert(e, kv)
            for s in range(self.nslots):
                self.stl.langs[s].insert(e, list(fields[s]))
            self.stl.count = len(self.stl.keys)
            self._search.clear()
            self.entriesInserted.emit()

    def _remove_entries(self, items):
        for e, _kv, _fields in reversed(items):
            self.entriesAboutToBeRemoved.emit(e, e)
            del self.stl.keys[e]
            for s in range(self.nslots):
                del self.stl.langs[s][e]
            self.stl.count = len(self.stl.keys)
            self._search.clear()
            self.entriesRemoved.emit()

    # ---------------------------------------------------------- saving
    def to_bytes(self):
        return self.stl.to_bytes()

    def verify(self, blob):
        back = Stl(blob, self.encoding)
        if back.keys != self.stl.keys:
            raise FormatError("read-back keys differ")
        if self.stl.legacy:
            same = back.langs[0] == self.stl.langs[0]
        else:
            same = back.langs == self.stl.langs
        if not same:
            raise FormatError("read-back text differs")

    def _mark_saved(self):
        self._saved = {}
        for e, (k, i) in enumerate(self.stl.keys):
            self._saved[k] = (i, [list(self.stl.langs[s][e]) for s in range(len(self.stl.langs))])
