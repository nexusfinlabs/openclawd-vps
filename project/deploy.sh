#!/usr/bin/env bash
set -euo pipefail

VPS_HOST="openclawd-vps"
REMOTE_DIR="~/openclawd_stack"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)/openclawd_stack"

echo "[deploy] rsync -> $VPS_HOST:$REMOTE_DIR"
rsync -av --delete \
  --exclude '.env' \
  --exclude 'vault' \
  --exclude '**/.env' \
  "$LOCAL_DIR/" "$VPS_HOST:$REMOTE_DIR/"

echo "[deploy] docker compose up -d --build (needs sudo)"
ssh -t "$VPS_HOST" "cd $REMOTE_DIR && sudo docker compose up -d --build"

echo "[deploy] status"
ssh -t "$VPS_HOST" "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | sed -n '1,20p'"

echo "[deploy] restarting OpenClaw gateway (to pick up system-prompt changes)..."
ssh "$VPS_HOST" 'export PATH="/home/albi_agent/.nvm/versions/node/v22.22.0/bin:$PATH" && openclaw gateway stop 2>/dev/null; sleep 2 && sudo systemctl start openclaw-gateway 2>/dev/null && sleep 3 && echo "Gateway: $(sudo systemctl is-active openclaw-gateway) — PID: $(pgrep -f openclaw-gateway)"'

echo "[deploy] ✅ DONE"
