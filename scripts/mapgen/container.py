"""Re-export shim: this codec lives in ``rosefmt.container`` since 2026-10-12.

Kept so ``from mapgen import container`` and the relative imports inside the
generator keep working; new code imports ``rosefmt.container`` directly.
"""
import os as _os
import sys as _sys

_scripts = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _scripts not in _sys.path:
    _sys.path.insert(0, _scripts)

import rosefmt.container as _m  # noqa: E402

globals().update({_k: _v for _k, _v in vars(_m).items() if not _k.startswith("__")})
del _m
