"""Launch Rose Dev Studio without a console window: double-click, or `pythonw run.pyw [file ...]`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from devstudio.app import main  # noqa: E402

sys.exit(main())
