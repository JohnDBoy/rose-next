# Data file codecs: `scripts/rosefmt/`

Every ROSE file format the Python tooling reads or writes has exactly one
implementation, in `scripts/rosefmt/`. This note records why the package
exists, what moved into it on 2026-10-12, what deliberately did not, and how
to prove a codec before trusting it.

## The problem it replaces

Before the consolidation, 101 of the 162 scripts loaded *another script* with
`importlib` to reach a parser. `import-oro.py` (an importer, 2,600 lines) was
loaded by 73 of them for its `Stb`, `Stl`, `Zsc`, `Chr` and `Ltb` classes and
its raw IFO lump reader; `import-item.py` by 28 for its STB/STL/ZSC appenders;
`rose-data-reader.py` by 11 for the foreign-dump-tolerant `Stb`/`Stl`. On top
of that, six scripts carried a private STB class of their own, five a private
STL, three a ZSC, three a TSI reader, three a ZMO trailer reader, two an LTB,
two an IFO. The copies had drifted: three different cell encodings (latin-1,
euc-kr, caller-chosen), one `.s()` that stripped whitespace and one that did
not, one STL reader that handled the legacy `I_NUM` dialect and four that
would ask for an 8 GB buffer on it. A trap learned in one copy stayed in the
others.

## Rules

1. **One home per format.** A reader and a writer live in `rosefmt/<format>.py`.
   Scripts import from the package; nothing imports a script to get a parser.
2. **Codecs are pure.** Bytes in, structure out, and back. No printing, no
   argparse, no `data/` lookups. The one concession is `save(dry)` on the table
   classes, kept because ~70 call sites use it; it writes a `.bak` beside the
   file as it always did (and `pack.ps1` refuses to bake while one exists).
3. **Round-trip is the test.** `scripts/rosefmt-roundtrip.py` re-serialises
   every shipped file of every format and compares bytes; `--root` points it
   at a reference dump, `--selftest` runs edit-a-field checks on synthetic
   tables. A codec that cannot round-trip is a reader and its docstring says so.
4. **Unknown bytes are carried.** Tails after the last record, undecoded lumps,
   a stale position on an empty LTB cell, five STL language slots sharing one
   block: all preserved, so a rewrite of an untouched file is byte-identical.
5. **Dialects are explicit.** The codec names the variant (`Stl.legacy`,
   `Ltb.wide`) and refuses to write what it did not read as such.
6. **The trap lives with the code.** Each module's docstring holds the format
   layout and every gotcha for that format, next to the field it concerns.

## What is in the package

| Module | Format | Round-trips | Notes |
| --- | --- | --- | --- |
| `stb` | `STB1` tables | 115/115 | `Stb(path, encoding)`: `get/s/i/set/set_i/occupied/grow_to/to_bytes/save`, header parsed for `colname`/`rowname`, `key_column()` sniffs the STL-key column. |
| `stl` | `ITST01`/`NRST01`/`QEST01` and legacy `I_NUM`/`N_NUM`/`Q_NUM` | 33/33 | `Stl(path, encoding)`: `has/index/name/field/append/set_name/remove/lang/by_key/by_id`. Shared language blocks are kept shared. `read_table`/`write_table` are the functional view `import-item.py` uses. |
| `zsc` | model tables | 64/64 | `Zsc`: `to_bytes(extra…)` appends, `rebuild()` rewrites the object section from `objects` (writing *at* an index); `serialize_object`, `prop_paths`, `asset_refs`. |
| `chr` | `LIST_NPC.CHR` | 1/1 | holes are `None`; the 2 KB tail past the declared count is kept. |
| `ltb` | `ULNGTB_*.LTB` (wide) / `LNGTB_*.LTB` (narrow) | 6/6 | `wide` detected from the index; `text/set_text/set_all_langs/grow_to`. |
| `aip` | monster AI | 534/534 | `parse` → (header, title, patterns, tail); records kept raw. |
| `tsi` | sprite atlases | 10/10 | `read(strict)`, `write`, `iter_sprites`, `sprite_entry` (takes the rect verbatim: item cells are `x..x+40`, skill cells `x..x+39`). |
| `qsd` | quest scripts | 227/227 | `parse`/`build`, plus the byte-level helpers the importers use: `walk`, `find_entity`, `build_trigger`, `append_pattern`, `drop_conditions`, `item_refs`, `remap_items`, `quest_refs`. |
| `condialog` | `.CON` dialogs | 226/226 | `split`/`join` (Lua + QEX1 appendix, XOR keyed on the final size), `str_ids`, `get_item`/`set_click`. Named `condialog` because `con` is a reserved device name on Windows and Python cannot import `con.py`. The full codec is the quest editor's `convo.rs`. |
| `ifo_lumps` | IFO chunks as raw lumps | 1582/1582 | the importers' view; `mapgen.ifo` is the structured codec for new work. |
| `zmo` | motion clips | read-only | header and the `EZMO` event trailer; `with_events` edits frames in place. |
| `idx` | `data.idx` | read-only | unsigned offsets; `pipeline.exe` writes it. |
| `binio` | primitives | | `pstr8`/`pstr16`/`vstr` (varint)/`cstr`, `FormatError`, `read_file` (path or bytes); `Reader`/`Writer` cursors. |
| `zon`, `chunk`, `ifo`, `lit`, `container` | the map formats | 9,035/9,035 | moved from `mapgen/` on 2026-10-12 unchanged; `mapgen.zon` and friends are re-export shims. `rosefmt.CODECS` maps extension to (parse, build). |
| `zms` | meshes v5-v8 | 7,842/7,842 | `parse`/`build`, `header`, `Mesh.positions_cm`/`triangles_cm`/`bbox_cm`, `rigid_v8`. v6 keeps its per-record u32 index columns; four shipped v8 files end before a trailer field and are kept short. |
| `dds` | texture headers, BGRA sheets | 14,278/14,278 (header) | `parse_header`/`build_header`, `split`/`join`, `info`, `side`, `read_bgra`/`write_bgra`. DXT encoding stays a texconv tool (`mapgen.lighting.encode_dds`, `make-minimap.py`). |

`scripts/mapgen/` is now the generator and the bakers only (`layout`, `terrain`,
`paint`, `lighting`, `objlight`, `relight`, `catalogue`, `prefab`, `preview`...).
`catalogue.read_zsc`, `catalogue.mesh_*` and `objlight.read_zms` are geometry
views built on `rosefmt.zsc` / `rosefmt.zms`; `lighting.dds_info` calls
`rosefmt.dds.info`. `ifo_lumps` no longer repeats the IFO record layout: it
walks each record with `rosefmt.ifo`'s readers and slices the byte spans.

## Phase 2 (2026-10-12): the map codecs and the three split formats

The pure codecs in `mapgen/` (`binio`, `container`, `zon`, `chunk`, `ifo`,
`lit`) moved into `rosefmt` as they were; each `mapgen/<name>.py` is a
re-export shim, so the 15 scripts and the three `docs/mapgen/*.md` references
read unchanged. `mapgen.binio`'s `Reader`/`Writer` merged into
`rosefmt.binio`, and `FormatError` is one class (a `ValueError`). The two IFO
implementations became one: `ifo_lumps` keeps the importers' raw API but reads
records through `rosefmt.ifo`. The three formats that were split across both
packages were merged:

- **ZSC**: `rosefmt.zsc` gained `decode_props` (the file stores the quaternion
  as w, x, y, z; parent is 1-based) and `material_flags`; `catalogue.read_zsc`
  is a view over `Zsc` with the same output.
- **ZMS**: `rosefmt.zms` is new, from the engine's `load_mesh_8`/`load_mesh_6`
  (`src/engine/src/zz_mesh_tool.cpp`); `catalogue.mesh_box`/`mesh_vertices`/
  `mesh_triangles`, `objlight.read_zms` and the glb importer's reader/writer
  are built on it. The private copies in `audit-zsc-bounds.py`,
  `fix-coplanar-object-overlaps.py`, `fix-wing-twin-faces.py` and
  `measure-flinch-timing.py` stay (applied one-offs).
- **DDS**: `rosefmt.dds` is new; `lighting.dds_info`, `audit-lightmap-index`'s
  `dds_side`, `add-dds-mipmaps`' `read_header` and the icon tools' BGRA
  sheet reader/writer are built on it.

Verified the same way as phase 1: `mapgen-roundtrip.py` still 9,035/9,035 and
its selftest; `rosefmt-roundtrip.py` byte-identical on every format including
ZMS and DDS; the outputs of `catalogue.read_zsc`, the ZMS readers and
`dds_info` hashed for every file before and after (identical); and the
read-only script commands diffed before and after.

## What moved, what stayed

Moved (the script now imports the shared codec under the same names, so every
caller is unchanged): `import-oro.py` (STB, STL, ZSC, CHR, LTB, IFO lumps, QSD
and CON helpers, TSI reader; it re-exports them for the 73 scripts that load
it), `import-item.py` (ZSC, STL functions, the STB appenders rebuilt on `Stb`),
`rose-data-reader.py` (STB, STL), `import-oro-fate.py` (QSD walkers, CON
helpers), `audit-ai-monster-refs.py` (AIP), `add-item-icon.py`,
`add-skill-icon.py`, `add-quest-emoticons.py` (TSI), `translate-karkia-dialog.py`
(LTB), `verify-vfs.py` (index), `balance-sim.py` and
`convert-buffs-to-percent.py` (STB), `audit-ai-skill-refs.py` and
`import-hebarn.py` (ZMO trailer).

Left in place, on purpose:

- `fix-item-names.py` (`StbFile`/`StlFile`), `fix-tooltip-labels.py` (`Stl`):
  one-off repairs already applied, with APIs that return decoded strings where
  the shared class returns bytes. Replacing them changes call sites for no gain.
- `import-eldeon-spawns.py`, `import-eldeon-art.py`, `restore-warp-gates.py`,
  `fix-coplanar-object-overlaps.py`, `audit-zsc-bounds.py`, `zsc_weapon_fix.py`,
  `measure-flinch-timing.py`, `import-cerberus.py`'s `zmo_with_events`: private
  readers in scripts that have run and are not expected to run again, or that
  carry validation logic a plain codec call would drop. Switch them over when
  they are next touched.
- `import-glb-weapon.py`'s ZMS/ZMO/EFT writers: they build *new* files from
  geometry rather than editing existing ones; they would be the seed of a
  `rosefmt.zms` when a second producer appears.
- `import-item.py`'s `read_varint`/`vstr_read` helpers: used for the DDS/icon
  paths too; harmless duplicates of `binio`.

## Behaviour differences accepted

- Codec errors are `rosefmt.FormatError` (a `ValueError`) where the copies
  raised `SystemExit`. No script caught `SystemExit` around a codec call (the
  48 `except SystemExit` in the tree all wrap `argparse --help` during module
  loading).
- `Stb.s()` never strips. The two private copies that stripped had their call
  sites changed to `.s(...).strip()`.
- `import-item.py`'s `stb_append_row` used to append the new cells *after* any
  trailing junk in the file; the shared writer puts them before the tail.
  Identical on every file we ship (none has a tail).

## How it was verified

1. `rosefmt-roundtrip.py` on `data/`: every format byte-identical (table above).
2. 51 read-only script commands (`--verify`, `--selftest`, `--dry-run`, the
   reports) captured before and after the switch-over and diffed: identical,
   except one importer's verify listing whose line order comes from a set.
3. The same round-trip on the reference dumps, for the foreign dialects. Every
   format is byte-identical on every file of Jrose (201 STB, 35 STL incl. the
   legacy ones, 142 ZSC, 1,219 AIP, 548 QSD, 463 CON, 2,138 IFO), 667, ruff and
   tsuki, with two exceptions that are findings about the dumps, not the
   codecs: RoseZA's `LIST_TERRAIN_OBJECT_ORO.STB` is truncated at byte 4,394
   (reported as a `FormatError`), and ruff's `ORO/TOWN/33_31.IFO` carries 61
   junk bytes inside a *non-final* lump, which the raw-lump reader refuses on
   purpose (an under-consumed lump is how a misread field is caught;
   `mapgen.ifo` carries per-lump tails and reads it).

   The foreign runs are what found four "carry the bytes" cases our own data
   never shows: Jrose leaves 2-4 bytes after an STL's last entry, tsuki writes
   STLs whose language slots all point at block 0 with the other blocks left
   dead in the file, ruff and tsuki have 12-15,381 bytes after a QSD's last
   pattern, ruff's `EM16-001.CON` has 732 bytes after its Lua, and 667's
   `ITEM1.TSI` declares 540 sprites for 9,295. Each is now preserved
   (`Stl.tail`, `qsd['tail']`, `condialog.split_ex`, `tsi.build(total=)`).

## Adding a format

Put the codec in `rosefmt/<format>.py` with the layout in the module docstring,
a `parse`/`build` pair (or a class with `to_bytes`), add it to `FORMATS` in
`rosefmt-roundtrip.py`, run the round-trip on `data/` and on a reference dump,
and add a row to the CLAUDE.md table. If it cannot round-trip, say so in the
docstring and register it as read-only in the round-trip script.
