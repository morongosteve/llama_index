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
| `--validate-only` | Build manifest, skip API calls |

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
