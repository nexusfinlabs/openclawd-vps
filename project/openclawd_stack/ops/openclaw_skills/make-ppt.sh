#!/bin/bash
# make-ppt.sh — Generate a professional PPTX presentation
# Usage: make-ppt.sh "5 slides sobre AI en payments: tendencias, riesgos"

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_DIR="$(dirname "$SCRIPT_DIR")"
export PATH="/home/albi_agent/.nvm/versions/node/v22.22.0/bin:$PATH"

# Load env
[ -f "$OPS_DIR/.env" ] && set -a && source "$OPS_DIR/.env" && set +a

if [ -z "${1:-}" ]; then
  openclaw message send --channel whatsapp --target 34605693177 --message "❌ Uso: \`!make-ppt 5 slides sobre AI en fintech\`"
  exit 1
fi

request="$*"

# Generate PPT
output=$(python3 "$OPS_DIR/ops/ppt_generator.py" "$request" 2>&1)

# Extract file path from output
pptx_path=$(echo "$output" | grep -o '/home/.*\.pptx' | head -1)

# Send summary message
openclaw message send --channel whatsapp --target 34605693177 --message "$output"

# Send the PPTX file if generated
if [ -n "$pptx_path" ] && [ -f "$pptx_path" ]; then
  openclaw message send --channel whatsapp --target 34605693177 --media "$pptx_path"
fi
