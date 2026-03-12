#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# ops/runner.sh  –  cron-safe single-URL processor
#   • flock global lock   → no parallel runs
#   • _work.targets copy  → never touches targets.txt
#   • ^https:// filter    → ignores junk lines
#   • jq for JSON         → no invalid control chars
#   • timestamped log
# ─────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$HOME/openclawd_stack"
STATE="$ROOT/state"
TARGETS="$STATE/targets.txt"
WORK="$STATE/_work.targets"
DONE="$STATE/done.txt"
FAILED="$STATE/failed.txt"
LOCKFILE="$STATE/runner.lock"
LOG="$STATE/runner.log"

mkdir -p "$STATE"
touch "$DONE" "$FAILED" "$LOG"

# ── global lock (non-blocking) ──────────────────────────
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  exit 0        # another instance is running → silently exit
fi

# ── helpers ─────────────────────────────────────────────
log() { printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

api_post_job() {
  local url="$1"
  # build JSON safely with jq (avoids "Invalid control character")
  local payload
  payload=$(jq -nc --arg u "$url" --arg n "texas-list" \
    '{"url":$u,"note":$n}')
  curl -sS -X POST "http://127.0.0.1:8000/jobs" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1 | tee -a "$LOG"
}

db_has_url() {
  local url="$1"
  sudo docker exec -i oc_postgres \
    psql -U openclawd -d openclawd -tAc \
    "SELECT count(1) FROM pages WHERE url='${url//\'/\'\'}'" \
    2>/dev/null | tr -d ' ' | grep -qE '^[1-9]'
}

redis_failed_has_url() {
  local url="$1"
  sudo docker exec -i oc_redis \
    redis-cli LRANGE jobs:failed 0 -1 \
    | grep -q "\"url\": \"$url\""
}

is_done()   { grep -Fxq "$1" "$DONE"   2>/dev/null; }
is_failed() { grep -Fxq "$1" "$FAILED" 2>/dev/null; }

# ── pick next URL ──────────────────────────────────────
next_url() {
  # work on a snapshot, never on the original
  cp -f "$TARGETS" "$WORK"

  # only lines matching ^https://
  grep -E '^https://' "$WORK" | while read -r u; do
    is_done   "$u" && continue
    is_failed "$u" && continue
    echo "$u"
    return 0
  done
  return 1
}

# ── main ────────────────────────────────────────────────
log "runner start"

if [[ ! -f "$TARGETS" ]]; then
  log "ERROR: missing $TARGETS"
  exit 1
fi

# ensure stack is up
sudo docker compose -f "$ROOT/docker-compose.yml" up -d --build \
  >>/dev/null 2>&1 || true

u="$(next_url || true)"
if [[ -z "${u:-}" ]]; then
  log "No pending URLs. done=$(wc -l < "$DONE") failed=$(wc -l < "$FAILED")"
  exit 0
fi

log "Processing: $u"
api_post_job "$u" >/dev/null || true

# wait up to 90 s for result in DB or redis failed list
for _ in $(seq 1 30); do
  if db_has_url "$u"; then
    echo "$u" >> "$DONE"
    log "DONE: $u"
    exit 0
  fi
  if redis_failed_has_url "$u"; then
    echo "$u" >> "$FAILED"
    log "FAILED: $u (redis jobs:failed)"
    exit 0
  fi
  sleep 3
done

# timeout → mark failed so pipeline doesn't block
echo "$u" >> "$FAILED"
log "FAILED: $u (timeout 90s)"
exit 0
