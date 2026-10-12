"""Byte-level primitives shared by the codecs: the string encodings ROSE uses.

ROSE files mix four string shapes, and reading one as another is the classic
silent failure (an IFO event-object trigger read as u8 under-consumes the lump):

* ``pstr16``  -- u16 length + bytes (STB cells and labels, QSD strings as i16)
* ``pstr8``   -- u8 length + bytes (IFO object names, TSI, STL keys and tag)
* ``vstr``    -- 7-bit varint length + bytes (STL entries, IFO event objects)
* ``cstr``    -- NUL-terminated (ZSC paths, CHR names, ZMO magic)
"""
import struct


class FormatError(ValueError):
    """The bytes are not the format the codec was asked for."""


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
