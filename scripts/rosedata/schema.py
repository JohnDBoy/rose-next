"""Table schema and file locations the importers share (from import-oro.py, 2026-10-12).

Column numbers are **game** columns (editor column - 1). LIST_NPC: col 5/6 right
and left hand (the right hand resolves in LIST_WEAPON.ZSC, the left in
LIST_SUBWPN.ZSC), 16 AI row, 21-24 sell tabs, 27 NPC_TYPE (also the TARGETMARK
sprite index), 40 STL key, 43 our own PVP-state column (0 NoPvp for type-999
townspeople, 3 All for monsters: the client picks the cursor off it). LIST_NPC
cols 0-42 align between every dump we own; 43 is ours alone.

Every importer that copies rows from a reference dump reads these rather than
spelling the numbers again.
"""
import re

from rosefmt.ifo_lumps import (LUMP_EVENT_OBJECT, LUMP_MOB, LUMP_REGEN,  # noqa: F401
                               LUMP_WARP)

NUL = b"\x00"

# zmo: a mesh effect names its morph animation too (JDCE_NIGHT01.EFT, the Desert
# of the Dead church's night light); without it the copied effect has no motion.
ABS_ASSET_RE = re.compile(rb"3DDATA[\\/][0-9A-Za-z_\\/. -]+?\.(?:ptl|dds|tga|zms|zmo)", re.I)

BARE_TEXTURE_RE = re.compile(rb"[0-9A-Za-z_][0-9A-Za-z_-]*\.(?:dds|tga)", re.I)

ZONE_OBJ_TABLE_COL, ZONE_CNST_TABLE_COL = 11, 12

SKY_STB_REL = r"3DDATA\STB\LIST_SKY.STB"

PARTICLE_TEXTURE_DIR = r"3DDATA\EFFECT\PARTICLES\TEXTURE"

# ZONE_BG_IMAGE (col 7) is a LIST_SKY.STB row, and every Oro zone points at row 10,
# which is blank in ours -- the map editor reports "Map load failed during loading
# sky" and the client gets no sky mesh. The zone rows name three tables, not two:
# object (11), cnst (12) and this one.
ZONE_SKY_COL = 7

# Zone join/kill/dead triggers. RoseZA hangs its own PvP hooks on Muris and the
# Gates of Muris (PvP71-Enter, PvP82-Enter/Kill/Death) which live in QSDs we do not
# have; 27 of our own zones use PvP1301-340, so the Oro rows take that and leave
# kill/dead blank. An unresolved trigger is inert, but a name no QSD defines is a
# landmine for whoever adds Oro quests later.
ZONE_TRIGGER_COLS = (22, 23, 24)

# --- map-editor tile palettes -------------------------------------------------
# ZONETYPEINFO.STB maps a map's ZoneType -- an int in block 0 of its .ZON -- to
# the editor's tileset helper tables. It is editor-only: the client
# (CTERRAIN::ReadZoneINFO), the gameserver (CZoneFILE::ReadZoneINFO) and the
# worldserver all fseek straight past that field. With no row the editor logs
# "Unknown ZoneType N; using empty tile set" and the brush palette is blank.
#
# Our table stopped at 13. The Oro maps use 14 (OROIP), 15 (TOWN) and 16 (the ten
# surface maps) -- but 15 is also what our own Eldeon prison EZ01 declares, so
# RoseZA's "15 = Orlo Town" cannot be taken verbatim without giving EZ01 the wrong
# palette. Type 15 therefore keeps its retail meaning (EZ, which fixes EZ01's
# palette -- missing here since before Oro) and Muris moves to a new type 17.
# Rewriting a .ZON's ZoneType is safe precisely because nothing but the editor
# reads it.
ZONETYPE_STB_REL = r"3DDATA\TERRAIN\TILES\ZONETYPEINFO.STB"

NPC_CHR_REL = r"3DDATA\NPC\LIST_NPC.CHR"

PART_NPC_ZSC_REL = r"3DDATA\NPC\PART_NPC.ZSC"

# LUMP_* come from rosefmt.ifo_lumps (imported above)
# lumps stage 1 empties; stages 2 and 3 refill WARP and REGEN/MOB
LUMPS_STAGE1_EMPTY = (LUMP_MOB, LUMP_REGEN, LUMP_WARP, LUMP_EVENT_OBJECT)

NPC_AI_COL, NPC_STRID_COL, NPC_PVP_COL = 16, 40, 43

NPC_SELL_TAB_COLS = (21, 22, 23, 24)

EVENT_STB_REL = r"3DDATA\STB\LIST_EVENT.STB"

EVENT_FILE_COL = 3                 # EVENT_FILENAME

CON_LTB_REL = r"3DDATA\EVENT\ulngtb_con.ltb"

NPC_R_WEAPON_COL, NPC_L_WEAPON_COL = 5, 6

NPC_COPY_COLS = 43                 # 0..42 align; 43 is our own PVP-state column

# LIST_WEAPON columns that decide how a monster's attack *presents*. A blank
# WEAPON_BULLET_EFFECT on a ranged monster means the client's Get_BulletNO()
# skips Add_BULLET and the server's projectile path picks MeleeHitFrame, which
# nothing on a bow/gun motion consumes -- the monster then deals damage with no
# projectile, no hit and no sound. Cols 31-43 are structurally aligned between
# the two data sets even though the stat columns above them were rebalanced.
WEAPON_PRESENTATION_COLS = (38, 39, 40, 41, 42)

# --------------------------------------------------------- stage 3: monsters
LEVEL_PREFIX = re.compile(r"^\(\d+\)\s*")

# NPC_PVP_STATE (col 43) is ours-only, so it is authored rather than copied -- and
# it is not one value. The client picks the mouse cursor straight off it:
# CGameStateMain, case OBJ_NPC, `is_pvp_enabled() ? CURSOR_ATTACK : CURSOR_NPC`.
# Monsters want All (731 of our 743 use it); townspeople want NoPvp (163 of our
# 167 type-999 rows use it), or every merchant in Muris shows the attack cursor.
DEFAULT_PVP_STATE = b"3"           # PvpState::All      -- monsters

NPC_PVP_STATE = b"0"               # PvpState::NoPvp    -- type-999 NPCs

NPC_TYPE_COL = 27

NPC_TYPE_NPC = b"999"
