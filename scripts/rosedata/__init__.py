"""rosedata -- the data layer the importers and balance passes share.

One flat namespace holding, in order of where things live:

* the codecs, from ``rosefmt`` (``Stb``, ``Stl``, ``Zsc``, ``Chr``, ``Ltb``, the
  raw IFO lump view ``read_ifo`` / ``read_lump`` / ``build_ifo`` ... and the
  ``LUMP_*`` numbers, the CON string-id reader);
* the table schema (``rosedata.schema``: LIST_NPC column numbers, the PVP-state
  values, data-relative file paths, the asset-path patterns);
* file helpers (``rosedata.files``: ``rel_path``, ``norm``, ``copy_files``,
  ``backup``, ``effect_chain``, ``find_asset``);
* the ZON questions (``rosedata.zone``: ``zon_tiles``, ``zon_events``,
  ``zon_zone_type``) and the character importer (``rosedata.npc``:
  ``import_characters``, ``regen_mob_ids``, ``StringPool``, ``clean_npc_name``).

Until 2026-10-12 all of this lived inside ``import-oro.py``, the RoseZA-era Oro
importer, and 73 scripts loaded that 2,600-line importer with ``importlib`` to
reach it. The importer itself was retired with the 667 Oro (its stages are in
git history before commit ee1ca094); the shared parts are here, with the same
names, so ``import rosedata as oro`` is a drop-in for what ``load_oro()`` gave.

Import from a script with::

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rosedata as oro
"""
import os as _os
import sys as _sys

_scripts = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _scripts not in _sys.path:
    _sys.path.insert(0, _scripts)

from rosefmt import Chr, Ltb, Stb, Stl, Zsc  # noqa: E402,F401
from rosefmt.binio import FormatError, read_vstr as read_pstr  # noqa: E402,F401
from rosefmt.condialog import (CON_HEADER_LEN, CON_NODE, CON_STR_ID_OFF,  # noqa: E402,F401
                               con_str_ids, con_xor_key)
from rosefmt.ifo_lumps import (LUMP_COLLISION, LUMP_EFFECT, LUMP_EVENT_OBJECT,  # noqa: E402,F401
                               LUMP_MOB, LUMP_OBJECT, LUMP_REGEN, LUMP_SOUND,
                               LUMP_WARP, OBJ_FIXED, IfoReader, build_ifo,
                               build_object_lump, lump_block, parse_object_lump,
                               put_bstr, read_ifo, read_lump)
from rosefmt.ltb import LTB_INDEX_ENTRY  # noqa: E402,F401
from rosefmt.qsd import (qsd_drop_conditions, qsd_find_entity, qsd_has_trigger,  # noqa: E402,F401
                         qsd_item_refs, qsd_pstr, qsd_quest_refs, qsd_remap_items)
from rosefmt.stl import STL_FIELDS  # noqa: E402,F401
from rosefmt.tsi import tsi_sprites  # noqa: E402,F401
from rosefmt.zsc import (MAX_MESH_ANI_TYPE, PROP_PATH_TAGS, SWITCH_ANI,  # noqa: E402,F401
                         SWITCH_CNST_ANI, asset_refs as zsc_asset_refs, prop_paths)

from .schema import *  # noqa: E402,F401,F403
from .files import (backup, copy_files, effect_chain, find_asset, find_qsd,  # noqa: E402,F401
                    norm, rel_path)
from .zone import zon_events, zon_tiles, zon_zone_type  # noqa: E402,F401
from .npc import StringPool, clean_npc_name, import_characters, regen_mob_ids  # noqa: E402,F401
from . import files, npc, schema, zone  # noqa: E402,F401
