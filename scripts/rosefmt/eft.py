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

``read`` returns the mesh render flags with their byte offset, and ``with_mesh_flags``
rewrites them in place, so an edit never re-serialises the file.
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
    (_loops, count), o = _ints(b, o, 2)
    particles = []
    for _ in range(count):
        _, o = _str(b, o)
        _, o = _str(b, o)
        o += 4
        ptl, o = _str(b, o)
        (use_ani,), o = _ints(b, o, 1)
        ani, o = _str(b, o)
        o += 8
        pos = struct.unpack_from("<3f", b, o)
        o += 28
        (delay, _link), o = _ints(b, o, 2)
        particles.append(dict(ptl=ptl, ani=ani if use_ani else "", pos=pos, delay=delay))
    (count,), o = _ints(b, o, 1)
    meshes = []
    for _ in range(count):
        _, o = _str(b, o)
        _, o = _str(b, o)
        o += 4
        zms, o = _str(b, o)
        zmo, o = _str(b, o)
        texture, o = _str(b, o)
        flags_offset = o
        flags, o = _ints(b, o, len(MESH_FLAGS))
        (use_ani,), o = _ints(b, o, 1)
        ani, o = _str(b, o)
        o += 8
        pos = struct.unpack_from("<3f", b, o)
        o += 28
        (delay, repeat, _link), o = _ints(b, o, 3)
        meshes.append(dict(zms=zms, zmo=zmo, texture=texture, ani=ani if use_ani else "",
                           flags=dict(zip(MESH_FLAGS, flags)), flags_offset=flags_offset,
                           pos=pos, delay=delay, repeat=repeat))
    return dict(name=name, sound=sound if use_sound else "", particles=particles, meshes=meshes,
                trailing=len(b) - o)


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
