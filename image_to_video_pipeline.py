#!/usr/bin/env python3
"""
Production-Grade Image-to-Video Pipeline
Kling V3 / GoEnhance — Batch, Validated, Async

Pipeline stages:
  1. Multi-stage asset validation + manifest build
  2. Async submission to the image2video endpoint
  3. Exponential-backoff polling with jitter
  4. Resumable batch processing (survives crashes via state.json)
  5. Local download of finished clips + results.json summary

Usage:
    export KLING_API_KEY="sk-..."
    python image_to_video_pipeline.py --input inputs --output outputs
    python image_to_video_pipeline.py --validate-only        # manifest, no API calls
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from PIL import Image, UnidentifiedImageError

# ─── Config ───────────────────────────────────────────────────────────────────

API_KEY         = os.environ.get("KLING_API_KEY", "YOUR_API_KEY")
SUBMIT_URL      = "https://api.kling.ai/v1/videos/image2video"
STATUS_URL      = "https://api.kling.ai/v1/videos/image2video/{task_id}"
INPUT_DIR       = Path("inputs")
OUTPUT_DIR      = Path("outputs")
MANIFEST_FILE   = Path("image_manifest.json")
ERRORS_FILE     = Path("image_errors.json")
RESULTS_FILE    = Path("results.json")
STATE_FILE      = Path("state.json")     # Resumability — survive crashes

MAX_CONCURRENCY = 5
MAX_FILE_BYTES  = 10 * 1024 * 1024      # 10 MB hard ceiling
MIN_DIMENSION   = 300                   # px floor on both axes
MAX_ASPECT_SKEW = 4.0                   # width/height or inverse, max ratio
VALID_FORMATS   = {"JPEG", "PNG", "WEBP", "TIFF", "BMP"}

# Polling config
BASE_INTERVAL   = 2.0
MAX_INTERVAL    = 30.0
MAX_POLLS       = 90
JITTER_RANGE    = 1.0

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type":  "application/json",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("i2v_pipeline")


# ─── Stage 1: Multi-Stage Asset Validation ────────────────────────────────────

VALIDATION_RULES = {
    "max_file_bytes": MAX_FILE_BYTES,
    "min_dimension_px": MIN_DIMENSION,
    "max_aspect_skew": MAX_ASPECT_SKEW,
    "valid_formats": sorted(VALID_FORMATS),
    "base64_prefix": "raw_only_no_data_uri",
}


def validate_and_encode(image_path: Path) -> dict:
    """
    Defense-in-depth validation gate. Returns a structured record or raises.

    Stages:
      1. File-size filter (before PIL instantiation — prevents OOM)
      2. Cryptographic header verification via PIL decode
      3. Dimensionality + aspect-ratio constraints
      4. Color-mode normalization (RGBA → RGB, palette → RGB)
      5. Base64 encoding — raw, no data-URI prefix (Kling requirement)
      6. SHA-256 checksum of raw bytes
    """
    path = Path(image_path)

    # Stage 1 — size gate before any PIL allocation
    file_bytes = path.stat().st_size
    if file_bytes == 0:
        raise ValueError(f"Zero-byte file: {path.name}")
    if file_bytes > MAX_FILE_BYTES:
        raise ValueError(
            f"File exceeds 10 MB ceiling ({file_bytes / 1e6:.2f} MB): {path.name}"
        )

    # Stage 2 — header + structural integrity via PIL
    try:
        img = Image.open(path)
        img.verify()                # reads header, raises on corruption
        img = Image.open(path)      # re-open after verify() (PIL requirement)
        img.load()                  # force full pixel decode
    except UnidentifiedImageError as exc:
        raise ValueError(f"Unidentified image [{path.name}]: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — surface any decode failure as a validation error
        raise ValueError(f"PIL decode failure [{path.name}]: {exc}") from exc

    fmt = img.format
    if fmt not in VALID_FORMATS:
        raise ValueError(f"Unsupported format {fmt} in {path.name}")

    # Stage 3 — dimensionality constraints
    w, h = img.size
    if w < MIN_DIMENSION or h < MIN_DIMENSION:
        raise ValueError(
            f"Dimensions below floor ({w}x{h} < {MIN_DIMENSION}px): {path.name}"
        )
    aspect = w / h
    if aspect > MAX_ASPECT_SKEW or aspect < (1 / MAX_ASPECT_SKEW):
        raise ValueError(
            f"Extreme aspect ratio ({aspect:.2f}) rejected — "
            f"latent space distortion risk: {path.name}"
        )

    # Stage 4 — color-mode normalization
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    color_mode = img.mode

    # Stage 5 — raw bytes read; raw base64, NO data-URI prefix (Kling strict)
    raw_bytes = path.read_bytes()
    raw_b64   = base64.b64encode(raw_bytes).decode("utf-8")

    # Stage 6 — SHA-256 checksum
    checksum = hashlib.sha256(raw_bytes).hexdigest()

    return {
        "filename":         path.name,
        "rel_path":         str(path),
        "base64":           raw_b64,
        "width_px":         w,
        "height_px":        h,
        "size_bytes":       file_bytes,
        "color_mode":       color_mode,
        "pil_format":       fmt,
        "checksum_sha256":  checksum,
    }


def build_manifest(input_dir: Path) -> tuple[list[dict], list[dict]]:
    """
    Walk input_dir, validate every image, return (manifests, errors).
    Writes image_manifest.json and image_errors.json.
    """
    manifests: list[dict] = []
    errors: list[dict] = []
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

    for path in sorted(input_dir.rglob("*")):
        if path.suffix.lower() not in extensions:
            continue
        try:
            record = validate_and_encode(path)
            manifests.append(record)
            log.info(
                f"  ✓ {path.name} ({record['width_px']}x{record['height_px']}, "
                f"{record['size_bytes'] / 1e3:.1f} KB)"
            )
        except ValueError as exc:
            errors.append({"filename": path.name, "error": str(exc)})
            log.warning(f"  ✗ {path.name} — {exc}")

    manifest_payload = {
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "total_valid":      len(manifests),
        "total_errors":     len(errors),
        "validation_rules": VALIDATION_RULES,
        "images":           manifests,
    }
    MANIFEST_FILE.write_text(json.dumps(manifest_payload, indent=2))
    ERRORS_FILE.write_text(json.dumps(errors, indent=2))

    log.info(f"Manifest: {len(manifests)} valid, {len(errors)} rejected")
    return manifests, errors


# ─── Stage 2: Exponential-Backoff Polling ─────────────────────────────────────

async def poll_with_backoff(session: aiohttp.ClientSession, task_id: str) -> dict:
    """
    Async polling with exponential backoff + jitter.
    Prevents thundering-herd rate-limit penalties at scale.
    Transitions: submitted → processing → succeed | failed | timeout
    """
    url = STATUS_URL.format(task_id=task_id)

    for attempt in range(MAX_POLLS):
        async with session.get(url, headers=HEADERS) as resp:
            data = await resp.json()

        status = data.get("data", {}).get("task_status")

        if status == "succeed":
            videos = data["data"]["task_result"]["videos"]
            return {"status": "succeed", "video_url": videos[0]["url"], "raw": data}

        if status == "failed":
            msg = data["data"].get("task_status_msg", "unspecified failure")
            raise RuntimeError(f"Generation failed [{task_id}]: {msg}")

        # Exponential backoff with randomized jitter — avoids synchronized retry storms
        sleep = min(MAX_INTERVAL, BASE_INTERVAL * (1.5 ** attempt)) + random.uniform(0, JITTER_RANGE)
        log.debug(f"  [{task_id}] attempt {attempt + 1}, status={status}, sleeping {sleep:.1f}s")
        await asyncio.sleep(sleep)

    raise TimeoutError(f"Task {task_id} timed out after {MAX_POLLS} polls.")


# ─── Stage 3: Submission ──────────────────────────────────────────────────────

async def submit_job(
    session: aiohttp.ClientSession,
    manifest_record: dict,
    job_config: dict,
) -> str:
    """Submit one image2video job. Returns task_id."""
    payload = {
        "model_name":       "kling-v3",
        "image":            manifest_record["base64"],  # raw base64, no prefix
        "prompt":           job_config.get(
            "prompt",
            "subtle expression shift, camera slowly pushes in, face fully in frame",
        ),
        "negative_prompt":  job_config.get(
            "negative_prompt",
            "blur, distortion, face morph, identity drift, anatomical distortion",
        ),
        "cfg_scale":        job_config.get("cfg_scale", 0.5),   # low = image-faithful
        "mode":             job_config.get("mode", "pro"),
        "duration":         job_config.get("duration", 10),
        "aspect_ratio":     job_config.get("aspect_ratio", "9:16"),
    }

    async with session.post(SUBMIT_URL, json=payload, headers=HEADERS) as resp:
        data = await resp.json()
        if resp.status >= 400:
            raise RuntimeError(f"Submit error {resp.status}: {data}")
        return data["data"]["task_id"]


# ─── Stage 4: Resumable Batch Processor ──────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


async def process_one(
    session:  aiohttp.ClientSession,
    sem:      asyncio.Semaphore,
    record:   dict,
    job_cfg:  dict,
    state:    dict,
) -> dict:
    """
    Full lifecycle for one image: submit → poll → download → return result.
    Skips submission if task_id already persisted in state (crash-resumability).
    """
    name = record["filename"]

    async with sem:
        try:
            # Resumability — skip resubmission if job already in flight
            if name in state and "task_id" in state[name]:
                task_id = state[name]["task_id"]
                log.info(f"  ↩ Resuming {name} (task_id={task_id})")
            else:
                task_id = await submit_job(session, record, job_cfg)
                state[name] = {
                    "task_id": task_id,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }
                save_state(state)
                log.info(f"  → Submitted {name} (task_id={task_id})")

            result = await poll_with_backoff(session, task_id)
            log.info(f"  ✓ Done: {name} → {result['video_url']}")

            # Download the video locally
            OUTPUT_DIR.mkdir(exist_ok=True)
            stem = Path(name).stem
            out_path = OUTPUT_DIR / f"{stem}__{task_id[:8]}.mp4"
            async with session.get(result["video_url"]) as vid_resp:
                out_path.write_bytes(await vid_resp.read())
            log.info(f"  💾 Saved: {out_path}")

            # Persist terminal success into state for full resumability
            state[name].update({
                "status":       "succeed",
                "video_url":    result["video_url"],
                "output_path":  str(out_path),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            save_state(state)

            return {
                "filename":    name,
                "checksum":    record["checksum_sha256"],
                "task_id":     task_id,
                "status":      "succeed",
                "video_url":   result["video_url"],
                "output_path": str(out_path),
            }

        except Exception as exc:  # noqa: BLE001 — one bad job must not sink the batch
            log.error(f"  ✗ Failed: {name} — {exc}")
            if name in state:
                state[name].update({"status": "failed", "error": str(exc)})
                save_state(state)
            return {
                "filename": name,
                "checksum": record.get("checksum_sha256"),
                "status":   "failed",
                "error":    str(exc),
            }


async def run_batch(manifests: list[dict], job_cfg: dict) -> list[dict]:
    """Fan out all manifest records across a bounded semaphore and collect results."""
    state = load_state()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [
            process_one(session, sem, record, job_cfg, state)
            for record in manifests
        ]
        results = await asyncio.gather(*tasks)

    return list(results)


# ─── Orchestration ────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kling V3 image-to-video batch pipeline")
    p.add_argument("--input", type=Path, default=INPUT_DIR, help="Input image directory")
    p.add_argument("--output", type=Path, default=OUTPUT_DIR, help="Output video directory")
    p.add_argument("--prompt", type=str, default=None, help="Override generation prompt")
    p.add_argument("--negative-prompt", type=str, default=None, help="Override negative prompt")
    p.add_argument("--cfg-scale", type=float, default=None, help="Image-faithfulness (0–1, lower = more faithful)")
    p.add_argument("--mode", type=str, default=None, choices=["std", "pro"], help="Generation mode")
    p.add_argument("--duration", type=int, default=None, help="Clip duration in seconds")
    p.add_argument("--aspect-ratio", type=str, default=None, help='e.g. "9:16", "16:9", "1:1"')
    p.add_argument("--concurrency", type=int, default=None, help="Max concurrent jobs")
    p.add_argument("--validate-only", action="store_true", help="Build manifest, skip API calls")
    return p.parse_args()


def build_job_config(args: argparse.Namespace) -> dict:
    """Collect only the overrides the user actually supplied; defaults live in submit_job."""
    cfg: dict = {}
    if args.prompt is not None:
        cfg["prompt"] = args.prompt
    if args.negative_prompt is not None:
        cfg["negative_prompt"] = args.negative_prompt
    if args.cfg_scale is not None:
        cfg["cfg_scale"] = args.cfg_scale
    if args.mode is not None:
        cfg["mode"] = args.mode
    if args.duration is not None:
        cfg["duration"] = args.duration
    if args.aspect_ratio is not None:
        cfg["aspect_ratio"] = args.aspect_ratio
    return cfg


def main() -> None:
    global INPUT_DIR, OUTPUT_DIR, MAX_CONCURRENCY

    args = parse_args()
    INPUT_DIR = args.input
    OUTPUT_DIR = args.output
    if args.concurrency is not None:
        MAX_CONCURRENCY = args.concurrency

    if not INPUT_DIR.is_dir():
        log.error(f"Input directory not found: {INPUT_DIR}")
        raise SystemExit(1)

    log.info(f"Stage 1 — validating assets in {INPUT_DIR}")
    manifests, errors = build_manifest(INPUT_DIR)

    if args.validate_only:
        log.info("Validate-only mode: manifest written, skipping submission.")
        return

    if not manifests:
        log.error("No valid images to process. See image_errors.json.")
        raise SystemExit(1)

    if API_KEY in ("", "YOUR_API_KEY"):
        log.error("KLING_API_KEY is not set. Export it before running real jobs.")
        raise SystemExit(1)

    job_cfg = build_job_config(args)

    log.info(f"Stage 2–4 — submitting {len(manifests)} jobs (concurrency={MAX_CONCURRENCY})")
    results = asyncio.run(run_batch(manifests, job_cfg))

    succeeded = [r for r in results if r["status"] == "succeed"]
    failed = [r for r in results if r["status"] == "failed"]

    summary = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "total":          len(results),
        "succeeded":      len(succeeded),
        "failed":         len(failed),
        "rejected_input": len(errors),
        "results":        results,
    }
    RESULTS_FILE.write_text(json.dumps(summary, indent=2))

    log.info(
        f"Batch complete: {len(succeeded)} succeeded, {len(failed)} failed, "
        f"{len(errors)} rejected at validation. Summary → {RESULTS_FILE}"
    )


if __name__ == "__main__":
    main()
