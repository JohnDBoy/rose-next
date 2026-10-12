"""TSI sprite atlases (``ITEM1.TSI``, ``SKILLICON.TSI``, ``TARGETMARK.TSI`` ...).

Layout::

    i16 texture_count
    per texture: i16 name_len | name (NUL-terminated inside) | u32 colour key
    i16 sprite_total
    per texture: i16 count | count x 54-byte sprite
    sprite: i16 texid | i32 x1 y1 x2 y2 | u32 colour | char[32] label

An STB icon column holds the **flat** sprite index -- the position across all
blocks in order -- so a sprite must never move between blocks; its *texture* is
read per sprite. ``ITEM1.TSI`` is 50 sheets x 169 cells (0-8449), extension
sheets ``icon51.dds`` + continue from 8450. The two atlases use different rect
conventions: item cells are ``x..x+40``, skill cells ``x..x+39``; a writer
matches its atlas (``sprite_entry`` takes the rect verbatim).

``sprite_total`` is a real safety net on **our** atlases, where it is written
back, but 667's ``ITEM1.TSI`` declares 540 while its blocks hold 9295 and the
blocks still consume the file exactly -- read a foreign atlas with
``strict=False``. A sheet is 512 px: the last row and column of a 13 x 13 grid of
40 px cells do not fit, and the engine clips a sprite at the sheet edge.

Round-trips byte for byte.
"""
import io
import struct

from .binio import read_file

SPRITE = 54


def read(path, strict=True):
    """(textures, blocks): textures = [(name, raw_entry)], blocks = [(count, raw)]."""
    f = io.BytesIO(read_file(path))
    ntex, = struct.unpack("<h", f.read(2))
    textures = []
    for _ in range(ntex):
        start = f.tell()
        nlen, = struct.unpack("<h", f.read(2))
        name = f.read(nlen).split(b"\x00")[0].decode("ascii")
        f.read(4)  # colour key
        f.seek(start)
        raw = f.read(2 + nlen + 4)
        textures.append((name, raw))
    total, = struct.unpack("<h", f.read(2))
    blocks = []
    for _ in range(ntex):
        cnt, = struct.unpack("<h", f.read(2))
        blocks.append((cnt, f.read(cnt * SPRITE)))
    rest = f.read()
    if rest:
        raise ValueError("trailing bytes in TSI")
    if strict and total != sum(c for c, _ in blocks):
        raise ValueError("TSI sprite count mismatch")
    return textures, blocks


def declared_total(path):
    """The header's sprite total as written (retail Ui.TSI says 690 for 688)."""
    b = read_file(path)
    o = 2
    ntex, = struct.unpack_from("<h", b, 0)
    for _ in range(ntex):
        nlen, = struct.unpack_from("<h", b, o)
        o += 2 + nlen + 4
    return struct.unpack_from("<h", b, o)[0]


def build(textures, blocks, total=None):
    """``total`` defaults to the real sprite count; pass ``declared_total(path)``
    to keep a foreign atlas's (wrong) header value on a byte-exact rewrite."""
    if len(textures) != len(blocks):
        raise ValueError("TSI: %d textures, %d blocks" % (len(textures), len(blocks)))
    out = [struct.pack("<h", len(textures))]
    out += [raw for _, raw in textures]
    out.append(struct.pack("<h", sum(c for c, _ in blocks) if total is None else total))
    for cnt, raw in blocks:
        out.append(struct.pack("<h", cnt))
        out.append(raw)
    return b"".join(out)


def write(path, textures, blocks, dry):
    blob = build(textures, blocks)
    if not dry:
        with open(path, "wb") as fh:
            fh.write(blob)
    return blob


def texture_entry(name):
    nb = name.encode("ascii") + b"\x00"
    return (name, struct.pack("<h", len(nb)) + nb + struct.pack("<I", 0))


def sprite_entry(texid, x1, y1, x2, y2, label, colour=0):
    sid = label.encode("ascii", "replace")[:31].ljust(32, b"\x00")
    return struct.pack("<h4iI", texid, x1, y1, x2, y2, colour) + sid


def iter_sprites(blocks):
    """Yield (flat_index, block_index, slot, texid, x1, y1, x2, y2)."""
    flat = 0
    for bi, (cnt, raw) in enumerate(blocks):
        for i in range(cnt):
            ent = raw[i * SPRITE:(i + 1) * SPRITE]
            texid, x1, y1, x2, y2 = struct.unpack_from("<h4i", ent, 0)
            yield flat, bi, i, texid, x1, y1, x2, y2
            flat += 1


def sprites(path, strict=False):
    """(texture names, [(texid, x1, y1, x2, y2)] in flat index order)."""
    textures, blocks = read(path, strict=strict)
    return ([n for n, _ in textures],
            [(t, x1, y1, x2, y2) for _f, _b, _s, t, x1, y1, x2, y2 in iter_sprites(blocks)])


tsi_read, tsi_write, tsi_sprites = read, write, sprites
