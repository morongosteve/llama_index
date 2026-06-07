"""
Unit tests for the Face Lock → image-to-video bridge.

Self-contained: no cv2/mediapipe (FaceAnalyzer is faked), no network.
"""

from __future__ import annotations

import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import face_lock_core as flc  # noqa: E402
import face_lock_pipeline as flp  # noqa: E402


def _metrics(**over):
    base = {
        "gonial_angle": 120.0,
        "canthal_tilt": 3.0,
        "facial_index": 92.0,
        "nasal_rotation": 5.0,
        "zygomatic_prominence": 1.5,
        "eye_shape_ratio": 0.30,
        "fitzpatrick_scale": 3,
    }
    base.update(over)
    return flc.FacialMeasurements(**base)


class FakeAnalyzer:
    """Stand-in for FaceAnalyzer that returns a scripted result, no vision deps."""

    def __init__(self, result):
        self._result = result
        self.calls = 0

    def analyze(self, image_np):
        self.calls += 1
        return self._result


# ─── build_locked_job_config ──────────────────────────────────────────────────


def test_job_config_folds_identity_and_anti_drift():
    m = _metrics()
    cfg = flp.build_locked_job_config(m, "Aria", platform="flux")
    assert "Maintain exact facial identity" in cfg["prompt"]
    assert flp.DEFAULT_MOTION_PROMPT in cfg["prompt"]
    # sharp jaw (<125) anti-drift term should appear in negatives
    assert "weak jaw" in cfg["negative_prompt"]
    assert flp.DEFAULT_VIDEO_NEGATIVES.split(",")[0] in cfg["negative_prompt"]


def test_job_config_preserves_base_cfg():
    cfg = flp.build_locked_job_config(
        _metrics(), "Aria", base_cfg={"cfg_scale": 0.3, "duration": 5, "mode": "pro"}
    )
    assert cfg["cfg_scale"] == 0.3 and cfg["duration"] == 5 and cfg["mode"] == "pro"


def test_job_config_handles_no_anti_drift_terms():
    # mid-range metrics → no anti-drift triggers; negatives still valid
    m = _metrics(gonial_angle=135.0, canthal_tilt=0.0, facial_index=85.0)
    cfg = flp.build_locked_job_config(m, "Aria")
    assert cfg["negative_prompt"]  # non-empty
    assert not cfg["negative_prompt"].startswith(",")


# ─── lock_from_reference ──────────────────────────────────────────────────────


def test_lock_from_reference_uses_injected_analyzer(tmp_path):
    ref = tmp_path / "ref.png"
    Image.new("RGB", (256, 256), (120, 90, 80)).save(ref)
    fake = FakeAnalyzer(_metrics())
    metrics, cfg = flp.lock_from_reference(ref, "Aria", analyzer=fake)
    assert fake.calls == 1
    assert metrics.gonial_angle == 120.0
    assert "Maintain exact facial identity" in cfg["prompt"]


def test_lock_from_reference_raises_when_no_face(tmp_path):
    ref = tmp_path / "ref.png"
    Image.new("RGB", (256, 256), (0, 0, 0)).save(ref)
    fake = FakeAnalyzer(None)
    with pytest.raises(ValueError, match="No face detected"):
        flp.lock_from_reference(ref, "Aria", analyzer=fake)


# ─── verify_clip ──────────────────────────────────────────────────────────────


def test_verify_clip_detects_consistent(monkeypatch):
    monkeypatch.setattr(flp, "extract_frame", lambda *a, **k: "FRAME")
    analyzer = FakeAnalyzer(_metrics())  # identical to lock → no drift
    v = flp.verify_clip("c.mp4", _metrics(), analyzer)
    assert v["has_drift"] is False
    assert v["report"] is not None


def test_verify_clip_detects_drift(monkeypatch):
    monkeypatch.setattr(flp, "extract_frame", lambda *a, **k: "FRAME")
    drifted = _metrics(canthal_tilt=20.0)  # far outside tolerance (2.0)
    analyzer = FakeAnalyzer(drifted)
    v = flp.verify_clip("c.mp4", _metrics(), analyzer)
    assert v["has_drift"] is True


def test_verify_clip_unreadable_video(monkeypatch):
    monkeypatch.setattr(flp, "extract_frame", lambda *a, **k: None)
    v = flp.verify_clip("c.mp4", _metrics(), FakeAnalyzer(_metrics()))
    assert v["has_drift"] is None and v["error"] == "unreadable_video"


def test_verify_clip_no_face(monkeypatch):
    monkeypatch.setattr(flp, "extract_frame", lambda *a, **k: "FRAME")
    v = flp.verify_clip("c.mp4", _metrics(), FakeAnalyzer(None))
    assert v["has_drift"] is None and v["error"] == "no_face_detected"


# ─── quarantine ───────────────────────────────────────────────────────────────


def test_should_quarantine_only_on_drift():
    assert flp.should_quarantine({"has_drift": True}) is True
    assert flp.should_quarantine({"has_drift": False}) is False
    assert flp.should_quarantine({"has_drift": None}) is False


def test_quarantine_moves_file(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    clip = out / "clip.mp4"
    clip.write_bytes(b"DATA")
    dest = flp.quarantine_clip(clip, out)
    assert not clip.exists()
    assert dest.exists() and dest.parent.name == flp.QUARANTINE_DIRNAME
    assert dest.read_bytes() == b"DATA"


# ─── HTML report ──────────────────────────────────────────────────────────────


def test_report_html_summary_and_verdicts():
    verifications = [
        {
            "video": "a.mp4",
            "thumbnail": "t/a.png",
            "has_drift": False,
            "report": [
                {
                    "Metric": "Canthal Tilt",
                    "Target": 3.0,
                    "Generated": 3.1,
                    "Diff": "0.10",
                    "Status": "PASS ✅",
                }
            ],
        },
        {"video": "b.mp4", "thumbnail": None, "has_drift": True, "report": None},
        {
            "video": "c.mp4",
            "thumbnail": None,
            "has_drift": None,
            "error": "no_face_detected",
            "report": None,
        },
    ]
    html = flp.generate_report_html(verifications, "Aria")
    assert "Face Lock Drift Report" in html
    assert "1 consistent" in html and "1 drifted" in html and "1 inconclusive" in html
    assert "CONSISTENT" in html and "DRIFT" in html and "INCONCLUSIVE" in html
    assert "a.mp4" in html and "Canthal Tilt" in html


def test_report_html_escapes_filenames():
    html = flp.generate_report_html(
        [{"video": "ev<il>.mp4", "thumbnail": None, "has_drift": False, "report": None}]
    )
    assert "<il>" not in html
    assert "ev&lt;il&gt;.mp4" in html
