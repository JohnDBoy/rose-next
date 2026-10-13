"""STL string tables (``LIST_*_S.STL``): names and descriptions keyed by STL key.

Both dialects are read; only the modern one is written back, and the legacy one
only when it was read as legacy (``legacy`` flag) -- each in its own layout:

* **modern** ``NRST01`` / ``ITST01`` / ``QEST01``::

      pstr8 tag | u32 key_count | key_count x (pstr8 key, u32 id)
      | u32 lang_count | lang_count x u32 block_offset
      per block: key_count x u32 entry_offset, then the entries

* **legacy** ``N_NUM`` / ``I_NUM`` / ``Q_NUM`` (Jrose and older clients): no
  language table and no per-entry offsets -- the entries follow the key table
  directly. A modern-only parser reads the first varint of the string data as a
  language count and asks for an 8 GB buffer.

An entry is ``nfields`` varint-length strings: 1 (name) for N, 2 (name,
description) for I, 4 for Q. **The client ignores the per-entry offset table
and reads the entries sequentially**, so entries must stay in key order --
which is why ``append`` only ever adds at the end and ``to_bytes`` rebuilds the
offset tables from scratch. The tag itself is a u8-length string, not a varint.

**Never grep an STL for keys**: each key is followed by a u32 id whose low byte
is often an ASCII digit (id 304 -> ``30 01 00 00``, and ``0x30`` is ``'0'``), so
``LSEL\\d+`` reads ``LSEL304`` as ``LSEL3040``. Parse the table.

Encoding: the ``encoding`` argument defaults to latin-1, which round-trips any
bytes, but our STL text is UTF-8 in every slot (the client converts it with
``CLocalizing::UTF8ToMBCS``; see src/tools/dev-studio/CLAUDE.md) -- pass
``encoding="utf-8"`` to read or write non-ASCII text. See ``stb`` for the
foreign dumps' encodings. Block 0 of
``LIST_SKILL_S.STL`` is real Korean for most keys -- English is block 1.

Round-trips byte for byte on every STL we ship.
"""
import io
import struct

from .binio import (FormatError, read_file, read_pstr8, read_vstr, write_pstr8,
                    write_vstr)
from .stb import backup

FIELDS = {b"NRST01": 1, b"ITST01": 2, b"QEST01": 4,
          b"N_NUM": 1, b"I_NUM": 2, b"Q_NUM": 4}
LEGACY = {b"N_NUM", b"I_NUM", b"Q_NUM"}
STL_FIELDS = FIELDS  # the name import-oro.py exported


class Stl:
    def __init__(self, path, encoding="latin-1"):
        self.path = path if not isinstance(path, (bytes, bytearray)) else None
        self.encoding = encoding
        buf = read_file(path)
        self.b = buf
        self.fmt, o = read_pstr8(buf, 0)
        if self.fmt not in FIELDS:
            raise FormatError("%s: unknown STL format %r" % (self.path, self.fmt))
        self.tag = self.fmt
        self.nfields = FIELDS[self.fmt]
        self.legacy = self.fmt in LEGACY
        count, = struct.unpack_from("<I", buf, o)
        o += 4
        self.keys = []
        for _ in range(count):
            k, o = read_pstr8(buf, o)
            i, = struct.unpack_from("<I", buf, o)
            o += 4
            self.keys.append((k, i))
        self.count = count

        self.langs = []          # [lang][entry] -> [field bytes, ...]
        self._block_end = []
        if self.legacy:
            rows, o = self._read_entries(buf, o, count)
            self.langs.append(rows)
            self.end = o
            self._block_end.append(o)
            self.tail = buf[o:]          # Jrose leaves 2-4 bytes after the last entry
        else:
            nlang, = struct.unpack_from("<I", buf, o)
            o += 4
            lang_off = struct.unpack_from("<%dI" % nlang, buf, o)
            o += 4 * nlang
            self.end = o
            # Several language slots may point at ONE block (LIST_STRING_S.STL:
            # five slots, one block). The groups are remembered so the writer
            # keeps the sharing -- and splits a group whose blocks were edited apart.
            self.lang_groups, first_at = [], {}
            for li, base in enumerate(lang_off):
                if base in first_at:
                    self.lang_groups[first_at[base]].append(li)
                else:
                    first_at[base] = len(self.lang_groups)
                    self.lang_groups.append([li])
            for base in lang_off:
                entry_off = struct.unpack_from("<%dI" % count, buf, base)
                rows = []
                for eo in entry_off:
                    fields, p = [], eo
                    for _ in range(self.nfields):
                        s, p = read_vstr(buf, p)
                        fields.append(s)
                    rows.append(fields)
                    self.end = max(self.end, p)
                self.langs.append(rows)
                self._block_end.append(p)
            self.tail = buf[self.end:]

    def _read_entries(self, buf, o, count):
        rows = []
        for _ in range(count):
            fields = []
            for _ in range(self.nfields):
                s, o = read_vstr(buf, o)
                fields.append(s)
            rows.append(fields)
        return rows, o

    # ------------------------------------------------------------ reading
    def _key(self, key):
        return key.encode("latin-1") if isinstance(key, str) else key

    def index(self, key):
        k = self._key(key)
        return next((i for i, (x, _) in enumerate(self.keys) if x == k), None)

    def has(self, key):
        return self.index(key) is not None

    def field(self, key, n=0, lang=0):
        """Field ``n`` of an entry as str; "" if the key is absent."""
        j = self.index(key)
        if j is None:
            return ""
        return self.langs[lang][j][n].decode(self.encoding, "replace")

    def name(self, key, lang=0):
        return self.field(key, 0, lang)

    def lang(self, index=0):
        """All entries of one language block as decoded tuples, in key order.

        Also sets ``end`` to where a sequential read of that block stops -- the
        client reads this way, ignoring the offset table.
        """
        if self.legacy:
            self.end = self._block_end[0]
        else:
            self.end = self._block_end[index]
        return [tuple(f.decode(self.encoding, "replace") for f in row)
                for row in self.langs[index]]

    def by_key(self, index=0):
        return {k.decode("latin-1"): v for (k, _), v in zip(self.keys, self.lang(index))}

    def by_id(self, index=0):
        return {i: v for (_, i), v in zip(self.keys, self.lang(index))}

    # ------------------------------------------------------------ writing
    def append(self, key, idx, name, *more):
        """Append one entry with the same text in every language block.

        ``more`` fills the following fields (description ...); the rest are
        blank. Strings are encoded with the table's encoding.
        """
        fields = [name] + list(more)
        if len(fields) > self.nfields:
            raise FormatError("%d fields for a %s entry" % (len(fields), self.fmt.decode()))
        fields = [f.encode(self.encoding) if isinstance(f, str) else f for f in fields]
        fields += [b""] * (self.nfields - len(fields))
        self.keys.append((self._key(key), idx))
        for rows in self.langs:
            rows.append(list(fields))
        self.count = len(self.keys)

    def set_name(self, key, name, lang=None):
        """Retitle an existing entry (every block, or one). False if absent.

        Only field 0 moves; a description in field 1 is left alone, and entry
        lengths are free to change because ``to_bytes`` rebuilds the offsets.
        """
        j = self.index(key)
        if j is None:
            return False
        n = name.encode(self.encoding) if isinstance(name, str) else name
        for li, rows in enumerate(self.langs):
            if lang is None or li == lang:
                rows[j][0] = n
        return True

    def set_field(self, key, n, value, lang=None):
        j = self.index(key)
        if j is None:
            return False
        v = value.encode(self.encoding) if isinstance(value, str) else value
        for li, rows in enumerate(self.langs):
            if lang is None or li == lang:
                rows[j][n] = v
        return True

    def remove(self, keys):
        """Drop entries by key (every language block). Returns how many went."""
        drop = {self._key(k) for k in keys}
        keep = [i for i, (k, _) in enumerate(self.keys) if k not in drop]
        gone = len(self.keys) - len(keep)
        self.keys = [self.keys[i] for i in keep]
        self.langs = [[rows[i] for i in keep] for rows in self.langs]
        self.count = len(self.keys)
        return gone

    def to_bytes(self):
        out = io.BytesIO()
        out.write(write_pstr8(self.fmt))
        out.write(struct.pack("<I", len(self.keys)))
        for k, i in self.keys:
            out.write(write_pstr8(k))
            out.write(struct.pack("<I", i))
        if self.legacy:
            for fields in self.langs[0]:
                for s in fields:
                    out.write(write_vstr(s))
            out.write(getattr(self, "tail", b""))
            return out.getvalue()
        out.write(struct.pack("<I", len(self.langs)))
        lang_off_pos = out.tell()
        out.write(b"\0" * (4 * len(self.langs)))
        lang_offsets = [0] * len(self.langs)
        for group in self._write_groups():
            block_at = out.tell()
            for li in group:
                lang_offsets[li] = block_at
            rows = self.langs[group[0]]
            entry_off_pos = out.tell()
            out.write(b"\0" * (4 * len(self.keys)))
            entry_offsets = []
            for fields in rows:
                entry_offsets.append(out.tell())
                for s in fields:
                    out.write(write_vstr(s))
            end = out.tell()
            out.seek(entry_off_pos)
            out.write(struct.pack("<%dI" % len(self.keys), *entry_offsets))
            out.seek(end)
        end = out.tell()
        out.seek(lang_off_pos)
        out.write(struct.pack("<%dI" % len(self.langs), *lang_offsets))
        out.seek(end)
        out.write(getattr(self, "tail", b""))
        return out.getvalue()

    def _write_groups(self):
        """Language slots that share one block, in write order. A group read as
        shared stays shared only while its blocks are still equal."""
        groups = getattr(self, "lang_groups", None) or [[i] for i in range(len(self.langs))]
        out = []
        for g in groups:
            head = [g[0]]
            for li in g[1:]:
                if self.langs[li] == self.langs[g[0]]:
                    head.append(li)
                else:
                    out.append([li])
            out.append(head)
        out.sort(key=lambda g: g[0])      # blocks in first-slot order
        return out

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


def stl_by_key(path, encoding="latin-1", index=0):
    return Stl(path, encoding).by_key(index)


# ------------------------------------------------- functional view (import-item)
def read_table(path):
    """(keys, langs) with ``langs[lang][entry]`` a tuple of field bytes."""
    t = Stl(path)
    return list(t.keys), [[tuple(row) for row in rows] for rows in t.langs]


def write_table(path, keys, langs, dry, fmt=b"ITST01"):
    """Serialise a whole modern table from the ``read_table`` shape.

    Every per-language entry is written at a fresh offset, so this is also how
    entries get *removed* -- the offset table is rebuilt rather than patched.
    """
    t = Stl.__new__(Stl)
    t.path, t.encoding, t.fmt, t.tag = path, "latin-1", fmt, fmt
    t.nfields, t.legacy = FIELDS[fmt], False
    t.keys = list(keys)
    t.langs = [[list(row) for row in rows] for rows in langs]
    t.count = len(t.keys)
    blob = t.to_bytes()
    if not dry:
        with open(path, "wb") as fh:
            fh.write(blob)
    return blob
