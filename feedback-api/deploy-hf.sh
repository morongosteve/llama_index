#!/usr/bin/env bash
set -euo pipefail

# Feedback API — Deploy to Hugging Face Spaces
#
# Usage:
#   export HF_TOKEN="hf_your_token_here"
#   bash deploy-hf.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FATAL]${NC} $1"; exit 1; }

[ -z "${HF_TOKEN:-}" ] && fail "HF_TOKEN not set. Get one at https://huggingface.co/settings/tokens"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- PREFLIGHT ---

log "Checking prerequisites..."

command -v git >/dev/null 2>&1 || fail "git not found"
command -v npm >/dev/null 2>&1 || fail "npm not found"
command -v hf >/dev/null 2>&1 || {
    log "Installing Hugging Face CLI..."
    pip install --upgrade huggingface_hub
}

[ -f "Dockerfile" ] || fail "Dockerfile not found in $SCRIPT_DIR"
[ -f "package.json" ] || fail "package.json not found"

# --- LOGIN ---

log "Logging into Hugging Face..."
hf auth login --token "$HF_TOKEN" --add-to-git-credential 2>/dev/null || true

HF_USER=$(hf whoami 2>/dev/null | head -1 | awk '{print $1}')
[ -z "$HF_USER" ] && fail "Could not determine HF username. Check your token."
log "Logged in as: $HF_USER"

SPACE_NAME="feedback-api"
SPACE_URL="https://huggingface.co/spaces/$HF_USER/$SPACE_NAME"
LIVE_URL="https://$HF_USER-$SPACE_NAME.hf.space"

# --- BUILD CHECK ---

log "Verifying build..."
npm install --silent 2>/dev/null
npm run build 2>/dev/null || fail "Build failed. Fix errors before deploying."
log "Build passed."

# --- CREATE SPACE ---

log "Creating HF Space..."
hf repo create "$SPACE_NAME" --type space --space-sdk docker 2>/dev/null || {
    warn "Space already exists or creation failed. Continuing..."
}

# --- GIT PUSH ---

log "Preparing git..."

if [ ! -d ".git" ]; then
    git init
fi

# Ensure we have a commit
git add -A
git add -f src/ 2>/dev/null || true
git diff --cached --quiet || git commit -m "Deploy Feedback API to HF Spaces"

# Set remote
REMOTE_URL="https://huggingface.co/spaces/$HF_USER/$SPACE_NAME"
git remote remove hf 2>/dev/null || true
git remote add hf "$REMOTE_URL"

log "Pushing to $REMOTE_URL..."
PUSH_OK=false
for i in 1 2 3; do
    if git push hf HEAD:main --force 2>/dev/null; then
        PUSH_OK=true
        break
    fi
    warn "Push attempt $i failed. Retrying in $((i * 5))s..."
    sleep $((i * 5))
done

$PUSH_OK || fail "Push failed after 3 attempts."

# --- VERIFY ---

log "Waiting for Space to build (this can take 3-5 minutes)..."
echo ""

for i in $(seq 1 15); do
    sleep 20
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$LIVE_URL/api/feedback/summary" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        break
    fi
    echo "  Attempt $i/15 — status $HTTP_CODE (building...)"
done

echo ""
echo "============================================"
echo -e "${GREEN}  FEEDBACK API — DEPLOYED${NC}"
echo "============================================"
echo ""
echo "  Space:      $SPACE_URL"
echo "  Live API:   $LIVE_URL"
echo ""
echo "  Test:"
echo "    curl $LIVE_URL/api/feedback"
echo "    curl $LIVE_URL/api/feedback/summary"
echo "    curl $LIVE_URL/llms.txt"
echo "    curl $LIVE_URL/llms-full.txt"
echo ""
echo "============================================"
