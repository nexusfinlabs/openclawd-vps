#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# ops/wa_watchdog.sh — WhatsApp 24/7 auto-recovery
#
# Runs every hour via cron.
# Checks if OpenClaw gateway has an active WhatsApp session.
# If not, re-runs channels login (no QR needed — saved creds).
#
# Cron entry (run as albi_agent):
#   0 * * * * /bin/bash ~/openclawd_stack/ops/wa_watchdog.sh >> ~/openclawd_stack/state/wa_watchdog.log 2>&1
# ─────────────────────────────────────────────────────────
set -euo pipefail

export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
LOG="$HOME/openclawd_stack/state/wa_watchdog.log"
OC_LOG_DIR="/tmp/openclaw"
LOCK="$HOME/openclawd_stack/state/wa_watchdog.lock"

mkdir -p "$(dirname "$LOG")"

log() { printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

# ── prevent concurrent runs ──
exec 9>"$LOCK"
if ! flock -n 9; then
    log "Already running, exiting."
    exit 0
fi

# ── check 1: gateway process alive? ──
if ! pgrep -f 'openclaw-gatewa' > /dev/null 2>&1; then
    log "WARN: Gateway process not found. Restarting systemd service..."
    systemctl --user restart openclaw-gateway
    sleep 5
fi

# ── check 2: recent WhatsApp activity in gateway logs? ──
# Look for disconnect or zero messagesHandled in last 90 minutes
TODAY_LOG="$OC_LOG_DIR/openclaw-$(date +%Y-%m-%d).log"
THRESHOLD=$(date -d '90 minutes ago' -Is 2>/dev/null || date -v-90M -Is 2>/dev/null || echo "")

wa_ok=false

if [[ -f "$TODAY_LOG" ]]; then
    # Check for "Listening for personal WhatsApp" in last 90 min
    if grep -q '"Listening for personal WhatsApp' "$TODAY_LOG"; then
        # Check that no disconnect occurred after last "Listening" entry
        last_listen=$(grep -n '"Listening for personal WhatsApp' "$TODAY_LOG" | tail -1 | cut -d: -f1)
        last_disconnect=$(grep -n '"WhatsApp Web connection closed\|Connection Terminated\|connection errored' "$TODAY_LOG" | tail -1 | cut -d: -f1)

        if [[ -z "$last_disconnect" ]] || [[ "$last_listen" -gt "$last_disconnect" ]]; then
            wa_ok=true
        fi
    fi
fi

if $wa_ok; then
    log "OK: WhatsApp session active."
    exit 0
fi

# ── WhatsApp is down — attempt recovery ──
log "WARN: WhatsApp not active. Attempting recovery via channels login..."

# Give login 30s to connect using saved credentials (no QR needed)
timeout 30 openclaw channels login --channel whatsapp 2>&1 | tee -a "$LOG" || true

sleep 3

# ── verify recovery ──
TODAY_LOG="$OC_LOG_DIR/openclaw-$(date +%Y-%m-%d).log"
if grep -q '"WhatsApp Web connected\|Listening for personal WhatsApp' "$TODAY_LOG" 2>/dev/null; then
    log "RECOVERED: WhatsApp reconnected successfully."
else
    log "ERROR: WhatsApp recovery failed. Manual intervention may be needed."
    log "  Run: ssh -t openclawd-vps 'export PATH=\$HOME/.nvm/versions/node/v22.22.0/bin:\$PATH && openclaw channels login --channel whatsapp --verbose'"
fi
