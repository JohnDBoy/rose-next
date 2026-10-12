"""CHR character tables (``LIST_NPC.CHR``): skeleton, parts, motions per NPC.

Layout::

    u16 n + NUL-terminated skeleton paths | same for motions | same for effects
    u16 char_count, then per character:
        u8 active (0 = hole, nothing follows)
        u16 skeleton | NUL-terminated name
        u16 n + n x u16 PART_NPC.ZSC model index
        u16 n + n x (u16 anim type, u16 motion index)
        u16 n + n x (u16 anim type, u16 effect index)

The file carries ~2 KB past the declared character count -- dead entries the
client never reads. It is preserved verbatim (``tail``).

A hole (``None``) is a row with no model: the Basilisk Captain (372) was one in
most dumps while Luna spawned it at 31 points. Monster casts play slot
``nMotion`` to cast and ``nMotion+1`` to release; only the release clip's action
frames land the skill (doc/making-monsters.md). **The server loads this file
too**: restart it as well as baking.

Round-trips byte for byte.
"""
import io
import struct

from .binio import read_file
from .stb import backup


class Chr:
    def __init__(self, path):
        self.path = path if not isinstance(path, (bytes, bytearray)) else None
        self.d = read_file(path)
        f = self.f = io.BytesIO(self.d)
        self.skeletons = [self.cstr() for _ in range(self.u16())]
        self.motions = [self.cstr() for _ in range(self.u16())]
        self.effects = [self.cstr() for _ in range(self.u16())]
        self.chars = []
        for _ in range(self.u16()):
            if not f.read(1)[0]:
                self.chars.append(None)
                continue
            skel = self.u16()
            name = self.cstr()
            models = [self.u16() for _ in range(self.u16())]
            anims = [(self.u16(), self.u16()) for _ in range(self.u16())]
            effs = [(self.u16(), self.u16()) for _ in range(self.u16())]
            self.chars.append(dict(skel=skel, name=name, models=models,
                                   anims=anims, effects=effs))
        self.tail = f.read()

    def u16(self):
        return struct.unpack("<H", self.f.read(2))[0]

    def cstr(self):
        out = b""
        while True:
            c = self.f.read(1)
            if c in (b"\x00", b""):
                break
            out += c
        return out

    def to_bytes(self):
        out = io.BytesIO()

        def strlist(items):
            out.write(struct.pack("<H", len(items)))
            for s in items:
                out.write(s + b"\x00")

        strlist(self.skeletons)
        strlist(self.motions)
        strlist(self.effects)
        out.write(struct.pack("<H", len(self.chars)))
        for c in self.chars:
            if c is None:
                out.write(b"\x00")
                continue
            out.write(b"\x01")
            out.write(struct.pack("<H", c["skel"]))
            out.write(c["name"] + b"\x00")
            out.write(struct.pack("<H", len(c["models"])))
            for m in c["models"]:
                out.write(struct.pack("<H", m))
            out.write(struct.pack("<H", len(c["anims"])))
            for t, a in c["anims"]:
                out.write(struct.pack("<HH", t, a))
            out.write(struct.pack("<H", len(c["effects"])))
            for t, e in c["effects"]:
                out.write(struct.pack("<HH", t, e))
        out.write(self.tail)
        return out.getvalue()

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
