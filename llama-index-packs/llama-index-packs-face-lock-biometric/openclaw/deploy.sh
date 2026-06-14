#!/usr/bin/env bash
set -euo pipefail

# Face Lock Bot — One-Command Deploy Script
# Run this on your Dell OptiPlex (or any Linux box with Docker)
#
# Usage:
#   export TELEGRAM_BOT_TOKEN="your-token-from-botfather"
#   export STRIPE_WEBHOOK_SECRET="whsec_..."  # optional, for payments
#   bash deploy.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FATAL]${NC} $1"; exit 1; }

# --- PREFLIGHT ---

log "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || {
    warn "Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sh
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker "$USER"
    log "Docker installed. You may need to log out and back in for group changes."
}

docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 not found. Update Docker."

[ -z "${TELEGRAM_BOT_TOKEN:-}" ] && fail "TELEGRAM_BOT_TOKEN is not set. Get one from @BotFather on Telegram."

# --- LOCATE PROJECT ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    fail "docker-compose.yml not found in $PROJECT_DIR"
fi

log "Project directory: $PROJECT_DIR"

# --- STAGE PYTHON PACKAGE ---

log "Staging Python package for Docker build..."

FACE_LOCK_PKG="$PROJECT_DIR/face_lock_pkg"
PARENT_DIR="$(dirname "$PROJECT_DIR")"

rm -rf "$FACE_LOCK_PKG"
mkdir -p "$FACE_LOCK_PKG/llama_index/packs/face_lock_biometric"

if [ -d "$PARENT_DIR/llama_index/packs/face_lock_biometric" ]; then
    cp -r "$PARENT_DIR/llama_index/packs/face_lock_biometric/"* \
          "$FACE_LOCK_PKG/llama_index/packs/face_lock_biometric/"
    cp "$PARENT_DIR/pyproject.toml" "$FACE_LOCK_PKG/" 2>/dev/null || true
    cp "$PARENT_DIR/README.md" "$FACE_LOCK_PKG/" 2>/dev/null || true
    touch "$FACE_LOCK_PKG/llama_index/__init__.py"
    touch "$FACE_LOCK_PKG/llama_index/packs/__init__.py"
    log "Python package staged."
else
    warn "Parent package not found at $PARENT_DIR/llama_index — skipping staging."
    warn "The Docker build will fail unless you install the package another way."
fi

# --- WRITE ENV FILE ---

log "Writing .env file..."
cat > "$PROJECT_DIR/.env" <<ENVEOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN:-}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-}
ENVEOF
chmod 600 "$PROJECT_DIR/.env"

# --- BUILD AND LAUNCH ---

log "Building Docker images..."
cd "$PROJECT_DIR"
docker compose --env-file .env build --no-cache

log "Starting services..."
docker compose --env-file .env up -d

# --- VERIFY ---

log "Waiting for health check..."
RETRIES=10
until docker compose exec -T face-lock-bot node -e "
  require('http').get('http://localhost:3000/health', r => {
    let d=''; r.on('data',c=>d+=c); r.on('end',()=>{console.log(d);process.exit(r.statusCode===200?0:1)})
  }).on('error', () => process.exit(1))
" 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    [ $RETRIES -eq 0 ] && { warn "Health check failed after 10 attempts. Check logs:"; docker compose logs --tail 20; break; }
    sleep 3
done

# --- REPORT ---

echo ""
echo "============================================"
echo -e "${GREEN}  FACE LOCK BOT — DEPLOYED${NC}"
echo "============================================"
echo ""
echo "  Bot:        Running (send a photo on Telegram)"
echo "  Health:     http://localhost:3000/health"
echo "  Logs:       docker compose logs -f"
echo "  Stop:       docker compose down"
echo "  Restart:    docker compose restart"
echo ""
[ -n "${STRIPE_WEBHOOK_SECRET:-}" ] && echo "  Stripe:     http://localhost:3001/webhook"
echo ""
echo "  Container:  $(docker compose ps --format '{{.Name}} {{.Status}}')"
echo ""
echo "============================================"
