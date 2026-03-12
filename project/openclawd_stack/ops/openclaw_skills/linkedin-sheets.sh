#!/bin/bash
# LinkedIn-to-Sheets: Read companies from a Google Sheet tab, search LinkedIn, write URLs back.
# Usage: ./linkedin-sheets.sh <tab_name> <start_row> <end_row>
# Example: ./linkedin-sheets.sh vc_payments 2 32

TAB="${1:-payments}"
START="${2:-2}"
END="${3:-}"

cd /home/albi_agent/openclawd_stack || exit 1

# Load environment
set -a
source .env 2>/dev/null
set +a

export GOOGLE_APPLICATION_CREDENTIALS="/home/albi_agent/.secrets/google/credentials.json"

echo "🔍 LinkedIn Search: tab=$TAB, rows=$START-$END"

CMD="python3 ops/linkedin_search.py --tab $TAB --start-row $START"
if [[ -n "$END" ]]; then
  CMD="$CMD --end-row $END"
fi

echo "Ejecutando: $CMD"
eval $CMD

echo ""
echo "✅ LinkedIn search completado. Revisa la pestaña '$TAB' en Google Sheets."
