"""QSD quest scripts (``3DDATA/QUESTDATA/*.QSD``): triggers of conditions and rewards.

Layout (mirrors ``src/tools/quest-editor/src/qsd.rs``)::

    u32 size_field (always 12, not the file length) | u32 pattern_count | str desc
    per pattern: u32 trigger_count | str name
    per trigger: u8 check_next | u32 cond_count | u32 rew_count | str name
                 then (cond_count + rew_count) entities: u32 size | i32 type | payload

``str`` is i16 length + bytes (NUL included). **Nothing in the file is an
offset**, so whole triggers can be spliced in by appending a pattern and
bumping the count, and a condition can be removed by deleting its bytes and
decrementing its trigger's count. An entity keeps its length: its ``u32 size``
is what the loader walks by, so never resize one by slicing.

Entity types: the high byte of ``type`` distinguishes conditions (``0x00``) and
rewards (``0x01``). Only three carry an item id: COND_004 (count + STR_ITEM_DATA
records), REWD_001 and REWD_032 -- COND_001/002/003 are quest *variables*, and
reading those as items yields plausible nonsense. The STR_ITEM_DATA stride is
derived from the entity size rather than assumed. **Trigger names are global
across every QSD**, and a failing trigger is silent on both sides.

Round-trips byte for byte (``parse`` / ``build``).
"""
import struct

from .binio import read_file

COND_ITEM, REWD_ITEM, REWD_ITEM2 = 4, 1, 32


def pstr(s):
    """A QSD string: i16 length + latin-1 bytes + NUL."""
    v = (s.encode("latin-1") if isinstance(s, str) else s) + b"\0"
    return struct.pack("<h", len(v)) + v


qsd_pstr = pstr


def _str(b, o):
    n, = struct.unpack_from("<h", b, o)
    o += 2
    return b[o:o + n], o + n


def parse(blob):
    """{'size': int, 'desc': bytes, 'patterns': [(name, [trigger])]} with a
    trigger ``{'check_next': int, 'name': bytes, 'conds': [bytes], 'rewds': [bytes]}``
    where each entity is its raw record (size + type + payload)."""
    b = read_file(blob)
    o = 0
    size, npat = struct.unpack_from("<II", b, o)
    o += 8
    desc, o = _str(b, o)
    pats = []
    for _ in range(npat):
        ntrig, = struct.unpack_from("<I", b, o)
        o += 4
        pname, o = _str(b, o)
        trigs = []
        for _ in range(ntrig):
            chk = b[o]
            o += 1
            ncond, nrew = struct.unpack_from("<II", b, o)
            o += 8
            tname, o = _str(b, o)
            ents = []
            for _ in range(ncond + nrew):
                esz, = struct.unpack_from("<I", b, o)
                ents.append(b[o:o + esz])
                o += esz
            trigs.append(dict(check_next=chk, name=tname, conds=ents[:ncond], rewds=ents[ncond:]))
        pats.append((pname, trigs))
    # ruff's dump has 12-3140 bytes after the last pattern in 19 files; the
    # loader reads the pattern count and stops, so they are dead but carried.
    return dict(size=size, desc=desc, patterns=pats, tail=b[o:])


def build(q):
    out = bytearray(struct.pack("<II", q["size"], len(q["patterns"])))
    out += struct.pack("<h", len(q["desc"])) + q["desc"]
    for pname, trigs in q["patterns"]:
        out += struct.pack("<I", len(trigs))
        out += struct.pack("<h", len(pname)) + pname
        for t in trigs:
            out += bytes([t["check_next"]])
            out += struct.pack("<II", len(t["conds"]), len(t["rewds"]))
            out += struct.pack("<h", len(t["name"])) + t["name"]
            for e in t["conds"] + t["rewds"]:
                out += e
    out += q.get("tail", b"")
    return bytes(out)


def entity_type(e):
    return struct.unpack_from("<i", e, 4)[0]


def trigger_name(raw):
    return raw.rstrip(b"\0").decode("latin-1")


# ------------------------------------------------------------- walkers
def walk(blob):
    """Yield (trigger_name, [(etype, entity_bytes)], trigger_bytes)."""
    b, o = blob, 4
    npat, = struct.unpack_from("<I", b, o); o += 4
    n, = struct.unpack_from("<h", b, o); o += 2 + n
    for _ in range(npat):
        ntrig, = struct.unpack_from("<I", b, o); o += 4
        n, = struct.unpack_from("<h", b, o); o += 2 + n
        for _ in range(ntrig):
            trig_start = o
            o += 1
            ncond, = struct.unpack_from("<I", b, o); o += 4
            nrew, = struct.unpack_from("<I", b, o); o += 4
            n, = struct.unpack_from("<h", b, o); o += 2
            name = b[o:o + n].rstrip(b"\0").decode("latin-1"); o += n
            ents = []
            for _ in range(ncond + nrew):
                esz, = struct.unpack_from("<I", b, o)
                etype, = struct.unpack_from("<i", b, o + 4)
                ents.append((etype, b[o:o + esz]))
                o += esz
            yield name, ents, b[trig_start:o]


def trigger_bytes(blob, name):
    for tname, _, raw in walk(blob):
        if tname == name:
            return raw
    return None


def find_entity(blob, trigger, etype):
    """Raw bytes of the first entity of ``etype`` inside ``trigger``, or None."""
    for tname, ents, _ in walk(blob):
        if tname != trigger:
            continue
        for t, raw in ents:
            if t == etype:
                return raw
    return None


def has_trigger(blob, name):
    return any(tname == name for tname, _, _ in walk(blob))


def trigger_names(blob):
    return [tname for tname, _, _ in walk(blob)]


def build_trigger(name, conds, rewds, check_next=0):
    return (bytes([check_next])
            + struct.pack("<II", len(conds), len(rewds))
            + pstr(name)
            + b"".join(conds) + b"".join(rewds))


def append_pattern(blob, pattern, triggers):
    """Append a pattern of pre-built triggers; the pattern count is at offset 4."""
    out = bytearray(blob)
    npat, = struct.unpack_from("<I", out, 4)
    struct.pack_into("<I", out, 4, npat + 1)
    out += struct.pack("<I", len(triggers)) + pstr(pattern)
    out += b"".join(triggers)
    return bytes(out)


def patch(template, *fields):
    """Copy a real entity and overwrite payload fields: (payload_offset, fmt, values)."""
    e = bytearray(template)
    for off, fmt, values in fields:
        struct.pack_into(fmt, e, 8 + off, *values)
    return bytes(e)


def parse_ok(blob):
    """Re-walk and confirm the whole file is consumed exactly: (ok, bytes consumed)."""
    b, o = blob, 4
    npat, = struct.unpack_from("<I", b, o); o += 4
    n, = struct.unpack_from("<h", b, o); o += 2 + n
    for _ in range(npat):
        ntrig, = struct.unpack_from("<I", b, o); o += 4
        n, = struct.unpack_from("<h", b, o); o += 2 + n
        for _ in range(ntrig):
            o += 1
            ncond, = struct.unpack_from("<I", b, o); o += 4
            nrew, = struct.unpack_from("<I", b, o); o += 4
            n, = struct.unpack_from("<h", b, o); o += 2 + n
            for _ in range(ncond + nrew):
                esz, = struct.unpack_from("<I", b, o)
                o += esz
    return o == len(b), o


def drop_conditions(blob, drops):
    """Remove named conditions: ``drops`` = {(trigger, cond_type, i16 value)}.

    Safe as a byte-level edit because the format carries no internal offsets.
    Returns (blob, [removed]).
    """
    b = bytearray(blob)
    wanted = {(t, ct, val) for t, ct, val in drops}
    if not wanted:
        return bytes(b), []
    removed, edits = [], []

    def u32(at):
        return struct.unpack_from("<I", b, at)[0]

    o = 4
    npat = u32(o); o += 4
    n, = struct.unpack_from("<h", b, o); o += 2 + n
    for _ in range(npat):
        ntrig = u32(o); o += 4
        n, = struct.unpack_from("<h", b, o); o += 2 + n
        for _ in range(ntrig):
            o += 1
            cond_at = o
            ncond = u32(o); o += 4
            nrew = u32(o); o += 4
            n, = struct.unpack_from("<h", b, o); o += 2
            tname = bytes(b[o:o + n]).rstrip(b"\0").decode("latin-1"); o += n
            for idx in range(ncond + nrew):
                ent = o
                esz = u32(o)
                etype = struct.unpack_from("<i", b, o + 4)[0] & 0xFFFFFF
                if idx < ncond and esz >= 11:
                    val, = struct.unpack_from("<h", b, ent + 8)
                    if (tname, etype, val) in wanted:
                        edits.append((ent, esz, cond_at))
                        removed.append((tname, etype, val))
                o = ent + esz
    for ent, esz, cond_at in sorted(edits, reverse=True):
        struct.pack_into("<I", b, cond_at, u32(cond_at) - 1)
        del b[ent:ent + esz]
    return bytes(b), removed


def item_refs(path_or_blob):
    """[(offset_of_the_u32_item_id, item_sn, 'condition'|'reward')]."""
    b = read_file(path_or_blob)
    out = []
    o = 0

    def u32():
        nonlocal o
        v, = struct.unpack_from("<I", b, o); o += 4; return v

    def i32():
        nonlocal o
        v, = struct.unpack_from("<i", b, o); o += 4; return v

    def skip_str():
        nonlocal o
        n, = struct.unpack_from("<h", b, o); o += 2 + n

    u32()
    npat = u32()
    skip_str()
    for _ in range(npat):
        ntrig = u32()
        skip_str()
        for _ in range(ntrig):
            o += 1
            ncond, nrew = u32(), u32()
            skip_str()
            for kind, cnt in (("condition", ncond), ("reward", nrew)):
                for _ in range(cnt):
                    ent = o
                    esz = u32()
                    etype = i32() & 0xFFFFFF
                    body = ent + 8
                    if kind == "condition" and etype == COND_ITEM:
                        n, = struct.unpack_from("<i", b, body)
                        stride = (esz - 12) // n if n > 0 else 0
                        for i in range(max(0, n)):
                            p = body + 4 + i * stride
                            out.append((p, struct.unpack_from("<I", b, p)[0], kind))
                    elif kind == "reward" and etype in (REWD_ITEM, REWD_ITEM2):
                        out.append((body, struct.unpack_from("<I", b, body)[0], kind))
                    o = ent + esz
    return out


def remap_items(blob, remap):
    """Rewrite item ids in place (fixed-size u32 pokes). Returns (blob, {sn: n})."""
    out = bytearray(blob)
    changed = {}
    for off, sn, _ in item_refs(blob):
        if sn in remap:
            struct.pack_into("<I", out, off, remap[sn])
            changed[sn] = changed.get(sn, 0) + 1
    return bytes(out), changed


def quest_refs(path_or_blob):
    """Quest ids a .QSD touches: COND_000 (has quest) and REWD_000 (add/swap)."""
    b = read_file(path_or_blob)
    out = set()
    for _, ents, _ in walk(b):
        for etype, e in ents:
            if (etype & 0xFFFFFF) == 0 and len(e) >= 12:
                q, = struct.unpack_from("<i", e, 8)
                if 0 < q < 60000:
                    out.add(q)
    return out


# the names import-oro.py / import-oro-fate.py exported
qsd_walk, qsd_trigger_bytes, qsd_find_entity = walk, trigger_bytes, find_entity
qsd_has_trigger, qsd_build_trigger, qsd_append_pattern = has_trigger, build_trigger, append_pattern
qsd_patch, qsd_parse_ok, qsd_drop_conditions = patch, parse_ok, drop_conditions
qsd_item_refs, qsd_remap_items, qsd_quest_refs = item_refs, remap_items, quest_refs
QSD_COND_ITEM, QSD_REWD_ITEM, QSD_REWD_ITEM2 = COND_ITEM, REWD_ITEM, REWD_ITEM2
