# image-to-video

Batch **image-to-video** pipeline with pluggable providers, cost estimation, and
optional **Face Lock** biometric drift verification.

## Install

```bash
pip install image-to-video                 # core (aiohttp, Pillow)
pip install "image-to-video[vision]"       # + Face Lock (numpy, opencv, mediapipe)
```

From source (editable):

```bash
pip install -e ./image-to-video
```

## Console commands

Two entry points are installed:

| Command | Module | Purpose |
|---------|--------|---------|
| `i2v` | `image_to_video.pipeline:main` | Validate → submit → poll → download a batch |
| `face-lock-pipeline` | `image_to_video.face_lock_bridge:main` | Lock identity → animate → drift-verify → report |

```bash
export KLING_API_KEY="sk-..."

# Estimate cost before spending (no API calls)
i2v --input inputs --dry-run --duration 10 --mode pro

# Run a batch (default provider: kling; also: goenhance)
i2v --input inputs --output outputs --provider kling

# Identity-locked end-to-end (requires the [vision] extra)
face-lock-pipeline --reference ref.png --subject "Aria" --input inputs --output outputs
```

## Layout

```
image-to-video/
├── pyproject.toml
├── src/image_to_video/
│   ├── pipeline.py          # generic batch machinery + CLI
│   ├── providers.py         # VideoProvider interface + Kling/GoEnhance + cost
│   ├── face_lock_core.py    # biometric measurement / prompt / drift logic
│   └── face_lock_bridge.py  # lock → animate → verify → report
└── tests/                   # self-contained: no network, no cv2/mediapipe
```

Add a backend by subclassing `VideoProvider` in `providers.py` and registering it
in `PROVIDERS`. Pricing constants and the GoEnhance endpoint/schema are
approximate — verify against each backend's live API before production use.

## Test

```bash
pip install -e "./image-to-video[dev]"
pytest image-to-video/tests -q
```
