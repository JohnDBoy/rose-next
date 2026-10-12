"""CON NPC dialogs (``3DDATA/EVENT/*.CON``): the node tree and its Lua. (Module named
``condialog`` because ``con`` is a reserved device name on Windows.)

This is the byte-level view: the fields the importers patch (click/check
function names, string ids, the Lua blob and our QEX1 appendix). The full
codec, including building a dialog from scratch, is the quest editor's
``src/tools/quest-editor/src/convo.rs`` -- the canonical implementation.

Layout: a 524-byte header (``u32 conv_off`` at 516, ``u32 script_off`` at 520),
then at ``conv_off``: ``i32 msg_num, u32 msg_start, i32 menu_num, u32
menu_start``. A message / menu item is an 80-byte node::

    i32 sn | i32 type | i32 value | char[32] check_func | char[32] click_func
    | i32 str_id          <- a row in ulngtb_con.ltb

MMT offsets are relative to their own table base (not ``conv_off``), and each
menu collection's body after its first 8 bytes (``i32 length, i32 num_sub``) is
XOR-encoded with ``xor_key(num_sub, length)``. Miss either and the ids read as
noise. The Lua at ``script_off`` is ``i32 len`` + bytecode XOR'd with
``xor_key(len, file_size)``; **the key depends on the final file size**, so the
main blob must be re-encoded whenever the appendix changes size.

Our extension: an optional appendix after the Lua -- ``b"QEX1"; i32 len; XOR'd
Lua source`` -- that the client (``cevent.cpp``) executes into the same
``lua_State`` after the main blob, so later definitions win. A ``.CON`` is
client-only; the server never reads it.

``split`` / ``join`` round-trip byte for byte.
"""
import struct

from .binio import read_file

HEADER_LEN = 524
NODE_SIZE = 80
NODE_CHECK_OFF = 12                  # char szFunc1[32]
NODE_CLICK_OFF = 44                  # char szFunc2[32]
NODE_STR_ID_OFF = 76
APPENDIX_MAGIC = b"QEX1"
CON_HEADER_LEN, CON_NODE, CON_STR_ID_OFF = HEADER_LEN, NODE_SIZE, NODE_STR_ID_OFF


def xor_key(v1, v2):
    return (v1 & 0xFF) if (v1 & 1) else (v2 & 0xFF)


def str_ids(path_or_blob):
    """Every positive LTB string id the dialog's messages and menu items name."""
    b = read_file(path_or_blob)
    if len(b) < HEADER_LEN + 16:
        return []
    conv_off, = struct.unpack_from("<I", b, 516)
    msg_num, msg_start = struct.unpack_from("<iI", b, HEADER_LEN)
    menu_num, menu_start = struct.unpack_from("<iI", b, HEADER_LEN + 8)
    out = []

    base = conv_off + msg_start
    for i in range(max(0, msg_num)):
        mmt, = struct.unpack_from("<I", b, base + 4 * i)
        p = base + mmt
        if p + NODE_SIZE <= len(b):
            out.append(struct.unpack_from("<i", b, p + NODE_STR_ID_OFF)[0])

    base = conv_off + menu_start
    for i in range(max(0, menu_num)):
        mmt, = struct.unpack_from("<I", b, base + 4 * i)
        coll_off = base + mmt
        if coll_off + 8 > len(b):
            continue
        length, num_sub = struct.unpack_from("<ii", b, coll_off)
        if length < 8 or coll_off + length > len(b):
            continue
        coll = bytearray(b[coll_off:coll_off + length])
        k = xor_key(num_sub, length)
        for j in range(8, len(coll)):
            coll[j] ^= k
        for j in range(max(0, num_sub)):
            if 12 + 4 * j > len(coll):
                break
            sub, = struct.unpack_from("<I", coll, 8 + 4 * j)
            if sub + NODE_SIZE <= len(coll):
                out.append(struct.unpack_from("<i", coll, sub + NODE_STR_ID_OFF)[0])
    return [x for x in out if x > 0]


def menu_offsets(blob):
    conv_off, = struct.unpack_from("<I", blob, 516)
    menu_num, menu_start = struct.unpack_from("<iI", blob, conv_off + 8)
    return conv_off + menu_start, menu_num


def _decoded_collection(blob, menu_idx):
    base, menu_num = menu_offsets(blob)
    if not 0 <= menu_idx < menu_num:
        raise ValueError("menu %d out of range (have %d)" % (menu_idx, menu_num))
    mmt, = struct.unpack_from("<I", blob, base + 4 * menu_idx)
    coll = base + mmt
    length, nsub = struct.unpack_from("<ii", blob, coll)
    key = xor_key(nsub, length)
    body = bytearray(blob[coll:coll + length])
    for i in range(8, len(body)):
        body[i] ^= key
    return coll, length, nsub, key, body


def set_click(blob, menu_idx, item_idx, func):
    """Rewrite one menu item's click-function name in place.

    Neither the collection's length nor its sub-count changes, so it can be
    decoded, patched and re-encoded without disturbing any offset.
    """
    out = bytearray(blob)
    coll, length, nsub, key, body = _decoded_collection(out, menu_idx)
    if not 0 <= item_idx < nsub:
        raise ValueError("menu %d item %d out of range (have %d)" % (menu_idx, item_idx, nsub))
    sub, = struct.unpack_from("<I", body, 8 + 4 * item_idx)
    name = func.encode("latin-1")
    if len(name) >= 32:
        raise ValueError("click function name too long: %s" % func)
    body[sub + NODE_CLICK_OFF:sub + NODE_CLICK_OFF + 32] = name + b"\0" * (32 - len(name))
    for i in range(8, len(body)):
        body[i] ^= key
    out[coll:coll + length] = body
    return bytes(out)


def get_item(blob, menu_idx, item_idx):
    """(type, child, check, click, str_id) for one menu item."""
    _coll, _length, _nsub, _key, body = _decoded_collection(blob, menu_idx)
    sub, = struct.unpack_from("<I", body, 8 + 4 * item_idx)
    _, mtype, child = struct.unpack_from("<3i", body, sub)
    chk = bytes(body[sub + NODE_CHECK_OFF:sub + NODE_CHECK_OFF + 32]).split(b"\0")[0].decode("latin-1")
    clk = bytes(body[sub + NODE_CLICK_OFF:sub + NODE_CLICK_OFF + 32]).split(b"\0")[0].decode("latin-1")
    sid, = struct.unpack_from("<i", body, sub + NODE_STR_ID_OFF)
    return mtype, child, chk, clk, sid


def split(blob):
    """(head, lua, appendix) with both blobs XOR-decoded."""
    return split_ex(blob)[:3]


def split_ex(blob):
    """(head, lua, appendix, tail): ``tail`` is whatever follows the Lua (or the
    appendix) -- ruff's EM16-001.CON carries 732 such bytes; the client never
    reads past the Lua length, so they are dead but must survive a rewrite."""
    script_off, = struct.unpack_from("<I", blob, 520)
    lua_len, = struct.unpack_from("<i", blob, script_off)
    lua_len = max(0, lua_len)
    total = len(blob)
    lua = bytes(x ^ xor_key(lua_len, total)
                for x in blob[script_off + 4: script_off + 4 + lua_len])
    appendix = b""
    ap_off = script_off + 4 + lua_len
    end = ap_off
    if ap_off + 8 <= total and blob[ap_off:ap_off + 4] == APPENDIX_MAGIC:
        ap_len, = struct.unpack_from("<i", blob, ap_off + 4)
        if ap_len > 0 and ap_off + 8 + ap_len <= total:
            appendix = bytes(x ^ xor_key(ap_len, total)
                             for x in blob[ap_off + 8: ap_off + 8 + ap_len])
            end = ap_off + 8 + ap_len
    return blob[:script_off], lua, appendix, blob[end:]


def join(head, lua, appendix=b"", tail=b""):
    """Rebuild the file; both blobs are keyed on the *final* file size, which
    includes any dead ``tail`` bytes after them."""
    ap_block = 8 + len(appendix) if appendix else 0
    total = len(head) + 4 + len(lua) + ap_block + len(tail)
    out = bytearray(head)
    out += struct.pack("<i", len(lua))
    out += bytes(x ^ xor_key(len(lua), total) for x in lua)
    if appendix:
        out += APPENDIX_MAGIC + struct.pack("<i", len(appendix))
        out += bytes(x ^ xor_key(len(appendix), total) for x in appendix)
    out += tail
    if len(out) != total:
        raise AssertionError((len(out), total))
    return bytes(out)


con_xor_key, con_str_ids, con_menu_offsets = xor_key, str_ids, menu_offsets
con_set_click, con_get_item, con_split, con_join = set_click, get_item, split, join
con_split_ex = split_ex
