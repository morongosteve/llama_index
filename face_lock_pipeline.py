#!/usr/bin/env python3
"""
Face Lock → Image-to-Video bridge.

End-to-end flow:
  1. LOCK    — extract biometric measurements from a reference face image
  2. GENERATE/ANIMATE — run the i2v pipeline with the locked identity baked
     into the prompt + anti-drift negative prompt
  3. VERIFY  — sample a frame from each rendered clip, re-measure, and compare
     against the lock; quarantine clips that drifted
  4. REPORT  — emit drift_results.json + report.html (thumbnails + pass/fail)

Pure-logic helpers (job-config assembly, quarantine decision, HTML report)
have no vision dependencies and are unit-tested. Frame sampling and face
analysis import cv2/mediapipe lazily, so this module imports anywhere.

Usage:
    export KLING_API_KEY="sk-..."
    python face_lock_pipeline.py --reference ref.png --subject "Aria" \
        --input inputs --output outputs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
from html import escape
from pathlib import Path
from typing import Optional

import face_lock_core as flc
import image_to_video_pipeline as i2v

log = logging.getLogger("face_lock_pipeline")

DEFAULT_MOTION_PROMPT = (
    "subtle expression shift, camera slowly pushes in, face fully in frame"
)
DEFAULT_VIDEO_NEGATIVES = (
    "blur, distortion, face morph, identity drift, anatomical distortion"
)
QUARANTINE_DIRNAME = "drift_rejected"


# ─── Stage 1+2 helpers: identity-locked job config (pure) ─────────────────────


def build_locked_job_config(
    metrics: flc.FacialMeasurements,
    subject_name: str,
    platform: str = "flux",
    motion_prompt: str = DEFAULT_MOTION_PROMPT,
    base_cfg: Optional[dict] = None,
) -> dict:
    """
    Fuse the biometric lock into an i2v job_config.

    The video prompt = motion + identity descriptors; the negative prompt =
    the lock's anti-drift constraints + standard video negatives. Any keys in
    base_cfg (cfg_scale, mode, duration, aspect_ratio, ...) are preserved
    unless overridden here.
    """
    gen = flc.PromptGenerator()
    prompts = gen.generate(metrics, platform, subject_name)

    # Strip the platform-gen scaffolding ("photo of ...") down to the identity
    # descriptors and fold them into a motion-oriented video prompt.
    identity = prompts["positive"]
    anti_drift = gen._generate_anti_drift_negatives(metrics)

    cfg = dict(base_cfg or {})
    cfg["prompt"] = f"{motion_prompt}. Maintain exact facial identity — {identity}"
    negatives = (
        [anti_drift, DEFAULT_VIDEO_NEGATIVES]
        if anti_drift
        else [DEFAULT_VIDEO_NEGATIVES]
    )
    cfg["negative_prompt"] = ", ".join(n for n in negatives if n)
    return cfg


# ─── Stage 1: lock (needs vision deps — lazy via FaceAnalyzer) ────────────────


def lock_from_reference(
    reference_path: Path,
    subject_name: str,
    platform: str = "flux",
    motion_prompt: str = DEFAULT_MOTION_PROMPT,
    base_cfg: Optional[dict] = None,
    analyzer: Optional["flc.FaceAnalyzer"] = None,
) -> tuple[flc.FacialMeasurements, dict]:
    """Measure the reference face and return (locked_metrics, job_config)."""
    import numpy as np
    from PIL import Image

    analyzer = analyzer or flc.FaceAnalyzer()
    image_np = np.array(Image.open(reference_path).convert("RGB"))
    metrics = analyzer.analyze(image_np)
    if metrics is None:
        raise ValueError(f"No face detected in reference: {reference_path}")

    cfg = build_locked_job_config(
        metrics, subject_name, platform, motion_prompt, base_cfg
    )
    log.info(f"Locked identity from {Path(reference_path).name}: {metrics.to_dict()}")
    return metrics, cfg


# ─── Stage 3: frame sampling + drift verification ─────────────────────────────


def extract_frame(
    video_path: Path, out_png: Optional[Path] = None, position: float = 0.5
):
    """
    Grab a representative frame from a video (default: midpoint).
    Returns the frame as a numpy array (BGR), or None if unreadable.
    Optionally writes a PNG thumbnail. cv2 imported lazily.
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        target = max(0, int(total * position) - 1) if total else 0
        if total:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        if out_png is not None:
            cv2.imwrite(str(out_png), frame)
        return frame
    finally:
        cap.release()


def verify_clip(
    video_path: Path,
    locked_metrics: flc.FacialMeasurements,
    analyzer: "flc.FaceAnalyzer",
    detector: Optional[flc.DriftDetector] = None,
    thumb_path: Optional[Path] = None,
    position: float = 0.5,
) -> dict:
    """
    Sample a frame, re-measure the face, and compare against the lock.

    Returns a verification record. `has_drift` is True/False when a face is
    measured, or None when the frame had no detectable face (inconclusive).
    """
    detector = detector or flc.DriftDetector()
    record: dict = {
        "video": str(video_path),
        "thumbnail": str(thumb_path) if thumb_path else None,
        "has_drift": None,
        "report": None,
    }

    frame = extract_frame(video_path, thumb_path, position)
    if frame is None:
        record["error"] = "unreadable_video"
        return record

    gen_metrics = analyzer.analyze(frame)
    if gen_metrics is None:
        record["error"] = "no_face_detected"
        return record

    report = detector.check_drift(locked_metrics, gen_metrics)
    record["has_drift"] = report["has_drift"]
    record["report"] = report["details"]
    return record


# ─── Quarantine decision (pure) ───────────────────────────────────────────────


def should_quarantine(verification: dict) -> bool:
    """Quarantine clips that drifted. Inconclusive (no face) is NOT quarantined."""
    return verification.get("has_drift") is True


def quarantine_clip(video_path: Path, output_dir: Path) -> Path:
    """Move a drifted clip into the quarantine subdir; returns the new path."""
    qdir = output_dir / QUARANTINE_DIRNAME
    qdir.mkdir(parents=True, exist_ok=True)
    dest = qdir / Path(video_path).name
    shutil.move(str(video_path), str(dest))
    return dest


# ─── Stage 4: HTML report (pure) ──────────────────────────────────────────────


def generate_report_html(verifications: list[dict], subject_name: str = "") -> str:
    """Render a self-contained HTML drift report from verification records."""
    rows = []
    for v in verifications:
        name = escape(Path(v["video"]).name)
        thumb = v.get("thumbnail")
        thumb_cell = (
            f'<img src="{escape(thumb)}" width="120" alt="{name}">' if thumb else "—"
        )

        if v.get("has_drift") is True:
            verdict = '<span style="color:#c0392b;font-weight:bold">DRIFT ❌</span>'
        elif v.get("has_drift") is False:
            verdict = (
                '<span style="color:#27ae60;font-weight:bold">CONSISTENT ✅</span>'
            )
        else:
            reason = escape(v.get("error", "inconclusive"))
            verdict = f'<span style="color:#7f8c8d">INCONCLUSIVE ({reason})</span>'

        detail = ""
        if v.get("report"):
            metrics_html = "".join(
                f"<tr><td>{escape(str(d['Metric']))}</td>"
                f"<td>{escape(str(d['Target']))}</td>"
                f"<td>{escape(str(d['Generated']))}</td>"
                f"<td>{escape(str(d['Diff']))}</td>"
                f"<td>{escape(str(d['Status']))}</td></tr>"
                for d in v["report"]
            )
            detail = (
                "<table class='inner'><tr><th>Metric</th><th>Target</th>"
                "<th>Generated</th><th>Diff</th><th>Status</th></tr>"
                f"{metrics_html}</table>"
            )

        rows.append(
            f"<tr><td>{thumb_cell}</td><td>{name}</td>"
            f"<td>{verdict}</td><td>{detail}</td></tr>"
        )

    total = len(verifications)
    drifted = sum(1 for v in verifications if v.get("has_drift") is True)
    consistent = sum(1 for v in verifications if v.get("has_drift") is False)
    inconclusive = total - drifted - consistent

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Face Lock Drift Report</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #2c3e50; }}
 h1 {{ margin-bottom: 0.2rem; }}
 .summary {{ margin: 1rem 0; font-size: 1.1rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td, th {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; text-align: left; }}
 th {{ background: #f4f6f7; }}
 table.inner {{ font-size: 0.85rem; }}
 table.inner th {{ background: #fbfcfc; }}
</style></head><body>
<h1>Face Lock Drift Report</h1>
<div class="summary">
 Subject: <b>{escape(subject_name) or "—"}</b> &middot;
 {total} clips &middot;
 <span style="color:#27ae60">{consistent} consistent</span> &middot;
 <span style="color:#c0392b">{drifted} drifted</span> &middot;
 <span style="color:#7f8c8d">{inconclusive} inconclusive</span>
</div>
<table>
 <tr><th>Thumbnail</th><th>Clip</th><th>Verdict</th><th>Metrics</th></tr>
 {"".join(rows)}
</table>
</body></html>
"""


# ─── Orchestration ────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Face Lock → image-to-video bridge")
    p.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Reference face image to lock onto",
    )
    p.add_argument(
        "--subject", type=str, default="Subject_01", help="Subject/character name"
    )
    p.add_argument(
        "--platform",
        type=str,
        default="flux",
        help="Prompt style (flux/midjourney/reve)",
    )
    p.add_argument(
        "--input", type=Path, default=i2v.INPUT_DIR, help="Input image directory"
    )
    p.add_argument(
        "--output", type=Path, default=i2v.OUTPUT_DIR, help="Output video directory"
    )
    p.add_argument(
        "--motion-prompt",
        type=str,
        default=DEFAULT_MOTION_PROMPT,
        help="Base motion prompt",
    )
    p.add_argument(
        "--no-quarantine", action="store_true", help="Report drift but don't move clips"
    )
    p.add_argument(
        "--lock-only", action="store_true", help="Print the locked job_config and exit"
    )
    return p.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    args = parse_args()

    if not args.reference.is_file():
        log.error(f"Reference image not found: {args.reference}")
        raise SystemExit(1)

    # Stage 1 — LOCK
    log.info("Stage 1 — locking identity from reference")
    locked_metrics, job_cfg = lock_from_reference(
        args.reference, args.subject, args.platform, args.motion_prompt
    )

    if args.lock_only:
        print(
            json.dumps(
                {"metrics": locked_metrics.to_dict(), "job_config": job_cfg}, indent=2
            )
        )
        return

    # Stage 2 — GENERATE/ANIMATE (reuse the i2v pipeline)
    i2v.OUTPUT_DIR = args.output
    log.info("Stage 2 — validating inputs and animating")
    manifests, _ = i2v.build_manifest(args.input)
    if not manifests:
        log.error("No valid input images. See image_errors.json.")
        raise SystemExit(1)
    if i2v.API_KEY in ("", "YOUR_API_KEY"):
        log.error("KLING_API_KEY is not set.")
        raise SystemExit(1)

    results = asyncio.run(i2v.run_batch(manifests, job_cfg))
    succeeded = [r for r in results if r["status"] == "succeed"]

    # Stage 3 — VERIFY + quarantine
    log.info(f"Stage 3 — verifying {len(succeeded)} clips against the lock")
    analyzer = flc.FaceAnalyzer()
    detector = flc.DriftDetector()
    thumbs_dir = args.output / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    verifications = []
    for r in succeeded:
        vid = Path(r["output_path"])
        thumb = thumbs_dir / f"{vid.stem}.png"
        v = verify_clip(vid, locked_metrics, analyzer, detector, thumb)
        if should_quarantine(v) and not args.no_quarantine:
            new_path = quarantine_clip(vid, args.output)
            v["quarantined_to"] = str(new_path)
            log.warning(f"  ⚠ drift — quarantined {vid.name}")
        verifications.append(v)

    # Stage 4 — REPORT
    (args.output / "drift_results.json").write_text(
        json.dumps(
            {
                "subject": args.subject,
                "locked_metrics": locked_metrics.to_dict(),
                "verifications": verifications,
            },
            indent=2,
        )
    )
    report_path = args.output / "report.html"
    report_path.write_text(generate_report_html(verifications, args.subject))
    log.info(f"Done. Report → {report_path}")


if __name__ == "__main__":
    main()
