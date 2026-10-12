"""Byte-level primitives shared by every codec: ROSE's string shapes and a cursor.

ROSE files mix four string shapes, and reading one as another is the classic
silent failure (an IFO event-object trigger read as u8 under-consumes the lump):

* ``pstr16``  -- u16 length + bytes (STB cells and labels, QSD strings as i16)
* ``pstr8``/``bstr`` -- u8 length + bytes (IFO object names, TSI, STL keys and tag)
* ``vstr``/``pstr`` -- 7-bit varint length + bytes (STL entries, IFO event objects;
  the client's ReadPascalString, cfilesystemtriggervfs.cpp:326-356: 1 byte below
  0x80, else ``(len & 0x7f) | 0x80, len >> 7`` -- LEB128 below 16384)
* ``cstr``    -- NUL-terminated (ZSC paths, CHR names, ZMO magic)

Strings stay ``bytes`` end to end. Game files are EUC-KR/CP949 (CP932 in
Jrose-origin data) and decoding then re-encoding is lossy for bytes invalid in
the guessed code page, which would break byte-exact round-trips. Decode only
for display.

``Reader`` / ``Writer`` are the little-endian cursors the map codecs use
(moved from ``mapgen/binio.py`` on 2026-10-12); the functions below are the
offset-based form the table codecs use. Both raise ``FormatError`` on overrun.
"""
import struct


class FormatError(ValueError):
    """The bytes are not the format the codec was asked for."""


# ----------------------------------------------------------- offset-based
def read_pstr16(buf, o):
    n, = struct.unpack_from("<H", buf, o)
    o += 2
    return buf[o:o + n], o + n


def write_pstr16(s):
    return struct.pack("<H", len(s)) + s


def read_pstr8(buf, o):
    n = buf[o]
    o += 1
    return buf[o:o + n], o + n


def write_pstr8(s):
    if len(s) > 255:
        raise FormatError("pascal string too long: %d" % len(s))
    return bytes([len(s)]) + s


def read_varint(buf, o):
    n, shift = 0, 0
    while True:
        c = buf[o]
        o += 1
        n |= (c & 0x7F) << shift
        if not (c & 0x80):
            return n, o
        shift += 7


def write_varint(n):
    out = b""
    while n > 0x7F:
        out += bytes([(n & 0x7F) | 0x80])
        n >>= 7
    return out + bytes([n])


def read_vstr(buf, o):
    n, o = read_varint(buf, o)
    return buf[o:o + n], o + n


def write_vstr(s):
    return write_varint(len(s)) + s


def read_cstr(buf, o):
    end = buf.find(b"\x00", o)
    if end < 0:
        return buf[o:], len(buf)
    return buf[o:end], end + 1


def write_cstr(s):
    return s + b"\x00"


def read_file(path_or_bytes):
    """Accept a path or an in-memory blob; every codec constructor does."""
    if isinstance(path_or_bytes, (bytes, bytearray, memoryview)):
        return bytes(path_or_bytes)
    with open(path_or_bytes, "rb") as fh:
        return fh.read()


def as_bytes(v, encoding="latin-1"):
    return v.encode(encoding) if isinstance(v, str) else v


# ------------------------------------------------------------------ cursors
class Reader:
    def __init__(self, data, pos=0, end=None):
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def remaining(self):
        return self.end - self.pos

    def _take(self, n):
        if n < 0 or self.pos + n > self.end:
            raise FormatError("read of %d bytes at %d overruns end %d" % (n, self.pos, self.end))
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def raw(self, n):
        return bytes(self._take(n))

    def rest(self):
        return self.raw(self.end - self.pos)

    def u8(self):
        return self._take(1)[0]

    def u16(self):
        return struct.unpack("<H", self._take(2))[0]

    def i16(self):
        return struct.unpack("<h", self._take(2))[0]

    def i32(self):
        return struct.unpack("<i", self._take(4))[0]

    def u32(self):
        return struct.unpack("<I", self._take(4))[0]

    def f32(self):
        return struct.unpack("<f", self._take(4))[0]

    def f32s(self, n):
        return struct.unpack("<%df" % n, self._take(4 * n))

    def i32s(self, n):
        return struct.unpack("<%di" % n, self._take(4 * n))

    def bstr(self):
        return self.raw(self.u8())

    def pstr(self):
        first = self.u8()
        if first & 0x80:
            n = (self.u8() << 7) | (first - 0x80)
        else:
            n = first
        return self.raw(n)

    def cstr(self):
        s, o = read_cstr(self.data, self.pos)
        if o > self.end:
            raise FormatError("cstr at %d runs past end %d" % (self.pos, self.end))
        self.pos = o
        return bytes(s)

    def array(self, dtype, count):
        """numpy array straight from the bytes: float bit patterns survive exactly."""
        import numpy as np
        dt = np.dtype(dtype)
        b = self._take(dt.itemsize * count)
        return np.frombuffer(b, dtype=dt, count=count).copy()


class Writer:
    def __init__(self):
        self.buf = bytearray()

    def tell(self):
        return len(self.buf)

    def getvalue(self):
        return bytes(self.buf)

    def raw(self, b):
        self.buf += b

    def u8(self, v):
        self.buf += struct.pack("<B", v)

    def u16(self, v):
        self.buf += struct.pack("<H", v)

    def i16(self, v):
        self.buf += struct.pack("<h", v)

    def i32(self, v):
        self.buf += struct.pack("<i", v)

    def u32(self, v):
        self.buf += struct.pack("<I", v)

    def f32(self, v):
        self.buf += struct.pack("<f", v)

    def f32s(self, vs):
        self.buf += struct.pack("<%df" % len(vs), *vs)

    def i32s(self, vs):
        self.buf += struct.pack("<%di" % len(vs), *vs)

    def bstr(self, b):
        if len(b) > 0xFF:
            raise FormatError("bstr longer than 255 bytes: %d" % len(b))
        self.u8(len(b))
        self.buf += b

    def pstr(self, b):
        n = len(b)
        if n < 0x80:
            self.u8(n)
        elif n < 0x8000:
            self.u8((n & 0x7F) | 0x80)
            self.u8(n >> 7)
        else:
            raise FormatError("pstr longer than 32767 bytes: %d" % n)
        self.buf += b

    def cstr(self, b):
        self.buf += b + b"\x00"

    def array(self, arr):
        import numpy as np
        self.buf += np.ascontiguousarray(arr).tobytes()
