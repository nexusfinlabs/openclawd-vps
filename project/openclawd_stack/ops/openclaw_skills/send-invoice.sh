#!/bin/bash
# send-invoice.sh — Send a previously generated invoice via email
# Usage: send-invoice.sh OC-FRA003 [email@client.com]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_DIR="$(dirname "$SCRIPT_DIR")"
export PATH="/home/albi_agent/.nvm/versions/node/v22.22.0/bin:$PATH"

# Load env
[ -f "$OPS_DIR/.env" ] && set -a && source "$OPS_DIR/.env" && set +a

invoice_ref="${1:-last}"

# If email provided as 2nd arg, we need to update the invoice data
if [ -n "${2:-}" ]; then
  data_file="$HOME/.openclaw/workspace/docs/drafts/${invoice_ref}_data.json"
  if [ -f "$data_file" ]; then
    python3 -c "
import json
with open('$data_file') as f: d=json.load(f)
d['client_email']='$2'
with open('$data_file','w') as f: json.dump(d,f,indent=2,ensure_ascii=False)
print('Email actualizado: $2')
"
  fi
fi

# Run send
output=$(python3 "$OPS_DIR/ops/invoice_manager.py" send "$invoice_ref" 2>&1)

# Send result via WhatsApp
openclaw message send --channel whatsapp --target 34605693177 --message "$output"
