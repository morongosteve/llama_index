# LlamaPacks 📦

## Llama-Pack Usage

If you merely intend to use the llama-pack, then the recommended route is via pip install:

```
pip install llama-index-packs-<name-of-pack>
```

For a list of our llama-packs Python packages, visit [llamahub.ai](https://llamahub.ai/?tab=llama-packs).

On the other hand, if you wish to download a llama-pack and potentially customize it,
you can download it as a template. There are a couple of ways to do so. First,
llama-packs can be downloaded as a template by using the `llamaindex-cli` tool
that comes with `llama-index`:

```bash
llamaindex-cli download-llamapack ZephyrQueryEnginePack --download-dir ./zephyr_pack
```

Or with the `download_llama_pack` function directly (in this case, you must supply
a download directory):

```python
from llama_index.core.llama_pack import download_llama_pack

# download and install dependencies
LlavaCompletionPack = download_llama_pack(
    "LlavaCompletionPack", "./llava_pack"  # ./llava_pack is the download dir
)
```

## RunPod setup guide (recommended for pack installation)

If you are installing many packs on a fresh RunPod machine, use isolated Python
versions and venvs per compatibility group to avoid cross-package dependency
breakage.

### 1) Install and verify `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv --version
```

### 2) Create a dedicated workspace

```bash
mkdir -p ~/llama-packs-runpod && cd ~/llama-packs-runpod
```

### 3) Create a Python 3.11 environment for incompatible packs

Use Python 3.11 (or 3.12) for packs that fail on Python 3.14, including:

- `llama-index-packs-agent-search-retriever` (`agent-search` supports `<3.12`)
- `llama-index-finetuning` (`tree-sitter-languages` wheels are unavailable for cp314)

```bash
uv venv --python 3.11 .venv-py311
source .venv-py311/bin/activate
python -V
```

Install in this env:

```bash
uv pip install -U pip setuptools wheel
uv pip install llama-index-packs-agent-search-retriever
uv pip install llama-index-finetuning
```

### 4) Create a separate environment for pyppeteer-based packs

`llama-index-packs-amazon-product-extraction` can pull `urllib3<2` through
`pyppeteer`. Keep it isolated so it does not downgrade `urllib3` for unrelated
projects.

```bash
deactivate 2>/dev/null || true
uv venv --python 3.12 .venv-py312-pyppeteer
source .venv-py312-pyppeteer/bin/activate
uv pip install -U pip setuptools wheel
uv pip install llama-index-packs-amazon-product-extraction
python -c "import urllib3; print(urllib3.__version__)"
```

### 5) Install safe packs in a main environment

```bash
deactivate 2>/dev/null || true
uv venv --python 3.12 .venv-main
source .venv-main/bin/activate
uv pip install llama-index-packs-vectara-rag
uv pip install llama-index-packs-diff-private-simple-dataset
```

### 6) Install `self-rag` with build prerequisites and patience

`llama-index-packs-self-rag` may compile `llama_cpp_python` from source. On
RunPod this can take several minutes.

```bash
# Ubuntu/Debian base images
sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build

# inside a clean env (reuse .venv-main or create another)
uv pip install llama-index-packs-self-rag
```

If it seems stuck, check progress before cancelling:

```bash
ps aux | grep -E "(cmake|ninja|gcc|g\+\+)" | grep -v grep
```

### 7) Quick validation checklist

```bash
python - <<'PY'
packages = [
    "llama_index.packs.agent_search_retriever",
    "llama_index.finetuning",
    "llama_index.packs.amazon_product_extraction",
    "llama_index.packs.vectara_rag",
]
for pkg in packages:
    try:
        __import__(pkg)
        print(f"OK: {pkg}")
    except Exception as e:
        print(f"FAIL: {pkg}: {e}")
PY
```

### 8) Operational recommendation for team setups

- Keep each pack-family in its own venv.
- Standardize on Python 3.11 or 3.12 for broadest compatibility.
- Avoid global installs on shared instances.
