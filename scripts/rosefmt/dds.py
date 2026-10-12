"""DDS textures: the 128-byte header (plus the DX10 block), and uncompressed BGRA sheets.

Header (``DDS_HEADER``, little-endian)::

    "DDS " | u32 size=124 | u32 flags | u32 height | u32 width | u32 pitch
    | u32 depth | u32 mip_count | 11 x u32 reserved
    pixel format: u32 size=32 | u32 pf_flags | 4s fourcc | u32 bit_count
                  | u32 r_mask | u32 g_mask | u32 b_mask | u32 a_mask
    u32 caps | u32 caps2 | u32 caps3 | u32 caps4 | u32 reserved
    (fourcc "DX10": 20 more bytes -- dxgi_format, dimension, misc, array, misc2)

``mip_count`` means nothing unless ``DDSD_MIPMAPCOUNT`` is set in ``flags``
(``Header.mips`` applies that rule). The engine caps every texture at three
mip levels (``setMipmapLevel(3)`` in INIT.LUA), which is what keeps
gutterless lightmap atlases from bleeding; the vendored texconv must be run
with ``-dx9`` or it writes a DX10 header the engine does not read.

Pixel data is not decoded here except for the **uncompressed 32-bit BGRA**
sheets the icon tools write (``read_bgra`` / ``write_bgra``, top mip only;
PIL imported on use). Compressed encoding is a tool, not a codec:
``mapgen.lighting.encode_dds`` / ``make-minimap.py`` drive texconv.

``parse_header`` / ``build_header`` round-trip the header bytes of every DDS
we ship; the pixel payload is carried through untouched by ``split``/``join``.
"""
import struct
from dataclasses import dataclass, field
from typing import Optional

from .binio import FormatError, read_file

MAGIC = b"DDS "
HEADER_LEN = 128
DX10_LEN = 20

DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH, DDSD_PITCH = 0x1, 0x2, 0x4, 0x8
DDSD_PIXELFORMAT, DDSD_MIPMAPCOUNT, DDSD_LINEARSIZE, DDSD_DEPTH = 0x1000, 0x20000, 0x80000, 0x800000
DDPF_ALPHAPIXELS, DDPF_FOURCC, DDPF_RGB = 0x1, 0x4, 0x40
DDSCAPS_TEXTURE, DDSCAPS_MIPMAP, DDSCAPS_COMPLEX = 0x1000, 0x400000, 0x8
DDSCAPS2_CUBEMAP, DDSCAPS2_VOLUME = 0x200, 0x200000


@dataclass
class Header:
    flags: int = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    height: int = 0
    width: int = 0
    pitch: int = 0
    depth: int = 0
    mip_count: int = 0
    reserved: tuple = (0,) * 11
    pf_flags: int = 0
    fourcc: bytes = b"\0\0\0\0"
    bit_count: int = 0
    r_mask: int = 0
    g_mask: int = 0
    b_mask: int = 0
    a_mask: int = 0
    caps: int = DDSCAPS_TEXTURE
    caps2: int = 0
    caps3: int = 0
    caps4: int = 0
    reserved2: int = 0
    dx10: Optional[bytes] = None      # the 20-byte DX10 block, verbatim

    @property
    def mips(self):
        """Mip levels as the loader understands them: the count only when flagged."""
        return self.mip_count if (self.flags & DDSD_MIPMAPCOUNT) else 0

    @property
    def is_dx10(self):
        return self.fourcc == b"DX10"

    @property
    def payload_offset(self):
        return HEADER_LEN + (DX10_LEN if self.is_dx10 else 0)

    @property
    def compressed(self):
        return bool(self.pf_flags & DDPF_FOURCC)


_FMT = "<4sIIIIIII11IIIIIIIIIIIIII"


def parse_header(path_or_blob):
    b = read_file(path_or_blob)
    if len(b) < HEADER_LEN or b[:4] != MAGIC:
        raise FormatError("not a DDS file")
    v = struct.unpack_from("<4sIIIIIII11I", b, 0)
    size = v[1]
    if size != 124:
        raise FormatError("DDS header size %d, expected 124" % size)
    h = Header(flags=v[2], height=v[3], width=v[4], pitch=v[5], depth=v[6], mip_count=v[7],
               reserved=tuple(v[8:19]))
    pf = struct.unpack_from("<II4sIIIII", b, 76)
    if pf[0] != 32:
        raise FormatError("DDS pixel-format size %d, expected 32" % pf[0])
    h.pf_flags, h.fourcc, h.bit_count = pf[1], pf[2], pf[3]
    h.r_mask, h.g_mask, h.b_mask, h.a_mask = pf[4:8]
    h.caps, h.caps2, h.caps3, h.caps4, h.reserved2 = struct.unpack_from("<5I", b, 108)
    if h.is_dx10:
        if len(b) < HEADER_LEN + DX10_LEN:
            raise FormatError("DX10 DDS truncated")
        h.dx10 = bytes(b[HEADER_LEN:HEADER_LEN + DX10_LEN])
    return h


def build_header(h):
    out = struct.pack("<4sIIIIIII11I", MAGIC, 124, h.flags, h.height, h.width, h.pitch,
                      h.depth, h.mip_count, *h.reserved)
    out += struct.pack("<II4sIIIII", 32, h.pf_flags, h.fourcc, h.bit_count,
                       h.r_mask, h.g_mask, h.b_mask, h.a_mask)
    out += struct.pack("<5I", h.caps, h.caps2, h.caps3, h.caps4, h.reserved2)
    if h.is_dx10:
        out += h.dx10 or b"\0" * DX10_LEN
    return out


def split(path_or_blob):
    """(Header, payload bytes)."""
    b = read_file(path_or_blob)
    h = parse_header(b)
    return h, b[h.payload_offset:]


def join(h, payload):
    return build_header(h) + payload


def _head(path_or_blob):
    """The first 148 bytes: enough for any header, without reading the pixels."""
    if isinstance(path_or_blob, (bytes, bytearray, memoryview)):
        return bytes(path_or_blob[:HEADER_LEN + DX10_LEN])
    with open(path_or_blob, "rb") as fh:
        return fh.read(HEADER_LEN + DX10_LEN)


def header(path_or_blob):
    """``parse_header`` from the first bytes only; None when not a DDS."""
    try:
        return parse_header(_head(path_or_blob))
    except (FormatError, OSError):
        return None


def info(path_or_blob):
    """(width, height, raw mip count, fourcc as str) -- what lighting.dds_info gave."""
    h = parse_header(_head(path_or_blob))
    return h.width, h.height, h.mip_count, h.fourcc.decode("latin-1")


def side(path_or_blob):
    """(width, height), or None for a file that is not a DDS."""
    h = header(path_or_blob)
    return None if h is None else (h.width, h.height)


# ------------------------------------------------- uncompressed BGRA sheets
def bgra_header(width, height, mips=0):
    """The header the icon tools write: 32-bit BGRA, no chain unless ``mips``."""
    h = Header(flags=DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT,
               height=height, width=width, pitch=width * 4, mip_count=mips,
               pf_flags=DDPF_RGB | DDPF_ALPHAPIXELS, bit_count=32,
               r_mask=0x00FF0000, g_mask=0x0000FF00, b_mask=0x000000FF, a_mask=0xFF000000,
               caps=DDSCAPS_TEXTURE)
    if mips:
        h.flags |= DDSD_MIPMAPCOUNT
        h.caps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX
    return h


def read_bgra(path_or_blob, size=None):
    """The top mip of an uncompressed 32-bit BGRA DDS as a PIL RGBA image.

    Validates from the header, not the file length: a sheet that
    ``add-dds-mipmaps.py`` gave a chain is longer than one level, and the extra
    levels are simply ignored. ``size`` = (w, h) refuses any other dimensions.
    """
    from PIL import Image
    b = read_file(path_or_blob)
    h = parse_header(b)
    if h.bit_count != 32 or not (h.pf_flags & (DDPF_RGB | DDPF_ALPHAPIXELS)) or h.compressed:
        raise FormatError("not an uncompressed 32-bit BGRA DDS (fourcc %r, %d bpp)"
                          % (h.fourcc, h.bit_count))
    if size is not None and (h.width, h.height) != tuple(size):
        raise FormatError("DDS is %dx%d, wanted %dx%d" % (h.width, h.height, size[0], size[1]))
    top = h.width * h.height * 4
    if len(b) < h.payload_offset + top:
        raise FormatError("DDS payload truncated")
    bgra = Image.frombytes("RGBA", (h.width, h.height), b[h.payload_offset:h.payload_offset + top])
    c0, c1, c2, c3 = bgra.split()        # file bytes are B,G,R,A -> swap back
    return Image.merge("RGBA", (c2, c1, c0, c3))


def bgra_bytes(img):
    """An RGBA PIL image as the header + BGRA top-mip bytes (no chain)."""
    from PIL import Image
    img = img.convert("RGBA")
    b, g, r, a = (img.getchannel(c) for c in ("B", "G", "R", "A"))
    return build_header(bgra_header(img.width, img.height)) + Image.merge("RGBA", (b, g, r, a)).tobytes()


def write_bgra(path, img, dry=False):
    blob = bgra_bytes(img)
    if not dry:
        with open(path, "wb") as fh:
            fh.write(blob)
    return blob
