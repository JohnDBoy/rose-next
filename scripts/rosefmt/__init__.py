"""rosefmt -- the one home for every ROSE file-format codec the scripts use.

Rules (the reasons are in doc/data-codecs.md):

* **One reader and one writer per format, here.** A script imports from this
  package; nothing imports a script to get at a parser. Before 2026-10-12 the
  STB/STL/ZSC/CHR/LTB codecs lived inside ``import-oro.py`` and 73 scripts loaded
  that importer with ``importlib`` to reach them, while five more scripts carried
  their own private STB class. A trap learned in one copy stayed in the others.
* **Codecs are pure.** A codec turns bytes into a structure and back. It does not
  print, parse arguments, make backups or look anything up under ``data/``. The
  script around it does the I/O and holds the policy. (``save(dry)`` on the
  table classes is the one concession, kept because 70 scripts call it; it
  writes a ``.bak`` beside the file exactly as it always did.)
* **Round-trip is the test.** ``scripts/rosefmt-roundtrip.py`` re-serialises
  every shipped file of every format here and compares the bytes. A codec that
  cannot prove that is a reader, and says so in its docstring.
* **Unknown bytes are carried, not dropped.** Tails, undecoded lumps and
  editor junk after the last record are kept verbatim so a rewrite is
  byte-identical.
* **Dialects are explicit.** An STL is modern (``ITST01``) or legacy
  (``I_NUM``); a ZMS is v6 (cm) or v8 (metres); the codec names the variant and
  refuses what it cannot write rather than guessing.
* **The trap lives with the code.** Every format gotcha is in the docstring of
  the field it concerns, not in a commit message.

The map formats (ZON, HIM, TIL, MOV, IFO as structured records, LIT) are in
``scripts/mapgen/`` and stay there; ``rosefmt.ifo_lumps`` is the older raw-lump
view of an IFO that the importers use, documented as such.

Import from a script with::

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from rosefmt import Stb, Stl, Zsc, Chr, Ltb
    from rosefmt import aip, condialog, ifo_lumps, qsd, tsi, zmo, idx
"""
from .binio import FormatError
from .stb import Stb
from .stl import Stl, stl_by_key
from .zsc import Zsc
from .chr import Chr
from .ltb import Ltb
from . import aip, binio, chr as chr_, condialog, idx, ifo_lumps, ltb, qsd, stb, stl, tsi, zmo, zsc

__all__ = [
    "FormatError", "Stb", "Stl", "stl_by_key", "Zsc", "Chr", "Ltb",
    "aip", "binio", "condialog", "idx", "ifo_lumps", "ltb", "qsd", "stb", "stl", "tsi",
    "zmo", "zsc",
]
