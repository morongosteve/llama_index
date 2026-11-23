"""
Unit tests for the Face Lock core (measurement geometry, input handling, film).

Self-contained: no cv2/mediapipe. ``FaceAnalyzer`` is driven by a fake face mesh
that normalises landmarks the way mediapipe does (x / width, y / height).
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest
from PIL import Image

from image_to_video import face_lock_core as flc

# Frames of different shape (1:1, 4:5, 16:9, tall): the face keeps the same
# pixel size in each, only the frame around it changes.
FRAMES = [(300, 300), (240, 300), (420, 236), (170, 302)]


def _face(tilt: float = 5.0, roll: float = 0.0) -> np.ndarray:
    """
    Landmark offsets (px, y down) from the frame centre of a symmetric face.

    Known geometry: face height (10-152) 120, width (234-454) 90, nasion-chin
    (168-152) 80, eye width 22, eyelid opening 6, tip->base drop 4. ``tilt`` is
    the canthal tilt of both eyes; ``roll`` rotates the whole face in-plane.
    """
    pts = np.zeros((478, 2))
    t = np.radians(tilt)
    pts[10], pts[152], pts[168] = (0, -60), (0, 60), (0, -20)
    pts[234], pts[454] = (-45, -5), (45, -5)
    pts[133], pts[33] = (-10, -16), (-10 - 22 * np.cos(t), -16 - 22 * np.sin(t))
    pts[362], pts[263] = (10, -16), (10 + 22 * np.cos(t), -16 - 22 * np.sin(t))
    pts[159], pts[145] = (-21, -20), (-21, -14)
    pts[1], pts[2] = (0, 8), (0, 12)
    pts[132], pts[172], pts[361], pts[397] = (-44, 20), (-36, 40), (44, 20), (36, 40)
    c, s = np.cos(np.radians(roll)), np.sin(np.radians(roll))
    return pts @ np.array([[c, s], [-s, c]])


class _FakeMesh:
    """Stand-in for mediapipe's FaceMesh; remembers the array it was given."""

    def __init__(self, face_px):
        self.face_px = face_px  # None -> "no face found"
        self.seen = None

    def process(self, rgb):
        self.seen = rgb
        if self.face_px is None:
            return types.SimpleNamespace(multi_face_landmarks=None)
        h, w = rgb.shape[:2]
        pts = self.face_px + np.array([w / 2, h / 2])
        lm = [types.SimpleNamespace(x=x / w, y=y / h, z=0.0) for x, y in pts]
        return types.SimpleNamespace(
            multi_face_landmarks=[types.SimpleNamespace(landmark=lm)]
        )


def _analyzer(face_px) -> flc.FaceAnalyzer:
    analyzer = flc.FaceAnalyzer.__new__(flc.FaceAnalyzer)  # skip __init__ (mediapipe)
    analyzer.face_mesh = _FakeMesh(face_px)
    return analyzer


def _measure(face_px, w: int, h: int) -> flc.FacialMeasurements:
    return _analyzer(face_px).analyze(np.zeros((h, w, 3), np.uint8))


# ─── geometry ─────────────────────────────────────────────────────────────────


def test_measurements_do_not_depend_on_frame_aspect_ratio():
    """
    Regression: x and y are normalised by different axes, so distances were
    computed in a distorted space and the facial index swung from ~48 to ~148
    for the same face in a 9:16 vs 16:9 frame.
    """
    face = _face()
    reference = _measure(face, *FRAMES[0]).to_dict()
    for w, h in FRAMES[1:]:
        assert _measure(face, w, h).to_dict() == pytest.approx(reference, abs=0.011), (
            w,
            h,
        )


def test_same_face_in_a_different_frame_is_not_flagged_as_drift():
    face = _face()
    locked = _measure(face, *FRAMES[0])
    for w, h in FRAMES[1:]:
        report = flc.DriftDetector().check_drift(locked, _measure(face, w, h))
        assert report["has_drift"] is False, (w, h, report["details"])


@pytest.mark.parametrize("tilt", [-6.0, 0.0, 0.4, 6.0])
def test_canthal_tilt_is_a_small_signed_angle(tilt):
    """Regression: the old formula returned ~(180 - tilt), i.e. +-179 near zero."""
    assert _measure(_face(tilt=tilt), 300, 300).canthal_tilt == pytest.approx(
        tilt, abs=0.01
    )


def test_canthal_tilt_cancels_in_plane_head_roll():
    upright = _measure(_face(tilt=5.0), 300, 300).canthal_tilt
    rolled = _measure(_face(tilt=5.0, roll=12.0), 300, 300).canthal_tilt
    assert rolled == pytest.approx(upright, abs=0.01)


def test_gonial_angle_is_measured_at_the_jaw_corner():
    """
    Regression: the vertex used to be a point on the jawline next to the
    other two, giving ~25 degrees (below every threshold) for any face.
    """
    assert 120 <= _measure(_face(), 300, 300).gonial_angle <= 160


def test_facial_index_nasal_rotation_and_eye_ratio_follow_their_definitions():
    m = _measure(_face(), 300, 300)
    assert m.facial_index == pytest.approx(80 / 90 * 100, abs=0.01)
    assert m.nasal_rotation == pytest.approx(4 / 120 * 100, abs=0.01)  # of face height
    assert m.eye_shape_ratio == pytest.approx(6 / 22, abs=0.006)


# ─── input handling ───────────────────────────────────────────────────────────


def test_ndarray_is_read_as_bgr_and_pil_image_as_rgb():
    analyzer = _analyzer(_face())
    bgr = np.zeros((300, 300, 3), np.uint8)
    bgr[..., 0] = 255  # blue, in BGR order
    analyzer.analyze(bgr)
    assert analyzer.face_mesh.seen[0, 0].tolist() == [0, 0, 255]  # mesh gets RGB

    analyzer.analyze(Image.new("RGB", (300, 300), (255, 0, 0)))  # red, in RGB order
    assert analyzer.face_mesh.seen[0, 0].tolist() == [255, 0, 0]


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P", "LA", "CMYK"])
def test_analyze_accepts_any_pil_mode(mode):
    assert _analyzer(_face()).analyze(Image.new(mode, (300, 300))) is not None


@pytest.mark.parametrize(
    "shape", [(300, 300), (300, 300, 1), (300, 300, 3), (300, 300, 4)]
)
def test_analyze_accepts_gray_and_alpha_arrays(shape):
    assert _analyzer(_face()).analyze(np.zeros(shape, np.uint8)) is not None


def test_analyze_rejects_unsupported_array_shape():
    with pytest.raises(ValueError):
        _analyzer(_face()).analyze(np.zeros((10, 10, 2), np.uint8))


def test_no_face_returns_none():
    assert _analyzer(None).analyze(np.zeros((64, 64, 3), np.uint8)) is None


def test_missing_legacy_solutions_api_gives_an_actionable_error(monkeypatch):
    """
    Mediapipe >= 0.10.30 has no `solutions`; the old code died with a bare
    AttributeError on every page load.
    """
    monkeypatch.setitem(sys.modules, "mediapipe", types.SimpleNamespace())
    with pytest.raises(RuntimeError, match=r"0\.10\.30"):
        flc.FaceAnalyzer()


# ─── film emulation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P", "LA", "CMYK"])
@pytest.mark.parametrize(
    "preset", ["Kodachrome 25", "Agfa CNS2", "Kodak Vision3 500T", "None"]
)
def test_film_presets_accept_any_pil_mode(mode, preset):
    """
    Regression: the presets unpack exactly three bands, so RGBA / grayscale /
    palette / CMYK uploads raised ValueError.
    """
    out = flc.AnalogFilmProcessor.apply_preset(Image.new(mode, (40, 30)), preset)
    assert out.mode == "RGB" and out.size == (40, 30)
