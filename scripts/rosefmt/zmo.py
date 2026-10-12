"""ZMO motion clips: the header and the action-frame event trailer (read side).

Header: ``"ZMO0002\\0" | u32 fps | u32 frame_count | u32 channel_count``, then
per channel ``u32 type | u32 bone`` and the frame data. Writing a full clip is
``import-glb-weapon.py``'s ``write_zmo`` (node-rotation clips only); this module
reads the header and edits the trailer.

Trailer (``EZMO`` / ``3ZMO``): ``... body ... | u16 n | n x i16 event-per-frame
| u32 trailer_offset | "EZMO"``. The events are what makes a clip *do*
something: a normal attack lands at frame 21 (melee) or fires at 22/23
(bow/gun); a skill release launches at 24/34 (or 26/25). **A bare-handed
monster on a 22/23 clip has nothing to fire** and used to deal damage with no
digit (``scripts/fix-zmo-attack-frames.py``). The server decrements the frame
count by one when it times a swing.
"""
import struct

from .binio import read_cstr, read_file

MAGIC = b"ZMO0002"
TRAILER_TAGS = (b"EZMO", b"3ZMO")


def read_header(blob):
    """(fps, frames, channels=[(type, bone)]) or None for a non-ZMO file."""
    b = read_file(blob)
    magic, o = read_cstr(b, 0)
    if magic != MAGIC:
        return None
    fps, frames, nchan = struct.unpack_from("<III", b, o)
    o += 12
    chans = [struct.unpack_from("<II", b, o + 8 * i) for i in range(nchan)]
    return fps, frames, chans


def events(blob):
    """(offset_of_first_event, [event per frame]) or (None, None) without a trailer."""
    b = read_file(blob)
    if len(b) < 8 or b[-4:] not in TRAILER_TAGS:
        return None, None
    off, = struct.unpack_from("<I", b, len(b) - 8)
    if not (0 <= off < len(b) - 2):
        return None, None
    n, = struct.unpack_from("<H", b, off)
    if off + 2 + 2 * n > len(b):
        return None, None
    return off + 2, list(struct.unpack_from("<%dh" % n, b, off + 2))


def event_set(blob):
    """The set of non-zero event ids a clip carries; empty without a trailer."""
    _, ev = events(blob)
    return {e for e in ev if e} if ev else set()


def with_events(blob, changes):
    """The clip's bytes with ``{frame: event}`` written into its trailer."""
    b = read_file(blob)
    base, ev = events(b)
    if base is None:
        raise ValueError("clip has no frame-event trailer")
    out = bytearray(b)
    for frame, event in changes.items():
        if not 0 <= frame < len(ev):
            raise ValueError("frame %d past the trailer (%d frames)" % (frame, len(ev)))
        struct.pack_into("<h", out, base + 2 * frame, event)
    return bytes(out)
