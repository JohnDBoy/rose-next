"""Bringing a character model across from another dump: ``import_characters``.

Nothing in ``LIST_NPC.CHR`` can be copied by index: the source's
``PART_NPC.ZSC`` models, skeletons and motions all overlap ours with different
meanings. Meshes and materials dedupe by path, models are appended, and the
skeleton/motion/effect pools intern lazily (``StringPool``), so the table
never names a file the asset copy did not bring.

``regen_mob_ids`` reads the two mob lists out of a REGEN record's raw extra
bytes (the importers' ``rosefmt.ifo_lumps`` view), which is how a spawn roster
is walked for the monsters it needs.
"""
import struct

from rosefmt import Chr, Zsc

from .files import backup, copy_files, norm, rel_path
from .schema import LEVEL_PREFIX, NPC_CHR_REL, PART_NPC_ZSC_REL


def clean_npc_name(raw):
    """RoseZA prefixes monster names with their level: '(201) Baby Desert Asper'."""
    return LEVEL_PREFIX.sub("", raw.decode("latin-1")).strip()


class StringPool:
    """Maps a source index to ours, interning on demand.

    Lazily, deliberately: interning every source string would append paths for
    skeletons and motions no imported monster references, and the asset copy
    only covers what is referenced -- so the table would carry entries pointing
    at files that are not there. Resolving on first use keeps the two in step
    by construction, and ``used`` is exactly the set of files to copy.
    """

    def __init__(self, our_list, src_list):
        self.ours, self.src = our_list, src_list
        self.have = {norm(s): i for i, s in enumerate(our_list)}
        self.used = set()

    def __getitem__(self, src_idx):
        s = self.src[src_idx]
        self.used.add(s.decode("latin-1"))
        k = norm(s)
        if k not in self.have:
            self.have[k] = len(self.ours)
            self.ours.append(s)
        return self.have[k]


def regen_mob_ids(extra):
    """The two mob lists inside a REGEN record's per-object extra bytes."""
    o = 0
    n = extra[o]
    o += 1 + n                                     # regen point name
    ids = []
    for _ in range(2):                             # basic list, then tactics list
        cnt, = struct.unpack_from("<i", extra, o)
        o += 4
        for _ in range(cnt):
            ln = extra[o]
            o += 1 + ln
            idx, c = struct.unpack_from("<ii", extra, o)
            o += 8
            if idx > 0 and c > 0:
                ids.append(idx)
    return ids


def import_characters(ids, ours, src, dry, what, src_of=None):
    """Copy LIST_NPC.CHR entries for ``ids``, remapping every index on the way in.

    ``src_of`` maps one of our ids to the source row it is copied from, for a
    character that lands on a different row here (default: the same row).
    Returns how many entries were written.
    """
    src_chr = Chr(rel_path(src, NPC_CHR_REL))
    our_chr = Chr(rel_path(ours, NPC_CHR_REL))
    src_zsc = Zsc(rel_path(src, PART_NPC_ZSC_REL))
    our_zsc = Zsc(rel_path(ours, PART_NPC_ZSC_REL))

    skel_map = StringPool(our_chr.skeletons, src_chr.skeletons)
    motion_map = StringPool(our_chr.motions, src_chr.motions)
    effect_map = StringPool(our_chr.effects, src_chr.effects)

    mesh_idx = {norm(m): i for i, m in enumerate(our_zsc.meshes)}
    mat_idx = {norm(p): i for i, (p, _) in enumerate(our_zsc.materials)}
    new_meshes, new_mats, new_objects = [], [], []
    model_map, art = {}, set()

    def map_model(sidx):
        if sidx in model_map:
            return model_map[sidx]
        cyl, sparts, sdummies, sbb = src_zsc.objects[sidx]
        parts = []
        for mid, tid, props in sparts:
            mk = norm(src_zsc.meshes[mid])
            if mk not in mesh_idx:
                mesh_idx[mk] = len(our_zsc.meshes) + len(new_meshes)
                new_meshes.append(src_zsc.meshes[mid])
            tk = norm(src_zsc.materials[tid][0])
            if tk not in mat_idx:
                mat_idx[tk] = len(our_zsc.materials) + len(new_mats)
                new_mats.append(src_zsc.materials[tid])
            art.add(src_zsc.meshes[mid].decode("latin-1"))
            art.add(src_zsc.materials[tid][0].decode("latin-1"))
            parts.append((mesh_idx[mk], mat_idx[tk], props))
        model_map[sidx] = len(our_zsc.objects) + len(new_objects)
        new_objects.append(our_zsc.object_bytes(cyl, parts, sdummies, sbb))
        return model_map[sidx]

    if max(ids) >= len(our_chr.chars):
        our_chr.chars.extend([None] * (max(ids) + 1 - len(our_chr.chars)))
    written = 0
    for i in ids:
        if our_chr.chars[i] is not None:
            continue
        s = (src_of or {}).get(i, i)
        c = src_chr.chars[s] if s < len(src_chr.chars) else None
        if c is None:
            raise SystemExit(f"{what} {s} has no LIST_NPC.CHR entry in the source")
        # An index past the end of its pool is dead padding, not a reference:
        # the value is always 52685 (0xCDCD, MSVC's uninitialised-heap fill) under
        # anim type 65535, written out by whatever tool built these files. Our own
        # LIST_NPC.CHR carries 112 of them across 12,027 anim entries and the
        # client is fine with it, so they pass through verbatim rather than being
        # remapped -- there is no string to intern -- or dropped, which would make
        # imported rows a different shape from the ones we already ship.
        sk = c["skel"]
        our_chr.chars[i] = dict(
            skel=sk if sk >= len(src_chr.skeletons) else skel_map[sk],
            name=c["name"],
            models=[map_model(m) for m in c["models"]],
            anims=[(t, a if a >= len(src_chr.motions) else motion_map[a])
                   for t, a in c["anims"]],
            effects=[(t, e if e >= len(src_chr.effects) else effect_map[e])
                     for t, e in c["effects"]],
        )
        written += 1

    art |= skel_map.used | motion_map.used
    print(f"    {'LIST_NPC.CHR':26s} {written} entries (now {len(our_chr.chars)}), "
          f"skel {len(our_chr.skeletons)} motion {len(our_chr.motions)}")
    print(f"    {'PART_NPC.ZSC':26s} +{len(new_objects)} models, "
          f"+{len(new_meshes)} meshes, +{len(new_mats)} materials")
    copy_files({a for a in art if "\\" in a or "/" in a}, src, ours, dry,
               f"{what} art")
    our_chr.save(dry)
    if new_objects and not dry:
        p = rel_path(ours, PART_NPC_ZSC_REL)
        backup(p)
        with open(p, "wb") as fh:
            fh.write(our_zsc.to_bytes(new_meshes, new_mats, new_objects))
    return written
