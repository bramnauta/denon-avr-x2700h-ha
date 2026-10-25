"""Load the Home Assistant independent modules without importing the package.

``protocol.py`` and ``client.py`` have no Home Assistant imports, so they can be
tested without installing Home Assistant. A stub package keeps the package's
``__init__`` (which does import Home Assistant) from running.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "denon_avr_x2700h"

if "denon_pkg" not in sys.modules:
    package = types.ModuleType("denon_pkg")
    package.__path__ = [str(COMPONENT)]
    sys.modules["denon_pkg"] = package
