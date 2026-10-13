"""Rose Dev Studio: a GUI over ``scripts/rosefmt`` for editing ROSE data files.

The codecs live in ``scripts/rosefmt`` and are imported, never copied: the
studio is a front end, and a file it saves is serialised by the same writer the
round-trip tests prove. This package puts ``scripts/`` on ``sys.path`` once,
here, so every module can ``from rosefmt import ...``.
"""
import os
import sys

_SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "scripts"))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
