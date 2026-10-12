"""Map generator (layouts, terrain, painting, lightmap bakers, zone assembly).

See docs/mapgen/PLAN.md for the project and docs/mapgen/FORMATS.md for the
formats. The file codecs (ZON, HIM/TIL/MOV, IFO, LIT) live in ``scripts/rosefmt``
since 2026-10-12 -- ``mapgen.zon`` and friends are re-export shims -- and
``scripts/mapgen-roundtrip.py`` proves them exact on the whole of
data/3DDATA/MAPS. Every codec is `parse_x(bytes) -> model`, `build_x(model) -> bytes`.
"""

from . import chunk, ifo, lit, zon  # noqa: F401 (shims over rosefmt)
from .binio import FormatError  # noqa: F401

# extension -> (parse, build); the codecs are rosefmt's since 2026-10-12
CODECS = {
    ".zon": (zon.parse, zon.build),
    ".ifo": (ifo.parse, ifo.build),
    ".him": (chunk.parse_him, chunk.build_him),
    ".til": (chunk.parse_til, chunk.build_til),
    ".mov": (chunk.parse_mov, chunk.build_mov),
    ".lit": (lit.parse_lit, lit.build_lit),
}
