"""
Compatibility shim.

The canonical implementation now lives in the installable ``image-to-video``
package as ``image_to_video.pipeline``. This module re-exports it so existing
``import image_to_video_pipeline`` usages and ``python image_to_video_pipeline.py``
keep working. Prefer ``from image_to_video.pipeline import ...`` in new code.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Work without installing the package: fall back to the in-repo source tree.
_SRC = Path(__file__).resolve().parent / "image-to-video" / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from image_to_video import pipeline as _module  # noqa: E402

if __name__ == "__main__":
    _module.main()
else:
    # Alias to the canonical module object so attribute access / monkeypatching
    # target the real implementation rather than this wrapper.
    sys.modules[__name__] = _module
