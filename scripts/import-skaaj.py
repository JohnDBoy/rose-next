#!/usr/bin/env python3
"""Import Skaaj, Jrose's cat-folk island town, as our zone 89.

Skaaj (スカ, "Ska") is Jrose zone 79: a small tropical island -- a plaza on the
southern islet, a bridge north to a ranch and a pool, open sea all round -- that
Jrose used as the hub of its housing and pet systems. We want the map, the
townsfolk and the way there; not the housing, the pet shop or the cooking chain.
Nothing hostile lives on it: the only spawns are butterflies and clownfish.

Staged like scripts/import-karkia.py, and for the same reason -- each stage is
independently testable in game and re-runnable:

    --stage 1   terrain, art, tiles, the zone row and its name. The copied .IFOs
                get their MOB/REGEN/WARP lumps emptied on the way in; the one
                warp gate led to Jrose's housing interior and is never refilled.
    --stage 2   the eleven townsfolk: LIST_NPC rows at their native ids, English
                names, character models, LIST_EVENT rows for their dialogs, the
                .CON files, and the placements back into the MOB lumps.
    --stage 3   the critters: three clownfish recolours (2785-2787) our table
                lacks, then the 21 regen points exactly as Jrose laid them out.
    --stage 4   dialog and travel: the "Skaaj language" switch, English text for
                every reachable line, Jrose-only options hidden, and the trips --
                Jones (Junon Polis) and Nova (Orlean Portal Temple) get a
                "take me to Skaaj" option, and Wedgy the island's travel guide
                sends you back to the Adventurer's Plains or Junon Polis.

Every stage is idempotent; --dry-run previews; --verify re-derives the state;
--selftest proves every writer round-trips byte-identically before anything is
touched.

Why this is a port and not a copy
---------------------------------
  * **Zone 79 is our Wasteland** (Oro), so Skaaj lands on 89, the first free row
    after Oro's block. Nothing in the map data encodes the number -- the tile
    folder is named `Skaaj\\79` but that is a path, and the revive-zone columns
    are blank -- so renumbering costs nothing. The STL key LZON079 is likewise
    taken; LZON100 is the first free above Karkia's block.

  * **The sky column is blank** in Jrose's row. The client reads it as an integer
    (blank = sky 0, the Junon day sky), but the xadet map editor rejects a blank
    cell outright, so we write an explicit 0.

  * **The .ZON is the stripped late-Jrose variant** with no LUMP_ECONOMY; without
    one the server's CEconomy runs on uninitialised heap. Spliced in exactly as
    import-karkia.py does it.

  * **The town is gated on a "language" quest switch.** Every NPC's real greeting
    sits behind `QF_checkQuestCondition("chk-Skaaj-Language-QSW")`, and the
    ungated line before it is cat-language ("nyaa nii onyaa..."). Miakis, the
    divine envoy, is the only one you understand; her dialog ends with a
    "Thank you!" that fires `Skaaj-Language-QSW-ON`, which sets quest switch 90,
    and from then on everyone speaks plainly. CEvent::Conversation walks every
    root node and each NPCSAY replaces the last, so the later gated line wins
    once the switch is on -- that is the whole mechanism, and it is kept. Switch
    90 is unused in our 225 QSD files, so the condition and reward entities are
    copied byte-for-byte from Jrose's QN-SKA001.QSD into our QP401.QSD.

  * **Four dialog options lean on Jrose systems we do not have** and call Lua
    functions our client never registered (GF_openDeliveryStore,
    GF_openSpotBank, GF_PetDepositOpen, GF_IsWorldName): the warehouse keeper's
    "my item center" and "withdraw-only storage", the rancher's "pet goods"
    (Jrose LIST_SELL 266, Jrose pet items) and "board my pet". A missing Lua
    function pops an ErrorBOX, so their check-function field is pointed at
    `TA_Hidden`, defined in a QEX1 appendix to return 0. Everything else the
    files call exists here: GF_openBank, GF_openStore, QF_doQuestTrigger,
    QF_findQuest, QF_getEventOwner.

  * **The cooking-chain, housing and TGS2015 branches do NOT simply never
    pass.** Their triggers are unknown here and fail, but several checks are
    inverted -- `TA_CookQ_Q32_10` ("your bag is full") returns 1 when
    `chk-Q32_INV` fails -- and the node's text is empty on our side. An NPCSAY
    with empty text closes the window *before* it tests the text, so Lusiga's
    greeting opened and was shut in the same tick and the bird read as mute
    (found in the client debug log, 2026-09-18). Every node gated on one of
    those chains (68 across the files, HIDE_CHECK_PREFIXES) is re-pointed at
    `TA_Hidden` as well.

  * **Wedgy's exits collide with ours by name.** His Lua fires
    `QF_doQuestTrigger("gotoJunon")` -- and a `gotoJunon` already exists in our
    TUTORIAL.QSD, since trigger names are global across every QSD -- and gates
    the Junon Polis option on `chk-clear-voyagequest` (Jrose's newbie voyage,
    quest switch 37, which *is* in use here for something else). Rather than
    patch bytecode, the QEX1 appendix on EM79-001 redefines the three functions:
    the appendix runs after the main blob in the same lua_State, so the later
    definition wins. Our triggers are `Skaaj-TravelToPlains` / `-ToJunon`, the
    same REWD_007 warps the Oro and Karkia travel scripts write, landing on
    each zone's own `start`, and the gate simply returns 1.

  * **Jrose NPC 1774 is dead on arrival**: no name, no LIST_NPC.CHR entry, and
    its placement asks for `EM79-012.con` while the file is `EM79-12.CON`. It
    is dropped rather than repaired.

  * **Our LIST_NPC.CHR carries orphan entries at 1753-1759** (a "noname" model
    582) with no LIST_NPC row behind them. import_characters keeps any entry it
    finds, so those slots are cleared first when the row is blank on our side,
    or the fisher would wear the wrong body.

After running: `add-dds-mipmaps.py --subdir 3DDATA/SKAAJ` and
`--subdir 3DDATA/TERRAIN/TILES/SKAAJ` (Jrose ships flat textures), delete the
`.bak` files the writers leave (pack.rs bakes them), rebake the VFS, restart the
servers. Stage 4's appended options need the QEX1-aware client, so ship client
and data together.
"""
import argparse
import importlib.util
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# --------------------------------------------------------------------- config
DEFAULT_SRC = r"C:\Users\Thomas\Desktop\Testclients\Jrose"

SRC_ZONE_ROW, ZONE_ROW = 79, 89
ZONE_NAME, ZONE_STL_KEY = "Skaaj", "LZON100"
ZONE_SKY = "0"                     # blank in the source; explicit for the editor
MAPS_REL = r"3DDATA\MAPS\SKAAJ\SKTOWN"
ART_REL = r"3DDATA\SKAAJ"
ZONE_STB_REL = r"3DDATA\STB\LIST_ZONE.STB"
ZONE_STL_REL = r"3DDATA\STB\LIST_ZONE_S.STL"
ZONE_COPY_COLS = 36                # Jrose has a 37th, its world-map number
ZONE_NAME_COL, ZONE_SKY_COL, ZONE_STL_COL = 0, 7, 26
NPC_STB_REL = r"3DDATA\STB\LIST_NPC.STB"
NPC_STL_REL = r"3DDATA\STB\LIST_NPC_S.STL"
NPC_CHR_REL = r"3DDATA\NPC\LIST_NPC.CHR"
EVENT_STB_REL = r"3DDATA\STB\LIST_EVENT.STB"
EVENT_FILE_COL = 3
EVENT_DIR_REL = r"3DDATA\EVENT"
LTB_REL = r"3DDATA\EVENT\ulngtb_con.ltb"
QSD_REL = r"3DDATA\QUESTDATA\QP401.QSD"
QSD_TEMPLATE_REL = r"3DDATA\QUESTDATA\PVP10.QSD"
QSD_TEMPLATE_TRIGGER = "PvP10-061"
SRC_QSD_REL = r"3DDATA\QUESTDATA\QN-SKA001.QSD"
BGM_SRC_REL = r"Sound\BGM\skaaj01.ogg"
BGM_DEPLOY_DIR = r"C:\Users\Thomas\Desktop\ROSEProject\Sound\BGM"
QUEST_EDITOR = os.path.join(ROOT, "bin", "release", "quest-editor.exe")

# Jrose id -> English name. The bracketed role titles are legible even where the
# names are katakana guesses: [旅行ガイド] travel guide, [倉庫番] storekeeper,
# [牧場主] rancher, [海の紳士] gentleman of the sea (an eagle -- "the bird
# talked!" is one of his lines), [フィッシャー] fisher, [神使] divine envoy,
# [ガイド] guide, [住民] islander, [わんぱくなチビっこ] rascal kitten,
# [ピュアなチビっこ] innocent kitten. ASCII only: Stb.set encodes latin-1.
NPCS = {
    1747: "[Travel Guide] Wedgy",
    1748: "[Storekeeper] Ferris",
    1749: "[Rancher] Calico",
    1750: "[Gentleman of the Sea] Lusiga",
    1753: "[Fisher] Chartres",
    1754: "[Divine Envoy] Miakis",
    1755: "[Guide] Lynx",
    1756: "[Islander] Guld",
    1757: "[Islander] Welf",
    1758: "[Rascal Kitten] Peter",
    1759: "[Innocent Kitten] Rex",
}
DROP_NPCS = {1774}                 # nameless, no CHR entry, misnamed dialog
NPC_STRID_PREFIX = "LSKNPC"
NPC_PVP_NOPVP = b"0"               # townsfolk: normal cursor, not the attack one

# The clownfish recolours (クマノミ青/赤/紫). Butterflies 8-10 and the plain
# clownfish 319-321 the regen points also name are rows we already ship.
CRITTERS = {2785: "Blue Clownfish", 2786: "Red Clownfish", 2787: "Purple Clownfish"}
CRITTER_PVP = b"3"                 # PvpState::All, like every other monster row
CRITTER_STRID_PREFIX = "LSKMOB"

# ---- dialog
CON_FILES = [f"EM79-{n:03d}.CON" for n in range(1, 12)]
# (menu, item) option nodes whose click function reaches a Lua function our
# client does not register. Their check field is pointed at TA_Hidden.
HIDE = {
    "EM79-002.CON": [(3, 1), (3, 2)],      # my item center; withdraw-only storage
    "EM79-003.CON": [(5, 0), (5, 1)],      # pet goods (Jrose shop 266); board a pet
}
# Every node gated on one of Jrose's own chains is re-pointed at TA_Hidden too.
# "Never passes on our side" is not true of them: the cooking chain's "your bag
# is full" lines are *inverted* checks (TA_CookQ_Q32_10 returns 1 when
# chk-Q32_INV fails, and every trigger we do not ship fails), the node's text is
# empty here, and CEvent::Conversation closes the open window before it tests
# the text -- so Lusiga's greeting opened and was shut in the same tick, which
# reads as "the bird does not talk". 68 nodes across the eleven files.
HIDE_CHECK_PREFIXES = ("TA_CookQ_", "TA_TGS2015_", "TA_MyRoom_", "TA_GET_MyRoom",
                       "TA_Enough_MyRoom", "TA_openSpotBank")
APPENDIX_BEGIN = "-- SKAAJ BEGIN\n"
APPENDIX_END = "-- SKAAJ END\n"
APPENDIX_BODY = ("-- rose-next: options that need Jrose systems we do not ship "
                 "are gated on this.\nfunction TA_Hidden() return 0 end\n")
# Per-file additions. Wedgy exits: his bytecode names Jrose triggers, so the
# functions are redefined here (the appendix runs after the main blob).
APPENDIX_EXTRA = {
    "EM79-001.CON": (
        "function TA_gotoJunon() return 1 end\n"
        "function AT_gotoGrassland() QF_doQuestTrigger(\"Skaaj-TravelToPlains\") end\n"
        "function AT_gotoJunon() QF_doQuestTrigger(\"Skaaj-TravelToJunon\") end\n"
    ),
}
NODE_CHECK_OFF = 12

# Quest triggers appended to QP401.QSD, one pattern each so any one can be added
# on its own run. (pattern, trigger, kind, arg): kind "copy" takes the trigger's
# entities verbatim from Jrose's QN-SKA001.QSD; "warp" builds a REWD_007 to the
# given zone's `start`.
TRIGGERS = [
    ("SkaajLanguageCheck", "chk-Skaaj-Language-QSW", "copy", None),
    ("SkaajLanguageOn",    "Skaaj-Language-QSW-ON",  "copy", None),
    ("SkaajTravel",        "Skaaj-TravelToIsland",   "warp", ZONE_ROW),
    ("SkaajReturnPlains",  "Skaaj-TravelToPlains",   "warp", 22),
    ("SkaajReturnJunon",   "Skaaj-TravelToJunon",    "warp", 2),
]
REWD_007 = 0x01000000 | 7
TRAVEL_TRIGGER = "Skaaj-TravelToIsland"
TRAVEL_HOSTS = [(1104, "[Historian] Jones"), (2101, "[Interplanetary Guide] Nova")]
TRAVEL_KEY = "skaaj"
TRAVEL_TEXT = {
    "--hook": "Could you take me to the island of Skaaj?",
    "--confirm": "Skaaj, the cat-folk's island. The boat is ready when you are. Shall we?",
    "--accept": "Yes, take me to Skaaj.",
    "--decline": "Not just yet.",
}

# str_id -> English, written into ulngtb_con.ltb at the source id (the ids
# 22456-22650 are all free on our side, and the .CON nodes point at them).
# Deliberately absent: the "BasicMenu" root nodes (22456, 22465, ...) and the
# structural menu-1 labels -- an empty cell renders nothing, which is what
# skips them -- and every line behind a quest gate we do not ship.
STRINGS = {
    # EM79-001 Wedgy, travel guide
    22560: "Nyaa~ nii na~ ni~ onyaa oni~ omii purr purr purr naa myaa ni~ unyaa nii yan nyao.",
    22561: "Huh?",
    22562: "Ni~ onii na~ ni~ onyaa oni~ omyaa nyaa nii yan nyao nii?",
    22563: "I... have no idea what you're saying.",
    22564: "I arrange passage to the other planets. From here the boat sails for Junon. Shall I book you a trip?",
    22565: "Yes, take me to the Adventurer's Plains.",
    22566: "Yes, take me to Junon Polis.",
    22649: "No, not today.",
    # EM79-002 Ferris, storekeeper
    22567: "Ni~ ounya na~ ni~ omya ni~ nii onaa nya nii omyaa myaa nyaa!",
    22568: "(What on earth is he saying?)",
    22569: "Welcome, welcome! The master's away, so I look after this nice safe storehouse! Want to use it? Well? Do you?",
    22570: "I'd like to use the storage.",
    22573: "Not right now, thanks.",
    # EM79-003 Calico, rancher
    22574: "Mii purr purr purr nii nya~n nyaa nyaa ouni~ unya~n na~ nii onaa nao nyaa oni~ mya na~ nii myaa?",
    22575: "Er... sorry?",
    22576: "Mi~? Nyaa nii un-nii nii myaa?",
    22577: "(I can't understand a word.)",
    22578: "So you're the one looking after the little ones, eh? If you ever need anything for them, just say the word and I'll sell it to you.",
    22581: "I don't need anything right now.",
    # EM79-004 Lusiga, gentleman of the sea
    22584: ".........",
    22585: "(It's just staring at me.)",
    22586: "Ah, a visitor. This planet is a peaceful one; you will seldom find cause to draw a weapon here. Take your ease and enjoy your stay.",
    22587: "(The bird... talked!)",
    # EM79-005 Chartres, fisher
    22588: "Nyao nii nii u... nii onii naa nii unii nii ouni myaa...",
    22589: "(He's staring at his fishing rod...?)",
    22590: "Y'know, I just sit here with my line in the water and before I know it the day's gone. Funny, that.",
    22591: "Y-yeah, I suppose it is.",
    # EM79-006 Miakis, divine envoy -- the one you understand
    22592: "Well, well, a visitor! Welcome, welcome to the planet Skaaj.",
    22593: "You... I can understand you!?",
    22594: "I see... so you have only just arrived, and you are struggling because you cannot understand what everyone is saying.",
    22595: "Yes! How do I make sense of what they're saying?",
    22596: "You are a special being, created by the goddess Arua to save the Seven Hearts. Even if their words are lost on you now, if you try to understand them, if you open your heart to them, their words will surely reach you.",
    22597: "Open my heart... I see. I'll go and try talking to the others again!",
    22598: "May there be light wherever your path leads...",
    22599: "Thank you!",
    22600: "Hello there. Is something troubling you?",
    22601: "No, nothing in particular.",
    # EM79-007 Lynx, guide
    22602: "Nyao nii nii ona~ mya ni~ ni~ o! Nii ou mii myaa mi~ nii ou mii nii umyaa nyao!",
    22603: "(I can't understand a word.)",
    22604: "Welcome to the planet Skaaj! Enjoy your stay!",
    22605: "Thanks.",
    # EM79-008 Guld, islander
    22616: "Mii~... naa nyan myaa...",
    22617: "(I can't understand a word.)",
    22618: "On a warm, sunny day like this, the best thing in the world is to bask in the sun and doze off for a while.",
    22619: "Can't argue with that.",
    # EM79-009 Welf, islander
    22620: "Nii onii naa mya nii yan myaa. Nii ni~ ou nii myaa.",
    22621: "(I can't understand a word.)",
    22622: "I wonder what's for dinner tonight... I hope it's fish...",
    22623: "Fish would be nice.",
    # EM79-010 Peter, rascal kitten
    22624: "Mi~ mi~ nii onyaa oni~ na~ purr purr purr nii unyao nii na~ nyao nyaa ou~ ni~ unyao nii~!",
    22625: "(I can't understand a word.)",
    22626: "I'm the fastest runner on the whole island! Pretty amazing, huh!",
    22627: "Yeah, that's amazing.",
    # EM79-011 Rex, innocent kitten
    22628: "Mii naa nii nii onii umi~? Naa mya myaa nyaa oni~?",
    22629: "(I can't understand a word.)",
    22630: "Oh! A stranger! Mum says I mustn't talk to strangers. Where did you come from, stranger?",
    22631: "...Aren't you not supposed to be talking to me?",
    22632: "Oh, right... okay then, zipping my mouth shut!",
    22633: "Good idea.",
}
LTB_KEY = "SKAAJ-{}"


# -------------------------------------------------------------------- helpers
def load(name, fname):
    """Import a sibling script as a module without running its main()."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [fname, "--help"]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return mod


import rosedata as oro  # the shared data layer (was import-oro.py)
kk = load("import_karkia", "import-karkia.py")        # copy_new, economy splice
fate = load("import_oro_fate", "import-oro-fate.py")  # QSD + .CON codecs
tk = load("translate_karkia", "translate-karkia-dialog.py")   # .LTB codec
travel = load("add_oro_travel", "add-oro-travel.py")  # .ZON event positions


def P(root, rel):
    return os.path.join(root, rel.replace("\\", "/"))


def S(src, rel):
    return oro.Stb(P(src, rel))


def O(ours, rel):
    return oro.Stb(P(ours, rel))


def mob_con_name(extra):
    """The .CON basename a MOB placement carries: i32 AI, then one pascal string."""
    n = extra[4]
    return extra[5:5 + n].decode("latin-1")


def canon_con(name):
    """EM79-001.con, exactly as the LIST_EVENT cell's basename reads."""
    stem = os.path.splitext(name)[0].upper()
    return stem[:5] + stem[5:].zfill(3) + ".con"


def con_set_check(blob, menu_idx, item_idx, func):
    """In-place rewrite of one node's 32-byte check-function field.

    Mirrors import-oro-fate's con_set_click: the menu collection's XOR key is
    derived from (sub-count, length), neither of which changes, so the body is
    decoded, patched and re-encoded without moving a byte.
    """
    out = bytearray(blob)
    base, menu_num = fate.con_menu_offsets(out)
    if not 0 <= menu_idx < menu_num:
        raise SystemExit(f"menu {menu_idx} out of range (have {menu_num})")
    mmt, = struct.unpack_from("<I", out, base + 4 * menu_idx)
    coll = base + mmt
    length, nsub = struct.unpack_from("<ii", out, coll)
    if not 0 <= item_idx < nsub:
        raise SystemExit(f"menu {menu_idx} item {item_idx} out of range (have {nsub})")
    key = fate.con_xor_key(nsub, length)
    body = bytearray(out[coll:coll + length])
    for i in range(8, len(body)):
        body[i] ^= key
    sub, = struct.unpack_from("<I", body, 8 + 4 * item_idx)
    name = func.encode("latin-1")
    if len(name) >= 32:
        raise SystemExit(f"check function name too long: {func}")
    body[sub + NODE_CHECK_OFF:sub + NODE_CHECK_OFF + 32] = name + b"\0" * (32 - len(name))
    for i in range(8, len(body)):
        body[i] ^= key
    out[coll:coll + length] = body
    return bytes(out)


def appendix_upsert(appendix, body):
    s = appendix.decode("latin-1")
    start = s.find(APPENDIX_BEGIN)
    if start >= 0:
        end = s.find(APPENDIX_END, start)
        if end >= 0:
            s = s[:start] + s[end + len(APPENDIX_END):]
    if s and not s.endswith("\n"):
        s += "\n"
    return (s + APPENDIX_BEGIN + body + APPENDIX_END).encode("latin-1")


def hidden_nodes(blob, name):
    """Every (menu, item) that ends up gated on TA_Hidden in `name`."""
    out = set(HIDE.get(name, []))
    _, menu_num = fate.con_menu_offsets(blob)
    for mi in range(menu_num):
        _, _, _, nsub = con_menu(blob, mi)
        for j in range(nsub):
            chk = fate.con_get_item(blob, mi, j)[2]
            if chk.startswith(HIDE_CHECK_PREFIXES):
                out.add((mi, j))
    return sorted(out)


def con_menu(blob, menu_idx):
    base, menu_num = fate.con_menu_offsets(blob)
    mmt, = struct.unpack_from("<I", blob, base + 4 * menu_idx)
    coll = base + mmt
    length, nsub = struct.unpack_from("<ii", blob, coll)
    return base, coll, length, nsub


def build_con(src_path, name):
    """Our version of one Skaaj dialog, derived from the pristine source."""
    blob = open(src_path, "rb").read()
    for menu, item in hidden_nodes(blob, name):
        blob = con_set_check(blob, menu, item, "TA_Hidden")
    head, lua, appendix = fate.con_split(blob)
    body = APPENDIX_BODY + APPENDIX_EXTRA.get(name, "")
    return fate.con_join(head, lua, appendix_upsert(appendix, body))


def write_if_changed(path, blob, dry, backup=True):
    if os.path.isfile(path) and open(path, "rb").read() == blob:
        return False
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if backup and os.path.isfile(path):
            oro.backup(path)
        with open(path, "wb") as fh:
            fh.write(blob)
    return True


def ifo_files(folder):
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(".ifo"))


def zone_zon(ours, row):
    z = O(ours, ZONE_STB_REL)
    rel = z.get(row, 1).decode("latin-1").strip()
    if not rel:
        raise SystemExit(f"LIST_ZONE row {row} has no zone file")
    return P(ours, rel)


def landing(ours, row, src=None):
    if row == ZONE_ROW and src and not O(ours, ZONE_STB_REL).get(row, 1).strip():
        zon = os.path.join(P(src, MAPS_REL), "SKTOWN.ZON")   # stage 1 not applied yet
    else:
        zon = zone_zon(ours, row)
    pos = travel.zon_event_positions(zon)
    if "start" not in pos:
        raise SystemExit(f"zone {row}: no 'start' event (have {sorted(pos)})")
    x, y = pos["start"]
    return int(round(x)), int(round(y))


def all_qsd_triggers(ours):
    """{trigger name: file} across every QSD we ship -- names are global."""
    d = P(ours, r"3DDATA\QUESTDATA")
    out = {}
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".qsd"):
            continue
        for name, _ents, _raw in fate.qsd_walk(open(os.path.join(d, f), "rb").read()):
            out.setdefault(name, f)
    return out


# ------------------------------------------------------------------- stage 1
def stage1(ours, src, src_index, dry):
    print("stage 1 -- terrain, art, tiles, the zone row")
    s_map, d_map = P(src, MAPS_REL), P(ours, MAPS_REL)
    if not os.path.isdir(s_map):
        raise SystemExit(f"source map folder missing: {s_map}")
    template = kk.economy_template(ours)

    # 1a. the map folder, recursively (every chunk has a LIGHTMAP subfolder)
    copied = rewritten = spliced = 0
    for base, _, names in os.walk(s_map):
        sub = os.path.relpath(base, s_map)
        dbase = d_map if sub == "." else os.path.join(d_map, sub)
        for name in sorted(names):
            sp, dp = os.path.join(base, name), os.path.join(dbase, name)
            if os.path.isfile(dp):
                continue
            low = name.lower()
            blob = None
            if low.endswith(".ifo"):
                buf, bounds = oro.read_ifo(sp)
                repl = {}
                for lt in (oro.LUMP_MOB, oro.LUMP_REGEN, oro.LUMP_WARP):
                    off, end = oro.lump_block(bounds, lt)
                    if off is None or buf[off:off + 4] == b"\0\0\0\0":
                        continue
                    _, trailing = oro.read_lump(buf, bounds, lt)
                    repl[lt] = oro.build_object_lump([], trailing)
                blob = oro.build_ifo(bounds, buf, repl) if repl else buf
                rewritten += 1 if repl else 0
            elif low.endswith(".zon"):
                blob = kk.zon_with_economy(sp, template)
                if blob is None:
                    blob = open(sp, "rb").read()
                else:
                    spliced += 1
            if not dry:
                os.makedirs(dbase, exist_ok=True)
                if blob is None:
                    shutil.copyfile(sp, dp)
                else:
                    with open(dp, "wb") as fh:
                        fh.write(blob)
            copied += 1
    print(f"    {'map files':26s} {copied:5d} new  ({rewritten} .IFO with entity lumps "
          f"emptied, {spliced} .ZON given a LUMP_ECONOMY)")

    # 1b. terrain tiles named by the .ZON
    zon = [f for f in os.listdir(s_map) if f.lower().endswith(".zon")][0]
    tiles = {t for t in oro.zon_tiles(os.path.join(s_map, zon)) if "\\" in t or "/" in t}
    new_dds = list(kk.copy_new(tiles, src_index, ours, dry, "terrain tiles")[3])

    # 1c. the object tables and everything they name. The IFOs place no effects
    # or sounds, so the tables are the whole inventory.
    s_art = P(src, ART_REL)
    zsc_rels, art = [], set()
    for name in sorted(os.listdir(s_art)):
        if name.lower().endswith(".zsc"):
            zsc_rels.append(f"{ART_REL}\\{name}")
            art |= oro.zsc_asset_refs(oro.Zsc(os.path.join(s_art, name)))
    art = {a for a in art if "\\" in a or "/" in a}
    art |= kk.effect_chain({a for a in art if a.lower().endswith(".eft")}, src_index)
    kk.copy_new(zsc_rels, src_index, ours, dry, "object tables")
    new_dds += kk.copy_new(art, src_index, ours, dry, "decoration art")[3]

    # 1d. the zone row
    src_zone, zstb = S(src, ZONE_STB_REL), O(ours, ZONE_STB_REL)
    if not src_zone.occupied(SRC_ZONE_ROW):
        raise SystemExit(f"source LIST_ZONE row {SRC_ZONE_ROW} is empty")
    if zstb.occupied(ZONE_ROW) and zstb.get(ZONE_ROW, ZONE_NAME_COL) != ZONE_NAME.encode():
        raise SystemExit(f"our LIST_ZONE row {ZONE_ROW} is occupied by "
                         f"{zstb.get(ZONE_ROW, 0)!r}")
    before = list(zstb.d[ZONE_ROW])
    for c in range(ZONE_COPY_COLS):
        zstb.set(ZONE_ROW, c, src_zone.get(SRC_ZONE_ROW, c))
    zstb.set(ZONE_ROW, ZONE_NAME_COL, ZONE_NAME)
    zstb.set(ZONE_ROW, ZONE_SKY_COL, ZONE_SKY)
    zstb.set(ZONE_ROW, ZONE_STL_COL, ZONE_STL_KEY)
    changed = zstb.d[ZONE_ROW] != before
    if changed:
        zstb.save(dry)
    print(f"    {'LIST_ZONE.STB':26s} row {ZONE_ROW} "
          f"{'written' if changed else 'already in place'}")

    zstl = oro.Stl(P(ours, ZONE_STL_REL))
    if not zstl.has(ZONE_STL_KEY):
        zstl.append(ZONE_STL_KEY, int(ZONE_STL_KEY[4:]), ZONE_NAME)
        zstl.save(dry)
        print(f"    {'LIST_ZONE_S.STL':26s} +1 key {ZONE_STL_KEY} (now {len(zstl.keys)})")
    else:
        print(f"    {'LIST_ZONE_S.STL':26s} {ZONE_STL_KEY} already present")

    # 1e. BGM lives outside data/, in the deployed game folder
    bgm_s = P(src, BGM_SRC_REL)
    bgm_d = os.path.join(BGM_DEPLOY_DIR, os.path.basename(bgm_s))
    if os.path.isdir(BGM_DEPLOY_DIR) and os.path.isfile(bgm_s):
        if os.path.isfile(bgm_d):
            print(f"    {'BGM':26s} {os.path.basename(bgm_s)} already deployed")
        else:
            if not dry:
                shutil.copyfile(bgm_s, bgm_d)
            print(f"    {'BGM':26s} {os.path.basename(bgm_s)} -> {BGM_DEPLOY_DIR}")
    else:
        print(f"    NOTE: copy {BGM_SRC_REL} into the deployed game's Sound\\BGM by hand")

    if new_dds:
        print(f"\n    NOTE: {len(new_dds)} new .dds have no mip chain. Run")
        print("          scripts/add-dds-mipmaps.py --subdir 3DDATA/SKAAJ and")
        print("          --subdir 3DDATA/TERRAIN/TILES/SKAAJ (see the Karkia import).")


# ------------------------------------------------------------------- stage 2
def placements_from_source(src):
    """{ifo name: (objs, trailing)} of the source MOB lumps, canonicalised."""
    s_map = P(src, MAPS_REL)
    out = {}
    for name in ifo_files(s_map):
        buf, bounds = oro.read_ifo(os.path.join(s_map, name))
        objs, trailing = oro.read_lump(buf, bounds, oro.LUMP_MOB)
        if not objs:
            continue
        keep = []
        for o in objs:
            if o["obj_id"] in DROP_NPCS:
                continue
            want = canon_con(mob_con_name(o["extra"]))
            o["extra"] = o["extra"][:4] + oro.put_bstr(want.encode("latin-1"))
            keep.append(o)
        if keep:
            out[name] = (keep, trailing)
    return out


def stage2(ours, src, src_index, dry):
    print("stage 2 -- the townsfolk")
    placements = placements_from_source(src)
    ids = sorted({o["obj_id"] for objs, _ in placements.values() for o in objs})
    unknown = [i for i in ids if i not in NPCS]
    if unknown:
        raise SystemExit(f"placements name NPCs with no English name: {unknown}")
    print(f"    {'placements':26s} {sum(len(o) for o, _ in placements.values())} "
          f"across {len(placements)} .IFO files, {len(ids)} NPCs "
          f"({len(DROP_NPCS)} dropped: {sorted(DROP_NPCS)})")

    # 2a. LIST_NPC rows at their native ids
    src_npc, our_npc = S(src, NPC_STB_REL), O(ours, NPC_STB_REL)
    our_npc.grow_to(max(ids) + 1)
    written, kept = [], []
    for i in ids:
        # Judged by name, not by occupied(): rows 1747-1759 hold stray cells with
        # no name behind them (the same trap the Oro import documents), and a
        # nameless row is a free row -- the copy overwrites every column anyway.
        cur = our_npc.get(i, 0).decode("latin-1").strip()
        if cur == NPCS[i]:
            kept.append(i)
            continue
        if cur:
            raise SystemExit(f"our LIST_NPC row {i} is occupied by {cur!r}")
        if not src_npc.get(i, 0).strip():
            raise SystemExit(f"NPC {i} is not in the source LIST_NPC")
        for c in range(min(our_npc.cols, src_npc.cols)):
            our_npc.set(i, c, src_npc.get(i, c))
        our_npc.set(i, 0, NPCS[i])
        our_npc.set(i, oro.NPC_STRID_COL, f"{NPC_STRID_PREFIX}{i}")
        our_npc.set(i, oro.NPC_PVP_COL, NPC_PVP_NOPVP)
        for c in oro.NPC_SELL_TAB_COLS:          # 1749's tab 266 is Jrose pet goods
            our_npc.set(i, c, b"")
        written.append(i)
    print(f"    {'LIST_NPC.STB':26s} {len(written)} rows written, {len(kept)} already ours")

    our_stl = oro.Stl(P(ours, NPC_STL_REL))
    nnames = 0
    for i in ids:
        key = f"{NPC_STRID_PREFIX}{i}"
        if not our_stl.has(key):
            our_stl.append(key, i, NPCS[i])
            nnames += 1
    print(f"    {'LIST_NPC_S.STL':26s} +{nnames} keys (now {len(our_stl.keys)})")

    # 2b. dialog registrations: the source cell verbatim (a full VFS path, which
    # is what the client Load()s), labelled with our English name.
    src_ev, our_ev = S(src, EVENT_STB_REL), O(ours, EVENT_STB_REL)
    have = {}
    for r in range(our_ev.rows):
        cell = our_ev.get(r, EVENT_FILE_COL).decode("latin-1").strip()
        if cell:
            have[os.path.basename(cell.replace("\\", "/")).lower()] = r
    src_by_base = {}
    for r in range(src_ev.rows):
        cell = src_ev.get(r, EVENT_FILE_COL).decode("latin-1").strip()
        if cell:
            src_by_base[os.path.basename(cell.replace("\\", "/")).lower()] = r
    free = (r for r in range(1, our_ev.rows)
            if not our_ev.get(r, EVENT_FILE_COL).strip())
    cons = {o["obj_id"]: mob_con_name(o["extra"])
            for objs, _ in placements.values() for o in objs}
    ev_written, con_rels = [], set()
    for i in ids:
        base = cons[i].lower()
        if base in have:
            continue
        s = src_by_base.get(base)
        if s is None:
            raise SystemExit(f"NPC {i}: {cons[i]} is in no source LIST_EVENT row")
        r = next(free)
        for c in range(min(our_ev.cols, src_ev.cols)):
            our_ev.set(r, c, src_ev.get(s, c))
        our_ev.set(r, 0, NPCS[i])
        have[base] = r
        ev_written.append(r)
    for i in ids:
        con_rels.add(f"{EVENT_DIR_REL}\\{canon_con(cons[i])}")
    print(f"    {'LIST_EVENT.STB':26s} +{len(ev_written)} rows {ev_written}")
    # copied verbatim here; stage 4 rewrites them from the source with our edits
    kk.copy_new(con_rels, src_index, ours, dry, ".CON dialogs")

    our_npc.save(dry)
    our_ev.save(dry)
    if nnames:
        our_stl.save(dry)

    # 2c. models. Our CHR has orphan entries at some of these ids (a "noname"
    # model with no LIST_NPC row); import_characters keeps whatever it finds,
    # so a slot whose row was blank a moment ago is cleared first.
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    cleared = []
    for i in written:
        if i < len(chr_.chars) and chr_.chars[i] is not None:
            chr_.chars[i] = None
            cleared.append(i)
    if cleared:
        chr_.save(dry)
        print(f"    {'LIST_NPC.CHR':26s} cleared orphan entries {cleared}"
              + (" (dry run: import_characters below still sees them)" if dry else ""))
    oro.import_characters(ids, ours, src, dry, "NPC")

    # 2d. the placements, last
    fill_lump(ours, placements, oro.LUMP_MOB, dry, "IFO mob lumps")


def fill_lump(ours, per_file, lump, dry, label):
    d_map = P(ours, MAPS_REL)
    files = n = 0
    for name, (objs, trailing) in sorted(per_file.items()):
        dp = os.path.join(d_map, name)
        if not os.path.isfile(dp):
            if dry:
                files += 1
                n += len(objs)
                continue                       # stage 1 not applied yet
            raise SystemExit(f"{dp}: run --stage 1 first")
        dbuf, dbounds = oro.read_ifo(dp)
        doff, dend = oro.lump_block(dbounds, lump)
        if doff is None:
            raise SystemExit(f"{dp}: no lump {lump} to fill")
        blob = oro.build_object_lump(objs, trailing)
        if dbuf[doff:dend] == blob:
            continue
        out = oro.build_ifo(dbounds, dbuf, {lump: blob})
        files += 1
        n += len(objs)
        if not dry:
            with open(dp, "wb") as fh:
                fh.write(out)
            vbuf, vbounds = oro.read_ifo(dp)
            voff, vend = oro.lump_block(vbounds, lump)
            if vbuf[voff:vend] != blob:
                raise SystemExit(f"VERIFY FAILED: {dp} lump {lump} mismatch")
    print(f"    {label:26s} {n} records into {files} files"
          + ("" if files else " (already in place)"))


# ------------------------------------------------------------------- stage 3
def regen_from_source(src):
    s_map = P(src, MAPS_REL)
    out, spawned = {}, set()
    for name in ifo_files(s_map):
        buf, bounds = oro.read_ifo(os.path.join(s_map, name))
        objs, trailing = oro.read_lump(buf, bounds, oro.LUMP_REGEN)
        if not objs:
            continue
        out[name] = (objs, trailing)
        for o in objs:
            spawned.update(oro.regen_mob_ids(o["extra"]))
    return out, spawned


def stage3(ours, src, src_index, dry):
    print("stage 3 -- the critters")
    regen, spawned = regen_from_source(src)
    src_npc, our_npc = S(src, NPC_STB_REL), O(ours, NPC_STB_REL)
    named = lambda i: bool(our_npc.get(i, 0).strip())
    ours_already = sorted(i for i in spawned if i not in CRITTERS and named(i))
    missing = sorted(i for i in spawned if i not in CRITTERS and not named(i))
    if missing:
        raise SystemExit(f"regen points name monsters we neither ship nor import: {missing}")
    print(f"    {'roster':26s} {sorted(spawned)} -- {len(ours_already)} already ours, "
          f"{len(CRITTERS)} to import")

    ids = sorted(CRITTERS)
    our_npc.grow_to(max(ids) + 1)
    written = []
    for i in ids:
        cur = our_npc.get(i, 0).decode("latin-1").strip()
        if cur == CRITTERS[i]:
            continue
        if cur:
            raise SystemExit(f"our LIST_NPC row {i} is occupied by {cur!r}")
        for c in range(min(our_npc.cols, src_npc.cols)):
            our_npc.set(i, c, src_npc.get(i, c))
        our_npc.set(i, 0, CRITTERS[i])
        our_npc.set(i, oro.NPC_STRID_COL, f"{CRITTER_STRID_PREFIX}{i}")
        our_npc.set(i, oro.NPC_PVP_COL, CRITTER_PVP)
        written.append(i)
    print(f"    {'LIST_NPC.STB':26s} {len(written)} rows written")
    our_stl = oro.Stl(P(ours, NPC_STL_REL))
    nnames = 0
    for i in ids:
        key = f"{CRITTER_STRID_PREFIX}{i}"
        if not our_stl.has(key):
            our_stl.append(key, i, CRITTERS[i])
            nnames += 1
    print(f"    {'LIST_NPC_S.STL':26s} +{nnames} keys")
    # AI: GE_fish_s.aip, row 94 -- the same row and file as our own clownfish
    src_ai, our_ai = S(src, r"3DDATA\STB\FILE_AI.STB"), O(ours, r"3DDATA\STB\FILE_AI.STB")
    for i in ids:
        a = int(our_npc.get(i, oro.NPC_AI_COL) or 0)
        if a and (a >= our_ai.rows or our_ai.get(a, 0) != src_ai.get(a, 0)):
            raise SystemExit(f"critter {i}: AI row {a} differs between the tables")
    our_npc.save(dry)
    if nnames:
        our_stl.save(dry)
    oro.import_characters(ids, ours, src, dry, "critter")
    fill_lump(ours, regen, oro.LUMP_REGEN, dry, "IFO regen lumps")


# ------------------------------------------------------------------- stage 4
def stage4(ours, src, src_index, dry):
    print("stage 4 -- dialog and travel")

    # 4a. quest triggers, into QP401.QSD
    qsd_path = P(ours, QSD_REL)
    blob = open(qsd_path, "rb").read()
    src_qsd = open(P(src, SRC_QSD_REL), "rb").read()
    tmpl = fate.qsd_find_entity(open(P(ours, QSD_TEMPLATE_REL), "rb").read(),
                                QSD_TEMPLATE_TRIGGER, REWD_007)
    if tmpl is None:
        raise SystemExit(f"no REWD_007 template in {QSD_TEMPLATE_TRIGGER}")
    everywhere = all_qsd_triggers(ours)
    wrote = 0
    for pattern, trigger, kind, arg in TRIGGERS:
        if fate.qsd_has_trigger(blob, trigger):
            continue
        if trigger in everywhere:
            raise SystemExit(f"trigger {trigger} already exists in {everywhere[trigger]}")
        if kind == "copy":
            ents = [raw for name, es, raw in fate.qsd_walk(src_qsd) if name == trigger]
            if not ents:
                raise SystemExit(f"{trigger} not in the source QSD")
            trig = ents[0]
        else:
            x, y = landing(ours, arg, src if dry else None)
            # STR_REWD_007: int zone; int x; int y; BYTE party option (0: only me)
            rew = fate.qsd_patch(tmpl, (0, "<iii", (arg, x, y)), (12, "<B", (0,)))
            trig = fate.qsd_build_trigger(trigger, [], [rew])
            print(f"    {trigger:26s} -> zone {arg} at ({x}, {y})")
        out = fate.qsd_append_pattern(blob, pattern, [trig])
        ok, consumed = fate.qsd_parse_ok(out)
        if not ok or not fate.qsd_has_trigger(out, trigger):
            raise SystemExit(f"rebuilt QSD does not re-parse ({consumed}/{len(out)})")
        blob = out
        wrote += 1
    if wrote:
        fate.write_file(qsd_path, blob, dry)
    print(f"    {'QP401.QSD':26s} +{wrote} triggers (now {len(blob)} bytes)")

    # 4b. English text, at the source string ids
    ltb_path = P(ours, LTB_REL)
    ltb = tk.Ltb(ltb_path)
    orig_rows = len(ltb.rows)
    ltb.grow_to(max(STRINGS) + 1)
    changed = 0
    for sid, text in sorted(STRINGS.items()):
        key, cur = ltb.text(sid, 0), ltb.text(sid, 1)
        if cur == text and key == LTB_KEY.format(sid):
            continue
        if key and not key.startswith("SKAAJ-"):
            raise SystemExit(f"ulngtb_con.ltb row {sid} is taken by {key!r}")
        ltb.set_all_langs(sid, LTB_KEY.format(sid), text)
        changed += 1
    if changed:
        bak = os.path.join(ROOT, "build", "skaaj", "ulngtb_con.ltb.orig")
        if not dry:
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            if not os.path.isfile(bak):
                shutil.copyfile(ltb_path, bak)
            with open(ltb_path, "wb") as fh:
                fh.write(ltb.to_bytes())
            back = tk.Ltb(ltb_path)
            bad = [s for s, t in STRINGS.items() if back.text(s, 1) != t]
            if bad:
                raise SystemExit(f"VERIFY FAILED: LTB rows {bad[:8]}")
    print(f"    {'ulngtb_con.ltb':26s} {changed} of {len(STRINGS)} strings written "
          f"({orig_rows} -> {len(ltb.rows)} rows)")

    # 4c. the dialogs themselves, rebuilt from the pristine source each run
    n = 0
    for name in CON_FILES:
        sp = os.path.join(P(src, EVENT_DIR_REL), name)
        if not os.path.isfile(sp):
            raise SystemExit(f"source dialog missing: {sp}")
        blob = build_con(sp, name)
        dp = os.path.join(P(ours, EVENT_DIR_REL), name)
        if write_if_changed(dp, blob, dry, backup=False):
            n += 1
        if not dry:
            head, lua, appendix = fate.con_split(open(dp, "rb").read())
            if APPENDIX_BODY.encode("latin-1") not in appendix:
                raise SystemExit(f"VERIFY FAILED: {name} appendix")
    hidden = sum(len(hidden_nodes(open(os.path.join(P(src, EVENT_DIR_REL), f), "rb").read(), f))
                 for f in CON_FILES)
    print(f"    {'.CON dialogs':26s} {n} of {len(CON_FILES)} rewritten "
          f"({hidden} nodes gated on TA_Hidden, appendix added)")

    # 4d. the way in, on the two NPCs that already do interplanetary travel
    if not os.path.isfile(QUEST_EDITOR):
        print(f"    NOTE: {QUEST_EDITOR} not built; run by hand:")
        for npc, who in TRAVEL_HOSTS:
            print(f"          quest-editor con-warp data {npc} {TRAVEL_KEY} {TRAVEL_TRIGGER} --write")
        return
    for npc, who in TRAVEL_HOSTS:
        cmd = [QUEST_EDITOR, "con-warp", ours, str(npc), TRAVEL_KEY, TRAVEL_TRIGGER]
        for flag, text in TRAVEL_TEXT.items():
            cmd += [flag, text]
        if not dry:
            cmd.append("--write")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"con-warp {npc} failed:\n{r.stdout}\n{r.stderr}")
        line = next((l for l in r.stdout.splitlines() if "warp option" in l), r.stdout.strip())
        print(f"    {who:26s} {line.strip()[:90]}")
    print("\n    Miakis (the divine envoy, by the plaza) is the one to talk to first:")
    print("    her 'Thank you!' sets quest switch 90 and the island starts speaking.")


# -------------------------------------------------------------------- verify
def verify(ours, src):
    print("verify")
    bad = []

    def check(cond, what):
        print(f"    {'ok ' if cond else 'BAD'} {what}")
        if not cond:
            bad.append(what)

    zstb = O(ours, ZONE_STB_REL)
    check(zstb.get(ZONE_ROW, 0) == ZONE_NAME.encode(), f"LIST_ZONE row {ZONE_ROW} is {ZONE_NAME}")
    check(zstb.get(ZONE_ROW, ZONE_SKY_COL) == ZONE_SKY.encode(), "sky column explicit")
    check(oro.Stl(P(ours, ZONE_STL_REL)).has(ZONE_STL_KEY), f"STL key {ZONE_STL_KEY}")
    d_map = P(ours, MAPS_REL)
    ifos = ifo_files(d_map) if os.path.isdir(d_map) else []
    check(len(ifos) == 30 and os.path.isfile(os.path.join(d_map, "SKTOWN.ZON")),
          f"map folder: {len(ifos)} .IFO + SKTOWN.ZON")
    if ifos:
        buf, bounds = oro.read_ifo(os.path.join(d_map, "SKTOWN.ZON"))
        check(oro.lump_block(bounds, kk.ZON_LUMP_ECONOMY)[0] is not None, "ZON has LUMP_ECONOMY")
    for rel in (f"{ART_REL}\\LIST_DECO_SKAAJ.ZSC", f"{ART_REL}\\LIST_CNST_SKAAJ.ZSC"):
        check(os.path.isfile(P(ours, rel)), rel)
    if os.path.isfile(P(ours, f"{ART_REL}\\LIST_DECO_SKAAJ.ZSC")):
        refs = oro.zsc_asset_refs(oro.Zsc(P(ours, f"{ART_REL}\\LIST_DECO_SKAAJ.ZSC")))
        idx = kk.index_tree(ours)
        missing = [r for r in refs if kk.key_of(r) not in idx]
        check(not missing, f"decoration art present ({len(refs)} refs, {len(missing)} missing)")
    if os.path.isfile(os.path.join(d_map, "SKTOWN.ZON")):
        idx = kk.index_tree(ours)
        tiles = oro.zon_tiles(os.path.join(d_map, "SKTOWN.ZON"))
        missing = [t for t in tiles if kk.key_of(t) not in idx]
        check(not missing, f"terrain tiles present ({len(tiles)}, {len(missing)} missing)")

    npc = O(ours, NPC_STB_REL)
    stl = oro.Stl(P(ours, NPC_STL_REL))
    chr_ = oro.Chr(P(ours, NPC_CHR_REL))
    for table, prefix in ((NPCS, NPC_STRID_PREFIX), (CRITTERS, CRITTER_STRID_PREFIX)):
        rows = [i for i in table if npc.get(i, 0).decode("latin-1") == table[i]]
        keys = [i for i in table if stl.has(f"{prefix}{i}")]
        chrs = [i for i in table if i < len(chr_.chars) and chr_.chars[i] is not None]
        check(len(rows) == len(table), f"{prefix}: {len(rows)}/{len(table)} LIST_NPC rows")
        check(len(keys) == len(table), f"{prefix}: {len(keys)}/{len(table)} STL keys")
        check(len(chrs) == len(table), f"{prefix}: {len(chrs)}/{len(table)} CHR entries")
    check(all(not npc.get(i, c).strip() for i in NPCS for c in oro.NPC_SELL_TAB_COLS),
          "no townsfolk carries a Jrose shop tab")

    ev = O(ours, EVENT_STB_REL)
    reg = {os.path.basename(ev.get(r, EVENT_FILE_COL).decode("latin-1").replace("\\", "/")).lower()
           for r in range(ev.rows) if ev.get(r, EVENT_FILE_COL).strip()}
    want = {canon_con(f).lower() for f in CON_FILES}
    check(want <= reg, f"LIST_EVENT registers {len(want & reg)}/{len(want)} dialogs")
    check(all(os.path.isfile(os.path.join(P(ours, EVENT_DIR_REL), f)) for f in CON_FILES),
          "all 11 .CON files present")

    placed, regen_pts, refs_ok = 0, 0, True
    for name in ifos:
        buf, bounds = oro.read_ifo(os.path.join(d_map, name))
        objs, _ = oro.read_lump(buf, bounds, oro.LUMP_MOB)
        for o in objs or []:
            placed += 1
            if mob_con_name(o["extra"]).lower() not in reg:
                refs_ok = False
        objs, _ = oro.read_lump(buf, bounds, oro.LUMP_REGEN)
        regen_pts += len(objs or [])
        objs, _ = oro.read_lump(buf, bounds, oro.LUMP_WARP)
        if objs:
            check(False, f"{name} still carries the housing warp gate")
    check(placed == len(NPCS), f"{placed}/{len(NPCS)} NPC placements")
    check(refs_ok, "every placement's .CON is registered")
    check(regen_pts == 21, f"{regen_pts}/21 regen points")

    qsd = open(P(ours, QSD_REL), "rb").read()
    have = [t for _, t, _, _ in TRIGGERS if fate.qsd_has_trigger(qsd, t)]
    check(len(have) == len(TRIGGERS), f"QP401.QSD holds {len(have)}/{len(TRIGGERS)} triggers")
    if os.path.isfile(P(ours, LTB_REL)):
        ltb = tk.Ltb(P(ours, LTB_REL))
        n = sum(1 for s, t in STRINGS.items() if ltb.text(s, 1) == t)
        check(n == len(STRINGS), f"ulngtb_con.ltb: {n}/{len(STRINGS)} English strings")
    n, leaks = 0, []
    for name in CON_FILES:
        dp = os.path.join(P(ours, EVENT_DIR_REL), name)
        if not os.path.isfile(dp):
            continue
        blob = open(dp, "rb").read()
        _, _, appendix = fate.con_split(blob)
        ok = APPENDIX_BODY.encode("latin-1") in appendix
        ok &= all(fate.con_get_item(blob, m, i)[2] == "TA_Hidden" for m, i in HIDE.get(name, []))
        _, menu_num = fate.con_menu_offsets(blob)
        for mi in range(menu_num):
            for j in range(con_menu(blob, mi)[3]):
                if fate.con_get_item(blob, mi, j)[2].startswith(HIDE_CHECK_PREFIXES):
                    leaks.append(f"{name}:{mi}/{j}")
        n += ok
    check(n == len(CON_FILES), f"{n}/{len(CON_FILES)} dialogs carry TA_Hidden")
    check(not leaks, f"no node still gated on a Jrose-only check ({len(leaks)} leak)")
    # The way in: con-warp appends to whichever .CON each host's placement names,
    # so count the dialogs whose appendix fires the trigger rather than guess.
    ev_dir = P(ours, EVENT_DIR_REL)
    carriers = []
    for f in sorted(os.listdir(ev_dir)):
        if not f.lower().endswith(".con") or f.upper().startswith("EM79-"):
            continue
        _, _, appendix = fate.con_split(open(os.path.join(ev_dir, f), "rb").read())
        if TRAVEL_TRIGGER.encode() in appendix:
            carriers.append(f)
    check(len(carriers) >= len(TRAVEL_HOSTS),
          f"{len(carriers)} dialogs offer {TRAVEL_TRIGGER} {carriers}")
    print("    " + ("ALL OK" if not bad else f"{len(bad)} problem(s)"))
    return 0 if not bad else 1


# ------------------------------------------------------------------ selftest
def selftest(ours, src):
    print("selftest -- every writer must reproduce its input byte for byte")
    s_map = P(src, MAPS_REL)
    for name in ifo_files(s_map) + ["SKTOWN.ZON"]:
        p = os.path.join(s_map, name)
        buf, bounds = oro.read_ifo(p)
        assert oro.build_ifo(bounds, buf, {}) == buf, name
        if name.lower().endswith(".ifo"):
            for lt in (oro.LUMP_MOB, oro.LUMP_REGEN, oro.LUMP_WARP):
                objs, trailing = oro.read_lump(buf, bounds, lt)
                if objs is None:
                    continue
                off, end = oro.lump_block(bounds, lt)
                assert oro.build_object_lump(objs, trailing) == buf[off:end], (name, lt)
    print("    30 .IFO + .ZON containers round-trip")
    for rel in (ZONE_STB_REL, NPC_STB_REL, EVENT_STB_REL, r"3DDATA\STB\FILE_AI.STB"):
        p = P(ours, rel)
        assert oro.Stb(p).to_bytes() == open(p, "rb").read(), rel
    for rel in (ZONE_STL_REL, NPC_STL_REL):
        p = P(ours, rel)
        assert oro.Stl(p).to_bytes() == open(p, "rb").read(), rel
    p = P(ours, NPC_CHR_REL)
    assert oro.Chr(p).to_bytes() == open(p, "rb").read(), "LIST_NPC.CHR"
    print("    LIST_ZONE / LIST_NPC / LIST_EVENT / FILE_AI / two STLs / CHR round-trip")
    p = P(ours, LTB_REL)
    ltb = tk.Ltb(p)
    # to_bytes() rebuilds the string pool, so the proof is that a re-read of the
    # rebuilt table holds every cell of the original, not byte identity.
    tmp = os.path.join(ROOT, "build", "skaaj", "selftest.ltb")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "wb") as fh:
        fh.write(ltb.to_bytes())
    back = tk.Ltb(tmp)
    os.remove(tmp)
    assert len(back.rows) == len(ltb.rows) and back.cols == ltb.cols
    assert all(back.rows[r] == ltb.rows[r] for r in range(len(ltb.rows)))
    print(f"    ulngtb_con.ltb rebuilds to the same {len(ltb.rows)} rows")
    for name in CON_FILES:
        p = os.path.join(P(src, EVENT_DIR_REL), name)
        blob = open(p, "rb").read()
        head, lua, appendix = fate.con_split(blob)
        assert fate.con_join(head, lua, appendix) == blob, name
        assert lua.startswith(b"\x1bLua"), f"{name}: Lua blob did not decode"
        for menu, item in HIDE.get(name, []):
            fate.con_get_item(blob, menu, item)
    print("    11 .CON dialogs split/join byte-identically, Lua decodes")
    for rel in (QSD_REL, QSD_TEMPLATE_REL):
        ok, consumed = fate.qsd_parse_ok(open(P(ours, rel), "rb").read())
        assert ok, rel
    ok, _ = fate.qsd_parse_ok(open(P(src, SRC_QSD_REL), "rb").read())
    assert ok
    names = {n for n, _, _ in fate.qsd_walk(open(P(src, SRC_QSD_REL), "rb").read())}
    assert {"chk-Skaaj-Language-QSW", "Skaaj-Language-QSW-ON"} <= names
    print("    QP401 / PVP10 / QN-SKA001 QSDs parse exactly")
    x, y = landing(ours, 2)
    assert 100_000 < x < 10_000_000 and 100_000 < y < 10_000_000, (x, y)
    print(f"    landing spot of zone 2 = ({x}, {y})")
    print("    selftest OK")


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", type=int, choices=(1, 2, 3, 4), action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--source", default=DEFAULT_SRC)
    args = ap.parse_args()
    ours = os.path.join(args.root, "data")
    src = args.source
    if not os.path.isdir(P(src, MAPS_REL)):
        raise SystemExit(f"source is not a Jrose client with Skaaj: {src}")
    if args.selftest:
        selftest(ours, src)
        return 0
    if args.verify:
        return verify(ours, src)
    if not args.stage:
        ap.error("give --stage N (1-4), --verify or --selftest")
    src_index = kk.index_tree(src)
    for st in sorted(set(args.stage)):
        {1: stage1, 2: stage2, 3: stage3, 4: stage4}[st](ours, src, src_index, args.dry_run)
        print()
    if args.dry_run:
        print("dry run: nothing written")
    else:
        print("done. Next: add-dds-mipmaps.py (see stage 1 note), delete the .bak files,")
        print("rebake the VFS, restart the servers, deploy client + data together.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
