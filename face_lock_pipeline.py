"""
Compatibility shim.

The canonical implementation now lives in the installable ``image-to-video``
package as ``image_to_video.face_lock_bridge``. This module re-exports it so
existing ``import face_lock_pipeline`` usages and ``python face_lock_pipeline.py``
keep working. Prefer ``from image_to_video.face_lock_bridge import ...`` in new code.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "image-to-video" / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from image_to_video import face_lock_bridge as _module  # noqa: E402

if __name__ == "__main__":
    _module.main()
else:
    sys.modules[__name__] = _module
