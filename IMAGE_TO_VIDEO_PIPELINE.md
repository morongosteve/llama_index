# Image-to-Video Pipeline

Production-grade async batch pipeline that animates still images into short
clips via the Kling V3 `image2video` API.

## Features

- **Multi-stage validation** — size ceiling, PIL header + full-decode integrity
  check, dimension floor, aspect-ratio bounds, color-mode normalization, raw
  base64 encoding (no data-URI prefix), SHA-256 checksum.
- **Async submission + polling** with exponential backoff and jitter.
- **Transient-HTTP retry** — automatic retry on `429`/`5xx` with `Retry-After`
  honoring, distinct from job polling.
- **Crash-resumable batching** — in-flight jobs are persisted to `state.json`
  and skipped on re-run rather than resubmitted.
- **Per-job error isolation** — one failed job never sinks the batch.
- Emits `image_manifest.json`, `image_errors.json`, and `results.json`.

## Install

```bash
pip install -r image_to_video_requirements.txt
```

## Usage

```bash
export KLING_API_KEY="sk-..."

# Full run: validate inputs/, submit, poll, download to outputs/
python image_to_video_pipeline.py --input inputs --output outputs

# Dry run: build the manifest only, no API calls
python image_to_video_pipeline.py --validate-only
```

### CLI options

| Flag | Description |
|------|-------------|
| `--input` | Input image directory (default `inputs`) |
| `--output` | Output video directory (default `outputs`) |
| `--prompt` | Override the generation prompt |
| `--negative-prompt` | Override the negative prompt |
| `--cfg-scale` | Image-faithfulness (0–1, lower = more faithful) |
| `--mode` | `std` or `pro` |
| `--duration` | Clip duration in seconds |
| `--aspect-ratio` | e.g. `9:16`, `16:9`, `1:1` |
| `--concurrency` | Max concurrent jobs |
| `--provider` | Backend: `kling` (default) or `goenhance` |
| `--validate-only` | Build manifest, skip API calls |
| `--dry-run` | Validate + print a cost estimate, then exit (no API calls) |

## Providers & cost estimation

Backends are pluggable via the `VideoProvider` interface in `video_providers.py`.
Each provider is a small declarative adapter (endpoints, request payload,
response parsing, pricing); the pipeline owns the generic retry / polling /
concurrency machinery. Built-in: **Kling V3** and **GoEnhance**. Add a new one
by subclassing `VideoProvider` and registering it in `PROVIDERS`.

```bash
# Estimate spend before committing to a batch
python image_to_video_pipeline.py --input inputs --dry-run --duration 10 --mode pro
# → Dry run [kling]: 3 clips × 10.0s ≈ USD 1.47 (USD 0.49/clip; ...)

# Switch backends
python image_to_video_pipeline.py --input inputs --provider goenhance
```

> Pricing constants in each provider are **approximate** and should be verified
> against the backend's current pricing. The GoEnhance endpoint paths/schema are
> isolated in `GoEnhanceProvider` and should be confirmed against its live API.

## Output files

| File | Contents |
|------|----------|
| `image_manifest.json` | Validated images + validation rules |
| `image_errors.json` | Rejected inputs with reasons |
| `state.json` | Per-image task state (enables resume) |
| `results.json` | Final batch summary |

## Testing

```bash
python -m pytest tests/test_image_to_video_pipeline.py -q
```

Tests are self-contained: no live network, no `pytest-asyncio` plugin required
(coroutines are driven via `asyncio.run`, and `aiohttp` is faked at the session
level).

## Face Lock integration (end-to-end identity-locked animation)

`face_lock_pipeline.py` wires the biometric **Face Lock** tooling into this
pipeline so a clip's identity is constrained by a reference face and verified
afterward:

1. **Lock** — measure a reference face (`face_lock_core.FaceAnalyzer`) into
   biometric metrics.
2. **Animate** — `build_locked_job_config` folds the identity descriptors into
   the video prompt and the lock's **anti-drift** terms into the negative
   prompt, then runs this pipeline.
3. **Verify** — sample a midpoint frame from each rendered clip, re-measure, and
   compare against the lock via `DriftDetector`.
4. **Quarantine + report** — clips that drifted are moved to
   `outputs/drift_rejected/`; a `report.html` (thumbnails + per-metric pass/fail)
   and `drift_results.json` are written.

The reusable Face Lock logic now lives in `face_lock_core.py` (imported by both
the Streamlit `face_lock_app.py` and this bridge). `cv2`/`mediapipe` are
imported lazily, so the pure-logic classes import without them.

```bash
export KLING_API_KEY="sk-..."
# Full flow: lock onto ref.png, animate inputs/, verify + report into outputs/
python face_lock_pipeline.py --reference ref.png --subject "Aria" \
    --input inputs --output outputs

# Inspect the identity-locked job config without calling the API
python face_lock_pipeline.py --reference ref.png --subject "Aria" --lock-only
```

The verify/animate stages additionally require the Face Lock vision deps:

```bash
pip install -r face_lock_requirements.txt   # mediapipe, opencv, numpy, Pillow, streamlit
```

```bash
python -m pytest tests/test_face_lock_pipeline.py -q
```
