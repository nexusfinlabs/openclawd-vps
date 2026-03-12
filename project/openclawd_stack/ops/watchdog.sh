#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/openclawd_stack"
LOG="$ROOT/state/watchdog.log"
mkdir -p "$ROOT/state"

log(){ echo "[$(date -Is)] $*" | tee -a "$LOG"; }

# 1) gateway openclaw (si lo necesitas para generar targets, no para runner)
openclaw health >/dev/null 2>&1 || true

# 2) stack docker
if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  log "API health failed -> restarting docker compose"
  sudo docker compose -f "$ROOT/docker-compose.yml" up -d --build || true
fi

# 3) worker container arriba
if ! sudo docker ps --format '{{.Names}}' | grep -qx oc_worker; then
  log "oc_worker not running -> restarting compose"
  sudo docker compose -f "$ROOT/docker-compose.yml" up -d --build || true
fi
