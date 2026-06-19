"""
Compatibility shim.

Canonical implementation: ``image_to_video.providers`` in the installable
``image-to-video`` package. Prefer ``from image_to_video.providers import ...``
in new code.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "image-to-video" / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from image_to_video import providers as _module  # noqa: E402

sys.modules[__name__] = _module
