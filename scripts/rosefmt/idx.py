"""VFS index (``data.idx``): the file table of the client's ``rose*.vfs`` archives.

Mirrors roselib's ``VfsIndex::write``: ``i32 base_version | i32 current_version
| i32 filesystem_count`` then per filesystem a ``pstr16 name`` and a reserved
i32 backfilled with the absolute offset of that filesystem's table. A table is
``i32 count | i32 deleted | i32 first_offset`` then per file::

    pstr16 name | u32 offset | u32 size | u32 block_size
    | u8 deleted, compressed, encrypted | i32 version | i32 checksum

**The offset is unsigned.** ``FileEntry::lFileOffset`` in triggervfs was a
signed ``long`` until 2026-08-29, so a file stored past 2 GB got a negative
offset and the client read noise (the symptom was ``SCRIPTS\\INIT.LUA`` failing
to parse). An archive still cannot exceed 4 GB; the packer rolls over to
``rose_2.vfs`` at 4.2 GB and every ``rose*.vfs`` must ship with the index.
Read-only: ``pipeline.exe`` writes the index.

**A head's table offset can be stale.** The tables sit back to back, but EVO's
``data.idx`` (their launcher's TSVFS writes it) points ROOT.VFS's head into the
middle of MAP.VFS's table; the client never notices because the real table
follows BASIC.VFS's. A table offset that lands inside an already-read table is
taken as "right after the previous one".

``read_files`` pulls named files out of the archives next to an index: classic
TriggerVFS archives store them raw at the indexed offset.
"""
import os
import struct

from .binio import read_file


class IdxError(Exception):
    pass


class Reader(object):
    """Little-endian cursor over the .idx bytes."""

    def __init__(self, data):
        self.d = data
        self.o = 0

    def i32(self):
        if self.o + 4 > len(self.d):
            raise IdxError("truncated .idx: wanted 4 bytes at %d" % self.o)
        v = struct.unpack_from("<i", self.d, self.o)[0]
        self.o += 4
        return v

    def u32(self):
        if self.o + 4 > len(self.d):
            raise IdxError("truncated .idx: wanted 4 bytes at %d" % self.o)
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def str16(self):
        if self.o + 2 > len(self.d):
            raise IdxError("truncated .idx: wanted a string length at %d" % self.o)
        n = struct.unpack_from("<H", self.d, self.o)[0]
        self.o += 2
        if self.o + n > len(self.d):
            raise IdxError("truncated .idx: wanted %d string bytes at %d" % (n, self.o))
        s = self.d[self.o:self.o + n].decode("latin-1")
        self.o += n
        return s


def parse(path_or_blob):
    """[(archive_name, [(name, offset, size), ...]), ...]."""
    r = Reader(read_file(path_or_blob))
    r.i32()  # base_version
    r.i32()  # current_version
    nfs = r.i32()
    if not (0 < nfs < 10000):
        raise IdxError("implausible filesystem count %d -- is this a data.idx?" % nfs)
    heads = []
    for _ in range(nfs):
        heads.append((r.str16(), r.i32()))
    out = []
    prev_end = None
    for name, table_off in heads:
        if prev_end is not None and table_off < prev_end:
            table_off = prev_end   # stale head offset: see the module docstring
        r.o = table_off
        count = r.i32()
        r.i32()  # deleted count
        r.i32()  # first offset (informational)
        files = []
        for _ in range(count):
            fn = r.str16()
            off = r.u32()    # UNSIGNED: see the module docstring
            size = r.u32()
            r.u32()          # block size
            r.o += 3         # deleted, compressed, encrypted
            r.i32()          # version
            r.i32()          # checksum
            files.append((fn, off, size))
        out.append((name, files))
        prev_end = r.o
    return out


parse_idx = parse


def read_files(idx_path, names):
    """{name: bytes} for ``names`` (VFS paths, any case and slash) found in the
    archives beside ``idx_path``; names not in the index are left out."""
    def key(n):
        return n.replace("/", "\\").rstrip("\0").upper()
    want = {key(n): n for n in names}
    out = {}
    folder = os.path.dirname(os.path.abspath(idx_path))
    for arc, files in parse(idx_path):
        hits = [(want[key(fn)], off, size) for fn, off, size in files if key(fn) in want]
        if not hits:
            continue
        with open(os.path.join(folder, arc.rstrip("\0").strip()), "rb") as fh:
            for n, off, size in hits:
                fh.seek(off)
                out[n] = fh.read(size)
    return out
