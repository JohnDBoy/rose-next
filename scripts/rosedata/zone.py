"""The three ZON questions importers ask, answered through ``rosefmt.zon``.

* ``zon_tiles`` -- the tile *texture* paths (lump 2), as str.
* ``zon_events`` -- the event positions (lump 1) as ``(name bytes, (x, z, y))``:
  the spawn/revive points (``start``, ``restore``, ``WARP-...``) a zone row and
  the warp table resolve by name.
* ``zon_zone_type`` -- read, and optionally rewrite, the editor-only ZoneType in
  lump 0 (ZONETYPEINFO.STB row). Nothing in the game reads it, which is why
  rewriting it is safe; the rewrite goes through the codec, so the file is
  otherwise byte-identical.
"""
from rosefmt import zon


def _model(path):
    with open(path, "rb") as fh:
        return zon.parse(fh.read())


def zon_tiles(path):
    """LUMP_ZONE_TILE (2): the tile texture paths."""
    texs = _model(path).lump(zon.TEXTURES)
    return [t.rstrip(b"\0").decode("latin-1") for t in texs] if texs is not None else []


def zon_events(path):
    """LUMP_EVENT_OBJECT (1) of a .ZON: [(name bytes, (x, z, y))]."""
    evs = _model(path).lump(zon.EVENTS)
    return [(e.name, (e.x, e.z, e.y)) for e in evs] if evs is not None else []


def zon_zone_type(path, new_type=None):
    """The ZoneType in lump 0; with ``new_type``, rewrite it when it differs."""
    m = _model(path)
    info = m.lump(zon.INFO)
    if info is None:
        return None
    cur = info.zone_type
    if new_type is not None and cur != new_type:
        info.zone_type = new_type
        with open(path, "wb") as fh:
            fh.write(zon.build(m))
    return cur
