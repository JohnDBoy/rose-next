""".eft effects (``3DDATA/EFFECT/*.eft``): particle systems and animated meshes.

Layout (``CEffectDATA::Load``, ``src/client/io_effect.cpp``); strings are
``i32 len | bytes``::

    str name | i32 use_sound | str sound | i32 sound_loops
    i32 particle_count, per particle:
        str name | str unique | i32 stb_index | str ptl | i32 use_ani | str ani
        i32 ani_loops | i32 ani_stb_index | f32 pos[3] | f32 rot[4] | i32 delay | i32 link
    i32 mesh_count, per mesh:
        str name | str unique | i32 stb_index | str zms | str zmo | str texture
        i32 alpha, two_side, alpha_test, z_test, z_write, blend_src, blend_dest, blend_op
        i32 use_ani | str ani | i32 ani_loops | i32 ani_stb_index
        f32 pos[3] | f32 rot[4] | i32 delay | i32 repeat | i32 link

Things that matter when editing one:

* **A flat mesh on the ground needs ``z_test`` 0.** With the depth test on, a decal
  at terrain height fights the terrain for the same depth and flickers. Our area
  spells' rune circle (``_SCOPE_02.ZMS`` in ``_runaston_01/02``) has it off; Jrose's
  Star Gazer copy (``_runaston_03_yellow_green``) had it on (2026-10-18).
* Blend values are D3DBLEND (5/2 = SRCALPHA/ONE, additive with alpha).
* Rotations are stored as yaw/pitch/roll degrees in the first three floats, not
  a quaternion, despite the four slots.

``read`` keeps every field, ``build`` writes it back byte for byte (604 of the 605 shipped
effects; ``rainbow01.eft`` is truncated), and ``with_mesh_flags`` patches the render flags
in place. A new effect is a ``read``-shaped dict -- see ``build``.
"""
import struct

from .binio import FormatError, read_file

MESH_FLAGS = ("alpha", "two_side", "alpha_test", "z_test", "z_write",
              "blend_src", "blend_dest", "blend_op")


def _str(b, o):
    if o + 4 > len(b):
        raise FormatError("truncated string length at %d" % o)
    n, = struct.unpack_from("<i", b, o)
    o += 4
    if n < 0 or o + n > len(b):
        raise FormatError("bad string length %d at %d" % (n, o - 4))
    return b[o:o + n].decode("latin-1"), o + n


def _ints(b, o, n):
    return list(struct.unpack_from("<%di" % n, b, o)), o + 4 * n


def read(blob):
    """{name, sound, particles: [{ptl, ani, pos, delay}], meshes: [{zms, zmo, texture,
    flags: {...}, flags_offset, pos, delay, repeat}], trailing}; raises FormatError on a
    truncated file. Bytes past the last mesh are counted, not refused: the client stops
    reading there, and 3 of the 605 effects we ship carry some (``rainbow01.eft`` is the
    one truncated file)."""
    try:
        return _read(read_file(blob))
    except struct.error as e:
        raise FormatError("truncated effect: %s" % e)


def _read(b):
    name, o = _str(b, 0)
    (use_sound,), o = _ints(b, o, 1)
    sound, o = _str(b, o)
    (sound_loops, count), o = _ints(b, o, 2)
    particles = []
    for _ in range(count):
        q = {}
        q["label"], o = _str(b, o)
        q["unique"], o = _str(b, o)
        (q["stb_index"],), o = _ints(b, o, 1)
        q["ptl"], o = _str(b, o)
        (q["use_ani"],), o = _ints(b, o, 1)
        q["ani_name"], o = _str(b, o)
        (q["ani_loops"], q["ani_stb_index"]), o = _ints(b, o, 2)
        q["pos"] = struct.unpack_from("<3f", b, o)
        q["rot"] = struct.unpack_from("<4f", b, o + 12)
        o += 28
        (q["delay"], q["link"]), o = _ints(b, o, 2)
        q["ani"] = q["ani_name"] if q["use_ani"] else ""
        particles.append(q)
    (count,), o = _ints(b, o, 1)
    meshes = []
    for _ in range(count):
        m = {}
        m["label"], o = _str(b, o)
        m["unique"], o = _str(b, o)
        (m["stb_index"],), o = _ints(b, o, 1)
        m["zms"], o = _str(b, o)
        m["zmo"], o = _str(b, o)
        m["texture"], o = _str(b, o)
        m["flags_offset"] = o
        flags, o = _ints(b, o, len(MESH_FLAGS))
        m["flags"] = dict(zip(MESH_FLAGS, flags))
        (m["use_ani"],), o = _ints(b, o, 1)
        m["ani_name"], o = _str(b, o)
        (m["ani_loops"], m["ani_stb_index"]), o = _ints(b, o, 2)
        m["pos"] = struct.unpack_from("<3f", b, o)
        m["rot"] = struct.unpack_from("<4f", b, o + 12)
        o += 28
        (m["delay"], m["repeat"], m["link"]), o = _ints(b, o, 3)
        m["ani"] = m["ani_name"] if m["use_ani"] else ""
        meshes.append(m)
    return dict(name=name, use_sound=use_sound, sound_name=sound,
                sound=sound if use_sound else "", sound_loops=sound_loops,
                particles=particles, meshes=meshes, trailing=len(b) - o, tail=b[o:])


def _wstr(s):
    raw = s.encode("latin-1") if isinstance(s, str) else s
    return struct.pack("<i", len(raw)) + raw


def build(e):
    """The bytes of an effect in ``read``'s shape -- byte-identical for one that came from
    ``read`` (604 of the 605 shipped effects; ``rosefmt-roundtrip``-style check in
    ``scripts/CLAUDE.md``). A new effect needs, per particle: ``ptl``, ``pos`` (cm, the
    parent's axes -- a character's front is -Y), ``delay`` (ms); everything else defaults."""
    out = [_wstr(e.get("name", "")), struct.pack("<i", e.get("use_sound", 0)),
           _wstr(e.get("sound_name", e.get("sound", ""))), struct.pack("<i", e.get("sound_loops", 0)),
           struct.pack("<i", len(e["particles"]))]
    for q in e["particles"]:
        out += [_wstr(q.get("label", "")), _wstr(q.get("unique", "")),
                struct.pack("<i", q.get("stb_index", 0)), _wstr(q["ptl"]),
                struct.pack("<i", q.get("use_ani", 0)), _wstr(q.get("ani_name", "NULL")),
                struct.pack("<2i", q.get("ani_loops", 0), q.get("ani_stb_index", 0)),
                struct.pack("<3f", *q["pos"]), struct.pack("<4f", *q.get("rot", (0.0, 0.0, 0.0, -1.0))),
                struct.pack("<2i", q.get("delay", 0), q.get("link", 1))]
    out.append(struct.pack("<i", len(e.get("meshes", []))))
    for m in e.get("meshes", []):
        out += [_wstr(m.get("label", "")), _wstr(m.get("unique", "")),
                struct.pack("<i", m.get("stb_index", 0)), _wstr(m["zms"]), _wstr(m["zmo"]),
                _wstr(m["texture"]),
                struct.pack("<%di" % len(MESH_FLAGS), *[m["flags"][k] for k in MESH_FLAGS]),
                struct.pack("<i", m.get("use_ani", 0)), _wstr(m.get("ani_name", "NULL")),
                struct.pack("<2i", m.get("ani_loops", 0), m.get("ani_stb_index", 0)),
                struct.pack("<3f", *m["pos"]), struct.pack("<4f", *m.get("rot", (0.0, 0.0, 0.0, -1.0))),
                struct.pack("<3i", m.get("delay", 0), m.get("repeat", 1), m.get("link", 1))]
    out.append(e.get("tail", b""))
    return b"".join(out)


def with_mesh_flags(blob, index, **changes):
    """The effect's bytes with mesh ``index``'s render flags changed (names: MESH_FLAGS)."""
    b = read_file(blob)
    mesh = read(b)["meshes"][index]
    out = bytearray(b)
    for k, v in changes.items():
        if k not in MESH_FLAGS:
            raise ValueError("unknown mesh flag %r" % k)
        struct.pack_into("<i", out, mesh["flags_offset"] + 4 * MESH_FLAGS.index(k), v)
    return bytes(out)
