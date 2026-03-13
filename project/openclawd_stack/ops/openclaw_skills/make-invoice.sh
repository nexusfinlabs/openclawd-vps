#!/bin/bash
# make-invoice.sh — Generate invoice PDF from natural language
# Usage: make-invoice.sh "5000 consulting para TechCorp"

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_DIR="$(dirname "$SCRIPT_DIR")"
export PATH="/home/albi_agent/.nvm/versions/node/v22.22.0/bin:$PATH"

# Load env
[ -f "$OPS_DIR/.env" ] && set -a && source "$OPS_DIR/.env" && set +a

if [ -z "${1:-}" ]; then
  openclaw message send --channel whatsapp --target 34605693177 --message "❌ Uso: \`!make-invoice 5000 consulting para TechCorp\`"
  exit 1
fi

# Combine all args as the request text
request="$*"

# Run invoice manager
output=$(python3 "$OPS_DIR/ops/invoice_manager.py" make "$request" 2>&1)

# Send result via WhatsApp
openclaw message send --channel whatsapp --target 34605693177 --message "$output"
